from __future__ import annotations

from pathlib import Path

from flin_linkedin_posts_mcp.config import load_config


def test_load_config_does_not_require_static_access_token() -> None:
    settings = load_config({})

    assert settings.client_id is None
    assert settings.client_secret is None
    assert settings.oauth_flow == "native_pkce"
    assert settings.redirect_uri is None
    assert settings.scopes == ("r_dma_portability_self_serve",)
    assert settings.api_version == "202312"
    assert settings.restli_protocol_version == "2.0.0"
    assert settings.timeout_seconds == 30.0
    assert settings.max_retries == 3
    assert settings.token_file == Path.home() / ".flin-linkedin-posts-mcp" / "tokens.json"


def test_load_config_reads_oauth_settings() -> None:
    settings = load_config(
        {
            "LINKEDIN_CLIENT_ID": "client-123",
            "LINKEDIN_CLIENT_SECRET": "secret-123",
            "LINKEDIN_OAUTH_FLOW": "authorization_code",
            "LINKEDIN_REDIRECT_URI": "http://127.0.0.1:63141/callback",
            "LINKEDIN_SCOPES": "profile r_dma_portability_self_serve",
            "LINKEDIN_API_VERSION": "202401",
            "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0",
            "LINKEDIN_TIMEOUT_SECONDS": "12",
            "LINKEDIN_MAX_RETRIES": "2",
            "LINKEDIN_OAUTH_TIMEOUT_SECONDS": "180",
            "LINKEDIN_TOKEN_FILE": "/tmp/linkedin-token.json",
        }
    )

    assert settings.client_id == "client-123"
    assert settings.client_secret == "secret-123"
    assert settings.oauth_flow == "authorization_code"
    assert settings.redirect_uri == "http://127.0.0.1:63141/callback"
    assert settings.scopes == ("profile", "r_dma_portability_self_serve")
    assert settings.api_version == "202401"
    assert settings.timeout_seconds == 12.0
    assert settings.max_retries == 2
    assert settings.oauth_timeout_seconds == 180.0
    assert settings.token_file == Path("/tmp/linkedin-token.json")
