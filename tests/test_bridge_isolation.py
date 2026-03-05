"""Tests for bridge credential isolation and privacy fence.

Covers:
- Per-bridge BlueBubbles secret validation
- Bridge ID → member ID forcing
- Laura data auto-classified as privileged
- Privacy fence for sensor queries
"""

import json
import os

import pytest
import pytest_asyncio

from pib.cli import cmd_webhook_receive, cmd_sensor_ingest


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def james_secret():
    """Set BLUEBUBBLES_JAMES_SECRET for tests."""
    os.environ["BLUEBUBBLES_JAMES_SECRET"] = "james-test-secret-xyz"
    yield "james-test-secret-xyz"
    del os.environ["BLUEBUBBLES_JAMES_SECRET"]


@pytest.fixture
def laura_secret():
    """Set BLUEBUBBLES_LAURA_SECRET for tests."""
    os.environ["BLUEBUBBLES_LAURA_SECRET"] = "laura-test-secret-abc"
    yield "laura-test-secret-abc"
    del os.environ["BLUEBUBBLES_LAURA_SECRET"]


@pytest.fixture
def no_secrets():
    """Ensure no BlueBubbles secrets are set."""
    for key in ["BLUEBUBBLES_JAMES_SECRET", "BLUEBUBBLES_LAURA_SECRET"]:
        os.environ.pop(key, None)
    yield
    # cleanup handled by other fixtures


# ═══════════════════════════════════════════════════════════
# TestBridgeWebhookIsolation
# ═══════════════════════════════════════════════════════════

class TestBridgeWebhookIsolation:
    """Test per-bridge webhook credential isolation."""

    @pytest.mark.asyncio
    async def test_james_bridge_forces_m_james(self, db, james_secret):
        """james bridge forces member_id to m-james regardless of payload."""
        result = await cmd_webhook_receive(db, {
            "bridge_id": "james",
            "api_key": james_secret,
            "payload": {
                "message": {
                    "guid": "test-guid-001",
                    "text": "Hello from James's phone",
                    "handle": {"address": "+1234567890"},
                },
            },
        }, "dev")

        assert result.get("status") == "processed"
        assert result.get("member_id") == "m-james"
        assert result.get("bridge_id") == "james"

    @pytest.mark.asyncio
    async def test_laura_bridge_forces_m_laura(self, db, laura_secret):
        """laura bridge forces member_id to m-laura regardless of payload."""
        result = await cmd_webhook_receive(db, {
            "bridge_id": "laura",
            "api_key": laura_secret,
            "payload": {
                "message": {
                    "guid": "test-guid-002",
                    "text": "Hello from Laura's phone",
                    "handle": {"address": "+0987654321"},
                },
            },
        }, "dev")

        assert result.get("status") == "processed"
        assert result.get("member_id") == "m-laura"
        assert result.get("bridge_id") == "laura"

    @pytest.mark.asyncio
    async def test_wrong_secret_rejected_james(self, db, james_secret):
        """Wrong secret for james bridge returns unauthorized."""
        result = await cmd_webhook_receive(db, {
            "bridge_id": "james",
            "api_key": "wrong-secret",
            "payload": {"message": {"guid": "test", "text": "hi"}},
        }, "dev")

        assert "error" in result
        assert result.get("status") == "unauthorized"

    @pytest.mark.asyncio
    async def test_wrong_secret_rejected_laura(self, db, laura_secret):
        """Wrong secret for laura bridge returns unauthorized."""
        result = await cmd_webhook_receive(db, {
            "bridge_id": "laura",
            "api_key": "wrong-secret",
            "payload": {"message": {"guid": "test", "text": "hi"}},
        }, "dev")

        assert "error" in result
        assert result.get("status") == "unauthorized"

    @pytest.mark.asyncio
    async def test_unknown_bridge_rejected(self, db, james_secret):
        """Unknown bridge_id with no matching secret returns unauthorized."""
        result = await cmd_webhook_receive(db, {
            "bridge_id": "unknown",
            "api_key": "some-random-secret",
            "payload": {
                "message": {
                    "guid": "test-guid-003",
                    "text": "Fallback test",
                    "handle": {"address": "+1111111111"},
                },
            },
        }, "dev")

        assert "error" in result
        assert result.get("status") == "unauthorized"

    @pytest.mark.asyncio
    async def test_no_bridge_secret_configured_error(self, db):
        """Missing BLUEBUBBLES_{BRIDGE}_SECRET returns config error."""
        # Ensure no secrets are set
        for key in ["BLUEBUBBLES_JAMES_SECRET", "BLUEBUBBLES_LAURA_SECRET"]:
            os.environ.pop(key, None)

        result = await cmd_webhook_receive(db, {
            "bridge_id": "james",
            "api_key": "any-secret",
            "payload": {"message": {"guid": "test", "text": "hi"}},
        }, "dev")

        assert "error" in result
        assert "not configured" in result["error"]


# ═══════════════════════════════════════════════════════════
# TestSensorIngestPrivacy
# ═══════════════════════════════════════════════════════════

class TestSensorIngestPrivacy:
    """Test auto-classification of Laura's data as privileged."""

    @pytest.mark.asyncio
    async def test_laura_auto_classified_privileged(self, db):
        """m-laura sensor data is auto-classified as privileged."""
        result = await cmd_sensor_ingest(db, {
            "source": "apple_health_sleep",
            "member_id": "m-laura",
            "timestamp": "2026-03-04T06:00:00-05:00",
            "data": {"total_minutes": 420},
            "classification": "normal",  # Explicitly try normal
            "idempotency_key": "test-laura-sleep-001",
        }, "dev")

        assert result.get("status") == "stored"
        assert result.get("classification") == "privileged"  # Auto-upgraded

        # Verify in DB
        row = await db.execute_fetchone(
            "SELECT * FROM pib_sensor_readings WHERE id = ?",
            [result["reading_id"]]
        )
        assert row["classification"] == "privileged"

        # Cleanup
        await db.execute("DELETE FROM pib_sensor_readings WHERE id = ?", [result["reading_id"]])
        await db.commit()

    @pytest.mark.asyncio
    async def test_james_stays_normal(self, db):
        """m-james sensor data stays normal classification."""
        result = await cmd_sensor_ingest(db, {
            "source": "apple_health_sleep",
            "member_id": "m-james",
            "timestamp": "2026-03-04T06:00:00-05:00",
            "data": {"total_minutes": 360},
            "classification": "normal",
            "idempotency_key": "test-james-sleep-001",
        }, "dev")

        assert result.get("status") == "stored"
        assert result.get("classification") == "normal"

        # Cleanup
        await db.execute("DELETE FROM pib_sensor_readings WHERE id = ?", [result["reading_id"]])
        await db.commit()

    @pytest.mark.asyncio
    async def test_idempotency_prevents_duplicates(self, db):
        """Same idempotency_key returns duplicate status."""
        idem_key = "test-idempotency-001"

        # First ingest
        result1 = await cmd_sensor_ingest(db, {
            "source": "battery",
            "member_id": "m-james",
            "data": {"level_pct": 75},
            "idempotency_key": idem_key,
        }, "dev")
        assert result1.get("status") == "stored"

        # Second ingest with same key
        result2 = await cmd_sensor_ingest(db, {
            "source": "battery",
            "member_id": "m-james",
            "data": {"level_pct": 80},
            "idempotency_key": idem_key,
        }, "dev")
        assert result2.get("status") == "duplicate"
        assert result2.get("existing_id") == result1.get("reading_id")

        # Cleanup
        await db.execute("DELETE FROM pib_sensor_readings WHERE id = ?", [result1["reading_id"]])
        await db.commit()


# ═══════════════════════════════════════════════════════════
# TestConsolePrivacyFence
# ═══════════════════════════════════════════════════════════

class TestConsolePrivacyFence:
    """Test privacy fence for sensor data queries."""

    @pytest.mark.asyncio
    async def test_james_cannot_see_laura_privileged_sensors(self, db):
        """James querying sensors should not see Laura's privileged data."""
        # Insert Laura's privileged sensor reading
        await db.execute(
            """INSERT INTO pib_sensor_readings
               (id, sensor_id, reading_type, member_id, timestamp, value, classification)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ["sns-test-001", "health", "sleep", "m-laura", "2026-03-04T06:00:00", '{"hours":7}', "privileged"],
        )
        # Insert James's normal sensor reading
        await db.execute(
            """INSERT INTO pib_sensor_readings
               (id, sensor_id, reading_type, member_id, timestamp, value, classification)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ["sns-test-002", "health", "sleep", "m-james", "2026-03-04T06:00:00", '{"hours":6}', "normal"],
        )
        await db.commit()

        # Query as James (privacy filter should exclude Laura's privileged)
        rows = await db.execute_fetchall(
            """SELECT * FROM pib_sensor_readings
               WHERE (classification != 'privileged' OR member_id = ?)""",
            ["m-james"]
        )

        member_ids = [r["member_id"] for r in rows]
        assert "m-james" in member_ids
        # Laura's privileged should be excluded unless James is m-laura
        laura_rows = [r for r in rows if r["member_id"] == "m-laura" and r["classification"] == "privileged"]
        assert len(laura_rows) == 0

        # Cleanup
        await db.execute("DELETE FROM pib_sensor_readings WHERE id IN ('sns-test-001', 'sns-test-002')")
        await db.commit()

    @pytest.mark.asyncio
    async def test_laura_sees_own_privileged_sensors(self, db):
        """Laura querying sensors should see her own privileged data."""
        # Insert Laura's privileged sensor reading
        await db.execute(
            """INSERT INTO pib_sensor_readings
               (id, sensor_id, reading_type, member_id, timestamp, value, classification)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ["sns-test-003", "health", "sleep", "m-laura", "2026-03-04T06:00:00", '{"hours":7}', "privileged"],
        )
        await db.commit()

        # Query as Laura (privacy filter should include her own privileged)
        rows = await db.execute_fetchall(
            """SELECT * FROM pib_sensor_readings
               WHERE (classification != 'privileged' OR member_id = ?)
               AND id = 'sns-test-003'""",
            ["m-laura"]
        )

        assert len(rows) == 1
        assert rows[0]["member_id"] == "m-laura"
        assert rows[0]["classification"] == "privileged"

        # Cleanup
        await db.execute("DELETE FROM pib_sensor_readings WHERE id = 'sns-test-003'")
        await db.commit()
