"""Apple Find My sensor: device and AirTag locations.

Raw coordinates → geofence match → location_id only.
Never stores GPS coordinates. Privacy: privileged.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class AppleFindMySensor:
    sensor_id = "sensor-apple-findmy"
    name = "Find My Locations"
    category = "device"
    requires_member = True

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns device and AirTag locations.

        device.findmy: {
          "devices": {
            "james_iphone": {"location_id": "loc-home", "label": "home"},
            "laura_iphone": {"location_id": "loc-laura-office", "label": "Laura's Office"},
          },
          "airtags": {
            "keys": {"location_id": "loc-home", "label": "home"},
            "charlie_backpack": {"location_id": "loc-school", "label": "school"},
          }
        }

        Feeds into: Location Intelligence system (pib_location_states)
        Privacy: privileged (location data always privileged in LLM context)

        TODO: Implement via Shortcuts automation → POST to webhook.
        Shortcut queries Find My for each device/AirTag, maps coordinates
        to known locations (geofencing), posts location_ids to PIB.
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 15,
            "privacy": "privileged",
            "layer": 2,
        }

    @staticmethod
    def reading_from_webhook(data: dict, member_id: str) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "devices": data.get("devices", {}),
            "airtags": data.get("airtags", {}),
        }

        return SensorReading(
            sensor_id="sensor-apple-findmy",
            reading_type="device.findmy",
            timestamp=now,
            value=value,
            member_id=member_id,
            confidence="high",
            ttl_minutes=15,
        )
