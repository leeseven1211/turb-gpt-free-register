from __future__ import annotations

import tempfile
import unittest
import logging
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

from core import account_task_store, record_store, task_run_log
from core.record_store import ACCOUNTS
from core.operations import task_gateway
from core.storage import operation
from tests.support_pg import PostgresTestCase
from webui import runtime


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

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

    def test_recent_login_can_force_an_explicit_direct_route(self):
        from core import account_liveness

        old_session = Mock()
        old_session.proxy = "socks5://proxy.example:1080"
        old_session.device_id = "stable-device"
        old_session.browser_profile = {"screen_width": 1920, "screen_height": 1080}
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
            return_value=({"accessToken": "fresh-at"}, "password"),
        ), patch.object(account_liveness, "_warm_authenticated_session"):
            account_liveness.perform_recent_login(
                old_session,
                "old@example.test",
                email_source="email_butler",
                proxy_override="",
            )

        self.assertEqual("", preflight.call_args.args[1])

    def test_follow_reauth_rejects_failed_navigation_response(self):
        from core.account_export import _follow_reauth

        session = Mock()
        session.get_auth_navigate_headers.return_value = {}
        session.get.return_value = _Response({}, status_code=403)

        with self.assertRaises(RuntimeError):
            _follow_reauth(session, "https://auth.example/reauth")

        session.get.assert_called_once()

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

    def test_bare_proxy_403_after_recent_login_retries_once_via_direct_protocol(self):
        from core.email_change_service import (
            RemoteRequestRejected,
            begin_change_with_optional_reauth,
        )

        session = Mock()
        proxy_session = Mock()
        proxy_session.proxy = "socks5://proxy.example:1080"
        direct_session = Mock()
        direct_session.proxy = ""
        first = RemoteRequestRejected(
            "recent login required",
            http_status=401,
        )
        proxy_forbidden = RemoteRequestRejected(
            "change email begin rejected",
            http_status=403,
        )
        with patch(
            "core.email_change_service.EmailChangeProtocol.begin",
            side_effect=[first, proxy_forbidden, {"success": True}],
        ) as begin, patch(
            "core.email_change_service.perform_recent_login",
            side_effect=[
                {"access_token": "proxy-at", "protocol_session": proxy_session},
                {"access_token": "direct-at", "protocol_session": direct_session},
            ],
        ) as recent_login:
            result = begin_change_with_optional_reauth(
                session,
                account_id=7,
                current_email="old@example.test",
                current_source="outlook",
                new_email="new@example.test",
                access_token="old-at",
            )

        self.assertEqual("direct-at", result.access_token)
        self.assertIs(direct_session, result.session)
        self.assertEqual(3, begin.call_count)
        self.assertEqual(2, recent_login.call_count)
        self.assertNotIn("proxy_override", recent_login.call_args_list[0].kwargs)
        self.assertEqual("", recent_login.call_args_list[1].kwargs["proxy_override"])

    def test_context_transport_failure_becomes_request_unknown_without_retry(self):
        from core.email_change_service import RemoteRequestUnknown, begin_change_with_optional_reauth

        session = Mock()
        context = Mock(run_id=19)
        with patch(
            "core.email_change_service.EmailChangeProtocol.begin",
            side_effect=ConnectionError("TLS reset"),
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
        context.remote_request_started.assert_called_once()
        self.assertEqual(
            "unknown",
            context.remote_request_receipt.call_args.kwargs["outcome"],
        )

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
            {"email": "queue@example.test", "access_token": "at"},
        )

    def tearDown(self):
        task_gateway.unregister_operation_handler("email_change")
        self.account_task_ready_patch.stop()
        self.account_task_schema_patch.stop()
        self.log_patch.stop()
        self.log_dir.cleanup()

    def test_submit_and_account_conflict_use_native_durable_task(self):
        from core import email_change_service

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
        self.assertEqual("request_unknown", error["error_code"])
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
