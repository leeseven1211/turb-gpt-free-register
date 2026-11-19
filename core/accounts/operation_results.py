# -*- coding: utf-8 -*-
"""账号执行的结果证据、本地读回与 durable lifecycle 适配。"""
from __future__ import annotations

import json
import re
import threading
import uuid
from collections.abc import Mapping
from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import Any

from core import db, operation_task_store
from core.accounts.liveness import service as live_check_service
from core.operations import task_gateway
from core.operations.proxy_resources import capture_proxy_pool_child


class AccountRouteCleanup:
    """Retain one original route and confirm its exact local release."""

    def __init__(self, route, *, run_id: int, domain=None) -> None:
        self.route = route
        self.run_id = int(run_id)
        self.domain = domain
        self.resource_identity = f"account-route:{self.run_id}:{uuid.uuid4().hex}"
        self._cleanup_facts = {}
        self.resource_id = None
        self.resource_uuid = None
        self.proxy_pool_child = None
        self.release_confirmed = False
        self._provider_returned = False
        self._physical_confirmed = False
        self._reason = None
        self._fault = None
        self._recent_until = None
        self._lock = threading.RLock()
        lease = getattr(route, "lease", None)
        lease_id = getattr(lease, "lease_id", None)
        metadata = getattr(lease, "metadata", None)
        self._persistent_lease_id = (
            str(lease_id) if lease_id is not None and isinstance(metadata, Mapping)
            and (metadata.get("persistent_lease") or metadata.get("pool_resource_id")) else None
        )
        self._pool_owned = bool(isinstance(metadata, Mapping) and metadata.get("pool_resource_id"))
        self._recent_ttl = max(0, int(metadata.get("recent_ttl") or 0)) if isinstance(metadata, Mapping) else 0

    def __getattr__(self, name):
        # Preserve the existing route read surface (proxy_url/public_dict).
        return getattr(self.route, name)

    def record_cleanup_facts(self, facts: Mapping[str, Any]) -> None:
        """Capture only observed facts before an intermediate release boundary."""
        from core.operations.settlement_contracts import seal_intent, thaw
        from core.storage.operations.common import _scrub

        self._cleanup_facts = thaw(seal_intent(
            kind="terminal", origin={}, payload=_scrub(dict(facts)),
        ).payload)

    def _read_original(self, *, deadline=None):
        from core.storage import postgres
        from psycopg.rows import dict_row

        with postgres.connect(row_factory=dict_row, deadline=deadline) as conn:
            with conn.cursor() as cur:
                schema = postgres.quote_identifier(postgres.schema_name())
                cur.execute(
                    f'SELECT * FROM {schema}."proxy_leases" WHERE lease_id=%s',
                    (self._persistent_lease_id,),
                )
                return cur.fetchone()

    def _retry_original(self, *, lease_id=None, deadline=None) -> None:
        """Retry only the original persistent ledger row; never initializes DDL."""
        from core.storage import postgres

        lease_id = str(lease_id or self._persistent_lease_id or "")
        with postgres.connect(deadline=deadline) as conn:
            with conn.cursor() as cur:
                schema = postgres.quote_identifier(postgres.schema_name())
                cur.execute(
                    f'''UPDATE {schema}."proxy_leases"
                        SET state=%s, recent_until=%s, released_at=now(),
                            release_reason=%s
                        WHERE lease_id=%s AND state IN
                          ('leased','shared_leased','pool_leased','recent')''',
                    (
                        "recent" if self._recent_until else "released",
                        self._recent_until,
                        str(self._reason or "account-route-release")[:120],
                        lease_id,
                    ),
                )
            conn.commit()

    def release(self, reason=None, *, fault=None, deadline=None) -> bool:
        from core.storage.operations.common import settlement_scope

        with self._lock:
            if self.release_confirmed:
                return True
            if self._reason is None:
                self._reason = str(reason or f"account-route-{self.run_id}")
                self._fault = bool(fault)
                if self._recent_ttl:
                    self._recent_until = (datetime.now() + timedelta(seconds=self._recent_ttl)).isoformat(timespec="seconds")
            scope = settlement_scope(self.domain, deadline=deadline) if self.domain is not None else nullcontext()
            try:
                with scope:
                    if not self._physical_confirmed:
                        if not self._provider_returned:
                            result = self.route.release(reason=self._reason, fault=self._fault)
                            if result is False:
                                raise task_gateway.OperationSettlementPending("account_route_release_unconfirmed")
                            self._provider_returned = True
                        if self._persistent_lease_id:
                            row = self._read_original(deadline=deadline)
                            if not row or row.get("state") not in {"released", "recent"}:
                                if not self._pool_owned and row is not None:
                                    # The provider may already have marked its
                                    # in-memory handle released while swallowing
                                    # SQL failure. Retry only the original local
                                    # ledger command, never provider/business.
                                    metadata = row.get("data")
                                    shared = bool(row.get("allow_reuse") or (
                                        isinstance(metadata, Mapping) and metadata.get("allow_reuse")
                                    ))
                                    expiry = row.get("recent_until") if row.get("state") == "recent" else row.get("expires_at")
                                    if shared or expiry and str(expiry) <= datetime.now().isoformat(timespec="seconds"):
                                        self._recent_until = None
                                    self._retry_original(lease_id=self._persistent_lease_id, deadline=deadline)
                                    row = self._read_original(deadline=deadline)
                                if not row or row.get("state") not in {"released", "recent"}:
                                    raise task_gateway.OperationSettlementPending("account_original_proxy_release_unconfirmed")
                        self._physical_confirmed = True
                    if self.resource_id is not None:
                        if not operation_task_store.release_resource(self.resource_id, state="released"):
                            raise task_gateway.OperationSettlementPending("account_route_resource_release_unconfirmed")
                    self.release_confirmed = True
                    return True
            except (task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
                raise
            except Exception as exc:
                raise task_gateway.OperationResourceCleanupPending(
                    cleanup=self, resource_identity=self.resource_identity, facts=self._cleanup_facts,
                ) from exc


def own_account_route(context, route, *, purpose: str, actor_scope: str = "external"):
    """Register the exact route before reporting/using it or persisting metadata."""
    if context is None or isinstance(route, AccountRouteCleanup):
        return route
    cleanup = AccountRouteCleanup(
        route, run_id=context.run_id, domain=getattr(context, "settlement_domain", None),
    )
    identity = cleanup.resource_identity
    context.register_cleanup(cleanup, key=identity, blocking=True)
    try:
        cleanup.proxy_pool_child = capture_proxy_pool_child(route, context, actor_scope=actor_scope)
        detail = {"execution_id": str(getattr(context, "execution_id", "")), "purpose": str(purpose)}
        if cleanup.proxy_pool_child is not None:
            detail["proxy_pool_child"] = dict(cleanup.proxy_pool_child)
        resource = operation_task_store.register_resource(
            context.run_id, resource_type="proxy_lease", provider=str(getattr(route, "provider", "") or ""),
            external_id=identity,
            detail=detail,
        )
        cleanup.resource_id = int(resource["id"])
        cleanup.resource_uuid = str(resource["resource_uuid"])
        payload = {
            "resource_id": cleanup.resource_id, "resource_uuid": cleanup.resource_uuid,
            "run_id": context.run_id, "execution_id": str(getattr(context, "execution_id", "")),
            "external_id": identity,
        }
        if cleanup.proxy_pool_child is not None:
            payload["proxy_pool_child"] = dict(cleanup.proxy_pool_child)
        context.add_settlement_obligation(
            "resource_release", resource_identity=f"operation-resource:{cleanup.resource_uuid}",
            payload=payload,
            blocks_permit=True,
        )
    except (task_gateway.OperationSettlementConflict, task_gateway.OperationSettlementFenced):
        raise
    except Exception as exc:
        cleanup.record_cleanup_facts({
            "operation_stage": "resource_registration", "completed_steps": [],
            "observed_steps": [], "unexecuted_steps": [str(purpose)],
        })
        raise task_gateway.OperationResourceCleanupPending(
            cleanup=cleanup, resource_identity=identity, facts=cleanup._cleanup_facts,
        ) from exc
    return cleanup


def account_setup_readback(
    account_id: int,
    email: str,
    steps: set[str],
    result: Mapping[str, Any],
) -> tuple[bool, dict[str, bool]]:
    """Verify local business persistence before publishing remote confirmed."""
    account = db.get_account(int(account_id)) or db.get_account_by_email(email) or {}
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    extra = raw_extra if isinstance(raw_extra, Mapping) else {}
    checks: dict[str, bool] = {}
    if "password" in steps:
        from core.accounts.password_evidence import password_is_confirmed

        checks["password"] = password_is_confirmed(account)
    if "twofa" in steps:
        checks["twofa"] = bool(str(account.get("totp_secret") or "").strip()) and not bool(
            extra.get("totp_setup_pending")
        )
    if "plan_check" in steps:
        checks["plan_check"] = str(account.get("plan_check_status") or "").strip().lower() == "success"
    status = str(result.get("status") or "").strip().lower()
    if status == "deactivated":
        checks["account_status"] = str(account.get("account_status") or "").strip().lower() == "deactivated"
    return bool(checks) and all(checks.values()), checks


def account_setup_receipt(
    account_id: int,
    email: str,
    steps: set[str],
    result: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Map an adapter result to the common remote receipt safety states."""
    status = str(result.get("status") or "").strip().lower()
    detail: dict[str, Any] = {
        "remote_response_received": True,
        "remote_result_confirmed": status in {"success", "completed", "deactivated"}
        or bool(result.get("ok")),
    }
    if result.get("password_driver") == "protocol" or isinstance(result.get("step_results"), Mapping):
        completed = set()
        rejected = False
        evidence = []
        for step in sorted(steps):
            value = (result.get("step_results") or {}).get(step) or result.get(
                {"password": "password_setup", "twofa": "twofa_setup", "plan_check": "plan_check"}.get(step, "")
            )
            outcome = value if isinstance(value, Mapping) else {}
            receipt_state = outcome.get("remote_receipt_state")
            if step == "plan_check":
                receipt_state = "confirmed" if outcome.get("ok") else "not_submitted"
            elif receipt_state in {None, "none", "not_submitted"} and outcome.get("mutation_submitted") is False:
                receipt_state = "not_submitted"
            elif receipt_state is None and outcome.get("ok"):
                receipt_state = "confirmed"
            evidence.append({"step": step, "ok": bool(outcome.get("ok")), "receipt_state": receipt_state or "unknown"})
            detail["setup_step_receipts"] = evidence
            if receipt_state == "rejected":
                rejected = True
            elif receipt_state == "not_submitted":
                continue
            elif receipt_state == "confirmed" and outcome.get("ok"):
                completed.add(step)
            else:
                return "unknown", detail
        if not completed:
            if rejected:
                return "rejected", detail
            return "not_submitted", {**detail, "mutation_submitted": False, "action_dispatched": False}
        local_confirmed, checks = account_setup_readback(account_id, email, completed, result)
        detail.update({
            "remote_result_confirmed": True,
            "local_business_writeback_confirmed": local_confirmed,
            "local_readback_confirmed": local_confirmed,
            "local_readback_checks": checks,
        })
        return ("confirmed" if local_confirmed else "local_commit_required"), detail
    if status == "unsupported":
        return "rejected", detail
    if status not in {"success", "completed", "deactivated"} and not result.get("ok"):
        return "unknown", detail
    local_confirmed, checks = account_setup_readback(
        account_id, email, steps, result,
    )
    detail.update({
        "local_business_writeback_confirmed": local_confirmed,
        "local_readback_confirmed": local_confirmed,
        "local_readback_checks": checks,
    })
    return ("confirmed" if local_confirmed else "local_commit_required"), detail


def safe_operation_result(
    value: Any,
    *,
    default_message: str = "账号操作未完成",
) -> task_gateway.OperationResult:
    """保留具体失败原因，仅将无凭据的诊断字段写入任务摘要。"""
    if isinstance(value, task_gateway.OperationResult):
        return value
    result = dict(value) if isinstance(value, Mapping) else {}
    status = str(result.get("status") or "").strip().lower()
    message = str(result.get("message") or default_message)
    error = str(result.get("error") or "") or None
    summary = {
        key: result.get(key)
        for key in (
            "status", "ok", "message", "plan_check", "twofa_driver", "auth_source",
            "browser_opened", "account_status_persisted", "proxy_provider",
            "proxy_region", "proxy_mode", "credential_confirmed",
            "mutation_submitted", "action_dispatched", "reconcile_required", "manual_reconcile",
            "password_setup", "password_driver", "twofa_setup", "remote_receipt_state",
            "stop_requested", "step_results", "setup_step_results", "requested_steps",
        )
        if key in result and result.get(key) is not None
    }
    cause_code = str(result.get("cause_code") or result.get("error_code") or "")
    if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", cause_code):
        summary["cause_code"] = cause_code
    for key in ("auth_diagnostics", "cause_diagnostics"):
        diagnostics = live_check_service._safe_refresh_auth_diagnostics(result.get(key))
        if diagnostics:
            summary[key] = diagnostics
    if (
        status in {"unknown", "request_unknown", "pending_confirmation", "attention_required"}
        or summary.get("reconcile_required") is True or summary.get("manual_reconcile") is True
    ):
        return task_gateway.OperationResult.request_unknown(message, summary, error=error)
    if status in {"success", "completed"} or bool(result.get("ok")):
        return task_gateway.OperationResult.success(summary, message=message)
    if status in {"cancelled", "stopped"}:
        return task_gateway.OperationResult.cancelled(message)
    if status == "deactivated":
        return task_gateway.OperationResult("deactivated", summary, message, message)
    if status == "unsupported":
        return task_gateway.OperationResult("unsupported", summary, message, message)
    if status == "partial_success":
        return task_gateway.OperationResult("partial_success", summary, message, error or message)
    return task_gateway.OperationResult("failed", summary, message, error or message)


class NativeTaskLifecycle:
    """Legacy-service-shaped reporter backed by one durable Run context."""

    def __init__(self, context: task_gateway.OperationHandlerContext) -> None:
        self.context = context

    def start_task(self, _task_id: int | None, *, message: str = "开始执行") -> None:
        self.context.report(stage="plan", state="running", message=message)

    def append_event(self, _task_id: int | None, **event: Any) -> None:
        payload = dict(event)
        stage = str(payload.pop("stage", "event") or "event")
        message = str(payload.pop("message") or "处理中")
        state = payload.pop("state", None)
        level = str(payload.pop("level", None) or "INFO")
        event_type = payload.pop("event_type", None)
        detail = payload.pop("detail", None)
        if payload:
            detail = {**(dict(detail) if isinstance(detail, Mapping) else {}), **payload}
        self.context.report(
            stage=stage, message=message, level=level,
            state=state, event_type=event_type, detail=detail,
        )

    def finish_task(self, _task_id: int | None, **kwargs: Any) -> dict:
        status = str(kwargs.get("status") or "failed").strip().lower()
        summary = kwargs.get("result_summary")
        summary = dict(summary) if isinstance(summary, Mapping) else {}
        if str(summary.get("outcome") or "").lower() == "request_unknown":
            result = task_gateway.OperationResult.request_unknown(
                str(kwargs.get("message") or "当前步骤未保存完整回执"), summary,
                error=str(kwargs.get("error") or "") or None,
            )
        elif status == "cancelled":
            result = task_gateway.OperationResult.cancelled(
                str(kwargs.get("message") or "任务已取消"),
            )
        elif status == "attention_required":
            summary.update({"outcome": "request_unknown", "reconcile_required": True})
            result = task_gateway.OperationResult.request_unknown(
                str(kwargs.get("message") or "当前步骤未保存完整回执"), summary,
                error=str(kwargs.get("error") or "") or None,
            )
        else:
            result = task_gateway.OperationResult(
                status,
                summary,
                str(kwargs.get("message") or ""),
                str(kwargs.get("error") or "") or None,
            )
        return self.context.finish(result)

    def register_task_dependency(self, **kwargs: Any) -> dict:
        return operation_task_store.register_task_dependency(**kwargs)


def native_task_data(context: task_gateway.OperationHandlerContext) -> dict[str, Any]:
    data = context.run.get("data")
    return dict(data) if isinstance(data, Mapping) else {}


def finish_native_context(
    context: task_gateway.OperationHandlerContext,
    result: task_gateway.OperationResult,
) -> task_gateway.OperationResult:
    if not context.finished:
        context.finish(result)
    return context.last_result or result
