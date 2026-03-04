"""Execution tools for project steps. Each returns {summary, data, artifacts}."""

import json
import logging
import os
from datetime import datetime

from pib.db import audit_log, next_id
from pib.tz import now_et
from pib.project.gates import GateViolation, check_reputational_gate
from pib.project.rate_limit import check_rate_limit

log = logging.getLogger(__name__)


def _safe_json_parse(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"raw": text}


async def _log_action(db, action_type: str, project_id: str, step_id: str, details: str):
    """Log a project action to audit_log for rate limiting and audit trail."""
    await audit_log(
        db, "proj_steps", "UPDATE", step_id,
        actor="pib", source=f"project:{action_type}",
        new_values=json.dumps({"project_id": project_id, "action": action_type, "details": details[:200]}),
    )


# ─── Web Search Tool ───


async def tool_web_search(db, project_id: str, step: dict, context: str = "") -> dict:
    """Execute a web search step. Stores results as proj_research artifacts."""
    if not await check_rate_limit(db, project_id, "web_search"):
        return {"summary": "Rate limit hit for web search", "data": {}, "artifacts": []}

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return {
            "summary": "Web search skipped: BRAVE_SEARCH_API_KEY not configured",
            "data": {"skipped": True},
            "artifacts": [],
        }

    query = step.get("description", step.get("title", ""))
    if context:
        query = f"{query} {context}"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                params={"q": query[:200], "count": 10},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        artifacts = []
        for item in data.get("web", {}).get("results", [])[:10]:
            result = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            }
            results.append(result)

            # Store as research artifact
            res_id = await next_id(db, "res")
            await db.execute(
                """INSERT INTO proj_research
                   (id, project_id, step_id, research_type, title, content, source_url, source_name)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [res_id, project_id, step["id"], "web_result",
                 item.get("title", "")[:200], item.get("description", ""),
                 item.get("url", ""), "brave_search"],
            )
            artifacts.append(res_id)

        await _log_action(db, "web_search", project_id, step["id"], query[:200])
        await db.commit()

        return {
            "summary": f"Found {len(results)} results for: {query[:100]}",
            "data": {"results": results, "query": query},
            "artifacts": artifacts,
        }

    except Exception as e:
        log.error(f"Web search failed: {e}")
        return {"summary": f"Web search failed: {e}", "data": {"error": str(e)}, "artifacts": []}


# ─── Gmail Draft Tool ───


async def tool_gmail_draft(db, project_id: str, step: dict, project: dict) -> dict:
    """Draft an email via LLM. Inserts into ops_comms with draft_status='pending'.

    NEVER sends directly. The human approves the draft via ops_comms workflow.
    """
    if not await check_rate_limit(db, project_id, "gmail_send"):
        return {"summary": "Rate limit hit for email drafts", "data": {}, "artifacts": []}

    try:
        check_reputational_gate(project, step.get("description", ""), "email")
    except GateViolation as e:
        return {"summary": f"Gate violation: {e.reason}", "data": {"gate_violation": str(e)}, "artifacts": []}

    # Build email via LLM
    try:
        from pib.llm import get_client, get_model

        model = await get_model(db, "sonnet")
        client = get_client()

        prompt = f"""Draft a professional email for this project step.

PROJECT: {project.get('title', '')}
STEP: {step.get('title', '')}
DETAILS: {step.get('description', '')}

Write a concise, professional email. Return JSON:
{{"to": "recipient email or description", "subject": "email subject", "body": "email body"}}

Sign as: James Stice (via PIB)"""

        response = await client.messages.create(
            model=model, max_tokens=1000, temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        email_data = _safe_json_parse(response.content[0].text)

    except Exception as e:
        log.error(f"Email draft LLM call failed: {e}")
        return {"summary": f"Email draft failed: {e}", "data": {"error": str(e)}, "artifacts": []}

    # Insert into ops_comms with draft_status='pending'
    try:
        comms_id = await next_id(db, "c")
        now = now_et().isoformat()
        await db.execute(
            """INSERT INTO ops_comms
               (id, date, channel, direction, from_addr, to_addr,
                subject, summary, body_snippet, draft_status, created_by, created_at)
               VALUES (?,?,?,?,?,?, ?,?,?,?,?,?)""",
            [
                comms_id, now[:10], "email", "outbound",
                "jrstice@gmail.com", email_data.get("to", "unknown"),
                email_data.get("subject", step.get("title", "")),
                email_data.get("body", "")[:200],
                email_data.get("body", "")[:500],
                "pending",
                "project",
                now,
            ],
        )
        await _log_action(db, "gmail_send", project_id, step["id"], f"Draft to {email_data.get('to', 'unknown')}")
        await db.commit()

        return {
            "summary": f"Email draft created: {email_data.get('subject', '')}",
            "data": {"comms_id": comms_id, "email": email_data},
            "artifacts": [comms_id],
        }
    except Exception as e:
        log.warning(f"ops_comms insert failed (table may not be ready): {e}")
        return {
            "summary": f"Email drafted but could not save to ops_comms: {e}",
            "data": {"email": email_data, "error": str(e)},
            "artifacts": [],
        }


# ─── Twilio SMS Draft Tool ───


async def tool_twilio_sms(db, project_id: str, step: dict, project: dict) -> dict:
    """Draft an SMS. Inserts into ops_comms with draft_status='pending'."""
    if not await check_rate_limit(db, project_id, "twilio_sms"):
        return {"summary": "Rate limit hit for SMS", "data": {}, "artifacts": []}

    try:
        check_reputational_gate(project, step.get("description", ""), "sms")
    except GateViolation as e:
        return {"summary": f"Gate violation: {e.reason}", "data": {"gate_violation": str(e)}, "artifacts": []}

    try:
        from pib.llm import get_client, get_model

        model = await get_model(db, "sonnet")
        client = get_client()

        prompt = f"""Draft a brief SMS for this project step.

PROJECT: {project.get('title', '')}
STEP: {step.get('title', '')}
DETAILS: {step.get('description', '')}

Keep it under 160 characters. Professional but friendly.
Return JSON: {{"to": "phone number or description", "body": "SMS text"}}

Identify as PIB on behalf of James Stice."""

        response = await client.messages.create(
            model=model, max_tokens=300, temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        sms_data = _safe_json_parse(response.content[0].text)

    except Exception as e:
        log.error(f"SMS draft LLM call failed: {e}")
        return {"summary": f"SMS draft failed: {e}", "data": {"error": str(e)}, "artifacts": []}

    try:
        comms_id = await next_id(db, "c")
        now = now_et().isoformat()
        await db.execute(
            """INSERT INTO ops_comms
               (id, date, channel, direction, to_addr,
                summary, body_snippet, draft_status, created_by, created_at)
               VALUES (?,?,?,?,?, ?,?,?,?,?)""",
            [
                comms_id, now[:10], "sms", "outbound",
                sms_data.get("to", "unknown"),
                sms_data.get("body", "")[:200],
                sms_data.get("body", "")[:500],
                "pending",
                "project",
                now,
            ],
        )
        await _log_action(db, "twilio_sms", project_id, step["id"], f"SMS to {sms_data.get('to', 'unknown')}")
        await db.commit()

        return {
            "summary": f"SMS draft created to {sms_data.get('to', 'unknown')}",
            "data": {"comms_id": comms_id, "sms": sms_data},
            "artifacts": [comms_id],
        }
    except Exception as e:
        log.warning(f"ops_comms insert failed (table may not be ready): {e}")
        return {
            "summary": f"SMS drafted but could not save to ops_comms: {e}",
            "data": {"sms": sms_data, "error": str(e)},
            "artifacts": [],
        }


# ─── Compile Research Tool ───


async def tool_compile_research(db, project_id: str, step: dict) -> dict:
    """Gather all proj_research for the project and synthesize into a comparison/report."""
    research_rows = await db.execute_fetchall(
        "SELECT * FROM proj_research WHERE project_id = ? ORDER BY created_at",
        [project_id],
    )

    if not research_rows:
        return {"summary": "No research to compile", "data": {}, "artifacts": []}

    research_items = [dict(r) for r in research_rows]
    research_text = "\n\n".join(
        f"[{r['research_type']}] {r['title']}\n{r['content'][:500]}"
        + (f"\nSource: {r['source_url']}" if r.get("source_url") else "")
        for r in research_items
    )

    try:
        from pib.llm import get_client, get_model

        model = await get_model(db, "opus")
        client = get_client()

        prompt = f"""Compile this research into a structured comparison/report.

PROJECT STEP: {step.get('title', '')}
INSTRUCTIONS: {step.get('description', '')}

RESEARCH DATA:
{research_text[:8000]}

Create a clear, structured summary. Highlight key findings, comparisons, and recommendations.
Return JSON: {{"title": "Report title", "summary": "1-2 sentence summary", "report": "Full report text", "recommendations": ["rec1", "rec2"]}}"""

        response = await client.messages.create(
            model=model, max_tokens=2000, temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        report = _safe_json_parse(response.content[0].text)

    except Exception as e:
        log.error(f"Compile research LLM call failed: {e}")
        return {"summary": f"Compilation failed: {e}", "data": {"error": str(e)}, "artifacts": []}

    # Store compiled report as research artifact
    res_id = await next_id(db, "res")
    await db.execute(
        """INSERT INTO proj_research
           (id, project_id, step_id, research_type, title, content, source_name)
           VALUES (?,?,?,?,?,?,?)""",
        [res_id, project_id, step["id"], "comparison",
         report.get("title", "Compiled Report"),
         report.get("report", report.get("summary", "")),
         "pib_compiler"],
    )
    await db.commit()

    return {
        "summary": report.get("summary", "Research compiled"),
        "data": report,
        "artifacts": [res_id],
    }


# ─── Generic Tool ───


async def tool_generic(db, project_id: str, step: dict, project: dict) -> dict:
    """Fallback tool: give LLM the step instructions + context."""
    try:
        from pib.llm import get_client, get_model

        model = await get_model(db, "sonnet")
        client = get_client()

        prompt = f"""You are executing a project step for PIB.

PROJECT: {project.get('title', '')}
STEP: {step.get('title', '')}
INSTRUCTIONS: {step.get('description', '')}
TOOL HINT: {step.get('tool_hint', 'none')}

If you can provide a useful result, return JSON:
{{"summary": "what was done", "result": "the output", "needs_human": false}}

If this requires human action, return:
{{"summary": "what the human needs to do", "result": "", "needs_human": true, "human_task": "description of what James needs to do"}}"""

        response = await client.messages.create(
            model=model, max_tokens=1000, temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _safe_json_parse(response.content[0].text)

    except Exception as e:
        log.error(f"Generic tool LLM call failed: {e}")
        return {"summary": f"Step execution failed: {e}", "data": {"error": str(e)}, "artifacts": []}

    # If LLM says needs human, create a task
    if result.get("needs_human"):
        try:
            task_id = await next_id(db, "tsk")
            await db.execute(
                """INSERT INTO ops_tasks
                   (id, title, status, assignee, domain, item_type,
                    micro_script, created_by, source_system,
                    project_ref, project_step_ref, notes)
                   VALUES (?,?,?,?,?,?, ?,?,?, ?,?,?)""",
                [
                    task_id,
                    result.get("human_task", step.get("title", "Project task")),
                    "inbox",
                    step.get("executor", "m-james") if step.get("executor") in ("james", "laura") else "m-james",
                    "projects",
                    "task",
                    result.get("summary", ""),
                    "project",
                    "project_engine",
                    project_id,
                    step["id"],
                    f"Project: {project.get('title', '')}",
                ],
            )
            await db.commit()
            return {
                "summary": f"Human task created: {result.get('human_task', '')}",
                "data": {"task_id": task_id, "needs_human": True},
                "artifacts": [task_id],
            }
        except Exception as e:
            log.warning(f"Could not create human task: {e}")

    return {
        "summary": result.get("summary", "Step completed"),
        "data": result,
        "artifacts": [],
    }


# ─── Tool Dispatcher ───

TOOL_MAP = {
    "web_search": tool_web_search,
    "gmail_send": tool_gmail_draft,
    "gmail_read": tool_generic,
    "twilio_sms": tool_twilio_sms,
    "twilio_call": tool_generic,
    "compile": tool_compile_research,
    "calendar_read": tool_generic,
    "memory_search": tool_generic,
    "file_create": tool_generic,
    "manual": tool_generic,
    "none": tool_generic,
}


async def dispatch_tool(db, project_id: str, step: dict, project: dict) -> dict:
    """Dispatch a step to the appropriate tool based on tool_hint."""
    tool_hint = step.get("tool_hint") or "none"
    tool_fn = TOOL_MAP.get(tool_hint, tool_generic)

    # Tools that take (db, project_id, step, context_or_project)
    if tool_fn in (tool_web_search,):
        return await tool_fn(db, project_id, step, project.get("brief", ""))
    elif tool_fn in (tool_compile_research,):
        return await tool_fn(db, project_id, step)
    else:
        return await tool_fn(db, project_id, step, project)
