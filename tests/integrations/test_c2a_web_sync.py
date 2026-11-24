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

    def test_bulk_submits_one_collection_and_returns_queue_receipts(self):
        result = {"accepted": True, "status": "queued", "queued_count": 1,
                  "queued": [{"task_id": 17, "run_id": 29}], "updated_count": 0,
                  "failed_count": 0, "skipped_count": 0}
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")), \
                patch("webui.routes.accounts.account_bulk_submission.submit_accounts", return_value=result) as submit, \
                patch("core.integrations.c2a.client.find_unique_account") as remote, \
                patch("webui.routes.accounts.db.get_account", side_effect=AssertionError("single read")):
            response = self.client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": [23, 23]})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["queued_count"], 1)
        self.assertEqual(response.json["updated_count"], 0)
        self.assertEqual(response.json["queued"][0]["task_id"], "17")
        submit.assert_called_once_with([23, 23], operation="c2a", trigger="c2a_manual_reimport")
        remote.assert_not_called()

    def test_bulk_preserves_classified_collection_results_without_remote_write(self):
        result = {"accepted": False, "status": "queued", "queued_count": 0, "queued": [],
                  "updated_count": 0, "failed_count": 1, "skipped_count": 0,
                  "failed": [{"id": 23, "error_code": "c2a_account_deactivated", "error": "关联账号已确认停用"}]}
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")), \
                patch("webui.routes.accounts.account_bulk_submission.submit_accounts", return_value=result), \
                patch("core.integrations.c2a.client.update_account_access_token") as remote:
            response = self.client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": [23]})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["failed"][0]["error_code"], "c2a_account_deactivated")
        remote.assert_not_called()

    def test_bulk_keeps_all_inputs_for_collection_validation(self):
        values = [True, 1.9, 0, -1, "1.0", "01", {}, "23"]
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")), \
                patch("webui.routes.accounts.account_bulk_submission.submit_accounts", return_value={"accepted": True}) as submit, \
                patch("webui.routes.accounts.db.get_account", side_effect=AssertionError("single read")):
            response = self.client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": values})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(submit.call_args.args, (values,))

    def test_bulk_requires_a_json_object(self):
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")):
            response = self.client.post("/api/accounts/c2a/sync-bulk", json=[23])

        self.assertEqual(400, response.status_code)
        self.assertFalse(response.json["ok"])
        self.assertEqual("请求体必须是 JSON 对象", response.json["error"])


if __name__ == "__main__":
    unittest.main()
