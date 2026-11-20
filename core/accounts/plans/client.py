# -*- coding: utf-8 -*-
"""ChatGPT 账号套餐、Go / Plus 优惠与额度查询。"""
from __future__ import annotations

import base64
import ipaddress
import json
import logging
import math
import socket
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote, urlparse

from curl_cffi import requests as curl_requests

from core.accounts.plans.promotion import DISCOUNT, FREE_TRIAL, parse_account_promotions, primary_plan_promotion
from core.auth.protocol.session import BrowserSession
from core.operations.runtime import OperationAccountDeactivated, OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

logger = logging.getLogger('core.chatgpt_plan')

ACCOUNTS_CHECK_PATH = "/backend-api/accounts/check/v4-2023-04-27"
USAGE_PATH = "/backend-api/wham/usage"

_QUOTA_WINDOW_LABELS = {
    "five_hour": "5小时限额",
    "weekly": "周限额",
    "monthly": "月限额",
    "daily": "日限额",
    "custom": "自定义窗口",
}
_QUOTA_KIND_ORDER = {"five_hour": 0, "daily": 1, "weekly": 2, "monthly": 3, "custom": 4}


from core.kernels.protocol.local import plan_check as _plan_kernel


def now_iso() -> str:
    return _plan_kernel.now_iso()


def normalize_token(token: str) -> str:
    return _plan_kernel.normalize_token(token)


def _mask_proxy(proxy: str) -> str:
    """返回可用于日志/API 结果的代理摘要，不泄露用户名和密码。"""
    value = str(proxy or "").strip()
    if not value:
        return ""
    try:
        parsed = urlparse(value if "://" in value else f"//{value}")
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        scheme = f"{parsed.scheme}://" if parsed.scheme else ""
        auth = "***:***@" if parsed.username or parsed.password else ""
        return f"{scheme}{auth}{host}{port}" or "***"
    except Exception:
        return "***"


def _local_proxy_status(proxy: str) -> tuple[bool, bool, str | None]:
    """检查回环代理端口；非本地代理不做预探测，避免额外网络请求。"""
    value = str(proxy or "").strip()
    if not value:
        return False, False, None
    try:
        parsed = urlparse(value if "://" in value else f"//{value}")
        host = parsed.hostname or ""
        is_loopback = host.lower() == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                is_loopback = False
        if not is_loopback:
            return False, True, None
        if not parsed.port:
            return True, False, "本地代理未配置端口"
        try:
            with socket.create_connection((host, parsed.port), timeout=0.5):
                return True, True, None
        except OSError as exc:
            return True, False, f"本地代理 {host}:{parsed.port} 未监听（{type(exc).__name__}）"
    except Exception as exc:
        return False, False, f"代理地址解析失败（{type(exc).__name__}）"


def resolve_plan_check_route(explicit_proxy: Optional[str] = None, *, session: BrowserSession | None = None) -> dict:
    """解析套餐查询的实际网络路径。

    非空 explicit_proxy 表示同一认证链已明确交付的线路；空字符串继续申请统一池线路。
    """
    if session is not None:
        # 已有会话沿用其实际线路，不额外占用一条根本不会使用的池租约。
        actual_proxy = getattr(session, "proxy", None)
        selected = actual_proxy if isinstance(actual_proxy, str) else explicit_proxy
        if not str(selected or "").strip():
            raise ValueError("已有查询会话缺少代理线路，请先从统一代理池领取")
        return {
            "proxy": selected, "proxy_mode": "session", "network_route": "proxy",
            "proxy_used": _mask_proxy(selected), "proxy_fallback_reason": None,
        }
    if explicit_proxy is not None and str(explicit_proxy or "").strip():
        selected = str(explicit_proxy).strip()
        return {
            "proxy": selected,
            "proxy_mode": "request",
            "network_route": "proxy" if selected else "direct",
            "proxy_used": _mask_proxy(selected) or None,
            "proxy_fallback_reason": None,
        }

    # 旧 CLI 的 PLAN_CHECK_PROXY_MODE/PLAN_CHECK_PROXY 只保留兼容读取；新
    # 套餐请求也必须领取统一池租约，不能自动直连或随机抽静态 URL。
    from core.proxy.account_routes import acquire_account_proxy

    route = acquire_account_proxy(purpose="plan-check")
    return {
        "proxy": route.proxy_url,
        **route.public_dict(),
        "proxy_fallback_reason": None,
        "_route": route,
    }


def _release_plan_route(route: dict | None) -> None:
    """释放 standalone 套餐查询创建的统一池租约。"""
    if not isinstance(route, dict):
        return
    selected = route.get("_route")
    if selected is not None:
        try:
            selected.release("completed")
        except Exception:
            logger.warning("套餐查询释放统一代理租约失败", exc_info=True)


def decode_jwt_payload_unverified(token: str) -> dict:
    return _plan_kernel.decode_jwt_payload_unverified(token, normalize_token=normalize_token)


def token_claims(token: str) -> dict:
    return _plan_kernel.token_claims(token, decode_jwt_payload_unverified=decode_jwt_payload_unverified)


def _common_headers(env: BrowserSession, token: str, claims: dict | None = None) -> dict[str, str]:
    return _plan_kernel._common_headers(env, token, claims, normalize_token=normalize_token, token_claims=token_claims)


def _quota_headers(env: BrowserSession, token: str, claims: dict | None = None) -> dict[str, str]:
    return _plan_kernel._quota_headers(env, token, claims, normalize_token=normalize_token, token_claims=token_claims)


def classify_quota_window(seconds: Any) -> tuple[str, str]:
    return _plan_kernel.classify_quota_window(seconds)


def _quota_number(value: Any, *, integer: bool = False) -> int | float | None:
    return _plan_kernel._quota_number(value, integer=integer)


def _parse_quota_rate_limit(rate_limit: Any) -> list[dict]:
    return _plan_kernel._parse_quota_rate_limit(
        rate_limit, _quota_number=_quota_number, classify_quota_window=classify_quota_window
    )


def parse_quota_usage(data: dict) -> dict:
    return _plan_kernel.parse_quota_usage(data, _parse_quota_rate_limit=_parse_quota_rate_limit, now_iso=now_iso)


def _remaining_request_timeout(timeout: float, deadline_at: float | None) -> float:
    return _plan_kernel._remaining_request_timeout(timeout, deadline_at, clock=time)


def _query_account_quota(
    env: BrowserSession, token: str, claims: dict, timeout: float, deadline_at: float | None = None
) -> dict:
    return _plan_kernel._query_account_quota(
        env,
        token,
        claims,
        timeout,
        deadline_at,
        _quota_headers=_quota_headers,
        _remaining_request_timeout=_remaining_request_timeout,
        now_iso=now_iso,
        parse_quota_usage=parse_quota_usage,
    )


def query_account_quota(
    token: str,
    *,
    proxy: Optional[str] = None,
    session: BrowserSession | None = None,
    timeout: float | None = None,
) -> dict:
    """Query only ``/wham/usage`` for a plan result captured in a browser flow."""
    token = normalize_token(token)
    if not token:
        return {"quota_status": "failed", "quota_checked_at": now_iso(), "quota_error": "token 为空"}
    claims = token_claims(token)
    try:
        route = resolve_plan_check_route(proxy, session=session)
        timeout_seconds, _attempts, _delay = _plan_check_settings(timeout, 1, 0)
    except Exception as exc:
        return {
            "quota_status": "failed",
            "quota_checked_at": now_iso(),
            "quota_http_status": None,
            "quota_error": f"额度查询网络配置错误: {type(exc).__name__}",
        }
    owns_session = session is None
    env = None
    try:
        env = session or BrowserSession(proxy=route["proxy"], detect_exit_geo=False)
        result = _query_account_quota(env, token, claims, timeout_seconds)
        result.update({key: value for key, value in route.items() if key != "proxy" and not key.startswith("_")})
        return result
    except Exception as exc:
        logger.debug("仅额度查询失败: %s", type(exc).__name__, exc_info=True)
        return {
            "quota_status": "failed",
            "quota_checked_at": now_iso(),
            "quota_http_status": None,
            "quota_error": f"额度查询网络错误: {type(exc).__name__}",
        }
    finally:
        if owns_session and env is not None:
            try:
                env.session.close()
            except Exception:
                pass
        _release_plan_route(route)


def parse_accounts_check(data: dict, *, token: str = "") -> dict:
    return _plan_kernel.parse_accounts_check(data, token=token, now_iso=now_iso, token_claims=token_claims)


def _plan_check_settings(
    timeout: float | None,
    max_attempts: int | None,
    retry_delay: float | None,
) -> tuple[float, int, float]:
    from config import proxy as proxy_cfg

    timeout_value = timeout if timeout is not None else getattr(proxy_cfg, "PLAN_CHECK_TIMEOUT", 15.0)
    attempts_value = max_attempts if max_attempts is not None else getattr(proxy_cfg, "PLAN_CHECK_MAX_ATTEMPTS", 2)
    delay_value = retry_delay if retry_delay is not None else getattr(proxy_cfg, "PLAN_CHECK_RETRY_DELAY", 1.5)
    return (
        max(1.0, min(60.0, float(timeout_value or 15.0))),
        max(1, min(4, int(attempts_value or 1))),
        max(0.0, min(30.0, float(delay_value or 0.0))),
    )


def _retryable_plan_error(http_status: int | None) -> bool:
    if http_status is None:
        return True
    return http_status in {408, 409, 425, 429} or http_status >= 500


def _is_proxy_transport_failure(exc: BaseException, *, selected_proxy: str, resp: Any) -> bool:
    """仅识别已选代理上的实际 curl_cffi 传输失败。"""
    if not str(selected_proxy or "").strip() or resp is not None:
        return False
    return isinstance(exc, (
        curl_requests.exceptions.ProxyError,
        curl_requests.exceptions.ConnectionError,
        curl_requests.exceptions.SSLError,
        curl_requests.exceptions.Timeout,
    ))


def _retry_wait_seconds(resp: Any, base_delay: float, attempt: int) -> float:
    try:
        retry_after = (getattr(resp, "headers", {}) or {}).get("retry-after")
        if retry_after is not None:
            return max(0.0, min(30.0, float(retry_after)))
    except (TypeError, ValueError):
        pass
    return max(0.0, min(30.0, base_delay * attempt))


def _query_promotion_checkout(result: dict, token: str, env: BrowserSession, *, country: str | None,
                              timeout: float, deadline_at: float | None, checkpoint=None,
                              claims: dict | None = None) -> None:
    """只为当前国家最优 Plus 活动预检；支付异常不改变套餐查询结论。"""
    from core.accounts.plans.checkout_probe import public_checkout_details, query_checkout_details

    promotions = result.get("account_promotions") or []
    candidates = [item for item in promotions if isinstance(item, dict)
                  and item.get("plan") == "plus" and item.get("eligible") is True]
    if not candidates:
        return
    priority = {"free_trial": 0, "discount": 1, "other_promo": 2}

    def order(item):
        percentage = item.get("discount_percentage")
        percentage = float(percentage) if isinstance(percentage, (int, float)) and not isinstance(percentage, bool) else 0
        count = item.get("duration_num_periods")
        count = float(count) if isinstance(count, (int, float)) and not isinstance(count, bool) else 0
        days = {"day": 1, "week": 7, "month": 30, "year": 365}.get(item.get("duration_period"), 0)
        return priority.get(item.get("kind"), 3), -percentage, -(count * days)

    selected = min(candidates, key=order)
    # 一次预检共享一分钟预算；已有国家总截止时间更早时服从原截止时间。
    probe_deadline = min(deadline_at, time.time() + 60) if deadline_at is not None else time.time() + 60
    try:
        details = query_checkout_details(
            token, session=env, country=country or "", campaign_id=selected.get("campaign_id") or "",
            plan="plus", timeout=timeout, deadline_at=probe_deadline,
            checkpoint=checkpoint, claims=claims,
        )
    except (OperationCancelled, OperationAccountDeactivated, OperationLeaseLost):
        raise
    except Exception:
        details = {"checkout_status": "failed", "checkout_checked_at": now_iso(),
                   "checkout_country": country, "checkout_error": "结账预检失败"}
    if details.get("proxy_transport_failure") is True:
        result["proxy_transport_failure"] = True
    selected.update(public_checkout_details(details))


def check_account_plan(
    token: str,
    *,
    proxy: Optional[str] = None,
    session: BrowserSession | None = None,
    timezone_offset_min: str = "-",
    timeout: float | None = None,
    max_attempts: int | None = None,
    retry_delay: float | None = None,
    context_recorder=None,
    deadline_at: float | None = None,
    include_checkout: bool = False,
    checkout_country: str | None = None,
    checkout_checkpoint=None,
) -> dict:
    token = normalize_token(token)
    if not token:
        return {"ok": False, "checked_at": now_iso(), "error": "token 为空"}
    claims = token_claims(token)
    if claims.get("token_expired") is True:
        return {
            "ok": False,
            "checked_at": now_iso(),
            "http_status": None,
            "error": "AT已过期/失效，请手动查活刷新",
            "needs_live_check": True,
            **{k: v for k, v in claims.items() if k != "payload"},
        }

    try:
        route = resolve_plan_check_route(proxy, session=session)
    except Exception as exc:
        return {
            "ok": False,
            "checked_at": now_iso(),
            "http_status": None,
            "error": f"套餐查询网络配置错误: {exc}",
            **{k: v for k, v in claims.items() if k != "payload"},
        }
    route_meta = {k: v for k, v in route.items() if k != "proxy" and not k.startswith("_")}
    try:
        timeout_seconds, attempts, base_delay = _plan_check_settings(timeout, max_attempts, retry_delay)
    except Exception as exc:
        _release_plan_route(route)
        return {
            "ok": False,
            "checked_at": now_iso(),
            "http_status": None,
            "error": f"套餐查询重试配置错误: {exc}",
            "retryable": False,
            **route_meta,
            **{k: v for k, v in claims.items() if k != "payload"},
        }

    last_result: dict | None = None
    for attempt in range(1, attempts + 1):
        env = None
        resp = None
        probe_result = None
        owns_session = session is None
        try:
            # 套餐查询只需要稳定的请求头，不需要额外访问 IP 地理信息接口。
            env = session or BrowserSession(proxy=route["proxy"], detect_exit_geo=False)
            if context_recorder is not None:
                context_recorder.open_protocol_session(
                    env,
                    route_attempt_no=attempt,
                    auth_method="access_token",
                )
            resp = _plan_kernel.request_accounts_check(
                env, headers=lambda: _common_headers(env, token, claims),
                timezone_offset_min=timezone_offset_min,
                timeout=lambda: _remaining_request_timeout(timeout_seconds, deadline_at),
            )
            response_text = resp.text or ""
            http_status = int(resp.status_code)
            if not (200 <= http_status < 300):
                is_auth_expired = http_status == 401
                last_result = {
                    "ok": False,
                    "checked_at": now_iso(),
                    "http_status": http_status,
                    "error": "AT已过期/失效，请手动查活刷新" if is_auth_expired else f"HTTP {http_status}",
                    "response_preview": response_text[:500],
                    "retryable": _retryable_plan_error(http_status),
                    "token_expired": True if is_auth_expired else claims.get("token_expired"),
                    "needs_live_check": True if is_auth_expired else False,
                }
                probe_result = last_result
            else:
                try:
                    data: Any = resp.json()
                except Exception:
                    data = json.loads(response_text) if response_text.strip().startswith(("{", "[")) else None
                if not isinstance(data, dict):
                    last_result = {
                        "ok": False,
                        "checked_at": now_iso(),
                        "http_status": http_status,
                        "error": "响应不是 JSON 对象",
                        "response_preview": response_text[:500],
                        "retryable": True,
                    }
                    probe_result = last_result
                else:
                    parsed = parse_accounts_check(data, token=token)
                    parsed["http_status"] = http_status
                    parsed["attempt_count"] = attempt
                    parsed["max_attempts"] = attempts
                    parsed["request_timeout"] = timeout_seconds
                    parsed["retryable"] = False
                    parsed.update(route_meta)
                    # 额度接口失败不应让套餐查询失败；它有独立状态，便于列表
                    # 展示“套餐已查到、额度暂不可用”以及保留上次成功快照。
                    parsed.update(_query_account_quota(env, token, claims, timeout_seconds, deadline_at))
                    if deadline_at is not None and time.time() > deadline_at:
                        raise TimeoutError("国家查询总期限已到")
                    if include_checkout:
                        _query_promotion_checkout(
                            parsed, token, env, country=checkout_country, timeout=timeout_seconds,
                            deadline_at=deadline_at, checkpoint=checkout_checkpoint, claims=claims,
                        )
                    probe_result = parsed
                    _release_plan_route(route)
                    return parsed
        except (OperationCancelled, OperationAccountDeactivated, OperationLeaseLost):
            _release_plan_route(route)
            raise
        except Exception as exc:
            logger.debug("套餐查询失败: %s: %s", type(exc).__name__, exc, exc_info=True)
            last_result = {
                "ok": False,
                "checked_at": now_iso(),
                "http_status": int(resp.status_code) if resp is not None and getattr(resp, "status_code", None) else None,
                "error": f"{type(exc).__name__}: {exc}",
                "retryable": True,
            }
            if _is_proxy_transport_failure(exc, selected_proxy=route["proxy"], resp=resp):
                last_result["proxy_transport_failure"] = True
            probe_result = last_result
        finally:
            if context_recorder is not None and env is not None:
                context_recorder.finish_session(
                    env,
                    status="success" if probe_result and probe_result.get("ok") else "failed",
                    result_code=(
                        "authenticated" if probe_result and probe_result.get("ok")
                        else str((probe_result or {}).get("error") or "probe_failed")[:160]
                    ),
                )
            if env is not None and owns_session:
                try:
                    env.close()
                except Exception:
                    pass

        last_result = last_result or {"ok": False, "checked_at": now_iso(), "error": "未知错误", "retryable": True}
        last_result.update({
            "attempt_count": attempt,
            "max_attempts": attempts,
            "request_timeout": timeout_seconds,
            **route_meta,
            **{k: v for k, v in claims.items() if k != "payload"},
        })
        if not last_result.get("retryable") or attempt >= attempts:
            _release_plan_route(route)
            return last_result

        wait_seconds = _retry_wait_seconds(resp, base_delay, attempt)
        logger.warning(
            "套餐查询临时失败，第 %s/%s 次，%.1fs 后重试: %s",
            attempt,
            attempts,
            wait_seconds,
            last_result.get("error"),
        )
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    _release_plan_route(route)
    return last_result or {
        "ok": False,
        "checked_at": now_iso(),
        "http_status": None,
        "error": "套餐查询未执行",
        "retryable": False,
        **route_meta,
        **{k: v for k, v in claims.items() if k != "payload"},
    }
