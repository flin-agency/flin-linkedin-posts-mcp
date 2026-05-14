# LinkedIn Engagement Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add official LinkedIn engagement lookups and an enrichment workflow for exported member posts.

**Architecture:** Keep post discovery on `memberSnapshotData`, derive post URNs from exported URLs and IDs, call `socialMetadata` and `memberCreatorPostAnalytics`, then merge those results back into exported posts. Keep bulk enrichment bounded with explicit limits and per-post error capture.

**Tech Stack:** Python 3.11, `httpx`, MCP Python SDK, `pytest`, `respx`

---

### Task 1: Client Request Coverage

**Files:**
- Modify: `tests/test_linkedin_client.py`
- Modify: `src/flin_linkedin_posts_mcp/linkedin_client.py`

**Steps:**

1. Write failing tests for URN extraction from `urn:li:share:*`, `urn:li:ugcPost:*`, and encoded LinkedIn feed URLs.
2. Run the targeted client tests and verify failure.
3. Implement minimal URN parsing helpers in `linkedin_client.py`.
4. Write failing tests for `socialMetadata` and `memberCreatorPostAnalytics` requests.
5. Run the targeted client tests and verify failure.
6. Implement minimal client helpers for `get_social_metadata` and `get_member_post_analytics`.
7. Run `pytest -q tests/test_linkedin_client.py`.

### Task 2: Tool-Level Engagement Handlers

**Files:**
- Modify: `tests/test_member_posts.py`
- Modify: `src/flin_linkedin_posts_mcp/tools/member_posts.py`

**Steps:**

1. Write failing tests for `get_post_social_metadata`.
2. Run the targeted tests and verify failure.
3. Implement the minimal tool handler and normalization.
4. Write failing tests for `get_member_post_analytics`.
5. Run the targeted tests and verify failure.
6. Implement the minimal analytics handler and normalization.
7. Run `pytest -q tests/test_member_posts.py`.

### Task 3: Bulk Enrichment

**Files:**
- Modify: `tests/test_member_posts.py`
- Modify: `src/flin_linkedin_posts_mcp/tools/member_posts.py`

**Steps:**

1. Write failing tests for `enrich_member_posts_with_engagement`, including per-post errors and selective toggles.
2. Run the targeted tests and verify failure.
3. Implement the merge logic with explicit limits and error capture.
4. Run `pytest -q tests/test_member_posts.py`.

### Task 4: MCP Wiring

**Files:**
- Modify: `src/flin_linkedin_posts_mcp/tool_registry.py`
- Modify: `src/flin_linkedin_posts_mcp/dispatcher.py`
- Modify: `src/flin_linkedin_posts_mcp/guards.py`
- Modify: `tests/test_tool_registry.py`
- Modify: `tests/test_guards.py`

**Steps:**

1. Write failing registry and guard expectations for the new tools.
2. Run the targeted tests and verify failure.
3. Implement the tool specs, dispatcher entries, and guard updates.
4. Run `pytest -q tests/test_tool_registry.py tests/test_guards.py`.

### Task 5: Documentation And Verification

**Files:**
- Modify: `README.md`

**Steps:**

1. Document the new tools, their required scopes, and the partial-failure behavior.
2. Run `ruff check .`.
3. Run `mypy src`.
4. Run `pytest -q`.
