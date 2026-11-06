from dataclasses import replace
import json
import os
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest

from flin_linkedin_posts_mcp.auth import (
    LinkedInOAuthClient, TokenRecord, TokenStore, _local_redirect_from_uri, run_local_oauth_login,
)
from flin_linkedin_posts_mcp.config import load_config
from flin_linkedin_posts_mcp.errors import LinkedInAPIError, LinkedInAuthError, LinkedInPostsError, LinkedInValidationError
from flin_linkedin_posts_mcp.linkedin_client import LinkedInClient
from flin_linkedin_posts_mcp.tools.member_posts import match_drafts_to_member_posts


def client_with_transport(handler):
    return LinkedInClient(
        access_token="private-bearer-token", api_version="202610", restli_protocol_version="2.0.0",
        timeout_seconds=1, max_retries=0, client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
    )


@pytest.mark.parametrize("url", [
    "https://attacker.example/rest/posts", "http://api.linkedin.com/rest/posts",
    "https://api.linkedin.com.attacker.example/rest/posts", "//attacker.example/rest/posts",
    "https://user:pass@api.linkedin.com/rest/posts", "https://api.linkedin.com:444/rest/posts",
    "https://api.linkedin.com/oauth/token", "https://api.linkedin.com/rest/posts#fragment",
])
def test_rejects_untrusted_destinations_before_sending_credentials(url):
    def forbidden(request):
        pytest.fail("No network request should be made")
    with pytest.raises(LinkedInValidationError):
        client_with_transport(forbidden).get_json_url(url)


def test_redirect_not_followed_even_with_injected_client():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://attacker.example/"})
    with pytest.raises(LinkedInAPIError, match="redirects"):
        client_with_transport(handler).get_json("memberSnapshotData")
    assert len(requests) == 1


def test_write_method_rejected():
    with pytest.raises(LinkedInValidationError, match="GET"):
        client_with_transport(lambda request: pytest.fail()).request_json("POST", "posts")


def test_pagination_cycle_stops():
    def handler(request):
        return httpx.Response(200, json={"elements": [], "paging": {"links": [{
            "rel": "next", "href": "https://api.linkedin.com/rest/memberSnapshotData?start=1"
        }]}})
    with pytest.raises(LinkedInAPIError, match="did not advance"):
        list(client_with_transport(handler).iter_member_snapshot_elements())


def test_api_errors_redact_credentials():
    def handler(request):
        return httpx.Response(403, json={"message": "Bad private-bearer-token", "access_token": "other-token"})
    with pytest.raises(LinkedInPostsError) as error:
        client_with_transport(handler).get_json("posts")
    assert "private-bearer-token" not in str(error.value)
    assert "other-token" not in json.dumps(error.value.details)


def test_oauth_errors_redact_credentials():
    settings = load_config({"LINKEDIN_CLIENT_ID": "id", "LINKEDIN_CLIENT_SECRET": "private-secret"})
    def handler(request):
        return httpx.Response(400, json={"error_description": "Bad private-secret code-123", "access_token": "echoed-token"})
    client = LinkedInOAuthClient(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(LinkedInAuthError) as error:
        client.exchange_code(code="code-123", redirect_uri="http://127.0.0.1:63141/callback", code_verifier="verifier")
    result = str(error.value) + json.dumps(error.value.details)
    assert all(secret not in result for secret in ("private-secret", "code-123", "echoed-token"))


def test_token_is_private_before_atomic_replace(tmp_path):
    target = tmp_path / "private" / "tokens.json"
    original_replace = os.replace
    def checked_replace(source, destination):
        assert Path(source).stat().st_mode & 0o777 == 0o600
        assert json.loads(Path(source).read_text())["access_token"] == "secret"
        original_replace(source, destination)
    with patch("flin_linkedin_posts_mcp.auth.os.replace", side_effect=checked_replace):
        TokenStore(target).save(TokenRecord("secret", 9999999999))
    assert target.parent.stat().st_mode & 0o777 == 0o700


def test_token_symlink_is_not_read_or_overwritten(tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("untouched")
    target = tmp_path / "tokens.json"
    target.symlink_to(victim)
    with pytest.raises(LinkedInAuthError, match="symbolic link"):
        TokenStore(target).load()
    TokenStore(target).save(TokenRecord("secret", 9999999999))
    assert victim.read_text() == "untouched"
    assert not target.is_symlink()


def test_invalid_callback_does_not_cancel_valid_login(tmp_path):
    settings = load_config({"LINKEDIN_CLIENT_ID": "id", "LINKEDIN_TOKEN_FILE": str(tmp_path / "tokens.json")})
    record = TokenRecord("secret", 9999999999)
    def browser(url):
        query = parse_qs(urlparse(url).query)
        uri = query["redirect_uri"][0]
        invalid = httpx.get(uri, params={"state": "wrong", "code": "injected"})
        assert invalid.status_code == 401
        response = httpx.get(uri + "?" + urlencode({"state": query["state"][0], "code": "valid"}))
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        return True
    with patch.object(LinkedInOAuthClient, "exchange_code", return_value=record) as exchange:
        assert run_local_oauth_login(settings, open_browser=browser) == record
    assert exchange.call_args.kwargs["code"] == "valid"


def test_invalid_oauth_configuration_does_not_shutdown_unstarted_server():
    settings = replace(load_config({"LINKEDIN_CLIENT_ID": "id"}), oauth_flow="invalid")
    with patch("flin_linkedin_posts_mcp.auth.ThreadingHTTPServer") as server:
        with pytest.raises(LinkedInValidationError):
            run_local_oauth_login(settings)
        server.return_value.shutdown.assert_not_called()
        server.return_value.server_close.assert_called_once()


@pytest.mark.parametrize("uri", ["http://user:pass@127.0.0.1:1234/callback", "http://127.0.0.1:0/callback", "https://example.com/callback"])
def test_invalid_redirect_rejected(uri):
    with pytest.raises(LinkedInValidationError):
        _local_redirect_from_uri(uri)


@pytest.mark.parametrize("drafts", [["x"] * 51, ["x" * 10001]])
def test_unbounded_drafts_rejected(drafts):
    with pytest.raises(ValueError):
        match_drafts_to_member_posts(client=None, settings=load_config({}), arguments={"drafts": drafts})
