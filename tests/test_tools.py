from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from flin_linkedin_ads_mcp.config import LinkedInAdsSettings
from flin_linkedin_ads_mcp.errors import AccountSelectionRequired
from flin_linkedin_ads_mcp.tools.campaigns import get_campaign, list_campaigns
from flin_linkedin_ads_mcp.tools.creatives import get_creative
from flin_linkedin_ads_mcp.tools.insights import get_insights


@dataclass
class DummyClient:
    calls: list[tuple[str, dict]]
    ad_accounts: list[str] = field(default_factory=lambda: ["111"])
    last_request_id: str | None = None

    def get_json(self, path: str, params: dict | None) -> dict:
        self.calls.append((path, dict(params or {})))
        if path == "adAccounts":
            return {
                "elements": [
                    {
                        "id": int(account_id.split(":")[-1]),
                        "name": f"Account {account_id}",
                    }
                    for account_id in self.ad_accounts
                ]
            }
        if path.endswith("/creatives"):
            return {"elements": [{"id": "urn:li:sponsoredCreative:999", "name": "Creative"}]}
        return {"elements": []}


@pytest.fixture
def settings() -> LinkedInAdsSettings:
    return LinkedInAdsSettings(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )


def test_list_campaigns_prefers_per_call_ad_account_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = list_campaigns(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "urn:li:sponsoredAccount:222", "page_size": 10},
    )

    assert result["ok"] is True
    assert client.calls == [("adAccounts/222/adCampaigns", {"q": "search", "pageSize": 10})]


def test_list_campaigns_auto_resolves_single_account_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = list_campaigns(client=client, settings=settings, arguments={})

    assert result["ok"] is True
    assert client.calls[0] == ("adAccounts", {"q": "search", "pageSize": 1000})
    assert client.calls[1] == ("adAccounts/111/adCampaigns", {"q": "search", "pageSize": 100})


def test_get_insights_passes_entity_filters(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "entity_ids": ["123", "urn:li:sponsoredCampaign:456"]},
    )

    assert result["ok"] is True
    path, params = client.calls[1]
    assert path.startswith("adAnalytics?")
    assert "q=analytics" in path
    assert "pivot=CAMPAIGN" in path
    assert "campaigns=List(urn:li:sponsoredCampaign:123,urn:li:sponsoredCampaign:456)" in path
    assert "fields=account_id,campaign_id,adset_id,ad_id,impressions,clicks,spend,reach,frequency,cpc,ctr" not in path
    assert "%2C" not in path
    assert params == {}


def test_list_campaigns_requires_ad_account_id_when_multiple_accounts_exist(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[], ad_accounts=["111", "222"])

    with pytest.raises(AccountSelectionRequired) as exc_info:
        list_campaigns(client=client, settings=settings, arguments={})

    assert [choice["ad_account_id"] for choice in exc_info.value.choices] == [
        "urn:li:sponsoredAccount:111",
        "urn:li:sponsoredAccount:222",
    ]


def test_get_campaign_rejects_invalid_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="supported format"):
        get_campaign(client=client, settings=settings, arguments={"id": "act_111/campaigns"})


def test_list_campaigns_rejects_invalid_ad_account_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="supported format"):
        list_campaigns(client=client, settings=settings, arguments={"ad_account_id": "foo"})


def test_list_campaigns_rejects_unknown_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="Unsupported fields"):
        list_campaigns(
            client=client,
            settings=settings,
            arguments={"ad_account_id": "urn:li:sponsoredAccount:222", "fields": ["id", "not_a_real_field"]},
        )


def test_get_insights_rejects_unknown_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="Unsupported fields"):
        get_insights(
            client=client,
            settings=settings,
            arguments={"pivot": "campaign", "fields": ["impressions", "not_a_real_metric"]},
        )


def test_get_insights_accepts_landing_page_clicks_field(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "pivot": "campaign",
            "fields": ["impressions", "landingPageClicks", "costInLocalCurrency"],
        },
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=impressions,landingPageClicks,costInLocalCurrency" in path


def test_get_insights_rejects_unsupported_cost_in_usd_field(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="Unsupported fields"):
        get_insights(
            client=client,
            settings=settings,
            arguments={"pivot": "campaign", "fields": ["impressions", "costInUsd"]},
        )


def test_get_creative_rejects_invalid_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="sponsoredCreative"):
        get_creative(client=client, settings=settings, arguments={"id": "../bad"})
