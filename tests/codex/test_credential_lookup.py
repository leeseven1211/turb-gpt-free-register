"""凭证定位在全库增长后仍只读取明确目标，保持原身份/归档口径。"""
from unittest.mock import patch

from core import db
from core.storage import codex, records
from core.codex import token_refresh_service
from core.integrations.sub2api import manual_upload, client
from core.operations import task_gateway
from tests.support_pg import PostgresTestCase


class CredentialLookupTests(PostgresTestCase):
    def setUp(self):
        records.init()
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": "lookup@example.test", "codex_status": "success"})
        codex.save_codex_credential_record("codex-lookup-free.json", {
            "email": "lookup@example.test", "refresh_token": "synthetic-refresh", "access_token": "synthetic-access"})

    def test_single_and_set_lookup_match_public_metadata_including_archived(self):
        codex.archive_codex("codex-lookup-free.json")
        expected = codex.list_codex_accounts(archived="all")[0]
        with patch.object(codex, "list_codex_accounts", side_effect=AssertionError("不应读取全库")):
            actual = codex.get_codex_account("codex-lookup-free.json")
            selected = codex.get_codex_accounts_by_filenames(["codex-lookup-free.json", "codex-missing.json"])
        self.assertEqual(expected, actual)
        self.assertEqual({"codex-lookup-free.json": expected}, selected)
        self.assertTrue(actual["archived"])

    def test_email_lookup_preserves_latest_credential_order_and_case(self):
        codex.save_codex_credential_record("codex-lookup-new.json", {
            "email": "LOOKUP@EXAMPLE.TEST", "refresh_token": "synthetic-new"})
        expected = next(row for row in codex.list_codex_accounts(archived="all")
                        if row["email"].strip().casefold() == "lookup@example.test")
        self.assertEqual(expected, codex.get_codex_account_by_email("  Lookup@example.test  "))

    def test_manual_account_upload_never_reads_all_credentials(self):
        account = db.get_account(self.account_id)
        with patch.object(db, "list_codex_accounts", side_effect=AssertionError("不应读取全库")), patch.object(
            client, "configured_backend_identity", return_value="synthetic-backend"
        ), patch.object(task_gateway, "notify_dispatch"):
            queued = manual_upload.queue_account(account)
        self.assertTrue(queued["accepted"])

    def test_refresh_lookup_keeps_reauthorization_rejection_without_all_rows(self):
        db.mark_codex_oauth_refresh("codex-lookup-free.json", error="invalid_grant")
        with patch.object(codex, "list_codex_accounts", side_effect=AssertionError("不应读取全库")):
            result = token_refresh_service.enqueue_refresh("codex-lookup-free.json")
        self.assertFalse(result["accepted"])
        self.assertEqual("reauth_required", result["error_code"])
