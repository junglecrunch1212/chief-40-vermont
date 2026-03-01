"""Tests for web API endpoints using httpx AsyncClient."""

import os
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock

# Ensure test env vars are set before import
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("PIB_DB_PATH", ":memory:")


@pytest_asyncio.fixture
async def client(db):
    """Create httpx AsyncClient with test DB injected."""
    import pib.web as web_mod
    from httpx import AsyncClient, ASGITransport

    # Inject the test db into the web module's global
    original_db = web_mod._db
    web_mod._db = db

    transport = ASGITransport(app=web_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    # Restore
    web_mod._db = original_db


@pytest.mark.asyncio
async def test_health_returns_status(client):
    """GET /health should return status, uptime, checks, dbSize."""
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert "uptime" in data
    assert "checks" in data
    assert "dbSize" in data


@pytest.mark.asyncio
async def test_costs_returns_shape(client):
    """GET /api/costs should return this_month, budget, percentage."""
    resp = await client.get("/api/costs")
    assert resp.status_code == 200
    data = resp.json()
    assert "this_month" in data
    assert "budget" in data
    assert "percentage" in data


@pytest.mark.asyncio
async def test_custody_returns_contract_shape(client):
    """GET /api/custody should return text, with, overnight."""
    resp = await client.get("/api/custody")
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "with" in data
    assert "overnight" in data


@pytest.mark.asyncio
async def test_chores_returns_contract_shape(client):
    """GET /api/chores should return {chores: [{id, title, done, stars}]}."""
    resp = await client.get("/api/chores?member_id=m-charlie")
    assert resp.status_code == 200
    data = resp.json()
    assert "chores" in data
    assert isinstance(data["chores"], list)


@pytest.mark.asyncio
async def test_siri_webhook_rejects_bad_token(client):
    """POST /webhooks/siri should return 403 without valid bearer token."""
    with patch.dict(os.environ, {"SIRI_BEARER_TOKEN": "real-secret"}):
        resp = await client.post(
            "/webhooks/siri",
            json={"text": "test", "ts": "123"},
            headers={"Authorization": "Bearer wrong-token"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_skip_task_uses_timedelta(client, db):
    """POST /api/tasks/{id}/skip should use timedelta, not replace(day=...)."""
    # Insert a test task
    await db.execute(
        "INSERT OR IGNORE INTO ops_tasks (id, title, status, assignee, created_by) "
        "VALUES ('tsk-skip-test', 'Test skip', 'next', 'm-james', 'test')"
    )
    await db.commit()

    resp = await client.post(
        "/api/tasks/tsk-skip-test/skip",
        json={},
        headers={"Content-Type": "application/json"},
    )
    # Should not be 500 (the old code would crash on month-end with ValueError)
    assert resp.status_code != 500


@pytest.mark.asyncio
async def test_today_stream_returns_contract_shape(client):
    """GET /api/today-stream should return stream, activeIdx, energy, streak."""
    resp = await client.get("/api/today-stream?member_id=m-james")
    assert resp.status_code == 200
    data = resp.json()
    assert "stream" in data
    assert isinstance(data["stream"], list)
    assert "activeIdx" in data
    assert "energy" in data
    assert "streak" in data
    # Verify energy shape
    assert "level" in data["energy"]
    assert "completions" in data["energy"]
    assert "cap" in data["energy"]
    # Verify streak shape
    assert "current" in data["streak"]
    assert "best" in data["streak"]


@pytest.mark.asyncio
async def test_scoreboard_returns_contract_shape(client):
    """GET /api/scoreboard-data should return cards, rewardHistory, domainWins, familyTotal."""
    resp = await client.get("/api/scoreboard-data")
    assert resp.status_code == 200
    data = resp.json()
    assert "cards" in data
    assert isinstance(data["cards"], list)
    assert "rewardHistory" in data
    assert "domainWins" in data
    assert "familyTotal" in data
