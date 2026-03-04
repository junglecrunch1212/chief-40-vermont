# OpenClaw Integration Spec — PIB v5 on OpenClaw L0

**Purpose:** This document tells a fresh OpenClaw agent how to refactor PIB v5 (chief-40-vermont) to run on OpenClaw as its infrastructure layer. OpenClaw becomes L0. PIB's existing Layer 1 (core) and Layer 2 (intelligence) remain intact.

**Audience:** A new OpenClaw agent instance with zero prior context. Read this after reading `CLAUDE.md` and the build spec.

---

## 1. What OpenClaw Is

OpenClaw is a daemon + agent framework that provides:

| Capability | What it does | PIB equivalent it replaces |
|---|---|---|
| **Gateway daemon** | Always-on process, auto-restarts | `uvicorn` process management |
| **Channel routing** | Signal, WhatsApp, Telegram, webchat, SMS | Twilio webhooks, BlueBubbles webhooks in `web.py` |
| **Model routing** | Multi-provider LLM (Anthropic, OpenAI), swap via config | Direct `anthropic.AsyncAnthropic` client in `llm.py` |
| **Cron engine** | Scheduled tasks with heartbeat monitoring | `APScheduler` in `scheduler.py` |
| **`gog` CLI** | Google Calendar, Sheets, Gmail, Drive, Contacts | Any future Google adapters |
| **Agent sessions** | Conversation management, sub-agents | `mem_sessions` + `mem_messages` tables |
| **Workspace** | File-based config (SOUL.md, AGENTS.md, MEMORY.md) | `pib_config` table + `pib_coach_protocols` table |
| **Skill system** | Installable modules from clawhub.com | N/A (new capability) |

OpenClaw runs as a Node.js daemon. It executes workspace scripts (typically `.mjs`) and can shell out to any CLI or runtime, including Python.

---

## 2. What to Keep Untouched

These PIB v5 modules contain domain logic that has no equivalent in OpenClaw. Keep them as Python, call them from OpenClaw scripts.

| Module | Lines | Why it stays |
|---|---|---|
| `engine.py` | 360 | `whatNow()`, `DBSnapshot`, state machine, energy computation. Pure, deterministic, tested. |
| `rewards.py` | 176 | Variable-ratio reinforcement, elastic streaks, velocity tracking. |
| `custody.py` | 69 | DST-safe custody math. Pure function. |
| `memory.py` | 213 | FTS5 search, negation detection, dedup, auto-promotion. |
| `ingest.py` | 244 | Prefix parser, micro-script generator, idempotency, pipeline stages. |
| `voice.py` | 371 | Voice corpus collection, profile synthesis, hierarchical resolution. |
| `comms.py` | 497 | Batch windows, inbox queries, draft lifecycle, extraction. |
| `proactive.py` | 274 | 11 trigger definitions, guardrails (quiet hours, focus mode, rate limits). |
| `extraction.py` | 151 | Async extraction worker for comms enrichment. |
| `db.py` | 250 | SQLite connection, migrations, audit log, ID generation. |
| `cost.py` | 32 | API cost tracking. |
| `backup.py` | 105 | SQLite backup, FTS5 rebuild, cleanup. |
| `readiness.py` | 86 | Bootstrap readiness checks. |

**Total preserved:** ~2,828 lines of tested domain logic.

---

## 3. What to Replace

These PIB v5 components overlap with OpenClaw infrastructure. Replace them with OpenClaw equivalents.

### 3.1 `web.py` (1,574 lines) → OpenClaw gateway + console server

`web.py` is a FastAPI app that serves:
- **API endpoints** (tasks, schedule, budget, chat, scoreboard, etc.)
- **Webhook receivers** (Twilio, BlueBubbles, Siri)
- **SSE streaming** for chat
- **Auth middleware**

**Replace with:**
- **Console server** (Node.js, serves the dashboard UI + REST API for the frontend). This is a simple Express/Hono server that reads from SQLite and serves HTML/JSON. It does NOT handle messaging — OpenClaw does that.
- **Webhook receivers** → OpenClaw channel config. When a Signal/WhatsApp/iMessage message arrives, OpenClaw routes it to the agent. The agent calls Python scripts to process it.
- **Chat endpoint** → OpenClaw's built-in chat. The agent IS the chat interface. Context assembly happens in the agent's system prompt (AGENTS.md routing tables) or in a `context_assembler` script.

### 3.2 `llm.py` (1,224 lines) → OpenClaw model routing + agent tools

`llm.py` contains:
- Anthropic client management → **DROP** (OpenClaw routes to models)
- Tool definitions (20 tools) → **KEEP as concept, reframe as agent instructions.** Instead of Anthropic tool_use format, these become routing rules in AGENTS.md: "when user says X, run `python -m pib.cli what-now $PIB_DB_PATH --member m-james`"
- Context assembly (`assemble_context`, `build_cross_domain_summary`, `build_calendar_context`) → **KEEP logic, port to a script.** This becomes `scripts/core/context_assembler.mjs` (or `.py`) that the agent calls to build its system prompt.
- Relevance detection (`analyze_relevance`) → **KEEP.** Either port to JS or call from Python.
- System prompt builder → **MOVE to SOUL.md + AGENTS.md.** OpenClaw agents get their personality from SOUL.md and their routing from AGENTS.md. The per-member persona rules (James = ADHD carousel, Laura = brief/no-preamble) go in SOUL.md.
- Session management → **DROP.** OpenClaw manages sessions natively.
- Conversation history → **DROP.** OpenClaw handles this.
- Streaming → **DROP.** OpenClaw handles SSE/streaming to channels.
- Layer 1 fallback (`deterministic_fallback`) → **KEEP.** This is critical. When the LLM is unavailable, the agent should detect this and call the fallback script directly.

### 3.3 `scheduler.py` (369 lines) → OpenClaw cron

Every APScheduler job becomes an OpenClaw cron entry. Map:

| APScheduler job | Cron schedule | OpenClaw equivalent |
|---|---|---|
| `calendar_incremental_sync` | `*/15 * * * *` | `node scripts/core/calendar_sync.mjs --incremental` |
| `calendar_full_sync` | `0 2 * * *` | `node scripts/core/calendar_sync.mjs --full` |
| `compute_daily_states` | `30 5 * * *` | `python -m pib.cli compute-daily-states $PIB_DB_PATH` |
| `recurring_spawn` | `0 6 * * *` | `python -m pib.cli recurring-spawn $PIB_DB_PATH` |
| `escalation_check` | `0 17 * * *` | `python -m pib.cli escalation-check $PIB_DB_PATH` |
| `morning_digest` | `15 7 * * *` | `python -m pib.cli morning-digest $PIB_DB_PATH --member m-james` |
| `proactive_trigger_scan` | `*/30 7-22 * * *` | `python -m pib.cli proactive-scan $PIB_DB_PATH` |
| `auto_promote_session_facts` | `0 */6 * * *` | `python -m pib.cli promote-facts $PIB_DB_PATH` |
| `push_to_sheets` | `*/15 * * * *` | `python -m pib.cli push-sheets $PIB_DB_PATH` |
| `health_probe` | `*/30 * * * *` | OpenClaw heartbeat (HEARTBEAT.md) |
| `sqlite_backup` | `0 * * * *` | `python -m pib.cli backup $PIB_DB_PATH` |
| `cleanup_expired` | `0 3 * * *` | `python -m pib.cli cleanup $PIB_DB_PATH` |
| `fts5_rebuild` | `0 2 * * 0` | `python -m pib.cli fts5-rebuild $PIB_DB_PATH` |
| `extraction_worker` | `*/5 * * * *` | `python -m pib.cli extraction-worker $PIB_DB_PATH` |
| `unsnooze_comms` | `*/15 * * * *` | `python -m pib.cli unsnooze $PIB_DB_PATH` |
| `expire_stale_drafts` | `0 22 * * *` | `python -m pib.cli expire-drafts $PIB_DB_PATH` |
| `synthesize_voice_profiles` | `0 3 * * 0` | `python -m pib.cli synthesize-voices $PIB_DB_PATH` |

**✅ DONE:** `src/pib/cli.py` exists (1,023 lines, 26 commands, 6-layer permission boundary) that exposes each job as a subcommand. OpenClaw cron calls these via `exec`.

### 3.4 `auth.py` (127 lines) → OpenClaw channel auth

Twilio signature validation, BlueBubbles secret, Siri token — these are handled by OpenClaw's channel config. Drop `auth.py`. If Siri shortcuts need a custom webhook, implement it in the console server with a simple bearer token.

### 3.5 `bootstrap_wizard.py` (231 lines) → OpenClaw workspace init

The bootstrap wizard (env var setup, credential wiring) is replaced by:
1. `openclaw init` (creates workspace)
2. `gog auth login` (Google)
3. Manual `.env` setup for Anthropic, Twilio, BlueBubbles keys
4. `python -m pib.cli bootstrap $PIB_DB_PATH` (SQLite schema + seed data)

---

## 4. Integration Pattern

### 4.1 How OpenClaw calls PIB

OpenClaw scripts (`.mjs`) call Python via `child_process.execFile` or `exec`:

```javascript
// scripts/core/what_now.mjs
import { execSync } from 'child_process';
const result = JSON.parse(
  execSync('python -m pib.cli what-now $PIB_DB_PATH --member m-james --json', {
    cwd: '/path/to/pib',
    env: { ...process.env, PIB_DB_PATH: '/path/to/pib.db' },
  }).toString()
);
```

This is the same pattern OpenClaw already uses for `gog` (Go binary called from Node). No new architectural concepts.

### 4.2 How the agent routes messages

In AGENTS.md, define routing tables:

```markdown
## Message Routing

| User says | Route to |
|---|---|
| "What's next?" / "what now" | `python -m pib.cli what-now $PIB_DB_PATH --member {member_id} --json` |
| "Who has Charlie?" | `python -m pib.cli custody $PIB_DB_PATH --date {today} --json` |
| "grocery: milk, eggs" | `python -m pib.cli ingest $PIB_DB_PATH --prefix --text "{message}" --json` |
| "meds taken" | `python -m pib.cli state $PIB_DB_PATH --action medication_taken --member {member_id}` |
| "done" / "mark [task] done" | `python -m pib.cli complete $PIB_DB_PATH --task {task_id} --member {member_id} --json` |
| [anything else] | Full LLM chat with context assembly |
```

For full LLM chat, the agent:
1. Calls `python -m pib.cli context $PIB_DB_PATH --member {member_id} --message "{message}" --json` to get assembled context
2. Uses that context in its own system prompt
3. Has tool-call routing to PIB CLI commands for writes

### 4.3 How the console server works

A standalone Node.js server (Express or Hono) that:
- Serves the dashboard HTML/JS
- Exposes REST endpoints that read/write SQLite (via Python CLI or direct `better-sqlite3` reads)
- Runs on a dedicated port (e.g., 3333)
- Is started by OpenClaw cron or as a background process
- Does NOT handle messaging — that's OpenClaw's job

### 4.4 How calendar data flows

```
Google Calendar API
       │
       ▼
  gog CLI (OpenClaw ships this)
       │
       ▼
  calendar_sync.mjs (OpenClaw cron, every 15 min)
       │  calls: python -m pib.cli calendar-ingest $PIB_DB_PATH --json
       ▼
  cal_raw_events → cal_classified_events (SQLite)
       │
       ▼
  whatNow() reads cal_classified_events for scheduling impact
```

`gog` replaces the stubbed calendar adapter. The classification pipeline from `cal_raw_events` → `cal_classified_events` uses the existing `common_source_classifications` table and Gene 1 (discover → propose → confirm → config → deterministic).

---

## 5. File Structure After Refactor

```
workspace/
├── SOUL.md              ← PIB personality (from build spec §2, coaching protocols)
├── AGENTS.md            ← Routing tables, calendar/task/comms routing
├── MEMORY.md            ← OpenClaw memory (agent learns over time)
├── HEARTBEAT.md         ← Health checks (replaces health_probe scheduler job)
├── USER.md              ← Family constraints, privacy rules
├── config/
│   ├── .env             ← Credentials (gitignored)
│   └── calendar_rules.json  ← Source classifications (Gene 1 output)
├── scripts/core/
│   ├── context_assembler.mjs  ← Calls pib.cli context, formats for agent
│   ├── calendar_sync.mjs      ← gog CLI → pib.cli calendar-ingest
│   ├── what_now.mjs            ← Thin wrapper: calls pib.cli what-now
│   └── heartbeat_check.mjs    ← SQLite health + gog connectivity checks
├── console/
│   ├── server.mjs       ← Dashboard API server (port 3333)
│   └── index.html       ← Dashboard UI (scoreboard, stream, schedule, chat)
├── pib/                  ← Python package (chief-40-vermont domain logic)
│   ├── pyproject.toml
│   ├── src/pib/
│   │   ├── cli.py        ← NEW: CLI entry point for all commands
│   │   ├── engine.py     ← whatNow(), state machine (unchanged)
│   │   ├── rewards.py    ← Variable-ratio rewards (unchanged)
│   │   ├── custody.py    ← Custody math (unchanged)
│   │   ├── memory.py     ← FTS5 memory (unchanged)
│   │   ├── ingest.py     ← Prefix parser, pipeline (unchanged)
│   │   ├── voice.py      ← Voice intelligence (unchanged)
│   │   ├── comms.py      ← Comms domain (unchanged)
│   │   ├── proactive.py  ← Proactive triggers (unchanged)
│   │   ├── extraction.py ← Comms extraction (unchanged)
│   │   ├── db.py         ← SQLite connection (unchanged)
│   │   ├── cost.py       ← Cost tracking (unchanged)
│   │   ├── backup.py     ← Backup/cleanup (unchanged)
│   │   └── readiness.py  ← Bootstrap checks (unchanged)
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_add_energy_states.sql
│   │   ├── 003_comms_enhancement.sql
│   │   └── 004_voice_intelligence.sql
│   └── tests/            ← 20 test files (unchanged)
├── state/
│   └── pib.db            ← SQLite database (the SSOT)
└── docs/
    ├── pib-v5-build-spec.md   ← Master spec (unchanged)
    └── openclaw-integration.md ← This document
```

---

## 6. The One New File: `pib/src/pib/cli.py`

This is the only new Python file needed. It's a thin CLI that exposes every PIB capability as a subcommand with `--json` output:

```python
"""PIB CLI — OpenClaw integration surface."""
import argparse, json, asyncio, sys

async def main():
    parser = argparse.ArgumentParser(prog="pib")
    sub = parser.add_subparsers(dest="command")

    # what-now
    wn = sub.add_parser("what-now")
    wn.add_argument("--member", required=True)
    wn.add_argument("--json", action="store_true")

    # complete
    comp = sub.add_parser("complete")
    comp.add_argument("--task", required=True)
    comp.add_argument("--member", required=True)
    comp.add_argument("--json", action="store_true")

    # custody
    cust = sub.add_parser("custody")
    cust.add_argument("--date", default=None)
    cust.add_argument("--json", action="store_true")

    # context (for agent prompt assembly)
    ctx = sub.add_parser("context")
    ctx.add_argument("--member", required=True)
    ctx.add_argument("--message", required=True)
    ctx.add_argument("--json", action="store_true")

    # ingest (prefix commands)
    ing = sub.add_parser("ingest")
    ing.add_argument("--text", required=True)
    ing.add_argument("--member", default="m-james")
    ing.add_argument("--prefix", action="store_true")
    ing.add_argument("--json", action="store_true")

    # state (meds, sleep, focus)
    st = sub.add_parser("state")
    st.add_argument("--action", required=True)
    st.add_argument("--value", default=None)
    st.add_argument("--member", default="m-james")

    # ... add subcommands for every scheduler job ...

    args = parser.parse_args()
    # Route to appropriate async handler, print JSON to stdout
    ...

if __name__ == "__main__":
    asyncio.run(main())
```

OpenClaw calls this via `python -m pib.cli <command> $PIB_DB_PATH --json` and reads stdout.

---

## 7. Known Issues to Fix During Refactor

These bugs exist in the current c40v codebase. Fix them during integration:

1. **Monthly recurring spawn** (`scheduler.py` line ~330): `today.replace(month=today.month + 1)` crashes on Jan 31, Mar 31, etc. Use `dateutil.relativedelta` or a try/except with day rollback.

2. **Undo tool broken** (`llm.py` `_tool_undo_last`): reads `undo["undo_sql"]` but the `common_undo_log` schema has `restore_data`, not `undo_sql`. Either add an `undo_sql` column or change the tool to use `restore_data`.

3. **FTS5 triggers missing**: `ops_tasks_fts` and `ops_items_fts` virtual tables are defined but never populated. Add INSERT/UPDATE/DELETE triggers or rebuild them periodically.

4. **`select_reward` uses `random.random()`**: This is intentional (variable-ratio), but seed it for test determinism.

---

## 8. Bootstrap Sequence

On a fresh Mac Mini with OpenClaw installed:

```bash
# 1. Create workspace
openclaw init

# 2. Wire credentials
gog auth login                          # Google (Calendar, Sheets, Gmail)
# Set in .env: ANTHROPIC_API_KEY, TWILIO_*, BLUEBUBBLES_*, PIB_DB_PATH

# 3. Clone PIB into workspace
cd /path/to/workspace
git clone https://github.com/junglecrunch1212/chief-40-vermont.git pib

# 4. Install Python package
cd pib && pip install -e ".[dev]" && cd ..

# 5. Initialize SQLite
python -m pib.cli bootstrap $PIB_DB_PATH            # Apply schema + seed data

# 6. Write SOUL.md, AGENTS.md, HEARTBEAT.md
# (Agent can generate these from pib-v5-build-spec.md §2 and §4)

# 7. Configure OpenClaw cron jobs
# (Add entries matching the table in §3.3)

# 8. Start gateway
openclaw gateway start

# 9. Start console
node console/server.mjs &

# 10. Verify
python -m pib.cli what-now $PIB_DB_PATH --member m-james --json
# Should return a task with micro_script
```

---

## 9. What Success Looks Like

After refactor, the system should pass these probes:

| Probe | Command | Expected |
|---|---|---|
| whatNow works | `python -m pib.cli what-now $PIB_DB_PATH --member m-james --json` | Returns one task with micro_script |
| State machine works | `python -m pib.cli complete $PIB_DB_PATH --task tsk-001 --member m-james --json` | Returns reward tier + streak |
| Custody works | `python -m pib.cli custody $PIB_DB_PATH --json` | Returns parent member_id |
| Calendar syncs | `gog calendar events --json` then `python -m pib.cli calendar-ingest $PIB_DB_PATH` | Events in `cal_classified_events` |
| Messaging works | Send "what's next?" via Signal | Agent responds with whatNow result |
| Offline resilience | Kill Anthropic key, send "what's next?" | Agent uses Layer 1 fallback |
| Console serves | `curl localhost:3333/api/what-now/m-james` | JSON response |
| Tests pass | `cd pib && pytest tests/ -v` | All green |
| Proactive fires | Wait for 7:15 AM | Morning digest delivered via channel |
| Heartbeat healthy | Triggered by OpenClaw | All checks pass |
