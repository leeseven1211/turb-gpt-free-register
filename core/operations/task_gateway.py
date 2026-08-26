"""账号任务统一提交/事件/终态入口。

当前兼容期保留 ``account_action_*`` 作为写模型，同时由存储投影同步到统一
``operation_*`` 模型。业务服务只依赖本模块，后续可以把实现替换成原生 run，而不必
再次修改查活、套餐、封号、Token 刷新和注册后置流程。
"""
from __future__ import annotations

from typing import Any


def _legacy():
    from core.operations import legacy_task_store

    return legacy_task_store


def init() -> None:
    return _legacy().init()


def create_batch(**kwargs: Any) -> str:
    return _legacy().create_batch(**kwargs)


def create_task(**kwargs: Any) -> int:
    return _legacy().create_task(**kwargs)


def start_task(task_id: int | None, **kwargs: Any) -> None:
    return _legacy().start_task(task_id, **kwargs)


def append_event(task_id: int | None, **kwargs: Any) -> None:
    return _legacy().append_event(task_id, **kwargs)


def finish_task(task_id: int | None, **kwargs: Any) -> None:
    return _legacy().finish_task(task_id, **kwargs)


def recover_interrupted() -> int:
    return _legacy().recover_interrupted()


def list_tasks(**kwargs: Any) -> dict:
    return _legacy().list_tasks(**kwargs)


def get_task(task_id: int) -> dict | None:
    return _legacy().get_task(task_id)


__all__ = [
    "init", "create_batch", "create_task", "start_task", "append_event", "finish_task",
    "recover_interrupted", "list_tasks", "get_task",
]
