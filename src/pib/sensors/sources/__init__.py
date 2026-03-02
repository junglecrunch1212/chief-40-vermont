"""Sensor source implementations. Import all sources to trigger @register_sensor."""

from pib.sensors.sources import (
    apple_battery,
    apple_findmy,
    apple_focus,
    apple_health_activity,
    apple_health_heart,
    apple_health_meds,
    apple_health_sleep,
    homekit,
    packages,
    school_alerts,
    sun,
    traffic,
    weather,
    wifi_presence,
)

__all__ = [
    "weather",
    "sun",
    "traffic",
    "apple_health_sleep",
    "apple_health_activity",
    "apple_health_heart",
    "apple_health_meds",
    "apple_focus",
    "apple_battery",
    "apple_findmy",
    "homekit",
    "wifi_presence",
    "packages",
    "school_alerts",
]
