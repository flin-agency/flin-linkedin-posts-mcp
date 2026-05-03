from __future__ import annotations

from flin_linkedin_posts_mcp.tool_registry import tool_specs


def test_tool_registry_exposes_expected_read_only_tools() -> None:
    names = [spec.name for spec in tool_specs()]

    assert names == [
        "auth_status",
        "login",
        "logout",
        "list_snapshot_domains",
        "list_member_posts",
        "analyze_member_posts",
        "match_drafts_to_member_posts",
    ]
