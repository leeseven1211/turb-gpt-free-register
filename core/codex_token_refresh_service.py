# -*- coding: utf-8 -*-
"""Codex OAuth access token 状态、refresh grant 与后台巡检。"""
from __future__ import annotations

import base64
import json
import logging
import re
import threading
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from config import codex as _cfg
from core import scheduler_state
from core.operations import task_gateway
from core.storage import codex as db
from core.storage import operation_runtime_store

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_SCHEDULER_STARTED = False
_HANDLER_REGISTERED = False
_HANDLER_LOCK = threading.RLock()
TASK_TYPE = "codex_token_refresh"
RESOURCE_FAMILY = "openai_interactive"
REQUEST_UNKNOWN = "request_unknown"
NEEDS_RECONCILIATION = "needs_reconciliation"
REQUEST_PENDING = "request_pending"
REAUTH_REQUIRED = "reauth_required"
_PENDING_MARKER = REQUEST_PENDING
_UNKNOWN_MARKER = f"{REQUEST_UNKNOWN}: {NEEDS_RECONCILIATION}"
_RECONCILIATION_MARKERS = (REQUEST_UNKNOWN, NEEDS_RECONCILIATION, REQUEST_PENDING)
# Only values that are safe and meaningful to capture in a durable task belong
# here.  The gateway rejects allowlist names containing secret-like words;
# the endpoint/client identity remain deployment configuration and are never
# copied into the task payload.  ``request_timeout`` is the stable public
# alias used by the preferred gateway contract.
_CONFIG_ALLOWLIST = {"request_timeout": "CODEX_REQUEST_TIMEOUT"}
_RECONCILIATION_QUERY_BATCH_SIZE = 500
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\b")
_CREDENTIAL_URL_RE = re.compile(r"(?i)(https?://)[^/@\s]+@")
_LONG_OPAQUE_RE = re.compile(r"\b[A-Za-z0-9_\-.]{48,}\b")
_REAUTH_ERROR_MARKERS = (
    "invalid_grant",
    "invalid refresh token",
    "refresh_token_invalidated",
    "refresh token invalidated",
    "refresh token expired",
    "refresh token revoked",
    "token has been revoked",
    "your session has ended",
    "session has ended",
)


class TokenRefreshError(RuntimeError):
    """刷新流程的安全、可持久化错误基类。"""

    code = "token_refresh_failed"
    action_dispatched = False
    remote_response_received = False
    needs_reconciliation = False
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        action_dispatched: bool = False,
        remote_response_received: bool = False,
        needs_reconciliation: bool = False,
        credential_persisted: bool = False,
        remote_request_id: str | None = None,
    ) -> None:
        super().__init__(str(message))
        self.action_dispatched = bool(action_dispatched)
        self.remote_response_received = bool(remote_response_received)
        self.needs_reconciliation = bool(needs_reconciliation)
        self.credential_persisted = bool(credential_persisted)
        self.remote_request_id = str(remote_request_id or "") or None


class TokenRefreshRequestUnknownError(TokenRefreshError):
    """远端可能已处理请求，但本地无法证明 refresh grant 结果。"""

    code = REQUEST_UNKNOWN
    needs_reconciliation = True

    def __init__(
        self,
        message: str,
        *,
        remote_response_received: bool = False,
        credential_persisted: bool = False,
        remote_request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            action_dispatched=True,
            remote_response_received=remote_response_received,
            needs_reconciliation=True,
            credential_persisted=credential_persisted,
            remote_request_id=remote_request_id,
        )


class TokenRefreshReauthRequiredError(TokenRefreshError):
    """远端明确拒绝旧 refresh token，需要重新 OAuth。"""

    code = REAUTH_REQUIRED

    def __init__(
        self,
        message: str,
        *,
        action_dispatched: bool = True,
        remote_response_received: bool = True,
    ) -> None:
        super().__init__(
            message,
            action_dispatched=action_dispatched,
            remote_response_received=remote_response_received,
        )


class TokenRefreshRejectedError(TokenRefreshError):
    """远端返回明确拒绝，但不是可安全自动重发的结果。"""

    code = "refresh_rejected"

    def __init__(self, message: str) -> None:
        super().__init__(message, action_dispatched=True, remote_response_received=True)


class TokenRefreshCancelledError(TokenRefreshError):
    """远端请求尚未发出前收到持久取消请求。"""

    code = "cancelled"


RefreshRequestUnknown = TokenRefreshRequestUnknownError
RefreshReauthRequired = TokenRefreshReauthRequiredError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_text(value: object, limit: int = 500) -> str:
    """保留错误码/类型，移除凭证、代理凭据和可能的长 opaque 值。"""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = _CREDENTIAL_URL_RE.sub(r"\1<redacted>@", text)
    text = _JWT_RE.sub("<redacted-jwt>", text)
    text = _LONG_OPAQUE_RE.sub("<redacted>", text)
    return text[:limit]


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _jwt_exp(access_token: str) -> datetime | None:
    try:
        parts = str(access_token or "").split(".")
        if len(parts) < 2:
            return None
        raw = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return None
        return datetime.fromtimestamp(float(exp), tz=timezone.utc)
    except Exception:
        return None


def oauth_metadata(content: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """计算可直接给 WebUI 使用的 OAuth 生命周期状态，不返回任何 token。"""
    current = now or _utc_now()
    expires_at = _parse_datetime(content.get("expired")) or _jwt_exp(
        str(content.get("access_token") or "")
    )
    has_access_token = bool(str(content.get("access_token") or "").strip())
    refreshable = bool(str(content.get("refresh_token") or "").strip())
    seconds_left = int((expires_at - current).total_seconds()) if expires_at else None
    threshold = max(1, int(getattr(_cfg, "CODEX_TOKEN_REFRESH_BEFORE_HOURS", 24) or 24)) * 3600

    if not has_access_token:
        status = "missing"
    elif expires_at is None:
        status = "unknown"
    elif seconds_left <= 0:
        status = "expired"
    elif seconds_left <= threshold:
        status = "expiring"
    else:
        status = "valid"

    return {
        "oauth_status": status,
        "oauth_expires_at": _iso_utc(expires_at) if expires_at else "",
        "oauth_seconds_left": seconds_left,
        "oauth_refreshable": refreshable,
        "oauth_auto_refresh": bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)),
    }


def refresh_error_requires_reauth(error: object) -> bool:
    lowered = str(error or "").strip().lower()
    return bool(lowered and any(marker in lowered for marker in _REAUTH_ERROR_MARKERS))


def sub2api_status_requires_reauth(http_status: object) -> bool:
    """Sub2API 401 表示远端已撤销 OAuth Token，需要重新授权。"""
    try:
        return int(http_status or 0) == 401
    except (TypeError, ValueError):
        return False


def _apply_account_status_override(item: dict[str, Any]) -> dict[str, Any]:
    """Make a confirmed account deactivation override local token expiry."""
    if str(item.get("oauth_account_status") or "").strip().lower() == "deactivated":
        item["oauth_status"] = "deactivated"
        item["oauth_reauth_required"] = True
    return item


def decorate_row(row: dict[str, Any]) -> dict[str, Any]:
    """读取凭证内容后为列表行补齐 OAuth 状态；失败时保持列表可用。"""
    item = dict(row)
    if item.get("oauth_status"):
        item["oauth_reauth_required"] = (
            refresh_error_requires_reauth(item.get("oauth_refresh_error"))
            or sub2api_status_requires_reauth(item.get("sub2api_http_status"))
        )
        return _apply_account_status_override(item)
    try:
        text, _ = db.read_codex_credential(str(item.get("filename") or ""))
        content = json.loads(text)
        if not isinstance(content, dict):
            raise ValueError("凭证不是 JSON 对象")
        item.update(oauth_metadata(content))
        item["oauth_reauth_required"] = (
            refresh_error_requires_reauth(item.get("oauth_refresh_error"))
            or sub2api_status_requires_reauth(item.get("sub2api_http_status"))
        )
    except Exception:
        item.update({
            "oauth_status": "unknown",
            "oauth_expires_at": str(item.get("expired") or ""),
            "oauth_seconds_left": None,
            "oauth_refreshable": False,
            "oauth_auto_refresh": bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)),
            "oauth_reauth_required": (
                refresh_error_requires_reauth(item.get("oauth_refresh_error"))
                or sub2api_status_requires_reauth(item.get("sub2api_http_status"))
            ),
        })
    return _apply_account_status_override(item)


def _refresh_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        raw_error = payload.get("error")
        nested_error = raw_error if isinstance(raw_error, dict) else {}
        code = str(
            nested_error.get("code")
            or payload.get("code")
            or (raw_error if isinstance(raw_error, str) else "")
        ).strip()
        description = str(
            nested_error.get("message")
            or payload.get("error_description")
            or payload.get("message")
            or ""
        ).strip()
        detail = ": ".join(part for part in (code, description) if part)
        if detail:
            return _safe_text(detail)
    return f"HTTP {int(getattr(response, 'status_code', 0) or 0)}"


def _request_refresh(refresh_token: str, *, config_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """只发送一次 refresh grant；网络不确定时绝不在本层自动重发。"""
    config_snapshot = config_snapshot or {}
    data = {
        "grant_type": "refresh_token",
        "client_id": str(config_snapshot.get("CODEX_CLIENT_ID") or getattr(_cfg, "CODEX_CLIENT_ID", "") or ""),
        "refresh_token": refresh_token,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "turb-gpt-free-register/codex-token-refresh",
    }
    timeout = _request_timeout(config_snapshot)
    try:
        response = requests.post(
            str(config_snapshot.get("CODEX_TOKEN_URL") or getattr(_cfg, "CODEX_TOKEN_URL", "") or ""),
            headers=headers,
            data=data,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise TokenRefreshRequestUnknownError(
            f"{REQUEST_UNKNOWN}: token endpoint {type(exc).__name__}",
            remote_response_received=False,
        ) from exc

    if response.status_code == 200:
        try:
            payload = response.json()
        except Exception as exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: token endpoint returned invalid JSON",
                remote_response_received=True,
            ) from exc
        if not isinstance(payload, dict) or not str(payload.get("access_token") or "").strip():
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: token endpoint response lacks access_token",
                remote_response_received=True,
            )
        return payload

    error = _refresh_error(response)
    if refresh_error_requires_reauth(error) or response.status_code in {400, 401}:
        raise TokenRefreshReauthRequiredError(f"{REAUTH_REQUIRED}: {_safe_text(error)}")
    # A 408/429/5xx response is not proof that the remote side did not rotate
    # the credential. It is terminal-for-now, not an auto-retry.
    if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
        raise TokenRefreshRequestUnknownError(
            f"{REQUEST_UNKNOWN}: token endpoint HTTP {response.status_code}",
            remote_response_received=True,
        )
    raise TokenRefreshRejectedError(
        f"refresh token rejected: HTTP {response.status_code}: {_safe_text(error)}",
    )


def _config_value(snapshot: Mapping[str, Any] | None, *keys: str, default: Any = None) -> Any:
    values = snapshot if isinstance(snapshot, Mapping) else {}
    for key in keys:
        if key in values:
            return values[key]
    return default


def _load_credential(filename: str) -> tuple[dict[str, Any], str, str]:
    text, actual_filename = db.read_codex_credential(filename)
    content = json.loads(text)
    if not isinstance(content, dict):
        raise RuntimeError("Codex 凭证不是 JSON 对象")
    old_refresh_token = str(content.get("refresh_token") or "").strip()
    if not old_refresh_token:
        raise TokenRefreshReauthRequiredError(
            f"{REAUTH_REQUIRED}: 凭证缺少 refresh_token，只能重新执行 OAuth 授权",
            action_dispatched=False,
            remote_response_received=False,
        )
    return content, actual_filename, old_refresh_token


def _build_updated_credential(
    content: Mapping[str, Any],
    token_response: Mapping[str, Any],
    *,
    refreshed_at: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    """Apply one token response without exposing the credential in summaries."""
    access_token = str(token_response.get("access_token") or "").strip()
    if not access_token:
        raise TokenRefreshRequestUnknownError(
            f"{REQUEST_UNKNOWN}: token endpoint response lacks access_token",
            remote_response_received=True,
        )
    updated = dict(content)
    updated["access_token"] = access_token
    returned_refresh_token = str(token_response.get("refresh_token") or "").strip()
    rotated = bool(returned_refresh_token)
    # OAuth providers are allowed to omit refresh_token when it does not
    # rotate. Retaining the old value is safe; treating omission as failure
    # would discard the only durable credential that can refresh again.
    if rotated:
        updated["refresh_token"] = returned_refresh_token
    refreshed_at = refreshed_at or _utc_now()
    updated["last_refresh"] = _iso_utc(refreshed_at)
    expires_in = token_response.get("expires_in")
    try:
        expires_at = refreshed_at + timedelta(seconds=max(1, int(expires_in)))
    except (TypeError, ValueError):
        expires_at = _jwt_exp(access_token)
    updated["expired"] = _iso_utc(expires_at) if expires_at is not None else ""
    if token_response.get("id_token"):
        updated["id_token"] = str(token_response.get("id_token") or "")
    return updated, rotated


def _safe_error(exc: BaseException) -> str:
    return _safe_text(f"{type(exc).__name__}: {exc}")


def _attach_remote_request_id(exc: BaseException, request_id: str) -> BaseException:
    try:
        setattr(exc, "remote_request_id", request_id)
    except Exception:
        pass
    return exc


def _report(report: Callable[..., Any] | None, **event: Any) -> None:
    """Best-effort event reporting; a telemetry failure cannot resend OAuth."""
    if report is None:
        return
    try:
        report(**event)
    except Exception:
        logger.exception("Codex token refresh progress writeback failed")


def _checkpoint(checkpoint: Callable[..., Any] | None) -> None:
    if checkpoint is not None:
        checkpoint()


def _unknown_summary(
    filename: str,
    *,
    reason: str,
    action_dispatched: bool,
    remote_response_received: bool,
    credential_persisted: bool = False,
    remote_request_id: str | None = None,
) -> dict[str, Any]:
    summary = {
        "ok": False,
        "status": REQUEST_UNKNOWN,
        "error_code": REQUEST_UNKNOWN,
        "outcome": REQUEST_UNKNOWN,
        "reconcile_required": True,
        "needs_reconciliation": True,
        "next_action": "manual_reconcile",
        "retryable": False,
        "action_dispatched": bool(action_dispatched),
        "remote_response_received": bool(remote_response_received),
        "credential_persisted": bool(credential_persisted),
        "checkpoint": "refresh_request_dispatched" if action_dispatched else "preflight",
        "filename": filename,
        "error": _safe_text(reason),
    }
    if remote_request_id:
        summary["remote_request_id"] = _safe_text(remote_request_id, 80)
    return summary


def _mark_unknown(filename: str, reason: str) -> None:
    marker = _safe_text(f"{_UNKNOWN_MARKER}: {_safe_error(RuntimeError(reason))}", 500)
    try:
        db.mark_codex_oauth_refresh(filename, error=marker)
    except Exception:
        logger.exception("记录 Codex token refresh request_unknown 失败：filename=%s", filename)


def _clear_refresh_marker_after_terminal(filename: str) -> bool:
    """Clear the producer fence only after the durable Run is terminal."""
    if not filename:
        return False
    try:
        db.mark_codex_oauth_refresh(filename, error=None)
    except Exception as exc:
        # The operation is already terminal. Leaving a pending/unknown marker
        # is safer than allowing a scheduler to infer that a refresh is safe.
        _mark_unknown(filename, f"terminal refresh metadata writeback failed: {_safe_error(exc)}")
        logger.exception("清除 Codex token refresh terminal marker 失败：filename=%s", filename)
        return False
    return True


def _persist_refreshed_credential(
    actual_filename: str,
    updated: Mapping[str, Any],
    *,
    remote_response_received: bool = True,
    clear_refresh_marker: bool = True,
) -> None:
    """Persist credentials and metadata exactly once after a remote grant."""
    try:
        db.write_codex_credential(actual_filename, dict(updated))
    except Exception as exc:
        raise TokenRefreshRequestUnknownError(
            f"{REQUEST_UNKNOWN}: credential writeback failed: {_safe_error(exc)}",
            remote_response_received=remote_response_received,
            credential_persisted=False,
        ) from exc
    try:
        persisted_text, _ = db.read_codex_credential(actual_filename)
        persisted = json.loads(persisted_text)
        if not isinstance(persisted, Mapping):
            raise ValueError("credential readback is not an object")
        if (
            str(persisted.get("access_token") or "")
            != str(updated.get("access_token") or "")
            or str(persisted.get("refresh_token") or "")
            != str(updated.get("refresh_token") or "")
        ):
            raise ValueError("credential readback does not match the refreshed pair")
    except Exception as exc:
        # A successful SQL/file write without a verified readback is not a
        # proof that this worker owns the current credential.  Keep the
        # remote intent unresolved so restart recovery cannot send the old
        # refresh token a second time.
        _mark_unknown(actual_filename, f"credential readback failed: {_safe_error(exc)}")
        raise TokenRefreshRequestUnknownError(
            f"{REQUEST_UNKNOWN}: credential readback failed: {_safe_error(exc)}",
            remote_response_received=remote_response_received,
            credential_persisted=False,
        ) from exc
    if clear_refresh_marker:
        try:
            db.mark_codex_oauth_refresh(actual_filename, error=None)
        except Exception as exc:
            # The access/refresh pair may already be durable. Keep the row fenced
            # from the scheduler so a metadata failure can never trigger another
            # refresh grant.
            _mark_unknown(actual_filename, f"refresh metadata writeback failed: {_safe_error(exc)}")
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: refresh metadata writeback failed: {_safe_error(exc)}",
                remote_response_received=remote_response_received,
                credential_persisted=True,
            ) from exc
    else:
        try:
            # The credential repository intentionally rebuilds its projection
            # on every write and therefore clears oauth_refresh_error. Keep a
            # producer fence in place until the gateway has durably finished
            # this Run; otherwise a crash in the tiny post-write window could
            # make the periodic producer submit a second refresh.
            db.mark_codex_oauth_refresh(actual_filename, error=_PENDING_MARKER)
        except Exception as exc:
            _mark_unknown(actual_filename, f"refresh pending marker restore failed: {_safe_error(exc)}")
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: refresh pending marker restore failed: {_safe_error(exc)}",
                remote_response_received=remote_response_received,
                credential_persisted=True,
            ) from exc


def _perform_refresh(
    filename: str,
    *,
    config_snapshot: Mapping[str, Any] | None = None,
    report: Callable[..., Any] | None = None,
    checkpoint: Callable[..., Any] | None = None,
    post_response_fence: Callable[[], Any] | None = None,
    is_cancel_requested: Callable[[], bool] | None = None,
    mark_settling: Callable[[], Any] | None = None,
    on_remote_dispatch: Callable[[str], Any] | None = None,
    on_remote_response: Callable[..., Any] | None = None,
    on_remote_receipt: Callable[..., Any] | None = None,
    defer_refresh_marker_clear: bool = False,
    persist_pending: bool = True,
) -> dict[str, Any]:
    """Run the single refresh attempt shared by native and compatibility handlers."""
    content, actual_filename, old_refresh_token = _load_credential(filename)
    cancel = is_cancel_requested or (lambda: False)
    _report(report, stage="preflight", state="running", message="开始刷新 Codex OAuth Token")
    _checkpoint(checkpoint)
    if cancel():
        raise TokenRefreshCancelledError("刷新请求发出前收到取消请求")

    if persist_pending:
        try:
            db.mark_codex_oauth_refresh(actual_filename, error=_PENDING_MARKER)
        except Exception as exc:
            raise TokenRefreshError(
                f"刷新请求意图写入失败: {_safe_error(exc)}",
            ) from exc
    _report(
        report,
        stage="refresh_token",
        state="running",
        message="已持久化 refresh grant 意图，准备发送一次远端请求",
        detail={
            "checkpoint": "refresh_request_dispatched",
            "retry_policy": "none",
            "request_unknown_policy": "manual_reconcile",
        },
    )
    _checkpoint(checkpoint)
    if cancel():
        raise TokenRefreshCancelledError("刷新请求发出前收到取消请求")

    remote_request_id = uuid.uuid4().hex

    def record_unknown_receipt(*, credential_persisted: bool = False) -> None:
        """Best-effort fence for post-dispatch failures; never confirm a write."""
        if on_remote_receipt is None:
            return
        try:
            on_remote_receipt(
                request_id=remote_request_id,
                outcome="unknown",
                detail={
                    "remote_response_received": True,
                    "receipt_state": "unknown",
                    "credential_persisted": bool(credential_persisted),
                    "readback_confirmed": False,
                    "terminal": False,
                },
            )
        except Exception:
            # The credential row and the remote intent marker are already
            # fenced. Recovery must treat the remaining response/intent as
            # unknown even if this secondary diagnostic write fails.
            logger.exception("记录 Codex token refresh unknown receipt 失败")

    if on_remote_dispatch is not None:
        try:
            on_remote_dispatch(remote_request_id)
        except Exception as exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: remote intent writeback failed: {_safe_error(exc)}",
                remote_response_received=False,
                remote_request_id=remote_request_id,
            ) from exc
    try:
        token_response = _request_refresh(
            old_refresh_token,
            config_snapshot=dict(config_snapshot or {}),
        )
    except TokenRefreshRequestUnknownError as exc:
        _attach_remote_request_id(exc, remote_request_id)
        try:
            if on_remote_response is not None:
                on_remote_response(
                    request_id=remote_request_id,
                    outcome="unknown",
                    detail={
                        "remote_response_received": bool(exc.remote_response_received),
                        "receipt_state": "unknown",
                        "terminal": False,
                    },
                )
            if on_remote_receipt is not None:
                on_remote_receipt(
                    request_id=remote_request_id,
                    outcome="unknown",
                    detail={
                        "remote_response_received": bool(exc.remote_response_received),
                        "receipt_state": "unknown",
                        "credential_persisted": bool(getattr(exc, "credential_persisted", False)),
                        "readback_confirmed": False,
                        "terminal": False,
                    },
                )
        except Exception as receipt_exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: remote receipt writeback failed: {_safe_error(receipt_exc)}",
                remote_response_received=bool(exc.remote_response_received),
                remote_request_id=remote_request_id,
            ) from receipt_exc
        raise
    except TokenRefreshReauthRequiredError as exc:
        _attach_remote_request_id(exc, remote_request_id)
        try:
            if on_remote_response is not None:
                on_remote_response(
                    request_id=remote_request_id,
                    outcome="rejected",
                    detail={
                        "remote_response_received": True,
                        "receipt_state": "response_received",
                        "terminal": False,
                    },
                )
            if on_remote_receipt is not None:
                on_remote_receipt(
                    request_id=remote_request_id,
                    outcome="rejected",
                    detail={
                        "remote_response_received": True,
                        "receipt_state": "rejected",
                        "terminal": True,
                    },
                )
        except Exception as receipt_exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: remote receipt writeback failed: {_safe_error(receipt_exc)}",
                remote_response_received=True,
                remote_request_id=remote_request_id,
            ) from receipt_exc
        raise
    except TokenRefreshRejectedError as exc:
        _attach_remote_request_id(exc, remote_request_id)
        try:
            if on_remote_response is not None:
                on_remote_response(
                    request_id=remote_request_id,
                    outcome="rejected",
                    detail={
                        "remote_response_received": True,
                        "receipt_state": "response_received",
                        "terminal": False,
                    },
                )
            if on_remote_receipt is not None:
                on_remote_receipt(
                    request_id=remote_request_id,
                    outcome="rejected",
                    detail={
                        "remote_response_received": True,
                        "receipt_state": "rejected",
                        "terminal": True,
                    },
                )
        except Exception as receipt_exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: remote receipt writeback failed: {_safe_error(receipt_exc)}",
                remote_response_received=True,
                remote_request_id=remote_request_id,
            ) from receipt_exc
        raise
    except TokenRefreshError:
        raise
    except Exception as exc:
        # This boundary is deliberately catch-all: a custom transport may
        # throw a non-requests timeout after bytes were sent. It is unknown,
        # never an ordinary failed/retryable result.
        unknown = TokenRefreshRequestUnknownError(
            f"{REQUEST_UNKNOWN}: refresh transport {_safe_error(exc)}",
            remote_response_received=False,
            remote_request_id=remote_request_id,
        )
        try:
            if on_remote_response is not None:
                on_remote_response(
                    request_id=remote_request_id,
                    outcome="unknown",
                    detail={
                        "remote_response_received": False,
                        "receipt_state": "unknown",
                        "terminal": False,
                    },
                )
            if on_remote_receipt is not None:
                on_remote_receipt(
                    request_id=remote_request_id,
                    outcome="unknown",
                    detail={
                        "remote_response_received": False,
                        "receipt_state": "unknown",
                        "credential_persisted": False,
                        "readback_confirmed": False,
                        "terminal": False,
                    },
                )
        except Exception as receipt_exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: remote receipt writeback failed: {_safe_error(receipt_exc)}",
                remote_response_received=False,
                remote_request_id=remote_request_id,
            ) from receipt_exc
        raise unknown from exc

    # An HTTP response is only an observation. It does not prove that this
    # process persisted the replacement credential, so this callback must
    # never use the terminal ``confirmed`` outcome.
    if on_remote_response is not None:
        try:
            on_remote_response(
                request_id=remote_request_id,
                outcome="received",
                detail={
                    "remote_response_received": True,
                    "receipt_state": "response_received",
                    "terminal": False,
                },
            )
        except Exception as response_exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: remote response event writeback failed: {_safe_error(response_exc)}",
                remote_response_received=True,
                remote_request_id=remote_request_id,
            ) from response_exc
    # The HTTP response may already contain a rotated refresh token. From
    # this boundary onward, cancellation is deliberately not a checkpoint:
    # it must not interrupt the write/readback/confirmed/finish settlement.
    # The durable handler supplies a lease-only fence callback so a genuinely
    # lost lease still prevents an unauthorized local write and preserves the
    # response as request_unknown for reconciliation.
    if post_response_fence is not None:
        post_response_fence()
    _report(
        report,
        stage="refresh_token",
        state="running",
        message="远端已返回 refresh grant 结果，正在确认本地凭证",
        detail={"checkpoint": "remote_response_received", "remote_response_received": True},
    )
    if mark_settling is not None:
        try:
            mark_settling()
        except Exception:
            # The remote response already exists. Continue once with local
            # persistence; the caller will fence the run if terminal storage
            # later fails.
            logger.exception("标记 Codex token refresh settling 失败")
    try:
        updated, rotated = _build_updated_credential(content, token_response)
        _persist_refreshed_credential(
            actual_filename,
            updated,
            clear_refresh_marker=not defer_refresh_marker_clear,
        )
    except TokenRefreshRequestUnknownError as exc:
        _attach_remote_request_id(exc, remote_request_id)
        record_unknown_receipt(
            credential_persisted=bool(getattr(exc, "credential_persisted", False)),
        )
        raise
    except Exception as exc:
        _attach_remote_request_id(exc, remote_request_id)
        record_unknown_receipt()
        raise

    # ``confirmed`` is deliberately after write + readback. A process crash
    # between the HTTP response and this point leaves the durable intent in
    # response_received/unknown, which recovery must fence instead of retrying.
    if on_remote_receipt is not None:
        try:
            on_remote_receipt(
                request_id=remote_request_id,
                outcome="confirmed",
                detail={
                    "remote_response_received": True,
                    "receipt_state": "confirmed",
                    "credential_persisted": True,
                    "readback_confirmed": True,
                    "terminal": True,
                },
            )
        except Exception as exc:
            raise TokenRefreshRequestUnknownError(
                f"{REQUEST_UNKNOWN}: confirmed receipt writeback failed: {_safe_error(exc)}",
                remote_response_received=True,
                credential_persisted=True,
                remote_request_id=remote_request_id,
            ) from exc
    metadata = oauth_metadata(updated)
    try:
        sync_result = _sync_sub2_if_needed(actual_filename)
    except Exception as exc:
        sync_result = {"status": "failed", "error": _safe_error(exc)}
    summary = {
        "ok": True,
        "status": "success",
        "filename": actual_filename,
        "email": str(updated.get("email") or ""),
        "expired": str(updated.get("expired") or ""),
        "credential_persisted": True,
        # ``operation._scrub`` intentionally removes keys containing "token"
        # from durable summaries. Keep this proof under a neutral metadata
        # name; the credential itself is never included in the summary.
        "credential_rotated": rotated,
        "checkpoint": "credential_persisted",
        "remote_request_id": remote_request_id,
        "remote_response_received": True,
        "action_dispatched": True,
        "retryable": False,
        "sub2_sync": sync_result.get("status"),
        **metadata,
    }
    if sync_result.get("status") == "failed":
        summary["sub2_sync_error"] = _safe_text(sync_result.get("error"))
    _report(
        report,
        stage="refresh_token",
        state="success",
        message="Codex OAuth Token 刷新成功",
        detail={
            "checkpoint": "credential_persisted",
            "credential_persisted": True,
            "credential_rotated": rotated,
            "sub2_sync": sync_result.get("status"),
        },
    )
    return summary


def refresh_credential(
    filename: str,
    *,
    config_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """兼容同步调用；durable worker 使用带 fencing 的内部编排。"""
    return _perform_refresh(
        filename,
        config_snapshot=config_snapshot,
        persist_pending=False,
    )


def _sync_sub2_if_needed(filename: str) -> dict[str, Any]:
    rows = db.list_codex_accounts(archived="all")
    row = next((item for item in rows if item.get("filename") == filename), {})
    if not bool(getattr(_cfg, "CODEX_TOKEN_AUTO_SYNC_SUB2API", True)):
        return {"status": "disabled"}
    if int(row.get("sub2_uploaded_count") or 0) <= 0:
        return {"status": "not_previously_uploaded"}

    from core.sub2api_client import upload_configured_codex_oauth_credential

    text, _ = db.read_codex_credential(filename)
    try:
        result = upload_configured_codex_oauth_credential(json.loads(text))
    except Exception as exc:
        error = _safe_error(exc)
        db.mark_codex_sub2_sync_error(filename, error)
        return {"status": "failed", "error": error}
    db.mark_codex_sub2_uploaded(filename)
    return {"status": "success", "updated": result.get("updated")}


def _run_data(run: Mapping[str, Any]) -> dict[str, Any]:
    raw = run.get("data")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _run_filename(run: Mapping[str, Any]) -> str:
    data = _run_data(run)
    return str(data.get("credential_filename") or data.get("filename") or "").strip()


def _update_account_state(
    email: str,
    *,
    credential_state: str | None = None,
    execution_status: str | None = None,
    last_run_status: str | None = None,
    error: str | None = None,
    active_run_id: int | None = None,
) -> None:
    if not email:
        return
    try:
        db.update_account_codex_operation_state(
            email,
            credential_state=credential_state,
            execution_status=execution_status,
            last_run_status=last_run_status,
            error=error,
            active_run_id=active_run_id,
        )
    except Exception:
        logger.exception("Codex token refresh account projection writeback failed: email=%s", email)


def _failed_summary(
    filename: str,
    exc: BaseException,
    *,
    action_dispatched: bool,
    remote_response_received: bool,
    remote_request_id: str | None = None,
) -> dict[str, Any]:
    code = str(getattr(exc, "code", "token_refresh_failed") or "token_refresh_failed")
    next_action = "reauthorize" if code == REAUTH_REQUIRED else "manual_retry"
    summary = {
        "ok": False,
        "status": "failed",
        "error_code": code,
        "filename": filename,
        "error": _safe_error(exc),
        "next_action": next_action,
        "retryable": False,
        "action_dispatched": bool(action_dispatched),
        "remote_response_received": bool(remote_response_received),
        "checkpoint": "refresh_request_dispatched" if action_dispatched else "preflight",
    }
    if remote_request_id:
        summary["remote_request_id"] = _safe_text(remote_request_id, 80)
    return summary


def _cancelled_summary(filename: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "cancelled",
        "error_code": "cancelled",
        "filename": filename,
        "message": _safe_text(message),
        "next_action": "none",
        "retryable": False,
        "action_dispatched": False,
        "remote_response_received": False,
        "checkpoint": "preflight",
    }


def _execute_legacy_run(run_id: int) -> dict[str, Any]:
    """兼容旧测试/调用者，但把 claim、lease 和 finish 全交给 B gateway。"""
    _register_worker()
    execute = getattr(task_gateway, "_execute_operation_handler", None)
    if not callable(execute):
        raise RuntimeError("durable operation gateway 缺少共享 handler 执行入口")
    payload = dict(execute(TASK_TYPE, int(run_id)))
    summary = payload.get("result_summary")
    if isinstance(summary, Mapping):
        # Preserve the old synchronous return shape for callers while the
        # gateway remains the only owner of claim/lease/terminal persistence.
        result = dict(summary)
        result.setdefault("status", payload.get("status"))
        result.setdefault("run_id", payload.get("run_id", int(run_id)))
        return result
    return payload


def _mark_refresh_failure(filename: str, reason: str) -> None:
    if not filename:
        return
    try:
        db.mark_codex_oauth_refresh(filename, error=_safe_text(reason))
    except Exception:
        logger.exception("记录 Codex OAuth 刷新失败状态异常: filename=%s", filename)


def _gateway_supports_operation_context() -> bool:
    context_cls = getattr(task_gateway, "OperationHandlerContext", None)
    return all(
        callable(getattr(task_gateway, name, None))
        for name in ("register_operation_handler", "submit_durable_operation")
    ) and all(
        callable(getattr(context_cls, name, None))
        for name in ("remote_request_started", "remote_request_receipt")
    )


def _register_worker() -> bool:
    """Register the task type once; dispatch ownership stays in the gateway."""
    global _HANDLER_REGISTERED
    with _HANDLER_LOCK:
        if _HANDLER_REGISTERED:
            return False
        if not _gateway_supports_operation_context():
            raise RuntimeError("Codex token refresh 需要已部署的 durable operation handler gateway")
        task_gateway.register_operation_handler(
            TASK_TYPE,
            _handle_operation_context,
            source_systems=("native_operations",),
            config_allowlist=_CONFIG_ALLOWLIST,
        )
        _HANDLER_REGISTERED = True
    task_gateway.notify_dispatch()
    return True


def _b_operation_result(
    status: str,
    *,
    message: str,
    summary: Mapping[str, Any],
    error: str | None = None,
) -> Any:
    result_cls = getattr(task_gateway, "OperationResult", None)
    if result_cls is None:
        return {
            "status": status,
            "ok": status == "success",
            "message": _safe_text(message),
            "error": _safe_text(error) if error else None,
            "result_summary": dict(summary),
        }
    if status == REQUEST_UNKNOWN:
        return result_cls.request_unknown(_safe_text(message), dict(summary))
    if status == "success":
        return result_cls.success(dict(summary), message=_safe_text(message))
    if status == "cancelled":
        return result_cls.cancelled(_safe_text(message))
    return result_cls(
        status,
        dict(summary),
        _safe_text(message),
        _safe_text(error) if error else None,
    )


def _handle_operation_context(context: Any) -> Any:
    """Preferred B-gateway handler using its injected claim/lease context."""
    try:
        from core.operations.task_gateway import OperationLeaseUnavailable
    except ImportError:  # pragma: no cover - only for a partial rolling import
        OperationLeaseUnavailable = ()  # type: ignore[assignment]
    try:
        from core.operation_runtime import OperationCancelled
    except ImportError:  # pragma: no cover - project always provides it
        OperationCancelled = ()  # type: ignore[assignment]

    run = context.run if isinstance(context.run, Mapping) else {}
    filename = _run_filename(run)
    email = str(getattr(context, "email", "") or run.get("email_snapshot") or "").strip()
    run_id = int(getattr(context, "run_id", run.get("id") or 0) or 0)
    remote_dispatched = False
    remote_response_received = False

    def on_remote_dispatch(request_id: str) -> None:
        nonlocal remote_dispatched
        remote_dispatched = True
        context.remote_request_started(
            action=TASK_TYPE,
            intent_kind="remote_write",
            request_id=request_id,
            detail={"retry_policy": "none", "checkpoint": "refresh_request_dispatched"},
        )

    def on_remote_response(*, request_id: str, outcome: str, detail: Mapping[str, Any]) -> None:
        nonlocal remote_response_received
        remote_response_received = bool(detail.get("remote_response_received"))
        context.remote_request_receipt(
            outcome=outcome,
            action=TASK_TYPE,
            request_id=request_id,
            detail={
                "remote_response_received": remote_response_received,
                "receipt_state": "response_received" if remote_response_received else "unknown",
                "terminal": False,
            },
        )

    def on_remote_receipt(*, request_id: str, outcome: str, detail: Mapping[str, Any]) -> None:
        nonlocal remote_response_received
        remote_response_received = bool(detail.get("remote_response_received", remote_response_received))
        receipt_state = str(detail.get("receipt_state") or outcome or "unknown")
        context.remote_request_receipt(
            outcome=outcome,
            action=TASK_TYPE,
            request_id=request_id,
            detail={
                "remote_response_received": remote_response_received,
                "receipt_state": receipt_state,
                "credential_persisted": bool(detail.get("credential_persisted")),
                "readback_confirmed": bool(detail.get("readback_confirmed")),
                "remote_result_confirmed": receipt_state == "confirmed",
                "local_business_writeback_confirmed": receipt_state == "confirmed",
                "local_readback_confirmed": receipt_state == "confirmed"
                and bool(detail.get("readback_confirmed")),
                "terminal": bool(detail.get("terminal")),
            },
        )

    def report(**event: Any) -> Any:
        return context.report(**event)

    def checkpoint() -> None:
        context.checkpoint()

    try:
        if not filename:
            raise TokenRefreshError("durable refresh task 缺少 credential_filename")
        account_id = int(getattr(context, "account_id", 0) or 0)
        if not account_id:
            raise TokenRefreshError("durable refresh task 缺少 account_id")
        with context.lease(resource_family=RESOURCE_FAMILY, ttl_seconds=600) as lease:
            _update_account_state(email, execution_status="running", active_run_id=run_id)
            snapshot = getattr(context, "config_snapshot", {})
            snapshot = snapshot if isinstance(snapshot, Mapping) else {}

            def post_response_fence() -> None:
                if not lease.heartbeat():
                    raise task_gateway.OperationLeaseLost(
                        "账号 lease 心跳失败，远端结果必须重新核验",
                    )

            result = _perform_refresh(
                filename,
                config_snapshot=snapshot,
                report=report,
                checkpoint=checkpoint,
                post_response_fence=post_response_fence,
                is_cancel_requested=lambda: bool(context.is_cancel_requested()),
                mark_settling=lambda: operation_runtime_store.mark_run_settling(run_id),
                on_remote_dispatch=on_remote_dispatch,
                on_remote_response=on_remote_response,
                on_remote_receipt=on_remote_receipt,
                defer_refresh_marker_clear=True,
            )
        _update_account_state(
            email,
            credential_state="valid",
            execution_status="empty",
            last_run_status="success",
            error=None,
            active_run_id=0,
        )
        terminal_result = _b_operation_result(
            "success",
            message="Codex OAuth Token 刷新成功",
            summary=result,
        )
        # Commit the gateway result first. If the process dies before this
        # metadata clear, the producer still sees request_pending and the
        # recovery path promotes it to reconcile instead of refreshing again.
        context.finish(terminal_result)
        _clear_refresh_marker_after_terminal(str(result.get("filename") or filename))
        return None
    except OperationLeaseUnavailable:
        # B's dispatcher owns requeue/backoff for lease contention. Do not
        # turn this into a business failure or submit a second run here.
        raise
    except OperationCancelled as exc:
        summary = _cancelled_summary(filename, str(exc))
        _update_account_state(
            email,
            execution_status="empty",
            last_run_status="cancelled",
            error=_safe_error(exc),
            active_run_id=0,
        )
        return _b_operation_result(
            "cancelled",
            message="Codex token refresh 已在远端请求前取消",
            summary=summary,
            error=_safe_error(exc),
        )
    except TokenRefreshRequestUnknownError as exc:
        remote_response_received = bool(getattr(exc, "remote_response_received", remote_response_received))
        summary = _unknown_summary(
            filename,
            reason=_safe_error(exc),
            action_dispatched=bool(getattr(exc, "action_dispatched", remote_dispatched)),
            remote_response_received=remote_response_received,
            credential_persisted=bool(getattr(exc, "credential_persisted", False)),
            remote_request_id=getattr(exc, "remote_request_id", None),
        )
        _mark_unknown(filename, _safe_error(exc))
        _update_account_state(
            email,
            execution_status="empty",
            last_run_status=REQUEST_UNKNOWN,
            error=_safe_error(exc),
            active_run_id=0,
        )
        return _b_operation_result(
            REQUEST_UNKNOWN,
            message="Codex refresh grant 结果待人工核验",
            summary=summary,
            error=_safe_error(exc),
        )
    except (TokenRefreshReauthRequiredError, TokenRefreshRejectedError, TokenRefreshError) as exc:
        action_dispatched = bool(getattr(exc, "action_dispatched", remote_dispatched))
        response_received = bool(getattr(exc, "remote_response_received", remote_response_received))
        summary = _failed_summary(
            filename,
            exc,
            action_dispatched=action_dispatched,
            remote_response_received=response_received,
            remote_request_id=getattr(exc, "remote_request_id", None),
        )
        _mark_refresh_failure(filename, _safe_error(exc))
        _update_account_state(
            email,
            execution_status="empty",
            last_run_status="failed",
            error=_safe_error(exc),
            active_run_id=0,
        )
        return _b_operation_result(
            "failed",
            message="Codex OAuth Token 刷新失败",
            summary=summary,
            error=_safe_error(exc),
        )
    except Exception as exc:
        if remote_dispatched:
            summary = _unknown_summary(
                filename,
                reason=_safe_error(exc),
                action_dispatched=True,
                remote_response_received=remote_response_received,
                remote_request_id=getattr(exc, "remote_request_id", None),
            )
            _mark_unknown(filename, _safe_error(exc))
            _update_account_state(
                email,
                execution_status="empty",
                last_run_status=REQUEST_UNKNOWN,
                error=_safe_error(exc),
                active_run_id=0,
            )
            return _b_operation_result(
                REQUEST_UNKNOWN,
                message="Codex refresh grant 结果待人工核验",
                summary=summary,
                error=_safe_error(exc),
            )
        summary = _failed_summary(
            filename,
            exc,
            action_dispatched=False,
            remote_response_received=False,
            remote_request_id=getattr(exc, "remote_request_id", None),
        )
        _mark_refresh_failure(filename, _safe_error(exc))
        _update_account_state(
            email,
            execution_status="empty",
            last_run_status="failed",
            error=_safe_error(exc),
            active_run_id=0,
        )
        return _b_operation_result(
            "failed",
            message="Codex OAuth Token 刷新失败",
            summary=summary,
            error=_safe_error(exc),
        )


def _snapshot_for_submission() -> Any:
    """Capture C's immutable published snapshot at durable submission time."""
    from config import non_sensitive_snapshot

    return non_sensitive_snapshot()


def _request_timeout(snapshot: Mapping[str, Any] | None) -> int:
    raw = _config_value(
        snapshot,
        "request_timeout",
        "CODEX_REQUEST_TIMEOUT",
        default=getattr(_cfg, "CODEX_REQUEST_TIMEOUT", 30),
    )
    try:
        return max(5, min(300, int(raw or 30)))
    except (TypeError, ValueError):
        return 30


def _idempotency_key(
    filename: str,
    row: Mapping[str, Any],
    *,
    trigger: str,
    explicit: str | None,
    reconcile: bool,
) -> str:
    if explicit:
        return _safe_text(explicit, 240)
    generation = (
        row.get("oauth_refresh_attempted_at")
        or row.get("last_refresh")
        or row.get("mtime")
        or row.get("updated_at")
        or "initial"
    )
    # ``reconcile`` is not an authorization to issue another remote grant.
    # Keep the same key space for compatibility callers; an unresolved
    # credential is rejected before submission instead of being made unique.
    return _safe_text(f"{TASK_TYPE}:{filename}:{trigger}:normal:{generation}", 240)


def _durable_submit(
    *,
    account_id: int,
    email: str,
    trigger: str,
    batch_id: int | None,
    data: Mapping[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    if not _gateway_supports_operation_context():
        raise RuntimeError("Codex token refresh 需要已部署的 durable operation submit gateway")
    return task_gateway.submit_durable_operation(
        task_type=TASK_TYPE,
        account_id=account_id,
        email=email,
        trigger=trigger,
        source_system="native_operations",
        source_id=idempotency_key,
        idempotency_key=idempotency_key,
        batch_id=batch_id,
        resource_family=RESOURCE_FAMILY,
        data=dict(data),
        config_snapshot=_snapshot_for_submission(),
        config_allowlist=_CONFIG_ALLOWLIST,
        dispatch=True,
    )


def _row_account(row: Mapping[str, Any], email: str) -> tuple[dict[str, Any] | None, int]:
    account = db.get_account_by_email(email) if email else None
    account_id = int(account.get("id") or 0) if account else 0
    return account, account_id


def _registered_account_id(row: Mapping[str, Any]) -> int:
    """Resolve the local account id used by the durable lease/fence.

    ``codex_credentials.account_id`` is normally the provider's ChatGPT
    account identifier, not the PostgreSQL ``registered_accounts.id``.  A
    numeric value remains a compatibility shortcut for migrated rows, but a
    normal producer scan must resolve by email before it can query B's
    reconciliation fence.
    """
    raw_registered_id = row.get("registered_account_id")
    if str(raw_registered_id or "").strip().isdigit() and int(raw_registered_id) > 0:
        return int(raw_registered_id)
    email = str(row.get("email") or "").strip()
    if email:
        _account, account_id = _row_account(row, email)
        if account_id > 0:
            return account_id
    raw_provider_id = row.get("account_id")
    if str(raw_provider_id or "").strip().isdigit() and int(raw_provider_id) > 0:
        return int(raw_provider_id)
    return 0


def _has_reconciliation_marker(value: object) -> bool:
    lowered = str(value or "").strip().lower()
    return any(marker in lowered for marker in _RECONCILIATION_MARKERS)


def enqueue_refresh(
    filename: str,
    *,
    trigger: str = "manual",
    batch_id: str | int | None = None,
    idempotency_key: str | None = None,
    reconcile: bool = False,
) -> dict[str, Any]:
    filename = str(filename or "").strip()
    row = next(
        (item for item in db.list_codex_accounts(archived="all") if item.get("filename") == filename),
        None,
    )
    if row is None:
        return {"accepted": False, "error": "Codex 凭证不存在", "filename": filename}
    decorated = decorate_row(row)
    if str(decorated.get("oauth_account_status") or "").strip().lower() == "deactivated":
        return {
            "accepted": False,
            "error_code": "account_deactivated",
            "next_action": "reauthorize",
            "error": "账号已停用，禁止刷新 Codex OAuth；需先恢复账号后重新授权",
            "filename": filename,
        }
    if not decorated.get("oauth_refreshable"):
        return {
            "accepted": False,
            "error_code": REAUTH_REQUIRED,
            "error": "凭证缺少 refresh_token，只能重跑 OAuth 授权",
            "filename": filename,
        }
    refresh_error = decorated.get("oauth_refresh_error") or row.get("oauth_refresh_error")
    if decorated.get("oauth_reauth_required"):
        return {
            "accepted": False,
            "error_code": REAUTH_REQUIRED,
            "next_action": "reauthorize",
            "error": "refresh token 已被远端拒绝，需要重新 OAuth 授权",
            "filename": filename,
        }
    if _has_reconciliation_marker(refresh_error):
        return {
            "accepted": False,
            "error_code": NEEDS_RECONCILIATION,
            "next_action": "manual_reconcile",
            "reconcile_required": True,
            "error": "上一次 refresh grant 结果未知；当前没有可证明的只读核验结果，禁止再次发送",
            "filename": filename,
        }

    email = str(row.get("email") or decorated.get("email") or "").strip()
    account, account_id = _row_account(row, email)
    if not account_id:
        return {
            "accepted": False,
            "error_code": "account_reference_missing",
            "error": "Codex 凭证没有对应的 registered account，不能申请 durable lease",
            "filename": filename,
            "email": email,
        }
    # The credential marker is only a local projection. A terminal/unknown
    # durable run may exist even when marker writeback was lost, so every
    # public submission performs the same fenced read as the periodic
    # producer before it can create a new remote-write attempt.
    fence_row = dict(row)
    fence_row["registered_account_id"] = account_id
    reconciliation_accounts = _reconciliation_account_ids([fence_row])
    if reconciliation_accounts is None or account_id in reconciliation_accounts:
        return {
            "accepted": False,
            "error_code": NEEDS_RECONCILIATION,
            "next_action": "manual_reconcile",
            "reconcile_required": True,
            "error": (
                "存在待核验的 durable refresh remote-write attempt"
                if reconciliation_accounts is not None
                else "无法读取 durable refresh reconciliation fence，已安全阻止提交"
            ),
            "filename": filename,
            "email": email,
        }
    if reconcile:
        return {
            "accepted": False,
            "error_code": NEEDS_RECONCILIATION,
            "next_action": "manual_reconcile",
            "reconcile_required": True,
            "error": "reconcile 仅用于人工核验，不能创建新的 refresh grant",
            "filename": filename,
            "email": email,
        }
    active = operation_runtime_store.active_run_for_account(
        account_id,
        resource_family=RESOURCE_FAMILY,
    )
    if active:
        return {
            "accepted": False,
            "busy": True,
            "error": "该凭证已有排队或运行中的 durable refresh 任务",
            "task_id": int(active.get("task_id") or 0) or None,
            "run_id": int(active.get("id") or 0) or None,
            "status": str(active.get("status") or ""),
            "filename": filename,
            "email": email,
        }

    try:
        _register_worker()
        native_batch_id = (
            int(batch_id) if isinstance(batch_id, int) and not isinstance(batch_id, bool) and int(batch_id) > 0
            else None
        )
        data: dict[str, Any] = {
            "credential_filename": filename,
            "resource_family": RESOURCE_FAMILY,
        }
        if batch_id is not None and native_batch_id is None:
            data["legacy_batch_id"] = _safe_text(batch_id, 120)
        key = _idempotency_key(
            filename,
            row,
            trigger=str(trigger or "manual"),
            explicit=idempotency_key,
            reconcile=bool(reconcile),
        )
        result = _durable_submit(
            account_id=account_id,
            email=email,
            trigger=str(trigger or "manual"),
            batch_id=native_batch_id,
            data=data,
            idempotency_key=key,
        )
    except Exception as exc:
        if "uq_operation_runs_active_account_family" in str(exc) or "duplicate key" in str(exc).lower():
            active = operation_runtime_store.active_run_for_account(
                account_id,
                resource_family=RESOURCE_FAMILY,
            )
            return {
                "accepted": False,
                "busy": True,
                "error": "该凭证已有排队或运行中的 durable refresh 任务",
                "task_id": int(active.get("task_id") or 0) or None if active else None,
                "run_id": int(active.get("id") or 0) or None if active else None,
                "filename": filename,
                "email": email,
            }
        return {
            "accepted": False,
            "error_code": "durable_submit_failed",
            "error": f"刷新任务创建失败: {_safe_error(exc)}",
            "filename": filename,
            "email": email,
        }
    if result.get("accepted") and not result.get("reused"):
        _update_account_state(email, execution_status="queued", active_run_id=result.get("run_id") or 0)
    result.update({"filename": filename, "email": email})
    return result


def _reconcile_abandoned_refresh_markers(rows: list[Mapping[str, Any]]) -> int:
    """Fence a pre-dispatch marker left by a crashed worker.

    Recovery is intentionally one-way: a pending marker with no active run is
    promoted to request_unknown. A scheduler may not infer that the provider
    did not rotate the token and send the grant again.
    """
    reconciled = 0
    for row in rows:
        if str(row.get("oauth_refresh_error") or "").strip().lower() != REQUEST_PENDING:
            continue
        filename = str(row.get("filename") or "").strip()
        email = str(row.get("email") or "").strip()
        _account, account_id = _row_account(row, email)
        if not account_id:
            _mark_unknown(filename, "worker restart left refresh request_pending without account reference")
            reconciled += 1
            continue
        try:
            active = operation_runtime_store.active_run_for_account(
                account_id,
                resource_family=RESOURCE_FAMILY,
            )
        except Exception:
            logger.exception("检查 Codex token refresh orphan run 失败：filename=%s", filename)
            continue
        if active:
            continue
        _mark_unknown(filename, "worker restart left refresh request_pending without active durable run")
        reconciled += 1
    return reconciled


def _reconciliation_account_ids(rows: list[Mapping[str, Any]]) -> set[int] | None:
    """Read B's durable producer fence for the accounts in this scan.

    ``None`` means the fence could not be read.  The scheduler must fail
    closed in that case; submitting a new refresh without proving the last
    native run is clear would defeat the remote-write intent contract.
    """
    try:
        account_ids = {
            account_id
            for row in rows
            if (account_id := _registered_account_id(row)) > 0
        }
    except Exception:
        logger.exception("解析 Codex token refresh producer account fence 失败")
        return None
    if not account_ids:
        return set()
    list_fence = getattr(operation_runtime_store, "list_reconciliation_accounts", None)
    if not callable(list_fence):
        logger.error("Codex token refresh 缺少 durable reconciliation producer fence")
        return None
    fenced_ids: set[int] = set()
    candidates = sorted(account_ids)
    for offset in range(0, len(candidates), _RECONCILIATION_QUERY_BATCH_SIZE):
        candidate_batch = candidates[offset:offset + _RECONCILIATION_QUERY_BATCH_SIZE]
        try:
            fenced = list_fence(
                task_type=TASK_TYPE,
                account_ids=candidate_batch,
                source_systems=("native_operations",),
                # The candidate filter is authoritative; batching prevents a
                # global LIMIT from dropping later candidates while B's query
                # deduplicates multiple runs for one account.
                limit=5000,
            )
        except Exception:
            logger.exception(
                "读取 Codex token refresh durable producer fence 失败：batch_offset=%s",
                offset,
            )
            return None
        for item in fenced:
            if (
                isinstance(item, Mapping)
                and str(item.get("account_id") or "").strip().isdigit()
                and int(item.get("account_id") or 0) > 0
            ):
                fenced_ids.add(int(item["account_id"]))
    return fenced_ids


def enqueue_due_credentials() -> dict[str, int]:
    if not bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)):
        return {"started": 0, "skipped": 0, "reconciled": 0}
    maximum = max(1, min(200, int(getattr(_cfg, "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", 20) or 20)))
    started = 0
    skipped = 0
    rows = db.list_codex_accounts(archived="0")
    reconciled = _reconcile_abandoned_refresh_markers(rows)
    reconciliation_accounts = _reconciliation_account_ids(rows)
    for row in rows:
        decorated = decorate_row(row)
        if decorated.get("oauth_status") not in {"expiring", "expired"}:
            skipped += 1
            continue
        if not decorated.get("oauth_refreshable"):
            skipped += 1
            continue
        if decorated.get("oauth_reauth_required"):
            skipped += 1
            continue
        if _has_reconciliation_marker(
            decorated.get("oauth_refresh_error") or row.get("oauth_refresh_error")
        ):
            skipped += 1
            continue
        account_id = _registered_account_id(row)
        if not account_id and str(row.get("email") or "").strip():
            # A named credential must resolve to the same registered account
            # used by enqueue_refresh before it can cross the remote-write
            # fence. Rows without even an email remain a compatibility path;
            # enqueue_refresh will reject them before submission.
            skipped += 1
            continue
        if account_id and (
            reconciliation_accounts is None or account_id in reconciliation_accounts
        ):
            skipped += 1
            continue
        if started >= maximum:
            skipped += 1
            continue
        queued = enqueue_refresh(str(row.get("filename") or ""), trigger="codex_token_refresh_scheduled")
        if queued.get("accepted"):
            started += 1
        else:
            skipped += 1
    return {"started": started, "skipped": skipped, "reconciled": reconciled}


SCHEDULER_TASK = "codex_token_refresh"


def scheduler_enabled() -> bool:
    return bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True))


def scheduler_interval_seconds() -> int:
    raw = int(getattr(_cfg, "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", 86400) or 86400)
    return max(300, min(86400, raw))


def _scheduler_loop() -> None:
    initial = max(10, min(3600, int(getattr(_cfg, "CODEX_TOKEN_REFRESH_INITIAL_DELAY_SECONDS", 120) or 120)))
    scheduler_state.run_periodic(
        task=SCHEDULER_TASK,
        label="Codex Token Refresh",
        work=enqueue_due_credentials,
        enabled=scheduler_enabled,
        interval_seconds=scheduler_interval_seconds,
        initial_delay_seconds=initial,
    )


def start_periodic_refresher() -> bool:
    global _SCHEDULER_STARTED
    try:
        _register_worker()
    except Exception:
        logger.exception("Codex token refresh durable handler registration failed")
        return False
    if not bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)):
        logger.info("[Codex Token Refresh] periodic refresher disabled")
        return False
    with _LOCK:
        if _SCHEDULER_STARTED:
            return False
        _SCHEDULER_STARTED = True
    # This thread is a producer only. The shared gateway owns claim, lease,
    # executor submission and terminal result persistence.
    threading.Thread(target=_scheduler_loop, name="codex-token-refresh-producer", daemon=True).start()
    logger.info(
        "[Codex Token Refresh] enabled interval=%ss before=%sh max_per_cycle=%s next_due_in=%ss",
        scheduler_interval_seconds(),
        getattr(_cfg, "CODEX_TOKEN_REFRESH_BEFORE_HOURS", 24),
        getattr(_cfg, "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", 20),
        int(scheduler_state.seconds_until_due(SCHEDULER_TASK, scheduler_interval_seconds())),
    )
    return True


def resume_queued(*, limit: int | None = None) -> int:
    """Register and wake the shared dispatcher without claiming a run."""
    try:
        _register_worker()
    except Exception:
        logger.exception("恢复 Codex token refresh handler 失败")
        return 0
    task_gateway.notify_dispatch()
    try:
        rows = operation_runtime_store.list_queued_runs(limit=int(limit or 500))
    except Exception:
        logger.exception("读取 Codex token refresh queued runs 失败")
        return 0
    return sum(1 for row in rows if str(row.get("task_type") or "") == TASK_TYPE)


def request_cancel(
    *,
    run_id: int | None = None,
    email: str = "",
    account_id: int | None = None,
) -> dict[str, Any]:
    """Persist a cooperative cancel request; no process-local cancellation state."""
    if run_id is None:
        if account_id is None and email:
            account = db.get_account_by_email(str(email).strip()) or {}
            account_id = int(account.get("id") or 0) or None
        if account_id:
            active = operation_runtime_store.active_run_for_account(
                int(account_id),
                resource_family=RESOURCE_FAMILY,
            )
            if active:
                run_id = int(active.get("id") or 0) or None
                email = str(active.get("email_snapshot") or email or "").strip()
    if not run_id:
        return {"ok": True, "running": False, "state": "empty", "message": "没有排队或运行中的 token refresh"}
    try:
        run = operation_runtime_store.request_run_cancel(
            int(run_id), reason="用户手动停止 Codex token refresh",
        )
    except LookupError as exc:
        return {"ok": False, "error": str(exc), "run_id": int(run_id)}
    status = str(run.get("status") or "cancelling")
    if not email:
        current = operation_runtime_store.get_run(int(run_id)) or {}
        email = str(current.get("email_snapshot") or "").strip()
    _update_account_state(
        email,
        execution_status="empty" if status == "cancelled" else "cancelling",
        last_run_status="cancelled" if status == "cancelled" else None,
        error="用户手动停止 Codex token refresh",
        active_run_id=0 if status == "cancelled" else int(run_id),
    )
    task_gateway.notify_dispatch()
    return {
        "ok": True,
        "run_id": int(run_id),
        "running": status != "cancelled",
        "state": status,
        "message": "已记录停止请求，任务将在安全检查点收口",
    }


def is_retrying(email: str) -> bool:
    account = db.get_account_by_email(str(email or "")) or {}
    account_id = int(account.get("id") or 0)
    return bool(
        account_id
        and operation_runtime_store.active_run_for_account(
            account_id,
            resource_family=RESOURCE_FAMILY,
        )
    )


def settings() -> dict[str, Any]:
    return {
        "enabled": bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)),
        "refresh_before_hours": int(getattr(_cfg, "CODEX_TOKEN_REFRESH_BEFORE_HOURS", 24) or 24),
        "scan_interval_seconds": int(getattr(_cfg, "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", 86400) or 86400),
        "max_per_cycle": int(getattr(_cfg, "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", 20) or 20),
        "auto_sync_sub2api": bool(getattr(_cfg, "CODEX_TOKEN_AUTO_SYNC_SUB2API", True)),
        "durable_tasks": True,
        "scheduler_role": "producer_only",
        "dispatcher_role": "shared_task_gateway",
        "retry_policy": "no_automatic_refresh_retry",
        "request_unknown_next_action": "manual_reconcile",
        "resource_family": RESOURCE_FAMILY,
    }
