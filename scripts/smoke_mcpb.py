"""Exercise the actual packaged stdio server without LinkedIn credentials."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def smoke(bundle: Path, expected_version: str | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="flin-mcpb-smoke-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(bundle) as archive:
            archive.extractall(root)
        manifest = json.loads((root / "manifest.json").read_text())
        config = manifest["server"]["mcp_config"]
        args = [arg.replace("${__dirname}", str(root)) for arg in config["args"]]
        env = {key: value for key, value in os.environ.items() if not key.startswith(("LINKEDIN_", "PYTHONPATH", "VIRTUAL_ENV"))}
        env["LINKEDIN_TOKEN_FILE"] = str(root / "test-tokens.json")
        parameters = StdioServerParameters(command=shutil.which("uv") or "uv", args=args, env=env)
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {"auth_status", "get_member_post_analytics"} <= names
                if expected_version is not None:
                    assert {"get_member_analytics", "get_member_follower_statistics"} <= names
                result = await session.call_tool("auth_status", {})
                assert not result.isError
                payload = json.loads(result.content[0].text)
                assert payload["ok"] and payload["data"]["authenticated"] is False
                assert payload["data"]["client_secret_configured"] is False
                if expected_version is not None:
                    assert payload["data"]["server_version"] == expected_version, payload["data"]
                print(f"Packaged MCP initialized; {len(names)} tools found; unauthenticated auth_status passed.")


async def verify_startup(bundle: Path, expected_version: str | None = None) -> None:
    # PyPI JSON and the package index can propagate at different times. Keep
    # using the unchanged launcher/cache, and still require the exact version.
    attempts = 12 if expected_version is not None else 1
    for attempt in range(attempts):
        try:
            await smoke(bundle, expected_version)
            return
        except Exception:
            if attempt == attempts - 1:
                raise
            print("Published server not ready; retrying startup in 5 seconds.")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(verify_startup(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 else None), timeout=120))
