from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tools.member_posts import ANALYTICS_METRIC_TYPES


DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
ANALYTICS_DATE_PROPERTIES = {
    "start_date": {"type": "string", "pattern": DATE_PATTERN, "description": "Inclusive start date (YYYY-MM-DD)."},
    "end_date": {"type": "string", "pattern": DATE_PATTERN, "description": "Exclusive end date (YYYY-MM-DD)."},
}
ANALYTICS_PROPERTIES = {
    **ANALYTICS_DATE_PROPERTIES,
    "aggregation": {"type": "string", "enum": ["TOTAL", "DAILY"], "default": "TOTAL"},
    "metric_types": {
        "type": "array", "items": {"type": "string", "enum": list(ANALYTICS_METRIC_TYPES)},
        "minItems": 1, "maxItems": 11,
    },
}
CONNECTION_SCHEMA = {
    "type": "object",
    "properties": {"connection": {"type": "string", "enum": ["portability", "analytics"], "default": "portability"}},
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="auth_status",
            description="Check local OAuth status for both connections, or select portability/analytics; this does not verify API approval",
            input_schema=CONNECTION_SCHEMA,
        ),
        ToolSpec(
            name="login",
            description="Log into portability (post content) or analytics (post metrics) using separate local tokens; use the same LinkedIn account",
            input_schema=CONNECTION_SCHEMA,
        ),
        ToolSpec(
            name="logout",
            description="Delete the selected connection's local OAuth token; the other connection is preserved",
            input_schema=CONNECTION_SCHEMA,
        ),
        ToolSpec(
            name="list_snapshot_domains",
            description="List available LinkedIn Member Data Portability snapshot domains and item counts",
            input_schema={
                "type": "object",
                "properties": {
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="list_member_posts",
            description="List posts/share records for the authenticated LinkedIn member",
            input_schema={
                "type": "object",
                "properties": {
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                    "include_raw": {"type": "boolean"},
                    "published_after": {"type": "string", "pattern": DATE_PATTERN},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="analyze_member_posts",
            description="Analyze the authenticated member's LinkedIn posts/share records",
            input_schema={
                "type": "object",
                "properties": {
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                    "top_n": {"type": "integer", "minimum": 1, "maximum": 25},
                    "include_posts": {"type": "boolean"},
                    "post_limit": {"type": "integer", "minimum": 1, "maximum": 500},
                    "published_after": {"type": "string", "pattern": DATE_PATTERN},
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="match_drafts_to_member_posts",
            description="Match draft post texts against the authenticated member's published LinkedIn posts",
            input_schema={
                "type": "object",
                "properties": {
                    "drafts": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 10000},
                        "minItems": 1,
                        "maxItems": 50,
                    },
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                    "published_after": {"type": "string", "pattern": DATE_PATTERN},
                    "post_limit": {"type": "integer", "minimum": 1, "maximum": 500},
                    "max_matches_per_draft": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["drafts"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_post_social_metadata",
            description="Fetch comment and reaction summary data for a single LinkedIn post",
            input_schema={
                "type": "object",
                "properties": {
                    "post_urn": {"type": "string"},
                    "post_url": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_member_post_analytics",
            description="Fetch personal post metrics, optionally by date range or day. DAILY excludes impressions, reach, link clicks, follower gains and profile views. Defaults to supported metrics; one API call per metric plus retries.",
            input_schema={
                "type": "object",
                "properties": {
                    "post_urn": {"type": "string"},
                    "post_url": {"type": "string"},
                    **ANALYTICS_PROPERTIES,
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_member_analytics",
            description="Fetch aggregate analytics across your own posts, optionally by date range or day. TOTAL reach is deduplicated by LinkedIn. DAILY excludes reach, link clicks, follower gains and profile views. One API call per metric plus retries; no portability login needed.",
            input_schema={"type": "object", "properties": ANALYTICS_PROPERTIES, "additionalProperties": False},
        ),
        ToolSpec(
            name="get_member_follower_statistics",
            description="Fetch your lifetime follower count or daily follower statistics for a date range. Requires r_member_profileAnalytics on the analytics connection. One API call plus retries.",
            input_schema={"type": "object", "properties": ANALYTICS_DATE_PROPERTIES, "additionalProperties": False},
        ),
        ToolSpec(
            name="enrich_member_posts_with_engagement",
            description="Combine portability post content with analytics from the second connection. Defaults: 5 posts, 5 metrics, no social metadata; per-call request budget including retries, not a daily quota",
            input_schema={
                "type": "object",
                "properties": {
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 5},
                    "max_api_calls": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                    "published_after": {"type": "string", "pattern": DATE_PATTERN},
                    "include_social_metadata": {"type": "boolean", "default": False},
                    "include_post_analytics": {"type": "boolean"},
                    "analytics_metric_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(ANALYTICS_METRIC_TYPES)},
                        "minItems": 1,
                        "maxItems": 11,
                    },
                },
                "additionalProperties": False,
            },
        ),
    ]
