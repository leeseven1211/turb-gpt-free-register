"""补全抽取保留历史续接、持久占用与 setup 证据顺序。"""

from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import db, operation_task_store
from core.accounts import completion_dependencies, completion_execution, operation_settings, setup_execution
from core.codex import retry_service
from core.operations import task_gateway
from core.runtime import capabilities


def execution_context(*, data=None, events=None):
    context = SimpleNamespace(
        account_id=41, task_id=42, run_id=43, email="boundary@example.test",
        task_type="account_setup_retry", source_system="webui_runtime",
        run={"data": dict(data or {}), "trigger": "registration_job_retry", "log_file": ""},
        config_snapshot={"password_driver": "protocol", "twofa_driver": "protocol"},
        execution_fence={"run_id": 43, "execution_id": "fixture-execution", "lease_token": "fixture-lease"},
        finished=False, last_result=None, report=Mock(), release_lease=Mock(),
        lease=Mock(return_value=nullcontext()),
        remote_request_started=Mock(), remote_request_receipt=Mock(),
        add_settlement_obligation=Mock(),
    )

    def finish(result):
        if events is not None:
            events.append("finish")
        context.finished = True
        context.last_result = result
        # This fixture confirms the parent synchronously, then runs only its
        # declared typed existing-child handoff, as the storage dispatcher
        # does after an authoritative settlement receipt.
        for call in context.add_settlement_obligation.call_args_list:
            if call.args == ("completion_dependency",):
                child_lookup = operation_task_store.get_task

                def lookup(task_id, **kwargs):
                    if int(task_id) == 42:
                        return {"id": 42, "last_run_id": 43, "status": result.status}
                    return child_lookup(task_id, **kwargs)

                with patch.object(operation_task_store, "get_task", side_effect=lookup):
                    assert completion_execution.apply_settlement_dependency(call.kwargs["payload"])
        return result.as_dict()

    context.finish = Mock(side_effect=finish)
    return context


class CompletionDependencyBoundaryTests(unittest.TestCase):
    def dependency(self, *, source="webui_runtime", child_status="success"):
        return {
            "id": 51, "status": "running", "parent_source_system": source,
            "parent_source_id": "42", "child_source_system": "webui_runtime",
            "child_source_id": "61", "child_status": child_status,
            "child_result": {"status": child_status},
            "payload": {
                "parent_run_id": 43, "account_id": 41, "email": "boundary@example.test",
                "task_trigger": "manual_account_completion", "remaining_steps": ["password"],
                "settings": {"password_enabled": True},
                "result_summary": {"refresh_at": {"accepted": True, "task_id": 61}},
            },
        }

    def test_email_change_handoff_never_reopens_its_terminal_parent(self):
        for child_status in ("success", "failed"):
            with self.subTest(child_status=child_status):
                dependency = self.dependency(source="native_operations", child_status=child_status)
                dependency["parent_source_id"] = "email-change:42"
                with (
                    patch.object(operation_task_store, "complete_task_dependency") as complete,
                    patch.object(operation_task_store, "get_task") as read_parent,
                    patch.object(operation_task_store, "retry_runtime_task") as retry,
                    patch.object(operation_task_store, "apply_task_dependency_result") as apply_result,
                    patch.object(completion_execution, "run_account_completion_worker") as worker,
                    patch.object(task_gateway, "notify_dispatch") as dispatch,
                ):
                    completion_dependencies.handle_ready_completion_dependency(dependency)
                complete.assert_called_once_with(51, success=True)
                read_parent.assert_not_called()
                retry.assert_not_called()
                apply_result.assert_not_called()
                worker.assert_not_called()
                dispatch.assert_not_called()

    def test_legacy_success_reserves_before_work_and_completes_after_work(self):
        dependency = self.dependency(source="account_action_tasks")
        events = []

        def reserve(_email):
            events.append("reserve")
            return True

        with (
            patch.object(retry_service, "reserve", side_effect=reserve) as reserved,
            patch.object(completion_execution, "run_account_completion_worker", side_effect=lambda *a, **k: events.append("worker")) as worker,
            patch.object(operation_task_store, "complete_task_dependency", side_effect=lambda *a, **k: events.append("complete")) as complete,
            patch.object(task_gateway, "notify_dependency_ready") as notify,
        ):
            completion_dependencies.handle_ready_completion_dependency(dependency)
        self.assertEqual(["reserve", "worker", "complete"], events)
        reserved.assert_called_once_with("boundary@example.test")
        worker.assert_called_once_with(
            "boundary@example.test", account_id=41, task_id=42,
            task_trigger="manual_account_completion", planned_steps=["password"],
            settings={"password_enabled": True},
            initial_result_summary={"refresh_at": {"accepted": True, "task_id": 61}},
        )
        complete.assert_called_once_with(51, success=True)
        notify.assert_not_called()

    def test_legacy_busy_reservation_returns_dependency_to_durable_queue(self):
        dependency = self.dependency(source="account_action_tasks")
        events = []
        with (
            patch.object(retry_service, "reserve", return_value=False),
            patch.object(completion_execution, "run_account_completion_worker") as worker,
            patch.object(operation_task_store, "complete_task_dependency", side_effect=lambda *a, **k: events.append("requeue")) as complete,
            patch.object(task_gateway, "notify_dependency_ready", side_effect=lambda *a: events.append("notify")) as notify,
        ):
            completion_dependencies.handle_ready_completion_dependency(dependency)
        self.assertEqual(["requeue", "notify"], events)
        worker.assert_not_called()
        complete.assert_called_once()
        self.assertEqual((51,), complete.call_args.args)
        self.assertFalse(complete.call_args.kwargs["success"])
        self.assertTrue(complete.call_args.kwargs["error"])
        notify.assert_called_once_with(dependency)

    def test_stale_or_cancelled_parent_consumes_dependency_without_mutating_parent(self):
        for last_run_id, status in (
            (44, "queued"), (43, "cancelled"), (43, "cancelling"), (43, "stopped"),
        ):
            for child_status in ("success", "failed"):
                with self.subTest(last_run_id=last_run_id, status=status, child_status=child_status):
                    dependency = self.dependency(child_status=child_status)
                    with (
                        patch.object(operation_task_store, "get_task", return_value={"id": 42, "last_run_id": last_run_id, "status": status}),
                        patch.object(operation_task_store, "complete_task_dependency") as complete,
                        patch.object(operation_task_store, "retry_runtime_task") as retry,
                        patch.object(operation_task_store, "apply_task_dependency_result") as apply_result,
                        patch.object(task_gateway, "notify_dispatch") as dispatch,
                    ):
                        completion_dependencies.handle_ready_completion_dependency(dependency)
                    complete.assert_called_once_with(51, success=True)
                    retry.assert_not_called()
                    apply_result.assert_not_called()
                    dispatch.assert_not_called()

    def test_new_manual_run_winning_resume_cas_does_not_dispatch_stale_continuation(self):
        dependency = self.dependency()
        dependency["payload"]["remaining_steps"] = []
        with (
            patch.object(operation_task_store, "get_task", return_value={"id": 42, "last_run_id": 43, "status": "partial_success"}),
            patch.object(operation_task_store, "retry_runtime_task", return_value={"id": 44, "dependency_stale": True}) as retry,
            patch.object(operation_task_store, "complete_task_dependency") as complete,
            patch.object(task_gateway, "notify_dispatch") as dispatch,
        ):
            completion_dependencies.handle_ready_completion_dependency(dependency)
        retry.assert_called_once()
        self.assertEqual((42,), retry.call_args.args)
        self.assertEqual(43, retry.call_args.kwargs["expected_previous_run_id"])
        self.assertEqual([], retry.call_args.kwargs["data"]["continuation_payload"]["remaining_steps"])
        complete.assert_called_once_with(51, success=True)
        dispatch.assert_not_called()


class CompletionSetupBusyBoundaryTests(unittest.TestCase):
    def test_durable_setup_blocker_only_consumes_steps_owned_by_this_setup_child(self):
        cases = (
            ({"source_system": "webui_runtime", "source_id": "account-completion-setup:42:43", "task_type": "account_setup_retry"}, ["codex"]),
            ({"source_system": "native_operations", "source_id": "unrelated-refresh", "task_type": "token_refresh"}, ["password", "codex"]),
        )
        for blocker, remaining in cases:
            for source_in_response in (False, True):
                with self.subTest(blocker=blocker, source_in_response=source_in_response):
                    context = execution_context()
                    with (
                        patch.object(task_gateway, "submit_durable_operation", return_value={
                            "accepted": False, "busy": True, "task_id": 61, "run_id": 62,
                            **(blocker if source_in_response else {}),
                        }),
                        patch.object(task_gateway, "get_task", autospec=True,
                                     side_effect=AssertionError("native blocker must not query legacy tasks")) as legacy_lookup,
                        patch.object(operation_task_store, "register_task_dependency", return_value={"id": 51, "status": "waiting"}) as register,
                        patch.object(operation_task_store, "get_task", autospec=True,
                                     return_value={"id": 61, "status": "running", **blocker}) as native_lookup,
                        patch.object(operation_task_store, "mark_task_dependency_ready", return_value=[]),
                        patch.object(task_gateway, "notify_dependency_ready") as notify,
                        patch.object(retry_service, "run_twofa_worker") as remote_worker,
                        patch.object(db, "get_account", side_effect=AssertionError("setup handoff must not read account state")),
                    ):
                        result = completion_execution.run_account_completion_worker(
                            context.email, account_id=41, task_id=42,
                            task_trigger="manual_account_completion",
                            planned_steps=["password", "codex"], settings={}, context=context,
                        )
                    legacy_lookup.assert_not_called()
                    # 补读 blocker 和登记后的快速终态检查是两个真实消费阶段。
                    self.assertEqual(1 if source_in_response else 2, native_lookup.call_count)
                    native_lookup.assert_called_with(61, include_events=False)
                    remote_worker.assert_not_called()
                    notify.assert_not_called()
                    self.assertEqual("partial_success", result.status)
                    self.assertEqual(remaining, result.summary["continuation_steps"])
                    register.assert_called_once()
                    edge = register.call_args.kwargs
                    self.assertEqual(blocker["source_system"], edge["child_source_system"])
                    self.assertEqual("61", edge["child_source_id"])
                    self.assertEqual(43, edge["payload"]["parent_run_id"])
                    self.assertEqual(remaining, edge["payload"]["remaining_steps"])
                    context.release_lease.assert_called()

    def test_unresolvable_native_blocker_requeues_without_consuming_setup_steps(self):
        cases = (None, {"id": 61, "source_system": "native_operations", "source_id": ""},
                 LookupError("missing"), TypeError("invalid reference"), ValueError("invalid id"))
        for blocker in cases:
            with self.subTest(blocker=blocker):
                context = execution_context()
                with (
                    patch.object(task_gateway, "submit_durable_operation", return_value={
                        "accepted": False, "busy": True, "task_id": 61, "run_id": 62,
                    }),
                    patch.object(task_gateway, "get_task", autospec=True,
                                 side_effect=AssertionError("native blocker must not query legacy tasks")) as legacy_lookup,
                    patch.object(operation_task_store, "get_task", autospec=True,
                                 **({"side_effect": blocker} if isinstance(blocker, Exception) else {"return_value": blocker})) as native_lookup,
                    patch.object(operation_task_store, "register_task_dependency") as register,
                    patch.object(retry_service, "run_twofa_worker") as remote_worker,
                    patch.object(db, "get_account", side_effect=AssertionError("unresolved blocker must not read account state")),
                ):
                    with self.assertRaises(task_gateway.OperationLeaseUnavailable):
                        completion_execution.run_account_completion_worker(
                            context.email, account_id=41, task_id=42,
                            task_trigger="manual_account_completion",
                            planned_steps=["password", "codex"], settings={}, context=context,
                        )
                native_lookup.assert_called_once_with(61, include_events=False)
                legacy_lookup.assert_not_called()
                context.finish.assert_not_called()
                register.assert_not_called()
                remote_worker.assert_not_called()
                context.release_lease.assert_called()

    def test_complete_submission_source_never_looks_up_a_different_task_model(self):
        for accepted, busy in ((True, False), (True, True), (False, True)):
            with self.subTest(accepted=accepted, busy=busy):
                submitted = {"accepted": accepted, "busy": busy, "task_id": 61, "run_id": 62,
                             "source_system": "webui_runtime", "source_id": "account-completion-setup:42:43"}
                with (
                    patch.object(task_gateway, "submit_durable_operation", return_value=dict(submitted)),
                    patch.object(task_gateway, "get_task", autospec=True,
                                 side_effect=AssertionError("complete source must not query legacy tasks")) as legacy_lookup,
                    patch.object(operation_task_store, "get_task", autospec=True,
                                 side_effect=AssertionError("complete source needs no blocker lookup")) as native_lookup,
                ):
                    result = setup_execution.submit_native_account_setup_child(
                        execution_context(), steps={"password"}, task_trigger="manual_account_completion",
                    )
                self.assertEqual({**submitted, "_setup_child_source_id": "account-completion-setup:42:43"}, result)
                legacy_lookup.assert_not_called()
                native_lookup.assert_not_called()


class SharedSetupEvidenceOrderTests(unittest.TestCase):
    def test_registration_setup_confirms_only_after_adapter_writeback_and_receipt(self):
        events = []
        context = execution_context(data={"steps": ["password"], "source_job_id": 91}, events=events)
        context.remote_request_started.side_effect = lambda *a, **k: events.append("intent")
        context.remote_request_receipt.side_effect = lambda **k: events.append("receipt")

        def adapter(_email, **_kwargs):
            events.append("adapter")
            return {
                "ok": True, "status": "success", "password_driver": "protocol",
                "step_results": {"password": {"ok": True, "remote_receipt_state": "confirmed"}},
            }

        def readback(_account_id):
            events.append("readback")
            return {"id": 41, "access_token": "fixture-at", "extra_json": {
                "account_password": "fixture-password", "account_password_state": "confirmed",
            }}

        with (
            patch.object(operation_settings, "completion_settings_from_snapshot", return_value=context.config_snapshot),
            patch.object(capabilities, "account_setup_unavailable", return_value=None),
            patch.object(retry_service, "run_twofa_worker", side_effect=adapter) as worker,
            patch.object(db, "get_account", side_effect=readback),
            patch.object(db, "get_account_by_email", side_effect=AssertionError("fixture account must satisfy readback")),
        ):
            result = setup_execution.handle_native_account_setup(context)
        self.assertEqual(["intent", "adapter", "readback", "receipt", "finish"], events)
        self.assertEqual("success", result.status)
        self.assertEqual(context.execution_fence, worker.call_args.kwargs["execution_fence"])
        self.assertEqual("registration_job_retry", worker.call_args.kwargs["task_trigger"])
        receipt = context.remote_request_receipt.call_args.kwargs
        self.assertEqual("confirmed", receipt["outcome"])
        self.assertEqual({"password": True}, receipt["detail"]["local_readback_checks"])
        self.assertEqual(receipt["detail"]["setup_step_receipts"], result.summary["setup_step_receipts"])

    def test_setup_adapter_exception_records_unknown_before_finishing(self):
        events = []
        context = execution_context(data={"steps": ["password"]}, events=events)
        context.remote_request_started.side_effect = lambda *a, **k: events.append("intent")
        context.remote_request_receipt.side_effect = lambda **k: events.append("receipt")

        def adapter(_email, **_kwargs):
            events.append("adapter")
            raise RuntimeError("fixture remote response lost")

        with (
            patch.object(operation_settings, "completion_settings_from_snapshot", return_value=context.config_snapshot),
            patch.object(capabilities, "account_setup_unavailable", return_value=None),
            patch.object(retry_service, "run_twofa_worker", side_effect=adapter),
            patch.object(db, "get_account") as readback,
        ):
            result = setup_execution.handle_native_account_setup(context)
        self.assertEqual(["intent", "adapter", "receipt", "finish"], events)
        self.assertEqual("request_unknown", result.status)
        self.assertTrue(result.summary["reconcile_required"])
        readback.assert_not_called()
        receipt = context.remote_request_receipt.call_args.kwargs
        self.assertEqual("unknown", receipt["outcome"])
        self.assertFalse(receipt["detail"]["remote_response_received"])


if __name__ == "__main__":
    unittest.main()
