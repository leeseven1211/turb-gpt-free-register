# -*- coding: utf-8 -*-
"""Codex protocol execution. Domain services inject current compatibility helpers.

This module owns requests/page transitions; credential reads, task reporting,
resource acquisition and callback settlement remain with the caller.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse


@dataclass(frozen=True)
class PasswordAuthCallbacks:
    credentials: Callable[[str], tuple[str, str]]
    auth_error: type[Exception]
    password_verify: Callable[..., dict]


@dataclass(frozen=True)
class MfaAuthCallbacks:
    credentials: Callable[[str], tuple[str, str]]
    auth_error: type[Exception]
    extract_factor_id: Callable[..., str]
    mfa_issue_challenge: Callable[..., Any]
    mfa_verify: Callable[..., dict]
    totp_code: Callable[[str], str]


@dataclass(frozen=True)
class ProtocolExecutionContext:
    """Explicit current-call dependencies; no domain module or mutable globals.

    Compatibility wrappers build this for every invocation so replacing a legacy
    helper continues to affect the same point in the execution chain.
    """

    AccountUnusableError: Any
    CodexAuthPageSession: Any
    CodexAuthResultUnknown: Any
    CodexDiagnosticSession: Any
    CodexSessionDiagnosticComplete: Any
    authorize_login_step: Callable[..., Any]
    build_authorize_url: Callable[..., Any]
    build_sentinel_header: Any
    cache_auth_session_metadata: Callable[..., Any]
    cache_auth_session_payload: Callable[..., Any]
    check_cancelled: Any
    load_client_id: Callable[[], str]
    confirm_email_step: Callable[..., Any]
    confirmed_consent_workspace_id: Callable[..., Any]
    current_workspace_id: Callable[..., Any]
    decode_auth_session_metadata: Callable[..., Any]
    decode_jwt_segment: Callable[..., Any]
    detect_account_unusable_response_body: Any
    ensure_oai_context_url: Callable[..., Any]
    ensure_phone_verification_enabled: Callable[..., Any]
    extract_code: Callable[..., Any]
    extract_continue_url: Callable[..., Any]
    extract_error_code: Any
    follow_login_continue_step: Callable[..., Any]
    follow_until_callback: Callable[..., Any]
    get_workspace_id: Callable[..., Any]
    is_transient_network_error: Any
    logger: Any
    clock: Any
    login_page_type_for_log: Callable[..., Any]
    login_session_presence: Callable[..., Any]
    login_target: Callable[..., Any]
    login_target_for_log: Callable[..., Any]
    max_redirects: Any
    mfa_auth: Callable[[], MfaAuthCallbacks]
    navigate_email_otp_send: Any
    net_backoff_base: Any
    net_max_attempts: Any
    password_auth: Callable[[], PasswordAuthCallbacks]
    post_json: Callable[..., Any]
    load_redirect_uri: Callable[[], str]
    report_stage: Any
    request_sentinel_token: Any
    resp_json: Callable[..., Any]
    rotate_document_navigation_id: Any
    safe_login_path: Callable[..., Any]
    load_token_url: Callable[[], str]
    url_path_for_log: Callable[..., Any]
    verify_saved_login_mfa: Callable[..., Any]
    with_net_retry: Callable[..., Any]
    workspace_cookie_wait_seconds: Any
    workspace_poll_interval_seconds: Any


def _with_net_retry(execution: ProtocolExecutionContext, label: str, fn):
    """
    对临时性网络错误（TLS/代理/超时/重置）做重试包装。
    非临时错误（业务 4xx 等）直接抛。最多 _NET_MAX_ATTEMPTS 次。
    """
    last_exc = None
    for attempt in range(1, execution.net_max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not execution.is_transient_network_error(exc):
                raise
            if attempt >= execution.net_max_attempts:
                break
            backoff = execution.net_backoff_base ** (attempt - 1)
            execution.logger.warning(
                f"[Codex] {label} 临时性网络错误 ({type(exc).__name__}: {str(exc)[:120]})，"
                f"{backoff:.1f}s 后重试 (尝试 {attempt}/{execution.net_max_attempts})..."
            )
            execution.clock.sleep(backoff)
    raise last_exc if last_exc else RuntimeError(f"[Codex] {label} 重试耗尽但无异常记录")


def _is_redirect_uri(execution: ProtocolExecutionContext, location: str) -> bool:
    """判断 Location 是否指向注册的 redirect_uri（localhost:1455/auth/callback）。"""
    try:
        parsed = urlparse(location)
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and \
        parsed.hostname in ("localhost", "127.0.0.1") and \
        parsed.port == 1455 and \
        parsed.path == "/auth/callback"


def _extract_code(execution: ProtocolExecutionContext, location: str, state: str) -> str:
    """从 redirect_uri 的 Location 里提取并校验 code。"""
    parsed = urlparse(location)
    qs = parse_qs(parsed.query)
    err = (qs.get("error") or [""])[0]
    if err:
        raise RuntimeError("[Codex] 授权服务器返回错误")
    code = (qs.get("code") or [""])[0]
    if not code:
        raise RuntimeError("[Codex] redirect_uri 缺少 code 参数")
    returned_states = qs.get("state") or []
    if len(returned_states) != 1 or returned_states[0] != state or not returned_states[0]:
        raise RuntimeError("[Codex] state 不匹配（疑似 CSRF）")
    return code


def _decode_jwt_segment(execution: ProtocolExecutionContext, seg: str) -> dict:
    """base64url 解码一个 JWT/cookie 段为 JSON dict（失败返回 {}）。"""
    try:
        padding = "=" * (-len(seg) % 4)
        return json.loads(base64.urlsafe_b64decode(seg + padding))
    except Exception:
        return {}


def _post_json(execution: ProtocolExecutionContext, session: Any, url: str, payload: dict, referer: str,
               sentinel_header: str | None = None, so_header: str | None = None):
    """统一发 /api/accounts/* 的 JSON POST。"""
    headers = session.get_auth_headers(referer=referer)
    if sentinel_header:
        headers["openai-sentinel-token"] = sentinel_header
    if so_header:
        headers["openai-sentinel-so-token"] = so_header
    resp = session.post(url, headers=headers, data=json.dumps(payload), allow_redirects=False)
    execution.cache_auth_session_metadata(session, resp)
    return resp


def _resp_json(execution: ProtocolExecutionContext, resp) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}


def _decode_auth_session_metadata(execution: ProtocolExecutionContext, value) -> dict:
    """把响应中的 oai-client-auth-session 转成 workspace payload。"""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    return execution.decode_jwt_segment(value.split(".", 1)[0])


def _cache_auth_session_metadata(execution: ProtocolExecutionContext, session: Any, resp) -> None:
    """缓存 Auth 响应携带的 session 元数据，供 cookie 尚未落地时恢复 workspace。"""
    try:
        execution.cache_auth_session_payload(session, execution.resp_json(resp), base_url=getattr(resp, "url", None))
    except Exception:
        execution.logger.debug("[Codex] 缓存 Auth session 元数据失败")


def _cache_auth_session_payload(execution: ProtocolExecutionContext,
    session: Any, payload: dict | None, *, base_url: str | None = "https://auth.openai.com/",
) -> None:
    """仅保留用于工作区选择的 ID，不保存响应中的其他字段。"""
    if not isinstance(payload, dict):
        return
    if isinstance(session, execution.CodexAuthPageSession):
        session.observe_payload(payload, source="continue", base_url=base_url)
    value = payload.get("oai-client-auth-session")
    if value is None:
        value = payload.get("auth_session") or payload.get("authSession")
    decoded = execution.decode_auth_session_metadata(value)
    workspaces = decoded.get("workspaces") if isinstance(decoded, dict) else None
    if not isinstance(workspaces, list):
        return
    ids = [str(item.get("id")) for item in workspaces if isinstance(item, dict) and item.get("id")]
    if ids:
        session._codex_auth_session_payload = {"workspaces": [{"id": item} for item in ids]}


def _bootstrap_authorize(execution: ProtocolExecutionContext,
    session: Any,
    state: str,
    code_challenge: str | None = None,
    auth_url: str | None = None,
) -> None:
    """
    GET Codex authorize URL 并跟随重定向，落到登录页，建立 auth.openai.com cookies
    （含 oai-client-auth-session：内含 Codex 目标 + 后续要用的 workspace 列表）。
    """
    # 默认使用调用方传入的 CPA 授权地址；未传时才走保留的本地 PKCE 生成逻辑。
    if not auth_url:
        if not code_challenge:
            raise RuntimeError("[Codex] 本地生成授权地址需要 code_challenge")
        auth_url = execution.build_authorize_url(state, code_challenge, prompt="login")
    auth_url = execution.ensure_oai_context_url(auth_url, session)
    headers = session.get_auth_navigate_headers(referer="https://chatgpt.com/")
    execution.logger.info("[Codex] 跟随 Codex authorize URL 建立会话...")
    execution.logger.info("[Codex] 授权入口 path=%s", urlparse(auth_url).path or "-")
    resp = execution.with_net_retry(
        "bootstrap authorize",
        lambda: session.get(auth_url, headers=headers, allow_redirects=True),
    )
    execution.logger.debug(
        "[Codex] authorize 落点 path=%s status=%s",
        execution.url_path_for_log(getattr(resp, "url", "")), getattr(resp, "status_code", ""),
    )


def _authorize_login_step(execution: ProtocolExecutionContext, result: dict) -> tuple[str, str]:
    """按服务端给出的页面和下一步地址识别登录挑战。"""
    if not isinstance(result, dict):
        raise RuntimeError("[Codex] 登录下一步响应格式未知，已停止等待邮箱验证码")
    page = result.get("page") if isinstance(result.get("page"), dict) else {}
    page_type = str(page.get("type") or "").strip().lower().replace("-", "_")
    continue_url = execution.extract_continue_url(result)
    path = ""
    trusted_callback = False
    if continue_url:
        trusted_url, trusted_callback = execution.login_target(continue_url)
        parsed = urlparse(trusted_url)
        path = parsed.path.rstrip("/").lower()

    # 页面类型与地址相互矛盾时拒绝请求，避免将发码地址当密码页打开。
    password_page = "password" in page_type
    mfa_page = "mfa" in page_type or "totp" in page_type
    email_page = page_type == "email_verification" or page_type.startswith("email_otp")
    phone_page = page_type in ("add_phone", "phone_verification")
    workspace_page = page_type in ("workspace_select", "workspace_selection")
    consent_page = page_type == "consent"
    password_path = path in ("/log-in/password", "/create-account/password")
    mfa_path = path.startswith("/mfa-challenge")
    email_path = path in ("/api/accounts/email-otp/send", "/email-verification")
    phone_path = path in ("/add-phone", "/phone-verification", "/api/accounts/add-phone/send")
    workspace_path = path == "/api/accounts/workspace/select"
    consent_path = path == "/sign-in-with-chatgpt/codex/consent"
    if (
        (password_page and (email_path or mfa_path))
        or (mfa_page and (email_path or password_path))
        or (email_page and (password_path or mfa_path))
        or ((password_page or mfa_page or email_page) and (workspace_path or consent_path or trusted_callback))
        or (phone_page and (password_path or mfa_path or email_path or workspace_path or consent_path or trusted_callback))
        or (workspace_page and (password_path or mfa_path or email_path or phone_path or consent_path or trusted_callback))
        or (consent_page and (password_path or mfa_path or email_path or phone_path or workspace_path or trusted_callback))
    ):
        raise RuntimeError("[Codex] 登录下一步页面类型与地址不一致，已停止请求")

    # 密码/TOTP 属于独立挑战，绝不能把 HTTP 200 误判为已发送邮箱 OTP。
    if path == "/create-account/password":
        raise RuntimeError("[Codex] 登录进入创建账号密码页，账号状态需先完成注册")
    if password_page or path == "/log-in/password":
        if continue_url and path != "/log-in/password":
            raise RuntimeError("[Codex] 登录密码挑战地址未获确认，已停止请求")
        return "password", continue_url
    if mfa_page or mfa_path:
        return "mfa", continue_url
    if path == "/api/accounts/email-otp/send":
        return "send", continue_url
    if path == "/email-verification":
        return "verify", continue_url
    if not continue_url and page_type in ("email_verification", "email_otp", "email_otp_verify"):
        return "verify", ""
    if phone_path or phone_page:
        return "phone", continue_url
    if workspace_path:
        return "workspace", ""
    if workspace_page:
        return "workspace", ""
    if trusted_callback:
        return "callback", continue_url
    if consent_path or consent_page:
        return "consent", continue_url
    if path in (
        "/authorize/continue", "/api/accounts/continue"
    ) or path.startswith("/sign-in-with-chatgpt/"):
        return "continue", continue_url
    if not continue_url and page_type == "authorize":
        return "continue", ""
    raise RuntimeError("[Codex] 提交邮箱后未确认进入邮箱验证码页，已停止等待")


def _confirm_email_step(execution: ProtocolExecutionContext,
    session: Any,
    step: str,
    continue_url: str,
    after_ts: float,
    *,
    referer: str = "https://auth.openai.com/log-in",
) -> tuple[str, str, float]:
    """只沿受信任的发码地址建立邮箱验证码页。"""
    if step == "send":
        after_ts = execution.clock.time()
        execution.navigate_email_otp_send(
            session,
            continue_url=continue_url,
            referer=referer,
        )
        return "verify", "", after_ts
    return step, continue_url, after_ts


def _submit_email(execution: ProtocolExecutionContext,
    session: Any, email: str, *, login_totp_secret: str | None = None
) -> tuple[str, str, float]:
    """POST authorize/continue，返回已确认的下一步登录挑战。"""
    sentinel_resp = execution.request_sentinel_token(session, "authorize_continue")
    sentinel_header, so_header = execution.build_sentinel_header(session, sentinel_resp, "authorize_continue")
    payload = {"username": {"kind": "email", "value": email}}
    otp_after_ts = execution.clock.time()
    resp = execution.post_json(
        session,
        "https://auth.openai.com/api/accounts/authorize/continue",
        payload,
        referer="https://auth.openai.com/log-in",
        sentinel_header=sentinel_header,
        so_header=so_header,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"[Codex] 提交邮箱失败 status={resp.status_code}")
    result = execution.resp_json(resp)
    step, continue_url = execution.authorize_login_step(result)
    cookie_present, cache_present = execution.login_session_presence(session)
    execution.logger.info(
        "[Codex] 邮箱提交响应 status=%s step=%s page_type=%s path=%s cookie=%s cache=%s",
        resp.status_code, step, execution.login_page_type_for_log(result),
        execution.safe_login_path(continue_url), cookie_present, cache_present,
    )
    if step == "mfa":
        return execution.verify_saved_login_mfa(
            session, email, result, continue_url, login_totp_secret=login_totp_secret
        )
    step, continue_url, otp_after_ts = execution.confirm_email_step(session, step, continue_url, otp_after_ts)
    return step, continue_url, otp_after_ts


def _verify_saved_login_password(execution: ProtocolExecutionContext,
    session: Any, email: str, continue_url: str = "", *,
    login_password: str | None = None,
    login_totp_secret: str | None = None,
) -> tuple[str, str, float]:
    """使用本轮或已保存的 OpenAI 密码，并识别服务端下一步。"""
    auth = execution.password_auth()

    password = str(login_password or "").strip()
    if not password:
        password, _ = auth.credentials(email)
    if not password:
        raise RuntimeError("[Codex] 登录要求密码验证，但账号没有已保存的 OpenAI 登录密码")
    # 使用服务端返回的密码页地址，保留其 query 中的挑战状态。
    password_url = continue_url or "https://auth.openai.com/log-in/password"
    if password_url.startswith("/"):
        password_url = "https://auth.openai.com" + password_url
    response = session.get(
        password_url,
        headers=session.get_auth_navigate_headers(referer="https://auth.openai.com/log-in"),
        allow_redirects=True,
    )
    try:
        final_url = urlparse(str(getattr(response, "url", "") or ""))
        final_path = final_url.path.rstrip("/").lower()
        final_port = final_url.port
    except ValueError:
        raise RuntimeError("[Codex] 登录密码页导航地址无效") from None
    if (
        response.status_code != 200
        or final_url.scheme.lower() != "https"
        or (final_url.hostname or "").lower() != "auth.openai.com"
        or final_port not in (None, 443)
        or final_url.username is not None
        or final_url.password is not None
        or final_path != "/log-in/password"
    ):
        raise RuntimeError("[Codex] 登录密码页导航未获确认")
    execution.rotate_document_navigation_id(session)
    otp_after_ts = execution.clock.time()
    try:
        result = auth.password_verify(session, password)
    except auth.auth_error as exc:
        if exc.code == "account_deactivated":
            raise execution.AccountUnusableError("[Codex] 账号已停用", error_code="account_deactivated") from None
        if exc.code not in ("password_rejected", "password_missing", "password_sentinel_failed"):
            raise execution.CodexAuthResultUnknown("[Codex] 密码验证请求结果未知，需先核对登录状态") from None
        raise RuntimeError(f"[Codex] 密码验证失败：{exc.code}") from None
    execution.cache_auth_session_payload(session, result)
    step, continue_url = execution.authorize_login_step(result)
    cookie_present, cache_present = execution.login_session_presence(session)
    execution.logger.info(
        "[Codex] 密码验证响应 status=2xx step=%s page_type=%s path=%s cookie=%s cache=%s",
        step, execution.login_page_type_for_log(result), execution.safe_login_path(continue_url),
        cookie_present, cache_present,
    )
    if step == "password":
        raise RuntimeError("[Codex] 密码验证后仍停留在密码挑战，已停止重复提交")
    if step == "mfa":
        return execution.verify_saved_login_mfa(
            session, email, result, continue_url, login_totp_secret=login_totp_secret
        )
    return execution.confirm_email_step(
        session,
        step,
        continue_url,
        otp_after_ts,
        referer="https://auth.openai.com/log-in/password",
    )


def _verify_saved_login_mfa(execution: ProtocolExecutionContext,
    session: Any, email: str, result: dict, continue_url: str, *,
    login_totp_secret: str | None = None,
) -> tuple[str, str, float]:
    """在当前 Codex Auth 会话完成 TOTP，保留后续 OAuth 地址供本驱动处理。"""
    auth = execution.mfa_auth()

    totp_secret = str(login_totp_secret or "").strip()
    if not totp_secret:
        _, totp_secret = auth.credentials(email)
    if not totp_secret:
        raise RuntimeError("[Codex] 登录要求 Authenticator 2FA，但账号没有已保存的 TOTP secret")
    factor_id = auth.extract_factor_id(result, continue_url)
    if not factor_id:
        raise RuntimeError("[Codex] 登录 MFA 响应缺少 factor_id，已停止验证")
    execution.report_stage("login_mfa", "正在验证已保存的 Authenticator 2FA")
    try:
        execution.check_cancelled()
        auth.mfa_issue_challenge(session, factor_id)
    except auth.auth_error as exc:
        raise RuntimeError(f"[Codex] MFA 挑战初始化失败：{exc.code}") from None
    execution.check_cancelled()
    otp_after_ts = execution.clock.time()
    try:
        mfa_result = auth.mfa_verify(session, factor_id, auth.totp_code(totp_secret))
    except auth.auth_error as exc:
        if exc.code == "account_deactivated":
            raise execution.AccountUnusableError("[Codex] 账号已停用", error_code="account_deactivated") from None
        if exc.code not in ("mfa_rejected", "mfa_code_missing"):
            raise execution.CodexAuthResultUnknown("[Codex] MFA 验证请求结果未知，需先核对登录状态") from None
        raise RuntimeError(f"[Codex] MFA 验证失败：{exc.code}") from None
    execution.cache_auth_session_payload(session, mfa_result)
    step, next_url = execution.authorize_login_step(mfa_result)
    cookie_present, cache_present = execution.login_session_presence(session)
    execution.logger.info(
        "[Codex] MFA 验证响应 status=2xx step=%s page_type=%s path=%s cookie=%s cache=%s",
        step, execution.login_page_type_for_log(mfa_result), execution.safe_login_path(next_url),
        cookie_present, cache_present,
    )
    if step == "mfa":
        raise RuntimeError("[Codex] MFA 验证后仍停留在 MFA 挑战，已停止重复提交")
    execution.report_stage("login_mfa", "Authenticator 2FA 已通过", state="success")
    if isinstance(session, execution.CodexDiagnosticSession):
        raise execution.CodexSessionDiagnosticComplete(session.collect_after_mfa())
    return execution.confirm_email_step(
        session,
        step,
        next_url,
        otp_after_ts,
        referer="https://auth.openai.com/mfa-challenge",
    )


def _submit_email_otp(execution: ProtocolExecutionContext, session: Any, code: str) -> dict:
    """POST email-otp/validate 提交邮箱验证码。带 sentinel(authorize_continue)。"""
    sentinel_resp = execution.request_sentinel_token(session, "authorize_continue")
    sentinel_header, so_header = execution.build_sentinel_header(session, sentinel_resp, "authorize_continue")
    resp = execution.post_json(
        session,
        "https://auth.openai.com/api/accounts/email-otp/validate",
        {"code": code},
        referer="https://auth.openai.com/email-verification",
        sentinel_header=sentinel_header,
        so_header=so_header,
    )
    if resp.status_code != 200:
        error_code = execution.extract_error_code(resp)
        if error_code in ("account_deactivated", "account_deleted", "account_banned"):
            raise execution.AccountUnusableError(
                f"[Codex] 账号已废（{error_code}）status={resp.status_code}",
                error_code=error_code,
            )
        body_error_code = execution.detect_account_unusable_response_body(resp.text or "")
        if body_error_code:
            raise execution.AccountUnusableError(
                f"[Codex] 账号已废（{body_error_code}）status={resp.status_code}",
                error_code=body_error_code,
            )
        raise RuntimeError(f"[Codex] 邮箱 OTP 验证失败 status={resp.status_code}")
    execution.logger.info("[Codex] 邮箱 OTP 验证通过")
    return execution.resp_json(resp)


def _current_workspace_id(execution: ProtocolExecutionContext, session: Any) -> tuple[str, str, bool]:
    """只读取当前会话已确认的工作区 ID；不发请求、不等待。"""
    def find_workspace_id(payload: dict) -> str:
        workspaces = payload.get("workspaces") if isinstance(payload, dict) else None
        for workspace in workspaces if isinstance(workspaces, list) else []:
            if isinstance(workspace, dict) and workspace.get("id"):
                return str(workspace["id"])
        return ""

    raw = None
    try:
        for cookie in session.session.cookies.jar:
            if cookie.name == "oai-client-auth-session":
                raw = cookie.value
                break
    except Exception:
        pass
    if not raw:
        try:
            raw = session.session.cookies.get("oai-client-auth-session")
        except Exception:
            raw = None

    if raw:
        workspace_id = find_workspace_id(execution.decode_auth_session_metadata(raw))
        if workspace_id:
            return workspace_id, "cookie", True
    workspace_id = find_workspace_id(getattr(session, "_codex_auth_session_payload", {}) or {})
    if workspace_id:
        return workspace_id, "cache", bool(raw)
    return "", "", bool(raw)


def _confirmed_consent_workspace_id(execution: ProtocolExecutionContext, session: Any) -> str:
    """确认 Cookie 与本轮 Auth 元数据中只有一个一致的工作区。"""
    payloads = [getattr(session, "_codex_auth_session_payload", {}) or {}]
    raw_cookies = []
    try:
        raw_cookies = [
            cookie.value for cookie in session.session.cookies.jar
            if cookie.name == "oai-client-auth-session" and cookie.value
        ]
    except Exception:
        pass
    if not raw_cookies:
        try:
            raw = session.session.cookies.get("oai-client-auth-session")
            if raw:
                raw_cookies.append(raw)
        except Exception:
            pass
    payloads.extend(execution.decode_auth_session_metadata(raw) for raw in raw_cookies)
    workspace_ids = set()
    for payload in payloads:
        workspaces = payload.get("workspaces") if isinstance(payload, dict) else None
        for workspace in workspaces if isinstance(workspaces, list) else []:
            workspace_id = workspace.get("id") if isinstance(workspace, dict) else None
            if not isinstance(workspace_id, str) or not workspace_id.strip():
                return ""
            workspace_ids.add(workspace_id.strip())
    return next(iter(workspace_ids)) if len(workspace_ids) == 1 else ""


def _get_workspace_id(execution: ProtocolExecutionContext, session: Any) -> str:
    """
    优先从 oai-client-auth-session cookie 解出 workspace；cookie 尚未落地时，
    退回 Auth 响应元数据，并在有界时间内等待 cookie/响应状态完成。
    """
    deadline = execution.clock.monotonic() + max(0.0, float(execution.workspace_cookie_wait_seconds))
    while True:
        workspace_id, source, cookie_present = execution.current_workspace_id(session)
        if workspace_id:
            execution.logger.info("[Codex] 已从%s确认工作区", "登录 Cookie" if source == "cookie" else "Auth 响应元数据")
            return workspace_id

        remaining = deadline - execution.clock.monotonic()
        if remaining <= 0:
            if not cookie_present:
                raise RuntimeError("[Codex] 找不到 oai-client-auth-session cookie，无法取 workspace_id")
            raise RuntimeError("[Codex] oai-client-auth-session 中无可用 workspace_id")
        execution.clock.sleep(min(execution.workspace_poll_interval_seconds, remaining))


def _extract_continue_url(execution: ProtocolExecutionContext, result: dict | None) -> str:
    """从 Auth JSON 响应中提取 continue/redirect URL。"""
    if not isinstance(result, dict):
        return ""
    page = result.get("page") or {}
    page = page if isinstance(page, dict) else {}
    return str(
        result.get("continue_url")
        or result.get("external_url")
        or result.get("redirect_url")
        or result.get("url")
        or page.get("continue_url")
        or page.get("external_url")
        or page.get("redirect_url")
        or page.get("url")
        or ""
    ).strip()


def _url_path_for_log(execution: ProtocolExecutionContext, value: str | None) -> str:
    """仅保留 URL path，避免日志记录 OAuth state/code 等 query 参数。"""
    try:
        return urlparse(str(value or "")).path[:120] or "-"
    except ValueError:
        return "-"


def _login_target(execution: ProtocolExecutionContext, value: str, *, base_url: str = "https://auth.openai.com/") -> tuple[str, bool]:
    """沿服务端返回地址继续登录，不按域名白名单阻断后续跳转。"""
    raw = str(value or "").strip()
    if not raw or "\\" in raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise RuntimeError("[Codex] 登录后续地址格式无效")
    try:
        raw = urljoin(base_url, raw)
        parsed = urlparse(raw)
        port = parsed.port
        callback = (
            parsed.scheme.lower() == "http"
            and (parsed.hostname or "").lower() in ("localhost", "127.0.0.1")
            and port == 1455
            and parsed.path == "/auth/callback"
        )
    except ValueError:
        raise RuntimeError("[Codex] 登录后续地址格式无效") from None
    return raw, callback


def _login_target_for_log(execution: ProtocolExecutionContext, value: str, *, base_url: str = "https://auth.openai.com/") -> str:
    """记录跳转结构，省略凭据、查询值及未知路径中的动态标识。"""
    try:
        url, _ = execution.login_target(value, base_url=base_url)
        parsed = urlparse(url)
        detail = {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "path": execution.safe_login_path(url),
            "query_keys": sorted(parse_qs(parsed.query, keep_blank_values=True)),
            "fragment_present": bool(parsed.fragment),
            "userinfo_present": parsed.username is not None or parsed.password is not None,
        }
    except (RuntimeError, ValueError):
        detail = {"format": "invalid"}
    return json.dumps(detail, ensure_ascii=False, sort_keys=True)


def _safe_login_path(execution: ProtocolExecutionContext, value: str | None) -> str:
    """诊断仅保留已知路径，动态挑战 ID 与查询参数一律不写日志。"""
    try:
        url, callback = execution.login_target(str(value or ""))
        path = urlparse(url).path.rstrip("/").lower()
    except RuntimeError:
        return "-"
    if callback:
        return "/auth/callback"
    if path.startswith("/mfa-challenge/"):
        return "/mfa-challenge/*"
    if path == "/sign-in-with-chatgpt/codex/consent":
        return path
    if path.startswith("/sign-in-with-chatgpt/"):
        return "/sign-in-with-chatgpt/*"
    if path in {
        "/authorize/continue", "/api/accounts/continue", "/api/accounts/workspace/select",
        "/email-verification", "/add-phone", "/phone-verification", "/api/accounts/add-phone/send",
        "/log-in/password",
    }:
        return path
    return "/other"


def _login_session_presence(execution: ProtocolExecutionContext, session: Any) -> tuple[bool, bool]:
    """脱敏诊断只报告 Auth Cookie 和工作区缓存是否存在。"""
    cookie_present = False
    try:
        cookies = session.session.cookies
        cookie_present = any(item.name == "oai-client-auth-session" for item in cookies.jar)
        if not cookie_present:
            cookie_present = bool(cookies.get("oai-client-auth-session"))
    except Exception:
        pass
    return cookie_present, bool(getattr(session, "_codex_auth_session_payload", None))


def _login_page_type_for_log(execution: ProtocolExecutionContext, payload: dict) -> str:
    page = payload.get("page") if isinstance(payload.get("page"), dict) else {}
    value = str(page.get("type") or "").strip().lower().replace("-", "_")
    return value if value in {
        "workspace_select", "workspace_selection", "consent", "authorize",
        "add_phone", "phone_verification", "email_verification", "login_password",
        "mfa_challenge",
    } else "unknown"


def _follow_login_continue_step(execution: ProtocolExecutionContext,
    session: Any, continue_url: str, state: str,
) -> tuple[str, str]:
    """逐跳识别登录后续；工作区步骤可携带授权页已确认的 ID。"""
    if not continue_url:
        raise RuntimeError("[Codex] 登录后续响应缺少可跟随地址")
    url, callback = execution.login_target(continue_url)
    for hop in range(execution.max_redirects):
        if callback:
            execution.extract_code(url, state)
            return "callback", url
        path = urlparse(url).path.rstrip("/").lower()
        if path == "/api/accounts/workspace/select":
            return "workspace", ""
        headers = session.get_auth_navigate_headers(
            referer="https://auth.openai.com/", user_initiated=True
        )
        resp = session.get(url, headers=headers, allow_redirects=False)
        final_url, final_callback = execution.login_target(str(getattr(resp, "url", "") or url))
        execution.cache_auth_session_metadata(session, resp)
        try:
            status = int(getattr(resp, "status_code", 0) or 0)
        except (TypeError, ValueError):
            status = 0
        payload = execution.resp_json(resp)
        payload = payload if isinstance(payload, dict) else {}
        location = (getattr(resp, "headers", None) or {}).get("location") or (
            getattr(resp, "headers", None) or {}
        ).get("Location")
        cookie_present, cache_present = execution.login_session_presence(session)
        execution.logger.info(
            "[Codex] 登录后续 hop=%s status=%s page_type=%s path=%s location_path=%s cookie=%s cache=%s",
            hop, status, execution.login_page_type_for_log(payload), execution.safe_login_path(final_url),
            execution.safe_login_path(location), cookie_present, cache_present,
        )
        if status < 200 or status >= 400:
            raise RuntimeError(f"[Codex] 登录后续请求未成功 status={status}")
        next_url = location or execution.extract_continue_url(payload)
        if next_url:
            execution.logger.info(
                "[Codex] 登录后续跳转 hop=%s status=%s source=%s target=%s",
                hop, status, "Location" if location else "JSON",
                execution.login_target_for_log(next_url, base_url=final_url),
            )
            next_url, _ = execution.login_target(next_url, base_url=final_url)
            next_result = {"continue_url": next_url}
            if not location and isinstance(payload.get("page"), dict):
                next_result["page"] = payload["page"]
            next_step, _ = execution.authorize_login_step(next_result)
            if next_step in ("workspace", "phone"):
                return next_step, ""
            if next_step == "callback":
                callback_url, _ = execution.login_target(next_url)
                execution.extract_code(callback_url, state)
                return "callback", callback_url
            if next_step not in ("continue", "consent"):
                raise RuntimeError("[Codex] 登录后续返回未支持的验证挑战，已停止继续")
            url, callback = execution.login_target(next_url)
            continue
        if final_callback:
            execution.extract_code(final_url, state)
            return "callback", final_url
        final_path = urlparse(final_url).path.rstrip("/").lower()
        if final_path == "/api/accounts/workspace/select":
            return "workspace", ""
        if final_path == "/sign-in-with-chatgpt/codex/consent":
            workspace_id = execution.confirmed_consent_workspace_id(session) if status == 200 and not payload else ""
            if workspace_id:
                execution.logger.info("[Codex] 已确认授权页及单一工作区，继续工作区选择")
                return "workspace", workspace_id
            return "consent", ""
        if final_path in ("/add-phone", "/phone-verification", "/api/accounts/add-phone/send"):
            return "phone", ""
        if payload:
            step, _ = execution.authorize_login_step(payload)
            if step in ("workspace", "consent", "phone"):
                return step, ""
        raise RuntimeError("[Codex] 登录后续响应未确认 callback、授权确认或工作区选择")
    raise RuntimeError(f"[Codex] 登录后续跟随超过 {execution.max_redirects} 跳")


def _follow_login_continue(execution: ProtocolExecutionContext, session: Any, continue_url: str, state: str) -> str | None:
    """兼容旧调用方：仅在确认 callback 后返回 URL。"""
    step, url = execution.follow_login_continue_step(session, continue_url, state)
    return url if step == "callback" else None


def _select_workspace_and_get_callback(execution: ProtocolExecutionContext,
    session: Any, state: str, *, workspace_id: str | None = None,
    phone_enabled: bool | None = None,
) -> str:
    """
    POST workspace/select，然后跟随后续重定向/响应里的 URL 直到命中 localhost:1455 callback。
    返回完整 callback URL（含 code）。
    """
    execution.report_stage("workspace", "正在选择已确认的工作区并等待 OAuth 回调")
    wid = workspace_id if workspace_id is not None else execution.get_workspace_id(session)
    resp = execution.post_json(
        session,
        "https://auth.openai.com/api/accounts/workspace/select",
        {"workspace_id": wid},
        referer="https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
    )

    # 1) 直接带 Location 头命中 callback
    loc = resp.headers.get("location") or resp.headers.get("Location")
    response_url = str(getattr(resp, "url", "") or "https://auth.openai.com/api/accounts/workspace/select")
    execution.logger.info("[Codex] 工作区选择响应 status=%s", resp.status_code)
    if loc:
        execution.logger.info(
            "[Codex] 工作区后续跳转 source=Location target=%s",
            execution.login_target_for_log(loc, base_url=response_url),
        )
        trusted_loc, callback = execution.login_target(loc, base_url=response_url)
        if callback:
            execution.extract_code(trusted_loc, state)
            execution.report_stage("workspace", "工作区选择已确认并收到有效 OAuth 回调", state="success")
            return trusted_loc

    # 2) 响应 JSON 里给了下一步 URL（continue_url / redirect_url / url / next）
    data = execution.resp_json(resp)
    data = data if isinstance(data, dict) else {}
    next_url = None
    next_source = "Location"
    for key in ("redirect_url", "continue_url", "url", "next", "location"):
        v = data.get(key)
        if isinstance(v, str) and v:
            next_url = v
            next_source = key
            break

    # 3) 没给 URL 但有 Location（非 callback）→ 从 Location 起跟
    if not next_url and loc:
        next_url = loc

    if not next_url:
        raise RuntimeError(f"[Codex] workspace/select 后找不到下一跳 URL: status={resp.status_code}")

    execution.logger.info(
        "[Codex] 工作区后续跳转 source=%s target=%s",
        next_source,
        execution.login_target_for_log(next_url, base_url=response_url),
    )
    next_url, _ = execution.login_target(next_url, base_url=response_url)

    # 跟随重定向链直到命中 callback
    callback_url = execution.follow_until_callback(session, next_url, state, phone_enabled=phone_enabled)
    execution.extract_code(callback_url, state)
    execution.report_stage("workspace", "工作区选择已确认并收到有效 OAuth 回调", state="success")
    return callback_url


def _follow_until_callback(execution: ProtocolExecutionContext,
    session: Any, url: str, state: str, *, phone_enabled: bool | None = None,
) -> str:
    """从给定 URL 起逐跳跟随，命中 localhost:1455 callback 时返回其 Location。"""
    step, callback = execution.follow_login_continue_step(session, url, state)
    if step == "phone":
        execution.ensure_phone_verification_enabled(phone_enabled)
    if step != "callback":
        raise RuntimeError("[Codex] 工作区选择后尚未确认 OAuth callback，已停止继续")
    return callback


def exchange_codex_token(execution: ProtocolExecutionContext, session: Any, code: str, code_verifier: str) -> dict:
    """用 authorization code 换 token。"""
    data = {
        "grant_type": "authorization_code",
        "client_id": execution.load_client_id(),
        "code": code,
        "redirect_uri": execution.load_redirect_uri(),
        "code_verifier": code_verifier,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    base = session._get_common_headers()
    base.update(headers)
    headers = base

    execution.logger.info("[Codex] 用 authorization code 换 token...")
    resp = session.post(execution.load_token_url(), headers=headers, data=urlencode(data))
    http_status = resp.status_code
    if http_status != 200:
        raise RuntimeError(f"[Codex] 换 token 失败 status={http_status}")
    token_resp = resp.json()
    if not token_resp.get("access_token"):
        raise RuntimeError("[Codex] token 响应缺少 access_token")
    execution.logger.info("[Codex] 换 token 成功，expires_in=%s", token_resp.get("expires_in"))
    return token_resp
