"""Tests for pib.capture_organizer — deep organizer with mocked LLM."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from pib.capture import create_capture
from pib.capture_organizer import (
    _apply_organization,
    get_common_tags,
    organize_batch,
)


class TestApplyOrganization:
    """Organization results are written back correctly."""

    @pytest.mark.asyncio
    async def test_apply_title_and_summary(self, db):
        cap = await create_capture(db, "m-james", "raw thought about cooking")
        org_data = {
            "title": "Cooking Thoughts",
            "summary": "Ideas about cooking techniques",
            "tags": ["cooking", "food"],
            "extracted_entities": [],
            "connections": [],
        }
        await _apply_organization(db, cap["id"], "m-james", org_data)

        row = await db.execute_fetchone(
            "SELECT * FROM cap_captures WHERE id = ?", [cap["id"]]
        )
        assert row["title"] == "Cooking Thoughts"
        assert row["summary"] == "Ideas about cooking techniques"
        assert row["triage_status"] == "organized"
        assert json.loads(row["tags"]) == ["cooking", "food"]

    @pytest.mark.asyncio
    async def test_apply_sets_resurface_after(self, db):
        cap = await create_capture(db, "m-james", "something to resurface")
        await _apply_organization(db, cap["id"], "m-james", {
            "title": "Test", "summary": "Test", "tags": [], "connections": [],
        })

        row = await db.execute_fetchone(
            "SELECT resurface_after FROM cap_captures WHERE id = ?", [cap["id"]]
        )
        assert row["resurface_after"] is not None


class TestGetCommonTags:
    """Tag frequency tracking."""

    @pytest.mark.asyncio
    async def test_empty_tags(self, db):
        tags = await get_common_tags(db, "m-james")
        assert tags == []

    @pytest.mark.asyncio
    async def test_tag_frequency(self, db):
        cap1 = await create_capture(db, "m-james", "one")
        cap2 = await create_capture(db, "m-james", "two")
        cap3 = await create_capture(db, "m-james", "three")

        # Manually set tags
        await db.execute(
            "UPDATE cap_captures SET tags = ? WHERE id = ?",
            [json.dumps(["cooking", "family"]), cap1["id"]],
        )
        await db.execute(
            "UPDATE cap_captures SET tags = ? WHERE id = ?",
            [json.dumps(["cooking", "health"]), cap2["id"]],
        )
        await db.execute(
            "UPDATE cap_captures SET tags = ? WHERE id = ?",
            [json.dumps(["travel"]), cap3["id"]],
        )
        await db.commit()

        tags = await get_common_tags(db, "m-james")
        assert "cooking" in tags
        # Cooking should be first (most frequent)
        assert tags[0] == "cooking"


class TestOrganizeBatch:
    """Batch organizer with config checks."""

    @pytest.mark.asyncio
    async def test_batch_returns_zero_when_nothing_to_organize(self, db):
        count = await organize_batch(db, batch_size=10)
        assert count == 0

    @pytest.mark.asyncio
    async def test_batch_disabled_by_config(self, db):
        await db.execute(
            "INSERT OR REPLACE INTO pib_config (key, value) VALUES ('capture_deep_organizer_enabled', '0')"
        )
        await db.commit()
        await create_capture(db, "m-james", "test")
        count = await organize_batch(db, batch_size=10)
        assert count == 0

    @pytest.mark.asyncio
    async def test_batch_skips_no_api_key(self, db):
        """Without ANTHROPIC_API_KEY, organize returns 0 (graceful)."""
        await create_capture(db, "m-james", "should be organized")
        with patch.dict("os.environ", {}, clear=True):
            count = await organize_batch(db, batch_size=10)
        assert count == 0
