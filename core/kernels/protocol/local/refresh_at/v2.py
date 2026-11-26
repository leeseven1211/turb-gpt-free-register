# -*- coding: utf-8 -*-
"""Authentication execution extracted without domain storage or task ownership.

Explicit dependencies preserve the original compatibility patch points.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class PostJsonDependencies:
    """Capabilities resolved by the domain at this invocation."""
    json: Any
    ProtocolV2AuthError: Any
    _mark_auth_submission: Any
    _request_diagnostics: Any
    _request_error: Any
    _response_status: Any


def _post_json(session, url: str, *, headers: dict, payload: dict, operation: str, _deps: PostJsonDependencies) -> dict:
    json = _deps.json
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _mark_auth_submission = _deps._mark_auth_submission
    _request_diagnostics = _deps._request_diagnostics
    _request_error = _deps._request_error
    _response_status = _deps._response_status
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


@dataclass(frozen=True)
class PasswordVerifyDependencies:
    """Capabilities resolved by the domain at this invocation."""
    ProtocolV2AuthError: Any
    _PASSWORD_PATH: Any
    _post_json: Any
    _request_diagnostics: Any
    _response_status: Any
    build_sentinel_header: Any
    request_sentinel_token: Any


def _password_verify(session, password: str, *, _deps: PasswordVerifyDependencies) -> dict:
    """Verify one saved OpenAI password, at most once per refresh run."""
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _PASSWORD_PATH = _deps._PASSWORD_PATH
    _post_json = _deps._post_json
    _request_diagnostics = _deps._request_diagnostics
    _response_status = _deps._response_status
    build_sentinel_header = _deps.build_sentinel_header
    request_sentinel_token = _deps.request_sentinel_token
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


@dataclass(frozen=True)
class MfaIssueChallengeDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _MFA_PATH: Any
    _post_json: Any


def _mfa_issue_challenge(session, factor_id: str, *, _deps: MfaIssueChallengeDependencies) -> dict:
    _MFA_PATH = _deps._MFA_PATH
    _post_json = _deps._post_json
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


@dataclass(frozen=True)
class MfaVerifyDependencies:
    """Capabilities resolved by the domain at this invocation."""
    ProtocolV2AuthError: Any
    _MFA_PATH: Any
    _post_json: Any


def _mfa_verify(session, factor_id: str, code: str, *, _deps: MfaVerifyDependencies) -> dict:
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _MFA_PATH = _deps._MFA_PATH
    _post_json = _deps._post_json
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


@dataclass(frozen=True)
class TotpCodeDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    ProtocolV2AuthError: Any
    pyotp: Any


def _totp_code(secret: str, *, _deps: TotpCodeDependencies) -> str:
    time = _deps.time
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    pyotp = _deps.pyotp
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


@dataclass(frozen=True)
class CompleteMfaDependencies:
    """Capabilities resolved by the domain at this invocation."""
    ProtocolV2AuthError: Any
    _MFA_PATH: Any
    _extract_continue_url: Any
    _extract_factor_id: Any
    _follow_and_fetch: Any
    _mfa_issue_challenge: Any
    _mfa_verify: Any
    _record_completed: Any
    _totp_code: Any


def _complete_mfa(session, result: dict, continue_url: str, secret: str, *, _deps: CompleteMfaDependencies) -> tuple[dict, str]:
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _MFA_PATH = _deps._MFA_PATH
    _extract_continue_url = _deps._extract_continue_url
    _extract_factor_id = _deps._extract_factor_id
    _follow_and_fetch = _deps._follow_and_fetch
    _mfa_issue_challenge = _deps._mfa_issue_challenge
    _mfa_verify = _deps._mfa_verify
    _record_completed = _deps._record_completed
    _totp_code = _deps._totp_code
    factor_id = _extract_factor_id(result, continue_url)
    if not factor_id:
        raise ProtocolV2AuthError("mfa_factor_missing", category="response", roxy_fallback_allowed=False)
    _mfa_issue_challenge(session, factor_id)
    mfa_result = _mfa_verify(session, factor_id, _totp_code(secret))
    _record_completed(session, "totp")
    mfa_continue_url = _extract_continue_url(mfa_result) or continue_url
    session_info = _follow_and_fetch(
        session,
        mfa_continue_url,
        referer=f"{_MFA_PATH}/{factor_id}",
    )
    return session_info, "password_mfa_totp"


@dataclass(frozen=True)
class CompleteEmailOtpDependencies:
    """Capabilities resolved by the domain at this invocation."""
    AccountUnusableError: Any
    ProtocolV2AuthError: Any
    _EMAIL_PATH: Any
    _extract_continue_url: Any
    _follow_and_fetch: Any
    _is_mfa: Any
    _record_completed: Any
    _validate_with_retry: Any
    logger: Any
    otp_failure_diagnostics: Any


def _complete_email_otp(session, email: str, after_ts: float, *, auth_method: str, _deps: CompleteEmailOtpDependencies) -> tuple[dict, str]:
    AccountUnusableError = _deps.AccountUnusableError
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _EMAIL_PATH = _deps._EMAIL_PATH
    _extract_continue_url = _deps._extract_continue_url
    _follow_and_fetch = _deps._follow_and_fetch
    _is_mfa = _deps._is_mfa
    _record_completed = _deps._record_completed
    _validate_with_retry = _deps._validate_with_retry
    logger = _deps.logger
    otp_failure_diagnostics = _deps.otp_failure_diagnostics
    try:
        result = _validate_with_retry(session, email, after_ts)
        _record_completed(session, "email_otp")
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
        error.diagnostics = otp_failure_diagnostics(exc)
        logger.warning(
            "[查活][Protocol v2] 邮箱验证码阶段失败：operation=%s failure_kind=%s mailbox_error_code=%s exception_type=%s",
            error.diagnostics["operation"], error.diagnostics["failure_kind"],
            error.diagnostics.get("mailbox_error_code", "-"), error.diagnostics["exception_type"],
        )
        raise error from exc


@dataclass(frozen=True)
class StartEmailSessionDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    ProtocolV2AuthError: Any
    _network_preflight_with_retry: Any
    detect_account_unusable_text: Any
    follow_authorize: Any


def _start_email_session(email: str, proxy: str | None, *, identity=None, context_recorder=None, session_adapter=None, _deps: StartEmailSessionDependencies):
    """Start one fresh auth session for a controlled email fallback."""
    time = _deps.time
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _network_preflight_with_retry = _deps._network_preflight_with_retry
    detect_account_unusable_text = _deps.detect_account_unusable_text
    follow_authorize = _deps.follow_authorize
    session = None
    try:
        session, authorize_url = _network_preflight_with_retry(
            email,
            proxy,
            max_attempts=1,
            identity=identity,
            context_recorder=context_recorder,
        )
        if callable(session_adapter):
            session = session_adapter(session)
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
    except BaseException:
        if context_recorder is not None and session is not None:
            context_recorder.finish_session(session, status="failed", result_code="email_session_start_failed")
        try:
            if session is not None:
                session.session.close()
        except Exception:
            pass
        raise


@dataclass(frozen=True)
class OpenOfferedPasswordLoginDependencies:
    """Capabilities resolved by the domain at this invocation."""
    HTMLParser: Any
    urljoin: Any
    urlparse: Any
    ProtocolV2AuthError: Any
    _EMAIL_PATH: Any
    _PASSWORD_PATH: Any
    _request_diagnostics: Any
    _response_status: Any
    logger: Any


def _open_offered_password_login(
    session,
    final_url: str,
    *,
    allow_standard_route: bool = True,
    require_standard_route: bool = True,
    _deps: OpenOfferedPasswordLoginDependencies,
) -> str:
    """检查密码入口；可按账号状态决定标准路由未提供时是否继续邮箱验证。"""
    HTMLParser = _deps.HTMLParser
    urljoin = _deps.urljoin
    urlparse = _deps.urlparse
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _EMAIL_PATH = _deps._EMAIL_PATH
    _PASSWORD_PATH = _deps._PASSWORD_PATH
    _request_diagnostics = _deps._request_diagnostics
    _response_status = _deps._response_status
    logger = _deps.logger
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
            try:
                response.raise_for_status()
            except Exception as exc:
                if getattr(exc, "response", None) is None:
                    exc.response = response
                raise
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
    logger.info("[查活][Protocol v2] 检查邮箱验证页上的密码登录入口")
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
    if not parser.target and not allow_standard_route:
        logger.info("[查活][Protocol v2] 页面未提供密码登录入口，继续邮箱验证码")
        return current_url
    if parser.target:
        logger.info("[查活][Protocol v2] 发现密码登录入口，优先验证保存的密码")
    # 标准密码页是既有登录路由；只做导航，并以服务端真实落点决定能否提交密码。
    try:
        response = navigate(parser.target or _PASSWORD_PATH, current_url)
    except ProtocolV2AuthError as exc:
        status = (getattr(exc, "diagnostics", {}) or {}).get("http_status")
        if not require_standard_route and int(status or 0) == 404:
            logger.info("[查活][Protocol v2] 标准密码路由返回 404，继续邮箱验证码")
            return current_url
        raise
    password_url = str(getattr(response, "url", "") or "")
    if not trusted_path(password_url, "/log-in/password"):
        if not require_standard_route and trusted_path(password_url, "/email-verification"):
            logger.info("[查活][Protocol v2] 服务端未提供密码登录页，继续邮箱验证码")
            return password_url
        raise unavailable()
    logger.info("[查活][Protocol v2] 服务端已允许进入密码登录页")
    return password_url


@dataclass(frozen=True)
class RefreshWithPasswordDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    urlparse: Any
    EmailOtpSendError: Any
    ProtocolV2AuthError: Any
    _AT_CALLBACK_CONTEXT: Any
    _PASSWORD_PATH: Any
    _complete_email_otp: Any
    _complete_mfa: Any
    _extract_continue_url: Any
    _extract_factor_id: Any
    _follow_and_fetch: Any
    _is_email_otp: Any
    _is_mfa: Any
    _network_preflight_with_retry: Any
    _now: Any
    _open_offered_password_login: Any
    _password_verify: Any
    _record_completed: Any
    _start_email_session: Any
    _success: Any
    account_email_is_invalid: Any
    check_account_liveness: Any
    detect_account_unusable_text: Any
    follow_authorize: Any
    get_account_login_credentials: Any
    logger: Any
    password_email_fallback_enabled: Any
    send_email_otp: Any


def _refresh_with_password(email: str, proxy: str | None, *, proxy_supplier: Callable[[int], str | None] | None, identity=None, context_recorder=None, on_remote_request_started: Callable[[], None] | None=None, on_authenticated=None, allow_password_email_fallback: bool | None=None, on_network_failure=None, session_adapter=None, _deps: RefreshWithPasswordDependencies) -> dict:
    time = _deps.time
    urlparse = _deps.urlparse
    EmailOtpSendError = _deps.EmailOtpSendError
    ProtocolV2AuthError = _deps.ProtocolV2AuthError
    _AT_CALLBACK_CONTEXT = _deps._AT_CALLBACK_CONTEXT
    _PASSWORD_PATH = _deps._PASSWORD_PATH
    _complete_email_otp = _deps._complete_email_otp
    _complete_mfa = _deps._complete_mfa
    _extract_continue_url = _deps._extract_continue_url
    _extract_factor_id = _deps._extract_factor_id
    _follow_and_fetch = _deps._follow_and_fetch
    _is_email_otp = _deps._is_email_otp
    _is_mfa = _deps._is_mfa
    _network_preflight_with_retry = _deps._network_preflight_with_retry
    _now = _deps._now
    _open_offered_password_login = _deps._open_offered_password_login
    _password_verify = _deps._password_verify
    _record_completed = _deps._record_completed
    _start_email_session = _deps._start_email_session
    _success = _deps._success
    account_email_is_invalid = _deps.account_email_is_invalid
    check_account_liveness = _deps.check_account_liveness
    detect_account_unusable_text = _deps.detect_account_unusable_text
    follow_authorize = _deps.follow_authorize
    get_account_login_credentials = _deps.get_account_login_credentials
    logger = _deps.logger
    password_email_fallback_enabled = _deps.password_email_fallback_enabled
    send_email_otp = _deps.send_email_otp
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
        def complete_email_callback(session, url, *, referer):
            _record_completed(session, "email_otp")
            return _follow_and_fetch(session, url, referer=referer)

        result = check_account_liveness(
            email,
            proxy=proxy,
            clear_log=False,
            proxy_supplier=proxy_supplier,
            on_remote_request_started=on_remote_request_started,
            **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
            **({"on_network_failure": on_network_failure} if callable(on_network_failure) else {}),
            **({"callback_handler": complete_email_callback} if _AT_CALLBACK_CONTEXT.get() is not None else {}),
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
            **({"on_preflight_failure": on_network_failure} if callable(on_network_failure) else {}),
        )
        if callable(session_adapter):
            session = session_adapter(session)
        if callable(on_remote_request_started):
            on_remote_request_started()
        otp_after_ts = time.time()
        final_url = follow_authorize(session, authorize_url)
        dead_code = detect_account_unusable_text(final_url)
        if dead_code:
            raise ProtocolV2AuthError("account_deactivated", category="account", roxy_fallback_allowed=False)

        parsed_final_url = urlparse(str(final_url or ""))
        if (
            parsed_final_url.hostname == "auth.openai.com"
            and parsed_final_url.path.rstrip("/") == "/email-verification"
        ):
            auth_method = "password"
            final_url = _open_offered_password_login(
                session,
                str(final_url),
                # 当前仍是首次认证；启用回调恢复能力不代表已经进入回调恢复阶段。
                allow_standard_route=True,
                require_standard_route=email_invalid,
            )
            parsed_final_url = urlparse(final_url)
        final_host = (parsed_final_url.hostname or "").lower()
        final_path = parsed_final_url.path.lower()
        if final_host == "auth.openai.com" and final_path == "/email-verification":
            auth_method = "email_otp"
            password_auth_status = "skipped"
            from core.network.at_transport_recovery import current_scope

            # AT 的初发和重发由独立 OTP 调度按会话状态确认；共享调用保留原行为。
            if _AT_CALLBACK_CONTEXT.get() is None and current_scope() is None:
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
            else:
                logger.info("[查活][Protocol v2] 已进入邮箱验证码页，交由当前会话的验证码调度确认发码并等待")
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
            _record_completed(session, "password")
        except ProtocolV2AuthError as exc:
            if exc.code != "password_rejected":
                raise
            email_fallback = (password_email_fallback_enabled()
                              if allow_password_email_fallback is None else allow_password_email_fallback)
            if email_invalid or not email_fallback:
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
                **({"session_adapter": session_adapter} if callable(session_adapter) else {}),
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
                        ("curl_error_code", "curl_error_code"),
                        ("mailbox_error_code", "mailbox_error_code"),
                        ("transport_exception_type", "transport_exception_type"),
                        ("redirect_hop", "redirect_hop"),
                        ("retry_attempt", "retry_attempt"),
                        ("target_host", "target_host"),
                        ("target_path", "target_path"),
                        ("auth_error", "auth_error"),
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
