# LinkedIn analytics: activation after approval

Verified against the official documentation on 2026-11-21. Version 0.3.2 adds separate Portability and Community Management connections. Each app needs its own client ID and client secret for regular OAuth. Automated tests cover both connections; live analytics access must be verified after the member logs in.

## Which connection supplies which data?

| Connection | Product / permission | Data |
| --- | --- | --- |
| Portability | Member Data Portability (Member), `r_dma_portability_self_serve` | Own post content, dates and links |
| Analytics | Community Management, `r_member_postAnalytics` | Own post performance metrics |
| Analytics (optional) | Community Management, `r_member_profileAnalytics` | Own follower count and daily follower statistics |

`r_member_postAnalytics` does not grant the Posts API's member-content permission `r_member_social`. Keep the first connection for text. Use the same LinkedIn account for both logins; app-scoped IDs are not treated as a shared identity. LinkedIn enforces ownership on analytics lookups.

Member Snapshot requests use `Linkedin-Version: 202312`, the endpoint's only supported version. Marketing/analytics requests retain the supported `202610` version. Do not infer a new supported version solely from the calendar month. The next release should recheck the migration table.

## Application setup

Keep the existing Member Data Portability app. Community Management Development access is requested on a new app without other API products. Associate it with the actual organization's Page and have a Page super admin verify it. Do not reuse the special Portability Member default Page for the Community app.

LinkedIn reviews registered organizations and commercial use cases. Use the real legal name, address, business email, website and privacy policy. The submitted use case must accurately describe the local MCP, the host client and any cloud processing. The earlier draft's claim that all data stays local was incorrect for use through a cloud AI client. Storage and onward processing of Marketing API data must match the reviewed use case and applicable restrictions. This server has no persistent post/analytics database; host chat history is separate. Deleting a local token does not erase host history or revoke LinkedIn access remotely.

## Configuration after approval

Retain the original `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI` and `LINKEDIN_SCOPES` for portability. Add these separately:

```text
LINKEDIN_ANALYTICS_CLIENT_ID=<second app ID>
LINKEDIN_ANALYTICS_CLIENT_SECRET=<second app secret>
LINKEDIN_ANALYTICS_REDIRECT_URI=http://127.0.0.1:63142/callback
LINKEDIN_ANALYTICS_SCOPES=r_member_postAnalytics
LINKEDIN_API_VERSION=202610
```

For optional follower statistics, set `LINKEDIN_ANALYTICS_SCOPES=r_member_postAnalytics r_member_profileAnalytics` after confirming both scopes in the app Auth tab. In Claude Desktop use the new **Analytics app: permissions** field; blank retains post analytics only. Scope changes require a new analytics login.

Register the exact callback in the second app. Tokens default to distinct `tokens.json` and `tokens.analytics.json` files in the existing token directory. Never copy tokens between apps. Native PKCE is only an alternative if LinkedIn explicitly enables it for that app.

## Live acceptance test

1. Check the second app's Auth tab actually lists `r_member_postAnalytics` after approval.
2. Import the 0.3.2 MCPB once for the added configuration fields and automatic PyPI launcher, then restart the running server. Future stable server versions are loaded at startup. Publishing the server does not change a running session or an already-installed configuration form.
3. Run `auth_status {}`. This reports local credentials and expiry, not a successful API authorization check.
4. Run `login {"connection":"analytics"}` and consent using the same member as the portability login.
5. Run `get_member_analytics {"metric_types":["IMPRESSION"]}` for a one-request check without a post URN or portability token. Then run `get_member_post_analytics` with a known own post URN and `metric_types: ["IMPRESSION"]`.
6. Compare the result with the LinkedIn UI, allowing for timing and documented metric differences. Check the returned post reference and genuine zero versus unavailable values.
7. Run `enrich_member_posts_with_engagement {"limit":5}`. Confirm text is returned alongside metrics, and inspect every `engagement_errors` entry.
8. Test another post format and confirm the export supplies a usable `share`/`ugcPost` URN. A plain activity ID is not assumed to be the same identifier. If needed, use a confirmed URN for the individual lookup rather than guessing.

## Quota and supported features

Development currently allows 100 calls/member/day and 500 calls/app/day, with no BATCH_GET. It is intended for development/testing within twelve months; plan the Standard application for production.

The bulk default is five posts and five metrics (25 analytics calls). `max_api_calls` defaults to 50, at most 100, and includes engagement retries. It does not track daily usage across calls/processes and excludes portability and OAuth. Bulk requests to an endpoint stop on 401 or 403; a 429 stops further engagement requests across both endpoints. Other failures remain per-post errors; completed results are preserved.

Social metadata is disabled by default and requires its own permissions. If explicitly enabled, single GETs are used. Missing counters remain null, not zero.

The five default metrics are IMPRESSION, MEMBERS_REACHED, RESHARE, REACTION and COMMENT. Optional additional metrics are POST_SAVE, POST_SEND, LINK_CLICKS, PREMIUM_CTA_CLICKS, FOLLOWER_GAINED_FROM_CONTENT and PROFILE_VIEW_FROM_CONTENT. Single-post and aggregate-member metrics support lifetime totals, date ranges and daily series. Aggregate reach comes from LinkedIn directly, not a sum of post reach. Daily queries exclude MEMBERS_REACHED, LINK_CLICKS, FOLLOWER_GAINED_FROM_CONTENT and PROFILE_VIEW_FROM_CONTENT; single-post DAILY also excludes IMPRESSION. The defaults select only supported daily metrics; explicit unsupported combinations fail before making requests. `start_date` is inclusive, `end_date` exclusive. Both use YYYY-MM-DD. Daily responses preserve each data point and date range under `series_by_type`; totals retain `metrics_by_type`.

`get_member_follower_statistics` uses the optional `r_member_profileAnalytics` scope, returning lifetime count without dates or daily statistics with dates. It preserves the original API response under `statistics`; do not confuse daily changes with lifetime totals. Video-specific endpoints are not implemented.

Single-post and aggregate tools allow at most 50 HTTP attempts per invocation; follower statistics at most four. These include retries and stop immediately on 429. No live analytics token was present in the working environment at verification; automated HTTP tests do not establish live account access.

## Official sources

- [Community Management overview and new-app FAQ](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview?view=li-lms-2026-11)
- [Review requirements](https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review?view=li-lms-2026-11)
- [Member Post Statistics](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/post-statistics?view=li-lms-2026-11)
- [Member Follower Statistics](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/follower-statistics?view=li-lms-2026-11)
- [Posts API permissions](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-11)
- [Access tiers](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access?view=li-lms-2026-11)
- [Latest Marketing releases](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/recent-changes?view=li-lms-2026-11)
- [Migration table](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/migrations?view=li-lms-2026-11)
- [Member Snapshot version](https://learn.microsoft.com/en-us/linkedin/dma/member-data-portability/shared/member-snapshot-api)
- [Marketing data restrictions](https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-11)
- [Storage requirements](https://learn.microsoft.com/en-us/linkedin/marketing/data-storage-requirements?view=li-lms-2026-11)
