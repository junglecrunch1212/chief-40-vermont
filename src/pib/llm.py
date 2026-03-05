"""LLM integration: Anthropic client, conversation flow, session management.

NOTE: In OpenClaw deployment, LLM calls are typically handled by the OpenClaw agent.
This module is used for direct CLI invocations (e.g., pib.cli context, pib.cli chat)
that need to compose LLM responses independently. The ANTHROPIC_API_KEY env var must be set.

Context assembly and relevance detection live in pib.context.
Tool definitions and execution live in pib.llm_tools.
"""

import json
import logging
import os
from datetime import date

import anthropic

from pib.db import next_id

# Re-export everything that was previously importable from pib.llm
from pib.context import (
    TOKEN_BUDGETS,
    estimate_tokens,
    enforce_budget,
    FINANCIAL_TRIGGERS,
    SCHEDULE_TRIGGERS,
    TASK_TRIGGERS,
    COVERAGE_TRIGGERS,
    COMMS_TRIGGERS,
    CAPTURE_TRIGGERS,
    PROJECT_TRIGGERS,
    build_entity_cache,
    analyze_relevance,
    get_model,
    select_model_tier,
    build_system_prompt,
    build_conversation_history,
    CROSS_DOMAIN_SUMMARY_SQL,
    build_cross_domain_summary,
    build_calendar_context,
    assemble_context,
)
from pib.llm_tools import (
    TOOLS,
    execute_tool,
    _tool_undo_last,
)

log = logging.getLogger(__name__)

# ─── Anthropic Client ───

_client: anthropic.AsyncAnthropic | None = None


_NO_API_KEY = False


def get_client() -> anthropic.AsyncAnthropic | None:
    """Get or create the Anthropic async client.

    Returns None if ANTHROPIC_API_KEY is not set (fallback to deterministic responses).
    """
    global _client, _NO_API_KEY
    if _NO_API_KEY:
        return None
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            log.warning(
                "ANTHROPIC_API_KEY not set — LLM calls will fall back to deterministic responses. "
                "Set the env var for full LLM functionality."
            )
            _NO_API_KEY = True
            return None
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


# ─── Session Management ───

async def get_or_create_session(db, member_id: str, channel: str, session_id: str | None = None) -> dict:
    """Get existing session or create new one."""
    if session_id:
        row = await db.execute_fetchone("SELECT * FROM mem_sessions WHERE id = ? AND active = 1", [session_id])
        if row:
            return dict(row)

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
               session_id: str | None = None, agent_id: str = "cos") -> dict:
    """Non-streaming chat handler. Returns complete response after all tool rounds."""
    session = await get_or_create_session(db, member_id, channel, session_id)
    sid = session["id"]

    await save_message(db, sid, "user", message)

    member = await db.execute_fetchone("SELECT * FROM common_members WHERE id = ?", [member_id])
    if not member:
        return {"response": "Unknown member.", "session_id": sid, "actions": []}
    member = dict(member)

    protocols = await db.execute_fetchall("SELECT * FROM pib_coach_protocols WHERE active = 1")
    system_prompt = build_system_prompt(member, channel, [dict(p) for p in protocols] if protocols else [])

    context = await assemble_context(db, member_id, message, agent_id=agent_id)

    history_msgs = await get_session_messages(db, sid)
    history = build_conversation_history(history_msgs, channel)
    if history and history[-1].get("role") == "user" and history[-1].get("content") == message:
        history = history[:-1]

    messages = list(history)
    user_content = message
    if context:
        user_content = f"[CONTEXT]\n{context}\n[/CONTEXT]\n\n{message}"
    messages.append({"role": "user", "content": user_content})

    items_rows = await db.execute_fetchall("SELECT id, name FROM ops_items WHERE status = 'active' LIMIT 50")
    entity_cache = build_entity_cache([dict(r) for r in items_rows] if items_rows else [])
    relevance = analyze_relevance(message, entity_cache)
    tier = select_model_tier(relevance["assemblers"], channel)
    model = await get_model(db, tier)

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

        if response.usage:
            from pib.cost import track_api_cost
            await track_api_cost(db, response.usage.input_tokens, response.usage.output_tokens, model)

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
                      session_id: str | None = None, agent_id: str = "cos"):
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

    context = await assemble_context(db, member_id, message, agent_id=agent_id)
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

                final_message = await stream.get_final_message()

            if not tool_uses or tool_rounds >= MAX_TOOL_ROUNDS:
                break

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
