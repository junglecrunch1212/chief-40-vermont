# scripts/core/ — OpenClaw Integration Scripts

These `.mjs` scripts bridge OpenClaw (L0) and PIB's Python CLI (L1-L2).

## Environment Variables

All scripts respect:

| Var | Default | Description |
|-----|---------|-------------|
| `PIB_DB_PATH` | `/opt/pib/data/pib.db` | Path to PIB SQLite database |
| `PIB_HOME` | `/opt/pib` | PIB home directory |
| `PIB_CALLER_AGENT` | `openclaw` | Passed to Python CLI for audit trail |

## Scripts

### `calendar_sync.mjs`

Fetches Google Calendar events via `gog` CLI and ingests them into PIB.

```bash
node scripts/core/calendar_sync.mjs --incremental --json   # last 24h
node scripts/core/calendar_sync.mjs --full --json           # last 90 days
node scripts/core/calendar_sync.mjs --cal-id "abc@group.calendar.google.com" --json
```

### `context_assembler.mjs`

Assembles the full LLM system prompt with calendar, tasks, and financial context.

```bash
node scripts/core/context_assembler.mjs --member 1 --json
node scripts/core/context_assembler.mjs --member 1 --message "What's on today?" --json
```

### `what_now.mjs`

Returns the single highest-priority next task for a member.

```bash
node scripts/core/what_now.mjs --member 1 --json
```

### `heartbeat_check.mjs`

Runs system health checks: DB exists, CLI health, gog auth, disk space, backup age.

```bash
node scripts/core/heartbeat_check.mjs --json
```

Returns `{status: "ok"|"warn"|"error", checks: [...]}`.

## Common Flags

All scripts support:
- `--json` — Structured JSON output
- `--help` — Usage information

## Reference
- `docs/openclaw-integration.md` §4.1 — Script architecture
- `src/pib/cli.py` — CLI command reference
