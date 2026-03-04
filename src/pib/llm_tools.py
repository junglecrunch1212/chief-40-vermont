"""LLM tool definitions and execution dispatch.

Extracted from llm.py — pure refactor, no logic changes.
"""

import json
import logging
import os

from pib.db import audit_log, next_id

log = logging.getLogger(__name__)

__all__ = [
    "TOOLS",
    "execute_tool",
]

# ─── Tool Definitions (Anthropic format) ───

TOOLS = [
    {
        "name": "create_task",
        "description": "Create a new task with title, assignee, due_date, energy, effort, micro_script",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "assignee": {"type": "string", "description": "Member ID (m-james, m-laura, m-charlie)"},
                "due_date": {"type": "string", "description": "ISO 8601 date (YYYY-MM-DD)"},
                "energy": {"type": "string", "enum": ["low", "medium", "high"]},
                "effort": {"type": "string", "enum": ["tiny", "small", "medium", "large"]},
                "micro_script": {"type": "string", "description": "First physical action"},
                "domain": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task_status",
        "description": "Change task status (uses state machine guards). For 'dismissed' include notes (10+ chars). For 'deferred' include scheduled_date. For 'waiting_on' include waiting_on.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "new_status": {"type": "string", "enum": ["next", "in_progress", "done", "waiting_on", "deferred", "dismissed"]},
                "notes": {"type": "string"},
                "scheduled_date": {"type": "string"},
                "waiting_on": {"type": "string"},
            },
            "required": ["task_id", "new_status"],
        },
    },
    {
        "name": "complete_task",
        "description": "Complete a task. Handles reward, streak, and Zeigarnik hook automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "member_id": {"type": "string"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "what_now",
        "description": "Get the ONE task this person should do next. Returns task + context + energy level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_id": {"type": "string", "description": "Member ID to check"},
            },
            "required": ["member_id"],
        },
    },
    {
        "name": "add_list_items",
        "description": "Add items to a named list (grocery, costco, target, hardware, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {"type": "string"},
                "items": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["list_name", "items"],
        },
    },
    {
        "name": "search_items",
        "description": "Search contacts, vendors, and assets in ops_items",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "type": {"type": "string", "enum": ["person", "vendor", "asset"]},
            },
            "required": ["query"],
        },
    },
    {
        "name": "send_message",
        "description": "Queue a message for delivery. Non-household recipients go to approval queue (Gene 4).",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient name or member_id"},
                "content": {"type": "string"},
                "channel": {"type": "string", "enum": ["sms", "imessage", "email"]},
            },
            "required": ["to", "content"],
        },
    },
    {
        "name": "query_schedule",
        "description": "Get calendar events for a date range, with privacy filtering",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
            "required": ["start_date"],
        },
    },
    {
        "name": "query_transactions",
        "description": "Search financial transactions by date range and category",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "category": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "query_budget",
        "description": "Get budget snapshot with spending vs targets per category",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_memory",
        "description": "Save a persistent fact to long-term memory (with dedup and negation detection)",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The fact to remember"},
                "category": {"type": "string", "enum": ["preferences", "facts", "decisions", "corrections", "observations", "commitments"]},
                "domain": {"type": "string"},
            },
            "required": ["content", "category"],
        },
    },
    {
        "name": "recall_memory",
        "description": "Search long-term memory via FTS5 full-text search",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "resolve_conflict",
        "description": "Mark a calendar conflict as resolved with a resolution note",
        "input_schema": {
            "type": "object",
            "properties": {
                "conflict_id": {"type": "string"},
                "resolution": {"type": "string"},
            },
            "required": ["conflict_id", "resolution"],
        },
    },
    {
        "name": "undo_last",
        "description": "Reverse the last LLM-generated operation",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "approve_pending",
        "description": "Approve or reject a pending approval queue item",
        "input_schema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
            },
            "required": ["approval_id", "decision"],
        },
    },
    {
        "name": "log_state",
        "description": "Log medication taken, sleep quality, or focus mode change",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["medication_taken", "sleep_report", "focus_mode"]},
                "value": {"type": "string", "description": "For sleep: great/okay/rough. For focus: on/off."},
            },
            "required": ["action"],
        },
    },
    # ─── Comms Domain Tools ───
    {
        "name": "search_comms",
        "description": "Search communications by person, channel, date range, urgency, or keyword",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Keyword search in summary/body/subject"},
                "channel": {"type": "string", "description": "Filter by channel (imessage, email, sms, etc.)"},
                "urgency": {"type": "string", "enum": ["urgent", "timely", "normal", "fyi"]},
                "needs_response": {"type": "boolean"},
                "member_id": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "draft_response",
        "description": "Generate a CoS-drafted response for a specific comm using the resolved voice profile",
        "input_schema": {
            "type": "object",
            "properties": {
                "comm_id": {"type": "string", "description": "The comm to draft a response for"},
            },
            "required": ["comm_id"],
        },
    },
    {
        "name": "approve_draft",
        "description": "Approve and send a pending draft response, optionally with edits",
        "input_schema": {
            "type": "object",
            "properties": {
                "comm_id": {"type": "string"},
                "edited_body": {"type": "string", "description": "Optional edited text to replace the draft"},
            },
            "required": ["comm_id"],
        },
    },
    {
        "name": "capture_comm",
        "description": "Create a manual capture entry (meeting note, call transcript, observation)",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Brief summary of the communication"},
                "body_snippet": {"type": "string", "description": "Full text or transcript"},
                "channel": {"type": "string", "default": "manual"},
                "comm_type": {"type": "string", "enum": ["meeting_note", "call_transcript", "recording_summary", "observation"]},
                "subject": {"type": "string"},
                "from_addr": {"type": "string"},
            },
            "required": ["summary"],
        },
    },
    # ─── Capture Domain Tools ───
    {
        "name": "capture_thought",
        "description": "Capture a thought, idea, recipe, bookmark, or note to the Second Brain. Zero friction — just needs text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The thought to capture (raw text)"},
                "household_visible": {"type": "boolean", "description": "Share with household? Default false.", "default": False},
            },
            "required": ["text"],
        },
    },
    {
        "name": "search_captures",
        "description": "Search the Second Brain (captures, notes, ideas, recipes, bookmarks) via full-text search",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "include_household": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "share_capture",
        "description": "Toggle household visibility for a capture",
        "input_schema": {
            "type": "object",
            "properties": {
                "capture_id": {"type": "string"},
                "household_visible": {"type": "boolean"},
            },
            "required": ["capture_id", "household_visible"],
        },
    },
    {
        "name": "list_notebooks",
        "description": "List all notebooks for the current user",
        "input_schema": {"type": "object", "properties": {}},
    },
    # Project domain
    {
        "name": "start_project",
        "description": "Start a multi-step household project. Use when someone asks to find a service provider, "
                       "book travel, handle a renovation, enroll in a program, or any other multi-step effort "
                       "involving research, outreach, or coordination. Creates a phased plan with gates for approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "brief": {
                    "type": "string",
                    "description": "The project brief — what needs to happen (e.g., 'find a piano teacher for Charlie')",
                },
            },
            "required": ["brief"],
        },
    },
]


# ─── Tool Executor ───

async def execute_tool(db, tool_name: str, tool_input: dict, member_id: str) -> dict:
    """Execute a tool call and return the result. All tool writes get audit logged."""
    try:
        if tool_name == "create_task":
            return await _tool_create_task(db, tool_input, member_id)
        elif tool_name == "update_task_status":
            return await _tool_update_task_status(db, tool_input, member_id)
        elif tool_name == "complete_task":
            return await _tool_complete_task(db, tool_input, member_id)
        elif tool_name == "what_now":
            return await _tool_what_now(db, tool_input)
        elif tool_name == "add_list_items":
            return await _tool_add_list_items(db, tool_input, member_id)
        elif tool_name == "search_items":
            return await _tool_search_items(db, tool_input)
        elif tool_name == "send_message":
            return await _tool_send_message(db, tool_input, member_id)
        elif tool_name == "query_schedule":
            return await _tool_query_schedule(db, tool_input, member_id)
        elif tool_name == "query_transactions":
            return await _tool_query_transactions(db, tool_input)
        elif tool_name == "query_budget":
            return await _tool_query_budget(db)
        elif tool_name == "save_memory":
            return await _tool_save_memory(db, tool_input, member_id)
        elif tool_name == "recall_memory":
            return await _tool_recall_memory(db, tool_input)
        elif tool_name == "resolve_conflict":
            return await _tool_resolve_conflict(db, tool_input, member_id)
        elif tool_name == "undo_last":
            return await _tool_undo_last(db, member_id)
        elif tool_name == "approve_pending":
            return await _tool_approve_pending(db, tool_input, member_id)
        elif tool_name == "log_state":
            return await _tool_log_state(db, tool_input, member_id)
        elif tool_name == "search_comms":
            return await _tool_search_comms(db, tool_input, member_id)
        elif tool_name == "draft_response":
            return await _tool_draft_response(db, tool_input, member_id)
        elif tool_name == "approve_draft":
            return await _tool_approve_draft(db, tool_input, member_id)
        elif tool_name == "capture_comm":
            return await _tool_capture_comm(db, tool_input, member_id)
        elif tool_name == "capture_thought":
            return await _tool_capture_thought(db, tool_input, member_id)
        elif tool_name == "search_captures":
            return await _tool_search_captures(db, tool_input, member_id)
        elif tool_name == "share_capture":
            return await _tool_share_capture(db, tool_input, member_id)
        elif tool_name == "list_notebooks":
            return await _tool_list_notebooks(db, member_id)
        elif tool_name == "start_project":
            return await _tool_start_project(db, tool_input, member_id)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        log.error(f"Tool {tool_name} failed: {e}", exc_info=True)
        return {"error": str(e)}


async def _tool_create_task(db, inp: dict, member_id: str) -> dict:
    from pib.ingest import generate_micro_script
    task_id = await next_id(db, "tsk")
    assignee = inp.get("assignee", member_id)
    micro = inp.get("micro_script") or generate_micro_script(inp)
    await db.execute(
        "INSERT INTO ops_tasks (id, title, assignee, domain, due_date, energy, effort, "
        "micro_script, notes, created_by, source_system) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [task_id, inp["title"], assignee, inp.get("domain", "tasks"),
         inp.get("due_date"), inp.get("energy"), inp.get("effort", "small"),
         micro, inp.get("notes"), "llm", "claude"],
    )
    await audit_log(db, "ops_tasks", "INSERT", task_id, actor="llm", new_values=json.dumps(inp))
    await db.commit()
    return {"created": task_id, "title": inp["title"], "assignee": assignee, "micro_script": micro}


async def _tool_update_task_status(db, inp: dict, member_id: str) -> dict:
    from pib.engine import transition_task
    result = await transition_task(db, inp["task_id"], inp["new_status"], inp, "llm")
    return result


async def _tool_complete_task(db, inp: dict, member_id: str) -> dict:
    from pib.rewards import complete_task_with_reward
    mid = inp.get("member_id", member_id)
    result = await complete_task_with_reward(db, inp["task_id"], mid, "llm")
    return result


async def _tool_what_now(db, inp: dict) -> dict:
    from pib.engine import load_snapshot, what_now
    mid = inp["member_id"]
    snapshot = await load_snapshot(db, mid)
    result = what_now(mid, snapshot)
    return {
        "the_one_task": result.the_one_task,
        "context": result.context,
        "energy_level": result.energy_level,
        "one_more_teaser": result.one_more_teaser,
        "completions_today": result.completions_today,
    }


async def _tool_add_list_items(db, inp: dict, member_id: str) -> dict:
    items = inp.get("items", [])
    list_name = inp["list_name"]
    added = []
    for item_text in items:
        item_id = await next_id(db, "lst")
        await db.execute(
            "INSERT INTO ops_lists (id, list_name, item_text, added_by) VALUES (?,?,?,?)",
            [item_id, list_name, item_text, "llm"],
        )
        added.append(item_id)
    await db.commit()
    return {"list": list_name, "added_count": len(added), "ids": added}


async def _tool_search_items(db, inp: dict) -> dict:
    query = inp["query"]
    item_type = inp.get("type")
    sql = "SELECT id, name, type, category, phone, email, notes FROM ops_items WHERE name LIKE ?"
    params = [f"%{query}%"]
    if item_type:
        sql += " AND type = ?"
        params.append(item_type)
    sql += " LIMIT 10"
    rows = await db.execute_fetchall(sql, params)
    return {"results": [dict(r) for r in rows] if rows else []}


async def _tool_send_message(db, inp: dict, member_id: str) -> dict:
    household_ids = {"m-james", "m-laura", "m-charlie"}
    to = inp["to"]
    if to not in household_ids:
        approval_id = await next_id(db, "apv")
        await db.execute(
            "INSERT INTO mem_approval_queue (id, action_type, title, detail, payload, requested_by) "
            "VALUES (?,?,?,?,?,?)",
            [approval_id, "send_message", f"Send message to {to}",
             f"Content: {inp['content'][:100]}", json.dumps(inp), member_id],
        )
        await db.commit()
        return {"queued_for_approval": approval_id, "to": to}
    # Route through channel registry for household members
    try:
        from pib.comms import determine_best_channel
        from pib.outbound_router import route_outbound
        channel_id = await determine_best_channel(db, member_id, recipient_id=to)
        result = await route_outbound(
            db,
            channel_id=channel_id,
            message=inp["content"],
            member_id=to,
        )
        return {"status": result.get("status", "queued"), "to": to, "channel": channel_id, "content": inp["content"]}
    except Exception as e:
        log.debug(f"Outbound routing unavailable for send_message, falling back: {e}")
        return {"status": "queued", "to": to, "content": inp["content"]}


async def _tool_query_schedule(db, inp: dict, member_id: str) -> dict:
    from pib.context import build_calendar_context
    start = inp["start_date"]
    end = inp.get("end_date", start)
    context = await build_calendar_context(db, start, end, member_id)
    return {"schedule": context, "start": start, "end": end}


async def _tool_query_transactions(db, inp: dict) -> dict:
    sql = "SELECT * FROM fin_transactions WHERE 1=1"
    params = []
    if inp.get("start_date"):
        sql += " AND transaction_date >= ?"
        params.append(inp["start_date"])
    if inp.get("end_date"):
        sql += " AND transaction_date <= ?"
        params.append(inp["end_date"])
    if inp.get("category"):
        sql += " AND category = ?"
        params.append(inp["category"])
    sql += " ORDER BY transaction_date DESC LIMIT ?"
    params.append(inp.get("limit", 20))
    rows = await db.execute_fetchall(sql, params)
    return {"transactions": [dict(r) for r in rows] if rows else []}


async def _tool_query_budget(db) -> dict:
    rows = await db.execute_fetchall("SELECT * FROM fin_budget_snapshot ORDER BY category")
    return {"budget": [dict(r) for r in rows] if rows else []}


async def _tool_save_memory(db, inp: dict, member_id: str) -> dict:
    from pib.memory import save_memory_deduped
    result = await save_memory_deduped(
        db, inp["content"], inp.get("category", "general"),
        inp.get("domain"), member_id, "inferred",
    )
    await db.commit()
    return result


async def _tool_recall_memory(db, inp: dict) -> dict:
    from pib.memory import search_memory
    results = await search_memory(db, inp["query"], inp.get("limit", 10))
    return {"memories": results}


async def _tool_resolve_conflict(db, inp: dict, member_id: str) -> dict:
    await db.execute(
        "UPDATE cal_conflicts SET status = 'resolved', resolution = ?, resolved_by = ?, "
        "resolved_at = datetime('now') WHERE id = ?",
        [inp["resolution"], member_id, inp["conflict_id"]],
    )
    await db.commit()
    return {"resolved": inp["conflict_id"]}


async def _tool_undo_last(db, member_id: str) -> dict:
    row = await db.execute_fetchone(
        "SELECT * FROM common_undo_log WHERE actor = ? ORDER BY created_at DESC LIMIT 1",
        [member_id],
    )
    if not row:
        return {"error": "Nothing to undo"}
    undo = dict(row)
    if undo.get("restore_data"):
        await db.executescript(undo["restore_data"])
        await db.execute("DELETE FROM common_undo_log WHERE id = ?", [undo["id"]])
        await db.commit()
        return {"undone": undo.get("operation", "last action")}
    return {"error": "No restore data available for this action"}


async def _tool_approve_pending(db, inp: dict, member_id: str) -> dict:
    await db.execute(
        "UPDATE mem_approval_queue SET status = ?, decided_by = ?, decided_at = datetime('now') WHERE id = ?",
        [inp["decision"], member_id, inp["approval_id"]],
    )
    await db.commit()
    return {"approval_id": inp["approval_id"], "decision": inp["decision"]}


async def _tool_log_state(db, inp: dict, member_id: str) -> dict:
    action = inp["action"]
    value = inp.get("value")
    if action == "medication_taken":
        await db.execute(
            "INSERT INTO pib_energy_states (member_id, state_date, meds_taken, meds_taken_at) "
            "VALUES (?, date('now'), 1, datetime('now')) "
            "ON CONFLICT(member_id, state_date) DO UPDATE SET meds_taken = 1, meds_taken_at = datetime('now')",
            [member_id],
        )
    elif action == "sleep_report":
        await db.execute(
            "INSERT INTO pib_energy_states (member_id, state_date, sleep_quality) "
            "VALUES (?, date('now'), ?) "
            "ON CONFLICT(member_id, state_date) DO UPDATE SET sleep_quality = ?",
            [member_id, value, value],
        )
    elif action == "focus_mode":
        on = 1 if value in ("on", "true", "1", True) else 0
        await db.execute(
            "INSERT INTO pib_energy_states (member_id, state_date, focus_mode) "
            "VALUES (?, date('now'), ?) "
            "ON CONFLICT(member_id, state_date) DO UPDATE SET focus_mode = ?",
            [member_id, on, on],
        )
    await db.commit()
    return {"logged": action, "value": value}


# ─── Comms Domain Tool Implementations ───

async def _tool_search_comms(db, inp: dict, member_id: str) -> dict:
    from pib.comms import get_comms_inbox
    results = await get_comms_inbox(
        db,
        search=inp.get("search"),
        channel=inp.get("channel"),
        urgency=inp.get("urgency"),
        needs_response=inp.get("needs_response"),
        member_id=inp.get("member_id"),
        limit=inp.get("limit", 10),
    )
    return {"comms": results, "count": len(results)}


async def _tool_draft_response(db, inp: dict, member_id: str) -> dict:
    from pib.comms import get_comm_by_id, save_draft
    from pib.voice import resolve_voice_profile

    comm = await get_comm_by_id(db, inp["comm_id"])
    if not comm:
        return {"error": "Comm not found"}

    profile = await resolve_voice_profile(
        db, member_id,
        recipient_item_ref=comm.get("item_ref"),
        channel=comm.get("channel"),
    )
    style_guide = ""
    if profile and profile.get("style_summary"):
        style_guide = f"\n\nMatch this writing style: {profile['style_summary']}"

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=f"You are drafting a response on behalf of {member_id}. "
                   f"Match their tone and style. Keep it concise.{style_guide}",
            messages=[{
                "role": "user",
                "content": f"Draft a reply to this message:\n"
                           f"From: {comm.get('from_addr', 'unknown')}\n"
                           f"Channel: {comm.get('channel', 'unknown')}\n"
                           f"Message: {comm.get('body_snippet') or comm.get('summary', '')}",
            }],
        )
        draft_text = response.content[0].text.strip()
    except Exception as e:
        return {"error": f"Draft generation failed: {e}"}

    profile_id = profile["id"] if profile else None
    await save_draft(db, inp["comm_id"], draft_text, profile_id)
    return {"draft": draft_text, "voice_profile": profile_id, "status": "pending"}


async def _tool_approve_draft(db, inp: dict, member_id: str) -> dict:
    from pib.comms import approve_draft
    result = await approve_draft(db, inp["comm_id"], inp.get("edited_body"))
    if not result:
        return {"error": "No pending draft for this comm"}
    return {"approved": True, "comm_id": inp["comm_id"]}


async def _tool_capture_comm(db, inp: dict, member_id: str) -> dict:
    from pib.comms import capture_manual
    comm_id = await capture_manual(db, member_id, inp)
    return {"captured": comm_id, "summary": inp["summary"]}


# ─── Capture Domain Tool Implementations ───

async def _tool_capture_thought(db, inp: dict, member_id: str) -> dict:
    from pib.capture import create_capture
    capture = await create_capture(
        db, member_id, inp["text"],
        source="chat",
        household_visible=inp.get("household_visible", False),
    )
    return {
        "captured": capture["id"],
        "type": capture["capture_type"],
        "notebook": capture["notebook"],
    }


async def _tool_search_captures(db, inp: dict, member_id: str) -> dict:
    from pib.capture import search_captures_fts
    results = await search_captures_fts(
        db, inp["query"], member_id,
        include_household=inp.get("include_household", False),
        limit=inp.get("limit", 10),
    )
    return {
        "captures": [
            {"id": r["id"], "type": r["capture_type"], "notebook": r["notebook"],
             "title": r.get("title"), "raw_text": r["raw_text"][:200],
             "tags": r.get("tags", "[]")}
            for r in results
        ],
        "count": len(results),
    }


async def _tool_share_capture(db, inp: dict, member_id: str) -> dict:
    from pib.capture import update_capture
    result = await update_capture(
        db, inp["capture_id"], member_id,
        {"household_visible": 1 if inp["household_visible"] else 0},
    )
    if not result:
        return {"error": "Capture not found or not owned by you"}
    return {"capture_id": inp["capture_id"], "household_visible": inp["household_visible"]}


async def _tool_list_notebooks(db, member_id: str) -> dict:
    from pib.capture import get_notebook_list
    notebooks = await get_notebook_list(db, member_id)
    return {
        "notebooks": [
            {"id": nb["id"], "name": nb["name"], "slug": nb["slug"],
             "icon": nb.get("icon"), "capture_count": nb.get("capture_count", 0)}
            for nb in notebooks
        ],
    }


# ─── Project Domain Tool ───

async def _tool_start_project(db, inp: dict, member_id: str) -> dict:
    """Start a household project. Detects signals, decomposes into phased plan."""
    brief = inp.get("brief", "")
    if not brief:
        return {"error": "brief is required"}

    try:
        from pib.project.detection import detect_project
        detection = detect_project(brief)
        if not detection:
            return {
                "message": "This doesn't look like a multi-step project. "
                           "Consider creating a task instead.",
                "is_project": False,
            }

        from pib.project.planner import decompose_project
        from pib.project.presenter import present_plan_for_approval

        result = await decompose_project(db, brief, member_id)
        presentation = await present_plan_for_approval(db, result["project_id"])

        return {
            "project_id": result["project_id"],
            "title": result["title"],
            "status": "pending_approval",
            "presentation": presentation,
            "is_project": True,
            "detection": detection,
        }
    except Exception as e:
        log.error(f"start_project failed: {e}", exc_info=True)
        return {"error": f"Project creation failed: {e}"}
