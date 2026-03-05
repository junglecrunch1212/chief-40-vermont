"""Tests for service adapters — Google Calendar, Gmail, BlueBubbles, Twilio, Sheets, Drive, Dispatcher."""

import os
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Ensure test env vars
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("PIB_DB_PATH", ":memory:")


# ═══════════════════════════════════════════════════════════════
# Adapter Registry
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_init_adapters_no_config():
    """init_adapters with no env vars should return all False."""
    from pib.adapters import init_adapters, _adapters
    _adapters.clear()

    with patch.dict(os.environ, {
        "GOOGLE_SA_KEY_PATH": "",
        "BLUEBUBBLES_JAMES_URL": "", "BLUEBUBBLES_JAMES_SECRET": "",
        
        "TWILIO_ACCOUNT_SID": "",
        "TWILIO_AUTH_TOKEN": "",
        "BACKUP_FOLDER_ID": "",
    }, clear=False):
        result = await init_adapters(None)

    assert result["google_calendar"] is False
    assert result["gmail"] is False
    assert result["bluebubbles"] is False
    assert result["twilio"] is False
    _adapters.clear()


@pytest.mark.asyncio
async def test_adapter_registry_get_and_all():
    """get_adapter and all_adapters should work with the registry."""
    from pib.adapters import get_adapter, all_adapters, _adapters

    _adapters.clear()
    assert get_adapter("nonexistent") is None
    assert all_adapters() == {}

    # Register a mock adapter
    _adapters["test"] = MagicMock()
    assert get_adapter("test") is not None
    assert "test" in all_adapters()
    _adapters.clear()


@pytest.mark.asyncio
async def test_health_check_empty():
    """health_check with no adapters should return empty dict."""
    from pib.adapters import health_check, _adapters
    _adapters.clear()
    result = await health_check()
    assert result == {}


@pytest.mark.asyncio
async def test_health_check_with_adapter():
    """health_check should ping registered adapters."""
    from pib.adapters import health_check, _adapters
    _adapters.clear()

    mock_adapter = AsyncMock()
    mock_adapter.ping = AsyncMock(return_value=True)
    _adapters["test_adapter"] = mock_adapter

    result = await health_check()
    assert result["test_adapter"]["ok"] is True
    assert result["test_adapter"]["status"] == "connected"
    _adapters.clear()


# ═══════════════════════════════════════════════════════════════
# Google Calendar Adapter
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_google_calendar_classify_privacy_fence(db):
    """Calendar adapter should redact Laura's work calendar titles."""
    from pib.adapters.google_calendar import GoogleCalendarAdapter

    adapter = GoogleCalendarAdapter()
    adapter._service = MagicMock()  # Won't call API

    # Set up a source marked as Laura's work calendar
    await db.execute(
        "INSERT INTO cal_sources (id, google_calendar_id, for_member_ids, classification_id) "
        "VALUES ('src-work', 'work@group.calendar.google.com', '[\"m-laura\"]', 'work-calendar')"
    )
    await db.commit()

    # Classify an event on that source
    event = {
        "id": "evt1",
        "start": {"dateTime": "2026-03-01T09:00:00-05:00", "date": None},
        "end": {"dateTime": "2026-03-01T10:00:00-05:00"},
        "summary": "Confidential Board Meeting",
    }

    raw_id = "raw-test-1"
    await db.execute(
        "INSERT INTO cal_raw_events (id, source_id, google_event_id, summary, raw_json) "
        "VALUES (?, 'src-work', 'evt1', 'Confidential Board Meeting', ?)",
        [raw_id, json.dumps(event)],
    )
    await db.commit()

    await adapter._classify_event(
        db, raw_id, "src-work", event, 0,
        "2026-03-01T09:00:00-05:00", "2026-03-01T10:00:00-05:00",
        "Confidential Board Meeting"
    )
    await db.commit()

    # The classified event should have redacted title
    row = await db.execute_fetchone(
        "SELECT * FROM cal_classified_events WHERE raw_event_id = ?", [raw_id]
    )
    assert row is not None
    assert row["privacy"] == "redacted"
    assert row["title_redacted"] == "Work event"


@pytest.mark.asyncio
async def test_google_calendar_gene4_no_write():
    """Calendar adapter.send() should raise NotImplementedError (Gene 4)."""
    from pib.adapters.google_calendar import GoogleCalendarAdapter

    adapter = GoogleCalendarAdapter()
    with pytest.raises(NotImplementedError, match="Gene 4"):
        await adapter.send(MagicMock())


# ═══════════════════════════════════════════════════════════════
# BlueBubbles Sender
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_bluebubbles_send():
    """BlueBubbles sender should POST to the correct API endpoint."""
    from pib.adapters.bluebubbles_sender import BlueBubblesSender
    from pib.ingest import OutboundMessage

    with patch.dict(os.environ, {"BLUEBUBBLES_JAMES_URL": "http://localhost:1234", "BLUEBUBBLES_JAMES_SECRET": "test-secret"}):
        sender = BlueBubblesSender()
        sender._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "data": {"guid": "msg-123"}}
        sender._client.post = AsyncMock(return_value=mock_response)

        msg = OutboundMessage(channel="imessage", to="+14045551234", content="Hello!")
        result = await sender.send(msg)

    assert result["ok"] is True
    assert result["message_guid"] == "msg-123"


@pytest.mark.asyncio
async def test_bluebubbles_ping_failure():
    """BlueBubbles ping should return False when server is unreachable."""
    from pib.adapters.bluebubbles_sender import BlueBubblesSender

    with patch.dict(os.environ, {"BLUEBUBBLES_JAMES_URL": "http://localhost:1234", "BLUEBUBBLES_JAMES_SECRET": "secret"}):
        sender = BlueBubblesSender()
        sender._client = AsyncMock()
        sender._client.get = AsyncMock(side_effect=Exception("Connection refused"))

        result = await sender.ping()
    assert result is False


# ═══════════════════════════════════════════════════════════════
# Twilio Sender
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_twilio_send():
    """Twilio sender should POST to the Messages API."""
    from pib.adapters.twilio_sender import TwilioSender
    from pib.ingest import OutboundMessage

    with patch.dict(os.environ, {
        "TWILIO_ACCOUNT_SID": "AC1234",
        "TWILIO_AUTH_TOKEN": "auth-token",
        "TWILIO_PHONE_NUMBER": "+15551234567",
    }):
        sender = TwilioSender()
        sender._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SM123"}
        sender._client.post = AsyncMock(return_value=mock_response)

        msg = OutboundMessage(channel="sms", to="+14045551234", content="Test SMS")
        result = await sender.send(msg)

    assert result["ok"] is True
    assert result["sid"] == "SM123"


@pytest.mark.asyncio
async def test_twilio_send_failure():
    """Twilio send should return ok=False on non-2xx response."""
    from pib.adapters.twilio_sender import TwilioSender
    from pib.ingest import OutboundMessage

    with patch.dict(os.environ, {
        "TWILIO_ACCOUNT_SID": "AC1234",
        "TWILIO_AUTH_TOKEN": "auth-token",
        "TWILIO_PHONE_NUMBER": "+15551234567",
    }):
        sender = TwilioSender()
        sender._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid phone number"
        sender._client.post = AsyncMock(return_value=mock_response)

        msg = OutboundMessage(channel="sms", to="bad-number", content="Test")
        result = await sender.send(msg)

    assert result["ok"] is False


# ═══════════════════════════════════════════════════════════════
# Dispatcher
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_dispatcher_routes_to_correct_adapter():
    """Dispatcher should route imessage to bluebubbles, sms to twilio."""
    from pib.adapters.dispatcher import send_message
    from pib.adapters import _adapters
    from pib.ingest import OutboundMessage

    _adapters.clear()

    mock_bb = AsyncMock()
    mock_bb.send = AsyncMock(return_value={"ok": True})
    _adapters["bluebubbles"] = mock_bb

    msg = OutboundMessage(channel="imessage", to="+14045551234", content="Hi")
    result = await send_message(msg)

    assert result["ok"] is True
    mock_bb.send.assert_called_once()
    _adapters.clear()


@pytest.mark.asyncio
async def test_dispatcher_unknown_channel():
    """Dispatcher should return error for unknown channel."""
    from pib.adapters.dispatcher import send_message
    from pib.ingest import OutboundMessage

    msg = OutboundMessage(channel="carrier_pigeon", to="pigeon-1", content="Coo")
    result = await send_message(msg)

    assert result["ok"] is False
    assert "Unknown channel" in result["error"]


@pytest.mark.asyncio
async def test_dispatcher_no_adapter():
    """Dispatcher should return error when adapter not registered."""
    from pib.adapters.dispatcher import send_message
    from pib.adapters import _adapters
    from pib.ingest import OutboundMessage

    _adapters.clear()
    msg = OutboundMessage(channel="sms", to="+14045551234", content="Hi")
    result = await send_message(msg)

    assert result["ok"] is False
    assert "not available" in result["error"]


@pytest.mark.asyncio
async def test_deliver_to_member(db):
    """deliver_to_member should look up member's preferred channel and send."""
    from pib.adapters.dispatcher import deliver_to_member
    from pib.adapters import _adapters

    _adapters.clear()

    # Set up a mock bluebubbles sender
    mock_bb = AsyncMock()
    mock_bb.send = AsyncMock(return_value={"ok": True})
    _adapters["bluebubbles"] = mock_bb

    # Add phone/channel to member
    await db.execute(
        "UPDATE common_members SET preferred_channel='imessage', phone='+14045551234' WHERE id='m-james'"
    )
    await db.commit()

    result = await deliver_to_member(db, "m-james", "Test message")
    assert result["ok"] is True
    mock_bb.send.assert_called_once()
    _adapters.clear()


@pytest.mark.asyncio
async def test_deliver_to_member_not_found(db):
    """deliver_to_member should error if member not found."""
    from pib.adapters.dispatcher import deliver_to_member

    result = await deliver_to_member(db, "m-nonexistent", "Test")
    assert result["ok"] is False
    assert "not found" in result["error"]


# ═══════════════════════════════════════════════════════════════
# Gmail Adapter
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_gmail_whitelist_matching():
    """Gmail adapter whitelist matching should work for domains and explicit addresses."""
    from pib.adapters.gmail import GmailAdapter

    adapter = GmailAdapter()

    whitelist = [
        {"match_type": "explicit_address", "pattern": "boss@example.com"},
        {"match_type": "domain", "pattern": "school.edu"},
    ]

    assert adapter._matches_whitelist("boss@example.com", whitelist) is True
    assert adapter._matches_whitelist("Jane <boss@example.com>", whitelist) is True
    assert adapter._matches_whitelist("teacher@school.edu", whitelist) is True
    assert adapter._matches_whitelist("random@other.com", whitelist) is False


@pytest.mark.asyncio
async def test_gmail_urgency_check():
    """Gmail adapter should detect urgency from triage keywords."""
    from pib.adapters.gmail import GmailAdapter

    adapter = GmailAdapter()

    keywords = [
        {"keyword": "urgent", "match_field": "subject"},
        {"keyword": "school.edu", "match_field": "from"},
    ]

    assert adapter._check_urgency("Urgent: please respond", "", "", keywords) == "medium"
    assert adapter._check_urgency("Hello", "teacher@school.edu", "", keywords) == "medium"
    assert adapter._check_urgency("Hello", "friend@gmail.com", "", keywords) is None


# ═══════════════════════════════════════════════════════════════
# Google Sheets Adapter
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sheets_push_without_adapter(db):
    """push_to_sheets should work gracefully without sheets adapter."""
    from pib.sheets import push_to_sheets
    from pib.adapters import _adapters
    _adapters.clear()

    result = await push_to_sheets(db)
    # Should return "ready" status for each table (no adapter available)
    for sheet_name, info in result.items():
        assert info["status"] in ("ready", "error")


# ═══════════════════════════════════════════════════════════════
# Google Drive Backup
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_drive_backup_no_db_file():
    """Drive backup should error if database file doesn't exist."""
    from pib.adapters.google_drive import GoogleDriveBackup

    adapter = GoogleDriveBackup()
    adapter._service = MagicMock()

    result = await adapter.upload_backup(db_path="/nonexistent/pib.db")
    assert result["ok"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_drive_backup_not_initialized():
    """Drive backup should error if service not initialized."""
    from pib.adapters.google_drive import GoogleDriveBackup

    adapter = GoogleDriveBackup()
    result = await adapter.upload_backup()
    assert result["ok"] is False
    assert "not initialized" in result["error"]


# ═══════════════════════════════════════════════════════════════
# Scheduler Wiring
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_calendar_sync_skips_without_adapter(db):
    """Calendar sync jobs should skip gracefully when adapter not configured."""
    from pib.adapters import _adapters
    _adapters.clear()

    from pib.scheduler import _calendar_incremental_sync, _calendar_full_sync
    # Should not raise — just log debug message
    await _calendar_incremental_sync(db)
    await _calendar_full_sync(db)


@pytest.mark.asyncio
async def test_gmail_sync_skips_without_adapter(db):
    """Gmail sync should skip gracefully when adapter not configured."""
    from pib.adapters import _adapters
    _adapters.clear()

    from pib.scheduler import _gmail_sync
    await _gmail_sync(db)


@pytest.mark.asyncio
async def test_drive_backup_skips_without_adapter(db):
    """Drive backup should skip gracefully when adapter not configured."""
    from pib.adapters import _adapters
    _adapters.clear()

    from pib.scheduler import _drive_backup
    await _drive_backup(db)


@pytest.mark.asyncio
async def test_scheduler_registers_adapter_jobs(db):
    """Scheduler should register gmail_sync and drive_backup jobs."""
    from pib.scheduler import setup_scheduler

    scheduler = await setup_scheduler(None, db)
    job_ids = [j.id for j in scheduler.get_jobs()]

    assert "gmail_sync" in job_ids
    assert "drive_backup" in job_ids
    assert "calendar_incremental_sync" in job_ids
    assert "calendar_full_sync" in job_ids

    scheduler.shutdown(wait=False)
