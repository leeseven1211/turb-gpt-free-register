# -*- coding: utf-8 -*-
"""协议重置密码（忘记密码流程）。

流程（已用真实账号验证）：
1. 账号 AT 过期时，先跑一次现有刷新 AT，建立可重置的登录状态
2. 新会话：登录预检 -> GET /reset-password
3. POST /api/accounts/password/send-otp（空 JSON，邮箱从会话取）
4. 邮箱取码 -> POST /api/accounts/email-otp/validate
5. 生成新密码，先写本地候选检查点
6. POST /api/accounts/password/reset（sentinel flow=password_reset）
7. 用新密码重新登录校验，成功后才确认检查点
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from core.accounts.liveness.protocol.legacy import _network_preflight_with_retry
from core.auth.protocol.openai_auth import (
    build_sentinel_header,
    generate_registration_password,
    request_sentinel_token,
)
from core.auth.protocol.session import BrowserSession
from core.email.provider import wait_for_otp
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

logger = logging.getLogger(__name__)

_AUTH = "https://auth.openai.com"
_RESET_PAGE = _AUTH + "/reset-password"
_SEND_OTP = _AUTH + "/api/accounts/password/send-otp"
_OTP_VALIDATE = _AUTH + "/api/accounts/email-otp/validate"
_PASSWORD_RESET = _AUTH + "/api/accounts/password/reset"


def _error(code: str, category: str = "auth", *, message: str = "", retryable: bool = False) -> dict:
    return {
        "ok": False,
        "status": "failed",
        "error": code,
        "error_category": category,
        "retryable": bool(retryable),
        "message": message or code,
        "live_check_driver": "protocol_reset",
        "auth_method": "protocol_reset",
    }


def _session_stale(account: dict) -> bool:
    from core.accounts.plans.client import token_claims

    token = str(account.get("access_token") or "").strip()
    if not token:
        return True
    try:
        claims = token_claims(token)
    except Exception:
        return True
    return claims.get("token_expired") is True


def _refresh_before_reset(email: str, *, proxy, proxy_supplier) -> dict | None:
    """AT 过期/缺失时先刷新一次；成功返回 None，失败返回错误字典。

    刷新会用账号最近一次登录的设备画像，成功后把“刚刚用过的那套画像”写回
    会话缓存，改密随后原样复用，保证整条链路是同一台设备。
    """
    from core.accounts.liveness import service as live_service

    try:
        runner = live_service._refresh_execution_runner(driver)
        result = runner(
            email,
            proxy=proxy,
            proxy_supplier=proxy_supplier,
            on_remote_request_started=None,
        )
    except (OperationCancelled, OperationLeaseLost):
        raise
    except Exception as exc:  # noqa: BLE001
        return _error(
            "password_change_session_required", "network",
            message=f"改密前刷新 AT 失败：{type(exc).__name__}",
            retryable=True,
        )
    if not isinstance(result, dict) or not result.get("ok"):
        code = str((result or {}).get("error") or "password_change_session_required")
        return _error(code, str((result or {}).get("error_category") or "network"),
                      message=str((result or {}).get("error") or "改密前刷新 AT 未成功"),
                      retryable=bool((result or {}).get("retryable")))
    return None


def _send_reset_otp(session: BrowserSession, *, report=None, check=None) -> None:
    headers = session.get_auth_headers(referer=_RESET_PAGE)
    response = session.post(_SEND_OTP, headers=headers, data="{}", allow_redirects=False)
    if response.status_code != 200:
        body = (response.text or "")[:240]
        if response.status_code == 429:
            raise RuntimeError(f"reset_rate_limited:{body}")
        raise RuntimeError(f"password_reset_send_otp_failed:HTTP {response.status_code}:{body}")


def _wait_reset_otp(email: str, after_ts: float, *, check=None) -> str:
    from config import email as email_cfg

    wait = max(1, int(getattr(email_cfg, "OTP_MAX_WAIT", 300) or 300))
    if callable(check):
        check()
    try:
        return wait_for_otp(email, after_ts=after_ts, max_wait=wait)
    except (OperationCancelled, OperationLeaseLost):
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"password_reset_otp_timeout:{type(exc).__name__}") from exc


class _RetrySendOtp(RuntimeError):
    """保留兼容：调用方按重发次数重新发起 send-otp。"""


def run_protocol_password_reset(
    email: str,
    *,
    proxy=None,
    proxy_supplier=None,
    execution_fence=None,
    checkpoint=None,
    report=None,
    refresh_before_reset: bool = True,
    new_password: str | None = None,
) -> dict:
    """走忘记密码流程重置账号密码；返回与账号补全一致的结果字典。"""
    from core import db

    email = str(email or "").strip()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    account = db.get_account_by_email(email) or {}
    if not account:
        return _error("account_not_found", "configuration", message="账号不存在")

    def note(stage: str, message: str, state: str = "running", **detail):
        if callable(report):
            try:
                report(stage=stage, state=state, message=message, detail=detail or None)
            except Exception:
                pass

    if refresh_before_reset and _session_stale(account):
        note("refresh_at", "改密前先刷新 AT，建立可重置的登录状态")
        failure = _refresh_before_reset(email, proxy=proxy, proxy_supplier=proxy_supplier)
        if failure is not None:
            return failure
        account = db.get_account_by_email(email) or account

    # 复用上次登录的指纹与 Cookie，避免“新设备 + 改密”触发 sensitive_action_cooldown。
    from core.storage.accounts import protocol_sessions

    cached = {}
    try:
        cached = protocol_sessions.load_session(int(account.get("id") or 0), email) or {}
    except Exception:
        cached = {}
    identity = None
    cached_profile = cached.get("browser_profile") if isinstance(cached.get("browser_profile"), dict) else {}
    if cached.get("device_id") and cached_profile:
        identity = {
            "device_id": str(cached.get("device_id")),
            "browser_profile": dict(cached_profile),
        }
        if cached_profile.get("impersonate"):
            identity["chrome_identity"] = {"impersonate": str(cached_profile["impersonate"])}

    session: BrowserSession | None = None
    cancelled = False
    try:
        if callable(checkpoint):
            checkpoint()
        try:
            session, authorize = _network_preflight_with_retry(
                email, proxy, proxy_supplier=proxy_supplier, identity=identity,
            )
        except ValueError:
            # 画像不完整时退回无 identity，至少保证流程可跑。
            session, authorize = _network_preflight_with_retry(
                email, proxy, proxy_supplier=proxy_supplier,
            )
        for item in cached.get("cookies") or []:
            try:
                session.session.cookies.set(
                    str(item["name"]), str(item["value"]),
                    domain=str(item["domain"]), path=str(item.get("path") or "/"),
                )
            except Exception:
                continue
        if callable(checkpoint):
            checkpoint()
        session.get(authorize, headers=session.get_auth_navigate_headers(referer="https://chatgpt.com/"),
                    allow_redirects=True)
        session.get(_RESET_PAGE, headers=session.get_auth_navigate_headers(referer=_AUTH + "/log-in/password"),
                    allow_redirects=True)
        note("password_reset", "已进入密码重置页面")
        # 记住这次改密实际使用的设备（Python 协议画像），下次刷新/改密可原样复用。
        try:
            from core.accounts.liveness.protocol import v3 as _v3

            payload = _v3._cookie_payload(session, {"user": {"id": account.get("user_id") or ""},
                                                  "account": {"id": account.get("chatgpt_account_id") or ""}})

            protocol_sessions.save_session(int(account.get("id") or 0), email, payload)
        except Exception:
            logger.warning("[改密] 设备画像缓存保存失败", exc_info=True)

        from config import email as email_cfg

        attempts = 1 + max(0, int(getattr(email_cfg, "OTP_RESEND_COUNT", 1) or 0))
        otp_code = None
        last_otp_error = None
        for attempt in range(1, attempts + 1):
            if callable(checkpoint):
                checkpoint()
            _send_reset_otp(session)
            note("password_reset_otp", f"已发送重置验证码（{attempt}/{attempts}）")
            try:
                otp_code = _wait_reset_otp(email, time.time(), check=checkpoint)
                break
            except Exception as exc:  # noqa: BLE001 - 取码超时按配置重发
                last_otp_error = exc
                if attempt >= attempts:
                    break
                note("password_reset_otp", f"验证码未到，重新发送（{attempt}/{attempts}）")
        if not otp_code:
            return _error("password_reset_otp_timeout", "email",
                          message=f"重置验证码超时：{last_otp_error}", retryable=True)

        headers = session.get_auth_headers(referer=_AUTH + "/email-verification")
        response = session.post(_OTP_VALIDATE, headers=headers,
                                data=json.dumps({"code": otp_code}), allow_redirects=False)
        if response.status_code != 200:
            return _error("password_reset_otp_rejected", "email", message=f"验证码被拒绝：HTTP {response.status_code}")
        try:
            payload = response.json() or {}
        except Exception:
            payload = {}
        continue_url = str(payload.get("continue_url") or "")
        if continue_url:
            session.get(continue_url, headers=session.get_auth_navigate_headers(referer=_AUTH + "/email-verification"),
                        allow_redirects=True)
        note("password_reset", "验证码通过，准备提交新密码")

        password = str(new_password or generate_registration_password())
        if not db.update_account_login_password(email, password, source="protocol_reset", confirmed=False):
            return _error("password_reset_checkpoint_failed", "runtime", message="新密码候选写入失败")
        note("login_password", "新密码候选已写入本地，正在提交重置", checkpoint="password_reset_submitted")

        sentinel = request_sentinel_token(session, "password_reset")
        sentinel_header, so_header = build_sentinel_header(session, sentinel, "password_reset")
        headers = session.get_auth_headers(referer=_AUTH + "/reset-password/new-password")
        headers["openai-sentinel-token"] = sentinel_header
        if so_header:
            headers["openai-sentinel-so-token"] = so_header
        response = session.post(_PASSWORD_RESET, headers=headers,
                                data=json.dumps({"password": password}), allow_redirects=False)
        if response.status_code != 200:
            if response.status_code == 429:
                return _error("password_reset_rate_limited", "network", message="重置请求被限流", retryable=True)
            if response.status_code in {400, 401, 403}:
                return _error("password_reset_rejected", "auth",
                              message=f"重置请求被拒绝：HTTP {response.status_code}")
            return _error("password_reset_request_unknown", "network",
                          message=f"重置结果未知：HTTP {response.status_code}", retryable=True)
        note("password_reset", "重置请求已接受，开始用新密码重新登录验证", state="success")

        from core.accounts.liveness import service as live_service

        driver = live_service._resolve_refresh_driver(None)
        runner = live_service._refresh_execution_runner(driver)
        verify = runner(email, proxy=proxy, proxy_supplier=proxy_supplier)
        if not isinstance(verify, dict) or not verify.get("ok"):
            return _error(
                "password_reset_unconfirmed", "auth",
                message="新密码已提交，但重新登录未成功",
                retryable=False,
            )
        db.update_account_login_password(email, password, source="protocol_reset", confirmed=True)
        note("login_password_result", "新密码已重新登录验证并写入本地", state="success",
             checkpoint="password_change_confirmed")
        return {
            "ok": True,
            "status": "success",
            "message": "密码重置完成",
            "checked_at": checked_at,
            "live_check_driver": "protocol_reset",
            "auth_method": "protocol_reset",
            "password_reset": "confirmed",
            "password_confirmed": True,
            "access_token": str(verify.get("access_token") or ""),
        }
    except (OperationCancelled, OperationLeaseLost):
        cancelled = True
        raise
    except Exception as exc:  # noqa: BLE001
        if cancelled:
            raise
        text = str(exc)
        code = "password_reset_failed"
        category = "runtime"
        retryable = False
        if text.startswith("reset_rate_limited"):
            code, category, retryable = "password_reset_rate_limited", "network", True
        elif text.startswith("password_reset_send_otp_failed"):
            code, category, retryable = "password_reset_send_otp_failed", "network", True
        elif text.startswith("password_reset_otp_timeout"):
            code, category, retryable = "password_reset_otp_timeout", "email", True
        return _error(code, category, message=text[:300], retryable=retryable)
    finally:
        if session is not None:
            try:
                session.session.close()
            except Exception:
                pass
