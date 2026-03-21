from __future__ import annotations


def test_server_module_imports_without_mcp_dependency() -> None:
    from flin_linkedin_ads_mcp import server

    assert hasattr(server, "main")
