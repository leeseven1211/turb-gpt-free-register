"""已有账号补密码的独立协议接口，不改变注册或登录驱动。"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from core.accounts.liveness.protocol import v2 as protocol_auth
from core.accounts.password_setup.proxy import is_proxy_transport_failure
from core.auth.protocol.openai_auth import build_sentinel_header, request_sentinel_token
from core.auth.protocol.sentinel_runner import generate_sentinel_token
from core.auth.state_machine import CancellationRequested
from core.email import provider as email_provider
from core.email.mailbox_wait import use_cooperative_wait
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

_CHATGPT = "https://chatgpt.com"
_AUTH = "https://auth.openai.com"
_PASSWORD_PAGE = _AUTH + "/reset-password/new-password"
_CONTROL_ERRORS = (CancellationRequested, OperationCancelled, OperationLeaseLost)
_PENDING_TYPES = {"password", "new_password", "password_reset", "email_verification", "email_otp", "mfa_challenge", "about_you"}
logger = logging.getLogger(__name__)


class ProtocolPasswordSetupError(RuntimeError):
    """仅携带分类与脱敏说明；未知结果只用于最终密码提交。"""

    def __init__(self, code: str, message: str, request_unknown: bool = False,
                 *, proxy_transport_failed: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_unknown = request_unknown
        self.proxy_transport_failed = proxy_transport_failed


def _check(checkpoint: Callable[[], None] | None) -> None:
    if checkpoint is not None:
        checkpoint()


def _trusted_url(value: str, *, unknown: bool = False) -> str:
    try:
        parsed = urlsplit(str(value or ""))
        valid = (
            parsed.scheme == "https" and parsed.hostname in {"chatgpt.com", "auth.openai.com"}
            and parsed.port in (None, 443) and not parsed.username and not parsed.password
            and not parsed.fragment
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ProtocolPasswordSetupError("password_setup_untrusted_redirect", "补密码流程返回了不受信任的跳转地址", unknown)
    return str(value)


def _request(session, method: str, url: str, *, checkpoint=None, final: bool = False, **kwargs):
    _check(checkpoint)
    try:
        return getattr(session, method)(url, **kwargs)
    except _CONTROL_ERRORS:
        raise
    except Exception as exc:
        raise ProtocolPasswordSetupError(
            "password_setup_request_unknown" if final else "password_setup_network_failed",
            "密码提交响应未能确认，请保留本次候选密码后核实" if final else "补密码请求未完成，请检查连接后重试",
            final,
            proxy_transport_failed=is_proxy_transport_failure(exc),
        ) from None


def _payload(response, *, final: bool = False) -> dict:
    try:
        data = response.json()
    except _CONTROL_ERRORS:
        raise
    except Exception:
        data = None
    status = int(getattr(response, "status_code", 0) or 0)
    error = data.get("error") if isinstance(data, dict) else None
    if status < 200 or status >= 300 or error:
        request_unknown = False
        details = error if isinstance(error, dict) else {}
        reason = str(details.get("code") or error or "").lower() + " " + str(details.get("message") or "").lower()
        if re.search(r"password_(?:already_(?:exists|set|added)|exists)|already (?:has|have|set).{0,20}password|password.{0,20}already", reason):
            code, message = "password_setup_already_set", "远端账号已设置密码，本操作不会重置已有密码"
        elif any(item in reason for item in ("invalid_state", "session_expired", "session_invalid", "login_required")) or status == 401:
            code, message = "password_setup_session_expired", "补密码登录状态已失效，请重新登录后重试"
        elif any(item in reason for item in ("mfa", "totp")):
            code, message = "password_setup_mfa_rejected", "补密码 2FA 验证未通过，请检查账号已有的密钥"
        elif any(item in reason for item in ("wrong_email_otp", "invalid_code", "invalid otp", "wrong code")):
            code, message = "password_setup_otp_rejected", "补密码邮箱验证码被拒绝，请重新获取本轮验证码"
        elif status == 429:
            code, message = "password_setup_rate_limited", "补密码请求受到限流，请稍后重试"
        elif status == 403:
            code, message = "password_setup_security_check", "补密码请求未通过安全校验，请检查当前会话和代理"
        elif final and (status <= 0 or 500 <= status < 600):
            # 上游错误或缺失 HTTP 状态不能证明密码未落地，仍需保留本次候选密码核实。
            code, message = "password_setup_request_unknown", "密码提交返回了无法确认结果的上游响应，请保留本次候选密码后核实"
            request_unknown = True
        else:
            code, message = "password_setup_http_rejected", f"补密码接口拒绝了请求（HTTP {status}）"
        raise ProtocolPasswordSetupError(code, message, request_unknown)
    if not isinstance(data, dict):
        raise ProtocolPasswordSetupError("password_setup_response_invalid", "补密码接口返回了无法确认的数据格式", final)
    return data


def _response_ok(response, *, unknown: bool = False) -> None:
    status = int(getattr(response, "status_code", 0) or 0)
    if not 200 <= status < 400:
        _payload(response, final=unknown)


def _follow(session, url: str, *, referer: str, checkpoint=None, final: bool = False) -> str:
    current = _trusted_url(url, unknown=final)
    for _ in range(12):
        chatgpt = urlsplit(current).hostname == "chatgpt.com"
        headers = (session.get_chatgpt_navigate_headers(referer=referer) if chatgpt
                   else session.get_auth_navigate_headers(referer=referer))
        response = _request(session, "get", current, headers=headers, allow_redirects=False, checkpoint=checkpoint, final=final)
        status = int(getattr(response, "status_code", 0) or 0)
        if status in (301, 302, 303, 307, 308):
            location = getattr(response, "headers", {}).get("location") or getattr(response, "headers", {}).get("Location")
            if not location:
                raise ProtocolPasswordSetupError("password_setup_redirect_invalid", "补密码跳转响应缺少目标地址", final)
            referer, current = current, _trusted_url(urljoin(current, location), unknown=final)
            continue
        _response_ok(response, unknown=final)
        return _trusted_url(str(getattr(response, "url", "") or current), unknown=final)
    raise ProtocolPasswordSetupError("password_setup_redirect_limit", "补密码跳转次数超出限制", final)


def _sentinel_headers(session, flow: str, checkpoint=None) -> dict[str, str]:
    _check(checkpoint)
    try:
        challenge = request_sentinel_token(session, flow)
        _check(checkpoint)
        if flow in {"email_otp_validate", "authorize_continue"}:
            token, observer = build_sentinel_header(session, challenge, flow)
        else:
            # 共享 runner 尚无 password_reset 页面映射，独立指定页面，不修改注册默认值。
            profile = dict(getattr(session, "browser_profile", {}) or {})
            profile["build_id"] = ""
            output = generate_sentinel_token(
                challenge=challenge, flow=flow, device_id=session.device_id,
                user_agent=profile.get("user_agent"), page_url=_PASSWORD_PAGE,
                browser_profile=profile, sentinel_sid=getattr(session, "sentinel_sid", None),
                react_listening_key=getattr(session, "react_listening_key", None),
                react_container_key=getattr(session, "react_container_key", None),
                react_resources_key=getattr(session, "react_resources_key", None),
                cookie=session.auth_cookie_header(),
            )
            parsed = json.loads(output)
            observer_value = parsed.pop("_so", None) or parsed.pop("so", None)
            if (not isinstance(parsed, dict) or not parsed.get("p") or not parsed.get("c")
                    or parsed.get("id") != session.device_id or parsed.get("flow") != flow):
                raise ValueError
            token = json.dumps(parsed, separators=(",", ":"))
            observer = (json.dumps({"so": observer_value, "c": parsed["c"], "id": session.device_id, "flow": flow}, separators=(",", ":"))
                        if observer_value else None)
        if not token:
            raise ValueError
    except _CONTROL_ERRORS:
        raise
    except Exception as exc:
        protocol_auth._reraise_control(exc)
        raise ProtocolPasswordSetupError("password_setup_sentinel_failed", "补密码安全令牌生成失败，尚未提交新密码",
            proxy_transport_failed=is_proxy_transport_failure(exc)) from None
    headers = {"openai-sentinel-token": token}
    if observer:
        headers["openai-sentinel-so-token"] = observer
    return headers


def _auth_post(session, path: str, payload: dict, *, referer: str, flow: str, checkpoint=None):
    headers = session.get_auth_headers(referer=referer)
    headers.update(_sentinel_headers(session, flow, checkpoint))
    headers["x-access-flow-invocation-id"] = str(uuid.uuid4())
    return _request(session, "post", _AUTH + path, headers=headers, data=json.dumps(payload), allow_redirects=False, checkpoint=checkpoint)


def _email_verification_context(session, email: str, *, referer: str, checkpoint=None) -> dict:
    """按当前客户端契约读取嵌套会话，只保留本轮发码需要的字段。"""
    headers = session.get_auth_headers(referer=referer)
    headers.pop("content-type", None)
    response = _request(session, "get", _AUTH + "/api/accounts/client_auth_session_dump",
        headers=headers, allow_redirects=False, checkpoint=checkpoint)
    payload = _payload(response)
    context = payload.get("client_auth_session")
    if not isinstance(context, dict):
        raise ProtocolPasswordSetupError("password_setup_otp_context_invalid", "补密码发码缺少有效的认证会话上下文")
    session_id, actual_email = context.get("session_id"), context.get("email")
    mode, pending = context.get("email_verification_mode"), context.get("passwordless_email_otp_send_pending")
    if (context.get("is_missing_session") is True or not isinstance(session_id, str) or not session_id
            or not isinstance(actual_email, str) or actual_email.strip().casefold() != email.strip().casefold()
            or "email_verification_mode" in context and not isinstance(mode, str)
            or "passwordless_email_otp_send_pending" in context and not isinstance(pending, bool)):
        raise ProtocolPasswordSetupError("password_setup_otp_context_invalid", "补密码发码会话尚未与目标账号对应")
    return {"session_id": session_id, "email": actual_email,
            **({"email_verification_mode": mode} if "email_verification_mode" in context else {}),
            "passwordless_email_otp_send_pending": pending}


def _send_email_verification_code(session, email: str, *, referer: str, after_ts: float, checkpoint=None) -> float:
    """执行验证页初发或明确重发，HTTP 页面跳转不作为发码回执。"""
    # 授权跳转前已记录时间锚点，兼容服务端或另一请求完成自动发码的情况。
    rotate = getattr(session, "rotate_document_navigation_id", None)
    if callable(rotate):
        rotate()
    context = _email_verification_context(session, email, referer=referer, checkpoint=checkpoint)
    pending = context["passwordless_email_otp_send_pending"] is True
    known_modes = {"passwordless_login", "passwordless_signup", "post_auth_email_verification", "post_signup", "resurrection_login"}
    raw_mode = context.get("email_verification_mode")
    mode_label = raw_mode if raw_mode in known_modes else "未提供" if "email_verification_mode" not in context else "其他"
    logger.info("[补密码] 发码上下文：来源=补密码，模式=%s，待发送=%s", mode_label, "是" if pending else "否")
    initial = pending and ("email_verification_mode" not in context
                           or context["email_verification_mode"] in {"passwordless_login", "passwordless_signup"})
    headers = session.get_auth_headers(referer=referer)
    headers.pop("content-type", None)
    if initial:
        logger.info("[补密码] 验证页存在待发送状态，正在准备本轮初发请求")
        headers.update(_sentinel_headers(session, "authorize_continue", checkpoint))
        current = _email_verification_context(session, email, referer=referer, checkpoint=checkpoint)
        if any(context.get(key) != current.get(key) or (key in context) != (key in current)
               for key in ("session_id", "email", "email_verification_mode")):
            raise ProtocolPasswordSetupError("password_setup_otp_context_changed", "补密码发码前认证会话发生变化，尚未发送验证码")
        if current["passwordless_email_otp_send_pending"] is not True:
            logger.info("[补密码] 待发送标记已清除，等待本轮邮件")
            return after_ts
        path, method_label = "/api/accounts/passwordless/send-otp", "初发"
    else:
        logger.info("[补密码] 验证页已有认证挑战，正在明确请求重发本轮验证码")
        headers.pop("openai-sentinel-token", None)
        headers.pop("openai-sentinel-so-token", None)
        path, method_label = "/api/accounts/email-otp/resend", "重发"
        # 明确重发会开启新的验证码窗口，不能读取授权阶段已到达的旧邮件。
        after_ts = time.time()
    headers["x-access-flow-invocation-id"] = str(uuid.uuid4())
    response = _request(session, "post", _AUTH + path, headers=headers, allow_redirects=False, checkpoint=checkpoint)
    status = int(getattr(response, "status_code", 0) or 0)
    if initial:
        data = _payload(response)
        page = data.get("page")
        payload = page.get("payload") if isinstance(page, dict) else None
        if (not isinstance(page, dict) or page.get("type") != "email_otp_verification"
                or isinstance(payload, dict) and payload.get("errors")):
            raise ProtocolPasswordSetupError("password_setup_otp_send_unconfirmed", "补密码初发未取得有效的发码回执")
    elif not 200 <= status < 300:
        if 300 <= status < 400:
            raise ProtocolPasswordSetupError("password_setup_otp_send_unconfirmed", "补密码重发未取得有效的发码回执")
        _payload(response)
    # 网页重发以 HTTP ok 为成功，允许空响应；初发必须取得明确验证页 JSON。
    logger.info("[补密码] 验证码%s请求已被接口接受，等待邮件到达", method_label)
    return after_ts


def _require_password_page(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.hostname == "auth.openai.com" and parsed.path.rstrip("/") == "/reset-password/new-password":
        return
    path = parsed.path.lower()
    if "mfa" in path:
        raise ProtocolPasswordSetupError("password_setup_mfa_secret_missing", "补密码重新验证需要 MFA，请先完成已有 MFA 登录")
    if path in {"/log-in", "/log-in/password", "/log-in-or-create-account"}:
        raise ProtocolPasswordSetupError("password_setup_session_expired", "补密码登录状态已失效，请重新登录后重试")
    raise ProtocolPasswordSetupError("password_setup_page_unexpected", "补密码流程未进入设置新密码页面")


def _continuation(data: dict) -> str:
    page = data.get("page") if isinstance(data.get("page"), dict) else {}
    payload = page.get("payload") if isinstance(page.get("payload"), dict) else {}
    return str(data.get("continue_url") or payload.get("url") or "")


def _is_mfa_page(url: str) -> bool:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    return parsed.hostname == "auth.openai.com" and (path == "/mfa-challenge" or path.startswith("/mfa-challenge/"))


def _verify_mfa(session, data: dict, url: str, secret: str, *, checkpoint=None) -> str:
    if not secret:
        raise ProtocolPasswordSetupError("password_setup_mfa_secret_missing", "补密码重新验证需要账号已有的 2FA 密钥")
    factor_id = protocol_auth._extract_factor_id(data, url)
    if not factor_id:
        raise ProtocolPasswordSetupError("password_setup_mfa_factor_missing", "补密码重新验证未返回有效的 2FA 挑战")
    logger.info("[补密码] 正在使用账号已有的 2FA 完成重新验证")
    headers = session.get_auth_headers(referer=url)
    headers.pop("openai-sentinel-token", None)
    headers.pop("openai-sentinel-so-token", None)
    _payload(_request(session, "post", _AUTH + "/api/accounts/mfa/issue_challenge",
        headers=headers, data=json.dumps({"id": factor_id, "type": "totp", "force_fresh_challenge": False}),
        allow_redirects=False, checkpoint=checkpoint))
    _check(checkpoint)
    try:
        code = protocol_auth._totp_code(secret)
    except protocol_auth.ProtocolV2AuthError:
        raise ProtocolPasswordSetupError("password_setup_mfa_secret_invalid", "账号已有的 2FA 密钥无法生成验证码") from None
    verified = _payload(_request(session, "post", _AUTH + "/api/accounts/mfa/verify",
        headers=headers, data=json.dumps({"id": factor_id, "type": "totp", "code": code}),
        allow_redirects=False, checkpoint=checkpoint))
    logger.info("[补密码] 2FA 重新验证已通过")
    return _trusted_url(_continuation(verified))


def _follow_password_page(session, url: str, *, referer: str, checkpoint=None) -> str:
    parsed = urlsplit(url)
    if parsed.hostname != "auth.openai.com" or parsed.path.rstrip("/") != "/authorize/continue":
        _require_password_page(url)
    landing = _follow(session, url, referer=referer, checkpoint=checkpoint)
    _require_password_page(landing)
    return landing


def _confirm_result(session, data: dict, *, checkpoint=None) -> None:
    page = data.get("page") if isinstance(data.get("page"), dict) else {}
    continuation = _continuation(data)
    if page.get("type") in _PENDING_TYPES or not continuation:
        raise ProtocolPasswordSetupError("password_setup_result_unconfirmed", "密码提交返回了未完成状态，请保留候选密码后核实", True)
    parsed = urlsplit(_trusted_url(continuation, unknown=True))
    query = parse_qs(parsed.query)
    callback = (parsed.hostname == "chatgpt.com" and parsed.path == "/api/auth/callback/openai"
                and bool(query.get("code")) and bool(query.get("state")) and not query.get("error"))
    if page.get("type") == "external_url" and callback:
        return
    allowed = (parsed.hostname == "auth.openai.com" and parsed.path.rstrip("/") == "/authorize/continue"
               or parsed.hostname == "chatgpt.com" and (callback or parsed.path == "/"))
    if allowed and not query.get("error"):
        try:
            landing = urlsplit(_follow(session, continuation, referer=_PASSWORD_PAGE, checkpoint=checkpoint, final=True))
        except ProtocolPasswordSetupError as exc:
            # 后续回调失败不能证明先前 password/add 未生效。
            exc.request_unknown = True
            raise
        if landing.hostname == "chatgpt.com" and landing.path == "/" and not parse_qs(landing.query).get("error"):
            return
    raise ProtocolPasswordSetupError("password_setup_result_unconfirmed", "密码提交尚未返回受信任的完成状态，请保留候选密码后核实", True)


def add_password(session, email: str, password: str, *, checkpoint=None, on_dispatched=None, on_confirmed=None,
                 otp_provider=None, totp_secret: str = "") -> dict:
    """复用已登录会话添加密码；回调均无参数，凭据仅用于当前请求。"""
    if not isinstance(email, str) or "@" not in email or not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ProtocolPasswordSetupError("password_setup_input_invalid", "补密码所需邮箱或新密码格式无效")
    if not all(re.search(pattern, password) for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")):
        raise ProtocolPasswordSetupError("password_setup_input_invalid", "新密码必须包含大小写字母、数字与符号")
    csrf = _payload(_request(session, "get", _CHATGPT + "/api/auth/csrf", headers=session.get_nextauth_headers(referer=_CHATGPT + "/"), checkpoint=checkpoint))
    if not isinstance(csrf.get("csrfToken"), str) or not csrf["csrfToken"]:
        raise ProtocolPasswordSetupError("password_setup_csrf_missing", "补密码流程未取得有效 CSRF 信息")
    signin_url = _CHATGPT + "/api/auth/signin/openai?" + urlencode({
        "connection": "password", "login_hint": email, "reauth": "password", "post_login_add_password": "true",
        "max_age": "0", "ext-oai-did": session.device_id,
    })
    headers = session.get_nextauth_headers(referer=_CHATGPT + "/")
    headers.update({"content-type": "application/x-www-form-urlencoded", "origin": _CHATGPT})
    signin = _payload(_request(session, "post", signin_url, headers=headers, data=urlencode({"callbackUrl": _CHATGPT + "/", "csrfToken": csrf["csrfToken"], "json": "true"}), allow_redirects=False, checkpoint=checkpoint))
    authorize_url = _trusted_url(signin.get("url"))
    _check(checkpoint)
    otp_after_ts = time.time()
    landing = _follow(session, authorize_url, referer=_CHATGPT + "/", checkpoint=checkpoint)
    verification = {}
    if urlsplit(landing).hostname == "auth.openai.com" and urlsplit(landing).path.rstrip("/") == "/email-verification":
        _check(checkpoint)
        requested_at = _send_email_verification_code(session, email, referer=landing, after_ts=otp_after_ts, checkpoint=checkpoint)
        sent_to = landing
        try:
            # 仅补密码采用较长的分段和网络余量，保留原线程取消/租约检查。
            with use_cooperative_wait(checkpoint or (lambda: None), poll_seconds=5, request_timeout=10):
                if otp_provider is not None:
                    otp = otp_provider(email, after_ts=requested_at)
                else:
                    source = email_provider.resolve_email_source(email, fallback=False)
                    otp = email_provider.wait_for_otp(email, after_ts=requested_at, email_source=source)
        except _CONTROL_ERRORS:
            raise
        except Exception:
            raise ProtocolPasswordSetupError("password_setup_otp_unavailable", "未能取得本轮补密码邮箱验证码") from None
        if not re.fullmatch(r"\d{6}", str(otp or "")):
            raise ProtocolPasswordSetupError("password_setup_otp_invalid", "补密码邮箱验证码格式无效")
        verification = _payload(_auth_post(session, "/api/accounts/email-otp/validate", {"code": str(otp)}, referer=sent_to, flow="email_otp_validate", checkpoint=checkpoint))
        next_url = _trusted_url(_continuation(verification))
        if _is_mfa_page(next_url):
            next_url = _verify_mfa(session, verification, next_url, totp_secret, checkpoint=checkpoint)
        landing = _follow_password_page(session, next_url, referer=sent_to, checkpoint=checkpoint)
    elif _is_mfa_page(landing):
        next_url = _verify_mfa(session, verification, landing, totp_secret, checkpoint=checkpoint)
        landing = _follow_password_page(session, next_url, referer=landing, checkpoint=checkpoint)
    _require_password_page(landing)
    headers = session.get_auth_headers(referer=landing)
    headers.update(_sentinel_headers(session, "password_reset", checkpoint))
    headers["x-access-flow-invocation-id"] = str(uuid.uuid4())
    _check(checkpoint)
    circuit_check = getattr(session, "_raise_if_circuit_open", None)
    if callable(circuit_check):
        try:
            circuit_check()
        except Exception:
            raise ProtocolPasswordSetupError("password_setup_session_cooling_down", "当前会话正在安全冷却，尚未提交新密码") from None
    if on_dispatched is not None:
        on_dispatched()
    response = _request(session, "post", _AUTH + "/api/accounts/password/add", headers=headers, data=json.dumps({"password": password}), allow_redirects=False, final=True)
    result = _payload(response, final=True)
    _confirm_result(session, result, checkpoint=checkpoint)
    if on_confirmed is not None:
        on_confirmed()
    _check(checkpoint)
    return {"ok": True, "status": "success", "password_added": True}
