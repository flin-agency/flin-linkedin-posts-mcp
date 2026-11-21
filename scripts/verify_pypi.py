"""Wait for PyPI and verify that the published files match this release build."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def verify() -> None:
    version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    url = f"https://pypi.org/pypi/flin-linkedin-posts-mcp/{version}/json"
    # Trusted Publishing adds .publish.attestation sidecars to this directory.
    # Verify both distributions explicitly, never those publisher-generated files.
    distributions = [
        Path("dist/release") / f"flin_linkedin_posts_mcp-{version}-py3-none-any.whl",
        Path("dist/release") / f"flin_linkedin_posts_mcp-{version}.tar.gz",
    ]
    expected = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in distributions}
    for attempt in range(12):
        try:
            with urlopen(url, timeout=15) as response:  # nosec B310: fixed HTTPS PyPI URL
                data = json.load(response)
            published = {item["filename"]: item["digests"]["sha256"] for item in data["urls"]}
            for filename, digest in expected.items():
                if published.get(filename) != digest:
                    raise RuntimeError(f"PyPI file missing or checksum mismatch: {filename}")
            print(f"PyPI {version}: all distribution checksums verified.")
            return
        except (HTTPError, URLError, RuntimeError):
            if attempt == 11:
                raise
            time.sleep(5)


if __name__ == "__main__":
    verify()
