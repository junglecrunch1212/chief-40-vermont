"""Per-project rate limiting using audit log queries."""

import logging

log = logging.getLogger(__name__)

# ─── Rate Limits ───

RATE_LIMITS = {
    "gmail_send": {"per_hour": 5, "per_day": 20},
    "twilio_sms": {"per_hour": 5, "per_day": 20},
    "twilio_call": {"per_hour": 3, "per_day": 10},
    "web_search": {"per_hour": 20, "per_day": 100},
}


async def check_rate_limit(db, project_id: str, action_type: str) -> bool:
    """Check whether a project action is within rate limits.

    Queries common_audit_log for recent actions tagged with this project.
    Returns True if under limit, False if exceeded.
    """
    limits = RATE_LIMITS.get(action_type)
    if not limits:
        return True  # No limits defined for this action type

    source_pattern = f"project:{action_type}"

    # Check hourly limit
    hourly_row = await db.execute_fetchone(
        """SELECT COUNT(*) as c FROM common_audit_log
           WHERE source = ? AND ts >= datetime('now', '-1 hour')
             AND new_values LIKE ?""",
        [source_pattern, f'%"project_id": "{project_id}"%'],
    )
    hourly_count = hourly_row["c"] if hourly_row else 0

    if hourly_count >= limits["per_hour"]:
        log.warning(
            f"Rate limit hit: {action_type} for {project_id} "
            f"({hourly_count}/{limits['per_hour']} per hour)"
        )
        return False

    # Check daily limit
    daily_row = await db.execute_fetchone(
        """SELECT COUNT(*) as c FROM common_audit_log
           WHERE source = ? AND ts >= datetime('now', '-24 hours')
             AND new_values LIKE ?""",
        [source_pattern, f'%"project_id": "{project_id}"%'],
    )
    daily_count = daily_row["c"] if daily_row else 0

    if daily_count >= limits["per_day"]:
        log.warning(
            f"Rate limit hit: {action_type} for {project_id} "
            f"({daily_count}/{limits['per_day']} per day)"
        )
        return False

    return True
