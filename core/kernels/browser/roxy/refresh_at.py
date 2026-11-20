# -*- coding: utf-8 -*-
"""Authentication execution extracted without domain storage or task ownership.

Explicit dependencies preserve the original compatibility patch points.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class IsAtTotpLoginPageDependencies:
    """Capabilities resolved by the domain at this invocation."""
    urlparse: Any
    _is_totp_login_page: Any


def _is_at_totp_login_page(snapshot, *, _deps: IsAtTotpLoginPageDependencies) -> bool:
    """AT 只依据可信 MFA 路由和当前可操作表单提前交接 TOTP。"""
    urlparse = _deps.urlparse
    _is_totp_login_page = _deps._is_totp_login_page
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

    return _is_totp_login_page(None, {**snapshot, "inputs": available})


@dataclass(frozen=True)
class ClassifyAtLoginPageDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _is_at_totp_login_page: Any


def _classify_at_login_page(snapshot, *, _deps: ClassifyAtLoginPageDependencies):
    """仅 AT 补足本地化 MFA 页面；默认分类及明确错误仍由公共分类器决定。"""
    _is_at_totp_login_page = _deps._is_at_totp_login_page
    from core.auth.state_machine import PageState, classify_page

    page = classify_page(snapshot)
    if page in {PageState.OTP_EMAIL, PageState.AUTH_TRANSIENT, PageState.UNKNOWN} and _is_at_totp_login_page(snapshot):
        return PageState.MFA_TOTP
    return page


@dataclass(frozen=True)
class CheckProfileHandoffDependencies:
    """Capabilities resolved by the domain at this invocation."""
    urlparse: Any
    pass


def _check_profile_handoff(driver, *, _deps: CheckProfileHandoffDependencies) -> None:
    """刷新只建立会话，资料页必须保留为独立的待补全事实。"""
    urlparse = _deps.urlparse
    parsed = urlparse(str(getattr(driver, "current_url", "") or ""))
    if parsed.hostname == "auth.openai.com" and any(
        marker in parsed.path for marker in ("about-you", "/profile", "create-account/about")
    ):
        error = RuntimeError("profile_completion_required: 密码步骤已推进，服务端要求补全账号资料")
        error.code = "profile_completion_required"
        raise error


@dataclass(frozen=True)
class PageAccountUnusableCodeDependencies:
    """Capabilities resolved by the domain at this invocation."""
    detect_account_unusable_text: Any


def _page_account_unusable_code(driver, *, _deps: PageAccountUnusableCodeDependencies) -> str:
    """从 Roxy 当前页面识别明确的账号停用/封禁文案。"""
    detect_account_unusable_text = _deps.detect_account_unusable_text
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


@dataclass(frozen=True)
class OpenStandardPasswordLoginDependencies:
    """Capabilities resolved by the domain at this invocation."""
    urlparse: Any
    _find_any: Any
    _safe_get: Any


def _open_standard_password_login(driver, *, _deps: OpenStandardPasswordLoginDependencies) -> bool:
    """只读尝试一次既有密码页，确认可信地址和可见密码框后才交给认证状态机。"""
    urlparse = _deps.urlparse
    _find_any = _deps._find_any
    _safe_get = _deps._safe_get
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


@dataclass(frozen=True)
class EnterExistingAccountOtpDependencies:
    """Capabilities resolved by the domain at this invocation."""
    AccountUnusableError: Any
    AuthCancelledError: Any
    OperationCancelled: Any
    OperationLeaseLost: Any
    _EmailInvalidLoginError: Any
    _browser_proxy_error: Any
    _check_profile_handoff: Any
    _classify_at_login_page: Any
    _email_otp_page_state: Any
    _has_access_token: Any
    _is_at_totp_login_page: Any
    _is_email_verification_page: Any
    _is_login_password_page: Any
    _open_standard_password_login: Any
    _page_account_unusable_code: Any
    _submit_email_step: Any
    _submit_email_via_browser_nextauth: Any
    _type_email_address: Any
    _wait_email_submit_next_state: Any
    account_email_is_invalid: Any
    complete_openai_login_challenge: Any
    logger: Any


def _enter_existing_account_otp(driver, email: str, *, password: str='', totp_secret: str='', _deps: EnterExistingAccountOtpDependencies) -> str:
    """提交邮箱并完成已有账号登录挑战；返回 ``otp``/``logged_in``。"""
    AccountUnusableError = _deps.AccountUnusableError
    AuthCancelledError = _deps.AuthCancelledError
    OperationCancelled = _deps.OperationCancelled
    OperationLeaseLost = _deps.OperationLeaseLost
    _EmailInvalidLoginError = _deps._EmailInvalidLoginError
    _browser_proxy_error = _deps._browser_proxy_error
    _check_profile_handoff = _deps._check_profile_handoff
    _classify_at_login_page = _deps._classify_at_login_page
    _email_otp_page_state = _deps._email_otp_page_state
    _has_access_token = _deps._has_access_token
    _is_at_totp_login_page = _deps._is_at_totp_login_page
    _is_email_verification_page = _deps._is_email_verification_page
    _is_login_password_page = _deps._is_login_password_page
    _open_standard_password_login = _deps._open_standard_password_login
    _page_account_unusable_code = _deps._page_account_unusable_code
    _submit_email_step = _deps._submit_email_step
    _submit_email_via_browser_nextauth = _deps._submit_email_via_browser_nextauth
    _type_email_address = _deps._type_email_address
    _wait_email_submit_next_state = _deps._wait_email_submit_next_state
    account_email_is_invalid = _deps.account_email_is_invalid
    complete_openai_login_challenge = _deps.complete_openai_login_challenge
    logger = _deps.logger
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


@dataclass(frozen=True)
class CompleteOtpDependencies:
    """Capabilities resolved by the domain at this invocation."""
    re: Any
    time: Any
    urlparse: Any
    AtRecoveryTimeout: Any
    AuthCancelledError: Any
    EmailButlerClientError: Any
    EmailOtpSendError: Any
    ForwardIMAPNoMailTimeout: Any
    OperationCancelled: Any
    OperationLeaseLost: Any
    _AtOtpPageChanged: Any
    _RoxyOtpSubmissionUnknown: Any
    _browser_proxy_error: Any
    _check_profile_handoff: Any
    _classify_at_login_page: Any
    _clear_otp_inputs: Any
    _click_continue: Any
    _click_resend_email_otp: Any
    _email_otp_page_state: Any
    _has_access_token: Any
    _login_existing_account_with_recovery: Any
    _type_otp: Any
    _wait_after_email_otp_submit: Any
    butler_transport_error_codes: Any
    check_cancelled: Any
    complete_openai_login_challenge: Any
    load_email_otp_wait_setting: Callable[[], Callable[[], Any]]
    logger: Any
    wait_for_otp: Any


def _complete_otp(driver, email: str, after_ts: float, *, password: str='', totp_secret: str='', on_email_confirmed=None, _deps: CompleteOtpDependencies) -> None:
    re = _deps.re
    time = _deps.time
    urlparse = _deps.urlparse
    AtRecoveryTimeout = _deps.AtRecoveryTimeout
    AuthCancelledError = _deps.AuthCancelledError
    EmailButlerClientError = _deps.EmailButlerClientError
    EmailOtpSendError = _deps.EmailOtpSendError
    ForwardIMAPNoMailTimeout = _deps.ForwardIMAPNoMailTimeout
    OperationCancelled = _deps.OperationCancelled
    OperationLeaseLost = _deps.OperationLeaseLost
    _AtOtpPageChanged = _deps._AtOtpPageChanged
    _RoxyOtpSubmissionUnknown = _deps._RoxyOtpSubmissionUnknown
    _browser_proxy_error = _deps._browser_proxy_error
    _check_profile_handoff = _deps._check_profile_handoff
    _classify_at_login_page = _deps._classify_at_login_page
    _clear_otp_inputs = _deps._clear_otp_inputs
    _click_continue = _deps._click_continue
    _click_resend_email_otp = _deps._click_resend_email_otp
    _email_otp_page_state = _deps._email_otp_page_state
    _has_access_token = _deps._has_access_token
    _login_existing_account_with_recovery = _deps._login_existing_account_with_recovery
    _type_otp = _deps._type_otp
    _wait_after_email_otp_submit = _deps._wait_after_email_otp_submit
    butler_transport_error_codes = _deps.butler_transport_error_codes
    check_cancelled = _deps.check_cancelled
    complete_openai_login_challenge = _deps.complete_openai_login_challenge
    load_email_otp_wait_setting = _deps.load_email_otp_wait_setting
    logger = _deps.logger
    wait_for_otp = _deps.wait_for_otp
    from core.auth.browser.auth_context import checkpoint, current_execution_context
    from core.auth.browser.browser_submission import BrowserSubmissionReceipt
    from core.auth.browser.email_otp import _email_otp_form_is_ready
    from core.auth.page_errors import auth_page_error
    from core.auth.state_machine import PageState, StageBudget, StageTimeout
    BUTLER_TRANSPORT_ERROR_CODES = butler_transport_error_codes()
    email_otp_max_wait = load_email_otp_wait_setting()

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
                round_wait = max(1, int(email_otp_max_wait()))
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


@dataclass(frozen=True)
class AuthenticatedBrowserSessionDependencies:
    """Capabilities resolved by the domain at this invocation."""
    pass


def _authenticated_browser_session(driver, proxy: str | None, *, _deps: AuthenticatedBrowserSessionDependencies):
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


@dataclass(frozen=True)
class LoginExistingAccountWithRecoveryDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    _enter_existing_account_otp: Any
    _page_warmup: Any
    logger: Any


def _login_existing_account_with_recovery(driver, email: str, *, password: str='', totp_secret: str='', timeout: float=120, on_restart=None, _deps: LoginExistingAccountWithRecoveryDependencies) -> str:
    """明确错误页离开旧文档后重建一次登录，两轮共用原截止时间。"""
    time = _deps.time
    _enter_existing_account_otp = _deps._enter_existing_account_otp
    _page_warmup = _deps._page_warmup
    logger = _deps.logger
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
