from __future__ import annotations

from typing import Any, Callable

from .config import LinkedInPostsSettings
from .guards import assert_read_only_tool
from .linkedin_client import LinkedInClient
from .tools.member_posts import (
    analyze_member_posts,
    auth_status,
    list_member_posts,
    list_snapshot_domains,
    login,
    logout,
)

ToolHandler = Callable[[LinkedInClient | None, LinkedInPostsSettings, dict[str, Any]], dict[str, Any]]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "auth_status": lambda client, settings, arguments: auth_status(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "login": lambda client, settings, arguments: login(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "logout": lambda client, settings, arguments: logout(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "list_snapshot_domains": lambda client, settings, arguments: list_snapshot_domains(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "list_member_posts": lambda client, settings, arguments: list_member_posts(
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
    client: LinkedInClient | None = None,
) -> dict[str, Any]:
    assert_read_only_tool(name)
    try:
        handler = TOOL_HANDLERS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown tool: {name}") from exc
    return handler(client, settings, arguments)
