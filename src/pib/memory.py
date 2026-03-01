"""Memory system: dedup, negation detection, auto-promote, FTS5 search."""

import logging

log = logging.getLogger(__name__)

# ─── Negation Detection ───

NEGATION_PREFIXES = {
    "not ", "no longer ", "doesn't ", "don't ", "isn't ", "aren't ",
    "stopped ", "quit ", "never ", "can't ", "won't ", "hasn't ", "haven't ",
}


NEGATION_TOKENS = {
    "not", "no", "never", "doesn't", "don't", "isn't", "aren't",
    "stopped", "quit", "can't", "won't", "hasn't", "haven't",
    "wasn't", "weren't",
}


def is_negation_of(new_content: str, existing_content: str) -> bool:
    """Detect when new fact negates existing. 'James doesn't like sushi' vs 'James likes sushi'."""
    new_lower, existing_lower = new_content.lower(), existing_content.lower()

    # Approach 1: prefix-based — "no longer uses Costco" vs "uses Costco"
    for prefix in NEGATION_PREFIXES:
        if new_lower.startswith(prefix) and existing_lower in new_lower[len(prefix):]:
            return True
        if existing_lower.startswith(prefix) and new_lower in existing_lower[len(prefix):]:
            return True

    # Approach 2: one side has negation words, the other doesn't — compare without them
    new_words = new_lower.split()
    existing_words = existing_lower.split()
    new_negs = set(new_words) & NEGATION_TOKENS
    existing_negs = set(existing_words) & NEGATION_TOKENS

    if bool(new_negs) != bool(existing_negs):
        new_filtered = set(w for w in new_words if w not in NEGATION_TOKENS)
        existing_filtered = set(w for w in existing_words if w not in NEGATION_TOKENS)
        overlap = len(new_filtered & existing_filtered) / max(len(new_filtered | existing_filtered), 1)
        if overlap >= 0.5:
            return True

    # Approach 3: high word overlap + negation word in the difference
    new_word_set = set(new_words)
    existing_word_set = set(existing_words)
    overlap = len(new_word_set & existing_word_set) / max(len(new_word_set | existing_word_set), 1)
    if overlap > 0.5 and (new_word_set - existing_word_set) & NEGATION_TOKENS:
        return True

    return False


# ─── Memory Dedup + Save ───

async def save_memory_deduped(
    db, content: str, category: str, domain: str, member_id: str, source: str
) -> dict:
    """Save memory with dedup: reinforce if similar, supersede if contradicted, insert if new."""
    existing = await db.execute_fetchall(
        "SELECT id, content, reinforcement_count FROM mem_long_term "
        "WHERE category = ? AND (domain = ? OR domain IS NULL) AND superseded_by IS NULL",
        [category, domain],
    )

    for row in existing:
        words_new = set(content.lower().split())
        words_existing = set(row["content"].lower().split())
        # Filter negation tokens for overlap — "doesn't" shouldn't reduce similarity
        filtered_new = words_new - NEGATION_TOKENS
        filtered_existing = words_existing - NEGATION_TOKENS
        overlap = len(filtered_new & filtered_existing) / max(len(filtered_new | filtered_existing), 1)

        if overlap > 0.60:
            if is_negation_of(content, row["content"]):
                cursor = await db.execute(
                    "INSERT INTO mem_long_term (content, category, domain, member_id, source) "
                    "VALUES (?,?,?,?,?)",
                    [content, category, domain, member_id, source],
                )
                new_id = cursor.lastrowid
                await db.execute(
                    "UPDATE mem_long_term SET superseded_by = ? WHERE id = ?",
                    [new_id, row["id"]],
                )
                return {"action": "superseded", "old_id": row["id"], "new_id": new_id}
            else:
                await db.execute(
                    "UPDATE mem_long_term SET reinforcement_count = reinforcement_count + 1, "
                    "last_reinforced_at = datetime('now') WHERE id = ?",
                    [row["id"]],
                )
                return {"action": "reinforced", "id": row["id"], "count": row["reinforcement_count"] + 1}
        elif overlap >= 0.40 and is_negation_of(content, row["content"]):
            # Lower threshold for contradiction — "like" vs "likes" reduces raw overlap
            cursor = await db.execute(
                "INSERT INTO mem_long_term (content, category, domain, member_id, source) "
                "VALUES (?,?,?,?,?)",
                [content, category, domain, member_id, source],
            )
            new_id = cursor.lastrowid
            await db.execute(
                "UPDATE mem_long_term SET superseded_by = ? WHERE id = ?",
                [new_id, row["id"]],
            )
            return {"action": "superseded", "old_id": row["id"], "new_id": new_id}

    # New fact — let SQLite AUTOINCREMENT assign the id
    cursor = await db.execute(
        "INSERT INTO mem_long_term (content, category, domain, member_id, source) "
        "VALUES (?,?,?,?,?)",
        [content, category, domain, member_id, source],
    )
    return {"action": "inserted", "id": cursor.lastrowid}


# ─── Auto-Promotion ───

PROMOTION_PATTERNS = {
    "decision": ("decisions", 0.9),
    "preference": ("preferences", 0.8),
    "correction": ("corrections", 1.0),
    "commitment": ("commitments", 0.9),
    "observation": ("observations", 0.7),
}

CONFIDENCE_BOOSTERS = {
    "decision": {"decided", "agreed", "choosing", "going with", "final", "settled"},
    "commitment": {"promise", "committed", "will do", "by friday", "by monday", "deadline"},
    "correction": {"actually", "wrong", "not right", "correction", "update", "changed"},
}


async def auto_promote_session_facts(db) -> dict:
    """Promote high-signal session facts to long-term memory. Runs every 6 hours."""
    facts = await db.execute_fetchall(
        "SELECT * FROM mem_session_facts WHERE auto_promoted = 0 "
        "AND (expires_at IS NULL OR expires_at > datetime('now')) "
        "ORDER BY created_at",
    )

    promoted = 0
    for fact in facts:
        pattern = PROMOTION_PATTERNS.get(fact["fact_type"])
        if not pattern:
            continue

        category, min_confidence = pattern
        confidence = 0.7

        boosters = CONFIDENCE_BOOSTERS.get(fact["fact_type"], set())
        content_lower = fact["content"].lower()
        for keyword in boosters:
            if keyword in content_lower:
                confidence = min(confidence + 0.1, 1.0)

        similar_count = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM mem_session_facts "
            "WHERE fact_type = ? AND content LIKE ? AND id != ?",
            [fact["fact_type"], f"%{fact['content'][:30]}%", fact["id"]],
        )
        if similar_count and similar_count["c"] >= 1:
            confidence = min(confidence + 0.15, 1.0)

        if confidence >= min_confidence:
            await save_memory_deduped(
                db, fact["content"], category, fact["domain"], fact["member_id"], "auto_promoted"
            )
            await db.execute(
                "UPDATE mem_session_facts SET auto_promoted = 1 WHERE id = ?", [fact["id"]]
            )
            promoted += 1

    return {"promoted": promoted}


# ─── FTS5 Search ───

async def search_memory(db, query: str, limit: int = 10) -> list[dict]:
    """Search long-term memory via FTS5."""
    rows = await db.execute_fetchall(
        "SELECT lt.*, rank FROM mem_long_term_fts fts "
        "JOIN mem_long_term lt ON lt.id = fts.rowid "
        "WHERE mem_long_term_fts MATCH ? AND lt.superseded_by IS NULL "
        "ORDER BY rank LIMIT ?",
        [query, limit],
    )
    return [dict(r) for r in rows] if rows else []
