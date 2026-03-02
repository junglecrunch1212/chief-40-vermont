"""HomeKit sensor: smart home state via Apple HomeKit.

Mac Mini has native HomeKit access through the Home framework.
Implementation: Swift helper or Shortcuts reading Home state.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class HomeKitSensor:
    sensor_id = "sensor-homekit"
    name = "Smart Home"
    category = "home"
    requires_member = False

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns smart home state.

        home.state: {
          "locks": {
            "front_door": {"locked": false, "last_changed": "15:35",
                          "changed_by": "charlie_iphone"}
          },
          "thermostat": {
            "current_temp": 72, "target_temp": 70, "mode": "cool",
            "occupancy": true
          },
          "garage": {
            "door": "closed", "last_changed": "09:48"
          },
          "cameras": {
            "front_porch": {"last_motion": "14:22", "motion_type": "delivery"}
          },
          "appliances": {
            "washer": {"state": "complete", "completed_at": "13:45"},
            "dryer": {"state": "running", "time_remaining_min": 22}
          }
        }

        TTL: 5 min

        TRIGGERS:
          - Front door unlock at 15:35 on school day → "Charlie's home"
          - Garage door open at 9:48 MWTh → "Laura leaving for office"
          - Washer complete → task suggestion: "Switch laundry to dryer"
          - Dryer complete → task suggestion: "Fold laundry"
          - Front porch motion + delivery window → "Package delivered"

        TODO: Implement via Swift HomeKit bridge or Shortcuts automation webhook.
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 5,
            "privacy": "full",
            "layer": 2,
        }

    @staticmethod
    def reading_from_webhook(data: dict) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "locks": data.get("locks", {}),
            "thermostat": data.get("thermostat", {}),
            "garage": data.get("garage", {}),
            "cameras": data.get("cameras", {}),
            "appliances": data.get("appliances", {}),
        }

        return SensorReading(
            sensor_id="sensor-homekit",
            reading_type="home.state",
            timestamp=now,
            value=value,
            confidence="high",
            ttl_minutes=5,
        )
