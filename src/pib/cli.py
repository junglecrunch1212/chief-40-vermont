"""CLI permission boundary for PIB v5 OpenClaw integration.

Entry point: python -m pib.cli <command> <db_path> [--json '{}'] [--member m-james]

All output is JSON to stdout, all errors to stderr.
Reads PIB_CALLER_AGENT env var (default: dev).
Loads config/agent_capabilities.yaml and config/governance.yaml.

Permission enforcement (6 layers):
  1. Agent allowlist check against agent_capabilities.yaml
  2. Governance gate check against governance.yaml
  3. SQL guard: CLI never exposes raw SQL execution to agents
  4. Write-rate tracking: count writes in mem_cos_activity over last 60s, block if >= 3
  5. Output sanitizer: regex-strip API keys, redact privileged calendar titles for non-dev
  6. Audit: every invocation logged to mem_cos_activity
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from pib.tz import now_et

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
AGENT_CAPS_PATH = CONFIG_DIR / "agent_capabilities.yaml"
GOVERNANCE_PATH = CONFIG_DIR / "governance.yaml"

# Command classification for governance gate mapping
WRITE_COMMANDS = {
    "task-create", "task-complete", "task-update", "task-snooze",
    "hold-create", "hold-confirm", "hold-reject",
    "recurring-done", "recurring-skip",
    "state-update", "capture",
    "run-proactive-checks", "webhook-receive", "sensor-ingest",
    "member-settings-set",
    # Channel commands (writes)
    "channel-enable", "channel-disable", "channel-step-done",
    "channel-add", "channel-update",
    "channel-grant-access", "channel-revoke-access", "channel-setup-member",
    "device-status",
    # Chat and comms commands
    "chat-stream", "comms-approve-draft", "comms-respond", "comms-snooze",
    # Calendar ingest
    "calendar-ingest",
}
ADMIN_COMMANDS = {"bootstrap", "backup", "migrate"}
READ_COMMANDS = {
    "what-now", "calendar-query", "custody", "budget", "search",
    "morning-digest", "health", "streak", "upcoming", "scoreboard-data",
    "member-settings-get", "bootstrap-verify", "context",
    # Channel commands (reads)
    "channel-list", "channel-status", "channel-onboarding", "channel-test",
    "channel-send-enum", "channel-member-list",
    "device-list", "account-list",
}

# Map CLI commands to governance action_gates keys
COMMAND_TO_GATE = {
    "task-create": "task_create",
    "task-complete": "task_complete",
    "task-update": "task_update",
    "task-snooze": "task_snooze",
    "hold-create": "calendar_hold_create",
    "hold-confirm": "calendar_hold_confirm",
    "hold-reject": "calendar_hold_reject",
    "recurring-done": "recurring_mark_done",
    "recurring-skip": "recurring_mark_skip",
    "state-update": "state_update",
    "capture": "capture_create",
    "webhook-receive": "webhook_receive",
    "run-proactive-checks": "run_proactive_checks",
    "member-settings-set": "member_settings_set",
    # Channel commands
    "channel-enable": "channel_enable",
    "channel-disable": "channel_disable",
    "channel-add": "channel_add",
    "channel-update": "channel_update",
    "channel-grant-access": "channel_grant_access",
    "channel-revoke-access": "channel_revoke_access",
    "channel-setup-member": "channel_setup_member",
    # Chat and comms commands
    "chat-stream": "capture_create",
    "comms-approve-draft": "comms_approve_draft",
    "comms-respond": "comms_respond",
    "comms-snooze": "comms_snooze",
    # Calendar ingest
    "calendar-ingest": "webhook_receive",
}

ALL_COMMANDS = READ_COMMANDS | WRITE_COMMANDS | ADMIN_COMMANDS


# ═══════════════════════════════════════════════════════════
# CONFIG LOADING
# ═══════════════════════════════════════════════════════════

def load_agent_capabilities() -> dict:
    """Load agent_capabilities.yaml from config/."""
    if not AGENT_CAPS_PATH.exists():
        _die(f"agent_capabilities.yaml not found at {AGENT_CAPS_PATH}")
    with open(AGENT_CAPS_PATH) as f:
        return yaml.safe_load(f)


def load_governance() -> dict:
    """Load governance.yaml from config/."""
    if not GOVERNANCE_PATH.exists():
        _die(f"governance.yaml not found at {GOVERNANCE_PATH}")
    with open(GOVERNANCE_PATH) as f:
        return yaml.safe_load(f)


# ═══════════════════════════════════════════════════════════
# PERMISSION ENFORCEMENT (6 layers)
# ═══════════════════════════════════════════════════════════

def check_agent_allowlist(agent_id: str, command: str, caps_config: dict) -> tuple[bool, str]:
    """Layer 1: Check agent is known and command is in allowed list."""
    agents = caps_config.get("agents", {})
    if agent_id not in agents:
        return False, f"Unknown agent: {agent_id}"

    agent = agents[agent_id]
    allowed = agent.get("allowed_cli_commands", [])
    blocked = agent.get("blocked_cli_commands", [])

    # dev with wildcard allowed
    if allowed == "*":
        return True, "ok"

    # Blocked wildcard means everything not in allowed is blocked
    if blocked == "*":
        if command not in allowed:
            return False, f"Agent '{agent_id}' does not have access to '{command}'"

    # Explicit block list
    if isinstance(blocked, list) and command in blocked:
        return False, f"Command '{command}' is explicitly blocked for agent '{agent_id}'"

    # Must be in allowed list
    if isinstance(allowed, list) and command not in allowed:
        return False, f"Command '{command}' is not in allowed list for agent '{agent_id}'"

    return True, "ok"


def check_governance_gate(agent_id: str, command: str, gov_config: dict) -> tuple[str, str]:
    """Layer 2: Check governance gate for write commands.

    Returns (gate_status, message) where gate_status is one of:
      'true'    — auto-approved, proceed
      'confirm' — queued for user confirmation
      'off'     — blocked entirely
      'skip'    — not a gated command (reads, admin)
    """
    gate_key = COMMAND_TO_GATE.get(command)
    if not gate_key:
        return "skip", "ok"

    action_gates = gov_config.get("action_gates", {})
    base_gate = action_gates.get(gate_key, True)

    # Check agent-specific overrides
    agent_overrides = gov_config.get("agent_overrides", {}).get(agent_id, {})
    gate_value = agent_overrides.get(gate_key, base_gate)

    if gate_value is True or gate_value == "true":
        return "true", "ok"
    elif gate_value == "confirm":
        return "confirm", f"Action '{gate_key}' requires user confirmation"
    elif gate_value is False or gate_value == "off":
        return "off", f"Action '{gate_key}' is disabled for agent '{agent_id}'"
    else:
        return "true", "ok"


def check_sql_guard(command: str) -> tuple[bool, str]:
    """Layer 3: CLI never exposes raw SQL execution to agents."""
    # All commands go through structured handlers, never raw SQL.
    # This guard exists as a defense-in-depth assertion.
    if command not in ALL_COMMANDS:
        return False, f"Unknown command: {command}. No raw SQL execution allowed."
    return True, "ok"


async def check_write_rate(db, agent_id: str, gov_config: dict) -> tuple[bool, str]:
    """Layer 4: Count writes in mem_cos_activity over last 60s, block if >= limit."""
    rate_limits = gov_config.get("rate_limits", {})
    max_writes = rate_limits.get("writes_per_minute", 3)

    try:
        row = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM mem_cos_activity "
            "WHERE actor = ? AND action_type = 'cli_write' "
            "AND created_at >= datetime('now', '-60 seconds')",
            [agent_id],
        )
        count = row["c"] if row else 0
        if count >= max_writes:
            return False, (
                f"Write rate limit exceeded: {count} writes in last 60s "
                f"(limit: {max_writes}). Auto-paused for safety."
            )
    except Exception:
        # Table may not exist yet — allow through
        pass

    return True, "ok"


def sanitize_output(output: str, agent_id: str, gov_config: dict) -> str:
    """Layer 5: Regex-strip API keys, redact privileged titles for non-dev agents."""
    sanitization = gov_config.get("output_sanitization", {})
    strip_patterns = sanitization.get("strip_patterns", [])

    result = output
    for pattern in strip_patterns:
        try:
            result = re.sub(pattern, "[REDACTED]", result)
        except re.error:
            pass

    # Redact privileged content for non-dev agents
    if agent_id != "dev":
        redact_keys = sanitization.get("redact_for_non_dev", [])
        if "laura_work_calendar_titles" in redact_keys:
            result = re.sub(
                r'"laura_work_title"\s*:\s*"[^"]*"',
                '"laura_work_title": "[private]"',
                result,
            )
        if "api_key_values" in redact_keys:
            result = re.sub(
                r'"api_key"\s*:\s*"[^"]*"',
                '"api_key": "[REDACTED]"',
                result,
            )

    return result


async def audit_invocation(
    db, agent_id: str, command: str, args: dict | None,
    result_summary: str, success: bool,
):
    """Layer 6: Log every CLI invocation to mem_cos_activity."""
    action_type = "cli_write" if command in WRITE_COMMANDS else "cli_read"
    if command in ADMIN_COMMANDS:
        action_type = "cli_admin"

    description = json.dumps({
        "command": command,
        "agent": agent_id,
        "args": args or {},
        "success": success,
        "summary": result_summary[:500],
    })

    try:
        await db.execute(
            "INSERT INTO mem_cos_activity (actor, action_type, description, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            [agent_id, action_type, description],
        )
        await db.commit()
    except Exception as e:
        # Audit failure should not block the command
        _err(f"Audit log failed: {e}")


# ═══════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════

async def cmd_bootstrap(db, args: dict, agent_id: str) -> dict:
    """Apply schema + migrations. Dev only."""
    from pib.db import apply_schema, apply_migrations
    await apply_schema(db)
    await apply_migrations(db)
    return {"status": "ok", "message": "Schema and migrations applied"}


async def cmd_what_now(db, args: dict, agent_id: str) -> dict:
    """Load snapshot + compute whatNow for a member."""
    from pib.engine import load_snapshot, what_now
    member_id = args.get("member_id", "m-james")
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


async def cmd_calendar_query(db, args: dict, agent_id: str) -> dict:
    """Query calendar events from cal_classified_events."""
    query_date = args.get("date", date.today().isoformat())
    member_id = args.get("member_id")
    privacy_filter = args.get("privacy", "full")

    conditions = ["event_date = ?"]
    params: list[Any] = [query_date]

    if member_id:
        conditions.append("member_id = ?")
        params.append(member_id)

    # Privacy fence: non-dev agents only see busy status for Laura's work calendar
    if agent_id != "dev":
        conditions.append("privacy IN ('full', 'busy_only')")

    where = " AND ".join(conditions)
    rows = await db.execute_fetchall(
        f"SELECT * FROM cal_classified_events WHERE {where} ORDER BY start_time",
        params,
    )
    events = [dict(r) for r in rows] if rows else []

    # Redact Laura's work calendar titles for non-dev agents
    if agent_id != "dev":
        for evt in events:
            if evt.get("privacy") == "busy_only":
                evt["title"] = "[busy]"
                evt["description"] = None
                evt["attendees"] = None

    return {"date": query_date, "events": events, "count": len(events)}


async def cmd_custody(db, args: dict, agent_id: str) -> dict:
    """Deterministic custody query."""
    from pib.custody import who_has_child, get_custody_text

    query_date = date.fromisoformat(args.get("date", date.today().isoformat()))

    config_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    if not config_row:
        return {"error": "No active custody config found"}

    config = dict(config_row)
    parent_id = who_has_child(query_date, config)

    member_rows = await db.execute_fetchall("SELECT * FROM common_members WHERE active = 1")
    members = {r["id"]: dict(r) for r in member_rows} if member_rows else {}
    text = get_custody_text(query_date, config, members)

    return {
        "date": query_date.isoformat(),
        "parent_id": parent_id,
        "text": text,
    }


async def cmd_budget(db, args: dict, agent_id: str) -> dict:
    """Financial snapshot from fin_budget_snapshot."""
    rows = await db.execute_fetchall(
        "SELECT * FROM fin_budget_snapshot ORDER BY category"
    )
    categories = [dict(r) for r in rows] if rows else []
    over_budget = [c for c in categories if c.get("over_threshold")]
    return {
        "categories": categories,
        "over_budget_count": len(over_budget),
        "over_budget": over_budget,
    }


async def cmd_search(db, args: dict, agent_id: str) -> dict:
    """FTS5 memory search, scoped to requesting member."""
    from pib.memory import search_memory

    query = args.get("query", "")
    limit = args.get("limit", 10)
    member_id = args.get("member_id")
    if not query:
        return {"error": "query is required", "results": []}

    results = await search_memory(db, query, limit=limit, member_id=member_id)
    return {"query": query, "results": results, "count": len(results)}


async def cmd_morning_digest(db, args: dict, agent_id: str) -> dict:
    """Assemble morning digest data."""
    from pib.proactive import build_morning_digest_data

    member_id = args.get("member_id", "m-james")
    return await build_morning_digest_data(db, member_id)


async def cmd_health(db, args: dict, agent_id: str) -> dict:
    """Evaluate system readiness."""
    from pib.readiness import evaluate_readiness
    return await evaluate_readiness(db)


async def cmd_streak(db, args: dict, agent_id: str) -> dict:
    """Query streak data for a member."""
    member_id = args.get("member_id", "m-james")
    rows = await db.execute_fetchall(
        "SELECT * FROM ops_streaks WHERE member_id = ?",
        [member_id],
    )
    streaks = [dict(r) for r in rows] if rows else []
    return {"member_id": member_id, "streaks": streaks}


async def cmd_upcoming(db, args: dict, agent_id: str) -> dict:
    """Query upcoming recurring tasks."""
    member_id = args.get("member_id", "m-james")
    days = args.get("days", 7)

    rows = await db.execute_fetchall(
        "SELECT * FROM ops_recurring "
        "WHERE assignee = ? AND active = 1 "
        "AND next_due <= date('now', ? || ' days') "
        "ORDER BY next_due",
        [member_id, str(days)],
    )
    tasks = [dict(r) for r in rows] if rows else []
    return {"member_id": member_id, "days": days, "tasks": tasks, "count": len(tasks)}


async def cmd_scoreboard_data(db, args: dict, agent_id: str) -> dict:
    """Composite scoreboard query: streaks, completions, custody."""
    from pib.custody import who_has_child

    today = date.today()

    # All member streaks
    streak_rows = await db.execute_fetchall(
        "SELECT * FROM ops_streaks WHERE streak_type = 'daily_completion'"
    )
    streaks = {r["member_id"]: dict(r) for r in streak_rows} if streak_rows else {}

    # Today's completions per member
    comp_rows = await db.execute_fetchall(
        "SELECT member_id, completions_today FROM pib_energy_states "
        "WHERE state_date = ?",
        [today.isoformat()],
    )
    completions = {r["member_id"]: r["completions_today"] for r in comp_rows} if comp_rows else {}

    # Custody
    custody_row = await db.execute_fetchone(
        "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
    )
    custody = None
    if custody_row:
        custody = who_has_child(today, dict(custody_row))

    return {
        "date": today.isoformat(),
        "streaks": streaks,
        "completions_today": completions,
        "custody_parent": custody,
    }


async def cmd_task_create(db, args: dict, agent_id: str) -> dict:
    """Create a new task."""
    from pib.db import next_id, audit_log

    title = args.get("title")
    if not title:
        return {"error": "title is required"}

    task_id = await next_id(db, "tsk")
    assignee = args.get("assignee", "m-james")
    effort = args.get("effort", "medium")
    due_date = args.get("due_date")
    notes = args.get("notes")
    item_type = args.get("item_type", "task")

    await db.execute(
        "INSERT INTO ops_tasks (id, title, assignee, effort, due_date, notes, item_type, "
        "created_by, source_system) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [task_id, title, assignee, effort, due_date, notes, item_type, agent_id, "cli"],
    )
    await audit_log(db, "ops_tasks", "INSERT", task_id, actor=agent_id, source="cli")
    await db.commit()
    return {"task_id": task_id, "title": title, "assignee": assignee, "status": "inbox"}


async def cmd_task_complete(db, args: dict, agent_id: str) -> dict:
    """Complete a task with reward selection."""
    from pib.rewards import complete_task_with_reward

    task_id = args.get("task_id")
    member_id = args.get("member_id", "m-james")
    if not task_id:
        return {"error": "task_id is required"}

    result = await complete_task_with_reward(db, task_id, member_id, actor=agent_id)
    return result


async def cmd_task_update(db, args: dict, agent_id: str) -> dict:
    """Transition a task to a new status with guard checks."""
    from pib.engine import transition_task

    task_id = args.get("task_id")
    new_status = args.get("status")
    if not task_id or not new_status:
        return {"error": "task_id and status are required"}

    update_data = {
        k: v for k, v in args.items()
        if k in ("notes", "scheduled_date", "waiting_on")
    }

    try:
        result = await transition_task(db, task_id, new_status, update_data, actor=agent_id)
        return result
    except ValueError as e:
        return {"error": str(e)}


async def cmd_task_snooze(db, args: dict, agent_id: str) -> dict:
    """Snooze a task by updating its scheduled_date."""
    from pib.db import audit_log

    task_id = args.get("task_id")
    scheduled_date = args.get("scheduled_date")
    if not task_id or not scheduled_date:
        return {"error": "task_id and scheduled_date are required"}

    row = await db.execute_fetchone("SELECT * FROM ops_tasks WHERE id = ?", [task_id])
    if not row:
        return {"error": f"Task {task_id} not found"}

    old_date = row["scheduled_date"]
    await db.execute(
        "UPDATE ops_tasks SET scheduled_date = ?, updated_at = datetime('now') WHERE id = ?",
        [scheduled_date, task_id],
    )
    await audit_log(
        db, "ops_tasks", "UPDATE", task_id, actor=agent_id,
        old_values=json.dumps({"scheduled_date": old_date}),
        new_values=json.dumps({"scheduled_date": scheduled_date}),
        source="cli",
    )
    await db.commit()
    return {"task_id": task_id, "scheduled_date": scheduled_date, "previous": old_date}


async def cmd_hold_create(db, args: dict, agent_id: str) -> dict:
    """Create a calendar hold (pending approval)."""
    from pib.db import next_id, audit_log

    title = args.get("title")
    event_date = args.get("date")
    start_time = args.get("start_time")
    end_time = args.get("end_time")
    member_id = args.get("member_id", "m-james")

    if not all([title, event_date, start_time, end_time]):
        return {"error": "title, date, start_time, and end_time are required"}

    hold_id = await next_id(db, "hold")
    await db.execute(
        "INSERT INTO cal_classified_events "
        "(id, title, event_date, start_time, end_time, member_id, "
        "scheduling_impact, approval_status, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, 'SOFT_BLOCK', 'pending', ?)",
        [hold_id, title, event_date, start_time, end_time, member_id, agent_id],
    )
    await audit_log(db, "cal_classified_events", "INSERT", hold_id, actor=agent_id, source="cli")
    await db.commit()
    return {"hold_id": hold_id, "status": "pending_approval", "title": title}


async def cmd_hold_confirm(db, args: dict, agent_id: str) -> dict:
    """Confirm a pending calendar hold."""
    from pib.db import audit_log

    hold_id = args.get("hold_id")
    if not hold_id:
        return {"error": "hold_id is required"}

    row = await db.execute_fetchone(
        "SELECT * FROM cal_classified_events WHERE id = ? AND approval_status = 'pending'",
        [hold_id],
    )
    if not row:
        return {"error": f"Hold {hold_id} not found or not pending"}

    await db.execute(
        "UPDATE cal_classified_events SET approval_status = 'confirmed', "
        "updated_at = datetime('now') WHERE id = ?",
        [hold_id],
    )
    await audit_log(
        db, "cal_classified_events", "UPDATE", hold_id, actor=agent_id,
        old_values='{"approval_status": "pending"}',
        new_values='{"approval_status": "confirmed"}',
        source="cli",
    )
    await db.commit()
    return {"hold_id": hold_id, "status": "confirmed"}


async def cmd_hold_reject(db, args: dict, agent_id: str) -> dict:
    """Reject a pending calendar hold."""
    from pib.db import audit_log

    hold_id = args.get("hold_id")
    if not hold_id:
        return {"error": "hold_id is required"}

    row = await db.execute_fetchone(
        "SELECT * FROM cal_classified_events WHERE id = ? AND approval_status = 'pending'",
        [hold_id],
    )
    if not row:
        return {"error": f"Hold {hold_id} not found or not pending"}

    reason = args.get("reason", "")
    await db.execute(
        "UPDATE cal_classified_events SET approval_status = 'rejected', "
        "updated_at = datetime('now') WHERE id = ?",
        [hold_id],
    )
    await audit_log(
        db, "cal_classified_events", "UPDATE", hold_id, actor=agent_id,
        old_values='{"approval_status": "pending"}',
        new_values=json.dumps({"approval_status": "rejected", "reason": reason}),
        source="cli",
    )
    await db.commit()
    return {"hold_id": hold_id, "status": "rejected", "reason": reason}


async def cmd_recurring_done(db, args: dict, agent_id: str) -> dict:
    """Mark a recurring task instance as done."""
    from pib.db import audit_log

    recurring_id = args.get("recurring_id")
    member_id = args.get("member_id", "m-james")
    if not recurring_id:
        return {"error": "recurring_id is required"}

    row = await db.execute_fetchone(
        "SELECT * FROM ops_recurring WHERE id = ?", [recurring_id]
    )
    if not row:
        return {"error": f"Recurring task {recurring_id} not found"}

    # Mark spawned now and advance next_due based on frequency string.
    await db.execute(
        "UPDATE ops_recurring SET "
        "last_spawned = datetime('now'), "
        "next_due = date('now', '+' || CASE lower(frequency) "
        "    WHEN 'daily' THEN '1' "
        "    WHEN 'weekdays' THEN '1' "
        "    WHEN 'weekly' THEN '7' "
        "    WHEN 'biweekly' THEN '14' "
        "    WHEN 'monthly' THEN '30' "
        "    WHEN 'quarterly' THEN '90' "
        "    WHEN 'yearly' THEN '365' "
        "    ELSE '7' "
        "END || ' days') "
        "WHERE id = ?",
        [recurring_id],
    )
    await audit_log(
        db, "ops_recurring", "UPDATE", recurring_id, actor=agent_id, source="cli"
    )
    await db.commit()
    return {"recurring_id": recurring_id, "status": "done", "member_id": member_id}


async def cmd_recurring_skip(db, args: dict, agent_id: str) -> dict:
    """Mark a recurring task instance as skipped."""
    from pib.db import audit_log

    recurring_id = args.get("recurring_id")
    reason = args.get("reason", "")
    if not recurring_id:
        return {"error": "recurring_id is required"}

    row = await db.execute_fetchone(
        "SELECT * FROM ops_recurring WHERE id = ?", [recurring_id]
    )
    if not row:
        return {"error": f"Recurring task {recurring_id} not found"}

    # Advance next_due without marking as spawned (skip).
    await db.execute(
        "UPDATE ops_recurring SET "
        "next_due = date('now', '+' || CASE lower(frequency) "
        "    WHEN 'daily' THEN '1' "
        "    WHEN 'weekdays' THEN '1' "
        "    WHEN 'weekly' THEN '7' "
        "    WHEN 'biweekly' THEN '14' "
        "    WHEN 'monthly' THEN '30' "
        "    WHEN 'quarterly' THEN '90' "
        "    WHEN 'yearly' THEN '365' "
        "    ELSE '7' "
        "END || ' days') "
        "WHERE id = ?",
        [recurring_id],
    )
    await audit_log(
        db, "ops_recurring", "UPDATE", recurring_id, actor=agent_id,
        new_values=json.dumps({"skipped": True, "reason": reason}),
        source="cli",
    )
    await db.commit()
    return {"recurring_id": recurring_id, "status": "skipped", "reason": reason}


async def cmd_state_update(db, args: dict, agent_id: str) -> dict:
    """UPSERT pib_energy_states — record meds taken, sleep quality, energy, focus mode."""
    member_id = args.get("member_id", "m-james")
    today = date.today().isoformat()

    # Build SET clause from known fields
    known_fields = {
        "meds_taken", "meds_taken_at", "sleep_quality", "focus_mode",
        "energy_override", "notes",
    }
    updates = {k: v for k, v in args.items() if k in known_fields}

    if not updates:
        return {"error": "No recognized state fields provided"}

    # Build UPSERT
    columns = ["member_id", "state_date"]
    values: list[Any] = [member_id, today]
    set_parts = []

    for field, value in updates.items():
        columns.append(field)
        values.append(value)
        set_parts.append(f"{field} = excluded.{field}")

    placeholders = ", ".join(["?"] * len(values))
    col_names = ", ".join(columns)
    set_clause = ", ".join(set_parts)

    await db.execute(
        f"INSERT INTO pib_energy_states ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT(member_id, state_date) DO UPDATE SET {set_clause}",
        values,
    )
    await db.commit()
    return {"member_id": member_id, "date": today, "updates": updates}


async def cmd_capture(db, args: dict, agent_id: str) -> dict:
    """Quick capture to inbox via capture.create_capture."""
    from pib.capture import create_capture

    text = args.get("text")
    member_id = args.get("member_id", "m-james")
    if not text:
        return {"error": "text is required"}

    source = args.get("source", "cli")
    household_visible = args.get("household_visible", False)

    result = await create_capture(
        db, member_id, text, source=source, household_visible=household_visible,
    )
    return result


async def cmd_run_proactive_checks(db, args: dict, agent_id: str) -> dict:
    """Scan proactive triggers for a member."""
    from pib.proactive import scan_triggers

    member_id = args.get("member_id", "m-james")
    fired = await scan_triggers(db, member_id)
    return {"member_id": member_id, "triggers_fired": fired, "count": len(fired)}


async def cmd_backup(db, args: dict, agent_id: str) -> dict:
    """Verify backup integrity. Dev only."""
    from pib.backup import backup_verify

    backup_dir = args.get("backup_dir", "/opt/pib/data/backups")
    return await backup_verify(backup_dir)


async def cmd_webhook_receive(db, args: dict, agent_id: str) -> dict:
    """Receive and process a BlueBubbles webhook payload.

    Per-bridge credential isolation: validates API key from BLUEBUBBLES_{MEMBER}_SECRET.
    Forces member_id from bridge identity (james→m-james, laura→m-laura).
    """
    from pib.ingest import IngestEvent, ingest, make_idempotency_key, resolve_member

    # Per-bridge credential validation
    provided_secret = args.get("api_key", "")
    bridge_member_map = {
        "james": ("BLUEBUBBLES_JAMES_SECRET", "m-james"),
        "laura": ("BLUEBUBBLES_LAURA_SECRET", "m-laura"),
    }

    # Try explicit bridge_id first, then match by secret
    bridge_id = args.get("bridge_id", "").lower()
    forced_member_id = None

    if bridge_id and bridge_id in bridge_member_map:
        env_key, forced_member_id = bridge_member_map[bridge_id]
        expected_secret = os.environ.get(env_key, "")
        if not expected_secret:
            return {"error": f"{env_key} not configured"}
        if provided_secret != expected_secret:
            return {"error": f"Invalid API key for bridge {bridge_id}", "status": "unauthorized"}
    else:
        # No bridge_id — match secret against all configured bridges
        for member, (env_key, member_id) in bridge_member_map.items():
            secret = os.environ.get(env_key, "")
            if secret and provided_secret == secret:
                forced_member_id = member_id
                break
        if not forced_member_id:
            return {"error": "Invalid API key — no matching BLUEBUBBLES_*_SECRET", "status": "unauthorized"}

    payload = args.get("payload", {})
    if not payload:
        return {"error": "payload is required"}

    # Extract message data from BlueBubbles format
    message = payload.get("message", payload)
    text = message.get("text", "")
    sender = message.get("handle", {})
    sender_address = sender.get("address", "") if isinstance(sender, dict) else str(sender)
    message_guid = message.get("guid", f"bb-{int(time.time())}")

    # Build IngestEvent
    idem_key = make_idempotency_key("bluebubbles", message_guid)
    event = IngestEvent(
        source="bluebubbles",
        timestamp=now_et().isoformat(),
        idempotency_key=idem_key,
        raw=message,
        text=text,
        reply_channel="imessage",
        reply_address=sender_address,
    )

    # Member resolution: forced from bridge_id takes precedence
    if forced_member_id:
        resolved_member_id = await resolve_member(db, event)
        if resolved_member_id and resolved_member_id != forced_member_id:
            log.warning(
                f"Bridge {bridge_id} member mismatch: payload resolved to {resolved_member_id}, "
                f"forcing to {forced_member_id}"
            )
        event.member_id = forced_member_id
    else:
        event.member_id = await resolve_member(db, event)

    # Process through ingest pipeline
    actions = await ingest(event, db)

    return {
        "status": "processed",
        "message_guid": message_guid,
        "member_id": event.member_id,
        "bridge_id": bridge_id or None,
        "actions": actions,
    }


async def cmd_migrate(db, args: dict, agent_id: str) -> dict:
    """Apply pending migrations. Dev only."""
    from pib.db import apply_migrations

    migrations_dir = args.get("migrations_dir")
    await apply_migrations(db, migrations_dir)
    return {"status": "ok", "message": "Migrations applied"}


async def cmd_member_settings_get(db, args: dict, agent_id: str) -> dict:
    """Get all settings for a member (common_members columns + pib_member_settings overrides)."""
    member_id = args.get("member_id", "m-james")

    member = await db.execute_fetchone(
        "SELECT * FROM common_members WHERE id = ?", [member_id]
    )
    if not member:
        return {"error": f"Member {member_id} not found"}

    # Base settings from common_members columns
    base = {
        "view_mode": member["view_mode"],
        "digest_mode": member["digest_mode"],
        "velocity_cap": member["velocity_cap"],
        "preferred_channel": member["preferred_channel"],
        "energy_markers": member["energy_markers"],
        "medication_config": member["medication_config"],
    }

    # Override with pib_member_settings
    overrides_rows = await db.execute_fetchall(
        "SELECT key, value, description FROM pib_member_settings WHERE member_id = ?",
        [member_id],
    )
    overrides = {r["key"]: r["value"] for r in overrides_rows} if overrides_rows else {}

    return {"member_id": member_id, "base": base, "overrides": overrides}


async def cmd_member_settings_set(db, args: dict, agent_id: str) -> dict:
    """Upsert a per-member setting in pib_member_settings."""
    from pib.db import audit_log

    member_id = args.get("member_id", "m-james")
    key = args.get("key")
    value = args.get("value")
    description = args.get("description")

    if not key or value is None:
        return {"error": "key and value are required"}

    member = await db.execute_fetchone(
        "SELECT id FROM common_members WHERE id = ?", [member_id]
    )
    if not member:
        return {"error": f"Member {member_id} not found"}

    await db.execute(
        "INSERT INTO pib_member_settings (member_id, key, value, description, updated_by) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(member_id, key) DO UPDATE SET "
        "value = excluded.value, description = excluded.description, "
        "updated_by = excluded.updated_by, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')",
        [member_id, key, str(value), description, agent_id],
    )
    await audit_log(
        db, "pib_member_settings", "UPSERT", f"{member_id}:{key}",
        actor=agent_id, new_values=json.dumps({"key": key, "value": value}),
        source="cli",
    )
    await db.commit()
    return {"member_id": member_id, "key": key, "value": value}


async def cmd_bootstrap_verify(db, args: dict, agent_id: str) -> dict:
    """Comprehensive standalone verification that the brain works end-to-end without bridges.

    Runs multiple checks:
    - evaluate_readiness(db)
    - what_now for m-james and m-laura
    - Task create/verify/cleanup
    - Custody logic
    - Governance gate (coach can't create tasks)
    - Calendar context for both members
    - Voice profiles for both members
    - Memory isolation test
    - Optional bridge connectivity check

    Returns structured JSON report with pass/fail per check, overall PASS/FAIL.
    """
    import subprocess

    from pib.readiness import evaluate_readiness
    from pib.custody import who_has_child
    from pib.context import build_calendar_context
    from pib.memory import save_memory_deduped, search_memory
    from pib.voice import get_profiles

    checks: dict[str, dict] = {}
    today = date.today()

    # 1. Readiness check
    try:
        readiness = await evaluate_readiness(db)
        checks["readiness"] = {
            "pass": readiness.get("ready", False),
            "detail": readiness,
        }
    except Exception as e:
        checks["readiness"] = {"pass": False, "detail": str(e)}

    # 2. what-now for m-james
    try:
        result = await cmd_what_now(db, {"member_id": "m-james"}, agent_id)
        checks["what_now_james"] = {
            "pass": "error" not in result,
            "detail": {"the_one_task": result.get("the_one_task")},
        }
    except Exception as e:
        checks["what_now_james"] = {"pass": False, "detail": str(e)}

    # 3. what-now for m-laura
    try:
        result = await cmd_what_now(db, {"member_id": "m-laura"}, agent_id)
        checks["what_now_laura"] = {
            "pass": "error" not in result,
            "detail": {"the_one_task": result.get("the_one_task")},
        }
    except Exception as e:
        checks["what_now_laura"] = {"pass": False, "detail": str(e)}

    # 4. Task create/verify/cleanup
    test_task_id = None
    try:
        create_result = await cmd_task_create(db, {
            "title": "__bootstrap_verify_test_task__",
            "assignee": "m-james",
        }, agent_id)
        test_task_id = create_result.get("task_id")
        if test_task_id:
            row = await db.execute_fetchone(
                "SELECT * FROM ops_tasks WHERE id = ?", [test_task_id]
            )
            task_found = row is not None
            # Cleanup
            await db.execute("DELETE FROM ops_tasks WHERE id = ?", [test_task_id])
            await db.commit()
            checks["task_lifecycle"] = {"pass": task_found, "detail": {"task_id": test_task_id}}
        else:
            checks["task_lifecycle"] = {"pass": False, "detail": "task_id not returned"}
    except Exception as e:
        checks["task_lifecycle"] = {"pass": False, "detail": str(e)}
        if test_task_id:
            try:
                await db.execute("DELETE FROM ops_tasks WHERE id = ?", [test_task_id])
                await db.commit()
            except Exception:
                pass

    # 5. Custody logic
    try:
        config_row = await db.execute_fetchone(
            "SELECT * FROM common_custody_configs WHERE active = 1 LIMIT 1"
        )
        if config_row:
            parent_id = who_has_child(today, dict(config_row))
            checks["custody"] = {"pass": parent_id is not None, "detail": {"parent_id": parent_id}}
        else:
            checks["custody"] = {"pass": True, "detail": "no custody config (ok for some households)"}
    except Exception as e:
        checks["custody"] = {"pass": False, "detail": str(e)}

    # 6. Governance gate - coach agent should be blocked from task-create
    try:
        caps_config = load_agent_capabilities()
        gov_config = load_governance()
        # Check that coach is blocked from task-create
        ok, msg = check_agent_allowlist("coach", "task-create", caps_config)
        gate_status, gate_msg = check_governance_gate("coach", "task-create", gov_config)
        coach_blocked = not ok or gate_status == "off"
        checks["governance_coach_blocked"] = {
            "pass": coach_blocked,
            "detail": {"allowlist_ok": ok, "gate_status": gate_status},
        }
    except Exception as e:
        checks["governance_coach_blocked"] = {"pass": False, "detail": str(e)}

    # 7. Calendar context for both members
    for member in ["m-james", "m-laura"]:
        try:
            cal_ctx = await build_calendar_context(db, today.isoformat(), today.isoformat(), member)
            checks[f"calendar_context_{member.replace('-', '_')}"] = {
                "pass": True,
                "detail": {"length": len(cal_ctx) if cal_ctx else 0},
            }
        except Exception as e:
            checks[f"calendar_context_{member.replace('-', '_')}"] = {"pass": False, "detail": str(e)}

    # 8. Voice profiles for both members
    for member in ["m-james", "m-laura"]:
        try:
            profiles = await get_profiles(db, member)
            checks[f"voice_profiles_{member.replace('-', '_')}"] = {
                "pass": True,
                "detail": {"profile_count": len(profiles)},
            }
        except Exception as e:
            checks[f"voice_profiles_{member.replace('-', '_')}"] = {"pass": False, "detail": str(e)}

    # 9. Memory isolation test: save fact for m-james, search as m-laura, verify 0
    test_memory_content = "__bootstrap_verify_memory_test_xyz123__"
    try:
        save_result = await save_memory_deduped(
            db, test_memory_content, "preferences", "test", "m-james", "observed"
        )
        await db.commit()
        # Search as m-laura - should NOT find it
        laura_results = await search_memory(db, "xyz123", limit=10, member_id="m-laura")
        laura_found = any(test_memory_content in r.get("content", "") for r in laura_results)
        # Search as m-james - SHOULD find it
        james_results = await search_memory(db, "xyz123", limit=10, member_id="m-james")
        james_found = any(test_memory_content in r.get("content", "") for r in james_results)
        # Cleanup
        await db.execute(
            "DELETE FROM mem_long_term WHERE content = ?", [test_memory_content]
        )
        await db.commit()
        checks["memory_isolation"] = {
            "pass": not laura_found,  # Laura should NOT see James's memory
            "detail": {
                "james_found": james_found,
                "laura_found": laura_found,
                "isolation_enforced": not laura_found,
            },
        }
    except Exception as e:
        checks["memory_isolation"] = {"pass": False, "detail": str(e)}
        try:
            await db.execute(
                "DELETE FROM mem_long_term WHERE content = ?", [test_memory_content]
            )
            await db.commit()
        except Exception:
            pass

    # 10. Optional bridge connectivity check
    bridge_checks = {}
    for bridge_name, env_key in [("james", "BLUEBUBBLES_JAMES_HOST"), ("laura", "BLUEBUBBLES_LAURA_HOST")]:
        host = os.environ.get(env_key)
        if host:
            try:
                result = subprocess.run(
                    ["curl", "-sf", "--connect-timeout", "3", f"http://{host}/api/v1/server/info"],
                    capture_output=True,
                    timeout=5,
                )
                bridge_checks[bridge_name] = {"reachable": result.returncode == 0}
            except Exception as e:
                bridge_checks[bridge_name] = {"reachable": False, "error": str(e)}
        else:
            bridge_checks[bridge_name] = {"skipped": True, "reason": f"{env_key} not set"}

    if bridge_checks:
        checks["bridge_connectivity"] = {"pass": True, "detail": bridge_checks}

    # Compute overall status
    required_checks = [
        "readiness", "what_now_james", "what_now_laura", "task_lifecycle",
        "governance_coach_blocked", "memory_isolation",
    ]
    overall_pass = all(checks.get(c, {}).get("pass", False) for c in required_checks)

    return {
        "overall": "PASS" if overall_pass else "FAIL",
        "checks": checks,
        "timestamp": now_et().isoformat(),
    }


async def cmd_context(db, args: dict, agent_id: str) -> dict:
    """Assemble LLM context for a member, filtered by calling agent's permissions."""
    from pib.context import assemble_context

    member_id = args.get("member_id", "m-james")
    message = args.get("message", "")

    prompt = await assemble_context(db, member_id, message, agent_id=agent_id)
    return {"prompt": prompt}


async def cmd_sensor_ingest(db, args: dict, agent_id: str) -> dict:
    """Ingest sensor reading from bridge.

    Receives {source, member_id, timestamp, classification, data}, stores reading,
    auto-classifies m-laura as privileged.
    """
    source = args.get("source")
    member_id = args.get("member_id")
    timestamp = args.get("timestamp") or now_et().isoformat()
    data = args.get("data", {})
    classification = args.get("classification", "normal")
    idempotency_key = args.get("idempotency_key")
    confidence = args.get("confidence", "high")
    ttl_minutes = args.get("ttl_minutes", 60)

    if not source or not member_id:
        return {"error": "source and member_id are required"}

    if not idempotency_key:
        # Generate a deterministic key from source + member + timestamp
        import hashlib
        idempotency_key = hashlib.sha256(
            f"{source}:{member_id}:{timestamp}".encode()
        ).hexdigest()[:32]

    # Validate confidence
    valid_confidence = {"high", "medium", "low", "stale"}
    if confidence not in valid_confidence:
        confidence = "high"

    # Auto-classify m-laura as privileged
    if member_id == "m-laura":
        classification = "privileged"

    # Check for duplicate via idempotency key
    existing = await db.execute_fetchone(
        "SELECT id FROM pib_sensor_readings WHERE idempotency_key = ?",
        [idempotency_key],
    )
    if existing:
        return {"status": "duplicate", "existing_id": existing["id"]}

    # Extract reading_type from source or data
    reading_type = data.get("type") or source

    # Resolve sensor_id: try exact match, then normalize (e.g. apple_battery -> sensor-apple-battery)
    sensor_id = source
    existing_sensor = await db.execute_fetchone(
        "SELECT sensor_id FROM pib_sensor_config WHERE sensor_id = ?", [source]
    )
    if not existing_sensor:
        # Try with sensor- prefix and underscores replaced by hyphens
        normalized = f"sensor-{source.replace('_', '-')}"
        existing_sensor = await db.execute_fetchone(
            "SELECT sensor_id FROM pib_sensor_config WHERE sensor_id = ?", [normalized]
        )
        if existing_sensor:
            sensor_id = normalized
        else:
            # Auto-register unknown sensor source
            await db.execute(
                "INSERT OR IGNORE INTO pib_sensor_config (sensor_id, name, category, enabled) "
                "VALUES (?, ?, 'bridge', 1)",
                [source, source],
            )

    # Compute expires_at from ttl_minutes
    from datetime import timedelta
    expires_at = (now_et() + timedelta(minutes=ttl_minutes)).isoformat()

    # Store the reading (id is INTEGER AUTOINCREMENT — omit to let SQLite assign)
    await db.execute(
        """INSERT INTO pib_sensor_readings
           (sensor_id, reading_type, member_id, timestamp, value,
            classification, confidence, ttl_minutes, expires_at, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            sensor_id, reading_type, member_id, timestamp,
            json.dumps(data), classification, confidence,
            ttl_minutes, expires_at, idempotency_key,
        ],
    )
    await db.commit()

    # Get the auto-assigned ID
    row = await db.execute_fetchone(
        "SELECT id FROM pib_sensor_readings WHERE idempotency_key = ?",
        [idempotency_key],
    )
    reading_id = row["id"] if row else None

    return {
        "status": "stored",
        "reading_id": reading_id,
        "member_id": member_id,
        "classification": classification,
        "source": source,
    }


async def cmd_chat_stream(db, args: dict, agent_id: str) -> dict:
    """Look up or create a chat session, log user message, assemble context.

    Since we can't call the Anthropic API in all environments, returns the
    context that WOULD be sent to Claude rather than streaming a response.
    """
    from pib.db import next_id, audit_log
    from pib.context import assemble_context

    message = args.get("message")
    session_id = args.get("session_id")
    child_mode = args.get("child_mode", False)
    member_id = args.get("member_id", "m-james")

    if not message:
        return {"error": "message is required"}

    # Look up or create session
    if session_id:
        row = await db.execute_fetchone(
            "SELECT * FROM mem_sessions WHERE id = ?", [session_id]
        )
        if not row:
            # Create session with the provided ID
            await db.execute(
                "INSERT INTO mem_sessions (id, member_id, channel, started_at, message_count, active) "
                "VALUES (?, ?, 'webchat', strftime('%Y-%m-%dT%H:%M:%SZ','now'), 0, 1)",
                [session_id, member_id],
            )
            await db.commit()
    else:
        session_id = await next_id(db, "ses")
        await db.execute(
            "INSERT INTO mem_sessions (id, member_id, channel, started_at, message_count, active) "
            "VALUES (?, ?, 'webchat', strftime('%Y-%m-%dT%H:%M:%SZ','now'), 0, 1)",
            [session_id, member_id],
        )
        await db.commit()

    # Log user message to mem_messages
    await db.execute(
        "INSERT INTO mem_messages (session_id, role, content, created_at) "
        "VALUES (?, 'user', ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
        [session_id, message],
    )

    # Update session message count and last_message_at
    await db.execute(
        "UPDATE mem_sessions SET message_count = message_count + 1, "
        "last_message_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
        [session_id],
    )

    # Assemble context that would be sent to Claude
    try:
        context_assembled = await assemble_context(
            db, member_id, message, agent_id=agent_id
        )
    except Exception as e:
        context_assembled = f"Context assembly failed: {e}"

    await audit_log(
        db, "mem_sessions", "UPDATE", session_id, actor=agent_id,
        new_values=json.dumps({"message": message[:200], "child_mode": child_mode}),
        source="cli",
    )
    await db.commit()

    return {
        "session_id": session_id,
        "context_assembled": context_assembled,
        "message_logged": True,
    }


async def cmd_comms_approve_draft(db, args: dict, agent_id: str) -> dict:
    """Approve a drafted comm in ops_comms."""
    from pib.db import audit_log

    comms_id = args.get("comms_id") or args.get("id")
    if not comms_id:
        return {"error": "comms_id is required"}

    row = await db.execute_fetchone(
        "SELECT * FROM ops_comms WHERE id = ?", [comms_id]
    )
    if not row:
        return {"error": f"Comm {comms_id} not found"}

    old_outcome = row["outcome"]
    await db.execute(
        "UPDATE ops_comms SET outcome = 'approved' WHERE id = ?",
        [comms_id],
    )
    await audit_log(
        db, "ops_comms", "UPDATE", comms_id, actor=agent_id,
        old_values=json.dumps({"outcome": old_outcome}),
        new_values=json.dumps({"outcome": "approved"}),
        source="cli",
    )
    await db.commit()
    return {"id": comms_id, "status": "approved"}


async def cmd_comms_respond(db, args: dict, agent_id: str) -> dict:
    """Mark a comm as responded in ops_comms."""
    from pib.db import audit_log

    comms_id = args.get("comms_id") or args.get("id")
    if not comms_id:
        return {"error": "comms_id is required"}

    row = await db.execute_fetchone(
        "SELECT * FROM ops_comms WHERE id = ?", [comms_id]
    )
    if not row:
        return {"error": f"Comm {comms_id} not found"}

    old_outcome = row["outcome"]
    old_responded_at = row["responded_at"]
    responded_at = now_et().isoformat()

    await db.execute(
        "UPDATE ops_comms SET responded_at = ?, outcome = 'responded' WHERE id = ?",
        [responded_at, comms_id],
    )
    await audit_log(
        db, "ops_comms", "UPDATE", comms_id, actor=agent_id,
        old_values=json.dumps({"outcome": old_outcome, "responded_at": old_responded_at}),
        new_values=json.dumps({"outcome": "responded", "responded_at": responded_at}),
        source="cli",
    )
    await db.commit()
    return {"id": comms_id, "status": "responded"}


async def cmd_comms_snooze(db, args: dict, agent_id: str) -> dict:
    """Snooze a comm by setting followup_date in ops_comms."""
    from pib.db import audit_log

    comms_id = args.get("comms_id") or args.get("id")
    until = args.get("until")
    if not comms_id:
        return {"error": "comms_id is required"}
    if not until:
        return {"error": "until is required"}

    row = await db.execute_fetchone(
        "SELECT * FROM ops_comms WHERE id = ?", [comms_id]
    )
    if not row:
        return {"error": f"Comm {comms_id} not found"}

    old_outcome = row["outcome"]
    old_followup = row["followup_date"]

    await db.execute(
        "UPDATE ops_comms SET followup_date = ?, outcome = 'snoozed' WHERE id = ?",
        [until, comms_id],
    )
    await audit_log(
        db, "ops_comms", "UPDATE", comms_id, actor=agent_id,
        old_values=json.dumps({"outcome": old_outcome, "followup_date": old_followup}),
        new_values=json.dumps({"outcome": "snoozed", "followup_date": until}),
        source="cli",
    )
    await db.commit()
    return {"id": comms_id, "status": "snoozed", "until": until}


async def cmd_calendar_ingest(db, args: dict, agent_id: str) -> dict:
    """Ingest calendar events from gog CLI output into cal_raw_events.

    Accepts either {events: [...]} or a raw list of event dicts.
    Each event has: google_event_id, calendar_id, summary, description,
    location, start, end, all_day, recurrence, attendees, status.
    """
    from pib.db import audit_log

    # Accept both {events: [...]} and a raw list
    if isinstance(args, list):
        events = args
    else:
        events = args.get("events", [])

    if not events:
        return {"error": "events list is required and must be non-empty"}

    # Cache source_id lookups by google_calendar_id
    source_cache: dict[str, str | None] = {}

    async def resolve_source_id(google_calendar_id: str) -> str | None:
        if google_calendar_id in source_cache:
            return source_cache[google_calendar_id]
        row = await db.execute_fetchone(
            "SELECT id FROM cal_sources WHERE google_calendar_id = ?",
            [google_calendar_id],
        )
        source_id = row["id"] if row else None
        source_cache[google_calendar_id] = source_id
        return source_id

    processed = 0
    skipped = 0

    for event in events:
        google_event_id = event.get("google_event_id")
        calendar_id = event.get("calendar_id")

        if not google_event_id or not calendar_id:
            skipped += 1
            continue

        source_id = await resolve_source_id(calendar_id)
        if not source_id:
            skipped += 1
            continue

        summary = event.get("summary")
        description = event.get("description")
        location = event.get("location")
        start_time = event.get("start")
        end_time = event.get("end")
        all_day = 1 if event.get("all_day") else 0
        recurrence_rule = event.get("recurrence")
        attendees = json.dumps(event.get("attendees")) if event.get("attendees") else None
        status = event.get("status")
        raw_json = json.dumps(event, default=str)

        # Upsert: insert or update on conflict (source_id, google_event_id)
        await db.execute(
            "INSERT INTO cal_raw_events "
            "(id, source_id, google_event_id, summary, description, location, "
            "start_time, end_time, all_day, recurrence_rule, attendees, status, "
            "raw_json, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now')) "
            "ON CONFLICT(source_id, google_event_id) DO UPDATE SET "
            "summary = excluded.summary, description = excluded.description, "
            "location = excluded.location, start_time = excluded.start_time, "
            "end_time = excluded.end_time, all_day = excluded.all_day, "
            "recurrence_rule = excluded.recurrence_rule, attendees = excluded.attendees, "
            "status = excluded.status, raw_json = excluded.raw_json, "
            "fetched_at = excluded.fetched_at",
            [
                f"cre-{source_id}-{google_event_id}", source_id, google_event_id,
                summary, description, location, start_time, end_time, all_day,
                recurrence_rule, attendees, status, raw_json,
            ],
        )
        processed += 1

    await audit_log(
        db, "cal_raw_events", "INSERT", f"ingest-{processed}",
        actor=agent_id,
        new_values=json.dumps({"events_processed": processed, "skipped": skipped}),
        source="cli",
    )
    await db.commit()

    return {"status": "ok", "events_processed": processed, "skipped": skipped}


# ═══════════════════════════════════════════════════════════
# COMMAND REGISTRY
# ═══════════════════════════════════════════════════════════

# Import channel commands
from pib.channel_cli import CHANNEL_COMMANDS

COMMAND_REGISTRY: dict[str, tuple[Any, str]] = {
    # (handler, category)
    "bootstrap":            (cmd_bootstrap,             "admin"),
    "what-now":             (cmd_what_now,              "read"),
    "calendar-query":       (cmd_calendar_query,        "read"),
    "custody":              (cmd_custody,               "read"),
    "budget":               (cmd_budget,                "read"),
    "search":               (cmd_search,                "read"),
    "morning-digest":       (cmd_morning_digest,        "read"),
    "health":               (cmd_health,                "read"),
    "streak":               (cmd_streak,                "read"),
    "upcoming":             (cmd_upcoming,              "read"),
    "scoreboard-data":      (cmd_scoreboard_data,       "read"),
    "task-create":          (cmd_task_create,           "write"),
    "task-complete":        (cmd_task_complete,         "write"),
    "task-update":          (cmd_task_update,           "write"),
    "task-snooze":          (cmd_task_snooze,           "write"),
    "hold-create":          (cmd_hold_create,           "write"),
    "hold-confirm":         (cmd_hold_confirm,          "write"),
    "hold-reject":          (cmd_hold_reject,           "write"),
    "recurring-done":       (cmd_recurring_done,        "write"),
    "recurring-skip":       (cmd_recurring_skip,        "write"),
    "state-update":         (cmd_state_update,          "write"),
    "capture":              (cmd_capture,               "write"),
    "run-proactive-checks": (cmd_run_proactive_checks,  "write"),
    "backup":               (cmd_backup,                "admin"),
    "webhook-receive":      (cmd_webhook_receive,       "write"),
    "migrate":              (cmd_migrate,               "admin"),
    "member-settings-get":  (cmd_member_settings_get,   "read"),
    "member-settings-set":  (cmd_member_settings_set,   "write"),
    "bootstrap-verify":     (cmd_bootstrap_verify,      "read"),
    "sensor-ingest":        (cmd_sensor_ingest,         "write"),
    "context":              (cmd_context,               "read"),
    # Chat and comms commands
    "chat-stream":          (cmd_chat_stream,           "write"),
    "comms-approve-draft":  (cmd_comms_approve_draft,   "write"),
    "comms-respond":        (cmd_comms_respond,         "write"),
    "comms-snooze":         (cmd_comms_snooze,          "write"),
    # Calendar ingest
    "calendar-ingest":      (cmd_calendar_ingest,       "write"),
}

# Merge channel commands into registry
for cmd_name, handler in CHANNEL_COMMANDS.items():
    if cmd_name in READ_COMMANDS:
        COMMAND_REGISTRY[cmd_name] = (handler, "read")
    elif cmd_name in WRITE_COMMANDS:
        COMMAND_REGISTRY[cmd_name] = (handler, "write")
    else:
        COMMAND_REGISTRY[cmd_name] = (handler, "read")


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def _out(data: dict):
    """Write JSON to stdout."""
    print(json.dumps(data, default=str, ensure_ascii=False))


def _err(message: str):
    """Write error to stderr."""
    print(message, file=sys.stderr)


def _die(message: str, code: int = 1):
    """Write error JSON to stdout and exit."""
    _out({"error": message})
    sys.exit(code)


def _parse_args(argv: list[str]) -> tuple[str, str, dict, str]:
    """Parse CLI arguments.

    Returns (command, db_path, args_dict, member_id).
    """
    if len(argv) < 2:
        _die(
            "Usage: python -m pib.cli <command> <db_path> "
            "[--json '{}'] [--member m-james]"
        )

    command = argv[0]
    db_path = argv[1]

    args_dict: dict[str, Any] = {}
    member_id = ""
    i = 2

    while i < len(argv):
        if argv[i] == "--json" and i + 1 < len(argv):
            try:
                args_dict = json.loads(argv[i + 1])
            except json.JSONDecodeError as e:
                _die(f"Invalid --json argument: {e}")
            i += 2
        elif argv[i] == "--member" and i + 1 < len(argv):
            member_id = argv[i + 1]
            i += 2
        else:
            _err(f"Unknown argument: {argv[i]}")
            i += 1

    # Inject member_id into args if provided
    if member_id:
        args_dict["member_id"] = member_id

    return command, db_path, args_dict, member_id


# ═══════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════

async def run(argv: list[str]) -> None:
    """Async main: parse args, enforce permissions, execute command, audit."""
    from pib.db import get_connection

    # ── Parse ──
    command, db_path, args_dict, member_id = _parse_args(argv)
    agent_id = os.environ.get("PIB_CALLER_AGENT", "dev")

    # ── Load config ──
    caps_config = load_agent_capabilities()
    gov_config = load_governance()

    # ── Layer 1: Agent allowlist ──
    ok, msg = check_agent_allowlist(agent_id, command, caps_config)
    if not ok:
        _out({"error": "forbidden", "agent": agent_id, "command": command, "detail": msg})
        return

    # ── Layer 2: Governance gate ──
    gate_status, gate_msg = check_governance_gate(agent_id, command, gov_config)
    if gate_status == "off":
        _out({"error": "governance_blocked", "agent": agent_id, "command": command, "detail": gate_msg})
        return
    if gate_status == "confirm":
        _out({"status": "pending_approval", "agent": agent_id, "command": command, "detail": gate_msg})
        return

    # ── Layer 3: SQL guard ──
    ok, msg = check_sql_guard(command)
    if not ok:
        _out({"error": "unknown_command", "command": command, "detail": msg})
        return

    # ── Resolve handler ──
    if command not in COMMAND_REGISTRY:
        _out({"error": "unknown_command", "command": command})
        return

    handler, category = COMMAND_REGISTRY[command]

    # ── Open database ──
    db = await get_connection(db_path)
    try:
        # ── Layer 4: Write-rate tracking (writes only) ──
        if command in WRITE_COMMANDS:
            ok, msg = await check_write_rate(db, agent_id, gov_config)
            if not ok:
                await audit_invocation(
                    db, agent_id, command, args_dict, f"RATE_LIMITED: {msg}", False
                )
                _out({"error": "rate_limited", "agent": agent_id, "command": command, "detail": msg})
                return

        # ── Execute command ──
        try:
            result = await handler(db, args_dict, agent_id)
        except Exception as e:
            log.exception(f"Command {command} failed")
            await audit_invocation(
                db, agent_id, command, args_dict, f"ERROR: {e}", False
            )
            _out({"error": "command_failed", "command": command, "detail": str(e)})
            return

        # ── Layer 5: Sanitize output ──
        raw_output = json.dumps(result, default=str, ensure_ascii=False)
        sanitized = sanitize_output(raw_output, agent_id, gov_config)

        # ── Layer 6: Audit ──
        summary = f"ok: {command}"
        if isinstance(result, dict):
            if result.get("error"):
                summary = f"error: {result['error']}"
        await audit_invocation(db, agent_id, command, args_dict, summary, True)

        # ── Output ──
        # Parse sanitized back to ensure valid JSON out
        try:
            _out(json.loads(sanitized))
        except json.JSONDecodeError:
            _out(result)

    finally:
        await db.close()


def main():
    """Sync entry point for console_scripts and python -m pib.cli."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    argv = sys.argv[1:]
    if not argv:
        _die(
            "Usage: pib <command> <db_path> [--json '{}'] [--member m-james]\n"
            "Commands: " + ", ".join(sorted(COMMAND_REGISTRY.keys()))
        )
    asyncio.run(run(argv))


if __name__ == "__main__":
    main()
