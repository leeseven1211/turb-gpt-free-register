# -*- coding: utf-8 -*-
"""Codex OAuth access token 状态、refresh grant 与后台巡检。"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from config import codex as _cfg
from core import scheduler_state
from core.operations import task_gateway as account_task_store
from core.task_reporter import TaskReporter
from core.storage import codex as db
from core.account_operation_executor import executor as _EXECUTOR

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_IN_FLIGHT: set[str] = set()
_SCHEDULER_STARTED = False
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def decorate_row(row: dict[str, Any]) -> dict[str, Any]:
    """读取凭证内容后为列表行补齐 OAuth 状态；失败时保持列表可用。"""
    item = dict(row)
    if item.get("oauth_status"):
        item["oauth_reauth_required"] = (
            refresh_error_requires_reauth(item.get("oauth_refresh_error"))
            or sub2api_status_requires_reauth(item.get("sub2api_http_status"))
        )
        return item
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
    return item


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
            return detail[:500]
    return f"HTTP {int(getattr(response, 'status_code', 0) or 0)}"


def _request_refresh(refresh_token: str) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "client_id": str(getattr(_cfg, "CODEX_CLIENT_ID", "") or ""),
        "refresh_token": refresh_token,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "turb-gpt-free-register/codex-token-refresh",
    }
    timeout = max(5, int(getattr(_cfg, "CODEX_REQUEST_TIMEOUT", 30) or 30))
    last_error = ""
    for attempt in range(1, 4):
        try:
            response = requests.post(
                str(getattr(_cfg, "CODEX_TOKEN_URL", "") or ""),
                headers=headers,
                data=data,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < 3:
                time.sleep(attempt)
                continue
            raise RuntimeError(f"Codex token 刷新网络失败: {last_error[:300]}") from exc

        if response.status_code == 200:
            try:
                payload = response.json()
            except Exception as exc:
                raise RuntimeError("Codex token 刷新响应不是 JSON") from exc
            if not isinstance(payload, dict) or not str(payload.get("access_token") or "").strip():
                raise RuntimeError("Codex token 刷新响应缺少 access_token")
            return payload
        if response.status_code == 429 or response.status_code >= 500:
            last_error = _refresh_error(response)
            if attempt < 3:
                time.sleep(attempt)
                continue
        raise RuntimeError(f"Codex token 刷新失败: {_refresh_error(response)}")
    raise RuntimeError(f"Codex token 刷新失败: {last_error or '重试耗尽'}")


def refresh_credential(filename: str) -> dict[str, Any]:
    """对一份本地凭证执行 refresh_token grant 并原子更新文件。"""
    text, actual_filename = db.read_codex_credential(filename)
    content = json.loads(text)
    if not isinstance(content, dict):
        raise RuntimeError("Codex 凭证不是 JSON 对象")
    old_refresh_token = str(content.get("refresh_token") or "").strip()
    if not old_refresh_token:
        raise RuntimeError("凭证缺少 refresh_token，只能重新执行 OAuth 授权")

    token_response = _request_refresh(old_refresh_token)
    updated = dict(content)
    updated["access_token"] = str(token_response.get("access_token") or "")
    updated["refresh_token"] = str(token_response.get("refresh_token") or old_refresh_token)
    if token_response.get("id_token"):
        updated["id_token"] = str(token_response.get("id_token") or "")
    refreshed_at = _utc_now()
    updated["last_refresh"] = _iso_utc(refreshed_at)
    expires_in = token_response.get("expires_in")
    try:
        expires_at = refreshed_at + timedelta(seconds=max(1, int(expires_in)))
    except (TypeError, ValueError):
        expires_at = _jwt_exp(updated["access_token"])
    if expires_at is not None:
        updated["expired"] = _iso_utc(expires_at)
    else:
        updated["expired"] = ""

    db.write_codex_credential(actual_filename, updated)
    db.mark_codex_oauth_refresh(actual_filename, error=None)
    metadata = oauth_metadata(updated)
    return {
        "ok": True,
        "filename": actual_filename,
        "email": str(updated.get("email") or ""),
        "expired": str(updated.get("expired") or ""),
        **metadata,
    }


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
        error = f"{type(exc).__name__}: {exc}"
        db.mark_codex_sub2_sync_error(filename, error)
        return {"status": "failed", "error": error[:500]}
    db.mark_codex_sub2_uploaded(filename)
    return {"status": "success", "updated": result.get("updated")}


def _run_worker(filename: str, task_id: int) -> None:
    reporter = TaskReporter(task_id)
    reporter.start(message="开始刷新 Codex OAuth Token")
    reporter.stage(
        "refresh_token", "running",
        message="使用 refresh_token 换取新的 access token",
    )
    try:
        result = refresh_credential(filename)
        sync_result = _sync_sub2_if_needed(filename)
        result["sub2_sync"] = sync_result.get("status")
        if sync_result.get("status") == "failed":
            result["sub2_sync_error"] = sync_result.get("error")
        message = "Codex OAuth Token 刷新成功"
        if sync_result.get("status") == "failed":
            message += "，但同步 sub2api 失败"
        reporter.stage("refresh_token", "success", message, detail={"sub2_sync": sync_result.get("status")})
        reporter.finish(
            status="success",
            message=message,
            result_summary=result,
            validation_method="oauth_refresh_token",
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        try:
            db.mark_codex_oauth_refresh(filename, error=error)
        except Exception:
            logger.exception("记录 Codex OAuth 刷新失败状态异常: filename=%s", filename)
        reporter.stage("refresh_token", "failed", "Codex OAuth Token 刷新失败", level="ERROR", detail={"error": error})
        reporter.finish(
            status="failed",
            message="Codex OAuth Token 刷新失败",
            error=error,
            result_summary={"ok": False, "filename": filename},
            validation_method="oauth_refresh_token",
        )
        logger.warning("[Codex Token Refresh] %s: %s", filename, error[:500])
    finally:
        with _LOCK:
            _IN_FLIGHT.discard(filename)


def enqueue_refresh(filename: str, *, trigger: str = "manual", batch_id: str | None = None) -> dict[str, Any]:
    filename = str(filename or "").strip()
    row = next(
        (item for item in db.list_codex_accounts(archived="all") if item.get("filename") == filename),
        None,
    )
    if row is None:
        return {"accepted": False, "error": "Codex 凭证不存在", "filename": filename}
    decorated = decorate_row(row)
    if not decorated.get("oauth_refreshable"):
        return {"accepted": False, "error": "凭证缺少 refresh_token，只能重跑 OAuth 授权", "filename": filename}
    with _LOCK:
        if filename in _IN_FLIGHT:
            return {"accepted": False, "busy": True, "error": "该凭证正在刷新", "filename": filename}
        _IN_FLIGHT.add(filename)

    email = str(row.get("email") or "")
    account = db.get_account_by_email(email) if email else None
    try:
        task_id = account_task_store.create_task(
            task_type="codex_token_refresh",
            account_id=int(account.get("id") or 0) or None if account else None,
            email=email,
            trigger=trigger,
            batch_id=batch_id,
        )
        _EXECUTOR.submit(_run_worker, filename, task_id)
    except Exception as exc:
        with _LOCK:
            _IN_FLIGHT.discard(filename)
        return {"accepted": False, "error": f"刷新任务创建失败: {type(exc).__name__}: {exc}", "filename": filename}
    return {"accepted": True, "task_id": task_id, "filename": filename, "email": email}


def enqueue_due_credentials() -> dict[str, int]:
    if not bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)):
        return {"started": 0, "skipped": 0}
    maximum = max(1, min(200, int(getattr(_cfg, "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", 20) or 20)))
    started = 0
    skipped = 0
    for row in db.list_codex_accounts(archived="0"):
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
        if started >= maximum:
            skipped += 1
            continue
        queued = enqueue_refresh(str(row.get("filename") or ""), trigger="codex_token_refresh_scheduled")
        if queued.get("accepted"):
            started += 1
        else:
            skipped += 1
    return {"started": started, "skipped": skipped}


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
    if not bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)):
        logger.info("[Codex Token Refresh] periodic refresher disabled")
        return False
    with _LOCK:
        if _SCHEDULER_STARTED:
            return False
        _SCHEDULER_STARTED = True
    threading.Thread(target=_scheduler_loop, name="codex-token-refresh-scheduler", daemon=True).start()
    logger.info(
        "[Codex Token Refresh] enabled interval=%ss before=%sh max_per_cycle=%s next_due_in=%ss",
        scheduler_interval_seconds(),
        getattr(_cfg, "CODEX_TOKEN_REFRESH_BEFORE_HOURS", 24),
        getattr(_cfg, "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", 20),
        int(scheduler_state.seconds_until_due(SCHEDULER_TASK, scheduler_interval_seconds())),
    )
    return True


def settings() -> dict[str, Any]:
    return {
        "enabled": bool(getattr(_cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True)),
        "refresh_before_hours": int(getattr(_cfg, "CODEX_TOKEN_REFRESH_BEFORE_HOURS", 24) or 24),
        "scan_interval_seconds": int(getattr(_cfg, "CODEX_TOKEN_REFRESH_SCAN_INTERVAL_SECONDS", 86400) or 86400),
        "max_per_cycle": int(getattr(_cfg, "CODEX_TOKEN_REFRESH_MAX_PER_CYCLE", 20) or 20),
        "auto_sync_sub2api": bool(getattr(_cfg, "CODEX_TOKEN_AUTO_SYNC_SUB2API", True)),
    }
