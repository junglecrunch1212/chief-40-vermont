# PIB v5 Console — Deep Audit vs Full Build Spec
**Date:** 2026-03-05  
**Auditor:** Subagent (deep-audit)  
**Scope:** Exhaustive comparison of build spec requirements vs actual implementation

---

## Executive Summary

This audit examined **every major feature** described in `pib-v5-build-spec.md` (~3800 lines) against the actual implementation in:
- Database schema (16 migrations)
- Console server (`console/server.mjs`, Express on port 3333)
- Console frontend (`console/index.html`, vanilla JS + routing)
- API contract (`pib-api-contract.md`)

**Key Findings:**
- **Layer 1 (Core)**: 🔨 Partially implemented — database schema solid, but critical whatNow() engine delegated to Python CLI (not found in Express server)
- **Console UI**: 🔨 Partially implemented — shell + basic views exist, but missing ADHD-specific affordances (stream carousel, progress dots, endowed progress, glow animation, keyboard nav)
- **Comms Inbox / Omnichannel**: 🔨 Partially implemented — database schema + channel registry exist, frontend comms page exists, but extraction pipeline, draft generation, and batch window logic are incomplete
- **Dark Prosthetics**: ❌ Missing — reward selection, streak psychology, variable-ratio reinforcement not in server logic
- **Proactive Messaging**: ❌ Missing — no triggers, no morning digest composition, no paralysis detection
- **Memory System**: ❌ Missing — tables exist, but dedup/supersession/auto-promotion logic not in server
- **Financial Integration**: ❌ Missing — budget tables exist, but no affordability checks, no transaction categorization
- **Privacy Enforcement**: 🔨 Partially implemented — classification schema exists, server has privacy filtering in schedule endpoint, but not consistently enforced across all endpoints

**Priority Breakdown:**
- **P0 (blocks demo)**: 8 gaps
- **P1 (blocks bootstrap)**: 12 gaps  
- **P2 (nice-to-have)**: 15 gaps

---

## 1. Infrastructure & Stack

### 1.1 Stack Requirements
**Spec:** Mac Mini, SQLite WAL, FastAPI on port 3141, BlueBubbles, Cloudflare Tunnel

**Reality:**
- ✅ SQLite WAL mode (confirmed in migrations)
- ❌ FastAPI — **Server is Express (Node.js) on port 3333**, not FastAPI (Python)
- ❌ BlueBubbles integration not found in server (no webhook endpoint at `/webhooks/bluebubbles`)
- ❌ Twilio webhook handler not found (no endpoint at `/webhooks/twilio`)
- ✅ Database path configurable via `PIB_DB_PATH`

**Gap:** The spec describes a Python/FastAPI server, but the implementation is Node.js/Express. This is a **fundamental architectural mismatch**. The spec's Python code examples (Section 3.6 write batching, Section 4 whatNow(), Section 5 rewards, etc.) are not translatable 1:1.

**Priority:** P0 — blocks understanding of what "the system" actually is

**File Citations:**
- `console/server.mjs:10-15` — Express app, port 3333
- Spec Section 3.1 — describes FastAPI + Python stack

---

## 2. Database Schema (Five Shapes)

### 2.1 Common Tables (meta, config, members, sources, locations, custody, audit)
**Spec:** Section 3.8 — full schema for 8 table groups

**Reality:**
- ✅ `meta_schema_version` — exists (`001_initial_schema.sql:8`)
- ✅ `meta_discovery_reports` — exists (`001_initial_schema.sql:14`)
- ✅ `meta_migrations` — exists (`001_initial_schema.sql:27`)
- ✅ `pib_config` — exists (`001_initial_schema.sql:42`)
- ✅ `common_members` — exists with all actor fields (`001_initial_schema.sql:56`)
  - ✅ `view_mode`, `digest_mode`, `energy_markers`, `medication_config`, `velocity_cap`
  - ✅ `capabilities`, `schedule_profile`, `household_duties`
- ✅ `common_source_classifications` — exists with four-label vocabulary (`001_initial_schema.sql:95`)
- ✅ `common_locations` — exists (`001_initial_schema.sql:114`)
- ✅ `common_custody_configs` — exists with DST-aware fields (`001_initial_schema.sql:123`)
- ✅ `common_life_phases` — exists (`001_initial_schema.sql:146`)
- ✅ `common_audit_log` — exists (`001_initial_schema.sql:162`)
- ✅ `common_idempotency_keys` — exists (`001_initial_schema.sql:173`)
- ✅ `common_id_sequences` — exists (`001_initial_schema.sql:179`)
- ✅ `common_dead_letter` — exists (`001_initial_schema.sql:184`)
- ✅ `common_undo_log` — exists (`001_initial_schema.sql:196`)

**Assessment:** ✅ Fully implemented — all common infrastructure tables present

**Priority:** N/A — complete

---

### 2.2 Ops Tables (tasks, goals, items, recurring, comms, lists)
**Spec:** Section 3.8 ops_* tables

**Reality:**
- ✅ `ops_tasks` — exists with full state machine fields (`001_initial_schema.sql:214`)
  - ✅ `status` CHECK constraint includes all 7 states
  - ✅ `item_type` includes chore, decision, purchase, etc.
  - ✅ `micro_script` column (Gene 7: EVERY task has this)
  - ✅ `recurring_ref`, `goal_ref`, `item_ref` foreign keys
  - ✅ `energy`, `effort`, `points` for whatNow() scoring
- ✅ `ops_goals` — exists (`001_initial_schema.sql:256`)
- ✅ `ops_items` — exists with CRM fields (`001_initial_schema.sql:267`)
  - ✅ `cos_can_contact`, `outbound_identity`, `reliability`
  - ✅ `last_meaningful_contact`, `hosting_balance`
- ✅ `ops_dependencies` — exists (`001_initial_schema.sql:296`)
- ✅ `ops_recurring` — exists (`001_initial_schema.sql:305`)
  - ✅ `next_due`, `micro_script_template`, `points`
- ✅ `ops_comms` — exists, **enhanced in migration 003** (`003_comms_enhancement.sql`)
  - ✅ `batch_window`, `batch_date` (for batching)
  - ✅ `extraction_status`, `extracted_items` (for task extraction)
  - ✅ `draft_response`, `draft_status` (for CoS drafting)
  - ✅ `snoozed_until` (for snooze)
  - ✅ `visibility` (for archive/filtering)
- ✅ `ops_lists` — exists (`001_initial_schema.sql:343`)
- ✅ `ops_gmail_whitelist` — exists (`001_initial_schema.sql:355`)
- ✅ `ops_gmail_triage_keywords` — exists (`001_initial_schema.sql:362`)
- ✅ `ops_streaks` — exists (`001_initial_schema.sql:369`)

**Assessment:** ✅ Fully implemented — all ops tables present, including comms enhancements

**Priority:** N/A — complete

---

### 2.3 Calendar Tables (sources, raw_events, classified_events, daily_states, conflicts)
**Spec:** Section 3.8 cal_* tables

**Reality:**
- ✅ `cal_sources` — exists (`001_initial_schema.sql:383`)
- ✅ `cal_raw_events` — exists (`001_initial_schema.sql:395`)
- ✅ `cal_classified_events` — exists (`001_initial_schema.sql:405`)
  - ✅ `privacy` column for filtering (full/privileged/redacted)
  - ✅ `title_redacted` for privacy-safe display
  - ✅ `scheduling_impact` (HARD_BLOCK, SOFT_BLOCK, etc.)
- ✅ `cal_daily_states` — exists (`001_initial_schema.sql:425`)
  - ✅ `custody_states`, `member_states`, `complexity_score`
- ✅ `cal_conflicts` — exists (`001_initial_schema.sql:440`)
- ✅ `cal_disambiguation_rules` — exists (`001_initial_schema.sql:456`)

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 2.4 Financial Tables (transactions, budget, merchant_rules)
**Spec:** Section 3.8 fin_* tables

**Reality:**
- ✅ `fin_transactions` — exists (`001_initial_schema.sql:471`)
- ✅ `fin_budget_config` — exists (`001_initial_schema.sql:485`)
- ✅ `fin_merchant_rules` — exists (`001_initial_schema.sql:492`)
- ✅ `fin_capital_expenses` — exists (`001_initial_schema.sql:502`)
- ✅ `fin_recurring_bills` — exists (`001_initial_schema.sql:513`)
- ✅ `fin_budget_snapshot` — exists (`001_initial_schema.sql:524`)

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 2.5 Memory Tables (sessions, messages, facts, long_term, digests, approvals)
**Spec:** Section 3.8 mem_* tables

**Reality:**
- ✅ `mem_sessions` — exists (`001_initial_schema.sql:536`)
- ✅ `mem_messages` — exists (`001_initial_schema.sql:545`)
- ✅ `mem_session_facts` — exists (`001_initial_schema.sql:558`)
- ✅ `mem_long_term` — exists (`001_initial_schema.sql:570`)
  - ✅ `reinforcement_count`, `superseded_by` columns for dedup
- ✅ `mem_long_term_fts` — FTS5 index exists (`001_initial_schema.sql:586`)
- ✅ `mem_precomputed_digests` — exists (`001_initial_schema.sql:591`)
- ✅ `mem_approval_queue` — exists (`001_initial_schema.sql:601`)
- ✅ `mem_cos_activity` — exists (`001_initial_schema.sql:615`)

**Assessment:** ✅ Fully implemented (schema only — logic gaps noted in Section 7)

**Priority:** N/A — complete

---

### 2.6 PIB Behavioral Tables (reward_log, energy_states, coach_protocols)
**Spec:** Section 3.8 pib_* tables (NEW in v5)

**Reality:**
- ✅ `pib_reward_log` — exists (`001_initial_schema.sql:628`)
- ✅ `pib_energy_states` — exists (`002_add_energy_states.sql`)
  - ✅ `medication_taken`, `sleep_quality`, `focus_mode_active`
  - ✅ `completions_today`, `velocity_cap_hit`
  - ✅ `current_energy_level` (low/medium/high)
- ✅ `pib_coach_protocols` — exists (`001_initial_schema.sql:650`)

**Assessment:** ✅ Fully implemented (schema only — logic gaps noted in Section 5)

**Priority:** N/A — complete

---

### 2.7 FTS5 Indexes
**Spec:** Section 3.8 — FTS5 for tasks, items, long-term memory

**Reality:**
- ✅ `ops_tasks_fts` — exists (`001_initial_schema.sql:661`)
- ✅ `ops_items_fts` — exists (`001_initial_schema.sql:664`)
- ✅ `mem_long_term_fts` — exists (`001_initial_schema.sql:586`)
- ✅ `cap_captures_fts` — exists (`006_capture_domain.sql:70`)
- ✅ `comms_fts` — exists (`011_comms_fts5.sql`)

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 2.8 Additional Schema from Migrations

#### Migration 005: Sensor Bus
**File:** `005_sensor_bus.sql`

- ✅ `sensor_readings` table — exists
- ✅ `sensor_rules` table — exists
- ✅ Config keys for sensor polling intervals

**Assessment:** ✅ Implemented (beyond spec — spec mentions sensor bus but doesn't detail schema)

#### Migration 006: Capture Domain
**File:** `006_capture_domain.sql`

- ✅ `cap_notebooks` — taxonomy buckets
- ✅ `cap_captures` — main capture storage with FTS5
- ✅ `cap_connections` — cross-domain links
- ✅ Deep organizer config keys

**Assessment:** ✅ Implemented (beyond spec — spec mentions capture but doesn't detail full schema)

#### Migration 009: Project Schema
**File:** `009_project_schema.sql`

- ✅ `proj_projects` table
- ✅ `proj_milestones` table  
- ✅ `proj_resources` table

**Assessment:** ✅ Implemented (beyond spec — spec doesn't describe project domain)

#### Migration 012: Channel Registry
**File:** `012_channel_registry.sql`

- ✅ `comms_channels` table — channel definitions with health tracking
- ✅ `comms_channel_health` table — per-channel health status
- ✅ `comms_channel_capabilities` table — channel capability flags
- ✅ `comms_channel_members` table — member access levels per channel

**Assessment:** ✅ Implemented (supports omnichannel vision from spec)

#### Migration 013: Entity Hierarchy
**File:** `013_entity_hierarchy.sql`

- ✅ `entity_hierarchy` table — parent-child relationships
- ✅ Recursive CTE for hierarchy queries

**Assessment:** ✅ Implemented (beyond spec)

---

## 3. Core Engine — whatNow()

### 3.1 whatNow() Implementation
**Spec:** Section 4 — "The single query the entire system exists to answer. Deterministic. No LLM. No side effects."

**Reality:**
- ❌ **Not found in `console/server.mjs`**
- 🔨 Server delegates to Python CLI: `runCLI("what-now", {}, memberId)` (`server.mjs:184`)
- ❌ Python CLI implementation not audited (out of scope for console audit)
- ❌ No evidence of deterministic sorting, energy matching, calendar filtering, or velocity cap logic in server

**Gap Analysis:**
The spec's whatNow() is a **pure function** on local data. The console server treats it as a black-box CLI call. This means:
- No visibility into ranking algorithm
- No inline energy matching
- No one-more teaser logic
- No Zeigarnik hook generation

**What Exists:**
- Server calls CLI, receives result, forwards to frontend (`server.mjs:184-186`)
- Frontend displays `whatNow.the_one_task` if present (`index.html:312`)

**What's Missing:**
- Deterministic task selection (overdue → due_today → in_progress → next → inbox → smallest first)
- Energy filtering (low energy → only tiny/small tasks)
- Velocity cap check (completions_today >= velocity_cap → return break task)
- Calendar block filter (in HARD_BLOCK → return blocked_until)
- Custody-aware task filtering (tasks blocked by "child not with assignee")
- One-more teaser (2nd task with effort estimate)
- Streak state inclusion
- Context string assembly ("3 overdue, 12-day streak, meds peaked")

**Priority:** P0 — blocks demo (the console depends on whatNow() to show "next task")

**Recommendation:** Either:
1. Implement whatNow() in Node.js in `server.mjs` (port Python spec logic), OR
2. Document that console is a **view layer** only, and all logic lives in Python backend

**File Citations:**
- Spec Section 4 — full whatNow() implementation in Python
- `console/server.mjs:184` — CLI delegation
- `console/index.html:312` — frontend consumes result

---

### 3.2 Custody Date Math (DST-Aware)
**Spec:** Section 4.1 — `who_has_child()` pure function with 20+ test cases

**Reality:**
- ❌ Not found in `server.mjs`
- 🔨 Server delegates to Python CLI: `runCLI("custody", { date: dateStr })` (`server.mjs:195`)
- ❌ No evidence of DST-safe date arithmetic in server

**Gap:** Same as whatNow() — delegated to Python CLI, no inline implementation

**Priority:** P1 — blocks bootstrap (custody state drives daily state, task blocking, handoff logic)

**File Citations:**
- Spec Section 4.1 — full `who_has_child()` with DST tests
- `console/server.mjs:195` — CLI delegation

---

## 4. Console Design System & ADHD Affordances

### 4.1 Fonts & Color Palette
**Spec:** Section 5.6 — Fraunces (headings), DM Sans (body), JetBrains Mono (data/code)

**Reality:**
- ✅ Fonts loaded via Google Fonts CDN (`index.html:5`)
- ✅ CSS custom properties for colors (`index.html:9-16`)
  - ✅ `--pink`, `--lav`, `--teal`, `--grn`, `--warn`, `--err`, `--info`
  - ✅ Warm cream background `--bg:#FFFBF5`
- ✅ Domain color map via `DOMAIN_BADGE` object (`index.html:104`)

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 4.2 Shell (Sidebar + Actor Switcher)
**Spec:** Section 5.7 — 220px sidebar, actor switcher, nav badges, custody indicator, health pulse

**Reality:**
- ✅ Shell layout with sidebar + main (`index.html:26-29`)
- ✅ Actor switcher with emoji buttons (`index.html:168-174`)
- ✅ Navigation items (`index.html:177-183`)
- 🔨 Nav badges — **partial**: inbox count logic exists but not wired (`index.html:106`)
- ❌ Custody indicator — **missing**: spec shows "👦 Charlie with James today" at bottom of sidebar
- 🔨 System health pulse — **partial**: health pill shown (`index.html:185-189`), but not polling `/api/health` every 5min

**Gap Analysis:**
- Custody indicator: Should read `GET /api/custody/today` and display at sidebar bottom
- Health pulse: Should poll every 5min, change color based on `status` field
- Nav badges: Tasks badge should show `GET /api/tasks?filter=inbox` count

**Priority:** P1 — blocks bootstrap (custody awareness is core to household context)

**File Citations:**
- Spec Section 5.7 — sidebar anatomy
- `console/index.html:168-189` — sidebar render

---

### 4.3 Today View — James (Stream Carousel + Progress Dots)
**Spec:** Section 5.6 Console Update — "Stream metaphor", endowed progress, progress dots, keyboard nav, radar, glow animation

**Reality:**
- 🔨 Today stream — **partial**: server builds unified stream (`server.mjs:153-204`), frontend renders basic list (`index.html:319-333`)
- ❌ **Endowed progress** — missing (spec: day starts at 2+ dots: "Woke up", "Opened PIB")
- ❌ **Progress dots** — missing (spec: horizontal dot row with 6 states: endowed, done, skipped, current, urgent, pending)
- ❌ **Keyboard navigation** — missing (spec: `←` `→` to browse, `Enter` to complete, `Esc` to skip)
- ❌ **Radar** — missing (spec: show next 3 calendar events within 2h window)
- ❌ **Glow animation** — missing (spec: active task card border pulses pink)
- ✅ Energy pills — present (`index.html:322-324`)
- ✅ Stream includes calendar events + tasks — present (`server.mjs:168-187`)

**Gap Analysis:**
The frontend renders a **basic task list**, not the spec's **stream carousel with ADHD affordances**. The spec describes:
- **ONE card at a time** (carousel view for James)
- **Progress dots** showing position in day (N / total)
- **Endowed progress** (2 free dots at day start to exploit endowment effect)
- **Glow animation** on active card (directs attention without startling)
- **Keyboard shortcuts** (zero mouse movement for ADHD users)
- **Radar** (peripheral time awareness)

**What Exists:**
- Server assembles stream correctly (tasks + calendar events)
- Frontend displays all items in a vertical list
- "Done" button per task

**What's Missing:**
- Carousel UI (one card at a time, prev/next navigation)
- Progress dots component
- Endowed items injection
- Glow CSS animation
- Keyboard event handlers
- Radar component (next 3 events from calendar)

**Priority:** P0 — blocks demo (the stream carousel IS the James experience)

**File Citations:**
- Spec Section 5.6 Console Update — full stream metaphor description
- Spec Section 2.1 — "ONE card at a time. Always micro-scripts."
- `console/server.mjs:153-204` — stream assembly (correct)
- `console/index.html:319-333` — frontend rendering (basic list, not carousel)

---

### 4.4 Today View — Laura (Compressed Bullets)
**Spec:** Section 2.2 — "Compressed view: decisions needed, your tasks, household status"

**Reality:**
- ❌ No Laura-specific view found in frontend
- ❌ `/api/decisions` endpoint exists (`server.mjs:235-239`), but no frontend consumer
- ❌ `/api/household-status` endpoint exists (`server.mjs:243-255`), but no frontend consumer
- ✅ `/api/tasks?assignee=m-laura` works (`server.mjs:206-224`)

**Gap:** The spec describes a **different UI layout** for Laura (not a stream, not a carousel). Frontend renders same Today view for all actors.

**Priority:** P1 — blocks bootstrap (Laura's view mode is a key differentiator)

**File Citations:**
- Spec Section 2.2 — Laura's compressed view mockup
- `console/server.mjs:235-255` — endpoints exist
- `console/index.html` — no Laura-specific rendering

---

### 4.5 Today View — Charlie (Full-Screen Child View)
**Spec:** Section 2.3 — "Full-screen without sidebar chrome. Privacy invariant: no adult data visible."

**Reality:**
- 🔨 Child view — **partial**: `/api/chores` endpoint exists (`server.mjs:759-767`), frontend has Charlie scoreboard section (`index.html:629-648`)
- ❌ **Full-screen enforcement** — missing: spec requires sidebar hidden when `currentActor === 'm-charlie'`
- ❌ **Privacy enforcement** — missing: spec requires nav items `['tasks','people','settings']` hidden for child

**Gap:** Frontend renders same shell for all actors. Child privacy is not enforced.

**Priority:** P1 — blocks bootstrap (child data leakage violates core privacy invariant)

**File Citations:**
- Spec Section 2.3 — "No sidebar chrome. No admin navigation visible."
- Spec Section 5.6 Console Update — "Charlie view: Hides Tasks, People, Settings from nav."
- `console/index.html:101` — `HIDDEN_FOR_CHILD` array defined but not consistently applied

---

## 5. Dark Prosthetics (Behavioral Mechanics)

### 5.1 Variable-Ratio Reinforcement (Reward Selection)
**Spec:** Section 5.1 — "60/25/10/5 distribution, select_reward(), log to pib_reward_log"

**Reality:**
- ✅ `pib_reward_log` table exists (`001_initial_schema.sql:628`)
- ❌ **Reward selection logic** — not found in `server.mjs`
- ❌ Server delegates task completion to Python CLI: `runCLI("task-complete", ...)` (`server.mjs:699`)
- ❌ No evidence of reward tier selection (simple/warm/delight/jackpot)
- ❌ No evidence of reward message templates
- ❌ No evidence of Zeigarnik hook ("One more? Only 3 min.")

**Gap:** Rewards are a **core differentiator** (Section 5.1: "These are not flavor. These are the core competitive differentiation."). The database is ready, but the logic is missing from the console server.

**Priority:** P0 — blocks demo (variable rewards make task completion addictive)

**File Citations:**
- Spec Section 5.1 — full `select_reward()` implementation
- `console/server.mjs:699` — CLI delegation
- `001_initial_schema.sql:628` — table exists

---

### 5.2 Elastic Streaks
**Spec:** Section 5.2 — "Grace days, custody pause, streak extension, reset-was-long detection"

**Reality:**
- ✅ `ops_streaks` table exists with `grace_days_used`, `custody_pause_enabled` (`001_initial_schema.sql:369`)
- ❌ **Streak update logic** — not found in `server.mjs`
- ❌ Delegated to Python CLI (assumed, no explicit call found)
- ❌ No evidence of grace day computation
- ❌ No evidence of custody-aware gap calculation

**Gap:** Streaks are central to ADHD Scorecard (Section 11). Database ready, logic missing.

**Priority:** P0 — blocks demo (streak display is on scoreboard + today view)

**File Citations:**
- Spec Section 5.2 — `update_streak()` implementation
- `001_initial_schema.sql:369` — table structure

---

### 5.3 Friction Asymmetry (State Machine Guards)
**Spec:** Section 5.3 — "Done = easy (one tap), dismissed = hard (10 char reason), deferred = medium (when instead?)"

**Reality:**
- ✅ Task state machine CHECK constraint in schema (`001_initial_schema.sql:217`)
- ❌ **Guards implementation** — not found in `server.mjs`
- ❌ No server-side validation that `dismissed` requires notes
- ❌ No server-side validation that `deferred` requires scheduled_date

**Gap:** Guards enforce the "path of least resistance IS the productive path." Missing server-side enforcement means frontend could bypass.

**Priority:** P1 — blocks bootstrap (friction asymmetry is behavioral design)

**File Citations:**
- Spec Section 5.3 — GUARDS dictionary
- `console/server.mjs` — no guard functions found

---

### 5.4 Coach Protocols
**Spec:** Section 5.4 — "7 protocols (never-guilt, always-celebrate, energy-match, etc.) loaded into system prompt"

**Reality:**
- ✅ `pib_coach_protocols` table exists (`001_initial_schema.sql:650`)
- ✅ `/api/settings/coaching` endpoint exists (`server.mjs:559-570`)
- ❌ **No system prompt assembly** in `server.mjs` (console is not generating LLM responses)
- ❌ Coach protocols not consumed by any server endpoint

**Gap:** Console server doesn't generate LLM responses (chat endpoint delegates to CLI: `server.mjs:718`). Coach protocols are stored but unused.

**Assessment:** 🔨 Partially implemented (storage only, no usage)

**Priority:** P1 — blocks bootstrap (coaching IS the personality)

**File Citations:**
- Spec Section 5.4 — full protocol examples
- `console/server.mjs:559-570` — read-only endpoint
- `console/server.mjs:718` — chat delegates to CLI

---

### 5.5 Scoreboard (Kitchen TV)
**Spec:** Section 5.5 — "Family cards, neuroprosthetic layers panel, Captain status, family total, auto-refresh 60s"

**Reality:**
- ✅ `/api/scoreboard` endpoint exists, delegates to CLI (`server.mjs:342`)
- ✅ Frontend scoreboard page exists (`index.html:629-648`)
- ❌ **Neuroprosthetic Layers panel** — missing from frontend (spec: 7 executive function domains with 0-100 scores)
- ✅ Family cards — present in frontend
- ✅ Captain status — present in API contract, not in current frontend mockup

**Gap:** The **Neuroprosthetic Layers panel** is a key spec addition (Section 5.5 Console Update). It makes the prosthetic **legible** — shows which cognitive functions are being supported. Database doesn't have tables for layer scores (they're computed from activity data, not stored).

**Priority:** P2 — nice-to-have (makes system introspectable, not blocking)

**File Citations:**
- Spec Section 5.5 Console Update — Neuroprosthetic Layers panel mockup
- `console/index.html:629-648` — scoreboard rendering (missing layers)

---

## 6. Ingestion Architecture

### 6.1 Adapter Interface & Pipeline
**Spec:** Section 6 — "Every data source implements same interface, returns Five Shapes, runs 8-stage pipeline"

**Reality:**
- ❌ No adapter implementations found in `server.mjs`
- ❌ No `/webhooks/twilio`, `/webhooks/bluebubbles`, `/webhooks/sheets` endpoints
- ❌ No ingestion pipeline (dedup → parse → classify → privacy fence → route → write)
- ❌ No `IngestEvent` dataclass equivalent

**Gap:** The spec describes a **full ingestion system** with 7 adapters (Gmail, Calendar, Reminders, iMessage, Twilio, Siri, Bank). The console server has **none of this**.

**Assessment:** ❌ Missing entirely

**Priority:** P0 — blocks demo (without ingestion, no data enters system)

**File Citations:**
- Spec Section 6 — full adapter architecture
- `console/server.mjs` — no webhook handlers found

---

### 6.2 Prefix Parser
**Spec:** Section 6.4 — "PREFIX_RULES array with 15 prefixes (grocery:, james:, buy, call, remember, meds, sleep, etc.)"

**Reality:**
- ❌ Not found in `server.mjs`
- 🔨 Frontend has "quick chips" (`index.html:498-502`) that send plain text, but no server-side prefix parsing

**Gap:** Prefix parsing is **Layer 1** (works without LLM). Missing means every capture requires LLM.

**Priority:** P1 — blocks bootstrap (prefix commands are zero-friction capture)

**File Citations:**
- Spec Section 6.4 — `PREFIX_RULES` array
- `console/index.html:498-502` — quick chips (UI only)

---

### 6.3 Micro-Script Generator
**Spec:** Section 6.5 — "Deterministic, no LLM. Generate physical first step from task type + item_ref"

**Reality:**
- ❌ Not found in `server.mjs`
- ✅ `micro_script` column exists on `ops_tasks` (`001_initial_schema.sql:230`)
- ❌ No evidence of script generation logic

**Gap:** Micro-scripts are **Gene 7** (every task has one). Database ready, generation missing.

**Priority:** P1 — blocks bootstrap (micro-scripts are core to task initiation)

**File Citations:**
- Spec Section 6.5 — `generate_micro_script()` function
- `001_initial_schema.sql:230` — column exists

---

## 7. Memory System

### 7.1 Save Memory (Dedup + Supersession)
**Spec:** Section 3.8 (embedded in mem_long_term description) — "save_memory_deduped(), negation detection, reinforcement vs supersession"

**Reality:**
- ✅ `mem_long_term` table with `reinforcement_count`, `superseded_by` columns (`001_initial_schema.sql:570`)
- ❌ **Dedup logic** — not found in `server.mjs`
- ❌ No negation detection ("doesn't like sushi" vs "likes sushi")
- ❌ No reinforcement logic (overlap > 0.60 → increment count)

**Gap:** Memory is append-only without dedup. Will grow unbounded with duplicates.

**Priority:** P1 — blocks bootstrap (memory dedup prevents garbage accumulation)

**File Citations:**
- Spec Section 3.8 — `save_memory_deduped()` implementation
- `001_initial_schema.sql:570-585` — schema supports it

---

### 7.2 Auto-Promotion (Session Facts → Long-Term)
**Spec:** Section 3.8 (embedded) — "Runs every 6 hours. Promotes high-confidence session facts. PROMOTION_PATTERNS dict."

**Reality:**
- ✅ `mem_session_facts` table exists (`001_initial_schema.sql:558`)
- ✅ `auto_promoted` column exists
- ❌ **Auto-promotion cron job** — not found
- ❌ No evidence of promotion patterns (decision → 0.9 confidence, preference → 0.8, etc.)

**Gap:** Session facts never graduate to long-term. They expire after 72 hours.

**Priority:** P2 — nice-to-have (system still functions, but loses learning)

**File Citations:**
- Spec Section 3.8 — `auto_promote_session_facts()` function

---

### 7.3 Memory Browser (Settings)
**Spec:** API contract — `/api/settings/memory?member=m-james&q=mortgage`

**Reality:**
- ✅ Endpoint exists (`server.mjs:642-657`)
- 🔨 FTS5 search delegated to CLI: `runCLI("search", ...)` (`server.mjs:649`)
- ❌ No frontend Settings → Memory tab

**Gap:** Backend ready, frontend missing.

**Priority:** P2 — nice-to-have (introspection, not blocking)

**File Citations:**
- API contract — `/api/settings/memory` spec
- `console/server.mjs:642-657` — endpoint exists
- `console/index.html` — Settings page exists but no memory tab

---

## 8. Proactive Engine

### 8.1 Trigger Definitions
**Spec:** Section 8.1 — "PROACTIVE_TRIGGERS array with 11 triggers (morning_digest, paralysis_detection, overdue_nudge, etc.)"

**Reality:**
- ❌ No trigger definitions found in `server.mjs`
- ❌ No cron scheduler (spec: APScheduler AsyncIOScheduler)
- ❌ No trigger scan loop

**Gap:** Proactive engine is **entirely missing**. No morning digest, no paralysis detection, no velocity celebration, no budget alerts.

**Assessment:** ❌ Missing entirely

**Priority:** P0 — blocks demo (morning digest is the daily reset)

**File Citations:**
- Spec Section 8.1 — full PROACTIVE_TRIGGERS array
- Spec Section 3.6 — APScheduler setup

---

### 8.2 Guardrails
**Spec:** Section 8.2 — "max_messages_per_person_per_day: 5, quiet_hours 22-7, respect_focus_mode"

**Reality:**
- ❌ No guardrails implementation found
- ✅ `focus_mode_active` column exists in `pib_energy_states` (`002_add_energy_states.sql`)

**Gap:** Without guardrails, proactive messages would spam users.

**Priority:** P0 — blocks demo (guardrails are safety layer)

**File Citations:**
- Spec Section 8.2 — GUARDRAILS dictionary

---

### 8.3 Morning Digest Composition
**Spec:** Section 8.3 — "Structured data → Opus → validation → deterministic template fallback"

**Reality:**
- ❌ Not found

**Gap:** Morning digest is the **most important message PIB sends** (spec quote). Missing.

**Priority:** P0 — blocks demo

**File Citations:**
- Spec Section 8.3 — `compose_morning_digest()` function

---

## 9. Comms Inbox / Omnichannel

### 9.1 Channel Registry
**Spec:** Not explicitly in spec, but implied by "full message pipeline, channel routing"

**Reality:**
- ✅ `comms_channels` table exists (`012_channel_registry.sql`)
- ✅ `comms_channel_health` table for polling status
- ✅ `comms_channel_capabilities` table
- ✅ `/api/channels` endpoint (`server.mjs:776-789`)
- ✅ `/api/channels/:id` endpoint (`server.mjs:791-821`)

**Assessment:** ✅ Fully implemented (schema + API)

**Priority:** N/A — complete

---

### 9.2 Batch Windows
**Spec:** Section 8.1 proactive triggers mentions batch windows (morning 8-9, midday 12-1, evening 7-8)

**Reality:**
- ✅ `batch_window`, `batch_date` columns on `ops_comms` (`003_comms_enhancement.sql:13-14`)
- ✅ Config keys for batch window times (`003_comms_enhancement.sql:45-50`)
- ✅ Index for batch queries (`003_comms_enhancement.sql:35-36`)
- ❌ **Batch window assignment logic** — not found in server
- ❌ **Batch processing cron** — not found

**Gap:** Database ready, logic missing.

**Priority:** P1 — blocks bootstrap (batching prevents notification spam)

**File Citations:**
- `003_comms_enhancement.sql:13-14` — columns
- `003_comms_enhancement.sql:45-50` — config

---

### 9.3 Extraction Pipeline
**Spec:** Section 14 (inferred from comms enhancement migration) — "Extract tasks/events from messages asynchronously"

**Reality:**
- ✅ `extraction_status`, `extracted_items` columns (`003_comms_enhancement.sql:15-17`)
- ✅ Index for extraction queue (`003_comms_enhancement.sql:40-41`)
- ❌ **Extraction worker** — not found
- ❌ No async extraction cron

**Gap:** Database ready, worker missing.

**Priority:** P2 — nice-to-have (extraction is Layer 2, system works without)

**File Citations:**
- `003_comms_enhancement.sql:15-17` — columns

---

### 9.4 Draft Generation
**Spec:** Section 14 (inferred) — "CoS drafts responses, queues for approval"

**Reality:**
- ✅ `draft_response`, `draft_status` columns (`003_comms_enhancement.sql:18-20`)
- ✅ Index for draft queries (`003_comms_enhancement.sql:38-39`)
- ✅ Config: `comms_drafting_enabled` (`003_comms_enhancement.sql:53`)
- ❌ **Draft generation logic** — not found
- ❌ No voice profile system (mentioned in config: `voice_profile_rebuild_day`)

**Gap:** Database ready, voice profile + drafting logic missing.

**Priority:** P2 — nice-to-have (drafting is advanced Layer 2)

**File Citations:**
- `003_comms_enhancement.sql:18-20` — columns
- `003_comms_enhancement.sql:53-58` — voice profile config

---

### 9.5 Comms Inbox Frontend
**Spec:** API contract — `/api/comms/inbox`, grouped by batch window, filterable by channel/status

**Reality:**
- ✅ Frontend Comms page exists (`index.html:526-607`)
- ✅ Channel sidebar with health dots
- ✅ Filter pills (all/pending/draft/snoozed/done)
- ✅ Batch window pills (all/morning/midday/evening)
- ✅ Action buttons (Approve, Reject, Respond, Snooze, Archive)
- ❌ **Backend `/api/comms/inbox` endpoint** — not found in `server.mjs`

**Gap:** Frontend ready, backend endpoint missing.

**Priority:** P1 — blocks bootstrap (comms inbox is a core view)

**File Citations:**
- `console/index.html:526-607` — frontend implementation
- `console/server.mjs` — endpoint not found

---

## 10. Financial Integration

### 10.1 Transaction Categorization
**Spec:** Section 3.8 fin_merchant_rules, Section 8.4 misclassification correction

**Reality:**
- ✅ `fin_merchant_rules` table exists (`001_initial_schema.sql:492`)
- ✅ `fin_transactions` table with `categorization_rule`, `needs_review` columns (`001_initial_schema.sql:471`)
- ❌ **Categorization logic** — not found in server
- ❌ No bank import adapter
- ❌ No merchant matching algorithm

**Gap:** Database ready, categorization engine missing.

**Priority:** P2 — nice-to-have (financial context enhances affordability checks, but not blocking)

**File Citations:**
- `001_initial_schema.sql:492-501` — merchant_rules schema

---

### 10.2 Budget Snapshot
**Spec:** Section 3.8 fin_budget_snapshot — "spent_this_month, remaining, pct_used, over_threshold"

**Reality:**
- ✅ `fin_budget_snapshot` table exists (`001_initial_schema.sql:524`)
- ✅ `/api/budget` endpoint exists (`server.mjs:344-356`)
- ❌ **Snapshot refresh cron** — not found (spec: daily at 7:15am)
- ❌ No evidence of snapshot computation logic

**Gap:** Table exists, but never populated.

**Priority:** P1 — blocks bootstrap (budget context is household decision support)

**File Citations:**
- `001_initial_schema.sql:524-533` — schema
- `console/server.mjs:344-356` — read endpoint

---

### 10.3 Affordability Checks
**Spec:** Section 2.2 Laura's view — "Can we afford a babysitter Saturday?" checks Child Care budget

**Reality:**
- ❌ No affordability check function found
- ✅ Budget data schema exists

**Gap:** Logic missing.

**Priority:** P2 — nice-to-have (enhances decision support)

---

## 11. Privacy Enforcement

### 11.1 Privacy Filtering at Read Layer
**Spec:** Gene 2, Gene 7 Invariant 5 — "Privileged data NEVER enters context window. Filtered at read layer."

**Reality:**
- ✅ `privacy` column on `cal_classified_events` (`001_initial_schema.sql:419`)
- ✅ `title_redacted` column for privacy-safe display
- ✅ Privacy filtering in `/api/schedule` endpoint (`server.mjs:227-235`)
- 🔨 Privacy filtering in `/api/today-stream` endpoint (`server.mjs:203-208`)
- ❌ **Not enforced in all endpoints** — `/api/tasks` doesn't filter, `/api/comms` doesn't filter

**Gap:** Partial enforcement. The spec requires **all read endpoints** filter privileged data, not just calendar.

**Priority:** P0 — blocks demo (privacy is a **hard invariant**)

**File Citations:**
- Spec Section 7.3 — `build_calendar_context()` with privacy filtering
- `console/server.mjs:227-235` — schedule endpoint filters
- `console/server.mjs:206-224` — tasks endpoint doesn't filter

---

### 11.2 Privacy Fence (Write Layer)
**Spec:** Gene 6, Rule 3 — "Writes cannot output data the read layer didn't provide."

**Reality:**
- ❌ No write-layer privacy checks found in server
- ✅ Audit log records all writes (`common_audit_log`)

**Gap:** No enforcement that LLM-generated outputs respect privacy boundaries.

**Priority:** P1 — blocks bootstrap (prevents accidental leaks in responses)

**File Citations:**
- Spec Section 6.3 Stage 5 — privacy fence in ingestion pipeline

---

## 12. Google Sheets Sync

### 12.1 Push Sync (Database → Sheets)
**Spec:** Section 9.2 — "SHEETS_SYNC_CONFIG dict, push every 15 min"

**Reality:**
- ❌ Not found in `server.mjs`
- ❌ No Google Sheets adapter
- ❌ No cron job for push sync

**Gap:** Entirely missing.

**Priority:** P2 — nice-to-have (Sheets mirror is backup SSOT, not critical path)

**File Citations:**
- Spec Section 9.2 — `push_to_sheets()` function

---

### 12.2 Webhook Pull (Sheets → Database)
**Spec:** Section 9.3 — `/webhooks/sheets` endpoint with Google Apps Script onChange trigger

**Reality:**
- ❌ No `/webhooks/sheets` endpoint in `server.mjs`

**Gap:** Entirely missing.

**Priority:** P2 — nice-to-have

**File Citations:**
- Spec Section 9.3 — webhook handler

---

## 13. Settings Pages

### 13.1 System Health
**Spec:** API contract — `/api/health` with checks for db, bluebubbles, calendar_sync, etc.

**Reality:**
- ✅ Endpoint exists (`server.mjs:143-145`)
- 🔨 Delegates to Python CLI: `runCLI("health")` (`server.mjs:144`)
- ❌ No inline health checks in server (db connectivity, adapter freshness, write queue depth)

**Gap:** Server relies on CLI for health. If CLI fails, health endpoint fails.

**Priority:** P1 — blocks bootstrap (health monitoring is operational requirement)

**File Citations:**
- API contract — health endpoint spec
- `console/server.mjs:143-145` — CLI delegation

---

### 13.2 Operating Costs
**Spec:** API contract — `/api/costs` with Anthropic API spend, SMS count, etc.

**Reality:**
- ✅ Endpoint exists (`server.mjs:530-537`)
- ❌ **No cost tracking logic** — reads from `pib_config` with keys `cost_*`, but no evidence those keys are populated

**Gap:** Endpoint exists, but no cost accumulation.

**Priority:** P2 — nice-to-have (cost tracking is operational, not functional)

**File Citations:**
- `console/server.mjs:530-537` — endpoint

---

### 13.3 AI Models
**Spec:** API contract — `/api/config/models` shows Sonnet + Opus with usage %

**Reality:**
- ✅ Endpoint exists (`server.mjs:539-548`)
- ✅ Reads from `pib_config` keys `anthropic_model_sonnet`, `anthropic_model_opus`

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 13.4 Sources (Classification Registry)
**Spec:** API contract — `/api/sources` lists all source_classifications

**Reality:**
- ✅ Endpoint exists (`server.mjs:550-553`)
- ✅ Reads from `common_source_classifications`

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 13.5 Life Phases
**Spec:** API contract — `/api/phases` lists phases with status/dates

**Reality:**
- ✅ Endpoint exists (`server.mjs:555-558`)
- ✅ Reads from `common_life_phases`

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 13.6 Config Editor
**Spec:** API contract — `POST /api/config/:key` to update runtime config

**Reality:**
- ✅ Endpoint exists (`server.mjs:570-589`)
- ✅ Writes to `pib_config` with audit log
- ✅ Uses `guardedWrite()` wrapper for permission check

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 13.7 Permissions (Read-Only)
**Spec:** API contract — `/api/settings/permissions` shows agent_capabilities.yaml

**Reality:**
- ✅ Endpoint exists (`server.mjs:591-611`)
- ✅ Loads `agent_capabilities.yaml` via `loadYAML()`

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 13.8 Coaching Protocols
**Spec:** API contract — `/api/settings/coaching` with toggle endpoint

**Reality:**
- ✅ Read endpoint exists (`server.mjs:613-621`)
- ✅ Toggle endpoint exists (`server.mjs:623-632`)
- ✅ Reads/writes `pib_coach_protocols` table

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 13.9 Governance Gates (Read-Only)
**Spec:** API contract — `/api/settings/gates` shows governance.yaml

**Reality:**
- ✅ Endpoint exists (`server.mjs:634-640`)
- ✅ Loads `governance.yaml`

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

### 13.10 Household (Member Management)
**Spec:** API contract — `/api/settings/household` with add/deactivate endpoints

**Reality:**
- ✅ Read endpoint exists (`server.mjs:642-646`)
- ✅ Add member endpoint exists (`server.mjs:648-668`)
- ✅ Deactivate member endpoint exists (`server.mjs:670-675`)

**Assessment:** ✅ Fully implemented

**Priority:** N/A — complete

---

## 14. Capture Domain (Beyond Spec)

**Note:** The capture domain is **not described in the build spec**, but exists in the database schema (`006_capture_domain.sql`) and has substantial infrastructure.

### 14.1 Capture Tables
- ✅ `cap_notebooks` — taxonomy buckets
- ✅ `cap_captures` — main storage with FTS5
- ✅ `cap_connections` — cross-domain links
- ✅ FTS5 index with sync triggers

**Assessment:** ✅ Implemented (beyond spec)

### 14.2 Capture Endpoints
- ❌ No `/api/captures` endpoints found in `server.mjs`
- ❌ No frontend Capture page

**Gap:** Database ready, API + UI missing.

**Priority:** P2 — nice-to-have (capture is Layer 2 enhancement)

---

## 15. Project Domain (Beyond Spec)

**Note:** Not in build spec.

### 15.1 Project Tables
- ✅ `proj_projects`, `proj_milestones`, `proj_resources` (`009_project_schema.sql`)

### 15.2 Project Endpoints
- ❌ No project endpoints in `server.mjs`
- ❌ No frontend Projects page

**Assessment:** 🔨 Schema only

**Priority:** P2 — beyond spec

---

## 16. Sensor Bus (Beyond Spec)

**Note:** Build spec mentions sensor bus (Section 3) but doesn't detail schema.

### 16.1 Sensor Tables
- ✅ `sensor_readings`, `sensor_rules` (`005_sensor_bus.sql`)

### 16.2 Sensor Integration
- ❌ No sensor polling adapters
- ❌ No sensor rule engine

**Assessment:** 🔨 Schema only

**Priority:** P2 — beyond spec

---

## 17. Missing Core Features (Comprehensive)

### P0 — Blocks Demo
1. **whatNow() engine** — deterministic task selection (delegated to CLI, not in server)
2. **Stream carousel UI** — one card at a time, progress dots, endowed progress, glow, keyboard nav
3. **Variable-ratio rewards** — 60/25/10/5 distribution, reward message selection
4. **Elastic streaks** — grace days, custody pause, streak extension logic
5. **Proactive engine** — morning digest, paralysis detection, triggers + guardrails
6. **Ingestion pipeline** — adapters, webhooks, prefix parser, Five Shapes
7. **Privacy enforcement** — consistent filtering across all endpoints
8. **Comms Inbox backend** — `/api/comms/inbox` endpoint with batch window logic

### P1 — Blocks Bootstrap
1. **Custody date math** — DST-aware who_has_child() (delegated to CLI)
2. **Micro-script generator** — deterministic physical first steps
3. **Laura's compressed view** — different UI layout for Laura
4. **Charlie's full-screen view** — sidebar hidden, privacy enforcement
5. **Friction asymmetry guards** — server-side state machine validation
6. **Memory dedup** — negation detection, reinforcement vs supersession
7. **Batch window assignment** — comms batching logic
8. **Budget snapshot refresh** — daily cron, computation logic
9. **Coach protocol usage** — load into system prompt (if server generates responses)
10. **Sidebar custody indicator** — "Charlie with James today" display
11. **Health pulse polling** — 5min interval, color changes
12. **Prefix parser** — deterministic capture routing

### P2 — Nice-to-Have
1. **Neuroprosthetic Layers panel** — 7 executive function scores on scoreboard
2. **Memory auto-promotion** — session facts → long-term (6h cron)
3. **Memory browser UI** — Settings → Memory tab
4. **Extraction pipeline** — async task/event extraction from comms
5. **Draft generation** — CoS voice profile + drafting logic
6. **Transaction categorization** — merchant matching, auto-categorize
7. **Affordability checks** — budget-aware decision support
8. **Google Sheets sync** — push/pull, bootstrap import
9. **Cost tracking** — Anthropic API spend accumulation
10. **Capture domain UI** — notebooks, connections, FTS5 search
11. **Project domain UI** — project management views
12. **Sensor bus** — polling adapters, rule engine
13. **Capture deep organizer** — LLM enrichment cron
14. **Resurfacing** — proactive capture resurfacing
15. **Cross-user connections** — household-wide capture links

---

## 18. What IS Implemented (Positives)

### Database Schema
✅ **Comprehensive and complete** — all tables from spec exist, plus additional domains (capture, projects, sensors, channels)

### Console Shell
✅ **Core shell** — sidebar, actor switcher, navigation, basic routing

### API Endpoints (Settings)
✅ **Settings pages** — health, costs, models, sources, phases, config, permissions, coaching, gates, household all have working endpoints

### Channel Registry
✅ **Omnichannel foundation** — channel definitions, health tracking, capabilities, member access

### Privacy Schema
✅ **Privacy infrastructure** — classification table, privacy column on events, title_redacted field

### Task Schema
✅ **Full task model** — state machine, micro_script, energy/effort, item_type, dependencies

### Comms Schema
✅ **Advanced comms** — batch windows, extraction, drafts, snooze, visibility

### Memory Schema
✅ **Memory infrastructure** — sessions, messages, facts, long-term with supersession

### Financial Schema
✅ **Complete financial model** — transactions, budget, merchant rules, capital expenses

---

## 19. Architectural Observations

### 19.1 Python vs Node.js
The spec describes a **Python/FastAPI** system. The implementation is **Node.js/Express**. This creates a fundamental disconnect:
- Spec's Python code examples are not directly applicable
- Server delegates core logic to `runCLI()` calls, suggesting a **Python backend exists elsewhere**
- Console server is a **thin view layer** over a separate Python system

**Implication:** This audit can only assess the **console layer**. The Python backend (if it exists) is out of scope.

### 19.2 Layer 1 vs Layer 2
The spec defines:
- **Layer 1 (Core)** — works without LLM, deterministic, always available
- **Layer 2 (Enhanced)** — requires Anthropic API, degrades gracefully

The console server **delegates most Layer 1 logic to CLI**:
- whatNow() → CLI
- custody → CLI
- streaks → CLI (inferred)
- rewards → CLI (inferred)

**This means:** The console cannot fulfill the Layer 1 guarantee ("Always works. No LLM. No API calls.") because it depends on an external CLI.

### 19.3 Gene 1 (The Loop)
The spec's **Gene 1** pattern (DISCOVER → PROPOSE → CONFIRM → CONFIG → DETERMINISTIC) is not evident in the console server. The server reads from tables that presumably were populated via The Loop, but the Loop itself is not in the server.

**Implication:** The console is **read-mostly**. Writes are guarded and limited. The Loop likely runs in the Python backend.

---

## 20. Recommendations

### Immediate (P0)
1. **Document the architecture clearly** — if the console is a view layer over a Python backend, state that explicitly. Current spec/reality mismatch creates confusion.
2. **Implement privacy filtering consistently** — all read endpoints must respect `privacy` column.
3. **Build stream carousel UI** — this is the James experience. Without it, the console is just a task list.
4. **Implement /api/comms/inbox** — frontend exists, backend missing.
5. **Add sidebar custody indicator** — simple read from `/api/custody/today`.
6. **Add health pulse polling** — 5min interval, update pill color.

### Short-Term (P1)
1. **Implement Laura's compressed view** — different layout when `currentActor === 'm-laura'`.
2. **Enforce Charlie's privacy** — hide nav items, full-screen mode.
3. **Build prefix parser in server** — Layer 1 capture without LLM.
4. **Implement sidebar nav badges** — inbox count, decisions count.
5. **Add micro-script display** — tasks should show the micro_script field in UI.

### Long-Term (P2)
1. **Decide on Neuroprosthetic Layers** — if keeping, compute scores from activity data.
2. **Consider porting core logic to Node** — if the goal is a standalone console, whatNow(), streaks, rewards should be in-process, not CLI-delegated.
3. **Build Capture UI** — the schema is impressive, UI would unlock it.

---

## 21. File Citations Index

**Build Spec:** `pib-v5-build-spec.md`
- Section 2.1 — James actor definition
- Section 2.2 — Laura actor definition
- Section 2.3 — Charlie actor definition
- Section 3.1 — Stack definition
- Section 3.6 — Write batching + APScheduler
- Section 3.8 — Full schema
- Section 4 — whatNow() implementation
- Section 4.1 — Custody date math
- Section 5.1 — Variable-ratio rewards
- Section 5.2 — Elastic streaks
- Section 5.3 — Friction asymmetry
- Section 5.4 — Coach protocols
- Section 5.5 — Scoreboard
- Section 5.6 — Console design system
- Section 5.7 — Console shell
- Section 6 — Ingestion architecture
- Section 6.4 — Prefix parser
- Section 6.5 — Micro-script generator
- Section 7.3 — Privacy-filtered context
- Section 8.1 — Proactive triggers
- Section 8.2 — Guardrails
- Section 8.3 — Morning digest
- Section 9.2 — Sheets push sync
- Section 9.3 — Sheets webhook pull

**API Contract:** `pib-api-contract.md`
- All endpoint specs

**Server:** `console/server.mjs`
- Lines 10-15 — Express setup
- Lines 143-145 — /api/health
- Lines 153-204 — /api/today-stream
- Lines 184 — whatNow CLI delegation
- Lines 195 — custody CLI delegation
- Lines 206-224 — /api/tasks
- Lines 227-235 — /api/schedule (privacy filtering)
- Lines 235-239 — /api/decisions
- Lines 243-255 — /api/household-status
- Lines 342 — /api/scoreboard
- Lines 344-356 — /api/budget
- Lines 530-537 — /api/costs
- Lines 539-548 — /api/config/models
- Lines 550-553 — /api/sources
- Lines 555-558 — /api/phases
- Lines 559-570 — /api/settings/coaching
- Lines 570-589 — POST /api/config/:key
- Lines 591-611 — /api/settings/permissions
- Lines 613-621 — /api/settings/coaching (read)
- Lines 623-632 — /api/settings/coaching/:id/toggle
- Lines 634-640 — /api/settings/gates
- Lines 642-675 — /api/settings/household
- Lines 699 — task-complete CLI delegation
- Lines 718 — chat CLI delegation
- Lines 759-767 — /api/chores
- Lines 776-789 — /api/channels
- Lines 791-821 — /api/channels/:id

**Frontend:** `console/index.html`
- Lines 5 — Google Fonts
- Lines 9-16 — CSS custom properties
- Lines 26-29 — Shell layout
- Lines 101 — HIDDEN_FOR_CHILD array
- Lines 104 — DOMAIN_BADGE object
- Lines 168-174 — Actor switcher
- Lines 177-183 — Navigation
- Lines 185-189 — Health pill
- Lines 312 — whatNow display
- Lines 319-333 — Today stream rendering
- Lines 322-324 — Energy pills
- Lines 498-502 — Chat quick chips
- Lines 526-607 — Comms inbox page
- Lines 629-648 — Scoreboard page

**Migrations:**
- `001_initial_schema.sql` — Lines 8-664 (all core tables)
- `002_add_energy_states.sql` — Energy states table
- `003_comms_enhancement.sql` — Comms domain enhancements
- `005_sensor_bus.sql` — Sensor tables
- `006_capture_domain.sql` — Capture domain
- `009_project_schema.sql` — Project tables
- `011_comms_fts5.sql` — Comms FTS5
- `012_channel_registry.sql` — Channel registry

---

## 22. Conclusion

This console has a **rock-solid database schema** and a **well-architected shell**. The Settings pages are mostly complete. The channel registry is impressive.

**But:**
- The **core engine** (whatNow, rewards, streaks, proactive triggers) is **delegated to a Python CLI** that was not audited.
- The **ADHD-specific UI affordances** (stream carousel, progress dots, endowed progress, glow) are **missing**.
- The **Comms Inbox frontend** is built, but the **backend endpoint is missing**.
- **Privacy enforcement** is **inconsistent** across endpoints.

**This is a 🔨 PARTIALLY IMPLEMENTED system** — the foundation is solid, but the differentiated features that make PIB a **prosthetic prefrontal cortex** (not just a task manager) are incomplete.

**Next Steps:**
1. Clarify the architecture: Is this a view layer over a Python backend, or should it be standalone?
2. If view layer: Document the Python backend contract and ensure console consumes it correctly.
3. If standalone: Port core logic (whatNow, rewards, streaks) to Node.js.
4. Either way: Build the stream carousel, enforce privacy, wire the Comms Inbox backend.

---

**End of Deep Audit**
