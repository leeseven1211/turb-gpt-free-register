# -*- coding: utf-8 -*-
"""Unified explicit task event facade for legacy account-operation workers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.operations import task_gateway
from core.operations.stages import normalize_step_state
from core.operations import run_log as task_run_log


@dataclass(frozen=True)
class TaskReporter:
    task_id: int | None

    def _context_task_binding(self) -> tuple[int | None, int | None]:
        current = task_run_log.current_context()
        current_task = current.get("task_id")
        # 注册流程内可能同步创建一个 account_action 子任务。普通 logger
        # 仍属于外层 Run，不能被子任务 TaskReporter 改写 task_id/run_id。
        if current_task is not None and self.task_id is not None and int(current_task) != int(self.task_id):
            return int(current_task), current.get("run_id")
        return self.task_id, current.get("run_id")

    def _bind_event_context(self, stage: str, event: object | None = None) -> None:
        """让后续普通 logger 记录继承最近一次结构化阶段。"""
        metadata = {}
        if isinstance(event, dict):
            metadata = {
                "event_id": event.get("event_id", event.get("id")),
                "event_uuid": event.get("event_uuid"),
                "source_event_id": event.get("source_event_id"),
                "source_system": event.get("source_system"),
                "main_step_id": event.get("main_step_id"),
            }
            metadata = {key: value for key, value in metadata.items() if value is not None}
        task_id, run_id = self._context_task_binding()
        if self.task_id is not None and task_id != self.task_id:
            # 子任务事件不能借用外层 Run 的日志路径携带自己的事件身份。
            metadata = {}
        task_run_log.set_current_stage(stage, task_id=task_id, run_id=run_id, **metadata)

    def start(self, message: str = "开始执行") -> None:
        task_id, run_id = self._context_task_binding()
        task_run_log.set_current_stage("preflight", task_id=task_id, run_id=run_id)
        task_gateway.start_task(self.task_id, message=message)

    def stage(
        self,
        stage: str,
        state: str,
        message: str,
        *,
        level: str = "INFO",
        detail: dict | None = None,
    ) -> None:
        normalized = normalize_step_state(state)
        if normalized is None:
            raise ValueError(f"不支持的任务步骤状态: {state!r}")
        self._bind_event_context(stage)
        event = task_gateway.append_event(
            self.task_id,
            stage=stage,
            state=normalized,
            event_type=f"stage.{normalized}",
            message=message,
            level=level,
            detail=detail,
        )
        self._bind_event_context(stage, event)

    def note(
        self,
        message: str,
        *,
        stage: str = "event",
        level: str = "INFO",
        event_type: str | None = None,
        detail: dict | None = None,
    ) -> None:
        level_value = str(level or "INFO").upper()
        self._bind_event_context(stage)
        event = task_gateway.append_event(
            self.task_id,
            stage=stage,
            message=message,
            level=level_value,
            event_type=event_type or ("note.error" if level_value == "ERROR" else "note.warning" if level_value == "WARNING" else "note.info"),
            detail=detail,
        )
        self._bind_event_context(stage, event)

    def resource(
        self,
        event_type: str,
        message: str,
        *,
        stage: str = "network",
        detail: dict | None = None,
        level: str = "INFO",
    ) -> None:
        if event_type not in {"resource.acquired", "resource.rotated", "resource.released"}:
            raise ValueError(f"不支持的资源事件: {event_type!r}")
        self.note(message, stage=stage, level=level, event_type=event_type, detail=detail)

    def finish(self, *, status: str, message: str, **kwargs: Any) -> None:
        task_gateway.finish_task(self.task_id, status=status, message=message, **kwargs)
