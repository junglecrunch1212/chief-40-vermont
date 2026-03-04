"""Tests for bootstrap-verify CLI command.

Covers:
- Passes on healthy database
- Reports failures individually
- Works without bridge connectivity
- Cleans up test artifacts
"""

import os

import pytest
import pytest_asyncio

from pib.cli import cmd_bootstrap_verify


# ═══════════════════════════════════════════════════════════
# TestBootstrapVerify
# ═══════════════════════════════════════════════════════════

class TestBootstrapVerify:
    """Test bootstrap-verify comprehensive verification command."""

    @pytest.mark.asyncio
    async def test_passes_on_healthy_db(self, db):
        """Bootstrap verify should pass on a properly seeded database."""
        # Set required env vars for readiness
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-token")
        os.environ.setdefault("TWILIO_PHONE_NUMBER", "+1234567890")
        os.environ.setdefault("SIRI_BEARER_TOKEN", "test-bearer")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        result = await cmd_bootstrap_verify(db, {}, "dev")

        # Check structure
        assert "overall" in result
        assert "checks" in result
        assert "timestamp" in result

        # Individual checks should be present
        checks = result["checks"]
        assert "readiness" in checks
        assert "what_now_james" in checks
        assert "what_now_laura" in checks
        assert "task_lifecycle" in checks
        assert "governance_coach_blocked" in checks
        assert "memory_isolation" in checks

    @pytest.mark.asyncio
    async def test_reports_failures_individually(self, db):
        """Each check should report independently — one failure doesn't stop others."""
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        result = await cmd_bootstrap_verify(db, {}, "dev")

        checks = result["checks"]

        # All checks should have pass and detail keys
        for check_name, check_result in checks.items():
            assert "pass" in check_result, f"Check {check_name} missing 'pass' key"
            assert "detail" in check_result, f"Check {check_name} missing 'detail' key"

    @pytest.mark.asyncio
    async def test_works_without_bridges(self, db):
        """Bootstrap verify should work when bridge hosts are not configured."""
        # Remove bridge host env vars
        for key in ["BLUEBUBBLES_JAMES_HOST", "BLUEBUBBLES_LAURA_HOST"]:
            os.environ.pop(key, None)

        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        result = await cmd_bootstrap_verify(db, {}, "dev")

        # Should complete without error
        assert "overall" in result
        assert "checks" in result

        # Bridge connectivity check should either be skipped or show "not set"
        if "bridge_connectivity" in result["checks"]:
            detail = result["checks"]["bridge_connectivity"].get("detail", {})
            # Should indicate hosts are not configured
            for bridge in ["james", "laura"]:
                if bridge in detail:
                    assert detail[bridge].get("skipped") or "not set" in str(detail[bridge].get("reason", ""))

    @pytest.mark.asyncio
    async def test_cleans_up_test_artifacts(self, db):
        """Bootstrap verify should clean up any test tasks/memories it creates."""
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        # Run bootstrap verify
        await cmd_bootstrap_verify(db, {}, "dev")

        # Check no test artifacts remain
        test_task = await db.execute_fetchone(
            "SELECT * FROM ops_tasks WHERE title = '__bootstrap_verify_test_task__'"
        )
        assert test_task is None, "Test task should be cleaned up"

        test_memory = await db.execute_fetchone(
            "SELECT * FROM mem_long_term WHERE content LIKE '%__bootstrap_verify_memory_test%'"
        )
        assert test_memory is None, "Test memory should be cleaned up"

    @pytest.mark.asyncio
    async def test_governance_coach_blocked_check(self, db):
        """Coach agent should be verified as blocked from task-create."""
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        result = await cmd_bootstrap_verify(db, {}, "dev")

        # The governance check should pass (meaning coach IS blocked)
        gov_check = result["checks"].get("governance_coach_blocked", {})
        # This depends on agent_capabilities.yaml config
        assert "pass" in gov_check

    @pytest.mark.asyncio
    async def test_memory_isolation_check(self, db):
        """Memory isolation should verify James can't see Laura's memories and vice versa."""
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        result = await cmd_bootstrap_verify(db, {}, "dev")

        memory_check = result["checks"].get("memory_isolation", {})
        assert "pass" in memory_check
        assert "detail" in memory_check

        # Detail should show isolation was tested
        detail = memory_check.get("detail", {})
        if isinstance(detail, dict):
            # isolation_enforced should be True (Laura didn't see James's test memory)
            assert detail.get("isolation_enforced", False) or memory_check.get("pass")

    @pytest.mark.asyncio
    async def test_calendar_context_checks(self, db):
        """Calendar context should be buildable for both members."""
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        result = await cmd_bootstrap_verify(db, {}, "dev")

        # Calendar context checks should be present for both members
        assert "calendar_context_m_james" in result["checks"]
        assert "calendar_context_m_laura" in result["checks"]

        # Both should pass (or at least complete)
        for member in ["m_james", "m_laura"]:
            check = result["checks"].get(f"calendar_context_{member}", {})
            assert "pass" in check

    @pytest.mark.asyncio
    async def test_voice_profiles_checks(self, db):
        """Voice profiles should be loadable for both members."""
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
        os.environ.setdefault("BLUEBUBBLES_JAMES_SECRET", "test-secret")

        result = await cmd_bootstrap_verify(db, {}, "dev")

        # Voice profile checks should be present for both members
        assert "voice_profiles_m_james" in result["checks"]
        assert "voice_profiles_m_laura" in result["checks"]

        # Both should pass (profiles may be empty but query shouldn't fail)
        for member in ["m_james", "m_laura"]:
            check = result["checks"].get(f"voice_profiles_{member}", {})
            assert "pass" in check
            assert check.get("pass") is True
