from __future__ import annotations

from typing import Any

from ..config import LinkedInAdsSettings
from ..linkedin_client import LinkedInClient
from .common import (
    build_collection_response,
    build_entity_response,
    compact_params,
    normalize_account_id,
    normalize_page_size,
    normalize_sort_order,
    resolve_fields,
)

DEFAULT_ACCOUNT_FIELDS = ["id", "name", "status", "type", "currency", "test", "servingStatuses"]
ALLOWED_ACCOUNT_FIELDS = {
    "id",
    "name",
    "status",
    "type",
    "currency",
    "test",
    "servingStatuses",
    "reference",
    "referenceInfo",
    "changeAuditStamps",
    "version",
    "notifiedOnCampaignOptimization",
    "notifiedOnCreativeApproval",
    "notifiedOnCreativeRejection",
    "notifiedOnEndOfCampaign",
}


def list_ad_accounts(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_ACCOUNT_FIELDS,
        allowed_fields=ALLOWED_ACCOUNT_FIELDS,
    )
    payload = client.get_json(
        "adAccounts",
        params=compact_params(
            {
                "q": "search",
                "search": arguments.get("search"),
                "search.test": _normalize_optional_bool(arguments.get("test"), "test"),
                "pageSize": normalize_page_size(arguments.get("page_size")),
                "pageToken": arguments.get("page_token"),
                "sortOrder": normalize_sort_order(arguments.get("sort_order")),
            }
        ),
    )
    return build_collection_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=fields_csv,
    )


def get_ad_account(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = normalize_account_id(arguments["id"])
    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_ACCOUNT_FIELDS,
        allowed_fields=ALLOWED_ACCOUNT_FIELDS,
    )
    payload = client.get_json(f"adAccounts/{account_id}", params={})
    return build_entity_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=fields_csv,
    )


def _normalize_optional_bool(value: Any, parameter_name: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError(f"{parameter_name} must be a boolean")
