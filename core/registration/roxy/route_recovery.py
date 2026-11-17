"""本地 Roxy 当前动作的线路证据与进程内同环境恢复状态。"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
import threading
import time
from types import SimpleNamespace
from typing import Any

from core.auth.browser.browser_submission import (
    BrowserSubmissionReceipt, record_browser_submission_fact, unresolved_submission_ids,
)
from core.registration.route_recovery import (
    RegistrationRouteFailure, registration_request_operation, registration_route_failure,
)
from core.auth.state_machine import StageBudget


class RoxyRouteFailureSignal(RuntimeError):
    """在原认证线程的下一个检查点停止旧线路，观察线程不执行恢复。"""

    def __init__(self, failure: RegistrationRouteFailure) -> None:
        self.failure = failure
        reason = f"HTTP {failure.http_status}" if failure.response_received else failure.transport_kind
        super().__init__(f"registration_route_failed: 当前 {failure.operation} 请求线路失败（{reason}）")


_STAGES = {
    "session": frozenset({"session", "auth_session", "callback"}),
    "preauth": frozenset({"preauth", "email_submit", "callback"}),
    "password": frozenset({"preauth", "email_submit", "password_create", "password_verify",
                           "otp_send", "callback"}),
    "otp": frozenset({"otp_send", "otp_validate", "callback"}),
    "profile": frozenset({"profile_submit", "callback"}),
    "twofa": frozenset({"twofa_enroll", "twofa_activate", "otp_send", "otp_validate"}),
}
_DRIVER_STATE_FIELDS = (
    "_browser_submission_receipt", "_browser_submission_receipts",
    "_registration_otp_tracker", "_email_otp_page_refresh_done",
    "_registration_otp_after_ts", "_registration_password_creation_chain",
)


def _target(driver) -> str:
    try:
        handle = driver.current_window_handle
        value = handle.removeprefix("CDwindow-") if isinstance(handle, str) else ""
        return value if re.fullmatch(r"[A-Za-z0-9_-]{1,160}", value) else ""
    except Exception:
        return ""


class RoxyRouteFailureObserver:
    """只接纳本动作开始之后、同一标签页且请求/响应已配对的关键失败。"""

    def __init__(self, driver, diagnostic_observer=None, *, wall_clock=None) -> None:
        self._clock = wall_clock or time.time
        self._diagnostic_observer = diagnostic_observer
        self._lock = threading.RLock()
        self._target = ""
        self._started = 0.0
        self._operations = frozenset()
        self._latest = None
        self.begin_stage(driver, "session")

    def begin_stage(self, driver, stage: str) -> None:
        with self._lock:
            self._target = _target(driver)
            self._started = self._clock()
            self._operations = _STAGES.get(stage, frozenset())
            self._latest = None

    def observe_network(self, record, *, phase: str) -> None:
        if callable(self._diagnostic_observer):
            try:
                self._diagnostic_observer(record, phase=phase)
            except Exception:
                # 只读诊断写入与业务线路控制相互独立；观察器失败不能关闭恢复。
                pass
        if not isinstance(record, dict):
            return
        target, request = str(record.get("target_id") or ""), str(record.get("request_id") or "")
        key = (target, request, record.get("redirect_index", 0))
        with self._lock:
            if not self._target or target != self._target or not request:
                return
            if phase == "request":
                started = record.get("started_wall_time")
                if not (type(started) in {int, float} and math.isfinite(started)
                        and self._started <= started <= self._clock() + 1.0):
                    return
                method, url = str(record.get("method") or "").upper(), str(record.get("url") or "")
                operation = registration_request_operation(method, url)
                # 新文档意味着原页面已离开；旁路资源永远不能提供换线证据。
                if record.get("resource_type") == "Document":
                    self._latest = None
                if (operation not in self._operations
                        or record.get("resource_type") not in {"Document", "Fetch", "XHR"}):
                    return
                self._latest = {"key": key, "method": method, "url": url,
                                "operation": operation, "failure": None, "http_status": None}
            elif phase in {"response", "complete"}:
                if not self._latest or self._latest["key"] != key:
                    return
                raw_status = record.get("status")
                response = SimpleNamespace(status_code=raw_status) if type(raw_status) is int else None
                error = RuntimeError(str(record["failure"])) if record.get("failure") else None
                failure = registration_route_failure(
                    self._latest["method"], self._latest["url"], response=response, error=error,
                )
                # 响应比完成事件更早抵达；补充事件不能把已有明确状态改回无响应。
                if response is not None or error is not None:
                    self._latest["failure"] = failure
                    self._latest["http_status"] = raw_status if type(raw_status) is int else None

    def call_failed(self, driver, method: str, url: str, error: BaseException) -> None:
        """同步调用点能证明当前动作时，接纳其真实异常，禁止凭终态文案猜端点。"""
        failure = registration_route_failure(method, url, error=error)
        with self._lock:
            if (failure is not None and failure.operation in self._operations
                    and self._target and _target(driver) == self._target):
                self._latest = {"key": (self._target, "synchronous-call", 0),
                                "method": method, "url": url, "failure": failure}

    def call_response(self, driver, method: str, url: str, status: int) -> None:
        """同步读取返回的状态优先于旁路 CDP 到达时机。"""
        failure = registration_route_failure(method, url, response=SimpleNamespace(status_code=status))
        with self._lock:
            if (failure is not None and failure.operation in self._operations
                    and self._target and _target(driver) == self._target):
                self._latest = {"key": (self._target, "synchronous-response", 0),
                                "method": method, "url": url, "failure": failure}

    def current(self, driver) -> tuple[RegistrationRouteFailure, tuple] | None:
        with self._lock:
            if self._target and _target(driver) == self._target and self._latest:
                failure = self._latest.get("failure")
                if isinstance(failure, RegistrationRouteFailure):
                    return failure, self._latest["key"]
        return None

    def failure(self, driver) -> RegistrationRouteFailure | None:
        current = self.current(driver)
        return current[0] if current is not None else None

    def current_response(self, driver, operation: str) -> int | None:
        with self._lock:
            if (self._target and _target(driver) == self._target and self._latest
                    and self._latest.get("operation") == operation):
                return self._latest.get("http_status")
        return None

    def raise_if_failed(self, driver) -> None:
        failure = self.failure(driver)
        if failure is not None:
            raise RoxyRouteFailureSignal(failure)


@dataclass
class RoxyRouteRecoveryState:
    """只供当前业务执行交接；不得作为持久化结果或公开诊断输出。"""

    profile_id: str
    facts: dict = field(repr=False)
    email: str = field(repr=False)
    password: str | None = field(default=None, repr=False)
    driver_state: dict[str, Any] = field(default_factory=dict, repr=False)
    otp_after_ts: Any = field(default=None, repr=False)
    restart_identity_login: bool = False
    preauth_restart: bool = False
    failed_operation: str = ""
    has_unknown_identity_write: bool = False
    unknown_profile_write: bool = False
    consumed: bool = field(default=False, repr=False)

    def restore(self, driver) -> None:
        for name, value in self.driver_state.items():
            setattr(driver, name, value)
        driver._registration_retained_identity_required = True


def make_recovery_state(driver, opened, *, email: str, facts: dict,
                        failure: RegistrationRouteFailure, password: str | None = None) -> RoxyRouteRecoveryState:
    """读取唯一候选但不写提交事实，未知资料/密码只能交原身份登录核验。"""
    from core.storage import registration

    private = registration.get_private_resume_context(int(facts["attempt_id"]), email=email)
    candidate = private.get("password") or password
    if candidate is not None and not isinstance(candidate, str):
        raise RuntimeError("request_unknown: 原候选密码无法核验，保留原环境") from None
    if private.get("password") and password and candidate != password:
        raise RuntimeError("request_unknown: 换线候选与原任务密码不一致，保留原环境")
    saved = {key: getattr(driver, key) for key in _DRIVER_STATE_FIELDS if hasattr(driver, key)}
    receipts = list(saved.get("_browser_submission_receipts") or [])
    current = saved.get("_browser_submission_receipt")
    if current is not None and all(item is not current for item in receipts):
        receipts.append(current)
    sensitive_pending = any(
        isinstance(item, BrowserSubmissionReceipt)
        and item.endpoint_kind in {"password_submit", "profile_submit", "otp_submit", "otp_resend"}
        and item.phase not in {"prepared", "not_dispatched", "confirmed", "rejected", "superseded"}
        for item in receipts
    )
    private_facts = private.get("submission_facts") or []
    pending_ids = unresolved_submission_ids(private_facts)
    private_sensitive_pending = any(
        isinstance(item, dict) and item.get("endpoint_kind") in {
            "password_submit", "profile_submit", "otp_submit", "otp_resend",
        } and item.get("submission_id") in pending_ids
        for item in private_facts
    )
    restart = sensitive_pending or private_sensitive_pending or failure.operation in {
        "password_create", "password_verify", "profile_submit", "callback",
    }
    return RoxyRouteRecoveryState(
        profile_id=str(opened.profile_id), facts=dict(facts), email=str(email).strip().casefold(),
        password=candidate, driver_state=saved,
        otp_after_ts=getattr(driver, "_registration_otp_after_ts", None),
        restart_identity_login=restart,
        preauth_restart=not restart and failure.operation in {"preauth", "email_submit"},
        failed_operation=failure.operation,
        has_unknown_identity_write=sensitive_pending or private_sensitive_pending,
        unknown_profile_write=any(
            isinstance(item, BrowserSubmissionReceipt) and item.endpoint_kind == "profile_submit"
            and item.phase not in {"prepared", "not_dispatched", "confirmed", "rejected", "superseded"}
            for item in receipts
        ) or any(
            isinstance(item, dict) and item.get("endpoint_kind") == "profile_submit"
            and item.get("submission_id") in pending_ids for item in private_facts
        ),
    )


def validated_recovery_state(value, *, facts: dict, profile_id: str | None, email: str):
    """恢复许可只在原执行、原邮箱、原环境仍一致且尚未接管时有效。"""
    if value is None:
        return None
    from core.storage import registration

    valid = isinstance(value, RoxyRouteRecoveryState)
    if valid:
        keys = ("job_id", "attempt_id", "run_id", "execution_id")
        valid = not value.consumed and all(
            (key == "job_id" or facts.get(key) not in (None, ""))
            and type(value.facts.get(key)) is type(facts.get(key))
            and value.facts.get(key) == facts.get(key) for key in keys
        )
        valid = valid and value.email == str(email).strip().casefold() and bool(value.profile_id)
        valid = valid and (not profile_id or str(profile_id) == value.profile_id)
    if valid:
        run = registration.get_run(int(facts["run_id"])) or {}
        valid = (run.get("status") == "running" and run.get("action_type") in {
            "registration", "registration_resume",
        } and all(run.get(key) == facts[key] for key in ("job_id", "attempt_id", "execution_id")))
    if not valid:
        raise RuntimeError("request_unknown: 换线恢复与原 Run、邮箱或 Profile 不一致，保留原环境")
    private = registration.get_private_resume_context(int(facts["attempt_id"]), email=email)
    if (private.get("password") or None) != value.password:
        raise RuntimeError("request_unknown: 换线恢复的原候选密码已变化，保留原环境")
    value.consumed = True
    return value


def record_current_refusal(driver, current) -> bool:
    """当前已配对的明确 403 只收口本次拒绝，不抹除更早未决提交。"""
    failure, key = current
    if failure.http_status != 403 or failure.response_received is not True:
        return False
    binding = key[:2]
    receipts = list(getattr(driver, "_browser_submission_receipts", None) or [])
    latest = getattr(driver, "_browser_submission_receipt", None)
    if latest is not None and all(item is not latest for item in receipts):
        receipts.append(latest)
    for receipt in receipts:
        if (isinstance(receipt, BrowserSubmissionReceipt)
                and receipt.request_binding == binding and receipt.response_binding == binding
                and receipt.http_status == 403 and receipt.phase in {
                    "request_observed", "response_observed", "unknown",
                }):
            record_browser_submission_fact(
                driver, "rejected", receipt=receipt, result="failure", error_type="registration_route_http_403",
            )
            return True
    return False


def continue_browser_twofa(driver, email: str, *, failure: RegistrationRouteFailure,
                          existing_secret: str | None, action, on_secret, check_stop) -> str:
    """新线路只处理原 MFA 动作；已保存密钥不重新 enrollment。"""
    from core.auth.browser import mfa_auth
    import pyotp

    check_stop()
    if not existing_secret and failure.response_received and failure.operation == "twofa_enroll":
        # enroll 的完整 403 是明确拒绝，尚无密钥时可在新线重做这一个动作。
        return action()
    evidence = mfa_auth._probe_existing_roxy_totp(driver, email)
    if evidence["confirmed"]:
        raise RuntimeError(
            "enabled_candidate_unverified: 远端已启用，但不能证明原待确认密钥与远端一致，保留密钥检查点"
        )
    if evidence["reason"] not in {"mfa_not_enabled", "totp_not_enabled"}:
        raise RuntimeError("mfa_route_state_unconfirmed: 新线路未取得同邮箱远端 MFA 完整状态，保留原密钥")
    step, field = mfa_auth._detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True)
    if step != "totp" or field is None:
        raise RuntimeError("mfa_route_enrollment_unavailable: 原 MFA 设置表单未恢复，保留原密钥且未重新开通")
    visible_secret = mfa_auth._read_totp_secret_from_dialog(driver, field, monitor_mfa_enrollment=True)
    if not visible_secret or (existing_secret and existing_secret != visible_secret):
        raise RuntimeError("mfa_route_enrollment_changed: 原 MFA enrollment 密钥无法匹配，未重新开通")
    secret = existing_secret or visible_secret
    if existing_secret is None:
        on_secret(secret)
    budget = StageBudget.start(45)
    while not budget.expired():
        check_stop()
        observer = getattr(driver, "_registration_route_observer", None)
        if isinstance(observer, RoxyRouteFailureObserver):
            observer.raise_if_failed(driver)
        # 离过期窗口太近时只等待，不创建新 enrollment 或替换原密钥。
        remaining = 30 - (int(time.time()) % 30)
        if remaining >= 6:
            break
        time.sleep(min(1.0, budget.remaining()))
    check_stop()
    step, field = mfa_auth._detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True)
    if step != "totp" or field is None:
        raise RuntimeError("mfa_route_enrollment_changed: 原 MFA 激活表单已变化，未提交验证码")
    code = pyotp.TOTP(secret).now()
    observer = getattr(driver, "_registration_route_observer", None)
    if isinstance(observer, RoxyRouteFailureObserver):
        observer.begin_stage(driver, "twofa")
    mfa_auth._human_type_text(driver, field, code, clear=True)
    button = mfa_auth._button_after_input(driver, field)
    if button is None:
        raise RuntimeError("mfa_route_enrollment_unavailable: 原 MFA 激活按钮不可用")
    mfa_auth._human_click(driver, button, label="registration_route_totp_verify")
    while not budget.expired():
        check_stop()
        observer = getattr(driver, "_registration_route_observer", None)
        if isinstance(observer, RoxyRouteFailureObserver):
            observer.raise_if_failed(driver)
        evidence = mfa_auth._probe_existing_roxy_totp(driver, email, timeout=min(10.0, budget.remaining()))
        if evidence["confirmed"]:
            if isinstance(observer, RoxyRouteFailureObserver) and observer.current_response(driver, "twofa_activate") == 200:
                return secret
            raise RuntimeError(
                "enabled_candidate_unverified: 新线路远端已启用，但原激活动作缺少明确成功回执，保留密钥检查点"
            )
        if evidence["reason"] in {"session_identity_unverified", "session_identity_mismatch"}:
            raise RuntimeError("mfa_route_identity_unverified: MFA 恢复后的远端身份无法匹配")
        time.sleep(min(0.5, budget.remaining()))
    raise RuntimeError("mfa_route_activation_unconfirmed: 原密钥激活后仍未取得同邮箱远端确认")


class RegistrationTwofaSession:
    """只包装注册内协议 2FA 当前请求，独立账号动作沿用原会话契约。"""

    def __init__(self, original, *, driver_getter) -> None:
        self._original = original
        self._driver_getter = driver_getter

    def __getattr__(self, name):
        return getattr(self._original, name)

    def post(self, url, *args, **kwargs):
        driver = self._driver_getter()
        observer = getattr(driver, "_registration_route_observer", None)
        if isinstance(observer, RoxyRouteFailureObserver):
            # 上层协议能力可能捕获 RuntimeError 后有限重试；当前写入已有
            # 线路失败时先停止，避免未知 enroll/activate 在旧线路重复派发。
            observer.raise_if_failed(driver)
        try:
            response = self._original.post(url, *args, **kwargs)
        except Exception as exc:
            if isinstance(observer, RoxyRouteFailureObserver):
                observer.call_failed(driver, "POST", url, exc)
                observer.raise_if_failed(driver)
            raise
        if isinstance(observer, RoxyRouteFailureObserver):
            observer.call_response(driver, "POST", url, getattr(response, "status_code", None))
            observer.raise_if_failed(driver)
        return response
