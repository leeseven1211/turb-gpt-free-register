"""原生账号操作的浏览器诊断：按 Task/Run 隔离，不修改注册任务。"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import threading
from typing import Any

from core.registration import debug as registration_debug

logger = logging.getLogger('core.operation_debug')
_LOCK = threading.RLock()
_ACTIVE: dict[tuple[int, int], "OperationDebugSession"] = {}


def artifact_job(task: dict, run: dict) -> dict:
    """只从已校验的任务记录生成目录，调用方不能指定文件路径。"""
    task_id, run_id = int(task["id"]), int(run["id"])
    return {
        # 基类 finalize 会清理注册会话表；负数不会与真实注册任务 ID 冲突。
        "id": -run_id,
        "job_uuid": f"operation-{task.get('task_uuid') or task_id}-run-{run.get('run_uuid') or run_id}",
        "job_type": "token_refresh", "run_id": run_id,
        "operation_task_id": task_id, "operation_run_id": run_id,
        "execution_id": run.get("execution_id"), "progress_stage": "preflight",
        "debug_enabled": True,
    }


class OperationDebugSession(registration_debug.RegistrationDebugSession):
    """复用采集器和本地产物，失败只保存现场，不暂停批量任务线程。"""

    capture_without_pause = True

    @staticmethod
    def _failure_category(reason: str, state: dict, network: list[dict] | None = None) -> str:
        text = str(reason or "").lower()
        if "email_submit_unconfirmed" in text:
            return "auth_submission_unconfirmed"
        if "forwardimap" in text:
            return "mail_service"
        return registration_debug.RegistrationDebugSession._failure_category(reason, state, network)

    @staticmethod
    def _failure_category_label(category: str) -> str:
        if category == "mail_service":
            return "邮箱收码服务"
        if category == "auth_submission_unconfirmed":
            return "认证提交未确认"
        return registration_debug.RegistrationDebugSession._failure_category_label(category)

    def _patch_job(self, **changes: Any) -> None:
        self.job.update(changes)

    def _refresh_terminal_context(self) -> None:
        # 原生操作没有 registration_jobs 记录，禁止按同数字 ID 查注册表。
        return None

    def _context_fields(self) -> dict[str, Any]:
        return {
            **super()._context_fields(),
            "operation_task_id": self.job.get("operation_task_id"),
            "operation_run_id": self.job.get("operation_run_id"),
        }

    def pause_failure(self, driver: Any, reason: str) -> str:
        if self.failure_captured:
            return self.debug_state
        self.failure_captured = True
        self.failure_stage = self.current_stage
        self._classify_failure(reason)
        if driver is not None:
            self.capture_page_snapshot(driver, reason)
        else:
            self._start_capture()
        self.debug_state = "captured"
        self.record({"kind": "failure_diagnostics", "reason": str(reason)[:1000], **self._context_fields()})
        return self.debug_state


@dataclass
class Activation:
    session: OperationDebugSession
    token: Any
    key: tuple[int, int]


def activate(context) -> Activation | None:
    """为原生刷新建立当前采集会话，保留调用方已有的注册调试上下文。"""
    if context is None or registration_debug.current_session() is not None:
        return None
    from core import operation_task_store

    task = operation_task_store.get_task(int(context.task_id), include_events=False)
    if not task or task.get("source_system") != "native_operations":
        return None
    run = next((item for item in task.get("runs") or [] if int(item["id"]) == int(context.run_id)), None)
    if run is None:
        return None
    session = OperationDebugSession(artifact_job(task, run), capture_mode="full")
    key = (int(context.task_id), int(context.run_id))
    with _LOCK:
        _ACTIVE[key] = session
    token = registration_debug._CURRENT_SESSION.set(session)
    logger.info("[账号操作调试] Roxy 刷新调试已开启：全程抓包，失败保存现场；入口为任务日志的诊断资源")
    return Activation(session, token, key)


def deactivate(activation: Activation | None, status: str = "") -> None:
    if activation is None:
        return
    try:
        activation.session.finalize("failed" if status == "attention_required" else status)
    except Exception:
        logger.exception("[账号操作调试] 收口采集失败：task_id=%s run_id=%s", *activation.key)
    finally:
        registration_debug._CURRENT_SESSION.reset(activation.token)
        with _LOCK:
            _ACTIVE.pop(activation.key, None)


def describe(task: dict, run: dict) -> dict:
    """普通任务详情只返回可用状态和计数，不返回页面正文或原始请求。"""
    job = artifact_job(task, run)
    path = registration_debug._artifact_dir_for_job(job)
    with _LOCK:
        active = _ACTIVE.get((int(task["id"]), int(run["id"])))
    manifest: dict = {}
    manifest_path = path / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    available = active is not None or manifest_path.is_file() or (path / "network.jsonl.gz").is_file()
    summary = active.summary() if active is not None else manifest.get("summary") or {}
    return {
        "available": available,
        "state": "recording" if active is not None else str(manifest.get("status") or "interrupted") if available else "unavailable",
        "failure_captured": bool((path / "last-page.json").is_file()),
        "screenshot_available": (path / "last-page.png").is_file(),
        "page_state_available": (path / "last-page.json").is_file(),
        "summary": {key: summary.get(key, 0) for key in (
            "request_count", "failed_count", "http_error_count", "websocket_frame_count", "dropped_event_count",
        )},
    }
