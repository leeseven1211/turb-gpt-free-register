"""Product durable worker status against fake connections; no PostgreSQL I/O."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core.storage import runtime_workers as store


class Cursor:
    def __init__(self, connection):
        self.connection = connection
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params=None):
        self.connection.calls.append((' '.join(sql.split()), params))
        if self.connection.error:
            raise self.connection.error
    def fetchone(self):
        return self.connection.rows.pop(0)


class Connection:
    autocommit = False
    def __init__(self, *rows, error=None):
        self.rows = list(rows)
        self.calls = []
        self.error = error
    def cursor(self, **kwargs):
        return Cursor(self)


def db_row(**updates):
    row = dict(instance_id='local', owner_nonce='nonce-a', generation=4,
               host='worker-host', pid=456, process_start='2026-11-16T10:00:00Z',
               mode='worker', release='abc1234', heartbeat_epoch=80., server_epoch=100.,
               status={'state': 'running', 'ready': True, 'applied_db_revision': 9,
                       'local_snapshot_revision': 3, 'components': {}, 'counts': {}})
    row.update(updates)
    return row


class WorkerStoreTests(unittest.TestCase):
    def setUp(self):
        self.no_db = patch.object(store.postgres_store, 'connect', side_effect=AssertionError('real DB forbidden'))
        self.no_db.start()
        self.addCleanup(self.no_db.stop)

    def test_status_projects_only_nonsecret_component_and_count_fields(self):
        raw = {'state': 'running', 'ready': True, 'password': 'secret', 'config': {'TOKEN': 'secret'},
               'applied_db_revision': 7, 'local_snapshot_revision': 2,
               'components': {'config_observer': {'state': 'applied', 'healthy': True, 'values': 'secret'},
                              'c2a_monitor': {'started': True, 'alive': True, 'disabled': True, 'api_key': 'secret'},
                              'smtp_password': {'healthy': True}},
               'counts': {'active': 2, 'accepted': 3, 'permits': 123, 'password': 'secret'}}
        self.assertEqual(store.normalize_status(raw), {
            'state': 'running', 'ready': True, 'applied_db_revision': 7, 'local_snapshot_revision': 2,
            'components': {'config_observer': {'state': 'applied', 'healthy': True},
                           'c2a_monitor': {'started': True, 'alive': True, 'disabled': True}},
            'counts': {'active': 2, 'accepted': 3}})

    def test_settlement_health_counts_and_age_survive_durable_projection(self):
        raw = {'components': {'settlement': {
            'started': True, 'alive': True, 'thread_alive': True, 'healthy': False,
            'error_code': 'settlement_storage_unavailable',
            'oldest_age_seconds': 2.5, 'stages': {'callback': 1, 'resources': 1, 'settlement': 2,
                'permit': 0, 'password': 'secret'},
            'counts': {'settlement_pending': 2, 'resource_pending': 0,
                       'permit_pending': 0, 'registered': 3, 'unverified_scan_pending': 1,
                       'password': 'secret'},
            'private_intent': 'secret'}},
            'counts': {'settlement_pending': 2, 'resource_pending': 0,
                'permit_pending': 0, 'compensation_inflight': 1, 'unpersisted': 2,
                'callback_active': 1, 'registered': 3, 'registration_pending': 1,
                'legacy_renewal_pending': 1,
                'unverified_scan_pending': 1,
                'password': 'secret'}}
        result = store.normalize_status(raw)
        component = result['components'].get('settlement')
        self.assertIsNotNone(component)
        self.assertEqual(component['oldest_age_seconds'], 2.5)
        self.assertEqual(component['error_code'], 'settlement_storage_unavailable')
        self.assertEqual(component['stages'], {'callback': 1, 'resources': 1,
                                             'settlement': 2, 'permit': 0})
        self.assertEqual(component['counts']['registered'], 3)
        self.assertEqual(component['counts'].get('unverified_scan_pending'), 1)
        self.assertEqual(result['counts'], {'settlement_pending': 2, 'resource_pending': 0,
            'permit_pending': 0, 'compensation_inflight': 1, 'unpersisted': 2,
            'callback_active': 1, 'registered': 3, 'registration_pending': 1,
            'legacy_renewal_pending': 1, 'unverified_scan_pending': 1})
        self.assertNotIn('secret', repr(result))

    def test_settlement_age_rejects_nonfinite_or_negative_values(self):
        for age in (-1, float('inf'), float('nan'), True, 'private'):
            with self.subTest(age=age), self.assertRaisesRegex(
                    ValueError, '^runtime_worker_invalid_status$'):
                store.normalize_status({'components': {'settlement': {
                    'oldest_age_seconds': age}}})

    def test_settlement_storage_classifications_survive_local_and_remote_projection(self):
        from core.runtime import readiness
        for code in ('settlement_storage_permission_denied',
                     'settlement_storage_authentication_failed',
                     'settlement_storage_sqlstate_unknown',
                     'settlement_carrier_unavailable'):
            with self.subTest(code=code):
                normalized = store.normalize_status({'state': 'running', 'ready': False,
                    'components': {'settlement': {'healthy': False, 'error_code': code,
                        'cleanup_scan_error_code': code,
                        'counts': {'unverified_scan_pending': 1}}},
                    'counts': {'unverified_scan_pending': 1}})
                local = readiness.compatibility_status(mode='worker', source='local_worker',
                    ready=False, state='running', identity={}, components=normalized['components'],
                    config={}, counts=normalized['counts'])
                remote = readiness.remote_status({**normalized, 'release': 'release',
                    'applied_db_revision': 1, 'owner_nonce': 'nonce', 'generation': 1},
                    expected_release='release', required_db_revision=1)
                for projected in (normalized, local, remote):
                    component = projected['components']['settlement']
                    self.assertEqual(component['error_code'], code)
                    self.assertEqual(component.get('cleanup_scan_error_code'), code)
                    self.assertEqual(component['counts']['unverified_scan_pending'], 1)
                    self.assertFalse(projected['ready'])

    def test_cleanup_scan_error_code_uses_fixed_safe_allowlist(self):
        private = 'postgresql://private-user:private-password@private-host/private-db'
        for code, expected in ((None, None), ('', None),
                               ('settlement_storage_unavailable', 'settlement_storage_unavailable'),
                               (private, 'component_error')):
            with self.subTest(expected=expected):
                normalized = store.normalize_status({'components': {'settlement': {
                    'error_code': code, 'cleanup_scan_error_code': code,
                    'private_error': private}}})
                component = normalized['components']['settlement']
                self.assertEqual(component['error_code'], expected)
                self.assertIn('cleanup_scan_error_code', component)
                self.assertEqual(component['cleanup_scan_error_code'], expected)
                self.assertNotIn('private-', repr(normalized))

    def test_registration_pending_roundtrips_to_local_and_remote_status(self):
        from core.runtime import readiness
        components = {name: {'started': True, 'alive': True}
                      for name in readiness.REQUIRED_COMPONENTS}
        components['config_observer']['state'] = 'applied'
        components['settlement']['healthy'] = True
        normalized = store.normalize_status({'state': 'running', 'ready': False,
            'components': components, 'counts': {'registration_pending': 1,
                                                'legacy_renewal_pending': 1,
                                                'unverified_scan_pending': 1}})
        local = readiness.compatibility_status(mode='worker', source='local_worker',
            ready=False, state='running', identity={}, components=normalized['components'],
            config={}, counts=normalized['counts'])
        remote = readiness.remote_status({**normalized, 'release': 'release',
            'applied_db_revision': 1, 'owner_nonce': 'nonce', 'generation': 1},
            expected_release='release', required_db_revision=1)
        self.assertEqual(local['counts']['registration_pending'], 1)
        self.assertEqual(remote['counts']['registration_pending'], 1)
        self.assertEqual(local['counts'].get('legacy_renewal_pending'), 1)
        self.assertEqual(remote['counts'].get('legacy_renewal_pending'), 1)
        self.assertEqual(local['counts'].get('unverified_scan_pending'), 1)
        self.assertEqual(remote['counts'].get('unverified_scan_pending'), 1)
        self.assertFalse(remote['ready'])

    def test_unknown_error_text_is_replaced_not_persisted(self):
        status = store.normalize_status({'state': 'degraded', 'components': {
            'proxy_pool': {'error_code': 'postgres://password@private-host', 'state': 'password=secret'}}})
        self.assertEqual(status['components']['proxy_pool'], {'error_code': 'component_error', 'state': 'unknown'})

    def test_invalid_counts_or_revisions_fail_before_io(self):
        for raw in [{'counts': {'active': -1}}, {'applied_db_revision': True}, {'counts': {'active': 1.5}}]:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, '^runtime_worker_invalid_status$'):
                store.normalize_status(raw)

    def test_missing_table_read_has_db_clock_and_never_ddl(self):
        conn = Connection({'relation': None, 'server_epoch': 1234.5})
        self.assertEqual(store.read_worker('local', conn=conn), {
            'instance_id': 'local', 'state': 'absent', 'present': False, 'fresh': False,
            'ready': False, 'server_epoch': 1234.5, 'heartbeat_epoch': None, 'age_seconds': None})
        self.assertEqual(len(conn.calls), 1)
        self.assertTrue(conn.calls[0][0].startswith('SELECT'))
        self.assertNotIn('CREATE', conn.calls[0][0])

    def test_read_freshness_uses_db_epochs_and_exact_boundary_is_stale(self):
        for heartbeat, expected in [(80., False), (80.1, True), (101., False)]:
            conn = Connection({'relation': 'runtime_workers', 'server_epoch': 99999.}, db_row(heartbeat_epoch=heartbeat))
            result = store.read_worker('local', conn=conn)
            self.assertEqual(result['fresh'], expected)
            self.assertEqual(result['ready'], expected)
            self.assertEqual(result['owner_nonce'], 'nonce-a')
            self.assertEqual(result['generation'], 4)
            self.assertEqual(result['server_epoch'], 100.)
            self.assertTrue(all(sql.startswith('SELECT') for sql, _ in conn.calls))

    def test_read_missing_row_is_absent_and_old_stopped_row_not_ready(self):
        conn = Connection({'relation': 'runtime_workers', 'server_epoch': 1.}, None)
        self.assertFalse(store.read_worker('local', conn=conn)['present'])
        row = db_row(heartbeat_epoch=99., status={'state': 'stopped', 'ready': True})
        conn = Connection({'relation': 'runtime_workers', 'server_epoch': 1.}, row)
        result = store.read_worker('local', conn=conn)
        self.assertTrue(result['fresh'])
        self.assertFalse(result['ready'])

    def test_heartbeat_cas_is_update_only_and_old_generation_is_rejected(self):
        token = store.WorkerGeneration('local', 'nonce-a', 3)
        conn = Connection(None)
        self.assertFalse(store.heartbeat(token, {'state': 'running', 'ready': True}, conn=conn))
        self.assertEqual(len(conn.calls), 1)
        sql, params = conn.calls[0]
        self.assertTrue(sql.startswith('UPDATE'))
        self.assertIn('instance_id = %s AND owner_nonce = %s AND generation = %s', sql)
        self.assertEqual(params[-3:], ('local', 'nonce-a', 3))
        self.assertNotIn('INSERT', sql)

    def test_successful_cas_returns_true_and_does_not_accept_secret_payload(self):
        conn = Connection({'generation': 3})
        result = store.heartbeat(store.WorkerGeneration('local', 'nonce-a', 3),
                                 {'state': 'running', 'password': 'sentinel-secret'}, conn=conn)
        self.assertTrue(result)
        self.assertNotIn('sentinel-secret', str(conn.calls))

    def test_begin_generation_is_atomic_idempotent_for_same_nonce(self):
        identity = {'host': 'host', 'pid': 22, 'process_start': 'start', 'mode': 'worker',
                    'release': 'abc', 'nonce': 'nonce-a', 'password': 'secret'}
        conn = Connection({'generation': 8})
        token = store.begin_generation('local', 'nonce-a', identity, conn=conn)
        self.assertEqual(token, store.WorkerGeneration('local', 'nonce-a', 8))
        sql, params = conn.calls[0]
        self.assertIn('ON CONFLICT (instance_id) DO UPDATE', sql)
        self.assertIn('owner_nonce = EXCLUDED.owner_nonce', sql)
        self.assertIn('generation + 1', sql)
        self.assertNotIn('secret', str(params))
        self.assertNotIn('CREATE', sql)

    def test_identity_web_and_nonce_mismatch_rejected(self):
        good = {'host': 'host', 'pid': 22, 'process_start': 'start', 'mode': 'worker', 'release': 'abc'}
        for values in [dict(good, mode='web'), dict(good, nonce='other'), dict(good, pid=True)]:
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, '^runtime_worker_invalid_identity$'):
                store.begin_generation('local', 'nonce-a', values, conn=Connection())

    def test_bootstrap_is_explicit_and_requires_transaction(self):
        conn = Connection()
        with patch.object(store.postgres_store, '_guard_production_schema'):
            store.ensure_tables(conn)
        self.assertEqual(len(conn.calls), 2)
        self.assertTrue(all(sql.startswith('CREATE') for sql, _ in conn.calls))
        conn.autocommit = True
        with self.assertRaisesRegex(ValueError, '^runtime_worker_transaction_required$'):
            store.ensure_tables(conn)

    def test_db_exception_is_fixed_and_has_no_sensitive_text(self):
        with self.assertRaisesRegex(store.RuntimeWorkerStoreError, '^runtime_worker_database_unavailable$') as result:
            store.read_worker('local', conn=Connection(error=RuntimeError('password=sentinel-secret')))
        self.assertNotIn('sentinel-secret', str(result.exception))


if __name__ == '__main__':
    unittest.main()
