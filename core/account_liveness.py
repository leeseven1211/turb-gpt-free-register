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
from core.session import BrowserSession
from core.chatgpt_auth import get_csrf_token, get_providers, probe_auth_session, signin_openai
from core.openai_auth import (
    follow_authorize,
    network_preflight,
    send_email_otp,
    validate_email_otp,
    EmailOtpInvalidError,
    AccountUnusableError,
    detect_account_unusable_text,
)
from core.account_export import follow_oauth_callback, fetch_session
from core.email_provider import wait_for_otp
from core.humanize import delay as human_delay

logger = logging.getLogger(__name__)
_LOG_DIR = Path(__file__).resolve().parent.parent / "注册日志"
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
    if isinstance(exc, AccountUnusableError):
        return False
    text = str(exc or "").lower()
    return any(h in text for h in _RETRYABLE_NETWORK_HINTS)


def _warm_protocol_login_context(session: BrowserSession) -> None:
    """按真实登录页顺序建立 Cookie、动态 build 与匿名 NextAuth 上下文。"""
    network_preflight(session)
    human_delay("navigate")
    if getattr(_protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", True):
        from core.chatgpt_bootstrap import anonymous_bootstrap

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


def _clear_optional_bootstrap_circuit(session: BrowserSession) -> None:
    """Clear a best-effort bootstrap circuit without replacing the cookie jar."""
    reset = getattr(session, "reset_circuit_breaker", None)
    if callable(reset):
        reset()
        return
    if getattr(session, "blocked_until", 0.0):
        session.blocked_until = 0.0
        session.blocked_reason = ""


def _warm_authenticated_session(session: BrowserSession, access_token: str) -> None:
    """Warm the authenticated HTTP session; optional failures stay non-fatal."""
    if not str(access_token or "").strip():
        return
    from core.chatgpt_bootstrap import authenticated_bootstrap

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


def _session_identity_payload(session: BrowserSession) -> dict | None:
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


def _complete_recent_login_on_session(
    session: BrowserSession,
    email: str,
    final_url: str,
    otp_after_ts: float,
    *,
    email_source: str | None,
) -> tuple[dict, str]:
    """Finish a fresh protocol login after the authorize navigation."""
    from core.account_credentials import get_account_login_credentials
    from core.protocol_v2_liveness import (
        _complete_mfa,
        _extract_continue_url,
        _follow_and_fetch,
        _is_email_otp,
        _is_mfa,
        _password_verify,
    )

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
    # A proxy can pass the anonymous preflight and still be rejected when the
    # authorize redirect crosses into auth.openai.com.  Keep this recovery
    # protocol-only: after a retryable 403/429/transport failure on the
    # selected proxy, rebuild the whole login session once on direct network.
    # The old implementation retried the same route only, which left email
    # change unable to recover from a bad 1024Proxy exit before any write.
    routes = [(selected_proxy, _session_identity_payload(session), "selected")]
    if selected_proxy:
        routes.append(("", None, "direct"))

    last_exc: BaseException | None = None
    for route_index, (route_proxy, route_identity, route_label) in enumerate(routes):
        fresh_session: BrowserSession | None = None
        try:
            if route_index:
                logger.warning(
                    "[Recent Login] 代理线路失败，切换协议直连兜底：route=%s",
                    route_label,
                )
            fresh_session, authorize_url = _network_preflight_with_retry(
                str(email or "").strip(),
                route_proxy,
                identity=route_identity,
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
        except AccountUnusableError:
            raise
        except Exception as exc:
            last_exc = exc
            retryable = _is_retryable_network_error(exc)
            should_try_next_route = (
                route_index == 0
                and bool(selected_proxy)
                and len(routes) > 1
                and retryable
            )
            if fresh_session is not None:
                try:
                    fresh_session.session.close()
                except Exception:
                    pass
            if not should_try_next_route:
                raise
            logger.warning(
                "[Recent Login] 代理路线失败，将使用协议直连重建会话：%s: %s",
                type(exc).__name__,
                str(exc)[:180],
            )

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Recent Login 路线为空")


def _network_preflight_with_retry(
    email: str,
    proxy: str | None,
    max_attempts: int = 4,
    *,
    proxy_supplier: Callable[[int], str | None] | None = None,
    identity=None,
    context_recorder=None,
) -> tuple[BrowserSession, str]:
    """页面/匿名态预热 → CSRF → Signin；每轮建新会话并可换新代理。

    /api/auth/providers 只是 NextAuth 的能力发现接口，登录流程并不依赖它；
    该接口又更容易被 Cloudflare 单独拦截，因此查活刷新 AT 时直接从 CSRF 开始。
    """
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
        # 空字符串是账号代理服务明确选择“直连”，不能转成 None 后又静默回退 PROXY_POOL。
        session_kwargs = {"proxy": selected_proxy}
        if identity is not None:
            session_kwargs["identity"] = identity
        session = BrowserSession(**session_kwargs)
        if context_recorder is not None:
            context_recorder.open_protocol_session(session, route_attempt_no=attempt)
        logger.info(
            "[查活] 会话创建完成：proxy=%s device_id=已隐藏（网络预检第 %s/%s 次）",
            session.proxy or "配置随机/直连", attempt, max_attempts,
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
            if attempt >= max_attempts or not _is_retryable_network_error(exc):
                try:
                    session.session.close()
                except Exception:
                    pass
                raise
            logger.warning(
                "[查活] 网络预检失败（%s/%s），%s：%s",
                attempt, max_attempts,
                "释放当前线路并换新代理重试" if proxy_supplier is not None else "同一线路创建新会话重试",
                str(exc)[:200],
            )
            time.sleep(2)
    raise RuntimeError(f"网络预检多次失败：{last_exc}")


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
) -> dict:
    current_otp = None
    last_exc: Exception | None = None
    for attempt in range(1, max_otp_attempts + 1):
        try:
            if current_otp is None:
                logger.info("[查活] 等待登录 OTP：%s（第 %s/%s 次）", email, attempt, max_otp_attempts)
                current_otp = wait_for_otp(
                    email,
                    after_ts=otp_after_ts,
                    email_source=email_source,
                    force_service=bool(email_source),
                )
            result = validate_email_otp(session, current_otp, sentinel_header=None, so_header=None)
            return result
        except EmailOtpInvalidError as exc:
            last_exc = exc
            if attempt >= max_otp_attempts:
                break
            logger.warning("[查活] OTP 无效/过期，重新发送后再取：%s", str(exc)[:180])
            send_email_otp(session)
            # 以“重新发送请求完成后”为新基准，避免刚刚失败的上一封旧码再次被 after 容忍窗口命中。
            otp_after_ts = time.time()
            current_otp = None
            time.sleep(1)
        except Exception as exc:
            # 提交 OTP 后的网络抖动（连接断开/超时/代理波动）：同一会话重发验证码再验证一次。
            if attempt >= max_otp_attempts or not _is_retryable_network_error(exc):
                raise
            last_exc = exc
            logger.warning("[查活] OTP 验证网络抖动，重新发送后再取（%s/%s）：%s", attempt, max_otp_attempts, str(exc)[:180])
            try:
                send_email_otp(session)
            except Exception:
                raise
            otp_after_ts = time.time()
            current_otp = None
            time.sleep(1)
    raise last_exc if last_exc else RuntimeError("OTP 验证失败")


def check_account_liveness(
    email: str,
    proxy: str | None = None,
    *,
    clear_log: bool = True,
    proxy_supplier: Callable[[int], str | None] | None = None,
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
        )

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

        follow_oauth_callback(session, str(continue_url), referer="https://auth.openai.com/email-verification")
        session_info = fetch_session(session)
        access_token = str(session_info.get("accessToken") or "")
        if not access_token:
            raise RuntimeError("重新登录后未拿到 accessToken")

        user = session_info.get("user") or {}
        account = session_info.get("account") or {}
        logger.info("[查活] 正常：%s user_id=%s plan=%s", email, user.get("id"), account.get("planType"))
        return {
            "ok": True,
            "status": "live",
            "checked_at": checked_at,
            "access_token": access_token,
            "session": session_info,
            "device_id": session.device_id,
            "proxy_used": session.proxy or None,
            "validation_method": "email_otp",
        }
    except AccountUnusableError as exc:
        code = getattr(exc, "error_code", "") or detect_account_unusable_text(str(exc)) or "account_deactivated"
        logger.warning("[查活] 已废号：%s %s", email, code)
        return {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code}
    except Exception as exc:
        code = detect_account_unusable_text(str(exc))
        if code:
            logger.warning("[查活] 已废号：%s %s", email, code)
            return {"ok": False, "status": "deactivated", "checked_at": checked_at, "error": code}
        logger.warning("[查活] 失败：%s %s: %s", email, type(exc).__name__, str(exc)[:260])
        return {"ok": False, "status": "failed", "checked_at": checked_at, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
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
