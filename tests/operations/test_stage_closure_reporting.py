"""关键兼容执行器只按真实成功证据收口，取消不能伪装成失败。"""

from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts import operation_results, operation_settings
from core.codex import oauth as codex_oauth, operation_service as codex_operation_service, retry_service as codex_retry_service
from core.registration import service as registration_service
from core.operations.runtime import OperationCancelled


class RegistrationCodexClosureTests(unittest.TestCase):
    def _run(self, result):
        job = {"id": 91, "status": "pending", "job_type": "codex_retry"}
        calls = Mock()
        with ExitStack() as stack:
            for name in ("_activate_job", "_deactivate_job", "_ensure_registration_run_context", "_finish_registration_run"):
                stack.enter_context(patch.object(registration_service, name))
            stack.enter_context(patch.object(registration_service, "is_stop_requested", return_value=False))
            stack.enter_context(patch.object(registration_service.db, "get_job", side_effect=lambda _: dict(job)))
            stack.enter_context(patch.object(registration_service, "_claim_job_for_worker", return_value=True))
            stack.enter_context(patch.object(registration_service.db, "update_job", side_effect=lambda _, **values: job.update(values)))
            stage = stack.enter_context(patch.object(registration_service.db, "update_job_progress"))
            finish = stack.enter_context(patch.object(registration_service.db, "finish_job_progress"))
            calls.attach_mock(stage, "stage")
            calls.attach_mock(finish, "finish")
            stack.enter_context(patch.object(registration_service.codex_retry_service, "run_worker", return_value=result))
            stack.enter_context(patch.object(registration_service.codex_retry_service, "release"))
            registration_service._run_codex_retry_job(91, "/tmp/stage-closure-fixture.log", "fixture@example.test", 92, 93)
        return calls, job

    def test_confirmed_success_closes_parent_job_before_task_result(self):
        calls, job = self._run({"ok": True, "status": "success"})
        stage_calls = [call for call in calls.mock_calls if call[0] == "stage" and call.args[1] == "codex"]
        self.assertEqual(["running", "success"], [call.kwargs["state"] for call in stage_calls])
        success = calls.mock_calls.index(stage_calls[-1])
        finish = next(index for index, call in enumerate(calls.mock_calls) if call[0] == "finish")
        self.assertLess(success, finish)
        self.assertEqual("success", job["status"])

    def test_failed_unknown_or_stopped_results_never_confirm_parent_stage(self):
        for result in (
            {"ok": False, "status": "failed"},
            {"ok": False, "status": "attention_required"},
            {"ok": True, "status": "stopped"},
        ):
            with self.subTest(status=result["status"]):
                calls, _ = self._run(result)
                self.assertFalse(any(
                    call[0] == "stage" and call.args[1] == "codex" and call.kwargs.get("state") == "success"
                    for call in calls.mock_calls
                ))


class WorkspaceClosureTests(unittest.TestCase):
    callback = "http://localhost:1455/auth/callback?code=fixture&state=expected"

    def _select(self, response, *, follow=None):
        report = Mock()
        with patch.object(codex_oauth, "report_stage", report), patch.object(
            codex_oauth, "_post_json", return_value=response
        ), patch.object(codex_oauth, "_follow_until_callback", return_value=follow):
            result = codex_oauth._select_workspace_and_get_callback(object(), "expected", workspace_id="fixture-workspace")
        return result, report

    def test_direct_valid_callback_closes_actual_selection(self):
        response = SimpleNamespace(headers={"Location": self.callback}, status_code=302)
        result, report = self._select(response)
        self.assertEqual(self.callback, result)
        self.assertEqual(["running", "success"], [call.kwargs.get("state", "running") for call in report.call_args_list])

    def test_followed_valid_callback_closes_actual_selection(self):
        response = SimpleNamespace(headers={}, status_code=200, json=lambda: {"continue_url": "/api/accounts/continue"})
        result, report = self._select(response, follow=self.callback)
        self.assertEqual(self.callback, result)
        self.assertEqual("success", report.call_args.kwargs["state"])

    def test_missing_callback_or_mismatched_state_cannot_confirm_selection(self):
        for response in (
            SimpleNamespace(headers={}, status_code=200, json=lambda: {}),
            SimpleNamespace(headers={"Location": self.callback.replace("expected", "mismatched")}, status_code=302),
        ):
            report = Mock()
            with self.subTest(response=response), patch.object(codex_oauth, "report_stage", report), patch.object(
                codex_oauth, "_post_json", return_value=response
            ), self.assertRaises(RuntimeError):
                codex_oauth._select_workspace_and_get_callback(object(), "expected", workspace_id="fixture-workspace")
            self.assertFalse(any(call.kwargs.get("state") == "success" for call in report.call_args_list))


class BrowserRetryNotificationTests(unittest.TestCase):
    def test_recovered_browser_retry_is_notification_in_existing_stage(self):
        route = Mock(provider="fixture", region="fixture", mode="direct", proxy_url=None)
        route.public_dict.return_value = {"network_route": "fixture"}
        attempt = 0

        def browser_action(_email, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise RuntimeError("fixture temporary error")
            # Real browser success invokes the supplied setup action; this
            # records the required step receipt consumed by finalization.
            kwargs["action"](Mock(), {})

        with ExitStack() as stack:
            stack.enter_context(patch("config.reload_all"))
            stack.enter_context(patch.object(codex_retry_service.db, "get_account_by_email", return_value={
                "id": 94, "extra_json": {"account_password": "fixture-password", "account_password_state": "confirmed"},
                "access_token": "fixture-at",
            }))
            stack.enter_context(patch.object(codex_retry_service.account_task_store, "get_task", return_value={}))
            events = stack.enter_context(patch.object(codex_retry_service.account_task_store, "append_event"))
            stack.enter_context(patch.object(codex_retry_service.task_run_log, "TaskRunLogHandler"))
            stack.enter_context(patch.object(codex_retry_service.logging, "getLogger", return_value=Mock()))
            stack.enter_context(patch.object(codex_retry_service, "check_stop_requested"))
            stack.enter_context(patch.object(codex_retry_service, "_attach_auth_projection"))
            def setup_action(*args, step_results, **kwargs):
                def complete(_driver, _session):
                    step_results["password"] = {
                        "ok": True, "status": "success", "message": "fixture verified password",
                        "remote_receipt_state": "confirmed",
                    }
                return complete
            stack.enter_context(patch.object(codex_retry_service, "_build_roxy_account_setup", side_effect=setup_action))
            stack.enter_context(patch.object(codex_retry_service, "_is_retryable_account_setup_error", return_value=True))
            stack.enter_context(patch.object(codex_retry_service, "_account_setup_retry_reason", return_value="fixture_retry"))
            stack.enter_context(patch.object(codex_retry_service.time, "sleep"))
            stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", return_value=route))
            browser = stack.enter_context(patch("core.codex.roxy.oauth.run_roxy_chatgpt_account_action", side_effect=browser_action))
            result = codex_retry_service.run_twofa_worker(
                "fixture@example.test", task_id=95, steps={"password"}, manage_task=False,
                clear_log=False, target_log_path="/tmp/stage-closure-fixture.log", password_driver_override="roxy",
            )
        self.assertTrue(result["ok"])
        self.assertEqual("confirmed", result["step_results"]["password"]["remote_receipt_state"])
        self.assertEqual(2, browser.call_count)
        notification = next(call.kwargs for call in events.call_args_list if call.kwargs.get("event_type") == "note.warning")
        self.assertEqual("browser", notification["stage"])
        self.assertNotIn("state", notification)
        self.assertEqual(1, notification["detail"]["attempt"])
        self.assertTrue(any(call.kwargs.get("stage") == "browser" and call.kwargs.get("state") == "success" for call in events.call_args_list))


class CodexCancellationStageTests(unittest.TestCase):
    def _run(self, phase, *, exception_type=OperationCancelled):
        service = codex_operation_service
        run = {"id": 96, "task_id": 97, "account_id": 98, "task_type": "codex_retry", "email_snapshot": "fixture@example.test", "data": {"config_snapshot": {"oauth_driver": "roxy"}}}
        from core.operations import concurrency

        execution = concurrency.ExecutionContext("fixture-permit", "fixture-execution", "operation_run:96", "codex_retry", run)
        route = Mock(provider="fixture", region="fixture", mode="direct", proxy_url=None)
        route.public_dict.return_value = {"network_route": "fixture"}
        with ExitStack() as stack:
            stack.enter_context(patch.object(service.task_gateway, "_operation", return_value=service.operation_task_store))
            stack.enter_context(patch.object(concurrency, "current_execution", return_value=execution))
            stack.enter_context(patch.object(concurrency, "validate_execution", return_value=True))
            stack.enter_context(patch.object(concurrency, "set_execution_state", return_value=True))
            for name, value in (
                ("claim_run", run), ("get_run", run), ("acquire_account_lease", "fixture-lease"),
                ("register_resource", {"id": 99, "resource_uuid": "fixture-route-resource"}),
                ("record_remote_intent", {}), ("is_run_cancel_requested", False),
                ("heartbeat_run", True), ("release_resource", True), ("release_account_lease", True),
            ):
                stack.enter_context(patch.object(service.operation_task_store, name, return_value=value))
            events = stack.enter_context(patch.object(service.operation_task_store, "append_runtime_event", return_value={}))
            def committed_finish(run_id, **values):
                return {"id": run_id, "status": values["status"],
                        "result_summary": dict(values.get("result_summary") or {}),
                        "message": values.get("message", ""), "error_message": values.get("error")}
            finish = stack.enter_context(patch.object(service.operation_task_store, "finish_run", side_effect=committed_finish))
            stack.enter_context(patch.object(service.db, "update_account_codex_operation_state"))
            # Keep the real lease/context state machine; this offline fixture
            # only suppresses the synthetic lease's renewal thread.
            stack.enter_context(patch("core.operations.task_gateway.threading.Thread.start"))
            stack.enter_context(patch.object(service.task_gateway.OperationHandlerContext, "register_cleanup"))
            stack.enter_context(patch.object(service, "CancellationToken", return_value=Mock()))
            stack.enter_context(patch.object(service, "_forget_dispatched"))
            stack.enter_context(patch.object(service.task_run_log, "TaskRunLogHandler"))
            stack.enter_context(patch.object(service.logging, "getLogger", return_value=Mock()))
            feature = stack.enter_context(patch.object(service, "_feature_ready", return_value=(True, "")))
            acquire = stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", return_value=route))
            oauth = stack.enter_context(patch.object(codex_oauth, "run_codex_oauth"))
            {"preflight": feature, "network": acquire, "browser": oauth}[phase].side_effect = exception_type("fixture cancellation")
            result = service._execute_run(96)
            self.assertEqual(1, {"preflight": feature, "network": acquire, "browser": oauth}[phase].call_count)
            finish.assert_called_once()
        return result, [call.kwargs for call in events.call_args_list], finish.call_args.kwargs

    def test_safe_cancellation_does_not_fail_preflight_or_network(self):
        for phase in ("preflight", "network"):
            with self.subTest(phase=phase):
                result, events, finish = self._run(phase)
                self.assertEqual("cancelled", result["status"])
                self.assertEqual("cancelled", finish["status"])
                self.assertFalse(any(event.get("state") == "failed" for event in events))
                self.assertTrue(any(event.get("stage") == phase and event.get("detail", {}).get("cancelled") for event in events))

    def test_driver_cancellation_keeps_remote_unknown_and_no_false_failed_stage(self):
        result, events, finish = self._run("browser")
        self.assertEqual("attention_required", result["status"])
        self.assertEqual("request_unknown", finish["result_summary"]["outcome"])
        self.assertFalse(any(event.get("state") == "failed" for event in events))
        self.assertTrue(any(event.get("stage") == "browser" and event.get("detail", {}).get("cancelled") for event in events))

    def test_real_driver_exception_still_records_failure(self):
        result, events, finish = self._run("browser", exception_type=RuntimeError)
        self.assertEqual("attention_required", result["status"])
        self.assertEqual("request_unknown", finish["result_summary"]["outcome"])
        self.assertTrue(any(event.get("state") == "failed" for event in events))

    def test_lease_loss_interrupts_each_scope_without_business_failure(self):
        for phase in ("preflight", "network", "browser"):
            with self.subTest(phase=phase):
                result, events, finish = self._run(phase, exception_type=codex_operation_service.task_gateway.OperationLeaseLost)
                self.assertEqual("attention_required", result["status"])
                self.assertEqual("request_unknown", finish["result_summary"]["outcome"])
                self.assertTrue(finish["result_summary"]["lease_lost"])
                self.assertFalse(any(event.get("state") == "failed" for event in events))
                self.assertTrue(any(
                    event.get("stage") == phase and event.get("detail", {}).get("lease_lost")
                    and event.get("detail", {}).get("reconcile_required") for event in events
                ))


class CompatibilityCompletionClosureTests(unittest.TestCase):
    def test_native_setup_keeps_an_explicit_password_reset_flag(self):
        from webui import runtime

        context = SimpleNamespace(
            run={"data": {"steps": ["password"], "force_password_reset": True}},
            task_type="password_setup", config_snapshot={},
            execution_fence={"run_id": 105, "execution_id": "fixture-execution", "lease_token": "fixture-lease"},
            account_id=103, task_id=104, run_id=105, email="fixture@example.test",
            report=Mock(), finished=False, last_result=None,
            lease=Mock(return_value=nullcontext()), remote_request_started=Mock(),
            remote_request_receipt=Mock(), finish=Mock(),
        )
        with (
            patch.object(operation_settings, "completion_settings_from_snapshot", return_value={}),
            patch.object(runtime.codex_retry_service, "run_twofa_worker", return_value={
                "ok": True, "status": "success",
            }) as worker,
            patch.object(operation_results, "account_setup_receipt", return_value=("confirmed", {})),
        ):
            result = runtime._handle_native_account_setup(context)

        self.assertEqual("success", result.status)
        self.assertTrue(worker.call_args.kwargs["force_password_reset"])

    def test_actual_setup_success_closes_coordinator_scope(self):
        from webui import runtime

        for result in (
            {"ok": True, "status": "success"},
            {"ok": False, "status": "failed"},
            {"ok": False, "status": "attention_required"},
        ):
            with self.subTest(status=result["status"]), ExitStack() as stack:
                stack.enter_context(patch.object(runtime.account_task_store, "start_task"))
                events = stack.enter_context(patch.object(runtime.account_task_store, "append_event"))
                stack.enter_context(patch.object(runtime.account_task_store, "finish_task"))
                stack.enter_context(patch.object(runtime.codex_retry_service, "release"))
                worker = stack.enter_context(patch.object(runtime.codex_retry_service, "run_twofa_worker", return_value=result))
                stack.enter_context(patch.object(runtime.logger, "exception"))
                runtime._run_account_completion_worker(
                    "fixture@example.test", account_id=101, task_id=102,
                    task_trigger="fixture", planned_steps=["password"], settings={}, context=None,
                )
            states = [call.kwargs.get("state") for call in events.call_args_list if call.kwargs.get("stage") == "account_setup"]
            self.assertEqual(["running", "success"] if result["ok"] else ["running"], states)
            self.assertFalse(worker.call_args.kwargs["manage_task"])

    def test_native_setup_needs_its_own_confirmed_writeback_before_success(self):
        from webui import runtime

        for receipt_state, business_status in (
            ("confirmed", "success"),
            ("confirmed", "deactivated"),
            ("rejected", "failed"),
            ("rejected", "unsupported"),
            ("local_commit_required", "success"),
            ("unknown", "failed"),
        ):
            context = SimpleNamespace(
                run={"data": {"steps": ["password"]}, "trigger": "fixture"},
                task_type="account_setup_retry",
                execution_fence={"run_id": 105, "execution_id": "fixture-execution", "lease_token": "fixture-lease"},
                config_snapshot={}, account_id=103, task_id=104, run_id=105,
                email="fixture@example.test", report=Mock(), finished=False, last_result=None,
                lease=Mock(return_value=nullcontext()), remote_request_started=Mock(),
                remote_request_receipt=Mock(), finish=Mock(),
            )
            with self.subTest(receipt=receipt_state, status=business_status), patch.object(
                operation_settings, "completion_settings_from_snapshot", return_value={}
            ), patch.object(runtime.codex_retry_service, "run_twofa_worker", return_value={
                "ok": business_status == "success", "status": business_status,
            }), patch.object(operation_results, "account_setup_receipt", return_value=(receipt_state, {})):
                result = runtime._handle_native_account_setup(context)
            success = receipt_state == "confirmed" and business_status == "success"
            failed = receipt_state == "rejected" and business_status == "failed"
            states = [call.kwargs["state"] for call in context.report.call_args_list if call.kwargs.get("stage") == "account_setup"]
            self.assertEqual(["running", "success"] if success else ["running", "failed"] if failed else ["running"], states)
            if receipt_state in {"unknown", "local_commit_required"}:
                self.assertEqual("request_unknown", result.status)


if __name__ == "__main__":
    unittest.main()
