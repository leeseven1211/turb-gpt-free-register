# -*- coding: utf-8 -*-
"""协议重置密码（忘记密码流程）。

协议步骤：
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
from contextlib import nullcontext
from datetime import datetime, timezone

from core.accounts.liveness.protocol.legacy import _network_preflight_with_retry
from core.auth.protocol.openai_auth import (
    build_sentinel_header,
    generate_registration_password,
    request_sentinel_token,
)
from core.auth.protocol.session import BrowserSession
from core.auth.state_machine import CancellationRequested
from core.email.provider import wait_for_otp
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

logger = logging.getLogger(__name__)

_AUTH = "https://auth.openai.com"
_RESET_PAGE = _AUTH + "/reset-password"
_SEND_OTP = _AUTH + "/api/accounts/password/send-otp"
_OTP_VALIDATE = _AUTH + "/api/accounts/email-otp/validate"
_PASSWORD_RESET = _AUTH + "/api/accounts/password/reset"


def _error(
    code: str,
    category: str = "auth",
    *,
    message: str = "",
    retryable: bool = False,
    request_unknown: bool = False,
) -> dict:
    result = {
        "ok": False,
        "status": "failed",
        "error": code,
        "error_category": category,
        "retryable": bool(retryable),
        "message": message or code,
        "live_check_driver": "protocol_reset",
        "auth_method": "protocol_reset",
    }
    if request_unknown:
        result.update(request_unknown=True, outcome="request_unknown", reconcile_required=True)
    return result


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


def _refresh_before_reset(
    email: str,
    *,
    proxy,
    proxy_supplier,
    account: dict | None = None,
    password_override: str | None = None,
) -> dict | None:
    """AT 过期/缺失时先刷新一次；成功返回 None，失败返回错误字典。

    刷新会用账号最近一次登录的设备画像，成功后把“刚刚用过的那套画像”写回
    会话缓存，改密随后原样复用，保证整条链路是同一台设备。
    """
    from core.accounts.liveness import service as live_service
    from core.accounts.credentials import (
        get_account_totp_secret_candidate, override_account_login_credentials,
    )

    try:
        driver = live_service._resolve_refresh_driver(None)
        runner = live_service._refresh_execution_runner(driver)
        credentials = (
            override_account_login_credentials(
                email, password_override, get_account_totp_secret_candidate(account),
            )
            if password_override and isinstance(account, dict)
            else nullcontext()
        )
        with credentials:
            result = runner(
                email,
                proxy=proxy,
                proxy_supplier=proxy_supplier,
                on_remote_request_started=None,
            )
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
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
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"password_reset_otp_timeout:{type(exc).__name__}") from exc


class _RetrySendOtp(RuntimeError):
    """保留兼容：调用方按重发次数重新发起 send-otp。"""


def _manual_recovery_owner(email: str, account: dict, execution_fence: dict | None) -> dict | None:
    """把账号任务的执行围栏投影为密码检查点 owner。"""
    fence = execution_fence if isinstance(execution_fence, dict) else {}
    if not all(fence.get(key) for key in ("run_id", "execution_id", "lease_token")):
        return None
    try:
        account_id = int(account.get("id") or 0)
        run_id = int(fence["run_id"])
    except (TypeError, ValueError):
        return None
    if account_id < 1 or run_id < 1:
        return None
    return {
        "email": email,
        "account_id": account_id,
        "purpose": "manual",
        "operation_run_id": run_id,
        "operation_execution_id": str(fence["execution_id"]),
        "operation_lease_token": str(fence["lease_token"]),
        "attempt_id": None,
        "registration_run_id": None,
        "registration_execution_id": None,
    }


def _invalidate_reset_session(account: dict, email: str) -> None:
    """验证新密码前清除旧 Cookie，避免把会话复用当成密码验证。"""
    from core.storage.accounts import protocol_sessions

    protocol_sessions.invalidate_session(int(account.get("id") or 0), email)


def _run_password_verification(
    email: str,
    password: str,
    *,
    account: dict,
    proxy,
    proxy_supplier,
) -> dict:
    """用本轮候选密码重新认证，并返回带密码证据的结果。"""
    from core.accounts.liveness import service as live_service
    from core.accounts.credentials import (
        get_account_totp_secret_candidate, override_account_login_credentials,
    )

    _invalidate_reset_session(account, email)
    driver = live_service._resolve_refresh_driver(None)
    runner = live_service._refresh_execution_runner(driver)
    with override_account_login_credentials(
        email, password, get_account_totp_secret_candidate(account),
    ):
        return runner(email, proxy=proxy, proxy_supplier=proxy_supplier)


def _password_verification_accepted(result: dict) -> bool:
    """只接受明确的密码认证成功，不接受 Cookie 或未提交密码的会话。"""
    if not isinstance(result, dict) or result.get("ok") is not True:
        return False
    if str(result.get("password_auth_status") or "").strip().lower() != "verified":
        return False
    auth_method = str(result.get("auth_method") or "").strip().lower()
    return bool(auth_method) and "session_cookie" not in auth_method and result.get("session_reused") is not True


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
    owner = _manual_recovery_owner(email, account, execution_fence)
    if owner is None:
        return _error(
            "password_reset_execution_fence_missing",
            "runtime",
            message="改密需要有效的账号任务执行租约",
        )
    from core.auth.browser.password_recovery import PasswordRecoverySession
    from core.storage.accounts import password_recovery as recovery_store

    recovery = PasswordRecoverySession(**owner)
    try:
        recovery.resume()
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except recovery_store.PasswordRecoveryError as exc:
        return _error(
            "password_reset_checkpoint_failed",
            "runtime",
            message=f"改密检查点不可用：{exc.code}",
        )

    def note(stage: str, message: str, state: str = "running", **detail):
        if callable(report):
            try:
                report(stage=stage, state=state, message=message, detail=detail or None)
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception:
                pass

    if refresh_before_reset and _session_stale(account):
        note("refresh_at", "改密前先刷新 AT，建立可重置的登录状态")
        pending_password = (
            str(getattr(recovery.checkpoint, "password", "") or "")
            if recovery.checkpoint is not None
            else ""
        )
        failure = _refresh_before_reset(
            email,
            proxy=proxy,
            proxy_supplier=proxy_supplier,
            account=account,
            password_override=pending_password or None,
        )
        if failure is not None:
            return failure
        account = db.get_account_by_email(email) or account

    # 复用账号最后一次使用的设备指纹（设备表优先，其次是会话缓存里的 Cookie）。
    from core.storage.accounts import device_profiles, protocol_sessions

    account_id = int(account.get("id") or 0)
    cached = {}
    try:
        cached = protocol_sessions.load_session(account_id, email) or {}
    except Exception:
        cached = {}
    remembered = {}
    try:
        remembered = device_profiles.load_profile(account_id, email) or {}
    except Exception:
        remembered = {}
    device = remembered or cached
    identity = None
    device_profile = device.get("browser_profile") if isinstance(device.get("browser_profile"), dict) else {}
    if device.get("device_id") and device_profile:
        identity = {
            "device_id": str(device.get("device_id")),
            "browser_profile": dict(device_profile),
        }
        impersonate = device_profile.get("impersonate") or device.get("impersonate")
        if impersonate:
            identity["chrome_identity"] = {"impersonate": str(impersonate)}

    session: BrowserSession | None = None
    remote_dispatched = False

    def mark_unknown() -> None:
        checkpoint_state = recovery.checkpoint
        if checkpoint_state is None or checkpoint_state.state != "started":
            return
        recovery.mark_unknown()

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
            device_profiles.remember_session(
                int(account.get("id") or 0), email, payload, origin="password_reset",
            )
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
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
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

        try:
            password = recovery.prepare(
                lambda: str(new_password) if new_password is not None else generate_registration_password(),
            )
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except recovery_store.PasswordRecoveryError as exc:
            return _error(
                "password_reset_checkpoint_failed",
                "runtime",
                message=f"新密码候选写入失败：{exc.code}",
            )
        note("login_password", "新密码候选已写入本地，正在提交重置", checkpoint="password_reset_submitted")

        sentinel = request_sentinel_token(session, "password_reset")
        sentinel_header, so_header = build_sentinel_header(session, sentinel, "password_reset")
        headers = session.get_auth_headers(referer=_AUTH + "/reset-password/new-password")
        headers["openai-sentinel-token"] = sentinel_header
        if so_header:
            headers["openai-sentinel-so-token"] = so_header
        try:
            # unknown 重跑仍沿用同一候选，但每次最终 POST 前重新校验 Run 与租约。
            password = recovery.prepare(lambda: password)
            if recovery.checkpoint is not None and recovery.checkpoint.state == "prepared":
                recovery.mark_started()
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except recovery_store.PasswordRecoveryError as exc:
            return _error(
                "password_reset_checkpoint_failed",
                "runtime",
                message=f"最终提交前检查点校验失败：{exc.code}",
            )
        remote_dispatched = True
        response = session.post(_PASSWORD_RESET, headers=headers,
                                data=json.dumps({"password": password}), allow_redirects=False)
        if response.status_code != 200:
            if response.status_code == 429:
                return _error("password_reset_rate_limited", "network", message="重置请求被限流", retryable=True)
            if response.status_code in {400, 401, 403}:
                return _error("password_reset_rejected", "auth",
                              message=f"重置请求被拒绝：HTTP {response.status_code}")
            mark_unknown()
            return _error("password_reset_request_unknown", "network",
                          message=f"重置结果未知：HTTP {response.status_code}", retryable=True,
                          request_unknown=True)
        note("password_reset", "重置请求已接受，开始用新密码重新登录验证", state="success")

        try:
            verify = _run_password_verification(
                email,
                password,
                account=account,
                proxy=proxy,
                proxy_supplier=proxy_supplier,
            )
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except Exception as exc:  # noqa: BLE001
            mark_unknown()
            return _error(
                "password_reset_unconfirmed",
                "auth",
                message=f"新密码重新登录失败：{type(exc).__name__}",
                retryable=True,
                request_unknown=True,
            )
        if not _password_verification_accepted(verify):
            mark_unknown()
            return _error(
                "password_reset_unconfirmed", "auth",
                message="新密码已提交，但未取得明确的密码认证成功证据",
                retryable=False,
                request_unknown=True,
            )
        try:
            confirmed_password = recovery.confirm("password_change_response")
            checkpoint_state = recovery.checkpoint
            if (not isinstance(confirmed_password, str)
                    or confirmed_password != password
                    or checkpoint_state is None
                    or str(getattr(checkpoint_state, "state", "")).strip() != "confirmed"):
                return _error(
                    "password_reset_checkpoint_failed",
                    "runtime",
                    message="新密码确认写回未返回已确认检查点",
                    request_unknown=True,
                )
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except recovery_store.PasswordRecoveryError as exc:
            return _error(
                "password_reset_checkpoint_failed",
                "runtime",
                message=f"新密码确认写回失败：{exc.code}",
                request_unknown=True,
            )
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
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        if remote_dispatched:
            try:
                mark_unknown()
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception:
                logger.warning("[改密] 取消后未知回执状态保存失败", exc_info=True)
        raise
    except Exception as exc:  # noqa: BLE001
        if remote_dispatched:
            try:
                mark_unknown()
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception:
                logger.warning("[改密] 未知回执状态保存失败", exc_info=True)
            return _error(
                "password_reset_request_unknown",
                "network",
                message=f"重置结果未知：{type(exc).__name__}",
                retryable=True,
                request_unknown=True,
            )
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
