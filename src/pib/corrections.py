"""Misclassification correction: learn from user feedback on wrong task/event categorization."""

import logging

log = logging.getLogger(__name__)


async def record_correction(db, entity_type: str, entity_id: str, field: str, old_value: str, new_value: str, corrected_by: str) -> dict:
    """Record a user correction for future classification improvement."""
    from pib.db import audit_log

    await audit_log(
        db,
        table_name=f"correction_{entity_type}",
        operation="UPDATE",
        entity_id=entity_id,
        actor=corrected_by,
        old_values=f'{{"field":"{field}","value":"{old_value}"}}',
        new_values=f'{{"field":"{field}","value":"{new_value}"}}',
        source="user_correction",
    )

    return {"status": "recorded", "entity_type": entity_type, "entity_id": entity_id}
