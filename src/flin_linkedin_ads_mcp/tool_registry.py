from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ACCOUNT_ID_PATTERN = "^(urn:li:sponsoredAccount:)?[0-9]+$"
CAMPAIGN_GROUP_PATTERN = "^(urn:li:sponsoredCampaignGroup:)?[0-9]+$"
CAMPAIGN_PATTERN = "^(urn:li:sponsoredCampaign:)?[0-9]+$"
CREATIVE_PATTERN = "^(urn:li:sponsoredCreative:)?[0-9]+$"
FIELD_PATTERN = "^[A-Za-z][A-Za-z0-9_.]*$"
DATE_PATTERN = "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="list_ad_accounts",
            description="List LinkedIn ad accounts accessible by the token",
            input_schema=_list_schema(),
        ),
        ToolSpec(
            name="get_ad_account",
            description="Fetch one LinkedIn ad account by id",
            input_schema=_account_id_schema(),
        ),
        ToolSpec(
            name="list_campaign_groups",
            description="List campaign groups for an ad account",
            input_schema=_account_list_schema(),
        ),
        ToolSpec(
            name="get_campaign_group",
            description="Fetch one campaign group by id",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "id": {"type": "string", "pattern": CAMPAIGN_GROUP_PATTERN},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="list_campaigns",
            description="List campaigns for an ad account",
            input_schema=_account_list_schema(),
        ),
        ToolSpec(
            name="get_campaign",
            description="Fetch one campaign by id",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "id": {"type": "string", "pattern": CAMPAIGN_PATTERN},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="list_creatives",
            description="List creatives for an ad account",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "campaign_id": {"type": "string", "pattern": CAMPAIGN_PATTERN},
                    "creative_ids": {
                        "type": "array",
                        "items": {"type": "string", "pattern": CREATIVE_PATTERN},
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "page_token": {"type": "string"},
                    "sort_order": {"type": "string", "enum": ["ASCENDING", "DESCENDING"]},
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_creative",
            description="Fetch one creative by id",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "id": {"type": "string", "pattern": CREATIVE_PATTERN},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_insights",
            description="Fetch LinkedIn ads analytics",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "pivot": {
                        "type": "string",
                        "enum": ["account", "campaign_group", "campaign", "creative"],
                        "default": "campaign",
                    },
                    "entity_ids": {"type": "array", "items": {"type": "string"}},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                    "time_granularity": {"type": "string", "default": "DAILY"},
                    "date_from": {"type": "string", "pattern": DATE_PATTERN},
                    "date_to": {"type": "string", "pattern": DATE_PATTERN},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "page_token": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
    ]


def _list_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {"type": "string", "pattern": FIELD_PATTERN},
            },
            "search": {"type": "string"},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 1000},
            "page_token": {"type": "string"},
            "sort_order": {"type": "string", "enum": ["ASCENDING", "DESCENDING"]},
            "test": {"type": "boolean"},
        },
        "additionalProperties": False,
    }


def _account_id_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
            "fields": {
                "type": "array",
                "items": {"type": "string", "pattern": FIELD_PATTERN},
            },
        },
        "required": ["id"],
        "additionalProperties": False,
    }


def _account_list_schema() -> dict[str, Any]:
    schema = _list_schema()
    schema["properties"]["ad_account_id"] = {"type": "string", "pattern": ACCOUNT_ID_PATTERN}
    return schema
