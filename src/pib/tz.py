"""Timezone constants — single source of truth for household time."""

from datetime import datetime
from zoneinfo import ZoneInfo

HOUSEHOLD_TZ = ZoneInfo("America/New_York")  # Atlanta


def now_et() -> datetime:
    """Current time in household timezone (America/New_York)."""
    return datetime.now(HOUSEHOLD_TZ)
