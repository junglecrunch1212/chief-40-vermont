"""Tests for whatNow() — determinism, energy filtering, velocity cap."""

import pytest
from datetime import datetime, date
from pib.engine import what_now, compute_energy_level, can_transition, DBSnapshot


class TestWhatNowDeterminism:
    """Same inputs MUST produce same output. No randomness in task selection."""

    def test_deterministic_same_result(self, snapshot):
        result1 = what_now("m-james", snapshot)
        result2 = what_now("m-james", snapshot)
        assert result1.the_one_task["id"] == result2.the_one_task["id"]

    def test_returns_highest_priority_task(self, snapshot):
        result = what_now("m-james", snapshot)
        # in_progress tasks should come before next/inbox
        assert result.the_one_task is not None
        assert result.the_one_task["status"] == "in_progress"

    def test_overdue_tasks_first(self, snapshot):
        snapshot.tasks.append({
            "id": "tsk-overdue", "title": "Overdue task", "status": "next",
            "assignee": "m-james", "energy": "low", "effort": "tiny",
            "due_date": "2020-01-01", "created_at": "2020-01-01",
        })
        result = what_now("m-james", snapshot)
        assert result.the_one_task["id"] == "tsk-overdue"

    def test_velocity_cap_triggers_break(self, snapshot):
        snapshot.energy_state["completions_today"] = 15
        snapshot.members["m-james"]["velocity_cap"] = 15
        result = what_now("m-james", snapshot)
        assert result.the_one_task["id"] == "break"
        assert "Rest" in result.the_one_task["notes"]

    def test_empty_tasks_returns_none(self, snapshot):
        snapshot.tasks = []
        result = what_now("m-james", snapshot)
        assert result.the_one_task is None

    def test_one_more_teaser_present(self, snapshot):
        result = what_now("m-james", snapshot)
        if len([t for t in snapshot.tasks if t["assignee"] == "m-james"]) > 1:
            assert result.one_more_teaser is not None

    def test_context_string_has_energy(self, snapshot):
        result = what_now("m-james", snapshot)
        assert "Energy:" in result.context


class TestComputeEnergyLevel:
    def test_rough_sleep_returns_low(self):
        energy = compute_energy_level(
            {"sleep_quality": "rough", "meds_taken": False},
            {"medication_config": "{}"},
        )
        assert energy == "low"

    def test_no_energy_state_returns_medium(self):
        assert compute_energy_level(None, {}) == "medium"

    def test_great_sleep_no_meds_config(self):
        energy = compute_energy_level(
            {"sleep_quality": "great", "meds_taken": False},
            {"medication_config": "{}", "energy_markers": "{}"},
        )
        assert energy == "high"


class TestStateTransitions:
    def test_inbox_to_next_allowed(self):
        ok, msg = can_transition({"status": "inbox"}, "next")
        assert ok

    def test_done_to_anything_blocked(self):
        ok, msg = can_transition({"status": "done"}, "next")
        assert not ok

    def test_dismiss_requires_notes(self):
        ok, msg = can_transition({"status": "inbox"}, "dismissed", {})
        assert not ok
        assert "notes" in msg.lower()

    def test_dismiss_with_notes_allowed(self):
        ok, msg = can_transition(
            {"status": "inbox"}, "dismissed",
            {"notes": "Not relevant anymore, removing."},
        )
        assert ok

    def test_defer_requires_date(self):
        ok, msg = can_transition({"status": "inbox"}, "deferred", {})
        assert not ok

    def test_defer_with_date_allowed(self):
        ok, msg = can_transition(
            {"status": "inbox"}, "deferred",
            {"scheduled_date": "2026-04-01"},
        )
        assert ok

    def test_waiting_requires_who(self):
        ok, msg = can_transition({"status": "next"}, "waiting_on", {})
        assert not ok

    def test_waiting_with_who_allowed(self):
        ok, msg = can_transition(
            {"status": "next"}, "waiting_on",
            {"waiting_on": "Laura"},
        )
        assert ok
