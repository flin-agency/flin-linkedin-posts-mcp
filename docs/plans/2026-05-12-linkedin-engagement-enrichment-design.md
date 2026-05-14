# LinkedIn Engagement Enrichment Design

## Goal

Extend the MCP so it can enrich the authenticated member's exported LinkedIn posts with engagement data from official LinkedIn APIs when the app has the required scopes.

## Constraints

- The existing `memberSnapshotData` export remains the source of truth for historical post discovery.
- Engagement fields are not available in the portability export and must be fetched separately.
- LinkedIn access is scope-gated. The MCP must fail clearly when `socialMetadata` or `memberCreatorPostAnalytics` permissions are unavailable.
- The enriched tool must stay bounded. It should default to limited post counts and avoid unbounded fan-out.

## Chosen Approach

Use the exported post URLs and IDs to derive `urn:li:share:*` or `urn:li:ugcPost:*` values, then call two official endpoints:

- `socialMetadata` for comment totals and reaction summaries
- `memberCreatorPostAnalytics` for post analytics metrics such as impressions, reach, comments, reactions, and reshares

Build three tools on top:

1. `get_post_social_metadata`
2. `get_member_post_analytics`
3. `enrich_member_posts_with_engagement`

`enrich_member_posts_with_engagement` will reuse `list_member_posts`, extract URNs, fetch engagement details, and merge the results into a single post list. It will keep per-post errors local to each record so one permission or lookup failure does not discard all other posts.

## Alternatives Considered

### 1. Replace export-driven discovery with Posts API

Rejected for now. The current MCP already has stable post discovery via portability export. Requiring `r_member_social` for everything would increase setup cost without solving the engagement gap by itself.

### 2. Only implement analytics and skip social metadata

Rejected. Analytics scopes are likely harder to obtain, while `socialMetadata` can still provide useful reaction and comment counts. Splitting them gives a usable partial path.

### 3. Batch everything through a single enrichment endpoint

Rejected as the only public surface. Separate low-level tools are useful for debugging permissions and testing single posts before broad enrichment.

## API Surface

### `get_post_social_metadata`

Input:

- `post_urn` or `post_url`

Output:

- `entity_urn`
- `comments_count`
- `reactions_total`
- `reactions_by_type`
- `raw` optional only if needed later

### `get_member_post_analytics`

Input:

- `post_urn` or `post_url`
- `metric_types` optional subset

Output:

- `entity_urn`
- `metrics`
- `metrics_by_type`

### `enrich_member_posts_with_engagement`

Input:

- `published_after`
- `limit`
- `page_size`
- `include_social_metadata`
- `include_post_analytics`
- `analytics_metric_types`

Output:

- post list from `list_member_posts`
- `entity_urn`
- `engagement_available`
- `comments_count`
- `reactions_total`
- `reactions_by_type`
- analytics fields under `analytics`
- `engagement_errors`

## Error Handling

- Missing URN in a post record should not fail the whole enrichment call. Mark that post with `engagement_available=false` and an `engagement_errors` entry.
- LinkedIn permission errors from the APIs should propagate for the single-post tools.
- The bulk enrichment tool should capture per-post failures and keep processing remaining posts.

## Testing Strategy

- Client tests for URN normalization, `socialMetadata` requests, and `memberCreatorPostAnalytics` requests
- Tool tests for single-post metadata, single-post analytics, and merged enrichment
- Registry and guard tests for the three new tools
- Full repo test suite after implementation
