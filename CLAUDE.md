# PIB v5 — Poopsy-In-A-Box

## What This Is
ADHD-optimized household Chief-of-Staff system for the Stice-Sclafani family. Runs on OpenClaw L0 infrastructure (gateway + cron + console) backed by SQLite with Claude LLM integration.

## Key Files
- `docs/pib-v5-build-spec.md` — THE master specification (3835 lines). Source of truth for all architecture, schema, algorithms, and behavioral mechanics.
- `docs/pib-api-contract.md` — Every API endpoint the console calls with request/response shapes.
- `docs/diagrams/pib-console-wired.jsx` — Complete React SPA prototype (1738 lines).
- `src/pib/` — Python source modules (domain logic + CLI).
- `scripts/core/` — Node.js operational scripts (calendar, context assembly, recurring tasks).
- `console/` — Express server (server.mjs) + dashboard UI (index.html).
- `workspace-template/` — OpenClaw workspace template (agents.yaml, cron, tools).
- `BOOTSTRAP_INSTRUCTIONS.md` — Setup guide for OpenClaw deployment.
- `migrations/001_initial_schema.sql` — Full SQLite DDL (35+ tables).
- `tests/` — pytest test suite.
- `archive/` — Deprecated FastAPI/frontend code (reference only, do not import).

## Architecture
- **L0 (Infrastructure):** OpenClaw gateway, cron engine, channel auth, `gog` CLI for Google.
- **Layer 1 (Core):** SQLite SSOT, whatNow(), state machine, prefix parser, custody math, streaks, rewards. Always works, no network.
- **Layer 2 (Intelligence):** Claude LLM (Opus/Sonnet), context assembly, 15 tools, streaming chat. Falls back to Layer 1.
- **Layer 3 (Enrichment):** Google Sheets sync, Gmail, CRM. Can be offline indefinitely.

## Conventions
- All dates: ISO 8601 (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`)
- ID format: `{prefix}-{ULID}` (e.g., `tsk-01HX...`, `mem-01HX...`)
- Database: SQLite 3.45+ with WAL mode, FTS5 for search
- Task state machine: inbox → next → in_progress → done (see spec §5.3)
- Timezone: America/New_York (Atlanta)

## Running
```bash
# CLI (domain commands)
python -m pib.cli <command> $PIB_DB_PATH [--json '{}'] [--member m-james]

# Console (Express dashboard)
node console/server.mjs  # :3333

# Tests
pip install -e ".[dev]"
pytest tests/ -v

# OpenClaw (gateway + cron)
openclaw gateway start
```

## Key Design Decisions
- whatNow() is pure/deterministic — same inputs always produce same output
- Privacy fence: Laura's work calendar content NEVER leaks into any context
- Variable-ratio rewards (60/25/10/5%) for dopamine-driven task completion
- All LLM writes have undo entries and audit log records
- Gene 4: PIB never writes to external calendars or moves money
