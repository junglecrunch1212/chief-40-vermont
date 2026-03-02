"""Sensor seed data: all 25 sensors defined, all disabled by default.

Every sensor PIB knows about gets a row in pib_sensor_config at install time.
The settings UI reads this table. Enabling one is just flipping a toggle + providing credentials.
"""

import json
import logging

log = logging.getLogger(__name__)

SENSOR_SEED = [
    # ═══ ENVIRONMENTAL (no member, location-based) ═══
    {
        "sensor_id": "sensor-weather",
        "name": "Weather",
        "category": "environmental",
        "poll_interval_minutes": 30,
        "privacy": "full",
        "layer": 1,
        "description": "Current conditions, forecast, alerts, AQI, pollen, UV",
        "source_type": "api",
        "requires_setup": 1,
        "setup_instructions": "Add OPENWEATHER_API_KEY to .env (free tier: 1000 calls/day)",
    },
    {
        "sensor_id": "sensor-sun",
        "name": "Sunrise/Sunset",
        "category": "environmental",
        "poll_interval_minutes": 1440,
        "privacy": "full",
        "layer": 1,
        "description": "Sunrise, sunset, twilight, day length. Computed locally — no API needed.",
        "source_type": "computed",
        "requires_setup": 0,
        "setup_complete": 1,
    },
    {
        "sensor_id": "sensor-traffic",
        "name": "Traffic",
        "category": "environmental",
        "poll_interval_minutes": 0,
        "privacy": "full",
        "layer": 1,
        "description": "Real-time traffic for upcoming transport events",
        "source_type": "api",
        "requires_setup": 1,
        "setup_instructions": "Uses existing Google Maps API key",
    },
    # ═══ HEALTH (per-member, opt-in) ═══
    {
        "sensor_id": "sensor-health-sleep",
        "name": "Sleep Tracking",
        "category": "health",
        "poll_interval_minutes": 720,
        "privacy": "privileged",
        "layer": 1,
        "description": "Sleep duration, quality, stages. Replaces manual 'sleep rough' command.",
        "source_type": "healthkit",
        "requires_setup": 1,
        "setup_instructions": "Run HealthKitExporter setup. Grant Sleep access.",
    },
    {
        "sensor_id": "sensor-health-activity",
        "name": "Activity",
        "category": "health",
        "poll_interval_minutes": 30,
        "privacy": "full",
        "layer": 2,
        "description": "Steps, workouts, activity rings",
        "source_type": "healthkit",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-health-heart",
        "name": "Heart Rate & HRV",
        "category": "health",
        "poll_interval_minutes": 60,
        "privacy": "privileged",
        "layer": 2,
        "description": "Resting HR, HRV trend. Stress indicator. Watch required.",
        "source_type": "healthkit",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-health-meds",
        "name": "Medication Tracking",
        "category": "health",
        "poll_interval_minutes": 60,
        "privacy": "privileged",
        "layer": 1,
        "description": "Auto-detects medication taken via Health app. Replaces manual 'meds taken'.",
        "source_type": "healthkit",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-health-cycle",
        "name": "Menstrual Cycle",
        "category": "health",
        "poll_interval_minutes": 1440,
        "privacy": "privileged",
        "layer": 3,
        "description": "Cycle tracking from Health app. Energy/mood pattern awareness.",
        "source_type": "healthkit",
        "requires_setup": 1,
        "setup_instructions": "Extremely sensitive. Laura must explicitly opt in.",
    },
    # ═══ DEVICE (per-member) ═══
    {
        "sensor_id": "sensor-apple-focus",
        "name": "Focus Mode",
        "category": "device",
        "poll_interval_minutes": 5,
        "privacy": "full",
        "layer": 1,
        "description": "Current Focus (DND, Work, Sleep, Driving). Affects message delivery.",
        "source_type": "shortcuts",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-apple-battery",
        "name": "Device Battery",
        "category": "device",
        "poll_interval_minutes": 30,
        "privacy": "full",
        "layer": 2,
        "description": "Battery levels. Low battery = reachability risk.",
        "source_type": "shortcuts",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-apple-findmy",
        "name": "Find My",
        "category": "device",
        "poll_interval_minutes": 15,
        "privacy": "privileged",
        "layer": 2,
        "description": "Device + AirTag locations. Feeds location intelligence.",
        "source_type": "shortcuts",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-apple-screentime",
        "name": "Screen Time",
        "category": "device",
        "poll_interval_minutes": 60,
        "privacy": "privileged",
        "layer": 3,
        "description": "Device usage patterns. Optional paralysis detection signal.",
        "source_type": "shortcuts",
        "requires_setup": 1,
    },
    # ═══ HOME (household-level) ═══
    {
        "sensor_id": "sensor-homekit",
        "name": "Smart Home",
        "category": "home",
        "poll_interval_minutes": 5,
        "privacy": "full",
        "layer": 2,
        "description": "Locks, thermostat, cameras, appliances via HomeKit",
        "source_type": "homekit",
        "requires_setup": 1,
        "setup_instructions": "Run HomeKitBridge setup. Grant Home access.",
    },
    {
        "sensor_id": "sensor-wifi-presence",
        "name": "WiFi Presence",
        "category": "home",
        "poll_interval_minutes": 5,
        "privacy": "full",
        "layer": 1,
        "description": "Who's home based on WiFi-connected devices. Simplest presence detection.",
        "source_type": "shell",
        "requires_setup": 1,
        "setup_instructions": "Configure router API or ARP scanning. Map MAC addresses to members.",
    },
    {
        "sensor_id": "sensor-garage-door",
        "name": "Garage Door",
        "category": "home",
        "poll_interval_minutes": 5,
        "privacy": "full",
        "layer": 2,
        "description": "Garage door state. Corroborates departure/arrival rhythms.",
        "source_type": "homekit",
        "requires_setup": 1,
    },
    # ═══ LOGISTICS ═══
    {
        "sensor_id": "sensor-packages",
        "name": "Package Tracking",
        "category": "logistics",
        "poll_interval_minutes": 60,
        "privacy": "full",
        "layer": 2,
        "description": "Delivery tracking from all carriers via AfterShip or Informed Delivery",
        "source_type": "api",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-school-alerts",
        "name": "School Alerts",
        "category": "logistics",
        "poll_interval_minutes": 60,
        "privacy": "full",
        "layer": 1,
        "description": "Closings, delays, early dismissal. Critical coverage impact.",
        "source_type": "api",
        "requires_setup": 1,
        "setup_instructions": "Configure school notification source (RSS, email filter, or API)",
    },
    {
        "sensor_id": "sensor-school-bus",
        "name": "School Bus Tracking",
        "category": "logistics",
        "poll_interval_minutes": 0,
        "privacy": "full",
        "layer": 3,
        "description": "Real-time bus location. Precise pickup timing.",
        "source_type": "api",
        "requires_setup": 1,
        "setup_instructions": "If school offers tracking app/API, configure here.",
    },
    {
        "sensor_id": "sensor-grocery-delivery",
        "name": "Grocery Delivery",
        "category": "logistics",
        "poll_interval_minutes": 15,
        "privacy": "full",
        "layer": 3,
        "description": "Instacart/delivery window tracking",
        "source_type": "api",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-prescription",
        "name": "Prescription Status",
        "category": "logistics",
        "poll_interval_minutes": 360,
        "privacy": "privileged",
        "layer": 3,
        "description": "Rx ready for pickup notifications. CVS/Walgreens text parsing.",
        "source_type": "sms_parse",
        "requires_setup": 1,
    },
    # ═══ VEHICLE ═══
    {
        "sensor_id": "sensor-vehicle-fuel",
        "name": "Vehicle Fuel/Charge",
        "category": "vehicle",
        "poll_interval_minutes": 360,
        "privacy": "full",
        "layer": 3,
        "description": "Fuel level or EV charge. 'Fill up today' suggestions.",
        "source_type": "api",
        "requires_setup": 1,
        "setup_instructions": "If car has connected app (Honda, Subaru), configure API.",
    },
    {
        "sensor_id": "sensor-vehicle-location",
        "name": "Vehicle Location",
        "category": "vehicle",
        "poll_interval_minutes": 15,
        "privacy": "privileged",
        "layer": 2,
        "description": "Where each car is. Inferred from member location or OBD GPS.",
        "source_type": "inferred",
        "requires_setup": 0,
    },
    # ═══ PET ═══
    {
        "sensor_id": "sensor-pet-activity",
        "name": "Captain Activity",
        "category": "pet",
        "poll_interval_minutes": 60,
        "privacy": "full",
        "layer": 3,
        "description": "If Captain has a GPS collar or activity tracker.",
        "source_type": "api",
        "requires_setup": 1,
    },
    # ═══ FINANCIAL ═══
    {
        "sensor_id": "sensor-transaction-alerts",
        "name": "Transaction Alerts",
        "category": "financial",
        "poll_interval_minutes": 0,
        "privacy": "privileged",
        "layer": 2,
        "description": "Real-time transaction notifications from bank/card. Budget impact.",
        "source_type": "webhook",
        "requires_setup": 1,
    },
    {
        "sensor_id": "sensor-bill-due",
        "name": "Bill Due Dates",
        "category": "financial",
        "poll_interval_minutes": 1440,
        "privacy": "privileged",
        "layer": 2,
        "description": "Upcoming bills and payment deadlines",
        "source_type": "api",
        "requires_setup": 1,
    },
]


async def seed_sensors(db) -> int:
    """Insert all sensor configs into pib_sensor_config. Safe to re-run (INSERT OR IGNORE).

    Returns the number of newly inserted sensors.
    """
    inserted = 0
    for sensor in SENSOR_SEED:
        sid = sensor["sensor_id"]
        row = await db.execute_fetchone(
            "SELECT 1 FROM pib_sensor_config WHERE sensor_id = ?", [sid]
        )
        if row:
            continue

        await db.execute(
            """INSERT INTO pib_sensor_config
               (sensor_id, name, category, poll_interval_minutes, privacy, layer,
                description, source_type, requires_setup, setup_complete, setup_instructions,
                enabled_for_members, source_config, required_permissions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                sid,
                sensor["name"],
                sensor["category"],
                sensor.get("poll_interval_minutes", 15),
                sensor.get("privacy", "full"),
                sensor.get("layer", 2),
                sensor.get("description", ""),
                sensor.get("source_type", "api"),
                sensor.get("requires_setup", 1),
                sensor.get("setup_complete", 0),
                sensor.get("setup_instructions"),
                json.dumps(sensor.get("enabled_for_members", [])),
                json.dumps(sensor.get("source_config", {})),
                json.dumps(sensor.get("required_permissions", [])),
            ],
        )
        inserted += 1

    await db.commit()
    log.info(f"Sensor seed: {inserted} new sensors inserted ({len(SENSOR_SEED)} total defined)")
    return inserted
