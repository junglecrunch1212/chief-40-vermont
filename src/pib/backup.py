"""Backup, verification, FTS5 rebuild, DB size monitoring."""

import logging
import os
import shutil
from datetime import date
from glob import glob

log = logging.getLogger(__name__)


async def fts5_rebuild(db):
    """Rebuild all FTS5 indexes to fix silent staleness. Weekly job."""
    for table in ["mem_long_term_fts", "ops_tasks_fts", "ops_items_fts"]:
        try:
            await db.execute(f"INSERT INTO {table}({table}) VALUES('rebuild')")
            log.info(f"FTS5 rebuild complete: {table}")
        except Exception as e:
            log.error(f"FTS5 rebuild failed for {table}: {e}")


async def backup_verify(backup_dir: str | None = None) -> dict:
    """Verify latest backup integrity. An unverified backup is not a backup."""
    backup_dir = backup_dir or os.environ.get("PIB_BACKUP_DIR", "/opt/pib/data/backups")
    import aiosqlite

    backups = sorted(glob(os.path.join(backup_dir, "*.db")))
    if not backups:
        return {"ok": False, "error": "No backups found"}

    latest = backups[-1]
    verify_path = "/tmp/pib_verify.db"

    try:
        shutil.copy(latest, verify_path)
        async with aiosqlite.connect(verify_path) as db:
            result = await db.execute_fetchone("PRAGMA integrity_check")
            ok = result[0] == "ok" if result else False

        if not ok:
            log.error(f"Backup integrity check FAILED: {latest}")

        return {"ok": ok, "backup": latest}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        if os.path.exists(verify_path):
            os.remove(verify_path)


async def db_size_monitor(db, db_path: str = "/opt/pib/data/pib.db") -> dict:
    """Monitor database size and fragmentation. Runs daily."""
    if not os.path.exists(db_path):
        return {"ok": True, "size_mb": 0}

    size_mb = os.path.getsize(db_path) / (1024 * 1024)

    page_count_row = await db.execute_fetchone("PRAGMA page_count")
    free_pages_row = await db.execute_fetchone("PRAGMA freelist_count")

    page_count = page_count_row[0] if page_count_row else 1
    free_pages = free_pages_row[0] if free_pages_row else 0
    fragmentation = free_pages / page_count if page_count else 0

    result = {
        "ok": True,
        "size_mb": round(size_mb, 1),
        "fragmentation": round(fragmentation, 3),
    }

    if size_mb > 500:
        log.warning(f"Database size: {size_mb:.0f}MB — consider archiving old audit logs")
        result["warning"] = "large_database"

    if fragmentation > 0.30:
        await db.execute("VACUUM")
        log.info(f"VACUUM complete. Was {fragmentation:.0%} fragmented.")
        result["vacuumed"] = True

    return result


async def cleanup_expired(db) -> dict:
    """Clean up expired audit logs, idempotency keys, undo entries."""
    results = {}

    # Audit logs older than 90 days
    r = await db.execute(
        "DELETE FROM common_audit_log WHERE ts < datetime('now', '-90 days')"
    )
    results["audit_deleted"] = r.rowcount

    # Idempotency keys older than 30 days
    r = await db.execute(
        "DELETE FROM common_idempotency_keys WHERE processed_at < datetime('now', '-30 days')"
    )
    results["idempotency_deleted"] = r.rowcount

    # Undo entries older than 7 days
    r = await db.execute(
        "DELETE FROM common_undo_log WHERE created_at < datetime('now', '-7 days')"
    )
    results["undo_deleted"] = r.rowcount

    await db.commit()
    return results
