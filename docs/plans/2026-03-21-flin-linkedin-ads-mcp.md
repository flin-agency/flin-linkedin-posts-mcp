# flin-linkedin-ads-mcp Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a production-ready, read-only LinkedIn Ads MCP server with full tests and docs for immediate local testing.

**Architecture:** Reuse the proven `flin-meta-ads-mcp` modular structure, rename to LinkedIn package namespace, and swap Meta API calls for LinkedIn REST calls with strict input validation and consistent response envelope.

**Tech Stack:** Python 3.11+, `mcp`, `httpx`, `pytest`, `respx`, `ruff`, `mypy`

---

### Task 1: Rename package and metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `.env.example`
- Move: `src/flin_meta_ads_mcp` -> `src/flin_linkedin_ads_mcp`
- Update imports in all `src` and `tests` modules

**Step 1: Write the failing test**
- Use existing tests with old imports and run one targeted test expecting import failures after namespace decision.

**Step 2: Run test to verify it fails**
- `pytest tests/test_server_import.py -q`

**Step 3: Write minimal implementation**
- Rename package directory and update package name/imports/config env vars.

**Step 4: Run test to verify it passes**
- `pytest tests/test_server_import.py -q`

### Task 2: Implement LinkedIn HTTP client and config

**Files:**
- Create/Modify: `src/flin_linkedin_ads_mcp/linkedin_client.py`
- Modify: `src/flin_linkedin_ads_mcp/config.py`
- Modify: `src/flin_linkedin_ads_mcp/errors.py`
- Modify: `tests/test_meta_client.py` (renamed to linkedin client test)
- Modify: `tests/test_config.py`

**Step 1: Write failing tests**
- Add tests for LinkedIn base URL, required headers, retry behavior, and error mapping.

**Step 2: Run test to verify it fails**
- `pytest tests/test_linkedin_client.py -q`

**Step 3: Write minimal implementation**
- Implement `LinkedInClient` with retries and normalized request-id capture.

**Step 4: Run test to verify it passes**
- `pytest tests/test_linkedin_client.py -q`

### Task 3: Implement tool registry, guards, dispatcher

**Files:**
- Modify: `src/flin_linkedin_ads_mcp/tool_registry.py`
- Modify: `src/flin_linkedin_ads_mcp/guards.py`
- Modify: `src/flin_linkedin_ads_mcp/dispatcher.py`
- Modify: `tests/test_tool_registry.py`
- Modify: `tests/test_guards.py`

**Step 1: Write failing tests**
- Update expected tool names and schema assertions.

**Step 2: Run test to verify it fails**
- `pytest tests/test_tool_registry.py tests/test_guards.py -q`

**Step 3: Write minimal implementation**
- Register LinkedIn tools and enforce strict allowlist.

**Step 4: Run test to verify it passes**
- `pytest tests/test_tool_registry.py tests/test_guards.py -q`

### Task 4: Implement domain tools (accounts, campaign groups, campaigns, creatives, insights)

**Files:**
- Modify: `src/flin_linkedin_ads_mcp/tools/common.py`
- Modify: `src/flin_linkedin_ads_mcp/tools/accounts.py`
- Create: `src/flin_linkedin_ads_mcp/tools/campaign_groups.py`
- Modify: `src/flin_linkedin_ads_mcp/tools/campaigns.py`
- Modify: `src/flin_linkedin_ads_mcp/tools/creatives.py`
- Modify: `src/flin_linkedin_ads_mcp/tools/insights.py`
- Remove obsolete: adsets/ads/previews tool modules
- Modify: `tests/test_tools.py`

**Step 1: Write failing tests**
- Cover endpoint paths, parameter mapping, pagination token extraction, and validation failures.

**Step 2: Run test to verify it fails**
- `pytest tests/test_tools.py -q`

**Step 3: Write minimal implementation**
- Build LinkedIn REST calls and normalize responses.

**Step 4: Run test to verify it passes**
- `pytest tests/test_tools.py -q`

### Task 5: Wire MCP server and final docs

**Files:**
- Modify: `src/flin_linkedin_ads_mcp/server.py`
- Modify: `tests/test_server.py`
- Modify: `tests/test_server_import.py`
- Modify: `README.md`

**Step 1: Write failing tests**
- Validate server import and unexpected error fallback behavior in new namespace.

**Step 2: Run test to verify it fails**
- `pytest tests/test_server.py tests/test_server_import.py -q`

**Step 3: Write minimal implementation**
- Update server name/entrypoint and docs examples.

**Step 4: Run test to verify it passes**
- `pytest tests/test_server.py tests/test_server_import.py -q`

### Task 6: Full verification

**Files:**
- All touched files

**Step 1: Run tests**
- `pytest -q`

**Step 2: Run lint and typing**
- `ruff check .`
- `mypy src`

**Step 3: Build confidence checks**
- Validate README quickstart commands and env vars against code.

