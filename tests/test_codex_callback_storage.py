# -*- coding: utf-8 -*-
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import codex_oauth, postgres_store, record_store
from core.storage import codex as codex_store
from tests.support_pg import PostgresTestCase


class CodexCallbackStorageTests(PostgresTestCase):
    def setUp(self):
        record_store.init()

    def test_callback_receipts_are_persisted_without_creating_files(self):
        for source in ("cpa", "sub2"):
            with self.subTest(source=source), TemporaryDirectory() as directory, ExitStack() as stack:
                root = Path(directory)
                stack.enter_context(patch.object(codex_oauth, "_PROJECT_ROOT", root))
                stack.enter_context(patch.object(codex_oauth._cfg, "CPA_SAVE_CALLBACK_RECEIPT", True))
                stack.enter_context(patch.object(codex_oauth, "_cpa_management_origin", return_value="https://cpa.example.test"))
                stack.enter_context(patch.object(codex_oauth, "_sub2_codex_base", return_value="https://sub2.example.test"))
                save = getattr(codex_oauth, f"_save_{source}_local_record")
                path = save(
                    email=f"{source}@example.test",
                    callback_url="http://localhost/callback?code=fixture-code",
                    auth_url="https://auth.example.test/authorize",
                    state="fixture-state",
                    submit_payload={"ok": True, "message": "已接收", "detail": {"receipt_id": 7}},
                )
                self.assertIsInstance(path, Path)
                self.assertFalse(path.exists(), "回执仅保存到 PostgreSQL，不应生成本地文件")
                self.assertEqual(list(root.iterdir()), [])
                postgres_store.reset_cache()
                stored = codex_store.read_codex_callback_receipt(path.name)
                self.assertEqual(stored["source"], source)
                self.assertEqual(stored["email"], f"{source}@example.test")
                self.assertEqual(stored["content"]["state"], "fixture-state")
                self.assertEqual(stored["content"]["callback_url"], "http://localhost/callback?code=fixture-code")
                self.assertEqual(stored["content"][f"{source}_submit_response"]["detail"], {"receipt_id": 7})
                self.assertEqual(record_store.count_rows(record_store.CODEX_CREDENTIALS), 0)

    def test_repeated_receipt_updates_one_database_row_and_keeps_creation_time(self):
        filename = "codex-repeat@example.test-cpa-callback.json"
        receipt_id = codex_store.save_codex_callback_receipt(
            filename, {"email": "repeat@example.test", "state": "first"}, source="cpa"
        )
        record_store.patch_row(record_store.CODEX_CALLBACK_RECEIPTS, receipt_id, {
            "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
        })
        repeated_id = codex_store.save_codex_callback_receipt(
            filename, {"email": "repeat@example.test", "state": "second", "details": {"accepted": True}}, source="cpa"
        )
        postgres_store.reset_cache()
        stored = codex_store.read_codex_callback_receipt(filename)
        self.assertEqual(receipt_id, repeated_id)
        self.assertEqual(record_store.count_rows(record_store.CODEX_CALLBACK_RECEIPTS), 1)
        self.assertEqual(stored["content"], {
            "email": "repeat@example.test", "state": "second", "details": {"accepted": True},
        })
        self.assertEqual(stored["created_at"], "2026-01-01T00:00:00")
        self.assertNotEqual(stored["updated_at"], "2026-01-01T00:00:00")

    def test_full_auth_responses_are_credentials_instead_of_receipts(self):
        for source in ("cpa", "sub2"):
            with self.subTest(source=source), TemporaryDirectory() as directory, ExitStack() as stack:
                stack.enter_context(patch.object(codex_oauth, "_PROJECT_ROOT", Path(directory)))
                auth = {
                    "type": "codex", "email": f"auth-{source}@example.test",
                    "account_id": f"account-{source}", "access_token": "fixture-access", "refresh_token": "fixture-refresh",
                }
                path = getattr(codex_oauth, f"_save_{source}_local_record")(
                    email=f"auth-{source}@example.test", callback_url="http://localhost/callback",
                    auth_url="https://auth.example.test/authorize", state="fixture-state",
                    submit_payload={"auth_json": auth},
                )
                stored = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", path.name)
                self.assertEqual(stored["content"], auth)
                self.assertEqual(record_store.count_rows(record_store.CODEX_CALLBACK_RECEIPTS), 0)

    def test_disabling_receipts_preserves_no_storage_behavior(self):
        with TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            stack.enter_context(patch.object(codex_oauth, "_PROJECT_ROOT", root))
            stack.enter_context(patch.object(codex_oauth._cfg, "CPA_SAVE_CALLBACK_RECEIPT", False))
            for source in ("cpa", "sub2"):
                with self.subTest(source=source):
                    path = getattr(codex_oauth, f"_save_{source}_local_record")(
                        email="disabled@example.test", callback_url="http://localhost/callback",
                        auth_url="https://auth.example.test/authorize", state="fixture-state",
                        submit_payload={"ok": True},
                    )
                    self.assertIsNone(path)
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(record_store.count_rows(record_store.CODEX_CALLBACK_RECEIPTS), 0)
            self.assertEqual(record_store.count_rows(record_store.CODEX_CREDENTIALS), 0)

    def test_callback_acceptance_still_requires_remote_credential_confirmation(self):
        for source in ("cpa", "sub2"):
            with self.subTest(source=source), TemporaryDirectory() as directory, ExitStack() as stack:
                stack.enter_context(patch.object(codex_oauth, "_PROJECT_ROOT", Path(directory)))
                stack.enter_context(patch.object(codex_oauth._cfg, "CPA_SAVE_CALLBACK_RECEIPT", True))
                stack.enter_context(patch.object(codex_oauth, "_cpa_management_origin", return_value="https://cpa.example.test"))
                stack.enter_context(patch.object(codex_oauth, "_sub2_codex_base", return_value="https://sub2.example.test"))
                result = codex_oauth._remote_callback_result(
                    source=source, email=f"waiting-{source}@example.test",
                    callback_url="http://localhost/callback", auth_url="https://auth.example.test/authorize",
                    state="fixture-state", submit_payload={"ok": True, "message": "已接收"},
                )
                self.assertEqual(result["status"], "attention_required")
                self.assertFalse(result["ok"])
                self.assertTrue(result["callback_submitted"])
                self.assertFalse(result["credential_confirmed"])
                self.assertIsNone(result.get("file_path"))
                self.assertIsNotNone(codex_store.read_codex_callback_receipt(Path(result["receipt_path"]).name))
                self.assertEqual(record_store.count_rows(record_store.CODEX_CREDENTIALS), 0)

    def test_missing_receipt_is_not_loaded_from_a_legacy_file(self):
        with TemporaryDirectory() as directory, patch.object(codex_oauth, "_PROJECT_ROOT", Path(directory)):
            path = Path(directory) / "codex-missing@example.test-cpa-callback.json"
            path.write_text('{"email":"missing@example.test"}', encoding="utf-8")
            self.assertIsNone(codex_store.read_codex_callback_receipt(path.name))

    def test_receipt_repository_rejects_invalid_inputs(self):
        for filename, content, source in (
            ("../codex-invalid.json", {}, "cpa"),
            ("codex-invalid.json", {}, "unknown"),
            ("codex-invalid.json", [], "cpa"),
        ):
            with self.subTest(filename=filename, source=source), self.assertRaises(ValueError):
                codex_store.save_codex_callback_receipt(filename, content, source=source)
        self.assertEqual(record_store.count_rows(record_store.CODEX_CALLBACK_RECEIPTS), 0)
