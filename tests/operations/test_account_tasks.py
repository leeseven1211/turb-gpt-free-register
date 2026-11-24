# -*- coding: utf-8 -*-
import base64
import json
import os
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, call, patch

from core import account_task_store, operation_task_store
from core.codex import retry_service as codex_retry_service
from core.codex import bulk_submission as codex_bulk_submission
from core.accounts.liveness import service as live_check_service
from core.storage import postgres as postgres_store, records as record_store
from core.storage.operations import store as operation_store
from core.codex.roxy import oauth as roxy_codex_oauth
from core.operations import run_log as task_run_log
from core.operations import task_gateway
from core.accounts import token_refresh as token_refresh_service
from core.auth.challenge import PasswordSetupUnsupportedError
from core.auth.protocol.openai_auth import AccountUnusableError
from webui import app as webui_app
from webui.app import create_app
from tests.support_pg import PostgresTestCase


def _jwt_with_exp(exp: datetime) -> str:
    def part(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"{part({'alg': 'none'})}.{part({'exp': int(exp.timestamp())})}.signature"


class AccountCompletionDeactivationTests(unittest.TestCase):
    def test_confirmed_unusable_account_is_persisted_as_deactivated(self):
        with (
            patch.object(
                codex_retry_service.db,
                "get_account_by_email",
                return_value={"id": 192},
            ),
            patch.object(
                codex_retry_service.db,
                "mark_account_deactivated",
                return_value=True,
            ) as mark_deactivated,
        ):
            result = codex_retry_service._persist_account_deactivated(
                "account@example.com",
                AccountUnusableError("账号已废", error_code="account_deactivated"),
            )

        self.assertTrue(result)
        mark_deactivated.assert_called_once_with(
            192,
            reason="account_deactivated",
            source="account_setup",
        )

    def test_account_setup_preserves_confirmed_unusable_error(self):
        account = {
            "id": 192,
            "email": "account@example.com",
            "access_token": "saved-token",
            "totp_secret": "existing-totp",
            "extra_json": "{}",
        }
        dead = AccountUnusableError("账号已废", error_code="account_deactivated")
        with (
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="Password!123"),
            patch("core.auth.browser.selenium_auth.set_login_password", side_effect=dead),
        ):
            setup = codex_retry_service._build_roxy_account_setup(
                "account@example.com", 101, include_twofa=False,
            )
            with self.assertRaises(AccountUnusableError):
                setup(object())

    def test_deactivated_operation_result_uses_stable_reason_code(self):
        with (
            patch.object(
                codex_retry_service.db,
                "get_account_by_email",
                return_value={"id": 192},
            ),
            patch.object(
                codex_retry_service.db,
                "mark_account_deactivated",
                return_value=True,
            ) as mark_deactivated,
        ):
            self.assertTrue(codex_retry_service._persist_account_deactivated_result(
                "account@example.com",
                {"status": "deactivated", "message": "账号已废（account_deactivated）"},
                source="codex_retry",
            ))

        mark_deactivated.assert_called_once_with(
            192,
            reason="account_deactivated",
            source="codex_retry",
        )

    def test_twofa_setup_preserves_confirmed_unusable_error(self):
        account = {
            "id": 192,
            "email": "account@example.com",
            "access_token": "saved-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        dead = AccountUnusableError("账号已废", error_code="account_deactivated")
        with (
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.auth.browser.selenium_auth.setup_roxy_2fa", side_effect=dead),
        ):
            setup = codex_retry_service._build_roxy_twofa_setup(
                "account@example.com", 101, twofa_driver="browser",
            )
            with self.assertRaises(AccountUnusableError):
                setup(object())

    def test_protocol_mailbox_failure_does_not_fall_back_to_browser(self):
        self.assertFalse(
            codex_retry_service._should_browser_fallback_after_protocol_error(
                RuntimeError("ForwardIMAPError: 等待新的邮箱验证码超时")
            )
        )

    def test_other_protocol_failure_can_still_use_configured_browser_fallback(self):
        self.assertTrue(
            codex_retry_service._should_browser_fallback_after_protocol_error(
                RuntimeError("ProtocolV2AuthError: mfa_enroll_unauthorized")
            )
        )


class AccountTaskStoreTests(unittest.TestCase):
    def setUp(self):
        if not os.getenv("DATABASE_URL"):
            self.skipTest("需要本机 PostgreSQL DATABASE_URL")
        self.tempdir = tempfile.TemporaryDirectory()
        self.task_log_root_patch = patch.object(task_run_log, "_LOG_ROOT", Path(self.tempdir.name))
        self.task_log_tasks_patch = patch.object(task_run_log, "_TASK_LOG_ROOT", Path(self.tempdir.name) / "tasks")
        self.task_log_root_patch.start()
        self.task_log_tasks_patch.start()
        self.schema = f"test_account_tasks_{uuid.uuid4().hex[:12]}"
        # Recovery consults durable permits in the same deployment schema.
        # Isolate both models, rather than redirecting only the legacy alias.
        schema_env = patch.dict(os.environ, {"TURB_DB_SCHEMA": self.schema, "OPERATION_TASK_DB_SCHEMA": self.schema})
        schema_env.start()
        self.addCleanup(schema_env.stop)
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.schema_patch.start()
        self.ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        self.ready_patch.start()
        self.url_patch = patch.object(postgres_store, "database_url", return_value=os.environ["DATABASE_URL"])
        self.url_patch.start()
        self.enabled_patch = patch.object(postgres_store, "enabled", return_value=True)
        self.enabled_patch.start()

    def tearDown(self):
        try:
            with postgres_store.connect() as conn, conn.cursor() as cur:
                cur.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        finally:
            self.enabled_patch.stop()
            self.url_patch.stop()
            self.ready_patch.stop()
            self.schema_patch.stop()
            self.task_log_tasks_patch.stop()
            self.task_log_root_patch.stop()
        self.tempdir.cleanup()

    def test_task_events_are_persisted_and_credentials_are_redacted(self):
        batch_id = account_task_store.create_batch(action_type="live_check", trigger="manual_bulk", total_count=1)
        task_id = account_task_store.create_task(
            task_type="live_check",
            account_id=7,
            email="a@example.com",
            trigger="manual_bulk",
            batch_id=batch_id,
        )
        account_task_store.start_task(task_id)
        account_task_store.append_event(
            task_id,
            stage="probe",
            message="probe complete",
            detail={"access_token": "secret", "token_expires_at": "2026-08-20T00:00:00Z"},
        )
        account_task_store.finish_task(
            task_id,
            status="success",
            message="done",
            result_summary={"ok": True, "refresh_token": "secret"},
            route={"proxy_used": "http://user:pass@1.2.3.4:8080", "network_route": "proxy"},
        )

        task = account_task_store.get_task(task_id)
        self.assertEqual("success", task["status"])
        self.assertEqual("http://***@1.2.3.4:8080", task["proxy_used"])
        self.assertNotIn("refresh_token", task["result_summary"])
        probe = next(event for event in task["events"] if event["stage"] == "probe")
        self.assertNotIn("access_token", probe["detail"])
        self.assertEqual("2026-08-20T00:00:00Z", probe["detail"]["token_expires_at"])
        self.assertEqual("note.info", probe["event_type"])
        self.assertTrue(Path(task["log_file"]).exists())
        self.assertNotIn("secret", Path(task["log_file"]).read_text(encoding="utf-8"))

    def test_recover_marks_running_tasks_interrupted(self):
        task_id = account_task_store.create_task(
            task_type="plan_check", account_id=1, email="a@example.com", trigger="manual"
        )
        account_task_store.start_task(task_id)
        self.assertEqual(1, account_task_store.recover_interrupted())
        self.assertEqual("interrupted", account_task_store.get_task(task_id)["status"])


class TokenRefreshServiceTests(unittest.TestCase):
    def test_deactivated_account_is_skipped_by_scheduled_refresh(self):
        now = datetime.now(timezone.utc)
        accounts = [
            {"id": 1, "email": "dead@example.com", "account_status": "deactivated", "access_token": _jwt_with_exp(now + timedelta(hours=3))},
            {"id": 2, "email": "live@example.com", "access_token": _jwt_with_exp(now + timedelta(hours=3))},
        ]
        with (
            patch.object(token_refresh_service.db, "list_accounts", return_value=accounts),
            patch.object(token_refresh_service.db, "sync_account_token_metadata", return_value=2),
            patch("core.accounts.liveness.service.enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
            patch.object(token_refresh_service, "_REFRESH_BEFORE_HOURS", 24),
        ):
            result = token_refresh_service.enqueue_due_accounts()
        self.assertEqual(1, result["started"])
        enqueue.assert_called_once()
        self.assertEqual(2, enqueue.call_args.kwargs["account_id"])


class AccountStatusTests(PostgresTestCase):
    def test_mark_account_deactivated_propagates_to_codex_credential(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "dead-codex@example.com",
            "codex_status": "success",
        }])[0]
        webui_app.db.save_codex_credential_record(
            "codex-dead-codex@example.com-free.json",
            {
                "email": "dead-codex@example.com",
                "type": "codex",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expired": "2099-01-01T00:00:00Z",
            },
        )

        self.assertTrue(webui_app.db.mark_account_deactivated(
            account_id,
            reason="account_deactivated",
            source="account_setup",
        ))

        credential = record_store.get_row_by(
            record_store.CODEX_CREDENTIALS,
            "filename",
            "codex-dead-codex@example.com-free.json",
        )
        self.assertEqual("deactivated", credential["oauth_status"])
        self.assertEqual("deactivated", credential["oauth_account_status"])
        self.assertTrue(credential["oauth_reauth_required"])

    def test_mark_account_deactivated_updates_status_and_source(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "dead@example.com",
            "codex_status": "skipped",
            "codex_credential_state": "valid",
        }])[0]

        self.assertTrue(webui_app.db.mark_account_deactivated(
            account_id,
            reason="account_deactivated",
            source="account_setup",
        ))

        row = webui_app.db.get_account(account_id)
        self.assertEqual("deactivated", row["account_status"])
        self.assertEqual("deactivated", row["codex_status"])
        self.assertEqual("deactivated", row["codex_credential_state"])
        self.assertEqual("account_deactivated", row["account_status_reason"])
        self.assertEqual("account_setup", row["account_status_source"])

    def test_deactivated_liveness_propagates_to_codex_credential(self):
        account_id = self.seed(record_store.ACCOUNTS, [{
            "email": "dead-live-codex@example.com",
            "codex_status": "success",
        }])[0]
        webui_app.db.save_codex_credential_record(
            "codex-dead-live-codex@example.com-free.json",
            {
                "email": "dead-live-codex@example.com",
                "type": "codex",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expired": "2099-01-01T00:00:00Z",
            },
        )

        self.assertTrue(webui_app.db.update_account_liveness(account_id, {
            "ok": False,
            "status": "deactivated",
            "error": "account_deactivated",
        }))

        credential = record_store.get_row_by(
            record_store.CODEX_CREDENTIALS,
            "filename",
            "codex-dead-live-codex@example.com-free.json",
        )
        self.assertEqual("deactivated", credential["oauth_status"])
        self.assertEqual("deactivated", credential["oauth_account_status"])

    def test_liveness_persists_only_safe_auth_fingerprint_summary(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            patches = []
            with ExitStack() as stack:
                for item in patches:
                    stack.enter_context(item)
                webui_app.db._save_accounts([{"id": 7, "email": "safe@example.com", "access_token": "old"}])
                self.assertTrue(webui_app.db.update_account_liveness(7, {
                    "ok": True,
                    "status": "live",
                    "auth_method": "password_totp",
                    "fingerprint": {
                        "source": "protocol",
                        "profile_ref": "abc123",
                        "screen_width": 1440,
                        "device_id": "private-device-id",
                        "oai_session_id": "private-session-id",
                        "proxy_url": "http://user:password@example.test:8080",
                    },
                }))
                row = webui_app.db.get_account(7)

        self.assertEqual("protocol", row["last_auth_fingerprint"]["source"])
        self.assertEqual(1440, row["last_auth_fingerprint"]["screen_width"])
        self.assertNotIn("device_id", row["last_auth_fingerprint"])
        self.assertNotIn("oai_session_id", row["last_auth_fingerprint"])
        self.assertNotIn("proxy_url", row["last_auth_fingerprint"])
        self.assertNotIn("private-device-id", row["last_auth_fingerprint_text"])

    def test_deactivated_liveness_result_persists_independent_account_status(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            patches = []
            with ExitStack() as stack:
                for item in patches:
                    stack.enter_context(item)
                webui_app.db._save_accounts([{"id": 7, "email": "dead@example.com", "access_token": "old"}])
                self.assertTrue(webui_app.db.update_account_liveness(7, {
                    "ok": False,
                    "status": "deactivated",
                    "checked_at": "2026-08-14T12:00:00",
                    "error": "account_deactivated",
                }))
                row = webui_app.db.get_account(7)
        self.assertEqual("deactivated", row["account_status"])
        self.assertEqual("account_deactivated", row["account_status_reason"])
        self.assertTrue(webui_app.db.account_is_deactivated(row))

    def test_non_deactivated_failure_does_not_mark_account(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            patches = []
            with ExitStack() as stack:
                for item in patches:
                    stack.enter_context(item)
                webui_app.db._save_accounts([{"id": 7, "email": "maybe@example.com", "access_token": "old"}])
                webui_app.db.update_account_liveness(7, {
                    "ok": False,
                    "status": "failed",
                    "http_status": 403,
                    "error": "AT rejected",
                })
                row = webui_app.db.get_account(7)
        self.assertNotEqual("deactivated", row.get("account_status"))
        self.assertEqual(403, row.get("live_check_http_status"))
    def test_only_due_token_is_force_refreshed(self):
        now = datetime.now(timezone.utc)
        accounts = [
            {"id": 1, "email": "due@example.com", "access_token": _jwt_with_exp(now + timedelta(hours=3))},
            {"id": 2, "email": "later@example.com", "access_token": _jwt_with_exp(now + timedelta(days=5))},
        ]
        with (
            patch.object(token_refresh_service.db, "list_accounts", return_value=accounts),
            patch.object(token_refresh_service.db, "sync_account_token_metadata", return_value=2),
            patch("core.accounts.liveness.service.enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
            patch.object(token_refresh_service, "_REFRESH_BEFORE_HOURS", 24),
        ):
            result = token_refresh_service.enqueue_due_accounts()
        self.assertEqual(1, result["started"])
        enqueue.assert_called_once_with(
            account_id=1,
            email="due@example.com",
            trigger="token_refresh_scheduled",
            proxy=None,
            force_refresh=True,
        )


class CodexRetryTaskTests(unittest.TestCase):
    def test_worker_records_sanitized_task_instance(self):
        with (
            tempfile.TemporaryDirectory() as tempdir,
            patch.object(codex_retry_service.db, "get_account_by_email", return_value={"id": 9, "email": "a@example.com"}),
            patch.object(codex_retry_service.db, "update_account_codex_status"),
            patch.object(codex_retry_service.account_task_store, "create_task", return_value=101) as create_task,
            patch.object(codex_retry_service.account_task_store, "start_task") as start_task,
            patch.object(codex_retry_service.account_task_store, "get_task", return_value={}),
            patch.object(codex_retry_service.account_task_store, "append_event") as append_event,
            patch.object(codex_retry_service.account_task_store, "finish_task") as finish_task,
            patch("config.reload_all"),
            patch("config.codex.CODEX_OAUTH_DRIVER", "protocol"),
            patch(
                "core.proxy.account_routes.acquire_account_proxy",
                return_value=Mock(
                    proxy_url="http://proxy.example",
                    provider="test",
                    region="US",
                    mode="pool",
                    public_dict=lambda: {"network_route": "test", "proxy_used": True},
                    release=Mock(),
                ),
            ),
            patch(
                "core.codex.oauth.run_codex_oauth",
                return_value={"ok": True, "status": "success", "file_path": "/tmp/credential.json", "callback_url": "sensitive"},
            ),
        ):
            result = codex_retry_service._run_worker_legacy(
                "a@example.com",
                target_log_path=Path(tempdir) / "codex.log",
                task_trigger="manual",
            )

        self.assertTrue(result["ok"])
        create_task.assert_called_once_with(
            task_type="codex_retry",
            account_id=9,
            email="a@example.com",
            trigger="manual",
        )
        start_task.assert_called_once_with(101, message="开始补跑 Codex OAuth 授权")
        self.assertTrue(any(call.kwargs.get("stage") == "oauth_result" for call in append_event.call_args_list))
        self.assertEqual("success", finish_task.call_args.kwargs["status"])
        self.assertNotIn("callback_url", finish_task.call_args.kwargs["result_summary"])

    def test_roxy_retry_sets_missing_twofa_before_continuing_oauth(self):
        order = []
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        account = {"id": 9, "email": "a@example.com", "totp_secret": ""}
        route = Mock(
            proxy_url="http://proxy.example",
            provider="test",
            region="AR",
            mode="pool",
        )
        route.public_dict.return_value = {
            "network_route": "test-route",
            "proxy_used": "http://proxy.example",
        }

        def setup_twofa(_driver, _email, *, on_secret, existing_secret=None):
            order.append("twofa")
            self.assertIsNone(existing_secret)
            on_secret(secret)
            return secret

        def run_roxy(_email, **kwargs):
            order.append("login")
            kwargs["before_oauth_setup"](object())
            order.append("oauth")
            return {"ok": True, "status": "success", "file_path": "/tmp/credential.json"}

        with (
            tempfile.TemporaryDirectory() as tempdir,
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_session", return_value=True),
            patch.object(codex_retry_service.db, "update_account_totp_secret", return_value=True) as save_totp,
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True) as save_twofa_status,
            patch.object(codex_retry_service.db, "update_account_codex_status"),
            patch.object(codex_retry_service.account_task_store, "start_task"),
            patch.object(codex_retry_service.account_task_store, "get_task", return_value={}),
            patch.object(codex_retry_service.account_task_store, "append_event") as append_event,
            patch.object(codex_retry_service.account_task_store, "finish_task"),
            patch("config.reload_all"),
            patch("config.codex.CODEX_OAUTH_DRIVER", "roxy"),
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route) as acquire,
            patch("core.auth.browser.selenium_auth.setup_roxy_2fa", side_effect=setup_twofa),
            patch("core.codex.roxy.oauth.run_roxy_codex_oauth", side_effect=run_roxy),
        ):
            result = codex_retry_service._run_worker_legacy(
                "a@example.com",
                target_log_path=Path(tempdir) / "codex.log",
                task_id=101,
                task_trigger="manual",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(order, ["login", "twofa", "oauth"])
        self.assertEqual(
            [item.kwargs["purpose"] for item in acquire.call_args_list],
            ["plan-check", "codex-oauth"],
        )
        self.assertEqual(
            save_totp.call_args_list,
            [
                call("a@example.com", secret, setup_pending=True),
                call("a@example.com", secret, setup_pending=False),
            ],
        )
        self.assertTrue(any(call.kwargs.get("stage") == "twofa_result" for call in append_event.call_args_list))
        save_twofa_status.assert_called_once_with("a@example.com", "success", "Authenticator 2FA 已启用")
        self.assertEqual(route.release.call_count, 2)
        route.release.assert_has_calls([
            call(reason="plan-check-a@example.com"),
            call(reason="codex-oauth-a@example.com"),
        ])

    def test_roxy_retry_uses_protocol_twofa_when_configured(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        account = {"id": 9, "email": "a@example.com", "totp_secret": ""}
        route = Mock(proxy_url="http://proxy.example", provider="test", region="AR", mode="pool")
        route.public_dict.return_value = {
            "network_route": "test-route",
            "proxy_used": "http://proxy.example",
        }

        def setup_protocol(_driver, _email, _session, access_token, *, on_secret, existing_secret=None):
            self.assertEqual(access_token, "fresh-chatgpt-token")
            self.assertIsNone(existing_secret)
            on_secret(secret)
            return secret, False

        def run_roxy(_email, **kwargs):
            kwargs["before_oauth_setup"](object())
            return {"ok": True, "status": "success", "file_path": "/tmp/credential.json"}

        with (
            tempfile.TemporaryDirectory() as tempdir,
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_session", return_value=True),
            patch.object(codex_retry_service.db, "update_account_totp_secret", return_value=True) as save_totp,
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True),
            patch.object(codex_retry_service.db, "update_account_codex_status"),
            patch.object(codex_retry_service.account_task_store, "start_task"),
            patch.object(codex_retry_service.account_task_store, "get_task", return_value={}),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch.object(codex_retry_service.account_task_store, "finish_task"),
            patch("config.reload_all"),
            patch("config.codex.CODEX_OAUTH_DRIVER", "roxy"),
            patch("config.twofa.get_twofa_driver", return_value="protocol"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch("core.auth.browser.selenium_auth.fetch_chatgpt_session", return_value={"accessToken": "fresh-chatgpt-token"}),
            patch("core.auth.protocol.session.BrowserSession"),
            patch("core.auth.browser.selenium_auth.setup_protocol_2fa_with_browser_fallback", side_effect=setup_protocol),
            patch("core.codex.roxy.oauth.run_roxy_codex_oauth", side_effect=run_roxy),
        ):
            result = codex_retry_service._run_worker_legacy(
                "a@example.com",
                target_log_path=Path(tempdir) / "codex.log",
                task_id=101,
                task_trigger="manual",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            save_totp.call_args_list,
            [
                call("a@example.com", secret, setup_pending=True),
                call("a@example.com", secret, setup_pending=False),
            ],
        )

    def test_account_setup_runs_password_and_protocol_twofa_serially_on_shared_browser(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        setup_order = []

        def set_password(_driver, _email, _password, *, on_password_prepared=None, on_password_submitted=None):
            setup_order.append("password")
            if on_password_prepared is not None:
                on_password_prepared(_password)
            if on_password_submitted is not None:
                on_password_submitted(_password)

        def setup_protocol(_driver, _email, _session, access_token, *, on_secret, existing_secret=None):
            self.assertEqual(access_token, "fresh-chatgpt-token")
            self.assertIsNone(existing_secret)
            setup_order.append("twofa")
            on_secret(secret)
            return secret, False

        with (
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_session", return_value=True),
            patch.object(codex_retry_service.db, "update_account_login_password", return_value=True),
            patch.object(codex_retry_service.db, "update_account_password_capability", return_value=True),
            patch.object(codex_retry_service.db, "update_account_totp_secret", return_value=True) as save_totp,
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch("config.twofa.get_twofa_driver", return_value="protocol"),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="AccountPassword!123"),
            patch("core.auth.browser.selenium_auth.set_login_password", side_effect=set_password),
            patch("core.auth.browser.selenium_auth.fetch_chatgpt_session", return_value={"accessToken": "fresh-chatgpt-token"}),
            patch("core.auth.protocol.session.BrowserSession"),
            patch("core.auth.browser.selenium_auth.setup_protocol_2fa_with_browser_fallback", side_effect=setup_protocol),
        ):
            setup = codex_retry_service._build_roxy_account_setup(
                "a@example.com", 101, proxy="http://proxy.example"
            )
            self.assertTrue(setup(object()))

        self.assertEqual(
            save_totp.call_args_list,
            [
                call("a@example.com", secret, setup_pending=True),
                call("a@example.com", secret, setup_pending=False),
            ],
        )
        self.assertEqual(setup_order, ["password", "twofa"])

    def test_account_setup_continues_twofa_when_password_step_fails(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        setup_order = []

        def fail_password(_driver, _email, _password, **_kwargs):
            setup_order.append("password")
            raise RuntimeError("password page unavailable")

        def setup_twofa(_driver, _email, *, on_secret, existing_secret=None):
            setup_order.append("twofa")
            on_secret(secret)
            return secret

        with (
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_totp_secret", return_value=True),
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="AccountPassword!123"),
            patch("core.auth.browser.selenium_auth.set_login_password", side_effect=fail_password),
            patch("core.auth.browser.selenium_auth.setup_roxy_2fa", side_effect=setup_twofa),
        ):
            setup = codex_retry_service._build_roxy_account_setup("a@example.com", 101)
            with self.assertRaisesRegex(RuntimeError, "账号密码"):
                setup(object())

        self.assertEqual(setup_order, ["password", "twofa"])

    def test_account_setup_continues_twofa_when_password_is_unsupported(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        setup_order = []

        def unsupported_password(_driver, _email, _password, **_kwargs):
            setup_order.append("password")
            raise PasswordSetupUnsupportedError("eligible=false")

        def setup_twofa(_driver, _email, *, on_secret, existing_secret=None):
            setup_order.append("twofa")
            self.assertIsNone(existing_secret)
            on_secret(secret)
            return secret

        with (
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_password_capability", return_value=True),
            patch.object(codex_retry_service.db, "update_account_totp_secret", return_value=True),
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="AccountPassword!123"),
            patch("core.auth.browser.selenium_auth.set_login_password", side_effect=unsupported_password),
            patch("core.auth.browser.selenium_auth.setup_roxy_2fa", side_effect=setup_twofa),
        ):
            setup = codex_retry_service._build_roxy_account_setup("a@example.com", 101)
            self.assertTrue(setup(object()))

        self.assertEqual(setup_order, ["password", "twofa"])

    def test_missing_password_entry_is_unsupported_and_twofa_continues(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        setup_order = []

        def missing_password_entry(_driver, _email, _password, **_kwargs):
            setup_order.append("password")
            raise RuntimeError("账号设置中未找到“Add password/设置密码”入口")

        def setup_twofa(_driver, _email, *, on_secret, existing_secret=None):
            setup_order.append("twofa")
            self.assertIsNone(existing_secret)
            on_secret(secret)
            return secret

        with (
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_password_capability", return_value=True) as save_capability,
            patch.object(codex_retry_service.db, "update_account_totp_secret", return_value=True),
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="AccountPassword!123"),
            patch("core.auth.browser.selenium_auth.set_login_password", side_effect=missing_password_entry),
            patch("core.auth.browser.selenium_auth.setup_roxy_2fa", side_effect=setup_twofa),
        ):
            setup = codex_retry_service._build_roxy_account_setup("a@example.com", 101)
            self.assertTrue(setup(object()))

        save_capability.assert_called_once_with(
            "a@example.com",
            eligible=False,
            reason="password_settings_entry_unavailable",
            evidence="stable_settings_page",
        )
        self.assertEqual(setup_order, ["password", "twofa"])

    def test_account_setup_persists_fresh_session_before_reporting_success(self):
        pending = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "",
            "totp_secret": "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
            "extra_json": json.dumps({
                "account_password": "saved-password",
                "registration_checkpoint": "email_verification_pending",
            }),
        }
        completed = {**pending, "access_token": "fresh-chatgpt-token"}
        with (
            patch.object(codex_retry_service.db, "get_account_by_email", side_effect=[pending, completed]),
            patch.object(codex_retry_service.db, "update_account_session", return_value=True) as save_session,
            patch.object(codex_retry_service.account_task_store, "append_event") as append_event,
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.auth.browser.selenium_auth.set_login_password") as set_password,
        ):
            setup = codex_retry_service._build_roxy_account_setup("a@example.com", 101, include_password=False)
            self.assertFalse(setup(object(), {
                "accessToken": "fresh-chatgpt-token",
                "expires": "2026-09-01T00:00:00Z",
            }))

        save_session.assert_called_once_with(
            "a@example.com",
            "fresh-chatgpt-token",
            expires_at="2026-09-01T00:00:00Z",
            chatgpt_session={
                "accessToken": "fresh-chatgpt-token",
                "expires": "2026-09-01T00:00:00Z",
            },
        )
        self.assertTrue(any(call.kwargs.get("stage") == "token" for call in append_event.call_args_list))
        set_password.assert_not_called()


class AccountActionLoginTests(unittest.TestCase):
    def test_about_you_is_completed_and_session_is_passed_to_action(self):
        opened = Mock(profile_id="profile-1")
        driver = Mock(current_url="https://auth.openai.com/about-you")
        client = Mock()
        client.open_profile_for_account.return_value = opened
        data_saver = Mock()
        session = {"accessToken": "fresh-token", "expires": "2026-09-01T00:00:00Z"}
        action = Mock(return_value=True)
        stages = []
        with (
            patch.object(roxy_codex_oauth, "RoxyBrowserClient", return_value=client),
            patch.object(roxy_codex_oauth, "_build_driver", return_value=driver),
            patch.object(roxy_codex_oauth, "_detect_browser_kind", return_value="Roxy"),
            patch.object(roxy_codex_oauth, "_center_browser_window"),
            patch.object(roxy_codex_oauth, "clear_roxy_browser_auth_state"),
            patch.object(roxy_codex_oauth, "_fill_email_and_otp", side_effect=lambda *_args, **_kwargs: stages.append(("login", "entered"))),
            patch("core.auth.browser.selenium_auth.complete_profile_page", return_value=True) as complete_profile,
            patch("core.auth.browser.selenium_auth.fetch_chatgpt_session", return_value=session),
            patch("core.registration.profile_utils.generate_random_birthday", return_value="1995-01-02"),
            patch("core.browser.roxy.profile_binding.account_profile_id_by_email", return_value=""),
            patch("core.browser.roxy.profile_binding.persist_account_profile_id", return_value=True),
            patch("core.browser.flow_policy.install_for_flow", return_value=data_saver) as install_for_flow,
            patch("core.browser.traffic.bind_roxy_capture") as bind_capture,
            patch.object(roxy_codex_oauth._roxy_cfg, "ROXY_KEEP_BROWSER_OPEN", False),
        ):
            self.assertTrue(roxy_codex_oauth.run_roxy_chatgpt_account_action(
                "a@example.com", action=action,
                stage_reporter=lambda **event: stages.append((event["stage"], event["state"])),
            ))

        self.assertEqual(stages[:2], [("browser", "success"), ("login", "entered")])
        complete_profile.assert_called_once()
        action.assert_called_once_with(driver, session)
        client.open_profile_for_account.assert_called_once_with(
            profile_id=None, proxy_url=None, data_saver_flow="account_action"
        )
        bind_capture.assert_called_once_with(opened, purpose="account_action")
        install_for_flow.assert_called_once_with(
            "account_action", opened, driver, label="ChatGPT 账号操作"
        )
        data_saver.stop.assert_called_once_with()
        client.open_profile.assert_not_called()
        driver.quit.assert_called_once_with()
        client.cleanup_profile.assert_called_once_with(opened)

    def test_profile_open_failure_does_not_report_browser_started(self):
        client = Mock()
        client.open_profile_for_account.side_effect = RuntimeError("浏览器环境启动失败")
        stage_reporter = Mock()
        with (
            patch.object(roxy_codex_oauth, "RoxyBrowserClient", return_value=client),
            patch.object(roxy_codex_oauth, "_build_driver") as build_driver,
            patch("core.browser.roxy.profile_binding.account_profile_id_by_email", return_value=""),
        ):
            with self.assertRaisesRegex(RuntimeError, "浏览器环境启动失败"):
                roxy_codex_oauth.run_roxy_chatgpt_account_action(
                    "a@example.com", action=Mock(), stage_reporter=stage_reporter,
                )

        build_driver.assert_not_called()
        stage_reporter.assert_not_called()


class AccountTaskApiTests(PostgresTestCase):
    def test_account_receipts_recover_first_runs_for_all_supported_submission_routes(self):
        ids = self.seed(record_store.ACCOUNTS, [
            {"email": f"receipt-{index}@example.test", "access_token": "saved-token",
             "email_source": source}
            for index, source in enumerate([
                "cloudflare", "cloudflare", "cloudflare", "cloudflare",
                "icloud_hide", "icloud_hide", "cloudflare",
            ])
        ])
        client = create_app(auth_code="test-auth").test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        actions = [
            ("/api/accounts/check-live-bulk", {"account_ids": [ids[0], ids[6]]}, 2),
            ("/api/accounts/refresh-token-bulk", {"account_ids": [ids[1]]}, 1),
            ("/api/accounts/check-plan", {"account_id": ids[2]}, 1),
            ("/api/accounts/check-plan-bulk", {"account_ids": [ids[3]]}, 1),
            (f"/api/accounts/{ids[6]}/check-deactivation-mail", None, 1),
            ("/api/accounts/check-deactivation-mail-bulk", {"account_ids": ids[4:6]}, 1),
        ]
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(live_check_service, "deployment_unavailable", return_value=None),
            patch("core.operations.task_gateway.notify_dispatch"),
        ):
            for path, payload, run_count in actions:
                with self.subTest(path=path):
                    headers = {"X-Account-Request-Key": str(uuid.uuid4())}
                    before = client.get("/api/accounts/operation-receipt", headers=headers)
                    self.assertEqual(200, before.status_code)
                    self.assertEqual({"ok": True, "found": False, "items": []}, before.get_json())

                    sent = client.post(path, headers=headers, json=payload)
                    self.assertEqual(202, sent.status_code)
                    body = sent.get_json()
                    submitted = body["started"] if isinstance(body.get("started"), list) else [body]
                    self.assertTrue(submitted, body)
                    expected = [
                        {"task_id": str(task_id), "run_id": str(run_id)}
                        for task_id, run_id in sorted({(item["task_id"], item["run_id"]) for item in submitted})
                    ]
                    self.assertEqual(run_count, len(expected))
                    receipt = client.get("/api/accounts/operation-receipt", headers=headers)
                    self.assertEqual(200, receipt.status_code)
                    self.assertEqual({"ok": True, "found": True, "items": expected}, receipt.get_json())
                    self.assertEqual("no-store", receipt.headers["Cache-Control"])

    def test_account_receipt_stays_with_original_run_after_task_retry(self):
        account_id, = self.seed(record_store.ACCOUNTS, [
            {"email": "receipt-retry@example.test", "access_token": "saved-token"},
        ])
        client = create_app(auth_code="test-auth").test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        headers = {"X-Account-Request-Key": "ffffffff-ffff-4fff-8fff-ffffffffffff"}
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch("core.operations.task_gateway.notify_dispatch"),
        ):
            sent = client.post("/api/accounts/check-plan", json={"account_id": account_id}, headers=headers)
            self.assertEqual(202, sent.status_code)
            original = sent.get_json()
            operation_task_store.finish_run(original["run_id"], status="failed", error="测试重跑")
            retried = operation_task_store.retry_runtime_task(original["task_id"])
            receipt = client.get("/api/accounts/operation-receipt", headers=headers)
        self.assertNotEqual(original["run_id"], retried["id"])
        self.assertEqual(
            [{"task_id": str(original["task_id"]), "run_id": str(original["run_id"])}],
            receipt.get_json()["items"],
        )

    def test_account_receipt_does_not_report_a_rejected_busy_claim(self):
        account_id, = self.seed(record_store.ACCOUNTS, [
            {"email": "receipt-busy@example.test", "access_token": "saved-token",
             "live_check_status": "queued", "live_check_queued_at": datetime.now().isoformat()},
        ])
        client = create_app(auth_code="test-auth").test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        headers = {"X-Account-Request-Key": uuid.uuid4().hex}
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(live_check_service, "deployment_unavailable", return_value=None),
            patch("core.operations.task_gateway.notify_dispatch"),
        ):
            response = client.post("/api/accounts/check-live-bulk", json={"account_ids": [account_id]}, headers=headers)
            receipt = client.get("/api/accounts/operation-receipt", headers=headers)
        self.assertEqual(202, response.status_code)
        self.assertEqual(0, response.get_json()["started_count"])
        self.assertEqual(1, response.get_json()["busy_count"])
        self.assertEqual({"ok": True, "found": False, "items": []}, receipt.get_json())

    def test_account_request_replay_after_finish_keeps_original_run_and_accepts_new_key(self):
        ids = self.seed(record_store.ACCOUNTS, [
            {"email": f"receipt-replay-{i}@example.test", "access_token": "saved-token", "email_source": source}
            for i, source in enumerate(("cloudflare", "cloudflare", "icloud_hide", "icloud_hide"))
        ])
        client = create_app(auth_code="test-auth").test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        actions = [
            ("/api/accounts/check-live-bulk", {"account_ids": [ids[0]]}, "live_check_status"),
            ("/api/accounts/refresh-token-bulk", {"account_ids": [ids[0]]}, "live_check_status"),
            ("/api/accounts/check-plan", {"account_id": ids[0]}, "plan_check_status"),
            (f"/api/accounts/{ids[1]}/check-deactivation-mail", None, "deactivation_mail_scan_status"),
            ("/api/accounts/check-deactivation-mail-bulk", {"account_ids": ids[2:]}, "deactivation_mail_scan_status"),
        ]
        headers = {"X-Account-Request-Key": str(uuid.uuid4())}
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(live_check_service, "deployment_unavailable", return_value=None),
            patch("core.operations.task_gateway.notify_dispatch"),
        ):
            for path, payload, status_field in actions:
                with self.subTest(path=path):
                    def send(request_headers, output=payload):
                        response = client.post(path, json=output, headers=request_headers)
                        self.assertEqual(202, response.status_code)
                        body = response.get_json()
                        return body["started"][0] if isinstance(body.get("started"), list) else body

                    account_id = ids[1] if payload is None else (
                        payload["account_ids"][0] if "account_ids" in payload else payload["account_id"]
                    )

                    def finish(run_id):
                        operation_task_store.finish_run(run_id, status="failed", error="测试完成")
                        record_store.patch_row(record_store.ACCOUNTS, account_id, {status_field: "failed"})

                    original = send(headers)
                    finish(original["run_id"])
                    replay = send(headers, {"account_ids": ids[2:][::-1]} if path.endswith("mail-bulk") else payload)
                    self.assertEqual((original["task_id"], original["run_id"]), (replay["task_id"], replay["run_id"]))
                    self.assertEqual("failed", webui_app.db.get_account(account_id)[status_field])
                    renewed = send({"X-Account-Request-Key": str(uuid.uuid4())})
                    self.assertNotEqual(original["run_id"], renewed["run_id"])
                    finish(renewed["run_id"])

    def test_account_request_receipt_hides_deleted_task_but_fresh_key_can_submit(self):
        account_id, = self.seed(record_store.ACCOUNTS, [
            {"email": "receipt-delete@example.test", "access_token": "saved-token"},
        ])
        client = create_app(auth_code="test-auth").test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        headers = {"X-Account-Request-Key": str(uuid.uuid4())}
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch("core.operations.task_gateway.notify_dispatch"),
        ):
            sent = client.post("/api/accounts/check-plan", json={"account_id": account_id}, headers=headers).get_json()
            operation_task_store.finish_run(sent["run_id"], status="failed", error="测试完成")
            record_store.patch_row(record_store.ACCOUNTS, account_id, {"plan_check_status": "failed"})
            self.assertEqual(1, operation_task_store.delete_tasks([sent["task_id"]])["deleted_count"])
            receipt = client.get("/api/accounts/operation-receipt", headers=headers)
            fresh = client.post("/api/accounts/check-plan", json={"account_id": account_id},
                                headers={"X-Account-Request-Key": str(uuid.uuid4())})
        self.assertEqual({"ok": True, "found": False, "items": []}, receipt.get_json())
        self.assertEqual(202, fresh.status_code)
        self.assertNotEqual(sent["task_id"], fresh.get_json()["task_id"])

    def test_concurrent_keyed_plan_submissions_return_one_active_run(self):
        account_id, = self.seed(record_store.ACCOUNTS, [
            {"email": "receipt-concurrent@example.test", "access_token": "saved-token"},
        ])
        app = create_app(auth_code="test-auth")
        headers = {"X-Auth-Code": "test-auth", "X-Account-Request-Key": str(uuid.uuid4())}

        def send():
            return app.test_client().post("/api/accounts/check-plan", json={"account_id": account_id}, headers=headers)

        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch("core.operations.task_gateway.notify_dispatch") as dispatch,
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            results = [pool.submit(send) for _ in range(2)]
            replies = [result.result(timeout=15) for result in results]
            dispatch.assert_called_once()
        self.assertEqual([202, 202], [reply.status_code for reply in replies])
        bodies = [reply.get_json() for reply in replies]
        self.assertEqual({False, True}, {body["reused"] for body in bodies})
        self.assertEqual(1, len({(body["task_id"], body["run_id"]) for body in bodies}))
        self.assertTrue(all(body["status"] == "queued" and not body["busy"] for body in bodies))

    def test_receipt_request_rejects_invalid_keys(self):
        client = create_app(auth_code="test-auth").test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        headers = {"X-Account-Request-Key": "%"}
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")):
            lookup = client.get("/api/accounts/operation-receipt", headers=headers)
            submission = client.post("/api/accounts/check-live-bulk", json={"account_ids": [1]}, headers=headers)
        self.assertEqual(400, lookup.status_code)
        self.assertEqual(400, submission.status_code)

    def test_token_refresh_bulk_accepts_more_than_500_accounts_and_deduplicates_ids(self):
        account_ids = self.seed(record_store.ACCOUNTS, [
            {"email": f"refresh-{index}@example.test"} for index in range(501)
        ])
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(account_task_store, "create_batch", return_value="refresh-batch") as create_batch,
            patch.object(
                live_check_service, "enqueue_account_live_check", return_value={"accepted": True},
            ) as enqueue,
            patch.object(record_store, "list_rows", wraps=record_store.list_rows) as load_accounts,
        ):
            response = client.post(
                "/api/accounts/refresh-token-bulk",
                json={"account_ids": [*account_ids, account_ids[0], str(account_ids[-1])]},
            )

        self.assertEqual(202, response.status_code)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(501, payload["started_count"])
        self.assertEqual(account_ids, [item["id"] for item in payload["started"]])
        self.assertEqual([], payload["skipped"])
        self.assertEqual(0, payload["failed_count"])
        create_batch.assert_called_once_with(
            action_type="token_refresh", trigger="manual_bulk", total_count=501,
        )
        self.assertEqual(account_ids, [item.kwargs["account_id"] for item in enqueue.call_args_list])
        self.assertTrue(all(item.kwargs["force_refresh"] for item in enqueue.call_args_list))
        load_accounts.assert_called_once()
        self.assertIs(record_store.ACCOUNTS, load_accounts.call_args.args[0])

    def test_bulk_account_preflight_preserves_results_and_uses_one_read(self):
        active_id, deactivated_id = self.seed(record_store.ACCOUNTS, [
            {"email": "ready@example.test", "access_token": "synthetic-at"},
            {"email": "deactivated@example.test", "account_status": "deactivated"},
        ])
        overflow_id = 2**63
        ids = [overflow_id, deactivated_id, "bad-id", active_id, str(active_id)]
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        for action, service, expected_skips in (
            ("check-live", "live_check_service.enqueue_account_live_check",
             [("bad-id", "ID 非法"), (overflow_id, "账号不存在"), (deactivated_id, "账号已标记为封号")]),
            ("refresh-token", "live_check_service.enqueue_account_live_check",
             [("bad-id", "ID 非法"), (overflow_id, "账号不存在"), (deactivated_id, "账号已标记为封号")]),
            ("check-plan", "plan_check_service.enqueue_account_plan_check",
             [(overflow_id, "账号不存在"), (deactivated_id, "账号已废号"), ("bad-id", "ID 非法")]),
        ):
            with (
                self.subTest(action=action),
                patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
                patch.object(account_task_store, "create_batch", return_value="bulk-batch"),
                patch(f"webui.routes.accounts.{service}", return_value={"accepted": True}) as enqueue,
                patch.object(record_store, "list_rows", wraps=record_store.list_rows) as load_accounts,
            ):
                response = client.post(f"/api/accounts/{action}-bulk", json={"account_ids": ids})
                self.assertEqual(202, response.status_code)
                payload = response.get_json()
                self.assertEqual([active_id], [item["id"] for item in payload["started"]])
                self.assertEqual(expected_skips, [(item["id"], item["reason"]) for item in payload["skipped"]])
                load_accounts.assert_called_once()
                enqueue.assert_called_once()

    def test_token_refresh_bulk_still_requires_nonempty_id_array(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(account_task_store, "create_batch") as create_batch,
            patch.object(live_check_service, "enqueue_account_live_check") as enqueue,
        ):
            for invalid_ids in (None, [], "1,2", {"id": 1}, 1):
                with self.subTest(account_ids=invalid_ids):
                    response = client.post(
                        "/api/accounts/refresh-token-bulk", json={"account_ids": invalid_ids},
                    )
                    self.assertEqual(400, response.status_code)
                    self.assertFalse(response.get_json()["ok"])

        create_batch.assert_not_called()
        enqueue.assert_not_called()

    def test_live_check_and_token_refresh_are_separate_api_actions(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        account = {"id": 7, "email": "a@example.com", "access_token": "saved-token"}
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(account_task_store, "create_batch", side_effect=["live-batch", "refresh-batch"]),
            patch.object(live_check_service, "enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
            patch.object(record_store, "list_rows", return_value=[account]),
        ):
            live_response = client.post("/api/accounts/check-live-bulk", json={"account_ids": [7]})
            refresh_response = client.post("/api/accounts/refresh-token-bulk", json={"account_ids": [7]})

        self.assertEqual(202, live_response.status_code)
        self.assertEqual(202, refresh_response.status_code)
        self.assertEqual(2, enqueue.call_count)
        live_call, refresh_call = enqueue.call_args_list
        self.assertEqual("manual_bulk", live_call.kwargs["trigger"])
        self.assertFalse(live_call.kwargs["force_refresh"])
        self.assertEqual("token_refresh_manual", refresh_call.kwargs["trigger"])
        self.assertTrue(refresh_call.kwargs["force_refresh"])

    def test_live_check_bulk_forwards_explicit_driver_override_only_to_live_tasks(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        account = {"id": 7, "email": "a@example.com", "access_token": "saved-token"}
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(account_task_store, "create_batch", return_value="live-batch"),
            patch.object(live_check_service, "enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
            patch.object(record_store, "list_rows", return_value=[account]),
            patch("config.account.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", True),
        ):
            response = client.post(
                "/api/accounts/check-live-bulk",
                json={"account_ids": [7], "driver": "browser_roxy"},
            )

        self.assertEqual(202, response.status_code)
        enqueue.assert_called_once()
        self.assertEqual("browser_roxy", enqueue.call_args.kwargs["driver"])

    def test_live_check_bulk_rejects_invalid_driver_before_loading_accounts(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(record_store, "list_rows") as load_accounts,
        ):
            response = client.post(
                "/api/accounts/check-live-bulk",
                json={"account_ids": [7], "driver": "protocol_v2"},
            )

        self.assertEqual(400, response.status_code)
        self.assertIn("尚未开放", response.get_json()["error"])
        load_accounts.assert_not_called()

    def test_live_check_bulk_rejects_configured_driver_when_gate_is_closed(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(record_store, "list_rows") as load_accounts,
            patch("config.account.ACCOUNT_LIVE_CHECK_DRIVER", "browser_roxy"),
            patch("config.account.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", False),
        ):
            response = client.post(
                "/api/accounts/check-live-bulk",
                json={"account_ids": [7]},
            )

        self.assertEqual(400, response.status_code)
        self.assertIn("ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", response.get_json()["error"])
        load_accounts.assert_not_called()

    def test_list_api_returns_task_instances(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        expected = {"ok": True, "items": [{"id": 3, "task_type": "live_check"}], "total": 1, "page": 1, "page_size": 20}
        with (
            patch.object(account_task_store, "list_tasks", return_value=expected),
            patch("core.accounts.token_refresh.settings", return_value={"enabled": True, "refresh_before_hours": 24}),
        ):
            response = client.get("/api/account-tasks?page_size=20")
        self.assertEqual(200, response.status_code)
        self.assertEqual("live_check", response.get_json()["items"][0]["task_type"])

    def test_ui_contains_unified_task_center_and_at_expiry(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        html = client.get("/", headers={"X-Auth-Code": "test-auth"}).get_data(as_text=True)
        for asset in (
            "css/shell.css", "js/shared/common.js", "js/pages/accounts/page.js",
            "js/pages/accounts/bridge.js",
            "js/pages/operations/page.js", "js/pages/accounts/email-change.js",
            "js/pages/accounts/inspection.js",
        ):
            response = client.get(f"/static/{asset}")
            try:
                self.assertEqual(response.status_code, 200, asset)
                html += "\n" + response.get_data(as_text=True)
            finally:
                response.close()
        self.assertIn('data-tab="tasks"', html)
        self.assertIn('任务中心', html)
        self.assertLess(html.index('data-tab="codex"'), html.index('data-tab="tasks"'))
        self.assertLess(html.index('data-tab="tasks"'), html.index('data-tab="outlook"'))
        self.assertIn('id="accountTasksPanel"', html)
        self.assertEqual(1, html.count('id="task-center-root"'))
        self.assertIn('data-module-url="/static/task-center/task-center.js', html)
        self.assertIn('data-style-url="/static/task-center/task-center.css', html)
        self.assertNotIn('id="accountTaskLogPanel"', html)
        # 运行切换、筛选、详情标签与中文动作由 Vue 组件测试覆盖。
        self.assertNotIn('data-codex-log=', html)
        self.assertIn("function _tokenDisplayState", html)
        self.assertIn("label: '正常'", html)
        self.assertIn("label: '过期'", html)
        self.assertIn("label: `失效 · ${liveHttpStatus || '未知'}`", html)
        self.assertIn('data-account-copy-secret="access_token"', html)
        self.assertIn("function configuredLiveCheckDriver", html)
        self.assertIn("configuredLiveCheckDriver: () => configuredLiveCheckDriver()", html)
        # Queue writes moved to the Vue action owner; the legacy entry only
        # provides saved configuration to that owner.
        action_source = (
            Path(__file__).resolve().parents[2]
            / "frontend/src/features/accounts/queuedActions.ts"
        ).read_text(encoding="utf-8")
        self.assertIn("driver: deps.configuredLiveCheckDriver()", action_source)
        self.assertIn("'/api/accounts/check-live-bulk'", action_source)
        self.assertIn("配置驱动", action_source)
        self.assertIn("实际驱动", action_source)
        self.assertIn("result.live_check_driver", action_source)
        self.assertIn("white-space:normal", html)
        self.assertIn("flex:1 1 auto; min-height:0; overflow:auto", html)

    def test_codex_retry_creates_account_task_instance(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(webui_app.codex_operation_service, "submit", return_value={
                "accepted": True, "task_id": 88, "run_id": 99,
                "account_id": 7, "email": "a@example.com", "status": "queued",
            }) as submit,
        ):
            response = client.post("/api/codex/retry", json={"email": "a@example.com"})

        self.assertEqual(202, response.status_code)
        self.assertEqual(88, response.get_json()["task_id"])
        self.assertEqual(99, response.get_json()["run_id"])
        submit.assert_called_once_with("a@example.com", trigger="manual")

    def test_codex_retry_bulk_accepts_selected_credential_filenames(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        account_id = 2**53 + 1
        record_store.insert_row(record_store.ACCOUNTS, {
            "id": account_id, "email": "a@example.com", "codex_status": "success",
        })
        record_store.insert_row(record_store.CODEX_CREDENTIALS, {
            "filename": "codex-a@example.com-free.json", "email": "a@example.com",
        })
        with (
            patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
            patch.object(webui_app.codex_operation_service, "_config_snapshot", return_value={"oauth_driver": "protocol"}),
            patch.object(webui_app.codex_operation_service, "_deployment_unavailable", return_value=None),
            patch.object(webui_app.codex_operation_service, "_feature_ready", return_value=(True, "")),
            patch.object(task_gateway, "notify_dispatch"),
        ):
            response = client.post("/api/codex/retry-bulk", json={
                "filenames": ["codex-a@example.com-free.json"],
            })

        self.assertEqual(202, response.status_code)
        payload = response.get_json()
        self.assertEqual(1, payload["started_count"])
        started = payload["started"][0]
        self.assertEqual("codex-a@example.com-free.json", started["filename"])
        self.assertEqual(str(account_id), started["account_id"])
        self.assertRegex(started["task_id"], r"^[1-9][0-9]*$")
        self.assertRegex(started["run_id"], r"^[1-9][0-9]*$")
        run = operation_store.get_run(int(started["run_id"]))
        self.assertEqual("codex_retry", run["task_type"])
        self.assertEqual(account_id, run["account_id"])
        self.assertEqual(str(run["batch_id"]), payload["batch_id"])

    def test_codex_stop_bulk_cancels_only_codex_runs(self):
        first_id = 2**53 + 1
        second_id = first_id + 1
        for account_id, email in ((first_id, "codex@example.com"), (second_id, "plan@example.com")):
            record_store.insert_row(record_store.ACCOUNTS, {"id": account_id, "email": email})
        codex = operation_store.create_runtime_task(
            task_type="codex_retry", account_id=first_id, email="codex@example.com",
        )
        plan = operation_store.create_runtime_task(
            task_type="plan_check", account_id=second_id, email="plan@example.com",
        )

        client = create_app(auth_code="test-auth").test_client()
        response = client.post("/api/codex/stop-bulk", json={"account_ids": [str(first_id), str(second_id)]},
                               headers={"X-Auth-Code": "test-auth"})

        self.assertEqual(200, response.status_code)
        result = response.get_json()
        self.assertEqual(1, result["stopped_count"])
        self.assertEqual(1, result["skipped_count"])
        self.assertEqual(str(first_id), result["stopped"][0]["id"])
        self.assertEqual(str(codex["run"]["id"]), result["stopped"][0]["run_id"])
        self.assertEqual(str(second_id), result["skipped"][0]["id"])
        self.assertEqual("run_not_active", result["skipped"][0]["reason_code"])
        self.assertEqual("cancelled", operation_store.get_run(codex["run"]["id"])["status"])
        self.assertEqual("queued", operation_store.get_run(plan["run"]["id"])["status"])

    def test_codex_execution_bulk_errors_are_json(self):
        client = create_app(auth_code="test-auth").test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        for path, submitter, body in (
            ("retry-bulk", "submit_reauthorization", {"account_ids": [1]}),
            ("stop-bulk", "cancel_reauthorization", {"account_ids": [1]}),
            ("refresh-token-bulk", "submit_refresh", {"filenames": ["codex-a.json"]}),
        ):
            with (
                self.subTest(path=path),
                patch("core.runtime.capabilities.require_feature", return_value=(True, "")),
                patch.object(codex_bulk_submission, submitter, side_effect=ValueError("idempotency_key_conflict")),
            ):
                invalid = client.post(f"/api/codex/{path}", json=["not an object"])
                self.assertEqual(400, invalid.status_code)
                self.assertFalse(invalid.get_json()["ok"])
                conflict = client.post(f"/api/codex/{path}", json=body)
                self.assertEqual(409, conflict.status_code)
                self.assertEqual("idempotency_key_conflict", conflict.get_json()["reason_code"])


if __name__ == "__main__":
    unittest.main()
