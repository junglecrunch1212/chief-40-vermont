import os

import pytest

from pib.readiness import evaluate_readiness, validate_strict_startup


@pytest.mark.asyncio
async def test_readiness_reports_missing_required(db):
    for key in [
        "ANTHROPIC_API_KEY",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER",
        "BLUEBUBBLES_SECRET",
        "SIRI_BEARER_TOKEN",
        "GOOGLE_SA_KEY_PATH",
    ]:
        os.environ.pop(key, None)

    report = await evaluate_readiness(db)
    assert report["ready"] is False
    assert "env_anthropic_api_key" in report["required_failed"]
    assert "table_ops_tasks" in report["checks"]


def test_validate_strict_startup_raises(monkeypatch):
    monkeypatch.setenv("PIB_STRICT_STARTUP", "1")
    with pytest.raises(RuntimeError):
        validate_strict_startup({"ready": False, "required_failed": ["x"]})


def test_validate_strict_startup_no_raise(monkeypatch):
    monkeypatch.setenv("PIB_STRICT_STARTUP", "1")
    validate_strict_startup({"ready": True, "required_failed": []})
