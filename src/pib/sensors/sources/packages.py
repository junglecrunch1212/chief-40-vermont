"""Package tracking sensor: delivery tracking from carriers.

Source: AfterShip API (aggregates USPS, UPS, FedEx, Amazon, DHL)
       or individual carrier APIs. Also: USPS Informed Delivery for mail.
"""

import logging
from datetime import datetime, timezone

from pib.sensors.protocol import SensorReading, register_sensor

log = logging.getLogger(__name__)


@register_sensor
class PackageTrackingSensor:
    sensor_id = "sensor-packages"
    name = "Package Tracking"
    category = "logistics"
    requires_member = False

    async def init(self) -> None:
        pass

    async def read(self) -> list[SensorReading]:
        """Returns package delivery status.

        logistics.packages: {
          "expected_today": [
            {"carrier": "amazon", "description": "Crib mattress",
             "window": "2:00 PM - 6:00 PM", "status": "out_for_delivery",
             "requires_someone_home": true},
          ],
          "upcoming": [
            {"carrier": "ups", "description": "Order from REI",
             "expected_date": "2026-03-04", "status": "in_transit"}
          ]
        }

        TTL: 60 min

        TRIGGERS:
          - Package requires signature + nobody home soon → alert
          - Perishable delivery + nobody home → urgent alert

        TODO: Implement via AfterShip API or individual carrier APIs.
        """
        return []

    async def ping(self) -> bool:
        return True

    def get_default_config(self) -> dict:
        return {
            "poll_interval_minutes": 60,
            "privacy": "full",
            "layer": 2,
        }

    @staticmethod
    def reading_from_webhook(data: dict) -> SensorReading:
        """Convert webhook POST data into a SensorReading."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {
            "expected_today": data.get("expected_today", []),
            "upcoming": data.get("upcoming", []),
        }

        return SensorReading(
            sensor_id="sensor-packages",
            reading_type="logistics.packages",
            timestamp=now,
            value=value,
            confidence="high",
            ttl_minutes=60,
        )
