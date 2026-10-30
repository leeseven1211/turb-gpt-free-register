# -*- coding: utf-8 -*-
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.storage import postgres as postgres_store, runtime_config as store
from tests.support_pg import PostgresTestCase, drop_schema, temporary_schema_name


class RuntimeConfigStoreTests(PostgresTestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode("ascii")
        self.environment = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": self.key})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_missing_tables_are_read_only_and_inactive(self):
        schema = temporary_schema_name("config_empty")
        with patch.dict(os.environ, {"TURB_DB_SCHEMA": schema}):
            self.assertIsNone(store.read_values())
            self.assertFalse(store.is_active())
            self.assertEqual(0, store.current_revision())
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regnamespace(%s)", (schema,))
            self.assertIsNone(cur.fetchone()[0])

    def test_activation_preserves_raw_strings_and_encrypts_current_and_historical_values(self):
        values = {"API_KEY": "first-private-value", "EMPTY": "", "MULTILINE": "中文\n第二行\n", "LIST": " a, b "}
        self.assertEqual(sorted(values), store.write_values(values, activate=True, source="migration"))
        self.assertTrue(store.is_active())
        self.assertEqual(values, store.read_values())
        self.assertEqual(1, store.current_revision())
        store.write_values({"API_KEY": "second-private-value"})
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT row_to_json(t)::text FROM {postgres_store.qualified('runtime_config_values')} t")
            raw_current = " ".join(row[0] for row in cur.fetchall())
            cur.execute(f"SELECT row_to_json(t)::text FROM {postgres_store.qualified('runtime_config_history')} t")
            raw_history = " ".join(row[0] for row in cur.fetchall())
        self.assertNotIn("first-private-value", raw_current + raw_history)
        self.assertNotIn("second-private-value", raw_current + raw_history)
        self.assertNotIn("第二行", raw_current + raw_history)
        self.assertEqual("second-private-value", store.read_values()["API_KEY"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT old_value_encrypted, new_value_encrypted FROM {postgres_store.qualified('runtime_config_history')} "
                "WHERE key = 'API_KEY' AND revision = 2"
            )
            old, new = cur.fetchone()
        cipher = Fernet(self.key.encode())
        self.assertEqual(b"first-private-value", cipher.decrypt(old.encode()))
        self.assertEqual(b"second-private-value", cipher.decrypt(new.encode()))

    def test_unactivated_values_stay_inactive_until_explicit_activation(self):
        self.assertEqual(["A"], store.write_values({"A": "value"}))
        self.assertIsNone(store.read_values())
        self.assertFalse(store.is_active())
        self.assertEqual([], store.write_values({}, activate=True))
        self.assertEqual({"A": "value"}, store.read_values())
        self.assertEqual(2, store.current_revision())

    def test_same_values_do_not_add_revision_or_history(self):
        store.write_values({"A": "one"}, activate=True)
        revision = store.current_revision()
        self.assertEqual([], store.write_values({"A": "one"}, activate=True))
        self.assertEqual(revision, store.current_revision())
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {postgres_store.qualified('runtime_config_history')}")
            self.assertEqual(1, cur.fetchone()[0])

    def test_missing_wrong_and_invalid_keys_fail_without_falling_back(self):
        store.write_values({"SECRET": "private-value"}, activate=True)
        for key, code in (("", "encryption_key_missing"), ("not-fernet", "encryption_key_invalid"), (Fernet.generate_key().decode(), "decryption_failed")):
            with self.subTest(code=code), patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": key}):
                self.assertTrue(store.is_active())
                self.assertEqual(1, store.current_revision())
                with self.assertRaises(store.RuntimeConfigStoreError) as raised:
                    store.read_values()
                self.assertEqual(code, raised.exception.code)
                self.assertNotIn("private-value", str(raised.exception))
                if key:
                    self.assertNotIn(key, str(raised.exception))
                with self.assertRaises(store.RuntimeConfigStoreError):
                    store.write_values({"OTHER": "new"})

    def test_activation_requires_key_even_for_empty_configuration(self):
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": ""}):
            with self.assertRaises(store.RuntimeConfigStoreError) as raised:
                store.write_values({}, activate=True)
        self.assertEqual("encryption_key_missing", raised.exception.code)
        self.assertFalse(store.is_active())

    def test_transaction_reads_uncommitted_candidate_and_rolls_back_all_changes(self):
        store.write_values({"A": "original"}, activate=True)
        before = store.current_revision()
        with self.assertRaisesRegex(ValueError, "候选配置校验失败"):
            with store.transaction() as conn:
                store.write_values({"A": "candidate", "B": "new"}, conn=conn)
                self.assertEqual({"A": "candidate", "B": "new"}, store.read_values())
                with store.transaction() as nested:
                    self.assertIs(conn, nested)
                    self.assertEqual(before + 1, store.current_revision())
                raise ValueError("候选配置校验失败")
        self.assertEqual({"A": "original"}, store.read_values())
        self.assertEqual(before, store.current_revision())
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {postgres_store.qualified('runtime_config_history')}")
            self.assertEqual(1, cur.fetchone()[0])

    def test_concurrent_partial_writes_keep_every_key_and_monotonic_revision(self):
        store.write_values({}, activate=True)
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda index: store.write_values({f"KEY_{index}": f"value-{index}"}), range(10)))
        self.assertEqual(10, sum(len(result) for result in results))
        self.assertEqual({f"KEY_{index}": f"value-{index}" for index in range(10)}, store.read_values())
        self.assertEqual(11, store.current_revision())

    def test_explicit_connection_does_not_commit_before_its_owner(self):
        store.write_values({"A": "original"}, activate=True)
        with self.assertRaisesRegex(ValueError, "撤销外部事务"):
            with postgres_store.connect() as conn:
                store.ensure_tables(conn)
                store.write_values({"A": "candidate"}, conn=conn)
                self.assertEqual({"A": "candidate"}, store.read_values(conn=conn))
                self.assertTrue(store.is_active(conn=conn))
                self.assertEqual(2, store.current_revision(conn=conn))
                raise ValueError("撤销外部事务")
        self.assertEqual({"A": "original"}, store.read_values())
        self.assertEqual(1, store.current_revision())

    def test_autocommit_connection_rejects_writes_before_any_ddl_and_allows_reads(self):
        empty_schema = temporary_schema_name("config_autocommit")
        self.addCleanup(drop_schema, empty_schema)
        with postgres_store.connect(autocommit=True) as conn:
            with patch.dict(os.environ, {"TURB_DB_SCHEMA": empty_schema}):
                self.assertIsNone(store.read_values(conn=conn))
                with self.assertRaises(store.RuntimeConfigStoreError) as raised:
                    store.write_values({"A": "candidate"}, conn=conn, activate=True)
                self.assertEqual("transaction_required", raised.exception.code)
                with self.assertRaises(store.RuntimeConfigStoreError) as raised:
                    store.ensure_tables(conn)
                self.assertEqual("transaction_required", raised.exception.code)
            with conn.cursor() as cur:
                cur.execute("SELECT to_regnamespace(%s)", (empty_schema,))
                self.assertIsNone(cur.fetchone()[0])

        store.write_values({"A": "original"}, activate=True)
        with postgres_store.connect(autocommit=True) as conn:
            self.assertEqual({"A": "original"}, store.read_values(conn=conn))
            self.assertTrue(store.is_active(conn=conn))
            self.assertEqual(1, store.current_revision(conn=conn))
            with self.assertRaises(store.RuntimeConfigStoreError):
                store.write_values({"A": "candidate", "B": "partial"}, conn=conn)
        self.assertEqual({"A": "original"}, store.read_values())
        self.assertEqual(1, store.current_revision())

    def test_database_failure_is_reported_without_connection_details(self):
        with patch.object(postgres_store, "connect", side_effect=RuntimeError("private-connection-value")):
            with self.assertRaises(store.RuntimeConfigStoreError) as raised:
                store.read_values()
        self.assertEqual("database_unavailable", raised.exception.code)
        self.assertNotIn("private-connection-value", str(raised.exception))

    def test_invalid_input_is_rejected_before_partial_write(self):
        store.write_values({"A": "original"}, activate=True)
        with self.assertRaises(store.RuntimeConfigStoreError):
            store.write_values({"A": "candidate", "B": None})
        self.assertEqual({"A": "original"}, store.read_values())
