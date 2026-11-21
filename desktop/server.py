"""Launch the latest stable PyPI server; never import a bundled server copy."""
from __future__ import annotations

import os
import shutil
from typing import Mapping

PYPI_INDEX = "https://pypi.org/simple"
SERVER_REQUIREMENT = "flin-linkedin-posts-mcp>=0.3.0"
SERVER_COMMAND = "flin-linkedin-posts-mcp"


def command(uv: str) -> list[str]:
    return [
        uv, "tool", "run", "--isolated", "--no-config", "--no-env-file",
        "--default-index", PYPI_INDEX, "--refresh", "--prerelease", "disallow",
        "--python", ">=3.11", "--from", SERVER_REQUIREMENT, SERVER_COMMAND,
    ]


def environment(source: Mapping[str, str]) -> dict[str, str]:
    # Do not let inherited indexes, overrides, offline mode or Python paths
    # redirect updates or shadow the installed package. Keep user credentials.
    return {
        key: value for key, value in source.items()
        if (not key.startswith("UV_") or key == "UV_CACHE_DIR")
        and key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }


def main() -> None:
    # uv run exposes its absolute executable path, including Claude-managed UV.
    uv = os.environ.get("UV") or shutil.which("uv")
    if uv is None:
        raise RuntimeError("Claude Desktop's managed uv runtime was not found; update Claude Desktop.")
    # Trusted host runtime, fixed arguments, no shell or tool-supplied command.
    os.execve(uv, command(uv), environment(os.environ))  # nosec B606


if __name__ == "__main__":
    main()
