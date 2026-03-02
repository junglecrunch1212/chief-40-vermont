"""School alerts sensor: closings, delays, early dismissals.

Source: School website RSS/API, email parsing, or manual entry.
CRITICAL: School delay/closing completely changes the day's coverage.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class SchoolAlertSensor:
    sensor_id = "sensor-school-alerts"
    name = "School Alerts"
    category = "logistics"
    requires_member = False

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns school status.

        logistics.school: {
          "status": "normal",         # normal/delayed/closed/early_dismissal
          "delay_hours": 0,
          "adjusted_start": null,
          "adjusted_end": null,
          "alerts": [],
          "upcoming": [
            {"date": "2026-03-05", "type": "half_day",
             "dismissal": "12:00", "note": "Teacher workday"}
          ]
        }

        TTL: 60 min (check morning, then hourly)

        CRITICAL IMPACT: School delay/closing completely changes the day.
          - 2-hour delay → Charlie home until 10:30 → coverage shift
          - Closed → full day coverage needed → rhythm override
          - Early dismissal → pickup time changes → transport adjustment

        This overrides school-related rhythms automatically.

        TODO: Implement via school notification source:
          - RSS feed from school website
          - Email filter (Gmail adapter can flag school emails)
          - School district API (if available)
          - Manual entry via chat command
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 60,
            "privacy": "full",
            "layer": 1,
        }

    @staticmethod
    def reading_from_webhook(data: dict) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "status": data.get("status", "normal"),
            "delay_hours": data.get("delay_hours", 0),
            "adjusted_start": data.get("adjusted_start"),
            "adjusted_end": data.get("adjusted_end"),
            "alerts": data.get("alerts", []),
            "upcoming": data.get("upcoming", []),
        }

        return SensorReading(
            sensor_id="sensor-school-alerts",
            reading_type="logistics.school",
            timestamp=now,
            value=value,
            confidence="high",
            ttl_minutes=60,
        )
