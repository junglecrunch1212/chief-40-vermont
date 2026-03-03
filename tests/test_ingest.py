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

    async def test_meds_taken_writes_to_energy_states(self, db):
        """Send 'meds taken' event, verify pib_energy_states has meds_taken=1."""
        event = IngestEvent(
            source="test", timestamp="2026-01-01T00:00:00Z",
            idempotency_key="test-meds", raw={}, text="meds taken",
            member_id="m-james",
        )
        prefix = parse_prefix(event.text)
        result = await route_prefix(db, prefix, event)
        await db.commit()

        assert result["action"] == "state_recorded"
        assert result["command"] == "medication_taken"

        row = await db.execute_fetchone(
            "SELECT meds_taken FROM pib_energy_states WHERE member_id = 'm-james' AND state_date = date('now')"
        )
        assert row is not None
        assert row["meds_taken"] == 1

    async def test_sleep_report_writes_to_energy_states(self, db):
        """Send 'sleep great' event, verify pib_energy_states has sleep_quality."""
        event = IngestEvent(
            source="test", timestamp="2026-01-01T00:00:00Z",
            idempotency_key="test-sleep", raw={}, text="sleep great",
            member_id="m-james",
        )
        prefix = parse_prefix(event.text)
        result = await route_prefix(db, prefix, event)
        await db.commit()

        assert result["action"] == "state_recorded"

        row = await db.execute_fetchone(
            "SELECT sleep_quality FROM pib_energy_states WHERE member_id = 'm-james' AND state_date = date('now')"
        )
        assert row is not None
        assert row["sleep_quality"] == "great"


class TestOpenClawMode:
    async def test_no_top_level_llm_import(self):
        """Verify no top-level import of pib.llm in ingest.py."""
        import ast
        from pathlib import Path
        ingest_path = Path(__file__).parent.parent / "src" / "pib" / "ingest.py"
        source = ingest_path.read_text()
        tree = ast.parse(source)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module and "pib.llm" in node.module:
                    pytest.fail(f"Top-level import of pib.llm found at line {node.lineno}")

    async def test_openclaw_mode_queues_instead_of_llm(self, db):
        """With PIB_RUNTIME_MODE=openclaw, messages should be queued not processed inline."""
        import os
        from pib.ingest import ingest, IngestEvent, make_idempotency_key

        os.environ["PIB_RUNTIME_MODE"] = "openclaw"
        try:
            event = IngestEvent(
                source="test", timestamp="2026-01-01T00:00:00Z",
                idempotency_key=make_idempotency_key("test", "openclaw-test"),
                raw={}, text="hello how are you",
                member_id="m-james",
            )
            actions = await ingest(event, db)
            assert any(a.get("reason") == "openclaw_mode" or a.get("action") == "queued_for_processing" for a in actions)
        finally:
            os.environ.pop("PIB_RUNTIME_MODE", None)
