# -*- coding: utf-8 -*-
import unittest

from core import admin_repository as repo
from core import db
from core import record_store as rs
from tests.support_pg import PostgresTestCase


class _QueryCounter:
    def __init__(self):
        self.count = 0

    def __enter__(self):
        import psycopg
        self._original = psycopg.Cursor.execute
        counter = self

        def execute(cursor, query, params=None, **kwargs):
            counter.count += 1
            return counter._original(cursor, query, params, **kwargs)

        psycopg.Cursor.execute = execute
        return self

    def __exit__(self, *_exc):
        import psycopg
        psycopg.Cursor.execute = self._original
        return False


class AdminRepositoryTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.account_ids = []
        for index in range(30):
            self.account_ids.append(rs.insert_row(rs.ACCOUNTS, {
                "email": f"user{index}@example.test",
                "email_source": "icloud_hide" if index % 2 else "outlook",
                "current_plan_type": "plus" if index % 3 == 0 else "free",
                "plan_check_status": "success",
                "plus_trial_eligible": index % 4 == 0,
                "codex_status": "success" if index % 2 else "failed",
                "access_token": f"token-{index}" if index % 2 else "",
                "totp_secret": "totp" if index % 2 else "",
                "password": "password" if index % 2 else "",
            }))
        for index in range(45):
            rs.insert_row(rs.JOBS, {
                "job_uuid": f"job-{index}",
                "email": f"user{index % 30}@example.test",
                "account_id": self.account_ids[index % 30] if index % 2 else None,
                "root_job_id": index + 1,
                "status": "failed" if index % 2 else "success",
                "email_source": "icloud_hide",
                "batch_id": "latest-batch" if index >= 40 else "older-batch",
                "batch_index": index,
            })
        rs.insert_row(rs.OUTLOOK_POOL, {"email": "pool1@example.test", "status": "available", "password": "secret"})
        rs.insert_row(rs.DOMAIN_POOL, {"email": "pool2@example.test", "status": "used", "code_url": "https://secret.test"})
        rs.insert_row(rs.ICLOUD_HIDE_POOL, {"email": "pool3@example.test", "status": "available", "account_id": "hme-1"})
        db.save_codex_credential_record(
            "codex-user1.json",
            {"email": "user1@example.test", "type": "codex", "access_token": "secret-token"},
        )

    def test_accounts_are_filtered_and_paginated_in_repository(self):
        result = repo.list_accounts(
            repo.PageRequest(page=2, page_size=7, filters={"source": "icloud_hide"}),
            archived="0",
        )
        self.assertEqual(result["total"], 15)
        self.assertEqual(len(result["items"]), 7)
        self.assertTrue(result["revision"])
        self.assertIn("source", result["facets"])
        self.assertTrue(all(item["email_source"] == "icloud_hide" for item in result["items"]))

    def test_job_page_has_constant_query_count(self):
        with _QueryCounter() as counter:
            result = repo.list_jobs(repo.PageRequest(page=1, page_size=20, filters={}))
        self.assertEqual(result["total"], 45)
        self.assertEqual(len(result["items"]), 20)
        self.assertLessEqual(counter.count, 8, counter.count)
        self.assertEqual(result["progress_rows"][-1]["batch_id"], "latest-batch")

    def test_email_pool_is_unified_and_does_not_return_secrets(self):
        result = repo.list_email_pool(repo.PageRequest(page=1, page_size=20, filters={"source": "all"}))
        self.assertEqual(result["total"], 3)
        self.assertEqual({row["source"] for row in result["items"]}, {"outlook", "cloudflare_domain", "icloud_hide"})
        for row in result["items"]:
            self.assertNotIn("password", row)
            self.assertNotIn("code_url", row)

    def test_codex_list_uses_relational_table_and_hides_content(self):
        result = repo.list_codex(repo.PageRequest(page=1, page_size=20, filters={"archived": "0"}))
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["summary"], {"total": 1, "exported": 0, "pending": 1})
        self.assertNotIn("content", result["accounts"][0])
        self.assertEqual(result["accounts"][0]["access_token_preview"], "已保存")

    def test_revision_changes_when_state_changes_inside_same_second(self):
        before_accounts = repo.list_account_statuses(repo.PageRequest(page=1, page_size=20))
        account_id = before_accounts["items"][0]["id"]
        rs.patch_row(rs.ACCOUNTS, account_id, {"plan_check_status": "running"})
        after_accounts = repo.list_account_statuses(repo.PageRequest(page=1, page_size=20))
        self.assertNotEqual(before_accounts["revision"], after_accounts["revision"])

        before_jobs = repo.list_jobs(repo.PageRequest(page=1, page_size=20))
        job_id = before_jobs["items"][0]["id"]
        rs.patch_row(rs.JOBS, job_id, {"status": "running"})
        after_jobs = repo.list_jobs(repo.PageRequest(page=1, page_size=20))
        self.assertNotEqual(before_jobs["revision"], after_jobs["revision"])

    def test_dashboard_uses_aggregates(self):
        result = repo.dashboard_aggregates()
        self.assertEqual(result["accounts"]["total"], 30)
        self.assertEqual(result["jobs"]["total"], 45)
        self.assertEqual(result["codex"]["total"], 1)

    def test_all_admin_reads_have_bounded_query_counts(self):
        cases = {
            "accounts": lambda: repo.list_accounts(repo.PageRequest(1, 20, {})),
            "account_status": lambda: repo.list_account_statuses(repo.PageRequest(1, 20, {})),
            "email_pool": lambda: repo.list_email_pool(repo.PageRequest(1, 20, {"source": "all"})),
            "codex": lambda: repo.list_codex(repo.PageRequest(1, 20, {"archived": "0"})),
            "dashboard": repo.dashboard_aggregates,
        }
        for name, call in cases.items():
            with self.subTest(name=name), _QueryCounter() as counter:
                call()
            self.assertLessEqual(counter.count, 12, (name, counter.count))


if __name__ == "__main__":
    unittest.main()
