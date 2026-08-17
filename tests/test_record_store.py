# -*- coding: utf-8 -*-
"""record_store 行级存储的行为测试。

重点验证三件旧 blob 方案做不到的事：
  1. 部分更新只动指定字段，并发改不同字段不会互相覆盖
  2. 条件更新实现真正的抢占（跨连接，不依赖进程内锁）
  3. 跨表事务能整体回滚
"""
import json
import threading
import unittest

from core import record_store as rs
from core.record_store import ACCOUNTS, GENERIC_API_POOL, JOBS, OUTLOOK_POOL
from tests.support_pg import PostgresTestCase


class RecordStoreSchemaTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def test_promoted_and_jsonb_fields_round_trip_as_one_flat_dict(self):
        acc_id = rs.insert_row(ACCOUNTS, {
            "email": "a@example.test",
            "plan_check_status": "success",      # 提升列
            "codex_agent_oai_session_id": "s-1",  # 稀疏字段，进 data
            "eligible_offer_ids": ["x", "y"],
        })
        row = rs.get_row(ACCOUNTS, acc_id)
        self.assertEqual(row["email"], "a@example.test")
        self.assertEqual(row["plan_check_status"], "success")
        self.assertEqual(row["codex_agent_oai_session_id"], "s-1")
        self.assertEqual(row["eligible_offer_ids"], ["x", "y"])
        self.assertEqual(row["id"], acc_id)

    def test_sparse_field_is_not_materialised_as_column(self):
        rs.insert_row(ACCOUNTS, {"email": "b@example.test", "some_brand_new_field": 1})
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s",
                (self.schema, ACCOUNTS.name),
            )
            columns = {r["column_name"] for r in cur.fetchall()}
        self.assertIn("plan_check_status", columns)      # 提升列存在
        self.assertNotIn("some_brand_new_field", columns)  # 新字段不需要 migration

    def test_derived_column_tracks_account_status(self):
        acc_id = rs.insert_row(ACCOUNTS, {"email": "c@example.test"})
        self.assertEqual(rs.count_rows(ACCOUNTS, where="deactivated"), 0)

        rs.patch_row(ACCOUNTS, acc_id, {"account_status": "deactivated"})
        self.assertEqual(rs.count_rows(ACCOUNTS, where="deactivated"), 1)

        # 无关更新不能把派生列连带清掉
        rs.patch_row(ACCOUNTS, acc_id, {"note": "改个备注"})
        self.assertEqual(rs.count_rows(ACCOUNTS, where="deactivated"), 1)


class PartialUpdateTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.acc_id = rs.insert_row(ACCOUNTS, {
            "email": "merge@example.test",
            "access_token": "token-original",
            "note": "原备注",
        })

    def test_patch_touches_only_named_fields(self):
        rs.patch_row(ACCOUNTS, self.acc_id, {"note": "新备注"})
        row = rs.get_row(ACCOUNTS, self.acc_id)
        self.assertEqual(row["note"], "新备注")
        self.assertEqual(row["access_token"], "token-original")

    def test_concurrent_patches_of_distinct_fields_both_survive(self):
        """旧的读全量→改→写全量在这里会丢掉其中一个改动。"""
        errors = []

        def write(field: str, value: str):
            try:
                rs.patch_row(ACCOUNTS, self.acc_id, {field: value})
            except Exception as exc:  # pragma: no cover - 出错时给出可读信息
                errors.append(f"{field}: {exc}")

        threads = [
            threading.Thread(target=write, args=("live_check_error", "错误A")),
            threading.Thread(target=write, args=("plan_check_error", "错误B")),
            threading.Thread(target=write, args=("note", "备注C")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        row = rs.get_row(ACCOUNTS, self.acc_id)
        self.assertEqual(row["live_check_error"], "错误A")
        self.assertEqual(row["plan_check_error"], "错误B")
        self.assertEqual(row["note"], "备注C")
        self.assertEqual(row["access_token"], "token-original")


class AtomicClaimTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.acc_id = rs.insert_row(ACCOUNTS, {"email": "claim@example.test"})

    def _claim(self) -> bool:
        return rs.claim_row(
            ACCOUNTS, self.acc_id,
            changes={"live_check_status": "queued", "live_check_trigger": "manual"},
            guard="deactivated = FALSE AND COALESCE(live_check_status,'') NOT IN ('queued','running')",
        )

    def test_second_claim_is_rejected(self):
        self.assertTrue(self._claim())
        self.assertFalse(self._claim())

    def test_only_one_of_many_concurrent_claims_wins(self):
        """这正是旧实现做不到的：threading.RLock 挡不住另一个进程。"""
        results = []
        lock = threading.Lock()

        def attempt():
            ok = self._claim()
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(1 for r in results if r), 1, f"应恰好一个成功，实际 {results}")

    def test_claim_is_released_when_status_cleared(self):
        self.assertTrue(self._claim())
        rs.patch_row(ACCOUNTS, self.acc_id, {"live_check_status": "success"})
        self.assertTrue(self._claim())

    def test_deactivated_account_cannot_be_claimed(self):
        rs.patch_row(ACCOUNTS, self.acc_id, {"account_status": "deactivated"})
        self.assertFalse(self._claim())


class CrossTableTransactionTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def test_account_and_pool_commit_together(self):
        with rs.transaction() as conn:
            acc_id = rs.insert_row(ACCOUNTS, {"email": "tx@example.test"}, conn=conn)
            rs.insert_row(OUTLOOK_POOL, {
                "email": "tx@example.test", "status": "used", "registered_account_id": acc_id,
            }, conn=conn)

        self.assertIsNotNone(rs.get_row_by(ACCOUNTS, "email", "tx@example.test"))
        pool = rs.get_row_by(OUTLOOK_POOL, "email", "tx@example.test")
        self.assertEqual(pool["status"], "used")

    def test_failure_rolls_back_both_tables(self):
        """旧实现是两次独立写文件，中间失败会留下"账号建了但邮箱没标记 used"。"""
        with self.assertRaises(Exception):
            with rs.transaction() as conn:
                rs.insert_row(ACCOUNTS, {"email": "rollback@example.test"}, conn=conn)
                rs.insert_row(OUTLOOK_POOL, {"email": "rollback@example.test"}, conn=conn)
                raise RuntimeError("模拟中途失败")

        self.assertIsNone(rs.get_row_by(ACCOUNTS, "email", "rollback@example.test"))
        self.assertIsNone(rs.get_row_by(OUTLOOK_POOL, "email", "rollback@example.test"))


class QueryTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        for i, (email, archived, plan) in enumerate([
            ("q1@example.test", False, "plus"),
            ("q2@example.test", False, "free"),
            ("q3@example.test", True, "free"),
        ], start=1):
            rs.insert_row(ACCOUNTS, {
                "email": email, "archived": archived, "current_plan_type": plan,
            })

    def test_archived_filter_and_default_ordering(self):
        rows = rs.list_rows(ACCOUNTS, where="archived = %s", params=(False,))
        self.assertEqual([r["email"] for r in rows], ["q2@example.test", "q1@example.test"])

    def test_lookup_by_email_is_case_insensitive(self):
        row = rs.get_row_by(ACCOUNTS, "email", "Q1@EXAMPLE.TEST", lower=True)
        self.assertIsNotNone(row)
        self.assertEqual(row["email"], "q1@example.test")

    def test_jsonb_substring_search_covers_sparse_fields(self):
        rs.insert_row(ACCOUNTS, {"email": "q4@example.test", "user_name": "独特名字"})
        rows = rs.list_rows(ACCOUNTS, where="data::text ILIKE %s", params=("%独特名字%",))
        self.assertEqual([r["email"] for r in rows], ["q4@example.test"])

    def test_sync_identity_keeps_migrated_ids(self):
        rs.insert_row(JOBS, {"id": 500, "job_uuid": "u-500", "status": "success"})
        rs.sync_identity(JOBS)
        new_id = rs.insert_row(JOBS, {"job_uuid": "u-next", "status": "queued"})
        self.assertGreater(new_id, 500)

    def test_pools_are_separate_tables(self):
        rs.insert_row(OUTLOOK_POOL, {"email": "same@example.test", "status": "available"})
        rs.insert_row(GENERIC_API_POOL, {"email": "same@example.test", "status": "used"})
        self.assertEqual(rs.get_row_by(OUTLOOK_POOL, "email", "same@example.test")["status"], "available")
        self.assertEqual(rs.get_row_by(GENERIC_API_POOL, "email", "same@example.test")["status"], "used")


if __name__ == "__main__":
    unittest.main()
