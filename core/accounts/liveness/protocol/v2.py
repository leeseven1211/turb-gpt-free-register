# -*- coding: utf-8 -*-
"""Opt-in Protocol v2 authentication flow for explicit AT refreshes.

The existing ``core.accounts.liveness.protocol.legacy`` flow is intentionally left untouched.  This
module is only called by a ``token_refresh`` task when the user explicitly selects
``protocol_v2``.  Ordinary live checks never import or call this module.

The adapter owns the password/MFA response state machine, but reuses the project's
existing session, Sentinel, OAuth callback, and email OTP primitives.  It never
logs passwords, TOTP values, tokens, cookies, or raw response bodies.
"""
from __future__ import annotations

import json
import logging
import re
import time
from contextvars import ContextVar
from datetime import datetime
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlparse

import pyotp

from config import account as account_config
from config.browser import IMPERSONATE, resolve_impersonate
from core.auth.email_guard import serialize_email_auth
from core.accounts.export import fetch_session, follow_oauth_callback
from core.accounts.liveness.protocol.legacy import _network_preflight_with_retry, _validate_with_retry, check_account_liveness
from core.accounts.liveness.protocol.otp_diagnostics import otp_failure_diagnostics
from core.auth.protocol.openai_auth import AccountUnusableError, AuthorizeRouteRejectedError, build_sentinel_header, detect_account_unusable_response_body, detect_account_unusable_text, EmailOtpSendError, follow_authorize, request_sentinel_token, send_email_otp
from core.accounts.credentials import account_email_is_invalid, get_account_login_credentials
from core.auth.fingerprint import build_safe_fingerprint_summary
from core.auth.challenge import auth_result_for_operation
from core.network.response_diagnostics import auth_error_from_body, safe_response_headers

logger = logging.getLogger('core.protocol_v2_liveness')

# 只由 AT 刷新入口启用；共享登录能力的补密码及其他协议沿用原行为。
_AT_CALLBACK_CONTEXT: ContextVar[dict | None] = ContextVar("at_callback_recovery", default=None)


def _record_completed(session, challenge: str) -> None:
    context = _AT_CALLBACK_CONTEXT.get()
    if context is None:
        return
    if context.get("session") != id(session):
        context.update(session=id(session), challenge_chain=[])
    chain = context["challenge_chain"]
    if challenge not in chain:
        chain.append(challenge)


def _callback_facts(context: dict | None) -> dict:
    if context is None:
        return {}
    chain = list(context.get("challenge_chain") or [])
    return {
        "challenge_chain": chain,
        "email_otp_status": "success" if "email_otp" in chain else "skipped",
        "mfa_status": "success" if "totp" in chain else "skipped",
        **({"password_auth_status": "verified"} if "password" in chain else {}),
    }


def _reraise_control(exception: BaseException) -> None:
    """保留经过兼容辅助函数包装的取消与执行租约失效信号。"""
    from core.auth.state_machine import CancellationRequested, StageTimeout
    from core.network.at_transport_recovery import AtRecoveryTimeout, current_scope
    from core.operations.runtime import OperationAccountDeactivated, OperationCancelled
    from core.operations.task_gateway import OperationLeaseLost

    pending, visited = [exception], set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, (OperationCancelled, OperationLeaseLost, CancellationRequested, OperationAccountDeactivated)):
            raise current
        if current_scope() is not None and isinstance(current, (AtRecoveryTimeout, StageTimeout)):
            raise current
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)

_PASSWORD_PATH = "https://auth.openai.com/log-in/password"
_MFA_PATH = "https://auth.openai.com/mfa-challenge"
_EMAIL_PATH = "https://auth.openai.com/email-verification"
_AUTH_MARKERS = (
    "invalid password",
    "incorrect password",
    "wrong password",
    "password is incorrect",
    "password_incorrect",
    "invalid_password",
    "wrong_password",
    "password_invalid",
    "password_rejected",
    "invalid_username_or_password",
    "invalid email or password",
    "incorrect email or password",
    "email or password is incorrect",
    "login failed",
    "密码错误",
    "邮箱或密码错误",
    "密码不正确",
)
_OTP_MARKERS = ("email-verification", "email_otp", "email otp", "one-time code", "验证码")
_MFA_MARKERS = ("mfa-challenge", "mfa_challenge", "totp", "multi-factor")


class ProtocolV2AuthError(RuntimeError):
    """A classified failure that is safe to pass to the task layer."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        category: str = "auth",
        retryable: bool = False,
        roxy_fallback_allowed: bool = True,
        response_observed: bool = False,
    ):
        self.code = str(code)
        self.category = str(category)
        self.retryable = bool(retryable)
        # These outcomes are credential/verification decisions, not workflow
        # failures.  Never let a caller accidentally turn them into an
        # automatic browser retry that could submit the same credential again.
        self.roxy_fallback_allowed = bool(roxy_fallback_allowed) and self.code not in {
            "password_rejected",
            "password_result_unknown",
            "password_rejected_email_fallback_failed",
            "passwordless_fallback_unavailable",
            "mfa_rejected",
            "mfa_secret_missing",
        }
        self.response_observed = bool(response_observed)
        self.mutation_submitted: bool | None = None
        self.action_dispatched: bool | None = None
        self.reconcile_required = self.code == "password_result_unknown"
        self.diagnostics: dict = {}
        super().__init__(message or self.code)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _extract_continue_url(result: dict | None) -> str:
    if not isinstance(result, dict):
        return ""
    page = result.get("page") or {}
    page = page if isinstance(page, dict) else {}
    return str(
        result.get("continue_url")
        or result.get("external_url")
        or result.get("url")
        or page.get("continue_url")
        or page.get("external_url")
        or page.get("url")
        or ""
    ).strip()


def _response_status(response) -> int | None:
    try:
        status = int(getattr(response, "status_code", 0) or 0)
    except (TypeError, ValueError):
        return None
    return status or None


def _response_text(response) -> str:
    # This is used only for local classification.  It must never be returned or
    # logged because auth responses can contain challenge details.
    return str(getattr(response, "text", "") or "")


def _request_diagnostics(exc: BaseException, *, operation: str, response_observed: bool) -> dict:
    """Return only safe metadata for diagnosing an auth request failure."""
    response = getattr(exc, "response", None)
    status = _response_status(response)
    result = {
        "operation": str(operation),
        "failure_kind": "http_error" if response_observed else "transport_error",
        "exception_type": type(exc).__name__[:80],
        "http_status": status,
        "response_observed": bool(response_observed),
    }
    if response_observed and response is not None:
        auth_error = auth_error_from_body(_response_text(response))
        headers = safe_response_headers(getattr(response, "headers", None))
        if auth_error:
            result["auth_error"] = auth_error
        if headers:
            result["response_headers"] = headers
    # 只读取 curl 稳定数值，不透传含 Token、代理或 URL 的异常原文。
    curl_code = getattr(exc, "code", None)
    if not isinstance(curl_code, int) or isinstance(curl_code, bool):
        match = re.search(r"curl:\s*\((28|35|56|60)\)", str(exc))
        curl_code = int(match.group(1)) if match else None
    if curl_code in {28, 35, 56, 60}:
        result["curl_error_code"] = int(curl_code)
    return result


def _mark_auth_submission(error: ProtocolV2AuthError) -> ProtocolV2AuthError:
    """认证 POST 已派发；保留原因，同时独立阻止不明回执的重复提交。"""
    error.mutation_submitted = True
    error.action_dispatched = True
    error.roxy_fallback_allowed = False
    error.reconcile_required = bool(
        not error.response_observed or error.code == "password_result_unknown"
        or error.code.endswith("_invalid_response")
        or error.code == "protocol_network_error"
    )
    if error.reconcile_required:
        error.roxy_fallback_allowed = False
        error.retryable = False
    return error


def _request_error(exc: BaseException, *, operation: str) -> ProtocolV2AuthError:
    response = getattr(exc, "response", None)
    status = _response_status(response)
    body = _response_text(response).lower()
    dead_code = detect_account_unusable_response_body(_response_text(response)) or detect_account_unusable_text(body)
    if dead_code:
        return ProtocolV2AuthError(
            "account_deactivated",
            category="account",
            roxy_fallback_allowed=False,
            response_observed=True,
        )

    if operation == "password_verify" and status in {400, 401, 403, 422}:
        if any(marker in body for marker in _AUTH_MARKERS):
            return ProtocolV2AuthError(
                "password_rejected",
                category="auth",
                roxy_fallback_allowed=False,
                response_observed=True,
            )

    if operation == "mfa_verify" and status in {400, 401, 422}:
        return ProtocolV2AuthError(
            "mfa_rejected",
            category="auth",
            roxy_fallback_allowed=False,
            response_observed=True,
        )

    if status in {408, 425, 429} or (status is not None and status >= 500):
        code = "password_result_unknown" if operation == "password_verify" else "protocol_network_error"
        return ProtocolV2AuthError(
            code,
            category="network",
            retryable=True,
            roxy_fallback_allowed=operation != "password_verify",
            response_observed=True,
        )

    # A transport exception after the password POST is deliberately not treated
    # as a wrong password.  Re-submitting it could duplicate an auth action.
    if operation == "password_verify":
        return ProtocolV2AuthError(
            "password_result_unknown",
            category="network",
            retryable=False,
            roxy_fallback_allowed=False,
            response_observed=status is not None,
        )
    return ProtocolV2AuthError(
        f"{operation}_failed",
        category="auth",
        response_observed=status is not None,
    )


def _post_json(session, url: str, *, headers: dict, payload: dict, operation: str) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _post_json as execute, PostJsonDependencies
    dependencies = PostJsonDependencies(
        json=json,
        ProtocolV2AuthError=ProtocolV2AuthError,
        _mark_auth_submission=_mark_auth_submission,
        _request_diagnostics=_request_diagnostics,
        _request_error=_request_error,
        _response_status=_response_status,
    )
    return execute(session, url, headers=headers, payload=payload, operation=operation, _deps=dependencies)


def _password_verify(session, password: str) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _password_verify as execute, PasswordVerifyDependencies
    dependencies = PasswordVerifyDependencies(
        ProtocolV2AuthError=ProtocolV2AuthError,
        _PASSWORD_PATH=_PASSWORD_PATH,
        _post_json=_post_json,
        _request_diagnostics=_request_diagnostics,
        _response_status=_response_status,
        build_sentinel_header=build_sentinel_header,
        request_sentinel_token=request_sentinel_token,
    )
    return execute(session, password, _deps=dependencies)


def _mfa_issue_challenge(session, factor_id: str) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _mfa_issue_challenge as execute, MfaIssueChallengeDependencies
    dependencies = MfaIssueChallengeDependencies(
        _MFA_PATH=_MFA_PATH,
        _post_json=_post_json,
    )
    return execute(session, factor_id, _deps=dependencies)


def _mfa_verify(session, factor_id: str, code: str) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _mfa_verify as execute, MfaVerifyDependencies
    dependencies = MfaVerifyDependencies(
        ProtocolV2AuthError=ProtocolV2AuthError,
        _MFA_PATH=_MFA_PATH,
        _post_json=_post_json,
    )
    return execute(session, factor_id, code, _deps=dependencies)


def _page_type(result: dict | None) -> str:
    if not isinstance(result, dict):
        return ""
    page = result.get("page") or {}
    return str(page.get("type") or "").strip().lower() if isinstance(page, dict) else ""


def _extract_factor_id(result: dict | None, continue_url: str = "") -> str:
    if isinstance(result, dict):
        candidates = [result.get("factor_id"), result.get("factorId"), result.get("id")]
        page = result.get("page") or {}
        if isinstance(page, dict):
            candidates.extend((page.get("factor_id"), page.get("factorId")))
            payload = page.get("payload") or {}
            if isinstance(payload, dict):
                candidates.extend((payload.get("factor_id"), payload.get("factorId"), payload.get("id")))
        for value in candidates:
            if str(value or "").strip():
                return str(value).strip()
    parsed = urlparse(str(continue_url or ""))
    query = parse_qs(parsed.query)
    for key in ("factor_id", "factorId", "id"):
        if query.get(key) and str(query[key][0] or "").strip():
            return str(query[key][0]).strip()
    if "/mfa-challenge/" in str(continue_url):
        return str(continue_url).rstrip("/").rsplit("/", 1)[-1]
    return ""


def _is_mfa(result: dict | None, continue_url: str = "") -> bool:
    value = " ".join((str(continue_url or ""), _page_type(result))).lower()
    return any(marker in value for marker in _MFA_MARKERS)


def _is_email_otp(result: dict | None, continue_url: str = "") -> bool:
    value = " ".join((str(continue_url or ""), _page_type(result))).lower()
    return any(marker in value for marker in _OTP_MARKERS)


def _follow_and_fetch(session, continue_url: str, *, referer: str) -> dict:
    context = _AT_CALLBACK_CONTEXT.get()
    if context is not None:
        from core.accounts.liveness.protocol.callback import CallbackRecoveryError, complete_callback

        try:
            return complete_callback(
                session, continue_url, referer=referer,
                email=context["email"], checkpoint=context.get("checkpoint"),
            )
        except CallbackRecoveryError as exc:
            error = ProtocolV2AuthError(
                exc.code, category=exc.category, retryable=exc.retryable,
                roxy_fallback_allowed=False,
                response_observed=bool(exc.diagnostics.get("response_observed")),
            )
            error.diagnostics = dict(exc.diagnostics)
            raise error from exc
    if not continue_url:
        raise ProtocolV2AuthError("auth_page_unknown", category="response", roxy_fallback_allowed=True)
    try:
        follow_oauth_callback(session, continue_url, referer=referer)
        return fetch_session(session)
    except AccountUnusableError:
        raise
    except Exception as exc:
        raise ProtocolV2AuthError(
            "oauth_callback_failed",
            category="network",
            retryable=True,
            roxy_fallback_allowed=True,
        ) from exc


def _totp_code(secret: str) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _totp_code as execute, TotpCodeDependencies
    dependencies = TotpCodeDependencies(
        time=time,
        ProtocolV2AuthError=ProtocolV2AuthError,
        pyotp=pyotp,
    )
    return execute(secret, _deps=dependencies)


def _complete_mfa(session, result: dict, continue_url: str, secret: str) -> tuple[dict, str]:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _complete_mfa as execute, CompleteMfaDependencies
    dependencies = CompleteMfaDependencies(
        ProtocolV2AuthError=ProtocolV2AuthError,
        _MFA_PATH=_MFA_PATH,
        _extract_continue_url=_extract_continue_url,
        _extract_factor_id=_extract_factor_id,
        _follow_and_fetch=_follow_and_fetch,
        _mfa_issue_challenge=_mfa_issue_challenge,
        _mfa_verify=_mfa_verify,
        _record_completed=_record_completed,
        _totp_code=_totp_code,
    )
    return execute(session, result, continue_url, secret, _deps=dependencies)


def _complete_email_otp(session, email: str, after_ts: float, *, auth_method: str) -> tuple[dict, str]:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _complete_email_otp as execute, CompleteEmailOtpDependencies
    dependencies = CompleteEmailOtpDependencies(
        AccountUnusableError=AccountUnusableError,
        ProtocolV2AuthError=ProtocolV2AuthError,
        _EMAIL_PATH=_EMAIL_PATH,
        _extract_continue_url=_extract_continue_url,
        _follow_and_fetch=_follow_and_fetch,
        _is_mfa=_is_mfa,
        _record_completed=_record_completed,
        _validate_with_retry=_validate_with_retry,
        logger=logger,
        otp_failure_diagnostics=otp_failure_diagnostics,
    )
    return execute(session, email, after_ts, auth_method=auth_method, _deps=dependencies)


def _start_email_session(
    email: str, proxy: str | None, *, identity=None, context_recorder=None, session_adapter=None,
):
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _start_email_session as execute, StartEmailSessionDependencies
    dependencies = StartEmailSessionDependencies(
        time=time,
        ProtocolV2AuthError=ProtocolV2AuthError,
        _network_preflight_with_retry=_network_preflight_with_retry,
        detect_account_unusable_text=detect_account_unusable_text,
        follow_authorize=follow_authorize,
    )
    return execute(email, proxy, identity=identity, context_recorder=context_recorder, session_adapter=session_adapter, _deps=dependencies)


def _open_offered_password_login(session, final_url: str, *, allow_standard_route: bool = True) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _open_offered_password_login as execute, OpenOfferedPasswordLoginDependencies
    dependencies = OpenOfferedPasswordLoginDependencies(
        HTMLParser=HTMLParser,
        urljoin=urljoin,
        urlparse=urlparse,
        ProtocolV2AuthError=ProtocolV2AuthError,
        _EMAIL_PATH=_EMAIL_PATH,
        _PASSWORD_PATH=_PASSWORD_PATH,
        _request_diagnostics=_request_diagnostics,
        _response_status=_response_status,
        logger=logger,
    )
    return execute(session, final_url, allow_standard_route=allow_standard_route, _deps=dependencies)


def _refresh_with_password(
    email: str,
    proxy: str | None,
    *,
    proxy_supplier: Callable[[int], str | None] | None,
    identity=None,
    context_recorder=None,
    on_remote_request_started: Callable[[], None] | None = None,
    on_authenticated=None,
    allow_password_email_fallback: bool | None = None,
    on_network_failure=None,
    session_adapter=None,
) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v2 import _refresh_with_password as execute, RefreshWithPasswordDependencies
    dependencies = RefreshWithPasswordDependencies(
        time=time,
        urlparse=urlparse,
        EmailOtpSendError=EmailOtpSendError,
        ProtocolV2AuthError=ProtocolV2AuthError,
        _AT_CALLBACK_CONTEXT=_AT_CALLBACK_CONTEXT,
        _PASSWORD_PATH=_PASSWORD_PATH,
        _complete_email_otp=_complete_email_otp,
        _complete_mfa=_complete_mfa,
        _extract_continue_url=_extract_continue_url,
        _extract_factor_id=_extract_factor_id,
        _follow_and_fetch=_follow_and_fetch,
        _is_email_otp=_is_email_otp,
        _is_mfa=_is_mfa,
        _network_preflight_with_retry=_network_preflight_with_retry,
        _now=_now,
        _open_offered_password_login=_open_offered_password_login,
        _password_verify=_password_verify,
        _record_completed=_record_completed,
        _start_email_session=_start_email_session,
        _success=_success,
        account_email_is_invalid=account_email_is_invalid,
        check_account_liveness=check_account_liveness,
        detect_account_unusable_text=detect_account_unusable_text,
        follow_authorize=follow_authorize,
        get_account_login_credentials=get_account_login_credentials,
        logger=logger,
        password_email_fallback_enabled=lambda: bool(getattr(account_config, "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", False)),
        send_email_otp=send_email_otp,
    )
    return execute(email, proxy, proxy_supplier=proxy_supplier, identity=identity, context_recorder=context_recorder, on_remote_request_started=on_remote_request_started, on_authenticated=on_authenticated, allow_password_email_fallback=allow_password_email_fallback, on_network_failure=on_network_failure, session_adapter=session_adapter, _deps=dependencies)


def _success(
    checked_at: str,
    session_info: dict,
    session,
    *,
    auth_method: str,
    password_auth_status: str,
    fallback_used: bool,
) -> dict:
    access_token = str(session_info.get("accessToken") or "").strip()
    if not access_token:
        raise ProtocolV2AuthError("access_token_missing", category="response", roxy_fallback_allowed=True)
    user = session_info.get("user") or {}
    account = session_info.get("account") or {}
    logger.info(
        "[查活][Protocol v2] 密码认证成功 user_id=%s plan=%s auth_method=%s",
        user.get("id"),
        account.get("planType"),
        auth_method,
    )
    return {
        "ok": True,
        "status": "live",
        "checked_at": checked_at,
        "access_token": access_token,
        "session": session_info,
        "proxy_used": getattr(session, "proxy", None) or None,
        "validation_method": "authenticated_session",
        "auth_method": auth_method,
        "password_auth_status": password_auth_status,
        "fallback_used": bool(fallback_used),
        "live_check_driver": "protocol_v2",
        "roxy_fallback_allowed": password_auth_status != "rejected",
        "auth": auth_result_for_operation(
            {
                "ok": True,
                "auth_method": auth_method,
                "password_auth_status": password_auth_status,
                "roxy_fallback_allowed": password_auth_status != "rejected",
            },
            auth_method="protocol_v2",
        ).as_dict(),
        "fingerprint": build_safe_fingerprint_summary(
            session,
            source="protocol",
            profile_version=getattr(session, "protocol_profile_version", None),
            profile_ref=getattr(session, "protocol_profile_ref", None),
            route={"proxy_mode": "proxy" if getattr(session, "proxy", None) else "direct"},
            transport_profile=f"curl_cffi:{resolve_impersonate(IMPERSONATE)}",
        ),
    }


@serialize_email_auth
def refresh_access_token(
    email: str,
    *,
    proxy: str | None = None,
    proxy_supplier: Callable[[int], str | None] | None = None,
    identity=None,
    context_recorder=None,
    on_remote_request_started: Callable[[], None] | None = None,
    on_authenticated=None,
    allow_password_email_fallback: bool | None = None,
    on_network_failure=None,
    callback_recovery: bool = False,
    callback_checkpoint=None,
    session_adapter=None,
) -> dict:
    """Run the opt-in Protocol v2 refresh flow and return a safe result."""
    checked_at = _now()
    remote_request_started = False

    def mark_remote_request_started() -> None:
        nonlocal remote_request_started
        if remote_request_started:
            return
        remote_request_started = True
        if callable(on_remote_request_started):
            on_remote_request_started()

    context = {"email": email, "checkpoint": callback_checkpoint, "challenge_chain": []} if callback_recovery else None
    marker = _AT_CALLBACK_CONTEXT.set(context)
    try:
        try:
            result = _refresh_with_password(
                email,
                proxy,
                proxy_supplier=proxy_supplier,
                identity=identity,
                context_recorder=context_recorder,
                on_remote_request_started=mark_remote_request_started,
                **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
                **({"allow_password_email_fallback": allow_password_email_fallback}
                   if allow_password_email_fallback is not None else {}),
                **({"on_network_failure": on_network_failure} if callable(on_network_failure) else {}),
                **({"session_adapter": session_adapter} if callable(session_adapter) else {}),
            )
        finally:
            _AT_CALLBACK_CONTEXT.reset(marker)
        facts = _callback_facts(context)
        if not result.get("ok"):
            for key in ("mfa_status", "email_otp_status"):
                if facts.get(key) == "skipped":
                    facts.pop(key)
        result.update(facts)
        if context is not None:
            result["auth"] = auth_result_for_operation(result, auth_method=str(result.get("auth_method") or "protocol_v2")).as_dict()
        result.setdefault("remote_request_started", remote_request_started)
        result.setdefault(
            "auth",
            auth_result_for_operation(result, auth_method=str(result.get("auth_method") or "protocol_v2")).as_dict(),
        )
        return result
    except AuthorizeRouteRejectedError as exc:
        return {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": "auth_route_rejected",
            "error_category": "network",
            "http_status": int(exc.status_code or 0) or None,
            "auth_method": "protocol_v2",
            "roxy_fallback_allowed": True,
            "retryable": True,
            "remote_request_started": remote_request_started,
            "live_check_driver": "protocol_v2",
            "auth": auth_result_for_operation(
                {"ok": False, "error": "auth_route_rejected", "roxy_fallback_allowed": True},
                auth_method="protocol_v2",
            ).as_dict(),
        }
    except AccountUnusableError as exc:
        code = getattr(exc, "error_code", "") or "account_deactivated"
        return {
            "ok": False,
            "status": "deactivated",
            "checked_at": checked_at,
            "error": code,
            "error_category": "account",
            "auth_method": "protocol_v2",
            "roxy_fallback_allowed": False,
            "remote_request_started": remote_request_started,
            "live_check_driver": "protocol_v2",
            "auth": auth_result_for_operation(
                {"ok": False, "error": code, "roxy_fallback_allowed": False},
                auth_method="protocol_v2",
            ).as_dict(),
        }
    except ProtocolV2AuthError as exc:
        from core.network.at_transport_recovery import current_scope

        if context is not None or current_scope() is not None:
            _reraise_control(exc)
        if callable(on_network_failure):
            on_network_failure(exc)
        status = "deactivated" if exc.code == "account_deactivated" else "failed"
        result = {
            "ok": False,
            "status": status,
            "checked_at": checked_at,
            "error": exc.code,
            "error_category": exc.category,
            "auth_method": getattr(exc, "auth_method", "protocol_v2"),
            "roxy_fallback_allowed": exc.roxy_fallback_allowed,
            "retryable": exc.retryable,
            "remote_request_started": remote_request_started,
            "live_check_driver": "protocol_v2",
        }
        facts = _callback_facts(context)
        # 仅覆盖确有成功回执的挑战；未通过的挑战仍按原失败位置投影。
        if facts.get("email_otp_status") != "success":
            facts.pop("email_otp_status", None)
        if facts.get("mfa_status") != "success":
            facts.pop("mfa_status", None)
        result.update(facts)
        if exc.mutation_submitted is not None:
            result["mutation_submitted"] = exc.mutation_submitted
        if exc.action_dispatched is not None:
            result["action_dispatched"] = exc.action_dispatched
            result["remote_response_received"] = exc.response_observed
        if exc.reconcile_required:
            result.update({"reconcile_required": True, "manual_reconcile": True, "next_action": "manual_reconcile"})
        if getattr(exc, "password_auth_status", ""):
            result["password_auth_status"] = exc.password_auth_status
        if getattr(exc, "diagnostics", None):
            result["auth_diagnostics"] = dict(exc.diagnostics)
            result["http_status"] = exc.diagnostics.get("http_status")
        result["auth"] = auth_result_for_operation(result, auth_method="protocol_v2").as_dict()
        if exc.code in {
            "password_rejected",
            "password_rejected_email_fallback_failed",
            "passwordless_fallback_unavailable",
        }:
            result["password_auth_status"] = "rejected"
        return result
    except Exception as exc:
        from core.network.at_transport_recovery import current_scope

        if context is not None or current_scope() is not None:
            _reraise_control(exc)
        if callable(on_network_failure):
            on_network_failure(exc)
        logger.warning("[查活][Protocol v2] 认证未完成：%s", type(exc).__name__)
        error = "protocol_v2_unknown_error" if remote_request_started else "network_preflight_failed"
        status = _response_status(getattr(exc, "response", None))
        diagnostics = {
            "operation": "protocol_v2_auth" if remote_request_started else "network_preflight",
            "failure_kind": "runtime_exception",
            "exception_type": type(exc).__name__[:80],
            "http_status": status,
            "response_observed": status is not None,
        }
        return {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": error,
            "error_category": "runtime" if remote_request_started else "network",
            "http_status": status,
            "auth_diagnostics": diagnostics,
            "auth_method": "protocol_v2",
            "roxy_fallback_allowed": True,
            "remote_request_started": remote_request_started,
            "live_check_driver": "protocol_v2",
            "auth": auth_result_for_operation(
                {"ok": False, "error": error, "roxy_fallback_allowed": True},
                auth_method="protocol_v2",
            ).as_dict(),
        }
