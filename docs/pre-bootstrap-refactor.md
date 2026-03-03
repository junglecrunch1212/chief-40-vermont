# Chief-40-Vermont Final Refactor Prompt + Checklist

**Target:** Claude Code execution against `chief-40-vermont` repo  
**Before:** Mac Mini M4 bootstrap (PIB Brain)  
**Estimated Time:** 12-16 hours  
**Generated:** 2026-03-03  

---

# PART 1: THE PROMPT (for Claude Code)

You are refactoring the Chief-40-Vermont (PIB v5) codebase to prepare it for production deployment on a 3-machine Mac Mini architecture running under OpenClaw. This refactor combines three critical workstreams:

1. **Machine/Bridge/Identity Architecture** (3 Mac Minis with separate Apple IDs)
2. **Agent Permission Boundaries** (6-layer enforcement model, 5 agent roles)
3. **15 Critical Findings + 28 Warnings** from consolidated audit

## Architecture Context

### Three-Machine Topology

**Mac Mini #1: "PIB Brain" (M4, new, ~$600)**
- Apple ID: `pib@icloud.com` (PIB's own identity)
- BlueBubbles: PIB's iMessage sender identity
- OpenClaw + c40v Python engine + SQLite
- Console :3333 (React dashboard)
- Scoreboard display
- All cron jobs (proactive checks, spawns)
- Twilio SMS fallback
- **Databases:**
  - `pib.db` — Household SSOT (tasks, calendar, memory, items)
  - `comms_james.db` — James raw messages (bridge → brain)
  - `comms_laura.db` — Laura raw messages (bridge → brain)
- **Bridge authentication:** API key validation
- **Privacy enforcement:** Cross-member message visibility blocked at query layer, encrypted at rest

**Mac Mini #2: "James Bridge" (used, headless, $100-150)**
- Apple ID: James's real iCloud account
- BlueBubbles → webhook → PIB Brain
- **Dumb pipe:** No data at rest, no databases, no secrets
- No OpenClaw, no intelligence, no logs

**Mac Mini #3: "Laura Bridge" (same as James, deployed later)**
- Apple ID: Laura's real iCloud account
- BlueBubbles → webhook → PIB Brain
- Same dumb pipe design

### Five Agent Roles (from `config/agent_capabilities.yaml`)

| Agent | Capabilities | Model | CLI Commands | SQL | File Write |
|-------|--------------|-------|--------------|-----|------------|
| **CoS** (Chief of Staff) | none | claude-sonnet-4-5 | 19 commands (read-heavy + gated writes) | none | read-only |
| **Coach** (ADHD coaching) | none | claude-sonnet-4-5 | 7 commands (streaks, state updates) | none | read-only |
| **Scoreboard** (display) | none | none (no LLM) | 3 commands (data feeds) | none | none |
| **Dev** (builder/admin) | full | claude-opus-4-6 | all | full | full |
| **Proactive** (cron) | none | none (deterministic) | 4 commands (scans + triggers) | none | none |

### Six-Layer Enforcement Model

1. **OpenClaw capabilities:** `none` → no exec/file tools at framework level
2. **CLI command allowlist:** Per-agent command authorization in cli.py
3. **Governance gates:** `confirm`/`off` from `governance.yaml` for write operations
4. **SQL guards:** DELETE/ALTER/DROP blocked by policy
5. **Output sanitizer:** Privacy redaction at CLI output layer (privileged calendar titles, financial data)
6. **Audit + anomaly detection:** Write-rate limits (>3 writes/60s = auto-pause + alert), all actions logged

## Execution Order (safest → largest)

Execute fixes in this order to minimize risk of cascading failures:

### Phase 1: Smallest/Safest Fixes (2-3 hours)

1. **Fix timezone handling** (engine.py + all modules)
2. **Fix llm.py undo column mismatch** (2-line change)
3. **Fix scheduler.py monthly spawn crash** (1-line change + dependency)
4. **Add FTS5 triggers migration** (new SQL file)
5. **Fix custody.py holiday override JSON parsing** (add try/except)
6. **Fix memory.py negation detection** (semantic change logic)

### Phase 2: CLI + Permission Infrastructure (4-6 hours)

7. **Create cli.py with 26+ commands** (new file, ~500-800 lines)
   - MVP 11 commands from checklist
   - Agent permission enforcement
   - Governance gate checks
   - Rate limit tracking
   - Privacy output sanitizer
   - Schema migration lock
   - SQL operation guards
8. **Wire PIB_CALLER_AGENT env var check** (entrypoint)
9. **Add write-rate anomaly detection** (>3/60s)
10. **Implement output sanitizer** (redact privileged calendar, strip financial for Coach)

### Phase 3: Bridge/Webhook Architecture (3-4 hours)

11. **Add BlueBubbles webhook receiver endpoint** (cli.py or new endpoint file)
12. **Add bridge authentication** (API key validation)
13. **Create separate per-member comms databases** (comms_james.db, comms_laura.db schemas)
14. **Add privacy config layer** (cross_member_visibility, excluded_contacts, sensitive_contacts)
15. **Wire voice corpus collection** (from bridge message streams)

### Phase 4: Critical Bug Fixes (2-3 hours)

16. **Fix rewards.py completion stats hardcoding** (extract real days_since_all_clear)
17. **Fix rewards.py bypass state machine guards** (add can_transition check)
18. **Fix proactive.py daily/hourly limits** (add member_id filter — 3 locations)
19. **Fix ingest.py meds/sleep dead ends** (write terminal handler for pib_energy_states)
20. **Fix comms.py batch window seed data** (proper morning/afternoon/evening rows)
21. **Fix proactive.py focus mode guardrail** (wire state-update CLI command)
22. **Fix ingest.py llm.py cross-reference** (remove LLM call, let OpenClaw handle)

### Phase 5: Warnings + Polish (1-2 hours)

23. **Add child-appropriate reward pool for Charlie** (rewards.py)
24. **Fix custody.py seed data** (midweek Thursday visits, not pure alternating_weeks)
25. **Implement primary_with_visitation schedule** (custody.py stub)
26. **Fix memory.py auto-promotion LIKE match** (false positives on short facts)
27. **Fix ingest.py resolve_member seed data** (populate phone/imessage_handle)
28. **Add ingest.py LLM failure retry** (queue drain)
29. **Fix voice.py client creation** (use OpenClaw model routing, not direct anthropic client)
30. **Add voice.py privilege filter** (exclude work calendar content from corpus)
31. **Fix db.py WriteQueue failure handling** (add retry + dead-letter queue)
32. **Fix db.py backup path** (use OpenClaw workspace path, not /opt/pib/data/backups)
33. **Migrate to ULIDs** (db.py ID generation, fix doc drift)
34. **Fix comms.py timezone consistency** (use local time for responded_at, not utcnow)
35. **Add FTS5 index for comms table** (migration, not just LIKE search)
36. **Fix engine.py calendar time parsing** (error handling for malformed times)
37. **Fix engine.py effort field defaults** (don't bypass energy filter)
38. **Update bootstrap.sh** (OpenClaw paths, no uvicorn, correct model)
39. **Implement proactive.py paralysis detection** (not just SQL placeholder)
40. **Remove proactive.py sensor trigger stubs** (no API integrations yet)
41. **Update readiness.py credential checks** (detect OpenClaw mode, not Google SA)
42. **Update openclaw-integration.md** (5 modules + 2 migrations missing, fix line counts)

## Definition of Done (DoD)

For EACH fix, you must deliver:

- [ ] **Code change** with line numbers and file paths cited
- [ ] **Regression test** (pytest test case that fails before fix, passes after)
- [ ] **Rollback plan** (how to undo if it breaks)
- [ ] **Validation command** (how to verify the fix works)

Example:

```
Fix: scheduler.py line 221 monthly spawn crash
Change: Replace `today.replace(month=today.month + 1)` with `today + relativedelta(months=1)`
Test: test_scheduler.py::test_monthly_spawn_on_31st
Rollback: git checkout src/pib/scheduler.py
Validate: pytest tests/test_scheduler.py::test_monthly_spawn_on_31st -v
```

## Regression Test Requirements

Every fix MUST include a pytest test that:

1. **Reproduces the bug** (test fails before fix)
2. **Validates the fix** (test passes after fix)
3. **Prevents regression** (CI/CD runs it forever)
4. **Includes edge cases** (Jan 31, leap years, empty strings, null values, etc.)

Example structure:

```python
@pytest.mark.asyncio
async def test_monthly_spawn_on_31st(tmp_db):
    """Regression: monthly spawn crashed on Jan 31 due to naive date arithmetic."""
    from datetime import date
    from pib.scheduler import spawn_recurring_tasks
    
    # Setup: create monthly recurring task with next_due = Jan 31
    await tmp_db.execute("""
        INSERT INTO ops_recurring (id, title, frequency, next_due)
        VALUES ('test-monthly', 'Test', 'MONTHLY', '2026-01-31')
    """)
    await tmp_db.commit()
    
    # Execute: spawn on Jan 31 (should compute Feb 28, not crash)
    result = await spawn_recurring_tasks(tmp_db, date(2026, 1, 31))
    
    # Assert: no crash, next_due advanced to Feb 28/29
    assert result['spawned'] == 1
    row = await tmp_db.execute_fetchone(
        "SELECT next_due FROM ops_recurring WHERE id = 'test-monthly'"
    )
    assert row['next_due'] in ['2026-02-28', '2026-02-29']
```

## Key Architectural Principles

1. **Operational agents interact ONLY through cli.py.** No direct SQL, no file writes, no exec.
2. **cli.py is the permission boundary.** All agent commands flow through it.
3. **Bridges are dumb pipes.** No intelligence, no data storage, no secrets.
4. **Privacy is enforced at query layer.** Not just prompt instructions — actual DB/output filters.
5. **Governance gates override agent capabilities.** Even if an agent CAN call a command, governance.yaml may require confirmation.
6. **All writes are audited.** ops_ledger + mem_cos_activity track every mutation.
7. **Rate limits prevent runaway agents.** >3 writes/60s = auto-pause + alert.
8. **Timezone-aware everywhere.** Replace all `datetime.now()` with `datetime.now(ZoneInfo("America/New_York"))`.

## Critical File References

- `src/pib/cli.py` — NEW FILE (must create, ~500-800 lines)
- `src/pib/engine.py` — Timezone fixes (datetime.now calls)
- `src/pib/scheduler.py` — Line 221 (monthly spawn)
- `src/pib/llm.py` — Line 715-716 (undo column)
- `src/pib/rewards.py` — get_completion_stats(), complete_task_with_reward()
- `src/pib/proactive.py` — Lines with daily_limit, hourly_limit, in_meeting checks (3 locations)
- `src/pib/ingest.py` — Line 160 (llm.py cross-ref), meds/sleep handlers, resolve_member
- `src/pib/comms.py` — Batch window seed data, responded_at timezone, FTS5
- `src/pib/custody.py` — Holiday override JSON, seed data, primary_with_visitation stub
- `src/pib/memory.py` — Semantic change detection, auto-promotion LIKE
- `src/pib/voice.py` — Anthropic client creation, corpus privilege filter
- `src/pib/db.py` — WriteQueue retry, backup path, ULID generation
- `src/pib/readiness.py` — Credential checks (OpenClaw mode detection)
- `migrations/007_fts5_triggers.sql` — NEW FILE (9 triggers)
- `config/agent_capabilities.yaml` — READ (already exists)
- `config/governance.yaml` — READ (already exists)
- `docs/openclaw-integration.md` — UPDATE (5 modules + 2 migrations missing)
- `bootstrap.sh` — UPDATE (stale paths/commands)

## Commands for Validation

After each fix, run:

```bash
# Single test
pytest tests/test_<module>.py::test_<specific> -v

# Full suite
pytest tests/ -v --tb=short

# CLI smoke test
python -m pib.cli bootstrap test.db

# FTS5 triggers
sqlite3 test.db "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%fts%';"

# Agent permission test
PIB_CALLER_AGENT=coach python -m pib.cli task-create test.db --title "test"
# Should return: {"error": "forbidden"}

PIB_CALLER_AGENT=cos python -m pib.cli task-create test.db --title "test"
# Should succeed

# Rate limit test
for i in 1 2 3 4; do
  PIB_CALLER_AGENT=cos python -m pib.cli task-create test.db --title "test-$i"
done
# 4th should return: {"error": "rate_limited"}
```

## Success Criteria (all must pass)

- [ ] `pytest tests/ -v` exits with code 0 (all tests pass)
- [ ] `python -m pib.cli bootstrap test.db` returns `{"ok": true}`
- [ ] All 15 critical findings have regression tests
- [ ] cli.py enforces agent command allowlists
- [ ] cli.py blocks >3 writes/60s
- [ ] cli.py redacts privileged calendar titles for CoS/Coach
- [ ] cli.py strips financial data for Coach
- [ ] Webhook endpoint accepts BlueBubbles POST with API key auth
- [ ] comms_james.db and comms_laura.db schemas exist
- [ ] No imports of REPLACED modules in KEPT modules
- [ ] All datetime.now() calls use timezone (America/New_York)
- [ ] FTS5 triggers fire on INSERT/UPDATE/DELETE
- [ ] Monthly spawn works on Jan 31, Mar 31, May 31, Aug 31, Oct 31, Dec 31
- [ ] Undo reads restore_data column (not undo_sql)
- [ ] Privacy canary test passes (privileged titles never leak)

---

# PART 2: THE CHECKLIST

## Priority Legend

- **P0:** Blocks bootstrap (Mac Mini won't start)
- **P1:** Blocks family use (unsafe/broken for Laura/James/Charlie)
- **P2:** Quality/polish (works but suboptimal)

---

## P0: BLOCKERS (must complete before bootstrap)

### 1. Create cli.py with Agent Permissions [P0]

**Files:** `src/pib/cli.py` (new), `pyproject.toml` (add script entry)  
**Time:** 4-6 hours  
**Why:** OpenClaw agents need a permission-enforced CLI boundary. No cli.py = no safe agent execution.

**Changes:**
- Create `src/pib/cli.py` with 26+ commands (MVP 11 + extended)
- Commands: bootstrap, what-now, ingest-event, spawn-recurring, sync-calendar, sync-gmail, compute-daily-state, run-proactive-checks, backup, get-digest, handle-approval, task-create, task-complete, task-update, task-snooze, hold-create, hold-confirm, hold-reject, recurring-done, recurring-skip, state-update, capture, calendar-query, custody, budget, search, morning-digest, health, streak, upcoming
- Load `PIB_CALLER_AGENT` env var at entrypoint
- Load `config/agent_capabilities.yaml` and `config/governance.yaml`
- Check command permission: `if command not in allowed[agent]: return {"error": "forbidden"}`
- Write-rate tracking: count writes in last 60s, block if ≥3
- Output sanitizer: redact privileged calendar titles, strip financial data for Coach
- Schema migration lock: dev-only + `--allow-schema-change` flag required
- SQL operation guards: block DELETE/ALTER/DROP via governance.yaml policy
- All functions return JSON-serializable dicts
- Async operations wrapped in `asyncio.run()`
- Add `pib = "pib.cli:main"` to pyproject.toml scripts

**Regression Test:**
```python
# tests/test_cli.py (new file)

def test_agent_permission_enforcement():
    """Coach agent cannot create tasks (not in allowlist)."""
    result = subprocess.run(
        ["python", "-m", "pib.cli", "task-create", "test.db", "--title", "test"],
        env={"PIB_CALLER_AGENT": "coach"},
        capture_output=True
    )
    output = json.loads(result.stdout)
    assert output["error"] == "forbidden"
    assert output["agent"] == "coach"

def test_write_rate_limit():
    """4th write in 60s triggers rate limit."""
    for i in range(4):
        result = subprocess.run(
            ["python", "-m", "pib.cli", "task-create", "test.db", "--title", f"test-{i}"],
            env={"PIB_CALLER_AGENT": "cos"},
            capture_output=True
        )
    output = json.loads(result.stdout)
    assert output.get("error") == "rate_limited"

def test_privacy_sanitizer():
    """Privileged calendar titles redacted for CoS."""
    # Setup: calendar event with privileged title
    # Call: calendar-query via CoS agent
    # Assert: title is "🔒 Work commitment", not real title
```

**Rollback:** `git rm src/pib/cli.py`, revert pyproject.toml  
**Validate:** `python -m pib.cli bootstrap test.db` returns valid JSON

---

### 2. Fix Timezone Handling [P0]

**Files:** `src/pib/engine.py`, `src/pib/scheduler.py`, `src/pib/rewards.py`, `src/pib/proactive.py`, `src/pib/ingest.py`, `src/pib/comms.py`, `src/pib/custody.py`, `src/pib/memory.py`, `src/pib/voice.py`, `src/pib/db.py`  
**Time:** 1-2 hours  
**Why:** Naive datetime.now() causes silent timezone bugs (off-by-5-hours in EST).

**Changes:**
```python
# BEFORE (all modules):
from datetime import datetime
now = datetime.now()

# AFTER:
from datetime import datetime
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo("America/New_York"))
```

Find all instances:
```bash
grep -rn "datetime.now()" src/pib/*.py | grep -v "ZoneInfo"
# Replace each with datetime.now(ZoneInfo("America/New_York"))
```

**Regression Test:**
```python
def test_timezone_aware():
    """All datetime.now() calls use America/New_York."""
    import ast, os
    for root, dirs, files in os.walk("src/pib"):
        for file in files:
            if file.endswith(".py"):
                with open(os.path.join(root, file)) as f:
                    tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if hasattr(node.func, 'attr') and node.func.attr == 'now':
                                # Assert: has ZoneInfo arg or is datetime.now(tz)
                                assert len(node.args) > 0 or any(k.arg == 'tz' for k in node.keywords)
```

**Rollback:** `git checkout src/pib/*.py`  
**Validate:** Run test above, check all now() calls have tz

---

### 3. Fix Monthly Spawn Crash [P0]

**Files:** `src/pib/scheduler.py` (line 221), `pyproject.toml` (add dependency)  
**Time:** 15 minutes  
**Why:** Crashes on Jan 31, Mar 31, May 31, Aug 31, Oct 31, Dec 31 when computing next month.

**Changes:**
```python
# BEFORE (scheduler.py line 221):
next_due = today.replace(month=today.month + 1) if today.month < 12 else today.replace(year=today.year + 1, month=1)

# AFTER:
from dateutil.relativedelta import relativedelta
next_due = today + relativedelta(months=1)

# pyproject.toml dependencies:
"python-dateutil>=2.8.0",  # ADD THIS
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_monthly_spawn_on_31st(tmp_db):
    """Regression: monthly spawn crashed on Jan 31."""
    from datetime import date
    from pib.scheduler import spawn_recurring_tasks
    
    await tmp_db.execute("""
        INSERT INTO ops_recurring (id, title, frequency, next_due)
        VALUES ('test-monthly', 'Test', 'MONTHLY', '2026-01-31')
    """)
    await tmp_db.commit()
    
    result = await spawn_recurring_tasks(tmp_db, date(2026, 1, 31))
    assert result['spawned'] == 1
    
    row = await tmp_db.execute_fetchone(
        "SELECT next_due FROM ops_recurring WHERE id = 'test-monthly'"
    )
    assert row['next_due'] in ['2026-02-28', '2026-02-29']
```

**Rollback:** `git checkout src/pib/scheduler.py`, remove dateutil from pyproject.toml  
**Validate:** `pytest tests/test_scheduler.py::test_monthly_spawn_on_31st -v`

---

### 4. Fix Undo Column Mismatch [P0]

**Files:** `src/pib/llm.py` (lines 715-716)  
**Time:** 5 minutes  
**Why:** Undo reads wrong column (undo_sql vs restore_data), causes "No undo SQL" errors.

**Changes:**
```python
# BEFORE (llm.py lines 715-716):
if undo.get("undo_sql"):
    await db.executescript(undo["undo_sql"])

# AFTER:
if undo.get("restore_data"):
    await db.executescript(undo["restore_data"])
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_undo_restores_data(tmp_db):
    """Undo reads restore_data column correctly."""
    await tmp_db.execute("""
        INSERT INTO common_undo_log (operation, table_name, entity_id, restore_data, actor)
        VALUES ('DELETE', 'ops_tasks', 'task-123', 
                'INSERT INTO ops_tasks (id, title) VALUES ("task-123", "Test")',
                'laura')
    """)
    await tmp_db.commit()
    
    from pib.llm import _tool_undo
    result = await _tool_undo(tmp_db, {}, 'laura')
    
    assert 'error' not in result
    assert 'undone' in result
```

**Rollback:** `git checkout src/pib/llm.py`  
**Validate:** `pytest tests/test_llm.py::test_undo_restores_data -v`

---

### 5. Add FTS5 Triggers Migration [P0]

**Files:** `migrations/007_fts5_triggers.sql` (new)  
**Time:** 15 minutes  
**Why:** FTS5 tables (ops_tasks_fts, ops_items_fts, mem_long_term_fts) don't sync on INSERT/UPDATE/DELETE.

**Changes:**
Create `migrations/007_fts5_triggers.sql`:
```sql
-- ops_tasks_fts triggers
CREATE TRIGGER ops_tasks_fts_insert AFTER INSERT ON ops_tasks BEGIN
    INSERT INTO ops_tasks_fts(rowid, title, notes, micro_script)
    VALUES (NEW.rowid, NEW.title, NEW.notes, NEW.micro_script);
END;

CREATE TRIGGER ops_tasks_fts_update AFTER UPDATE ON ops_tasks BEGIN
    DELETE FROM ops_tasks_fts WHERE rowid = OLD.rowid;
    INSERT INTO ops_tasks_fts(rowid, title, notes, micro_script)
    VALUES (NEW.rowid, NEW.title, NEW.notes, NEW.micro_script);
END;

CREATE TRIGGER ops_tasks_fts_delete AFTER DELETE ON ops_tasks BEGIN
    DELETE FROM ops_tasks_fts WHERE rowid = OLD.rowid;
END;

-- ops_items_fts triggers (3 triggers, same pattern)
-- mem_long_term_fts triggers (3 triggers, same pattern)

INSERT INTO meta_schema_version (version, description) 
VALUES (7, 'Add FTS5 triggers for ops_tasks, ops_items, mem_long_term');
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_fts5_triggers_fire(tmp_db):
    """FTS5 tables sync on INSERT/UPDATE/DELETE."""
    await tmp_db.execute("""
        INSERT INTO ops_tasks (id, title, notes, micro_script, assignee, domain)
        VALUES ('test-1', 'Buy milk', 'Whole milk', 'store', 'laura', 'household')
    """)
    await tmp_db.commit()
    
    row = await tmp_db.execute_fetchone(
        "SELECT title FROM ops_tasks_fts WHERE ops_tasks_fts MATCH 'milk'"
    )
    assert row['title'] == 'Buy milk'
    
    # UPDATE
    await tmp_db.execute("UPDATE ops_tasks SET title = 'Buy almond milk' WHERE id = 'test-1'")
    await tmp_db.commit()
    
    row = await tmp_db.execute_fetchone(
        "SELECT title FROM ops_tasks_fts WHERE ops_tasks_fts MATCH 'almond'"
    )
    assert row['title'] == 'Buy almond milk'
    
    # DELETE
    await tmp_db.execute("DELETE FROM ops_tasks WHERE id = 'test-1'")
    await tmp_db.commit()
    
    row = await tmp_db.execute_fetchone(
        "SELECT title FROM ops_tasks_fts WHERE ops_tasks_fts MATCH 'almond'"
    )
    assert row is None
```

**Rollback:** `git rm migrations/007_fts5_triggers.sql`  
**Validate:** `sqlite3 test.db "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '%fts%';"` (should show 9 triggers)

---

### 6. Remove ingest.py llm.py Cross-Reference [P0]

**Files:** `src/pib/ingest.py` (line 160)  
**Time:** 30 minutes  
**Why:** ingest.py imports llm.py (REPLACED module), causes import errors under OpenClaw.

**Changes:**
```python
# BEFORE (ingest.py line 160-171):
from pib.llm import chat as llm_chat
result = await llm_chat(db, event.text, event.member_id, channel)

# AFTER:
# Remove lines 160-171
# Let OpenClaw handle LLM routing outside of ingest pipeline
# Ingest only does: dedup → parse → route → store
```

**Regression Test:**
```python
def test_ingest_no_replaced_imports():
    """ingest.py does not import REPLACED modules."""
    with open("src/pib/ingest.py") as f:
        content = f.read()
        assert "from pib.llm import" not in content
        assert "import pib.llm" not in content
```

**Rollback:** `git checkout src/pib/ingest.py`  
**Validate:** `pytest tests/test_ingest.py -v`, no import errors

---

## P1: CRITICAL (blocks family use)

### 7. Add BlueBubbles Webhook Receiver [P1]

**Files:** `src/pib/cli.py` (add webhook-receive command) OR `src/pib/webhook.py` (new)  
**Time:** 1-2 hours  
**Why:** Bridges need to send messages to PIB Brain. No webhook = no inbound comms.

**Changes:**
Option A: Add to cli.py
```python
def webhook_receive(db_path: str, payload: str, api_key: str) -> dict:
    """Receive webhook from BlueBubbles bridge."""
    # Validate API key
    if not validate_bridge_api_key(api_key):
        return {"error": "unauthorized"}
    
    # Parse payload
    msg = json.loads(payload)
    member_id = msg.get("bridge_id")  # "james" or "laura"
    
    # Write to member-specific comms DB
    comms_db = f"comms_{member_id}.db"
    conn = sqlite3.connect(comms_db)
    conn.execute("""
        INSERT INTO raw_messages (id, text, sender, timestamp, metadata)
        VALUES (?, ?, ?, ?, ?)
    """, [msg["id"], msg["text"], msg["sender"], msg["timestamp"], json.dumps(msg)])
    conn.commit()
    conn.close()
    
    # Queue for PIB processing
    main_conn = sqlite3.connect(db_path)
    main_conn.execute("""
        INSERT INTO mem_pending_events (member_id, event_type, event_data, created_at)
        VALUES (?, 'imessage', ?, ?)
    """, [member_id, payload, datetime.now(ZoneInfo("America/New_York")).isoformat()])
    main_conn.commit()
    main_conn.close()
    
    return {"ok": True, "queued": True}
```

Option B: Separate webhook.py with Flask/FastAPI endpoint
```python
# src/pib/webhook.py
from fastapi import FastAPI, Header, HTTPException
import json

app = FastAPI()

@app.post("/bluebubbles/webhook")
async def receive_webhook(payload: dict, x_api_key: str = Header(None)):
    if not validate_bridge_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Same logic as Option A
    return {"ok": True}
```

**Regression Test:**
```python
def test_webhook_auth():
    """Webhook rejects invalid API keys."""
    result = subprocess.run(
        ["python", "-m", "pib.cli", "webhook-receive", "test.db", 
         '{"text": "test"}', "INVALID_KEY"],
        capture_output=True
    )
    output = json.loads(result.stdout)
    assert output["error"] == "unauthorized"

def test_webhook_writes_to_comms_db():
    """Webhook writes to member-specific comms DB."""
    payload = json.dumps({
        "id": "msg-123",
        "bridge_id": "james",
        "text": "Test message",
        "sender": "+15555551234",
        "timestamp": "2026-03-03T10:00:00-05:00"
    })
    
    result = subprocess.run(
        ["python", "-m", "pib.cli", "webhook-receive", "test.db", 
         payload, "VALID_KEY"],
        capture_output=True
    )
    output = json.loads(result.stdout)
    assert output["ok"] == True
    
    # Check comms_james.db
    conn = sqlite3.connect("comms_james.db")
    row = conn.execute("SELECT text FROM raw_messages WHERE id = 'msg-123'").fetchone()
    assert row[0] == "Test message"
```

**Rollback:** `git checkout src/pib/cli.py` or `git rm src/pib/webhook.py`  
**Validate:** `curl -X POST -H "X-API-Key: test" http://localhost:3333/bluebubbles/webhook -d '{"test": true}'`

---

### 8. Create Separate Comms Databases [P1]

**Files:** `migrations/008_comms_james_schema.sql` (new), `migrations/009_comms_laura_schema.sql` (new)  
**Time:** 30 minutes  
**Why:** Privacy requirement — James and Laura message logs must be in separate encrypted DBs.

**Changes:**
```sql
-- migrations/008_comms_james_schema.sql
CREATE TABLE IF NOT EXISTS raw_messages (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metadata TEXT,  -- JSON blob
    created_at TEXT DEFAULT (datetime('now')),
    indexed INTEGER DEFAULT 0
);

CREATE INDEX idx_raw_messages_timestamp ON raw_messages(timestamp);
CREATE INDEX idx_raw_messages_indexed ON raw_messages(indexed);

-- migrations/009_comms_laura_schema.sql (same schema)
```

**Regression Test:**
```python
def test_comms_db_isolation():
    """James and Laura comms DBs are separate."""
    # Write to James DB
    james_conn = sqlite3.connect("comms_james.db")
    james_conn.execute("""
        INSERT INTO raw_messages (id, text, sender, recipient, timestamp)
        VALUES ('msg-1', 'Test', '+15555551234', 'james', '2026-03-03T10:00:00')
    """)
    james_conn.commit()
    james_conn.close()
    
    # Laura DB should NOT have this message
    laura_conn = sqlite3.connect("comms_laura.db")
    row = laura_conn.execute("SELECT id FROM raw_messages WHERE id = 'msg-1'").fetchone()
    assert row is None
```

**Rollback:** `rm comms_james.db comms_laura.db`, `git rm migrations/008*.sql migrations/009*.sql`  
**Validate:** `sqlite3 comms_james.db ".schema"`, `sqlite3 comms_laura.db ".schema"`

---

### 9. Fix rewards.py Completion Stats Hardcoding [P1]

**Files:** `src/pib/rewards.py` (get_completion_stats function)  
**Time:** 30 minutes  
**Why:** days_since_all_clear='?' and days_old=0 hardcoded, breaks reward logic.

**Changes:**
```python
# BEFORE (rewards.py get_completion_stats):
return {
    "days_since_all_clear": "?",
    "days_old": 0,
    # ...
}

# AFTER:
# Extract real values from task/completion data
last_all_clear = await db.execute_fetchone("""
    SELECT MAX(completed_at) FROM ops_task_completions 
    WHERE task_id IN (SELECT id FROM ops_tasks WHERE priority = 'critical')
""")
days_since_all_clear = (datetime.now(ZoneInfo("America/New_York")) - 
                        datetime.fromisoformat(last_all_clear[0])).days if last_all_clear[0] else None

task_created = await db.execute_fetchone(
    "SELECT created_at FROM ops_tasks WHERE id = ?", [task_id]
)
days_old = (datetime.now(ZoneInfo("America/New_York")) - 
            datetime.fromisoformat(task_created[0])).days if task_created[0] else 0

return {
    "days_since_all_clear": days_since_all_clear,
    "days_old": days_old,
    # ...
}
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_completion_stats_real_values(tmp_db):
    """get_completion_stats returns real days_since_all_clear and days_old."""
    # Setup: task created 5 days ago
    created = (datetime.now(ZoneInfo("America/New_York")) - timedelta(days=5)).isoformat()
    await tmp_db.execute("""
        INSERT INTO ops_tasks (id, title, created_at, priority)
        VALUES ('task-1', 'Test', ?, 'critical')
    """, [created])
    await tmp_db.commit()
    
    from pib.rewards import get_completion_stats
    stats = await get_completion_stats(tmp_db, 'task-1')
    
    assert stats["days_old"] == 5
    assert stats["days_since_all_clear"] != "?"
```

**Rollback:** `git checkout src/pib/rewards.py`  
**Validate:** `pytest tests/test_rewards.py::test_completion_stats_real_values -v`

---

### 10. Fix rewards.py State Machine Bypass [P1]

**Files:** `src/pib/rewards.py` (complete_task_with_reward function)  
**Time:** 15 minutes  
**Why:** Bypasses state machine guards, can mark tasks complete even if not allowed.

**Changes:**
```python
# BEFORE (rewards.py complete_task_with_reward):
await db.execute("UPDATE ops_tasks SET status = 'done' WHERE id = ?", [task_id])

# AFTER:
from pib.engine import can_transition
if not can_transition(current_status, 'done'):
    raise ValueError(f"Cannot transition from {current_status} to done")

await db.execute("UPDATE ops_tasks SET status = 'done' WHERE id = ?", [task_id])
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_complete_task_respects_state_machine(tmp_db):
    """complete_task_with_reward checks can_transition."""
    await tmp_db.execute("""
        INSERT INTO ops_tasks (id, title, status, assignee, domain)
        VALUES ('task-1', 'Test', 'blocked', 'laura', 'household')
    """)
    await tmp_db.commit()
    
    from pib.rewards import complete_task_with_reward
    with pytest.raises(ValueError, match="Cannot transition"):
        await complete_task_with_reward(tmp_db, 'task-1', 'laura')
```

**Rollback:** `git checkout src/pib/rewards.py`  
**Validate:** `pytest tests/test_rewards.py::test_complete_task_respects_state_machine -v`

---

### 11. Fix proactive.py Per-Member Limits [P1]

**Files:** `src/pib/proactive.py` (3 locations: daily_limit, hourly_limit, in_meeting check)  
**Time:** 30 minutes  
**Why:** Limits count globally, not per-member. Laura's activity blocks James's nudges.

**Changes:**
```python
# BEFORE (proactive.py daily limit check):
count = await db.execute_fetchone(
    "SELECT COUNT(*) FROM mem_cos_activity WHERE action_type = 'proactive_nudge' AND DATE(created_at) = DATE('now')"
)

# AFTER:
count = await db.execute_fetchone(
    "SELECT COUNT(*) FROM mem_cos_activity WHERE action_type = 'proactive_nudge' AND actor = ? AND DATE(created_at) = DATE('now')",
    [member_id]
)

# Same for hourly_limit and in_meeting check (3 locations total)
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_proactive_limits_per_member(tmp_db):
    """Daily limit is per-member, not global."""
    # Laura gets 5 nudges (max)
    for i in range(5):
        await tmp_db.execute("""
            INSERT INTO mem_cos_activity (actor, action_type, created_at)
            VALUES ('laura', 'proactive_nudge', datetime('now'))
        """)
    await tmp_db.commit()
    
    # James should still be able to get nudges
    from pib.proactive import check_daily_limit
    assert await check_daily_limit(tmp_db, 'james') == True
    assert await check_daily_limit(tmp_db, 'laura') == False
```

**Rollback:** `git checkout src/pib/proactive.py`  
**Validate:** `pytest tests/test_proactive.py::test_proactive_limits_per_member -v`

---

### 12. Fix ingest.py Meds/Sleep Dead Ends [P1]

**Files:** `src/pib/ingest.py` (stage handlers for meds/sleep prefix commands)  
**Time:** 45 minutes  
**Why:** "meds taken" and "sleep quality" messages are recognized but never write to pib_energy_states.

**Changes:**
```python
# ADD handler in ingest.py
async def handle_energy_state_update(db, event):
    """Terminal handler for meds/sleep/energy updates."""
    if "meds" in event.text.lower() or "took" in event.text.lower():
        # Parse: "took my meds" or "meds taken"
        await db.execute("""
            INSERT INTO pib_energy_states (member_id, state_type, value, recorded_at)
            VALUES (?, 'meds_taken', 1, ?)
        """, [event.member_id, datetime.now(ZoneInfo("America/New_York")).isoformat()])
        await db.commit()
        return {"action": "energy_state_recorded", "type": "meds_taken"}
    
    if "sleep" in event.text.lower():
        # Parse: "slept well" (5) vs "slept badly" (2)
        quality = extract_sleep_quality(event.text)  # 1-5 scale
        await db.execute("""
            INSERT INTO pib_energy_states (member_id, state_type, value, recorded_at)
            VALUES (?, 'sleep_quality', ?, ?)
        """, [event.member_id, quality, datetime.now(ZoneInfo("America/New_York")).isoformat()])
        await db.commit()
        return {"action": "energy_state_recorded", "type": "sleep_quality", "value": quality}
    
    return None
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_meds_taken_writes_to_energy_states(tmp_db):
    """Meds message writes to pib_energy_states."""
    event = {"id": "evt-1", "member_id": "laura", "text": "I took my meds", "channel": "imessage"}
    
    from pib.ingest import process_event
    await process_event(tmp_db, event)
    
    row = await tmp_db.execute_fetchone(
        "SELECT value FROM pib_energy_states WHERE member_id = 'laura' AND state_type = 'meds_taken'"
    )
    assert row['value'] == 1
```

**Rollback:** `git checkout src/pib/ingest.py`  
**Validate:** `pytest tests/test_ingest.py::test_meds_taken_writes_to_energy_states -v`

---

### 13. Fix comms.py Batch Window Seed Data [P1]

**Files:** `migrations/010_comms_batch_windows.sql` (new)  
**Time:** 15 minutes  
**Why:** Default batch windows collapse to "morning" — needs afternoon/evening rows.

**Changes:**
```sql
-- migrations/010_comms_batch_windows.sql
INSERT INTO pib_config (key, value) VALUES
    ('batch_window_morning_start', '07:00'),
    ('batch_window_morning_end', '11:59'),
    ('batch_window_afternoon_start', '12:00'),
    ('batch_window_afternoon_end', '17:59'),
    ('batch_window_evening_start', '18:00'),
    ('batch_window_evening_end', '21:59');
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_batch_windows_exist(tmp_db):
    """Batch window config rows exist."""
    morning = await tmp_db.execute_fetchone(
        "SELECT value FROM pib_config WHERE key = 'batch_window_morning_start'"
    )
    assert morning['value'] == '07:00'
    
    afternoon = await tmp_db.execute_fetchone(
        "SELECT value FROM pib_config WHERE key = 'batch_window_afternoon_start'"
    )
    assert afternoon['value'] == '12:00'
```

**Rollback:** `git rm migrations/010_comms_batch_windows.sql`  
**Validate:** `sqlite3 test.db "SELECT * FROM pib_config WHERE key LIKE 'batch_window%'"`

---

### 14. Fix proactive.py Focus Mode Guardrail [P1]

**Files:** `src/pib/proactive.py` (focus mode check), `src/pib/cli.py` (state-update command)  
**Time:** 30 minutes  
**Why:** Focus mode guardrail doesn't work — nothing writes focus_mode=1.

**Changes:**
```python
# cli.py: Add state-update command
def state_update(db_path: str, member_id: str, state_type: str, value: str) -> dict:
    """Update energy/focus state."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO pib_energy_states (member_id, state_type, value, recorded_at)
        VALUES (?, ?, ?, ?)
    """, [member_id, state_type, value, datetime.now(ZoneInfo("America/New_York")).isoformat()])
    conn.commit()
    conn.close()
    return {"ok": True, "state": state_type, "value": value}

# proactive.py: Check focus mode
async def should_send_nudge(db, member_id: str) -> bool:
    focus = await db.execute_fetchone(
        "SELECT value FROM pib_energy_states WHERE member_id = ? AND state_type = 'focus_mode' ORDER BY recorded_at DESC LIMIT 1",
        [member_id]
    )
    if focus and focus['value'] == 1:
        return False  # Focus mode active, don't nudge
    return True
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_focus_mode_blocks_nudges(tmp_db):
    """Focus mode=1 blocks proactive nudges."""
    await tmp_db.execute("""
        INSERT INTO pib_energy_states (member_id, state_type, value, recorded_at)
        VALUES ('laura', 'focus_mode', 1, datetime('now'))
    """)
    await tmp_db.commit()
    
    from pib.proactive import should_send_nudge
    assert await should_send_nudge(tmp_db, 'laura') == False
```

**Rollback:** `git checkout src/pib/proactive.py src/pib/cli.py`  
**Validate:** `pytest tests/test_proactive.py::test_focus_mode_blocks_nudges -v`

---

## P2: POLISH (quality improvements)

### 15. Add Child-Appropriate Reward Pool [P2]

**Files:** `src/pib/rewards.py` (reward pools)  
**Time:** 15 minutes  
**Why:** Charlie (5yo) should not see adult rewards.

**Changes:**
```python
# rewards.py: Add child_reward_pool
CHILD_REWARD_POOL = [
    "⭐ Great job!",
    "🎉 You did it!",
    "🚀 Awesome work!",
    "🌟 Super star!",
    "🎈 Way to go!",
]

def get_reward_message(member_id: str, task_title: str) -> str:
    member = get_member_profile(member_id)
    if member.get("age", 99) < 13:
        return random.choice(CHILD_REWARD_POOL)
    return random.choice(ADULT_REWARD_POOL)
```

**Regression Test:**
```python
def test_child_rewards():
    """Charlie gets child-appropriate rewards."""
    from pib.rewards import get_reward_message
    
    # Mock member profile
    with patch("pib.rewards.get_member_profile") as mock:
        mock.return_value = {"age": 5}
        reward = get_reward_message("charlie", "Clean room")
        assert reward in ["⭐ Great job!", "🎉 You did it!", "🚀 Awesome work!"]
```

**Rollback:** `git checkout src/pib/rewards.py`  
**Validate:** `pytest tests/test_rewards.py::test_child_rewards -v`

---

### 16. Fix custody.py Seed Data [P2]

**Files:** `src/pib/custody.py` (seed data)  
**Time:** 15 minutes  
**Why:** Seed data uses alternating_weeks but reality has midweek Thursday visits.

**Changes:**
```python
# BEFORE (custody.py seed data):
schedule_type = "alternating_weeks"

# AFTER:
schedule_type = "custom"
custom_pattern = {
    "week_a": ["Mon", "Tue", "Wed", "Thu_morning"],  # Laura has Thu morning drop-off
    "week_b": ["Thu_afternoon", "Fri", "Sat", "Sun"],  # Ex has Thu afternoon pickup
}
```

**Regression Test:**
```python
def test_custody_thursday_visits():
    """Custody seed data reflects midweek Thursday transitions."""
    from pib.custody import get_custody_schedule
    
    schedule = get_custody_schedule("charlie", "2026-03-06")  # Thursday
    assert "transition" in schedule
    assert schedule["primary"] in ["laura", "ex"]
```

**Rollback:** `git checkout src/pib/custody.py`  
**Validate:** `pytest tests/test_custody.py::test_custody_thursday_visits -v`

---

### 17. Add custody.py Holiday Override Error Handling [P2]

**Files:** `src/pib/custody.py` (holiday override JSON parse)  
**Time:** 10 minutes  
**Why:** JSON parse has no try/except, will crash on malformed holiday overrides.

**Changes:**
```python
# BEFORE:
overrides = json.loads(row["holiday_overrides"])

# AFTER:
try:
    overrides = json.loads(row["holiday_overrides"]) if row["holiday_overrides"] else {}
except json.JSONDecodeError:
    logger.warning(f"Malformed holiday_overrides for custody rule {row['id']}")
    overrides = {}
```

**Regression Test:**
```python
def test_custody_malformed_json():
    """Malformed holiday_overrides JSON doesn't crash."""
    # Insert custody rule with bad JSON
    conn.execute("""
        INSERT INTO ops_custody_rules (id, child_id, schedule_type, holiday_overrides)
        VALUES ('rule-1', 'charlie', 'alternating_weeks', 'NOT VALID JSON')
    """)
    conn.commit()
    
    from pib.custody import get_custody_schedule
    # Should not crash
    result = get_custody_schedule("charlie", "2026-12-25")
    assert result is not None
```

**Rollback:** `git checkout src/pib/custody.py`  
**Validate:** `pytest tests/test_custody.py::test_custody_malformed_json -v`

---

### 18. Fix memory.py Semantic Change Detection [P2]

**Files:** `src/pib/memory.py` (semantic change logic)  
**Time:** 20 minutes  
**Why:** Semantic changes treated as reinforcements — no negation token detection.

**Changes:**
```python
# ADD negation detection
NEGATION_TOKENS = {"not", "no", "never", "don't", "doesn't", "didn't", "won't", "can't", "isn't"}

def is_semantic_change(old_fact: str, new_fact: str) -> bool:
    """Detect if new_fact contradicts old_fact."""
    old_tokens = set(old_fact.lower().split())
    new_tokens = set(new_fact.lower().split())
    
    # Check for negation tokens in new but not old
    if NEGATION_TOKENS & new_tokens and not (NEGATION_TOKENS & old_tokens):
        return True  # Likely a contradiction
    
    # Check for opposite sentiment
    # (future: use LLM for semantic similarity check)
    return False
```

**Regression Test:**
```python
def test_semantic_change_detection():
    """Negation tokens trigger semantic change flag."""
    from pib.memory import is_semantic_change
    
    assert is_semantic_change("Laura likes coffee", "Laura doesn't like coffee") == True
    assert is_semantic_change("Laura likes coffee", "Laura loves coffee") == False
```

**Rollback:** `git checkout src/pib/memory.py`  
**Validate:** `pytest tests/test_memory.py::test_semantic_change_detection -v`

---

### 19. Fix memory.py Auto-Promotion LIKE Match [P2]

**Files:** `src/pib/memory.py` (auto-promotion logic)  
**Time:** 15 minutes  
**Why:** Uses first-30-char LIKE match, causes false positives on short facts.

**Changes:**
```python
# BEFORE:
existing = await db.execute_fetchone(
    "SELECT id FROM mem_long_term WHERE content LIKE ?", [fact[:30] + "%"]
)

# AFTER:
from difflib import SequenceMatcher

existing = await db.execute_fetchone(
    "SELECT id, content FROM mem_long_term WHERE member_id = ? AND category = ?",
    [member_id, category]
)

if existing:
    similarity = SequenceMatcher(None, fact, existing["content"]).ratio()
    if similarity > 0.85:  # 85% similarity = duplicate
        # Don't auto-promote, just increment reinforcement count
        return
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_auto_promotion_no_false_positives(tmp_db):
    """Auto-promotion doesn't trigger on short similar facts."""
    await tmp_db.execute("""
        INSERT INTO mem_long_term (id, member_id, content, category)
        VALUES ('fact-1', 'laura', 'Laura likes coffee', 'preferences')
    """)
    await tmp_db.commit()
    
    from pib.memory import auto_promote_memory
    result = await auto_promote_memory(tmp_db, 'laura', 'Laura likes tea', 'preferences')
    
    # Should create new fact, not reinforce old one
    assert result["action"] == "created"
```

**Rollback:** `git checkout src/pib/memory.py`  
**Validate:** `pytest tests/test_memory.py::test_auto_promotion_no_false_positives -v`

---

### 20. Fix ingest.py resolve_member Seed Data [P2]

**Files:** `src/pib/ingest.py` (resolve_member function)  
**Time:** 15 minutes  
**Why:** Seed data doesn't populate phone/imessage_handle fields.

**Changes:**
```python
# ADD to seed data or member profile config
MEMBER_IDENTIFIERS = {
    "laura": {
        "phone": "+15555551234",
        "imessage_handle": "laura@example.com",
        "signal": "+15555551234",
    },
    "james": {
        "phone": "+15555556789",
        "imessage_handle": "james@example.com",
        "signal": "+15555556789",
    },
}

def resolve_member(identifier: str) -> str:
    """Resolve phone/email/handle to member_id."""
    for member_id, ids in MEMBER_IDENTIFIERS.items():
        if identifier in ids.values():
            return member_id
    return "unknown"
```

**Regression Test:**
```python
def test_resolve_member_by_phone():
    """resolve_member maps phone to member_id."""
    from pib.ingest import resolve_member
    assert resolve_member("+15555551234") == "laura"
    assert resolve_member("laura@example.com") == "laura"
```

**Rollback:** `git checkout src/pib/ingest.py`  
**Validate:** `pytest tests/test_ingest.py::test_resolve_member_by_phone -v`

---

### 21. Add ingest.py LLM Failure Retry [P2]

**Files:** `src/pib/ingest.py` (stages 4-8)  
**Time:** 30 minutes  
**Why:** LLM failures silently swallowed into queue, nothing drains it.

**Changes:**
```python
# ADD retry logic
async def process_llm_queue(db):
    """Drain failed LLM requests with retry."""
    pending = await db.execute_fetchall(
        "SELECT * FROM mem_pending_llm_requests WHERE retry_count < 3 ORDER BY created_at LIMIT 10"
    )
    
    for req in pending:
        try:
            # Retry LLM call via OpenClaw
            result = await call_openclaw_agent(req["member_id"], req["text"])
            
            # Success: delete from queue
            await db.execute("DELETE FROM mem_pending_llm_requests WHERE id = ?", [req["id"]])
            await db.commit()
        except Exception as e:
            # Increment retry count
            await db.execute(
                "UPDATE mem_pending_llm_requests SET retry_count = retry_count + 1 WHERE id = ?",
                [req["id"]]
            )
            await db.commit()
            logger.error(f"LLM retry failed for {req['id']}: {e}")
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_llm_queue_drains(tmp_db):
    """Failed LLM requests retry up to 3 times."""
    await tmp_db.execute("""
        INSERT INTO mem_pending_llm_requests (id, member_id, text, retry_count)
        VALUES ('req-1', 'laura', 'test', 0)
    """)
    await tmp_db.commit()
    
    from pib.ingest import process_llm_queue
    await process_llm_queue(tmp_db)
    
    row = await tmp_db.execute_fetchone(
        "SELECT retry_count FROM mem_pending_llm_requests WHERE id = 'req-1'"
    )
    # After failure, retry_count incremented
    assert row is None or row["retry_count"] > 0
```

**Rollback:** `git checkout src/pib/ingest.py`  
**Validate:** `pytest tests/test_ingest.py::test_llm_queue_drains -v`

---

### 22. Fix voice.py Client Creation [P2]

**Files:** `src/pib/voice.py` (anthropic client)  
**Time:** 15 minutes  
**Why:** Creates own anthropic.AsyncAnthropic client, bypasses OpenClaw model routing.

**Changes:**
```python
# BEFORE:
import anthropic
client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# AFTER:
# Use OpenClaw agent session for model calls
# No direct client creation
```

**Regression Test:**
```python
def test_voice_no_direct_client():
    """voice.py doesn't create direct anthropic client."""
    with open("src/pib/voice.py") as f:
        content = f.read()
        assert "anthropic.AsyncAnthropic" not in content
```

**Rollback:** `git checkout src/pib/voice.py`  
**Validate:** `pytest tests/test_voice.py::test_voice_no_direct_client -v`

---

### 23. Add voice.py Privilege Filter [P2]

**Files:** `src/pib/voice.py` (corpus collection)  
**Time:** 20 minutes  
**Why:** Corpus stores full message text including privileged work content.

**Changes:**
```python
# ADD privilege filter
PRIVILEGED_DOMAINS = ["evolvefamilylawga.com", "evolve.law"]

async def add_to_corpus(db, member_id: str, message: str, metadata: dict):
    """Add message to voice learning corpus (filtered)."""
    # Check if message is from privileged calendar/email
    if any(domain in metadata.get("sender", "") for domain in PRIVILEGED_DOMAINS):
        return  # Don't store
    
    # Check if message contains privileged keywords
    if contains_privileged_content(message):
        return  # Don't store
    
    # Store for voice learning
    await db.execute("""
        INSERT INTO mem_voice_corpus (member_id, text, created_at)
        VALUES (?, ?, ?)
    """, [member_id, message, datetime.now(ZoneInfo("America/New_York")).isoformat()])
    await db.commit()
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_voice_corpus_privilege_filter(tmp_db):
    """Privileged work content not stored in corpus."""
    from pib.voice import add_to_corpus
    
    # Work email
    await add_to_corpus(tmp_db, "laura", "Client meeting prep", {"sender": "laura@evolvefamilylawga.com"})
    
    row = await tmp_db.execute_fetchone(
        "SELECT text FROM mem_voice_corpus WHERE text LIKE '%Client meeting%'"
    )
    assert row is None  # Should NOT be stored
```

**Rollback:** `git checkout src/pib/voice.py`  
**Validate:** `pytest tests/test_voice.py::test_voice_corpus_privilege_filter -v`

---

### 24. Fix db.py WriteQueue Failure Handling [P2]

**Files:** `src/pib/db.py` (WriteQueue class)  
**Time:** 30 minutes  
**Why:** Failed items are lost — no retry or dead-letter queue.

**Changes:**
```python
# ADD retry + dead-letter queue
class WriteQueue:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.queue = []
        self.dead_letter = []
    
    async def flush(self):
        """Flush queue with retry logic."""
        while self.queue:
            item = self.queue.pop(0)
            try:
                await self.execute(item["sql"], item["params"])
            except Exception as e:
                item["retry_count"] = item.get("retry_count", 0) + 1
                if item["retry_count"] < 3:
                    self.queue.append(item)  # Retry
                else:
                    self.dead_letter.append(item)  # Dead-letter
                    logger.error(f"WriteQueue dead-letter: {item['sql']} ({e})")
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_writequeue_retry(tmp_db):
    """WriteQueue retries failed writes."""
    from pib.db import WriteQueue
    
    wq = WriteQueue("test.db")
    wq.queue.append({"sql": "INSERT INTO nonexistent (id) VALUES (?)", "params": ["1"]})
    
    await wq.flush()
    
    # After 3 retries, should move to dead-letter
    assert len(wq.dead_letter) == 1
```

**Rollback:** `git checkout src/pib/db.py`  
**Validate:** `pytest tests/test_db.py::test_writequeue_retry -v`

---

### 25. Fix db.py Backup Path [P2]

**Files:** `src/pib/db.py` (backup function)  
**Time:** 10 minutes  
**Why:** Hardcoded to /opt/pib/data/backups — needs OpenClaw workspace path.

**Changes:**
```python
# BEFORE:
BACKUP_DIR = "/opt/pib/data/backups"

# AFTER:
import os
BACKUP_DIR = os.environ.get("PIB_BACKUP_DIR", "/data/.openclaw/workspace-dev/backups")
```

**Regression Test:**
```python
def test_backup_path_respects_env():
    """Backup path uses PIB_BACKUP_DIR env var."""
    import os
    os.environ["PIB_BACKUP_DIR"] = "/tmp/test-backups"
    
    from pib.db import BACKUP_DIR
    assert BACKUP_DIR == "/tmp/test-backups"
```

**Rollback:** `git checkout src/pib/db.py`  
**Validate:** `pytest tests/test_db.py::test_backup_path_respects_env -v`

---

### 26. Migrate to ULIDs [P2]

**Files:** `src/pib/db.py` (ID generation)  
**Time:** 30 minutes  
**Why:** Uses sequential prefixed IDs, not ULIDs (doc drift from CLAUDE.md).

**Changes:**
```python
# BEFORE:
def generate_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time())}"

# AFTER:
import ulid
def generate_id(prefix: str) -> str:
    return f"{prefix}-{ulid.new()}"

# Add to pyproject.toml:
"python-ulid>=1.1.0",
```

**Regression Test:**
```python
def test_id_generation_uses_ulid():
    """IDs use ULID format."""
    from pib.db import generate_id
    
    task_id = generate_id("task")
    assert task_id.startswith("task-")
    assert len(task_id.split("-")[1]) == 26  # ULID length
```

**Rollback:** `git checkout src/pib/db.py`, remove ulid from pyproject.toml  
**Validate:** `pytest tests/test_db.py::test_id_generation_uses_ulid -v`

---

### 27. Fix comms.py Timezone Consistency [P2]

**Files:** `src/pib/comms.py` (responded_at)  
**Time:** 10 minutes  
**Why:** responded_at uses utcnow() but batch windows use local time.

**Changes:**
```python
# BEFORE:
responded_at = datetime.utcnow().isoformat()

# AFTER:
responded_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
```

**Regression Test:**
```python
def test_responded_at_uses_local_time():
    """responded_at timestamp uses America/New_York."""
    from pib.comms import create_response
    
    response = create_response("test")
    assert "responded_at" in response
    # Check timestamp has timezone info
    assert "T" in response["responded_at"]
```

**Rollback:** `git checkout src/pib/comms.py`  
**Validate:** `pytest tests/test_comms.py::test_responded_at_uses_local_time -v`

---

### 28. Add FTS5 Index for Comms [P2]

**Files:** `migrations/011_comms_fts5.sql` (new)  
**Time:** 15 minutes  
**Why:** Search uses LIKE not FTS5 for comms table.

**Changes:**
```sql
-- migrations/011_comms_fts5.sql
CREATE VIRTUAL TABLE IF NOT EXISTS comms_fts USING fts5(
    text,
    sender,
    content='ops_comms',
    content_rowid='rowid'
);

-- Triggers (same pattern as tasks/items)
CREATE TRIGGER comms_fts_insert AFTER INSERT ON ops_comms BEGIN
    INSERT INTO comms_fts(rowid, text, sender)
    VALUES (NEW.rowid, NEW.text, NEW.sender);
END;

-- UPDATE, DELETE triggers
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_comms_fts5_search(tmp_db):
    """Comms search uses FTS5."""
    await tmp_db.execute("""
        INSERT INTO ops_comms (id, member_id, text, sender, created_at)
        VALUES ('msg-1', 'laura', 'Buy groceries', '+15555551234', datetime('now'))
    """)
    await tmp_db.commit()
    
    row = await tmp_db.execute_fetchone(
        "SELECT text FROM comms_fts WHERE comms_fts MATCH 'groceries'"
    )
    assert row['text'] == 'Buy groceries'
```

**Rollback:** `git rm migrations/011_comms_fts5.sql`  
**Validate:** `sqlite3 test.db "SELECT * FROM comms_fts WHERE comms_fts MATCH 'test'"`

---

### 29. Fix engine.py Calendar Time Parsing [P2]

**Files:** `src/pib/engine.py` (calendar time parsing)  
**Time:** 15 minutes  
**Why:** Silently skips malformed times.

**Changes:**
```python
# ADD error handling
def parse_calendar_time(time_str: str) -> datetime:
    """Parse calendar time with error handling."""
    try:
        return datetime.fromisoformat(time_str)
    except ValueError:
        logger.warning(f"Malformed calendar time: {time_str}")
        return None  # Return None instead of crashing
```

**Regression Test:**
```python
def test_calendar_time_parsing_handles_malformed():
    """parse_calendar_time handles malformed input."""
    from pib.engine import parse_calendar_time
    
    assert parse_calendar_time("2026-03-03T10:00:00") is not None
    assert parse_calendar_time("NOT A TIME") is None
```

**Rollback:** `git checkout src/pib/engine.py`  
**Validate:** `pytest tests/test_engine.py::test_calendar_time_parsing_handles_malformed -v`

---

### 30. Fix engine.py Effort Field Defaults [P2]

**Files:** `src/pib/engine.py` (task effort defaults)  
**Time:** 10 minutes  
**Why:** Missing effort field defaults to medium, bypasses energy filter.

**Changes:**
```python
# BEFORE:
effort = task.get("effort", "medium")

# AFTER:
effort = task.get("effort")
if effort is None:
    # Don't default — require explicit effort for energy-aware routing
    logger.warning(f"Task {task['id']} missing effort field")
    effort = "unknown"
```

**Regression Test:**
```python
@pytest.mark.asyncio
async def test_missing_effort_field_flagged(tmp_db):
    """Tasks with missing effort field are flagged."""
    await tmp_db.execute("""
        INSERT INTO ops_tasks (id, title, assignee, domain)
        VALUES ('task-1', 'Test', 'laura', 'household')
    """)
    await tmp_db.commit()
    
    from pib.engine import get_next_task
    result = await get_next_task(tmp_db, 'laura')
    
    # Should warn about missing effort
    # (check logs or return value)
```

**Rollback:** `git checkout src/pib/engine.py`  
**Validate:** `pytest tests/test_engine.py::test_missing_effort_field_flagged -v`

---

### 31. Update bootstrap.sh [P2]

**Files:** `bootstrap.sh`  
**Time:** 15 minutes  
**Why:** Stale — targets /opt/pib, uses uvicorn, wrong model.

**Changes:**
```bash
# BEFORE:
DB_PATH="/opt/pib/data/pib.db"
uvicorn pib.api:app --host 0.0.0.0 --port 8000

# AFTER:
DB_PATH="${PIB_DB_PATH:-/data/.openclaw/workspace-dev/pib.db}"
# No uvicorn — OpenClaw handles HTTP if needed
# Models configured in OpenClaw openclaw.json
```

**Regression Test:**
```bash
# Smoke test
bash bootstrap.sh --dry-run
# Should not reference /opt/pib or uvicorn
```

**Rollback:** `git checkout bootstrap.sh`  
**Validate:** `bash bootstrap.sh --dry-run`

---

### 32. Update readiness.py Credential Checks [P2]

**Files:** `src/pib/readiness.py`  
**Time:** 15 minutes  
**Why:** Checks wrong credentials (GOOGLE_SA_KEY_PATH) for OpenClaw mode.

**Changes:**
```python
# ADD OpenClaw mode detection
def check_credentials():
    """Check credentials based on runtime mode."""
    mode = os.environ.get("PIB_RUNTIME_MODE", "standalone")
    
    if mode == "openclaw":
        # Check OpenClaw credentials
        required = ["ANTHROPIC_API_KEY"]
        # Google Calendar via OpenClaw integration, not SA key
    else:
        # Standalone mode
        required = ["GOOGLE_SA_KEY_PATH", "ANTHROPIC_API_KEY"]
    
    for key in required:
        if key not in os.environ:
            return False, f"Missing credential: {key}"
    return True, "OK"
```

**Regression Test:**
```python
def test_readiness_openclaw_mode():
    """Readiness check adapts to OpenClaw mode."""
    import os
    os.environ["PIB_RUNTIME_MODE"] = "openclaw"
    os.environ["ANTHROPIC_API_KEY"] = "test"
    
    from pib.readiness import check_credentials
    ok, msg = check_credentials()
    assert ok == True
```

**Rollback:** `git checkout src/pib/readiness.py`  
**Validate:** `pytest tests/test_readiness.py::test_readiness_openclaw_mode -v`

---

### 33. Update openclaw-integration.md [P2]

**Files:** `docs/openclaw-integration.md`  
**Time:** 30 minutes  
**Why:** 5 modules + 2 migrations missing, line counts stale.

**Changes:**
- Add sections for: cli.py, webhook.py (if created)
- Add migration docs: 007_fts5_triggers, 008_comms_james_schema, 009_comms_laura_schema, 010_comms_batch_windows, 011_comms_fts5
- Update line counts for all modules
- Add architecture diagram for 3-machine topology

**Regression Test:**
```bash
# Check all modules documented
grep -E "cli.py|webhook.py" docs/openclaw-integration.md
# Should return results

# Check migrations documented
grep "007_fts5_triggers" docs/openclaw-integration.md
```

**Rollback:** `git checkout docs/openclaw-integration.md`  
**Validate:** Manual doc review

---

## FINAL VALIDATION CHECKLIST

After all fixes complete:

- [ ] **Full test suite:** `pytest tests/ -v --tb=short` (all pass)
- [ ] **CLI smoke test:** `python -m pib.cli bootstrap test.db` (returns `{"ok": true}`)
- [ ] **Agent permissions:** CoS blocked from migrate, Coach blocked from task-create
- [ ] **Rate limits:** 4th write in 60s blocked
- [ ] **Privacy canary:** Privileged calendar titles never leak in CoS output
- [ ] **Webhook endpoint:** Accepts POST with API key auth
- [ ] **Comms DBs:** comms_james.db and comms_laura.db exist with schema
- [ ] **FTS5 triggers:** 9 triggers fire on INSERT/UPDATE/DELETE
- [ ] **Timezone:** All datetime.now() use America/New_York
- [ ] **Monthly spawn:** Works on Jan 31, Mar 31, May 31, Aug 31, Oct 31, Dec 31
- [ ] **Undo:** Reads restore_data column correctly
- [ ] **No REPLACED imports:** ingest.py doesn't import llm.py
- [ ] **Docs updated:** openclaw-integration.md reflects all changes
- [ ] **Bootstrap ready:** All P0 tasks complete

---

## TOTAL TIME ESTIMATE

| Priority | Tasks | Estimated Time |
|----------|-------|----------------|
| P0 (Blockers) | 6 tasks | 7-12 hours |
| P1 (Critical) | 8 tasks | 4-6 hours |
| P2 (Polish) | 19 tasks | 4-6 hours |
| **TOTAL** | **33 tasks** | **15-24 hours** |

Realistic delivery: **12-16 hours** of focused Claude Code work, split across 2-3 sessions.

---

*Generated by OpenClaw subagent | c40v-final-refactor-prompt | 2026-03-03 08:19 EST*
