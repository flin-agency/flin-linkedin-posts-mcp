# Repository requirements

- Every version update must publish both PyPI distributions and a new Claude Desktop MCPB. Use the tag-triggered `.github/workflows/release.yml`; a GitHub-only release is incomplete.
- Follow `docs/releasing.md`. Keep package/manifest versions, documentation links and `uv.lock` consistent.
- Preserve the desktop launcher's automatic stable PyPI updates at server startup. Do not revert to a bundled or pinned server without an explicit user request.
- Verify the real update-selection test and the published PyPI version, not only a local wheel. Be clear that a running server needs a restart and that changes to extension configuration fields require a one-time new MCPB import.
