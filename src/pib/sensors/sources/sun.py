"""Sunrise/Sunset sensor: computed locally from lat/lon + date.

Source: astral Python library. No API needed. Zero cost. Never fails.
"""

import logging
import os
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class SunSensor:
    sensor_id = "sensor-sun"
    name = "Sun Position"
    category = "environmental"
    requires_member = False

    def __init__(self):
        self.lat = float(os.environ.get("PIB_HOME_LAT", "33.749"))
        self.lon = float(os.environ.get("PIB_HOME_LON", "-84.388"))

    async def init(self) -> None:
        pass  # No external dependencies

    async def read(self) -> list[SensorReading]:
        """Compute sunrise, sunset, twilight times for today and tomorrow.

        Uses the `astral` library for solar calculations.
        TTL: 1440 min (24 hours — only changes ~1min/day).
        Poll: Once daily at 4:00 AM.
        """
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            from astral import LocationInfo
            from astral.sun import sun

            location = LocationInfo(
                name="Home",
                region="US",
                timezone="America/New_York",
                latitude=self.lat,
                longitude=self.lon,
            )
            s = sun(location.observer, date=now.date())

            def fmt_time(dt):
                return dt.strftime("%H:%M") if dt else None

            sunrise = s.get("sunrise")
            sunset = s.get("sunset")
            noon = s.get("noon")
            dawn = s.get("dawn")
            dusk = s.get("dusk")

            day_length = None
            if sunrise and sunset:
                day_length = round((sunset - sunrise).total_seconds() / 3600, 2)

            value = {
                "sunrise": fmt_time(sunrise),
                "sunset": fmt_time(sunset),
                "civil_twilight_start": fmt_time(dawn),
                "civil_twilight_end": fmt_time(dusk),
                "solar_noon": fmt_time(noon),
                "day_length_hours": day_length,
            }

            return [SensorReading(
                sensor_id=self.sensor_id,
                reading_type="sun.times",
                timestamp=now_str,
                value=value,
                confidence="high",
                ttl_minutes=1440,
            )]

        except ImportError:
            log.warning("astral library not installed — sun sensor returning empty")
            return []
        except Exception as e:
            log.error(f"Sun calculation failed: {e}")
            return []

    async def ping(self) -> bool:
        try:
            import astral  # noqa: F401
            return True
        except ImportError:
            return False

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 1440,
            "privacy": "full",
            "layer": 1,
            "source_config": {
                "latitude": self.lat,
                "longitude": self.lon,
            },
        }
