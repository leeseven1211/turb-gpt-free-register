# -*- coding: utf-8 -*-
"""Runtime writes stay in PostgreSQL and do not enqueue retired projections."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from core import account_export, compat_export, db, plan_check_service, record_store as rs
from tests.support_pg import PostgresTestCase


class DatabaseOnlyCompatibilityTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        compat_export.flush()

    def test_account_mutations_have_no_file_projection(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "db-only-account@example.test"})
        self.assertTrue(db.update_account_note(account_id, "database note"))
        self.assertEqual([], [kind for kind in compat_export.pending()
                              if kind in {"accounts", "jobs", "outlook", "icloud_hide_emails"}])
        self.assertEqual("database note", db.get_account(account_id)["note"])
        self.assertEqual({"logs_dir": str(db.storage_paths()["logs_dir"])}, db.storage_paths())

    def test_registration_core_persistence_does_not_create_batch_archive(self):
        with TemporaryDirectory() as temporary_dir:
            archive_dir = Path(temporary_dir) / "accounts"
            with patch.object(account_export, "_ACCOUNTS_DIR", archive_dir, create=True):
                account_id = account_export.persist_account_core(
                    email="database-only-registration@example.test",
                    access_token="test-access-token",
                    email_source="outlook",
                )

            self.assertFalse(archive_dir.exists())

        account = db.get_account(account_id)
        self.assertEqual("database-only-registration@example.test", account["email"])
        self.assertEqual("test-access-token", account["access_token"])

    def test_save_account_data_accepts_deprecated_output_path_keyword(self):
        with TemporaryDirectory() as temporary_dir:
            output_path = Path(temporary_dir) / "deprecated-account.json"
            with patch.object(plan_check_service, "enqueue_account_plan_check"):
                account_id = account_export.save_account_data(
                    email="legacy-keyword@example.test",
                    access_token="test-access-token",
                    output_path=output_path,
                    email_source="outlook",
                )

            self.assertFalse(output_path.exists())

        account = db.get_account(account_id)
        self.assertEqual("legacy-keyword@example.test", account["email"])
        self.assertEqual("outlook", account["email_source"])

    def test_save_account_data_preserves_deprecated_output_path_position(self):
        with TemporaryDirectory() as temporary_dir:
            output_path = Path(temporary_dir) / "deprecated-account.json"
            with patch.object(
                plan_check_service,
                "check_registration_account_plan",
                return_value={"ok": True},
            ):
                account_id = account_export.save_account_data(
                    "legacy-positional@example.test",
                    "test-access-token",
                    None,
                    {},
                    output_path,
                    "outlook",
                    "http://proxy.example:8080",
                    "",
                )

            self.assertFalse(output_path.exists())

        account = db.get_account(account_id)
        self.assertEqual("outlook", account["email_source"])
        self.assertEqual("http://proxy.example:8080", account["proxy_used"])

    def test_job_mutations_have_no_file_projection(self):
        job = db.create_job("registration", data={"email": "db-only-job@example.test"})
        db.update_job(job["id"], status="failed", error="test")
        self.assertNotIn("jobs_json", db.storage_paths())
        self.assertEqual("failed", db.get_job(job["id"])["status"])

    def test_outlook_and_icloud_pool_mutations_have_no_file_projection(self):
        outlook_id = rs.insert_row(rs.OUTLOOK_POOL, {
            "email": "db-only-outlook@example.test", "status": "available",
        })
        hme_id = rs.insert_row(rs.ICLOUD_HIDE_POOL, {
            "email": "db-only-hme@example.test", "status": "available",
        })
        self.assertTrue(rs.patch_row(rs.OUTLOOK_POOL, outlook_id, {"status": "used"}))
        self.assertTrue(rs.patch_row(rs.ICLOUD_HIDE_POOL, hme_id, {"status": "used"}))
        self.assertNotIn("outlook_json", db.storage_paths())
        self.assertNotIn("icloud_hide_json", db.storage_paths())
        self.assertEqual("used", rs.get_row(rs.OUTLOOK_POOL, outlook_id)["status"])
        self.assertEqual("used", rs.get_row(rs.ICLOUD_HIDE_POOL, hme_id)["status"])


if __name__ == "__main__":
    unittest.main()
