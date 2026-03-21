from __future__ import annotations

from typing import Any

from ..config import LinkedInAdsSettings
from ..linkedin_client import LinkedInClient
from .common import (
    build_collection_response,
    build_entity_response,
    compact_params,
    normalize_campaign_id,
    normalize_creative_urn,
    normalize_page_size,
    normalize_sort_order,
    resolve_ad_account_id,
    resolve_fields,
    to_campaign_urn,
    to_restli_list,
)

DEFAULT_CREATIVE_FIELDS = ["id", "name", "intendedStatus", "campaign", "account", "isServing"]
ALLOWED_CREATIVE_FIELDS = {
    "id",
    "name",
    "intendedStatus",
    "campaign",
    "account",
    "isServing",
    "isTest",
    "content",
    "review",
    "servingHoldReasons",
    "createdAt",
    "createdBy",
    "lastModifiedAt",
    "lastModifiedBy",
    "leadgenCallToAction",
}


def list_creatives(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_CREATIVE_FIELDS,
        allowed_fields=ALLOWED_CREATIVE_FIELDS,
    )

    creative_ids = arguments.get("creative_ids")
    if creative_ids is not None and not isinstance(creative_ids, list):
        raise ValueError("creative_ids must be an array")

    campaign_id = arguments.get("campaign_id")
    campaign_selector = None
    if campaign_id is not None:
        campaign_selector = to_restli_list([to_campaign_urn(normalize_campaign_id(campaign_id, parameter_name="campaign_id"))])

    creative_selector = None
    if isinstance(creative_ids, list) and creative_ids:
        creative_selector = to_restli_list(
            [normalize_creative_urn(creative_id, parameter_name="creative_ids[]") for creative_id in creative_ids]
        )

    payload = client.get_json(
        f"adAccounts/{account_id}/creatives",
        params=compact_params(
            {
                "q": "criteria",
                "campaigns": campaign_selector,
                "creatives": creative_selector,
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


def get_creative(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    creative_urn = normalize_creative_urn(arguments["id"], parameter_name="id")
    fields_csv = resolve_fields(
        arguments.get("fields"),
        default_fields=DEFAULT_CREATIVE_FIELDS,
        allowed_fields=ALLOWED_CREATIVE_FIELDS,
    )

    payload = client.get_json(
        f"adAccounts/{account_id}/creatives",
        params={
            "q": "criteria",
            "creatives": to_restli_list([creative_urn]),
            "pageSize": 1,
        },
    )
    elements = payload.get("elements", [])
    entity = elements[0] if isinstance(elements, list) and elements else {}

    return build_entity_response(
        payload=entity if isinstance(entity, dict) else {},
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=fields_csv,
    )
