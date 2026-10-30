"""异步任务中心投影的隔离契约和纯逻辑队列。

本模块只处理“哪个 batch 需要重算”和“重算何时完成”，不读取或解释注册事件。
正式接入前，B/D 适配层只需要把已经存在的 batch 关联转换为 ``enqueue`` 调用，
并提供一个只更新单个 batch 的 ``refresh_batch`` 实现。
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock, RLock
from typing import Any, Iterator, Protocol


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _batch_key(batch_id: object) -> str:
    value = str(batch_id or "").strip()
    if not value:
        raise ValueError("batch_id 不能为空")
    return value


def _lag_ms(started_at: datetime | None, ended_at: datetime | None, now: datetime) -> int | None:
    if started_at is None:
        return None
    end = ended_at or now
    return max(0, int((end - started_at).total_seconds() * 1000))


class BatchProjector(Protocol):
    """主投影接入点：只能刷新一个明确的 batch。"""

    def refresh_batch(self, batch_id: str) -> Any:
        """重算指定批次；不得扫描或更新其他批次。"""


@dataclass(frozen=True)
class ProjectionRequest:
    """队列请求，不复制事件 payload，也不定义事件 schema。"""

    batch_id: str
    reason: str = "event"
    requested_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "batch_id", _batch_key(self.batch_id))
        object.__setattr__(self, "reason", str(self.reason or "event")[:120])
        object.__setattr__(self, "requested_at", _as_utc(self.requested_at))


@dataclass(frozen=True)
class ProjectionLag:
    """可直接作为 API/UI 的投影延迟元数据。"""

    batch_id: str
    status: str
    attempts: int
    requested_at: datetime | None
    projected_at: datetime | None
    next_retry_at: datetime | None
    lag_ms: int | None
    delayed: bool
    last_error: str | None = None

    def as_dict(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or _now()
        lag = (
            _lag_ms(self.requested_at, None, current)
            if self.requested_at is not None and self.status != "succeeded"
            else self.lag_ms
        )
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "attempts": self.attempts,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "projected_at": self.projected_at.isoformat() if self.projected_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "lag_ms": lag,
            "delayed": bool(self.delayed or (lag is not None and lag > 0 and self.status != "succeeded")),
            "last_error": self.last_error,
        }


@dataclass
class _Entry:
    request: ProjectionRequest
    status: str = "queued"
    attempts: int = 0
    started_at: datetime | None = None
    projected_at: datetime | None = None
    next_retry_at: datetime | None = None
    last_error: str | None = None
    dirty: bool = False


class ProjectionQueue:
    """线程安全、按 batch 合并的投影队列。

    队列状态只在内存中保存，适合作为字段契约和 worker 行为的隔离测试替身。
    正式实现可将同样的状态持久化到数据库，但必须保留这里的语义：
    同一 batch 同时只有一个 writer，重复请求合并，失败留下可重试状态。
    """

    def __init__(self, *, retry_delay_seconds: float = 1.0) -> None:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds 不能为负数")
        self.retry_delay = timedelta(seconds=float(retry_delay_seconds))
        self._lock = RLock()
        self._entries: dict[str, _Entry] = {}
        self._batch_locks: dict[str, Lock] = {}

    def enqueue(
        self,
        batch_id: object,
        *,
        reason: str = "event",
        requested_at: datetime | None = None,
    ) -> ProjectionLag:
        request = ProjectionRequest(
            batch_id=_batch_key(batch_id),
            reason=reason,
            requested_at=requested_at or _now(),
        )
        with self._lock:
            entry = self._entries.get(request.batch_id)
            if entry is None:
                entry = _Entry(request=request)
                self._entries[request.batch_id] = entry
            elif entry.status == "running":
                # 当前 writer 收口后必须再跑一次，避免并发事件丢失。
                entry.dirty = True
                entry.request = request
            else:
                # queued/failed/succeeded 的重复请求都只保留一个待处理项。
                entry.request = request
                entry.status = "queued"
                entry.next_retry_at = None
                entry.last_error = None
            return self._snapshot_locked(request.batch_id, now=request.requested_at)

    def pending(self, *, now: datetime | None = None) -> tuple[str, ...]:
        current = now or _now()
        with self._lock:
            return tuple(
                batch_id
                for batch_id, entry in sorted(self._entries.items())
                if entry.status == "queued"
                or (entry.status == "failed" and (entry.next_retry_at is None or entry.next_retry_at <= current))
            )

    def snapshot(self, batch_id: object, *, now: datetime | None = None) -> ProjectionLag:
        key = _batch_key(batch_id)
        with self._lock:
            return self._snapshot_locked(key, now=now or _now())

    def _snapshot_locked(self, batch_id: str, *, now: datetime | None = None) -> ProjectionLag:
        current = now or _now()
        current = _as_utc(current)
        entry = self._entries.get(batch_id)
        if entry is None:
            return ProjectionLag(
                batch_id=batch_id,
                status="idle",
                attempts=0,
                requested_at=None,
                projected_at=None,
                next_retry_at=None,
                lag_ms=None,
                delayed=False,
            )
        projected_at = entry.projected_at
        delayed = entry.status != "succeeded"
        return ProjectionLag(
            batch_id=batch_id,
            status=entry.status,
            attempts=entry.attempts,
            requested_at=entry.request.requested_at,
            projected_at=projected_at,
            next_retry_at=entry.next_retry_at,
            lag_ms=_lag_ms(entry.request.requested_at, projected_at, current),
            delayed=delayed,
            last_error=entry.last_error,
        )

    @contextmanager
    def batch_writer(self, batch_id: object) -> Iterator[None]:
        """按规范化 batch_id 提供单批次 writer 锁。"""
        key = _batch_key(batch_id)
        with self._lock:
            lock = self._batch_locks.setdefault(key, Lock())
        with lock:
            yield

    @contextmanager
    def acquire_batches(self, batch_ids: list[object] | tuple[object, ...]) -> Iterator[tuple[str, ...]]:
        """按稳定字典序取得多个批次锁，避免交叉顺序造成死锁。"""
        keys = tuple(sorted({_batch_key(value) for value in batch_ids}))
        locks: list[Lock] = []
        with self._lock:
            locks = [self._batch_locks.setdefault(key, Lock()) for key in keys]
        for lock in locks:
            lock.acquire()
        try:
            yield keys
        finally:
            for lock in reversed(locks):
                lock.release()

    def run_once(
        self,
        projector: BatchProjector,
        *,
        now: datetime | None = None,
    ) -> ProjectionLag | None:
        """消费一个 due 请求；异常只影响该 batch，并留下失败重试状态。"""
        current = now or _now()
        with self._lock:
            due = [
                (batch_id, entry)
                for batch_id, entry in self._entries.items()
                if entry.status == "queued"
                or (entry.status == "failed" and (entry.next_retry_at is None or entry.next_retry_at <= current))
            ]
            if not due:
                return None
            batch_id, entry = min(due, key=lambda pair: (pair[0], pair[1].request.requested_at))
            entry.status = "running"
            entry.attempts += 1
            entry.started_at = current
            entry.next_retry_at = None
            entry.last_error = None

        try:
            with self.batch_writer(batch_id):
                projector.refresh_batch(batch_id)
        except Exception as exc:
            with self._lock:
                entry = self._entries[batch_id]
                entry.status = "failed"
                entry.next_retry_at = current + self.retry_delay
                entry.last_error = f"{type(exc).__name__}: {str(exc)[:500]}"
                return self._snapshot_locked(batch_id, now=current)

        with self._lock:
            entry = self._entries[batch_id]
            entry.projected_at = _now()
            if entry.dirty:
                entry.status = "queued"
                entry.dirty = False
            else:
                entry.status = "succeeded"
            return self._snapshot_locked(batch_id, now=entry.projected_at)

    def drain(
        self,
        projector: BatchProjector,
        *,
        max_items: int = 100,
        now: datetime | None = None,
    ) -> list[ProjectionLag]:
        results: list[ProjectionLag] = []
        for _ in range(max(0, int(max_items))):
            result = self.run_once(projector, now=now)
            if result is None:
                break
            results.append(result)
        return results


__all__ = ["BatchProjector", "ProjectionLag", "ProjectionQueue", "ProjectionRequest"]
