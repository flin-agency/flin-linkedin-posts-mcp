"""Verify Community Management tools through real dispatch and HTTP serialization."""
from dataclasses import replace

import httpx
import pytest
import respx

from flin_linkedin_posts_mcp.auth import TokenRecord, TokenStore
from flin_linkedin_posts_mcp.config import load_config
from flin_linkedin_posts_mcp.dispatcher import dispatch_tool
from flin_linkedin_posts_mcp.errors import LinkedInPermissionError, LinkedInRateLimitError


@pytest.fixture
def settings(tmp_path):
    settings = load_config({
        "LINKEDIN_TOKEN_FILE": str(tmp_path / "portability.json"),
        "LINKEDIN_ANALYTICS_CLIENT_ID": "community-app",
        "LINKEDIN_ANALYTICS_SCOPES": "r_member_postAnalytics r_member_profileAnalytics",
    })
    TokenStore(settings.analytics.token_file).save(TokenRecord(
        access_token="community-token", expires_at=9999999999.0,
        scope=" ".join(settings.analytics.scopes), client_id="community-app",
    ))
    return settings


@respx.mock
def test_aggregate_metrics_use_member_finder_and_analytics_token(settings):
    route = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(
        200, json={"elements": [{"count": 27}]}, headers={"x-li-request-id": "analytics-request"},
    )
    result = dispatch_tool("get_member_analytics", {
        "metric_types": ["MEMBERS_REACHED", "MEMBERS_REACHED"],
        "start_date": "2026-11-01", "end_date": "2026-11-21",
    }, settings=settings)
    assert result["data"]["metrics_by_type"] == {"MEMBERS_REACHED": 27}
    assert result["data"]["scope"] == "member"
    assert result["meta"]["request_id"] == "analytics-request"
    assert len(route.calls) == 1
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer community-token"
    assert request.headers["X-RestLi-Method"] == "FINDER"
    assert request.headers["Linkedin-Version"] == "202610"
    assert request.url.params["q"] == "me"
    assert "entity" not in request.url.params
    assert request.url.params["dateRange"] == "(start:(year:2026,month:11,day:1),end:(year:2026,month:11,day:21))"
    assert not settings.token_file.exists()  # No portability login required.


@respx.mock
@pytest.mark.parametrize("urn,union", [("urn:li:share:123", "share"), ("urn:li:ugcPost:123", "ugc")])
def test_single_post_daily_series_preserves_every_date_and_missing_count(settings, urn, union):
    points = [{"count": 0, "dateRange": {"start": {"year": 2026, "month": 11, "day": 1}}},
              {"dateRange": {"start": {"year": 2026, "month": 11, "day": 2}}}]
    route = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(200, json={"elements": points})
    result = dispatch_tool("get_member_post_analytics", {
        "post_urn": urn, "aggregation": "DAILY", "metric_types": ["REACTION"],
        "start_date": "2026-11-01",
    }, settings=settings)
    assert result["data"]["series_by_type"] == {"REACTION": points}
    assert "metrics_by_type" not in result["data"]
    query = route.calls[0].request.url.query.decode()
    assert f"entity=({union}:urn%3Ali%3A" in query
    assert "%253A" not in query
    assert "dateRange=(start:(year:2026,month:11,day:1))" in query


@respx.mock
@pytest.mark.parametrize("tool,extra,expected", [
    ("get_member_analytics", {}, {"IMPRESSION", "RESHARE", "REACTION", "COMMENT"}),
    ("get_member_post_analytics", {"post_urn": "urn:li:share:123"}, {"RESHARE", "REACTION", "COMMENT"}),
])
def test_daily_defaults_only_request_supported_metrics(settings, tool, extra, expected):
    route = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(200, json={"elements": []})
    result = dispatch_tool(tool, {"aggregation": "DAILY", **extra}, settings=settings)
    assert set(result["data"]["series_by_type"]) == expected
    assert {call.request.url.params["queryType"] for call in route.calls} == expected


@respx.mock
@pytest.mark.parametrize("arguments", [
    {"start_date": "2026-02-30"}, {"start_date": "20261101"}, {"end_date": 123},
    {"start_date": "2026-11-02", "end_date": "2026-11-01"},
    {"start_date": "2026-11-01", "end_date": "2026-11-01"},
    {"aggregation": "WEEKLY"},
    *[{"aggregation": "DAILY", "metric_types": [metric]} for metric in (
        "MEMBERS_REACHED", "LINK_CLICKS", "FOLLOWER_GAINED_FROM_CONTENT", "PROFILE_VIEW_FROM_CONTENT",
    )],
])
def test_invalid_queries_rejected_without_spending_quota(settings, arguments):
    with pytest.raises(ValueError):
        dispatch_tool("get_member_analytics", arguments, settings=settings)
    assert not respx.calls


@respx.mock
def test_single_post_daily_impressions_rejected(settings):
    with pytest.raises(ValueError, match="IMPRESSION"):
        dispatch_tool("get_member_post_analytics", {
            "post_urn": "urn:li:share:1", "aggregation": "DAILY", "metric_types": ["IMPRESSION"],
        }, settings=settings)
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize("arguments,finder", [({}, "me"), ({"end_date": "2026-11-21"}, "dateRange")])
def test_follower_statistics_preserve_linkedin_response(settings, arguments, finder):
    payload = {"elements": [{"memberFollowersCount": 0}], "paging": {"total": 1}}
    route = respx.get("https://api.linkedin.com/rest/memberFollowersCount").respond(200, json=payload)
    result = dispatch_tool("get_member_follower_statistics", arguments, settings=settings)
    assert result["data"]["statistics"] == payload
    assert route.calls[0].request.url.params["q"] == finder
    assert route.calls[0].request.headers["Authorization"] == "Bearer community-token"
    if arguments:
        assert route.calls[0].request.url.params["dateRange"] == "(end:(year:2026,month:11,day:21))"
    else:
        assert "dateRange" not in route.calls[0].request.url.params


@respx.mock
def test_follower_permission_must_be_consented_again(settings):
    store = TokenStore(settings.analytics.token_file)
    store.save(replace(store.load(), scope="r_member_postAnalytics"))
    with pytest.raises(LinkedInPermissionError, match="LINKEDIN_ANALYTICS_SCOPES"):
        dispatch_tool("get_member_follower_statistics", {}, settings=settings)
    assert not respx.calls


@respx.mock
def test_rate_limit_stops_without_retrying_or_requesting_next_metric(settings):
    route = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(429)
    with pytest.raises(LinkedInRateLimitError):
        dispatch_tool("get_member_analytics", {}, settings=settings)
    assert len(route.calls) == 1


@respx.mock
def test_retry_keeps_query_and_token(settings, monkeypatch):
    monkeypatch.setattr("flin_linkedin_posts_mcp.linkedin_client.time.sleep", lambda _: None)
    route = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics")
    route.side_effect = [httpx.Response(500), httpx.Response(200, json={"elements": []})]
    result = dispatch_tool("get_member_analytics", {"metric_types": ["IMPRESSION"]}, settings=settings)
    assert result["data"]["metrics_by_type"]["IMPRESSION"] is None
    assert len(route.calls) == 2
    assert route.calls[0].request.url == route.calls[1].request.url


def test_blank_desktop_scopes_keep_analytics_optional():
    assert load_config({"LINKEDIN_ANALYTICS_SCOPES": ""}).analytics is None
    settings = load_config({"LINKEDIN_SCOPES": "r_member_profileAnalytics"})
    assert settings.for_connection("analytics") is settings
