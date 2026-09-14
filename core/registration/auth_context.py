"""Execution and compatibility context for shared browser authentication.

The authentication capabilities are used by registration, OAuth recovery, and
live checks.  This module owns the small amount of per-call state those flows
may inject: cooperative cancellation, a monotonic deadline, and legacy
monkeypatch overrides.  It intentionally knows nothing about an application
service or a concrete browser driver.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import time
from types import FunctionType
from typing import Any, Callable, Iterator, Mapping

from .state_machine import Cancellation, CancellationRequested, StageBudget, StageTimeout


CancellationProbe = Cancellation | Callable[[], bool] | None


@dataclass(frozen=True)
class AuthExecutionContext:
    """Optional per-call cancellation/deadline contract.

    ``cancellation`` may be a :class:`Cancellation` value or a zero-argument
    probe supplied by an application service.  ``budget`` and ``deadline``
    are combined conservatively: a child capability may use less time, never
    more.  No application service is imported here.
    """

    cancellation: CancellationProbe = None
    budget: StageBudget | None = None
    deadline: float | None = None
    cancellation_error: Callable[[], BaseException] | None = None
    challenge_detector: Callable[[Any], bool] | None = None
    challenge_submitter: Callable[[Any, str, str], Any] | None = None
    challenge_resolver: Callable[..., Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def requested(self) -> bool:
        probe = self.cancellation
        if isinstance(probe, Cancellation):
            return probe.requested()
        return bool(probe and probe())

    def checkpoint(self) -> None:
        """Raise at a cooperative checkpoint when cancellation/deadline fired."""
        if isinstance(self.cancellation, Cancellation):
            self.cancellation.checkpoint()
        elif self.requested():
            if self.cancellation_error is not None:
                raise self.cancellation_error()
            raise CancellationRequested("用户手动停止认证任务")
        if self.budget is not None:
            self.budget.require()
        if self.deadline is not None and time.monotonic() >= float(self.deadline):
            raise StageTimeout("认证执行 context deadline exhausted")

    def remaining(self, default: float | None = None) -> float | None:
        """Return the smallest available timeout, if one is configured."""
        values: list[float] = []
        if self.budget is not None:
            values.append(max(0.0, float(self.budget.remaining())))
        if self.deadline is not None:
            values.append(max(0.0, float(self.deadline) - time.monotonic()))
        if not values:
            return default
        remaining = min(values)
        if default is None:
            return remaining
        return min(float(default), remaining)


_CURRENT_CONTEXT: ContextVar[AuthExecutionContext | None] = ContextVar(
    "shared_auth_execution_context",
    default=None,
)
_COMPAT_OVERRIDES: ContextVar[dict[str, object] | None] = ContextVar(
    "shared_auth_capability_overrides",
    default=None,
)


class _TimeProxy:
    """Expose clock calls while honoring a legacy per-call ``time`` patch."""

    def __getattr__(self, name: str) -> Any:
        override = current_override("time")
        source = override if override is not None else time
        return getattr(source, name)


time_proxy = _TimeProxy()


def current_execution_context() -> AuthExecutionContext | None:
    """Return the context local to the current task/thread, if any."""
    return _CURRENT_CONTEXT.get()


@contextmanager
def execution_context(context: AuthExecutionContext | None) -> Iterator[AuthExecutionContext | None]:
    """Install one authentication context for the duration of a capability."""
    if context is None:
        yield _CURRENT_CONTEXT.get()
        return
    marker = _CURRENT_CONTEXT.set(context)
    try:
        context.checkpoint()
        yield context
    finally:
        _CURRENT_CONTEXT.reset(marker)


def checkpoint(context: AuthExecutionContext | None = None) -> None:
    """Observe the explicit or current cancellation/deadline context."""
    active = context or _CURRENT_CONTEXT.get()
    if active is not None:
        active.checkpoint()


def remaining_timeout(default: float | None = None, context: AuthExecutionContext | None = None) -> float | None:
    """Return a context-bounded timeout without importing an application service."""
    active = context or _CURRENT_CONTEXT.get()
    return active.remaining(default) if active is not None else default


@contextmanager
def compatibility_overrides(overrides: Mapping[str, object] | None) -> Iterator[None]:
    """Install legacy dependency overrides in the current context only."""
    clean = {
        str(name): value
        for name, value in (overrides or {}).items()
        if value is not None
    }
    marker = _COMPAT_OVERRIDES.set(clean)
    try:
        yield
    finally:
        _COMPAT_OVERRIDES.reset(marker)


def current_override(name: str) -> object | None:
    """Return a per-call compatibility override, never a shared mutable value."""
    return (_COMPAT_OVERRIDES.get() or {}).get(str(name))


def make_dispatch(name: str, implementation: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap one implementation with context-local legacy monkeypatch support."""
    from functools import wraps

    @wraps(implementation)
    def dispatch(*args: Any, **kwargs: Any) -> Any:
        override = current_override(name)
        if override is not None:
            return override(*args, **kwargs)
        return implementation(*args, **kwargs)

    dispatch.__shared_capability__ = True
    dispatch.__shared_implementation__ = implementation
    dispatch.__capability_name__ = name
    return dispatch


def install_dispatches(namespace: dict[str, Any], names: tuple[str, ...] | list[str]) -> None:
    """Install dispatch wrappers once at module import, not by per-call rebinding."""
    for name in names:
        implementation = namespace.get(name)
        if isinstance(implementation, FunctionType) and not getattr(implementation, "__shared_capability__", False):
            namespace[name] = make_dispatch(name, implementation)


__all__ = [
    "AuthExecutionContext",
    "Cancellation",
    "CancellationRequested",
    "StageBudget",
    "StageTimeout",
    "checkpoint",
    "remaining_timeout",
    "current_execution_context",
    "execution_context",
    "compatibility_overrides",
    "current_override",
    "make_dispatch",
    "install_dispatches",
    "time_proxy",
]
