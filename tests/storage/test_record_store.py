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
from unittest.mock import patch

from core.storage import records as rs
from core.storage.records import ACCOUNTS, GENERIC_API_POOL, JOBS, OUTLOOK_POOL
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

    def test_generated_account_facets_follow_json_updates(self):
        acc_id = rs.insert_row(ACCOUNTS, {
            "email": "facets@example.test",
            "access_token": "token",
            "extra_json": '{"account_password":"secret"}',
            "totp_secret": "totp",
            "deactivation_mail_detected": True,
        })
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT account_has_access_token, account_has_password, "
                f"account_totp_enabled, account_deactivation_detected "
                f"FROM {rs._qualified(ACCOUNTS)} WHERE id = %s",
                (acc_id,),
            )
            self.assertEqual(tuple(cur.fetchone().values()), (True, True, True, True))

        rs.patch_row(ACCOUNTS, acc_id, {
            "access_token": "",
            "extra_json": "{}",
            "totp_secret": "",
            "deactivation_mail_detected": False,
        })
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT account_has_access_token, account_has_password, "
                f"account_totp_enabled, account_deactivation_detected "
                f"FROM {rs._qualified(ACCOUNTS)} WHERE id = %s",
                (acc_id,),
            )
            self.assertEqual(tuple(cur.fetchone().values()), (False, False, False, False))


class RecordStoreMigrationTests(PostgresTestCase):
    def test_new_process_reuses_completed_migration_without_schema_lock(self):
        rs.init()
        with (
            patch.object(rs, "_READY_KEY", ""),
            patch.object(rs, "advisory_xact_lock", wraps=rs.advisory_xact_lock) as schema_lock,
            patch.object(rs, "_sync_identity_cursor", wraps=rs._sync_identity_cursor) as repair,
        ):
            rs.init()
            schema_lock.assert_not_called()
            repair.assert_not_called()

    def test_migration_failure_leaves_no_completed_version(self):
        rs.reset_ready()
        with patch.object(rs, "_sync_identity_cursor", side_effect=RuntimeError("模拟序列修复中断")):
            with self.assertRaisesRegex(RuntimeError, "模拟序列修复中断"):
                rs.init()

        with (
            patch.object(rs, "_FORCE_SCHEMA_CHECK", False),
            patch.object(rs, "advisory_xact_lock", wraps=rs.advisory_xact_lock) as schema_lock,
            patch.object(rs, "_sync_identity_cursor", wraps=rs._sync_identity_cursor) as repair,
        ):
            rs.init()
            schema_lock.assert_called_once()
            self.assertEqual(repair.call_count, len(rs.ALL_TABLES))

    def test_second_initializer_rechecks_version_after_waiting_for_schema_lock(self):
        rs.init()
        with (
            patch.object(rs, "_READY_KEY", ""),
            patch.object(rs, "_SCHEMA_VERSION", rs._SCHEMA_VERSION + 1),
            patch.object(rs, "_apply_record_schema", wraps=rs._apply_record_schema) as migrate,
            rs._connect() as first,
            first.cursor() as cur,
        ):
            rs.advisory_xact_lock(first, f"record-store-schema:{self.schema}")
            cur.execute(
                f"INSERT INTO {rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)} (version) VALUES (%s)",
                (rs._SCHEMA_VERSION,),
            )
            original_lock = rs.advisory_xact_lock
            reached_lock = threading.Event()
            errors = []

            def wait_for_lock(conn, key):
                reached_lock.set()
                original_lock(conn, key)

            def init_in_second_connection():
                try:
                    rs.init()
                except Exception as exc:
                    errors.append(exc)

            with patch.object(rs, "advisory_xact_lock", side_effect=wait_for_lock):
                second = threading.Thread(target=init_in_second_connection)
                second.start()
                try:
                    self.assertTrue(reached_lock.wait(timeout=10))
                finally:
                    first.commit()
                    second.join(timeout=10)

            self.assertFalse(second.is_alive())
            self.assertEqual(errors, [])
            migrate.assert_not_called()

    def test_registration_jobs_have_normalized_email_index(self):
        rs.init()
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
                (self.schema, "idx_registration_jobs_normalized_email_id"),
            )
            definition = cur.fetchone()
        self.assertIsNotNone(definition)
        self.assertIn("lower(btrim(email)), id DESC", definition["indexdef"])


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

    def test_patch_returning_ids_only_preserves_guard_without_merging_sparse_data(self):
        busy_id = rs.insert_row(ACCOUNTS, {
            "email": "busy@example.test", "plan_check_status": "running", "note": "busy-note",
        })
        with patch.object(rs, "_merge", side_effect=AssertionError("ID-only must not merge account data")):
            rows = rs.patch_rows_where_returning(
                ACCOUNTS, changes={"plan_check_status": "queued", "note": "new-note"},
                where="id=ANY(%s) AND COALESCE(plan_check_status, '') <> %s",
                params=([self.acc_id, busy_id, 999999], "running"), id_only=True,
            )
        self.assertEqual(rows, [{"id": self.acc_id}])
        account = rs.get_row(ACCOUNTS, self.acc_id)
        self.assertEqual(account["plan_check_status"], "queued")
        self.assertEqual(account["note"], "new-note")
        self.assertEqual(account["access_token"], "token-original")
        busy = rs.get_row(ACCOUNTS, busy_id)
        self.assertEqual(busy["plan_check_status"], "running")
        self.assertEqual(busy["note"], "busy-note")

    def test_patch_returning_defaults_to_full_merged_business_rows(self):
        rows = rs.patch_rows_where_returning(
            ACCOUNTS, changes={"plan_check_status": "queued", "note": "new-note"},
            where="id = %s", params=(self.acc_id,),
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], self.acc_id)
        self.assertEqual(row["email"], "merge@example.test")
        self.assertEqual(row["plan_check_status"], "queued")
        self.assertEqual(row["note"], "new-note")
        self.assertEqual(row["access_token"], "token-original")
        self.assertTrue(row["updated_at"])
        self.assertNotIn("data", row)
        self.assertNotIn("deactivated", row)

    def test_patch_returning_borrowed_connection_rolls_back_in_both_modes(self):
        for id_only in (False, True):
            with self.subTest(id_only=id_only):
                with self.assertRaisesRegex(RuntimeError, "rollback"):
                    with rs.transaction() as conn:
                        rows = rs.patch_rows_where_returning(
                            ACCOUNTS, changes={"plan_check_status": "queued", "note": "new-note"},
                            where="id = %s", params=(self.acc_id,), conn=conn, id_only=id_only,
                        )
                        self.assertEqual([row["id"] for row in rows], [self.acc_id])
                        self.assertEqual(rs.get_row(ACCOUNTS, self.acc_id, conn=conn)["plan_check_status"], "queued")
                        raise RuntimeError("rollback")
                account = rs.get_row(ACCOUNTS, self.acc_id)
                self.assertIsNone(account["plan_check_status"])
                self.assertEqual(account["note"], "原备注")
                self.assertEqual(account["access_token"], "token-original")

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

    def test_init_repairs_identity_sequences_after_explicit_import_ids(self):
        rs.insert_row(OUTLOOK_POOL, {
            "id": 500,
            "email": "imported@example.test",
            "status": "available",
        })
        rs.reset_ready()
        rs.init()

        new_id = rs.insert_row(OUTLOOK_POOL, {
            "email": "after-import@example.test",
            "status": "available",
        })
        self.assertGreater(new_id, 500)

    def test_pools_are_separate_tables(self):
        rs.insert_row(OUTLOOK_POOL, {"email": "same@example.test", "status": "available"})
        rs.insert_row(GENERIC_API_POOL, {"email": "same@example.test", "status": "used"})
        self.assertEqual(rs.get_row_by(OUTLOOK_POOL, "email", "same@example.test")["status"], "available")
        self.assertEqual(rs.get_row_by(GENERIC_API_POOL, "email", "same@example.test")["status"], "used")


class IdentitySequenceTests(PostgresTestCase):
    def test_repeated_init_does_not_consume_synchronized_identity(self):
        rs.init()
        first_id = rs.insert_row(JOBS, {"job_uuid": "u-first", "status": "queued"})
        self.assertEqual(first_id, 1)

        rs.reset_ready()
        rs.init()
        rs.reset_ready()
        rs.init()

        next_id = rs.insert_row(JOBS, {"job_uuid": "u-next", "status": "queued"})
        self.assertEqual(next_id, 2)

    def test_empty_identity_table_starts_at_one(self):
        rs.init()
        first_id = rs.insert_row(
            OUTLOOK_POOL,
            {"email": "first@example.test", "status": "available"},
        )
        self.assertEqual(first_id, 1)

    def test_explicit_import_id_is_repaired_without_a_startup_gap(self):
        rs.init()
        imported_id = rs.insert_row(
            JOBS,
            {"id": 500, "job_uuid": "u-imported", "status": "success"},
        )
        self.assertEqual(imported_id, 500)

        rs.reset_ready()
        rs.init()
        rs.reset_ready()
        rs.init()

        next_id = rs.insert_row(JOBS, {"job_uuid": "u-after-import", "status": "queued"})
        self.assertEqual(next_id, 501)

    def test_history_table_without_identity_sequence_does_not_block_init(self):
        table = rs._qualified(OUTLOOK_POOL)
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            cur.execute(
                f"CREATE TABLE {table} ("
                "id BIGINT PRIMARY KEY, "
                "data JSONB NOT NULL DEFAULT '{}'::jsonb"
                ")"
            )

        rs.reset_ready()
        rs.init()
        imported_id = rs.insert_row(
            OUTLOOK_POOL,
            {"id": 77, "email": "legacy@example.test", "status": "available"},
        )
        self.assertEqual(imported_id, 77)

        rs.reset_ready()
        rs.init()
        self.assertEqual(rs.get_row(OUTLOOK_POOL, imported_id)["email"], "legacy@example.test")


if __name__ == "__main__":
    unittest.main()
