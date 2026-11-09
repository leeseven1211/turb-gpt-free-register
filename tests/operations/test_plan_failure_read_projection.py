"""旧套餐任务从各自 Run 事件恢复列表错误，不写回历史和账号快照。"""
from unittest.mock import MagicMock, patch

from core import account_task_store
from core.storage import postgres
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class PlanFailureReadProjectionTests(PostgresTestCase):
    def setUp(self):
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.schema_patch.start()
        account_task_store.init()
        store.reset_ready()
        store.init()

    def tearDown(self):
        self.schema_patch.stop()

    def record(self, run_id, country, *, ok=False, status=None, error=None):
        store.append_runtime_event(
            run_id, stage="plan_check", event_type="promotion.query.recorded", message="套餐回执",
            detail={"country": country, "ok": ok, "http_status": status, "error": error},
        )

    def test_list_and_detail_recover_current_run_without_overwriting_history(self):
        task = store.create_runtime_task(task_type="plan_check", account_id=901,
                                         email="plan-projection@example.test", trigger="test")
        first_id = int(task["run"]["id"])
        self.record(first_id, "JP", status=401)
        store.finish_run(first_id, status="failed", error="全部国家查询失败：JP")
        second = store.retry_runtime_task(int(task["id"]))
        second_id = int(second["id"])
        self.record(second_id, "JP", status=401)
        self.record(second_id, "JP", ok=True, status=200)
        self.record(second_id, "VN", status=None, error="AT已过期/失效，请手动查活刷新")
        store.finish_run(second_id, status="partial_success", error="部分国家查询失败：VN")
        listed = store.list_tasks(task_type="plan_check", include_facets=False)["items"][0]
        current = listed["result_summary"]["country_failures"]
        self.assertEqual([("VN", "token_local_expired")], [(r["country"], r["code"]) for r in current])
        detail = store.get_task(int(task["id"]), include_events=False)
        self.assertEqual(current, detail["result_summary"]["country_failures"])
        self.assertEqual("token_http_401", detail["runs"][0]["result_summary"]["country_failures"][0]["code"])
        progress = store.get_run_progress(int(task["id"]), second_id)
        self.assertEqual(current, progress["failure"]["country_failures"])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT result_summary FROM {store._table('operation_runs')} WHERE id=%s", (second_id,))
            self.assertNotIn("country_failures", cur.fetchone()[0] or {})

    def test_multiple_tasks_restore_their_own_latest_failure(self):
        expected = {}
        for index, status in enumerate((401, 403)):
            task = store.create_runtime_task(task_type="plan_check", account_id=910 + index,
                                             email=f"plan-{index}@example.test", trigger="test")
            run_id = int(task["run"]["id"])
            self.record(run_id, "JP", status=status)
            store.finish_run(run_id, status="failed", error="全部国家查询失败：JP")
            expected[task["id"]] = status
        listed = store.list_tasks(task_type="plan_check", include_facets=False)["items"]
        self.assertEqual(expected, {row["id"]: row["result_summary"]["country_failures"][0]["http_status"] for row in listed})


def test_old_country_evidence_is_read_with_one_batch_query():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    items = [{"task_type": "plan_check", "status": "failed", "last_run_id": value} for value in (1, 2, 3)]
    store._attach_plan_failure_summaries(items, conn=connection)
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[1] == ([1, 2, 3],)
