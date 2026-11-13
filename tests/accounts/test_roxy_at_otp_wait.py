"""AT 独立等码观察页面，仅明确无邮件时在原会话重发一次。"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import time
import unittest
from unittest.mock import Mock, patch

from core.accounts.liveness.roxy import flow
from core.auth.browser.auth_context import AuthExecutionContext, execution_context
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.protocol.openai_auth import EmailOtpSendError
from core.auth.state_machine import StageBudget, StageTimeout
from core.email.email_butler.client import EmailButlerClientError
from core.email.forward_imap import ForwardIMAPNoMailTimeout
from core.operations.runtime import OperationCancelled


EMAIL = "otp-account@example.test"
OTP_URL = "https://auth.openai.com/email-verification"


def otp_page():
    return {"url": OTP_URL, "text": f"Enter the code sent to {EMAIL}",
            "inputs": [{"type": "text", "autocomplete": "one-time-code"}], "errors": []}


class AtOtpWaitTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.driver = Mock(current_url=OTP_URL)
        self.driver._otp_resend_receipt = None
        self.driver._browser_submission_receipt = None
        self.page = otp_page()
        self.snapshot = self.stack.enter_context(patch.object(flow, "_email_otp_page_state", side_effect=lambda _driver: deepcopy(self.page)))
        self.fetch = self.stack.enter_context(patch.object(flow, "wait_for_otp", return_value="fixture-code"))
        self.resend = self.stack.enter_context(patch.object(flow, "_click_resend_email_otp", return_value={
            "ok": True, "ui_ack": "confirmed", "requested_after_ts": 200.0}))
        self.submit = self.stack.enter_context(patch.object(flow, "_type_otp"))
        self.stack.enter_context(patch.object(flow, "_clear_otp_inputs"))
        self.stack.enter_context(patch.object(flow, "_click_continue"))
        self.confirmation = self.stack.enter_context(patch.object(flow, "_wait_after_email_otp_submit", return_value="accepted"))
        self.token = self.stack.enter_context(patch.object(flow, "_has_access_token", return_value=False))
        self.cancel = self.stack.enter_context(patch.object(flow, "check_cancelled"))

    def no_mail(self, status=None):
        return EmailButlerClientError("测试等待无邮件", error_code="inbound_code_timeout", status_code=status)

    def run_otp(self, **kwargs):
        return flow._complete_otp(self.driver, EMAIL, 100.0, **kwargs)

    @contextmanager
    def real_provider(self, side_effect):
        from config import email as email_config
        from core.email import provider
        from core.email.email_butler import client

        with (
            patch.object(flow, "wait_for_otp", provider.wait_for_otp),
            patch.multiple(email_config, USE_EMAIL_SERVICE=True, OTP_MAX_WAIT=80),
            patch.object(provider, "resolve_email_source", return_value="email_butler"),
            patch("core.email.derivation.find_binding", return_value=None),
            patch("core.auth.email_guard.current_session", return_value=None),
            patch("core.auth.email_guard.begin_generation"),
            patch.object(client, "fetch_latest_otp", side_effect=side_effect) as fetch,
        ):
            yield fetch

    @contextmanager
    def real_butler_transport(self, *, round_wait=80, on_request=None):
        from config import email as email_config
        from core.email import provider
        from core.email.email_butler import client, lease_bindings, v2

        base = "https://butler.example.test/v2"
        account = client.EmailButlerAccount(EMAIL, "fixture-mailbox", lease_id="lse_original",
                                           client_id="fixture-client", api_base=base, api_key="fixture-key")
        lease = {"id": "lse_original", "email": EMAIL, "service": "openai", "provider": "icloud_hme",
                 "client_id": "fixture-client", "status": "active", "created_at": "1970-01-01T00:00:00Z",
                 "expires_at": None}
        binding = {"lease_id": lease["id"], "client_id": lease["client_id"], "api_base": base}
        requests = []

        def request(method, url, **kwargs):
            requests.append((method, url, kwargs["timeout"]))
            if on_request is not None:
                on_request(method, url)
            if url.endswith("/me"):
                data = {"client_id": "fixture-client", "permissions": ["codes.read"],
                        "allowed_services": ["openai"], "limits": {}}
            elif url.endswith("/leases/lse_original"):
                data = lease
            else:
                self.assertEqual(base + "/leases/lse_original/code", url)
                data = {"lease_id": "lse_original", "service": "openai", "status": "matched",
                        "verification_code": "123456", "code_id": "code_fixture",
                        "received_at": "1970-01-01T00:03:20Z"}
            response = Mock(status_code=200)
            response.json.return_value = {"data": data, "request_id": "request_fixture"}
            return response

        with (
            patch.object(flow, "wait_for_otp", provider.wait_for_otp),
            patch.multiple(email_config, USE_EMAIL_SERVICE=True, OTP_MAX_WAIT=round_wait, EMAIL_BUTLER_REQUEST_TIMEOUT=20),
            patch.object(provider, "resolve_email_source", return_value="email_butler"),
            patch("core.email.derivation.find_binding", return_value=None),
            patch("core.auth.email_guard.current_session", return_value=None),
            patch("core.auth.email_guard.begin_generation"),
            patch.dict(client._CONTEXT_CACHE, {}, clear=True),
            patch.object(client, "get_account_context", return_value=account),
            patch.object(lease_bindings.records, "list_rows", return_value=[]),
            patch.object(lease_bindings, "save", return_value=binding),
            patch.object(v2.requests, "request", side_effect=request),
        ):
            yield requests

    def test_real_butler_lease_preflight_preserves_original_http_timeout_when_it_takes_over_two_seconds(self):
        now = [0.0]
        budget = StageBudget.start(900, clock=lambda: now[0])

        def slow_preflight(_method, url):
            if not url.endswith("/code"):
                now[0] += 3

        with self.real_butler_transport(on_request=slow_preflight) as requests, execution_context(AuthExecutionContext(budget=budget)):
            self.run_otp()
        self.assertEqual([30.0, 30.0], [item[2] for item in requests[:2]])
        self.assertTrue(requests[0][1].endswith("/me"))
        self.assertTrue(requests[1][1].endswith("/leases/lse_original"))
        self.assertEqual(20.0, requests[2][2])
        self.assertEqual(6, now[0])
        self.assertEqual(900, budget.deadline)
        self.resend.assert_not_called()
        self.submit.assert_called_once()

    def test_real_butler_lease_preflight_still_clamps_to_round_or_original_total_budget(self):
        for round_wait, total_wait, expected in ((5, 900, 5.0), (80, 9, 9.0)):
            with self.subTest(round_wait=round_wait, total_wait=total_wait):
                budget = StageBudget.start(total_wait, clock=lambda: 0.0)
                with self.real_butler_transport(round_wait=round_wait) as requests, execution_context(AuthExecutionContext(budget=budget)):
                    self.run_otp()
                self.assertEqual([expected, expected], [item[2] for item in requests[:2]])
                self.assertEqual(total_wait, budget.deadline)

    def test_shared_provider_default_keeps_two_second_cooperative_http_cap(self):
        from core.email import provider

        with self.real_butler_transport() as requests:
            self.assertEqual("123456", provider.wait_for_otp(EMAIL, after_ts=100.0, max_wait=80,
                page_checkpoint=lambda: None, budget=StageBudget.start(900)))
        self.assertEqual([2.0, 2.0, 2.0], [item[2] for item in requests])

    def test_real_butler_lease_preflight_cancellation_and_total_expiry_interrupt_before_next_request(self):
        for ending in ("cancelled", "budget_expired"):
            with self.subTest(ending=ending):
                now = [0.0]
                budget = StageBudget.start(900, clock=lambda: now[0])
                error = OperationCancelled("测试前置读取取消")

                def end_after_first_request(_method, _url):
                    if ending == "cancelled":
                        self.cancel.side_effect = error
                    else:
                        now[0] = 901

                try:
                    with (self.assertRaises(OperationCancelled if ending == "cancelled" else StageTimeout),
                          self.real_butler_transport(on_request=end_after_first_request) as requests,
                          execution_context(AuthExecutionContext(budget=budget))):
                        self.run_otp()
                finally:
                    self.cancel.side_effect = None
                self.assertEqual(1, len(requests))
                self.assertEqual(900, budget.deadline)
        self.resend.assert_not_called()
        self.submit.assert_not_called()

    def test_real_provider_keeps_eighty_second_rounds_with_a_nine_hundred_second_total(self):
        now = [0.0]
        rounds = []
        budget = StageBudget.start(900, clock=lambda: now[0])

        def fetch(_email, *, after_ts, max_wait):
            rounds.append((after_ts, max_wait))
            now[0] += max_wait
            if len(rounds) == 1:
                raise self.no_mail()
            return "fixture-code"

        with self.real_provider(fetch), execution_context(AuthExecutionContext(budget=budget)):
            self.run_otp()
        self.assertEqual([(100.0, 80), (200.0, 80)], rounds)
        self.assertEqual(160.0, now[0])
        self.assertEqual(900.0, budget.deadline)
        self.resend.assert_called_once()
        self.submit.assert_called_once()

    def test_real_provider_clamps_the_last_round_to_the_remaining_total_budget(self):
        now = [0.0]
        rounds = []
        budget = StageBudget.start(30, clock=lambda: now[0])

        def fetch(_email, *, after_ts, max_wait):
            rounds.append((after_ts, max_wait))
            now[0] += max_wait
            raise self.no_mail()

        with self.assertRaises(StageTimeout), self.real_provider(fetch), execution_context(AuthExecutionContext(budget=budget)):
            self.run_otp()
        self.assertEqual([(100.0, 30)], rounds)
        self.assertEqual(30.0, budget.deadline)
        self.resend.assert_not_called()

    def test_no_mail_resends_once_then_uses_click_time_and_same_total_budget(self):
        for error in (self.no_mail(), self.no_mail(408), ForwardIMAPNoMailTimeout("测试没有新邮件")):
            with self.subTest(error=type(error).__name__, status=getattr(error, "status_code", None)):
                self.fetch.reset_mock()
                self.resend.reset_mock()
                self.fetch.side_effect = [error, "fixture-code"]
                deadline = time.monotonic() + 300
                with execution_context(AuthExecutionContext(deadline=deadline)):
                    self.run_otp()
                self.assertEqual([100.0, 200.0], [call.kwargs["after_ts"] for call in self.fetch.call_args_list])
                self.assertTrue(all(call.kwargs["budget"].deadline == deadline for call in self.fetch.call_args_list))
                self.assertTrue(all(callable(call.kwargs["page_checkpoint"]) for call in self.fetch.call_args_list))
                self.resend.assert_called_once()
                self.assertEqual(deadline, self.resend.call_args.kwargs["budget"].deadline)
                self.driver.refresh.assert_not_called()
                self.driver.get.assert_not_called()

    def test_second_no_mail_keeps_original_error_and_never_resends_again(self):
        second = self.no_mail()
        self.fetch.side_effect = [self.no_mail(), second]
        with self.assertRaises(EmailButlerClientError) as caught:
            self.run_otp()
        self.assertIs(second, caught.exception)
        self.resend.assert_called_once()
        self.submit.assert_not_called()

    def test_other_mailbox_errors_are_not_resend_triggers(self):
        for code, status in (("source_authentication_failed", 408), ("recipient_mismatch", None),
                             ("butler_transport_timeout", None), ("inbound_code_timeout", 503)):
            with self.subTest(code=code, status=status):
                error = EmailButlerClientError("测试收件失败", error_code=code, status_code=status)
                self.fetch.side_effect = error
                with self.assertRaises(EmailButlerClientError) as caught:
                    self.run_otp()
                self.assertIs(error, caught.exception)
        self.resend.assert_not_called()

    def test_retryable_mailbox_preflight_connection_retries_once_in_same_window(self):
        for code in ("butler_transport_connection", "butler_transport_timeout", "butler_transport_failed"):
            with self.subTest(code=code):
                self.fetch.reset_mock()
                error = EmailButlerClientError("测试前置只读连接失败", error_code=code)
                error.retryable = True
                self.fetch.side_effect = [error, "fixture-code"]
                deadline = time.monotonic() + 300
                with execution_context(AuthExecutionContext(deadline=deadline)):
                    self.run_otp()
                self.assertEqual([100.0, 100.0], [call.kwargs["after_ts"] for call in self.fetch.call_args_list])
                self.assertTrue(all(call.kwargs["budget"].deadline == deadline for call in self.fetch.call_args_list))
        self.resend.assert_not_called()

    def test_repeated_mailbox_preflight_failure_and_untrusted_source_do_not_loop(self):
        first = EmailButlerClientError("测试临时连接失败", error_code="butler_transport_connection")
        first.retryable = True
        second = EmailButlerClientError("测试再次连接失败", error_code="butler_transport_connection")
        second.retryable = True
        self.fetch.side_effect = [first, second]
        with self.assertRaises(EmailButlerClientError) as caught:
            self.run_otp()
        self.assertIs(second, caught.exception)
        self.assertEqual(2, self.fetch.call_count)
        self.fetch.reset_mock()
        source = EmailButlerClientError("测试来源拒绝", error_code="source_authentication_failed")
        source.retryable = True
        self.fetch.side_effect = source
        with self.assertRaises(EmailButlerClientError) as caught:
            self.run_otp()
        self.assertIs(source, caught.exception)
        self.fetch.assert_called_once()
        self.resend.assert_not_called()

    def test_resend_ui_ack_unconfirmed_continues_wait_without_another_click(self):
        self.resend.return_value = {"ok": True, "ui_ack": "unconfirmed", "requested_after_ts": 201.0}
        self.fetch.side_effect = [self.no_mail(), "fixture-code"]
        self.run_otp()
        self.assertEqual([100.0, 201.0], [call.kwargs["after_ts"] for call in self.fetch.call_args_list])
        self.resend.assert_called_once()
        self.submit.assert_called_once()

    def test_resend_read_failure_after_dispatch_keeps_the_same_click_and_waits(self):
        def resend(*_args, **_kwargs):
            self.driver._otp_resend_receipt = {"clicked": True, "requested_after_ts": 202.0}
            raise RuntimeError("测试点击后读取未确认")

        self.resend.side_effect = resend
        self.fetch.side_effect = [self.no_mail(), "fixture-code"]
        self.run_otp()
        self.assertEqual([100.0, 202.0], [call.kwargs["after_ts"] for call in self.fetch.call_args_list])
        self.resend.assert_called_once()

    def test_explicit_resend_http_rejection_stops_with_actual_status(self):
        def resend(*_args, **_kwargs):
            self.driver._browser_submission_receipt = BrowserSubmissionReceipt(
                kind="otp", stage="otp_resend", endpoint_kind="otp_resend", http_method="POST",
                phase="response_observed", http_status=429, result="failure")
            return {"ok": True, "ui_ack": "unconfirmed", "requested_after_ts": 200.0}

        self.resend.side_effect = resend
        self.fetch.side_effect = self.no_mail()
        with self.assertRaises(EmailOtpSendError) as caught:
            self.run_otp()
        self.assertEqual(429, caught.exception.status_code)
        self.assertEqual("http_error", caught.exception.reason)
        self.fetch.assert_called_once()
        self.resend.assert_called_once()

    def test_late_resend_rejection_is_checked_through_real_provider_and_at_round_end(self):
        from core.email.mailbox_wait import cooperative_checkpoint

        for ending in ("checkpoint", "mail_timeout", "candidate"):
            with self.subTest(ending=ending):
                receipt = BrowserSubmissionReceipt(kind="otp", stage="otp_resend", endpoint_kind="otp_resend",
                                                   http_method="POST", phase="ui_dispatched")
                calls = []
                self.resend.reset_mock()

                def resend(*_args, **_kwargs):
                    self.driver._browser_submission_receipt = receipt
                    return {"ok": True, "ui_ack": "unconfirmed", "requested_after_ts": 200.0}

                def fetch(_email, **kwargs):
                    calls.append(kwargs["after_ts"])
                    if len(calls) == 1:
                        raise self.no_mail()
                    receipt.transition("response_observed", http_status=429, result="failure")
                    # 后续动作替换 driver 当前回执，原重发的迟到响应仍须由原对象核对。
                    self.driver._browser_submission_receipt = BrowserSubmissionReceipt(
                        kind="otp", stage="email_otp", endpoint_kind="otp_submit")
                    if ending == "checkpoint":
                        cooperative_checkpoint()
                    if ending == "mail_timeout":
                        raise self.no_mail()
                    return "fixture-code"

                self.resend.side_effect = resend
                with self.assertRaises(EmailOtpSendError) as caught, self.real_provider(fetch):
                    self.run_otp()
                self.assertEqual("http_error", caught.exception.reason)
                self.assertEqual(429, caught.exception.status_code)
                self.assertEqual([100.0, 200.0], calls)
                self.resend.assert_called_once()
        self.submit.assert_not_called()

    def test_new_login_ignores_old_resend_rejection_without_resetting_resend_limit(self):
        from core.email.mailbox_wait import cooperative_checkpoint

        for ending in ("candidate", "no_mail"):
            with self.subTest(ending=ending):
                old_receipt = BrowserSubmissionReceipt(kind="otp", stage="otp_resend", endpoint_kind="otp_resend",
                                                       http_method="POST", phase="ui_dispatched")
                calls = []
                self.page = otp_page()
                self.resend.reset_mock()
                self.submit.reset_mock()
                final_no_mail = self.no_mail()

                def resend(*_args, **_kwargs):
                    self.driver._browser_submission_receipt = old_receipt
                    return {"ok": True, "ui_ack": "unconfirmed", "requested_after_ts": 200.0}

                def login(*_args, **_kwargs):
                    self.page = otp_page()
                    self.driver._browser_submission_receipt = BrowserSubmissionReceipt(
                        kind="email", stage="submit_email", endpoint_kind="email_submit", phase="confirmed")
                    return "otp"

                def fetch(_email, **kwargs):
                    calls.append(kwargs["after_ts"])
                    if len(calls) == 1:
                        raise self.no_mail()
                    if len(calls) == 2:
                        self.page = {"url": "https://chatgpt.com/auth/login", "inputs": [{"type": "email"}], "text": "Log in"}
                        cooperative_checkpoint()
                        self.fail("邮箱入口应交回已有账号登录")
                    old_receipt.transition("response_observed", http_status=429, result="failure")
                    cooperative_checkpoint()
                    if ending == "no_mail":
                        raise final_no_mail
                    return "fixture-code"

                self.resend.side_effect = resend
                with (self.real_provider(fetch), patch.object(flow.time, "time", return_value=123.0),
                      patch.object(flow, "_login_existing_account_with_recovery", side_effect=login) as restart):
                    if ending == "candidate":
                        self.run_otp(password="fixture-password")
                        self.submit.assert_called_once()
                    else:
                        with self.assertRaises(EmailButlerClientError) as caught:
                            self.run_otp(password="fixture-password")
                        self.assertIs(final_no_mail, caught.exception)
                        self.submit.assert_not_called()
                self.assertEqual([100.0, 200.0, 123.0], calls)
                self.assertEqual(429, old_receipt.http_status)
                self.assertEqual("response_observed", old_receipt.phase)
                restart.assert_called_once()
                self.resend.assert_called_once()

    def test_no_mail_does_not_resend_on_an_untrusted_or_unmounted_otp_page(self):
        for page in ({**otp_page(), "url": "https://example.test/email-verification"},
                     {**otp_page(), "inputs": []}):
            with self.subTest(page=page):
                self.page = page
                error = self.no_mail()
                self.fetch.side_effect = error
                with self.assertRaises(EmailButlerClientError) as caught:
                    self.run_otp()
                self.assertIs(error, caught.exception)
        self.resend.assert_not_called()

    def test_current_page_identity_mismatch_prevents_resend(self):
        self.page["text"] = "Enter the code sent to another@example.test"
        self.fetch.side_effect = self.no_mail()
        with self.assertRaisesRegex(RuntimeError, "identity_mismatch") as caught:
            self.run_otp()
        self.assertEqual(("identity_mismatch", "auth"), flow._refresh_failure_cause(caught.exception, "email_otp"))
        self.resend.assert_not_called()

    def test_expired_page_during_wait_is_not_overridden_by_old_verified_text(self):
        self.page = {**otp_page(), "text": "Your session has expired. Email verified", "emailVerified": True}

        def wait(*_args, **kwargs):
            kwargs["page_checkpoint"]()

        self.fetch.side_effect = wait
        with self.assertRaisesRegex(flow._RoxyOtpSubmissionUnknown, "认证页面已失效"):
            self.run_otp()
        self.resend.assert_not_called()
        self.submit.assert_not_called()

    def test_email_verified_page_during_wait_hands_off_to_session_read(self):
        self.page = {**otp_page(), "text": "Email verified", "emailVerified": True}

        def wait(*_args, **kwargs):
            kwargs["page_checkpoint"]()

        self.fetch.side_effect = wait
        confirmed = Mock()
        self.run_otp(on_email_confirmed=confirmed)
        confirmed.assert_called_once()
        self.resend.assert_not_called()
        self.submit.assert_not_called()

    def test_authenticated_page_during_wait_hands_off_without_typing_or_resending(self):
        def wait(*_args, **kwargs):
            self.page = {"url": "https://chatgpt.com/", "inputs": [], "text": ""}
            self.driver.current_url = self.page["url"]
            self.token.return_value = True
            kwargs["page_checkpoint"]()
            self.fail("已登录页面应立即交回获取会话")

        self.fetch.side_effect = wait
        confirmed = Mock()
        self.run_otp(on_email_confirmed=confirmed)
        confirmed.assert_called_once()
        self.submit.assert_not_called()
        self.resend.assert_not_called()

    def test_totp_page_during_wait_hands_off_to_existing_challenge(self):
        def wait(*_args, **kwargs):
            self.page = {"url": "https://auth.openai.com/mfa", "text": "Authenticator code",
                         "inputs": [{"type": "text", "name": "totp", "autocomplete": "one-time-code"}]}
            kwargs["page_checkpoint"]()

        self.fetch.side_effect = wait
        confirmed = Mock()
        with patch("core.codex.roxy.oauth.complete_openai_login_challenge", return_value="advanced") as challenge:
            self.run_otp(totp_secret="fixture-secret", on_email_confirmed=confirmed)
        challenge.assert_called_once_with(self.driver, EMAIL, "", "fixture-secret", timeout=45,
                                          page_classifier=flow._classify_at_login_page)
        confirmed.assert_called_once()
        self.submit.assert_not_called()
        self.resend.assert_not_called()

    def test_email_entry_during_wait_reuses_login_and_updates_mail_time(self):
        def first_wait(*_args, **kwargs):
            self.page = {"url": "https://chatgpt.com/auth/login", "inputs": [{"type": "email", "value": ""}], "text": "Log in"}
            kwargs["page_checkpoint"]()

        def login(*_args, **_kwargs):
            self.page = otp_page()
            return "otp"

        calls = 0

        def wait(*args, **kwargs):
            nonlocal calls
            calls += 1
            return first_wait(*args, **kwargs) if calls == 1 else "fixture-code"

        self.fetch.side_effect = wait
        with patch.object(flow, "_login_existing_account_with_recovery", side_effect=login) as restart, \
                patch.object(flow.time, "time", return_value=123.0):
            self.run_otp(password="fixture-password", totp_secret="fixture-secret")
        self.assertEqual([100.0, 123.0], [call.kwargs["after_ts"] for call in self.fetch.call_args_list])
        restart.assert_called_once()
        self.assertEqual("fixture-password", restart.call_args.kwargs["password"])
        self.resend.assert_not_called()

    def test_cancellation_and_existing_budget_expiry_interrupt_mail_wait(self):
        for error in (OperationCancelled("测试取消"), StageTimeout("测试原阶段预算结束")):
            with self.subTest(error=type(error).__name__):
                def wait(*_args, **kwargs):
                    self.cancel.side_effect = error
                    kwargs["page_checkpoint"]()

                self.fetch.side_effect = wait
                with self.assertRaises(type(error)) as caught:
                    self.run_otp()
                self.assertIs(error, caught.exception)
                self.cancel.side_effect = None
        self.resend.assert_not_called()

    def test_expired_original_budget_cannot_be_replaced_by_resend_budget(self):
        now = [0.0]
        budget = StageBudget.start(30, clock=lambda: now[0])

        def wait(*_args, **kwargs):
            now[0] = 31.0
            kwargs["page_checkpoint"]()

        self.fetch.side_effect = wait
        with self.assertRaises(StageTimeout), execution_context(AuthExecutionContext(budget=budget)):
            self.run_otp()
        self.resend.assert_not_called()

