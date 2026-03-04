"""Proactive engine: triggers, guardrails, morning digest."""

import json
import logging
from datetime import datetime, time

from pib.tz import now_et

log = logging.getLogger(__name__)

# ─── Guardrails ───

GUARDRAILS = {
    "max_proactive_per_day": 5,
    "max_proactive_per_hour": 2,
    "quiet_hours_start": time(22, 0),
    "quiet_hours_end": time(7, 0),
}


def _is_quiet_hours(now_time=None):
    """Check if current time is in quiet hours (spans midnight: 22:00→07:00).

    Returns True during quiet hours when proactive messages should be suppressed.
    The OR condition is correct because quiet hours span midnight:
    - 22:00-23:59 → start <= time is True
    - 00:00-06:59 → time < end is True
    - 07:00-21:59 → both False → not quiet
    """
    if now_time is None:
        now_time = now_et().time()
    start = GUARDRAILS["quiet_hours_start"]
    end = GUARDRAILS["quiet_hours_end"]
    return start <= now_time or now_time < end


async def can_send_proactive(db, member_id: str, now: datetime | None = None) -> tuple[bool, str]:
    """Check all guardrails before sending a proactive message."""
    now = now or now_et()

    # Quiet hours
    if _is_quiet_hours(now.time()):
        return False, "quiet_hours"

    # Focus mode (auto-expire after 2 hours)
    energy = await db.execute_fetchone(
        "SELECT focus_mode, updated_at FROM pib_energy_states WHERE member_id = ? AND state_date = date('now')",
        [member_id],
    )
    if energy and energy["focus_mode"]:
        if energy.get("updated_at"):
            try:
                updated = datetime.fromisoformat(energy["updated_at"].replace("Z", "+00:00"))
                updated_naive = updated.replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None) if now.tzinfo else now
                hours_elapsed = (now_naive - updated_naive).total_seconds() / 3600
                if hours_elapsed > 2:
                    await db.execute(
                        "UPDATE pib_energy_states SET focus_mode = 0, updated_at = datetime('now') "
                        "WHERE member_id = ? AND state_date = date('now')",
                        [member_id],
                    )
                    await db.commit()
                    log.info(f"Auto-expired focus mode for {member_id} after {hours_elapsed:.1f}h")
                else:
                    return False, "focus_mode"
            except (ValueError, TypeError):
                return False, "focus_mode"
        else:
            return False, "focus_mode"

    # In-meeting check
    cal = await db.execute_fetchone(
        "SELECT 1 FROM cal_classified_events "
        "WHERE event_date = date('now') AND scheduling_impact = 'HARD_BLOCK' "
        "AND start_time <= time('now') AND end_time >= time('now')",
    )
    if cal:
        return False, "in_meeting"

    # Daily limit (per-member)
    daily_count = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM mem_cos_activity "
        "WHERE action_type = 'proactive_message' AND actor = 'proactive' "
        "AND description LIKE ? "
        "AND created_at >= datetime('now', 'start of day')",
        [f"%for {member_id}%"],
    )
    if daily_count and daily_count["c"] >= GUARDRAILS["max_proactive_per_day"]:
        return False, "daily_limit"

    # Hourly limit (per-member)
    hourly_count = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM mem_cos_activity "
        "WHERE action_type = 'proactive_message' AND actor = 'proactive' "
        "AND description LIKE ? "
        "AND created_at >= datetime('now', '-1 hour')",
        [f"%for {member_id}%"],
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
        "description": "3+ tasks in next status, none completed in 2+ hours, energy not crashed",
        "query": (
            "SELECT COUNT(*) as c FROM ops_tasks "
            "WHERE status = 'next' AND assignee = (SELECT id FROM common_members WHERE role='parent' LIMIT 1) "
            "AND id NOT IN (SELECT id FROM ops_tasks WHERE status='done' AND completed_at >= datetime('now', '-2 hours'))"
        ),
        "min_count": 3,
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

# ─── Sensor-Driven Triggers ───
# These check pib_sensor_readings and pib_sensor_alerts for environmental conditions.

SENSOR_TRIGGERS = [
    {
        "name": "weather_before_outdoor",
        "priority": 3,
        "cooldown_minutes": 120,
        "description": "30 min before REQUIRES_TRANSPORT or outdoor event, check weather",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-weather' AND reading_type = 'weather.current' "
            "AND expires_at > datetime('now') ORDER BY timestamp DESC LIMIT 1"
        ),
        "calendar_condition": (
            "SELECT 1 FROM cal_classified_events "
            "WHERE event_date = date('now') AND scheduling_impact = 'REQUIRES_TRANSPORT' "
            "AND time(start_time, '-30 minutes') <= time('now') "
            "AND time(start_time) > time('now')"
        ),
    },
    {
        "name": "severe_weather_immediate",
        "priority": 1,
        "cooldown_minutes": 60,
        "description": "Immediately on severe weather alerts",
        "alert_query": (
            "SELECT * FROM pib_sensor_alerts "
            "WHERE sensor_id = 'sensor-weather' AND severity IN ('warning','critical') "
            "AND status = 'active'"
        ),
    },
    {
        "name": "school_status_change",
        "priority": 2,
        "cooldown_minutes": 120,
        "description": "School delay/closing/early dismissal detected",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-school-alerts' AND reading_type = 'logistics.school' "
            "AND expires_at > datetime('now') "
            "AND json_extract(value, '$.status') != 'normal' "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
    {
        "name": "departure_traffic_check",
        "priority": 3,
        "cooldown_minutes": 60,
        "description": "45 min before REQUIRES_TRANSPORT, check traffic",
        "calendar_condition": (
            "SELECT 1 FROM cal_classified_events "
            "WHERE event_date = date('now') AND scheduling_impact = 'REQUIRES_TRANSPORT' "
            "AND time(start_time, '-45 minutes') <= time('now') "
            "AND time(start_time) > time('now')"
        ),
    },
    {
        "name": "sleep_quality_adjustment",
        "priority": 4,
        "cooldown_minutes": 1440,
        "description": "Morning: if sleep was poor/fair, adjust expectations",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-health-sleep' AND reading_type = 'health.sleep.summary' "
            "AND expires_at > datetime('now') "
            "AND json_extract(value, '$.quality') IN ('poor', 'fair') "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
        "hour_range": (6, 10),
    },
    {
        "name": "medication_not_taken",
        "priority": 3,
        "cooldown_minutes": 480,
        "description": "45 min after scheduled med time, if not logged",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-health-meds' AND reading_type = 'health.medication' "
            "AND expires_at > datetime('now') "
            "AND json_extract(value, '$.all_taken') = 0 "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
        "hour_range": (7, 12),
    },
    {
        "name": "device_battery_coverage_risk",
        "priority": 3,
        "cooldown_minutes": 120,
        "description": "Phone < 15% AND transport duty in next 2 hours",
        "sensor_query": (
            "SELECT value, member_id FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-apple-battery' AND reading_type = 'device.battery' "
            "AND expires_at > datetime('now') "
            "AND json_extract(value, '$.reachability_risk') = 1 "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
    {
        "name": "package_delivery_awareness",
        "priority": 5,
        "cooldown_minutes": 240,
        "description": "Package out for delivery",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-packages' AND reading_type = 'logistics.packages' "
            "AND expires_at > datetime('now') "
            "AND json_extract(value, '$.expected_today') != '[]' "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
    {
        "name": "appliance_done",
        "priority": 5,
        "cooldown_minutes": 60,
        "description": "Washer/dryer cycle complete",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-homekit' AND reading_type = 'home.state' "
            "AND expires_at > datetime('now') "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
    {
        "name": "sunset_outdoor_reminder",
        "priority": 4,
        "cooldown_minutes": 1440,
        "description": "45 min before sunset if outdoor activity likely",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-sun' AND reading_type = 'sun.times' "
            "AND expires_at > datetime('now') "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
    {
        "name": "pollen_allergy_morning",
        "priority": 4,
        "cooldown_minutes": 1440,
        "description": "Morning if pollen high + member has allergy config",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-weather' AND reading_type = 'weather.current' "
            "AND expires_at > datetime('now') "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
        "hour_range": (6, 9),
    },
    {
        "name": "uv_outdoor_advisory",
        "priority": 4,
        "cooldown_minutes": 240,
        "description": "Before outdoor event if UV >= 6",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-weather' AND reading_type = 'weather.current' "
            "AND expires_at > datetime('now') "
            "AND CAST(json_extract(value, '$.uv_index') AS INTEGER) >= 6 "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
    {
        "name": "stress_trend_weekly",
        "priority": 6,
        "cooldown_minutes": 10080,
        "description": "Sunday evening if HRV declining 3+ days",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-health-heart' AND reading_type = 'health.heart.summary' "
            "AND expires_at > datetime('now') "
            "AND json_extract(value, '$.hrv_trend') = 'declining' "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
        "day_of_week": 6,
        "hour_range": (17, 21),
    },
    {
        "name": "focus_mode_message_hold",
        "priority": 2,
        "cooldown_minutes": 30,
        "description": "Hold non-urgent messages when member in DND/Driving",
        "sensor_query": (
            "SELECT value, member_id FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-apple-focus' AND reading_type = 'device.focus' "
            "AND expires_at > datetime('now') "
            "AND json_extract(value, '$.active_focus') IN ('do_not_disturb', 'driving') "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
    {
        "name": "rhythm_corroboration",
        "priority": 6,
        "cooldown_minutes": 240,
        "description": "Sensor data confirms or contradicts a rhythm",
        "sensor_query": (
            "SELECT value FROM pib_sensor_readings "
            "WHERE sensor_id = 'sensor-wifi-presence' AND reading_type = 'home.wifi_presence' "
            "AND expires_at > datetime('now') "
            "ORDER BY timestamp DESC LIMIT 1"
        ),
    },
]


async def scan_triggers(db, member_id: str) -> list[dict]:
    """Scan all proactive triggers (core + sensor) and return those that fired."""
    fired = []
    now = now_et()

    can_send, reason = await can_send_proactive(db, member_id, now)
    if not can_send:
        log.debug(f"Proactive blocked: {reason}")
        return []

    # ── Core triggers ──
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
                result_dict = dict(result)
                min_count = trigger.get("min_count", 1)
                # For COUNT queries, check against min_count threshold
                if "c" in result_dict and result_dict["c"] < min_count:
                    continue
                fired.append({"trigger": trigger["name"], "data": result_dict})

    # ── Sensor triggers ──
    fired.extend(await _scan_sensor_triggers(db, member_id, now))

    # ── Capture triggers ──
    fired.extend(await _scan_capture_triggers(db, member_id, now))

    # ── Project triggers ──
    try:
        fired.extend(await _scan_project_triggers(db, member_id, now))
    except Exception as e:
        log.debug(f"Project trigger scan skipped: {e}")

    return fired


async def _scan_sensor_triggers(db, member_id: str, now: datetime) -> list[dict]:
    """Scan sensor-driven triggers. Graceful — if sensor tables don't exist, returns []."""
    fired = []
    try:
        for trigger in SENSOR_TRIGGERS:
            # Check cooldown
            last = await db.execute_fetchone(
                "SELECT MAX(created_at) as last_fired FROM mem_cos_activity "
                "WHERE description LIKE ? AND created_at >= datetime('now', ?)",
                [f"%{trigger['name']}%", f"-{trigger['cooldown_minutes']} minutes"],
            )
            if last and last["last_fired"]:
                continue

            # Check hour_range
            if "hour_range" in trigger:
                start_h, end_h = trigger["hour_range"]
                if not (start_h <= now.hour < end_h):
                    continue

            # Check day_of_week
            if "day_of_week" in trigger and now.weekday() != trigger["day_of_week"]:
                continue

            # Check calendar_condition (if present, must match for trigger to fire)
            if "calendar_condition" in trigger:
                cal_result = await db.execute_fetchone(trigger["calendar_condition"])
                if not cal_result:
                    continue

            # Check alert_query (for alert-based triggers)
            if "alert_query" in trigger:
                alert_result = await db.execute_fetchone(trigger["alert_query"])
                if alert_result:
                    fired.append({"trigger": trigger["name"], "data": dict(alert_result)})
                continue

            # Check sensor_query
            if "sensor_query" in trigger:
                result = await db.execute_fetchone(trigger["sensor_query"])
                if result:
                    data = dict(result)
                    # Parse value JSON if present
                    if "value" in data and isinstance(data["value"], str):
                        try:
                            data["value"] = json.loads(data["value"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    fired.append({"trigger": trigger["name"], "data": data})

    except Exception as e:
        # Sensor tables may not exist yet — graceful degradation
        log.debug(f"Sensor trigger scan skipped: {e}")

    return fired


# ─── Capture Triggers ───

CAPTURE_TRIGGERS = [
    {
        "name": "capture_weekly_review",
        "priority": 5,
        "cooldown_minutes": 10080,  # 7 days
        "day_of_week": 6,  # Sunday
        "hour_range": (17, 21),  # 5-9 PM
        "description": "Weekly review of unorganized captures",
    },
    {
        "name": "capture_resurface",
        "priority": 6,
        "cooldown_minutes": 480,  # 8 hours
        "description": "Surface a relevant organized capture",
    },
    {
        "name": "capture_connection_discovery",
        "priority": 7,
        "cooldown_minutes": 1440,  # 24 hours
        "description": "Cross-user connection discovery on household captures",
    },
    {
        "name": "capture_stale_inbox",
        "priority": 8,
        "cooldown_minutes": 2880,  # 48 hours
        "description": "Nudge about captures sitting in inbox > 3 days",
    },
]


async def _scan_capture_triggers(db, member_id: str, now: datetime) -> list[dict]:
    """Scan capture-related proactive triggers. Graceful — if cap tables don't exist, returns []."""
    fired = []
    try:
        for trigger in CAPTURE_TRIGGERS:
            # Check cooldown
            last = await db.execute_fetchone(
                "SELECT MAX(created_at) as last_fired FROM mem_cos_activity "
                "WHERE description LIKE ? AND created_at >= datetime('now', ?)",
                [f"%{trigger['name']}%", f"-{trigger['cooldown_minutes']} minutes"],
            )
            if last and last["last_fired"]:
                continue

            # Check day_of_week
            if "day_of_week" in trigger and now.weekday() != trigger["day_of_week"]:
                continue

            # Check hour_range
            if "hour_range" in trigger:
                start_h, end_h = trigger["hour_range"]
                if not (start_h <= now.hour < end_h):
                    continue

            # Trigger-specific conditions
            if trigger["name"] == "capture_weekly_review":
                count = await db.execute_fetchone(
                    "SELECT COUNT(*) as c FROM cap_captures "
                    "WHERE member_id = ? AND triage_status IN ('raw','triaged') AND archived = 0",
                    [member_id],
                )
                if count and count["c"] > 0:
                    fired.append({"trigger": trigger["name"], "data": {"count": count["c"]}})

            elif trigger["name"] == "capture_resurface":
                from pib.capture import get_captures_for_resurfacing
                resurfaceable = await get_captures_for_resurfacing(db, member_id, limit=1)
                if resurfaceable:
                    cap = resurfaceable[0]
                    fired.append({"trigger": trigger["name"], "data": {
                        "capture_id": cap["id"],
                        "title": cap.get("title") or cap["raw_text"][:80],
                        "type": cap["capture_type"],
                    }})

            elif trigger["name"] == "capture_connection_discovery":
                # Check for household-visible captures that haven't had connection discovery
                count = await db.execute_fetchone(
                    "SELECT COUNT(*) as c FROM cap_captures "
                    "WHERE member_id = ? AND household_visible = 1 AND triage_status = 'organized' "
                    "AND id NOT IN (SELECT source_capture_id FROM cap_connections WHERE created_by = 'cross_user_discovery')",
                    [member_id],
                )
                if count and count["c"] > 0:
                    fired.append({"trigger": trigger["name"], "data": {"count": count["c"]}})

            elif trigger["name"] == "capture_stale_inbox":
                count = await db.execute_fetchone(
                    "SELECT COUNT(*) as c FROM cap_captures "
                    "WHERE member_id = ? AND notebook = 'inbox' AND archived = 0 "
                    "AND created_at < datetime('now', '-3 days')",
                    [member_id],
                )
                if count and count["c"] > 0:
                    fired.append({"trigger": trigger["name"], "data": {"count": count["c"]}})

    except Exception as e:
        log.debug(f"Capture trigger scan skipped: {e}")

    return fired


# ─── Project Triggers ───

PROJECT_TRIGGERS = [
    {
        "name": "project_stale_check",
        "priority": 4,
        "cooldown_minutes": 1440,  # 24 hours
        "description": "Projects with no step activity > 48h",
    },
    {
        "name": "project_gate_reminder",
        "priority": 5,
        "cooldown_minutes": 720,  # 12 hours
        "description": "Pending gates older than 24 hours",
    },
    {
        "name": "project_progress_update",
        "priority": 3,
        "cooldown_minutes": 1440,  # 24 hours
        "hour": 20,  # 8 PM
        "description": "Daily project progress summary",
    },
]


async def _scan_project_triggers(db, member_id: str, now: datetime) -> list[dict]:
    """Scan project-related proactive triggers. Graceful — if proj tables don't exist, returns []."""
    fired = []
    try:
        for trigger in PROJECT_TRIGGERS:
            # Check cooldown
            last = await db.execute_fetchone(
                "SELECT MAX(created_at) as last_fired FROM mem_cos_activity "
                "WHERE description LIKE ? AND created_at >= datetime('now', ?)",
                [f"%{trigger['name']}%", f"-{trigger['cooldown_minutes']} minutes"],
            )
            if last and last["last_fired"]:
                continue

            # Check hour
            if "hour" in trigger and now.hour != trigger["hour"]:
                continue

            if trigger["name"] == "project_stale_check":
                count = await db.execute_fetchone(
                    """SELECT COUNT(*) as c FROM proj_projects
                       WHERE status = 'active' AND requested_by = ?
                         AND updated_at < datetime('now', '-48 hours')""",
                    [member_id],
                )
                if count and count["c"] > 0:
                    fired.append({"trigger": trigger["name"], "data": {"stale_count": count["c"]}})

            elif trigger["name"] == "project_gate_reminder":
                gates = await db.execute_fetchall(
                    """SELECT g.id, g.title, p.title as project_title
                       FROM proj_gates g
                       JOIN proj_projects p ON g.project_id = p.id
                       WHERE g.status = 'waiting' AND p.requested_by = ?
                         AND g.created_at < datetime('now', '-24 hours')
                       LIMIT 3""",
                    [member_id],
                )
                if gates:
                    gate_list = [dict(g) for g in gates]
                    fired.append({"trigger": trigger["name"], "data": {
                        "count": len(gate_list),
                        "gates": gate_list,
                    }})

            elif trigger["name"] == "project_progress_update":
                active = await db.execute_fetchone(
                    "SELECT COUNT(*) as c FROM proj_projects WHERE status = 'active' AND requested_by = ?",
                    [member_id],
                )
                if active and active["c"] > 0:
                    fired.append({"trigger": trigger["name"], "data": {"active_count": active["c"]}})

    except Exception as e:
        log.debug(f"Project trigger scan skipped: {e}")

    return fired


# ─── Morning Digest ───

async def build_morning_digest_data(db, member_id: str) -> dict:
    """Assemble structured data for the morning digest."""
    from pib.engine import load_snapshot, what_now
    from pib.custody import who_has_child

    today = now_et().date()

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

    # High-priority captures
    high_priority_captures = []
    try:
        from pib.capture import list_captures
        hp = await list_captures(db, member_id, priority="high", limit=3)
        high_priority_captures = [{"id": c["id"], "title": c.get("title") or c["raw_text"][:80],
                                   "type": c["capture_type"]} for c in hp]
    except Exception:
        pass  # Capture tables may not exist yet

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
        "high_priority_captures": high_priority_captures,
    }


# ─── Proactive Dispatch via Outbound Router ───


async def dispatch_proactive_message(
    db, member_id: str, message: str, trigger_type: str
) -> dict | None:
    """Dispatch a proactive message through the outbound router.

    Delegates to comms.dispatch_proactive_message which handles channel
    selection and routing. Guardrails (quiet hours, rate limits, focus mode)
    are already checked by can_send_proactive() before this is called.

    Args:
        db: Database connection
        member_id: Recipient member ID
        message: Message body to send
        trigger_type: The proactive trigger name (for audit trail)

    Returns:
        Route result dict, or None if routing unavailable
    """
    from pib.comms import dispatch_proactive_message as _dispatch
    return await _dispatch(db, member_id, message, trigger_type)
