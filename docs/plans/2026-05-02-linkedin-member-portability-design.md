# LinkedIn Member Portability MCP Design

## Goal

Rebuild `flin-linkedin-posts-mcp` as a packaged local MCP that lets each user sign in with their own LinkedIn account and read their own post/share data through LinkedIn Member Data Portability.

## Architecture

The MCP uses LinkedIn's native OAuth PKCE flow. The `login` tool opens the user's system browser, listens on a temporary `127.0.0.1` callback URL, exchanges the authorization code for an access token, and stores the token in a local user config file outside the repository.

Data reads use `GET https://api.linkedin.com/rest/memberSnapshotData` with `q=criteria` and `domain=MEMBER_SHARE_INFO`. The implementation normalizes the snapshot records into the same high-level post shape used by the existing analyzer where possible.

## Configuration

- `LINKEDIN_CLIENT_ID` is required for interactive login.
- `LINKEDIN_SCOPES` defaults to `r_dma_portability_self_serve`.
- `LINKEDIN_API_VERSION` defaults to `202312` for Member Data Portability.
- `LINKEDIN_TOKEN_FILE` optionally overrides the local token store path.
- The package must not require or ship a client secret.

## MCP Tools

- `auth_status`: report whether a token is available and whether it is expired.
- `login`: start local OAuth PKCE login and store the returned token.
- `logout`: remove the stored token.
- `list_snapshot_domains`: fetch domain counts/debug data from `memberSnapshotData`.
- `list_member_posts`: fetch and normalize authenticated-member `MEMBER_SHARE_INFO` records.
- `analyze_member_posts`: summarize fetched member posts.

## Error Handling

Missing client ID, missing token, expired token, OAuth callback errors, LinkedIn 401/403 responses, and unsupported token payloads return structured MCP errors. A LinkedIn 403 is surfaced as a permission error with enough context to explain that the user's developer app likely lacks Member Data Portability approval.

## Packaging

The package remains installable through `uvx` or local editable installs. README setup instructions must explain that each user needs a LinkedIn Developer app with Member Data Portability API access and a loopback redirect URI.

## Testing

Tests cover config defaults, PKCE generation, token-store persistence, OAuth URL construction/token exchange, tool registry/guard wiring, snapshot pagination, post normalization, and analysis filtering.
