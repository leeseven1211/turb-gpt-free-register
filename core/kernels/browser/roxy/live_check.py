# -*- coding: utf-8 -*-
"""Authentication execution extracted without domain storage or task ownership.

Explicit dependencies preserve the original compatibility patch points.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class HeadersDependencies:
    """Capabilities resolved by the domain at this invocation."""
    ACCOUNTS_CHECK_PATH: Any
    normalize_token: Any
    token_claims: Any


def _headers(token: str, *, _deps: HeadersDependencies) -> dict[str, str]:
    ACCOUNTS_CHECK_PATH = _deps.ACCOUNTS_CHECK_PATH
    normalize_token = _deps.normalize_token
    token_claims = _deps.token_claims
    claims = token_claims(token)
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "x-openai-target-path": ACCOUNTS_CHECK_PATH,
        "x-openai-target-route": "/backend-api/accounts/check/{version}",
    }
    account_id = str(claims.get("account_id") or "").strip()
    if account_id:
        headers["chatgpt-account-id"] = account_id
    headers["authorization"] = f"Bearer {normalize_token(token)}"
    return headers


@dataclass(frozen=True)
class FailureDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _now: Any


def _failure(error: str, *, category: str, checked_at: str | None=None, http_status: int | None=None, retryable: bool | None=None, _deps: FailureDependencies, **extra: Any) -> dict[str, Any]:
    _now = _deps._now
    result: dict[str, Any] = {
        "ok": False,
        "status": "failed",
        "checked_at": checked_at or _now(),
        "error": error,
        "error_category": category,
        "validation_method": "access_token",
        "live_check_driver": "browser_roxy",
    }
    if http_status is not None:
        result["http_status"] = http_status
    if retryable is not None:
        result["retryable"] = retryable
    result.update(extra)
    return result


@dataclass(frozen=True)
class ExecuteProbeDependencies:
    """Capabilities resolved by the domain at this invocation."""
    json: Any
    quote: Any
    ACCOUNTS_CHECK_PATH: Any
    _MAX_RESPONSE_TEXT: Any
    _RETRYABLE_HTTP_STATUS: Any
    _failure: Any
    _headers: Any
    parse_accounts_check: Any


def _execute_probe(driver: Any, token: str, proxy: str | None, *, _deps: ExecuteProbeDependencies) -> dict[str, Any]:
    json = _deps.json
    quote = _deps.quote
    ACCOUNTS_CHECK_PATH = _deps.ACCOUNTS_CHECK_PATH
    _MAX_RESPONSE_TEXT = _deps._MAX_RESPONSE_TEXT
    _RETRYABLE_HTTP_STATUS = _deps._RETRYABLE_HTTP_STATUS
    _failure = _deps._failure
    _headers = _deps._headers
    parse_accounts_check = _deps.parse_accounts_check
    del proxy  # 代理已绑定在 Roxy Profile；不把完整代理传进页面脚本。
    try:
        timezone_offset = int(driver.execute_script("return new Date().getTimezoneOffset();"))
    except Exception:
        timezone_offset = "-"
    endpoint = f"https://chatgpt.com{ACCOUNTS_CHECK_PATH}?timezone_offset_min={quote(str(timezone_offset))}"
    script = r"""
const endpoint = arguments[0];
const requestHeaders = arguments[1];
const done = arguments[arguments.length - 1];
fetch(endpoint, {
  method: 'GET',
  headers: requestHeaders,
  credentials: 'omit',
  redirect: 'manual',
  cache: 'no-store'
}).then(async response => {
  let body = '';
  try { body = (await response.text()).slice(0, 1000000); } catch (_) {}
  done({status: response.status, body, redirected: response.redirected});
}).catch(error => done({error: String(error && (error.stack || error.message) || error)}));
"""
    try:
        raw = driver.execute_async_script(script, endpoint, _headers(token))
    except Exception as exc:
        return _failure(
            f"Roxy AT probe 执行失败: {type(exc).__name__}: {str(exc)[:300]}",
            category="browser_execution",
            retryable=True,
        )
    if not isinstance(raw, dict):
        return _failure("Roxy AT probe 返回格式异常", category="browser_execution", retryable=False)
    if raw.get("error"):
        return _failure(
            f"Roxy AT probe 网络失败: {str(raw['error'])[:300]}",
            category="network",
            retryable=True,
        )
    try:
        http_status = int(raw.get("status"))
    except (TypeError, ValueError):
        http_status = None
    body = str(raw.get("body") or "")[:_MAX_RESPONSE_TEXT]
    if http_status == 401:
        return _failure(
            "AT已过期/失效，请手动查活刷新",
            category="auth",
            http_status=http_status,
            retryable=False,
            needs_live_check=True,
            token_expired=True,
            response_preview=body[:500],
        )
    if http_status is None or not 200 <= http_status < 300:
        return _failure(
            f"HTTP {http_status or 'unknown'}",
            category="network" if http_status is not None else "browser_execution",
            http_status=http_status,
            retryable=http_status is None or http_status in _RETRYABLE_HTTP_STATUS or http_status >= 500,
            response_preview=body[:500],
        )
    try:
        data = json.loads(body)
        parsed = parse_accounts_check(data, token=token)
    except Exception as exc:
        return _failure(
            f"Roxy AT probe 响应解析失败: {type(exc).__name__}: {str(exc)[:300]}",
            category="response",
            http_status=http_status,
            retryable=False,
            response_preview=body[:500],
        )
    parsed.update({
        "http_status": http_status,
        "validation_method": "access_token",
        "live_check_driver": "browser_roxy",
    })
    return parsed
