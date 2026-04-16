"""Variable-ratio reinforcement, elastic streaks, velocity tracking."""

import logging
import random
from datetime import date, datetime

from pib.tz import now_et

log = logging.getLogger(__name__)

# ─── Variable-Ratio Reward Schedule ───
# 60/25/10/5 — ADHD brains need more frequent dopamine hits
REWARD_SCHEDULE = [
    (0.60, "simple", ["Done \u2713", "\u2713", "Got it \u2713", "Checked off \u2713"]),
    (0.25, "warm", [
        "Nice, that's {streak} in a row today!",
        "Solid. What took you longest was starting \u2014 and you did.",
        "That's {today_count} today. Momentum is real.",
        "Another one bites the dust.",
    ]),
    (0.10, "delight", [
        "Fun fact: the average person takes 23 minutes to refocus after a distraction. You just proved you're not average.",
        "Streak preserved. Your future self thanks you.",
        "That task had been sitting there {days_old} days. It's finally free.",
    ]),
    (0.05, "jackpot", [
        "JACKPOT! You cleared your entire overdue queue. This hasn't happened in {days_since_clear} days!",
        "Holy smokes \u2014 {today_count} tasks in one session. That's a personal record.",
        "You've been on fire this week. {week_count} completed. The household is literally running because of you.",
    ]),
]


CHILD_REWARD_POOL = [
    (0.60, "simple", ["Great job!", "You did it!", "Way to go!", "Awesome!"]),
    (0.25, "warm", [
        "That's {today_count} things done today. You're a superstar!",
        "Keep it up! You're on a roll!",
        "Your parents are so proud of you!",
    ]),
    (0.10, "delight", [
        "You're like a superhero getting things done!",
        "High five! You're doing amazing!",
    ]),
    (0.05, "jackpot", [
        "WOW! You've done so many things today! You're incredible!",
    ]),
]


def select_reward(member_id: str, task: dict, stats: dict, member_age: int | None = None) -> tuple[str, str]:
    """Select reward tier and message. Returns (tier, message)."""
    schedule = CHILD_REWARD_POOL if (member_age is not None and member_age < 13) else REWARD_SCHEDULE
    roll = random.random()
    cumulative = 0.0
    for prob, tier, templates in schedule:
        cumulative += prob
        if roll <= cumulative:
            template = random.choice(templates)
            message = template.format(
                streak=stats.get("current_streak", 0),
                today_count=stats.get("completions_today", 0),
                week_count=stats.get("week_completions", 0),
                days_old=stats.get("days_old", 0),
                days_since_clear=stats.get("days_since_all_clear", "?"),
            )
            return tier, message
    return "simple", "Done \u2713"


# ─── Elastic Streaks ───

async def update_streak(db, member_id: str, completion_date: date) -> dict:
    """Update daily completion streak with grace days and custody pausing."""
    streak = await db.execute_fetchone(
        "SELECT * FROM ops_streaks WHERE member_id = ? AND streak_type = 'daily_completion'",
        [member_id],
    )

    if not streak:
        await db.execute(
            "INSERT INTO ops_streaks (member_id, streak_type, current_streak, best_streak, last_completion_date) "
            "VALUES (?, 'daily_completion', 1, 1, ?)",
            [member_id, completion_date.isoformat()],
        )
        return {"current": 1, "best": 1, "event": "started"}

    last_date = date.fromisoformat(streak["last_completion_date"])
    gap = (completion_date - last_date).days

    if gap <= 0:
        return {"current": streak["current_streak"], "best": streak["best_streak"], "event": "same_day"}
    elif gap == 1:
        # Next day: extend streak
        new_streak = streak["current_streak"] + 1
        new_best = max(new_streak, streak["best_streak"])
        await db.execute(
            "UPDATE ops_streaks SET current_streak=?, best_streak=?, last_completion_date=?, "
            "grace_days_used=0, updated_at=datetime('now') WHERE id=?",
            [new_streak, new_best, completion_date.isoformat(), streak["id"]],
        )
        event = "extended"
        if new_streak == new_best and new_streak > 3:
            event = "new_record"
        return {"current": new_streak, "best": new_best, "event": event}
    elif gap == 2 and streak["grace_days_used"] < streak["max_grace_days"]:
        # Grace period: 1 miss doesn't break
        new_streak = streak["current_streak"] + 1
        await db.execute(
            "UPDATE ops_streaks SET current_streak=?, last_completion_date=?, "
            "grace_days_used=grace_days_used+1, updated_at=datetime('now') WHERE id=?",
            [new_streak, completion_date.isoformat(), streak["id"]],
        )
        return {"current": new_streak, "best": streak["best_streak"], "event": "grace_used"}
    else:
        # Streak broken. Reset.
        await db.execute(
            "UPDATE ops_streaks SET current_streak=1, last_completion_date=?, "
            "grace_days_used=0, updated_at=datetime('now') WHERE id=?",
            [completion_date.isoformat(), streak["id"]],
        )
        event = "reset"
        if streak["current_streak"] >= 3:
            event = "reset_was_long"  # Trigger "welcome back" at 3-day recovery
        return {"current": 1, "best": streak["best_streak"], "event": event}


# ─── Task Completion with Rewards ───

async def get_completion_stats(db, member_id: str, task_id: str | None = None, now: datetime | None = None) -> dict:
    """Get stats needed for reward message interpolation."""
    row = await db.execute_fetchone(
        "SELECT completions_today FROM pib_energy_states "
        "WHERE member_id = ? AND state_date = date('now')",
        [member_id],
    )
    completions_today = row["completions_today"] if row else 0

    week_row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM ops_tasks "
        "WHERE completed_by = ? AND completed_at >= date('now', '-7 days') AND status = 'done'",
        [member_id],
    )
    week_completions = week_row["c"] if week_row else 0

    streak_row = await db.execute_fetchone(
        "SELECT current_streak FROM ops_streaks "
        "WHERE member_id = ? AND streak_type = 'daily_completion'",
        [member_id],
    )
    current_streak = streak_row["current_streak"] if streak_row else 0

    # Compute days_old from task creation date
    days_old = 0
    if task_id:
        task_row = await db.execute_fetchone(
            "SELECT created_at FROM ops_tasks WHERE id = ?", [task_id]
        )
        if task_row and task_row["created_at"]:
            try:
                created = datetime.fromisoformat(task_row["created_at"].replace("Z", "+00:00"))
                days_old = (now_et() - created.astimezone(now_et().tzinfo)).days
            except (ValueError, TypeError):
                days_old = 0

    # Compute days_since_all_clear
    days_since_all_clear = "?"
    clear_row = await db.execute_fetchone(
        "SELECT MAX(state_date) as last_clear FROM pib_energy_states "
        "WHERE member_id = ? AND completions_today > 0 AND state_date < date('now')",
        [member_id],
    )
    if clear_row and clear_row["last_clear"]:
        try:
            last_clear = date.fromisoformat(clear_row["last_clear"])
            days_since_all_clear = (now_et().date() - last_clear).days
        except (ValueError, TypeError):
            pass

    return {
        "completions_today": completions_today,
        "week_completions": week_completions,
        "current_streak": current_streak,
        "days_old": days_old,
        "days_since_all_clear": days_since_all_clear,
    }


async def complete_task_with_reward(db, task_id: str, member_id: str, actor: str, now: datetime | None = None) -> dict:
    """Complete a task, update streak, select reward, log everything."""
    # 1. Complete the task using state machine (not raw SQL bypass)
    from pib.engine import transition_task
    await transition_task(db, task_id, "done", {}, actor)

    # 2. Update velocity
    await db.execute(
        "INSERT INTO pib_energy_states (member_id, state_date, completions_today, last_completion_at) "
        "VALUES (?, date('now'), 1, datetime('now')) "
        "ON CONFLICT(member_id, state_date) DO UPDATE SET "
        "completions_today = completions_today + 1, last_completion_at = datetime('now')",
        [member_id],
    )

    # 3. Update streak
    streak = await update_streak(db, member_id, now_et().date())

    # 4. Select reward (age-aware for child-appropriate messages)
    stats = await get_completion_stats(db, member_id, task_id=task_id)
    task_row = await db.execute_fetchone("SELECT * FROM ops_tasks WHERE id = ?", [task_id])
    task = dict(task_row) if task_row else {}
    member_row = await db.execute_fetchone(
        "SELECT age FROM common_members WHERE id = ?", [member_id]
    )
    member_age = member_row["age"] if member_row and member_row["age"] is not None else None
    tier, message = select_reward(member_id, task, stats, member_age=member_age)

    # 5. Log reward
    await db.execute(
        "INSERT INTO pib_reward_log (member_id, task_id, reward_tier, reward_text) VALUES (?,?,?,?)",
        [member_id, task_id, tier, message],
    )

    await db.commit()
    return {"reward_tier": tier, "reward_message": message, "streak": streak}
