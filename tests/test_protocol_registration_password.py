# -*- coding: utf-8 -*-
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from core.registration import protocol


class ProtocolPasswordRegistrationTests(unittest.TestCase):
    def test_password_stage_uses_one_bundle_then_registers_and_sends_otp(self):
        session = object()
        events = []
        bundle = {"token": "challenge", "_request_p": "same-p"}
        register_result = {
            "continue_url": "/api/accounts/email-otp/send",
            "page": {"type": "email_otp_send"},
        }

        def bundle_side_effect(_session):
            events.append("bundle")
            return bundle

        def password_page_side_effect(_session):
            events.append("password-page")
            return "https://auth.openai.com/create-account/password"

        def header_side_effect(_session, received_bundle, flow):
            events.append(("header", received_bundle, flow))
            return "sentinel-header", "so-header"

        def register_side_effect(_session, email, password, sentinel, so):
            events.append(("register", email, password, sentinel, so))
            return register_result

        def otp_side_effect(_session, continue_url):
            events.append(("otp", continue_url))
            return "https://auth.openai.com/email-verification"

        def checkpoint_side_effect(password):
            events.append(("checkpoint", password))

        with (
            patch.object(protocol, "generate_registration_password", return_value="Password!123"),
            patch.object(protocol, "navigate_create_account_password", side_effect=password_page_side_effect),
            patch.object(protocol, "request_password_sentinel_bundle", side_effect=bundle_side_effect),
            patch.object(protocol, "build_sentinel_header", side_effect=header_side_effect),
            patch.object(protocol, "register_user", side_effect=register_side_effect),
            patch.object(protocol, "navigate_email_otp_send", side_effect=otp_side_effect),
        ):
            result = protocol._run_protocol_password_stage(
                session,
                "user@example.com",
                on_password_submitted=checkpoint_side_effect,
            )

        self.assertEqual(result["password"], "Password!123")
        self.assertEqual(result["register_result"], register_result)
        self.assertEqual(result["otp_url"], "https://auth.openai.com/email-verification")
        self.assertEqual(events[0], "password-page")
        self.assertEqual(events[1], "bundle")
        self.assertEqual(events[2], ("header", bundle, "username_password_create"))
        self.assertEqual(events[3], (
            "register",
            "user@example.com",
            "Password!123",
            "sentinel-header",
            "so-header",
        ))
        self.assertEqual(events[4], ("checkpoint", "Password!123"))
        self.assertEqual(events[5], ("otp", "/api/accounts/email-otp/send"))

    def test_password_stage_rejects_register_response_without_continue_url(self):
        session = object()
        with (
            patch.object(protocol, "generate_registration_password", return_value="Password!123"),
            patch.object(protocol, "navigate_create_account_password", return_value="https://auth.openai.com/create-account/password"),
            patch.object(protocol, "request_password_sentinel_bundle", return_value={"token": "challenge"}),
            patch.object(protocol, "build_sentinel_header", return_value=("sentinel", "so")),
            patch.object(protocol, "register_user", return_value={"page": {"type": "unknown"}}),
            patch.object(protocol, "navigate_email_otp_send") as navigate,
        ):
            with self.assertRaisesRegex(RuntimeError, "缺少 continue_url"):
                protocol._run_protocol_password_stage(session, "user@example.com")

        navigate.assert_not_called()

    def test_password_stage_marks_transport_failure_as_unknown(self):
        session = object()
        with (
            patch.object(protocol, "generate_registration_password", return_value="Password!123"),
            patch.object(protocol, "navigate_create_account_password", return_value="https://auth.openai.com/create-account/password"),
            patch.object(protocol, "request_password_sentinel_bundle", return_value={"token": "challenge"}),
            patch.object(protocol, "build_sentinel_header", return_value=("sentinel", "so")),
            patch.object(protocol, "register_user", side_effect=TimeoutError("read timed out")),
            patch.object(protocol, "human_delay"),
        ):
            with self.assertRaisesRegex(RuntimeError, "user/register 请求结果未知"):
                protocol._run_protocol_password_stage(session, "user@example.com")

    def test_password_stage_keeps_checkpoint_when_otp_navigation_fails(self):
        checkpointed = []
        with (
            patch.object(protocol, "generate_registration_password", return_value="Password!123"),
            patch.object(protocol, "navigate_create_account_password"),
            patch.object(protocol, "request_password_sentinel_bundle", return_value={"token": "challenge"}),
            patch.object(protocol, "build_sentinel_header", return_value=("sentinel", "so")),
            patch.object(protocol, "register_user", return_value={
                "continue_url": "/api/accounts/email-otp/send",
            }),
            patch.object(protocol, "navigate_email_otp_send", side_effect=TimeoutError("read timed out")),
        ):
            with self.assertRaisesRegex(TimeoutError, "read timed out"):
                protocol._run_protocol_password_stage(
                    object(),
                    "user@example.com",
                    on_password_submitted=checkpointed.append,
                )

        self.assertEqual(checkpointed, ["Password!123"])

    def test_run_registration_invokes_password_stage_after_authorize(self):
        session = SimpleNamespace(proxy="", device_id="device-id", sentinel_sid=None, browser_profile=None)
        events = []

        def password_stage(_session, email, **_kwargs):
            events.append(("password", email))
            return {
                "password": "Password!123",
                "register_result": {"continue_url": "/api/accounts/email-otp/send"},
                "continue_url": "/api/accounts/email-otp/send",
                "otp_url": "https://auth.openai.com/email-verification",
            }

        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "probe_auth_session"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(
                protocol, "follow_authorize", side_effect=lambda *_args: events.append("authorize")
            ))
            stack.enter_context(patch.object(
                protocol, "_maybe_run_protocol_password_stage", side_effect=password_stage
            ))
            stack.enter_context(patch.object(
                protocol,
                "validate_email_otp",
                side_effect=lambda *_args: events.append("otp-validate") or {
                    "page": {"type": "about_you"},
                    "continue_url": "https://auth.openai.com/about-you",
                },
            ))
            stack.enter_context(patch.object(protocol, "navigate_about_you"))
            stack.enter_context(patch.object(protocol, "request_sentinel_token", return_value={"token": "opaque"}))
            stack.enter_context(patch.object(protocol, "build_sentinel_header", return_value=("sentinel", "so")))
            stack.enter_context(patch.object(protocol, "create_account", return_value={
                "continue_url": "https://auth.openai.com/authorize/continue?state=opaque",
            }))
            stack.enter_context(patch.object(
                protocol,
                "_finalize_registration_session",
                return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
            ))
            stack.enter_context(patch("core.registration_service.persist_registration_core", return_value=7))
            stack.enter_context(patch(
                "core.registration.checkpoints.save_email_verification_checkpoint",
                return_value=19,
            ))
            stack.enter_context(patch("core.registration_service.report_registered_account"))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", False, create=True
            ))
            stack.enter_context(patch.object(protocol._email_cfg, "USE_EMAIL_SERVICE", True))
            stack.enter_context(patch("core.db.update_account_codex_status"))
            stack.enter_context(patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": True}))
            stack.enter_context(patch(
                "core.registration_postprocess.summarize_postprocess",
                return_value=SimpleNamespace(next_actions=(), account_readiness={}),
            ))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            result = protocol.run_protocol_registration(
                "user@example.com",
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source="generic_api",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
            )

        self.assertTrue(result["success"], result)
        self.assertLess(events.index("authorize"), events.index(("password", "user@example.com")))
        self.assertLess(events.index(("password", "user@example.com")), events.index("otp-validate"))
        self.assertIn("password", result["auth"]["challenge_chain"])

    def test_protocol_plan_check_reuses_registration_session_and_proxy(self):
        session = SimpleNamespace(
            proxy="http://proxy.example:8080",
            device_id="device-id",
            sentinel_sid=None,
            browser_profile=None,
        )
        password_stage = {
            "password": "Password!123",
            "register_result": {"continue_url": "/api/accounts/email-otp/send"},
            "continue_url": "/api/accounts/email-otp/send",
            "otp_url": "https://auth.openai.com/email-verification",
        }
        plan_check_result = {
            "ok": True,
            "current_plan_type": "free",
            "plus_promo_kind": "free_trial",
            "plus_trial_eligible": True,
        }

        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "probe_auth_session"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(protocol, "follow_authorize"))
            stack.enter_context(
                patch.object(protocol, "_maybe_run_protocol_password_stage", return_value=password_stage)
            )
            stack.enter_context(patch.object(
                protocol,
                "validate_email_otp",
                return_value={
                    "page": {"type": "about_you"},
                    "continue_url": "https://auth.openai.com/about-you",
                },
            ))
            stack.enter_context(patch.object(protocol, "navigate_about_you"))
            stack.enter_context(patch.object(protocol, "request_sentinel_token", return_value={"token": "opaque"}))
            stack.enter_context(patch.object(protocol, "build_sentinel_header", return_value=("sentinel", "so")))
            stack.enter_context(patch.object(protocol, "create_account", return_value={
                "continue_url": "https://auth.openai.com/authorize/continue?state=opaque",
            }))
            stack.enter_context(patch.object(
                protocol,
                "_finalize_registration_session",
                return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
            ))
            stack.enter_context(patch("core.registration_service.persist_registration_core", return_value=7))
            stack.enter_context(patch(
                "core.registration.checkpoints.save_email_verification_checkpoint",
                return_value=19,
            ))
            stack.enter_context(patch("core.registration_service.report_registered_account"))
            sync_check = stack.enter_context(patch(
                "core.plan_check_service.check_registration_account_plan",
                return_value=plan_check_result,
            ))
            enqueue = stack.enter_context(patch("core.plan_check_service.enqueue_account_plan_check"))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", False, create=True
            ))
            stack.enter_context(patch.object(protocol._email_cfg, "USE_EMAIL_SERVICE", True))
            stack.enter_context(patch("core.db.update_account_codex_status"))
            stack.enter_context(patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": True}))
            stack.enter_context(patch(
                "core.registration_postprocess.summarize_postprocess",
                return_value=SimpleNamespace(next_actions=(), account_readiness={}),
            ))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            result = protocol.run_protocol_registration(
                "user@example.com",
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source="generic_api",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": True,
                },
            )

        self.assertTrue(result["success"], result)
        sync_check.assert_called_once_with(
            account_id=7,
            email="user@example.com",
            access_token="fresh-token",
            proxy="http://proxy.example:8080",
            session=session,
        )
        enqueue.assert_not_called()
        self.assertEqual("free_trial", result["plan_check"]["plus_promo_kind"])

    def test_protocol_plan_check_runs_before_twofa_after_core_persistence(self):
        session = SimpleNamespace(
            proxy="http://proxy.example:8080",
            device_id="device-id",
            sentinel_sid=None,
            browser_profile=None,
        )
        password_stage = {
            "password": "Password!123",
            "register_result": {"continue_url": "/api/accounts/email-otp/send"},
            "continue_url": "/api/accounts/email-otp/send",
            "otp_url": "https://auth.openai.com/email-verification",
        }
        events = []

        def persist_core(*_args, **_kwargs):
            events.append("core_persisted")
            return 7

        def check_plan(**_kwargs):
            events.append("plan_check")
            return {"ok": True, "current_plan_type": "free", "plus_promo_kind": "free_trial"}

        def setup_twofa(*_args, **_kwargs):
            events.append("twofa")
            return "totp-secret"

        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "probe_auth_session"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(protocol, "follow_authorize"))
            stack.enter_context(patch.object(protocol, "_maybe_run_protocol_password_stage", return_value=password_stage))
            stack.enter_context(patch.object(protocol, "validate_email_otp", return_value={
                "page": {"type": "about_you"},
                "continue_url": "https://auth.openai.com/about-you",
            }))
            stack.enter_context(patch.object(protocol, "navigate_about_you"))
            stack.enter_context(patch.object(protocol, "request_sentinel_token", return_value={"token": "opaque"}))
            stack.enter_context(patch.object(protocol, "build_sentinel_header", return_value=("sentinel", "so")))
            stack.enter_context(patch.object(protocol, "create_account", return_value={
                "continue_url": "https://auth.openai.com/authorize/continue?state=opaque",
            }))
            stack.enter_context(patch.object(
                protocol,
                "_finalize_registration_session",
                return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
            ))
            stack.enter_context(patch("core.registration_service.persist_registration_core", side_effect=persist_core))
            stack.enter_context(patch(
                "core.registration.checkpoints.save_email_verification_checkpoint",
                return_value=19,
            ))
            stack.enter_context(patch("core.registration_service.report_registered_account"))
            stack.enter_context(patch("core.plan_check_service.check_registration_account_plan", side_effect=check_plan))
            stack.enter_context(patch.object(protocol, "setup_2fa_protocol", side_effect=setup_twofa))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", False, create=True
            ))
            stack.enter_context(patch.object(protocol._email_cfg, "USE_EMAIL_SERVICE", True))
            stack.enter_context(patch("core.db.update_account_codex_status"))
            stack.enter_context(patch("core.db.update_account_totp_secret"))
            stack.enter_context(patch("core.db.update_account_twofa_status"))
            stack.enter_context(patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": True}))
            stack.enter_context(patch(
                "core.registration_postprocess.summarize_postprocess",
                return_value=SimpleNamespace(next_actions=(), account_readiness={}),
            ))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            result = protocol.run_protocol_registration(
                "user@example.com",
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source="generic_api",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": True,
                    "codex_enabled": False,
                    "plan_check_enabled": True,
                },
            )

        self.assertTrue(result["success"], result)
        self.assertEqual(["core_persisted", "plan_check", "twofa"], events)

    def test_password_disabled_does_not_enter_password_stage(self):
        session = object()
        with patch.object(protocol, "_run_protocol_password_stage") as password_stage:
            result = protocol._maybe_run_protocol_password_stage(
                session,
                "user@example.com",
                password_enabled=False,
            )

        self.assertIsNone(result)
        password_stage.assert_not_called()

    def test_existing_password_stage_uses_protocol_password_verify(self):
        session = object()
        verify_result = {
            "continue_url": "https://auth.openai.com/email-verification",
            "page": {"type": "email_otp"},
        }
        with patch(
            "core.protocol_v2_liveness._password_verify",
            return_value=verify_result,
        ) as verify:
            result = protocol._run_protocol_existing_password_stage(
                session,
                "user@example.com",
                "SavedPassword!123",
            )

        self.assertIs(result, verify_result)
        verify.assert_called_once_with(session, "SavedPassword!123")

    def test_existing_password_transport_failure_is_unknown(self):
        with patch(
            "core.protocol_v2_liveness._password_verify",
            side_effect=TimeoutError("read timed out"),
        ):
            with self.assertRaisesRegex(RuntimeError, "密码验证请求结果未知"):
                protocol._run_protocol_existing_password_stage(
                    object(),
                    "user@example.com",
                    "SavedPassword!123",
                )

    def test_resume_mfa_uses_saved_totp_secret(self):
        mfa_response = {
            "page": {"type": "mfa_challenge"},
            "continue_url": "https://auth.openai.com/mfa-challenge?factor_id=factor-1",
        }
        session_info = {"accessToken": "fresh-token", "user": {}, "account": {}}
        with patch(
            "core.protocol_v2_liveness._complete_mfa",
            return_value=(session_info, "password_mfa_totp"),
        ) as complete_mfa:
            result, access_token = protocol._complete_protocol_resume_mfa(
                object(),
                mfa_response,
                "https://auth.openai.com/mfa-challenge?factor_id=factor-1",
                "SavedTotpSecret",
            )

        self.assertIs(result, session_info)
        self.assertEqual(access_token, "fresh-token")
        complete_mfa.assert_called_once_with(
            unittest.mock.ANY,
            mfa_response,
            "https://auth.openai.com/mfa-challenge?factor_id=factor-1",
            "SavedTotpSecret",
        )

    def test_resume_skips_password_verify_when_authorize_is_already_on_email_page(self):
        self.assertFalse(
            protocol._protocol_resume_requires_password(
                "https://auth.openai.com/email-verification"
            )
        )
        self.assertTrue(
            protocol._protocol_resume_requires_password(
                "https://auth.openai.com/log-in/password"
            )
        )

    def test_resume_otp_send_failure_is_marked_unconfirmed(self):
        with patch.object(
            protocol,
            "navigate_email_otp_send",
            side_effect=TimeoutError("read timed out"),
        ):
            with self.assertRaisesRegex(RuntimeError, "续跑邮箱验证码发送未确认"):
                protocol._send_protocol_resume_email_otp(object())

    def test_resume_otp_send_failure_returns_request_unknown_and_retains_same_email(self):
        session = SimpleNamespace(proxy="", device_id="device-id", sentinel_sid=None, browser_profile=None)
        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "probe_auth_session"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(
                protocol,
                "follow_authorize",
                return_value="https://auth.openai.com/email-verification",
            ))
            stack.enter_context(patch.object(
                protocol,
                "navigate_email_otp_send",
                side_effect=TimeoutError("read timed out"),
            ))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            retain = stack.enter_context(patch(
                "core.email_provider.retain_email",
                return_value="generic_api",
            ))
            result = protocol.run_protocol_registration(
                "user@example.com",
                "Test User",
                "2000-01-01",
                email_source="generic_api",
                existing_password="SavedPassword!123",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
            )

        self.assertFalse(result["success"])
        self.assertTrue(result["request_unknown"])
        self.assertEqual(result["error_code"], "request_unknown")
        retain.assert_called_once()

    def test_resume_does_not_register_again_after_password_verify(self):
        session = SimpleNamespace(proxy="", device_id="device-id", sentinel_sid=None, browser_profile=None)
        events = []

        def send_resume_otp(_session, continue_url=None, *, referer):
            events.append(("send", continue_url, referer))
            return "https://auth.openai.com/email-verification"

        def wait_for_resume_otp(_email, **kwargs):
            events.append(("wait", kwargs["after_ts"]))
            return "123456"

        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "probe_auth_session"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(
                protocol,
                "follow_authorize",
                return_value="https://auth.openai.com/log-in/password",
            ))
            verify = stack.enter_context(patch.object(
                protocol,
                "_run_protocol_existing_password_stage",
                return_value={"page": {"type": "email_otp"}, "continue_url": "/email-verification"},
            ))
            stack.enter_context(patch.object(
                protocol,
                "navigate_email_otp_send",
                side_effect=send_resume_otp,
            ))
            stack.enter_context(patch.object(protocol, "wait_for_otp", side_effect=wait_for_resume_otp))
            stack.enter_context(patch.object(protocol, "_maybe_run_protocol_password_stage"))
            mfa_response = {
                "page": {"type": "mfa_challenge"},
                "continue_url": "https://auth.openai.com/mfa-challenge?factor_id=factor-1",
            }
            stack.enter_context(patch.object(
                protocol,
                "validate_email_otp",
                return_value=mfa_response,
            ))
            complete_mfa = stack.enter_context(patch.object(
                protocol,
                "_complete_protocol_resume_mfa",
                return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
            ))
            create_account = stack.enter_context(patch.object(protocol, "create_account"))
            stack.enter_context(patch.object(
                protocol,
                "_finalize_registration_session",
                return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
            ))
            stack.enter_context(patch("core.registration_service.persist_registration_core", return_value=7))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "SEND_SENTINEL_ON_EMAIL_OTP_VALIDATE", False, create=True
            ))
            stack.enter_context(patch.object(protocol._email_cfg, "USE_EMAIL_SERVICE", True))
            stack.enter_context(patch("core.db.update_account_codex_status"))
            stack.enter_context(patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": True}))
            stack.enter_context(patch(
                "core.registration_postprocess.summarize_postprocess",
                return_value=SimpleNamespace(next_actions=(), account_readiness={}),
            ))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            result = protocol.run_protocol_registration(
                "user@example.com",
                "Test User",
                "2000-01-01",
                email_source="generic_api",
                existing_password="SavedPassword!123",
                existing_totp_secret="SavedTotpSecret",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
            )

        self.assertTrue(result["success"], result)
        verify.assert_called_once_with(session, "user@example.com", "SavedPassword!123")
        complete_mfa.assert_called_once_with(
            session,
            mfa_response,
            "https://auth.openai.com/mfa-challenge?factor_id=factor-1",
            "SavedTotpSecret",
        )
        create_account.assert_not_called()
        self.assertEqual(result["remote_identity"], "existing")
        self.assertEqual(
            events[0],
            ("send", None, "https://auth.openai.com/email-verification"),
        )
        self.assertEqual(events[1][0], "wait")

    def test_run_registration_keeps_password_transport_unknown_and_retains_email(self):
        session = SimpleNamespace(proxy="", device_id="device-id", sentinel_sid=None, browser_profile=None)
        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "probe_auth_session"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(protocol, "follow_authorize"))
            stack.enter_context(patch.object(
                protocol,
                "_maybe_run_protocol_password_stage",
                side_effect=RuntimeError("user/register 请求结果未知: TimeoutError"),
            ))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            retain = stack.enter_context(patch(
                "core.email_provider.retain_email",
                return_value="generic_api",
            ))
            result = protocol.run_protocol_registration(
                "user@example.com",
                "Test User",
                "2000-01-01",
                email_source="generic_api",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
            )

        self.assertFalse(result["success"])
        self.assertTrue(result["request_unknown"], result)
        self.assertEqual(result["error_code"], "request_unknown")
        retain.assert_called_once()

    def test_authorize_route_rejection_is_safe_for_outer_proxy_rotation(self):
        class RouteRejectedError(RuntimeError):
            code = "auth_route_rejected"
            retry_with_new_proxy = True

        session = SimpleNamespace(proxy="", device_id="device-id", sentinel_sid=None, browser_profile=None)
        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "probe_auth_session"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(
                protocol,
                "follow_authorize",
                side_effect=RouteRejectedError("HTTP 403"),
            ))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(
                protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True
            ))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            retain = stack.enter_context(patch(
                "core.email_provider.retain_email",
                return_value="generic_api",
            ))
            result = protocol.run_protocol_registration(
                "user@example.com",
                "Test User",
                "2000-01-01",
                email_source="generic_api",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
            )

        self.assertFalse(result["success"])
        self.assertFalse(result["request_unknown"])
        self.assertEqual("auth_route_rejected", result["error_code"])
        self.assertTrue(result["retry_as_new_route"])
        retain.assert_called_once()


if __name__ == "__main__":
    unittest.main()
