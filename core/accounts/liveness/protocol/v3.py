# -*- coding: utf-8 -*-
"""Independent AT refresh with verified cookie reuse and bounded challenges.

Only explicitly selected v3 tasks enter this module. Authentication primitives
are shared with v2 without modifying its state or registration behavior.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timezone
from http.cookiejar import Cookie
from urllib.parse import unquote, urljoin, urlparse

from core.accounts.credentials import account_email_is_invalid, get_account_login_credentials
from core.accounts.plans.client import token_claims
from core.accounts.liveness.protocol.legacy import _network_preflight_with_retry, _validate_with_retry
from core.accounts.liveness.protocol.otp_diagnostics import otp_failure_diagnostics
from core.accounts.liveness.protocol.v2 import (
    ProtocolV2AuthError, _mfa_issue_challenge, _mfa_verify, _password_verify,
    _post_json, _totp_code,
)
from core.auth.challenge import auth_result_for_operation
from core.auth.email_guard import serialize_email_auth
from core.auth.protocol.openai_auth import AccountUnusableError, AuthorizeRouteRejectedError, send_email_otp
from core.auth.protocol.session import BrowserSession
from core.email.provider import wait_for_otp
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost
from core.storage import accounts as db
from core.storage.accounts import protocol_sessions
from core.storage.accounts.auth import _STABLE_PROFILE_FIELDS

logger = logging.getLogger("core.protocol_v3_liveness")
_AUTH = "https://auth.openai.com"
_CHAT = "https://chatgpt.com"
_SESSION_URL = _CHAT + "/api/auth/session"
_HOSTS = {"auth.openai.com", "chatgpt.com"}
_COOKIE_HOSTS = _HOSTS | {"sentinel.openai.com"}


class ProtocolV3AuthError(ProtocolV2AuthError):
    pass


def _error(code, *, category="auth", retryable=False):
    return ProtocolV3AuthError(code, category=category, retryable=retryable, roxy_fallback_allowed=False)


def _reraise_control(exception: BaseException) -> None:
    """Recover cancellation/lease signals wrapped by compatibility primitives."""
    from core.auth.state_machine import CancellationRequested, StageTimeout
    from core.network.at_transport_recovery import AtRecoveryTimeout, current_scope

    pending, visited = [exception], set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, (OperationCancelled, OperationLeaseLost)):
            raise current
        if current_scope() is not None and isinstance(current, (AtRecoveryTimeout, StageTimeout, CancellationRequested)):
            raise current
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)


def _client_auth_context(session, payload: dict) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _client_auth_context as execute, ClientAuthContextDependencies
    dependencies = ClientAuthContextDependencies(
        base64=base64,
        json=json,
        time=time,
        unquote=unquote,
        _error=_error,
    )
    return execute(session, payload, _deps=dependencies)


def _trusted_url(value: str, *, base=_AUTH) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _trusted_url as execute, TrustedUrlDependencies
    dependencies = TrustedUrlDependencies(
        urljoin=urljoin,
        urlparse=urlparse,
        _HOSTS=_HOSTS,
        _error=_error,
    )
    return execute(value, base=base, _deps=dependencies)


def _continue(payload: dict) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _continue as execute, ContinueDependencies
    dependencies = ContinueDependencies(
        _trusted_url=_trusted_url,
    )
    return execute(payload, _deps=dependencies)


def _follow(session, url: str, *, referer=_CHAT + "/") -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _follow as execute, FollowDependencies
    dependencies = FollowDependencies(
        urlparse=urlparse,
        _error=_error,
        _trusted_url=_trusted_url,
    )
    return execute(session, url, referer=referer, _deps=dependencies)


def _factor(payload: dict, url: str) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _factor as execute, FactorDependencies
    from core.accounts.liveness.protocol.v2 import _extract_factor_id
    dependencies = FactorDependencies(
        _error=_error,
        _extract_factor_id=_extract_factor_id,
    )
    return execute(payload, url, _deps=dependencies)


def _account_identity(target: dict) -> tuple[str, str]:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _account_identity as execute, AccountIdentityDependencies
    dependencies = AccountIdentityDependencies(
        json=json,
        token_claims=token_claims,
    )
    return execute(target, _deps=dependencies)


def _verify_identity(info: dict, email: str, target: dict) -> None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _verify_identity as execute, VerifyIdentityDependencies
    dependencies = VerifyIdentityDependencies(
        _account_identity=_account_identity,
        _error=_error,
        token_claims=token_claims,
    )
    return execute(info, email, target, _deps=dependencies)


def _workspace(payload: dict, target: dict) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _workspace as execute, WorkspaceDependencies
    dependencies = WorkspaceDependencies(
        _account_identity=_account_identity,
        _error=_error,
    )
    return execute(payload, target, _deps=dependencies)


def _read_session(session, *, cached: bool) -> dict | None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _read_session as execute, ReadSessionDependencies
    dependencies = ReadSessionDependencies(
        OperationCancelled=OperationCancelled,
        OperationLeaseLost=OperationLeaseLost,
        _CHAT=_CHAT,
        _SESSION_URL=_SESSION_URL,
        _error=_error,
        token_claims=token_claims,
    )
    return execute(session, cached=cached, _deps=dependencies)


def _cookie_payload(session, info: dict) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _cookie_payload as execute, CookiePayloadDependencies
    dependencies = CookiePayloadDependencies(
        time=time,
        _COOKIE_HOSTS=_COOKIE_HOSTS,
        _STABLE_PROFILE_FIELDS=_STABLE_PROFILE_FIELDS,
    )
    return execute(session, info, _deps=dependencies)


def _restore_cookies(session, payload: dict) -> None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _restore_cookies as execute, RestoreCookiesDependencies
    dependencies = RestoreCookiesDependencies(
        Cookie=Cookie,
        time=time,
        _COOKIE_HOSTS=_COOKIE_HOSTS,
    )
    return execute(session, payload, _deps=dependencies)


def _cache_invalidate(account_id, email):
    if account_id:
        try:
            protocol_sessions.invalidate_session(account_id, email)
        except Exception:
            logger.warning("[Protocol v3] 私有会话清理不可用")


def _success(session, info, *, email, target, account_id, checked_at, methods, on_authenticated):
    _verify_identity(info, email, target)
    reused = methods == ["session_cookie"]
    result = {"ok": True, "status": "live", "checked_at": checked_at, "access_token": info["accessToken"],
              "session": info, "proxy_used": getattr(session, "proxy", None) or None,
              "validation_method": "authenticated_session", "auth_method": "_".join(methods),
              "live_check_driver": "protocol_v3", "session_reused": reused,
              "password_auth_status": "verified" if "password" in methods else "skipped",
              "email_otp_status": "success" if "email_otp" in methods else "skipped",
              "mfa_status": "success" if "mfa" in methods else "skipped",
              "fallback_used": False, "remote_request_started": not reused,
              "session_cache_status": "not_applicable"}
    if account_id:
        try:
            saved = protocol_sessions.save_session(account_id, email, _cookie_payload(session, info))
            result["session_cache_status"] = "saved" if saved is not False else "unavailable"
        except Exception:
            result["session_cache_status"] = "unavailable"
            logger.warning("[Protocol v3] AT 已取得，私有会话缓存未保存")
    result["auth"] = auth_result_for_operation(result, auth_method=result["auth_method"]).as_dict()
    return on_authenticated(result, session) if callable(on_authenticated) else result


def _authenticate(session, initial_url, *, email, target, password, secret, progress):
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v3 import _authenticate as execute, AuthenticateDependencies
    dependencies = AuthenticateDependencies(
        time=time,
        urlparse=urlparse,
        OperationCancelled=OperationCancelled,
        OperationLeaseLost=OperationLeaseLost,
        ProtocolV2AuthError=ProtocolV2AuthError,
        _AUTH=_AUTH,
        _client_auth_context=_client_auth_context,
        _continue=_continue,
        _error=_error,
        _factor=_factor,
        _follow=_follow,
        _mfa_issue_challenge=_mfa_issue_challenge,
        _mfa_verify=_mfa_verify,
        _password_verify=_password_verify,
        _post_json=_post_json,
        _read_session=_read_session,
        _reraise_control=_reraise_control,
        _totp_code=_totp_code,
        _validate_with_retry=_validate_with_retry,
        _workspace=_workspace,
        account_email_is_invalid=account_email_is_invalid,
        otp_failure_diagnostics=otp_failure_diagnostics,
        send_email_otp=send_email_otp,
        wait_for_otp=wait_for_otp,
    )
    return execute(session, initial_url, email=email, target=target, password=password, secret=secret, progress=progress, _deps=dependencies)


@serialize_email_auth
def refresh_access_token(email: str, *, proxy=None, proxy_supplier=None, identity=None,
                         context_recorder=None, on_remote_request_started=None,
                         on_authenticated=None, account_id: int | None = None) -> dict:
    email = str(email or "").strip()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session, remote_started, result = None, False, None
    progress = {"methods": [], "attempted": ""}
    try:
        target = (db.get_account(int(account_id)) if account_id else db.get_account_by_email(email)) or {}
        if not email or (account_id and not target) or (target and str(target.get("email") or "").strip().lower() != email.lower()):
            raise _error("account_reference_mismatch", category="configuration")
        actual_id = int(account_id or target.get("id") or 0) or None
        cached = None
        if actual_id:
            try:
                cached = protocol_sessions.load_session(actual_id, email)
            except Exception:
                logger.warning("[Protocol v3] 私有会话读取不可用，使用正常认证")
        if cached:
            try:
                selected_proxy = proxy_supplier(1) if proxy_supplier else proxy
            except (OperationCancelled, OperationLeaseLost):
                raise
            except Exception:
                raise _error("cached_session_network_failed", category="network", retryable=True) from None
            try:
                identity_payload = {"device_id": cached["device_id"], "browser_profile": cached["browser_profile"]}
                session = BrowserSession(proxy=selected_proxy, detect_exit_geo=False, identity=identity_payload)
                _restore_cookies(session, cached)
            except (OperationCancelled, OperationLeaseLost):
                raise
            except (KeyError, TypeError, ValueError):
                if session is not None:
                    session.session.close()
                session = None
                _cache_invalidate(actual_id, email)
            except Exception:
                raise _error("cached_session_network_failed", category="network", retryable=True) from None
            if session is not None:
                info = _read_session(session, cached=True)
                if info:
                    try:
                        _verify_identity(info, email, target)
                        _verify_identity(info, email, cached)
                    except ProtocolV2AuthError:
                        info = None
                if info:
                    result = _success(session, info, email=email, target=target, account_id=actual_id,
                                      checked_at=checked_at, methods=["session_cookie"], on_authenticated=on_authenticated)
                    return result
                session.session.close()
                session = None
                _cache_invalidate(actual_id, email)
        password, secret = get_account_login_credentials(email)
        session, authorize = _network_preflight_with_retry(email, proxy, proxy_supplier=proxy_supplier, identity=identity, context_recorder=context_recorder)
        if callable(on_remote_request_started):
            on_remote_request_started()
        remote_started = True
        info, methods = _authenticate(session, authorize, email=email, target=target, password=password, secret=secret, progress=progress)
        result = _success(session, info, email=email, target=target, account_id=actual_id,
                          checked_at=checked_at, methods=methods, on_authenticated=on_authenticated)
        return result
    except (OperationCancelled, OperationLeaseLost):
        raise
    except AccountUnusableError:
        result = {"ok": False, "status": "deactivated", "error": "account_deactivated", "error_category": "account", "roxy_fallback_allowed": False}
    except AuthorizeRouteRejectedError as exc:
        result = {"ok": False, "status": "failed", "error": "auth_route_rejected", "error_category": "network", "http_status": int(exc.status_code or 0) or None, "roxy_fallback_allowed": True, "retryable": True}
    except ProtocolV2AuthError as exc:
        _reraise_control(exc)
        result = {"ok": False, "status": "deactivated" if exc.code == "account_deactivated" else "failed",
                  "error": exc.code, "error_category": exc.category, "roxy_fallback_allowed": exc.roxy_fallback_allowed,
                  "retryable": exc.retryable}
        if exc.mutation_submitted is not None:
            result["mutation_submitted"] = exc.mutation_submitted
        if exc.action_dispatched is not None:
            result.update(action_dispatched=exc.action_dispatched, remote_response_received=exc.response_observed)
        if exc.reconcile_required:
            result.update(reconcile_required=True, manual_reconcile=True, next_action="manual_reconcile")
        if exc.code == "password_rejected":
            result["password_auth_status"] = "rejected"
        if exc.diagnostics:
            result["auth_diagnostics"] = exc.diagnostics
            result["http_status"] = exc.diagnostics.get("http_status")
    except Exception as exc:
        _reraise_control(exc)
        result = {"ok": False, "status": "failed", "error": "protocol_v3_unknown_error" if remote_started else "network_preflight_failed",
                  "error_category": "runtime" if remote_started else "network", "roxy_fallback_allowed": False}
    finally:
        if result is not None:
            if not result.get("ok"):
                completed, attempted = progress["methods"], progress["attempted"]
                chain = list(completed)
                if attempted in {"password", "email_otp", "mfa"} and attempted not in chain:
                    chain.append(attempted)
                if chain:
                    result.setdefault("auth_method", "_".join(chain))
                result.setdefault("password_auth_status", "verified" if "password" in completed else "" if attempted == "password" else "skipped")
                result.setdefault("email_otp_status", "success" if "email_otp" in completed else "failed" if attempted == "email_otp" else "skipped")
                result.setdefault("mfa_status", "success" if "mfa" in completed else "failed" if attempted == "mfa" else "skipped")
            result.setdefault("checked_at", checked_at)
            result.setdefault("live_check_driver", "protocol_v3")
            result.setdefault("auth_method", "protocol_v3")
            result.setdefault("remote_request_started", remote_started)
            if not remote_started:
                result.setdefault("mutation_submitted", False)
                result.setdefault("action_dispatched", False)
            result.setdefault("auth", auth_result_for_operation(result, auth_method=result["auth_method"]).as_dict())
        if session is not None:
            if context_recorder is not None:
                try:
                    context_recorder.finish_session(session, status="success" if result and result.get("ok") else "failed", result_code="authenticated" if result and result.get("ok") else (result or {}).get("error", "cancelled"))
                except Exception:
                    logger.warning("[Protocol v3] 认证上下文收尾不可用")
            try:
                session.session.close()
            except Exception:
                logger.warning("[Protocol v3] 会话连接关闭未完成")
    return result
