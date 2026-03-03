"""Tests for per-project rate limiting."""

import json

import pytest

from pib.project.rate_limit import check_rate_limit, RATE_LIMITS


@pytest.mark.asyncio
class TestCheckRateLimit:
    """Tests for check_rate_limit()."""

    async def test_under_limit_returns_true(self, db):
        """No prior actions → under limit → True."""
        result = await check_rate_limit(db, "proj-00100", "gmail_send")
        assert result is True

    async def test_unknown_action_returns_true(self, db):
        """Unknown action type with no defined limits → True."""
        result = await check_rate_limit(db, "proj-00100", "unknown_action")
        assert result is True

    async def test_at_hourly_limit_returns_false(self, db):
        """At hourly limit → False."""
        limit = RATE_LIMITS["gmail_send"]["per_hour"]
        for i in range(limit):
            await db.execute(
                """INSERT INTO common_audit_log
                   (table_name, operation, entity_id, source, new_values, ts)
                   VALUES (?, ?, ?, ?, ?, datetime('now', ?))""",
                [
                    "proj_steps", "UPDATE", f"step-{i:05d}",
                    "project:gmail_send",
                    json.dumps({"project_id": "proj-00100"}),
                    f"-{i} minutes",
                ],
            )
        await db.commit()

        result = await check_rate_limit(db, "proj-00100", "gmail_send")
        assert result is False

    async def test_at_daily_limit_returns_false(self, db):
        """At daily limit → False (even if hourly is OK due to spread)."""
        limit = RATE_LIMITS["web_search"]["per_day"]  # 100
        # Spread entries across 24 hours to stay under hourly (20/hr) but hit daily
        for i in range(limit):
            hours_ago = (i * 24) // limit  # Spread evenly over 24h
            await db.execute(
                """INSERT INTO common_audit_log
                   (table_name, operation, entity_id, source, new_values, ts)
                   VALUES (?, ?, ?, ?, ?, datetime('now', ?))""",
                [
                    "proj_steps", "UPDATE", f"step-{i:05d}",
                    "project:web_search",
                    json.dumps({"project_id": "proj-00100"}),
                    f"-{hours_ago} hours",
                ],
            )
        await db.commit()

        result = await check_rate_limit(db, "proj-00100", "web_search")
        assert result is False

    async def test_different_project_not_counted(self, db):
        """Actions from a different project should not count."""
        limit = RATE_LIMITS["gmail_send"]["per_hour"]
        for i in range(limit):
            await db.execute(
                """INSERT INTO common_audit_log
                   (table_name, operation, entity_id, source, new_values, ts)
                   VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                [
                    "proj_steps", "UPDATE", f"step-{i:05d}",
                    "project:gmail_send",
                    json.dumps({"project_id": "proj-OTHER"}),  # Different project
                ],
            )
        await db.commit()

        result = await check_rate_limit(db, "proj-00100", "gmail_send")
        assert result is True
