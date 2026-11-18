"""Real gateway contexts and admission boundaries using offline repository seams."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from core.operations import task_gateway as gateway


@pytest.fixture(autouse=True)
def offline_storage_guard():
    from core.storage import postgres
    with patch.object(postgres, "connect", side_effect=AssertionError("offline tests cannot connect")), \
         patch.object(postgres, "database_url", side_effect=AssertionError("offline tests cannot load config")):
        yield


class ResultStore:
    def __init__(self):
        self.calls = []
        self.failed = True

    def is_run_cancel_requested(self, *args):
        return False

    def finish_run(self, run_id, **kwargs):
        self.calls.append(kwargs)
        if self.failed:
            raise OSError("synthetic database unavailable")
        return {"id":run_id, "status":kwargs["status"], "result_summary":kwargs["result_summary"]}


def test_native_finish_failure_freezes_first_result_and_forbids_replacement():
    store = ResultStore()
    with patch.object(gateway,"_operation", return_value=store):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8}, execution_id="original")
        summary = {"steps":[{"state":"done"}]}
        with pytest.raises(Exception):
            context.finish(gateway.OperationResult.success(summary))
        summary["steps"][0]["state"] = "mutated"
        with pytest.raises(Exception):
            context.finish(gateway.OperationResult.failed("late catch"))
        assert len(store.calls) == 1
        assert store.calls[0]["result_summary"]["steps"][0]["state"] == "done"


def test_duplicate_finish_is_pure_confirmation():
    store = ResultStore()
    store.failed = False
    with patch.object(gateway,"_operation", return_value=store):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8}, execution_id="original")
        result = gateway.OperationResult.success({"writeback":"done"})
        first = context.finish(result)
        assert context.finish(result) == first
        assert len(store.calls) == 1


def test_confirmed_actual_result_drives_context_success_hooks():
    store = ResultStore()
    store.failed = False
    store.finish_run = lambda *args, **kwargs: {
        "status":"attention_required", "result_summary":{"outcome":"request_unknown"},
        "error_message":"original remote receipt incomplete"}
    with patch.object(gateway,"_operation", return_value=store):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8}, execution_id="original")
        context.finish(gateway.OperationResult.success({"requested":"success"}))
        assert context.finished
        assert context.last_result.status == "request_unknown"
        assert not context.last_result.as_dict()["ok"]


def test_defer_failure_is_frozen_before_later_cancellation_and_no_terminal_write():
    store = ResultStore()
    calls = []
    def requeue(run_id, **kwargs):
        calls.append(kwargs)
        raise OSError("synthetic offline")
    store.requeue_claimed_run = requeue
    with patch.object(gateway,"_operation", return_value=store):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8}, execution_id="original")
        data = {"next":{"page":2}}
        with pytest.raises(gateway.OperationSettlementPending):
            context.defer(delay_seconds=3,reason="awaiting local receipt",data=data)
        data["next"]["page"] = 999
        context.cancellation.request_local()
        with pytest.raises(gateway.OperationSettlementConflict):
            context.finish(gateway.OperationResult.cancelled())
        assert context._settlement_intent.payload["data"]["next"]["page"] == 2
        assert len(calls) == 1
        assert store.calls == []


def test_obligation_declaration_freezes_nested_payload_and_rejects_late_append():
    store = ResultStore()
    store.failed = False
    with patch.object(gateway,"_operation", return_value=store):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8}, execution_id="original")
        payload = {"child":{"run_id":71}}
        context.add_settlement_obligation("completion_dependency",resource_identity="child:71",payload=payload)
        payload["child"]["run_id"] = 99
        context.finish(gateway.OperationResult.success())
        assert context._settlement_intent.obligations[0]["payload"]["child"]["run_id"] == 71
        with pytest.raises(gateway.OperationSettlementConflict):
            context.add_settlement_obligation("completion_dependency",resource_identity="child:99",payload={})


def test_execute_admitted_handoff_uses_callback_barrier_without_eager_permit_release():
    from contextlib import nullcontext
    from core.operations import concurrency, settlement
    from core.runtime import execution_access
    execution = SimpleNamespace(settlement_ticket={"ticket_id":"original"})
    events = []
    with patch.object(concurrency,"execution_scope",return_value=nullcontext()), \
         patch.object(concurrency,"release_execution",side_effect=lambda *a,**k:events.append("unsafe-release")), \
         patch.object(execution_access,"execution_allowed",return_value=True), \
         patch.object(settlement,"callback_started",side_effect=lambda item:events.append("started") or True), \
         patch.object(settlement,"callback_exited",side_effect=lambda item:events.append("exited")), \
         patch.object(settlement,"request_release",side_effect=lambda *a,**k:events.append("handoff")):
        assert gateway.execute_admitted(execution,lambda:events.append("business") or 42) == 42
    assert events == ["started","business","exited","handoff"]


def test_unstarted_rollback_failure_hands_off_and_does_not_release():
    from core.operations import concurrency, settlement
    from core.operations.settlement_contracts import SettlementDomain
    domain = SettlementDomain("offline", "synthetic", "synthetic", "original")
    execution = SimpleNamespace(permit_id="permit",execution_id="execution",execution_key="operation_run:7",
        claimed_run={"id":7,"task_id":8,"run_uuid":"run"},
        settlement_domain=domain,settlement_ticket={"ticket_id":"ticket","permit_id":"permit",
            "execution_id":"execution","run_id":7,"run_uuid":"run","domain_id":"original"})
    calls=[]
    def pending(item,intent,submit):
        calls.append(intent)
        raise gateway.OperationSettlementPending("synthetic offline")
    with patch.object(gateway,"_operation",return_value=ResultStore()), \
         patch.object(concurrency,"release_execution",side_effect=AssertionError("early release")), \
         patch.object(settlement,"settle",side_effect=pending), \
         patch.object(settlement,"callback_exited"), patch.object(settlement,"request_release") as release:
        with pytest.raises(gateway.OperationSettlementPending):
            gateway.rollback_admission(execution)
        assert calls[0].kind == "defer"
        assert calls[0].payload["subtype"] == "unstarted_rollback"
        assert calls[0].origin["permit_id"] == "permit"
        release.assert_called_once()


@pytest.fixture
def participant_registry():
    import time
    from contextlib import ExitStack
    from core.operations import settlement
    from core.storage.operations import settlements
    previous_thread = settlement._THREAD
    assert previous_thread is None or not previous_thread.is_alive()
    assert all(value == 0 for value in settlement.active_counts().values()), settlement.runtime_status()
    assert not settlement._EXPECTED and not settlement._SCAN_BLOCKED
    assert settlement._RESERVATIONS == settlement._SCAN_INFLIGHT == 0
    assert settlement._RESERVATION.get() is None
    with ExitStack() as outer:
        # Preserve the idle caller's lifecycle before the real stop installs
        # its deadline and STOP flags, including when no carrier was created.
        for name in ("_DEADLINE", "_STOP", "_STARTED", "_STOP_WITH_PENDING",
                     "_REGISTRY_ERROR", "_CARRIER_ERROR"):
            outer.enter_context(patch.object(settlement, name, getattr(settlement, name)))
        assert settlement.stop_runtime(time.monotonic()+1)
        stack = outer.enter_context(ExitStack())
        for name, value in (
            ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
            ("_CARRIER_ERROR", ""), ("_DOMAINS", {}), ("_DEADLINE", None),
            ("_THREAD", None), ("_STARTED", False), ("_STOP", False),
            ("_STOP_WITH_PENDING", False), ("_ADMISSION", None),
            ("_SCAN_NEXT", {}), ("_SCAN_FAILURES", {}), ("_SCAN_ERROR", ""),
            ("_SCAN_BLOCKED", {}), ("_SCAN_INFLIGHT", 0), ("_RESERVATIONS", 0),
        ):
            stack.enter_context(patch.object(settlement, name, value))
        yield settlement
        # Close each original synthetic responsibility through its real gate;
        # never erase pending tickets to make lifecycle counts look empty.
        def confirm(intent, **kwargs):
            return {"transition_id":intent.transition_id,"actual_result":gateway.settlement_thaw(intent.payload)}
        with patch.object(settlements,"submit_intent",side_effect=confirm), \
             patch.object(settlements,"mark_cleanup_handoff",return_value=True), \
             patch.object(settlements,"run_cleanup_once",return_value=None), \
             patch.object(settlements,"cleanup_blocks_permit",return_value=False), \
             patch.object(settlement,"_release_execution",side_effect=lambda item,reason,deadline:setattr(item,"released",True) or True):
            for item in list(settlement._REGISTRY.values()):
                assert not item.inflight
                if item.released:
                    continue
                settlement.callback_exited(item.execution)
                if item.intent is None:
                    frozen=gateway.seal_intent(kind="terminal",origin=gateway.settlement_thaw(item.ticket),
                        payload={"status":"attention_required","result_summary":{"synthetic_fixture_exit":True}})
                    settlement.settle(item.execution,frozen,lambda intent,deadline:confirm(intent))
                settlement.request_release(item.execution,reason="synthetic_fixture_exit")
            assert settlement.start_runtime()
            assert settlement.drain_runtime(time.monotonic()+1), settlement.runtime_status()
            assert all(value == 0 for value in settlement.active_counts().values())
            assert not settlement._EXPECTED
            assert settlement.stop_runtime(time.monotonic()+1)
            assert settlement._THREAD is not None and not settlement._THREAD.is_alive()
            assert not settlement._REGISTRY_ERROR and not settlement._CARRIER_ERROR
            assert not settlement._SCAN_BLOCKED
            assert settlement._RESERVATIONS == settlement._SCAN_INFLIGHT == 0


def participant(settlement, *, started=True):
    from core.operations.settlement_contracts import SettlementDomain
    execution = SimpleNamespace(permit_id="permit",execution_id="execution",execution_key="operation_run:7",
        claimed_run={"id":7,"task_id":8,"run_uuid":"run","account_id":9},released=False,
        settlement_domain=SettlementDomain("offline","synthetic","synthetic","original"),
        settlement_ticket={"ticket_id":"ticket","permit_id":"permit","execution_id":"execution",
            "run_id":7,"run_uuid":"run","task_id":8,"domain_id":"original"})
    settlement.register_execution(execution,execution.settlement_ticket)
    if started:
        assert settlement.callback_started(execution)
    return execution


def test_native_participant_pending_retries_only_frozen_storage_and_final_token(participant_registry):
    import time
    from core.storage.operations import settlements
    from tests.operations.test_settlement_leases import LeaseStore
    settlement = participant_registry
    execution = participant(settlement)
    store = LeaseStore()
    calls = []
    healthy = False
    def submit(intent, **kwargs):
        calls.append((intent,kwargs["domain"]))
        if not healthy:
            raise OSError("synthetic unavailable")
        return {"actual_result":{"status":"success","result_summary":{"stored":"actual"}},
                "transition_id":intent.transition_id}
    with patch.object(gateway,"_current_settlement_execution",return_value=execution), \
         patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_domain_scope",return_value=__import__('contextlib').nullcontext()), \
         patch.object(settlements,"submit_intent",side_effect=submit), \
         patch.object(settlements,"mark_cleanup_handoff",return_value=True), \
         patch.object(settlements,"run_cleanup_once",return_value=None), \
         patch.object(settlements,"cleanup_blocks_permit",return_value=False), \
         patch.object(settlement,"_release_execution",side_effect=lambda item,reason,deadline:setattr(item,"released",True) or True):
        context = gateway.OperationHandlerContext(execution.claimed_run,execution_id=execution.execution_id)
        with context.lease(scope_kind="final") as lease:
            pass
        original = {"steps":[{"done":True}]}
        with pytest.raises(gateway.OperationSettlementPending):
            context.finish(gateway.OperationResult.success(original))
        original["steps"][0]["done"] = False
        assert not context.release_lease()
        assert not lease.released
        assert store.deletes == 0
        frozen = context._settlement_intent
        assert frozen.origin["lease_token"] == lease.token
        assert frozen.payload["result_summary"]["steps"][0]["done"] is True
        settlement.callback_exited(execution)
        gateway._handoff_execution(execution)
        healthy = True
        settlement.start_runtime()
        assert settlement.drain_runtime(time.monotonic()+2)
        assert execution.released and lease.released
        assert store.deletes == 0
        assert all(item is frozen and domain is execution.settlement_domain for item,domain in calls)
        # Retry from context is a pure receipt read; actual row determines result.
        context.finish(gateway.OperationResult.success({"steps":[{"done":True}]}))
        assert context.last_result.summary == {"stored":"actual"}


def test_started_callback_can_never_be_unstarted_rollback_even_after_exit(participant_registry):
    settlement = participant_registry
    execution = participant(settlement)
    settlement.callback_exited(execution)
    with pytest.raises(gateway.OperationSettlementConflict):
        gateway.rollback_admission(execution)
    assert settlement.responsibility(execution).intent is None


@pytest.mark.parametrize("late_error", [
    gateway.OperationCancelled("late cancellation"),
    gateway.OperationLeaseLost("late heartbeat"),
    gateway.OperationAccountDeactivated("late account status"),
    PermissionError("late permission"), RuntimeError("late generic catch"),
])
def test_native_handler_late_exception_cannot_replace_frozen_success(late_error):
    from core.operations import concurrency
    store = ResultStore()
    execution = SimpleNamespace(execution_id="original",claimed_run={"id":7,"task_id":8})
    def handler(context):
        try:
            context.finish(gateway.OperationResult.success({"writeback":"confirmed"}))
        except gateway.OperationSettlementPending:
            raise late_error
    with patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_OPERATION_HANDLERS",{"synthetic":handler}), \
         patch.object(concurrency,"current_execution",return_value=execution), \
         patch.object(concurrency,"validate_execution",return_value=True), \
         patch.object(concurrency,"set_execution_state",return_value=True):
        with pytest.raises(gateway.OperationSettlementPending):
            gateway._execute_operation_handler("synthetic",7)
    assert len(store.calls) == 1
    assert store.calls[0]["status"] == "success"


def test_native_handler_preserves_actual_confirmed_success_after_late_cleanup_error():
    from core.operations import concurrency
    store = ResultStore()
    store.failed = False
    execution = SimpleNamespace(execution_id="original",claimed_run={"id":7,"task_id":8})
    def handler(context):
        context.finish(gateway.OperationResult.success({"writeback":"confirmed"}))
        raise RuntimeError("late cleanup failure")
    with patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_OPERATION_HANDLERS",{"synthetic":handler}), \
         patch.object(concurrency,"current_execution",return_value=execution), \
         patch.object(concurrency,"validate_execution",return_value=True), \
         patch.object(concurrency,"set_execution_state",return_value=True):
        result = gateway._execute_operation_handler("synthetic",7)
    assert result["status"] == "success"
    assert result["ok"]
    assert len(store.calls) == 1


@pytest.mark.parametrize("mode",["cancelled","rejected","submit_error","completed"])
def test_dispatch_submit_and_future_boundaries_share_original_responsibility(mode,participant_registry):
    from core.operations import concurrency
    from concurrent.futures import Future
    settlement = participant_registry
    execution = participant(settlement,started=False)
    # This case models admission before any worker callback starts.
    row = {"id":7,"task_type":"synthetic","source_system":"native_operations"}
    future = Future()
    if mode == "cancelled":
        future.cancel()
    elif mode == "completed":
        future.set_result(None)
    class Executor:
        def available_slots(self): return 1
        def try_submit(self,*args):
            if mode == "rejected": return None
            if mode == "submit_error": raise RuntimeError("synthetic executor rejection")
            return future
    store = SimpleNamespace(list_dispatchable_runs=lambda **kwargs:[row])
    with patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_executor",return_value=Executor()), \
         patch.object(gateway,"admit_operation_run",return_value=SimpleNamespace(admitted=True,context=execution)), \
         patch.object(concurrency,"order_dispatch_candidates",side_effect=lambda rows:rows), \
         patch.object(gateway,"rollback_admission") as rollback, \
         patch.object(gateway,"_handoff_execution") as handoff, \
         patch.object(concurrency,"release_execution",side_effect=AssertionError("eager release forbidden")):
        try:
            gateway._dispatch_registered_group({"synthetic":(lambda run_id:None,("native_operations",))},{},None)
        finally:
            gateway.release_dispatch(7)
        if mode == "completed":
            handoff.assert_called_once_with(execution,reason="future_completed")
            rollback.assert_not_called()
        else:
            assert rollback.call_count == 1
            assert rollback.call_args.args == (execution,)
            handoff.assert_not_called()


def test_obligation_is_sanitized_once_before_freeze_and_duplicate_identity():
    store = ResultStore()
    with patch.object(gateway,"_operation",return_value=store):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8},execution_id="original")
        first = context.add_settlement_obligation("completion_dependency",resource_identity="child:71",
            payload={"child_run_id":71,"access_token":"synthetic-private", "password_setup":{"ok":True,"password":"private"}})
        again = context.add_settlement_obligation("completion_dependency",resource_identity="child:71",
            payload={"child_run_id":71,"access_token":"different-private", "password_setup":{"ok":True,"password":"other"}})
        assert first == again
        assert first["payload"] == {"child_run_id":71,"password_setup":{"ok":True}}


def test_defer_uses_authoritative_terminal_receipt_instead_of_claiming_queued():
    store = ResultStore()
    store.requeue_claimed_run = lambda *args,**kwargs:{"status":"cancelled","result_summary":{"cancelled":True}}
    with patch.object(gateway,"_operation",return_value=store):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8},execution_id="original")
        result = context.defer(delay_seconds=1,reason="requested defer")
    assert result["status"] == "cancelled"
    assert context.finished
    assert not context.deferred
    assert context.last_result.status == "cancelled"


def test_participant_failed_step_delete_transfers_exact_handle_before_conservative_submit(participant_registry):
    import time
    from contextlib import nullcontext
    from core.storage.operations import settlements
    from tests.operations.test_settlement_leases import LeaseStore
    settlement = participant_registry
    execution = participant(settlement)
    store = LeaseStore()
    events = []
    def delete(*args):
        events.append("delete")
        if store.failure: raise OSError("unknown step DELETE ACK")
        return True
    store.release_account_lease = delete
    def submit(intent, **kwargs):
        assert store.failure is False
        assert intent.origin["lease_requirement"] == "step_release_unconfirmed"
        events.append("submit")
        return {"actual_result":{"status":"attention_required","result_summary":{
            "reason":"step_lease_release_unconfirmed"}},"transition_id":intent.transition_id}
    with patch.object(gateway,"_current_settlement_execution",return_value=execution), \
         patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_domain_scope",return_value=nullcontext()), \
         patch.object(settlements,"submit_intent",side_effect=submit), \
         patch.object(settlements,"mark_cleanup_handoff",return_value=True), \
         patch.object(settlements,"run_cleanup_once",return_value=None), \
         patch.object(settlements,"cleanup_blocks_permit",return_value=False), \
         patch.object(settlement,"_release_execution",side_effect=lambda item,reason,deadline:setattr(item,"released",True) or True):
        context = gateway.OperationHandlerContext(execution.claimed_run,execution_id=execution.execution_id)
        with pytest.raises(gateway.OperationSettlementPending):
            with context.lease(scope_kind="step"):
                events.append("business-step")
        frozen = context._settlement_intent
        assert frozen is not None
        assert events == ["business-step","delete"]
        assert settlement.responsibility(execution).intent is frozen
        settlement.start_runtime()
        # Active callback still owns the original handle; carrier cannot DELETE.
        assert events == ["business-step","delete"]
        store.failure = False
        settlement.callback_exited(execution)
        gateway._handoff_execution(execution)
        assert settlement.drain_runtime(time.monotonic()+2)
        assert events == ["business-step","delete","delete","submit"]
        assert execution.released


@pytest.mark.parametrize("identity,payload",[("x"*1001,{}),("valid",[])])
def test_invalid_typed_obligation_is_rejected_before_intent_freeze(identity,payload):
    with patch.object(gateway,"_operation",return_value=ResultStore()):
        context = gateway.OperationHandlerContext({"id":7,"task_id":8},execution_id="original")
        with pytest.raises((ValueError,TypeError)):
            context.add_settlement_obligation("completion_dependency",resource_identity=identity,payload=payload)
        assert not context._settlement_obligations
        assert context._settlement_intent is None


@pytest.mark.parametrize("failed_stage",["validate","initial_heartbeat_exception","initial_heartbeat_false"])
def test_scope_entry_failure_seals_unstarted_rollback_and_recovers_without_callback(participant_registry,failed_stage):
    import time
    from core.operations import concurrency
    from core.storage.operations import settlements
    settlement = participant_registry
    execution = participant(settlement,started=False)
    events=[]
    healthy=False
    execution.domain_schema="synthetic"
    execution._domain_url="offline"
    def submit(intent, **kwargs):
        events.append("local-requeue")
        assert intent.kind == "defer"
        assert intent.payload["subtype"] == "unstarted_rollback"
        if not healthy: raise OSError("synthetic persistence offline")
        return {"actual_result":{"status":"queued"},"transition_id":intent.transition_id}
    with patch.object(concurrency,"validate_execution",side_effect=OSError("validation unavailable") if failed_stage == "validate" else None,return_value=True), \
         patch.object(concurrency.permits,"heartbeat",side_effect=OSError("initial heartbeat ACK unavailable") if failed_stage == "initial_heartbeat_exception" else None,return_value=failed_stage != "initial_heartbeat_false"), \
         patch.object(concurrency,"release_execution",side_effect=AssertionError("early release")), \
         patch.object(settlements,"submit_intent",side_effect=submit), \
         patch.object(settlements,"mark_cleanup_handoff",return_value=True), \
         patch.object(settlements,"run_cleanup_once",return_value=None), \
         patch.object(settlements,"cleanup_blocks_permit",return_value=False), \
         patch.object(settlement,"_release_execution",side_effect=lambda item,reason,deadline:setattr(item,"released",True) or events.append("permit-release") or True):
        with pytest.raises(Exception):
            gateway.execute_admitted(execution,lambda:events.append("business"))
        owned=settlement.responsibility(execution)
        assert owned.intent is not None
        assert owned.intent.payload["subtype"] == "unstarted_rollback"
        assert owned.callback_exited
        assert "business" not in events
        assert not execution.released
        healthy=True
        settlement.start_runtime()
        assert settlement.drain_runtime(time.monotonic()+2)
        assert execution.released
        assert "business" not in events
        assert events[-1] == "permit-release"


@pytest.mark.parametrize("late_error",[
    PermissionError("late permission"), gateway.OperationLeaseUnavailable("late acquisition"),
])
def test_confirmed_receipt_wins_over_late_permission_or_lease_business_catch(late_error):
    from core.operations import concurrency
    store=ResultStore()
    store.failed=False
    execution=SimpleNamespace(execution_id="original",claimed_run={"id":7,"task_id":8})
    def handler(context):
        context.finish(gateway.OperationResult.success({"writeback":"confirmed"}))
        raise late_error
    with patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_OPERATION_HANDLERS",{"synthetic":handler}), \
         patch.object(concurrency,"current_execution",return_value=execution), \
         patch.object(concurrency,"validate_execution",return_value=True), \
         patch.object(concurrency,"set_execution_state",return_value=True):
        result=gateway._execute_operation_handler("synthetic",7)
    assert result["status"] == "success"
    assert result["ok"]
    assert len(store.calls) == 1


def test_legacy_runtime_starts_owned_settlement_before_recovery_without_implicit_owner():
    from webui import runtime
    from core.operations import settlement
    from core.runtime import process,execution_access
    from core.storage.operations import bulk
    events=[]
    def recovery(logger):
        events.append("recovery")
        raise RuntimeError("stop synthetic startup before unrelated workers")
    with patch.object(process,"get_runtime_context",return_value=None), \
         patch.object(execution_access,"component_start_allowed",return_value=True), \
         patch.object(runtime,"_runtime_started",False), \
         patch.object(runtime,"_legacy_settlement_started",False), \
         patch.object(runtime,"_legacy_settlement_atexit_registered",False), \
         patch.object(runtime.operation_task_store,"init",side_effect=lambda:events.append("storage")), \
         patch.object(bulk,"init",side_effect=lambda:events.append("bulk")), \
         patch.object(settlement,"start_runtime",side_effect=lambda:events.append("settlement") or True), \
         patch.object(runtime.reconciliation,"recover_before_handlers",side_effect=recovery), \
         patch("atexit.register"):
        with pytest.raises(RuntimeError,match="stop synthetic"):
            runtime.start_runtime()
    assert events == ["storage","bulk","settlement","recovery"]


def test_legacy_runtime_stop_never_reports_clean_while_legacy_producers_remain():
    from webui import runtime
    from core.runtime import process
    with patch.object(process,"get_runtime_context",return_value=None), \
         patch.object(runtime,"_runtime_started",True):
        assert runtime.stop_runtime(timeout=0.01) is False


def test_context_cancellation_uses_original_domain_even_outside_handler_scope():
    from contextlib import nullcontext
    store=ResultStore()
    original=object()
    observed=[]
    with patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_domain_scope",side_effect=lambda domain,**kwargs:observed.append(domain) or nullcontext()):
        context=gateway.OperationHandlerContext({"id":7,"task_id":8},execution_id="original")
        context._domain=original
        assert context.is_cancel_requested(force=True) is False
    assert observed == [original]


def test_registered_midflow_cleanup_failure_freezes_technical_exit_without_business_retry(participant_registry):
    import time
    from contextlib import nullcontext
    from core.operations import concurrency
    from core.storage.operations import settlements
    from tests.operations.test_settlement_leases import LeaseStore
    settlement=participant_registry
    execution=participant(settlement)
    store=LeaseStore()
    store.failure=False
    observed=[]
    healthy=False
    class Cleanup:
        release_confirmed=False
        def release(self, *, deadline=None):
            observed.append("cleanup")
            if not healthy:
                error_type=getattr(gateway,"OperationResourceCleanupPending",gateway.OperationSettlementPending)
                if error_type is gateway.OperationSettlementPending:
                    raise error_type("registered cleanup unavailable")
                raise error_type(cleanup=self,resource_identity="route:original",facts={
                    "operation_stage":"plan_country", "observed_steps":[{"country":"US","ok":True}],
                    "unexecuted_steps":["CA"],"local_business_writeback_confirmed":False})
            self.release_confirmed=True
            return True
    cleanup=Cleanup()
    calls=[]
    def submit(intent,**kwargs):
        calls.append(intent)
        return {"actual_result":{"status":intent.payload["status"],
            "result_summary":gateway.settlement_thaw(intent.payload["result_summary"])},"transition_id":intent.transition_id}
    captured=[]
    def handler(context):
        captured.append(context)
        with context.lease(scope_kind="final"):
            context.register_cleanup(cleanup,key="route:original",blocking=True)
            observed.append("country-US")
            cleanup.release()
            observed.append("country-CA-forbidden")
    with patch.object(concurrency,"current_execution",return_value=execution), \
         patch.object(concurrency,"validate_execution",return_value=True), \
         patch.object(concurrency,"set_execution_state",return_value=True), \
         patch.object(gateway,"_OPERATION_HANDLERS",{"synthetic":handler}), \
         patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_domain_scope",return_value=nullcontext()), \
         patch.object(settlements,"submit_intent",side_effect=submit), \
         patch.object(settlements,"mark_cleanup_handoff",return_value=True), \
         patch.object(settlements,"run_cleanup_once",return_value=None), \
         patch.object(settlements,"cleanup_blocks_permit",return_value=False), \
         patch.object(settlement,"_release_execution",side_effect=lambda item,reason,deadline:setattr(item,"released",True) or True):
        try:
            gateway._execute_operation_handler("synthetic",7)
        except gateway.OperationSettlementPending:
            pass
        context=captured[0]
        assert context._settlement_intent is not None
        frozen=context._settlement_intent
        assert frozen.payload["status"] == "attention_required"
        summary=frozen.payload["result_summary"]
        assert summary["outcome"] == "resource_cleanup_pending"
        assert summary["cause_code"] == "resource_release_unconfirmed"
        assert summary["observed_steps"][0]["country"] == "US"
        assert summary["unexecuted_steps"] == ("CA",)
        assert summary["automatic_business_retry"] is False
        assert "request_unknown" not in str(summary)
        assert "country-CA-forbidden" not in observed
        assert len(captured) == 1
        settlement.callback_exited(execution)
        gateway._handoff_execution(execution)
        healthy=True
        settlement.start_runtime()
        assert settlement.drain_runtime(time.monotonic()+2)
        assert execution.released and cleanup.release_confirmed
        assert len(calls) == 1 and calls[0] is frozen
        assert observed.count("country-US") == 1


def test_unregistered_cleanup_signal_cannot_create_terminal_authority():
    error_type=getattr(gateway,"OperationResourceCleanupPending",None)
    assert error_type is not None
    with patch.object(gateway,"_operation",return_value=ResultStore()):
        context=gateway.OperationHandlerContext({"id":7,"task_id":8},execution_id="original")
        error=error_type(cleanup=object(),resource_identity="not-owned",facts={})
        with pytest.raises(gateway.OperationSettlementFenced):
            context.finish_cleanup_failure(error)
        assert context._settlement_intent is None


def test_plain_pending_without_exact_cleanup_is_never_guessed_into_terminal():
    from core.operations import concurrency
    store=ResultStore()
    execution=SimpleNamespace(execution_id="original",claimed_run={"id":7,"task_id":8})
    captured=[]
    def handler(context):
        captured.append(context)
        raise gateway.OperationSettlementPending("untyped unavailable")
    with patch.object(gateway,"_operation",return_value=store), \
         patch.object(gateway,"_OPERATION_HANDLERS",{"synthetic":handler}), \
         patch.object(concurrency,"current_execution",return_value=execution), \
         patch.object(concurrency,"validate_execution",return_value=True), \
         patch.object(concurrency,"set_execution_state",return_value=True):
        with pytest.raises(gateway.OperationSettlementPending):
            gateway._execute_operation_handler("synthetic",7)
    assert captured[0]._settlement_intent is None
    assert store.calls == []


def test_cleanup_control_facts_are_frozen_and_sanitized_without_private_payload():
    handle=object()
    facts={"observed_steps":[{"country":"US","ok":True}],"access_token":"synthetic-private"}
    signal=gateway.OperationResourceCleanupPending(cleanup=handle,resource_identity="route:original",facts=facts)
    facts["observed_steps"][0]["ok"]=False
    assert signal.facts["observed_steps"][0]["ok"] is True
    assert "access_token" not in signal.facts
    assert "synthetic-private" not in str(signal)


def test_registered_key_with_wrong_cleanup_object_cannot_seal_or_release(participant_registry):
    from core.operations import settlement
    execution=participant(participant_registry)
    with patch.object(gateway,"_current_settlement_execution",return_value=execution), \
         patch.object(gateway,"_operation",return_value=ResultStore()):
        context=gateway.OperationHandlerContext(execution.claimed_run,execution_id=execution.execution_id)
        original=SimpleNamespace(release=lambda **kwargs:True)
        context.register_cleanup(original,key="route:original")
        error=gateway.OperationResourceCleanupPending(cleanup=object(),resource_identity="route:original")
        with pytest.raises(gateway.OperationSettlementFenced):
            context.finish_cleanup_failure(error)
        assert context._settlement_intent is None
        assert not execution.released
        assert settlement.responsibility(execution).intent is None


@pytest.mark.parametrize("confirmed",[False,True])
def test_cleanup_control_preserves_preexisting_original_success_intent(confirmed):
    store=ResultStore()
    store.failed=not confirmed
    with patch.object(gateway,"_operation",return_value=store):
        context=gateway.OperationHandlerContext({"id":7,"task_id":8},execution_id="original")
        if confirmed:
            context.finish(gateway.OperationResult.success({"stored":"known"}))
        else:
            with pytest.raises(gateway.OperationSettlementPending):
                context.finish(gateway.OperationResult.success({"stored":"known"}))
        original=context._settlement_intent
        error=gateway.OperationResourceCleanupPending(cleanup=object(),resource_identity="unknown")
        if confirmed:
            result=context.finish_cleanup_failure(error)
            assert result["status"] == "success"
        else:
            with pytest.raises(gateway.OperationSettlementPending):
                context.finish_cleanup_failure(error)
        assert context._settlement_intent is original
        assert context._settlement_intent.payload["status"] == "success"
        assert len(store.calls) == 1


def test_cleanup_technical_exit_keeps_preexisting_stored_remote_safety_classification(participant_registry):
    settlement=participant_registry
    execution=participant(settlement)
    execution.claimed_run["result_summary"]={"outcome":"request_unknown","reconcile_required":True,
        "completed_steps":["saved-step"]}
    from core.storage.operations import settlements
    with patch.object(gateway,"_current_settlement_execution",return_value=execution), \
         patch.object(gateway,"_operation",return_value=ResultStore()), \
         patch.object(settlements,"submit_intent",side_effect=lambda intent,**kwargs:{
             "actual_result":{"status":intent.payload["status"],
                "result_summary":gateway.settlement_thaw(intent.payload["result_summary"])},
             "transition_id":intent.transition_id}):
        context=gateway.OperationHandlerContext(execution.claimed_run,execution_id=execution.execution_id)
        cleanup=SimpleNamespace(release=lambda **kwargs:True)
        context.register_cleanup(cleanup,key="route:original")
        context.finish_cleanup_failure(gateway.OperationResourceCleanupPending(
            cleanup=cleanup,resource_identity="route:original",facts={"unexecuted_steps":["next"]}))
        summary=context._settlement_intent.payload["result_summary"]
        assert summary["outcome"] == "request_unknown"
        assert summary["reconcile_required"] is True
        assert summary["completed_steps"] == ("saved-step",)
        assert summary["cause_code"] == "resource_release_unconfirmed"
