"""Tests for pib.sensors.protocol — SensorReading, Sensor Protocol, registry."""

import hashlib
import json

import pytest

from pib.sensors.protocol import (
    SENSOR_REGISTRY,
    Sensor,
    SensorReading,
    make_reading_key,
    register_sensor,
)


class TestSensorReading:
    def test_basic_shape(self):
        r = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp_f": 72, "condition": "sunny"},
        )
        assert r.sensor_id == "sensor-weather"
        assert r.reading_type == "weather.current"
        assert r.value["temp_f"] == 72
        assert r.confidence == "high"
        assert r.ttl_minutes == 30
        assert r.member_id is None
        assert r.location_id is None

    def test_auto_idempotency_key(self):
        r = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp_f": 72},
        )
        assert r.idempotency_key != ""
        assert len(r.idempotency_key) == 64  # SHA256 hex

    def test_explicit_idempotency_key(self):
        r = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp_f": 72},
            idempotency_key="custom-key",
        )
        assert r.idempotency_key == "custom-key"

    def test_deterministic_idempotency(self):
        """Same inputs always produce same key."""
        r1 = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp_f": 72},
        )
        r2 = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp_f": 72},
        )
        assert r1.idempotency_key == r2.idempotency_key

    def test_different_values_different_keys(self):
        r1 = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp_f": 72},
        )
        r2 = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.current",
            timestamp="2026-03-02T12:00:00Z",
            value={"temp_f": 80},
        )
        assert r1.idempotency_key != r2.idempotency_key

    def test_member_id_and_location(self):
        r = SensorReading(
            sensor_id="sensor-health-sleep",
            reading_type="health.sleep.summary",
            timestamp="2026-03-02T12:00:00Z",
            value={"duration_hours": 7.5},
            member_id="m-james",
            location_id="loc-home",
        )
        assert r.member_id == "m-james"
        assert r.location_id == "loc-home"

    def test_custom_ttl_and_confidence(self):
        r = SensorReading(
            sensor_id="sensor-weather",
            reading_type="weather.forecast",
            timestamp="2026-03-02T12:00:00Z",
            value={},
            confidence="medium",
            ttl_minutes=120,
        )
        assert r.confidence == "medium"
        assert r.ttl_minutes == 120


class TestMakeReadingKey:
    def test_sha256_format(self):
        key = make_reading_key("sensor-weather", "weather.current", "2026-03-02T12:00:00Z", {"temp": 72})
        assert len(key) == 64
        # Verify it's valid hex
        int(key, 16)

    def test_deterministic(self):
        k1 = make_reading_key("s", "t", "ts", {"a": 1})
        k2 = make_reading_key("s", "t", "ts", {"a": 1})
        assert k1 == k2

    def test_order_independent_values(self):
        """JSON sort_keys ensures dict order doesn't matter."""
        k1 = make_reading_key("s", "t", "ts", {"a": 1, "b": 2})
        k2 = make_reading_key("s", "t", "ts", {"b": 2, "a": 1})
        assert k1 == k2


class TestRegisterSensor:
    def test_register_and_retrieve(self):
        # Save and restore registry state
        old_registry = dict(SENSOR_REGISTRY)
        try:
            @register_sensor
            class TestSensor:
                sensor_id = "sensor-test-protocol"
                name = "Test"
                category = "environmental"
                requires_member = False

                async def init(self): pass
                async def read(self): return []
                async def ping(self): return True
                def get_default_config(self): return {}

            assert "sensor-test-protocol" in SENSOR_REGISTRY
            assert SENSOR_REGISTRY["sensor-test-protocol"] is TestSensor
        finally:
            SENSOR_REGISTRY.clear()
            SENSOR_REGISTRY.update(old_registry)

    def test_sensor_protocol_check(self):
        """Verify the Protocol is runtime checkable."""

        class FakeSensor:
            sensor_id = "fake"
            name = "Fake"
            category = "test"
            requires_member = False

            async def init(self): pass
            async def read(self): return []
            async def ping(self): return True
            def get_default_config(self): return {}

        assert isinstance(FakeSensor(), Sensor)
