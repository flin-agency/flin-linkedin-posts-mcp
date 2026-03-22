from __future__ import annotations

from typing import Any, Callable

from .config import LinkedInPostsSettings
from .guards import assert_read_only_tool
from .linkedin_client import LinkedInClient
from .tools.member_posts import analyze_member_posts, get_member_profile, get_post, list_member_posts

ToolHandler = Callable[[LinkedInClient, LinkedInPostsSettings, dict[str, Any]], dict[str, Any]]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_member_profile": lambda client, settings, arguments: get_member_profile(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "list_member_posts": lambda client, settings, arguments: list_member_posts(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "get_post": lambda client, settings, arguments: get_post(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "analyze_member_posts": lambda client, settings, arguments: analyze_member_posts(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
}


def dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    settings: LinkedInPostsSettings,
    client: LinkedInClient,
) -> dict[str, Any]:
    assert_read_only_tool(name)
    try:
        handler = TOOL_HANDLERS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown tool: {name}") from exc
    return handler(client, settings, arguments)
