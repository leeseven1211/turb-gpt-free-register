# -*- coding: utf-8 -*-
"""账号查活后台队列：协议 BrowserSession 指纹环境 + 独立日志。"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from core import db
from core.account_liveness import check_account_liveness, log_path
from core.chatgpt_plan import check_account_plan, token_claims
from core.openai_auth import detect_account_unusable_text

logger = logging.getLogger(__name__)

_WORKERS = 3
_QUEUE_LIMIT = 500
_EXECUTOR = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="live-check")
_QUEUE_SLOTS = threading.BoundedSemaphore(_QUEUE_LIMIT)
_RUNNING: set[int] = set()
_LOCK = threading.Lock()


def is_checking(email: str) -> bool:
    acc = db.get_account_by_email(email)
    if not acc:
        return False
    return str(acc.get("live_check_status") or "") in {"queued", "running"}


def _append_log(email: str, line: str, *, clear: bool = False) -> None:
    p = log_path(email)
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H:%M:%S")
    mode = "w" if clear else "a"
    with p.open(mode, encoding="utf-8") as f:
        f.write(f"{stamp} [INFO] {line}\n")


def _token_probe_retryable(result: dict) -> bool:
    """只有网络/风控类结果才值得换线路；Token 失效直接转邮箱重新登录。"""
    if result.get("needs_live_check") or result.get("token_expired") is True:
        return False
    status = result.get("http_status")
    if status is None:
        return True
    try:
        status = int(status)
    except (TypeError, ValueError):
        return False
    return status in {403, 408, 409, 425, 429} or status >= 500


def _run_live_check(*, account_id: int, email: str, proxy: str | None, trigger: str) -> dict:
    account_route = None
    route: dict = {}
    try:
        with _LOCK:
            _RUNNING.add(int(account_id))
        if not db.mark_account_live_check_running(account_id):
            _append_log(email, "[查活] 账号已删除或查活状态已被重置，取消执行")
            return {"ok": False, "status": "failed", "error": "账号已删除或查活状态已被重置"}
        from core.account_proxy import acquire_account_proxy

        def acquire_retry_route(attempt: int) -> str:
            """网络预检每次重试都释放旧租约并申请新线路。"""
            nonlocal account_route, route
            if account_route is not None:
                account_route.release(reason=f"live-check-{account_id}-preflight-rotate")
            account_route = acquire_account_proxy(
                account_id=account_id,
                email=email,
                purpose="live-check",
            )
            route = account_route.public_dict()
            _append_log(
                email,
                f"[查活] 查活线路 {attempt}/4 "
                f"network_route={route.get('network_route')} proxy_mode={route.get('proxy_mode')} "
                f"proxy_used={route.get('proxy_used') or '-'} "
                f"fallback_reason={route.get('proxy_fallback_reason') or '-'}",
            )
            return account_route.proxy_url

        def acquire_explicit_route() -> str:
            """显式代理只申请一次，后续步骤严格复用调用方指定线路。"""
            nonlocal account_route, route
            if account_route is None:
                account_route = acquire_account_proxy(
                    account_id=account_id,
                    email=email,
                    purpose="live-check",
                    explicit_proxy=proxy,
                )
                route = account_route.public_dict()
            return account_route.proxy_url

        # 先验证数据库里现有 AT。accounts/check 是已登录接口，返回 200 足以确认
        # 账号仍可正常访问；只有 AT 过期/失效时才需要走容易受 CF 影响的邮箱重登录。
        account = db.get_account(account_id) or {}
        saved_access_token = str(account.get("access_token") or "").strip()
        saved_claims = token_claims(saved_access_token) if saved_access_token else {}
        result = None
        if saved_access_token and saved_claims.get("token_expired") is not True:
            probe_attempts = 4 if proxy is None else 1
            _append_log(email, "[查活] 优先验证现有 accessToken；有效则无需重复发送邮箱验证码")
            for attempt in range(1, probe_attempts + 1):
                selected_proxy = acquire_retry_route(attempt) if proxy is None else acquire_explicit_route()
                probe = check_account_plan(
                    saved_access_token,
                    proxy=selected_proxy,
                    max_attempts=1,
                )
                if probe.get("ok"):
                    result = {
                        "ok": True,
                        "status": "live",
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "access_token": saved_access_token,
                        "session": {
                            "account": {"planType": probe.get("current_plan_type")},
                        },
                        "proxy_used": selected_proxy or None,
                        "validation_method": "access_token",
                    }
                    _append_log(
                        email,
                        f"[查活] accessToken 验证成功：HTTP {probe.get('http_status') or 200} "
                        f"plan={probe.get('current_plan_type') or 'unknown'}",
                    )
                    break

                unusable_code = detect_account_unusable_text(
                    f"{probe.get('error') or ''} {probe.get('response_preview') or ''}"
                )
                if unusable_code:
                    result = {
                        "ok": False,
                        "status": "deactivated",
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "error": unusable_code,
                        "validation_method": "access_token",
                    }
                    break

                _append_log(
                    email,
                    f"[查活] accessToken 验证未通过（{attempt}/{probe_attempts}）："
                    f"{str(probe.get('error') or '未知错误')[:220]}",
                )
                if not _token_probe_retryable(probe) or attempt >= probe_attempts:
                    _append_log(email, "[查活] 现有 Token 无法确认状态，转邮箱 OTP 重新登录刷新")
                    break

        if result is None and proxy is None:
            # WebUI 默认调用由账号代理配置选路，重试时允许真正轮换线路。
            _append_log(email, f"[查活] 开始后台执行 trigger={trigger}，网络预检失败时将轮换代理")
            result = check_account_liveness(
                email,
                proxy=None,
                clear_log=False,
                proxy_supplier=acquire_retry_route,
            )
        elif result is None:
            # API 显式传入的代理（包括空字符串直连）尊重调用方选择，不擅自改线。
            selected_proxy = acquire_explicit_route()
            _append_log(
                email,
                "[查活] 开始后台执行 "
                f"trigger={trigger} network_route={route.get('network_route')} "
                f"proxy_mode={route.get('proxy_mode')} proxy_used={route.get('proxy_used') or '-'} "
                f"fallback_reason={route.get('proxy_fallback_reason') or '-'}",
            )
            result = check_account_liveness(email, proxy=selected_proxy, clear_log=False)
        result.update({
            "proxy_provider": route.get("proxy_provider"),
            "proxy_region": route.get("proxy_region"),
            "network_route": route.get("network_route"),
            "proxy_used": route.get("proxy_used"),
        })
        db.update_account_liveness(account_id, result)
        if result.get("ok"):
            if result.get("validation_method") == "access_token":
                _append_log(email, "[查活] 完成：账号正常，现有 accessToken 已通过在线验证")
            else:
                _append_log(email, "[查活] 完成：账号正常，已通过邮箱登录刷新 accessToken")
        elif result.get("status") == "deactivated":
            _append_log(email, f"[查活] 完成：账号已废 {result.get('error') or ''}")
        else:
            _append_log(email, f"[查活] 完成：失败 {result.get('error') or ''}")
        return result
    except Exception as exc:
        result = {
            "ok": False,
            "status": "failed",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
        }
        try:
            db.update_account_liveness(account_id, result)
        except Exception:
            logger.exception("[查活] 写入异常状态失败: account_id=%s", account_id)
        logger.exception("[查活] 后台异常: %s", email)
        try:
            _append_log(email, f"[查活] 后台异常：{result['error']}")
        except Exception:
            pass
        return result
    finally:
        if account_route is not None:
            account_route.release(reason=f"live-check-{account_id}")
        with _LOCK:
            _RUNNING.discard(int(account_id))
        _QUEUE_SLOTS.release()


def enqueue_account_live_check(*, account_id: int, email: str, trigger: str = "manual", proxy: str | None = None) -> dict:
    account_id = int(account_id)
    email = str(email or "").strip()
    if not email:
        return {"accepted": False, "busy": False, "error": "email 为空"}
    if not _QUEUE_SLOTS.acquire(blocking=False):
        return {"accepted": False, "busy": False, "queue_full": True, "error": "查活队列已满，请稍后重试"}
    if not db.claim_account_live_check(acc_id=account_id, trigger=trigger):
        _QUEUE_SLOTS.release()
        return {"accepted": False, "busy": True, "error": "该账号正在查活"}

    _append_log(email, f"[查活] 已入队 account_id={account_id} trigger={trigger}", clear=True)
    try:
        _EXECUTOR.submit(
            _run_live_check,
            account_id=account_id,
            email=email,
            proxy=proxy,
            trigger=str(trigger or "manual"),
        )
    except Exception as exc:
        _QUEUE_SLOTS.release()
        result = {
            "ok": False,
            "status": "failed",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"查活入队失败: {type(exc).__name__}: {str(exc)[:160]}",
        }
        db.update_account_liveness(account_id, result)
        _append_log(email, result["error"])
        return {"accepted": False, "busy": False, "error": result["error"]}

    return {
        "accepted": True,
        "busy": False,
        "account_id": account_id,
        "email": email,
        "status": "queued",
        "trigger": str(trigger or "manual"),
    }


def queue_settings() -> dict:
    return {"workers": _WORKERS, "queue_limit": _QUEUE_LIMIT}
