"""Tests for compute_complexity_score — base + environmental modifiers."""

from pib.engine import compute_complexity_score


class TestBaseScoring:
    def test_empty_state(self):
        score = compute_complexity_score({})
        assert score == 0.0

    def test_hard_block_events(self):
        state = {
            "events": [
                {"scheduling_impact": "HARD_BLOCK"},
                {"scheduling_impact": "HARD_BLOCK"},
            ]
        }
        score = compute_complexity_score(state)
        assert score == 2.0

    def test_soft_block_events(self):
        state = {
            "events": [{"scheduling_impact": "SOFT_BLOCK"}]
        }
        score = compute_complexity_score(state)
        assert score == 0.5

    def test_requires_transport(self):
        state = {
            "events": [{"scheduling_impact": "REQUIRES_TRANSPORT"}]
        }
        score = compute_complexity_score(state)
        assert score == 0.3

    def test_unresolved_conflicts(self):
        state = {"unresolved_conflicts": 2}
        score = compute_complexity_score(state)
        assert score == 4.0

    def test_overdue_tasks(self):
        state = {"overdue_tasks": 5}
        score = compute_complexity_score(state)
        assert score == 1.0

    def test_custody_transition(self):
        state = {"custody_states": {"transition_today": True}}
        score = compute_complexity_score(state)
        assert score == 0.5

    def test_combined_base(self):
        state = {
            "events": [
                {"scheduling_impact": "HARD_BLOCK"},
                {"scheduling_impact": "SOFT_BLOCK"},
                {"scheduling_impact": "REQUIRES_TRANSPORT"},
            ],
            "unresolved_conflicts": 1,
            "overdue_tasks": 3,
        }
        # 1.0 + 0.5 + 0.3 + 2.0 + 0.6 = 4.4
        score = compute_complexity_score(state)
        assert abs(score - 4.4) < 0.01


class TestEnvironmentalModifiers:
    def test_severe_weather(self):
        state = {"weather": {"alerts": ["severe_thunderstorm"]}}
        score = compute_complexity_score(state)
        assert score == 0.5

    def test_perfect_weather(self):
        state = {"weather": {"outdoor_suitability": "good", "alerts": []}}
        # -0.3 but clamped at 0.0 minimum
        score = compute_complexity_score(state)
        assert score == 0.0  # Can't go negative

    def test_perfect_weather_reduces_from_base(self):
        state = {
            "events": [{"scheduling_impact": "HARD_BLOCK"}],
            "weather": {"outdoor_suitability": "good", "alerts": []},
        }
        # 1.0 - 0.3 = 0.7
        score = compute_complexity_score(state)
        assert abs(score - 0.7) < 0.01

    def test_school_not_normal(self):
        state = {"school_status": {"status": "delayed"}}
        score = compute_complexity_score(state)
        assert score == 0.3

    def test_school_normal_no_impact(self):
        state = {"school_status": {"status": "normal"}}
        score = compute_complexity_score(state)
        assert score == 0.0

    def test_delivery_needs_home(self):
        state = {"deliveries": {"requires_someone_home": True}}
        score = compute_complexity_score(state)
        assert score == 0.2

    def test_poor_sleep(self):
        state = {
            "member_states": {
                "m-james": {"health": {"sleep_quality": "poor"}},
            }
        }
        score = compute_complexity_score(state)
        assert score == 0.3


class TestCapping:
    def test_cap_at_10(self):
        state = {
            "events": [{"scheduling_impact": "HARD_BLOCK"}] * 12,
            "unresolved_conflicts": 5,
        }
        score = compute_complexity_score(state)
        assert score == 10.0

    def test_floor_at_zero(self):
        state = {"weather": {"outdoor_suitability": "good", "alerts": []}}
        score = compute_complexity_score(state)
        assert score >= 0.0
