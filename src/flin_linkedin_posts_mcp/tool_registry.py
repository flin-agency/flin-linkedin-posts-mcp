from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="auth_status",
            description="Check whether the local MCP has a usable LinkedIn OAuth token",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolSpec(
            name="login",
            description="Start browser-based LinkedIn OAuth login and store the token locally",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolSpec(
            name="logout",
            description="Delete the locally stored LinkedIn OAuth token",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
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
                        "items": {"type": "string"},
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
    ]
