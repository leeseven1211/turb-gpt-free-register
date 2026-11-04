"""协议凭据早存与服务端下一步分派的离线故障注入。"""
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from core.storage import records as record_store
from core.storage.operations import store as operation
from core.storage import registration
from tests.support_pg import PostgresTestCase




class ProtocolPrivateCredentialStorageTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()
        self.email = "private-offline@example.test"
        self.attempt = registration.create_attempt(self.email)
        self.run = registration.start_run(self.attempt["id"], initial_status="running", execution_id="offline-current")

    def _save(self, state, **changes):
        kwargs = {"email": self.email, "password": "OfflinePassword!123", "state": state,
                  "run_id": self.run["id"], "execution_id": "offline-current"}
        kwargs.update(changes)
        return registration.save_password_checkpoint(self.attempt["id"], **kwargs)

    def test_prepared_is_private_and_does_not_create_registered_account(self):
        self._save("prepared")
        self.assertIsNone(record_store.get_row_by(record_store.ACCOUNTS, "email", self.email))
        self.assertNotIn("private_context", registration.get_attempt(self.attempt["id"]))
        self.assertNotIn("OfflinePassword!123", str(registration.list_attempts()))
        self.assertNotIn("OfflinePassword!123", str(registration.events(self.attempt["id"])))
        self.assertNotIn("private_context", operation._row({"private_context": {"password": "hidden"}}))
        self.assertEqual(registration.get_private_resume_context(self.attempt["id"], email=self.email)["password_state"], "prepared")

    def test_worker_and_original_password_guard(self):
        self._save("prepared")
        for changes in ({"execution_id": "offline-stale"}, {"email": "other@example.test"}, {"password": "Replacement!123"}):
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                self._save("started", **changes)

    def test_confirmed_account_and_totp_pending_do_not_project_enabled(self):
        pool_id = record_store.insert_row(record_store.OUTLOOK_POOL, {"email": self.email})
        self._save("started")
        saved = self._save("confirmed", account={"email_source": "generic_api"})
        self.assertIsNotNone(saved["account_id"])
        registration.persist_core_account(self.attempt["id"], access_token="offline-token", account={"email": self.email},
            run_id=self.run["id"], execution_id="offline-current")
        registration.save_totp_checkpoint(self.attempt["id"], email=self.email, secret="offline-secret", confirmed=False,
            run_id=self.run["id"], execution_id="offline-current")
        account = record_store.get_row_by(record_store.ACCOUNTS, "email", self.email)
        self.assertFalse(account.get("totp_secret"))
        self.assertFalse(record_store.get_row(record_store.OUTLOOK_POOL, pool_id).get("totp_secret"))
        extra = json.loads(account["extra_json"]) if isinstance(account["extra_json"], str) else account["extra_json"]
        self.assertTrue(extra["totp_setup_pending"])
        self.assertEqual(extra["twofa"]["status"], "pending")
        registration.save_totp_checkpoint(self.attempt["id"], email=self.email, secret="offline-secret", confirmed=True,
            run_id=self.run["id"], execution_id="offline-current")
        account = record_store.get_row_by(record_store.ACCOUNTS, "email", self.email)
        self.assertEqual(account["totp_secret"], "offline-secret")
        self.assertEqual(record_store.get_row(record_store.OUTLOOK_POOL, pool_id)["totp_secret"], "offline-secret")

    def test_unknown_without_account_recovers_same_attempt_core_and_session(self):
        self._save("started")
        registration.mark_request_unknown(self.attempt["id"], target="identity")
        registration.finish_run(self.run["id"], status="failed")
        registration.advance_checkpoint(self.attempt["id"], "failed")
        self.run = registration.start_run(self.attempt["id"], initial_status="running", execution_id="offline-current")
        result = registration.persist_core_account(self.attempt["id"], access_token="offline-token",
            account={"email": self.email, "chatgpt_session": {"accessToken": "offline-token", "expires": "offline"}},
            run_id=self.run["id"], execution_id="offline-current")
        self.assertEqual(result["attempt"]["id"], self.attempt["id"])
        self.assertEqual(result["attempt"]["checkpoint"], "core_persisted")
        account = record_store.get_row(record_store.ACCOUNTS, result["account_id"])
        session = json.loads(account["chatgpt_session"]) if isinstance(account["chatgpt_session"], str) else account["chatgpt_session"]
        self.assertEqual(session["expires"], "offline")
