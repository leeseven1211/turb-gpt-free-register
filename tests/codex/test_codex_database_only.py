# -*- coding: utf-8 -*-
"""Codex 凭证和操作状态只在 PostgreSQL 中持久化。"""
from concurrent.futures import ThreadPoolExecutor
import json

from core.storage import compat_export
from core import db
from core.storage import postgres as postgres_store, records as record_store
from tests.support_pg import PostgresTestCase


class CodexDatabaseOnlyTests(PostgresTestCase):
    def setUp(self):
        record_store.reset_ready()
        record_store.init()
        self.filename = "codex-database-only@example.test-free.json"
        self.content = {
            "email": "database-only@example.test",
            "account_id": "acct-database-only",
            "type": "codex",
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
        }

    def assert_no_codex_snapshots(self):
        compat_export.flush()
        self.assertFalse(db._CODEX_DIR.exists(), "业务写入不得生成凭证目录")
        self.assertFalse(db._CODEX_EXPORT_STATE.exists(), "业务写入不得生成导出状态文件")
        self.assert_no_collection_copies()

    def assert_no_collection_copies(self):
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {postgres_store.qualified('app_collections')}")
            self.assertEqual(cur.fetchone()[0], 0, "Codex 操作不得生成全量集合副本")

    def test_credential_lifecycle_persists_without_generating_snapshots(self):
        db.save_codex_credential_record(self.filename, self.content)
        self.assert_no_codex_snapshots()
        updated = {**self.content, "access_token": "synthetic-updated"}
        db.write_codex_credential(self.filename, updated)
        self.assert_no_codex_snapshots()
        raw, filename = db.read_codex_credential(self.filename)
        self.assertEqual(filename, self.filename)
        self.assertEqual(json.loads(raw)["access_token"], "synthetic-updated")

        def increment(index):
            if index % 2:
                return db.mark_codex_exported(self.filename)
            return db.mark_codex_sub2_uploaded(self.filename)

        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(increment, range(16)))
        stored = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", self.filename)
        self.assertEqual(stored["exported_count"], 8)
        self.assertEqual(stored["sub2_uploaded_count"], 8)
        self.assertTrue(stored["exported_at"])
        self.assertTrue(stored["sub2_uploaded_at"])
        self.assert_no_codex_snapshots()

        db.mark_codex_sub2_sync_error(self.filename, "测试同步失败")
        db.mark_codex_oauth_refresh(self.filename, error="测试刷新失败")
        self.assertTrue(db.archive_codex(self.filename, True)["archived"])
        self.assertEqual(db.list_codex_accounts(), [])
        self.assertEqual(len(db.list_codex_accounts(archived="1")), 1)
        self.assert_no_codex_snapshots()
        db.archive_codex(self.filename, False)
        db.reset_codex_exported(self.filename)
        stored = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", self.filename)
        self.assertEqual(stored["exported_count"], 0)
        self.assertIsNone(stored["exported_at"])
        self.assertEqual(stored["sub2_uploaded_count"], 8)
        self.assertEqual(stored["sub2_sync_error"], "测试同步失败")
        self.assertEqual(stored["oauth_refresh_error"], "测试刷新失败")
        self.assertFalse(stored["archived"])
        self.assert_no_codex_snapshots()
        self.assertTrue(db.delete_codex_credential(self.filename))
        self.assertIsNone(record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", self.filename))
        self.assert_no_codex_snapshots()

    def test_legacy_files_do_not_change_database_or_get_rewritten_or_deleted(self):
        record_store.insert_row(record_store.CODEX_CREDENTIALS, {
            "filename": self.filename,
            "email": self.content["email"],
            "account_id": self.content["account_id"],
            "content": self.content,
            "exported_count": 0,
        })
        db._CODEX_DIR.mkdir()
        legacy_credential = db._CODEX_DIR / self.filename
        credential_text = json.dumps({**self.content, "access_token": "stale-file-access"})
        state_text = json.dumps({self.filename: {"exported_count": 99, "archived": True}})
        legacy_credential.write_text(credential_text, encoding="utf-8")
        db._CODEX_EXPORT_STATE.write_text(state_text, encoding="utf-8")

        raw, _filename = db.read_codex_credential(self.filename)
        self.assertEqual(json.loads(raw)["access_token"], "synthetic-access")
        listing = db.list_codex_accounts()
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["exported_count"], 0)
        db.mark_codex_exported(self.filename)
        db.mark_codex_sub2_uploaded(self.filename)
        self.assertTrue(db.delete_codex_credential(self.filename))
        self.assertFalse(db.delete_codex_credential(self.filename))
        compat_export.flush()
        self.assertTrue(legacy_credential.exists(), "删除数据库凭证不得删除历史文件")
        self.assertEqual(legacy_credential.read_text(encoding="utf-8"), credential_text)
        self.assertEqual(db._CODEX_EXPORT_STATE.read_text(encoding="utf-8"), state_text)
        self.assertIsNone(record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", self.filename))
        self.assert_no_collection_copies()
