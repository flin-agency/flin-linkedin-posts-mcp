from __future__ import annotations

from flin_linkedin_posts_mcp.tool_registry import tool_specs


def test_tool_registry_exposes_expected_read_only_tools() -> None:
    names = [spec.name for spec in tool_specs()]

    assert names == [
        "get_member_profile",
        "list_member_posts",
        "get_post",
        "analyze_member_posts",
    ]
