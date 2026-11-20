# -*- coding: utf-8 -*-
"""Authentication execution extracted without domain storage or task ownership.

Explicit dependencies preserve the original compatibility patch points.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_AUTH = "https://auth.openai.com"
_CHAT = "https://chatgpt.com"


@dataclass(frozen=True)
class ClientAuthContextDependencies:
    """Capabilities resolved by the domain at this invocation."""
    base64: Any
    json: Any
    time: Any
    unquote: Any
    _error: Any


def _client_auth_context(session, payload: dict, *, _deps: ClientAuthContextDependencies) -> dict:
    """Read the server's auth context from response or its signed cookie.

    Cookie data only selects a server challenge; final Session/AT identity is
    still verified independently. Never expose decoded contents in results.
    """
    base64 = _deps.base64
    json = _deps.json
    time = _deps.time
    unquote = _deps.unquote
    _error = _deps._error
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


@dataclass(frozen=True)
class TrustedUrlDependencies:
    """Capabilities resolved by the domain at this invocation."""
    urljoin: Any
    urlparse: Any
    _HOSTS: Any
    _error: Any


def _trusted_url(value: str, *, base=_AUTH, _deps: TrustedUrlDependencies) -> str:
    urljoin = _deps.urljoin
    urlparse = _deps.urlparse
    _HOSTS = _deps._HOSTS
    _error = _deps._error
    target = urljoin(base, str(value or ""))
    try:
        parsed = urlparse(target)
        if (parsed.scheme != "https" or parsed.hostname not in _HOSTS
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            raise ValueError
    except (TypeError, ValueError):
        raise _error("untrusted_auth_url", category="response") from None
    return target


@dataclass(frozen=True)
class ContinueDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _trusted_url: Any


def _continue(payload: dict, *, _deps: ContinueDependencies) -> str:
    _trusted_url = _deps._trusted_url
    page = payload.get("page") or {}
    page = page if isinstance(page, dict) else {}
    nested = page.get("payload") or {}
    nested = nested if isinstance(nested, dict) else {}
    value = (payload.get("continue_url") or payload.get("external_url") or payload.get("url")
             or page.get("continue_url") or page.get("external_url") or page.get("url") or nested.get("url"))
    return _trusted_url(value) if value else ""


@dataclass(frozen=True)
class FollowDependencies:
    """Capabilities resolved by the domain at this invocation."""
    urlparse: Any
    _error: Any
    _trusted_url: Any


def _follow(session, url: str, *, referer=_CHAT + '/', _deps: FollowDependencies) -> str:
    """Check every redirect before sending any cookies to the next origin."""
    urlparse = _deps.urlparse
    _error = _deps._error
    _trusted_url = _deps._trusted_url
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


@dataclass(frozen=True)
class FactorDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _error: Any
    _extract_factor_id: Any


def _factor(payload: dict, url: str, *, _deps: FactorDependencies) -> str:
    _error = _deps._error
    _extract_factor_id = _deps._extract_factor_id
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


@dataclass(frozen=True)
class AccountIdentityDependencies:
    """Capabilities resolved by the domain at this invocation."""
    json: Any
    token_claims: Any


def _account_identity(target: dict, *, _deps: AccountIdentityDependencies) -> tuple[str, str]:
    json = _deps.json
    token_claims = _deps.token_claims
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


@dataclass(frozen=True)
class VerifyIdentityDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _account_identity: Any
    _error: Any
    token_claims: Any


def _verify_identity(info: dict, email: str, target: dict, *, _deps: VerifyIdentityDependencies) -> None:
    _account_identity = _deps._account_identity
    _error = _deps._error
    token_claims = _deps.token_claims
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


@dataclass(frozen=True)
class WorkspaceDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _account_identity: Any
    _error: Any


def _workspace(payload: dict, target: dict, *, _deps: WorkspaceDependencies) -> str:
    _account_identity = _deps._account_identity
    _error = _deps._error
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


@dataclass(frozen=True)
class ReadSessionDependencies:
    """Capabilities resolved by the domain at this invocation."""
    OperationCancelled: Any
    OperationLeaseLost: Any
    _CHAT: Any
    _SESSION_URL: Any
    _error: Any
    token_claims: Any


def _read_session(session, *, cached: bool, _deps: ReadSessionDependencies) -> dict | None:
    OperationCancelled = _deps.OperationCancelled
    OperationLeaseLost = _deps.OperationLeaseLost
    _CHAT = _deps._CHAT
    _SESSION_URL = _deps._SESSION_URL
    _error = _deps._error
    token_claims = _deps.token_claims
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


@dataclass(frozen=True)
class CookiePayloadDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    _COOKIE_HOSTS: Any
    _STABLE_PROFILE_FIELDS: Any


def _cookie_payload(session, info: dict, *, _deps: CookiePayloadDependencies) -> dict:
    time = _deps.time
    _COOKIE_HOSTS = _deps._COOKIE_HOSTS
    _STABLE_PROFILE_FIELDS = _deps._STABLE_PROFILE_FIELDS
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


@dataclass(frozen=True)
class RestoreCookiesDependencies:
    """Capabilities resolved by the domain at this invocation."""
    Cookie: Any
    time: Any
    _COOKIE_HOSTS: Any


def _restore_cookies(session, payload: dict, *, _deps: RestoreCookiesDependencies) -> None:
    Cookie = _deps.Cookie
    time = _deps.time
    _COOKIE_HOSTS = _deps._COOKIE_HOSTS
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


@dataclass(frozen=True)
class AuthenticateDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    urlparse: Any
    OperationCancelled: Any
    OperationLeaseLost: Any
    ProtocolV2AuthError: Any
    _AUTH: Any
    _client_auth_context: Any
    _continue: Any
    _error: Any
    _factor: Any
    _follow: Any
    _mfa_issue_challenge: Any
    _mfa_verify: Any
    _password_verify: Any
    _post_json: Any
    _read_session: Any
    _reraise_control: Any
    _totp_code: Any
    _validate_with_retry: Any
    _workspace: Any
    account_email_is_invalid: Any
    otp_failure_diagnostics: Any
    send_email_otp: Any
    wait_for_otp: Any


def _authenticate(session, initial_url, *, email, target, password, secret, progress, _deps: AuthenticateDependencies):
    time = _deps.time
    urlparse = _deps.urlparse
    OperationCancelled = _deps.OperationCancelled
    OperationLeaseLost = _deps.OperationLeaseLost
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _AUTH = _deps._AUTH
    _client_auth_context = _deps._client_auth_context
    _continue = _deps._continue
    _error = _deps._error
    _factor = _deps._factor
    _follow = _deps._follow
    _mfa_issue_challenge = _deps._mfa_issue_challenge
    _mfa_verify = _deps._mfa_verify
    _password_verify = _deps._password_verify
    _post_json = _deps._post_json
    _read_session = _deps._read_session
    _reraise_control = _deps._reraise_control
    _totp_code = _deps._totp_code
    _validate_with_retry = _deps._validate_with_retry
    _workspace = _deps._workspace
    account_email_is_invalid = _deps.account_email_is_invalid
    otp_failure_diagnostics = _deps.otp_failure_diagnostics
    send_email_otp = _deps.send_email_otp
    wait_for_otp = _deps.wait_for_otp
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
