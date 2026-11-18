"""Offline regressions for the native extraction/payment settlement seam."""
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from core.extract_link import independent_payment as payment
from core.extract_link import service
from core.extract_link.contracts import ProviderJob
from core.operations.settlement_contracts import (
    OperationSettlementConflict,
    OperationSettlementFenced,
    OperationSettlementPending,
)
from tests.extract_link import test_extract_link_provider_flow as fixtures


@contextmanager
def provider_case(job=None):
    fixture = fixtures.ExtractLinkTerminalFailureFlowTests()
    with fixture._scenario(failed_job=job or ProviderJob(
        job_id="synthetic-original", extraction_state="succeeded",
        links=("https://example.test/material",),
    )) as case:
        yield case


@pytest.mark.parametrize("control", [
    OperationSettlementPending, OperationSettlementConflict, OperationSettlementFenced,
])
def test_provider_finish_control_does_not_rewrite_result_or_repeat_finish(control):
    with provider_case() as case:
        case.context.finish.side_effect = control("synthetic settlement control")
        with pytest.raises(control):
            service._handle_provider_operation(case.context)
        assert case.context.finish.call_count == 1
        assert case.save_account.call_count == 1
        assert case.save_account.call_args.args[1]["status"] == "success"
        case.provider.create_job.assert_called_once()


def test_provider_defer_ack_loss_does_not_requeue_or_query_twice():
    job = ProviderJob(job_id="synthetic-original", extraction_state="running", payment_state="pending")
    with provider_case(job) as case:
        case.context.run["data"].update(provider_id="legacy", mode="auto_payment", link_type="upi")
        case.context.defer = Mock(side_effect=OperationSettlementPending("synthetic lost defer ACK"))
        with pytest.raises(OperationSettlementPending):
            service._handle_provider_operation(case.context)
        assert case.context.defer.call_count == 1
        case.provider.create_job.assert_called_once()
        case.context.finish.assert_not_called()


def test_provider_standalone_scope_is_explicitly_final():
    with provider_case() as case:
        case.context.lease = Mock(return_value=nullcontext())
        service._handle_provider_operation(case.context)
        assert case.context.lease.call_args.kwargs["scope_kind"] == "final"


def test_extraction_proxy_forces_step_scope_and_never_finishes_main_run():
    context = SimpleNamespace(
        run={"data": {"mode": "auto_payment", "payment_source": "xxsyun"}},
        finish=Mock(), lease=Mock(return_value=nullcontext()),
    )
    proxy = payment.ExtractionContext(context)
    with proxy.lease(resource_family="openai_interactive"):
        proxy.finish(status="success", result_summary={"extraction_status": "succeeded"})
    assert context.lease.call_args.kwargs["scope_kind"] == "step"
    context.finish.assert_not_called()
    assert proxy.result["status"] == "success"


def test_step_release_unknown_does_not_enter_payment_or_finish_main_run():
    scopes = []
    context = SimpleNamespace(
        task_id=11, run_id=22, account_id=33, run={"data": {"provider_id": "lumen_flow"}},
        finish=Mock(),
    )

    @contextmanager
    def lease(**kwargs):
        scopes.append(kwargs.get("scope_kind"))
        yield None
        raise OperationSettlementPending("synthetic release transport unknown")

    context.lease = lease

    def extract(proxy, **_kwargs):
        with proxy.lease(resource_family="openai_interactive"):
            proxy.finish(status="success")

    provider = SimpleNamespace(_handle_provider_operation=extract)
    with patch.object(payment.payments, "get_task_payment_order", return_value=None), \
            patch.object(payment, "_saved_extraction", return_value={}), \
            patch.object(payment, "_execute_payment") as execute:
        with pytest.raises(OperationSettlementPending):
            payment.handle(context, provider)
    assert scopes == ["step"]
    execute.assert_not_called()
    context.finish.assert_not_called()


def test_independent_payment_phase_is_explicitly_final():
    context = SimpleNamespace(
        task_id=11, run_id=22, account_id=33, run={"data": {}},
        lease=Mock(return_value=nullcontext()),
    )
    with patch.object(payment.payments, "get_task_payment_order", return_value={"payment_state": "pending"}), \
            patch.object(payment, "_saved_extraction", return_value={}), \
            patch.object(payment, "_execute_payment"):
        payment.handle(context, Mock())
    assert context.lease.call_args.kwargs["scope_kind"] == "final"


def test_extraction_resource_cleanup_unknown_does_not_enter_payment():
    context = SimpleNamespace(
        task_id=11, run_id=22, account_id=33, run={"data": {"provider_id": "huanguang"}},
        lease=Mock(return_value=nullcontext()), finish=Mock(),
    )

    def extract(proxy):
        proxy._extract_proxy_cleanup_handles = {
            "original-proxy": SimpleNamespace(release_confirmed=False),
        }
        proxy.finish(status="success")

    with patch.object(payment.payments, "get_task_payment_order", return_value=None), \
            patch.object(payment, "_saved_extraction", return_value={}), \
            patch.object(payment, "_execute_payment") as execute:
        with pytest.raises(OperationSettlementPending):
            payment.handle(context, SimpleNamespace(_handle_provider_operation=extract))
    execute.assert_not_called()
    context.finish.assert_called_once()
    result = context.finish.call_args.kwargs
    assert result["status"] == "attention_required"
    assert result["result_summary"]["payment_status"] == "not_started"
    assert result["result_summary"]["automatic_business_retry"] is False


def test_independent_plus_inline_control_is_transparent():
    context = SimpleNamespace(
        account_id=33, email="synthetic@example.test", checkpoint=Mock(), report=Mock(), finish=Mock(), defer=Mock(),
    )
    order = {"id": 1, "submitted_at": None, "summary": {}}
    state = {}
    with patch.object(service, "_bool_setting", return_value=True), \
            patch.object(payment.db, "get_account", return_value={}), \
            patch.object(payment.jobs, "independent_plus_is_confirmed", return_value=False), \
            patch.object(payment, "_save_state") as save, \
            patch.object(payment, "_update") as update, \
            patch("core.accounts.plans.service.run_account_plan_check_inline",
                  side_effect=OperationSettlementPending("synthetic inline cleanup")):
        with pytest.raises(OperationSettlementPending):
            payment._verify_plus(context, service, {}, state, order, SimpleNamespace(poll_interval=10))
    save.assert_called_once()
    update.assert_not_called()
    context.finish.assert_not_called()
    context.defer.assert_not_called()


def test_legacy_failure_writeback_precedes_terminal_freeze():
    context = SimpleNamespace(
        checkpoint=Mock(), report=Mock(), finish=Mock(),
    )
    writes = []
    context.finish.side_effect = lambda **kwargs: writes.append(("finish", kwargs["status"]))
    with patch.object(service.db, "mark_account_extract_running", return_value=True), \
            patch.object(service.db, "update_account_extract",
                         side_effect=lambda *args, **kwargs: writes.append(("writeback", args[1]["status"]))), \
            patch.object(service, "_bool_setting", return_value=False), \
            patch.object(service, "_ensure_extract_token", side_effect=ValueError("synthetic preflight failed")):
        service._run_extract(
            account_id=33, email="synthetic@example.test", access_token="", link_type="upi",
            cdk="synthetic", trigger="synthetic", operation_context=context, release_queue_slot=False,
        )
    assert writes == [("writeback", "failed"), ("finish", "failed")]


def test_proxy_release_failure_keeps_failed_resource_pending():
    context = SimpleNamespace(release_resource=Mock())
    leases = [SimpleNamespace(lease_id="good"), SimpleNamespace(lease_id="unknown")]

    def release(lease, **_kwargs):
        if lease.lease_id == "unknown":
            raise OSError("synthetic physical release unknown")

    with patch("core.proxy.provider.release_proxy", side_effect=release):
        service._release_huanguang_proxies(context, leases, [91, 92], terminal=True)
    assert [call.args[0] for call in context.release_resource.call_args_list] == [91]


def test_proxy_cleanup_retries_exact_failed_handle_and_resource_once():
    context = SimpleNamespace(release_resource=Mock(), register_cleanup=Mock())
    lease = SimpleNamespace(lease_id="original")
    with patch("core.proxy.provider.release_proxy", side_effect=[
            OSError("synthetic release ACK unknown"), None,
    ]) as release:
        service._release_huanguang_proxies(context, [lease], [91], terminal=True)
        handle = context.register_cleanup.call_args.args[0]
        assert not handle.release_confirmed
        context.release_resource.assert_not_called()
        assert handle.release()
        assert handle.release()
    assert release.call_count == 2
    assert all(call.args[0] is lease for call in release.call_args_list)
    context.release_resource.assert_called_once_with(91, state="released")


def test_proxy_cleanup_declares_exact_durable_identity_when_physical_unknown():
    context = SimpleNamespace(release_resource=Mock(), register_cleanup=Mock(), add_settlement_obligation=Mock())
    lease = SimpleNamespace(lease_id="original", metadata={"extract_resource_uuid": "original-resource-uuid"})
    with patch("core.proxy.provider.release_proxy", side_effect=OSError("synthetic physical ACK unknown")):
        service._release_huanguang_proxies(context, [lease], [91], terminal=True)
    context.release_resource.assert_not_called()
    context.add_settlement_obligation.assert_called_once_with(
        "resource_release", resource_identity="original-resource-uuid", blocks_permit=True,
        payload={"resource_id": 91, "resource_uuid": "original-resource-uuid", "external_id": "original"},
    )


def test_restored_proxy_from_prior_run_remains_pending_without_transfer():
    from core.storage.operations import common

    context = SimpleNamespace(run_id=22, release_resource=Mock(), register_cleanup=Mock(),
                              add_settlement_obligation=Mock())
    lease = SimpleNamespace(lease_id="original", metadata={
        "extract_resource_uuid": "original-resource-uuid", "extract_restored_reference": True,
    })
    conn = MagicMock()
    conn.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = {
        "run_id": 21, "resource_uuid": "original-resource-uuid", "external_id": "original",
    }
    with patch.object(common, "_connect", return_value=conn), \
            patch("core.proxy.provider.release_proxy") as physical:
        service._release_huanguang_proxies(context, [lease], [91], terminal=True)
    handle = context.register_cleanup.call_args.args[0]
    assert not handle.release_confirmed
    physical.assert_not_called()
    context.release_resource.assert_not_called()
    context.add_settlement_obligation.assert_not_called()


def test_post_payment_followup_is_declared_before_freeze_without_enqueue():
    job = ProviderJob(
        job_id="synthetic-original", extraction_state="succeeded", payment_state="succeeded",
        links=("https://example.test/material",),
    )
    order = []
    with provider_case(job) as case:
        case.context.run["data"]["mode"] = "manual_payment"
        case.context.add_settlement_obligation = Mock(
            side_effect=lambda *args, **kwargs: order.append(("obligation", args, kwargs)),
        )
        case.context.finish.side_effect = lambda **kwargs: order.append(("finish", kwargs))
        case.save_job.return_value = {"updated_at": "2026-11-17T00:00:00+00:00"}
        with patch.object(service, "_bool_setting",
                          side_effect=lambda key, default=False: key == "EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED"), \
                patch.object(service, "_payment_aftercare", return_value=("skipped", "", False)), \
                patch.object(service, "_reconcile_huanguang_automatic_payment", return_value=False), \
                patch("core.accounts.plans.service.enqueue_account_plan_check") as enqueue:
            service._handle_provider_operation(case.context)
    enqueue.assert_not_called()
    assert [item[0] for item in order] == ["obligation", "finish"], order
    obligation = order[0][2]
    assert obligation["resource_identity"] == "extract-workbench:810:payment-success"
    assert obligation["blocks_permit"] is False
    assert obligation["payload"]["trigger"] == "extract_post_payment"
    assert obligation["payload"]["expected_provider_updated_at"] == "2026-11-17T00:00:00+00:00"
    assert "access_token" not in repr(obligation)


def followup_payload():
    return {
        "action_kind": "extract_plan_verify",
        "task_id": 11, "run_id": 22, "account_id": 33, "provider_id": "lumen_flow",
        "expected_provider_updated_at": "2026-11-17T00:00:00+00:00",
        "trigger": "extract_post_payment", "idempotency_key": "extract-workbench:11:payment-success",
    }


def test_followup_lost_owner_does_not_read_account_or_enqueue():
    with patch("core.runtime.execution_access.execution_allowed", return_value=False), \
            patch.object(service.db, "get_account") as account, \
            patch.object(service, "_followup_snapshot") as snapshot, \
            patch("core.accounts.plans.service.enqueue_account_plan_check") as enqueue:
        assert service.apply_settlement_followup(followup_payload()) is False
    account.assert_not_called()
    snapshot.assert_not_called()
    enqueue.assert_not_called()


def test_followup_newer_run_or_provider_version_never_enqueues():
    with patch("core.runtime.execution_access.execution_allowed", return_value=True), \
            patch.object(service, "_followup_snapshot", return_value=None), \
            patch.object(service.db, "get_account") as account, \
            patch("core.accounts.plans.service.enqueue_account_plan_check") as enqueue:
        assert service.apply_settlement_followup(followup_payload())
    account.assert_not_called()
    enqueue.assert_not_called()


def test_followup_parent_superseded_before_enqueue_does_not_enqueue():
    with patch("core.runtime.execution_access.execution_allowed", return_value=True), \
            patch.object(service, "_followup_snapshot", side_effect=[{}, None]), \
            patch.object(service, "_settlement_account_snapshot", return_value={"access_token": "synthetic"}), \
            patch.object(service, "_write_followup_state") as write, \
            patch("core.accounts.plans.service.enqueue_account_plan_check") as enqueue:
        assert service.apply_settlement_followup(followup_payload())
    enqueue.assert_not_called()
    write.assert_not_called()


def test_followup_uses_original_trigger_and_idempotency_without_remote_action():
    with patch("core.runtime.execution_access.execution_allowed", return_value=True), \
            patch.object(service, "_followup_snapshot", return_value={}), \
            patch.object(service, "_settlement_account_snapshot", return_value={
                "email": "synthetic@example.test", "access_token": "synthetic-local-only",
            }), \
            patch.object(service, "_write_followup_state", return_value=True) as write, \
            patch.object(service, "_settlement_enqueue_plan", return_value={"accepted": True}) as enqueue:
        assert service.apply_settlement_followup(followup_payload())
    enqueue.assert_called_once()
    assert enqueue.call_args.args[1]["email"] == "synthetic@example.test"
    assert enqueue.call_args.args[2] == "synthetic-local-only"
    assert write.call_args.kwargs["plus_status"] == "pending"


def test_typed_followup_does_not_enter_legacy_db_init_or_facade():
    payload = followup_payload()
    with patch("core.runtime.execution_access.execution_allowed", return_value=True), \
            patch.object(service, "_followup_snapshot", return_value={}), \
            patch.object(service, "_settlement_account_snapshot", return_value={
                "email": "synthetic@example.test", "access_token": "synthetic-local-only",
            }), \
            patch.object(service, "_settlement_enqueue_plan", return_value={"accepted": True}), \
            patch.object(service, "_write_followup_state", return_value=True), \
            patch.object(service.db, "get_account", side_effect=AssertionError("legacy db facade")), \
            patch("core.storage.records.init", side_effect=AssertionError("row-store init")), \
            patch("core.accounts.plans.service.enqueue_account_plan_check",
                  side_effect=AssertionError("legacy enqueue facade")):
        assert service.apply_settlement_followup(payload)


def test_settlement_enqueue_uses_frozen_snapshot_and_native_gateway_only():
    payload = {
        **followup_payload(),
        "config_snapshot": {
            "PLAN_CHECK_COUNTRIES": ["IN"],
            "ACCOUNT_PLAN_CHECK_PROXY_MODE": "pool",
            "PLAN_CHECK_TIMEOUT": 15,
        },
    }
    account = {"email": "synthetic@example.test"}
    with patch("core.accounts.plans.service.register_operation_handlers") as register, \
            patch.object(service, "_settlement_claim_plan", return_value=True), \
            patch.object(service.account_task_store, "submit_durable_operation",
                         return_value={"accepted": True, "reused": False}) as submit:
        result = service._settlement_enqueue_plan(payload, account, "synthetic-local-only")
    assert result["accepted"] is True
    register.assert_called_once()
    submit.assert_called_once()
    kwargs = submit.call_args.kwargs
    assert kwargs["idempotency_key"] == payload["idempotency_key"]
    assert kwargs["config_snapshot"] == payload["config_snapshot"]
    assert kwargs["data"]["countries"] == ["IN"]
    assert kwargs["data"]["proxy_source"] == "pool"


def test_settlement_followup_deadline_stops_before_any_account_read():
    with patch.object(service, "_settlement_account_snapshot",
                      side_effect=AssertionError("account read after expired deadline")):
        assert service.apply_settlement_followup(
            followup_payload(), deadline=0.0,
        ) is False


def test_settlement_account_snapshot_uses_original_base_schema_without_init():
    from core.operations.settlement_contracts import SettlementDomain
    from core.storage import postgres, records
    from core.storage.operations import common

    domain = SettlementDomain(
        database_url="postgresql://synthetic/original",
        operation_schema="test_original_operation", permit_schema="test_original_accounts",
        domain_id="synthetic-split-domain",
    )
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {
        "id": 33, "email": "synthetic@example.test", "deactivated": False,
        "data": {"access_token": "synthetic-original-token"},
    }
    with common.settlement_scope(domain, conn=connection), \
            patch.dict("os.environ", {
                "DATABASE_URL": "postgresql://synthetic/drifted",
                "TURB_DB_SCHEMA": "test_drifted_accounts",
                "OPERATION_TASK_DB_SCHEMA": "test_drifted_operation",
            }), \
            patch.object(records, "init", side_effect=AssertionError("unexpected record initialization")), \
            patch.object(postgres, "connect", side_effect=AssertionError("unexpected outside connection")):
        account = service._settlement_account_snapshot(followup_payload())
    sql = cursor.execute.call_args.args[0]
    assert '"test_original_accounts"."registered_accounts"' in sql
    assert '"test_original_operation"."registered_accounts"' not in sql
    assert "test_drifted" not in sql
    assert account["access_token"] == "synthetic-original-token"


def test_settlement_native_enqueue_reuses_original_child_without_record_init():
    """Exercise the real service -> gateway -> runtime idempotency path."""
    from core.operations.settlement_contracts import SettlementDomain
    from core.storage import postgres, records
    from core.storage.operations import common

    domain = SettlementDomain(
        database_url="postgresql://synthetic/original",
        operation_schema="test_original_operation", permit_schema="test_original_accounts",
        domain_id="synthetic-split-domain",
    )
    payload = {**followup_payload(), "config_snapshot": {"PLAN_CHECK_COUNTRIES": ["IN"]}}
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        {"id": 33, "email": "synthetic@example.test", "data": {"access_token": "synthetic"}},
        {"id": 44, "source_system": "native_operations", "status": "queued", "data": {}},
        {"id": 55, "task_id": 44, "status": "queued", "data": {}},
    ]
    with common.settlement_scope(domain, conn=connection), \
            patch.object(records, "init", side_effect=AssertionError("unexpected record initialization")), \
            patch.object(postgres, "connect", side_effect=AssertionError("unexpected outside connection")), \
            patch.object(service.account_task_store, "notify_dispatch",
                         side_effect=AssertionError("reused child must not notify")):
        result = service._settlement_enqueue_plan(
            payload, {"email": "synthetic@example.test"}, "synthetic-local-token",
        )
    assert result["accepted"] is True
    assert result["reused"] is True
    assert (result["task_id"], result["run_id"]) == (44, 55)
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert '"test_original_accounts"."registered_accounts"' in statements[0]
    assert any('"test_original_operation"."operation_tasks"' in sql for sql in statements)
    assert any('"test_original_operation"."operation_runs"' in sql for sql in statements)
    assert all("INSERT" not in sql.upper() and "CREATE " not in sql.upper() for sql in statements)


@pytest.mark.parametrize("reused,claimed,accepted", [
    (False, True, True), (False, False, False), (True, False, True),
])
def test_initialized_enqueue_preserves_original_claim_and_cancel(reused, claimed, accepted):
    submitted = {"accepted": True, "busy": reused, "reused": reused,
                 "task_id": 44, "run_id": 55, "status": "queued"}
    with patch.object(service.account_task_store, "submit_durable_operation", return_value=submitted), \
            patch.object(service, "_settlement_claim_plan", create=True, return_value=claimed) as claim, \
            patch("core.accounts.plans.service._cancel_unclaimed_native_run") as cancel:
        result = service._settlement_enqueue_plan(
            followup_payload(), {"email": "synthetic@example.test"}, "synthetic",
        )
    assert result["accepted"] is accepted
    assert result["busy"] is (not accepted)
    if reused:
        claim.assert_not_called()
        cancel.assert_not_called()
    else:
        claim.assert_called_once()
        if claimed:
            cancel.assert_not_called()
        else:
            cancel.assert_called_once_with(55)


def test_post_payment_followup_captures_original_plan_config_before_freeze():
    captured = []
    context = SimpleNamespace(
        task_id=11, run_id=22, account_id=33, config_snapshot={"driver": "extract-alias"},
        add_settlement_obligation=lambda *args, **kwargs: captured.append(kwargs),
    )
    snapshot = SimpleNamespace(revision=7, as_dict=lambda: {
        "PLAN_CHECK_COUNTRIES": ["IN"], "PLAN_CHECK_TIMEOUT": 23,
        "EXTRACT_LINK_CDK": "synthetic-must-not-save",
    })
    with patch("core.accounts.plans.service.get_config_snapshot", return_value=snapshot):
        service._declare_post_payment_followup(
            context, provider_id="lumen_flow", saved={"updated_at": "2026-11-17T00:00:00+00:00"},
        )
    values = captured[0]["payload"]["config_snapshot"]
    assert values["PLAN_CHECK_COUNTRIES"] == ["IN"]
    assert values["PLAN_CHECK_TIMEOUT"] == 23
    assert values["config_snapshot_revision"] == 7
    assert "EXTRACT_LINK_CDK" not in values


def test_initialized_plan_claim_reuses_original_guard_in_base_schema_no_init():
    from core.operations.settlement_contracts import SettlementDomain
    from core.storage import postgres, records
    from core.storage.operations import common

    domain = SettlementDomain(
        database_url="postgresql://synthetic/original",
        operation_schema="test_original_operation", permit_schema="test_original_accounts",
        domain_id="synthetic-split-domain",
    )
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"id": 33}
    original_guard = service.db._stage_claim_guard
    with common.settlement_scope(domain, conn=connection), \
            patch.object(records, "init", side_effect=AssertionError("unexpected record initialization")), \
            patch.object(postgres, "connect", side_effect=AssertionError("unexpected outside connection")), \
            patch.object(service.db, "_stage_claim_guard", wraps=original_guard) as guard:
        assert service._settlement_claim_plan(followup_payload())
    guard.assert_called_once_with("plan_check")
    sql, params = cursor.execute.call_args.args
    assert '"test_original_accounts"."registered_accounts"' in sql
    assert '"test_original_operation"."registered_accounts"' not in sql
    assert '"plan_check_status" = %s' in sql
    assert "data->>'plan_check_deadline_at'" in sql
    assert "extract_post_payment" in repr(params)
    assert "plan_check_queued_at" in repr(params)


def test_native_step_delete_unknown_stops_payment_with_original_handle():
    from core.operations import task_gateway as gateway

    store = SimpleNamespace(
        is_run_cancel_requested=Mock(return_value=False),
        acquire_account_lease=Mock(return_value="original-token"),
        heartbeat_run=Mock(return_value=True),
        release_account_lease=Mock(side_effect=OSError("synthetic DELETE ACK unknown")),
    )
    with patch.object(gateway, "_operation", return_value=store):
        context = gateway.OperationHandlerContext(
            {"id": 22, "task_id": 11, "account_id": 33, "data": {"provider_id": "lumen_flow"}},
            execution_id="synthetic-original-execution",
        )

        def extract(proxy):
            with proxy.lease(resource_family="openai_interactive", scope_kind="final"):
                proxy.finish(status="success")

        with patch.object(payment.payments, "get_task_payment_order", return_value=None), \
                patch.object(payment, "_saved_extraction", return_value={}), \
                patch.object(payment, "_execute_payment") as execute:
            with pytest.raises(OperationSettlementPending):
                payment.handle(context, SimpleNamespace(_handle_provider_operation=extract))
        assert context._lease.scope_kind == "step"
        assert not context._lease.released
        assert context._lease.token == "original-token"
        assert len(context._leases) == 1
        assert not context.finished
        execute.assert_not_called()
        store.release_account_lease.side_effect = None
        store.release_account_lease.return_value = True
        context.release_lease()


@pytest.mark.parametrize("defer", [False, True])
def test_native_context_freezes_original_provider_transition_once(defer):
    from core.operations import task_gateway as gateway
    from core.operations.settlement_contracts import thaw

    job = ProviderJob(
        job_id="synthetic-original",
        extraction_state="running" if defer else "succeeded",
        payment_state="pending" if defer else "not_started",
        links=() if defer else ("https://example.test/material",),
    )
    store = SimpleNamespace(
        is_run_cancel_requested=Mock(return_value=False),
        acquire_account_lease=Mock(return_value="original-final-token"),
        heartbeat_run=Mock(return_value=True), release_account_lease=Mock(return_value=True),
        finish_run=Mock(side_effect=OSError("synthetic terminal ACK unknown")),
        requeue_claimed_run=Mock(side_effect=OSError("synthetic defer ACK unknown")),
    )
    with provider_case(job) as case, patch.object(gateway, "_operation", return_value=store):
        run = {
            "id": 811, "task_id": 810, "account_id": 77,
            "data": dict(case.context.run["data"]),
        }
        if defer:
            run["data"].update(provider_id="legacy", mode="auto_payment", link_type="upi")
        context = gateway.OperationHandlerContext(run, execution_id="synthetic-original-execution")
        context.report = case.context.report
        context.remote_request_started = Mock()
        context.remote_request_receipt = Mock()
        try:
            with pytest.raises(OperationSettlementPending):
                service._handle_provider_operation(context)
            frozen = context._settlement_intent
            assert frozen.kind == ("defer" if defer else "terminal")
            assert context._settlement_receipt is None
            assert not context.finished
            assert context._leases[0].scope_kind == "final"
            case.provider.create_job.assert_called_once()
            if defer:
                assert store.requeue_claimed_run.call_count == 1
                store.finish_run.assert_not_called()
            else:
                assert store.finish_run.call_count == 1
                assert thaw(frozen.payload)["status"] == "success"
                assert case.save_account.call_count == 1
                assert case.save_account.call_args.args[1]["status"] == "success"
                store.requeue_claimed_run.assert_not_called()
        finally:
            for lease in context._leases:
                if not lease.released:
                    lease.release()
