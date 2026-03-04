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
    "run-proactive-checks", "webhook-receive",
    "member-settings-set",
}
ADMIN_COMMANDS = {"bootstrap", "backup", "migrate"}
READ_COMMANDS = {
    "what-now", "calendar-query", "custody", "budget", "search",
    "morning-digest", "health", "streak", "upcoming", "scoreboard-data",
    "member-settings-get",
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
        "SELECT * FROM ops_recurring_tasks "
        "WHERE assignee = ? AND active = 1 "
        "AND next_due_date <= date('now', ? || ' days') "
        "ORDER BY next_due_date",
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
        "SELECT * FROM ops_recurring_tasks WHERE id = ?", [recurring_id]
    )
    if not row:
        return {"error": f"Recurring task {recurring_id} not found"}

    # Update last_completed and advance next_due_date
    await db.execute(
        "UPDATE ops_recurring_tasks SET last_completed_date = date('now'), "
        "last_completed_by = ?, completions = completions + 1, "
        "next_due_date = date('now', '+' || frequency_days || ' days'), "
        "updated_at = datetime('now') WHERE id = ?",
        [member_id, recurring_id],
    )
    await audit_log(
        db, "ops_recurring_tasks", "UPDATE", recurring_id, actor=agent_id, source="cli"
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
        "SELECT * FROM ops_recurring_tasks WHERE id = ?", [recurring_id]
    )
    if not row:
        return {"error": f"Recurring task {recurring_id} not found"}

    # Advance next_due_date without counting as completion
    await db.execute(
        "UPDATE ops_recurring_tasks SET "
        "next_due_date = date('now', '+' || frequency_days || ' days'), "
        "skips = skips + 1, updated_at = datetime('now') WHERE id = ?",
        [recurring_id],
    )
    await audit_log(
        db, "ops_recurring_tasks", "UPDATE", recurring_id, actor=agent_id,
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

    Validates API key from BLUEBUBBLES_SECRET env var.
    Parses payload, resolves member, writes to DB or processes via ingest.
    """
    from pib.ingest import IngestEvent, ingest, make_idempotency_key, resolve_member

    # Validate API key
    expected_secret = os.environ.get("BLUEBUBBLES_SECRET", "")
    provided_secret = args.get("api_key", "")
    if not expected_secret:
        return {"error": "BLUEBUBBLES_SECRET not configured"}
    if provided_secret != expected_secret:
        return {"error": "Invalid API key", "status": "unauthorized"}

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

    # Resolve member
    event.member_id = await resolve_member(db, event)

    # Process through ingest pipeline
    actions = await ingest(event, db)

    return {
        "status": "processed",
        "message_guid": message_guid,
        "member_id": event.member_id,
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


# ═══════════════════════════════════════════════════════════
# COMMAND REGISTRY
# ═══════════════════════════════════════════════════════════

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
}


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
