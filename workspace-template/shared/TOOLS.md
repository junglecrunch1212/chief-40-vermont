# TOOLS.md

## PIB CLI (domain logic)
All PIB commands go through the CLI permission boundary:
```
source /opt/pib/venv/bin/activate
python -m pib.cli <command> $PIB_DB_PATH [--json '{}'] [--member m-james]
```
Set agent role: `export PIB_CALLER_AGENT=cos`
See `docs/openclaw-integration.md` for full command reference.

## Google Workspace (gog CLI)
Ships with OpenClaw. Pre-authenticated via `gog auth login`.
```
gog calendar list
gog calendar events <calendar_id> --from YYYY-MM-DD --to YYYY-MM-DD --json
gog sheets get <sheet_id> <range> --json
gog gmail list --json
```

## Database
SQLite SSOT at `$PIB_DB_PATH` (default: `/opt/pib/data/pib.db`).
Read via CLI commands, not raw SQL. WAL mode, FTS5 for search.

## Console
Express server at `console/server.mjs`, port 3333.
Start: `node console/server.mjs`
Dashboard: `console/index.html`

## Backup
Hourly via `python -m pib.cli backup $PIB_DB_PATH`.
Backups stored in `/opt/pib/data/backups/`.
