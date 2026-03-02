"""Production readiness checks for bootstrap and runtime integrations."""

from __future__ import annotations

import os
from pathlib import Path

CRITICAL_ENV = [
    "ANTHROPIC_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "BLUEBUBBLES_SECRET",
    "SIRI_BEARER_TOKEN",
]

GOOGLE_ENV = [
    "GOOGLE_SA_KEY_PATH",
]

OPTIONAL_ENV = [
    "CLOUDFLARE_TUNNEL_TOKEN",
    "BACKUP_PUBLIC_KEY",
    "BACKUP_FOLDER_ID",
    "PIB_SHEETS_WEBHOOK_TOKEN",
]


def _is_set(name: str) -> bool:
    value = os.environ.get(name, "")
    return bool(value and value.strip())


def _file_exists(path: str | None) -> bool:
    if not path:
        return False
    return Path(path).exists()


async def evaluate_readiness(db) -> dict:
    """Evaluate bootstrap/runtime readiness without exposing secret values."""
    checks: dict[str, dict] = {}

    for key in CRITICAL_ENV:
        checks[f"env_{key.lower()}"] = {"ok": _is_set(key), "required": True}

    for key in OPTIONAL_ENV:
        checks[f"env_{key.lower()}"] = {"ok": _is_set(key), "required": False}

    google_key = os.environ.get("GOOGLE_SA_KEY_PATH")
    google_set = _is_set("GOOGLE_SA_KEY_PATH")
    checks["env_google_sa_key_path"] = {"ok": google_set, "required": True}
    checks["google_sa_key_file"] = {"ok": _file_exists(google_key), "required": True}

    # DB surface checks (tables expected for core launch)
    expected_tables = [
        "ops_tasks",
        "ops_comms",
        "cal_classified_events",
        "fin_transactions",
        "common_members",
    ]
    for table in expected_tables:
        row = await db.execute_fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", [table]
        )
        checks[f"table_{table}"] = {"ok": row is not None, "required": True}

    required_failed = [name for name, c in checks.items() if c.get("required") and not c.get("ok")]
    optional_failed = [name for name, c in checks.items() if not c.get("required") and not c.get("ok")]

    return {
        "ready": len(required_failed) == 0,
        "required_failed": required_failed,
        "optional_missing": optional_failed,
        "checks": checks,
    }


def validate_strict_startup(readiness: dict):
    """Raise RuntimeError when strict startup is enabled and required checks fail."""
    if os.environ.get("PIB_STRICT_STARTUP", "0") != "1":
        return
    if readiness.get("ready"):
        return
    failed = ", ".join(readiness.get("required_failed", []))
    raise RuntimeError(f"Strict startup readiness check failed: {failed}")
