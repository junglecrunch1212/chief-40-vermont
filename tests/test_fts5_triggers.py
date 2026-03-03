"""Tests for FTS5 sync triggers from migration 007.

Verifies that INSERT/UPDATE/DELETE on ops_tasks and mem_long_term
are automatically reflected in the corresponding FTS5 virtual tables.
"""

import pytest


class TestFTS5TriggersExist:
    """Migration 007 should create 9 FTS5 sync triggers."""

    async def test_fts5_triggers_exist(self, db):
        rows = await db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE '%fts%'"
        )
        trigger_names = [r["name"] for r in rows]
        assert len(trigger_names) >= 9, (
            f"Expected at least 9 FTS triggers, found {len(trigger_names)}: {trigger_names}"
        )
        # Spot-check the expected trigger names
        expected = {
            "ops_tasks_fts_insert",
            "ops_tasks_fts_update",
            "ops_tasks_fts_delete",
            "ops_items_fts_insert",
            "ops_items_fts_update",
            "ops_items_fts_delete",
            "mem_long_term_fts_insert",
            "mem_long_term_fts_update",
            "mem_long_term_fts_delete",
        }
        assert expected.issubset(set(trigger_names)), (
            f"Missing triggers: {expected - set(trigger_names)}"
        )


class TestTasksFTSInsert:
    """INSERT trigger populates ops_tasks_fts."""

    async def test_tasks_fts_insert(self, db):
        await db.execute(
            "INSERT INTO ops_tasks (id, title, status, assignee, domain, energy, effort, "
            "micro_script, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ["tsk-fts-001", "Replace furnace filter", "next", "m-james",
             "household", "low", "small", "Go to basement, swap filter", "test"],
        )
        await db.commit()

        rows = await db.execute_fetchall(
            "SELECT * FROM ops_tasks_fts WHERE ops_tasks_fts MATCH ?",
            ["furnace"],
        )
        assert len(rows) == 1
        assert "furnace" in rows[0]["title"].lower()


class TestTasksFTSUpdate:
    """UPDATE trigger keeps ops_tasks_fts in sync."""

    async def test_tasks_fts_update(self, db):
        await db.execute(
            "INSERT INTO ops_tasks (id, title, status, assignee, domain, energy, effort, "
            "micro_script, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ["tsk-fts-002", "Old title plumbing", "next", "m-james",
             "household", "low", "small", "", "test"],
        )
        await db.commit()

        # Update the title
        await db.execute(
            "UPDATE ops_tasks SET title = ? WHERE id = ?",
            ["Schedule electrician inspection", "tsk-fts-002"],
        )
        await db.commit()

        # Old title should no longer match
        old_rows = await db.execute_fetchall(
            "SELECT * FROM ops_tasks_fts WHERE ops_tasks_fts MATCH ?",
            ["plumbing"],
        )
        assert len(old_rows) == 0

        # New title should match
        new_rows = await db.execute_fetchall(
            "SELECT * FROM ops_tasks_fts WHERE ops_tasks_fts MATCH ?",
            ["electrician"],
        )
        assert len(new_rows) == 1
        assert "electrician" in new_rows[0]["title"].lower()


class TestTasksFTSDelete:
    """DELETE trigger removes from ops_tasks_fts."""

    async def test_tasks_fts_delete(self, db):
        await db.execute(
            "INSERT INTO ops_tasks (id, title, status, assignee, domain, energy, effort, "
            "micro_script, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ["tsk-fts-003", "Unique xylophone repair", "next", "m-james",
             "household", "low", "small", "", "test"],
        )
        await db.commit()

        # Confirm it exists in FTS
        rows = await db.execute_fetchall(
            "SELECT * FROM ops_tasks_fts WHERE ops_tasks_fts MATCH ?",
            ["xylophone"],
        )
        assert len(rows) == 1

        # Delete the task
        await db.execute("DELETE FROM ops_tasks WHERE id = ?", ["tsk-fts-003"])
        await db.commit()

        # FTS should return nothing
        rows = await db.execute_fetchall(
            "SELECT * FROM ops_tasks_fts WHERE ops_tasks_fts MATCH ?",
            ["xylophone"],
        )
        assert len(rows) == 0


class TestMemoryFTSInsert:
    """INSERT trigger populates mem_long_term_fts."""

    async def test_memory_fts_insert(self, db):
        await db.execute(
            "INSERT INTO mem_long_term (category, content, domain, member_id, source) "
            "VALUES (?, ?, ?, ?, ?)",
            ["preferences", "James prefers sourdough bread from Whole Foods",
             "food", "m-james", "user_stated"],
        )
        await db.commit()

        rows = await db.execute_fetchall(
            "SELECT * FROM mem_long_term_fts WHERE mem_long_term_fts MATCH ?",
            ["sourdough"],
        )
        assert len(rows) == 1
        assert "sourdough" in rows[0]["content"].lower()


class TestMemoryFTSUpdate:
    """UPDATE trigger keeps mem_long_term_fts in sync."""

    async def test_memory_fts_update(self, db):
        await db.execute(
            "INSERT INTO mem_long_term (category, content, domain, member_id, source) "
            "VALUES (?, ?, ?, ?, ?)",
            ["preferences", "Laura enjoys running marathons",
             "fitness", "m-laura", "user_stated"],
        )
        await db.commit()

        # Get the auto-generated id
        row = await db.execute_fetchone(
            "SELECT id FROM mem_long_term WHERE content LIKE '%marathons%'"
        )
        mem_id = row["id"]

        # Update the content
        await db.execute(
            "UPDATE mem_long_term SET content = ? WHERE id = ?",
            ["Laura enjoys cycling on weekends", mem_id],
        )
        await db.commit()

        # Old content should no longer match
        old_rows = await db.execute_fetchall(
            "SELECT * FROM mem_long_term_fts WHERE mem_long_term_fts MATCH ?",
            ["marathons"],
        )
        assert len(old_rows) == 0

        # New content should match
        new_rows = await db.execute_fetchall(
            "SELECT * FROM mem_long_term_fts WHERE mem_long_term_fts MATCH ?",
            ["cycling"],
        )
        assert len(new_rows) == 1
        assert "cycling" in new_rows[0]["content"].lower()


class TestMemoryFTSDelete:
    """DELETE trigger removes from mem_long_term_fts."""

    async def test_memory_fts_delete(self, db):
        await db.execute(
            "INSERT INTO mem_long_term (category, content, domain, member_id, source) "
            "VALUES (?, ?, ?, ?, ?)",
            ["facts", "Charlie has a pet iguana named Ziggy",
             "pets", "m-charlie", "user_stated"],
        )
        await db.commit()

        # Confirm it exists in FTS
        rows = await db.execute_fetchall(
            "SELECT * FROM mem_long_term_fts WHERE mem_long_term_fts MATCH ?",
            ["iguana"],
        )
        assert len(rows) == 1

        # Get the id and delete
        row = await db.execute_fetchone(
            "SELECT id FROM mem_long_term WHERE content LIKE '%iguana%'"
        )
        await db.execute("DELETE FROM mem_long_term WHERE id = ?", [row["id"]])
        await db.commit()

        # FTS should return nothing
        rows = await db.execute_fetchall(
            "SELECT * FROM mem_long_term_fts WHERE mem_long_term_fts MATCH ?",
            ["iguana"],
        )
        assert len(rows) == 0
