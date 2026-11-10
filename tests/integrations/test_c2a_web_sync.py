"""C2A 重新导入 API 只创建持久任务，不在 HTTP 请求内写远端。"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core.integrations.c2a import manual_sync
from webui.app import create_app


class C2AWebSyncTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    def test_bulk_is_blocked_when_c2a_configuration_is_unavailable(self):
        with patch("core.runtime.capabilities.require_feature", return_value=(False, "C2A_API_KEY 未配置")), patch(
            "core.integrations.c2a.manual_sync.queue_account"
        ) as queue:
            response = self.client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": [23]})

        self.assertEqual(503, response.status_code)
        self.assertFalse(response.json["ok"])
        self.assertEqual("c2a_sync", response.json["feature"])
        self.assertIn("C2A_API_KEY", response.json["error"])
        queue.assert_not_called()

    def test_bulk_deduplicates_and_returns_only_queue_receipts(self):
        account = {"id": 23, "email": "fixture@example.test"}
        queued = {"accepted": True, "task_id": 17, "run_id": 29, "status": "queued"}
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")), patch(
            "webui.app.db.get_account", return_value=account
        ), patch("core.integrations.c2a.manual_sync.queue_account", return_value=queued) as queue, patch(
            "core.integrations.c2a.client.find_unique_account"
        ) as find_remote, patch("core.integrations.c2a.client.update_account_access_token") as update_remote:
            response = self.client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": [23, 23]})

        self.assertEqual(202, response.status_code)
        self.assertTrue(response.json["accepted"])
        self.assertEqual("queued", response.json["status"])
        self.assertEqual(1, response.json["queued_count"])
        self.assertEqual(0, response.json["updated_count"])
        self.assertEqual(17, response.json["queued"][0]["task_id"])
        queue.assert_called_once_with(account)
        find_remote.assert_not_called()
        update_remote.assert_not_called()

    def test_bulk_preserves_classified_enqueue_failure_without_remote_write(self):
        account = {"id": 23, "email": "fixture@example.test"}
        failure = manual_sync.C2AReimportError(
            "c2a_account_deactivated", "关联账号已确认停用，未向 C2A 更新 AT"
        )
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")), patch(
            "webui.app.db.get_account", return_value=account
        ), patch("core.integrations.c2a.manual_sync.queue_account", side_effect=failure) as queue, patch(
            "core.integrations.c2a.client.update_account_access_token"
        ) as update_remote:
            response = self.client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": [23]})

        self.assertEqual(202, response.status_code)
        self.assertTrue(response.json["accepted"])
        self.assertEqual(0, response.json["queued_count"])
        self.assertEqual(1, response.json["failed_count"])
        self.assertEqual("c2a_account_deactivated", response.json["failed"][0]["error_code"])
        queue.assert_called_once_with(account)
        update_remote.assert_not_called()

    def test_bulk_rejects_bool_float_and_noncanonical_ids_before_account_lookup(self):
        account = {"id": 23, "email": "fixture@example.test"}
        queued = {"accepted": True, "task_id": 17, "run_id": 29, "status": "queued"}
        values = [True, 1.9, 0, -1, "1.0", "01", {}, "23"]
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")), patch(
            "webui.app.db.get_account", return_value=account
        ) as get_account, patch(
            "core.integrations.c2a.manual_sync.queue_account", return_value=queued
        ) as queue:
            response = self.client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": values})

        self.assertEqual(202, response.status_code)
        self.assertEqual(1, response.json["queued_count"])
        self.assertEqual(7, response.json["skipped_count"])
        self.assertEqual(
            {"c2a_local_account_id_invalid"},
            {item["error_code"] for item in response.json["skipped"]},
        )
        get_account.assert_called_once_with(23)
        queue.assert_called_once_with(account)

    def test_bulk_requires_a_json_object(self):
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")):
            response = self.client.post("/api/accounts/c2a/sync-bulk", json=[23])

        self.assertEqual(400, response.status_code)
        self.assertFalse(response.json["ok"])
        self.assertEqual("请求体必须是 JSON 对象", response.json["error"])


if __name__ == "__main__":
    unittest.main()
