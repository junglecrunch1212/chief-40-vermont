"""Weather sensor: current conditions, forecast, alerts, AQI, pollen, UV.

Source: OpenWeatherMap API (free tier: 1000 calls/day).
Alternatives: NWS API (free, US-only), WeatherKit (Apple, paid).
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class WeatherSensor:
    sensor_id = "sensor-weather"
    name = "Weather"
    category = "environmental"
    requires_member = False

    def __init__(self):
        self.api_key = os.environ.get("OPENWEATHER_API_KEY", "")
        self.lat = os.environ.get("PIB_HOME_LAT", "33.749")
        self.lon = os.environ.get("PIB_HOME_LON", "-84.388")

    async def init(self) -> None:
        if not self.api_key:
            raise ValueError("OPENWEATHER_API_KEY not set")

    async def read(self) -> list[SensorReading]:
        """Fetch current conditions + forecast + alerts.

        TODO: Implement actual OpenWeatherMap API call:
          GET https://api.openweathermap.org/data/3.0/onecall
              ?lat={lat}&lon={lon}&appid={key}&units=imperial

        Returns readings:
          weather.current: temp, feels_like, condition, humidity, wind, UV, AQI, pollen
          weather.forecast: hourly 24h, daily 7d, precipitation windows
          weather.alerts: severe weather alerts
        """
        # TODO: Replace with actual API call using httpx
        # async with httpx.AsyncClient() as client:
        #     resp = await client.get(
        #         "https://api.openweathermap.org/data/3.0/onecall",
        #         params={"lat": self.lat, "lon": self.lon,
        #                 "appid": self.api_key, "units": "imperial"},
        #     )
        #     data = resp.json()

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        readings = []

        # Current conditions reading
        current_value = {
            "temp_f": None,
            "feels_like_f": None,
            "condition": None,
            "condition_text": None,
            "humidity": None,
            "wind_mph": None,
            "wind_direction": None,
            "uv_index": None,
            "visibility_miles": None,
            "precipitation_chance": None,
            "air_quality_index": None,
            "aqi_label": None,
            "pollen": {"tree": None, "grass": None, "ragweed": None},
        }
        readings.append(SensorReading(
            sensor_id=self.sensor_id,
            reading_type="weather.current",
            timestamp=now,
            value=current_value,
            confidence="low",
            ttl_minutes=30,
        ))

        # Forecast reading
        forecast_value = {
            "hourly": [],
            "daily": [],
            "precipitation_windows": [],
        }
        readings.append(SensorReading(
            sensor_id=self.sensor_id,
            reading_type="weather.forecast",
            timestamp=now,
            value=forecast_value,
            confidence="low",
            ttl_minutes=60,
        ))

        return readings

    async def ping(self) -> bool:
        return bool(self.api_key)

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 30,
            "privacy": "full",
            "layer": 1,
            "source_config": {
                "provider": "openweathermap",
                "api_key_env": "OPENWEATHER_API_KEY",
                "location": "from_common_locations.loc-home",
            },
        }
