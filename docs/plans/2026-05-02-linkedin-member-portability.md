# LinkedIn Member Portability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a packaged local LinkedIn posts MCP where each user logs in with LinkedIn OAuth PKCE and reads their own Member Data Portability snapshot posts.

**Architecture:** Replace static bearer-token configuration with local OAuth/token storage and switch reads from `/rest/posts` to `/rest/memberSnapshotData`. Keep MCP responses stable and normalize `MEMBER_SHARE_INFO` snapshot records into post-shaped data.

**Tech Stack:** Python 3.11, `httpx`, MCP Python SDK, `pytest`, `respx`.

---

### Task 1: Config And Token Store

**Files:**
- Modify: `src/flin_linkedin_posts_mcp/config.py`
- Create: `src/flin_linkedin_posts_mcp/auth.py`
- Test: `tests/test_config.py`
- Test: `tests/test_auth.py`

**Steps:**

1. Write failing tests for config defaults without `LINKEDIN_ACCESS_TOKEN`.
2. Write failing tests for token save/load/delete using a temporary token file.
3. Implement `LinkedInPostsSettings` fields for client ID, scopes, token file, API version, timeout, and retries.
4. Implement `TokenRecord` and `TokenStore`.
5. Run targeted tests and keep them green.

### Task 2: OAuth PKCE Login

**Files:**
- Modify: `src/flin_linkedin_posts_mcp/auth.py`
- Test: `tests/test_auth.py`

**Steps:**

1. Write failing tests for PKCE challenge generation.
2. Write failing tests for authorization URL construction.
3. Write failing tests for exchanging a code into a persisted token.
4. Implement `OAuthFlow` helpers with browser/callback orchestration isolated enough for tests.
5. Run targeted tests.

### Task 3: Member Snapshot Client

**Files:**
- Modify: `src/flin_linkedin_posts_mcp/linkedin_client.py`
- Test: `tests/test_linkedin_client.py`

**Steps:**

1. Write failing tests for `memberSnapshotData` request headers and query parameters.
2. Write failing tests for pagination using `paging.links`.
3. Implement snapshot fetch helpers.
4. Run targeted tests.

### Task 4: MCP Tools

**Files:**
- Modify: `src/flin_linkedin_posts_mcp/tools/member_posts.py`
- Modify: `src/flin_linkedin_posts_mcp/tool_registry.py`
- Modify: `src/flin_linkedin_posts_mcp/dispatcher.py`
- Modify: `src/flin_linkedin_posts_mcp/guards.py`
- Modify: `src/flin_linkedin_posts_mcp/server.py`
- Test: `tests/test_member_posts.py`
- Test: `tests/test_tool_registry.py`
- Test: `tests/test_guards.py`
- Test: `tests/test_server.py`

**Steps:**

1. Write failing tests for auth tools, domain listing, post listing, and analysis.
2. Implement the new handlers and registry entries.
3. Remove obsolete profile/post-by-URN behavior.
4. Run targeted tests.

### Task 5: Docs And Verification

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml` if dependency metadata changes.

**Steps:**

1. Update README setup, OAuth, MCP config, and troubleshooting.
2. Run `pytest -q`.
3. Run `ruff check .` if available.
4. Run `python -m build` or `uv build` to verify packaging.
