"""Codex 批量下载集合读取素材，凭据只进入明确的下载响应。"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from unittest.mock import patch

from flask import Flask
from psycopg import Cursor

from core import db
from core.storage import records
from tests.support_pg import PostgresTestCase
from webui.routes import codex
from webui.runtime import WebUIContext


class CodexBulkReadTests(PostgresTestCase):
    def setUp(self):
        self.names = ["codex-first.json", "codex-second.json"]
        self.seed(records.CODEX_CREDENTIALS, [
            {"filename": name, "email": f"{index}@example.test",
             "content": {"email": f"{index}@example.test", "access_token": f"synthetic-{index}"},
             "exported_count": 0, "archived": index == 1}
            for index, name in enumerate(self.names)
        ])
        app = Flask(__name__)
        app.register_blueprint(codex.create_codex_blueprint(WebUIContext(app, logging.getLogger(__name__))))
        self.client = app.test_client()

    def request_reads(self, path, filenames):
        queries = []
        original = Cursor.execute

        def capture(cursor, query, *args, **kwargs):
            text = str(query)
            if text.lstrip().upper().startswith("SELECT") and "codex_credentials" in text:
                queries.append(text)
            return original(cursor, query, *args, **kwargs)

        with patch.object(Cursor, "execute", capture):
            response = self.client.post(path, json={"filenames": filenames})
        return response, queries

    def test_local_bulk_reads_once_and_preserves_order_duplicates_and_partial_errors(self):
        records.insert_row(records.CODEX_CREDENTIALS, {
            "filename": "codex-corrupt.json", "content": ["invalid-json-shape"],
        })
        response, queries = self.request_reads("/api/codex/download-bulk", [
            self.names[1], f" {self.names[0]} ", self.names[1],
            "codex-missing.json", "../codex-first.json", "codex-corrupt.json", 7,
        ])
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(queries), "本地批量下载不得逐文件读取数据库")
        result = response.get_json()
        self.assertEqual(3, result["count"])
        self.assertEqual([self.names[1], self.names[0], self.names[1]],
                         [item["filename"] for item in result["credentials"]])
        self.assertEqual("synthetic-1", result["credentials"][0]["data"]["access_token"])
        self.assertEqual(["codex-missing.json", "../codex-first.json", "codex-corrupt.json", "7"],
                         [item["filename"] for item in result["errors"]])
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        stored = records.list_rows(records.CODEX_CREDENTIALS, where="filename=ANY(%s)",
                                   params=(self.names,), order_by="filename")
        self.assertEqual([1, 1], [row["exported_count"] for row in stored])

    def test_cpa_bulk_prefetches_once_and_marks_only_successful_downloads(self):
        from core.codex import oauth
        from core.codex.cpa_download import CpaDownloadError

        with (
            patch.object(codex, "_feature_unavailable", return_value=None),
            patch.object(oauth, "list_cpa_codex_auth_files", return_value=[]),
            patch.object(oauth, "download_cpa_codex_auth_text",
                         side_effect=[('{"type":"codex","kept":"original"}', "remote-first.json", {}),
                                      CpaDownloadError("cpa_timeout", "CPA 请求超时", "auth_file_download")]),
        ):
            response, queries = self.request_reads("/api/codex/download-bulk-from-cpa", self.names)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(queries), "CPA 打包本地素材也必须集合读取")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(["remote-first.json", "manifest.json"], archive.namelist())
            self.assertEqual("original", json.loads(archive.read("remote-first.json"))["kept"])
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(1, manifest["count"])
            self.assertEqual(self.names[1], manifest["errors"][0]["filename"])
        stored = records.list_rows(records.CODEX_CREDENTIALS, order_by="filename")
        self.assertEqual([1, 0], [row["exported_count"] for row in stored])

    def test_missing_database_credential_does_not_read_a_legacy_file(self):
        name = "codex-only-legacy.json"
        db._CODEX_DIR.mkdir()
        (db._CODEX_DIR / name).write_text('{"access_token":"legacy-file-ignored"}', encoding="utf-8")
        response, queries = self.request_reads("/api/codex/download-bulk", [name])
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(queries))
        self.assertEqual(0, response.get_json()["count"])
        self.assertIn("凭证不存在", response.get_json()["errors"][0]["error"])
        self.assertNotIn("legacy-file-ignored", response.get_data(as_text=True))
