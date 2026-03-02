"""Apple Health activity sensor: steps, workouts, activity rings.

Less privacy-sensitive than sleep/heart. Can be 'full' privacy.
Data arrives via webhook from HealthKit or Shortcuts automation.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class AppleHealthActivitySensor:
    sensor_id = "sensor-health-activity"
    name = "Activity Tracking"
    category = "health"
    requires_member = True

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns activity data per member.

        health.activity.summary: {
          "steps": 4500,
          "distance_miles": 2.1,
          "active_calories": 180,
          "exercise_minutes": 22,
          "stand_hours": 6,
          "move_ring_pct": 45,
          "exercise_ring_pct": 73,
          "stand_ring_pct": 50,
          "workouts_today": [
            {"type": "running", "duration_min": 25, "calories": 280,
             "start": "06:30", "end": "06:55"}
          ]
        }

        TTL: 30 min (updates frequently during the day)

        TODO: Webhook-driven — data arrives via POST.
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 30,
            "privacy": "full",
            "layer": 2,
            "enabled_for_members": [],
            "required_permissions": ["healthkit.activity"],
        }

    @staticmethod
    def reading_from_webhook(data: dict, member_id: str) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "steps": data.get("steps"),
            "distance_miles": data.get("distance_miles"),
            "active_calories": data.get("active_calories"),
            "exercise_minutes": data.get("exercise_minutes"),
            "stand_hours": data.get("stand_hours"),
            "move_ring_pct": data.get("move_ring_pct"),
            "exercise_ring_pct": data.get("exercise_ring_pct"),
            "stand_ring_pct": data.get("stand_ring_pct"),
            "workouts_today": data.get("workouts_today", []),
        }

        return SensorReading(
            sensor_id="sensor-health-activity",
            reading_type="health.activity.summary",
            timestamp=now,
            value=value,
            member_id=member_id,
            confidence="high",
            ttl_minutes=30,
        )
