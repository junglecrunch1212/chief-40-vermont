"""Tests for pib.voice — corpus collection, profile synthesis, profile resolution."""

import json

import pytest

from pib.voice import (
    _estimate_formality,
    _extract_vocabulary,
    _fallback_style_summary,
    collect_voice_sample,
    get_corpus_stats,
    get_profiles,
    resolve_voice_profile,
)


# ═══════════════════════════════════════════════════════════
# Formality Estimation
# ═══════════════════════════════════════════════════════════

class TestFormalityEstimation:
    def test_casual_message(self):
        score = _estimate_formality("hey! lol gonna grab lunch wanna come?")
        assert score < 0.4

    def test_formal_message(self):
        score = _estimate_formality(
            "Dear Dr. Park, Thank you for your prompt response. "
            "I appreciate you taking the time to review the documents. Sincerely, James."
        )
        assert score > 0.6

    def test_neutral_message(self):
        score = _estimate_formality("Can you call the plumber about the leak?")
        assert 0.3 <= score <= 0.7

    def test_score_clamped_to_range(self):
        score = _estimate_formality("lol haha omg btw gonna wanna gotta ya yep nah hey! yo sup thx")
        assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════
# Vocabulary Extraction
# ═══════════════════════════════════════════════════════════

class TestVocabularyExtraction:
    def test_extracts_distinctive_words(self):
        samples = [
            {"body": "Thanks for the update on the project"},
            {"body": "Thanks for letting me know about the meeting"},
            {"body": "Thanks, I appreciate the heads up"},
            {"body": "The weather is nice today"},
            {"body": "The project timeline looks good"},
        ]
        vocab = _extract_vocabulary(samples)
        assert isinstance(vocab, list)
        # "thanks" appears in 60% of samples — should be distinctive
        assert "thanks" in vocab

    def test_empty_samples(self):
        vocab = _extract_vocabulary([])
        assert vocab == []


# ═══════════════════════════════════════════════════════════
# Fallback Style Summary
# ═══════════════════════════════════════════════════════════

class TestFallbackStyleSummary:
    def test_generates_description(self):
        samples = [
            {"word_count": 10, "formality_score": 0.3},
            {"word_count": 8, "formality_score": 0.2},
            {"word_count": 12, "formality_score": 0.35},
        ]
        summary = _fallback_style_summary(samples)
        assert "brief" in summary
        assert "casual" in summary

    def test_formal_long_messages(self):
        samples = [
            {"word_count": 50, "formality_score": 0.8},
            {"word_count": 45, "formality_score": 0.75},
        ]
        summary = _fallback_style_summary(samples)
        assert "formal" in summary
        assert "detailed" in summary


# ═══════════════════════════════════════════════════════════
# Corpus Collection
# ═══════════════════════════════════════════════════════════

class TestCorpusCollection:
    async def test_collect_sample(self, db):
        sample_id = await collect_voice_sample(
            db,
            member_id="m-james",
            body="Thanks for the update! I'll check with the plumber tomorrow.",
            channel="imessage",
            comm_type="sms",
            recipient_type="friend",
        )
        assert sample_id.startswith("vs-")

        row = await db.execute_fetchone(
            "SELECT * FROM cos_voice_corpus WHERE id = ?", [sample_id]
        )
        assert row is not None
        assert row["member_id"] == "m-james"
        assert row["channel"] == "imessage"
        assert row["word_count"] > 0
        assert row["formality_score"] is not None

    async def test_corpus_stats(self, db):
        await collect_voice_sample(db, "m-james", "Hello there", "imessage")
        await collect_voice_sample(db, "m-james", "Hi again", "email")
        stats = await get_corpus_stats(db, "m-james")
        assert stats["total_samples"] == 2
        assert stats["by_channel"]["imessage"] == 1
        assert stats["by_channel"]["email"] == 1


# ═══════════════════════════════════════════════════════════
# Profile Resolution
# ═══════════════════════════════════════════════════════════

class TestProfileResolution:
    async def _seed_profile(self, db, scope, scope_level, member="m-james"):
        from pib.db import next_id
        pid = await next_id(db, "vp")
        await db.execute(
            """INSERT INTO cos_voice_profiles
               (id, member_id, scope, scope_level, sample_count, confidence, style_summary)
               VALUES (?, ?, ?, ?, 20, 0.8, 'Test style')""",
            [pid, member, scope, scope_level],
        )
        await db.commit()
        return pid

    async def test_resolve_baseline(self, db):
        await self._seed_profile(db, "baseline", 0)
        profile = await resolve_voice_profile(db, "m-james")
        assert profile is not None
        assert profile["scope"] == "baseline"

    async def test_resolve_most_specific(self, db):
        await self._seed_profile(db, "baseline", 0)
        await self._seed_profile(db, "channel:imessage", 1)
        await self._seed_profile(db, "person:itm-001", 5)

        # With person ref — should get person profile (level 5)
        profile = await resolve_voice_profile(
            db, "m-james",
            recipient_item_ref="itm-001",
            channel="imessage",
        )
        assert profile["scope"] == "person:itm-001"

    async def test_resolve_channel_fallback(self, db):
        await self._seed_profile(db, "baseline", 0)
        await self._seed_profile(db, "channel:imessage", 1)

        profile = await resolve_voice_profile(
            db, "m-james",
            channel="imessage",
        )
        assert profile["scope"] == "channel:imessage"

    async def test_resolve_no_profile(self, db):
        profile = await resolve_voice_profile(db, "m-james")
        assert profile is None

    async def test_get_profiles_list(self, db):
        await self._seed_profile(db, "baseline", 0)
        await self._seed_profile(db, "channel:email", 1)
        profiles = await get_profiles(db, "m-james")
        assert len(profiles) == 2
        # Should be sorted by scope_level DESC
        assert profiles[0]["scope_level"] >= profiles[1]["scope_level"]
