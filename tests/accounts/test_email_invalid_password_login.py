# -*- coding: utf-8 -*-
"""失效邮箱刷新 AT 时优先使用保存密码和 TOTP，不连接真实账号或数据库。"""
from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


EMAIL = "fixture@example.test"
OTP_URL = "https://auth.openai.com/email-verification"
PASSWORD_URL = "https://auth.openai.com/log-in/password"
MFA_URL = "https://auth.openai.com/mfa-challenge/factor-fixture"


class _Response:
    def __init__(self, url: str, text: str = "", status_code: int = 200):
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": "text/html"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self):
        self.proxy = ""
        self.session = MagicMock()
        self.get = MagicMock()

    def get_auth_headers(self, referer=""):
        return {"referer": referer}

    def get_auth_navigate_headers(self, referer="", **_kwargs):
        return {"referer": referer}


class AccountEmailInvalidPolicyTests(unittest.TestCase):
    def test_policy_reads_account_flag_without_changing_account(self):
        from core.accounts.credentials import account_email_is_invalid

        for account, expected in (
            ({"email_invalid": True}, True),
            ({"email_invalid": False}, False),
            ({}, False),
            (None, False),
        ):
            with self.subTest(account=account), patch(
                "core.db.get_account_by_email", return_value=account,
            ) as get_account:
                self.assertIs(account_email_is_invalid(EMAIL), expected)
                get_account.assert_called_once_with(EMAIL)


class OfferedPasswordLoginTests(unittest.TestCase):
    def test_uses_offered_same_origin_login_link_and_preserves_query(self):
        from core.accounts.liveness.protocol import v2 as v2

        session = _Session()
        target = PASSWORD_URL + "?state=fixture&mode=login"
        session.get.side_effect = [
            _Response(OTP_URL, '<a href="/log-in/password?state=fixture&amp;mode=login">使用密码</a>'),
            _Response(target, '<input type="password">'),
        ]

        result = v2._open_offered_password_login(session, OTP_URL)

        self.assertEqual(target, result)
        self.assertEqual([OTP_URL, target], [call.args[0] for call in session.get.call_args_list])

    def test_unoffered_or_untrusted_links_only_try_standard_login_route(self):
        from core.accounts.liveness.protocol import v2 as v2

        for html in (
            '<p>请输入验证码</p>',
            '<a href="https://other.example/log-in/password">使用密码</a>',
            '<a href="https://auth.openai.com.other.example/log-in/password">使用密码</a>',
            '<a href="https://fixture@auth.openai.com/log-in/password">使用密码</a>',
            '<a href="/create-account/password">创建密码</a>',
            '<a href="javascript:location.href=\'/log-in/password\'">使用密码</a>',
        ):
            for final_url in (PASSWORD_URL, OTP_URL):
                with self.subTest(html=html, final_url=final_url):
                    session = _Session()
                    session.get.side_effect = [_Response(OTP_URL, html), _Response(final_url)]
                    if final_url == PASSWORD_URL:
                        self.assertEqual(PASSWORD_URL, v2._open_offered_password_login(session, OTP_URL))
                    else:
                        with self.assertRaises(v2.ProtocolV2AuthError) as caught:
                            v2._open_offered_password_login(session, OTP_URL)
                        self.assertEqual("password_login_unavailable", caught.exception.code)
                        self.assertIs(caught.exception.mutation_submitted, False)
                        self.assertIs(caught.exception.action_dispatched, False)
                        self.assertFalse(caught.exception.reconcile_required)
                    self.assertEqual([OTP_URL, PASSWORD_URL], [call.args[0] for call in session.get.call_args_list])

    def test_password_link_must_finish_on_trusted_login_page(self):
        from core.accounts.liveness.protocol import v2 as v2

        for final_url in ("https://other.example/log-in/password", "https://auth.openai.com/create-account/password"):
            with self.subTest(final_url=final_url):
                session = _Session()
                session.get.side_effect = [
                    _Response(OTP_URL, '<a href="/log-in/password">使用密码</a>'),
                    _Response(final_url),
                ]
                with self.assertRaises(v2.ProtocolV2AuthError) as caught:
                    v2._open_offered_password_login(session, OTP_URL)
                self.assertEqual("password_login_unavailable", caught.exception.code)

    def test_navigation_failures_report_no_password_submission_and_allow_browser_fallback(self):
        from core.accounts.liveness.protocol import v2 as v2

        for stage in ("otp_page", "password_page"):
            for failure in ("timeout", "http_error"):
                with self.subTest(stage=stage, failure=failure):
                    session = _Session()
                    initial = _Response(OTP_URL, '<a href="/log-in/password">使用密码</a>')
                    failed = (
                        TimeoutError("fixture-private-navigation-detail")
                        if failure == "timeout" else _Response(
                            OTP_URL if stage == "otp_page" else PASSWORD_URL, status_code=503,
                        )
                    )
                    session.get.side_effect = [failed] if stage == "otp_page" else [initial, failed]

                    with self.assertRaises(v2.ProtocolV2AuthError) as caught:
                        v2._open_offered_password_login(session, OTP_URL)

                    error = caught.exception
                    self.assertEqual("password_login_unavailable", error.code)
                    self.assertIs(error.mutation_submitted, False)
                    self.assertIs(error.action_dispatched, False)
                    self.assertFalse(error.reconcile_required)
                    self.assertTrue(error.roxy_fallback_allowed)
                    self.assertNotIn("fixture-private-navigation-detail", str(error))


class InvalidEmailProtocolLoginTests(unittest.TestCase):
    def _context(self, *, invalid=True, password="fixture-password", secret="fixture-secret", landing=OTP_URL):
        from core.accounts.liveness.protocol import v2 as v2

        stack = ExitStack()
        self.addCleanup(stack.close)
        session = _Session()
        stack.enter_context(patch.object(v2, "account_email_is_invalid", return_value=invalid, create=True))
        stack.enter_context(patch.object(v2, "get_account_login_credentials", return_value=(password, secret)))
        preflight = stack.enter_context(patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize-fixture")))
        stack.enter_context(patch.object(v2, "follow_authorize", return_value=landing))
        opened = stack.enter_context(patch.object(v2, "_open_offered_password_login", return_value=PASSWORD_URL, create=True))
        verify = stack.enter_context(patch.object(v2, "_password_verify", return_value={"continue_url": MFA_URL}))
        mfa = stack.enter_context(patch.object(v2, "_complete_mfa", return_value=({"accessToken": "fixture-fresh-at"}, "password_mfa_totp")))
        send = stack.enter_context(patch.object(v2, "send_email_otp"))
        email = stack.enter_context(patch.object(v2, "_complete_email_otp", return_value=({"accessToken": "fixture-fresh-at"}, "email_otp")))
        legacy = stack.enter_context(patch.object(v2, "check_account_liveness", return_value={"ok": True, "status": "live"}))
        return v2, session, preflight, opened, verify, mfa, send, email, legacy

    def test_invalid_email_uses_password_then_totp_without_requesting_mail(self):
        v2, session, _, opened, verify, mfa, send, email, legacy = self._context()
        boundary = MagicMock()
        authenticated = MagicMock(side_effect=lambda result, _session: result)

        result = v2.refresh_access_token(
            EMAIL, proxy="", on_remote_request_started=boundary, on_authenticated=authenticated,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("password_mfa_totp", result["auth_method"])
        self.assertEqual("verified", result["password_auth_status"])
        opened.assert_called_once_with(session, OTP_URL)
        verify.assert_called_once_with(session, "fixture-password")
        mfa.assert_called_once_with(session, {"continue_url": MFA_URL}, MFA_URL, "fixture-secret")
        boundary.assert_called_once()
        self.assertIs(authenticated.call_args.args[1], session)
        send.assert_not_called()
        email.assert_not_called()
        legacy.assert_not_called()
        session.session.close.assert_called_once()

    def test_invalid_email_without_password_does_not_fall_back_to_otp(self):
        v2, _, preflight, opened, verify, _, send, email, legacy = self._context(password="", secret="")

        result = v2.refresh_access_token(EMAIL, proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("password_missing", result["error"])
        preflight.assert_not_called()
        opened.assert_not_called()
        verify.assert_not_called()
        send.assert_not_called()
        email.assert_not_called()
        legacy.assert_not_called()

    def test_invalid_email_password_rejection_never_uses_enabled_email_fallback(self):
        from config import account as account_config

        v2, _, _, _, verify, _, send, email, legacy = self._context(landing=PASSWORD_URL)
        verify.side_effect = v2.ProtocolV2AuthError("password_rejected", roxy_fallback_allowed=False)
        with patch.object(account_config, "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", True), patch.object(
            v2, "_start_email_session",
        ) as email_fallback:
            result = v2.refresh_access_token(EMAIL, proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("password_rejected", result["error"])
        email_fallback.assert_not_called()
        send.assert_not_called()
        email.assert_not_called()
        legacy.assert_not_called()

    def test_invalid_email_reports_required_email_challenge_after_password(self):
        v2, _, _, _, verify, mfa, send, email, _ = self._context(landing=PASSWORD_URL)
        verify.return_value = {"continue_url": OTP_URL, "page": {"type": "email_verification"}}

        result = v2.refresh_access_token(EMAIL, proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("email_verification_required", result["error"])
        mfa.assert_not_called()
        send.assert_not_called()
        email.assert_not_called()

    def test_invalid_email_reports_unavailable_password_entry_without_waiting_for_mail(self):
        v2, _, _, opened, verify, _, send, email, _ = self._context()
        opened.side_effect = v2.ProtocolV2AuthError("password_login_unavailable")

        result = v2.refresh_access_token(EMAIL, proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("password_login_unavailable", result["error"])
        verify.assert_not_called()
        send.assert_not_called()
        email.assert_not_called()

    def test_password_page_timeout_remains_before_submission_in_refresh_result(self):
        from core.accounts.liveness import service as live_check_service
        from core.accounts.liveness.protocol import v2 as v2_module

        open_offered = v2_module._open_offered_password_login
        v2, session, _, opened, verify, _, send, email, _ = self._context()
        opened.side_effect = open_offered
        session.get.side_effect = [
            _Response(OTP_URL, '<a href="/log-in/password">使用密码</a>'),
            TimeoutError("fixture-private-navigation-detail"),
        ]

        result = v2.refresh_access_token(EMAIL, proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("password_login_unavailable", result["error"])
        self.assertIs(result["mutation_submitted"], False)
        self.assertIs(result["action_dispatched"], False)
        self.assertTrue(result["roxy_fallback_allowed"])
        self.assertFalse(live_check_service._refresh_result_is_unknown(result))
        self.assertTrue(live_check_service._refresh_result_before_remote_boundary(result))
        verify.assert_not_called()
        send.assert_not_called()
        email.assert_not_called()

    def test_unmarked_email_keeps_existing_initial_otp_flow(self):
        v2, _, _, opened, verify, mfa, send, email, legacy = self._context(invalid=False)

        result = v2.refresh_access_token(EMAIL, proxy="")

        self.assertTrue(result["ok"])
        self.assertEqual("email_otp", result["auth_method"])
        opened.assert_not_called()
        verify.assert_not_called()
        mfa.assert_not_called()
        send.assert_called_once()
        email.assert_called_once()
        legacy.assert_not_called()

    def test_unmarked_email_without_password_keeps_legacy_login(self):
        v2, _, preflight, opened, verify, _, _, _, legacy = self._context(invalid=False, password="", secret="")

        result = v2.refresh_access_token(EMAIL, proxy="")

        self.assertTrue(result["ok"])
        self.assertEqual("legacy_email_otp", result["auth_method"])
        legacy.assert_called_once()
        preflight.assert_not_called()
        opened.assert_not_called()
        verify.assert_not_called()


class InvalidEmailLegacyAndBrowserTests(unittest.TestCase):
    def test_legacy_entry_preserves_callbacks_when_delegating_invalid_email(self):
        from core.accounts.liveness.protocol import legacy as account_liveness
        from core.accounts.liveness.protocol import v2 as v2

        proxy_supplier = MagicMock()
        boundary = MagicMock()
        authenticated = MagicMock()
        expected = {"ok": True, "status": "live", "auth_method": "password_mfa_totp"}
        with (
            patch("core.accounts.credentials.account_email_is_invalid", return_value=True, create=True),
            patch.object(account_liveness, "account_email_is_invalid", return_value=True, create=True),
            patch.object(v2, "refresh_access_token", return_value=expected) as refresh,
        ):
            result = account_liveness.check_account_liveness(
                EMAIL, proxy="", clear_log=False, proxy_supplier=proxy_supplier,
                on_remote_request_started=boundary, on_authenticated=authenticated,
            )

        self.assertEqual(expected, result)
        refresh.assert_called_once_with(
            EMAIL, proxy="", proxy_supplier=proxy_supplier,
            on_remote_request_started=boundary, on_authenticated=authenticated,
        )

    def _browser_otp_entry(self, *, invalid: bool, challenge_state="advanced"):
        from core.accounts.liveness.roxy import flow as roxy_liveness

        driver = MagicMock()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("core.accounts.credentials.account_email_is_invalid", return_value=invalid, create=True))
        stack.enter_context(patch.object(roxy_liveness, "account_email_is_invalid", return_value=invalid, create=True))
        stack.enter_context(patch.object(roxy_liveness, "_open_standard_password_login", return_value=False))
        for name, value in (
            ("_page_account_unusable_code", ""),
            ("_type_email_address", None),
            ("_submit_email_step", None),
            ("_wait_email_submit_next_state", "otp"),
            ("_has_access_token", False),
            ("_is_login_password_page", False),
            ("_is_email_verification_page", True),
        ):
            stack.enter_context(patch.object(roxy_liveness, name, return_value=value))
        challenge = stack.enter_context(patch(
            "core.codex.roxy.oauth.complete_openai_login_challenge", return_value=challenge_state,
        ))
        return driver, roxy_liveness, challenge

    def test_browser_initial_otp_tries_saved_password_for_invalid_email(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=True)

        result = roxy_liveness._enter_existing_account_otp(
            driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
        )

        self.assertEqual("logged_in", result)
        challenge.assert_called_once_with(driver, EMAIL, "fixture-password", "fixture-secret", timeout=45)

    def test_browser_unmarked_email_uses_offered_saved_password_before_waiting_for_mail(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=False)

        result = roxy_liveness._enter_existing_account_otp(
            driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
        )

        self.assertEqual("logged_in", result)
        challenge.assert_called_once_with(driver, EMAIL, "fixture-password", "fixture-secret", timeout=45)
        roxy_liveness._open_standard_password_login.assert_not_called()

    def test_browser_unmarked_email_returns_to_mail_if_shared_challenge_still_requires_it(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=False, challenge_state="email_otp")

        result = roxy_liveness._enter_existing_account_otp(
            driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
        )

        self.assertEqual("otp", result)
        challenge.assert_called_once()
        roxy_liveness._open_standard_password_login.assert_not_called()

    def test_browser_unmarked_email_without_password_keeps_mail_flow(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=False)

        result = roxy_liveness._enter_existing_account_otp(driver, EMAIL)

        self.assertEqual("otp", result)
        challenge.assert_not_called()
        roxy_liveness._open_standard_password_login.assert_not_called()

    def test_browser_without_offered_link_tries_standard_password_route_once(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=True)
        driver._browser_submission_receipt = SimpleNamespace(endpoint_kind="email_submit")
        challenge.side_effect = ["email_otp", "advanced"]
        roxy_liveness._open_standard_password_login.return_value = True

        result = roxy_liveness._enter_existing_account_otp(
            driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
        )

        self.assertEqual("logged_in", result)
        roxy_liveness._open_standard_password_login.assert_called_once_with(driver)
        self.assertEqual(2, challenge.call_count)

    def test_browser_standard_password_route_still_requiring_otp_does_not_loop(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=True, challenge_state="email_otp")
        driver._browser_submission_receipt = SimpleNamespace(endpoint_kind="email_submit")
        roxy_liveness._open_standard_password_login.return_value = True

        with self.assertRaises(RuntimeError) as caught:
            roxy_liveness._enter_existing_account_otp(
                driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
            )

        self.assertEqual("password_login_unavailable", caught.exception.code)
        self.assertIs(caught.exception.not_submitted, True)
        roxy_liveness._open_standard_password_login.assert_called_once_with(driver)
        self.assertEqual(2, challenge.call_count)

    def test_browser_does_not_reopen_password_route_after_password_was_submitted(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=True)
        driver._browser_submission_receipt = SimpleNamespace(endpoint_kind="email_submit")

        def password_then_email(*_args, **_kwargs):
            driver._browser_submission_receipt = SimpleNamespace(endpoint_kind="password_submit")
            return "email_otp"

        challenge.side_effect = password_then_email
        with self.assertRaises(RuntimeError) as caught:
            roxy_liveness._enter_existing_account_otp(
                driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
            )

        self.assertEqual("email_verification_required", caught.exception.code)
        roxy_liveness._open_standard_password_login.assert_not_called()
        challenge.assert_called_once()

    def test_browser_standard_password_navigation_timeout_remains_not_submitted(self):
        from core.accounts.liveness.roxy import flow as roxy_module

        open_standard = roxy_module._open_standard_password_login
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=True, challenge_state="email_otp")
        driver._browser_submission_receipt = SimpleNamespace(endpoint_kind="email_submit")
        roxy_liveness._open_standard_password_login.side_effect = open_standard
        with patch.object(roxy_liveness, "_safe_get", side_effect=TimeoutError("fixture-private-navigation")) as navigate:
            with self.assertRaises(RuntimeError) as caught:
                roxy_liveness._enter_existing_account_otp(
                    driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
                )

        self.assertEqual("password_login_unavailable", caught.exception.code)
        self.assertIs(caught.exception.not_submitted, True)
        self.assertNotIn("fixture-private-navigation", str(caught.exception))
        navigate.assert_called_once()
        roxy_liveness._open_standard_password_login.assert_called_once_with(driver)
        challenge.assert_called_once()

    def test_browser_history_preserves_password_submission_after_otp_receipt_overwrites_current(self):
        driver, roxy_liveness, challenge = self._browser_otp_entry(invalid=True)
        initial = SimpleNamespace(endpoint_kind="email_submit")
        driver._browser_submission_receipt = initial
        driver._browser_submission_receipts = [initial]

        def password_then_otp(*_args, **_kwargs):
            # 当前回执可能被后续 OTP 覆盖，本轮历史仍能证明密码已经提交。
            password_receipt = SimpleNamespace(endpoint_kind="password_submit")
            otp_receipt = SimpleNamespace(endpoint_kind="otp_submit")
            driver._browser_submission_receipts.extend([password_receipt, otp_receipt])
            driver._browser_submission_receipt = otp_receipt
            return "email_otp"

        challenge.side_effect = password_then_otp
        with self.assertRaises(RuntimeError) as caught:
            roxy_liveness._enter_existing_account_otp(
                driver, EMAIL, password="fixture-password", totp_secret="fixture-secret",
            )

        self.assertEqual("email_verification_required", caught.exception.code)
        self.assertIs(caught.exception.not_submitted, False)
        roxy_liveness._open_standard_password_login.assert_not_called()
        challenge.assert_called_once()

    def test_browser_refresh_returns_fixed_code_without_password_or_when_mail_is_still_required(self):
        for password, initial_state, submitted_password, expected_code in (
            ("", "otp", False, "password_missing"),
            ("fixture-password", "otp", False, "password_login_unavailable"),
            ("fixture-password", "otp", True, "email_verification_required"),
            ("fixture-password", "login_password", True, "email_verification_required"),
        ):
            with self.subTest(initial_state=initial_state, expected_code=expected_code):
                driver, roxy_liveness, challenge = self._browser_otp_entry(
                    invalid=True, challenge_state="email_otp",
                )
                driver._browser_submission_receipt = SimpleNamespace(endpoint_kind="email_submit")
                if submitted_password:
                    # 密码提交后仍需邮箱，与没有密码入口保留不同的外部原因码。
                    def complete_password(*_args, **_kwargs):
                        driver._browser_submission_receipt = SimpleNamespace(endpoint_kind="password_submit")
                        return "email_otp"

                    challenge.side_effect = complete_password
                opened = SimpleNamespace(profile_id="profile-fixture", account_bound=True)
                client = MagicMock()
                client.open_profile_for_account.return_value = opened
                with ExitStack() as stack:
                    for dependency in (
                        patch.object(roxy_liveness, "available", return_value=True),
                        patch.object(roxy_liveness, "RoxyBrowserClient", return_value=client),
                        patch.object(roxy_liveness, "_build_driver", return_value=driver),
                        patch.object(roxy_liveness, "_center_browser_window"),
                        patch.object(roxy_liveness, "_safe_get"),
                        patch.object(roxy_liveness, "_page_warmup"),
                        patch.object(roxy_liveness, "_maybe_accept"),
                        patch.object(roxy_liveness, "_wait_email_submit_next_state", return_value=initial_state),
                        patch.object(roxy_liveness, "_is_login_password_page", return_value=initial_state == "login_password"),
                        patch.object(roxy_liveness, "_quit_driver"),
                        patch("core.browser.roxy.profile_binding.account_profile_id_by_email", return_value="profile-fixture"),
                        patch("core.codex.roxy.oauth._account_login_credentials", return_value=(password, "fixture-secret")),
                        patch("core.browser.asset_policy.start_auth_asset_cache"),
                        patch("core.browser.asset_policy.stop_asset_cache"),
                        patch("core.browser.flow_policy.install_for_flow"),
                        patch("core.browser.traffic.finish_roxy_capture"),
                    ):
                        stack.enter_context(dependency)
                    complete_email = stack.enter_context(patch.object(roxy_liveness, "_complete_otp"))
                    fetch_session = stack.enter_context(patch.object(roxy_liveness, "_fetch_chatgpt_session"))
                    wait_for_mail = stack.enter_context(patch.object(roxy_liveness, "wait_for_otp"))

                    result = roxy_liveness.refresh_access_token(EMAIL, context_recorder=MagicMock())

                self.assertFalse(result["ok"])
                self.assertEqual("failed", result["status"])
                self.assertEqual(expected_code, result.get("error_code"))
                if not submitted_password:
                    self.assertIs(result["mutation_submitted"], False)
                    self.assertIs(result["action_dispatched"], False)
                complete_email.assert_not_called()
                wait_for_mail.assert_not_called()
                fetch_session.assert_not_called()
                if not password:
                    challenge.assert_not_called()


class InvalidEmailRefreshReceiptTests(unittest.TestCase):
    def test_required_email_challenge_preserves_cause_and_confirmed_failure(self):
        from core.accounts.liveness import service as live_check_service

        result = {
            "ok": False,
            "status": "failed",
            "error": "email_verification_required",
            "error_code": "email_verification_required",
            "remote_request_started": True,
            "password_auth_status": "verified",
            "roxy_fallback_allowed": False,
        }

        self.assertEqual("email_verification_required", live_check_service._safe_refresh_cause_code(result))
        self.assertTrue(live_check_service._refresh_result_is_rejected(result))
        self.assertFalse(live_check_service._refresh_result_is_unknown(result))


if __name__ == "__main__":
    unittest.main()
