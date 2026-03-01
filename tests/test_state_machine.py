"""Tests for task state machine transitions and guards."""

import pytest
from pib.engine import can_transition, TRANSITIONS


class TestTransitionMap:
    """Every state's allowed transitions are correctly defined."""

    def test_inbox_transitions(self):
        assert set(TRANSITIONS["inbox"]) == {"next", "in_progress", "waiting_on", "deferred", "dismissed"}

    def test_next_transitions(self):
        assert set(TRANSITIONS["next"]) == {"in_progress", "done", "waiting_on", "deferred", "dismissed"}

    def test_in_progress_transitions(self):
        assert set(TRANSITIONS["in_progress"]) == {"done", "waiting_on", "deferred"}

    def test_waiting_on_transitions(self):
        assert set(TRANSITIONS["waiting_on"]) == {"in_progress", "next", "done"}

    def test_deferred_transitions(self):
        assert set(TRANSITIONS["deferred"]) == {"next", "inbox"}

    def test_done_is_terminal(self):
        assert TRANSITIONS["done"] == []

    def test_dismissed_is_terminal(self):
        assert TRANSITIONS["dismissed"] == []


class TestGuards:
    """Friction asymmetry: done = easy, dismiss = hard."""

    def test_done_always_allowed(self):
        ok, _ = can_transition({"status": "next"}, "done")
        assert ok

    def test_dismiss_blocked_without_notes(self):
        ok, msg = can_transition({"status": "next"}, "dismissed", {})
        assert not ok

    def test_dismiss_blocked_with_short_notes(self):
        ok, msg = can_transition({"status": "next"}, "dismissed", {"notes": "nah"})
        assert not ok

    def test_dismiss_allowed_with_long_notes(self):
        ok, _ = can_transition(
            {"status": "next"}, "dismissed",
            {"notes": "This task is no longer relevant because the event was cancelled."},
        )
        assert ok

    def test_deferred_requires_scheduled_date(self):
        ok, _ = can_transition({"status": "next"}, "deferred", {})
        assert not ok

        ok, _ = can_transition({"status": "next"}, "deferred", {"scheduled_date": "2026-04-01"})
        assert ok

    def test_waiting_on_requires_who(self):
        ok, _ = can_transition({"status": "next"}, "waiting_on", {})
        assert not ok

        ok, _ = can_transition({"status": "next"}, "waiting_on", {"waiting_on": "Laura"})
        assert ok

    def test_invalid_transition_rejected(self):
        ok, msg = can_transition({"status": "done"}, "inbox")
        assert not ok
        assert "Cannot transition" in msg
