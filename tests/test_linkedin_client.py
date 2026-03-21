from __future__ import annotations

import httpx
import pytest
import respx

from flin_linkedin_ads_mcp.errors import LinkedInPermissionError, LinkedInRateLimitError
from flin_linkedin_ads_mcp.linkedin_client import LinkedInClient


@respx.mock
def test_get_json_retries_after_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    route = respx.get("https://api.linkedin.com/rest/adAccounts")
    route.side_effect = [
        httpx.Response(429, json={"message": "rate limit"}),
        httpx.Response(200, json={"elements": [{"id": 1}]}, headers={"x-li-request-id": "req-1"}),
    ]

    sleeps: list[float] = []
    monkeypatch.setattr("flin_linkedin_ads_mcp.linkedin_client.time.sleep", lambda seconds: sleeps.append(seconds))

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=2,
    )
    payload = client.get_json("adAccounts", params={"q": "search"})

    assert payload["elements"] == [{"id": 1}]
    assert sleeps == [0.5]


@respx.mock
def test_get_json_uses_required_linkedin_headers() -> None:
    route = respx.get("https://api.linkedin.com/rest/adAccounts").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    client.get_json("adAccounts", params={"q": "search", "pageSize": 10})

    assert len(route.calls) == 1
    request = route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer token"
    assert request.headers.get("Linkedin-Version") == "202602"
    assert request.headers.get("X-Restli-Protocol-Version") == "2.0.0"


@respx.mock
def test_get_json_sets_finder_method_header_for_finder_queries() -> None:
    route = respx.get("https://api.linkedin.com/rest/adAccounts").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    client.get_json("adAccounts?q=search&pageSize=10", params={})

    assert len(route.calls) == 1
    request = route.calls[0].request
    assert request.headers.get("X-RestLi-Method") == "FINDER"


@respx.mock
def test_get_json_preserves_query_from_path_when_params_are_empty_dict() -> None:
    route = respx.get("https://api.linkedin.com/rest/adAnalytics").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )

    client.get_json(
        "adAnalytics?q=analytics&pivot=CAMPAIGN&fields=impressions,clicks,costInLocalCurrency",
        params={},
    )

    assert len(route.calls) == 1
    request = route.calls[0].request
    assert request.url.params.get("q") == "analytics"
    assert request.url.params.get("pivot") == "CAMPAIGN"
    assert request.url.params.get("fields") == "impressions,clicks,costInLocalCurrency"


@respx.mock
def test_get_json_maps_permission_error() -> None:
    respx.get("https://api.linkedin.com/rest/adAccounts").mock(
        return_value=httpx.Response(403, json={"message": "Permission denied"})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )

    with pytest.raises(LinkedInPermissionError):
        client.get_json("adAccounts", params={"q": "search"})


@respx.mock
def test_get_json_raises_rate_limit_error_after_retries() -> None:
    respx.get("https://api.linkedin.com/rest/adAccounts").mock(
        return_value=httpx.Response(429, json={"message": "rate limit"})
    )

    client = LinkedInClient(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )

    with pytest.raises(LinkedInRateLimitError):
        client.get_json("adAccounts", params={"q": "search"})
