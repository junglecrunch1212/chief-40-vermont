"""Production readiness checks for bootstrap and runtime integrations."""

from __future__ import annotations

import os
from pathlib import Path

# Per-bridge BlueBubbles secrets (one per personal Mac Mini)
BRIDGE_SECRETS = [
    "BLUEBUBBLES_JAMES_SECRET",
    "BLUEBUBBLES_LAURA_SECRET",
]

CRITICAL_ENV = [
    "ANTHROPIC_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
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
    is_openclaw = os.environ.get("PIB_RUNTIME_MODE") == "openclaw"

    for key in CRITICAL_ENV:
        checks[f"env_{key.lower()}"] = {"ok": _is_set(key), "required": True}

    # Per-bridge BlueBubbles secrets — at least one must be set for bridge support
    any_bridge_secret = any(_is_set(key) for key in BRIDGE_SECRETS)
    for key in BRIDGE_SECRETS:
        checks[f"env_{key.lower()}"] = {"ok": _is_set(key), "required": False}
    checks["env_bluebubbles_bridges"] = {
        "ok": any_bridge_secret,
        "required": True,
        "detail": "At least one of BLUEBUBBLES_JAMES_SECRET or BLUEBUBBLES_LAURA_SECRET must be set",
    }

    for key in OPTIONAL_ENV:
        checks[f"env_{key.lower()}"] = {"ok": _is_set(key), "required": False}

    # OpenClaw handles Google auth — skip GOOGLE_SA_KEY_PATH check in openclaw mode
    google_required = not is_openclaw
    google_key = os.environ.get("GOOGLE_SA_KEY_PATH")
    google_set = _is_set("GOOGLE_SA_KEY_PATH")
    checks["env_google_sa_key_path"] = {"ok": google_set, "required": google_required}
    checks["google_sa_key_file"] = {"ok": _file_exists(google_key), "required": google_required}

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

    # FTS5 trigger existence check
    fts_triggers = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM sqlite_master WHERE type='trigger' AND name LIKE '%fts%'"
    )
    checks["fts5_triggers"] = {"ok": (fts_triggers["c"] if fts_triggers else 0) >= 9, "required": False}

    # governance.yaml existence check
    governance_path = Path(__file__).parent.parent.parent / "config" / "governance.yaml"
    checks["governance_yaml"] = {"ok": governance_path.exists(), "required": False}

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
