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

    def test_recent_login_error_code_is_recognized_without_message_matching(self):
        from core.email_change_service import RemoteRequestRejected, _is_reauth_required

        exc = RemoteRequestRejected(
            "change_email begin rejected",
            http_status=403,
            remote_error_code="recent_login_required",
        )

        self.assertTrue(_is_reauth_required(exc))

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
        first = RuntimeError("reauth_required")
        fresh = {"access_token": "fresh-at"}
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
        self.assertEqual(2, begin.call_count)
        recent_login.assert_called_once()
        self.assertEqual("old@example.test", recent_login.call_args.kwargs["email"])
        self.assertEqual("outlook", recent_login.call_args.kwargs["email_source"])

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
