# Release requirements

Every version release must ship **both** the Python distribution on PyPI and a fresh Claude Desktop `.mcpb` on GitHub. Do not publish a standalone GitHub release and treat that as a completed update.

1. Bump `pyproject.toml` and `manifest.json` together, update the manifest documentation tag and the installation download filename, and run `uv lock`.
2. Run CI, including `tests/test_desktop_updates.py`. That test launches a real UV tool twice against a temporary local index: a newly available stable release must be selected using the unchanged launcher and cache, while a newer prerelease is excluded.
3. Merge the reviewed release commit, then push its matching `vX.Y.Z` tag. A normal source commit without a new version tag does not publish to PyPI.
4. The **Release** workflow tests/audits/builds the Python distributions and desktop bundle, publishes to PyPI with Trusted Publishing, verifies public PyPI SHA-256 digests, then starts the bundle and checks that `auth_status.server_version` equals the release version. Only then does it create/update the GitHub release and attach all files.
5. Verify the workflow succeeds and both PyPI and GitHub downloads exist. Do not report completion while PyPI publication or the post-publication start test has failed.

The workflow can be rerun or dispatched against an existing tag. PyPI uploads skip already-existing files, but verification must confirm their hashes match the build. Existing GitHub releases receive the checked artifacts rather than failing with “release already exists”. Release runs are serialized. Never move an existing release tag or overwrite a PyPI version with changed code; use a new version.

The desktop launcher updates at server startup from the public HTTPS PyPI index, not from GitHub source. It ignores inherited alternate indexes, resolution overrides, and offline settings. The minimum supported server is 0.3.0; subsequent stable versions are intentionally unbounded to meet automatic-update requirements. The installed launcher and configuration form are not themselves automatically replaced by PyPI. Changes to those require a new MCPB import unless distribution moves to Claude's official auto-updating directory.
