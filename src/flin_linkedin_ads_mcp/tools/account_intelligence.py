from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from ..config import LinkedInAdsSettings
from ..linkedin_client import LinkedInClient
from .common import (
    build_collection_response,
    compact_params,
    normalize_campaign_id,
    normalize_page_size,
    resolve_ad_account_id,
    resolve_fields,
    to_account_urn,
    to_campaign_urn,
    to_restli_list,
)

DEFAULT_LOOKBACK_WINDOW = "LAST_90_DAYS"
ALLOWED_LOOKBACK_WINDOWS = {"LAST_7_DAYS", "LAST_30_DAYS", "LAST_60_DAYS", "LAST_90_DAYS"}
AD_SEGMENT_PATTERN = re.compile(r"^(?:urn:li:adSegment:)?([0-9]+)$")

DEFAULT_ACCOUNT_INTELLIGENCE_FIELDS = [
    "companyName",
    "engagementLevel",
    "paidImpressions",
    "paidClicks",
    "paidEngagements",
    "paidLeads",
    "paidQualifiedLeads",
    "conversions",
    "organicImpressions",
    "organicEngagements",
]

ALLOWED_ACCOUNT_INTELLIGENCE_FIELDS = {
    "companyName",
    "companyPageUrl",
    "companyWebsite",
    "engagementLevel",
    "organicImpressions",
    "organicEngagements",
    "paidImpressions",
    "paidClicks",
    "paidEngagements",
    "paidLeads",
    "paidQualifiedLeads",
    "conversions",
}


def list_account_intelligence(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_ACCOUNT_INTELLIGENCE_FIELDS,
        allowed_fields=ALLOWED_ACCOUNT_INTELLIGENCE_FIELDS,
    )

    lookback_window = _normalize_lookback_window(arguments.get("lookback_window"))
    filter_criteria = _build_filter_criteria(
        lookback_window=lookback_window,
        ad_segment_ids=arguments.get("ad_segment_ids"),
        campaign_id=arguments.get("campaign_id"),
    )

    skip_company_decoration = arguments.get("skip_company_decoration")
    if skip_company_decoration is not None and not isinstance(skip_company_decoration, bool):
        raise ValueError("skip_company_decoration must be a boolean")

    page_start = arguments.get("page_start")
    if page_start is None:
        start = 0
    else:
        start = int(page_start)
        if start < 0:
            raise ValueError("page_start must be greater than or equal to 0")

    params = compact_params(
        {
            "q": "account",
            "account": to_account_urn(account_id),
            "filterCriteria": filter_criteria,
            "start": start,
            "count": normalize_page_size(arguments.get("page_size"), default=100),
            "skipCompanyDecoration": skip_company_decoration,
        }
    )

    payload = client.get_json(f"accountIntelligence?{_raw_query(params)}", params={})
    return build_collection_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=fields_csv,
    )


def _build_filter_criteria(*, lookback_window: str, ad_segment_ids: Any, campaign_id: Any) -> str:
    parts = [f"lookbackWindow:{lookback_window}"]

    if ad_segment_ids is not None:
        if not isinstance(ad_segment_ids, list):
            raise ValueError("ad_segment_ids must be an array")
        if not ad_segment_ids:
            raise ValueError("ad_segment_ids must not be empty")
        segment_urns = [_normalize_ad_segment_urn(value, parameter_name="ad_segment_ids") for value in ad_segment_ids]
        parts.append(f"adSegments:{to_restli_list(segment_urns)}")

    if campaign_id is not None:
        parts.append(f"campaign:{to_campaign_urn(normalize_campaign_id(campaign_id, parameter_name='campaign_id'))}")

    return f"({','.join(parts)})"


def _normalize_lookback_window(value: Any) -> str:
    if value is None:
        return DEFAULT_LOOKBACK_WINDOW
    if not isinstance(value, str):
        raise ValueError("lookback_window must be a string")

    clean_value = value.strip().upper()
    if clean_value not in ALLOWED_LOOKBACK_WINDOWS:
        allowed = ", ".join(sorted(ALLOWED_LOOKBACK_WINDOWS))
        raise ValueError(f"lookback_window must be one of: {allowed}")
    return clean_value


def _normalize_ad_segment_urn(value: Any, *, parameter_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{parameter_name} must contain strings")
    clean_value = value.strip()
    match = AD_SEGMENT_PATTERN.fullmatch(clean_value)
    if not match:
        raise ValueError(f"{parameter_name} must contain ad segment ids or ad segment URNs")
    return f"urn:li:adSegment:{match.group(1)}"


def _raw_query(params: dict[str, Any]) -> str:
    segments = [f"{quote(str(key), safe='._')}={quote(_query_value(value), safe=',()')}" for key, value in params.items()]
    return "&".join(segments)


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
