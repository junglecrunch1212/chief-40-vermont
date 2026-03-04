"""Project execution engine: state machine for advancing projects step-by-step."""

import json
import logging
from datetime import datetime

from pib.db import audit_log, next_id
from pib.tz import now_et

log = logging.getLogger(__name__)


async def advance_project(db, project_id: str) -> dict:
    """Main entry point: advance a project by executing its next step.

    Called by cron every 5 minutes and after gate approvals.
    Returns {status, action_taken, details}.
    """
    project = await db.execute_fetchone(
        "SELECT * FROM proj_projects WHERE id = ?", [project_id]
    )
    if not project:
        return {"status": "error", "action_taken": "none", "details": "Project not found"}

    project = dict(project)

    if project["status"] not in ("active", "approved"):
        return {"status": "skipped", "action_taken": "none", "details": f"Project status is {project['status']}"}

    # If just approved, activate it
    if project["status"] == "approved":
        await _activate_project(db, project_id)
        project["status"] = "active"

    # Find current active phase, or activate the next pending one
    phase = await _get_or_activate_next_phase(db, project_id)
    if not phase:
        # All phases completed — try to complete the project
        await _try_complete_project(db, project_id)
        return {"status": "completing", "action_taken": "close_project", "details": "All phases done"}

    # Check for pending gates blocking this phase
    pending_gate = await db.execute_fetchone(
        """SELECT * FROM proj_gates
           WHERE project_id = ? AND after_phase_id = ? AND status IN ('pending', 'waiting')
           ORDER BY created_at LIMIT 1""",
        [project_id, phase["id"]],
    )
    if pending_gate and dict(pending_gate)["status"] == "waiting":
        return {"status": "blocked", "action_taken": "none", "details": f"Waiting for gate: {pending_gate['title']}"}

    # Find next executable step in current phase
    step = await _get_next_step(db, phase["id"])
    if not step:
        # All steps in this phase are done — complete the phase
        await _complete_phase(db, phase["id"])

        # Check if there's a gate after this phase that needs activation
        gate = await db.execute_fetchone(
            """SELECT * FROM proj_gates
               WHERE project_id = ? AND after_phase_id = ? AND status = 'pending'
               LIMIT 1""",
            [project_id, phase["id"]],
        )
        if gate:
            gate = dict(gate)
            if gate["behavior"] in ("confirm", "approve"):
                await db.execute(
                    "UPDATE proj_gates SET status = 'waiting' WHERE id = ?",
                    [gate["id"]],
                )
                await db.commit()
                return {
                    "status": "gate_waiting",
                    "action_taken": "activate_gate",
                    "details": f"Gate activated: {gate['title']}",
                    "gate_id": gate["id"],
                }
            elif gate["behavior"] == "inform":
                # Auto-approve inform gates
                await db.execute(
                    "UPDATE proj_gates SET status = 'approved', decided_at = ?, decision_notes = 'auto-inform' WHERE id = ?",
                    [now_et().isoformat(), gate["id"]],
                )
                await db.commit()

        # Try to move to next phase
        return await advance_project(db, project_id)

    step = dict(step)

    # Execute the step
    result = await _execute_step(db, project, step)
    return result


async def _get_or_activate_next_phase(db, project_id: str) -> dict | None:
    """Get the current active phase, or activate the next pending one."""
    # Check for active phase
    active = await db.execute_fetchone(
        "SELECT * FROM proj_phases WHERE project_id = ? AND status = 'active' ORDER BY phase_number LIMIT 1",
        [project_id],
    )
    if active:
        return dict(active)

    # Activate next pending phase
    pending = await db.execute_fetchone(
        "SELECT * FROM proj_phases WHERE project_id = ? AND status = 'pending' ORDER BY phase_number LIMIT 1",
        [project_id],
    )
    if pending:
        await _activate_phase(db, pending["id"])
        return dict(pending)

    return None


async def _get_next_step(db, phase_id: str) -> dict | None:
    """Get the next executable step in a phase."""
    # First check for any step that's currently active or waiting (don't skip it)
    active = await db.execute_fetchone(
        """SELECT * FROM proj_steps WHERE phase_id = ? AND status IN ('active', 'waiting')
           ORDER BY step_number LIMIT 1""",
        [phase_id],
    )
    if active:
        active = dict(active)
        if active["status"] == "waiting":
            return None  # Blocked on this step — don't advance
        return active

    # Find next pending step
    pending = await db.execute_fetchone(
        "SELECT * FROM proj_steps WHERE phase_id = ? AND status = 'pending' ORDER BY step_number LIMIT 1",
        [phase_id],
    )
    if not pending:
        return None

    pending = dict(pending)

    # Check dependencies
    if pending.get("depends_on"):
        dep_step = await db.execute_fetchone(
            "SELECT status FROM proj_steps WHERE id = ?", [pending["depends_on"]]
        )
        if dep_step and dep_step["status"] not in ("completed", "skipped"):
            return None  # Dependency not met

    return pending


async def _execute_step(db, project: dict, step: dict) -> dict:
    """Execute a single step based on its type."""
    step_type = step["step_type"]
    now = now_et().isoformat()

    # Mark step active
    await db.execute(
        "UPDATE proj_steps SET status = 'active', started_at = ? WHERE id = ?",
        [now, step["id"]],
    )
    await db.commit()

    try:
        if step_type == "human":
            return await _handle_human_step(db, project, step)
        elif step_type == "wait":
            return await _handle_wait_step(db, project, step)
        elif step_type == "gate":
            return await _handle_gate_step(db, project, step)
        elif step_type in ("auto", "draft"):
            return await _execute_auto_step(db, project, step)
        else:
            log.warning(f"Unknown step type: {step_type}")
            return await _execute_auto_step(db, project, step)

    except Exception as e:
        log.error(f"Step {step['id']} failed: {e}", exc_info=True)
        await _fail_step(db, step["id"], str(e), project["id"])
        return {"status": "failed", "action_taken": "fail_step", "details": str(e)}


async def _handle_human_step(db, project: dict, step: dict) -> dict:
    """Create an ops_task for a human step and mark step as waiting."""
    assignee = "m-james"
    if step.get("executor") == "laura":
        assignee = "m-laura"

    task_id = await next_id(db, "tsk")
    await db.execute(
        """INSERT INTO ops_tasks
           (id, title, status, assignee, domain, item_type,
            micro_script, created_by, source_system,
            project_ref, project_step_ref, notes)
           VALUES (?,?,?,?,?,?, ?,?,?, ?,?,?)""",
        [
            task_id,
            step["title"],
            "inbox",
            assignee,
            "projects",
            "task",
            step.get("description", ""),
            "project",
            "project_engine",
            project["id"],
            step["id"],
            f"Project: {project['title']}",
        ],
    )

    await db.execute(
        "UPDATE proj_steps SET status = 'waiting', task_ref = ? WHERE id = ?",
        [task_id, step["id"]],
    )
    await db.commit()

    return {
        "status": "waiting",
        "action_taken": "create_task",
        "details": f"Human task created: {step['title']}",
        "task_id": task_id,
    }


async def _handle_wait_step(db, project: dict, step: dict) -> dict:
    """Mark step as waiting for external input."""
    await db.execute(
        "UPDATE proj_steps SET status = 'waiting' WHERE id = ?",
        [step["id"]],
    )
    await db.commit()

    return {"status": "waiting", "action_taken": "wait", "details": f"Waiting: {step['title']}"}


async def _handle_gate_step(db, project: dict, step: dict) -> dict:
    """Create a gate for a gate-type step."""
    # Check if gate already exists for this step
    existing = await db.execute_fetchone(
        "SELECT * FROM proj_gates WHERE after_step_id = ?", [step["id"]]
    )
    if not existing:
        gate_id = await next_id(db, "gate")
        await db.execute(
            """INSERT INTO proj_gates
               (id, project_id, after_step_id, behavior, gate_type, title, description, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            [gate_id, project["id"], step["id"], "confirm", "decision",
             step["title"], step.get("description", ""), "waiting"],
        )
    else:
        gate_id = existing["id"]

    await db.execute(
        "UPDATE proj_steps SET status = 'waiting' WHERE id = ?",
        [step["id"]],
    )
    await db.commit()

    return {
        "status": "gate_waiting",
        "action_taken": "create_gate",
        "details": f"Gate created: {step['title']}",
        "gate_id": gate_id,
    }


async def _execute_auto_step(db, project: dict, step: dict) -> dict:
    """Execute an auto/draft step using the appropriate tool."""
    from pib.project.tools import dispatch_tool

    try:
        result = await dispatch_tool(db, project["id"], step, project)

        now = now_et().isoformat()

        # If the tool created a human task, mark step as waiting
        if result.get("data", {}).get("needs_human"):
            await db.execute(
                """UPDATE proj_steps SET status = 'waiting',
                   result_summary = ?, result_data = ?,
                   task_ref = ?
                   WHERE id = ?""",
                [result.get("summary", ""), json.dumps(result.get("data", {})),
                 result.get("data", {}).get("task_id"), step["id"]],
            )
        else:
            await db.execute(
                """UPDATE proj_steps SET status = 'completed', completed_at = ?,
                   result_summary = ?, result_data = ?
                   WHERE id = ?""",
                [now, result.get("summary", ""), json.dumps(result.get("data", {})), step["id"]],
            )

        await db.commit()

        return {
            "status": "completed" if not result.get("data", {}).get("needs_human") else "waiting",
            "action_taken": "execute_auto",
            "details": result.get("summary", "Step completed"),
        }

    except Exception as e:
        log.error(f"Auto step {step['id']} failed: {e}", exc_info=True)
        await _fail_step(db, step["id"], str(e), project["id"])
        return {"status": "failed", "action_taken": "fail_step", "details": str(e)}


# ─── State Transitions ───


async def _activate_project(db, project_id: str):
    """Set project to active status."""
    now = now_et().isoformat()
    await db.execute(
        "UPDATE proj_projects SET status = 'active', updated_at = ? WHERE id = ?",
        [now, project_id],
    )
    await audit_log(db, "proj_projects", "UPDATE", project_id, actor="engine", source="project_engine",
                    new_values=json.dumps({"status": "active"}))
    await db.commit()


async def _activate_phase(db, phase_id: str):
    """Set phase to active status."""
    now = now_et().isoformat()
    await db.execute(
        "UPDATE proj_phases SET status = 'active', started_at = ? WHERE id = ?",
        [now, phase_id],
    )
    await db.commit()


async def _complete_phase(db, phase_id: str):
    """Set phase to completed status."""
    now = now_et().isoformat()
    await db.execute(
        "UPDATE proj_phases SET status = 'completed', completed_at = ? WHERE id = ?",
        [now, phase_id],
    )
    await db.commit()


async def _try_complete_project(db, project_id: str):
    """Check if all phases are done and close the project."""
    remaining = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM proj_phases WHERE project_id = ? AND status NOT IN ('completed', 'skipped')",
        [project_id],
    )
    if remaining and remaining["c"] > 0:
        return

    # Check for any pending/waiting gates
    pending_gates = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM proj_gates WHERE project_id = ? AND status IN ('pending', 'waiting')",
        [project_id],
    )
    if pending_gates and pending_gates["c"] > 0:
        return

    await _close_project(db, project_id)


async def _close_project(db, project_id: str):
    """Close out a project: archive research, generate summary, mark completed."""
    now = now_et().isoformat()

    # Archive research to cap_captures (graceful — cap_captures may not exist)
    try:
        research_rows = await db.execute_fetchall(
            "SELECT title, content FROM proj_research WHERE project_id = ? AND research_type = 'comparison'",
            [project_id],
        )
        if research_rows:
            from pib.capture import create_capture
            project = await db.execute_fetchone(
                "SELECT title, requested_by FROM proj_projects WHERE id = ?", [project_id]
            )
            if project:
                for r in research_rows[:3]:
                    try:
                        await create_capture(
                            db, project["requested_by"],
                            f"[Project: {project['title']}] {r['title']}\n{r['content'][:1000]}",
                            source="project_archive",
                        )
                    except Exception:
                        pass
    except Exception as e:
        log.debug(f"Research archival to captures skipped: {e}")

    await db.execute(
        "UPDATE proj_projects SET status = 'completed', completed_at = ?, updated_at = ? WHERE id = ?",
        [now, now, project_id],
    )
    await audit_log(db, "proj_projects", "UPDATE", project_id, actor="engine", source="project_engine",
                    new_values=json.dumps({"status": "completed"}))
    await db.commit()
    log.info(f"Project {project_id} completed")


async def _fail_step(db, step_id: str, error_message: str, project_id: str):
    """Mark a step as failed and log to dead letter queue."""
    now = now_et().isoformat()
    await db.execute(
        "UPDATE proj_steps SET status = 'failed', result_summary = ? WHERE id = ?",
        [error_message[:500], step_id],
    )

    # Insert into dead letter queue
    try:
        await db.execute(
            """INSERT INTO common_dead_letter (operation, error_message, retry_count, max_retries)
               VALUES (?, ?, 0, 3)""",
            [f"project_step:{project_id}:{step_id}", error_message[:500]],
        )
    except Exception as e:
        log.warning(f"Could not insert into dead letter: {e}")

    await db.commit()


# ─── External Integration: step completion from task completion ───


async def on_task_completed(db, task_id: str):
    """Called when an ops_task linked to a project step is completed.

    Marks the corresponding project step as completed and tries to advance.
    """
    step = await db.execute_fetchone(
        "SELECT * FROM proj_steps WHERE task_ref = ? AND status = 'waiting'",
        [task_id],
    )
    if not step:
        return

    step = dict(step)
    now = now_et().isoformat()
    await db.execute(
        "UPDATE proj_steps SET status = 'completed', completed_at = ? WHERE id = ?",
        [now, step["id"]],
    )
    await db.commit()

    # Try to advance the project
    await advance_project(db, step["project_id"])
