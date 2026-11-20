"""Execute the Roxy registration page flow with domain-owned persistence callbacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.browser.email_otp import _EmailSubmissionUnknown
from core.auth.browser.password_auth import PasswordPageError, ProfileAccountAlreadyExistsError
from core.auth.challenge import classify_registration_identity
from core.auth.state_machine import PageState, StageBudget


@dataclass(frozen=True)
class RoxyRegistrationRequest:
    email: str
    name: str
    birthday: str
    proxy: str | None
    otp_code: str | None
    existing_totp_secret: str | None
    profile_id: str | None
    current_profile_id: str
    selected_email_source: str | None
    password_required: bool
    resume_scope: bool
    resume_metadata: Any
    route_state: Any
    local_browser: bool
    route_recovery_enabled: bool
    cf_rotation_allowed: bool
    has_retained_browser: bool
    current_lease_route_verified: bool
    facts: dict


@dataclass
class RoxyRegistrationState:
    existing_password: str | None = None
    openai_password: str | None = None
    password_confirmed: bool = False
    access_token: str | None = None
    account_id: int | None = None
    create_acknowledged: bool = False
    remote_identity: str = "unknown"
    auth_challenge_chain: list[str] = field(default_factory=list)
    existing_profile_unverified: bool = False
    existing_profile_reconciliation: bool = False
    password_recovery: Any = None
    email_entry_waiting: bool = False
    resume_login_get_transport_failure: bool = False


@dataclass(frozen=True)
class RoxyBrowserCapabilities:
    check_stop: Callable[..., Any]
    classify_otp_wait_failure: Callable[..., Any]
    complete_totp: Callable[..., Any]
    fetch_session: Callable[..., Any]
    fill_password: Callable[..., Any]
    has_access_token: Callable[..., Any]
    is_email_verification_page: Callable[..., Any]
    is_proxy_transport_failure: Callable[..., Any]
    maybe_accept: Callable[..., Any]
    observe_email_page: Callable[..., Any]
    page_warmup: Callable[..., Any]
    read_resume_session: Callable[..., Any]
    reconcile_profile_session: Callable[..., Any]
    otp_attempt_wait_seconds: Callable[..., Any]
    password_confirmed_after_token: Callable[..., Any]
    profile_form_ready: Callable[..., Any]
    resend_otp: Callable[..., Any]
    retained_page_state: Callable[..., Any]
    safe_get: Callable[..., Any]
    submit_email_otp: Callable[..., Any]
    validate_session_identity: Callable[..., Any]
    wait_after_otp_submit: Callable[..., Any]
    wait_otp_page_ready: Callable[..., Any]
    wait_password_reset_required: Callable[..., Any]
    human_delay: Callable[..., Any]
    password_evidence: Callable[..., Any]
    password_receipt_ids: Callable[..., Any]
    submit_email: Callable[..., Any]
    complete_profile: Callable[..., Any]
    complete_login_challenge: Callable[..., Any]
    retained_state_factory: Callable[..., Any]
    otp_tracker_type: type
    password_transition_error: type[Exception]


@dataclass(frozen=True)
class RoxyRegistrationCallbacks:
    password_recovery_session: Callable[..., Any]
    resume_password_recovery: Callable[[Any], bool]
    password_recovery_confirms: Callable[[Any, str | None, bool], bool]
    recover_password: Callable[..., Any]
    prepare_retained_resume: Callable[..., Any]
    save_password_checkpoint: Callable[..., Any]
    save_pending_checkpoint: Callable[..., Any]
    record_submission: Callable[..., Any]
    report_progress: Callable[..., Any]
    report_otp_evidence: Callable[..., Any]
    report_registered_account: Callable[..., Any]
    wait_for_otp: Callable[..., Any]
    rejected_existing_profile: Callable[[str, dict], bool]
    otp_total_wait: Callable[[], int]
    selenium_timeout: Callable[[], int]
    lightweight_post_auth: Callable[[], bool]
    wall_time: Callable[[], float]
    logger: Any


@dataclass(frozen=True)
class RoxyAuthenticationResult:
    session_info: dict
    lightweight_post_auth: bool
    token_budget: StageBudget


def execute_registration_auth(
    driver,
    request: RoxyRegistrationRequest,
    state: RoxyRegistrationState,
    *,
    callbacks: RoxyRegistrationCallbacks,
    browser: RoxyBrowserCapabilities,
    route_observer=None,
    native_signin_diagnostics=None,
) -> RoxyAuthenticationResult:
    """Run the original page/password/OTP/profile/session sequence for one validated run."""
    email = request.email
    name = request.name
    birthday = request.birthday
    proxy = request.proxy
    otp_code = request.otp_code
    existing_totp_secret = request.existing_totp_secret
    profile_id = request.profile_id
    selected_email_source = request.selected_email_source
    password_required = request.password_required
    resume_scope = request.resume_scope
    resume_metadata = request.resume_metadata
    route_state = request.route_state
    current_lease_route_verified = request.current_lease_route_verified
    context = request.facts
    logger = callbacks.logger
    _check_manual_stop = browser.check_stop
    _classify_otp_wait_failure = browser.classify_otp_wait_failure
    _complete_registration_totp_after_email_otp = browser.complete_totp
    _fetch_chatgpt_session = browser.fetch_session
    _fill_password_page_if_present = browser.fill_password
    _has_access_token = browser.has_access_token
    _is_email_verification_page = browser.is_email_verification_page
    _is_registration_proxy_transport_failure = browser.is_proxy_transport_failure
    _maybe_accept = browser.maybe_accept
    _observe_registration_email_page = browser.observe_email_page
    _page_warmup = browser.page_warmup
    _read_registration_resume_session = browser.read_resume_session
    _reconcile_existing_profile_session = browser.reconcile_profile_session
    _registration_otp_attempt_wait_seconds = browser.otp_attempt_wait_seconds
    _registration_password_confirmed_after_token = browser.password_confirmed_after_token
    _registration_profile_form_ready = browser.profile_form_ready
    _resend_email_otp_after_failure = browser.resend_otp
    _retained_page_state = browser.retained_page_state
    _safe_get = browser.safe_get
    _submit_registration_email_otp = browser.submit_email_otp
    _validate_registration_session_identity = browser.validate_session_identity
    _wait_after_email_otp_submit = browser.wait_after_otp_submit
    _wait_email_otp_page_ready = browser.wait_otp_page_ready
    _wait_for_current_password_reset_required = browser.wait_password_reset_required
    human_delay = browser.human_delay
    password_evidence = browser.password_evidence
    password_receipt_ids = browser.password_receipt_ids
    submit_email = browser.submit_email
    complete_profile = browser.complete_profile
    complete_openai_login_challenge = browser.complete_login_challenge
    RetainedResumeState = browser.retained_state_factory
    _OtpAttemptTracker = browser.otp_tracker_type
    _PasswordTransitionTimeout = browser.password_transition_error
    _registration_password_recovery_session = callbacks.password_recovery_session
    _recover_roxy_password = callbacks.recover_password
    prepare_retained_resume = callbacks.prepare_retained_resume
    save_protocol_password_checkpoint = callbacks.save_password_checkpoint
    _save_pending_email_verification_checkpoint = callbacks.save_pending_checkpoint
    record_browser_submission_fact = callbacks.record_submission
    report_job_progress = callbacks.report_progress
    report_job_otp_evidence = callbacks.report_otp_evidence
    report_registered_account = callbacks.report_registered_account
    wait_for_otp = callbacks.wait_for_otp

    verified_resume_session = None
    retained_state = None
    restart_login = False
    rejected_existing_profile = False
    password_recovered_before_resume = False
    if resume_scope and request.local_browser and (route_state is None):
        state.password_recovery = _registration_password_recovery_session(email, context)
        if state.password_recovery is not None and callbacks.resume_password_recovery(state.password_recovery):
            report_job_progress("login_password", "running", "正在恢复原账号未完成的密码检查点")
            state.existing_password = _recover_roxy_password(
                driver,
                email,
                state.password_recovery,
                email_source=selected_email_source,
                totp_secret=existing_totp_secret,
            )
            password_recovered_before_resume = True
    if resume_scope:
        try:
            rejected_existing_profile = callbacks.rejected_existing_profile(email, context)
            state.existing_profile_unverified = rejected_existing_profile
        except Exception:
            raise RuntimeError("request_unknown: 同一 Attempt 的原资料拒绝事实无法核验，已保留原身份") from None
    if resume_metadata or (
        resume_scope and state.existing_password and profile_id and (request.current_profile_id == str(profile_id))
    ):
        report_job_progress("page", "running", "正在核验原浏览器环境的登录态")
        verified_resume_session = _read_registration_resume_session(driver, email)
        if request.route_recovery_enabled and route_observer is not None:
            route_observer.raise_if_failed(driver)
        if verified_resume_session:
            state.existing_profile_unverified = False
    if route_state is not None and verified_resume_session:
        retained_state = RetainedResumeState(PageState.AUTHENTICATED, state.existing_password)
    elif route_state is not None and route_state.restart_identity_login:
        if not state.existing_password:
            raise RuntimeError("request_unknown: 原写入结果未明且没有可核验候选密码，保留原身份")
        retained_page = _retained_page_state(
            driver, email, allow_restart=True, allow_callback_restart=route_state.failed_operation == "callback"
        )
        retained_state = RetainedResumeState(retained_page, state.existing_password, restart_login=True)
    elif route_state is not None and route_state.preauth_restart:
        retained_state = RetainedResumeState(PageState.AUTH_TRANSIENT, state.existing_password, restart_login=True)
    elif resume_metadata or password_recovered_before_resume:
        retained_state = prepare_retained_resume(
            driver,
            email=email,
            existing_password=state.existing_password,
            facts=context,
            verified_session=verified_resume_session,
            otp_after_ts=getattr(driver, "_registration_otp_after_ts", None)
            if password_recovered_before_resume
            else resume_metadata.otp_after_ts,
        )
    if retained_state is not None:
        state.existing_password = retained_state.password
        restart_login = bool(getattr(retained_state, "restart_login", False))
        if restart_login:
            logger.info("[Roxy注册] 原认证提交仍未确认，使用原邮箱和保存密码自动继续登录")
            retained_state = None
            driver._registration_otp_tracker = None
    otp_after_ts = (
        getattr(driver, "_registration_otp_after_ts", None)
        if password_recovered_before_resume and (not restart_login)
        else resume_metadata.otp_after_ts
        if resume_metadata and (not restart_login)
        else callbacks.wall_time()
    )
    if (
        retained_state
        and retained_state.page_state == PageState.OTP_EMAIL
        and (retained_state.pending_otp is None)
        and (otp_after_ts is None)
    ):
        raise RuntimeError("request_unknown: 原验证码邮件时间未能核验，已保留原浏览器")
    driver._registration_otp_after_ts = otp_after_ts
    if verified_resume_session:
        report_job_progress("page", "skipped", "原环境登录态已核验，无需打开登录页")
    elif retained_state:
        report_job_progress("page", "skipped", "已接管原失败窗口，从当前认证页面继续")
    else:
        report_job_progress("page", "running", "正在打开 ChatGPT 注册页")
        driver._registration_password_creation_chain = None
        entry_url = (
            "https://chatgpt.com/auth/login_with?callback_path=/"
            if not request.local_browser and resume_scope and state.existing_password
            else "https://chatgpt.com/auth/login"
        )
        logger.info("[Roxy注册] 打开登录页：%s", entry_url)
        if native_signin_diagnostics is not None:
            native_signin_diagnostics.begin_navigation(driver)
        if route_observer is not None:
            route_observer.begin_stage(driver, "preauth")
        try:
            _safe_get(
                driver,
                entry_url,
                timeout=min(45, callbacks.selenium_timeout()),
                attempts=2,
                accept_hosts=("chatgpt.com", "auth.openai.com"),
            )
        except Exception as exc:
            if route_observer is not None:
                route_observer.call_failed(driver, "GET", entry_url, exc)
            state.resume_login_get_transport_failure = bool(
                resume_scope and current_lease_route_verified and _is_registration_proxy_transport_failure(exc)
            )
            raise
        human_delay("navigate")
        _page_warmup(driver, reason="login_page")
        report_job_progress("page", "success", "登录页已打开，待确认邮箱入口")
        logger.info("[Roxy注册] 登录页已打开，开始确认邮箱入口")
        _maybe_accept(driver)
    _check_manual_stop()

    def _report_email_progress(phase: str, detail: str) -> None:
        report_job_progress("submit_email", "skipped" if phase == "skipped" else "running", detail)
        if phase in {"pending", "fallback"}:
            report_job_progress("auth_redirect", "running", "正在确认密码页、邮箱验证码页或登录态")

    def _mark_email_submitted() -> None:
        report_job_progress("submit_email", "success", "邮箱认证已确认进入下一步")

    def _handoff_current_cf_challenge() -> None:
        if request.route_recovery_enabled and route_observer is not None:
            route_observer.raise_if_failed(driver)
        if native_signin_diagnostics.failure_diagnostic(driver):
            raise _EmailSubmissionUnknown("email_submit_unconfirmed: 当前认证入口尚未进入下一步，交回服务层检查线路")

    if verified_resume_session:
        next_state = "authenticated"
        report_job_progress("submit_email", "skipped", "原环境登录态已核验，无需再次提交邮箱")
        report_job_progress("auth_redirect", "skipped", "原环境登录态已核验，无需认证跳转")
    elif retained_state:
        next_state = {
            PageState.PASSWORD_CREATE: "password",
            PageState.PASSWORD_LOGIN: "login_password",
            PageState.OTP_EMAIL: "otp",
            PageState.PROFILE: "profile",
            PageState.MFA_TOTP: "totp",
            PageState.EMAIL_VERIFIED: "email_verified",
        }.get(retained_state.page_state, "authenticated")
        report_job_progress("submit_email", "skipped", "已核验原任务窗口，无需再次提交邮箱")
        report_job_progress("auth_redirect", "skipped", "从原窗口当前认证步骤继续")
    else:
        report_job_progress("submit_email", "running", "正在等待可见的邮箱输入框")
        state.email_entry_waiting = True
        next_state = submit_email(
            driver,
            email,
            attempts=3,
            on_submitted=_mark_email_submitted,
            allow_login_password=resume_scope,
            on_progress=_report_email_progress,
            **{"on_page_observed": lambda snapshot: _observe_registration_email_page(driver, snapshot)}
            if request.local_browser
            else {},
            **{"recover_late_email_entry": True} if request.local_browser else {},
            **{"on_before_recovery": _handoff_current_cf_challenge}
            if (request.cf_rotation_allowed or request.route_recovery_enabled)
            and current_lease_route_verified
            and (not request.has_retained_browser)
            and (native_signin_diagnostics is not None)
            else {},
        )
        state.email_entry_waiting = False
    state.remote_identity = classify_registration_identity(next_state)
    _check_manual_stop()
    if not verified_resume_session and (not retained_state):
        report_job_progress("auth_redirect", "success", f"已进入认证下一步：{next_state}")
    password_stage_expected = password_required or bool(state.existing_password) or request.local_browser
    if verified_resume_session:
        password_progress_detail = "原环境登录态已核验，保留原密码且无需再次提交"
    elif state.existing_password:
        password_progress_detail = "正在继续待验证账号的登录流程"
    elif password_required:
        password_progress_detail = "正在创建恢复候选密码，之后核验同邮箱登录态"
    else:
        password_progress_detail = "正在检查当前页面提供的密码入口"
    report_job_progress(
        "login_password",
        "running" if password_stage_expected and (not verified_resume_session) else "skipped",
        password_progress_detail,
    )
    password_submitted_this_run = False
    password_prepared_this_run = False
    previous_password_receipts = password_receipt_ids(driver) if request.local_browser else frozenset()
    if route_observer is not None:
        route_observer.begin_stage(driver, "password")

    def _checkpoint_prepared_password(password: str) -> None:
        """在异步密码点击前保存原密码，供同一 Attempt 续跑。"""
        nonlocal password_prepared_this_run
        receipt = getattr(driver, "_browser_submission_receipt", None)
        if (
            route_state is not None
            and route_state.has_unknown_identity_write
            and (getattr(receipt, "stage", "") == "password_create")
        ):
            raise RuntimeError(
                "request_unknown: route_password_create_not_replayable: 原密码创建结果未确认，恢复只允许原候选登录"
            )
        password_prepared_this_run = True
        try:
            save_protocol_password_checkpoint(
                email=email, password=password, state="prepared", proxy=proxy, email_source=selected_email_source
            )
        except Exception:
            context = getattr(driver, "_registration_fact_context", {}) or {}
            if context.get("attempt_id") is not None or not getattr(driver, "_registration_legacy_compat", False):
                raise

    def _checkpoint_submitted_password(password: str) -> None:
        nonlocal password_submitted_this_run
        password_submitted_this_run = True
        try:
            save_protocol_password_checkpoint(
                email=email, password=password, state="started", proxy=proxy, email_source=selected_email_source
            )
        except Exception:
            context = getattr(driver, "_registration_fact_context", {}) or {}
            if context.get("attempt_id") is not None or not getattr(driver, "_registration_legacy_compat", False):
                raise

    try:
        retained_otp_can_try_password = bool(
            request.local_browser
            and retained_state
            and (retained_state.page_state == PageState.OTP_EMAIL)
            and (retained_state.pending_otp is None)
            and (not password_recovered_before_resume)
        )
        if verified_resume_session or (
            retained_state
            and retained_state.page_state not in {PageState.PASSWORD_CREATE, PageState.PASSWORD_LOGIN}
            and (not retained_otp_can_try_password)
        ):
            state.openai_password = state.existing_password
        else:
            state.openai_password = (
                _fill_password_page_if_present(
                    driver,
                    email,
                    timeout=120,
                    existing_password=state.existing_password,
                    on_password_prepared=_checkpoint_prepared_password,
                    on_password_submitted=_checkpoint_submitted_password,
                    **{"prefer_saved_password_entry": True, "password_required": password_required}
                    if request.local_browser
                    else {},
                )
                or state.existing_password
            )
    except (PasswordPageError, _PasswordTransitionTimeout) as exc:
        if not (resume_scope and request.local_browser and _wait_for_current_password_reset_required(driver)):
            if isinstance(exc, _PasswordTransitionTimeout):
                report_job_progress("login_password", "failed", "已触发密码提交操作，远端结果仍待确认")
            raise
        report_job_progress("login_password", "running", "本次密码验证明确要求重置，正在恢复原账号密码")
        state.existing_password = state.openai_password = _recover_roxy_password(
            driver, email, state.password_recovery, email_source=selected_email_source, totp_secret=existing_totp_secret
        )
        otp_after_ts = getattr(driver, "_registration_otp_after_ts", None)
        retained_state = None
        password_submitted_this_run = True
    except Exception as exc:
        if password_stage_expected and (not verified_resume_session):
            report_job_progress("login_password", "failed", f"账号密码处理失败: {type(exc).__name__}: {str(exc)[:180]}")
        raise
    else:
        if password_stage_expected and (not verified_resume_session):
            if request.local_browser:
                evidence = password_evidence(driver, exclude_ids=previous_password_receipts)
                credential_check = evidence["credential_check"]
                if credential_check in {"verified", "accepted"}:
                    password_result_state = "running"
                    password_result_detail = (
                        "本次密码登录验证已通过，等待取得同邮箱 Token"
                        if credential_check == "verified"
                        else "本次创建请求已被接受，密码仍作为恢复候选等待完成认证"
                    )
                elif credential_check in {"rejected", "unknown"}:
                    password_result_state = "failed"
                    password_result_detail = (
                        "远端已明确拒绝本次密码"
                        if credential_check == "rejected"
                        else "本次密码已提交，远端结果仍未确认"
                    )
                else:
                    password_result_state = "skipped"
                    password_result_detail = "本次未提交或未取得密码验证回执；本地保存密码不代表远端已验证"
            elif password_submitted_this_run:
                password_result_state = "success"
                password_result_detail = "账号密码已提交并进入下一步"
            elif state.existing_password and state.openai_password and _is_email_verification_page(driver):
                password_result_state = "success"
                password_result_detail = "已复用待验证账号的密码信息；本次直接进入邮箱验证码，未重新提交密码"
            else:
                password_result_state = "success" if state.openai_password else "skipped"
                password_result_detail = (
                    "当前认证流先验证邮箱，但密码流程未返回新密码"
                    if _is_email_verification_page(driver)
                    else "密码流程未返回新密码"
                )
            report_job_progress("login_password", password_result_state, password_result_detail)
    if not verified_resume_session and (
        password_submitted_this_run
        or password_evidence(driver, exclude_ids=previous_password_receipts)["credential_check"]
        in {"verified", "accepted"}
    ):
        state.auth_challenge_chain.append("password")
    if not verified_resume_session and state.openai_password and (state.account_id is None):
        state.account_id = _save_pending_email_verification_checkpoint(
            email=email, openai_password=state.openai_password
        )
        report_registered_account(state.account_id)
        state.create_acknowledged = True
        logger.info(
            "[Roxy注册] 恢复候选已保存，继续核验账号和密码：id=%s email=%s resume=%s",
            state.account_id,
            email,
            bool(state.existing_password),
        )
    resume_login_state = ""
    otp_after_ts = getattr(driver, "_registration_otp_after_ts", otp_after_ts)
    if (
        state.existing_password
        and (not verified_resume_session)
        and (not retained_state)
        and _registration_profile_form_ready(driver)
    ):
        resume_login_state = "advanced"
        logger.info("[Roxy注册] 已核验可见资料表单，继续原注册资料阶段")
    elif state.existing_password and (not verified_resume_session) and (not retained_state):
        resume_kwargs = {"timeout": 45}
        if password_submitted_this_run:
            resume_kwargs["password_already_submitted"] = True
        if selected_email_source is not None:
            resume_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                address, email_source=selected_email_source, **kwargs
            )
        resume_login_state = complete_openai_login_challenge(
            driver, email, state.existing_password, str(existing_totp_secret or ""), **resume_kwargs
        )
        logger.info("[Roxy注册] 待验证账号公共登录状态机完成：email=%s state=%s", email, resume_login_state)
    _check_manual_stop()
    if not verified_resume_session:
        report_job_progress("email_otp", "running", "正在等待并验证邮箱验证码")
        report_job_otp_evidence(
            request_kind="resume_login" if state.existing_password else "initial",
            ui_ack="unconfirmed",
            detail="页面已进入邮箱验证码步骤，但仅凭页面状态不能确认邮件请求已被接受",
        )
    last_otp_ui_ack = "unconfirmed"
    current_otp = otp_code
    submitted_otps = getattr(driver, "_registration_otp_tracker", None) if resume_metadata else None
    if not isinstance(submitted_otps, _OtpAttemptTracker):
        submitted_otps = _OtpAttemptTracker()
    driver._registration_otp_tracker = submitted_otps
    max_otp_attempts = 3
    otp_total_wait = callbacks.otp_total_wait()
    otp_budget = StageBudget.start(otp_total_wait)
    if route_observer is not None:
        route_observer.begin_stage(driver, "otp")
    otp_wait_deadline = otp_budget.deadline
    otp_already_complete = (
        bool(verified_resume_session)
        or bool(retained_state and retained_state.page_state in {PageState.PROFILE, PageState.EMAIL_VERIFIED})
        or resume_login_state == "advanced"
        or _has_access_token(driver)
    )
    if retained_state and retained_state.pending_otp:
        outcome = _wait_after_email_otp_submit(
            driver,
            timeout=60,
            budget=otp_budget,
            expected_email=email,
            **{"monitor_otp_network": True} if request.local_browser else {},
        )
        if outcome == "session_expired":
            raise RuntimeError(
                "request_unknown: auth_session_unavailable: 原验证码页认证会话不可用，已保留原 Attempt，需沿用原身份重新登录"
            )
        if outcome not in {"accepted", "email_verified", "totp_required"}:
            raise RuntimeError(
                "request_unknown: otp_request_unconfirmed: 原验证码提交仍未确认，已保留原窗口，未重新填码或重发"
            )
        otp_budget.require("原验证码提交再次核验")
        verified_resume_session = _read_registration_resume_session(driver, email, budget=otp_budget)
        retained_state = prepare_retained_resume(
            driver,
            email=email,
            existing_password=state.existing_password,
            facts=context,
            verified_session=verified_resume_session,
            otp_after_ts=getattr(driver, "_registration_otp_after_ts", otp_after_ts),
        )
        if retained_state.pending_otp is not None or retained_state.page_state not in {
            PageState.PROFILE,
            PageState.EMAIL_VERIFIED,
            PageState.MFA_TOTP,
            PageState.AUTHENTICATED,
        }:
            raise RuntimeError("request_unknown: 原验证码提交未能再次核验，已保留原窗口")
        if retained_state.page_state == PageState.MFA_TOTP:
            _complete_registration_totp_after_email_otp(
                driver, email, state.existing_password, existing_totp_secret, budget=otp_budget
            )
            state.remote_identity = "existing"
            state.auth_challenge_chain.append("totp")
        otp_already_complete = True
        state.auth_challenge_chain.append("email_otp")
    for otp_attempt in range(1, max_otp_attempts + 1):
        if otp_already_complete:
            break
        ready_outcome = _wait_email_otp_page_ready(driver, budget=otp_budget)
        if ready_outcome in {"stuck", "session_expired"}:
            failure_code = (
                "auth_session_unavailable" if ready_outcome == "session_expired" else "otp_request_unconfirmed"
            )
            failure_detail = (
                "验证码页认证会话不可用；保留原 Attempt，需沿用原身份重新登录，未填码或追加重发"
                if ready_outcome == "session_expired"
                else "验证码页表单未就绪，受限恢复后仍未确认；保留原 Attempt，本轮未追加重发"
            )
            latest_submission = getattr(driver, "_browser_submission_receipt", None)
            if (
                isinstance(latest_submission, BrowserSubmissionReceipt)
                and latest_submission.endpoint_kind == "otp_resend"
            ):
                status = latest_submission.http_status
                failure_detail += (
                    f"；此前已尝试重发，接口 HTTP {status}"
                    if status is not None
                    else "；此前已尝试重发，接口结果未确认"
                )
            report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
            report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
            raise RuntimeError(f"{failure_code}: {failure_detail}")
        if ready_outcome == "totp_required":
            state.remote_identity = "existing"
            post_otp_state = _complete_registration_totp_after_email_otp(
                driver,
                email,
                state.existing_password,
                existing_totp_secret,
                timeout=min(45, otp_budget.require("邮箱验证后 TOTP")),
                budget=otp_budget,
            )
            if "email_otp" not in state.auth_challenge_chain:
                state.auth_challenge_chain.append("email_otp")
            if "totp" not in state.auth_challenge_chain:
                state.auth_challenge_chain.append("totp")
            resume_login_state = "advanced"
            break
        if ready_outcome in ("accepted", "email_verified"):
            if "email_otp" not in state.auth_challenge_chain:
                state.auth_challenge_chain.append("email_otp")
            break
        if current_otp is None:
            if otp_after_ts is None:
                raise RuntimeError("request_unknown: 原验证码邮件时间未能核验，已保留原窗口，未收码或重发")
            logger.info("[Roxy注册][OTP] 等待验证码：%s（第 %s/%s 次）", email, otp_attempt, max_otp_attempts)
            try:
                attempt_wait = _registration_otp_attempt_wait_seconds(otp_wait_deadline, otp_attempt, max_otp_attempts)
                otp_budget.require("email OTP")
                if attempt_wait <= 0:
                    raise TimeoutError(f"邮箱验证码总等待已达到 {otp_total_wait}s")
                otp_kwargs = {"after_ts": otp_after_ts, "max_wait": attempt_wait}
                if selected_email_source is not None:
                    otp_kwargs["email_source"] = selected_email_source
                current_otp = wait_for_otp(email, budget=otp_budget, **otp_kwargs)
            except Exception as exc:
                if otp_attempt >= max_otp_attempts:
                    failure_code, failure_detail = _classify_otp_wait_failure(exc, last_ui_ack=last_otp_ui_ack)
                    report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                    report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                    raise RuntimeError(f"{failure_code}: {failure_detail}") from exc
                logger.warning(
                    "[Roxy注册][OTP] 单轮等待结束仍未收到新验证码，重新发送后只等待新邮件（下一轮 %s/%s）：%s: %s",
                    otp_attempt + 1,
                    max_otp_attempts,
                    type(exc).__name__,
                    str(exc)[:180],
                )
                try:
                    resend_result = _resend_email_otp_after_failure(
                        driver, reason="等待邮箱验证码超时/未收到新验证码", budget=otp_budget
                    )
                except Exception as resend_exc:
                    failure_code = "otp_request_unconfirmed"
                    failure_detail = "验证码重发控件未能完成或缺少确认；不能断言服务端已经发信"
                    report_job_otp_evidence(
                        request_kind="resend", ui_ack="rejected", detail=failure_detail, failure_code=failure_code
                    )
                    report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                    raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
                otp_after_ts = float(resend_result.get("requested_after_ts") or callbacks.wall_time())
                driver._registration_otp_after_ts = otp_after_ts
                last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
                report_job_otp_evidence(
                    request_kind="resend", ui_ack=last_otp_ui_ack, detail="等待超时后请求重新发送验证码"
                )
                human_delay("api", budget=otp_budget)
                current_otp = None
                continue
        if not submitted_otps.accept(current_otp):
            failure_detail = "收码器返回了本次运行已经提交过的验证码，拒绝重复提交"
            logger.warning("[Roxy注册][OTP] %s", failure_detail)
            if otp_attempt >= max_otp_attempts:
                failure_code = "otp_reused_after_resend"
                report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}")
            try:
                resend_result = _resend_email_otp_after_failure(driver, reason=failure_detail, budget=otp_budget)
            except Exception as resend_exc:
                failure_code = "otp_request_unconfirmed"
                failure_detail = "重复验证码已拒绝，但验证码重发控件未能完成或缺少确认"
                report_job_otp_evidence(
                    request_kind="resend", ui_ack="rejected", detail=failure_detail, failure_code=failure_code
                )
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
            otp_after_ts = float(resend_result.get("requested_after_ts") or callbacks.wall_time())
            driver._registration_otp_after_ts = otp_after_ts
            last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
            report_job_otp_evidence(
                request_kind="resend", ui_ack=last_otp_ui_ack, detail="拒绝重复验证码后请求重新发送"
            )
            human_delay("api", budget=otp_budget)
            current_otp = None
            continue
        logger.info("[Roxy注册][OTP] 已收到验证码")
        outcome, otp_submission = _submit_registration_email_otp(
            driver,
            current_otp,
            budget=otp_budget,
            expected_email=email,
            **{"monitor_otp_network": True} if request.local_browser else {},
            on_refresh_retry=lambda: report_job_progress(
                "email_otp", "running", "刷新后仍在验证码页，正在使用上次验证码再次验证"
            ),
        )
        if outcome in ("accepted", "email_verified", "totp_required"):
            record_browser_submission_fact(driver, "confirmed", receipt=otp_submission, result="success")
        elif outcome == "invalid":
            record_browser_submission_fact(driver, "rejected", receipt=otp_submission, result="failure")
        elif outcome in {"stuck", "session_expired"}:
            record_browser_submission_fact(
                driver,
                "unknown",
                receipt=otp_submission,
                result="unknown" if outcome == "session_expired" else "timeout",
            )
            failure_code = "auth_session_unavailable" if outcome == "session_expired" else "otp_request_unconfirmed"
            failure_detail = (
                "验证码提交后的认证会话不可用；保留原提交和原 Attempt，需沿用原身份重新登录，未追加提交或重发"
                if outcome == "session_expired"
                else "验证码提交可能已派发，但 60 秒内未确认结果；保留原 Attempt，未自动重发"
            )
            report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
            report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
            raise RuntimeError(f"{failure_code}: {failure_detail}")
        if outcome == "totp_required":
            state.remote_identity = "existing"
            post_otp_state = _complete_registration_totp_after_email_otp(
                driver, email, state.existing_password, existing_totp_secret, budget=otp_budget
            )
            if "email_otp" not in state.auth_challenge_chain:
                state.auth_challenge_chain.append("email_otp")
            if "totp" not in state.auth_challenge_chain:
                state.auth_challenge_chain.append("totp")
            resume_login_state = "advanced"
            break
        if outcome in ("accepted", "email_verified"):
            if "email_otp" not in state.auth_challenge_chain:
                state.auth_challenge_chain.append("email_otp")
            break
        if otp_attempt >= max_otp_attempts:
            failure_code = "otp_invalid_or_expired"
            failure_detail = "已取得并提交验证码，但页面未接受或验证码已过期"
            report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
            report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
            raise RuntimeError(f"{failure_code}: {failure_detail}")
        logger.warning(
            "[Roxy注册][OTP] 验证码错误/过期，准备重新发送并重新获取验证码（%s/%s）", otp_attempt + 1, max_otp_attempts
        )
        try:
            resend_result = _resend_email_otp_after_failure(
                driver, reason="邮箱验证码提交后页面无效或卡住", budget=otp_budget
            )
        except Exception as resend_exc:
            failure_code = "otp_request_unconfirmed"
            failure_detail = "验证码重发控件未能完成或缺少确认；不能断言服务端已经发信"
            report_job_otp_evidence(
                request_kind="resend", ui_ack="rejected", detail=failure_detail, failure_code=failure_code
            )
            report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
            raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
        otp_after_ts = float(resend_result.get("requested_after_ts") or callbacks.wall_time())
        driver._registration_otp_after_ts = otp_after_ts
        last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
        report_job_otp_evidence(
            request_kind="resend", ui_ack=last_otp_ui_ack, detail="验证码无效或页面未推进后请求重新发送"
        )
        human_delay("api", budget=otp_budget)
        current_otp = None
    report_job_progress(
        "email_otp",
        "skipped" if otp_already_complete else "success",
        "已有登录态，无需再次验证邮箱" if otp_already_complete else "邮箱验证码已通过",
    )
    _check_manual_stop()
    if (
        not verified_resume_session
        and route_state is not None
        and route_state.has_unknown_identity_write
        and (route_state.unknown_profile_write or route_state.failed_operation == "profile_submit")
    ):
        if route_observer is not None:
            route_observer.begin_stage(driver, "session")
        session_url = "https://chatgpt.com/api/auth/session"
        try:
            _safe_get(driver, session_url, timeout=30, attempts=1, accept_hosts=("chatgpt.com",))
        except Exception as exc:
            if route_observer is not None:
                route_observer.call_failed(driver, "GET", session_url, exc)
            raise
        verified_resume_session = _read_registration_resume_session(driver, email)
        if not verified_resume_session:
            raise RuntimeError(
                "request_unknown: route_profile_result_unconfirmed: 原资料写入结果未明，原身份登录后仍无完整会话"
            )
    if route_observer is not None:
        route_observer.begin_stage(driver, "profile")
    profile_submitted = False
    if not verified_resume_session:
        report_job_progress(
            "profile", "running", "正在核验原账号登录态" if rejected_existing_profile else "正在填写账号资料"
        )
        logger.info("[Roxy注册] 开始等待资料页/登录态")
        if rejected_existing_profile:
            state.existing_profile_reconciliation = True
            verified_resume_session = _reconcile_existing_profile_session(driver, email)
            state.existing_profile_unverified = False
            state.existing_profile_reconciliation = False
        else:
            try:
                profile_submitted = complete_profile(
                    driver, name, birthday, timeout=60, expected_email=email, transition_timeout=90
                )
            except ProfileAccountAlreadyExistsError:
                state.existing_profile_unverified = True
                state.existing_profile_reconciliation = True
                verified_resume_session = _reconcile_existing_profile_session(driver, email)
                state.existing_profile_unverified = False
                state.existing_profile_reconciliation = False
    if profile_submitted:
        state.remote_identity = "new_candidate"
        state.create_acknowledged = True
        human_delay("post_auth", minimum=0.25, maximum=0.8)
        report_job_progress("profile", "success", "账号资料已提交")
    else:
        state.remote_identity = "existing"
        report_job_progress("profile", "skipped", "已有登录态，无需填写资料")
    report_job_progress("token", "running", "正在等待登录态并获取 Token")
    logger.info("[Roxy注册] 等待 ChatGPT 跳转并写入 session/accessToken")
    _check_manual_stop()
    token_budget = StageBudget.start(120)
    if route_observer is not None:
        route_observer.begin_stage(driver, "session")
    lightweight_post_auth = callbacks.lightweight_post_auth()
    session_info = verified_resume_session or _fetch_chatgpt_session(
        driver, timeout=120, budget=token_budget, prefer_homepage=not lightweight_post_auth
    )
    _validate_registration_session_identity(session_info, email)
    state.access_token = session_info["accessToken"]
    state.password_confirmed = _registration_password_confirmed_after_token(
        driver, email=email, password=state.openai_password, previous_receipts=previous_password_receipts
    )
    if state.password_recovery is not None:
        state.password_confirmed = callbacks.password_recovery_confirms(
            state.password_recovery, state.openai_password, state.password_confirmed
        )
    if state.password_confirmed and "password" not in state.auth_challenge_chain:
        state.auth_challenge_chain.append("password")
    if state.password_confirmed:
        report_job_progress("login_password", "success", "已取得同邮箱 Token，并确认当前账号密码有效")
    logger.info("[Roxy注册] 已拿到 accessToken：%s", email)
    return RoxyAuthenticationResult(
        session_info=session_info,
        lightweight_post_auth=lightweight_post_auth,
        token_budget=token_budget,
    )
