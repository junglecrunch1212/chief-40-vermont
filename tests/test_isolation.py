"""Tests for member data isolation across memory, calendar, and settings."""

import json
import pytest
from pib.memory import save_memory_deduped, search_memory


class TestMemorySearchIsolation:
    """Verify search_memory() returns only the requesting member's data."""

    async def test_search_returns_own_members_facts(self, db):
        """James's search should only find James's memories."""
        await save_memory_deduped(db, "James prefers morning workouts", "preferences", "health", "m-james", "user_stated")
        await save_memory_deduped(db, "Laura prefers evening yoga", "preferences", "health", "m-laura", "user_stated")
        await db.commit()

        results = await search_memory(db, "prefers", limit=10, member_id="m-james")
        assert len(results) == 1
        assert "James" in results[0]["content"]

    async def test_search_excludes_other_members_facts(self, db):
        """Laura's search should not return James's private memories."""
        await save_memory_deduped(db, "James has a therapy appointment Tuesdays", "facts", "health", "m-james", "user_stated")
        await db.commit()

        results = await search_memory(db, "therapy appointment", limit=10, member_id="m-laura")
        assert len(results) == 0

    async def test_search_includes_household_shared_facts(self, db):
        """Household-shared facts (member_id=NULL) should be visible to all."""
        await db.execute(
            "INSERT INTO mem_long_term (content, category, domain, member_id, source) "
            "VALUES ('Household wifi password is abc123', 'facts', 'household', NULL, 'user_stated')"
        )
        await db.commit()

        results = await search_memory(db, "wifi password", limit=10, member_id="m-james")
        assert len(results) == 1
        assert "wifi" in results[0]["content"].lower()

    async def test_search_without_member_returns_all(self, db):
        """Backwards-compatible: no member_id returns all memories."""
        await save_memory_deduped(db, "James fact alpha", "facts", "misc", "m-james", "user_stated")
        await save_memory_deduped(db, "Laura fact alpha", "facts", "misc", "m-laura", "user_stated")
        await db.commit()

        results = await search_memory(db, "fact alpha", limit=10)
        assert len(results) == 2


class TestMemoryDedupIsolation:
    """Verify save_memory_deduped() doesn't cross-match between members."""

    async def test_same_fact_different_members_not_reinforced(self, db):
        """Identical facts from different members should NOT be deduplicated."""
        result1 = await save_memory_deduped(
            db, "The dentist office closes at 5pm",
            "facts", "health", "m-james", "user_stated",
        )
        await db.commit()
        assert result1["action"] == "inserted"

        result2 = await save_memory_deduped(
            db, "The dentist office closes at 5pm",
            "facts", "health", "m-laura", "user_stated",
        )
        assert result2["action"] == "inserted"  # NOT reinforced

    async def test_contradiction_doesnt_cross_supersede(self, db):
        """James's negation should not supersede Laura's memory."""
        await save_memory_deduped(
            db, "Laura likes sushi",
            "preferences", "food", "m-laura", "user_stated",
        )
        await db.commit()

        result = await save_memory_deduped(
            db, "James doesn't like sushi",
            "preferences", "food", "m-james", "user_stated",
        )
        # Should be inserted as new (not superseding Laura's fact)
        assert result["action"] == "inserted"

        # Verify Laura's fact is NOT superseded
        laura_fact = await db.execute_fetchone(
            "SELECT * FROM mem_long_term WHERE member_id = 'm-laura' AND superseded_by IS NULL"
        )
        assert laura_fact is not None
        assert "Laura likes sushi" in laura_fact["content"]


class TestCalendarContextIsolation:
    """Verify build_calendar_context() filters events by member."""

    async def test_member_specific_events_filtered(self, db):
        """Events for Laura only should not appear in James's calendar context."""
        from pib.context import build_calendar_context
        from datetime import date

        today = date.today().isoformat()

        # Insert Laura-only event
        await db.execute(
            "INSERT INTO cal_classified_events "
            "(id, event_date, start_time, end_time, title, title_redacted, "
            "for_member_ids, privacy) "
            "VALUES (?, ?, '09:00', '10:00', 'Laura deposition', '[busy]', ?, 'privileged')",
            ["ev-laura-1", today, '["m-laura"]'],
        )
        # Insert household-wide event
        await db.execute(
            "INSERT INTO cal_classified_events "
            "(id, event_date, start_time, end_time, title, title_redacted, "
            "for_member_ids, privacy) "
            "VALUES (?, ?, '15:30', '16:00', 'Charlie pickup', 'Charlie pickup', ?, 'full')",
            ["ev-household-1", today, '[]'],
        )
        await db.commit()

        # James should see household event but not Laura-only event
        james_ctx = await build_calendar_context(db, today, today, "m-james")
        assert "Charlie pickup" in james_ctx
        assert "deposition" not in james_ctx  # Laura's event excluded

        # Laura should see both
        laura_ctx = await build_calendar_context(db, today, today, "m-laura")
        assert "Charlie pickup" in laura_ctx
        assert "[busy]" in laura_ctx  # Privileged: sees redacted title only


class TestMemberSettingsIsolation:
    """Verify per-member settings table works correctly."""

    async def test_settings_scoped_to_member(self, db):
        """Settings for one member don't leak to another."""
        # Apply migration
        await db.execute(
            "CREATE TABLE IF NOT EXISTS pib_member_settings ("
            "member_id TEXT NOT NULL REFERENCES common_members(id), "
            "key TEXT NOT NULL, value TEXT NOT NULL, description TEXT, "
            "updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), "
            "updated_by TEXT DEFAULT 'system', PRIMARY KEY(member_id, key))"
        )

        await db.execute(
            "INSERT INTO pib_member_settings (member_id, key, value) VALUES (?, ?, ?)",
            ["m-james", "theme", "dark"],
        )
        await db.execute(
            "INSERT INTO pib_member_settings (member_id, key, value) VALUES (?, ?, ?)",
            ["m-laura", "theme", "light"],
        )
        await db.commit()

        james_settings = await db.execute_fetchall(
            "SELECT * FROM pib_member_settings WHERE member_id = ?", ["m-james"]
        )
        assert len(james_settings) == 1
        assert james_settings[0]["value"] == "dark"

        laura_settings = await db.execute_fetchall(
            "SELECT * FROM pib_member_settings WHERE member_id = ?", ["m-laura"]
        )
        assert len(laura_settings) == 1
        assert laura_settings[0]["value"] == "light"

    async def test_upsert_doesnt_affect_other_member(self, db):
        """Upserting James's setting doesn't touch Laura's."""
        await db.execute(
            "CREATE TABLE IF NOT EXISTS pib_member_settings ("
            "member_id TEXT NOT NULL REFERENCES common_members(id), "
            "key TEXT NOT NULL, value TEXT NOT NULL, description TEXT, "
            "updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), "
            "updated_by TEXT DEFAULT 'system', PRIMARY KEY(member_id, key))"
        )

        # Set both
        await db.execute(
            "INSERT INTO pib_member_settings (member_id, key, value) VALUES (?, ?, ?)",
            ["m-james", "velocity_cap_override", "10"],
        )
        await db.execute(
            "INSERT INTO pib_member_settings (member_id, key, value) VALUES (?, ?, ?)",
            ["m-laura", "velocity_cap_override", "25"],
        )
        await db.commit()

        # Update James only
        await db.execute(
            "INSERT INTO pib_member_settings (member_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(member_id, key) DO UPDATE SET value = excluded.value",
            ["m-james", "velocity_cap_override", "8"],
        )
        await db.commit()

        # Verify Laura unchanged
        laura_row = await db.execute_fetchone(
            "SELECT value FROM pib_member_settings WHERE member_id = ? AND key = ?",
            ["m-laura", "velocity_cap_override"],
        )
        assert laura_row["value"] == "25"
