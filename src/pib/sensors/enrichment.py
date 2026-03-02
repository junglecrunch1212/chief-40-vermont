"""Sensor enrichment layer: feeds sensor readings into daily_state.

Each enrich_* function queries pib_sensor_readings for latest data.
If no readings exist (sensor not enabled), the function is a no-op.
Graceful degradation by default.
"""

import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


async def enrich_daily_state_with_sensors(db, state: dict) -> dict:
    """Main entry point: enrich daily_state with all available sensor data.

    Called by _compute_daily_states() in scheduler.py after calendar/custody computation.
    Each sub-enrichment is independent — failure in one doesn't affect others.
    """
    enrichers = [
        enrich_weather,
        enrich_sun,
        enrich_school,
        enrich_deliveries,
        enrich_health,
        enrich_ambient,
    ]

    for enricher in enrichers:
        try:
            await enricher(db, state)
        except Exception as e:
            log.warning(f"Sensor enrichment {enricher.__name__} failed: {e}")

    return state


async def enrich_weather(db, state: dict):
    """Add weather context to daily_state."""
    reading = await _get_latest_reading(db, "sensor-weather", "weather.current")
    if not reading:
        return

    value = reading["value"]
    forecast = await _get_latest_reading(db, "sensor-weather", "weather.forecast")
    alerts_reading = await _get_latest_reading(db, "sensor-weather", "weather.alerts")

    # Determine outdoor suitability
    outdoor = "good"
    temp = value.get("temp_f")
    if temp is not None:
        if temp > 95 or temp < 25:
            outdoor = "dangerous"
        elif temp > 90 or temp < 32:
            outdoor = "poor"
        elif value.get("precipitation_chance", 0) > 50:
            outdoor = "poor"
        elif value.get("uv_index", 0) >= 8 or value.get("precipitation_chance", 0) > 30:
            outdoor = "good_with_caution"

    impacts = []
    if value.get("uv_index", 0) >= 6:
        impacts.append(f"UV index {value['uv_index']} — sunscreen recommended")
    pollen = value.get("pollen", {})
    if any(v == "high" for v in pollen.values() if v):
        high_types = [k for k, v in pollen.items() if v == "high"]
        impacts.append(f"Pollen high ({', '.join(high_types)})")
    if value.get("precipitation_chance", 0) > 40:
        impacts.append("Rain likely — bring umbrella")

    precip_windows = []
    if forecast:
        precip_windows = forecast["value"].get("precipitation_windows", [])

    state["weather"] = {
        "summary": _build_weather_summary(value),
        "outdoor_suitability": outdoor,
        "uv_index": value.get("uv_index"),
        "pollen": value.get("pollen"),
        "precipitation_windows": precip_windows,
        "alerts": alerts_reading["value"] if alerts_reading else [],
        "impacts": impacts,
    }


async def enrich_sun(db, state: dict):
    """Add sun times to daily_state."""
    reading = await _get_latest_reading(db, "sensor-sun", "sun.times")
    if not reading:
        return

    value = reading["value"]
    impacts = []
    sunset = value.get("sunset")
    if sunset:
        impacts.append(f"Outdoor activities should wrap up by {sunset}")

    state["sun"] = {
        "sunrise": value.get("sunrise"),
        "sunset": sunset,
        "outdoor_window_hours": value.get("day_length_hours"),
        "impacts": impacts,
    }


async def enrich_school(db, state: dict):
    """Add school status to daily_state."""
    reading = await _get_latest_reading(db, "sensor-school-alerts", "logistics.school")
    if not reading:
        state["school_status"] = {"status": "unknown", "adjustments": []}
        return

    value = reading["value"]
    adjustments = []
    status = value.get("status", "normal")
    if status == "delayed":
        hours = value.get("delay_hours", 0)
        adjustments.append(f"{hours}-hour delay — adjusted start: {value.get('adjusted_start')}")
    elif status == "closed":
        adjustments.append("School closed — full day coverage needed")
    elif status == "early_dismissal":
        adjustments.append(f"Early dismissal at {value.get('adjusted_end')}")

    state["school_status"] = {
        "status": status,
        "adjustments": adjustments,
    }


async def enrich_deliveries(db, state: dict):
    """Add delivery tracking to daily_state."""
    reading = await _get_latest_reading(db, "sensor-packages", "logistics.packages")
    if not reading:
        state["deliveries"] = {
            "expected_today": 0,
            "requires_someone_home": False,
            "delivery_windows": [],
        }
        return

    value = reading["value"]
    today_pkgs = value.get("expected_today", [])
    needs_home = any(p.get("requires_someone_home") for p in today_pkgs)
    windows = []
    for pkg in today_pkgs:
        if pkg.get("window"):
            windows.append({"window": pkg["window"], "carrier": pkg.get("carrier")})

    state["deliveries"] = {
        "expected_today": len(today_pkgs),
        "requires_someone_home": needs_home,
        "delivery_windows": windows,
    }


async def enrich_health(db, state: dict):
    """Add per-member health context to member_states.

    Privacy: raw health data is NEVER exposed. Only derived impacts
    appear in state (e.g., "sleep was poor" not "6.5 hours, 3 awakenings").
    """
    member_states = state.get("member_states", {})
    if not member_states:
        return

    for member_id in list(member_states.keys()):
        health = {}

        # Sleep
        sleep = await _get_latest_reading(
            db, "sensor-health-sleep", "health.sleep.summary", member_id=member_id
        )
        if sleep:
            sv = sleep["value"]
            health["sleep_quality"] = sv.get("quality", "unknown")
            health["sleep_hours"] = sv.get("total_hours")
        else:
            health["sleep_quality"] = "unknown"
            health["sleep_hours"] = None

        # Medication
        meds = await _get_latest_reading(
            db, "sensor-health-meds", "health.medication", member_id=member_id
        )
        if meds:
            mv = meds["value"]
            health["medication_taken"] = mv.get("all_taken", False)
            health["medication_taken_at"] = None
            for m in mv.get("medications", []):
                if m.get("taken"):
                    health["medication_taken_at"] = m.get("taken_at")
                    break
            health["peak_window"] = mv.get("peak_window")
            health["crash_window"] = mv.get("crash_window")
        else:
            health["medication_taken"] = None

        # Energy level (derived from sleep + meds + activity)
        health["energy_level"] = _derive_energy_level(health)
        health["energy_factors"] = _derive_energy_factors(health)

        # Heart/stress (privileged — only trend, not raw)
        heart = await _get_latest_reading(
            db, "sensor-health-heart", "health.heart.summary", member_id=member_id
        )
        if heart:
            health["stress_trend"] = heart["value"].get("hrv_trend", "stable")
        else:
            health["stress_trend"] = "unknown"

        # Activity rings
        activity = await _get_latest_reading(
            db, "sensor-health-activity", "health.activity.summary", member_id=member_id
        )
        if activity:
            av = activity["value"]
            health["activity_rings"] = {
                "move": av.get("move_ring_pct"),
                "exercise": av.get("exercise_ring_pct"),
                "stand": av.get("stand_ring_pct"),
            }

        # Focus mode
        focus = await _get_latest_reading(
            db, "sensor-apple-focus", "device.focus", member_id=member_id
        )
        if focus:
            health["focus_mode"] = focus["value"].get("active_focus")
        else:
            health["focus_mode"] = None

        # Reachability (battery)
        battery = await _get_latest_reading(
            db, "sensor-apple-battery", "device.battery", member_id=member_id
        )
        if battery:
            health["reachable"] = not battery["value"].get("reachability_risk", False)
            health["battery_warning"] = battery["value"].get("reachability_risk", False)
        else:
            health["reachable"] = True
            health["battery_warning"] = False

        member_states[member_id]["health"] = health


async def enrich_ambient(db, state: dict):
    """Add household ambient state (occupants, appliances, security)."""
    ambient = {}

    # WiFi presence
    wifi = await _get_latest_reading(db, "sensor-wifi-presence", "home.wifi_presence")
    if wifi:
        ambient["home_occupants"] = wifi["value"].get("members_home", [])
    else:
        ambient["home_occupants"] = []

    # HomeKit state
    homekit = await _get_latest_reading(db, "sensor-homekit", "home.state")
    if homekit:
        hv = homekit["value"]
        # Appliance alerts
        appliance_alerts = []
        for name, info in hv.get("appliances", {}).items():
            if info.get("state") == "complete":
                appliance_alerts.append(f"{name} complete")
        ambient["appliance_alerts"] = appliance_alerts

        # Security
        locks = hv.get("locks", {})
        all_locked = all(l.get("locked", True) for l in locks.values())
        ambient["security"] = "normal" if all_locked else "door_unlocked"

        # Temperature
        thermo = hv.get("thermostat", {})
        ambient["home_temp"] = thermo.get("current_temp")
    else:
        ambient["appliance_alerts"] = []
        ambient["security"] = "unknown"
        ambient["home_temp"] = None

    state["ambient"] = ambient


# ─── Helpers ───

def _derive_energy_level(health: dict) -> str:
    """Derive energy level from available health signals."""
    sleep_q = health.get("sleep_quality", "unknown")
    meds = health.get("medication_taken")

    if sleep_q == "poor":
        return "low"
    if sleep_q == "good" and meds:
        return "high"
    if sleep_q == "fair":
        return "medium"
    return "medium"  # Default


def _derive_energy_factors(health: dict) -> list[str]:
    """Build human-readable list of energy factors."""
    factors = []
    sleep_q = health.get("sleep_quality", "unknown")
    sleep_h = health.get("sleep_hours")
    if sleep_q != "unknown":
        desc = f"{sleep_q} sleep"
        if sleep_h:
            desc += f" ({sleep_h}h)"
        factors.append(desc)

    if health.get("medication_taken"):
        taken_at = health.get("medication_taken_at", "")
        peak = health.get("peak_window")
        desc = "meds taken"
        if taken_at:
            desc += f" at {taken_at}"
        if peak:
            desc += f" (peak {peak.get('start', '')}-{peak.get('end', '')})"
        factors.append(desc)
    elif health.get("medication_taken") is False:
        factors.append("meds not taken yet")

    return factors


def _build_weather_summary(value: dict) -> str:
    """Build a one-line weather summary."""
    parts = []
    condition = value.get("condition_text")
    if condition:
        parts.append(condition)
    temp = value.get("temp_f")
    if temp is not None:
        parts.append(f"{temp}\u00b0F")
    precip = value.get("precipitation_chance")
    if precip and precip > 20:
        parts.append(f"{precip}% rain")
    return ", ".join(parts) if parts else "No weather data"


async def _get_latest_reading(
    db, sensor_id: str, reading_type: str, member_id: str | None = None
) -> dict | None:
    """Get the most recent non-expired reading for a sensor + type."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if member_id:
        row = await db.execute_fetchone(
            """SELECT * FROM pib_sensor_readings
               WHERE sensor_id = ? AND reading_type = ? AND member_id = ?
                 AND expires_at > ?
               ORDER BY timestamp DESC LIMIT 1""",
            [sensor_id, reading_type, member_id, now],
        )
    else:
        row = await db.execute_fetchone(
            """SELECT * FROM pib_sensor_readings
               WHERE sensor_id = ? AND reading_type = ?
                 AND expires_at > ?
               ORDER BY timestamp DESC LIMIT 1""",
            [sensor_id, reading_type, now],
        )

    if not row:
        return None

    result = dict(row)
    try:
        result["value"] = json.loads(result["value"])
    except (json.JSONDecodeError, TypeError):
        pass
    return result
