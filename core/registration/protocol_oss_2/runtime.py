"""开源protocol-2 的网络、邮箱与原 Attempt 检查点桥接。"""
from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from urllib.parse import urlsplit

from core.auth_challenge import AuthCancelledError
from core.http_response_diagnostics import auth_error_from_body, auth_submission_endpoint
from core.registration.protocol_oss import ProtocolOssRequestUnknown

_CONTEXT: ContextVar[dict | None] = ContextVar("protocol_oss_2_context", default=None)

# 上游日志包含响应正文和凭据；本地只通过明确的进度与受控任务诊断报告事实。
_vendor_logger = logging.getLogger("core.registration.protocol_oss_2.upstream")
_vendor_logger.addHandler(logging.NullHandler())
_vendor_logger.propagate = False


class _VendorCancelled(BaseException):
    """Carry cancellation through upstream broad Exception retry handlers."""

    def __init__(self, reason: BaseException):
        self.reason = reason


def _check_stop_requested():
    from core.registration_service import StopRequested, check_stop_requested

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
    """会话重建仍沿用同一代理、停止信号和本地流量关联。"""

    def __init__(self, transport, context: dict):
        self._transport = transport
        self._context = context

    def __getattr__(self, name):
        return getattr(self._transport, name)

    def request(self, method, url, **kwargs):
        _check_stop_requested()
        context = self._context
        path = urlsplit(url).path
        if method.upper() == "POST" and path.endswith("/create_account"):
            context["profile_started"] = True
        profile_submit = method.upper() == "POST" and auth_submission_endpoint(url) == "profile_submit"
        if profile_submit:
            context.pop("profile_diagnostics", None)
        started = time.perf_counter()
        response = None
        error = None
        try:
            response = self._transport.request(method, url, **kwargs)
            response._protocol2_streaming = bool(kwargs.get("stream"))
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
                payload = response.json()
                if isinstance(payload, dict):
                    context["session_info"] = payload
            return response
        except BaseException as exc:
            error = exc
            if method.upper() == "POST":
                context["write_unknown"] = True
            raise
        finally:
            capture = context.get("capture")
            if context.get("observing", True):
                try:
                    observed = _HeaderOnlyResponse(response) if response is not None and kwargs.get("stream") else response
                    if capture is not None:
                        capture.record(started_at=started, response=observed, error=error)
                    from core.registration_debug import record_protocol_exchange

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


def create_http_session(**kwargs):
    """只为当前驱动创建 wreq，会话工厂不修改其他驱动或全局模块。"""
    from core.registration.protocol_oss_2.upstream.http_client_wreq import _HAS_WREQ, create_http_session as create

    if not _HAS_WREQ:
        raise ModuleNotFoundError("开源protocol-2 需要安装 wreq", name="wreq")

    context = _CONTEXT.get()
    if context is None:
        raise RuntimeError("开源protocol-2 缺少注册执行上下文")
    _check_stop_requested()
    kwargs["proxy"] = context["proxy"]
    transport = _ObservedSession(create(**kwargs), context)
    context["sessions"].append(transport)
    return transport


def run_upstream_protocol(
    session, *, email, name, birthday, otp_code, email_source,
    existing_password, existing_totp_secret, options,
):
    """执行固定上游 AuthFlow，邮箱和凭据始终属于本地原任务。"""
    from core.email_provider import wait_for_otp
    from config import email as email_cfg
    from core.registration.checkpoints import save_protocol_password_checkpoint
    from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow
    from core.registration.protocol_oss_2.upstream.config import Config
    from core.registration.protocol_oss_2.upstream.fingerprint import generate_fingerprint
    from core.registration_service import (
        StopRequested, check_stop_requested, registration_fact_context, report_job_progress,
    )

    password_confirmed = False
    if existing_password:
        from core.storage import registration

        facts = registration_fact_context()
        if facts.get("attempt_id") is not None:
            private = registration.get_private_resume_context(int(facts["attempt_id"]), email=email)
            saved_password = private.get("password")
            if saved_password and saved_password != existing_password:
                raise RuntimeError("原 Attempt 的恢复密码不一致，已停止")
            password_confirmed = bool(saved_password) and private.get("password_state") == "confirmed"

    context = {
        "proxy": session.proxy, "capture": session.protocol_traffic, "sessions": [],
        "password_started": False, "password_confirmed": password_confirmed,
        "profile_started": False, "write_unknown": False, "session_info": {},
    }

    def progress(stage, state, detail):
        _check_stop_requested()
        report_job_progress(stage, state, detail)

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
                return code
            try:
                return wait_for_otp(
                    email, after_ts=issued_after, max_wait=timeout, email_source=email_source,
                )
            except (StopRequested, AuthCancelledError) as exc:
                raise _VendorCancelled(exc) from exc

    class LocalAuthFlow(AuthFlow):
        def register_password(self, address):
            if context["password_confirmed"]:
                # 原 Attempt 已有远端确认，续跑沿用原密码并进入邮箱认证分支。
                progress("password", "skipped", "复用原任务已确认的账号密码，本次不重复提交密码注册")
                return False
            accepted = super().register_password(address)
            if not accepted:
                progress("password", "failed", "上游未接受密码注册，继续通过原邮箱验证")
            return accepted

        def _random_password(self):
            if existing_password:
                # 上次可能停在提交前；远端仍走新注册时复用原密码完成该请求。
                return existing_password
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
            context["password_confirmed"] = True
            save_protocol_password_checkpoint(
                email=address, password=password, state="confirmed",
                proxy=session.proxy, email_source=email_source,
            )
            progress("password", "success", "上游已确认密码注册")

        def signup(self, *args, **kwargs):
            progress("submit_email", "running", "正在建立上游邮箱认证状态")
            result = super().signup(*args, **kwargs)
            progress("submit_email", "success", "上游邮箱认证状态已建立")
            progress("auth_redirect", "success", "已进入上游认证流程")
            return result

        def verify_otp(self, code):
            result = super().verify_otp(code)
            progress("email_otp", "success", "上游邮箱验证码已通过")
            return result

        def login_password_verify(self, password):
            progress("login_password", "running", "正在使用原密码继续上游认证")
            self.get_sentinel_token(self.result.device_id)
            result = super().login_password_verify(password)
            context["password_confirmed"] = True
            progress("login_password", "success", "原密码已通过上游认证")
            return result

        def create_account(self):
            context.pop("profile_diagnostics", None)
            context.pop("profile_error", None)
            progress("profile", "running", "正在提交上游注册资料")
            try:
                result = super().create_account()
            except Exception as exc:
                # 上游可能吞掉资料异常后重认证；仅给最终仍传播的同一异常归因。
                context["profile_error"] = exc
                raise
            progress("profile", "success", "上游已确认注册资料")
            return result

        def _resolve_login_password(self, address):
            # 本地没有原密码时，由上游邮箱认证分支处理；不提交推测密码。
            password = str(self.result.password or existing_password or "")
            if not password:
                raise RuntimeError("已有账号需要原密码，请使用原任务重跑补全凭据")
            return password, True

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
        flow.registration_name = name
        flow.registration_birthday = birthday
        flow._last_sentinel_token = ""
        flow._last_sentinel_so_token = ""
        flow.result.password = existing_password or ""
        flow.result.totp_secret = existing_totp_secret or ""
        progress("browser", "success", "开源protocol-2 会话已初始化")
        result = flow.run_register(LocalMailbox())
        check_stop_requested()
        access_token = str(result.access_token or "").strip()
        if not access_token:
            raise RuntimeError("上游注册结束但尚未取得 access_token，可重跑原任务继续")
        session_info = dict(context["session_info"])
        session_info["accessToken"] = access_token
        session.session.close()
        session.session = flow.session
        session.device_id = result.device_id
        session.browser_profile.update(fingerprint)
        session.browser_profile["accept_language"] = fingerprint.get("lang_full", "en-US,en;q=0.9")
        session.browser_profile["navigator_language"] = fingerprint.get("lang", "en-US")
        # 后处理通过 BrowserSession 自身计量，避免对同一请求重复记账。
        context["observing"] = False
        return {
            "access_token": access_token, "session_info": session_info,
            "registration_password": (result.password or None) if context["password_confirmed"] else None,
            "password_validated": context["password_confirmed"],
            "remote_identity": "existing" if existing_password or flow._is_existing_account else "new",
            "challenge_chain": ["password", "email_otp"],
        }
    except _VendorCancelled as exc:
        raise exc.reason
    except (StopRequested, AuthCancelledError):
        raise
    except Exception as exc:
        if existing_password or any(context[key] for key in ("password_started", "password_confirmed", "profile_started", "write_unknown")):
            raise ProtocolOssRequestUnknown(
                "开源protocol-2 尚未取得完整会话，可重跑原任务继续",
                register_response_confirmed=context["password_confirmed"],
                cause_diagnostics=context.get("profile_diagnostics") if context.get("profile_error") is exc else None,
            ) from exc
        raise
    finally:
        _CONTEXT.reset(token)
        for transport in context["sessions"]:
            if transport is not session.session:
                transport.close()
