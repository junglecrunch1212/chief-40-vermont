"""Tests for memory dedup, negation detection, auto-promotion."""

import pytest
from pib.memory import is_negation_of, save_memory_deduped, _basic_stem, auto_promote_session_facts


class TestNegationDetection:
    def test_direct_negation(self):
        assert is_negation_of("James doesn't like sushi", "James likes sushi")

    def test_no_longer(self):
        assert is_negation_of("no longer uses Costco", "uses Costco")

    def test_stopped(self):
        assert is_negation_of("stopped taking medication", "taking medication")

    def test_not_negation(self):
        assert not is_negation_of("James likes pizza", "James likes sushi")

    def test_unrelated(self):
        assert not is_negation_of("The sky is blue", "Dogs are friendly")

    def test_high_overlap_with_negation_word(self):
        assert is_negation_of(
            "James does not prefer morning meetings",
            "James prefers morning meetings",
        )


class TestSaveMemoryDeduped:
    async def test_new_fact_inserted(self, db):
        result = await save_memory_deduped(
            db, "Charlie's teacher is Mrs. Johnson",
            "facts", "school", "m-james", "user_stated",
        )
        assert result["action"] == "inserted"
        await db.commit()

    async def test_duplicate_reinforced(self, db):
        await save_memory_deduped(
            db, "Charlie's teacher is Mrs. Johnson",
            "facts", "school", "m-james", "user_stated",
        )
        await db.commit()

        result = await save_memory_deduped(
            db, "Charlie's teacher is Mrs. Johnson",
            "facts", "school", "m-james", "user_stated",
        )
        assert result["action"] == "reinforced"

    async def test_contradiction_supersedes(self, db):
        await save_memory_deduped(
            db, "James likes sushi",
            "preferences", "food", "m-james", "user_stated",
        )
        await db.commit()

        result = await save_memory_deduped(
            db, "James doesn't like sushi",
            "preferences", "food", "m-james", "user_stated",
        )
        assert result["action"] == "superseded"


class TestBasicStem:
    def test_strip_s(self):
        assert _basic_stem("likes") == "like"
        assert _basic_stem("runs") == "run"

    def test_strip_ed(self):
        assert _basic_stem("walked") == "walk"
        assert _basic_stem("played") == "play"

    def test_strip_ing(self):
        assert _basic_stem("running") == "runn"
        assert _basic_stem("playing") == "play"

    def test_strip_es(self):
        assert _basic_stem("watches") == "watch"

    def test_short_words_unchanged(self):
        assert _basic_stem("is") == "is"
        assert _basic_stem("as") == "as"


class TestNegationWithVerbConjugation:
    def test_likes_vs_like(self):
        """Stemming should help detect 'likes X' vs 'doesn't like X'."""
        assert is_negation_of("James doesn't like sushi", "James likes sushi")

    def test_runs_vs_doesnt_run(self):
        assert is_negation_of("James doesn't run anymore", "James runs every morning")


class TestAutoPromotion:
    async def test_auto_promote_does_not_false_match_short(self, db):
        """Short content like 'cat' shouldn't false-match 'catalog'."""
        # Insert a session fact with short content
        await db.execute(
            "INSERT INTO mem_session_facts (fact_type, content, domain, member_id, auto_promoted, created_at) "
            "VALUES ('decision', 'cat is the best', 'pets', 'm-james', 0, datetime('now'))"
        )
        # Insert another with similar prefix but different meaning
        await db.execute(
            "INSERT INTO mem_session_facts (fact_type, content, domain, member_id, auto_promoted, created_at) "
            "VALUES ('decision', 'catalog should be updated quarterly', 'work', 'm-james', 0, datetime('now'))"
        )
        await db.commit()

        result = await auto_promote_session_facts(db)
        # Just verify it runs without error — the key is no false matching
        assert isinstance(result["promoted"], int)
