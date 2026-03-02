"""Setup wizard helpers for credential onboarding and env file management."""

from __future__ import annotations

import os
from pathlib import Path

ALLOWED_SETUP_KEYS = {
    "PIB_ENV",
    "PIB_STRICT_STARTUP",
    "ANTHROPIC_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "GOOGLE_SA_KEY_PATH",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "GOOGLE_OAUTH_SCOPES",
    "BLUEBUBBLES_SECRET",
    "BLUEBUBBLES_URL",
    "CLOUDFLARE_TUNNEL_TOKEN",
    "SIRI_BEARER_TOKEN",
    "BACKUP_PUBLIC_KEY",
    "BACKUP_FOLDER_ID",
    "PIB_SHEETS_WEBHOOK_TOKEN",
    "PIB_DB_PATH",
    "PIB_PORT",
    "PIB_HOST",
    "PIB_LOG_DIR",
    "PIB_CORS_ORIGINS",
    "PIB_TIMEZONE",
}

MASK_KEYS = {
    "ANTHROPIC_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "BLUEBUBBLES_SECRET",
    "CLOUDFLARE_TUNNEL_TOKEN",
    "SIRI_BEARER_TOKEN",
    "BACKUP_PUBLIC_KEY",
    "PIB_SHEETS_WEBHOOK_TOKEN",
}


def env_file_path() -> Path:
    configured = os.environ.get("PIB_ENV_FILE")
    if configured:
        return Path(configured)
    default_prod = Path("/opt/pib/config/.env")
    if default_prod.exists():
        return default_prod
    return Path("config/.env")


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def write_env_file(path: Path, values: dict[str, str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# PIB runtime environment (managed by setup wizard)"]
    for key in sorted(values.keys()):
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n")


def mask_value(key: str, value: str) -> str:
    if key in MASK_KEYS and value:
        if len(value) <= 6:
            return "*" * len(value)
        return value[:3] + "*" * (len(value) - 6) + value[-3:]
    return value


def get_setup_status() -> dict:
    path = env_file_path()
    values = parse_env_file(path)

    required = [
        "ANTHROPIC_API_KEY",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER",
        "GOOGLE_SA_KEY_PATH",
        "BLUEBUBBLES_SECRET",
        "SIRI_BEARER_TOKEN",
    ]

    services = [
        {
            "id": "anthropic",
            "label": "Anthropic",
            "keys": ["ANTHROPIC_API_KEY"],
            "docs": "https://console.anthropic.com/settings/keys",
        },
        {
            "id": "google",
            "label": "Google Console / Gmail / Calendar / Drive",
            "keys": [
                "GOOGLE_SA_KEY_PATH",
                "GOOGLE_OAUTH_CLIENT_ID",
                "GOOGLE_OAUTH_CLIENT_SECRET",
                "GOOGLE_OAUTH_REDIRECT_URI",
            ],
            "docs": "https://console.cloud.google.com/apis/dashboard",
        },
        {
            "id": "twilio",
            "label": "Twilio",
            "keys": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"],
            "docs": "https://console.twilio.com/",
        },
        {
            "id": "bluebubbles",
            "label": "BlueBubbles",
            "keys": ["BLUEBUBBLES_SECRET", "BLUEBUBBLES_URL"],
            "docs": "https://bluebubbles.app/",
        },
    ]

    service_status = []
    for svc in services:
        present = [k for k in svc["keys"] if values.get(k)]
        service_status.append(
            {
                **svc,
                "ready": len(present) == len(svc["keys"]),
                "present": present,
                "missing": [k for k in svc["keys"] if k not in present],
            }
        )

    missing_required = [k for k in required if not values.get(k)]

    return {
        "env_file": str(path),
        "ready": len(missing_required) == 0,
        "missing_required": missing_required,
        "services": service_status,
        "values": {k: mask_value(k, v) for k, v in values.items() if k in ALLOWED_SETUP_KEYS},
    }


def upsert_env_values(updates: dict[str, str]) -> dict:
    invalid = [k for k in updates.keys() if k not in ALLOWED_SETUP_KEYS]
    if invalid:
        raise ValueError(f"Unsupported keys: {', '.join(invalid)}")

    path = env_file_path()
    values = parse_env_file(path)
    for k, v in updates.items():
        values[k] = str(v).strip()
    write_env_file(path, values)
    return get_setup_status()
