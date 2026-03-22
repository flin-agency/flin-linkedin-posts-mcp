from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MEMBER_URN_PATTERN = r"^urn:li:person:[A-Za-z0-9_-]+$"
POST_URN_PATTERN = r"^urn:li:(?:share|ugcPost|post):[A-Za-z0-9_-]+$"
DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="get_member_profile",
            description="Resolve the currently authenticated LinkedIn member profile from the access token",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolSpec(
            name="list_member_posts",
            description="List LinkedIn posts authored by the current member or a specific member URN",
            input_schema={
                "type": "object",
                "properties": {
                    "author_urn": {"type": "string", "pattern": MEMBER_URN_PATTERN},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                    "page_token": {"type": "string"},
                    "include_raw": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_post",
            description="Fetch a single LinkedIn post and normalize its text/media fields",
            input_schema={
                "type": "object",
                "properties": {
                    "post_urn": {"type": "string", "pattern": POST_URN_PATTERN},
                    "include_raw": {"type": "boolean"},
                },
                "required": ["post_urn"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="analyze_member_posts",
            description="Analyze a member's recent LinkedIn posts and return summary metrics and top themes",
            input_schema={
                "type": "object",
                "properties": {
                    "author_urn": {"type": "string", "pattern": MEMBER_URN_PATTERN},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                    "page_token": {"type": "string"},
                    "top_n": {"type": "integer", "minimum": 1, "maximum": 25},
                    "include_posts": {"type": "boolean"},
                    "published_after": {"type": "string", "pattern": DATE_PATTERN},
                },
                "additionalProperties": False,
            },
        ),
    ]
