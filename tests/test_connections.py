"""Exercise the two-app workflow at the HTTP boundary, without live credentials."""
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

import httpx
import pytest
import respx

from flin_linkedin_posts_mcp.auth import TokenRecord, TokenStore, load_valid_token, run_local_oauth_login
from flin_linkedin_posts_mcp.config import load_config
from flin_linkedin_posts_mcp.errors import LinkedInAuthError, LinkedInPermissionError
from flin_linkedin_posts_mcp.tools.member_posts import (
    auth_status, enrich_member_posts_with_engagement, get_member_post_analytics, login, logout,
)


@pytest.fixture
def settings(tmp_path):
    return load_config({
        "LINKEDIN_CLIENT_ID": "portability-app",
        "LINKEDIN_TOKEN_FILE": str(tmp_path / "tokens.json"),
        "LINKEDIN_ANALYTICS_CLIENT_ID": "analytics-app",
        "LINKEDIN_ANALYTICS_CLIENT_SECRET": "analytics-secret",
        "LINKEDIN_ANALYTICS_REDIRECT_URI": "http://127.0.0.1:63142/callback",
    })


def save_tokens(settings):
    for connection in ("portability", "analytics"):
        selected = settings.for_connection(connection)
        TokenStore(selected.token_file).save(TokenRecord(
            access_token=f"{connection}-token", expires_at=9999999999.0,
            scope=" ".join(selected.scopes), client_id=selected.client_id,
        ))


def snapshot(count=2, *, post_id=None):
    return {"elements": [{"snapshotDomain": "MEMBER_SHARE_INFO", "snapshotData": [
        {"ShareId": post_id or f"urn:li:share:{i}", "ShareCommentary": f"Post {i}", "Date": "2026-11-14"}
        for i in range(1, count + 1)
    ]}]}


def test_separate_configuration_and_status(settings):
    save_tokens(settings)
    analytics = settings.for_connection("analytics")
    assert analytics.token_file == settings.token_file.with_name("tokens.analytics.json")
    assert analytics.scopes == ("r_member_postAnalytics",)
    assert analytics.oauth_flow == "authorization_code"
    result = auth_status(client=None, settings=settings, arguments={})["data"]
    assert result["authenticated"] is True  # Preserve the original top-level shape.
    assert result["connections"]["analytics"]["authenticated"] is True
    assert "analytics-token" not in str(result)
    assert "analytics-secret" not in str(result)
    logout(client=None, settings=settings, arguments={"connection": "analytics"})
    assert TokenStore(analytics.token_file).load() is None
    assert TokenStore(settings.token_file).load() is not None


def test_login_routes_to_selected_app(settings, monkeypatch):
    seen = []
    def fake_login(selected):
        seen.append(selected)
        return TokenRecord(access_token="new", expires_at=9999999999.0, client_id=selected.client_id)
    monkeypatch.setattr("flin_linkedin_posts_mcp.tools.member_posts.run_local_oauth_login", fake_login)
    login(client=None, settings=settings, arguments={"connection": "analytics"})
    login(client=None, settings=settings, arguments={})
    assert [item.client_id for item in seen] == ["analytics-app", "portability-app"]


@respx.mock
def test_actual_oauth_login_binds_analytics_token(settings):
    save_tokens(settings)
    original = settings.token_file.read_bytes()
    # Dynamic loopback port avoids reserving a fixed port in the test suite.
    selected = replace(settings.analytics, oauth_flow="native_pkce", redirect_uri=None, client_secret=None)
    route = respx.post("https://www.linkedin.com/oauth/v2/accessToken").respond(200, json={
        "access_token": "new-analytics", "expires_in": 3600, "scope": "r_member_postAnalytics",
    })
    def browser(url):
        query = parse_qs(urlparse(url).query)
        assert query["client_id"] == ["analytics-app"]
        assert query["scope"] == ["r_member_postAnalytics"]
        callback = query["redirect_uri"][0] + "?" + urlencode({"state": query["state"][0], "code": "code"})
        with urlopen(callback, timeout=5) as response:
            assert response.status == 200
        return True
    record = run_local_oauth_login(selected, open_browser=browser)
    assert record.client_id == "analytics-app"
    assert TokenStore(selected.token_file).load() == record
    assert settings.token_file.read_bytes() == original
    assert b"client_id=analytics-app" in route.calls[0].request.content


@pytest.mark.parametrize("mode", ["same", "relative", "symlink", "hardlink"])
def test_shared_token_files_are_rejected(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "tokens.json"
    first.write_text("{}")
    second = tmp_path / "other.json"
    if mode == "symlink":
        second.symlink_to(first)
    elif mode == "hardlink":
        second.hardlink_to(first)
    else:
        second = first if mode == "same" else Path("tokens.json")
    with pytest.raises(ValueError, match="different token files"):
        load_config({"LINKEDIN_TOKEN_FILE": str(first), "LINKEDIN_ANALYTICS_CLIENT_ID": "app",
                     "LINKEDIN_ANALYTICS_TOKEN_FILE": str(second)})


def test_optional_blank_desktop_fields_and_partial_configuration():
    assert load_config({"LINKEDIN_ANALYTICS_CLIENT_ID": "", "LINKEDIN_ANALYTICS_REDIRECT_URI": ""}).analytics is None
    with pytest.raises(ValueError, match="CLIENT_ID"):
        load_config({"LINKEDIN_ANALYTICS_CLIENT_SECRET": "secret"})
    with pytest.raises(ValueError, match="not configured"):
        load_config({}).for_connection("analytics")
    shared = load_config({"LINKEDIN_SCOPES": "r_dma_portability_self_serve r_member_postAnalytics"})
    assert shared.for_connection("analytics") is shared


@pytest.mark.parametrize("client_id", [None, "wrong-app"])
def test_analytics_rejects_unbound_or_wrong_app_tokens(settings, client_id):
    TokenStore(settings.analytics.token_file).save(TokenRecord(
        access_token="copied", expires_at=9999999999.0, client_id=client_id,
    ))
    with pytest.raises(LinkedInAuthError, match="does not match"):
        load_valid_token(settings.analytics)
    result = auth_status(client=None, settings=settings, arguments={"connection": "analytics"})
    assert result["data"]["authenticated"] is False


@respx.mock
def test_refresh_uses_second_app_and_preserves_scope(settings):
    selected = settings.analytics
    TokenStore(selected.token_file).save(TokenRecord(
        access_token="old", expires_at=1, refresh_token="refresh", refresh_expires_at=9999999999.0,
        scope="r_member_postAnalytics", client_id=selected.client_id,
    ))
    route = respx.post("https://www.linkedin.com/oauth/v2/accessToken").respond(200, json={
        "access_token": "refreshed", "expires_in": 3600,
    })
    record = load_valid_token(selected)
    assert b"client_id=analytics-app" in route.calls[0].request.content
    assert b"client_secret=analytics-secret" in route.calls[0].request.content
    assert record.client_id == "analytics-app"
    assert record.scope == "r_member_postAnalytics"
    assert record.refresh_token == "refresh"
    assert not settings.token_file.exists()


@respx.mock
def test_combines_content_and_metrics_with_the_correct_tokens(settings):
    save_tokens(settings)
    content = respx.get("https://api.linkedin.com/rest/memberSnapshotData").respond(200, json=snapshot())
    metrics = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(200, json={"elements": [{"count": 9}]})
    result = enrich_member_posts_with_engagement(client=None, settings=settings, arguments={})
    assert result["data"][0]["text"] == "Post 1"
    assert result["data"][0]["analytics"]["IMPRESSION"] == 9
    assert result["data"][0]["engagement_available"] is True
    assert len(metrics.calls) == 10
    assert content.calls[0].request.headers["Authorization"] == "Bearer portability-token"
    assert content.calls[0].request.headers["Linkedin-Version"] == "202312"
    assert all(call.request.headers["Authorization"] == "Bearer analytics-token" for call in metrics.calls)
    assert all(call.request.headers["Linkedin-Version"] == "202610" for call in metrics.calls)
    assert all(call.request.headers.get("X-RestLi-Method") != "BATCH_GET" for call in respx.calls)


@respx.mock
def test_single_post_analytics_does_not_require_portability_login(settings):
    TokenStore(settings.analytics.token_file).save(TokenRecord(
        access_token="analytics-token", expires_at=9999999999.0,
        scope="r_member_postAnalytics", client_id="analytics-app",
    ))
    respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(200, json={"elements": [{"count": 0}]})
    result = get_member_post_analytics(client=None, settings=settings, arguments={
        "post_urn": "urn:li:ugcPost:1", "metric_types": ["POST_SAVE", "LINK_CLICKS", "PROFILE_VIEW_FROM_CONTENT"],
    })
    assert result["data"]["metrics_by_type"] == {"POST_SAVE": 0, "LINK_CLICKS": 0, "PROFILE_VIEW_FROM_CONTENT": 0}


@respx.mock
def test_missing_second_token_never_falls_back_to_first(settings):
    save_tokens(settings)
    TokenStore(settings.analytics.token_file).clear()
    with pytest.raises(LinkedInAuthError, match="analytics"):
        get_member_post_analytics(client=None, settings=settings, arguments={"post_urn": "urn:li:share:1"})
    assert not respx.calls


@respx.mock
def test_known_missing_scope_is_reported_without_network(settings):
    save_tokens(settings)
    store = TokenStore(settings.analytics.token_file)
    store.save(replace(store.load(), scope="profile"))
    with pytest.raises(LinkedInPermissionError, match="r_member_postAnalytics"):
        get_member_post_analytics(client=None, settings=settings, arguments={"post_urn": "urn:li:share:1"})
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize("status", [401, 403, 429])
def test_enrichment_stops_on_access_or_rate_errors_but_keeps_content(settings, status):
    save_tokens(settings)
    respx.get("https://api.linkedin.com/rest/memberSnapshotData").respond(200, json=snapshot())
    metrics = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(status, json={"message": "denied"})
    result = enrich_member_posts_with_engagement(client=None, settings=settings, arguments={})
    assert len(metrics.calls) == 1
    assert len(result["data"]) == 2
    assert all(post["text"] and post["engagement_errors"] for post in result["data"])
    assert all(post["engagement_available"] is False for post in result["data"])


@respx.mock
@pytest.mark.parametrize("social_status, expected_analytics_calls", [(403, 10), (429, 0)])
def test_social_scope_failure_allows_analytics_but_rate_limit_stops_both(settings, social_status, expected_analytics_calls):
    save_tokens(settings)
    respx.get("https://api.linkedin.com/rest/memberSnapshotData").respond(200, json=snapshot())
    social = respx.get(url__regex=r"https://api.linkedin.com/rest/socialMetadata/.*").respond(
        social_status, json={"message": "denied"},
    )
    metrics = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(
        200, json={"elements": [{"count": 9}]},
    )
    result = enrich_member_posts_with_engagement(client=None, settings=settings, arguments={"include_social_metadata": True})
    assert len(social.calls) == 1
    assert len(metrics.calls) == expected_analytics_calls
    assert all(post["text"] and post["engagement_errors"] for post in result["data"])


@respx.mock
def test_request_budget_counts_retries(settings, monkeypatch):
    save_tokens(settings)
    monkeypatch.setattr("flin_linkedin_posts_mcp.linkedin_client.time.sleep", lambda _: None)
    respx.get("https://api.linkedin.com/rest/memberSnapshotData").respond(200, json=snapshot())
    metrics = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics")
    metrics.side_effect = [httpx.Response(500), httpx.Response(200, json={"elements": [{"count": 2}]})]
    result = enrich_member_posts_with_engagement(client=None, settings=settings, arguments={
        "limit": 2, "analytics_metric_types": ["IMPRESSION"], "max_api_calls": 2,
    })
    assert len(metrics.calls) == 2
    assert result["data"][0]["analytics"]["IMPRESSION"] == 2
    assert result["data"][1]["engagement_errors"][0]["code"] == "rate_limit_error"


@respx.mock
def test_large_request_rejected_before_fetching_any_data(settings):
    with pytest.raises(ValueError, match="125 API calls"):
        enrich_member_posts_with_engagement(client=None, settings=settings, arguments={"limit": 25})
    assert not respx.calls


@respx.mock
def test_missing_metrics_are_not_zero_or_available(settings):
    save_tokens(settings)
    respx.get("https://api.linkedin.com/rest/memberSnapshotData").respond(200, json=snapshot(1))
    respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").respond(200, json={"elements": []})
    result = enrich_member_posts_with_engagement(client=None, settings=settings, arguments={"limit": 1})
    assert result["data"][0]["engagement_available"] is False
    assert all(value is None for value in result["data"][0]["analytics"].values())


@respx.mock
def test_activity_ids_are_not_guessed(settings):
    save_tokens(settings)
    respx.get("https://api.linkedin.com/rest/memberSnapshotData").respond(200, json=snapshot(1, post_id="urn:li:activity:123"))
    result = enrich_member_posts_with_engagement(client=None, settings=settings, arguments={"limit": 1})
    assert len(respx.calls) == 1
    assert "cannot safely be converted" in result["data"][0]["engagement_errors"][0]["message"]
