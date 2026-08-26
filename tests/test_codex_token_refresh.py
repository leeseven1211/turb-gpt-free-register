# -*- coding: utf-8 -*-
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from core import codex_token_refresh_service as service, db
from webui.app import create_app
from webui.routes import codex as codex_routes
from tests.support_pg import PostgresTestCase


class CodexOauthMetadataTests(unittest.TestCase):
    def test_reset_export_keeps_oauth_and_sub2_tracking(self):
        existing = {
            "filename": "codex-a@example.com-free.json",
            "exported_at": "2026-08-17T12:00:00",
            "exported_count": 2,
            "sub2_uploaded_count": 1,
            "oauth_refresh_error": "invalid_grant",
        }
        with patch.object(db, "_patch_codex", return_value=existing) as save:
            db.reset_codex_exported("codex-a@example.com-free.json")
        self.assertEqual(
            save.call_args.args,
            ("codex-a@example.com-free.json", {"exported_count": 0, "exported_at": None}),
        )

    def test_status_uses_expired_and_refresh_token_independently(self):
        now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
        with patch.object(service._cfg, "CODEX_TOKEN_REFRESH_BEFORE_HOURS", 24):
            valid = service.oauth_metadata({
                "access_token": "opaque",
                "refresh_token": "refresh",
                "expired": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }, now=now)
            expiring = service.oauth_metadata({
                "access_token": "opaque",
                "refresh_token": "refresh",
                "expired": (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }, now=now)
            expired = service.oauth_metadata({
                "access_token": "opaque",
                "expired": (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }, now=now)

        self.assertEqual("valid", valid["oauth_status"])
        self.assertTrue(valid["oauth_refreshable"])
        self.assertEqual("expiring", expiring["oauth_status"])
        self.assertEqual("expired", expired["oauth_status"])
        self.assertFalse(expired["oauth_refreshable"])

    def test_invalidated_refresh_token_requires_reauthorization(self):
        self.assertTrue(
            service.refresh_error_requires_reauth(
                "refresh_token_invalidated: Your session has ended. Please log in again."
            )
        )
        self.assertTrue(service.refresh_error_requires_reauth("session has ended"))

    def test_refresh_error_extracts_top_level_code(self):
        response = Mock(status_code=400)
        response.json.return_value = {
            "message": "Your session has ended. Please log in again.",
            "type": "invalid_request_error",
            "param": None,
            "code": "refresh_token_invalidated",
        }

        self.assertEqual(
            "refresh_token_invalidated: Your session has ended. Please log in again.",
            service._refresh_error(response),
        )

    def test_refresh_preserves_old_refresh_token_when_server_does_not_rotate_it(self):
        original = {
            "type": "codex",
            "email": "a@example.com",
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "expired": "2026-08-17T00:00:00Z",
        }
        with (
            patch.object(service.db, "read_codex_credential", return_value=(json.dumps(original), "codex-a@example.com-free.json")),
            patch.object(service, "_request_refresh", return_value={"access_token": "new-access", "expires_in": 3600}),
            patch.object(service.db, "write_codex_credential") as write,
            patch.object(service.db, "mark_codex_oauth_refresh") as mark,
        ):
            result = service.refresh_credential("codex-a@example.com-free.json")

        saved = write.call_args.args[1]
        self.assertEqual("new-access", saved["access_token"])
        self.assertEqual("old-refresh", saved["refresh_token"])
        self.assertEqual("expiring", result["oauth_status"])
        mark.assert_called_once_with("codex-a@example.com-free.json", error=None)

    def test_refresh_grant_posts_only_refresh_fields(self):
        response = Mock(status_code=200)
        response.json.return_value = {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}
        with patch.object(service.requests, "post", return_value=response) as post:
            payload = service._request_refresh("old-refresh")

        self.assertEqual("new-refresh", payload["refresh_token"])
        sent = post.call_args.kwargs["data"]
        self.assertEqual("refresh_token", sent["grant_type"])
        self.assertEqual("old-refresh", sent["refresh_token"])
        self.assertNotIn("code", sent)

    def test_scheduled_scan_only_queues_due_refreshable_credentials(self):
        rows = [
            {"filename": "codex-due.json", "oauth_status": "expiring", "oauth_refreshable": True},
            {"filename": "codex-later.json", "oauth_status": "valid", "oauth_refreshable": True},
            {"filename": "codex-no-refresh.json", "oauth_status": "expired", "oauth_refreshable": False},
        ]
        with (
            patch.object(service._cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True),
            patch.object(service.db, "list_codex_accounts", return_value=rows),
            patch.object(service, "enqueue_refresh", return_value={"accepted": True}) as enqueue,
        ):
            result = service.enqueue_due_credentials()

        self.assertEqual(1, result["started"])
        enqueue.assert_called_once_with("codex-due.json", trigger="codex_token_refresh_scheduled")


class CodexOauthRefreshApiTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    def test_bulk_endpoint_creates_token_refresh_tasks(self):
        with (
            patch.object(codex_routes.account_task_store, "create_batch", return_value="batch-1"),
            patch.object(service, "enqueue_refresh", return_value={
                "accepted": True,
                "task_id": 901,
                "filename": "codex-a@example.com-free.json",
                "email": "a@example.com",
            }) as enqueue,
        ):
            response = self.client.post(
                "/api/codex/refresh-token-bulk",
                json={"filenames": ["codex-a@example.com-free.json"]},
            )

        self.assertEqual(202, response.status_code)
        self.assertEqual(1, response.get_json()["started_count"])
        enqueue.assert_called_once_with(
            "codex-a@example.com-free.json",
            trigger="manual_bulk",
            batch_id="batch-1",
        )


if __name__ == "__main__":
    unittest.main()
