from __future__ import annotations

import pytest

from flin_linkedin_posts_mcp.guards import assert_read_only_tool


def test_read_only_guard_accepts_post_tools() -> None:
    assert_read_only_tool("auth_status")
    assert_read_only_tool("login")
    assert_read_only_tool("logout")
    assert_read_only_tool("list_snapshot_domains")
    assert_read_only_tool("list_member_posts")
    assert_read_only_tool("analyze_member_posts")


def test_read_only_guard_rejects_removed_tools() -> None:
    with pytest.raises(PermissionError, match="read-only"):
        assert_read_only_tool("get_insights")
