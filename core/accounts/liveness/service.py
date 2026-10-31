# -*- coding: utf-8 -*-
"""账号查活后台队列：协议 BrowserSession 指纹环境 + 独立日志。"""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from config.schema import get_config_snapshot
from core.operations.runtime import OperationCancelled
from core.operations import run_log as task_run_log
from core.operations import task_gateway as account_task_store
from core.storage import accounts as db
from core.accounts.liveness.protocol.legacy import check_account_liveness, log_path
from core.operations.reporter import TaskReporter
from core.accounts.plans.client import check_account_plan, token_claims
from core.accounts.liveness.router import LiveCheckDriverError, resolve_driver, run_probe
from core.auth.protocol.openai_auth import detect_account_unusable_text
from core.auth.challenge import auth_result_for_operation
from core.operations.executor import configured_workers, operation_log_context
from core.operations.executor import executor as _EXECUTOR

logger = logging.getLogger('core.live_check_service')

_QUEUE_LIMIT = 500
_QUEUE_SLOTS = threading.BoundedSemaphore(_QUEUE_LIMIT)  # synchronous inline compatibility only
_RUNNING: set[int] = set()
_LOCK = threading.Lock()

# Persist only non-sensitive choices required to execute a native Run.  ATs,
# passwords, cookies, and proxy URLs remain account/client data and are loaded
# on demand after claim.
LIVE_CONFIG_ALLOWLIST = {
    "live_check_driver": "ACCOUNT_LIVE_CHECK_DRIVER",
    "browser_enabled": "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED",
    "refresh_protocol_version": "OPENAI_PROTOCOL_VERSION",
    "refresh_driver": "ACCOUNT_AT_REFRESH_DRIVER",
    "refresh_roxy_debug_enabled": "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED",
    "live_check_proxy_mode": "ACCOUNT_LIVE_CHECK_PROXY_MODE",
    "refresh_at_proxy_mode": "ACCOUNT_REFRESH_AT_PROXY_MODE",
    "roxy_fallback_enabled": "LIVE_CHECK_ROXY_FALLBACK_ENABLED",
    "proxy_retry_limit": "ACCOUNT_ACTION_PROXY_RETRIES",
    "proxy_retry_delay": "ACCOUNT_ACTION_PROXY_RETRY_DELAY",
    "auth_profile_mode": "ACCOUNT_AUTH_PROFILE_MODE",
    "auth_raw_context_enabled": "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED",
    "auth_v2_enabled": "ACCOUNT_AUTH_V2_ENABLED",
}


def _snapshot_value(snapshot, key: str, default=None):
    if isinstance(snapshot, dict) and key in snapshot:
        return snapshot[key]
    return default


def _captured_proxy_source(purpose: str) -> str | None:
    """Resolve a route mode once; never put the selected URL in task data."""
    try:
        from core.proxy.account_routes import account_action_proxy_mode

        return str(account_action_proxy_mode(purpose) or "").strip() or None
    except Exception:
        logger.exception("[查活] 读取账号动作线路配置失败: purpose=%s", purpose)
        return None


class _ReporterAdapter:
    """Keep the old worker vocabulary while routing native events to ``ctx``."""

    def __init__(self, task_id: int | None, context=None, *, finish_operation: bool = True):
        self._legacy = TaskReporter(task_id) if context is None else None
        self._context = context
        self._finish_operation = bool(finish_operation)

    def start(self, message: str = "开始执行") -> None:
        if self._context is None:
            self._legacy.start(message)
        else:
            self._native_report("preflight", state="running", message=message)

    def _native_report(self, stage: str, **event):
        task_run_log.set_current_stage(
            stage, task_id=getattr(self._context, "task_id", None),
            run_id=getattr(self._context, "run_id", None),
            identifier_namespace="operation",
        )
        result = self._context.report(stage=stage, **event)
        if isinstance(result, dict):
            task_run_log.set_current_stage(
                stage,
                event_id=result.get("event_id", result.get("id")),
                event_uuid=result.get("event_uuid"),
                source_event_id=result.get("source_event_id"),
                source_system=result.get("source_system"),
                main_step_id=result.get("main_step_id"),
            )
        return result

    def stage(self, stage: str, state: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.stage(stage, state, message, **kwargs)
        else:
            self._native_report(stage, state=state, message=message, **kwargs)

    def note(self, message: str, *, stage: str = "event", **kwargs) -> None:
        if self._context is None:
            self._legacy.note(message, stage=stage, **kwargs)
        else:
            self._native_report(stage, message=message, **kwargs)

    def resource(self, event_type: str, message: str, *, stage: str = "network", **kwargs) -> None:
        if self._context is None:
            self._legacy.resource(event_type, message, stage=stage, **kwargs)
        else:
            self._native_report(stage, message=message, event_type=event_type, **kwargs)

    def finish(self, *, status: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.finish(status=status, message=message, **kwargs)
            return
        summary = dict(kwargs.get("result_summary") or {})
        for key in ("route", "validation_method"):
            if kwargs.get(key) is not None:
                summary[key] = kwargs[key]
        if not self._finish_operation:
            self._native_report(
                stage="nested_live_check",
                message=message,
                detail={**summary, "status": status},
            )
            return
        self._context.finish(
            status=status,
            message=message,
            error=kwargs.get("error"),
            result_summary=summary,
        )


def _reporter(task_id: int | None, context=None, *, finish_operation: bool = True):
    return _ReporterAdapter(task_id, context, finish_operation=finish_operation)


def _checkpoint(context, message: str = "用户手动停止维护任务") -> None:
    if context is not None:
        context.checkpoint(message)
        # The normal token poll is intentionally throttled.  A remote request
        # boundary is a safety fence, so cancellation must be observed again
        # immediately after the heartbeat rather than waiting for the next
        # throttled poll.
        if context.is_cancel_requested(force=True):
            raise OperationCancelled(message)


_SAFE_REFRESH_CAUSE_CODES = frozenset({
    "access_token_missing", "account_deactivated", "auth_page_unknown",
    "auth_route_rejected", "email_otp_failed", "email_otp_send_failed",
    "mfa_code_missing", "mfa_factor_missing", "mfa_issue_challenge_failed",
    "mfa_issue_challenge_invalid_response", "mfa_rejected", "mfa_secret_invalid",
    "mfa_secret_missing", "mfa_verify_failed", "mfa_verify_invalid_response",
    "network_preflight_failed", "oauth_callback_failed", "password_missing",
    "password_rejected", "password_rejected_email_fallback_failed",
    "password_result_unknown", "password_sentinel_failed", "password_change_required", "password_page_error",
    "auth_operation_timeout", "auth_context_missing",
    "roxy_password_prepare_timeout",
    "password_verify_failed", "password_verify_invalid_response",
    "password_login_unavailable", "email_verification_required",
    "passwordless_fallback_unavailable", "protocol_network_error",
    "protocol_v2_unknown_error", "refresh_driver_exception", "refresh_result_invalid",
    "refresh_cancelled", "refresh_local_commit_failed", "remote_response_missing",
    "roxy_not_configured", "roxy_profile_open_failed", "roxy_driver_attach_failed",
    "roxy_navigation_failed", "roxy_login_failed", "roxy_session_fetch_failed",
    "roxy_authenticated_callback_failed", "email_submit_unconfirmed", "email_otp_no_mail",
    "roxy_proxy_tunnel_failed",
    "roxy_login_page_not_ready", "roxy_login_page_timeout",
    "roxy_login_preflight_timeout", "roxy_login_preflight_failed",
})
_SAFE_AUTH_DIAGNOSTIC_OPERATIONS = frozenset({
    "email_otp", "email_otp_send", "mfa_issue_challenge", "mfa_verify",
    "network_preflight", "password_email_fallback", "password_verify", "password_sentinel", "password_login",
    "protocol_v2_auth",
    "roxy_open", "roxy_driver", "roxy_navigation", "roxy_login", "roxy_email_otp", "roxy_session", "roxy_callback",
})
_SAFE_AUTH_FAILURE_KINDS = frozenset({
    "fallback_failed", "http_error", "imap_error", "invalid_code", "manual_timeout",
    "no_mail", "otp_error", "rejected", "runtime_exception", "transport_error",
    "unconfirmed",
})


def _safe_refresh_cause_code(result: dict | None) -> str | None:
    """只保存协议适配器定义的稳定码，不能把异常原文当作原因码。"""
    value = result if isinstance(result, dict) else {}
    for key in ("error_code", "error"):
        code = str(value.get(key) or "").strip().lower()
        if code in _SAFE_REFRESH_CAUSE_CODES:
            return code
    return None


def _safe_refresh_auth_diagnostics(value: object) -> dict | None:
    """把认证诊断限制为无凭据的字段和值，再写入任务事件和摘要。"""
    if not isinstance(value, dict):
        return None
    safe: dict = {}
    from core.network.response_diagnostics import safe_auth_error, safe_response_headers

    auth_error = safe_auth_error(value.get("auth_error"))
    headers = safe_response_headers(value.get("response_headers"))
    if auth_error:
        safe["auth_error"] = auth_error
    if headers:
        safe["response_headers"] = headers
    for key in ("operation", "cause_operation"):
        text = str(value.get(key) or "").strip()
        if text in _SAFE_AUTH_DIAGNOSTIC_OPERATIONS:
            safe[key] = text
    for key in ("failure_kind", "cause_failure_kind"):
        text = str(value.get(key) or "").strip()
        if text in _SAFE_AUTH_FAILURE_KINDS:
            safe[key] = text
    cause_code = str(value.get("cause_code") or "").strip()
    if cause_code in _SAFE_REFRESH_CAUSE_CODES:
        safe["cause_code"] = cause_code
    exception_type = str(value.get("exception_type") or "").strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", exception_type):
        safe["exception_type"] = exception_type
    status = value.get("http_status")
    if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
        safe["http_status"] = status
    if isinstance(value.get("response_observed"), bool):
        safe["response_observed"] = value["response_observed"]
    curl_code = value.get("curl_error_code")
    if isinstance(curl_code, int) and not isinstance(curl_code, bool) and curl_code in {28, 35, 56, 60}:
        safe["curl_error_code"] = curl_code
    return safe or None


def _refresh_result_is_unknown(result: dict | None) -> bool:
    """A refresh response without remote confirmation must remain reconcilable."""
    value = result if isinstance(result, dict) else {}
    auth = value.get("auth") if isinstance(value.get("auth"), dict) else {}
    result_codes = [
        str(value.get(key) or "").strip().lower()
        for key in ("error_code", "status", "error")
    ]
    auth_codes = [
        str(auth.get(key) or "").strip().lower()
        for key in ("code", "status")
    ]
    markers = (
        "request_unknown", "password_result_unknown", "protocol_v2_unknown_error",
        "oauth_callback_failed",
    )
    return bool(
        value.get("request_unknown") or value.get("manual_reconcile") or value.get("reconcile_required") or
        any(any(marker in code for marker in markers) for code in result_codes)
        or (
            not _refresh_result_before_remote_boundary(value)
            and (
                auth.get("next_action") == "manual_reconcile"
                or any(any(marker in code for marker in markers) for code in auth_codes)
            )
        )
    )


def _unknown_refresh_response_observed(result: dict) -> bool:
    """页面错误不能冒充已经观测到认证 HTTP 响应。"""
    if result.get("error_code") in {
        "password_change_required", "password_page_error", "auth_operation_timeout", "auth_context_missing",
        "roxy_proxy_tunnel_failed",
        "roxy_password_prepare_timeout",
    }:
        return result.get("response_observed") is True
    return True


def _refresh_exception_is_unknown(exc: BaseException) -> bool:
    text = str(exc or "").strip().lower()
    return any(marker in text for marker in (
        "request_unknown", "password_result_unknown", "oauth_callback_failed",
        "protocol_v2_unknown_error",
    ))


def _refresh_result_before_remote_boundary(result: dict | None) -> bool:
    """判断刷新结果是否明确发生在远端认证边界之前。"""
    value = result if isinstance(result, dict) else {}
    if _refresh_result_not_submitted(value):
        return True
    if value.get("remote_request_started") is True:
        return False
    if value.get("remote_request_started") is False:
        return True
    codes = {
        str(value.get(key) or "").strip().lower()
        for key in ("error_code", "error", "status")
    }
    return bool(codes & {"auth_route_rejected", "network_preflight_failed"})


def _refresh_result_not_submitted(result: dict | None) -> bool:
    """只有适配器同时确认认证未提交和动作未派发，才能关闭旧请求边界。"""
    value = result if isinstance(result, dict) else {}
    return value.get("mutation_submitted") is False and value.get("action_dispatched") is False


def _is_proxy_transport_failure(result: dict | None) -> bool:
    """仅把明确的预检网络失败标记为代理故障。"""
    value = result if isinstance(result, dict) else {}
    codes = {str(value.get(key) or "").strip().lower() for key in ("error", "error_code")}
    return "network_preflight_failed" in codes


def _refresh_result_is_rejected(result: dict | None) -> bool:
    """Return true only for an explicit, safe remote rejection.

    A generic failed response can mean that the remote login was accepted but
    the response was lost.  Treating that as a normal failure would permit a
    second remote login, so only protocol/account rejection markers are
    allowed to close the remote-write checkpoint.
    """
    value = result if isinstance(result, dict) else {}
    if str(value.get("status") or "").strip().lower() == "deactivated":
        return True
    auth = value.get("auth") if isinstance(value.get("auth"), dict) else {}
    final_codes = {
        str(value.get(key) or "").strip().lower()
        for key in ("error_code", "error", "status")
    } | {
        str(auth.get(key) or "").strip().lower()
        for key in ("code", "status")
    }
    # 密码拒绝后进入邮箱兜底，后续失败并不能证明整条刷新已被远端拒绝。
    # v2 会同时保留 password_auth_status=rejected，不能让这个步骤状态覆盖最终结果。
    if "password_rejected_email_fallback_failed" in final_codes:
        return False
    codes = [
        str(value.get(key) or "").strip().lower()
        for key in ("error_code", "error", "status", "password_auth_status")
    ] + [
        str(auth.get(key) or "").strip().lower()
        for key in ("code", "status", "password_auth_status")
    ]
    markers = (
        "account_deactivated",
        "password_rejected",
        "passwordless_fallback_unavailable",
        "email_verification_required",
    )
    return any(code in markers for code in codes if code)


def _mark_refresh_reconcile_required(result: dict | None, error: str | None = None) -> dict:
    value = dict(result) if isinstance(result, dict) else {}
    value.pop("request_unknown", None)
    value.update({
        "ok": False,
        "status": "failed",
        "reconcile_required": True,
        "manual_reconcile": True,
        "next_action": "manual_reconcile",
    })
    cause = _safe_refresh_cause_code(value)
    if str(value.get("error_code") or "").strip() == "request_unknown":
        value["error_code"] = cause or "remote_response_missing"
    if str(value.get("error") or "").strip() == "request_unknown":
        value["error"] = cause or "remote_response_missing"
    if error:
        value.setdefault("error", str(error)[:500])
    else:
        value.setdefault("error", "remote_response_missing")
    if _safe_refresh_cause_code(value) is None:
        value.setdefault("error_code", "remote_response_missing")
    return value


def _record_refresh_receipt(context, boundary: dict | None, outcome: str, detail: dict | None = None) -> None:
    """Persist one refresh receipt without swallowing a safety-boundary error."""
    if context is None or not boundary:
        return
    context.remote_request_receipt(
        outcome=outcome,
        action=str(boundary["action"]),
        request_id=str(boundary["request_id"]),
        detail=dict(detail or {}),
    )
    boundary["receipt_outcome"] = str(outcome)
    boundary["pending_confirmation"] = str(outcome) == "response_received"


def _confirm_refresh_receipt(
    *, context, boundary: dict | None, result: dict, account_id: int, writeback_ok: bool,
) -> bool:
    """Confirm AT refresh only after remote, business, and readback evidence."""
    if context is None or not boundary or not boundary.get("pending_confirmation"):
        return True
    token = str(result.get("access_token") or "").strip()
    remote_result_confirmed = bool(result.get("ok") and token)
    local_business_writeback_confirmed = bool(writeback_ok)
    account_after = db.get_account(account_id) if local_business_writeback_confirmed else None
    expected_status = str(result.get("status") or "").strip()
    stored_token = str((account_after or {}).get("access_token") or "").strip()
    local_readback_confirmed = bool(
        account_after
        and bool((account_after or {}).get("live_check_ok"))
        and str((account_after or {}).get("live_check_status") or "").strip() == expected_status
        and stored_token == token
    )
    evidence = {
        "remote_result_confirmed": remote_result_confirmed,
        "local_business_writeback_confirmed": local_business_writeback_confirmed,
        "local_readback_confirmed": local_readback_confirmed,
        "response_observed": True,
    }
    if all(evidence.values()):
        _record_refresh_receipt(context, boundary, "confirmed", evidence)
        return True
    _record_refresh_receipt(context, boundary, "local_commit_required", evidence)
    result["error_code"] = "refresh_local_commit_failed"
    result.update(_mark_refresh_reconcile_required(
        result, "刷新 AT 已收到远端响应，但本地业务写回/读回未完成，需人工对账"
    ))
    return False


def _attach_auth_projection(
    result: dict,
    *,
    auth_method: str,
    remote_identity: str = "existing",
) -> dict:
    """Attach the safe cross-driver authentication result to a task result."""
    if isinstance(result, dict):
        result.setdefault(
            "auth",
            auth_result_for_operation(
                result,
                auth_method=auth_method,
                remote_identity=remote_identity,
            ).as_dict(),
        )
    return result


def is_checking(email: str) -> bool:
    acc = db.get_account_by_email(email)
    if not acc:
        return False
    return str(acc.get("live_check_status") or "") in {"queued", "running"}


def _append_log(email: str, line: str, *, clear: bool = False) -> None:
    p = log_path(email)
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H:%M:%S")
    mode = "w" if clear else "a"
    with p.open(mode, encoding="utf-8") as f:
        f.write(f"{stamp} [INFO] {line}\n")


def _token_probe_retryable(result: dict) -> bool:
    """只有网络/风控类结果才值得换线路；查活不会因 Token 失效自动重登录。"""
    if result.get("needs_live_check") or result.get("token_expired") is True:
        return False
    status = result.get("http_status")
    if status is None:
        return True
    try:
        status = int(status)
    except (TypeError, ValueError):
        return False
    return status in {403, 408, 409, 425, 429} or status >= 500


def _roxy_fallback_enabled(config_snapshot: dict | None = None) -> bool:
    # 通过 config.proxy 读取，保证 WebUI 写入 .env 后 reload_all() 能立即生效。
    if config_snapshot is not None:
        return bool(_snapshot_value(config_snapshot, "roxy_fallback_enabled", True))
    from config import proxy as proxy_config

    return bool(getattr(proxy_config, "LIVE_CHECK_ROXY_FALLBACK_ENABLED", True))


def _account_action_proxy_retry_limit(config_snapshot: dict | None = None) -> int:
    """读取账号动作代理申请的额外换线次数。"""
    if config_snapshot is not None:
        try:
            value = int(_snapshot_value(config_snapshot, "proxy_retry_limit", 2) or 0)
        except (TypeError, ValueError):
            value = 2
        return max(0, min(3, value))
    try:
        from config import proxy as proxy_config

        value = int(getattr(proxy_config, "ACCOUNT_ACTION_PROXY_RETRIES", 2) or 0)
    except (TypeError, ValueError, ImportError):
        value = 2
    return max(0, min(3, value))


def _account_action_proxy_retry_delay(config_snapshot: dict | None = None) -> float:
    if config_snapshot is not None:
        try:
            value = float(_snapshot_value(config_snapshot, "proxy_retry_delay", 1.0) or 0.0)
        except (TypeError, ValueError):
            value = 1.0
        return max(0.0, min(10.0, value))
    try:
        from config import proxy as proxy_config

        value = float(getattr(proxy_config, "ACCOUNT_ACTION_PROXY_RETRY_DELAY", 1.0) or 0)
    except (TypeError, ValueError, ImportError):
        value = 1.0
    return max(0.0, min(10.0, value))


def _is_retryable_account_proxy_acquisition_error(error: object) -> bool:
    """只把代理平台/租约碰撞视为可换线错误。"""
    text = str(error or "").lower()
    return any(marker in text for marker in (
        "duplicateproxyerror",
        "1024proxy 获取失败",
        "1024proxy 批量获取失败",
    ))


def _acquire_account_proxy_with_retries(
    *,
    acquire_proxy,
    account_id: int,
    email: str,
    purpose: str,
    rotation_index: int = 0,
    retry_callback=None,
    config_snapshot: dict | None = None,
    source: str | None = None,
):
    """只重试账号动作的代理申请，不重跑后续认证步骤。"""
    retry_limit = _account_action_proxy_retry_limit(config_snapshot)
    base_rotation = max(0, int(rotation_index or 0))
    for attempt in range(retry_limit + 1):
        try:
            return acquire_proxy(
                account_id=account_id,
                email=email,
                purpose=purpose,
                rotation_index=base_rotation + attempt,
                **({"source": source} if source else {}),
            )
        except Exception as exc:
            if attempt >= retry_limit or not _is_retryable_account_proxy_acquisition_error(exc):
                raise
            next_attempt = attempt + 1
            if retry_callback is not None:
                retry_callback(next_attempt, retry_limit, exc)
            delay = _account_action_proxy_retry_delay(config_snapshot)
            if delay:
                time.sleep(delay)


def _resolve_refresh_driver(requested: str | None = None, *, config_snapshot: dict | None = None) -> str:
    """Resolve and freeze the explicit AT-refresh implementation for one task."""
    from config import account as account_config
    from core.auth.protocol.version import resolve_protocol_version

    value = None if requested is None else str(requested or "").strip().lower()
    if value in {"browser_roxy", "roxy"}:
        return "browser_roxy"
    if value is None and str(_snapshot_value(
        config_snapshot, "refresh_driver", getattr(account_config, "ACCOUNT_AT_REFRESH_DRIVER", "protocol"),
    ) or "protocol").strip().lower() == "browser_roxy":
        return "browser_roxy"
    legacy_v2_alias = value == "protocol_v2"
    if value is None:
        try:
            version = resolve_protocol_version(
                "refresh_at", requested=_snapshot_value(config_snapshot, "refresh_protocol_version"),
            )
        except ValueError as exc:
            logger.warning("[查活] 协议版本配置无效，刷新 AT 回落 v1：%s", exc)
            version = "v1"
    elif value in {"v1", "1"}:
        version = "v1"
    elif value in {"v2", "2"}:
        version = "v2"
    elif value in {"current", "protocol", "protocol_current", "legacy", ""}:
        version = "v1"
    elif legacy_v2_alias:
        version = "v2"
    else:
        logger.warning("[查活] 不支持的刷新 AT 版本/驱动 %r，回落 v1", value)
        version = "v1"

    # Only the old literal driver name keeps the old kill-switch semantics.
    # The new OPENAI_PROTOCOL_VERSION=v2 is the explicit replacement and must
    # not be silently disabled by a stale compatibility flag.
    if legacy_v2_alias and not bool(getattr(account_config, "ACCOUNT_AUTH_V2_ENABLED", False)):
        logger.warning("[查活] 旧配置 protocol_v2 未开启兼容开关，刷新 AT 回落 v1")
        version = "v1"
    return "protocol_v2" if resolve_protocol_version("refresh_at", requested=version) == "v2" else "legacy"


def _refresh_protocol_version(refresh_driver: str | None) -> str | None:
    """Expose the stable public version for a legacy internal driver value."""
    if refresh_driver is None or str(refresh_driver).strip().lower() == "browser_roxy":
        return None
    return "v2" if str(refresh_driver).strip().lower() == "protocol_v2" else "v1"


def _refresh_driver_request(refresh_driver: str | None) -> str | None:
    """保留浏览器驱动，同时兼容旧任务使用的协议版本字段。"""
    return "browser_roxy" if refresh_driver == "browser_roxy" else _refresh_protocol_version(refresh_driver)


def deployment_unavailable(
    *, force_refresh: bool, driver: str | None = None, config_snapshot: dict | None = None,
) -> dict | None:
    """按已经解析的查活/刷新驱动在业务开始前检查部署能力。"""
    from core.runtime.capabilities import browser_operation_unavailable

    selected = (
        _resolve_refresh_driver(driver, config_snapshot=config_snapshot)
        if force_refresh else driver or _snapshot_value(config_snapshot, "live_check_driver")
    )
    return browser_operation_unavailable(
        selected or "protocol_current",
        browser_fallback_enabled=force_refresh and _roxy_fallback_enabled(config_snapshot),
        fallback_setting="LIVE_CHECK_ROXY_FALLBACK_ENABLED",
    )


def _resolve_protocol_identity(
    account_id: int,
    refresh_driver: str | None,
    config_snapshot: dict | None = None,
):
    """Load the optional stable identity only for the explicit Protocol v2 path."""
    if refresh_driver != "protocol_v2":
        return None
    from config import account as account_config

    mode = str(
        _snapshot_value(
            config_snapshot,
            "auth_profile_mode",
            getattr(account_config, "ACCOUNT_AUTH_PROFILE_MODE", "current"),
        )
        or "current"
    ).strip().lower()
    if mode in {"", "current"}:
        return None
    if mode != "account_stable":
        logger.warning("[查活] 不支持的 Protocol 设备画像模式 %r，保持当前会话随机画像", mode)
        return None
    from core.storage.accounts.auth import ensure_account_protocol_identity

    identity = ensure_account_protocol_identity(account_id)
    logger.info(
        "[查活][Protocol v2] 使用账号稳定设备画像 profile_ref=%s version=%s",
        identity.profile_ref,
        identity.profile_version,
    )
    return identity


def _report_protocol_v2_refresh(reporter: TaskReporter, result: dict) -> None:
    """Project Protocol v2's actual auth method without inventing OTP success."""
    auth_method = str(result.get("auth_method") or "protocol_v2")
    password_status = str(result.get("password_auth_status") or "")
    diagnostics = _safe_refresh_auth_diagnostics(result.get("auth_diagnostics")) or {}
    operation = diagnostics.get("operation")
    if operation == "password_email_fallback":
        operation = diagnostics.get("cause_operation")
    mfa_failed = not result.get("ok") and operation in {"mfa_issue_challenge", "mfa_verify"}
    if mfa_failed and not password_status and auth_method.startswith("password"):
        password_status = "rejected" if result.get("error") == "password_rejected_email_fallback_failed" else "verified"
    is_roxy_fallback = bool(result.get("fallback_used")) and result.get("validation_method") == "roxy_email_otp"
    uses_email = (
        "email" in auth_method
        or auth_method == "legacy_email_otp"
        or result.get("error") in {
            "password_rejected_email_fallback_failed",
            "passwordless_fallback_unavailable",
            "email_verification_required",
        }
    )
    uses_mfa = "mfa" in auth_method or mfa_failed

    if password_status == "rejected":
        reporter.stage(
            "login_password",
            "failed",
            "保存的账号密码被拒绝，保留密码错误证据",
            level="WARNING",
            detail={"auth_method": auth_method},
        )
    elif password_status == "verified":
        reporter.stage("login_password", "success", "账号密码验证通过")
    elif password_status == "skipped":
        reporter.stage("login_password", "skipped", "本次认证未提交账号密码，按邮箱验证码认证")
    elif auth_method == "legacy_email_otp":
        reporter.stage("login_password", "skipped", "账号没有保存密码，沿用邮箱认证")
    elif result.get("ok"):
        reporter.stage(
            "login_password",
            "success",
            "Roxy 浏览器认证已完成" if is_roxy_fallback else "协议认证已完成",
            detail={"auth_method": auth_method},
        )
    else:
        reporter.stage(
            "login_password",
            "failed",
            "Roxy 浏览器认证未完成" if is_roxy_fallback else "Protocol v2 密码认证未完成",
            level="ERROR",
            detail={
                "error": result.get("error"),
                "auth_method": auth_method,
                "auth_diagnostics": _safe_refresh_auth_diagnostics(result.get("auth_diagnostics")),
            },
        )

    reporter.stage(
        "mfa_challenge",
        "success" if uses_mfa and result.get("ok") else "skipped" if not uses_mfa else "failed",
        "TOTP MFA 验证已完成" if uses_mfa and result.get("ok") else "本次认证未进入 TOTP MFA" if not uses_mfa else "TOTP MFA 未完成",
        level="ERROR" if uses_mfa and not result.get("ok") else "INFO",
        detail={"auth_method": auth_method, **({"auth_diagnostics": diagnostics} if mfa_failed else {})},
    )
    reporter.stage(
        "email_otp",
        "success" if uses_email and (result.get("ok") or mfa_failed) else "skipped" if not uses_email else "failed",
        "邮箱验证码已通过" if uses_email and (result.get("ok") or mfa_failed) else "本次认证未使用邮箱验证码" if not uses_email else "邮箱验证码未完成",
        level="ERROR" if uses_email and not result.get("ok") and not mfa_failed else "INFO",
        detail={"auth_method": auth_method, "fallback_used": bool(result.get("fallback_used"))},
    )
    if result.get("ok"):
        reporter.stage("authenticate", "success", "账号认证已完成", detail={"auth_method": auth_method, "fallback_used": bool(result.get("fallback_used"))})
        reporter.stage("token", "success", "最新 AT 已获取并保存")


def _browser_live_check_probe(
    *,
    token: str,
    proxy: str | None,
    email: str | None = None,
    context_recorder=None,
    route_context: dict | None = None,
) -> dict:
    """延迟加载 Roxy AT probe，避免 current 路径提前初始化浏览器依赖。"""
    from core.accounts.liveness.roxy.probe import run_probe

    return run_probe(
        token=token,
        proxy=proxy,
        email=email,
        context_recorder=context_recorder,
        route_context=route_context,
    )


def _run_live_check(
    *,
    account_id: int,
    email: str,
    proxy: str | None,
    trigger: str,
    task_id: int | None = None,
    force_refresh: bool = False,
    driver: str | None = None,
    refresh_driver: str | None = None,
    release_queue_slot: bool = False,
    operation_context=None,
    finish_operation: bool = True,
    config_snapshot: dict | None = None,
    proxy_source: str | None = None,
    on_authenticated=None,
    result_writer=None,
    completion_auth: bool = False,
) -> dict:
    def save_result(account_id, result):
        return result_writer(result) if callable(result_writer) else db.update_account_liveness(account_id, result)

    account_route = None
    result = None
    route: dict = {}
    reporter = _reporter(task_id, operation_context, finish_operation=finish_operation)
    refresh_boundary: dict | None = None
    preflight_open = True
    network_open = False
    network_started = False
    debug_activation = None
    debug_cancelled = False
    try:
        _checkpoint(operation_context)
        with _LOCK:
            _RUNNING.add(int(account_id))
        if not db.mark_account_live_check_running(account_id):
            _append_log(email, "[查活] 账号已删除或查活状态已被重置，取消执行")
            reporter.finish(
                status="cancelled",
                message="账号已删除或查活状态已被重置",
            )
            return {"ok": False, "status": "failed", "error": "账号已删除或查活状态已被重置"}
        reporter.start(message="开始刷新账号 AT" if force_refresh else "开始验证账号 accessToken")
        # 入队时已经解析并冻结了 driver；直接调用 worker 的旧测试/兼容入口
        # 没有传值时才在这里读取当前配置，避免任务排队期间热改配置导致中途换路。
        selected_live_check_driver = None if force_refresh else (
            driver
            or _snapshot_value(config_snapshot, "live_check_driver")
            or resolve_driver()
        )
        selected_refresh_driver = _resolve_refresh_driver(
            refresh_driver, config_snapshot=config_snapshot,
        ) if force_refresh else None
        if selected_refresh_driver == "browser_roxy" and operation_context is not None:
            from config import account as account_config

            if bool(_snapshot_value(
                config_snapshot, "refresh_roxy_debug_enabled",
                getattr(account_config, "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED", False),
            )):
                from core.operations import debug as operation_debug

                debug_activation = operation_debug.activate(operation_context)
        reporter.stage("preflight", "success", "查活配置预检通过", detail={
            "force_refresh": bool(force_refresh),
            "live_check_driver": selected_live_check_driver,
            "refresh_driver": selected_refresh_driver,
        })
        preflight_open = False
        if selected_live_check_driver:
            reporter.note(
                stage="access_token",
                message=f"普通查活驱动：{selected_live_check_driver}",
                detail={"live_check_driver": selected_live_check_driver},
            )
        if selected_refresh_driver:
            reporter.note(
                stage="login_password",
                message=("刷新 AT 使用 Roxy 浏览器登录" if selected_refresh_driver == "browser_roxy"
                         else f"刷新 AT 协议版本：{_refresh_protocol_version(selected_refresh_driver)}"),
                detail={
                    "protocol_version": _refresh_protocol_version(selected_refresh_driver),
                    "token_refresh_driver": selected_refresh_driver,
                },
            )
        from core.proxy.account_routes import acquire_account_proxy

        def begin_network_stage() -> None:
            nonlocal network_open, network_started
            network_open = True
            if not network_started:
                reporter.stage("network", "running", "正在申请查活网络线路")
                network_started = True

        def acquire_retry_route(attempt: int) -> str:
            """网络预检每次重试都释放旧租约并申请新线路。"""
            nonlocal account_route, route, network_open
            begin_network_stage()
            if account_route is not None:
                account_route.release(reason=f"live-check-{account_id}-preflight-rotate")
            account_route = None
            route = {}
            purpose = "token-refresh" if force_refresh else "live-check"

            def report_retry(next_attempt: int, retry_limit: int, error: Exception) -> None:
                message = f"申请账号动作线路失败，准备换线重试 ({next_attempt}/{retry_limit})"
                _append_log(email, f"[查活] {message}: {type(error).__name__}: {str(error)[:220]}")
                reporter.note(
                    stage="network",
                    level="WARNING",
                    message=message,
                    detail={"error": f"{type(error).__name__}: {str(error)[:300]}"},
                )

            account_route = _acquire_account_proxy_with_retries(
                acquire_proxy=acquire_account_proxy,
                account_id=account_id,
                email=email,
                purpose=purpose,
                rotation_index=max(0, attempt - 1),
                retry_callback=report_retry,
                config_snapshot=config_snapshot,
                source=proxy_source or _snapshot_value(
                    config_snapshot,
                    "refresh_at_proxy_mode" if force_refresh else "live_check_proxy_mode",
                ),
            )
            route = account_route.public_dict()
            _append_log(
                email,
                f"[查活] 查活线路 {attempt}/4 "
                f"network_route={route.get('network_route')} proxy_mode={route.get('proxy_mode')} "
                f"proxy_used={route.get('proxy_used') or '-'} "
                f"fallback_reason={route.get('proxy_fallback_reason') or '-'}",
            )
            reporter.resource(
                "resource.acquired",
                message=f"已选择查活线路（第 {attempt}/4 次）",
                stage="network",
                detail=route,
            )
            reporter.stage("network", "success", "网络线路已就绪", detail={
                key: route.get(key)
                for key in ("network_route", "proxy_mode", "proxy_provider", "proxy_region")
            })
            network_open = False
            if force_refresh:
                reporter.stage("login_password", "running", "正在重新登录刷新 AT")
            return account_route.proxy_url

        def acquire_explicit_route() -> str:
            """有显式线路时只申请一次；空值改由统一代理池领取线路。"""
            nonlocal account_route, route, network_open
            if not str(proxy or "").strip():
                # 空字符串是旧调用方的“未提供线路”表现，不能把它传成
                # BrowserSession 直连；改走统一池领取并沿用本次查活链路。
                return acquire_retry_route(1)
            if account_route is None:
                begin_network_stage()
                account_route = acquire_account_proxy(
                    account_id=account_id,
                    email=email,
                    purpose="token-refresh" if force_refresh else "live-check",
                    explicit_proxy=proxy,
                    source=proxy_source or _snapshot_value(
                        config_snapshot,
                        "refresh_at_proxy_mode" if force_refresh else "live_check_proxy_mode",
                    ),
                )
                route = account_route.public_dict()
                reporter.resource("resource.acquired", "已选择指定账号线路", stage="network", detail=route)
                reporter.stage("network", "success", "网络线路已就绪")
                network_open = False
                if force_refresh:
                    reporter.stage("login_password", "running", "正在重新登录刷新 AT")
            return account_route.proxy_url

        # 查活和刷新 AT 是两个不同动作：
        # - 查活只验证数据库里的现有 AT，不发送邮箱 OTP，也不偷偷刷新 AT。
        # - 刷新 AT（force_refresh=True）才跳过旧 AT，按账号可用凭据重新登录。
        account = db.get_account(account_id) or {}
        if force_refresh and account.get("email_invalid") is True and selected_refresh_driver != "browser_roxy":
            selected_refresh_driver = "protocol_v2"
            reporter.note(
                stage="login_password",
                message="邮箱已失效，优先使用保存的密码及 2FA 登录",
                detail={"protocol_version": "v2", "token_refresh_driver": selected_refresh_driver},
            )
        protocol_identity = _resolve_protocol_identity(
            account_id, selected_refresh_driver, config_snapshot,
        )
        auth_context_recorder = None
        if selected_refresh_driver in {"protocol_v2", "browser_roxy"} or selected_live_check_driver in {"protocol_current", "browser_roxy"}:
            from config import account as account_config

            if bool(_snapshot_value(
                config_snapshot,
                "auth_raw_context_enabled",
                getattr(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False),
            )):
                from core.storage.accounts.auth import AuthContextRecorder

                recorder_kwargs = {
                    "account_id": account_id,
                    "protocol_identity": protocol_identity,
                    "action": "token_refresh" if force_refresh else "live_check",
                    "driver": selected_refresh_driver or selected_live_check_driver or "unknown",
                }
                if operation_context is not None:
                    # Native task IDs are not legacy account_action_tasks IDs.
                    # Bind raw auth context directly to the durable operation run.
                    auth_context_recorder = AuthContextRecorder(
                        operation_run_id=int(operation_context.run_id), **recorder_kwargs,
                    )
                else:
                    auth_context_recorder = AuthContextRecorder.from_account_action_task(
                        task_id, **recorder_kwargs,
                    )
        saved_access_token = str(account.get("access_token") or "").strip()
        saved_claims = token_claims(saved_access_token) if saved_access_token else {}
        last_probe_error = ""
        last_probe_error_category = None
        last_probe_http_status = None

        def invoke_refresh(call, *, driver_name: str):
            """在网络预检完成后建立远端请求边界，并执行一次刷新。"""
            nonlocal refresh_boundary
            if operation_context is None:
                return call(None)

            def begin_remote_request() -> None:
                nonlocal refresh_boundary
                if refresh_boundary is not None:
                    return
                request_id = f"token-refresh:{operation_context.run_id}:{uuid.uuid4().hex}"
                # 只有匿名网络预检完成后才持久化边界；不记录 Token、密码、代理或原始响应。
                operation_context.remote_request_started(
                    "token_refresh",
                    request_id=request_id,
                    detail={
                        "driver": str(driver_name or "unknown"),
                        "trigger": str(trigger or "manual"),
                        "protocol_version": _refresh_protocol_version(driver_name),
                    },
                )
                refresh_boundary = {
                    "action": "token_refresh",
                    "request_id": request_id,
                    "receipt_outcome": "started",
                    "pending_confirmation": False,
                }
            try:
                remote_result = call(begin_remote_request)
                # 兼容适配器和未调用回调的测试替身保持保守策略：只有明确的预检错误
                # 才不打开“结果未知”的安全栅栏。
                if refresh_boundary is None and not _refresh_result_before_remote_boundary(remote_result):
                    begin_remote_request()
            except account_task_store.OperationLeaseLost:
                raise
            except OperationCancelled as exc:
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "unknown",
                    {"response_observed": False, "cancelled": True},
                )
                raise exc
            except Exception as exc:
                if refresh_boundary is None:
                    # 适配器未报告阶段就抛错时，保守地按远端结果未知处理。
                    begin_remote_request()
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "unknown",
                    {
                        "response_observed": False,
                        "exception_type": type(exc).__name__,
                    },
                )
                return _mark_refresh_reconcile_required(
                    {
                        "error": "refresh_driver_exception",
                        "error_category": "runtime",
                        "auth_diagnostics": {
                            "operation": "protocol_v2_auth",
                            "failure_kind": "runtime_exception",
                            "exception_type": type(exc).__name__[:80],
                        },
                    },
                )

            if not isinstance(remote_result, dict):
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "unknown",
                    {"response_observed": True, "response_type": type(remote_result).__name__},
                )
                return _mark_refresh_reconcile_required({"error": "refresh_result_invalid"})
            if _refresh_result_not_submitted(remote_result):
                _record_refresh_receipt(
                    operation_context, refresh_boundary, "not_submitted",
                    {
                        "mutation_submitted": False,
                        "action_dispatched": False,
                        "cause_code": _safe_refresh_cause_code(remote_result),
                    },
                )
                # 旧认证没有提交，浏览器兜底应建立自己的全新 intent。
                refresh_boundary = None
                return remote_result
            if _refresh_result_is_unknown(remote_result) and not _refresh_result_before_remote_boundary(remote_result):
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "unknown",
                    {"response_observed": _unknown_refresh_response_observed(remote_result), "status": remote_result.get("status")},
                )
                return _mark_refresh_reconcile_required(remote_result)
            if remote_result.get("ok") and str(remote_result.get("access_token") or "").strip():
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "response_received",
                    {
                        "response_observed": True,
                        "remote_result_confirmed": True,
                        "status": remote_result.get("status"),
                    },
                )
                return remote_result
            if _refresh_result_is_rejected(remote_result):
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "rejected",
                    {
                        "response_observed": True,
                        "status": remote_result.get("status"),
                        "error_code": remote_result.get("error_code") or remote_result.get("error"),
                    },
                )
                return remote_result
            if _refresh_result_before_remote_boundary(remote_result):
                return remote_result
            _record_refresh_receipt(
                operation_context,
                refresh_boundary,
                "unknown",
                {"response_observed": _unknown_refresh_response_observed(remote_result), "status": remote_result.get("status")},
            )
            return _mark_refresh_reconcile_required(remote_result)
        if saved_access_token and not force_refresh:
            probe_attempts = 4 if proxy is None else 1
            _append_log(email, "[查活] 优先验证现有 accessToken；有效则无需重复发送邮箱验证码")
            for attempt in range(1, probe_attempts + 1):
                _checkpoint(operation_context)
                selected_proxy = acquire_retry_route(attempt) if proxy is None else acquire_explicit_route()
                reporter.stage(
                    "access_token",
                    "running",
                    message="优先在线验证现有 AT；有效则不发送邮箱验证码",
                    detail={
                        "attempt_no": attempt,
                        "token_expires_at": saved_claims.get("token_expires_at"),
                    },
                )
                probe = run_probe(
                    driver=selected_live_check_driver,
                    probe=check_account_plan,
                    token=saved_access_token,
                    proxy=selected_proxy,
                    email=email,
                    max_attempts=1,
                    browser_probe=_browser_live_check_probe,
                    context_recorder=auth_context_recorder,
                    route_context=route,
                )
                try:
                    last_probe_http_status = int(probe.get("http_status"))
                except (TypeError, ValueError):
                    last_probe_http_status = None
                last_probe_error_category = probe.get("error_category")
                if probe.get("ok"):
                    result = {
                        "ok": True,
                        "status": "live",
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "http_status": last_probe_http_status or 200,
                        "access_token": saved_access_token,
                        "session": {
                            "account": {"planType": probe.get("current_plan_type")},
                        },
                        "proxy_used": selected_proxy or None,
                        "validation_method": "access_token",
                        "live_check_driver": probe.get("live_check_driver") or selected_live_check_driver,
                    }
                    _append_log(
                        email,
                        f"[查活] accessToken 验证成功：HTTP {probe.get('http_status') or 200} "
                        f"plan={probe.get('current_plan_type') or 'unknown'}",
                    )
                    reporter.stage(
                        "access_token",
                        "success",
                        message="AT 在线验证成功",
                        detail={
                            "http_status": probe.get("http_status") or 200,
                            "plan": probe.get("current_plan_type") or "unknown",
                        },
                    )
                    break

                unusable_code = detect_account_unusable_text(
                    f"{probe.get('error') or ''} {probe.get('response_preview') or ''}"
                )
                if unusable_code:
                    result = {
                        "ok": False,
                        "status": "deactivated",
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "error": unusable_code,
                        "http_status": last_probe_http_status,
                        "validation_method": "access_token",
                        "error_category": probe.get("error_category"),
                        "live_check_driver": probe.get("live_check_driver") or selected_live_check_driver,
                    }
                    break

                _append_log(
                    email,
                    f"[查活] accessToken 验证未通过（{attempt}/{probe_attempts}）："
                    f"{str(probe.get('error') or '未知错误')[:220]}",
                )
                last_probe_error = str(probe.get("error") or "现有 accessToken 无法验证")[:220]
                reporter.note(
                    stage="access_token",
                    level="WARNING",
                    message=f"AT 在线验证未通过（{attempt}/{probe_attempts}）",
                    detail={
                        "http_status": probe.get("http_status"),
                        "error_category": probe.get("error_category"),
                        "error": probe.get("error"),
                    },
                )
                if not _token_probe_retryable(probe) or attempt >= probe_attempts:
                    _append_log(email, "[查活] 现有 Token 无法确认状态；不会自动登录，请单独点击“刷新AT”")
                    break

            if result is None:
                probe_driver = probe.get("live_check_driver") or selected_live_check_driver
                reporter.stage(
                    "access_token", "failed", "AT 在线验证未通过",
                    level="ERROR",
                    detail={
                        "http_status": last_probe_http_status,
                        "error_category": last_probe_error_category,
                        "error": last_probe_error,
                    },
                )
                result = {
                    "ok": False,
                    "status": "failed",
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                    "error": "现有 accessToken 已过期或失效，请点击“刷新AT”",
                    "http_status": last_probe_http_status,
                    "validation_method": "access_token",
                    "probe_error": last_probe_error,
                    "error_category": probe.get("error_category"),
                    "live_check_driver": probe_driver,
                    "token_expired": bool(
                        probe.get("token_expired") is True
                        or probe.get("needs_live_check") is True
                        or saved_claims.get("token_expired") is True
                    ),
                    "needs_live_check": bool(probe.get("needs_live_check")),
                }
        elif not force_refresh:
            result = {
                "ok": False,
                "status": "failed",
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "error": "账号没有 accessToken，请点击“刷新AT”后再查活",
                "validation_method": "access_token",
            }
            reporter.stage("access_token", "failed", result["error"], level="ERROR", detail={"validation_method": "access_token"})

        if result is None:
            reporter.note(
                stage="reauth",
                message=(
                    "按账号可用凭据重新登录刷新 AT"
                    if force_refresh
                    else "查活未通过；如需获取新 AT，请单独点击“刷新AT”"
                ),
            )

        if not force_refresh and result is not None:
            result.setdefault("live_check_driver", selected_live_check_driver)

        if result is None and selected_refresh_driver == "browser_roxy":
            from core.accounts.liveness.roxy.flow import refresh_access_token

            selected_proxy = acquire_retry_route(1) if proxy is None else acquire_explicit_route()
            _append_log(email, "[查活][Roxy] 开始浏览器登录刷新 AT")
            _checkpoint(operation_context, "Roxy 登录刷新 AT 前检查取消状态")
            result = invoke_refresh(
                lambda on_remote_request_started: refresh_access_token(
                    email,
                    proxy=selected_proxy,
                    **({"context_recorder": auth_context_recorder} if auth_context_recorder is not None else {}),
                    on_remote_request_started=on_remote_request_started,
                    **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
                ),
                driver_name="browser_roxy",
            )
            if isinstance(result, dict):
                result.setdefault("live_check_driver", "browser_roxy")
                result.setdefault("auth_method", "roxy_browser")
        elif result is None and proxy is None:
            # WebUI 默认调用由账号代理配置选路，重试时允许真正轮换线路。
            _append_log(email, f"[查活] 开始后台执行 trigger={trigger}，网络预检失败时将轮换代理")
            if selected_refresh_driver == "protocol_v2":
                from core.accounts.liveness.protocol.v2 import refresh_access_token

                _checkpoint(operation_context, "刷新 AT 前检查取消状态")
                result = invoke_refresh(
                    lambda on_remote_request_started: refresh_access_token(
                        email,
                        proxy=None,
                        proxy_supplier=acquire_retry_route,
                        identity=protocol_identity,
                        context_recorder=auth_context_recorder,
                        on_remote_request_started=on_remote_request_started,
                        **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
                    ),
                    driver_name=selected_refresh_driver,
                )
            else:
                _checkpoint(operation_context, "邮箱登录刷新 AT 前检查取消状态")
                result = invoke_refresh(
                    lambda on_remote_request_started: check_account_liveness(
                        email,
                        proxy=None,
                        clear_log=False,
                        proxy_supplier=acquire_retry_route,
                        **({"on_remote_request_started": on_remote_request_started} if on_remote_request_started else {}),
                        **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
                    ),
                    driver_name=selected_refresh_driver or "legacy_email_otp",
                )
        elif result is None:
            # 有效显式线路继续复用调用方租约；空字符串按未提供线路走统一代理池。
            selected_proxy = acquire_explicit_route()
            _append_log(
                email,
                "[查活] 开始后台执行 "
                f"trigger={trigger} network_route={route.get('network_route')} "
                f"proxy_mode={route.get('proxy_mode')} proxy_used={route.get('proxy_used') or '-'} "
                f"fallback_reason={route.get('proxy_fallback_reason') or '-'}",
            )
            if selected_refresh_driver == "protocol_v2":
                from core.accounts.liveness.protocol.v2 import refresh_access_token

                _checkpoint(operation_context, "刷新 AT 前检查取消状态")
                result = invoke_refresh(
                    lambda on_remote_request_started: refresh_access_token(
                        email,
                        proxy=selected_proxy,
                        identity=protocol_identity,
                        context_recorder=auth_context_recorder,
                        on_remote_request_started=on_remote_request_started,
                        **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
                    ),
                    driver_name=selected_refresh_driver,
                )
            else:
                _checkpoint(operation_context, "邮箱登录刷新 AT 前检查取消状态")
                result = invoke_refresh(
                    lambda on_remote_request_started: check_account_liveness(
                        email,
                        proxy=selected_proxy,
                        clear_log=False,
                        **({"on_remote_request_started": on_remote_request_started} if on_remote_request_started else {}),
                        **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
                    ),
                    driver_name=selected_refresh_driver or "legacy_email_otp",
                )
        if refresh_boundary is not None:
            _checkpoint(operation_context, "刷新 AT 请求完成后检查取消状态")
        if (
            not result.get("ok")
            and result.get("status") != "deactivated"
            and not _refresh_result_is_unknown(result)
            and (
                refresh_boundary is None
                or refresh_boundary.get("receipt_outcome") == "rejected"
            )
            and (bool(saved_access_token) or completion_auth)
            and force_refresh
            and selected_refresh_driver != "browser_roxy"
            and _roxy_fallback_enabled(config_snapshot)
            and result.get("roxy_fallback_allowed", True)
        ):
            from core.accounts.liveness.roxy.flow import available as roxy_available, refresh_access_token
            if roxy_available():
                if debug_activation is None and operation_context is not None:
                    from config import account as account_config
                    from core.operations import debug as operation_debug

                    if bool(_snapshot_value(
                        config_snapshot, "refresh_roxy_debug_enabled",
                        getattr(account_config, "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED", False),
                    )):
                        debug_activation = operation_debug.activate(operation_context)
                reporter.note(
                    stage="roxy_fallback",
                    level="WARNING",
                    message="协议登录未通过，启用 Roxy 浏览器 NextAuth 兜底",
                    detail={"protocol_error": result.get("error")},
                )
                _append_log(email, "[查活] 协议登录未通过，启用 Roxy 浏览器 NextAuth 兜底")
                roxy_proxy = account_route.proxy_url if account_route is not None else proxy
                if proxy is None and account_route is not None:
                    # A protocol failure can be caused by the current exit
                    # (403/TLS/proxy corruption). Do not send the browser
                    # fallback through that same lease; rotate once while
                    # keeping explicit caller-selected proxies untouched.
                    if _is_proxy_transport_failure(result):
                        account_route.release(
                            reason=f"live-check-{account_id}-roxy-fallback-rotate",
                            fault=True,
                        )
                    else:
                        account_route.release(reason=f"live-check-{account_id}-roxy-fallback-rotate")
                    account_route = None
                    route = {}

                    def report_fallback_retry(next_attempt: int, retry_limit: int, error: Exception) -> None:
                        message = f"Roxy 兜底申请新线路失败，准备换线重试 ({next_attempt}/{retry_limit})"
                        _append_log(email, f"[查活] {message}: {type(error).__name__}: {str(error)[:220]}")
                        reporter.note(
                            stage="network",
                            level="WARNING",
                            message=message,
                            detail={"error": f"{type(error).__name__}: {str(error)[:300]}"},
                        )

                    begin_network_stage()
                    account_route = _acquire_account_proxy_with_retries(
                        acquire_proxy=acquire_account_proxy,
                        account_id=account_id,
                        email=email,
                        purpose="token-refresh",
                        rotation_index=4,
                        retry_callback=report_fallback_retry,
                        config_snapshot=config_snapshot,
                        source=proxy_source or _snapshot_value(
                            config_snapshot, "refresh_at_proxy_mode",
                        ),
                    )
                    route = account_route.public_dict()
                    reporter.resource(
                        "resource.acquired",
                        message="Roxy 兜底已切换新认证线路",
                        stage="network",
                        detail=route,
                    )
                    reporter.stage(
                        "network",
                        "success",
                        "Roxy 兜底认证线路已就绪",
                        detail={
                            key: route.get(key)
                            for key in ("network_route", "proxy_mode", "proxy_provider", "proxy_region")
                        },
                    )
                    network_open = False
                    roxy_proxy = account_route.proxy_url

                def run_roxy_refresh(on_remote_request_started):
                    if on_remote_request_started:
                        on_remote_request_started()
                    refresh_kwargs = {"proxy": roxy_proxy}
                    if auth_context_recorder is not None:
                        refresh_kwargs["context_recorder"] = auth_context_recorder
                    return refresh_access_token(email, **refresh_kwargs)

                roxy_result = invoke_refresh(
                    run_roxy_refresh,
                    driver_name="roxy_browser",
                )
                if isinstance(roxy_result, dict):
                    # Keep the task-center result tied to the actual driver after
                    # the fallback; otherwise a Roxy outcome is projected as a
                    # Protocol v2 password outcome and becomes misleading to
                    # operators.
                    roxy_result.setdefault("fallback_used", True)
                    roxy_result.setdefault("auth_method", "roxy_browser")
                    roxy_result.setdefault("live_check_driver", "browser_roxy")
                result = roxy_result
        if refresh_boundary is not None:
            _checkpoint(operation_context, "刷新 AT 最终结果写回前检查取消状态")
        if isinstance(result, dict):
            _attach_auth_projection(
                result,
                auth_method=str(
                    result.get("auth_method")
                    or result.get("live_check_driver")
                    or ("legacy_email_otp" if force_refresh else "access_token")
                ),
            )
        if force_refresh and _refresh_result_is_unknown(result):
            result.update(_mark_refresh_reconcile_required(result))
        if selected_refresh_driver:
            result.setdefault("token_refresh_driver", selected_refresh_driver)
            result.setdefault("protocol_version", _refresh_protocol_version(selected_refresh_driver))
        result.update({
            "proxy_provider": route.get("proxy_provider"),
            "proxy_region": route.get("proxy_region"),
            "network_route": route.get("network_route"),
            "proxy_used": route.get("proxy_used"),
        })
        try:
            writeback_ok = bool(save_result(account_id, result))
        except Exception:
            if refresh_boundary and refresh_boundary.get("pending_confirmation"):
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "local_commit_required",
                    {
                        "remote_result_confirmed": True,
                        "local_business_writeback_confirmed": False,
                        "local_readback_confirmed": False,
                        "response_observed": True,
                    },
                )
            raise
        if refresh_boundary and refresh_boundary.get("pending_confirmation"):
            refresh_confirmed = _confirm_refresh_receipt(
                context=operation_context,
                boundary=refresh_boundary,
                result=result,
                account_id=account_id,
                writeback_ok=writeback_ok,
            )
            if not refresh_confirmed:
                try:
                    save_result(account_id, result)
                except Exception:
                    logger.exception("[查活] 远端刷新未确认状态写回失败: account_id=%s", account_id)
        if force_refresh:
            if selected_refresh_driver == "browser_roxy":
                from core.accounts.liveness.roxy.refresh_errors import ROXY_LOGIN_CAUSES, roxy_login_failure_code

                error_message = str(result.get("error") or "")
                page_error = result.get("error_code") in {
                    "password_change_required", "password_page_error", "auth_operation_timeout", "auth_context_missing",
                    "roxy_proxy_tunnel_failed",
                    "roxy_password_prepare_timeout",
                }
                login_cause = ROXY_LOGIN_CAUSES.get(result.get("error_code") or roxy_login_failure_code(error_message))
                failure_message = error_message if page_error else login_cause[1] if login_cause else "Roxy 浏览器登录未完成"
                reporter.stage(
                    "authenticate", "success" if result.get("ok") else "failed",
                    "Roxy 浏览器登录已完成" if result.get("ok") else failure_message,
                    level="INFO" if result.get("ok") else "ERROR",
                    detail={"auth_method": result.get("auth_method"), "error": result.get("error"),
                            "error_code": _safe_refresh_cause_code(result)},
                )
                if result.get("ok"):
                    reporter.stage("token", "success", "最新 AT 已获取并保存")
            elif selected_refresh_driver == "protocol_v2":
                _report_protocol_v2_refresh(reporter, result)
            elif result.get("ok"):
                reporter.stage("login_password", "success", "邮箱登录已完成")
                reporter.stage("email_otp", "success", "登录验证已通过")
                reporter.stage("token", "success", "最新 AT 已获取并保存")
            else:
                reporter.stage(
                    "login_password", "failed", "邮箱登录刷新 AT 未完成",
                    level="ERROR", detail={"error": result.get("error")},
                )
        if result.get("ok"):
            if result.get("validation_method") == "access_token":
                _append_log(email, "[查活] 完成：账号正常，现有 accessToken 已通过在线验证")
            else:
                _append_log(email, "[查活] 完成：账号正常，已重新登录刷新 accessToken")
        elif result.get("status") == "deactivated":
            _append_log(email, f"[查活] 完成：账号已废 {result.get('error') or ''}")
        else:
            _append_log(email, f"[查活] 完成：失败 {result.get('error') or ''}")
        final_status = "success" if result.get("ok") else (
            "deactivated" if result.get("status") == "deactivated"
            else "failed"
        )
        reporter.finish(
            status=final_status,
            message=(
                "账号正常，AT 在线验证成功"
                if result.get("ok") and result.get("validation_method") == "access_token"
                else "账号正常，已重新登录刷新 AT"
                if result.get("ok")
                else "账号已确认停用"
                if final_status == "deactivated"
                else f"查活失败：{_safe_refresh_cause_code(result) or '认证未完成'}"
            ),
            error=result.get("error") if not result.get("ok") else None,
            result_summary={
                "ok": bool(result.get("ok")),
                "status": result.get("status"),
                "http_status": result.get("http_status"),
                "error_category": result.get("error_category"),
                "cause_code": _safe_refresh_cause_code(result),
                "reconcile_required": bool(result.get("reconcile_required")),
                "manual_reconcile": bool(result.get("manual_reconcile")),
                "next_action": result.get("next_action"),
                "checked_at": result.get("checked_at"),
                "plan": (result.get("session") or {}).get("account", {}).get("planType"),
                "live_check_driver": result.get("live_check_driver"),
                "token_refresh_driver": selected_refresh_driver,
                "protocol_version": _refresh_protocol_version(selected_refresh_driver),
                "auth_method": result.get("auth_method"),
                "password_auth_status": result.get("password_auth_status"),
                "password_action_dispatched": result.get("password_action_dispatched"),
                "fallback_used": result.get("fallback_used"),
                "debug_browser_kept": bool(result.get("debug_browser_kept")),
                "auth_diagnostics": _safe_refresh_auth_diagnostics(result.get("auth_diagnostics")),
                "fingerprint": result.get("fingerprint"),
                "token_expired": result.get("token_expired"),
                "needs_live_check": result.get("needs_live_check"),
            },
            route={**route, **{key: result.get(key) for key in ("network_route", "proxy_provider", "proxy_region", "proxy_used")}},
            validation_method=result.get("validation_method"),
        )
        return result
    except account_task_store.OperationLeaseLost:
        # The gateway owns lease-loss fencing and request-unknown conversion.
        # Do not turn a lost native fence into an ordinary service failure.
        debug_cancelled = True
        raise
    except OperationCancelled as exc:
        debug_cancelled = True
        receipt_outcome = str((refresh_boundary or {}).get("receipt_outcome") or "")
        remote_unknown = bool(
            force_refresh
            and refresh_boundary
            and receipt_outcome not in {"rejected", "not_submitted"}
        )
        if remote_unknown and receipt_outcome not in {"unknown", "local_commit_required", "confirmed"}:
            _record_refresh_receipt(
                operation_context,
                refresh_boundary,
                "unknown",
                {"response_observed": receipt_outcome == "response_received", "cancelled": True},
            )
        result = {
            "ok": False,
            "status": "failed" if remote_unknown else "cancelled",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": (
                "刷新 AT 请求已跨越远端边界，取消结果待确认"
                if remote_unknown else str(exc) or "查活任务已取消"
            ),
            "cancelled": not remote_unknown,
            "error_code": "refresh_cancelled" if remote_unknown else "cancelled",
        }
        if remote_unknown:
            result.update({
                "reconcile_required": True,
                "manual_reconcile": True,
                "next_action": "manual_reconcile",
            })
        try:
            save_result(account_id, result)
        except Exception:
            logger.exception("[查活] 取消状态写回失败: account_id=%s", account_id)
        if preflight_open:
            reporter.note("查活在预检完成前取消", stage="preflight", level="WARNING", detail={"cancelled": True})
        reporter.finish(
            status="failed" if remote_unknown else "cancelled",
            message="刷新 AT 请求结果待确认，需人工对账" if remote_unknown else "查活任务已取消",
            error=result["error"],
            result_summary={
                "cause_code": result["error_code"],
                "reconcile_required": remote_unknown,
                "manual_reconcile": remote_unknown,
                "next_action": result.get("next_action"),
            },
        )
        return result
    except Exception as exc:
        receipt_outcome = str((refresh_boundary or {}).get("receipt_outcome") or "")
        remote_unknown = bool(
            force_refresh
            and refresh_boundary
            and receipt_outcome not in {"rejected", "not_submitted"}
        )
        if remote_unknown and receipt_outcome not in {"unknown", "local_commit_required", "confirmed"}:
            try:
                _record_refresh_receipt(
                    operation_context,
                    refresh_boundary,
                    "unknown",
                    {"response_observed": receipt_outcome == "response_received"},
                )
            except Exception:
                logger.exception("[查活] 远端刷新异常回执写入失败: account_id=%s", account_id)
        unknown = bool(force_refresh and (_refresh_exception_is_unknown(exc) or remote_unknown))
        result = {
            "ok": False,
            "status": "failed",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            "error_code": str(
                getattr(exc, "code", "") or getattr(exc, "error_code", "") or ""
            ).strip() or (
                "refresh_local_commit_failed" if receipt_outcome == "local_commit_required"
                else "refresh_driver_exception"
            ),
            "auth_method": "legacy_email_otp" if force_refresh else "access_token",
        }
        if unknown:
            result.update({
                "reconcile_required": True,
                "manual_reconcile": True,
                "next_action": "manual_reconcile",
            })
        _attach_auth_projection(
            result,
            auth_method=result["auth_method"],
        )
        try:
            save_result(account_id, result)
        except Exception:
            logger.exception("[查活] 写入异常状态失败: account_id=%s", account_id)
        logger.exception("[查活] 后台异常: %s", email)
        try:
            _append_log(email, f"[查活] 后台异常：{result['error']}")
        except Exception:
            pass
        if preflight_open:
            reporter.stage(
                "preflight", "failed", "查活预检失败",
                level="ERROR", detail={"error": result["error"]},
            )
        elif network_open:
            reporter.stage(
                "network", "failed", "查活网络线路申请失败",
                level="ERROR", detail={"error": result["error"]},
            )
        else:
            reporter.stage(
                "login_password" if force_refresh else "access_token",
                "failed",
                "刷新 AT 后台异常" if force_refresh else "AT 验证后台异常",
                level="ERROR",
                detail={"error": result["error"]},
            )
        reporter.finish(
            status="failed",
            message="刷新 AT 结果待确认，需人工对账" if unknown else "查活后台执行异常",
            error=result["error"],
            route=route,
            result_summary={
                "cause_code": _safe_refresh_cause_code(result),
                "reconcile_required": unknown,
                "manual_reconcile": unknown,
                "next_action": result.get("next_action"),
            },
        )
        return result
    finally:
        if account_route is not None:
            if _is_proxy_transport_failure(result):
                account_route.release(reason=f"live-check-{account_id}", fault=True)
            else:
                account_route.release(reason=f"live-check-{account_id}")
        with _LOCK:
            _RUNNING.discard(int(account_id))
        if release_queue_slot:
            _QUEUE_SLOTS.release()
        if debug_activation is not None:
            from core.operations import debug as operation_debug

            operation_debug.deactivate(
                debug_activation,
                status="cancelled" if debug_cancelled else "success" if (result or {}).get("ok") else "failed",
            )


def _numeric_batch_id(value: str | int | None) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip().isdigit() else None
    except (TypeError, ValueError):
        return None


def _native_response(submitted: dict, *, task_type: str, account_id: int, email: str, trigger: str) -> dict:
    accepted = bool(submitted.get("accepted"))
    response = {
        "accepted": accepted,
        # A newly created or idempotently reused item is accepted, not busy.
        # The gateway's busy rejection is the only conflict signal.
        "busy": bool(submitted.get("busy")) and not accepted,
        "account_id": account_id,
        "email": email,
        "status": submitted.get("status") or ("queued" if accepted else "failed"),
        "trigger": trigger,
        "task_type": task_type,
        "task_id": submitted.get("task_id"),
        "run_id": submitted.get("run_id"),
        "source_system": submitted.get("source_system"),
        "source_id": submitted.get("source_id"),
        "reused": bool(submitted.get("reused")),
    }
    if submitted.get("error"):
        response["error"] = submitted["error"]
    return response


def _cancel_unclaimed_native_run(run_id: int | None, reason: str) -> None:
    if not run_id:
        return
    try:
        from core.storage.operations import runtime as operation_runtime_store

        operation_runtime_store.request_run_cancel(int(run_id), reason=reason)
    except Exception:
        logger.exception("[查活] 取消孤立 durable run 失败: run_id=%s", run_id)


def _handle_live_operation(context):
    if context.account_id is None:
        _reporter(context.task_id, context).stage("preflight", "failed", "查活缺少账号", level="ERROR")
        context.finish(status="failed", message="查活缺少账号", error="查活缺少账号")
        return None
    data = context.run.get("data") if isinstance(context.run.get("data"), dict) else {}
    unavailable = deployment_unavailable(
        force_refresh=bool(data.get("force_refresh")),
        driver=data.get("refresh_driver") if data.get("force_refresh") else data.get("driver"),
        config_snapshot=context.config_snapshot,
    )
    if unavailable:
        return account_task_store.OperationResult.failed(unavailable["error"], unavailable)
    account = db.get_account(int(context.account_id))
    email = str((account or {}).get("email") or context.email or "").strip()
    # Email-change post-checks use a distinct durable resource family so the
    # child can be queued while the parent is settling.  Normal live-check
    # and token-refresh runs still carry ``openai_interactive`` in their run
    # row; using the frozen run family here keeps the lease fence consistent
    # for both paths.
    with context.lease(resource_family=context.resource_family):
        if data.get("completion_auth"):
            from core.accounts.completion import active_registration_job

            if active_registration_job(int(context.account_id), email):
                raise account_task_store.OperationLeaseUnavailable(
                    "该账号仍有注册任务正在执行，等待注册结束后补全账号"
                )
        with operation_log_context(context, stage="preflight"):
            _run_live_check(
                account_id=int(context.account_id),
                email=email,
                proxy=None,
                trigger=str(context.run.get("trigger") or "manual"),
                task_id=int(context.task_id),
                force_refresh=bool(data.get("force_refresh")),
                driver=data.get("driver") or None,
                refresh_driver=data.get("refresh_driver") or None,
                release_queue_slot=False,
                operation_context=context,
                config_snapshot=context.config_snapshot,
                proxy_source=str(
                    data.get("proxy_source")
                    or _snapshot_value(
                        context.config_snapshot,
                        "refresh_at_proxy_mode" if data.get("force_refresh") else "live_check_proxy_mode",
                    )
                    or ""
                ).strip() or None,
                **({"completion_auth": True} if data.get("completion_auth") else {}),
            )
    return None


def _retry_token_refresh_operation(task: dict) -> dict:
    """重跑刷新 AT 时固定当前配置，历史 Run 仍保留原驱动和请求证据。"""
    from core.storage.operations import store as operation

    if account_task_store.operation_is_deactivated(task):
        return {"accepted": False, "busy": False, "deactivated": True, "error": "账号已废号，不能重跑"}
    if str(task.get("status") or "").strip().lower() in {
        "queued", "running", "cancelling", "settling", "stopping", "waiting",
    }:
        return {"accepted": False, "busy": True, "error": "任务仍在执行"}
    task_id = int(task.get("id") or 0)
    if not task_id:
        return {"accepted": False, "busy": False, "error": "任务缺少 id"}
    snapshot = account_task_store.normalize_config_snapshot(
        get_config_snapshot(), allowlist=LIVE_CONFIG_ALLOWLIST,
    )
    refresh_driver = _resolve_refresh_driver(config_snapshot=snapshot)
    unavailable = deployment_unavailable(force_refresh=True, driver=refresh_driver, config_snapshot=snapshot)
    if unavailable:
        return unavailable
    try:
        run = operation.retry_runtime_task(
            task_id, trigger="manual_retry",
            data={
                "retry_action": "manual_retry", "force_refresh": True,
                "refresh_driver": _refresh_driver_request(refresh_driver),
                "config_snapshot": snapshot,
                "proxy_source": snapshot.get("refresh_at_proxy_mode") or "",
            },
        )
    except (LookupError, ValueError) as exc:
        return {
            "accepted": False, "busy": False, "error": str(exc),
            "deactivated": "账号已废号" in str(exc),
        }
    account_task_store.notify_dispatch()
    return {
        "accepted": True, "busy": False, "reused": False,
        "task_id": task_id, "run_id": int(run["id"]),
        "account_id": int(task.get("account_id") or 0) or None,
        "email": str(task.get("email_snapshot") or ""),
        "status": "queued", "source_system": "native_operations",
    }


def _retry_live_check_operation(task: dict) -> dict:
    """原生查活重试沿用历史快照，入队前验证其浏览器需求。"""
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    snapshot = data.get("config_snapshot") if isinstance(data.get("config_snapshot"), dict) else None
    unavailable = deployment_unavailable(
        force_refresh=False,
        driver=data.get("driver") or _snapshot_value(snapshot, "live_check_driver"),
        config_snapshot=snapshot,
    )
    if unavailable:
        return unavailable
    return account_task_store.default_operation_retry(task)


def register_operation_handlers() -> bool:
    """Register maintenance handlers; runtime owns starting the one dispatcher."""
    register = getattr(account_task_store, "register_operation_handler", None)
    if not callable(register):
        return False
    register(
        "live_check",
        _handle_live_operation,
        source_systems=("native_operations",),
        config_allowlist=LIVE_CONFIG_ALLOWLIST,
        retry_handler=_retry_live_check_operation,
    )
    register(
        "token_refresh",
        _handle_live_operation,
        source_systems=("native_operations",),
        config_allowlist=LIVE_CONFIG_ALLOWLIST,
        retry_handler=_retry_token_refresh_operation,
    )
    return True


def start_dispatcher() -> bool:
    if not register_operation_handlers():
        return False
    starter = getattr(account_task_store, "start_dispatcher", None)
    return bool(starter()) if callable(starter) else False


def register_maintenance_operation_handlers() -> bool:
    """Runtime entrypoint for all maintenance handler registrations.

    B's runtime hook can call this one function during startup; each service
    remains the owner of its own handler implementation and no second
    dispatcher is created here.
    """
    from core.accounts.deactivation import mail_scan as deactivation_mail_service
    from core.accounts.email_change import service as email_change_service
    from core.extract_link import service as extract_link_service
    from core.accounts.plans import service as plan_check_service

    from core.accounts.inspection import service as account_inspection_service

    registered = (
        account_inspection_service.register_operation_handlers(),
        register_operation_handlers(),
        plan_check_service.register_operation_handlers(),
        deactivation_mail_service.register_operation_handlers(),
        extract_link_service.register_operation_handlers(),
        email_change_service.register_operation_handlers(),
    )
    return all(registered)


def start_maintenance_dispatcher() -> bool:
    if not register_maintenance_operation_handlers():
        return False
    starter = getattr(account_task_store, "start_dispatcher", None)
    return bool(starter()) if callable(starter) else False


def _submit_native_live(
    *, account_id: int, email: str, trigger: str, task_type: str,
    force_refresh: bool, driver: str | None, refresh_driver: str | None,
    explicit_proxy_requested: bool, batch_id: str | None, idempotency_key: str | None,
    resource_family: str = "openai_interactive",
    allow_missing_token: bool = False,
    config_snapshot: dict | None = None,
) -> dict:
    register_operation_handlers()
    key = str(idempotency_key or "").strip() or None
    source_id = (
        f"maintenance:{task_type}:{account_id}:{key}"
        if key else f"maintenance:{task_type}:{account_id}:{uuid.uuid4().hex}"
    )
    return account_task_store.submit_durable_operation(
        task_type=task_type,
        account_id=account_id,
        email=email,
        trigger=trigger,
        source_system="native_operations",
        source_id=source_id,
        idempotency_key=key,
        batch_id=_numeric_batch_id(batch_id),
        resource_family=str(resource_family or "openai_interactive"),
        data={
            "force_refresh": bool(force_refresh),
            # 标记补全认证范围，避免带 token 字样的字段被统一脱敏规则丢弃。
            **({"completion_auth": True} if force_refresh and allow_missing_token else {}),
            "driver": driver,
            "refresh_driver": refresh_driver,
            "proxy_source": _captured_proxy_source(
                "token-refresh" if force_refresh else "live-check"
            ),
            # Explicit proxy credentials must not be persisted in operation data.
            "explicit_proxy_requested": bool(explicit_proxy_requested),
        },
        **({"config_snapshot": config_snapshot, "config_allowlist": (*LIVE_CONFIG_ALLOWLIST, "config_snapshot_revision")}
           if config_snapshot is not None else {
               "config_snapshot_provider": get_config_snapshot, "config_allowlist": LIVE_CONFIG_ALLOWLIST,
           }),
        dispatch=True,
    )


def run_account_live_check_inline(
    *,
    account_id: int,
    email: str,
    trigger: str,
    force_refresh: bool = False,
    proxy: str | None = None,
    driver: str | None = None,
    operation_context=None,
    config_snapshot: dict | None = None,
    on_authenticated=None,
    result_writer=None,
    allow_missing_token: bool = False,
) -> dict:
    """Synchronously run the preflight inside its parent durable operation.

    The native path deliberately creates no child task and no local queue slot:
    the extract handler already owns the account lease and durable Run.
    """
    account_id = int(account_id)
    email = str(email or "").strip()
    if not email:
        return {"accepted": False, "busy": False, "error": "email 为空"}

    effective_live_check_driver = None
    effective_refresh_driver = None
    if not force_refresh:
        try:
            effective_live_check_driver = resolve_driver(
                driver or _snapshot_value(config_snapshot, "live_check_driver")
            )
        except LiveCheckDriverError as exc:
            return {"accepted": False, "busy": False, "error": str(exc)}
    else:
        effective_refresh_driver = _resolve_refresh_driver(driver, config_snapshot=config_snapshot)

    unavailable = deployment_unavailable(
        force_refresh=force_refresh, driver=effective_refresh_driver if force_refresh else effective_live_check_driver,
        config_snapshot=config_snapshot,
    )
    if unavailable:
        return unavailable

    account = db.get_account(account_id)
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    if db.account_is_deactivated(account):
        return {
            "accepted": False, "busy": False, "deactivated": True,
            "error": "账号已标记为封号，停止查活/刷新 AT",
        }
    if force_refresh and not allow_missing_token and not str(account.get("access_token") or "").strip():
        return {
            "accepted": False, "busy": False, "not_registered": True,
            "error": "账号没有现有 access_token，拒绝刷新 AT；请先完成账号注册或执行注册续跑",
        }

    if force_refresh and account.get("email_invalid") is True and effective_refresh_driver != "browser_roxy":
        effective_refresh_driver = "protocol_v2"

    native_inline = operation_context is not None
    if not native_inline and not _QUEUE_SLOTS.acquire(blocking=False):
        return {"accepted": False, "busy": False, "queue_full": True, "error": "查活队列已满，请稍后重试"}
    if not db.claim_account_live_check(acc_id=account_id, trigger=trigger):
        if not native_inline:
            _QUEUE_SLOTS.release()
        return {"accepted": False, "busy": True, "error": "该账号正在查活"}

    task_type = "token_refresh" if force_refresh else "live_check"
    task_id = int(operation_context.task_id) if native_inline else None
    try:
        if not native_inline:
            task_id = account_task_store.create_task(
                task_type=task_type,
                account_id=account_id,
                email=email,
                trigger=str(trigger or "manual"),
            )
        result = _run_live_check(
            account_id=account_id,
            email=email,
            proxy=proxy,
            trigger=str(trigger or "manual"),
            task_id=task_id,
            force_refresh=bool(force_refresh),
            driver=effective_live_check_driver,
            refresh_driver=_refresh_driver_request(effective_refresh_driver),
            release_queue_slot=False,
            operation_context=operation_context,
            finish_operation=not native_inline,
            config_snapshot=config_snapshot,
            **({"on_authenticated": on_authenticated} if callable(on_authenticated) else {}),
            **({"result_writer": result_writer} if callable(result_writer) else {}),
        )
    except account_task_store.OperationLeaseLost:
        # An extract parent must let the gateway fence the whole operation;
        # converting a lost child heartbeat into a normal inline failure could
        # incorrectly report a remote auth attempt as safely failed.
        raise
    except Exception as exc:
        result = {
            "ok": False, "status": "failed",
            "error": f"查活内联执行异常: {type(exc).__name__}: {str(exc)[:300]}",
        }
        try:
            result_writer(result) if callable(result_writer) else db.update_account_liveness(account_id, result)
        except Exception:
            logger.exception("[查活] 内联异常状态写回失败: account_id=%s", account_id)
        if not native_inline and task_id:
            account_task_store.finish_task(
                task_id, status="failed", message="查活内联执行异常", error=result["error"],
            )
    finally:
        if not native_inline:
            _QUEUE_SLOTS.release()
    return {
        "accepted": True,
        "busy": False,
        "account_id": account_id,
        "task_id": task_id,
        "task_type": task_type,
        "result": result,
    }


def enqueue_account_live_check(
    *,
    account_id: int,
    email: str,
    trigger: str = "manual",
    proxy: str | None = None,
    batch_id: str | None = None,
    force_refresh: bool = False,
    driver: str | None = None,
    idempotency_key: str | None = None,
    resource_family: str = "openai_interactive",
    allow_missing_token: bool = False,
) -> dict:
    account_id = int(account_id)
    email = str(email or "").strip()
    trigger = str(trigger or "manual")
    if not email:
        return {"accepted": False, "busy": False, "error": "email 为空"}
    snapshot = account_task_store.normalize_config_snapshot(get_config_snapshot(), allowlist=LIVE_CONFIG_ALLOWLIST)
    effective_live_check_driver = None
    effective_refresh_driver = None
    if not force_refresh:
        try:
            effective_live_check_driver = resolve_driver(driver)
        except LiveCheckDriverError as exc:
            return {"accepted": False, "busy": False, "error": str(exc)}
    else:
        effective_refresh_driver = _resolve_refresh_driver(driver)
    unavailable = deployment_unavailable(
        force_refresh=force_refresh, driver=effective_refresh_driver if force_refresh else effective_live_check_driver,
        config_snapshot=snapshot,
    )
    if unavailable:
        return unavailable
    account = db.get_account(account_id)
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    if db.account_is_deactivated(account):
        return {
            "accepted": False, "busy": False, "deactivated": True,
            "error": "账号已标记为封号，停止查活/刷新 AT",
        }
    if force_refresh and allow_missing_token:
        from core.accounts.completion import active_registration_job

        if active_registration_job(account_id, email):
            return {
                "accepted": False, "busy": True, "error_code": "registration_in_progress",
                "error": "该账号仍有注册任务正在执行，请等待结束后补全账号",
            }
    if force_refresh and not allow_missing_token and not str(account.get("access_token") or "").strip():
        return {
            "accepted": False, "busy": False, "not_registered": True,
            "error": "账号没有现有 access_token，拒绝刷新 AT；请先完成账号注册或执行注册续跑",
        }

    if force_refresh and account.get("email_invalid") is True and effective_refresh_driver != "browser_roxy":
        effective_refresh_driver = "protocol_v2"

    task_type = "token_refresh" if force_refresh else "live_check"
    claimed = False
    key = str(idempotency_key or "").strip() or None
    if not key:
        if not db.claim_account_live_check(acc_id=account_id, trigger=trigger):
            return {"accepted": False, "busy": True, "error": "该账号正在查活"}
        claimed = True
    try:
        submitted = _submit_native_live(
            account_id=account_id, email=email, trigger=trigger, task_type=task_type,
            force_refresh=force_refresh, driver=effective_live_check_driver,
            refresh_driver=_refresh_driver_request(effective_refresh_driver),
            explicit_proxy_requested=proxy is not None,
            batch_id=batch_id, idempotency_key=key,
            resource_family=resource_family,
            config_snapshot=snapshot,
            **({"allow_missing_token": True} if force_refresh and allow_missing_token else {}),
        )
    except Exception as exc:
        error = f"查活任务持久化失败: {type(exc).__name__}: {str(exc)[:300]}"
        if claimed:
            db.update_account_liveness(account_id, {"ok": False, "status": "failed", "error": error})
        return {"accepted": False, "busy": False, "error": error}
    if not submitted.get("accepted"):
        if claimed and not submitted.get("busy"):
            db.update_account_liveness(account_id, {"ok": False, "status": "failed", "error": submitted.get("error")})
        return _native_response(submitted, task_type=task_type, account_id=account_id, email=email, trigger=trigger)
    if key and not submitted.get("reused"):
        if not db.claim_account_live_check(acc_id=account_id, trigger=trigger):
            _cancel_unclaimed_native_run(submitted.get("run_id"), "账号查活业务状态已被其他请求占用")
            return {
                "accepted": False, "busy": True, "account_id": account_id,
                "email": email, "task_id": submitted.get("task_id"),
                "run_id": submitted.get("run_id"), "error": "该账号正在查活",
            }
    _append_log(
        email,
        f"[{'刷新AT' if force_refresh else '查活'}] 已持久化 account_id={account_id} trigger={trigger}",
        clear=True,
    )
    response = _native_response(
        submitted, task_type=task_type, account_id=account_id, email=email, trigger=trigger,
    )
    if effective_live_check_driver:
        response["live_check_driver"] = effective_live_check_driver
    if force_refresh:
        response["token_refresh_driver"] = effective_refresh_driver
        response["protocol_version"] = _refresh_protocol_version(effective_refresh_driver)
    return response


def queue_settings() -> dict:
    return {"workers": configured_workers(), "queue_limit": _QUEUE_LIMIT}


# Registration is side-effect free when the shared helper is not installed yet;
# once installed it makes restart recovery visible to the existing runtime
# dispatcher without creating a service-owned consumer thread.
register_operation_handlers()
