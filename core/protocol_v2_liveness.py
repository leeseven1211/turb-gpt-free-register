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
import time
from datetime import datetime
from typing import Callable
from urllib.parse import parse_qs, urlparse

import pyotp

from config import account as account_config
from core.account_export import fetch_session, follow_oauth_callback
from core.account_liveness import (
    _network_preflight_with_retry,
    _validate_with_retry,
    check_account_liveness,
)
from core.openai_auth import (
    AccountUnusableError,
    build_sentinel_header,
    detect_account_unusable_response_body,
    detect_account_unusable_text,
    follow_authorize,
    request_sentinel_token,
    send_email_otp,
)
from core.account_credentials import get_account_login_credentials

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
    "login failed",
    "密码错误",
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
            "mfa_rejected",
            "mfa_secret_missing",
        }
        self.response_observed = bool(response_observed)
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
            response_observed=False,
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
        raise _request_error(exc, operation=operation) from exc

    status = _response_status(response)
    if status is None or status < 200 or status >= 300:
        exc = RuntimeError(f"{operation} status={status or 0}")
        exc.response = response
        raise _request_error(exc, operation=operation) from exc
    try:
        data = response.json()
    except Exception as exc:
        raise ProtocolV2AuthError(
            f"{operation}_invalid_response",
            category="response",
            roxy_fallback_allowed=True,
            response_observed=True,
        ) from exc
    if not isinstance(data, dict):
        raise ProtocolV2AuthError(
            f"{operation}_invalid_response",
            category="response",
            roxy_fallback_allowed=True,
            response_observed=True,
        )
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
        raise ProtocolV2AuthError(
            "password_sentinel_failed",
            category="network",
            retryable=True,
            roxy_fallback_allowed=True,
        ) from exc
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
        raise ProtocolV2AuthError(
            "email_otp_failed",
            category="email",
            roxy_fallback_allowed=False,
        ) from exc


def _start_email_session(email: str, proxy: str | None):
    """Start one fresh auth session for a controlled email fallback."""
    session, authorize_url = _network_preflight_with_retry(email, proxy, max_attempts=1)
    after_ts = time.time()
    final_url = follow_authorize(session, authorize_url)
    dead_code = detect_account_unusable_text(final_url)
    if dead_code:
        raise ProtocolV2AuthError("account_deactivated", category="account", roxy_fallback_allowed=False)
    if "email-verification" not in str(final_url).lower():
        # The password page may remain the visible route after rejection.  Ask
        # for the one-time code explicitly instead of blindly clicking a page.
        after_ts = time.time()
        send_email_otp(session, referer=str(final_url or _PASSWORD_PATH))
    return session, after_ts


def _refresh_with_password(
    email: str,
    proxy: str | None,
    *,
    proxy_supplier: Callable[[int], str | None] | None,
) -> dict:
    session = None
    fallback_session = None
    checked_at = _now()
    password, totp_secret = get_account_login_credentials(email)
    if not password:
        # The v2 adapter does not invent a different no-password flow.  Keep
        # the established email/re-auth implementation as a compatibility
        # adapter and label the result so the task UI remains truthful.
        result = check_account_liveness(
            email,
            proxy=proxy,
            clear_log=False,
            proxy_supplier=proxy_supplier,
        )
        result.setdefault("auth_method", "legacy_email_otp")
        result.setdefault("live_check_driver", "protocol_v2")
        return result

    fallback_used = False
    try:
        session, authorize_url = _network_preflight_with_retry(
            email,
            proxy,
            proxy_supplier=proxy_supplier,
        )
        otp_after_ts = time.time()
        final_url = follow_authorize(session, authorize_url)
        dead_code = detect_account_unusable_text(final_url)
        if dead_code:
            raise ProtocolV2AuthError("account_deactivated", category="account", roxy_fallback_allowed=False)

        try:
            password_result = _password_verify(session, password)
        except ProtocolV2AuthError as exc:
            if exc.code != "password_rejected":
                raise
            if not bool(getattr(account_config, "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", False)):
                raise
            # Do not reuse the rejected session.  The fallback starts a fresh
            # cookie jar, while keeping the original selected proxy.
            fallback_used = True
            fallback_session, fallback_after_ts = _start_email_session(email, getattr(session, "proxy", proxy))
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
                return _success(
                    checked_at,
                    session_info,
                    fallback_session,
                    auth_method=auth_method,
                    password_auth_status="rejected",
                    fallback_used=True,
                )
            except Exception as fallback_exc:
                raise ProtocolV2AuthError(
                    "password_rejected_email_fallback_failed",
                    category="email",
                    roxy_fallback_allowed=False,
                ) from fallback_exc

        continue_url = _extract_continue_url(password_result)
        if _is_mfa(password_result, continue_url):
            if not totp_secret:
                raise ProtocolV2AuthError(
                    "mfa_secret_missing",
                    category="configuration",
                    roxy_fallback_allowed=False,
                )
            session_info, auth_method = _complete_mfa(session, password_result, continue_url, totp_secret)
        elif _is_email_otp(password_result, continue_url):
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
        elif continue_url:
            session_info = _follow_and_fetch(session, continue_url, referer=_PASSWORD_PATH)
            auth_method = "password"
        else:
            raise ProtocolV2AuthError("auth_page_unknown", category="response", roxy_fallback_allowed=True)
        return _success(
            checked_at,
            session_info,
            session,
            auth_method=auth_method,
            password_auth_status="verified",
            fallback_used=fallback_used,
        )
    finally:
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
    }


def refresh_access_token(
    email: str,
    *,
    proxy: str | None = None,
    proxy_supplier: Callable[[int], str | None] | None = None,
) -> dict:
    """Run the opt-in Protocol v2 refresh flow and return a safe result."""
    checked_at = _now()
    try:
        return _refresh_with_password(email, proxy, proxy_supplier=proxy_supplier)
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
            "live_check_driver": "protocol_v2",
        }
    except ProtocolV2AuthError as exc:
        result = {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": exc.code,
            "error_category": exc.category,
            "auth_method": "protocol_v2",
            "roxy_fallback_allowed": exc.roxy_fallback_allowed,
            "retryable": exc.retryable,
            "live_check_driver": "protocol_v2",
        }
        if exc.code in {"password_rejected", "password_rejected_email_fallback_failed"}:
            result["password_auth_status"] = "rejected"
        return result
    except Exception as exc:
        logger.warning("[查活][Protocol v2] 认证失败：%s: %s", type(exc).__name__, str(exc)[:160])
        return {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": "protocol_v2_unknown_error",
            "error_category": "runtime",
            "auth_method": "protocol_v2",
            "roxy_fallback_allowed": True,
            "live_check_driver": "protocol_v2",
        }
