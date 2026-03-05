# TOOLS.md (Dev Agent)

## PIB CLI (full access)
```
python -m pib.cli <command> $PIB_DB_PATH [--json '{}'] [--member m-james]
```
Agent role: `export PIB_CALLER_AGENT=dev`

## Google Workspace (gog CLI)
```
gog calendar list
gog calendar events <calendar_id> --from YYYY-MM-DD --to YYYY-MM-DD --json
gog sheets get <sheet_id> <range> --json
gog gmail list --json
```

## Database
SQLite SSOT at `$PIB_DB_PATH`. Direct SQL access for debugging. WAL mode, FTS5 for search.

## Console
Express server at `console/server.mjs`, port 3333.

## Backup
`python -m pib.cli backup $PIB_DB_PATH`

## Capabilities: full
- Filesystem read/write
- Shell exec
- Direct database access
- All CLI commands
