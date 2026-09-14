# -*- coding: utf-8 -*-
"""行级存储改造的并发与快照安全回归。"""
from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from core import db, record_store as rs
from core.storage.db_legacy import SnapshotConflictError
from tests.support_pg import PostgresTestCase


class FreshSchemaCreateTests(PostgresTestCase):
    """首次业务调用也必须自己完成行级表初始化。"""

    def test_create_job_and_account_initialize_a_new_schema(self):
        # 本类没有 setUp 调 rs.init()；PostgresTestCase 只创建 schema，不创建业务表。
        job = db.create_job("outlook", data={"config_snapshot": {"plan_check_enabled": False}})
        account_id = db.insert_account(
            email="fresh-schema@example.test",
            access_token="token-fresh-schema",
        )

        self.assertIsNotNone(rs.get_row(rs.JOBS, job["id"]))
        self.assertIsNotNone(rs.get_row(rs.ACCOUNTS, account_id))


class FreshSchemaAccountTests(PostgresTestCase):
    """账号入口单独验证：不能依赖 create_job 先建过业务表。"""

    def test_insert_account_initializes_a_new_schema(self):
        account_id = db.insert_account(
            email="fresh-account-schema@example.test",
            access_token="token-fresh-account-schema",
        )

        self.assertIsNotNone(rs.get_row(rs.ACCOUNTS, account_id))


class SnapshotConflictTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def test_versioned_stale_snapshot_raises_and_does_not_report_success(self):
        job_id = rs.insert_row(rs.JOBS, {"job_uuid": "snapshot-versioned", "status": "queued"})
        stale = rs.get_row(rs.JOBS, job_id, include_version=True)
        rs.patch_row(rs.JOBS, job_id, {"status": "running"})

        with self.assertRaises(SnapshotConflictError):
            db._sync_table(rs.JOBS, [stale])

        self.assertEqual(rs.get_row(rs.JOBS, job_id)["status"], "running")

    def test_unversioned_existing_snapshot_is_rejected_instead_of_full_overwrite(self):
        job_id = rs.insert_row(rs.JOBS, {"job_uuid": "snapshot-unversioned", "status": "queued"})
        stale = rs.get_row(rs.JOBS, job_id)
        rs.patch_row(rs.JOBS, job_id, {"status": "running", "worker_pid": 123})

        with self.assertRaises(SnapshotConflictError):
            db._sync_table(rs.JOBS, [stale])

        row = rs.get_row(rs.JOBS, job_id)
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["worker_pid"], 123)

    def test_compat_snapshot_insert_does_not_delete_unmentioned_rows(self):
        first_id = rs.insert_row(rs.JOBS, {"job_uuid": "kept-1", "status": "success"})
        second_id = rs.insert_row(rs.JOBS, {"job_uuid": "kept-2", "status": "failed"})

        payload = {"job_uuid": "compat-new", "status": "queued"}
        db._sync_table(rs.JOBS, [payload])

        self.assertIsNotNone(rs.get_row(rs.JOBS, first_id))
        self.assertIsNotNone(rs.get_row(rs.JOBS, second_id))
        self.assertEqual(rs.count_rows(rs.JOBS), 3)

    def test_nested_data_filters_reserved_and_promoted_keys(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": "nested-data@example.test",
            "plan_check_status": "success",
            "data": {
                "email": "nested-email-must-not-win",
                "plan_check_status": "nested-status-must-not-win",
                "deactivated": True,
                "account_has_access_token": True,
                "copy_line": "derived-metadata",
                "account_copy_line": "derived-account-metadata",
                "__record_version": "stale-version",
                "keep_nested_value": {"kind": "business"},
            },
        })

        row = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertEqual(row["email"], "nested-data@example.test")
        self.assertEqual(row["plan_check_status"], "success")
        self.assertEqual(row["keep_nested_value"], {"kind": "business"})
        self.assertNotIn("deactivated", row)
        self.assertNotIn("account_has_access_token", row)
        self.assertNotIn("copy_line", row)
        self.assertNotIn("account_copy_line", row)
        self.assertNotIn("__record_version", row)

        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT data FROM {rs._qualified(rs.ACCOUNTS)} WHERE id = %s",
                (account_id,),
            )
            data = cur.fetchone()["data"]
        self.assertEqual(data, {"keep_nested_value": {"kind": "business"}})

    def test_nested_data_survives_partial_patch_with_shallow_jsonb_merge(self):
        job_id = rs.insert_row(rs.JOBS, {
            "job_uuid": "nested-data-patch",
            "status": "queued",
            "data": {
                "config_snapshot": {"plan_check_enabled": True},
                "opaque_payload": {"version": 1},
            },
        })

        rs.patch_row(rs.JOBS, job_id, {
            "status": "running",
            "data": {
                "opaque_payload": {"version": 2},
                "status": "nested-status-must-not-win",
                "copy_line": "derived-metadata",
            },
        })

        row = rs.get_row(rs.JOBS, job_id)
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["config_snapshot"], {"plan_check_enabled": True})
        self.assertEqual(row["opaque_payload"], {"version": 2})
        self.assertNotIn("copy_line", row)
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT data FROM {rs._qualified(rs.JOBS)} WHERE id = %s",
                (job_id,),
            )
            self.assertEqual(cur.fetchone()["data"], {
                "config_snapshot": {"plan_check_enabled": True},
                "opaque_payload": {"version": 2},
            })


class ConcurrentWriteTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def test_concurrent_create_jobs_use_database_generated_ids(self):
        barrier = threading.Barrier(8)
        ids: list[int] = []
        errors: list[str] = []
        lock = threading.Lock()

        def insert(index: int) -> None:
            try:
                barrier.wait(timeout=10)
                job = db.create_job(
                    "outlook",
                    data={"config_snapshot": {"plan_check_enabled": False}},
                )
                with lock:
                    ids.append(int(job["id"]))
            except Exception as exc:  # pragma: no cover - failure detail is asserted below
                with lock:
                    errors.append(f"{index}: {exc}")

        with patch.object(db.compat_export, "schedule"):
            threads = [threading.Thread(target=insert, args=(index,)) for index in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=40)

        self.assertEqual(errors, [])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(set(ids)), 8)
        self.assertEqual(rs.count_rows(rs.JOBS), 8)

    def test_concurrent_distinct_field_updates_both_survive(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "distinct-fields@example.test"})
        barrier = threading.Barrier(3)
        errors: list[str] = []

        def update_note() -> None:
            try:
                barrier.wait(timeout=10)
                self.assertTrue(db.update_account_note(account_id, "并发备注"))
            except Exception as exc:  # pragma: no cover - failure detail is asserted below
                errors.append(f"note: {exc}")

        def update_extract() -> None:
            try:
                barrier.wait(timeout=10)
                self.assertTrue(db.update_account_extract(
                    account_id,
                    {"ok": True, "status": "success", "message": "extract-ok"},
                ))
            except Exception as exc:  # pragma: no cover - failure detail is asserted below
                errors.append(f"extract: {exc}")

        def update_proxy() -> None:
            try:
                barrier.wait(timeout=10)
                self.assertTrue(db.update_account_registration_proxy(
                    account_id, provider="provider-test", region="us",
                ))
            except Exception as exc:  # pragma: no cover - failure detail is asserted below
                errors.append(f"proxy: {exc}")

        threads = [
            threading.Thread(target=update_note),
            threading.Thread(target=update_extract),
            threading.Thread(target=update_proxy),
        ]
        with patch.object(db.compat_export, "schedule"):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)

        self.assertEqual(errors, [])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        row = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertEqual(row["note"], "并发备注")
        self.assertEqual(row["extract_link_status"], "success")
        self.assertEqual(row["extract_link_message"], "extract-ok")
        self.assertEqual(row["registration_proxy_provider"], "provider-test")
        self.assertEqual(row["registration_proxy_region"], "US")

    def test_hot_business_writes_do_not_call_snapshot_helpers(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "hot-path@example.test"})

        with (
            patch.object(db, "_load_accounts", side_effect=AssertionError("hot path loaded accounts")),
            patch.object(db, "_load_jobs", side_effect=AssertionError("hot path loaded jobs")),
            patch.object(db, "_sync_table", side_effect=AssertionError("hot path synced snapshot")),
            patch.object(db.compat_export, "schedule"),
        ):
            job = db.create_job("outlook")
            self.assertTrue(db.update_account_note(account_id, "boundary-note"))
            self.assertTrue(db.update_account_extract(
                account_id, {"ok": True, "status": "success"},
            ))
            self.assertTrue(db.update_account_registration_proxy(
                account_id, provider="boundary-provider", region="ca",
            ))

        self.assertIsNotNone(rs.get_row(rs.JOBS, job["id"]))
        account = rs.get_row(rs.ACCOUNTS, account_id)
        self.assertEqual(account["note"], "boundary-note")
        self.assertEqual(account["extract_link_status"], "success")
        self.assertEqual(account["registration_proxy_region"], "CA")

    def test_duplicate_retry_creation_returns_one_shared_child(self):
        source = db.create_job("outlook")
        db.update_job(source["id"], status="success")
        barrier = threading.Barrier(2)
        results: list[tuple[dict, bool]] = []
        errors: list[str] = []
        lock = threading.Lock()

        def create() -> None:
            try:
                barrier.wait(timeout=10)
                result = db.create_retry_job(
                    source["id"],
                    job_type="registration_resume",
                    email_source="outlook",
                    email="retry@example.test",
                )
                with lock:
                    results.append(result)
            except Exception as exc:  # pragma: no cover - failure detail is asserted below
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=create) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(1 for _row, created in results if created), 1)
        self.assertEqual(len({int(row["id"]) for row, _created in results}), 1)
        self.assertEqual(
            rs.count_rows(rs.JOBS, where='"root_job_id" = %s', params=(source["id"],)),
            1,
        )

    def test_registered_import_uses_identity_and_is_idempotent(self):
        record = {
            "email": "imported@example.test",
            "password": "password-for-test",
            "client_id": "client-for-test",
            "refresh_token": "refresh-for-test",
            "access_token": "token-for-test",
        }

        self.assertEqual(
            db.import_registered_email_accounts([record, record], "outlook"),
            (1, 1),
        )
        account = rs.get_row_by(rs.ACCOUNTS, "email", record["email"], lower=True)
        pool = rs.get_row_by(rs.OUTLOOK_POOL, "email", record["email"], lower=True)
        self.assertIsNotNone(account)
        self.assertEqual(pool["status"], "used")
        self.assertEqual(pool["registered_account_id"], account["id"])
        self.assertEqual(rs.count_rows(rs.ACCOUNTS), 1)
        self.assertEqual(rs.count_rows(rs.OUTLOOK_POOL), 1)

    def test_startup_recovery_only_changes_rows_and_never_deletes(self):
        job_ids = [
            rs.insert_row(rs.JOBS, {
                "job_uuid": f"recovery-{status}",
                "status": status,
            })
            for status in ("success", "running", "queued")
        ]
        account_ids = [
            rs.insert_row(rs.ACCOUNTS, {
                "email": f"recovery-{index}@example.test",
                "live_check_status": status,
            })
            for index, status in enumerate(("success", "running"))
        ]
        before_jobs = rs.count_rows(rs.JOBS)
        before_accounts = rs.count_rows(rs.ACCOUNTS)

        db.recover_interrupted_registration_jobs()
        db.recover_interrupted_live_checks()

        self.assertEqual(rs.count_rows(rs.JOBS), before_jobs)
        self.assertEqual(rs.count_rows(rs.ACCOUNTS), before_accounts)
        self.assertEqual(rs.get_row(rs.JOBS, job_ids[0])["status"], "success")
        self.assertEqual(rs.get_row(rs.ACCOUNTS, account_ids[0])["live_check_status"], "success")


if __name__ == "__main__":
    unittest.main()
