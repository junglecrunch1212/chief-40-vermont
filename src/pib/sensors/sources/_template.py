"""Template for creating a new sensor. Copy this file and fill in the blanks.

Steps to add a new sensor:
  1. Copy this file to a new name (e.g., roomba.py)
  2. Replace YOUR_SENSOR_ID, YOUR_SENSOR_NAME, YOUR_CATEGORY
  3. Implement read() to return SensorReading(s)
  4. Add a seed entry to pib/sensors/seed.py SENSOR_SEED list
  5. Import the new module in pib/sensors/sources/__init__.py
  6. Enable it: UPDATE pib_sensor_config SET enabled=1 WHERE sensor_id='your-id'
  7. (Optional) Add enrichment consumer in pib/sensors/enrichment.py
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


# Uncomment @register_sensor when ready to activate
# @register_sensor
class TemplateSensor:
    sensor_id = "sensor-template"  # Change to your sensor ID
    name = "Template Sensor"       # Human-readable name
    category = "environmental"     # environmental/health/device/home/logistics/vehicle/pet/financial
    requires_member = False        # True if per-member (health), False if environmental

    async def init(self) -> None:
        """Set up connections, validate credentials."""
        pass

    async def read(self) -> list[SensorReading]:
        """Fetch current readings.

        Must be idempotent. Must handle failures gracefully.
        Return [] if no new data.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        value = {
            # Your sensor-specific data here
        }

        return [SensorReading(
            sensor_id=self.sensor_id,
            reading_type="your.reading_type",
            timestamp=now,
            value=value,
            confidence="high",
            ttl_minutes=30,
        )]

    async def ping(self) -> bool:
        """Health check. Can we reach the data source?"""
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 15,
            "privacy": "full",
            "layer": 2,
        }
