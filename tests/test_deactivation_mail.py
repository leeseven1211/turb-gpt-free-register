# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import db, deactivation_mail_service
from webui.app import create_app


class DeactivationMailTests(unittest.TestCase):
    def _db_patches(self, root: Path):
        return (
            patch.object(db, "_ACCOUNTS_JSON", root / "accounts.json"),
            patch.object(db, "_LEGACY_ACCOUNTS_JSON", root / "legacy_accounts.json"),
            patch.object(db, "_ACCOUNTS_TXT", root / "accounts.txt"),
            patch.object(db, "_TOKENS_TXT", root / "tokens.txt"),
            patch.object(db, "_VIEWER_HTML", root / "viewer.html"),
        )

    def test_detected_mail_is_durable_and_empty_rescan_does_not_clear_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "accounts.json").write_text(
                '[{"id":1,"email":"a@test.com","email_source":"email_butler"}]', encoding="utf-8"
            )
            patches = self._db_patches(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                db.update_account_deactivation_mail(1, {
                    "status": "success", "detected": True, "subject": "Deactivated",
                    "sender": "noreply@openai.com", "received_at": "2026-08-06T09:00:00Z",
                })
                db.update_account_deactivation_mail(1, {"status": "success", "detected": False})
                row = db.get_account(1)
                self.assertTrue(row["deactivation_mail_detected"])
                self.assertEqual(row["deactivation_mail_subject"], "Deactivated")

    def test_manual_endpoint_queues_without_access_token(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        with patch.object(deactivation_mail_service, "enqueue", return_value={"accepted": True, "account_id": 7}), patch.object(
            deactivation_mail_service, "queue_settings", return_value={"enabled": True}
        ):
            response = client.post("/api/accounts/7/check-deactivation-mail")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.get_json()["ok"])

    def test_account_management_ui_has_column_without_separate_menu(self):
        html = (Path(__file__).resolve().parents[1] / "webui" / "templates" / "index.html").read_text("utf-8")
        self.assertIn('<th class="col-risk-mail">封号邮件</th>', html)
        self.assertIn("data-deactivation-mail-check", html)
        self.assertNotIn('data-tab="email-butler"', html)


if __name__ == "__main__":
    unittest.main()
