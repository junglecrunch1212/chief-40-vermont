"""Traffic sensor: real-time traffic conditions for key routes.

Source: Google Maps Distance Matrix API or Routes API.
On-demand only — polls BEFORE transport events, not constantly.
"""

import logging
import os
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class TrafficSensor:
    sensor_id = "sensor-traffic"
    name = "Traffic Conditions"
    category = "environmental"
    requires_member = False

    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")

    async def init(self) -> None:
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not set")

    async def read(self) -> list[SensorReading]:
        """Called on-demand before transport events.

        TODO: Implement Google Maps Distance Matrix API call:
          GET https://maps.googleapis.com/maps/api/distancematrix/json
              ?origins={origin}&destinations={dest}&departure_time=now&key={key}

        Returns:
          traffic.route: origin, destination, normal_minutes, current_minutes,
                         delay_minutes, delay_reason, suggested_departure, alternative_route
        """
        # On-demand sensor — read() is called with context about the upcoming event.
        # Default read returns empty; use read_for_event() for actual traffic checks.
        return []

    async def read_for_event(self, origin: str, destination: str) -> list[SensorReading]:
        """Fetch traffic for a specific route.

        TODO: Replace with actual Google Maps API call using httpx.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        value = {
            "origin": origin,
            "destination": destination,
            "normal_minutes": None,
            "current_minutes": None,
            "delay_minutes": None,
            "delay_reason": None,
            "suggested_departure": None,
            "alternative_route": None,
        }

        return [SensorReading(
            sensor_id=self.sensor_id,
            reading_type="traffic.route",
            timestamp=now,
            value=value,
            confidence="low",
            ttl_minutes=5,
        )]

    async def ping(self) -> bool:
        return bool(self.api_key)

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 0,
            "privacy": "full",
            "layer": 1,
            "source_config": {
                "provider": "google_maps",
                "api_key_env": "GOOGLE_MAPS_API_KEY",
            },
        }
