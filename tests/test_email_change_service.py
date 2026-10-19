from __future__ import annotations

import tempfile
import unittest
import logging
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from core import account_task_store, record_store, task_run_log
from core.record_store import ACCOUNTS
from core.operations import task_gateway
from core.storage import operation
from tests.support_pg import PostgresTestCase
from webui import runtime


class _Response:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.headers = dict(headers or {})

    def json(self):
        return self._payload


class EmailChangeProtocolContractTests(unittest.TestCase):
    def test_recent_login_rebuilds_a_fresh_protocol_session(self):
        from core import account_liveness

        old_session = Mock()
        old_session.proxy = "socks5://proxy.example:1080"
        old_session.device_id = "stable-device"
        old_session.protocol_identity_id = "identity-1"
        old_session.protocol_profile_ref = "profile-1"
        old_session.protocol_profile_version = 3
        old_session.browser_profile = {
            "screen_width": 1920,
            "screen_height": 1080,
            "device_pixel_ratio": 1,
            "hardware_concurrency": 8,
            "device_memory": 8,
            "js_heap_size_limit": 4294705152,
        }
        fresh_session = Mock()
        with patch.object(
            account_liveness,
            "_network_preflight_with_retry",
            return_value=(fresh_session, "https://auth.openai.com/authorize"),
        ) as preflight, patch.object(
            account_liveness,
            "follow_authorize",
            return_value="https://auth.openai.com/log-in/password",
        ), patch.object(
            account_liveness,
            "_complete_recent_login_on_session",
            return_value=({"accessToken": "fresh-at"}, "password_mfa_totp"),
            create=True,
        ) as complete, patch.object(
            account_liveness,
            "_warm_authenticated_session",
        ) as warm:
            result = account_liveness.perform_recent_login(
                old_session,
                "old@example.test",
                email_source="email_butler",
                access_token="old-at",
            )

        self.assertIs(fresh_session, result["protocol_session"])
        self.assertEqual("fresh-at", result["access_token"])
        self.assertEqual("password_mfa_totp", result["auth_method"])
        self.assertEqual(old_session.proxy, preflight.call_args.args[1])
        identity = preflight.call_args.kwargs["identity"]
        self.assertEqual("stable-device", identity["device_id"])
        self.assertEqual("identity-1", identity["identity_id"])
        complete.assert_called_once()
        warm.assert_called_once_with(fresh_session, "fresh-at")

    def test_recent_login_does_not_fallback_to_direct_after_proxy_403(self):
        from core import account_liveness

        old_session = Mock()
        old_session.proxy = "socks5://proxy.example:1080"
        old_session.device_id = "stable-device"
        old_session.protocol_identity_id = "identity-1"
        old_session.protocol_profile_ref = "profile-1"
        old_session.protocol_profile_version = 3
        old_session.browser_profile = {"screen_width": 1920}
        failed_session = Mock()
        fresh_session = Mock()
        with patch.object(
            account_liveness,
            "_network_preflight_with_retry",
            side_effect=RuntimeError("HTTP 403 from auth.openai.com"),
        ) as preflight, patch.object(
            account_liveness,
            "follow_authorize",
            return_value="https://auth.openai.com/log-in/password",
        ), patch.object(
            account_liveness,
            "_complete_recent_login_on_session",
            return_value=({"accessToken": "fresh-at"}, "password_mfa_totp"),
        ), patch.object(account_liveness, "_warm_authenticated_session"):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                account_liveness.perform_recent_login(
                    old_session,
                    "old@example.test",
                    email_source="email_butler",
                    access_token="old-at",
                )

        preflight.assert_called_once()
        self.assertEqual(old_session.proxy, preflight.call_args.args[1])
        self.assertEqual("stable-device", preflight.call_args.kwargs["identity"]["device_id"])

    def test_follow_reauth_rejects_failed_navigation_response(self):
        from core.account_export import _follow_reauth

        session = Mock()
        session.get_auth_navigate_headers.return_value = {}
        session.get.return_value = _Response({}, status_code=403)

        with self.assertRaises(RuntimeError):
            _follow_reauth(session, "https://auth.example/reauth")

        session.get.assert_called_once()

    def test_live_child_uses_its_durable_resource_family_for_the_lease(self):
        from core import live_check_service

        acquired_families = []

        @contextmanager
        def lease(*, resource_family):
            acquired_families.append(resource_family)
            yield Mock()

        context = SimpleNamespace(
            account_id=790,
            task_id=97991,
            email="new@example.test",
            resource_family="email_change_live_check",
            run={"data": {"force_refresh": True}, "trigger": "email_change_auto"},
            config_snapshot=None,
            lease=lease,
        )
        with patch.object(
            live_check_service.db,
            "get_account",
            return_value={"email": "new@example.test"},
        ), patch.object(live_check_service, "_run_live_check") as run:
            self.assertIsNone(live_check_service._handle_live_operation(context))

        self.assertEqual(["email_change_live_check"], acquired_families)
        self.assertTrue(run.call_args.kwargs["force_refresh"])

    def test_follow_reauth_retries_transient_failure_on_same_session(self):
        from core import account_export

        session = Mock()
        transient = RuntimeError("upstream unavailable")
        transient.response = Mock(status_code=503)
        with patch.object(account_export, "_warm_auth_document_for_reauth"), patch.object(
            account_export, "_follow_reauth", side_effect=[transient, "https://auth.example/email-verification"]
        ) as follow, patch.object(account_export.time, "sleep") as sleep:
            result = account_export._follow_reauth_with_retry(
                session, "https://auth.example/reauth"
            )

        self.assertEqual("https://auth.example/email-verification", result)
        self.assertEqual(2, follow.call_count)
        sleep.assert_called_once()

    def test_recent_login_email_landing_uses_selected_mailbox_source(self):
        from core import account_liveness

        session = Mock()
        with patch(
            "core.account_credentials.get_account_login_credentials",
            return_value=("", ""),
        ), patch.object(
            account_liveness,
            "_validate_with_retry",
            return_value={"continue_url": "https://auth.example/callback"},
        ) as validate, patch(
            "core.protocol_v2_liveness._follow_and_fetch",
            return_value={"accessToken": "fresh-at"},
        ) as exchange:
            session_info, auth_method = account_liveness._complete_recent_login_on_session(
                session,
                "old@example.test",
                "https://auth.openai.com/email-verification",
                123.0,
                email_source="outlook",
            )

        self.assertEqual("fresh-at", session_info["accessToken"])
        self.assertEqual("email_otp", auth_method)
        validate.assert_called_once_with(
            session,
            "old@example.test",
            123.0,
            email_source="outlook",
        )
        exchange.assert_called_once()

    def test_recent_login_password_landing_uses_saved_password_and_totp(self):
        from core import account_liveness

        session = Mock()
        password_result = {
            "continue_url": "https://auth.openai.com/mfa-challenge/factor-1"
        }
        with patch(
            "core.account_credentials.get_account_login_credentials",
            return_value=("saved-password", "saved-totp"),
        ), patch(
            "core.protocol_v2_liveness._password_verify",
            return_value=password_result,
        ) as verify_password, patch(
            "core.protocol_v2_liveness._complete_mfa",
            return_value=({"accessToken": "fresh-at"}, "password_mfa_totp"),
        ) as complete_mfa, patch(
            "core.account_liveness.wait_for_otp",
        ) as wait:
            session_info, auth_method = account_liveness._complete_recent_login_on_session(
                session,
                "old@example.test",
                "https://auth.openai.com/log-in/password",
                123.0,
                email_source="icloud_hide",
            )

        self.assertEqual("fresh-at", session_info["accessToken"])
        self.assertEqual("password_mfa_totp", auth_method)
        verify_password.assert_called_once_with(session, "saved-password")
        complete_mfa.assert_called_once_with(
            session,
            password_result,
            "https://auth.openai.com/mfa-challenge/factor-1",
            "saved-totp",
        )
        wait.assert_not_called()

    def test_authenticated_warmup_clears_optional_bootstrap_circuit(self):
        from core import account_liveness

        class Session:
            blocked_until = 123.0
            blocked_reason = "HTTP 403 from optional bootstrap"

        session = Session()
        with patch(
            "core.chatgpt_bootstrap.authenticated_bootstrap",
            side_effect=RuntimeError("optional bootstrap failed"),
        ):
            account_liveness._warm_authenticated_session(session, "access-token")

        self.assertEqual(0.0, session.blocked_until)
        self.assertEqual("", session.blocked_reason)


class EmailChangeLoggingTests(unittest.TestCase):
    class _GuardContext:
        account_id = 7
        run_id = 29
        task_id = 30
        email = "old@example.test"
        run = {"data": {"email_source": "outlook"}, "trigger": "test"}
        config_snapshot = {"email_change_enabled": True}

        def __init__(self):
            self.events = []

        def report(self, **event):
            self.events.append(event)

        @contextmanager
        def lease(self, *, resource_family):
            yield None

        def checkpoint(self):
            return None

        def remote_request_started(self, *args, **kwargs):
            return None

        def remote_request_receipt(self, *args, **kwargs):
            return None

    def _guard_context(self):
        return self._GuardContext()

    def _source_account(self):
        return {
            "email": "old@example.test",
            "email_source": "outlook",
            "access_token": "old-at",
        }

    def test_email_butler_owned_target_is_marked_used_and_reacquired(self):
        from core import email_change_service

        context = self._guard_context()
        with (
            patch.object(email_change_service.email_provider, "acquire_email", side_effect=[
                "used@example.test",
                "fresh@example.test",
            ]) as acquire_email,
            patch.object(email_change_service.db, "get_account_by_email", side_effect=[
                {"id": 99, "email": "used@example.test"},
                None,
            ]),
            patch.object(email_change_service.email_provider, "release_email") as release_email,
        ):
            target, failure = email_change_service._acquire_email_change_target(
                context,
                account_id=7,
                source="email_butler",
                current_email="old@example.test",
            )

        self.assertIsNone(failure)
        self.assertEqual("fresh@example.test", target)
        self.assertEqual(2, acquire_email.call_count)
        release_email.assert_called_once_with(
            "used@example.test",
            status="used",
            source="email_butler",
            note="本地账号 #99 已使用该邮箱",
        )
        self.assertEqual("running", context.events[-1]["state"])
        self.assertIn("正在重新领取", context.events[-1]["message"])

    def test_email_butler_owned_target_stops_when_used_closeout_fails(self):
        from core import email_change_service

        context = self._guard_context()
        with (
            patch.object(email_change_service.email_provider, "acquire_email", return_value="used@example.test") as acquire_email,
            patch.object(email_change_service.db, "get_account_by_email", return_value={"id": 99, "email": "used@example.test"}),
            patch.object(email_change_service.email_provider, "release_email", side_effect=RuntimeError("closeout failed")),
        ):
            target, failure = email_change_service._acquire_email_change_target(
                context,
                account_id=7,
                source="email_butler",
                current_email="old@example.test",
            )

        self.assertEqual("used@example.test", target)
        self.assertEqual("failed", failure.status)
        self.assertEqual("email_change_target_in_use", failure.summary["cause_code"])
        acquire_email.assert_called_once()

    def test_target_owned_by_another_account_finishes_source_without_remote_begin(self):
        from core import email_change_service

        context = self._guard_context()
        route = Mock()
        begin = Mock()
        with (
            patch.object(email_change_service.db, "get_account", return_value=self._source_account()),
            patch.object(email_change_service.db, "get_account_by_email", return_value={"id": 99, "email": "taken@example.test"}),
            patch.object(email_change_service.email_provider, "validate_email_source", return_value="outlook"),
            patch("core.browser_traffic.record_unavailable"),
            patch.object(email_change_service.db, "claim_account_email_change", return_value=True),
            patch.object(email_change_service.email_provider, "acquire_email", return_value="  Taken@Example.test "),
            patch.object(email_change_service.db, "mark_account_email_change_running") as mark_running,
            patch.object(email_change_service, "acquire_account_proxy", return_value=route) as acquire_proxy,
            patch.object(email_change_service, "begin_change_with_optional_reauth", return_value=begin) as begin_call,
            patch.object(email_change_service.db, "finish_account_email_change", return_value=True) as finish,
            patch.object(email_change_service, "_release_unconsumed") as release,
        ):
            result = email_change_service._handle_email_change(context)

        self.assertEqual("failed", result.status)
        self.assertEqual("email_change_target_in_use", result.summary["cause_code"])
        self.assertEqual(7, result.summary["account_id"])
        self.assertFalse(result.summary.get("target_email"))
        finish.assert_called_once_with(
            7,
            ok=False,
            new_email="Taken@Example.test",
            source="outlook",
            error="目标邮箱已被本地账号占用，已停止换绑",
        )
        mark_running.assert_not_called()
        acquire_proxy.assert_not_called()
        begin_call.assert_not_called()
        release.assert_not_called()
        self.assertTrue(all("Taken@Example.test" not in str(event) for event in context.events))

    def test_archived_or_disabled_account_email_remains_unavailable(self):
        from core import email_change_service

        for owner in (
            {"id": 99, "email": "taken@example.test", "archived": True},
            {"id": 100, "email": "taken@example.test", "deactivated": True},
        ):
            with self.subTest(owner=owner):
                context = self._guard_context()
                with (
                    patch.object(email_change_service.db, "get_account", return_value=self._source_account()),
                    patch.object(email_change_service.db, "get_account_by_email", return_value=owner),
                    patch.object(email_change_service.email_provider, "validate_email_source", return_value="outlook"),
                    patch("core.browser_traffic.record_unavailable"),
                    patch.object(email_change_service.db, "claim_account_email_change", return_value=True),
                    patch.object(email_change_service.email_provider, "acquire_email", return_value="taken@example.test"),
                    patch.object(email_change_service, "acquire_account_proxy") as acquire_proxy,
                    patch.object(email_change_service, "begin_change_with_optional_reauth") as begin_call,
                    patch.object(email_change_service.db, "finish_account_email_change", return_value=True) as finish,
                    patch.object(email_change_service, "_release_unconsumed") as release,
                ):
                    result = email_change_service._handle_email_change(context)

                self.assertEqual("email_change_target_in_use", result.summary["cause_code"])
                self.assertEqual(7, finish.call_args.args[0])
                acquire_proxy.assert_not_called()
                begin_call.assert_not_called()
                release.assert_not_called()

    def test_same_email_guard_finishes_source_without_releasing_bound_mailbox(self):
        from core import email_change_service

        context = self._guard_context()
        with (
            patch.object(email_change_service.db, "get_account", return_value=self._source_account()),
            patch.object(email_change_service.email_provider, "validate_email_source", return_value="outlook"),
            patch("core.browser_traffic.record_unavailable"),
            patch.object(email_change_service.db, "claim_account_email_change", return_value=True),
            patch.object(email_change_service.email_provider, "acquire_email", return_value=" OLD@example.test "),
            patch.object(email_change_service.db, "finish_account_email_change", return_value=True) as finish,
            patch.object(email_change_service, "_release_unconsumed") as release,
            patch.object(email_change_service, "acquire_account_proxy") as acquire_proxy,
            patch.object(email_change_service, "begin_change_with_optional_reauth") as begin_call,
        ):
            result = email_change_service._handle_email_change(context)

        self.assertEqual("failed", result.status)
        self.assertEqual("email_change_same_email", result.summary["cause_code"])
        finish.assert_called_once_with(
            7,
            ok=False,
            new_email="OLD@example.test",
            source="outlook",
            error="领取到的邮箱与当前邮箱相同，已停止换绑",
        )
        release.assert_not_called()
        acquire_proxy.assert_not_called()
        begin_call.assert_not_called()

    def test_email_change_logs_allocated_mailbox_when_waiting_for_otp(self):
        from core import email_change_service

        class _Context:
            account_id = 7
            run_id = 29
            task_id = 30
            email = "old@example.test"
            run = {"data": {"email_source": "outlook"}, "trigger": "test"}
            config_snapshot = {"email_change_enabled": True}

            def __init__(self):
                self.events = []

            def report(self, **event):
                self.events.append(event)

            @contextmanager
            def lease(self, *, resource_family):
                yield None

            def checkpoint(self):
                return None

            def remote_request_started(self, *args, **kwargs):
                return None

            def remote_request_receipt(self, *args, **kwargs):
                return None

        context = _Context()
        route = SimpleNamespace(
            proxy_url="",
            public_dict=lambda: {},
            release=Mock(),
        )
        session = Mock()
        identity = SimpleNamespace(session_payload=lambda: {})
        begin = email_change_service.BeginChangeResult(
            session=session,
            access_token="fresh-at",
            after_ts=123.0,
            reauthenticated=False,
        )
        account = {
            "email": "old@example.test",
            "email_source": "outlook",
            "access_token": "old-at",
        }

        with patch.object(email_change_service.db, "get_account", return_value=account), \
            patch.object(email_change_service.db, "get_account_by_email", return_value=None), \
            patch.object(email_change_service.email_provider, "validate_email_source", return_value="outlook"), \
            patch("core.browser_traffic.record_unavailable"), \
            patch.object(email_change_service.db, "claim_account_email_change", return_value=True), \
            patch.object(email_change_service.email_provider, "acquire_email", return_value="new@example.test"), \
            patch.object(email_change_service.db, "mark_account_email_change_running", return_value=True), \
            patch.object(email_change_service, "acquire_account_proxy", return_value=route), \
            patch.object(email_change_service, "_account_stable_identity", return_value=identity), \
            patch("core.session.BrowserSession", return_value=session), \
            patch.object(email_change_service, "begin_change_with_optional_reauth", return_value=begin) as begin_call, \
            patch.object(email_change_service.email_provider, "wait_for_otp", side_effect=RuntimeError("mailbox wait timed out")), \
            patch.object(email_change_service.db, "finish_account_email_change", return_value=True):
            result = email_change_service._handle_email_change(context)

        self.assertEqual("request_unknown", result.status)
        begin_call.assert_called_once()
        self.assertIn(
            ("email", "success", "新邮箱已领取：new@example.test"),
            [(item["stage"], item["state"], item["message"]) for item in context.events],
        )
        self.assertIn(
            ("email_otp", "running", "等待新邮箱验证码：new@example.test"),
            [(item["stage"], item["state"], item["message"]) for item in context.events],
        )

    def test_verify_prepare_and_transport_failures_keep_accepted_mailbox(self):
        from core import email_change_service

        account = {
            "email": "old@example.test",
            "email_source": "outlook",
            "access_token": "old-at",
        }
        route = SimpleNamespace(proxy_url="", public_dict=lambda: {}, release=Mock())
        identity = SimpleNamespace(session_payload=lambda: {})
        for failure in ("prepare", "transport"):
            with self.subTest(failure=failure):
                context = Mock(
                    account_id=7,
                    run_id=31,
                    task_id=32,
                    email="old@example.test",
                    run={"data": {"email_source": "outlook"}, "trigger": "test"},
                    config_snapshot={"email_change_enabled": True},
                )
                context.lease.return_value = nullcontext()
                session = Mock()
                session.get_chatgpt_headers.return_value = {}
                session.device_id = "device-test"
                session.navigator_language.return_value = "en-US"
                order = []
                context.remote_request_started.side_effect = lambda *_args, **_kwargs: order.append("intent")
                if failure == "prepare":
                    session.get_chatgpt_headers.side_effect = RuntimeError("private-token")
                else:
                    def disconnect(*_args, **_kwargs):
                        order.append("post")
                        raise ConnectionError("TLS reset")

                    session.post.side_effect = disconnect
                begin = email_change_service.BeginChangeResult(
                    session=session,
                    access_token="fresh-at",
                    after_ts=123.0,
                )
                with (
                    patch.object(email_change_service.db, "get_account", return_value=account),
                    patch.object(email_change_service.db, "get_account_by_email", return_value=None),
                    patch.object(email_change_service.email_provider, "validate_email_source", return_value="outlook"),
                    patch("core.browser_traffic.record_unavailable"),
                    patch.object(email_change_service.db, "claim_account_email_change", return_value=True),
                    patch.object(email_change_service.email_provider, "acquire_email", return_value="new@example.test"),
                    patch.object(email_change_service.db, "mark_account_email_change_running", return_value=True),
                    patch.object(email_change_service, "acquire_account_proxy", return_value=route),
                    patch.object(email_change_service, "_account_stable_identity", return_value=identity),
                    patch("core.session.BrowserSession", return_value=session),
                    patch.object(email_change_service, "begin_change_with_optional_reauth", return_value=begin),
                    patch.object(email_change_service.email_provider, "wait_for_otp", return_value="123456"),
                    patch.object(email_change_service.db, "finish_account_email_change", return_value=True) as finish,
                    patch.object(email_change_service, "_release_unconsumed") as release,
                ):
                    result = email_change_service._handle_email_change(context)

                self.assertEqual("request_unknown", result.status)
                self.assertEqual("request_unknown", finish.call_args.kwargs["outcome"])
                release.assert_not_called()
                if failure == "prepare":
                    self.assertEqual("email_change_verify_prepare_failed", result.summary["cause_code"])
                    self.assertEqual([], order)
                    session.post.assert_not_called()
                    self.assertNotIn("private-token", finish.call_args.kwargs["error"])
                    context.remote_request_receipt.assert_not_called()
                else:
                    self.assertEqual(["intent", "post"], order)
                    session.post.assert_called_once()
                    self.assertEqual("unknown", context.remote_request_receipt.call_args.kwargs["outcome"])

    def test_recent_login_unknown_landing_rejects_before_waiting_for_otp(self):
        from core import account_liveness

        session = Mock()
        with patch(
            "core.account_credentials.get_account_login_credentials",
            return_value=("", ""),
        ), patch(
            "core.account_liveness.wait_for_otp",
        ) as wait:
            with self.assertRaisesRegex(RuntimeError, "Recent Login 落点不受支持"):
                account_liveness._complete_recent_login_on_session(
                    session,
                    "old@example.test",
                    "https://auth.openai.com/error",
                    123.0,
                    email_source="outlook",
                )

        wait.assert_not_called()


    def test_remote_rejection_exposes_only_safe_status_and_error_code(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response(
            {
                "error": {
                    "code": "invalid_email",
                    "message": "new-user@example.test is not allowed",
                }
            },
            status_code=400,
        )

        with self.assertRaises(RemoteRequestRejected) as caught:
            EmailChangeProtocol().begin(session, "at-test", "new-user@example.test")

        self.assertEqual(400, caught.exception.http_status)
        self.assertEqual("invalid_email", caught.exception.remote_error_code)
        self.assertNotIn("new-user@example.test", str(caught.exception))

    def test_remote_rejection_reads_nested_detail_code(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response(
            {"detail": {"message": "Recent login required", "code": "reauth_required"}},
            status_code=401,
        )

        with self.assertRaises(RemoteRequestRejected) as caught:
            EmailChangeProtocol().begin(session, "at-test", "new-user@example.test")

        self.assertEqual(401, caught.exception.http_status)
        self.assertEqual("reauth_required", caught.exception.remote_error_code)

    def test_remote_rejection_reads_safe_scalar_detail_code(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response(
            {"detail": "email_domain_not_allowed"},
            status_code=422,
        )

        with self.assertRaises(RemoteRequestRejected) as caught:
            EmailChangeProtocol().begin(session, "at-test", "new-user@example.test")

        self.assertEqual(422, caught.exception.http_status)
        self.assertEqual("email_domain_not_allowed", caught.exception.remote_error_code)

    def test_remote_rejection_classifies_detail_message_without_address(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response(
            {
                "detail": {
                    "message": "Email alice@leeseven.com uses a domain that is not allowed",
                },
            },
            status_code=422,
        )

        with self.assertRaises(RemoteRequestRejected) as caught:
            EmailChangeProtocol().begin(session, "at-test", "new-user@example.test")

        self.assertEqual("email_domain_rejected", caught.exception.remote_error_code)
        self.assertNotIn("alice@leeseven.com", str(caught.exception))

    def test_remote_rejection_keeps_only_safe_json_shape(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response(
            {"errors": {"email": ["alice@leeseven.com is invalid"]}},
            status_code=422,
        )

        with self.assertRaises(RemoteRequestRejected) as caught:
            EmailChangeProtocol().begin(session, "at-test", "new-user@example.test")

        self.assertEqual("object.errors_object", caught.exception.response_error_shape)
        self.assertNotIn("alice@leeseven.com", caught.exception.response_error_shape)

    def test_remote_rejection_projects_fixed_hints_without_detail_text(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response(
            {"detail": "The email address cannot be used for this account."},
            status_code=422,
        )

        with self.assertRaises(RemoteRequestRejected) as caught:
            EmailChangeProtocol().begin(session, "at-test", "new-user@example.test")

        self.assertEqual("email_change_not_allowed", caught.exception.remote_error_code)
        self.assertEqual(
            ("account", "email", "not_allowed"),
            caught.exception.response_error_hints,
        )
        self.assertNotIn("cannot be used", " ".join(caught.exception.response_error_hints))


class EmailChangeCloseoutTests(unittest.TestCase):
    def test_successful_email_change_closes_consumed_email_as_used(self):
        from core import email_change_service

        with patch.object(
            email_change_service.email_provider,
            "release_email",
            return_value="email_butler",
        ) as release_email:
            result = email_change_service._finalize_consumed_email(
                "new@example.test",
                7,
                "email_butler",
            )

        self.assertEqual("success", result["status"])
        release_email.assert_called_once_with(
            "new@example.test",
            status="used",
            source="email_butler",
            note="账号 #7 邮箱换绑成功",
        )

    def test_email_closeout_failure_is_reported_without_raising(self):
        from core import email_change_service

        with patch.object(
            email_change_service.email_provider,
            "release_email",
            side_effect=RuntimeError("Email Butler release failed"),
        ):
            result = email_change_service._finalize_consumed_email(
                "new@example.test",
                7,
                "email_butler",
            )

        self.assertEqual("failed", result["status"])
        self.assertEqual("RuntimeError", result["error_type"])

    def test_successful_email_change_invokes_email_closeout(self):
        from core import email_change_service

        class _Context:
            account_id = 7
            run_id = 29
            task_id = 30
            email = "old@example.test"
            run = {"data": {"email_source": "email_butler"}, "trigger": "test"}
            config_snapshot = {"email_change_enabled": True}

            def report(self, **event):
                return None

            @contextmanager
            def lease(self, *, resource_family):
                yield None

            def checkpoint(self):
                return None

            def remote_request_started(self, *args, **kwargs):
                return None

            def remote_request_receipt(self, *args, **kwargs):
                return None

        context = _Context()
        route = SimpleNamespace(
            proxy_url="",
            public_dict=lambda: {},
            release=Mock(),
        )
        session = Mock()
        identity = SimpleNamespace(session_payload=lambda: {})
        begin = email_change_service.BeginChangeResult(
            session=session,
            access_token="fresh-at",
            after_ts=123.0,
            reauthenticated=False,
        )
        initial_account = {
            "email": "old@example.test",
            "email_source": "icloud_hide",
            "access_token": "old-at",
        }
        updated_account = {
            "email": "new@example.test",
            "email_source": "email_butler",
            "access_token": "fresh-at",
        }

        with (
            patch.object(email_change_service.db, "get_account", side_effect=[initial_account, updated_account]),
            patch.object(email_change_service.db, "get_account_by_email", return_value=None),
            patch.object(email_change_service.email_provider, "validate_email_source", return_value="email_butler"),
            patch("core.browser_traffic.record_unavailable"),
            patch.object(email_change_service.db, "claim_account_email_change", return_value=True),
            patch.object(email_change_service.email_provider, "acquire_email", return_value="new@example.test"),
            patch.object(email_change_service.db, "mark_account_email_change_running", return_value=True),
            patch.object(email_change_service, "acquire_account_proxy", return_value=route),
            patch.object(email_change_service, "_account_stable_identity", return_value=identity),
            patch("core.session.BrowserSession", return_value=session),
            patch.object(email_change_service, "begin_change_with_optional_reauth", return_value=begin),
            patch.object(email_change_service.email_provider, "wait_for_otp", return_value="123456"),
            patch.object(email_change_service.EmailChangeProtocol, "prepare_verify", return_value=Mock()),
            patch.object(email_change_service.EmailChangeProtocol, "verify"),
            patch.object(email_change_service.email_provider, "email_material_line", return_value="new@example.test"),
            patch.object(email_change_service.db, "finish_account_email_change", return_value=True),
            patch.object(email_change_service, "_enqueue_live_check_child", return_value={"accepted": False}),
            patch.object(
                email_change_service,
                "_finalize_consumed_email",
                return_value={
                    "status": "failed",
                    "source": "email_butler",
                    "error_type": "EmailButlerClientError",
                },
            ) as finalize,
        ):
            result = email_change_service._handle_email_change(context)

        self.assertEqual("success", result.status)
        self.assertIn("邮箱服务收口失败", result.message)
        self.assertEqual("failed", result.summary["email_closeout"]["status"])
        finalize.assert_called_once_with("new@example.test", 7, "email_butler")


class EmailChangeEligibilityTests(unittest.TestCase):
    def test_email_prepare_failure_summary_redacts_supplier_email(self):
        from core.email_change_service import _safe_local_failure_message

        summary = _safe_local_failure_message(
            "邮箱准备失败",
            RuntimeError(
                "所选邮箱来源 email_butler 领取失败: EmailButlerClientError: "
                "Email Butler 请求失败 (/mailboxes/alice@example.test/messages): HTTP 409"
            ),
        )

        self.assertEqual("邮箱准备失败: Email Butler 领取失败（HTTP 409）", summary)
        self.assertNotIn("alice@example.test", summary)

    def test_submit_rejects_too_new_account_before_email_source_check(self):
        from core import email_change_service

        account = {
            "id": 7,
            "email": "account@example.test",
            "access_token": "at-test",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=23),
        }
        with patch.object(email_change_service.db, "get_account", return_value=account), patch(
            "core.feature_availability.require_email_source",
            return_value=(True, ""),
        ) as source_ready, patch.object(task_gateway, "submit_durable_operation") as submit:
            result = email_change_service.submit_email_change(
                7,
                source="email_butler",
                dispatch=False,
            )

        self.assertFalse(result["accepted"])
        self.assertIn("注册时间不足", result["error"])
        source_ready.assert_not_called()
        submit.assert_not_called()

    def test_submit_allows_account_past_minimum_age(self):
        from core import email_change_service

        account = {
            "id": 7,
            "email": "account@example.test",
            "access_token": "at-test",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=25),
        }
        with patch.object(email_change_service.db, "get_account", return_value=account), patch(
            "core.feature_availability.require_email_source",
            return_value=(True, ""),
        ), patch.object(
            task_gateway,
            "submit_durable_operation",
            return_value={"accepted": True, "task_id": 9, "run_id": 10},
        ) as submit:
            result = email_change_service.submit_email_change(
                7,
                source="email_butler",
                dispatch=False,
            )

        self.assertTrue(result["accepted"])
        submit.assert_called_once()

    def test_change_request_includes_account_context_from_access_token(self):
        from core.email_change_service import EmailChangeProtocol

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response({"success": True})
        with patch(
            "core.chatgpt_plan.token_claims",
            return_value={"account_id": "account-test"},
        ):
            EmailChangeProtocol().begin(
                session,
                "at-test",
                "new-user@example.test",
            )

        headers = session.post.call_args.kwargs["headers"]
        self.assertEqual("account-test", headers["chatgpt-account-id"])

    def test_recent_login_error_code_is_recognized_without_message_matching(self):
        from core.email_change_service import RemoteRequestRejected, _is_reauth_required

        exc = RemoteRequestRejected(
            "change_email begin rejected",
            http_status=403,
            remote_error_code="recent_login_required",
        )

        self.assertTrue(_is_reauth_required(exc))

    def test_begin_401_is_recognized_as_recent_login_requirement(self):
        from core.email_change_service import RemoteRequestRejected, _is_reauth_required

        exc = RemoteRequestRejected(
            "change_email begin rejected",
            http_status=401,
        )

        self.assertTrue(_is_reauth_required(exc))

    def test_non_auth_rejection_is_not_reclassified_as_recent_login(self):
        from core.email_change_service import RemoteRequestRejected, _is_reauth_required

        exc = RemoteRequestRejected(
            "change_email begin rejected",
            http_status=403,
            remote_error_code="account_policy_denied",
        )

        self.assertFalse(_is_reauth_required(exc))

    def test_change_request_does_not_replay_after_transport_failure(self):
        from core.email_change_service import EmailChangeProtocol

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.side_effect = ConnectionError("TLS reset")

        with self.assertRaises(ConnectionError):
            EmailChangeProtocol().begin(session, "at-test", "new@example.test")

        self.assertEqual(1, session.post.call_count)

    def test_explicit_reauth_retries_begin_once_and_uses_old_mailbox(self):
        from core.email_change_service import begin_change_with_optional_reauth

        session = Mock()
        fresh_session = Mock()
        first = RuntimeError("reauth_required")
        fresh = {
            "access_token": "fresh-at",
            "protocol_session": fresh_session,
        }
        with patch(
            "core.email_change_service.EmailChangeProtocol.prepare_begin",
            return_value=Mock(),
        ), patch(
            "core.email_change_service.EmailChangeProtocol.begin",
            side_effect=[first, {"success": True}],
        ) as begin, patch(
            "core.email_change_service.perform_recent_login",
            return_value=fresh,
        ) as recent_login:
            result = begin_change_with_optional_reauth(
                session,
                account_id=7,
                current_email="old@example.test",
                current_source="outlook",
                new_email="new@example.test",
                access_token="old-at",
            )

        self.assertEqual("fresh-at", result.access_token)
        self.assertTrue(result.reauthenticated)
        self.assertIs(fresh_session, result.session)
        self.assertEqual(2, begin.call_count)
        self.assertIs(session, begin.call_args_list[0].args[0])
        self.assertIs(fresh_session, begin.call_args_list[1].args[0])
        recent_login.assert_called_once()
        self.assertEqual("old@example.test", recent_login.call_args.kwargs["email"])
        self.assertEqual("outlook", recent_login.call_args.kwargs["email_source"])

    def test_bare_proxy_403_after_recent_login_is_not_replayed(self):
        from core.email_change_service import (
            RemoteRequestRejected,
            begin_change_with_optional_reauth,
        )

        session = Mock()
        proxy_session = Mock()
        proxy_session.proxy = "socks5://proxy.example:1080"
        first = RemoteRequestRejected(
            "recent login required",
            http_status=401,
        )
        proxy_forbidden = RemoteRequestRejected(
            "change email begin rejected",
            http_status=403,
        )
        with patch(
            "core.email_change_service.EmailChangeProtocol.prepare_begin",
            return_value=Mock(),
        ), patch(
            "core.email_change_service.EmailChangeProtocol.begin",
            side_effect=[first, proxy_forbidden],
        ) as begin, patch(
            "core.email_change_service.perform_recent_login",
            return_value={"access_token": "proxy-at", "protocol_session": proxy_session},
        ) as recent_login:
            with self.assertRaises(RemoteRequestRejected):
                begin_change_with_optional_reauth(
                    session,
                    account_id=7,
                    current_email="old@example.test",
                    current_source="outlook",
                    new_email="new@example.test",
                    access_token="old-at",
                )

        self.assertEqual(2, begin.call_count)
        recent_login.assert_called_once()

    def test_remote_rejection_records_only_safe_response_metadata(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response(
            {"error": "forbidden"},
            status_code=403,
            headers={
                "content-type": "text/html; charset=UTF-8",
                "server": "cloudflare",
                "cf-mitigated": "challenge",
                "cf-ray": "sensitive-ray-id",
                "set-cookie": "secret-cookie",
            },
        )

        with self.assertRaises(RemoteRequestRejected) as caught:
            EmailChangeProtocol().begin(session, "at-test", "new@example.test")

        exc = caught.exception
        self.assertEqual("text/html", exc.response_content_type)
        self.assertEqual("cloudflare", exc.response_server)
        self.assertTrue(exc.cf_mitigated)
        self.assertTrue(exc.cf_ray_present)
        self.assertNotIn("sensitive-ray-id", str(exc))
        self.assertFalse(hasattr(exc, "response_headers"))

    def test_close_protocol_session_closes_the_owned_transport(self):
        from core.email_change_service import _close_protocol_session

        session = Mock()
        _close_protocol_session(session)

        session.session.close.assert_called_once_with()

    def test_context_transport_failure_becomes_request_unknown_without_retry(self):
        from core.email_change_service import RemoteRequestUnknown, begin_change_with_optional_reauth

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        context = Mock(run_id=19)
        order = []
        context.remote_request_started.side_effect = lambda *_args, **_kwargs: order.append("intent")

        def disconnect(*_args, **_kwargs):
            order.append("post")
            raise ConnectionError("TLS reset")

        session.post.side_effect = disconnect
        with self.assertRaises(RemoteRequestUnknown):
            begin_change_with_optional_reauth(
                session,
                account_id=7,
                current_email="old@example.test",
                current_source="outlook",
                new_email="new@example.test",
                access_token="old-at",
                context=context,
            )

        self.assertEqual(["intent", "post"], order)
        session.post.assert_called_once()
        context.remote_request_started.assert_called_once()
        self.assertEqual(
            "unknown",
            context.remote_request_receipt.call_args.kwargs["outcome"],
        )

    def test_initial_begin_prepare_failure_is_local_without_remote_intent(self):
        from core.email_change_service import LocalRequestPrepareError, begin_change_with_optional_reauth

        session = Mock()
        session.get_chatgpt_headers.side_effect = RuntimeError("private-token")
        context = Mock(run_id=20)
        with self.assertRaises(LocalRequestPrepareError) as caught:
            begin_change_with_optional_reauth(
                session,
                account_id=7,
                current_email="old@example.test",
                current_source="outlook",
                new_email="new@example.test",
                access_token="old-at",
                context=context,
            )

        session.post.assert_not_called()
        context.remote_request_started.assert_not_called()
        context.remote_request_receipt.assert_not_called()
        self.assertNotIn("private-token", str(caught.exception))

    def test_reauth_begin_prepare_failure_stops_before_second_intent(self):
        from core.email_change_service import LocalRequestPrepareError, begin_change_with_optional_reauth

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response({"error": "recent login required"}, status_code=401)
        fresh_session = Mock()
        fresh_session.get_chatgpt_headers.side_effect = RuntimeError("private-token")
        context = Mock(run_id=21)
        with patch(
            "core.email_change_service.perform_recent_login",
            return_value={"access_token": "fresh-at", "protocol_session": fresh_session},
        ):
            with self.assertRaises(LocalRequestPrepareError):
                begin_change_with_optional_reauth(
                    session,
                    account_id=7,
                    current_email="old@example.test",
                    current_source="outlook",
                    new_email="new@example.test",
                    access_token="old-at",
                    context=context,
                )

        session.post.assert_called_once()
        fresh_session.post.assert_not_called()
        context.remote_request_started.assert_called_once()
        context.remote_request_receipt.assert_called_once()
        self.assertEqual("rejected", context.remote_request_receipt.call_args.kwargs["outcome"])

    def test_reauth_begin_transport_failure_keeps_second_request_unknown(self):
        from core.email_change_service import RemoteRequestUnknown, begin_change_with_optional_reauth

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response({"error": "recent login required"}, status_code=401)
        fresh_session = Mock()
        fresh_session.get_chatgpt_headers.return_value = {}
        fresh_session.device_id = "device-test"
        fresh_session.navigator_language.return_value = "en-US"
        fresh_session.post.side_effect = ConnectionError("TLS reset")
        context = Mock(run_id=22)
        with patch(
            "core.email_change_service.perform_recent_login",
            return_value={"access_token": "fresh-at", "protocol_session": fresh_session},
        ):
            with self.assertRaises(RemoteRequestUnknown):
                begin_change_with_optional_reauth(
                    session,
                    account_id=7,
                    current_email="old@example.test",
                    current_source="outlook",
                    new_email="new@example.test",
                    access_token="old-at",
                    context=context,
                )

        session.post.assert_called_once()
        fresh_session.post.assert_called_once()
        self.assertEqual(2, context.remote_request_started.call_count)
        self.assertEqual(
            ["rejected", "unknown"],
            [call.kwargs["outcome"] for call in context.remote_request_receipt.call_args_list],
        )

    def test_successful_begin_with_lost_receipt_is_request_unknown(self):
        from core.email_change_service import RemoteRequestUnknown, begin_change_with_optional_reauth

        session = Mock()
        context = Mock(run_id=23)
        context.remote_request_receipt.side_effect = task_gateway.OperationLeaseLost(
            "lease lost while persisting receipt"
        )
        with patch(
            "core.email_change_service.EmailChangeProtocol.prepare_begin",
            return_value=Mock(),
        ), patch(
            "core.email_change_service.EmailChangeProtocol.begin",
            return_value={"success": True},
        ) as begin:
            with self.assertRaises(RemoteRequestUnknown):
                begin_change_with_optional_reauth(
                    session,
                    account_id=7,
                    current_email="old@example.test",
                    current_source="outlook",
                    new_email="new@example.test",
                    access_token="old-at",
                    context=context,
                )

        begin.assert_called_once()

    def test_successful_reauth_begin_with_lost_receipt_is_request_unknown(self):
        from core.email_change_service import (
            RemoteRequestRejected,
            RemoteRequestUnknown,
            begin_change_with_optional_reauth,
        )

        session = Mock()
        fresh_session = Mock()
        context = Mock(run_id=29)
        context.remote_request_receipt.side_effect = [
            None,
            task_gateway.OperationLeaseLost("lease lost while persisting receipt"),
        ]
        with patch(
            "core.email_change_service.EmailChangeProtocol.prepare_begin",
            return_value=Mock(),
        ), patch(
            "core.email_change_service.EmailChangeProtocol.begin",
            side_effect=[
                RemoteRequestRejected("recent login required", http_status=401),
                {"success": True},
            ],
        ) as begin, patch(
            "core.email_change_service.perform_recent_login",
            return_value={"access_token": "fresh-at", "protocol_session": fresh_session},
        ):
            with self.assertRaises(RemoteRequestUnknown):
                begin_change_with_optional_reauth(
                    session,
                    account_id=7,
                    current_email="old@example.test",
                    current_source="outlook",
                    new_email="new@example.test",
                    access_token="old-at",
                    context=context,
                )

        self.assertEqual(2, begin.call_count)

    def test_server_error_is_request_unknown_but_client_rejection_is_explicit(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected, RemoteRequestUnknown

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        session.post.return_value = _Response({"error": {"code": "upstream"}}, status_code=503)
        with self.assertRaises(RemoteRequestUnknown):
            EmailChangeProtocol().begin(session, "at-test", "new@example.test")

        session.post.return_value = _Response({"error": {"code": "invalid_email"}}, status_code=400)
        with self.assertRaises(RemoteRequestRejected):
            EmailChangeProtocol().begin(session, "at-test", "new@example.test")

    def test_prepared_verify_keeps_remote_response_classification(self):
        from core.email_change_service import EmailChangeProtocol, RemoteRequestRejected, RemoteRequestUnknown

        for status, expected in ((400, RemoteRequestRejected), (503, RemoteRequestUnknown)):
            with self.subTest(status=status):
                session = Mock()
                session.get_chatgpt_headers.return_value = {}
                session.device_id = "device-test"
                session.navigator_language.return_value = "en-US"
                protocol = EmailChangeProtocol()
                prepared = protocol.prepare_verify(session, "at-test", "new@example.test", "123456")
                session.get_chatgpt_headers.side_effect = AssertionError("verify 不应再次准备请求")
                session.post.return_value = _Response({"error": {"code": "rejected"}}, status_code=status)

                with self.assertRaises(expected):
                    protocol.verify(session, "at-test", "new@example.test", "123456", prepared=prepared)

                session.post.assert_called_once()

        session = Mock()
        session.get_chatgpt_headers.return_value = {}
        session.device_id = "device-test"
        session.navigator_language.return_value = "en-US"
        protocol = EmailChangeProtocol()
        prepared = protocol.prepare_verify(session, "at-test", "new@example.test", "123456")
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("response lost")
        session.post.return_value = response
        with self.assertRaises(RemoteRequestUnknown):
            protocol.verify(session, "at-test", "new@example.test", "123456", prepared=prepared)
        session.post.assert_called_once()


class EmailChangeStorageTests(PostgresTestCase):
    def setUp(self):
        self.account_task_schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.account_task_ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        self.account_task_schema_patch.start()
        self.account_task_ready_patch.start()
        record_store.reset_ready()
        operation.reset_ready()
        record_store.init()
        operation.init()
        self.account_id = record_store.insert_row(
            ACCOUNTS,
            {
                "email": "old@example.test",
                "email_source": "outlook",
                "access_token": "old-at",
                "original_email_line": "old@example.test----mail-pass----client----refresh",
                "extra_json": '{"account_password":"keep-me","email_change_marker":"old"}',
            },
        )

    def tearDown(self):
        self.account_task_ready_patch.stop()
        self.account_task_schema_patch.stop()

    def test_writeback_is_atomic_and_preserves_original_mailbox_material(self):
        from core.storage import accounts

        record_store.insert_row(
            record_store.OUTLOOK_POOL,
            {
                "email": "old@example.test",
                "status": "used",
                "used_at": "2026-09-01T12:00:00",
                "registered_account_id": self.account_id,
            },
        )
        self.assertTrue(
            accounts.finish_account_email_change(
                self.account_id,
                ok=True,
                new_email="new@example.test",
                source="outlook",
                material_line="new@example.test----new-pass----new-client----new-refresh",
            )
        )
        row = record_store.get_row(ACCOUNTS, self.account_id)
        self.assertEqual("new@example.test", row["email"])
        self.assertEqual("outlook", row["email_source"])
        self.assertEqual("", row.get("access_token") or "")
        self.assertEqual(
            "old@example.test----mail-pass----client----refresh",
            row["original_email_line"],
        )
        self.assertEqual("new@example.test----new-pass----new-client----new-refresh", row["email_change_material_line"])
        self.assertIn("account_password", row["extra_json"])
        public_account = accounts.get_account(self.account_id)
        self.assertNotIn("email_change_material_line", public_account)

        old_pool = record_store.get_row_by(
            record_store.OUTLOOK_POOL, "email", "old@example.test", lower=True
        )
        self.assertEqual("replaced", old_pool["status"])
        self.assertEqual(self.account_id, old_pool["registered_account_id"])
        self.assertIn("邮箱已换绑", old_pool.get("note") or "")

        from core import db

        self.assertFalse(
            db.release_unconsumed_outlook("old@example.test", note="不应恢复")
        )
        old_pool_after_release = record_store.get_row_by(
            record_store.OUTLOOK_POOL, "email", "old@example.test", lower=True
        )
        self.assertEqual("replaced", old_pool_after_release["status"])

    def test_success_writeback_keeps_recent_login_token_for_post_change_live_check(self):
        from core.storage import accounts

        token = (
            "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0."
            "eyJleHAiOjQxMDAwMDAwMDAsInN1YiI6InRlc3QiLCJhY2NvdW50X2lkIjoiMSJ9."
            "signature"
        )
        with patch(
            "core.chatgpt_plan.token_claims",
            return_value={"token_expires_at": "2100-01-01T00:00:00+00:00", "token_expired": False},
        ):
            self.assertTrue(
                accounts.finish_account_email_change(
                    self.account_id,
                    ok=True,
                    new_email="new@example.test",
                    source="outlook",
                    access_token=token,
                )
            )
        row = record_store.get_row(ACCOUNTS, self.account_id)
        self.assertEqual(token, row["access_token"])
        self.assertEqual("2100-01-01T00:00:00+00:00", row["token_expires_at"])
        self.assertFalse(row["token_expired"])

    def test_failed_writeback_does_not_change_current_email(self):
        from core.storage import accounts

        self.assertTrue(
            accounts.finish_account_email_change(
                self.account_id,
                ok=False,
                new_email="new@example.test",
                source="outlook",
                error="remote rejected",
            )
        )
        row = record_store.get_row(ACCOUNTS, self.account_id)
        self.assertEqual("old@example.test", row["email"])
        self.assertEqual("old-at", row["access_token"])
        self.assertEqual("remote rejected", row["email_change_error"])

    def test_email_change_stage_claim_uses_jsonb_projection(self):
        from core.storage import db_legacy

        self.assertTrue(
            db_legacy.claim_account_email_change(
                self.account_id,
                "outlook",
                "test",
            )
        )
        self.assertTrue(
            db_legacy.mark_account_email_change_running(
                self.account_id,
                "new@example.test",
                source="outlook",
            )
        )
        row = record_store.get_row(ACCOUNTS, self.account_id)
        self.assertEqual("running", row["email_change_status"])
        self.assertEqual("new@example.test", row["email_change_target"])


class EmailChangeDurableOperationTests(PostgresTestCase):
    def setUp(self):
        self.log_dir = tempfile.TemporaryDirectory()
        self.log_patch = patch.object(task_run_log, "_LOG_ROOT", Path(self.log_dir.name))
        self.log_patch.start()
        self.account_task_schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.account_task_ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        self.account_task_schema_patch.start()
        self.account_task_ready_patch.start()
        record_store.reset_ready()
        operation.reset_ready()
        record_store.init()
        operation.init()
        self.account_id = record_store.insert_row(
            ACCOUNTS,
            {
                "email": "queue@example.test",
                "access_token": "at",
                "created_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
            },
        )

    def tearDown(self):
        task_gateway.unregister_operation_handler("email_change")
        self.account_task_ready_patch.stop()
        self.account_task_schema_patch.stop()
        self.log_patch.stop()
        self.log_dir.cleanup()

    def test_submit_and_account_conflict_use_native_durable_task(self):
        from core import email_change_service

        with patch(
            "core.feature_availability.require_email_source",
            return_value=(True, ""),
        ):
            first = email_change_service.submit_email_change(
                self.account_id, source="outlook", dispatch=False,
            )
            second = email_change_service.submit_email_change(
                self.account_id, source="outlook", dispatch=False,
            )

        self.assertTrue(first["accepted"])
        self.assertEqual("email_change", first["task_type"])
        self.assertTrue(second["busy"])
        task = operation.get_task(first["task_id"], include_events=False)
        self.assertEqual("native_operations", task["source_system"])
        self.assertEqual("email_change", task["task_type"])

    def test_submit_rejects_configured_but_unavailable_email_source_before_enqueue(self):
        from core import email_change_service

        with patch(
            "core.feature_availability.require_email_source",
            return_value=(False, "邮箱池没有可用 Outlook 素材"),
        ), patch.object(task_gateway, "submit_durable_operation") as submit:
            result = email_change_service.submit_email_change(
                self.account_id,
                source="outlook",
                dispatch=False,
            )

        self.assertFalse(result["accepted"])
        self.assertIn("邮箱池没有可用", result["error"])
        submit.assert_not_called()

    def test_remote_receipt_phase_can_open_verify_boundary_without_retrying(self):
        created = operation.create_runtime_task(
            task_type="email_change",
            account_id=self.account_id,
            email="queue@example.test",
            trigger="test",
        )
        run = operation.claim_run(
            created["run"]["id"], execution_id="exec-email-change", worker_pid=1,
        )
        context = task_gateway.OperationHandlerContext(run, execution_id="exec-email-change")
        with context.lease():
            context.remote_request_started(
                "change_email.begin", request_id="begin-1",
            )
            context.remote_request_receipt(
                outcome="response_received",
                action="change_email.begin",
                request_id="begin-1",
                detail={"phase_complete": True, "remote_response_confirmed": True},
            )
            context.remote_request_started(
                "change_email.verify", request_id="verify-1",
            )


class EmailChangeProjectionTests(unittest.TestCase):
    def test_progress_and_request_unknown_error_are_explicit(self):
        from core.task_errors import classify_task_error
        from core.task_progress import build_progress_snapshot
        from core.task_stages import flow_for

        self.assertEqual(
            ["email", "network", "login_password", "email_otp", "submit_email", "complete"],
            [item["key"] for item in flow_for("email_change")],
        )
        snapshot = build_progress_snapshot(
            1,
            2,
            "email_change",
            {"status": "attention_required", "result_summary": {"outcome": "request_unknown"}},
            [{"stage": "verify_email", "event_type": "stage.failed", "detail": {"step_state": "failed"}}],
        )
        self.assertIn("result", [step["id"] for step in snapshot["main_steps"]])
        error = classify_task_error("request_unknown: remote response pending", task_type="email_change")
        # 已按任务类型细分缺失回执，保留原有人工核验动作。
        self.assertEqual("email_change_receipt_missing", error["error_code"])
        self.assertEqual("manual_reconcile", error["next_action"])


class EmailChangeRouteTests(unittest.TestCase):
    def setUp(self):
        from webui.routes.accounts import create_accounts_blueprint

        self.app = Flask("email-change-routes")
        self.app.register_blueprint(
            create_accounts_blueprint(
                runtime.WebUIContext(self.app, logging.getLogger("email-change-routes")),
            )
        )

    def test_single_route_submits_selected_source(self):
        from core import email_change_service

        with patch.object(
            email_change_service,
            "submit_email_change",
            return_value={"accepted": True, "task_id": 11, "run_id": 12, "task_type": "email_change"},
        ) as submit, patch(
            "webui.routes.accounts.db.get_account",
            return_value={"id": 7, "email_source": "outlook"},
        ):
            response = self.app.test_client().post(
                "/api/accounts/7/email-change",
                json={"source": "outlook", "idempotency_key": "request-1"},
            )

        self.assertEqual(202, response.status_code)
        self.assertTrue(response.get_json()["ok"])
        submit.assert_called_once_with(
            7,
            source="outlook",
            trigger="manual_email_change",
            idempotency_key="request-1",
        )

    def test_bulk_route_uses_one_native_batch_submission(self):
        from core import email_change_service

        with patch.object(
            email_change_service,
            "submit_email_change_bulk",
            return_value={
                "accepted": True,
                "batch_id": 20,
                "started": [{"account_id": 7}],
                "started_count": 1,
            },
        ) as submit:
            response = self.app.test_client().post(
                "/api/accounts/email-change-bulk",
                json={"account_ids": [7, 7, 8], "source": "outlook"},
            )

        self.assertEqual(202, response.status_code)
        self.assertTrue(response.get_json()["ok"])
        submit.assert_called_once_with(
            [7, 7, 8],
            source="outlook",
            trigger="manual_email_change_bulk",
            idempotency_key=None,
        )
