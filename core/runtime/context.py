"""Explicit process role and shared admission reasons; no application imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
import threading


class RuntimeMode(str, Enum):
    COMBINED = "combined"
    WEB = "web"
    WORKER = "worker"


class AdmissionGate:
    """Reasons are independent: one subsystem cannot reopen another's block."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reasons = {"startup"}

    def block(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("admission_reason_required")
        with self._lock:
            self._reasons.add(reason)

    def unblock(self, reason: str) -> None:
        with self._lock:
            self._reasons.discard(reason)

    def is_open(self) -> bool:
        with self._lock:
            return not self._reasons

    def reasons(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._reasons))


@dataclass(frozen=True)
class RuntimeContext:
    mode: RuntimeMode | str
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("core.runtime"))
    admission: AdmissionGate = field(default_factory=AdmissionGate)

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "mode", RuntimeMode(self.mode))
        except (ValueError, TypeError) as exc:
            raise ValueError("runtime_mode_invalid") from exc

    @property
    def executes(self) -> bool:
        return self.mode in (RuntimeMode.COMBINED, RuntimeMode.WORKER)
