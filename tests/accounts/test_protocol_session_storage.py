# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.storage import records as rs
from tests.support_pg import PostgresTestCase


class ProtocolSessionStorageTests(PostgresTestCase):
    def setUp(self):
        from core.storage.accounts import protocol_sessions
        self.store = protocol_sessions
        self.key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.key.start()
        self.addCleanup(self.key.stop)
        rs.init()
        self.account_id = rs.insert_row(rs.ACCOUNTS, {"email": "cache@example.test"})
        self.payload = {"cookies": [{"name": "session", "value": "sensitive-fixture", "domain": "chatgpt.com"}], "device_id": "fixture-device"}

    def test_roundtrip_is_encrypted_and_absent_from_public_account(self):
        self.store.save_session(self.account_id, "Cache@Example.Test", self.payload)
        self.assertEqual(self.payload, self.store.load_session(self.account_id, "cache@example.test"))
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT encrypted_payload FROM "{self.schema}"."account_protocol_sessions"')
            encrypted = cur.fetchone()["encrypted_payload"]
        self.assertNotIn("sensitive-fixture", encrypted)
        self.assertNotIn("sensitive-fixture", json.dumps(rs.get_row(rs.ACCOUNTS, self.account_id)))

    def test_expired_cache_is_not_loaded(self):
        old = datetime.now(timezone.utc) - timedelta(days=2)
        self.store.save_session(self.account_id, "cache@example.test", self.payload, now=old, ttl_seconds=60)
        self.assertIsNone(self.store.load_session(self.account_id, "cache@example.test"))

    def test_account_and_changed_email_cannot_read_another_identity(self):
        other = rs.insert_row(rs.ACCOUNTS, {"email": "other@example.test"})
        self.store.save_session(self.account_id, "cache@example.test", self.payload)
        self.assertIsNone(self.store.load_session(other, "cache@example.test"))
        self.assertIsNone(self.store.load_session(self.account_id, "other@example.test"))
        rs.patch_row(rs.ACCOUNTS, self.account_id, {"email": "renamed@example.test"})
        self.assertIsNone(self.store.load_session(self.account_id, "cache@example.test"))

    def test_corrupt_ciphertext_is_ignored(self):
        self.store.save_session(self.account_id, "cache@example.test", self.payload)
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f'UPDATE "{self.schema}"."account_protocol_sessions" SET encrypted_payload=%s', ("corrupted",))
        self.assertIsNone(self.store.load_session(self.account_id, "cache@example.test"))

    def test_swapped_ciphertext_cannot_cross_account_binding(self):
        other = rs.insert_row(rs.ACCOUNTS, {"email": "other@example.test"})
        self.store.save_session(self.account_id, "cache@example.test", self.payload)
        self.store.save_session(other, "other@example.test", self.payload)
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f'UPDATE "{self.schema}"."account_protocol_sessions" SET encrypted_payload=(SELECT encrypted_payload FROM "{self.schema}"."account_protocol_sessions" WHERE account_id=%s) WHERE account_id=%s', (self.account_id, other))
        self.assertIsNone(self.store.load_session(other, "other@example.test"))
