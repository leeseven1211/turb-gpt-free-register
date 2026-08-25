# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from unittest.mock import patch

from core import codex_oauth
from core.operation_runtime import CancellationToken, OperationCancelled


class CodexCredentialSemanticsTests(unittest.TestCase):
    def test_callback_receipt_is_not_reported_as_saved_credential(self):
        with patch.object(
            codex_oauth, "_save_cpa_local_record",
            return_value=Path("/tmp/codex-user-cpa-callback.json"),
        ):
            result = codex_oauth._remote_callback_result(
                source="cpa",
                email="user@example.com",
                callback_url="http://localhost/callback",
                auth_url="https://auth.example",
                state="state",
                submit_payload={"message": "accepted"},
            )
        self.assertFalse(result["ok"])
        self.assertEqual("attention_required", result["status"])
        self.assertFalse(result["credential_confirmed"])
        self.assertIsNone(result["file_path"])
        self.assertTrue(result["receipt_path"].endswith("-cpa-callback.json"))

    def test_embedded_auth_json_is_confirmed_success(self):
        with patch.object(
            codex_oauth, "_save_cpa_local_record",
            return_value=Path("/tmp/codex-user-free.json"),
        ):
            result = codex_oauth._remote_callback_result(
                source="cpa",
                email="user@example.com",
                callback_url="http://localhost/callback",
                auth_url="https://auth.example",
                state="state",
                submit_payload={"auth_json": {"type": "codex", "access_token": "secret"}},
            )
        self.assertTrue(result["ok"])
        self.assertEqual("success", result["status"])
        self.assertTrue(result["credential_confirmed"])
        self.assertTrue(result["file_path"].endswith("-free.json"))
        self.assertIsNone(result["receipt_path"])

    def test_cpa_reconciliation_confirms_new_remote_credential(self):
        confirmed_path = Path("/tmp/codex-user-free.json")
        with (
            patch.object(
                codex_oauth, "_save_cpa_local_record",
                return_value=Path("/tmp/codex-user-cpa-callback.json"),
            ),
            patch.object(
                codex_oauth, "_confirm_cpa_credential_after_callback",
                return_value=confirmed_path,
            ) as confirm,
        ):
            result = codex_oauth._remote_callback_result(
                source="cpa",
                email="user@example.com",
                callback_url="http://localhost/callback",
                auth_url="https://auth.example",
                state="state",
                submit_payload={"message": "accepted"},
                cpa_baseline={"captured": True, "fingerprint": "old"},
            )
        confirm.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual("success", result["status"])
        self.assertTrue(result["credential_confirmed"])
        self.assertEqual(str(confirmed_path), result["file_path"])
        self.assertIsNone(result["receipt_path"])


class CancellationTokenTests(unittest.TestCase):
    def test_cancellation_is_cooperative_and_scoped_to_run(self):
        requested = {12: False}
        token = CancellationToken(12, "token-12", lambda run_id, _token: requested[run_id], poll_interval=0)
        token.checkpoint()
        requested[12] = True
        with self.assertRaises(OperationCancelled):
            token.checkpoint()


if __name__ == "__main__":
    unittest.main()
