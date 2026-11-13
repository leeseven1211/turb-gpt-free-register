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
    """Read the server's auth context from response or its signed cookie.

    Cookie data only selects a server challenge; final Session/AT identity is
    still verified independently. Never expose decoded contents in results.
    """
    explicit = payload.get("oai-client-auth-session")
    if isinstance(explicit, dict) and explicit:
        return explicit
    jar = session.session.cookies
    candidates = []
    for cookie in getattr(jar, "jar", jar):
        if (getattr(cookie, "name", "") != "oai-client-auth-session"
                or str(getattr(cookie, "domain", "")).lower().lstrip(".") not in {"auth.openai.com", "openai.com"}
                or (getattr(cookie, "expires", None) and cookie.expires <= time.time())):
            continue
        raw = str(cookie.value or "")
        if len(raw) > 65536:
            continue
        raw = unquote(raw).strip('"')
        # Both signed payload.signature and JWT header.payload.signature occur.
        for segment in raw.split(".")[:2]:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)).decode("utf-8"))
            except (ValueError, UnicodeError):
                continue
            if not isinstance(decoded, dict):
                continue
            decoded = decoded.get("oai-client-auth-session", decoded)
            if not isinstance(decoded, dict):
                continue
            context = {key: decoded[key] for key in ("mfa_challenge_factors", "mfa_factors", "workspaces", "workspace_id") if key in decoded}
            if context:
                candidates.append(context)
    unique = {json.dumps(value, sort_keys=True): value for value in candidates}
    if len(unique) > 1:
        raise _error("auth_context_ambiguous", category="response")
    return next(iter(unique.values()), {})


def _trusted_url(value: str, *, base=_AUTH) -> str:
    target = urljoin(base, str(value or ""))
    try:
        parsed = urlparse(target)
        if (parsed.scheme != "https" or parsed.hostname not in _HOSTS
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            raise ValueError
    except (TypeError, ValueError):
        raise _error("untrusted_auth_url", category="response") from None
    return target


def _continue(payload: dict) -> str:
    page = payload.get("page") or {}
    page = page if isinstance(page, dict) else {}
    nested = page.get("payload") or {}
    nested = nested if isinstance(nested, dict) else {}
    value = (payload.get("continue_url") or payload.get("external_url") or payload.get("url")
             or page.get("continue_url") or page.get("external_url") or page.get("url") or nested.get("url"))
    return _trusted_url(value) if value else ""


def _follow(session, url: str, *, referer=_CHAT + "/") -> str:
    """Check every redirect before sending any cookies to the next origin."""
    current = _trusted_url(url)
    for _ in range(12):
        parsed = urlparse(current)
        header_method = session.get_chatgpt_navigate_headers if parsed.hostname == "chatgpt.com" else session.get_auth_navigate_headers
        response = session.get(current, headers=header_method(referer=referer), allow_redirects=False)
        status = int(getattr(response, "status_code", 0) or 0)
        if status in {301, 302, 303, 307, 308}:
            location = str((getattr(response, "headers", {}) or {}).get("location") or "")
            if not location:
                raise _error("auth_redirect_invalid", category="response")
            referer, current = current, _trusted_url(location, base=current)
            continue
        if not 200 <= status < 300:
            error = _error("auth_navigation_failed", category="network", retryable=status in {403, 429} or status >= 500)
            error.diagnostics = {"operation": "protocol_v3_auth", "http_status": status, "response_observed": True}
            raise error
        return current
    raise _error("auth_redirect_limit", category="response")


def _factor(payload: dict, url: str) -> str:
    from core.accounts.liveness.protocol.v2 import _extract_factor_id
    direct = _extract_factor_id(payload, url)
    if direct:
        return direct
    context = payload.get("oai-client-auth-session") or {}
    if isinstance(context, dict):
        factors = [item for key in ("mfa_challenge_factors", "mfa_factors")
                   for item in (context.get(key) or []) if isinstance(item, dict) and item.get("factor_type") == "totp" and item.get("id")]
        unique = {str(item["id"]) for item in factors}
        if len(unique) == 1:
            return unique.pop()
    raise _error("mfa_factor_missing", category="response")


def _account_identity(target: dict) -> tuple[str, str]:
    saved = target.get("chatgpt_session") or {}
    if isinstance(saved, str):
        try:
            saved = json.loads(saved)
        except (ValueError, TypeError):
            saved = {}
    saved = saved if isinstance(saved, dict) else {}
    try:
        claims = token_claims(str(target.get("access_token") or ""))
    except Exception:
        claims = {}
    return (str(target.get("user_id") or (saved.get("user") or {}).get("id") or claims.get("user_id") or ""),
            str(target.get("chatgpt_account_id") or (saved.get("account") or {}).get("id") or claims.get("account_id") or ""))


def _verify_identity(info: dict, email: str, target: dict) -> None:
    user, account = info.get("user") or {}, info.get("account") or {}
    if not isinstance(user, dict) or not isinstance(account, dict) or not str(user.get("email") or "").strip():
        raise _error("identity_unconfirmed", category="response")
    if str(user["email"]).strip().lower() != email.lower():
        raise _error("identity_mismatch", category="account")
    user_id, account_id = _account_identity(target)
    if (user_id and str(user.get("id") or "") != user_id) or (account_id and str(account.get("id") or "") != account_id):
        raise _error("identity_mismatch", category="account")
    try:
        claims = token_claims(str(info.get("accessToken") or ""))
    except Exception:
        claims = {}
    if ((claims.get("email") and str(claims["email"]).strip().lower() != email.lower())
            or (claims.get("user_id") and str(claims["user_id"]) != str(user.get("id") or ""))
            or (claims.get("account_id") and str(claims["account_id"]) != str(account.get("id") or ""))):
        raise _error("identity_mismatch", category="account")


def _workspace(payload: dict, target: dict) -> str:
    page = payload.get("page") or {}
    context = payload.get("oai-client-auth-session") or {}
    candidates = context.get("workspaces") if isinstance(context, dict) else None
    if candidates is None and isinstance(page, dict):
        nested = page.get("payload") or {}
        candidates = nested.get("workspaces") if isinstance(nested, dict) else None
    candidates = [item for item in (candidates or []) if isinstance(item, dict) and item.get("id")]
    unique = {str(item["id"]): item for item in candidates}
    expected = _account_identity(target)[1]
    matched = [str(item["id"]) for item in candidates if expected and expected in {str(item["id"]), str(item.get("account_id") or "")}]
    if len(set(matched)) == 1:
        return matched[0]
    if len(unique) == 1:
        return next(iter(unique))
    raise _error("workspace_ambiguous" if unique else "workspace_missing", category="response")


def _read_session(session, *, cached: bool) -> dict | None:
    try:
        response = session.get(_SESSION_URL, headers=session.get_nextauth_headers(referer=_CHAT + "/"), allow_redirects=False)
    except (OperationCancelled, OperationLeaseLost):
        raise
    except Exception:
        raise _error("cached_session_network_failed" if cached else "session_fetch_failed", category="network", retryable=True) from None
    status = int(getattr(response, "status_code", 0) or 0)
    if cached and status == 401:
        return None
    if not 200 <= status < 300:
        error = _error("cached_session_http_failed" if cached else "session_fetch_failed", category="network", retryable=status in {403, 429} or status >= 500)
        error.diagnostics = {"operation": "session_reuse" if cached else "protocol_v3_auth", "http_status": status, "response_observed": True}
        raise error
    try:
        info = response.json()
    except Exception:
        raise _error("cached_session_invalid_response" if cached else "session_invalid_response", category="response") from None
    if not isinstance(info, dict):
        raise _error("cached_session_invalid_response" if cached else "session_invalid_response", category="response")
    if not str(info.get("accessToken") or "").strip():
        if cached and not info:
            return None
        raise _error("access_token_missing", category="response")
    try:
        expired = token_claims(str(info["accessToken"])).get("token_expired") is True
    except (ValueError, TypeError, OverflowError):
        raise _error("session_invalid_response", category="response") from None
    if expired:
        raise _error("access_token_expired", category="auth")
    return info


def _cookie_payload(session, info: dict) -> dict:
    cookies = []
    cookie_jar = session.session.cookies
    for item in getattr(cookie_jar, "jar", cookie_jar):
        domain = str(getattr(item, "domain", "") or "").lower().lstrip(".")
        expiry = getattr(item, "expires", None)
        if domain not in _COOKIE_HOSTS or (expiry and float(expiry) <= time.time()):
            continue
        cookies.append({"name": str(item.name), "value": str(item.value), "domain": str(item.domain),
                        "path": str(item.path or "/"), "secure": bool(item.secure), "expires": expiry})
    # Store only device fields, never route credentials, navigation URLs or trace IDs.
    profile = {key: value for key, value in (getattr(session, "browser_profile", {}) or {}).items()
               if key in _STABLE_PROFILE_FIELDS and key not in {"script_src_samples", "window_feature_flags", "navigator_proto_samples", "document_key_samples", "window_key_samples"}}
    return {"cookies": cookies, "device_id": str(session.device_id), "browser_profile": profile,
            "user_id": str((info.get("user") or {}).get("id") or ""),
            "chatgpt_account_id": str((info.get("account") or {}).get("id") or "")}


def _restore_cookies(session, payload: dict) -> None:
    cookies = payload.get("cookies")
    if not isinstance(cookies, list) or not cookies or len(cookies) > 200:
        raise ValueError("invalid_cached_cookies")
    for item in cookies:
        if not isinstance(item, dict) or str(item.get("domain") or "").lower().lstrip(".") not in _COOKIE_HOSTS:
            raise ValueError("invalid_cached_cookie_domain")
        name, value = item.get("name"), item.get("value")
        if not isinstance(name, str) or not isinstance(value, str) or not name:
            raise ValueError("invalid_cached_cookie")
        expiry = item.get("expires")
        if expiry is not None:
            expiry = int(expiry)
            if expiry <= time.time():
                continue
        domain = item["domain"]
        # curl_cffi Cookies.set lacks expires; the underlying standard CookieJar
        # retains it and works with both real curl and offline test containers.
        jar = session.session.cookies
        getattr(jar, "jar", jar).set_cookie(Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=domain.startswith("."),
            path=str(item.get("path") or "/"), path_specified=True,
            secure=bool(item.get("secure", True)), expires=expiry, discard=expiry is None,
            comment=None, comment_url=None, rest={}, rfc2109=False,
        ))


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
    url = _follow(session, initial_url)
    payload = {"continue_url": url}
    methods, seen = progress["methods"], set()
    for _ in range(8):
        context = _client_auth_context(session, payload)
        if context:
            payload = {**payload, "oai-client-auth-session": context}
        url = _continue(payload)
        page = payload.get("page") or {}
        kind = str(page.get("type") or "").lower() if isinstance(page, dict) else ""
        path = urlparse(url).path.rstrip("/").lower() if url else ""
        if kind in {"about_you", "about-you", "create_account", "create-account"} or path in {"/about-you", "/create-account/password", "/create-account"}:
            raise _error("account_profile_required", category="account")
        if "mfa" in kind or path.startswith("/mfa-challenge"):
            stage = "mfa"
        elif kind == "workspace" or path == "/workspace":
            stage = "workspace"
        elif path == "/log-in/password" or kind in {"password", "login_password", "password_verify"}:
            stage = "password"
        elif path == "/email-verification" or kind in {"email_otp", "email_verification"}:
            stage = "email_otp"
        elif url:
            stage = "callback"
        else:
            raise _error("auth_page_unknown", category="response")
        if stage == "email_otp" and account_email_is_invalid(email):
            if "password" in seen:
                raise _error("email_verification_required", category="email")
            if not password:
                raise _error("password_missing", category="configuration")
            # Navigation only: the server must actually offer the password page
            # before a saved password is submitted. Never bypass an email challenge.
            offered = _follow(session, _AUTH + "/log-in/password", referer=url)
            if urlparse(offered).path.rstrip("/") != "/log-in/password":
                raise _error("password_login_unavailable", category="auth")
            payload = {"continue_url": offered}
            continue
        if stage in seen:
            raise _error("auth_challenge_loop", category="response")
        seen.add(stage)
        progress["attempted"] = stage
        if stage == "password":
            if not password:
                raise _error("password_missing", category="configuration")
            payload = _password_verify(session, password)
            methods.append("password")
        elif stage == "email_otp":
            if account_email_is_invalid(email):
                raise _error("email_verification_required", category="email")
            requested_at = time.time()
            from core.network.at_transport_recovery import current_scope

            if current_scope() is not None:
                def validate_current_code(code):
                    # v3 保持原有 POST、禁止跳转及结构化提交回执，不切换到共享验证器。
                    return _post_json(
                        session, _AUTH + "/api/accounts/email-otp/validate",
                        headers=session.get_auth_headers(referer=_AUTH + "/email-verification"),
                        payload={"code": code}, operation="email_otp_validate",
                    )

                try:
                    payload = _validate_with_retry(session, email, requested_at, at_validator=validate_current_code)
                except (OperationCancelled, OperationLeaseLost, ProtocolV2AuthError):
                    raise
                except Exception as exc:
                    _reraise_control(exc)
                    error = _error("email_otp_failed", category="email")
                    error.diagnostics = otp_failure_diagnostics(exc)
                    raise error from exc
            else:
                send_email_otp(session)
                try:
                    code = wait_for_otp(email, after_ts=requested_at)
                except (OperationCancelled, OperationLeaseLost):
                    raise
                except Exception as exc:
                    error = _error("email_otp_failed", category="email")
                    error.diagnostics = otp_failure_diagnostics(exc)
                    raise error from None
                payload = _post_json(session, _AUTH + "/api/accounts/email-otp/validate", headers=session.get_auth_headers(referer=_AUTH + "/email-verification"), payload={"code": code}, operation="email_otp_validate")
            methods.append("email_otp")
        elif stage == "mfa":
            if not secret:
                raise _error("mfa_secret_missing", category="configuration")
            factor = _factor(payload, url)
            _mfa_issue_challenge(session, factor)
            payload = _mfa_verify(session, factor, _totp_code(secret))
            methods.append("mfa")
        elif stage == "workspace":
            payload = _post_json(session, _AUTH + "/api/accounts/workspace/select", headers=session.get_auth_headers(referer=url or _AUTH + "/workspace"), payload={"workspace_id": _workspace(payload, target)}, operation="workspace_select")
        else:
            final = _follow(session, url)
            final_path = urlparse(final).path.rstrip("/").lower()
            if final_path in {"/about-you", "/log-in/password", "/email-verification", "/workspace"} or final_path.startswith("/mfa-challenge"):
                payload = {"continue_url": final}
                seen.discard("callback")
                continue
            if urlparse(final).hostname != "chatgpt.com":
                raise _error("auth_page_unknown", category="response")
            return _read_session(session, cached=False), methods or ["existing_session"]
    raise _error("auth_challenge_loop", category="response")


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
