"""账号入口按套餐恢复开关允许缺少 AT 的账号创建查询任务。"""
from unittest import TestCase
from unittest.mock import patch

from webui.app import create_app


class PlanAutoRefreshRouteTests(TestCase):
    def setUp(self):
        self.client = create_app(auth_code="plan-route-test").test_client()
        self.headers = {"X-Auth-Code": "plan-route-test"}
        self.accounts = {
            1: {"id": 1, "email": "missing-at@example.test", "access_token": ""},
            2: {"id": 2, "email": "current-at@example.test", "access_token": "synthetic-at"},
            3: {"id": 3, "email": "second-missing@example.test"},
        }

    def test_single_missing_at_is_queued_when_auto_refresh_is_enabled(self):
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch("webui.routes.accounts.db.get_account", return_value=self.accounts[1]),
            patch("webui.routes.accounts.plan_check_service.get_config_snapshot",
                  return_value={"PLAN_CHECK_AUTO_REFRESH_AT_ENABLED": True}),
            patch("webui.routes.accounts.plan_check_service.enqueue_account_plan_check",
                  return_value={"accepted": True, "task_id": 10}) as enqueue,
        ):
            response = self.client.post("/api/accounts/check-plan", json={"account_id": 1}, headers=self.headers)
        self.assertEqual(202, response.status_code)
        self.assertEqual("", enqueue.call_args.kwargs["access_token"])
        self.assertEqual("manual", enqueue.call_args.kwargs["trigger"])

    def test_single_missing_at_remains_rejected_when_auto_refresh_is_disabled(self):
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch("webui.routes.accounts.db.get_account", return_value=self.accounts[1]),
            patch("webui.routes.accounts.plan_check_service.get_config_snapshot",
                  return_value={"PLAN_CHECK_AUTO_REFRESH_AT_ENABLED": False}),
            patch("webui.routes.accounts.plan_check_service.enqueue_account_plan_check") as enqueue,
        ):
            response = self.client.post("/api/accounts/check-plan", json={"account_id": 1}, headers=self.headers)
        self.assertEqual(400, response.status_code)
        self.assertIn("没有 access_token", response.get_json()["error"])
        enqueue.assert_not_called()

    def test_bulk_submits_complete_selection_once_and_preserves_accepted_counts(self):
        result = {"started_count": 3, "skipped_count": 0, "started": [], "skipped": [], "batch_id": 10}
        with patch("webui.routes.accounts._feature_unavailable", return_value=None), \
                patch("webui.routes.accounts.account_bulk_submission.submit_accounts", return_value=result) as submit, \
                patch("webui.routes.accounts.plan_check_service.enqueue_account_plan_check", side_effect=AssertionError("single enqueue")):
            response = self.client.post("/api/accounts/check-plan-bulk", json={"account_ids": [1, 2, 3]}, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["started_count"], 3)
        self.assertEqual(response.json["skipped_count"], 0)
        submit.assert_called_once_with([1, 2, 3], operation="plan", trigger="manual_bulk",
                                      parameters={"timezone_offset_min": "-"}, request_key=None)

    def test_bulk_preserves_missing_at_classification_from_collection_service(self):
        result = {"started_count": 1, "skipped_count": 2, "started": [{"id": 2}],
                  "skipped": [{"id": 1, "reason": "缺少 access_token"}, {"id": 3, "reason": "缺少 access_token"}]}
        with patch("webui.routes.accounts._feature_unavailable", return_value=None), \
                patch("webui.routes.accounts.account_bulk_submission.submit_accounts", return_value=result):
            response = self.client.post("/api/accounts/check-plan-bulk", json={"account_ids": [1, 2, 3]}, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["started_count"], 1)
        self.assertEqual({row["id"] for row in response.json["skipped"]}, {"1", "3"})
