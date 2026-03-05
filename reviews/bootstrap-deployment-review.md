# Bootstrap & Deployment Readiness Review

**Date:** 2026-03-05  
**Reviewer:** dev-subagent  
**Codebase:** c40v (PIB v5)

---

## Executive Summary

The bootstrap pipeline is **substantially complete** with a clear path from bare metal to running system for all three machine types. There are several issues ranging from minor to moderate that should be fixed before a production deploy.

**Overall readiness: 🟡 ALMOST READY — 6 issues to resolve**

---

## 1. Bootstrap Script (`scripts/bootstrap.sh`)

### ✅ What's correct
- Creates all required directories (`data`, `logs`, `config`, `data/backups`)
- Sets up Python venv and installs deps via `pip install -e .[dev]`
- Copies `.env.example` → `/opt/pib/config/.env`
- Copies workspace templates for cos/coach/dev agents
- Installs console npm deps (when node available)
- Installs launchd plist
- Handles `--dry-run`, `--dev`, `--prod`, `--skip-frontend`, `--noninteractive` flags
- Preflight checks (python3, sqlite3, disk space)
- Prod mode runs strict readiness probe
- Verifies governance.yaml + FTS5 triggers

### 🔴 Issue 1: `--dry-run` flag is parsed but never checked
The script sets `DRY_RUN=1` and prints a banner, but **no step actually checks `$DRY_RUN` before executing**. Every `mkdir`, `pip install`, `cp`, `npm install`, etc. runs regardless. This is a bug.

**Fix:** Wrap each step in `if [[ "$DRY_RUN" -eq 0 ]]; then ... else echo "  [DRY RUN] would ..."; fi`

### 🟡 Issue 2: Migrations not explicitly run in bootstrap
The bootstrap script calls `seed_data.py` which calls `apply_schema()` + `apply_migrations()`. This works, but the migration step is implicit (buried inside the seed script). If someone runs the seed script independently, they might not realize it also applies migrations.

**Recommendation:** Add an explicit migration step before seeding, or at minimum document that `seed_data.py` handles schema + migrations.

### 🟡 Issue 3: Permissions — 700 on PIB_HOME is aggressive
`chmod 700 "$PIB_HOME"` means only the owner can access anything under `/opt/pib/`. If any service runs as a different user (e.g., a launchd system-level daemon), it won't be able to read the DB. Currently the plist runs as the user agent, so this is fine, but it's fragile.

### ✅ Permissions otherwise correct
- `config/` → 700 ✅
- `data/` → 755 ✅ (though 700 might be better for data)
- `.env` → 600 ✅
- `pib.db` → 600 ✅

---

## 2. Migration Ordering

### ✅ No duplicate numbering
Migrations are numbered 001–016, **sequentially with no gaps and no duplicates**. The task brief asked about "two files starting with 002_" — this is not the case. Only one `002_add_energy_states.sql` exists.

### ✅ Migration application logic is sound
- `db.py:apply_migrations()` reads `meta_migrations` table for current version
- Processes files in sorted order by filename prefix
- Stores checksums and up/down SQL
- Supports rollback SQL via `-- DOWN` separator

### ✅ Dependencies are correct
- 001: Full schema (all base tables)
- 002–006: Add columns/tables that reference base tables
- 007: FTS5 triggers (depends on tables from 001+003)
- 008–016: Incremental additions, all depend on earlier tables

---

## 3. MAC_MINI_WALKTHROUGH.md (Hub Bootstrap)

### ✅ Strengths
- Extremely thorough beginner guide (Parts 1–17)
- Covers everything: unboxing, macOS setup, Homebrew, Node, Python, Git, GitHub SSH, OpenClaw, Google OAuth, Anthropic API, BlueBubbles, Signal, WhatsApp, Twilio, agent files, launchd, pre-flight checklist
- Port allocation table (3141, 3333, 18789, 1234)
- 10-prompt deployment sequence with clear "when to paste" triggers
- Troubleshooting section

### ✅ Correct paths
All paths reference `/opt/pib/` consistently.

### 🟡 Issue 4: No [HUMAN] / [AGENT] markers
The doc doesn't use explicit `[HUMAN]` or `[AGENT]` labels. Instead, Parts 1–14 are human steps and Part 15+ are agent-driven (via OpenClaw prompts). This is clear from context but could be more explicit.

### 🟡 Issue 5: Agent workspace references `infra` but bootstrap.sh only copies `cos/coach/dev`
- `MAC_MINI_WALKTHROUGH.md` Part 12 loops over `cos coach infra dev`
- `bootstrap.sh` step 7b loops over `cos coach dev`
- `workspace-template/` directory has no `infra/` subdirectory
- **Mismatch:** The walkthrough references an `infra` agent that doesn't exist in templates

**Fix:** Either add `infra/` workspace template or remove `infra` from the walkthrough loop.

### ✅ Google OAuth covered
Part 6 covers `gog auth login` for both James and Laura's accounts.

### ✅ OpenClaw installation covered
Part 5 covers `npm install -g openclaw`, init, and verification.

---

## 4. PERSONAL_MINI_SETUP.md (Bridge Setup)

### ✅ Excellent coverage
- Clear hub+spoke architecture diagram
- Per-machine component matrix
- Full BlueBubbles install + config for both bridges
- Apple Shortcuts automations with detailed step-by-step build instructions
- HomeKit bridge setup (3 options: Shortcuts, Homebridge, MQTT)
- Sensor webhook contract with full payload schemas
- Task capture webhook contract
- Local queue + retry mechanism for CoS downtime
- Network security (LAN-only, bearer tokens, firewall rules)
- Maintenance & monitoring procedures
- Troubleshooting guide
- Complete crontab appendices

### 🟡 Issue 6: Sensor endpoint port inconsistency
- Architecture diagram says `$COS_HOST :3333`
- Key Endpoints table says `http://$COS_HOST:3333/api/sensors/ingest`
- But the homebridge forwarder script (Section 7) forwards to **port 3141**: `port: 3141, path: '/api/sensors/ingest'`
- Port allocation in the walkthrough says 3141 = "PIB CoS API" and 3333 = "Console dashboard"

**Ambiguity:** Is the sensor ingest on port 3141 (Python API) or 3333 (Console/Node)? The bridge setup doc mostly says 3333 but the forwarder says 3141. This needs to be resolved and made consistent.

### ✅ Per-bridge credentials scoped
- James: `BLUEBUBBLES_JAMES_SECRET` + `BLUEBUBBLES_JAMES_URL`
- Laura: `BLUEBUBBLES_LAURA_SECRET` + `BLUEBUBBLES_LAURA_URL`
- Webhook URLs differ per bridge (`/api/webhooks/bluebubbles/james` vs `/laura`)

### ✅ Privacy classification documented
Laura's data auto-classified as `privileged` with defense-in-depth (client-side + server-side enforcement).

### ✅ Health check mechanism documented
Section 9 has per-bridge health check commands and CoS-side staleness detection with expected intervals.

---

## 5. Launchd/Startup (`config/com.pib.runtime.plist`)

### ✅ Correct configuration
- Label: `com.pib.runtime`
- Runs: `openclaw gateway start` via `/bin/sh -c`
- WorkingDirectory: `/opt/pib`
- RunAtLoad: true (starts on login)
- KeepAlive: true (auto-restart on failure)
- ThrottleInterval: 5 seconds (prevents restart storm)
- Logs to `/opt/pib/logs/pib-stdout.log` and `pib-stderr.log`
- PATH includes `/opt/homebrew/bin`, venv, standard paths
- Sets `PIB_DB_PATH` and `PIB_LOG_DIR` env vars

### ❓ No separate console plist
The console server (`console/server.mjs`) doesn't have its own launchd plist. The walkthrough (Part 13) creates a plist for `com.openclaw.gateway` but not for the console. If the console runs independently on port 3333, it needs its own plist.

**Note:** If the console is started by the OpenClaw gateway internally, this is fine. But it's not documented either way.

---

## 6. Readiness Checks (`src/pib/readiness.py`)

### ✅ Checks critical dependencies
- **Env vars:** ANTHROPIC_API_KEY, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, SIRI_BEARER_TOKEN
- **BlueBubbles:** At least one bridge pair (SECRET+URL) configured
- **Google:** SA key path + file existence (skipped in OpenClaw mode)
- **DB tables:** ops_tasks, ops_comms, cal_classified_events, fin_transactions, common_members
- **FTS5 triggers:** ≥9 expected
- **governance.yaml:** Exists

### ❌ Does NOT distinguish hub vs bridge
Readiness checks are hub-only. There's no bridge readiness check (e.g., "is BlueBubbles running?", "can I reach the CoS?"). Bridge readiness is handled informally via the verification checklist in PERSONAL_MINI_SETUP.md.

### ✅ Can run before full bootstrap
The checks are non-destructive — they only read env vars, check file existence, and query DB tables. If the DB doesn't exist yet, it would fail on the DB checks, which is correct behavior (tells you what's missing).

### ✅ Strict startup mode
`validate_strict_startup()` raises `RuntimeError` when `PIB_STRICT_STARTUP=1` and required checks fail. Used in bootstrap.sh prod mode.

---

## 7. Test Suite

### ✅ In-memory SQLite correctly configured
- `conftest.py` uses `aiosqlite.connect(":memory:")`
- Applies full schema via `apply_schema()` + `apply_migrations()`
- Seeds test data (3 members, custody config, 4 tasks, ID sequences)
- Row factory set to `aiosqlite.Row`

### ✅ No external services required
- Tests use in-memory DB
- `DBSnapshot` fixture provides pre-built state for engine tests
- No network calls in fixtures

### ✅ Comprehensive test coverage
35 test files covering: adapters, bootstrap verification, bridge isolation, capture, CLI, comms, complexity scoring, context, custody, energy, engine, extraction, FTS5 triggers, graceful degradation, ingest, isolation, LLM, memory, outbound integration, prefix parser, privacy, proactive triggers, project (detection, engine, gates, planner, rate limit), readiness, rewards, sensor (bus, enrichment, privacy, protocol, triggers), state machine, streaks, timezone, voice.

---

## Issue Summary

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| 1 | 🔴 HIGH | `--dry-run` flag does nothing | `scripts/bootstrap.sh` |
| 2 | 🟡 MED | Migrations implicit in seed script | `scripts/bootstrap.sh` step 5 |
| 3 | 🟡 LOW | PIB_HOME 700 is aggressive | `scripts/bootstrap.sh` step 1 |
| 4 | 🟡 LOW | No [HUMAN]/[AGENT] markers in walkthrough | `MAC_MINI_WALKTHROUGH.md` |
| 5 | 🟡 MED | `infra` agent referenced but doesn't exist | Walkthrough vs bootstrap.sh vs templates |
| 6 | 🟡 MED | Sensor endpoint port inconsistency (3141 vs 3333) | `PERSONAL_MINI_SETUP.md` |

### Not issues (clarified)
- **Migration numbering:** Clean 001–016, no duplicates
- **Console plist:** Likely managed by OpenClaw gateway, but should be documented

---

## Per-Machine Readiness

| Machine | Ready? | Blockers |
|---------|--------|----------|
| CoS Mac Mini (hub) | 🟡 | Fix dry-run bug, resolve port ambiguity |
| James's Mac Mini (bridge) | 🟢 | Docs are thorough and actionable |
| Laura's Mac Mini (bridge) | 🟢 | Same as James minus HomeKit — clearly documented |

---

## Recommendations (Priority Order)

1. **Fix `--dry-run`** in bootstrap.sh — this is the only blocking bug
2. **Resolve port 3141 vs 3333** for sensor ingest — pick one and update all docs
3. **Remove `infra` from walkthrough** or add workspace template
4. **Add bridge readiness script** (even a simple bash health-check)
5. **Document console startup** — does OpenClaw gateway start it, or does it need its own plist?
6. **Add [HUMAN]/[AGENT] markers** to walkthrough for clarity
