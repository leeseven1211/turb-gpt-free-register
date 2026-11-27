"""使用模拟店铺和来源验证销售领域行为。"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from cryptography.fernet import Fernet

from core.operations import task_gateway
from core.sales import runtime, service, store
from core.sales.errors import SalesError
from core.storage.operations import common, legacy_task_store, store as operations
from tests.support_pg import PostgresTestCase
from tests.support_settlement import install_native_settlement_fixture


PRODUCT = {
    "external_product_id": "101", "goods_key": "fixture-goods",
    "name": "测试商品", "status": "active", "price": "20.00",
}


def make_account(account_id, email, *, archived=False, complete=True):
    return {
        "id": account_id, "email": email, "plan": "plus", "archived": archived,
        "delivery_line": email + "----fixture-password----" + ("FIXTURE2FA" if complete else ""),
    }


class FakeSource:
    def __init__(self, *accounts):
        self.rows = {account["id"]: account for account in accounts}
        self.archive_failure = False
        self.search_failure = False
        self.archive_calls = []

    def accounts(self, account_ids):
        return [dict(self.rows[i]) for i in account_ids if i in self.rows]

    def find_accounts(self, emails):
        if self.search_failure:
            raise SalesError("source_timeout", "来源接口超时", 504)
        return [dict(row) for row in self.rows.values() if row["email"].casefold() in emails]

    def archive(self, account_id):
        self.archive_calls.append(account_id)
        if self.archive_failure:
            raise SalesError("source_timeout", "来源接口超时", 504)
        self.rows[account_id]["archived"] = True
        return True


class FakeShop:
    def __init__(self):
        self.merchant = "fixture-merchant"
        self.product = dict(PRODUCT)
        self.stock = []
        self.sales = []
        self.writes = []
        self.result_mode = "ok"

    def check(self):
        return {"external_shop_id": self.merchant, "capabilities": {"inventory": True}}

    def products(self):
        return [dict(self.product)]

    def inventory(self, external_product_id):
        if external_product_id != self.product["external_product_id"]:
            raise SalesError("shop_product_not_found", "商品不存在", 404)
        return [dict(row) for row in self.stock]

    def import_inventory(self, external_product_id, lines):
        self.writes.append((external_product_id, list(lines)))
        for line in lines[:1] if self.result_mode == "partial" else lines:
            self.add_stock(line)
        if self.result_mode == "lost":
            raise SalesError("shop_timeout", "店铺请求超时", 504)
        return {"duplicate_only": self.result_mode == "duplicate"}

    def add_stock(self, line, *, sold=False):
        self.stock.append({
            "external_inventory_id": str(len(self.stock) + 201), "content": line,
            "status": "sold" if sold else "available",
        })

    def orders(self):
        return [dict(row) for row in self.sales]


def order(*cards, status="paid", goods_key="fixture-goods"):
    return {
        "order_ref": "fixture-order", "goods_key": goods_key, "status": status,
        "quantity": len(cards) or 1, "sendout": len(cards), "cards": list(cards),
        "amount": "20.00", "fee": "0.12", "fee_payer": "buyer",
        "paid_at": "2026-11-27T08:00:00+00:00",
    }


class SalesServiceTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        operations.reset_ready()
        operations.init()
        store.reset_ready()
        store.init()
        store.save_source({"id": "oracle", "name": "远端", "kind": "remote",
                           "base_url": "https://oracle.example.test", "auth_env": "TEST_ORACLE_AUTH"})
        self.shop = store.save_shop({"name": "测试店铺", "enabled": True,
                                     "external_shop_id": "fixture-merchant"})
        self.product = store.replace_products(self.shop["id"], [PRODUCT])[0]
        self.remote = FakeSource(make_account(17, "remote@example.test"))
        self.local = FakeSource(make_account(17, "local@example.test"))
        self.merchant = FakeShop()
        self._patch(service, "shop_adapter", lambda _shop: self.merchant)
        self._patch(service, "account_source", lambda source: {"local": self.local, "oracle": self.remote}[source["id"]])
        self._patch(service, "executor_id", lambda: "local")
        patcher = patch.dict("os.environ", {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch(self, obj, name, value):
        patcher = patch.object(obj, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _add(self, source, *account_ids):
        return [row["id"] for row in service.add_accounts(source, list(account_ids))["items"]]

    def _submit(self, *ids, request_key=None):
        return service.submit_listing(self.shop["id"], self.product["id"], list(ids), request_key or str(uuid4()))

    def _execute(self, *ids):
        return service.execute_listing(self.shop["id"], self.product["id"], list(ids))

    def _prune_task_history(self, task_id):
        future = common._now() + timedelta(days=8)
        with patch.object(common, "_now", return_value=future):
            cleanup = operations.cleanup_terminal_history(retention_days=7, archive=lambda _snapshot: None)
        self.assertEqual(1, cleanup["deleted_tasks"])
        self.assertIsNone(operations.get_task(task_id, include_events=False))

    def test_same_request_returns_same_task_and_changed_intent_conflicts(self):
        local, = self._add("local", 17)
        remote, = self._add("oracle", 17)
        key = str(uuid4())

        first = self._submit(local, request_key=key)
        same = self._submit(local, request_key=key)
        with self.assertRaises(SalesError) as conflict:
            self._submit(remote, request_key=key)

        self.assertEqual(first["task_id"], same["task_id"])
        self.assertEqual("sales_request_conflict", conflict.exception.code)
        saved = operations.get_task(first["task_id"], include_events=False)
        self.assertIsNone(saved["account_id"])
        self.assertEqual("", saved["email_snapshot"])
        self.assertNotIn("fixture-password", repr(saved))
        self.assertIsNone(store.get_item(remote)["shop_id"])
        self.assertEqual([], self.merchant.writes)

    def test_submission_failure_rolls_back_frozen_material(self):
        remote, = self._add("oracle", 17)
        with patch.object(task_gateway, "submit_durable_operation", return_value={"accepted": False}):
            with self.assertRaises(SalesError):
                self._submit(remote)
        self.assertFalse(store.get_item(remote, private=True)["fingerprint"])
        self.assertEqual([], store.list_listing_pending())

    def test_lost_receipt_is_confirmed_by_readback_and_archives_its_source_only(self):
        local, = self._add("local", 17)
        remote, = self._add("oracle", 17)
        self._submit(remote)
        self.merchant.result_mode = "lost"

        self.assertEqual(1, self._execute(remote)["listed_count"])
        self.assertEqual(1, self._execute(remote)["listed_count"])
        self.assertEqual(1, len(self.merchant.writes))
        self.assertTrue(store.get_item(remote)["archived"])
        self.assertFalse(store.get_item(local)["archived"])
        self.assertEqual([17], self.remote.archive_calls)
        self.assertEqual([], self.local.archive_calls)

    def test_duplicate_response_confirms_only_readback_and_resumes_missing_intent(self):
        self.remote.rows[18] = make_account(18, "second@example.test")
        first, second = self._add("oracle", 17, 18)
        self._submit(first, second)
        self.merchant.result_mode = "partial"

        result = self._execute(first, second)
        self.assertEqual(1, result["listed_count"])
        self.assertEqual("listing_inventory_unconfirmed", result["items"][1]["error_code"])
        self.assertTrue(store.get_item(first)["archived"])
        self.assertFalse(store.get_item(second)["archived"])

        self.remote.rows[18]["delivery_line"] = make_account(18, "changed@example.test")["delivery_line"]
        self.merchant.result_mode = "duplicate"
        self.assertEqual(1, self._execute(second)["listed_count"])
        self.assertEqual([("101", [make_account(18, "second@example.test")["delivery_line"]])],
                         self.merchant.writes[1:])

    def test_incomplete_material_has_a_per_item_error_and_submit_keeps_other_account(self):
        self.remote.rows[18] = make_account(18, "missing@example.test", complete=False)
        good, incomplete = self._add("oracle", 17, 18)

        submitted = self._submit(good, incomplete)
        self.assertEqual("listing_material_incomplete", submitted["items"][1]["error_code"])
        self.assertFalse(store.get_item(incomplete, private=True)["fingerprint"])
        self.assertEqual(1, self._execute(good)["listed_count"])

    def test_history_uses_all_sources_then_requires_exact_material_with_unique_match(self):
        self.merchant.add_stock(self.remote.rows[17]["delivery_line"])
        self.local.rows[18] = dict(self.remote.rows[17], id=18)
        duplicate = service.execute_sync(self.shop["id"])
        self.assertEqual("source_match_ambiguous", duplicate["items"][0]["error_code"])
        self.assertEqual(0, store.list_items()["total"])

        self.local.rows[18]["delivery_line"] = "remote@example.test----different----FIXTURE2FA"
        self.local.search_failure = True
        unavailable = service.execute_sync(self.shop["id"])
        self.assertEqual("source_match_unavailable", unavailable["items"][0]["error_code"])
        self.assertEqual(0, store.list_items()["total"])

        self.local.search_failure = False
        self.assertEqual(1, service.execute_sync(self.shop["id"])["listed_count"])
        matched = store.list_items()["items"][0]
        self.assertEqual("oracle", matched["source_id"])
        self.assertFalse(matched["archive_pending"])
        self.assertEqual([], self.remote.archive_calls)

    def test_failed_source_constructor_leaves_unmatched_row_and_keeps_existing_mapping(self):
        self.merchant.add_stock(self.remote.rows[17]["delivery_line"])
        service.execute_sync(self.shop["id"])
        known, = store.list_items()["items"]
        self.local.rows[18] = make_account(18, "other@example.test")
        self.merchant.add_stock(self.local.rows[18]["delivery_line"])
        self.merchant.stock[0]["status"] = "sold"

        def source_factory(source):
            if source["id"] == "oracle":
                raise SalesError("source_auth_missing", "来源未配置授权码", 503)
            return self.local

        self._patch(service, "account_source", source_factory)
        summary = service.execute_sync(self.shop["id"])

        self.assertEqual("source_match_unavailable", summary["error_code"])
        self.assertEqual("sold", store.get_item(known["id"])["status"])
        self.assertEqual(1, store.list_items()["total"])

    def test_history_attaches_manual_sale_without_changing_its_status_or_archive_obligation(self):
        remote, = self._add("oracle", 17)
        marked = service.change_status({"item_ids": [remote], "status": "sold"})
        self.assertEqual("sold", marked["items"][0]["status"])
        self.assertTrue(store.get_item(remote)["archive_pending"])
        self.merchant.add_stock(self.remote.rows[17]["delivery_line"])

        result = service.execute_sync(self.shop["id"])

        self.assertEqual(1, result["sold_count"])
        self.assertEqual(1, store.list_items()["total"])
        item = store.get_item(remote)
        self.assertEqual("sold", item["status"])
        self.assertEqual("201", item["external_inventory_id"])
        self.assertEqual(self.product["id"], item["product_id"])
        self.assertTrue(item["archive_pending"])
        self.assertEqual([], self.merchant.writes)

    def test_order_requires_the_product_key_and_delivered_material_and_retains_sale_after_refund(self):
        line = self.remote.rows[17]["delivery_line"]
        self.merchant.add_stock(line)
        for invalid in (order(), order(line, goods_key="wrong-goods")):
            self.merchant.sales[:] = [invalid]
            service.execute_sync(self.shop["id"])
            self.assertEqual("listed", store.list_items()["items"][0]["status"])

        self.merchant.sales[:] = [order(line)]
        service.execute_sync(self.shop["id"])
        sold = store.list_items()["items"][0]
        self.assertEqual("sold", sold["status"])
        self.assertEqual("fixture-order", sold["order_ref"])
        self.assertIsNotNone(sold["paid_at"])
        self.assertFalse(sold["archive_pending"])

        self.merchant.sales[:] = [order(status="refunded")]
        service.execute_sync(self.shop["id"])
        refunded = store.get_item(sold["id"])
        self.assertEqual("sold", refunded["status"])
        self.assertEqual("refunded", refunded["order_status"])

    def test_only_delivered_order_without_inventory_prevents_duplicate_import(self):
        remote, = self._add("oracle", 17)
        self._submit(remote)
        self.merchant.sales[:] = [order(self.remote.rows[17]["delivery_line"])]

        self.assertEqual(1, self._execute(remote)["sold_count"])
        self.assertEqual([], self.merchant.writes)
        self.assertEqual("fixture-order", store.get_item(remote)["order_ref"])

    def test_sync_counts_one_order_for_multiple_delivered_accounts_and_duplicate_rows(self):
        self.remote.rows[18] = make_account(18, "second@example.test")
        receipt = order(self.remote.rows[17]["delivery_line"], self.remote.rows[18]["delivery_line"])
        self.merchant.sales[:] = [receipt, dict(receipt)]

        result = service.execute_sync(self.shop["id"])

        self.assertEqual(1, result["order_count"])
        self.assertEqual(2, result["sold_count"])
        self.assertEqual({"fixture-order"}, {row["order_ref"] for row in store.list_items()["items"]})

    def test_archive_retry_short_circuits_when_source_already_archived(self):
        remote, = self._add("oracle", 17)
        self._submit(remote)
        self.remote.archive_failure = True
        self._execute(remote)
        self.assertEqual("listed", store.get_item(remote)["status"])
        self.assertTrue(store.get_item(remote)["archive_pending"])

        self.remote.rows[17]["archived"] = True
        service.process_archives()
        self.assertFalse(store.get_item(remote)["archive_pending"])
        self.assertTrue(store.get_item(remote)["archived"])
        self.assertEqual([17], self.remote.archive_calls)

    def test_terminal_listing_with_pending_material_is_enqueued_again_only_once(self):
        remote, = self._add("oracle", 17)
        receipt = self._submit(remote)
        self.assertEqual(0, runtime.enqueue_recoveries())
        operations.request_run_cancel(receipt["run_id"], reason="模拟进程中断")

        self.assertEqual(1, runtime.enqueue_recoveries())
        self.assertEqual(0, runtime.enqueue_recoveries())
        restored, original = service.list_jobs()
        self.assertNotEqual(original["run_id"], restored["run_id"])
        self.assertEqual("queued", restored["status"])
        self.assertEqual(original["product_id"], restored["product_id"])

    def test_listing_recovery_after_task_retention_keeps_the_frozen_product_key(self):
        self.remote.rows[18] = make_account(18, "second@example.test")
        first, second = self._add("oracle", 17, 18)
        accepted = self._submit(first, second)
        operations.request_run_cancel(accepted["run_id"], reason="模拟进程中断")
        self._prune_task_history(accepted["task_id"])
        self.assertEqual(1, runtime.enqueue_recoveries())
        self.assertEqual(1, self._execute(first)["listed_count"])

        self.merchant.product["goods_key"] = "changed-product-key"
        service.check_shop(self.shop["id"])
        result = self._execute(second)

        self.assertEqual("listing_target_changed", result["items"][0]["error_code"])
        self.assertEqual("pending", store.get_item(second)["sync_status"])
        self.assertEqual(1, len(self.merchant.writes))

    def test_user_cancel_pauses_recovery_and_manual_retry_reopens_original_intent(self):
        runtime.register_actions()
        self.addCleanup(task_gateway.unregister_operation_handler, "sales_sync")
        remote, = self._add("oracle", 17)
        accepted = self._submit(remote)
        task = operations.get_task(accepted["task_id"], include_events=False)
        cancel = task_gateway.operation_action("sales_sync", "cancel", source_system="native_operations")
        retry = task_gateway.operation_action("sales_sync", "retry", source_system="native_operations")

        self.assertTrue(cancel(task)["ok"])
        self.assertEqual("paused", store.get_item(remote)["sync_status"])
        self.assertEqual(0, runtime.enqueue_recoveries())
        self.assertEqual([], self.merchant.writes)
        status = service.change_status({"item_ids": [remote], "status": "for_sale"})
        self.assertEqual("listing_intent_active", status["items"][0]["error_code"])
        cancelled = operations.get_task(accepted["task_id"], include_events=False)
        retried = retry(cancelled)
        self.assertTrue(retried["accepted"])
        self.assertNotEqual(accepted["run_id"], retried["run_id"])
        self.assertEqual("pending", store.get_item(remote)["sync_status"])
        self.assertEqual(1, self._execute(remote)["listed_count"])

    def test_sync_confirms_stock_from_a_paused_listing_even_after_task_retention(self):
        runtime.register_actions()
        self.addCleanup(task_gateway.unregister_operation_handler, "sales_sync")
        remote, = self._add("oracle", 17)
        accepted = self._submit(remote)
        task = operations.get_task(accepted["task_id"], include_events=False)
        cancel = task_gateway.operation_action("sales_sync", "cancel", source_system="native_operations")
        self.assertTrue(cancel(task)["ok"])
        self._prune_task_history(accepted["task_id"])
        self.merchant.add_stock(self.remote.rows[17]["delivery_line"])

        self.assertEqual(1, service.execute_sync(self.shop["id"])["listed_count"])
        item = store.get_item(remote)
        self.assertEqual("listed", item["status"])
        self.assertTrue(item["archive_pending"])
        self.assertEqual([], self.merchant.writes)
        self.assertEqual([], self.remote.archive_calls)
        self.assertEqual(1, runtime.enqueue_recoveries())

    def test_shared_worker_runs_listing_and_persists_public_result(self):
        fixture = install_native_settlement_fixture(self)
        self.addCleanup(fixture.close)
        runtime.register_handler()
        self.addCleanup(task_gateway.unregister_operation_handler, "sales_sync")
        remote, = self._add("oracle", 17)
        accepted = self._submit(remote)

        task_gateway._execute_operation_handler("sales_sync", accepted["run_id"])
        fixture.wait_for_run_released(accepted["run_id"])

        job, = service.list_jobs()
        self.assertEqual("success", job["status"])
        self.assertEqual("listed", job["result_summary"]["items"][0]["status"])
        self.assertEqual(1, job["result_summary"]["archived_count"])
        self.assertTrue(store.get_item(remote)["archived"])

        self.remote.rows[18] = make_account(18, "second@example.test")
        second, = self._add("oracle", 18)
        self.remote.archive_failure = True
        accepted = self._submit(second)
        task_gateway._execute_operation_handler("sales_sync", accepted["run_id"])
        fixture.wait_for_run_released(accepted["run_id"])

        job = next(row for row in service.list_jobs() if row["run_id"] == accepted["run_id"])
        self.assertEqual("partial_success", job["status"])
        self.assertEqual("listed", job["result_summary"]["items"][0]["status"])
        self.assertEqual("source_timeout", job["result_summary"]["items"][0]["archive_error_code"])
        self.assertTrue(store.get_item(second)["archive_pending"])

    def test_periodic_sync_skips_a_shop_that_changed_owner_after_scan(self):
        scanned = store.list_shops()
        service.save_shop({"id": self.shop["id"], "owner_id": "oracle"})

        with patch.object(store, "list_shops", return_value=scanned):
            runtime._enqueue_periodic_syncs({})

        self.assertEqual([], service.list_jobs())

    def test_merchant_change_after_submission_keeps_listing_intent_pending(self):
        remote, = self._add("oracle", 17)
        self._submit(remote)
        self.merchant.merchant = "other-merchant"
        with self.assertRaises(SalesError) as mismatch:
            self._execute(remote)

        self.assertEqual("shop_identity_mismatch", mismatch.exception.code)
        self.assertEqual([], self.merchant.writes)
        self.assertEqual("pending", store.get_item(remote)["sync_status"])

    def test_other_executor_cannot_submit_or_execute_shop_operations(self):
        self._patch(service, "executor_id", lambda: "oracle")
        remote, = self._add("oracle", 17)
        for action in (lambda: self._submit(remote),
                       lambda: service.submit_sync(self.shop["id"]),
                       lambda: service.execute_sync(self.shop["id"]),
                       lambda: self._execute(remote)):
            with self.assertRaises(SalesError) as forbidden:
                action()
            self.assertEqual("shop_executor_mismatch", forbidden.exception.code)
        self.assertEqual([], self.merchant.writes)
