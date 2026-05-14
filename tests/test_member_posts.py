from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flin_linkedin_posts_mcp.auth import TokenRecord, TokenStore
from flin_linkedin_posts_mcp.config import LinkedInPostsSettings
from flin_linkedin_posts_mcp.tools.member_posts import (
    analyze_member_posts,
    enrich_member_posts_with_engagement,
    auth_status,
    get_member_post_analytics,
    get_post_social_metadata,
    list_member_posts,
    list_snapshot_domains,
    match_drafts_to_member_posts,
    logout,
)


@dataclass
class DummyClient:
    elements: list[dict[str, Any]]
    calls: list[tuple[str | None, int]] = field(default_factory=list)
    last_request_id: str | None = "req-1"
    social_metadata_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)
    analytics_payloads: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def iter_member_snapshot_elements(self, *, domain: str | None = None, page_size: int = 100):
        self.calls.append((domain, page_size))
        yield from self.elements

    def get_social_metadata(self, entity_urn: str) -> dict[str, Any]:
        return self.social_metadata_payloads[entity_urn]

    def batch_get_social_metadata(self, entity_urns: list[str]) -> dict[str, Any]:
        return {
            "results": {entity_urn: self.social_metadata_payloads[entity_urn] for entity_urn in entity_urns},
            "errors": {},
            "statuses": {},
        }

    def get_member_post_analytics(self, entity_urn: str, *, query_type: str, aggregation: str = "TOTAL") -> dict[str, Any]:
        return self.analytics_payloads[(entity_urn, query_type)]


def _settings(token_file: Path) -> LinkedInPostsSettings:
    return LinkedInPostsSettings(
        client_id="client-123",
        client_secret=None,
        oauth_flow="native_pkce",
        redirect_uri=None,
        scopes=("r_dma_portability_self_serve",),
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
                    "Likes": "12",
                    "Comments": 3,
                    "Impressions": "456",
                },
                {
                    "ShareId": "share-2",
                    "ShareCommentary": "Second post about analytics #AI #MCP",
                    "Date": "2025-12-31 10:00:00 UTC",
                    "ShareLink": "https://www.linkedin.com/feed/update/urn:li:share:2/",
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
    assert result["data"][0]["likes_count"] == 12
    assert result["data"][0]["comments_count"] == 3
    assert result["data"][0]["impressions_count"] == 456
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


def test_analyze_member_posts_limits_included_posts_without_changing_summary(tmp_path: Path) -> None:
    client = DummyClient(_snapshot_elements())

    result = analyze_member_posts(
        client=client,
        settings=_settings(tmp_path / "tokens.json"),
        arguments={"include_posts": True, "post_limit": 1},
    )

    assert result["data"]["post_count"] == 2
    assert result["data"]["included_post_count"] == 1
    assert [post["post_id"] for post in result["data"]["posts"]] == ["share-1"]


def test_list_member_posts_filters_and_limits_results(tmp_path: Path) -> None:
    client = DummyClient(_snapshot_elements())

    result = list_member_posts(
        client=client,
        settings=_settings(tmp_path / "tokens.json"),
        arguments={"published_after": "2026-01-01", "limit": 1},
    )

    assert [post["post_id"] for post in result["data"]] == ["share-1"]


def test_match_drafts_to_member_posts_returns_best_matches(tmp_path: Path) -> None:
    client = DummyClient(_snapshot_elements())

    result = match_drafts_to_member_posts(
        client=client,
        settings=_settings(tmp_path / "tokens.json"),
        arguments={
            "drafts": [
                "Hello LinkedIn #AI @OpenAI",
                "Analytics post about MCP",
            ],
            "max_matches_per_draft": 1,
        },
    )

    assert result["data"][0]["draft"] == "Hello LinkedIn #AI @OpenAI"
    assert result["data"][0]["matches"][0]["post_id"] == "share-1"
    assert result["data"][0]["matches"][0]["similarity"] == 1.0
    assert result["data"][1]["draft"] == "Analytics post about MCP"
    assert result["data"][1]["matches"][0]["post_id"] == "share-2"


def test_get_post_social_metadata_returns_normalized_counts(tmp_path: Path) -> None:
    client = DummyClient(
        _snapshot_elements(),
        social_metadata_payloads={
            "urn:li:share:123": {
                "entity": "urn:li:share:123",
                "commentsState": "OPEN",
                "commentSummary": {"count": 4, "topLevelCount": 3},
                "reactionSummaries": {
                    "LIKE": {"reactionType": "LIKE", "count": 2},
                    "EMPATHY": {"reactionType": "EMPATHY", "count": 1},
                },
            }
        },
    )

    result = get_post_social_metadata(
        client=client,
        settings=_settings(tmp_path / "tokens.json"),
        arguments={"post_urn": "urn:li:share:123"},
    )

    assert result["data"]["entity_urn"] == "urn:li:share:123"
    assert result["data"]["comments_count"] == 4
    assert result["data"]["reactions_total"] == 3
    assert result["data"]["reactions_by_type"] == {"LIKE": 2, "EMPATHY": 1}


def test_get_member_post_analytics_returns_metrics_by_type(tmp_path: Path) -> None:
    client = DummyClient(
        _snapshot_elements(),
        analytics_payloads={
            ("urn:li:share:123", "REACTION"): {"elements": [{"totalValue": {"long": 11}}]},
            ("urn:li:share:123", "COMMENT"): {"elements": [{"totalValue": {"long": 4}}]},
        },
    )

    result = get_member_post_analytics(
        client=client,
        settings=_settings(tmp_path / "tokens.json"),
        arguments={"post_urn": "urn:li:share:123", "metric_types": ["REACTION", "COMMENT"]},
    )

    assert result["data"]["entity_urn"] == "urn:li:share:123"
    assert result["data"]["metrics_by_type"] == {"REACTION": 11, "COMMENT": 4}


def test_enrich_member_posts_with_engagement_merges_metadata_and_analytics(tmp_path: Path) -> None:
    client = DummyClient(
        _snapshot_elements(),
        social_metadata_payloads={
            "urn:li:share:1": {
                "entity": "urn:li:share:1",
                "commentSummary": {"count": 7, "topLevelCount": 6},
                "reactionSummaries": {"LIKE": {"reactionType": "LIKE", "count": 5}},
            },
            "urn:li:share:2": {
                "entity": "urn:li:share:2",
                "commentSummary": {"count": 2, "topLevelCount": 2},
                "reactionSummaries": {"PRAISE": {"reactionType": "PRAISE", "count": 1}},
            },
        },
        analytics_payloads={
            ("urn:li:share:1", "IMPRESSION"): {"elements": [{"totalValue": {"long": 101}}]},
            ("urn:li:share:1", "REACTION"): {"elements": [{"totalValue": {"long": 5}}]},
            ("urn:li:share:2", "IMPRESSION"): {"elements": [{"totalValue": {"long": 51}}]},
            ("urn:li:share:2", "REACTION"): {"elements": [{"totalValue": {"long": 1}}]},
        },
    )

    result = enrich_member_posts_with_engagement(
        client=client,
        settings=_settings(tmp_path / "tokens.json"),
        arguments={"limit": 2, "analytics_metric_types": ["IMPRESSION", "REACTION"]},
    )

    assert result["data"][0]["entity_urn"] == "urn:li:share:1"
    assert result["data"][0]["comments_count"] == 7
    assert result["data"][0]["reactions_total"] == 5
    assert result["data"][0]["analytics"] == {"IMPRESSION": 101, "REACTION": 5}
    assert result["data"][0]["engagement_available"] is True
