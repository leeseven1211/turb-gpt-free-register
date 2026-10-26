# -*- coding: utf-8 -*-
"""使用 Roxy 指纹浏览器为已注册账号刷新 ChatGPT accessToken。

该流程处理已有账号的密码、TOTP 和邮箱 OTP；一旦识别为新账号密码/资料页会
立即停止，避免查活意外创建账号。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from config import roxybrowser as cfg
from core.email_auth_guard import serialize_email_auth
from core.email_provider import wait_for_otp
from core.forward_imap_client import ForwardIMAPError, ForwardIMAPNoMailTimeout
from core.account_credentials import account_email_is_invalid
from core.openai_auth import AccountUnusableError, detect_account_unusable_text
from core.auth_challenge import AuthCancelledError
from core.operation_runtime import OperationCancelled, check_cancelled, current_token, report_stage
from core.operations.task_gateway import OperationLeaseLost
from core.registration.selenium_auth import (
    build_driver as _build_driver,
    center_browser_window as _center_browser_window,
    clear_otp_inputs as _clear_otp_inputs,
    click_continue as _click_continue,
    click_resend_email_otp as _click_resend_email_otp,
    email_otp_page_state as _email_otp_page_state,
    fetch_chatgpt_session as _fetch_chatgpt_session,
    find_any as _find_any,
    has_access_token as _has_access_token,
    is_email_verification_page as _is_email_verification_page,
    is_login_password_page as _is_login_password_page,
    maybe_accept as _maybe_accept,
    page_warmup as _page_warmup,
    quit_driver as _quit_driver,
    safe_get as _safe_get,
    submit_email_step as _submit_email_step,
    submit_email_via_browser_nextauth as _submit_email_via_browser_nextauth,
    type_email_address as _type_email_address,
    type_otp as _type_otp,
    wait_after_email_otp_submit as _wait_after_email_otp_submit,
    wait_email_submit_next_state as _wait_email_submit_next_state,
)
from core.roxybrowser_client import RoxyBrowserClient

logger = logging.getLogger(__name__)

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


def _browser_proxy_error(driver) -> str:
    """只读取浏览器自身错误页上的固定网络码，不回传页面正文。"""
    if driver is None:
        return ""
    try:
        if not str(driver.current_url or "").startswith("chrome-error://"):
            return ""
        text = str(driver.execute_script("return document.body ? document.body.innerText : '';"))
        return next((code for code in _PROXY_BROWSER_ERRORS if code in text), "")
    except Exception:
        return ""


def _refresh_failure_cause(exc: Exception, stage: str, browser_error: str = "") -> tuple[str, str]:
    """先保留认证异常的明确原因，再按实际失败阶段分类并保留异常原文。"""
    code = str(getattr(exc, "code", "") or "")
    if code in {"password_rejected", "password_result_unknown", "mfa_secret_missing", "mfa_rejected", "email_submit_unconfirmed"}:
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
            )
    else:
        _submit_email_step(driver, email)
        code = _page_account_unusable_code(driver)
        if code:
            raise AccountUnusableError(f"邮箱提交后页面确认账号已停用/封禁: {code}", error_code=code)
        state = _wait_email_submit_next_state(driver, email, timeout=30)
    if state in {"blank_shell", "email_page", "email_cleared", "unknown"}:
        fallback = _submit_email_via_browser_nextauth(driver, email)
        state = str(fallback.get("state") or "")
        if not state:
            state = _wait_email_submit_next_state(
                driver,
                email,
                timeout=35,
                wait_through_transient=True,
            )
        if not fallback.get("ok") and state not in {"otp", "password", "login_password", "logged_in"}:
            raise RuntimeError(f"浏览器 NextAuth 登录导航失败: {fallback}")
    if state == "logged_in" or _has_access_token(driver):
        return "logged_in"
    if state == "password" and not _is_login_password_page(driver):
        raise RuntimeError("邮箱进入新账号创建密码页，查活已停止，未创建账号")
    if state == "login_password" or _is_login_password_page(driver):
        # Keep the liveness flow aligned with the shared browser login state
        # machine. Some existing accounts land on /log-in/password even when
        # their saved credentials are valid; the old liveness-only path could
        # only search for a passwordless button and therefore failed every
        # such refresh before trying the saved password/TOTP.
        from core.roxy_codex_oauth import complete_openai_login_challenge

        if account_email_is_invalid(email) and not password:
            raise _EmailInvalidLoginError("password_missing", not_submitted=True)
        challenge_state = complete_openai_login_challenge(
            driver,
            email,
            password,
            totp_secret,
            timeout=45,
        )
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
            from core.roxy_codex_oauth import complete_openai_login_challenge

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
            )
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
    totp_secret: str = "",
) -> None:
    current_otp = None
    for attempt in range(1, 4):
        if current_otp is None:
            current_otp = wait_for_otp(email, after_ts=after_ts)
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
        )
        if outcome in {"accepted", "email_verified"}:
            return
        if outcome == "totp_required":
            from core.roxy_codex_oauth import complete_openai_login_challenge

            challenge_state = complete_openai_login_challenge(
                driver,
                email,
                "",
                totp_secret,
                timeout=45,
            )
            if challenge_state == "advanced":
                return
            raise RuntimeError(f"邮箱验证码后 TOTP 登录链未完成：state={challenge_state}")
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
    from core.session import BrowserSession

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
    """把原生任务取消信号传给共享 Selenium 的每个等待检查点。"""
    @wraps(function)
    def wrapped(*args, **kwargs):
        from core.operation_runtime import current_token
        from core.registration.auth_context import AuthExecutionContext, execution_context

        token = current_token()
        if token is None:
            return function(*args, **kwargs)
        with execution_context(AuthExecutionContext(
            cancellation=lambda: bool(token.requested()),
            cancellation_error=lambda: OperationCancelled("用户手动停止刷新 AT"),
        )):
            return function(*args, **kwargs)
    return wrapped


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
    from core import registration_debug

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
    remote_started = False
    failure_stage = "open"

    def stage(value: str) -> None:
        nonlocal failure_stage
        failure_stage = value
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
        from core.roxy_profile_binding import (
            account_profile_id_by_email,
            persist_account_profile_id,
        )

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
                from core import browser_traffic

                browser_traffic.bind_roxy_capture(opened, purpose="token_refresh")
            except Exception:
                logger.exception("[浏览器流量] 关联刷新 AT 上下文失败；刷新继续")
        effective_proxy = None if profile_reused else proxy
        stage("driver")
        driver = _build_driver(opened)
        if debug_session is not None:
            registration_debug.attach_current_roxy(getattr(opened, "debugger_address", None))
        from core import browser_asset_policy

        asset_cache = browser_asset_policy.start_auth_asset_cache(opened, driver, flow="token_refresh")
        try:
            from core import browser_flow_policy

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
        from core.roxy_codex_oauth import _account_login_credentials

        password, totp_secret = _account_login_credentials(email)
        otp_after_ts = time.time()
        check_cancelled("用户手动停止刷新 AT")
        if callable(on_remote_request_started):
            on_remote_request_started()
        remote_started = True
        stage("login")
        state = _enter_existing_account_otp(
            driver,
            email,
            password=password,
            totp_secret=totp_secret,
        )
        if state == "otp":
            stage("email_otp")
            _complete_otp(driver, email, otp_after_ts, totp_secret=totp_secret)
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
        logger.warning("[查活][Roxy] 失败：%s: %s", type(exc).__name__, str(exc)[:260])
        browser_error = _browser_proxy_error(driver)
        cause_code, category = _refresh_failure_cause(exc, failure_stage, browser_error)
        failure_kind = ("no_mail" if isinstance(exc, ForwardIMAPNoMailTimeout)
                        else "imap_error" if isinstance(exc, ForwardIMAPError)
                        else "runtime_exception")
        refresh_result = {
            "ok": False,
            "status": "failed",
            "checked_at": checked_at,
            "error": f"Roxy {type(exc).__name__}: {str(exc)[:500]}" + (f"；浏览器错误：{browser_error}" if browser_error else ""),
            "error_code": cause_code,
            "error_category": category,
            "failure_stage": failure_stage,
            "auth_diagnostics": {"operation": f"roxy_{failure_stage}", "failure_kind": failure_kind,
                                 "exception_type": type(exc).__name__},
            "validation_method": "roxy_email_otp",
        }
        if not remote_started:
            refresh_result.update({"remote_request_started": False, "mutation_submitted": False, "action_dispatched": False})
        return refresh_result
    finally:
        from core import browser_asset_policy, browser_traffic

        if isinstance(refresh_result, dict):
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
        keep_browser = not cancelled and (
            bool(getattr(cfg, "ROXY_KEEP_BROWSER_OPEN", False)) or (full_debug and failed)
        )
        if full_debug and failed and driver is not None and not cancelled:
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
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[查活][Roxy] 清理临时环境失败（profile 原值不写日志）")
