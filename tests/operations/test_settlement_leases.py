"""Native lease regression tests with no database/config access."""
import threading
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.operations import task_gateway as gateway


class LeaseStore:
    def __init__(self):
        self.deletes = 0
        self.failure = True
        self.acquires = 0

    def release_account_lease(self, run_id, token):
        self.deletes += 1
        if self.failure:
            raise OSError("synthetic delete ACK unavailable")
        return False  # successful exact DELETE of absent original token confirms absence

    def heartbeat_run(self, *args, **kwargs):
        return True

    def acquire_account_lease(self, **kwargs):
        self.acquires += 1
        return f"original-{self.acquires}"

    def is_run_cancel_requested(self, *args):
        return False


@pytest.fixture(autouse=True)
def offline_storage_guard():
    from core.storage import postgres
    with patch.object(postgres, "connect", side_effect=AssertionError("offline tests cannot connect")), \
         patch.object(postgres, "database_url", side_effect=AssertionError("offline tests cannot load config")):
        yield


@pytest.fixture
def store():
    value = LeaseStore()
    with patch.object(gateway, "_operation", return_value=value):
        yield value


def test_failed_delete_preserves_original_handle_and_retries_even_when_lost(store):
    lease = gateway.OperationLease(run_id=7, account_id=9, resource_family="synthetic", token="original")
    try:
        with pytest.raises(OSError):
            lease.release()
        assert not lease.released
        assert lease.state == "release_pending"
        lease._heartbeat_lost = True
        store.failure = False
        assert lease.release()
        assert lease.released
        assert store.deletes == 2
    finally:
        lease._heartbeat_stop.set()


def test_context_keeps_failed_step_and_cannot_reacquire(store):
    context = gateway.OperationHandlerContext({"id": 7, "task_id": 8, "account_id": 9}, execution_id="old")
    lease = context.acquire_lease()
    try:
        with pytest.raises(Exception):
            context.release_lease()
        assert context._lease is lease
        with pytest.raises(Exception):
            context.acquire_lease()
        assert store.acquires == 1
    finally:
        store.failure = False
        context.release_lease()


def test_final_scope_exit_retains_fence_until_atomic_terminal(store):
    store.failure = False
    context = gateway.OperationHandlerContext({"id": 7, "task_id": 8, "account_id": 9}, execution_id="old")
    with context.lease(scope_kind="final") as lease:
        assert context.execution_fence["lease_token"] == lease.token
    try:
        assert not lease.released
        assert store.deletes == 0
        assert context.execution_fence["lease_token"] == lease.token
    finally:
        context.release_lease()


def test_heartbeat_and_release_are_serialized_on_original_handle(store):
    entered = threading.Event()
    resume = threading.Event()
    events = []
    def heartbeat(*args, **kwargs):
        events.append("heartbeat-enter")
        entered.set()
        resume.wait(1)
        events.append("heartbeat-exit")
        return True
    def release(*args, **kwargs):
        events.append("delete")
        return True
    store.heartbeat_run = heartbeat
    store.release_account_lease = release
    lease = gateway.OperationLease(run_id=7,account_id=9,resource_family="synthetic",token="old")
    renewal = threading.Thread(target=lease.heartbeat)
    deletion = threading.Thread(target=lease.release)
    renewal.start()
    assert entered.wait(1)
    deletion.start()
    assert events == ["heartbeat-enter"]
    resume.set()
    renewal.join(1)
    deletion.join(1)
    assert events == ["heartbeat-enter","heartbeat-exit","delete"]
    assert not lease.heartbeat()


def test_release_uses_captured_original_domain_after_ambient_change(store):
    original = SimpleNamespace(database_url="offline-original",operation_schema="old",permit_schema="old",domain_id="old")
    observed = []
    def scope(domain, **kwargs):
        observed.append(domain)
        return nullcontext()
    lease = gateway.OperationLease(run_id=7,account_id=9,resource_family="synthetic",token="old",domain=original)
    with patch.object(gateway,"_domain_scope",side_effect=scope):
        with pytest.raises(OSError):
            lease.release()
        store.failure = False
        lease.release()
    assert observed == [original,original]


def test_failed_step_release_freezes_conservative_terminal_before_caller_can_continue(store):
    calls = []
    store.finish_run = lambda run_id, **kwargs: calls.append(kwargs) or {
        "status":kwargs["status"],"result_summary":kwargs["result_summary"]}
    context = gateway.OperationHandlerContext({"id":7,"task_id":8,"account_id":9},execution_id="old")
    try:
        with pytest.raises(gateway.OperationSettlementPending):
            with context.lease(scope_kind="step"):
                pass
        intent = context._settlement_intent
        assert intent is not None
        assert intent.payload["status"] == "attention_required"
        assert intent.payload["result_summary"]["reason"] == "step_lease_release_unconfirmed"
        assert intent.origin["lease_requirement"] == "step_release_unconfirmed"
        assert intent.origin["scope_kind"] == "step"
        with pytest.raises(gateway.OperationSettlementConflict):
            context.finish(gateway.OperationResult.success())
    finally:
        store.failure = False
        if context._lease is not None:
            context._lease.release()


def test_released_final_handle_never_masquerades_as_no_lease_preflight(store):
    store.failure = False
    context = gateway.OperationHandlerContext({"id":7,"task_id":8,"account_id":9},execution_id="old")
    lease = context.acquire_lease(scope_kind="final")
    lease.release()
    origin = context._origin()
    assert origin["lease_requirement"] == "final"
    assert origin["lease_token"] == lease.token


def test_release_confirmation_keeps_real_thread_join_observable(store):
    import time
    store.failure = False
    lease = gateway.OperationLease(run_id=7,account_id=9,resource_family="synthetic",token="old")
    lease._heartbeat_stop.set()
    lease._heartbeat_thread.join(1)
    allow_exit = threading.Event()
    retiring = threading.Thread(target=lambda:allow_exit.wait(1))
    retiring.start()
    lease._heartbeat_thread = retiring
    try:
        assert not lease.release(deadline=time.monotonic()+0.01)
        assert lease.state == "release_confirmed"
        assert not lease.join(deadline=time.monotonic()+0.01)
        assert retiring.is_alive()
        allow_exit.set()
        assert lease.join(deadline=time.monotonic()+1)
    finally:
        allow_exit.set()
        retiring.join(1)


def test_context_cannot_reacquire_until_old_heartbeat_physically_exits(store):
    store.failure = False
    context = gateway.OperationHandlerContext({"id":7,"task_id":8,"account_id":9},execution_id="old")
    lease = context.acquire_lease()
    lease.release()
    allow_exit = threading.Event()
    retiring = threading.Thread(target=lambda:allow_exit.wait(1))
    retiring.start()
    lease._heartbeat_thread = retiring
    try:
        with pytest.raises(gateway.OperationSettlementPending):
            context.acquire_lease()
        assert store.acquires == 1
    finally:
        allow_exit.set()
        retiring.join(1)


@pytest.mark.parametrize("run_id,account_id",[(99,9),(7,99)])
def test_adopt_rejects_other_run_or_account_without_stealing_handle(store,run_id,account_id):
    from core.operations.settlement_contracts import SettlementDomain
    store.failure = False
    context = gateway.OperationHandlerContext({"id":7,"task_id":8,"account_id":9},execution_id="old")
    lease = gateway.OperationLease(run_id=run_id,account_id=account_id,resource_family="synthetic",token="other")
    try:
        with pytest.raises(gateway.OperationSettlementFenced):
            context.adopt_lease(lease)
        assert context._leases == []
    finally:
        lease.release()


def test_adopt_never_rebinds_captured_lease_to_a_different_original_domain(store):
    from core.operations.settlement_contracts import SettlementDomain
    original = SettlementDomain("offline-original","old","old","old")
    successor = SettlementDomain("offline-new","new","new","new")
    context = gateway.OperationHandlerContext({"id":7,"task_id":8,"account_id":9},execution_id="old")
    context._domain = successor
    lease = gateway.OperationLease(run_id=7,account_id=9,resource_family="synthetic",token="old",domain=original)
    try:
        with pytest.raises(gateway.OperationSettlementFenced):
            context.adopt_lease(lease)
        assert lease.domain is original
        assert context._leases == []
    finally:
        with patch.object(gateway,"_domain_scope",return_value=nullcontext()):
            store.failure = False
            lease.release()


def test_live_superseded_disposition_confirms_old_token_without_claiming_original_result(store):
    store.failure = False
    lease = gateway.OperationLease(run_id=7,account_id=9,resource_family="synthetic",token="old")
    try:
        with pytest.raises(ValueError):
            lease.mark_disposition_confirmed({"kind":"other"})
        assert lease.state == "held"
        import hashlib
        proof={"disposition_kind":"live_superseded","run_id":7,
               "original_intent_committed":False,"lease_disposition":"exact_original_token_absent",
               "lease_fingerprint":hashlib.sha256(b"old").hexdigest()}
        assert lease.mark_disposition_confirmed(proof)
        assert lease.released
        assert lease.state == "release_confirmed"
    finally:
        lease._heartbeat_stop.set()
