# -*- coding: utf-8 -*-
import json
import os
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import psycopg
from psycopg_pool import PoolTimeout

from core import db, postgres_store, record_store
from tests.support_pg import PostgresTestCase, temporary_schema_name
from tools import migrate_codex_files as migration


class CodexFileMigrationTests(PostgresTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name, content, *, legacy_core=False):
        base = self.root / "core" if legacy_core else self.root
        directory = base / "codex_accounts"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(json.dumps(content), encoding="utf-8")
        return base

    def credential(self, email="migrated@example.test"):
        return {"type": "codex", "email": email, "access_token": "old-access"}

    def test_both_locations_and_state_migrate_without_overwriting_existing_rows(self):
        filename = "codex-migrated@example.test-free.json"
        base = self.write(filename, self.credential(), legacy_core=True)
        (base / "codex_导出状态.json").write_text(json.dumps({
            filename: {"exported_count": 4, "sub2_uploaded_count": 2, "archived": True},
            "codex-orphan@example.test-free.json": {"exported_count": 7},
        }), encoding="utf-8")
        other = "codex-second@example.test-free.json"
        self.write(other, self.credential("second@example.test"))

        preview = migration.migrate(self.root)
        self.assertEqual(2, preview["missing_credentials"])
        self.assertEqual(1, preview["orphan_states"])
        self.assertEqual(0, preview["inserted_credentials"])

        result = migration.migrate(self.root, apply=True)
        self.assertEqual(2, result["inserted_credentials"])
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertEqual(4, row["exported_count"])
        self.assertEqual(2, row["sub2_uploaded_count"])
        self.assertTrue(row["archived"])
        record_store.patch_row(record_store.CODEX_CREDENTIALS, row["id"], {
            "content": {"type": "codex", "email": "migrated@example.test", "access_token": "new-access"},
            "exported_count": 0, "sub2_uploaded_count": 0, "archived": False,
        })
        before = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        repeated = migration.migrate(self.root, apply=True)
        self.assertEqual(0, repeated["inserted_credentials"])
        after = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertEqual(before, after)

    def test_callback_receipts_use_separate_table(self):
        for source in ("cpa", "sub2"):
            filename = f"codex-receipt@example.test-{source}-callback.json"
            content = {"type": f"codex_{source}_callback", "email": "receipt@example.test", "state": "submitted"}
            self.write(filename, content)

        result = migration.migrate(self.root, apply=True)
        self.assertEqual(2, result["inserted_receipts"])
        self.assertEqual(0, record_store.count_rows(record_store.CODEX_CREDENTIALS))
        rows = record_store.list_rows(record_store.CODEX_CALLBACK_RECEIPTS)
        self.assertEqual({"cpa", "sub2"}, {row["source"] for row in rows})
        self.assertTrue(all(row["content"]["state"] == "submitted" for row in rows))

    def test_conflicting_new_snapshots_abort_before_any_insert(self):
        filename = "codex-migrated@example.test-free.json"
        self.write(filename, self.credential())
        self.write(filename, {**self.credential(), "access_token": "different"}, legacy_core=True)
        self.write("codex-valid@example.test-free.json", self.credential("valid@example.test"))

        result = migration.migrate(self.root, apply=True)
        self.assertEqual(1, result["errors"]["conflicting_duplicates"])
        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(0, record_store.count_rows(record_store.CODEX_CREDENTIALS))

    def test_existing_database_record_ignores_different_old_snapshots(self):
        record_store.init()
        filename = "codex-migrated@example.test-free.json"
        db.save_codex_credential_record(filename, {**self.credential(), "access_token": "current"})
        self.write(filename, self.credential())
        self.write(filename, {**self.credential(), "access_token": "different"}, legacy_core=True)
        before = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)

        result = migration.migrate(self.root, apply=True)

        self.assertEqual({}, result["errors"])
        self.assertEqual(1, result["existing_credentials"])
        self.assertEqual(before, record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename))

    def test_existing_account_identity_skips_renamed_old_credentials(self):
        filename = "codex-Current@example.test-plus.json"
        db.save_codex_credential_record(filename, {
            **self.credential("Current@example.test"), "account_id": "acct-renamed", "access_token": "current-access",
        })
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        record_store.patch_row(record_store.CODEX_CREDENTIALS, row["id"], {"exported_count": 0, "archived": False})
        self.write("codex-old@example.test-free.json", {
            **self.credential("old@example.test"), "account_id": "acct-renamed",
        })
        before = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)

        preview = migration.migrate(self.root)
        result = migration.migrate(self.root, apply=True)

        self.assertEqual(1, preview["existing_identity_credentials"])
        self.assertEqual(0, preview["missing_credentials"])
        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(1, record_store.count_rows(record_store.CODEX_CREDENTIALS))
        self.assertEqual(before, record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename))

    def test_existing_email_plan_identity_ignores_case_without_account_id(self):
        filename = "codex-User@example.test-free.json"
        db.save_codex_credential_record(filename, {**self.credential("User@example.test"), "access_token": "current-access"})
        self.write("codex-user@example.test-free.json", self.credential("user@example.test"))
        before = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)

        result = migration.migrate(self.root, apply=True)

        self.assertEqual(1, result["existing_identity_credentials"])
        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(1, record_store.count_rows(record_store.CODEX_CREDENTIALS))
        self.assertEqual(before, record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename))

    def test_conflicting_new_filenames_for_same_identity_abort_all_imports(self):
        self.write("codex-old@example.test-free.json", {**self.credential("old@example.test"), "account_id": "acct-duplicate"})
        self.write("codex-new@example.test-plus.json", {**self.credential("new@example.test"), "account_id": "acct-duplicate"})
        self.write("codex-User@example.test-free.json", self.credential("User@example.test"))
        self.write("codex-case-copy@example.test-free.json", self.credential("user@example.test"))
        self.write("codex-unrelated@example.test-free.json", self.credential("unrelated@example.test"))

        result = migration.migrate(self.root, apply=True)

        self.assertEqual(2, result["errors"]["conflicting_identity"])
        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(0, record_store.count_rows(record_store.CODEX_CREDENTIALS))

    def test_apply_rechecks_identity_after_concurrent_credential_save(self):
        filename = "codex-new@example.test-plus.json"
        content = {**self.credential("new@example.test"), "account_id": "acct-concurrent", "access_token": "current-access"}
        self.write("codex-old@example.test-free.json", {**self.credential("old@example.test"), "account_id": "acct-concurrent"})
        original_transaction = record_store.transaction
        injected = False

        def save_before_transaction():
            nonlocal injected
            if not injected:
                injected = True
                db.save_codex_credential_record(filename, content)
            return original_transaction()

        with patch.object(record_store, "transaction", side_effect=save_before_transaction):
            result = migration.migrate(self.root, apply=True)

        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(1, result["existing_identity_credentials"])
        self.assertEqual(1, record_store.count_rows(record_store.CODEX_CREDENTIALS))
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertEqual("current-access", row["content"]["access_token"])

    def test_invalid_files_abort_without_partial_import(self):
        self.write("codex-valid@example.test-free.json", self.credential("valid@example.test"))
        self.write("codex-empty@example.test-free.json", {"type": "codex", "email": "empty@example.test"})
        self.write("codex-null@example.test-free.json", None)
        self.write("codex-invalid-type@example.test-free.json", {"type": {}, "access_token": "invalid"})
        directory = self.root / "codex_accounts"
        (directory / "codex-broken@example.test-free.json").write_text("{", encoding="utf-8")

        result = migration.migrate(self.root, apply=True)

        self.assertEqual(3, result["errors"]["invalid_content"])
        self.assertEqual(1, result["errors"]["invalid_json"])
        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(0, record_store.count_rows(record_store.CODEX_CREDENTIALS))

    def test_invalid_state_aborts_without_partial_import(self):
        filename = "codex-migrated@example.test-free.json"
        self.write(filename, self.credential())
        (self.root / "codex_导出状态.json").write_text(json.dumps({filename: {"exported_count": -2}}), encoding="utf-8")

        result = migration.migrate(self.root, apply=True)

        self.assertEqual(1, result["errors"]["invalid_state"])
        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(0, record_store.count_rows(record_store.CODEX_CREDENTIALS))

    def test_invalid_credential_metadata_aborts_before_any_insert(self):
        self.write("codex-valid@example.test-free.json", self.credential("valid@example.test"))
        self.write("codex-invalid@example.test-free.json", {
            **self.credential("invalid@example.test"),
            "expired": "0001-01-01T00:00:00+01:00",
        })

        result = migration.migrate(self.root, apply=True)

        self.assertEqual(1, result["errors"]["invalid_content"])
        self.assertEqual(0, result["inserted_credentials"])
        self.assertEqual(0, record_store.count_rows(record_store.CODEX_CREDENTIALS))

    def test_dry_run_does_not_create_business_tables(self):
        self.write("codex-migrated@example.test-free.json", self.credential())
        empty_schema = temporary_schema_name("codex_readonly")
        with (
            patch.dict(os.environ, {"TURB_DB_SCHEMA": empty_schema}),
            patch.object(record_store, "init", side_effect=AssertionError("只读对账不得建表")),
        ):
            result = migration.migrate(self.root)
        self.assertEqual(1, result["missing_credentials"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (f"{empty_schema}.codex_credentials",))
            self.assertIsNone(cur.fetchone()[0])


class CodexFileMigrationCliTests(unittest.TestCase):
    def test_connection_and_unexpected_errors_report_only_classification(self):
        cases = (
            (RuntimeError("DATABASE_URL 未配置"), "database_not_configured"),
            (PoolTimeout("private-connection-information"), "database_PoolTimeout"),
            (psycopg.OperationalError("private-connection-information"), "database_OperationalError"),
            (LookupError("private-connection-information"), "operation_LookupError"),
        )
        for error, category in cases:
            with self.subTest(category=category), patch.object(migration, "migrate", side_effect=error):
                output = io.StringIO()
                with redirect_stdout(output):
                    code = migration.main(["--source-root", "/unused", "--dry-run"])
                self.assertEqual(2, code)
                self.assertEqual({"errors": {category: 1}}, json.loads(output.getvalue()))
                self.assertNotIn("private-connection-information", output.getvalue())
