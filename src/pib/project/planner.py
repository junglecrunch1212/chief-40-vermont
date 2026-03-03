"""Project planner: LLM-powered decomposition of briefs into phased plans."""

import json
import logging
import os
from datetime import datetime

from pib.db import audit_log, get_config, next_id

log = logging.getLogger(__name__)

# ─── Planner System Prompt ───

PLANNER_SYSTEM_PROMPT = """You are PIB's project planner. Given a household project brief, decompose it into
a structured, phased plan that PIB can execute step-by-step.

RULES:
1. Break the project into 2-5 phases. Each phase has 2-8 steps.
2. The LAST phase MUST be a close-out phase (review results, clean up).
3. Every plan MUST have at least one 'confirm' or 'approve' gate. Fully autonomous projects are NOT allowed.
4. Use gates wisely:
   - none: PIB auto-advances (e.g., web research)
   - inform: PIB notifies James, then auto-advances
   - confirm: PIB pauses and waits for James to say "go ahead"
   - approve: PIB pauses and waits for explicit approval (for spending, commitments, selections)
5. Step types:
   - auto: PIB executes (research, drafting, compiling)
   - draft: PIB creates a draft for review (emails, documents)
   - gate: Decision point requiring human input
   - human: Requires physical human action (attend meeting, sign contract)
   - wait: Wait for external response (vendor reply, approval from external party)
6. Executors: pib, james, laura, external
7. Tool hints: web_search, gmail_send, gmail_read, twilio_sms, twilio_call, compile, manual, none
8. Classify risks: financial (none/low/medium/high), reputational (none/low/medium/high), technical (none/low/medium/high)
9. Suggest permissions: can_email_strangers, can_sms_strangers, can_call_strangers, can_spend, can_share_phone, can_share_address

Return ONLY valid JSON matching this schema:
{
  "title": "Short project title",
  "phases": [
    {
      "title": "Phase title",
      "description": "What this phase accomplishes",
      "gate_after": "none|inform|confirm|approve",
      "gate_description": "What James needs to decide (if gate is confirm/approve)",
      "steps": [
        {
          "title": "Step title",
          "description": "What this step does",
          "step_type": "auto|draft|gate|human|wait",
          "executor": "pib|james|laura|external",
          "tool_hint": "web_search|gmail_send|...|none",
          "estimated_minutes": 15
        }
      ]
    }
  ],
  "risk_financial": "none|low|medium|high",
  "risk_reputational": "none|low|medium|high",
  "risk_technical": "none|low|medium|high",
  "suggested_permissions": ["can_email_strangers", ...],
  "estimated_duration_days": 14,
  "budget_estimate_cents": null
}"""


PLANNER_USER_TEMPLATE = """PROJECT BRIEF: {brief}

CONTEXT:
{context}

{pre_research}

Decompose this into a phased plan. Remember: at least one confirm/approve gate, last phase is close-out."""


# ─── Main Entry Point ───


async def decompose_project(db, brief: str, requested_by: str) -> dict:
    """Decompose a project brief into a phased plan via LLM.

    Returns the full project dict with id, plan, and presentation.
    """
    project_id = await next_id(db, "proj")

    # Pre-research for grounding
    pre_research = await _pre_research(brief)

    # Build household context
    context = await _build_planning_context(db, requested_by)

    # Make the LLM call
    plan = await _call_planner_llm(db, brief, context, pre_research)

    # Validate the plan
    errors = _validate_plan(plan)
    if errors:
        log.warning(f"Plan validation failed: {errors}. Using plan with warnings.")

    # Persist to database
    await _persist_plan(db, project_id, brief, plan, requested_by)

    await audit_log(
        db, "proj_projects", "INSERT", project_id,
        actor=requested_by, source="planner",
        new_values=json.dumps({"title": plan.get("title", brief[:60]), "brief": brief[:200]}),
    )
    await db.commit()

    return {
        "project_id": project_id,
        "title": plan.get("title", brief[:60]),
        "plan": plan,
        "status": "pending_approval",
        "validation_warnings": errors,
    }


# ─── Pre-Research ───


async def _pre_research(brief: str) -> str:
    """Do 1-3 grounding web searches to inform the plan.

    Returns formatted research text, or empty string if no API key.
    """
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return ""

    try:
        import httpx

        queries = _generate_research_queries(brief)
        results = []

        async with httpx.AsyncClient(timeout=10) as client:
            for query in queries[:3]:
                try:
                    resp = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                        params={"q": query, "count": 5},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    for item in data.get("web", {}).get("results", [])[:3]:
                        results.append(f"- {item.get('title', '')}: {item.get('description', '')}")
                except Exception as e:
                    log.debug(f"Pre-research query failed: {e}")

        if results:
            return "PRE-RESEARCH FINDINGS:\n" + "\n".join(results)
    except ImportError:
        log.debug("httpx not available for pre-research")

    return ""


def _generate_research_queries(brief: str) -> list[str]:
    """Generate 1-3 search queries from a brief."""
    words = brief.lower().split()
    # Simple heuristic: use the brief as-is for a query, plus a cost query
    queries = [brief[:100]]
    if any(w in words for w in ["cost", "price", "budget", "afford", "how much"]):
        pass  # Already included cost language
    else:
        queries.append(f"{brief[:80]} cost price Atlanta GA")
    return queries


# ─── Planning Context ───


async def _build_planning_context(db, requested_by: str) -> str:
    """Build household context for the planner."""
    parts = []

    # Who's asking
    member = await db.execute_fetchone(
        "SELECT id, display_name, role FROM common_members WHERE id = ?",
        [requested_by],
    )
    if member:
        parts.append(f"REQUESTED BY: {member['display_name']} ({member['role']})")

    # Household members
    members = await db.execute_fetchall(
        "SELECT display_name, role FROM common_members WHERE active = 1"
    )
    if members:
        names = [f"{m['display_name']} ({m['role']})" for m in members]
        parts.append(f"HOUSEHOLD: {', '.join(names)}")

    # Location
    try:
        addr = await get_config(db, "home_address")
        if addr:
            parts.append(f"LOCATION: {addr}")
    except Exception:
        parts.append("LOCATION: Atlanta, GA")

    # Active life phase
    try:
        phase = await db.execute_fetchone(
            "SELECT name FROM common_life_phases WHERE status = 'active' LIMIT 1"
        )
        if phase:
            parts.append(f"LIFE PHASE: {phase['name']}")
    except Exception:
        pass

    # Active projects count
    try:
        row = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM proj_projects WHERE status IN ('active','blocked','paused')"
        )
        if row:
            parts.append(f"ACTIVE PROJECTS: {row['c']}")
    except Exception:
        pass

    return "\n".join(parts) if parts else "No additional context available."


# ─── LLM Call ───


async def _call_planner_llm(db, brief: str, context: str, pre_research: str) -> dict:
    """Call the LLM to generate a project plan."""
    from pib.llm import get_client, get_model

    model = await get_model(db, "opus")
    client = get_client()

    user_prompt = PLANNER_USER_TEMPLATE.format(
        brief=brief,
        context=context,
        pre_research=pre_research or "(No pre-research available)",
    )

    response = await client.messages.create(
        model=model,
        max_tokens=4000,
        temperature=0.3,
        system=PLANNER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text
    return _safe_json_parse(text)


def _safe_json_parse(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.error(f"Failed to parse planner JSON: {text[:200]}")
        return {
            "title": "Untitled Project",
            "phases": [
                {
                    "title": "Manual Planning",
                    "description": "LLM plan parsing failed — manual planning needed.",
                    "gate_after": "approve",
                    "gate_description": "Review and create plan manually",
                    "steps": [
                        {
                            "title": "Create plan manually",
                            "description": "The automated planner couldn't parse the response.",
                            "step_type": "human",
                            "executor": "james",
                            "tool_hint": "none",
                            "estimated_minutes": 30,
                        }
                    ],
                }
            ],
            "risk_financial": "low",
            "risk_reputational": "low",
            "risk_technical": "none",
            "suggested_permissions": [],
            "estimated_duration_days": 14,
        }


# ─── Validation ───


def _validate_plan(plan: dict) -> list[str]:
    """Validate a plan structure. Returns list of error strings (empty = valid)."""
    errors = []

    phases = plan.get("phases", [])
    if not phases:
        errors.append("Plan has no phases")
        return errors

    if len(phases) < 2:
        errors.append(f"Plan has {len(phases)} phase(s), minimum is 2")
    if len(phases) > 10:
        errors.append(f"Plan has {len(phases)} phases, maximum is 10")

    # Check for at least one confirm/approve gate
    has_gate = False
    for phase in phases:
        gate = phase.get("gate_after", "none")
        if gate in ("confirm", "approve"):
            has_gate = True

        steps = phase.get("steps", [])
        if not steps:
            errors.append(f"Phase '{phase.get('title', '?')}' has no steps")
        if len(steps) > 8:
            errors.append(f"Phase '{phase.get('title', '?')}' has {len(steps)} steps (max 8)")

        for step in steps:
            step_type = step.get("step_type", "")
            if step_type not in ("auto", "draft", "gate", "human", "wait"):
                errors.append(f"Step '{step.get('title', '?')}' has invalid type: {step_type}")
            executor = step.get("executor", "")
            if executor not in ("pib", "james", "laura", "external"):
                errors.append(f"Step '{step.get('title', '?')}' has invalid executor: {executor}")
            if step_type == "gate":
                has_gate = True

    if not has_gate:
        errors.append("Plan has no confirm/approve gate — fully autonomous projects are not allowed")

    # Check last phase is close-out-like
    last_title = phases[-1].get("title", "").lower()
    close_out_words = ["close", "final", "wrap", "review", "report", "complete", "finish", "summary"]
    if not any(w in last_title for w in close_out_words):
        errors.append(f"Last phase '{phases[-1].get('title', '?')}' doesn't appear to be a close-out phase")

    return errors


# ─── Persistence ───


async def _persist_plan(db, project_id: str, brief: str, plan: dict, requested_by: str):
    """Write project, phases, steps, and gates to the database."""
    title = plan.get("title", brief[:60])
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Determine permissions from plan suggestions
    perms = plan.get("suggested_permissions", [])

    await db.execute(
        """INSERT INTO proj_projects
           (id, title, brief, status, requested_by,
            risk_financial, risk_reputational, risk_technical,
            budget_limit_cents, estimated_duration_days,
            can_email_strangers, can_sms_strangers, can_call_strangers,
            can_share_address, can_share_phone, can_spend,
            plan_json, created_at, updated_at)
           VALUES (?,?,?,?,?, ?,?,?, ?,?, ?,?,?, ?,?,?, ?,?,?)""",
        [
            project_id, title, brief, "pending_approval", requested_by,
            plan.get("risk_financial", "low"),
            plan.get("risk_reputational", "low"),
            plan.get("risk_technical", "none"),
            plan.get("budget_estimate_cents"),
            plan.get("estimated_duration_days"),
            1 if "can_email_strangers" in perms else 0,
            1 if "can_sms_strangers" in perms else 0,
            1 if "can_call_strangers" in perms else 0,
            1 if "can_share_address" in perms else 0,
            1 if "can_share_phone" in perms else 0,
            1 if "can_spend" in perms else 0,
            json.dumps(plan),
            now, now,
        ],
    )

    phases = plan.get("phases", [])
    for phase_num, phase_data in enumerate(phases, 1):
        phase_id = await next_id(db, "phase")
        await db.execute(
            """INSERT INTO proj_phases (id, project_id, phase_number, title, description, status)
               VALUES (?,?,?,?,?,?)""",
            [phase_id, project_id, phase_num, phase_data["title"],
             phase_data.get("description", ""), "pending"],
        )

        steps = phase_data.get("steps", [])
        for step_num, step_data in enumerate(steps, 1):
            step_id = await next_id(db, "step")
            await db.execute(
                """INSERT INTO proj_steps
                   (id, phase_id, project_id, step_number, title, description,
                    step_type, status, executor, tool_hint, estimated_minutes)
                   VALUES (?,?,?,?,?,?, ?,?,?,?,?)""",
                [
                    step_id, phase_id, project_id, step_num,
                    step_data.get("title", f"Step {step_num}"),
                    step_data.get("description", ""),
                    step_data.get("step_type", "auto"),
                    "pending",
                    step_data.get("executor", "pib"),
                    step_data.get("tool_hint"),
                    step_data.get("estimated_minutes"),
                ],
            )

        # Create gate after this phase if specified
        gate_behavior = phase_data.get("gate_after", "none")
        if gate_behavior in ("inform", "confirm", "approve"):
            gate_id = await next_id(db, "gate")
            gate_type = "approval" if gate_behavior == "approve" else "decision"
            await db.execute(
                """INSERT INTO proj_gates
                   (id, project_id, after_phase_id, behavior, gate_type, title, description, status)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [
                    gate_id, project_id, phase_id, gate_behavior, gate_type,
                    f"Gate: {phase_data['title']}",
                    phase_data.get("gate_description", f"Review results of {phase_data['title']}"),
                    "pending",
                ],
            )
