"""Context assembly, relevance detection, and token budgeting for LLM prompts.

Extracted from llm.py — pure refactor, no logic changes.
"""

import json
import logging
import re
from datetime import date

from pib.db import get_config

log = logging.getLogger(__name__)

__all__ = [
    "TOKEN_BUDGETS",
    "estimate_tokens",
    "enforce_budget",
    "FINANCIAL_TRIGGERS",
    "SCHEDULE_TRIGGERS",
    "TASK_TRIGGERS",
    "COVERAGE_TRIGGERS",
    "COMMS_TRIGGERS",
    "CAPTURE_TRIGGERS",
    "PROJECT_TRIGGERS",
    "build_entity_cache",
    "analyze_relevance",
    "build_system_prompt",
    "build_cross_domain_summary",
    "build_calendar_context",
    "assemble_context",
    "build_conversation_history",
    "CROSS_DOMAIN_SUMMARY_SQL",
]

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
    (SELECT COUNT(*) FROM ops_tasks WHERE assignee = ? AND status NOT IN ('done','dismissed')) AS active_tasks,
    (SELECT COUNT(*) FROM ops_tasks WHERE assignee = ? AND due_date < date('now') AND status NOT IN ('done','dismissed','deferred')) AS overdue_tasks,
    (SELECT COUNT(*) FROM ops_tasks WHERE assignee = ? AND due_date = date('now') AND status NOT IN ('done','dismissed')) AS due_today,
    (SELECT COUNT(*) FROM cal_conflicts WHERE status = 'unresolved') AS open_conflicts,
    (SELECT SUM(CASE WHEN over_threshold = 1 THEN 1 ELSE 0 END) FROM fin_budget_snapshot) AS budget_alerts,
    (SELECT name FROM common_life_phases WHERE status = 'active' LIMIT 1) AS active_phase
"""


async def build_cross_domain_summary(db, member_id: str = "m-james") -> str:
    """Build the always-on ~500-token cross-domain summary.

    Enriched with sensor data when available:
    - Weather summary (temp, condition, alerts)
    - Sun times (sunrise/sunset)
    - Per-member health context (privacy-filtered)
    - Home occupancy
    - Deliveries
    - Active sensor alerts
    """
    row = await db.execute_fetchone(CROSS_DOMAIN_SUMMARY_SQL, [member_id, member_id, member_id])
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
        pass

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
        pass

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
        pass

    return lines


# ─── Privacy-Filtered Calendar Context ───

async def build_calendar_context(db, start_date: str, end_date: str, member_id: str) -> str:
    """Calendar context with privacy + member filtering at the read layer.

    Only returns events that are household-wide (for_member_ids = '[]') or
    that include the requesting member in their for_member_ids JSON array.
    """
    events = await db.execute_fetchall(
        "SELECT * FROM cal_classified_events "
        "WHERE event_date BETWEEN ? AND ? "
        "AND (for_member_ids = '[]' OR for_member_ids LIKE '%' || ? || '%') "
        "ORDER BY start_time",
        [start_date, end_date, member_id],
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

    # Cross-domain summary (always included, scoped to member)
    summary = await build_cross_domain_summary(db, member_id=member_id)
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

    # Memory injection (scoped to requesting member)
    from pib.memory import search_memory
    search_terms = " ".join(w for w in message.split() if len(w) > 3)[:50]
    if search_terms:
        memories = await search_memory(db, search_terms, limit=5, member_id=member_id)
        if memories:
            mem_lines = [f"  - {m['content']}" for m in memories]
            parts.append(f"RELEVANT MEMORIES:\n" + "\n".join(mem_lines))

    # Capture injection
    try:
        from pib.capture import list_captures, search_captures_fts
        pinned = await list_captures(db, member_id, pinned_only=True, limit=5)
        if pinned:
            pin_lines = [f"  - [{c['capture_type']}] {c.get('title') or c['raw_text'][:80]}" for c in pinned]
            parts.append(f"PINNED CAPTURES:\n" + "\n".join(pin_lines))

        if "captures" in relevance["assemblers"] and search_terms:
            matched = await search_captures_fts(db, search_terms, member_id, include_household=True, limit=5)
            if matched:
                cap_lines = [f"  - [{c['capture_type']}] {c.get('title') or c['raw_text'][:80]}" for c in matched]
                parts.append(f"RELEVANT CAPTURES:\n" + "\n".join(cap_lines))
    except Exception:
        pass

    # Project context injection
    try:
        if "projects" in relevance["assemblers"]:
            from pib.project.context import assemble_project_context
            proj_ctx = await assemble_project_context(db, member_id)
            if proj_ctx:
                parts.append(f"ACTIVE PROJECTS:\n{proj_ctx}")
    except Exception:
        pass

    context = "\n\n".join(parts)
    return enforce_budget("assembled_context", context)
