from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from typing import Any, Callable, Mapping
import re

from ..auth import TokenStore, load_valid_token, run_local_oauth_login, token_status_payload
from ..config import LinkedInPostsSettings
from ..linkedin_client import LinkedInClient
from .common import build_entity_response, build_ok_response

MEMBER_SHARE_INFO_DOMAIN = "MEMBER_SHARE_INFO"
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'-]{2,}")
STOPWORDS = {
    "aber", "alle", "auch", "auf", "aus", "bei", "bin", "das", "dass", "dem", "den", "der", "des",
    "die", "ein", "eine", "einer", "einem", "einen", "er", "es", "for", "from", "has", "have", "ich",
    "ihr", "ihre", "im", "in", "ist", "mit", "nicht", "oder", "sie", "sind", "the", "und", "was",
    "wer", "wie", "wir", "you", "your", "zum", "zur",
}


def auth_status(*, client: Any | None, settings: LinkedInPostsSettings, arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments:
        raise ValueError("auth_status does not accept arguments")
    record = TokenStore(settings.token_file).load()
    return build_entity_response(
        payload=token_status_payload(settings, record),
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def login(*, client: Any | None, settings: LinkedInPostsSettings, arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments:
        raise ValueError("login does not accept arguments")
    record = run_local_oauth_login(settings)
    return build_entity_response(
        payload=token_status_payload(settings, record),
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def logout(*, client: Any | None, settings: LinkedInPostsSettings, arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments:
        raise ValueError("logout does not accept arguments")
    TokenStore(settings.token_file).clear()
    return build_entity_response(
        payload=token_status_payload(settings, None),
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def list_snapshot_domains(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    page_size = _as_int(arguments.get("page_size"), parameter_name="page_size", default=100, minimum=1, maximum=100)

    def collect(runtime_client: Any) -> list[dict[str, Any]]:
        counts: Counter[str] = Counter()
        for element in runtime_client.iter_member_snapshot_elements(domain=None, page_size=page_size):
            domain = element.get("snapshotDomain") if isinstance(element, Mapping) else None
            if not isinstance(domain, str) or not domain:
                continue
            snapshot_data = element.get("snapshotData")
            counts[domain] += len(snapshot_data) if isinstance(snapshot_data, list) else 0
        return [{"domain": domain, "count": count} for domain, count in sorted(counts.items())]

    data = _with_linkedin_client(client=client, settings=settings, callback=collect)
    return build_ok_response(
        data=data,
        next_after=None,
        has_next=False,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def list_member_posts(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    include_raw = _as_bool(arguments.get("include_raw"), parameter_name="include_raw", default=False)
    page_size = _as_int(arguments.get("page_size"), parameter_name="page_size", default=100, minimum=1, maximum=100)

    def collect(runtime_client: Any) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        for element in runtime_client.iter_member_snapshot_elements(domain=MEMBER_SHARE_INFO_DOMAIN, page_size=page_size):
            if element.get("snapshotDomain") != MEMBER_SHARE_INFO_DOMAIN:
                continue
            posts.extend(_posts_from_snapshot_element(element, include_raw=include_raw))
        posts.sort(key=lambda post: post.get("published_at") or "", reverse=True)
        return posts

    posts = _with_linkedin_client(client=client, settings=settings, callback=collect)
    return build_ok_response(
        data=posts,
        next_after=None,
        has_next=False,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def analyze_member_posts(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    include_posts = _as_bool(arguments.get("include_posts"), parameter_name="include_posts", default=True)
    top_n = _as_int(arguments.get("top_n"), parameter_name="top_n", default=10, minimum=1, maximum=25)
    published_after = arguments.get("published_after")
    published_after_date = date.fromisoformat(published_after) if published_after is not None else None

    listing = list_member_posts(
        client=client,
        settings=settings,
        arguments={
            "page_size": arguments.get("page_size", 100),
            "include_raw": False,
        },
    )
    posts = listing["data"]
    if published_after_date is not None:
        posts = [post for post in posts if (post_date := _post_date(post)) is None or post_date >= published_after_date]

    texts = [post.get("text") or "" for post in posts]
    hashtags = Counter(tag.lower() for post in posts for tag in post.get("hashtags", []))
    mentions = Counter(mention.lower() for post in posts for mention in post.get("mentions", []))
    words = Counter(word.lower() for text in texts for word in WORD_RE.findall(text) if word.lower() not in STOPWORDS)

    enriched: dict[str, Any] = {
        "snapshot_domain": MEMBER_SHARE_INFO_DOMAIN,
        "post_count": len(posts),
        "posts_with_text": sum(1 for text in texts if text.strip()),
        "average_text_length": round(sum(len(text.strip()) for text in texts) / len(posts), 2) if posts else 0,
        "average_hashtag_count": round(sum(len(post.get("hashtags", [])) for post in posts) / len(posts), 2) if posts else 0,
        "top_hashtags": [{"value": key, "count": count} for key, count in hashtags.most_common(top_n)],
        "top_mentions": [{"value": key, "count": count} for key, count in mentions.most_common(top_n)],
        "top_terms": [{"value": key, "count": count} for key, count in words.most_common(top_n)],
    }
    if include_posts:
        enriched["posts"] = posts
    return build_entity_response(
        payload=enriched,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def _with_linkedin_client(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    callback: Callable[[Any], Any],
) -> Any:
    if client is not None:
        return callback(client)
    token = load_valid_token(settings)
    runtime_client = LinkedInClient(
        access_token=token.access_token,
        api_version=settings.api_version,
        restli_protocol_version=settings.restli_protocol_version,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    try:
        return callback(runtime_client)
    finally:
        runtime_client.close()


def _posts_from_snapshot_element(element: Mapping[str, Any], *, include_raw: bool) -> list[dict[str, Any]]:
    snapshot_data = element.get("snapshotData")
    if not isinstance(snapshot_data, list):
        return []
    posts: list[dict[str, Any]] = []
    for item in snapshot_data:
        if isinstance(item, Mapping):
            posts.append(_normalize_snapshot_post(item, include_raw=include_raw))
    return posts


def _normalize_snapshot_post(data: Mapping[str, Any], *, include_raw: bool) -> dict[str, Any]:
    raw = dict(data)
    text = _extract_text(raw)
    published_at = _normalize_datetime(_first_value(raw, "Date", "Created Date", "Creation Date", "Created Time", "createdAt", "publishedAt"))
    normalized: dict[str, Any] = {
        "post_id": _first_str(raw, "ShareId", "shareId", "id", "urn", "Activity URN"),
        "text": text,
        "hashtags": _extract_hashtags(text),
        "mentions": _extract_mentions(text),
        "published_at": published_at,
        "url": _first_str(raw, "ShareLink", "URL", "Url", "Permalink", "permalink"),
        "visibility": _first_str(raw, "Visibility", "visibility"),
        "media_urls": _extract_media_urls(raw),
    }
    if include_raw:
        normalized["raw"] = raw
    return normalized


def _extract_text(data: Mapping[str, Any]) -> str | None:
    for path in (
        ("ShareCommentary",),
        ("Commentary",),
        ("Text",),
        ("Content",),
        ("Message",),
        ("commentary", "text"),
        ("commentary",),
        ("text",),
    ):
        value = _extract_nested_str(data, path)
        if value:
            return value
    return None


def _first_value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _first_str(data: Mapping[str, Any], *keys: str) -> str | None:
    value = _first_value(data, *keys)
    return str(value).strip() if value is not None and str(value).strip() else None


def _extract_nested_str(data: Any, path: tuple[str, ...]) -> str | None:
    current = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    if isinstance(current, str) and current.strip():
        return current.strip()
    return None


def _normalize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        timestamp = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")
    if not isinstance(value, str):
        return str(value)
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith(" UTC"):
        cleaned = f"{cleaned[:-4]}+00:00"
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        return f"{cleaned}T00:00:00Z"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        match = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", cleaned)
        if not match:
            return value.strip()
        parsed = datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}+00:00")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _extract_media_urls(data: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(data, Mapping):
        for nested in data.values():
            urls.extend(_extract_media_urls(nested))
    elif isinstance(data, list):
        for item in data:
            urls.extend(_extract_media_urls(item))
    elif isinstance(data, str) and data.startswith(("https://", "http://")):
        urls.append(data)
    return list(dict.fromkeys(urls))


def _extract_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(match.group(1) for match in re.finditer(r"#([\w-]+)", text)))


def _extract_mentions(text: str | None) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(match.group(1) for match in re.finditer(r"@([\w.-]+)", text)))


def _post_date(post: Mapping[str, Any]) -> date | None:
    published_at = post.get("published_at")
    if not isinstance(published_at, str):
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", published_at)
    if match:
        return date.fromisoformat(match.group(1))
    return None


def _as_bool(value: Any, *, parameter_name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{parameter_name} must be a boolean")
    return value


def _as_int(value: Any, *, parameter_name: str, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError(f"{parameter_name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{parameter_name} must be between {minimum} and {maximum}")
    return value
