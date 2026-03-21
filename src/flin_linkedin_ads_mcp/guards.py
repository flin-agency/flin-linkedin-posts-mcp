from __future__ import annotations


READ_ONLY_TOOL_NAMES = {
    "list_ad_accounts",
    "get_ad_account",
    "list_campaign_groups",
    "get_campaign_group",
    "list_campaigns",
    "get_campaign",
    "list_creatives",
    "get_creative",
    "get_insights",
}


def assert_read_only_tool(name: str) -> None:
    if name not in READ_ONLY_TOOL_NAMES:
        raise PermissionError("Tool is not allowed in strict read-only mode")
