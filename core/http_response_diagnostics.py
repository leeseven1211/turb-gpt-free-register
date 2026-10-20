"""认证失败的响应头白名单与保守归因，不保存凭据或任意头值。"""
from __future__ import annotations

from collections.abc import Mapping
from email.utils import format_datetime, parsedate_to_datetime
import json
import re
from urllib.parse import urlsplit


_SERVERS = frozenset({"cloudflare", "nginx", "envoy", "caddy", "awselb/2.0", "amazons3"})
_CONTENT_TYPES = frozenset({
    "text/html", "text/plain", "application/json", "application/problem+json", "application/xhtml+xml",
})
_RAY = re.compile(r"[0-9a-fA-F]{16,32}(?:-[A-Z]{3})?")
_HTTP_DATE = re.compile(r"[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT")
_AUTH_ERROR_LIMIT = 64 * 1024
_AUTH_ERROR_CODES = {
    "invalid_auth_step": "auth_state", "invalid_state": "auth_state", "missing_session": "auth_state",
    "session_expired": "auth_state", "session_not_found": "auth_state",
    "email_taken": "email_conflict", "email_exists": "email_conflict",
    "user_already_exists": "email_conflict", "account_exists": "email_conflict",
    "account_already_exists": "email_conflict", "identifier_already_exists": "email_conflict",
    "invalid_email": "email_rejected", "email_not_allowed": "email_rejected",
    "unsupported_email": "email_rejected", "email_domain_not_allowed": "email_rejected",
    "signup_disallowed": "signup_rejected", "registration_disallowed": "signup_rejected",
    "signup_blocked": "signup_rejected", "account_create_rejected": "signup_rejected",
    "invalid_birthday": "profile_invalid", "invalid_birthdate": "profile_invalid",
    "invalid_age": "profile_invalid", "invalid_name": "profile_invalid",
    "invalid_request": "request_invalid", "validation_error": "request_invalid",
    "invalid_request_error": "request_invalid", "invalid_password": "credentials_rejected",
    "incorrect_password": "credentials_rejected", "invalid_otp": "otp_rejected",
    "otp_expired": "otp_rejected", "invalid_grant": "credentials_rejected",
    "rate_limit_exceeded": "rate_limited", "too_many_requests": "rate_limited",
    "account_deactivated": "account_unusable", "account_suspended": "account_unusable",
    "unsupported_country": "region_rejected", "access_denied": "request_rejected",
    "unknown": "unknown",
}
_AUTH_ERROR_TYPES = frozenset({
    "invalid_request_error", "authentication_error", "permission_error", "rate_limit_error",
    "server_error", "api_error", "invalid_request", "access_denied", "unknown",
})


def auth_submission_endpoint(url: object) -> str:
    """只把可信认证源的固定 API 路由关联到提交动作，不用路径子串猜测。"""
    try:
        parsed = urlsplit(str(url or ""))
        if (parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username or parsed.password):
            return ""
    except (TypeError, ValueError):
        return ""
    path = parsed.path
    if parsed.hostname in {"chatgpt.com", "chat.openai.com"}:
        if path == "/api/auth/csrf":
            return "nextauth_csrf"
        if path in {"/api/auth/signin/openai", "/api/auth/signin/auth0"}:
            return "nextauth_signin"
        return ""
    if parsed.hostname != "auth.openai.com":
        return ""
    return {
        "/api/accounts/authorize": "email_submit",
        "/api/accounts/password": "password_submit",
        "/api/accounts/password/verify": "password_submit",
        "/api/accounts/user/register": "password_submit",
        "/api/accounts/email-otp/validate": "otp_submit",
        "/api/accounts/email-otp/verify": "otp_submit",
        "/api/accounts/email-otp/send": "otp_resend",
        "/api/accounts/email-otp/resend": "otp_resend",
        "/api/accounts/passwordless/send-otp": "otp_resend",
        "/api/accounts/create_account": "profile_submit",
    }.get(path, "")


def safe_auth_error(value: object) -> dict[str, str]:
    """错误码也采用固定白名单；任意消息、未知码和请求内容均不能透传。"""
    if not isinstance(value, Mapping) or not any(key in value for key in ("code", "type")):
        return {}
    code, error_type = value.get("code"), value.get("type")
    code = code if isinstance(code, str) and code in _AUTH_ERROR_CODES else "unknown"
    error_type = error_type if isinstance(error_type, str) and error_type in _AUTH_ERROR_TYPES else "unknown"
    return {"code": code, "type": error_type, "category": _AUTH_ERROR_CODES[code]}


def is_auth_session_diagnostic(url: object) -> bool:
    """会话诊断 GET 不属于业务提交，单独限定来源与固定路由。"""
    try:
        parsed = urlsplit(str(url or ""))
        return (parsed.scheme == "https" and parsed.hostname == "auth.openai.com"
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and parsed.path == "/api/accounts/client_auth_session_dump")
    except (TypeError, ValueError):
        return False


def auth_error_from_body(body: object) -> dict[str, str]:
    """有限解析认证失败 JSON，只返回结构化固定枚举，不返回原始正文。"""
    if isinstance(body, bytes):
        if len(body) > _AUTH_ERROR_LIMIT:
            return {}
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    if not isinstance(body, str) or len(body) > _AUTH_ERROR_LIMIT:
        return {}
    try:
        if len(body.encode("utf-8")) > _AUTH_ERROR_LIMIT:
            return {}
    except UnicodeEncodeError:
        return {}

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("认证错误 JSON 包含重复字段")
            result[key] = value
        return result

    try:
        payload = json.loads(body, object_pairs_hook=unique_object)
    except (ValueError, TypeError, RecursionError):
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return safe_auth_error(payload.get("error"))


def safe_response_headers(headers: object) -> dict[str, str]:
    """头名和值均受约束；未知服务只记为其他，不透传私有字符串。"""
    if not isinstance(headers, Mapping):
        return {}
    safe = {}
    for name, raw in headers.items():
        if not isinstance(name, str) or not isinstance(raw, str):
            continue
        if len(raw) > 256 or "\r" in raw or "\n" in raw:
            continue
        name, value = name.strip().lower(), raw.strip()
        if name == "server":
            safe[name] = value.lower() if value.lower() in _SERVERS else "其他"
        elif name == "cf-mitigated" and value.lower() == "challenge":
            safe[name] = "challenge"
        elif name == "cf-ray" and _RAY.fullmatch(value):
            safe[name] = value
        elif name == "content-type":
            mime = value.split(";", 1)[0].strip().lower()
            if mime in _CONTENT_TYPES:
                safe[name] = mime
        elif name == "retry-after":
            if re.fullmatch(r"[0-9]{1,9}", value):
                safe[name] = value
            elif _HTTP_DATE.fullmatch(value):
                try:
                    safe[name] = format_datetime(parsedate_to_datetime(value), usegmt=True)
                except (TypeError, ValueError, OverflowError):
                    pass
    return safe


def response_rejection_diagnostic(status: object, headers: Mapping) -> dict[str, str]:
    """CF 经过标志不能证明挑战，更不能证明代理 IP 不可用。"""
    if status != 403:
        return {}
    if headers.get("cf-mitigated") == "challenge":
        return {"kind": "cloudflare_challenge", "label": "检测到 Cloudflare 挑战"}
    if headers.get("server") == "cloudflare" or headers.get("cf-ray"):
        return {"kind": "cloudflare_unconfirmed", "label": "请求经过 Cloudflare，拒绝原因未确认"}
    return {"kind": "http_403_unconfirmed", "label": "HTTP 403，拒绝来源与原因未确认"}
