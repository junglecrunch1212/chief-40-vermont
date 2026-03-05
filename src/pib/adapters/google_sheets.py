"""Google Sheets adapter — pushes DB state to configured Google Sheets."""

import json
import logging
import os

log = logging.getLogger(__name__)


class GoogleSheetsAdapter:
    """Push PIB data to Google Sheets using the Sheets API."""

    name = "google_sheets"
    source = "google_sheets"

    def __init__(self):
        self._service = None
        self._key_path = os.environ.get("GOOGLE_SA_KEY_PATH", "")

    async def init(self) -> None:
        """Initialize the Sheets API service."""
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(self._key_path, scopes=scopes)
        self._service = build("sheets", "v4", credentials=creds)
        log.info("Google Sheets adapter initialized")

    async def ping(self) -> bool:
        """Check if the Sheets API is reachable by reading a test range."""
        if not self._service:
            return False
        try:
            # Just verify the API works — actual sheet ID needed for real check
            self._service.spreadsheets().get(spreadsheetId="test").execute()
            return True
        except Exception as e:
            # 404 means API is working, sheet just doesn't exist
            if "404" in str(e) or "not found" in str(e).lower():
                return True
            log.warning(f"Sheets ping failed: {e}")
            return False

    async def poll(self) -> list:
        """Sheets adapter does not poll — inbound handled by webhook."""
        return []

    async def push(self, db, sheet_id: str, sheet_name: str, columns: list[str],
                   data: list[dict]) -> dict:
        """Push data to a specific sheet tab.

        Args:
            db: Database connection (unused but kept for consistency)
            sheet_id: Google Sheets spreadsheet ID
            sheet_name: Tab name within the spreadsheet
            columns: Column headers
            data: List of dicts to write

        Returns:
            Dict with push result
        """
        if not self._service:
            return {"ok": False, "error": "Sheets service not initialized"}

        try:
            # Build values array: header row + data rows
            values = [columns]
            for row in data:
                values.append([str(row.get(col, "")) for col in columns])

            # Clear existing data and write fresh
            range_str = f"{sheet_name}!A1"

            self._service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range=f"{sheet_name}!A:Z",
            ).execute()

            result = self._service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_str,
                valueInputOption="RAW",
                body={"values": values},
            ).execute()

            updated = result.get("updatedRows", 0)
            log.info(f"Sheets push: {sheet_name} updated with {updated} rows")
            return {"ok": True, "rows": updated}

        except Exception as e:
            log.error(f"Sheets push failed for {sheet_name}: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    async def send(self, message) -> None:
        """Sheets adapter does not send messages."""
        raise NotImplementedError("Google Sheets does not send messages")
