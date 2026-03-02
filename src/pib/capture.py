"""Capture domain: zero-friction knowledge capture, deterministic triage, CRUD, FTS5 search.

Layer 1 — all operations are deterministic (no LLM). Deep organization is in capture_organizer.py.
"""

import json
import logging
import re

from pib.db import audit_log, next_id

log = logging.getLogger(__name__)


# ─── System Notebooks ───

SYSTEM_NOTEBOOKS = [
    {"slug": "inbox",     "name": "Inbox",     "icon": "📥", "sort_order": 0},
    {"slug": "ideas",     "name": "Ideas",     "icon": "💡", "sort_order": 10},
    {"slug": "recipes",   "name": "Recipes",   "icon": "🍳", "sort_order": 20},
    {"slug": "bookmarks", "name": "Bookmarks", "icon": "🔖", "sort_order": 30},
    {"slug": "quotes",    "name": "Quotes",    "icon": "💬", "sort_order": 40},
    {"slug": "questions", "name": "Questions",  "icon": "❓", "sort_order": 50},
    {"slug": "reference", "name": "Reference", "icon": "📚", "sort_order": 60},
    {"slug": "logs",      "name": "Logs",      "icon": "📝", "sort_order": 70},
]


# ─── Deterministic Triage Rules ───

TRIAGE_RULES = [
    # (regex, capture_type, notebook_slug, priority)
    (r"^recipe:\s*", "recipe", "recipes", "normal"),
    (r"^idea:\s*", "idea", "ideas", "normal"),
    (r"^bookmark:\s*", "bookmark", "bookmarks", "normal"),
    (r"^quote:\s*", "quote", "quotes", "normal"),
    (r"^question:\s*", "question", "questions", "normal"),
    (r"^ref:\s*", "reference", "reference", "normal"),
    (r"^log:\s*", "log", "logs", "normal"),
    (r"^note:\s*", "note", "inbox", "normal"),
    (r"^important:\s*", "note", "inbox", "high"),
]

CONTENT_HEURISTICS = [
    # (pattern, capture_type, notebook_slug)
    (r"(?:ingredients?|servings?|cups?|tbsp|tsp|preheat|recipe)", "recipe", "recipes"),
    (r"(?:https?://\S+)", "bookmark", "bookmarks"),
    (r'^"[^"]+"\s*[-—]\s*\w', "quote", "quotes"),
    (r"(?:how\s+(?:do|does|can|should|to)|what\s+(?:is|are)|why\s+(?:is|does))\b", "question", "questions"),
]


def triage_capture(raw_text: str) -> dict:
    """Deterministic triage: classify raw text into type, notebook, priority.

    Returns {capture_type, notebook, priority, cleaned_text}.
    Pure function — no DB, no LLM. Same input always produces same output.
    """
    text = raw_text.strip()

    # Pass 1: Prefix rules (highest precedence)
    for pattern, capture_type, notebook, priority in TRIAGE_RULES:
        m = re.match(pattern, text, re.IGNORECASE)
        if m:
            cleaned = text[m.end():].strip()
            return {
                "capture_type": capture_type,
                "notebook": notebook,
                "priority": priority,
                "cleaned_text": cleaned,
            }

    # Pass 2: Content heuristics
    for pattern, capture_type, notebook in CONTENT_HEURISTICS:
        if re.search(pattern, text, re.IGNORECASE):
            return {
                "capture_type": capture_type,
                "notebook": notebook,
                "priority": "normal",
                "cleaned_text": text,
            }

    # Default: note in inbox
    return {
        "capture_type": "note",
        "notebook": "inbox",
        "priority": "normal",
        "cleaned_text": text,
    }


# ─── Notebook Management ───

async def ensure_member_notebooks(db, member_id: str):
    """Create system notebooks for a member if they don't exist. Idempotent."""
    for nb in SYSTEM_NOTEBOOKS:
        existing = await db.execute_fetchone(
            "SELECT id FROM cap_notebooks WHERE member_id = ? AND slug = ?",
            [member_id, nb["slug"]],
        )
        if not existing:
            nb_id = await next_id(db, "nb")
            await db.execute(
                "INSERT INTO cap_notebooks (id, member_id, name, slug, icon, sort_order, is_system) "
                "VALUES (?, ?, ?, ?, ?, ?, 1)",
                [nb_id, member_id, nb["name"], nb["slug"], nb["icon"], nb["sort_order"]],
            )
    await db.commit()


async def get_notebook_list(db, member_id: str) -> list[dict]:
    """Get notebooks for member (own + household-wide)."""
    rows = await db.execute_fetchall(
        "SELECT * FROM cap_notebooks WHERE member_id = ? OR member_id IS NULL "
        "ORDER BY sort_order, name",
        [member_id],
    )
    return [dict(r) for r in rows] if rows else []


async def create_notebook(db, member_id: str, name: str, slug: str,
                          icon: str | None = None, description: str | None = None) -> dict:
    """Create a custom notebook."""
    nb_id = await next_id(db, "nb")
    await db.execute(
        "INSERT INTO cap_notebooks (id, member_id, name, slug, icon, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [nb_id, member_id, name, slug, icon, description],
    )
    await db.commit()
    return {"id": nb_id, "name": name, "slug": slug}


async def update_notebook(db, notebook_id: str, member_id: str, updates: dict) -> dict | None:
    """Update notebook fields. Returns updated notebook or None if not found/not owned."""
    row = await db.execute_fetchone(
        "SELECT * FROM cap_notebooks WHERE id = ? AND member_id = ?",
        [notebook_id, member_id],
    )
    if not row:
        return None

    allowed = {"name", "slug", "icon", "description", "sort_order"}
    sets = []
    params = []
    for k, v in updates.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)

    if not sets:
        return dict(row)

    sets.append("updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')")
    params.extend([notebook_id, member_id])
    await db.execute(
        f"UPDATE cap_notebooks SET {', '.join(sets)} WHERE id = ? AND member_id = ?",
        params,
    )
    await db.commit()
    return await db.execute_fetchone(
        "SELECT * FROM cap_notebooks WHERE id = ?", [notebook_id]
    )


# ─── Capture CRUD ───

async def create_capture(
    db,
    member_id: str,
    raw_text: str,
    source: str = "chat",
    source_ref: str | None = None,
    household_visible: bool = False,
) -> dict:
    """Create a capture: triage + insert + audit log. Returns the new capture dict."""
    # Ensure system notebooks exist
    await ensure_member_notebooks(db, member_id)

    # Deterministic triage
    triage = triage_capture(raw_text)

    cap_id = await next_id(db, "cap")
    await db.execute(
        """INSERT INTO cap_captures
           (id, member_id, raw_text, body, source, source_ref, capture_type,
            notebook, priority, household_visible, triage_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'triaged')""",
        [
            cap_id, member_id, raw_text, triage["cleaned_text"],
            source, source_ref, triage["capture_type"],
            triage["notebook"], triage["priority"],
            1 if household_visible else 0,
        ],
    )

    # Update notebook capture_count
    await db.execute(
        "UPDATE cap_notebooks SET capture_count = capture_count + 1 "
        "WHERE member_id = ? AND slug = ?",
        [member_id, triage["notebook"]],
    )

    await audit_log(db, "cap_captures", "INSERT", cap_id, actor=member_id, source=source)
    await db.commit()

    row = await db.execute_fetchone("SELECT * FROM cap_captures WHERE id = ?", [cap_id])
    return dict(row)


async def get_capture(db, capture_id: str, member_id: str) -> dict | None:
    """Get a single capture. Enforces ownership or household_visible."""
    row = await db.execute_fetchone(
        "SELECT * FROM cap_captures WHERE id = ? AND (member_id = ? OR household_visible = 1)",
        [capture_id, member_id],
    )
    return dict(row) if row else None


async def update_capture(db, capture_id: str, member_id: str, updates: dict) -> dict | None:
    """Update capture fields. Only owner can update. Returns updated capture or None."""
    row = await db.execute_fetchone(
        "SELECT * FROM cap_captures WHERE id = ? AND member_id = ?",
        [capture_id, member_id],
    )
    if not row:
        return None

    allowed = {
        "title", "body", "capture_type", "notebook", "priority", "tags",
        "summary", "pinned", "household_visible", "privacy",
        "resurface_after", "recipe_data",
    }
    sets = []
    params = []
    old_values = {}
    for k, v in updates.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v if not isinstance(v, (list, dict)) else json.dumps(v))
            old_values[k] = row[k]

    if not sets:
        return dict(row)

    sets.append("updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')")
    params.extend([capture_id, member_id])
    await db.execute(
        f"UPDATE cap_captures SET {', '.join(sets)} WHERE id = ? AND member_id = ?",
        params,
    )
    await audit_log(
        db, "cap_captures", "UPDATE", capture_id,
        actor=member_id, old_values=json.dumps(old_values),
        new_values=json.dumps({k: v for k, v in updates.items() if k in allowed}),
    )
    await db.commit()

    return await get_capture(db, capture_id, member_id)


async def archive_capture(db, capture_id: str, member_id: str) -> bool:
    """Soft-archive a capture. Returns True if successful."""
    row = await db.execute_fetchone(
        "SELECT id FROM cap_captures WHERE id = ? AND member_id = ?",
        [capture_id, member_id],
    )
    if not row:
        return False

    await db.execute(
        "UPDATE cap_captures SET archived = 1, archived_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
        [capture_id],
    )
    await audit_log(db, "cap_captures", "UPDATE", capture_id, actor=member_id,
                    new_values='{"archived": true}')
    await db.commit()
    return True


# ─── List & Search ───

async def list_captures(
    db,
    member_id: str,
    notebook: str | None = None,
    capture_type: str | None = None,
    priority: str | None = None,
    include_household: bool = False,
    search: str | None = None,
    pinned_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List captures with multi-filter support. Follows comms.py pattern."""
    conditions = []
    params = []

    if include_household:
        conditions.append("(member_id = ? OR household_visible = 1)")
        params.append(member_id)
    else:
        conditions.append("member_id = ?")
        params.append(member_id)

    conditions.append("archived = 0")

    if notebook:
        conditions.append("notebook = ?")
        params.append(notebook)
    if capture_type:
        conditions.append("capture_type = ?")
        params.append(capture_type)
    if priority:
        conditions.append("priority = ?")
        params.append(priority)
    if pinned_only:
        conditions.append("pinned = 1")
    if search:
        conditions.append("(raw_text LIKE ? OR title LIKE ? OR body LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await db.execute_fetchall(
        f"SELECT * FROM cap_captures WHERE {where} "
        "ORDER BY pinned DESC, created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    return [dict(r) for r in rows] if rows else []


async def search_captures_fts(
    db,
    query: str,
    member_id: str,
    include_household: bool = False,
    limit: int = 20,
) -> list[dict]:
    """FTS5 search with LIKE fallback. Reuses _sanitize_fts5_query from memory.py."""
    from pib.memory import _sanitize_fts5_query

    safe_query = _sanitize_fts5_query(query)
    if not safe_query:
        return []

    if include_household:
        visibility = "(c.member_id = ? OR c.household_visible = 1)"
    else:
        visibility = "c.member_id = ?"

    try:
        rows = await db.execute_fetchall(
            f"SELECT c.*, rank FROM cap_captures_fts fts "
            f"JOIN cap_captures c ON c.rowid = fts.rowid "
            f"WHERE cap_captures_fts MATCH ? AND {visibility} AND c.archived = 0 "
            f"ORDER BY rank LIMIT ?",
            [safe_query, member_id, limit],
        )
        return [dict(r) for r in rows] if rows else []
    except Exception:
        # FTS5 fallback — LIKE search
        like = f"%{safe_query}%"
        rows = await db.execute_fetchall(
            f"SELECT * FROM cap_captures WHERE {visibility} AND archived = 0 "
            f"AND (raw_text LIKE ? OR title LIKE ? OR body LIKE ? OR tags LIKE ?) "
            f"ORDER BY created_at DESC LIMIT ?",
            [member_id, like, like, like, like, limit],
        )
        return [dict(r) for r in rows] if rows else []


# ─── Resurfacing ───

async def get_captures_for_resurfacing(db, member_id: str, limit: int = 3) -> list[dict]:
    """Find captures due for resurfacing: organized, not archived, resurface_after <= now."""
    rows = await db.execute_fetchall(
        "SELECT * FROM cap_captures "
        "WHERE member_id = ? AND archived = 0 AND triage_status = 'organized' "
        "AND resurface_after IS NOT NULL AND resurface_after <= strftime('%Y-%m-%dT%H:%M:%SZ','now') "
        "ORDER BY resurface_after ASC LIMIT ?",
        [member_id, limit],
    )
    return [dict(r) for r in rows] if rows else []


async def mark_resurfaced(db, capture_id: str):
    """Update resurfacing counters after a capture is shown to the user."""
    await db.execute(
        "UPDATE cap_captures SET last_resurfaced_at = strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
        "resurface_count = resurface_count + 1, resurface_after = NULL, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
        [capture_id],
    )
    await db.commit()


# ─── Connections ───

async def add_connection(
    db,
    source_capture_id: str,
    target_type: str,
    target_id: str,
    connection_type: str = "related",
    reason: str | None = None,
    confidence: float = 1.0,
    created_by: str = "system",
) -> int | None:
    """Add a connection from a capture to another entity. Deduplicates via UNIQUE constraint."""
    try:
        cursor = await db.execute(
            "INSERT INTO cap_connections "
            "(source_capture_id, target_type, target_id, connection_type, reason, confidence, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [source_capture_id, target_type, target_id, connection_type, reason, confidence, created_by],
        )
        await db.commit()
        return cursor.lastrowid
    except Exception:
        # UNIQUE constraint violation — connection already exists
        return None


async def get_connections(db, capture_id: str) -> list[dict]:
    """Get all connections for a capture."""
    rows = await db.execute_fetchall(
        "SELECT * FROM cap_connections WHERE source_capture_id = ? ORDER BY created_at DESC",
        [capture_id],
    )
    return [dict(r) for r in rows] if rows else []


async def find_household_connections(db, capture_id: str) -> list[dict]:
    """Find cross-user connections for a household-visible capture via word overlap."""
    capture = await db.execute_fetchone(
        "SELECT * FROM cap_captures WHERE id = ? AND household_visible = 1",
        [capture_id],
    )
    if not capture:
        return []

    # Extract significant words from capture
    text = f"{capture['raw_text']} {capture['title'] or ''} {capture['body'] or ''}"
    words = set(re.findall(r'\b\w{4,}\b', text.lower()))
    if len(words) < 2:
        return []

    # Find other household-visible captures from different members with word overlap
    others = await db.execute_fetchall(
        "SELECT * FROM cap_captures WHERE household_visible = 1 AND member_id != ? "
        "AND archived = 0 ORDER BY created_at DESC LIMIT 100",
        [capture["member_id"]],
    )

    connections = []
    for other in others:
        other_text = f"{other['raw_text']} {other['title'] or ''} {other['body'] or ''}"
        other_words = set(re.findall(r'\b\w{4,}\b', other_text.lower()))
        overlap = len(words & other_words) / max(len(words | other_words), 1)

        if overlap >= 0.2:
            conn_id = await add_connection(
                db, capture_id, "capture", other["id"],
                connection_type="related",
                reason=f"Shared topics: {', '.join(list(words & other_words)[:5])}",
                confidence=min(overlap * 2, 1.0),
                created_by="cross_user_discovery",
            )
            if conn_id:
                connections.append({
                    "connection_id": conn_id,
                    "target_id": other["id"],
                    "overlap": overlap,
                })

    return connections


# ─── Stats ───

async def get_capture_stats(db, member_id: str) -> dict:
    """Get capture statistics for a member."""
    try:
        total = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM cap_captures WHERE member_id = ? AND archived = 0",
            [member_id],
        )
        recent = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM cap_captures WHERE member_id = ? AND archived = 0 "
            "AND created_at > datetime('now', '-7 days')",
            [member_id],
        )
        untriaged = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM cap_captures WHERE member_id = ? "
            "AND triage_status IN ('raw', 'triaged') AND archived = 0",
            [member_id],
        )
        return {
            "total": total["c"] if total else 0,
            "recent_7d": recent["c"] if recent else 0,
            "untriaged": untriaged["c"] if untriaged else 0,
        }
    except Exception:
        return {"total": 0, "recent_7d": 0, "untriaged": 0}
