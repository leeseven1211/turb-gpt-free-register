# -*- coding: utf-8 -*-
"""已注册账号查活：重新邮箱 OTP 登录，成功拿到最新 ChatGPT accessToken 即视为正常。"""
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from config import openai_protocol as _protocol_cfg
from core.auth.email_guard import serialize_email_auth
from core.auth.protocol.session import BrowserSession
from core.auth.protocol.chatgpt_auth import get_csrf_token, get_providers, probe_auth_session, signin_openai
from core.auth.protocol.openai_auth import follow_authorize, network_preflight, send_email_otp, validate_email_otp, EmailOtpInvalidError, AccountUnusableError, detect_account_unusable_text
from core.accounts.export import follow_oauth_callback, fetch_session
from core.email.email_butler.client import EmailButlerClientError
from core.email.provider import wait_for_otp
from core.accounts.credentials import account_email_is_invalid
from core.accounts.liveness.protocol.otp_diagnostics import mark_otp_failure
from core.accounts.liveness.protocol.otp_delivery import ensure_initial_otp_sent as _ensure_at_otp_sent, resend_otp as _resend_at_otp
from core.auth.humanize import delay as human_delay
from core.runtime.paths import task_log_root

logger = logging.getLogger('core.account_liveness')
_LOG_DIR = task_log_root()
_RUNNING: set[str] = set()
_RUNNING_LOCK = threading.Lock()

# 查活网络预检失败（403/429/代理/超时等）多为出口 IP 被 CF 标记或代理池抖动，
# 视为可换新 IP 重试；账号本身问题（废号/邮箱错误等）不重试。
_RETRYABLE_NETWORK_HINTS = (
    "403", "429", "502", "503", "504",
    "proxy", "socks", "timeout", "timed out",
    "connection", "closed", "reset",
)


def _is_retryable_network_error(exc: BaseException) -> bool:
    from core.network.at_transport_recovery import current_scope, exhausted, network_failure

    if current_scope() is not None:
        return not exhausted(exc) and network_failure(error=exc) is not None
    if isinstance(exc, AccountUnusableError):
        return False
    text = str(exc or "").lower()
    return any(h in text for h in _RETRYABLE_NETWORK_HINTS)


def _warm_protocol_login_context(session: BrowserSession) -> None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v1 import _warm_protocol_login_context as execute, WarmProtocolLoginContextDependencies
    dependencies = WarmProtocolLoginContextDependencies(
        _clear_optional_bootstrap_circuit=_clear_optional_bootstrap_circuit,
        _protocol_cfg=_protocol_cfg,
        get_providers=get_providers,
        human_delay=human_delay,
        network_preflight=network_preflight,
        probe_auth_session=probe_auth_session,
    )
    return execute(session, _deps=dependencies)


def _clear_optional_bootstrap_circuit(session: BrowserSession) -> None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v1 import _clear_optional_bootstrap_circuit as execute, ClearOptionalBootstrapCircuitDependencies
    dependencies = ClearOptionalBootstrapCircuitDependencies(
    )
    return execute(session, _deps=dependencies)


def _warm_authenticated_session(session: BrowserSession, access_token: str) -> None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v1 import _warm_authenticated_session as execute, WarmAuthenticatedSessionDependencies
    dependencies = WarmAuthenticatedSessionDependencies(
        _clear_optional_bootstrap_circuit=_clear_optional_bootstrap_circuit,
        logger=logger,
    )
    return execute(session, access_token, _deps=dependencies)


def _session_identity_payload(session: BrowserSession) -> dict | None:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v1 import _session_identity_payload as execute, SessionIdentityPayloadDependencies
    dependencies = SessionIdentityPayloadDependencies(
    )
    return execute(session, _deps=dependencies)


def _complete_recent_login_on_session(
    session: BrowserSession,
    email: str,
    final_url: str,
    otp_after_ts: float,
    *,
    email_source: str | None,
) -> tuple[dict, str]:
    """Finish a fresh protocol login after the authorize navigation."""
    from core.accounts.credentials import get_account_login_credentials
    from core.accounts.liveness.protocol.v2 import _complete_mfa, _extract_continue_url, _follow_and_fetch, _is_email_otp, _is_mfa, _password_verify

    parsed = urlparse(str(final_url or ""))
    final_host = (parsed.hostname or "").lower()
    final_path = parsed.path.rstrip("/").lower() or "/"
    password, totp_secret = get_account_login_credentials(str(email or "").strip())

    if final_host == "auth.openai.com" and final_path == "/email-verification":
        validate_result = _validate_with_retry(
            session,
            email,
            otp_after_ts,
            email_source=email_source,
        )
        continue_url = _extract_continue_url(validate_result)
        if _is_mfa(validate_result, continue_url):
            if not totp_secret:
                raise RuntimeError("Recent Login 需要 TOTP，但账号未保存 TOTP 密钥")
            session_info, _ = _complete_mfa(
                session,
                validate_result,
                continue_url,
                totp_secret,
            )
            return session_info, "email_otp_mfa"
        return (
            _follow_and_fetch(
                session,
                continue_url,
                referer="https://auth.openai.com/email-verification",
            ),
            "email_otp",
        )

    if final_host == "auth.openai.com" and final_path.startswith("/mfa-challenge"):
        if not totp_secret:
            raise RuntimeError("Recent Login 需要 TOTP，但账号未保存 TOTP 密钥")
        session_info, _ = _complete_mfa(
            session,
            {"continue_url": str(final_url)},
            str(final_url),
            totp_secret,
        )
        return session_info, "mfa_totp"

    if final_host != "auth.openai.com" or final_path != "/log-in/password":
        raise RuntimeError(
            f"Recent Login 落点不受支持：host={final_host or 'unknown'} path={final_path}"
        )
    if not password:
        raise RuntimeError("Recent Login 进入密码页，但账号未保存 OpenAI 登录密码")

    password_result = _password_verify(session, password)
    continue_url = _extract_continue_url(password_result)
    if _is_mfa(password_result, continue_url):
        if not totp_secret:
            raise RuntimeError("Recent Login 需要 TOTP，但账号未保存 TOTP 密钥")
        return _complete_mfa(
            session,
            password_result,
            continue_url,
            totp_secret,
        )
    if _is_email_otp(password_result, continue_url):
        validate_result = _validate_with_retry(
            session,
            email,
            otp_after_ts,
            email_source=email_source,
        )
        email_continue_url = _extract_continue_url(validate_result)
        if _is_mfa(validate_result, email_continue_url):
            if not totp_secret:
                raise RuntimeError("Recent Login 需要 TOTP，但账号未保存 TOTP 密钥")
            session_info, _ = _complete_mfa(
                session,
                validate_result,
                email_continue_url,
                totp_secret,
            )
            return session_info, "password_email_otp_mfa"
        return (
            _follow_and_fetch(
                session,
                email_continue_url,
                referer="https://auth.openai.com/email-verification",
            ),
            "password_email_otp",
        )
    if continue_url:
        return (
            _follow_and_fetch(
                session,
                continue_url,
                referer="https://auth.openai.com/log-in/password",
            ),
            "password",
        )
    raise RuntimeError("Recent Login 密码验证响应缺少后续认证地址")


@serialize_email_auth
def perform_recent_login(
    session: BrowserSession,
    email: str,
    *,
    email_source: str | None = None,
    access_token: str | None = None,
) -> dict:
    """Build a fresh cookie session and complete a protocol-only login.

    A new access token is not sufficient for the change-email endpoint: the
    follow-up request must use the same fresh Cookie Jar that completed the
    login.  This mirrors the public implementation while retaining this
    project's stable account identity and durable task boundaries.
    """
    del access_token  # Kept in the signature for compatibility with callers.
    selected_proxy = getattr(session, "proxy", None)
    # Recent Login 属于当前邮箱换绑认证链。预检失败时只允许在同一已领取
    # 线路上由预检函数重建会话重试；不能在认证链中途改成直连或另一条线路。
    fresh_session, authorize_url = _network_preflight_with_retry(
        str(email or "").strip(),
        selected_proxy,
        identity=_session_identity_payload(session),
    )
    otp_after_ts = time.time()
    final_url = follow_authorize(fresh_session, authorize_url)
    dead_code = detect_account_unusable_text(final_url)
    if dead_code:
        raise AccountUnusableError(f"账号已废弃（{dead_code}）", error_code=dead_code)
    session_info, auth_method = _complete_recent_login_on_session(
        fresh_session,
        str(email or "").strip(),
        str(final_url or ""),
        otp_after_ts,
        email_source=email_source,
    )
    fresh_token = str((session_info or {}).get("accessToken") or "").strip()
    if not fresh_token:
        raise RuntimeError("Recent Login 未获取到新的 access_token")
    _warm_authenticated_session(fresh_session, fresh_token)
    try:
        session.session.close()
    except Exception:
        pass
    return {
        "access_token": fresh_token,
        "reauthenticated": True,
        "auth_method": auth_method,
        "protocol_session": fresh_session,
    }


def _network_preflight_with_retry(
    email: str,
    proxy: str | None,
    max_attempts: int = 4,
    *,
    proxy_supplier: Callable[[int], str | None] | None = None,
    identity=None,
    context_recorder=None,
    on_preflight_failure: Callable[[BaseException], None] | None = None,
) -> tuple[BrowserSession, str]:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v1 import _network_preflight_with_retry as execute, NetworkPreflightWithRetryDependencies
    dependencies = NetworkPreflightWithRetryDependencies(
        time=time,
        BrowserSession=BrowserSession,
        _is_retryable_network_error=_is_retryable_network_error,
        _warm_protocol_login_context=_warm_protocol_login_context,
        get_csrf_token=get_csrf_token,
        human_delay=human_delay,
        logger=logger,
        probe_auth_session=probe_auth_session,
        signin_openai=signin_openai,
    )
    return execute(email, proxy, max_attempts, proxy_supplier=proxy_supplier, identity=identity, context_recorder=context_recorder, on_preflight_failure=on_preflight_failure, _deps=dependencies)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_path(email: str) -> Path:
    safe = str(email or "").replace("/", "_").replace("\\", "_").replace(":", "_")
    return _LOG_DIR / f"live-check-{safe}.log"


def is_checking(email: str) -> bool:
    key = str(email or "").strip().lower()
    with _RUNNING_LOCK:
        return key in _RUNNING


def _validate_with_retry(
    session: BrowserSession,
    email: str,
    otp_after_ts: float,
    max_otp_attempts: int = 3,
    email_source: str | None = None,
    *,
    at_validator: Callable[[str], dict] | None = None,
) -> dict:
    """Compatibility entry; execution and explicit capabilities live in the kernel."""
    from core.kernels.protocol.local.refresh_at.v1 import _validate_with_retry as execute, ValidateWithRetryDependencies
    dependencies = ValidateWithRetryDependencies(
        time=time,
        EmailButlerClientError=EmailButlerClientError,
        EmailOtpInvalidError=EmailOtpInvalidError,
        _ensure_at_otp_sent=_ensure_at_otp_sent,
        _is_retryable_network_error=_is_retryable_network_error,
        _resend_at_otp=_resend_at_otp,
        logger=logger,
        mark_otp_failure=mark_otp_failure,
        send_email_otp=send_email_otp,
        validate_email_otp=validate_email_otp,
        wait_for_otp=wait_for_otp,
    )
    return execute(session, email, otp_after_ts, max_otp_attempts, email_source, at_validator=at_validator, _deps=dependencies)


def _authenticate_email_session(session, email: str, authorize_url: str, checked_at: str, *, on_remote_request_started=None, callback_handler=None) -> dict:
    """Pass current compatibility primitives into the protocol execution kernel."""
    from core.kernels.protocol.local.refresh_at.v1 import _authenticate_email_session as execute, AuthenticateEmailSessionDependencies
    dependencies = AuthenticateEmailSessionDependencies(
        _validate_with_retry=_validate_with_retry,
        detect_account_unusable_text=detect_account_unusable_text,
        fetch_session=fetch_session,
        follow_authorize=follow_authorize,
        follow_oauth_callback=follow_oauth_callback,
        logger=logger,
        time=time,
    )
    return execute(session, email, authorize_url, checked_at, on_remote_request_started=on_remote_request_started, callback_handler=callback_handler, _deps=dependencies)


@serialize_email_auth
def check_account_liveness(
    email: str,
    proxy: str | None = None,
    *,
    clear_log: bool = True,
    proxy_supplier: Callable[[int], str | None] | None = None,
    on_remote_request_started: Callable[[], None] | None = None,
    on_authenticated=None,
    on_network_failure=None,
    callback_handler=None,
) -> dict:
    """
    重新登录账号并刷新最新 accessToken。

    返回：
      {
        ok: bool,
        status: live/deactivated/failed,
        access_token: str?,
        session: dict?,
        checked_at: ISO,
        error: str?
      }
    """
    email = str(email or "").strip()
    if not email:
        raise ValueError("email 不能为空")

    if account_email_is_invalid(email):
        from core.accounts.liveness.protocol.v2 import refresh_access_token

        logger.info("[查活] 邮箱已失效，改用保存的密码及 2FA 刷新 AT")
        return refresh_access_token(
            email, proxy=proxy, proxy_supplier=proxy_supplier,
            on_remote_request_started=on_remote_request_started,
            **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
            **({"on_network_failure": on_network_failure} if callable(on_network_failure) else {}),
        )

    checked_at = _now()
    key = email.lower()
    path = log_path(email)
    path.parent.mkdir(parents=True, exist_ok=True)
    if clear_log:
        path.write_text("", encoding="utf-8")

    fh: logging.FileHandler | None = None
    session: BrowserSession | None = None
    root_logger = logging.getLogger()
    thread_name = threading.current_thread().name
    with _RUNNING_LOCK:
        _RUNNING.add(key)
    try:
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        fh.addFilter(lambda record: record.threadName == thread_name)
        root_logger.addHandler(fh)

        logger.info("[查活] 日志文件：%s", path)
        logger.info("[查活] 开始重新登录：%s", email)
        logger.info(
            "[查活] 流程：浏览器指纹会话 → 页面/匿名态预热 → CSRF → Signin → "
            "Authorize → 邮箱 OTP → OAuth callback → Session/AT"
        )
        session, authorize_url = _network_preflight_with_retry(
            email,
            proxy,
            proxy_supplier=proxy_supplier,
            **({"on_preflight_failure": on_network_failure} if callable(on_network_failure) else {}),
        )

        result = _authenticate_email_session(
            session, email, authorize_url, checked_at,
            on_remote_request_started=on_remote_request_started, callback_handler=callback_handler,
        )
        return on_authenticated(result, session) if result.get("ok") and callable(on_authenticated) else result
    except AccountUnusableError as exc:
        code = getattr(exc, "error_code", "") or detect_account_unusable_text(str(exc)) or "account_deactivated"
        logger.warning("[查活] 已废号：%s %s", email, code)
        return {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code}
    except Exception as exc:
        if callable(callback_handler):
            from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError, _reraise_control

            _reraise_control(exc)
            if isinstance(exc, ProtocolV2AuthError):
                raise
        if callable(on_network_failure):
            on_network_failure(exc)
        code = detect_account_unusable_text(str(exc))
        if code:
            logger.warning("[查活] 已废号：%s %s", email, code)
            return {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code}
        logger.warning("[查活] 失败：%s %s: %s", email, type(exc).__name__, str(exc)[:260])
        result = {"ok": False, "status": "failed", "checked_at": checked_at, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
        from core.network.at_transport_recovery import current_scope, network_failure

        if current_scope() is not None:
            diagnostics = network_failure(error=exc)
            if diagnostics is not None:
                result["auth_diagnostics"] = {"operation": "protocol_v2_auth", **diagnostics}
        return result
    finally:
        try:
            logger.info("[查活] 结束：%s", email)
            if session is not None:
                try:
                    session.session.close()
                except Exception:
                    pass
            if fh is not None:
                root_logger.removeHandler(fh)
                fh.close()
        finally:
            with _RUNNING_LOCK:
                _RUNNING.discard(key)
