"""开源protocol-2 的网络、邮箱与原 Attempt 检查点桥接。"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
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
_vendor_logger = logging.getLogger("core.registration.protocol_oss_2.upstream")
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
    from core.registration.service import StopRequested, check_stop_requested

    try:
        check_stop_requested()
    except (StopRequested, AuthCancelledError) as exc:
        if _CONTEXT.get() is None:
            raise
        raise _VendorCancelled(exc) from exc


class _HeaderOnlyResponse:
    """诊断流式导航时只观察响应头，不读取本来无需下载的正文。"""

    content = b""
    text = ""

    def __init__(self, response):
        self._response = response

    def __getattr__(self, name):
        return getattr(self._response, name)

    def json(self):
        return {}


class _ObservedSession:
    """当前动作在业务统一预算内换线，保留会话与停止信号。"""

    def __init__(self, transport, context: dict):
        self._transport = transport
        self._context = context

    def __getattr__(self, name):
        return getattr(self._transport, name)

    def request(self, method, url, **kwargs):
        while True:
            response = None
            error = None
            try:
                response = self._request_once(method, url, **kwargs)
            except Exception as exc:
                from core.registration.service import StopRequested

                if isinstance(exc, (StopRequested, AuthCancelledError)):
                    raise
                error = exc
            failure = registration_route_failure(method, url, response=response, error=error)
            context = self._context
            allowed = context.get("route_recovery_operations")
            enabled = context.get("route_recovery_enabled", True)
            callback = current_route_recovery() if enabled else None
            if failure is None or (allowed is not None and failure.operation not in allowed) or callback is None:
                if error is not None:
                    raise error
                return response
            if response is not None:
                close = getattr(response, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            try:
                pause = getattr(self._transport, "pause_for_route_recovery", None)
                if callable(pause):
                    pause()
            except Exception as exc:
                raise _VendorRouteRecovery(
                    failure, error=exc, method=method, stage="close_previous_connection",
                ) from exc
            try:
                lease = callback(failure, context.get("proxy"))
            except Exception as exc:
                from core.registration.service import StopRequested

                if isinstance(exc, (StopRequested, AuthCancelledError)):
                    raise _VendorCancelled(exc) from exc
                raise _VendorRouteRecovery(failure, error=exc, method=method) from exc
            if lease is None:
                raise _VendorRouteRecovery(failure, error=error, method=method) from error
            try:
                self._replace_route(lease)
            except Exception as exc:
                raise _VendorRouteRecovery(failure, error=exc, method=method) from exc
            if not failure.replay_safe:
                raise _VendorRouteRecovery(failure, switched=True, error=error, method=method) from error

    def _replace_route(self, lease):
        """只替换连接和租约关联，Cookie Jar、画像和认证栈保持不变。"""
        from core.network.protocol_traffic import ProtocolTrafficCapture, current_correlation

        context = self._context
        proxy = str(getattr(lease, "proxy_url", "") or "").strip()
        if not proxy:
            raise RuntimeError("换线未返回可用代理，已停止当前注册动作")
        capture = context.get("capture")
        correlation = dict(getattr(capture, "correlation", {}) or {})
        if capture is not None:
            capture.flush()
        self._transport.proxies = {"http": proxy, "https": proxy}
        context["proxy"] = proxy
        flow = context.get("flow")
        if flow is not None:
            flow.config.proxy = proxy
            flow._proxy_pool = [proxy]
            flow._proxy_idx = -1
        parent = context.get("parent_session")
        if parent is not None:
            parent.proxy = proxy
        correlation.update(current_correlation())
        correlation["proxy_lease_id"] = getattr(lease, "lease_id", None)
        context["capture"] = ProtocolTrafficCapture(correlation) if capture is not None or correlation.get("proxy_lease_id") else None
        if parent is not None:
            parent.protocol_traffic = None if context.get("exclusive_traffic_capture") else context["capture"]

    def _request_once(self, method, url, **kwargs):
        _check_stop_requested()
        context = self._context
        path = urlsplit(url).path
        if path.endswith("/api/auth/session"):
            context["session_response_incomplete"] = False
        if method.upper() == "POST" and path.endswith("/create_account"):
            context["profile_started"] = True
        profile_submit = method.upper() == "POST" and auth_submission_endpoint(url) == "profile_submit"
        password_create = method.upper() == "POST" and path == "/api/accounts/user/register"
        if profile_submit:
            context.pop("profile_diagnostics", None)
        if password_create:
            context.pop("password_diagnostics", None)
        started = time.perf_counter()
        response = None
        error = None
        try:
            response = self._transport.request(method, url, **kwargs)
            response._protocol2_streaming = bool(kwargs.get("stream"))
            if password_create:
                try:
                    status = int(response.status_code)
                    if status != 200:
                        context["password_diagnostics"] = {
                            "operation": "password_submit", "http_status": status,
                            "auth_error": auth_error_from_body(response.text),
                        }
                except Exception:
                    pass
            if profile_submit and not kwargs.get("stream"):
                try:
                    status = int(response.status_code)
                    if 400 <= status <= 599:
                        context["profile_diagnostics"] = {
                            "operation": "profile_submit", "http_status": status,
                            "auth_error": auth_error_from_body(response.text),
                        }
                except Exception:
                    # 诊断提取失败不能覆盖远端响应或读取原始异常正文。
                    pass
            if path.endswith("/api/auth/session") and response.status_code == 200:
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                if isinstance(payload, dict):
                    access_token = str(payload.get("accessToken") or payload.get("access_token") or "").strip()
                    user = payload.get("user")
                    actual_email = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
                    if access_token and actual_email:
                        normalized = dict(payload, accessToken=access_token)
                        context["session_info"] = normalized
                        expected = str(context.get("email") or "").strip().casefold()
                        context["session_identity_mismatch"] = bool(
                            (expected and expected != actual_email)
                            or (payload.get("accessToken") and payload.get("access_token")
                                and payload["accessToken"] != payload["access_token"])
                        )
                    else:
                        # 后续空响应不能抹掉同一认证链已核验的完整 Session。
                        context["session_response_incomplete"] = True
                else:
                    context["session_response_incomplete"] = True
            return response
        except BaseException as exc:
            error = exc
            operation = registration_request_operation(method, url)
            if response is None and operation in {"password_create", "profile_submit"}:
                context["write_unknown"] = True
                context.setdefault("unknown_identity_operations", set()).add(operation)
            raise
        finally:
            diagnostics = context.get("registration_diagnostics")
            if diagnostics is not None:
                try:
                    diagnostics.observe_request(
                        method, url, response=response, error=error, stream=bool(kwargs.get("stream")),
                    )
                except Exception:
                    # 外围诊断失败不能改变原响应、异常或后续认证动作。
                    pass
            capture = context.get("capture")
            if context.get("observing", True):
                try:
                    observed = _HeaderOnlyResponse(response) if response is not None and kwargs.get("stream") else response
                    if capture is not None:
                        capture.record(started_at=started, response=observed, error=error)
                    from core.registration.debug import record_protocol_exchange

                    record_protocol_exchange(
                        method=method, url=url, started_at=started,
                        request_headers=kwargs.get("headers"),
                        request_body=kwargs.get("json", kwargs.get("data")),
                        response=observed, error=error,
                    )
                except Exception:
                    # 诊断写入失败不得改变认证结果，也不输出私有响应。
                    pass

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


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
    """只为当前驱动创建 wreq，会话工厂不修改其他驱动或全局模块。"""
    from core.registration.protocol_oss_2.upstream.http_client_wreq import _HAS_WREQ, create_http_session as create

    if not _HAS_WREQ:
        raise ModuleNotFoundError("开源protocol-2 需要安装 wreq", name="wreq")

    context = _CONTEXT.get()
    if context is None:
        raise RuntimeError("开源protocol-2 缺少注册执行上下文")
    _check_stop_requested()
    if context.get("identity_recovery") and context["sessions"]:
        # 原身份恢复只允许沿用当前认证现场，不能重建空会话或更换画像。
        return context["sessions"][-1]
    kwargs["proxy"] = context["proxy"]
    transport = _ObservedSession(create(**kwargs), context)
    if context["sessions"]:
        # 上游换指纹或预热重建会话后，旧认证链的密码接收/校验不能用于新 Token。
        context["password_register_accepted"] = False
        context["password_verified"] = False
        context["session_info"] = {}
        context.pop("session_identity_mismatch", None)
    context["sessions"].append(transport)
    return transport


def run_upstream_protocol(
    session, *, email, name, birthday, otp_code, email_source,
    existing_password, existing_totp_secret, options,
):
    """执行固定上游 AuthFlow，邮箱和凭据始终属于本地原任务。"""
    from core.email.provider import wait_for_otp
    from config import email as email_cfg
    from core.registration.checkpoints import save_protocol_password_checkpoint
    from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
    from core.registration.protocol_oss_2.upstream.config import Config
    from core.registration.protocol_oss_2.upstream.fingerprint import generate_fingerprint
    from core.registration.service import StopRequested, check_stop_requested, registration_fact_context, report_job_progress

    facts = registration_fact_context()
    registration_intent = _registration_intent_from_facts(facts)
    if existing_password:
        from core.storage import registration

        if facts.get("attempt_id") is not None:
            private = registration.get_private_resume_context(int(facts["attempt_id"]), email=email)
            saved_password = private.get("password")
            if saved_password and saved_password != existing_password:
                raise RuntimeError("原 Attempt 的恢复密码不一致，已停止")

    context = {
        "proxy": session.proxy, "capture": session.protocol_traffic, "sessions": [], "email": email,
        "parent_session": session, "route_recovery_enabled": True,
        "password_started": False, "password_register_accepted": False, "password_verified": False,
        "profile_started": False, "write_unknown": False, "session_info": {},
        "registration_diagnostics": RegistrationFailureDiagnostics(),
    }

    def observe(method, *args):
        try:
            return getattr(context["registration_diagnostics"], method)(*args)
        except Exception:
            # 诊断只观察，不授予认证分支、重试或取消控制权。
            return None

    def observed_action(operation, callback, *args, **kwargs):
        try:
            sequence = context["registration_diagnostics"].sequence
        except Exception:
            sequence = None
        try:
            return callback(*args, **kwargs)
        except Exception as exc:
            observe("bind_failure", exc, operation, sequence)
            raise

    def progress(stage, state, detail):
        _check_stop_requested()
        report_job_progress(stage, state, detail)
        observe("progress", stage, state)

    class LocalMailbox:
        kind = "local"
        pooled = False
        ephemeral = False

        def __init__(self):
            self.code = otp_code

        def create_mailbox(self):
            return email

        def peek_otp(self, *args, **kwargs):
            return None

        def wait_for_otp(self, email_addr, timeout=120, issued_after=None):
            if str(email_addr).strip().lower() != str(email).strip().lower():
                raise ValueError("开源protocol-2 取码邮箱与原任务不一致")
            progress("email_otp", "running", "正在通过原邮箱来源等待验证码")
            if self.code is not None:
                code, self.code = self.code, None
                observe("received_otp")
                return code
            try:
                code = wait_for_otp(
                    email, after_ts=issued_after, max_wait=timeout, email_source=email_source,
                )
                observe("received_otp")
                return code
            except (StopRequested, AuthCancelledError) as exc:
                raise _VendorCancelled(exc) from exc

    class LocalAuthFlow(AuthFlow):
        def register_password(self, address):
            if context.get("identity_recovery"):
                raise ProtocolRegistrationContextError("原身份换线恢复禁止重新创建密码")
            accepted = observed_action("password_submit", super().register_password, address)
            if not accepted:
                diagnostic = context.get("password_diagnostics") or {}
                status = diagnostic.get("http_status")
                code = (diagnostic.get("auth_error") or {}).get("code")
                detail = f"密码创建请求被拒绝：HTTP {status}" if status else "上游未接受密码注册"
                if code:
                    detail += f"，原因={code}"
                progress("password", "failed", f"{detail}；继续通过原邮箱验证")
            return accepted

        def _random_password(self):
            if self.result.password or existing_password:
                # 上次可能停在提交前；远端仍走新注册时复用原密码完成该请求。
                return self.result.password or existing_password
            password = super()._random_password()
            save_protocol_password_checkpoint(
                email=email, password=password, state="prepared",
                proxy=session.proxy, email_source=email_source,
            )
            return password

        def before_password_submit(self, address, password):
            progress("password", "running", "正在提交开源protocol-2 密码注册")
            save_protocol_password_checkpoint(
                email=address, password=password, state="started",
                proxy=session.proxy, email_source=email_source,
            )
            context["password_started"] = True

        def after_password_submit(self, address, password):
            context["password_register_accepted"] = True
            save_protocol_password_checkpoint(
                email=address, password=password, state="confirmed",
                proxy=session.proxy, email_source=email_source,
            )
            progress("password", "running", "密码创建请求已接受，候选密码已保存；等待邮箱验证和 Token")

        def signup(self, *args, **kwargs):
            if context.get("identity_recovery"):
                raise ProtocolRegistrationContextError("原身份换线恢复禁止退回新注册")
            progress("submit_email", "running", "正在建立上游邮箱认证状态")
            result = observed_action("email_submit", super().signup, *args, **kwargs)
            progress("submit_email", "success", "上游邮箱认证状态已建立")
            progress("auth_redirect", "success", "已进入上游认证流程")
            return result

        def verify_otp(self, code):
            result = observed_action("otp_validate", super().verify_otp, code)
            progress("email_otp", "success", "上游邮箱验证码已通过")
            return result

        def send_otp(self, *args, **kwargs):
            return observed_action("otp_send", super().send_otp, *args, **kwargs)

        def login_password_verify(self, password):
            progress("login_password", "running", "正在使用原密码继续上游认证")
            self.get_sentinel_token(self.result.device_id)
            result = observed_action("password_submit", super().login_password_verify, password)
            context["password_verified"] = True
            progress("login_password", "running", "原密码已通过本轮校验，等待取得 Token 后确认")
            return result

        def create_account(self):
            if context.get("identity_recovery") and "profile_submit" in context.get("unknown_identity_operations", set()):
                raise ProtocolRegistrationContextError("原资料提交结果未知，禁止在原身份恢复中重复创建")
            context.pop("profile_diagnostics", None)
            context.pop("profile_error", None)
            progress("profile", "running", "正在提交上游注册资料")
            try:
                result = observed_action("profile_submit", super().create_account)
            except Exception as exc:
                # 上游可能吞掉资料异常后重认证；仅给最终仍传播的同一异常归因。
                context["profile_error"] = exc
                raise
            progress("profile", "success", "上游已确认注册资料")
            # 仅补进度，不在原流程之外增加停止检查点。
            try:
                report_job_progress("token", "running", "资料已确认，正在完成回调和登录态")
            except Exception:
                # 新增进度写入失败同样不能改变原认证结果。
                pass
            observe("progress", "token", "running")
            return result

        def get_auth_session(self):
            result = super().get_auth_session()
            if context.get("session_identity_mismatch"):
                raise ProtocolSessionIdentityError("登录会话身份或 Token 字段冲突，原任务已保留")
            verified = context.get("session_info") or {}
            if verified:
                self.session_info = dict(verified)
                self.result.access_token = verified["accessToken"]
                return self.result.session_token, self.result.access_token
            return result

        def _resolve_login_password(self, address):
            # 本地没有原密码时，由上游邮箱认证分支处理；不提交推测密码。
            password = str(self.result.password or existing_password or "")
            if not password:
                raise RuntimeError("已有账号需要原密码，请使用原任务重跑补全凭据")
            return password, True

        def recover_identity(self, mailbox):
            """先核验已有 Session，再走禁止创建兜底的原邮箱登录入口。"""
            context["identity_recovery"] = True
            self._is_existing_account = True
            self.get_auth_session()
            if context.get("session_info"):
                return self.result
            progress("auth_redirect", "running", "已保留原提交结果，正在通过原邮箱恢复登录态")
            return self.run_protocol_login(
                mailbox, email, self.result.password or existing_password or "",
                strict_identity_resume=True,
                allow_profile_completion="profile_submit" not in context.get("unknown_identity_operations", set()),
            )

    def preserve_unknown_route_action(interrupted):
        """只追加已派发动作的未知事实，后续登录成功也不改写原创建结果。"""
        import uuid

        failure = interrupted.failure
        context.setdefault("route_unknown_operations", set()).add(failure.operation)
        if facts.get("attempt_id") is None:
            return
        from core.storage import registration

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

    token = _CONTEXT.set(context)
    flow = None
    try:
        progress("browser", "running", "正在初始化开源protocol-2 会话")
        fingerprint = generate_fingerprint(
            country_code=str(options.get("proxy_country") or "US"), browser_family="chrome",
        )
        # 与指定仓库桥接入口一致，使用 Chrome152 网络画像。
        fingerprint["impersonate"] = "chrome152"
        fingerprint["fallback_impersonates"] = ["chrome152"]
        flow = LocalAuthFlow(
            Config(proxy=session.proxy), fingerprint=fingerprint,
            fingerprint_browser_family="chrome", proxy_pool=[session.proxy],
            env_overrides={
                "WEBUI_ALLOW_LOGIN": "1", "OTP_TIMEOUT": str(options.get("otp_timeout") or email_cfg.OTP_MAX_WAIT),
                "SKIP_OAUTH_TOKEN_EXCHANGE": "1", "OAUTH_CODEX_RT_EXCHANGE": "0",
                "OAUTH_CODEX_RT_BEFORE_CALLBACK": "0", "OAUTH_EXCHANGE_BEFORE_CALLBACK": "0",
                "OAUTH_SECONDARY_AUTHORIZE_EXCHANGE": "0", "OAUTH_REFRESH_ONLY": "0",
                "OAUTH_TOKEN_EXCHANGE_FROM_CALLBACK": "0",
            },
            account_callback=lambda address: {
                "password": existing_password or "", "totp_secret": existing_totp_secret or "",
            } if str(address).strip().lower() == str(email).strip().lower() else {},
        )
        context["flow"] = flow
        flow.registration_name = name
        flow.registration_birthday = birthday
        flow.registration_intent = registration_intent
        flow._last_sentinel_token = ""
        flow._last_sentinel_so_token = ""
        flow.result.password = existing_password or ""
        flow.result.totp_secret = existing_totp_secret or ""
        progress("browser", "success", "开源protocol-2 会话已初始化")
        mailbox = LocalMailbox()
        action = lambda: flow.run_register(mailbox)
        while True:
            try:
                result = action()
                break
            except _VendorRouteRecovery as interrupted:
                failure = interrupted.failure
                context["route_failure"] = failure
                if not failure.replay_safe:
                    preserve_unknown_route_action(interrupted)
                if not interrupted.switched:
                    close_failed = interrupted.stage == "close_previous_connection"
                    error = ProtocolRegistrationRouteError(
                        failure, "旧连接关闭失败，未交还当前线路" if close_failed else "当前注册请求换线恢复未完成",
                        cause_code="registration_route_close_failed" if close_failed else "",
                    )
                    # 把当前错误响应绑定到逃出上游后的同一异常，不借用历史事件。
                    operation = "password_submit" if failure.operation in {"password_create", "password_verify"} else failure.operation
                    observe("bind_failure", error, operation, context["registration_diagnostics"].sequence - 1)
                    raise error from interrupted.error
                if interrupted.error is not None:
                    context["route_unknown_error"] = interrupted.error
                if failure.operation == "profile_submit" and interrupted.error is not None:
                    context["profile_error"] = interrupted.error
                action = lambda: flow.recover_identity(mailbox)
        check_stop_requested()
        access_token = str(result.access_token or "").strip()
        if not access_token:
            raise RuntimeError("上游注册结束但尚未取得 access_token，可重跑原任务继续")
        session_info = dict(context["session_info"])
        user = session_info.get("user")
        actual_email = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
        if not actual_email:
            raise ProtocolSessionResponseError("本轮未取得包含目标身份的完整 Session，原任务可重跑")
        if actual_email != str(email).strip().casefold():
            raise ProtocolSessionIdentityError("登录会话缺少目标邮箱身份或与原任务不一致，已保留候选密码")
        if str(session_info.get("accessToken") or "").strip() != access_token:
            raise ProtocolSessionIdentityError("本轮 Token 与已核验的登录会话不一致，已保留候选密码")
        password_validated = bool(context["password_register_accepted"] or context["password_verified"])
        if context["password_register_accepted"]:
            progress("password", "success", "本轮密码创建及认证已完成，已取得 Token")
        elif context["password_verified"]:
            progress("login_password", "success", "本轮原密码校验及认证已完成，已取得 Token")
        session.session.close()
        session.session = flow.session
        session.device_id = result.device_id
        session.browser_profile.update(fingerprint)
        session.browser_profile["accept_language"] = fingerprint.get("lang_full", "en-US,en;q=0.9")
        session.browser_profile["navigator_language"] = fingerprint.get("lang", "en-US")
        # 后处理通过 BrowserSession 自身计量，避免对同一请求重复记账。
        context["observing"] = False
        context["route_recovery_enabled"] = False
        return {
            "access_token": access_token, "session_info": session_info,
            "registration_password": result.password or existing_password or None,
            "password_validated": password_validated,
            "password_state": "confirmed" if password_validated else "candidate",
            "password_diagnostics": context.get("password_diagnostics"),
            "remote_identity": "existing" if flow._is_existing_account else "new",
            "challenge_chain": (["password"] if password_validated else []) + ["email_otp"],
            "route_unknown_operations": sorted(context.get("route_unknown_operations", set())),
        }
    except _VendorCancelled as exc:
        raise exc.reason
    except (StopRequested, AuthCancelledError):
        raise
    except Exception as exc:
        route_failure = getattr(exc, "route_failure", None) or context.get("route_failure")
        if route_failure is not None:
            exc.route_failure = route_failure
        if (context.get("session_response_incomplete") and not context.get("session_info")
                and not context.get("profile_error") and not context.get("route_unknown_error")
                and not getattr(exc, "cause_code", "")):
            invalid = ProtocolSessionResponseError("本轮 Session 响应缺少完整身份或 Token，原任务可重跑")
            invalid.__cause__ = exc
            exc = invalid
        # 有界恢复未完成时仍保留原资料提交的失败事实，避免变成泛化无凭证错误。
        primary = context.get("profile_error") or context.get("route_unknown_error") or exc
        diagnostics = observe("failure", primary)
        if diagnostics is not None:
            try:
                exc.registration_diagnostics = diagnostics
            except Exception:
                pass
        if existing_password or any(context[key] for key in ("password_started", "password_register_accepted", "password_verified", "profile_started", "write_unknown")):
            unknown = ProtocolOssRequestUnknown(
                "开源protocol-2 尚未取得完整会话，可重跑原任务继续",
                register_response_confirmed=context["password_register_accepted"],
                cause_diagnostics=context.get("profile_diagnostics"),
            )
            if getattr(exc, "cause_code", "") in {
                "password_entry_navigation_failed", "password_entry_navigation_timeout", "password_entry_not_offered",
                "identity_mismatch",
                "registration_password_create_rejected", "registration_password_unconfirmed",
                "registration_auth_state_unrecognized", "registration_session_invalid_response",
                "registration_route_close_failed",
            }:
                unknown.cause_code = exc.cause_code
            if diagnostics is not None:
                unknown.registration_diagnostics = diagnostics
            if route_failure is not None:
                unknown.route_failure = route_failure
            raise unknown from exc
        raise
    finally:
        _CONTEXT.reset(token)
        for transport in context["sessions"]:
            if transport is not session.session:
                transport.close()
