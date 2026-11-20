"""开源protocol-2 的网络、邮箱与原 Attempt 检查点桥接。"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict
from urllib.parse import urlsplit

from core.auth.challenge import AuthCancelledError
from core.network.response_diagnostics import auth_error_from_body, auth_submission_endpoint
from core.registration.failure_diagnostics import RegistrationFailureDiagnostics
from core.registration.protocol_oss_2.lifecycle import ProtocolOssRequestUnknown
from core.registration.route_recovery import (
    current_route_recovery,
    registration_request_operation,
    registration_route_failure,
)

_CONTEXT: ContextVar[dict | None] = ContextVar("protocol_oss_2_context", default=None)

# 上游日志包含响应正文和凭据；本地只通过明确的进度与受控任务诊断报告事实。
_vendor_logger = logging.getLogger("core.kernels.protocol.protocol_oss_2.upstream")
_vendor_logger.addHandler(logging.NullHandler())
_vendor_logger.propagate = False


class _VendorCancelled(BaseException):
    """Carry cancellation through upstream broad Exception retry handlers."""

    def __init__(self, reason: BaseException):
        self.reason = reason


class _VendorRouteRecovery(BaseException):
    """让换线边界穿过上游宽泛重试，回到原身份恢复入口。"""

    def __init__(self, failure, *, switched=False, error=None, method="", stage=""):
        self.failure = failure
        self.switched = switched
        self.error = error
        self.method = str(method).upper()
        self.stage = stage


class ProtocolRegistrationRouteError(RuntimeError):
    """当前注册请求的线路恢复未完成，保留结构化失败事实。"""

    def __init__(self, failure, message="当前注册请求换线恢复未完成", *, cause_code=""):
        super().__init__(message)
        self.route_failure = failure
        self.http_status = failure.http_status
        if cause_code:
            self.cause_code = cause_code


class ProtocolSessionIdentityError(RuntimeError):
    """Token 的完整邮箱无法与本轮任务对应时拒绝保存密码或账号。"""

    cause_code = "identity_mismatch"


class ProtocolSessionResponseError(RuntimeError):
    """本轮还没有可核验的完整 Session，原任务保留重跑。"""

    cause_code = "registration_session_invalid_response"


class ProtocolRegistrationContextError(RuntimeError):
    """原执行事实无法核验，不能把续跑猜测为全新注册。"""

    cause_code = "registration_checkpoint_failed"


class ProtocolRegistrationVerificationRequiredError(RuntimeError):
    """资料请求已接受，但远端仍要求身份验证，尚未交付登录会话。"""

    cause_code = "registration_identity_verification_required"


def _registration_intent_from_facts(facts: dict) -> str:
    """使用持久化 Run 判定执行意图，不从密码是否存在或页面落点推断。"""
    if not any(facts.values()):
        return "signup"
    if not all(facts.get(key) for key in ("attempt_id", "run_id", "execution_id")):
        raise ProtocolRegistrationContextError("原注册执行上下文不完整")
    from core.storage import registration

    try:
        run = registration.get_run(int(facts["run_id"]))
    except Exception as exc:
        raise ProtocolRegistrationContextError("原注册执行检查点读取失败") from exc
    if (not run or run.get("attempt_id") != facts["attempt_id"]
            or run.get("execution_id") != facts["execution_id"]
            or run.get("job_id") != facts.get("job_id")
            or run.get("action_type") not in {"registration", "registration_resume"}):
        raise ProtocolRegistrationContextError("原注册执行检查点与当前任务不匹配")
    try:
        run_no = int(run["run_no"])
        if run_no < 1:
            raise ValueError("执行序号必须为正数")
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolRegistrationContextError("原注册执行序号无效") from exc
    return "resume" if run["action_type"] == "registration_resume" else "signup"


def _check_stop_requested():
    from core.operations.task_gateway import OperationLeaseLost
    from core.registration.service import StopRequested, check_stop_requested

    try:
        check_stop_requested()
    except (StopRequested, AuthCancelledError, OperationLeaseLost) as exc:
        if _CONTEXT.get() is None:
            raise
        raise _VendorCancelled(exc) from exc


from core.kernels.protocol.protocol_oss_2.registration.transport import (
    HeaderOnlyResponse as _HeaderOnlyResponse,
    ObservedSession as _KernelObservedSession,
)


def _transport_callbacks():
    from core.kernels.protocol.protocol_oss_2.registration.transport import ProtocolTransportCallbacks

    def is_cancelled(error):
        from core.operations.task_gateway import OperationLeaseLost
        from core.registration.service import StopRequested

        return isinstance(error, (StopRequested, AuthCancelledError, OperationLeaseLost))

    def replace_route_capture(context, capture, lease, correlation):
        from core.network.protocol_traffic import ProtocolTrafficCapture, current_correlation

        correlation.update(current_correlation())
        correlation["proxy_lease_id"] = getattr(lease, "lease_id", None)
        context["capture"] = ProtocolTrafficCapture(correlation) if capture is not None or correlation.get("proxy_lease_id") else None

    def record_protocol_exchange(**kwargs):
        from core.registration.debug import record_protocol_exchange

        return record_protocol_exchange(**kwargs)

    return ProtocolTransportCallbacks(
        check_stop=lambda: _check_stop_requested(), is_cancelled=is_cancelled,
        context_active=lambda: _CONTEXT.get() is not None,
        current_route_recovery=lambda: current_route_recovery(),
        replace_route_capture=replace_route_capture, record_protocol_exchange=record_protocol_exchange,
        vendor_cancelled=_VendorCancelled, vendor_route_recovery=_VendorRouteRecovery,
        perf_counter=lambda: time.perf_counter(),
    )


class _ObservedSession(_KernelObservedSession):
    """Legacy constructor for kernel execution with the current domain callbacks."""

    def __init__(self, transport, context: dict):
        super().__init__(transport, context, callbacks=_transport_callbacks())


@contextmanager
def registration_twofa_route_recovery(session, *, access_token=""):
    """只给当前注册的 2FA 动作开通恢复，不向套餐、AT 或 Codex 传播。"""
    observed = getattr(session, "session", None)
    if not isinstance(observed, _ObservedSession) or current_route_recovery() is None:
        yield
        return
    context = observed._context
    previous = {key: context.get(key) for key in (
        "route_recovery_enabled", "route_recovery_operations", "observing", "exclusive_traffic_capture",
    )}
    context.update({
        "route_recovery_enabled": True, "route_recovery_operations": {"twofa_enroll", "twofa_activate"},
        "observing": True, "exclusive_traffic_capture": True,
    })
    # 当前请求由观察器逐次计量，避免父 BrowserSession 重复记录最后一次响应。
    session.protocol_traffic = None
    try:
        yield
    except _VendorCancelled as interrupted:
        raise interrupted.reason
    except _VendorRouteRecovery as interrupted:
        error = ProtocolRegistrationRouteError(
            interrupted.failure, "注册 2FA 当前动作结果待确认，保留已有密钥与账号",
            cause_code="registration_route_close_failed" if interrupted.stage == "close_previous_connection" else "",
        )
        state = {"operation": interrupted.failure.operation, "http_status": None, "state": "unknown"}
        if interrupted.switched and access_token:
            try:
                response = session.get(
                    "https://chatgpt.com/backend-api/accounts/mfa_info",
                    headers={"accept": "application/json", "authorization": f"Bearer {access_token}"},
                    timeout=30, allow_redirects=False,
                )
                status = int(response.status_code)
                state["http_status"] = status
                payload = response.json() if status == 200 else None
                if isinstance(payload, dict):
                    if payload.get("mfa_enabled") is True and payload.get("mfa_enabled_v2") is True:
                        state["state"] = "enabled_candidate_unverified"
                    elif payload.get("mfa_enabled") is False and payload.get("mfa_enabled_v2") is False:
                        state["state"] = "not_enabled"
            except Exception as exc:
                from core.registration.service import StopRequested

                if isinstance(exc, (StopRequested, AuthCancelledError)):
                    raise
                # 只读核验失败仍保留原设置动作待确认，不能重发或确认候选。
                pass
        error.twofa_recovery = state
        raise error from interrupted.error
    finally:
        context.update(previous)
        session.protocol_traffic = context.get("capture")


def create_http_session(**kwargs):
    """Create the current registration session using the original patched factory."""
    from core.registration.protocol_oss_2.upstream.http_client_wreq import _HAS_WREQ, create_http_session as create
    from core.kernels.protocol.protocol_oss_2.registration.transport import create_observed_http_session

    if not _HAS_WREQ:
        raise ModuleNotFoundError("开源protocol-2 需要安装 wreq", name="wreq")
    return create_observed_http_session(
        context=_CONTEXT.get(), create_transport=create, observed_factory=_ObservedSession,
        check_stop=_check_stop_requested, **kwargs,
    )


def run_upstream_protocol(
    session, *, email, name, birthday, otp_code, email_source,
    existing_password, existing_totp_secret, options,
):
    """执行固定上游 AuthFlow，邮箱和凭据始终属于本地原任务。"""
    from core.email.provider import wait_for_otp
    from config import email as email_cfg
    from core.registration.checkpoints import save_protocol_password_checkpoint
    from core.registration.service import StopRequested, check_stop_requested, registration_fact_context, report_job_progress
    from core.operations.task_gateway import OperationLeaseLost

    facts = registration_fact_context()
    registration_intent = _registration_intent_from_facts(facts)
    if existing_password:
        from core.storage import registration

        if facts.get("attempt_id") is not None:
            private = registration.get_private_resume_context(int(facts["attempt_id"]), email=email)
            saved_password = private.get("password")
            if saved_password and saved_password != existing_password:
                raise RuntimeError("原 Attempt 的恢复密码不一致，已停止")

    from core.operations.errors import safe_registration_diagnostics
    from core.kernels.protocol.protocol_oss_2.registration.runner import (
        ProtocolExecutionCallbacks, execute_upstream_protocol,
    )

    def record_unknown_action(interrupted):
        import uuid

        if facts.get("attempt_id") is None:
            return
        from core.storage import registration

        failure = interrupted.failure
        kind, stage, endpoint = {
            "password_create": ("password", "password_create", "password_submit"),
            "password_verify": ("password", "login_password", "password_submit"),
            "profile_submit": ("profile", "profile", "profile_submit"),
            "email_submit": ("email", "submit_email", "email_submit"),
            "otp_validate": ("otp", "email_otp", "otp_submit"),
            "otp_send": ("otp", "otp_resend", "otp_resend"),
            "callback": ("callback", "auth_redirect", "auth_redirect"),
        }[failure.operation]
        registration.record_submission_fact(
            int(facts["attempt_id"]), submission_id=uuid.uuid4().hex,
            kind=kind, stage=stage, phase="unknown", endpoint_kind=endpoint,
            http_method=interrupted.method, http_status=failure.http_status, result="unknown",
            run_id=facts.get("run_id"), execution_id=facts.get("execution_id"), job_id=facts.get("job_id"),
        )

    callbacks = ProtocolExecutionCallbacks(
        check_stop=check_stop_requested, check_vendor_stop=_check_stop_requested,
        report_progress=report_job_progress, wait_for_otp=wait_for_otp,
        save_password_checkpoint=save_protocol_password_checkpoint,
        record_unknown_action=record_unknown_action, safe_diagnostics=safe_registration_diagnostics,
        diagnostics_factory=RegistrationFailureDiagnostics, create_http_session=create_http_session,
        activate_context=_CONTEXT.set, reset_context=_CONTEXT.reset,
        cancel_errors=(StopRequested, AuthCancelledError, OperationLeaseLost),
        mailbox_cancel_errors=(StopRequested, AuthCancelledError),
        vendor_cancelled=_VendorCancelled, vendor_route_recovery=_VendorRouteRecovery,
        context_error=ProtocolRegistrationContextError, route_error=ProtocolRegistrationRouteError,
        session_response_error=ProtocolSessionResponseError, session_identity_error=ProtocolSessionIdentityError,
        verification_required_error=ProtocolRegistrationVerificationRequiredError,
        request_unknown_error=ProtocolOssRequestUnknown, otp_max_wait=lambda: email_cfg.OTP_MAX_WAIT,
    )
    return execute_upstream_protocol(
        session, email=email, name=name, birthday=birthday, otp_code=otp_code,
        email_source=email_source, existing_password=existing_password,
        existing_totp_secret=existing_totp_secret, options=options,
        registration_intent=registration_intent, callbacks=callbacks,
    )
