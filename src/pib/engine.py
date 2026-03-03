"""Core engine: whatNow(), compute_energy_level(), DBSnapshot, WhatNowResult."""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from pib.tz import now_et

log = logging.getLogger(__name__)


@dataclass
class WhatNowResult:
    the_one_task: dict | None
    context: str
    calendar_status: str | None = None
    energy_level: str = "medium"
    one_more_teaser: dict | None = None
    completions_today: int = 0
    velocity_cap: int = 15


@dataclass
class DBSnapshot:
    """Pre-loaded data for whatNow() — avoids repeated DB calls."""
    tasks: list[dict]
    daily_state: dict | None
    energy_state: dict | None
    members: dict  # {member_id: member_dict}
    streaks: dict  # {member_id: streak_dict}
    calendar_events: list[dict] = field(default_factory=list)
    now: datetime = field(default_factory=now_et)


# ─── Task State Machine ───

TRANSITIONS = {
    "inbox": ["next", "in_progress", "waiting_on", "deferred", "dismissed"],
    "next": ["in_progress", "done", "waiting_on", "deferred", "dismissed"],
    "in_progress": ["done", "waiting_on", "deferred"],
    "waiting_on": ["in_progress", "next", "done"],
    "deferred": ["next", "inbox"],
    "done": [],
    "dismissed": [],
}

GUARDS = {
    "done": lambda t, u: True,  # EASY: one tap
    "dismissed": lambda t, u: bool(u.get("notes")) and len(u["notes"]) >= 10,  # HARD: why?
    "deferred": lambda t, u: bool(u.get("scheduled_date")),  # MEDIUM: when instead?
    "waiting_on": lambda t, u: bool(u.get("waiting_on")),  # MEDIUM: who?
}


def can_transition(task: dict, new_status: str, update_data: dict | None = None) -> tuple[bool, str]:
    """Check if a task status transition is allowed."""
    current = task.get("status", "inbox")
    allowed = TRANSITIONS.get(current, [])
    if new_status not in allowed:
        return False, f"Cannot transition from '{current}' to '{new_status}'. Allowed: {allowed}"

    guard = GUARDS.get(new_status)
    if guard and not guard(task, update_data or {}):
        if new_status == "dismissed":
            return False, "Dismissing requires notes (10+ characters explaining why)."
        if new_status == "deferred":
            return False, "Deferring requires a scheduled_date (when instead?)."
        if new_status == "waiting_on":
            return False, "Waiting requires specifying who you're waiting on."
        return False, f"Guard check failed for transition to '{new_status}'."

    return True, "ok"


async def transition_task(db, task_id: str, new_status: str, update_data: dict, actor: str) -> dict:
    """Transition a task to a new status with guard checks."""
    task = await db.execute_fetchone("SELECT * FROM ops_tasks WHERE id = ?", [task_id])
    if not task:
        raise ValueError(f"Task {task_id} not found")

    ok, msg = can_transition(dict(task), new_status, update_data)
    if not ok:
        raise ValueError(msg)

    sets = ["status = ?", "updated_at = datetime('now')"]
    params = [new_status]

    if new_status == "done":
        sets.extend(["completed_at = datetime('now')", "completed_by = ?"])
        params.append(actor)
    if update_data.get("notes"):
        sets.append("notes = ?")
        params.append(update_data["notes"])
    if update_data.get("scheduled_date"):
        sets.append("scheduled_date = ?")
        params.append(update_data["scheduled_date"])
    if update_data.get("waiting_on"):
        sets.extend(["waiting_on = ?", "waiting_since = datetime('now')"])
        params.append(update_data["waiting_on"])

    params.append(task_id)
    await db.execute(f"UPDATE ops_tasks SET {', '.join(sets)} WHERE id = ?", params)
    await db.commit()
    return {"task_id": task_id, "new_status": new_status}


# ─── Energy Level Computation ───

def compute_energy_level(energy_state: dict | None, member: dict, now: datetime | None = None) -> str:
    """Deterministic energy level based on medication timing, sleep, and time of day."""
    if not energy_state:
        return "medium"

    now = now or now_et()
    current_hour = now.hour

    sleep = energy_state.get("sleep_quality", "okay")
    meds = energy_state.get("meds_taken", False)
    meds_at = energy_state.get("meds_taken_at")

    # Rough sleep overrides everything
    if sleep == "rough":
        return "low"

    # Parse medication config
    med_config = json.loads(member.get("medication_config", "{}"))
    if not med_config:
        # No medication tracking — use time-of-day heuristic
        energy_markers = json.loads(member.get("energy_markers", "{}"))
        crash_hours = energy_markers.get("crash_hours", [])
        for window in crash_hours:
            start, end = window.split("-")
            s = int(start.split(":")[0])
            e = int(end.split(":")[0])
            if s <= current_hour < e:
                return "low"
        return "medium" if sleep == "okay" else "high"

    # Medication-based energy
    if not meds:
        # Before meds: low if past typical dose time
        dose_time = med_config.get("typical_dose_time", "07:30")
        dose_hour = int(dose_time.split(":")[0])
        if current_hour >= dose_hour + 1:
            return "low"  # Should have taken meds by now
        return "medium"

    # After meds: compute phase
    if meds_at:
        try:
            meds_dt = datetime.fromisoformat(meds_at)
            minutes_since = (now - meds_dt).total_seconds() / 60
        except (ValueError, TypeError):
            minutes_since = 120

        peak_onset = med_config.get("peak_onset_minutes", 60)
        peak_duration = med_config.get("peak_duration_minutes", 240)
        crash_onset = med_config.get("crash_onset_minutes", 300)

        if minutes_since < peak_onset:
            return "medium"  # Coming up
        elif minutes_since < peak_onset + peak_duration:
            return "high"  # Peak window
        elif minutes_since < crash_onset:
            return "medium"  # Tapering
        else:
            return "crashed"  # Post-crash

    return "medium"


# ─── Complexity Score ───


def compute_complexity_score(state: dict) -> float:
    """Compute daily complexity score from calendar + environmental signals.

    Base scoring (calendar):
      +1.0 per HARD_BLOCK event
      +0.5 per SOFT_BLOCK
      +1.5 per coverage gap
      +2.0 per unresolved conflict
      +0.3 per REQUIRES_TRANSPORT
      +0.5 per custody transition
      +0.2 per overdue task

    Environmental modifiers (sensor-driven):
      +0.5 if severe weather alert active
      +0.3 if school status != "normal"
      +0.2 if any delivery requires someone home during a block
      +0.3 if any member sleep_quality == "poor"
      +0.2 if traffic delay > 15 min
      -0.3 if weather is "perfect" (good outdoor suitability, no alerts)

    Cap at 10.0.
    """
    score = 0.0

    # ── Calendar base scoring ──
    events = state.get("events", [])
    for event in events:
        impact = event.get("scheduling_impact")
        if impact == "HARD_BLOCK":
            score += 1.0
        elif impact == "SOFT_BLOCK":
            score += 0.5
        elif impact == "REQUIRES_TRANSPORT":
            score += 0.3

    score += state.get("unresolved_conflicts", 0) * 2.0
    score += state.get("overdue_tasks", 0) * 0.2

    # Custody transitions (if custody_states mentions a transition today)
    custody = state.get("custody_states", {})
    if custody.get("transition_today"):
        score += 0.5

    # ── Environmental modifiers (from sensor enrichment) ──
    weather = state.get("weather", {})
    if weather:
        alerts = weather.get("alerts", [])
        if alerts:
            score += 0.5
        elif weather.get("outdoor_suitability") == "good" and not alerts:
            score -= 0.3  # Perfect weather reduces complexity

    school = state.get("school_status", {})
    if school.get("status") and school["status"] != "normal":
        score += 0.3

    deliveries = state.get("deliveries", {})
    if deliveries.get("requires_someone_home"):
        score += 0.2

    member_states = state.get("member_states", {})
    for mid, mstate in member_states.items():
        health = mstate.get("health", {})
        if health.get("sleep_quality") == "poor":
            score += 0.3

    return min(max(score, 0.0), 10.0)


# ─── Energy Filter ───

def _energy_filter(energy_level: str) -> list[str] | None:
    """Return allowed effort levels for current energy, or None for no filter."""
    filters = {
        "crashed": ["tiny"],
        "low": ["tiny", "small"],
        "medium": None,  # All efforts allowed
        "high": None,
    }
    return filters.get(energy_level)


# ─── Break Task ───

def _break_task(completions: int) -> dict:
    """Generate a break suggestion when velocity cap is hit."""
    return {
        "id": "break",
        "title": "Take a break",
        "status": "next",
        "micro_script": "Stand up \u2192 walk to kitchen \u2192 glass of water \u2192 10 minutes off screens",
        "energy": "low",
        "effort": "tiny",
        "notes": f"You've done {completions} things today. That's genuinely impressive. Rest.",
    }


# ─── whatNow() — The Core Function ───

def what_now(member_id: str, snapshot: DBSnapshot) -> WhatNowResult:
    """THE function. Deterministic. Same inputs = same output. No randomness.

    Returns the ONE task this person should do next, with full context.
    """
    now = snapshot.now
    current_hour = now.hour
    today = now.date() if isinstance(now, datetime) else now

    member = snapshot.members.get(member_id, {})
    velocity_cap = member.get("velocity_cap", 15)

    # ── Energy state ──
    energy_level = compute_energy_level(snapshot.energy_state, member, now)
    completions = snapshot.energy_state.get("completions_today", 0) if snapshot.energy_state else 0

    # ── Velocity cap ──
    if completions >= velocity_cap:
        return WhatNowResult(
            the_one_task=_break_task(completions),
            context=f"Velocity cap reached ({completions}/{velocity_cap}). Rest.",
            energy_level=energy_level,
            completions_today=completions,
            velocity_cap=velocity_cap,
        )

    # ── Calendar check ──
    calendar_status = None
    for event in snapshot.calendar_events:
        if event.get("scheduling_impact") == "HARD_BLOCK":
            event_start = event.get("start_time") or ""
            event_end = event.get("end_time") or ""
            try:
                if not event_start or not event_end:
                    continue
                s = datetime.fromisoformat(event_start) if "T" in event_start else datetime.strptime(event_start, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
                e = datetime.fromisoformat(event_end) if "T" in event_end else datetime.strptime(event_end, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
                if s <= now.replace(tzinfo=None) <= e:
                    calendar_status = f"In: {event.get('title', 'event')} until {event_end}"
                    break
            except (ValueError, TypeError):
                pass

    # ── Filter tasks for this member ──
    active_statuses = {"inbox", "next", "in_progress", "waiting_on"}
    member_tasks = [
        t for t in snapshot.tasks
        if t.get("assignee") == member_id and t.get("status") in active_statuses
    ]

    # ── Energy filter ──
    allowed_efforts = _energy_filter(energy_level)
    if allowed_efforts:
        energy_filtered = [t for t in member_tasks if t.get("effort") in allowed_efforts]
        if energy_filtered:
            member_tasks = energy_filtered

    # ── Scoring + Selection (deterministic, no randomness) ──
    def task_score(t: dict) -> tuple:
        """Lower tuple = higher priority."""
        status_order = {"in_progress": 0, "next": 1, "inbox": 2, "waiting_on": 3}
        effort_order = {"tiny": 0, "small": 1, "medium": 2, "large": 3}

        # Overdue tasks first
        due = t.get("due_date")
        is_overdue = 0
        days_until_due = 999
        if due:
            try:
                due_date = date.fromisoformat(due)
                days_until_due = (due_date - today).days
                is_overdue = 1 if days_until_due < 0 else 0
            except ValueError:
                pass

        return (
            -is_overdue,  # Overdue first (negative = earlier)
            days_until_due,  # Sooner due dates next
            status_order.get(t.get("status", "inbox"), 5),
            effort_order.get(t.get("effort") or "unknown", 2),
            t.get("created_at", ""),
        )

    member_tasks.sort(key=task_score)

    the_one_task = member_tasks[0] if member_tasks else None
    one_more = member_tasks[1] if len(member_tasks) > 1 else None

    # ── Context string ──
    context_parts = []
    if calendar_status:
        context_parts.append(calendar_status)
    context_parts.append(f"{completions}/{velocity_cap} done today")
    context_parts.append(f"Energy: {energy_level}")

    streak_data = snapshot.streaks.get(member_id, {})
    if streak_data.get("current_streak", 0) > 0:
        context_parts.append(f"Streak: {streak_data['current_streak']} days")

    return WhatNowResult(
        the_one_task=the_one_task,
        context=" \u00b7 ".join(context_parts),
        calendar_status=calendar_status,
        energy_level=energy_level,
        one_more_teaser=one_more,
        completions_today=completions,
        velocity_cap=velocity_cap,
    )


# ─── Snapshot Loader ───

async def load_snapshot(db, member_id: str) -> DBSnapshot:
    """Load all data needed for whatNow() in one batch."""
    today = date.today()

    # Tasks
    tasks_rows = await db.execute_fetchall(
        "SELECT * FROM ops_tasks WHERE assignee = ? AND status NOT IN ('done', 'dismissed')",
        [member_id],
    )
    tasks = [dict(r) for r in tasks_rows] if tasks_rows else []

    # Energy state
    energy_row = await db.execute_fetchone(
        "SELECT * FROM pib_energy_states WHERE member_id = ? AND state_date = ?",
        [member_id, today.isoformat()],
    )
    energy_state = dict(energy_row) if energy_row else None

    # Calendar events for today
    cal_rows = await db.execute_fetchall(
        "SELECT * FROM cal_classified_events WHERE event_date = ? ORDER BY start_time",
        [today.isoformat()],
    )
    calendar_events = [dict(r) for r in cal_rows] if cal_rows else []

    # Members
    member_rows = await db.execute_fetchall("SELECT * FROM common_members WHERE active = 1")
    members = {r["id"]: dict(r) for r in member_rows} if member_rows else {}

    # Streaks
    streak_rows = await db.execute_fetchall(
        "SELECT * FROM ops_streaks WHERE streak_type = 'daily_completion'"
    )
    streaks = {r["member_id"]: dict(r) for r in streak_rows} if streak_rows else {}

    # Daily state
    daily_row = await db.execute_fetchone(
        "SELECT * FROM cal_daily_states WHERE state_date = ? ORDER BY version DESC LIMIT 1",
        [today.isoformat()],
    )
    daily_state = dict(daily_row) if daily_row else None

    return DBSnapshot(
        tasks=tasks,
        daily_state=daily_state,
        energy_state=energy_state,
        members=members,
        streaks=streaks,
        calendar_events=calendar_events,
    )
