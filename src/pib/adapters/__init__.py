"""PIB Service Adapters — concrete implementations of the Adapter protocol.

Registry pattern: each adapter registers itself so the scheduler and health
endpoint can iterate all adapters without hard-coding imports.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)

# Global adapter registry — populated by init_adapters()
_adapters: dict[str, Any] = {}


def get_adapter(name: str):
    """Get a registered adapter by name, or None."""
    return _adapters.get(name)


def all_adapters() -> dict[str, Any]:
    """Return all registered adapters."""
    return dict(_adapters)


async def init_adapters(db) -> dict[str, bool]:
    """Initialize all adapters that have valid config. Returns {name: ok}."""
    import os
    results = {}

    # Google Calendar
    if os.environ.get("GOOGLE_SA_KEY_PATH") and os.path.isfile(os.environ.get("GOOGLE_SA_KEY_PATH", "")):
        try:
            from pib.adapters.google_calendar import GoogleCalendarAdapter
            adapter = GoogleCalendarAdapter()
            await adapter.init()
            _adapters["google_calendar"] = adapter
            results["google_calendar"] = True
            log.info("Google Calendar adapter initialized")
        except Exception as e:
            log.warning(f"Google Calendar adapter failed to init: {e}")
            results["google_calendar"] = False
    else:
        log.info("Google Calendar adapter skipped — GOOGLE_SA_KEY_PATH not set or missing")
        results["google_calendar"] = False

    # Gmail
    if os.environ.get("GOOGLE_SA_KEY_PATH") and os.path.isfile(os.environ.get("GOOGLE_SA_KEY_PATH", "")):
        try:
            from pib.adapters.gmail import GmailAdapter
            adapter = GmailAdapter()
            await adapter.init()
            _adapters["gmail"] = adapter
            results["gmail"] = True
            log.info("Gmail adapter initialized")
        except Exception as e:
            log.warning(f"Gmail adapter failed to init: {e}")
            results["gmail"] = False
    else:
        results["gmail"] = False

    # BlueBubbles sender (per-bridge: BLUEBUBBLES_JAMES_* / BLUEBUBBLES_LAURA_*)
    any_bb = any(
        os.environ.get(f"BLUEBUBBLES_{m}_URL") and os.environ.get(f"BLUEBUBBLES_{m}_SECRET")
        for m in ("JAMES", "LAURA")
    )
    if any_bb:
        try:
            from pib.adapters.bluebubbles_sender import BlueBubblesSender
            adapter = BlueBubblesSender()
            await adapter.init()
            _adapters["bluebubbles"] = adapter
            results["bluebubbles"] = True
            log.info("BlueBubbles sender initialized")
        except Exception as e:
            log.warning(f"BlueBubbles sender failed to init: {e}")
            results["bluebubbles"] = False
    else:
        log.info("BlueBubbles sender skipped — no BLUEBUBBLES_{MEMBER}_URL/SECRET set")
        results["bluebubbles"] = False

    # Twilio sender
    if os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"):
        try:
            from pib.adapters.twilio_sender import TwilioSender
            adapter = TwilioSender()
            await adapter.init()
            _adapters["twilio"] = adapter
            results["twilio"] = True
            log.info("Twilio sender initialized")
        except Exception as e:
            log.warning(f"Twilio sender failed to init: {e}")
            results["twilio"] = False
    else:
        log.info("Twilio sender skipped — TWILIO credentials not set")
        results["twilio"] = False

    # Google Sheets
    if os.environ.get("GOOGLE_SA_KEY_PATH") and os.path.isfile(os.environ.get("GOOGLE_SA_KEY_PATH", "")):
        try:
            from pib.adapters.google_sheets import GoogleSheetsAdapter
            adapter = GoogleSheetsAdapter()
            await adapter.init()
            _adapters["google_sheets"] = adapter
            results["google_sheets"] = True
            log.info("Google Sheets adapter initialized")
        except Exception as e:
            log.warning(f"Google Sheets adapter failed to init: {e}")
            results["google_sheets"] = False
    else:
        results["google_sheets"] = False

    # Google Drive backup
    if os.environ.get("GOOGLE_SA_KEY_PATH") and os.environ.get("BACKUP_FOLDER_ID"):
        try:
            from pib.adapters.google_drive import GoogleDriveBackup
            adapter = GoogleDriveBackup()
            await adapter.init()
            _adapters["google_drive"] = adapter
            results["google_drive"] = True
            log.info("Google Drive backup adapter initialized")
        except Exception as e:
            log.warning(f"Google Drive backup failed to init: {e}")
            results["google_drive"] = False
    else:
        results["google_drive"] = False

    log.info(f"Adapters initialized: {sum(1 for v in results.values() if v)}/{len(results)} active")
    return results


async def health_check() -> dict[str, dict]:
    """Ping all registered adapters and return health status."""
    status = {}
    for name, adapter in _adapters.items():
        try:
            ok = await adapter.ping()
            status[name] = {"ok": ok, "status": "connected" if ok else "unreachable"}
        except Exception as e:
            status[name] = {"ok": False, "status": "error", "error": str(e)}
    return status
