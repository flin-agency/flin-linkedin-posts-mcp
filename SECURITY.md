# Security

Use the latest release. Report vulnerabilities privately through the repository's GitHub **Security → Report a vulnerability** feature when available. Do not post tokens, client secrets, private exports, or working exploit details in public issues; if private reporting is unavailable, contact the repository maintainers privately first.

## Trust boundaries

- This is a local stdio MCP server. OAuth alone temporarily opens a loopback HTTP listener.
- The API client permits only GET requests to HTTPS `api.linkedin.com` under `/rest/` or `/v2/`, with redirects disabled. OAuth token exchange uses LinkedIn's fixed HTTPS endpoint.
- Tokens are stored in a local plaintext file, created with owner-only permissions before writing and replaced atomically. A newly created token directory has mode `0700`. Existing parent directories are not chmod'ed. The account, its other processes, administrators, and backups remain trusted.
- Claude Desktop's client-secret field is marked sensitive. Tokens are never bundled. Errors redact known credentials and sensitive keys; no unexpected exception traceback is sent to logs.
- Post content is untrusted data. It is returned to the MCP host; the host is responsible for model prompt-injection defences and approval of other tools.
- `logout` deletes local credentials; it does not revoke them remotely.
- The MCPB ships source and a dependency lockfile, and requires network access on first launch. The release checksum is an integrity check, not a signature.

See [the security review](docs/security-review-2026-11-06.md) for findings, evidence, and limits. Automated scans detect known issues only and are not a security guarantee.
