"""Google Sheets bidirectional sync: push DB state, receive webhook updates."""

import json
import logging

log = logging.getLogger(__name__)

# Sheets sync tables and their column mappings
SYNC_TABLES = {
    "Tasks": {
        "table": "ops_tasks",
        "columns": ["id", "title", "status", "assignee", "domain", "due_date",
                     "energy", "effort", "micro_script", "notes"],
        "filter": "status NOT IN ('done', 'dismissed')",
    },
    "Lists": {
        "table": "ops_lists",
        "columns": ["id", "list_name", "item_text", "quantity", "unit",
                     "checked", "added_by", "added_at"],
        "filter": "checked = 0",
    },
    "Budget": {
        "table": "fin_budget_snapshot",
        "columns": ["category", "monthly_target", "spent_this_month",
                     "remaining", "pct_used", "over_threshold"],
        "filter": None,
    },
    "Schedule": {
        "table": "cal_classified_events",
        "columns": ["id", "event_date", "start_time", "end_time", "title",
                     "scheduling_impact", "for_member_ids"],
        "filter": "event_date >= date('now') AND event_date <= date('now', '+7 days')",
    },
}


async def push_to_sheets(db) -> dict:
    """Push current DB state to Google Sheets. Runs every 15 minutes."""
    results = {}
    for sheet_name, config in SYNC_TABLES.items():
        try:
            query = f"SELECT {', '.join(config['columns'])} FROM {config['table']}"
            if config.get("filter"):
                query += f" WHERE {config['filter']}"

            rows = await db.execute_fetchall(query)
            data = [dict(r) for r in rows] if rows else []
            results[sheet_name] = {"rows": len(data), "status": "ready"}
            # Actual Google Sheets API call would go here
        except Exception as e:
            log.error(f"Sheets push failed for {sheet_name}: {e}")
            results[sheet_name] = {"rows": 0, "status": "error", "error": str(e)}

    return results


async def handle_sheets_webhook(db, payload: dict) -> dict:
    """Process an incoming Google Sheets onChange webhook."""
    sheet_name = payload.get("sheet_name")
    changes = payload.get("changes", [])

    if not sheet_name or sheet_name not in SYNC_TABLES:
        return {"status": "ignored", "reason": "unknown_sheet"}

    config = SYNC_TABLES[sheet_name]
    applied = 0

    for change in changes:
        row_id = change.get("id")
        field = change.get("field")
        new_value = change.get("value")

        if not row_id or not field:
            continue

        if field not in config["columns"]:
            continue

        try:
            await db.execute(
                f"UPDATE {config['table']} SET {field} = ?, updated_at = datetime('now') WHERE id = ?",
                [new_value, row_id],
            )
            applied += 1
        except Exception as e:
            log.error(f"Sheets webhook update failed: {e}")

    if applied:
        await db.commit()

    return {"status": "ok", "applied": applied}
