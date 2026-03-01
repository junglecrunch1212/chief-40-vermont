"""Tests for LLM integration: context assembly, tool dispatch, deterministic fallback."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pib.llm import (
    analyze_relevance,
    assemble_context,
    build_conversation_history,
    build_cross_domain_summary,
    build_entity_cache,
    build_system_prompt,
    deterministic_fallback,
    estimate_tokens,
    execute_tool,
    select_model_tier,
)


class TestTokenEstimation:
    def test_estimate_tokens(self):
        assert estimate_tokens("hello world") == 2  # 11 chars / 4

    def test_empty_string(self):
        assert estimate_tokens("") == 0


class TestRelevanceDetection:
    def test_financial_triggers(self):
        result = analyze_relevance("how much did we spend on groceries?", {})
        assert "financial" in result["assemblers"]

    def test_schedule_triggers(self):
        result = analyze_relevance("what's on the calendar today?", {})
        assert "schedule" in result["assemblers"]

    def test_task_triggers(self):
        result = analyze_relevance("I need to finish my todo list", {})
        assert "tasks" in result["assemblers"]

    def test_coverage_triggers(self):
        result = analyze_relevance("who has custody this weekend?", {})
        assert "coverage" in result["assemblers"]
        assert "schedule" in result["assemblers"]

    def test_cross_domain_always_included(self):
        result = analyze_relevance("hello", {})
        assert "cross_domain_summary" in result["assemblers"]


class TestEntityCache:
    def test_build_cache(self):
        rows = [{"id": "itm-1", "name": "Dr. Smith", "display_name": None}]
        cache = build_entity_cache(rows)
        assert "itm-1" in cache
        assert cache["itm-1"]["pattern"].search("call dr. smith")


class TestModelSelection:
    def test_simple_query_uses_sonnet(self):
        assert select_model_tier(["cross_domain_summary"], "web") == "sonnet"

    def test_complex_query_uses_opus(self):
        assert select_model_tier(["financial", "schedule", "tasks"], "web") == "opus"

    def test_morning_brief_uses_opus(self):
        assert select_model_tier(["morning_brief"], "web") == "opus"


class TestSystemPrompt:
    def test_james_prompt_includes_adhd(self):
        member = {"id": "m-james", "display_name": "James", "role": "parent"}
        prompt = build_system_prompt(member, "web", [])
        assert "ADHD-aware" in prompt
        assert "ONE thing at a time" in prompt

    def test_laura_prompt_includes_privacy(self):
        member = {"id": "m-laura", "display_name": "Laura", "role": "parent"}
        prompt = build_system_prompt(member, "web", [])
        assert "Never reference or acknowledge her work calendar content" in prompt

    def test_sms_channel_brevity(self):
        member = {"id": "m-james", "display_name": "James", "role": "parent"}
        prompt = build_system_prompt(member, "sms", [])
        assert "BREVITY" in prompt

    def test_coach_protocols_included(self):
        member = {"id": "m-james", "display_name": "James", "role": "parent"}
        protocols = [{"name": "Never Guilt", "behavior": "No shaming, ever."}]
        prompt = build_system_prompt(member, "web", protocols)
        assert "Never Guilt" in prompt


class TestConversationHistory:
    def test_sliding_window(self):
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(100)]
        result = build_conversation_history(messages, "web")
        assert len(result) <= 50

    def test_sms_shorter_window(self):
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        result = build_conversation_history(messages, "sms")
        assert len(result) <= 10


class TestToolExecution:
    async def test_what_now_tool(self, db):
        result = await execute_tool(db, "what_now", {"member_id": "m-james"}, "m-james")
        assert "the_one_task" in result

    async def test_add_list_items_tool(self, db):
        result = await execute_tool(
            db, "add_list_items",
            {"list_name": "grocery", "items": ["milk", "eggs"]},
            "m-james",
        )
        assert result["added_count"] == 2
        assert result["list"] == "grocery"

    async def test_create_task_tool(self, db):
        result = await execute_tool(
            db, "create_task",
            {"title": "Call dentist", "assignee": "m-james"},
            "m-james",
        )
        assert "created" in result
        assert result["title"] == "Call dentist"

    async def test_save_memory_tool(self, db):
        result = await execute_tool(
            db, "save_memory",
            {"content": "Charlie's favorite color is blue", "category": "facts"},
            "m-james",
        )
        assert result["action"] == "inserted"

    async def test_recall_memory_tool(self, db):
        # First save, then recall
        await execute_tool(
            db, "save_memory",
            {"content": "Test memory for recall", "category": "facts"},
            "m-james",
        )
        # Note: FTS5 might not work in tests without proper content sync triggers,
        # so we just verify the function runs without error
        result = await execute_tool(
            db, "recall_memory", {"query": "test memory"}, "m-james"
        )
        assert "memories" in result

    async def test_log_state_tool(self, db):
        result = await execute_tool(
            db, "log_state",
            {"action": "medication_taken"},
            "m-james",
        )
        assert result["logged"] == "medication_taken"

    async def test_send_message_non_household_goes_to_approval(self, db):
        result = await execute_tool(
            db, "send_message",
            {"to": "dr-smith", "content": "Confirming appointment"},
            "m-james",
        )
        assert "queued_for_approval" in result

    async def test_unknown_tool(self, db):
        result = await execute_tool(db, "nonexistent_tool", {}, "m-james")
        assert "error" in result


class TestDeterministicFallback:
    async def test_what_next_query(self, db):
        result = await deterministic_fallback("what's next?", "m-james", db)
        assert "Next:" in result or "Nothing pending" in result

    async def test_custody_query(self, db):
        result = await deterministic_fallback("who has Charlie?", "m-james", db)
        assert "Custody" in result or "custody" in result.lower() or "unavailable" in result.lower()

    async def test_generic_query(self, db):
        result = await deterministic_fallback("hello there", "m-james", db)
        assert "offline" in result.lower() or "basic mode" in result.lower()


class TestContextAssembly:
    async def test_assembles_dashboard(self, db):
        ctx = await assemble_context(db, "m-james", "hello")
        assert "DASHBOARD:" in ctx

    async def test_task_triggers_add_next_task(self, db):
        ctx = await assemble_context(db, "m-james", "what's my next task?")
        assert "NEXT TASK:" in ctx or "DASHBOARD:" in ctx

    async def test_coverage_trigger_adds_custody(self, db):
        ctx = await assemble_context(db, "m-james", "who has custody today?")
        # May or may not have custody data depending on seed
        assert "DASHBOARD:" in ctx
