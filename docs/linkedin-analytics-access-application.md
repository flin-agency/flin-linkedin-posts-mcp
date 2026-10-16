# LinkedIn Analytics Access Application Prep

## Goal

Enable this MCP to fetch authenticated-member LinkedIn post analytics such as impressions, reach, reactions, comments, and shares/reshares.

The required LinkedIn product is **Community Management API**. The key scope for member post analytics is:

```text
r_member_postAnalytics
```

LinkedIn documents this scope as part of Community Management API and notes that it is supported in API versions starting from `202506`.
That initial Marketing API version is now retired. This project uses `202610` for analytics, the latest release as of October 16, 2026.
Member Snapshot requests independently use `202312`, the only version supported by that endpoint.

Official references:

- Getting access overview: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- Increasing access and permissions table: https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access
- Community Management app review: https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review
- Community Management integration requirements: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/integration-requirements-community-management

## Important Qualification Risk

LinkedIn currently says Community Management APIs are available only to registered legal organizations for commercial use cases. A purely personal/local hobby app may be rejected.

Before applying, prepare:

- Business email address, not a personal email.
- Registered legal organization name.
- Registered organization address.
- Organization website.
- Public privacy policy URL.
- LinkedIn Page associated with that organization.
- App verification by a super admin of that LinkedIn Page.
- App name that does not include LinkedIn or Microsoft marks.

## Where To Apply

1. Open https://www.linkedin.com/developers/apps
2. Select the LinkedIn app.
3. Go to **Products**.
4. Add/apply for **Community Management API**.
5. Complete the Development tier access request form.
6. After approval, rerun OAuth login with the new scope.

If a Standard tier form is required later, LinkedIn expects a downloadable screen recording demonstrating the app and the approved use case.

## Product / Use Case Draft

Use this as the basis for the application form.

```text
Product name:
Flin LinkedIn Posts Analytics MCP

Product overview:
Flin LinkedIn Posts Analytics MCP is a local analytics integration that helps an authenticated LinkedIn member understand the performance of their own LinkedIn posts. The user signs in through LinkedIn OAuth, grants consent, and the application retrieves only the user's own post metadata and post analytics to build a private reporting view.

Primary use case:
Read-only member post analytics for the authenticated member. The app combines the user's exported post/share records with LinkedIn member post analytics so the user can review post history, post text, publish dates, and aggregate performance metrics such as impressions, members reached, reactions, comments, and shares/reshares.

Business purpose:
The app supports internal content performance analysis and executive/employee advocacy reporting. It helps the authenticated user understand which topics, hashtags, and posting periods perform best, without scraping LinkedIn pages or reading data for unauthenticated members.

Requested scope:
r_member_postAnalytics

Existing related scope:
r_dma_portability_self_serve is used for the authenticated user's own Member Data Portability snapshot data, including post/share records. r_member_postAnalytics is requested only to add official analytics metrics for those same authenticated-member posts.

Data accessed:
- Authenticated member's own post URNs and post URLs
- Authenticated member's own post text and publish date from Member Data Portability data
- Aggregate post analytics: impressions, members reached, reactions, comments, shares/reshares

Data not accessed:
- No arbitrary LinkedIn member lookup
- No scraping
- No access to posts from unrelated authors
- No resale or onward transfer of LinkedIn data
- No advertising audience building
- No automated commenting, liking, or posting

User flow:
1. User starts the local MCP integration.
2. User signs in with LinkedIn OAuth and grants the requested scopes.
3. The app lists only the authenticated user's own exported posts.
4. The app derives each post URN and requests official LinkedIn post analytics for those posts.
5. The app displays/export metrics locally for the authenticated user.

Storage and retention:
OAuth tokens are stored locally on the user's machine. Post and analytics data are processed locally and are not sent to third-party services. Any optional CSV/JSON export is user initiated and remains on the user's device. Users can delete the local token through the logout tool.

Security and privacy controls:
The app uses OAuth 2.0, requests minimal read-only scopes for the use case, stores secrets outside source code through environment variables, handles permission errors explicitly, and respects LinkedIn API rate limits. Users can revoke access from LinkedIn and can remove the local token at any time.
```

## Privacy Policy Draft Points

Publish a real privacy policy on the organization's website before applying. It should cover at least:

```text
Data collected:
We collect LinkedIn data only after the user authenticates with LinkedIn and grants permission. The application may process the user's own LinkedIn post text, post URLs, publish dates, post URNs, and aggregate post analytics such as impressions, reach, reactions, comments, and shares.

Purpose:
The data is used only to provide private post performance analysis to the authenticated user.

Storage:
OAuth tokens and exported analytics are stored locally on the user's device unless the user explicitly exports or stores them elsewhere.

Sharing:
We do not sell LinkedIn data and do not share it with third parties.

Deletion:
Users can delete local tokens through the application logout function and can revoke app access in LinkedIn account settings.

Contact:
Provide a business contact email for privacy requests.
```

Have legal counsel review this before publishing.

## LinkedIn App Cleanup Before Applying

Before submitting an application:

1. Rotate any Client Secret that has been exposed.
2. Revoke/regenerate any access token that has been exposed.
3. Add a real privacy policy URL in the app settings.
4. Verify the app against the organization's LinkedIn Page.
5. Use a business email and organization-owned domain.

## MCP Configuration After Approval

After LinkedIn approves Community Management API access and the `r_member_postAnalytics` scope is available for the app, update the MCP environment:

```json
{
  "mcpServers": {
    "flin-linkedin-posts-mcp": {
      "command": "uv",
      "args": ["run", "flin-linkedin-posts-mcp"],
      "cwd": "/absolute/path/to/flin-linkedin-posts-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "<YOUR_LINKEDIN_CLIENT_ID>",
        "LINKEDIN_CLIENT_SECRET": "<YOUR_LINKEDIN_CLIENT_SECRET>",
        "LINKEDIN_REDIRECT_URI": "http://127.0.0.1:63141/callback",
        "LINKEDIN_SCOPES": "r_dma_portability_self_serve r_member_postAnalytics",
        "LINKEDIN_API_VERSION": "202610"
      }
    }
  }
}
```

Then restart the MCP host and run:

1. `logout`
2. `login`
3. `list_member_posts`
4. `get_member_post_analytics` with one known post URL/URN
5. `enrich_member_posts_with_engagement`

## Expected MCP Metrics

The existing MCP asks LinkedIn for these analytics metric types:

```text
IMPRESSION
MEMBERS_REACHED
RESHARE
REACTION
COMMENT
```

If access is approved and the token includes `r_member_postAnalytics`, the tool `get_member_post_analytics` should return `metrics_by_type` for a single post, and `enrich_member_posts_with_engagement` should merge those metrics into post records.

## If LinkedIn Rejects The Request

Fallback options:

- Continue using Member Data Portability for post content, dates, links, hashtags, mentions, and post-count analysis.
- Use LinkedIn's native UI manually for impressions/engagement metrics.
- Apply again only after meeting LinkedIn's business, organization, page verification, privacy policy, and commercial-use requirements.
