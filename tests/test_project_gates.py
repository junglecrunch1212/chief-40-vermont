"""Tests for deterministic risk gates."""

import pytest

from pib.project.gates import (
    GateViolation,
    check_financial_gate,
    check_reputational_gate,
    check_technical_gate,
    FORBIDDEN_ACTIONS,
)


class TestFinancialGate:
    """Tests for check_financial_gate()."""

    def test_within_budget_passes(self):
        project = {"can_spend": 1, "budget_limit_cents": 50000, "budget_spent_cents": 10000,
                    "budget_per_action_limit_cents": 5000}
        # Should not raise
        check_financial_gate(project, 2000, "Buy supplies")

    def test_can_spend_zero_raises(self):
        project = {"can_spend": 0}
        with pytest.raises(GateViolation) as exc_info:
            check_financial_gate(project, 100, "Any purchase")
        assert exc_info.value.fence == "financial"
        assert "not authorized to spend" in exc_info.value.reason

    def test_exceeds_budget_raises(self):
        project = {"can_spend": 1, "budget_limit_cents": 10000, "budget_spent_cents": 9500,
                    "budget_per_action_limit_cents": 5000}
        with pytest.raises(GateViolation) as exc_info:
            check_financial_gate(project, 600, "Over budget purchase")
        assert exc_info.value.fence == "financial"
        assert "exceed project budget" in exc_info.value.reason

    def test_exceeds_per_action_limit_raises(self):
        project = {"can_spend": 1, "budget_limit_cents": 100000, "budget_spent_cents": 0,
                    "budget_per_action_limit_cents": 5000}
        with pytest.raises(GateViolation) as exc_info:
            check_financial_gate(project, 6000, "Big purchase")
        assert exc_info.value.fence == "financial"
        assert "per-action limit" in exc_info.value.reason

    def test_no_budget_limit_allows(self):
        """If budget_limit_cents is None, no budget check."""
        project = {"can_spend": 1, "budget_per_action_limit_cents": 10000}
        check_financial_gate(project, 5000, "No budget limit set")

    def test_exactly_at_budget_passes(self):
        """Spending exactly up to the budget should pass."""
        project = {"can_spend": 1, "budget_limit_cents": 10000, "budget_spent_cents": 5000,
                    "budget_per_action_limit_cents": 5000}
        check_financial_gate(project, 5000, "Exact budget")


class TestReputationalGate:
    """Tests for check_reputational_gate()."""

    def test_email_without_permission_raises(self):
        project = {"can_email_strangers": 0}
        with pytest.raises(GateViolation) as exc_info:
            check_reputational_gate(project, "vendor@example.com", "email")
        assert exc_info.value.fence == "reputational"

    def test_email_with_permission_passes(self):
        project = {"can_email_strangers": 1}
        check_reputational_gate(project, "vendor@example.com", "email")

    def test_sms_without_permission_raises(self):
        project = {"can_sms_strangers": 0}
        with pytest.raises(GateViolation):
            check_reputational_gate(project, "+1234567890", "sms")

    def test_sms_with_permission_passes(self):
        project = {"can_sms_strangers": 1}
        check_reputational_gate(project, "+1234567890", "sms")

    def test_call_without_permission_raises(self):
        project = {"can_call_strangers": 0}
        with pytest.raises(GateViolation):
            check_reputational_gate(project, "+1234567890", "call")

    def test_call_with_permission_passes(self):
        project = {"can_call_strangers": 1}
        check_reputational_gate(project, "+1234567890", "call")

    def test_twilio_sms_alias(self):
        """twilio_sms maps to can_sms_strangers."""
        project = {"can_sms_strangers": 0}
        with pytest.raises(GateViolation):
            check_reputational_gate(project, "+1234567890", "twilio_sms")

    def test_unknown_channel_passes(self):
        """Unknown channels don't have permission requirements."""
        project = {}
        check_reputational_gate(project, "handle", "unknown_channel")


class TestTechnicalGate:
    """Tests for check_technical_gate()."""

    def test_modify_config_forbidden(self):
        with pytest.raises(GateViolation) as exc_info:
            check_technical_gate("modify_config")
        assert exc_info.value.fence == "technical"
        assert "Gene 4" in exc_info.value.reason

    def test_modify_schema_forbidden(self):
        with pytest.raises(GateViolation):
            check_technical_gate("modify_schema")

    def test_delete_data_forbidden(self):
        with pytest.raises(GateViolation):
            check_technical_gate("delete_data")

    def test_web_search_allowed(self):
        """Non-forbidden actions should pass."""
        check_technical_gate("web_search")

    def test_gmail_send_allowed(self):
        check_technical_gate("gmail_send")

    def test_all_forbidden_actions_raise(self):
        """Every action in FORBIDDEN_ACTIONS should raise."""
        for action in FORBIDDEN_ACTIONS:
            with pytest.raises(GateViolation):
                check_technical_gate(action)


class TestGateViolation:
    """Tests for GateViolation exception."""

    def test_attributes(self):
        exc = GateViolation(fence="financial", reason="Over budget", requires="approval")
        assert exc.fence == "financial"
        assert exc.reason == "Over budget"
        assert exc.requires == "approval"

    def test_str_format(self):
        exc = GateViolation(fence="technical", reason="Forbidden action")
        assert "[technical]" in str(exc)
        assert "Forbidden action" in str(exc)
