from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from flin_linkedin_ads_mcp.config import LinkedInAdsSettings
from flin_linkedin_ads_mcp.errors import LinkedInValidationError
from flin_linkedin_ads_mcp.errors import AccountSelectionRequired
from flin_linkedin_ads_mcp.tools.account_intelligence import list_account_intelligence
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
        if path.startswith("accountIntelligence?"):
            return {
                "elements": [
                    {
                        "companyName": "Microsoft",
                        "paidImpressions": 133,
                        "paidClicks": 20,
                        "paidQualifiedLeads": 5,
                        "conversions": 12,
                    }
                ]
            }
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
    assert "pivot.value=CAMPAIGN" in path
    assert "timeGranularity.value=DAILY" in path
    assert "campaigns=List(urn%3Ali%3AsponsoredCampaign%3A123,urn%3Ali%3AsponsoredCampaign%3A456)" in path
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


def test_get_insights_accepts_extended_reporting_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "fields": ["totalEngagements", "oneClickLeads", "costInUsd"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=totalEngagements,oneClickLeads,costInUsd" in path


def test_get_insights_accepts_yearly_time_granularity(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "time_granularity": "YEARLY", "fields": ["impressions", "clicks"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "timeGranularity.value=YEARLY" in path


def test_get_insights_accepts_member_demographic_pivot(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "member_company_size", "fields": ["impressions", "costInLocalCurrency"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "pivot.value=MEMBER_COMPANY_SIZE" in path


def test_get_insights_accepts_action_clicks_metric(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "fields": ["impressions", "actionClicks"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=impressions,actionClicks" in path


def test_get_insights_accepts_video_and_event_metrics(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "pivot": "campaign",
            "fields": ["videoWatchTime", "averageVideoWatchTime", "eventViews", "eventWatchTime"],
        },
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=videoWatchTime,averageVideoWatchTime,eventViews,eventWatchTime" in path


def test_get_insights_omits_default_account_facet_when_campaigns_are_explicit(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "pivot": "campaign",
            "campaign_ids": ["456070296", "469031486"],
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "time_granularity": "ALL",
        },
    )

    assert result["ok"] is True
    path, _ = client.calls[0]
    assert "campaigns=List(urn%3Ali%3AsponsoredCampaign%3A456070296,urn%3Ali%3AsponsoredCampaign%3A469031486)" in path
    assert "accounts=List(" not in path


def test_get_insights_retries_query_shapes_for_illegal_argument(settings: LinkedInAdsSettings) -> None:
    class QueryShapeFlakyClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path == "adAccounts":
                return {"elements": [{"id": 508834004, "name": "Account"}]}
            if len(self.calls) < 8:
                raise LinkedInValidationError(
                    "Invalid query parameters passed to request",
                    status_code=400,
                    details={
                        "status_code": 400,
                        "error": {"code": "ILLEGAL_ARGUMENT", "message": "Invalid query parameters passed to request"},
                    },
                )
            return {"elements": []}

    client = QueryShapeFlakyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "pivot": "campaign",
            "campaign_ids": ["456070296"],
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "time_granularity": "DAILY",
        },
    )

    assert result["ok"] is True
    called_paths = [path for path, _ in client.calls]
    assert called_paths[0].startswith("adAnalytics?")
    assert "pivot.value=CAMPAIGN" in called_paths[0]
    assert "pivot=CAMPAIGN" in called_paths[1]
    assert "accounts=List(" in called_paths[2]
    assert "dateRange=(start%3A(day%3A1,month%3A1,year%3A2025),end%3A(day%3A31,month%3A12,year%3A2025))" in called_paths[-1]


def test_get_insights_rejects_more_than_20_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])
    fields = [
        "actionClicks",
        "adUnitClicks",
        "approximateMemberReach",
        "averageDwellTime",
        "audiencePenetration",
        "cardClicks",
        "cardImpressions",
        "clicks",
        "commentLikes",
        "comments",
        "companyPageClicks",
        "conversionValueInLocalCurrency",
        "costInLocalCurrency",
        "costInUsd",
        "costPerQualifiedLead",
        "dateRange",
        "documentCompletions",
        "documentFirstQuartileCompletions",
        "documentMidpointCompletions",
        "documentThirdQuartileCompletions",
        "downloadClicks",
    ]

    with pytest.raises(ValueError, match="at most 20"):
        get_insights(
            client=client,
            settings=settings,
            arguments={"pivot": "campaign", "fields": fields},
        )


def test_list_account_intelligence_builds_filter_criteria_query(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = list_account_intelligence(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "lookback_window": "LAST_30_DAYS",
            "ad_segment_ids": ["123", "urn:li:adSegment:456"],
            "campaign_id": "469031486",
            "skip_company_decoration": True,
            "page_size": 500,
            "page_start": 0,
        },
    )

    assert result["ok"] is True
    path, params = client.calls[0]
    assert path.startswith("accountIntelligence?")
    assert "q=account" in path
    assert "account=urn%3Ali%3AsponsoredAccount%3A508834004" in path
    assert "start=0" in path
    assert "count=500" in path
    assert "skipCompanyDecoration=true" in path
    assert (
        "filterCriteria=(lookbackWindow%3ALAST_30_DAYS,adSegments%3AList(urn%3Ali%3AadSegment%3A123,urn%3Ali%3AadSegment%3A456),campaign%3Aurn%3Ali%3AsponsoredCampaign%3A469031486)"
        in path
    )
    assert params == {}


def test_get_creative_rejects_invalid_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="sponsoredCreative"):
        get_creative(client=client, settings=settings, arguments={"id": "../bad"})
