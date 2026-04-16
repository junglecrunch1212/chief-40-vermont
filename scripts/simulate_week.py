"""7-day family simulation for PIB v5 — exercises all CLI commands against a seeded DB."""

import asyncio
import json
import logging
import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pib.db import get_connection
from pib.cli import (
    cmd_what_now, cmd_custody, cmd_state_update, cmd_task_create,
    cmd_task_complete, cmd_capture, cmd_recurring_done, cmd_recurring_skip,
    cmd_calendar_query, cmd_search, cmd_streak, cmd_scoreboard_data,
    cmd_budget, cmd_sensor_ingest, cmd_health, cmd_upcoming,
    cmd_morning_digest, cmd_context, cmd_bootstrap_verify,
    cmd_task_snooze, cmd_task_update, cmd_hold_create,
)
from pib.engine import transition_task

# ─── Setup logging ───
LOG_DIR = Path("/tmp/pib-sim/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "simulation.log", mode="w"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("sim")

# ─── Results tracker ───
results: dict[str, dict] = {}


def track(cmd: str, success: bool, detail: str = ""):
    if cmd not in results:
        results[cmd] = {"success": 0, "error": 0, "errors": []}
    if success:
        results[cmd]["success"] += 1
    else:
        results[cmd]["error"] += 1
        results[cmd]["errors"].append(detail[:200])


async def clear_rate_limit(db):
    """Remove rate-limit tracking records to prevent 3/min block."""
    await db.execute(
        "DELETE FROM mem_cos_activity WHERE action_type = 'cli_write' "
        "AND created_at >= datetime('now', '-120 seconds')"
    )
    await db.commit()


async def safe_call(cmd_name, handler, db, args, agent_id="dev"):
    """Call a CLI handler safely, tracking results."""
    try:
        result = await handler(db, args, agent_id)
        if isinstance(result, dict) and result.get("error"):
            track(cmd_name, False, str(result["error"]))
            log.warning(f"  {cmd_name}: error={result['error']}")
        else:
            track(cmd_name, True)
            log.info(f"  {cmd_name}: ok")
        return result
    except Exception as e:
        track(cmd_name, False, str(e))
        log.error(f"  {cmd_name}: EXCEPTION {e}")
        return {"error": str(e)}


SLEEP_QUALITIES = ["great", "okay", "rough"]
CAPTURE_TEXTS = [
    "grocery: eggs",
    "grocery: bread",
    "note: need to check AC filter",
    "remember Laura prefers oat milk",
    "idea: date night at the new Thai place",
    "note: call roofer about Saturday",
    "recipe: slow cooker chicken recipe from Sarah",
    "bookmark: https://example.com/adhd-tips",
    "remember Charlie has soccer at 4pm on Tuesdays",
    "note: Captain needs nail trim",
    "grocery: dog food",
    "important: passport renewal deadline May 1",
    "question: when does Charlie's school summer break start",
    "note: check baby registry for missing items",
]

TASK_TITLES = [
    ("Schedule dentist appointment", "small", "health"),
    ("Order diapers from Amazon", "tiny", "household"),
    ("Research pediatrician options", "medium", "health"),
    ("Fix kitchen faucet drip", "medium", "household"),
    ("Call insurance about claim", "small", "finance"),
    ("Set up baby monitor", "medium", "household"),
    ("Organize garage", "large", "household"),
    ("Book date night restaurant", "small", "family"),
    ("Update emergency contacts list", "tiny", "admin"),
    ("Clean out car", "small", "household"),
    ("Return library books", "tiny", "household"),
    ("Buy baby shower gift for Sarah", "small", "household"),
    ("Schedule oil change", "tiny", "household"),
    ("Review budget spreadsheet", "medium", "finance"),
]


async def simulate_day(db, day_date: date, day_num: int):
    """Simulate one day of family activity."""
    day_name = day_date.strftime("%A")
    log.info(f"{'='*60}")
    log.info(f"DAY {day_num}: {day_date.isoformat()} ({day_name})")
    log.info(f"{'='*60}")

    sleep_q = random.choice(SLEEP_QUALITIES)

    # ── James morning: meds + sleep ──
    log.info(f"  James: sleep={sleep_q}, meds=yes")
    await safe_call("state-update", cmd_state_update, db, {
        "member_id": "m-james",
        "meds_taken": 1,
        "meds_taken_at": f"{day_date.isoformat()}T07:30:00",
        "sleep_quality": sleep_q,
    })
    await clear_rate_limit(db)

    # ── Morning digest ──
    await safe_call("morning-digest", cmd_morning_digest, db, {"member_id": "m-james"})

    # ── Both check what-now ──
    await safe_call("what-now", cmd_what_now, db, {"member_id": "m-james"})
    await safe_call("what-now", cmd_what_now, db, {"member_id": "m-laura"})

    # ── Custody check ──
    await safe_call("custody", cmd_custody, db, {"date": day_date.isoformat()})

    # ── Calendar check ──
    await safe_call("calendar-query", cmd_calendar_query, db, {"date": day_date.isoformat()})

    # ── Upcoming recurring ──
    await safe_call("upcoming", cmd_upcoming, db, {"member_id": "m-james", "days": 3})

    # ── Context ──
    await safe_call("context", cmd_context, db, {"member_id": "m-james", "message": "what should I do today?"})

    # ── James creates and completes 1-3 tasks ──
    num_tasks = random.randint(1, 3)
    for i in range(num_tasks):
        title, effort, domain = random.choice(TASK_TITLES)
        title = f"{title} (day {day_num})"
        cr = await safe_call("task-create", cmd_task_create, db, {
            "title": title, "assignee": "m-james", "effort": effort,
        })
        await clear_rate_limit(db)

        if isinstance(cr, dict) and cr.get("task_id"):
            task_id = cr["task_id"]
            # Transition inbox -> next
            try:
                await transition_task(db, task_id, "next", {}, "dev")
                track("task-update(next)", True)
            except Exception as e:
                track("task-update(next)", False, str(e))

            # Complete it
            await safe_call("task-complete", cmd_task_complete, db, {
                "task_id": task_id, "member_id": "m-james",
            })
            await clear_rate_limit(db)

    # ── Laura completes 1-2 tasks ──
    num_laura = random.randint(1, 2)
    for i in range(num_laura):
        title, effort, domain = random.choice(TASK_TITLES)
        title = f"Laura: {title} (day {day_num})"
        cr = await safe_call("task-create", cmd_task_create, db, {
            "title": title, "assignee": "m-laura", "effort": effort,
        })
        await clear_rate_limit(db)

        if isinstance(cr, dict) and cr.get("task_id"):
            task_id = cr["task_id"]
            try:
                await transition_task(db, task_id, "next", {}, "dev")
                track("task-update(next)", True)
            except Exception as e:
                track("task-update(next)", False, str(e))
            await safe_call("task-complete", cmd_task_complete, db, {
                "task_id": task_id, "member_id": "m-laura",
            })
            await clear_rate_limit(db)

    # ── Captures ──
    captures = random.sample(CAPTURE_TEXTS, min(3, len(CAPTURE_TEXTS)))
    for text in captures:
        await safe_call("capture", cmd_capture, db, {
            "text": text, "member_id": "m-james",
        })
        await clear_rate_limit(db)

    # ── Recurring tasks ──
    if day_num <= 7:
        # Do morning meds recurring
        await safe_call("recurring-done", cmd_recurring_done, db, {
            "recurring_id": "rec-morning-meds", "member_id": "m-james",
        })
        await clear_rate_limit(db)

    # Skip Captain PM walk on day 3 (rain)
    if day_num == 3:
        await safe_call("recurring-skip", cmd_recurring_skip, db, {
            "recurring_id": "rec-captain-pm", "reason": "raining outside",
        })
        await clear_rate_limit(db)

    # ── Sensor ingest on day 2 ──
    if day_num == 2:
        await safe_call("sensor-ingest", cmd_sensor_ingest, db, {
            "source": "apple_health_sleep",
            "member_id": "m-james",
            "timestamp": f"{day_date.isoformat()}T06:00:00",
            "data": {"total_minutes": random.randint(300, 480)},
            "idempotency_key": f"sim-sleep-day{day_num}",
        })
        await clear_rate_limit(db)

    # ── Thursday custody handoff ──
    if day_name == "Thursday":
        log.info("  Thursday custody handoff check")
        await safe_call("custody", cmd_custody, db, {"date": day_date.isoformat()})
        # Also check tomorrow
        tomorrow = (day_date + timedelta(days=1)).isoformat()
        await safe_call("custody", cmd_custody, db, {"date": tomorrow})

    # ── Task snooze on day 4 ──
    if day_num == 4:
        cr = await safe_call("task-create", cmd_task_create, db, {
            "title": "Snooze test task", "assignee": "m-james",
        })
        await clear_rate_limit(db)
        if isinstance(cr, dict) and cr.get("task_id"):
            await safe_call("task-snooze", cmd_task_snooze, db, {
                "task_id": cr["task_id"],
                "scheduled_date": (day_date + timedelta(days=3)).isoformat(),
            })
            await clear_rate_limit(db)

    # ── Hold create on day 5 ──
    if day_num == 5:
        await safe_call("hold-create", cmd_hold_create, db, {
            "title": "Possible playdate at park",
            "date": (day_date + timedelta(days=2)).isoformat(),
            "start_time": "14:00",
            "end_time": "16:00",
            "member_id": "m-james",
        })
        await clear_rate_limit(db)

    # ── End of day checks ──
    await safe_call("streak", cmd_streak, db, {"member_id": "m-james"})
    await safe_call("scoreboard-data", cmd_scoreboard_data, db, {})


async def edge_case_tests(db):
    """Test edge cases: already-done task, nonexistent task, empty title, coach blocked, invalid transitions."""
    log.info(f"\n{'='*60}")
    log.info("EDGE CASE TESTS")
    log.info(f"{'='*60}")

    # 1. Complete an already-done task
    log.info("  Test: complete already-done task")
    cr = await safe_call("task-create", cmd_task_create, db, {
        "title": "Edge: already done test", "assignee": "m-james",
    })
    await clear_rate_limit(db)
    if isinstance(cr, dict) and cr.get("task_id"):
        tid = cr["task_id"]
        await transition_task(db, tid, "next", {}, "dev")
        await safe_call("task-complete", cmd_task_complete, db, {"task_id": tid, "member_id": "m-james"})
        await clear_rate_limit(db)
        # Try to complete again
        result = await safe_call("edge:complete-done", cmd_task_complete, db, {"task_id": tid, "member_id": "m-james"})
        if isinstance(result, dict) and "error" in str(result):
            track("edge:complete-done-rejected", True)
        else:
            track("edge:complete-done-rejected", False, "Should have been rejected")

    # 2. Complete nonexistent task
    log.info("  Test: complete nonexistent task")
    result = await safe_call("edge:nonexistent", cmd_task_complete, db, {"task_id": "tsk-DOESNOTEXIST", "member_id": "m-james"})

    # 3. Empty title task-create
    log.info("  Test: empty title task-create")
    result = await safe_call("edge:empty-title", cmd_task_create, db, {"title": "", "assignee": "m-james"})
    await clear_rate_limit(db)

    # 4. Coach agent trying task-create (should be blocked by allowlist)
    log.info("  Test: coach agent blocked from task-create")
    from pib.cli import check_agent_allowlist, load_agent_capabilities
    caps = load_agent_capabilities()
    ok, msg = check_agent_allowlist("coach", "task-create", caps)
    if not ok:
        track("edge:coach-blocked", True)
        log.info(f"  Coach correctly blocked: {msg}")
    else:
        track("edge:coach-blocked", False, "Coach should be blocked from task-create")

    # 5. Invalid state transition: done → inbox
    log.info("  Test: invalid transition done->inbox")
    cr = await safe_call("task-create", cmd_task_create, db, {
        "title": "Edge: invalid transition", "assignee": "m-james",
    })
    await clear_rate_limit(db)
    if isinstance(cr, dict) and cr.get("task_id"):
        tid = cr["task_id"]
        await transition_task(db, tid, "next", {}, "dev")
        await transition_task(db, tid, "done", {}, "dev")
        try:
            await transition_task(db, tid, "inbox", {}, "dev")
            track("edge:done-to-inbox", False, "Should have raised ValueError")
        except ValueError as e:
            track("edge:done-to-inbox", True)
            log.info(f"  Correctly rejected done->inbox: {e}")


async def final_checks(db):
    """Run comprehensive end-of-simulation checks."""
    log.info(f"\n{'='*60}")
    log.info("FINAL CHECKS")
    log.info(f"{'='*60}")

    await safe_call("health", cmd_health, db, {})
    await safe_call("budget", cmd_budget, db, {})
    await safe_call("search", cmd_search, db, {"query": "dentist", "member_id": "m-james"})
    await safe_call("bootstrap-verify", cmd_bootstrap_verify, db, {})

    # FTS5 check
    log.info("  Checking FTS5 index integrity...")
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM ops_tasks_fts WHERE ops_tasks_fts MATCH 'dentist' LIMIT 5"
        )
        count = len(rows) if rows else 0
        track("fts5-match-query", True)
        log.info(f"  FTS5 MATCH 'dentist': {count} results")
    except Exception as e:
        track("fts5-match-query", False, str(e))
        log.error(f"  FTS5 error: {e}")


async def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pib-sim/data/pib.db"
    log.info(f"PIB v5 Week Simulation — DB: {db_path}")

    db = await get_connection(db_path)
    try:
        # Simulate 7 days: Mon Apr 13 through Sun Apr 19, 2026
        start_date = date(2026, 4, 13)
        for day_num in range(1, 8):
            day_date = start_date + timedelta(days=day_num - 1)
            await simulate_day(db, day_date, day_num)

        # Edge cases
        await edge_case_tests(db)

        # Final checks
        await final_checks(db)

    finally:
        await db.close()

    # ── Summary ──
    log.info(f"\n{'='*60}")
    log.info("SIMULATION SUMMARY")
    log.info(f"{'='*60}")

    total_success = sum(r["success"] for r in results.values())
    total_error = sum(r["error"] for r in results.values())
    total = total_success + total_error

    log.info(f"Total calls: {total}")
    log.info(f"Successes: {total_success}")
    log.info(f"Errors: {total_error}")
    log.info(f"Success rate: {total_success/total*100:.1f}%" if total > 0 else "N/A")

    for cmd, data in sorted(results.items()):
        status = "PASS" if data["error"] == 0 else "FAIL"
        log.info(f"  [{status}] {cmd}: {data['success']} ok, {data['error']} err")
        for err in data["errors"]:
            log.info(f"         -> {err}")

    # Write JSON results
    results_path = LOG_DIR / "simulation_results.json"
    with open(results_path, "w") as f:
        json.dump({
            "total_calls": total,
            "successes": total_success,
            "errors": total_error,
            "success_rate": f"{total_success/total*100:.1f}%" if total > 0 else "N/A",
            "commands": results,
        }, f, indent=2, default=str)
    log.info(f"\nResults written to {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
