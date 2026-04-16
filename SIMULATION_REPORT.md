# PIB v5 Simulation Report

**Date:** 2026-04-16
**Branch:** `claude/simulate-user-activity-YkITf`
**Scope:** Full bootstrap + 7-day family simulation + API/CLI exercise + test suite

---

## Summary

| Layer | Tested | Pass | Fail | Notes |
|-------|--------|------|------|-------|
| Pytest suite | 599 tests | 587 | 12 | 5 sensor, 6 adapter, 1 CLI assertion |
| HTTP API | 56 endpoints | 54 | 2 | Both "failures" are correct behavior (404, 400) |
| CLI commands | 143 calls | 76 | 67 | 63 are rate-limit blocks, 4 are real bugs |
| Bootstrap (seed_data.py) | 1 run | 0 | 1 | 5 schema mismatches found and fixed |
| Bootstrap (seed.mjs) | 1 run | 0 | 1 | All INSERT INTO missing OR REPLACE |

**Total bugs found: 12**

---

## Bugs Found

### CRITICAL (Bootstrap Blockers)

#### BUG #1 — seed_data.py: wrong column name `adapter_type`
- **File:** `scripts/seed_data.py:324`
- **Error:** `sqlite3.OperationalError: table comms_channels has no column named adapter_type`
- **Root cause:** Schema (migration 012) uses `adapter_id`, seed script uses `adapter_type`
- **Impact:** Fresh bootstrap fails at channel seeding
- **Status:** FIXED in this branch

#### BUG #2 — seed_data.py: invalid CHECK value silently dropped
- **File:** `scripts/seed_data.py:317`
- **Error:** Downstream `FOREIGN KEY constraint failed` on `comms_channel_member_access`
- **Root cause:** `category='async'` for voicemail channel violates `CHECK (category IN ('conversational','broadcast','capture','administrative'))`. `INSERT OR IGNORE` silently swallows the CHECK violation, leaving the channel row absent. Access row then references a missing FK.
- **Impact:** Bootstrap fails with misleading FK error instead of CHECK error
- **Anti-pattern:** `INSERT OR IGNORE` masks constraint violations
- **Status:** FIXED — changed to `'conversational'`

#### BUG #3 — seed_data.py: wrong column names in comms_accounts
- **File:** `scripts/seed_data.py:372`
- **Error:** `table comms_accounts has no column named member_id`
- **Root cause:** Schema uses `owner_member_id` + `address`, seed uses `member_id` + `account_identifier`. Also `account_type` values ('gmail','apple_id','outlook') don't match CHECK ('email','phone','social','api','webhook').
- **Status:** FIXED — remapped all columns and values

#### BUG #4 — seed_data.py: wrong columns in fin_budget_config
- **File:** `scripts/seed_data.py:388`
- **Error:** Would fail on `id` and `icon` columns that don't exist
- **Root cause:** Schema has PK=`category` with no `id` or `icon` columns
- **Status:** FIXED — removed phantom columns

#### BUG #5 — seed_data.py: missing required columns in ops_recurring
- **File:** `scripts/seed_data.py:402`
- **Error:** Missing `type` (NOT NULL) and `next_due` (NOT NULL with CHECK); nonexistent `preferred_time`
- **Status:** FIXED — added `type='task'` and realistic `next_due` dates

#### BUG #6 — seed.mjs: all INSERT INTO missing OR REPLACE
- **File:** `console/seed.mjs` (30+ INSERT statements)
- **Error:** `UNIQUE constraint failed: common_members.id` when run after Python seed
- **Root cause:** All INSERT statements use bare `INSERT INTO` instead of `INSERT OR REPLACE INTO`. Since Python seed and migration 014 create overlapping rows, the Node seed crashes on the first collision.
- **Status:** FIXED — converted all to `INSERT OR REPLACE INTO`

### HIGH (Runtime Crashes)

#### BUG #7 — rewards.py: `sqlite3.Row.get()` doesn't exist
- **File:** `src/pib/rewards.py:214`
- **Error:** `AttributeError: 'sqlite3.Row' object has no attribute 'get'`
- **Root cause:** Code uses `member_row.get("age")` but `sqlite3.Row` only supports `member_row["age"]`
- **Impact:** Every `task-complete` CLI call crashes, blocking the reward/streak pipeline
- **Status:** FIXED — changed to `member_row["age"]`

#### BUG #10 — cmd_sensor_ingest: 3 schema mismatches vs pib_sensor_readings
- **File:** `src/pib/cli.py:1211`
- **Error:** `sqlite3.IntegrityError: datatype mismatch`
- **Root cause (triple mismatch):**
  1. `id` inserted as ULID text string but column is `INTEGER PRIMARY KEY AUTOINCREMENT`
  2. `confidence` inserted as float (1.0) but column has `CHECK (confidence IN ('high','medium','low','stale'))`
  3. Missing required `ttl_minutes` and `expires_at` columns (both NOT NULL)
- **Impact:** All sensor data ingest is broken (5 test failures)
- **Status:** NOT FIXED (requires schema or CLI redesign)

#### BUG #12 — channels.py: capabilities parsed as dict but stored as list
- **File:** `src/pib/channels.py:131`
- **Error:** `AttributeError: 'list' object has no attribute 'get'`
- **Root cause:** Channel `config_json` stores capabilities as `["in","out","draft"]` (list) but code expects `{"can_inbound": true, ...}` (dict).
- **Impact:** `channel-list` CLI command and any channel registry operations crash
- **Status:** NOT FIXED (requires format migration or parser update)

### MEDIUM (Design Issues)

#### BUG #8 — writes_per_minute: 3 is too restrictive
- **File:** `config/governance.yaml:89`
- **Issue:** A normal morning routine (log meds + complete task + capture note) triggers rate limiting within 60 seconds. In the simulation, 63 out of 67 CLI failures were rate-limit blocks.
- **Impact:** Real users doing rapid morning check-ins are blocked
- **Recommendation:** Increase to 15-20 or make per-command (don't count auto-approved state-update/capture against the write limit)
- **Status:** NOT FIXED (policy decision)

#### BUG #9 — Governance gates checked before input validation
- **File:** `src/pib/cli.py` (command flow)
- **Issue:** `task-update` with invalid transition (done→inbox) returns `"pending_approval"` instead of rejecting. `task-snooze` with missing `scheduled_date` also queues for approval instead of failing validation.
- **Impact:** Users get misleading "needs approval" responses for requests that can never succeed
- **Status:** NOT FIXED (architecture issue)

#### BUG #11 — bootstrap-verify memory_isolation uses invalid source value
- **File:** bootstrap-verify command in `src/pib/cli.py`
- **Error:** `CHECK constraint failed: source IN ('user_stated','inferred','observed','auto_promoted')`
- **Impact:** bootstrap-verify always reports memory_isolation as failed
- **Status:** NOT FIXED

---

## What Worked Well

1. **whatNow()** — Deterministic task selection worked perfectly across all 7 simulated days. Energy filtering, velocity cap, and task scoring all functioned correctly.
2. **Custody math** — `who_has_child()` returned correct results for all date queries.
3. **State machine** — Task transitions properly enforced (done→done rejected, guards for dismissed/deferred working).
4. **HTTP API** — 54/56 endpoints returned correct responses. Privacy filtering on Laura's work calendar properly redacted titles.
5. **Agent boundaries** — Coach agent correctly blocked from task-create. Dev agent has full access.
6. **Calendar context** — Events, scheduling impact, prep/travel times all correctly assembled.
7. **FTS5 search** — Memory search working.
8. **Scoreboard** — Family streaks, completions, custody parent all rendering correctly.
9. **Captures** — Note/recipe/grocery captures via API working, notebook assignment correct.
10. **Recurring tasks** — `recurring-done` properly advances next_due.

---

## Test Suite Failures (Pre-existing)

| Test | Root Cause | Bug # |
|------|-----------|-------|
| test_bridge_isolation (5 tests) | sensor_ingest datatype mismatch | #10 |
| test_adapters (6 tests) | Missing adapter modules (bluebubbles, sheets, etc.) | N/A (optional deps) |
| test_cli::test_coach_blocked_task_create | Assertion checks for "blocked" but msg says "does not have access" | Minor |

---

## Simulation Coverage

### CLI Commands Exercised
- `health`, `what-now`, `custody`, `morning-digest`, `calendar-query`, `budget`, `search`, `streak`, `scoreboard-data`, `upcoming`, `bootstrap-verify`, `member-settings-get`, `context`
- `state-update`, `task-create`, `task-complete`, `capture`, `recurring-done`, `recurring-skip`, `run-proactive-checks`, `channel-list`, `sensor-ingest`

### API Endpoints Exercised
- Identity: `/api/me`, `/api/health`, `/api/whoami`
- Today: `/api/today-stream`, `/api/energy`
- Tasks: `/api/tasks`, `/api/tasks/:id/complete`, `/api/tasks/:id/skip`, `/api/tasks/:id/triage`
- Calendar: `/api/schedule`, `/api/calendar/windows`, `/api/custody/today`
- Lists: `/api/lists`, `/api/lists/:name`, `/api/lists/:name/items`
- Captures: `/api/captures`, `/api/captures/stats`, `/api/captures/recipes`, `/api/capture`
- Comms: `/api/channels`, `/api/comms/inbox`
- People: `/api/people/contacts`, `/api/people/comms`, `/api/people/observations`, `/api/people/autonomy-tiers`
- Settings: `/api/config`, `/api/settings/permissions`, `/api/settings/gates`, `/api/settings/coaching`, `/api/settings/household`, `/api/settings/memory`, `/api/settings/captures`
- Chat: `/api/chat/history`
- Scoreboard: `/api/scoreboard`
- Budget: `/api/budget`
- Sensors: `/api/sensors`
- Household: `/api/household-status`, `/api/costs`, `/api/config/models`, `/api/decisions`, `/api/chores`

### Family Activity Simulated
- 7 days (Mon-Sun) of Stice-Sclafani household
- James: meds tracking, task completions, grocery captures, memory saves, recurring tasks
- Laura: sleep logging, task completions, calendar privacy
- Charlie: custody transitions, chore tracking
- Edge cases: coach agent boundaries, invalid transitions, empty titles, non-existent tasks
