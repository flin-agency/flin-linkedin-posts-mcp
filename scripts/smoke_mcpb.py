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


async def smoke(bundle: Path) -> None:
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
                assert len(tools.tools) == 10
                result = await session.call_tool("auth_status", {})
                assert not result.isError
                payload = json.loads(result.content[0].text)
                assert payload["ok"] and payload["data"]["authenticated"] is False
                assert payload["data"]["client_secret_configured"] is False
                print("Packaged MCP initialized; 10 tools found; unauthenticated auth_status passed.")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(smoke(Path(sys.argv[1]).resolve()), timeout=120))
