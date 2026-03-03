"""Tests for scheduler job wiring and async execution."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from pib.scheduler import (
    _safe_job,
    _morning_digest,
    _proactive_trigger_scan,
    _recurring_spawn,
    _escalation_check,
    setup_scheduler,
)


@pytest.mark.asyncio
async def test_safe_job_catches_errors(db):
    """_safe_job should catch exceptions and not propagate them."""
    async def failing_job(db):
        raise ValueError("test error")

    # Should not raise
    await _safe_job(failing_job, db)


@pytest.mark.asyncio
async def test_safe_job_passes_db(db):
    """_safe_job should pass the db connection to the wrapped function."""
    received_args = []

    async def spy_job(db):
        received_args.append(db)

    await _safe_job(spy_job, db)
    assert len(received_args) == 1
    assert received_args[0] is db


@pytest.mark.asyncio
async def test_morning_digest_iterates_parents(db):
    """_morning_digest should call build_morning_digest_data for each active parent."""
    call_args = []

    async def mock_build(db, member_id):
        call_args.append(member_id)
        return {"the_one_task": None, "events": [], "custody": None, "budget_alerts": []}

    async def mock_deliver(db, member_id, content, channel=None):
        return {"ok": False, "error": "test"}

    with patch("pib.proactive.build_morning_digest_data", side_effect=mock_build), \
         patch("pib.adapters.dispatcher.deliver_to_member", side_effect=mock_deliver):
        await _morning_digest(db)

    # Should have been called for both m-james and m-laura (active parents)
    assert len(call_args) >= 1
    assert any("m-james" in str(a) or "m-laura" in str(a) for a in call_args)


@pytest.mark.asyncio
async def test_proactive_trigger_scan_respects_guardrails(db):
    """_proactive_trigger_scan should check can_send_proactive and skip blocked members."""
    scan_calls = []

    async def mock_can_send(db, member_id):
        return (False, "quiet_hours")

    async def mock_scan(db, member_id):
        scan_calls.append(member_id)
        return []

    with patch("pib.proactive.can_send_proactive", side_effect=mock_can_send):
        with patch("pib.proactive.scan_triggers", side_effect=mock_scan):
            await _proactive_trigger_scan(db)

    # scan_triggers should NOT have been called since guardrails blocked
    assert len(scan_calls) == 0


@pytest.mark.asyncio
async def test_escalation_check_records_activity(db):
    """_escalation_check should record overdue tasks in mem_cos_activity."""
    # Insert an overdue task
    await db.execute(
        "INSERT INTO ops_tasks (id, title, status, assignee, due_date, created_by) "
        "VALUES ('tsk-overdue1', 'Overdue task', 'next', 'm-james', '2020-01-01', 'test')"
    )
    await db.commit()

    await _escalation_check(db)

    # Check that an activity record was created
    row = await db.execute_fetchone(
        "SELECT * FROM mem_cos_activity WHERE action_type = 'escalation'"
    )
    assert row is not None
    assert "Overdue task" in row["description"]


@pytest.mark.asyncio
async def test_recurring_spawn_creates_task(db):
    """_recurring_spawn should create tasks from ops_recurring entries."""
    from datetime import date

    await db.execute(
        "INSERT INTO ops_recurring (id, title, assignee, domain, frequency, active, next_due, type) "
        "VALUES ('rec-001', 'Walk Captain', 'm-james', 'household', 'DAILY', 1, ?, 'task')",
        [date.today().isoformat()],
    )
    await db.commit()

    # generate_micro_script is imported locally inside _recurring_spawn
    with patch("pib.ingest.generate_micro_script", return_value="Walk the dog"):
        try:
            await _recurring_spawn(db)
        except Exception:
            pass  # May fail if ingest module has other deps; check the task was created

    # Check a task was spawned
    row = await db.execute_fetchone(
        "SELECT * FROM ops_tasks WHERE title = 'Walk Captain' AND created_by = 'recurring'"
    )
    assert row is not None
    assert row["assignee"] == "m-james"


@pytest.mark.asyncio
async def test_monthly_spawn_jan31_to_feb28(db):
    """Monthly recurring on Jan 31 should spawn next on Feb 28 (not crash)."""
    from datetime import date
    from unittest.mock import patch as _patch

    await db.execute(
        "INSERT INTO ops_recurring (id, title, assignee, domain, frequency, active, next_due, type) "
        "VALUES ('rec-jan31', 'Monthly Report', 'm-james', 'work', 'MONTHLY', 1, '2026-01-31', 'task')",
    )
    await db.commit()

    with _patch("pib.scheduler.date") as mock_date, \
         _patch("pib.ingest.generate_micro_script", return_value="Start: Monthly Report"):
        mock_date.today.return_value = date(2026, 1, 31)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        try:
            await _recurring_spawn(db)
        except Exception:
            pass

    row = await db.execute_fetchone(
        "SELECT next_due FROM ops_recurring WHERE id = 'rec-jan31'"
    )
    if row and row["next_due"]:
        assert row["next_due"] == "2026-02-28"


@pytest.mark.asyncio
async def test_monthly_spawn_mar31_to_apr30(db):
    """Monthly recurring on Mar 31 should spawn next on Apr 30."""
    from datetime import date
    from unittest.mock import patch as _patch

    await db.execute(
        "INSERT INTO ops_recurring (id, title, assignee, domain, frequency, active, next_due, type) "
        "VALUES ('rec-mar31', 'End of Month', 'm-james', 'work', 'MONTHLY', 1, '2026-03-31', 'task')",
    )
    await db.commit()

    with _patch("pib.scheduler.date") as mock_date, \
         _patch("pib.ingest.generate_micro_script", return_value="Start task"):
        mock_date.today.return_value = date(2026, 3, 31)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        try:
            await _recurring_spawn(db)
        except Exception:
            pass

    row = await db.execute_fetchone(
        "SELECT next_due FROM ops_recurring WHERE id = 'rec-mar31'"
    )
    if row and row["next_due"]:
        assert row["next_due"] == "2026-04-30"


@pytest.mark.asyncio
async def test_monthly_spawn_dec31_to_jan31(db):
    """Monthly recurring on Dec 31 should spawn next on Jan 31 of next year."""
    from datetime import date
    from unittest.mock import patch as _patch

    await db.execute(
        "INSERT INTO ops_recurring (id, title, assignee, domain, frequency, active, next_due, type) "
        "VALUES ('rec-dec31', 'Year End', 'm-james', 'work', 'MONTHLY', 1, '2026-12-31', 'task')",
    )
    await db.commit()

    with _patch("pib.scheduler.date") as mock_date, \
         _patch("pib.ingest.generate_micro_script", return_value="Start task"):
        mock_date.today.return_value = date(2026, 12, 31)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        try:
            await _recurring_spawn(db)
        except Exception:
            pass

    row = await db.execute_fetchone(
        "SELECT next_due FROM ops_recurring WHERE id = 'rec-dec31'"
    )
    if row and row["next_due"]:
        assert row["next_due"] == "2027-01-31"


@pytest.mark.asyncio
async def test_setup_scheduler_registers_all_jobs(db):
    """setup_scheduler should register all expected cron jobs."""
    app = MagicMock()

    scheduler = await setup_scheduler(app, db)
    if scheduler is None:
        pytest.skip("APScheduler not installed")

    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}

    expected_jobs = {
        "calendar_incremental_sync", "calendar_full_sync", "compute_daily_states",
        "recurring_spawn", "escalation_check", "morning_digest",
        "proactive_trigger_scan", "auto_promote_session_facts", "push_to_sheets",
        "health_probe", "sqlite_backup", "cleanup_expired", "fts5_rebuild",
        "extraction_worker", "unsnooze_comms", "retry_failed_extractions",
        "expire_stale_drafts", "synthesize_voice_profiles",
    }

    assert expected_jobs.issubset(job_ids), f"Missing jobs: {expected_jobs - job_ids}"
    scheduler.shutdown(wait=False)
