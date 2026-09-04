# -*- coding: utf-8 -*-
import base64
import json
import os
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, call, patch

from core import account_task_store, codex_retry_service, live_check_service, postgres_store, roxy_codex_oauth, task_run_log, token_refresh_service
from core.openai_auth import AccountUnusableError
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
                "update_account_liveness",
                return_value=True,
            ) as update_liveness,
        ):
            result = codex_retry_service._persist_account_deactivated(
                "account@example.com",
                AccountUnusableError("账号已废", error_code="account_deactivated"),
            )

        self.assertTrue(result)
        update_liveness.assert_called_once_with(
            192,
            {
                "ok": False,
                "status": "deactivated",
                "error": "account_deactivated",
                "validation_method": "account_setup",
            },
        )

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
            patch("core.live_check_service.enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
            patch.object(token_refresh_service, "_REFRESH_BEFORE_HOURS", 24),
        ):
            result = token_refresh_service.enqueue_due_accounts()
        self.assertEqual(1, result["started"])
        enqueue.assert_called_once()
        self.assertEqual(2, enqueue.call_args.kwargs["account_id"])


class AccountStatusTests(PostgresTestCase):
    def test_liveness_persists_only_safe_auth_fingerprint_summary(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            patches = [
                patch.object(webui_app.db, "_ACCOUNTS_JSON", root / "registered.json"),
                patch.object(webui_app.db, "_OUTLOOK_JSON", root / "outlook.json"),
                patch.object(webui_app.db, "_ACCOUNTS_TXT", root / "registered.txt"),
                patch.object(webui_app.db, "_TOKENS_TXT", root / "tokens.txt"),
                patch.object(webui_app.db, "_OUTLOOK_TXT", root / "outlook.txt"),
                patch.object(webui_app.db, "_VIEWER_HTML", root / "viewer.html"),
            ]
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
            patches = [
                patch.object(webui_app.db, "_ACCOUNTS_JSON", root / "registered.json"),
                patch.object(webui_app.db, "_OUTLOOK_JSON", root / "outlook.json"),
                patch.object(webui_app.db, "_ACCOUNTS_TXT", root / "registered.txt"),
                patch.object(webui_app.db, "_TOKENS_TXT", root / "tokens.txt"),
                patch.object(webui_app.db, "_OUTLOOK_TXT", root / "outlook.txt"),
                patch.object(webui_app.db, "_VIEWER_HTML", root / "viewer.html"),
            ]
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
            patches = [
                patch.object(webui_app.db, "_ACCOUNTS_JSON", root / "registered.json"),
                patch.object(webui_app.db, "_OUTLOOK_JSON", root / "outlook.json"),
                patch.object(webui_app.db, "_ACCOUNTS_TXT", root / "registered.txt"),
                patch.object(webui_app.db, "_TOKENS_TXT", root / "tokens.txt"),
                patch.object(webui_app.db, "_OUTLOOK_TXT", root / "outlook.txt"),
                patch.object(webui_app.db, "_VIEWER_HTML", root / "viewer.html"),
            ]
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
            patch("core.live_check_service.enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
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
            patch.object(codex_retry_service.account_task_store, "append_event") as append_event,
            patch.object(codex_retry_service.account_task_store, "finish_task") as finish_task,
            patch("config.reload_all"),
            patch("config.codex.CODEX_OAUTH_DRIVER", "protocol"),
            patch(
                "core.account_proxy.acquire_account_proxy",
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
                "core.codex_oauth.run_codex_oauth",
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
            patch.object(codex_retry_service.account_task_store, "append_event") as append_event,
            patch.object(codex_retry_service.account_task_store, "finish_task"),
            patch("config.reload_all"),
            patch("config.codex.CODEX_OAUTH_DRIVER", "roxy"),
            patch("config.twofa.get_twofa_driver", return_value="browser"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch("core.roxy_registration.setup_roxy_2fa", side_effect=setup_twofa),
            patch("core.roxy_codex_oauth.run_roxy_codex_oauth", side_effect=run_roxy),
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
            save_totp.call_args_list,
            [
                call("a@example.com", secret, setup_pending=True),
                call("a@example.com", secret, setup_pending=False),
            ],
        )
        self.assertTrue(any(call.kwargs.get("stage") == "twofa_result" for call in append_event.call_args_list))
        save_twofa_status.assert_called_once_with("a@example.com", "success", "Authenticator 2FA 已启用")
        route.release.assert_called_once_with(reason="codex-oauth-a@example.com")

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
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch.object(codex_retry_service.account_task_store, "finish_task"),
            patch("config.reload_all"),
            patch("config.codex.CODEX_OAUTH_DRIVER", "roxy"),
            patch("config.twofa.get_twofa_driver", return_value="protocol"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch("core.roxy_registration._fetch_chatgpt_session", return_value={"accessToken": "fresh-chatgpt-token"}),
            patch("core.session.BrowserSession"),
            patch("core.registration.selenium_auth.setup_protocol_2fa_with_browser_fallback", side_effect=setup_protocol),
            patch("core.roxy_codex_oauth.run_roxy_codex_oauth", side_effect=run_roxy),
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

        def set_password(_driver, _email, _password, *, on_password_submitted=None):
            setup_order.append("password")
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
            patch.object(codex_retry_service.db, "update_account_totp_secret", return_value=True) as save_totp,
            patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True),
            patch.object(codex_retry_service.account_task_store, "append_event"),
            patch("config.twofa.get_twofa_driver", return_value="protocol"),
            patch("core.roxy_registration._registration_password", return_value="AccountPassword!123"),
            patch("core.roxy_registration.set_roxy_login_password", side_effect=set_password),
            patch("core.roxy_registration._fetch_chatgpt_session", return_value={"accessToken": "fresh-chatgpt-token"}),
            patch("core.session.BrowserSession"),
            patch("core.registration.selenium_auth.setup_protocol_2fa_with_browser_fallback", side_effect=setup_protocol),
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
            patch("core.roxy_registration._registration_password", return_value="AccountPassword!123"),
            patch("core.roxy_registration.set_roxy_login_password", side_effect=fail_password),
            patch("core.roxy_registration.setup_roxy_2fa", side_effect=setup_twofa),
        ):
            setup = codex_retry_service._build_roxy_account_setup("a@example.com", 101)
            with self.assertRaisesRegex(RuntimeError, "账号密码"):
                setup(object())

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
        ):
            setup = codex_retry_service._build_roxy_account_setup("a@example.com", 101)
            self.assertFalse(setup(object(), {
                "accessToken": "fresh-chatgpt-token",
                "expires": "2026-09-01T00:00:00Z",
            }))

        save_session.assert_called_once_with(
            "a@example.com",
            "fresh-chatgpt-token",
            expires_at="2026-09-01T00:00:00Z",
        )
        self.assertTrue(any(call.kwargs.get("stage") == "token" for call in append_event.call_args_list))


class AccountActionLoginTests(unittest.TestCase):
    def test_about_you_is_completed_and_session_is_passed_to_action(self):
        opened = Mock(profile_id="profile-1")
        driver = Mock(current_url="https://auth.openai.com/about-you")
        client = Mock()
        client.open_profile_with_capacity_wait.return_value = opened
        session = {"accessToken": "fresh-token", "expires": "2026-09-01T00:00:00Z"}
        action = Mock(return_value=True)
        with (
            patch.object(roxy_codex_oauth, "RoxyBrowserClient", return_value=client),
            patch.object(roxy_codex_oauth, "_build_driver", return_value=driver),
            patch.object(roxy_codex_oauth, "_detect_browser_kind", return_value="Roxy"),
            patch.object(roxy_codex_oauth, "_center_browser_window"),
            patch.object(roxy_codex_oauth, "clear_roxy_browser_auth_state"),
            patch.object(roxy_codex_oauth, "_fill_email_and_otp"),
            patch("core.roxy_registration._complete_profile_page", return_value=True) as complete_profile,
            patch("core.roxy_registration._fetch_chatgpt_session", return_value=session),
            patch("core.profile_utils.generate_random_birthday", return_value="1995-01-02"),
            patch.object(roxy_codex_oauth._roxy_cfg, "ROXY_KEEP_BROWSER_OPEN", False),
        ):
            self.assertTrue(roxy_codex_oauth.run_roxy_chatgpt_account_action(
                "a@example.com", action=action,
            ))

        complete_profile.assert_called_once()
        action.assert_called_once_with(driver, session)
        client.open_profile_with_capacity_wait.assert_called_once_with(proxy_url=None)
        client.open_profile.assert_not_called()
        driver.quit.assert_called_once_with()
        client.cleanup_profile.assert_called_once_with(opened)


class AccountTaskApiTests(PostgresTestCase):
    def test_live_check_and_token_refresh_are_separate_api_actions(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        account = {"id": 7, "email": "a@example.com", "access_token": "saved-token"}
        with (
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch.object(account_task_store, "create_batch", side_effect=["live-batch", "refresh-batch"]),
            patch.object(live_check_service, "enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
            patch.object(webui_app.db, "get_account", return_value=account),
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
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch.object(account_task_store, "create_batch", return_value="live-batch"),
            patch.object(live_check_service, "enqueue_account_live_check", return_value={"accepted": True}) as enqueue,
            patch.object(webui_app.db, "get_account", return_value=account),
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
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch.object(webui_app.db, "get_account") as get_account,
        ):
            response = client.post(
                "/api/accounts/check-live-bulk",
                json={"account_ids": [7], "driver": "protocol_v2"},
            )

        self.assertEqual(400, response.status_code)
        self.assertIn("尚未开放", response.get_json()["error"])
        get_account.assert_not_called()

    def test_live_check_bulk_rejects_configured_driver_when_gate_is_closed(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch.object(webui_app.db, "get_account") as get_account,
            patch("config.account.ACCOUNT_LIVE_CHECK_DRIVER", "browser_roxy"),
            patch("config.account.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", False),
        ):
            response = client.post(
                "/api/accounts/check-live-bulk",
                json={"account_ids": [7]},
            )

        self.assertEqual(400, response.status_code)
        self.assertIn("ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", response.get_json()["error"])
        get_account.assert_not_called()

    def test_list_api_returns_task_instances(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        expected = {"ok": True, "items": [{"id": 3, "task_type": "live_check"}], "total": 1, "page": 1, "page_size": 20}
        with (
            patch.object(account_task_store, "list_tasks", return_value=expected),
            patch("core.token_refresh_service.settings", return_value={"enabled": True, "refresh_before_hours": 24}),
        ):
            response = client.get("/api/account-tasks?page_size=20")
        self.assertEqual(200, response.status_code)
        self.assertEqual("live_check", response.get_json()["items"][0]["task_type"])

    def test_ui_contains_unified_task_center_and_at_expiry(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        html = client.get("/", headers={"X-Auth-Code": "test-auth"}).get_data(as_text=True)
        for asset in ("css/modern.css", "js/modern/common.js", "js/modern/accounts.js"):
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
        self.assertIn('id="accountTaskRunSelect"', html)
        self.assertIn('data-account-task-detail-tab="events"', html)
        self.assertIn('data-account-task-detail-tab="logs"', html)
        self.assertIn('data-account-task-detail-tab="artifacts"', html)
        self.assertIn('data-column-filter="accountTaskTypeFilterV2"', html)
        self.assertIn("values: ['registration', 'registration_resume'", html)
        self.assertIn("codex_retry:'Codex 补跑'", html)
        self.assertNotIn('data-codex-log=', html)
        self.assertIn("function _tokenDisplayState", html)
        self.assertIn("label: '正常'", html)
        self.assertIn("label: '过期'", html)
        self.assertIn("label: `失效 · ${liveHttpStatus || '未知'}`", html)
        self.assertIn('data-account-copy-secret="access_token"', html)
        self.assertIn("function configuredLiveCheckDriver", html)
        self.assertIn("driver: configuredLiveCheckDriver()", html)
        self.assertIn("配置驱动", html)
        self.assertIn("实际驱动", html)
        self.assertIn("function meaningfulTaskDetail", html)
        self.assertIn("white-space:normal", html)
        self.assertIn("flex:1 1 auto; min-height:0; overflow:auto", html)

    def test_codex_retry_creates_account_task_instance(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with (
            patch("core.feature_availability.require_feature", return_value=(True, "")),
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
        account = {"id": 7, "email": "a@example.com", "codex_status": "success"}
        with (
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch.object(webui_app.db, "list_codex_accounts", return_value=[{
                "filename": "codex-a@example.com-free.json",
                "email": "a@example.com",
            }]),
            patch.object(webui_app.db, "get_account_by_email", return_value=account),
            patch.object(webui_app.codex_operation_service, "submit_bulk", return_value={
                "accepted": True,
                "batch_id": 1,
                "batch_uuid": "batch-1",
                "started": [{"account_id": 7, "email": "a@example.com", "task_id": 89, "run_id": 90}],
                "started_count": 1,
                "skipped": [],
            }) as submit_bulk,
        ):
            response = client.post("/api/codex/retry-bulk", json={
                "filenames": ["codex-a@example.com-free.json"],
                "workers": 2,
            })

        self.assertEqual(202, response.status_code)
        payload = response.get_json()
        self.assertEqual(1, payload["started_count"])
        self.assertEqual(89, payload["started"][0]["task_id"])
        submit_bulk.assert_called_once_with([7], trigger="manual_bulk")


if __name__ == "__main__":
    unittest.main()
