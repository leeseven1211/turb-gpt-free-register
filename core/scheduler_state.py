# -*- coding: utf-8 -*-
"""周期任务的上次运行时间，持久化在数据库里。

为什么需要：三个定时任务原先只靠进程内的 threading.Event 计时——启动等一个
初始延迟，然后每隔 interval 跑一次。这意味着**每重启一次就会重新跑一轮**，
而 Codex Token 刷新这种按天调度的任务，重启频繁时等于反复执行。

把"上次跑完的时间"存下来之后，重启只是接着上次的节奏走：距离下次到期还有多久
就等多久，当天已经跑过就不会再跑。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from core import postgres_store

logger = logging.getLogger(__name__)

_COLLECTION = "scheduler_state"
_LOCK = threading.RLock()


def _load() -> dict:
    try:
        found, payload = postgres_store.load_collection(_COLLECTION)
        return payload if found and isinstance(payload, dict) else {}
    except Exception:
        # 读不到就当成"从没跑过"：宁可多跑一轮，也不要因为状态读取失败而漏跑。
        logger.exception("[Scheduler] 读取调度状态失败，按未运行处理")
        return {}


def last_run_at(task: str) -> datetime | None:
    raw = str((_load().get(str(task)) or {}).get("last_run_at") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def mark_ran(task: str) -> None:
    with _LOCK:
        state = _load()
        entry = dict(state.get(str(task)) or {})
        entry["last_run_at"] = datetime.now().isoformat(timespec="seconds")
        entry["run_count"] = int(entry.get("run_count") or 0) + 1
        state[str(task)] = entry
        try:
            postgres_store.save_collection(_COLLECTION, state)
        except Exception:
            # 记不上不影响本轮已经跑完的工作，最坏结果是下次重启多跑一轮。
            logger.exception("[Scheduler] 写入调度状态失败：%s", task)


def seconds_until_due(task: str, interval_seconds: float) -> float:
    """距离下次应当运行还有多少秒；已到期返回 0。"""
    interval = max(0.0, float(interval_seconds))
    previous = last_run_at(task)
    if previous is None:
        return 0.0
    elapsed = (datetime.now() - previous).total_seconds()
    if elapsed < 0:
        # 系统时间被往前调过，当成到期，避免永远等下去。
        return 0.0
    return max(0.0, interval - elapsed)


def describe(task: str, interval_seconds: float) -> dict:
    """给 UI 用的状态快照。"""
    previous = last_run_at(task)
    remaining = seconds_until_due(task, interval_seconds)
    return {
        "task": str(task),
        "last_run_at": previous.isoformat(timespec="seconds") if previous else None,
        "next_run_at": (datetime.now() + timedelta(seconds=remaining)).isoformat(timespec="seconds"),
        "seconds_until_due": int(remaining),
        "interval_seconds": int(interval_seconds),
    }


def reset(task: str) -> None:
    """清掉某个任务的记录，让它下一轮立刻执行。"""
    with _LOCK:
        state = _load()
        if str(task) in state:
            del state[str(task)]
            postgres_store.save_collection(_COLLECTION, state)


# 分段等待的上限：配置改了之后最多这么久生效，不必重启服务。
_POLL_CAP_SECONDS = 60.0


def run_periodic(
    *,
    task: str,
    label: str,
    work,
    enabled,
    interval_seconds,
    initial_delay_seconds: float = 60.0,
    stop: threading.Event | None = None,
) -> None:
    """重启安全的周期调度循环。

    `enabled` 和 `interval_seconds` 传的是可调用对象而不是值：配置在 WebUI 改过
    之后走的是 config.reload_all()，取值必须在每一轮重新读，否则要重启才生效。

    与原实现的区别：
      - 上次运行时间存在数据库里，重启后按剩余时间接续，不会一重启就重跑一轮
      - 分段等待，最长 60s 一段，改了开关或间隔无需重启
    """
    ticker = stop or threading.Event()
    if ticker.wait(max(0.0, float(initial_delay_seconds))):
        return
    while True:
        try:
            if not enabled():
                if ticker.wait(_POLL_CAP_SECONDS):
                    return
                continue
            remaining = seconds_until_due(task, interval_seconds())
            if remaining > 0:
                if ticker.wait(min(remaining, _POLL_CAP_SECONDS)):
                    return
                continue
            try:
                result = work()
                logger.info("[%s] scheduled run: %s", label, result)
            except Exception:
                logger.exception("[%s] scheduled cycle failed", label)
            # 失败也记一次：否则一直失败会变成每 60 秒重试一轮，把外部服务打爆。
            mark_ran(task)
        except Exception:
            logger.exception("[%s] scheduler loop error", label)
            if ticker.wait(_POLL_CAP_SECONDS):
                return
