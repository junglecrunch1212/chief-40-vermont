"""Tests for ingestion pipeline — dedup, routing, list creation."""

import pytest
from pib.ingest import (
    IngestEvent, is_duplicate, make_idempotency_key,
    parse_prefix, generate_micro_script, route_prefix,
)


class TestIdempotency:
    async def test_duplicate_detected(self, db):
        key = make_idempotency_key("sms", "msg-123")
        assert not await is_duplicate(db, key)

        await db.execute(
            "INSERT INTO common_idempotency_keys (key_hash, source) VALUES (?, ?)",
            [key, "sms"],
        )
        assert await is_duplicate(db, key)

    async def test_different_keys_not_duplicate(self, db):
        key1 = make_idempotency_key("sms", "msg-123")
        key2 = make_idempotency_key("sms", "msg-456")
        assert key1 != key2


class TestMicroScriptGenerator:
    def test_purchase_task(self):
        script = generate_micro_script({"title": "Buy diapers", "item_type": "purchase"})
        assert "search" in script.lower()
        assert "diapers" in script

    def test_phone_task(self):
        script = generate_micro_script({"title": "Call dentist", "requires": "phone"})
        assert "phone" in script.lower()

    def test_research_task(self):
        script = generate_micro_script({"title": "Best car seats 2026", "item_type": "research"})
        assert "browser" in script.lower()

    def test_decision_task(self):
        script = generate_micro_script({"title": "Nursery paint color", "item_type": "decision"})
        assert "pros/cons" in script.lower()

    def test_default_task(self):
        script = generate_micro_script({"title": "Some generic task"})
        assert "Some generic task" in script


class TestRoutePrefix:
    async def test_grocery_creates_list_items(self, db):
        event = IngestEvent(
            source="test", timestamp="2026-01-01T00:00:00Z",
            idempotency_key="test-key", raw={}, text="grocery: milk, eggs, bread",
            member_id="m-james",
        )
        prefix = parse_prefix(event.text)
        result = await route_prefix(db, prefix, event)
        assert result["action"] == "list_items_added"
        assert result["count"] == 3

        # Verify items in DB
        rows = await db.execute_fetchall(
            "SELECT * FROM ops_lists WHERE list_name = 'grocery'"
        )
        assert len(rows) == 3

    async def test_task_prefix_creates_task(self, db):
        event = IngestEvent(
            source="test", timestamp="2026-01-01T00:00:00Z",
            idempotency_key="test-key", raw={}, text="buy diapers",
            member_id="m-james",
        )
        prefix = parse_prefix(event.text)
        result = await route_prefix(db, prefix, event)
        assert result["action"] == "task_created"
        assert "diapers" in result["title"]
