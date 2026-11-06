"""Keep credentials out of upstream error details returned to an MCP host."""
from __future__ import annotations

from typing import Any

_SECRET_KEYS = {"access_token", "refresh_token", "client_secret", "code", "code_verifier", "authorization"}


def redact(value: Any, *secrets: str | None) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).lower() in _SECRET_KEYS else redact(item, *secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, *secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
    return value
