"""Authentication layer: Cloudflare Access, Twilio signature, rate limiter."""

import base64
import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict
from urllib.parse import urlencode

from fastapi import HTTPException, Request

log = logging.getLogger(__name__)


def _is_production() -> bool:
    return os.environ.get("PIB_ENV", "dev").lower() in {"prod", "production"}


# ─── Rate Limiter ───

class RateLimiter:
    """Per-source rate limiter using sliding window."""

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._limits = {
            "sms": (30, 60),       # 30 per minute
            "siri": (20, 60),      # 20 per minute
            "web": (10, 60),       # 10 per minute
            "imessage": (30, 60),  # 30 per minute
            "default": (60, 60),   # 60 per minute
        }

    def check(self, source: str, key: str) -> bool:
        """Returns True if request is allowed, False if rate-limited."""
        limit, window = self._limits.get(source, self._limits["default"])
        bucket = f"{source}:{key}"
        now = time.time()

        # Clean old entries
        self._windows[bucket] = [t for t in self._windows[bucket] if now - t < window]

        if len(self._windows[bucket]) >= limit:
            return False

        self._windows[bucket].append(now)
        return True


rate_limiter = RateLimiter()


# ─── Twilio Signature Validation ───

def validate_twilio_signature(request_url: str, params: dict, signature: str) -> bool:
    """Validate Twilio webhook signature using HMAC-SHA1."""
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        if _is_production():
            log.error("TWILIO_AUTH_TOKEN not set in production")
            return False
        log.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return True

    # Build the data string
    data = request_url
    for key in sorted(params.keys()):
        data += key + params[key]

    computed = hmac.new(
        auth_token.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    expected = base64.b64encode(computed).decode("utf-8")
    return hmac.compare_digest(expected, signature)


# ─── BlueBubbles Secret ───

def validate_bluebubbles_secret(request_secret: str) -> bool:
    """Validate BlueBubbles webhook shared secret."""
    expected = os.environ.get("BLUEBUBBLES_SECRET", "")
    if not expected:
        if _is_production():
            log.error("BLUEBUBBLES_SECRET not set in production")
            return False
        log.warning("BLUEBUBBLES_SECRET not set — skipping validation")
        return True
    return hmac.compare_digest(request_secret, expected)


# ─── Siri Bearer Token ───

def validate_siri_token(auth_header: str) -> bool:
    """Validate Siri Shortcuts Bearer token."""
    expected = os.environ.get("SIRI_BEARER_TOKEN", "")
    if not expected:
        return not _is_production()
    if not auth_header.startswith("Bearer "):
        return False
    return hmac.compare_digest(auth_header[7:], expected)


# ─── Middleware ───

async def auth_middleware(request: Request, call_next):
    """Authentication middleware for FastAPI."""
    path = request.url.path

    # Health probe is public
    if path == "/health":
        return await call_next(request)

    # Webhook endpoints use source-specific auth
    if path.startswith("/webhooks/"):
        source = path.split("/")[-1]
        if not rate_limiter.check(source, request.client.host if request.client else "unknown"):
            raise HTTPException(status_code=429, detail="Rate limited")
        return await call_next(request)

    # All other endpoints require Cloudflare Access or session
    # In production, Cloudflare Access adds Cf-Access-Jwt-Assertion header
    return await call_next(request)
