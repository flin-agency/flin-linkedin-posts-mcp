from __future__ import annotations

from flin_linkedin_ads_mcp.response import ok_response, selection_required_response


def test_ok_response_includes_paging_and_meta() -> None:
    payload = ok_response(
        data=[{"id": "1"}],
        next_after=None,
        has_next=False,
        api_version="202602",
        request_id="abc123",
    )

    assert payload == {
        "ok": True,
        "data": [{"id": "1"}],
        "paging": {"next_after": None, "has_next": False},
        "meta": {"api_version": "202602", "request_id": "abc123"},
    }


def test_selection_required_response_shape() -> None:
    payload = selection_required_response(
        question="Which account?",
        parameter="ad_account_id",
        choices=[
            {"ad_account_id": "urn:li:sponsoredAccount:1", "label": "Account One"},
            {"ad_account_id": "urn:li:sponsoredAccount:2", "label": "Account Two"},
        ],
        api_version="202602",
        request_id="req-1",
    )

    assert payload["ok"] is True
    assert payload["data"]["type"] == "selection_required"
    assert payload["data"]["parameter"] == "ad_account_id"
    assert len(payload["data"]["choices"]) == 2
