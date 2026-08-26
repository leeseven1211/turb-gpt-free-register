"""统一 operation schema 生命周期入口。"""
from __future__ import annotations

from typing import Any


def init() -> None:
    from core.storage import operation

    operation.init()


def reset_ready() -> None:
    from core.storage import operation

    operation.reset_ready()


__all__ = ["init", "reset_ready"]
