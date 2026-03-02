"""Tests for graceful degradation — system works fine with zero sensors."""

import pytest

from pib.engine import compute_complexity_score, compute_energy_level, what_now, DBSnapshot
from pib.sensors.bus import SensorBus


class TestZeroSensors:
    """All core functions work when no sensors are active."""

    @pytest.mark.asyncio
    async def test_sensor_bus_starts_with_no_sensors(self, db):
        bus = SensorBus(db)
        await bus.start()
        assert len(bus.sensors) == 0
        assert bus._running is True
        await bus.stop()

    @pytest.mark.asyncio
    async def test_get_latest_readings_empty(self, db):
        bus = SensorBus(db)
        readings = await bus.get_latest_readings()
        assert readings == []

    @pytest.mark.asyncio
    async def test_get_reading_history_empty(self, db):
        bus = SensorBus(db)
        history = await bus.get_reading_history("sensor-weather", hours=24)
        assert history == []

    @pytest.mark.asyncio
    async def test_get_active_alerts_empty(self, db):
        bus = SensorBus(db)
        alerts = await bus.get_active_alerts()
        assert alerts == []


class TestComplexityWithoutSensors:
    """compute_complexity_score works without any sensor data."""

    def test_empty_state(self):
        score = compute_complexity_score({})
        assert score == 0.0

    def test_calendar_only(self):
        state = {
            "events": [
                {"scheduling_impact": "HARD_BLOCK"},
                {"scheduling_impact": "SOFT_BLOCK"},
            ],
            "overdue_tasks": 2,
        }
        score = compute_complexity_score(state)
        assert score > 0
        # No environmental modifiers applied
        expected = 1.0 + 0.5 + 0.4  # HARD + SOFT + 2*0.2
        assert abs(score - expected) < 0.01


class TestWhatNowWithoutSensors:
    """whatNow() works without sensor infrastructure."""

    def test_what_now_basic(self, snapshot):
        result = what_now("m-james", snapshot)
        # Should return a result without crashing
        assert result is not None
        assert isinstance(result.the_one_task, (dict, type(None)))


class TestEnergyWithoutSensors:
    def test_energy_level_without_sensor_data(self):
        """compute_energy_level works without any sensor health data."""
        level = compute_energy_level(
            energy_state=None,
            member={"id": "m-james"},
        )
        assert level in ("low", "medium", "high")


class TestEnrichmentGracefulDegradation:
    """Sensor enrichment doesn't crash when sensor tables have no data."""

    @pytest.mark.asyncio
    async def test_enrichment_no_crash(self, db):
        from pib.sensors.enrichment import enrich_daily_state_with_sensors
        state = {"custody_states": {}, "events": []}
        # Should not raise even with no sensor readings
        await enrich_daily_state_with_sensors(db, state)
        assert isinstance(state, dict)
