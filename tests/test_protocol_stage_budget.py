"""协议注册阶段预算与一次性回调的离线故障注入。"""
from contextlib import ExitStack
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import MagicMock, patch

from core import account_export, email_provider, mailbox_wait
from core.registration import protocol
from core.registration.state_machine import CancellationRequested, StageBudget, StageTimeout


class ProtocolStageBudgetTests(unittest.TestCase):
    def test_callback_completed_session_retry_does_not_replay_callback(self):
        now = [10.0]
        budget = StageBudget.start(20, clock=lambda: now[0])
        with ExitStack() as stack:
            callback = stack.enter_context(patch.object(protocol, "follow_oauth_callback", return_value="https://chatgpt.com/"))
            fetch = stack.enter_context(patch.object(protocol, "fetch_session", side_effect=[TimeoutError("临时读取失败"), {"accessToken": "offline"}]))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch("core.registration.state_machine.time.sleep", side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)))
            result = protocol._finalize_registration_session(object(), "https://auth.openai.com/continue", "test@example.com", budget=budget)
        self.assertEqual(result[1], "offline")
        callback.assert_called_once()
        self.assertEqual(fetch.call_count, 2)
        self.assertLess(fetch.call_args_list[1].kwargs["timeout"], fetch.call_args_list[0].kwargs["timeout"])
        self.assertEqual(callback.call_args.kwargs["timeout"], 20)

    def test_callback_unknown_result_is_not_replayed(self):
        with patch.object(protocol, "follow_oauth_callback", side_effect=TimeoutError("响应丢失")) as callback, patch.object(protocol, "fetch_session") as fetch:
            with self.assertRaisesRegex(RuntimeError, "结果未知"):
                protocol._finalize_registration_session(object(), "https://auth.openai.com/continue", "test@example.com")
        callback.assert_called_once()
        fetch.assert_not_called()

    def test_callback_server_failure_is_still_unknown_and_not_replayed(self):
        error = RuntimeError("远端错误")
        error.response = SimpleNamespace(url="https://chatgpt.com/api/auth/callback/openai", status_code=503, text="")
        with patch.object(protocol, "follow_oauth_callback", side_effect=error) as callback, patch.object(protocol, "fetch_session") as fetch:
            with self.assertRaisesRegex(RuntimeError, "结果未知"):
                protocol._finalize_registration_session(object(), "https://auth.openai.com/continue", "test@example.com")
        callback.assert_called_once()
        fetch.assert_not_called()

    def test_callback_explicit_terminal_rejection_stops(self):
        response = SimpleNamespace(url="https://chatgpt.com/api/auth/callback/openai", status_code=400, text="")
        error = RuntimeError("明确拒绝")
        error.response = response
        with patch.object(protocol, "follow_oauth_callback", side_effect=error) as callback, patch.object(protocol, "fetch_session") as fetch:
            with self.assertRaisesRegex(RuntimeError, "AUTH_ERROR"):
                protocol._finalize_registration_session(object(), "https://auth.openai.com/continue", "test@example.com")
        callback.assert_called_once()
        fetch.assert_not_called()

    def test_callback_cancelled_is_not_wrapped_or_retried(self):
        error = CancellationRequested("已停止")
        with patch.object(protocol, "follow_oauth_callback", side_effect=error) as callback:
            with self.assertRaises(CancellationRequested) as raised:
                protocol._finalize_registration_session(object(), "https://auth.openai.com/continue", "test@example.com")
        self.assertIs(raised.exception, error)
        callback.assert_called_once()

    def test_session_late_result_does_not_escape_stage_deadline(self):
        now = [0.0]
        budget = StageBudget.start(2, clock=lambda: now[0])
        def late_result(*args, **kwargs):
            now[0] = 3
            return {"accessToken": "offline"}
        with patch.object(protocol, "follow_oauth_callback", return_value="https://chatgpt.com/"), patch.object(protocol, "human_delay"), patch.object(protocol, "fetch_session", side_effect=late_result):
            with self.assertRaises(StageTimeout):
                protocol._finalize_registration_session(object(), "https://auth.openai.com/continue", "test@example.com", budget=budget)

    def test_remaining_time_reaches_actual_callback_and_session_request(self):
        session = MagicMock()
        response = session.get.return_value
        response.url = "https://chatgpt.com/"
        response.json.return_value = {"accessToken": "offline"}
        account_export.follow_oauth_callback(session, "https://auth.openai.com/continue", timeout=1.25)
        self.assertEqual(session.get.call_args.kwargs["timeout"], 1.25)
        account_export.fetch_session(session, timeout=0.5)
        self.assertEqual(session.get.call_args.kwargs["timeout"], 0.5)

    def test_budget_sleep_observes_cancellation_before_full_delay(self):
        now = [0.0]
        cancelled = [False]
        budget = StageBudget.start(10, clock=lambda: now[0], cancel=lambda: cancelled[0])
        def sleeper(seconds):
            self.assertLessEqual(seconds, 0.1)
            now[0] += seconds
            cancelled[0] = True
        with self.assertRaises(CancellationRequested):
            budget.sleep(5, sleeper=sleeper)
        self.assertLessEqual(now[0], 0.1)

    def test_mailbox_timeout_context_and_reset(self):
        now = [0.0]
        budget = StageBudget.start(2, clock=lambda: now[0])
        self.assertEqual(mailbox_wait.bounded_timeout(30), 30)
        with mailbox_wait.use_budget(budget):
            self.assertEqual(mailbox_wait.bounded_timeout(30), 2)
            self.assertEqual(mailbox_wait.bounded_timeout(0), 2)
            self.assertEqual(mailbox_wait.bounded_timeout((0, None)), (1, 1))
            now[0] = 1.75
            self.assertEqual(mailbox_wait.bounded_timeout(30), 0.25)
        self.assertIsNone(mailbox_wait.current_budget())

    def test_imap_connect_cancel_closes_socket(self):
        from core import forward_imap_client
        mail = MagicMock()
        mail.login.side_effect = CancellationRequested("已停止")
        with patch.object(forward_imap_client, "_settings", return_value=("localhost", 993, "local", "offline")), patch.object(forward_imap_client.imaplib, "IMAP4_SSL", return_value=mail):
            with self.assertRaises(CancellationRequested):
                forward_imap_client._connect()
        mail.sock.close.assert_called_once()

    def test_dispatch_keeps_same_deadline_across_otp_waits(self):
        now = [0.0]
        budget = StageBudget.start(5, clock=lambda: now[0])
        seen = []
        def provider(*args, **kwargs):
            seen.append((kwargs["max_wait"], mailbox_wait.current_budget()))
            now[0] += 2
            return "123456"
        with patch("core.gptmail_client.fetch_latest_otp", side_effect=provider), patch("config.email.USE_EMAIL_SERVICE", True):
            email_provider.wait_for_otp("test@example.com", 0, email_source="gptmail", budget=budget)
            email_provider.wait_for_otp("test@example.com", 0, email_source="gptmail", budget=budget)
        self.assertEqual([item[0] for item in seen], [5, 3])
        self.assertTrue(all(item[1] is budget for item in seen))
        self.assertIsNone(mailbox_wait.current_budget())

    def test_provider_late_result_and_exception_reset_context(self):
        now = [0.0]
        budget = StageBudget.start(1, clock=lambda: now[0])
        def provider(*args, **kwargs):
            now[0] = 2
            return "123456"
        with patch("core.gptmail_client.fetch_latest_otp", side_effect=provider), patch("config.email.USE_EMAIL_SERVICE", True):
            with self.assertRaises(StageTimeout):
                email_provider.wait_for_otp("test@example.com", 0, email_source="gptmail", budget=budget)
        self.assertIsNone(mailbox_wait.current_budget())

    def test_gptmail_network_timeout_follows_remaining_budget(self):
        from core import gptmail_client
        response = MagicMock(status_code=200)
        response.json.return_value = {"success": True, "data": {"emails": []}}
        with mailbox_wait.use_budget(StageBudget.start(0.25)), patch.object(gptmail_client, "_headers", return_value={}), patch.object(gptmail_client.requests, "get", return_value=response) as request:
            gptmail_client._get("/api/emails")
        self.assertGreater(request.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(request.call_args.kwargs["timeout"], 0.25)

    def test_imap_parent_cancel_aborts_existing_bounded_io(self):
        from core import forward_imap_client
        cancelled = [False]
        started = threading.Event()
        release = threading.Event()
        budget = StageBudget.start(10, cancel=lambda: cancelled[0])
        mail = MagicMock()
        def blocking_read():
            cancelled[0] = True
            started.set()
            release.wait(2)
            return "晚到结果"
        try:
            with mailbox_wait.use_budget(budget):
                imap_budget = forward_imap_client._IMAPBudget(10)
                with self.assertRaises(CancellationRequested):
                    imap_budget.call("读取", blocking_read, mail=mail)
            self.assertTrue(started.is_set())
            mail.sock.shutdown.assert_called_once()
        finally:
            release.set()

    def test_manual_wait_cancel_clears_waiting_without_blocking_input(self):
        from core import manual_otp
        cancelled = [False]
        budget = StageBudget.start(10, cancel=lambda: cancelled[0])
        event = MagicMock()
        def cancel_on_wait(*args, **kwargs):
            self.assertLessEqual(kwargs["timeout"], 0.1)
            cancelled[0] = True
            return False
        event.wait.side_effect = cancel_on_wait
        with ExitStack() as stack:
            stack.enter_context(mailbox_wait.use_budget(budget))
            stack.enter_context(patch.object(manual_otp, "pop_manual_otp", return_value=None))
            stack.enter_context(patch.object(manual_otp, "mark_waiting"))
            clear = stack.enter_context(patch.object(manual_otp, "clear_waiting"))
            stack.enter_context(patch.object(manual_otp, "_event_for", return_value=event))
            stack.enter_context(patch("sys.stdin", SimpleNamespace(isatty=lambda: False)))
            stack.enter_context(patch("core.registration_service.check_stop_requested"))
            with self.assertRaises(CancellationRequested):
                manual_otp.wait_for_manual_otp("test@example.com")
        clear.assert_called_once_with("test@example.com")

    def test_provider_cancellation_is_not_wrapped_and_context_is_reset(self):
        error = CancellationRequested("已停止")
        with patch("core.gptmail_client.fetch_latest_otp", side_effect=error), patch("config.email.USE_EMAIL_SERVICE", True):
            with self.assertRaises(CancellationRequested) as raised:
                email_provider.wait_for_otp("test@example.com", 0, email_source="gptmail", budget=StageBudget.start(5))
        self.assertIs(raised.exception, error)
        self.assertIsNone(mailbox_wait.current_budget())

    def test_qq_imap_login_and_select_cancel_close_local_resources(self):
        from core import qqmail_client
        for method in ("login", "select"):
            with self.subTest(method=method):
                mail = MagicMock()
                getattr(mail, method).side_effect = CancellationRequested("已停止")
                with mailbox_wait.use_budget(StageBudget.start(10)), patch.object(qqmail_client._email_cfg, "QQ_EMAIL", "fixture@example.test"), patch.object(qqmail_client._email_cfg, "QQ_IMAP_PASSWORD", "fixture"), patch.object(qqmail_client.imaplib, "IMAP4_SSL", return_value=mail):
                    with self.assertRaises(CancellationRequested):
                        qqmail_client._connect_imap()
                mail.sock.close.assert_called_once()
                mail.file.close.assert_called_once()
                mail.logout.assert_not_called()

    def test_cloudmail_token_cancel_is_not_retried_or_wrapped(self):
        from core import cloudmail_client
        error = CancellationRequested("已停止")
        with patch.object(cloudmail_client.requests, "post", side_effect=error) as request:
            with self.assertRaises(CancellationRequested) as raised:
                cloudmail_client.gen_token(email="fixture@example.test", password="fixture", base_url="https://fixture.invalid")
        self.assertIs(raised.exception, error)
        request.assert_called_once()

    def test_imap_cancel_after_worker_completed_closes_unclaimed_connection(self):
        from core import forward_imap_client
        cancelled = [False]
        done = [False]
        finished = SimpleNamespace(set=lambda: done.__setitem__(0, True), is_set=lambda: done[0])
        def wait(timeout):
            self.assertTrue(done[0])
            cancelled[0] = True
            return False
        finished.wait = wait
        abandoned = threading.Event()
        connection = SimpleNamespace(sock=MagicMock(), file=MagicMock())
        def thread_factory(*, target, **kwargs):
            return SimpleNamespace(start=target)
        budget = StageBudget.start(10, cancel=lambda: cancelled[0])
        with mailbox_wait.use_budget(budget), patch.object(forward_imap_client.threading, "Event", side_effect=[finished, abandoned]), patch.object(forward_imap_client.threading, "Thread", side_effect=thread_factory):
            imap_budget = forward_imap_client._IMAPBudget(10)
            with self.assertRaises(CancellationRequested):
                imap_budget.call("连接", lambda: connection, connection_result=True)
        connection.sock.close.assert_called_once()
        connection.file.close.assert_called_once()

    def test_imap_slot_wait_checks_parent_cancel_in_short_segments(self):
        from core import forward_imap_client
        cancelled = [False]
        slots = MagicMock()
        def occupied(*, timeout):
            self.assertLessEqual(timeout, 0.1)
            cancelled[0] = True
            return False
        slots.acquire.side_effect = occupied
        with mailbox_wait.use_budget(StageBudget.start(10, cancel=lambda: cancelled[0])), patch.object(forward_imap_client, "_IMAP_IO_SLOTS", slots):
            with self.assertRaises(CancellationRequested):
                forward_imap_client._IMAPBudget(10).call("等待槽位", lambda: self.fail("不应进入 I/O"))
        slots.acquire.assert_called_once()
        slots.release.assert_not_called()


if __name__ == "__main__":
    unittest.main()
