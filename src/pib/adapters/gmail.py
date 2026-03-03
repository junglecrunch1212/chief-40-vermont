"""Gmail adapter — polls inbox, writes to ops_comms, sends approved drafts.

Uses Gmail API via google-api-python-client with service account credentials
(domain-wide delegation) or OAuth2 for personal accounts.
"""

import base64
import json
import logging
import os
from datetime import datetime
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


class GmailAdapter:
    """Adapter for Gmail API — polls inbox and sends approved drafts."""

    name = "gmail"
    source = "gmail"

    def __init__(self):
        self._service = None
        self._key_path = os.environ.get("GOOGLE_SA_KEY_PATH", "")
        self._user_email = os.environ.get("GMAIL_USER_EMAIL", "")

    async def init(self) -> None:
        """Initialize the Gmail API service."""
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ]
        creds = Credentials.from_service_account_file(self._key_path, scopes=scopes)

        # Domain-wide delegation requires impersonating the user
        if self._user_email:
            creds = creds.with_subject(self._user_email)

        self._service = build("gmail", "v1", credentials=creds)
        log.info("Gmail adapter initialized")

    async def ping(self) -> bool:
        """Check if the Gmail API is reachable."""
        if not self._service:
            return False
        try:
            self._service.users().getProfile(userId="me").execute()
            return True
        except Exception as e:
            log.warning(f"Gmail ping failed: {e}")
            return False

    async def poll(self, db, max_results: int = 50) -> int:
        """Poll Gmail inbox for new messages and write to ops_comms.

        Filters messages against ops_gmail_whitelist and ops_gmail_triage_keywords.
        Only processes messages not already in ops_comms (dedup by message ID).

        Returns:
            Number of new messages ingested
        """
        if not self._service:
            log.error("Gmail service not initialized")
            return 0

        # Load whitelist and keywords
        whitelist = await self._load_whitelist(db)
        keywords = await self._load_triage_keywords(db)

        # Fetch recent unread messages
        try:
            results = self._service.users().messages().list(
                userId="me", q="is:unread", maxResults=max_results
            ).execute()
        except Exception as e:
            log.error(f"Gmail list failed: {e}")
            return 0

        messages = results.get("messages", [])
        if not messages:
            return 0

        ingested = 0
        for msg_stub in messages:
            msg_id = msg_stub["id"]

            # Dedup: skip if already ingested
            existing = await db.execute_fetchone(
                "SELECT 1 FROM ops_comms WHERE channel = 'email' AND id = ?",
                [f"gmail-{msg_id}"],
            )
            if existing:
                continue

            try:
                msg = self._service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()

                headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
                from_addr = headers.get("from", "")
                subject = headers.get("subject", "")
                to_addr = headers.get("to", "")
                date_str = headers.get("date", "")

                # Apply whitelist filter
                if whitelist and not self._matches_whitelist(from_addr, whitelist):
                    continue

                # Extract body snippet
                snippet = msg.get("snippet", "")

                # Check triage keywords for urgency
                urgency = self._check_urgency(subject, from_addr, snippet, keywords)

                # Determine batch window
                from pib.comms import assign_batch_window
                batch_window, batch_date = assign_batch_window()

                # Write to ops_comms
                from pib.db import next_id
                comm_id = f"gmail-{msg_id}"
                await db.execute(
                    "INSERT OR IGNORE INTO ops_comms "
                    "(id, date, channel, direction, from_addr, to_addr, subject, summary, "
                    "body_snippet, needs_response, response_urgency, comm_type, "
                    "batch_window, batch_date, extraction_status, created_by) "
                    "VALUES (?,date('now'),'email','inbound',?,?,?,?,?,?,?,?,?,?,'pending','gmail_adapter')",
                    [comm_id, from_addr, to_addr, subject, subject, snippet,
                     1 if urgency else 0, urgency, "email",
                     batch_window, batch_date],
                )
                ingested += 1

            except Exception as e:
                log.error(f"Gmail message {msg_id} processing failed: {e}", exc_info=True)

        if ingested > 0:
            await db.commit()
            log.info(f"Gmail: ingested {ingested} new messages")

        return ingested

    async def send(self, message) -> dict:
        """Send an email via Gmail API.

        Args:
            message: OutboundMessage with channel='email', to=email address

        Returns:
            Dict with send result
        """
        if not self._service:
            return {"ok": False, "error": "Gmail service not initialized"}

        try:
            mime = MIMEText(message.content)
            mime["to"] = message.to
            mime["subject"] = message.metadata.get("subject", "Message from PIB")

            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            result = self._service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()

            log.info(f"Email sent to {message.to}: {result.get('id')}")
            return {"ok": True, "message_id": result.get("id")}

        except Exception as e:
            log.error(f"Gmail send failed: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    async def _load_whitelist(self, db) -> list[dict]:
        """Load active Gmail whitelist entries."""
        rows = await db.execute_fetchall(
            "SELECT match_type, pattern FROM ops_gmail_whitelist WHERE active = 1"
        )
        return [dict(r) for r in rows] if rows else []

    async def _load_triage_keywords(self, db) -> list[dict]:
        """Load active triage keywords."""
        rows = await db.execute_fetchall(
            "SELECT keyword, match_field FROM ops_gmail_triage_keywords WHERE active = 1"
        )
        return [dict(r) for r in rows] if rows else []

    def _matches_whitelist(self, from_addr: str, whitelist: list[dict]) -> bool:
        """Check if a sender matches any whitelist entry."""
        from_lower = from_addr.lower()
        for entry in whitelist:
            pattern = entry["pattern"].lower()
            match_type = entry["match_type"]

            if match_type == "explicit_address" and pattern in from_lower:
                return True
            elif match_type == "domain" and from_lower.endswith(f"@{pattern}") or from_lower.endswith(f".{pattern}>"):
                return True
            elif match_type == "items_email" and pattern in from_lower:
                return True

        return False

    def _check_urgency(self, subject: str, from_addr: str, body: str,
                       keywords: list[dict]) -> str | None:
        """Check triage keywords and return urgency level if matched."""
        for kw in keywords:
            keyword = kw["keyword"].lower()
            field = kw["match_field"]

            if field == "subject" and keyword in subject.lower():
                return "medium"
            elif field == "from" and keyword in from_addr.lower():
                return "medium"
            elif field == "body" and keyword in body.lower():
                return "low"

        return None
