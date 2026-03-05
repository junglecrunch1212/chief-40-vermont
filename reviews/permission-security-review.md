# Permission & Security Model Review — PIB v5
**Date:** 2026-03-05  
**Reviewer:** Dev subagent  
**Scope:** Multi-agent permission boundaries, privacy fences, governance gates

---

## Executive Summary

The permission model is **well-designed and mostly implemented**. The 6-layer enforcement in `cli.py` is real code, not just docs. Key strengths: agent allowlist enforcement, governance gates, rate limiting, output sanitization, and audit logging all exist and run on every invocation. Two gaps found (noted below), but nothing critical — the architecture is sound.

**Overall: ✅ SOLID — 2 medium findings, 3 minor observations**

---

## 1. CLI Permission Boundary (`src/pib/cli.py`)

### ✅ PIB_CALLER_AGENT checked on every invocation
- Line in `run()`: `agent_id = os.environ.get("PIB_CALLER_AGENT", "dev")`
- **Default is "dev"** — this is intentional (dev is the admin agent, and only dev runs without explicit agent ID). Operational agents (CoS/Coach) are launched by OpenClaw with the env var set.
- All 6 layers use `agent_id` throughout.

### ✅ Agent allowlist enforced (Layer 1)
- `check_agent_allowlist()` loads `config/agent_capabilities.yaml`
- Checks: unknown agent → rejected; wildcard `"*"` for dev; explicit allowed/blocked lists for others
- Blocked wildcard `"*"` for scoreboard/proactive means only explicitly listed commands pass

### ✅ Governance gates enforced (Layer 2)
- `check_governance_gate()` maps commands via `COMMAND_TO_GATE` dict
- Checks `agent_overrides` on top of base gates
- Returns `"off"` → blocked, `"confirm"` → pending_approval, `"true"` → auto-approve
- In `run()`: `off` returns error JSON, `confirm` returns `pending_approval` status

### ✅ Rate limiting implemented (Layer 4)
- `check_write_rate()` queries `mem_cos_activity` for writes in last 60s
- Limit from `governance.yaml`: `writes_per_minute: 3`
- Gracefully handles missing table (early bootstrap)

### ✅ Output sanitization (Layer 5)
- `sanitize_output()` strips Anthropic API keys, env var leaks
- Non-dev agents: Laura's work calendar titles redacted, API keys redacted
- Patterns loaded from `governance.yaml` `output_sanitization` section

### ✅ Audit logging (Layer 6)
- `audit_invocation()` writes to `mem_cos_activity` on every call
- Captures: agent, command, args (truncated to 500 chars), success/fail
- Audit failure doesn't block the command (defense in depth, not a blocker)

### ✅ SQL guard (Layer 3)
- `check_sql_guard()` rejects any command not in `ALL_COMMANDS` set
- Combined with OpenClaw `capabilities: none` for operational agents, no raw SQL possible

---

## 2. Agent Capability Alignment

### Cross-reference: `agent_capabilities.yaml` vs `AGENTS.md` files

| Agent | YAML allowed | AGENTS.md listed | Aligned? |
|-------|-------------|-----------------|----------|
| CoS | 23 read + 13 write commands | All listed in AGENTS.md tables | ✅ Yes |
| Coach | 5 read + 4 write commands | All listed, blocked commands called out | ✅ Yes |
| Scoreboard | 3 read commands | N/A (no AGENTS.md — data feed only) | ✅ OK |
| Dev | `"*"` wildcard | "All commands available" | ✅ Yes |
| Proactive | 4 commands (1 write + 3 read) | N/A (cron-only, no interactive) | ✅ OK |

### ✅ Blocked commands actually blocked in code
- Coach `task-create`: blocked in YAML (`blocked_cli_commands`) AND governance override (`task_create: off`)
- Coach `budget`: blocked in YAML `blocked_cli_commands`
- Coach `hold-create`: blocked in YAML AND governance override (`calendar_hold_create: off`)
- Scoreboard all writes: governance overrides set `off` for task_create, task_complete, task_update, calendar_hold_create
- Scoreboard `blocked_cli_commands: "*"` — everything not in the 3 allowed commands is rejected

### 🟡 FINDING M1: Coach's `blocked_cli_commands` is a list, not `"*"`
Coach has an explicit block list rather than a wildcard block. This means any NEW command added to the CLI would be **allowed by default** for Coach unless also added to the block list. Scoreboard and Proactive correctly use `blocked_cli_commands: "*"` (default-deny).

**Recommendation:** Change Coach to `blocked_cli_commands: "*"` with only the explicit allow list, matching Scoreboard/Proactive pattern.

**Risk:** Medium — new commands would slip through to Coach until block list is updated.

---

## 3. Privacy Fences

### ✅ Laura's work calendar titles — code-enforced filtering

**In `context.py` → `build_calendar_context()`:**
- Events with `privacy: "privileged"` → shows `title_redacted` (not original title)
- Events with `privacy: "redacted"` → shows `[unavailable]`
- Events with `privacy: "full"` → shows actual title
- Member filtering via `for_member_ids` SQL LIKE clause — James can't see Laura-only events

**In `cli.py` → `cmd_calendar_query()`:**
- Non-dev agents: `privacy IN ('full', 'busy_only')` SQL filter
- Non-dev agents: `busy_only` events get `title = "[busy]"`, description/attendees nulled

**In `cli.py` → `sanitize_output()`:**
- Regex strips `laura_work_title` JSON keys for non-dev agents

**Test coverage:** `tests/test_privacy.py` uses canary strings to verify no leak. ✅

### ✅ Financial data not in Coach context
- Coach YAML: `privacy.financial_detail: none`
- Coach YAML: `budget` in `blocked_cli_commands`
- Coach SOUL.md: "❌ NO financial data — ever"
- `context.py` `assemble_context()`: financial section only assembled when `"financial"` relevance trigger fires, and this runs in the LLM context which is agent-scoped by the system prompt

### 🟡 FINDING M2: `assemble_context()` doesn't filter by agent role
`context.py` → `assemble_context(db, member_id, message)` takes `member_id` but NOT `agent_id`. If Coach calls `what-now` and the system prompt builder calls `assemble_context`, the financial data section would be assembled if the user's message contains financial trigger words.

**However, this is mitigated by:**
1. Coach can't call `budget` CLI command (blocked)
2. Coach's system prompt (SOUL.md) says never discuss finances
3. The `build_system_prompt()` function doesn't include financial context for Coach
4. In practice, Coach doesn't call `assemble_context()` directly — it goes through CLI commands

**Risk:** Medium — if the context assembly path ever runs for Coach agent with a message containing "$" or "budget", financial data could leak into Coach's LLM context. The CLI boundary prevents direct `budget` access, but `assemble_context` is a broader function.

**Recommendation:** Add `agent_id` parameter to `assemble_context()` and skip financial section when agent is Coach.

### ✅ Charlie data not directly addressable
- Charlie is a "passive actor" — no `m-charlie` CLI commands exist
- Memory search scoped to requesting member_id
- No commands target Charlie directly
- Custody data is about schedule, not Charlie's personal data

---

## 4. Channel Isolation

### ✅ Dev agent restricted to webchat
- `agent_capabilities.yaml`: dev channels = `[webchat]`
- Dev SOUL.md: "NEVER message Laura or family groups"
- Dev AGENTS.md: "Do NOT message family members"

**However:** Channel enforcement is at the **OpenClaw framework level** (which agent gets which channel), not in `cli.py`. The CLI doesn't have a "send message" command — outbound routing goes through `outbound_router.py` which checks channel capabilities via `ChannelRegistry`. The CLI has no `send-message` or `send-imessage` command, so dev can't programmatically send to iMessage through the CLI.

### ✅ CoS/Coach cannot run admin commands
- Both have `migrate`, `bootstrap`, `backup` in `blocked_cli_commands`
- Layer 1 (`check_agent_allowlist`) rejects these before any handler runs
- Test coverage in `tests/test_cli.py`: `test_cos_blocked_admin`, `test_cos_blocked_bootstrap`

### ✅ Scoreboard has no write capability
- Only 3 read commands allowed: `scoreboard-data`, `custody`, `streak`
- `blocked_cli_commands: "*"` — everything else rejected
- Governance overrides: all write gates set to `off`
- Double enforcement: allowlist AND governance gates

---

## 5. Governance Gates — End-to-End Trace

### `task_create: true` → auto-approve ✅
- `check_governance_gate("cos", "task-create", gov)` → returns `("true", "ok")`
- In `run()`: `true` falls through to handler execution
- `cmd_task_create` runs immediately, inserts row, returns task_id

### `calendar_hold_create: confirm` → queued ✅
- `check_governance_gate("cos", "hold-create", gov)` → returns `("confirm", "...")`
- In `run()`: `confirm` returns `{"status": "pending_approval", ...}` — handler NEVER executes
- User must approve through a separate flow

### `task_delete` → blocked ✅
- There IS no `task-delete` command at all — "No row is ever deleted from the task store" (Gene 7)
- Not in `ALL_COMMANDS`, so `check_sql_guard()` would reject it
- Not in `COMMAND_REGISTRY`, so no handler exists

### Agent overrides applied correctly ✅
- `governance.yaml` → `agent_overrides.coach.task_create: off`
- `check_governance_gate("coach", "task-create", gov)` correctly merges override over base
- Even if Coach somehow passes Layer 1 (allowlist), Layer 2 (governance) blocks it
- Same for scoreboard and proactive overrides

---

## 6. Workspace Template Isolation

### ✅ CoS SOUL.md — appropriate scope
- Contains household management, privacy rules, coaching protocols (Dark Prosthetics)
- Contains Laura/James/Charlie/Captain voice profiles — appropriate for household manager
- Financial data marked as `household_only` — appropriate restriction
- Includes "Scope Restrictions (CoS)" section explicitly listing what CoS cannot do

### ✅ Coach SOUL.md — no financial references
- Explicit: "❌ NO financial data — ever"
- `privacy.financial_detail: NONE`
- No budget, money, spending references in coaching protocols
- Scope section cleanly limited to streaks, energy, motivation

### ✅ Dev SOUL.md — no coaching protocols
- Contains Nine Genes reference (architectural, not coaching)
- No variable-ratio reinforcement, no elastic streaks, no Dark Prosthetics
- Scope limited to build/maintain/debug
- Privacy note: "Full visibility (admin) — for debugging only, never leak"

---

## Test Coverage Assessment

| Area | Test File | Coverage |
|------|-----------|----------|
| CLI allowlist | `test_cli.py` | ✅ Agent allow/block, unknown agents, all 5 agent types |
| Governance gates | `test_cli.py` | ✅ Gate values (true/confirm/off), agent overrides |
| Privacy fences | `test_privacy.py` | ✅ Canary strings, privileged/redacted titles |
| Memory isolation | `test_isolation.py` | ✅ Cross-member search, dedup, household shared |
| Bridge isolation | `test_bridge_isolation.py` | ✅ Per-bridge secrets, member forcing |
| Sensor privacy | `test_sensor_privacy.py` | ✅ Laura auto-privileged classification |

---

## Findings Summary

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| M1 | 🟡 Medium | Coach uses explicit block list instead of `blocked: "*"` — new commands default-allowed | Open |
| M2 | 🟡 Medium | `assemble_context()` doesn't filter financial data by agent role (mitigated by CLI boundary) | Open |
| O1 | 🔵 Minor | `PIB_CALLER_AGENT` defaults to `"dev"` — if env var missing, full admin | By design |
| O2 | 🔵 Minor | `outbound_router.py` doesn't check agent_id — relies on OpenClaw framework for channel isolation | Acceptable |
| O3 | 🔵 Minor | No explicit `task_delete` gate in governance.yaml (command doesn't exist, but gate could be defensive) | Low risk |

---

## Recommendations

1. **M1 fix:** Change Coach `blocked_cli_commands` from explicit list to `"*"` (default-deny)
2. **M2 fix:** Add `agent_id` param to `assemble_context()`, skip financial assembler for Coach
3. **Defensive:** Add `task_delete: off` to governance.yaml even though the command doesn't exist
4. **Test:** Add a test that iterates ALL_COMMANDS and verifies each agent's allow/block is consistent with YAML

---

*Review complete. Architecture is sound. The 6-layer enforcement model provides genuine defense-in-depth, not just documentation theater.*
