from __future__ import annotations

import httpx
import pytest
import respx

from flin_linkedin_posts_mcp.errors import LinkedInPermissionError, LinkedInRateLimitError
from flin_linkedin_posts_mcp.linkedin_client import (
    LinkedInClient,
    format_member_post_analytics_entity,
    normalize_post_urn,
)


@respx.mock
def test_get_json_retries_after_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    route = respx.get("https://api.linkedin.com/rest/posts")
    route.side_effect = [
        httpx.Response(429, json={"message": "rate limit"}),
        httpx.Response(200, json={"elements": [{"id": 1}]}, headers={"x-li-request-id": "req-1"}),
    ]

    sleeps: list[float] = []
    monkeypatch.setattr("flin_linkedin_posts_mcp.linkedin_client.time.sleep", lambda seconds: sleeps.append(seconds))

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=2,
    )
    payload = client.get_json("posts", params={"q": "author"})

    assert payload["elements"] == [{"id": 1}]
    assert sleeps == [0.5]


@respx.mock
def test_get_json_uses_required_linkedin_headers() -> None:
    route = respx.get("https://api.linkedin.com/rest/posts").mock(return_value=httpx.Response(200, json={"elements": []}))

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    client.get_json("posts", params={"q": "author", "count": 10})

    request = route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer token"
    assert request.headers.get("Linkedin-Version") == "202602"
    assert request.headers.get("X-Restli-Protocol-Version") == "2.0.0"
    assert request.headers.get("X-RestLi-Method") == "FINDER"


@respx.mock
def test_get_member_snapshot_data_uses_criteria_finder() -> None:
    route = respx.get("https://api.linkedin.com/rest/memberSnapshotData").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202312",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    client.get_member_snapshot_data(domain="MEMBER_SHARE_INFO", count=25, start=50)

    request = route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer token"
    assert request.headers.get("Linkedin-Version") == "202312"
    assert request.headers.get("X-RestLi-Method") == "FINDER"
    assert request.url.params["q"] == "criteria"
    assert request.url.params["domain"] == "MEMBER_SHARE_INFO"
    assert request.url.params["count"] == "25"
    assert request.url.params["start"] == "50"


@respx.mock
def test_iter_member_snapshot_elements_follows_next_links() -> None:
    route = respx.get("https://api.linkedin.com/rest/memberSnapshotData")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "elements": [{"snapshotDomain": "MEMBER_SHARE_INFO", "snapshotData": [{"id": "1"}]}],
                "paging": {"links": [{"rel": "next", "href": "/rest/memberSnapshotData?q=criteria&start=1&count=1"}]},
            },
        ),
        httpx.Response(
            200,
            json={
                "elements": [{"snapshotDomain": "MEMBER_SHARE_INFO", "snapshotData": [{"id": "2"}]}],
                "paging": {"links": []},
            },
        ),
    ]

    client = LinkedInClient(
        access_token="token",
        api_version="202312",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )

    elements = list(client.iter_member_snapshot_elements(domain="MEMBER_SHARE_INFO", page_size=1))

    assert [item["snapshotData"][0]["id"] for item in elements] == ["1", "2"]
    assert route.calls[1].request.url.params["start"] == "1"


@respx.mock
def test_get_json_url_skips_restli_method_for_v2_userinfo() -> None:
    route = respx.get("https://api.linkedin.com/v2/userinfo").mock(return_value=httpx.Response(200, json={"sub": "abc"}))

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    client.get_json_url("https://api.linkedin.com/v2/userinfo")

    request = route.calls[0].request
    assert request.headers.get("X-RestLi-Method") is None


@respx.mock
def test_get_json_maps_permission_error() -> None:
    respx.get("https://api.linkedin.com/rest/posts").mock(return_value=httpx.Response(403, json={"message": "Permission denied"}))

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )

    with pytest.raises(LinkedInPermissionError):
        client.get_json("posts", params={"q": "author"})


@respx.mock
def test_get_json_raises_rate_limit_error_after_retries() -> None:
    respx.get("https://api.linkedin.com/rest/posts").mock(return_value=httpx.Response(429, json={"message": "rate limit"}))

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )

    with pytest.raises(LinkedInRateLimitError):
        client.get_json("posts", params={"q": "author"})


def test_normalize_post_urn_handles_direct_and_encoded_values() -> None:
    assert normalize_post_urn("urn:li:share:123") == "urn:li:share:123"
    assert normalize_post_urn("https://www.linkedin.com/feed/update/urn%3Ali%3AugcPost%3A456") == "urn:li:ugcPost:456"


def test_format_member_post_analytics_entity_wraps_supported_urns() -> None:
    assert format_member_post_analytics_entity("urn:li:share:123") == "(share:urn%3Ali%3Ashare%3A123)"
    assert format_member_post_analytics_entity("urn:li:ugcPost:456") == "(ugc:urn%3Ali%3AugcPost%3A456)"


@respx.mock
def test_get_social_metadata_reads_single_entity() -> None:
    route = respx.get("https://api.linkedin.com/rest/socialMetadata/urn%3Ali%3Ashare%3A123").mock(
        return_value=httpx.Response(200, json={"entity": "urn:li:share:123", "commentSummary": {"count": 4}})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202312",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    payload = client.get_social_metadata("urn:li:share:123")

    request = route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer token"
    assert request.headers.get("Linkedin-Version") == "202602"
    assert payload["commentSummary"]["count"] == 4


@respx.mock
def test_batch_get_social_metadata_uses_batch_get_semantics() -> None:
    route = respx.get("https://api.linkedin.com/rest/socialMetadata").mock(
        return_value=httpx.Response(200, json={"results": {"urn:li:share:123": {"entity": "urn:li:share:123"}}})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202312",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    payload = client.batch_get_social_metadata(["urn:li:share:123"])

    request = route.calls[0].request
    assert request.headers.get("X-RestLi-Method") == "BATCH_GET"
    assert request.headers.get("Linkedin-Version") == "202602"
    assert request.url.params["ids"] == "List(urn:li:share:123)"
    assert payload["results"]["urn:li:share:123"]["entity"] == "urn:li:share:123"


@respx.mock
def test_get_member_post_analytics_uses_entity_finder() -> None:
    route = respx.get("https://api.linkedin.com/rest/memberCreatorPostAnalytics").mock(
        return_value=httpx.Response(200, json={"elements": [{"totalValue": {"long": 42}}]})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202312",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    payload = client.get_member_post_analytics("urn:li:share:123", query_type="REACTION")

    request = route.calls[0].request
    assert request.headers.get("X-RestLi-Method") == "FINDER"
    assert request.headers.get("Linkedin-Version") == "202602"
    assert request.url.params["q"] == "entity"
    assert request.url.params["entity"] == "(share:urn%3Ali%3Ashare%3A123)"
    assert request.url.params["queryType"] == "REACTION"
    assert request.url.params["aggregation"] == "TOTAL"
    assert payload["elements"][0]["totalValue"]["long"] == 42
