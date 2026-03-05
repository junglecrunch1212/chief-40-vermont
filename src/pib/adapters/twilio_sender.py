"""Twilio outbound adapter — sends SMS via Twilio REST API."""

import logging
import os

import httpx

log = logging.getLogger(__name__)


class TwilioSender:
    """Send SMS messages through Twilio."""

    name = "twilio"
    source = "twilio"

    def __init__(self):
        self._account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self._auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self._from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
        self._client: httpx.AsyncClient | None = None

    async def init(self) -> None:
        """Initialize the HTTP client with Twilio auth."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            auth=(self._account_sid, self._auth_token),
        )
        log.info("Twilio sender initialized")

    async def ping(self) -> bool:
        """Check if Twilio API is reachable."""
        if not self._client or not self._account_sid:
            return False
        try:
            resp = await self._client.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}.json"
            )
            return resp.status_code == 200
        except Exception as e:
            log.warning(f"Twilio ping failed: {e}")
            return False

    async def poll(self) -> list:
        """Twilio sender does not poll — inbound handled by webhook."""
        return []

    async def send(self, message) -> dict:
        """Send an SMS through Twilio.

        Args:
            message: OutboundMessage with channel='sms', to=phone number

        Returns:
            Dict with send result
        """
        if not self._client:
            raise RuntimeError("Twilio sender not initialized")

        resp = await self._client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json",
            data={
                "To": message.to,
                "From": self._from_number,
                "Body": message.content,
            },
        )

        if resp.status_code not in (200, 201):
            log.error(f"Twilio send failed ({resp.status_code}): {resp.text}")
            return {"ok": False, "error": resp.text, "status_code": resp.status_code}

        result = resp.json()
        log.info(f"SMS sent to {message.to}: SID={result.get('sid')}")
        return {"ok": True, "sid": result.get("sid")}

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
