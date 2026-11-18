"""S03 native checkpoint safety; offline by default, PG only by root opt-in.

The loopback remote is an in-process synthetic call ledger. It represents no
password, token, account, payment, or real external business result.
"""
from __future__ import annotations

import copy
import os
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.operations import task_gateway as gateway
from core.storage.operations import recovery


ACTION = "synthetic_loopback_write"
REQUEST = "s03-original-request"
CASES = (
    ("not_sent", 0, "not_submitted", "failed", "interrupted"),
    ("sent_no_ack", 1, "unknown", "request_unknown", "attention_required"),
    ("remote_confirmed_receipt_write_failed", 1, "started", "request_unknown", "attention_required"),
)


class LoopbackRemote:
    def __init__(self):
        self.calls = []

    def send(self, *, ack: bool):
        self.calls.append(REQUEST)
        if not ack:
            raise TimeoutError("synthetic remote accepted; ACK unavailable")
        return {"synthetic_remote_confirmed": True}


class OfflineCheckpointRepository:
    """Repository seam records method calls; context/intent logic stays native."""
    def __init__(self):
        self.data = {}
        self.starts = self.receipts = self.checkpoints = self.finishes = 0
        self.fail_receipt = False
        self.fail_terminal = True
        self.snapshots = []

    def is_run_cancel_requested(self, *args):
        self.checkpoints += 1
        return False

    def record_remote_intent(self, run_id, **kwargs):
        self.starts += 1
        self.data["remote_intent"] = {
            "kind": kwargs["intent_kind"], "action": kwargs["action"],
            "request_id": kwargs["request_id"], "receipt_state": "started",
        }
        return {"id": run_id, "data": copy.deepcopy(self.data)}

    def record_remote_receipt(self, run_id, **kwargs):
        self.receipts += 1
        if self.fail_receipt:
            raise OSError("synthetic receipt transaction rolled back")
        state = kwargs.get("receipt_state") or kwargs["outcome"]
        self.data["remote_intent"]["receipt_state"] = state
        self.data["remote_receipt"] = {"receipt_state": state, "detail": kwargs["detail"]}
        return {"id": run_id, "data": copy.deepcopy(self.data)}

    def finish_run(self, run_id, **kwargs):
        self.finishes += 1
        self.snapshots.append(copy.deepcopy(kwargs))
        if self.fail_terminal:
            raise OSError("synthetic terminal storage unavailable")
        return {"id": run_id, "status": kwargs["status"], "result_summary": kwargs["result_summary"]}


def exercise_once(context, remote, mode):
    """Explicit synthetic adapter invokes native boundaries exactly once."""
    context.checkpoint()
    context.remote_request_started(ACTION, request_id=REQUEST, detail={"synthetic": True})
    if mode == "not_sent":
        context.remote_request_receipt(
            outcome="not_submitted", action=ACTION, request_id=REQUEST,
            detail={"mutation_submitted": False, "action_dispatched": False},
        )
        return gateway.OperationResult.failed(
            "synthetic local failure before dispatch",
            {"synthetic": True, "mutation_submitted": False, "action_dispatched": False},
        )
    try:
        context.checkpoint()
        response = remote.send(ack=mode != "sent_no_ack")
        context.remote_request_receipt(
            outcome="response_received", action=ACTION, request_id=REQUEST,
            detail={"remote_result_confirmed": response["synthetic_remote_confirmed"],
                    "local_business_writeback_confirmed": False,
                    "local_readback_confirmed": False},
        )
    except TimeoutError:
        context.remote_request_receipt(
            outcome="unknown", action=ACTION, request_id=REQUEST,
            detail={"response_observed": False},
        )
        return gateway.OperationResult.request_unknown("synthetic sent request has no ACK")
    except OSError:
        return gateway.OperationResult.request_unknown("synthetic response receipt failed to persist")
    raise AssertionError("S03 receipt-failure mode must not infer overall success")


@pytest.fixture
def no_database():
    from core.storage import postgres

    with patch.object(postgres, "connect", side_effect=AssertionError("offline S03 cannot connect")), \
         patch.object(postgres, "connect_dedicated", side_effect=AssertionError("offline S03 cannot connect")):
        yield


@pytest.mark.parametrize("mode,count,receipt_state,status,crash_status", CASES)
def test_native_checkpoint_failure_freezes_original_intent_without_remote_replay(
    no_database, mode, count, receipt_state, status, crash_status,
):
    store = OfflineCheckpointRepository()
    store.fail_receipt = mode == "remote_confirmed_receipt_write_failed"
    remote = LoopbackRemote()
    callbacks = 0
    with patch.object(gateway, "_operation", return_value=store):
        context = gateway.OperationHandlerContext({"id": 7, "task_id": 8}, execution_id="s03-original")
        callbacks += 1
        result = exercise_once(context, remote, mode)
        assert len(remote.calls) == count
        assert result.status == status
        assert store.data["remote_intent"]["receipt_state"] == receipt_state
        with pytest.raises(gateway.OperationSettlementPending):
            context.finish(result)
        frozen = context._settlement_intent
        digest = frozen.request_digest
        with pytest.raises(gateway.OperationSettlementConflict):
            context.finish(gateway.OperationResult.success({"synthetic": True, "late_guess": True}))
        store.fail_terminal = False
        context.finish(result)
        context.finish(result)
        assert context._settlement_intent is frozen
        assert frozen.request_digest == digest
        assert store.finishes == 2
        assert store.snapshots[0] == store.snapshots[1]
        assert callbacks == 1
        assert len(remote.calls) == count
        assert store.starts == 1
        assert store.receipts == 1
        assert store.checkpoints >= 1
        # This is the real pure recovery classifier, not elapsed PG recovery.
        recovered = recovery._recovery_result({"execution_id": "s03-original", "data": store.data})
        assert recovered["status"] == crash_status


@pytest.mark.parametrize("data,status", [
    ({}, "interrupted"),
    ({"remote_intent": {"kind": "remote_write", "receipt_state": "started"}}, "attention_required"),
    ({"remote_intent": {"kind": "remote_write", "receipt_state": "rejected"}}, "interrupted"),
    ({"remote_intent": {"kind": "remote_write", "receipt_state": "not_submitted"}}, "interrupted"),
    ({"remote_intent": {"kind": "remote_write", "receipt_state": "confirmed"}}, "attention_required"),
])
def test_crash_without_terminal_receipt_never_reconstructs_success(no_database, data, status):
    result = recovery._recovery_result({"data": data, "execution_id": "lost-original"})
    assert result["status"] == status
    assert result["status"] != "success"
    if status == "attention_required":
        assert result["result_summary"]["outcome"] == "request_unknown"
        assert result["result_summary"]["reconcile_required"] is True


if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    # Importing this module without root's explicit exclusive slot never loads
    # support_pg and never probes the developer's configured database.
    import time
    import uuid
    from tests.support_pg import PostgresTestCase
    from tests.support_settlement import install_native_settlement_fixture
    from core.operations import concurrency, settlement
    from core.storage.operations import legacy_task_store
    from core.storage.operations import store as operations, settlements
    from core.storage import postgres, records

    class RemoteCheckpointNativePostgresTests(PostgresTestCase):
        def setUp(self):
            super().setUp()
            self.stack = ExitStack()
            self.addCleanup(self.stack.close)
            self.stack.enter_context(patch.object(legacy_task_store, "_SCHEMA", self.schema))
            self.stack.enter_context(patch.object(legacy_task_store, "_READY_KEY", ""))
            legacy_task_store.init()
            operations.reset_ready()
            operations.init()
            # The disposable schema has no deployed policy. Native admission
            # reads schema defaults, independent of process config/environment.
            with postgres.connect() as conn:
                values, _revision, migration_required = concurrency._policy(conn)
            self.assertFalse(migration_required)
            self.assertGreaterEqual(values["GLOBAL_TASK_WORKERS"], 1)
            self.assertGreaterEqual(values["ACCOUNT_PLAN_CHECK_WORKERS"], 1)
            self.settlement_fixture = install_native_settlement_fixture(self)

        def tearDown(self):
            self.settlement_fixture.close()

        def test_s03_native_checkpoint_and_same_terminal_retry(self):
            for mode, count, receipt_state, status, crash_status in CASES:
                with self.subTest(mode=mode):
                    account_id = records.insert_row(records.ACCOUNTS, {
                        "email": f"s03-{uuid.uuid4().hex}@example.test",
                    })
                    task = operations.create_runtime_task(
                        task_type="plan_check", account_id=account_id,
                        email=f"s03-{account_id}@example.test", resource_family="openai_interactive",
                        trigger="synthetic_s03",
                    )
                    run_id = int(task["run"]["id"])
                    # The creation response's nested run is storage-shaped;
                    # dispatch uses the native enriched run joined with task.
                    run = operations.get_run(run_id)
                    self.assertEqual("plan_check", run["task_type"])
                    admission = gateway.admit_operation_run(run)
                    self.assertTrue(admission.admitted)
                    execution = admission.context
                    remote = LoopbackRemote()
                    callbacks = 0
                    original_submit = settlements.submit_intent
                    submits = []
                    failing = True

                    def submit(intent, **kwargs):
                        submits.append(intent)
                        if failing:
                            raise OSError("synthetic original terminal storage failure")
                        return original_submit(intent, **kwargs)

                    settlement.callback_started(execution)
                    with concurrency.execution_scope(execution), patch.object(settlements, "submit_intent", side_effect=submit):
                        context = gateway.OperationHandlerContext(execution.claimed_run, execution_id=execution.execution_id)
                        with context.lease(scope_kind="final"):
                            callbacks += 1
                            if mode == "remote_confirmed_receipt_write_failed":
                                with patch.object(operations, "record_remote_receipt", side_effect=OSError("receipt rollback")):
                                    result = exercise_once(context, remote, mode)
                            else:
                                result = exercise_once(context, remote, mode)
                            stored = operations.get_run(run_id)
                            self.assertEqual(receipt_state, stored["data"]["remote_intent"]["receipt_state"])
                            self.assertEqual(crash_status, recovery._recovery_result(stored)["status"])
                            with self.assertRaises(gateway.OperationSettlementPending):
                                context.finish(result)
                            intent = context._settlement_intent
                            self.assertIsNone(settlements.read_receipt(intent, domain=context.settlement_domain))
                            failing = False
                            context.finish(result)
                            context.finish(result)
                        self.assertEqual(1, callbacks)
                        self.assertEqual(count, len(remote.calls))
                        self.assertTrue(all(item is intent for item in submits))
                        receipt = settlements.read_receipt(intent, domain=context.settlement_domain)
                        expected = "failed" if mode == "not_sent" else "attention_required"
                        self.assertEqual(expected, receipt["status"])
                        self.assertEqual(expected, operations.get_run(run_id)["status"])
                        self.assertEqual(expected, operations.get_task(task["id"], include_events=False)["status"])
                    settlement.callback_exited(execution)
                    settlement.request_release(execution)
                    self.settlement_fixture.wait_for_run_released(run_id)
