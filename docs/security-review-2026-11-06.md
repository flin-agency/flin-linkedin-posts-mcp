# Security review — 2026-11-06 / v0.3.0

Scope: all server source, OAuth/token handling, tool inputs, API transport, dependency lock, GitHub workflows, and the new macOS Claude Desktop bundle. Review combines manual inspection, security regression tests, Bandit static analysis, and pip-audit of the locked runtime requirements.

## Findings fixed

| Finding | Exposure before fix | Remediation |
| --- | --- | --- |
| Token-file write before chmod | Local disclosure window and symlink overwrite risk | `mkstemp` with mode 0600 before writing, atomic replacement, new directory mode 0700, refuse symlink reads |
| Unrestricted absolute API URLs | Reusable client could send bearer credentials to arbitrary HTTP/HTTPS targets; current MCP tools did not expose arbitrary URLs directly | Exact HTTPS API host/path allowlist, explicit redirect rejection and GET-only enforcement |
| Invalid OAuth state aborts login | Unauthenticated loopback request could cancel login | Constant-time comparison; invalid callbacks leave the login pending |
| Shutdown before callback server starts | Invalid OAuth configuration could hang instead of returning an error | Shutdown only after the server thread starts; always close resources |
| Upstream errors and tracebacks | Responses could echo credentials into MCP output or logs | Redact sensitive fields and known credentials; omit unexpected tracebacks |
| Cyclic snapshot pagination | Repeated cursor could run indefinitely | Require cursor progress and enforce 1000-page ceiling |
| Unbounded draft inputs | Excessive comparison work when calling handlers directly | Maximum 50 drafts, 10000 characters per draft |
| Floating installation dependencies | Different installations could resolve different dependency versions | Commit audited `uv.lock`; bundle starts with `uv run --locked --no-dev` |
| Packaging local files | Broad archiving could include `.env`, tokens, or virtual environments | Explicit source/documentation allowlist, symlink checks, deterministic ZIP and SHA-256 checksum |

OAuth callback HTML also sends no-store, no-referrer and restrictive content-security-policy headers. Sensitive callback text is HTML-escaped. Runtime requests keep TLS verification enabled. No shell evaluation, arbitrary command execution, write-to-LinkedIn tool, telemetry, or post-content execution was found in the application source.

## Validation

- Complete pytest suite (81 tests), including real loopback callback requests with mocked LinkedIn token exchange.
- Ruff and mypy checks.
- Bandit source scan. A public OAuth endpoint URL is explicitly marked as a false-positive hardcoded-password finding; no finding is suppressed globally.
- pip-audit against the complete pinned runtime dependency export: no known vulnerabilities reported on the review date.
- detect-secrets scan of project files: findings reviewed as test fixtures (PKCE example, dummy secrets, rejected-URL cases); no live credentials identified. Git history was not exhaustively secret-scanned.
- Official MCPB manifest validation, deterministic archive/content checks, and stdio initialization/tool-discovery/auth-status smoke test from an extracted bundle.
- Source archives and wheel validated as Python distributions; GitHub CI repeats the automated quality and package checks.

## Limits and remaining risks

This is not an independent penetration test or a guarantee of vulnerability absence. No real LinkedIn login, granted-product availability, or data retrieval was tested because those require the user's own app credentials and account consent. The Claude Desktop graphical installer was not exercised. Runtime execution was tested on the available macOS host; Intel compatibility is based on the managed Python/UV format and portable source, not a second physical Intel Mac test.

Tokens remain plaintext for the local account. The extension is not signed/notarized. Dependency and package registries, the MCP host, the operating system, and same-user local processes remain trusted. Post text returned to Claude can contain malicious instructions; the host must treat it as data. Snapshot output and network response size are not globally capped; large legitimate exports can consume significant memory/time despite bounded page count and draft inputs. Dependencies need ongoing updates and rescanning.
