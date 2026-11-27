"""整批人工重跑创建新回执，旧目标与邮箱快照继续保留。"""
from __future__ import annotations

import copy
import unittest

from core.storage import postgres
from core.storage.operations import store as operations
from tests.teams import test_execution as execution_support


class TeamBatchRetryTests(execution_support.PostgresTestCase):
    """复用原生执行夹具；仅替换远端以外的手工前置状态。"""

    setUp = execution_support.TeamExecutionTests.setUp
    tearDown = execution_support.TeamExecutionTests.tearDown
    bind = execution_support.TeamExecutionTests.bind
    run_task = execution_support.TeamExecutionTests.run_task
    ready = execution_support.TeamExecutionTests.ready

    def test_parent_retry_creates_new_request_without_rewriting_old_items(self):
        team = self.bind()
        request = self.store.create_join_request(
            team["id"],
            targets=[{
                "account_id": self.accounts[1],
                "email_snapshot": "execution-1@example.test",
            }],
            task_factory=self.execution.enqueue_operation,
        )
        self.run_task("team_join_request", request["run_id"])
        original_item = self.store.list_join_items(team["id"], request["id"])["items"][0]
        operations.request_run_cancel(original_item["run_id"])
        self.store.update_invitation(
            team["id"], original_item["invitation_id"],
            changes={"active": False, "execution_status": "failed"},
        )
        self.ready(request["run_id"])
        self.assertEqual(
            "partial_success",
            self.run_task("team_join_request", request["run_id"])["status"],
        )
        old_receipt = copy.deepcopy(self.store.list_join_items(team["id"], request["id"]))
        old_request = copy.deepcopy(self.store.get_join_request(team["id"], request["id"]))
        original_task = operations.get_task(request["task_id"])

        retried = self.execution.retry_task(
            original_task, request_key="team-batch-retry-review-0001",
        )
        replay = self.execution.retry_task(
            original_task, request_key="team-batch-retry-review-0001",
        )
        self.assertEqual(retried, replay)
        new_request_id = retried.get("id") or retried.get("join_request_id")
        self.assertIsNotNone(new_request_id, "整批重跑必须返回新的持久加入请求")
        self.assertNotEqual(str(request["id"]), str(new_request_id))
        new_request = self.store.get_join_request(team["id"], new_request_id)
        self.assertEqual("retry", new_request["operation"])
        self.assertNotEqual(request["run_id"], new_request["run_id"])
        self.assertEqual(
            old_request, self.store.get_join_request(team["id"], request["id"]),
            "人工重跑不能复用并改写原请求的运行身份或汇总",
        )
        self.assertEqual(
            old_receipt, self.store.list_join_items(team["id"], request["id"]),
            "旧请求的逐目标执行回执必须保留",
        )
        new_items = self.store.list_join_items(team["id"], new_request_id)["items"]
        self.assertEqual(len(new_items), 1)
        self.assertEqual(original_item["account_id"], new_items[0]["account_id"])
        with postgres.connect() as conn:
            row = conn.execute(
                f"SELECT email_snapshot,input_invitation_id "
                f"FROM {postgres.qualified('team_join_request_items')} "
                "WHERE request_id=%s AND ordinal=%s",
                (int(new_request_id), new_items[0]["ordinal"]),
            ).fetchone()
        self.assertEqual("execution-1@example.test", row[0])
        self.assertEqual(original_item["invitation_id"], row[1])
        self.run_task("team_join_request", new_request["run_id"])
        new_item = self.store.list_join_items(team["id"], new_request_id)["items"][0]
        self.assertEqual("accepted", new_item["acceptance_status"])
        self.assertNotEqual(original_item["run_id"], new_item["run_id"])


if __name__ == "__main__":
    unittest.main()
