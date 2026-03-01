"""FastAPI application: routes, middleware, health probe, SSE streaming."""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime

import aiosqlite
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pib.db import apply_schema, get_config, get_connection, next_id, set_config
from pib.engine import (
    DBSnapshot,
    WhatNowResult,
    can_transition,
    load_snapshot,
    transition_task,
    what_now,
)
from pib.rewards import complete_task_with_reward, select_reward

log = logging.getLogger(__name__)

# ─── Database singleton ───
_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await get_connection()
        await apply_schema(_db)
    return _db


# ─── App Lifespan ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await get_db()
    log.info("PIB v5 starting — database connected")
    yield
    if _db:
        await _db.close()
    log.info("PIB v5 shutdown")


app = FastAPI(title="PIB v5", version="5.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if directory exists
static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ═══════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health_probe():
    """External monitoring endpoint. Pure reads, no writes."""
    db = await get_db()
    checks = {}

    try:
        row = await db.execute_fetchone("SELECT COUNT(*) as c FROM common_members WHERE active=1")
        checks["db"] = {"ok": True, "members": row["c"] if row else 0}
    except Exception as e:
        checks["db"] = {"ok": False, "error": str(e)}

    all_ok = all(c.get("ok", False) for c in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks},
    )


# ═══════════════════════════════════════════════════════════════
# MEMBERS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/members")
async def list_members():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM common_members WHERE active = 1 ORDER BY display_name"
    )
    return [dict(r) for r in rows] if rows else []


@app.get("/api/members/{member_id}")
async def get_member(member_id: str):
    db = await get_db()
    row = await db.execute_fetchone("SELECT * FROM common_members WHERE id = ?", [member_id])
    if not row:
        raise HTTPException(404, "Member not found")
    return dict(row)


# ═══════════════════════════════════════════════════════════════
# WHAT-NOW (the core endpoint)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/what-now/{member_id}")
async def api_what_now(member_id: str):
    db = await get_db()
    snapshot = await load_snapshot(db, member_id)
    result = what_now(member_id, snapshot)
    return {
        "the_one_task": result.the_one_task,
        "context": result.context,
        "calendar_status": result.calendar_status,
        "energy_level": result.energy_level,
        "one_more_teaser": result.one_more_teaser,
        "completions_today": result.completions_today,
        "velocity_cap": result.velocity_cap,
    }


# ═══════════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/tasks")
async def list_tasks(
    member_id: str | None = None,
    status: str | None = None,
    domain: str | None = None,
):
    db = await get_db()
    query = "SELECT * FROM ops_tasks WHERE 1=1"
    params = []

    if member_id:
        query += " AND assignee = ?"
        params.append(member_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    if domain:
        query += " AND domain = ?"
        params.append(domain)

    query += " ORDER BY due_date ASC, created_at ASC"
    rows = await db.execute_fetchall(query, params)
    return [dict(r) for r in rows] if rows else []


@app.post("/api/tasks")
async def create_task(request: Request):
    db = await get_db()
    body = await request.json()
    task_id = await next_id(db, "tsk")

    from pib.ingest import generate_micro_script
    micro = body.get("micro_script") or generate_micro_script(body)

    await db.execute(
        "INSERT INTO ops_tasks (id, title, assignee, domain, item_type, due_date, "
        "scheduled_date, energy, effort, micro_script, notes, created_by, source_system) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            task_id,
            body["title"],
            body.get("assignee", "m-james"),
            body.get("domain", "tasks"),
            body.get("item_type", "task"),
            body.get("due_date"),
            body.get("scheduled_date"),
            body.get("energy"),
            body.get("effort", "small"),
            micro,
            body.get("notes"),
            body.get("created_by", "api"),
            "api",
        ],
    )
    await db.commit()
    row = await db.execute_fetchone("SELECT * FROM ops_tasks WHERE id = ?", [task_id])
    return dict(row)


@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, request: Request):
    db = await get_db()
    body = await request.json()

    new_status = body.get("status")
    if new_status:
        result = await transition_task(db, task_id, new_status, body, body.get("actor", "api"))
        return result

    # Non-status update
    sets = []
    params = []
    for field in ["title", "notes", "due_date", "energy", "effort", "micro_script", "domain", "assignee"]:
        if field in body:
            sets.append(f"{field} = ?")
            params.append(body[field])

    if not sets:
        raise HTTPException(400, "No fields to update")

    sets.append("updated_at = datetime('now')")
    params.append(task_id)
    await db.execute(f"UPDATE ops_tasks SET {', '.join(sets)} WHERE id = ?", params)
    await db.commit()

    row = await db.execute_fetchone("SELECT * FROM ops_tasks WHERE id = ?", [task_id])
    return dict(row) if row else {"task_id": task_id}


@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: str, request: Request):
    db = await get_db()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    member_id = body.get("member_id", "m-james")
    actor = body.get("actor", member_id)
    result = await complete_task_with_reward(db, task_id, member_id, actor)
    return result


# ═══════════════════════════════════════════════════════════════
# LISTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/lists/{list_name}")
async def get_list(list_name: str, show_checked: bool = False):
    db = await get_db()
    query = "SELECT * FROM ops_lists WHERE list_name = ?"
    params = [list_name]
    if not show_checked:
        query += " AND checked = 0"
    query += " ORDER BY added_at ASC"
    rows = await db.execute_fetchall(query, params)
    return [dict(r) for r in rows] if rows else []


@app.post("/api/lists/{list_name}")
async def add_list_items(list_name: str, request: Request):
    db = await get_db()
    body = await request.json()
    items = body.get("items", [])
    added = []
    for item in items:
        item_id = await next_id(db, "lst")
        text = item if isinstance(item, str) else item.get("text", "")
        await db.execute(
            "INSERT INTO ops_lists (id, list_name, item_text, added_by) VALUES (?, ?, ?, ?)",
            [item_id, list_name, text, body.get("member_id", "m-james")],
        )
        added.append({"id": item_id, "text": text})
    await db.commit()
    return {"list_name": list_name, "added": added}


@app.patch("/api/lists/{list_name}/{item_id}")
async def check_list_item(list_name: str, item_id: str):
    db = await get_db()
    await db.execute(
        "UPDATE ops_lists SET checked = 1, checked_at = datetime('now') WHERE id = ?",
        [item_id],
    )
    await db.commit()
    return {"id": item_id, "checked": True}


# ═══════════════════════════════════════════════════════════════
# SCHEDULE
# ═══════════════════════════════════════════════════════════════

@app.get("/api/schedule")
async def get_schedule(
    start_date: str | None = None,
    end_date: str | None = None,
    member_id: str | None = None,
):
    db = await get_db()
    start = start_date or date.today().isoformat()
    end = end_date or start

    from pib.llm import build_calendar_context

    context = await build_calendar_context(db, start, end, member_id or "m-james")

    rows = await db.execute_fetchall(
        "SELECT * FROM cal_classified_events WHERE event_date BETWEEN ? AND ? "
        "AND privacy IN ('full', 'privileged') ORDER BY event_date, start_time",
        [start, end],
    )
    events = []
    for r in rows or []:
        e = dict(r)
        if e["privacy"] == "privileged":
            e["title"] = e.get("title_redacted", "Meeting")
            e.pop("description", None)
        events.append(e)
    return events


# ═══════════════════════════════════════════════════════════════
# BUDGET / FINANCE
# ═══════════════════════════════════════════════════════════════

@app.get("/api/budget")
async def get_budget():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM fin_budget_snapshot ORDER BY category")
    return [dict(r) for r in rows] if rows else []


@app.get("/api/transactions")
async def get_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    limit: int = 50,
):
    db = await get_db()
    query = "SELECT * FROM fin_transactions WHERE 1=1"
    params: list = []

    if start_date:
        query += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND transaction_date <= ?"
        params.append(end_date)
    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY transaction_date DESC LIMIT ?"
    params.append(limit)
    rows = await db.execute_fetchall(query, params)
    return [dict(r) for r in rows] if rows else []


# ═══════════════════════════════════════════════════════════════
# MEMORY
# ═══════════════════════════════════════════════════════════════

@app.post("/api/memory")
async def save_memory(request: Request):
    db = await get_db()
    body = await request.json()
    from pib.memory import save_memory_deduped

    result = await save_memory_deduped(
        db,
        content=body["content"],
        category=body.get("category", "general"),
        domain=body.get("domain"),
        member_id=body.get("member_id", "m-james"),
        source=body.get("source", "api"),
    )
    await db.commit()
    return result


@app.get("/api/memory/search")
async def search_memory_api(q: str = Query(...)):
    db = await get_db()
    from pib.memory import search_memory
    results = await search_memory(db, q)
    return results


# ═══════════════════════════════════════════════════════════════
# SCOREBOARD
# ═══════════════════════════════════════════════════════════════

@app.get("/api/scoreboard-data")
async def scoreboard_data():
    db = await get_db()
    members = await db.execute_fetchall(
        "SELECT * FROM common_members WHERE active = 1 AND role IN ('parent', 'child')"
    )

    cards = []
    for m in members or []:
        member = dict(m)
        member_id = member["id"]

        # Streak
        streak_row = await db.execute_fetchone(
            "SELECT current_streak, best_streak FROM ops_streaks "
            "WHERE member_id = ? AND streak_type = 'daily_completion'",
            [member_id],
        )
        streak = streak_row["current_streak"] if streak_row else 0

        # Today count
        today_row = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM ops_tasks WHERE completed_by = ? AND completed_at >= date('now') AND status = 'done'",
            [member_id],
        )
        done_today = today_row["c"] if today_row else 0

        # Week count + points
        week_row = await db.execute_fetchone(
            "SELECT COUNT(*) as c, COALESCE(SUM(points), 0) as pts FROM ops_tasks "
            "WHERE completed_by = ? AND completed_at >= date('now', '-7 days') AND status = 'done'",
            [member_id],
        )
        week_count = week_row["c"] if week_row else 0
        week_points = week_row["pts"] if week_row else 0

        # Next task
        snapshot = await load_snapshot(db, member_id)
        wn = what_now(member_id, snapshot)

        cards.append({
            "member_id": member_id,
            "display_name": member["display_name"],
            "role": member["role"],
            "streak": streak,
            "done_today": done_today,
            "week_count": week_count,
            "week_points": week_points,
            "next_task": wn.the_one_task.get("title") if wn.the_one_task else None,
        })

    # Family total
    total_week = sum(c["week_count"] for c in cards)

    return {
        "cards": cards,
        "family_total_week": total_week,
    }


@app.get("/scoreboard", response_class=HTMLResponse)
async def scoreboard_page():
    """Kitchen TV scoreboard — standalone page."""
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>PIB Scoreboard</title>
<style>body{background:#1a1a2e;color:#eee;font-family:sans-serif;margin:40px;}</style>
<script>
setInterval(async()=>{
  const r=await fetch('/api/scoreboard-data');
  const d=await r.json();
  document.getElementById('data').textContent=JSON.stringify(d,null,2);
},60000);
window.onload=async()=>{
  const r=await fetch('/api/scoreboard-data');
  const d=await r.json();
  document.getElementById('data').textContent=JSON.stringify(d,null,2);
};
</script></head>
<body><h1>PIB Scoreboard</h1><pre id="data">Loading...</pre></body></html>"""


# ═══════════════════════════════════════════════════════════════
# CHAT (SSE Streaming)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Handle a chat message with full LLM integration. Falls back to Layer 1 if API unavailable."""
    db = await get_db()
    body = await request.json()
    message = body.get("message", "")
    member_id = body.get("member_id", "m-james")
    channel = body.get("channel", "web")
    session_id = body.get("session_id")

    # Check for prefix commands first (Layer 1 — no LLM needed)
    from pib.ingest import parse_prefix
    prefix_result = parse_prefix(message)
    if prefix_result:
        from pib.ingest import IngestEvent, route_prefix
        event = IngestEvent(
            source="web_chat",
            timestamp=datetime.now().isoformat(),
            idempotency_key="",
            raw={},
            text=message,
            member_id=member_id,
        )
        result = await route_prefix(db, prefix_result, event)
        await db.commit()
        return {"response": json.dumps(result), "actions": [result]}

    # Full LLM conversation flow (Layer 2 with Layer 1 fallback)
    from pib.llm import chat as llm_chat
    result = await llm_chat(db, message, member_id, channel, session_id)
    return result


@app.post("/api/chat/send")
async def chat_send(request: Request):
    """Send a chat message. Returns session_id for streaming via /api/chat/stream."""
    db = await get_db()
    body = await request.json()
    message = body.get("message", body.get("text", ""))
    member_id = body.get("member_id", "m-james")
    channel = body.get("channel", "web")
    session_id = body.get("session_id")

    from pib.llm import chat as llm_chat
    result = await llm_chat(db, message, member_id, channel, session_id)
    return result


@app.get("/api/chat/stream")
async def chat_stream(
    session_id: str | None = None,
    member_id: str = "m-james",
    message: str = "",
    channel: str = "web",
):
    """SSE streaming endpoint for chat. Connect and send message via query params."""
    db = await get_db()

    if not message:
        return JSONResponse(400, {"error": "message parameter required"})

    from pib.llm import stream_chat
    return StreamingResponse(
        stream_chat(db, message, member_id, channel, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/chat/history")
async def chat_history(session_id: str):
    """Get conversation history for a session."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT role, content, tool_calls, model, tokens_in, tokens_out, created_at "
        "FROM mem_messages WHERE session_id = ? ORDER BY created_at",
        [session_id],
    )
    return [dict(r) for r in rows] if rows else []


# ═══════════════════════════════════════════════════════════════
# CUSTODY
# ═══════════════════════════════════════════════════════════════

@app.get("/api/custody")
async def get_custody(query_date: str | None = None):
    db = await get_db()
    from pib.custody import who_has_child

    qdate = date.fromisoformat(query_date) if query_date else date.today()
    config_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    if not config_row:
        return {"date": qdate.isoformat(), "custody": "no_config"}

    parent_id = who_has_child(qdate, dict(config_row))
    member = await db.execute_fetchone("SELECT display_name FROM common_members WHERE id = ?", [parent_id])
    return {
        "date": qdate.isoformat(),
        "parent_id": parent_id,
        "parent_name": member["display_name"] if member else parent_id,
    }


# ═══════════════════════════════════════════════════════════════
# ENERGY / STATE
# ═══════════════════════════════════════════════════════════════

@app.post("/api/state")
async def log_state(request: Request):
    db = await get_db()
    body = await request.json()
    member_id = body.get("member_id", "m-james")
    action = body.get("action")
    value = body.get("value")

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
        await db.execute(
            "INSERT INTO pib_energy_states (member_id, state_date, focus_mode) "
            "VALUES (?, date('now'), ?) "
            "ON CONFLICT(member_id, state_date) DO UPDATE SET focus_mode = ?",
            [member_id, 1 if value else 0, 1 if value else 0],
        )

    await db.commit()
    return {"status": "ok", "action": action}


# ═══════════════════════════════════════════════════════════════
# SETTINGS / CONFIG
# ═══════════════════════════════════════════════════════════════

@app.get("/api/config")
async def get_all_config():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT key, value, description FROM pib_config ORDER BY key")
    return {r["key"]: {"value": r["value"], "description": r["description"]} for r in rows} if rows else {}


@app.put("/api/config/{key}")
async def update_config(key: str, request: Request):
    db = await get_db()
    body = await request.json()
    await set_config(db, key, body["value"], actor=body.get("actor", "api"))
    return {"key": key, "value": body["value"]}


# ═══════════════════════════════════════════════════════════════
# WEBHOOKS
# ═══════════════════════════════════════════════════════════════

@app.post("/webhooks/twilio")
async def twilio_webhook(request: Request):
    """Handle inbound Twilio SMS."""
    db = await get_db()
    form = await request.form()
    from pib.ingest import IngestEvent, ingest, make_idempotency_key

    event = IngestEvent(
        source="twilio",
        timestamp=datetime.now().isoformat(),
        idempotency_key=make_idempotency_key("sms", form.get("MessageSid", "")),
        raw=dict(form),
        text=form.get("Body", ""),
        reply_channel="sms",
        reply_address=form.get("From", ""),
    )

    actions = await ingest(event, db)
    return {"status": "ok", "actions": len(actions)}


@app.post("/webhooks/bluebubbles")
async def bluebubbles_webhook(request: Request):
    """Handle inbound BlueBubbles iMessage."""
    db = await get_db()
    body = await request.json()
    from pib.ingest import IngestEvent, ingest, make_idempotency_key

    event = IngestEvent(
        source="imessage",
        timestamp=datetime.now().isoformat(),
        idempotency_key=make_idempotency_key("imessage", body.get("guid", "")),
        raw=body,
        text=body.get("text", ""),
        reply_channel="imessage",
        reply_address=body.get("handle", ""),
    )

    actions = await ingest(event, db)
    return {"status": "ok", "actions": len(actions)}


@app.post("/webhooks/siri")
async def siri_webhook(request: Request):
    """Handle inbound Siri Shortcut."""
    db = await get_db()
    body = await request.json()
    from pib.ingest import IngestEvent, ingest, make_idempotency_key

    event = IngestEvent(
        source="siri",
        timestamp=datetime.now().isoformat(),
        idempotency_key=make_idempotency_key("siri", f"{body.get('ts', '')}:{body.get('text', '')}"),
        raw=body,
        text=body.get("text", ""),
        member_id=body.get("member_id", "m-james"),
    )

    actions = await ingest(event, db)
    return {"status": "ok", "actions": len(actions)}


@app.post("/webhooks/sheets")
async def sheets_webhook(request: Request):
    """Handle Google Sheets onChange webhook."""
    db = await get_db()
    body = await request.json()
    from pib.sheets import handle_sheets_webhook
    result = await handle_sheets_webhook(db, body)
    return result


# ═══════════════════════════════════════════════════════════════
# APPROVAL QUEUE
# ═══════════════════════════════════════════════════════════════

@app.get("/api/approvals")
async def list_approvals(status: str = "pending"):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM mem_approval_queue WHERE status = ? ORDER BY requested_at DESC",
        [status],
    )
    return [dict(r) for r in rows] if rows else []


@app.post("/api/approvals/{approval_id}")
async def decide_approval(approval_id: str, request: Request):
    db = await get_db()
    body = await request.json()
    decision = body.get("decision")  # "approved" or "rejected"
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "Decision must be 'approved' or 'rejected'")

    await db.execute(
        "UPDATE mem_approval_queue SET status = ?, decided_by = ?, decided_at = datetime('now') WHERE id = ?",
        [decision, body.get("decided_by", "api"), approval_id],
    )
    await db.commit()
    return {"id": approval_id, "status": decision}


# ═══════════════════════════════════════════════════════════════
# ITEMS (Contacts, Vendors, Assets — ops_items)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/items")
async def list_items(type: str | None = None, status: str = "active"):
    db = await get_db()
    query = "SELECT * FROM ops_items WHERE status = ?"
    params: list = [status]
    if type:
        query += " AND type = ?"
        params.append(type)
    query += " ORDER BY name"
    rows = await db.execute_fetchall(query, params)
    return [dict(r) for r in rows] if rows else []


@app.post("/api/items")
async def create_item(request: Request):
    db = await get_db()
    body = await request.json()
    item_id = await next_id(db, "itm")
    await db.execute(
        "INSERT INTO ops_items (id, name, type, category, domain, phone, email, notes, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            item_id, body["name"], body["type"],
            body.get("category"), body.get("domain"),
            body.get("phone"), body.get("email"),
            body.get("notes"), json.dumps(body.get("metadata", {})),
        ],
    )
    await db.commit()
    row = await db.execute_fetchone("SELECT * FROM ops_items WHERE id = ?", [item_id])
    return dict(row)


# ═══════════════════════════════════════════════════════════════
# STREAKS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/streaks/{member_id}")
async def get_streaks(member_id: str):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM ops_streaks WHERE member_id = ?", [member_id]
    )
    return [dict(r) for r in rows] if rows else []


# ═══════════════════════════════════════════════════════════════
# TODAY STREAM (James carousel — SSE)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/today-stream")
async def today_stream(member_id: str = "m-james"):
    """SSE stream of whatNow + calendar + custody for the Today page carousel."""
    db = await get_db()

    snapshot = await load_snapshot(db, member_id)
    wn = what_now(member_id, snapshot)

    from pib.llm import build_calendar_context
    today = date.today().isoformat()
    calendar = await build_calendar_context(db, today, today, member_id)

    from pib.custody import who_has_child
    config_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    custody = None
    if config_row:
        parent_id = who_has_child(date.today(), dict(config_row))
        parent = await db.execute_fetchone("SELECT display_name FROM common_members WHERE id = ?", [parent_id])
        custody = {"parent_id": parent_id, "parent_name": parent["display_name"] if parent else parent_id}

    streak_row = await db.execute_fetchone(
        "SELECT current_streak FROM ops_streaks WHERE member_id = ? AND streak_type = 'daily_completion'",
        [member_id],
    )

    return {
        "the_one_task": wn.the_one_task,
        "context": wn.context,
        "energy_level": wn.energy_level,
        "calendar_status": wn.calendar_status,
        "one_more_teaser": wn.one_more_teaser,
        "completions_today": wn.completions_today,
        "velocity_cap": wn.velocity_cap,
        "calendar": calendar,
        "custody": custody,
        "streak": streak_row["current_streak"] if streak_row else 0,
    }


# ═══════════════════════════════════════════════════════════════
# TASK SKIP
# ═══════════════════════════════════════════════════════════════

@app.post("/api/tasks/{task_id}/skip")
async def skip_task(task_id: str, request: Request):
    """Skip a task — defers it to tomorrow."""
    db = await get_db()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    from pib.engine import transition_task
    tomorrow = (date.today().replace(day=date.today().day + 1)).isoformat()
    result = await transition_task(
        db, task_id, "deferred",
        {"scheduled_date": body.get("scheduled_date", tomorrow),
         "notes": body.get("notes", "Skipped")},
        body.get("actor", "user"),
    )
    return result


# ═══════════════════════════════════════════════════════════════
# DECISIONS (Laura's queue)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/decisions")
async def get_decisions(member_id: str = "m-laura"):
    """Get pending decisions/approvals for a member."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM mem_approval_queue WHERE (requested_by = ? OR status = 'pending') "
        "ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END, requested_at DESC",
        [member_id],
    )
    return [dict(r) for r in rows] if rows else []


# ═══════════════════════════════════════════════════════════════
# CHORES (Charlie's system)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/chores")
async def get_chores(member_id: str = "m-charlie"):
    """Get chores for a member (typically Charlie)."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM ops_tasks WHERE assignee = ? AND item_type = 'chore' "
        "AND status NOT IN ('done', 'dismissed') ORDER BY due_date",
        [member_id],
    )
    return [dict(r) for r in rows] if rows else []


@app.post("/api/chores/{chore_id}/toggle")
async def toggle_chore(chore_id: str):
    """Toggle a chore done/not-done (simplified for child UI)."""
    db = await get_db()
    row = await db.execute_fetchone("SELECT status FROM ops_tasks WHERE id = ?", [chore_id])
    if not row:
        raise HTTPException(404, "Chore not found")

    if row["status"] == "done":
        await db.execute(
            "UPDATE ops_tasks SET status = 'next', completed_at = NULL, completed_by = NULL WHERE id = ?",
            [chore_id],
        )
    else:
        from pib.rewards import complete_task_with_reward
        await complete_task_with_reward(db, chore_id, "m-charlie", "m-charlie")

    await db.commit()
    updated = await db.execute_fetchone("SELECT * FROM ops_tasks WHERE id = ?", [chore_id])
    return dict(updated)


# ═══════════════════════════════════════════════════════════════
# HOUSEHOLD STATUS (aggregate dashboard)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/household-status")
async def household_status():
    """Aggregate household status for the home page."""
    db = await get_db()

    from pib.custody import who_has_child
    config_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    custody = None
    if config_row:
        parent_id = who_has_child(date.today(), dict(config_row))
        custody = parent_id

    tasks_row = await db.execute_fetchone(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status = 'done' AND completed_at >= date('now') THEN 1 ELSE 0 END) as done_today, "
        "SUM(CASE WHEN due_date < date('now') AND status NOT IN ('done','dismissed','deferred') THEN 1 ELSE 0 END) as overdue "
        "FROM ops_tasks WHERE status NOT IN ('done','dismissed')"
    )

    budget_row = await db.execute_fetchone(
        "SELECT COUNT(*) as alerts FROM fin_budget_snapshot WHERE over_threshold = 1"
    )

    conflicts_row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM cal_conflicts WHERE status = 'unresolved'"
    )

    members = await db.execute_fetchall(
        "SELECT m.id, m.display_name, s.current_streak FROM common_members m "
        "LEFT JOIN ops_streaks s ON m.id = s.member_id AND s.streak_type = 'daily_completion' "
        "WHERE m.active = 1 AND m.role IN ('parent', 'child')"
    )

    phase = await db.execute_fetchone(
        "SELECT name, status FROM common_life_phases WHERE status = 'active' LIMIT 1"
    )

    return {
        "custody_today": custody,
        "tasks": {
            "active": tasks_row["total"] if tasks_row else 0,
            "done_today": tasks_row["done_today"] if tasks_row else 0,
            "overdue": tasks_row["overdue"] if tasks_row else 0,
        },
        "budget_alerts": budget_row["alerts"] if budget_row else 0,
        "unresolved_conflicts": conflicts_row["c"] if conflicts_row else 0,
        "members": [{"id": m["id"], "name": m["display_name"], "streak": m["current_streak"] or 0} for m in members] if members else [],
        "active_phase": dict(phase) if phase else None,
    }


# ═══════════════════════════════════════════════════════════════
# PEOPLE (Contacts, Comms, Observations, Autonomy)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/people/contacts")
async def get_contacts():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM ops_items WHERE type = 'person' AND status = 'active' ORDER BY name"
    )
    return [dict(r) for r in rows] if rows else []


@app.get("/api/people/comms")
async def get_people_comms(limit: int = 20):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM ops_comms ORDER BY date DESC LIMIT ?", [limit]
    )
    return [dict(r) for r in rows] if rows else []


@app.get("/api/people/observations")
async def get_observations():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM mem_long_term WHERE category = 'observations' AND superseded_by IS NULL "
        "ORDER BY created_at DESC LIMIT 50"
    )
    return [dict(r) for r in rows] if rows else []


@app.get("/api/people/autonomy-tiers")
async def get_autonomy_tiers():
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, name, type, autonomy_tier FROM ops_items WHERE type = 'person' AND autonomy_tier IS NOT NULL "
        "ORDER BY autonomy_tier, name"
    )
    return [dict(r) for r in rows] if rows else []


# ═══════════════════════════════════════════════════════════════
# COSTS / SOURCES / PHASES (Settings)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/costs")
async def get_costs():
    db = await get_db()
    monthly_spend = await get_config(db, "api_cost_this_month") or "0"
    monthly_budget = await get_config(db, "monthly_api_budget") or "30"
    return {
        "this_month": float(monthly_spend),
        "budget": float(monthly_budget),
        "percentage": round(float(monthly_spend) / float(monthly_budget) * 100, 1) if float(monthly_budget) > 0 else 0,
    }


@app.get("/api/sources")
async def get_sources():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM cal_sources ORDER BY source_name")
    return [dict(r) for r in rows] if rows else []


@app.get("/api/phases")
async def get_phases():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM common_life_phases ORDER BY start_date")
    return [dict(r) for r in rows] if rows else []


# ═══════════════════════════════════════════════════════════════
# COMMS DOMAIN
# ═══════════════════════════════════════════════════════════════

from pib import comms as comms_module
from pib import voice as voice_module


@app.get("/api/comms/inbox")
async def comms_inbox(
    visibility: str = "normal",
    needs_response: bool | None = None,
    urgency: str | None = None,
    channel: str | None = None,
    member_id: str | None = None,
    batch_window: str | None = None,
    batch_date: str | None = None,
    draft_status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    db = await get_db()
    return await comms_module.get_comms_inbox(
        db,
        visibility=visibility,
        needs_response=needs_response,
        urgency=urgency,
        channel=channel,
        member_id=member_id,
        batch_window=batch_window,
        batch_date=batch_date,
        draft_status=draft_status,
        search=search,
        limit=limit,
        offset=offset,
    )


@app.get("/api/comms/counts")
async def comms_counts():
    db = await get_db()
    return await comms_module.get_comms_counts(db)


@app.get("/api/comms/{comm_id}")
async def comms_detail(comm_id: str):
    db = await get_db()
    comm = await comms_module.get_comm_by_id(db, comm_id)
    if not comm:
        raise HTTPException(status_code=404, detail="Comm not found")
    return comm


@app.post("/api/comms/{comm_id}/mark-responded")
async def comms_mark_responded(comm_id: str, request: Request):
    db = await get_db()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    outcome = body.get("outcome", "responded")
    await comms_module.mark_responded(db, comm_id, outcome)
    return {"ok": True, "comm_id": comm_id}


@app.post("/api/comms/{comm_id}/snooze")
async def comms_snooze(comm_id: str, request: Request):
    db = await get_db()
    body = await request.json()
    until = body.get("until")
    if not until:
        raise HTTPException(status_code=400, detail="'until' datetime required")
    await comms_module.snooze_comm(db, comm_id, until)
    return {"ok": True, "comm_id": comm_id, "snoozed_until": until}


@app.post("/api/comms/{comm_id}/tag")
async def comms_tag(comm_id: str, request: Request):
    db = await get_db()
    body = await request.json()
    tag = body.get("tag")
    if not tag:
        raise HTTPException(status_code=400, detail="'tag' required")
    await comms_module.tag_comm(db, comm_id, tag)
    return {"ok": True, "comm_id": comm_id, "tag": tag}


@app.post("/api/comms/{comm_id}/approve-draft")
async def comms_approve_draft(comm_id: str, request: Request):
    db = await get_db()
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    edited_body = body.get("edited_body")
    result = await comms_module.approve_draft(db, comm_id, edited_body)
    if not result:
        raise HTTPException(status_code=400, detail="No pending draft for this comm")
    return {"ok": True, "comm_id": comm_id, "draft_status": "approved"}


@app.post("/api/comms/{comm_id}/reject-draft")
async def comms_reject_draft(comm_id: str):
    db = await get_db()
    await comms_module.reject_draft(db, comm_id)
    return {"ok": True, "comm_id": comm_id, "draft_status": "rejected"}


@app.post("/api/comms/{comm_id}/reply")
async def comms_reply(comm_id: str, request: Request):
    db = await get_db()
    body = await request.json()
    reply_text = body.get("body")
    if not reply_text:
        raise HTTPException(status_code=400, detail="'body' required")

    # Mark original as responded
    await comms_module.mark_responded(db, comm_id, "responded")

    # Collect voice sample from direct reply
    comm = await comms_module.get_comm_by_id(db, comm_id)
    if comm:
        try:
            await voice_module.collect_voice_sample(
                db,
                member_id=comm.get("member_id", "m-james"),
                body=reply_text,
                channel=comm.get("channel", "unknown"),
                comm_type=comm.get("comm_type"),
                recipient_type=None,
                item_ref=comm.get("item_ref"),
            )
        except Exception as e:
            log.warning(f"Voice sample collection failed (non-fatal): {e}")

    return {"ok": True, "comm_id": comm_id, "replied": True}


@app.post("/api/comms/{comm_id}/extraction/{index}/approve")
async def comms_extraction_approve(comm_id: str, index: int):
    db = await get_db()
    item = await comms_module.approve_extraction(db, comm_id, index)
    if not item:
        raise HTTPException(status_code=400, detail="Invalid comm or extraction index")
    return {"ok": True, "comm_id": comm_id, "index": index, "item": item}


@app.post("/api/comms/{comm_id}/extraction/{index}/reject")
async def comms_extraction_reject(comm_id: str, index: int):
    db = await get_db()
    result = await comms_module.reject_extraction(db, comm_id, index)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid comm or extraction index")
    return {"ok": True, "comm_id": comm_id, "index": index}


@app.post("/api/comms/capture")
async def comms_capture(request: Request):
    db = await get_db()
    body = await request.json()
    member_id = body.get("member_id", "m-james")
    if "summary" not in body:
        raise HTTPException(status_code=400, detail="'summary' required")
    comm_id = await comms_module.capture_manual(db, member_id, body)
    return {"ok": True, "comm_id": comm_id}


@app.get("/api/voice/profiles")
async def voice_profiles(member: str = "m-james"):
    db = await get_db()
    profiles = await voice_module.get_profiles(db, member)
    stats = await voice_module.get_corpus_stats(db, member)
    return {"profiles": profiles, "stats": stats}


# ═══════════════════════════════════════════════════════════════
# APP ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    import uvicorn
    port = int(os.environ.get("PIB_PORT", "3141"))
    host = os.environ.get("PIB_HOST", "0.0.0.0")
    uvicorn.run("pib.web:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
