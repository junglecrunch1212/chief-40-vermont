"""Tests for pib.capture — deterministic triage, CRUD, search, notebooks, connections."""

import json

import pytest

from pib.capture import (
    CONTENT_HEURISTICS,
    SYSTEM_NOTEBOOKS,
    TRIAGE_RULES,
    archive_capture,
    create_capture,
    get_capture,
    list_captures,
    search_captures_fts,
    triage_capture,
    update_capture,
    add_connection,
    get_connections,
    get_notebook_list,
    get_capture_stats,
)


class TestTriageCapture:
    """Deterministic triage: same input always produces same output."""

    def test_default_is_note_inbox(self):
        result = triage_capture("just a random thought")
        assert result["capture_type"] == "note"
        assert result["notebook"] == "inbox"
        assert result["priority"] == "normal"

    def test_recipe_prefix(self):
        result = triage_capture("recipe: chicken parmesan with garlic bread")
        assert result["capture_type"] == "recipe"
        assert result["notebook"] == "recipes"
        assert result["cleaned_text"] == "chicken parmesan with garlic bread"

    def test_idea_prefix(self):
        result = triage_capture("idea: build a treehouse for Charlie")
        assert result["capture_type"] == "idea"
        assert result["notebook"] == "ideas"

    def test_bookmark_prefix(self):
        result = triage_capture("bookmark: https://example.com/article")
        assert result["capture_type"] == "bookmark"
        assert result["notebook"] == "bookmarks"

    def test_quote_prefix(self):
        result = triage_capture('quote: "The only way out is through" - Robert Frost')
        assert result["capture_type"] == "quote"
        assert result["notebook"] == "quotes"

    def test_question_prefix(self):
        result = triage_capture("question: how do I set up a 529 plan?")
        assert result["capture_type"] == "question"
        assert result["notebook"] == "questions"

    def test_ref_prefix(self):
        result = triage_capture("ref: Charlie's pediatrician Dr. Chen 404-555-0100")
        assert result["capture_type"] == "reference"
        assert result["notebook"] == "reference"

    def test_important_prefix_high_priority(self):
        result = triage_capture("important: remember to file taxes by April 15")
        assert result["capture_type"] == "note"
        assert result["priority"] == "high"
        assert result["notebook"] == "inbox"

    def test_heuristic_recipe_content(self):
        result = triage_capture("2 cups flour, 1 tsp salt, preheat oven to 350")
        assert result["capture_type"] == "recipe"
        assert result["notebook"] == "recipes"

    def test_heuristic_url_is_bookmark(self):
        result = triage_capture("check out https://example.com/cool-article")
        assert result["capture_type"] == "bookmark"
        assert result["notebook"] == "bookmarks"

    def test_heuristic_question(self):
        result = triage_capture("how do I change the oil in my car?")
        assert result["capture_type"] == "question"
        assert result["notebook"] == "questions"

    def test_determinism(self):
        """Same input always produces same output."""
        for _ in range(10):
            r1 = triage_capture("idea: test determinism")
            r2 = triage_capture("idea: test determinism")
            assert r1 == r2

    def test_prefix_case_insensitive(self):
        r1 = triage_capture("RECIPE: test")
        r2 = triage_capture("recipe: test")
        assert r1["capture_type"] == r2["capture_type"] == "recipe"

    def test_prefix_strips_whitespace(self):
        result = triage_capture("  idea:   spaced out thought  ")
        assert result["capture_type"] == "idea"
        assert result["cleaned_text"] == "spaced out thought"


class TestCreateCapture:
    """create_capture: triage + insert + audit."""

    @pytest.mark.asyncio
    async def test_basic_create(self, db):
        cap = await create_capture(db, "m-james", "test note about groceries")
        assert cap["id"].startswith("cap-")
        assert cap["member_id"] == "m-james"
        assert cap["raw_text"] == "test note about groceries"
        assert cap["triage_status"] == "triaged"

    @pytest.mark.asyncio
    async def test_auto_classification(self, db):
        cap = await create_capture(db, "m-james", "recipe: chocolate chip cookies")
        assert cap["capture_type"] == "recipe"
        assert cap["notebook"] == "recipes"

    @pytest.mark.asyncio
    async def test_household_visible(self, db):
        cap = await create_capture(db, "m-james", "shared family note", household_visible=True)
        assert cap["household_visible"] == 1

    @pytest.mark.asyncio
    async def test_notebooks_seeded(self, db):
        await create_capture(db, "m-james", "trigger notebook seeding")
        notebooks = await get_notebook_list(db, "m-james")
        slugs = {nb["slug"] for nb in notebooks}
        assert "inbox" in slugs
        assert "ideas" in slugs
        assert "recipes" in slugs

    @pytest.mark.asyncio
    async def test_source_preserved(self, db):
        cap = await create_capture(db, "m-james", "from prefix", source="prefix", source_ref="test-key")
        assert cap["source"] == "prefix"
        assert cap["source_ref"] == "test-key"


class TestPrivacy:
    """Private captures hidden from others; household captures visible."""

    @pytest.mark.asyncio
    async def test_private_capture_hidden_from_other(self, db):
        cap = await create_capture(db, "m-james", "private thought")
        # Laura can't see it
        result = await get_capture(db, cap["id"], "m-laura")
        assert result is None

    @pytest.mark.asyncio
    async def test_household_capture_visible(self, db):
        cap = await create_capture(db, "m-james", "shared thought", household_visible=True)
        # Laura CAN see it
        result = await get_capture(db, cap["id"], "m-laura")
        assert result is not None
        assert result["id"] == cap["id"]

    @pytest.mark.asyncio
    async def test_owner_always_sees_capture(self, db):
        cap = await create_capture(db, "m-james", "my thought")
        result = await get_capture(db, cap["id"], "m-james")
        assert result is not None


class TestCaptureUpdate:
    """Update and archive operations."""

    @pytest.mark.asyncio
    async def test_update_title(self, db):
        cap = await create_capture(db, "m-james", "untitled thought")
        updated = await update_capture(db, cap["id"], "m-james", {"title": "My Thought"})
        assert updated["title"] == "My Thought"

    @pytest.mark.asyncio
    async def test_update_tags(self, db):
        cap = await create_capture(db, "m-james", "tagged thought")
        updated = await update_capture(db, cap["id"], "m-james", {"tags": ["test", "important"]})
        assert json.loads(updated["tags"]) == ["test", "important"]

    @pytest.mark.asyncio
    async def test_cannot_update_others_capture(self, db):
        cap = await create_capture(db, "m-james", "james only")
        result = await update_capture(db, cap["id"], "m-laura", {"title": "hacked"})
        assert result is None

    @pytest.mark.asyncio
    async def test_archive(self, db):
        cap = await create_capture(db, "m-james", "to be archived")
        ok = await archive_capture(db, cap["id"], "m-james")
        assert ok is True
        # Archived captures don't appear in list
        caps = await list_captures(db, "m-james")
        assert all(c["id"] != cap["id"] for c in caps)


class TestSearch:
    """List and FTS5 search."""

    @pytest.mark.asyncio
    async def test_list_by_notebook(self, db):
        await create_capture(db, "m-james", "idea: something creative")
        await create_capture(db, "m-james", "just a note")
        ideas = await list_captures(db, "m-james", notebook="ideas")
        assert all(c["notebook"] == "ideas" for c in ideas)

    @pytest.mark.asyncio
    async def test_list_by_type(self, db):
        await create_capture(db, "m-james", "recipe: cookies")
        await create_capture(db, "m-james", "note: something else")
        recipes = await list_captures(db, "m-james", capture_type="recipe")
        assert all(c["capture_type"] == "recipe" for c in recipes)

    @pytest.mark.asyncio
    async def test_fts5_search(self, db):
        await create_capture(db, "m-james", "the quick brown fox jumps over the lazy dog")
        results = await search_captures_fts(db, "quick brown fox", "m-james")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_household_search(self, db):
        await create_capture(db, "m-james", "shared knowledge about gardening", household_visible=True)
        results = await search_captures_fts(db, "gardening", "m-laura", include_household=True)
        assert len(results) >= 1


class TestConnections:
    """Cross-capture and cross-domain connections."""

    @pytest.mark.asyncio
    async def test_add_connection(self, db):
        cap1 = await create_capture(db, "m-james", "first thought")
        cap2 = await create_capture(db, "m-james", "second thought")
        conn_id = await add_connection(db, cap1["id"], "capture", cap2["id"], reason="related topics")
        assert conn_id is not None

    @pytest.mark.asyncio
    async def test_connection_dedup(self, db):
        cap1 = await create_capture(db, "m-james", "alpha")
        cap2 = await create_capture(db, "m-james", "beta")
        id1 = await add_connection(db, cap1["id"], "capture", cap2["id"])
        id2 = await add_connection(db, cap1["id"], "capture", cap2["id"])
        assert id1 is not None
        assert id2 is None  # Duplicate

    @pytest.mark.asyncio
    async def test_get_connections(self, db):
        cap1 = await create_capture(db, "m-james", "source")
        cap2 = await create_capture(db, "m-james", "target")
        await add_connection(db, cap1["id"], "capture", cap2["id"])
        connections = await get_connections(db, cap1["id"])
        assert len(connections) == 1
        assert connections[0]["target_id"] == cap2["id"]


class TestStats:
    """Capture statistics."""

    @pytest.mark.asyncio
    async def test_stats_empty(self, db):
        stats = await get_capture_stats(db, "m-james")
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_stats_with_captures(self, db):
        await create_capture(db, "m-james", "one")
        await create_capture(db, "m-james", "two")
        await create_capture(db, "m-james", "three")
        stats = await get_capture_stats(db, "m-james")
        assert stats["total"] == 3
        assert stats["recent_7d"] == 3
