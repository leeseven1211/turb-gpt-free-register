"""Protocol-2 authentication execution with explicit domain callbacks.

The runner owns upstream flow/session control. The registration domain owns durable
password facts, OTP source selection, progress, recovery audit and request-unknown policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

from core.kernels.protocol.protocol_oss_2.upstream.auth_flow import AuthFlow, RegistrationIdentityRecoveryError
from core.kernels.protocol.protocol_oss_2.upstream.config import Config
from core.kernels.protocol.protocol_oss_2.upstream.fingerprint import generate_fingerprint


@dataclass(frozen=True)
class ProtocolExecutionCallbacks:
    check_stop: Callable[[], None]
    check_vendor_stop: Callable[[], None]
    report_progress: Callable[..., None]
    wait_for_otp: Callable[..., str]
    save_password_checkpoint: Callable[..., Any]
    record_unknown_action: Callable[..., None]
    safe_diagnostics: Callable[..., Any]
    diagnostics_factory: Callable[..., Any]
    create_http_session: Callable[..., Any]
    activate_context: Callable[..., Any]
    reset_context: Callable[..., None]
    cancel_errors: tuple[type[BaseException], ...]
    mailbox_cancel_errors: tuple[type[BaseException], ...]
    vendor_cancelled: type[BaseException]
    vendor_route_recovery: type[BaseException]
    context_error: type[Exception]
    route_error: type[Exception]
    session_response_error: type[Exception]
    session_identity_error: type[Exception]
    verification_required_error: type[Exception]
    request_unknown_error: type[Exception]
    otp_max_wait: Callable[[], int]


def execute_upstream_protocol(
    session, *, email, name, birthday, otp_code, email_source,
    existing_password, existing_totp_secret, options, registration_intent: str,
    callbacks: ProtocolExecutionCallbacks,
):
    """Execute the existing upstream request sequence for one validated run."""
    _VendorCancelled = callbacks.vendor_cancelled
    _VendorRouteRecovery = callbacks.vendor_route_recovery
    ProtocolRegistrationContextError = callbacks.context_error
    ProtocolRegistrationRouteError = callbacks.route_error
    ProtocolSessionResponseError = callbacks.session_response_error
    ProtocolSessionIdentityError = callbacks.session_identity_error
    ProtocolRegistrationVerificationRequiredError = callbacks.verification_required_error
    ProtocolOssRequestUnknown = callbacks.request_unknown_error

    context = {
        "proxy": session.proxy, "capture": session.protocol_traffic, "sessions": [], "email": email,
        "parent_session": session, "route_recovery_enabled": True,
        "password_started": False, "password_register_accepted": False, "password_verified": False,
        "profile_started": False, "write_unknown": False, "session_info": {},
        "registration_diagnostics": callbacks.diagnostics_factory(),
    }

    def observe(method, *args):
        try:
            return getattr(context["registration_diagnostics"], method)(*args)
        except Exception:
            # 诊断只观察，不授予认证分支、重试或取消控制权。
            return None

    def record_recovery_audit(error=None, failure=None):
        """只保存固定请求类别与诊断，不复制原异常正文。"""
        entry = {}
        if error is not None:
            diagnostics = callbacks.safe_diagnostics(observe("failure", error))
            if diagnostics:
                entry["registration_diagnostics"] = diagnostics
        if failure is not None:
            entry["route_failure"] = asdict(failure)
        if entry:
            context["recovery_audit"] = [*context.get("recovery_audit", []), entry][-4:]

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
        callbacks.check_vendor_stop()
        callbacks.report_progress(stage, state, detail)
        observe("progress", stage, state)

    class LocalMailbox:
        kind = "local"
        pooled = False
        ephemeral = False

        def __init__(self):
            self.code = otp_code
            self.waits = 0

        def _wait_limit(self):
            try:
                from config import email as email_cfg

                return max(1, int(getattr(email_cfg, "OTP_MAX_ATTEMPTS", 1) or 1))
            except Exception:
                return 1

        def create_mailbox(self):
            return email

        def peek_otp(self, *args, **kwargs):
            return None

        def wait_for_otp(self, email_addr, timeout=120, issued_after=None):
            if str(email_addr).strip().lower() != str(email).strip().lower():
                raise ValueError("开源protocol-2 取码邮箱与原任务不一致")
            self.waits += 1
            if self.waits > self._wait_limit():
                raise TimeoutError("验证码等待次数已达上限（OTP_MAX_ATTEMPTS）")
            progress("email_otp", "running", "正在通过原邮箱来源等待验证码")
            if self.code is not None:
                code, self.code = self.code, None
                observe("received_otp")
                return code
            try:
                code = callbacks.wait_for_otp(
                    email, after_ts=issued_after, max_wait=timeout, email_source=email_source,
                )
                observe("received_otp")
                return code
            except callbacks.mailbox_cancel_errors as exc:
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
            callbacks.save_password_checkpoint(
                email=email, password=password, state="prepared",
                proxy=session.proxy, email_source=email_source,
            )
            return password

        def before_password_submit(self, address, password):
            progress("password", "running", "正在提交开源protocol-2 密码注册")
            callbacks.save_password_checkpoint(
                email=address, password=password, state="started",
                proxy=session.proxy, email_source=email_source,
            )
            context["password_started"] = True

        def after_password_submit(self, address, password):
            context["password_register_accepted"] = True
            callbacks.save_password_checkpoint(
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
            context.pop("resume_method_mismatch_error", None)
            sequence = context.get("request_sequence", 0)
            try:
                result = observed_action("otp_validate", super().verify_otp, code)
            except Exception as exc:
                if (context.get("request_sequence", 0) > sequence
                        and context.get("last_request_operation") == "otp_validate"
                        and context.get("last_request_http_status") == 400
                        and context.get("otp_method_mismatch") is True):
                    context["resume_method_mismatch_error"] = exc
                raise
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
            if context.get("identity_recovery") and (
                context.get("profile_started")
                or context.get("resume_auth_recovery_used")
                or "profile_submit" in context.get("unknown_identity_operations", set())
            ):
                raise RegistrationIdentityRecoveryError("registration_profile_submission_unresolved")
            context.pop("profile_diagnostics", None)
            progress("profile", "running", "正在提交上游注册资料")
            try:
                result = observed_action("profile_submit", super().create_account)
            except Exception as exc:
                # 资料回执仅绑定此异常；后续认证失败另行按当前事实归因。
                context["profile_error"] = True
                exc.protocol_profile_diagnostics = context.get("profile_diagnostics")
                record_recovery_audit(exc)
                raise
            progress("profile", "success", "上游已确认注册资料")
            target = urlsplit(str(result or ""))
            if (target.scheme == "https" and target.hostname == "auth.openai.com"
                    and target.port in (None, 443) and not target.username and not target.password
                    and target.path.rstrip("/") == "/verify-your-identity"):
                raise ProtocolRegistrationVerificationRequiredError(
                    "资料已接受，OpenAI 要求继续身份验证，当前协议尚未完成该步骤"
                )
            # 仅补进度，不在原流程之外增加停止检查点。
            try:
                callbacks.report_progress("token", "running", "资料已确认，正在完成回调和登录态")
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
            mailbox.code = None
            self._is_existing_account = True
            self.get_auth_session()
            if context.get("session_info"):
                return self.result
            progress("auth_redirect", "running", "已保留原提交结果，正在通过原邮箱恢复登录态")
            return self.run_protocol_login(
                mailbox, email, self.result.password or existing_password or "",
                strict_identity_resume=True,
                allow_profile_completion=(
                    not context.get("profile_started")
                    and not context.get("resume_auth_recovery_used")
                    and "profile_submit" not in context.get("unknown_identity_operations", set())
                ),
            )

    def preserve_unknown_route_action(interrupted):
        """Report unknown writes to the domain owner before identity recovery."""
        context.setdefault("route_unknown_operations", set()).add(interrupted.failure.operation)
        callbacks.record_unknown_action(interrupted)

    token = callbacks.activate_context(context)
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
            session_factory=callbacks.create_http_session,
            fingerprint_browser_family="chrome", proxy_pool=[session.proxy],
            env_overrides={
                "WEBUI_ALLOW_LOGIN": "1", "OTP_TIMEOUT": str(options.get("otp_timeout") or callbacks.otp_max_wait()),
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
                if context.get("session_response_incomplete") and not context.get("session_info"):
                    raise ProtocolSessionResponseError("本轮 Session 响应缺少完整身份或 Token，原任务可重跑")
                break
            except _VendorRouteRecovery as interrupted:
                failure = interrupted.failure
                context["route_failure"] = failure
                record_recovery_audit(interrupted.error, failure)
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
                action = lambda: flow.recover_identity(mailbox)
            except callbacks.cancel_errors:
                raise
            except Exception as exc:
                current_mismatch = context.pop("resume_method_mismatch_error", None) is exc
                empty_session = (
                    context.get("last_request_operation") == "session"
                    and context.get("last_request_http_status") == 200
                    and context.get("session_response_incomplete")
                    and not context.get("session_info")
                    and not context.get("profile_error")
                    and not context.get("profile_diagnostics")
                    and getattr(exc, "cause_code", "") == "registration_session_invalid_response"
                )
                if (registration_intent != "resume" or not existing_password
                        or context.get("identity_recovery") or context.get("resume_auth_recovery_used")
                        or context.get("write_unknown") or context.get("session_identity_mismatch")
                        or context.get("auth_write_unknown")
                        or context.get("profile_error")
                        or context.get("password_diagnostics")
                        or context.get("route_failure") or not (current_mismatch or empty_session)):
                    raise
                context["resume_auth_recovery_used"] = True
                record_recovery_audit(exc)
                context["registration_diagnostics"] = callbacks.diagnostics_factory()
                progress("auth_redirect", "running", "当前认证未取得有效会话，正在沿原身份恢复登录一次")
                action = lambda: flow.recover_identity(mailbox)
        callbacks.check_stop()
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
    except callbacks.cancel_errors:
        raise
    except Exception as exc:
        route_failure = getattr(exc, "route_failure", None) or context.get("route_failure")
        if route_failure is not None:
            exc.route_failure = route_failure
        diagnostics = observe("failure", exc)
        if (context.get("session_response_incomplete") and not context.get("session_info")
                and context.get("last_request_operation") == "session"
                and (diagnostics or {}).get("failure_kind") in {"unknown", "missing_session"}
                and not getattr(exc, "cause_code", "")):
            invalid = ProtocolSessionResponseError("本轮 Session 响应缺少完整身份或 Token，原任务可重跑")
            invalid.__cause__ = exc
            exc = invalid
            diagnostics = observe("failure", exc)
        exc.route_recovery_blocked = route_failure is None
        exc.registration_recovery_audit = context.get("recovery_audit", [])
        if diagnostics is not None:
            try:
                exc.registration_diagnostics = diagnostics
            except Exception:
                pass
        if existing_password or any(context[key] for key in ("password_started", "password_register_accepted", "password_verified", "profile_started", "write_unknown")):
            unknown = ProtocolOssRequestUnknown(
                "开源protocol-2 尚未取得完整会话，可重跑原任务继续",
                register_response_confirmed=context["password_register_accepted"],
                cause_diagnostics=getattr(exc, "protocol_profile_diagnostics", None),
            )
            if getattr(exc, "cause_code", "") in {
                "password_entry_navigation_failed", "password_entry_navigation_timeout", "password_entry_not_offered",
                "identity_mismatch",
                "registration_password_create_rejected", "registration_password_unconfirmed",
                "registration_auth_state_unrecognized", "registration_session_invalid_response",
                "registration_route_close_failed",
                "registration_identity_verification_required",
                "registration_profile_submission_unresolved",
                "user_register_continue_url_missing",
            }:
                unknown.cause_code = exc.cause_code
            if diagnostics is not None:
                unknown.registration_diagnostics = diagnostics
            if route_failure is not None:
                unknown.route_failure = route_failure
            unknown.route_recovery_blocked = exc.route_recovery_blocked
            unknown.registration_recovery_audit = exc.registration_recovery_audit
            raise unknown from exc
        raise
    finally:
        callbacks.reset_context(token)
        for transport in context["sessions"]:
            if transport is not session.session:
                transport.close()
