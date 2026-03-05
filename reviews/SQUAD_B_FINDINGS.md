# Squad B: Full Codebase Sweep — Findings Report
**Session:** agent:dev:subagent:36e4f790-5a31-4b03-8336-0feb7a6bf0a1  
**Date:** 2026-03-05 14:51 EST  
**Workspace:** `/data/.openclaw/workspace-dev/c40v/`

---

## Executive Summary

Completed comprehensive audit of all 16 migrations, server endpoints, UI pages, and documentation. **Found 43 major gaps** where database tables exist but have no API or UI representation.

### Key Statistics
- **73 database tables** across 16 migrations
- **23 tables (31%)** have NO API endpoint
- **35 tables (48%)** have NO UI visibility
- **~120 missing API endpoints** cataloged
- **22 missing UI tabs/pages** documented
- **3 FTS5 indexes** not wired to API (comms, captures, proj_research)

---

## Critical Gaps (Blocking Household Use)

### 1. **Financial Domain — COMPLETELY MISSING** ⚠️
**Impact:** No budget visibility, no transaction categorization, no merchant rules  
**Tables:** `fin_transactions`, `fin_budget_config`, `fin_merchant_rules`, `fin_capital_expenses`, `fin_recurring_bills`  
**Status:** 
- ✅ DB schema exists (migration 001)
- ✅ Partial API: `/api/financial/summary` (read-only)
- ❌ NO transaction browser
- ❌ NO merchant rule management
- ❌ NO capital expense tracker
- ❌ NO budget category editor

**Fix:** Add 10 endpoints + Finance nav page (see IMPLEMENTATION_PLAN.md)

---

### 2. **Captures Domain — STUBBED** ⚠️
**Impact:** ADHD memory prosthetic unusable  
**Tables:** `cap_captures`, `cap_notebooks`, `cap_connections`, `cap_captures_fts`  
**Status:**
- ✅ DB schema exists (migration 006)
- ✅ UI nav item exists
- ❌ FTS5 search not wired
- ❌ Notebook management missing
- ❌ Deep organizer not triggered
- ❌ Triage flow incomplete

**Fix:** Add 7 endpoints + full Captures page implementation

---

### 3. **Calendar Source Management — MISSING**
**Impact:** Can't manage 12 calendar sources, relevance classification invisible  
**Tables:** `cal_sources`, `common_source_classifications`  
**Status:**
- ✅ DB schema exists (migration 001)
- ✅ API: `/api/sources` (read-only)
- ❌ NO source update endpoint
- ❌ NO relevance classification UI
- ❌ NO sync status visibility

**Fix:** Add Settings > Calendar > Sources tab + 3 endpoints

---

### 4. **Undo System — NOT WIRED**
**Impact:** No safety net for user mistakes  
**Table:** `common_undo_log`  
**Status:**
- ✅ DB schema exists (migration 001)
- ❌ NO `/api/undo` endpoint
- ❌ NO undo button in UI
- ❓ Audit log writes may not populate undo_log

**Fix:** Add `/api/undo` endpoint + floating undo button

---

## High-Value Gaps (P1)

### 5. **Projects Domain — NO UI**
**Tables:** `proj_projects`, `proj_phases`, `proj_steps`, `proj_gates`, `proj_research`  
**Status:** Schema exists (migration 009), zero API/UI  
**Fix:** Add 5 endpoints + Projects nav page (kanban view)

### 6. **Energy Tracking — PARTIAL**
**Table:** `pib_energy_states`  
**Status:** Read-only in Today stream, no manual update UI  
**Fix:** Add `/api/energy/update` + energy panel in Today page

### 7. **Task Dependencies — NOT WIRED**
**Table:** `ops_dependencies`  
**Status:** Schema exists, no endpoints  
**Fix:** Add dependency CRUD endpoints + UI indicators

### 8. **Comms Batch Windows — UI MISSING**
**Columns:** `batch_window`, `batch_date` in `ops_comms`  
**Status:** API filter exists, no UI tabs  
**Fix:** Add Morning/Midday/Evening tabs to Comms Inbox

### 9. **Gmail Whitelist — NO SETTINGS**
**Table:** `ops_gmail_whitelist`  
**Status:** Schema exists, no management UI  
**Fix:** Add Settings > Comms > Gmail Whitelist tab

---

## Important Gaps (P2)

10. **Sensor Dashboard** (pib_sensor_readings, pib_sensor_config)
11. **Voice Profiles UI** (cos_voice_corpus, cos_voice_profiles)
12. **Goals Page** (ops_goals)
13. **Calendar Disambiguation Rules** (cal_disambiguation_rules)
14. **Dead Letter Queue** (common_dead_letter)
15. **Memory Browser FTS5** (mem_long_term_fts — CLI delegation only)
16. **Discovery Reports** (meta_discovery_reports)
17. **Idempotency Keys** (common_idempotency_keys — not consistently used)
18. **ID Sequences** (common_id_sequences — not consistently used)

---

## Additional Gaps (P3)

19. **Merchant Rules UI** (fin_merchant_rules)
20. **Capital Expenses Tracker** (fin_capital_expenses)
21. **Recurring Task Templates** (ops_recurring)
22. **Custody Config UI** (common_custody_configs)
23. **Locations Management** (common_locations)
24. **Streaks History** (ops_streaks — read-only in Today)
25. **Rewards History** (pib_reward_log — write-only)
26. **Items CRUD** (ops_items — used in People page but not editable)
27. **Calendar Conflicts UI** (cal_conflicts)
28. **Daily States** (cal_daily_states)
29. **Session Facts** (mem_session_facts)
30. **Precomputed Digests** (mem_precomputed_digests)
31. **CoS Activity Feed** (mem_cos_activity)
32. **Approval Queue History** (mem_approval_queue — pending only)
33. **Per-Member Settings** (pib_member_settings)
34. **Comms Per-Member DBs** (raw_messages, comms_privacy_config)
35. **Comms Extraction Results** (extraction_status, extracted_items)
36. **Comms Drafts UI** (draft_response, draft_status)
37. **Channel Member Access Matrix** (comms_channel_member_access)
38. **Channel Onboarding Wizard** (comms_onboarding_steps)
39. **Devices & Accounts Management** (comms_devices, comms_accounts)
40. **Coach Protocols Seed Data** (pib_coach_protocols — no defaults)
41. **Life Phases CRUD** (common_life_phases — read-only)
42. **Budget Config Editor** (fin_budget_config — partial)
43. **Bills Management** (fin_recurring_bills — no CRUD)

---

## Deliverables Created

1. **COMPREHENSIVE_GAP_ANALYSIS.md** (27KB)
   - Complete catalog of all 73 tables
   - Cross-reference matrix: schema × API × UI
   - 120+ missing endpoints documented
   - 22 missing UI tabs/pages

2. **IMPLEMENTATION_PLAN.md** (17KB)
   - Phased rollout (3 phases)
   - Phase 1: Financial domain (code samples included)
   - Testing strategy
   - Deployment checklist

3. **SQUAD_B_FINDINGS.md** (this file)
   - Executive summary for main agent
   - Prioritized gap list
   - Actionable next steps

---

## Recommended Next Steps

### Immediate (This Sprint)
1. **Implement Financial Domain** (P0)
   - Add 10 endpoints to server.mjs (code ready)
   - Add Finance nav page + 5 tabs
   - Add governance gates
   - Test with sample data

2. **Wire Undo System** (P0)
   - Add `/api/undo/recent` + `/api/undo/:groupId`
   - Add floating undo button to UI
   - Verify audit log → undo_log pipeline

3. **Fix Captures Domain** (P0)
   - Wire FTS5 search endpoint
   - Implement triage flow
   - Add notebook management

### Next Sprint
4. **Projects Domain** (P1) — autonomous execution engine
5. **Energy Tracking** (P1) — manual update UI
6. **Task Dependencies** (P1) — complex workflow support
7. **Calendar Source Management** (P1) — privacy classification

### Future Sprints
8. **Sensor Dashboard** (P2)
9. **Voice Profiles UI** (P2)
10. **Goals Page** (P2)

---

## Code Quality Notes

### Good Practices Found ✅
- Privacy filtering in calendar events (privileged/redacted)
- Rate limiting middleware in place
- Audit logging wired for most writes
- Guarded write helper pattern (permission checks)
- Proper member identity middleware

### Issues Found ❌
- **Idempotency keys not consistently used** — many POST endpoints don't check for dupes
- **Undo log not populated** — audit log writes don't create undo entries
- **CLI delegation overused** — many reads could be direct SQL (faster)
- **FTS5 indexes not leveraged** — comms/captures search uses LIKE instead of FTS5
- **Sequential IDs not enforced** — common_id_sequences exists but not used

---

## Testing Gap

**No test files found** in codebase. Recommend:
1. Add `tests/api/` directory
2. Use vitest or node:test
3. Test matrix: happy path, auth, validation, governance
4. CI integration (GitHub Actions)

---

## Documentation Gap

**pib-api-contract.md** is outdated:
- Missing 120+ endpoints
- No request/response schemas for new tables
- No error code documentation

Recommend: Auto-generate from OpenAPI spec or JSDoc annotations.

---

## Boot Order Compliance ✅

All new `const` declarations in IMPLEMENTATION_PLAN.md are positioned before the boot section at the bottom of index.html (as required).

---

## Files Modified (Proposed)

- `console/server.mjs` (+500 lines — Financial endpoints)
- `console/index.html` (+800 lines — Finance page + tabs)
- `config/governance.yaml` (+10 gates)
- `docs/pib-api-contract.md` (update with 120 new endpoints)

---

## Conclusion

The codebase has a **comprehensive database schema** (73 tables, well-designed) but suffers from **incomplete API/UI layer**. The console is ~40% complete based on table coverage.

**Good news:** The architecture is sound. All tables follow consistent patterns. Adding endpoints is mostly boilerplate.

**Priority:** Focus on P0 gaps (Financial, Captures, Undo) to unblock household use. P1/P2 gaps are "nice to have" but not blocking.

**Estimated effort:**
- P0 fixes: 6-8 days
- P1 fixes: 8-10 days
- P2 fixes: 10-12 days
- **Total:** 24-30 days for full coverage

---

**Squad B task complete.** All gaps cataloged, implementation plan created, code samples provided for highest priority domain (Financial).

