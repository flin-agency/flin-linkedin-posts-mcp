from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Mapping
from urllib.parse import quote
import re

from ..config import LinkedInPostsSettings
from ..linkedin_client import LinkedInClient
from .common import build_entity_response, build_ok_response

MEMBER_URN_RE = re.compile(r"^urn:li:person:[A-Za-z0-9_-]+$")
POST_URN_RE = re.compile(r"^urn:li:(?:share|ugcPost|post):[A-Za-z0-9_-]+$")
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'-]{2,}")
STOPWORDS = {
    "aber", "alle", "auch", "auf", "aus", "bei", "bin", "das", "dass", "dem", "den", "der", "des",
    "die", "ein", "eine", "einer", "einem", "einen", "er", "es", "for", "from", "has", "have", "ich",
    "ihr", "ihre", "im", "in", "ist", "mit", "nicht", "oder", "sie", "sind", "the", "und", "was",
    "wer", "wie", "wir", "you", "your", "zum", "zur",
}


def get_member_profile(*, client: LinkedInClient, settings: LinkedInPostsSettings, arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments:
        raise ValueError("get_member_profile does not accept arguments")
    payload = _get_member_profile_payload(client)
    normalized = _normalize_member_profile(payload)
    return build_entity_response(payload=normalized, api_version=settings.api_version, request_id=getattr(client, "last_request_id", None))


def list_member_posts(*, client: LinkedInClient, settings: LinkedInPostsSettings, arguments: dict[str, Any]) -> dict[str, Any]:
    include_raw = _as_bool(arguments.get("include_raw"), parameter_name="include_raw", default=False)
    page_size = _as_int(arguments.get("page_size"), parameter_name="page_size", default=25, minimum=1, maximum=100)
    author_urn = _resolve_author_urn(client=client, author_urn=arguments.get("author_urn"))
    params: dict[str, Any] = {"q": "author", "author": author_urn, "count": page_size}
    if arguments.get("page_token"):
        params["start"] = arguments["page_token"]
    payload = client.get_json("posts", params=params)
    elements = payload.get("elements", []) if isinstance(payload, Mapping) else []
    posts = [_normalize_post(item, include_raw=include_raw) for item in elements if isinstance(item, Mapping)]
    paging = payload.get("paging", {}) if isinstance(payload, Mapping) else {}
    next_token = _next_page_token(paging, page_size=page_size)
    return build_ok_response(data=posts, next_after=next_token, has_next=bool(next_token), api_version=settings.api_version, request_id=getattr(client, "last_request_id", None))


def get_post(*, client: LinkedInClient, settings: LinkedInPostsSettings, arguments: dict[str, Any]) -> dict[str, Any]:
    post_urn = _normalize_post_urn(arguments["post_urn"], parameter_name="post_urn")
    include_raw = _as_bool(arguments.get("include_raw"), parameter_name="include_raw", default=False)
    encoded = quote(post_urn, safe="")
    payload = client.get_json(f"posts/{encoded}", params={})
    normalized = _normalize_post(payload, include_raw=include_raw)
    return build_entity_response(payload=normalized, api_version=settings.api_version, request_id=getattr(client, "last_request_id", None))


def analyze_member_posts(*, client: LinkedInClient, settings: LinkedInPostsSettings, arguments: dict[str, Any]) -> dict[str, Any]:
    include_posts = _as_bool(arguments.get("include_posts"), parameter_name="include_posts", default=True)
    top_n = _as_int(arguments.get("top_n"), parameter_name="top_n", default=10, minimum=1, maximum=25)
    published_after = arguments.get("published_after")
    if published_after is not None:
        published_after_date = date.fromisoformat(published_after)
    else:
        published_after_date = None

    listing = list_member_posts(client=client, settings=settings, arguments={
        "author_urn": arguments.get("author_urn"),
        "page_size": arguments.get("page_size", 25),
        "page_token": arguments.get("page_token"),
        "include_raw": False,
    })
    posts = listing["data"]
    if published_after_date is not None:
        posts = [post for post in posts if _post_date(post) is None or _post_date(post) >= published_after_date]

    texts = [post.get("text") or "" for post in posts]
    hashtags = Counter(tag.lower() for post in posts for tag in post.get("hashtags", []))
    mentions = Counter(mention.lower() for post in posts for mention in post.get("mentions", []))
    words = Counter(word.lower() for text in texts for word in WORD_RE.findall(text) if word.lower() not in STOPWORDS)

    enriched = {
        "author_urn": posts[0].get("author_urn") if posts else arguments.get("author_urn"),
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
    return build_entity_response(payload=enriched, api_version=settings.api_version, request_id=getattr(client, "last_request_id", None))


def _resolve_author_urn(*, client: LinkedInClient, author_urn: Any) -> str:
    if author_urn is not None:
        return _normalize_member_urn(author_urn, parameter_name="author_urn")
    payload = _get_member_profile_payload(client)
    return _normalize_member_profile(payload)["member_urn"]


def _get_member_profile_payload(client: LinkedInClient) -> Mapping[str, Any]:
    payload = client.get_json_url("https://api.linkedin.com/v2/userinfo")
    if not isinstance(payload, Mapping):
        raise ValueError("LinkedIn userinfo response must be an object")
    return payload


def _normalize_member_profile(payload: Mapping[str, Any]) -> dict[str, Any]:
    member_id = str(payload.get("sub") or "").strip()
    if not member_id:
        raise ValueError("LinkedIn userinfo response did not include sub")
    return {
        "member_urn": f"urn:li:person:{member_id}",
        "member_id": member_id,
        "name": payload.get("name"),
        "given_name": payload.get("given_name"),
        "family_name": payload.get("family_name"),
        "locale": payload.get("locale"),
        "email": payload.get("email"),
        "email_verified": payload.get("email_verified"),
    }


def _normalize_post(value: Mapping[str, Any], *, include_raw: bool) -> dict[str, Any]:
    data = dict(value)
    text = _extract_text(data)
    normalized = {
        "post_urn": _first_str(data, "id", "urn"),
        "author_urn": _first_str(data, "author"),
        "text": text,
        "hashtags": _extract_hashtags(text),
        "mentions": _extract_mentions(text),
        "published_at": _extract_published_at(data),
        "visibility": _extract_nested_str(data, ("visibility", "com.linkedin.ugc.MemberNetworkVisibility")),
        "commentary": data.get("commentary"),
        "lifecycle_state": _first_str(data, "lifecycleState"),
        "media_urls": _extract_media_urls(data),
    }
    if include_raw:
        normalized["raw"] = data
    return normalized


def _extract_text(data: Mapping[str, Any]) -> str | None:
    for path in (("commentary", "text"), ("shareCommentary", "text"), ("text",), ("commentary",)):
        value = _extract_nested_str(data, path)
        if value:
            return value
    return None


def _extract_published_at(data: Mapping[str, Any]) -> str | None:
    for key in ("publishedAt", "publishedAtTimestamp", "createdAt"):
        value = data.get(key)
        if value is None:
            continue
        return str(value)
    return None


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


def _first_str(data: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_nested_str(data: Any, path: tuple[str, ...]) -> str | None:
    current = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    if isinstance(current, str) and current.strip():
        return current.strip()
    return None


def _extract_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(match.group(1) for match in re.finditer(r"#([\w-]+)", text)))


def _extract_mentions(text: str | None) -> list[str]:
    if not text:
        return []
    return list(dict.fromkeys(match.group(1) for match in re.finditer(r"@([\w.-]+)", text)))


def _next_page_token(paging: Any, *, page_size: int) -> str | None:
    if not isinstance(paging, Mapping):
        return None
    start = paging.get("start")
    total = paging.get("total")
    count = paging.get("count", page_size)
    if isinstance(start, int) and isinstance(total, int) and start + int(count) < total:
        return str(start + int(count))
    return None


def _post_date(post: Mapping[str, Any]) -> date | None:
    published_at = post.get("published_at")
    if not isinstance(published_at, str):
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", published_at)
    if match:
        return date.fromisoformat(match.group(1))
    return None


def _normalize_member_urn(value: Any, *, parameter_name: str) -> str:
    if not isinstance(value, str) or not MEMBER_URN_RE.fullmatch(value.strip()):
        raise ValueError(f"{parameter_name} must be a LinkedIn member URN like urn:li:person:abc123")
    return value.strip()


def _normalize_post_urn(value: Any, *, parameter_name: str) -> str:
    if not isinstance(value, str) or not POST_URN_RE.fullmatch(value.strip()):
        raise ValueError(f"{parameter_name} must be a LinkedIn post URN like urn:li:share:123")
    return value.strip()


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
