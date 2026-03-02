"""Tests for sensor-driven proactive triggers."""

import pytest

from pib.proactive import PROACTIVE_TRIGGERS, SENSOR_TRIGGERS


class TestSensorTriggerDefinitions:
    """Verify sensor triggers exist and have correct structure."""

    def _get_sensor_triggers(self):
        """Get all sensor-related triggers from the SENSOR_TRIGGERS list."""
        return list(SENSOR_TRIGGERS)

    def test_sensor_triggers_exist(self):
        triggers = self._get_sensor_triggers()
        assert len(triggers) >= 10  # At least most sensor triggers are defined

    def test_triggers_have_required_fields(self):
        triggers = self._get_sensor_triggers()
        for t in triggers:
            assert "name" in t, f"Trigger missing 'name': {t}"
            assert "priority" in t, f"Trigger {t['name']} missing 'priority'"
            assert "cooldown_minutes" in t, f"Trigger {t['name']} missing 'cooldown_minutes'"

    def test_trigger_priorities_in_range(self):
        triggers = self._get_sensor_triggers()
        for t in triggers:
            assert 1 <= t["priority"] <= 10, f"Trigger {t['name']} priority {t['priority']} out of range"

    def test_cooldowns_positive(self):
        triggers = self._get_sensor_triggers()
        for t in triggers:
            assert t["cooldown_minutes"] > 0, f"Trigger {t['name']} cooldown must be positive"

    def test_severe_weather_is_high_priority(self):
        triggers = self._get_sensor_triggers()
        severe = [t for t in triggers if t["name"] == "severe_weather_immediate"]
        if severe:
            assert severe[0]["priority"] <= 3  # Should be high priority

    def test_no_duplicate_names(self):
        all_triggers = list(PROACTIVE_TRIGGERS) + list(SENSOR_TRIGGERS)
        names = [t["name"] for t in all_triggers]
        assert len(names) == len(set(names)), "Duplicate trigger names found"
