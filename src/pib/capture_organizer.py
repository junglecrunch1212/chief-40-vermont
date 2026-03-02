"""Deep organizer for captures — Layer 2 (LLM-powered).

Runs on a schedule (every 30 min) to enrich triaged captures with:
- Title and summary
- Tags and entity extraction
- Connection discovery (FTS5)
- Dual-route proposals (spawn task/memory)
- Recipe data extraction
- Cross-user connection discovery (household_visible only)

Follows the extraction.py pattern: batch processing, graceful failure, retry limits.
"""

import json
import logging
import os

from pib.db import audit_log, get_config

log = logging.getLogger(__name__)


ORGANIZER_SYSTEM_PROMPT = """You are a knowledge organizer for a household management system (ADHD-optimized).
Given a captured thought/note, return structured metadata as JSON.

Rules:
- title: 3-8 word descriptive title
- summary: 1 sentence summary of the key insight or content
- tags: 1-5 relevant tags (lowercase, no spaces, use hyphens)
- extracted_entities: people, places, businesses mentioned [{name, type}]
- connections: search queries to find related content in the knowledge base (2-4 queries)
- dual_route: if this should ALSO become a task or memory, specify {shape: "task"|"memory", data: {...}}
  - Only suggest dual_route for clear action items (tasks) or important facts (memories)
- recipe_data: if this is a recipe, extract {servings, prep_min, cook_min, ingredients: [], steps: [], cuisine, dietary_tags: []}
  - Only include recipe_data for actual recipes

Return ONLY valid JSON. No explanation text."""

ORGANIZER_USER_TEMPLATE = """Organize this captured thought:

Type: {capture_type}
Notebook: {notebook}
Content: {raw_text}

Existing tags in this user's collection: {existing_tags}

Return JSON with: title, summary, tags, extracted_entities, connections, dual_route (or null), recipe_data (or null)"""


async def organize_batch(db, batch_size: int | None = None) -> int:
    """Process a batch of triaged captures. Returns count organized."""
    enabled = await get_config(db, "capture_deep_organizer_enabled", "1")
    if enabled != "1":
        log.debug("Deep organizer disabled by config")
        return 0

    if batch_size is None:
        batch_size = int(await get_config(db, "capture_deep_organizer_batch_size", "20"))

    # Get triaged captures that haven't been organized yet
    captures = await db.execute_fetchall(
        "SELECT * FROM cap_captures WHERE triage_status = 'triaged' "
        "AND organize_attempts < 3 AND archived = 0 "
        "ORDER BY created_at ASC LIMIT ?",
        [batch_size],
    )
    if not captures:
        return 0

    log.info(f"Organizing {len(captures)} captures")
    organized = 0

    for capture in captures:
        try:
            existing_tags = await get_common_tags(db, capture["member_id"])
            org_data = await _organize_single(capture, existing_tags)

            if org_data:
                await _apply_organization(db, capture["id"], capture["member_id"], org_data)
                organized += 1

                # Cross-user connection discovery for household-visible captures
                if capture["household_visible"]:
                    cross_user_enabled = await get_config(db, "capture_cross_user_connections", "1")
                    if cross_user_enabled == "1":
                        await _discover_cross_user_connections(db, capture["id"])
            else:
                # Increment attempt count but don't mark as failed yet
                await db.execute(
                    "UPDATE cap_captures SET organize_attempts = organize_attempts + 1 "
                    "WHERE id = ?",
                    [capture["id"]],
                )
                await db.commit()

        except Exception as e:
            log.error(f"Organize failed for capture {capture['id']}: {e}")
            await db.execute(
                "UPDATE cap_captures SET organize_attempts = organize_attempts + 1, "
                "triage_status = CASE WHEN organize_attempts >= 2 THEN 'failed' ELSE triage_status END "
                "WHERE id = ?",
                [capture["id"]],
            )
            await db.commit()

    return organized


async def _organize_single(capture: dict, existing_tags: list[str]) -> dict | None:
    """Run LLM organization on a single capture. Returns structured org_data or None."""
    raw_text = capture.get("raw_text", "")
    if not raw_text.strip():
        return None

    user_msg = ORGANIZER_USER_TEMPLATE.format(
        capture_type=capture.get("capture_type", "note"),
        notebook=capture.get("notebook", "inbox"),
        raw_text=raw_text,
        existing_tags=", ".join(existing_tags[:30]) if existing_tags else "(none yet)",
    )

    try:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            log.warning("No ANTHROPIC_API_KEY — skipping organization")
            return None

        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=ORGANIZER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = response.content[0].text.strip()
        # Handle markdown code block wrapping
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)
        if not isinstance(data, dict):
            log.warning(f"Organizer returned non-dict: {type(data)}")
            return None

        return data

    except json.JSONDecodeError as e:
        log.error(f"Failed to parse organizer JSON: {e}")
        return None
    except Exception as e:
        log.error(f"LLM organizer call failed: {e}")
        return None


async def _apply_organization(db, capture_id: str, member_id: str, org_data: dict):
    """Write organization results back to the capture and create connections."""
    sets = ["triage_status = 'organized'", "organize_attempts = organize_attempts + 1",
            "last_organized_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')",
            "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')"]
    params = []

    if org_data.get("title"):
        sets.append("title = ?")
        params.append(org_data["title"])

    if org_data.get("summary"):
        sets.append("summary = ?")
        params.append(org_data["summary"])

    if org_data.get("tags"):
        sets.append("tags = ?")
        params.append(json.dumps(org_data["tags"]))

    if org_data.get("extracted_entities"):
        sets.append("extracted_entities = ?")
        params.append(json.dumps(org_data["extracted_entities"]))

    if org_data.get("recipe_data"):
        recipe_enabled = await get_config(db, "capture_recipe_extraction", "1")
        if recipe_enabled == "1":
            sets.append("recipe_data = ?")
            params.append(json.dumps(org_data["recipe_data"]))

    # Set resurface_after to 7 days from now for organized captures
    sets.append("resurface_after = strftime('%Y-%m-%dT%H:%M:%SZ','now', '+7 days')")

    params.append(capture_id)
    await db.execute(
        f"UPDATE cap_captures SET {', '.join(sets)} WHERE id = ?",
        params,
    )

    # Search for and create connections
    if org_data.get("connections"):
        await _search_for_connections(db, capture_id, org_data["connections"])

    await audit_log(
        db, "cap_captures", "UPDATE", capture_id,
        actor="deep_organizer",
        new_values=json.dumps({"title": org_data.get("title"), "tags": org_data.get("tags")}),
    )
    await db.commit()

    # Handle dual routing proposals
    if org_data.get("dual_route"):
        await _handle_dual_route(db, capture_id, member_id, org_data["dual_route"])


async def _search_for_connections(db, capture_id: str, connection_queries: list[str]):
    """Search for related content using FTS5 and create connections."""
    from pib.capture import search_captures_fts, add_connection

    capture = await db.execute_fetchone(
        "SELECT member_id FROM cap_captures WHERE id = ?", [capture_id]
    )
    if not capture:
        return

    for query in connection_queries[:4]:  # Limit to 4 queries
        try:
            results = await search_captures_fts(
                db, query, capture["member_id"], include_household=True, limit=3
            )
            for result in results:
                if result["id"] != capture_id:
                    await add_connection(
                        db, capture_id, "capture", result["id"],
                        connection_type="related",
                        reason=f"FTS match: {query}",
                        created_by="deep_organizer",
                    )
        except Exception as e:
            log.debug(f"Connection search failed for query '{query}': {e}")


async def _discover_cross_user_connections(db, capture_id: str):
    """Discover cross-user connections for household-visible captures."""
    from pib.capture import find_household_connections
    try:
        connections = await find_household_connections(db, capture_id)
        if connections:
            log.info(f"Found {len(connections)} cross-user connections for {capture_id}")
    except Exception as e:
        log.debug(f"Cross-user connection discovery failed for {capture_id}: {e}")


async def _handle_dual_route(db, capture_id: str, member_id: str, dual_route: dict):
    """Handle dual-routing: create a task or memory from a capture."""
    from pib.db import next_id

    shape = dual_route.get("shape")
    data = dual_route.get("data", {})

    if shape == "task" and data.get("title"):
        try:
            task_id = await next_id(db, "tsk")
            await db.execute(
                "INSERT INTO ops_tasks (id, title, assignee, created_by, source_system) "
                "VALUES (?, ?, ?, 'deep_organizer', 'capture')",
                [task_id, data["title"], member_id],
            )
            await db.execute(
                "UPDATE cap_captures SET spawned_task_id = ? WHERE id = ?",
                [task_id, capture_id],
            )
            await db.commit()
            log.info(f"Dual-routed capture {capture_id} -> task {task_id}")
        except Exception as e:
            log.error(f"Dual-route task creation failed: {e}")

    elif shape == "memory" and data.get("content"):
        try:
            from pib.memory import save_memory_deduped
            result = await save_memory_deduped(
                db, data["content"],
                category=data.get("category", "observations"),
                domain=data.get("domain"),
                member_id=member_id,
                source="capture_organizer",
            )
            if result.get("id"):
                await db.execute(
                    "UPDATE cap_captures SET spawned_memory_id = ? WHERE id = ?",
                    [result["id"], capture_id],
                )
                await db.commit()
                log.info(f"Dual-routed capture {capture_id} -> memory {result['id']}")
        except Exception as e:
            log.error(f"Dual-route memory creation failed: {e}")


async def get_common_tags(db, member_id: str, limit: int = 50) -> list[str]:
    """Get the most commonly used tags for a member. Used for auto-suggest."""
    try:
        rows = await db.execute_fetchall(
            "SELECT tags FROM cap_captures WHERE member_id = ? AND tags != '[]' AND archived = 0 "
            "ORDER BY created_at DESC LIMIT 200",
            [member_id],
        )
        tag_counts: dict[str, int] = {}
        for row in (rows or []):
            try:
                tags = json.loads(row["tags"])
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        # Sort by frequency, return top N
        sorted_tags = sorted(tag_counts.keys(), key=lambda t: tag_counts[t], reverse=True)
        return sorted_tags[:limit]
    except Exception:
        return []
