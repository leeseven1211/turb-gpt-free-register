# -*- coding: utf-8 -*-
"""Opt-in Protocol v2 authentication flow for explicit AT refreshes.

The existing ``core.account_liveness`` flow is intentionally left untouched.  This
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
from datetime import datetime
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlparse

import pyotp

from config import account as account_config
from config.browser import IMPERSONATE, resolve_impersonate
from core.email_auth_guard import serialize_email_auth
from core.account_export import fetch_session, follow_oauth_callback
from core.account_liveness import (
    _network_preflight_with_retry,
    _validate_with_retry,
    check_account_liveness,
)
from core.openai_auth import (
    AccountUnusableError,
    AuthorizeRouteRejectedError,
    build_sentinel_header,
    detect_account_unusable_response_body,
    detect_account_unusable_text,
    EmailOtpSendError,
    follow_authorize,
    request_sentinel_token,
    send_email_otp,
)
from core.account_credentials import account_email_is_invalid, get_account_login_credentials
from core.auth_fingerprint import build_safe_fingerprint_summary
from core.auth_challenge import auth_result_for_operation

logger = logging.getLogger(__name__)

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
    try:
        response = session.post(
            url,
            headers=headers,
            data=json.dumps(payload, separators=(",", ":")),
            allow_redirects=False,
        )
    except Exception as exc:
        error = _request_error(exc, operation=operation)
        error.diagnostics = _request_diagnostics(
            exc,
            operation=operation,
            response_observed=error.response_observed,
        )
        raise _mark_auth_submission(error) from exc

    status = _response_status(response)
    if status is None or status < 200 or status >= 300:
        exc = RuntimeError(f"{operation} status={status or 0}")
        exc.response = response
        error = _request_error(exc, operation=operation)
        error.diagnostics = _request_diagnostics(
            exc,
            operation=operation,
            response_observed=error.response_observed,
        )
        raise _mark_auth_submission(error) from exc
    try:
        data = response.json()
    except Exception as exc:
        raise _mark_auth_submission(ProtocolV2AuthError(
            f"{operation}_invalid_response",
            category="response",
            roxy_fallback_allowed=True,
            response_observed=True,
        )) from exc
    if not isinstance(data, dict):
        raise _mark_auth_submission(ProtocolV2AuthError(
            f"{operation}_invalid_response",
            category="response",
            roxy_fallback_allowed=True,
            response_observed=True,
        ))
    return data


def _password_verify(session, password: str) -> dict:
    """Verify one saved OpenAI password, at most once per refresh run."""
    if not password:
        raise ProtocolV2AuthError(
            "password_missing",
            category="configuration",
            roxy_fallback_allowed=False,
        )
    try:
        sentinel = request_sentinel_token(session, "password_verify")
        sentinel_header, so_header = build_sentinel_header(session, sentinel, "password_verify")
    except Exception as exc:
        error = ProtocolV2AuthError(
            "password_sentinel_failed",
            category="network",
            retryable=True,
            roxy_fallback_allowed=True,
        )
        # Sentinel 失败时尚未派发密码 POST，明确证据允许上层安全转浏览器。
        error.mutation_submitted = False
        error.action_dispatched = False
        error.diagnostics = _request_diagnostics(
            exc, operation="password_sentinel", response_observed=_response_status(getattr(exc, "response", None)) is not None,
        )
        raise error from exc
    headers = session.get_auth_headers(referer=_PASSWORD_PATH)
    headers["openai-sentinel-token"] = sentinel_header
    if so_header:
        headers["openai-sentinel-so-token"] = so_header
    return _post_json(
        session,
        "https://auth.openai.com/api/accounts/password/verify",
        headers=headers,
        payload={"password": password},
        operation="password_verify",
    )


def _mfa_issue_challenge(session, factor_id: str) -> dict:
    headers = session.get_auth_headers(referer=_MFA_PATH)
    headers.pop("openai-sentinel-token", None)
    headers.pop("openai-sentinel-so-token", None)
    return _post_json(
        session,
        "https://auth.openai.com/api/accounts/mfa/issue_challenge",
        headers=headers,
        payload={"id": factor_id, "type": "totp", "force_fresh_challenge": False},
        operation="mfa_issue_challenge",
    )


def _mfa_verify(session, factor_id: str, code: str) -> dict:
    if not code:
        raise ProtocolV2AuthError("mfa_code_missing", category="configuration", roxy_fallback_allowed=False)
    headers = session.get_auth_headers(referer=_MFA_PATH)
    headers.pop("openai-sentinel-token", None)
    headers.pop("openai-sentinel-so-token", None)
    return _post_json(
        session,
        "https://auth.openai.com/api/accounts/mfa/verify",
        headers=headers,
        payload={"id": factor_id, "type": "totp", "code": code},
        operation="mfa_verify",
    )


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
    if not secret:
        raise ProtocolV2AuthError(
            "mfa_secret_missing",
            category="configuration",
            roxy_fallback_allowed=False,
        )
    # Do not submit in the last six seconds of a 30-second TOTP window.
    remaining = 30.0 - (time.time() % 30.0)
    if remaining < 6.0:
        time.sleep(remaining + 0.5)
    try:
        return pyotp.TOTP(secret).now()
    except Exception as exc:
        raise ProtocolV2AuthError(
            "mfa_secret_invalid",
            category="configuration",
            roxy_fallback_allowed=False,
        ) from exc


def _complete_mfa(session, result: dict, continue_url: str, secret: str) -> tuple[dict, str]:
    factor_id = _extract_factor_id(result, continue_url)
    if not factor_id:
        raise ProtocolV2AuthError("mfa_factor_missing", category="response", roxy_fallback_allowed=False)
    _mfa_issue_challenge(session, factor_id)
    mfa_result = _mfa_verify(session, factor_id, _totp_code(secret))
    mfa_continue_url = _extract_continue_url(mfa_result) or continue_url
    session_info = _follow_and_fetch(
        session,
        mfa_continue_url,
        referer=f"{_MFA_PATH}/{factor_id}",
    )
    return session_info, "password_mfa_totp"


def _complete_email_otp(session, email: str, after_ts: float, *, auth_method: str) -> tuple[dict, str]:
    try:
        result = _validate_with_retry(session, email, after_ts)
        continue_url = _extract_continue_url(result)
        if _is_mfa(result, continue_url):
            # The email OTP response may itself hand off to MFA.  The caller
            # provides the secret through the outer state machine in that case.
            return result, auth_method
        return _follow_and_fetch(session, continue_url, referer=_EMAIL_PATH), auth_method
    except ProtocolV2AuthError:
        raise
    except AccountUnusableError:
        raise
    except Exception as exc:
        error = ProtocolV2AuthError(
            "email_otp_failed",
            category="email",
            roxy_fallback_allowed=False,
        )
        error.diagnostics = {
            "operation": "email_otp",
            "failure_kind": {
                "ForwardIMAPNoMailTimeout": "no_mail",
                "ForwardIMAPError": "imap_error",
                "TimeoutError": "manual_timeout",
                "EmailOtpInvalidError": "invalid_code",
            }.get(type(exc).__name__, "otp_error"),
            "exception_type": type(exc).__name__[:80],
        }
        raise error from exc


def _start_email_session(email: str, proxy: str | None, *, identity=None, context_recorder=None):
    """Start one fresh auth session for a controlled email fallback."""
    session = None
    try:
        session, authorize_url = _network_preflight_with_retry(
            email,
            proxy,
            max_attempts=1,
            identity=identity,
            context_recorder=context_recorder,
        )
        after_ts = time.time()
        final_url = follow_authorize(session, authorize_url)
        dead_code = detect_account_unusable_text(final_url)
        if dead_code:
            raise ProtocolV2AuthError("account_deactivated", category="account", roxy_fallback_allowed=False)
        final_url_text = str(final_url or "").lower()
        if "email-verification" in final_url_text:
            # The authorize flow has already established the email challenge.  Do
            # not issue a second send request here; the OTP waiter starts from the
            # timestamp captured before the redirect.
            return session, after_ts
        if "/log-in/password" in final_url_text:
            # A password page is not an email challenge.  The browser UI may offer
            # an explicit "use a one-time code" action, but the protocol adapter
            # has no safe, version-stable action for that UI state.  In particular,
            # /api/accounts/email-otp/send from this page can redirect to /error.
            raise ProtocolV2AuthError(
                "passwordless_fallback_unavailable",
                category="auth",
                roxy_fallback_allowed=False,
            )
        raise ProtocolV2AuthError(
            "auth_page_unknown",
            category="response",
            roxy_fallback_allowed=False,
        )
    except Exception:
        if context_recorder is not None and session is not None:
            context_recorder.finish_session(session, status="failed", result_code="email_session_start_failed")
        try:
            if session is not None:
                session.session.close()
        except Exception:
            pass
        raise


def _open_offered_password_login(session, final_url: str) -> str:
    """邮箱失效时沿用当前会话，只访问认证页实际提供的密码登录入口。"""
    def trusted_path(url: str, path: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https" and parsed.netloc.lower() == "auth.openai.com"
            and parsed.path.rstrip("/") == path
        )

    def unavailable() -> ProtocolV2AuthError:
        error = ProtocolV2AuthError(
            "password_login_unavailable", category="auth", roxy_fallback_allowed=True,
        )
        error.mutation_submitted = False
        error.action_dispatched = False
        return error

    def navigate(url: str, referer: str):
        try:
            response = session.get(
                url, headers=session.get_auth_navigate_headers(referer=referer),
                allow_redirects=True,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            error = unavailable()
            error.category = "network"
            error.diagnostics = _request_diagnostics(
                exc, operation="password_login",
                response_observed=_response_status(getattr(exc, "response", None)) is not None,
            )
            raise error from exc

    if not trusted_path(final_url, "/email-verification"):
        raise unavailable()
    response = navigate(final_url, _EMAIL_PATH)
    current_url = str(getattr(response, "url", "") or final_url)
    if trusted_path(current_url, "/log-in/password"):
        return current_url
    if not trusted_path(current_url, "/email-verification"):
        raise unavailable()

    class PasswordLinkParser(HTMLParser):
        target = ""

        def handle_starttag(self, tag, attrs):
            if tag.lower() != "a" or self.target:
                return
            href = dict(attrs).get("href") or ""
            target = urljoin(current_url, href)
            if trusted_path(target, "/log-in/password"):
                self.target = target

    parser = PasswordLinkParser()
    parser.feed(str(getattr(response, "text", "") or ""))
    if not parser.target:
        raise unavailable()
    response = navigate(parser.target, current_url)
    password_url = str(getattr(response, "url", "") or "")
    if not trusted_path(password_url, "/log-in/password"):
        raise unavailable()
    logger.info("[查活][Protocol v2] 邮箱已失效，已切换到页面提供的密码登录入口")
    return password_url


def _refresh_with_password(
    email: str,
    proxy: str | None,
    *,
    proxy_supplier: Callable[[int], str | None] | None,
    identity=None,
    context_recorder=None,
    on_remote_request_started: Callable[[], None] | None = None,
    on_authenticated=None,
) -> dict:
    def completed(*args, **kwargs):
        result = _success(*args, **kwargs)
        return on_authenticated(result, args[2]) if callable(on_authenticated) else result

    session = None
    fallback_session = None
    checked_at = _now()
    password, totp_secret = get_account_login_credentials(email)
    email_invalid = account_email_is_invalid(email)
    if not password:
        if email_invalid:
            error = ProtocolV2AuthError(
                "password_missing", category="configuration", roxy_fallback_allowed=False,
            )
            error.mutation_submitted = False
            error.action_dispatched = False
            raise error
        # The v2 adapter does not invent a different no-password flow.  Keep
        # the established email/re-auth implementation as a compatibility
        # adapter and label the result so the task UI remains truthful.
        result = check_account_liveness(
            email,
            proxy=proxy,
            clear_log=False,
            proxy_supplier=proxy_supplier,
            on_remote_request_started=on_remote_request_started,
            **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
        )
        result.setdefault("auth_method", "legacy_email_otp")
        result.setdefault("live_check_driver", "protocol_v2")
        return result

    fallback_used = False
    auth_method = "protocol_v2"
    password_auth_status = ""
    try:
        session, authorize_url = _network_preflight_with_retry(
            email,
            proxy,
            proxy_supplier=proxy_supplier,
            identity=identity,
            context_recorder=context_recorder,
        )
        if callable(on_remote_request_started):
            on_remote_request_started()
        otp_after_ts = time.time()
        final_url = follow_authorize(session, authorize_url)
        dead_code = detect_account_unusable_text(final_url)
        if dead_code:
            raise ProtocolV2AuthError("account_deactivated", category="account", roxy_fallback_allowed=False)

        parsed_final_url = urlparse(str(final_url or ""))
        if (
            email_invalid and parsed_final_url.hostname == "auth.openai.com"
            and parsed_final_url.path.rstrip("/") == "/email-verification"
        ):
            auth_method = "password"
            final_url = _open_offered_password_login(session, str(final_url))
            parsed_final_url = urlparse(final_url)
        final_host = (parsed_final_url.hostname or "").lower()
        final_path = parsed_final_url.path.lower()
        if final_host == "auth.openai.com" and final_path == "/email-verification":
            auth_method = "email_otp"
            password_auth_status = "skipped"
            # 到达验证页不代表已发信；显式发码后再开始等待本轮邮件。
            otp_after_ts = time.time()
            try:
                send_email_otp(session)
            except Exception as exc:
                error = ProtocolV2AuthError(
                    "email_otp_send_failed",
                    category="email",
                    roxy_fallback_allowed=False,
                )
                error.diagnostics = {
                    "operation": "email_otp_send",
                    "failure_kind": exc.reason if isinstance(exc, EmailOtpSendError) else "transport_error",
                    "http_status": exc.status_code if isinstance(exc, EmailOtpSendError) else None,
                    "exception_type": type(exc).__name__[:80],
                }
                raise error from exc
            email_result, auth_method = _complete_email_otp(
                session,
                email,
                otp_after_ts,
                auth_method=auth_method,
            )
            email_continue_url = _extract_continue_url(email_result)
            if _is_mfa(email_result, email_continue_url):
                if not totp_secret:
                    raise ProtocolV2AuthError(
                        "mfa_secret_missing",
                        category="configuration",
                        roxy_fallback_allowed=False,
                    )
                session_info, _ = _complete_mfa(session, email_result, email_continue_url, totp_secret)
                auth_method = "email_otp_mfa"
            else:
                session_info = email_result
            return completed(
                checked_at,
                session_info,
                session,
                auth_method=auth_method,
                password_auth_status=password_auth_status,
                fallback_used=False,
            )

        if final_host == "auth.openai.com" and final_path.startswith("/mfa-challenge"):
            auth_method = "mfa_totp"
            password_auth_status = "skipped"
            if not totp_secret:
                raise ProtocolV2AuthError(
                    "mfa_secret_missing",
                    category="configuration",
                    roxy_fallback_allowed=False,
                )
            factor_id = _extract_factor_id(None, str(final_url))
            if not factor_id:
                raise ProtocolV2AuthError("mfa_factor_missing", category="response", roxy_fallback_allowed=False)
            session_info, _ = _complete_mfa(session, {"continue_url": str(final_url)}, str(final_url), totp_secret)
            return completed(
                checked_at,
                session_info,
                session,
                auth_method=auth_method,
                password_auth_status=password_auth_status,
                fallback_used=False,
            )

        if final_host != "auth.openai.com" or final_path != "/log-in/password":
            raise ProtocolV2AuthError(
                "auth_page_unknown",
                category="response",
                roxy_fallback_allowed=True,
            )

        try:
            auth_method = "password"
            password_result = _password_verify(session, password)
        except ProtocolV2AuthError as exc:
            if exc.code != "password_rejected":
                raise
            if email_invalid or not bool(getattr(account_config, "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", False)):
                raise
            # Do not reuse the rejected session.  The fallback starts a fresh
            # cookie jar, while keeping the original selected proxy.
            fallback_used = True
            if context_recorder is not None:
                context_recorder.finish_session(
                    session,
                    status="failed",
                    result_code="password_rejected",
                )
            fallback_session, fallback_after_ts = _start_email_session(
                email,
                getattr(session, "proxy", proxy),
                identity=identity,
                context_recorder=context_recorder,
            )
            try:
                email_result, auth_method = _complete_email_otp(
                    fallback_session,
                    email,
                    fallback_after_ts,
                    auth_method="password_fallback_email_otp",
                )
                if _is_mfa(email_result, _extract_continue_url(email_result)):
                    if not totp_secret:
                        raise ProtocolV2AuthError(
                            "mfa_secret_missing",
                            category="configuration",
                            roxy_fallback_allowed=False,
                        )
                    session_info, auth_method = _complete_mfa(
                        fallback_session,
                        email_result,
                        _extract_continue_url(email_result),
                        totp_secret,
                    )
                else:
                    session_info = email_result
                return completed(
                    checked_at,
                    session_info,
                    fallback_session,
                    auth_method=auth_method,
                    password_auth_status="rejected",
                    fallback_used=True,
                )
            except Exception as fallback_exc:
                if isinstance(fallback_exc, ProtocolV2AuthError) and fallback_exc.code == "passwordless_fallback_unavailable":
                    raise ProtocolV2AuthError(
                        fallback_exc.code,
                        category=fallback_exc.category,
                        retryable=fallback_exc.retryable,
                        roxy_fallback_allowed=False,
                    ) from fallback_exc
                error = ProtocolV2AuthError(
                    "password_rejected_email_fallback_failed",
                    category="email",
                    roxy_fallback_allowed=False,
                )
                # 外层保留“密码被拒绝且邮箱兜底失败”，同时记录内层安全码，
                # 避免取码超时、回调异常等原因在任务摘要中消失。
                error.diagnostics = {
                    "operation": "password_email_fallback",
                    "failure_kind": "fallback_failed",
                    "exception_type": type(fallback_exc).__name__[:80],
                }
                if isinstance(fallback_exc, ProtocolV2AuthError):
                    inner = fallback_exc.diagnostics if isinstance(fallback_exc.diagnostics, dict) else {}
                    error.diagnostics["cause_code"] = fallback_exc.code
                    for key, target in (
                        ("operation", "cause_operation"),
                        ("failure_kind", "cause_failure_kind"),
                        ("http_status", "http_status"),
                        ("response_observed", "response_observed"),
                        ("exception_type", "exception_type"),
                    ):
                        if key in inner:
                            error.diagnostics[target] = inner[key]
                raise error from fallback_exc

        continue_url = _extract_continue_url(password_result)
        if _is_mfa(password_result, continue_url):
            if not totp_secret:
                raise ProtocolV2AuthError(
                    "mfa_secret_missing",
                    category="configuration",
                    roxy_fallback_allowed=False,
                )
            session_info, auth_method = _complete_mfa(session, password_result, continue_url, totp_secret)
            password_auth_status = "verified"
        elif _is_email_otp(password_result, continue_url):
            if email_invalid:
                password_auth_status = "verified"
                raise ProtocolV2AuthError(
                    "email_verification_required", category="email", roxy_fallback_allowed=False,
                    response_observed=True,
                )
            email_result, auth_method = _complete_email_otp(
                session,
                email,
                otp_after_ts,
                auth_method="password_email_otp",
            )
            if _is_mfa(email_result, _extract_continue_url(email_result)):
                if not totp_secret:
                    raise ProtocolV2AuthError(
                        "mfa_secret_missing",
                        category="configuration",
                        roxy_fallback_allowed=False,
                    )
                session_info, _ = _complete_mfa(
                    session,
                    email_result,
                    _extract_continue_url(email_result),
                    totp_secret,
                )
                auth_method = "password_email_otp_mfa"
            else:
                session_info = email_result
            password_auth_status = "verified"
        elif continue_url:
            session_info = _follow_and_fetch(session, continue_url, referer=_PASSWORD_PATH)
            auth_method = "password"
            password_auth_status = "verified"
        else:
            raise ProtocolV2AuthError("auth_page_unknown", category="response", roxy_fallback_allowed=True)
        return completed(
            checked_at,
            session_info,
            session,
            auth_method=auth_method,
            password_auth_status="verified",
            fallback_used=fallback_used,
        )
    except ProtocolV2AuthError as exc:
        # Keep the state-machine location without copying any response body.
        exc.auth_method = auth_method
        if password_auth_status:
            exc.password_auth_status = password_auth_status
        raise
    finally:
        if context_recorder is not None:
            if fallback_session is not None:
                context_recorder.finish_session(
                    fallback_session,
                    status="success" if fallback_used and 'session_info' in locals() else "failed",
                    result_code="password_fallback_email_otp" if fallback_used and 'session_info' in locals() else "password_fallback_failed",
                )
            if session is not None:
                context_recorder.finish_session(
                    session,
                    status="success" if not fallback_used and 'session_info' in locals() else "failed",
                    result_code="authenticated" if not fallback_used and 'session_info' in locals() else "protocol_v2_failed",
                )
        for item in (fallback_session, session):
            try:
                if item is not None:
                    item.session.close()
            except Exception:
                pass


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

    try:
        result = _refresh_with_password(
            email,
            proxy,
            proxy_supplier=proxy_supplier,
            identity=identity,
            context_recorder=context_recorder,
            on_remote_request_started=mark_remote_request_started,
            **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
        )
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
