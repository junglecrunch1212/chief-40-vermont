"""Scheduler: APScheduler AsyncIOScheduler for all cron jobs."""

import logging

log = logging.getLogger(__name__)


async def setup_scheduler(app, db):
    """Configure and start the APScheduler with all cron jobs.

    CRITICAL: Use AsyncIOScheduler, NEVER BlockingScheduler (freezes event loop).
    All jobs are async functions — APScheduler's AsyncIOScheduler handles them natively.
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
        _safe_job, CronTrigger.from_crontab("*/15 * * * *"),
        args=[_calendar_incremental_sync, db], id="calendar_incremental_sync",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 2 * * *"),
        args=[_calendar_full_sync, db], id="calendar_full_sync",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("30 5 * * *"),
        args=[_compute_daily_states, db], id="compute_daily_states",
    )

    # ─── Tasks ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 6 * * *"),
        args=[_recurring_spawn, db], id="recurring_spawn",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 17 * * *"),
        args=[_escalation_check, db], id="escalation_check",
    )

    # ─── Proactive ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("15 7 * * *"),
        args=[_morning_digest, db], id="morning_digest",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("*/30 7-22 * * *"),
        args=[_proactive_trigger_scan, db], id="proactive_trigger_scan",
    )

    # ─── Memory ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 */6 * * *"),
        args=[_auto_promote_session_facts, db], id="auto_promote_session_facts",
    )

    # ─── Sheets ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("*/15 * * * *"),
        args=[_push_to_sheets, db], id="push_to_sheets",
    )

    # ─── System ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("*/30 * * * *"),
        args=[_health_probe, db], id="health_probe",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 * * * *"),
        args=[_sqlite_backup, db], id="sqlite_backup",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 3 * * *"),
        args=[_cleanup_expired, db], id="cleanup_expired",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 2 * * 0"),
        args=[_fts5_rebuild, db], id="fts5_rebuild",
    )

    # ─── Comms Domain ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("*/5 * * * *"),
        args=[_extraction_worker, db], id="extraction_worker",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("*/15 * * * *"),
        args=[_unsnooze_comms, db], id="unsnooze_comms",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 */4 * * *"),
        args=[_retry_failed_extractions, db], id="retry_failed_extractions",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 22 * * *"),
        args=[_expire_stale_drafts, db], id="expire_stale_drafts",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 3 * * 0"),
        args=[_synthesize_voice_profiles, db], id="synthesize_voice_profiles",
    )

    scheduler.start()
    log.info(f"Scheduler started with {len(scheduler.get_jobs())} jobs")
    return scheduler


async def _safe_job(fn, db):
    """Async wrapper for error isolation — prevents one failing job from crashing the scheduler."""
    try:
        await fn(db)
    except Exception as e:
        log.error(f"Scheduler job {fn.__name__} failed: {e}", exc_info=True)


# ─── Job Implementations ───

async def _morning_digest(db):
    """Build and log morning digest (7:15 AM ET). Delivery via adapters when wired."""
    from pib.proactive import build_morning_digest_data
    log.info("Running morning digest")
    members = await db.execute_fetchall(
        "SELECT id FROM common_members WHERE active = 1 AND role = 'parent'"
    )
    for member in members or []:
        data = await build_morning_digest_data(db, member["id"])
        log.info(f"Morning digest for {member['id']}: {len(data)} sections")


async def _proactive_trigger_scan(db):
    """Scan for proactive trigger conditions every 30 minutes."""
    from pib.proactive import can_send_proactive, scan_triggers
    log.info("Scanning proactive triggers")

    members = await db.execute_fetchall(
        "SELECT id FROM common_members WHERE active = 1 AND role = 'parent'"
    )
    for member in members or []:
        member_id = member["id"]
        ok, reason = await can_send_proactive(db, member_id)
        if not ok:
            log.debug(f"Proactive blocked for {member_id}: {reason}")
            continue
        fired = await scan_triggers(db, member_id)
        for trigger in fired:
            log.info(f"Trigger fired: {trigger['trigger']} for {member_id}")
            # Record the trigger firing for cooldown tracking
            await db.execute(
                "INSERT INTO mem_cos_activity (action_type, actor, description, created_at) "
                "VALUES ('proactive_message', 'proactive', ?, datetime('now'))",
                [f"trigger:{trigger['trigger']} for {member_id}"],
            )
        if fired:
            await db.commit()


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

        # Advance next_due based on frequency column
        frequency = r.get("frequency", "")
        freq_upper = frequency.upper()
        if freq_upper == "DAILY":
            from datetime import timedelta
            next_due = today + timedelta(days=1)
        elif freq_upper == "WEEKLY":
            from datetime import timedelta
            next_due = today + timedelta(weeks=1)
        elif freq_upper == "MONTHLY":
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
        for task in overdue:
            await db.execute(
                "INSERT INTO mem_cos_activity (action_type, actor, description, created_at) "
                "VALUES ('escalation', 'scheduler', ?, datetime('now'))",
                [f"Overdue: {task['title']} (due {task['due_date']}) assigned to {task['assignee']}"],
            )
        await db.commit()


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


async def _calendar_full_sync(db):
    """Full calendar resync at 2 AM."""
    log.info("Calendar full sync — awaiting Google Calendar adapter")


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
        custody_json = json.dumps({"charlie": parent})
        member_states_json = json.dumps({})
        await db.execute(
            "INSERT INTO cal_daily_states (state_date, version, custody_states, member_states, complexity_score, computed_at) "
            "VALUES (?, 1, ?, ?, 0.0, datetime('now')) "
            "ON CONFLICT(state_date, version) DO UPDATE SET "
            "custody_states = excluded.custody_states, computed_at = excluded.computed_at",
            [today.isoformat(), custody_json, member_states_json],
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
    """Hourly SQLite backup verification."""
    from pib.backup import backup_verify
    log.info("Running SQLite backup verification")
    result = await backup_verify()
    if not result.get("ok"):
        log.warning(f"Backup verification issue: {result}")
    return result


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
