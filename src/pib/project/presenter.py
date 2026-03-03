"""Project plan presenter: format plans for human review."""

import json
import logging

log = logging.getLogger(__name__)

# Gate icons
GATE_ICONS = {
    "none": "",
    "inform": "  [inform]",
    "confirm": "  [confirm]",
    "approve": "  [approve]",
}


async def present_plan_for_approval(db, project_id: str) -> str:
    """Format a project plan for human review.

    Returns a formatted string suitable for iMessage, console, or chat.
    """
    project = await db.execute_fetchone(
        "SELECT * FROM proj_projects WHERE id = ?", [project_id]
    )
    if not project:
        return f"Project {project_id} not found."

    project = dict(project)

    phases = await db.execute_fetchall(
        "SELECT * FROM proj_phases WHERE project_id = ? ORDER BY phase_number",
        [project_id],
    )
    phases = [dict(p) for p in phases] if phases else []

    steps = await db.execute_fetchall(
        "SELECT * FROM proj_steps WHERE project_id = ? ORDER BY phase_id, step_number",
        [project_id],
    )
    steps = [dict(s) for s in steps] if steps else []

    gates = await db.execute_fetchall(
        "SELECT * FROM proj_gates WHERE project_id = ? ORDER BY created_at",
        [project_id],
    )
    gates = [dict(g) for g in gates] if gates else []

    # Build gate lookup by after_phase_id
    gate_by_phase = {}
    for g in gates:
        if g.get("after_phase_id"):
            gate_by_phase[g["after_phase_id"]] = g

    # Build step lookup by phase_id
    steps_by_phase = {}
    for s in steps:
        steps_by_phase.setdefault(s["phase_id"], []).append(s)

    # Format
    lines = []
    lines.append(f"PROJECT: {project['title']}")
    lines.append(f"Brief: {project['brief'][:200]}")
    lines.append("")

    # Risk summary
    risks = []
    if project.get("risk_financial") and project["risk_financial"] != "none":
        risks.append(f"Financial: {project['risk_financial']}")
    if project.get("risk_reputational") and project["risk_reputational"] != "none":
        risks.append(f"Reputational: {project['risk_reputational']}")
    if project.get("risk_technical") and project["risk_technical"] != "none":
        risks.append(f"Technical: {project['risk_technical']}")
    if risks:
        lines.append(f"Risk: {', '.join(risks)}")

    # Budget
    if project.get("budget_limit_cents"):
        lines.append(f"Budget: ${project['budget_limit_cents'] / 100:.2f}")

    # Timeline
    if project.get("estimated_duration_days"):
        lines.append(f"Timeline: ~{project['estimated_duration_days']} days")

    # Permissions
    perms = []
    if project.get("can_email_strangers"):
        perms.append("email strangers")
    if project.get("can_sms_strangers"):
        perms.append("SMS strangers")
    if project.get("can_call_strangers"):
        perms.append("call strangers")
    if project.get("can_spend"):
        perms.append("spend money")
    if project.get("can_share_phone"):
        perms.append("share phone")
    if project.get("can_share_address"):
        perms.append("share address")
    if perms:
        lines.append(f"Permissions needed: {', '.join(perms)}")

    lines.append("")
    lines.append("PHASES:")

    for phase in phases:
        gate = gate_by_phase.get(phase["id"])
        gate_label = ""
        if gate:
            gate_label = GATE_ICONS.get(gate["behavior"], "")

        lines.append(f"  {phase['phase_number']}. {phase['title']}{gate_label}")

        phase_steps = steps_by_phase.get(phase["id"], [])
        for step in phase_steps:
            executor_label = ""
            if step["executor"] != "pib":
                executor_label = f" ({step['executor'].upper()})"
            type_label = ""
            if step["step_type"] == "human":
                type_label = " [YOU]"
            elif step["step_type"] == "wait":
                type_label = " [wait]"
            elif step["step_type"] == "gate":
                type_label = " [gate]"

            lines.append(f"     {step['step_number']}. {step['title']}{executor_label}{type_label}")

        if gate and gate["behavior"] in ("confirm", "approve"):
            lines.append(f"     --- {gate['description'] or 'Review and decide'} ---")

    lines.append("")
    lines.append("Reply 'approve' to start, 'dismiss' to cancel, or ask questions.")

    return "\n".join(lines)
