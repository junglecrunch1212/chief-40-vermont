# TOOLS.md (CoS Agent)

## PIB CLI (domain logic — only interface)
```
python -m pib.cli <command> $PIB_DB_PATH [--json '{}'] [--member m-james]
```
Agent role: `export PIB_CALLER_AGENT=cos`

All domain operations go through the CLI. No raw SQL. No file writes. No exec.

## Google Workspace (read-only via CLI)
Calendar and sheets data is accessed through PIB CLI commands (calendar-query, budget).
Do NOT use `gog` CLI directly — that's handled by the infrastructure layer.

## Capabilities: none
- No filesystem writes
- No shell exec
- No direct database access
- Read workspace .md files only
