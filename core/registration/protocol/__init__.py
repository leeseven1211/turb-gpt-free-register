"""纯协议注册流程。

该模块承接原先位于 `main.py` 的 HTTP/curl_cffi 注册主体。驱动选择不在这里处理，
由 `core.registration.dispatcher` 统一完成。
"""
from __future__ import annotations

import json
import logging
import re
import time
from contextlib import nullcontext
from urllib.parse import urlparse

from config import email as _email_cfg
from config import codex as _codex_cfg
from config import openai_protocol as _protocol_cfg
from config import twofa as _twofa_cfg
from core.accounts.export import fetch_session, follow_oauth_callback, setup_2fa_protocol
from core.auth.protocol.chatgpt_auth import get_csrf_token, get_providers, probe_auth_session, signin_openai
from core.email.provider import resolve_email_source, validate_email_source, wait_for_otp
from core.email.forward_imap import ForwardIMAPNoMailTimeout
from core.auth.humanize import delay as human_delay
from core.auth.protocol.openai_auth import AccountUnusableError, EmailOtpInvalidError, build_sentinel_header, create_account, follow_authorize, generate_registration_password, navigate_create_account_password, navigate_email_otp_send, navigate_about_you, network_preflight, register_user, request_password_sentinel_bundle, request_sentinel_token, send_email_otp, validate_email_otp
from core.registration.profile_utils import generate_random_birthday
from core.auth.protocol.session import BrowserSession
from core.auth.challenge import AuthCancelledError, auth_result_for_registration
from core.auth.state_machine import PageState, StageBudget, StageTimeout, classify_page

logger = logging.getLogger(__name__)

_FINALIZE_SESSION_MAX_ATTEMPTS = 5


def _classify_registration_continuation(page_type: str, continue_url: str | None) -> str:
    """Classify the remote account state before choosing create-account."""
    normalized_type = str(page_type or "").strip().lower()
    normalized_url = str(continue_url or "").strip().lower()
    if normalized_type in {
        "login_password",
        "password_login",
        "log_in_password",
        "password_login_required",
    } or "/log-in/password" in normalized_url:
        return "existing"
    if normalized_type == "external_url" or (
        normalized_url
        and "about-you" not in normalized_url
        and (
            "chatgpt.com/api/auth/callback" in normalized_url
            or "auth.openai.com/authorize/continue" in normalized_url
        )
    ):
        return "existing"
    if normalized_type in {"about_you", "about-you"} or "about-you" in normalized_url:
        return "new_candidate"
    return "unknown"


_FINALIZE_SESSION_BACKOFF_BASE = 2.0


def _protocol_registration_cause_code(
    exc: BaseException,
    error_text: str,
    *,
    register_accepted: bool,
    checkpoint_account_id: int | None,
    otp_send_in_flight: bool,
) -> str:
    """只用固定原因码描述失败，不把服务端正文或凭据写入任务结果。"""
    if not register_accepted:
        return (
            "user_register_result_unknown"
            if error_text.startswith("user/register 请求结果未知")
            else "registration_failed"
        )
    if checkpoint_account_id is None:
        return "registration_checkpoint_failed"
    if error_text.startswith("user/register 响应缺少 continue_url"):
        return "user_register_continue_url_missing"
    for marker in (
        "email_otp_send_rejected",
        "email_otp_send_failed",
        "email_otp_send_unconfirmed",
    ):
        if error_text.startswith(marker):
            return marker
    if otp_send_in_flight:
        return "email_otp_send_no_response" if isinstance(exc, TimeoutError) else "email_otp_send_unknown"
    if isinstance(exc, ForwardIMAPNoMailTimeout):
        return "email_otp_no_mail"
    return "post_register_failure"


def _safe_protocol_registration_error(exc: BaseException, cause_code: str) -> str:
    """仅保留固定阶段、异常类型和 HTTP 状态，不复制远端正文。"""
    from core.operations.errors import safe_registration_diagnostics

    diagnostics = safe_registration_diagnostics(getattr(exc, "registration_diagnostics", None))
    descriptions = {
        "account_create_invalid_state": "资料提交时认证会话已失效",
        "account_create_user_already_exists": "远端提示账号已存在，完整登录态尚未确认",
        "user_register_result_unknown": "账号创建请求结果待确认，未保留失败细项",
        "registration_checkpoint_failed": "注册检查点本地写入失败",
        "user_register_continue_url_missing": "账号创建响应缺少后续验证地址",
        "email_otp_send_rejected": "验证码发送请求被拒绝",
        "email_otp_send_failed": "验证码发送请求失败",
        "email_otp_send_unconfirmed": "验证码发送结果未确认",
        "email_otp_send_no_response": "验证码发送请求未收到响应",
        "email_otp_send_unknown": "验证码发送结果待确认",
        "email_otp_no_mail": "等待窗口内未收到验证码邮件",
        "post_register_failure": "注册请求之后流程失败",
        "registration_failed": "注册流程失败",
        "protocol_preauth_transport_failed": "协议认证前置请求发生传输错误",
        "protocol_post_otp_transport_failed": "已取得邮箱验证码，后续认证请求发生传输错误",
        "protocol_auth_transport_failed": "协议认证请求发生传输错误",
        "protocol_auth_rejected_before_password": "密码尚未确认时认证请求被拒绝",
        "protocol_auth_http_failed": "协议认证请求返回 HTTP 错误",
        "protocol_session_incomplete": "注册资料已确认，后续登录态尚未取得",
        "protocol_failure_evidence_missing": "协议失败未保留足够请求证据，无法确认具体原因",
    }
    type_name = diagnostics.get("exception_type", "Exception") if diagnostics else type(exc).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", type_name):
        type_name = "Exception"
    response = getattr(exc, "response", None)
    status = diagnostics.get("http_status")
    for value in (
        getattr(response, "status_code", None),
        getattr(exc, "status_code", None),
        getattr(exc, "http_status", None),
    ):
        if diagnostics:
            break
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            continue
        if 100 <= candidate <= 599:
            status = candidate
            break
    if status is None and not diagnostics and not cause_code.startswith("protocol_") and cause_code != "user_register_result_unknown":
        match = re.search(r"\b(?:HTTP(?:\s+Error)?\s*:?|status\s*[=:])\s*(\d{3})\b", str(exc), re.IGNORECASE)
        if match:
            candidate = int(match.group(1))
            if 100 <= candidate <= 599:
                status = candidate
    suffix = f" HTTP {status}" if status is not None else ""
    if diagnostics:
        suffix += " 诊断=" + json.dumps(diagnostics, ensure_ascii=False, separators=(",", ":"))
    if cause_code in {"account_create_invalid_state", "account_create_user_already_exists"} or (
        cause_code.startswith("protocol_") and cause_code in descriptions
    ):
        return f"{cause_code}: {descriptions[cause_code]}：{type_name}{suffix}"
    return f"{descriptions.get(cause_code, '注册流程失败')}：{type_name}{suffix}"


def _protocol_password_continue_url(register_result: object) -> str:
    """从 user/register 响应中提取并校验邮箱 OTP 发送地址。"""
    if not isinstance(register_result, dict):
        raise RuntimeError("user/register 响应缺少 continue_url，无法发送邮箱验证码")

    page = register_result.get("page")
    page = page if isinstance(page, dict) else {}
    continue_url = (
        register_result.get("continue_url")
        or register_result.get("url")
        or page.get("continue_url")
        or page.get("url")
    )
    normalized = str(continue_url or "").strip()
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/").lower()
    if host and host != "auth.openai.com":
        raise RuntimeError("user/register 响应缺少 continue_url，无法发送邮箱验证码")
    if path != "/api/accounts/email-otp/send":
        raise RuntimeError("user/register 响应缺少 continue_url，无法发送邮箱验证码")
    return normalized


def _run_protocol_password_stage(
    session: BrowserSession,
    email: str,
    *,
    referer: str = "https://auth.openai.com/email-verification",
    password: str | None = None,
    on_password_prepared=None,
    on_password_started=None,
    on_password_submitted=None,
    on_otp_send_started=None,
) -> dict:
    """提交 Protocol 密码并进入邮箱验证码页面。"""
    password = password or generate_registration_password()
    if on_password_prepared is not None:
        on_password_prepared(password)
    # passwordless/send-otp 只属于无密码登录/注册页的首封验证码加载器。
    # 密码注册页的邮箱验证码由 user/register 成功后返回的
    # /api/accounts/email-otp/send 导航触发；提前调用会把密码注册会话打成
    # 无效状态，并得到无正文的 HTTP 500。
    navigate_create_account_password(session, referer=referer)
    sentinel_response = request_password_sentinel_bundle(session)
    sentinel_header, so_header = build_sentinel_header(
        session,
        sentinel_response,
        "username_password_create",
    )
    human_delay("challenge")
    if on_password_started is not None:
        on_password_started(password)
    try:
        register_result = register_user(
            session,
            email,
            password,
            sentinel_header,
            so_header,
        )
    except AuthCancelledError:
        raise
    except Exception as exc:
        response = getattr(exc, "response", None)
        try:
            status_code = int(getattr(response, "status_code", 0) or 0)
        except (TypeError, ValueError):
            status_code = 0
        if status_code == 0 or status_code >= 500:
            # 异常正文可能包含响应内容或凭据；只保留类型与状态码。
            raise RuntimeError(
                f"user/register 请求结果未知: {type(exc).__name__[:80]} http_status={status_code or '-'}"
            ) from None
        raise
    # user/register 成功即代表远端已接受密码并创建可继续验证的邮箱身份。
    # 在读取响应页形态、发送 OTP 前保存检查点，避免后续导航中断后丢失续跑凭据。
    if on_password_submitted is not None:
        on_password_submitted(password)
    continue_url = _protocol_password_continue_url(register_result)
    otp_requested_at = time.time()
    otp_url = navigate_email_otp_send(
        session,
        continue_url,
        on_request_started=on_otp_send_started,
    )
    return {
        "password": password,
        "register_result": register_result,
        "continue_url": continue_url,
        "otp_url": otp_url,
        "otp_sent_at": otp_requested_at,
    }


def _maybe_run_protocol_password_stage(
    session: BrowserSession,
    email: str,
    *,
    password_enabled: bool,
    referer: str = "https://auth.openai.com/email-verification",
    password: str | None = None,
    on_password_prepared=None,
    on_password_started=None,
    on_password_submitted=None,
    on_otp_send_started=None,
) -> dict | None:
    """按任务快照决定是否进入密码注册阶段。"""
    if not password_enabled:
        return None
    return _run_protocol_password_stage(
        session,
        email,
        referer=referer,
        password=password,
        on_password_prepared=on_password_prepared,
        on_password_started=on_password_started,
        on_password_submitted=on_password_submitted,
        on_otp_send_started=on_otp_send_started,
    )


def _run_protocol_existing_password_stage(
    session: BrowserSession,
    email: str,
    password: str,
) -> dict:
    """用同一协议会话验证已保存密码，继续进入邮箱验证页。"""
    from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError, _password_verify

    try:
        result = _password_verify(session, password)
    except AuthCancelledError:
        raise
    except ProtocolV2AuthError as exc:
        if exc.code == "password_result_unknown":
            raise RuntimeError(f"密码验证请求结果未知: {exc.code}") from exc
        raise RuntimeError(f"协议续跑密码验证失败: {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(
            f"密码验证请求结果未知: {type(exc).__name__}"
        ) from None

    if not isinstance(result, dict):
        raise RuntimeError("协议续跑密码验证响应未知，无法继续邮箱验证")
    page = result.get("page") if isinstance(result.get("page"), dict) else {}
    continue_url = str(
        result.get("continue_url")
        or result.get("external_url")
        or result.get("url")
        or page.get("continue_url")
        or page.get("external_url")
        or page.get("url")
        or ""
    ).lower()
    page_type = str(page.get("type") or "").lower()
    from core.accounts.liveness.protocol.v2 import _is_mfa
    continuation = _classify_registration_continuation(page_type, continue_url)
    if ("email-verification" not in continue_url and "email_otp" not in page_type
            and urlparse(continue_url).path.rstrip("/") != "/api/accounts/email-otp/send"
            and not _is_mfa(result, continue_url) and continuation not in {"existing", "new_candidate"}):
        raise RuntimeError("协议续跑密码验证后页面未知，已停止继续注册")
    return result


def _protocol_resume_requires_password(final_url: object) -> bool:
    """判断待验证账号续跑是否真的落在登录密码页。"""
    parsed = urlparse(str(final_url or ""))
    return parsed.path.rstrip("/").lower() == "/log-in/password"


def _protocol_resume_otp_continue_url(result: object) -> str | None:
    """读取密码验证返回的下一步；验证码页本身不需要再次发码。"""
    if not isinstance(result, dict):
        return None
    page = result.get("page") if isinstance(result.get("page"), dict) else {}
    values = (
        result.get("continue_url"), result.get("external_url"), result.get("url"),
        page.get("continue_url"), page.get("external_url"), page.get("url"),
    )
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        parsed = urlparse(raw)
        path = parsed.path.rstrip("/").lower()
        if path == "/email-verification":
            return None
        if path == "/api/accounts/email-otp/send":
            return raw
    page_type = str(page.get("type") or "").strip().lower()
    if "email_otp" in page_type or "email-verification" in page_type:
        return None
    return ""


def _send_protocol_resume_email_otp(
    session: BrowserSession,
    *,
    after_ts: float,
    auth_final_url: str,
    continue_url: str | None = None,
    otp_page_ready: bool = False,
) -> float:
    """沿服务端当前状态续跑验证码，避免重复发送已进入验证码页的会话。"""
    final_path = urlparse(str(auth_final_url or "")).path.rstrip("/").lower()
    if otp_page_ready or (final_path == "/email-verification" and continue_url is None):
        logger.info("[OTP] 续跑认证已进入邮箱验证码页，保留当前会话，不重复请求发码")
        return after_ts
    if continue_url == "":
        raise RuntimeError("续跑密码验证后未确认邮箱验证码页")
    if continue_url is None:
        raise RuntimeError("续跑认证页面未提供邮箱验证码继续地址")
    try:
        navigate_email_otp_send(
            session,
            continue_url=continue_url,
            referer="https://auth.openai.com/email-verification",
        )
    except (AuthCancelledError, StageTimeout):
        raise
    except Exception as exc:
        raise RuntimeError(
            f"续跑邮箱验证码发送未确认: {type(exc).__name__}"
        ) from exc
    return time.time()


def _wait_for_otp_with_resend(
    session: BrowserSession,
    email: str,
    *,
    after_ts: float,
    email_source: str | None = "icloud_hide",
    budget: StageBudget | None = None,
) -> str:
    """仅在 IMAP 正常但没有新邮件时，于原等待预算内重发一次。"""
    total_wait = max(1, int(_email_cfg.OTP_MAX_WAIT))
    first_wait = min(120, total_wait // 2)
    shared_budget = budget or StageBudget.start(total_wait)
    total_wait = min(total_wait, shared_budget.require("邮箱验证码"))
    first_wait = min(first_wait, total_wait)
    kwargs = {"after_ts": after_ts, "email_source": email_source}
    if budget is not None:
        kwargs["budget"] = budget
    if first_wait < 30 or total_wait - first_wait < 30:
        return wait_for_otp(email, max_wait=total_wait, **kwargs)

    try:
        return wait_for_otp(email, max_wait=first_wait, **kwargs)
    except ForwardIMAPNoMailTimeout:
        remaining = min(total_wait - first_wait, shared_budget.require("邮箱验证码重发"))
        if remaining < 30:
            raise
        logger.warning(
            "[OTP] Gmail IMAP 正常轮询但未收到新验证码，将在同一账号会话中重发一次：%s",
            email,
        )
        resend_after_ts = time.time()
        with session.request_budget(shared_budget) if budget is not None else nullcontext():
            send_email_otp(session)
        return wait_for_otp(
            email,
            after_ts=resend_after_ts,
            email_source=email_source,
            max_wait=remaining,
            **({"budget": budget} if budget is not None else {}),
        )


def _wait_for_resume_otp_with_resend(
    session: BrowserSession,
    email: str,
    *,
    after_ts: float,
    email_source: str | None = "icloud_hide",
    budget: StageBudget | None = None,
) -> str:
    """兼容旧测试与调用方，统一使用验证码页的一次受控重发。"""
    return _wait_for_otp_with_resend(
        session,
        email,
        after_ts=after_ts,
        email_source=email_source,
        **({"budget": budget} if budget is not None else {}),
    )


def _complete_protocol_resume_mfa(
    session: BrowserSession,
    mfa_result: dict,
    continue_url: str,
    totp_secret: str,
    *,
    budget: StageBudget | None = None,
) -> tuple[dict, str]:
    """完成待验证账号的 TOTP 挑战，并返回已建立的 ChatGPT 会话。"""
    from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError, _complete_mfa

    secret = str(totp_secret or "").strip()
    if not secret:
        raise RuntimeError("协议续跑 TOTP 验证需要已保存的密钥")
    try:
        with session.request_budget(budget) if budget is not None else nullcontext():
            session_info, _auth_method = _complete_mfa(
                session,
                mfa_result,
                continue_url,
                secret,
            )
    except ProtocolV2AuthError as exc:
        cause = exc.__cause__
        while cause is not None:
            if isinstance(cause, (AuthCancelledError, StageTimeout)):
                raise cause
            cause = cause.__cause__
        if str(getattr(exc, "category", "") or "") == "network":
            raise RuntimeError(
                f"协议续跑 TOTP 验证请求结果未知: {exc.code}"
            ) from exc
        raise RuntimeError(f"协议续跑 TOTP 验证失败: {exc.code}") from exc

    if not isinstance(session_info, dict):
        raise RuntimeError("协议续跑 TOTP 验证响应未知")
    access_token = str(session_info.get("accessToken") or "").strip()
    if not access_token:
        raise RuntimeError("协议续跑 TOTP 验证后 session 响应缺少 accessToken")
    if budget is not None:
        budget.require("TOTP 认证")
    return session_info, access_token


def _protocol_terminal_state(value: object) -> PageState | None:
    """Map callback/session errors to terminal states instead of polling blindly."""
    response = getattr(value, "response", None)
    if response is not None:
        response_url = str(getattr(response, "url", "") or "").lower()
        response_text = str(getattr(response, "text", "") or "").lower()
        try:
            status = int(getattr(response, "status_code", 0) or 0)
        except (TypeError, ValueError):
            status = 0
        if "callback" in response_url and status in (400, 401, 403, 422):
            return PageState.AUTH_ERROR
        if any(marker in response_text for marker in ("oauth callback error", "invalid_grant", "session has ended")):
            return PageState.AUTH_ERROR
    if isinstance(value, dict):
        error_text = " ".join(str(value.get(key) or "") for key in ("error", "error_code", "message", "detail", "url"))
        if any(marker in error_text.lower() for marker in (
            "oauthcallback", "oauth callback error", "callback error", "session has ended",
            "logged out", "unauthorized", "invalid_grant",
        )):
            state = classify_page({"url": value.get("url"), "text": error_text})
            return state if state in (PageState.AUTH_ERROR, PageState.LOGGED_OUT) else PageState.AUTH_ERROR
        return classify_page(value)
    text = str(value or "")
    if not text:
        return None
    state = classify_page({"url": getattr(value, "url", "") or (text if text.startswith("http") else ""), "text": text})
    return state if state in (PageState.AUTH_ERROR, PageState.LOGGED_OUT) else None


def _finalize_registration_session(
    session: BrowserSession,
    continue_url: str,
    email: str,
    callback_referer: str = "https://auth.openai.com/about-you",
    *,
    total_timeout: float = 90.0,
    budget: StageBudget | None = None,
) -> tuple[dict, str]:
    """共用阶段预算；回调成功后仅重试读取同一会话。"""
    if not continue_url:
        raise RuntimeError("create_account 响应缺少 continue_url，无法完成 OAuth 回调")

    budget = budget or StageBudget.start(total_timeout)
    last_exc: Exception | None = None
    callback_completed = False
    for attempt in range(1, _FINALIZE_SESSION_MAX_ATTEMPTS + 1):
        budget.require("OAuth callback/session")
        try:
            logger.info(
                f"[登录态] 完成 OAuth 回调并拉取 Token：{email} "
                f"(尝试 {attempt}/{_FINALIZE_SESSION_MAX_ATTEMPTS})"
            )
            if not callback_completed:
                callback_url = follow_oauth_callback(
                    session, continue_url, referer=callback_referer,
                    timeout=budget.require("OAuth 回调"),
                )
                terminal = _protocol_terminal_state(callback_url)
                if terminal in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
                    raise RuntimeError(f"OAuth callback reached terminal state: {terminal.value}")
                callback_completed = True
                human_delay("post_auth", budget=budget)
            session_info = fetch_session(session, timeout=budget.require("ChatGPT session"))
            budget.require("ChatGPT session")
            terminal = _protocol_terminal_state(session_info)
            if terminal in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
                raise RuntimeError(f"ChatGPT session reached terminal state: {terminal.value}")
            access_token = session_info.get("accessToken")
            if not access_token:
                raise RuntimeError("session 响应缺少 accessToken")
            logger.info(f"[登录态] 已拿到 accessToken：{email}")
            return session_info, access_token
        except (AuthCancelledError, StageTimeout):
            raise
        except Exception as exc:
            last_exc = exc
            terminal = _protocol_terminal_state(exc)
            if terminal in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
                raise RuntimeError(
                    f"OAuth callback/session entered terminal state {terminal.value}: {str(exc)[:240]}"
                ) from exc
            if not callback_completed:
                response = getattr(exc, "response", None)
                status = int(getattr(response, "status_code", 0) or 0)
                # 只有明确限流拒绝才重试未完成回调；5xx 或响应丢失
                # 都不能证明一次性授权码未被消费。
                if status != 429:
                    raise RuntimeError("OAuth 回调请求结果未知，保留原注册意图等待恢复") from exc
            if attempt >= _FINALIZE_SESSION_MAX_ATTEMPTS:
                break
            backoff = _FINALIZE_SESSION_BACKOFF_BASE ** (attempt - 1)
            remaining = budget.remaining()
            if remaining <= 0:
                break
            logger.warning(
                f"[登录态] 回调或拉取 Token 失败：{email}，"
                f"{type(exc).__name__}: {str(exc)[:180]}，{backoff:.1f}s 后重试"
            )
            budget.sleep(min(backoff, remaining))

    if budget.expired():
        raise StageTimeout(
            f"OAuth callback/session exceeded shared stage timeout {int(total_timeout)} seconds"
        ) from last_exc
    raise RuntimeError(
        f"OAuth 回调/拉取 Token 重试耗尽：{email}，"
        f"最后错误：{type(last_exc).__name__ if last_exc else 'Unknown'}: {last_exc}"
    ) from last_exc


def run_protocol_registration(
    email: str,
    name: str,
    birthday: str | None = None,
    proxy: str | None = None,
    otp_code: str | None = None,
    registration_options: dict | None = None,
    email_source: str | None = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
) -> dict:
    """执行完整的纯协议 ChatGPT 注册流程。"""
    if not str(proxy or "").strip():
        raise RuntimeError(
            "Protocol 注册必须使用统一代理池已领取线路，禁止无代理或直连"
        )
    from core.registration.service import StopRequested, check_stop_requested, report_job_progress, report_registered_account

    def _cancelled() -> bool:
        try:
            check_stop_requested()
        except StopRequested:
            return True
        return False

    selected_email_source = validate_email_source(email_source) if email_source else None
    options = dict(registration_options or {})
    existing_password = str(existing_password or "").strip() or None
    existing_totp_secret = str(existing_totp_secret or "").strip() or None
    password_required = bool(options.get("password_enabled", False) or existing_password)
    twofa_enabled = bool(options.get("twofa_enabled", _twofa_cfg.ENABLE_2FA))
    # ``dict.get`` evaluates its default argument eagerly.  Read the live
    # config only for legacy callers that did not provide a job snapshot.
    codex_enabled = (
        bool(options["codex_enabled"])
        if "codex_enabled" in options
        else bool(getattr(_codex_cfg, "ENABLE_CODEX_AUTO", False))
    )
    plan_check_enabled = bool(options.get("plan_check_enabled", True))

    report_job_progress("browser", "running", "正在初始化协议注册会话")
    session = BrowserSession(proxy=proxy)
    report_job_progress("browser", "success", "协议注册会话已初始化")

    # 从代理 URL 中抽取 sid 段做日志，避免把账号密码完整打印。
    proxy_label = "无"
    if session.proxy:
        try:
            sid_part = next(
                (seg for seg in session.proxy.split("@")[0].split("-") if len(seg) == 8),
                "***",
            )
            proxy_label = f"{session.proxy.split('://')[0]}://...sid-{sid_part}...@{session.proxy.split('@')[-1]}"
        except Exception:
            proxy_label = "已配置"

    if not birthday:
        birthday = generate_random_birthday()

    logger.info(f"[注册] 开始：{email}，代理={proxy_label}")
    logger.info(f"[注册] 本次随机生日: {birthday}")
    logger.debug("[注册] 设备/会话标识已生成（原值不写日志）")

    create_acknowledged = False
    password_register_accepted = False
    otp_send_in_flight = False
    remote_identity = "unknown"
    auth_challenge_chain: list[str] = []
    account_id: int | None = None
    openai_password: str | None = None
    password_request_started = False
    core_persisted = False
    bootstrap_error = None
    direct_result = None
    password_validated = bool(existing_password)
    try:
        if existing_password:
            from core.registration.service import registration_fact_context
            from core.storage import registration
            facts = registration_fact_context()
            if facts.get("attempt_id") is not None:
                private = registration.get_private_resume_context(int(facts["attempt_id"]), email=email)
                if private.get("password"):
                    if private["password"] != existing_password:
                        raise RuntimeError("原 Attempt 的恢复密码不一致，已停止")
                    password_validated = private.get("password_state") == "confirmed"
        report_job_progress("page", "running", "正在初始化 ChatGPT 注册页状态")
        # 网络预检必须在 signin/follow_authorize 之前完成；预检不带邮箱，不会触发 OTP。
        # Roxy 的成功链路不会先请求无参数 Auth authorize；该探针在部分
        # 代理上会被 403 拒绝，而带真实 state 的 authorize 才是有效判定。
        network_preflight(session, include_auth_probe=False)
        human_delay("navigate")

        # 根据 HAR 补齐匿名态 ChatGPT 首屏/模型预热链路。
        if getattr(_protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", True):
            from core.auth.protocol.chatgpt_bootstrap import anonymous_bootstrap

            anonymous_bootstrap(
                session,
                strict=bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)),
            )
            human_delay("navigate")

        # ==================== 阶段1: ChatGPT 认证 ====================
        get_providers(session)
        human_delay("api")

        # Auth Web 在邮箱提交前会读取一次匿名 NextAuth session；这一步会
        # 固定当前匿名登录上下文，缺失时 passwordless/send-otp 可能只返回
        # 无正文的 500，而不是可诊断的业务错误。
        probe_auth_session(session)
        human_delay("api")

        csrf_token = get_csrf_token(session)
        human_delay("api")
        report_job_progress("page", "success", "注册页状态已初始化")

        report_job_progress("submit_email", "running", "正在提交邮箱")
        authorize_url = signin_openai(session, csrf_token, email)
        report_job_progress("submit_email", "success", "邮箱已提交")
        report_job_progress("auth_redirect", "running", "正在跟随 OpenAI 认证跳转")
        human_delay("api")

        # 只读取本次 OTP 触发之后的邮件，避免命中旧验证码。
        otp_after_ts = time.time()

        # ==================== 阶段2: OpenAI Auth ====================
        auth_final_url = follow_authorize(session, authorize_url)
        human_delay("navigate")
        report_job_progress("auth_redirect", "success", "已进入 OpenAI 认证下一步")

        # 密码模式必须先完成 user/register 和邮箱验证码发送；否则仅记录
        # password challenge 并不会在远端创建可继续验证的邮箱身份。
        reuse_for_registration = bool(existing_password and
            urlparse(str(auth_final_url)).path.rstrip("/").lower() == "/create-account/password")
        if not existing_password and _protocol_resume_requires_password(auth_final_url):
            remote_identity = "existing"
            raise RuntimeError("已有账号密码页缺少原密码，已停止新注册")
        if not existing_password:
            from core.accounts.liveness.protocol.v2 import _is_mfa
            if _is_mfa({}, str(auth_final_url or "")):
                remote_identity = "existing"
                raise RuntimeError("已有账号 MFA 页面缺少原恢复凭据，已停止新注册")
        if existing_password and not reuse_for_registration:
            report_job_progress("resume_auth", "running", "正在用原身份继续协议认证")
            # 待邮箱验证检查点的 authorize 会话已经直接落在邮箱验证页。
            # 这里的密码此前已成功提交，重复 POST password/verify 会把
            # 已建立的邮箱验证状态打成 HTTP 400；只有真正落到登录密码页
            # 时才需要再次提交已保存密码。
            password_result = None
            if _protocol_resume_requires_password(auth_final_url):
                report_job_progress("login_password", "running", "正在验证已保存的原密码")
                password_result = _run_protocol_existing_password_stage(
                    session,
                    email,
                    existing_password,
                )
                password_validated = True
            # Roxy 保留已经到达的验证码页面；Protocol 也只沿服务端返回的
            # continue_url 触发发码，禁止用固定地址重复请求已建立的 OTP 会话。
            if password_result is None and not _protocol_resume_requires_password(auth_final_url):
                password_result = {"continue_url": auth_final_url}
            otp_continue_url = _protocol_resume_otp_continue_url(password_result)
            if otp_continue_url == "":
                direct_result = password_result
            else:
                otp_after_ts = _send_protocol_resume_email_otp(
                    session, after_ts=otp_after_ts, auth_final_url=auth_final_url,
                    continue_url=otp_continue_url,
                    otp_page_ready=password_result is not None and otp_continue_url is None,
                )
            openai_password = existing_password
            auth_challenge_chain.append("password")
            if _protocol_resume_requires_password(auth_final_url):
                report_job_progress("login_password", "success", "本次密码验证已确认，继续服务端认证状态")
            else:
                report_job_progress("resume_auth", "success", "已复用原身份继续服务端认证状态")
        elif password_required:
            report_job_progress("credential_prepare", "running", "正在保存原密码并准备注册请求")

        def _checkpoint_submitted_password(password: str) -> None:
            nonlocal account_id, create_acknowledged, password_register_accepted, password_validated
            if account_id is not None:
                report_job_progress("credential_prepare", "success", "注册请求已确认，复用已有账号检查点")
                return
            # 此回调只在 user/register 已返回成功响应后调用；即使本地检查点
            # 写入失败，也不能把远端身份误标为尚未开始。
            password_register_accepted = True
            password_validated = True
            create_acknowledged = True
            from core.registration.checkpoints import save_protocol_password_checkpoint

            saved = save_protocol_password_checkpoint(
                email=email,
                password=password,
                state="confirmed",
                proxy=session.proxy or None,
                email_source=selected_email_source,
            )
            account_id = int(saved["account_id"])
            report_registered_account(account_id)
            report_job_progress("credential_prepare", "success", "注册请求已确认，密码检查点已保存")

        def _checkpoint_password(password: str, state: str) -> None:
            nonlocal openai_password, password_request_started
            from core.registration.checkpoints import save_protocol_password_checkpoint
            check_stop_requested()
            save_protocol_password_checkpoint(email=email, password=password, state=state)
            openai_password = password
            if state == "started":
                password_request_started = True

        def _mark_otp_send_started() -> None:
            nonlocal otp_send_in_flight
            otp_send_in_flight = True

        password_stage = None if existing_password and not reuse_for_registration else _maybe_run_protocol_password_stage(
            session,
            email,
            password_enabled=password_required,
            referer=auth_final_url,
            password=existing_password if reuse_for_registration else None,
            on_password_prepared=lambda password: _checkpoint_password(password, "prepared"),
            on_password_started=lambda password: _checkpoint_password(password, "started"),
            on_password_submitted=_checkpoint_submitted_password,
            on_otp_send_started=_mark_otp_send_started,
        )
        if password_stage is not None:
            otp_send_in_flight = False
            openai_password = password_stage["password"]
            password_validated = True
            # 以发送导航发起前的时间作为边界，只接收本次请求之后的新邮件。
            otp_after_ts = float(password_stage.get("otp_sent_at") or time.time())
            auth_challenge_chain.append("password")
            report_job_progress("login_password", "success", "账号密码已提交并进入邮箱验证码页")

        validate_result = direct_result
        if direct_result is None:
            otp_budget = StageBudget.start(_email_cfg.OTP_MAX_WAIT, cancel=_cancelled)
            # ==================== 阶段3: 验证码验证 ====================
            report_job_progress("email_otp", "running", "正在等待并验证邮箱验证码")
            validate_result = None
            max_otp_attempts = 3
            current_otp = otp_code
            with (session.request_budget(otp_budget) if callable(getattr(session, "request_budget", None)) else nullcontext()):
                for otp_attempt in range(1, max_otp_attempts + 1):
                    if current_otp is None:
                        if _email_cfg.USE_EMAIL_SERVICE:
                            logger.info(f"[OTP] 等待验证码：{email}（第 {otp_attempt}/{max_otp_attempts} 次）")
                            otp_kwargs = {"after_ts": otp_after_ts, "budget": otp_budget}
                            if selected_email_source is not None:
                                otp_kwargs["email_source"] = selected_email_source
                            if (
                                otp_attempt == 1
                                and (selected_email_source or resolve_email_source(email)) == "icloud_hide"
                                and str(_email_cfg.ICLOUD_HME_INBOX_MODE).strip().lower() == "forward_imap"
                            ):
                                current_otp = _wait_for_otp_with_resend(
                                    session,
                                    email,
                                    after_ts=otp_after_ts,
                                    email_source=selected_email_source,
                                    budget=otp_budget,
                                )
                            else:
                                current_otp = wait_for_otp(email, **otp_kwargs)
                        else:
                            logger.info("")
                            logger.info(f"[OTP] 请检查邮箱，输入收到的 6 位验证码（第 {otp_attempt}/{max_otp_attempts} 次）:")
                            current_otp = wait_for_otp(email, force_service=False, budget=otp_budget,
                                after_ts=otp_after_ts, email_source=selected_email_source)

                    human_delay("otp_input", budget=otp_budget)
                    try:
                        sentinel_header_9 = None
                        so_header_9 = None
                        if getattr(_protocol_cfg, "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", False):
                            sentinel_resp_9 = request_sentinel_token(session, "authorize_continue")
                            sentinel_header_9, so_header_9 = build_sentinel_header(
                                session, sentinel_resp_9, "authorize_continue"
                            )
                            human_delay("challenge", budget=otp_budget)

                        validate_result = validate_email_otp(session, current_otp, sentinel_header_9, so_header_9)
                        break
                    except EmailOtpInvalidError as exc:
                        if otp_attempt >= max_otp_attempts:
                            raise
                        logger.warning(f"[OTP] 验证码错误/过期：{str(exc)[:180]}，准备重新发送并重新获取验证码")
                        otp_after_ts = time.time()
                        send_email_otp(session)
                        human_delay("api", budget=otp_budget)
                        current_otp = None

            if validate_result is None:
                raise RuntimeError("OTP 验证未完成")
            report_job_progress("email_otp", "success", "邮箱验证码已通过")
            auth_challenge_chain.append("email_otp")
            human_delay("api")

        # OTP 校验后的下一步由服务端 auth session 决定。
        page = validate_result.get("page") if isinstance(validate_result, dict) else {}
        page = page if isinstance(page, dict) else {}
        page_type = str(page.get("type") or "")
        otp_continue_url = (
            validate_result.get("continue_url")
            or validate_result.get("external_url")
            or validate_result.get("url")
            or page.get("continue_url")
            or page.get("external_url")
            or page.get("url")
        )
        logger.info(
            f"[步骤10] 后续分支判断: page_type={page_type or '空'}, "
            f"has_continue_url={bool(otp_continue_url)}"
        )

        # ==================== 阶段5/6: 完成注册或直接 OAuth 回调 ====================
        otp_continue_text = str(otp_continue_url or "")
        from core.accounts.liveness.protocol.v2 import _is_mfa

        resume_mfa_required = bool(
            existing_password and _is_mfa(validate_result, otp_continue_text)
        )
        if resume_mfa_required:
            remote_identity = "existing"
            continuation_identity = "existing"
            report_job_progress("profile", "skipped", "已有账号状态，正在完成 TOTP 验证")
            report_job_progress("token", "running", "正在完成 TOTP 验证并获取 Token")
            session_info, access_token = _complete_protocol_resume_mfa(
                session,
                validate_result,
                otp_continue_text,
                existing_totp_secret or "",
                budget=StageBudget.start(90, cancel=_cancelled),
            )
            create_acknowledged = True
            auth_challenge_chain.append("totp")
            report_job_progress("token", "success", "已获取 accessToken")
        else:
            continuation_identity = _classify_registration_continuation(page_type, otp_continue_text)
        if not resume_mfa_required and continuation_identity == "existing":
            if page_type in {
                "login_password",
                "password_login",
                "log_in_password",
                "password_login_required",
            } or "/log-in/password" in otp_continue_text.lower():
                remote_identity = "existing"
                raise RuntimeError(
                    "邮箱验证码后进入已有账号密码页；本地未保存该账号密码，已停止新注册并要求人工协调"
                )
            remote_identity = "existing"
            report_job_progress("profile", "skipped", "已有账号状态，无需填写资料")
            if not otp_continue_url:
                raise RuntimeError("OTP external_url 响应缺少可跟随 URL，无法继续")
            logger.info(f"[注册] OTP 后进入 OAuth 回调分支，跳过 create_account：{email}")
            create_acknowledged = True
            report_job_progress("token", "running", "正在完成 OAuth 回调并获取 Token")
            session_info, access_token = _finalize_registration_session(
                session,
                otp_continue_url,
                email,
                callback_referer="https://auth.openai.com/email-verification",
                budget=StageBudget.start(90, cancel=_cancelled),
            )
            report_job_progress("token", "success", "已获取 accessToken")
        elif not resume_mfa_required and continuation_identity == "new_candidate":
            remote_identity = "new_candidate"
            report_job_progress("profile", "running", "正在填写账号资料")
            about_url = str(otp_continue_url) if otp_continue_url and "about-you" in str(otp_continue_url) else None
            navigate_about_you(session, about_url)
            human_delay("navigate")

            sentinel_resp_11 = request_sentinel_token(session, "oauth_create_account")
            sentinel_header_11, so_header_11 = build_sentinel_header(
                session, sentinel_resp_11, "oauth_create_account"
            )
            human_delay("challenge")
            human_delay("form")

            create_result = create_account(session, name, birthday, sentinel_header_11, so_header_11)
            create_acknowledged = True
            report_job_progress("profile", "success", "账号资料已提交")

            logger.info(f"[注册] 创建接口已通过：{email}，继续完成 OAuth 回调")
            human_delay("post_auth")
        elif not resume_mfa_required:
            remote_identity = "unknown"
            raise RuntimeError(
                "OTP 后续页面类型未知，不应盲目 create_account"
            )

        if continuation_identity == "new_candidate":
            continue_url = create_result.get("continue_url")
            if not continue_url:
                raise RuntimeError("create_account 响应缺少 continue_url，无法继续")

            report_job_progress("token", "running", "正在完成 OAuth 回调并获取 Token")
            session_info, access_token = _finalize_registration_session(
                session,
                continue_url,
                email,
                budget=StageBudget.start(90, cancel=_cancelled),
            )
            report_job_progress("token", "success", "已获取 accessToken")

        # Token is the registration boundary.  Persist the core account before
        # entering any independent 2FA/Codex/plan work.  This is outside the
        # page-shape branches so the existing-session OAuth path is covered too.
        from core.registration.service import persist_registration_core

        account_id = persist_registration_core(
            email=email,
            access_token=access_token,
            chatgpt_session=session_info,
            email_source=selected_email_source or resolve_email_source(email),
            proxy_used=session.proxy or None,
            extra={
                "user": session_info.get("user"),
                "account": session_info.get("account"),
                "expires": session_info.get("expires"),
                "device_id": session.device_id,
                "sentinel_sid": getattr(session, "sentinel_sid", None),
                "browser_profile": getattr(session, "browser_profile", None),
                **({"account_password": openai_password} if openai_password and password_validated else {}),
                "registration_checkpoint": "core_persisted",
                "registration_driver": "protocol",
            },
        )
        core_persisted = True
        logger.info("[核心完成] %s，账号ID=%s，Token 已获取（原值不写日志）", email, account_id)
        if getattr(_protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", True):
            from core.auth.protocol.chatgpt_bootstrap import authenticated_bootstrap
            try:
                authenticated_bootstrap(session, access_token,
                    strict=bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)))
            except (AuthCancelledError, StopRequested):
                raise
            except Exception as exc:
                # 已保存核心凭据，预热失败仅影响后处理。
                logger.warning("登录态预热失败，核心账号已保存：%s", type(exc).__name__)
                if bool(getattr(_protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", False)):
                    bootstrap_error = f"登录态预热未完成：{type(exc).__name__}"
        human_delay("post_auth")

        # Roxy 在刚获取 Token 后、任何账号设置前从登录页读取权益。Protocol 也在
        # 这个窗口复用同一 BrowserSession 和注册代理同步查询，避免 2FA/Codex
        # 等后置动作改变首次登录态后才判断新账号的试用资格。
        plan_result = {"status": "pending", "ok": False, "message": "套餐查询未执行"}
        if plan_check_enabled:
            try:
                from core.accounts.plans.service import check_registration_account_plan

                report_job_progress("plan_check", "running", "正在复用注册会话与代理查询套餐")
                checked = check_registration_account_plan(
                    account_id=account_id,
                    email=email,
                    access_token=access_token,
                    proxy=session.proxy or "",
                    session=session,
                )
                plan_result = dict(checked or {})
                plan_result["ok"] = bool(plan_result.get("ok"))
                plan_result["status"] = "success" if plan_result["ok"] else "failed"
                plan_result["message"] = (
                    "套餐查询完成"
                    if plan_result["ok"]
                    else str(plan_result.get("error") or "套餐查询失败")
                )
                report_job_progress(
                    "plan_check",
                    "success" if plan_result["ok"] else "failed",
                    plan_result["message"][:300],
                )
            except (AuthCancelledError, StopRequested):
                raise
            except Exception as exc:
                plan_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
                report_job_progress("plan_check", "failed", plan_result["message"])
        else:
            plan_result = {"status": "skipped", "ok": True, "message": "未启用注册后自动查套餐"}

        # ==================== 阶段7: 设置 2FA ====================
        totp_secret = None
        if twofa_enabled:
            report_job_progress("twofa", "running", "正在设置 Authenticator 2FA")
            try:
                twofa_driver = _twofa_cfg.get_twofa_driver_for_options(options)
                if twofa_driver != "protocol":
                    raise RuntimeError("协议注册驱动只支持 protocol 2FA；browser 模式请切换到 RoxyBrowser 注册")
                from core.registration.checkpoints import save_protocol_totp_checkpoint
                candidate_secret = setup_2fa_protocol(session, access_token,
                    on_secret=lambda secret: save_protocol_totp_checkpoint(email=email, secret=secret, confirmed=False))
                save_protocol_totp_checkpoint(email=email, secret=candidate_secret, confirmed=True)
                totp_secret = candidate_secret
                report_job_progress("twofa", "success", "协议 2FA 已启用")
            except (AuthCancelledError, StopRequested):
                raise
            except Exception as exc:
                logger.error("2FA 设置未完成：%s", type(exc).__name__)
                logger.warning("核心账号已保存；如已取得密钥，保留待确认状态供后续协调")
                report_job_progress("twofa", "failed", f"2FA 设置未完成：{type(exc).__name__}")
        else:
            logger.debug("已跳过 2FA 设置 (config.ENABLE_2FA=False)")
            report_job_progress("twofa", "skipped", "未启用 Authenticator 2FA")

        # ==================== 阶段 7.5: Codex OAuth ====================
        codex_result = {"status": "skipped", "ok": False, "message": "未触发"}
        try:
            from core.codex.oauth import run_codex_oauth

            if codex_enabled:
                report_job_progress("codex", "running", "正在执行 Codex OAuth")
                from core.registration.service import codex_driver_for_registration

                codex_kwargs = {
                    "proxy": session.proxy,
                    "driver_override": codex_driver_for_registration(options),
                }
                if selected_email_source is not None:
                    codex_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                        address,
                        email_source=selected_email_source,
                        **kwargs,
                    )
                codex_result = run_codex_oauth(
                    email,
                    login_password=openai_password if password_validated else None,
                    login_totp_secret=totp_secret,
                    **codex_kwargs,
                )
                report_job_progress(
                    "codex",
                    "success"
                    if codex_result.get("ok")
                    else "skipped"
                    if codex_result.get("status") == "skipped"
                    else "failed",
                    str(codex_result.get("message") or "Codex OAuth 已完成")[:300],
                )
            else:
                codex_result = {
                    "status": "skipped",
                    "ok": True,
                    "message": "ENABLE_CODEX_AUTO=False，跳过 Codex",
                }
                report_job_progress("codex", "skipped", codex_result["message"])
        except (AuthCancelledError, StopRequested):
            raise
        except AccountUnusableError:
            raise
        except Exception as exc:
            codex_result = {
                "status": "failed",
                "ok": False,
                "message": f"{type(exc).__name__}: {str(exc)[:180]}",
            }
            report_job_progress("codex", "failed", codex_result["message"])

        if codex_result.get("ok"):
            logger.info(
                "[Codex] 成功：%s，授权回调已处理",
                email,
            )
        elif codex_result.get("status") == "skipped":
            logger.info(f"[Codex] 跳过：{email}，原因={codex_result.get('message')}")
        else:
            logger.warning(f"[Codex] 失败：{email}，原因={codex_result.get('message')}")

        # Post-processing is deliberately outside the core persistence call.
        # Keep the existing status projections for account setup/retry views.
        from core import db
        if codex_result.get("status") in {"success", "failed", "skipped", "attention_required"}:
            codex_status = "success" if codex_result.get("ok") and codex_result.get("status") != "skipped" else codex_result.get("status")
            db.update_account_codex_status(
                email,
                codex_status,
                None if codex_status in {"success", "skipped"} else str(codex_result.get("message") or "")[:500],
            )
        # 待确认密钥的状态已由早存入口写入，不能在末尾覆盖成已失败。

        # ==================== 阶段9: 后置自动触发 flow ====================
        flow_result = {"status": "skipped", "ok": False, "message": "未触发"}
        try:
            from core.integrations.flow_trigger import trigger_flow

            flow_result = trigger_flow(access_token)
        except Exception as exc:
            flow_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}

        if flow_result.get("ok"):
            logger.info(
                f"[Flow] 成功：{email}，HTTP={flow_result.get('http_status')}, "
                f"flow_id={flow_result.get('flow_id') or '未解析'}"
            )
        elif flow_result.get("status") == "skipped":
            logger.info(f"[Flow] 跳过：{email}，原因={flow_result.get('message')}")
        else:
            logger.warning(
                f"[Flow] 失败：{email}，HTTP={flow_result.get('http_status') or '无'}, "
                f"原因={flow_result.get('message')}"
            )

        logger.debug("[完成] Authenticator 2FA 状态：%s", "已启用" if totp_secret else "未启用")

        codex_ok = codex_result.get("ok") or codex_result.get("status") == "skipped"
        twofa_ok = (not twofa_enabled) or bool(totp_secret)
        password_ok = not password_required or bool(openai_password and password_validated)
        postprocess_success = bool(codex_ok and twofa_ok and password_ok and plan_result.get("ok") and not bootstrap_error)
        task_error = None if postprocess_success else "; ".join(
            item for item in (
                None if codex_ok else f"Codex 未完成: {codex_result.get('message', '未知')}",
                None if twofa_ok else "2FA 未完成",
                None if plan_result.get("ok") else "套餐查询待重试",
                bootstrap_error,
                None if password_ok else "原密码尚未确认生效",
            ) if item
        )
        from core.registration.postprocess import summarize_postprocess
        readiness = summarize_postprocess(
            core_success=True,
            password_present=bool(openai_password and password_validated),
            outcomes={"twofa": {"status": "success" if twofa_ok else "failed", "ok": twofa_ok},
                      "codex": codex_result, "plan_check": plan_result},
            password_required=password_required,
            twofa_required=twofa_enabled,
            codex_enabled=codex_enabled,
            plan_check_required=plan_check_enabled,
        )

        return {
            "success": True,
            "registration_success": True,
            "core_persisted": core_persisted,
            "postprocess_success": postprocess_success,
            "partial_success": not postprocess_success,
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "flow": flow_result,
            "codex": codex_result,
            "plan_check": plan_result,
            "postprocess_warnings": [bootstrap_error] if bootstrap_error else [],
            "next_actions": [action.as_dict() for action in readiness.next_actions],
            "account_readiness": readiness.account_readiness,
            "remote_identity": remote_identity,
            "remote_identity_state": "confirmed",
            "registration_intent": "reconcile" if remote_identity == "existing" else "new",
            "auth": auth_result_for_registration(
                {"success": True},
                auth_method="protocol",
                remote_identity=remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
            "error": task_error,
        }

    except AuthCancelledError:
        if password_request_started and not core_persisted:
            from core.registration.service import _mark_registration_request_unknown
            _mark_registration_request_unknown("密码请求开始后用户停止，保留原身份等待确认",
                facts={"register_response_confirmed": password_register_accepted})
        raise StopRequested("用户停止协议注册") from None
    except StopRequested:
        if password_request_started and not core_persisted:
            from core.registration.service import _mark_registration_request_unknown
            _mark_registration_request_unknown("密码请求开始后用户停止，保留原身份等待确认",
                facts={"register_response_confirmed": password_register_accepted})
        raise
    except Exception as exc:
        error_text = str(exc)
        auth_route_rejected = bool(
            getattr(exc, "retry_with_new_proxy", False)
            and str(getattr(exc, "code", "") or "") == "auth_route_rejected"
        ) and not password_register_accepted
        request_unknown = password_register_accepted or any(marker in error_text for marker in (
            "后续页面类型未知",
            "响应缺少可跟随 URL",
            "响应缺少 continue_url",
            "请求结果未知",
            "密码验证请求结果未知",
            "续跑邮箱验证码发送未确认",
            "协议续跑密码验证后页面未知",
            "协议续跑密码验证响应未知",
            "协议续跑 TOTP 验证请求结果未知",
            "协议续跑 TOTP 验证响应未知",
            "协议续跑 TOTP 验证后 session 响应缺少 accessToken",
            "session 响应缺少 accessToken",
            "OAuth callback/session",
        ))
        cause_code = _protocol_registration_cause_code(
            exc,
            error_text,
            register_accepted=password_register_accepted,
            checkpoint_account_id=account_id,
            otp_send_in_flight=otp_send_in_flight,
        )
        safe_error_text = _safe_protocol_registration_error(exc, cause_code)
        logger.error("协议注册失败：%s", safe_error_text)
        remote_existing = remote_identity == "existing"
        auth_error_code = (
            "remote_existing"
            if remote_existing
            else "auth_route_rejected"
            if auth_route_rejected
            else "request_unknown"
            if request_unknown
            else "registration_failed"
        )
        account_unusable = isinstance(exc, AccountUnusableError)

        try:
            if email and account_unusable:
                from core.email.provider import mark_email_permanently_unusable

                src = mark_email_permanently_unusable(
                    email,
                    source=selected_email_source,
                    note=f"上游明确确认账号永久失效: {safe_error_text[:180]}",
                )
                logger.warning(f"[邮箱:{src}] {email} 已确认永久失效，标记 failed")
            elif email:
                from core.email.provider import retain_email

                src = retain_email(
                    email,
                    source=selected_email_source,
                    note=f"协议注册中途失败，保留给原任务链: {safe_error_text[:180]}",
                )
                logger.warning(f"[邮箱:{src}] {email} 注册中途失败，保留原邮箱等待重跑或对账")
        except Exception:
            pass
        return {
            "success": False,
            "core_persisted": core_persisted,
            "email": email,
            "account_id": account_id,
            "request_unknown": request_unknown,
            "manual_reconcile": remote_existing,
            # 只有 follow_authorize 的显式路由拒绝才允许外层重启整段协议。
            # 该分支发生在账号创建之前，且不会覆盖 request_unknown/已有账号保护。
            "retry_as_new_route": auth_route_rejected,
            "register_response_confirmed": password_register_accepted,
            "cause_code": cause_code,
            "remote_identity": remote_identity,
            "remote_identity_state": "confirmed" if remote_existing or password_register_accepted else "unknown",
            "remote_account_state": "confirmed" if remote_existing else "request_unknown" if request_unknown else "not_started",
            "error_code": auth_error_code,
            "email_permanently_unusable": account_unusable,
            "account_unusable_error_code": (
                exc.error_code or "account_deactivated"
                if account_unusable
                else None
            ),
            "auth": auth_result_for_registration(
                {"success": False, "error_code": auth_error_code},
                auth_method="protocol",
                remote_identity="existing" if remote_existing else remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
            "error": safe_error_text,
        }
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                logger.warning("协议会话收口失败：%s", type(exc).__name__)
