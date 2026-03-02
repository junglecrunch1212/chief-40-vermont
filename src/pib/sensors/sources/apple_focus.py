"""Apple Focus Mode sensor: current Focus state for each family member.

Accessed via Shortcuts automation or `shortcuts` CLI on Mac Mini.
When Laura is in "Do Not Disturb" → PIB doesn't send non-urgent messages.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class AppleFocusModeSensor:
    sensor_id = "sensor-apple-focus"
    name = "Focus Mode"
    category = "device"
    requires_member = True

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns current Focus mode per member.

        device.focus: {
          "active_focus": "driving",  # or null, "do_not_disturb", "work",
                                       # "sleep", "personal", "fitness"
          "since": "09:48",
          "inferred_state": "commuting"
        }

        TTL: 5 min (focus changes are instant)

        INTEGRATION:
          "driving" → member is commuting, don't send non-urgent messages
          "sleep" → member is asleep, update sleep rhythm data
          "work" → member is in work mode, respect boundaries
          "do_not_disturb" → reduce notifications
          null → normal availability

        TODO: Implement via Shortcuts CLI or Shortcuts automation webhook.
        macOS: `shortcuts run "Get Focus Mode"` → parse output
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 5,
            "privacy": "full",
            "layer": 1,
        }

    @staticmethod
    def reading_from_webhook(data: dict, member_id: str) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        focus = data.get("active_focus")
        inferred = None
        if focus == "driving":
            inferred = "commuting"
        elif focus == "sleep":
            inferred = "sleeping"
        elif focus == "work":
            inferred = "working"

        value = {
            "active_focus": focus,
            "since": data.get("since"),
            "inferred_state": inferred,
        }

        return SensorReading(
            sensor_id="sensor-apple-focus",
            reading_type="device.focus",
            timestamp=now,
            value=value,
            member_id=member_id,
            confidence="high",
            ttl_minutes=5,
        )
