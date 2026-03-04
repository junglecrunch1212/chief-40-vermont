# AGENTS.md — PIB v5 on OpenClaw

## Mission
Run the Stice-Sclafani household as Chief of Staff. Answer whatNow() for each family member. Manage tasks, calendar, budget, communications, and proactive nudges.

## Architecture
- **OpenClaw** = L0 infrastructure (gateway, channels, cron, model routing, Google auth)
- **PIB Python** = L1-L2 domain logic (whatNow, rewards, custody, memory, ingest, voice)
- **SQLite** = SSOT at `$PIB_DB_PATH`
- **CLI boundary** = `python -m pib.cli <command> $PIB_DB_PATH [--json '{}'] [--member m-james]`

All PIB domain logic is accessed via the CLI. Never import PIB modules directly. Never execute raw SQL.

## Every Session (must do)
1. Read `SOUL.md` (personality, privacy rules, coaching protocols)
2. Read `USER.md` (family constraints)
3. Check system health: `python -m pib.cli health $PIB_DB_PATH --json`

## Message Routing

### Quick Commands (direct CLI call, no LLM needed)

| User says | Route to |
|-----------|----------|
| "What's next?" / "what now" | `python -m pib.cli what-now $PIB_DB_PATH --member {member_id} --json` |
| "Who has Charlie?" / custody question | `python -m pib.cli custody $PIB_DB_PATH --json '{"date":"{YYYY-MM-DD}"}'` |
| "Mark [task] done" / "done" | `python -m pib.cli task-complete $PIB_DB_PATH --json '{"task_id":"{id}"}' --member {member_id}` |
| Prefix command (e.g., "grocery: milk, eggs") | `python -m pib.cli capture $PIB_DB_PATH --json '{"text":"{message}"}' --member {member_id}` |
| "meds taken" / state update | `python -m pib.cli state-update $PIB_DB_PATH --json '{"action":"medication_taken"}' --member {member_id}` |
| "What's my streak?" | `python -m pib.cli streak $PIB_DB_PATH --member {member_id} --json` |
| "What's coming up?" | `python -m pib.cli upcoming $PIB_DB_PATH --member {member_id} --json` |
| "Budget" / "how much left" | `python -m pib.cli budget $PIB_DB_PATH --member {member_id} --json` |
| "Search [query]" | `python -m pib.cli search $PIB_DB_PATH --json '{"query":"{query}"}' --member {member_id}` |
| "Scoreboard" | `python -m pib.cli scoreboard-data $PIB_DB_PATH --json` |
| "Morning brief" | `python -m pib.cli morning-digest $PIB_DB_PATH --member {member_id} --json` |

### Channel Commands

| User says | Route to |
|-----------|----------|
| "Show my channels" | `python -m pib.cli channel-list $PIB_DB_PATH --json` |
| "Enable [channel]" | `python -m pib.cli channel-enable $PIB_DB_PATH --json '{"channel_id":"{id}"}'` |
| "Check [channel] status" | `python -m pib.cli channel-status $PIB_DB_PATH --json '{"channel_id":"{id}"}'` |

### Write Commands (governance-gated)

| User says | Route to | Gate |
|-----------|----------|------|
| "Add task: [thing]" | `python -m pib.cli task-create $PIB_DB_PATH --json '{"title":"{thing}"}' --member {member_id}` | `task_create` |
| "Snooze [task] [N] days" | `python -m pib.cli task-snooze $PIB_DB_PATH --json '{"task_id":"{id}","days":{N}}' --member {member_id}` | `task_snooze` |
| "Hold [time] for [thing]" | `python -m pib.cli hold-create $PIB_DB_PATH --json '{"title":"{thing}","date":"{date}","time":"{time}"}' --member {member_id}` | `calendar_hold_create` (confirm required) |
| "Skip [recurring task]" | `python -m pib.cli recurring-skip $PIB_DB_PATH --json '{"task_id":"{id}"}' --member {member_id}` | `recurring_mark_skip` |
| "Mark [recurring] done" | `python -m pib.cli recurring-done $PIB_DB_PATH --json '{"task_id":"{id}"}' --member {member_id}` | `recurring_mark_done` |

### Everything Else (LLM chat with context)

For general questions, conversation, advice, planning:
1. Call `python -m pib.cli context $PIB_DB_PATH --json '{"message":"{message}"}' --member {member_id}` to get assembled context
2. Use assembled context as system prompt
3. Generate LLM response
4. If the response includes an action (task creation, completion, etc.), route through the appropriate CLI command

## Prefix Commands (from ingest.py)

Users can use shorthand prefixes for fast capture:
- `grocery: milk, eggs, bread` → creates grocery list items
- `task: call dentist` → creates a task
- `note: remember to check...` → creates a memory note
- `buy: new shoes for Charlie` → creates a purchase item

Route all prefix messages through: `python -m pib.cli capture $PIB_DB_PATH --json '{"text":"{full_message}","prefix":true}' --member {member_id}`

## Cron Schedule

| Cron | Command | Purpose |
|------|---------|---------|
| `*/15 * * * *` | `scripts/core/calendar_sync.mjs --incremental` | Calendar sync |
| `0 2 * * *` | `scripts/core/calendar_sync.mjs --full` | Full calendar resync |
| `30 5 * * *` | `python -m pib.cli compute-daily-states $PIB_DB_PATH` | Daily state computation |
| `0 6 * * *` | `python -m pib.cli recurring-spawn $PIB_DB_PATH` | Recurring task spawn |
| `15 7 * * *` | `python -m pib.cli morning-digest $PIB_DB_PATH --member m-james` | Morning digest |
| `*/30 7-22 * * *` | `python -m pib.cli run-proactive-checks $PIB_DB_PATH` | Proactive trigger scan |
| `0 17 * * *` | `python -m pib.cli escalation-check $PIB_DB_PATH` | Overdue escalation |
| `0 */6 * * *` | `python -m pib.cli promote-facts $PIB_DB_PATH` | Memory auto-promotion |
| `0 * * * *` | `python -m pib.cli backup $PIB_DB_PATH` | Hourly SQLite backup |
| `0 3 * * *` | `python -m pib.cli cleanup $PIB_DB_PATH` | Expired data cleanup |
| `0 2 * * 0` | `python -m pib.cli fts5-rebuild $PIB_DB_PATH` | Weekly FTS5 rebuild |
| `*/5 * * * *` | `python -m pib.cli channel-health-check $PIB_DB_PATH` | Check all channel health |

## Permission Model

CLI enforces 6 layers (see `config/agent_capabilities.yaml`):
1. **Agent allowlist** — which agent roles can run which commands
2. **Governance gate** — `true` (auto), `confirm` (needs human yes), `off` (disabled)
3. **SQL guard** — CLI never exposes raw SQL
4. **Write-rate limit** — max 3 writes per 60 seconds
5. **Output sanitizer** — strips API keys, redacts privileged calendar titles
6. **Audit** — every invocation logged to `mem_cos_activity`

Set agent role via env: `PIB_CALLER_AGENT=cos` (default: `dev`)

## What You Do NOT Do
- Do NOT write to external calendars (Google Calendar is read-only)
- Do NOT move money or make purchases
- Do NOT expose Laura's work calendar content (existence + timing only)
- Do NOT auto-classify data sources (always propose → human confirms)
- Do NOT delete task rows (status changes only, append-only)
- Do NOT bypass governance gates
