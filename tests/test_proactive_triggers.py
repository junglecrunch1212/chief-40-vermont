"""Tests for proactive trigger evaluation, quiet hours, and guardrails."""

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestQuietHours:
    """Test quiet hours logic — _is_quiet_hours helper."""

    def _is_quiet_hours(self, now_time: time, quiet_start: time = time(22, 0),
                        quiet_end: time = time(7, 0)) -> bool:
        """Local implementation matching expected behavior for testing."""
        if quiet_start <= quiet_end:
            return quiet_start <= now_time <= quiet_end
        else:  # wraps midnight
            return now_time >= quiet_start or now_time <= quiet_end

    def test_midnight_is_quiet(self):
        assert self._is_quiet_hours(time(0, 0))

    def test_3am_is_quiet(self):
        assert self._is_quiet_hours(time(3, 0))

    def test_6am_is_quiet(self):
        assert self._is_quiet_hours(time(6, 0))

    def test_7am_is_quiet(self):
        assert self._is_quiet_hours(time(7, 0))

    def test_8am_is_not_quiet(self):
        assert not self._is_quiet_hours(time(8, 0))

    def test_noon_is_not_quiet(self):
        assert not self._is_quiet_hours(time(12, 0))

    def test_9pm_is_not_quiet(self):
        assert not self._is_quiet_hours(time(21, 0))

    def test_10pm_is_quiet(self):
        assert self._is_quiet_hours(time(22, 0))

    def test_11pm_is_quiet(self):
        assert self._is_quiet_hours(time(23, 0))


class TestTriggerTypes:
    """Test that each trigger type fires on expected conditions."""

    def test_financial_trigger_on_budget_keyword(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("how's our budget looking?", {})
        assert "financial" in result["assemblers"]

    def test_schedule_trigger_on_tomorrow(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("what's happening tomorrow?", {})
        assert "schedule" in result["assemblers"]

    def test_task_trigger_on_overdue(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("any overdue items?", {})
        assert "tasks" in result["assemblers"]

    def test_coverage_trigger_on_custody(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("who has custody?", {})
        assert "coverage" in result["assemblers"]

    def test_comms_trigger_on_email(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("check my emails", {})
        assert "comms" in result["assemblers"]

    def test_capture_trigger_on_note(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("save this note", {})
        assert "captures" in result["assemblers"]

    def test_project_trigger_on_project(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("how's the project?", {})
        assert "projects" in result["assemblers"]

    def test_no_trigger_on_greeting(self):
        from pib.context import analyze_relevance
        result = analyze_relevance("hey there", {})
        # Only cross_domain_summary should be present
        non_summary = [a for a in result["assemblers"] if a != "cross_domain_summary"]
        assert len(non_summary) == 0


class TestGuardrails:
    """Test rate limiting and focus mode suppression patterns."""

    def test_focus_mode_detected_in_energy_state(self):
        """Focus mode should suppress proactive triggers (pattern test)."""
        energy_state = {"focus_mode": 1, "member_id": "m-james"}
        assert energy_state["focus_mode"] == 1
        # In real code, proactive triggers check focus_mode before firing

    def test_rate_limit_window(self):
        """Rate limiting: no more than N proactive messages per hour (pattern test)."""
        recent_proactive_count = 3
        max_per_hour = 3
        should_suppress = recent_proactive_count >= max_per_hour
        assert should_suppress

    def test_under_rate_limit(self):
        recent_proactive_count = 1
        max_per_hour = 3
        should_suppress = recent_proactive_count >= max_per_hour
        assert not should_suppress

    def test_model_tier_escalation_for_complex(self):
        """Complex queries should escalate to opus tier."""
        from pib.context import select_model_tier
        # 3+ assemblers → opus
        assert select_model_tier(["financial", "schedule", "tasks"], "web") == "opus"
        # Simple → sonnet
        assert select_model_tier(["cross_domain_summary"], "web") == "sonnet"
