"""Apple device battery sensor: battery levels for family devices.

A CoS checks: is someone reachable? Low battery = might go dark = coverage risk.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class AppleBatterySensor:
    sensor_id = "sensor-apple-battery"
    name = "Device Battery"
    category = "device"
    requires_member = True

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns battery levels for member devices.

        device.battery: {
          "devices": {
            "iphone": {"level": 23, "charging": false, "low_power_mode": true},
            "watch": {"level": 45, "charging": false},
            "macbook": {"level": 88, "charging": true}
          },
          "reachability_risk": true  # Any device < 10% and not charging
        }

        TTL: 30 min

        TRIGGER: If primary device < 10% and member has transport duty
                 in next 2 hours → alert.

        TODO: Implement via Shortcuts automation webhook.
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 30,
            "privacy": "full",
            "layer": 2,
        }

    @staticmethod
    def reading_from_webhook(data: dict, member_id: str) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        devices = data.get("devices", {})
        reachability_risk = any(
            d.get("level", 100) < 10 and not d.get("charging", False)
            for d in devices.values()
        )

        value = {
            "devices": devices,
            "reachability_risk": reachability_risk,
        }

        return SensorReading(
            sensor_id="sensor-apple-battery",
            reading_type="device.battery",
            timestamp=now,
            value=value,
            member_id=member_id,
            confidence="high",
            ttl_minutes=30,
        )
