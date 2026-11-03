"""Explicit, one-shot adapters for the optional anonymous challenge probe."""
from __future__ import annotations

import datetime
import logging
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from core.auth.challenge import AuthCancelledError

logger = logging.getLogger(__name__)
LOGIN_URL = "https://chatgpt.com/auth/login"
_SAFE_DEFAULT_HEADERS = {
    "user-agent", "accept", "accept-language", "accept-encoding", "content-type", "connection",
    "cache-control", "pragma", "upgrade-insecure-requests", "priority",
}


def _check_default_headers(transport) -> None:
    # Reject rather than mutate the live transport or silently carry credentials
    # to a challenge origin. CookieJar still applies its normal origin rules.
    for key in (getattr(transport, "headers", None) or {}):
        name = str(key).lower()
        if name not in _SAFE_DEFAULT_HEADERS and not name.startswith(("sec-ch-", "sec-fetch-")):
            raise ValueError("challenge transport has unsupported persistent headers")
    if getattr(transport, "auth", None):
        raise ValueError("challenge transport has persistent authentication")


def _propagate_cancelled(exc: Exception) -> None:
    if isinstance(exc, AuthCancelledError):
        raise exc
    # Registration's stop signal predates the storage-neutral auth signal.
    from core.registration.service import StopRequested
    if isinstance(exc, StopRequested):
        raise exc


def _record(owner, *, method, url, started, response=None, error=None, headers=None, data=None):
    try:
        record = getattr(owner, "_record_traffic", None)
        if callable(record):
            record(started, response=response, error=error)
        elif isinstance(owner, dict) and owner.get("capture") is not None:
            owner["capture"].record(started_at=started, response=response, error=error)
        from core.network.response_diagnostics import safe_response_headers
        from core.registration.debug import record_protocol_exchange
        parsed = urlsplit(url)
        host = parsed.hostname if parsed.hostname in {"chatgpt.com", "challenges.cloudflare.com"} else "challenge.invalid"
        safe_url = LOGIN_URL if url == LOGIN_URL else f"https://{host}/cdn-cgi/challenge-platform/"
        # Raw registration capture intentionally does no redaction. Never give
        # it challenge scripts/proofs, Set-Cookie, or token-bearing path/query.
        safe_response = None
        if response is not None:
            safe_response = SimpleNamespace(
                status_code=int(response.status_code), url=safe_url, content=b"", text="",
                headers=safe_response_headers(dict(response.headers.items())),
            )
        record_protocol_exchange(
            method=method, url=safe_url, started_at=started, request_headers={}, request_body=None,
            response=safe_response, error=RuntimeError("challenge_request_failed") if error else None,
        )
    except Exception:
        # Optional diagnostics cannot change an HTTP outcome.
        logger.debug("[CF] 记录挑战流量失败")


class _StreamResponse:
    """Keep bytes consumed by the bounded bridge readable by the caller."""

    def __init__(self, response, iterator, finish):
        self._response, self._iterator, self._finish = response, iterator, finish
        self._body = bytearray()
        self._finished = False

    def __getattr__(self, name):
        return getattr(self._response, name)

    @property
    def content(self):
        return bytes(self._body)

    @property
    def text(self):
        return self.content.decode("utf-8", "replace")

    def iter_content(self, chunk_size=16384):
        try:
            for chunk in self._iterator(chunk_size):
                if isinstance(chunk, (bytes, bytearray, memoryview)):
                    block = bytes(chunk)
                    self._body.extend(block)
                    yield block
        finally:
            self.close()

    def close(self):
        if not self._finished:
            self._finished = True
            try:
                self._response.close()
            except Exception as exc:
                _propagate_cancelled(exc)
            finally:
                self._finish(self)


class BrowserChallengeTransport:
    """Use the original curl pool; challenge I/O does not reset its circuit."""

    def __init__(self, owner):
        self.owner, self.raw = owner, owner.session
        _check_default_headers(self.raw)

    @property
    def cookies(self):
        return self.raw.cookies

    @property
    def headers(self):
        return self.raw.headers

    def request(self, method, url, **kwargs):
        _check_default_headers(self.raw)
        bounded = getattr(self.owner, "_bounded_request_kwargs", None)
        if callable(bounded):
            kwargs = bounded(kwargs)
        started = time.perf_counter()
        try:
            response = self.raw.request(method, url, **kwargs)
        except BaseException as exc:
            _record(self.owner, method=method, url=url, started=started, error=exc)
            raise
        # A bridge 403 ends this attempt and preserves the original challenge
        # cooldown. A newly observed rate limit retains its own cooldown.
        if int(response.status_code) == 429:
            self.owner._observe_response_for_circuit_breaker(response, url)
        finish = lambda item: _record(self.owner, method=method, url=url, started=started, response=item,
                                      headers=kwargs.get("headers"), data=kwargs.get("data"))
        if kwargs.get("stream"):
            return _StreamResponse(response, lambda size: response.iter_content(chunk_size=size), finish)
        finish(response)
        return response


class WreqChallengeTransport:
    """Single I/O on the original wreq client, bypassing its retry loop."""

    def __init__(self, raw, context):
        self.raw, self.context = raw, context
        _check_default_headers(raw)

    @property
    def cookies(self):
        # The upstream name-keyed mirror loses duplicate cookie names by domain.
        jar = self.raw._jar()
        return SimpleNamespace(jar=list(jar.get_all() or []) if jar is not None else [])

    @property
    def headers(self):
        return self.raw.headers

    def request(self, method, url, **kwargs):
        from core.registration.protocol_oss_2.upstream.http_client_wreq import WreqResponse
        _check_default_headers(self.raw)
        original_url = url
        started = time.perf_counter()
        timeout = float(kwargs.get("timeout", 1))
        if timeout <= 0:
            raise TimeoutError("challenge budget exhausted")
        target, prepared, _ = self.raw._prepare(url, kwargs)
        # Upstream _td rounds to >=1 second; optional probe must respect a
        # subsecond remaining budget rather than extending the deadline.
        prepared["timeout"] = datetime.timedelta(seconds=timeout)
        if self.raw._proxy_obj is not None:
            prepared["proxy"] = self.raw._proxy_obj
        try:
            raw_response = getattr(self.raw._client, method.lower())(target, **prepared)
            self.raw.cookies._sync()
            response = WreqResponse(raw_response, self.raw)
        except BaseException as exc:
            _record(self.context, method=method, url=original_url, started=started, error=exc)
            raise
        finish = lambda item: _record(self.context, method=method, url=original_url, started=started,
                                      response=item, headers=kwargs.get("headers"), data=kwargs.get("data"))
        if kwargs.get("stream"):
            return _StreamResponse(response, lambda size: raw_response.stream(), finish)
        finish(response)
        return response


def _profile(headers: dict, browser_profile: dict | None = None) -> dict:
    profile = dict(browser_profile or {})
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    for key in ("user-agent", "accept-language", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"):
        if normalized.get(key):
            profile[key.replace("-", "_")] = normalized[key]
    return profile


def recover_browser_preflight(owner, response, *, headers, budget):
    """Only called by the enabled login preflight, never generic GET/POST."""
    from core.network.cloudflare import classify_challenge, solve_challenge
    if not classify_challenge(response).confirmed or getattr(owner, "_cf_preflight_attempted", False) is True:
        return response
    owner._cf_preflight_attempted = True
    old_circuit = (owner.blocked_until, owner.blocked_reason)
    try:
        result = solve_challenge(BrowserChallengeTransport(owner), response, url=LOGIN_URL, headers=headers,
                                 profile=_profile(headers, getattr(owner, "browser_profile", {})), budget=budget)
        if result.status == "verified" and (owner.blocked_until, owner.blocked_reason) == old_circuit:
            owner.blocked_until, owner.blocked_reason = 0.0, ""
            return result.response
    except Exception as exc:
        _propagate_cancelled(exc)
        logger.info("[CF] 预检恢复未完成，保留原响应 (%s)", type(exc).__name__)
    return response
