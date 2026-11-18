"""Offline producer contracts for exact proxy-pool child associations."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import importlib
import logging
from types import SimpleNamespace
import threading

import pytest

from core.accounts import operation_results
from core.codex import operation_service as oauth
from core.operations import task_gateway
from core.operations.settlement_contracts import (
    OperationSettlementPending,
    SettlementDomain,
)


DOMAIN = SettlementDomain(
    "postgresql://synthetic/never-connect",
    "original_operations",
    "original_records",
    "original-domain",
)


class BindingContext:
    """Keep gateway obligation sealing real while replacing external storage."""

    add_settlement_obligation = task_gateway.OperationHandlerContext.add_settlement_obligation

    def __init__(self, *, driver="protocol"):
        self.task_id = 42
        self.run_id = 43
        self.execution_id = "original-execution"
        self.run = {
            "id": 43,
            "task_id": 42,
            "run_uuid": "original-run-uuid",
            "account_id": 41,
            "email_snapshot": "synthetic@example.test",
            "resource_family": "openai_interactive",
            "data": {"config_snapshot": {"oauth_driver": driver}},
        }
        self.settlement_domain = DOMAIN
        self._execution = SimpleNamespace(
            execution_id=self.execution_id,
            permit_id="original-permit",
            claimed_run=self.run,
            settlement_domain=DOMAIN,
            settlement_ticket={
                "version": 1,
                "domain_id": DOMAIN.domain_id,
                "ticket_id": "original-ticket",
                "permit_id": "original-permit",
                "task_id": self.task_id,
                "run_id": self.run_id,
                "run_uuid": "original-run-uuid",
                "execution_id": self.execution_id,
            },
        )
        self._transition_lock = threading.RLock()
        self._settlement_intent = None
        self._settlement_obligations = {}
        self.cleanups = []
        self.events = []
        self.terminal_results = []

    def register_cleanup(self, cleanup, *, key, blocking=True):
        self.events.append("cleanup-owned")
        self.cleanups.append((cleanup, key, blocking))
        return cleanup

    def acquire_lease(self, **kwargs):
        return SimpleNamespace(token="synthetic-account-lease", lost=False)

    def finish(self, **kwargs):
        self.terminal_results.append(deepcopy(kwargs))
        return kwargs


def pool_route():
    lease = SimpleNamespace(
        lease_id="original-child",
        provider="synthetic-provider",
        acquired_at=datetime(2026, 11, 18, 8, 30, 0),
        expires_at=datetime(2026, 11, 18, 8, 35, 0),
        state="pool_leased",
        metadata={
            "persistent_lease": True,
            "pool_resource_id": "original-pool-resource",
            "pool_anchor_id": "original-anchor",
            "allow_reuse": False,
            "operation_task_id": 42,
            "operation_run_id": 43,
            "account_id": 41,
        },
    )
    return SimpleNamespace(
        lease=lease,
        provider="synthetic-provider",
        mode="pool",
        region="ZZ",
        proxy_url="http://private-user:private-password@192.0.2.1:80",
        public_dict=lambda: {"network_route": "proxy"},
        release=lambda **kwargs: None,
    )


def expected_descriptor(*, actor_scope="external"):
    return {
        "version": 1,
        "domain_id": "original-domain",
        "task_id": 42,
        "run_id": 43,
        "run_uuid": "original-run-uuid",
        "execution_id": "original-execution",
        "provider": "synthetic-provider",
        "lease_id": "original-child",
        "pool_resource_id": "original-pool-resource",
        "pool_anchor_id": "original-anchor",
        "acquired_at": "2026-11-18T08:30:00",
        "expires_at": "2026-11-18T08:35:00",
        "actor_scope": actor_scope,
    }


def capture(route, context, **kwargs):
    try:
        module = importlib.import_module("core.operations.proxy_resources")
    except ModuleNotFoundError as exc:
        pytest.fail(f"exact proxy child capture is not implemented: {exc}")
    helper = getattr(module, "capture_proxy_pool_child", None)
    assert callable(helper), "exact proxy child capture is not implemented"
    return helper(route, context, **kwargs)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    from core.storage import postgres

    def forbidden(*args, **kwargs):
        raise AssertionError("offline proxy binding test attempted external I/O")

    monkeypatch.setattr(postgres, "connect", forbidden)
    monkeypatch.setattr(postgres, "connect_dedicated", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)


def resource_recorder(monkeypatch, context, *, store=None):
    resources = []
    target = store or operation_results.operation_task_store

    def register(run_id, **kwargs):
        context.events.append("resource-registered")
        row = {
            "id": 901,
            "resource_uuid": "original-operation-resource",
            "run_id": run_id,
            **deepcopy(kwargs),
        }
        resources.append(row)
        return deepcopy(row)

    monkeypatch.setattr(target, "register_resource", register)
    return resources


def only_obligation(context):
    values = list(context._settlement_obligations.values())
    assert len(values) == 1
    assert values[0]["action_kind"] == "resource_release"
    assert values[0]["blocks_permit"] is True
    return values[0]


def test_capture_freezes_original_pool_child_identity_without_private_routing_data():
    route = pool_route()
    context = BindingContext()

    descriptor = capture(route, context)
    route.lease.lease_id = "replacement-child"
    route.lease.metadata["pool_resource_id"] = "replacement-pool-resource"
    route.lease.metadata["pool_anchor_id"] = "replacement-anchor"
    route.lease.acquired_at = datetime(2026, 11, 18, 9, 0, 0)
    context.run["run_uuid"] = "replacement-run"

    assert descriptor == expected_descriptor()
    assert "resource_uuid" not in descriptor
    assert "private-password" not in repr(descriptor)
    assert "192.0.2.1" not in repr(descriptor)
    assert "postgresql://" not in repr(descriptor)


@pytest.mark.parametrize("actor_scope", ["owner_process", "external"])
def test_capture_preserves_explicit_actor_scope(actor_scope):
    assert capture(pool_route(), BindingContext(), actor_scope=actor_scope) == expected_descriptor(
        actor_scope=actor_scope,
    )


@pytest.mark.parametrize("missing", [
    "lease_id", "pool_resource_id", "pool_anchor_id", "acquired_at", "expires_at",
])
def test_incomplete_marked_pool_child_cannot_silently_become_generic_cleanup(missing):
    route = pool_route()
    if missing in route.lease.metadata:
        route.lease.metadata.pop(missing)
    else:
        setattr(route.lease, missing, None)

    with pytest.raises(OperationSettlementPending):
        capture(route, BindingContext())


@pytest.mark.parametrize("lease", [
    None,
    SimpleNamespace(lease_id="legacy-persistent", metadata={"persistent_lease": True}),
])
def test_non_pool_route_does_not_create_a_proxy_child_binding(lease):
    route = SimpleNamespace(lease=lease, provider="synthetic")
    assert capture(route, BindingContext()) is None


@pytest.mark.parametrize("missing", ["domain", "ticket"])
def test_legacy_context_without_captured_authority_is_not_given_a_guessed_binding(missing):
    context = BindingContext()
    if missing == "domain":
        context.settlement_domain = None
        context._execution.settlement_domain = None
    else:
        context._execution.settlement_ticket = None

    assert capture(pool_route(), context) is None


@pytest.mark.parametrize("actor_scope", ["owner_process", "external"])
def test_account_producer_persists_the_same_snapshot_in_resource_and_obligation(
    monkeypatch, actor_scope,
):
    context = BindingContext()
    route = pool_route()
    resources = resource_recorder(monkeypatch, context)

    operation_results.own_account_route(
        context, route, purpose="plan-check", actor_scope=actor_scope,
    )
    route.lease.metadata["pool_anchor_id"] = "replacement-anchor"
    obligation = only_obligation(context)

    assert context.events == ["cleanup-owned", "resource-registered"]
    assert resources[0]["detail"]["proxy_pool_child"] == expected_descriptor(
        actor_scope=actor_scope,
    )
    assert obligation["payload"]["proxy_pool_child"] == resources[0]["detail"]["proxy_pool_child"]
    assert obligation["payload"]["resource_id"] == 901
    assert obligation["payload"]["resource_uuid"] == "original-operation-resource"


def test_account_producer_defaults_to_external_actor_scope(monkeypatch):
    context = BindingContext()
    resources = resource_recorder(monkeypatch, context)

    operation_results.own_account_route(context, pool_route(), purpose="plan-check")

    assert resources[0]["detail"]["proxy_pool_child"] == expected_descriptor()
    assert only_obligation(context)["payload"]["proxy_pool_child"] == expected_descriptor()


def test_account_capture_failure_retains_cleanup_ownership_without_registering_resource(monkeypatch):
    context = BindingContext()
    route = pool_route()
    route.lease.expires_at = None
    resources = resource_recorder(monkeypatch, context)

    with pytest.raises(OperationSettlementPending):
        operation_results.own_account_route(context, route, purpose="plan-check")

    assert context.events == ["cleanup-owned"]
    assert context.cleanups[0][0].route is route
    assert resources == []
    assert context.terminal_results == []
    assert context._settlement_obligations == {}


def test_account_missing_child_attribute_is_rejected_after_cleanup_ownership(monkeypatch):
    context = BindingContext()
    route = pool_route()
    delattr(route.lease, "lease_id")
    resources = resource_recorder(monkeypatch, context)

    with pytest.raises(OperationSettlementPending):
        operation_results.own_account_route(context, route, purpose="plan-check")

    assert context.events == ["cleanup-owned"]
    assert context.cleanups[0][0].route is route
    assert resources == []


def test_account_non_pool_registration_keeps_existing_generic_obligation(monkeypatch):
    context = BindingContext()
    route = SimpleNamespace(lease=None, provider="request", release=lambda **kwargs: None)
    resources = resource_recorder(monkeypatch, context)

    operation_results.own_account_route(context, route, purpose="plan-check")

    assert "proxy_pool_child" not in resources[0]["detail"]
    assert "proxy_pool_child" not in only_obligation(context)["payload"]


def test_account_live_release_keeps_the_original_durable_binding(monkeypatch):
    context = BindingContext()
    resources = resource_recorder(monkeypatch, context)
    released = []
    monkeypatch.setattr(
        operation_results.operation_task_store,
        "release_resource",
        lambda resource_id, **kwargs: released.append((resource_id, deepcopy(kwargs))) or True,
    )
    cleanup = operation_results.own_account_route(context, pool_route(), purpose="plan-check")
    monkeypatch.setattr(cleanup, "_read_original", lambda **kwargs: {
        "lease_id": "original-child", "state": "released",
    })

    assert cleanup.release(reason="plan-check-completed") is True
    assert released == [(901, {"state": "released"})]
    assert resources[0]["detail"]["proxy_pool_child"] == expected_descriptor()
    assert only_obligation(context)["payload"]["proxy_pool_child"] == expected_descriptor()


def prepare_codex_producer(monkeypatch, context, route):
    monkeypatch.setattr(oauth.operation_task_store, "get_run", lambda run_id: context.run)
    monkeypatch.setattr(oauth.operation_task_store, "is_run_cancel_requested", lambda *args: False)
    monkeypatch.setattr(oauth.operation_task_store, "append_runtime_event", lambda *args, **kwargs: {})
    monkeypatch.setattr(oauth.operation_task_store, "record_remote_intent", lambda *args, **kwargs: {})
    monkeypatch.setattr(oauth, "_deployment_unavailable", lambda snapshot: None)
    monkeypatch.setattr(oauth, "_feature_ready", lambda snapshot: (True, ""))
    monkeypatch.setattr(oauth.db, "update_account_codex_operation_state", lambda *args, **kwargs: True)
    monkeypatch.setattr(oauth.task_run_log, "TaskRunLogHandler", lambda *args, **kwargs: logging.NullHandler())
    monkeypatch.setattr(oauth.task_run_log, "set_current_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr("core.operations.concurrency.set_execution_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("core.proxy.account_routes.acquire_account_proxy", lambda **kwargs: route)
    monkeypatch.setattr(oauth._RouteCleanup, "release", lambda self, **kwargs: True)

    def stop_at_oauth(*args, **kwargs):
        context.events.append("oauth-dispatched")
        raise OperationSettlementPending("synthetic stop after producer boundary")

    monkeypatch.setattr("core.codex.oauth.run_codex_oauth", stop_at_oauth)


@pytest.mark.parametrize(("driver", "actor_scope"), [
    ("protocol", "owner_process"),
    ("protocol_v2", "owner_process"),
    ("protocol_current", "owner_process"),
    ("protocol_direct", "owner_process"),
    ("roxy", "external"),
    ("protocol_future", "external"),
])
def test_codex_producer_captures_actor_scope_before_oauth_dispatch(monkeypatch, driver, actor_scope):
    context = BindingContext(driver=driver)
    route = pool_route()
    resources = resource_recorder(monkeypatch, context, store=oauth.operation_task_store)
    prepare_codex_producer(monkeypatch, context, route)

    with pytest.raises(OperationSettlementPending, match="synthetic stop"):
        oauth._execute_claimed_run_with_context(43, context._execution, context)

    assert context.events == ["cleanup-owned", "resource-registered", "oauth-dispatched"]
    assert resources[0]["detail"]["proxy_pool_child"] == expected_descriptor(actor_scope=actor_scope)
    assert only_obligation(context)["payload"]["proxy_pool_child"] == expected_descriptor(
        actor_scope=actor_scope,
    )
    assert only_obligation(context)["payload"]["external_id"] == resources[0]["external_id"]


def test_codex_missing_child_attribute_is_rejected_after_cleanup_ownership(monkeypatch):
    context = BindingContext()
    route = pool_route()
    delattr(route.lease, "lease_id")
    resources = resource_recorder(monkeypatch, context, store=oauth.operation_task_store)
    prepare_codex_producer(monkeypatch, context, route)

    with pytest.raises(OperationSettlementPending, match="proxy_pool_child_descriptor_invalid"):
        oauth._execute_claimed_run_with_context(43, context._execution, context)

    assert context.events == ["cleanup-owned"]
    assert context.cleanups[0][0].route is route
    assert resources == []
    assert context.terminal_results == []
