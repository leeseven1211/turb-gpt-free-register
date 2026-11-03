"""Bounded same-transport recovery for the anonymous ChatGPT login page.

This module never creates a session, replays an authentication action, or treats
an issued clearance cookie as proof that the original document has recovered.
The caller supplies a transport adapter whose request method does one streamed
request using the existing proxy, fingerprint, and RFC cookie store.
"""
from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from core.auth.challenge import AuthCancelledError
from core.auth.state_machine import StageBudget, StageTimeout

ANONYMOUS_LOGIN_URL = "https://chatgpt.com/auth/login"
MAX_SOLVE_SECONDS = 12.0
MAX_REQUESTS = 12
MAX_REQUEST_BODY_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
MAX_COOKIE_BYTES = 32 * 1024

_CHALLENGE_HOSTS = frozenset({"chatgpt.com", "challenges.cloudflare.com"})
_CHALLENGE_PREFIX = "/cdn-cgi/challenge-platform/"
_EXPLICIT_INTERACTIVE = re.compile(
    rb"""(?:\bcType\b|["']cType["']|\[\s*["']cType["']\s*\])\s*[:=]\s*(["'])interactive\1"""
)
_RUNTIME_KINDS = frozenset({"fetch", "xhr", "script", "iframe", "challenge"})
_RUNTIME_HEADERS = frozenset({"accept", "accept-language", "content-type", "cache-control"})
_IDENTITY_HEADERS = frozenset({
    "user-agent", "accept-language", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    "sec-ch-ua-platform-version", "sec-ch-ua-arch", "sec-ch-ua-bitness", "sec-ch-ua-model",
    "sec-ch-ua-full-version-list",
})
_FORBIDDEN_HEADERS = frozenset({
    "authorization", "cookie", "cookie2", "host", "proxy-authorization", "proxy-authenticate",
    "forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "connection",
    "transfer-encoding", "content-length",
})
_AUTH_COOKIE_NAMES = frozenset({
    "__secure-next-auth.session-token", "next-auth.session-token", "__secure-authjs.session-token",
    "authjs.session-token", "access_token", "refresh_token", "__session", "auth-token",
})
_BROWSER_PROFILE_KEYS = frozenset({
    "user_agent", "navigator_language", "navigator_languages", "navigator_platform", "navigator_vendor",
    "hardware_concurrency", "device_memory", "device_pixel_ratio", "screen_width", "screen_height",
    "screen_avail_width", "screen_avail_height", "color_depth", "outer_width", "outer_height",
    "viewport_width", "viewport_height", "timezone_iana", "timezone_offset_minutes", "timezone_name",
    "user_agent_data_platform", "chrome_major", "chrome_full_version", "browser_family", "browser_os",
})


@dataclass(frozen=True)
class ChallengeEvidence:
    confirmed: bool
    reason: str


@dataclass(frozen=True)
class SolveResult:
    status: str
    reason: str
    response: object = field(repr=False, compare=False)
    request_count: int = 0


class _PolicyError(RuntimeError):
    """Only constant safe reason codes may be passed to this exception."""


class _Unsupported(RuntimeError):
    """A transport lacks metadata required to establish the recovery boundary."""


def _headers(value: object) -> dict[str, str]:
    items = getattr(value, "items", None)
    if not callable(items):
        raise _PolicyError("invalid_headers")
    result = {}
    size = 0
    for index, pair in enumerate(items()):
        if index >= 128:
            raise _PolicyError("header_count_limit")
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise _PolicyError("invalid_headers")
        name, raw = pair
        if (not isinstance(name, str) or not isinstance(raw, str)
                or not re.fullmatch(r"[A-Za-z0-9!#$&'*+.^_`|~-]+", name)
                or any(ord(char) < 32 or ord(char) == 127 for char in raw)):
            raise _PolicyError("invalid_headers")
        key = name.lower()
        if key in result and key != "set-cookie":
            raise _PolicyError("duplicate_header")
        size += len(name.encode("utf-8")) + len(raw.encode("utf-8"))
        if size > MAX_HEADER_BYTES:
            raise _PolicyError("header_limit")
        # Set-Cookie is legitimately repeated by real WreqResponses.  Cookie
        # application belongs to the transport jar; never flatten or export it.
        if key != "set-cookie":
            result[key] = raw
    return result


def classify_challenge(response: object) -> ChallengeEvidence:
    """Cloudflare routing headers alone never establish an actual challenge."""
    try:
        headers = _headers(getattr(response, "headers", {}))
        confirmed = (int(getattr(response, "status_code", 0)) == 403
                     and headers.get("cf-mitigated", "").strip().lower() == "challenge")
    except (TypeError, ValueError, _PolicyError):
        confirmed = False
    return ChallengeEvidence(confirmed, "confirmed_challenge" if confirmed else "not_confirmed_challenge")


def _challenge_url(url: object) -> bool:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(char) < 33 for char in url):
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname in _CHALLENGE_HOSTS
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and not parsed.fragment and parsed.path.startswith(_CHALLENGE_PREFIX)
                and len(parsed.path) > len(_CHALLENGE_PREFIX)
                and "\\" not in url and "%" not in parsed.path
                and not any(part in {".", ".."} for part in parsed.path.split("/")))
    except ValueError:
        return False


def _cancelled(exc: BaseException) -> bool:
    # Do not import the registration service (and its operational dependencies)
    # from this optional network helper merely to identify its stop sentinel.
    return isinstance(exc, AuthCancelledError) or any(
        cls.__name__ == "StopRequested" and cls.__module__ == "core.registration.service"
        for cls in type(exc).__mro__
    )


def _cookies(transport: object) -> list:
    store = getattr(transport, "cookies", None)
    jar = getattr(store, "jar", None)
    if jar is None:
        # A flat name/value mapping has already lost domain/path/HttpOnly data.
        raise _Unsupported("cookie_metadata_unavailable")
    result, size = [], 0
    for cookie in jar:
        if isinstance(cookie, (str, bytes)) or not _cookie_field(cookie, "name"):
            raise _Unsupported("cookie_metadata_unavailable")
        size += len(str(_cookie_field(cookie, "name", ""))) + len(str(_cookie_field(cookie, "value", "")))
        if len(result) >= 256 or size > 64 * 1024:
            raise _PolicyError("cookie_store_limit")
        result.append(cookie)
    return result


def _cookie_field(cookie: object, name: str, default=None):
    return cookie.get(name, default) if isinstance(cookie, Mapping) else getattr(cookie, name, default)


def _matching_cookie(cookie: object, url: str) -> bool:
    parsed = urlsplit(url)
    domain = str(_cookie_field(cookie, "domain", "")).lower()
    if not domain:
        return False
    domain_name = domain.lstrip(".")
    host_only = not bool(_cookie_field(cookie, "domain_specified", domain.startswith(".")))
    if parsed.hostname != domain_name and (host_only or not parsed.hostname.endswith("." + domain_name)):
        return False
    path = str(_cookie_field(cookie, "path", "/") or "/")
    if parsed.path != path and not parsed.path.startswith(path if path.endswith("/") else path + "/"):
        return False
    if _cookie_field(cookie, "secure", False) and parsed.scheme != "https":
        return False
    expires = _cookie_field(cookie, "expires")
    if isinstance(expires, datetime):
        expires = expires.replace(tzinfo=timezone.utc).timestamp() if expires.tzinfo is None else expires.timestamp()
    if isinstance(expires, (int, float)) and expires <= time.time():
        return False
    return True


def _http_only(cookie: object) -> bool:
    if _cookie_field(cookie, "http_only", False) or _cookie_field(cookie, "httponly", False):
        return True
    rest = _cookie_field(cookie, "_rest", {})
    return isinstance(rest, Mapping) and any(str(name).lower() == "httponly" for name in rest)


def _visible_cookies(transport: object, url: str) -> list[dict]:
    result = []
    size = 0
    for cookie in _cookies(transport):
        if not _matching_cookie(cookie, url) or _http_only(cookie):
            continue
        name, value = _cookie_field(cookie, "name", ""), _cookie_field(cookie, "value", "")
        if not isinstance(name, str) or not isinstance(value, str) or not name:
            continue
        domain = str(_cookie_field(cookie, "domain", ""))
        item = {"name": name, "value": value, "domain": domain.lstrip("."),
                "path": str(_cookie_field(cookie, "path", "/") or "/"),
                "secure": bool(_cookie_field(cookie, "secure", False)),
                "hostOnly": not bool(_cookie_field(cookie, "domain_specified", domain.startswith(".")))}
        size += len(json.dumps(item, ensure_ascii=True).encode("ascii"))
        if size > MAX_COOKIE_BYTES or len(result) >= 64:
            raise _PolicyError("cookie_limit")
        result.append(item)
    return result


def _cookie_snapshot(transport: object, names: set[str] | frozenset[str]) -> tuple:
    snapshot = []
    for cookie in _cookies(transport):
        if _matching_cookie(cookie, ANONYMOUS_LOGIN_URL) and _cookie_field(cookie, "name", "") in names:
            snapshot.append((str(_cookie_field(cookie, "domain", "")), str(_cookie_field(cookie, "path", "/")),
                             str(_cookie_field(cookie, "name", "")),
                             hashlib.sha256(str(_cookie_field(cookie, "value", "")).encode()).digest()))
    return tuple(sorted(snapshot))


def _authenticated(transport: object) -> bool:
    for cookie in _cookies(transport):
        name = str(_cookie_field(cookie, "name", "")).lower()
        if (_matching_cookie(cookie, ANONYMOUS_LOGIN_URL) and _cookie_field(cookie, "value", "")
                and any(name == auth or name.startswith(auth + ".") for auth in _AUTH_COOKIE_NAMES)):
            return True
    return False


def _safe_response_headers(response: object) -> dict[str, str]:
    headers = _headers(getattr(response, "headers", {}))
    allowed = {"content-type", "cache-control", "cf-mitigated", "retry-after"}
    return {name: value for name, value in headers.items() if name in allowed and len(value) <= 256}


def _close_response(response: object) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        try:
            close()
        except Exception as exc:
            if _cancelled(exc):
                raise
            # Optional transport/traffic cleanup must not mask cancellation or
            # timeout already raised while consuming the response.


def _read_response(response: object, budget: StageBudget, *, streamed: bool = False,
                   byte_limit: int | None = None) -> bytes:
    limit = min(MAX_RESPONSE_BYTES, byte_limit) if byte_limit is not None else MAX_RESPONSE_BYTES
    try:
        budget.require("cloudflare response")
        length = _headers(getattr(response, "headers", {})).get("content-length", "")
        if length.isdigit() and int(length) > limit:
            raise _PolicyError("response_byte_limit")
        if streamed and callable(getattr(response, "iter_content", None)):
            chunks, size = [], 0
            iterator = iter(response.iter_content(chunk_size=min(8192, max(1, limit + 1))))
            while True:
                budget.require("cloudflare response")
                try:
                    chunk = next(iterator)
                except StopIteration:
                    budget.require("cloudflare response")
                    break
                budget.require("cloudflare response")
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise _PolicyError("invalid_response_body")
                size += len(chunk)
                if size > limit:
                    raise _PolicyError("response_byte_limit")
                chunks.append(bytes(chunk))
            return b"".join(chunks)
        body = getattr(response, "content", b"")
        if not isinstance(body, (bytes, bytearray)):
            raise _PolicyError("invalid_response_body")
        if len(body) > limit:
            raise _PolicyError("response_byte_limit")
        budget.require("cloudflare response")
        return bytes(body)
    finally:
        if streamed:
            _close_response(response)


class _Bridge:
    def __init__(self, transport: object, budget: StageBudget, headers: dict[str, str]):
        self.transport = transport
        self.budget = budget
        self.headers = headers
        self.request_count = 0
        self.byte_count = 0
        self.failure: Exception | None = None

    def __call__(self, request: dict) -> dict:
        try:
            if self.failure is not None:
                raise self.failure
            if not isinstance(request, Mapping) or set(request) - {"method", "url", "headers", "body", "kind"}:
                raise _PolicyError("invalid_bridge_request")
            method, url = request.get("method"), request.get("url")
            if (method not in {"GET", "POST"} or not _challenge_url(url)
                    or request.get("kind") not in _RUNTIME_KINDS):
                raise _PolicyError("request_not_allowed")
            supplied = _headers(request.get("headers", {}))
            if set(supplied) - _RUNTIME_HEADERS:
                raise _PolicyError("header_not_allowed")
            headers = dict(self.headers)
            headers.update(supplied)
            body = request.get("body")
            if body is not None and not isinstance(body, str):
                raise _PolicyError("invalid_request_body")
            if method == "GET" and body:
                raise _PolicyError("get_body_not_allowed")
            response, content = self.request(method, url, headers, body)
            return {"status": int(response.status_code), "url": url,
                    "headers": _safe_response_headers(response), "body": base64.b64encode(content).decode("ascii"),
                    "cookies": _visible_cookies(self.transport, url)}
        except Exception as exc:
            self.failure = exc
            raise

    def request(self, method: str, url: str, headers: dict, body: str | None = None) -> tuple[object, bytes]:
        self.budget.require("cloudflare request")
        if self.request_count >= MAX_REQUESTS:
            raise _PolicyError("request_limit")
        body_bytes = len(body.encode("utf-8")) if body else 0
        if body_bytes > MAX_REQUEST_BODY_BYTES:
            raise _PolicyError("request_body_limit")
        if self.byte_count + body_bytes >= MAX_TOTAL_BYTES:
            raise _PolicyError("total_byte_limit")
        self.byte_count += body_bytes
        self.request_count += 1
        kwargs = {"headers": headers, "timeout": self.budget.require("cloudflare request"),
                  "allow_redirects": False, "stream": True}
        if body is not None:
            kwargs["data"] = body
        response = self.transport.request(method, url, **kwargs)
        try:
            self.budget.require("cloudflare response")
            if str(getattr(response, "url", "")) != url:
                raise _PolicyError("unexpected_response_url")
            if 300 <= int(response.status_code) < 400:
                raise _PolicyError("redirect_not_allowed")
            if int(response.status_code) == 429:
                raise _PolicyError("rate_limited")
            if int(response.status_code) == 403:
                raise _PolicyError("subrequest_forbidden")
            content = _read_response(response, self.budget, streamed=True,
                                     byte_limit=MAX_TOTAL_BYTES - self.byte_count)
            self.budget.require("cloudflare response")
            self.byte_count += len(content)
            return response, content
        except BaseException:
            _close_response(response)
            raise


def _expected_login(response: object, content: bytes) -> bool:
    headers = _headers(getattr(response, "headers", {}))
    if (int(response.status_code) != 200 or str(getattr(response, "url", "")) != ANONYMOUS_LOGIN_URL
            or headers.get("cf-mitigated", "").strip().lower() == "challenge"
            or headers.get("content-type", "").split(";", 1)[0].strip().lower() != "text/html"):
        return False
    html = content.decode("utf-8", errors="replace").lower()
    if any(marker in html for marker in ("/cdn-cgi/challenge-platform/", "cf-chl-", "challenges.cloudflare.com")):
        return False
    return bool(re.search(r"<title\b[^>]*>\s*chatgpt\s*</title\s*>", html)
                and re.search(r"<(?:main|form)\b", html)
                and re.search(r"(?:log\s*in|sign\s*up|/auth/login)", html)
                and any(marker in html for marker in ("/assets/", "/_next/", "__next_data__", 'id="root"', 'id="__next"')))


def solve_challenge(transport, response, *, url, headers, profile, budget,
                    runtime_factory=None) -> SolveResult:
    """Try one bounded DOM run and one exact anonymous document verification.

    Failure returns the caller's original response. Cancellation is deliberately
    propagated; exception text and response bodies never enter diagnostic codes.
    The runtime's boolean denotes completion, not successful HTTP recovery.
    """
    bridge = None
    def result(status, reason, document=response):
        return SolveResult(status, reason, document, bridge.request_count if bridge else 0)

    try:
        budget.check_cancelled()
        if not classify_challenge(response).confirmed:
            return result("unchanged", "not_confirmed_challenge")
        if url != ANONYMOUS_LOGIN_URL or str(getattr(response, "url", "")) != url:
            return result("blocked", "anonymous_login_only")
        original_request = getattr(response, "request", None)
        original_method = (original_request.get("method", "GET") if isinstance(original_request, Mapping)
                           else getattr(original_request, "method", "GET"))
        if original_method != "GET":
            return result("blocked", "anonymous_get_only")
        budget = budget.child(MAX_SOLVE_SECONDS)
        budget.require("cloudflare recovery")
        request_headers = _headers(headers)
        defaults = _headers(getattr(transport, "headers", {}))
        if _FORBIDDEN_HEADERS.intersection(request_headers) or _FORBIDDEN_HEADERS.intersection(defaults):
            return result("blocked", "authenticated_headers")
        if _authenticated(transport):
            return result("blocked", "authenticated_cookie_store")
        if not isinstance(profile, Mapping):
            return result("blocked", "invalid_browser_profile")
        identity_headers = {name: value for name, value in {**defaults, **request_headers}.items()
                            if name in _IDENTITY_HEADERS}
        user_agent = identity_headers.get("user-agent") or profile.get("user_agent")
        if (not isinstance(user_agent, str) or not user_agent or len(user_agent) > 1024
                or (profile.get("user_agent") and profile["user_agent"] != user_agent)):
            return result("blocked", "browser_identity_mismatch")
        identity_headers["user-agent"] = user_agent
        identity_headers = _headers(identity_headers)
        browser_identity = {name: value for name, value in profile.items() if name in _BROWSER_PROFILE_KEYS}
        if len(json.dumps(browser_identity).encode("utf-8")) > 64 * 1024:
            return result("blocked", "profile_limit")
        html = _read_response(response, budget)
        # Only explicit challenge-type declarations establish this unsupported
        # interaction. A managed page or Turnstile element alone does not.
        if _EXPLICIT_INTERACTIVE.search(html):
            return result("unsupported", "interactive_challenge")
        before_clearance = _cookie_snapshot(transport, {"cf_clearance"})
        before_identity = _cookie_snapshot(transport, {"oai-did"})
        remaining = budget.require("cloudflare runtime")
        if remaining < 0.1:
            return result("timeout", "insufficient_verification_budget")
        payload = {"url": url, "html": html.decode("utf-8", errors="replace"), "userAgent": user_agent,
                   "browserIdentity": browser_identity, "cookies": _visible_cookies(transport, url),
                   # The runtime may spend its entire wait. Keep the remaining
                   # quarter of the same deadline for the single verification.
                   "waitMs": max(1, int(min(10.0, remaining * 0.75) * 1000))}
        bridge = _Bridge(transport, budget, identity_headers)
        if runtime_factory is None:
            from core.network.cloudflare_runtime import run_runtime
            runtime_factory = run_runtime
        completed = runtime_factory(payload, bridge, budget)
        if bridge.failure is not None:
            raise bridge.failure
        budget.require("cloudflare verification")
        if completed is not True:
            return result("unsupported", "runtime_incomplete")
        if _authenticated(transport) or _cookie_snapshot(transport, {"oai-did"}) != before_identity:
            return result("blocked", "identity_changed")
        verify_headers = {name: value for name, value in request_headers.items()
                          if name in _IDENTITY_HEADERS or name in {"accept", "upgrade-insecure-requests", "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest", "sec-fetch-user"}}
        verify_headers.update(identity_headers)
        verified, content = bridge.request("GET", url, verify_headers)
        if _authenticated(transport) or _cookie_snapshot(transport, {"oai-did"}) != before_identity:
            return result("blocked", "identity_changed")
        expected_login = _expected_login(verified, content)
        budget.require("cloudflare verification")
        if expected_login:
            return result("verified", "expected_login_document", verified)
        if _cookie_snapshot(transport, {"cf_clearance"}) != before_clearance:
            return result("clearance_issued", "login_not_verified")
        return result("unchanged", "login_not_verified")
    except Exception as exc:
        if _cancelled(exc):
            raise
        if isinstance(exc, (StageTimeout, TimeoutError)):
            return result("timeout", "recovery_timeout")
        if isinstance(exc, _PolicyError):
            return result("blocked", str(exc))
        if isinstance(exc, _Unsupported):
            return result("unsupported", str(exc))
        if isinstance(exc, (ImportError, ModuleNotFoundError)):
            return result("unsupported", "runtime_unavailable")
        return result("unchanged", "optional_recovery_error")
