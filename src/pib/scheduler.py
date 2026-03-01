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
        lambda: log.info("calendar_incremental_sync: placeholder"),
        CronTrigger.from_crontab("*/15 * * * *"),
        id="calendar_incremental_sync",
    )
    scheduler.add_job(
        lambda: log.info("calendar_full_sync: placeholder"),
        CronTrigger.from_crontab("0 2 * * *"),
        id="calendar_full_sync",
    )
    scheduler.add_job(
        lambda: log.info("compute_daily_states: placeholder"),
        CronTrigger.from_crontab("30 5 * * *"),
        id="compute_daily_states",
    )

    # ─── Tasks ───
    scheduler.add_job(
        lambda: log.info("recurring_spawn: placeholder"),
        CronTrigger.from_crontab("0 6 * * *"),
        id="recurring_spawn",
    )
    scheduler.add_job(
        lambda: log.info("escalation_check: placeholder"),
        CronTrigger.from_crontab("0 17 * * *"),
        id="escalation_check",
    )

    # ─── Proactive ───
    scheduler.add_job(
        lambda: log.info("morning_digest: placeholder"),
        CronTrigger.from_crontab("0 6 * * *"),
        id="morning_digest",
    )
    scheduler.add_job(
        lambda: log.info("proactive_trigger_scan: placeholder"),
        CronTrigger.from_crontab("*/30 7-22 * * *"),
        id="proactive_trigger_scan",
    )

    # ─── Memory ───
    scheduler.add_job(
        lambda: log.info("auto_promote_session_facts: placeholder"),
        CronTrigger.from_crontab("0 */6 * * *"),
        id="auto_promote_session_facts",
    )

    # ─── Sheets ───
    scheduler.add_job(
        lambda: log.info("push_to_sheets: placeholder"),
        CronTrigger.from_crontab("*/15 * * * *"),
        id="push_to_sheets",
    )

    # ─── System ───
    scheduler.add_job(
        lambda: log.info("health_probe: placeholder"),
        CronTrigger.from_crontab("*/30 * * * *"),
        id="health_probe",
    )
    scheduler.add_job(
        lambda: log.info("sqlite_backup: placeholder"),
        CronTrigger.from_crontab("0 * * * *"),
        id="sqlite_backup",
    )
    scheduler.add_job(
        lambda: log.info("cleanup_expired: placeholder"),
        CronTrigger.from_crontab("0 3 * * *"),
        id="cleanup_expired",
    )
    scheduler.add_job(
        lambda: log.info("fts5_rebuild: placeholder"),
        CronTrigger.from_crontab("0 2 * * 0"),
        id="fts5_rebuild",
    )

    scheduler.start()
    log.info(f"Scheduler started with {len(scheduler.get_jobs())} jobs")
    return scheduler
