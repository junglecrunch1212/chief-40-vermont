# Data Layer Review — PIB v5

**Date:** 2026-03-05  
**Reviewer:** Subagent (review-data-layer)  
**Scope:** Migrations 001–016, engine.py, rewards.py, custody.py, memory.py, ingest.py, seed_data.py

---

## 1. Schema Integrity

### Migration Numbering
✅ No conflicting numbers. All 16 files have unique prefixes (001–016).

⚠️ **Comment/version mismatch in 009**: File is named `009_project_schema.sql` but the comment says "Migration 007: Project Domain". Cosmetic only — no runtime impact.

⚠️ **015_member_settings.sql** inserts `meta_schema_version` with `version = 2`, which collides with the conceptual "migration 002" (002_add_energy_states.sql). The `meta_schema_version` table has no uniqueness constraint on `version`, so this won't error but creates confusing version history.

### Foreign Keys
✅ All FKs in 001 reference tables defined earlier in the same file or within the same migration.

⚠️ **Forward references in ops_tasks**: `item_ref REFERENCES ops_items(id)`, `recurring_ref REFERENCES ops_recurring(id)`, `goal_ref REFERENCES ops_goals(id)` — ops_tasks is created BEFORE ops_items, ops_recurring, and ops_goals in migration 001. SQLite with `CREATE TABLE IF NOT EXISTS` won't enforce FK ordering at creation time, and FK enforcement only matters at INSERT/UPDATE with `PRAGMA foreign_keys = ON`. **Risk: if foreign_keys pragma is ON, inserts will fail unless tables exist.** The tables DO all exist in 001, just defined after ops_tasks. This is fine for SQLite but fragile.

⚠️ **016 pib_sensor_readings duplicates 005**: Migration 005 already creates `pib_sensor_readings` (with FK to `pib_sensor_config`). Migration 016 creates `pib_sensor_readings` again with a DIFFERENT schema (no FK to pib_sensor_config, different columns like `classification`, no `ttl_minutes`, no `expires_at`). Because of `IF NOT EXISTS`, **whichever runs first wins**. If 005 runs first (it should), 016 is silently a no-op, and its indexes reference columns that don't exist in the 005 schema (`classification`). **🔴 BUG: Schema conflict between 005 and 016.**

### Indexes
✅ Good coverage:
- `ops_tasks`: 3 partial indexes on status/assignee, due_date, overdue
- `ops_comms`: date, pending, inbox, batch, drafts, extraction
- `cal_classified_events`: event_date, scheduling_impact
- `fin_transactions`: date, category, needs_review
- `common_audit_log`: ts, entity

⚠️ **Missing index on ops_recurring(next_due)** — recurring spawn queries will scan the full table. Low volume now but worth adding.

⚠️ **Missing index on ops_tasks(recurring_ref)** — per AGENTS.md, the canonical read pattern is `WHERE recurring_ref IS NOT NULL AND status = 'next'`.

### FTS5 Tables
✅ All 5 FTS5 tables have proper content-sync triggers:
- `ops_tasks_fts` (007) — matches ops_tasks columns
- `ops_items_fts` (007) — matches ops_items columns  
- `mem_long_term_fts` (001+007) — matches mem_long_term columns
- `cap_captures_fts` (006) — matches cap_captures columns
- `comms_fts` (011) — matches ops_comms columns
- `proj_research_fts` (009) — matches proj_research columns

⚠️ **mem_long_term_fts trigger uses `NEW.id` as rowid** (in 007), while the FTS5 table declares `content_rowid='id'`. This works because `id` IS the INTEGER PRIMARY KEY (aliased to rowid). Correct but non-obvious.

---

## 2. Determinism

### whatNow() — ✅ DETERMINISTIC
- `what_now()` is a pure function of `(member_id, DBSnapshot)`
- No LLM calls, no network calls, no random, no side effects
- No `datetime.now()` inside — uses `snapshot.now`
- Energy computation receives `now` as parameter
- Task scoring uses a deterministic tuple sort (no random tiebreaking)
- `DBSnapshot.now` defaults to `now_et()` but is overridable for testing

### load_snapshot() — ⚠️ NOT DETERMINISTIC (by design)
- **🔴 Uses `date.today()` directly** (line 399) instead of receiving time as a parameter
- This means the snapshot loader is wall-clock dependent — fine for production but makes testing harder
- Should accept an optional `as_of: date = None` parameter

### compute_energy_level() — ⚠️ MOSTLY DETERMINISTIC
- Accepts `now` as optional param — good
- Falls back to `now_et()` if not provided (line ~128) — means callers must pass it explicitly for determinism
- All other logic is pure

### compute_complexity_score() — ✅ FULLY DETERMINISTIC
- Pure function of `state` dict, no side effects, no time dependency

---

## 3. SSOT Consistency

### Tasks
✅ **ops_tasks is the single SSOT for task instances.** Clear separation:
- `ops_recurring` = schedule templates (what to spawn)
- `ops_tasks` = actual instances (with `recurring_ref` FK back)
- Per AGENTS.md: read `ops_tasks WHERE recurring_ref IS NOT NULL` for recurring instances

### Calendar
✅ Clean pipeline: `cal_sources` → `cal_raw_events` → `cal_classified_events` → `cal_daily_states`
- Raw events have dedup via `UNIQUE(source_id, google_event_id)`
- Classified events link back via `raw_event_id`
- Dedup group support via `dedup_group_id`

### Financial
✅ `fin_transactions` is local SSOT. `import_source` / `import_batch` / `external_id UNIQUE` indicate read-from-external-source pattern. Budget snapshots are precomputed caches.

### Memory
✅ Two-tier: `mem_session_facts` (ephemeral, 72hr TTL) → `mem_long_term` (permanent). Auto-promotion pipeline in `memory.py`. Supersession chain via `superseded_by` FK.

---

## 4. State Machine

### Transitions — ✅ WELL-DEFINED
```
inbox → next, in_progress, waiting_on, deferred, dismissed
next → in_progress, done, waiting_on, deferred, dismissed
in_progress → done, waiting_on, deferred
waiting_on → in_progress, next, done
deferred → next, inbox
done → (terminal)
dismissed → (terminal)
```

### Guards — ✅ ENFORCED
- `dismissed` requires 10+ character notes (friction = intentional)
- `deferred` requires `scheduled_date`
- `waiting_on` requires `waiting_on` field
- `done` always allowed (one-tap completion — ADHD-friendly)

### Audit Trail — ⚠️ PARTIAL
- `common_audit_log` table exists with full structure
- `common_undo_log` exists for reversibility
- **But `transition_task()` does NOT write to audit_log.** It just updates ops_tasks directly. The audit trail infrastructure is there but not wired into the state machine.
- `complete_task_with_reward()` in rewards.py properly delegates to `transition_task()` — good.

### Column Whitelist — ✅ GOOD
- `ALLOWED_UPDATE_COLUMNS` prevents SQL injection via dynamic column names in `transition_task()`

---

## 5. Seed Data Alignment

### Members — ✅ ALIGNED
- `m-james`, `m-laura`, `m-charlie`, `m-baby` — all columns exist in schema
- `m-laura-ex` as coparent — correct role
- `capabilities` field is JSON string — matches TEXT column

### Calendar Sources — ✅ ALIGNED  
- 4 sources with `classification_id` referencing `common_source_classifications`
- Source classifications seeded first, then calendar sources — FK order correct
- Placeholder google_calendar_ids — correct for template

### Custody Config — ✅ ALIGNED
- All seeded columns exist in `common_custody_configs`
- `anchor_parent = m-james`, `other_parent = m-laura-ex` — both seeded as members

### Config — ✅ ALIGNED
- All PIB_CONFIG entries use (key, value, description) matching `pib_config` schema

⚠️ **Duplicate config seeds**: Migration 003 and 010 both seed `comms_batch_*` keys. Using `INSERT OR IGNORE` so no error, but 003 seeds `evening_end = 20:00` while 010 seeds `evening_end = 19:00`. **Whichever runs first wins.** Since 003 runs before 010, the evening window is 19:00–20:00 (from 003), and 010's 18:00–19:00 values are silently ignored. **🔴 Inconsistent intent.**

---

## 6. Idempotency

### Ingestion — ✅ ROBUST
- `common_idempotency_keys` table with `key_hash` PK
- `is_duplicate()` check is first stage of pipeline
- `record_idempotency()` writes before processing
- SHA256 keys from `(source, identifier)`

### Calendar Sync — ✅ DEDUP VIA UNIQUE CONSTRAINT
- `cal_raw_events` has `UNIQUE(source_id, google_event_id)` — natural dedup

### Recurring Spawn — ⚠️ NOT VISIBLE IN REVIEWED CODE
- `ops_recurring.last_spawned` field exists for tracking
- No spawn function was found in the reviewed Python files — likely in `scripts/core/` (JS) or not yet implemented
- **Risk: if spawn logic doesn't check `last_spawned`, duplicates are possible**

### Memory — ✅ DEDUP VIA CONTENT SIMILARITY
- `save_memory_deduped()` checks overlap ratio before inserting
- Reinforces on high overlap (>60%), supersedes on negation/value-change
- Scoped per-member — prevents cross-member interference

### Sensor Readings — ✅ (in migration 005)
- `idempotency_key` with UNIQUE index
- `expires_at` for TTL-based cleanup

---

## 7. Additional Findings

### 🔴 Critical: Dual pib_sensor_readings schemas (005 vs 016)
Migration 005 creates a full sensor readings table with FK to pib_sensor_config, TTL, expiry. Migration 016 creates a simpler version with `classification` column and no FK. Only one can exist. The indexes in 016 reference columns (`classification`) not in the 005 schema.

**Fix:** Remove 016 or merge its additions (classification, member-scoped indexes) into 005 as ALTER TABLE statements.

### ⚠️ `date.today()` in rewards.py and load_snapshot()
- `complete_task_with_reward()` calls `date.today()` for streak updates
- `load_snapshot()` uses `date.today()` for calendar queries
- Both should accept an optional date parameter for testability

### ⚠️ `random.random()` in rewards.py
- `select_reward()` uses `random.random()` — intentionally non-deterministic (variable-ratio reinforcement schedule)
- This is correct for production but should accept an optional `rng` parameter for testing

### ⚠️ Audit log not wired
- The `common_audit_log` and `common_undo_log` tables are well-designed but no Python code writes to them
- `transition_task()` should log state changes to audit_log
- `complete_task_with_reward()` should create undo_log entries

### ✅ Privacy Architecture
- Per-member comms databases (008) — good isolation
- Laura's calendar marked `privacy: 'redacted'` in source classifications
- Sensor readings have `classification` for privacy fencing (in 016 schema)

---

## Summary

| Area | Status | Issues |
|------|--------|--------|
| Migration numbering | ✅ | Version comments mismatched but no conflicts |
| Foreign keys | ⚠️ | Forward refs in 001 (works but fragile) |
| Schema conflicts | 🔴 | **005 vs 016: dual pib_sensor_readings** |
| Indexes | ✅ | Missing 2 useful ones (recurring, tasks.recurring_ref) |
| FTS5 | ✅ | All synced with triggers |
| whatNow() determinism | ✅ | Pure function, no side effects |
| load_snapshot() | ⚠️ | Uses date.today() — not testable |
| State machine | ✅ | Transitions + guards enforced |
| Audit trail | ⚠️ | Tables exist, not wired to state machine |
| SSOT | ✅ | Clean separation across all domains |
| Seed data | ⚠️ | Duplicate comms batch config (003 vs 010) |
| Idempotency | ✅ | Robust across ingestion, calendar, memory |
| Recurring spawn | ⚠️ | Not found in Python — may be JS-only or unimplemented |

### Priority Fixes
1. **🔴 Resolve 005 vs 016 sensor_readings conflict** — merge or remove 016
2. **⚠️ Wire audit_log into transition_task()** — the table is there, use it
3. **⚠️ Add `as_of` parameter to load_snapshot()** — testability
4. **⚠️ Reconcile comms batch config** between 003 and 010
5. **⚠️ Add indexes** on `ops_recurring(next_due)` and `ops_tasks(recurring_ref)`
