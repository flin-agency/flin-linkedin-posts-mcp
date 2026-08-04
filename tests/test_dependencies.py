from __future__ import annotations

import tomllib
from pathlib import Path


def test_mcp_dependency_excludes_breaking_v2() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies = pyproject["project"]["dependencies"]
    mcp_requirement = next(item for item in dependencies if item.startswith("mcp"))

    assert mcp_requirement == "mcp>=1.0.0,<2"
