from __future__ import annotations

import pytest

from flin_linkedin_ads_mcp.config import load_config


def test_load_config_requires_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="LINKEDIN_ACCESS_TOKEN is required"):
        load_config()


def test_load_config_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "token")
    monkeypatch.delenv("LINKEDIN_API_VERSION", raising=False)
    monkeypatch.delenv("LINKEDIN_RESTLI_PROTOCOL_VERSION", raising=False)
    monkeypatch.delenv("LINKEDIN_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LINKEDIN_MAX_RETRIES", raising=False)

    settings = load_config()

    assert settings.access_token == "token"
    assert settings.api_version == "202603"
    assert settings.restli_protocol_version == "2.0.0"
    assert settings.timeout_seconds == 30.0
    assert settings.max_retries == 3
