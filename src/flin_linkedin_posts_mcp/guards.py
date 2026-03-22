from __future__ import annotations


READ_ONLY_TOOL_NAMES = {
    "get_member_profile",
    "list_member_posts",
    "get_post",
    "analyze_member_posts",
}


def assert_read_only_tool(name: str) -> None:
    if name not in READ_ONLY_TOOL_NAMES:
        raise PermissionError("Tool is not allowed in strict read-only mode")
