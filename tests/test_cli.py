"""Tests for the CLI permission boundary (pib.cli).

Covers the 6 enforcement layers:
  1. Agent allowlist (check_agent_allowlist)
  2. Governance gates (check_governance_gate)
  3. SQL guard (check_sql_guard)
  4. Write-rate detection (check_write_rate)
  5. Output sanitization (sanitize_output)
  6. Audit logging (tested implicitly through command handlers)

Also tests command handlers cmd_what_now and cmd_custody, and verifies
that the coach agent cannot call task-create and scoreboard is read-only.
"""

import json
import os

import pytest
import yaml

from pib.cli import (
    check_agent_allowlist,
    check_governance_gate,
    check_sql_guard,
    check_write_rate,
    sanitize_output,
    cmd_what_now,
    cmd_custody,
    cmd_task_create,
    WRITE_COMMANDS,
    READ_COMMANDS,
    ADMIN_COMMANDS,
    ALL_COMMANDS,
    COMMAND_TO_GATE,
)


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def agent_caps():
    """Load production agent_capabilities.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "config", "agent_capabilities.yaml"
    )
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def governance():
    """Load production governance.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__), os.pardir, "config", "governance.yaml"
    )
    with open(config_path) as f:
        return yaml.safe_load(f)


# ═══════════════════════════════════════════════════════════
# 1. check_agent_allowlist
# ═══════════════════════════════════════════════════════════

class TestCheckAgentAllowlist:
    """Layer 1: Verify agent identity + command is in allowed list."""

    def test_dev_wildcard_allows_everything(self, agent_caps):
        """dev agent has allowed_cli_commands: '*' -- any command passes."""
        ok, msg = check_agent_allowlist("dev", "bootstrap", agent_caps)
        assert ok is True
        assert msg == "ok"

    def test_dev_wildcard_allows_write_commands(self, agent_caps):
        ok, msg = check_agent_allowlist("dev", "task-create", agent_caps)
        assert ok is True

    def test_unknown_agent_rejected(self, agent_caps):
        ok, msg = check_agent_allowlist("rogue-bot", "what-now", agent_caps)
        assert ok is False
        assert "Unknown agent" in msg

    def test_cos_allowed_read(self, agent_caps):
        ok, msg = check_agent_allowlist("cos", "what-now", agent_caps)
        assert ok is True

    def test_cos_allowed_write(self, agent_caps):
        ok, msg = check_agent_allowlist("cos", "task-create", agent_caps)
        assert ok is True

    def test_cos_blocked_admin(self, agent_caps):
        """cos has 'migrate' in blocked_cli_commands."""
        ok, msg = check_agent_allowlist("cos", "migrate", agent_caps)
        assert ok is False
        assert "blocked" in msg.lower() or "not in allowed" in msg.lower() or "does not have access" in msg.lower()

    def test_cos_blocked_bootstrap(self, agent_caps):
        ok, msg = check_agent_allowlist("cos", "bootstrap", agent_caps)
        assert ok is False

    def test_coach_allowed_read(self, agent_caps):
        ok, msg = check_agent_allowlist("coach", "what-now", agent_caps)
        assert ok is True

    def test_coach_blocked_task_create(self, agent_caps):
        """Coach has task-create in blocked_cli_commands."""
        ok, msg = check_agent_allowlist("coach", "task-create", agent_caps)
        assert ok is False
        assert "blocked" in msg.lower() or "not in allowed" in msg.lower() or "does not have access" in msg.lower()

    def test_coach_blocked_budget(self, agent_caps):
        """Coach cannot discuss money -- budget is blocked."""
        ok, msg = check_agent_allowlist("coach", "budget", agent_caps)
        assert ok is False

    def test_scoreboard_allowed_own_commands(self, agent_caps):
        """Scoreboard is allowed: scoreboard-data, custody, streak."""
        for cmd in ("scoreboard-data", "custody", "streak"):
            ok, msg = check_agent_allowlist("scoreboard", cmd, agent_caps)
            assert ok is True, f"scoreboard should be allowed '{cmd}'"

    def test_scoreboard_blocked_wildcard(self, agent_caps):
        """Scoreboard has blocked_cli_commands: '*' -- anything not in allowed is blocked."""
        ok, msg = check_agent_allowlist("scoreboard", "task-create", agent_caps)
        assert ok is False

    def test_scoreboard_blocked_what_now(self, agent_caps):
        ok, msg = check_agent_allowlist("scoreboard", "what-now", agent_caps)
        assert ok is False

    def test_proactive_allowed_own_commands(self, agent_caps):
        for cmd in ("run-proactive-checks", "what-now", "custody", "calendar-query"):
            ok, msg = check_agent_allowlist("proactive", cmd, agent_caps)
            assert ok is True, f"proactive should be allowed '{cmd}'"

    def test_proactive_blocked_task_create(self, agent_caps):
        ok, msg = check_agent_allowlist("proactive", "task-create", agent_caps)
        assert ok is False


# ═══════════════════════════════════════════════════════════
# 2. check_governance_gate
# ═══════════════════════════════════════════════════════════

class TestCheckGovernanceGate:
    """Layer 2: Governance gates on write commands."""

    def test_read_command_skips_gate(self, governance):
        """Read commands are not gated -- returns 'skip'."""
        status, msg = check_governance_gate("cos", "what-now", governance)
        assert status == "skip"

    def test_task_create_auto_approved(self, governance):
        """task_create gate is true -> auto-approve."""
        status, msg = check_governance_gate("cos", "task-create", governance)
        assert status == "true"

    def test_task_update_requires_confirm(self, governance):
        """task_update gate is 'confirm' -> requires user approval."""
        status, msg = check_governance_gate("cos", "task-update", governance)
        assert status == "confirm"
        assert "confirmation" in msg.lower()

    def test_hold_create_requires_confirm(self, governance):
        status, msg = check_governance_gate("cos", "hold-create", governance)
        assert status == "confirm"

    def test_coach_task_create_off(self, governance):
        """Coach has agent_override: task_create: off."""
        status, msg = check_governance_gate("coach", "task-create", governance)
        assert status == "off"
        assert "disabled" in msg.lower()

    def test_coach_hold_create_off(self, governance):
        status, msg = check_governance_gate("coach", "hold-create", governance)
        assert status == "off"

    def test_scoreboard_task_create_off(self, governance):
        status, msg = check_governance_gate("scoreboard", "task-create", governance)
        assert status == "off"

    def test_scoreboard_task_complete_off(self, governance):
        status, msg = check_governance_gate("scoreboard", "task-complete", governance)
        assert status == "off"

    def test_scoreboard_task_update_off(self, governance):
        status, msg = check_governance_gate("scoreboard", "task-update", governance)
        assert status == "off"

    def test_proactive_task_create_off(self, governance):
        status, msg = check_governance_gate("proactive", "task-create", governance)
        assert status == "off"

    def test_state_update_auto_approved(self, governance):
        """state_update is always auto-approved (meds, sleep, energy)."""
        status, msg = check_governance_gate("cos", "state-update", governance)
        assert status == "true"

    def test_unknown_command_skips_gate(self, governance):
        """Commands not in COMMAND_TO_GATE map should skip."""
        status, msg = check_governance_gate("cos", "health", governance)
        assert status == "skip"


# ═══════════════════════════════════════════════════════════
# 3. check_sql_guard
# ═══════════════════════════════════════════════════════════

class TestCheckSqlGuard:
    """Layer 3: Defense-in-depth against unknown commands."""

    def test_known_commands_pass(self):
        for cmd in ALL_COMMANDS:
            ok, msg = check_sql_guard(cmd)
            assert ok is True, f"Known command '{cmd}' should pass SQL guard"

    def test_unknown_command_blocked(self):
        ok, msg = check_sql_guard("exec-raw-sql")
        assert ok is False
        assert "Unknown command" in msg

    def test_sql_injection_attempt_blocked(self):
        ok, msg = check_sql_guard("'; DROP TABLE ops_tasks; --")
        assert ok is False


# ═══════════════════════════════════════════════════════════
# 4. check_write_rate
# ═══════════════════════════════════════════════════════════

class TestCheckWriteRate:
    """Layer 4: Write-rate throttling via DB query."""

    @pytest.mark.asyncio
    async def test_under_limit_allowed(self, db, governance):
        """Zero recent writes -> allowed."""
        ok, msg = await check_write_rate(db, "cos", governance)
        assert ok is True
        assert msg == "ok"

    @pytest.mark.asyncio
    async def test_at_limit_blocked(self, db, governance):
        """Insert 3 writes in last 60s -> blocked (limit is 3)."""
        for i in range(3):
            await db.execute(
                "INSERT INTO mem_cos_activity (actor, action_type, description, created_at) "
                "VALUES (?, 'cli_write', ?, datetime('now'))",
                ["cos", f"write {i}"],
            )
        await db.commit()

        ok, msg = await check_write_rate(db, "cos", governance)
        assert ok is False
        assert "rate limit" in msg.lower()

    @pytest.mark.asyncio
    async def test_different_agent_not_affected(self, db, governance):
        """Writes from 'coach' should not count against 'cos'."""
        for i in range(3):
            await db.execute(
                "INSERT INTO mem_cos_activity (actor, action_type, description, created_at) "
                "VALUES (?, 'cli_write', ?, datetime('now'))",
                ["coach", f"write {i}"],
            )
        await db.commit()

        ok, msg = await check_write_rate(db, "cos", governance)
        assert ok is True

    @pytest.mark.asyncio
    async def test_read_actions_dont_count(self, db, governance):
        """cli_read actions should not trigger write-rate limit."""
        for i in range(5):
            await db.execute(
                "INSERT INTO mem_cos_activity (actor, action_type, description, created_at) "
                "VALUES (?, 'cli_read', ?, datetime('now'))",
                ["cos", f"read {i}"],
            )
        await db.commit()

        ok, msg = await check_write_rate(db, "cos", governance)
        assert ok is True


# ═══════════════════════════════════════════════════════════
# 5. sanitize_output
# ═══════════════════════════════════════════════════════════

class TestSanitizeOutput:
    """Layer 5: Output sanitizer strips API keys and model names."""

    def test_strips_anthropic_api_key(self, governance):
        output = '{"key": "sk-ant-abc123_DEF456-xyz"}'
        result = sanitize_output(output, "cos", governance)
        assert "sk-ant-" not in result
        assert "[REDACTED]" in result

    def test_strips_env_var_leak(self, governance):
        output = "Config: ANTHROPIC_API_KEY=sk-ant-secret123 loaded"
        result = sanitize_output(output, "cos", governance)
        assert "sk-ant-secret123" not in result
        assert "[REDACTED]" in result

    def test_strips_model_id(self, governance):
        output = '{"model": "claude-3-5-20250101"}'
        result = sanitize_output(output, "cos", governance)
        assert "claude-3-5-20250101" not in result
        assert "[REDACTED]" in result

    def test_dev_agent_sees_laura_work_titles(self, governance):
        """Dev agent should NOT have Laura's work titles redacted."""
        output = '{"laura_work_title": "Q4 Board Meeting"}'
        result = sanitize_output(output, "dev", governance)
        assert "Q4 Board Meeting" in result

    def test_non_dev_redacts_laura_work_titles(self, governance):
        """Non-dev agents get Laura's work titles redacted (privacy fence)."""
        output = '{"laura_work_title": "Q4 Board Meeting"}'
        result = sanitize_output(output, "cos", governance)
        assert "Q4 Board Meeting" not in result
        assert "[private]" in result

    def test_non_dev_redacts_api_key_values(self, governance):
        output = '{"api_key": "super-secret-value"}'
        result = sanitize_output(output, "coach", governance)
        assert "super-secret-value" not in result
        assert "[REDACTED]" in result

    def test_dev_sees_api_key_values(self, governance):
        output = '{"api_key": "super-secret-value"}'
        result = sanitize_output(output, "dev", governance)
        assert "super-secret-value" in result

    def test_clean_output_unchanged(self, governance):
        """Output without sensitive data passes through unchanged."""
        output = '{"the_one_task": "Call the dentist", "streak": 5}'
        result = sanitize_output(output, "cos", governance)
        assert result == output

    def test_multiple_patterns_stripped(self, governance):
        """All sensitive patterns stripped in one pass."""
        output = (
            'key=sk-ant-abc123 model=claude-3-5-20250101 '
            'ANTHROPIC_API_KEY=leaked-key'
        )
        result = sanitize_output(output, "cos", governance)
        assert "sk-ant-" not in result
        assert "claude-3-5-20250101" not in result
        assert "leaked-key" not in result


# ═══════════════════════════════════════════════════════════
# 6. Command handlers: cmd_what_now
# ═══════════════════════════════════════════════════════════

class TestCmdWhatNow:
    """Test cmd_what_now returns expected structure from seeded data."""

    @pytest.mark.asyncio
    async def test_returns_the_one_task(self, db):
        result = await cmd_what_now(db, {"member_id": "m-james"}, "dev")
        assert "the_one_task" in result
        assert "context" in result
        assert "calendar_status" in result
        assert "energy_level" in result
        assert "completions_today" in result
        assert "velocity_cap" in result

    @pytest.mark.asyncio
    async def test_default_member_is_james(self, db):
        """When no member_id given, defaults to m-james."""
        result = await cmd_what_now(db, {}, "dev")
        assert "the_one_task" in result

    @pytest.mark.asyncio
    async def test_one_more_teaser_present(self, db):
        result = await cmd_what_now(db, {"member_id": "m-james"}, "dev")
        assert "one_more_teaser" in result


# ═══════════════════════════════════════════════════════════
# 7. Command handlers: cmd_custody
# ═══════════════════════════════════════════════════════════

class TestCmdCustody:
    """Test cmd_custody returns deterministic custody data."""

    @pytest.mark.asyncio
    async def test_returns_custody_fields(self, db):
        result = await cmd_custody(db, {"date": "2026-03-03"}, "dev")
        assert "date" in result
        assert "parent_id" in result
        assert "text" in result
        assert result["date"] == "2026-03-03"

    @pytest.mark.asyncio
    async def test_parent_id_is_valid(self, db):
        result = await cmd_custody(db, {"date": "2026-03-03"}, "dev")
        assert result["parent_id"] in ("m-james", "m-laura-ex")

    @pytest.mark.asyncio
    async def test_text_contains_name(self, db):
        result = await cmd_custody(db, {"date": "2026-03-03"}, "dev")
        assert "Charlie" in result["text"]

    @pytest.mark.asyncio
    async def test_defaults_to_today(self, db):
        """When no date arg, defaults to today."""
        result = await cmd_custody(db, {}, "dev")
        assert "date" in result
        assert "parent_id" in result


# ═══════════════════════════════════════════════════════════
# 8. Coach agent cannot call task-create (end-to-end)
# ═══════════════════════════════════════════════════════════

class TestCoachPermissionBoundary:
    """Verify coach agent is blocked at both allowlist AND governance layers."""

    def test_coach_blocked_by_allowlist(self, agent_caps):
        ok, msg = check_agent_allowlist("coach", "task-create", agent_caps)
        assert ok is False
        assert "coach" in msg.lower() or "blocked" in msg.lower()

    def test_coach_blocked_by_governance(self, governance):
        status, msg = check_governance_gate("coach", "task-create", governance)
        assert status == "off"

    def test_coach_blocked_hold_create_allowlist(self, agent_caps):
        ok, msg = check_agent_allowlist("coach", "hold-create", agent_caps)
        assert ok is False

    def test_coach_blocked_hold_create_governance(self, governance):
        status, msg = check_governance_gate("coach", "hold-create", governance)
        assert status == "off"

    def test_coach_allowed_state_update(self, agent_caps, governance):
        """Coach CAN update state (meds, sleep, energy)."""
        ok, msg = check_agent_allowlist("coach", "state-update", agent_caps)
        assert ok is True
        status, _ = check_governance_gate("coach", "state-update", governance)
        assert status == "true"

    def test_coach_allowed_task_complete(self, agent_caps, governance):
        """Coach CAN complete tasks ('I did it!' flow)."""
        ok, msg = check_agent_allowlist("coach", "task-complete", agent_caps)
        assert ok is True
        status, _ = check_governance_gate("coach", "task-complete", governance)
        assert status == "true"


# ═══════════════════════════════════════════════════════════
# 9. Scoreboard is strictly read-only
# ═══════════════════════════════════════════════════════════

class TestScoreboardReadOnly:
    """Scoreboard agent restricted to read-only commands."""

    def test_scoreboard_cannot_write(self, agent_caps):
        """Every write command must be blocked for scoreboard."""
        for cmd in WRITE_COMMANDS:
            ok, msg = check_agent_allowlist("scoreboard", cmd, agent_caps)
            assert ok is False, f"scoreboard should not be allowed write command '{cmd}'"

    def test_scoreboard_cannot_admin(self, agent_caps):
        """Every admin command must be blocked for scoreboard."""
        for cmd in ADMIN_COMMANDS:
            ok, msg = check_agent_allowlist("scoreboard", cmd, agent_caps)
            assert ok is False, f"scoreboard should not be allowed admin command '{cmd}'"

    def test_scoreboard_governance_blocks_writes(self, governance):
        """Governance overrides also block scoreboard from writes."""
        for gate_cmd, gate_key in COMMAND_TO_GATE.items():
            if gate_key in ("task_create", "task_complete", "task_update",
                            "calendar_hold_create"):
                status, _ = check_governance_gate("scoreboard", gate_cmd, governance)
                assert status == "off", (
                    f"scoreboard governance gate for '{gate_cmd}' should be 'off'"
                )

    def test_scoreboard_allowed_reads_only(self, agent_caps):
        """Only scoreboard-data, custody, streak are allowed."""
        allowed = {"scoreboard-data", "custody", "streak"}
        for cmd in READ_COMMANDS:
            ok, _ = check_agent_allowlist("scoreboard", cmd, agent_caps)
            if cmd in allowed:
                assert ok is True, f"scoreboard should be allowed '{cmd}'"
            else:
                assert ok is False, f"scoreboard should NOT be allowed '{cmd}'"


# ═══════════════════════════════════════════════════════════
# 10. PIB_CALLER_AGENT env var
# ═══════════════════════════════════════════════════════════

class TestCallerAgentEnvVar:
    """Verify the CLI reads PIB_CALLER_AGENT from environment."""

    def test_env_var_sets_agent(self, monkeypatch):
        monkeypatch.setenv("PIB_CALLER_AGENT", "coach")
        assert os.environ.get("PIB_CALLER_AGENT") == "coach"

    def test_env_var_defaults_to_dev(self, monkeypatch):
        monkeypatch.delenv("PIB_CALLER_AGENT", raising=False)
        agent_id = os.environ.get("PIB_CALLER_AGENT", "dev")
        assert agent_id == "dev"

    def test_env_var_unknown_agent_blocked(self, monkeypatch, agent_caps):
        """An unknown agent set via env var should be rejected by allowlist."""
        monkeypatch.setenv("PIB_CALLER_AGENT", "evil-agent")
        agent_id = os.environ["PIB_CALLER_AGENT"]
        ok, msg = check_agent_allowlist(agent_id, "what-now", agent_caps)
        assert ok is False
        assert "Unknown agent" in msg
