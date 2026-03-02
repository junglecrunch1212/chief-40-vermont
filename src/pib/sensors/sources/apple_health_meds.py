"""Apple Health medication sensor: auto-detects medication taken via Health app.

Replaces or supplements the manual "meds taken" chat command.
If James logs meds in Apple Health app → PIB picks it up automatically.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class AppleHealthMedicationSensor:
    sensor_id = "sensor-health-meds"
    name = "Medication Tracking"
    category = "health"
    requires_member = True

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns medication status.

        health.medication: {
          "medications": [
            {
              "name": "Vyvanse",
              "scheduled_time": "07:30",
              "taken": true,
              "taken_at": "07:42",
              "logged_by": "apple_health"
            }
          ],
          "all_taken": true,
          "next_due": null,
          "peak_window": {"start": "09:30", "end": "13:00"},
          "crash_window": {"start": "15:00", "end": "17:00"}
        }

        TTL: 60 min
        Privacy: privileged

        INTEGRATION: Feeds directly into compute_energy_level().
        Replaces the manual pib_energy_states.medication_taken field.

        TODO: Webhook-driven — data arrives via POST from HealthKit.
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 60,
            "privacy": "privileged",
            "layer": 1,
            "enabled_for_members": [],
            "required_permissions": ["healthkit.medications"],
        }

    @staticmethod
    def reading_from_webhook(data: dict, member_id: str) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        medications = data.get("medications", [])
        all_taken = all(m.get("taken", False) for m in medications) if medications else False

        value = {
            "medications": medications,
            "all_taken": all_taken,
            "next_due": data.get("next_due"),
            "peak_window": data.get("peak_window"),
            "crash_window": data.get("crash_window"),
        }

        return SensorReading(
            sensor_id="sensor-health-meds",
            reading_type="health.medication",
            timestamp=now,
            value=value,
            member_id=member_id,
            confidence="high",
            ttl_minutes=60,
        )
