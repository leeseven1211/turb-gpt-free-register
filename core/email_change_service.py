# -*- coding: utf-8 -*-
"""Protocol-only email change operation.

The durable operation owns the account lease and the remote intent/receipt
boundary.  This module deliberately has no Roxy/Selenium fallback.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from config.schema import get_config_snapshot
from core import account_proxy, email_provider, live_check_service, operation_task_store
from core.operations import task_gateway
from core.account_liveness import (
    _network_preflight_with_retry,
    _validate_with_retry,
)
from core.account_export import fetch_session, follow_oauth_callback
from core.chatgpt_auth import get_csrf_token, signin_openai
from core.chatgpt_bootstrap import authenticated_bootstrap
from core.openai_auth import detect_account_unusable_text, follow_authorize
from core.session import BrowserSession
from core.storage import account_auth
from core.storage import accounts as db

logger = logging.getLogger(__name__)

EMAIL_CHANGE_TASK_TYPE = "email_change"
SOURCE_SYSTEM = "native_operations"
RESOURCE_FAMILY = "openai_interactive"
BEGIN_URL = "https://chatgpt.com/backend-api/accounts/change_email/begin"
VERIFY_URL = "https://chatgpt.com/backend-api/accounts/change_email/verify"
EMAIL_CHANGE_CONFIG_ALLOWLIST = {
    "proxy_mode": "ACCOUNT_EMAIL_CHANGE_PROXY_MODE",
    "protocol_version": "OPENAI_PROTOCOL_VERSION",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_REAUTH_MARKERS = (
    "reauth_required",
    "recent_login_required",
    "recent_login",
    "recent authentication",
    "step_up_required",
    "step-up",
)


@dataclass(frozen=True)
class ProtocolResponse:
    status_code: int
    payload: Any
    text: str = ""


class _RemoteRequestUnknown(RuntimeError):
    def __init__(self, summary: Mapping[str, Any] | None = None):
        super().__init__("远端请求结果待核验")
        self.summary = dict(summary or {})


class ChangeEmailProtocolClient:
    """Small HTTP adapter for the public ChatGPT email-change contract."""

    def _request(
        self,
        session: BrowserSession,
        access_token: str,
        url: str,
        payload: Mapping[str, Any],
    ) -> ProtocolResponse:
        headers = dict(session.get_chatgpt_headers(referer="https://chatgpt.com/settings/account"))
        headers.update({
            "authorization": (
                access_token
                if str(access_token).lower().startswith("bearer ")
                else f"Bearer {access_token}"
            ),
            "origin": "https://chatgpt.com",
            "content-type": "application/json",
        })
        response = session.post(url, headers=headers, json=dict(payload))
        try:
            body = response.json()
        except Exception:
            body = {}
        return ProtocolResponse(
            status_code=int(getattr(response, "status_code", 0) or 0),
            payload=body,
            text=str(getattr(response, "text", "") or ""),
        )

    def begin(self, session: BrowserSession, access_token: str, new_email: str) -> ProtocolResponse:
        return self._request(session, access_token, BEGIN_URL, {"new_email": new_email})

    def verify(self, session: BrowserSession, access_token: str, code: str) -> ProtocolResponse:
        return self._request(session, access_token, VERIFY_URL, {"code": code})


def _normalize_email(value: str | None) -> str:
    email = str(value or "").strip().lower()
    if email and not _EMAIL_RE.match(email):
        raise ValueError("新邮箱格式无效")
    return email


def _snapshot_value(snapshot: Any, key: str, default: Any = None) -> Any:
    if isinstance(snapshot, Mapping):
        return snapshot.get(key, default)
    values = getattr(snapshot, "values", None)
    if isinstance(values, Mapping):
        return values.get(key, default)
    return default


def _payload_text(response: ProtocolResponse) -> str:
    try:
        return json.dumps(response.payload, ensure_ascii=False, sort_keys=True).lower()
    except Exception:
        return str(response.text or "").lower()


def _response_error_code(response: ProtocolResponse) -> str:
    payload = response.payload if isinstance(response.payload, Mapping) else {}
    error = payload.get("error")
    if isinstance(error, Mapping):
        return str(error.get("code") or error.get("type") or "").strip().lower()
    return str(payload.get("code") or payload.get("error_code") or "").strip().lower()


def response_requires_reauth(response: ProtocolResponse) -> bool:
    text = _payload_text(response)
    code = _response_error_code(response)
    return any(marker in code or marker in text for marker in _REAUTH_MARKERS)


def _response_unknown(response: ProtocolResponse) -> bool:
    return response.status_code == 0 or response.status_code >= 500


def _response_accepted(response: ProtocolResponse) -> bool:
    if not 200 <= response.status_code < 300:
        return False
    payload = response.payload if isinstance(response.payload, Mapping) else {}
    if payload.get("error") or payload.get("error_code"):
        return False
    status = str(payload.get("status") or payload.get("state") or "").strip().lower()
    return status not in {"failed", "failure", "rejected", "denied", "invalid", "error"}


def _safe_child(child: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: child.get(key)
        for key in ("task_id", "run_id", "status", "accepted", "busy", "source_system", "source_id")
        if child.get(key) is not None
    }


def run_recent_login(
    email: str,
    proxy: str | None,
    identity: Any = None,
    *,
    context: Any = None,
) -> str:
    """Perform the existing protocol login flow after explicit reauth."""
    session = None
    identity_payload = identity.session_payload() if callable(getattr(identity, "session_payload", None)) else identity
    try:
        session, authorize_url = _network_preflight_with_retry(
            email, proxy, identity=identity_payload,
        )
        final_url = follow_authorize(session, authorize_url)
        dead_code = detect_account_unusable_text(final_url)
        if dead_code:
            raise RuntimeError(dead_code)
        validate_result = _validate_with_retry(session, email, time.time())
        page = validate_result.get("page") if isinstance(validate_result, Mapping) else {}
        page = page if isinstance(page, Mapping) else {}
        continue_url = (
            validate_result.get("continue_url")
            or validate_result.get("external_url")
            or validate_result.get("url")
            or page.get("continue_url")
            or page.get("external_url")
            or page.get("url")
        )
        if not continue_url or "about-you" in str(continue_url):
            raise RuntimeError("Recent Login 未返回可用的 OAuth continue_url")
        follow_oauth_callback(session, str(continue_url), referer="https://auth.openai.com/email-verification")
        session_info = fetch_session(session)
        token = str(session_info.get("accessToken") or "").strip()
        if not token:
            raise RuntimeError("Recent Login 未返回 accessToken")
        return token
    finally:
        raw_session = getattr(session, "session", None)
        close = getattr(raw_session, "close", None)
        if callable(close):
            close()


def submit_email_change(
    *,
    account_id: int,
    new_email: str | None = None,
    email_source: str | None = None,
    trigger: str = "manual_email_change",
    idempotency_key: str | None = None,
    batch_id: int | None = None,
) -> dict[str, Any]:
    account = db.get_account(int(account_id))
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    old_email = str(account.get("email") or "").strip()
    if not old_email:
        return {"accepted": False, "busy": False, "error": "账号邮箱为空"}
    target = _normalize_email(new_email)
    if target and target.casefold() == old_email.casefold():
        return {"accepted": False, "busy": False, "error": "新邮箱不能与当前邮箱相同"}
    if target:
        conflict = db.get_account_by_email(target)
        if conflict and int(conflict.get("id") or 0) != int(account_id):
            return {"accepted": False, "busy": False, "error": "新邮箱已绑定其它账号"}
    source = None
    if email_source:
        source = email_provider.validate_email_source(email_source)
    key = str(idempotency_key or "").strip() or None
    source_id = f"email-change:{int(account_id)}:{key or uuid.uuid4().hex}"
    data = {"new_email": target, "email_source": source}
    queued = task_gateway.submit_durable_operation(
        task_type=EMAIL_CHANGE_TASK_TYPE,
        account_id=int(account_id),
        email=old_email,
        trigger=str(trigger or "manual_email_change"),
        source_system=SOURCE_SYSTEM,
        source_id=source_id,
        idempotency_key=key,
        batch_id=int(batch_id) if batch_id is not None else None,
        resource_family=RESOURCE_FAMILY,
        data=data,
        config_snapshot_provider=get_config_snapshot,
        config_allowlist=EMAIL_CHANGE_CONFIG_ALLOWLIST,
        dispatch=True,
    )
    return {
        **{key: queued.get(key) for key in (
            "accepted", "busy", "reused", "task_id", "run_id", "status", "source_system", "source_id",
        ) if key in queued},
        "account_id": int(account_id),
        "email": old_email,
        "task_type": EMAIL_CHANGE_TASK_TYPE,
        "trigger": str(trigger or "manual_email_change"),
    }


def _remote_call(
    context: Any,
    phase: str,
    call: Callable[[], ProtocolResponse],
) -> ProtocolResponse:
    request_id = f"email-change:{context.run_id}:{phase}:{uuid.uuid4().hex}"
    action = f"email_change_{phase}"
    context.remote_request_started(
        action,
        intent_kind="remote_write",
        request_id=request_id,
        detail={"phase": phase},
    )
    try:
        response = call()
    except Exception as exc:
        context.remote_request_receipt(
            outcome="request_unknown",
            receipt_state="unknown",
            action=action,
            request_id=request_id,
            detail={"response_observed": False, "exception_type": type(exc).__name__},
        )
        raise _RemoteRequestUnknown from exc
    if _response_unknown(response):
        context.remote_request_receipt(
            outcome="request_unknown",
            receipt_state="unknown",
            action=action,
            request_id=request_id,
            detail={"response_observed": True, "remote_result_confirmed": False},
        )
        raise _RemoteRequestUnknown
    if not _response_accepted(response):
        context.remote_request_receipt(
            outcome="rejected",
            receipt_state="rejected",
            action=action,
            request_id=request_id,
            detail={"response_observed": True, "remote_result_confirmed": False},
        )
        return response
    context.remote_request_receipt(
        outcome="accepted",
        receipt_state="received",
        action=action,
        request_id=request_id,
        detail={"response_observed": True, "remote_result_confirmed": False},
    )
    return response


def _release_parent(context: Any, released: bool) -> bool:
    if released:
        return True
    context.release_lease()
    return True


def _enqueue_refresh_child(context: Any, account_id: int, email: str, trigger: str) -> dict[str, Any]:
    key = f"email-change:{int(context.task_id)}:refresh"
    queued = live_check_service.enqueue_account_live_check(
        account_id=int(account_id),
        email=email,
        trigger=trigger,
        force_refresh=True,
        idempotency_key=key,
    )
    if queued.get("accepted") or not queued.get("not_registered"):
        return queued
    submit_native = getattr(live_check_service, "_submit_native_live", None)
    if not callable(submit_native):
        return queued
    return submit_native(
        account_id=int(account_id),
        email=email,
        trigger=trigger,
        task_type="token_refresh",
        force_refresh=True,
        driver=None,
        refresh_driver=None,
        explicit_proxy_requested=False,
        batch_id=None,
        idempotency_key=key,
    )


def handle_email_change(context: Any) -> task_gateway.OperationResult:
    account = db.get_account(int(context.account_id)) if context.account_id is not None else None
    if not account:
        return task_gateway.OperationResult.failed("账号不存在")
    old_email = str(account.get("email") or context.email or "").strip()
    data = context.run.get("data") if isinstance(getattr(context, "run", None), Mapping) else {}
    data = data if isinstance(data, Mapping) else {}
    new_email = _normalize_email(data.get("new_email"))
    email_source = str(data.get("email_source") or "").strip().lower() or "outlook"
    if not new_email:
        new_email = _normalize_email(email_provider.acquire_email(email_source))
    if new_email.casefold() == old_email.casefold():
        return task_gateway.OperationResult.failed("新邮箱不能与当前邮箱相同")
    conflict = db.get_account_by_email(new_email)
    if conflict and int(conflict.get("id") or 0) != int(context.account_id):
        return task_gateway.OperationResult.failed("新邮箱已绑定其它账号")
    access_token = str(account.get("access_token") or "").strip()
    if not access_token:
        return task_gateway.OperationResult.failed("当前账号没有可用 access_token")

    lease_acquired = False
    lease_released = False
    route = None
    try:
        context.acquire_lease(resource_family=RESOURCE_FAMILY)
        lease_acquired = True
        context.report(stage="email", state="running", message="准备新邮箱", detail={"email_source": email_source})
        context.report(stage="network", state="running", message="分配换绑线路")
        route = account_proxy.acquire_account_proxy(
            account_id=int(context.account_id), email=old_email, purpose="email-change",
        )
        identity = account_auth.ensure_account_protocol_identity(int(context.account_id))
        session = getattr(context, "session", None)
        if session is None:
            session = BrowserSession(
                proxy=str(getattr(route, "proxy_url", "") or ""),
                detect_exit_geo=False,
                identity=(identity.session_payload() if identity is not None else None),
            )
        authenticated_bootstrap(session, access_token, strict=False)
        client = ChangeEmailProtocolClient()

        context.report(stage="email_change_begin", state="running", message="提交换绑请求")
        token = access_token
        begin = _remote_call(context, "begin", lambda: client.begin(session, token, new_email))
        if response_requires_reauth(begin):
            context.report(stage="reauth", state="running", message="远端要求 Recent Login")
            token = run_recent_login(old_email, getattr(route, "proxy_url", None), identity, context=context)
            begin = _remote_call(context, "begin", lambda: client.begin(session, token, new_email))
        if not _response_accepted(begin):
            return task_gateway.OperationResult.failed("远端拒绝邮箱换绑请求")
        context.report(stage="email_change_begin", state="success", message="换绑请求已接受")
        context.checkpoint()

        context.report(stage="email_change_verify", state="running", message="等待新邮箱验证码")
        code = email_provider.wait_for_otp(new_email, after_ts=time.time())
        verify = _remote_call(context, "verify", lambda: client.verify(session, token, str(code)))
        if not _response_accepted(verify):
            return task_gateway.OperationResult.failed("远端拒绝邮箱验证码")
        try:
            writeback = db.update_account_email_after_change(
                account_id=int(context.account_id),
                expected_old_email=old_email,
                new_email=new_email,
                email_source=email_source,
            )
        except Exception as exc:
            logger.warning("邮箱换绑远端已确认但本地写回异常: %s", type(exc).__name__)
            raise _RemoteRequestUnknown({
                "remote_change_confirmed": True,
                "local_writeback_confirmed": False,
                "local_readback_confirmed": False,
            }) from exc
        if not writeback or not writeback.get("local_readback_confirmed"):
            raise _RemoteRequestUnknown({
                "remote_change_confirmed": True,
                "local_writeback_confirmed": False,
                "local_readback_confirmed": False,
            })
        context.remote_request_receipt(
            outcome="accepted",
            receipt_state="confirmed",
            action="email_change_verify",
            detail={
                "remote_result_confirmed": True,
                "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True,
            },
        )
        context.report(stage="email_change_verify", state="success", message="邮箱换绑已写回本地")

        if route is not None:
            release = getattr(route, "release", None)
            if callable(release):
                release(reason="email-change-parent-complete")
                route = None
        lease_released = _release_parent(context, lease_released)
        context.report(stage="refresh_token", state="running", message="提交新会话刷新子任务")
        child = _enqueue_refresh_child(
            context, int(context.account_id), new_email, "email_change_refresh",
        )
        child_safe = _safe_child(child)
        if child.get("accepted"):
            operation_task_store.register_task_dependency(
                parent_source_system=SOURCE_SYSTEM,
                parent_source_id=str(context.task_id),
                child_source_system=str(child.get("source_system") or SOURCE_SYSTEM),
                child_source_id=str(child.get("source_id") or child.get("task_id") or ""),
                dependency_type="email_change_refresh",
                payload={
                    "account_id": int(context.account_id),
                    "email": new_email,
                    "remaining_steps": ["refresh_at"],
                },
            )
        summary = {
            "remote_change_confirmed": True,
            "local_writeback_confirmed": True,
            "local_readback_confirmed": True,
            "awaiting_steps": [] if child.get("accepted") else ["refresh_at"],
            "child_tasks": [child_safe] if child_safe else [],
            "email_source": email_source,
        }
        return task_gateway.OperationResult(
            "partial_success",
            summary,
            "邮箱换绑完成，已提交新会话刷新子任务",
        )
    except _RemoteRequestUnknown as exc:
        summary = {
            "remote_change_confirmed": False,
            "reconcile_required": True,
            **getattr(exc, "summary", {}),
        }
        return task_gateway.OperationResult.request_unknown(
            "远端换绑结果待核验",
            summary,
        )
    except (
        task_gateway.OperationLeaseUnavailable,
        task_gateway.OperationLeaseLost,
        task_gateway.OperationCancelled,
    ):
        raise
    except Exception as exc:
        logger.warning("邮箱换绑 durable handler failed: %s", type(exc).__name__)
        return task_gateway.OperationResult.failed("邮箱换绑未完成", {"error_type": type(exc).__name__})
    finally:
        if route is not None:
            release = getattr(route, "release", None)
            if callable(release):
                release(reason="email-change-finished")
        if lease_acquired and not lease_released:
            context.release_lease()


def retry_email_change(task: Mapping[str, Any]) -> dict[str, Any]:
    if task_gateway.operation_requires_reconciliation(task):
        return {
            "accepted": False,
            "busy": False,
            "reconcile_required": True,
            "error": "远端请求结果待核验，禁止盲目重试",
        }
    status = str(task.get("status") or "").strip().lower()
    if status in {"queued", "running", "cancelling", "settling", "stopping", "waiting"}:
        return {"accepted": False, "busy": True, "error": "任务仍在执行"}
    task_id = int(task.get("id") or 0)
    if not task_id:
        return {"accepted": False, "busy": False, "error": "任务缺少 id"}
    run = operation_task_store.retry_runtime_task(
        task_id, trigger="manual_retry", data={"retry_action": "manual_retry"},
    )
    task_gateway.notify_dispatch()
    return {
        "accepted": True,
        "busy": False,
        "task_id": task_id,
        "run_id": int(run.get("id") or 0) or None,
        "status": "queued",
        "source_system": SOURCE_SYSTEM,
    }


def cancel_email_change(task: Mapping[str, Any]) -> dict[str, Any]:
    return task_gateway.default_operation_cancel(task)


def register_operation_handlers() -> bool:
    task_gateway.register_operation_handler(
        EMAIL_CHANGE_TASK_TYPE,
        handle_email_change,
        source_systems=(SOURCE_SYSTEM,),
        config_allowlist=EMAIL_CHANGE_CONFIG_ALLOWLIST,
        retry_handler=retry_email_change,
        cancel_handler=cancel_email_change,
    )
    return True


register_operation_handlers()
