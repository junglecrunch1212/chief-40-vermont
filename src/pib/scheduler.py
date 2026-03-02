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

    # ─── Sensor Bus ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("*/5 * * * *"),
        args=[_sensor_bus_poll, db], id="sensor_bus_poll",
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

    # ─── Capture Domain ───
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("*/30 7-23 * * *"),
        args=[_capture_deep_organizer, db], id="capture_deep_organizer",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 3 * * *"),
        args=[_capture_stale_cleanup, db], id="capture_stale_cleanup",
    )
    scheduler.add_job(
        _safe_job, CronTrigger.from_crontab("0 2 * * 0"),
        args=[_capture_fts5_rebuild, db], id="capture_fts5_rebuild",
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
    """Compute daily calendar states at 5:30 AM.

    Merges four data streams:
      1. Calendar events (from cal_classified_events)
      2. Custody computation
      3. Sensor readings (via enrichment layer)
      4. Task/budget context
    """
    from datetime import date
    from pib.custody import who_has_child
    from pib.engine import compute_complexity_score
    import json

    log.info("Computing daily states")
    today = date.today()
    today_str = today.isoformat()

    # ── 1. Custody ──
    custody_states = {}
    config_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    if config_row:
        parent = who_has_child(today, dict(config_row))
        custody_states = {"charlie": parent}

    # ── 2. Calendar events for today ──
    events = await db.execute_fetchall(
        "SELECT * FROM cal_classified_events WHERE event_date = ? ORDER BY start_time",
        [today_str],
    )
    events = [dict(e) for e in events] if events else []

    # ── 3. Member states (initialize) ──
    members = await db.execute_fetchall(
        "SELECT id FROM common_members WHERE active = 1"
    )
    member_states = {}
    for m in members or []:
        member_states[m["id"]] = {
            "events": [e for e in events if m["id"] in (e.get("for_member_ids") or "")],
        }

    # ── 4. Overdue tasks ──
    overdue_row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM ops_tasks WHERE due_date < ? AND status NOT IN ('done','dismissed','deferred')",
        [today_str],
    )
    overdue_count = overdue_row["c"] if overdue_row else 0

    # ── 5. Conflicts ──
    conflict_row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM cal_conflicts WHERE status = 'unresolved' AND conflict_date = ?",
        [today_str],
    )
    conflict_count = conflict_row["c"] if conflict_row else 0

    # ── 6. Build state dict ──
    state = {
        "custody_states": custody_states,
        "member_states": member_states,
        "events": events,
        "overdue_tasks": overdue_count,
        "unresolved_conflicts": conflict_count,
        "transportation": {},
        "coverage_status": {},
        "activity_schedule": {},
        "complexity_score": 0.0,
        "task_load": {},
        "budget_snapshot": {},
    }

    # ── 7. Life phase ──
    phase_row = await db.execute_fetchone(
        "SELECT name FROM common_life_phases WHERE status = 'active' LIMIT 1"
    )
    state["life_phase"] = phase_row["name"] if phase_row else None

    # ── 8. Sensor enrichment (graceful — no-op if no sensors active) ──
    try:
        from pib.sensors.enrichment import enrich_daily_state_with_sensors
        await enrich_daily_state_with_sensors(db, state)
    except Exception as e:
        log.warning(f"Sensor enrichment failed (non-fatal): {e}")

    # ── 8b. Capture enrichment (graceful — no-op if no cap tables) ──
    try:
        from pib.capture import get_capture_stats
        for m in members or []:
            stats = await get_capture_stats(db, m["id"])
            if m["id"] in member_states:
                member_states[m["id"]]["capture_stats"] = stats
    except Exception:
        pass  # Capture tables may not exist yet

    # ── 9. Complexity score ──
    state["complexity_score"] = compute_complexity_score(state)

    # ── 10. Store ──
    custody_json = json.dumps(state["custody_states"])
    member_states_json = json.dumps(state["member_states"])
    transportation_json = json.dumps(state.get("transportation", {}))
    coverage_json = json.dumps(state.get("coverage_status", {}))
    activity_json = json.dumps(state.get("activity_schedule", {}))
    task_load_json = json.dumps(state.get("task_load", {}))
    budget_json = json.dumps(state.get("budget_snapshot", {}))

    await db.execute(
        """INSERT INTO cal_daily_states
           (state_date, version, custody_states, member_states,
            transportation, coverage_status, activity_schedule,
            complexity_score, task_load, budget_snapshot, life_phase, computed_at)
           VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(state_date, version) DO UPDATE SET
             custody_states = excluded.custody_states,
             member_states = excluded.member_states,
             transportation = excluded.transportation,
             coverage_status = excluded.coverage_status,
             activity_schedule = excluded.activity_schedule,
             complexity_score = excluded.complexity_score,
             task_load = excluded.task_load,
             budget_snapshot = excluded.budget_snapshot,
             life_phase = excluded.life_phase,
             computed_at = excluded.computed_at""",
        [
            today_str, custody_json, member_states_json,
            transportation_json, coverage_json, activity_json,
            state["complexity_score"], task_load_json, budget_json,
            state.get("life_phase"),
        ],
    )
    await db.commit()
    log.info(
        f"Daily state computed: custody={custody_states}, "
        f"complexity={state['complexity_score']:.1f}, "
        f"sensors={'enriched' if 'weather' in state else 'none'}"
    )


async def _sensor_bus_poll(db):
    """Poll all enabled sensors that are due for a reading."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = await db.execute_fetchall(
        """SELECT sensor_id FROM pib_sensor_config
           WHERE enabled = 1 AND status IN ('healthy', 'degraded')
             AND poll_interval_minutes > 0
             AND (next_poll_at IS NULL OR next_poll_at <= ?)""",
        [now],
    )
    if not rows:
        return

    # Lazy import to avoid circular dependency
    from pib.sensors.bus import SensorBus

    # Get or create the bus instance from app state if available,
    # otherwise create a temporary one for this poll cycle.
    bus = getattr(db, "_sensor_bus", None)
    if bus is None:
        bus = SensorBus(db)
        await bus.start()

    for row in rows:
        await bus.poll_sensor(row["sensor_id"])


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


# ─── Capture Domain Jobs ───


async def _capture_deep_organizer(db):
    """Run deep organizer on triaged captures every 30 min (7 AM - 11 PM)."""
    try:
        from pib.capture_organizer import organize_batch
        count = await organize_batch(db)
        if count > 0:
            log.info(f"Deep organizer processed {count} captures")
    except Exception as e:
        log.debug(f"Capture deep organizer skipped: {e}")


async def _capture_stale_cleanup(db):
    """Auto-archive inbox captures > 30 days (3 AM daily)."""
    try:
        cursor = await db.execute(
            "UPDATE cap_captures SET archived = 1, archived_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
            "WHERE notebook = 'inbox' AND archived = 0 "
            "AND created_at < datetime('now', '-30 days')"
        )
        await db.commit()
        if cursor.rowcount > 0:
            log.info(f"Auto-archived {cursor.rowcount} stale inbox captures")
    except Exception as e:
        log.debug(f"Capture stale cleanup skipped: {e}")


async def _capture_fts5_rebuild(db):
    """Weekly rebuild of capture FTS5 index (Sunday 2 AM)."""
    try:
        await db.execute("INSERT INTO cap_captures_fts(cap_captures_fts) VALUES('rebuild')")
        await db.commit()
        log.info("Capture FTS5 index rebuilt")
    except Exception as e:
        log.debug(f"Capture FTS5 rebuild skipped: {e}")
