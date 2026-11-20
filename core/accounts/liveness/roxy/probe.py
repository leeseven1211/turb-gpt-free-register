# -*- coding: utf-8 -*-
"""Roxy 浏览器普通查活 probe。

该模块只验证已有 access token。它不打开登录页、不提交账号凭据、不发送
邮箱验证码，也不读取或写入持久 Cookie/localStorage；有账号标识时优先复用
账号绑定的 Profile，没有绑定时才创建并回写绑定。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

from config import roxybrowser as roxy_config
from core.accounts.plans.client import ACCOUNTS_CHECK_PATH, normalize_token, parse_accounts_check, token_claims
from core.auth.browser.selenium_auth import build_driver, quit_driver, safe_get
from core.browser.roxy.client import RoxyBrowserClient

logger = logging.getLogger('core.live_check_browser')

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
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.live_check import _headers as execute, HeadersDependencies
    dependencies = HeadersDependencies(
        ACCOUNTS_CHECK_PATH=ACCOUNTS_CHECK_PATH,
        normalize_token=normalize_token,
        token_claims=token_claims,
    )
    return execute(token, _deps=dependencies)


def _failure(
    error: str,
    *,
    category: str,
    checked_at: str | None = None,
    http_status: int | None = None,
    retryable: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.live_check import _failure as execute, FailureDependencies
    dependencies = FailureDependencies(
        _now=_now,
    )
    return execute(error, category=category, checked_at=checked_at, http_status=http_status, retryable=retryable, **extra, _deps=dependencies)


def _execute_probe(driver: Any, token: str, proxy: str | None) -> dict[str, Any]:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.live_check import _execute_probe as execute, ExecuteProbeDependencies
    dependencies = ExecuteProbeDependencies(
        json=json,
        quote=quote,
        ACCOUNTS_CHECK_PATH=ACCOUNTS_CHECK_PATH,
        _MAX_RESPONSE_TEXT=_MAX_RESPONSE_TEXT,
        _RETRYABLE_HTTP_STATUS=_RETRYABLE_HTTP_STATUS,
        _failure=_failure,
        _headers=_headers,
        parse_accounts_check=parse_accounts_check,
    )
    return execute(driver, token, proxy, _deps=dependencies)


def run_probe(
    *,
    token: str,
    proxy: str | None = None,
    email: str | None = None,
    context_recorder=None,
    route_context: dict | None = None,
) -> dict[str, Any]:
    """打开账号绑定的 Roxy Profile 并执行一次旧 AT probe。"""
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
    bound_profile_id = ""
    opened = None
    driver = None
    data_saver = None
    asset_cache = None
    probe_result = None
    try:
        if email:
            from core.browser.roxy.profile_binding import account_profile_id_by_email

            bound_profile_id = account_profile_id_by_email(email, strict=True)
        try:
            if email:
                opened = client.open_profile_for_account(
                    profile_id=bound_profile_id or None,
                    proxy_url=proxy,
                    data_saver_flow="live_check",
                )
                if not bound_profile_id or str(opened.profile_id) != str(bound_profile_id):
                    from core.browser.roxy.profile_binding import persist_account_profile_id

                    if not persist_account_profile_id(email, opened.profile_id):
                        raise RuntimeError("账号 Roxy Profile 绑定写回失败")
                    opened.account_bound = True
                    client.mark_profile_bound(opened.profile_id)
            else:
                # Preserve the low-level adapter contract for callers that do
                # not have an account identity (and for legacy integrations).
                opened = client.open_profile(proxy_url=proxy, data_saver_flow="live_check")
            if context_recorder is not None:
                context_recorder.open_roxy_profile(
                    opened,
                    route_attempt_no=1,
                    proxy_url=(None if bound_profile_id and opened.account_bound else proxy),
                    proxy_context=route_context,
                )
            else:
                try:
                    from core.browser import traffic as browser_traffic

                    browser_traffic.bind_roxy_capture(opened, purpose="live_check")
                except Exception:
                    logger.exception("[浏览器流量] 关联普通查活上下文失败；查活继续")
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
        try:
            from core.browser import flow_policy as browser_flow_policy

            data_saver = browser_flow_policy.install_for_flow("live_check", opened, driver)
        except Exception as exc:
            logger.warning(
                "[浏览器省流量] 普通查活规则安装失败，继续查活：%s",
                type(exc).__name__,
            )
        from core.browser import asset_policy as browser_asset_policy

        asset_cache = browser_asset_policy.start_auth_asset_cache(opened, driver, flow="live_check")
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
        probe_result = _execute_probe(driver, token, proxy)
        return probe_result
    except Exception as exc:
        logger.warning("[查活][Roxy] 旧 AT probe 失败: %s: %s", type(exc).__name__, str(exc)[:300])
        return _failure(
            f"Roxy AT probe {type(exc).__name__}: {str(exc)[:500]}",
            category="browser_execution",
            checked_at=checked_at,
            retryable=True,
        )
    finally:
        from core.browser import asset_policy as browser_asset_policy, traffic as browser_traffic

        browser_asset_policy.stop_asset_cache(asset_cache)
        if data_saver is not None:
            try:
                data_saver.stop()
            except Exception:
                logger.exception("[浏览器省流量] 普通查活统计停止失败")
        if opened is not None:
            browser_traffic.finish_roxy_capture(opened)
        if driver is not None:
            quit_driver(driver)
        if opened is not None:
            try:
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[查活][Roxy] 临时环境清理失败（profile 原值不写日志）")
            if context_recorder is not None:
                context_recorder.finish_roxy_profile(
                    opened,
                    status="success" if probe_result and probe_result.get("ok") else "failed",
                    result_code=(
                        "authenticated" if probe_result and probe_result.get("ok")
                        else str((probe_result or {}).get("error_category") or "probe_failed")[:160]
                    ),
                )


__all__ = ["available", "run_probe"]
