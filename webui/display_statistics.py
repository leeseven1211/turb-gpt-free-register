"""仅供展示的短期统计缓存；不参与任务领取或业务资格判定。"""
from __future__ import annotations

import threading
import time
from copy import deepcopy
from datetime import datetime, timezone


class DisplayStatisticsCache:
    """同一应用合并重复统计，查询期间不额外占用数据库连接。"""

    def __init__(self, *, ttl: float = 15):
        self._ttl = max(0, ttl)
        self._lock = threading.RLock()
        self._entries: dict[str, tuple[float, float | None, dict]] = {}
        self._loading: dict[str, threading.Event] = {}
        self._generation = 0

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
            self._entries.clear()

    def get(self, key: str, loader) -> dict:
        while True:
            with self._lock:
                cached = self._entries.get(key)
                if cached is not None:
                    deadline, expiry, value = cached
                    if time.monotonic() < deadline and (expiry is None or time.time() < expiry):
                        return deepcopy(value)
                self._entries.pop(key, None)
                pending = self._loading.get(key)
                if pending is None:
                    pending = self._loading[key] = threading.Event()
                    generation = self._generation
                    break
            pending.wait()
        try:
            value = dict(loader())
            value["statistics_updated_at"] = datetime.now(timezone.utc).isoformat()
            value["statistics_max_age_seconds"] = self._ttl
            expiry = value.get("next_expiry_epoch")
            if expiry is not None:
                expiry = float(expiry)
            with self._lock:
                if generation == self._generation:
                    self._entries[key] = (time.monotonic() + self._ttl, expiry, deepcopy(value))
            return value
        finally:
            with self._lock:
                self._loading.pop(key, None)
                pending.set()
