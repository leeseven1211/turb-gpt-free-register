"""Passive exact proxy-child evidence for an original operation resource.

This adapter only reads an existing child and acknowledges local borrowing
responsibility. It never returns a proxy, changes inventory, or proves a remote
business outcome.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from core.storage.operations import common as _common


_BINDING_FIELDS = frozenset({
    "version", "domain_id", "task_id", "run_id", "run_uuid", "execution_id",
    "provider", "lease_id", "pool_resource_id", "pool_anchor_id",
    "acquired_at", "expires_at", "actor_scope",
})


def _timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _positive_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def reconcile_proxy_resource(cur, *, resource, binding, origin, domain) -> bool:
    """CAS one exact resource after its process and child responsibility ended.

    The caller holds the original permit/Run/resource locks and validates its
    receipt claim or independent disposition. No caller-supplied stop boolean
    replaces the original process identity.
    """
    if not isinstance(resource, Mapping) or not isinstance(binding, Mapping) or not isinstance(origin, Mapping):
        return False
    detail = _common._decode(resource.get("detail")) or {}
    if (not isinstance(detail, Mapping) or set(binding) != _BINDING_FIELDS
            or binding.get("version") != 1 or isinstance(binding.get("version"), bool)
            or binding.get("actor_scope") != "owner_process"
            or detail.get("proxy_pool_child") != dict(binding)
            or resource.get("state") not in {"acquired", "reconciliation_required"}
            or resource.get("resource_type") != "proxy_lease"
            or not _positive_id(binding.get("task_id")) or not _positive_id(binding.get("run_id"))):
        return False
    if (str(binding.get("domain_id") or "") != str(domain.domain_id)
            or str(origin.get("domain_id") or "") != str(domain.domain_id)
            or int(resource.get("run_id") or 0) != binding["run_id"]
            or int(origin.get("run_id") or 0) != binding["run_id"]
            or int(origin.get("task_id") or 0) != binding["task_id"]):
        return False
    for key in ("run_uuid", "execution_id"):
        if not binding.get(key) or str(binding[key]) != str(origin.get(key) or ""):
            return False
    if (str(detail.get("execution_id") or "") != str(binding["execution_id"])
            or not binding.get("provider")
            or str(resource.get("provider") or "") != str(binding["provider"])
            or any(not isinstance(binding.get(key), str) or not binding[key]
                   for key in ("lease_id", "pool_resource_id", "pool_anchor_id"))):
        return False
    acquired = _timestamp(binding.get("acquired_at"))
    expiry = _timestamp(binding.get("expires_at"))
    if acquired is None or expiry is None or acquired.tzinfo != expiry.tzinfo:
        return False
    if expiry <= acquired:
        return False
    from core.storage.operations.recovery import _original_process_exited
    owner = origin.get("owner")
    if not isinstance(owner, Mapping) or not _original_process_exited(owner):
        return False
    cur.execute(f'''SELECT lease_id,provider,state,acquired_at,expires_at,
            operation_task_id,operation_run_id,data
        FROM {_common._quote(domain.permit_schema)}."proxy_leases"
        WHERE lease_id=%s FOR SHARE''', (binding["lease_id"],))
    child = cur.fetchone()
    if not child:
        return False
    child_data = _common._decode(child.get("data")) or {}
    if not isinstance(child_data, Mapping):
        return False
    if (str(child.get("lease_id") or "") != binding["lease_id"]
            or str(child.get("provider") or "") != str(binding["provider"])
            or str(child_data.get("pool_resource_id") or "") != binding["pool_resource_id"]
            or str(child_data.get("pool_anchor_id") or "") != binding["pool_anchor_id"]
            or child.get("operation_task_id") != binding["task_id"]
            or child.get("operation_run_id") != binding["run_id"]
            or _timestamp(child.get("acquired_at")) != acquired
            or _timestamp(child.get("expires_at")) != expiry):
        return False
    if child.get("state") in {"released", "recent"}:
        evidence = "exact_child_released"
    elif (child.get("state") in {"pool_leased", "shared_leased"}
          and datetime.now(expiry.tzinfo) >= expiry):
        evidence = "exact_child_expired"
    else:
        return False
    cur.execute(f'''UPDATE {_common._table('operation_resources')}
        SET state='released',released_at=now(),
            detail=detail || %s::jsonb
        WHERE id=%s AND run_id=%s AND resource_uuid=%s AND external_id=%s
          AND resource_type='proxy_lease' AND provider=%s
          AND state IN ('acquired','reconciliation_required')
          AND detail->>'execution_id'=%s AND detail->'proxy_pool_child'=%s::jsonb
        RETURNING id''',
        (_common._json({"proxy_child_release_evidence": evidence}),
         int(resource["id"]), binding["run_id"], str(resource["resource_uuid"]),
         str(resource.get("external_id") or ""), str(binding["provider"]),
         str(binding["execution_id"]), _common._json(dict(binding))))
    return cur.fetchone() is not None
