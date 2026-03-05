# Hub+Spoke Infrastructure Architecture Review

> **Date:** 2026-03-05 · **Reviewer:** Subagent (infra-arch) · **Codebase:** c40v (PIB v5)

---

## 1. Credential Isolation

### ✅ PASS — Hub credentials properly scoped
- `config/.env.example`: Hub-only secrets (ANTHROPIC_API_KEY, TWILIO_*, GOOGLE_SA_KEY_PATH) are clearly hub-side.
- Bridge secrets (BLUEBUBBLES_{MEMBER}_*) are documented as per-bridge but stored in hub's .env — this is **correct by design**: the hub needs bridge URLs/secrets to send outbound iMessages through bridges.

### ⚠️ WARN — BlueBubbles secrets live on BOTH hub and bridges
- **File:** `config/.env.example:21-24`
- The hub stores `BLUEBUBBLES_JAMES_SECRET` and `BLUEBUBBLES_LAURA_SECRET` so it can call the bridge APIs. The bridges also know their own secret (it's set in BlueBubbles server config). This is architecturally necessary for hub→bridge outbound sends, but means the BB secrets exist on two machines each.
- **Risk:** Low. BB secrets are LAN-only authentication tokens. But document this dual-residency explicitly.

### ✅ PASS — No hub secrets leak to bridges
- Hub-only secrets (Anthropic, Twilio, Google SA) are never referenced in bridge setup sections of `PERSONAL_MINI_SETUP.md`.
- Bridges only need: `COS_HOST` env var, their own BlueBubbles instance, Apple Shortcuts.

---

## 2. Network Topology / Ports

### ✅ RESOLVED — Port 3141 vs 3333 confusion (fixed 2026-03-05)
- Port 3141 was a legacy reference to a planned-but-never-built standalone CoS API.
- All services run on port **3333** (Console/Express server). All references updated.
- **Files affected:** `PERSONAL_MINI_SETUP.md:61,1100,1107-1108`, `docs/pib-v5-build-spec.md:354`
- The deprecated FastAPI server (`archive/deprecated-fastapi/web.py:2181`) used :3141. The live system uses Express on :3333. The port table and firewall rules need updating.

### ✅ PASS — No port conflicts between services
- 3333 (Console/Express on hub), 1234 (BlueBubbles on bridges), 8581/51826 (Homebridge on James) — all distinct, no overlaps.

### ✅ PASS — No hardcoded localhost assumptions that break hub+spoke
- All cross-machine URLs use `$COS_HOST` variable or `.local` mDNS names, not `localhost`.
- `localhost:1234` references in docs are correctly scoped to "run this ON the bridge machine."

---

## 3. Data Flow Direction

### ✅ PASS — Bridges → Hub (one-way push) pattern correctly implemented
- **Sensor data:** Apple Shortcuts on bridges POST to `$COS_HOST:3333/api/sensors/ingest`
- **Task capture:** Shortcuts POST to `$COS_HOST:3333/api/capture/task`
- **BlueBubbles webhooks:** Bridge BB instance POSTs to `$COS_HOST:3333/api/webhooks/bluebubbles/{member}`
- **HomeKit:** Homebridge on James's Mini forwards state changes to CoS via HTTP webhook

### ⚠️ WARN — Hub DOES initiate connections to bridges (outbound iMessage)
- `src/pib/adapters/bluebubbles_sender.py:42-48`: Hub calls `bridge['url']/api/v1/server/info` (ping) and `bridge['url']/api/v1/message/text` (send).
- This means hub→bridge is **not** purely one-way. The hub actively connects to bridges to send iMessages.
- This is architecturally sound but contradicts a strict "bridges→hub only" model. Document as **bidirectional for iMessage channel**.

---

## 4. Secret Management

### ✅ PASS — Secrets gitignored properly
- `.gitignore` includes: `.env`, `config/.env`, `*.pem`, `*.db`

### ✅ PASS — .env.example documents all secrets with clear placeholders
- `config/.env.example` lists all env vars with placeholder values. No real secrets committed.

### ⚠️ WARN — No clear per-machine ownership labels in .env.example
- `config/.env.example` is a single file. It doesn't mark which vars belong on which machine.
- **Recommendation:** Add comments like `# --- HUB ONLY ---` and `# --- HUB (references bridge) ---`

### ✅ PASS — Key rotation documented
- `docs/pib-v5-build-spec.md:3394-3398`: Rotation cadences specified (Anthropic quarterly, Twilio annually, BB after macOS updates).
- `docs/pib-v5-build-spec.md:3817-3819`: Last-rotated tracking in DB.
- **Note:** No automated rotation — manual process only. Acceptable for a 3-machine household system.

---

## 5. Scalability (Adding a Third Person)

### ❌ FAIL — Hardcoded "JAMES"/"LAURA" tuples block scalability
Three locations hardcode the member list as a Python tuple:

| File | Line | Code |
|------|------|------|
| `src/pib/adapters/bluebubbles_sender.py` | 24 | `for member in ("JAMES", "LAURA"):` |
| `src/pib/adapters/__init__.py` | 65 | `for m in ("JAMES", "LAURA")` |
| `src/pib/readiness.py` | 48-49 | `("BLUEBUBBLES_JAMES_SECRET", "BLUEBUBBLES_JAMES_URL"), ("BLUEBUBBLES_LAURA_SECRET", ...)` |

**Impact:** Adding a nanny or grandparent bridge requires editing 3 Python files. This should be data-driven (e.g., scan env vars matching `BLUEBUBBLES_*_URL` pattern, or read from `common_members` table).

### ✅ PASS — member_id is the universal routing key
- `bluebubbles_sender.py:57-62`: `_resolve_bridge()` uses `member_id` (e.g., "m-james" → "james") to select bridge. This pattern is generic IF the bridge registry is dynamic.

### ⚠️ WARN — Config and docs assume exactly two members
- `config/.env.example:21-24`: Only JAMES and LAURA vars listed.
- `PERSONAL_MINI_SETUP.md`: Two-member structure throughout (Section 2 = James, Section 3 = Laura).
- Not a code bug, but docs would need a "Adding a New Bridge" section.

---

## Summary

| Check | Verdict | Key Issue |
|-------|---------|-----------|
| Credential isolation | ✅ PASS | BB secrets on hub is by-design (outbound sends) |
| Port topology | ⚠️ WARN | **3141 vs 3333 confusion in docs + firewall rules** |
| Data flow direction | ✅ PASS | Bidirectional for iMessage (documented as WARN) |
| Secret management | ✅ PASS | Minor: add per-machine labels to .env.example |
| Scalability | ❌ FAIL | **Hardcoded ("JAMES", "LAURA") in 3 Python files** |

### Top 3 Action Items

1. **Fix port 3141/3333 confusion** — Update `PERSONAL_MINI_SETUP.md` port table (line 61) and firewall rules (lines 1107-1108) to reflect that Express on :3333 is the actual ingest endpoint. Either remove :3141 references or document it as deprecated.

2. **Make bridge registry data-driven** — Replace hardcoded `("JAMES", "LAURA")` tuples with dynamic env var scanning (e.g., `re.findall(r'BLUEBUBBLES_(\w+)_URL', env_keys)`). Affects: `bluebubbles_sender.py:24`, `__init__.py:65`, `readiness.py:48-49`.

3. **Add per-machine ownership comments** to `config/.env.example` — Group vars under `# === CoS Hub ===` and `# === Hub → Bridge references ===` headers.
