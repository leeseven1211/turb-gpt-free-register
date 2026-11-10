"""历史轮次的结果筛选包含未展开成员，且不越过该轮固定范围。"""
import uuid
from unittest.mock import patch

from core.storage import records
from core.storage.operations import bulk, bulk_common as common
from tests.support_pg import PostgresTestCase


class ImplicitRoundMembersTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()
        settings = patch("core.bulk_operations.catalog.capture_settings",
                         return_value={"config_revision": "implicit-test", "effective_settings": {}})
        settings.start()
        self.addCleanup(settings.stop)

    def batch(self):
        ids = self.seed(records.ACCOUNTS, [
            {"email": f"implicit-{number}@example.test", "created_at": "2026-10-15T10:00:00"}
            for number in range(5)
        ])
        selection = bulk.create_selection(request_key=uuid.uuid4().hex,
            source={"kind": "ids", "ids": ids}, operation_key="plan_check", config_revision="implicit-test")
        bulk.freeze_selection(selection["id"])
        return bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"],
            selection_revision=1, operation_key="plan_check", parameters={}, config_revision="implicit-test")

    def cancel(self, batch, *, round_id=None):
        current = bulk.get_batch(batch["id"])
        command = bulk.request_control(batch["id"], request_key=uuid.uuid4().hex,
            action="cancel_not_started", expected_control_revision=current["control_revision"], round_id=round_id)
        for _ in range(5):
            command = bulk.settle_control(command["id"])
            bulk.project_pending()
            if command["state"] == "completed":
                return
        self.fail("合成无执行批次的取消未在有界结算内完成")

    def copy_cancelled(self, batch, round_id, *, reasons=None):
        scope = {"kind": "result_filter", "states": ["cancelled"]}
        if reasons:
            scope["reason_codes"] = reasons
        selection = bulk.create_selection(request_key=uuid.uuid4().hex,
            source={"kind": "batch_targets", "batch_id": batch["id"], "view": "round",
                    "round_id": round_id, "selection": scope},
            operation_key="plan_check", config_revision="implicit-test")
        return bulk.freeze_selection(selection["id"])

    def test_initial_round_cancelled_filter_includes_materialized_and_implicit_members(self):
        batch = self.batch()
        bulk.materialize_targets(batch["id"], limit=2)
        self.cancel(batch)
        self.assertEqual(bulk.get_round(batch["id"], batch["round_id"])["counts"]["cancelled"], 5)
        copied = self.copy_cancelled(batch, batch["round_id"])
        self.assertEqual(copied["target_count"], 5)
        # 隐式取消没有伪造执行错误；带原因筛选仍必须有对应证据。
        self.assertEqual(self.copy_cancelled(batch, batch["round_id"], reasons=["no_such_error"])["target_count"], 0)
        retry = bulk.create_round(batch["id"], request_key=uuid.uuid4().hex,
            source={"view": "round", "round_id": batch["round_id"]},
            selection={"kind": "result_filter", "states": ["cancelled"]})
        self.assertEqual(bulk.freeze_round(retry["id"])["target_count"], 5)
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS count FROM {common.table('operation_runs')}")
            self.assertEqual(cur.fetchone()["count"], 0)

    def test_retry_round_cancelled_filter_stays_with_its_two_implicit_members(self):
        batch = self.batch()
        self.cancel(batch)
        roots = bulk.list_targets(batch["id"])["items"]
        chosen = [item["id"] for item in roots[:2]]
        retry = bulk.create_round(batch["id"], request_key=uuid.uuid4().hex,
            source={"view": "current"}, selection={"kind": "targets", "target_ids": chosen})
        self.assertEqual(bulk.freeze_round(retry["id"])["target_count"], 2)
        self.cancel(batch, round_id=retry["id"])
        copied = self.copy_cancelled(batch, retry["id"])
        self.assertEqual(copied["target_count"], 2)
        copied_ids = {item["target_id"] for item in bulk.get_selection(copied["id"])["items"]}
        self.assertEqual(copied_ids, {item["account_id"] for item in roots[:2]})
        next_round = bulk.create_round(batch["id"], request_key=uuid.uuid4().hex,
            source={"view": "round", "round_id": retry["id"]},
            selection={"kind": "result_filter", "states": ["cancelled"]})
        self.assertEqual(bulk.freeze_round(next_round["id"])["target_count"], 2)
