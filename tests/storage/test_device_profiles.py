# -*- coding: utf-8 -*-
import unittest

from core.storage import postgres as pg, records
from core.storage.accounts import device_profiles, protocol_sessions
from tests.support_pg import PostgresTestCase


class DeviceProfileStoreTests(PostgresTestCase):
    def setUp(self):
        self.email = "device-profile@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email,
            "access_token": "at",
            "created_at": "2026-11-20T10:00:00",
            "updated_at": "2026-11-20T10:00:00",
        })
        self.profile = {
            "browser_os": "Windows",
            "navigator_platform": "Win32",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0",
            "screen_width": 2560,
            "screen_height": 1440,
            "hardware_concurrency": 24,
            "device_memory": 8,
            "device_pixel_ratio": 1,
            "js_heap_size_limit": 4294967296,
            "impersonate": "chrome146",
        }

    def test_roundtrip_keeps_device_layer_only(self):
        saved = device_profiles.save_profile(
            self.account_id, self.email,
            {"device_id": "device-abc", "browser_profile": self.profile,
             "cookies": [{"name": "secret-cookie", "value": "v"}]},
            origin="refresh_at_rust",
        )
        self.assertTrue(saved)
        payload = device_profiles.load_profile(self.account_id, self.email)
        self.assertEqual("device-abc", payload["device_id"])
        self.assertEqual(self.profile, payload["browser_profile"])
        self.assertEqual("chrome146", payload["impersonate"])
        self.assertEqual("refresh_at_rust", payload["source"])
        self.assertNotIn("cookies", payload)

    def test_payload_is_encrypted_at_rest(self):
        device_profiles.save_profile(
            self.account_id, self.email,
            {"device_id": "device-abc", "browser_profile": self.profile},
        )
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT encrypted_payload FROM {pg.qualified('account_device_profiles')} WHERE account_id=%s",
                (self.account_id,),
            )
            raw = cur.fetchone()[0]
        self.assertNotIn("device-abc", raw)
        self.assertNotIn("Windows NT", raw)

    def test_profile_survives_session_expiry(self):
        payload = {"device_id": "device-abc", "browser_profile": self.profile,
                   "cookies": [{"name": "oai-did", "value": "device-abc",
                                "domain": ".openai.com", "path": "/"}]}
        protocol_sessions.save_session(self.account_id, self.email, payload)
        device_profiles.remember_session(self.account_id, self.email, payload, origin="password_reset")
        protocol_sessions.invalidate_session(self.account_id, self.email)
        self.assertIsNone(protocol_sessions.load_session(self.account_id, self.email))
        self.assertEqual("device-abc", device_profiles.load_profile(self.account_id, self.email)["device_id"])

    def test_requires_device_id_and_matching_email(self):
        self.assertFalse(device_profiles.save_profile(
            self.account_id, self.email, {"browser_profile": self.profile}))
        self.assertFalse(device_profiles.save_profile(
            self.account_id, "other@example.test",
            {"device_id": "device-abc", "browser_profile": self.profile}))
        device_profiles.save_profile(
            self.account_id, self.email, {"device_id": "device-abc", "browser_profile": self.profile})
        records.patch_row(records.ACCOUNTS, self.account_id, {"email": "renamed@example.test"})
        self.assertIsNone(device_profiles.load_profile(self.account_id, self.email))
        self.assertIsNone(device_profiles.load_profile(self.account_id, "renamed@example.test"))


if __name__ == "__main__":
    unittest.main()
