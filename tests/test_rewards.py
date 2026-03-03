"""Tests for variable-ratio rewards and reward selection."""

import pytest
from pib.rewards import select_reward, REWARD_SCHEDULE, CHILD_REWARD_POOL, complete_task_with_reward, get_completion_stats


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


class TestChildRewardPool:
    def test_child_reward_pool_probabilities(self):
        total = sum(prob for prob, _, _ in CHILD_REWARD_POOL)
        assert abs(total - 1.0) < 0.001

    def test_child_age_gets_child_pool(self):
        stats = {"current_streak": 2, "completions_today": 1, "week_completions": 5}
        tier, message = select_reward("m-charlie", {}, stats, member_age=5)
        assert tier in ("simple", "warm", "delight", "jackpot")
        # Child messages shouldn't have adult-style messages
        assert "dopamine" not in message.lower()

    def test_adult_age_gets_adult_pool(self):
        stats = {"current_streak": 2, "completions_today": 1, "week_completions": 5}
        # member_age=None (default) should use adult pool
        tier, message = select_reward("m-james", {}, stats)
        assert tier in ("simple", "warm", "delight", "jackpot")


class TestCompletionStats:
    async def test_days_old_computed(self, db):
        """Create task 5 days ago, verify days_old is computed."""
        from datetime import datetime, timedelta
        five_days_ago = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        await db.execute(
            "UPDATE ops_tasks SET created_at = ? WHERE id = 'tsk-00001'",
            [five_days_ago],
        )
        await db.commit()

        stats = await get_completion_stats(db, "m-james", task_id="tsk-00001")
        assert stats["days_old"] >= 4  # Allow 1 day variance

    async def test_stats_without_task_id(self, db):
        stats = await get_completion_stats(db, "m-james")
        assert stats["days_old"] == 0
        assert "completions_today" in stats


class TestStateMachineEnforcement:
    async def test_complete_deferred_task_raises(self, db):
        """Attempting to complete a deferred task should raise ValueError."""
        await db.execute(
            "INSERT INTO ops_tasks (id, title, status, assignee, created_by, scheduled_date) "
            "VALUES ('tsk-deferred1', 'Deferred', 'deferred', 'm-james', 'test', '2026-04-01')"
        )
        await db.commit()

        with pytest.raises(ValueError):
            await complete_task_with_reward(db, "tsk-deferred1", "m-james", "m-james")
