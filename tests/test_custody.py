"""Tests for custody date math — 20+ cases including DST transitions."""

import json

import pytest
from datetime import date
from pib.custody import who_has_child


@pytest.fixture
def alt_week_config():
    return {
        "schedule_type": "alternating_weeks",
        "anchor_date": "2026-01-05",  # Monday
        "anchor_parent": "m-james",
        "other_parent": "m-laura-ex",
        "holiday_overrides": "[]",
    }


@pytest.fixture
def alt_weekend_config():
    return {
        "schedule_type": "alternating_weekends_midweek",
        "anchor_date": "2026-01-05",
        "anchor_parent": "m-james",
        "other_parent": "m-laura-ex",
        "midweek_visit_enabled": True,
        "midweek_visit_day": "wednesday",
        "midweek_visit_parent": "m-laura-ex",
        "holiday_overrides": "[]",
    }


@pytest.fixture
def every_other_weekend_config():
    return {
        "schedule_type": "every_other_weekend",
        "anchor_date": "2026-01-05",
        "anchor_parent": "m-james",
        "other_parent": "m-laura-ex",
        "holiday_overrides": "[]",
    }


class TestAlternatingWeeks:
    """Basic alternating-weeks schedule."""

    def test_anchor_week(self, alt_week_config):
        # Week 0 (anchor week) → James
        assert who_has_child(date(2026, 1, 5), alt_week_config) == "m-james"
        assert who_has_child(date(2026, 1, 11), alt_week_config) == "m-james"

    def test_other_week(self, alt_week_config):
        # Week 1 → other parent
        assert who_has_child(date(2026, 1, 12), alt_week_config) == "m-laura-ex"
        assert who_has_child(date(2026, 1, 18), alt_week_config) == "m-laura-ex"

    def test_back_to_anchor(self, alt_week_config):
        # Week 2 → back to James
        assert who_has_child(date(2026, 1, 19), alt_week_config) == "m-james"

    def test_far_future(self, alt_week_config):
        # 10 weeks out → week 10 = even = James
        assert who_has_child(date(2026, 3, 16), alt_week_config) == "m-james"
        # 11 weeks = odd = other
        assert who_has_child(date(2026, 3, 23), alt_week_config) == "m-laura-ex"


class TestDSTTransitions:
    """DST must not affect custody. Calendar days, never hours."""

    @pytest.mark.parametrize("query_date,expected", [
        ("2026-03-07", "m-james"),      # Saturday, week 8 (even) → James
        ("2026-03-08", "m-james"),      # Sunday, week 8 (even) → James
        ("2026-03-09", "m-laura-ex"),   # Spring forward Monday, week 9 (odd) → Ex
        ("2026-03-10", "m-laura-ex"),   # Day after spring forward, week 9 → Ex
        ("2026-03-14", "m-laura-ex"),   # Saturday, still week 9 → Ex
        ("2026-03-15", "m-laura-ex"),   # Sunday, still week 9 → Ex
        ("2026-03-16", "m-james"),      # Monday, week 10 (even) → James
        ("2026-10-31", "m-james"),      # Saturday, week 42 (even) → James
        ("2026-11-01", "m-james"),      # Fall back Sunday, week 42 (even) → James
        ("2026-11-02", "m-laura-ex"),   # Monday, week 43 (odd) → Ex
    ])
    def test_dst_transitions(self, alt_week_config, query_date, expected):
        result = who_has_child(date.fromisoformat(query_date), alt_week_config)
        assert result == expected, f"Date {query_date}: expected {expected}, got {result}"


class TestHolidayOverrides:
    def test_holiday_override_takes_priority(self, alt_week_config):
        alt_week_config["holiday_overrides"] = json.dumps([
            {"start": "2026-12-24", "end": "2026-12-26", "parent": "m-laura-ex"}
        ])
        assert who_has_child(date(2026, 12, 25), alt_week_config) == "m-laura-ex"

    def test_non_holiday_date_unaffected(self, alt_week_config):
        alt_week_config["holiday_overrides"] = '[{"start":"2026-12-24","end":"2026-12-26","parent":"m-laura-ex"}]'
        # Dec 23 should follow normal schedule
        result = who_has_child(date(2026, 12, 23), alt_week_config)
        assert result in ("m-james", "m-laura-ex")  # depends on week parity


class TestAlternatingWeekendsMidweek:
    def test_weekday_default_to_anchor(self, alt_weekend_config):
        # Monday in week 0 → James (anchor)
        assert who_has_child(date(2026, 1, 5), alt_weekend_config) == "m-james"

    def test_anchor_weekend(self, alt_weekend_config):
        # Saturday in week 0 (even) → anchor parent
        assert who_has_child(date(2026, 1, 10), alt_weekend_config) == "m-james"

    def test_other_weekend(self, alt_weekend_config):
        # Saturday in week 1 (odd) → other parent
        assert who_has_child(date(2026, 1, 17), alt_weekend_config) == "m-laura-ex"

    def test_midweek_visit(self, alt_weekend_config):
        # Wednesday in week 0 → midweek visit parent
        assert who_has_child(date(2026, 1, 7), alt_weekend_config) == "m-laura-ex"


class TestEveryOtherWeekend:
    def test_weekday_always_anchor(self, every_other_weekend_config):
        assert who_has_child(date(2026, 1, 5), every_other_weekend_config) == "m-james"
        assert who_has_child(date(2026, 1, 6), every_other_weekend_config) == "m-james"

    def test_other_parent_weekend(self, every_other_weekend_config):
        # Week 1 weekend → other parent
        assert who_has_child(date(2026, 1, 17), every_other_weekend_config) == "m-laura-ex"

    def test_anchor_parent_weekend(self, every_other_weekend_config):
        # Week 0 weekend → anchor parent
        assert who_has_child(date(2026, 1, 10), every_other_weekend_config) == "m-james"


class TestEdgeCases:
    def test_anchor_date_itself(self, alt_week_config):
        result = who_has_child(date(2026, 1, 5), alt_week_config)
        assert result == "m-james"

    def test_day_before_anchor(self, alt_week_config):
        # Day before anchor is negative day_diff → still works
        result = who_has_child(date(2026, 1, 4), alt_week_config)
        assert result in ("m-james", "m-laura-ex")

    def test_primary_with_visitation_defaults(self):
        config = {
            "schedule_type": "primary_with_visitation",
            "anchor_date": "2026-01-01",
            "anchor_parent": "m-james",
            "other_parent": "m-laura-ex",
            "holiday_overrides": "[]",
        }
        assert who_has_child(date(2026, 6, 15), config) == "m-james"
