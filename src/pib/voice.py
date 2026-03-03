"""Voice Intelligence: corpus collection, profile synthesis, profile resolution.

Passively collects outbound message samples (approved drafts, direct replies)
into cos_voice_corpus. Weekly LLM synthesis creates hierarchical voice profiles
in cos_voice_profiles. At draft time, the most specific matching profile is
resolved to guide tone-matched draft generation.

Resolution chain: person > channel_x_type > person_type > domain > channel > baseline
"""

import json
import logging
import os
from datetime import datetime

from pib.db import get_config, next_id
from pib.tz import now_et

log = logging.getLogger(__name__)

# Scope levels for resolution (higher = more specific, wins)
SCOPE_LEVELS = {
    "baseline": 0,
    "channel": 1,
    "domain": 2,
    "person_type": 3,
    "channel_x_type": 4,
    "person": 5,
}


# ─── Privacy Filter ───

PRIVILEGED_DOMAINS = ["evolvefamilylawga.com", "evolve.law"]


def _is_from_privileged_domain(item_ref: str | None, labels: dict | None = None) -> bool:
    """Check if a message is from a privileged domain (Laura's work)."""
    check_values = []
    if item_ref:
        check_values.append(item_ref.lower())
    if labels:
        for v in labels.values():
            if v:
                check_values.append(str(v).lower())
    return any(domain in val for val in check_values for domain in PRIVILEGED_DOMAINS)


# ─── Corpus Collection ───


async def collect_voice_sample(
    db,
    member_id: str,
    body: str,
    channel: str,
    comm_type: str | None = None,
    recipient_type: str | None = None,
    item_ref: str | None = None,
    energy_state: str | None = None,
) -> str:
    """Collect an outbound message sample into the voice corpus.

    Called when:
    - A draft is approved and sent
    - A user writes a direct reply through the system

    This is fire-and-forget — collection failure never blocks the pipeline.
    """
    # Privacy filter: don't store samples from privileged domains
    if _is_from_privileged_domain(item_ref, {"comm_type": comm_type, "recipient_type": recipient_type}):
        log.debug(f"Voice sample filtered: privileged domain for {item_ref}")
        return ""

    sample_id = await next_id(db, "vs")
    word_count = len(body.split())
    formality = _estimate_formality(body)

    labels = json.dumps({
        "channel": channel,
        "comm_type": comm_type,
        "recipient_type": recipient_type,
    })

    await db.execute(
        """INSERT INTO cos_voice_corpus (
            id, member_id, channel, comm_type, recipient_type,
            item_ref, body, word_count, formality_score,
            energy_state, labels
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            sample_id, member_id, channel, comm_type, recipient_type,
            item_ref, body, word_count, formality,
            energy_state, labels,
        ],
    )
    await db.commit()
    log.debug(f"Voice sample collected: {sample_id} ({word_count} words, formality={formality:.2f})")
    return sample_id


def _estimate_formality(text: str) -> float:
    """Quick heuristic formality score: 0.0 (casual) → 1.0 (formal).

    Looks at: greeting style, punctuation, contractions, sentence length, capitalization.
    """
    score = 0.5  # neutral baseline
    lower = text.lower()

    # Casual indicators (reduce score)
    casual_markers = ["lol", "haha", "omg", "btw", "gonna", "wanna", "gotta",
                      "ya", "yep", "nah", "hey!", "yo ", "sup ", "thx", "k "]
    for marker in casual_markers:
        if marker in lower:
            score -= 0.05

    # Formal indicators (increase score)
    formal_markers = ["dear ", "sincerely", "regards", "thank you for",
                      "i appreciate", "please find", "attached", "per our"]
    for marker in formal_markers:
        if marker in lower:
            score += 0.08

    # Contractions = more casual
    contractions = ["don't", "can't", "won't", "i'm", "it's", "he's", "she's",
                    "we're", "they're", "couldn't", "wouldn't", "shouldn't"]
    contraction_count = sum(1 for c in contractions if c in lower)
    score -= contraction_count * 0.02

    # Sentence length — longer sentences trend formal
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    if sentences:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_len > 15:
            score += 0.1
        elif avg_len < 5:
            score -= 0.1

    # Clamp to 0-1
    return max(0.0, min(1.0, score))


# ─── Profile Synthesis ───


async def synthesize_profiles(db, member_id: str) -> int:
    """Rebuild all voice profiles for a member from corpus samples.

    Called weekly by scheduler. Groups corpus samples by scope,
    then uses LLM to summarize writing style at each scope level.

    Returns number of profiles rebuilt.
    """
    min_samples = int(await get_config(db, "voice_profile_min_samples", "15"))
    min_person = int(await get_config(db, "voice_profile_min_person", "5"))

    # Collect all samples for this member
    rows = await db.execute_fetchall(
        "SELECT * FROM cos_voice_corpus WHERE member_id = ? ORDER BY created_at DESC",
        [member_id],
    )
    samples = [dict(r) for r in rows]

    if len(samples) < min_samples:
        log.info(f"Not enough samples for {member_id}: {len(samples)}/{min_samples}")
        return 0

    profiles_rebuilt = 0

    # Baseline profile (all samples)
    if len(samples) >= min_samples:
        await _build_profile(db, member_id, "baseline", SCOPE_LEVELS["baseline"], samples)
        profiles_rebuilt += 1

    # Channel profiles
    by_channel: dict[str, list] = {}
    for s in samples:
        by_channel.setdefault(s["channel"], []).append(s)

    for channel, ch_samples in by_channel.items():
        if len(ch_samples) >= min_samples:
            scope = f"channel:{channel}"
            await _build_profile(db, member_id, scope, SCOPE_LEVELS["channel"], ch_samples)
            profiles_rebuilt += 1

    # Recipient type profiles
    by_type: dict[str, list] = {}
    for s in samples:
        rtype = s.get("recipient_type") or "unknown"
        by_type.setdefault(rtype, []).append(s)

    for rtype, rt_samples in by_type.items():
        if rtype != "unknown" and len(rt_samples) >= min_samples:
            scope = f"person_type:{rtype}"
            await _build_profile(db, member_id, scope, SCOPE_LEVELS["person_type"], rt_samples)
            profiles_rebuilt += 1

    # Per-person profiles (item_ref)
    by_person: dict[str, list] = {}
    for s in samples:
        if s.get("item_ref"):
            by_person.setdefault(s["item_ref"], []).append(s)

    for item_ref, p_samples in by_person.items():
        if len(p_samples) >= min_person:
            scope = f"person:{item_ref}"
            await _build_profile(db, member_id, scope, SCOPE_LEVELS["person"], p_samples)
            profiles_rebuilt += 1

    log.info(f"Rebuilt {profiles_rebuilt} voice profiles for {member_id}")
    return profiles_rebuilt


async def _build_profile(db, member_id: str, scope: str, scope_level: int, samples: list[dict]):
    """Build or update a single voice profile from samples."""
    now = now_et().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Calculate stats
    word_counts = [s["word_count"] for s in samples if s.get("word_count")]
    formalities = [s["formality_score"] for s in samples if s.get("formality_score") is not None]
    avg_length = sum(word_counts) / len(word_counts) if word_counts else 0
    avg_formality = sum(formalities) / len(formalities) if formalities else 0.5

    # Try LLM synthesis for style summary
    style_summary = await _synthesize_style_summary(samples)
    vocabulary = _extract_vocabulary(samples)
    confidence = min(1.0, len(samples) / 30.0)  # Scales up to 30 samples

    # Generate profile ID
    profile_id = await next_id(db, "vp")

    await db.execute(
        """INSERT INTO cos_voice_profiles (
            id, member_id, scope, scope_level, sample_count, confidence,
            style_summary, vocabulary, avg_length, avg_formality,
            rebuilt_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(member_id, scope) DO UPDATE SET
            sample_count = excluded.sample_count,
            confidence = excluded.confidence,
            style_summary = excluded.style_summary,
            vocabulary = excluded.vocabulary,
            avg_length = excluded.avg_length,
            avg_formality = excluded.avg_formality,
            rebuilt_at = excluded.rebuilt_at""",
        [
            profile_id, member_id, scope, scope_level, len(samples),
            confidence, style_summary, json.dumps(vocabulary),
            avg_length, avg_formality, now, now,
        ],
    )
    await db.commit()


# Module-level lazy singleton for Anthropic client
# Note: OpenClaw will replace this with its model routing
_anthropic_client = None


def _get_anthropic_client():
    """Get or create a lazy singleton Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        _anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
    return _anthropic_client


async def _synthesize_style_summary(samples: list[dict]) -> str | None:
    """Use LLM to summarize writing style from samples. Returns None on failure."""
    try:
        client = _get_anthropic_client()
        if not client:
            return _fallback_style_summary(samples)

        # Take a representative subset (max 10 samples)
        subset = samples[:10]
        sample_text = "\n---\n".join(s["body"][:200] for s in subset)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system="Describe this person's writing style in 2-3 sentences. "
                   "Focus on: tone, formality level, typical length, greeting/closing style, "
                   "use of contractions, emoji usage, and any distinctive patterns.",
            messages=[{"role": "user", "content": f"Analyze these message samples:\n\n{sample_text}"}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.warning(f"LLM style synthesis failed: {e}")
        return _fallback_style_summary(samples)


def _fallback_style_summary(samples: list[dict]) -> str:
    """Generate a basic style summary without LLM."""
    word_counts = [s.get("word_count", 0) for s in samples]
    formalities = [s.get("formality_score", 0.5) for s in samples]
    avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
    avg_form = sum(formalities) / len(formalities) if formalities else 0.5

    length_desc = "brief" if avg_words < 15 else "moderate-length" if avg_words < 40 else "detailed"
    tone_desc = "casual" if avg_form < 0.35 else "conversational" if avg_form < 0.65 else "formal"

    return f"Typically writes {length_desc}, {tone_desc} messages averaging {avg_words:.0f} words."


def _extract_vocabulary(samples: list[dict]) -> list[str]:
    """Extract characteristic words/phrases from samples."""
    from collections import Counter

    word_freq: Counter = Counter()
    for s in samples:
        words = s.get("body", "").lower().split()
        word_freq.update(w for w in words if len(w) > 3)

    # Filter to distinctive words (appear in >20% of samples but not >80%)
    total = len(samples)
    distinctive = []
    for word, count in word_freq.most_common(50):
        freq = count / total
        if 0.2 <= freq <= 0.8:
            distinctive.append(word)
        if len(distinctive) >= 20:
            break

    return distinctive


# ─── Profile Resolution ───


async def resolve_voice_profile(
    db,
    member_id: str,
    recipient_item_ref: str | None = None,
    channel: str | None = None,
    recipient_type: str | None = None,
) -> dict | None:
    """Resolve the most specific voice profile for a draft.

    Resolution chain (highest scope_level wins):
    1. person:{item_ref} (scope_level=5)
    2. channel_x_type:{channel}:{type} (scope_level=4)
    3. person_type:{type} (scope_level=3)
    4. domain — not implemented yet (scope_level=2)
    5. channel:{channel} (scope_level=1)
    6. baseline (scope_level=0)
    """
    # Build candidate scopes in priority order
    candidate_scopes = ["baseline"]

    if channel:
        candidate_scopes.append(f"channel:{channel}")

    if recipient_type:
        candidate_scopes.append(f"person_type:{recipient_type}")
        if channel:
            candidate_scopes.append(f"channel_x_type:{channel}:{recipient_type}")

    if recipient_item_ref:
        candidate_scopes.append(f"person:{recipient_item_ref}")

    # Query for matching profiles, ordered by scope_level DESC
    placeholders = ", ".join("?" * len(candidate_scopes))
    rows = await db.execute_fetchall(
        f"""SELECT * FROM cos_voice_profiles
            WHERE member_id = ? AND scope IN ({placeholders})
            ORDER BY scope_level DESC
            LIMIT 1""",
        [member_id] + candidate_scopes,
    )

    if rows:
        profile = dict(rows[0])
        log.debug(f"Resolved voice profile: {profile['scope']} (level={profile['scope_level']})")
        return profile

    return None


async def get_profiles(db, member_id: str) -> list[dict]:
    """Get all voice profiles for a member. For Settings page display."""
    rows = await db.execute_fetchall(
        "SELECT * FROM cos_voice_profiles WHERE member_id = ? ORDER BY scope_level DESC",
        [member_id],
    )
    return [dict(r) for r in rows]


async def get_corpus_stats(db, member_id: str) -> dict:
    """Get corpus statistics for a member."""
    total = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM cos_voice_corpus WHERE member_id = ?",
        [member_id],
    )
    by_channel = await db.execute_fetchall(
        "SELECT channel, COUNT(*) as c FROM cos_voice_corpus "
        "WHERE member_id = ? GROUP BY channel",
        [member_id],
    )

    return {
        "total_samples": total["c"] if total else 0,
        "by_channel": {r["channel"]: r["c"] for r in by_channel},
    }
