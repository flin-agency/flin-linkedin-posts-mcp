# flin-linkedin-ads-mcp Design

## Goal
Build a strict read-only MCP server for LinkedIn Ads that mirrors the architecture and UX of `flin-meta-ads-mcp`, so it can be installed via `uvx` and used in Claude with minimal setup.

## Scope (v0.1.x)
- Read-only only.
- No create/update/delete actions.
- No OAuth exchange or token refresh flow.
- No generic proxy endpoint.

## Architecture
- Keep the same layered structure as `flin-meta-ads-mcp`:
  - `server.py`: MCP bindings and tool exposure.
  - `dispatcher.py`: tool routing.
  - `tool_registry.py`: JSON Schemas for tool args.
  - `linkedin_client.py`: HTTP layer + retry/error mapping.
  - `tools/*.py`: domain logic (accounts, campaign groups, campaigns, creatives, analytics).
  - `response.py`: consistent normalized MCP JSON payload.
- Keep output envelope unchanged (`ok`, `data`, `paging`, `meta`) for easy downstream compatibility.

## API Model
- Base URL: `https://api.linkedin.com/rest`
- Required headers:
  - `Authorization: Bearer <token>`
  - `Linkedin-Version: YYYYMM` (configurable)
  - `X-Restli-Protocol-Version: 2.0.0`
- Search endpoints use `q=search` with optional `search` expression and cursor pagination (`pageToken`, `metadata.nextPageToken`).

## Exposed Tools
- `list_ad_accounts`
- `get_ad_account`
- `list_campaign_groups`
- `get_campaign_group`
- `list_campaigns`
- `get_campaign`
- `list_creatives`
- `get_creative`
- `get_insights`

## Validation & Safety
- Strict read-only allowlist in `guards.py`.
- Strong identifier validation (numeric account IDs, URN formats for linked entities).
- Reject unknown/unsupported field requests.
- Retry transient errors (429/5xx) with exponential backoff.

## Testing Strategy
- Unit tests for:
  - config parsing defaults/required vars
  - client retry/auth-header/error mapping
  - read-only guard
  - tool registry schemas
  - tool argument validation and endpoint construction
  - server fallback behavior for unexpected exceptions
- No live integration tests required for local readiness.

## Assumptions
- The user provides a valid LinkedIn Marketing API token with read permission (`r_ads`).
- MCP runtime provides the `mcp` package at execution time.
