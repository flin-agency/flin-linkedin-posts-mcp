from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
from typing import Mapping


DEFAULT_API_VERSION = "202610"
MEMBER_SNAPSHOT_API_VERSION = "202312"
MEMBER_ANALYTICS_SCOPES = frozenset({"r_member_postAnalytics", "r_member_profileAnalytics"})


@dataclass(frozen=True, slots=True)
class LinkedInPostsSettings:
    client_id: str | None
    client_secret: str | None
    oauth_flow: str
    redirect_uri: str | None
    scopes: tuple[str, ...]
    api_version: str
    restli_protocol_version: str
    timeout_seconds: float
    max_retries: int
    oauth_timeout_seconds: float
    token_file: Path
    analytics: LinkedInPostsSettings | None = None
    connection_name: str = "portability"

    def for_connection(self, connection: str) -> LinkedInPostsSettings:
        if connection == "portability":
            return self
        if connection != "analytics":
            raise ValueError("connection must be portability or analytics")
        if self.analytics is not None:
            return self.analytics
        # Preserve approved single-app installations; never silently send a
        # portability-only token to the analytics API.
        if MEMBER_ANALYTICS_SCOPES.intersection(self.scopes):
            return self
        raise ValueError(
            "Analytics connection is not configured. Set LINKEDIN_ANALYTICS_CLIENT_ID, "
            "LINKEDIN_ANALYTICS_CLIENT_SECRET and LINKEDIN_ANALYTICS_REDIRECT_URI, "
            "then run login with connection='analytics' after LinkedIn approval."
        )


def load_config(env: Mapping[str, str] | None = None) -> LinkedInPostsSettings:
    source = os.environ if env is None else env
    client_secret = source.get("LINKEDIN_CLIENT_SECRET") or None
    oauth_flow = source.get("LINKEDIN_OAUTH_FLOW")
    if oauth_flow is None:
        oauth_flow = "authorization_code" if client_secret else "native_pkce"
    oauth_flow = oauth_flow.strip().lower().replace("-", "_")
    scopes = tuple(scope for scope in source.get("LINKEDIN_SCOPES", "r_dma_portability_self_serve").split() if scope)
    token_file = Path(
        source.get(
            "LINKEDIN_TOKEN_FILE",
            str(Path.home() / ".flin-linkedin-posts-mcp" / "tokens.json"),
        )
    )

    settings = LinkedInPostsSettings(
        client_id=source.get("LINKEDIN_CLIENT_ID") or None,
        client_secret=client_secret,
        oauth_flow=oauth_flow,
        redirect_uri=source.get("LINKEDIN_REDIRECT_URI") or None,
        scopes=scopes,
        api_version=source.get("LINKEDIN_API_VERSION", DEFAULT_API_VERSION),
        restli_protocol_version=source.get("LINKEDIN_RESTLI_PROTOCOL_VERSION", "2.0.0"),
        timeout_seconds=float(source.get("LINKEDIN_TIMEOUT_SECONDS", "30")),
        max_retries=int(source.get("LINKEDIN_MAX_RETRIES", "3")),
        oauth_timeout_seconds=float(source.get("LINKEDIN_OAUTH_TIMEOUT_SECONDS", "300")),
        token_file=token_file,
    )
    analytics_values = {
        key.removeprefix("LINKEDIN_ANALYTICS_"): value.strip()
        for key, value in source.items()
        if key.startswith("LINKEDIN_ANALYTICS_") and value.strip()
    }
    if not analytics_values:
        return settings
    if not analytics_values.get("CLIENT_ID"):
        raise ValueError("LINKEDIN_ANALYTICS_CLIENT_ID is required for the analytics connection")
    analytics_token_file = Path(analytics_values.get(
        "TOKEN_FILE", str(token_file.with_name(f"{token_file.stem}.analytics{token_file.suffix}"))
    ))
    if (analytics_token_file.resolve() == token_file.resolve() or (
        analytics_token_file.exists() and token_file.exists() and analytics_token_file.samefile(token_file)
    )):
        raise ValueError("Portability and analytics must use different token files")
    secret = analytics_values.get("CLIENT_SECRET") or None
    analytics = replace(
        settings,
        client_id=analytics_values["CLIENT_ID"],
        client_secret=secret,
        oauth_flow=analytics_values.get("OAUTH_FLOW", "authorization_code" if secret else "native_pkce")
        .lower().replace("-", "_"),
        redirect_uri=analytics_values.get("REDIRECT_URI") or None,
        scopes=tuple(analytics_values.get("SCOPES", "r_member_postAnalytics").split()),
        token_file=analytics_token_file,
        connection_name="analytics",
    )
    return replace(settings, analytics=analytics)
