# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor

from core import admin_repository, db, record_store
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AdminCrudTests(PostgresTestCase):
    def setUp(self):
        record_store.reset_ready()
        record_store.init()

    def test_account_bulk_mutations_touch_only_selected_rows(self):
        first = record_store.insert_row(record_store.ACCOUNTS, {"email": "a@example.test"})
        second = record_store.insert_row(record_store.ACCOUNTS, {"email": "b@example.test"})

        updated, skipped = db.update_accounts_note([first, 99999], "reviewed")
        self.assertEqual([item["id"] for item in updated], [first])
        self.assertEqual(skipped, [{"id": 99999, "reason": "账号不存在"}])
        self.assertEqual(db.get_account(first)["note"], "reviewed")
        self.assertEqual(db.get_account(second)["note"], "")

        archived, skipped = db.archive_accounts([first, 99999], True)
        self.assertEqual([item["id"] for item in archived], [first])
        self.assertEqual(len(skipped), 1)
        deleted, skipped = db.delete_accounts([first, 99999])
        self.assertEqual([item["id"] for item in deleted], [first])
        self.assertIsNone(db.get_account(first))
        self.assertIsNotNone(db.get_account(second))

    def test_pool_claim_is_atomic_across_workers(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "only@example.test",
            "status": "available",
            "password": "secret",
        })
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda _index: db.claim_next_outlook(), range(6)))
        claimed = [row for row in results if row]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["email"], "only@example.test")

    def test_email_list_is_compact_and_secret_endpoint_is_explicit(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "pool@example.test",
            "status": "available",
            "password": "mail-password",
            "client_id": "client-id",
            "refresh_token": "refresh-secret",
        })
        listing = admin_repository.list_email_pool(
            admin_repository.PageRequest(page=1, page_size=20, filters={"source": "outlook"})
        )
        item = listing["items"][0]
        self.assertTrue(item["has_password"])
        self.assertNotIn("password", item)
        self.assertNotIn("refresh_token", item)

        app = create_app(auth_code="test-auth")
        legacy_list = app.test_client().get(
            "/api/outlook?source=outlook&limit=20",
            headers={"X-Auth-Code": "test-auth"},
        )
        self.assertEqual(legacy_list.status_code, 200)
        self.assertNotIn("password", legacy_list.get_json()[0])
        self.assertNotIn("refresh_token", legacy_list.get_json()[0])

        response = app.test_client().get(
            "/api/outlook/secret?source=outlook&email=pool@example.test&field=copy_line",
            headers={"X-Auth-Code": "test-auth"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["value"],
            "pool@example.test----mail-password----client-id----refresh-secret",
        )

    def test_codex_crud_uses_database_and_atomic_counters(self):
        filename = "codex-user@example.test-free.json"
        content = {
            "email": "user@example.test",
            "type": "codex",
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "account_id": "acct-1",
        }
        db.save_codex_credential_record(filename, content)
        listing = admin_repository.list_codex(
            admin_repository.PageRequest(page=1, page_size=20, filters={"archived": "0"})
        )
        self.assertEqual(listing["total"], 1)
        self.assertNotIn("content", listing["accounts"][0])
        self.assertEqual(listing["accounts"][0]["access_token_preview"], "已保存")

        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(lambda _index: db.mark_codex_exported(filename), range(5)))
        stored = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertEqual(stored["exported_count"], 5)

        raw, actual = db.read_codex_credential(filename)
        self.assertEqual(actual, filename)
        self.assertIn("access-secret", raw)
        self.assertTrue(db.archive_codex(filename, True)["archived"])
        self.assertTrue(db.delete_codex_credential(filename))
        self.assertIsNone(record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename))

    def test_job_batch_delete_has_atomic_running_guard(self):
        terminal = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "terminal-job",
            "status": "failed",
        })
        running = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "running-job",
            "status": "running",
        })
        deleted, skipped = db.delete_jobs([terminal, running, 99999], delete_log=False)
        self.assertEqual([int(row["id"]) for row in deleted], [terminal])
        self.assertEqual({item["reason"] for item in skipped}, {"运行中，不能删除", "任务不存在"})
        self.assertIsNotNone(db.get_job(running))


if __name__ == "__main__":
    import unittest
    unittest.main()
