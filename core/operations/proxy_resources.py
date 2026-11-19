"""Capture safe original pool-child identities before an operation uses them."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from core.operations.settlement_contracts import OperationSettlementPending


def _identity(value) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("missing exact identity")
    return value


def _timestamp(value) -> str:
    if not isinstance(value, datetime):
        raise ValueError("missing original lease timestamp")
    return value.isoformat()


def capture_proxy_pool_child(route, context, *, actor_scope="external") -> dict | None:
    """Snapshot one delivered handle; this grants no authority to return it.

    Legacy callers without captured admission authority keep their existing
    generic cleanup. Marked pool handles with damaged identities cannot be
    registered as if they were generic resources.
    """
    lease = getattr(route, "lease", None)
    metadata = getattr(lease, "metadata", None)
    if not isinstance(metadata, Mapping) or not any(
        key in metadata for key in ("pool_resource_id", "pool_anchor_id")
    ):
        return None

    domain = getattr(context, "settlement_domain", None)
    execution = getattr(context, "_execution", None)
    ticket = getattr(execution, "settlement_ticket", None)
    if domain is None or not getattr(domain, "domain_id", None) or not isinstance(ticket, Mapping) or not ticket:
        return None
    if any(not ticket.get(key) for key in (
        "ticket_id", "permit_id", "domain_id", "run_uuid", "execution_id", "run_id", "task_id",
    )):
        return None

    try:
        domain_id = _identity(domain.domain_id)
        run_id = int(context.run_id)
        task_id = int(context.task_id)
        execution_id = _identity(context.execution_id)
        run_uuid = _identity(ticket["run_uuid"])
        if actor_scope not in {"owner_process", "external"}:
            raise ValueError("unsupported actor scope")
        if run_id <= 0 or task_id <= 0 or (
            _identity(ticket["domain_id"]) != domain_id
            or int(ticket["run_id"]) != run_id
            or int(ticket["task_id"]) != task_id
            or _identity(ticket["execution_id"]) != execution_id
            or str(getattr(execution, "execution_id", "")) != execution_id
            or str(getattr(execution, "permit_id", "")) != _identity(ticket["permit_id"])
        ):
            raise ValueError("captured origin mismatch")
        run = getattr(context, "run", None)
        if isinstance(run, Mapping) and run.get("run_uuid") and run["run_uuid"] != run_uuid:
            raise ValueError("captured run mismatch")
        return {
            "version": 1,
            "domain_id": domain_id,
            "task_id": task_id,
            "run_id": run_id,
            "run_uuid": run_uuid,
            "execution_id": execution_id,
            "provider": _identity(lease.provider),
            "lease_id": _identity(lease.lease_id),
            "pool_resource_id": _identity(metadata.get("pool_resource_id")),
            "pool_anchor_id": _identity(metadata.get("pool_anchor_id")),
            "acquired_at": _timestamp(lease.acquired_at),
            "expires_at": _timestamp(lease.expires_at),
            "actor_scope": actor_scope,
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        raise OperationSettlementPending("proxy_pool_child_descriptor_invalid") from None
