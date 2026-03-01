"""Custody date math — DST-aware, deterministic, no LLM."""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HOUSEHOLD_TZ = ZoneInfo("America/New_York")  # Atlanta


def who_has_child(query_date: date, config: dict) -> str:
    """Deterministic custody state. No LLM. Returns parent member_id.

    CRITICAL: DST transitions can make a 'day' 23 or 25 hours.
    Always compute in calendar days, never hours.
    """
    anchor = date.fromisoformat(config["anchor_date"])
    anchor_parent = config["anchor_parent"]
    other_parent = config["other_parent"]

    # Holiday overrides take priority
    overrides = json.loads(config.get("holiday_overrides", "[]"))
    for override in overrides:
        if override["start"] <= query_date.isoformat() <= override["end"]:
            return override["parent"]

    # Calendar-day difference (immune to DST)
    day_diff = (query_date - anchor).days  # Always integer, DST-safe

    schedule_type = config["schedule_type"]
    if schedule_type == "alternating_weeks":
        week_num = day_diff // 7
        return anchor_parent if week_num % 2 == 0 else other_parent

    elif schedule_type == "alternating_weekends_midweek":
        week_num = day_diff // 7
        day_of_week = query_date.weekday()  # 0=Mon

        is_anchor_weekend = week_num % 2 == 0
        if day_of_week >= 5:  # Weekend
            return anchor_parent if is_anchor_weekend else other_parent

        # Midweek visit check
        if config.get("midweek_visit_enabled"):
            visit_day = config.get("midweek_visit_day")
            if visit_day and query_date.strftime("%A").lower() == visit_day.lower():
                return config.get("midweek_visit_parent", other_parent)

        # Weekday default: anchor parent
        return anchor_parent

    elif schedule_type == "every_other_weekend":
        week_num = day_diff // 7
        day_of_week = query_date.weekday()
        if day_of_week >= 5 and week_num % 2 == 1:
            return other_parent
        return anchor_parent

    elif schedule_type == "primary_with_visitation":
        return anchor_parent  # Override with visitation config

    return anchor_parent  # Default fallback


def get_custody_text(query_date: date, config: dict, members: dict) -> str:
    """Human-readable custody status for the given date."""
    parent_id = who_has_child(query_date, config)
    parent_name = members.get(parent_id, {}).get("display_name", parent_id)
    child_name = members.get(config.get("child_id", ""), {}).get("display_name", "Charlie")
    return f"{child_name} with {parent_name} today"
