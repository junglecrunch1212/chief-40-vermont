"""Tests for pib.sensors.bus — SensorBus lifecycle, polling, failure handling."""

import json

import pytest

from pib.sensors.bus import SensorBus
from pib.sensors.protocol import SENSOR_REGISTRY, SensorReading, register_sensor


# ─── Test Sensor Fixture ───

class MockSensor:
    sensor_id = "sensor-mock-test"
    name = "Mock Sensor"
    category = "environmental"
    requires_member = False

    def __init__(self):
        self.readings = []
        self.fail_on_read = False
        self.init_called = False

    async def init(self):
        self.init_called = True

    async def read(self):
        if self.fail_on_read:
            raise RuntimeError("Simulated sensor failure")
        return self.readings

    async def ping(self):
        return True

    def get_default_config(self):
        return {"poll_interval_minutes": 15, "privacy": "full", "layer": 1}


@pytest.fixture
def mock_sensor():
    return MockSensor()


async def _setup_bus(db, mock_sensor_instance):
    """Set up a SensorBus with a mock sensor enabled."""
    # Seed the sensor config
    await db.execute(
        "INSERT OR IGNORE INTO pib_sensor_config (sensor_id, name, category, enabled, poll_interval_minutes, status) "
        "VALUES (?, ?, ?, 1, 15, 'unconfigured')",
        ["sensor-mock-test", "Mock Sensor", "environmental"],
    )
    await db.commit()

    bus = SensorBus(db)
    # Manually inject the mock sensor (bypass registry)
    bus.sensors["sensor-mock-test"] = mock_sensor_instance
    await db.execute(
        "UPDATE pib_sensor_config SET status = 'healthy', consecutive_failures = 0 WHERE sensor_id = 'sensor-mock-test'"
    )
    await db.commit()
    return bus


class TestBusLifecycle:
    @pytest.mark.asyncio
    async def test_start_with_no_enabled_sensors(self, db):
        bus = SensorBus(db)
        await bus.start()
        assert len(bus.sensors) == 0
        assert bus._running is True

    @pytest.mark.asyncio
    async def test_stop(self, db):
        bus = SensorBus(db)
        await bus.start()
        await bus.stop()
        assert bus._running is False
        assert len(bus.sensors) == 0


class TestPolling:
    @pytest.mark.asyncio
    async def test_poll_stores_reading(self, db, mock_sensor):
        bus = await _setup_bus(db, mock_sensor)
        mock_sensor.readings = [
            SensorReading(
                sensor_id="sensor-mock-test",
                reading_type="test.value",
                timestamp="2026-03-02T12:00:00Z",
                value={"temp": 72},
                ttl_minutes=30,
            )
        ]

        await bus.poll_sensor("sensor-mock-test")

        row = await db.execute_fetchone(
            "SELECT * FROM pib_sensor_readings WHERE sensor_id = 'sensor-mock-test'"
        )
        assert row is not None
        assert row["reading_type"] == "test.value"
        value = json.loads(row["value"])
        assert value["temp"] == 72

    @pytest.mark.asyncio
    async def test_poll_deduplicates(self, db, mock_sensor):
        bus = await _setup_bus(db, mock_sensor)
        reading = SensorReading(
            sensor_id="sensor-mock-test",
            reading_type="test.value",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp": 72},
            ttl_minutes=30,
        )
        mock_sensor.readings = [reading]

        await bus.poll_sensor("sensor-mock-test")
        await bus.poll_sensor("sensor-mock-test")

        rows = await db.execute_fetchall(
            "SELECT * FROM pib_sensor_readings WHERE sensor_id = 'sensor-mock-test'"
        )
        assert len(rows) == 1  # Only one stored despite two polls

    @pytest.mark.asyncio
    async def test_poll_nonexistent_sensor(self, db):
        bus = SensorBus(db)
        # Should not raise
        await bus.poll_sensor("sensor-does-not-exist")

    @pytest.mark.asyncio
    async def test_poll_updates_health(self, db, mock_sensor):
        bus = await _setup_bus(db, mock_sensor)
        mock_sensor.readings = [
            SensorReading(
                sensor_id="sensor-mock-test",
                reading_type="test.value",
                timestamp="2026-03-02T12:00:00Z",
                value={"temp": 72},
            )
        ]

        await bus.poll_sensor("sensor-mock-test")

        row = await db.execute_fetchone(
            "SELECT status, consecutive_failures FROM pib_sensor_config WHERE sensor_id = 'sensor-mock-test'"
        )
        assert row["status"] == "healthy"
        assert row["consecutive_failures"] == 0


class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_single_failure_increments_counter(self, db, mock_sensor):
        bus = await _setup_bus(db, mock_sensor)
        mock_sensor.fail_on_read = True

        await bus.poll_sensor("sensor-mock-test")

        row = await db.execute_fetchone(
            "SELECT consecutive_failures, status FROM pib_sensor_config WHERE sensor_id = 'sensor-mock-test'"
        )
        assert row["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_degraded_after_threshold(self, db, mock_sensor):
        bus = await _setup_bus(db, mock_sensor)
        mock_sensor.fail_on_read = True

        # Fail 3 times to trigger degraded
        for _ in range(3):
            await bus.poll_sensor("sensor-mock-test")

        row = await db.execute_fetchone(
            "SELECT status FROM pib_sensor_config WHERE sensor_id = 'sensor-mock-test'"
        )
        assert row["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_disabled_after_many_failures(self, db, mock_sensor):
        bus = await _setup_bus(db, mock_sensor)
        mock_sensor.fail_on_read = True

        # Fail 10 times to trigger disable
        for _ in range(10):
            await bus.poll_sensor("sensor-mock-test")

        row = await db.execute_fetchone(
            "SELECT status, enabled FROM pib_sensor_config WHERE sensor_id = 'sensor-mock-test'"
        )
        assert row["status"] == "disabled"
        assert row["enabled"] == 0
        assert "sensor-mock-test" not in bus.sensors


class TestGetLatestReadings:
    @pytest.mark.asyncio
    async def test_get_latest_empty(self, db):
        bus = SensorBus(db)
        readings = await bus.get_latest_readings()
        assert readings == []

    @pytest.mark.asyncio
    async def test_get_latest_with_data(self, db, mock_sensor):
        from datetime import datetime, timezone
        bus = await _setup_bus(db, mock_sensor)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_sensor.readings = [
            SensorReading(
                sensor_id="sensor-mock-test",
                reading_type="test.value",
                timestamp=now_str,
                value={"temp": 72},
                ttl_minutes=1440,  # 24 hours — won't expire during test
            )
        ]
        await bus.poll_sensor("sensor-mock-test")

        readings = await bus.get_latest_readings(sensor_id="sensor-mock-test")
        assert len(readings) >= 1
        assert readings[0]["sensor_id"] == "sensor-mock-test"
        assert readings[0]["value"]["temp"] == 72
        assert "age_minutes" in readings[0]
        assert "is_stale" in readings[0]
        assert "is_fresh" in readings[0]


class TestGetReadingHistory:
    @pytest.mark.asyncio
    async def test_history_empty(self, db):
        bus = SensorBus(db)
        history = await bus.get_reading_history("sensor-mock-test", hours=24)
        assert history == []

    @pytest.mark.asyncio
    async def test_history_with_data(self, db, mock_sensor):
        from datetime import datetime, timezone
        bus = await _setup_bus(db, mock_sensor)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_sensor.readings = [
            SensorReading(
                sensor_id="sensor-mock-test",
                reading_type="test.value",
                timestamp=now_str,
                value={"temp": 72},
                ttl_minutes=1440,  # ensure not expired during test
            )
        ]
        await bus.poll_sensor("sensor-mock-test")

        history = await bus.get_reading_history("sensor-mock-test", hours=24)
        assert len(history) >= 1
