"""Versioned, immutable requests for local terminal/defer persistence.

Neither a storage callback nor connection credentials are serialized by this
protocol.  The captured domain is deliberately a separate, non-public value.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any
import uuid


@dataclass(frozen=True)
class SettlementDomain:
    database_url: str = field(repr=False)
    operation_schema: str
    permit_schema: str
    domain_id: str


@dataclass(frozen=True)
class SettlementIntent:
    transition_id: str
    kind: str
    origin: Mapping = field(repr=False)
    payload: Mapping = field(repr=False)
    obligations: tuple = field(repr=False)
    request_digest: str
    version: int = 1

    def __post_init__(self):
        if self.kind not in {"terminal", "defer"} or self.version != 1:
            raise ValueError("unsupported settlement protocol")
        if not isinstance(self.transition_id, str) or not self.transition_id:
            raise ValueError("settlement transition identity is required")
        if not isinstance(self.origin, Mapping) or not isinstance(self.payload, Mapping):
            raise TypeError("settlement origin and payload must be mappings")
        origin = _freeze(self.origin)
        payload = _freeze(self.payload)
        obligations = _freeze(self.obligations)
        if not isinstance(obligations, tuple) or any(not isinstance(item, Mapping) for item in obligations):
            raise TypeError("settlement obligations must be typed mappings")
        digest = _digest({"version": self.version, "kind": self.kind,
                          "origin": origin, "payload": payload, "obligations": obligations})
        if self.request_digest and self.request_digest != digest:
            raise ValueError("settlement request digest mismatch")
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "obligations", obligations)
        object.__setattr__(self, "request_digest", digest)


def _freeze(value: Any, ancestors: frozenset[int] = frozenset()) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("settlement JSON requires finite numbers")
        return value
    if isinstance(value, (Mapping, list, tuple)):
        if id(value) in ancestors:
            raise ValueError("settlement JSON cannot contain cycles")
        ancestors = ancestors | {id(value)}
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise TypeError("settlement JSON keys must be strings")
            return MappingProxyType({key: _freeze(item, ancestors) for key, item in value.items()})
        return tuple(_freeze(item, ancestors) for item in value)
    raise TypeError("settlement value is not JSON-compatible")


def _digest(value: Any) -> str:
    canonical = json.dumps(thaw(value), sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seal_intent(*, kind, origin, payload, obligations=(), transition_id=None):
    return SettlementIntent(transition_id or str(uuid.uuid4()), kind, origin, payload, tuple(obligations), "")


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(item) for item in value]
    return value


def same_intent(left, right):
    return (isinstance(left, SettlementIntent) and isinstance(right, SettlementIntent)
            and left.version == right.version and left.transition_id == right.transition_id
            and left.kind == right.kind and left.request_digest == right.request_digest)


class OperationSettlementPending(RuntimeError):
    code = "operation_settlement_pending"


class OperationSettlementConflict(RuntimeError):
    code = "operation_settlement_conflict"


class OperationSettlementFenced(PermissionError):
    code = "operation_settlement_fenced"


def classify_failure(exc):
    """Return stable transport/SQLSTATE facts, never exception text."""
    state = getattr(exc, "sqlstate", None)
    if state == "42501":
        return "settlement_storage_permission_denied", True
    if isinstance(state, str) and state.startswith("28"):
        return "settlement_storage_authentication_failed", True
    if isinstance(state, str) and state:
        if state.startswith("08") or state in {
            "40001", "40P01", "55P03", "57014", "57P01", "57P02", "57P03",
        }:
            return "settlement_storage_unavailable", False
        return "settlement_storage_sqlstate_unknown", True
    return "settlement_storage_unavailable", False


def classify_cleanup_failure(exc):
    if isinstance(exc, (OperationSettlementConflict, OperationSettlementFenced)):
        return exc.code, True
    if isinstance(exc, (ValueError, RuntimeError)) and not getattr(exc, "sqlstate", None):
        # Missing physical proof/actor handoff is ordinary waiting. Do not
        # interpret arbitrary error text as authority to release or block.
        return "settlement_cleanup_waiting", False
    return classify_failure(exc)
