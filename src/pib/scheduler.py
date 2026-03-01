"""Scheduler: APScheduler AsyncIOScheduler for all cron jobs."""

import logging

log = logging.getLogger(__name__)


async def setup_scheduler(app, db):
    """Configure and start the APScheduler with all cron jobs.

    CRITICAL: Use AsyncIOScheduler, NEVER BlockingScheduler (freezes event loop).
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.warning("APScheduler not installed — scheduler disabled")
        return None

    scheduler = AsyncIOScheduler()

    # ─── Calendar Sync ───
    scheduler.add_job(
        lambda: _run_job(db, _calendar_incremental_sync),
        CronTrigger.from_crontab("*/15 * * * *"),
        id="calendar_incremental_sync",
    )
    scheduler.add_job(
        lambda: _run_job(db, _calendar_full_sync),
        CronTrigger.from_crontab("0 2 * * *"),
        id="calendar_full_sync",
    )
    scheduler.add_job(
        lambda: _run_job(db, _compute_daily_states),
        CronTrigger.from_crontab("30 5 * * *"),
        id="compute_daily_states",
    )

    # ─── Tasks ───
    scheduler.add_job(
        lambda: _run_job(db, _recurring_spawn),
        CronTrigger.from_crontab("0 6 * * *"),
        id="recurring_spawn",
    )
    scheduler.add_job(
        lambda: _run_job(db, _escalation_check),
        CronTrigger.from_crontab("0 17 * * *"),
        id="escalation_check",
    )

    # ─── Proactive ───
    scheduler.add_job(
        lambda: _run_job(db, _morning_digest),
        CronTrigger.from_crontab("15 7 * * *"),
        id="morning_digest",
    )
    scheduler.add_job(
        lambda: _run_job(db, _proactive_trigger_scan),
        CronTrigger.from_crontab("*/30 7-22 * * *"),
        id="proactive_trigger_scan",
    )

    # ─── Memory ───
    scheduler.add_job(
        lambda: _run_job(db, _auto_promote_session_facts),
        CronTrigger.from_crontab("0 */6 * * *"),
        id="auto_promote_session_facts",
    )

    # ─── Sheets ───
    scheduler.add_job(
        lambda: _run_job(db, _push_to_sheets),
        CronTrigger.from_crontab("*/15 * * * *"),
        id="push_to_sheets",
    )

    # ─── System ───
    scheduler.add_job(
        lambda: _run_job(db, _health_probe),
        CronTrigger.from_crontab("*/30 * * * *"),
        id="health_probe",
    )
    scheduler.add_job(
        lambda: _run_job(db, _sqlite_backup),
        CronTrigger.from_crontab("0 * * * *"),
        id="sqlite_backup",
    )
    scheduler.add_job(
        lambda: _run_job(db, _cleanup_expired),
        CronTrigger.from_crontab("0 3 * * *"),
        id="cleanup_expired",
    )
    scheduler.add_job(
        lambda: _run_job(db, _fts5_rebuild),
        CronTrigger.from_crontab("0 2 * * 0"),
        id="fts5_rebuild",
    )

    # ─── Comms Domain ───
    scheduler.add_job(
        lambda: _run_job(db, _extraction_worker),
        CronTrigger.from_crontab("*/5 * * * *"),
        id="extraction_worker",
    )
    scheduler.add_job(
        lambda: _run_job(db, _unsnooze_comms),
        CronTrigger.from_crontab("*/15 * * * *"),
        id="unsnooze_comms",
    )
    scheduler.add_job(
        lambda: _run_job(db, _retry_failed_extractions),
        CronTrigger.from_crontab("0 */4 * * *"),
        id="retry_failed_extractions",
    )
    scheduler.add_job(
        lambda: _run_job(db, _expire_stale_drafts),
        CronTrigger.from_crontab("0 22 * * *"),
        id="expire_stale_drafts",
    )
    scheduler.add_job(
        lambda: _run_job(db, _synthesize_voice_profiles),
        CronTrigger.from_crontab("0 3 * * 0"),
        id="synthesize_voice_profiles",
    )

    scheduler.start()
    log.info(f"Scheduler started with {len(scheduler.get_jobs())} jobs")
    return scheduler


def _run_job(db, fn):
    """Wrapper to run async job functions safely."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(fn(db))
    except Exception as e:
        log.error(f"Scheduler job failed: {e}", exc_info=True)


# ─── Job Implementations ───

async def _morning_digest(db):
    """Build and log morning digest (7:15 AM ET). Delivery via adapters when wired."""
    from pib.proactive import build_morning_digest_data
    log.info("Running morning digest")
    data = await build_morning_digest_data(db)
    log.info(f"Morning digest assembled: {len(data)} sections")
    # TODO: pipe through LLM to compose natural language, then send via outbound adapter


async def _proactive_trigger_scan(db):
    """Scan for proactive trigger conditions every 30 minutes."""
    from pib.proactive import can_send_proactive, scan_triggers
    log.info("Scanning proactive triggers")

    members = await db.execute_fetchall(
        "SELECT id FROM common_members WHERE active = 1 AND role = 'parent'"
    )
    for member in members or []:
        member_id = member["id"]
        if not await can_send_proactive(db, member_id):
            continue
        fired = await scan_triggers(db, member_id)
        for trigger in fired:
            log.info(f"Trigger fired: {trigger['name']} for {member_id}")
            # TODO: compose message via LLM and send via outbound adapter


async def _recurring_spawn(db):
    """Spawn tasks from ops_recurring at midnight."""
    from datetime import date
    from pib.db import next_id
    from pib.ingest import generate_micro_script

    log.info("Spawning recurring tasks")
    today = date.today()
    rows = await db.execute_fetchall(
        "SELECT * FROM ops_recurring WHERE active = 1 AND "
        "(next_due IS NULL OR next_due <= ?)",
        [today.isoformat()],
    )

    spawned = 0
    for row in rows or []:
        r = dict(row)
        task_id = await next_id(db, "tsk")
        micro = generate_micro_script(r)
        await db.execute(
            "INSERT INTO ops_tasks (id, title, assignee, domain, item_type, due_date, "
            "energy, effort, micro_script, created_by, source_system) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [task_id, r["title"], r.get("assignee", "m-james"), r.get("domain", "tasks"),
             r.get("item_type", "task"), today.isoformat(),
             r.get("energy"), r.get("effort", "small"), micro, "recurring", "scheduler"],
        )

        # Advance next_due based on rrule
        rrule = r.get("rrule", "")
        if "DAILY" in rrule:
            from datetime import timedelta
            next_due = today + timedelta(days=1)
        elif "WEEKLY" in rrule:
            from datetime import timedelta
            next_due = today + timedelta(weeks=1)
        elif "MONTHLY" in rrule:
            next_due = today.replace(month=today.month + 1) if today.month < 12 else today.replace(year=today.year + 1, month=1)
        else:
            next_due = None

        if next_due:
            await db.execute(
                "UPDATE ops_recurring SET next_due = ?, last_spawned = ? WHERE id = ?",
                [next_due.isoformat(), today.isoformat(), r["id"]],
            )
        spawned += 1

    await db.commit()
    log.info(f"Spawned {spawned} recurring tasks")


async def _escalation_check(db):
    """Check for tasks that need escalation (5 PM daily)."""
    log.info("Running escalation check")
    overdue = await db.execute_fetchall(
        "SELECT id, title, assignee, due_date FROM ops_tasks "
        "WHERE due_date < date('now') AND status NOT IN ('done','dismissed','deferred') "
        "ORDER BY due_date"
    )
    if overdue:
        log.info(f"Found {len(overdue)} overdue tasks for escalation")
        # TODO: send escalation notifications via outbound adapter


async def _auto_promote_session_facts(db):
    """Promote high-signal session facts to long-term memory."""
    from pib.memory import auto_promote_session_facts
    log.info("Running memory auto-promotion")
    result = await auto_promote_session_facts(db)
    log.info(f"Promoted {result['promoted']} session facts")


async def _push_to_sheets(db):
    """Push DB data to Google Sheets."""
    from pib.sheets import push_to_sheets
    log.info("Pushing to Google Sheets")
    result = await push_to_sheets(db)
    log.info(f"Sheets sync: {result}")


async def _calendar_incremental_sync(db):
    """Incremental calendar sync every 15 minutes."""
    log.info("Calendar incremental sync — awaiting Google Calendar adapter")
    # TODO: implement when Google Calendar OAuth adapter is wired


async def _calendar_full_sync(db):
    """Full calendar resync at 2 AM."""
    log.info("Calendar full sync — awaiting Google Calendar adapter")
    # TODO: implement when Google Calendar OAuth adapter is wired


async def _compute_daily_states(db):
    """Compute daily calendar states at 5:30 AM."""
    from datetime import date
    from pib.custody import who_has_child
    import json

    log.info("Computing daily states")
    today = date.today()
    config_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    if config_row:
        parent = who_has_child(today, dict(config_row))
        await db.execute(
            "INSERT INTO cal_daily_states (state_date, day_type, custody_states, computed_at) "
            "VALUES (?, 'normal', ?, datetime('now')) "
            "ON CONFLICT(state_date) DO UPDATE SET custody_states = excluded.custody_states, computed_at = excluded.computed_at",
            [today.isoformat(), json.dumps({"charlie": parent})],
        )
        await db.commit()
        log.info(f"Daily state computed: custody={parent}")


async def _health_probe(db):
    """Internal health check every 30 minutes."""
    try:
        row = await db.execute_fetchone("SELECT COUNT(*) as c FROM common_members WHERE active = 1")
        log.info(f"Health probe OK: {row['c']} active members")
    except Exception as e:
        log.error(f"Health probe failed: {e}")


async def _sqlite_backup(db):
    """Hourly SQLite backup."""
    from pib.backup import backup_verify
    log.info("Running SQLite backup")
    await backup_verify(db)


async def _cleanup_expired(db):
    """Clean up expired audit/idempotency entries at 3 AM."""
    from pib.backup import cleanup_expired
    log.info("Running cleanup")
    await cleanup_expired(db)


async def _fts5_rebuild(db):
    """Weekly FTS5 index rebuild (Sunday 2 AM)."""
    from pib.backup import fts5_rebuild
    log.info("Rebuilding FTS5 indexes")
    await fts5_rebuild(db)


# ─── Comms Domain Jobs ───


async def _extraction_worker(db):
    """Run async extraction worker every 5 minutes."""
    from pib.extraction import extraction_worker
    count = await extraction_worker(db)
    if count > 0:
        log.info(f"Extraction worker processed {count} comms")


async def _unsnooze_comms(db):
    """Restore snoozed comms whose snooze has expired."""
    from pib.comms import unsnooze_due
    count = await unsnooze_due(db)
    if count > 0:
        log.info(f"Unsnoozed {count} comms")


async def _retry_failed_extractions(db):
    """Re-attempt failed extractions every 4 hours."""
    from pib.extraction import retry_failed_extractions
    count = await retry_failed_extractions(db)
    if count > 0:
        log.info(f"Re-queued {count} failed extractions")


async def _expire_stale_drafts(db):
    """Expire drafts pending > 24 hours at 10 PM daily."""
    cursor = await db.execute(
        "UPDATE ops_comms SET draft_status = 'rejected' "
        "WHERE draft_status = 'pending' AND created_at <= datetime('now', '-24 hours')"
    )
    await db.commit()
    if cursor.rowcount > 0:
        log.info(f"Expired {cursor.rowcount} stale drafts")


async def _synthesize_voice_profiles(db):
    """Rebuild voice profiles for all active members (Sunday 3 AM)."""
    from pib.voice import synthesize_profiles
    members = await db.execute_fetchall(
        "SELECT id FROM common_members WHERE active = 1 AND role = 'parent'"
    )
    total = 0
    for member in members or []:
        count = await synthesize_profiles(db, member["id"])
        total += count
    if total > 0:
        log.info(f"Synthesized {total} voice profiles")
