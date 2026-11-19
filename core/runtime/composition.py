"""Injected runtime lifecycle. Does not import domain modules, Flask or storage."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import threading
import time
from typing import Any, Protocol

from .context import RuntimeContext
from .instance_owner import OwnerError
from .manifest import COMPONENTS


class ExecutionOwner(Protocol):
    def start(self) -> Any: ...
    def require_owner(self) -> None: ...
    def close(self, timeout: float = 2.0) -> bool: ...


@dataclass(frozen=True)
class ComponentHooks:
    start: Callable[[RuntimeContext], Any]
    stop: Callable[[RuntimeContext, float], bool] | None = None


class RuntimeStartError(RuntimeError):
    """Stable public reason, without a connection string or domain exception."""


class RuntimeController:
    def __init__(
        self,
        context: RuntimeContext,
        components: Mapping[str, ComponentHooks],
        *,
        owner: ExecutionOwner | None = None,
    ) -> None:
        self.context = context
        self.components = dict(components)
        self.owner = owner
        self._lock = threading.RLock()
        self._state = "new"
        self._owner_acquired = False
        self._owner_cleanup_required = False
        self._remaining: list[str] = []
        self._component_states: dict[str, dict[str, Any]] = {}
        self._failure_code: str | None = None

    def start(self) -> bool:
        with self._lock:
            if self._state == "started":
                return False
            if self._state != "new":
                raise RuntimeStartError("runtime_restart_requires_new_context")
            if not self.context.executes:
                self.context.admission.block("web")
                self.context.admission.unblock("startup")
                self._state = "started"
                return True
            if self.owner is None:
                self._fail_before_start("owner_required")
            if any(spec.name not in self.components for spec in COMPONENTS):
                self._fail_before_start("component_binding_missing")

            self._state = "starting"
            try:
                # A failed start may retain a monitor/file fence. Keep its
                # handle until close explicitly confirms cleanup as well.
                self._owner_cleanup_required = True
                self.owner.start()
                self._owner_acquired = True
                self.owner.require_owner()
                for spec in COMPONENTS:
                    self.owner.require_owner()
                    hooks = self.components[spec.name]
                    state = {"state": "starting", "error_type": None}
                    self._component_states[spec.name] = state
                    # A start callback may allocate a thread before raising.
                    if spec.kind == "service":
                        self._remaining.append(spec.name)
                    try:
                        hooks.start(self.context)
                    except Exception as exc:
                        state.update(state="start_failed", error_type=type(exc).__name__)
                        if spec.required:
                            raise RuntimeStartError("component_start_failed") from exc
                    else:
                        state["state"] = "started"
                self.owner.require_owner()
                self.context.admission.unblock("startup")
                self._state = "started"
                return True
            except BaseException as exc:
                self.context.admission.block("startup_failed")
                self._failure_code = (
                    str(exc) if isinstance(exc, RuntimeStartError) else "runtime_start_failed"
                )
                # This is rollback of startup allocations, not the T7 task drain.
                if self._owner_cleanup_required:
                    self.stop(timeout=3.0)
                self._state = "start_failed"
                if isinstance(exc, RuntimeStartError) or not isinstance(exc, Exception):
                    raise
                raise RuntimeStartError(self._failure_code) from exc

    def _fail_before_start(self, reason: str) -> None:
        self._state = "start_failed"
        self._failure_code = reason
        self.context.admission.block("startup_failed")
        raise RuntimeStartError(reason)

    def stop_selected(self, names: Sequence[str], timeout: float = 3.0) -> bool:
        """Stop one drain phase while retaining execution ownership."""
        with self._lock:
            selected = list(names)
            if len(selected) != len(set(selected)) or any(name not in self.components for name in selected):
                raise ValueError("stop_components_invalid")
            self.context.admission.block("draining")
            self._state = "stopping"
            deadline = time.monotonic() + max(0.0, float(timeout))
            for name in selected:
                if name not in self._remaining:
                    continue
                if name == "settlement" and any(other != name for other in self._remaining):
                    # Startup rollback can reach this carrier after another
                    # service failed to join. That service may still produce
                    # cleanup, so keep settlement alive until every producer
                    # is physically stopped, just as the managed drain does.
                    self._component_states[name]["state"] = "stop_deferred"
                    continue
                stop = self.components[name].stop
                if stop is None:
                    self._component_states[name]["state"] = "stop_unsupported"
                    continue
                try:
                    stopped = stop(self.context, max(0.0, deadline - time.monotonic())) is True
                except Exception as exc:
                    stopped = False
                    self._component_states[name]["error_type"] = type(exc).__name__
                self._component_states[name]["state"] = "stopped" if stopped else "stop_incomplete"
                if stopped:
                    self._remaining.remove(name)
            complete = not any(name in self._remaining for name in selected)
            if not complete:
                self._state = "stop_incomplete"
            return complete

    def close_owner(self, timeout: float = 3.0) -> bool:
        """Release the process fence only after all owned services stopped."""
        with self._lock:
            if self._remaining:
                self._state = "stop_incomplete"
                return False
            if self._owner_cleanup_required:
                try:
                    closed = self.owner.close(timeout=max(0.0, float(timeout))) is True
                except Exception:
                    closed = False
                if not closed:
                    self._state = "stop_incomplete"
                    return False
                self._owner_acquired = False
                self._owner_cleanup_required = False
            self._state = "stopped"
            return True

    def stop(self, timeout: float = 3.0, *, order: Sequence[str] | None = None,
             release_owner: bool = True) -> bool:
        """Truthful bounded teardown; T7 may retain owner until heartbeat stops."""
        with self._lock:
            names = list(reversed(self._remaining)) if order is None else list(order)
            if len(names) != len(set(names)) or set(names) != set(self._remaining):
                raise ValueError("stop_order_incomplete")
            deadline = time.monotonic() + max(0.0, float(timeout))
            if not self.stop_selected(names, max(0.0, deadline - time.monotonic())):
                return False
            if not release_owner:
                self._state = "components_stopped"
                return True
            return self.close_owner(max(0.0, deadline - time.monotonic()))

    def status(self) -> dict[str, Any]:
        """Lifecycle facts only. T7 adds liveness and mode-aware readiness."""
        with self._lock:
            return {
                "mode": self.context.mode.value,
                "state": self._state,
                "startup_complete": self._state == "started",
                "admission_open": self.context.admission.is_open(),
                "admission_reasons": list(self.context.admission.reasons()),
                "owner_acquired": self._owner_acquired,
                "owner_cleanup_required": self._owner_cleanup_required,
                "failure_code": self._failure_code,
                "components": {key: dict(value) for key, value in self._component_states.items()},
                "remaining_components": list(self._remaining),
            }

    def _execution_owner_state(self) -> str:
        if not self.context.executes or not self._owner_acquired or self.owner is None:
            return "lost"
        try:
            self.owner.require_owner()
        except Exception as exc:
            if isinstance(exc, OwnerError) and exc.code == "owner_probe_paused":
                return "paused"
            self.context.admission.block("owner_lost")
            return "lost"
        return "held" if self._owner_acquired else "lost"

    def execution_owner_valid(self) -> bool:
        """Allow fenced settlement during drain without admitting new work."""
        return self._execution_owner_state() == "held"

    def execution_owner_lost(self) -> bool:
        """Only a terminal failure tells the Worker entrypoint to exit."""
        return self._execution_owner_state() == "lost"

    def execution_admitted(self) -> bool:
        """Fast admission hint; task/permit CAS remains authoritative."""
        if self._state != "started" or not self.context.admission.is_open():
            return False
        return (
            self.execution_owner_valid()
            and self._state == "started"
            and self.context.admission.is_open()
        )
