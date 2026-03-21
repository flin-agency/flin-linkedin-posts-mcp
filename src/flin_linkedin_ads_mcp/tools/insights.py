from __future__ import annotations

from typing import Any

from ..config import LinkedInAdsSettings
from ..linkedin_client import LinkedInClient
from .common import (
    build_collection_response,
    build_insights_selector,
    compact_params,
    date_range_to_restli,
    resolve_ad_account_id,
    resolve_fields,
    to_account_urn,
    to_restli_list,
    validate_date,
)

DEFAULT_INSIGHT_FIELDS = [
    "costInLocalCurrency",
    "impressions",
    "clicks",
    "dateRange",
    "pivotValues",
]

ALLOWED_PIVOTS = {
    "account": "ACCOUNT",
    "campaign_group": "CAMPAIGN_GROUP",
    "campaign": "CAMPAIGN",
    "creative": "CREATIVE",
}

ALLOWED_TIME_GRANULARITIES = {"DAILY", "MONTHLY", "ALL"}

ALLOWED_INSIGHT_FIELDS = {
    "costInLocalCurrency",
    "clicks",
    "dateRange",
    "externalWebsiteConversions",
    "impressions",
    "landingPageClicks",
    "likes",
    "pivotValues",
    "shares",
}


def _raw_query(params: dict[str, Any]) -> str:
    filtered = compact_params(params)
    segments = [f"{key}={value}" for key, value in filtered.items()]
    return "&".join(segments)


def get_insights(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    pivot = _normalize_pivot(arguments.get("pivot"))
    api_pivot = ALLOWED_PIVOTS[pivot]
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))

    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_INSIGHT_FIELDS,
        allowed_fields=ALLOWED_INSIGHT_FIELDS,
    )

    time_granularity = _normalize_time_granularity(arguments.get("time_granularity"))

    date_from = arguments.get("date_from")
    date_to = arguments.get("date_to")
    date_range = None
    if date_from is not None or date_to is not None:
        if date_from is None or date_to is None:
            raise ValueError("date_from and date_to must be provided together")
        date_range = date_range_to_restli(
            date_from=validate_date(date_from, parameter_name="date_from"),
            date_to=validate_date(date_to, parameter_name="date_to"),
        )

    params: dict[str, Any] = {
        "q": "analytics",
        "pivot": api_pivot,
        "accounts": to_restli_list([to_account_urn(account_id)]),
        "fields": fields_csv,
        "timeGranularity": time_granularity,
        "dateRange": date_range,
    }

    entity_ids = arguments.get("entity_ids")
    if entity_ids is not None:
        if not isinstance(entity_ids, list):
            raise ValueError("entity_ids must be an array")
        if entity_ids:
            selector_key, selector_value = build_insights_selector(pivot, entity_ids)
            params[selector_key] = selector_value

    payload = client.get_json(f"adAnalytics?{_raw_query(params)}", params={})
    return build_collection_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def _normalize_pivot(value: Any) -> str:
    if value is None:
        return "campaign"
    if not isinstance(value, str):
        raise ValueError("pivot must be a string")
    clean_value = value.strip().lower()
    if clean_value not in ALLOWED_PIVOTS:
        raise ValueError("pivot must be one of: account, campaign_group, campaign, creative")
    return clean_value


def _normalize_time_granularity(value: Any) -> str:
    if value is None:
        return "DAILY"
    if not isinstance(value, str):
        raise ValueError("time_granularity must be a string")
    clean_value = value.strip().upper()
    if clean_value not in ALLOWED_TIME_GRANULARITIES:
        raise ValueError("time_granularity must be one of: DAILY, MONTHLY, ALL")
    return clean_value
