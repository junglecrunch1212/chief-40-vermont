"""WiFi presence sensor: which devices are on the home network.

Source: Router admin API, ARP table, or Bonjour/mDNS scan.
The cheapest, most reliable presence detector. No GPS, no Apple access needed.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class WifiPresenceSensor:
    sensor_id = "sensor-wifi-presence"
    name = "WiFi Presence"
    category = "home"
    requires_member = False

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns which devices are on the home network.

        home.wifi_presence: {
          "devices_home": ["james_iphone", "james_macbook", "james_watch",
                           "charlie_ipad"],
          "devices_away": ["laura_iphone", "laura_macbook"],
          "members_home": ["m-james", "m-charlie"],
          "members_away": ["m-laura"],
          "unknown_devices": 2
        }

        TTL: 5 min
        Poll: Every 5 min

        Simplest presence detection. High confidence for "home".
        Cannot determine specific location if "away".

        TODO: Implement via:
          - Router API (varies by router model)
          - ARP table scan: `arp -a` → parse MAC addresses → map to members
          - Bonjour/mDNS: scan for known Apple devices on local network
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 5,
            "privacy": "full",
            "layer": 1,
            "source_config": {
                "mac_to_member": {},
                "mac_to_device": {},
            },
        }

    @staticmethod
    def reading_from_webhook(data: dict) -> SensorReading:
        """Convert webhook or scan data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "devices_home": data.get("devices_home", []),
            "devices_away": data.get("devices_away", []),
            "members_home": data.get("members_home", []),
            "members_away": data.get("members_away", []),
            "unknown_devices": data.get("unknown_devices", 0),
        }

        return SensorReading(
            sensor_id="sensor-wifi-presence",
            reading_type="home.wifi_presence",
            timestamp=now,
            value=value,
            confidence="high",
            ttl_minutes=5,
        )
