"""Tests for energy level computation and medication timing."""

import pytest
from datetime import datetime
from pib.engine import compute_energy_level


JAMES_MEMBER = {
    "medication_config": '{"name":"Adderall","typical_dose_time":"07:30","peak_onset_minutes":60,"peak_duration_minutes":240,"crash_onset_minutes":300}',
    "energy_markers": '{"peak_hours":["09:00-12:00"],"crash_hours":["14:00-16:00"]}',
}


class TestEnergyWithMeds:
    def test_before_meds_early_morning(self):
        energy = compute_energy_level(
            {"meds_taken": False, "sleep_quality": "okay"},
            JAMES_MEMBER,
            now=datetime(2026, 3, 1, 7, 0),
        )
        assert energy == "medium"

    def test_before_meds_late_morning(self):
        energy = compute_energy_level(
            {"meds_taken": False, "sleep_quality": "okay"},
            JAMES_MEMBER,
            now=datetime(2026, 3, 1, 9, 0),
        )
        assert energy == "low"  # Should have taken by now

    def test_peak_window(self):
        energy = compute_energy_level(
            {"meds_taken": True, "meds_taken_at": "2026-03-01T07:30:00", "sleep_quality": "okay"},
            JAMES_MEMBER,
            now=datetime(2026, 3, 1, 9, 0),  # 90 min after meds → peak
        )
        assert energy == "high"

    def test_crash_window(self):
        energy = compute_energy_level(
            {"meds_taken": True, "meds_taken_at": "2026-03-01T07:30:00", "sleep_quality": "okay"},
            JAMES_MEMBER,
            now=datetime(2026, 3, 1, 13, 0),  # 330 min → crash
        )
        assert energy == "crashed"


class TestEnergyWithoutMeds:
    def test_no_med_config_default(self):
        energy = compute_energy_level(
            {"meds_taken": False, "sleep_quality": "okay"},
            {"medication_config": "{}", "energy_markers": "{}"},
        )
        assert energy in ("medium", "high")

    def test_crash_hours(self):
        energy = compute_energy_level(
            {"meds_taken": False, "sleep_quality": "okay"},
            {"medication_config": "{}", "energy_markers": '{"crash_hours":["14:00-16:00"]}'},
            now=datetime(2026, 3, 1, 15, 0),
        )
        assert energy == "low"


class TestSleepOverride:
    def test_rough_sleep_always_low(self):
        energy = compute_energy_level(
            {"meds_taken": True, "meds_taken_at": "2026-03-01T07:30:00", "sleep_quality": "rough"},
            JAMES_MEMBER,
            now=datetime(2026, 3, 1, 9, 0),
        )
        assert energy == "low"

    def test_no_energy_state(self):
        assert compute_energy_level(None, JAMES_MEMBER) == "medium"
