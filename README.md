# flin-linkedin-posts-mcp

`flin-linkedin-posts-mcp` is a local MCP server for reading and analyzing the authenticated member's own LinkedIn post/share data.

It uses LinkedIn member OAuth login and the Member Data Portability API. Each user runs the MCP locally, signs into their own LinkedIn account in the system browser, and stores their token on their own machine.

The MCP supports two login flows:

- Regular 3-legged OAuth with a client secret. This is the recommended local setup for most LinkedIn Developer apps.
- Native OAuth PKCE. This does not require a client secret, but LinkedIn must explicitly enable the Native PKCE protocol for your app.

## Important Access Requirement

This MCP does not bypass LinkedIn API approval. Each user should create their own LinkedIn Developer app with access to Member Data Portability API (Member) and the `r_dma_portability_self_serve` permission. Without that product/scope, LinkedIn returns `403 ACCESS_DENIED` for `memberSnapshotData`.

Native PKCE is a separate LinkedIn app capability. If LinkedIn shows `Not enough permissions to access Native PKCE protocol`, use the regular 3-legged OAuth setup below or ask LinkedIn to enable Native PKCE for the app.

Relevant LinkedIn docs:

- 3-legged OAuth: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- Native OAuth PKCE: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native
- Member Snapshot API: https://learn.microsoft.com/en-us/linkedin/dma/member-data-portability/shared/member-snapshot-api
- Snapshot domains: https://learn.microsoft.com/en-us/linkedin/dma/member-data-portability/shared/snapshot-domain
- API access overview: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access

## Features

- Browser-based LinkedIn login with regular OAuth or native PKCE
- Local token storage outside the repository
- Auth status and logout tools
- Snapshot domain count/debug tool
- Authenticated member post/share listing from `MEMBER_SHARE_INFO`
- Post analysis for counts, text length, hashtags, mentions, and top terms
- Best-effort extraction of engagement counters when they are present in snapshot rows
- Draft-to-published matching based on provided draft texts

## MCP Tools

1. `auth_status`
2. `login`
3. `logout`
4. `list_snapshot_domains`
5. `list_member_posts`
6. `analyze_member_posts`
7. `match_drafts_to_member_posts`

## Configuration

Required for login:

- `LINKEDIN_CLIENT_ID`: LinkedIn Developer app client ID

Recommended for regular 3-legged OAuth:

- `LINKEDIN_CLIENT_SECRET`: LinkedIn Developer app client secret. If set, `LINKEDIN_OAUTH_FLOW` defaults to `authorization_code`.
- `LINKEDIN_REDIRECT_URI`: exact local callback URI registered in the LinkedIn app, for example `http://127.0.0.1:63141/callback`.

Optional:

- `LINKEDIN_OAUTH_FLOW`: `authorization_code` or `native_pkce`. Defaults to `authorization_code` when `LINKEDIN_CLIENT_SECRET` is set, otherwise `native_pkce`.
- `LINKEDIN_SCOPES`: defaults to `r_dma_portability_self_serve`
- `LINKEDIN_API_VERSION`: defaults to `202312`
- `LINKEDIN_RESTLI_PROTOCOL_VERSION`: defaults to `2.0.0`
- `LINKEDIN_TIMEOUT_SECONDS`: defaults to `30`
- `LINKEDIN_MAX_RETRIES`: defaults to `3`
- `LINKEDIN_OAUTH_TIMEOUT_SECONDS`: defaults to `300`
- `LINKEDIN_TOKEN_FILE`: defaults to `~/.flin-linkedin-posts-mcp/tokens.json`

The MCP intentionally does not require `LINKEDIN_ACCESS_TOKEN` anymore. Tokens are created through the `login` tool.

## LinkedIn Developer App Setup

1. Create or open a LinkedIn Developer app.
2. Add/obtain access to `Member Data Portability API (Member)`.
3. Make sure the app can request `r_dma_portability_self_serve`.
4. For regular 3-legged OAuth, add an exact loopback redirect URL in the app's Auth tab, for example `http://127.0.0.1:63141/callback`.
5. Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, and `LINKEDIN_REDIRECT_URI` to the same redirect URL.
6. For native PKCE only, ask LinkedIn to enable Native PKCE OAuth for the app, omit `LINKEDIN_CLIENT_SECRET`, and configure loopback redirect URIs as LinkedIn requires.

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
        "LINKEDIN_CLIENT_SECRET": "<YOUR_LINKEDIN_CLIENT_SECRET>",
        "LINKEDIN_REDIRECT_URI": "http://127.0.0.1:63141/callback",
        "LINKEDIN_SCOPES": "r_dma_portability_self_serve",
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
        "LINKEDIN_CLIENT_SECRET": "<YOUR_LINKEDIN_CLIENT_SECRET>",
        "LINKEDIN_REDIRECT_URI": "http://127.0.0.1:63141/callback",
        "LINKEDIN_SCOPES": "r_dma_portability_self_serve",
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
5. `match_drafts_to_member_posts` if you want to compare draft text to published posts

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
- `Not enough permissions to access Native PKCE protocol`: the LinkedIn app does not have Native PKCE enabled. Set `LINKEDIN_CLIENT_SECRET` and `LINKEDIN_REDIRECT_URI` to use regular 3-legged OAuth, or ask LinkedIn to enable Native PKCE for the app.
- `LINKEDIN_REDIRECT_URI is required when LINKEDIN_OAUTH_FLOW=authorization_code`: add the same exact local callback URL to the LinkedIn app's Auth tab and to the MCP config.
- `403 ACCESS_DENIED` for `partnerApiMemberSnapshotData`: the LinkedIn Developer app/token likely does not have Member Data Portability API access or `r_dma_portability_self_serve`.
- `LinkedIn token has expired`: run `login` again. If LinkedIn issued a refresh token, the MCP attempts a refresh automatically before requiring login.
- `Timed out waiting for LinkedIn OAuth callback`: rerun `login` and complete the browser flow within `LINKEDIN_OAUTH_TIMEOUT_SECONDS`.

## Notes

- The MCP reads only the authenticated member's own snapshot data.
- It does not support arbitrary-author LinkedIn post lookup.
- `MEMBER_SHARE_INFO` is snapshot/export-style data, so field names can vary. The normalizer is intentionally tolerant and keeps `include_raw=true` available for debugging.
- LinkedIn's portability data for `Shares` is documented around fields like date, link, commentary, media URL, and visibility. Likes, comments, and impressions are exposed only if they appear in the snapshot payload returned for that member.
- Saved LinkedIn drafts are not exposed as a documented portability snapshot domain here. `match_drafts_to_member_posts` compares draft texts you already have against published posts; it does not fetch drafts from LinkedIn.
