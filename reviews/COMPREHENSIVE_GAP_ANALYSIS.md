# PIB v5 Console — Comprehensive Gap Analysis
**Date:** 2026-03-05  
**Scope:** Full codebase sweep for missing endpoints, UI features, and data representations

## Executive Summary

This document catalogs **every gap** between:
- Database schema (16 migrations)
- API endpoints (server.mjs + route files)
- Console UI (index.html)
- Spec documents (pib-v5-build-spec.md, pib-api-contract.md)

---

## 🔴 Critical Gaps (No API or UI)

### 1. **Financial Domain** (fin_* tables)
**Tables:** `fin_transactions`, `fin_budget_config`, `fin_merchant_rules`, `fin_capital_expenses`, `fin_recurring_bills`, `fin_budget_snapshot`

**Status:**
- ✅ API: `/api/budget` (CLI delegation)
- ✅ API: `/api/financial/summary` (partial — categories, bills, transactions)
- ❌ UI: No financial page in nav
- ❌ UI: No transaction browser
- ❌ UI: No merchant rule management
- ❌ UI: No capital expense tracker
- ❌ API: No `/api/transactions` endpoint
- ❌ API: No `/api/transactions/:id` detail endpoint
- ❌ API: No transaction categorization endpoint
- ❌ API: No merchant rule CRUD
- ❌ API: No capital expense CRUD

**Fixes Needed:**
1. Add `/api/financial/transactions` (GET with filters: date range, category, merchant)
2. Add `/api/financial/transactions/:id` (GET single transaction)
3. Add `/api/financial/transactions/:id/categorize` (POST update category)
4. Add `/api/financial/merchant-rules` (GET/POST/PATCH/DELETE)
5. Add `/api/financial/capital-expenses` (GET/POST/PATCH)
6. Add `/api/financial/bills` (GET/POST/PATCH for recurring bills)
7. Add "Finance" tab to nav (icon: dollar-sign)
8. Implement Finance page with tabs: Transactions, Budget, Bills, Merchant Rules, Capital Expenses

---

### 2. **Calendar Source Classifications** (cal_sources + common_source_classifications)
**Tables:** `cal_sources`, `common_source_classifications`

**Status:**
- ✅ API: `/api/sources` (read-only list)
- ✅ API: `/api/schedule` (calendar events)
- ❌ UI: No calendar source management in Settings
- ❌ UI: Calendar source relevance (blocks_member, blocks_household, etc.) not visible
- ❌ API: No `/api/sources/:id/update` endpoint
- ❌ API: No `/api/calendar/sources` specific endpoint

**Fixes Needed:**
1. Add Settings > Calendar > Sources tab
2. Show calendar source relevance classification in UI
3. Add `/api/calendar/sources` (GET list with sync status)
4. Add `/api/calendar/sources/:id` (GET/PATCH for classification updates)
5. Show sync_token, last_synced in UI for troubleshooting

---

### 3. **Memory Browser with FTS5** (mem_long_term + mem_long_term_fts)
**Tables:** `mem_long_term`, `mem_long_term_fts`

**Status:**
- ✅ API: `/api/settings/memory` (basic read + CLI search delegation)
- ✅ UI: Settings > Memory tab exists
- ❌ UI: FTS5 search not wired (uses CLI delegation)
- ❌ API: No direct FTS5 query endpoint
- ❌ UI: No memory detail modal
- ❌ UI: No memory edit/delete UI
- ❌ UI: No `superseded_by` chain visualization

**Fixes Needed:**
1. Add `/api/memory/search` (POST with FTS5 query, rank by relevance)
2. Add `/api/memory/:id` (GET detail with supersession chain)
3. Add `/api/memory/:id/supersede` (POST to mark superseded)
4. Wire FTS5 search in Settings > Memory tab (replace CLI delegation)
5. Add memory detail modal with edit/supersede options

---

### 4. **Energy States** (pib_energy_states)
**Table:** `pib_energy_states`

**Status:**
- ✅ API: Partial — read in `/api/today-stream`
- ✅ API: Write in task completion (inline update)
- ❌ UI: No dedicated energy tracking page
- ❌ API: No `/api/energy` standalone endpoint
- ❌ API: No `/api/energy/:memberId/history` endpoint
- ❌ UI: No energy level manual update UI
- ❌ UI: No sleep quality selector
- ❌ UI: No focus mode toggle

**Fixes Needed:**
1. Add `/api/energy` (GET current state for member)
2. Add `/api/energy/history` (GET time series for charts)
3. Add `/api/energy/update` (POST manual updates: energy_level, sleep_quality, focus_mode)
4. Add Energy tab to Today page (James carousel)
5. Add energy chart to Scoreboard

---

### 5. **Sensor Readings** (pib_sensor_readings + pib_sensor_config)
**Tables:** `pib_sensor_readings`, `pib_sensor_config`, `pib_sensor_alerts`

**Status:**
- ✅ API: `/api/sensors` (GET with privacy filter)
- ✅ API: `/api/sensors/ingest` (POST from bridges)
- ❌ UI: No sensor dashboard
- ❌ UI: No sensor config management
- ❌ API: No `/api/sensors/config` endpoint
- ❌ API: No `/api/sensors/alerts` endpoint
- ❌ UI: No sensor readings visualizations

**Fixes Needed:**
1. Add `/api/sensors/config` (GET/PATCH sensor configuration)
2. Add `/api/sensors/alerts` (GET active alerts)
3. Add `/api/sensors/:id/readings` (GET time series for one sensor)
4. Add Settings > Sensors tab with config management
5. Add sensor dashboard page (optional nav item)

---

### 6. **Discovery Reports** (meta_discovery_reports)
**Table:** `meta_discovery_reports`

**Status:**
- ❌ API: No endpoint
- ❌ UI: No visibility

**Fixes Needed:**
1. Add `/api/discovery/reports` (GET pending reports)
2. Add `/api/discovery/reports/:id/confirm` (POST confirm discovery)
3. Add Settings > Discovery tab
4. Show pending discoveries in settings with approve/reject UI

---

### 7. **ID Sequences** (common_id_sequences)
**Table:** `common_id_sequences`

**Status:**
- ✅ DB: Table exists
- ❌ API: No read endpoint
- ❌ UI: No visibility
- ❓ Usage: Not consistently used for new records (needs audit)

**Fixes Needed:**
1. Add `/api/admin/sequences` (GET list for debugging)
2. Audit all create endpoints to use sequential IDs
3. Add Settings > Admin > Sequences (read-only debug view)

---

### 8. **Undo Log** (common_undo_log)
**Table:** `common_undo_log`

**Status:**
- ✅ DB: Table exists
- ❌ API: No undo endpoint
- ❌ UI: No undo button anywhere
- ❌ API: No `/api/undo` endpoint

**Fixes Needed:**
1. Add `/api/undo/recent` (GET last 10 undoable actions)
2. Add `/api/undo/:groupId` (POST perform undo)
3. Add undo button to UI (floating action or in nav)
4. Wire audit log writes to populate undo_log

---

### 9. **Dead Letter Queue** (common_dead_letter)
**Table:** `common_dead_letter`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No visibility

**Fixes Needed:**
1. Add `/api/admin/dead-letter` (GET list of failed operations)
2. Add `/api/admin/dead-letter/:id/retry` (POST manual retry)
3. Add `/api/admin/dead-letter/:id/resolve` (POST mark resolved)
4. Add Settings > Admin > Dead Letter Queue

---

### 10. **Idempotency Keys** (common_idempotency_keys)
**Table:** `common_idempotency_keys`

**Status:**
- ✅ DB: Table exists
- ❌ Usage: Not consistently used in write endpoints
- ❌ API: No read endpoint

**Fixes Needed:**
1. Audit all write endpoints to use idempotency keys
2. Add `/api/admin/idempotency` (GET recent keys for debugging)
3. Document idempotency key generation in API contract

---

### 11. **Task Dependencies** (ops_dependencies)
**Table:** `ops_dependencies`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No dependency visualization

**Fixes Needed:**
1. Add `/api/tasks/:id/dependencies` (GET blocked/blocking tasks)
2. Add `/api/tasks/:id/dependencies` (POST add dependency)
3. Add `/api/tasks/dependencies/:id` (DELETE remove dependency)
4. Add dependency indicator in task list UI
5. Add dependency graph visualization (optional advanced feature)

---

### 12. **Gmail Whitelist** (ops_gmail_whitelist)
**Table:** `ops_gmail_whitelist`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No settings management

**Fixes Needed:**
1. Add `/api/settings/gmail-whitelist` (GET/POST/DELETE)
2. Add Settings > Comms > Gmail Whitelist tab
3. Show match_type (items_email, domain, explicit_address) in UI
4. Add pattern tester (dry-run match check)

---

### 13. **Calendar Disambiguation Rules** (cal_disambiguation_rules)
**Table:** `cal_disambiguation_rules`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No settings management

**Fixes Needed:**
1. Add `/api/calendar/disambiguation-rules` (GET/POST/PATCH/DELETE)
2. Add Settings > Calendar > Disambiguation tab
3. Show pattern, match_field, resolved_type in UI
4. Add rule priority management

---

### 14. **Voice Intelligence** (cos_voice_corpus + cos_voice_profiles)
**Tables:** `cos_voice_corpus`, `cos_voice_profiles` (migration 004)

**Status:**
- ✅ DB: Tables exist
- ❌ API: No endpoints
- ❌ UI: No visibility

**Fixes Needed:**
1. Add `/api/voice/corpus` (GET sample count, recent samples)
2. Add `/api/voice/profiles` (GET voice profiles for member)
3. Add `/api/voice/rebuild` (POST trigger profile rebuild)
4. Add Settings > Comms > Voice Profiles tab
5. Show sample count, confidence, last rebuilt in UI

---

### 15. **Projects** (proj_* tables from migration 009)
**Tables:** `proj_projects`, `proj_phases`, `proj_steps`, `proj_gates`, `proj_research`, `proj_research_fts`

**Status:**
- ✅ DB: Tables exist
- ❌ API: No endpoints
- ❌ UI: No project view

**Fixes Needed:**
1. Add `/api/projects` (GET list with status filter)
2. Add `/api/projects/:id` (GET detail with phases/steps/gates)
3. Add `/api/projects` (POST create new project)
4. Add `/api/projects/:id/phases/:phaseId/steps/:stepId/complete` (POST)
5. Add `/api/projects/:id/gates/:gateId/decide` (POST approve/reject)
6. Add Projects page to nav (icon: briefcase)
7. Implement project kanban view (planning → active → completed)
8. Add project detail modal with phase/step tree

---

### 16. **Capture Domain** (cap_* tables from migration 006)
**Tables:** `cap_captures`, `cap_notebooks`, `cap_connections`, `cap_captures_fts`

**Status:**
- ✅ DB: Tables exist
- ❌ API: Partial — CLI delegation only
- ✅ UI: Captures nav item exists (stubbed)
- ❌ API: No direct FTS5 search endpoint
- ❌ API: No notebook management
- ❌ API: No connection management
- ❌ UI: Captures page not fully implemented

**Fixes Needed:**
1. Add `/api/captures` (GET with filters: notebook, type, tag)
2. Add `/api/captures/search` (POST FTS5 search)
3. Add `/api/captures/:id` (GET/PATCH/DELETE)
4. Add `/api/captures/:id/organize` (POST trigger deep organizer)
5. Add `/api/notebooks` (GET/POST/PATCH/DELETE)
6. Add `/api/captures/:id/connections` (GET/POST/DELETE)
7. Wire Captures page UI (browse, search, triage, organize)
8. Add recipe view for capture_type=recipe

---

### 17. **Comms Batch Windows** (ops_comms columns from migration 003)
**Columns:** `batch_window`, `batch_date`, `extraction_status`, `draft_status`, `snoozed_until`

**Status:**
- ✅ API: `/api/comms/inbox` supports batch_window filter
- ❌ UI: Batch window selector not visible in Comms Inbox
- ❌ UI: No batch window config in settings

**Fixes Needed:**
1. Add batch window tabs to Comms Inbox (Morning, Midday, Evening)
2. Show batch_date, batch_window in comm detail
3. Add Settings > Comms > Batch Windows (edit start/end times)

---

### 18. **Comms Extraction** (ops_comms columns)
**Columns:** `extraction_status`, `extracted_items`, `extraction_confidence`

**Status:**
- ✅ DB: Columns exist
- ❌ API: No extraction endpoint
- ❌ UI: No extraction results visibility

**Fixes Needed:**
1. Add `/api/comms/:id/extract` (POST trigger extraction)
2. Add `/api/comms/:id/extraction` (GET extraction results)
3. Show extracted_items in comm detail modal
4. Add approve/reject extracted items UI

---

### 19. **Comms Drafts** (ops_comms columns)
**Columns:** `draft_response`, `draft_status`, `draft_voice_profile_id`

**Status:**
- ✅ API: `/api/comms/:id/approve`, `/api/comms/:id/reject` exist
- ❌ UI: Draft status not shown in inbox list
- ❌ UI: No draft editing UI

**Fixes Needed:**
1. Add draft indicator (badge) in comms inbox
2. Add draft editing modal (textarea with approve/reject buttons)
3. Show voice_profile_id used for draft in detail

---

### 20. **Channel Member Access** (comms_channel_member_access)
**Table:** `comms_channel_member_access`

**Status:**
- ✅ API: `/api/channels/member/:memberId` exists
- ✅ API: `/api/channels/:id/access` (POST grant)
- ❌ UI: No channel access management in settings
- ❌ UI: No per-member channel visibility toggle

**Fixes Needed:**
1. Add Settings > Channels > Member Access tab
2. Show matrix: members × channels with access_level
3. Add batch_window preference selector per member per channel
4. Add can_approve_drafts toggle

---

### 21. **Channel Onboarding** (comms_onboarding_steps)
**Table:** `comms_onboarding_steps`

**Status:**
- ✅ API: `/api/channels/:id/onboarding/:stepKey/complete` exists
- ❌ UI: No onboarding wizard
- ❌ Seed: No onboarding steps seeded for default channels

**Fixes Needed:**
1. Seed onboarding steps for each channel in migration 014
2. Add channel setup wizard UI (modal with steps)
3. Show onboarding progress in Settings > Channels

---

### 22. **Devices & Accounts** (comms_devices, comms_accounts)
**Tables:** `comms_devices`, `comms_accounts`

**Status:**
- ✅ API: `/api/devices` (GET)
- ✅ API: `/api/accounts` (GET)
- ❌ UI: No device/account management
- ❌ API: No device/account CRUD

**Fixes Needed:**
1. Add Settings > Channels > Devices tab
2. Add Settings > Channels > Accounts tab
3. Add `/api/devices` (POST/PATCH/DELETE)
4. Add `/api/accounts` (POST/PATCH/DELETE)
5. Show device status, last_seen_at in UI

---

### 23. **Coach Protocols** (pib_coach_protocols)
**Table:** `pib_coach_protocols`

**Status:**
- ✅ API: `/api/settings/coaching` (GET)
- ✅ API: `/api/settings/coaching/:id/toggle` (POST)
- ✅ UI: Settings > Coaching tab exists
- ❌ Seed: No default protocols seeded
- ❌ UI: Protocol examples not shown

**Fixes Needed:**
1. Seed default coach protocols in migration or seed file
2. Show protocol examples in UI (expandable)
3. Add protocol add/edit UI (admin only)

---

### 24. **Life Phases** (common_life_phases)
**Table:** `common_life_phases`

**Status:**
- ✅ API: `/api/phases` (GET)
- ✅ UI: Settings > Life Phases tab exists
- ❌ API: No life phase CRUD
- ❌ UI: No add/edit phase UI

**Fixes Needed:**
1. Add `/api/phases` (POST/PATCH/DELETE)
2. Add life phase add/edit modal in settings
3. Show active phase indicator in Today page

---

### 25. **Custody Configs** (common_custody_configs)
**Table:** `common_custody_configs`

**Status:**
- ✅ API: `/api/custody/today` (CLI delegation)
- ❌ API: No custody config management
- ❌ UI: No custody settings

**Fixes Needed:**
1. Add `/api/custody/configs` (GET/POST/PATCH/DELETE)
2. Add Settings > Household > Custody tab
3. Show schedule_type, transition details in UI
4. Add holiday override editor

---

### 26. **Locations** (common_locations)
**Table:** `common_locations`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No location management

**Fixes Needed:**
1. Add `/api/locations` (GET/POST/PATCH/DELETE)
2. Add Settings > Household > Locations tab
3. Show travel_times in UI
4. Add map integration (optional)

---

### 27. **Recurring Tasks** (ops_recurring)
**Table:** `ops_recurring`

**Status:**
- ✅ DB: Table exists
- ❌ API: No direct recurring endpoint (CLI only)
- ❌ UI: No recurring task management

**Fixes Needed:**
1. Add `/api/recurring` (GET/POST/PATCH/DELETE)
2. Add Settings > Tasks > Recurring tab
3. Show next_due, frequency in UI
4. Add recurring task template editor

---

### 28. **Streaks** (ops_streaks)
**Table:** `ops_streaks`

**Status:**
- ✅ API: Read in `/api/today-stream`
- ✅ API: Write in task completion
- ❌ API: No standalone streak endpoint
- ❌ UI: Streak visualization incomplete

**Fixes Needed:**
1. Add `/api/streaks/:memberId` (GET with history)
2. Add streak chart to Scoreboard
3. Show grace days used in UI

---

### 29. **Rewards** (pib_reward_log)
**Table:** `pib_reward_log`

**Status:**
- ✅ API: Write in task completion
- ❌ API: No read endpoint
- ❌ UI: No reward history

**Fixes Needed:**
1. Add `/api/rewards/:memberId` (GET recent rewards)
2. Add Scoreboard > Rewards tab
3. Show reward tier distribution chart

---

### 30. **Goals** (ops_goals)
**Table:** `ops_goals`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No goals page

**Fixes Needed:**
1. Add `/api/goals` (GET/POST/PATCH/DELETE)
2. Add Goals page to nav (icon: target)
3. Show progress_metric, progress_current/target in UI
4. Link tasks to goals (goal_ref column)

---

### 31. **Items** (ops_items)
**Table:** `ops_items`

**Status:**
- ✅ DB: Table exists (contacts, vendors, assets)
- ❌ API: No dedicated items endpoint
- ❌ UI: Items used in People page but not manageable

**Fixes Needed:**
1. Add `/api/items` (GET with type filter)
2. Add `/api/items/:id` (GET/PATCH/DELETE)
3. Add `/api/items` (POST create)
4. Add People > Contacts CRUD UI
5. Add Settings > Assets tab for asset tracking

---

### 32. **Capital Expenses** (fin_capital_expenses)
**Table:** `fin_capital_expenses`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No visibility

**Fixes Needed:**
1. Add `/api/financial/capital-expenses` (GET/POST/PATCH)
2. Add Finance > Capital Expenses tab
3. Show target_amount, accumulated, monthly_contribution
4. Add progress bar visualization

---

### 33. **Budget Config** (fin_budget_config)
**Table:** `fin_budget_config`

**Status:**
- ✅ API: Read in `/api/financial/summary`
- ❌ API: No budget config CRUD
- ❌ UI: Budget categories in summary but not editable

**Fixes Needed:**
1. Add `/api/financial/budget` (POST/PATCH category targets)
2. Add Finance > Budget tab with editable targets
3. Show is_fixed, is_discretionary flags
4. Add alert_threshold slider

---

### 34. **Merchant Rules** (fin_merchant_rules)
**Table:** `fin_merchant_rules`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No visibility

**Fixes Needed:**
1. Add `/api/financial/merchant-rules` (GET/POST/PATCH/DELETE)
2. Add Finance > Merchant Rules tab
3. Show pattern, match_type, priority
4. Add rule tester (dry-run categorization)

---

### 35. **Daily States** (cal_daily_states)
**Table:** `cal_daily_states`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No visibility

**Fixes Needed:**
1. Add `/api/calendar/daily-states/:date` (GET precomputed state)
2. Show complexity_score, coverage_status in Schedule page
3. Add daily state timeline visualization (optional)

---

### 36. **Calendar Conflicts** (cal_conflicts)
**Table:** `cal_conflicts`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No conflict alerts

**Fixes Needed:**
1. Add `/api/calendar/conflicts` (GET unresolved)
2. Add conflict banner in Schedule page
3. Add `/api/calendar/conflicts/:id/resolve` (POST with resolution)

---

### 37. **Session Facts** (mem_session_facts)
**Table:** `mem_session_facts`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No visibility

**Fixes Needed:**
1. Add `/api/chat/facts` (GET recent session facts)
2. Show session facts in Chat page sidebar
3. Add promote-to-long-term button

---

### 38. **Precomputed Digests** (mem_precomputed_digests)
**Table:** `mem_precomputed_digests`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No digest preview

**Fixes Needed:**
1. Add `/api/digests/:memberId/:date` (GET precomputed digest)
2. Add digest preview modal
3. Add `/api/digests/:id/deliver` (POST mark delivered)

---

### 39. **CoS Activity Log** (mem_cos_activity)
**Table:** `mem_cos_activity`

**Status:**
- ✅ DB: Table exists
- ❌ API: No endpoint
- ❌ UI: No activity feed

**Fixes Needed:**
1. Add `/api/activity` (GET recent CoS actions)
2. Add activity feed to Today page or sidebar
3. Show entity links (task, comm, etc.)

---

### 40. **Approval Queue** (mem_approval_queue)
**Table:** `mem_approval_queue`

**Status:**
- ✅ API: `/api/decisions` (GET pending)
- ✅ API: `/api/approvals/:id/decide` (POST)
- ✅ UI: Laura's view has Decisions
- ❌ UI: No approval history view
- ❌ UI: No auto-expire notifications

**Fixes Needed:**
1. Add approval history tab
2. Show auto_expire_at countdown
3. Add expiry notification banner

---

### 41. **Per-Member Settings** (pib_member_settings from migration 015)
**Table:** `pib_member_settings`

**Status:**
- ✅ API: `/api/member-settings` (GET/POST via CLI)
- ❌ UI: No dedicated per-member settings tab

**Fixes Needed:**
1. Add Settings > My Preferences tab
2. Show velocity_cap, digest_mode, view_mode as editable
3. Wire to pib_member_settings table

---

### 42. **Comms Per-Member Databases** (raw_messages, comms_privacy_config from migration 008)
**Tables:** `raw_messages`, `comms_privacy_config` (in separate DBs)

**Status:**
- ✅ DB: Schema exists
- ❌ API: No bridge to per-member DBs
- ❌ UI: No raw message browser

**Fixes Needed:**
1. Add `/api/comms/raw/:memberId` (GET raw messages)
2. Add privacy fence enforcement (read own DB only)
3. Add Settings > Privacy > My Messages tab

---

### 43. **Comms FTS5** (comms_fts from migration 011)
**Table:** `comms_fts`

**Status:**
- ✅ DB: FTS5 index exists
- ❌ API: Search not wired to FTS5
- ❌ UI: Comms search uses simple LIKE, not FTS5

**Fixes Needed:**
1. Replace comms inbox search with FTS5 query
2. Add rank-based sorting
3. Add search highlighting

---

---

## 📋 API Gaps Summary

### Missing Endpoints by Domain

#### Financial
- `GET /api/financial/transactions`
- `GET /api/financial/transactions/:id`
- `POST /api/financial/transactions/:id/categorize`
- `GET /api/financial/merchant-rules`
- `POST /api/financial/merchant-rules`
- `PATCH /api/financial/merchant-rules/:id`
- `DELETE /api/financial/merchant-rules/:id`
- `GET /api/financial/capital-expenses`
- `POST /api/financial/capital-expenses`
- `PATCH /api/financial/capital-expenses/:id`
- `GET /api/financial/bills`
- `POST /api/financial/bills`
- `PATCH /api/financial/bills/:id`
- `POST /api/financial/budget` (update category targets)

#### Calendar
- `GET /api/calendar/sources`
- `GET /api/calendar/sources/:id`
- `PATCH /api/calendar/sources/:id`
- `GET /api/calendar/disambiguation-rules`
- `POST /api/calendar/disambiguation-rules`
- `PATCH /api/calendar/disambiguation-rules/:id`
- `DELETE /api/calendar/disambiguation-rules/:id`
- `GET /api/calendar/daily-states/:date`
- `GET /api/calendar/conflicts`
- `POST /api/calendar/conflicts/:id/resolve`

#### Memory
- `POST /api/memory/search` (FTS5 direct)
- `GET /api/memory/:id`
- `POST /api/memory/:id/supersede`
- `PATCH /api/memory/:id`

#### Energy
- `GET /api/energy`
- `GET /api/energy/history`
- `POST /api/energy/update`

#### Sensors
- `GET /api/sensors/config`
- `PATCH /api/sensors/config/:id`
- `GET /api/sensors/alerts`
- `GET /api/sensors/:id/readings`

#### Projects
- `GET /api/projects`
- `GET /api/projects/:id`
- `POST /api/projects`
- `POST /api/projects/:id/phases/:phaseId/steps/:stepId/complete`
- `POST /api/projects/:id/gates/:gateId/decide`

#### Captures
- `GET /api/captures`
- `POST /api/captures/search` (FTS5)
- `GET /api/captures/:id`
- `PATCH /api/captures/:id`
- `DELETE /api/captures/:id`
- `POST /api/captures/:id/organize`
- `GET /api/notebooks`
- `POST /api/notebooks`
- `PATCH /api/notebooks/:id`
- `DELETE /api/notebooks/:id`
- `GET /api/captures/:id/connections`
- `POST /api/captures/:id/connections`
- `DELETE /api/captures/:id/connections/:connId`

#### Tasks
- `GET /api/tasks/:id/dependencies`
- `POST /api/tasks/:id/dependencies`
- `DELETE /api/tasks/dependencies/:id`
- `GET /api/recurring`
- `POST /api/recurring`
- `PATCH /api/recurring/:id`
- `DELETE /api/recurring/:id`

#### Goals
- `GET /api/goals`
- `POST /api/goals`
- `PATCH /api/goals/:id`
- `DELETE /api/goals/:id`

#### Items
- `GET /api/items`
- `GET /api/items/:id`
- `POST /api/items`
- `PATCH /api/items/:id`
- `DELETE /api/items/:id`

#### Voice
- `GET /api/voice/corpus`
- `GET /api/voice/profiles`
- `POST /api/voice/rebuild`

#### Admin
- `GET /api/admin/sequences`
- `GET /api/admin/dead-letter`
- `POST /api/admin/dead-letter/:id/retry`
- `POST /api/admin/dead-letter/:id/resolve`
- `GET /api/admin/idempotency`
- `GET /api/undo/recent`
- `POST /api/undo/:groupId`
- `GET /api/activity`

#### Discovery
- `GET /api/discovery/reports`
- `POST /api/discovery/reports/:id/confirm`

#### Comms Extraction
- `POST /api/comms/:id/extract`
- `GET /api/comms/:id/extraction`

#### Custody
- `GET /api/custody/configs`
- `POST /api/custody/configs`
- `PATCH /api/custody/configs/:id`
- `DELETE /api/custody/configs/:id`

#### Locations
- `GET /api/locations`
- `POST /api/locations`
- `PATCH /api/locations/:id`
- `DELETE /api/locations/:id`

#### Streaks & Rewards
- `GET /api/streaks/:memberId`
- `GET /api/rewards/:memberId`

---

## 🎨 UI Gaps Summary

### Missing Pages
1. **Finance** (nav item + full page)
   - Tabs: Transactions, Budget, Bills, Merchant Rules, Capital Expenses
2. **Projects** (nav item + kanban view)
3. **Goals** (nav item + progress tracker)

### Missing Settings Tabs
1. **Calendar > Sources**
2. **Calendar > Disambiguation Rules**
3. **Comms > Batch Windows** (config editor)
4. **Comms > Gmail Whitelist**
5. **Comms > Voice Profiles**
6. **Channels > Devices**
7. **Channels > Accounts**
8. **Channels > Member Access** (matrix view)
9. **Channels > Onboarding** (wizard)
10. **Sensors** (config management)
11. **Discovery** (pending reports)
12. **Tasks > Recurring**
13. **Household > Custody**
14. **Household > Locations**
15. **Admin > Sequences**
16. **Admin > Dead Letter Queue**
17. **Admin > Idempotency Keys**
18. **Privacy > My Messages** (per-member raw messages)
19. **My Preferences** (per-member settings)

### Missing UI Features
1. **Today page:** Energy chart, life phase indicator
2. **Tasks page:** Dependency indicators, recurring task template view
3. **Schedule page:** Conflict banner, complexity score
4. **Lists page:** Working (exists)
5. **Comms page:** Batch window tabs, draft editing modal, extraction results
6. **Captures page:** Not fully implemented
7. **Chat page:** Session facts sidebar
8. **Scoreboard page:** Streak chart, reward history
9. **People page:** Contact CRUD, asset tracking
10. **Settings page:** 19 missing tabs (see above)
11. **Undo button:** Floating action or nav item
12. **Activity feed:** CoS recent actions

---

## 🔧 Implementation Priority

### P0 (Blocking Household Use)
1. **Financial endpoints + UI** — budget visibility critical
2. **Captures full implementation** — ADHD memory prosthetic core feature
3. **Calendar source management** — privacy/relevance classification
4. **Undo endpoint + UI** — safety net for mistakes

### P1 (High Value)
1. **Projects endpoints + UI** — autonomous execution engine
2. **Energy tracking** — burnout prevention
3. **Task dependencies** — complex workflow support
4. **Comms batch windows UI** — batch processing visibility
5. **Gmail whitelist settings** — reduce noise

### P2 (Important)
1. **Sensor dashboard** — environmental intelligence
2. **Voice profiles UI** — draft quality insights
3. **Goals page** — long-term tracking
4. **Calendar disambiguation rules** — classification accuracy
5. **Dead letter queue** — operational visibility

### P3 (Nice to Have)
1. **Merchant rules UI** — auto-categorization tuning
2. **Capital expenses tracker** — financial planning
3. **Recurring task templates** — task automation
4. **Custody config UI** — schedule complexity
5. **Admin debug views** — sequences, idempotency, activity

---

## 📊 Metrics

- **Total DB tables:** 73
- **Tables with no API endpoint:** 23 (31%)
- **Tables with no UI:** 35 (48%)
- **Missing API endpoints:** ~120
- **Missing UI tabs/pages:** 22
- **FTS5 indexes not wired to API:** 3 (comms, captures, proj_research)

---

## Next Steps

1. **Squad assignment:** Split implementation across 3 squads (Financial, Intelligence, Operations)
2. **API-first:** Implement all missing endpoints before UI
3. **Test coverage:** Add endpoint tests for each new route
4. **Documentation:** Update pib-api-contract.md with all new endpoints
5. **Seed data:** Populate defaults for protocols, onboarding steps, rules
6. **Boot order:** Ensure all new `const` declarations in index.html come before boot section

