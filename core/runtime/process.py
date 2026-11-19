"""Explicitly installed process runtime; no ownerless compatibility fallback."""
from __future__ import annotations

import logging
import threading

from .composition import RuntimeController, RuntimeStartError
from .context import RuntimeContext

_LOCK = threading.RLock()
_RUNTIME: RuntimeController | None = None
_LIFECYCLE = None


def install_runtime(runtime: RuntimeController) -> None:
    global _RUNTIME
    with _LOCK:
        if _RUNTIME is not None and _RUNTIME is not runtime:
            raise RuntimeStartError("runtime_already_configured")
        _RUNTIME = runtime


def _configured() -> RuntimeController:
    with _LOCK:
        if _RUNTIME is None:
            raise RuntimeStartError("runtime_not_configured")
        return _RUNTIME


def install_lifecycle(lifecycle) -> None:
    global _LIFECYCLE
    with _LOCK:
        if _RUNTIME is None:
            raise RuntimeStartError("runtime_not_configured")
        if _LIFECYCLE is not None and _LIFECYCLE is not lifecycle:
            raise RuntimeStartError("runtime_lifecycle_already_configured")
        _LIFECYCLE = lifecycle


def _lifecycle():
    with _LOCK:
        selected = _LIFECYCLE
    return selected if selected is not None else _configured()


def start_runtime(runtime_logger: logging.Logger | None = None) -> bool:
    return _lifecycle().start()


def stop_runtime(timeout: float = 60.0) -> bool:
    return _lifecycle().stop(timeout=timeout)


def runtime_status() -> dict:
    return _lifecycle().status()


def get_runtime_context() -> RuntimeContext | None:
    """None identifies an explicitly unconfigured standalone caller.

    Legacy CLI policy belongs to its caller. An absent context never silently
    grants ownership to a managed execution process.
    """
    with _LOCK:
        return _RUNTIME.context if _RUNTIME is not None else None


def execution_admitted() -> bool:
    with _LOCK:
        runtime = _RUNTIME
    return runtime is not None and runtime.execution_admitted()


def execution_owner_valid() -> bool:
    """Owner fence for existing work settlement, independent of admission."""
    with _LOCK:
        runtime = _RUNTIME
    return runtime is not None and runtime.execution_owner_valid()


def execution_owner_lost() -> bool:
    """Treat an absent runtime as terminal, but allow a bounded probe pause."""
    with _LOCK:
        runtime = _RUNTIME
    return runtime is None or runtime.execution_owner_lost()
