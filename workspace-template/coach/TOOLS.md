# TOOLS.md (Coach Agent)

## PIB CLI (domain logic — only interface)
```
python -m pib.cli <command> $PIB_DB_PATH [--json '{}'] [--member m-james]
```
Agent role: `export PIB_CALLER_AGENT=coach`

Limited to: what-now, streak, upcoming, search, health, task-complete, recurring-done, recurring-skip, state-update.

## Capabilities: none
- No filesystem writes
- No shell exec
- No direct database access
- Read workspace .md files only
