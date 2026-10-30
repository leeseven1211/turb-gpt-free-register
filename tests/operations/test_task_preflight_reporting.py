# -*- coding: utf-8 -*-
"""验证服务上报的阶段与实际执行边界一致，不调用真实账号或数据库。"""
from contextlib import ExitStack, contextmanager, nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.codex import token_refresh_service as codex_token_refresh_service
from core.accounts.liveness import service as live_check_service
from core.accounts.plans import service as plan_check_service
from core.operations import run_log as task_run_log
from core.operations.runtime import OperationCancelled
from core.operations.progress import build_progress_snapshot


class TaskPreflightReportingTests(unittest.TestCase):
    def tearDown(self):
        task_run_log.clear_current_context()

    @contextmanager
    def _scenario(self, service, *, native=True):
        events = []
        execution = []

        def report(*_args, **event):
            events.append(dict(event))
            execution.append((event.get("stage"), event.get("state")))
            return {"event_id": len(events)}

        def finish(**result):
            execution.append(("finished", result["status"]))

        context = SimpleNamespace(
            task_id=901,
            run_id=902,
            account_id=7,
            email="fixture@example.test",
            run={"data": {}},
            config_snapshot={"auth_raw_context_enabled": False},
            report=Mock(side_effect=report),
            finish=Mock(side_effect=finish),
            checkpoint=Mock(),
            is_cancel_requested=Mock(return_value=False),
            lease=Mock(side_effect=lambda **_kwargs: nullcontext()),
        )
        database = Mock()
        database.mark_account_plan_check_running.return_value = True
        database.claim_account_plan_check.return_value = True
        database.mark_account_live_check_running.return_value = True
        database.update_account_liveness.return_value = True
        database.get_account.return_value = {
            "email": context.email,
            "access_token": "fixture-access-value",
        }
        route = SimpleNamespace(
            proxy_url="http://fixture.invalid:8080",
            public_dict=lambda: {"network_route": "proxy", "proxy_provider": "fixture"},
            release=Mock(),
        )

        def acquire(**_kwargs):
            execution.append(("network_call", None))
            return route

        def query(*_args, **_kwargs):
            execution.append(("remote_call", None))
            return {"ok": True, "http_status": 200, "current_plan_type": "free"}

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "db", database))
            stack.enter_context(patch.object(service, "logger"))
            stack.enter_context(patch.object(service.account_task_store, "create_task", return_value=901))
            stack.enter_context(patch.object(service.account_task_store, "start_task"))
            stack.enter_context(patch.object(service.account_task_store, "append_event", side_effect=report))
            legacy_finish = stack.enter_context(patch.object(
                service.account_task_store, "finish_task",
                side_effect=lambda *_args, **kwargs: finish(**kwargs),
            ))
            network = stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", side_effect=acquire))
            if service is plan_check_service:
                remote = stack.enter_context(patch.object(service, "_query_account_plan", side_effect=query))
            else:
                stack.enter_context(patch.object(service, "_append_log"))
                stack.enter_context(patch.object(service, "_resolve_protocol_identity", return_value=None))
                stack.enter_context(patch.object(service, "token_claims", return_value={}))
                remote = stack.enter_context(patch.object(service, "run_probe", side_effect=query))
            yield SimpleNamespace(
                context=context,
                operation_context=context if native else None,
                database=database,
                events=events,
                execution=execution,
                route=route,
                network=network,
                remote=remote,
                finish=context.finish if native else legacy_finish,
            )

    def _run(self, service, scenario, **kwargs):
        arguments = {
            "account_id": 7,
            "email": "fixture@example.test",
            "proxy": "http://fixture.invalid:8080",
            "trigger": "manual",
            "task_id": 901,
            "operation_context": scenario.operation_context,
        }
        if service is plan_check_service:
            arguments.update(access_token="fixture-access-value", timezone_offset_min="-")
            worker = service._run_plan_check
        else:
            arguments.update(
                driver="protocol_current",
                config_snapshot={"auth_raw_context_enabled": False},
            )
            worker = service._run_live_check
        arguments.update(kwargs)
        return worker(**arguments)

    @staticmethod
    def _states(events, state):
        return [event["stage"] for event in events if event.get("state") == state]

    @staticmethod
    def _progress(events, *, task_type, status, error=None):
        source = []
        for index, event in enumerate(events, 1):
            state = event.get("state")
            source.append({
                **event,
                "id": index,
                "event_type": event.get("event_type") or (f"stage.{state}" if state else "note.info"),
                "detail": {**(event.get("detail") or {}), **({"step_state": state} if state else {})},
            })
        return build_progress_snapshot(
            901, 902, task_type,
            {"status": status, "error_message": error}, source,
        )

    def _assert_preflight_before_requests(self, scenario):
        self.assertEqual(["preflight"], [
            event["stage"] for event in scenario.events
            if event.get("stage") == "preflight" and event.get("state") == "success"
        ])
        preflight = scenario.execution.index(("preflight", "success"))
        self.assertLess(preflight, scenario.execution.index(("network_call", None)))
        self.assertLess(preflight, scenario.execution.index(("remote_call", None)))
        self.assertEqual([], self._states(scenario.events, "failed"))

    def test_plan_success_closes_preflight_before_requests_for_both_reporters(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(plan_check_service, native=native) as scenario:
                result = self._run(plan_check_service, scenario)
                self.assertTrue(result["ok"])
                self._assert_preflight_before_requests(scenario)
                self.assertEqual("success", scenario.finish.call_args.kwargs["status"])
                scenario.route.release.assert_called_once()

    def test_plan_route_uses_frozen_reuse_switch_after_configuration_changes(self):
        with self._scenario(plan_check_service) as scenario, patch("config.proxy.PLAN_CHECK_PROXY_ALLOW_REUSE", True):
            result = self._run(plan_check_service, scenario, config_snapshot={"proxy_allow_reuse": False})
            self.assertTrue(result["ok"])
            self.assertIs(False, scenario.network.call_args.kwargs["allow_reuse"])

    def test_live_success_closes_preflight_before_requests_for_both_reporters(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(live_check_service, native=native) as scenario:
                result = self._run(live_check_service, scenario)
                self.assertTrue(result["ok"])
                self._assert_preflight_before_requests(scenario)
                self.assertEqual("success", scenario.finish.call_args.kwargs["status"])
                scenario.route.release.assert_called_once()

    def test_successful_email_fallback_recovers_password_failure_in_service_progress(self):
        with self._scenario(live_check_service, native=False) as scenario:
            live_check_service._report_protocol_v2_refresh(
                live_check_service.TaskReporter(901),
                {
                    "ok": True,
                    "auth_method": "email_otp",
                    "password_auth_status": "rejected",
                    "fallback_used": True,
                },
            )
            snapshot = self._progress(scenario.events, task_type="token_refresh", status="success")
            authenticate = next(item for item in snapshot["main_steps"] if item["id"] == "authenticate")
            password = next(item for item in authenticate["children"] if item["id"] == "login_password")
            self.assertEqual("success", authenticate["state"])
            self.assertIsNone(snapshot["failure"])
            self.assertEqual("recovered", password["display_status"])
            self.assertTrue(any(attempt["state"] == "failed" for attempt in password["attempts"]))
            self.assertEqual(["login_password"], self._states(scenario.events, "failed"))
            scenario.network.assert_not_called()
            scenario.remote.assert_not_called()

    def test_protocol_mfa_failure_reports_the_mfa_stage(self):
        for method, password_status in (("password", ""), ("email_otp", "skipped")):
            with self.subTest(method=method), self._scenario(live_check_service, native=False) as scenario:
                live_check_service._report_protocol_v2_refresh(
                    live_check_service.TaskReporter(901),
                    {
                        "ok": False,
                        "auth_method": method,
                        "password_auth_status": password_status,
                        "error": "account_deactivated",
                        "auth_diagnostics": {"operation": "mfa_verify", "http_status": 403},
                    },
                )
                self.assertEqual(["mfa_challenge"], self._states(scenario.events, "failed"))
                mfa = next(event for event in scenario.events if event["stage"] == "mfa_challenge")
                self.assertEqual("mfa_verify", mfa["detail"]["auth_diagnostics"]["operation"])
                snapshot = self._progress(scenario.events, task_type="token_refresh", status="deactivated")
                self.assertEqual("mfa_challenge", snapshot["failure"]["stage"])

    def test_password_rejected_email_fallback_mfa_failure_keeps_password_rejection(self):
        with self._scenario(live_check_service, native=False) as scenario:
            live_check_service._report_protocol_v2_refresh(
                live_check_service.TaskReporter(901),
                {
                    "ok": False,
                    "auth_method": "password_fallback_email_otp",
                    "error": "password_rejected_email_fallback_failed",
                    "auth_diagnostics": {"operation": "password_email_fallback", "cause_operation": "mfa_verify"},
                },
            )
            self.assertEqual(["login_password", "mfa_challenge"], self._states(scenario.events, "failed"))
            password = next(event for event in scenario.events if event["stage"] == "login_password")
            self.assertIn("密码被拒绝", password["message"])
            email = next(event for event in scenario.events if event["stage"] == "email_otp")
            self.assertEqual("success", email["state"])

    def test_live_missing_token_reports_actual_failure_instead_of_successful_preflight(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(live_check_service, native=native) as scenario:
                scenario.database.get_account.return_value = {"email": "fixture@example.test"}
                result = self._run(live_check_service, scenario)
                self.assertFalse(result["ok"])
                self.assertEqual(["access_token"], self._states(scenario.events, "failed"))
                snapshot = self._progress(scenario.events, task_type="live_check", status="failed", error=result["error"])
                self.assertEqual("access_token", snapshot["failure"]["stage"])
                self.assertIn("没有 accessToken", snapshot["failure"]["message"])
                preflight = next(item for item in snapshot["main_steps"] if item["id"] == "preflight")
                self.assertEqual("success", preflight["state"])
                scenario.network.assert_not_called()
                scenario.remote.assert_not_called()

    def test_missing_account_input_fails_preflight_without_requesting_network(self):
        for service in (plan_check_service, live_check_service):
            with self.subTest(service=service.__name__), self._scenario(service) as scenario:
                scenario.context.account_id = None
                handler = service._handle_plan_operation if service is plan_check_service else service._handle_live_operation
                handler(scenario.context)
                self.assertEqual(["preflight"], self._states(scenario.events, "failed"))
                self.assertEqual("failed", scenario.finish.call_args.kwargs["status"])
                scenario.database.get_account.assert_not_called()
                scenario.network.assert_not_called()
                scenario.remote.assert_not_called()

    def test_plan_missing_token_fails_only_preflight(self):
        with self._scenario(plan_check_service) as scenario:
            scenario.database.get_account.return_value = {"email": "fixture@example.test"}
            plan_check_service._handle_plan_operation(scenario.context)
            self.assertEqual(["preflight"], self._states(scenario.events, "failed"))
            self.assertEqual("failed", scenario.finish.call_args.kwargs["status"])
            scenario.network.assert_not_called()
            scenario.remote.assert_not_called()

    def test_missing_saved_account_cancels_plan_without_failed_stage(self):
        with self._scenario(plan_check_service) as scenario:
            scenario.database.get_account.return_value = None
            plan_check_service._handle_plan_operation(scenario.context)
            self.assertEqual([], self._states(scenario.events, "failed"))
            self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])
            scenario.network.assert_not_called()
            scenario.remote.assert_not_called()

    def test_cancellation_before_preflight_does_not_report_failure(self):
        for service in (plan_check_service, live_check_service):
            with self.subTest(service=service.__name__), self._scenario(service) as scenario:
                scenario.context.checkpoint.side_effect = OperationCancelled("测试取消")
                result = self._run(service, scenario)
                self.assertTrue(result["cancelled"])
                self.assertEqual([], self._states(scenario.events, "failed"))
                self.assertEqual([], self._states(scenario.events, "success"))
                self.assertEqual("cancelled", scenario.finish.call_args.kwargs["status"])
                scenario.network.assert_not_called()
                scenario.remote.assert_not_called()

    def test_live_invalid_configuration_fails_only_preflight_for_both_reporters(self):
        for native in (True, False):
            with self.subTest(native=native), self._scenario(live_check_service, native=native) as scenario:
                with patch.object(live_check_service, "resolve_driver", side_effect=ValueError("无效驱动配置")):
                    result = self._run(live_check_service, scenario, driver=None)
                self.assertFalse(result["ok"])
                self.assertEqual(["preflight"], self._states(scenario.events, "failed"))
                self.assertEqual([], self._states(scenario.events, "success"))
                scenario.network.assert_not_called()
                scenario.remote.assert_not_called()

    def test_account_state_exception_fails_only_preflight(self):
        for service in (plan_check_service, live_check_service):
            with self.subTest(service=service.__name__), self._scenario(service) as scenario:
                marker = (
                    scenario.database.mark_account_plan_check_running
                    if service is plan_check_service
                    else scenario.database.mark_account_live_check_running
                )
                marker.side_effect = RuntimeError("账号状态检查异常")
                result = self._run(service, scenario)
                self.assertFalse(result["ok"])
                self.assertEqual(["preflight"], self._states(scenario.events, "failed"))
                scenario.network.assert_not_called()
                scenario.remote.assert_not_called()

    def test_registration_plan_closes_preflight_before_query(self):
        with self._scenario(plan_check_service, native=False) as scenario:
            result = plan_check_service.check_registration_account_plan(
                account_id=7,
                email="fixture@example.test",
                access_token="fixture-access-value",
                proxy="http://fixture.invalid:8080",
            )
            self.assertTrue(result["ok"])
            self.assertLess(
                scenario.execution.index(("preflight", "success")),
                scenario.execution.index(("remote_call", None)),
            )
            self.assertEqual([], self._states(scenario.events, "failed"))
            scenario.network.assert_not_called()

    def test_registration_plan_state_exception_does_not_report_unstarted_query_failed(self):
        with self._scenario(plan_check_service, native=False) as scenario:
            scenario.database.mark_account_plan_check_running.side_effect = RuntimeError("账号状态检查异常")
            result = plan_check_service.check_registration_account_plan(
                account_id=7,
                email="fixture@example.test",
                access_token="fixture-access-value",
                proxy="http://fixture.invalid:8080",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(["preflight"], self._states(scenario.events, "failed"))
            scenario.remote.assert_not_called()

    def test_codex_refresh_cancels_before_request_without_failed_preflight(self):
        service = codex_token_refresh_service
        for cancelled_by_checkpoint in (False, True):
            with self.subTest(cancelled_by_checkpoint=cancelled_by_checkpoint):
                report = Mock()
                checkpoint = Mock(side_effect=OperationCancelled("测试取消") if cancelled_by_checkpoint else None)
                expected_error = OperationCancelled if cancelled_by_checkpoint else service.TokenRefreshCancelledError
                with (
                    patch.object(service, "_load_credential", return_value=({}, "fixture-codex.json", "fixture-refresh-value")),
                    patch.object(service, "db") as database,
                    patch.object(service, "_request_refresh") as remote,
                ):
                    with self.assertRaises(expected_error):
                        service._perform_refresh(
                            "fixture-codex.json",
                            report=report,
                            checkpoint=checkpoint,
                            is_cancel_requested=lambda: not cancelled_by_checkpoint,
                        )
                events = [call.kwargs for call in report.call_args_list]
                self.assertEqual([], self._states(events, "failed"))
                self.assertTrue(any(
                    event.get("event_type") == "note.warning"
                    and event.get("stage") == "preflight"
                    and event.get("detail", {}).get("cancelled") is True
                    for event in events
                ))
                remote.assert_not_called()
                database.mark_codex_oauth_refresh.assert_not_called()

    def test_codex_native_handler_separates_safe_cancel_from_unknown_remote_result(self):
        service = codex_token_refresh_service
        for unknown in (False, True):
            with self.subTest(unknown=unknown):
                context = SimpleNamespace(
                    task_id=901,
                    run_id=902,
                    account_id=7,
                    email="fixture@example.test",
                    run={"data": {"credential_filename": "fixture-codex.json"}},
                    config_snapshot={},
                    report=Mock(),
                    checkpoint=Mock(),
                    is_cancel_requested=Mock(return_value=False),
                    finish=Mock(),
                    lease=Mock(side_effect=lambda **_kwargs: nullcontext()),
                )
                error = (
                    service.TokenRefreshRequestUnknownError("远端结果待确认")
                    if unknown else service.TokenRefreshCancelledError("请求发出前取消")
                )
                with (
                    patch.object(service, "_perform_refresh", side_effect=error),
                    patch.object(service, "operation_log_context", side_effect=lambda *_args, **_kwargs: nullcontext()),
                    patch.object(service, "_update_account_state") as update,
                    patch.object(service, "_mark_unknown") as mark_unknown,
                    patch.object(service, "_mark_refresh_failure") as mark_failed,
                ):
                    result = service._handle_operation_context(context)
                expected_status = "request_unknown" if unknown else "cancelled"
                self.assertEqual(expected_status, result.status)
                self.assertEqual(expected_status, update.call_args.kwargs["last_run_status"])
                mark_failed.assert_not_called()
                context.finish.assert_not_called()
                if unknown:
                    self.assertTrue(result.summary["reconcile_required"])
                    self.assertTrue(result.summary["action_dispatched"])
                    mark_unknown.assert_called_once()
                else:
                    self.assertTrue(result.summary["cancelled"])
                    mark_unknown.assert_not_called()


if __name__ == "__main__":
    unittest.main()
