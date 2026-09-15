# -*- coding: utf-8 -*-
"""Runtime writes stay in PostgreSQL and do not enqueue retired projections."""
import unittest

from core import compat_export, db, record_store as rs
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
