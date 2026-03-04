# Bootstrap Readiness Task Plan — PIB v5 on OpenClaw

**Context:** PIB v5 (chief-40-vermont) runs on OpenClaw as L0 infrastructure. This plan defines what PIB must build vs what OpenClaw already provides. Read alongside:
- `docs/openclaw-integration.md` — architecture spec (what to keep/replace/build)
- `MAC_MINI_BOOTSTRAP.md` — technical checklist
- `MAC_MINI_WALKTHROUGH.md` — step-by-step beginner setup

**Deployment model:** OpenClaw daemon on Mac Mini handles channels, cron, model routing, Google auth (`gog` CLI). PIB is a Python package called via `pib.cli` from OpenClaw scripts. SQLite is the SSOT. No standalone FastAPI server.

---

## Exit Criteria (Definition of Done)

PIB is launch-ready when all are true:

- Mac Mini bootstrap is reproducible per `MAC_MINI_WALKTHROUGH.md`.
- Credentials wired: Google (`gog auth`), Anthropic (`openclaw config`), BlueBubbles, and at least one messaging channel (Signal/WhatsApp/iMessage).
- Inbound + outbound messaging works end-to-end via OpenClaw channels.
- Tasks, Calendar, and Finance SSOTs populated in SQLite with deterministic ingest/sync.
- Per-member privacy enforced at the read layer (Gene 7 invariant #5).
- Backups, health checks (HEARTBEAT.md), and restore drill operational.
- `pytest tests/ -v` all green.
- All probes from `docs/openclaw-integration.md` §9 pass.

---

## What OpenClaw Handles (not PIB's responsibility)

These are provided by OpenClaw L0. PIB does not build or manage them:

| Capability | OpenClaw provides | PIB equivalent dropped |
|---|---|---|
| Channel routing | Signal, WhatsApp, iMessage, SMS, webchat | `web.py` webhook endpoints |
| Google auth | `gog auth login` + automatic token refresh | OAuth flows, token lifecycle |
| Model routing | Multi-provider LLM, failover, config swap | Direct Anthropic client |
| Cron engine | Scheduled jobs with heartbeat monitoring | APScheduler |
| Process management | Gateway daemon, auto-restart | uvicorn process management |
| Webhook security | Channel-level auth (Twilio signatures, etc.) | `auth.py` middleware |
| Session management | Agent sessions, conversation history | `mem_sessions` / `mem_messages` |
| Credential storage | `openclaw config set` | `.env` file management |

---

## P0 — Foundation & Security

### T-001: Startup Validation ✅ DONE
- `pib.cli bootstrap` validates: Python version ≥ 3.12, SQLite with FTS5, `PIB_DB_PATH` writable, required config present.
- Fails fast with actionable error messages if anything is missing.
- **DoD:** `pib.cli bootstrap` either succeeds or prints exactly what's wrong and how to fix it.

### T-002: Privacy & PII Guardrails (Gene 7 #5) ✅ DONE
- Read-layer privacy fence enforced: `privacy: full/privileged/redacted` on all calendar events.
- Laura's work calendar content (`privileged`) never enters LLM context — filtered in `build_calendar_context()`, not in prompts.
- PII-safe logging: no raw calendar titles, no email bodies, no phone numbers in log output.
- **Add canary tests:** pytest tests that assert privileged data is absent from assembled context strings.
- **DoD:** Privacy policy enforced by code paths and verified by tests. Not by prompts.

### T-003: Console Access Control
- Console (port 3333) serves on LAN only — bind to `0.0.0.0` but no external port forwarding.
- Optional: simple bearer token for API endpoints (`PIB_CONSOLE_TOKEN` env var, checked if set, skipped if unset).
- Member identity on console determined by UI selection (not login — household of 4 on local network).
- **DoD:** Console accessible from any device on home WiFi. Not accessible from internet unless explicitly tunneled.

---

## P0 — Core Data Pipelines

### T-010: Calendar Pipeline (priority #1)
- `scripts/core/calendar_sync.mjs` calls `gog calendar events --json` for each classified source.
- Raw events written to `cal_raw_events` with idempotency (UNIQUE on source_id + google_event_id).
- Classification pipeline: `cal_raw_events` → `cal_classified_events` using rules from `common_source_classifications`.
- Privacy tier applied during classification (full/privileged/redacted per source config).
- Stale-source detection: track `last_synced` per `cal_sources` row, warn if >30 min stale.
- Incremental sync every 15 min (OpenClaw cron). Full resync daily at 2 AM.
- **DoD:** `whatNow()` sees today's calendar events. Morning digest includes schedule. Conflicts detected. `gog` failure degrades gracefully (uses last-known data + warns).

### T-011: Gmail → Comms Inbox
- `scripts/core/gmail_sync.mjs` calls `gog gmail list --json` with incremental cursor.
- Feeds into `pib.cli comms-ingest` which maps to `ops_comms` with idempotency.
- Batch window assignment (morning/midday/evening) via deterministic `assign_batch_window()`.
- Urgency classification: keyword-based (deterministic), not LLM.
- Extraction pipeline proposes tasks/events from message content (requires approval gate).
- **DoD:** "Do I need to respond to anyone?" works. Comms batched for ADHD-friendly delivery windows.

### T-012: Financial OS Sync
- `scripts/core/finance_sync.mjs` calls `gog sheets get` on Financial OS spreadsheet.
- Normalizes into `fin_transactions` + recomputes `fin_budget_snapshot`.
- Dedup by external_id. Merchant normalization via `fin_merchant_rules`.
- Sync every 15 min (OpenClaw cron).
- **DoD:** "Can we afford X?" and "How's the budget?" return real data. Budget alerts fire when `over_threshold = 1`.

### T-013: Tasks Bidirectional Sync
- SQLite `ops_tasks` is the SSOT for task state.
- Read from Google Sheets (Life OS TASKS tab) on initial hydration.
- Write back task status changes to Sheets for visibility (optional, one-way push).
- All mutations go through state machine (`can_transition` + guards).
- Recurring spawn is idempotent (`last_spawned` check prevents duplicates).
- **DoD:** Tasks created/completed/deferred in PIB appear in Sheets. State machine invariants hold under all test scenarios.

### T-014: Cross-Source Extraction
- Comms → proposed tasks/events via `extraction.py` worker.
- Confidence thresholds: ≥0.8 = auto-propose for approval, <0.8 = log only.
- Approval gate: proposed items enter `mem_approval_queue`, require human yes.
- Approved items become real `ops_tasks` or `cal_classified_events` rows.
- **DoD:** "PIB found a dentist appointment in your email — want me to add it?" works end-to-end.

---

## P0 — Messaging & Outbound

### T-020: Outbound Message Delivery
- OpenClaw handles transport (Signal, WhatsApp, iMessage, SMS).
- PIB triggers outbound via agent session responses (reactive) and proactive engine (scheduled).
- Proactive messages respect guardrails: quiet hours, focus mode, in-meeting, daily/hourly limits.
- Delivery status tracked in `ops_comms` (sent/delivered/failed).
- **DoD:** Morning digest reaches James via preferred channel at 7:15 AM. Proactive nudges fire correctly. Non-household messages go to approval queue (Gene 4).

### T-021: Proactive Engine Wiring
- 11 triggers from `proactive.py` already defined.
- Wire trigger output → OpenClaw outbound message delivery.
- Cooldown tracking via `mem_cos_activity`.
- **DoD:** Critical conflict alerts, overdue nudges, paralysis detection, budget alerts, and comms batch summaries all fire and deliver at the right times.

---

## P1 — Surfaces & UX

### T-030: Scoreboard (Kitchen TV)
- `/scoreboard` endpoint serves fullscreen HTML page.
- Three columns: James vs Laura vs Charlie.
- Data from `/api/scoreboard-data` (already implemented in c40v).
- Auto-refresh every 60 seconds. Dark mode. Readable across room.
- **DoD:** TV at `http://MAC-IP:3333/scoreboard` shows live family scores, streaks, next tasks.

### T-031: ADHD Stream (James Carousel)
- `/api/today-stream` already returns structured stream data.
- Console renders as one-card-at-a-time carousel per build spec §2.1.
- Endowed progress items ("Woke up ✓", "Opened PIB ✓") pre-filled.
- Energy state + streak visible. Micro-script prominent.
- **DoD:** James opens console → sees ONE thing to do, with the first physical action spelled out.

### T-032: Role-Tailored Views
- James: carousel (`view_mode: carousel`). One card, micro-scripts, energy matching.
- Laura: compressed (`view_mode: compressed`). Brief, decisions-needing-her, what James is handling.
- Charlie: child (`view_mode: child`). Chore checklist with star rewards.
- View mode read from `common_members.view_mode` column.
- **DoD:** Each family member sees an interface designed for them.

### T-033: Console Chat
- Chat widget in console sends messages to OpenClaw agent.
- Agent uses assembled context from `pib.cli context --member {member_id}`.
- Responses rendered in chat UI with tool action indicators.
- **DoD:** Chat in console works like messaging PIB from any channel, but with richer UI.

---

## P1 — Reliability & Ops

### T-040: Health Checks (HEARTBEAT.md)
- `pib.cli health --json` checks:
  - SQLite readable + writable
  - `gog calendar list` succeeds (Google auth valid)
  - Console server responding on port 3333
  - Last calendar sync age < 30 min
  - No unresolved critical conflicts
  - DB size within bounds
  - Backup freshness
- OpenClaw heartbeat triggers this and alerts Bossman if anything is `error` or `warn`.
- **DoD:** HEARTBEAT_OK when healthy. Actionable alert text when not.

### T-041: Backup & Restore
- Hourly SQLite backup: copy `pib.db` to `backups/pib-YYYY-MM-DDTHH.db`.
- Daily backup verification: open backup, run `PRAGMA integrity_check`.
- Retain 7 days of hourly backups, 30 days of daily backups.
- Restore drill: documented procedure, tested quarterly.
- **DoD:** `pib.cli backup` creates verified backup. `pib.cli restore --from backups/pib-xxx.db` restores to known state.

### T-042: Migration Safety ✅ DONE
- `meta_migrations` table tracks applied migrations with checksums.
- Every migration has `up_sql` and `down_sql`.
- `pib.cli migrate` backs up DB before applying, rolls back on failure.
- **DoD:** Schema changes are reversible with tested procedure.

### T-043: Structured Logging
- `pib.cli` commands output JSON to stdout (for OpenClaw to parse).
- Errors go to stderr with correlation IDs.
- No PII in logs (calendar titles redacted, phone numbers masked).
- Log rotation: `/tmp/pib-*.log` files, 10MB max, 5 backups.
- **DoD:** Any failure traceable. No PII leakage in log files.

---

## P1 — Deployment Hardening

### T-050: Launchd Auto-Start
- OpenClaw gateway: `com.openclaw.gateway.plist` with KeepAlive + RunAtLoad.
- Console server: `com.pib.console.plist` with KeepAlive + RunAtLoad.
- BlueBubbles: Login Items auto-start.
- Crash-loop detection: if process restarts >5 times in 10 min, stop and alert.
- **DoD:** Power cycle Mac Mini → all services running within 60 seconds, no human intervention.

### T-051: Remote Access
- SSH enabled (System Settings → Sharing → Remote Login).
- Cloudflare tunnel for external webhook delivery (Twilio, Siri Shortcuts).
- Tailscale optional for personal SSH access from anywhere.
- Console NOT exposed externally unless explicitly tunneled.
- **DoD:** James can SSH from laptop. Twilio webhooks reach Mac Mini. Console is LAN-only by default.

---

## P2 — Quality & Completeness

### T-060: Test Coverage ✅ DONE (507+ tests)
- Existing: 20 unit/integration test files (engine, state machine, custody, energy, rewards, streaks, memory, privacy, voice, ingest, web).
- Add: E2E tests with mock adapters (mock `gog` CLI output, mock OpenClaw channel).
- Add: Canary tests for privacy (T-002).
- Add: Invariant tests for all Gene 7 rules.
- **DoD:** `pytest tests/ -v` covers all critical paths. CI gate optional but recommended.

### T-061: Cost Governance ✅ DONE
- `cost.py` tracks per-model token usage.
- Monthly spend alert when approaching budget threshold.
- Auto-degrade: switch to cheaper model tier when 80% of budget consumed.
- **DoD:** Predictable monthly API spend. Alert before overspend.

### T-062: Data Retention
- `cleanup_expired` job runs nightly at 3 AM.
- Retention: idempotency keys 7 days, undo log 24 hours, session facts 72 hours (unless promoted).
- Audit log: retain 90 days, then archive.
- `ops_tasks` rows: never deleted (Gene 7 invariant #1).
- **DoD:** DB doesn't grow unbounded. Historical data preserved per policy.

### T-063: Voice Intelligence Bootstrap
- Passive — collects corpus samples from approved drafts and direct replies.
- Requires ~15 samples per scope before synthesis.
- Weekly profile rebuild (Sunday 3 AM cron job).
- No action needed at bootstrap — it learns over time.
- **DoD:** After 2-3 weeks of usage, voice profiles exist and drafts match writing style.

---

## Execution Sequence

```
Phase 1 — Bootstrap (MAC_MINI_WALKTHROUGH.md)
  Mac setup → software → OpenClaw → credentials → agent files
  Time: ~2 hours human, then agent takes over

Phase 2 — Core Build (agent executes autonomously)
  T-010 Calendar pipeline          ← #1 priority, unlocks whatNow + schedule
  T-013 Tasks sync                 ← #2, unlocks task management
  T-001 Startup validation         ← baked into pib.cli bootstrap
  T-002 Privacy guardrails         ← canary tests
  T-020 Outbound messaging         ← unlocks proactive delivery
  T-021 Proactive engine wiring    ← morning digest, nudges
  Time: 3-4 agent sessions

Phase 3 — Surfaces
  T-030 Scoreboard                 ← kitchen TV
  T-031 ADHD Stream                ← James carousel
  T-032 Role views                 ← Laura/Charlie experiences
  T-033 Console chat               ← web chat interface
  Time: 2-3 agent sessions

Phase 4 — Data Completeness
  T-012 Financial sync             ← budget awareness
  T-011 Gmail → Comms              ← communication tracking
  T-014 Cross-source extraction    ← auto-propose tasks from email
  Time: 2-3 agent sessions

Phase 5 — Hardening
  T-040 Health checks
  T-041 Backup/restore
  T-042 Migration safety
  T-043 Structured logging
  T-050 Launchd hardening
  T-051 Remote access
  T-003 Console access control
  Time: 1-2 agent sessions

Phase 6 — Quality
  T-060 Test coverage
  T-061 Cost governance
  T-062 Data retention
  T-063 Voice intelligence (passive, no build needed)
  Time: 1-2 agent sessions
```

**Total estimated: ~15 agent sessions from bootstrap to production-grade.**

---

## Go-Live Checklist

```
CORE
[ ] pib.cli bootstrap succeeds
[ ] pytest tests/ -v all green
[ ] whatNow() returns task with micro-script
[ ] Custody math correct for today
[ ] Calendar pipeline running (cal_classified_events populated)

MESSAGING
[ ] Inbound message via at least one channel → PIB responds
[ ] Outbound proactive message delivered (morning digest)
[ ] Non-household message → approval queue (not sent directly)

DATA
[ ] Tasks SSOT populated from Life OS Sheets
[ ] Financial SSOT populated from Financial OS Sheets
[ ] Calendar SSOT populated from Google Calendar via gog
[ ] Privacy canary tests passing

SURFACES
[ ] Console loads at http://MAC-IP:3333/
[ ] Scoreboard loads at http://MAC-IP:3333/scoreboard
[ ] Chat works in console

OPS
[ ] HEARTBEAT.md → HEARTBEAT_OK
[ ] Backup created and verified
[ ] Launchd services survive reboot test
[ ] SSH access works from laptop

FAMILY
[ ] James: carousel view, whatNow, rewards working
[ ] Laura: compressed view, decisions queue visible
[ ] Charlie: chore checklist with stars
[ ] Kitchen TV: scoreboard displaying
```
