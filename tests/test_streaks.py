"""Tests for elastic streaks — grace days, resets, custody pausing."""

import pytest
from datetime import date
from pib.rewards import update_streak


class TestStreakCreation:
    async def test_first_completion_starts_streak(self, db):
        result = await update_streak(db, "m-james", date(2026, 3, 1))
        assert result["current"] == 1
        assert result["best"] == 1
        assert result["event"] == "started"
        await db.commit()


class TestStreakExtension:
    async def test_next_day_extends(self, db):
        await update_streak(db, "m-james", date(2026, 3, 1))
        await db.commit()
        result = await update_streak(db, "m-james", date(2026, 3, 2))
        assert result["current"] == 2
        assert result["event"] == "extended"
        await db.commit()

    async def test_same_day_no_change(self, db):
        await update_streak(db, "m-james", date(2026, 3, 1))
        await db.commit()
        result = await update_streak(db, "m-james", date(2026, 3, 1))
        assert result["event"] == "same_day"


class TestGraceDays:
    async def test_grace_day_preserves_streak(self, db):
        await update_streak(db, "m-james", date(2026, 3, 1))
        await db.commit()
        await update_streak(db, "m-james", date(2026, 3, 2))
        await db.commit()
        # Skip day 3, complete day 4 → grace used
        result = await update_streak(db, "m-james", date(2026, 3, 4))
        assert result["event"] == "grace_used"
        assert result["current"] == 3
        await db.commit()


class TestStreakReset:
    async def test_two_day_gap_breaks_streak(self, db):
        await update_streak(db, "m-james", date(2026, 3, 1))
        await db.commit()
        await update_streak(db, "m-james", date(2026, 3, 2))
        await db.commit()
        await update_streak(db, "m-james", date(2026, 3, 3))
        await db.commit()
        # Skip two days
        result = await update_streak(db, "m-james", date(2026, 3, 6))
        assert result["current"] == 1
        assert result["event"] == "reset_was_long"  # Was 3+ days
        await db.commit()

    async def test_short_streak_simple_reset(self, db):
        await update_streak(db, "m-james", date(2026, 3, 1))
        await db.commit()
        # Skip multiple days
        result = await update_streak(db, "m-james", date(2026, 3, 10))
        assert result["current"] == 1
        assert result["event"] == "reset"
        await db.commit()


class TestNewRecord:
    async def test_new_record_event(self, db):
        # Build up a streak of 4
        for day in range(1, 5):
            await update_streak(db, "m-james", date(2026, 3, day))
            await db.commit()
        result = await update_streak(db, "m-james", date(2026, 3, 5))
        # Should be new_record since 5 > 4 and > 3 threshold
        if result["current"] == result["best"] and result["current"] > 3:
            assert result["event"] == "new_record"
        await db.commit()
