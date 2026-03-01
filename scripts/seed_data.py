"""Seed data loader — populates a fresh database with household configuration."""

import asyncio
import json
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import aiosqlite
from pib.db import apply_schema, get_connection


MEMBERS = [
    {
        "id": "m-james", "display_name": "James", "role": "parent",
        "can_be_assigned_tasks": 1, "can_receive_messages": 1,
        "preferred_channel": "imessage", "view_mode": "carousel",
        "digest_mode": "full", "velocity_cap": 15,
        "energy_markers": json.dumps({"peak_hours": ["09:00-12:00"], "crash_hours": ["14:00-16:00"]}),
        "medication_config": json.dumps({
            "name": "Adderall", "typical_dose_time": "07:30",
            "peak_onset_minutes": 60, "peak_duration_minutes": 240, "crash_onset_minutes": 300,
        }),
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
        "capabilities": json.dumps({"can_stay_home_alone": False, "needs_car_seat": False}),
    },
    {
        "id": "m-baby", "display_name": "Baby Girl", "role": "child",
        "is_adult": 0, "expected_arrival": "2026-05-15",
        "capabilities": json.dumps({"needs_constant_supervision": True}),
    },
]

CAPTAIN_ITEM = {
    "id": "i-captain", "name": "Captain", "type": "pet",
    "category": "household", "domain": "household",
    "metadata": json.dumps({
        "species": "dog", "breed": "unknown",
        "vet": "Peachtree Vet", "meds_monthly": True,
    }),
}

LIFE_PHASES = [
    {
        "id": "phase-pre-baby", "name": "Pre-Baby Prep", "status": "active",
        "start_date": "2026-02-01", "end_date": "2026-05-15",
        "description": "Preparing for baby arrival. Nesting mode.",
        "overrides": json.dumps({"suppress_crm_nudges": False, "max_new_tasks_per_day": 8}),
    },
    {
        "id": "phase-newborn", "name": "Newborn Survival", "status": "pending",
        "start_date": "2026-05-15", "end_date": "2026-08-15",
        "description": "First 3 months. Survival mode.",
        "overrides": json.dumps({
            "suppress_crm_nudges": True, "digest_mode": "minimal",
            "velocity_cap_override": 5, "max_proactive_per_day": 2,
        }),
    },
    {
        "id": "phase-infant", "name": "Infant", "status": "pending",
        "start_date": "2026-08-15", "end_date": "2027-05-15",
        "description": "3-12 months. Restore velocity, add pediatrician recurring.",
        "overrides": json.dumps({"velocity_cap_override": 10, "max_proactive_per_day": 4}),
    },
]

COACH_PROTOCOLS = [
    {
        "id": "protocol-never-guilt", "name": "Never Guilt",
        "trigger_condition": "Any reference to overdue tasks, missed deadlines, or incomplete work",
        "behavior": "Lead with the micro-script, not the overdue count. Never use words: should have, forgot, missed, behind, falling.",
    },
    {
        "id": "protocol-always-celebrate", "name": "Always Celebrate",
        "trigger_condition": "Any task completion, any status change to done",
        "behavior": "Always acknowledge completions with warmth. Never skip the celebration.",
    },
    {
        "id": "protocol-energy-match", "name": "Energy-Aware Presentation",
        "trigger_condition": "Any task presentation during low energy period",
        "behavior": "During low energy: present only tiny/small tasks. Use softer language. Validate rest.",
    },
    {
        "id": "protocol-no-compare", "name": "Never Compare Family Members",
        "trigger_condition": "Any reference to multiple family members' productivity",
        "behavior": "Never compare James and Laura's task counts, speeds, or consistency.",
    },
    {
        "id": "protocol-momentum-check", "name": "Momentum Check After 3+",
        "trigger_condition": "3 or more task completions in the current session",
        "behavior": "After 3+ completions: 'That's momentum. Want to ride it or bank it?'",
    },
    {
        "id": "protocol-scaffold-independence", "name": "Scaffold Independence",
        "trigger_condition": "Morning briefing, weekly review",
        "behavior": "Periodically reinforce fallback strategies. PIB should build independence, not dependency.",
    },
    {
        "id": "protocol-paralysis-break", "name": "Paralysis Detection",
        "trigger_condition": "2+ hours of inactivity during peak hours with no calendar block",
        "behavior": "Gentle check-in. Never guilt. Offer the tiniest possible restart.",
    },
    {
        "id": "protocol-post-meeting-capture", "name": "Post-Meeting Capture",
        "trigger_condition": "Calendar event with 2+ attendees ended within last 15 minutes",
        "behavior": "Prompt for action items. Route response through ingestion pipeline.",
    },
]

PIB_CONFIG = [
    ("anthropic_model_sonnet", "claude-sonnet-4-5-20250929", "Default model for routine queries"),
    ("anthropic_model_opus", "claude-opus-4-6", "Escalation model for complex synthesis"),
    ("anthropic_model_sonnet_previous", "claude-sonnet-4-5-20250514", "Fallback if current model deprecated"),
    ("anthropic_model_opus_previous", "claude-opus-4-5-20250918", "Fallback if current model deprecated"),
    ("monthly_api_budget_alert", "75.00", "Alert when monthly API spend exceeds this"),
    ("charlie_star_milestone_25", "Pick Friday movie", "Reward at 25 stars"),
    ("charlie_star_milestone_50", "Choose weekend activity", "Reward at 50 stars"),
    ("charlie_star_milestone_100", "Special outing with parent", "Reward at 100 stars"),
    ("household_timezone", "America/New_York", "Atlanta timezone for all date math"),
    ("emergency_contacts", json.dumps({
        "vet": "Peachtree Vet (404) 555-0111",
        "pediatrician": "Dr. Chen (404) 555-0222",
        "poison_control": "1-800-222-1222",
    }), "Emergency contact numbers"),
]


async def seed(db_path: str = "pib.db"):
    """Seed a database with all household configuration."""
    conn = await get_connection(db_path)
    await apply_schema(conn)

    # Members
    for m in MEMBERS:
        cols = list(m.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        await conn.execute(
            f"INSERT OR IGNORE INTO common_members ({col_names}) VALUES ({placeholders})",
            list(m.values()),
        )

    # Captain (pet)
    await conn.execute(
        "INSERT OR IGNORE INTO ops_items (id, name, type, category, domain, metadata) VALUES (?,?,?,?,?,?)",
        [CAPTAIN_ITEM["id"], CAPTAIN_ITEM["name"], CAPTAIN_ITEM["type"],
         CAPTAIN_ITEM["category"], CAPTAIN_ITEM["domain"], CAPTAIN_ITEM["metadata"]],
    )

    # Life phases
    for p in LIFE_PHASES:
        await conn.execute(
            "INSERT OR IGNORE INTO common_life_phases (id, name, status, start_date, end_date, description, overrides) "
            "VALUES (?,?,?,?,?,?,?)",
            [p["id"], p["name"], p["status"], p["start_date"], p["end_date"], p["description"], p["overrides"]],
        )

    # Coach protocols
    for p in COACH_PROTOCOLS:
        await conn.execute(
            "INSERT OR IGNORE INTO pib_coach_protocols (id, name, trigger_condition, behavior) VALUES (?,?,?,?)",
            [p["id"], p["name"], p["trigger_condition"], p["behavior"]],
        )

    # Config
    for key, value, desc in PIB_CONFIG:
        await conn.execute(
            "INSERT OR IGNORE INTO pib_config (key, value, description) VALUES (?,?,?)",
            [key, value, desc],
        )

    # ID sequences
    for prefix in ["tsk", "mem", "lst", "itm", "com", "ses"]:
        await conn.execute(
            "INSERT OR IGNORE INTO common_id_sequences (prefix, next_val) VALUES (?, 1)",
            [prefix],
        )

    await conn.commit()
    print(f"Seeded {db_path} successfully.")
    print(f"  Members: {len(MEMBERS)}")
    print(f"  Life phases: {len(LIFE_PHASES)}")
    print(f"  Coach protocols: {len(COACH_PROTOCOLS)}")
    print(f"  Config entries: {len(PIB_CONFIG)}")
    await conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "pib.db"
    asyncio.run(seed(db_path))
