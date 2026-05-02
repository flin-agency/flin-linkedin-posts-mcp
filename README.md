# flin-linkedin-posts-mcp

`flin-linkedin-posts-mcp` is a local MCP server for reading and analyzing the authenticated member's own LinkedIn post/share data.

It uses LinkedIn native OAuth PKCE login and the Member Data Portability API. Each user runs the MCP locally, signs into their own LinkedIn account in the system browser, and stores their token on their own machine.

## Important Access Requirement

This MCP does not bypass LinkedIn API approval. The LinkedIn Developer app used by the local user must have access to Member Data Portability API (3rd Party) and the `r_dma_portability_3rd_party` permission. Without that product/scope, LinkedIn returns `403 ACCESS_DENIED` for `memberSnapshotData`.

Relevant LinkedIn docs:

- Native OAuth PKCE: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native
- Member Snapshot API: https://learn.microsoft.com/en-us/linkedin/dma/member-data-portability/shared/member-snapshot-api
- Snapshot domains: https://learn.microsoft.com/en-us/linkedin/dma/member-data-portability/shared/snapshot-domain
- API access overview: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access

## Features

- Browser-based LinkedIn login with OAuth PKCE
- Local token storage outside the repository
- Auth status and logout tools
- Snapshot domain count/debug tool
- Authenticated member post/share listing from `MEMBER_SHARE_INFO`
- Post analysis for counts, text length, hashtags, mentions, and top terms

## MCP Tools

1. `auth_status`
2. `login`
3. `logout`
4. `list_snapshot_domains`
5. `list_member_posts`
6. `analyze_member_posts`

## Configuration

Required for login:

- `LINKEDIN_CLIENT_ID`: LinkedIn Developer app client ID

Optional:

- `LINKEDIN_SCOPES`: defaults to `r_dma_portability_3rd_party`
- `LINKEDIN_API_VERSION`: defaults to `202312`
- `LINKEDIN_RESTLI_PROTOCOL_VERSION`: defaults to `2.0.0`
- `LINKEDIN_TIMEOUT_SECONDS`: defaults to `30`
- `LINKEDIN_MAX_RETRIES`: defaults to `3`
- `LINKEDIN_OAUTH_TIMEOUT_SECONDS`: defaults to `300`
- `LINKEDIN_TOKEN_FILE`: defaults to `~/.flin-linkedin-posts-mcp/tokens.json`

The MCP intentionally does not require `LINKEDIN_ACCESS_TOKEN` anymore. Tokens are created through the `login` tool.

## LinkedIn Developer App Setup

1. Create or open a LinkedIn Developer app.
2. Add/obtain access to `Member Data Portability API (3rd Party)`.
3. Make sure the app can request `r_dma_portability_3rd_party`.
4. Configure native PKCE OAuth support with loopback redirect URIs.
5. Add a loopback redirect URI pattern supported by LinkedIn, for example `http://127.0.0.1:{port}/callback` if the portal allows dynamic loopback ports. If the portal requires exact ports, run the MCP with a matching callback port after extending the config.
6. Use the app's Client ID as `LINKEDIN_CLIENT_ID`.

## Claude Desktop Configuration

For a published package:

```json
{
  "mcpServers": {
    "flin-linkedin-posts-mcp": {
      "command": "uvx",
      "args": ["--refresh", "flin-linkedin-posts-mcp@latest"],
      "env": {
        "LINKEDIN_CLIENT_ID": "<YOUR_LINKEDIN_CLIENT_ID>",
        "LINKEDIN_API_VERSION": "202312"
      }
    }
  }
}
```

For local development from this repository:

```json
{
  "mcpServers": {
    "flin-linkedin-posts-mcp": {
      "command": "uv",
      "args": ["run", "flin-linkedin-posts-mcp"],
      "cwd": "/path/to/flin-linkedin-posts-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "<YOUR_LINKEDIN_CLIENT_ID>",
        "LINKEDIN_API_VERSION": "202312"
      }
    }
  }
}
```

After adding the config, restart the MCP host and call:

1. `auth_status`
2. `login`
3. `list_snapshot_domains`
4. `list_member_posts` or `analyze_member_posts`

## Local Development

```bash
python3 -m pip install -e '.[dev]'
pytest -q
ruff check .
```

## Packaging

```bash
python3 -m build
```

The package entry point is:

```bash
flin-linkedin-posts-mcp
```

## Troubleshooting

- `LINKEDIN_CLIENT_ID is required before running login`: set `LINKEDIN_CLIENT_ID` in the MCP config.
- `403 ACCESS_DENIED` for `partnerApiMemberSnapshotData`: the LinkedIn Developer app/token likely does not have Member Data Portability API access or `r_dma_portability_3rd_party`.
- `LinkedIn token has expired`: run `login` again. If LinkedIn issued a refresh token, the MCP attempts a refresh automatically before requiring login.
- `Timed out waiting for LinkedIn OAuth callback`: rerun `login` and complete the browser flow within `LINKEDIN_OAUTH_TIMEOUT_SECONDS`.

## Notes

- The MCP reads only the authenticated member's own snapshot data.
- It does not support arbitrary-author LinkedIn post lookup.
- `MEMBER_SHARE_INFO` is snapshot/export-style data, so field names can vary. The normalizer is intentionally tolerant and keeps `include_raw=true` available for debugging.
