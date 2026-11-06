"""Build a deterministic auto-updating launcher bundle with an explicit file allowlist."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build_bundle(output_dir: Path, *, root: Path = ROOT) -> Path:
    manifest = json.loads((root / "manifest.json").read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())
    version = project["project"]["version"]
    if manifest["version"] != version:
        raise ValueError("Manifest and project versions must match")
    files = [root / name for name in (
        "manifest.json", "README.md", "LICENSE",
        "SECURITY.md", "desktop/server.py", "docs/claude-desktop-macos.md",
        "docs/security-review-2026-11-06.md", "docs/releasing.md",
    )]
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"flin-linkedin-posts-mcp-{version}-macos.mcpb"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        # MCPB UV hosts require project metadata, but the launcher has no dependencies.
        metadata = (
            '[project]\nname = "flin-linkedin-desktop-launcher"\n'
            f'version = "{version}"\nrequires-python = ">=3.11"\ndependencies = []\n'
        )
        info = zipfile.ZipInfo("pyproject.toml", date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, metadata)
        for path in files:
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Expected a regular file: {path}")
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (output_dir / "SHA256SUMS").write_text(f"{digest}  {output.name}\n")
    return output


if __name__ == "__main__":
    print(build_bundle(ROOT / "dist" / "desktop"))
