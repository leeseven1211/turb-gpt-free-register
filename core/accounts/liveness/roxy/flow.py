# -*- coding: utf-8 -*-
"""使用 Roxy 指纹浏览器为已注册账号刷新 ChatGPT accessToken。

该流程复用本地保存密码处理页面提供的密码、TOTP 和邮箱 OTP；没有保存密码时
不创建密码，资料页仍交回明确的补全操作。
"""
from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from config import roxybrowser as cfg
from core.auth.email_guard import serialize_email_auth
from core.email.provider import wait_for_otp
from core.email.email_butler.client import EmailButlerClientError
from core.email.forward_imap import ForwardIMAPError, ForwardIMAPNoMailTimeout
from core.accounts.credentials import account_email_is_invalid
from core.auth.protocol.openai_auth import AccountUnusableError, EmailOtpSendError, detect_account_unusable_text
from core.auth.challenge import AuthCancelledError
from core.auth.browser.password_auth import PASSWORD_PREPARE_REASONS
from core.auth.browser.password_evidence import password_evidence, password_receipt_ids
from core.operations.runtime import OperationCancelled, check_cancelled, current_token, record_stage, report_stage
from core.operations.task_gateway import OperationLeaseLost
from core.auth.browser.selenium_auth import build_driver as _build_driver, center_browser_window as _center_browser_window, clear_otp_inputs as _clear_otp_inputs, click_continue as _click_continue, click_resend_email_otp as _click_resend_email_otp, email_otp_page_state as _email_otp_page_state, fetch_chatgpt_session as _fetch_chatgpt_session, find_any as _find_any, has_access_token as _has_access_token, is_email_verification_page as _is_email_verification_page, is_login_password_page as _is_login_password_page, maybe_accept as _maybe_accept, page_warmup as _page_warmup, quit_driver as _quit_driver, safe_get as _safe_get, submit_email_step as _submit_email_step, submit_email_via_browser_nextauth as _submit_email_via_browser_nextauth, type_email_address as _type_email_address, type_otp as _type_otp, wait_after_email_otp_submit as _wait_after_email_otp_submit, wait_email_submit_next_state as _wait_email_submit_next_state
from core.browser.roxy.client import RoxyBrowserClient
from core.accounts.liveness.roxy.refresh_errors import ROXY_LOGIN_CAUSES, roxy_login_failure_code
from core.network.at_transport_recovery import AtRecoveryTimeout

logger = logging.getLogger('core.roxy_liveness')


@contextmanager
def _timed_refresh_step(step: str):
    started_at = time.monotonic()
    try:
        yield
    finally:
        logger.info("[查活][Roxy] %s耗时 %.0f ms", step, (time.monotonic() - started_at) * 1000)


_ROXY_STAGE_CAUSES = {
    "open": ("roxy_profile_open_failed", "browser"),
    "driver": ("roxy_driver_attach_failed", "browser"),
    "navigation": ("roxy_navigation_failed", "network"),
    "login": ("roxy_login_failed", "auth"),
    "email_otp": ("email_otp_failed", "email"),
    "session": ("roxy_session_fetch_failed", "response"),
    "callback": ("roxy_authenticated_callback_failed", "runtime"),
}


_PROXY_BROWSER_ERRORS = ("ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY_CONNECTION_FAILED")
_AT_BROWSER_NETWORK_KINDS = {
    "ERR_TUNNEL_CONNECTION_FAILED": "proxy",
    "ERR_PROXY_CONNECTION_FAILED": "proxy",
    "ERR_CONNECTION_RESET": "connection",
    "ERR_CONNECTION_CLOSED": "connection",
    "ERR_CONNECTION_REFUSED": "connection",
    "ERR_HTTP2_PING_FAILED": "connection",
    "ERR_NAME_NOT_RESOLVED": "dns",
    "ERR_TIMED_OUT": "timeout",
    "ERR_CONNECTION_TIMED_OUT": "timeout",
    "ERR_SSL_PROTOCOL_ERROR": "tls",
    "ERR_CERT_AUTHORITY_INVALID": "tls",
    "ERR_CERT_DATE_INVALID": "tls",
    "Failed to fetch": "connection",
}


def _at_browser_network_error(driver) -> str:
    """只从当前浏览器错误文档读取固定传输码，不采用普通页面中的提示文字。"""
    if driver is None:
        return ""
    try:
        page = driver.execute_script(
            "return {url: location.href, text: document.body ? document.body.innerText : ''};",
        )
        if not isinstance(page, dict) or not str(page.get("url") or "").startswith("chrome-error://"):
            return ""
        text = str(page.get("text") or "")
        return next((code for code in _AT_BROWSER_NETWORK_KINDS if code.startswith("ERR_")
                     and re.search(r"\b" + re.escape(code) + r"\b", text)), "")
    except Exception:
        return ""


def _at_network_diagnostics(exc: Exception, stage: str, driver=None) -> dict:
    """AT 作用域内的网络证据供外层恢复使用，不改变表单提交或业务错误码。"""
    from core.network.at_transport_recovery import current_scope, network_failure

    if current_scope() is None or stage not in {"navigation", "login", "email_otp", "session"}:
        return {}
    if str(getattr(exc, "code", "") or "") in {
        "password_rejected", "password_change_required", "password_page_error", "password_missing",
        "mfa_rejected", "mfa_secret_missing", "mfa_secret_invalid", "email_verification_required",
        "account_deactivated", "profile_completion_required",
    }:
        return {}
    # 取码服务走独立连接，收件服务网络异常不能误判为浏览器代理故障。
    chain, item = [], exc
    while isinstance(item, BaseException) and len(chain) < 8 and not any(item is old for old in chain):
        chain.append(item)
        item = item.__cause__ or (None if item.__suppress_context__ else item.__context__)
    if any(type(item).__module__.startswith("core.email") for item in chain):
        return {}
    network_error = str(getattr(exc, "network_error", "") or "")
    if network_error not in _AT_BROWSER_NETWORK_KINDS:
        network_error = ""
    # Chrome 的导航异常和 MFA 辅助函数均使用明确的 net::ERR_* 标记。
    if not network_error:
        for item in chain:
            marker = re.search(r"\bnet::(ERR_[A-Z0-9_]+)\b", str(item))
            if marker and marker.group(1) in _AT_BROWSER_NETWORK_KINDS:
                network_error = marker.group(1)
                break
    if not network_error:
        network_error = _at_browser_network_error(driver)
    if network_error:
        return {"failure_kind": "transport_error", "network_error": network_error,
                "transport_kind": _AT_BROWSER_NETWORK_KINDS[network_error], "response_observed": False}
    from core.auth.state_machine import StageTimeout

    if any(isinstance(item, StageTimeout) for item in chain):
        return {}
    response = getattr(exc, "response", None)
    request = getattr(exc, "request", None)
    target = getattr(response, "url", None) or getattr(request, "url", None)
    if isinstance(target, str) and target:
        try:
            parsed = urlparse(target)
        except ValueError:
            return {}
        if parsed.scheme != "https" or parsed.hostname not in {"auth.openai.com", "chatgpt.com", "chat.openai.com", "sentinel.openai.com"}:
            return {}
    failure = network_failure(error=exc)
    if not failure:
        return {}
    return {key: value for key, value in failure.items()
            if key in {"failure_kind", "transport_kind", "http_status", "curl_error_code", "response_observed",
                       "exception_type", "transport_exception_type"}}


def _browser_proxy_error(driver, *, snapshot: dict | None = None) -> str:
    """以实际文档确认浏览器错误页，只返回固定网络码。"""
    def error_code(page) -> str:
        if not isinstance(page, dict) or not str(page.get("url") or "").startswith("chrome-error://"):
            return ""
        text = str(page.get("text") or "")
        return next((code for code in _PROXY_BROWSER_ERRORS if code in text), "")

    if snapshot is not None:
        return error_code(snapshot)
    if driver is None:
        return ""
    try:
        if str(driver.current_url or "").startswith("chrome-error://"):
            return error_code({"url": driver.current_url, "text": driver.execute_script(
                "return document.body ? document.body.innerText : '';",
            )})
        # ChromeDriver 可能继续返回导航前尝试的 HTTPS 地址；文档地址才说明
        # 当前是否是浏览器错误页，普通认证页正文出现 ERR_* 不能据此分类。
        page = driver.execute_script(
            "return {url: location.href, text: document.body ? document.body.innerText : ''};",
        )
        return error_code(page)
    except Exception:
        return ""


def _refresh_failure_cause(exc: Exception, stage: str, browser_error: str = "") -> tuple[str, str]:
    """先保留认证异常的明确原因，再按实际失败阶段分类并保留异常原文。"""
    code = str(getattr(exc, "code", "") or "")
    if code in {"password_rejected", "password_result_unknown", "password_change_required", "password_page_error",
                "mfa_secret_missing", "mfa_rejected", "email_submit_unconfirmed",
                "auth_operation_timeout", "auth_context_missing", "password_entry_navigation_failed",
                "profile_completion_required", "identity_mismatch"}:
        return code, "auth"
    if browser_error or any(marker in str(exc) for marker in _PROXY_BROWSER_ERRORS):
        return "roxy_proxy_tunnel_failed", "network"
    text = str(exc).lower()
    if type(exc).__name__ == "_EmailSubmissionUnknown":
        return "email_submit_unconfirmed", "auth"
    if type(exc).__name__ == "ForwardIMAPNoMailTimeout" or "等待新的邮箱验证码超时" in text:
        return "email_otp_no_mail", "email"
    if "totp" in text and any(marker in text for marker in ("未通过", "不正确", "invalid")):
        return "mfa_rejected", "auth"
    if "totp" in text and any(marker in text for marker in ("缺少", "没有", "missing")):
        return "mfa_secret_missing", "configuration"
    if stage == "login":
        login_cause = roxy_login_failure_code(exc)
        if login_cause:
            return login_cause, ROXY_LOGIN_CAUSES[login_cause][2]
    return _ROXY_STAGE_CAUSES[stage]


class _EmailInvalidLoginError(RuntimeError):
    """失效邮箱登录的已知失败，只携带固定原因和明确的提交事实。"""

    def __init__(self, code: str, *, not_submitted: bool = False):
        self.code = code
        self.not_submitted = bool(not_submitted)
        message = {
            "password_missing": "邮箱已失效，且未保存 OpenAI 登录密码",
            "password_login_unavailable": "邮箱已失效，服务端未提供可用的密码登录流程",
            "email_verification_required": "邮箱已失效，密码登录后仍需邮箱验证",
        }[code]
        super().__init__(f"{code}: {message}")


class _RoxyOtpSubmissionUnknown(RuntimeError):
    """邮箱验证码的本次提交尚未确认，保留现场供同一账号手动重跑。"""

    code = "email_submit_unconfirmed"


class _AtOtpPageChanged(RuntimeError):
    """仅将 AT 等码期间的新页面交回当前浏览器认证流程。"""

    def __init__(self, state: str):
        self.state = state
        super().__init__("等待验证码时页面已进入其他认证阶段")


def _is_at_totp_login_page(snapshot) -> bool:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _is_at_totp_login_page as execute, IsAtTotpLoginPageDependencies
    def _is_totp_login_page(*args, **kwargs):
        from core.codex.roxy.oauth import _is_totp_login_page as classify
        return classify(*args, **kwargs)
    dependencies = IsAtTotpLoginPageDependencies(
        urlparse=urlparse,
        _is_totp_login_page=_is_totp_login_page,
    )
    return execute(snapshot, _deps=dependencies)


def _classify_at_login_page(snapshot):
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _classify_at_login_page as execute, ClassifyAtLoginPageDependencies
    dependencies = ClassifyAtLoginPageDependencies(
        _is_at_totp_login_page=_is_at_totp_login_page,
    )
    return execute(snapshot, _deps=dependencies)


def _at_unknown_page_detail(exc, cause_code, driver, *, browser_error="", network_diagnostics=None) -> str:
    """只解释既有 AT 失败的末态，不参与登录、重试或提交结果判断。"""
    if driver is None or browser_error or network_diagnostics:
        return ""
    if cause_code not in {"roxy_login_failed", "email_otp_failed", "email_submit_unconfirmed"}:
        return ""
    if not (type(exc) is RuntimeError or isinstance(exc, _RoxyOtpSubmissionUnknown)):
        return ""
    text = str(exc)
    if cause_code == "email_submit_unconfirmed":
        if not (isinstance(exc, _RoxyOtpSubmissionUnknown) and re.search(r"\bstate=stuck(?:$|[\s,，])", text)):
            return ""
    elif not any(marker in text for marker in (
        "浏览器登录未进入已有账号 OTP，最后状态=", "已有账号登录挑战未完成：state=",
        "已有账号 TOTP 登录挑战未完成：state=", "邮箱提交后未识别到密码、TOTP 或邮箱验证码分支：",
    )):
        return ""
    from core.auth.page_errors import AuthPageError
    from core.auth.state_machine import PageState, StageTimeout
    from core.network.at_transport_recovery import current_scope, network_failure

    scope = current_scope()
    if scope is not None and scope.pending_network_failure:
        return ""

    chain, item = [], exc
    while isinstance(item, BaseException) and len(chain) < 8 and not any(item is previous for previous in chain):
        chain.append(item)
        item = item.__cause__ or (None if item.__suppress_context__ else item.__context__)
    if any(isinstance(item, (AuthPageError, StageTimeout, OperationCancelled, AuthCancelledError,
                             OperationLeaseLost, AtRecoveryTimeout))
           or type(item).__module__.startswith("core.email") for item in chain):
        return ""
    if (any(str(getattr(item, "code", "") or getattr(item, "error_code", "") or "")
            not in {"", "email_submit_unconfirmed"} for item in chain)
            or network_failure(error=exc) is not None or "net::ERR_" in text
            or any(marker in text.casefold() for marker in (
                "session_expired", "提交本地 totp 后", "本地 totp 未通过", "authenticator 验证页缺少",
                "totp 登录链未完成", "本地保存的注册密码未通过", "邮箱验证码连续错误", "otp_request_unconfirmed",
            ))):
        return ""
    try:
        snapshot = _email_otp_page_state(driver)
        if (not isinstance(snapshot, dict) or snapshot.get("error") or snapshot.get("errors")
                or snapshot.get("authErrorPage") or snapshot.get("challengePresent")):
            return ""
        location = urlparse(str(snapshot.get("url") or ""))
        if location.scheme == "chrome-error":
            return ""
        initialization = snapshot.get("initialization")
        if isinstance(initialization, dict) and (
            initialization.get("pending") or initialization.get("recent_activity")
            or initialization.get("ready", "complete") != "complete"
        ):
            return ""
        inputs = [item for item in snapshot.get("inputs") or [] if isinstance(item, dict)
                  and item.get("visible") is not False and item.get("otpFieldVisible") is not False
                  and str(item.get("type") or "").lower() != "hidden"]
        if any(str(item.get("ariaInvalid") or "").lower() == "true" for item in inputs):
            return ""
        controls = [*inputs, *(item for item in snapshot.get("buttons") or [] if isinstance(item, dict)
                              and item.get("visible") is not False and str(item.get("tag") or "").upper() != "A")]
        if not any(not item.get("otpFieldDisabled", item.get("disabled"))
                   and not item.get("otpFieldReadOnly", item.get("readOnly")) for item in controls):
            return ""
        page = _classify_at_login_page(snapshot)
        trusted = (location.scheme == "https" and location.hostname in {"auth.openai.com", "chatgpt.com", "chat.openai.com"}
                   and location.port in (None, 443) and not location.username and not location.password)
        mfa_route = trusted and location.hostname == "auth.openai.com" and location.path.startswith("/mfa-challenge/")
        unsupported_mfa = (mfa_route and page in {PageState.OTP_EMAIL, PageState.MFA_TOTP, PageState.AUTH_TRANSIENT}
                           and not _is_at_totp_login_page(snapshot))
        if page != PageState.UNKNOWN and not unsupported_mfa:
            return ""
        route = "/<external>"
        if mfa_route:
            route = "/mfa-challenge/<factor>"
        elif trusted:
            route = location.path if location.path in {
                "/", "/auth/login", "/login", "/log-in", "/log-in/password", "/email-verification",
                "/auth/error", "/error", "/add-phone", "/phone-verification", "/workspace", "/consent",
            } else "/<auth-path>"
        return f"无法识别认证页面；页面状态={page.value}；路由={route}"
    except (OperationCancelled, AuthCancelledError, OperationLeaseLost, AtRecoveryTimeout):
        raise
    except Exception:
        # 失败后的诊断读取不能取代触发收口的原始异常。
        return ""


def _check_profile_handoff(driver) -> None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _check_profile_handoff as execute, CheckProfileHandoffDependencies
    dependencies = CheckProfileHandoffDependencies(
        urlparse=urlparse,
    )
    return execute(driver, _deps=dependencies)


def available() -> bool:
    return (
        bool(str(getattr(cfg, "ROXY_API_BASE", "") or "").strip())
        and bool(str(getattr(cfg, "ROXY_API_TOKEN", "") or "").strip())
        and bool(str(getattr(cfg, "ROXY_WORKSPACE_ID", "") or "").strip())
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _page_account_unusable_code(driver) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _page_account_unusable_code as execute, PageAccountUnusableCodeDependencies
    dependencies = PageAccountUnusableCodeDependencies(
        detect_account_unusable_text=detect_account_unusable_text,
    )
    return execute(driver, _deps=dependencies)


def _open_standard_password_login(driver) -> bool:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _open_standard_password_login as execute, OpenStandardPasswordLoginDependencies
    dependencies = OpenStandardPasswordLoginDependencies(
        urlparse=urlparse,
        _find_any=_find_any,
        _safe_get=_safe_get,
    )
    return execute(driver, _deps=dependencies)


def _enter_existing_account_otp(
    driver,
    email: str,
    *,
    password: str = "",
    totp_secret: str = "",
) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _enter_existing_account_otp as execute, EnterExistingAccountOtpDependencies
    def complete_openai_login_challenge(*args, **kwargs):
        from core.codex.roxy.oauth import complete_openai_login_challenge as complete
        return complete(*args, **kwargs)
    dependencies = EnterExistingAccountOtpDependencies(
        AccountUnusableError=AccountUnusableError,
        AuthCancelledError=AuthCancelledError,
        OperationCancelled=OperationCancelled,
        OperationLeaseLost=OperationLeaseLost,
        _EmailInvalidLoginError=_EmailInvalidLoginError,
        _browser_proxy_error=_browser_proxy_error,
        _check_profile_handoff=_check_profile_handoff,
        _classify_at_login_page=_classify_at_login_page,
        _email_otp_page_state=_email_otp_page_state,
        _has_access_token=_has_access_token,
        _is_at_totp_login_page=_is_at_totp_login_page,
        _is_email_verification_page=_is_email_verification_page,
        _is_login_password_page=_is_login_password_page,
        _open_standard_password_login=_open_standard_password_login,
        _page_account_unusable_code=_page_account_unusable_code,
        _submit_email_step=_submit_email_step,
        _submit_email_via_browser_nextauth=_submit_email_via_browser_nextauth,
        _type_email_address=_type_email_address,
        _wait_email_submit_next_state=_wait_email_submit_next_state,
        account_email_is_invalid=account_email_is_invalid,
        complete_openai_login_challenge=complete_openai_login_challenge,
        logger=logger,
    )
    return execute(driver, email, password=password, totp_secret=totp_secret, _deps=dependencies)


def _complete_otp(
    driver,
    email: str,
    after_ts: float,
    *,
    password: str = "",
    totp_secret: str = "",
    on_email_confirmed=None,
) -> None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _complete_otp as execute, CompleteOtpDependencies
    def complete_openai_login_challenge(*args, **kwargs):
        from core.codex.roxy.oauth import complete_openai_login_challenge as complete
        return complete(*args, **kwargs)

    def butler_transport_error_codes():
        from core.accounts.liveness.protocol.otp_diagnostics import BUTLER_TRANSPORT_ERROR_CODES
        return BUTLER_TRANSPORT_ERROR_CODES

    def load_email_otp_wait_setting():
        from config import email as email_config
        return lambda: email_config.OTP_MAX_WAIT

    dependencies = CompleteOtpDependencies(
        re=re,
        time=time,
        urlparse=urlparse,
        AtRecoveryTimeout=AtRecoveryTimeout,
        AuthCancelledError=AuthCancelledError,
        EmailButlerClientError=EmailButlerClientError,
        EmailOtpSendError=EmailOtpSendError,
        ForwardIMAPNoMailTimeout=ForwardIMAPNoMailTimeout,
        OperationCancelled=OperationCancelled,
        OperationLeaseLost=OperationLeaseLost,
        _AtOtpPageChanged=_AtOtpPageChanged,
        _RoxyOtpSubmissionUnknown=_RoxyOtpSubmissionUnknown,
        _browser_proxy_error=_browser_proxy_error,
        _check_profile_handoff=_check_profile_handoff,
        _classify_at_login_page=_classify_at_login_page,
        _clear_otp_inputs=_clear_otp_inputs,
        _click_continue=_click_continue,
        _click_resend_email_otp=_click_resend_email_otp,
        _email_otp_page_state=_email_otp_page_state,
        _has_access_token=_has_access_token,
        _login_existing_account_with_recovery=_login_existing_account_with_recovery,
        _type_otp=_type_otp,
        _wait_after_email_otp_submit=_wait_after_email_otp_submit,
        butler_transport_error_codes=butler_transport_error_codes,
        check_cancelled=check_cancelled,
        complete_openai_login_challenge=complete_openai_login_challenge,
        load_email_otp_wait_setting=load_email_otp_wait_setting,
        logger=logger,
        wait_for_otp=wait_for_otp,
    )
    return execute(driver, email, after_ts, password=password, totp_secret=totp_secret, on_email_confirmed=on_email_confirmed, _deps=dependencies)


def _authenticated_browser_session(driver, proxy: str | None):
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _authenticated_browser_session as execute, AuthenticatedBrowserSessionDependencies
    dependencies = AuthenticatedBrowserSessionDependencies(
    )
    return execute(driver, proxy, _deps=dependencies)


def _with_refresh_execution_context(function):
    """把原生取消及 AT 恢复总时限传给共享 Selenium 等待检查点。"""
    @wraps(function)
    def wrapped(*args, **kwargs):
        from core.operations.runtime import current_token
        from core.auth.browser.auth_context import AuthExecutionContext, execution_context
        from core.network.at_transport_recovery import current_scope

        token = current_token()
        scope = current_scope()
        if token is None and scope is None:
            return function(*args, **kwargs)

        def requested() -> bool:
            if scope is not None:
                scope.check()
            return bool(token is not None and token.requested())

        with execution_context(AuthExecutionContext(
            cancellation=requested,
            cancellation_error=lambda: OperationCancelled("用户手动停止刷新 AT"),
            deadline=scope.deadline if scope is not None else None,
        )):
            return function(*args, **kwargs)
    return wrapped


def _login_existing_account_with_recovery(
    driver, email: str, *, password: str = "", totp_secret: str = "",
    timeout: float = 120, on_restart=None,
) -> str:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.browser.roxy.refresh_at import _login_existing_account_with_recovery as execute, LoginExistingAccountWithRecoveryDependencies
    dependencies = LoginExistingAccountWithRecoveryDependencies(
        time=time,
        _enter_existing_account_otp=_enter_existing_account_otp,
        _page_warmup=_page_warmup,
        logger=logger,
    )
    return execute(driver, email, password=password, totp_secret=totp_secret, timeout=timeout, on_restart=on_restart, _deps=dependencies)


@serialize_email_auth
@_with_refresh_execution_context
def refresh_access_token(
    email: str,
    *,
    proxy: str | None = None,
    context_recorder=None,
    on_remote_request_started=None,
    on_authenticated=None,
) -> dict:
    """复用账号绑定的 Roxy Profile 登录并返回刷新后的 Session/AT。"""
    checked_at = _now()
    if not available():
        return {"ok": False, "status": "failed", "checked_at": checked_at,
                "error": "Roxy 浏览器连接未配置", "error_code": "roxy_not_configured",
                "error_category": "configuration", "remote_request_started": False,
                "mutation_submitted": False, "action_dispatched": False,
                "live_check_driver": "browser_roxy", "auth_method": "roxy_browser"}
    from core.registration import debug as registration_debug

    debug_session = registration_debug.current_session()
    full_debug = bool(debug_session is not None and debug_session.capture_mode == "full")
    client = None
    opened = None
    driver = None
    data_saver = None
    asset_cache = None
    refresh_result = None
    callback_session = None
    cancelled = False
    budget_exhausted = False
    remote_started = False
    failure_stage = "open"
    initial_password_ids = frozenset()
    email_challenge_started = False
    email_challenge_completed = False
    session_acquired = False
    network_recovery_failed = False

    def email_confirmed() -> None:
        nonlocal email_challenge_completed
        email_challenge_completed = True

    def stage(value: str) -> None:
        nonlocal failure_stage
        failure_stage = value
        from core.network.at_transport_recovery import current_scope

        scope = current_scope()
        if scope is not None:
            if value == "callback" and session_acquired:
                # AT 已取得后仍检查取消和租约，认证总时限不再覆盖成功事实。
                if callable(scope.checkpoint):
                    scope.checkpoint()
            else:
                scope.check()
        if callable(getattr(debug_session, "update_stage", None)):
            debug_session.update_stage({"open": "browser", "driver": "browser", "navigation": "browser",
                                        "login": "login", "session": "token", "callback": "token"}.get(value, value))
        if current_token() is not None:
            completed = {
                "navigation": ("browser", "Roxy 浏览器已启动并连接"),
                "login": ("page", "ChatGPT 登录页已打开"),
                "email_otp": ("login", "已确认邮箱提交后的验证页面"),
            }.get(value)
            if value == "session" and not email_challenge_started:
                completed = ("login", "已确认浏览器进入登录状态")
            if completed:
                completed_stage, message = completed
                record_stage(completed_stage, message, state="success", detail={"child_step_id": completed_stage})
            visible_stage, message = {
                "driver": ("browser", "正在连接 Roxy 浏览器"),
                "navigation": ("page", "正在加载 ChatGPT 登录页"),
                "login": ("login", "正在提交登录邮箱并识别后续认证页面"),
                "email_otp": ("email_otp", "服务端仍要求邮箱验证，正在查收邮箱验证码"),
                "session": ("refresh_token", "登录验证已完成，正在读取会话和 AT"),
                "callback": ("token", "正在处理已取得的登录会话"),
            }[value]
            detail = {"child_step_id": visible_stage} if visible_stage in {"browser", "page"} else None
            report_stage(visible_stage, message, detail=detail)

    try:
        check_cancelled("用户手动停止刷新 AT")
        client = RoxyBrowserClient()
        from core.browser.roxy.profile_binding import account_profile_id_by_email, persist_account_profile_id

        bound_profile_id = account_profile_id_by_email(email, strict=True)
        logger.info("[查活][Roxy] 打开或创建账号指纹浏览器环境")
        with _timed_refresh_step("启动 Roxy 环境"):
            opened = client.open_profile_for_account(
                profile_id=bound_profile_id or None,
                proxy_url=proxy,
                data_saver_flow="token_refresh",
                stop_checker=lambda: check_cancelled("用户手动停止刷新 AT"),
                **({"headless": False} if full_debug else {}),
            )
        profile_reused = bool(
            bound_profile_id
            and str(opened.profile_id) == str(bound_profile_id)
            and bool(getattr(opened, "account_bound", False))
        )
        if not bound_profile_id or str(opened.profile_id) != str(bound_profile_id):
            if not persist_account_profile_id(email, opened.profile_id):
                raise RuntimeError("账号 Roxy Profile 绑定写回失败")
            opened.account_bound = True
            client.mark_profile_bound(opened.profile_id)
        if context_recorder is not None:
            context_recorder.open_roxy_profile(
                opened,
                route_attempt_no=1,
                proxy_url=(None if profile_reused else proxy),
                proxy_context=None,
            )
        else:
            try:
                from core.browser import traffic as browser_traffic

                browser_traffic.bind_roxy_capture(opened, purpose="token_refresh")
            except Exception:
                logger.exception("[浏览器流量] 关联刷新 AT 上下文失败；刷新继续")
        effective_proxy = None if profile_reused else proxy
        stage("driver")
        with _timed_refresh_step("连接 Selenium"):
            driver = _build_driver(opened)
        initial_password_ids = password_receipt_ids(driver)
        capture = getattr(opened, "traffic_capture", None)
        observe = getattr(capture, "set_submission_observer", None)
        if callable(observe):
            from core.registration.roxy import _make_submission_observer

            observe(_make_submission_observer(driver))
        if debug_session is not None:
            registration_debug.attach_current_roxy(getattr(opened, "debugger_address", None))
        from core.browser import asset_policy as browser_asset_policy

        asset_cache = browser_asset_policy.start_auth_asset_cache(opened, driver, flow="token_refresh")
        try:
            from core.browser import flow_policy as browser_flow_policy

            data_saver = browser_flow_policy.install_for_flow("token_refresh", opened, driver)
        except Exception as exc:
            logger.warning(
                "[浏览器省流量] 刷新 AT 规则安装失败，继续刷新：%s",
                type(exc).__name__,
            )
        _center_browser_window(driver)
        driver.set_page_load_timeout(int(getattr(cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90))
        try:
            driver.set_script_timeout(15)
        except Exception:
            pass
        check_cancelled("用户手动停止刷新 AT")
        stage("navigation")
        with _timed_refresh_step("导航至登录页"):
            _safe_get(
                driver,
                "https://chatgpt.com/auth/login",
                timeout=min(50, int(getattr(cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
                attempts=2,
                accept_hosts=("chatgpt.com", "auth.openai.com"),
            )
        with _timed_refresh_step("准备登录页"):
            _page_warmup(driver, reason="live_check_login")
            _maybe_accept(driver)
        code = _page_account_unusable_code(driver)
        if code:
            refresh_result = {
                "ok": False,
                "status": "deactivated",
                "checked_at": checked_at,
                "error": code,
                "validation_method": "roxy_email_otp",
            }
            return refresh_result
        from core.codex.roxy.oauth import _account_login_credentials

        password, totp_secret = _account_login_credentials(email)
        otp_after_ts = time.time()
        check_cancelled("用户手动停止刷新 AT")
        if callable(on_remote_request_started):
            on_remote_request_started()
        remote_started = True
        stage("login")
        def restart_otp_boundary():
            nonlocal otp_after_ts
            otp_after_ts = time.time()

        with _timed_refresh_step("处理邮箱提交与登录挑战"):
            state = _login_existing_account_with_recovery(
                driver,
                email,
                password=password,
                totp_secret=totp_secret,
                on_restart=restart_otp_boundary,
            )
        if state == "otp":
            email_challenge_started = True
            stage("email_otp")
            _complete_otp(
                driver, email, otp_after_ts, password=password, totp_secret=totp_secret,
                on_email_confirmed=email_confirmed,
            )
        code = _page_account_unusable_code(driver)
        if code:
            refresh_result = {
                "ok": False,
                "status": "deactivated",
                "checked_at": checked_at,
                "error": code,
                "validation_method": "roxy_email_otp",
            }
            return refresh_result
        stage("session")
        session_info = _fetch_chatgpt_session(driver, timeout=120)
        access_token = str(session_info.get("accessToken") or "").strip()
        if not access_token:
            raise RuntimeError("Roxy 登录完成但未拿到 accessToken")
        session_acquired = True
        refresh_result = {
            "ok": True,
            "status": "live",
            "checked_at": checked_at,
            "access_token": access_token,
            "session": session_info,
            "proxy_used": effective_proxy or None,
            "validation_method": "roxy_email_otp",
            "live_check_driver": "browser_roxy",
            "auth_method": "roxy_browser",
            "remote_request_started": remote_started,
        }
        if callable(on_authenticated):
            stage("callback")
            callback_session = _authenticated_browser_session(driver, proxy)
            refresh_result = on_authenticated(refresh_result, callback_session)
        return refresh_result
    except (OperationCancelled, OperationLeaseLost):
        cancelled = True
        raise
    except AtRecoveryTimeout:
        budget_exhausted = True
        raise
    except AuthCancelledError as exc:
        cancelled = True
        raise OperationCancelled(str(exc) or "用户手动停止刷新 AT") from exc
    except AccountUnusableError as exc:
        code = getattr(exc, "error_code", "") or detect_account_unusable_text(str(exc)) or "account_deactivated"
        refresh_result = {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code, "validation_method": "roxy_email_otp"}
        return refresh_result
    except _EmailInvalidLoginError as exc:
        logger.warning("[查活][Roxy] 失效邮箱登录未完成：%s", str(exc))
        refresh_result = {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": str(exc),
            "error_code": exc.code,
            "error_category": {
                "password_missing": "configuration",
                "password_login_unavailable": "auth",
                "email_verification_required": "email",
            }[exc.code],
            "roxy_fallback_allowed": False,
            "validation_method": "roxy_email_otp",
        }
        if exc.not_submitted:
            refresh_result.update({"mutation_submitted": False, "action_dispatched": False})
        else:
            refresh_result.update({"response_observed": True, "remote_response_received": True})
        return refresh_result
    except Exception as exc:
        code = detect_account_unusable_text(str(exc))
        if code:
            refresh_result = {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code, "validation_method": "roxy_email_otp"}
            return refresh_result
        from core.auth.state_machine import StageTimeout

        browser_error = _browser_proxy_error(driver)
        cause_code, category = _refresh_failure_cause(exc, failure_stage, browser_error)
        prepare_reason = getattr(driver, "_password_prepare_reason", "")
        receipt = getattr(driver, "_browser_submission_receipt", None)
        if (not browser_error and failure_stage == "login"
                and isinstance(prepare_reason, str) and prepare_reason in PASSWORD_PREPARE_REASONS
                and getattr(receipt, "stage", "") == "login_password"
                and getattr(receipt, "phase", "") in {"prepared", "not_dispatched"}
                and (isinstance(exc, StageTimeout) or "password_form_not_ready:" in str(exc))):
            cause_code, category = "roxy_password_prepare_timeout", "browser"
            error_detail = f"密码表单准备超时，最后等待原因={prepare_reason}"
        else:
            error_detail = str(exc)[:500]
        failure_kind = ("no_mail" if isinstance(exc, ForwardIMAPNoMailTimeout)
                        else "imap_error" if isinstance(exc, ForwardIMAPError)
                        else "runtime_exception")
        auth_diagnostics = {"operation": f"roxy_{failure_stage}", "failure_kind": failure_kind,
                            "exception_type": type(exc).__name__}
        if failure_stage == "email_otp" and isinstance(exc, (EmailButlerClientError, EmailOtpSendError)):
            from core.accounts.liveness.protocol.otp_diagnostics import otp_failure_diagnostics

            # 沿用同次取码异常的真实原因，保留浏览器阶段与收件动作的对应关系。
            operation = "email_otp_send" if isinstance(exc, EmailOtpSendError) else "email_otp"
            auth_diagnostics = {**otp_failure_diagnostics(exc, operation=operation), "operation": "roxy_email_otp",
                                "cause_operation": operation}
        network_diagnostics = _at_network_diagnostics(exc, failure_stage, driver) if not session_acquired else {}
        network_recovery_failed = bool(network_diagnostics)
        try:
            page_detail = _at_unknown_page_detail(
                exc, cause_code, driver, browser_error=browser_error, network_diagnostics=network_diagnostics,
            )
        except (OperationCancelled, OperationLeaseLost):
            cancelled = True
            raise
        except AtRecoveryTimeout:
            budget_exhausted = True
            raise
        except AuthCancelledError as diagnostic_error:
            cancelled = True
            raise OperationCancelled(str(diagnostic_error) or "用户手动停止刷新 AT") from diagnostic_error
        if page_detail:
            cause_code, category = "auth_page_unknown", "auth"
            error_detail = f"{page_detail}；原始错误：{error_detail}"
        logger.warning("[查活][Roxy] 失败：%s: %s", type(exc).__name__, error_detail[:260])
        refresh_result = {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": f"Roxy {type(exc).__name__}: {error_detail}" + (f"；浏览器错误：{browser_error}" if browser_error else ""),
            "error_code": cause_code,
            "error_category": category,
            "failure_stage": failure_stage,
            "auth_diagnostics": {**auth_diagnostics, **network_diagnostics},
            "validation_method": "roxy_email_otp",
        }
        if cause_code in {"password_change_required", "password_page_error"} and getattr(exc, "not_submitted", False):
            refresh_result["password_action_dispatched"] = False
        if not remote_started:
            refresh_result.update({"remote_request_started": False, "mutation_submitted": False, "action_dispatched": False})
        return refresh_result
    finally:
        from core.browser import asset_policy as browser_asset_policy, traffic as browser_traffic

        if isinstance(refresh_result, dict):
            evidence = password_evidence(driver, exclude_ids=initial_password_ids)
            refresh_result["password_auth_status"] = evidence["credential_check"]
            refresh_result["password_action_dispatched"] = evidence["submitted"]
            refresh_result["auth_facts"] = {
                **evidence,
                "email_challenge": ("success" if email_challenge_completed else "failed")
                if email_challenge_started else "skipped",
                "session_acquired": session_acquired,
            }
            refresh_result.setdefault("live_check_driver", "browser_roxy")
            refresh_result.setdefault("auth_method", "roxy_browser")
            refresh_result.setdefault("remote_request_started", remote_started)
        failed = bool(refresh_result is not None and not refresh_result.get("ok"))
        if failed and not cancelled:
            try:
                if isinstance(getattr(debug_session, "job", None), dict):
                    debug_session.job["error_code"] = refresh_result.get("error_code") or ""
                registration_debug.capture_current_failure(
                    str(refresh_result.get("error") or "Roxy 登录刷新 AT 未完成"), driver,
                )
            except Exception:
                logger.exception("[查活][Roxy] 保存失败现场时发生异常")
        keep_browser = not cancelled and not budget_exhausted and not network_recovery_failed and (
            bool(getattr(cfg, "ROXY_KEEP_BROWSER_OPEN", False)) or (full_debug and failed)
        )
        if full_debug and failed and driver is not None and keep_browser:
            refresh_result["debug_browser_kept"] = True
        if callback_session is not None:
            callback_session.session.close()
        browser_asset_policy.stop_asset_cache(asset_cache)
        if data_saver is not None:
            try:
                data_saver.stop()
            except Exception:
                logger.exception("[浏览器省流量] 刷新 AT 统计停止失败")
        if context_recorder is not None and opened is not None:
            try:
                succeeded = bool(refresh_result and refresh_result.get("ok"))
                context_recorder.finish_roxy_profile(
                    opened,
                    status="success" if succeeded else "failed",
                    result_code=(
                        "authenticated"
                        if succeeded
                        else str(
                            (refresh_result or {}).get("error_code")
                            or (refresh_result or {}).get("error_category")
                            or (refresh_result or {}).get("status")
                            or "refresh_failed"
                        )[:160]
                    ),
                )
            except Exception:
                logger.exception("[浏览器流量] 收口刷新 AT 上下文失败；刷新结果保持不变")
        if opened is not None:
            browser_traffic.finish_roxy_capture(opened)
        if driver is not None and not keep_browser:
            _quit_driver(driver)
        if opened is not None and not keep_browser:
            try:
                if (network_recovery_failed or budget_exhausted) and bool(getattr(cfg, "ROXY_KEEP_BROWSER_OPEN", False)):
                    # 只关闭本次 AT 失败环境，避免保留窗口阻塞后续同账号换线。
                    client.close_profile(opened.profile_id)
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[查活][Roxy] 清理临时环境失败（profile 原值不写日志）")
