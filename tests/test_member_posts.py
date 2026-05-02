from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flin_linkedin_posts_mcp.auth import TokenRecord, TokenStore
from flin_linkedin_posts_mcp.config import LinkedInPostsSettings
from flin_linkedin_posts_mcp.tools.member_posts import (
    analyze_member_posts,
    auth_status,
    list_member_posts,
    list_snapshot_domains,
    logout,
)


@dataclass
class DummyClient:
    elements: list[dict[str, Any]]
    calls: list[tuple[str | None, int]] = field(default_factory=list)
    last_request_id: str | None = "req-1"

    def iter_member_snapshot_elements(self, *, domain: str | None = None, page_size: int = 100):
        self.calls.append((domain, page_size))
        yield from self.elements


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


def _snapshot_elements() -> list[dict[str, Any]]:
    return [
        {
            "snapshotDomain": "MEMBER_SHARE_INFO",
            "snapshotData": [
                {
                    "ShareId": "share-1",
                    "ShareCommentary": "Hello LinkedIn #AI @OpenAI",
                    "Date": "2026-03-20 10:00:00 UTC",
                    "ShareLink": "https://www.linkedin.com/feed/update/urn:li:share:1/",
                    "Visibility": "PUBLIC",
                },
                {
                    "ShareId": "share-2",
                    "ShareCommentary": "Second post about analytics #AI #MCP",
                    "Date": "2025-12-31 10:00:00 UTC",
                },
            ],
        },
        {
            "snapshotDomain": "PROFILE",
            "snapshotData": [{"First Name": "Nic"}],
        },
    ]


def test_auth_status_reports_missing_token(tmp_path: Path) -> None:
    result = auth_status(client=None, settings=_settings(tmp_path / "tokens.json"), arguments={})

    assert result["data"]["authenticated"] is False
    assert result["data"]["client_id_configured"] is True


def test_auth_status_reports_stored_token(tmp_path: Path) -> None:
    token_file = tmp_path / "tokens.json"
    TokenStore(token_file).save(TokenRecord(access_token="access", expires_at=9999999999.0, scope="scope"))

    result = auth_status(client=None, settings=_settings(token_file), arguments={})

    assert result["data"]["authenticated"] is True
    assert result["data"]["expired"] is False
    assert result["data"]["scope"] == "scope"


def test_logout_clears_stored_token(tmp_path: Path) -> None:
    token_file = tmp_path / "tokens.json"
    TokenStore(token_file).save(TokenRecord(access_token="access", expires_at=9999999999.0))

    result = logout(client=None, settings=_settings(token_file), arguments={})

    assert result["data"]["authenticated"] is False
    assert not token_file.exists()


def test_list_snapshot_domains_summarizes_snapshot_data_counts(tmp_path: Path) -> None:
    client = DummyClient(_snapshot_elements())

    result = list_snapshot_domains(client=client, settings=_settings(tmp_path / "tokens.json"), arguments={"page_size": 50})

    assert result["data"] == [
        {"domain": "MEMBER_SHARE_INFO", "count": 2},
        {"domain": "PROFILE", "count": 1},
    ]
    assert client.calls == [(None, 50)]


def test_list_member_posts_normalizes_member_share_info(tmp_path: Path) -> None:
    client = DummyClient(_snapshot_elements())

    result = list_member_posts(client=client, settings=_settings(tmp_path / "tokens.json"), arguments={"page_size": 25})

    assert result["ok"] is True
    assert result["data"][0]["post_id"] == "share-1"
    assert result["data"][0]["text"] == "Hello LinkedIn #AI @OpenAI"
    assert result["data"][0]["hashtags"] == ["AI"]
    assert result["data"][0]["mentions"] == ["OpenAI"]
    assert result["data"][0]["published_at"] == "2026-03-20T10:00:00Z"
    assert result["data"][0]["url"] == "https://www.linkedin.com/feed/update/urn:li:share:1/"
    assert client.calls == [("MEMBER_SHARE_INFO", 25)]


def test_analyze_member_posts_filters_by_date(tmp_path: Path) -> None:
    client = DummyClient(_snapshot_elements())

    result = analyze_member_posts(
        client=client,
        settings=_settings(tmp_path / "tokens.json"),
        arguments={"published_after": "2026-01-01", "top_n": 3},
    )

    assert result["data"]["post_count"] == 1
    assert result["data"]["posts_with_text"] == 1
    assert result["data"]["top_hashtags"] == [{"value": "ai", "count": 1}]
