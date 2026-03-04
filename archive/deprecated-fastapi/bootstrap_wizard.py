"""Bootstrap Setup Wizard helpers: credential catalog, env persistence, guided setup state."""

from __future__ import annotations

import os
from pathlib import Path

ENV_PATH_DEFAULT = "/opt/pib/config/.env"

SERVICE_FIELDS = [
    {
        "service": "Anthropic",
        "key": "ANTHROPIC_API_KEY",
        "label": "Anthropic API Key",
        "required": True,
        "secret": True,
        "chrome_steps": [
            "Open https://console.anthropic.com/settings/keys in Chrome.",
            "Click 'Create Key'.",
            "Copy the key and paste it into this wizard.",
        ],
    },
    {
        "service": "Twilio",
        "key": "TWILIO_ACCOUNT_SID",
        "label": "Twilio Account SID",
        "required": True,
        "secret": False,
        "chrome_steps": [
            "Open https://console.twilio.com/ in Chrome.",
            "From Dashboard, copy Account SID.",
            "Paste here.",
        ],
    },
    {
        "service": "Twilio",
        "key": "TWILIO_AUTH_TOKEN",
        "label": "Twilio Auth Token",
        "required": True,
        "secret": True,
        "chrome_steps": [
            "In Twilio Console, reveal Auth Token.",
            "Copy and paste it here.",
        ],
    },
    {
        "service": "Twilio",
        "key": "TWILIO_PHONE_NUMBER",
        "label": "Twilio Number",
        "required": True,
        "secret": False,
        "chrome_steps": [
            "In Twilio Console, go to Phone Numbers > Manage.",
            "Purchase or select a number with SMS capability.",
            "Paste in E.164 format like +14045550123.",
        ],
    },
    {
        "service": "Google",
        "key": "GOOGLE_SA_KEY_PATH",
        "label": "Google Service Account JSON Path",
        "required": True,
        "secret": False,
        "chrome_steps": [
            "Open https://console.cloud.google.com/apis/credentials in Chrome.",
            "Create or select a service account, then create JSON key.",
            "Upload key to Mac mini, e.g. /opt/pib/config/google-sa-key.json.",
            "Paste that file path in this field.",
        ],
    },
    {
        "service": "BlueBubbles",
        "key": "BLUEBUBBLES_URL",
        "label": "BlueBubbles Server URL",
        "required": True,
        "secret": False,
        "chrome_steps": [
            "Open your BlueBubbles server settings page.",
            "Copy the webhook/server URL.",
            "Paste URL (example: http://localhost:1234).",
        ],
    },
    {
        "service": "BlueBubbles",
        "key": "BLUEBUBBLES_SECRET",
        "label": "BlueBubbles Shared Secret",
        "required": True,
        "secret": True,
        "chrome_steps": [
            "In BlueBubbles, set or copy webhook password/secret.",
            "Paste secret here.",
        ],
    },
    {
        "service": "Cloudflare",
        "key": "CLOUDFLARE_TUNNEL_TOKEN",
        "label": "Cloudflare Tunnel Token",
        "required": False,
        "secret": True,
        "chrome_steps": [
            "Open Cloudflare Zero Trust in Chrome.",
            "Create a Tunnel for PIB.",
            "Copy tunnel token and paste here.",
        ],
    },
    {
        "service": "Siri",
        "key": "SIRI_BEARER_TOKEN",
        "label": "Siri Shortcut Bearer Token",
        "required": True,
        "secret": True,
        "chrome_steps": [
            "Generate a long random token.",
            "Paste same token in Siri Shortcut Authorization header.",
            "Paste token here.",
        ],
    },
    {
        "service": "Google Sheets",
        "key": "PIB_SHEETS_WEBHOOK_TOKEN",
        "label": "Sheets Webhook Token",
        "required": False,
        "secret": True,
        "chrome_steps": [
            "Create Google Apps Script webhook guard token.",
            "Paste token here to validate Sheets webhook calls.",
        ],
    },
    {
        "service": "Backups",
        "key": "BACKUP_PUBLIC_KEY",
        "label": "Backup Encryption Public Key",
        "required": False,
        "secret": False,
        "chrome_steps": [
            "Generate age public key for backup encryption.",
            "Paste public key here.",
        ],
    },
    {
        "service": "Backups",
        "key": "BACKUP_FOLDER_ID",
        "label": "Google Drive Backup Folder ID",
        "required": False,
        "secret": False,
        "chrome_steps": [
            "Open target Drive folder in Chrome.",
            "Copy folder ID from URL.",
            "Paste here.",
        ],
    },
]


def env_path() -> Path:
    return Path(os.environ.get("PIB_ENV_FILE", ENV_PATH_DEFAULT))


def parse_env_file(path: Path | None = None) -> dict[str, str]:
    p = path or env_path()
    if not p.exists():
        return {}
    data: dict[str, str] = {}
    for line in p.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def upsert_env_value(key: str, value: str, path: Path | None = None):
    p = path or env_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text().splitlines() if p.exists() else []

    target = f"{key}={value}"
    replaced = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            out.append(target)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(target)

    p.write_text("\n".join(out).rstrip() + "\n")


def _mask(value: str, secret: bool) -> str:
    if not value:
        return ""
    if not secret:
        return value
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "***" + value[-3:]


def wizard_state() -> dict:
    current = parse_env_file()
    fields = []
    missing_required = []

    for f in SERVICE_FIELDS:
        val = current.get(f["key"], "")
        is_set = bool(val)
        entry = {
            "service": f["service"],
            "key": f["key"],
            "label": f["label"],
            "required": f["required"],
            "secret": f["secret"],
            "is_set": is_set,
            "value_masked": _mask(val, f["secret"]),
            "chrome_steps": f["chrome_steps"],
        }
        fields.append(entry)
        if f["required"] and not is_set:
            missing_required.append(f["key"])

    return {
        "env_file": str(env_path()),
        "complete": len(missing_required) == 0,
        "missing_required": missing_required,
        "fields": fields,
    }
