from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class LinkedInPostsSettings:
    client_id: str | None
    scopes: tuple[str, ...]
    api_version: str
    restli_protocol_version: str
    timeout_seconds: float
    max_retries: int
    oauth_timeout_seconds: float
    token_file: Path


def load_config(env: Mapping[str, str] | None = None) -> LinkedInPostsSettings:
    source = os.environ if env is None else env
    scopes = tuple(scope for scope in source.get("LINKEDIN_SCOPES", "r_dma_portability_3rd_party").split() if scope)
    token_file = Path(
        source.get(
            "LINKEDIN_TOKEN_FILE",
            str(Path.home() / ".flin-linkedin-posts-mcp" / "tokens.json"),
        )
    )

    return LinkedInPostsSettings(
        client_id=source.get("LINKEDIN_CLIENT_ID") or None,
        scopes=scopes,
        api_version=source.get("LINKEDIN_API_VERSION", "202312"),
        restli_protocol_version=source.get("LINKEDIN_RESTLI_PROTOCOL_VERSION", "2.0.0"),
        timeout_seconds=float(source.get("LINKEDIN_TIMEOUT_SECONDS", "30")),
        max_retries=int(source.get("LINKEDIN_MAX_RETRIES", "3")),
        oauth_timeout_seconds=float(source.get("LINKEDIN_OAUTH_TIMEOUT_SECONDS", "300")),
        token_file=token_file,
    )
