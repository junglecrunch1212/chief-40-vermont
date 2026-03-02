"""Sensor Protocol: SensorReading dataclass, Sensor Protocol, and registry.

Parallel to the Adapter Protocol (ingest.py) but for unidirectional context signals.
Sensors read() environmental/health/device state, emit standardized readings,
and feed into daily_state computation. Lightweight. Stateless. Simple.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class SensorReading:
    """Universal shape for ALL context signals.

    Every sensor in PIB — weather, health, traffic, device — emits this shape.
    """

    sensor_id: str
    reading_type: str
    timestamp: str
    value: dict
    member_id: str | None = None
    location_id: str | None = None
    confidence: str = "high"
    ttl_minutes: int = 30
    idempotency_key: str = ""

    def __post_init__(self):
        if not self.idempotency_key:
            self.idempotency_key = make_reading_key(
                self.sensor_id, self.reading_type, self.timestamp, self.value
            )


@runtime_checkable
class Sensor(Protocol):
    """The Sensor Protocol. Parallel to Adapter Protocol but simpler.

    No send(). No webhooks. Just read + health check.
    """

    sensor_id: str
    name: str
    category: str
    requires_member: bool

    async def init(self) -> None:
        """Set up connections, validate credentials."""
        ...

    async def read(self) -> list[SensorReading]:
        """Fetch current readings. Called on schedule by the sensor bus.

        Returns 0+ readings (0 = no new data, which is fine).
        Must be idempotent. Must handle failures gracefully.
        Must respect TTL — don't re-read if last reading is still valid.
        """
        ...

    async def ping(self) -> bool:
        """Health check. Can we reach the data source?"""
        ...

    def get_default_config(self) -> dict:
        """Returns default sensor configuration for onboarding.

        Includes: poll_interval_minutes, privacy, enabled, required_permissions.
        """
        ...


# === SENSOR REGISTRATION ===

SENSOR_REGISTRY: dict[str, type] = {}


def register_sensor(cls):
    """Decorator. @register_sensor class WeatherSensor: ..."""
    SENSOR_REGISTRY[cls.sensor_id] = cls
    return cls


def make_reading_key(sensor_id: str, reading_type: str, timestamp: str, value: dict) -> str:
    """Generate a SHA256 idempotency key for a sensor reading."""
    import json

    payload = f"{sensor_id}:{reading_type}:{timestamp}:{json.dumps(value, sort_keys=True)}"
    return hashlib.sha256(payload.encode()).hexdigest()
