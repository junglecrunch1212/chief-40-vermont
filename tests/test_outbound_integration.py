"""Tests for outbound router integration with comms, LLM tools, and proactive."""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch


# ─── Helpers ───


async def _setup_channel_registry(db):
    """Create channel registry tables for testing (may already exist from migrations)."""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS comms_channels (
            id TEXT PRIMARY KEY,
            label TEXT,
            adapter TEXT,
            category TEXT DEFAULT 'conversational',
            enabled INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 50,
            capabilities TEXT DEFAULT '{}',
            behavior TEXT DEFAULT '{}',
            health TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS comms_channel_member_access (
            id TEXT PRIMARY KEY,
            member_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'read',
            show_in_inbox INTEGER DEFAULT 1,
            can_approve_drafts INTEGER DEFAULT 0,
            receives_proactive INTEGER DEFAULT 1,
            digest_include INTEGER DEFAULT 1,
            notify_on_urgent INTEGER DEFAULT 1,
            batch_window TEXT,
            created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            UNIQUE(member_id, channel_id)
        );
    """)
    await db.commit()


async def _insert_draft_comm(db, comm_id="c-test-001", channel="whatsapp_family", member_id="m-james"):
    """Insert a comm with a pending draft."""
    await db.execute(
        """INSERT OR IGNORE INTO ops_comms (id, date, channel, direction, member_id, summary,
           body_snippet, draft_status, draft_response, visibility, needs_response,
           response_urgency, created_by, created_at)
           VALUES (?, '2026-03-04', ?, 'inbound', ?, 'Test comm', 'Test body',
           'pending', 'Draft reply text', 'normal', 1, 'normal', 'test', '2026-03-04T12:00:00Z')""",
        [comm_id, channel, member_id],
    )
    await db.commit()


# ─── Tests ───


@pytest.mark.asyncio
async def test_approve_draft_graceful_fallback_no_registry(db):
    """approve_draft() falls back gracefully when outbound_router fails."""
    await _insert_draft_comm(db)

    from pib.comms import approve_draft
    result = await approve_draft(db, "c-test-001")

    assert result is not None
    assert result["draft_status"] == "approved"
    assert result["id"] == "c-test-001"


@pytest.mark.asyncio
async def test_approve_draft_routes_through_outbound(db):
    """approve_draft() routes through outbound_router when available."""
    await _insert_draft_comm(db, comm_id="c-test-002")

    mock_route = AsyncMock(return_value={
        "status": "sent", "channel_id": "whatsapp_family", "message_id": "msg-1"
    })

    with patch("pib.outbound_router.route_outbound", mock_route):
        from pib.comms import approve_draft
        result = await approve_draft(db, "c-test-002")

    assert result is not None
    assert result["draft_status"] == "approved"
    # The mock was called (outbound routing attempted)
    mock_route.assert_called_once()
    call_kwargs = mock_route.call_args
    assert call_kwargs[1]["message"] == "Draft reply text" or call_kwargs[0][1] == "Draft reply text"


@pytest.mark.asyncio
async def test_determine_best_channel_with_registry(db):
    """determine_best_channel() picks highest-priority channel with write access."""
    await _setup_channel_registry(db)

    await db.execute(
        "INSERT INTO comms_channels (id, label, adapter, enabled, priority) VALUES (?, ?, ?, 1, 10)",
        ["whatsapp_james", "WhatsApp James", "whatsapp"],
    )
    await db.execute(
        "INSERT INTO comms_channels (id, label, adapter, enabled, priority) VALUES (?, ?, ?, 1, 50)",
        ["email_james", "Email James", "gmail"],
    )
    await db.execute(
        "INSERT INTO comms_channel_member_access (id, member_id, channel_id, access_level) VALUES (?, ?, ?, ?)",
        ["acc-1", "m-james", "whatsapp_james", "write"],
    )
    await db.execute(
        "INSERT INTO comms_channel_member_access (id, member_id, channel_id, access_level) VALUES (?, ?, ?, ?)",
        ["acc-2", "m-james", "email_james", "write"],
    )
    await db.commit()

    from pib.comms import determine_best_channel
    channel = await determine_best_channel(db, "m-james")

    assert channel == "whatsapp_james"


@pytest.mark.asyncio
async def test_determine_best_channel_fallback(db):
    """determine_best_channel() falls back to 'imessage' when no registry."""
    from pib.comms import determine_best_channel
    channel = await determine_best_channel(db, "m-nonexistent")
    assert channel == "imessage"


@pytest.mark.asyncio
async def test_member_scoped_inbox(db):
    """get_comms_inbox() scopes to member's accessible channels when registry exists."""
    await _setup_channel_registry(db)

    await db.execute(
        """INSERT INTO ops_comms (id, date, channel, visibility, needs_response, response_urgency,
           direction, created_by, created_at)
           VALUES ('c-scope-1', '2026-03-04', 'whatsapp_family', 'normal', 1, 'normal',
           'inbound', 'test', '2026-03-04T12:00:00Z')""",
    )
    await db.execute(
        """INSERT INTO ops_comms (id, date, channel, visibility, needs_response, response_urgency,
           direction, created_by, created_at)
           VALUES ('c-scope-2', '2026-03-04', 'email_work', 'normal', 1, 'normal',
           'inbound', 'test', '2026-03-04T12:00:00Z')""",
    )
    await db.execute(
        "INSERT INTO comms_channel_member_access (id, member_id, channel_id, access_level, show_in_inbox) VALUES (?, ?, ?, ?, 1)",
        ["acc-scope-1", "m-james", "whatsapp_family", "read"],
    )
    await db.commit()

    from pib.comms import get_comms_inbox
    results = await get_comms_inbox(db, member_id="m-james")

    ids = [r["id"] for r in results]
    assert "c-scope-1" in ids
    assert "c-scope-2" not in ids


@pytest.mark.asyncio
async def test_dispatch_proactive_message(db):
    """dispatch_proactive_message() routes through outbound_router."""
    mock_route = AsyncMock(return_value={
        "status": "sent", "channel_id": "imessage", "message_id": "msg-2"
    })

    with patch("pib.outbound_router.route_outbound", mock_route):
        from pib.comms import dispatch_proactive_message
        result = await dispatch_proactive_message(
            db, "m-james", "Time for your meds!", "medication_not_taken"
        )

    assert result is not None
    assert result["status"] == "sent"
    mock_route.assert_called_once()


@pytest.mark.asyncio
async def test_proactive_dispatch_reexport(db):
    """proactive.dispatch_proactive_message delegates to comms correctly."""
    mock_route = AsyncMock(return_value={
        "status": "sent", "channel_id": "imessage", "message_id": "msg-3"
    })

    with patch("pib.outbound_router.route_outbound", mock_route):
        from pib.proactive import dispatch_proactive_message
        result = await dispatch_proactive_message(
            db, "m-james", "Good morning!", "morning_digest"
        )

    assert result is not None
    assert result["status"] == "sent"
