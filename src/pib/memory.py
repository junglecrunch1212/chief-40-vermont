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


def _basic_stem(word: str) -> str:
    """Strip common English suffixes for rough word normalization."""
    if word.endswith("ing") and len(word) > 5:
        return word[:-3]
    if word.endswith("ed") and len(word) > 4:
        return word[:-2]
    # Only strip "es" for true -es plurals (watches, dishes, foxes, buzzes)
    if word.endswith("es") and len(word) > 4:
        base = word[:-2]
        if base.endswith(("ch", "sh", "s", "x", "z")):
            return base
    if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        return word[:-1]
    return word


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
        new_filtered = set(_basic_stem(w) for w in new_words if w not in NEGATION_TOKENS)
        existing_filtered = set(_basic_stem(w) for w in existing_words if w not in NEGATION_TOKENS)
        # Use the smaller set as denominator so extra context words don't dilute the match
        min_len = min(len(new_filtered), len(existing_filtered))
        overlap = len(new_filtered & existing_filtered) / max(min_len, 1)
        if overlap >= 0.5:
            return True

    # Approach 3: high word overlap + negation word in the difference
    new_word_set = set(new_words)
    existing_word_set = set(existing_words)
    overlap = len(new_word_set & existing_word_set) / max(len(new_word_set | existing_word_set), 1)
    if overlap > 0.5 and (new_word_set - existing_word_set) & NEGATION_TOKENS:
        return True

    return False


# Stopwords to ignore when comparing sentence structure
_STOPWORDS = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
              "to", "of", "in", "for", "on", "with", "at", "by", "from", "and", "or"}


def has_value_change(new_content: str, existing_content: str) -> bool:
    """Detect when sentence structure is same but a key value differs.

    'James likes sushi' vs 'James likes pizza' — same structure, different object.
    Only triggers when exactly 1-2 content words differ and the rest overlap heavily.
    """
    new_words = [_basic_stem(w) for w in new_content.lower().split() if w not in _STOPWORDS and w not in NEGATION_TOKENS]
    old_words = [_basic_stem(w) for w in existing_content.lower().split() if w not in _STOPWORDS and w not in NEGATION_TOKENS]

    if not new_words or not old_words:
        return False

    new_set, old_set = set(new_words), set(old_words)
    shared = new_set & old_set
    only_new = new_set - old_set
    only_old = old_set - new_set

    # High structural overlap (>= 60% shared) with exactly 1-2 words swapped on each side
    if len(shared) < 1:
        return False
    overlap = len(shared) / max(len(new_set | old_set), 1)
    if overlap >= 0.40 and 0 < len(only_new) <= 2 and 0 < len(only_old) <= 2:
        return True

    return False


# ─── Memory Dedup + Save ───

async def save_memory_deduped(
    db, content: str, category: str, domain: str, member_id: str, source: str
) -> dict:
    """Save memory with dedup: reinforce if similar, supersede if contradicted, insert if new.

    Dedup is scoped to the same member to prevent cross-member interference.
    """
    existing = await db.execute_fetchall(
        "SELECT id, content, reinforcement_count FROM mem_long_term "
        "WHERE category = ? AND (domain = ? OR domain IS NULL) "
        "AND member_id = ? AND superseded_by IS NULL",
        [category, domain, member_id],
    )

    for row in existing:
        words_new = set(content.lower().split())
        words_existing = set(row["content"].lower().split())
        # Filter negation tokens for overlap — "doesn't" shouldn't reduce similarity
        filtered_new = words_new - NEGATION_TOKENS
        filtered_existing = words_existing - NEGATION_TOKENS
        overlap = len(filtered_new & filtered_existing) / max(len(filtered_new | filtered_existing), 1)

        if overlap > 0.60:
            if is_negation_of(content, row["content"]) or has_value_change(content, row["content"]):
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

        # Check for similar facts from the same member using SequenceMatcher
        # (avoids false positives on short content and cross-member contamination)
        from difflib import SequenceMatcher
        similar_rows = await db.execute_fetchall(
            "SELECT content FROM mem_session_facts "
            "WHERE fact_type = ? AND id != ? AND member_id = ?",
            [fact["fact_type"], fact["id"], fact["member_id"]],
        )
        similar_found = 0
        for sr in (similar_rows or []):
            ratio = SequenceMatcher(None, fact["content"].lower(), sr["content"].lower()).ratio()
            if ratio >= 0.6:
                similar_found += 1
        if similar_found >= 1:
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

def _sanitize_fts5_query(query: str) -> str:
    """Sanitize a query string for FTS5 MATCH. Remove special characters."""
    import re
    # Remove FTS5 special characters and keep only words
    words = re.findall(r'\w+', query)
    if not words:
        return ""
    # Join with spaces — FTS5 implicit AND
    return " ".join(words)


async def search_memory(db, query: str, limit: int = 10, member_id: str | None = None) -> list[dict]:
    """Search long-term memory via FTS5, scoped to a member.

    When member_id is provided, only returns memories belonging to that member
    or household-shared memories (member_id IS NULL).
    """
    safe_query = _sanitize_fts5_query(query)
    if not safe_query:
        return []

    member_clause = ""
    params: list = [safe_query]
    if member_id:
        member_clause = " AND (lt.member_id = ? OR lt.member_id IS NULL)"
        params.append(member_id)
    params.append(limit)

    try:
        rows = await db.execute_fetchall(
            "SELECT lt.*, rank FROM mem_long_term_fts fts "
            "JOIN mem_long_term lt ON lt.id = fts.rowid "
            "WHERE mem_long_term_fts MATCH ? AND lt.superseded_by IS NULL"
            f"{member_clause} "
            "ORDER BY rank LIMIT ?",
            params,
        )
        return [dict(r) for r in rows] if rows else []
    except Exception:
        # FTS5 content sync may not be set up — fall back to LIKE search
        like_params: list = [f"%{safe_query}%"]
        like_member = ""
        if member_id:
            like_member = " AND (member_id = ? OR member_id IS NULL)"
            like_params.append(member_id)
        like_params.append(limit)
        rows = await db.execute_fetchall(
            "SELECT * FROM mem_long_term WHERE content LIKE ? AND superseded_by IS NULL"
            f"{like_member} "
            "ORDER BY created_at DESC LIMIT ?",
            like_params,
        )
        return [dict(r) for r in rows] if rows else []
