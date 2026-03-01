"""Async extraction worker: pulls comms with extraction_status='pending',
runs LLM to propose tasks/events/entities/list items, stores results.

All extractions are PROPOSALS — Gene 1 CONFIRM gate governs.
Nothing auto-creates without user approval.
"""

import json
import logging
import os

from pib.comms import get_pending_extractions, mark_extraction_failed, save_extraction_result
from pib.db import get_config

log = logging.getLogger(__name__)

# Extraction prompt — instructs the LLM to find actionable items in a message
EXTRACTION_SYSTEM_PROMPT = """You are an extraction engine for a household management system.
Given a message, extract ANY actionable items that could be:
- task: Something someone needs to DO (e.g., "call the plumber", "pick up groceries")
- event: A date/time reference (e.g., "dinner Friday at 7", "piano lessons Tuesdays 4pm")
- entity: A person, business, or contact (e.g., "Dr. Park (404) 555-0300")
- list_item: Something to add to a shopping/task list (e.g., "milk, eggs, bread")
- recurring: A repeating commitment (e.g., "piano lessons every Tuesday 4pm")
- bill: A financial amount or bill (e.g., "electric bill was $142")

For each extracted item, return:
- type: one of [task, event, entity, list_item, recurring, bill]
- title: short description
- data: relevant structured data (assignee, amount, date, phone, etc.)
- confidence: 0.0-1.0 how confident you are this is a real actionable item

Return a JSON array of extracted items. If nothing actionable, return [].
Be conservative — only extract items you're confident about (>= 0.6).
NEVER fabricate items that aren't clearly implied by the message."""

EXTRACTION_USER_TEMPLATE = """Extract actionable items from this message:

Channel: {channel}
From: {from_addr}
Date: {date}
Subject: {subject}
Message: {body}

Return ONLY a JSON array. No explanation text."""


async def extraction_worker(db) -> int:
    """Process pending extractions. Returns count of comms processed.

    Called by scheduler every 5 minutes.
    """
    min_confidence = float(await get_config(db, "comms_extraction_min_confidence", "0.7"))
    enabled = await get_config(db, "comms_extraction_enabled", "1")
    if enabled != "1":
        log.debug("Extraction disabled by config")
        return 0

    pending = await get_pending_extractions(db, limit=10)
    if not pending:
        return 0

    log.info(f"Processing {len(pending)} pending extractions")
    processed = 0

    for comm in pending:
        try:
            items = await _extract_from_comm(comm, min_confidence)
            if items is not None:
                avg_confidence = sum(i["confidence"] for i in items) / len(items) if items else 0.0
                await save_extraction_result(db, comm["id"], items, avg_confidence)
                processed += 1
                log.info(f"Extracted {len(items)} items from comm {comm['id']}")
            else:
                await save_extraction_result(db, comm["id"], [], 0.0)
                processed += 1
        except Exception as e:
            log.error(f"Extraction failed for comm {comm['id']}: {e}")
            await mark_extraction_failed(db, comm["id"])

    return processed


async def _extract_from_comm(comm: dict, min_confidence: float) -> list[dict] | None:
    """Run LLM extraction on a single comm. Returns list of proposed items."""
    # Build the extraction prompt
    body = comm.get("body_snippet") or comm.get("summary") or ""
    if not body.strip():
        return []

    user_msg = EXTRACTION_USER_TEMPLATE.format(
        channel=comm.get("channel", "unknown"),
        from_addr=comm.get("from_addr", "unknown"),
        date=comm.get("date", "unknown"),
        subject=comm.get("subject", ""),
        body=body,
    )

    try:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            log.warning("No ANTHROPIC_API_KEY — skipping extraction")
            return None

        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        # Parse the JSON response
        text = response.content[0].text.strip()
        # Handle markdown code block wrapping
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        items = json.loads(text)
        if not isinstance(items, list):
            log.warning(f"Extraction returned non-list: {type(items)}")
            return []

        # Filter by confidence threshold
        filtered = [item for item in items if item.get("confidence", 0) >= min_confidence]
        return filtered

    except json.JSONDecodeError as e:
        log.error(f"Failed to parse extraction JSON: {e}")
        return None
    except Exception as e:
        log.error(f"LLM extraction call failed: {e}")
        return None


async def retry_failed_extractions(db) -> int:
    """Re-attempt failed extractions. Called by scheduler every 4 hours."""
    cursor = await db.execute(
        "UPDATE ops_comms SET extraction_status = 'pending' "
        "WHERE extraction_status = 'failed'"
    )
    await db.commit()
    count = cursor.rowcount
    if count > 0:
        log.info(f"Re-queued {count} failed extractions for retry")
    return count
