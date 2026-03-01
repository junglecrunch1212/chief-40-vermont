"""Tests for variable-ratio rewards and reward selection."""

import pytest
from pib.rewards import select_reward, REWARD_SCHEDULE


class TestRewardDistribution:
    def test_probabilities_sum_to_one(self):
        total = sum(prob for prob, _, _ in REWARD_SCHEDULE)
        assert abs(total - 1.0) < 0.001

    def test_select_reward_returns_tuple(self):
        stats = {"current_streak": 5, "completions_today": 3, "week_completions": 15}
        tier, message = select_reward("m-james", {"id": "tsk-1"}, stats)
        assert tier in ("simple", "warm", "delight", "jackpot")
        assert isinstance(message, str)
        assert len(message) > 0

    def test_distribution_over_many_rolls(self):
        """Over 1000 rolls, distribution should roughly match schedule."""
        counts = {"simple": 0, "warm": 0, "delight": 0, "jackpot": 0}
        stats = {"current_streak": 5, "completions_today": 3, "week_completions": 15}

        for _ in range(1000):
            tier, _ = select_reward("m-james", {}, stats)
            counts[tier] += 1

        # Simple should be the most common (60%)
        assert counts["simple"] > counts["warm"]
        # Jackpot should be the least common (5%)
        assert counts["jackpot"] < counts["delight"]

    def test_message_formatting(self):
        stats = {
            "current_streak": 7,
            "completions_today": 4,
            "week_completions": 20,
            "days_old": 5,
            "days_since_all_clear": 10,
        }
        # Run many times to hit different tiers
        for _ in range(50):
            tier, message = select_reward("m-james", {"created_at": "2026-01-01"}, stats)
            # Message should not contain unformatted {placeholders}
            assert "{" not in message or "}" not in message
