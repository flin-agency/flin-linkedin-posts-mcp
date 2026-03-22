from __future__ import annotations

from typing import Any, Mapping

from ..response import ok_response


def build_ok_response(
    *,
    data: Any,
    api_version: str,
    request_id: str | None,
    next_after: str | None = None,
    has_next: bool = False,
) -> dict[str, Any]:
    return ok_response(
        data=data,
        next_after=next_after,
        has_next=has_next,
        api_version=api_version,
        request_id=request_id,
    )


def build_entity_response(
    *,
    payload: Mapping[str, Any],
    api_version: str,
    request_id: str | None,
) -> dict[str, Any]:
    return build_ok_response(
        data=dict(payload),
        api_version=api_version,
        request_id=request_id,
    )
