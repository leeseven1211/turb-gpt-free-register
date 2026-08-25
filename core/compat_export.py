# -*- coding: utf-8 -*-
"""兼容文件的去抖导出器。

PostgreSQL 是唯一事实来源；根目录那些 JSON/TXT 和 accounts_viewer.html 只是
给 CLI、CPA 和人工导出用的兼容产物。但它们原先是在每次写入的主路径上同步生成的：
改一个账号备注要重写 2.1 MB JSON + 2.5 MB viewer + 0.4 MB token.txt，
接口要等这几百毫秒才返回。

这里把导出从主路径上摘下来：写库照旧同步（数据安全不受影响），导出改成后台
去抖任务，窗口内的多次变更合并成一次渲染。

导出器不接收行数据，只接收一个"种类"名，到点后自己从库里重新读当前状态。
这样合并天然是对的——最后一次渲染写的一定是最新状态，也不必在内存里留着
几 MB 的快照。

环境变量（内部性能开关，与 ACCOUNT_TASK_DB_SCHEMA 同类，不进 WebUI 配置页）：
    COMPAT_EXPORT_MODE=debounced|sync|off   默认 debounced
    COMPAT_EXPORT_DEBOUNCE_SECONDS=5.0
"""
from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

_CV = threading.Condition()
_EXPORTERS: dict[str, Callable[[], None]] = {}
_DIRTY: set[str] = set()
_DEADLINE: float = 0.0
_WORKER: threading.Thread | None = None
_STOPPING = False
_DEFAULT_DEBOUNCE = 5.0
_RUN_LOCK = threading.RLock()


def mode() -> str:
    value = str(os.getenv("COMPAT_EXPORT_MODE") or "debounced").strip().lower()
    return value if value in {"debounced", "sync", "off"} else "debounced"


def debounce_seconds() -> float:
    raw = str(os.getenv("COMPAT_EXPORT_DEBOUNCE_SECONDS") or "").strip()
    if not raw:
        return _DEFAULT_DEBOUNCE
    try:
        return max(0.0, float(raw))
    except ValueError:
        return _DEFAULT_DEBOUNCE


def register(kind: str, exporter: Callable[[], None]) -> None:
    """登记某一类兼容产物的渲染函数。函数自己从库里读当前状态。"""
    with _CV:
        _EXPORTERS[str(kind)] = exporter


def schedule(kind: str) -> None:
    """标记某类兼容产物为待导出。"""
    current = mode()
    if current == "off":
        return
    if current == "sync":
        _run_one(kind)
        return
    global _DEADLINE
    with _CV:
        if kind not in _EXPORTERS:
            logger.warning("[兼容导出] 未登记的种类：%s", kind)
            return
        _DIRTY.add(kind)
        _DEADLINE = time.monotonic() + debounce_seconds()
        _ensure_worker_locked()
        _CV.notify_all()


def _ensure_worker_locked() -> None:
    global _WORKER
    if _WORKER is not None and _WORKER.is_alive():
        return
    _WORKER = threading.Thread(target=_loop, name="compat-export", daemon=True)
    _WORKER.start()


def _run_one(kind: str) -> None:
    with _CV:
        exporter = _EXPORTERS.get(kind)
    if exporter is None:
        return
    try:
        # sync 模式和 flush/后台线程可能同时到达；文件导出必须串行，否则两个
        # 渲染器会争抢同一个临时文件。业务数据库写入不受这把锁影响。
        with _RUN_LOCK:
            exporter()
    except Exception:
        # 兼容文件不是事实来源，导出失败不该影响业务写入；但必须留下完整堆栈，
        # 否则文件会悄悄变旧。这里不重试：持续失败时重试只会刷屏。
        logger.exception("[兼容导出] %s 渲染失败，文件将保持上一次的内容", kind)


def _loop() -> None:
    while True:
        with _CV:
            while not _DIRTY and not _STOPPING:
                _CV.wait()
            if _STOPPING and not _DIRTY:
                return
            # 等到静默窗口结束；期间有新变更会把 _DEADLINE 推后
            while not _STOPPING:
                remaining = _DEADLINE - time.monotonic()
                if remaining <= 0:
                    break
                _CV.wait(remaining)
            kinds = sorted(_DIRTY)
            _DIRTY.clear()
        for kind in kinds:
            _run_one(kind)


def flush(kinds: list[str] | None = None) -> list[str]:
    """立刻在当前线程渲染待导出内容。进程退出前和"立即导出"入口用。"""
    with _CV:
        targets = sorted(_DIRTY) if kinds is None else [k for k in kinds if k in _EXPORTERS]
        _DIRTY.difference_update(targets)
    for kind in targets:
        _run_one(kind)
    return targets


def pending() -> list[str]:
    with _CV:
        return sorted(_DIRTY)


def shutdown() -> None:
    """进程退出时把没写完的导出补上，避免文件停留在旧内容。"""
    global _STOPPING
    flush()
    with _CV:
        _STOPPING = True
        _CV.notify_all()


atexit.register(shutdown)
