from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote

from ..config import LinkedInAdsSettings
from ..errors import LinkedInValidationError
from ..linkedin_client import LinkedInClient
from .common import build_entity_response, normalize_share_urn


def get_share_content(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    share_urn = normalize_share_urn(arguments["share_urn"], parameter_name="share_urn")
    include_raw = _normalize_include_raw(arguments.get("include_raw"))

    payload, source_endpoint = _fetch_share_payload(client=client, share_urn=share_urn)
    text = _extract_text(payload)
    image_urls, thumbnail_urls = _extract_image_urls(payload)

    response_payload: dict[str, Any] = {
        "share_urn": share_urn,
        "source_endpoint": source_endpoint,
        "post_url": f"https://www.linkedin.com/feed/update/{share_urn}",
        "text": text,
        "image_url": image_urls[0] if image_urls else None,
        "image_urls": image_urls,
        "thumbnail_urls": thumbnail_urls,
    }

    if include_raw:
        response_payload["raw"] = payload

    return build_entity_response(
        payload=response_payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def _normalize_include_raw(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError("include_raw must be a boolean")
    return value


def _fetch_share_payload(*, client: LinkedInClient, share_urn: str) -> tuple[dict[str, Any], str]:
    encoded_share_urn = quote(share_urn, safe="")
    last_validation_error: LinkedInValidationError | None = None

    for endpoint in ("shares", "posts"):
        path = f"{endpoint}/{encoded_share_urn}"
        try:
            payload = client.get_json(path, params={})
        except LinkedInValidationError as exc:
            last_validation_error = exc
            continue

        if isinstance(payload, Mapping):
            return dict(payload), endpoint
        return {}, endpoint

    if last_validation_error is not None:
        raise last_validation_error
    raise RuntimeError("Unable to resolve share content")


def _extract_text(payload: Mapping[str, Any]) -> str | None:
    for path in (
        ("commentary", "text"),
        ("specificContent", "com.linkedin.ugc.ShareContent", "shareCommentary", "text"),
        ("shareCommentary", "text"),
        ("text",),
    ):
        candidate = _nested_value(payload, path)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _nested_value(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _extract_image_urls(payload: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    image_urls: list[str] = []
    thumbnail_urls: list[str] = []
    _collect_image_urls(
        payload,
        image_urls=image_urls,
        thumbnail_urls=thumbnail_urls,
        parent_key=None,
        thumbnail_context=False,
    )
    return image_urls, thumbnail_urls


def _collect_image_urls(
    value: Any,
    *,
    image_urls: list[str],
    thumbnail_urls: list[str],
    parent_key: str | None,
    thumbnail_context: bool,
) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_name = str(key).lower()
            nested_thumbnail_context = thumbnail_context or any(
                token in key_name for token in ("thumbnail", "thumb", "poster")
            )
            _collect_image_urls(
                nested_value,
                image_urls=image_urls,
                thumbnail_urls=thumbnail_urls,
                parent_key=key_name,
                thumbnail_context=nested_thumbnail_context,
            )
        return

    if isinstance(value, list):
        for item in value:
            _collect_image_urls(
                item,
                image_urls=image_urls,
                thumbnail_urls=thumbnail_urls,
                parent_key=parent_key,
                thumbnail_context=thumbnail_context,
            )
        return

    if not isinstance(value, str):
        return

    candidate = value.strip()
    if not _looks_like_image_url(candidate):
        return

    if thumbnail_context or (parent_key and any(token in parent_key for token in ("thumbnail", "thumb", "poster"))):
        _append_unique(thumbnail_urls, candidate)

    _append_unique(image_urls, candidate)


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _looks_like_image_url(value: str) -> bool:
    lower = value.lower()
    if not lower.startswith(("https://", "http://")):
        return False

    without_query = lower.split("?", 1)[0]
    if without_query.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".svg")):
        return True
    if "media.licdn.com" in lower:
        return True
    if "/dms/image/" in lower:
        return True
    return False
