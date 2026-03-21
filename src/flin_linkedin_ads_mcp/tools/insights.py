from __future__ import annotations

import datetime as dt
import re
from typing import Any, Callable, Mapping
from urllib.parse import quote

from ..config import LinkedInAdsSettings
from ..errors import LinkedInValidationError
from ..linkedin_client import LinkedInClient
from .common import (
    build_collection_response,
    build_insights_selector,
    compact_params,
    normalize_account_id,
    normalize_campaign_group_id,
    normalize_campaign_id,
    normalize_creative_urn,
    normalize_organization_urn,
    normalize_share_urn,
    resolve_ad_account_id,
    resolve_fields,
    to_account_urn,
    to_campaign_group_urn,
    to_campaign_urn,
    to_restli_list,
    validate_date,
)

DEFAULT_INSIGHT_FIELDS = [
    "impressions",
    "clicks",
]

ALLOWED_PIVOTS = {
    "company": "COMPANY",
    "share": "SHARE",
    "campaign": "CAMPAIGN",
    "campaign_group": "CAMPAIGN_GROUP",
    "account": "ACCOUNT",
    "creative": "CREATIVE",
    "conversion": "CONVERSION",
    "conversation_node": "CONVERSATION_NODE",
    "conversation_node_option_index": "CONVERSATION_NODE_OPTION_INDEX",
    "serving_location": "SERVING_LOCATION",
    "card_index": "CARD_INDEX",
    "member_company_size": "MEMBER_COMPANY_SIZE",
    "member_industry": "MEMBER_INDUSTRY",
    "member_seniority": "MEMBER_SENIORITY",
    "member_job_title": "MEMBER_JOB_TITLE",
    "member_job_function": "MEMBER_JOB_FUNCTION",
    "member_country_v2": "MEMBER_COUNTRY_V2",
    "member_region_v2": "MEMBER_REGION_V2",
    "member_company": "MEMBER_COMPANY",
    "member_county": "MEMBER_COUNTY",
    "placement_name": "PLACEMENT_NAME",
    "impression_device_type": "IMPRESSION_DEVICE_TYPE",
    "event_stage": "EVENT_STAGE",
}

ALLOWED_TIME_GRANULARITIES = {"DAILY", "MONTHLY", "ALL", "YEARLY"}

ALLOWED_INSIGHT_FIELDS = {
    "actionClicks",
    "adUnitClicks",
    "approximateMemberReach",
    "averageDwellTime",
    "averageEventWatchTime",
    "averageEventWatchTimeOver15Seconds",
    "averageEventWatchTimeOver2Minutes",
    "averageEventWatchTimeOver30Seconds",
    "averageVideoWatchTime",
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
    "costPerEventView",
    "costPerEventViewOver15Seconds",
    "costPerEventViewOver2Minutes",
    "costPerEventViewOver30Seconds",
    "costPerQualifiedLead",
    "dateRange",
    "documentCompletions",
    "documentFirstQuartileCompletions",
    "documentMidpointCompletions",
    "documentThirdQuartileCompletions",
    "downloadClicks",
    "eventViews",
    "eventViewsOver15Seconds",
    "eventViewsOver2Minutes",
    "eventViewsOver30Seconds",
    "eventWatchTime",
    "externalWebsiteConversions",
    "externalWebsitePostClickConversions",
    "externalWebsitePostViewConversions",
    "follows",
    "fullScreenPlays",
    "headlineClicks",
    "headlineImpressions",
    "impressions",
    "jobApplications",
    "jobApplyClicks",
    "landingPageClicks",
    "leadGenerationMailContactInfoShares",
    "leadGenerationMailInterestedClicks",
    "likes",
    "oneClickLeadFormOpens",
    "oneClickLeads",
    "opens",
    "otherEngagements",
    "pivotValues",
    "postClickJobApplications",
    "postClickJobApplyClicks",
    "postClickRegistrations",
    "postViewJobApplications",
    "postViewJobApplyClicks",
    "postViewRegistrations",
    "qualifiedLeads",
    "reactions",
    "registrations",
    "revenueAttributionMetrics",
    "sends",
    "shares",
    "subscriptionClicks",
    "talentLeads",
    "textUrlClicks",
    "totalEngagements",
    "validWorkEmailLeads",
    "videoCompletions",
    "videoFirstQuartileCompletions",
    "videoMidpointCompletions",
    "videoStarts",
    "videoThirdQuartileCompletions",
    "videoViews",
    "videoWatchTime",
    "viralCardClicks",
    "viralCardImpressions",
    "viralClicks",
    "viralCommentLikes",
    "viralComments",
    "viralCompanyPageClicks",
    "viralDocumentCompletions",
    "viralDocumentFirstQuartileCompletions",
    "viralDocumentMidpointCompletions",
    "viralDocumentThirdQuartileCompletions",
    "viralDownloadClicks",
    "viralExternalWebsiteConversions",
    "viralExternalWebsitePostClickConversions",
    "viralExternalWebsitePostViewConversions",
    "viralFollows",
    "viralFullScreenPlays",
    "viralImpressions",
    "viralJobApplications",
    "viralJobApplyClicks",
    "viralLandingPageClicks",
    "viralLikes",
    "viralOneClickLeadFormOpens",
    "viralOneClickLeads",
    "viralOtherEngagements",
    "viralPostClickJobApplications",
    "viralPostClickJobApplyClicks",
    "viralPostClickRegistrations",
    "viralPostViewJobApplications",
    "viralPostViewJobApplyClicks",
    "viralPostViewRegistrations",
    "viralReactions",
    "viralRegistrations",
    "viralShares",
    "viralSubscriptionClicks",
    "viralTotalEngagements",
    "viralVideoCompletions",
    "viralVideoFirstQuartileCompletions",
    "viralVideoMidpointCompletions",
    "viralVideoStarts",
    "viralVideoThirdQuartileCompletions",
    "viralVideoViews",
}

MAX_INSIGHT_FIELDS = 20
FIELD_ALIASES = {
    "pivotValue": "pivotValues",
}
DERIVED_INSIGHT_FIELDS: dict[str, tuple[str, ...]] = {
    "clickThroughRate": ("clicks", "impressions"),
    "costPerClick": ("costInLocalCurrency", "clicks"),
}

ALLOWED_CAMPAIGN_TYPES = {
    "TEXT_AD",
    "SPONSORED_UPDATES",
    "SPONSORED_INMAILS",
    "DYNAMIC",
}

ALLOWED_OBJECTIVE_TYPES = {
    "LEAD_GENERATION",
    "CREATIVE_ENGAGEMENT",
    "WEBSITE_TRAFFIC",
    "VIDEO_VIEW",
    "BRAND_AWARENESS",
    "WEBSITE_CONVERSION",
    "WEBSITE_VISIT",
    "ENGAGEMENT",
    "JOB_APPLICANT",
}

ALLOWED_SORT_FIELDS = {
    "COST_IN_LOCAL_CURRENCY",
    "IMPRESSIONS",
    "CLICKS",
    "ONE_CLICK_LEADS",
    "OPENS",
    "SENDS",
    "EXTERNAL_WEBSITE_CONVERSIONS",
}

ALLOWED_SORT_ORDERS = {"ASCENDING", "DESCENDING"}

DATE_RANGE_YMD_PATTERN = re.compile(
    r"^\(start:\(year:(?P<sy>\d+),month:(?P<sm>\d+),day:(?P<sd>\d+)\)"
    r"(,end:\(year:(?P<ey>\d+),month:(?P<em>\d+),day:(?P<ed>\d+)\))?\)$"
)


def _raw_query(params: dict[str, Any]) -> str:
    filtered = compact_params(params)
    segments = [
        f"{quote(str(key), safe='._')}={quote(_query_value(value), safe=_safe_chars_for_query_value(key, value))}"
        for key, value in filtered.items()
    ]
    return "&".join(segments)


def get_insights(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    normalized_pivot, api_pivot = _normalize_pivot(arguments.get("pivot"))

    requested_fields, output_fields_csv, derived_fields = _prepare_requested_fields(arguments.get("fields"))
    fields_csv = resolve_fields(
        requested_fields,
        default_fields=DEFAULT_INSIGHT_FIELDS,
        allowed_fields=ALLOWED_INSIGHT_FIELDS,
        max_fields=MAX_INSIGHT_FIELDS,
    )

    time_granularity = _normalize_time_granularity(arguments.get("time_granularity"))
    account_selector = _resolve_accounts_selector(client=client, arguments=arguments)
    date_range = _resolve_date_range(arguments)

    params: dict[str, Any] = {
        "q": "analytics",
        "pivot.value": api_pivot,
        "accounts": account_selector,
        "fields": fields_csv,
        "timeGranularity.value": time_granularity,
        "dateRange": date_range,
    }

    _add_optional_filters(params=params, arguments=arguments)
    _apply_entity_ids_compat(params=params, pivot=normalized_pivot, entity_ids=arguments.get("entity_ids"))
    _drop_default_account_selector_if_other_facets_are_present(params=params, arguments=arguments)

    payload: dict[str, Any] | None = None
    query_variants = _analytics_query_variants(params=params, account_selector=account_selector)
    for index, variant in enumerate(query_variants):
        try:
            payload = client.get_json(f"adAnalytics?{_raw_query(variant)}", params=None)
            break
        except LinkedInValidationError as exc:
            if index < len(query_variants) - 1 and _is_query_shape_error(exc):
                continue
            raise

    if payload is None:
        raise RuntimeError("Unable to fetch insights from adAnalytics")

    if derived_fields:
        payload = _inject_derived_metrics(payload=payload, derived_fields=derived_fields)

    return build_collection_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=output_fields_csv,
    )


def _apply_entity_ids_compat(*, params: dict[str, Any], pivot: str, entity_ids: Any) -> None:
    if entity_ids is None:
        return
    if not isinstance(entity_ids, list):
        raise ValueError("entity_ids must be an array")
    if not entity_ids:
        return

    selector_key, selector_value = build_insights_selector(pivot, entity_ids)
    if selector_key not in params:
        params[selector_key] = selector_value


def _drop_default_account_selector_if_other_facets_are_present(*, params: dict[str, Any], arguments: dict[str, Any]) -> None:
    if arguments.get("account_ids") is not None:
        return

    if any(key in params for key in ("campaigns", "campaignGroups", "creatives", "shares", "companies")):
        params.pop("accounts", None)


def _add_optional_filters(*, params: dict[str, Any], arguments: dict[str, Any]) -> None:
    campaigns = _build_optional_selector(
        arguments.get("campaign_ids"),
        parameter_name="campaign_ids",
        normalizer=lambda value: to_campaign_urn(normalize_campaign_id(value, parameter_name="campaign_ids")),
    )
    if campaigns is not None:
        params["campaigns"] = campaigns

    campaign_groups = _build_optional_selector(
        arguments.get("campaign_group_ids"),
        parameter_name="campaign_group_ids",
        normalizer=lambda value: to_campaign_group_urn(normalize_campaign_group_id(value, parameter_name="campaign_group_ids")),
    )
    if campaign_groups is not None:
        params["campaignGroups"] = campaign_groups

    creatives = _build_optional_selector(
        arguments.get("creative_ids"),
        parameter_name="creative_ids",
        normalizer=lambda value: normalize_creative_urn(value, parameter_name="creative_ids"),
    )
    if creatives is not None:
        params["creatives"] = creatives

    shares = _build_optional_selector(
        arguments.get("share_ids"),
        parameter_name="share_ids",
        normalizer=lambda value: normalize_share_urn(value, parameter_name="share_ids"),
    )
    if shares is not None:
        params["shares"] = shares

    companies = _build_optional_selector(
        arguments.get("company_ids"),
        parameter_name="company_ids",
        normalizer=lambda value: normalize_organization_urn(value, parameter_name="company_ids"),
    )
    if companies is not None:
        params["companies"] = companies

    campaign_type = arguments.get("campaign_type")
    if campaign_type is not None:
        params["campaignType.value"] = _normalize_choice(
            campaign_type,
            parameter_name="campaign_type",
            allowed=ALLOWED_CAMPAIGN_TYPES,
        )

    objective_type = arguments.get("objective_type")
    if objective_type is not None:
        params["objectiveType.value"] = _normalize_choice(
            objective_type,
            parameter_name="objective_type",
            allowed=ALLOWED_OBJECTIVE_TYPES,
        )

    sort_by_field = arguments.get("sort_by_field")
    sort_order = arguments.get("sort_order")
    if sort_by_field is None and sort_order is None:
        return
    if sort_by_field is None or sort_order is None:
        raise ValueError("sort_by_field and sort_order must be provided together")

    params["sortBy.field"] = _normalize_choice(
        sort_by_field,
        parameter_name="sort_by_field",
        allowed=ALLOWED_SORT_FIELDS,
    )
    params["sortBy.order"] = _normalize_choice(
        sort_order,
        parameter_name="sort_order",
        allowed=ALLOWED_SORT_ORDERS,
    )


def _resolve_accounts_selector(*, client: LinkedInClient, arguments: dict[str, Any]) -> str:
    account_ids = arguments.get("account_ids")
    if account_ids is not None:
        return _build_selector(
            account_ids,
            parameter_name="account_ids",
            normalizer=lambda value: to_account_urn(normalize_account_id(value)),
        )

    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    return to_restli_list([to_account_urn(account_id)])


def _build_optional_selector(
    values: Any,
    *,
    parameter_name: str,
    normalizer: Callable[[str], str],
) -> str | None:
    if values is None:
        return None
    return _build_selector(values, parameter_name=parameter_name, normalizer=normalizer)


def _build_selector(
    values: Any,
    *,
    parameter_name: str,
    normalizer: Callable[[str], str],
) -> str:
    if not isinstance(values, list):
        raise ValueError(f"{parameter_name} must be an array")
    if not values:
        raise ValueError(f"{parameter_name} must not be empty")
    normalized = [normalizer(value) for value in values]
    return to_restli_list(normalized)


def _resolve_date_range(arguments: dict[str, Any]) -> str:
    date_from = arguments.get("date_from")
    date_to = arguments.get("date_to")

    if date_from is None and date_to is None:
        raise ValueError("date_from is required for get_insights (adAnalytics requires dateRange)")
    if date_from is None:
        raise ValueError("date_from must be provided when date_to is set")

    start_date = dt.date.fromisoformat(validate_date(date_from, parameter_name="date_from"))
    if date_to is None:
        return "(start:(year:{year},month:{month},day:{day}))".format(
            year=start_date.year,
            month=start_date.month,
            day=start_date.day,
        )

    end_date = dt.date.fromisoformat(validate_date(date_to, parameter_name="date_to"))
    return (
        "(start:(year:{start_year},month:{start_month},day:{start_day}),"
        "end:(year:{end_year},month:{end_month},day:{end_day}))"
    ).format(
        start_year=start_date.year,
        start_month=start_date.month,
        start_day=start_date.day,
        end_year=end_date.year,
        end_month=end_date.month,
        end_day=end_date.day,
    )


def _analytics_query_variants(*, params: dict[str, Any], account_selector: str) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []

    def _append(candidate: dict[str, Any]) -> None:
        if any(existing == candidate for existing in variants):
            return
        variants.append(candidate)

    base = dict(params)
    _append(base)
    _append(_to_legacy_param_names(base))

    has_non_account_facet = any(key in base for key in ("campaigns", "campaignGroups", "creatives", "shares", "companies"))
    allow_accounts_fallback = "accounts" not in base and has_non_account_facet
    if allow_accounts_fallback:
        with_accounts = dict(base)
        with_accounts["accounts"] = account_selector
        _append(with_accounts)
        _append(_to_legacy_param_names(with_accounts))

    alternate_date_range = _to_day_month_year_date_range(base.get("dateRange"))
    if alternate_date_range is not None:
        base_alt_date = dict(base)
        base_alt_date["dateRange"] = alternate_date_range
        _append(base_alt_date)
        _append(_to_legacy_param_names(base_alt_date))

        if allow_accounts_fallback:
            base_alt_date_with_accounts = dict(base_alt_date)
            base_alt_date_with_accounts["accounts"] = account_selector
            _append(base_alt_date_with_accounts)
            _append(_to_legacy_param_names(base_alt_date_with_accounts))

    if "sortBy.field" in base or "sortBy.order" in base:
        base_without_sort = _without_sort(base)
        _append(base_without_sort)
        _append(_to_legacy_param_names(base_without_sort))

        if allow_accounts_fallback:
            base_without_sort_with_accounts = dict(base_without_sort)
            base_without_sort_with_accounts["accounts"] = account_selector
            _append(base_without_sort_with_accounts)
            _append(_to_legacy_param_names(base_without_sort_with_accounts))

        if alternate_date_range is not None:
            base_without_sort_alt_date = dict(base_without_sort)
            base_without_sort_alt_date["dateRange"] = alternate_date_range
            _append(base_without_sort_alt_date)
            _append(_to_legacy_param_names(base_without_sort_alt_date))

            if allow_accounts_fallback:
                base_without_sort_alt_date_with_accounts = dict(base_without_sort_alt_date)
                base_without_sort_alt_date_with_accounts["accounts"] = account_selector
                _append(base_without_sort_alt_date_with_accounts)
                _append(_to_legacy_param_names(base_without_sort_alt_date_with_accounts))

    return variants


def _without_sort(params: dict[str, Any]) -> dict[str, Any]:
    reduced = dict(params)
    reduced.pop("sortBy.field", None)
    reduced.pop("sortBy.order", None)
    return reduced


def _to_legacy_param_names(params: dict[str, Any]) -> dict[str, Any]:
    legacy = dict(params)
    for key_with_value_suffix, legacy_key in (
        ("pivot.value", "pivot"),
        ("timeGranularity.value", "timeGranularity"),
        ("campaignType.value", "campaignType"),
        ("objectiveType.value", "objectiveType"),
    ):
        if key_with_value_suffix in legacy:
            legacy[legacy_key] = legacy.pop(key_with_value_suffix)
    return legacy


def _to_day_month_year_date_range(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    match = DATE_RANGE_YMD_PATTERN.fullmatch(value)
    if not match:
        return None

    groups = match.groupdict()
    start = "start:(day:{day},month:{month},year:{year})".format(
        day=groups["sd"],
        month=groups["sm"],
        year=groups["sy"],
    )

    if groups["ey"] is None or groups["em"] is None or groups["ed"] is None:
        return f"({start})"

    end = "end:(day:{day},month:{month},year:{year})".format(
        day=groups["ed"],
        month=groups["em"],
        year=groups["ey"],
    )
    return f"({start},{end})"


def _normalize_pivot(value: Any) -> tuple[str, str]:
    if value is None:
        return "campaign", ALLOWED_PIVOTS["campaign"]
    if not isinstance(value, str):
        raise ValueError("pivot must be a string")

    normalized = value.strip().replace("-", "_").lower()
    if normalized not in ALLOWED_PIVOTS:
        supported = ", ".join(sorted(ALLOWED_PIVOTS))
        raise ValueError(f"pivot must be one of: {supported}")

    return normalized, ALLOWED_PIVOTS[normalized]


def _normalize_time_granularity(value: Any) -> str:
    if value is None:
        return "DAILY"
    if not isinstance(value, str):
        raise ValueError("time_granularity must be a string")
    clean_value = value.strip().upper()
    if clean_value not in ALLOWED_TIME_GRANULARITIES:
        raise ValueError("time_granularity must be one of: DAILY, MONTHLY, ALL, YEARLY")
    return clean_value


def _normalize_choice(value: Any, *, parameter_name: str, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{parameter_name} must be a string")
    clean_value = value.strip().upper()
    if clean_value not in allowed:
        raise ValueError(f"{parameter_name} must be one of: {', '.join(sorted(allowed))}")
    return clean_value


def _normalize_requested_fields(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    normalized: list[Any] = []
    for item in value:
        if isinstance(item, str):
            normalized.append(FIELD_ALIASES.get(item, item))
            continue
        normalized.append(item)
    return normalized


def _prepare_requested_fields(value: Any) -> tuple[Any, str | None, set[str]]:
    normalized = _normalize_requested_fields(value)
    if not isinstance(normalized, list):
        return normalized, None, set()

    api_fields: list[Any] = []
    output_fields: list[str] = []
    derived_fields: set[str] = set()
    seen_api_fields: set[str] = set()
    seen_output_fields: set[str] = set()

    for item in normalized:
        if not isinstance(item, str):
            api_fields.append(item)
            continue

        if item not in seen_output_fields:
            seen_output_fields.add(item)
            output_fields.append(item)

        dependencies = DERIVED_INSIGHT_FIELDS.get(item)
        if dependencies is None:
            if item not in seen_api_fields:
                seen_api_fields.add(item)
                api_fields.append(item)
            continue

        derived_fields.add(item)
        for dependency in dependencies:
            if dependency in seen_api_fields:
                continue
            seen_api_fields.add(dependency)
            api_fields.append(dependency)

    output_fields_csv = ",".join(output_fields) if output_fields else None
    return api_fields, output_fields_csv, derived_fields


def _inject_derived_metrics(*, payload: dict[str, Any], derived_fields: set[str]) -> dict[str, Any]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        return payload

    normalized_elements: list[Any] = []
    for item in elements:
        if not isinstance(item, Mapping):
            normalized_elements.append(item)
            continue

        row = dict(item)

        if "clickThroughRate" in derived_fields:
            row["clickThroughRate"] = _safe_ratio(
                numerator=_to_float(row.get("clicks")),
                denominator=_to_float(row.get("impressions")),
            )

        if "costPerClick" in derived_fields:
            row["costPerClick"] = _safe_ratio(
                numerator=_to_float(row.get("costInLocalCurrency")),
                denominator=_to_float(row.get("clicks")),
            )

        normalized_elements.append(row)

    payload["elements"] = normalized_elements
    return payload


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    clean_value = value.strip()
    if not clean_value:
        return None

    try:
        return float(clean_value)
    except ValueError:
        return None


def _safe_ratio(*, numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator <= 0:
        return None
    return numerator / denominator


def _is_query_shape_error(error: LinkedInValidationError) -> bool:
    message = str(error.message or "").lower()
    if "no virtual resource found" in message:
        return True
    if "invalid query parameters" in message:
        return True
    if "illegal_argument" in message:
        return True
    if "query_param_not_allowed" in message:
        return True

    details_error = error.details.get("error", {})
    if isinstance(details_error, dict):
        code = str(details_error.get("code") or "").upper()
        if code in {"RESOURCE_NOT_FOUND", "ILLEGAL_ARGUMENT", "QUERY_PARAM_NOT_ALLOWED"}:
            return True

        raw_error_details = details_error.get("errorDetails")
        if isinstance(raw_error_details, dict):
            input_errors = raw_error_details.get("inputErrors")
            if isinstance(input_errors, list):
                for item in input_errors:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("code") or "").upper() == "QUERY_PARAM_NOT_ALLOWED":
                        return True

    return False


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _safe_chars_for_query_value(key: str, value: Any) -> str:
    if key == "dateRange":
        return ",():"
    return ",()"
