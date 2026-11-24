"""邮箱池集合写入保留墓碑与租约证据，分块提交只确认已落库结果。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
import uuid

from flask import Flask

from core.operations.bulk_mutations import execute_chunked_bulk
from core.storage import records as store, registration
from tests.support_pg import PostgresTestCase
from webui.routes import email_pool


def mutations():
    from core.storage.email import bulk_mutations
    return bulk_mutations


class EmailPoolBulkMutationTests(PostgresTestCase):
    def setUp(self):
        store.init()
        registration.reset_ready()
        registration.init()

    def row(self, source, email, **changes):
        specs = {'outlook': store.OUTLOOK_POOL, 'generic_api': store.GENERIC_API_POOL,
            'cloudflare_domain': store.DOMAIN_POOL, 'icloud_hide': store.ICLOUD_HIDE_POOL,
            'email_butler': store.EMAIL_BUTLER_POOL}
        payload = {'email': email, 'status': 'available', **changes}
        if source == 'email_butler':
            profile = store.insert_row(store.EMAIL_INBOX_PROFILES, {
                'inbox_key': uuid.uuid4().hex, 'revision': 1, 'connector': 'forward_butler',
                'state': 'active', 'credential_ref': 'BULK_TEST_KEY',
                'inbox_locator': {'api_base': 'https://fixture.test/v2'}})
            payload.update(inbox_profile_id=profile, butler_handoff={
                'lease_id': 'original-lease', 'acquisition_id': 'original-acquisition',
                'client_id': 'original-client', 'version': 2, 'state': 'issued',
                'service': 'openai', 'email': email, 'expires_at': None})
        row_id = store.insert_row(specs[source], payload)
        return specs[source], row_id

    def test_status_groups_sources_deduplicates_and_skips_missing_or_tombstoned_rows(self):
        fixtures = [self.row(source, f'{source}@example.test') for source in (
            'outlook', 'generic_api', 'cloudflare_domain', 'icloud_hide', 'email_butler')]
        tombstone = self.row('outlook', 'deleted@example.test', status='tombstone')
        result = mutations().update_status_many([
            {'source': source, 'email': f'{source}@example.test'} for source in (
                'outlook', 'generic_api', 'cloudflare_domain', 'icloud_hide', 'email_butler')]
            + [{'source': 'outlook', 'email': 'OUTLOOK@example.test'},
               {'source': 'outlook', 'email': 'missing@example.test'},
               {'source': 'outlook', 'email': 'deleted@example.test'}], 'disabled', '手工停用')
        self.assertEqual(len(result), 7)
        self.assertEqual([item.status for item in result], ['updated'] * 5 + ['skipped', 'skipped'])
        self.assertEqual([item.reason_code for item in result[-2:]], ['email_not_found', 'local_email_deleted'])
        for spec, row_id in fixtures:
            row = store.get_row(spec, row_id)
            self.assertEqual((row['status'], row['note']), ('disabled', '手工停用'))
            self.assertTrue(row['used_at'])
        self.assertEqual(store.get_row(*tombstone)['status'], 'tombstone')
        self.assertEqual(store.get_row(*fixtures[3])['disabled_reason'], 'manual')
        mutations().update_status_many(['icloud_hide:icloud_hide@example.test'], 'available')
        self.assertIsNone(store.get_row(*fixtures[3])['disabled_reason'])

    def test_status_keeps_existing_manual_reset_rules_and_blocks_pending_or_replaced(self):
        evidence = (
            ('registered', {'status': 'failed', 'access_token': 'fixture-at'}, 'updated', None),
            ('unknown', {'status': 'request_unknown'}, 'updated', None),
            ('claimed', {'status': 'used', 'used_at': '2026-11-01T00:00:00'}, 'updated', None),
            ('replaced', {'status': 'replaced'}, 'skipped', 'email_replaced'),
            ('pending', {'status': 'pending_sync'}, 'skipped', 'service_fact_sync_pending'),
        )
        rows = [self.row('outlook', name + '@example.test', **payload) for name, payload, _, _ in evidence]
        result = mutations().update_status_many([name + '@example.test' for name, _, _, _ in evidence], 'available', None)
        self.assertEqual([(item.status, item.reason_code) for item in result],
            [(status, reason) for _, _, status, reason in evidence])
        self.assertEqual([store.get_row(*row)['status'] for row in rows],
            ['available', 'available', 'available', 'replaced', 'pending_sync'])
        self.assertTrue(all(store.get_row(*row)['used_at'] is None for row in rows[:3]))

    def test_delete_preserves_registered_and_unknown_lease_and_is_replayable(self):
        from core.email.email_butler import service_facts
        unused = self.row('email_butler', 'unused@example.test')
        unknown = self.row('email_butler', 'unknown@example.test', status='request_unknown')
        protected = self.row('generic_api', 'registered@example.test')
        store.insert_row(store.ACCOUNTS, {'email': 'registered@example.test', 'access_token': 'fixture-at'})
        targets = ['email_butler:unused@example.test', 'email_butler:unknown@example.test',
            'generic_api:registered@example.test', 'outlook:missing@example.test']
        result = mutations().delete_many(targets)
        self.assertEqual([item.status for item in result], ['updated', 'updated', 'skipped', 'skipped'])
        self.assertEqual(result[2].reason_code, 'registration_confirmed')
        self.assertEqual(store.get_row(*unused)['status'], 'tombstone')
        self.assertEqual(store.get_row(*unknown)['status'], 'tombstone')
        self.assertEqual(store.get_row(*protected)['status'], 'available')
        self.assertEqual(service_facts.sync_status('email_butler', 'unused@example.test')['state'], 'pending')
        sync = service_facts.sync_status('email_butler', 'unknown@example.test')
        self.assertEqual((sync['state'], sync['error_code'], sync['lease_retained']),
            ('local_only', 'registration_result_unverified', True))
        replay = mutations().delete_many(targets[:2])
        self.assertTrue(all(item.status == 'updated' for item in replay))
        self.assertEqual(len(store.list_rows(store.EMAIL_SERVICE_SYNC)), 2)

    def test_delete_shared_transaction_failure_preserves_only_previously_committed_chunk(self):
        rows = [self.row('outlook', f'chunk{number}@example.test') for number in range(4)]
        targets = tuple(f'outlook:chunk{number}@example.test' for number in range(4))
        calls = 0
        def apply(chunk):
            nonlocal calls
            calls += 1
            with store.transaction() as conn:
                results = mutations().delete_many(chunk, conn=conn)
                if calls == 2:
                    raise RuntimeError('injected failure before block receipt')
                return results
        result = execute_chunked_bulk('email_pool_delete', targets, apply, chunk_size=2)
        self.assertEqual((result.updated_count, result.failed_count), (2, 2))
        self.assertEqual([store.get_row(*row)['status'] for row in rows],
            ['tombstone', 'tombstone', 'available', 'available'])
        readback = mutations().delete_many(targets[:2])
        self.assertTrue(all(item.status == 'updated' for item in readback))

    def test_delete_keeps_parent_recovery_and_every_historical_case_variant(self):
        first = self.row('outlook', 'Case@example.test')
        second = self.row('outlook', 'case@example.test')
        parent = self.row('icloud_hide', 'parent@example.test', password='recovery-material')
        child = store.insert_row(store.EMAIL_ADDRESS_ALLOCATIONS, {
            'address': 'parent+child@example.test', 'address_norm': 'parent+child@example.test',
            'source': 'icloud_hide', 'parent_kind': 'pool', 'parent_id': parent[1],
            'parent_address': 'parent@example.test', 'inbox_profile_id': 1,
            'strategy': 'plus_tag', 'tag': 'child', 'state': 'used', 'account_id': 42})
        result = mutations().delete_many(['outlook:case@example.test', 'icloud_hide:parent@example.test'])
        self.assertEqual([item.status for item in result], ['updated', 'updated'])
        self.assertEqual([store.get_row(*row)['status'] for row in (first, second)], ['tombstone', 'tombstone'])
        row = store.get_row(*parent)
        self.assertEqual((row['status'], row['password'], row['derivation_policy']['enabled']),
            ('disabled', 'recovery-material', False))
        self.assertTrue(row['pool_deleted_at'])
        self.assertEqual(store.get_row(store.EMAIL_ADDRESS_ALLOCATIONS, child)['account_id'], 42)

    def test_committed_email_chunk_can_refresh_compatibility_outputs(self):
        import os
        from core.storage import compat_export
        generic = self.row('generic_api', 'export@example.test')
        snapshots = []
        with patch.dict(os.environ, {'COMPAT_EXPORT_MODE': 'sync'}), patch.dict(compat_export._EXPORTERS,
                {'generic_api_emails': lambda: snapshots.append(store.get_row(*generic)['status'])}):
            with store.transaction() as conn:
                results = mutations()._handle_status_chunk(('generic_api:export@example.test',),
                    {'status': 'disabled'}, conn=conn)
            self.assertEqual(snapshots, [])
            mutations()._after_commit(('generic_api:export@example.test',), {'status': 'disabled'}, results)
        self.assertEqual(snapshots, ['disabled'])

    def test_derived_status_rejects_bound_and_retired_addresses_without_recycling_them(self):
        ids = []
        for number, payload in enumerate(({'state': 'available'}, {'state': 'used', 'account_id': 7},
                                         {'state': 'retired'})):
            ids.append(store.insert_row(store.EMAIL_ADDRESS_ALLOCATIONS, {
                'address': f'child{number}@example.test', 'address_norm': f'child{number}@example.test',
                'source': 'outlook', 'parent_kind': 'pool', 'parent_id': 1,
                'parent_address': 'parent@example.test', 'inbox_profile_id': 1,
                'strategy': 'plus_tag', 'tag': str(number), **payload}))
        results = mutations().update_derivation_status_many(ids + [ids[0], 9999], 'disabled')
        self.assertEqual([item.status for item in results], ['updated', 'skipped', 'skipped', 'skipped'])
        self.assertEqual([store.get_row(store.EMAIL_ADDRESS_ALLOCATIONS, row_id)['state'] for row_id in ids],
            ['disabled', 'used', 'retired'])


class TestEmailPoolBulkRoutes:
    def test_empty_bulk_storage_command_has_no_side_effects(self):
        assert mutations().update_status_many([], 'disabled', None) == ()
        assert mutations().delete_many([]) == ()
        assert mutations().update_derivation_status_many([], 'disabled') == ()

    def client(self):
        import logging
        app = Flask(__name__)
        app.register_blueprint(email_pool.create_email_pool_blueprint(SimpleNamespace(logger=logging.getLogger('test'))))
        return app.test_client()

    def test_bulk_status_accepts_durable_command_without_reading_or_writing_pool(self):
        with patch('core.operations.bulk_mutation_worker.submit_bulk_mutation', return_value={
                'accepted': True, 'task_id': 12, 'run_id': 19}) as submit, \
             patch.object(email_pool, '_pool_row_for_source', side_effect=AssertionError('request did pool IO')):
            response = self.client().post('/api/outlook/status-bulk', headers={'Idempotency-Key': 'email-status-1'},
                json={'items': [{'source': 'generic_api', 'email': 'One@Example.test'},
                    {'source': 'generic_api', 'email': 'one@example.test'}], 'status': 'disabled', 'note': '停用'})
        assert response.status_code == 202
        assert response.json['accepted'] is True
        assert response.json['task_id'] == 12
        assert submit.call_args.args == ('email_pool_status', ['generic_api:one@example.test', 'generic_api:one@example.test'],
            {'status': 'disabled', 'note': '停用'})
        assert submit.call_args.kwargs['idempotency_key'] == 'email-status-1'

    def test_bulk_delete_accepts_command_and_derived_route_stays_managed_by_butler(self):
        with patch('core.operations.bulk_mutation_worker.submit_bulk_mutation', return_value={
                'accepted': True, 'task_id': 13, 'run_id': 20}) as submit, \
             patch.object(email_pool, '_pool_row_for_source', side_effect=AssertionError('request did pool IO')):
            response = self.client().post('/api/outlook/delete-bulk',
                json={'source': 'icloud_hide', 'emails': ['ONE@example.test', 'one@example.test']})
        assert response.status_code == 202
        assert submit.call_args.args == ('email_pool_delete', ['icloud_hide:one@example.test', 'icloud_hide:one@example.test'], {})
        assert self.client().post('/api/email-derivation/status-bulk', json={'ids': [1], 'state': 'available'}).status_code == 410
