"""BlueBubbles outbound adapter — sends iMessages via BlueBubbles REST API."""

import logging
import os

import httpx

log = logging.getLogger(__name__)


class BlueBubblesSender:
    """Send iMessages through a BlueBubbles server."""

    name = "bluebubbles"
    source = "bluebubbles"

    def __init__(self):
        self._base_url = os.environ.get("BLUEBUBBLES_URL", "").rstrip("/")
        self._secret = os.environ.get("BLUEBUBBLES_SECRET", "")
        self._client: httpx.AsyncClient | None = None

    async def init(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)
        log.info("BlueBubbles sender initialized")

    async def ping(self) -> bool:
        """Check if BlueBubbles server is reachable."""
        if not self._client or not self._base_url:
            return False
        try:
            resp = await self._client.get(
                f"{self._base_url}/api/v1/server/info",
                params={"password": self._secret},
            )
            return resp.status_code == 200
        except Exception as e:
            log.warning(f"BlueBubbles ping failed: {e}")
            return False

    async def poll(self) -> list:
        """BlueBubbles sender does not poll — inbound handled by webhook."""
        return []

    async def send(self, message) -> dict:
        """Send an iMessage through BlueBubbles.

        Args:
            message: OutboundMessage with channel='imessage', to=phone/email handle

        Returns:
            Dict with send result
        """
        if not self._client:
            raise RuntimeError("BlueBubbles sender not initialized")

        payload = {
            "chatGuid": f"iMessage;-;{message.to}",
            "message": message.content,
            "method": "apple-script",
        }

        resp = await self._client.post(
            f"{self._base_url}/api/v1/message/text",
            json=payload,
            params={"password": self._secret},
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
