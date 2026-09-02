# -*- coding: utf-8 -*-
"""Roxy 浏览器普通查活 probe。

该模块只验证已有 access token。它不打开登录页、不提交账号凭据、不发送
邮箱验证码，也不读取或写入持久 Cookie/localStorage；Roxy 环境默认由本次
任务创建并在结束时清理。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

from config import roxybrowser as roxy_config
from core.chatgpt_plan import ACCOUNTS_CHECK_PATH, normalize_token, parse_accounts_check, token_claims
from core.registration.selenium_auth import build_driver, safe_get
from core.roxybrowser_client import RoxyBrowserClient

logger = logging.getLogger(__name__)

_PROBE_PAGE = "https://chatgpt.com/robots.txt"
_PROBE_TIMEOUT_SECONDS = 20
_MAX_RESPONSE_TEXT = 1_000_000
_RETRYABLE_HTTP_STATUS = frozenset({408, 409, 425, 429})


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def available() -> bool:
    """只检查 Roxy 连接所需配置，不检查注册主驱动。"""
    return bool(
        str(getattr(roxy_config, "ROXY_API_BASE", "") or "").strip()
        and str(getattr(roxy_config, "ROXY_API_TOKEN", "") or "").strip()
        and str(getattr(roxy_config, "ROXY_WORKSPACE_ID", "") or "").strip()
    )


def _headers(token: str) -> dict[str, str]:
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


def _failure(
    error: str,
    *,
    category: str,
    checked_at: str | None = None,
    http_status: int | None = None,
    retryable: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
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


def _execute_probe(driver: Any, token: str, proxy: str | None) -> dict[str, Any]:
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


def run_probe(*, token: str, proxy: str | None = None) -> dict[str, Any]:
    """创建临时 Roxy 环境并执行一次旧 AT probe。"""
    checked_at = _now()
    if not normalize_token(token):
        return _failure("token 为空", category="configuration", checked_at=checked_at, retryable=False)
    if not available():
        return _failure(
            "Roxy 浏览器普通查活未配置",
            category="configuration",
            checked_at=checked_at,
            retryable=False,
        )
    client = RoxyBrowserClient()
    opened = None
    driver = None
    try:
        try:
            opened = client.open_profile(proxy_url=proxy)
        except Exception as exc:
            return _failure(
                f"Roxy Profile 创建/打开失败: {type(exc).__name__}: {str(exc)[:500]}",
                category="profile",
                checked_at=checked_at,
                retryable=True,
            )
        try:
            driver = build_driver(opened)
        except Exception as exc:
            return _failure(
                f"Roxy 浏览器驱动连接失败: {type(exc).__name__}: {str(exc)[:500]}",
                category="browser_driver",
                checked_at=checked_at,
                retryable=True,
            )
        driver.set_page_load_timeout(int(getattr(roxy_config, "ROXY_SELENIUM_TIMEOUT", 90) or 90))
        try:
            driver.set_script_timeout(_PROBE_TIMEOUT_SECONDS)
        except Exception:
            pass
        # 仅打开同源静态页面，为受控 fetch 提供 chatgpt.com origin；不进入 auth/login。
        try:
            safe_get(
                driver,
                _PROBE_PAGE,
                timeout=min(30, int(getattr(roxy_config, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
                attempts=1,
                accept_hosts=("chatgpt.com",),
            )
        except Exception as exc:
            return _failure(
                f"Roxy 查活页面/代理连接失败: {type(exc).__name__}: {str(exc)[:500]}",
                category="browser_navigation",
                checked_at=checked_at,
                retryable=True,
            )
        return _execute_probe(driver, token, proxy)
    except Exception as exc:
        logger.warning("[查活][Roxy] 旧 AT probe 失败: %s: %s", type(exc).__name__, str(exc)[:300])
        return _failure(
            f"Roxy AT probe {type(exc).__name__}: {str(exc)[:500]}",
            category="browser_execution",
            checked_at=checked_at,
            retryable=True,
        )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                logger.debug("[查活][Roxy] driver 关闭失败", exc_info=True)
        if opened is not None:
            try:
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[查活][Roxy] 临时环境清理失败：profile=%s", getattr(opened, "profile_id", "-"))


__all__ = ["available", "run_probe"]
