"""Tests for memory dedup, negation detection, auto-promotion."""

import pytest
from pib.memory import is_negation_of, save_memory_deduped


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
