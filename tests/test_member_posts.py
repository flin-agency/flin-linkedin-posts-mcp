from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from flin_linkedin_posts_mcp.config import LinkedInPostsSettings
from flin_linkedin_posts_mcp.tools.member_posts import analyze_member_posts, get_member_profile, get_post, list_member_posts


@dataclass
class DummyClient:
    calls: list[tuple[str, dict | None]] = field(default_factory=list)
    last_request_id: str | None = "req-1"

    def get_json(self, path: str, params: dict | None = None) -> dict:
        self.calls.append((path, params))
        if path == "posts":
            return {
                "elements": [
                    {
                        "id": "urn:li:share:1",
                        "author": "urn:li:person:member-1",
                        "commentary": {"text": "Hello LinkedIn #AI @OpenAI"},
                        "publishedAt": "2026-03-20T10:00:00Z",
                    },
                    {
                        "id": "urn:li:share:2",
                        "author": "urn:li:person:member-1",
                        "commentary": {"text": "Second post about analytics #AI #MCP"},
                        "publishedAt": "2026-03-21T10:00:00Z",
                    },
                ],
                "paging": {"start": 0, "count": 2, "total": 2},
            }
        if path.startswith("posts/"):
            return {
                "id": "urn:li:share:1",
                "author": "urn:li:person:member-1",
                "commentary": {"text": "Hello LinkedIn #AI @OpenAI"},
                "publishedAt": "2026-03-20T10:00:00Z",
            }
        raise AssertionError(f"unexpected path: {path}")

    def get_json_url(self, url: str, params: dict | None = None) -> dict:
        self.calls.append((url, params))
        if url == "https://api.linkedin.com/v2/userinfo":
            return {"sub": "member-1", "name": "Ada Lovelace", "locale": "de_DE"}
        raise AssertionError(f"unexpected url: {url}")


@pytest.fixture
def settings() -> LinkedInPostsSettings:
    return LinkedInPostsSettings(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )


def test_get_member_profile_normalizes_userinfo(settings: LinkedInPostsSettings) -> None:
    client = DummyClient()

    result = get_member_profile(client=client, settings=settings, arguments={})

    assert result["data"]["member_urn"] == "urn:li:person:member-1"
    assert result["data"]["name"] == "Ada Lovelace"


def test_list_member_posts_uses_resolved_member_when_author_missing(settings: LinkedInPostsSettings) -> None:
    client = DummyClient()

    result = list_member_posts(client=client, settings=settings, arguments={"page_size": 2})

    assert result["ok"] is True
    assert result["data"][0]["hashtags"] == ["AI"]
    assert client.calls[0][0] == "https://api.linkedin.com/v2/userinfo"
    assert client.calls[1] == ("posts", {"q": "author", "author": "urn:li:person:member-1", "count": 2})


def test_get_post_rejects_invalid_urn(settings: LinkedInPostsSettings) -> None:
    client = DummyClient()

    with pytest.raises(ValueError, match="post URN"):
        get_post(client=client, settings=settings, arguments={"post_urn": "foo"})


def test_analyze_member_posts_returns_top_terms(settings: LinkedInPostsSettings) -> None:
    client = DummyClient()

    result = analyze_member_posts(client=client, settings=settings, arguments={"author_urn": "urn:li:person:member-1", "page_size": 2, "top_n": 3})

    assert result["data"]["post_count"] == 2
    assert result["data"]["top_hashtags"][0] == {"value": "ai", "count": 2}
    assert any(item["value"] == "linkedin" for item in result["data"]["top_terms"])
