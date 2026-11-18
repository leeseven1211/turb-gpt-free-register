"""Admission preserves fairness while omitting an unused cursor read on denial."""
from __future__ import annotations

from contextlib import ExitStack, nullcontext
import unittest
from unittest.mock import patch

from core.storage.operations import permits


class AdmissionCursorChecks(unittest.TestCase):
    def admit(self, *, occupied=0, policy_blocks=(), last_type='', active=False):
        scopes = [{'kind': 'global', 'key': 'deployment', 'limit': 4}]
        statements = []
        schema = 'test_admission_cursor_offline'
        tables = (
            'operation_execution_dispatch_cursor', 'operation_execution_requests',
            'operation_execution_permits', 'operation_execution_permit_scopes',
        )

        class Cursor:
            result = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, params=None):
                sql = ' '.join(str(query).split())
                # The repository captures schema before its transaction. Keep
                # this SQL-only fixture independent of ambient schema scopes.
                for table in tables:
                    sql = sql.replace(f'"{schema}"."{table}"', table)
                statements.append((sql, params))
                if sql.startswith('SELECT s.scope_kind'):
                    self.result = [{'scope_kind': 'global', 'scope_key': 'deployment', 'occupied': occupied}]
                elif sql.startswith('SELECT 1 FROM operation_execution_permits'):
                    self.result = [{'one': 1}] if active else []
                elif sql.startswith('SELECT task_type, batches, lanes'):
                    self.result = [{'task_type': last_type, 'batches': {}, 'lanes': {}}]
                elif sql.startswith('SELECT execution_key,task_type,batch_key'):
                    self.result = [{'execution_key': f'request:{name}', 'task_type': name, 'batch_key': '',
                                    'scopes': scopes, 'dispatch_lane': 'new', 'blocked_by': []}
                                   for name in ('live_check', 'token_refresh')]
                else:
                    self.result = []

            def fetchone(self):
                return self.result[0] if self.result else None

            def fetchall(self):
                return self.result

        class Connection(Cursor):
            def cursor(self, **_):
                return Cursor()

            def transaction(self):
                return nullcontext()

        with ExitStack() as stack:
            stack.enter_context(patch.object(permits, 'ensure_tables'))
            stack.enter_context(patch.object(permits, 'admission_lock'))
            stack.enter_context(patch.object(permits.postgres, 'connect', return_value=Connection()))
            stack.enter_context(patch.object(permits.postgres, 'schema_name', return_value=schema))
            stack.enter_context(patch.object(permits.postgres, 'qualified', side_effect=lambda name: name))
            result = permits.try_admit(execution_key='request:live_check', task_type='live_check',
                execution_id='execution', run_id=12, batch_key='', owner={}, metadata={},
                policy=lambda conn: (scopes, 7, list(policy_blocks)),
                claim=lambda conn, execution_id: {'id': 12})
        return result, statements

    def test_capacity_denied_records_request_and_reason_without_fairness_cursor_read(self):
        result, statements = self.admit(occupied=4)
        self.assertEqual({'blocked_by': ['global_capacity']}, result)
        self.assertEqual(1, sum(sql.startswith('INSERT INTO operation_execution_requests') for sql, _ in statements))
        self.assertIn(('UPDATE operation_execution_requests SET blocked_by=%s::jsonb WHERE execution_key=%s',
                       ('["global_capacity"]', 'request:live_check')), statements)
        self.assertFalse(any(sql.startswith('SELECT task_type, batches, lanes') for sql, _ in statements))
        self.assertFalse(any(sql.startswith('SELECT execution_key,task_type,batch_key') for sql, _ in statements))

    def test_policy_or_active_denials_do_not_read_cursor(self):
        for kwargs, expected in (({'policy_blocks': ['migration']}, ['migration']),
                                 ({'active': True}, ['execution_active'])):
            with self.subTest(kwargs=kwargs):
                result, statements = self.admit(**kwargs)
                self.assertEqual(expected, result['blocked_by'])
                self.assertFalse(any(sql.startswith('SELECT task_type, batches, lanes') for sql, _ in statements))

    def test_available_capacity_preserves_persisted_type_fairness(self):
        result, statements = self.admit(last_type='live_check')
        self.assertEqual({'blocked_by': ['fairness_turn']}, result)
        sql = [item[0] for item in statements]
        cursor = [i for i, value in enumerate(sql) if value.startswith('SELECT task_type, batches, lanes')]
        ready = [i for i, value in enumerate(sql) if value.startswith('SELECT execution_key,task_type,batch_key')]
        self.assertEqual(1, len(cursor))
        self.assertEqual(1, len(ready))
        self.assertLess(cursor[0], ready[0])

    def test_available_fair_turn_still_claims_and_persists_permit(self):
        result, statements = self.admit(last_type='token_refresh')
        self.assertEqual([], result['blocked_by'])
        self.assertEqual({'id': 12}, result['claimed_run'])
        self.assertEqual(7, result['policy_revision'])
        self.assertEqual('execution', result['execution_id'])
        self.assertTrue(result['permit_id'])
        self.assertEqual(1, sum(sql.startswith('INSERT INTO operation_execution_permits') for sql, _ in statements))
        self.assertEqual(1, sum(sql.startswith('UPDATE operation_execution_dispatch_cursor') for sql, _ in statements))
        self.assertEqual(1, sum(sql.startswith('SELECT task_type, batches, lanes') for sql, _ in statements))

