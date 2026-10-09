"""验证邮箱换绑阶段事件与明确的业务结果一致，全程模拟外部依赖。"""
from contextlib import ExitStack, contextmanager, nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import email_change_service as service
from core.operation_runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost


class EmailChangeReportingTests(unittest.TestCase):
    @contextmanager
    def scenario(self):
        events = []
        real_begin = service.begin_change_with_optional_reauth
        context = SimpleNamespace(
            account_id=7, run_id=29, task_id=30, email="old@example.test",
            run={"data": {"email_source": "outlook"}, "trigger": "test"},
            config_snapshot={"email_change_enabled": True},
            report=Mock(side_effect=lambda **event: events.append(event)),
            checkpoint=Mock(), lease=Mock(return_value=nullcontext()),
            remote_request_started=Mock(), remote_request_receipt=Mock(),
        )
        session = Mock()
        route = SimpleNamespace(proxy_url="", public_dict=lambda: {}, release=Mock())
        begin = service.BeginChangeResult(session, "fixture-at", 123.0, False)
        with ExitStack() as stack:
            database = stack.enter_context(patch.object(service, "db"))
            database.get_account.return_value = {
                "email": context.email, "access_token": "fixture-at", "email_source": "outlook",
            }
            database.claim_account_email_change.return_value = True
            database.finish_account_email_change.return_value = True
            provider = stack.enter_context(patch.object(service, "email_provider"))
            provider.validate_email_source.return_value = "outlook"
            provider.acquire_email.return_value = "new@example.test"
            provider.wait_for_otp.return_value = "123456"
            provider.email_material_line.return_value = "fixture-material"
            proxy = stack.enter_context(patch.object(service, "acquire_account_proxy", return_value=route))
            stack.enter_context(patch.object(service, "_account_stable_identity", return_value=SimpleNamespace(session_payload=lambda: {})))
            session_factory = stack.enter_context(patch("core.session.BrowserSession", return_value=session))
            start = stack.enter_context(patch.object(service, "begin_change_with_optional_reauth", return_value=begin))
            protocol = stack.enter_context(patch.object(service, "EmailChangeProtocol"))
            stack.enter_context(patch("core.browser_traffic.record_unavailable"))
            release = stack.enter_context(patch.object(service, "_release_unconsumed"))
            readback = stack.enter_context(patch.object(service, "_safe_readback", return_value=True))
            closeout = stack.enter_context(patch.object(service, "_finalize_consumed_email", return_value={"status": "success"}))
            stack.enter_context(patch.object(service, "_enqueue_live_check_child", return_value={"accepted": False}))
            yield SimpleNamespace(
                context=context, events=events, db=database, provider=provider,
                proxy=proxy, session_factory=session_factory, begin=start,
                protocol=protocol.return_value, release=release, readback=readback,
                closeout=closeout,
                real_begin=real_begin,
            )

    @staticmethod
    def states(scenario):
        return [(event["stage"], event.get("state")) for event in scenario.events if event.get("state")]

    def test_mailbox_validation_failures_close_email_without_starting_network(self):
        for case in ("claimed", "empty", "same", "provider_error"):
            with self.subTest(case=case), self.scenario() as scenario:
                if case == "claimed":
                    scenario.db.claim_account_email_change.return_value = False
                elif case == "empty":
                    scenario.provider.acquire_email.return_value = ""
                elif case == "same":
                    scenario.provider.acquire_email.return_value = "OLD@example.test"
                else:
                    scenario.provider.acquire_email.side_effect = RuntimeError("EmailButler alice@example.test HTTP 502")
                result = service._handle_email_change(scenario.context)
                self.assertEqual("failed", result.status)
                self.assertEqual([("email", "running"), ("email", "failed")], self.states(scenario))
                scenario.proxy.assert_not_called()
                self.assertNotIn("alice@example.test", str(scenario.events))

    def test_route_or_session_prepare_failure_closes_network(self):
        for case in ("route", "session"):
            with self.subTest(case=case), self.scenario() as scenario:
                getattr(scenario, "proxy" if case == "route" else "session_factory").side_effect = RuntimeError("fixture-error")
                result = service._handle_email_change(scenario.context)
                self.assertEqual("failed", result.status)
                self.assertEqual([("email", "running"), ("email", "success"), ("network", "running"), ("network", "failed")], self.states(scenario))
                scenario.begin.assert_not_called()

    def test_explicit_begin_or_verify_rejection_closes_submission(self):
        for case in ("begin", "verify"):
            with self.subTest(case=case), self.scenario() as scenario:
                target = scenario.begin if case == "begin" else scenario.protocol.verify
                target.side_effect = service.RemoteRequestRejected("fixture-rejection", http_status=400)
                result = service._handle_email_change(scenario.context)
                self.assertEqual("failed", result.status)
                self.assertIn(("submit_email", "failed"), self.states(scenario))
                self.assertNotIn(("submit_email", "success"), self.states(scenario))

    def test_otp_timeout_closes_only_actual_otp_failure_and_keeps_remote_fence(self):
        with self.scenario() as scenario:
            scenario.provider.wait_for_otp.side_effect = TimeoutError("fixture-timeout")
            result = service._handle_email_change(scenario.context)
            self.assertEqual("request_unknown", result.status)
            self.assertIn(("email_otp", "failed"), self.states(scenario))
            self.assertNotIn(("submit_email", "failed"), self.states(scenario))
            scenario.release.assert_not_called()

    def test_otp_cancel_or_lease_loss_does_not_become_failure(self):
        for exception in (OperationCancelled("任务已取消"), OperationLeaseLost("租约丢失")):
            with self.subTest(exception=type(exception).__name__), self.scenario() as scenario:
                scenario.provider.wait_for_otp.side_effect = exception
                if isinstance(exception, OperationLeaseLost):
                    with self.assertRaises(OperationLeaseLost):
                        service._handle_email_change(scenario.context)
                else:
                    self.assertEqual("request_unknown", service._handle_email_change(scenario.context).status)
                    self.assertTrue(any(event.get("detail", {}).get("cancelled") for event in scenario.events))
                self.assertFalse(any(state == "failed" for _, state in self.states(scenario)))
                scenario.release.assert_not_called()

    def test_transport_unknown_does_not_close_submission_as_failed_or_success(self):
        with self.scenario() as scenario:
            scenario.protocol.verify.side_effect = ConnectionError("fixture-disconnect")
            self.assertEqual("request_unknown", service._handle_email_change(scenario.context).status)
            self.assertNotIn(("submit_email", "failed"), self.states(scenario))
            self.assertNotIn(("submit_email", "success"), self.states(scenario))
            scenario.release.assert_not_called()

    def test_cancel_during_begin_retains_mailbox_after_remote_intent(self):
        for phase in ("initial", "reauth"):
            with self.subTest(phase=phase), self.scenario() as scenario:
                scenario.begin.side_effect = scenario.real_begin
                scenario.protocol.begin.side_effect = (
                    OperationCancelled("远端请求中取消") if phase == "initial" else [
                        service.RemoteRequestRejected("reauth required", http_status=401),
                        OperationCancelled("远端请求中取消"),
                    ]
                )
                with patch.object(service, "perform_recent_login", return_value={"access_token": "fixture-at", "protocol_session": Mock()}):
                    result = service._handle_email_change(scenario.context)
                self.assertEqual("request_unknown", result.status)
                scenario.release.assert_not_called()
                self.assertNotIn(("submit_email", "failed"), self.states(scenario))
                self.assertEqual("unknown", scenario.context.remote_request_receipt.call_args.kwargs["outcome"])

    def test_local_writeback_unknown_keeps_confirmed_submission_success(self):
        with self.scenario() as scenario:
            scenario.readback.return_value = False
            self.assertEqual("request_unknown", service._handle_email_change(scenario.context).status)
            self.assertIn(("submit_email", "success"), self.states(scenario))
            self.assertIn(("complete", "running"), self.states(scenario))
            self.assertNotIn(("complete", "success"), self.states(scenario))
            scenario.closeout.assert_not_called()

    def test_confirmed_change_closes_writeback_and_retains_provider_warning(self):
        for closeout in ("success", "failed"):
            with self.subTest(closeout=closeout), self.scenario() as scenario:
                scenario.closeout.return_value = {"status": closeout}
                self.assertEqual("success", service._handle_email_change(scenario.context).status)
                self.assertEqual(("complete", "success"), self.states(scenario)[-1])
                self.assertFalse(any(state == "failed" for _, state in self.states(scenario)))
                self.assertEqual(closeout == "failed", any(event.get("level") == "warning" for event in scenario.events))


class RecentLoginReportingTests(unittest.TestCase):
    def test_recent_login_failure_or_success_before_second_rejection_has_own_end(self):
        for case in ("error", "missing_token", "missing_session", "reauth_ok"):
            with self.subTest(case=case):
                context = Mock(run_id=29)
                session = Mock()
                recent = {"access_token": "fixture-at", "protocol_session": session}
                if case == "missing_token":
                    recent.pop("access_token")
                elif case == "missing_session":
                    recent.pop("protocol_session")
                with patch.object(service, "EmailChangeProtocol") as protocol, patch.object(service, "perform_recent_login", return_value=recent) as login:
                    protocol.return_value.begin.side_effect = [
                        service.RemoteRequestRejected("reauth required", http_status=401),
                        service.RemoteRequestRejected("fixture rejection", http_status=400),
                    ]
                    if case == "error":
                        login.side_effect = RuntimeError("fixture-error")
                    with self.assertRaises(service.RemoteRequestRejected):
                        service.begin_change_with_optional_reauth(session, account_id=7, current_email="old@example.test", current_source="outlook", new_email="new@example.test", access_token="fixture-at", context=context)
                states = [(call.kwargs["stage"], call.kwargs.get("state")) for call in context.report.call_args_list]
                self.assertEqual([("login_password", "running"), ("login_password", "success" if case == "reauth_ok" else "failed")], states)
