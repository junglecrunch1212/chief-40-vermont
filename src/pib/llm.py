"""LLM integration: Anthropic client, tool execution, context assembly, conversation flow."""

import json
import logging
import os
import re
from datetime import date, datetime

import anthropic

from pib.db import audit_log, get_config, next_id

log = logging.getLogger(__name__)

# ─── Token Budget ───

TOKEN_BUDGETS = {
    "system_prompt": 2_500,
    "cross_domain_summary": 500,
    "assembled_context": 25_000,
    "memory_injection": 3_000,
    "conversation_history": 20_000,
}


def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ~ 4 chars for English text."""
    return len(text) // 4


def enforce_budget(section_name: str, content: str) -> str:
    """Truncate content to fit its budget."""
    budget = TOKEN_BUDGETS.get(section_name, 25_000)
    estimated = estimate_tokens(content)
    if estimated > budget:
        log.warning(f"Token budget exceeded: {section_name} = {estimated} (budget: {budget}). Truncating.")
        char_budget = budget * 4
        half = char_budget // 2
        content = content[:half] + "\n... [truncated] ...\n" + content[-half:]
    return content


# ─── Relevance Detection (3-layer) ───

FINANCIAL_TRIGGERS = {
    "money", "spend", "spent", "budget", "afford", "cost", "price", "save",
    "income", "mortgage", "bill", "payment", "account", "balance", "transaction", "$",
}
SCHEDULE_TRIGGERS = {
    "calendar", "schedule", "busy", "free", "available", "appointment", "meeting",
    "event", "conflict", "today", "tomorrow", "this week", "next week", "weekend",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}
TASK_TRIGGERS = {
    "task", "to-do", "todo", "honey-do", "remind", "need to", "should", "must",
    "deadline", "overdue", "done", "finish", "complete",
}
COVERAGE_TRIGGERS = {
    "who has", "custody", "pickup", "dropoff", "coverage", "gap", "babysit", "sitter",
}
COMMS_TRIGGERS = {
    "message", "messages", "email", "emails", "reply", "respond", "responded",
    "draft", "inbox", "unread", "text", "texted", "called", "voicemail",
    "whatsapp", "imessage", "wrote", "sent", "received", "heard from",
    "reach out", "voice note", "recording",
}
CAPTURE_TRIGGERS = {
    "capture", "note", "remember this", "save this", "second brain", "notebook",
    "idea", "recipe", "bookmark", "thought", "jot down", "write down",
    "my notes", "my ideas", "my captures", "my recipes", "my bookmarks",
}
PROJECT_TRIGGERS = {
    "project", "projects", "progress", "status update", "how's the",
    "phase", "gate", "approve", "dismiss",
    "piano teacher", "contractor", "renovation", "ADU",
    "enrollment", "registration", "vendor", "provider",
    "hire", "booking", "travel", "camp",
}


def build_entity_cache(db_rows: list[dict]) -> dict:
    """Build entity cache with word-boundary regex patterns."""
    entities = {}
    for row in db_rows:
        name = row.get("name") or row.get("display_name", "")
        if name:
            pattern = re.compile(r"\b" + re.escape(name.lower()) + r"\b")
            entities[row["id"]] = {"name": name, "pattern": pattern}
    return entities


def analyze_relevance(message: str, entity_cache: dict) -> dict:
    """Multi-match relevance detection. Returns assemblers and matched entities."""
    msg_lower = message.lower()
    assemblers = set()
    matched_entities = []

    if any(t in msg_lower for t in FINANCIAL_TRIGGERS):
        assemblers.add("financial")
    if any(t in msg_lower for t in SCHEDULE_TRIGGERS):
        assemblers.add("schedule")
    if any(t in msg_lower for t in TASK_TRIGGERS):
        assemblers.add("tasks")
    if any(t in msg_lower for t in COVERAGE_TRIGGERS):
        assemblers.update(["coverage", "schedule"])
    if any(t in msg_lower for t in COMMS_TRIGGERS):
        assemblers.add("comms")
    if any(t in msg_lower for t in CAPTURE_TRIGGERS):
        assemblers.add("captures")
    if any(t in msg_lower for t in PROJECT_TRIGGERS):
        assemblers.add("projects")

    for entity_id, entity in entity_cache.items():
        if entity["pattern"].search(msg_lower):
            matched_entities.append(entity_id)
            assemblers.add("entity_lookup")

    assemblers.add("cross_domain_summary")

    return {"assemblers": list(assemblers), "matched_entities": matched_entities}


# ─── Model Selection ───

async def get_model(db, tier: str) -> str:
    """Load model ID from pib_config table with sane defaults."""
    defaults = {
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-6",
    }
    return await get_config(db, f"anthropic_model_{tier}") or defaults.get(tier, defaults["sonnet"])


def select_model_tier(assemblers: list[str], channel: str) -> str:
    """Determine model tier based on query complexity."""
    if len(assemblers) >= 3:
        return "opus"
    if "morning_brief" in assemblers:
        return "opus"
    if channel == "email" and assemblers:
        return "opus"
    return "sonnet"


# ─── Anthropic Client ───

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    """Get or create the Anthropic async client."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


# ─── System Prompt Builder ───

def build_system_prompt(member: dict, channel: str, coach_protocols: list[dict]) -> str:
    """Build the system prompt for a given member and channel."""
    prompt = f"""You are PIB — the Stice-Sclafani household Chief of Staff. You live on a Mac Mini in the closet. You're the competent friend who happens to have a photographic memory and infinite patience. Not a robot. Not a servant. A peer who happens to be really, really organized.

WHO: {member["display_name"]} ({member["role"]})
CHANNEL: {channel}
{"BREVITY: 1-3 sentences max. No markdown. No bullets." if channel in ("imessage", "sms") else ""}
TODAY: {date.today().strftime("%A, %B %d, %Y")}

PERSONALITY:
- Warm, direct, first-name. Lead with the answer.
- Match question energy. Casual -> casual. Focused -> focused.
- Never guilt, shame, or compare family members.
- Celebrate completions. Always. Every single time.
"""

    if member.get("id") == "m-james":
        prompt += """
JAMES-SPECIFIC:
- ADHD-aware: ONE thing at a time. Never lists of 5+. Always the micro-script first.
- When presenting an overdue task: lead with the micro-script, not the overdue count.
- After 3+ completions in a session: "That's momentum. Want to ride it or bank it?"
- Periodically: "Your three things today are X, Y, Z. Even without me, you know these."
"""
    elif member.get("id") == "m-laura":
        prompt += """
LAURA-SPECIFIC:
- Brief. No preamble. Lead with what needs her attention.
- HOME life only. Never reference or acknowledge her work calendar content.
- Highlight: decisions needing her, schedule conflicts, what James is handling.
"""

    prompt += "\nPROTOCOLS:\n"
    for p in coach_protocols:
        prompt += f"- {p['name']}: {p['behavior']}\n"

    prompt += """
RULES:
1. Every claim MUST come from tool calls or context blocks. Never guess.
2. When you learn a persistent fact, use save_memory immediately.
3. Confirm actions in ONE line.
4. Messages to non-household people: ALWAYS queue for approval.
5. If you detect a conflict the system hasn't caught, flag it.
6. For task completions, ALWAYS use the complete_task tool (it handles rewards + streaks).
7. Never output privileged calendar content. If it's redacted in context, it's redacted in your response.
"""
    return prompt


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
        # Capture domain
        elif tool_name == "capture_thought":
            return await _tool_capture_thought(db, tool_input, member_id)
        elif tool_name == "search_captures":
            return await _tool_search_captures(db, tool_input, member_id)
        elif tool_name == "share_capture":
            return await _tool_share_capture(db, tool_input, member_id)
        elif tool_name == "list_notebooks":
            return await _tool_list_notebooks(db, member_id)
        # Project domain
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
    # Gene 4: non-household messages ALWAYS go to approval queue
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
    return {"status": "queued", "to": to, "content": inp["content"]}


async def _tool_query_schedule(db, inp: dict, member_id: str) -> dict:
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

    # Resolve voice profile for tone matching
    profile = await resolve_voice_profile(
        db, member_id,
        recipient_item_ref=comm.get("item_ref"),
        channel=comm.get("channel"),
    )
    style_guide = ""
    if profile and profile.get("style_summary"):
        style_guide = f"\n\nMatch this writing style: {profile['style_summary']}"

    # Generate draft via LLM
    try:
        import anthropic
        import os
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


# ─── Conversation History ───

def build_conversation_history(messages: list[dict], channel: str) -> list[dict]:
    """Sliding window: keep recent messages within token budget."""
    max_messages = 10 if channel in ("sms", "imessage") else 50
    budget = TOKEN_BUDGETS["conversation_history"]

    recent = messages[-max_messages:]
    total_tokens = sum(estimate_tokens(m.get("content", "") if isinstance(m.get("content"), str) else "") for m in recent)

    while total_tokens > budget and len(recent) > 2:
        removed = recent.pop(0)
        c = removed.get("content", "")
        total_tokens -= estimate_tokens(c if isinstance(c, str) else "")

    return recent


# ─── Cross-Domain Summary SQL ───

CROSS_DOMAIN_SUMMARY_SQL = """
SELECT
    (SELECT COUNT(*) FROM ops_tasks WHERE status NOT IN ('done','dismissed')) AS active_tasks,
    (SELECT COUNT(*) FROM ops_tasks WHERE due_date < date('now') AND status NOT IN ('done','dismissed','deferred')) AS overdue_tasks,
    (SELECT COUNT(*) FROM ops_tasks WHERE due_date = date('now') AND status NOT IN ('done','dismissed')) AS due_today,
    (SELECT COUNT(*) FROM cal_conflicts WHERE status = 'unresolved') AS open_conflicts,
    (SELECT SUM(CASE WHEN over_threshold = 1 THEN 1 ELSE 0 END) FROM fin_budget_snapshot) AS budget_alerts,
    (SELECT name FROM common_life_phases WHERE status = 'active' LIMIT 1) AS active_phase
"""


async def build_cross_domain_summary(db) -> str:
    """Build the always-on ~500-token cross-domain summary.

    Enriched with sensor data when available:
    - Weather summary (temp, condition, alerts)
    - Sun times (sunrise/sunset)
    - Per-member health context (privacy-filtered)
    - Home occupancy
    - Deliveries
    - Active sensor alerts
    """
    row = await db.execute_fetchone(CROSS_DOMAIN_SUMMARY_SQL)
    if not row:
        return "No data available."

    lines = []

    # ── Core stats ──
    core_parts = []
    if row["active_tasks"]:
        task_desc = f"{row['active_tasks']} tasks"
        if row["overdue_tasks"]:
            task_desc += f" ({row['overdue_tasks']} overdue)"
        core_parts.append(task_desc)
    if row["due_today"]:
        core_parts.append(f"{row['due_today']} due today")
    if row["open_conflicts"]:
        core_parts.append(f"{row['open_conflicts']} conflicts")
    if row["budget_alerts"]:
        core_parts.append(f"{row['budget_alerts']} budget alerts")
    if core_parts:
        lines.append(" | ".join(core_parts))

    # ── Daily state (includes sensor enrichment) ──
    daily = await db.execute_fetchone(
        "SELECT * FROM cal_daily_states WHERE state_date = date('now') ORDER BY version DESC LIMIT 1"
    )
    if daily:
        complexity = daily["complexity_score"]
        lines.append(f"Complexity: {complexity:.1f}/10")

        # Parse member_states for health context
        try:
            member_states = json.loads(daily["member_states"] or "{}")
            for mid, mstate in member_states.items():
                health = mstate.get("health", {})
                if not health:
                    continue
                member_parts = [mid.replace("m-", "").title()]
                # Privacy: only derived impacts, not raw data
                energy = health.get("energy_level")
                if energy and energy != "medium":
                    member_parts.append(f"energy: {energy}")
                focus = health.get("focus_mode")
                if focus:
                    member_parts.append(f"focus: {focus}")
                if health.get("battery_warning"):
                    member_parts.append("low battery")
                sleep_q = health.get("sleep_quality")
                if sleep_q and sleep_q != "unknown":
                    member_parts.append(f"sleep: {sleep_q}")
                if len(member_parts) > 1:
                    lines.append("  " + " | ".join(member_parts))
        except (json.JSONDecodeError, TypeError):
            pass

    # ── Sensor context (weather, sun, etc.) ──
    sensor_lines = await _build_sensor_summary_lines(db)
    lines.extend(sensor_lines)

    # ── Capture stats ──
    try:
        from pib.capture import get_capture_stats
        # Get stats for all active members
        members = await db.execute_fetchall("SELECT id FROM common_members WHERE role != 'child'")
        for m in (members or []):
            stats = await get_capture_stats(db, m["id"])
            if stats["total"] > 0:
                cap_parts = [f"{stats['total']} captures"]
                if stats["untriaged"]:
                    cap_parts.append(f"{stats['untriaged']} unorganized")
                name = m["id"].replace("m-", "").title()
                lines.append(f"Second Brain ({name}): {', '.join(cap_parts)}")
    except Exception:
        pass  # Capture tables may not exist yet

    # ── Project stats ──
    try:
        from pib.project.context import get_project_stats
        members = members if members else await db.execute_fetchall(
            "SELECT id FROM common_members WHERE role != 'child'"
        )
        for m in (members or []):
            mid = m["id"] if isinstance(m, dict) else m[0]
            pstats = await get_project_stats(db, mid)
            if pstats["active"] > 0 or pstats["pending_approval"] > 0:
                p_parts = []
                if pstats["active"]:
                    p_parts.append(f"{pstats['active']} active")
                if pstats["pending_approval"]:
                    p_parts.append(f"{pstats['pending_approval']} awaiting approval")
                if pstats["pending_gates"]:
                    p_parts.append(f"{pstats['pending_gates']} gates pending")
                name = mid.replace("m-", "").title()
                lines.append(f"Projects ({name}): {', '.join(p_parts)}")
    except Exception:
        pass  # Project tables may not exist yet

    # ── Phase ──
    if row["active_phase"]:
        lines.append(f"Phase: {row['active_phase']}")

    return "\n".join(lines) if lines else "All clear."


async def _build_sensor_summary_lines(db) -> list[str]:
    """Build sensor-enriched summary lines for the cross-domain summary."""
    lines = []

    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Weather
        weather = await db.execute_fetchone(
            """SELECT value FROM pib_sensor_readings
               WHERE sensor_id = 'sensor-weather' AND reading_type = 'weather.current'
                 AND expires_at > ?
               ORDER BY timestamp DESC LIMIT 1""",
            [now],
        )
        if weather:
            try:
                wv = json.loads(weather["value"])
                w_parts = []
                if wv.get("condition_text"):
                    w_parts.append(wv["condition_text"])
                if wv.get("temp_f") is not None:
                    w_parts.append(f"{wv['temp_f']}\u00b0F")
                if wv.get("uv_index") and wv["uv_index"] >= 6:
                    w_parts.append(f"UV {wv['uv_index']}")
                pollen = wv.get("pollen", {})
                high_pollen = [k for k, v in pollen.items() if v == "high"]
                if high_pollen:
                    w_parts.append(f"pollen high")
                if w_parts:
                    lines.append("Weather: " + ", ".join(w_parts))
            except (json.JSONDecodeError, TypeError):
                pass

        # Sun
        sun = await db.execute_fetchone(
            """SELECT value FROM pib_sensor_readings
               WHERE sensor_id = 'sensor-sun' AND reading_type = 'sun.times'
                 AND expires_at > ?
               ORDER BY timestamp DESC LIMIT 1""",
            [now],
        )
        if sun:
            try:
                sv = json.loads(sun["value"])
                if sv.get("sunrise") and sv.get("sunset"):
                    lines.append(f"Sun: rises {sv['sunrise']}, sets {sv['sunset']}")
            except (json.JSONDecodeError, TypeError):
                pass

        # WiFi presence
        wifi = await db.execute_fetchone(
            """SELECT value FROM pib_sensor_readings
               WHERE sensor_id = 'sensor-wifi-presence' AND reading_type = 'home.wifi_presence'
                 AND expires_at > ?
               ORDER BY timestamp DESC LIMIT 1""",
            [now],
        )
        if wifi:
            try:
                wfv = json.loads(wifi["value"])
                home = wfv.get("members_home", [])
                if home:
                    names = [m.replace("m-", "").title() for m in home]
                    lines.append(f"Home: {', '.join(names)}")
            except (json.JSONDecodeError, TypeError):
                pass

        # Deliveries
        pkgs = await db.execute_fetchone(
            """SELECT value FROM pib_sensor_readings
               WHERE sensor_id = 'sensor-packages' AND reading_type = 'logistics.packages'
                 AND expires_at > ?
               ORDER BY timestamp DESC LIMIT 1""",
            [now],
        )
        if pkgs:
            try:
                pv = json.loads(pkgs["value"])
                today_count = len(pv.get("expected_today", []))
                if today_count > 0:
                    lines.append(f"Deliveries: {today_count} expected today")
            except (json.JSONDecodeError, TypeError):
                pass

        # Active sensor alerts
        alerts = await db.execute_fetchall(
            "SELECT severity, title FROM pib_sensor_alerts WHERE status = 'active' ORDER BY severity DESC LIMIT 3"
        )
        for alert in alerts or []:
            severity_icon = {"critical": "!!", "warning": "!", "info": ""}.get(alert["severity"], "")
            lines.append(f"  {severity_icon} {alert['title']}")

    except Exception:
        pass  # Sensor tables may not exist yet — graceful degradation

    return lines


# ─── Privacy-Filtered Calendar Context ───

async def build_calendar_context(db, start_date: str, end_date: str, member_id: str) -> str:
    """Calendar context with privacy filtering at the read layer."""
    events = await db.execute_fetchall(
        "SELECT * FROM cal_classified_events WHERE event_date BETWEEN ? AND ? ORDER BY start_time",
        [start_date, end_date],
    )

    lines = []
    for event in events:
        if event["privacy"] == "full":
            lines.append(f"  {event['start_time']}-{event['end_time']} {event['title']}")
        elif event["privacy"] == "privileged":
            lines.append(f"  {event['start_time']}-{event['end_time']} {event['title_redacted']}")
        elif event["privacy"] == "redacted":
            lines.append(f"  {event['start_time']}-{event['end_time']} [unavailable]")

    return "\n".join(lines) if lines else "No events."


# ─── Context Assembly ───

async def assemble_context(db, member_id: str, message: str) -> str:
    """Assemble the full context block for the LLM: summary + calendar + memory + whatNow."""
    parts = []

    # Cross-domain summary (always included)
    summary = await build_cross_domain_summary(db)
    parts.append(f"DASHBOARD: {summary}")

    # Relevance-driven assembly
    items_rows = await db.execute_fetchall("SELECT id, name FROM ops_items WHERE status = 'active' LIMIT 50")
    entity_cache = build_entity_cache([dict(r) for r in items_rows] if items_rows else [])
    relevance = analyze_relevance(message, entity_cache)

    if "schedule" in relevance["assemblers"]:
        today = date.today().isoformat()
        cal_ctx = await build_calendar_context(db, today, today, member_id)
        parts.append(f"SCHEDULE TODAY:\n{cal_ctx}")

    if "financial" in relevance["assemblers"]:
        budget_rows = await db.execute_fetchall("SELECT * FROM fin_budget_snapshot WHERE over_threshold = 1")
        if budget_rows:
            alerts = [f"  {r['category']}: ${r['spent']:.0f}/{r['budget']:.0f}" for r in budget_rows]
            parts.append(f"BUDGET ALERTS:\n" + "\n".join(alerts))

    if "tasks" in relevance["assemblers"]:
        from pib.engine import load_snapshot, what_now
        snapshot = await load_snapshot(db, member_id)
        wn = what_now(member_id, snapshot)
        if wn.the_one_task:
            parts.append(f"NEXT TASK: {wn.the_one_task['title']} | {wn.the_one_task.get('micro_script', '')}")

    if "coverage" in relevance["assemblers"]:
        from pib.custody import who_has_child
        config_row = await db.execute_fetchone(
            "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
        )
        if config_row:
            parent = who_has_child(date.today(), dict(config_row))
            member = await db.execute_fetchone("SELECT display_name FROM common_members WHERE id = ?", [parent])
            parts.append(f"CUSTODY TODAY: {member['display_name'] if member else parent}")

    # Memory injection: recent relevant memories
    from pib.memory import search_memory
    # Extract key words from message for memory search
    search_terms = " ".join(w for w in message.split() if len(w) > 3)[:50]
    if search_terms:
        memories = await search_memory(db, search_terms, limit=5)
        if memories:
            mem_lines = [f"  - {m['content']}" for m in memories]
            parts.append(f"RELEVANT MEMORIES:\n" + "\n".join(mem_lines))

    # Capture injection: pinned captures always + FTS-matched captures when relevant
    try:
        from pib.capture import list_captures, search_captures_fts
        # Always inject pinned captures
        pinned = await list_captures(db, member_id, pinned_only=True, limit=5)
        if pinned:
            pin_lines = [f"  - [{c['capture_type']}] {c.get('title') or c['raw_text'][:80]}" for c in pinned]
            parts.append(f"PINNED CAPTURES:\n" + "\n".join(pin_lines))

        # FTS-matched captures when message is capture-relevant
        if "captures" in relevance["assemblers"] and search_terms:
            matched = await search_captures_fts(db, search_terms, member_id, include_household=True, limit=5)
            if matched:
                cap_lines = [f"  - [{c['capture_type']}] {c.get('title') or c['raw_text'][:80]}" for c in matched]
                parts.append(f"RELEVANT CAPTURES:\n" + "\n".join(cap_lines))
    except Exception:
        pass  # Capture tables may not exist yet

    # Project context injection when relevant
    try:
        if "projects" in relevance["assemblers"]:
            from pib.project.context import assemble_project_context
            proj_ctx = await assemble_project_context(db, member_id)
            if proj_ctx:
                parts.append(f"ACTIVE PROJECTS:\n{proj_ctx}")
    except Exception:
        pass  # Project tables may not exist yet

    context = "\n\n".join(parts)
    return enforce_budget("assembled_context", context)


# ─── Session Management ───

async def get_or_create_session(db, member_id: str, channel: str, session_id: str | None = None) -> dict:
    """Get existing session or create new one."""
    if session_id:
        row = await db.execute_fetchone("SELECT * FROM mem_sessions WHERE id = ? AND active = 1", [session_id])
        if row:
            return dict(row)

    # Create new session
    sid = await next_id(db, "ses")
    await db.execute(
        "INSERT INTO mem_sessions (id, member_id, channel) VALUES (?,?,?)",
        [sid, member_id, channel],
    )
    await db.commit()
    return {"id": sid, "member_id": member_id, "channel": channel, "message_count": 0}


async def save_message(db, session_id: str, role: str, content: str, **kwargs):
    """Save a message to the session history."""
    await db.execute(
        "INSERT INTO mem_messages (session_id, role, content, tool_calls, tool_results, model, tokens_in, tokens_out) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [session_id, role, content,
         kwargs.get("tool_calls"), kwargs.get("tool_results"),
         kwargs.get("model"), kwargs.get("tokens_in"), kwargs.get("tokens_out")],
    )
    await db.execute(
        "UPDATE mem_sessions SET last_message_at = datetime('now'), message_count = message_count + 1 WHERE id = ?",
        [session_id],
    )


async def get_session_messages(db, session_id: str) -> list[dict]:
    """Get messages for a session, formatted for the Anthropic API."""
    rows = await db.execute_fetchall(
        "SELECT role, content FROM mem_messages WHERE session_id = ? ORDER BY created_at",
        [session_id],
    )
    if not rows:
        return []
    messages = []
    for r in rows:
        role = r["role"]
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": r["content"]})
    return messages


# ─── Layer 1 Deterministic Fallback ───

async def deterministic_fallback(message: str, member_id: str, db) -> str:
    """Layer 1 response when Anthropic API is unavailable. No LLM. Pure data."""
    from pib.engine import load_snapshot, what_now
    msg_lower = message.lower()
    wn = what_now(member_id, await load_snapshot(db, member_id))

    if any(t in msg_lower for t in ["what's next", "next", "what now", "what should"]):
        if wn.the_one_task:
            return f"Next: {wn.the_one_task['title']}\n{wn.the_one_task.get('micro_script', '')}"
        return "Nothing pending right now."

    if any(t in msg_lower for t in ["who has", "custody", "charlie"]):
        from pib.custody import who_has_child
        config_row = await db.execute_fetchone(
            "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
        )
        if config_row:
            parent = who_has_child(date.today(), dict(config_row))
            return f"Custody today: {parent}"
        return "Custody data unavailable."

    if "done" in msg_lower and wn.the_one_task:
        from pib.rewards import complete_task_with_reward
        await complete_task_with_reward(db, wn.the_one_task["id"], member_id, "user")
        return "Done! (AI is temporarily offline - basic mode active)"

    parts = ["AI offline - basic mode."]
    if wn.context:
        parts.append(wn.context)
    if wn.the_one_task:
        parts.append(f"Next: {wn.the_one_task['title']}")
    return " ".join(parts)


# ─── Main Chat Handler ───

MAX_TOOL_ROUNDS = 5


async def chat(db, message: str, member_id: str, channel: str = "web",
               session_id: str | None = None) -> dict:
    """Non-streaming chat handler. Returns complete response after all tool rounds."""
    session = await get_or_create_session(db, member_id, channel, session_id)
    sid = session["id"]

    # Save user message
    await save_message(db, sid, "user", message)

    # Build system prompt
    member = await db.execute_fetchone("SELECT * FROM common_members WHERE id = ?", [member_id])
    if not member:
        return {"response": "Unknown member.", "session_id": sid, "actions": []}
    member = dict(member)

    protocols = await db.execute_fetchall("SELECT * FROM pib_coach_protocols WHERE active = 1")
    system_prompt = build_system_prompt(member, channel, [dict(p) for p in protocols] if protocols else [])

    # Build context
    context = await assemble_context(db, member_id, message)

    # Build conversation history
    history_msgs = await get_session_messages(db, sid)
    history = build_conversation_history(history_msgs, channel)
    # Remove the last message (which is the one we just saved)
    if history and history[-1].get("role") == "user" and history[-1].get("content") == message:
        history = history[:-1]

    # Build messages for API
    messages = list(history)
    user_content = message
    if context:
        user_content = f"[CONTEXT]\n{context}\n[/CONTEXT]\n\n{message}"
    messages.append({"role": "user", "content": user_content})

    # Select model
    items_rows = await db.execute_fetchall("SELECT id, name FROM ops_items WHERE status = 'active' LIMIT 50")
    entity_cache = build_entity_cache([dict(r) for r in items_rows] if items_rows else [])
    relevance = analyze_relevance(message, entity_cache)
    tier = select_model_tier(relevance["assemblers"], channel)
    model = await get_model(db, tier)

    # Try LLM (Layer 2), fall back to Layer 1
    actions = []
    try:
        client = get_client()
        tool_rounds = 0
        response_text = ""

        while tool_rounds <= MAX_TOOL_ROUNDS:
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
            )

            # Process response
            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            if text_parts:
                response_text += "".join(text_parts)

            if not tool_uses or tool_rounds >= MAX_TOOL_ROUNDS:
                break

            # Execute tools and continue conversation
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for tool_use in tool_uses:
                result = await execute_tool(db, tool_use.name, tool_use.input, member_id)
                actions.append({"tool": tool_use.name, "input": tool_use.input, "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})
            tool_rounds += 1

        # Track cost
        if response.usage:
            from pib.cost import track_api_cost
            await track_api_cost(db, response.usage.input_tokens, response.usage.output_tokens, model)

        # Save assistant response
        await save_message(db, sid, "assistant", response_text,
                           model=model,
                           tokens_in=response.usage.input_tokens if response.usage else None,
                           tokens_out=response.usage.output_tokens if response.usage else None,
                           tool_calls=json.dumps([{"tool": a["tool"], "input": a["input"]} for a in actions]) if actions else None)
        await db.commit()

        return {"response": response_text, "session_id": sid, "actions": actions}

    except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        log.warning(f"LLM unavailable ({e}), falling back to Layer 1")
        fallback = await deterministic_fallback(message, member_id, db)
        await save_message(db, sid, "assistant", fallback, model="layer1_fallback")
        await db.commit()
        return {"response": fallback, "session_id": sid, "actions": [], "fallback": True}


# ─── Streaming Chat Handler ───

async def stream_chat(db, message: str, member_id: str, channel: str = "web",
                      session_id: str | None = None):
    """Streaming chat handler. Yields SSE-formatted chunks. Circuit breaker at 5 tool rounds."""
    session = await get_or_create_session(db, member_id, channel, session_id)
    sid = session["id"]

    await save_message(db, sid, "user", message)

    member = await db.execute_fetchone("SELECT * FROM common_members WHERE id = ?", [member_id])
    if not member:
        yield f"data: {json.dumps({'type': 'text', 'content': 'Unknown member.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'session_id': sid})}\n\n"
        return
    member = dict(member)

    protocols = await db.execute_fetchall("SELECT * FROM pib_coach_protocols WHERE active = 1")
    system_prompt = build_system_prompt(member, channel, [dict(p) for p in protocols] if protocols else [])

    context = await assemble_context(db, member_id, message)
    history_msgs = await get_session_messages(db, sid)
    history = build_conversation_history(history_msgs, channel)
    if history and history[-1].get("role") == "user" and history[-1].get("content") == message:
        history = history[:-1]

    messages = list(history)
    user_content = f"[CONTEXT]\n{context}\n[/CONTEXT]\n\n{message}" if context else message
    messages.append({"role": "user", "content": user_content})

    items_rows = await db.execute_fetchall("SELECT id, name FROM ops_items WHERE status = 'active' LIMIT 50")
    entity_cache = build_entity_cache([dict(r) for r in items_rows] if items_rows else [])
    relevance = analyze_relevance(message, entity_cache)
    tier = select_model_tier(relevance["assemblers"], channel)
    model = await get_model(db, tier)

    actions = []
    full_response = ""

    try:
        client = get_client()
        tool_rounds = 0

        while tool_rounds <= MAX_TOOL_ROUNDS:
            collected_text = ""
            tool_uses = []
            current_tool = None

            async with client.messages.stream(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if hasattr(event.content_block, "type") and event.content_block.type == "tool_use":
                            current_tool = {"id": event.content_block.id, "name": event.content_block.name, "input_json": ""}
                        else:
                            current_tool = None
                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            collected_text += event.delta.text
                            full_response += event.delta.text
                            yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"
                        elif hasattr(event.delta, "partial_json") and current_tool:
                            current_tool["input_json"] += event.delta.partial_json
                    elif event.type == "content_block_stop":
                        if current_tool:
                            try:
                                tool_input = json.loads(current_tool["input_json"]) if current_tool["input_json"] else {}
                            except json.JSONDecodeError:
                                tool_input = {}
                            tool_uses.append({
                                "id": current_tool["id"],
                                "name": current_tool["name"],
                                "input": tool_input,
                            })
                            current_tool = None

                # Get the final message for building next turn
                final_message = await stream.get_final_message()

            if not tool_uses or tool_rounds >= MAX_TOOL_ROUNDS:
                break

            # Execute tools
            messages.append({"role": "assistant", "content": final_message.content})
            tool_results = []
            for tu in tool_uses:
                result = await execute_tool(db, tu["name"], tu["input"], member_id)
                actions.append({"tool": tu["name"], "input": tu["input"], "result": result})
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': tu['name'], 'result': result})}\n\n"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})
            tool_rounds += 1

        # Save and finalize
        await save_message(db, sid, "assistant", full_response, model=model,
                           tool_calls=json.dumps([{"tool": a["tool"], "input": a["input"]} for a in actions]) if actions else None)
        await db.commit()

        yield f"data: {json.dumps({'type': 'done', 'session_id': sid, 'actions': len(actions)})}\n\n"

    except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        log.warning(f"LLM unavailable ({e}), streaming Layer 1 fallback")
        fallback = await deterministic_fallback(message, member_id, db)
        await save_message(db, sid, "assistant", fallback, model="layer1_fallback")
        await db.commit()
        yield f"data: {json.dumps({'type': 'text', 'content': fallback})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'session_id': sid, 'fallback': True})}\n\n"
