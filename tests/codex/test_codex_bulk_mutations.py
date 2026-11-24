"""Codex 本地集合写入：真实隔离 PostgreSQL 与下载边界。"""
import io
import json
import logging
import zipfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from flask import Flask
from psycopg import Cursor

from core import db
from core.storage import postgres as postgres_store, records as record_store
from tests.support_pg import PostgresTestCase
from webui.routes import codex
from webui.runtime import WebUIContext


class CodexBulkMutationTests(PostgresTestCase):
    def setUp(self):
        from core.storage.codex import bulk_mutations

        self.bulk = bulk_mutations
        self.names = ["codex-first.json", "codex-second.json"]
        self.seed(record_store.CODEX_CREDENTIALS, [
            {
                "filename": name, "content": {"email": f"{index}@example.test"},
                "exported_count": 3, "exported_at": "previous",
                "sub2_uploaded_count": 7, "unrelated": "keep",
            }
            for index, name in enumerate(self.names)
        ])
        app = Flask(__name__)
        app.register_blueprint(codex.create_codex_blueprint(WebUIContext(app, logging.getLogger(__name__))))
        self.client = app.test_client()

    def row(self, name):
        return record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", name)

    def capture_sql(self, operation):
        queries = []
        native_execute = Cursor.execute

        def execute(cursor, query, *args, **kwargs):
            queries.append(str(query))
            return native_execute(cursor, query, *args, **kwargs)

        with patch.object(Cursor, "execute", execute):
            result = operation()
        mutations = [query for query in queries if "RETURNING" in query and
                     ("UPDATE " in query or "DELETE " in query)]
        self.assertEqual(len(mutations), 1, queries)
        self.assertIn("ANY(", mutations[0])
        return result

    def test_archive_classifies_missing_duplicate_and_invalid_filenames_in_one_write(self):
        result = self.capture_sql(lambda: self.bulk.archive_many(
            [self.names[1], self.names[0], self.names[1], "codex-missing.json", "../codex-bad.json", None],
            True,
        ))
        self.assertEqual((result.updated_count, result.skipped_count, result.duplicate_count), (2, 3, 1))
        self.assertEqual(
            [(item.key, item.status, item.reason_code) for item in result.items],
            [
                (self.names[1], "updated", None), (self.names[0], "updated", None),
                ("codex-missing.json", "skipped", "not_found"),
                ("../codex-bad.json", "skipped", "invalid_filename"),
                (None, "skipped", "invalid_filename"),
            ],
        )
        first, second = (self.row(name) for name in self.names)
        self.assertTrue(first["archived"])
        self.assertEqual(first["archived_at"], second["archived_at"])
        self.assertEqual(first["unrelated"], "keep")
        self.bulk.archive_many(self.names, False)
        self.assertFalse(self.row(self.names[0])["archived"])
        self.assertIsNone(self.row(self.names[0])["archived_at"])

    def test_export_mark_and_reset_are_atomic_set_writes(self):
        result = self.capture_sql(lambda: self.bulk.mark_exported_many([*self.names, self.names[0]]))
        self.assertEqual((result.updated_count, result.duplicate_count), (2, 1))
        self.assertEqual([self.row(name)["exported_count"] for name in self.names], [4, 4])
        self.assertTrue(self.row(self.names[0])["exported_at"])
        result = self.capture_sql(lambda: self.bulk.reset_exported_many([*self.names, "codex-missing.json"]))
        self.assertEqual((result.updated_count, result.skipped_count), (2, 1))
        for name in self.names:
            row = self.row(name)
            self.assertEqual(row["exported_count"], 0)
            self.assertIsNone(row["exported_at"])
            self.assertEqual(row["sub2_uploaded_count"], 7)

    def test_concurrent_export_marks_do_not_lose_increments(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.bulk.mark_exported_many(self.names), range(8)))
        self.assertEqual([self.row(name)["exported_count"] for name in self.names], [11, 11])

    def test_filename_whitespace_preserves_worker_receipt_keys_and_increments_once(self):
        result = self.bulk.mark_exported_many([f" {self.names[0]} ", self.names[0]])
        self.assertEqual([item.key for item in result.items], [f" {self.names[0]} ", self.names[0]])
        self.assertEqual([item.status for item in result.items], ["updated", "updated"])
        self.assertEqual(self.row(self.names[0])["exported_count"], 4)

    def test_delete_is_one_set_write_and_leaves_legacy_files_alone(self):
        db._CODEX_DIR.mkdir()
        path = db._CODEX_DIR / self.names[0]
        path.write_text('{"legacy":true}', encoding="utf-8")
        result = self.capture_sql(lambda: self.bulk.delete_many(
            [*self.names, self.names[0], "codex-missing.json", "../unsafe.json"],
        ))
        self.assertEqual((result.updated_count, result.skipped_count, result.duplicate_count), (2, 2, 1))
        self.assertEqual([self.row(name) for name in self.names], [None, None])
        self.assertTrue(path.exists())

    def test_supplied_connection_keeps_mutation_in_callers_transaction(self):
        with record_store.transaction() as conn:
            self.bulk.mark_exported_many(self.names, conn=conn)
            with conn.cursor() as cur:
                cur.execute(f"SELECT exported_count FROM {postgres_store.qualified('codex_credentials')} ORDER BY filename")
                self.assertEqual([row["exported_count"] for row in cur.fetchall()], [4, 4])
            conn.rollback()
        self.assertEqual([self.row(name)["exported_count"] for name in self.names], [3, 3])

    def test_single_state_routes_share_collection_mutations(self):
        with (
            patch.object(db, "archive_codex", side_effect=AssertionError("逐条归档")),
            patch.object(db, "reset_codex_exported", side_effect=AssertionError("逐条重置")),
            patch.object(db, "delete_codex_credential", side_effect=AssertionError("逐条删除")),
        ):
            response = self.client.post("/api/codex/archive", json={"filename": self.names[0]})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json["record"]["archived"])
            response = self.client.post("/api/codex/archive", json={"filename": self.names[0], "archived": False})
            self.assertFalse(response.json["record"]["archived"])
            response = self.client.post("/api/codex/reset-export", json={"filename": self.names[0]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.row(self.names[0])["exported_count"], 0)
            response = self.client.post("/api/codex/delete", json={"filename": self.names[0]})
            self.assertEqual(response.status_code, 200)
            response = self.client.post("/api/codex/delete", json={"filename": self.names[0]})
            self.assertEqual(response.status_code, 404)

    def test_bulk_state_routes_accept_commands_without_claiming_completed_mutations(self):
        calls = []

        def submit(operation, targets, parameters, *, idempotency_key, trigger):
            calls.append((operation, targets, parameters, idempotency_key, trigger))
            return {"accepted": True, "task_id": 123, "run_id": 456}

        with patch.object(codex.bulk_mutation_worker, "submit_bulk_mutation", side_effect=submit):
            for path in ("archive-bulk", "delete-bulk", "reset-export-bulk"):
                response = self.client.post(
                    f"/api/codex/{path}", json={"filenames": self.names, "archived": False},
                    headers={"Idempotency-Key": "same-command"},
                )
                self.assertEqual(response.status_code, 202)
                self.assertTrue(response.json["accepted"])
                self.assertEqual(response.json["run_id"], 456)
                self.assertNotIn("updated_count", response.json)
        self.assertEqual(calls, [
            ("codex_archive", self.names, {"archived": False}, "same-command", "manual_bulk"),
            ("codex_delete", self.names, {}, "same-command", "manual_bulk"),
            ("codex_reset_export", self.names, {}, "same-command", "manual_bulk"),
        ])
        self.assertEqual([self.row(name)["exported_count"] for name in self.names], [3, 3])
        self.assertFalse(self.row(self.names[0])["archived"])

    def test_local_downloads_preserve_json_content_and_set_export_mark(self):
        with patch.object(db, "mark_codex_exported", side_effect=AssertionError("逐条导出")):
            response = self.client.get(f"/api/codex/download/{self.names[0]}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {"email": "0@example.test"})
            self.assertIn(self.names[0], response.headers["Content-Disposition"])
            response = self.client.post("/api/codex/download-bulk", json={"filenames": self.names})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["count"], 2)
            self.assertEqual([entry["filename"] for entry in response.json["credentials"]], self.names)
        self.assertEqual([self.row(name)["exported_count"] for name in self.names], [5, 4])

    def test_bulk_download_keeps_content_and_per_file_error_when_credential_disappears(self):
        with patch.object(db, "read_codex_credential", return_value=('{"email":"gone@example.test"}', "codex-gone.json")):
            response = self.client.post("/api/codex/download-bulk", json={"filenames": ["codex-gone.json"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 1)
        self.assertEqual(response.json["errors"][0]["filename"], "codex-gone.json")
        self.assertIn("凭证不存在", response.json["errors"][0]["error"])

    def test_cpa_download_zip_keeps_original_files_and_marks_successes_together(self):
        from core.codex import oauth

        with (
            patch.object(codex, "_feature_unavailable", return_value=None),
            patch.object(oauth, "list_cpa_codex_auth_files", return_value=[]),
            patch.object(oauth, "download_cpa_codex_auth_text",
                         side_effect=lambda **kwargs: ('{"type":"codex"}', kwargs["local_filename"], {})),
            patch.object(db, "mark_codex_exported", side_effect=AssertionError("逐条导出")),
        ):
            response = self.client.post("/api/codex/download-bulk-from-cpa", json={"filenames": self.names})
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(archive.namelist(), [*self.names, "manifest.json"])
            self.assertEqual(json.loads(archive.read("manifest.json"))["count"], 2)
        self.assertEqual([self.row(name)["exported_count"] for name in self.names], [4, 4])
