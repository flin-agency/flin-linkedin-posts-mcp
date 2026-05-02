from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path

import httpx
import pytest
import respx

from flin_linkedin_posts_mcp.auth import (
    LinkedInOAuthClient,
    TokenRecord,
    TokenStore,
    build_code_challenge,
    generate_code_verifier,
)
from flin_linkedin_posts_mcp.config import LinkedInPostsSettings
from flin_linkedin_posts_mcp.errors import LinkedInValidationError


def _settings(token_file: Path) -> LinkedInPostsSettings:
    return LinkedInPostsSettings(
        client_id="client-123",
        client_secret=None,
        oauth_flow="native_pkce",
        redirect_uri=None,
        scopes=("r_dma_portability_3rd_party",),
        api_version="202312",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
        oauth_timeout_seconds=30,
        token_file=token_file,
    )


def test_generate_code_verifier_is_pkce_safe() -> None:
    verifier = generate_code_verifier()

    assert 43 <= len(verifier) <= 128
    assert re.fullmatch(r"[A-Za-z0-9._~-]+", verifier)


def test_build_code_challenge_uses_s256_base64url() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")

    assert build_code_challenge(verifier) == expected


def test_token_store_persists_and_clears_token(tmp_path: Path) -> None:
    token_file = tmp_path / "tokens.json"
    store = TokenStore(token_file)
    record = TokenRecord(
        access_token="access",
        expires_at=12345.0,
        token_type="Bearer",
        scope="r_dma_portability_3rd_party",
        refresh_token="refresh",
        refresh_expires_at=45678.0,
    )

    store.save(record)

    assert json.loads(token_file.read_text())["access_token"] == "access"
    if os.name != "nt":
        assert oct(token_file.stat().st_mode & 0o777) == "0o600"
    assert store.load() == record

    store.clear()

    assert store.load() is None
    assert not token_file.exists()


def test_token_record_expiry_uses_skew() -> None:
    record = TokenRecord(access_token="access", expires_at=1000.0)

    assert record.is_expired(now=940.0, skew_seconds=60) is True
    assert record.is_expired(now=939.0, skew_seconds=60) is False


def test_oauth_client_builds_native_pkce_authorization_url(tmp_path: Path) -> None:
    client = LinkedInOAuthClient(_settings(tmp_path / "tokens.json"))

    url = client.authorization_url(
        redirect_uri="http://127.0.0.1:3456/callback",
        state="state-123",
        code_challenge="challenge-123",
    )

    assert url.startswith("https://www.linkedin.com/oauth/native-pkce/authorization?")
    assert "client_id=client-123" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A3456%2Fcallback" in url
    assert "scope=r_dma_portability_3rd_party" in url
    assert "code_challenge=challenge-123" in url
    assert "code_challenge_method=S256" in url


def test_oauth_client_builds_authorization_code_url_without_pkce(tmp_path: Path) -> None:
    client = LinkedInOAuthClient(
        LinkedInPostsSettings(
            client_id="client-123",
            client_secret="secret-123",
            oauth_flow="authorization_code",
            redirect_uri="http://127.0.0.1:63141/callback",
            scopes=("r_dma_portability_3rd_party",),
            api_version="202312",
            restli_protocol_version="2.0.0",
            timeout_seconds=10,
            max_retries=1,
            oauth_timeout_seconds=30,
            token_file=tmp_path / "tokens.json",
        )
    )

    url = client.authorization_url(
        redirect_uri="http://127.0.0.1:63141/callback",
        state="state-123",
        code_challenge="challenge-123",
    )

    assert url.startswith("https://www.linkedin.com/oauth/v2/authorization?")
    assert "client_id=client-123" in url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A63141%2Fcallback" in url
    assert "scope=r_dma_portability_3rd_party" in url
    assert "code_challenge" not in url
    assert "code_challenge_method" not in url


@respx.mock
def test_oauth_client_exchanges_code_for_token_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    route = respx.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "access",
                "expires_in": 3600,
                "refresh_token": "refresh",
                "refresh_token_expires_in": 86400,
                "scope": "r_dma_portability_3rd_party",
                "token_type": "Bearer",
            },
        )
    )
    client = LinkedInOAuthClient(_settings(tmp_path / "tokens.json"))

    record = client.exchange_code(
        code="code-123",
        redirect_uri="http://127.0.0.1:3456/callback",
        code_verifier="verifier-123",
    )

    assert record.access_token == "access"
    assert record.expires_at == 4600.0
    assert record.refresh_token == "refresh"
    assert record.refresh_expires_at == 87400.0
    request = route.calls[0].request
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert b"grant_type=authorization_code" in request.content
    assert b"client_id=client-123" in request.content
    assert b"code_verifier=verifier-123" in request.content


@respx.mock
def test_oauth_client_exchanges_authorization_code_with_client_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    route = respx.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "access",
                "expires_in": 3600,
                "scope": "r_dma_portability_3rd_party",
                "token_type": "Bearer",
            },
        )
    )
    client = LinkedInOAuthClient(
        LinkedInPostsSettings(
            client_id="client-123",
            client_secret="secret-123",
            oauth_flow="authorization_code",
            redirect_uri="http://127.0.0.1:63141/callback",
            scopes=("r_dma_portability_3rd_party",),
            api_version="202312",
            restli_protocol_version="2.0.0",
            timeout_seconds=10,
            max_retries=1,
            oauth_timeout_seconds=30,
            token_file=tmp_path / "tokens.json",
        )
    )

    record = client.exchange_code(
        code="code-123",
        redirect_uri="http://127.0.0.1:63141/callback",
        code_verifier="verifier-123",
    )

    assert record.access_token == "access"
    request = route.calls[0].request
    assert b"client_id=client-123" in request.content
    assert b"client_secret=secret-123" in request.content
    assert b"code_verifier" not in request.content


def test_authorization_code_flow_requires_configured_redirect_uri(tmp_path: Path) -> None:
    settings = LinkedInPostsSettings(
        client_id="client-123",
        client_secret="secret-123",
        oauth_flow="authorization_code",
        redirect_uri=None,
        scopes=("r_dma_portability_3rd_party",),
        api_version="202312",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
        oauth_timeout_seconds=30,
        token_file=tmp_path / "tokens.json",
    )
    client = LinkedInOAuthClient(settings)

    with pytest.raises(LinkedInValidationError, match="LINKEDIN_REDIRECT_URI"):
        client.authorization_url(
            redirect_uri="http://127.0.0.1:63141/callback",
            state="state-123",
            code_challenge="challenge-123",
        )
