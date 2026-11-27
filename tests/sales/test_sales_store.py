# -*- coding: utf-8 -*-
"""销售 PostgreSQL 仓储的隔离测试。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from tests.support_pg import PostgresTestCase

from core.sales import store
try:
    from core.sales.errors import SalesError
except ModuleNotFoundError:
    from core.sales.store import SalesError


class SalesStoreTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        store.reset_ready()
        store.init()

    def setUp(self) -> None:
        super().setUp()
        store.reset_ready()
        store.init()
        store.save_source({"id": "oracle", "name": "Oracle", "kind": "remote"})

    def test_source_account_identity_allows_same_account_id_across_sources_and_is_idempotent(self):
        first = store.add_item(source_id="local", account_id=7, email="local@example.test")
        other = store.add_item(source_id="oracle", account_id=7, email="remote@example.test")

        self.assertNotEqual(first["id"], other["id"])
        same = store.add_item(source_id="local", account_id=7, email="local@example.test")
        self.assertEqual(first["id"], same["id"])
        self.assertEqual(2, store.list_items()["total"])

    def test_private_material_is_not_in_public_projection(self):
        item = store.add_item(
            source_id="local",
            account_id=8,
            email="private@example.test",
        )
        shop = store.save_shop({"name": "私有材料店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "private-goods", "name": "私有商品"}],
        )[0]
        store.freeze_listing(
            item["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            fingerprint="fingerprint-a",
            delivery_ciphertext="ciphertext-a",
        )

        public = store.get_item(item["id"])
        private = store.get_item(item["id"], private=True)
        self.assertNotIn("fingerprint", public)
        self.assertNotIn("delivery_ciphertext", public)
        self.assertEqual("fingerprint-a", private["fingerprint"])
        self.assertEqual("ciphertext-a", private["delivery_ciphertext"])

    def test_fingerprint_is_globally_unique_even_for_different_shops(self):
        first = store.add_item(source_id="local", account_id=9, email="a@example.test")
        second = store.add_item(source_id="oracle", account_id=9, email="b@example.test")
        shop = store.save_shop({"name": "冲突测试店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "conflict-goods", "name": "冲突商品"}],
        )[0]
        store.freeze_listing(
            first["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            fingerprint="same-material",
            delivery_ciphertext="ciphertext-a",
        )

        with self.assertRaises(SalesError) as raised:
            store.freeze_listing(
                second["id"],
                shop_id=shop["id"],
                product_id=product["id"],
                fingerprint="same-material",
                delivery_ciphertext="ciphertext-b",
            )
        self.assertEqual("listing_fingerprint_conflict", raised.exception.code)

    def test_shop_product_snapshot_and_external_inventory_are_scoped_to_shop(self):
        shop = store.save_shop({"name": "小铺", "external_shop_id": "merchant-1"})
        products = store.replace_products(
            shop["id"],
            [
                {
                    "external_product_id": "goods-1",
                    "goods_key": "key-1",
                    "name": "商品一",
                    "status": "active",
                    "price": 20,
                },
                {
                    "external_product_id": "goods-2",
                    "goods_key": "key-2",
                    "name": "商品二",
                    "price": Decimal("30.50"),
                },
            ],
        )
        self.assertEqual(2, len(products))
        self.assertEqual(2, len(store.list_products(shop["id"])))
        replacement = store.replace_products(
            shop["id"],
            [{"external_product_id": "goods-1", "goods_key": "key-1", "name": "商品一改名"}],
        )
        self.assertEqual(2, len(replacement))
        statuses = {row["external_product_id"]: row["status"] for row in store.list_products(shop["id"])}
        self.assertEqual("unavailable", statuses["goods-2"])

        item = store.add_item(source_id="local", account_id=10, email="inventory@example.test")
        store.freeze_listing(
            item["id"],
            shop_id=shop["id"],
            product_id=products[0]["id"],
            fingerprint="inventory-material",
            delivery_ciphertext="ciphertext",
        )
        confirmed = store.confirm_inventory(
            item["id"],
            shop_id=shop["id"],
            product_id=products[0]["id"],
            external_inventory_id="inventory-1",
        )
        self.assertEqual("listed", confirmed["status"])
        self.assertEqual("inventory-1", confirmed["external_inventory_id"])

    def test_freeze_sets_pending_and_confirm_archive_intent_is_atomic(self):
        shop = store.save_shop({"name": "小铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "goods-1", "goods_key": "key-1", "name": "商品一"}],
        )[0]
        item = store.add_item(source_id="local", account_id=11, email="pending@example.test")
        frozen = store.freeze_listing(
            item["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            fingerprint="pending-material",
            delivery_ciphertext="ciphertext",
        )
        self.assertEqual("pending", frozen["sync_status"])
        self.assertEqual([], store.list_archive_pending())
        listed = store.confirm_inventory(
            item["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            external_inventory_id="inventory-pending",
        )
        self.assertTrue(listed["archive_pending"])
        pending = store.list_archive_pending()
        self.assertEqual([item["id"]], [row["id"] for row in pending])
        self.assertEqual(shop["id"], pending[0]["shop_id"])
        self.assertEqual("local", pending[0]["source_id"])

    def test_confirm_sold_cannot_be_downgraded_by_old_snapshot(self):
        shop = store.save_shop({"name": "小铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "goods-1", "goods_key": "key-1", "name": "商品一"}],
        )[0]
        item = store.add_item(source_id="local", account_id=12, email="sold@example.test")
        store.freeze_listing(
            item["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            fingerprint="sold-material",
            delivery_ciphertext="ciphertext",
        )
        sold = store.confirm_inventory(
            item["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            external_inventory_id="inventory-sold",
            sold=True,
            order_ref="order-1",
            order_amount=20,
            paid_at="2026-11-27T10:00:00+00:00",
        )
        self.assertEqual("sold", sold["status"])
        old_snapshot = store.confirm_inventory(
            item["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            external_inventory_id="inventory-sold",
            sold=False,
        )
        self.assertEqual("sold", old_snapshot["status"])

    def test_two_sources_with_same_account_id_can_be_created_concurrently(self):
        def add(source_id: str):
            return store.add_item(
                source_id=source_id,
                account_id=99,
                email=f"{source_id}@example.test",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(add, ("local", "oracle")))
        self.assertEqual(2, len({row["id"] for row in results}))
        self.assertEqual(
            {"local", "oracle"},
            {row["source_id"] for row in store.get_items([row["id"] for row in results])},
        )

    def test_pending_queries_are_owner_scoped_and_inventory_lookup_is_private(self):
        shop = store.save_shop({"name": "恢复店铺", "owner_id": "oracle"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "recover-goods", "name": "恢复商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=100, email="recover@example.test")
        store.freeze_listing(
            item["id"],
            shop_id=shop["id"],
            product_id=product["id"],
            fingerprint="recover-material",
            delivery_ciphertext="recover-ciphertext",
        )
        self.assertEqual([], store.list_listing_pending(owner_id="local"))
        pending = store.list_listing_pending(owner_id="oracle")
        self.assertEqual([item["id"]], [row["id"] for row in pending])
        found = store.find_inventory_items(
            shop["id"],
            fingerprints=["recover-material"],
        )
        self.assertEqual("recover-ciphertext", found[0]["delivery_ciphertext"])
        self.assertEqual("recover-material", found[0]["fingerprint"])

    def test_status_counts_follow_non_status_filters(self):
        first = store.add_item(source_id="local", account_id=101, email="one@example.test")
        second = store.add_item(source_id="local", account_id=102, email="two@example.test")
        store.patch_item(first["id"], {"status": "listed"})
        result = store.list_items(source_id="local", status="listed")
        self.assertEqual(1, result["total"])
        self.assertEqual({"all": 2, "for_sale": 1, "listed": 1, "sold": 0}, result["counts"])

    def test_freeze_retry_preserves_original_target_and_delivery_material(self):
        shop = store.save_shop({"name": "重试店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "retry-goods", "name": "重试商品"}],
        )[0]
        other_shop = store.save_shop({"name": "另一店铺"})
        other_product = store.replace_products(
            other_shop["id"],
            [{"external_product_id": "other-goods", "name": "另一商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=103, email="retry@example.test")
        store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="retry-original", delivery_ciphertext="cipher-original",
        )
        retried = store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="retry-original", delivery_ciphertext="cipher-new",
        )
        private = store.get_item(item["id"], private=True)
        self.assertEqual("retry-original", private["fingerprint"])
        self.assertEqual("cipher-original", private["delivery_ciphertext"])
        self.assertEqual("pending", retried["sync_status"])
        with self.assertRaises(SalesError) as raised:
            store.freeze_listing(
                item["id"], shop_id=other_shop["id"], product_id=other_product["id"],
                fingerprint="retry-original", delivery_ciphertext="cipher-original",
            )
        self.assertEqual("listing_target_immutable", raised.exception.code)

    def test_confirm_retry_preserves_external_and_order_facts(self):
        shop = store.save_shop({"name": "回读店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "readback-goods", "name": "回读商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=104, email="readback@example.test")
        store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="readback-material", delivery_ciphertext="ciphertext",
        )
        first = store.confirm_inventory(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            external_inventory_id="inventory-readback", sold=True,
            order_ref="order-readback", order_amount=25, paid_at="2026-11-27T10:00:00+00:00",
        )
        second = store.confirm_inventory(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            external_inventory_id="", sold=False,
        )
        self.assertEqual("sold", second["status"])
        self.assertEqual(first["external_inventory_id"], second["external_inventory_id"])
        self.assertEqual("order-readback", second["order_ref"])
        self.assertEqual(25.0, second["order_amount"])
        self.assertEqual(first["paid_at"], second["paid_at"])
        searched = store.list_items(q="order-readback", status="sold")
        self.assertEqual([item["id"]], [row["id"] for row in searched["items"]])
        self.assertEqual({"all": 1, "for_sale": 0, "listed": 0, "sold": 1}, searched["counts"])
        with self.assertRaises(SalesError) as raised:
            store.confirm_inventory(
                item["id"], shop_id=shop["id"], product_id=product["id"],
                external_inventory_id="different-inventory", sold=False,
            )
        self.assertEqual("external_inventory_conflict", raised.exception.code)

    def test_duplicate_add_does_not_replace_frozen_account_snapshot(self):
        shop = store.save_shop({"name": "快照店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "snapshot-goods", "name": "快照商品"}],
        )[0]
        item = store.add_item(
            source_id="local", account_id=105, email="old@example.test",
            plan="old-plan", note="old-note",
        )
        store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="snapshot-material", delivery_ciphertext="ciphertext",
        )
        repeated = store.add_item(
            source_id="local", account_id=105, email="new@example.test",
            plan="new-plan", note="new-note",
        )
        self.assertEqual(item["id"], repeated["id"])
        self.assertEqual("old@example.test", repeated["email"])
        self.assertEqual("old-plan", repeated["plan"])
        self.assertEqual("old-note", repeated["note"])

    def test_patch_cannot_reassign_frozen_target_or_external_inventory(self):
        shop = store.save_shop({"name": "保护店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "protected-goods", "name": "保护商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=106, email="protected@example.test")
        store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="protected-material", delivery_ciphertext="ciphertext",
        )
        with self.assertRaises(SalesError) as raised:
            store.patch_item(item["id"], {"shop_id": shop["id"] + 1})
        self.assertEqual("listing_target_immutable", raised.exception.code)
        store.confirm_inventory(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            external_inventory_id="protected-inventory",
        )
        with self.assertRaises(SalesError) as raised:
            store.patch_item(item["id"], {"external_inventory_id": "other-inventory"})
        self.assertEqual("external_inventory_immutable", raised.exception.code)

    def test_archive_pending_owner_filter_uses_internal_owner_for_manual_items(self):
        item = store.add_item(source_id="local", account_id=107, email="manual-owner@example.test")
        store.patch_item(
            item["id"],
            {"status": "listed", "archive_owner_id": "executor-a"},
            event="manual_status",
        )
        self.assertEqual([], store.list_archive_pending(owner_id="executor-b"))
        self.assertEqual([item["id"]], [row["id"] for row in store.list_archive_pending(owner_id="executor-a")])

    def test_freeze_persists_private_listing_binding_without_public_leak(self):
        shop = store.save_shop({"name": "绑定店铺", "external_shop_id": "external-shop"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "binding-goods", "goods_key": "binding-key", "name": "绑定商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=108, email="binding@example.test")
        store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="binding-material", delivery_ciphertext="ciphertext",
            binding={
                "external_shop_id": "external-shop",
                "external_product_id": "binding-goods",
                "goods_key": "binding-key",
            },
        )
        public = store.get_item(item["id"])
        private = store.get_item(item["id"], private=True)
        self.assertNotIn("listing_binding", public)
        self.assertEqual(
            {
                "external_shop_id": "external-shop",
                "external_product_id": "binding-goods",
                "goods_key": "binding-key",
            },
            private["listing_binding"],
        )

    def test_historical_freeze_can_attach_manual_sold_without_changing_status_or_archive(self):
        shop = store.save_shop({"name": "历史店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "historical-goods", "name": "历史商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=109, email="historical@example.test")
        store.patch_item(item["id"], {"status": "sold", "archived": True}, event="manual_status")
        frozen = store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="historical-material", delivery_ciphertext="ciphertext",
            historical=True,
        )
        self.assertEqual("sold", frozen["status"])
        self.assertTrue(frozen["archived"])
        self.assertEqual("pending", frozen["sync_status"])

    def test_normal_freeze_rejects_manual_sold_without_historical_flag(self):
        shop = store.save_shop({"name": "普通店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "normal-goods", "name": "普通商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=110, email="normal@example.test")
        store.patch_item(item["id"], {"status": "sold"}, event="manual_status")
        with self.assertRaises(SalesError) as raised:
            store.freeze_listing(
                item["id"], shop_id=shop["id"], product_id=product["id"],
                fingerprint="normal-material", delivery_ciphertext="ciphertext",
            )
        self.assertEqual("sold_listing_immutable", raised.exception.code)

    def test_order_ref_cannot_change_and_first_order_facts_are_preserved(self):
        shop = store.save_shop({"name": "订单事实店铺"})
        product = store.replace_products(
            shop["id"],
            [{"external_product_id": "order-goods", "name": "订单商品"}],
        )[0]
        item = store.add_item(source_id="local", account_id=111, email="order@example.test")
        store.freeze_listing(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            fingerprint="order-material", delivery_ciphertext="ciphertext",
        )
        first = store.confirm_inventory(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            external_inventory_id="", sold=True, order_ref="order-first",
            order_amount=20, paid_at="2026-11-27T10:00:00+00:00",
        )
        second = store.confirm_inventory(
            item["id"], shop_id=shop["id"], product_id=product["id"],
            external_inventory_id="", sold=True, order_ref="",
            order_amount=99, paid_at="2026-11-27T11:00:00+00:00",
        )
        self.assertEqual("order-first", second["order_ref"])
        self.assertEqual(first["order_amount"], second["order_amount"])
        self.assertEqual(first["paid_at"], second["paid_at"])
        with self.assertRaises(SalesError) as raised:
            store.confirm_inventory(
                item["id"], shop_id=shop["id"], product_id=product["id"],
                external_inventory_id="", sold=True, order_ref="order-other",
            )
        self.assertEqual("order_ref_conflict", raised.exception.code)
