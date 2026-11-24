"""按需秘密读取与导出使用集合查询，秘密仅出现在授权响应中。"""
from __future__ import annotations

import io
import json
import zipfile
from unittest.mock import patch

from psycopg import Cursor

from core.storage import records
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountBulkReadTests(PostgresTestCase):
    def setUp(self):
        self.client = create_app(auth_code="bulk-read-auth").test_client()
        self.headers = {"X-Auth-Code": "bulk-read-auth"}

    def accounts(self):
        return self.seed(records.ACCOUNTS, [
            {"email": "first@example.test", "access_token": "synthetic-first",
             "chatgpt_session": '{"accessToken":"stored-first","extra":{"keep":true}}',
             "extra_json": '{"account_password":"synthetic-password"}'},
            {"email": "second@example.test", "access_token": "",
             "chatgpt_session": '{"accessToken":"stored-second"}'},
        ])

    def request_queries(self, path, body):
        queries = []
        execute = Cursor.execute
        def capture(cur, query, *args, **kwargs):
            queries.append(str(query))
            return execute(cur, query, *args, **kwargs)
        with patch.object(Cursor, "execute", capture):
            response = self.client.post(path, json=body, headers=self.headers)
        return response, [query for query in queries if query.lstrip().upper().startswith("SELECT")
                          and "registered_accounts" in query]

    def test_secret_bulk_reads_accounts_and_saved_sessions_in_one_select(self):
        ids = self.accounts()
        response, queries = self.request_queries("/api/accounts/secret-bulk",
            {"account_ids": [ids[1], ids[0], ids[1], 9999], "field": "chatgpt_session"})
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(queries))
        result = response.get_json()
        self.assertEqual(ids[::-1], [item["id"] for item in result["values"]])
        self.assertEqual("stored-first", json.loads(result["values"][1]["value"])["accessToken"])
        self.assertEqual("账号不存在", result["skipped"][0]["reason"])
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_secret_fields_and_auth_are_unchanged(self):
        ids = self.accounts()
        for field, expected in (("access_token", "synthetic-first"),
                                ("account_password", "synthetic-password"),
                                ("account_password_line", "first@example.test----synthetic-password")):
            with self.subTest(field=field):
                response = self.client.post("/api/accounts/secret-bulk",
                    json={"account_ids": ids, "field": field}, headers=self.headers)
                self.assertEqual(expected, response.get_json()["values"][0]["value"])
        self.assertEqual(400, self.client.post("/api/accounts/secret-bulk",
            json={"account_ids": ids, "field": "private_dump"}, headers=self.headers).status_code)
        self.assertEqual(401, self.client.post("/api/accounts/secret-bulk",
            json={"account_ids": ids, "field": "email"}).status_code)

    def test_session_zip_queries_once_and_bigint_is_exact(self):
        ids = self.accounts()
        large = 9007199254740993
        records.insert_row(records.ACCOUNTS, {"id": large, "email": "large@example.test",
                                              "chatgpt_session": '{"accessToken":"large-session"}'})
        # 显式ID由数据库identity的独立测试记录保存，不经JS浮点数转换。
        with records.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {records._qualified(records.ACCOUNTS)} SET id=%s WHERE email=%s",
                        (large, "large@example.test"))
        response, queries = self.request_queries("/api/accounts/download-session-bulk",
            {"account_ids": [str(large), ids[0], str(large), 9999]})
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(queries))
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual([str(large), ids[0]], [item["id"] for item in manifest["files"]])
            self.assertEqual(1, manifest["skipped_count"])

    def test_cpa_export_prefetches_locals_and_updates_only_successes_once(self):
        from core.codex import oauth
        from core.storage.accounts import bulk_reads
        from core.storage.codex import bulk_mutations
        ids = self.accounts()
        names = ["codex-first.json", "codex-second.json"]
        self.seed(records.CODEX_CREDENTIALS, [
            {"filename": name, "email": email, "plan": "free", "exported_count": 0}
            for name, email in zip(names, ["first@example.test", "second@example.test"])
        ])
        with patch("webui.routes.accounts._feature_unavailable", return_value=None), \
                patch.object(oauth, "list_cpa_codex_auth_files", return_value=[{"name": name} for name in names]), \
                patch.object(oauth, "find_cpa_codex_auth_file", side_effect=lambda **kw: {"name": kw["local_filename"]}), \
                patch.object(oauth, "download_cpa_codex_auth_text", side_effect=[
                    ('{"type":"codex"}', names[0], {}), RuntimeError("synthetic-download-failure")]), \
                patch.object(bulk_reads, "read_accounts", wraps=bulk_reads.read_accounts) as read, \
                patch.object(bulk_mutations, "mark_exported_many", wraps=bulk_mutations.mark_exported_many) as mark:
            response = self.client.post("/api/accounts/download-cpa-bulk",
                json={"account_ids": ids}, headers=self.headers)
        self.assertEqual(200, response.status_code)
        read.assert_called_once()
        mark.assert_called_once_with([names[0]])
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(1, manifest["count"])
            self.assertEqual(1, len(manifest["errors"]))
        stored = records.list_rows(records.CODEX_CREDENTIALS, order_by="id")
        self.assertEqual([1, 0], [item["exported_count"] for item in stored])

    def test_local_codex_lookup_selects_latest_unarchived_match_only(self):
        from core.storage.accounts import bulk_reads
        self.seed(records.CODEX_CREDENTIALS, [
            {"filename": "codex-old.json", "email": "First@example.test", "updated_at": "2026-01-01"},
            {"filename": "codex-new.json", "email": " first@example.test ", "updated_at": "2026-02-01"},
            {"filename": "codex-archived.json", "email": "first@example.test",
             "updated_at": "2026-03-01", "archived": True},
            {"filename": "codex-other.json", "email": "other@example.test", "updated_at": "2026-04-01"},
        ])
        self.assertEqual({"first@example.test": "codex-new.json"},
                         bulk_reads.local_codex_filenames(["FIRST@example.test"]))
