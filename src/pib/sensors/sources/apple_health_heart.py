"""Apple Health heart rate + HRV sensor. Watch only (James).

Highly sensitive. Always privileged privacy.
Trending HRV is a stress indicator — if declining 3+ days → suggest lighter schedule.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class AppleHealthHeartSensor:
    sensor_id = "sensor-health-heart"
    name = "Heart Rate & HRV"
    category = "health"
    requires_member = True

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns heart rate and HRV data.

        health.heart.summary: {
          "resting_hr": 62,
          "current_hr": 75,
          "hrv_ms": 42,
          "hrv_7day_avg": 45,
          "hrv_trend": "declining",   # stable/improving/declining
          "high_hr_alerts": 0,
          "low_hr_alerts": 0,
        }

        TTL: 60 min
        Privacy: ALWAYS privileged. LLM sees "stress indicators elevated"
                 not "HRV 42ms, resting HR 62"

        TODO: Webhook-driven — data arrives via POST from HealthKit.
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 60,
            "privacy": "privileged",
            "layer": 2,
            "enabled_for_members": [],
            "required_permissions": ["healthkit.heart_rate", "healthkit.hrv"],
        }

    @staticmethod
    def reading_from_webhook(data: dict, member_id: str) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "resting_hr": data.get("resting_hr"),
            "current_hr": data.get("current_hr"),
            "hrv_ms": data.get("hrv_ms"),
            "hrv_7day_avg": data.get("hrv_7day_avg"),
            "hrv_trend": data.get("hrv_trend", "stable"),
            "high_hr_alerts": data.get("high_hr_alerts", 0),
            "low_hr_alerts": data.get("low_hr_alerts", 0),
        }

        return SensorReading(
            sensor_id="sensor-health-heart",
            reading_type="health.heart.summary",
            timestamp=now,
            value=value,
            member_id=member_id,
            confidence="high",
            ttl_minutes=60,
        )
