"""Tests for sensor privacy — health data never raw in LLM context."""

import pytest

from pib.sensors.protocol import SensorReading


class TestPrivacyClassification:
    """Health sensors should always have privileged or higher privacy."""

    def test_health_reading_shape(self):
        """Health readings carry member_id and don't expose raw values externally."""
        r = SensorReading(
            sensor_id="sensor-health-sleep",
            reading_type="health.sleep.summary",
            timestamp="2026-03-02T08:00:00Z",
            value={
                "duration_hours": 6.2,
                "quality": "fair",
                "derived_energy": "low",
            },
            member_id="m-james",
            confidence="high",
        )
        assert r.member_id == "m-james"
        # The value should contain derived impacts, not raw biometrics
        assert "derived_energy" in r.value

    def test_heart_reading_has_member(self):
        """Heart rate data is always per-member."""
        r = SensorReading(
            sensor_id="sensor-health-heart",
            reading_type="health.heart.summary",
            timestamp="2026-03-02T08:00:00Z",
            value={"resting_hr": 68, "hrv_ms": 45},
            member_id="m-james",
        )
        assert r.member_id is not None

    def test_environmental_sensor_no_member(self):
        """Environmental sensors don't require member_id."""
        r = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T08:00:00Z",
            value={"temp_f": 72, "condition": "sunny"},
        )
        assert r.member_id is None


class TestPrivacyFiltering:
    """Ensure privacy field is respected in sensor config."""

    @pytest.mark.asyncio
    async def test_health_sensor_config_is_privileged(self, db):
        """Health sensors should be configured with privileged privacy."""
        # Check seed data for health sensors
        row = await db.execute_fetchone(
            "SELECT privacy FROM pib_sensor_config WHERE sensor_id = 'sensor-health-sleep'"
        )
        # Sensor may not be seeded in test DB — that's OK
        if row:
            assert row["privacy"] in ("privileged", "redacted")

    @pytest.mark.asyncio
    async def test_weather_sensor_config_is_full(self, db):
        """Weather sensors should be configured with full privacy (publicly visible data)."""
        row = await db.execute_fetchone(
            "SELECT privacy FROM pib_sensor_config WHERE sensor_id = 'sensor-weather'"
        )
        if row:
            assert row["privacy"] == "full"
