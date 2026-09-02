# -*- coding: utf-8 -*-
import dataclasses
import threading
import unittest
from unittest.mock import patch

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

    def test_raw_context_is_disabled_without_creating_a_context_row(self):
        from core.storage import account_auth

        with patch("config.account.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False):
            self.assertIsNone(
                account_auth.create_auth_run_context(
                    operation_run_id=999,
                    account_id=self.account_id,
                    action="token_refresh",
                    driver="protocol_v2",
                )
            )
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass(%s) AS name",
                (f'"{self.schema}"."account_auth_run_contexts"',),
            )
            self.assertIsNone(cur.fetchone()["name"])


class AccountAuthRunContextStorageTests(PostgresTestCase):
    def setUp(self):
        from core import record_store
        from core.storage import account_auth, operation

        record_store.reset_ready()
        account_auth.reset_ready()
        operation.reset_ready()
        record_store.init()
        self.account_id = rs.insert_row(ACCOUNTS, {"email": "context@example.test"})
        self.run = operation.create_runtime_task(
            task_type="token_refresh",
            account_id=self.account_id,
            email="context@example.test",
            trigger="test",
        )["run"]

    def test_allowlists_raw_session_and_proxy_context_without_public_projection(self):
        from config import account as account_config
        from core.storage import account_auth

        with patch.object(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True):
            context_id = account_auth.create_auth_run_context(
                operation_run_id=self.run["id"],
                context_no=1,
                account_id=self.account_id,
                action="token_refresh",
                driver="protocol_v2",
                auth_method="password",
                route_attempt_no=1,
                session_no=1,
                device_id="device-raw",
                session_identifiers={
                    "oai_session_id": "session-raw",
                    "react_container_key": "react-raw",
                    "password": "must-drop",
                },
                proxy_url="socks5h://user:secret@proxy.example:1080",
                proxy_context={
                    "provider": "1024proxy",
                    "region": "JP",
                    "exit_ip": "198.51.100.10",
                    "proxy_password": "must-drop",
                },
            )
            row = account_auth.get_auth_run_context(context_id)

        self.assertIsNotNone(context_id)
        self.assertEqual("device-raw", row["device_id"])
        self.assertEqual({"oai_session_id": "session-raw", "react_container_key": "react-raw"}, row["session_identifiers"])
        self.assertEqual({"provider": "1024proxy", "region": "JP", "exit_ip": "198.51.100.10"}, row["proxy_context"])
        self.assertEqual("socks5h://user:secret@proxy.example:1080", row["proxy_url"])
        self.assertNotIn("password", row["session_identifiers"])
        self.assertNotIn("proxy_password", row["proxy_context"])
        self.assertNotIn("account_auth_run_contexts", rs.get_row(ACCOUNTS, self.account_id))

    def test_context_no_is_allocated_under_operation_run_lock_and_finish_is_idempotent(self):
        from config import account as account_config
        from core.storage import account_auth

        with patch.object(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True):
            first = account_auth.create_auth_run_context(
                operation_run_id=self.run["id"], account_id=self.account_id,
                action="token_refresh", driver="protocol_v2",
            )
            second = account_auth.create_auth_run_context(
                operation_run_id=self.run["id"], account_id=self.account_id,
                action="token_refresh", driver="protocol_v2", session_no=2,
            )
            self.assertTrue(account_auth.finish_auth_run_context(first, status="rotated", result_code="retry"))
            self.assertTrue(account_auth.finish_auth_run_context(first, status="rotated", result_code="retry"))
            self.assertNotEqual(first, second)
            first_row = account_auth.get_auth_run_context(first)
            second_row = account_auth.get_auth_run_context(second)
        self.assertEqual(1, first_row["context_no"])
        self.assertEqual(2, second_row["context_no"])
        self.assertEqual("rotated", first_row["status"])
        self.assertEqual("retry", first_row["result_code"])

    def test_expired_context_cleanup_is_bounded_and_keeps_live_context(self):
        from config import account as account_config
        from core.storage import account_auth

        with patch.object(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True), \
             patch.object(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS", 30):
            expired = account_auth.create_auth_run_context(
                operation_run_id=self.run["id"], account_id=self.account_id,
                action="token_refresh", driver="protocol_v2",
            )
            live = account_auth.create_auth_run_context(
                operation_run_id=self.run["id"], account_id=self.account_id,
                action="token_refresh", driver="protocol_v2", session_no=2,
            )
            with rs._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"UPDATE \"{self.schema}\".\"account_auth_run_contexts\" "
                    "SET expires_at = now() - interval '1 minute' WHERE id = %s",
                    (expired,),
                )
            self.assertEqual(1, account_auth.cleanup_expired_auth_contexts(limit=1))
            self.assertIsNone(account_auth.get_auth_run_context(expired))
            self.assertIsNotNone(account_auth.get_auth_run_context(live))

    def test_context_read_requires_audit_and_audit_contains_no_raw_values(self):
        from config import account as account_config
        from core.storage import account_auth

        with patch.object(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", True):
            context_id = account_auth.create_auth_run_context(
                operation_run_id=self.run["id"], account_id=self.account_id,
                action="token_refresh", driver="protocol_v2",
                device_id="private-device-id",
                session_identifiers={"oai_session_id": "private-session-id"},
            )
            with self.assertRaisesRegex(account_auth.AccountAuthStorageError, "actor_required"):
                account_auth.audit_auth_run_context_access(context_id, actor="")
            row = account_auth.get_auth_run_context_audited(
                context_id, actor="local-admin", purpose="incident-review", scope="identifiers",
            )

        self.assertEqual("private-device-id", row["device_id"])
        self.assertEqual({"oai_session_id": "private-session-id"}, row["session_identifiers"])
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT actor, purpose, scope FROM \"{self.schema}\".\"account_auth_context_access_audits\" "
                "WHERE context_id = %s",
                (context_id,),
            )
            audit = cur.fetchone()
        self.assertEqual("local-admin", audit["actor"])
        self.assertEqual("incident-review", audit["purpose"])
        self.assertEqual("identifiers", audit["scope"])

    def test_raw_context_reads_and_finishes_are_noops_when_disabled(self):
        from config import account as account_config
        from core.storage import account_auth

        with patch.object(account_config, "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED", False):
            self.assertIsNone(account_auth.get_auth_run_context(123))
            self.assertFalse(account_auth.finish_auth_run_context(123, status="failed"))

if __name__ == "__main__":
    unittest.main()
