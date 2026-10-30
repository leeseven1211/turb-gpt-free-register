"""统一 operation schema 生命周期入口。"""
from __future__ import annotations

from typing import Any


def init() -> None:
    from core.storage.operations import store as operation

    operation.init()
    # Remail 意图与统一任务中心共用当前 PostgreSQL schema；建表仍是增量、幂等迁移。
    from core.storage.email import remail_orders

    remail_orders.init()


def reset_ready() -> None:
    from core.storage.operations import store as operation

    operation.reset_ready()
    from core.storage.email import remail_orders

    remail_orders._READY_KEY = ""


__all__ = ["init", "reset_ready"]
