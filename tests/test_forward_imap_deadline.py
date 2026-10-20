# -*- coding: utf-8 -*-
import socket
import threading
import time
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import Mock, patch

from core import forward_imap_client as client


class _Clock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class _Socket:
    def __init__(self, interrupted=None):
        self.timeouts = []
        self.closed = threading.Event()
        self.interrupted = interrupted

    def settimeout(self, seconds):
        self.timeouts.append(seconds)

    def shutdown(self, _how):
        if self.interrupted is not None:
            self.interrupted.set()

    def close(self):
        self.closed.set()


class _Stream:
    def __init__(self):
        self.closed = threading.Event()

    def close(self):
        self.closed.set()


class _Mail:
    def __init__(self, interrupted=None):
        self.sock = _Socket(interrupted)
        self.file = _Stream()
        self.logout = Mock(side_effect=AssertionError("成功收码不应等待 LOGOUT"))

    def noop(self):
        return "OK", []


def _message(recipient="alias@icloud.com", code="654321", received="10-Oct-2026 02:13:31 +0000"):
    msg = EmailMessage()
    msg["From"] = "OpenAI <noreply@openai.com>"
    msg["To"] = recipient
    msg["Subject"] = f"Your ChatGPT code is {code}"
    msg.set_content(f"Your code is {code}")
    return "OK", [(f'1 (INTERNALDATE "{received}" BODY[] {{1}}'.encode(), msg.as_bytes())]


class ForwardIMAPDeadlineTests(unittest.TestCase):
    def test_connect_login_and_select_share_remaining_budget(self):
        clock = _Clock()
        mail = _Mail()

        def construct(*_args, **kwargs):
            self.assertEqual(kwargs["timeout"], 8)
            clock.advance(4)
            return mail

        def login(*_args):
            clock.advance(2)
            return "OK", []

        def select(*_args, **kwargs):
            self.assertTrue(kwargs["readonly"])
            clock.advance(1)
            return "OK", []

        mail.login, mail.select = login, select
        with (
            patch.object(client.time, "monotonic", side_effect=clock.monotonic),
            patch.object(client, "_settings", return_value=("imap.example.test", 993, "user", "secret")),
            patch.object(client.imaplib, "IMAP4_SSL", side_effect=construct),
        ):
            budget = client._IMAPBudget(8)
            self.assertIs(client._connect(budget=budget), mail)
            self.assertEqual(budget.remaining(), 1)
        self.assertEqual(mail.sock.timeouts, [4, 2])
        client._close_imap(mail)

    def test_late_otp_is_rejected_and_connection_is_closed(self):
        clock = _Clock()
        mail = _Mail()

        def slow_probe(*_args, **_kwargs):
            clock.advance(161.314)
            return "654321"

        with (
            patch.object(client.time, "monotonic", side_effect=clock.monotonic),
            patch.object(client, "_connect", return_value=mail),
            patch.object(client, "_latest_forwarded_otp", side_effect=slow_probe),
            self.assertLogs(client.logger, level="INFO") as logs,
        ):
            with self.assertRaises(client.ForwardIMAPError) as caught:
                client._fetch_latest_otp_local("alias@icloud.com", 0, max_wait=80)
        self.assertNotIsInstance(caught.exception, client.ForwardIMAPNoMailTimeout)
        self.assertTrue(mail.sock.closed.is_set())
        self.assertTrue(mail.file.closed.wait(0.5))
        self.assertNotIn("alias@icloud.com", "\n".join(logs.output))
        self.assertNotIn("654321", "\n".join(logs.output))

    def test_success_returns_without_logout_and_closes_resources(self):
        mail = _Mail()
        with (
            patch.object(client, "_connect", return_value=mail),
            patch.object(client, "_latest_forwarded_otp", return_value="654321"),
        ):
            result = client._fetch_latest_otp_local("alias@icloud.com", 0, max_wait=80)
        self.assertEqual(result, "654321")
        mail.logout.assert_not_called()
        self.assertTrue(mail.sock.closed.is_set())
        self.assertTrue(mail.file.closed.is_set())

    def test_connection_returning_after_deadline_is_closed(self):
        release = threading.Event()
        mail = _Mail()

        def delayed_connection(*_args, **_kwargs):
            release.wait(1)
            return mail

        with (
            patch.object(client, "_settings", return_value=("imap.example.test", 993, "user", "secret")),
            patch.object(client.imaplib, "IMAP4_SSL", side_effect=delayed_connection),
        ):
            started = time.monotonic()
            try:
                with self.assertRaises(client._IMAPDeadlineExceeded):
                    client._connect(budget=client._IMAPBudget(0.03))
                self.assertLess(time.monotonic() - started, 0.5)
            finally:
                release.set()
            self.assertTrue(mail.file.closed.wait(0.5))
        self.assertTrue(mail.sock.closed.is_set())

    def test_blocked_read_is_interrupted_and_cleanup_does_not_wait_for_logout(self):
        interrupted = threading.Event()
        mail = _Mail(interrupted)

        def stalled_read():
            interrupted.wait(1)
            raise OSError("已中断")

        started = time.monotonic()
        with self.assertRaises(client._IMAPDeadlineExceeded):
            client._IMAPBudget(0.03).call("FETCH", stalled_read, mail=mail)
        client._close_imap(mail)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(interrupted.is_set())
        self.assertTrue(mail.file.closed.wait(0.5))
        mail.logout.assert_not_called()

    def test_noncompliant_read_defers_file_cleanup_until_worker_finishes(self):
        release = threading.Event()
        mail = _Mail()

        def stalled_read():
            release.wait(1)
            return "late"

        try:
            with self.assertRaises(client._IMAPDeadlineExceeded):
                client._IMAPBudget(0.03).call("FETCH", stalled_read, mail=mail)
            client._close_imap(mail)
            self.assertTrue(mail.sock.closed.is_set())
            self.assertFalse(mail.file.closed.is_set())
        finally:
            release.set()
        self.assertTrue(mail.file.closed.wait(0.5))

    def test_continuous_response_fragments_cannot_extend_total_deadline(self):
        reader, writer = socket.socketpair()
        stopped = threading.Event()
        writing = threading.Event()
        mail = _Mail()
        mail.sock = reader
        mail.file = reader.makefile("rb")

        def drip_response():
            try:
                while not stopped.is_set():
                    writer.sendall(b"x")
                    writing.set()
                    stopped.wait(0.003)
            except OSError:
                pass

        sender = threading.Thread(target=drip_response, daemon=True)
        sender.start()
        try:
            self.assertTrue(writing.wait(0.5))
            started = time.monotonic()
            with self.assertRaises(client._IMAPDeadlineExceeded):
                client._IMAPBudget(0.05).call("FETCH", mail.file.readline, mail=mail)
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertTrue(mail._forward_imap_pending_io.wait(0.5))
            client._close_imap(mail)
            self.assertTrue(mail.file.closed)
        finally:
            stopped.set()
            writer.close()
            sender.join(0.5)
            client._close_imap(mail)

    def test_capacity_wait_expires_without_starting_another_network_worker(self):
        slots = threading.BoundedSemaphore(1)
        slots.acquire()
        operation = Mock()
        with patch.object(client, "_IMAP_IO_SLOTS", slots):
            try:
                with self.assertRaises(client._IMAPDeadlineExceeded):
                    client._IMAPBudget(0.02).call("SEARCH", operation)
            finally:
                slots.release()
            self.assertEqual(client._IMAPBudget(1).call("NOOP", lambda: "ok"), "ok")
        operation.assert_not_called()

    def test_searches_use_same_deadline_and_stop_before_next_header(self):
        clock = _Clock()
        mail = _Mail()
        searches = []

        def search(*args):
            searches.append(args)
            clock.advance(1.2)
            return "OK", [b"1"]

        mail.search = search
        mail.fetch = Mock()
        with patch.object(client.time, "monotonic", side_effect=clock.monotonic):
            with self.assertRaises(client._IMAPDeadlineExceeded):
                client._latest_forwarded_otp(mail, "alias@icloud.com", 0, budget=client._IMAPBudget(3))
        self.assertEqual(len(searches), 3)
        mail.fetch.assert_not_called()

    def test_latest_valid_candidate_ends_fetching_and_uses_peek(self):
        mail = _Mail()
        mail.search = Mock(return_value=("OK", [b"2 1 3"]))
        mail.fetch = Mock(return_value=_message())
        with self.assertLogs(client.logger, level="INFO") as logs:
            result = client._latest_forwarded_otp(mail, "alias@icloud.com", 0, budget=client._IMAPBudget(10))
        self.assertEqual(result, "654321")
        self.assertEqual(mail.search.call_count, 7)
        mail.fetch.assert_called_once_with(b"3", "(INTERNALDATE BODY.PEEK[])")
        text = "\n".join(logs.output)
        self.assertIn("SEARCH/To", text)
        self.assertIn("匹配数量=3", text)
        self.assertIn("阶段=FETCH", text)
        self.assertNotIn("alias@icloud.com", text)
        self.assertNotIn("654321", text)
        client._close_imap(mail)

    def test_fetch_crossing_deadline_cannot_return_a_valid_code(self):
        clock = _Clock()
        mail = _Mail()
        mail.search = Mock(return_value=("OK", [b"1"]))

        def slow_fetch(*_args):
            clock.advance(81)
            return _message()

        mail.fetch = slow_fetch
        with patch.object(client.time, "monotonic", side_effect=clock.monotonic):
            with self.assertRaises(client._IMAPDeadlineExceeded):
                client._latest_forwarded_otp(mail, "alias@icloud.com", 0, budget=client._IMAPBudget(80))
        self.assertTrue(mail.sock.closed.is_set())
        self.assertTrue(mail.file.closed.wait(0.5))

    def test_progressive_fetch_keeps_exact_recipient_and_delivery_cutoff_filters(self):
        mail = _Mail()
        mail.search = Mock(return_value=("OK", [b"1 2 3"]))
        mail.fetch = Mock(side_effect=[
            _message("other-alias@icloud.com", "111111"),
            _message("alias@icloud.com", "222222", "10-Oct-2026 02:13:10 +0000"),
            _message("alias@icloud.com", "333333"),
        ])
        after = datetime(2026, 10, 10, 2, 13, 25, tzinfo=timezone.utc).timestamp()
        result = client._latest_forwarded_otp(mail, "alias@icloud.com", after, budget=client._IMAPBudget(10))
        self.assertEqual(result, "333333")
        self.assertEqual([call.args[0] for call in mail.fetch.call_args_list], [b"3", b"2", b"1"])
        client._close_imap(mail)

    def test_login_failure_closes_connected_mailbox(self):
        mail = _Mail()
        mail.login = Mock(side_effect=client.imaplib.IMAP4.error("登录失败"))
        with (
            patch.object(client, "_settings", return_value=("imap.example.test", 993, "user", "secret")),
            patch.object(client.imaplib, "IMAP4_SSL", return_value=mail),
        ):
            with self.assertRaises(client.ForwardIMAPError):
                client._connect(budget=client._IMAPBudget(2))
        self.assertTrue(mail.sock.closed.is_set())
        self.assertTrue(mail.file.closed.is_set())


if __name__ == "__main__":
    unittest.main()
