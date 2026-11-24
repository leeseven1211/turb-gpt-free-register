"""账号工具栏提链只集合保存本地受理事实，不执行第三方提链。"""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

from psycopg import Cursor

from core.extract_link import service
from core.storage import records
from core.storage.operations import bulk_submission, store as operation
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountExtractBulkTests(PostgresTestCase):
    def setUp(self):
        operation.init()

    def account(self, number, **changes):
        return records.insert_row(records.ACCOUNTS, {
            "id": number, "email": f"account-{number}@example.test",
            "current_plan_type": "free", "plus_promo_kind": "free_trial",
            "access_token": "synthetic-private-at", **changes,
        })

    def boundaries(self):
        stack = ExitStack()
        stack.enter_context(patch("webui.routes.accounts._feature_unavailable", return_value=None))
        stack.enter_context(patch.object(service, "_provider_mode_enabled", return_value=True))
        stack.enter_context(patch.object(service, "get_config_snapshot", return_value={
            "revision": 19, "values": {"EXTRACT_LINK_TYPE": "pix",
                "EXTRACT_LINK_API_BASE": "https://synthetic.example.test",
                "UNRELATED_SECRET": "do-not-persist"},
        }))
        stack.enter_context(patch.object(service, "_cdk", return_value="synthetic-private-cdk"))
        stack.enter_context(patch.object(service, "_enabled_link_type_order", return_value=("paypal", "pix")))
        stack.enter_context(patch.object(service, "enqueue_account_extract",
                                        side_effect=AssertionError("禁止逐账号提交")))
        stack.enter_context(patch.object(service, "register_operation_handlers",
                                        side_effect=AssertionError("Web 不安装执行器")))
        return stack

    def post(self, ids, **parameters):
        client = create_app(auth_code="synthetic-auth").test_client()
        response = client.post("/api/accounts/extract-link-bulk",
            json={"account_ids": ids, **parameters}, headers={"X-Auth-Code": "synthetic-auth"})
        self.assertEqual(202, response.status_code)
        return response.get_json()

    def tasks(self):
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task.*, run.data AS run_data FROM {operation._table('operation_tasks')} task "
                        f"JOIN {operation._table('operation_runs')} run ON run.id=task.last_run_id "
                        "WHERE task.task_type='extract_link' ORDER BY task.account_id")
            return [dict(row) for row in cur.fetchall()]

    def test_toolbar_saves_one_collection_with_original_legacy_parameters(self):
        self.account(7, archived=True, extract_link_failed_types=["pix"])
        self.account(8)
        with self.boundaries(), patch("core.operations.task_gateway.notify_dispatch") as notify:
            body = self.post([7, 8, 7], link_type="pix", cdk="must-not-persist",
                paypal_region_selected="3", paypal_country="US", paypal_currency="USD",
                paypal_region="NA", unexpected="not-a-payment-option")
        self.assertEqual(2, body["started_count"])
        self.assertEqual([], body["failed"])
        self.assertEqual(["paypal", "pix"], [item["link_type"] for item in body["started"]])
        self.assertEqual("pix", body["started"][0]["fallback_from"])
        notify.assert_called_once()
        tasks = self.tasks()
        self.assertEqual(2, len(tasks))
        for task in tasks:
            self.assertEqual("native_operations", task["source_system"])
            self.assertEqual("manual_bulk", task["trigger"])
            self.assertEqual(int(body["batch_id"]), task["batch_id"])
            self.assertNotIn("provider_id", task["run_data"], "账号入口继续使用原默认 legacy 执行")
            self.assertNotIn("workbench_action", task["run_data"])
            self.assertEqual({"paypal_region_selected": 3, "paypal_country": "US",
                              "paypal_currency": "USD", "paypal_region": "NA"},
                             task["run_data"]["payment_options"])
            self.assertEqual(19, task["run_data"]["config_snapshot"]["config_snapshot_revision"])
            self.assertNotIn("UNRELATED_SECRET", repr(task))
            self.assertNotIn("must-not-persist", repr(task))
            self.assertNotIn("synthetic-private-at", repr(task))
        self.assertEqual("manual_bulk", records.get_row(records.ACCOUNTS, 7)["extract_link_trigger"])

    def test_qualification_busy_and_invalid_receipts_preserve_each_target(self):
        self.account(7)
        self.account(8, current_plan_type="plus")
        self.account(9, plus_promo_kind="discount")
        self.account(10, access_token="")
        self.account(11, account_status="deactivated")
        self.account(12)
        self.account(13, extract_link_status="queued", extract_link_queued_at="2999-01-01T00:00:00")
        operation.create_runtime_task(task_type="plan_check", account_id=12, email="account-12@example.test")
        with self.boundaries(), patch("core.operations.task_gateway.notify_dispatch"):
            body = self.post([7, 8, 9, 10, 11, 12, 13, 99, "bad", 7])
        self.assertEqual([7], [int(item["id"]) for item in body["started"]])
        self.assertEqual({8, 9, 10, 11, 99, "bad"}, {
            int(item["id"]) if str(item["id"]).isdigit() else item["id"] for item in body["skipped"]})
        self.assertEqual({12, 13}, {int(item["id"]) for item in body["busy"]})
        self.assertEqual(0, body["failed_count"])

    def test_sql_budget_and_transactions_do_not_grow_per_account(self):
        for number in range(1, 23):
            self.account(number)
        execute = Cursor.execute
        queries = []

        def capture(cur, statement, *args, **kwargs):
            queries.append(str(statement))
            return execute(cur, statement, *args, **kwargs)

        with self.boundaries(), patch("core.operations.task_gateway.notify_dispatch"), \
                patch.object(Cursor, "execute", capture):
            one = self.post([22], link_type="pix")
            first = len(queries)
            queries.clear()
            many = self.post(list(range(1, 21)), link_type="pix")
        self.assertEqual(1, one["started_count"])
        self.assertEqual(20, many["started_count"])
        self.assertEqual(first, len(queries))
        self.assertLessEqual(len(queries), 16)
        inserts = [q for q in queries if q.lstrip().startswith("INSERT INTO")
                   and 'operation_tasks"' in q]
        self.assertEqual(1, len(inserts))

    def test_failed_collection_rolls_back_claim_and_tasks(self):
        self.account(7)
        self.account(8)
        with self.boundaries(), patch.object(bulk_submission, "create_specs",
                side_effect=RuntimeError("synthetic-secret-not-for-browser")), \
                patch("core.operations.task_gateway.notify_dispatch") as notify:
            body = self.post([7, 8], link_type="pix")
        self.assertEqual(2, body["failed_count"])
        self.assertEqual(0, body["started_count"])
        self.assertNotIn("synthetic-secret-not-for-browser", repr(body))
        self.assertEqual([], self.tasks())
        self.assertIsNone(records.get_row(records.ACCOUNTS, 7)["extract_link_status"])
        notify.assert_not_called()

    def test_failed_collection_keeps_preexisting_busy_and_skipped_classifications(self):
        self.account(7)
        self.account(8)
        self.account(9, current_plan_type="plus")
        operation.create_runtime_task(task_type="plan_check", account_id=8, email="account-8@example.test")
        with self.boundaries(), patch.object(bulk_submission, "create_specs",
                side_effect=RuntimeError("synthetic")), patch("core.operations.task_gateway.notify_dispatch"):
            body = self.post([7, 8, 9], link_type="pix")
        self.assertEqual([7], [int(item["id"]) for item in body["failed"]])
        self.assertEqual([8], [int(item["id"]) for item in body["busy"]])
        self.assertEqual([9], [int(item["id"]) for item in body["skipped"]])

    def test_initial_database_failure_reports_all_valid_targets_without_false_success(self):
        from core.storage.extract_link import account_submission
        with self.boundaries(), patch.object(account_submission, "read_accounts",
                side_effect=RuntimeError("synthetic")), patch("core.operations.task_gateway.notify_dispatch"):
            body = self.post([7, 8], link_type="pix")
        self.assertEqual(0, body["started_count"])
        self.assertEqual({7, 8}, {int(item["id"]) for item in body["failed"]})

    def test_bigint_ids_and_native_task_references_remain_exact(self):
        number = 9007199254740993
        self.account(number)
        with operation._connect() as conn, conn.cursor() as cur:
            for table in ("operation_tasks", "operation_runs", "operation_batches"):
                cur.execute("SELECT setval(pg_get_serial_sequence(%s,'id'),%s,false)",
                            (operation._table(table), number))
        with self.boundaries(), patch("core.operations.task_gateway.notify_dispatch"):
            body = self.post([str(number)], link_type="pix")
        self.assertEqual(str(number), body["batch_id"])
        self.assertEqual(str(number), body["started"][0]["id"])
        self.assertEqual(str(number), body["started"][0]["task_id"])
        self.assertEqual(str(number), body["started"][0]["run_id"])
