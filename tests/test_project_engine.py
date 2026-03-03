"""Tests for project execution engine."""

import json

import pytest

from pib.project.engine import advance_project, on_task_completed


# ─── Helper: seed a project with phases and steps into the DB ───

async def _seed_project(db, project_id="proj-00100", status="active", phases=None):
    """Insert a test project with phases and steps."""
    await db.execute(
        """INSERT INTO proj_projects
           (id, title, brief, status, requested_by,
            risk_financial, risk_reputational, risk_technical,
            can_spend, can_email_strangers, can_sms_strangers, can_call_strangers,
            created_at, updated_at)
           VALUES (?,?,?,?,?, ?,?,?, ?,?,?,?, datetime('now'), datetime('now'))""",
        [project_id, "Test Project", "A test brief", status, "m-james",
         "low", "low", "none", 1, 1, 1, 0],
    )

    if phases is None:
        phases = [
            {
                "id": "phase-00100",
                "number": 1,
                "title": "Research",
                "status": "pending",
                "steps": [
                    {"id": "step-00100", "number": 1, "title": "Web search", "type": "auto",
                     "executor": "pib", "tool_hint": "web_search", "status": "pending"},
                    {"id": "step-00101", "number": 2, "title": "Compile", "type": "auto",
                     "executor": "pib", "tool_hint": "compile", "status": "pending"},
                ],
            },
            {
                "id": "phase-00101",
                "number": 2,
                "title": "Human Review",
                "status": "pending",
                "steps": [
                    {"id": "step-00102", "number": 1, "title": "Review results", "type": "human",
                     "executor": "james", "tool_hint": "none", "status": "pending"},
                ],
            },
            {
                "id": "phase-00102",
                "number": 3,
                "title": "Final Review",
                "status": "pending",
                "steps": [
                    {"id": "step-00103", "number": 1, "title": "Close out", "type": "auto",
                     "executor": "pib", "tool_hint": "none", "status": "pending"},
                ],
            },
        ]

    for phase in phases:
        await db.execute(
            """INSERT INTO proj_phases (id, project_id, phase_number, title, description, status)
               VALUES (?,?,?,?,?,?)""",
            [phase["id"], project_id, phase["number"], phase["title"], "", phase["status"]],
        )
        for step in phase.get("steps", []):
            await db.execute(
                """INSERT INTO proj_steps
                   (id, phase_id, project_id, step_number, title, description,
                    step_type, status, executor, tool_hint)
                   VALUES (?,?,?,?,?,?, ?,?,?,?)""",
                [step["id"], phase["id"], project_id, step["number"],
                 step["title"], "", step["type"], step["status"],
                 step["executor"], step.get("tool_hint")],
            )

    await db.commit()


@pytest.mark.asyncio
class TestAdvanceProject:
    """Tests for advance_project()."""

    async def test_not_found(self, db):
        result = await advance_project(db, "proj-NONEXISTENT")
        assert result["status"] == "error"

    async def test_skips_non_active(self, db):
        await _seed_project(db, status="pending_approval")
        result = await advance_project(db, "proj-00100")
        assert result["status"] == "skipped"

    async def test_activates_pending_phase(self, db):
        """First advance should activate the first pending phase."""
        await _seed_project(db)
        result = await advance_project(db, "proj-00100")

        # Phase should be activated
        phase = await db.execute_fetchone(
            "SELECT * FROM proj_phases WHERE id = 'phase-00100'"
        )
        assert phase["status"] == "active"

    async def test_auto_step_executes(self, db):
        """An auto step should be marked active then completed/failed."""
        await _seed_project(db)
        result = await advance_project(db, "proj-00100")

        step = await db.execute_fetchone(
            "SELECT * FROM proj_steps WHERE id = 'step-00100'"
        )
        # Step should be completed or failed (auto execution may fail without real API, that's ok)
        assert step["status"] in ("completed", "failed")

    async def test_human_step_creates_task(self, db):
        """A human step should create an ops_task and mark step waiting."""
        # Set up with phase 1 completed so engine moves to phase 2 (human step)
        await _seed_project(db, phases=[
            {
                "id": "phase-00100",
                "number": 1,
                "title": "Human Phase",
                "status": "active",
                "steps": [
                    {"id": "step-00100", "number": 1, "title": "Do something physically",
                     "type": "human", "executor": "james", "tool_hint": "none", "status": "pending"},
                ],
            },
            {
                "id": "phase-00101",
                "number": 2,
                "title": "Final Review",
                "status": "pending",
                "steps": [
                    {"id": "step-00101", "number": 1, "title": "Close out", "type": "auto",
                     "executor": "pib", "tool_hint": "none", "status": "pending"},
                ],
            },
        ])

        result = await advance_project(db, "proj-00100")
        assert result["action_taken"] == "create_task"

        # Check step is waiting
        step = await db.execute_fetchone("SELECT * FROM proj_steps WHERE id = 'step-00100'")
        assert step["status"] == "waiting"

        # Check ops_task was created with project_ref
        task = await db.execute_fetchone(
            "SELECT * FROM ops_tasks WHERE project_ref = 'proj-00100'"
        )
        assert task is not None
        assert task["project_step_ref"] == "step-00100"

    async def test_gate_step_creates_gate(self, db):
        """A gate-type step should create a proj_gate and block advancement."""
        await _seed_project(db, phases=[
            {
                "id": "phase-00100",
                "number": 1,
                "title": "Decision Phase",
                "status": "active",
                "steps": [
                    {"id": "step-00100", "number": 1, "title": "Choose an option",
                     "type": "gate", "executor": "pib", "tool_hint": "none", "status": "pending"},
                ],
            },
            {
                "id": "phase-00101",
                "number": 2,
                "title": "Final Review",
                "status": "pending",
                "steps": [
                    {"id": "step-00101", "number": 1, "title": "Close out", "type": "auto",
                     "executor": "pib", "tool_hint": "none", "status": "pending"},
                ],
            },
        ])

        result = await advance_project(db, "proj-00100")
        assert result["action_taken"] == "create_gate"
        assert result["status"] == "gate_waiting"

        # Check gate was created
        gate = await db.execute_fetchone(
            "SELECT * FROM proj_gates WHERE project_id = 'proj-00100' AND after_step_id = 'step-00100'"
        )
        assert gate is not None
        assert gate["status"] == "waiting"

    async def test_failed_step_goes_to_dead_letter(self, db):
        """A step failure should NOT crash the project — should be in dead letter."""
        # We'll use an auto step that will fail because the tool execution
        # encounters an error (no real API available)
        await _seed_project(db)
        result = await advance_project(db, "proj-00100")

        # If the step failed, check dead letter
        step = await db.execute_fetchone("SELECT * FROM proj_steps WHERE id = 'step-00100'")
        if step["status"] == "failed":
            dl = await db.execute_fetchone(
                "SELECT * FROM common_dead_letter WHERE operation LIKE '%step-00100%'"
            )
            assert dl is not None

    async def test_approved_project_activates(self, db):
        """A project with status 'approved' should get activated."""
        await _seed_project(db, status="approved")
        result = await advance_project(db, "proj-00100")

        proj = await db.execute_fetchone("SELECT * FROM proj_projects WHERE id = 'proj-00100'")
        assert proj["status"] == "active"


@pytest.mark.asyncio
class TestOnTaskCompleted:
    """Tests for on_task_completed() integration hook."""

    async def test_marks_step_completed(self, db):
        """Completing a linked task should complete the project step."""
        await _seed_project(db, phases=[
            {
                "id": "phase-00100",
                "number": 1,
                "title": "Human Phase",
                "status": "active",
                "steps": [
                    {"id": "step-00100", "number": 1, "title": "Human action",
                     "type": "human", "executor": "james", "tool_hint": "none", "status": "pending"},
                ],
            },
            {
                "id": "phase-00101",
                "number": 2,
                "title": "Final Review",
                "status": "pending",
                "steps": [
                    {"id": "step-00101", "number": 1, "title": "Close out", "type": "auto",
                     "executor": "pib", "tool_hint": "none", "status": "pending"},
                ],
            },
        ])

        # First advance creates the human task
        result = await advance_project(db, "proj-00100")
        assert result["action_taken"] == "create_task"
        task_id = result["task_id"]

        # Simulate task completion
        await db.execute(
            "UPDATE ops_tasks SET status = 'done' WHERE id = ?", [task_id]
        )
        await db.commit()

        # Call the hook
        await on_task_completed(db, task_id)

        # Step should be completed
        step = await db.execute_fetchone("SELECT * FROM proj_steps WHERE id = 'step-00100'")
        assert step["status"] == "completed"

    async def test_no_linked_step_is_noop(self, db):
        """on_task_completed with a non-project task should be a no-op."""
        await on_task_completed(db, "tsk-NONEXISTENT")
        # No error raised — just a no-op
