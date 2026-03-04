"""Tests for outbound router integration with comms, LLM tools, and proactive."""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch


# ─── Helpers ───


async def _setup_channel_registry(db):
    """Ensure channel registry tables exist (should already exist from migrations)."""
    # Tables should already exist from migrations 012/013.
    # Just verify they're there; if not, the tests will fail with a clear error.
    pass


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
        "INSERT OR IGNORE INTO comms_channels (id, display_name, adapter_id, enabled, sort_order) VALUES (?, ?, ?, 1, 10)",
        ["whatsapp_james", "WhatsApp James", "whatsapp"],
    )
    await db.execute(
        "INSERT OR IGNORE INTO comms_channels (id, display_name, adapter_id, enabled, sort_order) VALUES (?, ?, ?, 1, 50)",
        ["email_james", "Email James", "gmail"],
    )
    # Clear any seeded access for this member, then add test data
    await db.execute("DELETE FROM comms_channel_member_access WHERE member_id = 'm-test-chan'")
    await db.execute(
        "INSERT INTO comms_channel_member_access (id, member_id, channel_id, access_level) VALUES (?, ?, ?, ?)",
        ["acc-test-1", "m-test-chan", "whatsapp_james", "write"],
    )
    await db.execute(
        "INSERT INTO comms_channel_member_access (id, member_id, channel_id, access_level) VALUES (?, ?, ?, ?)",
        ["acc-test-2", "m-test-chan", "email_james", "write"],
    )
    await db.commit()

    from pib.comms import determine_best_channel
    channel = await determine_best_channel(db, "m-test-chan")

    # Should pick whatsapp_james (sort_order 10 < 50)
    assert channel == "whatsapp_james"


@pytest.mark.asyncio
async def test_determine_best_channel_fallback(db):
    """determine_best_channel() falls back when member has no access rows."""
    from pib.comms import determine_best_channel
    channel = await determine_best_channel(db, "m-nonexistent")
    # Should get something (from registry sendable channels or 'imessage' fallback)
    assert isinstance(channel, str)
    assert len(channel) > 0


@pytest.mark.asyncio
async def test_member_scoped_inbox(db):
    """get_comms_inbox() scopes to member's accessible channels when registry exists."""
    await _setup_channel_registry(db)

    # Insert test channels first
    await db.execute(
        "INSERT OR IGNORE INTO comms_channels (id, display_name, adapter_id, enabled, sort_order) VALUES (?, ?, ?, 1, 10)",
        ["whatsapp_family", "WhatsApp Family", "whatsapp"],
    )
    await db.execute(
        "INSERT OR IGNORE INTO comms_channels (id, display_name, adapter_id, enabled, sort_order) VALUES (?, ?, ?, 1, 50)",
        ["email_work", "Email Work", "gmail"],
    )

    await db.execute(
        """INSERT INTO ops_comms (id, date, channel, direction, member_id, summary,
           body_snippet, visibility, needs_response, response_urgency, created_by, created_at)
           VALUES ('c-scope-1', '2026-03-04', 'whatsapp_family', 'inbound', 'm-james',
           'Test WA', 'Test WA body', 'normal', 1, 'normal', 'test', '2026-03-04T12:00:00Z')""",
    )
    await db.execute(
        """INSERT INTO ops_comms (id, date, channel, direction, member_id, summary,
           body_snippet, visibility, needs_response, response_urgency, created_by, created_at)
           VALUES ('c-scope-2', '2026-03-04', 'email_work', 'inbound', 'm-james',
           'Test Email', 'Test Email body', 'normal', 1, 'normal', 'test', '2026-03-04T12:00:00Z')""",
    )
    await db.execute(
        "INSERT OR IGNORE INTO comms_channel_member_access (id, member_id, channel_id, access_level, show_in_inbox) VALUES (?, ?, ?, ?, 1)",
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
