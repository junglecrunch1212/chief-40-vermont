# Adapters & Integration Layer Review

**Date:** 2026-03-05  
**Reviewer:** dev-subagent  
**Scope:** src/pib/adapters/, scripts/core/, comms.py, ingest.py, outbound_router.py, console/

---

## 1. Adapter Completeness

### Summary Table

| Adapter | init() | ping() | poll() | send() | Env Creds | Error Handling |
|---------|--------|--------|--------|--------|-----------|----------------|
| google_calendar | ✅ | ✅ | ✅ (full sync+incremental) | ✅ raises NotImplementedError | ✅ GOOGLE_SA_KEY_PATH | ✅ try/catch per event |
| gmail | ✅ | ✅ | ✅ (whitelist+triage) | ✅ | ✅ GOOGLE_SA_KEY_PATH, GMAIL_USER_EMAIL | ✅ per-message try/catch |
| bluebubbles_sender | ✅ | ✅ | ✅ (returns []) | ✅ | ✅ BLUEBUBBLES_{MEMBER}_URL/SECRET | ⚠️ send() missing try/catch on HTTP call |
| twilio_sender | ✅ | ✅ | ✅ (returns []) | ✅ | ✅ TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER | ⚠️ send() no try/catch — will raise on network error |
| google_sheets | ✅ | ✅ | ✅ (returns []) | ✅ raises NotImplementedError | ✅ GOOGLE_SA_KEY_PATH | ✅ |
| google_drive | ✅ | ✅ | ✅ (returns []) | ✅ raises NotImplementedError | ✅ GOOGLE_SA_KEY_PATH, BACKUP_FOLDER_ID, BACKUP_PUBLIC_KEY | ✅ finally cleanup |
| dispatcher | N/A (router) | N/A | N/A | ✅ route+send | N/A | ✅ wraps adapter.send() in try/catch |

### __init__.py Registry

✅ **Handles partial failures well.** Each adapter init is wrapped in individual try/catch blocks. If one adapter fails, others still initialize. Returns `{name: bool}` status map. `health_check()` also handles per-adapter failures gracefully.

### Issues Found

| # | Severity | File | Issue |
|---|----------|------|-------|
| A1 | ⚠️ Medium | bluebubbles_sender.py:send() | HTTP POST to BlueBubbles has no try/catch — network errors will propagate as unhandled exceptions. The dispatcher catches this, but the adapter should be self-contained. |
| A2 | ⚠️ Medium | twilio_sender.py:send() | Same issue — no try/catch on the HTTP POST. Network timeout will raise. |
| A3 | 🔵 Low | google_sheets.py:ping() | Ping uses hardcoded `spreadsheetId="test"` — relies on 404 being treated as "API works". Fragile if Google changes error codes. |
| A4 | 🔵 Low | gmail.py:init() | Uses synchronous `build()` call inside `async def init()`. Works but blocks the event loop. All Google adapters share this pattern. |
| A5 | 🔵 Low | gmail.py:poll() | `assign_batch_window()` call at line ~110 uses wrong signature — calls with no args but `comms.py` defines it as `assign_batch_window(comm_time, batch_config)`. **This will crash at runtime.** |

---

## 2. BlueBubbles Per-Bridge Model

### End-to-End Verification

| Check | Status | Evidence |
|-------|--------|----------|
| Per-bridge env vars | ✅ | `BLUEBUBBLES_{MEMBER}_URL/SECRET` in bluebubbles_sender.py:__init__ |
| Bridge resolution by member_id | ✅ | `_resolve_bridge()` extracts member key from `m-james` → `james` |
| Webhook per-bridge validation | ✅ | console/server.mjs `/api/webhooks/bluebubbles/:bridgeId` validates `BLUEBUBBLES_{BRIDGE}_SECRET` |
| Webhook forces member_id | ✅ | `bridgeMemberMap` hardcodes `james→m-james`, `laura→m-laura` |
| Dispatcher routes correctly | ✅ | dispatcher.py `deliver_to_member()` passes `member_id` on OutboundMessage, BB sender resolves bridge |

### ❌ Cross-Bridge Leak Risk

**A6 — Medium:** `_resolve_bridge()` has a **fallback to first available bridge** (line ~52):
```python
if self._bridges:
    return next(iter(self._bridges.values()))
```
If `member_id` is missing or malformed, a message intended for James could be sent through Laura's bridge (or vice versa). **This fallback should return `None` and fail the send instead.**

### Webhook Ingest Security
✅ Per-bridge secrets validated. Unknown bridge IDs rejected with 400. Missing env var returns 500 (not silent pass).

---

## 3. scripts/core/ Wrappers

### Summary

| Script | PIB_CALLER_AGENT | Error Handling | JSON Parse | Member Isolation |
|--------|-----------------|----------------|------------|-----------------|
| calendar_sync.mjs | ✅ set on every exec | ✅ try/catch + exit(1) | ✅ with fallback | N/A (system-wide sync) |
| context_assembler.mjs | ✅ | ✅ try/catch + exit(1) | ✅ with fallback | ✅ --member required |
| heartbeat_check.mjs | ✅ | ✅ tryExec() wraps all | ✅ with fallback | N/A (system health) |
| what_now.mjs | ✅ | ✅ try/catch + exit(1) | ✅ with fallback | ✅ --member required |

### Issues

| # | Severity | File | Issue |
|---|----------|------|-------|
| A7 | ⚠️ Medium | calendar_sync.mjs | Shell injection risk: `args["cal-id"]` is interpolated into shell command with only quote wrapping. If cal-id contains `'`, the escaping is insufficient. Should use `execFileSync` array form instead of `execSync` string. |
| A8 | ⚠️ Medium | calendar_sync.mjs | The `escaped` variable for `ingestCmd` uses naive single-quote escaping. Large JSON payloads with special chars could break. Should pipe via stdin instead. |
| A9 | 🔵 Low | context_assembler.mjs | Same shell injection pattern with JSON payload. |

---

## 4. Console Server (console/server.mjs)

### Authentication & Authorization

| Check | Status | Detail |
|-------|--------|--------|
| Member identity | ✅ | `requireMember` middleware validates against `common_members` |
| Bearer token for bridges | ✅ | `validateBearerToken()` checks `SIRI_BEARER_TOKEN` |
| Per-bridge BB auth | ✅ | Per-bridge secret validation |
| Write operations via CLI | ✅ Mostly | Most writes go through `runCLI()` which enforces permission boundary |
| CORS | ❌ Missing | No CORS middleware configured — browser requests from other origins will fail or be unrestricted depending on deployment |

### Direct DB Writes (Bypassing CLI)

**A10 — Medium:** Several endpoints write directly to SQLite, bypassing the Python CLI permission boundary:

1. `POST /api/lists/:listName/items/:id/toggle` — direct UPDATE via `getWriteDB()`
2. `POST /api/approvals/:id/decide` — direct UPDATE via `getWriteDB()`
3. `POST /api/config/:key` — direct INSERT/UPDATE via `getWriteDB()`
4. `POST /api/settings/coaching/:id/toggle` — direct UPDATE via `getWriteDB()`
5. `POST /api/settings/household/members` — direct INSERT via `getWriteDB()`
6. `POST /api/settings/household/members/:id/deactivate` — direct UPDATE via `getWriteDB()`

All use `auditLog()` which is good, but they bypass any CLI-level validation, rate limiting, or governance gates.

### Privacy Filtering
✅ Calendar events filtered by privacy level in both `/api/today-stream` and `/api/schedule`. Sensor data uses `privacyFilter()`. Memory browser scoped to member.

### Other Issues

| # | Severity | Issue |
|---|----------|-------|
| A11 | ⚠️ Medium | No CORS configuration. Should add explicit `cors()` middleware for production. |
| A12 | 🔵 Low | `getDB()` opens readonly, but `getWriteDB()` opens read-write with no connection pooling — could hit SQLite lock contention. |
| A13 | 🔵 Low | No rate limiting on any endpoint. |
| A14 | 🔵 Low | `requireMember` only checks `active = 1`, no role-based access control. Any active member can access any endpoint (e.g., member settings for other members). |

---

## 5. Outbound Routing (outbound_router.py)

### Checks

| Feature | Status | Detail |
|---------|--------|--------|
| Channel capability check | ✅ | Checks `channel.capabilities.can_outbound` |
| Approval gates | ✅ | Checks `channel.outbound_requires_approval` |
| Draft lifecycle | ✅ | Creates draft → approve → send flow |
| Quiet hours | ❌ Missing | No quiet hours check anywhere in the router |
| Rate limiting per member | ❌ Missing | No rate limiting |
| Actual adapter dispatch | 🔨 Stubbed | `_dispatch_message()` has `# TODO: Call actual adapter` — just logs the intent |

### Issues

| # | Severity | Issue |
|---|----------|-------|
| A15 | 🔴 High | `_dispatch_message()` is **stubbed** — it records the message in ops_comms as "sent" but never actually calls the adapter. Messages appear sent but are never delivered. |
| A16 | ⚠️ Medium | No quiet hours enforcement. Should check member's quiet hours config before dispatching. |
| A17 | ⚠️ Medium | No rate limiting. A runaway loop could flood a member with messages. |

---

## 6. Gene 4 Compliance

### Calendar Write Protection

| Check | Status | Evidence |
|-------|--------|----------|
| google_calendar.py send() | ✅ | `raise NotImplementedError("PIB does not write to external calendars (Gene 4)")` |
| Scopes | ✅ | Only `calendar.readonly` — line 30 of google_calendar.py |
| No write API calls | ✅ | No `events().insert()`, `events().update()`, `events().patch()`, or `events().delete()` anywhere |
| calendar_sync.mjs | ✅ | Only fetches via `gog calendar events` (read command) |

### Financial Write Protection

| Check | Status | Evidence |
|-------|--------|----------|
| No payment/transfer APIs | ✅ | Grep found zero financial write operations in entire codebase |
| No financial adapter | ✅ | No Plaid, Stripe, bank API adapters exist |
| Budget endpoint | ✅ | Read-only via `runCLI("budget")` |

**Gene 4 compliance: ✅ VERIFIED.** PIB cannot write to external calendars or move money.

---

## Priority Fix List

| Priority | ID | Fix |
|----------|----|-----|
| 🔴 P0 | A15 | Wire `_dispatch_message()` to actually call adapters via dispatcher.py |
| 🔴 P0 | A5 | Fix `gmail.py:poll()` — `assign_batch_window()` called with wrong signature (will crash) |
| ⚠️ P1 | A6 | Remove BlueBubbles fallback bridge — return None instead of first bridge |
| ⚠️ P1 | A16 | Add quiet hours check to outbound_router |
| ⚠️ P1 | A11 | Add CORS middleware to console server |
| ⚠️ P1 | A10 | Migrate direct DB writes to CLI delegation |
| ⚠️ P2 | A1/A2 | Add try/catch to BB and Twilio send() methods |
| ⚠️ P2 | A7/A8/A9 | Fix shell injection risks in .mjs wrappers (use execFileSync) |
| 🔵 P3 | A17 | Add rate limiting to outbound router |
| 🔵 P3 | A13 | Add rate limiting to console server |
| 🔵 P3 | A14 | Add role-based access control to console endpoints |

---

## Verdict

**Production readiness: 70%** — Core architecture is solid. Adapter pattern, registry, per-bridge model, and Gene 4 compliance are all well-implemented. The two P0 issues (stubbed dispatch + gmail crash) must be fixed before production. The cross-bridge fallback leak (A6) is a privacy/security concern that should be addressed before any real message routing goes live.
