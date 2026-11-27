# -*- coding: utf-8 -*-
"""协议重置密码（忘记密码流程）。

协议步骤：
1. 账号 AT 过期时，先跑一次现有刷新 AT，建立可重置的登录状态
2. 新会话：登录预检 -> GET /reset-password
3. POST /api/accounts/password/send-otp（空 JSON，邮箱从会话取）
4. 邮箱取码 -> POST /api/accounts/email-otp/validate
5. 生成新密码，先写本地候选检查点
6. POST /api/accounts/password/reset（sentinel flow=password_reset）
7. 用新密码重新登录校验，确认检查点后保存完整凭据并核验业务接口
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import nullcontext
from urllib.parse import urlparse

from core.accounts.liveness.protocol.legacy import _network_preflight_with_retry
from core.auth.protocol.openai_auth import (
    build_sentinel_header,
    request_sentinel_token,
)
from core.auth.protocol.session import BrowserSession
from core.auth.state_machine import CancellationRequested
from core.email.provider import wait_for_otp
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost
from core.accounts.password_setup import protocol as password_protocol
from core.accounts.password_setup.reset_completion import (
    complete_password_reset as _complete_reset,
    validate_password_session as _validate_reset_auth,
)
from core.accounts.password_setup.reset_support import (
    PasswordResetAuthPageSession,
    ProtocolPasswordResetError,
    check_reset_mailbox as _check_reset_mailbox,
    check_reset_response,
    classify_reset_mailbox_error,
    generate_reset_password,
)

logger = logging.getLogger(__name__)

_AUTH = "https://auth.openai.com"
_RESET_PAGE = _AUTH + "/reset-password"
_SEND_OTP = _AUTH + "/api/accounts/password/send-otp"
_OTP_VALIDATE = _AUTH + "/api/accounts/email-otp/validate"
_PASSWORD_RESET = _AUTH + "/api/accounts/password/reset"


def _saved_password(account: dict) -> str:
    extra = account.get("extra_json") or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (TypeError, ValueError):
            extra = {}
    return str(extra.get("account_password") or "") if isinstance(extra, dict) else ""


def _error(
    code: str,
    category: str = "auth",
    *,
    message: str = "",
    retryable: bool = False,
    request_unknown: bool = False,
    stage: str = "",
    cause_code: str = "",
    password_confirmed: bool = False,
    detail: dict | None = None,
    mutation_submitted: bool | None = None,
    rejected: bool = False,
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
        "stage": stage,
        "cause_code": cause_code or code,
    }
    if password_confirmed:
        result.update(password_confirmed=True, password_reset="confirmed", completion_pending=True)
    if detail:
        result["cause_diagnostics"] = dict(detail)
    if request_unknown:
        result.update(request_unknown=True, outcome="request_unknown")
    if mutation_submitted is not None:
        result.update(mutation_submitted=mutation_submitted, action_dispatched=mutation_submitted)
    if password_confirmed:
        result["remote_receipt_state"] = "local_commit_required"
    elif request_unknown:
        result["remote_receipt_state"] = "unknown"
    elif rejected:
        result["remote_receipt_state"] = "rejected"
    elif mutation_submitted is False:
        result["remote_receipt_state"] = "not_submitted"
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


def _has_login_cookies(payload: dict) -> bool:
    """AT 有效不能代替密码重置所需的登录 Cookie 上下文。"""
    return any(
        isinstance(item, dict)
        and str(item.get("name") or "").startswith("__Secure-next-auth.session-token")
        and str(item.get("value") or "").strip()
        and str(item.get("domain") or "").lstrip(".").lower() == "chatgpt.com"
        for item in payload.get("cookies") or []
    )


def _refresh_before_reset(
    email: str,
    *,
    proxy,
    proxy_supplier,
    account: dict | None = None,
    password_override: str | None = None,
    refresh_driver: str | None = None,
    authenticated_context: dict | None = None,
) -> dict | None:
    """AT 过期/缺失时先刷新一次；成功返回 None，失败返回错误字典。

    沿用明确配置的刷新驱动与可用设备资料，不将普通刷新当成严格重放证明。
    """
    from core.accounts.liveness import service as live_service
    from core.accounts.credentials import (
        get_account_totp_secret_candidate, override_account_login_credentials,
    )

    try:
        driver = refresh_driver or live_service._resolve_refresh_driver(None)
        runner = live_service._refresh_execution_runner(driver)
        credentials = (
            override_account_login_credentials(
                email, password_override, get_account_totp_secret_candidate(account),
            )
            if password_override and isinstance(account, dict)
            else nullcontext()
        )
        def capture(result, active_session):
            if isinstance(authenticated_context, dict) and isinstance(result, dict) and result.get("ok"):
                if active_session is not None:
                    from core.accounts.liveness.protocol.v3 import _cookie_payload

                    authenticated_context.update(_cookie_payload(active_session, result.get("session") or {}))
                elif isinstance(result.get("_protocol_session"), dict):
                    authenticated_context.update(result["_protocol_session"])
            return result

        with credentials:
            options = {} if driver == "browser_roxy" else {"proxy_supplier": proxy_supplier}
            if isinstance(authenticated_context, dict):
                options["on_authenticated"] = capture
                if driver in {"rust", "protocol_v3"}:
                    options["persist_session"] = False
            result = runner(email, proxy=proxy, on_remote_request_started=None, **options)
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except Exception as exc:  # noqa: BLE001
        return _error(
            "password_change_session_required", "network",
            message=f"改密前刷新 AT 失败：{type(exc).__name__}",
            retryable=True, stage="pre_login", mutation_submitted=False,
        )
    if not isinstance(result, dict) or not result.get("ok"):
        code = str((result or {}).get("error") or "password_change_session_required")
        if code in {"password_change_required", "password_reset_required"}:
            logger.info("[改密] 服务端要求先重置密码，继续接码重置")
            return None
        return _error(code, str((result or {}).get("error_category") or "network"),
                      message=str((result or {}).get("error") or "改密前刷新 AT 未成功"),
                      retryable=bool((result or {}).get("retryable")),
                      stage="pre_login", mutation_submitted=False)
    return None


def _send_reset_otp(session: BrowserSession, *, report=None, check=None) -> None:
    headers = session.get_auth_headers(referer=_RESET_PAGE)
    response = session.post(_SEND_OTP, headers=headers, data="{}", allow_redirects=False)
    payload = check_reset_response(response, stage="send_otp")
    observe = getattr(session, "observe_payload", None)
    if callable(observe):
        observe(payload)


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
        raise classify_reset_mailbox_error(exc, stage="wait_otp") from None


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


def _run_password_verification(
    email: str,
    password: str,
    *,
    account: dict,
    proxy,
    proxy_supplier,
    identity: dict | None = None,
    refresh_driver: str | None = None,
    checkpoint=None,
) -> dict:
    """用本轮候选密码重新认证，并返回带密码证据的结果。"""
    from core.accounts.liveness import service as live_service
    from core.accounts.credentials import (
        get_account_totp_secret_candidate, override_account_login_credentials,
    )
    from core.accounts.liveness.protocol import v3
    if callable(checkpoint):
        checkpoint()
    driver = refresh_driver or live_service._resolve_refresh_driver(None)
    # v1 只做邮箱认证，无法证明候选密码；改密验证明确使用现有 v2 密码能力，
    # 不改变普通刷新任务的版本选择。
    if driver in {"legacy", "protocol_v1"}:
        driver = "protocol_v2"
    runner = live_service._refresh_execution_runner(driver)

    def authenticated(result, active_session):
        if callable(checkpoint):
            checkpoint()
        if isinstance(result, dict) and result.get("ok") and active_session is not None:
            try:
                result["_protocol_session"] = v3._cookie_payload(active_session, result.get("session") or {})
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception as exc:
                result["_session_capture_error"] = type(exc).__name__
        return result

    options = {"on_authenticated": authenticated}
    if identity and driver in {"protocol_v2", "protocol_v3", "rust"}:
        options["identity"] = identity
    if driver in {"protocol_v3", "rust"}:
        options["persist_session"] = False
        options["reuse_session"] = False
    if driver == "protocol_v2":
        options["allow_password_email_fallback"] = False
    if driver != "browser_roxy":
        options["proxy_supplier"] = proxy_supplier
    with override_account_login_credentials(
        email, password, get_account_totp_secret_candidate(account),
    ):
        return runner(email, proxy=proxy, **options)


def _password_verification_accepted(result: dict) -> bool:
    """只接受明确的密码认证成功，不接受 Cookie 或未提交密码的会话。"""
    if not isinstance(result, dict) or result.get("ok") is not True:
        return False
    if str(result.get("password_auth_status") or "").strip().lower() != "verified":
        return False
    auth_method = str(result.get("auth_method") or "").strip().lower()
    return bool(auth_method) and "session_cookie" not in auth_method and result.get("session_reused") is not True


def _candidate_explicitly_rejected(result: dict) -> bool:
    code = str(result.get("error") or "")
    if code in {"password_reset_required", "password_change_required"}:
        return True
    if code != "password_rejected":
        return False
    if result.get("live_check_driver") != "rust":
        return True
    # Rust 旧二进制把所有 password_verify 400/401 都投影为 password_rejected；
    # 只有原始结构化原因明确为错误密码时，才据此重新执行远端 reset。
    diagnostic = result.get("auth_diagnostics") or {}
    try:
        payload = json.loads(diagnostic.get("detail") or "{}")
    except (TypeError, ValueError, AttributeError):
        return False
    if not isinstance(payload, dict):
        return False
    error = payload.get("error")
    remote_code = error.get("code") if isinstance(error, dict) else payload.get("code")
    return remote_code in {"incorrect_password", "invalid_password", "wrong_password"}


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
    refresh_config_snapshot: dict | None = None,
) -> dict:
    """走忘记密码流程重置账号密码；返回与账号补全一致的结果字典。"""
    from core import db

    email = str(email or "").strip()
    account = db.get_account_by_email(email) or {}
    if not account:
        return _error("account_not_found", "configuration", message="账号不存在", mutation_submitted=False)
    owner = _manual_recovery_owner(email, account, execution_fence)
    if owner is None:
        return _error(
            "password_reset_execution_fence_missing",
            "runtime",
            message="改密需要有效的账号任务执行租约",
            mutation_submitted=False,
        )
    from core.auth.browser.password_recovery import PasswordRecoverySession
    from core.storage.accounts import password_recovery as recovery_store

    recovery = PasswordRecoverySession(**owner)
    try:
        # 当前 durable Task 已确认的密码归属优先，不能被后来任务的候选接管。
        recovery.resume_manual_password_change()
        if recovery.checkpoint is None:
            recovery.resume()
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except recovery_store.PasswordRecoveryError as exc:
        return _error(
            "password_reset_checkpoint_failed",
            "runtime",
            message=f"改密检查点不可用：{exc.code}",
        )

    active_stage = "preflight"

    def note(stage: str, message: str, state: str = "running", **detail):
        nonlocal active_stage
        active_stage = stage
        if callable(report):
            try:
                report(stage=stage, state=state, message=message, detail=detail or None)
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception:
                pass

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
    reset_response_accepted = False
    from core.accounts.liveness import service as live_service

    refresh_driver = live_service._resolve_refresh_driver(None, config_snapshot=refresh_config_snapshot)

    def finish(auth: dict) -> dict:
        _validate_reset_auth(account, email, auth)
        if recovery.checkpoint is None or recovery.checkpoint.state != "confirmed":
            password = recovery.checkpoint.password if recovery.checkpoint is not None else ""
            confirmed = recovery.confirm("password_change_response", completion_pending=True)
            if (confirmed != password or recovery.checkpoint is None
                    or recovery.checkpoint.state != "confirmed"):
                raise recovery_store.PasswordRecoveryError("confirmation_uncommitted")
            note("login_password_result", "新密码已重新登录验证并写入本地", state="success",
                 checkpoint="password_change_confirmed")
        return _complete_reset(
            recovery=recovery, owner=owner, account=account, email=email, auth=auth,
            proxy=getattr(session, "proxy", None) or proxy, checkpoint=checkpoint, report=report,
        )

    def verify_candidate(password: str) -> dict:
        note("login_password", "正在使用已保存的新密码重新登录",
             driver="protocol_v2" if refresh_driver in {"legacy", "protocol_v1"} else refresh_driver,
             configured_driver=refresh_driver, checkpoint="password_change_verification")
        return _run_password_verification(
            email, password, account=account,
            proxy=getattr(session, "proxy", None) or proxy,
            proxy_supplier=None if session is not None else proxy_supplier,
            identity=identity, refresh_driver=refresh_driver, checkpoint=checkpoint,
        )

    def mark_unknown() -> None:
        checkpoint_state = recovery.checkpoint
        if checkpoint_state is None or checkpoint_state.state != "started":
            return
        recovery.mark_unknown()

    def dispatched_fact() -> bool | None:
        if remote_dispatched:
            return True
        state = getattr(recovery.checkpoint, "state", "")
        return None if state in {"started", "unknown", "confirmed"} else False

    try:
        if callable(checkpoint):
            checkpoint()
        recovered = recovery.checkpoint
        if (recovered is not None and recovered.state == "confirmed"
                and getattr(recovered, "completion_pending", None) is False):
            return _complete_reset(
                recovery=recovery, owner=owner, account=account, email=email,
                auth=None,
                proxy=proxy, checkpoint=checkpoint, report=report,
            )
        if recovered is not None and recovered.state in {"started", "unknown", "confirmed"}:
            verification = verify_candidate(recovered.password)
            if _password_verification_accepted(verification):
                return finish(verification)
            # 只有远端明确拒绝候选密码时，才以同一候选重置；不把网络、MFA 或
            # Cookie 复用等未确认结果当成密码未生效。confirmed 永远只补收尾。
            code = str((verification or {}).get("error") or "")
            if recovered.state == "confirmed" or not _candidate_explicitly_rejected(verification or {}):
                return _error(
                    "password_reset_completion_auth_failed" if recovered.state == "confirmed" else "password_reset_unconfirmed",
                    str((verification or {}).get("error_category") or "auth"),
                    message="密码已确认，重新登录收尾未完成" if recovered.state == "confirmed"
                    else "候选密码尚未取得明确认证结果，可重跑继续核验",
                    retryable=True, request_unknown=recovered.state != "confirmed",
                    password_confirmed=recovered.state == "confirmed", stage="login_password",
                    cause_code=code or "password_auth_evidence_missing",
                )

        _check_reset_mailbox(email)
        if refresh_before_reset and (_session_stale(account) or not _has_login_cookies(cached)):
            note("refresh_at", "改密前建立完整登录上下文，取得可重置的会话")
            refreshed_context = {}
            failure = _refresh_before_reset(
                email, proxy=proxy, proxy_supplier=proxy_supplier, account=account,
                refresh_driver=refresh_driver, authenticated_context=refreshed_context,
            )
            if failure is not None:
                return failure
            account = db.get_account_by_email(email) or account
            cached = refreshed_context or protocol_sessions.load_session(account_id, email) or {}
            remembered = device_profiles.load_profile(account_id, email) or {}
            device = remembered or cached
            profile = device.get("browser_profile")
            if device.get("device_id") and isinstance(profile, dict) and profile:
                identity = {"device_id": str(device["device_id"]), "browser_profile": dict(profile)}
        try:
            session, authorize = _network_preflight_with_retry(
                email, proxy, proxy_supplier=proxy_supplier, identity=identity,
            )
        except ValueError:
            # 画像不完整时退回无 identity，至少保证流程可跑。
            session, authorize = _network_preflight_with_retry(
                email, proxy, proxy_supplier=proxy_supplier,
            )
        session = PasswordResetAuthPageSession(session)
        if cached.get("cookies"):
            from core.accounts.liveness.protocol.v3 import _restore_cookies

            _restore_cookies(session, cached)
        if callable(checkpoint):
            checkpoint()
        authorize_response = session.get(
            authorize, headers=session.get_auth_navigate_headers(referer="https://chatgpt.com/"),
            allow_redirects=True,
        )
        authorize_landing = str(getattr(authorize_response, "url", "") or "")
        initial_authorize_path = urlparse(authorize_landing).path
        parsed_authorize = urlparse(authorize_landing)
        if (parsed_authorize.hostname == "auth.openai.com"
                and parsed_authorize.path.rstrip("/") == "/email-verification"):
            from core.accounts.liveness.protocol.v2 import _open_offered_password_login

            note("password_reset", "授权落在邮箱验证页，先进入已有密码登录入口")
            authorize_landing = _open_offered_password_login(session, authorize_landing)
        reset_response = session.get(
            _RESET_PAGE, headers=session.get_auth_navigate_headers(referer=_AUTH + "/log-in/password"),
            allow_redirects=True,
        )
        note(
            "password_reset", "已请求密码重置页面",
            authorize_status=getattr(authorize_response, "status_code", None),
            authorize_path=initial_authorize_path,
            password_entry_path=urlparse(authorize_landing).path,
            reset_status=getattr(reset_response, "status_code", None),
            reset_path=urlparse(str(getattr(reset_response, "url", "") or "")).path,
            restored_login_cookies=_has_login_cookies(cached),
            auth_page_present=bool(session._auth_page),
        )
        # 本轮已选中的设备交给后续重新认证，旧认证 Cookie 不作为新会话保存。
        if getattr(session, "device_id", None) and isinstance(getattr(session, "browser_profile", None), dict):
            identity = {"device_id": session.device_id, "browser_profile": dict(session.browser_profile)}

        from config import email as email_cfg

        attempts = 1 + max(0, int(getattr(email_cfg, "OTP_RESEND_COUNT", 1) or 0))
        otp_code = None
        last_otp_error = None
        for attempt in range(1, attempts + 1):
            if callable(checkpoint):
                checkpoint()
            otp_after_ts = time.time()
            _send_reset_otp(session)
            note("password_reset_otp", f"已发送重置验证码（{attempt}/{attempts}）")
            try:
                otp_code = _wait_reset_otp(email, otp_after_ts, check=checkpoint)
                break
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except ProtocolPasswordResetError as exc:
                last_otp_error = exc
                if exc.code != "password_reset_otp_timeout":
                    raise
                if attempt >= attempts:
                    break
                note("password_reset_otp", f"验证码未到，重新发送（{attempt}/{attempts}）")
        if not otp_code:
            if last_otp_error is not None:
                raise last_otp_error
            return _error("password_reset_otp_timeout", "email", stage="wait_otp",
                          message="等待本轮重置验证码超时", retryable=True)

        headers = session.get_auth_headers(referer=_AUTH + "/email-verification")
        response = session.post(_OTP_VALIDATE, headers=headers,
                                data=json.dumps({"code": otp_code}), allow_redirects=False)
        payload = check_reset_response(response, stage="validate_otp")
        session.observe_payload(payload)
        continue_url = password_protocol._continuation(payload)
        if continue_url:
            from core.accounts.credentials import get_account_totp_secret_candidate

            if password_protocol._is_mfa_page(continue_url):
                continue_url = password_protocol._verify_mfa(
                    session, payload, continue_url, get_account_totp_secret_candidate(account),
                    checkpoint=checkpoint,
                )
            password_protocol._follow_password_page(
                session, continue_url, referer=_AUTH + "/email-verification", checkpoint=checkpoint,
            )
        elif (payload.get("page") or {}).get("type") not in {"new_password", "password_reset"}:
            raise ProtocolPasswordResetError(
                "password_reset_page_unconfirmed", "验码后尚未确认进入新密码步骤",
                stage="validate_otp", category="auth", cause_code="reset_page_missing", retryable=True,
            )
        note("password_reset", "验证码通过，准备提交新密码")

        try:
            password = recovery.prepare(
                lambda: str(new_password) if new_password is not None else generate_reset_password(
                    _saved_password(account),
                ),
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
        check_reset_response(response, stage="reset", result_unknown=True)
        reset_response_accepted = True
        note("password_reset", "重置请求已接受，开始用新密码重新登录验证", state="success")

        verify = verify_candidate(password)
        if not _password_verification_accepted(verify):
            mark_unknown()
            return _error(
                "password_reset_unconfirmed", "auth",
                message="新密码已提交，但未取得明确的密码认证成功证据",
                retryable=True, request_unknown=True, stage="login_password",
                cause_code=str((verify or {}).get("error") or "password_auth_evidence_missing"),
            )
        return finish(verify)
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        if remote_dispatched:
            try:
                mark_unknown()
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception:
                logger.warning("[改密] 取消后未知回执状态保存失败", exc_info=True)
        raise
    except ProtocolPasswordResetError as exc:
        confirmed = recovery.checkpoint is not None and recovery.checkpoint.state == "confirmed"
        if remote_dispatched and not confirmed:
            mark_unknown()
        return _error(
            exc.code, exc.category, message=str(exc), retryable=exc.retryable,
            request_unknown=(exc.request_unknown or reset_response_accepted) and not confirmed, stage=exc.stage,
            cause_code=exc.cause_code, password_confirmed=confirmed, detail=exc.detail,
            mutation_submitted=dispatched_fact(),
            rejected=remote_dispatched and not reset_response_accepted and not exc.request_unknown and not confirmed,
        )
    except recovery_store.PasswordRecoveryError as exc:
        confirmed = recovery.checkpoint is not None and recovery.checkpoint.state == "confirmed"
        return _error(
            "password_reset_checkpoint_failed", "runtime",
            message=f"改密检查点或收尾写回失败：{exc.code}", retryable=True,
            request_unknown=remote_dispatched and not confirmed, stage=active_stage,
            cause_code=exc.code, password_confirmed=confirmed,
            mutation_submitted=dispatched_fact(),
        )
    except Exception as exc:  # noqa: BLE001
        confirmed = recovery.checkpoint is not None and recovery.checkpoint.state == "confirmed"
        if remote_dispatched and not confirmed:
            try:
                mark_unknown()
            except (CancellationRequested, OperationCancelled, OperationLeaseLost):
                raise
            except Exception:
                logger.warning("[改密] 未知回执状态保存失败", exc_info=True)
        cause = str(getattr(exc, "code", "") or type(exc).__name__)
        return _error(
            "password_reset_completion_failed" if confirmed else "password_reset_stage_failed",
            str(getattr(exc, "category", "") or "runtime"),
            message=f"{'密码已确认，收尾' if confirmed else '改密'}在 {active_stage} 阶段未完成：{cause}",
            retryable=True, request_unknown=remote_dispatched and not confirmed,
            password_confirmed=confirmed, stage=active_stage, cause_code=cause,
            mutation_submitted=dispatched_fact(),
        )
    finally:
        if session is not None:
            try:
                session.session.close()
            except Exception:
                pass
