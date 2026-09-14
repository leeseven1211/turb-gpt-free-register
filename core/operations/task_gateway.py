"""账号任务统一提交、事件和持久调度边界。

兼容期仍由 ``legacy_task_store`` 写入旧账号任务；本模块负责把任务和
依赖交给 PostgreSQL 的统一运行时。进程内线程只负责轮询和提交，真正的
claim 以及父子推进都由存储层的原子状态转换决定。
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any


logger = logging.getLogger(__name__)

# A dependency has exactly one claim owner: the persistent scanner below. The
# installed callback only submits the already-claimed row to the shared
# account-operation budget; it must not claim the row again.
_DEPENDENCY_HANDLER: Callable[[dict], Any] | None = None
_DEPENDENCY_HANDLER_LOCK = threading.RLock()
_DEPENDENCY_WAKE = threading.Event()
_DEPENDENCY_STOP = threading.Event()
_DEPENDENCY_THREAD: threading.Thread | None = None
_DEPENDENCY_LOCK = threading.RLock()
_DEPENDENCY_INTERVAL_SECONDS = 0.5
_DEPENDENCY_BATCH_SIZE = 32

# Native operation dispatch is task-type based rather than Codex-specific.
# A handler is registered at the gateway boundary and receives a run id. The
# gateway scans every native/compatibility operation row that has a registered
# task type, so adding a maintenance handler does not require another raw
# scheduler thread.
_DISPATCH_HANDLERS: dict[str, tuple[Callable[[int], Any], tuple[str, ...] | None]] = {}
_DISPATCH_HANDLER_LOCK = threading.RLock()
_RUN_DISPATCHED: set[int] = set()
_RUN_DISPATCH_LOCK = threading.RLock()
_RUN_DISPATCH_WAKE = threading.Event()
_RUN_DISPATCH_STOP = threading.Event()
_RUN_DISPATCH_THREAD: threading.Thread | None = None
_RUN_DISPATCH_INTERVAL_SECONDS = 0.5
_RUN_DISPATCH_BATCH_SIZE = 32


def _legacy():
    from core.operations import legacy_task_store

    return legacy_task_store


def _operation():
    from core.storage import operation

    return operation


def _executor():
    from core.account_operation_executor import executor

    return executor


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
    result = _legacy().finish_task(task_id, **kwargs)
    if task_id:
        _mark_dependency_ready(
            child_source_system="account_action_tasks",
            child_source_id=str(int(task_id)),
            child_status=str(kwargs.get("status") or "failed"),
            child_result=kwargs.get("result_summary") if isinstance(kwargs.get("result_summary"), dict) else {},
        )
    return result


def recover_interrupted() -> int:
    return _legacy().recover_interrupted()


def list_tasks(**kwargs: Any) -> dict:
    return _legacy().list_tasks(**kwargs)


def get_task(task_id: int) -> dict | None:
    return _legacy().get_task(task_id)


def register_task_dependency(**kwargs: Any) -> dict:
    """Persist a handoff between legacy and native task IDs."""
    return _operation().register_task_dependency(**kwargs)


def _mark_dependency_ready(**kwargs: Any) -> None:
    try:
        ready = _operation().mark_task_dependency_ready(**kwargs)
    except Exception:
        logger.exception(
            "更新账号任务父子依赖失败：child=%s:%s",
            kwargs.get("child_source_system"), kwargs.get("child_source_id"),
        )
        return
    if ready:
        # Wake the one persistent claim owner.  Do not invoke a callback on
        # the child worker stack and do not claim rows in this notification
        # path.
        notify_dependency_ready(ready[0])


def set_dependency_ready_handler(handler: Callable[[dict], Any] | None) -> None:
    """Install the continuation submission hook used by the WebUI runtime."""
    global _DEPENDENCY_HANDLER
    with _DEPENDENCY_HANDLER_LOCK:
        _DEPENDENCY_HANDLER = handler
    _DEPENDENCY_WAKE.set()


def _dependency_handler() -> Callable[[dict], Any] | None:
    with _DEPENDENCY_HANDLER_LOCK:
        return _DEPENDENCY_HANDLER


def _dependency_tick() -> int:
    handler = _dependency_handler()
    if handler is None:
        return 0
    # Do not claim a large ready backlog while the shared account-operation
    # budget is already full. The callback still rechecks the budget because
    # another producer can win the race between this snapshot and submit.
    slots = _executor().available_slots()
    if slots <= 0:
        return 0
    claimed_count = 0
    try:
        candidates = _operation().list_ready_task_dependencies(
            limit=min(_DEPENDENCY_BATCH_SIZE, slots),
            initialize=False,
        )
        for candidate in candidates:
            # This is the only claim site in the process. A second process can
            # race safely because the SQL update is a ready->running CAS.
            claimed = _operation().claim_task_dependency(
                int(candidate.get("id") or 0), initialize=False,
            )
            if not claimed:
                continue
            claimed_count += 1
            try:
                # The callback is a non-blocking executor submission boundary.
                # It must return the row to ready itself when the shared budget
                # is full.
                handler(dict(claimed))
            except Exception as exc:
                logger.exception(
                    "提交父任务依赖续接失败：dependency_id=%s", claimed.get("id"),
                )
                try:
                    _operation().complete_task_dependency(
                        int(claimed["id"]),
                        success=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    notify_dependency_ready(claimed)
                except Exception:
                    logger.exception(
                        "父任务依赖失败状态写回失败：dependency_id=%s", claimed.get("id"),
                    )
    except Exception:
        logger.exception("持久父任务依赖 dispatcher 轮询失败")
    return claimed_count


def _dependency_loop() -> None:
    while not _DEPENDENCY_STOP.is_set():
        claimed = _dependency_tick()
        if claimed:
            # Drain only a finite batch per pass. This prevents a large ready
            # backlog from starving the rest of the process.
            continue
        _DEPENDENCY_WAKE.wait(_DEPENDENCY_INTERVAL_SECONDS)
        _DEPENDENCY_WAKE.clear()


def start_dependency_dispatcher(
    *, interval_seconds: float = 0.5, batch_size: int = 32,
) -> bool:
    """Start one persistent ready-queue scanner for completion handoffs."""
    global _DEPENDENCY_THREAD, _DEPENDENCY_INTERVAL_SECONDS, _DEPENDENCY_BATCH_SIZE
    with _DEPENDENCY_LOCK:
        _DEPENDENCY_INTERVAL_SECONDS = max(0.05, min(30.0, float(interval_seconds)))
        _DEPENDENCY_BATCH_SIZE = max(1, min(500, int(batch_size)))
        if _DEPENDENCY_THREAD is not None and _DEPENDENCY_THREAD.is_alive():
            _DEPENDENCY_WAKE.set()
            return False
        _DEPENDENCY_STOP.clear()
        try:
            recovered = _operation().recover_stale_task_dependencies()
            if recovered:
                logger.warning("已恢复 %s 个超时的父任务依赖 claim", recovered)
        except Exception:
            logger.exception("恢复父任务依赖 claim 失败；持久 ready 扫描仍会继续")
        _DEPENDENCY_WAKE.set()
        _DEPENDENCY_THREAD = threading.Thread(
            target=_dependency_loop,
            name="operation-dependency-dispatcher",
            daemon=True,
        )
        _DEPENDENCY_THREAD.start()
        return True


def stop_dependency_dispatcher(*, timeout: float = 2.0) -> bool:
    global _DEPENDENCY_THREAD
    with _DEPENDENCY_LOCK:
        thread = _DEPENDENCY_THREAD
        if thread is None:
            return False
        _DEPENDENCY_STOP.set()
        _DEPENDENCY_WAKE.set()
    thread.join(max(0.0, float(timeout)))
    with _DEPENDENCY_LOCK:
        if _DEPENDENCY_THREAD is thread and not thread.is_alive():
            _DEPENDENCY_THREAD = None
    return not thread.is_alive()


def dependency_dispatcher_status() -> dict[str, object]:
    with _DEPENDENCY_LOCK:
        thread = _DEPENDENCY_THREAD
        return {
            "started": thread is not None,
            "alive": bool(thread and thread.is_alive()),
            "name": thread.name if thread is not None else None,
            "claim_owner": "operation-dependency-dispatcher",
        }


def notify_dependency_ready(dependency: dict | None = None) -> None:
    """Wake the persistent scanner for a row already marked ``ready``."""
    _DEPENDENCY_WAKE.set()


def drain_ready_dependencies(*, limit: int = 100, initialized: bool = False) -> int:
    """Wake and count durable ready rows without claiming them.

    Startup and child completion share the same scanner. Keeping this method
    notification-only is important: a startup caller must not claim a row and
    then hand it to a callback that attempts a second ready->running CAS.
    """
    rows = _operation().list_ready_task_dependencies(
        limit=limit, initialize=not initialized,
    )
    _DEPENDENCY_WAKE.set()
    return len(rows)


def register_dispatch_handler(
    task_type: str,
    handler: Callable[[int], Any],
    *,
    source_systems: tuple[str, ...] | list[str] | None = ("native_operations",),
) -> None:
    """Register a durable run handler by task type and source namespace.

    Native handlers default to native rows so a compatibility task that still
    has its old service scheduler cannot be executed a second time. A handler
    that has completed a source migration can explicitly pass ``None`` or its
    allowed source systems.
    """
    name = str(task_type or "").strip()
    if not name:
        raise ValueError("task_type 不能为空")
    if not callable(handler):
        raise TypeError("task handler 必须可调用")
    allowed_sources = None if source_systems is None else tuple(
        str(item).strip() for item in source_systems if str(item).strip()
    )
    with _DISPATCH_HANDLER_LOCK:
        _DISPATCH_HANDLERS[name] = (handler, allowed_sources)
    _RUN_DISPATCH_WAKE.set()


def unregister_dispatch_handler(task_type: str) -> None:
    with _DISPATCH_HANDLER_LOCK:
        _DISPATCH_HANDLERS.pop(str(task_type or "").strip(), None)


def registered_dispatch_types() -> tuple[str, ...]:
    with _DISPATCH_HANDLER_LOCK:
        return tuple(sorted(_DISPATCH_HANDLERS))


def reserve_dispatch(run_id: int) -> bool:
    """Reserve a run for either direct submit or the persistent scanner."""
    with _RUN_DISPATCH_LOCK:
        value = int(run_id)
        if value in _RUN_DISPATCHED:
            return False
        _RUN_DISPATCHED.add(value)
        return True


def release_dispatch(run_id: int) -> None:
    with _RUN_DISPATCH_LOCK:
        _RUN_DISPATCHED.discard(int(run_id))
    _RUN_DISPATCH_WAKE.set()


def _run_handler_snapshot() -> dict[str, tuple[Callable[[int], Any], tuple[str, ...] | None]]:
    with _DISPATCH_HANDLER_LOCK:
        return dict(_DISPATCH_HANDLERS)


def dispatch_registered_once(*, limit: int | None = None) -> int:
    """Submit a finite batch of registered durable runs through the budget."""
    handlers = _run_handler_snapshot()
    if not handlers:
        return 0
    slots = _executor().available_slots()
    if slots <= 0:
        return 0
    source_systems: set[str] = set()
    accepts_all_sources = False
    for _handler, allowed_sources in handlers.values():
        if allowed_sources is None:
            accepts_all_sources = True
            break
        source_systems.update(allowed_sources)
    if not accepts_all_sources and not source_systems:
        return 0
    requested_limit = int(limit or (_RUN_DISPATCH_BATCH_SIZE * 2))
    scan_limit = max(slots, min(5000, requested_limit))
    try:
        runs = _operation().list_dispatchable_runs(
            limit=scan_limit,
            task_types=tuple(handlers),
            source_systems=None if accepts_all_sources else tuple(sorted(source_systems)),
        )
    except (AttributeError, TypeError):
        # Compatibility with an older storage wrapper during a rolling update.
        try:
            runs = _operation().list_queued_runs(limit=scan_limit)
        except AttributeError:
            runs = []
    submitted = 0
    for run in runs:
        if submitted >= slots:
            break
        task_type = str(run.get("task_type") or "")
        entry = handlers.get(task_type)
        if entry is None:
            continue
        handler, allowed_sources = entry
        source_system = str(run.get("source_system") or "")
        if allowed_sources is not None and source_system not in allowed_sources:
            continue
        if not reserve_dispatch(int(run["id"])):
            continue
        try:
            future = _executor().try_submit(handler, int(run["id"]))
        except Exception:
            release_dispatch(int(run["id"]))
            logger.exception("提交 durable operation 失败：run_id=%s", run.get("id"))
            continue
        if future is None:
            release_dispatch(int(run["id"]))
            break
        submitted += 1
        try:
            future.add_done_callback(
                lambda _completed, run_id=int(run["id"]): release_dispatch(run_id)
            )
        except AttributeError:
            release_dispatch(int(run["id"]))
    return submitted


def notify_dispatch() -> None:
    """Wake the durable task dispatcher after a new run is persisted."""
    _RUN_DISPATCH_WAKE.set()


def _run_dispatch_loop() -> None:
    while not _RUN_DISPATCH_STOP.is_set():
        submitted = dispatch_registered_once()
        if submitted:
            continue
        _RUN_DISPATCH_WAKE.wait(_RUN_DISPATCH_INTERVAL_SECONDS)
        _RUN_DISPATCH_WAKE.clear()


def start_dispatcher(*, interval_seconds: float = 0.5, batch_size: int = 32) -> bool:
    """Start the shared task-type dispatcher for durable operation runs."""
    global _RUN_DISPATCH_THREAD, _RUN_DISPATCH_INTERVAL_SECONDS, _RUN_DISPATCH_BATCH_SIZE
    with _RUN_DISPATCH_LOCK:
        _RUN_DISPATCH_INTERVAL_SECONDS = max(0.05, min(30.0, float(interval_seconds)))
        _RUN_DISPATCH_BATCH_SIZE = max(1, min(500, int(batch_size)))
        if _RUN_DISPATCH_THREAD is not None and _RUN_DISPATCH_THREAD.is_alive():
            _RUN_DISPATCH_WAKE.set()
            return False
        _RUN_DISPATCH_STOP.clear()
        _RUN_DISPATCH_WAKE.set()
        _RUN_DISPATCH_THREAD = threading.Thread(
            target=_run_dispatch_loop,
            name="operation-task-dispatcher",
            daemon=True,
        )
        _RUN_DISPATCH_THREAD.start()
        return True


def stop_dispatcher(*, timeout: float = 2.0) -> bool:
    global _RUN_DISPATCH_THREAD
    with _RUN_DISPATCH_LOCK:
        thread = _RUN_DISPATCH_THREAD
        if thread is None:
            return False
        _RUN_DISPATCH_STOP.set()
        _RUN_DISPATCH_WAKE.set()
    thread.join(max(0.0, float(timeout)))
    with _RUN_DISPATCH_LOCK:
        if _RUN_DISPATCH_THREAD is thread and not thread.is_alive():
            _RUN_DISPATCH_THREAD = None
    return not thread.is_alive()


def dispatcher_status() -> dict[str, object]:
    with _RUN_DISPATCH_LOCK:
        thread = _RUN_DISPATCH_THREAD
        return {
            "started": thread is not None,
            "alive": bool(thread and thread.is_alive()),
            "name": thread.name if thread is not None else None,
            "dispatched_runs": len(_RUN_DISPATCHED),
            "registered_task_types": registered_dispatch_types(),
        }


__all__ = [
    "init", "create_batch", "create_task", "start_task", "append_event", "finish_task",
    "recover_interrupted", "list_tasks", "get_task", "register_task_dependency",
    "set_dependency_ready_handler", "notify_dependency_ready", "drain_ready_dependencies",
    "start_dependency_dispatcher", "stop_dependency_dispatcher", "dependency_dispatcher_status",
    "register_dispatch_handler", "unregister_dispatch_handler", "registered_dispatch_types",
    "reserve_dispatch", "release_dispatch", "dispatch_registered_once",
    "notify_dispatch",
    "start_dispatcher", "stop_dispatcher", "dispatcher_status",
]
