# scripts/core/ — OpenClaw Integration Scripts

These `.mjs` scripts are the glue between OpenClaw (L0) and PIB's Python CLI (L1-L2).
They are created by the OpenClaw agent during bootstrap Phase 7.

## Expected Scripts

| Script | Purpose |
|--------|---------|
| `calendar_sync.mjs` | Calls `gog calendar events --json`, pipes to `python -m pib.cli calendar-ingest $PIB_DB_PATH` |
| `context_assembler.mjs` | Calls `python -m pib.cli context $PIB_DB_PATH --member {id}`, returns system prompt |
| `what_now.mjs` | Thin wrapper around `python -m pib.cli what-now $PIB_DB_PATH` |
| `heartbeat_check.mjs` | SQLite health + gog connectivity checks |

## Pattern

Each script:
1. Reads config/env for paths and credentials
2. Calls `gog` CLI or Python CLI via `execSync`/`spawn`
3. Parses JSON output
4. Returns structured result to OpenClaw

## Reference
- `docs/openclaw-integration.md` §4.1 — Script architecture
- `docs/openclaw-integration.md` §5 — Workspace file generation
- `src/pib/cli.py` — CLI command reference (26 commands, 6-layer permission boundary)
