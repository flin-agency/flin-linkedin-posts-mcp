from __future__ import annotations

from typing import Any

from ..config import LinkedInAdsSettings
from ..linkedin_client import LinkedInClient
from .common import (
    build_collection_response,
    build_entity_response,
    compact_params,
    normalize_campaign_id,
    normalize_page_size,
    normalize_sort_order,
    resolve_ad_account_id,
    resolve_fields,
)

DEFAULT_CAMPAIGN_FIELDS = ["id", "name", "status", "type", "account", "campaignGroup", "test"]
ALLOWED_CAMPAIGN_FIELDS = {
    "id",
    "name",
    "status",
    "type",
    "account",
    "campaignGroup",
    "test",
    "runSchedule",
    "targeting",
    "servingStatuses",
    "changeAuditStamps",
    "version",
    "dailyBudget",
    "totalBudget",
    "unitCost",
    "costType",
    "optimizationTargetType",
    "format",
    "objectiveType",
    "creativeSelection",
    "associatedEntity",
    "locale",
}


def list_campaigns(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_CAMPAIGN_FIELDS,
        allowed_fields=ALLOWED_CAMPAIGN_FIELDS,
    )
    payload = client.get_json(
        f"adAccounts/{account_id}/adCampaigns",
        params=compact_params(
            {
                "q": "search",
                "search": arguments.get("search"),
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


def get_campaign(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    campaign_id = normalize_campaign_id(arguments["id"], parameter_name="id")
    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_CAMPAIGN_FIELDS,
        allowed_fields=ALLOWED_CAMPAIGN_FIELDS,
    )
    payload = client.get_json(f"adAccounts/{account_id}/adCampaigns/{campaign_id}", params={})
    return build_entity_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=fields_csv,
    )
