"""Proactive engine: triggers, guardrails, morning digest."""

import json
import logging
from datetime import datetime, time

log = logging.getLogger(__name__)

# ─── Guardrails ───

GUARDRAILS = {
    "max_proactive_per_day": 5,
    "max_proactive_per_hour": 2,
    "quiet_hours_start": time(22, 0),
    "quiet_hours_end": time(7, 0),
}


async def can_send_proactive(db, member_id: str, now: datetime | None = None) -> tuple[bool, str]:
    """Check all guardrails before sending a proactive message."""
    now = now or datetime.now()

    # Quiet hours
    if GUARDRAILS["quiet_hours_start"] <= now.time() or now.time() < GUARDRAILS["quiet_hours_end"]:
        return False, "quiet_hours"

    # Focus mode
    energy = await db.execute_fetchone(
        "SELECT focus_mode FROM pib_energy_states WHERE member_id = ? AND state_date = date('now')",
        [member_id],
    )
    if energy and energy["focus_mode"]:
        return False, "focus_mode"

    # In-meeting check
    cal = await db.execute_fetchone(
        "SELECT 1 FROM cal_classified_events "
        "WHERE event_date = date('now') AND scheduling_impact = 'HARD_BLOCK' "
        "AND start_time <= time('now') AND end_time >= time('now')",
    )
    if cal:
        return False, "in_meeting"

    # Daily limit
    daily_count = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM mem_cos_activity "
        "WHERE action_type = 'proactive_message' AND actor = 'proactive' "
        "AND created_at >= datetime('now', 'start of day')",
    )
    if daily_count and daily_count["c"] >= GUARDRAILS["max_proactive_per_day"]:
        return False, "daily_limit"

    # Hourly limit
    hourly_count = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM mem_cos_activity "
        "WHERE action_type = 'proactive_message' AND actor = 'proactive' "
        "AND created_at >= datetime('now', '-1 hour')",
    )
    if hourly_count and hourly_count["c"] >= GUARDRAILS["max_proactive_per_hour"]:
        return False, "hourly_limit"

    return True, "ok"


# ─── Trigger Definitions ───

PROACTIVE_TRIGGERS = [
    {
        "name": "critical_conflict_48h",
        "priority": 1,
        "cooldown_minutes": 120,
        "query": (
            "SELECT * FROM cal_conflicts WHERE severity IN ('critical','high') "
            "AND status='unresolved' AND conflict_date <= date('now','+2 days')"
        ),
    },
    {
        "name": "morning_digest",
        "priority": 2,
        "cooldown_minutes": 1440,
        "hour": 6,
    },
    {
        "name": "overdue_nudge",
        "priority": 3,
        "cooldown_minutes": 480,
        "query": (
            "SELECT * FROM ops_tasks WHERE due_date < date('now') "
            "AND status NOT IN ('done','dismissed','deferred') LIMIT 1"
        ),
    },
    {
        "name": "paralysis_detection",
        "priority": 4,
        "cooldown_minutes": 180,
        "description": "2h silence during peak hours with no calendar block",
    },
    {
        "name": "post_meeting_capture",
        "priority": 5,
        "cooldown_minutes": 30,
        "description": "Calendar event with 2+ attendees ended within last 15 minutes",
    },
    {
        "name": "budget_alert",
        "priority": 6,
        "cooldown_minutes": 1440,
        "query": (
            "SELECT category, pct_used FROM fin_budget_snapshot WHERE over_threshold = 1"
        ),
    },
    # ─── Comms Domain Triggers ───
    {
        "name": "comm_batch_morning",
        "priority": 4,
        "cooldown_minutes": 1440,
        "query": (
            "SELECT COUNT(*) as c FROM ops_comms "
            "WHERE batch_window = 'morning' AND batch_date = date('now') "
            "AND visibility = 'normal' AND needs_response = 1"
        ),
        "batch_window": "morning",
    },
    {
        "name": "comm_batch_midday",
        "priority": 5,
        "cooldown_minutes": 1440,
        "query": (
            "SELECT COUNT(*) as c FROM ops_comms "
            "WHERE batch_window = 'midday' AND batch_date = date('now') "
            "AND visibility = 'normal' AND needs_response = 1"
        ),
        "batch_window": "midday",
    },
    {
        "name": "comm_batch_evening",
        "priority": 5,
        "cooldown_minutes": 1440,
        "query": (
            "SELECT COUNT(*) as c FROM ops_comms "
            "WHERE batch_window = 'evening' AND batch_date = date('now') "
            "AND visibility = 'normal' AND needs_response = 1"
        ),
        "batch_window": "evening",
    },
    {
        "name": "comm_urgent_inbound",
        "priority": 2,
        "cooldown_minutes": 60,
        "query": (
            "SELECT * FROM ops_comms "
            "WHERE response_urgency = 'urgent' AND needs_response = 1 "
            "AND visibility = 'normal' "
            "AND created_at >= datetime('now', '-1 hour')"
        ),
    },
    {
        "name": "comm_draft_stale",
        "priority": 6,
        "cooldown_minutes": 480,
        "query": (
            "SELECT * FROM ops_comms "
            "WHERE draft_status = 'pending' "
            "AND created_at <= datetime('now', '-4 hours')"
        ),
    },
    {
        "name": "comm_response_overdue",
        "priority": 5,
        "cooldown_minutes": 1440,
        "query": (
            "SELECT * FROM ops_comms "
            "WHERE needs_response = 1 AND visibility = 'normal' "
            "AND date <= date('now', '-2 days') AND outcome = 'pending'"
        ),
    },
]


async def scan_triggers(db, member_id: str) -> list[dict]:
    """Scan all proactive triggers and return those that fired."""
    fired = []
    now = datetime.now()

    can_send, reason = await can_send_proactive(db, member_id, now)
    if not can_send:
        log.debug(f"Proactive blocked: {reason}")
        return []

    for trigger in PROACTIVE_TRIGGERS:
        # Check cooldown
        last = await db.execute_fetchone(
            "SELECT MAX(created_at) as last_fired FROM mem_cos_activity "
            "WHERE description LIKE ? AND created_at >= datetime('now', ?)",
            [f"%{trigger['name']}%", f"-{trigger['cooldown_minutes']} minutes"],
        )
        if last and last["last_fired"]:
            continue

        # Check hour condition
        if "hour" in trigger and now.hour != trigger["hour"]:
            continue

        # Check batch window time condition (for comms batch triggers)
        if "batch_window" in trigger:
            from pib.comms import get_batch_config
            batch_config = await get_batch_config(db)
            window_name = trigger["batch_window"]
            window_start = batch_config[window_name]["start"]
            window_end = batch_config[window_name]["end"]
            if not (window_start <= now.time() <= window_end):
                continue

        # Check query condition
        if "query" in trigger:
            result = await db.execute_fetchone(trigger["query"])
            if result:
                # For COUNT queries, only fire if count > 0
                if "c" in dict(result) and result["c"] == 0:
                    continue
                fired.append({"trigger": trigger["name"], "data": dict(result)})

    return fired


# ─── Morning Digest ───

async def build_morning_digest_data(db, member_id: str) -> dict:
    """Assemble structured data for the morning digest."""
    from pib.engine import load_snapshot, what_now
    from pib.custody import who_has_child

    today = datetime.now().date()

    # whatNow for top tasks
    snapshot = await load_snapshot(db, member_id)
    wn = what_now(member_id, snapshot)

    # Today's calendar
    events = await db.execute_fetchall(
        "SELECT * FROM cal_classified_events WHERE event_date = ? "
        "AND privacy IN ('full','privileged') ORDER BY start_time",
        [today.isoformat()],
    )

    # Custody
    custody_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    custody_text = None
    if custody_row:
        custody_parent = who_has_child(today, dict(custody_row))
        member_row = await db.execute_fetchone(
            "SELECT display_name FROM common_members WHERE id = ?", [custody_parent]
        )
        if member_row:
            custody_text = f"Charlie with {member_row['display_name']} today"

    # Budget alerts
    budget_alerts = await db.execute_fetchall(
        "SELECT category, pct_used FROM fin_budget_snapshot WHERE over_threshold = 1"
    )

    return {
        "date": today.isoformat(),
        "member_id": member_id,
        "the_one_task": wn.the_one_task,
        "context": wn.context,
        "energy_level": wn.energy_level,
        "events": [dict(e) for e in events] if events else [],
        "custody": custody_text,
        "budget_alerts": [dict(a) for a in budget_alerts] if budget_alerts else [],
        "completions_today": wn.completions_today,
    }
