"""Privacy fence tests — Invariant 5: privileged data never leaks."""

import pytest
from pib.llm import build_calendar_context

PRIVACY_CANARY = "CANARY_XJ7_PRIVILEGED_LEAK_DETECTOR"


@pytest.fixture
async def db_with_privileged_events(db):
    """Seed privileged calendar events with canary strings."""
    await db.execute(
        "INSERT INTO cal_classified_events "
        "(id, source_id, event_date, start_time, end_time, title, "
        "privacy, title_redacted, for_member_ids) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "priv-1", "laura-work-cal", "2026-03-03", "14:00", "16:00",
            f"Johnson v. Johnson Deposition {PRIVACY_CANARY}",
            "privileged", "Laura - Meeting", '["m-laura"]',
        ],
    )
    await db.execute(
        "INSERT INTO cal_classified_events "
        "(id, source_id, event_date, start_time, end_time, title, "
        "privacy, title_redacted, for_member_ids) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "priv-2", "laura-work-cal", "2026-03-04", "09:00", "10:00",
            f"Smith Custody Mediation {PRIVACY_CANARY}",
            "redacted", "Laura - unavailable", '["m-laura"]',
        ],
    )
    await db.execute(
        "INSERT INTO cal_classified_events "
        "(id, source_id, event_date, start_time, end_time, title, "
        "privacy, title_redacted, for_member_ids) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            "full-1", "family-cal", "2026-03-03", "18:00", "19:00",
            "Family Dinner",
            "full", "Family Dinner", '["m-james","m-laura"]',
        ],
    )
    await db.commit()
    return db


class TestPrivilegedTitleNeverInContext:
    async def test_no_privileged_titles_in_context(self, db_with_privileged_events):
        context = await build_calendar_context(
            db_with_privileged_events, "2026-03-01", "2026-03-07", "m-james"
        )
        assert "Johnson" not in context
        assert "Deposition" not in context
        assert "Smith Custody" not in context
        assert PRIVACY_CANARY not in context
        # Full events DO appear
        assert "Family Dinner" in context

    async def test_privileged_shows_redacted_title(self, db_with_privileged_events):
        """Laura-only events are invisible to James; Laura sees redacted title."""
        # James can't see Laura-only events
        ctx_james = await build_calendar_context(
            db_with_privileged_events, "2026-03-01", "2026-03-07", "m-james"
        )
        assert "Laura - Meeting" not in ctx_james

        # Laura sees her own event with redacted title
        ctx_laura = await build_calendar_context(
            db_with_privileged_events, "2026-03-01", "2026-03-07", "m-laura"
        )
        assert "Laura - Meeting" in ctx_laura

    async def test_redacted_shows_unavailable(self, db_with_privileged_events):
        """Laura-only redacted events are invisible to James; Laura sees [unavailable]."""
        # James can't see Laura-only events
        ctx_james = await build_calendar_context(
            db_with_privileged_events, "2026-03-01", "2026-03-07", "m-james"
        )
        assert "unavailable" not in ctx_james

        # Laura sees her redacted event
        ctx_laura = await build_calendar_context(
            db_with_privileged_events, "2026-03-01", "2026-03-07", "m-laura"
        )
        assert "unavailable" in ctx_laura


class TestCanaryNeverInAnyOutput:
    async def test_canary_never_in_calendar_context(self, db_with_privileged_events):
        context = await build_calendar_context(
            db_with_privileged_events, "2026-03-01", "2026-03-07", "m-james"
        )
        assert PRIVACY_CANARY not in context

    async def test_canary_not_for_any_member(self, db_with_privileged_events):
        for member_id in ["m-james", "m-laura", "m-charlie"]:
            context = await build_calendar_context(
                db_with_privileged_events, "2026-03-01", "2026-03-07", member_id
            )
            assert PRIVACY_CANARY not in context
