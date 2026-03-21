from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from ..errors import AccountSelectionRequired
from ..response import ok_response

if TYPE_CHECKING:
    from ..linkedin_client import LinkedInClient

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
MAX_FIELDS = 50

ACCOUNT_ID_PATTERN = re.compile(r"^(?:urn:li:sponsoredAccount:)?([0-9]+)$")
CAMPAIGN_GROUP_ID_PATTERN = re.compile(r"^(?:urn:li:sponsoredCampaignGroup:)?([0-9]+)$")
CAMPAIGN_ID_PATTERN = re.compile(r"^(?:urn:li:sponsoredCampaign:)?([0-9]+)$")
CREATIVE_URN_PATTERN = re.compile(r"^urn:li:sponsoredCreative:[0-9]+$")
CREATIVE_ID_PATTERN = re.compile(r"^(?:urn:li:sponsoredCreative:)?([0-9]+)$")
SHARE_URN_PATTERN = re.compile(r"^urn:li:share:[0-9]+$")
ORGANIZATION_URN_PATTERN = re.compile(r"^urn:li:organization:[0-9]+$")
FIELD_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*$")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

SORT_ORDERS = {"ASCENDING", "DESCENDING"}


def resolve_ad_account_id(*, client: LinkedInClient, ad_account_id: str | None) -> str:
    if ad_account_id:
        return normalize_account_id(ad_account_id)
    return _discover_single_ad_account_id(client)


def normalize_account_id(value: str) -> str:
    match = _match_required(value, ACCOUNT_ID_PATTERN, "ad_account_id")
    return match.group(1)


def normalize_campaign_group_id(value: str, *, parameter_name: str = "id") -> str:
    match = _match_required(value, CAMPAIGN_GROUP_ID_PATTERN, parameter_name)
    return match.group(1)


def normalize_campaign_id(value: str, *, parameter_name: str = "id") -> str:
    match = _match_required(value, CAMPAIGN_ID_PATTERN, parameter_name)
    return match.group(1)


def normalize_creative_urn(value: str, *, parameter_name: str = "id") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{parameter_name} must be a string")
    clean_value = value.strip()
    if CREATIVE_URN_PATTERN.fullmatch(clean_value):
        return clean_value
    match = CREATIVE_ID_PATTERN.fullmatch(clean_value)
    if not match:
        raise ValueError(f"{parameter_name} must be a numeric id or sponsoredCreative URN")
    return f"urn:li:sponsoredCreative:{match.group(1)}"


def normalize_share_urn(value: str, *, parameter_name: str = "id") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{parameter_name} must be a string")
    clean_value = value.strip()
    if not SHARE_URN_PATTERN.fullmatch(clean_value):
        raise ValueError(f"{parameter_name} must be a share URN (urn:li:share:<id>)")
    return clean_value


def normalize_organization_urn(value: str, *, parameter_name: str = "id") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{parameter_name} must be a string")
    clean_value = value.strip()
    if not ORGANIZATION_URN_PATTERN.fullmatch(clean_value):
        raise ValueError(f"{parameter_name} must be an organization URN (urn:li:organization:<id>)")
    return clean_value


def validate_date(value: str, *, parameter_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{parameter_name} must be a string in YYYY-MM-DD format")
    clean_value = value.strip()
    if not DATE_PATTERN.fullmatch(clean_value):
        raise ValueError(f"{parameter_name} must be in YYYY-MM-DD format")
    dt.date.fromisoformat(clean_value)
    return clean_value


def normalize_page_size(value: Any, default: int = DEFAULT_PAGE_SIZE) -> int:
    if value is None:
        return default
    return max(1, min(MAX_PAGE_SIZE, int(value)))


def normalize_sort_order(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("sort_order must be a string")
    clean_value = value.strip().upper()
    if clean_value not in SORT_ORDERS:
        raise ValueError("sort_order must be one of: ASCENDING, DESCENDING")
    return clean_value


def resolve_fields(
    fields: Iterable[str] | None,
    *,
    default_fields: Iterable[str],
    allowed_fields: Iterable[str],
    max_fields: int = MAX_FIELDS,
) -> str:
    selected = list(default_fields) if fields is None else list(fields)
    if not selected:
        raise ValueError("fields must not be empty")
    if len(selected) > max_fields:
        raise ValueError(f"fields must contain at most {max_fields} entries")

    allowed = set(allowed_fields)
    resolved: list[str] = []
    seen: set[str] = set()
    unsupported: set[str] = set()

    for field in selected:
        if not isinstance(field, str):
            raise ValueError("fields must contain only strings")
        clean_field = field.strip()
        if not clean_field:
            raise ValueError("fields must not contain empty values")
        if not FIELD_NAME_PATTERN.fullmatch(clean_field):
            raise ValueError(f"Invalid field name: {clean_field}")
        if clean_field not in allowed:
            unsupported.add(clean_field)
            continue
        if clean_field not in seen:
            seen.add(clean_field)
            resolved.append(clean_field)

    if unsupported:
        rejected = ", ".join(sorted(unsupported))
        raise ValueError(f"Unsupported fields requested: {rejected}")

    if not resolved:
        raise ValueError("fields must include at least one allowed value")

    return ",".join(resolved)


def build_ok_response(
    *,
    data: Any,
    api_version: str,
    request_id: str | None,
    next_after: str | None = None,
    has_next: bool = False,
) -> dict[str, Any]:
    return ok_response(
        data=data,
        next_after=next_after,
        has_next=has_next,
        api_version=api_version,
        request_id=request_id,
    )


def compact_params(params: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


def build_collection_response(
    *,
    payload: Mapping[str, Any],
    api_version: str,
    request_id: str | None,
    fields_csv: str | None = None,
) -> dict[str, Any]:
    elements = payload.get("elements", [])
    data: list[dict[str, Any]] = []
    if isinstance(elements, list):
        data = [dict(item) for item in elements if isinstance(item, Mapping)]

    if fields_csv:
        fields = tuple(field.strip() for field in fields_csv.split(",") if field.strip())
        data = [_filter_entity(item, fields=fields) for item in data]

    metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), Mapping) else {}
    next_page_token = metadata.get("nextPageToken") if isinstance(metadata.get("nextPageToken"), str) else None

    return build_ok_response(
        data=data,
        api_version=api_version,
        request_id=request_id,
        next_after=next_page_token,
        has_next=bool(next_page_token),
    )


def build_entity_response(
    *,
    payload: Mapping[str, Any],
    api_version: str,
    request_id: str | None,
    fields_csv: str | None = None,
) -> dict[str, Any]:
    data = dict(payload)
    if fields_csv:
        fields = tuple(field.strip() for field in fields_csv.split(",") if field.strip())
        data = _filter_entity(data, fields=fields)

    return build_ok_response(
        data=data,
        api_version=api_version,
        request_id=request_id,
    )


def to_account_urn(account_id: str) -> str:
    return f"urn:li:sponsoredAccount:{account_id}"


def to_campaign_group_urn(campaign_group_id: str) -> str:
    return f"urn:li:sponsoredCampaignGroup:{campaign_group_id}"


def to_campaign_urn(campaign_id: str) -> str:
    return f"urn:li:sponsoredCampaign:{campaign_id}"


def to_restli_list(values: Iterable[str]) -> str:
    normalized = [value for value in values if value]
    return f"List({','.join(normalized)})"


def date_range_to_restli(*, date_from: str, date_to: str) -> str:
    start = dt.date.fromisoformat(date_from)
    end = dt.date.fromisoformat(date_to)
    return (
        "(start:(year:{start_year},month:{start_month},day:{start_day}),"
        "end:(year:{end_year},month:{end_month},day:{end_day}))"
    ).format(
        start_year=start.year,
        start_month=start.month,
        start_day=start.day,
        end_year=end.year,
        end_month=end.month,
        end_day=end.day,
    )


def build_insights_selector(pivot: str, entity_ids: list[str]) -> tuple[str, str]:
    normalized_pivot = pivot.strip().lower().replace("-", "_")

    if normalized_pivot == "account":
        urns = [to_account_urn(normalize_account_id(entity_id)) for entity_id in entity_ids]
        return "accounts", to_restli_list(urns)
    if normalized_pivot == "campaign_group":
        urns = [to_campaign_group_urn(normalize_campaign_group_id(entity_id)) for entity_id in entity_ids]
        return "campaignGroups", to_restli_list(urns)
    if normalized_pivot == "campaign":
        urns = [to_campaign_urn(normalize_campaign_id(entity_id)) for entity_id in entity_ids]
        return "campaigns", to_restli_list(urns)
    if normalized_pivot == "creative":
        urns = [normalize_creative_urn(entity_id) for entity_id in entity_ids]
        return "creatives", to_restli_list(urns)
    if normalized_pivot == "share":
        urns = [normalize_share_urn(entity_id) for entity_id in entity_ids]
        return "shares", to_restli_list(urns)
    if normalized_pivot == "company":
        urns = [normalize_organization_urn(entity_id) for entity_id in entity_ids]
        return "companies", to_restli_list(urns)

    raise ValueError(
        "entity_ids is only supported for pivots: account, campaign_group, campaign, creative, share, company"
    )


def _discover_single_ad_account_id(client: LinkedInClient) -> str:
    cached = getattr(client, "_resolved_ad_account_id", None)
    if isinstance(cached, str) and cached:
        return cached

    payload = client.get_json("adAccounts", params={"q": "search", "pageSize": MAX_PAGE_SIZE})
    elements = payload.get("elements", [])

    choices_by_id: dict[str, dict[str, str]] = {}
    if isinstance(elements, list):
        for account in elements:
            if not isinstance(account, Mapping) or account.get("id") is None:
                continue
            try:
                account_id = normalize_account_id(str(account.get("id")))
            except ValueError:
                continue
            name = str(account.get("name") or "")
            urn = to_account_urn(account_id)
            label = f"{name} ({urn})" if name else urn
            choices_by_id[account_id] = {"ad_account_id": urn, "label": label}

    choices = [choices_by_id[key] for key in sorted(choices_by_id)]

    if not choices:
        raise ValueError("No ad accounts accessible for this token")
    if len(choices) > 1:
        raise AccountSelectionRequired(
            choices=choices,
            message="Multiple ad accounts available. Which ad_account_id should I use?",
        )

    resolved_urn = choices[0]["ad_account_id"]
    resolved = normalize_account_id(resolved_urn)
    setattr(client, "_resolved_ad_account_id", resolved)
    return resolved


def _filter_entity(entity: Mapping[str, Any], *, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: entity[field] for field in fields if field in entity}


def _match_required(value: str, pattern: re.Pattern[str], parameter_name: str):
    if not isinstance(value, str):
        raise ValueError(f"{parameter_name} must be a string")
    clean_value = value.strip()
    match = pattern.fullmatch(clean_value)
    if not match:
        raise ValueError(f"{parameter_name} is not in a supported format")
    return match
