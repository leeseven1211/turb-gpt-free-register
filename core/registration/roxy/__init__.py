# -*- coding: utf-8 -*-
"""通过 RoxyBrowser 指纹浏览器 + Selenium 执行 ChatGPT 注册。"""
from __future__ import annotations

import logging
import copy
import json
import math
import random
import re
import string
import threading
import time
import uuid
from types import SimpleNamespace
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from config import codex as _codex_cfg
from config import twofa as _twofa_cfg
from core.accounts.export import setup_2fa_protocol
from core.email.provider import wait_for_otp, resolve_email_source, validate_email_source
from core.auth.humanize import delay as human_delay
from core.network.response_diagnostics import auth_submission_endpoint, safe_response_headers
from core.auth.protocol.openai_auth import AccountUnusableError
from core.browser.roxy.client import RoxyBrowserClient, RoxyOpenResult, RoxyProfileQuotaExceeded
from core.auth.protocol.session import BrowserSession
from core.auth.state_machine import PageState, StageBudget, StageTimeout, can_resend_otp, classify_page
from core.auth.browser.auth_context import AuthExecutionContext
from core.auth.page_errors import AuthPageError, auth_page_error
from core.auth.browser.email_otp import EmailOtpNetworkError, _EmailSubmissionUnknown
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.auth.browser.submission_recovery import diagnostics_for, log_submission_diagnostics
from core.auth.browser.selenium_dom import _dispatch_trusted_click
from core.registration.retained_browser import (
    persist_browser_resume_context, recover_attempt_failed_browser,
    recover_bound_failed_browser, retain_failed_browser, take_failed_browser,
)
from core.registration.retained_resume import (
    _is_native_resume_start_page, _page_state as _retained_page_state,
    RetainedResumeState, has_rejected_existing_profile, prepare_retained_resume,
)
from core.registration.route_recovery import current_route_recovery as _route_recovery_callback
from core.registration.roxy.route_recovery import (
    RoxyRouteFailureObserver, RoxyRouteFailureSignal, make_recovery_state,
    RegistrationTwofaSession, continue_browser_twofa, record_current_refusal, validated_recovery_state,
)
from core.auth.browser.password_auth import PasswordPageError, ProfileAccountAlreadyExistsError
from core.auth.browser.password_evidence import password_evidence, password_receipt_ids
from core.accounts.password_evidence import registration_password_extra
from core.auth.challenge import MfaSecretMissingError, PasswordRejectedError, PasswordSetupNotReadyError, RemoteExistingAccountError, auth_result_for_registration, classify_registration_identity

logger = logging.getLogger(__name__)


def _is_native_signin_page(url: object) -> bool:
    try:
        parsed = urlsplit(str(url or ""))
        return (parsed.scheme == "https" and parsed.hostname == "chatgpt.com"
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and parsed.path == "/auth/login_with")
    except ValueError:
        return False


class _NativeSigninFailureDiagnostics:
    """只读关联当前原生登录导航，不把旧窗口的挑战归给本轮邮箱等待。"""

    def __init__(self, shared_diagnostics, *, include_form_entry: bool = False) -> None:
        self.shared_diagnostics = shared_diagnostics
        self.include_form_entry = include_form_entry
        self.lock = threading.Lock()
        self.active = False
        self.target = ""
        self.started = None
        self.latest = None

    def _is_entry(self, url) -> bool:
        if _is_native_signin_page(url):
            return True
        try:
            parsed = urlsplit(str(url or ''))
            return (self.include_form_entry and parsed.scheme == 'https'
                    and parsed.hostname == 'chatgpt.com' and parsed.port in (None, 443)
                    and not parsed.username and not parsed.password and parsed.path == '/auth/login')
        except ValueError:
            return False

    def begin_navigation(self, driver) -> None:
        try:
            handle = driver.current_window_handle
            target = handle.removeprefix("CDwindow-") if isinstance(handle, str) else ""
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", target):
                target = ""
        except Exception:
            target = ""
        with self.lock:
            self.active = bool(target)
            self.target = target
            self.started = None
            self.latest = None

    def observe_network(self, record, *, phase: str) -> None:
        self.shared_diagnostics.observe_network(record, phase=phase)
        if not isinstance(record, dict):
            return
        target = str(record.get("target_id") or "")
        request = str(record.get("request_id") or "")
        started = record.get("started_monotonic")
        valid_start = (isinstance(started, (int, float)) and not isinstance(started, bool)
                       and math.isfinite(started))
        with self.lock:
            if not self.active or target != self.target:
                return
            if phase == "request" and record.get("resource_type") == "Document" and record.get("method") == "GET":
                if self._is_entry(record.get("url")) and target and valid_start:
                    self.started, self.latest = started, None
                else:
                    self.started, self.latest = None, None
                return
            if self.started is None or not request:
                return
            key = (target, request, record.get("redirect_index", 0))
            endpoint = auth_submission_endpoint(record.get("url"))
            is_auth_request = endpoint and (record.get('method') == 'POST' or (
                self.include_form_entry and endpoint == 'nextauth_csrf' and record.get('method') == 'GET'))
            if phase == "request" and is_auth_request:
                if not valid_start or started < self.started:
                    return
                # 后续认证 POST 一旦开始，旧失败就不再解释当前等待；迟到响应也
                # 只能更新同一请求，不能盖过新请求的成功或尚未确认状态。
                self.latest = {"key": key, "endpoint": endpoint, "status": None, "challenge": False}
            elif phase in {"response", "complete"} and self.latest and key == self.latest["key"]:
                # collector 结束请求后会移除开始时间；补充头只能凭已接纳的
                # 当前请求及重定向代际更新，不能据此建立新的认证请求范围。
                status = record.get("status")
                if isinstance(status, (int, float)) and not isinstance(status, bool) and 100 <= status <= 599:
                    self.latest["status"] = status
                headers = safe_response_headers(record.get("response_headers"))
                if "cf-mitigated" in headers:
                    self.latest["challenge"] = headers["cf-mitigated"] == "challenge"

    def failure_diagnostic(self, driver) -> dict:
        try:
            if not self._is_entry(driver.current_url):
                return {}
            handle = driver.current_window_handle
            target = handle.removeprefix('CDwindow-') if isinstance(handle, str) else ''
        except Exception:
            return {}
        with self.lock:
            endpoints = {'nextauth_signin', 'nextauth_csrf'} if self.include_form_entry else {'nextauth_signin'}
            if not (self.active and target == self.target and self.latest and self.latest["endpoint"] in endpoints
                    and self.latest["status"] == 403 and self.latest["challenge"]):
                return {}
            endpoint = self.latest['endpoint']
        return {"cause_code": "auth_cloudflare_challenge", "cause_diagnostics": {
            "http_status": 403, "auth_endpoint": endpoint, "response_kind": "cloudflare_challenge",
        }}


def _receipt_accepts_submission_endpoint(receipt, endpoint_kind: str) -> bool:
    expected = str(getattr(receipt, "endpoint_kind", "") or "")
    endpoint_kind = str(endpoint_kind or "")
    if expected == "email_submit":
        # UI 邮箱点击实际发送 NextAuth signin；CSRF GET 只是前置读取，
        # 不能把它的成功或失败写成这次邮箱 POST 的回执。
        return endpoint_kind in {"email_submit", "nextauth_signin"}
    return bool(expected and expected == endpoint_kind)


def _unique_submission_receipt_for_endpoint(driver, endpoint_kind: str):
    """仅在本 Run 存在唯一候选时把 CDP request 关联到提交事实。"""
    history = getattr(driver, "_browser_submission_receipts", None)
    if not isinstance(history, list):
        history = []
    candidates = [
        item for item in history
        if getattr(item, "phase", "") not in {"prepared", "not_dispatched"}
        and _receipt_accepts_submission_endpoint(item, endpoint_kind)
        and (endpoint_kind != "password_submit" or getattr(driver, "_browser_submission_receipt", None) is None
             or item is driver._browser_submission_receipt)
        and not (endpoint_kind == "otp_resend" and getattr(item, "phase", "") == "confirmed"
                 and getattr(item, "request_binding", None) is not None)
    ]
    # 同 target/endpoint 的迟到 request 无法证明属于哪一次提交时，宁可不
    # 补 request_fact，页面回执仍保留原有的安全结论。
    return candidates[0] if len(candidates) == 1 else None


def _submission_response_fact(endpoint_kind: str, status: object) -> tuple[str, str]:
    """把已绑定响应转换为保守事实，不把 CSRF 失败冒充 signin 拒绝。"""
    try:
        code = int(status or 0)
    except (TypeError, ValueError):
        code = 0
    if endpoint_kind == "nextauth_csrf":
        return "response_observed", ""
    if code in {400, 401}:
        return "rejected", "failure"
    if endpoint_kind == "nextauth_signin" and code == 403:
        # 挑战拦截属于本次请求失败，不证明账号或后续同身份登录被永久拒绝。
        return "response_observed", "failure"
    if 100 <= code < 400:
        return "response_observed", "success"
    return "response_observed", ""


def _password_reset_required_for_current_submission(driver) -> bool:
    """只接纳当前密码派发页、本次 requestId 明确要求重置的响应。"""
    receipt = getattr(driver, "_browser_submission_receipt", None)
    if not isinstance(receipt, BrowserSubmissionReceipt):
        return False
    binding = receipt.request_binding
    return bool(
        receipt.kind == "resume_login" and receipt.stage == "login_password"
        and receipt.endpoint_kind == "password_submit" and receipt.phase == "rejected"
        and receipt.http_method == "POST" and type(receipt.http_status) is int and receipt.http_status == 401
        and receipt.dispatch_target_id and binding and binding[0] == receipt.dispatch_target_id
        and binding == receipt.response_binding and receipt.auth_error.get("code") == "password_reset_required"
    )


def _wait_for_current_password_reset_required(driver) -> bool:
    """在原密码提交预算内，等待最多一轮采集正文延迟；不派发任何新动作。"""
    if _password_reset_required_for_current_submission(driver):
        return True
    receipt = getattr(driver, "_browser_submission_receipt", None)
    if not (isinstance(receipt, BrowserSubmissionReceipt)
            and receipt.kind == "resume_login" and receipt.stage == "login_password"
            and receipt.endpoint_kind == "password_submit" and receipt.http_method == "POST"
            and receipt.phase in {"dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "rejected", "unknown"}
            and receipt.dispatch_target_id and receipt.dispatch_started_at is not None):
        return False
    deadline = min(time.monotonic() + 2.2, receipt.dispatch_started_at + _password_transition_timeout_seconds())
    while time.monotonic() < deadline:
        _check_manual_stop()
        if getattr(driver, "_browser_submission_receipt", None) is not receipt:
            return False
        if _password_reset_required_for_current_submission(driver):
            return True
        if receipt.request_binding is not None and receipt.request_binding == receipt.response_binding:
            return False
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    return _password_reset_required_for_current_submission(driver)


def _registration_password_recovery_owner(email: str, facts: dict) -> dict | None:
    """把本次注册执行映射到操作 Run，保留两套独立的执行标识。"""
    from core import db
    from core.storage.operations import store as operations

    if not all(facts.get(key) for key in ("attempt_id", "run_id", "execution_id", "job_id")):
        raise RuntimeError("password_recovery_owner_missing: 当前注册执行身份不完整")
    account = db.get_account_by_email(email) or {}
    if not account.get("id"):
        # 尚未形成本地账号的旧续跑不具备换密同步目标，保留原认证行为。
        return None
    job_id = int(facts["job_id"])
    progress = operations.get_registration_progress([job_id]).get(job_id) or {}
    operation_run_id = progress.get("operation_run_id")
    operation_run = operations.get_run(int(operation_run_id)) if operation_run_id else None
    if not operation_run or not operation_run.get("execution_id"):
        raise RuntimeError("password_recovery_owner_missing: 原账号与当前操作 Run 无法核验")
    return {
        "email": email, "account_id": int(account["id"]), "purpose": "registration",
        "operation_run_id": int(operation_run_id),
        "operation_execution_id": str(operation_run["execution_id"]), "operation_lease_token": None,
        "attempt_id": int(facts["attempt_id"]), "registration_run_id": int(facts["run_id"]),
        "registration_execution_id": str(facts["execution_id"]),
    }


def _registration_password_recovery_session(email: str, facts: dict):
    # 兼容不带真实 Run 的旧内部调用；这些入口无法获得自动重置资格。
    if not all(facts.get(key) for key in ("attempt_id", "run_id", "execution_id", "job_id")):
        return None
    from core.auth.browser.password_recovery import PasswordRecoverySession

    owner = _registration_password_recovery_owner(email, facts)
    return PasswordRecoverySession(**owner) if owner is not None else None


def _recover_roxy_password(
    driver, email: str, recovery, *, email_source: str | None, totp_secret: str | None = None,
) -> str:
    """恢复对象确认账号和 Attempt 同步后，才把新密码交回原注册流程。"""
    if recovery is None:
        raise RuntimeError("password_recovery_owner_missing: 当前执行没有可核验的密码恢复归属")
    from core.codex.roxy.oauth import _reset_password_via_email

    otp_provider = lambda address, **kwargs: wait_for_otp(address, email_source=email_source, **kwargs)
    _reset_password_via_email(
        driver, email, otp_provider, recovery=recovery, allow_profile_handoff=True,
        totp_secret=str(totp_secret or ""),
    )
    checkpoint = recovery.checkpoint
    if checkpoint is None or checkpoint.state != "confirmed":
        raise RuntimeError("password_recovery_unconfirmed: 新密码尚未获得明确认证确认，已保留恢复检查点")
    return checkpoint.password


def _make_submission_observer(driver, *, monitor_otp_network: bool = False):
    from core.kernels.browser.roxy.registration.submissions import SubmissionCallbacks, make_submission_observer

    return make_submission_observer(
        driver, monitor_otp_network=monitor_otp_network,
        callbacks=SubmissionCallbacks(
            record_submission=lambda *args, **kwargs: record_browser_submission_fact(*args, **kwargs),
            accepts_endpoint=lambda *args, **kwargs: _receipt_accepts_submission_endpoint(*args, **kwargs),
            unique_receipt=lambda *args, **kwargs: _unique_submission_receipt_for_endpoint(*args, **kwargs),
            response_fact=lambda *args, **kwargs: _submission_response_fact(*args, **kwargs),
            wall_time=lambda: time.time(),
        ),
    )


# These failures happen before a local account checkpoint exists. Keeping the
# temporary Profile for them only consumes a Roxy slot; failures after a
# password/OTP submit are deliberately excluded by the state guards below.
_DISPOSABLE_PRE_ACCOUNT_FAILURE_MARKERS = (
    "err_tunnel_connection_failed",
    "err_proxy_connection_failed",
    "chrome-error://chromewebdata/",
    "邮箱提交/认证跳转超过总预算",
    "roxy registration stage timeout exhausted",
    "email otp input budget exhausted",
    "page_not_hydrated",
)

_REGISTRATION_REQUEST_UNKNOWN_MARKERS = (
    "auth_session_unavailable:",
    "session_identity_unverified",
    "session_identity_mismatch",
    "邮箱提交后未识别到",
    "邮箱提交/认证跳转超过总预算",
    "注册页状态未知",
    "后续页面类型未知",
    "认证跳转结果未知",
)


from core.kernels.browser.roxy.registration.session import (
    validate_registration_session_identity as _validate_registration_session_identity,
    registration_password_confirmed_after_token as _registration_password_confirmed_after_token,
)


def _registration_session_callbacks():
    from core.auth.browser.session_auth import ChatGPTSessionUnavailable, _read_chatgpt_session_once
    from core.kernels.browser.roxy.registration.session import SessionCallbacks

    return SessionCallbacks(
        read_session_once=_read_chatgpt_session_once,
        session_unavailable_error=ChatGPTSessionUnavailable,
        route_observer_type=RoxyRouteFailureObserver,
        current_route_recovery=_route_recovery_callback, check_stop=_check_manual_stop,
        native_resume_start_page=_is_native_resume_start_page, safe_get=_safe_get,
        validate_identity=_validate_registration_session_identity, logger=logger,
    )


def _read_registration_resume_session(driver, email: str, *, budget: StageBudget | None = None) -> dict | None:
    from core.kernels.browser.roxy.registration.session import read_registration_resume_session

    return read_registration_resume_session(driver, email, budget=budget, callbacks=_registration_session_callbacks())





def _reconcile_existing_profile_session(driver, email: str) -> dict:
    from core.kernels.browser.roxy.registration.session import reconcile_existing_profile_session

    return reconcile_existing_profile_session(driver, email, callbacks=_registration_session_callbacks())


def _retained_profile_can_attach(client, opened) -> bool:
    """按已打开进程核验原窗口；列表状态过期或连接未知不能触发新建。"""
    try:
        connection = client.get_open_profile_connection(opened.profile_id)
        if connection is None:
            return False
        ports = []
        for address in (connection.get("http"), opened.debugger_address):
            if not isinstance(address, str) or not address.strip():
                raise ValueError("调试连接地址缺失")
            address = address.strip()
            parsed = urlsplit(address if "://" in address else f"//{address}")
            if parsed.username or parsed.password or not parsed.hostname or not parsed.port:
                raise ValueError("调试连接端口不可用")
            ports.append(parsed.port)
        if ports[0] != ports[1]:
            raise ValueError("原调试连接端口已变化")
        return True
    except Exception:
        raise RuntimeError("request_unknown: 原浏览器状态未能核验，已保留原提交") from None


from core.kernels.browser.roxy.registration.otp import (
    _OTP_PREPARE_CURRENT_FORM_SCRIPT, _OTP_SUBMIT_CURRENT_FORM_SCRIPT,
)





def _registration_otp_form_callbacks():
    from core.codex.roxy.oauth import _install_email_otp_validate_hook
    from core.kernels.browser.roxy.registration.otp import OtpFormCallbacks

    return OtpFormCallbacks(
        record_submission=record_browser_submission_fact,
        install_validate_hook=_install_email_otp_validate_hook,
        dispatch_trusted_click=_dispatch_trusted_click, logger=logger,
    )


def _prepare_email_otp_current_form(driver, inputs, *, budget: StageBudget | None = None,
                                    capture_responses: bool = False) -> None:
    from core.kernels.browser.roxy.registration.otp import prepare_email_otp_current_form

    return prepare_email_otp_current_form(
        driver, inputs, budget=budget, capture_responses=capture_responses,
        callbacks=_registration_otp_form_callbacks(),
    )


def _submit_email_otp_current_form(driver) -> dict:
    from core.kernels.browser.roxy.registration.otp import submit_email_otp_current_form

    return submit_email_otp_current_form(driver, callbacks=_registration_otp_form_callbacks())

def _submit_registration_email_otp(driver, otp_code: str, *, budget: StageBudget,
                                   expected_email: str, on_refresh_retry=None,
                                   monitor_otp_network: bool = False):
    from core.kernels.browser.roxy.registration.otp import OtpExecutionCallbacks, submit_registration_email_otp

    callbacks = OtpExecutionCallbacks(
        record_submission=record_browser_submission_fact,
        log_submission_diagnostics=log_submission_diagnostics,
        email_otp_page_state=_email_otp_page_state, clear_otp_inputs=_clear_otp_inputs,
        budget_timeout=_budget_timeout, type_otp=_type_otp,
        prepare_current_form=_prepare_email_otp_current_form,
        submit_current_form=_submit_email_otp_current_form,
        check_stop=_check_manual_stop, human_delay=human_delay,
        wait_after_submit=_wait_after_email_otp_submit, logger=logger,
    )
    return submit_registration_email_otp(
        driver, otp_code, budget=budget, expected_email=expected_email,
        on_refresh_retry=on_refresh_retry, monitor_otp_network=monitor_otp_network,
        callbacks=callbacks,
    )


_PASSWORD_ENTRY_FAILURE_MARKERS = (
    "password_entry_page_not_hydrated",
    "password_entry_not_offered",
    "password_entry_recovery_exhausted",
)


class _OtpAttemptTracker:
    """记录已用验证码，防止重发后再次使用上一轮旧码。"""

    def __init__(self) -> None:
        self._submitted: set[str] = set()

    def accept(self, code: object) -> bool:
        normalized = str(code or "").strip()
        if not normalized or normalized in self._submitted:
            return False
        self._submitted.add(normalized)
        return True


def _is_registration_request_unknown(error_text: object) -> bool:
    """Recognize an observed-but-unclassified remote registration state."""
    if isinstance(error_text, _EmailSubmissionUnknown):
        return True
    if isinstance(error_text, EmailOtpNetworkError):
        return error_text.request_unknown
    if isinstance(error_text, PasswordPageError):
        return not bool(getattr(error_text, "not_submitted", False))
    if isinstance(error_text, AuthPageError):
        return bool(getattr(error_text, "submission_unknown", not getattr(error_text, "not_submitted", False)))
    text = str(error_text or "")
    if text.startswith("request_unknown:"):
        return True
    return any(marker in text for marker in _REGISTRATION_REQUEST_UNKNOWN_MARKERS)


def _observe_registration_email_page(driver, snapshot) -> None:
    """现成页面错误优先交回调度；未决提交仍沿原身份保持未知。"""
    error = auth_page_error(snapshot)
    if error is None:
        return
    receipt = getattr(driver, "_browser_submission_receipt", None)
    phase = getattr(receipt, "phase", "")
    unresolved = {"dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "unknown"}
    history = getattr(driver, "_browser_submission_receipts", ())
    previous_unknown = isinstance(history, (list, tuple)) and any(
        getattr(item, "phase", "") in unresolved for item in history
    )
    ui_pending = phase in {"", "prepared"} and isinstance(getattr(driver, "_email_submission_receipt", None), dict)
    context = getattr(driver, "_registration_fact_context", None)
    if not (phase in unresolved or previous_unknown or ui_pending) and isinstance(context, dict) and context.get("attempt_id") is not None:
        try:
            from core.storage import registration

            # 新 driver 不一定加载过原 Attempt 的回执；仅明确错误收口时核验一次。
            previous_unknown = registration.has_unresolved_submission_facts(int(context["attempt_id"]))
        except Exception:
            previous_unknown = True
            logger.warning("[Roxy注册] 原 Attempt 的未决提交事实暂不可核验，保留页面原因及未知状态")
    error.submission_unknown = bool(phase in unresolved or previous_unknown or ui_pending)
    error.not_submitted = bool(phase in {"", "prepared", "not_dispatched"} and not error.submission_unknown)
    if phase == "prepared" and error.not_submitted:
        record_browser_submission_fact(driver, "not_dispatched", receipt=receipt,
                                       result="cancelled", error_type=error.code)
    elif phase in unresolved:
        record_browser_submission_fact(driver, "unknown", receipt=receipt,
                                       result="unknown", error_type=error.code)
    logger.warning("[Roxy注册] 邮箱等待发现明确页面错误：%s；保留原身份及提交事实，交回注册调度", error.code)
    raise error


def _is_disposable_pre_account_failure(
    error_text: str,
    *,
    create_acknowledged: bool,
    account_id: int | None,
) -> bool:
    """Return whether a run-created Profile can be discarded safely."""
    if create_acknowledged or account_id is not None:
        return False
    normalized = str(error_text or "").lower()
    # 密码入口阶段已在 OpenAI 侧推进过注册身份。即使页面仍是空壳，也要保留
    # Profile/cookie 给同一 Attempt 继续恢复，不能按普通首屏空壳回收。
    if any(marker in normalized for marker in _PASSWORD_ENTRY_FAILURE_MARKERS):
        return False
    if any(marker in normalized for marker in _DISPOSABLE_PRE_ACCOUNT_FAILURE_MARKERS):
        return True
    # The page-not-hydrated classifier is persisted separately from the raw
    # exception. Match its characteristic empty ChatGPT auth snapshot too.
    empty_actions = "'actions': []" in normalized or '"actions": []' in normalized
    empty_inputs = "'inputs': []" in normalized or '"inputs": []' in normalized
    return (
        "找不到邮箱输入框/邮箱入口" in normalized
        and "chatgpt.com/auth/login" in normalized
        and empty_actions
        and empty_inputs
    )



from core.auth.browser import auth_capabilities as _auth_capabilities


def _shared_compat_overrides() -> dict[str, object]:
    """收集当前 Roxy 模块被旧测试/集成显式覆盖的绑定。"""
    overrides: dict[str, object] = {}
    for name in _auth_capabilities._COMPAT_BINDING_NAMES:
        candidate = globals().get(name)
        if candidate is None or getattr(candidate, "__roxy_shared_wrapper__", False):
            continue
        overrides[name] = candidate
    return overrides


def _call_shared_capability(name: str, *args, **kwargs):
    """调用共享能力；兼容覆盖是单次、显式且线程隔离的。"""
    overrides = _shared_compat_overrides()
    # 开源驱动仅在指定阶段注入页面辅助，不能重绑共享模块或影响其他注册任务。
    overrides.update(kwargs.pop("_helper_overrides", None) or {})
    if kwargs.get("context") is None:
        try:
            from core.registration.service import StopRequested, is_stop_requested

            def cancellation():
                if is_stop_requested():
                    return True
                driver = args[0] if args else None
                observer = getattr(driver, "_registration_route_observer", None)
                if isinstance(observer, RoxyRouteFailureObserver) and _route_recovery_callback() is not None:
                    observer.raise_if_failed(driver)
                return False

            kwargs["context"] = AuthExecutionContext(
                cancellation=cancellation,
                budget=kwargs.get("budget") if isinstance(kwargs.get("budget"), StageBudget) else None,
                cancellation_error=lambda: StopRequested("认证能力收到注册任务停止请求"),
            )
        except (ImportError, AttributeError):
            # Keep direct/unit capability calls usable when the registration
            # service is intentionally not loaded.  The service-facing path
            # supplies the concrete cancellation exception above.
            pass
    # The shared MFA/registration challenge capability accepts callbacks; it
    # must not import this OAuth orchestrator just to preserve the historical
    # Roxy monkeypatch points.  Resolve those adapters only on the old Roxy
    # path and inject them into the same ContextVar override scope.
    if name in {
        "_complete_registration_totp_after_email_otp",
        "_complete_settings_email_reauth",
    }:
        try:
            from core.codex.roxy import oauth as _oauth

            for callback_name in (
                "complete_openai_login_challenge",
                "_is_totp_login_page",
                "_submit_saved_login_totp",
            ):
                callback = getattr(_oauth, callback_name, None)
                if callable(callback):
                    overrides[callback_name] = callback
        except Exception:
            # A direct registration flow may not have loaded the OAuth module;
            # the capability will report a missing injected resolver only if
            # it actually reaches a chained challenge.
            pass
    return _auth_capabilities.call_with_compatibility(
        name,
        overrides,
        *args,
        **kwargs,
    )


def _make_shared_compatibility_wrapper(name: str):
    def wrapper(*args, **kwargs):
        return _call_shared_capability(name, *args, **kwargs)

    wrapper.__name__ = name
    wrapper.__qualname__ = name
    wrapper.__module__ = __name__
    wrapper.__roxy_shared_wrapper__ = True
    wrapper.__shared_capability__ = True
    return wrapper


_log_prefix = _make_shared_compatibility_wrapper("_log_prefix")
_build_driver = _make_shared_compatibility_wrapper("_build_driver")
_quit_driver = _make_shared_compatibility_wrapper("quit_driver")
_center_browser_window = _make_shared_compatibility_wrapper("_center_browser_window")
_wait = _make_shared_compatibility_wrapper("_wait")
_budget_timeout = _make_shared_compatibility_wrapper("_budget_timeout")
_roxy_page_state = _make_shared_compatibility_wrapper("_roxy_page_state")
_auth_terminal_page_state = _make_shared_compatibility_wrapper("_auth_terminal_page_state")
_safe_get = _make_shared_compatibility_wrapper("_safe_get")
_visible = _make_shared_compatibility_wrapper("_visible")
_browser_actions_enabled = _make_shared_compatibility_wrapper("_browser_actions_enabled")
_apply_browser_automation_mask = _make_shared_compatibility_wrapper("_apply_browser_automation_mask")
_human_scroll_to = _make_shared_compatibility_wrapper("_human_scroll_to")
_human_click = _make_shared_compatibility_wrapper("_human_click")
_human_type_text = _make_shared_compatibility_wrapper("_human_type_text")
_page_warmup = _make_shared_compatibility_wrapper("_page_warmup")
_refresh_chatgpt_settings_shell_if_needed = _make_shared_compatibility_wrapper("_refresh_chatgpt_settings_shell_if_needed")
_settings_page_not_ready = _make_shared_compatibility_wrapper("_settings_page_not_ready")
_find_any = _make_shared_compatibility_wrapper("_find_any")
_click_any = _make_shared_compatibility_wrapper("_click_any")
_type_any = _make_shared_compatibility_wrapper("_type_any")
_email_entry_state = _make_shared_compatibility_wrapper("_email_entry_state")
_find_visible_email_input_js = _make_shared_compatibility_wrapper("_find_visible_email_input_js")
_is_oauth_consent_like = _make_shared_compatibility_wrapper("_is_oauth_consent_like")
_is_external_idp_url = _make_shared_compatibility_wrapper("_is_external_idp_url")
_assert_not_external_idp = _make_shared_compatibility_wrapper("_assert_not_external_idp")
_click_email_entry_option = _make_shared_compatibility_wrapper("_click_email_entry_option")
_is_blank_chatgpt_auth_shell = _make_shared_compatibility_wrapper("_is_blank_chatgpt_auth_shell")
_reload_blank_chatgpt_auth_shell = _make_shared_compatibility_wrapper("_reload_blank_chatgpt_auth_shell")
_email_submit_advanced_state = _make_shared_compatibility_wrapper("_email_submit_advanced_state")
_type_email_address = _make_shared_compatibility_wrapper("_type_email_address")
_submit_nearest_form_for_active_input = _make_shared_compatibility_wrapper("_submit_nearest_form_for_active_input")
_current_email_input_value = _make_shared_compatibility_wrapper("_current_email_input_value")
_stabilize_email_input_before_submit = _make_shared_compatibility_wrapper("_stabilize_email_input_before_submit")
_submit_email_form_stable = _make_shared_compatibility_wrapper("_submit_email_form_stable")
_submit_email_step = _make_shared_compatibility_wrapper("_submit_email_step")
_recover_email_submit_if_stuck = _make_shared_compatibility_wrapper("_recover_email_submit_if_stuck")
_submit_email_via_browser_nextauth = _make_shared_compatibility_wrapper("_submit_email_via_browser_nextauth")
_email_input_value_state = _make_shared_compatibility_wrapper("_email_input_value_state")
_is_email_login_page_still_present = _make_shared_compatibility_wrapper("_is_email_login_page_still_present")
_diagnostic_url = _make_shared_compatibility_wrapper("_diagnostic_url")
_redact_diagnostic_text = _make_shared_compatibility_wrapper("_redact_diagnostic_text")
_log_blank_auth_shell_diagnostics = _make_shared_compatibility_wrapper("_log_blank_auth_shell_diagnostics")
_wait_email_submit_next_state = _make_shared_compatibility_wrapper("_wait_email_submit_next_state")
_submit_email_and_wait_next = _make_shared_compatibility_wrapper("_submit_email_and_wait_next")
_type_otp = _make_shared_compatibility_wrapper("_type_otp")
_email_otp_page_state = _make_shared_compatibility_wrapper("_email_otp_page_state")
_wait_email_otp_page_ready = _make_shared_compatibility_wrapper("_wait_email_otp_page_ready")
_recover_email_otp_page_if_needed = _make_shared_compatibility_wrapper("_recover_email_otp_page_if_needed")
_email_otp_page_recovery_reason = _make_shared_compatibility_wrapper("_email_otp_page_recovery_reason")
_is_email_verification_page = _make_shared_compatibility_wrapper("_is_email_verification_page")
_clear_otp_inputs = _make_shared_compatibility_wrapper("_clear_otp_inputs")
_click_resend_email_otp = _make_shared_compatibility_wrapper("_click_resend_email_otp")
_resend_email_otp_after_failure = _make_shared_compatibility_wrapper("_resend_email_otp_after_failure")
_classify_otp_wait_failure = _make_shared_compatibility_wrapper("_classify_otp_wait_failure")
_complete_registration_totp_after_email_otp = _make_shared_compatibility_wrapper("_complete_registration_totp_after_email_otp")
_wait_after_email_otp_submit = _make_shared_compatibility_wrapper("_wait_after_email_otp_submit")
_click_continue = _make_shared_compatibility_wrapper("_click_continue")
_maybe_accept = _make_shared_compatibility_wrapper("_maybe_accept")
_page_snapshot = _make_shared_compatibility_wrapper("_page_snapshot")
_has_access_token = _make_shared_compatibility_wrapper("_has_access_token")
_is_profile_like = _make_shared_compatibility_wrapper("_is_profile_like")
_set_element_value = _make_shared_compatibility_wrapper("_set_element_value")
_select_or_type = _make_shared_compatibility_wrapper("_select_or_type")
_fill_birthday_or_age = _make_shared_compatibility_wrapper("_fill_birthday_or_age")
_generate_roxy_password = _make_shared_compatibility_wrapper("_generate_roxy_password")
_registration_password = _make_shared_compatibility_wrapper("_registration_password")
_registration_auth_mode = _make_shared_compatibility_wrapper("_registration_auth_mode")
_password_transition_timeout_seconds = _make_shared_compatibility_wrapper("_password_transition_timeout_seconds")
_password_page_state = _make_shared_compatibility_wrapper("_password_page_state")
_is_signup_password_page = _make_shared_compatibility_wrapper("_is_signup_password_page")
_is_login_password_page = _make_shared_compatibility_wrapper("_is_login_password_page")
_click_passwordless_signup_if_present = _make_shared_compatibility_wrapper("_click_passwordless_signup_if_present")
_click_signup_password_from_otp_if_present = _make_shared_compatibility_wrapper("_click_signup_password_from_otp_if_present")
_fill_password_page_if_present = _make_shared_compatibility_wrapper("_fill_password_page_if_present")
_accept_profile_consents = _make_shared_compatibility_wrapper("_accept_profile_consents")
_complete_profile_page = _make_shared_compatibility_wrapper("_complete_profile_page")
_click_if_enabled_submit = _make_shared_compatibility_wrapper("_click_if_enabled_submit")
_read_chatgpt_session_once = _make_shared_compatibility_wrapper("_read_chatgpt_session_once")
_switch_to_chatgpt_window_if_any = _make_shared_compatibility_wrapper("_switch_to_chatgpt_window_if_any")
_fetch_chatgpt_session = _make_shared_compatibility_wrapper("_fetch_chatgpt_session")
_wait_registration_homepage = _make_shared_compatibility_wrapper("_wait_registration_homepage")
_check_manual_stop = _make_shared_compatibility_wrapper("_check_manual_stop")
_probe_chatgpt_password_eligibility = _make_shared_compatibility_wrapper("_probe_chatgpt_password_eligibility")
_totp_secret_candidate = _make_shared_compatibility_wrapper("_totp_secret_candidate")
_first_visible_css = _make_shared_compatibility_wrapper("_first_visible_css")
_is_stale_element_error = _make_shared_compatibility_wrapper("_is_stale_element_error")
_visible_new_password_inputs = _make_shared_compatibility_wrapper("_visible_new_password_inputs")
_wait_visible_css = _make_shared_compatibility_wrapper("_wait_visible_css")
_detect_mfa_enrollment_step = _make_shared_compatibility_wrapper("_detect_mfa_enrollment_step")
_wait_mfa_enrollment_step = _make_shared_compatibility_wrapper("_wait_mfa_enrollment_step")
_wait_after_mfa_email_submit = _make_shared_compatibility_wrapper("_wait_after_mfa_email_submit")
_dismiss_single_action_dialog = _make_shared_compatibility_wrapper("_dismiss_single_action_dialog")
_dismiss_chatgpt_pricing_modal = _make_shared_compatibility_wrapper("_dismiss_chatgpt_pricing_modal")
_click_chatgpt_settings_control = _make_shared_compatibility_wrapper("_click_chatgpt_settings_control")
_reveal_chatgpt_settings_navigation = _make_shared_compatibility_wrapper("_reveal_chatgpt_settings_navigation")
_click_password_setting_fallback = _make_shared_compatibility_wrapper("_click_password_setting_fallback")
_open_chatgpt_security_settings = _make_shared_compatibility_wrapper("_open_chatgpt_security_settings")
_disable_roxy_2fa = _make_shared_compatibility_wrapper("_disable_roxy_2fa")
_complete_settings_email_reauth = _make_shared_compatibility_wrapper("_complete_settings_email_reauth")
set_roxy_login_password = _make_shared_compatibility_wrapper("set_roxy_login_password")
_button_after_input = _make_shared_compatibility_wrapper("_button_after_input")
_read_totp_secret_from_dialog = _make_shared_compatibility_wrapper("_read_totp_secret_from_dialog")
_manual_totp_secret = _make_shared_compatibility_wrapper("_manual_totp_secret")
setup_roxy_2fa = _make_shared_compatibility_wrapper("setup_roxy_2fa")
setup_protocol_2fa_with_browser_fallback = _make_shared_compatibility_wrapper("setup_protocol_2fa_with_browser_fallback")
set_login_password = _make_shared_compatibility_wrapper("set_roxy_login_password")
setup_roxy_2fa = _make_shared_compatibility_wrapper("setup_roxy_2fa")
setup_protocol_2fa_with_browser_fallback = _make_shared_compatibility_wrapper("setup_protocol_2fa_with_browser_fallback")

# Constants/classes retained for old tests and integrations.  They are values
# from the shared responsibility modules, not implementations copied back into
# this compatibility surface.
_PasswordTransitionTimeout = _auth_capabilities._PasswordTransitionTimeout
_CHATGPT_HOME_URL = _auth_capabilities._mfa_auth._CHATGPT_HOME_URL
_CHATGPT_SECURITY_SETTINGS_URL = _auth_capabilities._mfa_auth._CHATGPT_SECURITY_SETTINGS_URL
_CHATGPT_PASSWORD_SETTINGS_URL = _auth_capabilities._mfa_auth._CHATGPT_PASSWORD_SETTINGS_URL
_MFA_EMAIL_CODE_SELECTOR = _auth_capabilities._mfa_auth._MFA_EMAIL_CODE_SELECTOR
_MFA_TOTP_CODE_SELECTOR = _auth_capabilities._mfa_auth._MFA_TOTP_CODE_SELECTOR

def _is_roxy_window_capacity_error(error: object) -> bool:
    """只识别明确的窗口容量错误，避免把网络/配置故障误当成可等待状态。"""
    text = str(error or "").strip().lower()
    if not text:
        return False
    markers = (
        "窗口额度不足",
        "窗口数量已达上限",
        "窗口数已达上限",
        "窗口达到上限",
        "window quota",
        "window limit",
        "maximum number of windows",
        "too many windows",
    )
    return any(marker in text for marker in markers)


def _wait_for_roxy_window_retry(seconds: float) -> None:
    """可被手动停止打断的容量等待，最多每秒检查一次停止信号。"""
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        _check_manual_stop()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(1.0, remaining))


def _open_roxy_profile_with_capacity_wait(
    client,
    proxy_url: str | None,
    *,
    profile_id: str | None = None,
    progress_callback=None,
    data_saver_flow: str | None = None,
    prefer_existing_profile: bool = False,
    preclosed_profile: bool = False,
) -> RoxyOpenResult:
    """仅在 /browser/open 遇到可恢复的窗口忙时等待，避免快速消费后续任务槽位。"""
    timeout = max(0, int(getattr(_cfg, "ROXY_WINDOW_WAIT_TIMEOUT", 900) or 0))
    interval = max(1, int(getattr(_cfg, "ROXY_WINDOW_WAIT_INTERVAL", 10) or 10))
    started = time.monotonic()
    attempt = 0

    while True:
        _check_manual_stop()
        attempt += 1
        try:
            debug_headless = None
            try:
                from core.registration.debug import current_session
                debug_session = current_session()
                # failure_only 只在最终失败时保存现场，不需要为了采集而
                # 显示浏览器窗口；只有显式全量调试才强制可见。这样普通
                # 诊断和线程池遗留的 failure_only 会话都不会覆盖无头配置。
                if getattr(debug_session, "capture_mode", "") == "full":
                    debug_headless = False
            except Exception:
                pass
            open_kwargs = {"proxy_url": proxy_url}
            if data_saver_flow is not None:
                open_kwargs["data_saver_flow"] = data_saver_flow
            if debug_headless is not None:
                open_kwargs["headless"] = debug_headless
            if prefer_existing_profile:
                open_kwargs["prefer_existing_profile"] = True
            if preclosed_profile:
                open_kwargs["preclosed_profile"] = True
            if profile_id is None:
                opened = client.open_profile(**open_kwargs)
            else:
                opened = client.open_profile_for_account(
                    profile_id=profile_id,
                    **open_kwargs,
                )
            if attempt > 1:
                logger.info(
                    "[Roxy注册] 已等到空闲窗口并成功启动环境：attempt=%s waited=%.1fs profile=%s",
                    attempt,
                    time.monotonic() - started,
                    opened.profile_id,
                )
            return opened
        except Exception as exc:
            if isinstance(exc, RoxyProfileQuotaExceeded):
                raise
            if not _is_roxy_window_capacity_error(exc) or timeout <= 0:
                raise

            elapsed = time.monotonic() - started
            remaining = timeout - elapsed
            if remaining <= 0:
                raise RuntimeError(
                    f"等待 Roxy 空闲窗口超时（>{timeout}s），最后错误: {str(exc)[:180]}"
                ) from exc

            delay = min(float(interval), remaining)
            detail = (
                f"Roxy 窗口已满，等待空闲名额：已等 {int(elapsed)}s，"
                f"{int(delay)}s 后重试，最长 {timeout}s"
            )
            if progress_callback is not None:
                progress_callback("browser", "running", detail)
            logger.warning(
                "[Roxy注册] %s（attempt=%s，剩余 %.1fs）：%s",
                detail,
                attempt,
                remaining,
                str(exc)[:180],
            )
            _wait_for_roxy_window_retry(delay)


def _install_registration_postprocess_data_saver(opened, driver):
    """为注册后的 2FA/账号操作切换认证规则，并由外层统一收口统计。"""
    try:
        from core.browser.flow_policy import install_for_flow

        return install_for_flow(
            "account_action",
            opened,
            driver,
            label="ChatGPT 账号操作",
        )
    except Exception:
        logger.exception("[Roxy注册] 安装注册后账号操作省流量规则失败；后续流程继续")
        return None



def _registration_otp_attempt_wait_seconds(deadline: float, attempt: int, max_attempts: int) -> int:
    """Split one total OTP budget across remaining resend attempts."""
    remaining = max(0.0, float(deadline) - time.monotonic())
    attempts_left = max(1, int(max_attempts) - int(attempt) + 1)
    return int(math.ceil(remaining / attempts_left)) if remaining > 0 else 0


def _save_roxy_account_checkpoint(
    *,
    email: str,
    access_token: str,
    session_info: dict,
    opened: RoxyOpenResult,
    openai_password: str | None,
    proxy: str | None,
    email_source: str | None = None,
    totp_secret: str | None = None,
    codex_result: dict | None = None,
    twofa_result: dict | None = None,
    registration_driver: str = "roxy",
    password_confirmed: bool = False,
) -> int:
    """只落库、不做套餐查询的注册检查点。"""
    from core.db import insert_account

    user = session_info.get("user") or {}
    account = session_info.get("account") or {}
    codex = codex_result or {}
    codex_status = str(codex.get("status") or "").strip() or None
    codex_error = str(codex.get("message") or "").strip() if codex_status == "failed" else None
    extra = {
        "user": user,
        "account": account,
        "expires": session_info.get("expires"),
        "roxybrowser": {
            "profile_id": opened.profile_id,
            "open_result": opened.raw,
            "retained": True,
        },
        "registration_checkpoint": "registered",
        "registration_driver": registration_driver,
        "codex": codex_result,
        "twofa": twofa_result,
    }
    # 本轮直接复用登录态时可能没有返回密码，空值不能清除账号已有凭据。
    extra.update(registration_password_extra(openai_password, confirmed=password_confirmed))
    twofa_status = str((twofa_result or {}).get("status") or "").strip().lower()
    if totp_secret and twofa_status in {"running", "failed"}:
        # The key is already persisted, but OpenAI has not yet been confirmed
        # enabled. Keep this checkpoint explicit so a later browser retry can
        # verify/finish enrollment instead of assuming the secret is active.
        extra["totp_setup_pending"] = True
    account_id = insert_account(
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        user_id=user.get("id"),
        user_name=user.get("name"),
        plan_type=account.get("planType"),
        expires_at=session_info.get("expires"),
        proxy_used=proxy or None,
        email_source=email_source or resolve_email_source(email),
        extra=extra,
        chatgpt_session=session_info,
        codex_status=codex_status,
        codex_error=codex_error,
    )
    opened.account_bound = True
    RoxyBrowserClient.mark_profile_bound(opened.profile_id)
    return account_id


def _save_pending_email_verification_checkpoint(
    *,
    email: str,
    openai_password: str,
    opened: RoxyOpenResult,
    proxy: str | None,
    email_source: str | None = None,
) -> int:
    """保存原邮箱和恢复候选；密码创建被接受尚不能证明密码已经生效。"""
    from core.registration.checkpoints import save_email_verification_checkpoint

    account_id = save_email_verification_checkpoint(
        email=email,
        password=openai_password,
        proxy=proxy,
        email_source=email_source,
        profile_metadata={
            "profile_id": opened.profile_id,
            "open_result": opened.raw,
            "retained": True,
        },
    )
    opened.account_bound = True
    RoxyBrowserClient.mark_profile_bound(opened.profile_id)
    return account_id


def _run_in_isolated_browser_tab(driver, callback, *, label: str):
    """在同一浏览器 Profile 的新标签页执行操作，结束后恢复原标签页。

    Cookie 仍由同一个 Roxy Profile 共享，但 OAuth 的 URL/表单/失败页面不会覆盖
    注册完成后的 ChatGPT 标签页。callback 成功或抛错都会关闭本次新建的全部标签页。
    """
    original_handles = list(getattr(driver, "window_handles", []) or [])
    original_handle = getattr(driver, "current_window_handle", None)
    if not original_handle:
        raise RuntimeError(f"{label} 无法读取原浏览器标签页")
    if original_handle not in original_handles:
        original_handles.append(original_handle)
    original_set = set(original_handles)

    try:
        driver.switch_to.new_window("tab")
    except Exception as first_exc:
        # 兼容缺少 Selenium new_window 的浏览器适配层。
        try:
            driver.switch_to.window(original_handle)
            driver.execute_script("window.open('about:blank', '_blank');")
            end = time.time() + 5
            new_handles = []
            while time.time() < end:
                new_handles = [h for h in (getattr(driver, "window_handles", []) or []) if h not in original_set]
                if new_handles:
                    break
                time.sleep(0.1)
            if not new_handles:
                raise RuntimeError("window.open 未创建新标签页")
            driver.switch_to.window(new_handles[-1])
        except Exception as fallback_exc:
            try:
                driver.switch_to.window(original_handle)
            except Exception:
                pass
            raise RuntimeError(
                f"无法为 {label} 创建独立标签页，已停止以避免污染注册登录态："
                f"new_window={type(first_exc).__name__}: {first_exc}; "
                f"fallback={type(fallback_exc).__name__}: {fallback_exc}"
            ) from fallback_exc

    isolated_handle = getattr(driver, "current_window_handle", None)
    if not isolated_handle or isolated_handle in original_set:
        try:
            driver.switch_to.window(original_handle)
        except Exception:
            pass
        raise RuntimeError(f"{label} 独立标签页创建后句柄未变化")

    logger.info("[Roxy注册] %s 已在独立标签页启动，原 ChatGPT 标签页保持不变", label)
    try:
        return callback()
    finally:
        # callback 可能又打开 callback/popup 标签页；只关闭本次操作新增的句柄。
        try:
            current_handles = list(getattr(driver, "window_handles", []) or [])
        except Exception:
            current_handles = []
        for handle in reversed(current_handles):
            if handle in original_set:
                continue
            try:
                driver.switch_to.window(handle)
                driver.close()
            except Exception as exc:
                logger.debug("[Roxy注册] 关闭 %s 新标签页失败 handle=%s: %s", label, handle, exc)
        try:
            remaining = list(getattr(driver, "window_handles", []) or [])
            target = original_handle if original_handle in remaining else next(
                (h for h in original_handles if h in remaining),
                None,
            )
            if not target:
                raise RuntimeError("原标签页已不存在")
            driver.switch_to.window(target)
            logger.info("[Roxy注册] %s 已结束并切回原 ChatGPT 标签页", label)
        except Exception as exc:
            raise RuntimeError(f"{label} 结束后无法恢复原 ChatGPT 标签页：{exc}") from exc


def _is_registration_proxy_transport_failure(exc: BaseException) -> bool:
    """只认明确连接错误；HTTP 拒绝、超时和页面空壳不能证明代理故障。"""
    return re.search(
        r"(?<![a-z0-9_])(?:net::)?(?:err_tunnel_connection_failed|err_proxy_connection_failed|"
        r"err_connection_reset|err_connection_closed|err_connection_refused|err_connection_aborted)"
        r"(?![a-z0-9_])",
        f"{type(exc).__name__}: {exc}", re.I,
    ) is not None


def _validated_resume_proxy_rotation(options: dict, facts: dict, profile_id: str | None) -> dict:
    """换线许可只属于当前 Run 的临时调用，不能跨 Attempt 或执行接管窗口。"""
    value = options.get("_resume_proxy_rotation")
    if not isinstance(value, dict):
        return {}
    reopen = str(value.get("reopen_profile_id") or "").strip()
    try:
        keys = ("job_id", "attempt_id", "run_id", "execution_id")
        if any(facts.get(key) in (None, "") or value.get(key) != facts[key] for key in keys):
            raise ValueError
        from core.storage import registration

        run = registration.get_run(int(facts["run_id"])) or {}
        if (run.get("action_type") != "registration_resume" or run.get("status") != "running"
                or any(run.get(key) != facts[key] for key in ("job_id", "attempt_id", "execution_id"))
                or (reopen and reopen != str(profile_id or "").strip())):
            raise ValueError
    except Exception:
        if reopen:
            raise RuntimeError("request_unknown: 换线重开与原 Run、Attempt 或环境身份不一致，保留原窗口") from None
        return {}
    return value


def _validated_roxy_cf_proxy_rotation(options: dict, facts: dict, profile_id: str | None) -> dict:
    """认证挑战换线只接受服务层绑定当前 Run 的临时上下文。"""
    value = options.get('_roxy_cf_proxy_rotation')
    if not isinstance(value, dict):
        return {}
    reopen = str(value.get('reopen_profile_id') or '').strip()
    deleted_temporary = value.get('previous_cf_temporary_profile_deleted', False)
    try:
        if type(deleted_temporary) is not bool or (deleted_temporary and (reopen or profile_id)):
            raise ValueError
        keys = ('job_id', 'attempt_id', 'run_id', 'execution_id')
        if any(facts.get(key) in (None, '') or type(value.get(key)) is not type(facts[key])
               or value.get(key) != facts[key] for key in keys):
            raise ValueError
        from core.storage import registration
        run = registration.get_run(int(facts['run_id'])) or {}
        if (run.get('action_type') not in {'registration', 'registration_resume'}
                or run.get('status') != 'running'
                or any(run.get(key) != facts[key] for key in ('job_id', 'attempt_id', 'execution_id'))
                or (reopen and reopen != str(profile_id or '').strip())):
            raise ValueError
    except Exception:
        if reopen or deleted_temporary:
            raise RuntimeError('request_unknown: CF 换线与原 Run、Attempt 或环境身份不一致，保留原环境') from None
        return {}
    return value


def _confirmed_cf_profile_deleted(client, profile_id: str) -> bool:
    """新建环境换线前，必须在回收站实际查到该环境，未知列表不视为删除成功。"""
    from core.browser.roxy.client import _workspace_id_value
    normalized = str(profile_id).strip()
    payload = client.request('GET', '/browser/list_v2', params={
        'workspaceId': _workspace_id_value(), 'dirId': normalized, 'isDelete': 1,
        'page_index': 1, 'page_size': 10,
    })
    if not isinstance(payload, dict):
        return False
    data = payload.get('data')
    containers = [data, payload]
    rows = data if isinstance(data, list) else None
    if rows is None:
        for container in containers:
            if isinstance(container, dict):
                rows = next((container[key] for key in ('rows', 'list', 'records', 'items')
                             if isinstance(container.get(key), list)), None)
                if rows is not None:
                    break
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return False
    return any(str(row.get('dirId') or row.get('dir_id') or row.get('id')
                   or row.get('profileId') or row.get('profile_id') or '').strip() == normalized
               for row in rows)


def _registration_profile_form_ready(driver) -> bool:
    from core.kernels.browser.roxy.registration.profile import registration_profile_form_ready

    return registration_profile_form_ready(driver, snapshot=_page_snapshot)


def _run_roxy_authentication(
    driver, *, email, name, birthday, proxy, otp_code, existing_password,
    existing_totp_secret, profile_id, opened, selected_email_source, password_required,
    resume_scope, resume_metadata, route_state, local_browser, route_recovery_enabled,
    cf_rotation_allowed, has_retained_browser, current_lease_route_verified, context,
    data_saver, route_observer, native_signin_diagnostics, submit_email, complete_profile,
    state,
):
    from core.kernels.browser.roxy.registration.runner import (
        RoxyBrowserCapabilities, RoxyRegistrationCallbacks, RoxyRegistrationRequest,
        execute_registration_auth,
    )
    from core.registration.service import report_job_otp_evidence, report_job_progress, report_registered_account

    def rejected_existing_profile(address, facts):
        from core.storage import registration

        private = registration.get_private_resume_context(int(facts["attempt_id"]), email=address)
        return has_rejected_existing_profile(private.get("submission_facts"))

    def save_password_checkpoint(**kwargs):
        from core.registration.checkpoints import save_protocol_password_checkpoint

        return save_protocol_password_checkpoint(**kwargs)

    def save_pending_checkpoint(*, email, openai_password):
        return _save_pending_email_verification_checkpoint(
            email=email, openai_password=openai_password, opened=opened, proxy=proxy,
            email_source=selected_email_source,
        )

    def otp_total_wait():
        try:
            from config import email as email_cfg
            return max(1, int(getattr(email_cfg, "OTP_MAX_WAIT", 240) or 240))
        except Exception:
            return 240

    def complete_login_challenge(*args, **kwargs):
        from core.codex.roxy.oauth import complete_openai_login_challenge

        return complete_openai_login_challenge(*args, **kwargs)

    def resume_password_recovery(recovery):
        return recovery.resume()

    def password_recovery_confirms(recovery, password, already_confirmed):
        if recovery.checkpoint is not None:
            recovered = recovery.checkpoint
            return already_confirmed or (
                recovered.state == "confirmed" and recovered.password == password
            )
        return already_confirmed

    request = RoxyRegistrationRequest(
        email=email, name=name, birthday=birthday, proxy=proxy, otp_code=otp_code,
        existing_totp_secret=existing_totp_secret, profile_id=profile_id,
        current_profile_id=str(opened.profile_id), selected_email_source=selected_email_source,
        password_required=password_required, resume_scope=resume_scope, resume_metadata=resume_metadata,
        route_state=route_state, local_browser=local_browser, route_recovery_enabled=route_recovery_enabled,
        cf_rotation_allowed=cf_rotation_allowed, has_retained_browser=has_retained_browser,
        current_lease_route_verified=current_lease_route_verified, facts=context,
    )
    callbacks = RoxyRegistrationCallbacks(
        password_recovery_session=_registration_password_recovery_session,
        resume_password_recovery=resume_password_recovery,
        password_recovery_confirms=password_recovery_confirms,
        recover_password=_recover_roxy_password,
        prepare_retained_resume=prepare_retained_resume,
        save_password_checkpoint=save_password_checkpoint,
        save_pending_checkpoint=save_pending_checkpoint,
        record_submission=record_browser_submission_fact,
        report_progress=report_job_progress,
        report_otp_evidence=report_job_otp_evidence,
        report_registered_account=report_registered_account,
        wait_for_otp=wait_for_otp,
        rejected_existing_profile=rejected_existing_profile, otp_total_wait=otp_total_wait,
        selenium_timeout=lambda: int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90),
        lightweight_post_auth=lambda: bool(data_saver is not None and data_saver.enabled), logger=logger,
        wall_time=lambda: time.time(),
    )
    browser = RoxyBrowserCapabilities(
        check_stop=_check_manual_stop,
        classify_otp_wait_failure=_classify_otp_wait_failure,
        complete_totp=_complete_registration_totp_after_email_otp,
        fetch_session=_fetch_chatgpt_session,
        fill_password=_fill_password_page_if_present,
        has_access_token=_has_access_token,
        is_email_verification_page=_is_email_verification_page,
        is_proxy_transport_failure=_is_registration_proxy_transport_failure,
        maybe_accept=_maybe_accept,
        observe_email_page=_observe_registration_email_page,
        page_warmup=_page_warmup,
        read_resume_session=_read_registration_resume_session,
        reconcile_profile_session=_reconcile_existing_profile_session,
        otp_attempt_wait_seconds=_registration_otp_attempt_wait_seconds,
        password_confirmed_after_token=_registration_password_confirmed_after_token,
        profile_form_ready=_registration_profile_form_ready,
        resend_otp=_resend_email_otp_after_failure,
        retained_page_state=_retained_page_state,
        safe_get=_safe_get,
        submit_email_otp=_submit_registration_email_otp,
        validate_session_identity=_validate_registration_session_identity,
        wait_after_otp_submit=_wait_after_email_otp_submit,
        wait_otp_page_ready=_wait_email_otp_page_ready,
        wait_password_reset_required=_wait_for_current_password_reset_required,
        human_delay=human_delay,
        password_evidence=password_evidence,
        password_receipt_ids=password_receipt_ids,
        submit_email=submit_email,
        complete_profile=complete_profile,
        complete_login_challenge=complete_login_challenge,
        retained_state_factory=RetainedResumeState,
        otp_tracker_type=_OtpAttemptTracker,
        password_transition_error=_PasswordTransitionTimeout,
    )
    return execute_registration_auth(
        driver, request, state, callbacks=callbacks, browser=browser,
        route_observer=route_observer, native_signin_diagnostics=native_signin_diagnostics,
    )


def run_roxy_registration(
    email: str,
    name: str,
    birthday: str,
    proxy: str = None,
    otp_code: str = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
    profile_id: str | None = None,
    registration_options: dict | None = None,
    email_source: str | None = None,
    *,
    _browser_helpers=None,
) -> dict:
    """Roxy 指纹浏览器自动化注册入口。"""
    registration_driver = _browser_helpers.driver_name if _browser_helpers is not None else "roxy"
    submit_email = (
        _browser_helpers.submit_email_and_wait_next if _browser_helpers is not None
        else _submit_email_and_wait_next
    )
    complete_profile = (
        _browser_helpers.complete_profile_page if _browser_helpers is not None
        else _complete_profile_page
    )
    if not str(proxy or "").strip():
        raise RuntimeError(
            "Roxy 注册必须使用统一代理池已领取线路，禁止无代理 Profile 或直连"
        )
    from core.registration.service import report_job_otp_evidence, report_job_progress, report_registered_account

    selected_email_source = validate_email_source(email_source) if email_source else None
    options = dict(registration_options or {})
    password_required = bool(options.get("password_enabled", _registration_auth_mode() == "password"))
    twofa_enabled = bool(options.get("twofa_enabled", _twofa_cfg.ENABLE_2FA))
    # ``dict.get`` evaluates its default argument eagerly.  Read the live
    # config only for legacy callers that did not provide a job snapshot; this
    # keeps submitted choices authoritative and avoids touching Codex config
    # while Codex is disabled.
    codex_enabled = (
        bool(options["codex_enabled"])
        if "codex_enabled" in options
        else bool(getattr(_codex_cfg, "ENABLE_CODEX_AUTO", False))
    )
    plan_check_enabled = bool(options.get("plan_check_enabled", True))

    from core.registration.service import registration_fact_context

    facts = registration_fact_context()
    route_callback = _route_recovery_callback() if _browser_helpers is None else None
    route_state = (
        validated_recovery_state(options.get("_roxy_route_recovery"), facts=facts,
                                 profile_id=profile_id, email=email)
        if _browser_helpers is None else None
    )
    if route_state is not None:
        profile_id = route_state.profile_id
        if existing_password and route_state.password and existing_password != route_state.password:
            raise RuntimeError("request_unknown: 换线密码与原候选不一致，保留原身份")
        existing_password = route_state.password or existing_password
    retry_country = options.get("retry_proxy_country_override")
    explicit_retry_route = False
    if retry_country is not None and _browser_helpers is None:
        from config.countries import ISO_3166_ALPHA2

        if (not isinstance(retry_country, str) or retry_country not in ISO_3166_ALPHA2
                or retry_country != options.get("proxy_country")):
            raise ValueError("重跑代理国家与本轮线路配置不一致")
        explicit_retry_route = True
    rotation_context = _validated_resume_proxy_rotation(options, facts, profile_id)
    cf_rotation_context = (
        _validated_roxy_cf_proxy_rotation(options, facts, profile_id) if _browser_helpers is None else {}
    )
    retained = None
    reopened_retained = (
        SimpleNamespace(driver=SimpleNamespace(**route_state.driver_state),
                        opened=SimpleNamespace(profile_id=route_state.profile_id),
                        otp_after_ts=route_state.otp_after_ts)
        if route_state is not None else None
    )
    if not (route_state is not None or rotation_context.get("reopen_profile_id") or cf_rotation_context.get('reopen_profile_id')
            or cf_rotation_context.get('previous_cf_temporary_profile_deleted') is True):
        retained = take_failed_browser(email=email, profile_id=profile_id, facts=facts)
        if retained is None:
            retained = recover_attempt_failed_browser(email=email, profile_id=profile_id, facts=facts)
        if retained is None:
            retained = recover_bound_failed_browser(email=email, profile_id=profile_id, facts=facts)
    if retained is not None and explicit_retry_route:
        # 先沿原身份核验并找回 Profile，再由既有关闭确认/更新代理路径重开；
        # 接管旧 driver 会沿用旧中继，无法兑现本轮显式选择的国家。
        profile_id = str(retained.opened.profile_id)
        reopened_retained = retained
        retained = None
    report_job_progress("browser", "running", "正在接管原失败窗口" if retained else "正在打开或创建 Roxy 浏览器环境")
    client = RoxyBrowserClient()
    retained_driver = None
    if retained:
        retained_driver = retained.driver
        try:
            if retained_driver is None:
                raise RuntimeError("原 Selenium 连接未保存在当前进程")
            str(retained_driver.current_url)
        except Exception:
            try:
                if not _retained_profile_can_attach(client, retained.opened):
                    retained = None
                    retained_driver = None
                else:
                    # 只连接保存的原 debugger；重连的活页还需独立核验邮箱身份。
                    retained_driver = _build_driver(retained.opened)
                    retained_driver._registration_retained_identity_required = True
                    for attr in ("_browser_submission_receipt", "_browser_submission_receipts",
                                 "_registration_otp_after_ts", "_registration_otp_tracker", "_email_otp_page_refresh_done"):
                        if retained.driver is not None and hasattr(retained.driver, attr):
                            setattr(retained_driver, attr, getattr(retained.driver, attr))
            except Exception:
                if retained.driver is not None:
                    retain_failed_browser(retained.driver, retained.opened, email=email, facts=facts)
                raise RuntimeError("request_unknown: 原浏览器连接未能恢复，已保留原提交") from None
    if retained:
        # 旧 worker 已退出；沿用原连接，重新建立本轮观察器，不发送 browser/open。
        opened = copy.copy(retained.opened)
        opened.created_by_run = False
        opened.traffic_capture = None
        client.attach_retained_profile_relay(opened)
        opened.proxy_route_retained = True
    else:
        opened = _open_roxy_profile_with_capacity_wait(
            client,
            proxy,
            profile_id=profile_id,
            progress_callback=report_job_progress,
            data_saver_flow="registration",
            **({"prefer_existing_profile": True} if explicit_retry_route and profile_id else {}),
            **({"preclosed_profile": True} if route_state is not None else {}),
        )
    try:
        from core.browser import traffic as browser_traffic
        if retained:
            browser_traffic.start_roxy_capture(opened, purpose="registration")
        browser_traffic.bind_roxy_capture(
            opened,
            purpose="registration",
            registration_job_id=facts.get("job_id"),
            operation_run_id=facts.get("run_id"),
        )
    except Exception:
        logger.exception("[浏览器流量] 关联注册任务上下文失败；注册流程继续")
    if profile_id and str(opened.profile_id) != str(profile_id):
        try:
            from core.browser.roxy.profile_binding import persist_account_profile_id

            if not persist_account_profile_id(email, opened.profile_id):
                raise RuntimeError("账号 Roxy Profile 绑定写回失败")
            opened.account_bound = True
            client.mark_profile_bound(opened.profile_id)
            logger.info("[Roxy注册] 账号绑定环境已替换为可用 Profile")
        except Exception:
            logger.exception("[Roxy注册] 回写替代 Profile 绑定失败；停止使用未绑定环境")
            try:
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[Roxy注册] 绑定失败后的替代环境清理失败")
            raise
    driver = retained_driver
    resume_metadata = retained or reopened_retained
    data_saver = None
    public_asset_cache = None
    postprocess_data_saver = None
    profile_discarded = False
    create_acknowledged = False
    openai_password: str | None = None
    password_confirmed = False
    access_token: str | None = None
    core_persisted = False
    account_id: int | None = None
    totp_secret: str | None = None
    plan_check_session = None
    remote_identity = "unknown"
    auth_challenge_chain: list[str] = []
    failed = False
    # 非接管分支已把当前租约写入新开/重开的 Profile；接管窗口仍使用原中继，
    # 不能因该窗口连接失败而隔离服务层刚领到的另一条租约。
    current_lease_route_verified = retained is None and getattr(opened, "proxy_route_retained", False) is False
    resume_login_get_transport_failure = False
    resume_proxy_rotation_ready = False
    cf_proxy_rotation_ready = False
    cf_proxy_rotation_profile_id = ''
    existing_profile_unverified = False
    existing_profile_reconciliation = False
    password_recovery = None
    native_signin_diagnostics = None
    route_observer = None
    route_failure = None
    route_recovery_ready = False
    route_recovery_state = None
    route_close_attempted = False
    route_close_failed = False
    email_entry_waiting = False
    try:
        try:
            from core.registration.debug import attach_current_roxy
            attach_current_roxy(opened.debugger_address)
        except Exception:
            logger.exception("[Roxy注册][Debug] 启动浏览器网络抓包失败；注册流程继续执行")
        if reopened_retained is not None:
            driver = _build_driver(opened)
            # 换线重开只更换连接；原身份、未决回执和邮件时间仍交原恢复围栏核验。
            driver._registration_retained_identity_required = True
            for attr in ("_browser_submission_receipt", "_browser_submission_receipts",
                         "_registration_otp_tracker", "_email_otp_page_refresh_done"):
                if reopened_retained.driver is not None and hasattr(reopened_retained.driver, attr):
                    setattr(driver, attr, getattr(reopened_retained.driver, attr))
            driver._registration_otp_after_ts = reopened_retained.otp_after_ts
            if route_state is not None:
                route_state.restore(driver)
            if (getattr(opened, "created_by_run", False) is True
                    and str(opened.profile_id).strip() != str(reopened_retained.opened.profile_id).strip()):
                # 本轮明确新建的替代环境尚无原认证页；仅清空本地启动页，
                # 再由原恢复检查核验密码与提交事实并选择原身份登录。
                _check_manual_stop()
                driver.get("about:blank")
        if bool(_cfg.ROXY_KEEP_BROWSER_OPEN):
            if retained is not None and driver is not None:
                # 新 Selenium 连接没有旧 driver 属性；首次保存前恢复原邮件
                # 边界，避免在认证页读取失败时把持久时间覆盖为空。
                driver._registration_otp_after_ts = retained.otp_after_ts
            persist_browser_resume_context(driver, opened, email=email, facts=facts)
        if driver is None:
            driver = _build_driver(opened)
        # 每次绑定都重置策略，避免接管旧 driver 时混用本地与开源 Roxy 行为。
        driver._registration_local_roxy_password_entry = _browser_helpers is None
        # 认证事实共用当前 Attempt/Run；CDP 观察器只需从 driver 读取这份只读
        # 上下文，不另起消费者或在事件里复制敏感凭据。
        try:
            from core.registration.service import registration_fact_context
            driver._registration_fact_context = dict(registration_fact_context())
        except Exception:
            driver._registration_fact_context = None
        # 只有明确的 registration_resume Run 才能进入恢复登录 action scope。
        # 普通注册人工重跑即使带着旧密码，也不能借 resume_login 绕过旧未知围栏。
        resume_scope = False
        context = driver._registration_fact_context or {}
        if existing_password and context.get("run_id") is not None:
            try:
                from core.storage import registration

                run = registration.get_run(int(context["run_id"])) or {}
                resume_scope = (
                    str(run.get("action_type") or "") == "registration_resume"
                    and str(run.get("status") or "") in {"queued", "running"}
                )
            except Exception:
                logger.exception("[Roxy注册] 校验 registration_resume Run 失败，关闭恢复提交范围")
        if route_state is not None and existing_password:
            # 普通 registration 同 Run 由业务层另行授予原候选登录派发许可；
            # 仅 prepared 的候选仍用新邮箱前置认证，不改成原账号登录动作。
            private = registration.get_private_resume_context(int(context["attempt_id"]), email=email)
            resume_scope = not registration._route_preauth_authorized(
                private, run_id=context.get("run_id"), execution_id=context.get("execution_id"),
            )
        driver._registration_resume_login = resume_scope
        from core.auth.browser.password_auth import _install_auth_initialization_observer
        _install_auth_initialization_observer(driver)
        from core.browser.asset_policy import start_registration_asset_cache
        public_asset_cache = start_registration_asset_cache(opened, driver=driver, proxy_url=proxy)
        from core.browser.data_saver import BrowserDataSaver
        data_saver = BrowserDataSaver(label="Roxy注册")
        data_saver.install_selenium(driver)
        shared_diagnostics = diagnostics_for(driver)
        if _browser_helpers is None:
            native_signin_diagnostics = _NativeSigninFailureDiagnostics(shared_diagnostics, include_form_entry=True)
            route_observer = RoxyRouteFailureObserver(driver, native_signin_diagnostics.observe_network)
            driver._registration_route_observer = route_observer
        traffic_capture = getattr(opened, "traffic_capture", None)
        if traffic_capture is not None:
            diagnostic_observer = getattr(traffic_capture, "set_auth_diagnostic_observer", None)
            if callable(diagnostic_observer):
                diagnostic_observer((route_observer or native_signin_diagnostics or shared_diagnostics).observe_network)
            setter = getattr(traffic_capture, "set_data_saver", None)
            if callable(setter):
                setter(data_saver)
            observe = getattr(traffic_capture, "set_submission_observer", None)
            if callable(observe):
                observe(_make_submission_observer(driver, monitor_otp_network=_browser_helpers is None))
        from core.registration import plan_capture as registration_plan_capture
        registration_plan_capture.install_selenium(driver)
        report_job_progress("browser", "success", "Roxy 浏览器环境已启动")
        _center_browser_window(driver)
        driver.set_page_load_timeout(int(_cfg.ROXY_SELENIUM_TIMEOUT))
        try:
            driver.set_script_timeout(12)
        except Exception:
            pass
        logger.info("[Roxy注册] 开始：%s，profile=%s", email, opened.profile_id)

        from core.kernels.browser.roxy.registration.runner import RoxyRegistrationState

        authentication_state = RoxyRegistrationState(
            existing_password=existing_password,
            openai_password=openai_password,
            password_confirmed=password_confirmed,
            access_token=access_token,
            account_id=account_id,
            create_acknowledged=create_acknowledged,
            remote_identity=remote_identity,
            auth_challenge_chain=auth_challenge_chain,
            existing_profile_unverified=existing_profile_unverified,
            existing_profile_reconciliation=existing_profile_reconciliation,
            password_recovery=password_recovery,
            email_entry_waiting=email_entry_waiting,
            resume_login_get_transport_failure=resume_login_get_transport_failure,
        )
        try:
            authentication = _run_roxy_authentication(
                driver, email=email, name=name, birthday=birthday, proxy=proxy, otp_code=otp_code,
                existing_password=existing_password, existing_totp_secret=existing_totp_secret,
                profile_id=profile_id, opened=opened, selected_email_source=selected_email_source,
                password_required=password_required, resume_scope=resume_scope, resume_metadata=resume_metadata,
                route_state=route_state, local_browser=_browser_helpers is None,
                route_recovery_enabled=route_callback is not None, cf_rotation_allowed=bool(cf_rotation_context),
                has_retained_browser=retained is not None, current_lease_route_verified=current_lease_route_verified,
                context=context, data_saver=data_saver, route_observer=route_observer,
                native_signin_diagnostics=native_signin_diagnostics, submit_email=submit_email,
                complete_profile=complete_profile, state=authentication_state,
            )
        finally:
            existing_password = authentication_state.existing_password
            openai_password = authentication_state.openai_password
            password_confirmed = authentication_state.password_confirmed
            access_token = authentication_state.access_token
            account_id = authentication_state.account_id
            create_acknowledged = authentication_state.create_acknowledged
            remote_identity = authentication_state.remote_identity
            auth_challenge_chain = authentication_state.auth_challenge_chain
            existing_profile_unverified = authentication_state.existing_profile_unverified
            existing_profile_reconciliation = authentication_state.existing_profile_reconciliation
            password_recovery = authentication_state.password_recovery
            email_entry_waiting = authentication_state.email_entry_waiting
            resume_login_get_transport_failure = authentication_state.resume_login_get_transport_failure
        session_info = authentication.session_info
        lightweight_post_auth = authentication.lightweight_post_auth
        token_budget = authentication.token_budget

        # 注册主体到这里已经成功。先保存账号、随机登录密码和 Token，并立即绑定任务；
        # 再响应停止请求或查询套餐，避免后续操作中断时丢失已经核验的完整会话。
        from core.registration.service import persist_registration_core

        account_id = persist_registration_core(
            email=email,
            access_token=access_token,
            chatgpt_session=session_info,
            email_source=selected_email_source or resolve_email_source(email),
            proxy_used=proxy or None,
            extra={
                "user": session_info.get("user"),
                "account": session_info.get("account"),
                "expires": session_info.get("expires"),
                "roxybrowser": {
                    "profile_id": opened.profile_id,
                    "open_result": opened.raw,
                    "retained": True,
                },
                **registration_password_extra(openai_password, confirmed=password_confirmed),
                "registration_checkpoint": "core_persisted",
                "registration_driver": registration_driver,
            },
        )
        core_persisted = True
        if route_observer is not None:
            route_observer.begin_stage(driver, "completed")
        opened.account_bound = True
        client.mark_profile_bound(opened.profile_id)
        logger.info("[Roxy注册] 注册主体已保存检查点：id=%s email=%s", account_id, email)

        _check_manual_stop()
        # 先保留首页自然返回的权益快照，避免后续安全设置导航清空页面内缓存。
        # 此处不等待、不主动请求；需要补查时统一计入最后的套餐阶段。
        captured_plan_result = None
        if plan_check_enabled and lightweight_post_auth:
            captured_plan_result = registration_plan_capture.read_selenium(driver, access_token, wait_seconds=0)

        if lightweight_post_auth:
            from core.auth.browser.session_auth import _park_verified_registration_page

            data_saver.activate_post_auth()
            parked = _park_verified_registration_page(driver, budget=token_budget, check_stop=_check_manual_stop)
            logger.info("[Roxy注册] 省流量后处理：轻量同源页面=%s，跳过完整首页加载", parked)
            report_job_progress("token", "success", "已保存完整登录会话，省流量模式跳过完整首页加载")
        else:
            report_job_progress("token", "running", "登录会话已保存，正在确认正常首页就绪")
            try:
                homepage = _wait_registration_homepage(driver, budget=token_budget)
            except StageTimeout:
                # 会话已保存；可选首页观察不能成为再次注册的理由。
                homepage = {"ready": False, "reason": "timeout"}
            if homepage["ready"]:
                if data_saver is not None:
                    data_saver.activate_post_auth()
                report_job_progress("token", "success", "已获取 accessToken，正常首页已就绪")
            else:
                logger.warning("[Roxy注册] 首页未确认就绪，保持核心资源加载：reason=%s", homepage["reason"])
                report_job_progress("token", "success", "已获取 accessToken；首页未确认就绪，保持核心资源加载")
            if plan_check_enabled:
                captured_plan_result = registration_plan_capture.read_selenium(driver, access_token, wait_seconds=0)

        codex_result = {
            "status": "skipped",
            "ok": True,
            "message": "ENABLE_CODEX_AUTO=False，跳过 Codex",
        }
        try:
            if codex_enabled:
                report_job_progress("codex", "running", "正在执行 Codex OAuth")
                # 注册流程本身已创建 Roxy 一号一环境。这里不能再新建第二个 Roxy 环境；
                # 复用当前注册窗口并保留刚建立的登录态，直接开始 Codex 授权。
                from core.codex.roxy.oauth import run_roxy_codex_oauth
                logger.info("[Roxy注册][Codex] ENABLE_CODEX_AUTO=True，复用当前注册 Roxy 窗口执行 Codex 授权，不创建新环境")
                _check_manual_stop()
                codex_kwargs = {}
                if selected_email_source is not None:
                    codex_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                        address,
                        email_source=selected_email_source,
                        **kwargs,
                    )
                codex_result = _run_in_isolated_browser_tab(
                    driver,
                    lambda: run_roxy_codex_oauth(
                        email,
                        proxy=proxy,
                        reuse_existing_profile=True,
                        existing_driver=driver,
                        existing_opened=opened,
                        force=True,
                        # 当前 Roxy 环境刚完成这个账号的注册，保留登录态可直接进入
                        # consent/手机验证；若登录态不可复用，页面仍会回落到邮箱 OTP。
                        clear_existing_state=False,
                        **codex_kwargs,
                    ),
                    label="Codex OAuth",
                )
                report_job_progress(
                    "codex",
                    "success" if codex_result.get("ok") else "failed",
                    str(codex_result.get("message") or "Codex OAuth 已完成")[:300],
                )
            else:
                logger.info("[Roxy注册][Codex] ENABLE_CODEX_AUTO=False，注册后跳过 Codex OAuth")
                report_job_progress("codex", "skipped", "未启用 Codex 自动授权")
        except AccountUnusableError:
            raise
        except Exception as exc:
            codex_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            report_job_progress("codex", "failed", codex_result["message"])

        browser_twofa_prepared = False

        def _rebind_twofa_route(current) -> None:
            """2FA 同栈换线只替换连接，核心账号和已完成后处理均保留。"""
            nonlocal driver, opened, proxy, route_observer, native_signin_diagnostics
            nonlocal data_saver, public_asset_cache, postprocess_data_saver
            nonlocal plan_check_session
            if route_callback is None or route_observer is None:
                raise RoxyRouteFailureSignal(current[0])
            _check_manual_stop()
            from core.registration.debug import current_session
            debug_session = current_session()
            if debug_session is not None:
                debug_session.capture_page_snapshot(driver, "注册内 MFA 当前请求换线")
            from core.browser.traffic import finish_roxy_capture, bind_roxy_capture
            finish_roxy_capture(opened)
            if route_observer.current(driver) != current:
                raise RuntimeError("mfa_route_evidence_stale: MFA 请求已有新进展，撤销旧线路失败")
            if not client.close_profile(opened.profile_id) or client.get_open_profile_connection(opened.profile_id) is not None:
                raise RuntimeError("mfa_route_close_unconfirmed: 原 Profile 关闭未确认，保留账号与密钥检查点")
            # 注册协议 MFA 与后续套餐曾共用这个会话；旧线路释放前销毁它，
            # 后续套餐按新的 proxy 建连接，不能继承旧租约或旧线路熔断。
            if plan_check_session is not None:
                plan_check_session.close()
                plan_check_session = None
            route_observer.begin_stage(driver, "completed")
            _check_manual_stop()
            next_lease = route_callback(current[0], proxy)
            if next_lease is None:
                raise RuntimeError("mfa_route_budget_exhausted: 注册换线额度已耗尽，保留账号与密钥检查点")
            from core.browser.asset_policy import stop_registration_asset_cache
            stop_registration_asset_cache(public_asset_cache)
            public_asset_cache = None
            if data_saver is not None:
                data_saver.stop()
            data_saver = None
            if postprocess_data_saver is not None:
                postprocess_data_saver.stop()
            postprocess_data_saver = None
            old_driver = driver
            _quit_driver(old_driver)
            next_proxy = str(next_lease.proxy_url)
            replacement = _open_roxy_profile_with_capacity_wait(
                client, next_proxy, profile_id=opened.profile_id, preclosed_profile=True,
                progress_callback=report_job_progress, data_saver_flow="registration",
            )
            if str(replacement.profile_id) != str(opened.profile_id):
                raise RuntimeError("mfa_route_profile_changed: MFA 换线必须保留原 Profile")
            opened = replacement
            opened.account_bound = True
            proxy = next_proxy
            driver = _build_driver(opened)
            driver._registration_local_roxy_password_entry = True
            driver._registration_fact_context = dict(facts)
            driver._registration_resume_login = resume_scope
            shared = diagnostics_for(driver)
            route_observer = RoxyRouteFailureObserver(driver, shared.observe_network)
            driver._registration_route_observer = route_observer
            native_signin_diagnostics = None
            _check_manual_stop()
            bind_roxy_capture(opened, purpose="registration", registration_job_id=facts.get("job_id"),
                              operation_run_id=facts.get("run_id"))
            capture = getattr(opened, "traffic_capture", None)
            if capture is not None:
                setter = getattr(capture, "set_auth_diagnostic_observer", None)
                if callable(setter):
                    setter(route_observer.observe_network)
                setter = getattr(capture, "set_submission_observer", None)
                if callable(setter):
                    setter(_make_submission_observer(driver, monitor_otp_network=True))
            from core.auth.browser.password_auth import _install_auth_initialization_observer
            _install_auth_initialization_observer(driver)
            driver.set_page_load_timeout(int(_cfg.ROXY_SELENIUM_TIMEOUT))
            route_observer.begin_stage(driver, "twofa")
            _prepare_browser_twofa()

        def _run_browser_twofa_with_routes(action, checkpoint_secret) -> str:
            pending_failure = None
            while True:
                _check_manual_stop()
                if route_observer is not None:
                    route_observer.begin_stage(driver, "twofa")
                try:
                    if pending_failure is None:
                        return action()
                    return continue_browser_twofa(
                        driver, email, failure=pending_failure, existing_secret=totp_secret,
                        action=action, on_secret=checkpoint_secret, check_stop=_check_manual_stop,
                    )
                except Exception:
                    current = route_observer.current(driver) if route_observer is not None else None
                    if (current is None or route_callback is None or not current_lease_route_verified
                            or current[0].operation not in {"twofa_enroll", "twofa_activate", "otp_send", "otp_validate"}):
                        raise
                    pending_failure = current[0]
                    _rebind_twofa_route(current)

        def _prepare_browser_twofa():
            nonlocal postprocess_data_saver, browser_twofa_prepared
            if route_observer is not None and route_callback is not None:
                route_observer.raise_if_failed(driver)
            # 只有实际进入浏览器设置时才恢复核心资源，协议成功不启动首页。
            browser_twofa_prepared = True
            postprocess_data_saver = _install_registration_postprocess_data_saver(
                opened,
                driver,
            )

        # 先跑 Codex，最大化复用注册完成后的 auth.openai.com 账号选择态；
        # 未完成的 MFA enrollment 会改变授权页状态，不能放在 Codex 前面。
        account_id = _save_roxy_account_checkpoint(
            email=email,
            access_token=access_token,
            session_info=session_info,
            opened=opened,
            openai_password=openai_password,
            password_confirmed=password_confirmed,
            proxy=proxy,
            email_source=selected_email_source,
            codex_result=codex_result,
            registration_driver=registration_driver,
        )
        report_registered_account(account_id)

        twofa_result = {
            "status": "skipped",
            "ok": True,
            "message": "ENABLE_2FA=False，跳过 Authenticator 2FA",
        }
        if twofa_enabled:
            report_job_progress("twofa", "running", "正在设置 Authenticator 2FA")
            try:
                def _checkpoint_totp_secret(secret: str) -> None:
                    nonlocal account_id, totp_secret
                    totp_secret = secret
                    account_id = _save_roxy_account_checkpoint(
                        email=email,
                        access_token=access_token,
                        session_info=session_info,
                        opened=opened,
                        openai_password=openai_password,
                        password_confirmed=password_confirmed,
                        proxy=proxy,
                        email_source=selected_email_source,
                        totp_secret=totp_secret,
                        codex_result=codex_result,
                        registration_driver=registration_driver,
                        twofa_result={
                            "status": "running",
                            "ok": False,
                            "message": "已保存 Authenticator key，正在激活 2FA",
                        },
                    )
                    report_registered_account(account_id)
                    logger.info("[Roxy注册][2FA] Authenticator key 已写入账号检查点，准备激活")

                twofa_driver = _twofa_cfg.get_twofa_driver_for_options(options)
                twofa_kwargs = {"on_secret": _checkpoint_totp_secret}
                if _browser_helpers is None:
                    twofa_kwargs["monitor_mfa_enrollment"] = True
                if selected_email_source is not None:
                    twofa_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                        address,
                        email_source=selected_email_source,
                        **kwargs,
                    )
                if twofa_driver == "protocol":
                    protocol_session = BrowserSession(proxy=proxy or "")
                    plan_check_session = protocol_session
                    fallback_used = False
                    if _browser_helpers is None and route_callback is not None:
                        first_protocol_call = True
                        observed_protocol = RegistrationTwofaSession(protocol_session, driver_getter=lambda: driver)

                        def run_protocol_then_original_browser():
                            nonlocal first_protocol_call, fallback_used
                            if first_protocol_call:
                                first_protocol_call = False
                                secret, fallback_used = setup_protocol_2fa_with_browser_fallback(
                                    driver, email, observed_protocol, access_token,
                                    before_browser=_prepare_browser_twofa, **twofa_kwargs,
                                )
                                return secret
                            # 已经换线后只续接原 MFA 动作；协议旧 Session 的熔断
                            # 不套到新浏览器，也不重做已经提交过的 enrollment。
                            fallback_used = True
                            _prepare_browser_twofa()
                            return setup_roxy_2fa(driver, email, **twofa_kwargs)

                        totp_secret = _run_browser_twofa_with_routes(
                            run_protocol_then_original_browser, _checkpoint_totp_secret,
                        )
                    else:
                        totp_secret, fallback_used = setup_protocol_2fa_with_browser_fallback(
                            driver, email, protocol_session, access_token,
                            before_browser=_prepare_browser_twofa, **twofa_kwargs,
                        )
                    twofa_result = {
                        "status": "success",
                        "ok": True,
                        "message": (
                            "协议失败后已通过浏览器 UI 启用 2FA"
                            if fallback_used
                            else "协议 2FA 已启用"
                        ),
                        "driver": "browser_fallback" if fallback_used else "protocol",
                    }
                else:
                    _prepare_browser_twofa()
                    totp_secret = _run_browser_twofa_with_routes(
                        lambda: setup_roxy_2fa(driver, email, **twofa_kwargs),
                        _checkpoint_totp_secret,
                    ) if _browser_helpers is None else setup_roxy_2fa(driver, email, **twofa_kwargs)
                    twofa_result = {
                        "status": "success",
                        "ok": True,
                        "message": "浏览器 2FA 已启用",
                        "driver": "browser",
                    }
                report_job_progress("twofa", "success", twofa_result["message"])
            except Exception as exc:
                message = f"{type(exc).__name__}: {str(exc)[:180]}"
                twofa_result = {"status": "failed", "ok": False, "message": message}
                logger.error("[Roxy注册][2FA] 设置失败：%s", message)
                logger.debug("[Roxy注册][2FA] 错误详情", exc_info=True)
                report_job_progress("twofa", "failed", f"2FA 设置失败: {message}")
            finally:
                if route_observer is not None:
                    route_observer.begin_stage(driver, "completed")
        else:
            report_job_progress("twofa", "skipped", "未启用 Authenticator 2FA")

        account_id = _save_roxy_account_checkpoint(
            email=email,
            access_token=access_token,
            session_info=session_info,
            opened=opened,
            openai_password=openai_password,
            password_confirmed=password_confirmed,
            proxy=proxy,
            email_source=selected_email_source,
            totp_secret=totp_secret,
            codex_result=codex_result,
            twofa_result=twofa_result,
            registration_driver=registration_driver,
        )
        report_registered_account(account_id)

        if lightweight_post_auth and browser_twofa_prepared and twofa_result.get("ok"):
            # 设置已确认并保存；保留窗口也不继续加载设置页的后台资源。
            _park_verified_registration_page(driver, budget=StageBudget.start(10), check_stop=_check_manual_stop)

        # Final account metadata is updated by the existing checkpoint helper.
        # Plan lookup is independent work and is queued after the core account
        # has already been persisted, so a network failure cannot roll back
        # registration success.
        plan_result = {"status": "pending", "ok": False, "message": "套餐查询已独立入队"}
        if plan_check_enabled:
            _check_manual_stop()
            report_job_progress("plan_check", "running", "正在查询注册会话中的套餐与 Plus 优惠资格")
            plan_started = time.monotonic()
            try:
                # 在同一个阶段完成套餐捕获与额度读取，计时不再跨越首页观察和 2FA。
                try:
                    if captured_plan_result is None:
                        captured_plan_result = registration_plan_capture.read_or_fetch_selenium(driver, access_token)
                except Exception as exc:
                    logger.warning("[Roxy注册][套餐] 浏览器查询失败，将尝试后台查询：%s", type(exc).__name__)
                from core import db
                if isinstance(captured_plan_result, dict) and captured_plan_result.get("ok"):
                    captured = dict(captured_plan_result)
                    if not captured.get("quota_status"):
                        from core.accounts.plans.client import query_account_quota
                        captured.update(query_account_quota(
                            access_token,
                            proxy=proxy or None,
                            session=plan_check_session,
                        ))
                    captured["trigger"] = "registration_browser_response"
                    db.update_account_plan_check(acc_id=account_id, result=captured)
                    plan_result = {"status": "success", "ok": True, "message": "复用浏览器权益数据"}
                else:
                    from core.accounts.plans.service import enqueue_account_plan_check
                    queued = enqueue_account_plan_check(
                        account_id=account_id,
                        email=email,
                        access_token=access_token,
                        trigger="registration_auto",
                    )
                    plan_result = {
                        "status": "pending" if queued.get("accepted") or queued.get("busy") else "failed",
                        "ok": False,
                        "message": (
                            "套餐查询已提交后台任务，等待查询结果"
                            if queued.get("accepted")
                            else "账号已有套餐查询，等待查询结果"
                            if queued.get("busy")
                            else str(queued.get("error") or "套餐查询未入队")
                        ),
                    }
            except Exception as exc:
                plan_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            finally:
                source = (captured_plan_result or {}).get("source", "browser_response") if isinstance(captured_plan_result, dict) else "background_queue"
                logger.info("[Roxy注册][套餐] 本轮查询结束：耗时=%.3fs 来源=%s 状态=%s",
                            max(0.0, time.monotonic() - plan_started), source, plan_result["status"])
        else:
            plan_result = {"status": "skipped", "ok": True, "message": "未启用注册后自动查套餐"}
        if plan_check_enabled:
            report_job_progress(
                "plan_check",
                plan_result["status"] if plan_result["status"] in {"success", "failed"} else "pending",
                plan_result["message"],
            )
        codex_ok = codex_result.get("ok") or codex_result.get("status") == "skipped"
        twofa_ok = twofa_result.get("ok") or twofa_result.get("status") == "skipped"
        errors = []
        if not codex_ok:
            errors.append(f"Codex 未完成: {codex_result.get('message')}")
        if not twofa_ok:
            errors.append(f"2FA 未完成: {twofa_result.get('message')}")
        if not plan_result.get("ok"):
            errors.append(f"套餐查询待处理: {plan_result.get('message')}")
        if password_required and not password_confirmed:
            errors.append("账号已取得 Token；恢复候选尚未确认有效，需要补全密码")
        postprocess_ok = bool(codex_ok and twofa_ok and plan_result.get("ok")
                              and (not password_required or password_confirmed))
        from core.registration.postprocess import summarize_postprocess
        readiness = summarize_postprocess(
            core_success=True,
            password_present=password_confirmed,
            outcomes={"twofa": twofa_result, "codex": codex_result, "plan_check": plan_result},
            password_required=password_required,
            twofa_required=twofa_enabled,
            codex_enabled=codex_enabled,
            plan_check_required=plan_check_enabled,
        )
        return {
            # 账号和 Token 已在前面的检查点落库，注册主体就是成功。Codex/2FA
            # 属于后置能力，失败时返回部分成功，不能让服务层误判为“没注册出账号”。
            "success": True,
            "registration_success": True,
            "core_persisted": core_persisted,
            "postprocess_success": postprocess_ok,
            "partial_success": not postprocess_ok,
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "codex": codex_result,
            "twofa": twofa_result,
            "plan_check": plan_result,
            "next_actions": [action.as_dict() for action in readiness.next_actions],
            "account_readiness": readiness.account_readiness,
            "password_validated": password_confirmed,
            "remote_identity": remote_identity,
            "remote_identity_state": "confirmed",
            "registration_intent": "reconcile" if remote_identity == "existing" else "new",
            "auth": auth_result_for_registration(
                {"success": True},
                auth_method=registration_driver,
                remote_identity=remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
            "error": None if not errors else "; ".join(errors),
        }
    except Exception as exc:
        failed = True
        route_current = (
            route_observer.current(driver)
            if route_observer is not None and current_lease_route_verified and not core_persisted
            else None
        )
        route_failure = route_current[0] if route_current is not None else None
        native_failure_diagnostic = (
            native_signin_diagnostics.failure_diagnostic(driver)
            if native_signin_diagnostics is not None and email_entry_waiting
            and isinstance(exc, (StageTimeout, _EmailSubmissionUnknown, RoxyRouteFailureSignal))
            else {}
        )
        failure_note = (
            "; auth_cloudflare_challenge: 认证入口请求返回 HTTP 403，Cloudflare 挑战阻断邮箱入口"
            if native_failure_diagnostic else ""
        )
        logger.error("[Roxy注册] 失败：%s: %s%s", type(exc).__name__, exc, failure_note)
        logger.debug("[Roxy注册] 失败详情", exc_info=True)
        try:
            from core.registration.service import is_stop_requested
            stopped = is_stop_requested()
        except Exception:
            stopped = False
        if not stopped:
            try:
                if driver is not None:
                    log_submission_diagnostics(driver, diagnostics_for(driver).stage, "final_failure",
                                               receipt=getattr(driver, "_browser_submission_receipt", None))
                if (route_current is not None and route_callback is not None
                        and not (core_persisted or access_token)):
                    from core.registration.debug import current_session
                    debug_session = current_session()
                    if debug_session is not None:
                        debug_session.capture_page_snapshot(driver, f"{type(exc).__name__}: 当前注册请求换线")
                    from core.browser.traffic import finish_roxy_capture
                    finish_roxy_capture(opened)
                    # 迟到成功、新请求或导航均撤销旧证据；关闭确认前绝不领取新线。
                    if route_observer.current(driver) == route_current:
                        # 先排空已接纳的响应回执，再记录明确拒绝与恢复现场；
                        # 不能因旁路线程尚未写完 response_binding 就误判未知。
                        record_current_refusal(driver, route_current)
                        route_recovery_state = make_recovery_state(
                            driver, opened, email=email, facts=facts,
                            failure=route_failure, password=openai_password or existing_password,
                        )
                        route_close_attempted = True
                        route_recovery_ready = client.close_profile(opened.profile_id) is True
                        route_recovery_ready = (
                            route_recovery_ready and client.get_open_profile_connection(opened.profile_id) is None
                        )
                        route_close_failed = not route_recovery_ready
                    else:
                        route_failure = None
                        route_recovery_state = None
                    if route_recovery_ready:
                        logger.info("[Roxy注册] 当前关键请求线路失败，已关闭原环境并保留同身份恢复现场")
                if (route_callback is None and native_failure_diagnostic and cf_rotation_context.get('retry_available') is True
                        and current_lease_route_verified and retained is None
                        and not (core_persisted or create_acknowledged or access_token)):
                    from core.registration.debug import current_session
                    debug_session = current_session()
                    if debug_session is not None:
                        debug_session.capture_page_snapshot(driver, f'{type(exc).__name__}: CF 认证挑战换线')
                    # 保存证据可能耗时；较新的认证请求或导航一旦出现就撤销旧挑战许可。
                    if native_signin_diagnostics.failure_diagnostic(driver) == native_failure_diagnostic:
                        from core.browser.traffic import finish_roxy_capture
                        finish_roxy_capture(opened)
                        # 采集收口会排空迟到事件，再次确认后才能关闭本轮挑战连接。
                        still_challenged = native_signin_diagnostics.failure_diagnostic(driver) == native_failure_diagnostic
                        if not still_challenged:
                            native_failure_diagnostic = {}
                        closed = still_challenged and client.close_profile(opened.profile_id) is True
                        closed = closed and client.get_open_profile_connection(opened.profile_id) is None
                        if closed and opened.created_by_run and not opened.account_bound:
                            deleted = client.delete_profile(opened.profile_id) is True
                            deleted = deleted and _confirmed_cf_profile_deleted(client, opened.profile_id)
                            if deleted:
                                profile_discarded = True
                                from core.browser.roxy.client import _untrack_created_profile
                                try:
                                    _untrack_created_profile(opened.profile_id)
                                except Exception:
                                    logger.exception('[Roxy注册] 临时环境已进入回收站，本地清理登记待后续收口')
                                cf_proxy_rotation_ready = True
                        elif closed:
                            cf_proxy_rotation_profile_id = str(opened.profile_id)
                            cf_proxy_rotation_ready = True
                        if cf_proxy_rotation_ready:
                            logger.info('[Roxy注册] 当前认证入口已确认 CF 挑战，环境已关闭，交回同身份换 IP 重试')
                    else:
                        native_failure_diagnostic = {}
                if (route_callback is None and resume_login_get_transport_failure
                        and rotation_context.get("retry_available") is True):
                    from core.registration.debug import current_session

                    reason = f"{type(exc).__name__}: {str(exc)[:500]}"
                    debug_session = current_session()
                    if debug_session is not None:
                        # 中间线路失败只存快照，不把整个 Run 标成已捕获最终失败，
                        # 否则下一条线路的真正终态会失去现场。
                        debug_session.capture_page_snapshot(driver, reason)
                    from core.browser.traffic import finish_roxy_capture

                    finish_roxy_capture(opened)
                    # 只关闭本轮尚未提交认证 POST 的失败连接；不删除 Profile、
                    # Cookie 或旧未知事实。关闭未确认时不向服务层开放换线。
                    resume_proxy_rotation_ready = client.close_profile(opened.profile_id) is True
            except Exception:
                if route_close_attempted and not route_recovery_ready:
                    route_close_failed = True
                logger.exception("[Roxy注册] 保存换线现场或关闭失败连接未完成，保留原窗口")
            if not native_failure_diagnostic:
                failure_note = ''
            if not (route_recovery_ready or resume_proxy_rotation_ready or cf_proxy_rotation_ready):
                try:
                    from core.registration.debug import pause_current_failure
                    pause_current_failure(driver, f"{type(exc).__name__}: {str(exc)[:500]}{failure_note}")
                except Exception:
                    logger.exception("[Roxy注册][Debug] 保留失败现场失败；继续按原失败流程收口")
        # 未确认创建前通常可以回收邮箱；但 password 模式下缺少创建密码入口时，
        # 该地址可能已经在 OpenAI 侧进入已有账号/半成品账号状态。继续放回池里只会
        # 让后续任务反复命中登录 OTP 页，永远无法完成“账号+密码”注册。
        password_result_unknown = isinstance(exc, _PasswordTransitionTimeout)
        email_result_unknown = isinstance(exc, _EmailSubmissionUnknown) or (
            isinstance(exc, AuthPageError) and email_entry_waiting
            and bool(getattr(exc, "submission_unknown", False))
        )
        error_text = str(exc)
        from core.storage.accounts.password_recovery import PasswordRecoveryError

        password_recovery_error_code = (
            f"password_recovery_{exc.code}" if isinstance(exc, PasswordRecoveryError)
            else next((code for code in ("password_recovery_owner_missing", "password_recovery_unconfirmed")
                       if error_text.startswith(f"{code}:")), "")
        )
        account_unusable = isinstance(exc, AccountUnusableError)
        pre_account_transport_failure = _is_disposable_pre_account_failure(
            error_text,
            create_acknowledged=create_acknowledged,
            account_id=account_id,
        ) and not (password_result_unknown or email_result_unknown or existing_profile_unverified
                   or isinstance(exc, EmailOtpNetworkError))
        request_unknown = (
            password_result_unknown or existing_profile_unverified or _is_registration_request_unknown(exc)
            or (isinstance(exc, PasswordPageError) and bool(existing_password))
            or (route_recovery_state is not None and route_recovery_state.restart_identity_login
                and route_failure is not None and not route_failure.response_received)
        ) and not pre_account_transport_failure
        remote_existing = (
            isinstance(exc, RemoteExistingAccountError) or remote_identity == "existing"
        ) and not existing_profile_unverified
        password_rejected = isinstance(exc, PasswordRejectedError)
        account_create_rejected = "account_create_rejected" in error_text.lower()
        password_entry_error_code = next(
            (
                code
                for marker, code in (
                    ("registration_password_entry_unavailable", "registration_password_entry_unavailable"),
                    ("password_entry_navigation_failed", "password_entry_navigation_failed"),
                    ("profile_completion_required", "profile_completion_required"),
                    ("password_entry_page_not_hydrated", "workflow.password_entry_not_hydrated"),
                    ("password_entry_not_offered", "workflow.password_entry_not_offered"),
                    ("password_entry_recovery_exhausted", "workflow.password_entry_recovery_exhausted"),
                )
                if marker in error_text.lower()
            ),
            None,
        )
        if getattr(exc, "code", "") == "password_entry_navigation_failed":
            password_entry_error_code = "password_entry_navigation_failed"
        mfa_secret_missing = isinstance(exc, MfaSecretMissingError) or any(marker in error_text.lower() for marker in (
            "缺少可用密码或 totp",
            "没有 totp 密钥",
            "没有可用 totp",
            "mfa_secret_missing",
        ))
        disposable_proxy_failure = (
            pre_account_transport_failure and not resume_login_get_transport_failure
            and not (route_callback is not None and route_failure is not None)
        )
        if disposable_proxy_failure and opened.created_by_run:
            try:
                client.discard_profile(opened)
                profile_discarded = True
                logger.info(
                    "[Roxy注册] 注册前阶段失败且未产生远端账号状态，已软删除临时环境释放重试额度：profile=%s",
                    opened.profile_id,
                )
            except Exception:
                logger.exception("[Roxy注册] 释放代理失败临时环境时出错；保留原失败结果")
        try:
            if account_unusable:
                from core.email.provider import mark_email_permanently_unusable

                mark_email_permanently_unusable(
                    email,
                    source=selected_email_source,
                    note=f"上游明确确认账号永久失效: {error_text[:180]}",
                )
            else:
                from core.email.provider import retain_email

                retain_email(
                    email,
                    source=selected_email_source,
                    note=f"Roxy注册中途失败，保留给原任务链: {error_text[:180]}",
                )
        except Exception:
            pass
        auth_remote_identity = "existing" if remote_existing else remote_identity
        auth_error_code = (
            ProfileAccountAlreadyExistsError.error_type
            if existing_profile_reconciliation
            else password_recovery_error_code
            if password_recovery_error_code
            else
            exc.code
            if isinstance(exc, (PasswordPageError, AuthPageError, EmailOtpNetworkError))
            else
            "password_rejected"
            if password_rejected
            else "account_create_rejected"
            if account_create_rejected
            else password_entry_error_code
            if password_entry_error_code
            else "mfa_secret_missing"
            if mfa_secret_missing
            else
            "remote_existing"
            if remote_existing
            else "request_unknown"
            if request_unknown
            else "registration_failed"
        )
        error_prefix = (
            f"{auth_error_code}: "
            if auth_error_code and auth_error_code.casefold() not in error_text.casefold()
            else ""
        )
        return {
            "success": False,
            "route_failure": route_failure,
            "route_recovery_ready": route_recovery_ready,
            "route_recovery_profile_id": str(opened.profile_id) if route_recovery_ready else "",
            "route_recovery_state": route_recovery_state if route_recovery_ready else None,
            **native_failure_diagnostic,
            **({"cause_code": exc.code} if isinstance(exc, AuthPageError) else {}),
            **({"cause_code": exc.cause_code} if isinstance(exc, EmailOtpNetworkError) else {}),
            **({"cause_code": password_recovery_error_code} if password_recovery_error_code else {}),
            **({"cause_code": password_entry_error_code} if password_entry_error_code else {}),
            'cf_proxy_rotation_ready': cf_proxy_rotation_ready,
            'cf_proxy_rotation_profile_id': cf_proxy_rotation_profile_id if cf_proxy_rotation_ready else '',
            **({'cf_proxy_rotation_context': {key: facts[key] for key in (
                'job_id', 'attempt_id', 'run_id', 'execution_id',
            )}} if native_failure_diagnostic and cf_rotation_context and current_lease_route_verified else {}),
            **({"cause_code": ProfileAccountAlreadyExistsError.error_type, "register_response_confirmed": True}
               if existing_profile_reconciliation else {}),
            **({"cause_code": "registration_route_close_failed"} if route_close_failed else {}),
            # OTP页面识别只细化原因，不改变既有换线许可或代理故障惩罚。
            "proxy_transport_failure": not isinstance(exc, EmailOtpNetworkError) and _is_registration_proxy_transport_failure(exc),
            "current_lease_route_verified": current_lease_route_verified,
            "resume_login_get_transport_failure": resume_login_get_transport_failure,
            "resume_proxy_rotation_ready": resume_proxy_rotation_ready,
            "resume_proxy_rotation_profile_id": str(opened.profile_id) if resume_proxy_rotation_ready else "",
            "core_persisted": core_persisted,
            "registration_pending": bool(account_id and not access_token),
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "request_unknown": request_unknown,
            **({"current_password_not_submitted": True} if isinstance(exc, PasswordPageError)
               and getattr(exc, "not_submitted", False) else {}),
            "email_submission_unconfirmed": bool(email_result_unknown and not create_acknowledged and account_id is None),
            "manual_reconcile": remote_existing,
            "remote_identity": "existing" if remote_existing else remote_identity,
            "remote_identity_state": "confirmed" if remote_existing else "unknown",
            "remote_account_state": "confirmed" if remote_existing else "request_unknown" if request_unknown else "not_started",
            "error_code": auth_error_code,
            "email_permanently_unusable": account_unusable,
            "account_unusable_error_code": (
                exc.error_code or "account_deactivated"
                if account_unusable
                else None
            ),
            "auth": auth_result_for_registration(
                {"success": False, "error_code": auth_error_code,
                 **({"request_unknown": request_unknown} if isinstance(exc, (AuthPageError, EmailOtpNetworkError)) else {})},
                auth_method=registration_driver,
                remote_identity=auth_remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
            "error": (
                f"{error_prefix}{type(exc).__name__}: {str(exc)[:300]}{failure_note}"
                + ("; registration_route_close_failed: 原 Profile 关闭未确认，未释放旧线路或领取新线路"
                   if route_close_failed else "")
            ),
        }
    finally:
        if postprocess_data_saver is not None:
            try:
                postprocess_data_saver.stop()
            except Exception:
                logger.exception("[Roxy注册] 收口注册后账号操作省流量统计失败")
        from core.browser.asset_policy import stop_registration_asset_cache
        stop_registration_asset_cache(public_asset_cache)
        if data_saver is not None:
            try:
                data_saver.stop()
            except Exception:
                logger.exception("[Roxy注册] 收口省流量统计失败")
        if not profile_discarded:
            try:
                from core.browser.traffic import finish_roxy_capture
                # Profiler 需要活着的 CDP target，必须先于 driver.quit 收口。
                finish_roxy_capture(opened)
            except Exception:
                logger.exception("[Roxy注册] 收口浏览器流量与执行覆盖率失败")
        if driver and not profile_discarded and (route_recovery_ready or resume_proxy_rotation_ready or cf_proxy_rotation_ready
                                                  or not bool(_cfg.ROXY_KEEP_BROWSER_OPEN)):
            try:
                _quit_driver(driver)
            except Exception:
                pass
        if not profile_discarded and not (route_recovery_ready or resume_proxy_rotation_ready or cf_proxy_rotation_ready):
            try:
                client.cleanup_profile(opened)
            finally:
                if failed and driver is not None and bool(_cfg.ROXY_KEEP_BROWSER_OPEN):
                    try:
                        persist_browser_resume_context(driver, opened, email=email, facts=facts)
                    except Exception:
                        logger.error("[Roxy注册] 原窗口恢复关联保存失败，仍保留当前进程连接")
                    retain_failed_browser(driver, opened, email=email, facts=facts)
        if driver is not None and _browser_helpers is None:
            driver._registration_route_observer = None
        if plan_check_session is not None:
            try:
                plan_check_session.session.close()
            except Exception:
                pass
