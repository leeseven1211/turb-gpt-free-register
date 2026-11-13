# -*- coding: utf-8 -*-
"""使用 Roxy 指纹浏览器为已注册账号刷新 ChatGPT accessToken。

该流程复用本地保存密码处理页面提供的密码、TOTP 和邮箱 OTP；没有保存密码时
不创建密码，资料页仍交回明确的补全操作。
"""
from __future__ import annotations

import logging
import re
import time
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
from core.operations.runtime import OperationCancelled, check_cancelled, current_token, report_stage
from core.operations.task_gateway import OperationLeaseLost
from core.auth.browser.selenium_auth import build_driver as _build_driver, center_browser_window as _center_browser_window, clear_otp_inputs as _clear_otp_inputs, click_continue as _click_continue, click_resend_email_otp as _click_resend_email_otp, email_otp_page_state as _email_otp_page_state, fetch_chatgpt_session as _fetch_chatgpt_session, find_any as _find_any, has_access_token as _has_access_token, is_email_verification_page as _is_email_verification_page, is_login_password_page as _is_login_password_page, maybe_accept as _maybe_accept, page_warmup as _page_warmup, quit_driver as _quit_driver, safe_get as _safe_get, submit_email_step as _submit_email_step, submit_email_via_browser_nextauth as _submit_email_via_browser_nextauth, type_email_address as _type_email_address, type_otp as _type_otp, wait_after_email_otp_submit as _wait_after_email_otp_submit, wait_email_submit_next_state as _wait_email_submit_next_state
from core.browser.roxy.client import RoxyBrowserClient
from core.accounts.liveness.roxy.refresh_errors import ROXY_LOGIN_CAUSES, roxy_login_failure_code
from core.network.at_transport_recovery import AtRecoveryTimeout

logger = logging.getLogger('core.roxy_liveness')

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
    """AT 只依据可信 MFA 路由和当前可操作表单提前交接 TOTP。"""
    if not isinstance(snapshot, dict):
        return False
    from core.auth.state_machine import PageState, classify_page

    if classify_page(snapshot) in {
        PageState.AUTH_ERROR, PageState.LOGGED_OUT, PageState.EMAIL_VERIFIED, PageState.AUTHENTICATED,
        PageState.PASSWORD_LOGIN, PageState.PASSWORD_CREATE, PageState.PROFILE,
    }:
        return False
    try:
        location = urlparse(str(snapshot.get("url") or ""))
        if (location.scheme != "https" or location.hostname != "auth.openai.com" or location.port not in (None, 443)
                or location.username or location.password or not location.path.startswith("/mfa-challenge/")
                or not location.path.removeprefix("/mfa-challenge/")):
            return False
    except ValueError:
        return False
    inputs = [item for item in snapshot.get("inputs") or [] if isinstance(item, dict)
              and item.get("visible") is not False and item.get("otpFieldVisible") is not False
              and str(item.get("type") or "").lower() != "hidden"]
    if any(str(item.get("type") or "").lower() == "password"
           or str(item.get("autocomplete") or "").lower() == "current-password"
           or any("password" in str(item.get(key) or "").lower() for key in ("name", "id")) for item in inputs):
        return False
    available = [item for item in inputs if not item.get("otpFieldDisabled", item.get("disabled"))
                 and not item.get("otpFieldReadOnly", item.get("readOnly"))]
    if not available:
        return False
    from core.codex.roxy.oauth import _is_totp_login_page

    return _is_totp_login_page(None, {**snapshot, "inputs": available})


def _classify_at_login_page(snapshot):
    """仅 AT 补足本地化 MFA 页面；默认分类及明确错误仍由公共分类器决定。"""
    from core.auth.state_machine import PageState, classify_page

    page = classify_page(snapshot)
    if page in {PageState.OTP_EMAIL, PageState.AUTH_TRANSIENT, PageState.UNKNOWN} and _is_at_totp_login_page(snapshot):
        return PageState.MFA_TOTP
    return page


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
    """刷新只建立会话，资料页必须保留为独立的待补全事实。"""
    parsed = urlparse(str(getattr(driver, "current_url", "") or ""))
    if parsed.hostname == "auth.openai.com" and any(
        marker in parsed.path for marker in ("about-you", "/profile", "create-account/about")
    ):
        error = RuntimeError("profile_completion_required: 密码步骤已推进，服务端要求补全账号资料")
        error.code = "profile_completion_required"
        raise error


def available() -> bool:
    return (
        bool(str(getattr(cfg, "ROXY_API_BASE", "") or "").strip())
        and bool(str(getattr(cfg, "ROXY_API_TOKEN", "") or "").strip())
        and bool(str(getattr(cfg, "ROXY_WORKSPACE_ID", "") or "").strip())
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _page_account_unusable_code(driver) -> str:
    """从 Roxy 当前页面识别明确的账号停用/封禁文案。"""
    try:
        url = str(driver.current_url or "")
    except Exception:
        url = ""
    try:
        title = str(driver.title or "")
    except Exception:
        title = ""
    try:
        text = str(driver.execute_script("return document.body ? document.body.innerText : '';" ) or "")
    except Exception:
        text = ""
    return detect_account_unusable_text("\n".join((url, title, text)))


def _open_standard_password_login(driver) -> bool:
    """只读尝试一次既有密码页，确认可信地址和可见密码框后才交给认证状态机。"""
    def trusted_password_page() -> bool:
        parsed = urlparse(str(getattr(driver, "current_url", "") or ""))
        return (
            parsed.scheme == "https" and parsed.netloc.lower() in {"auth.openai.com", "auth.openai.com:443"}
            and parsed.path.rstrip("/") == "/log-in/password"
        )

    _safe_get(
        driver, "https://auth.openai.com/log-in/password",
        timeout=10, attempts=1, accept_hosts=("auth.openai.com",),
    )
    if not trusted_password_page():
        return False
    try:
        _find_any(driver, ["input[type='password']"], timeout=8)
    except RuntimeError as exc:
        if str(exc).startswith("找不到页面元素:"):
            return False
        raise
    return trusted_password_page()


def _enter_existing_account_otp(
    driver,
    email: str,
    *,
    password: str = "",
    totp_secret: str = "",
) -> str:
    """提交邮箱并完成已有账号登录挑战；返回 ``otp``/``logged_in``。"""
    from core.auth.page_errors import auth_page_error

    def observe_page(snapshot):
        browser_error = _browser_proxy_error(driver, snapshot=snapshot)
        if browser_error:
            logger.warning("[查活][Roxy] 邮箱提交后页面识别：浏览器代理连接失败，错误码=%s；停止等待下一步", browser_error)
            raise RuntimeError(f"浏览器代理连接失败：{browser_error}")
        error = auth_page_error(snapshot)
        if error is not None:
            logger.warning("[查活][Roxy] 邮箱提交后页面识别：%s；立即交给登录恢复", error)
            raise error

    code = _page_account_unusable_code(driver)
    if code:
        raise AccountUnusableError(f"登录页确认账号已停用/封禁: {code}", error_code=code)
    state = ""
    try:
        _type_email_address(driver, email, timeout=25)
    except RuntimeError as exc:
        # 查活入口遇到未挂载的 ChatGPT 登录壳时，直接复用当前 Roxy
        # 浏览器上下文走 NextAuth。这里不重试输入或提交，避免重复触发认证。
        if "找不到邮箱输入框/邮箱入口" not in str(exc):
            raise
        fallback = _submit_email_via_browser_nextauth(driver, email)
        state = str(fallback.get("state") or "").strip().lower()
        logger.warning(
            "[查活][Roxy] 邮箱入口未挂载，启用 NextAuth 登录兜底：%s",
            {key: fallback.get(key) for key in ("ok", "stage", "state", "reason") if key in fallback},
        )
        if not fallback.get("ok") and state not in {"otp", "password", "login_password", "logged_in"}:
            raise RuntimeError(f"邮箱入口未挂载且 NextAuth 兜底失败：{fallback}") from exc
        if state not in {"otp", "password", "login_password", "logged_in"}:
            state = _wait_email_submit_next_state(
                driver,
                email,
                timeout=35,
                wait_through_transient=True,
                on_page_observed=observe_page,
            )
    else:
        _submit_email_step(driver, email)
        code = _page_account_unusable_code(driver)
        if code:
            raise AccountUnusableError(f"邮箱提交后页面确认账号已停用/封禁: {code}", error_code=code)
        state = _wait_email_submit_next_state(driver, email, timeout=30, on_page_observed=observe_page)
    if state in {"blank_shell", "email_page", "email_cleared", "unknown"}:
        fallback = _submit_email_via_browser_nextauth(driver, email)
        state = str(fallback.get("state") or "")
        if not state:
            state = _wait_email_submit_next_state(
                driver,
                email,
                timeout=35,
                wait_through_transient=True,
                on_page_observed=observe_page,
            )
        if not fallback.get("ok") and state not in {"otp", "password", "login_password", "logged_in"}:
            raise RuntimeError(f"浏览器 NextAuth 登录导航失败: {fallback}")
    if state == "logged_in" or _has_access_token(driver):
        return "logged_in"
    if _is_at_totp_login_page(_email_otp_page_state(driver)):
        from core.codex.roxy.oauth import complete_openai_login_challenge

        challenge_state = complete_openai_login_challenge(
            driver, email, password, totp_secret, timeout=45, page_classifier=_classify_at_login_page,
        )
        _check_profile_handoff(driver)
        if challenge_state == "advanced":
            return "logged_in"
        if challenge_state == "email_otp":
            return "otp"
        raise RuntimeError(f"已有账号 TOTP 登录挑战未完成：state={challenge_state}")
    if state == "password" and not _is_login_password_page(driver) and not password:
        raise RuntimeError("邮箱进入新账号创建密码页，查活已停止，未创建账号")
    if state in {"login_password", "password"} or _is_login_password_page(driver):
        # Keep the liveness flow aligned with the shared browser login state
        # machine. Some existing accounts land on /log-in/password even when
        # their saved credentials are valid; the old liveness-only path could
        # only search for a passwordless button and therefore failed every
        # such refresh before trying the saved password/TOTP.
        from core.codex.roxy.oauth import complete_openai_login_challenge

        if account_email_is_invalid(email) and not password:
            raise _EmailInvalidLoginError("password_missing", not_submitted=True)
        challenge_state = complete_openai_login_challenge(
            driver,
            email,
            password,
            totp_secret,
            timeout=45,
            page_classifier=_classify_at_login_page,
        )
        _check_profile_handoff(driver)
        if challenge_state == "advanced":
            return "logged_in"
        if challenge_state == "email_otp":
            if account_email_is_invalid(email):
                raise _EmailInvalidLoginError("email_verification_required")
            return "otp"
        raise RuntimeError(f"已有账号登录挑战未完成：state={challenge_state}")
    if state == "otp" or _is_email_verification_page(driver):
        email_invalid = account_email_is_invalid(email)
        if email_invalid or password:
            from core.codex.roxy.oauth import complete_openai_login_challenge

            if not password:
                raise _EmailInvalidLoginError("password_missing", not_submitted=True)
            initial_receipt = getattr(driver, "_browser_submission_receipt", None)
            initial_history = getattr(driver, "_browser_submission_receipts", None)
            initial_receipts = {id(item) for item in initial_history} if isinstance(initial_history, list) else set()

            def password_submitted() -> bool:
                receipt = getattr(driver, "_browser_submission_receipt", None)
                if receipt is not initial_receipt and getattr(receipt, "endpoint_kind", "") == "password_submit":
                    return True
                history = getattr(driver, "_browser_submission_receipts", None)
                return isinstance(history, list) and any(
                    id(item) not in initial_receipts and getattr(item, "endpoint_kind", "") == "password_submit"
                    for item in history
                )

            challenge_state = complete_openai_login_challenge(
                driver, email, password, totp_secret, timeout=45,
                page_classifier=_classify_at_login_page,
            )
            _check_profile_handoff(driver)
            if challenge_state == "advanced":
                return "logged_in"
            if challenge_state == "email_otp":
                if not email_invalid:
                    return "otp"
                # 公共状态机找不到页面提供的密码入口时会直接返回邮箱分支；
                # 只有本轮产生密码提交回执，才把它描述为密码后的邮箱挑战。
                if not password_submitted():
                    try:
                        opened_password = _open_standard_password_login(driver)
                    except (OperationCancelled, AuthCancelledError, OperationLeaseLost):
                        raise
                    except Exception as exc:
                        raise _EmailInvalidLoginError("password_login_unavailable", not_submitted=True) from exc
                    if not opened_password:
                        raise _EmailInvalidLoginError("password_login_unavailable", not_submitted=True)
                    challenge_state = complete_openai_login_challenge(
                        driver, email, password, totp_secret, timeout=45,
                        page_classifier=_classify_at_login_page,
                    )
                    if challenge_state == "advanced":
                        return "logged_in"
                    if challenge_state == "email_otp":
                        if not password_submitted():
                            raise _EmailInvalidLoginError("password_login_unavailable", not_submitted=True)
                        raise _EmailInvalidLoginError("email_verification_required")
                else:
                    raise _EmailInvalidLoginError("email_verification_required")
            raise RuntimeError(f"已有账号登录挑战未完成：state={challenge_state}")
        return "otp"
    raise RuntimeError(f"浏览器登录未进入已有账号 OTP，最后状态={state}")


def _complete_otp(
    driver,
    email: str,
    after_ts: float,
    *,
    password: str = "",
    totp_secret: str = "",
    on_email_confirmed=None,
) -> None:
    from core.auth.browser.auth_context import checkpoint, current_execution_context
    from core.auth.browser.browser_submission import BrowserSubmissionReceipt
    from core.auth.browser.email_otp import _email_otp_form_is_ready
    from core.auth.page_errors import auth_page_error
    from core.auth.state_machine import PageState, StageBudget, StageTimeout
    from core.accounts.liveness.protocol.otp_diagnostics import BUTLER_TRANSPORT_ERROR_CODES
    from config import email as email_config

    context = current_execution_context()
    budget = context.budget if context is not None else None
    if context is not None and context.deadline is not None:
        deadline = min(context.deadline, budget.deadline) if budget is not None else context.deadline
        budget = StageBudget(deadline, clock=time.monotonic, cancellation=context.cancellation)
    no_mail_resent = False
    mailbox_read_retried = False
    login_restarted = False
    current_page = PageState.UNKNOWN
    resend_receipt = None

    def check_resend_receipt():
        if resend_receipt is None:
            return
        status = resend_receipt.http_status
        if type(status) is int and 400 <= status <= 599:
            raise EmailOtpSendError("http_error", status)
        if resend_receipt.phase == "rejected":
            raise EmailOtpSendError("rejected", status or 0)

    def observe_page():
        nonlocal current_page
        check_cancelled("用户手动停止刷新 AT")
        checkpoint()
        check_resend_receipt()
        state = _email_otp_page_state(driver)
        browser_error = _browser_proxy_error(driver, snapshot=state)
        if browser_error:
            raise RuntimeError(f"浏览器代理连接失败：{browser_error}")
        location = urlparse(str(state.get("url") or ""))
        if (location.scheme != "https" or location.hostname not in {"chatgpt.com", "auth.openai.com"}
                or location.port not in (None, 443) or location.username or location.password):
            current_page = PageState.UNKNOWN
            return
        error = auth_page_error(state)
        if error is not None:
            raise error
        current_page = _classify_at_login_page(state)
        if current_page in {PageState.OTP_EMAIL, PageState.MFA_TOTP}:
            hints = re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}",
                               str(state.get("text") or ""), flags=re.IGNORECASE)
            if any(hint.casefold() != email.strip().casefold() for hint in hints):
                error = RuntimeError("identity_mismatch: 当前认证页面的邮箱与任务账号不一致")
                error.code = "identity_mismatch"
                raise error
        if current_page == PageState.MFA_TOTP:
            raise _AtOtpPageChanged("totp_required")
        if current_page in {PageState.AUTH_ERROR, PageState.LOGGED_OUT}:
            raise _RoxyOtpSubmissionUnknown("email_submit_unconfirmed: 等码期间认证页面已失效")
        if current_page == PageState.EMAIL_VERIFIED or state.get("emailVerified") is True:
            raise _AtOtpPageChanged("email_verified")
        if (location.hostname == "chatgpt.com" and not location.path.startswith(("/auth/", "/api/", "/login"))
                and _has_access_token(driver, **({"budget": budget} if budget is not None else {}))):
            raise _AtOtpPageChanged("logged_in")
        email_input = any(isinstance(item, dict) and item.get("visible") is not False
                          and (str(item.get("type") or "").lower() == "email"
                               or str(item.get("name") or "").lower() in {"email", "username"})
                          for item in state.get("inputs") or [])
        if (email_input and (location.hostname, location.path.rstrip("/")) in {
                ("chatgpt.com", "/auth/login"), ("auth.openai.com", "/log-in"),
                ("auth.openai.com", "/log-in/email")}):
            raise _AtOtpPageChanged("email_page")
        if current_page == PageState.PROFILE:
            _check_profile_handoff(driver)
        if (current_page == PageState.OTP_EMAIL and (
                location.hostname != "auth.openai.com" or location.path.rstrip("/") != "/email-verification"
                or not _email_otp_form_is_ready(state))):
            current_page = PageState.AUTH_TRANSIENT

    def wait_current_otp():
        nonlocal after_ts, no_mail_resent, mailbox_read_retried, resend_receipt
        while True:
            try:
                round_wait = max(1, int(email_config.OTP_MAX_WAIT))
                code = wait_for_otp(email, after_ts=after_ts, max_wait=round_wait,
                                    page_checkpoint=observe_page, page_request_timeout=round_wait,
                                    **({"budget": budget} if budget is not None else {}))
                observe_page()
                return code
            except (EmailButlerClientError, ForwardIMAPNoMailTimeout) as exc:
                check_resend_receipt()
                if (isinstance(exc, EmailButlerClientError) and exc.error_code in BUTLER_TRANSPORT_ERROR_CODES
                        and getattr(exc, "retryable", False) is True and not mailbox_read_retried):
                    observe_page()
                    mailbox_read_retried = True
                    logger.warning("[查活][Roxy] 收件前置读取发生临时连接故障，沿原时间窗只读恢复一次")
                    continue
                no_mail = (isinstance(exc, ForwardIMAPNoMailTimeout) or (
                    exc.error_code == "inbound_code_timeout" and exc.status_code in (None, 408)))
                if not no_mail or no_mail_resent:
                    raise
                observe_page()
                if current_page != PageState.OTP_EMAIL:
                    raise
                no_mail_resent = True
                logger.warning("[查活][Roxy] 首轮等待未收到验证码，在当前账号验证页重发一次")
                requested_at = time.time()
                try:
                    resend = _click_resend_email_otp(driver, timeout=25,
                                                   **({"budget": budget} if budget is not None else {}))
                except (OperationCancelled, AuthCancelledError, OperationLeaseLost, StageTimeout, AtRecoveryTimeout):
                    raise
                except Exception as send_error:
                    receipt = getattr(driver, "_otp_resend_receipt", None)
                    if not isinstance(receipt, dict) or not receipt.get("clicked"):
                        raise EmailOtpSendError("unconfirmed") from send_error
                    resend = {"requested_after_ts": receipt.get("requested_after_ts"), "ui_ack": "unconfirmed"}
                receipt = getattr(driver, "_browser_submission_receipt", None)
                if isinstance(receipt, BrowserSubmissionReceipt) and receipt.stage == "otp_resend":
                    resend_receipt = receipt
                check_resend_receipt()
                resend = resend if isinstance(resend, dict) else {}
                after_ts = float(resend.get("requested_after_ts") or requested_at)
                if resend.get("ui_ack") != "confirmed":
                    logger.warning("[查活][Roxy] 重发已派发但页面回执未确认，继续等待本次邮件，不追加重发")
                observe_page()

    def complete_totp():
        from core.codex.roxy.oauth import complete_openai_login_challenge

        if callable(on_email_confirmed):
            on_email_confirmed()
        challenge_state = complete_openai_login_challenge(
            driver, email, "", totp_secret, timeout=45, page_classifier=_classify_at_login_page,
        )
        if challenge_state != "advanced":
            raise RuntimeError(f"邮箱验证码后 TOTP 登录链未完成：state={challenge_state}")

    current_otp = None
    for attempt in range(1, 4):
        while current_otp is None:
            try:
                current_otp = wait_current_otp()
            except _AtOtpPageChanged as change:
                if change.state == "totp_required":
                    complete_totp()
                    return
                if change.state in {"logged_in", "email_verified"}:
                    if callable(on_email_confirmed):
                        on_email_confirmed()
                    return
                if login_restarted:
                    raise _RoxyOtpSubmissionUnknown("email_submit_unconfirmed: 恢复登录后再次返回邮箱入口")
                login_restarted = True
                logger.info("[查活][Roxy] 等码期间返回邮箱入口，交回已有账号登录流程")
                after_ts = time.time()

                def restart_boundary():
                    nonlocal after_ts
                    after_ts = time.time()

                state = _login_existing_account_with_recovery(
                    driver, email, password=password, totp_secret=totp_secret, on_restart=restart_boundary,
                )
                # 新登录只停止观察旧会话的重发结果；原回执事实和本次重发次数继续保留。
                resend_receipt = None
                if state == "logged_in":
                    return
        baseline = _email_otp_page_state(driver)
        _clear_otp_inputs(driver)
        _type_otp(driver, current_otp)
        try:
            _click_continue(driver)
        except (OperationCancelled, AuthCancelledError, OperationLeaseLost):
            raise
        except Exception:
            # 输入最后一位可能已触发自动提交，原按钮卸载后继续观察原结果。
            pass
        outcome = _wait_after_email_otp_submit(
            driver, timeout=35, baseline_state=baseline, expected_email=email,
            page_classifier=_classify_at_login_page,
        )
        if outcome in {"accepted", "email_verified"} and callable(on_email_confirmed):
            on_email_confirmed()
        if outcome in {"accepted", "email_verified"}:
            return
        if outcome == "totp_required":
            complete_totp()
            return
        if outcome != "invalid":
            reason = "认证会话已失效" if outcome == "session_expired" else "验证码提交结果未确认"
            raise _RoxyOtpSubmissionUnknown(f"email_submit_unconfirmed: {reason}，state={outcome}")
        if attempt >= 3:
            break
        requested_at = time.time()
        resend = _click_resend_email_otp(driver, timeout=25)
        after_ts = float(resend.get("requested_after_ts") or requested_at) if isinstance(resend, dict) else requested_at
        current_otp = None
    raise RuntimeError("邮箱验证码连续错误/过期，已达到最大重试次数")


def _authenticated_browser_session(driver, proxy: str | None):
    """为既有成功回调提供同线路、同 Cookie 的协议会话，不把 Selenium 当作 HTTP 会话。"""
    from core.auth.protocol.session import BrowserSession

    session = BrowserSession(proxy=str(proxy or ""), detect_exit_geo=False)
    try:
        for cookie in driver.get_cookies():
            domain = str(cookie.get("domain") or "").lstrip(".").lower()
            if domain not in {"chatgpt.com", "auth.openai.com"}:
                continue
            name = str(cookie.get("name") or "")
            if not name:
                continue
            value = str(cookie.get("value") or "")
            session.session.cookies.set(name, value, domain=str(cookie["domain"]), path=str(cookie.get("path") or "/"))
            if name == "oai-did" and value:
                session.device_id = value
        for domain in ("chatgpt.com", "auth.openai.com", "sentinel.openai.com"):
            session.session.cookies.set("oai-did", session.device_id, domain=domain, path="/")
        user_agent = driver.execute_script("return navigator.userAgent;")
        if isinstance(user_agent, str) and user_agent.strip():
            session.session.headers["User-Agent"] = user_agent
        return session
    except BaseException:
        session.session.close()
        raise


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
    """明确错误页离开旧文档后重建一次登录，两轮共用原截止时间。"""
    from dataclasses import replace
    from core.auth.browser.auth_context import AuthExecutionContext, current_execution_context, execution_context
    from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
    from core.auth.browser.submission_recovery import begin_auth_session
    from core.auth.page_errors import AuthPageError
    from core.auth.state_machine import StageBudget, StageTimeout

    parent = current_execution_context() or AuthExecutionContext()
    remaining = parent.remaining(float(timeout))
    budget = parent.budget.child(remaining) if parent.budget else StageBudget.start(remaining, clock=time.monotonic)
    context = replace(parent, budget=budget)
    with execution_context(context):
        for attempt in range(2):
            context.checkpoint()
            try:
                return _enter_existing_account_otp(driver, email, password=password, totp_secret=totp_secret)
            except AuthPageError as exc:
                logger.warning("[查活][Roxy] 页面识别：%s；剩余预算=%.1f秒；恢复=%d/1",
                               str(exc), budget.remaining(), attempt)
                if attempt or budget.remaining() <= 1:
                    raise
                receipt = getattr(driver, "_browser_submission_receipt", None)
                if isinstance(receipt, BrowserSubmissionReceipt) and receipt.phase in {
                    "dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed",
                }:
                    record_browser_submission_fact(
                        driver, "unknown", receipt=receipt, result="unknown", error_type=exc.code,
                    )
                logger.warning("[查活][Roxy] %s；从 ChatGPT 登录入口重建同一账号认证（1/1），原提交回执继续保留",
                               str(exc))
                email_barrier = isinstance(getattr(driver, "_email_submission_receipt", None), dict)
                old_document = driver.execute_script("return performance.timeOrigin;") if email_barrier else None
                begin_auth_session(driver)
                driver._auth_page_error = None
                previous_timeout = getattr(getattr(driver, "timeouts", None), "page_load", None)
                try:
                    # 通用导航最少等待 10 秒；此恢复入口直接使用原预算的剩余时间。
                    driver.set_page_load_timeout(min(10.0, budget.require("重建登录入口")))
                    driver.get("https://chatgpt.com/auth/login")
                    context.checkpoint()
                    if email_barrier:
                        new_document = driver.execute_script("return performance.timeOrigin;")
                        if not (type(old_document) in (int, float) and type(new_document) in (int, float)
                                and new_document != old_document):
                            logger.warning("[查活][Roxy] 未确认已离开原认证文档，保留邮箱提交屏障与原错误")
                            raise exc
                        # 新文档只释放本地点击屏障，旧 HTTP 提交回执仍保留 unknown。
                        driver._email_submission_receipt = None
                        driver._email_submission_diagnostics = None
                    _page_warmup(driver, reason="live_check_login_recovery")
                    context.checkpoint()
                    if callable(on_restart):
                        on_restart()
                except StageTimeout:
                    raise exc
                finally:
                    if isinstance(previous_timeout, (int, float)):
                        try:
                            driver.set_page_load_timeout(previous_timeout)
                        except Exception:
                            logger.debug("[查活][Roxy] 恢复导航后还原加载超时失败")
        raise RuntimeError("已有账号登录恢复未返回状态")


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
            visible_stage, message = {
                "driver": ("login", "正在连接 Roxy 浏览器"),
                "navigation": ("login", "正在加载 ChatGPT 登录页"),
                "login": ("login", "正在登录账号，优先使用页面提供的已保存密码入口"),
                "email_otp": ("email_otp", "服务端仍要求邮箱验证，正在查收邮箱验证码"),
                "session": ("refresh_token", "登录验证已完成，正在读取会话和 AT"),
                "callback": ("token", "正在处理已取得的登录会话"),
            }[value]
            report_stage(visible_stage, message)

    try:
        check_cancelled("用户手动停止刷新 AT")
        client = RoxyBrowserClient()
        from core.browser.roxy.profile_binding import account_profile_id_by_email, persist_account_profile_id

        bound_profile_id = account_profile_id_by_email(email, strict=True)
        logger.info("[查活][Roxy] 打开或创建账号指纹浏览器环境")
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
        _safe_get(
            driver,
            "https://chatgpt.com/auth/login",
            timeout=min(50, int(getattr(cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
            attempts=2,
            accept_hosts=("chatgpt.com", "auth.openai.com"),
        )
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
