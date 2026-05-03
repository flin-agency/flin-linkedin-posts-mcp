from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
from html import escape
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import secrets
import threading
import time
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlencode, urlparse
import webbrowser

import httpx

from .config import LinkedInPostsSettings
from .errors import LinkedInAuthError, LinkedInValidationError

NATIVE_PKCE_AUTHORIZATION_ENDPOINT = "https://www.linkedin.com/oauth/native-pkce/authorization"
AUTHORIZATION_CODE_ENDPOINT = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_ENDPOINT = "https://www.linkedin.com/oauth/v2/accessToken"
SUPPORTED_OAUTH_FLOWS = {"native_pkce", "authorization_code"}


@dataclass(frozen=True, slots=True)
class TokenRecord:
    access_token: str
    expires_at: float
    token_type: str = "Bearer"
    scope: str | None = None
    refresh_token: str | None = None
    refresh_expires_at: float | None = None

    def is_expired(self, *, now: float | None = None, skew_seconds: float = 60.0) -> bool:
        current = time.time() if now is None else now
        return current + skew_seconds >= self.expires_at

    def refresh_is_expired(self, *, now: float | None = None, skew_seconds: float = 60.0) -> bool:
        if self.refresh_token is None or self.refresh_expires_at is None:
            return True
        current = time.time() if now is None else now
        return current + skew_seconds >= self.refresh_expires_at

    def to_json(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "scope": self.scope,
            "refresh_token": self.refresh_token,
            "refresh_expires_at": self.refresh_expires_at,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "TokenRecord":
        access_token = payload.get("access_token")
        expires_at = payload.get("expires_at")
        if not isinstance(access_token, str) or not access_token:
            raise LinkedInAuthError("Stored LinkedIn token is missing access_token")
        if not isinstance(expires_at, int | float):
            raise LinkedInAuthError("Stored LinkedIn token is missing expires_at")
        token_type = payload.get("token_type")
        scope = payload.get("scope")
        refresh_token = payload.get("refresh_token")
        refresh_expires_at = payload.get("refresh_expires_at")
        return cls(
            access_token=access_token,
            expires_at=float(expires_at),
            token_type=token_type if isinstance(token_type, str) and token_type else "Bearer",
            scope=scope if isinstance(scope, str) else None,
            refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token else None,
            refresh_expires_at=float(refresh_expires_at) if isinstance(refresh_expires_at, int | float) else None,
        )


class TokenStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> TokenRecord | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise LinkedInAuthError(f"Could not read LinkedIn token file: {self.path}") from exc
        if not isinstance(payload, Mapping):
            raise LinkedInAuthError("Stored LinkedIn token file must contain a JSON object")
        return TokenRecord.from_json(payload)

    def save(self, record: TokenRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(record.to_json(), indent=2, sort_keys=True))
        if os.name != "nt":
            os.chmod(self.path, 0o600)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return


def generate_code_verifier(length: int = 64) -> str:
    verifier = secrets.token_urlsafe(length)
    if len(verifier) < 43:
        return generate_code_verifier(length + 8)
    return verifier[:128]


def build_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class LinkedInOAuthClient:
    def __init__(self, settings: LinkedInPostsSettings, *, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = client or httpx.Client(timeout=settings.timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def authorization_url(self, *, redirect_uri: str, state: str, code_challenge: str) -> str:
        if not self.settings.client_id:
            raise LinkedInValidationError("LINKEDIN_CLIENT_ID is required before running login")
        flow = self._oauth_flow()
        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(self.settings.scopes),
        }
        if flow == "native_pkce":
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
            return f"{NATIVE_PKCE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

        if not self.settings.client_secret:
            raise LinkedInValidationError(
                "LINKEDIN_CLIENT_SECRET is required when LINKEDIN_OAUTH_FLOW=authorization_code"
            )
        if not self.settings.redirect_uri:
            raise LinkedInValidationError(
                "LINKEDIN_REDIRECT_URI is required when LINKEDIN_OAUTH_FLOW=authorization_code"
            )
        return f"{AUTHORIZATION_CODE_ENDPOINT}?{urlencode(params)}"

    def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str) -> TokenRecord:
        if not self.settings.client_id:
            raise LinkedInValidationError("LINKEDIN_CLIENT_ID is required before running login")
        flow = self._oauth_flow()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.settings.client_id,
        }
        if flow == "native_pkce":
            data["code_verifier"] = code_verifier
        else:
            if not self.settings.client_secret:
                raise LinkedInValidationError(
                    "LINKEDIN_CLIENT_SECRET is required when LINKEDIN_OAUTH_FLOW=authorization_code"
                )
            data["client_secret"] = self.settings.client_secret
        response = self._client.post(
            TOKEN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise LinkedInAuthError(
                _oauth_error_message(response),
                status_code=response.status_code,
                details={"status_code": response.status_code, "error": _safe_json(response)},
            )
        return _token_record_from_response(response.json())

    def refresh_access_token(self, refresh_token: str) -> TokenRecord:
        if not self.settings.client_id:
            raise LinkedInValidationError("LINKEDIN_CLIENT_ID is required before refreshing token")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
        }
        if self._oauth_flow() == "authorization_code":
            if not self.settings.client_secret:
                raise LinkedInValidationError(
                    "LINKEDIN_CLIENT_SECRET is required when LINKEDIN_OAUTH_FLOW=authorization_code"
                )
            data["client_secret"] = self.settings.client_secret
        response = self._client.post(
            TOKEN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise LinkedInAuthError(
                _oauth_error_message(response),
                status_code=response.status_code,
                details={"status_code": response.status_code, "error": _safe_json(response)},
            )
        return _token_record_from_response(response.json())

    def _oauth_flow(self) -> str:
        if self.settings.oauth_flow not in SUPPORTED_OAUTH_FLOWS:
            raise LinkedInValidationError(
                "LINKEDIN_OAUTH_FLOW must be either native_pkce or authorization_code"
            )
        return self.settings.oauth_flow


@dataclass(frozen=True, slots=True)
class LocalRedirect:
    uri: str
    host: str
    port: int
    path: str


def run_local_oauth_login(
    settings: LinkedInPostsSettings,
    *,
    open_browser: Callable[[str], bool] = webbrowser.open,
) -> TokenRecord:
    if not settings.client_id:
        raise LinkedInValidationError("LINKEDIN_CLIENT_ID is required before running login")

    state = secrets.token_urlsafe(24)
    code_verifier = generate_code_verifier()
    code_challenge = build_code_challenge(code_verifier)
    callback_result: dict[str, str] = {}
    callback_event = threading.Event()
    if settings.redirect_uri:
        local_redirect = _local_redirect_from_uri(settings.redirect_uri)
        callback_path = local_redirect.path
    else:
        if settings.oauth_flow == "authorization_code":
            raise LinkedInValidationError(
                "LINKEDIN_REDIRECT_URI is required when LINKEDIN_OAUTH_FLOW=authorization_code"
            )
        local_redirect = None
        callback_path = "/callback"

    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path != callback_path:
                self.send_error(404)
                return

            returned_state = _first_query_value(query, "state")
            if returned_state != state:
                callback_result["error"] = "OAuth state mismatch"
                self._write_page(401, "LinkedIn login failed. You can close this window.")
                callback_event.set()
                return

            error = _first_query_value(query, "error")
            if error:
                description = _first_query_value(query, "error_description") or error
                callback_result["error"] = description
                self._write_page(
                    400,
                    "LinkedIn login was cancelled or failed.",
                    details=description,
                )
                callback_event.set()
                return

            code = _first_query_value(query, "code")
            if not code:
                callback_result["error"] = "LinkedIn callback did not include an authorization code"
                self._write_page(400, "LinkedIn login failed. You can close this window.")
                callback_event.set()
                return

            callback_result["code"] = code
            self._write_page(200, "LinkedIn login complete. You can close this window.")
            callback_event.set()

        def log_message(self, *_: Any) -> None:
            return

        def _write_page(self, status_code: int, message: str, *, details: str | None = None) -> None:
            detail_html = f"<p>{escape(details)}</p>" if details else ""
            body = (
                "<!doctype html><title>LinkedIn MCP</title>"
                f"<p>{escape(message)}</p>{detail_html}"
                "<p>You can close this window.</p>"
            ).encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if local_redirect:
        server = ThreadingHTTPServer((local_redirect.host, local_redirect.port), OAuthCallbackHandler)
        redirect_uri = local_redirect.uri
    else:
        server = ThreadingHTTPServer(("127.0.0.1", 0), OAuthCallbackHandler)
        redirect_uri = f"http://127.0.0.1:{server.server_port}{callback_path}"
    oauth_client = LinkedInOAuthClient(settings)
    try:
        url = oauth_client.authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        open_browser(url)
        if not callback_event.wait(settings.oauth_timeout_seconds):
            raise LinkedInAuthError("Timed out waiting for LinkedIn OAuth callback")
        if callback_result.get("error"):
            raise LinkedInAuthError(callback_result["error"])
        record = oauth_client.exchange_code(
            code=callback_result["code"],
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )
        TokenStore(settings.token_file).save(record)
        return record
    finally:
        server.shutdown()
        server.server_close()
        oauth_client.close()


def load_valid_token(settings: LinkedInPostsSettings) -> TokenRecord:
    store = TokenStore(settings.token_file)
    record = store.load()
    if record is None:
        raise LinkedInAuthError("LinkedIn is not authenticated. Run the login tool first.")
    if not record.is_expired():
        return record
    if record.refresh_token and not record.refresh_is_expired():
        oauth_client = LinkedInOAuthClient(settings)
        try:
            refreshed = oauth_client.refresh_access_token(record.refresh_token)
        finally:
            oauth_client.close()
        if refreshed.refresh_token is None:
            refreshed = TokenRecord(
                access_token=refreshed.access_token,
                expires_at=refreshed.expires_at,
                token_type=refreshed.token_type,
                scope=refreshed.scope,
                refresh_token=record.refresh_token,
                refresh_expires_at=record.refresh_expires_at,
            )
        store.save(refreshed)
        return refreshed
    raise LinkedInAuthError("LinkedIn token has expired. Run the login tool again.")


def token_status_payload(settings: LinkedInPostsSettings, record: TokenRecord | None) -> dict[str, Any]:
    return {
        "authenticated": record is not None and not record.is_expired(),
        "expired": record.is_expired() if record else None,
        "expires_at": record.expires_at if record else None,
        "scope": record.scope if record else None,
        "has_refresh_token": bool(record.refresh_token) if record else False,
        "refresh_expires_at": record.refresh_expires_at if record else None,
        "client_id_configured": bool(settings.client_id),
        "client_secret_configured": bool(settings.client_secret),
        "oauth_flow": settings.oauth_flow,
        "redirect_uri_configured": bool(settings.redirect_uri),
        "token_file": str(settings.token_file),
    }


def _token_record_from_response(payload: Any) -> TokenRecord:
    if not isinstance(payload, Mapping):
        raise LinkedInAuthError("LinkedIn token response must be a JSON object")
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    if not isinstance(access_token, str) or not access_token:
        raise LinkedInAuthError("LinkedIn token response did not include access_token")
    if not isinstance(expires_in, int | float):
        raise LinkedInAuthError("LinkedIn token response did not include expires_in")

    now = time.time()
    refresh_token = payload.get("refresh_token")
    refresh_expires_in = payload.get("refresh_token_expires_in")
    return TokenRecord(
        access_token=access_token,
        expires_at=now + float(expires_in),
        token_type=str(payload.get("token_type") or "Bearer"),
        scope=payload.get("scope") if isinstance(payload.get("scope"), str) else None,
        refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token else None,
        refresh_expires_at=now + float(refresh_expires_in) if isinstance(refresh_expires_in, int | float) else None,
    )


def _first_query_value(query: Mapping[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]


def _local_redirect_from_uri(uri: str) -> LocalRedirect:
    parsed = urlparse(uri)
    if parsed.scheme != "http":
        raise LinkedInValidationError(
            "LINKEDIN_REDIRECT_URI must be an http loopback URL such as "
            "http://127.0.0.1:63141/callback"
        )
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise LinkedInValidationError("LINKEDIN_REDIRECT_URI must use 127.0.0.1 or localhost")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LinkedInValidationError("LINKEDIN_REDIRECT_URI must include a valid port") from exc
    if port is None:
        raise LinkedInValidationError("LINKEDIN_REDIRECT_URI must include a port")
    if not parsed.path or parsed.path == "/":
        raise LinkedInValidationError("LINKEDIN_REDIRECT_URI must include a callback path")
    if parsed.query or parsed.fragment:
        raise LinkedInValidationError("LINKEDIN_REDIRECT_URI must not include query strings or fragments")
    return LocalRedirect(uri=uri, host=parsed.hostname, port=port, path=parsed.path)


def _oauth_error_message(response: httpx.Response) -> str:
    payload = _safe_json(response)
    description = payload.get("error_description")
    if isinstance(description, str) and description:
        return description
    error = payload.get("error")
    if isinstance(error, str) and error:
        return error
    return response.text or "LinkedIn OAuth request failed"


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
