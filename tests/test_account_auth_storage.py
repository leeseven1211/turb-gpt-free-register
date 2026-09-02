# -*- coding: utf-8 -*-
import dataclasses
import threading
import unittest

from core import record_store as rs
from core.record_store import ACCOUNTS
from tests.support_pg import PostgresTestCase


class AccountAuthProfileDerivationTests(unittest.TestCase):
    def test_same_key_is_stable_and_domain_separated(self):
        from core.storage import account_auth

        key = "11" * 32
        first = account_auth._derive_identity(key)
        second = account_auth._derive_identity(key)

        self.assertEqual(first, second)
        self.assertEqual(36, len(first["device_id"]))
        self.assertEqual(12, len(first["profile_ref"]))
        self.assertNotEqual(
            account_auth._material(bytes.fromhex(key), 1, "device-id"),
            account_auth._material(bytes.fromhex(key), 1, "profile-ref"),
        )

    def test_profile_contains_device_fields_but_no_route_or_session_fields(self):
        from config.browser import build_browser_environment, validate_browser_profile
        from core.storage import account_auth

        profile = account_auth._derive_identity("22" * 32)["browser_profile"]
        # Locale/timezone are route-specific and deliberately absent from the
        # stored profile; BrowserSession overlays them for the current route.
        self.assertEqual([], validate_browser_profile(build_browser_environment({}, base_profile=profile)))
        self.assertTrue(profile["user_agent"])
        self.assertGreater(profile["screen_width"], 0)
        self.assertGreater(profile["hardware_concurrency"], 0)
        for forbidden in {
            "geo", "locale_profile", "timezone_iana", "timezone_offset_minutes",
            "timezone_name", "react_listening_key", "react_container_key",
            "react_resources_key", "sentinel_sid", "oai_session_id", "device_id",
        }:
            self.assertNotIn(forbidden, profile)

    def test_different_keys_do_not_share_derived_identity_ids(self):
        from core.storage import account_auth

        first = account_auth._derive_identity("33" * 32)
        second = account_auth._derive_identity("44" * 32)
        self.assertNotEqual(first["device_id"], second["device_id"])
        self.assertNotEqual(first["profile_ref"], second["profile_ref"])


class AccountAuthIdentityStorageTests(PostgresTestCase):
    def setUp(self):
        from core.storage import account_auth

        rs.reset_ready()
        account_auth.reset_ready()
        rs.init()
        self.account_id = rs.insert_row(ACCOUNTS, {"email": "identity@example.test"})

    def test_identity_is_lazy_private_and_idempotent(self):
        from core.storage import account_auth

        identity = account_auth.ensure_account_protocol_identity(self.account_id)
        again = account_auth.ensure_account_protocol_identity(self.account_id)
        fetched = account_auth.get_active_account_protocol_identity(self.account_id)

        self.assertEqual(identity, again)
        self.assertEqual(identity, fetched)
        self.assertNotIn("profile_key", dataclasses.asdict(identity))
        self.assertEqual("identity@example.test", rs.get_row(ACCOUNTS, self.account_id)["email"])
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT profile_key FROM \"{self.schema}\".\"account_protocol_identities\" "
                "WHERE id = %s",
                (identity.identity_id,),
            )
            self.assertEqual(64, len(cur.fetchone()["profile_key"]))

    def test_missing_account_fails_without_creating_identity(self):
        from core.storage import account_auth

        with self.assertRaisesRegex(account_auth.AccountAuthStorageError, "account_not_found"):
            account_auth.ensure_account_protocol_identity(999999)
        self.assertEqual(1, rs.count_rows("registered_accounts"))
        self.assertEqual(0, self._identity_count())

    def test_concurrent_ensure_returns_one_same_identity(self):
        from core.storage import account_auth

        results = []
        errors = []
        lock = threading.Lock()

        def ensure():
            try:
                value = account_auth.ensure_account_protocol_identity(self.account_id)
                with lock:
                    results.append(value)
            except Exception as exc:  # pragma: no cover - assertion reports unexpected DB errors
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=ensure) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual([], errors)
        self.assertEqual(6, len(results))
        self.assertEqual({item.identity_id for item in results}, {results[0].identity_id})
        self.assertEqual(1, self._identity_count())

    def _identity_count(self):
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n FROM "{self.schema}"."account_protocol_identities"')
            return int(cur.fetchone()["n"])


if __name__ == "__main__":
    unittest.main()
