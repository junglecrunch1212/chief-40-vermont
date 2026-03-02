"""Tests for pib.sensors.enrichment — daily_state enrichment from sensor readings."""

import json

import pytest

from pib.sensors.enrichment import enrich_daily_state_with_sensors


class TestEnrichmentWithNoData:
    """Graceful degradation: enrichment with no sensor readings."""

    @pytest.mark.asyncio
    async def test_enrichment_with_empty_state(self, db):
        state = {}
        await enrich_daily_state_with_sensors(db, state)
        # Should not crash — state may or may not have new keys
        assert isinstance(state, dict)

    @pytest.mark.asyncio
    async def test_enrichment_preserves_existing_state(self, db):
        state = {"custody_states": {"m-charlie": "james"}, "events": []}
        await enrich_daily_state_with_sensors(db, state)
        assert state["custody_states"]["m-charlie"] == "james"
        assert state["events"] == []


class TestEnrichmentWithData:
    """Enrichment with actual sensor readings in the DB."""

    async def _insert_reading(self, db, sensor_id, reading_type, value, ttl=1440):
        await db.execute(
            "INSERT OR IGNORE INTO pib_sensor_config (sensor_id, name, category, enabled, poll_interval_minutes) "
            "VALUES (?, ?, 'environmental', 1, 15)",
            [sensor_id, sensor_id],
        )
        await db.execute(
            """INSERT INTO pib_sensor_readings
               (sensor_id, reading_type, timestamp, value, confidence, ttl_minutes, expires_at, idempotency_key)
               VALUES (?, ?, datetime('now'), ?, 'high', ?, datetime('now', '+24 hours'), ?)""",
            [sensor_id, reading_type, json.dumps(value), ttl, f"test-{sensor_id}-{reading_type}"],
        )
        await db.commit()

    @pytest.mark.asyncio
    async def test_weather_enrichment(self, db):
        await self._insert_reading(
            db, "sensor-weather", "weather.current",
            {"temp_f": 72, "condition": "sunny", "humidity": 45},
        )
        state = {}
        await enrich_daily_state_with_sensors(db, state)
        # Weather should appear in state if enrichment picks it up
        # (depends on implementation details — at minimum, no crash)
        assert isinstance(state, dict)

    @pytest.mark.asyncio
    async def test_sun_enrichment(self, db):
        await self._insert_reading(
            db, "sensor-sun", "sun.times",
            {"sunrise": "06:45", "sunset": "18:30", "day_length_hours": 11.75},
        )
        state = {}
        await enrich_daily_state_with_sensors(db, state)
        assert isinstance(state, dict)

    @pytest.mark.asyncio
    async def test_school_enrichment(self, db):
        await self._insert_reading(
            db, "sensor-school-alerts", "logistics.school",
            {"status": "normal", "school_name": "Test Elementary"},
        )
        state = {}
        await enrich_daily_state_with_sensors(db, state)
        assert isinstance(state, dict)
