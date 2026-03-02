"""Shared test fixtures: in-memory DB, seed data, snapshot."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest
import pytest_asyncio
import aiosqlite

from pib.engine import DBSnapshot

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"

SEED_MEMBERS = [
    {
        "id": "m-james", "display_name": "James", "role": "parent",
        "can_be_assigned_tasks": 1, "can_receive_messages": 1,
        "preferred_channel": "imessage", "view_mode": "carousel",
        "digest_mode": "full", "velocity_cap": 15,
        "energy_markers": '{"peak_hours":["09:00-12:00"],"crash_hours":["14:00-16:00"]}',
        "medication_config": '{"name":"Adderall","typical_dose_time":"07:30","peak_onset_minutes":60,"peak_duration_minutes":240,"crash_onset_minutes":300}',
    },
    {
        "id": "m-laura", "display_name": "Laura", "role": "parent",
        "can_be_assigned_tasks": 1, "can_receive_messages": 1,
        "preferred_channel": "imessage", "view_mode": "compressed",
        "digest_mode": "compressed", "velocity_cap": 20,
    },
    {
        "id": "m-charlie", "display_name": "Charlie", "role": "child",
        "is_adult": 0, "age": 6, "view_mode": "child",
        "capabilities": '{"can_stay_home_alone":false,"needs_car_seat":false}',
    },
]

SEED_CUSTODY_CONFIG = {
    "child_id": "m-charlie",
    "schedule_type": "alternating_weeks",
    "anchor_date": "2026-01-05",
    "anchor_parent": "m-james",
    "other_parent": "m-laura-ex",
    "effective_from": "2026-01-01",
    "holiday_overrides": "[]",
}

SEED_TASKS = [
    {
        "id": "tsk-00001", "title": "Call the dentist", "status": "next",
        "assignee": "m-james", "domain": "health", "energy": "low", "effort": "small",
        "micro_script": "Open phone -> search 'Peachtree Dental' -> tap call",
        "due_date": None, "created_by": "seed",
    },
    {
        "id": "tsk-00002", "title": "Buy diapers", "status": "next",
        "assignee": "m-james", "domain": "household", "energy": "low", "effort": "tiny",
        "micro_script": "Open browser -> search 'diapers'", "item_type": "purchase",
        "due_date": date.today().isoformat(), "created_by": "seed",
    },
    {
        "id": "tsk-00003", "title": "Review nursery layout", "status": "inbox",
        "assignee": "m-james", "domain": "household", "energy": "medium", "effort": "medium",
        "micro_script": "Open notes -> list pros/cons for: nursery layout",
        "due_date": None, "created_by": "seed",
    },
    {
        "id": "tsk-00004", "title": "Schedule pediatrician", "status": "in_progress",
        "assignee": "m-james", "domain": "health", "energy": "low", "effort": "small",
        "micro_script": "Open phone -> call Dr. Chen", "item_type": "appointment",
        "due_date": (date.today()).isoformat(), "created_by": "seed",
    },
]


async def seed_test_data(db: aiosqlite.Connection):
    """Insert seed data for tests."""
    # Members
    for m in SEED_MEMBERS:
        cols = list(m.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        await db.execute(
            f"INSERT OR IGNORE INTO common_members ({col_names}) VALUES ({placeholders})",
            list(m.values()),
        )

    # Coparent (for custody tests)
    await db.execute(
        "INSERT OR IGNORE INTO common_members (id, display_name, role, is_household_member) "
        "VALUES ('m-laura-ex', 'Ex', 'coparent', 0)",
    )

    # Custody config
    c = SEED_CUSTODY_CONFIG
    await db.execute(
        "INSERT OR IGNORE INTO common_custody_configs "
        "(child_id, schedule_type, anchor_date, anchor_parent, other_parent, effective_from, holiday_overrides) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [c["child_id"], c["schedule_type"], c["anchor_date"],
         c["anchor_parent"], c["other_parent"], c["effective_from"], c["holiday_overrides"]],
    )

    # Tasks
    for t in SEED_TASKS:
        await db.execute(
            "INSERT OR IGNORE INTO ops_tasks (id, title, status, assignee, domain, energy, effort, "
            "micro_script, due_date, created_by, item_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [t["id"], t["title"], t["status"], t["assignee"], t["domain"],
             t.get("energy"), t.get("effort"), t.get("micro_script", ""),
             t.get("due_date"), t.get("created_by", "seed"), t.get("item_type", "task")],
        )

    # ID sequences
    for prefix in ["tsk", "mem", "lst", "itm", "c", "vs", "vp", "sns", "cap", "nb"]:
        await db.execute(
            "INSERT OR IGNORE INTO common_id_sequences (prefix, next_val) VALUES (?, 100)",
            [prefix],
        )

    await db.commit()


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database with full schema + seed data."""
    from pib.db import PIBConnection, apply_schema, apply_migrations
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        wrapped = PIBConnection(conn)
        # Use production schema + migration path
        await apply_schema(wrapped)
        await apply_migrations(wrapped)
        await seed_test_data(wrapped)
        yield wrapped


@pytest.fixture
def snapshot():
    """Pre-loaded DBSnapshot for whatNow() tests."""
    members = {m["id"]: m for m in SEED_MEMBERS}
    tasks = [dict(t) for t in SEED_TASKS]

    return DBSnapshot(
        tasks=tasks,
        daily_state=None,
        energy_state={"completions_today": 2, "sleep_quality": "okay", "meds_taken": True,
                       "meds_taken_at": datetime.now().isoformat()},
        members=members,
        streaks={"m-james": {"current_streak": 5, "best_streak": 12}},
        calendar_events=[],
        now=datetime.now(),
    )


@pytest.fixture
def custody_config():
    """Standard custody config for testing."""
    return dict(SEED_CUSTODY_CONFIG)
