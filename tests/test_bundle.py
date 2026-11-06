import importlib.util
import json
from pathlib import Path
import zipfile


def test_bundle_is_reproducible_and_excludes_local_files(tmp_path):
    spec = importlib.util.spec_from_file_location("build_mcpb", "scripts/build_mcpb.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    first = module.build_bundle(tmp_path / "one")
    second = module.build_bundle(tmp_path / "two")
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        assert "uv.lock" in names
        assert "desktop/server.py" in names
        assert all(not any(part in {".env", ".git", ".venv", "__pycache__", "tokens.json"} for part in Path(name).parts) for name in names)
        assert all(name.startswith("src/") or name in {
            "manifest.json", "pyproject.toml", "uv.lock", "README.md", "LICENSE", "SECURITY.md",
            "desktop/server.py", "docs/claude-desktop-macos.md", "docs/security-review-2026-11-06.md",
        } for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["user_config"]["client_secret"]["sensitive"] is True
        assert "--locked" in manifest["server"]["mcp_config"]["args"]
