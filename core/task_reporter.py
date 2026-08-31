# -*- coding: utf-8 -*-
"""Unified explicit task event facade for legacy account-operation workers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.operations import task_gateway
from core.task_stages import normalize_step_state


@dataclass(frozen=True)
class TaskReporter:
    task_id: int | None

    def start(self, message: str = "开始执行") -> None:
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
        task_gateway.append_event(
            self.task_id,
            stage=stage,
            state=normalized,
            event_type=f"stage.{normalized}",
            message=message,
            level=level,
            detail=detail,
        )

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
        task_gateway.append_event(
            self.task_id,
            stage=stage,
            message=message,
            level=level_value,
            event_type=event_type or ("note.error" if level_value == "ERROR" else "note.warning" if level_value == "WARNING" else "note.info"),
            detail=detail,
        )

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
