"""Apple Health sleep sensor: sleep duration, quality, stages.

Implementation paths:
  Option A: Swift helper (HealthKitExporter) on Mac Mini → POST to PIB webhook
  Option B: Shortcuts automation "When I wake up" → POST to PIB webhook
  Option C: Health data XML export (manual, most private)

This sensor receives data via webhook POST to /webhooks/sensor/sensor-health-sleep.
The read() method queries the latest webhook-delivered data.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class AppleHealthSleepSensor:
    sensor_id = "sensor-health-sleep"
    name = "Sleep Tracking"
    category = "health"
    requires_member = True

    async def init(self) -> None:
        pass  # Webhook-driven — no outbound connection needed

    async def read(self) -> list[SensorReading]:
        """Returns sleep data per member with health data enabled.

        health.sleep.summary: {
          "date": "2026-03-01",
          "total_hours": 6.5,
          "quality": "fair",        # good/fair/poor
          "deep_sleep_pct": 15,     # Watch only
          "rem_pct": 22,            # Watch only
          "awakenings": 3,          # Watch only
          "sleep_start": "23:15",
          "sleep_end": "05:45",
          "heart_rate_sleeping": 58, # Watch only
          "respiratory_rate": 14,    # Watch only
        }

        TTL: 720 min (12 hours — sleep data is daily)
        Poll: Once at 7:00 AM (after typical wake-up)

        CRITICAL: Feeds directly into compute_energy_level().
        If sleep quality is "poor" → energy capped at "low" for the day.

        TODO: Implement webhook data retrieval. This sensor is populated by
        POST /webhooks/sensor/sensor-health-sleep with HealthKit data.
        """
        # Webhook-driven: data arrives via POST, not polling.
        # read() is a no-op — the webhook handler stores readings directly.
        return []

    async def ping(self) -> bool:
        return True  # Always available — webhook receiver is passive

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 720,
            "privacy": "privileged",
            "layer": 1,
            "enabled_for_members": [],
            "required_permissions": ["healthkit.sleep"],
        }

    @staticmethod
    def reading_from_webhook(data: dict, member_id: str) -> SensorReading:
        """Convert webhook POST data into a SensorReading.

        Called by the webhook endpoint handler.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        total_hours = data.get("total_hours")
        quality = "good"
        if total_hours is not None:
            if total_hours < 5:
                quality = "poor"
            elif total_hours < 7:
                quality = "fair"

        value = {
            "date": data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "total_hours": total_hours,
            "quality": data.get("quality", quality),
            "deep_sleep_pct": data.get("deep_sleep_pct"),
            "rem_pct": data.get("rem_pct"),
            "awakenings": data.get("awakenings"),
            "sleep_start": data.get("sleep_start"),
            "sleep_end": data.get("sleep_end"),
            "heart_rate_sleeping": data.get("heart_rate_sleeping"),
            "respiratory_rate": data.get("respiratory_rate"),
        }

        return SensorReading(
            sensor_id="sensor-health-sleep",
            reading_type="health.sleep.summary",
            timestamp=now,
            value=value,
            member_id=member_id,
            confidence="high",
            ttl_minutes=720,
        )
