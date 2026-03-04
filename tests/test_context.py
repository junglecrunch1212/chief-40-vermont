"""Tests for pib.context: context assembly, relevance detection, token budgeting, privacy fence."""

import pytest
from pib.context import (
    analyze_relevance,
    build_calendar_context,
    build_entity_cache,
    build_conversation_history,
    build_system_prompt,
    enforce_budget,
    estimate_tokens,
    FINANCIAL_TRIGGERS,
    SCHEDULE_TRIGGERS,
    TASK_TRIGGERS,
    COVERAGE_TRIGGERS,
    COMMS_TRIGGERS,
    CAPTURE_TRIGGERS,
    PROJECT_TRIGGERS,
    select_model_tier,
)

PRIVACY_CANARY = "CANARY_XJ7_PRIVILEGED_LEAK_DETECTOR"


# ─── Token Budget ───

class TestTokenBudget:
    def test_estimate_tokens_basic(self):
        assert estimate_tokens("hello world") == 2  # 11 chars / 4

    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 0

    def test_enforce_budget_within_limit(self):
        content = "short content"
        result = enforce_budget("system_prompt", content)
        assert result == content

    def test_enforce_budget_truncates(self):
        # system_prompt budget = 2500 tokens = 10000 chars
        content = "x" * 20000
        result = enforce_budget("system_prompt", content)
        assert len(result) < len(content)
        assert "[truncated]" in result

    def test_enforce_budget_unknown_section(self):
        # Unknown sections get 25000 token budget
        content = "small"
        result = enforce_budget("nonexistent_section", content)
        assert result == content


# ─── Relevance Detection ───

class TestRelevanceDetection:
    def test_financial_triggers(self):
        result = analyze_relevance("how much did we spend on groceries?", {})
        assert "financial" in result["assemblers"]

    def test_schedule_triggers(self):
        result = analyze_relevance("what's on the calendar today?", {})
        assert "schedule" in result["assemblers"]

    def test_task_triggers(self):
        result = analyze_relevance("show me overdue tasks", {})
        assert "tasks" in result["assemblers"]

    def test_coverage_triggers(self):
        result = analyze_relevance("who has custody this weekend?", {})
        assert "coverage" in result["assemblers"]
        assert "schedule" in result["assemblers"]  # coverage adds schedule too

    def test_comms_triggers(self):
        result = analyze_relevance("any new emails in my inbox?", {})
        assert "comms" in result["assemblers"]

    def test_capture_triggers(self):
        result = analyze_relevance("save this recipe for later", {})
        assert "captures" in result["assemblers"]

    def test_project_triggers(self):
        result = analyze_relevance("how's the piano teacher project going?", {})
        assert "projects" in result["assemblers"]

    def test_cross_domain_always_present(self):
        result = analyze_relevance("hello", {})
        assert "cross_domain_summary" in result["assemblers"]

    def test_entity_matching(self):
        cache = build_entity_cache([{"id": "v-1", "name": "Dr. Smith"}])
        result = analyze_relevance("call dr. smith about the appointment", cache)
        assert "entity_lookup" in result["assemblers"]
        assert "v-1" in result["matched_entities"]

    def test_no_false_entity_match(self):
        cache = build_entity_cache([{"id": "v-1", "name": "Dr. Smith"}])
        result = analyze_relevance("what's for dinner?", cache)
        assert "entity_lookup" not in result["assemblers"]

    def test_multiple_triggers(self):
        result = analyze_relevance("check the budget and calendar for today", {})
        assert "financial" in result["assemblers"]
        assert "schedule" in result["assemblers"]

    def test_all_seven_trigger_sets_exist(self):
        """Ensure all 7 trigger dictionaries are non-empty sets."""
        for triggers in [FINANCIAL_TRIGGERS, SCHEDULE_TRIGGERS, TASK_TRIGGERS,
                         COVERAGE_TRIGGERS, COMMS_TRIGGERS, CAPTURE_TRIGGERS,
                         PROJECT_TRIGGERS]:
            assert isinstance(triggers, set)
            assert len(triggers) > 0


# ─── Model Selection ───

class TestModelSelection:
    def test_simple_query_uses_sonnet(self):
        assert select_model_tier(["cross_domain_summary"], "web") == "sonnet"

    def test_complex_query_uses_opus(self):
        assert select_model_tier(["financial", "schedule", "tasks"], "web") == "opus"

    def test_morning_brief_uses_opus(self):
        assert select_model_tier(["morning_brief"], "web") == "opus"

    def test_email_uses_opus(self):
        assert select_model_tier(["comms"], "email") == "opus"


# ─── System Prompt ───

class TestSystemPrompt:
    def test_produces_string(self):
        member = {"id": "m-james", "display_name": "James", "role": "parent"}
        result = build_system_prompt(member, "web", [])
        assert isinstance(result, str)
        assert "James" in result
        assert "ADHD" in result  # James-specific

    def test_laura_prompt(self):
        member = {"id": "m-laura", "display_name": "Laura", "role": "parent"}
        result = build_system_prompt(member, "web", [])
        assert "Laura" in result
        assert "HOME life only" in result

    def test_brevity_on_sms(self):
        member = {"id": "m-james", "display_name": "James", "role": "parent"}
        result = build_system_prompt(member, "sms", [])
        assert "BREVITY" in result

    def test_protocols_included(self):
        member = {"id": "m-james", "display_name": "James", "role": "parent"}
        protocols = [{"name": "TestProto", "behavior": "Do the thing"}]
        result = build_system_prompt(member, "web", protocols)
        assert "TestProto" in result
        assert "Do the thing" in result


# ─── Conversation History ───

class TestConversationHistory:
    def test_sliding_window(self):
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(100)]
        result = build_conversation_history(msgs, "web")
        assert len(result) <= 50

    def test_sms_shorter_window(self):
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        result = build_conversation_history(msgs, "sms")
        assert len(result) <= 10

    def test_empty_messages(self):
        assert build_conversation_history([], "web") == []


# ─── Privacy Fence ───

class TestPrivacyFence:
    @pytest.fixture
    async def db_with_privileged_events(self, db):
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
        await db.commit()
        return db

    @pytest.mark.asyncio
    async def test_privileged_title_never_leaks(self, db_with_privileged_events):
        """Invariant 5: privileged calendar titles must not appear in context."""
        ctx = await build_calendar_context(
            db_with_privileged_events, "2026-03-03", "2026-03-03", "m-james"
        )
        assert PRIVACY_CANARY not in ctx
        assert "Johnson" not in ctx
        assert "Laura - Meeting" in ctx  # redacted title should appear

    @pytest.mark.asyncio
    async def test_full_privacy_shows_title(self, db):
        """Full-privacy events show their real title."""
        await db.execute(
            "INSERT INTO cal_classified_events "
            "(id, source_id, event_date, start_time, end_time, title, "
            "privacy, title_redacted, for_member_ids) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "full-1", "family-cal", "2026-03-03", "10:00", "11:00",
                "Charlie Soccer Practice",
                "full", "Charlie Soccer Practice", '["m-james","m-laura"]',
            ],
        )
        await db.commit()
        ctx = await build_calendar_context(db, "2026-03-03", "2026-03-03", "m-james")
        assert "Charlie Soccer Practice" in ctx

    @pytest.mark.asyncio
    async def test_redacted_shows_unavailable(self, db):
        """Redacted events show [unavailable]."""
        await db.execute(
            "INSERT INTO cal_classified_events "
            "(id, source_id, event_date, start_time, end_time, title, "
            "privacy, title_redacted, for_member_ids) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "red-1", "private-cal", "2026-03-03", "12:00", "13:00",
                "Secret Thing",
                "redacted", None, '["m-laura"]',
            ],
        )
        await db.commit()
        ctx = await build_calendar_context(db, "2026-03-03", "2026-03-03", "m-james")
        assert "Secret Thing" not in ctx
        assert "[unavailable]" in ctx

    @pytest.mark.asyncio
    async def test_no_events(self, db):
        ctx = await build_calendar_context(db, "2099-01-01", "2099-01-01", "m-james")
        assert ctx == "No events."
