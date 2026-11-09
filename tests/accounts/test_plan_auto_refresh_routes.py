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

    def test_bulk_missing_at_uses_one_current_config_read_and_keeps_all_eligible_accounts(self):
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch("webui.routes.accounts.db.get_account", side_effect=self.accounts.get),
            patch("webui.routes.accounts.plan_check_service.get_config_snapshot",
                  return_value={"PLAN_CHECK_AUTO_REFRESH_AT_ENABLED": True}) as snapshot,
            patch("webui.routes.accounts.account_task_store.create_batch", return_value="batch-10") as batch,
            patch("webui.routes.accounts.plan_check_service.enqueue_account_plan_check",
                  return_value={"accepted": True}) as enqueue,
        ):
            response = self.client.post("/api/accounts/check-plan-bulk", json={"account_ids": [1, 2, 3]}, headers=self.headers)
        self.assertEqual(202, response.status_code)
        body = response.get_json()
        self.assertEqual(3, body["started_count"])
        self.assertEqual(0, body["skipped_count"])
        self.assertEqual(["", "synthetic-at", ""], [call.kwargs["access_token"] for call in enqueue.call_args_list])
        self.assertTrue(all(call.kwargs["batch_id"] == "batch-10" for call in enqueue.call_args_list))
        self.assertEqual(3, batch.call_args.kwargs["total_count"])
        snapshot.assert_called_once()

    def test_bulk_auto_refresh_disabled_skips_missing_at_but_keeps_existing_at(self):
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch("webui.routes.accounts.db.get_account", side_effect=self.accounts.get),
            patch("webui.routes.accounts.plan_check_service.get_config_snapshot",
                  return_value={"PLAN_CHECK_AUTO_REFRESH_AT_ENABLED": False}),
            patch("webui.routes.accounts.account_task_store.create_batch", return_value="batch-11") as batch,
            patch("webui.routes.accounts.plan_check_service.enqueue_account_plan_check",
                  return_value={"accepted": True}) as enqueue,
        ):
            response = self.client.post("/api/accounts/check-plan-bulk", json={"account_ids": [1, 2, 3]}, headers=self.headers)
        self.assertEqual(202, response.status_code)
        body = response.get_json()
        self.assertEqual(1, body["started_count"])
        self.assertEqual(2, body["skipped_count"])
        self.assertEqual({1, 3}, {row["id"] for row in body["skipped"]})
        self.assertTrue(all(row["reason"] == "缺少 access_token" for row in body["skipped"]))
        self.assertEqual(2, enqueue.call_args.kwargs["account_id"])
        self.assertEqual(1, batch.call_args.kwargs["total_count"])
