from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping


@dataclass(frozen=True, slots=True)
class LinkedInAdsSettings:
    access_token: str
    api_version: str
    restli_protocol_version: str
    timeout_seconds: float
    max_retries: int


def load_config(env: Mapping[str, str] | None = None) -> LinkedInAdsSettings:
    source = os.environ if env is None else env
    access_token = source.get("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        raise ValueError("LINKEDIN_ACCESS_TOKEN is required")

    return LinkedInAdsSettings(
        access_token=access_token,
        api_version=source.get("LINKEDIN_API_VERSION", "202603"),
        restli_protocol_version=source.get("LINKEDIN_RESTLI_PROTOCOL_VERSION", "2.0.0"),
        timeout_seconds=float(source.get("LINKEDIN_TIMEOUT_SECONDS", "30")),
        max_retries=int(source.get("LINKEDIN_MAX_RETRIES", "3")),
    )
