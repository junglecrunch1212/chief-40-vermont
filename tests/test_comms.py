"""Tests for pib.comms — inbox, batch windows, drafts, extraction, snooze."""

import json
from datetime import datetime, time

import pytest

from pib.comms import (
    approve_draft,
    approve_extraction,
    archive_comm,
    assign_batch_date,
    assign_batch_window,
    capture_manual,
    get_comm_by_id,
    get_comms_counts,
    get_comms_inbox,
    mark_responded,
    queue_extraction,
    reject_draft,
    reject_extraction,
    save_draft,
    snooze_comm,
    tag_comm,
    unsnooze_due,
)

# Default batch config for tests
TEST_BATCH_CONFIG = {
    "morning": {"start": time(8, 0), "end": time(9, 0)},
    "midday": {"start": time(12, 0), "end": time(13, 0)},
    "evening": {"start": time(19, 0), "end": time(20, 0)},
}


# ─── Helper: insert a test comm ───

async def insert_comm(db, comm_id="c-test-01", **overrides):
    defaults = {
        "id": comm_id,
        "date": "2026-03-01",
        "channel": "imessage",
        "direction": "inbound",
        "from_addr": "Dan",
        "member_id": "m-james",
        "summary": "Can you call the plumber?",
        "body_snippet": "Hey, can you call the plumber about the leak?",
        "needs_response": 1,
        "response_urgency": "timely",
        "outcome": "pending",
        "visibility": "normal",
        "extraction_status": "none",
        "draft_status": "none",
        "created_by": "test",
    }
    defaults.update(overrides)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join(["?"] * len(defaults))
    await db.execute(
        f"INSERT INTO ops_comms ({cols}) VALUES ({placeholders})",
        list(defaults.values()),
    )
    await db.commit()
    return defaults


# ═══════════════════════════════════════════════════════════
# Batch Window Assignment
# ═══════════════════════════════════════════════════════════

class TestBatchWindowAssignment:
    def test_early_morning_goes_to_morning(self):
        dt = datetime(2026, 3, 1, 7, 30)
        assert assign_batch_window(dt, TEST_BATCH_CONFIG) == "morning"

    def test_midday_comm_goes_to_midday(self):
        dt = datetime(2026, 3, 1, 10, 0)
        assert assign_batch_window(dt, TEST_BATCH_CONFIG) == "midday"

    def test_afternoon_goes_to_evening(self):
        dt = datetime(2026, 3, 1, 15, 0)
        assert assign_batch_window(dt, TEST_BATCH_CONFIG) == "evening"

    def test_late_night_goes_to_next_morning(self):
        dt = datetime(2026, 3, 1, 22, 0)
        assert assign_batch_window(dt, TEST_BATCH_CONFIG) == "morning"

    def test_deterministic_same_input_same_output(self):
        dt = datetime(2026, 3, 1, 11, 30)
        result1 = assign_batch_window(dt, TEST_BATCH_CONFIG)
        result2 = assign_batch_window(dt, TEST_BATCH_CONFIG)
        assert result1 == result2

    def test_batch_date_normal(self):
        dt = datetime(2026, 3, 1, 10, 0)
        d = assign_batch_date(dt, "midday", TEST_BATCH_CONFIG)
        assert d == "2026-03-01"

    def test_batch_date_next_day_for_late_night(self):
        dt = datetime(2026, 3, 1, 22, 0)
        d = assign_batch_date(dt, "morning", TEST_BATCH_CONFIG)
        assert d == "2026-03-02"


# ═══════════════════════════════════════════════════════════
# Inbox Queries
# ═══════════════════════════════════════════════════════════

class TestCommsInbox:
    async def test_empty_inbox(self, db):
        result = await get_comms_inbox(db)
        assert result == []

    async def test_inbox_returns_comms(self, db):
        await insert_comm(db, "c-01")
        await insert_comm(db, "c-02")
        result = await get_comms_inbox(db)
        assert len(result) == 2

    async def test_filter_by_needs_response(self, db):
        await insert_comm(db, "c-01", needs_response=1)
        await insert_comm(db, "c-02", needs_response=0)
        result = await get_comms_inbox(db, needs_response=True)
        assert len(result) == 1
        assert result[0]["id"] == "c-01"

    async def test_filter_by_urgency(self, db):
        await insert_comm(db, "c-01", response_urgency="urgent")
        await insert_comm(db, "c-02", response_urgency="fyi")
        result = await get_comms_inbox(db, urgency="urgent")
        assert len(result) == 1

    async def test_filter_by_channel(self, db):
        await insert_comm(db, "c-01", channel="email")
        await insert_comm(db, "c-02", channel="imessage")
        result = await get_comms_inbox(db, channel="email")
        assert len(result) == 1
        assert result[0]["channel"] == "email"

    async def test_search_by_text(self, db):
        await insert_comm(db, "c-01", summary="Call the plumber", body_snippet="Need to fix the sink")
        await insert_comm(db, "c-02", summary="Dinner at 7", body_snippet="Restaurant on Friday")
        result = await get_comms_inbox(db, search="plumber")
        assert len(result) == 1

    async def test_urgent_sorted_first(self, db):
        await insert_comm(db, "c-01", response_urgency="fyi")
        await insert_comm(db, "c-02", response_urgency="urgent")
        result = await get_comms_inbox(db)
        assert result[0]["response_urgency"] == "urgent"

    async def test_archived_not_in_inbox(self, db):
        await insert_comm(db, "c-01", visibility="archived")
        result = await get_comms_inbox(db)
        assert len(result) == 0


class TestCommsCounts:
    async def test_counts_empty(self, db):
        counts = await get_comms_counts(db)
        assert counts["needs_response"] == 0
        assert counts["urgent"] == 0

    async def test_counts_with_data(self, db):
        await insert_comm(db, "c-01", needs_response=1, response_urgency="urgent")
        await insert_comm(db, "c-02", needs_response=1, response_urgency="timely")
        await insert_comm(db, "c-03", needs_response=0)
        counts = await get_comms_counts(db)
        assert counts["needs_response"] == 2
        assert counts["urgent"] == 1
        assert counts["total_normal"] == 3


# ═══════════════════════════════════════════════════════════
# State Transitions
# ═══════════════════════════════════════════════════════════

class TestCommsStateTransitions:
    async def test_mark_responded(self, db):
        await insert_comm(db, "c-01", needs_response=1)
        await mark_responded(db, "c-01")
        comm = await get_comm_by_id(db, "c-01")
        assert comm["needs_response"] == 0
        assert comm["outcome"] == "responded"
        assert comm["responded_at"] is not None

    async def test_snooze_comm(self, db):
        await insert_comm(db, "c-01")
        await snooze_comm(db, "c-01", "2026-03-02T08:00:00Z")
        comm = await get_comm_by_id(db, "c-01")
        assert comm["visibility"] == "snoozed"
        assert comm["snoozed_until"] == "2026-03-02T08:00:00Z"

    async def test_unsnooze_due(self, db):
        await insert_comm(db, "c-01", visibility="snoozed", snoozed_until="2020-01-01T00:00:00Z")
        count = await unsnooze_due(db)
        assert count == 1
        comm = await get_comm_by_id(db, "c-01")
        assert comm["visibility"] == "normal"

    async def test_unsnooze_not_yet_due(self, db):
        await insert_comm(db, "c-01", visibility="snoozed", snoozed_until="2030-01-01T00:00:00Z")
        count = await unsnooze_due(db)
        assert count == 0

    async def test_archive_comm(self, db):
        await insert_comm(db, "c-01")
        await archive_comm(db, "c-01")
        comm = await get_comm_by_id(db, "c-01")
        assert comm["visibility"] == "archived"

    async def test_tag_comm(self, db):
        await insert_comm(db, "c-01")
        await tag_comm(db, "c-01", "follow-up")
        comm = await get_comm_by_id(db, "c-01")
        assert comm["suggested_action"] == "follow-up"


# ═══════════════════════════════════════════════════════════
# Extraction Lifecycle
# ═══════════════════════════════════════════════════════════

class TestExtractionLifecycle:
    async def test_queue_extraction(self, db):
        await insert_comm(db, "c-01", extraction_status="none")
        await queue_extraction(db, "c-01")
        comm = await get_comm_by_id(db, "c-01")
        assert comm["extraction_status"] == "pending"

    async def test_approve_extraction(self, db):
        items = [{"type": "task", "title": "Call plumber", "confidence": 0.9}]
        await insert_comm(db, "c-01", extracted_items=json.dumps(items), extraction_status="completed")
        result = await approve_extraction(db, "c-01", 0)
        assert result is not None
        assert result["approved"] is True

    async def test_reject_extraction(self, db):
        items = [{"type": "task", "title": "Call plumber", "confidence": 0.9}]
        await insert_comm(db, "c-01", extracted_items=json.dumps(items), extraction_status="completed")
        result = await reject_extraction(db, "c-01", 0)
        assert result is True
        comm = await get_comm_by_id(db, "c-01")
        updated_items = json.loads(comm["extracted_items"])
        assert updated_items[0]["rejected"] is True

    async def test_approve_invalid_index(self, db):
        items = [{"type": "task", "title": "Call plumber", "confidence": 0.9}]
        await insert_comm(db, "c-01", extracted_items=json.dumps(items))
        result = await approve_extraction(db, "c-01", 5)
        assert result is None


# ═══════════════════════════════════════════════════════════
# Draft Lifecycle
# ═══════════════════════════════════════════════════════════

class TestDraftLifecycle:
    async def test_save_draft(self, db):
        await insert_comm(db, "c-01")
        await save_draft(db, "c-01", "Thanks, I'll call them today.")
        comm = await get_comm_by_id(db, "c-01")
        assert comm["draft_response"] == "Thanks, I'll call them today."
        assert comm["draft_status"] == "pending"

    async def test_approve_draft(self, db):
        await insert_comm(db, "c-01", draft_response="Thanks!", draft_status="pending")
        result = await approve_draft(db, "c-01")
        assert result is not None
        assert result["draft_status"] == "approved"

    async def test_approve_draft_with_edit(self, db):
        await insert_comm(db, "c-01", draft_response="Thanks!", draft_status="pending")
        result = await approve_draft(db, "c-01", edited_body="Thanks so much!")
        assert result["draft_response"] == "Thanks so much!"

    async def test_reject_draft(self, db):
        await insert_comm(db, "c-01", draft_status="pending")
        await reject_draft(db, "c-01")
        comm = await get_comm_by_id(db, "c-01")
        assert comm["draft_status"] == "rejected"

    async def test_approve_non_pending_draft_fails(self, db):
        await insert_comm(db, "c-01", draft_status="rejected")
        result = await approve_draft(db, "c-01")
        assert result is None


# ═══════════════════════════════════════════════════════════
# Manual Capture
# ═══════════════════════════════════════════════════════════

class TestManualCapture:
    async def test_capture_creates_comm(self, db):
        comm_id = await capture_manual(db, "m-james", {
            "summary": "Meeting notes from standup",
            "body_snippet": "Discussed sprint progress. Need to follow up on testing.",
            "comm_type": "meeting_note",
        })
        assert comm_id.startswith("c-")
        comm = await get_comm_by_id(db, comm_id)
        assert comm is not None
        assert comm["summary"] == "Meeting notes from standup"
        assert comm["extraction_status"] == "pending"
        assert comm["source_classification"] == "manual_capture"

    async def test_capture_assigns_batch_window(self, db):
        comm_id = await capture_manual(db, "m-james", {"summary": "Test note"})
        comm = await get_comm_by_id(db, comm_id)
        assert comm["batch_window"] in ("morning", "midday", "evening")
        assert comm["batch_date"] is not None
