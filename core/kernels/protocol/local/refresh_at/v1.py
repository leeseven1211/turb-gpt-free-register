# -*- coding: utf-8 -*-
"""Authentication execution extracted without domain storage or task ownership.

Explicit dependencies preserve the original compatibility patch points.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.auth.protocol.session import BrowserSession

@dataclass(frozen=True)
class WarmProtocolLoginContextDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _clear_optional_bootstrap_circuit: Any
    _protocol_cfg: Any
    get_providers: Any
    human_delay: Any
    network_preflight: Any
    probe_auth_session: Any


def _warm_protocol_login_context(session: BrowserSession, *, _deps: WarmProtocolLoginContextDependencies) -> None:
    """按真实登录页顺序建立 Cookie、动态 build 与匿名 NextAuth 上下文。"""
    _clear_optional_bootstrap_circuit = _deps._clear_optional_bootstrap_circuit
    _protocol_cfg = _deps._protocol_cfg
    get_providers = _deps.get_providers
    human_delay = _deps.human_delay
    network_preflight = _deps.network_preflight
    probe_auth_session = _deps.probe_auth_session
    network_preflight(session)
    human_delay("navigate")
    if getattr(_protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", True):
        from core.auth.protocol.chatgpt_bootstrap import anonymous_bootstrap

        anonymous_bootstrap(
            session,
            strict=bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)),
        )
        human_delay("navigate")
    # best-effort bootstrap 的非关键接口不能阻断正式认证链；随后复现
    # 成功浏览器样本的 providers → session → CSRF → session 顺序。
    _clear_optional_bootstrap_circuit(session)
    get_providers(session)
    probe_auth_session(session)


@dataclass(frozen=True)
class ClearOptionalBootstrapCircuitDependencies:
    """Capabilities resolved by the domain at this invocation."""
    pass


def _clear_optional_bootstrap_circuit(session: BrowserSession, *, _deps: ClearOptionalBootstrapCircuitDependencies) -> None:
    """Clear a best-effort bootstrap circuit without replacing the cookie jar."""
    reset = getattr(session, "reset_circuit_breaker", None)
    if callable(reset):
        reset()
        return
    if getattr(session, "blocked_until", 0.0):
        session.blocked_until = 0.0
        session.blocked_reason = ""


@dataclass(frozen=True)
class WarmAuthenticatedSessionDependencies:
    """Capabilities resolved by the domain at this invocation."""
    _clear_optional_bootstrap_circuit: Any
    logger: Any


def _warm_authenticated_session(session: BrowserSession, access_token: str, *, _deps: WarmAuthenticatedSessionDependencies) -> None:
    """Warm the authenticated HTTP session; optional failures stay non-fatal."""
    _clear_optional_bootstrap_circuit = _deps._clear_optional_bootstrap_circuit
    logger = _deps.logger
    if not str(access_token or "").strip():
        return
    from core.auth.protocol.chatgpt_bootstrap import authenticated_bootstrap

    try:
        authenticated_bootstrap(session, access_token, strict=False)
    except Exception as exc:
        logger.warning(
            "[Recent Login] 登录态预热失败，继续正式认证链：%s: %s",
            type(exc).__name__,
            str(exc)[:180],
        )
    finally:
        _clear_optional_bootstrap_circuit(session)


@dataclass(frozen=True)
class SessionIdentityPayloadDependencies:
    """Capabilities resolved by the domain at this invocation."""
    pass


def _session_identity_payload(session: BrowserSession, *, _deps: SessionIdentityPayloadDependencies) -> dict | None:
    """Carry the stable account identity into a fresh cookie session."""
    device_id = str(getattr(session, "device_id", "") or "").strip()
    browser_profile = getattr(session, "browser_profile", None)
    if not device_id or not isinstance(browser_profile, dict):
        return None
    return {
        "device_id": device_id,
        "identity_id": getattr(session, "protocol_identity_id", None),
        "profile_ref": getattr(session, "protocol_profile_ref", None),
        "profile_version": getattr(session, "protocol_profile_version", None),
        "browser_profile": dict(browser_profile),
    }


@dataclass(frozen=True)
class NetworkPreflightWithRetryDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    BrowserSession: Any
    _is_retryable_network_error: Any
    _warm_protocol_login_context: Any
    get_csrf_token: Any
    human_delay: Any
    logger: Any
    probe_auth_session: Any
    signin_openai: Any


def _network_preflight_with_retry(email: str, proxy: str | None, max_attempts: int=4, *, proxy_supplier: Callable[[int], str | None] | None=None, identity=None, context_recorder=None, on_preflight_failure: Callable[[BaseException], None] | None=None, _deps: NetworkPreflightWithRetryDependencies) -> tuple[BrowserSession, str]:
    """页面/匿名态预热 → CSRF → Signin；每轮建新会话并可换新代理。

    /api/auth/providers 只是 NextAuth 的能力发现接口，登录流程并不依赖它；
    该接口又更容易被 Cloudflare 单独拦截，因此查活刷新 AT 时直接从 CSRF 开始。
    """
    time = _deps.time
    BrowserSession = _deps.BrowserSession
    _is_retryable_network_error = _deps._is_retryable_network_error
    _warm_protocol_login_context = _deps._warm_protocol_login_context
    get_csrf_token = _deps.get_csrf_token
    human_delay = _deps.human_delay
    logger = _deps.logger
    probe_auth_session = _deps.probe_auth_session
    signin_openai = _deps.signin_openai
    from core.network.at_transport_recovery import current_scope

    if current_scope() is not None:
        # AT 的请求层负责原线恢复，跨线路重启统一由独立 AT worker 管理。
        max_attempts = 1
    session: BrowserSession | None = None
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        if session is not None:
            if context_recorder is not None:
                context_recorder.finish_session(
                    session,
                    status="rotated",
                    result_code="network_preflight_retry",
                )
            try:
                session.session.close()
            except Exception:
                pass
        selected_proxy = proxy_supplier(attempt) if proxy_supplier is not None else proxy
        # 直连没有可轮换的出口。重复创建会话只会再次撞同一个 Auth
        # 边缘路由，并把一次确定性的线路拒绝放大成四次失败。
        attempt_limit = attempt if not str(selected_proxy or "").strip() else max_attempts
        # 空字符串是账号代理服务明确选择“直连”，不能转成 None 后又静默回退 PROXY_POOL。
        session_kwargs = {"proxy": selected_proxy}
        if identity is not None:
            session_kwargs["identity"] = identity
        session = BrowserSession(**session_kwargs)
        if context_recorder is not None:
            context_recorder.open_protocol_session(session, route_attempt_no=attempt)
        logger.info(
            "[查活] 会话创建完成：proxy=%s device_id=已隐藏（网络预检第 %s/%s 次）",
            session.proxy or "配置随机/直连", attempt, attempt_limit,
        )
        try:
            _warm_protocol_login_context(session)
            csrf = get_csrf_token(session)
            human_delay("api")
            probe_auth_session(session)
            authorize_url = signin_openai(session, csrf, email)
            return session, authorize_url
        except Exception as exc:
            last_exc = exc
            if callable(on_preflight_failure):
                try:
                    on_preflight_failure(exc)
                except Exception:
                    try:
                        session.session.close()
                    except Exception:
                        pass
                    raise
            if attempt >= attempt_limit or not _is_retryable_network_error(exc):
                try:
                    session.session.close()
                except Exception:
                    pass
                raise
            logger.warning(
                "[查活] 网络预检失败（%s/%s），%s：%s",
                attempt, attempt_limit,
                "释放当前线路并换新代理重试" if proxy_supplier is not None else "同一线路创建新会话重试",
                str(exc)[:200],
            )
            time.sleep(2)
    raise RuntimeError(f"网络预检多次失败：{last_exc}")


@dataclass(frozen=True)
class ValidateWithRetryDependencies:
    """Capabilities resolved by the domain at this invocation."""
    time: Any
    EmailButlerClientError: Any
    EmailOtpInvalidError: Any
    _ensure_at_otp_sent: Any
    _is_retryable_network_error: Any
    _resend_at_otp: Any
    logger: Any
    mark_otp_failure: Any
    send_email_otp: Any
    validate_email_otp: Any
    wait_for_otp: Any


def _validate_with_retry(session: BrowserSession, email: str, otp_after_ts: float, max_otp_attempts: int | None=None, email_source: str | None=None, *, at_validator: Callable[[str], dict] | None=None, _deps: ValidateWithRetryDependencies) -> dict:
    time = _deps.time
    EmailButlerClientError = _deps.EmailButlerClientError
    EmailOtpInvalidError = _deps.EmailOtpInvalidError
    _ensure_at_otp_sent = _deps._ensure_at_otp_sent
    _is_retryable_network_error = _deps._is_retryable_network_error
    _resend_at_otp = _deps._resend_at_otp
    logger = _deps.logger
    mark_otp_failure = _deps.mark_otp_failure
    send_email_otp = _deps.send_email_otp
    validate_email_otp = _deps.validate_email_otp
    wait_for_otp = _deps.wait_for_otp
    from core.network.at_transport_recovery import current_scope

    if max_otp_attempts is None:
        # 与注册/续跑统一：1 次等待 + OTP_RESEND_COUNT 次重发。
        try:
            from config import email as email_cfg

            max_otp_attempts = 1 + max(0, int(getattr(email_cfg, "OTP_RESEND_COUNT", 1) or 0))
        except Exception:
            max_otp_attempts = 2
    at_scope = current_scope()
    if at_scope is not None:
        # AT 刷新的传输恢复预算更紧：最多两轮。
        max_otp_attempts = min(max_otp_attempts, 2)
        try:
            otp_after_ts = _ensure_at_otp_sent(session, email, otp_after_ts, checkpoint=at_scope.check)
        except Exception as send_exc:
            mark_otp_failure(send_exc, "email_otp_send")
            raise
    current_otp = None
    last_exc: Exception | None = None
    for attempt in range(1, max_otp_attempts + 1):
        otp_operation = "email_otp"
        try:
            if current_otp is None:
                logger.info("[查活] 等待登录 OTP：%s（第 %s/%s 次）", email, attempt, max_otp_attempts)
                current_otp = wait_for_otp(
                    email,
                    after_ts=otp_after_ts,
                    email_source=email_source,
                    # 未指定来源时遵循全局配置，并由取码器解析账号保存的邮箱来源。
                    force_service=True if email_source else None,
                )
            otp_operation = "email_otp_validate"
            if at_scope is not None and at_validator is not None:
                result = at_validator(current_otp)
            else:
                result = validate_email_otp(session, current_otp, sentinel_header=None, so_header=None)
            return result
        except EmailOtpInvalidError as exc:
            mark_otp_failure(exc, otp_operation)
            last_exc = exc
            if attempt >= max_otp_attempts:
                break
            logger.warning("[查活] OTP 无效/过期，重新发送后再取：%s", str(exc)[:180])
            if at_scope is not None:
                at_scope.check()
            resend_started_at = time.time() if at_scope is not None else None
            try:
                if at_scope is not None:
                    _resend_at_otp(session, checkpoint=at_scope.check)
                else:
                    send_email_otp(session)
            except Exception as send_exc:
                mark_otp_failure(send_exc, "email_otp_send")
                raise
            # AT 从发码前收件，避免漏掉请求返回前已投递的新码；其他入口沿用原时间窗。
            otp_after_ts = resend_started_at if resend_started_at is not None else time.time()
            current_otp = None
            time.sleep(1)
        except Exception as exc:
            mark_otp_failure(exc, otp_operation)
            # 无邮件超时允许在原会话重发，不作为 OpenAI 代理的网络故障。
            no_mail_timeout = (
                at_scope is not None
                and otp_operation == "email_otp"
                and isinstance(exc, EmailButlerClientError)
                and exc.error_code == "inbound_code_timeout"
                and exc.status_code in (None, 408)
            )
            if attempt >= max_otp_attempts or not (no_mail_timeout or _is_retryable_network_error(exc)):
                raise
            if at_scope is not None:
                at_scope.check()
            last_exc = exc
            if no_mail_timeout:
                logger.warning("[查活] 等待登录验证码超时，在原会话重新发送后继续等待（%s/%s）", attempt, max_otp_attempts)
            else:
                logger.warning("[查活] 邮箱验证码阶段失败，重新发送后再取（%s/%s）：%s", attempt, max_otp_attempts, str(exc)[:180])
            resend_started_at = time.time() if at_scope is not None else None
            try:
                if at_scope is not None:
                    _resend_at_otp(session, checkpoint=at_scope.check)
                else:
                    send_email_otp(session)
            except Exception as send_exc:
                mark_otp_failure(send_exc, "email_otp_send")
                raise
            otp_after_ts = resend_started_at if resend_started_at is not None else time.time()
            current_otp = None
            time.sleep(1)
    raise last_exc if last_exc else RuntimeError("OTP 验证失败")




@dataclass(frozen=True)
class AuthenticateEmailSessionDependencies:
    """Current protocol primitives supplied by the account domain."""
    _validate_with_retry: Any
    detect_account_unusable_text: Any
    fetch_session: Any
    follow_authorize: Any
    follow_oauth_callback: Any
    logger: Any
    time: Any


def _authenticate_email_session(session, email: str, authorize_url: str, checked_at: str, *, on_remote_request_started=None, callback_handler=None, _deps: AuthenticateEmailSessionDependencies) -> dict:
    """Authorize, verify email and acquire Session/AT on the already-owned session."""
    _validate_with_retry = _deps._validate_with_retry
    detect_account_unusable_text = _deps.detect_account_unusable_text
    fetch_session = _deps.fetch_session
    follow_authorize = _deps.follow_authorize
    follow_oauth_callback = _deps.follow_oauth_callback
    logger = _deps.logger
    time = _deps.time
    if callable(on_remote_request_started):
        on_remote_request_started()
    otp_after_ts = time.time()
    final_url = follow_authorize(session, authorize_url)
    dead_code = detect_account_unusable_text(final_url)
    if dead_code:
        return {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": dead_code}

    validate_result = _validate_with_retry(session, email, otp_after_ts)
    page = validate_result.get("page") if isinstance(validate_result, dict) else {}
    page = page if isinstance(page, dict) else {}
    page_type = str(page.get("type") or "")
    continue_url = (
        validate_result.get("continue_url")
        or validate_result.get("external_url")
        or validate_result.get("url")
        or page.get("continue_url")
        or page.get("external_url")
        or page.get("url")
    )
    if not continue_url:
        raise RuntimeError(f"OTP 登录成功但没有 OAuth continue_url: {validate_result}")
    if "about-you" in str(continue_url) or page_type in {"about_you", "about-you"}:
        raise RuntimeError(f"该邮箱登录后进入资料页，疑似不是完整已注册账号: page_type={page_type}, continue_url={continue_url}")

    if callable(callback_handler):
        # AT v2 显式注入恢复能力，其他调用方继续使用既有回调。
        session_info = callback_handler(session, str(continue_url), referer="https://auth.openai.com/email-verification")
    else:
        follow_oauth_callback(session, str(continue_url), referer="https://auth.openai.com/email-verification")
        session_info = fetch_session(session)
    access_token = str(session_info.get("accessToken") or "")
    if not access_token:
        raise RuntimeError("重新登录后未拿到 accessToken")

    user = session_info.get("user") or {}
    account = session_info.get("account") or {}
    logger.info("[查活] 正常：%s user_id=%s plan=%s", email, user.get("id"), account.get("planType"))
    result = {
        "ok": True,
        "status": "live",
        "checked_at": checked_at,
        "access_token": access_token,
        "session": session_info,
        "device_id": session.device_id,
        "proxy_used": session.proxy or None,
        "validation_method": "email_otp",
    }
    return result
