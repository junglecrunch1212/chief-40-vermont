"""BlueBubbles outbound adapter — sends iMessages via per-bridge BlueBubbles REST API.

Each household member has their own BlueBubbles instance on their personal Mac Mini.
Credentials: BLUEBUBBLES_{MEMBER}_SECRET and BLUEBUBBLES_{MEMBER}_URL.
"""

import logging
import os
import re

import httpx

log = logging.getLogger(__name__)


class BlueBubblesSender:
    """Send iMessages through per-member BlueBubbles servers."""

    name = "bluebubbles"
    source = "bluebubbles"

    def __init__(self):
        # Per-bridge configuration
        self._bridges = {}
        # Auto-discover bridge members from BLUEBUBBLES_*_SECRET env vars
        members = [m.group(1) for key in os.environ
                   if (m := re.match(r'BLUEBUBBLES_(\w+)_SECRET', key))]
        for member in members:
            url = os.environ.get(f"BLUEBUBBLES_{member}_URL", "").rstrip("/")
            secret = os.environ.get(f"BLUEBUBBLES_{member}_SECRET", "")
            if url and secret:
                self._bridges[member.lower()] = {"url": url, "secret": secret}
        self._client: httpx.AsyncClient | None = None

    async def init(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)
        log.info(f"BlueBubbles sender initialized with {len(self._bridges)} bridge(s)")

    async def ping(self) -> bool:
        """Check if at least one BlueBubbles server is reachable."""
        if not self._client or not self._bridges:
            return False
        for member, bridge in self._bridges.items():
            try:
                resp = await self._client.get(
                    f"{bridge['url']}/api/v1/server/info",
                    params={"password": bridge["secret"]},
                )
                if resp.status_code == 200:
                    return True
            except Exception as e:
                log.warning(f"BlueBubbles ping failed for {member}: {e}")
        return False

    async def poll(self) -> list:
        """BlueBubbles sender does not poll — inbound handled by webhook."""
        return []

    def _resolve_bridge(self, message) -> dict | None:
        """Resolve which bridge to use based on message member_id."""
        member_id = getattr(message, "member_id", None) or ""
        # Try to match member_id (e.g. "m-james" → "james")
        member_key = member_id.replace("m-", "").lower() if member_id else ""
        if member_key in self._bridges:
            return self._bridges[member_key]
        # No fallback — refuse to send if member_id doesn't match a known bridge
        log.error(f"No BlueBubbles bridge for member_id={member_id!r} (resolved key={member_key!r})")
        return None

    async def send(self, message) -> dict:
        """Send an iMessage through the appropriate member's BlueBubbles bridge.

        Args:
            message: OutboundMessage with channel='imessage', to=phone/email handle

        Returns:
            Dict with send result
        """
        if not self._client:
            raise RuntimeError("BlueBubbles sender not initialized")

        bridge = self._resolve_bridge(message)
        if not bridge:
            return {"ok": False, "error": "No BlueBubbles bridge configured"}

        payload = {
            "chatGuid": f"iMessage;-;{message.to}",
            "message": message.content,
            "method": "apple-script",
        }

        resp = await self._client.post(
            f"{bridge['url']}/api/v1/message/text",
            json=payload,
            params={"password": bridge["secret"]},
        )

        if resp.status_code != 200:
            log.error(f"BlueBubbles send failed ({resp.status_code}): {resp.text}")
            return {"ok": False, "error": resp.text, "status_code": resp.status_code}

        result = resp.json()
        log.info(f"iMessage sent to {message.to}: {result.get('status', 'ok')}")
        return {"ok": True, "message_guid": result.get("data", {}).get("guid")}

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
