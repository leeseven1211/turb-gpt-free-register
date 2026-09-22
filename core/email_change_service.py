# -*- coding: utf-8 -*-
"""Durable protocol-only ChatGPT email-change operation."""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping

from core import email_provider
from core.account_proxy import acquire_account_proxy
from core.operation_runtime import OperationCancelled
from core.operations import task_gateway
from core.storage import accounts as db
from core.storage import operation as operation_store

if TYPE_CHECKING:
    from core.session import BrowserSession

logger = logging.getLogger(__name__)

EMAIL_CHANGE_TASK_TYPE = "email_change"
EMAIL_CHANGE_SOURCE_SYSTEM = "native_operations"
EMAIL_CHANGE_RESOURCE_FAMILY = "openai_interactive"
EMAIL_CHANGE_LIVE_RESOURCE_FAMILY = "email_change_live_check"

EMAIL_CHANGE_CONFIG_ALLOWLIST = {
    "email_change_enabled": "ACCOUNT_EMAIL_CHANGE_ENABLED",
    "email_change_proxy_mode": "ACCOUNT_EMAIL_CHANGE_PROXY_MODE",
    "auth_profile_mode": "ACCOUNT_AUTH_PROFILE_MODE",
    "protocol_version": "OPENAI_PROTOCOL_VERSION",
}


def _config_snapshot():
    from config.schema import get_config_snapshot

    return get_config_snapshot()


def _email_change_min_account_age_hours() -> int:
    from config import account as account_config

    try:
        return max(0, min(int(account_config.ACCOUNT_EMAIL_CHANGE_MIN_ACCOUNT_AGE_HOURS or 0), 8760))
    except (TypeError, ValueError):
        return 168


def _account_age_gate_error(account: Mapping[str, Any]) -> str:
    """Reject only parseable, clearly too-new accounts before leasing a mailbox."""
    minimum_hours = _email_change_min_account_age_hours()
    if minimum_hours <= 0:
        return ""
    raw_created_at = account.get("created_at")
    if isinstance(raw_created_at, datetime):
        created_at = raw_created_at
    else:
        try:
            created_at = datetime.fromisoformat(str(raw_created_at or "").strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return ""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds()
    if age_seconds >= minimum_hours * 3600:
        return ""
    return f"账号注册时间不足 {minimum_hours} 小时，暂不提交邮箱换绑"


def _safe_local_failure_message(stage: str, exc: BaseException) -> str:
    """Keep task errors actionable without copying supplier paths or mailbox addresses."""
    raw = str(exc or "")
    if "EmailButler" in raw or "email_butler" in raw:
        category = "Email Butler 领取失败"
    elif "邮箱池" in raw or "邮箱来源" in raw:
        category = "邮箱来源领取失败"
    else:
        category = type(exc).__name__
    match = re.search(r"\bHTTP\s+([1-5]\d{2})\b", raw, flags=re.IGNORECASE)
    status_suffix = f"（HTTP {match.group(1)}）" if match else ""
    return f"{str(stage or '邮箱换绑失败')}: {category}{status_suffix}"


class _RemoteRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        remote_error_code: str | None = None,
        response_content_type: str | None = None,
        response_server: str | None = None,
        cf_mitigated: bool = False,
        cf_ray_present: bool = False,
        response_error_shape: str | None = None,
        response_error_hints: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = int(http_status) if http_status is not None else None
        self.remote_error_code = str(remote_error_code or "").strip() or None
        self.response_content_type = str(response_content_type or "").strip() or None
        self.response_server = str(response_server or "").strip() or None
        self.cf_mitigated = bool(cf_mitigated)
        self.cf_ray_present = bool(cf_ray_present)
        self.response_error_shape = str(response_error_shape or "").strip() or None
        self.response_error_hints = tuple(
            hint for hint in response_error_hints or ()
            if hint in {
                "account", "already_in_use", "domain", "email", "invalid", "not_allowed",
                "not_supported", "phone", "rate_limit", "too_new", "verification",
            }
        )


class RemoteRequestRejected(_RemoteRequestError):
    """The remote endpoint returned an explicit, safe rejection."""

    remote_response_observed = True


class RemoteRequestUnknown(_RemoteRequestError):
    """The transport result crossed a write boundary but is not known."""

    request_unknown = True


@dataclass(frozen=True)
class BeginChangeResult:
    session: BrowserSession
    access_token: str
    after_ts: float
    reauthenticated: bool = False


class EmailChangeProtocol:
    """The public change_email begin/verify HTTP contract.

    These methods deliberately do not retry.  The caller records a durable
    intent immediately before each call and decides whether the response is a
    safe rejection or an unknown remote result.
    """

    _BASE_URL = "https://chatgpt.com"

    @staticmethod
    def _response_payload(response: Any) -> Any:
        try:
            return response.json()
        except Exception:
            return None

    @staticmethod
    def _response_error_shape(response: Any) -> str:
        """Return only a fixed structural label for a rejected JSON response."""
        payload = EmailChangeProtocol._response_payload(response)
        if not isinstance(payload, dict):
            return ""
        for key in ("error", "errors", "detail"):
            value = payload.get(key)
            if isinstance(value, dict):
                return f"object.{key}_object"
            if isinstance(value, list):
                return f"object.{key}_list"
            if isinstance(value, str):
                return f"object.{key}_string"
        if any(key in payload for key in ("message", "msg", "code", "error_code")):
            return "object.standard_error_fields"
        return "object.unclassified"

    @staticmethod
    def _safe_error_hints(value: Any) -> tuple[str, ...]:
        text = str(value or "").strip().lower()
        if not text:
            return ()
        hints: set[str] = set()
        if "email" in text:
            hints.add("email")
        if "domain" in text:
            hints.add("domain")
        if "account" in text:
            hints.add("account")
        if any(marker in text for marker in (
            "not allowed", "cannot be used", "can't be used", "not eligible", "forbidden",
            "blocked", "prohibited", "policy",
        )):
            hints.add("not_allowed")
        if "not supported" in text:
            hints.add("not_supported")
        if "already" in text and any(marker in text for marker in ("used", "exists", "registered")):
            hints.add("already_in_use")
        if any(marker in text for marker in ("invalid", "malformed", "format", "valid email")):
            hints.add("invalid")
        if any(marker in text for marker in ("verify", "verification")):
            hints.add("verification")
        if "phone" in text:
            hints.add("phone")
        if any(marker in text for marker in ("too many", "rate limit", "rate-limit")):
            hints.add("rate_limit")
        if any(marker in text for marker in ("too new", "too recent", "not old enough")):
            hints.add("too_new")
        return tuple(sorted(hints))

    @staticmethod
    def _error_code_from_hints(hints: tuple[str, ...]) -> str:
        hint_set = set(hints)
        if {"email", "domain", "not_allowed"}.issubset(hint_set):
            return "email_domain_rejected"
        if {"email", "already_in_use"}.issubset(hint_set):
            return "email_already_in_use"
        if {"email", "invalid"}.issubset(hint_set):
            return "invalid_email"
        if {"account", "too_new"}.issubset(hint_set):
            return "email_change_account_too_new"
        if "email" in hint_set and "not_supported" in hint_set:
            return "email_change_not_supported"
        if "email" in hint_set and "verification" in hint_set:
            return "email_change_verification_required"
        if "email" in hint_set and "not_allowed" in hint_set:
            return "email_change_not_allowed"
        if "rate_limit" in hint_set:
            return "email_change_rate_limited"
        return ""

    @classmethod
    def _response_error_hints(cls, response: Any) -> tuple[str, ...]:
        payload = cls._response_payload(response)
        values: list[str] = []

        def collect(value: Any, depth: int = 0) -> None:
            if depth > 4 or len(values) >= 40:
                return
            if isinstance(value, dict):
                for item in value.values():
                    collect(item, depth + 1)
            elif isinstance(value, (list, tuple)):
                for item in value[:20]:
                    collect(item, depth + 1)
            elif isinstance(value, str):
                values.append(value)

        collect(payload)
        return tuple(sorted({hint for value in values for hint in cls._safe_error_hints(value)}))

    @staticmethod
    def _safe_error_code(value: Any) -> str:
        raw_code = str(value or "").strip()
        if not raw_code or len(raw_code) > 120:
            return ""
        if all(char.isalnum() or char in "._:-" for char in raw_code):
            return raw_code
        return EmailChangeProtocol._error_code_from_hints(
            EmailChangeProtocol._safe_error_hints(raw_code)
        )

    @classmethod
    def _response_error_code(cls, response: Any) -> str:
        payload = cls._response_payload(response)
        if not isinstance(payload, dict):
            return ""

        codes: list[Any] = [payload.get("code"), payload.get("error_code")]
        messages: list[Any] = []
        types: list[Any] = []

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                codes.extend((value.get("code"), value.get("error_code")))
                messages.extend((value.get("message"), value.get("msg")))
                types.append(value.get("type"))
                nested = value.get("detail")
                if nested is not None:
                    collect(nested)
            elif isinstance(value, list):
                for item in value[:5]:
                    collect(item)
            elif isinstance(value, str):
                messages.append(value)

        collect(payload.get("error"))
        collect(payload.get("detail"))
        for candidate in [*codes, *messages, *types]:
            error_code = cls._safe_error_code(candidate)
            if error_code:
                return error_code
        return cls._error_code_from_hints(cls._response_error_hints(response))

    @staticmethod
    def _safe_response_metadata(response: Any) -> dict[str, Any]:
        raw_headers = getattr(response, "headers", None) or {}
        headers = {str(key).lower(): str(value) for key, value in raw_headers.items()}
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if len(content_type) > 80 or not all(
            char.isalnum() or char in ".+-/" for char in content_type
        ):
            content_type = ""
        server = headers.get("server", "").strip().lower()
        if len(server) > 80 or not all(
            char.isalnum() or char in " ._+-/" for char in server
        ):
            server = ""
        return {
            "response_content_type": content_type or None,
            "response_server": server or None,
            "cf_mitigated": bool(headers.get("cf-mitigated")),
            "cf_ray_present": bool(headers.get("cf-ray")),
        }

    def _post(self, session: BrowserSession, path: str, access_token: str, payload: dict) -> dict:
        headers = dict(session.get_chatgpt_headers(referer="https://chatgpt.com/") or {})
        token = str(access_token or "").strip()
        headers.update({
            "authorization": f"Bearer {token}",
            "oai-device-id": str(getattr(session, "device_id", "") or ""),
            "oai-language": str(session.navigator_language() or "en-US"),
            "origin": "https://chatgpt.com",
            "content-type": "application/json",
        })
        # Modern ChatGPT account endpoints resolve the selected account from
        # the same JWT-derived header used by plan/quota requests.  Omitting it
        # can leave a freshly authenticated multi-account session without an
        # explicit account context and the edge responds with a bare 403.
        from core.chatgpt_plan import token_claims

        account_id = str(token_claims(token).get("account_id") or "").strip()
        if account_id:
            headers["chatgpt-account-id"] = account_id
        response = session.post(
            f"{self._BASE_URL}{path}",
            headers=headers,
            data=json.dumps(payload, separators=(",", ":")),
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code != 200:
            error_code = self._response_error_code(response)
            response_meta = {
                **self._safe_response_metadata(response),
                "response_error_shape": self._response_error_shape(response),
                "response_error_hints": self._response_error_hints(response),
            }
            suffix = f" ({error_code})" if error_code else ""
            if status_code == 408 or status_code == 429 or status_code >= 500:
                raise RemoteRequestUnknown(
                    f"{path} 返回 {status_code}{suffix}，远端结果待确认",
                    http_status=status_code,
                    remote_error_code=error_code,
                    **response_meta,
                )
            raise RemoteRequestRejected(
                f"{path} 返回 {status_code}{suffix}",
                http_status=status_code,
                remote_error_code=error_code,
                **response_meta,
            )
        try:
            result = response.json()
        except Exception as exc:
            raise RemoteRequestUnknown(
                f"{path} 返回不是 JSON，远端结果待确认",
                http_status=status_code,
                remote_error_code="invalid_json",
            ) from exc
        if not isinstance(result, dict):
            raise RemoteRequestUnknown(
                f"{path} 返回格式异常，远端结果待确认",
                http_status=status_code,
                remote_error_code="invalid_response_shape",
            )
        if not result.get("success"):
            error_code = self._response_error_code(response) or "remote_rejected"
            raise RemoteRequestRejected(
                f"{path} 返回失败 ({error_code})",
                http_status=status_code,
                remote_error_code=error_code,
                response_error_shape=self._response_error_shape(response),
                response_error_hints=self._response_error_hints(response),
            )
        return result

    def begin(self, session: BrowserSession, access_token: str, new_email: str) -> dict:
        return self._post(
            session,
            "/backend-api/accounts/change_email/begin",
            access_token,
            {"email": str(new_email or "").strip()},
        )

    def verify(self, session: BrowserSession, access_token: str, new_email: str, code: str) -> dict:
        return self._post(
            session,
            "/backend-api/accounts/change_email/verify",
            access_token,
            {"email": str(new_email or "").strip(), "code": str(code or "").strip()},
        )


def _is_reauth_required(exc: BaseException) -> bool:
    # The change-email begin endpoint uses a bare 401 for an expired or stale
    # authenticated session.  It is safe to recover here because this helper
    # is only called for the initial begin request, before a new-email write
    # has been accepted; the verify request never enters this branch.
    if isinstance(exc, RemoteRequestRejected) and int(getattr(exc, "http_status", 0) or 0) == 401:
        return True
    error_code = str(getattr(exc, "remote_error_code", "") or "").strip().lower()
    normalized_code = error_code.replace("-", "_").replace(" ", "_")
    if normalized_code in {"reauth_required", "recent_login_required", "step_up_required"}:
        return True
    text = str(exc or "").strip().lower()
    normalized_text = text.replace("-", "_")
    return any(marker in normalized_text for marker in (
        "reauth_required",
        "recent_login_required",
        "recent login required",
        "step_up_required",
    ))


def _safe_remote_error_detail(exc: BaseException) -> dict[str, Any]:
    detail: dict[str, Any] = {}
    http_status = getattr(exc, "http_status", None)
    if http_status is not None:
        detail["http_status"] = int(http_status)
    error_code = str(getattr(exc, "remote_error_code", "") or "").strip()
    if error_code:
        detail["remote_error_code"] = error_code[:120]
    content_type = str(getattr(exc, "response_content_type", "") or "").strip()
    if content_type:
        detail["response_content_type"] = content_type[:80]
    server = str(getattr(exc, "response_server", "") or "").strip()
    if server:
        detail["response_server"] = server[:80]
    response_error_shape = str(getattr(exc, "response_error_shape", "") or "").strip()
    if response_error_shape:
        detail["response_error_shape"] = response_error_shape[:80]
    response_error_hints = tuple(getattr(exc, "response_error_hints", ()) or ())
    if response_error_hints:
        detail["response_error_hints"] = list(response_error_hints[:12])
    if bool(getattr(exc, "cf_mitigated", False)):
        detail["cf_mitigated"] = True
    if bool(getattr(exc, "cf_ray_present", False)):
        detail["cf_ray_present"] = True
    return detail


def _access_token(value: Mapping[str, Any] | None) -> str:
    data = value if isinstance(value, Mapping) else {}
    return str(data.get("access_token") or data.get("accessToken") or "").strip()


def _remote_request_id(context, phase: str) -> str:
    return f"email-change:{int(context.run_id)}:{phase}:{uuid.uuid4().hex}"


def _record_begin_success_receipt(context, *, request_id: str | None) -> None:
    """Persist a successful begin response without downgrading it to failure.

    Once ``begin`` returned successfully, losing the lease or failing the local
    receipt write makes the remote state unknown.  The caller must retain the
    allocated mailbox for reconciliation instead of releasing it for reuse.
    """
    if context is None:
        return
    try:
        context.remote_request_receipt(
            outcome="response_received",
            action="change_email.begin",
            request_id=request_id,
            detail={
                "response_observed": True,
                "remote_result_confirmed": True,
                "phase_complete": True,
            },
        )
    except Exception as exc:
        raise RemoteRequestUnknown("begin 已成功但本地回执未确认") from exc


def begin_change_with_optional_reauth(
    session: BrowserSession,
    *,
    account_id: int,
    current_email: str,
    current_source: str,
    new_email: str,
    access_token: str,
    context=None,
) -> BeginChangeResult:
    """Try begin once, then perform one explicit Recent Login if required."""
    protocol = EmailChangeProtocol()
    token = str(access_token or "").strip()
    after_ts = time.time()
    first_request_id = _remote_request_id(context, "begin") if context is not None else None
    if context is not None:
        context.remote_request_started(
            "change_email.begin",
            request_id=first_request_id,
            detail={"account_id": int(account_id), "phase": "initial"},
        )
    try:
        protocol.begin(session, token, new_email)
    except task_gateway.OperationLeaseLost:
        raise
    except Exception as exc:
        if not _is_reauth_required(exc):
            if context is not None:
                context.remote_request_receipt(
                    outcome="rejected" if isinstance(exc, RemoteRequestRejected) else "unknown",
                    action="change_email.begin",
                    request_id=first_request_id,
                    detail={
                        "response_observed": isinstance(exc, RemoteRequestRejected),
                        "reauth_required": False,
                        "exception_type": type(exc).__name__,
                        **_safe_remote_error_detail(exc),
                    },
                )
                if not isinstance(exc, RemoteRequestRejected):
                    raise RemoteRequestUnknown("begin 请求结果待确认") from exc
            raise

        if context is not None:
            context.remote_request_receipt(
                outcome="rejected",
                action="change_email.begin",
                request_id=first_request_id,
                detail={
                    "response_observed": True,
                    "reauth_required": True,
                    **_safe_remote_error_detail(exc),
                },
            )
            context.report(
                stage="login_password",
                state="running",
                message="服务端要求 Recent Login，验证当前邮箱",
            )
        try:
            recent = perform_recent_login(
                session,
                email=current_email,
                email_source=current_source,
                access_token=token,
            )
        except task_gateway.OperationLeaseLost:
            raise
        except Exception as recent_exc:
            # The first begin was explicitly rejected; Recent Login has not
            # crossed the email-change write boundary.
            raise RemoteRequestRejected(
                f"Recent Login 失败: {type(recent_exc).__name__}"
            ) from recent_exc
        token = _access_token(recent)
        if not token:
            raise RemoteRequestRejected("Recent Login 未返回新的 access_token")
        recent_session = recent.get("protocol_session") if isinstance(recent, Mapping) else None
        if recent_session is None:
            raise RemoteRequestRejected("Recent Login 未返回新的协议会话")
        session = recent_session
        after_ts = time.time()
        second_request_id = _remote_request_id(context, "begin-reauth") if context is not None else None
        if context is not None:
            context.remote_request_started(
                "change_email.begin",
                request_id=second_request_id,
                detail={"account_id": int(account_id), "phase": "recent_login"},
            )
        try:
            protocol.begin(session, token, new_email)
        except task_gateway.OperationLeaseLost:
            raise
        except RemoteRequestRejected as second_exc:
            if context is not None:
                context.remote_request_receipt(
                    outcome="rejected",
                    action="change_email.begin",
                    request_id=second_request_id,
                    detail={
                        "response_observed": True,
                        "phase": "recent_login",
                        **_safe_remote_error_detail(second_exc),
                    },
                )
            raise
        except Exception as second_exc:
            if context is not None:
                context.remote_request_receipt(
                    outcome="unknown",
                    action="change_email.begin",
                    request_id=second_request_id,
                    detail={
                        "response_observed": False,
                        "phase": "recent_login",
                        **_safe_remote_error_detail(second_exc),
                    },
                )
                raise RemoteRequestUnknown("begin 重认证后请求结果待确认") from second_exc
            raise
        _record_begin_success_receipt(context, request_id=second_request_id)
        return BeginChangeResult(session, token, after_ts, True)
    _record_begin_success_receipt(context, request_id=first_request_id)
    return BeginChangeResult(session, token, after_ts, False)


def perform_recent_login(*args, **kwargs):
    """Lazy adapter to keep protocol imports patchable and cycle-free."""
    from core.account_liveness import perform_recent_login as _perform_recent_login

    return _perform_recent_login(*args, **kwargs)


def _captured_proxy_source(snapshot: Mapping[str, Any] | None) -> str | None:
    value = snapshot.get("email_change_proxy_mode") if isinstance(snapshot, Mapping) else None
    if value:
        return str(value).strip().lower()
    try:
        from core.account_proxy import account_action_proxy_mode

        return str(account_action_proxy_mode("email-change") or "").strip() or None
    except Exception:
        logger.exception("读取邮箱换绑代理来源失败")
        return None


def _account_stable_identity(account_id: int):
    from core.storage.account_auth import ensure_account_protocol_identity

    return ensure_account_protocol_identity(int(account_id))


def _safe_readback(account_id: int, email: str, source: str, access_token: str) -> bool:
    account = db.get_account(int(account_id)) or {}
    return bool(
        str(account.get("email") or "").strip().lower() == str(email or "").strip().lower()
        and str(account.get("email_source") or "").strip().lower() == str(source or "").strip().lower()
        and str(account.get("access_token") or "").strip() == str(access_token or "").strip()
    )


def _release_unconsumed(email: str, account_id: int, error: str) -> None:
    if not email:
        return
    try:
        email_provider.release_email_if_unconsumed(
            email, note=f"账号 #{int(account_id)} 邮箱换绑失败: {str(error)[:240]}"
        )
    except Exception:
        logger.exception("邮箱换绑失败邮箱回收异常: account_id=%s", account_id)


def _close_protocol_session(session: BrowserSession | None) -> None:
    if session is None:
        return
    try:
        transport = getattr(session, "session", None)
        close = getattr(transport, "close", None)
        if callable(close):
            close()
    except Exception:
        logger.debug("关闭邮箱换绑协议会话失败", exc_info=True)


def _enqueue_live_check_child(context, account_id: int, email: str) -> dict[str, Any]:
    from core import live_check_service

    result = live_check_service.enqueue_account_live_check(
        account_id=int(account_id),
        email=str(email),
        trigger="email_change_auto",
        force_refresh=True,
        idempotency_key=f"email-change-live:{int(context.task_id)}",
        # The child handler acquires the normal openai_interactive account
        # lease. Its durable run uses a distinct family so it can be created
        # before the parent attempt is terminalized; the parent lease is
        # already released when this function is called.
        resource_family=EMAIL_CHANGE_LIVE_RESOURCE_FAMILY,
    )
    if result.get("accepted") and result.get("task_id"):
        parent = operation_store.get_task(int(context.task_id), include_events=False) or {}
        child_source_id = result.get("source_id") or result.get("task_id")
        parent_source_id = parent.get("source_id") or context.task_id
        if child_source_id:
            try:
                operation_store.register_task_dependency(
                    parent_source_system=EMAIL_CHANGE_SOURCE_SYSTEM,
                    parent_source_id=str(parent_source_id),
                    child_source_system=str(result.get("source_system") or EMAIL_CHANGE_SOURCE_SYSTEM),
                    child_source_id=str(child_source_id),
                    dependency_type="email_change_live_check",
                    payload={"account_id": int(account_id), "purpose": "post_email_change_at"},
                )
                result["dependency_registered"] = True
            except Exception as exc:
                # The child is already durable and has its own account lease;
                # preserve the confirmed parent while surfacing the handoff
                # problem for task-center follow-up.
                logger.exception("邮箱换绑查活依赖登记失败: account_id=%s", account_id)
                result["dependency_registered"] = False
                result["dependency_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return result


def _handle_email_change(context):
    if context.account_id is None:
        return task_gateway.OperationResult.failed("邮箱换绑缺少账号")
    data = context.run.get("data") if isinstance(context.run.get("data"), dict) else {}
    snapshot = context.config_snapshot if isinstance(context.config_snapshot, Mapping) else {}
    if snapshot.get("email_change_enabled") is False:
        return task_gateway.OperationResult.failed("协议邮箱换绑已被配置关闭")
    account_id = int(context.account_id)
    account = db.get_account(account_id)
    if not account:
        return task_gateway.OperationResult.failed("账号不存在")
    current_email = str(account.get("email") or context.email or "").strip()
    token = str(account.get("access_token") or "").strip()
    if not current_email or not token:
        return task_gateway.OperationResult.failed("账号缺少当前邮箱或 access_token")
    try:
        source = email_provider.validate_email_source(data.get("email_source") or "")
    except ValueError as exc:
        return task_gateway.OperationResult.failed(str(exc))
    try:
        from core import browser_traffic

        browser_traffic.record_unavailable(
            summary_key=f"email-change-protocol:{int(context.run_id)}",
            source="email_change",
            method="protocol",
            reason="protocol_no_browser_observation",
            account_id=account_id,
            purpose="email_change",
            operation_task_id=int(context.task_id),
            operation_run_id=int(context.run_id),
        )
    except Exception:
        logger.exception("邮箱换绑协议流量标记写入失败；业务流程继续: account_id=%s", account_id)
    new_email = ""
    route = None
    session = None
    account_claimed = False
    remote_accepted = False
    writeback_confirmed = False
    context.report(stage="email", state="running", message="准备新邮箱")
    try:
        with context.lease(resource_family=EMAIL_CHANGE_RESOURCE_FAMILY):
            context.checkpoint()
            if not db.claim_account_email_change(account_id, source, str(context.run.get("trigger") or "manual")):
                return task_gateway.OperationResult.failed("账号已有邮箱换绑状态")
            account_claimed = True
            new_email = str(email_provider.acquire_email(source) or "").strip()
            if not new_email:
                return task_gateway.OperationResult.failed("邮箱池未返回新邮箱")
            if new_email.lower() == current_email.lower():
                _release_unconsumed(new_email, account_id, "新邮箱与当前邮箱相同")
                return task_gateway.OperationResult.failed("领取到的邮箱与当前邮箱相同")
            db.mark_account_email_change_running(account_id, new_email, source=source)
            context.report(stage="network", state="running", message="分配邮箱换绑线路")
            route = acquire_account_proxy(
                account_id=account_id,
                email=current_email,
                purpose="email-change",
                source=str(
                    data.get("proxy_source")
                    or _captured_proxy_source(snapshot)
                    or ""
                ).strip() or None,
            )
            context.report(stage="network", state="success", message="邮箱换绑线路已就绪", detail=route.public_dict())
            identity = _account_stable_identity(account_id)
            from core.session import BrowserSession

            session = BrowserSession(
                proxy=route.proxy_url,
                identity=identity.session_payload(),
            )
            context.checkpoint()
            context.report(stage="submit_email", state="running", message="发送新邮箱验证码")
            begin = begin_change_with_optional_reauth(
                session,
                account_id=account_id,
                current_email=current_email,
                current_source=str(account.get("email_source") or "").strip().lower(),
                new_email=new_email,
                access_token=token,
                context=context,
            )
            session = begin.session
            token = begin.access_token
            remote_accepted = True
            context.report(
                stage="login_password",
                state="success" if begin.reauthenticated else "skipped",
                message="已完成 Recent Login 重认证" if begin.reauthenticated else "现有 AT 满足重认证要求",
                detail={"reauthenticated": begin.reauthenticated},
            )
            context.checkpoint()
            context.report(stage="email_otp", state="running", message="等待新邮箱验证码")
            try:
                otp = email_provider.wait_for_otp(
                    new_email,
                    after_ts=begin.after_ts,
                    email_source=source,
                    force_service=True,
                )
            except Exception as exc:
                db.finish_account_email_change(
                    account_id,
                    ok=False,
                    new_email=new_email,
                    source=source,
                    error=f"{type(exc).__name__}: {str(exc)[:300]}",
                    outcome="request_unknown",
                )
                return task_gateway.OperationResult.request_unknown("begin 已发送验证码，但新邮箱结果待核验")
            context.checkpoint()
            context.report(stage="email_otp", state="success", message="新邮箱验证码已获取")
            verify_request_id = _remote_request_id(context, "verify")
            context.remote_request_started(
                "change_email.verify",
                request_id=verify_request_id,
                detail={"account_id": account_id},
            )
            try:
                EmailChangeProtocol().verify(session, token, new_email, otp)
            except task_gateway.OperationLeaseLost:
                raise
            except RemoteRequestRejected as exc:
                context.remote_request_receipt(
                    outcome="rejected",
                    action="change_email.verify",
                    request_id=verify_request_id,
                    detail={
                        "response_observed": True,
                        **_safe_remote_error_detail(exc),
                    },
                )
                db.finish_account_email_change(
                    account_id,
                    ok=False,
                    new_email=new_email,
                    source=source,
                    error=str(exc),
                )
                _release_unconsumed(new_email, account_id, str(exc))
                return task_gateway.OperationResult.failed("新邮箱验证码未通过", {"error_code": "email_otp_rejected"})
            except Exception as exc:
                context.remote_request_receipt(
                    outcome="unknown",
                    action="change_email.verify",
                    request_id=verify_request_id,
                    detail={
                        "response_observed": False,
                        "exception_type": type(exc).__name__,
                        **_safe_remote_error_detail(exc),
                    },
                )
                db.finish_account_email_change(
                    account_id,
                    ok=False,
                    new_email=new_email,
                    source=source,
                    error=f"{type(exc).__name__}: {str(exc)[:300]}",
                    outcome="request_unknown",
                )
                return task_gateway.OperationResult.request_unknown("verify 请求结果待核验")
            context.remote_request_receipt(
                outcome="response_received",
                action="change_email.verify",
                request_id=verify_request_id,
                detail={"response_observed": True, "remote_result_confirmed": True},
            )
            context.report(stage="submit_email", state="success", message="新邮箱验证码验证成功")
            material_line = email_provider.email_material_line(new_email, source)
            if not db.finish_account_email_change(
                account_id,
                ok=True,
                new_email=new_email,
                source=source,
                material_line=material_line,
                access_token=token,
            ) or not _safe_readback(account_id, new_email, source, token):
                context.remote_request_receipt(
                    outcome="local_commit_required",
                    action="change_email.verify",
                    request_id=verify_request_id,
                    detail={
                        "response_observed": True,
                        "remote_result_confirmed": True,
                        "local_business_writeback_confirmed": False,
                        "local_readback_confirmed": False,
                    },
                )
                return task_gateway.OperationResult.request_unknown("远端换绑成功但本地写回未确认")
            writeback_confirmed = True
            context.remote_request_receipt(
                outcome="confirmed",
                action="change_email.verify",
                request_id=verify_request_id,
                detail={
                    "response_observed": True,
                    "remote_result_confirmed": True,
                    "local_business_writeback_confirmed": True,
                    "local_readback_confirmed": True,
                },
            )
            context.report(stage="complete", state="success", message="邮箱换绑本地写回已确认")
    except task_gateway.OperationLeaseLost as exc:
        if account_claimed:
            if remote_accepted:
                try:
                    db.finish_account_email_change(
                        account_id,
                        ok=False,
                        new_email=new_email or None,
                        source=source,
                        error=str(exc) or "账号 lease 丢失，远端换绑结果待核验",
                        outcome="request_unknown",
                    )
                except Exception:
                    logger.exception("lease 丢失后的邮箱换绑待核验状态写回失败: account_id=%s", account_id)
            else:
                if new_email:
                    _release_unconsumed(new_email, account_id, str(exc))
                try:
                    db.finish_account_email_change(
                        account_id,
                        ok=False,
                        new_email=new_email or None,
                        source=source,
                        error=str(exc) or "账号 lease 丢失，邮箱换绑未完成",
                    )
                except Exception:
                    logger.exception("lease 丢失后的邮箱换绑失败状态写回失败: account_id=%s", account_id)
        raise
    except OperationCancelled as exc:
        if remote_accepted:
            db.finish_account_email_change(
                account_id,
                ok=False,
                new_email=new_email or None,
                source=source,
                error=str(exc) or "任务已取消，但远端换绑结果待核验",
                outcome="request_unknown",
            )
            return task_gateway.OperationResult.request_unknown("换绑请求已跨越远端边界，取消结果待核验")
        if new_email:
            _release_unconsumed(new_email, account_id, str(exc))
        db.finish_account_email_change(
            account_id,
            ok=False,
            new_email=new_email or None,
            source=source,
            error=str(exc) or "邮箱换绑任务已取消",
        )
        return task_gateway.OperationResult.cancelled(str(exc) or "邮箱换绑任务已取消")
    except RemoteRequestUnknown as exc:
        db.finish_account_email_change(
            account_id,
            ok=False,
            new_email=new_email or None,
            source=source,
            error=str(exc),
            outcome="request_unknown",
        )
        return task_gateway.OperationResult.request_unknown(str(exc))
    except RemoteRequestRejected as exc:
        if new_email:
            _release_unconsumed(new_email, account_id, str(exc))
        db.finish_account_email_change(
            account_id,
            ok=False,
            new_email=new_email or None,
            source=source,
            error=str(exc),
        )
        return task_gateway.OperationResult.failed(str(exc))
    except Exception as exc:
        local_error = _safe_local_failure_message(
            "邮箱准备失败" if not new_email else "邮箱换绑失败",
            exc,
        )
        if remote_accepted or writeback_confirmed:
            db.finish_account_email_change(
                account_id,
                ok=False,
                new_email=new_email or None,
                source=source,
                error=local_error,
                outcome="request_unknown",
            )
            return task_gateway.OperationResult.request_unknown("邮箱换绑结果待核验")
        if new_email:
            _release_unconsumed(new_email, account_id, local_error)
        db.finish_account_email_change(
            account_id,
            ok=False,
            new_email=new_email or None,
            source=source,
            error=local_error,
        )
        return task_gateway.OperationResult.failed(local_error)
    finally:
        _close_protocol_session(session)
        if route is not None:
            try:
                route.release(reason="email-change-completed")
            except Exception:
                logger.exception("邮箱换绑线路释放失败: account_id=%s", account_id)

    try:
        child = _enqueue_live_check_child(context, account_id, new_email)
    except Exception as exc:
        # The remote email change and local account writeback are already
        # confirmed. A local child-queue outage must not rewrite that parent
        # result as a failed remote operation.
        logger.exception("邮箱换绑后的协议查活子任务入队失败: account_id=%s", account_id)
        child = {
            "accepted": False,
            "error": f"查活子任务入队失败: {type(exc).__name__}",
        }
    summary = {
        "email_change_confirmed": True,
        "new_email": new_email,
        "post_change_live_check": {
            "accepted": bool(child.get("accepted")),
            "task_id": child.get("task_id"),
            "run_id": child.get("run_id"),
            "status": child.get("status"),
        },
    }
    if child.get("accepted"):
        return task_gateway.OperationResult.success(
            summary,
            message="邮箱换绑成功，已排队协议查活刷新 AT",
        )
    summary["post_change_live_check"]["error"] = child.get("error") or "查活子任务未入队"
    return task_gateway.OperationResult.success(
        summary,
        message="邮箱换绑成功，查活刷新 AT 待后续处理",
    )


def register_operation_handlers() -> bool:
    register = getattr(task_gateway, "register_operation_handler", None)
    if not callable(register):
        return False
    register(
        EMAIL_CHANGE_TASK_TYPE,
        _handle_email_change,
        source_systems=(EMAIL_CHANGE_SOURCE_SYSTEM,),
        config_allowlist=EMAIL_CHANGE_CONFIG_ALLOWLIST,
    )
    return True


def submit_email_change(
    account_id: int,
    *,
    source: str,
    trigger: str = "manual",
    batch_id: int | None = None,
    batch_ordinal: int | None = None,
    idempotency_key: str | None = None,
    dispatch: bool = True,
) -> dict[str, Any]:
    account = db.get_account(int(account_id))
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    try:
        selected_source = email_provider.validate_email_source(source)
    except ValueError as exc:
        return {"accepted": False, "busy": False, "error": str(exc)}
    age_gate_error = _account_age_gate_error(account)
    if age_gate_error:
        return {"accepted": False, "busy": False, "error": age_gate_error}
    from core.feature_availability import require_email_source

    source_ready, source_reason = require_email_source(selected_source)
    if not source_ready:
        return {
            "accepted": False,
            "busy": False,
            "error": f"邮箱来源 {selected_source} 当前不可用：{source_reason}",
        }
    if not str(account.get("access_token") or "").strip():
        return {"accepted": False, "busy": False, "error": "账号缺少 access_token，请先查活刷新 AT"}
    if str(account.get("email_change_status") or "").strip().lower() in {
        "request_unknown", "attention_required",
    }:
        return {
            "accepted": False,
            "busy": False,
            "reconcile_required": True,
            "error": "上一次邮箱换绑结果待人工核验，禁止盲目重试",
        }
    from config import account as account_config

    if not bool(getattr(account_config, "ACCOUNT_EMAIL_CHANGE_ENABLED", True)):
        return {"accepted": False, "busy": False, "error": "协议邮箱换绑已被配置关闭"}
    register_operation_handlers()
    key = str(idempotency_key or "").strip() or None
    source_id = (
        f"email-change:{int(account_id)}:{key}"
        if key else f"email-change:{int(account_id)}:{uuid.uuid4().hex}"
    )
    submitted = task_gateway.submit_durable_operation(
        task_type=EMAIL_CHANGE_TASK_TYPE,
        account_id=int(account_id),
        email=str(account.get("email") or "").strip(),
        trigger=str(trigger or "manual"),
        source_system=EMAIL_CHANGE_SOURCE_SYSTEM,
        source_id=source_id,
        idempotency_key=key,
        batch_id=batch_id,
        batch_ordinal=batch_ordinal,
        resource_family=EMAIL_CHANGE_RESOURCE_FAMILY,
        data={
            "email_source": selected_source,
            "proxy_source": _captured_proxy_source(None),
        },
        config_snapshot_provider=_config_snapshot,
        config_allowlist=EMAIL_CHANGE_CONFIG_ALLOWLIST,
        dispatch=dispatch,
    )
    submitted["task_type"] = EMAIL_CHANGE_TASK_TYPE
    return submitted


def submit_email_change_bulk(
    account_ids: list[int] | tuple[int, ...],
    *,
    source: str,
    trigger: str = "manual_bulk",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    ids: list[int] = []
    for raw in account_ids or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value not in ids:
            ids.append(value)
    if not ids:
        return {"accepted": False, "error": "没有可换绑的账号"}
    try:
        selected_source = email_provider.validate_email_source(source)
    except ValueError as exc:
        return {"accepted": False, "error": str(exc)}
    batch = operation_store.create_runtime_batch(
        batch_type=EMAIL_CHANGE_TASK_TYPE,
        title="批量协议邮箱换绑",
        requested_count=len(ids),
        trigger=trigger,
    )
    started: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    request_key = str(idempotency_key or "").strip() or None
    for ordinal, account_id in enumerate(ids, 1):
        key = f"{request_key}:{account_id}" if request_key else None
        item = submit_email_change(
            account_id,
            source=selected_source,
            trigger=trigger,
            batch_id=int(batch["id"]),
            batch_ordinal=ordinal,
            idempotency_key=key,
            dispatch=False,
        )
        if item.get("accepted"):
            started.append(item)
        else:
            skipped.append({"id": account_id, "error": item.get("error") or "邮箱换绑未入队", "busy": bool(item.get("busy"))})
    operation_store.set_runtime_batch_skipped(int(batch["id"]), skipped)
    if not started:
        operation_store.mark_runtime_batch_empty(int(batch["id"]), status="failed")
    if started:
        task_gateway.notify_dispatch()
    return {
        "accepted": bool(started),
        "batch_id": int(batch["id"]),
        "batch_uuid": batch.get("batch_uuid"),
        "started": started,
        "started_count": len(started),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }


register_operation_handlers()
