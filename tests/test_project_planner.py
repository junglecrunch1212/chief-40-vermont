"""Tests for project planner: validation and persistence."""

import json

import pytest
import pytest_asyncio

from pib.project.planner import _validate_plan, _persist_plan, _safe_json_parse


# ─── Valid plan fixture ───

VALID_PLAN = {
    "title": "Find Piano Teacher for Charlie",
    "phases": [
        {
            "title": "Research Local Teachers",
            "description": "Search for piano teachers in Atlanta area",
            "gate_after": "none",
            "steps": [
                {"title": "Web search for piano teachers", "step_type": "auto", "executor": "pib", "tool_hint": "web_search", "estimated_minutes": 15},
                {"title": "Compile findings", "step_type": "auto", "executor": "pib", "tool_hint": "compile", "estimated_minutes": 10},
            ],
        },
        {
            "title": "Compare and Select",
            "description": "Present options for review",
            "gate_after": "approve",
            "gate_description": "Choose a teacher to contact",
            "steps": [
                {"title": "Present comparison", "step_type": "gate", "executor": "pib", "tool_hint": "none", "estimated_minutes": 5},
            ],
        },
        {
            "title": "Contact and Schedule",
            "description": "Reach out and book a trial lesson",
            "gate_after": "confirm",
            "gate_description": "Confirm booking",
            "steps": [
                {"title": "Send inquiry email", "step_type": "draft", "executor": "pib", "tool_hint": "gmail_send", "estimated_minutes": 10},
                {"title": "Wait for reply", "step_type": "wait", "executor": "external", "tool_hint": "none", "estimated_minutes": 1440},
            ],
        },
        {
            "title": "Close-out and Review",
            "description": "Finalize and archive results",
            "gate_after": "none",
            "steps": [
                {"title": "Summarize results", "step_type": "auto", "executor": "pib", "tool_hint": "none", "estimated_minutes": 5},
            ],
        },
    ],
    "risk_financial": "low",
    "risk_reputational": "low",
    "risk_technical": "none",
    "suggested_permissions": ["can_email_strangers"],
    "estimated_duration_days": 14,
}


class TestValidatePlan:
    """Tests for _validate_plan()."""

    def test_valid_plan_passes(self):
        errors = _validate_plan(VALID_PLAN)
        assert errors == []

    def test_no_phases_fails(self):
        errors = _validate_plan({"title": "Bad Plan", "phases": []})
        assert any("no phases" in e for e in errors)

    def test_single_phase_fails(self):
        plan = {
            "title": "Too Simple",
            "phases": [
                {"title": "Do everything", "gate_after": "approve", "steps": [
                    {"title": "One step", "step_type": "auto", "executor": "pib"},
                ]},
            ],
        }
        errors = _validate_plan(plan)
        assert any("minimum is 2" in e for e in errors)

    def test_too_many_phases_fails(self):
        phases = [
            {"title": f"Phase {i}", "gate_after": "none", "steps": [
                {"title": "Step", "step_type": "auto", "executor": "pib"}
            ]} for i in range(11)
        ]
        # Add approve gate to first phase to avoid that error
        phases[0]["gate_after"] = "approve"
        phases[-1]["title"] = "Final Review"
        errors = _validate_plan({"title": "Too Many", "phases": phases})
        assert any("maximum is 10" in e for e in errors)

    def test_no_gate_fails(self):
        plan = {
            "title": "Ungated",
            "phases": [
                {"title": "Research", "gate_after": "none", "steps": [
                    {"title": "Search", "step_type": "auto", "executor": "pib"},
                ]},
                {"title": "Final Review", "gate_after": "none", "steps": [
                    {"title": "Done", "step_type": "auto", "executor": "pib"},
                ]},
            ],
        }
        errors = _validate_plan(plan)
        assert any("no confirm/approve gate" in e for e in errors)

    def test_invalid_step_type_fails(self):
        plan = {
            "title": "Bad Type",
            "phases": [
                {"title": "Phase 1", "gate_after": "approve", "steps": [
                    {"title": "Bad step", "step_type": "INVALID", "executor": "pib"},
                ]},
                {"title": "Final Review", "gate_after": "none", "steps": [
                    {"title": "Done", "step_type": "auto", "executor": "pib"},
                ]},
            ],
        }
        errors = _validate_plan(plan)
        assert any("invalid type: INVALID" in e for e in errors)

    def test_invalid_executor_fails(self):
        plan = {
            "title": "Bad Executor",
            "phases": [
                {"title": "Phase 1", "gate_after": "approve", "steps": [
                    {"title": "Bad step", "step_type": "auto", "executor": "NOBODY"},
                ]},
                {"title": "Final Review", "gate_after": "none", "steps": [
                    {"title": "Done", "step_type": "auto", "executor": "pib"},
                ]},
            ],
        }
        errors = _validate_plan(plan)
        assert any("invalid executor: NOBODY" in e for e in errors)

    def test_last_phase_must_be_closeout(self):
        plan = {
            "title": "No Closeout",
            "phases": [
                {"title": "Research", "gate_after": "approve", "steps": [
                    {"title": "Search", "step_type": "auto", "executor": "pib"},
                ]},
                {"title": "Execute More Stuff", "gate_after": "none", "steps": [
                    {"title": "Done", "step_type": "auto", "executor": "pib"},
                ]},
            ],
        }
        errors = _validate_plan(plan)
        assert any("close-out phase" in e for e in errors)

    def test_gate_step_type_counts_as_gate(self):
        """A step with step_type='gate' should satisfy the gate requirement."""
        plan = {
            "title": "Gate Step",
            "phases": [
                {"title": "Phase 1", "gate_after": "none", "steps": [
                    {"title": "Decision point", "step_type": "gate", "executor": "pib"},
                ]},
                {"title": "Final Review", "gate_after": "none", "steps": [
                    {"title": "Done", "step_type": "auto", "executor": "pib"},
                ]},
            ],
        }
        errors = _validate_plan(plan)
        # Should not have the "no confirm/approve gate" error
        assert not any("no confirm/approve gate" in e for e in errors)


class TestSafeJsonParse:
    """Tests for _safe_json_parse()."""

    def test_plain_json(self):
        result = _safe_json_parse('{"title": "Test"}')
        assert result["title"] == "Test"

    def test_markdown_fenced_json(self):
        text = '```json\n{"title": "Fenced"}\n```'
        result = _safe_json_parse(text)
        assert result["title"] == "Fenced"

    def test_invalid_json_fallback(self):
        result = _safe_json_parse("This is not JSON at all")
        assert result["title"] == "Untitled Project"
        assert len(result["phases"]) >= 1


@pytest.mark.asyncio
class TestPersistPlan:
    """Tests for _persist_plan() with in-memory SQLite."""

    async def test_persist_creates_rows(self, db):
        await _persist_plan(db, "proj-00100", "Find a piano teacher", VALID_PLAN, "m-james")
        await db.commit()

        # Check project row
        proj = await db.execute_fetchone("SELECT * FROM proj_projects WHERE id = 'proj-00100'")
        assert proj is not None
        assert proj["title"] == "Find Piano Teacher for Charlie"
        assert proj["status"] == "pending_approval"
        assert proj["requested_by"] == "m-james"
        assert proj["can_email_strangers"] == 1

        # Check phases
        phases = await db.execute_fetchall(
            "SELECT * FROM proj_phases WHERE project_id = 'proj-00100' ORDER BY phase_number"
        )
        assert len(phases) == 4

        # Check steps
        steps = await db.execute_fetchall(
            "SELECT * FROM proj_steps WHERE project_id = 'proj-00100' ORDER BY phase_id, step_number"
        )
        assert len(steps) == 6  # 2 + 1 + 2 + 1

        # Check gates (approve + confirm = 2 gates created)
        gates = await db.execute_fetchall(
            "SELECT * FROM proj_gates WHERE project_id = 'proj-00100'"
        )
        assert len(gates) == 2  # approve and confirm gates

    async def test_persist_gate_behaviors(self, db):
        await _persist_plan(db, "proj-00101", "Test gates", VALID_PLAN, "m-james")
        await db.commit()

        gates = await db.execute_fetchall(
            "SELECT * FROM proj_gates WHERE project_id = 'proj-00101' ORDER BY created_at"
        )
        behaviors = [g["behavior"] for g in gates]
        assert "approve" in behaviors
        assert "confirm" in behaviors
