# -*- coding: utf-8 -*-
import base64
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core import account_task_store, codex_retry_service, token_refresh_service
from webui.app import create_app


def _jwt_with_exp(exp: datetime) -> str:
    def part(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"{part({'alg': 'none'})}.{part({'exp': int(exp.timestamp())})}.signature"


class AccountTaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(account_task_store, "_DB_PATH", Path(self.tempdir.name) / "tasks.db")
        self.path_patch.start()
        account_task_store._READY_PATH = None

    def tearDown(self):
        account_task_store._READY_PATH = None
        self.path_patch.stop()
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

    def test_recover_marks_running_tasks_interrupted(self):
        task_id = account_task_store.create_task(
            task_type="plan_check", account_id=1, email="a@example.com", trigger="manual"
        )
        account_task_store.start_task(task_id)
        self.assertEqual(1, account_task_store.recover_interrupted())
        self.assertEqual("interrupted", account_task_store.get_task(task_id)["status"])


class TokenRefreshServiceTests(unittest.TestCase):
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
            patch("config.codex.CODEX_OAUTH_DRIVER", "browser_use"),
            patch(
                "core.codex_oauth.run_codex_oauth",
                return_value={"ok": True, "status": "success", "file_path": "/tmp/credential.json", "callback_url": "sensitive"},
            ),
        ):
            result = codex_retry_service.run_worker(
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


class AccountTaskApiTests(unittest.TestCase):
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

    def test_ui_contains_task_submenu_and_at_expiry(self):
        html = (Path(__file__).resolve().parents[1] / "webui" / "templates" / "index.html").read_text("utf-8")
        self.assertIn('data-view="tasks">任务实例', html)
        self.assertIn('id="accountTasksPanel"', html)
        self.assertIn('<option value="codex_retry">Codex 补跑</option>', html)
        self.assertNotIn('data-codex-log=', html)
        self.assertIn("AT 剩余", html)

    def test_codex_retry_creates_account_task_instance(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        account = {"id": 7, "email": "a@example.com", "codex_status": "failed"}
        with (
            patch("core.feature_availability.require_feature", return_value=(True, "")),
            patch.object(codex_retry_service, "reserve", return_value=True),
            patch.object(codex_retry_service.db, "get_account_by_email", return_value=account),
            patch.object(codex_retry_service.db, "update_account_codex_status"),
            patch.object(account_task_store, "create_task", return_value=88) as create_task,
            patch("webui.app.threading.Thread") as thread_cls,
        ):
            response = client.post("/api/codex/retry", json={"email": "a@example.com"})

        self.assertEqual(202, response.status_code)
        self.assertEqual(88, response.get_json()["task_id"])
        create_task.assert_called_once_with(
            task_type="codex_retry",
            account_id=7,
            email="a@example.com",
            trigger="manual",
        )
        thread_cls.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
