"""LLM integration: system prompt, tool definitions, context assembly, conversation flow."""

import logging
import re
from datetime import date

from pib.db import get_config

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


# ─── Tool Definitions ───

TOOLS = [
    {"name": "create_task", "description": "Create a new task with title, assignee, due_date, energy, effort, micro_script"},
    {"name": "update_task_status", "description": "Change task status (uses state machine guards)"},
    {"name": "complete_task", "description": "Complete a task. Handles reward, streak, Zeigarnik hook."},
    {"name": "what_now", "description": "Get the ONE task this person should do next."},
    {"name": "add_list_items", "description": "Add items to a named list (grocery, costco, target, etc.)"},
    {"name": "search_items", "description": "Search ops_items by name, type, or FTS5 query"},
    {"name": "send_message", "description": "Queue a message for delivery. Non-household -> approval queue."},
    {"name": "query_schedule", "description": "Get calendar events for a date range"},
    {"name": "query_transactions", "description": "Search financial transactions"},
    {"name": "query_budget", "description": "Get budget snapshot with spending vs targets"},
    {"name": "save_memory", "description": "Save a persistent fact to long-term memory (with dedup)"},
    {"name": "recall_memory", "description": "Search long-term memory via FTS5"},
    {"name": "resolve_conflict", "description": "Mark a calendar conflict as resolved"},
    {"name": "undo_last", "description": "Reverse the last LLM-generated operation"},
    {"name": "approve_pending", "description": "Approve or reject a pending approval queue item"},
    {"name": "log_state", "description": "Log medication, sleep quality, or focus mode change"},
]


# ─── Conversation History ───

def build_conversation_history(messages: list[dict], channel: str) -> list[dict]:
    """Sliding window: keep recent messages within token budget."""
    max_messages = 10 if channel in ("sms", "imessage") else 50
    budget = TOKEN_BUDGETS["conversation_history"]

    recent = messages[-max_messages:]
    total_tokens = sum(estimate_tokens(m.get("content", "")) for m in recent)

    while total_tokens > budget and len(recent) > 2:
        removed = recent.pop(0)
        total_tokens -= estimate_tokens(removed.get("content", ""))

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
    """Build the always-on 500-token cross-domain summary."""
    row = await db.execute_fetchone(CROSS_DOMAIN_SUMMARY_SQL)
    if not row:
        return "No data available."

    parts = []
    if row["active_tasks"]:
        parts.append(f"Active tasks: {row['active_tasks']}")
    if row["overdue_tasks"]:
        parts.append(f"Overdue: {row['overdue_tasks']}")
    if row["due_today"]:
        parts.append(f"Due today: {row['due_today']}")
    if row["open_conflicts"]:
        parts.append(f"Calendar conflicts: {row['open_conflicts']}")
    if row["budget_alerts"]:
        parts.append(f"Budget alerts: {row['budget_alerts']}")
    if row["active_phase"]:
        parts.append(f"Phase: {row['active_phase']}")

    return " | ".join(parts) if parts else "All clear."


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
