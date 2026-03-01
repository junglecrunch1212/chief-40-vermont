"""Tests for pib.extraction — async extraction worker."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from pib.comms import get_comm_by_id, get_pending_extractions, save_extraction_result
from pib.extraction import extraction_worker, retry_failed_extractions


async def insert_comm(db, comm_id, **overrides):
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


class TestExtractionWorker:
    async def test_no_pending_returns_zero(self, db):
        count = await extraction_worker(db)
        assert count == 0

    async def test_disabled_by_config(self, db):
        await db.execute(
            "UPDATE pib_config SET value = '0' WHERE key = 'comms_extraction_enabled'"
        )
        await db.commit()
        await insert_comm(db, "c-01", extraction_status="pending")
        count = await extraction_worker(db)
        assert count == 0

    async def test_pending_comms_found(self, db):
        await insert_comm(db, "c-01", extraction_status="pending")
        pending = await get_pending_extractions(db)
        assert len(pending) == 1
        assert pending[0]["id"] == "c-01"


class TestExtractionResults:
    async def test_save_extraction_result(self, db):
        await insert_comm(db, "c-01", extraction_status="pending")
        items = [
            {"type": "task", "title": "Call plumber", "confidence": 0.85},
            {"type": "event", "title": "Dinner Friday", "confidence": 0.7},
        ]
        await save_extraction_result(db, "c-01", items, 0.775)
        comm = await get_comm_by_id(db, "c-01")
        assert comm["extraction_status"] == "completed"
        assert comm["extraction_confidence"] == 0.775
        parsed = json.loads(comm["extracted_items"])
        assert len(parsed) == 2
        assert parsed[0]["type"] == "task"

    async def test_extraction_result_empty_list(self, db):
        await insert_comm(db, "c-01", extraction_status="pending")
        await save_extraction_result(db, "c-01", [], 0.0)
        comm = await get_comm_by_id(db, "c-01")
        assert comm["extraction_status"] == "completed"
        assert json.loads(comm["extracted_items"]) == []


class TestRetryFailedExtractions:
    async def test_retry_requeues_failed(self, db):
        await insert_comm(db, "c-01", extraction_status="failed")
        await insert_comm(db, "c-02", extraction_status="failed")
        await insert_comm(db, "c-03", extraction_status="completed")
        count = await retry_failed_extractions(db)
        assert count == 2
        comm = await get_comm_by_id(db, "c-01")
        assert comm["extraction_status"] == "pending"

    async def test_retry_no_failed(self, db):
        await insert_comm(db, "c-01", extraction_status="completed")
        count = await retry_failed_extractions(db)
        assert count == 0
