"""Configuration values and revision share metadata without cross-transaction caching."""
from __future__ import annotations

from contextlib import ExitStack
import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.operations import concurrency
from core.storage import runtime_config as store
from tests.support_pg import PostgresTestCase


class SnapshotChecks(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.cipher = Fernet(Fernet.generate_key())
        self.stack.enter_context(patch.object(store, '_cipher', return_value=self.cipher))
        self.stack.enter_context(patch.object(store.postgres_store, 'qualified', side_effect=lambda name: name))

    def connection(self, *, exists=True, metadata=None, values=None, corrupt=()):
        cipher = self.cipher
        encrypted = {key: ('corrupt' if key in corrupt else cipher.encrypt(value.encode()).decode())
                     for key, value in (values or {}).items()}

        class Cursor:
            rows = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, params=None):
                statements.append((query, params))
                if query.startswith('SELECT to_regclass'):
                    self.rows = [{'relation': 'runtime_config_meta' if exists else None}]
                elif query.startswith('SELECT active, revision'):
                    self.rows = [metadata] if metadata else []
                elif query.startswith('SELECT m.active, m.revision, v.key, v.value_encrypted'):
                    if not metadata:
                        # The real LEFT JOIN has no rows when the singleton
                        # metadata row is absent.
                        self.rows = []
                        return
                    active = bool(metadata['active'])
                    revision = metadata['revision']
                    selected = None if params is None else params[0]
                    if not active or selected == []:
                        joined = [None]
                    else:
                        keys = encrypted if selected is None else {
                            key: encrypted[key] for key in set(selected) & set(encrypted)
                        }
                        joined = sorted(keys) or [None]
                    self.rows = [
                        {
                            'active': active,
                            'revision': revision,
                            'key': key,
                            'value_encrypted': encrypted[key] if key is not None else None,
                        }
                        for key in joined
                    ]
                else:
                    raise AssertionError('unexpected SQL in read-only snapshot')

            def fetchone(self):
                return self.rows[0] if self.rows else None

            def fetchall(self):
                return self.rows

        class Connection:
            def cursor(self, **_):
                return Cursor()

        statements = []
        return Connection(), statements

    def test_absent_empty_meta_and_inactive_preserve_revision_without_cipher(self):
        for kwargs, expected, count in (({'exists': False}, (None, 0), 1),
                                        ({}, (None, 0), 2),
                                        ({'metadata': {'active': False, 'revision': 9}}, (None, 9), 2)):
            with self.subTest(kwargs=kwargs):
                conn, statements = self.connection(**kwargs)
                with patch.object(store, '_cipher', side_effect=AssertionError('inactive must not decrypt')):
                    self.assertEqual(expected, store.read_snapshot(conn=conn))
                self.assertEqual(count, len(statements))

    def test_active_empty_keys_returns_empty_without_cipher(self):
        conn, statements = self.connection(metadata={'active': True, 'revision': 9})
        with patch.object(store, '_cipher', side_effect=AssertionError('empty keys must not decrypt')):
            self.assertEqual(({}, 9), store.read_snapshot(conn=conn, keys=()))
        self.assertEqual(2, len(statements))

    def test_selection_decrypts_only_requested_keys_and_reads_metadata_once(self):
        conn, statements = self.connection(metadata={'active': True, 'revision': 9},
            values={'A': ' 中文\n', 'B': 'corrupted unrelated'}, corrupt=('B',))
        self.assertEqual(({'A': ' 中文\n'}, 9), store.read_snapshot(conn=conn, keys=('A', 'MISSING', 'A')))
        self.assertEqual(2, len(statements))
        self.assertEqual(['A', 'MISSING'], statements[-1][1][0])
        self.assertEqual(1, sum(query.startswith('SELECT m.active, m.revision') for query, _ in statements))

    def test_selected_corruption_keeps_sanitized_failure(self):
        conn, _ = self.connection(metadata={'active': True, 'revision': 9}, values={'A': 'private'}, corrupt=('A',))
        with self.assertRaises(store.RuntimeConfigStoreError) as caught:
            store.read_snapshot(conn=conn, keys=('A',))
        self.assertEqual('decryption_failed', caught.exception.code)
        self.assertNotIn('private', str(caught.exception))

    def test_read_values_and_revision_old_api_keep_inactive_and_active_semantics(self):
        for active, expected in ((False, None), (True, {'A': ''})):
            conn, _ = self.connection(metadata={'active': active, 'revision': 4}, values={'A': ''})
            with self.subTest(active=active):
                self.assertEqual(expected, store.read_values(conn=conn))
                self.assertEqual(4, store.current_revision(conn=conn))

    def test_context_connection_is_respected_without_opening_a_new_connection(self):
        conn, _ = self.connection(metadata={'active': True, 'revision': 3}, values={'A': 'transaction candidate'})
        token = store._CURRENT_CONNECTION.set(conn)
        try:
            self.assertEqual(({'A': 'transaction candidate'}, 3), store.read_snapshot())
        finally:
            store._CURRENT_CONNECTION.reset(token)

    def test_policy_keeps_default_and_migration_semantics_with_two_queries(self):
        cases = [(False, {}, False, 2), (True, {}, True, 2),
                 (True, {'CONCURRENCY_POLICY_REVISION': '1', 'GLOBAL_TASK_WORKERS': '4'}, False, 2)]
        for active, values, migration, sql_count in cases:
            with self.subTest(active=active, values=values):
                conn, statements = self.connection(metadata={'active': active, 'revision': 5}, values=values)
                parsed, revision, required = concurrency._policy(conn)
                self.assertEqual(5, revision)
                self.assertIs(required, migration)
                self.assertGreater(parsed['GLOBAL_TASK_WORKERS'], 0)
                if values:
                    self.assertEqual(4, parsed['GLOBAL_TASK_WORKERS'])
                self.assertEqual(sql_count, len(statements))


class SnapshotPostgresTests(PostgresTestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'TURB_CONFIG_ENCRYPTION_KEY': Fernet.generate_key().decode()})
        environment.start()
        self.addCleanup(environment.stop)

    def test_activation_revision_and_selected_values_are_read_together(self):
        store.write_values({'A': 'raw value', 'B': 'other'})
        self.assertEqual((None, 1), store.read_snapshot())
        store.write_values({}, activate=True)
        self.assertEqual(({'A': 'raw value'}, 2), store.read_snapshot(keys=('A', 'A', 'missing')))
        self.assertEqual(({}, 2), store.read_snapshot(keys=()))

    def test_transaction_snapshot_keeps_rollback_and_current_revision_contract(self):
        store.write_values({'A': 'original'}, activate=True)
        with self.assertRaisesRegex(ValueError, 'rollback candidate'):
            with store.transaction() as conn:
                store.write_values({'A': 'candidate'}, conn=conn)
                self.assertEqual(({'A': 'candidate'}, 2), store.read_snapshot(conn=conn))
                self.assertEqual(({'A': 'candidate'}, 2), store.read_snapshot())
                raise ValueError('rollback candidate')
        self.assertEqual(({'A': 'original'}, 1), store.read_snapshot())
        self.assertEqual(1, store.current_revision())

