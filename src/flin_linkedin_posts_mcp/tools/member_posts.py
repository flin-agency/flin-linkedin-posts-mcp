from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from typing import Any, Callable, Mapping
import re

from ..auth import TokenStore, load_valid_token, run_local_oauth_login, token_status_payload
from ..config import LinkedInPostsSettings
from ..errors import LinkedInPostsError
from ..linkedin_client import LinkedInClient, normalize_post_urn
from .common import build_entity_response, build_ok_response

MEMBER_SHARE_INFO_DOMAIN = "MEMBER_SHARE_INFO"
ANALYTICS_METRIC_TYPES = ("IMPRESSION", "MEMBERS_REACHED", "RESHARE", "REACTION", "COMMENT")
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
    limit = _as_optional_int(arguments.get("limit"), parameter_name="limit", minimum=1, maximum=500)
    published_after = arguments.get("published_after")
    published_after_date = date.fromisoformat(published_after) if published_after is not None else None

    def collect(runtime_client: Any) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        for element in runtime_client.iter_member_snapshot_elements(domain=MEMBER_SHARE_INFO_DOMAIN, page_size=page_size):
            if element.get("snapshotDomain") != MEMBER_SHARE_INFO_DOMAIN:
                continue
            posts.extend(_posts_from_snapshot_element(element, include_raw=include_raw))
        posts.sort(key=lambda post: post.get("published_at") or "", reverse=True)
        return _filter_posts(posts, published_after_date=published_after_date, limit=limit)

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
    post_limit = _as_optional_int(arguments.get("post_limit"), parameter_name="post_limit", minimum=1, maximum=500)
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
        included_posts = posts[:post_limit] if post_limit is not None else posts
        enriched["included_post_count"] = len(included_posts)
        enriched["posts"] = included_posts
    return build_entity_response(
        payload=enriched,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def match_drafts_to_member_posts(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    drafts = arguments.get("drafts")
    if not isinstance(drafts, list) or not drafts:
        raise ValueError("drafts must be a non-empty array of strings")
    normalized_drafts: list[str] = []
    for draft in drafts:
        if not isinstance(draft, str) or not draft.strip():
            raise ValueError("drafts must contain only non-empty strings")
        normalized_drafts.append(draft.strip())

    max_matches_per_draft = _as_int(
        arguments.get("max_matches_per_draft"),
        parameter_name="max_matches_per_draft",
        default=3,
        minimum=1,
        maximum=10,
    )

    listing = list_member_posts(
        client=client,
        settings=settings,
        arguments={
            "page_size": arguments.get("page_size", 100),
            "published_after": arguments.get("published_after"),
            "limit": arguments.get("post_limit"),
            "include_raw": False,
        },
    )
    posts = listing["data"]

    matches: list[dict[str, Any]] = []
    for draft in normalized_drafts:
        scored_posts = sorted(
            (
                {
                    "post_id": post.get("post_id"),
                    "published_at": post.get("published_at"),
                    "url": post.get("url"),
                    "text": post.get("text"),
                    "similarity": _similarity(draft, post.get("text")),
                }
                for post in posts
            ),
            key=lambda item: item["similarity"],
            reverse=True,
        )
        matches.append(
            {
                "draft": draft,
                "matches": scored_posts[:max_matches_per_draft],
            }
        )

    return build_ok_response(
        data=matches,
        next_after=None,
        has_next=False,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def get_post_social_metadata(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    entity_urn = _resolve_post_urn(arguments)

    def collect(runtime_client: Any) -> dict[str, Any]:
        return _normalize_social_metadata_payload(runtime_client.get_social_metadata(entity_urn))

    payload = _with_linkedin_client(client=client, settings=settings, callback=collect)
    return build_entity_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def get_member_post_analytics(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    entity_urn = _resolve_post_urn(arguments)
    metric_types = _metric_types_from_arguments(arguments.get("metric_types"))

    def collect(runtime_client: Any) -> dict[str, Any]:
        metrics_by_type: dict[str, int | None] = {}
        for metric_type in metric_types:
            payload = runtime_client.get_member_post_analytics(entity_urn, query_type=metric_type)
            metrics_by_type[metric_type] = _extract_analytics_total(payload)
        return {
            "entity_urn": entity_urn,
            "metrics_by_type": metrics_by_type,
        }

    payload = _with_linkedin_client(client=client, settings=settings, callback=collect)
    return build_entity_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
    )


def enrich_member_posts_with_engagement(
    *,
    client: Any | None,
    settings: LinkedInPostsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    include_social_metadata = _as_bool(arguments.get("include_social_metadata"), parameter_name="include_social_metadata", default=True)
    include_post_analytics = _as_bool(arguments.get("include_post_analytics"), parameter_name="include_post_analytics", default=True)
    limit = _as_int(arguments.get("limit"), parameter_name="limit", default=25, minimum=1, maximum=100)
    metric_types = _metric_types_from_arguments(arguments.get("analytics_metric_types"))

    listing = list_member_posts(
        client=client,
        settings=settings,
        arguments={
            "page_size": arguments.get("page_size", 100),
            "published_after": arguments.get("published_after"),
            "limit": limit,
            "include_raw": False,
        },
    )
    posts = [dict(post) for post in listing["data"]]

    for post in posts:
        post["entity_urn"] = _post_entity_urn(post)
        post["engagement_errors"] = []
        post["engagement_available"] = False

    if include_social_metadata:
        _enrich_posts_with_social_metadata(posts=posts, client=client, settings=settings)
    if include_post_analytics:
        _enrich_posts_with_analytics(posts=posts, client=client, settings=settings, metric_types=metric_types)

    for post in posts:
        post["engagement_available"] = bool(
            post.get("comments_count") is not None
            or post.get("reactions_total") is not None
            or post.get("analytics")
        )

    return build_ok_response(
        data=posts,
        next_after=None,
        has_next=False,
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


def _enrich_posts_with_social_metadata(
    *,
    posts: list[dict[str, Any]],
    client: Any | None,
    settings: LinkedInPostsSettings,
) -> None:
    entity_urns = [entity_urn for post in posts if isinstance((entity_urn := post.get("entity_urn")), str)]
    if not entity_urns:
        return

    try:
        payload = _with_linkedin_client(
            client=client,
            settings=settings,
            callback=lambda runtime_client: runtime_client.batch_get_social_metadata(entity_urns),
        )
    except LinkedInPostsError as exc:
        for post in posts:
            _add_engagement_error(post, exc)
        return

    results = payload.get("results", {}) if isinstance(payload, Mapping) else {}
    for post in posts:
        entity_urn = post.get("entity_urn")
        if not isinstance(entity_urn, str):
            _add_engagement_error(post, ValueError("Unable to determine LinkedIn post URN"))
            continue
        item = results.get(entity_urn) if isinstance(results, Mapping) else None
        if not isinstance(item, Mapping):
            _add_engagement_error(post, ValueError("No social metadata returned for post"))
            continue
        post.update(_normalize_social_metadata_payload(item))


def _enrich_posts_with_analytics(
    *,
    posts: list[dict[str, Any]],
    client: Any | None,
    settings: LinkedInPostsSettings,
    metric_types: tuple[str, ...],
) -> None:
    for post in posts:
        entity_urn = post.get("entity_urn")
        if not isinstance(entity_urn, str):
            _add_engagement_error(post, ValueError("Unable to determine LinkedIn post URN"))
            continue
        entity_urn_str = entity_urn
        metrics: dict[str, int | None] = {}
        for metric_type in metric_types:
            try:
                def load_metric(runtime_client: Any, *, entity_urn: str = entity_urn_str, metric_type: str = metric_type) -> dict[str, Any]:
                    return runtime_client.get_member_post_analytics(entity_urn, query_type=metric_type)

                payload = _with_linkedin_client(
                    client=client,
                    settings=settings,
                    callback=load_metric,
                )
            except LinkedInPostsError as exc:
                _add_engagement_error(post, exc)
                break
            metrics[metric_type] = _extract_analytics_total(payload)
        if metrics:
            post["analytics"] = metrics


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
        "likes_count": _first_int(raw, "Likes", "Like Count", "likes", "likeCount"),
        "comments_count": _first_int(raw, "Comments", "Comment Count", "comments", "commentCount"),
        "impressions_count": _first_int(raw, "Impressions", "Impression Count", "Views", "impressions", "impressionCount", "viewCount"),
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


def _resolve_post_urn(arguments: Mapping[str, Any]) -> str:
    post_urn = arguments.get("post_urn")
    post_url = arguments.get("post_url")
    if isinstance(post_urn, str) and post_urn.strip():
        return normalize_post_urn(post_urn)
    if isinstance(post_url, str) and post_url.strip():
        return normalize_post_urn(post_url)
    raise ValueError("post_urn or post_url is required")


def _first_value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _first_str(data: Mapping[str, Any], *keys: str) -> str | None:
    value = _first_value(data, *keys)
    return str(value).strip() if value is not None and str(value).strip() else None


def _first_int(data: Mapping[str, Any], *keys: str) -> int | None:
    value = _first_value(data, *keys)
    return _coerce_int(value)


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


def _normalize_social_metadata_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    reaction_summaries = payload.get("reactionSummaries")
    reactions_by_type: dict[str, int] = {}
    if isinstance(reaction_summaries, Mapping):
        for reaction_type, summary in reaction_summaries.items():
            count = None
            if isinstance(summary, Mapping):
                count = _coerce_int(summary.get("count"))
            if isinstance(reaction_type, str) and count is not None:
                reactions_by_type[reaction_type] = count

    comment_summary = payload.get("commentSummary")
    comments_count = None
    top_level_comments_count = None
    if isinstance(comment_summary, Mapping):
        comments_count = _coerce_int(comment_summary.get("count"))
        top_level_comments_count = _coerce_int(comment_summary.get("topLevelCount"))

    return {
        "entity_urn": _first_str(payload, "entity"),
        "comments_state": _first_str(payload, "commentsState"),
        "comments_count": comments_count,
        "top_level_comments_count": top_level_comments_count,
        "reactions_total": sum(reactions_by_type.values()),
        "reactions_by_type": reactions_by_type,
    }


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


def _post_entity_urn(post: Mapping[str, Any]) -> str | None:
    for key in ("post_id", "url"):
        value = post.get(key)
        if isinstance(value, str) and value.strip():
            try:
                return normalize_post_urn(value)
            except ValueError:
                continue
    return None


def _extract_analytics_total(payload: Mapping[str, Any]) -> int | None:
    elements = payload.get("elements")
    if not isinstance(elements, list) or not elements:
        return None
    first = elements[0]
    if not isinstance(first, Mapping):
        return None
    total_value = first.get("totalValue")
    if isinstance(total_value, Mapping):
        return _coerce_int(total_value.get("long"))
    return _coerce_int(first.get("value"))


def _metric_types_from_arguments(value: Any) -> tuple[str, ...]:
    if value is None:
        return ANALYTICS_METRIC_TYPES
    if not isinstance(value, list) or not value:
        raise ValueError("metric_types must be a non-empty array of strings")
    metric_types: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("metric_types must contain only strings")
        metric_type = item.strip().upper()
        if metric_type not in ANALYTICS_METRIC_TYPES:
            raise ValueError(f"Unsupported metric type: {item}")
        metric_types.append(metric_type)
    return tuple(dict.fromkeys(metric_types))


def _add_engagement_error(post: dict[str, Any], exc: Exception) -> None:
    errors = post.setdefault("engagement_errors", [])
    if not isinstance(errors, list):
        errors = []
        post["engagement_errors"] = errors
    if isinstance(exc, LinkedInPostsError):
        errors.append({"code": exc.error_code, "message": exc.message})
    else:
        errors.append({"code": "validation_error", "message": str(exc)})


def _filter_posts(posts: list[dict[str, Any]], *, published_after_date: date | None, limit: int | None) -> list[dict[str, Any]]:
    filtered = posts
    if published_after_date is not None:
        filtered = [post for post in filtered if (post_date := _post_date(post)) is None or post_date >= published_after_date]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("_", "")
        if re.fullmatch(r"-?\d+", cleaned):
            return int(cleaned)
    return None


def _similarity(left: str, right: Any) -> float:
    if not isinstance(right, str) or not right.strip():
        return 0.0
    normalized_left = re.sub(r"\s+", " ", left.strip().lower())
    normalized_right = re.sub(r"\s+", " ", right.strip().lower())
    return round(SequenceMatcher(a=normalized_left, b=normalized_right).ratio(), 4)


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


def _as_optional_int(value: Any, *, parameter_name: str, minimum: int, maximum: int) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{parameter_name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{parameter_name} must be between {minimum} and {maximum}")
    return value
