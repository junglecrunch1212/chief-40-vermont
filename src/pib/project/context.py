"""Project context assembler for the LLM conversation system."""

import logging

log = logging.getLogger(__name__)

# ─── Trigger Keywords ───

PROJECT_TRIGGERS = {
    "project", "projects", "progress", "status update", "how's the",
    "phase", "gate", "approve", "dismiss",
    "piano teacher", "contractor", "renovation", "ADU",
    "enrollment", "registration", "vendor", "provider",
    "hire", "booking", "travel", "camp",
}


async def assemble_project_context(db, member_id: str) -> str:
    """Build project context for the LLM.

    Returns a summary of active projects, current steps, and pending gates.
    Returns empty string if no active projects (save context tokens).
    """
    try:
        projects = await db.execute_fetchall(
            """SELECT id, title, status FROM proj_projects
               WHERE status IN ('active', 'blocked', 'paused', 'pending_approval')
                 AND (requested_by = ? OR visible_to = 'all')
               ORDER BY updated_at DESC LIMIT 5""",
            [member_id],
        )
    except Exception:
        return ""  # proj tables may not exist yet

    if not projects:
        return ""

    parts = ["ACTIVE PROJECTS:"]

    for proj in projects:
        proj = dict(proj)
        project_id = proj["id"]

        # Current phase
        phase = await db.execute_fetchone(
            """SELECT title, phase_number FROM proj_phases
               WHERE project_id = ? AND status = 'active'
               ORDER BY phase_number LIMIT 1""",
            [project_id],
        )

        # Current step
        step = await db.execute_fetchone(
            """SELECT title, status, step_type FROM proj_steps
               WHERE project_id = ? AND status IN ('active', 'waiting', 'ready')
               ORDER BY step_number LIMIT 1""",
            [project_id],
        )

        # Pending gates
        gate = await db.execute_fetchone(
            """SELECT title, behavior FROM proj_gates
               WHERE project_id = ? AND status = 'waiting'
               ORDER BY created_at LIMIT 1""",
            [project_id],
        )

        line = f"- {proj['title']} [{proj['status']}]"
        if phase:
            line += f" | Phase {phase['phase_number']}: {phase['title']}"
        if step:
            step = dict(step)
            line += f" | Step: {step['title']} ({step['status']})"
        if gate:
            gate = dict(gate)
            line += f" | GATE PENDING: {gate['title']} ({gate['behavior']})"

        parts.append(line)

    return "\n".join(parts)


async def get_project_stats(db, member_id: str) -> dict:
    """Get project statistics for cross-domain summary."""
    try:
        active = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM proj_projects WHERE status IN ('active','blocked') AND requested_by = ?",
            [member_id],
        )
        pending = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM proj_projects WHERE status = 'pending_approval' AND requested_by = ?",
            [member_id],
        )
        gates = await db.execute_fetchone(
            """SELECT COUNT(*) as c FROM proj_gates g
               JOIN proj_projects p ON g.project_id = p.id
               WHERE g.status = 'waiting' AND p.requested_by = ?""",
            [member_id],
        )
        return {
            "active": active["c"] if active else 0,
            "pending_approval": pending["c"] if pending else 0,
            "pending_gates": gates["c"] if gates else 0,
        }
    except Exception:
        return {"active": 0, "pending_approval": 0, "pending_gates": 0}
