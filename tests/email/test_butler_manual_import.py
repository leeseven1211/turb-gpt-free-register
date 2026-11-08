"""v2 人工导入按持久意图分配，未知结果及进程中断继续原租约。"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from cryptography.fernet import Fernet
from core.storage import records as record_store
from tests.support_pg import PostgresTestCase


class ButlerManualImportTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        from config import email as config
        from config.concurrency import policy_values
        from core.email.email_butler import manual_import, manual_import_v2, v2
        from core.storage import runtime_config

        self.service, self.impl, self.api = manual_import, manual_import_v2, v2
        encryption = patch.dict(os.environ, {'TURB_CONFIG_ENCRYPTION_KEY': Fernet.generate_key().decode()})
        encryption.start()
        self.addCleanup(encryption.stop)
        policy = policy_values({})
        policy.update(GLOBAL_TASK_WORKERS=4, EMAIL_IMPORT_WORKERS=4)
        runtime_config.write_values({key: str(value) for key, value in policy.items()}, activate=True, source='test')
        record_store.init()
        self.lock = threading.Lock()
        self.calls, self.intents = [], {}
        self.addresses = ['parent@icloud.com', 'parent+child@icloud.com']
        self.timeout_address = None
        self.reject_address = None
        self.wrong_identity = False
        self.me = {'client_id': 'fixture-client', 'allowed_services': ['openai'],
            'permissions': ['leases.create', 'leases.long_term', 'leases.read', 'codes.read'],
            'limits': {'idempotency_retention_seconds': 604800}}
        def save_secret(key, value):
            runtime_config.write_values({key: value}, source='test')
            os.environ[key] = value
            from config.runtime import reset_cache
            reset_cache()

        for target in [
            patch.multiple(config, EMAIL_BUTLER_API_BASE='https://original.example/v2',
                           EMAIL_BUTLER_API_KEY='fixture-secret', ICLOUD_HME_FORWARD_IMAP_EMAIL=''),
            patch('core.email.derivation._save_profile_secret',
                  side_effect=save_secret),
            patch.object(v2, 'me', side_effect=lambda **kwargs: deepcopy(self.me)),
            patch.object(v2, 'availability', side_effect=lambda *args, **kwargs:
                  {'service': 'openai', 'available': len(self.addresses)}),
            patch.object(v2, 'create_lease', side_effect=self.remote),
            patch.object(v2, 'get_lease', side_effect=lambda lease_id, **kwargs:
                  deepcopy(next(value for value in self.intents.values() if value['id'] == lease_id))),
            patch.object(manual_import, '_launch'),
        ]:
            target.start()
            self.addCleanup(target.stop)

    def lease(self, email, intent, *, provider='icloud_hme'):
        return {'id': 'lse_' + uuid.uuid5(uuid.NAMESPACE_URL, intent).hex,
            'email': email, 'provider': provider, 'service': 'openai', 'status': 'active',
            'created_at': '2026-11-08T00:00:00Z', 'expires_at': None,
            'client_id': self.me['client_id'], 'external_ref': intent}

    def remote(self, **kwargs):
        with self.lock:
            self.calls.append(deepcopy(kwargs))
            intent = kwargs['idempotency_key']
            if intent not in self.intents:
                email = self.addresses[len(self.intents)]
                self.intents[intent] = self.lease(email, intent,
                    provider=kwargs['provider'] if kwargs['provider'] != 'auto' else 'icloud_hme')
            lease = deepcopy(self.intents[intent])
        if lease['email'] == self.timeout_address:
            raise self.api.ButlerV2Error('request_timeout', '测试超时', retryable=True, request_unknown=True)
        if lease['email'] == self.reject_address:
            raise self.api.ButlerV2Error('permission_denied', '测试拒绝', status_code=403)
        if self.wrong_identity:
            lease['external_ref'] = 'different-intent'
        return lease

    def preview(self, count=2, **filters):
        return self.service.preview({'provider': 'icloud_hme', 'count': count, **filters})

    def create(self, count=2):
        preview = self.preview(count)
        request = {'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']}
        return self.service.create(request), request

    def items(self, batch):
        return record_store.list_rows(record_store.EMAIL_BUTLER_IMPORT_ITEMS,
            where='batch_id=%s', params=(batch['batch_id'],), order_by='position ASC')

    def run_batch(self, batch):
        self.service._run_batch(batch['batch_id'])
        return self.service.get(batch['batch_id'])

    def test_preview_is_read_only_and_does_not_claim_or_disclose_addresses(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': self.addresses[0], 'status': 'available'})
        result = self.preview()
        self.assertEqual((result['available'], result['selected']), (2, 2))
        self.assertEqual(result['items'], [])
        self.assertEqual(self.calls, [])
        self.assertEqual(record_store.count_rows(record_store.EMAIL_INBOX_PROFILES), 0)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_POOL), 0)

    def test_preview_accepts_unlimited_requested_count_without_snapshotting_addresses(self):
        self.addresses = [f'parent+large{index}@icloud.com' for index in range(5001)]
        result = self.preview(count=10000)
        self.assertEqual((result['count'], result['selected'], result['available']), (10000, 5001, 5001))
        snapshot = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, 'preview_token', result['preview_token'])
        self.assertEqual(snapshot['candidates'], [])
        self.assertEqual(snapshot['api_version'], 2)
        self.assertIsNone(self.service.options()['max_count'])

    def test_create_freezes_slots_and_request_replay_does_not_allocate_again(self):
        batch, request = self.create()
        frozen = self.items(batch)
        self.assertEqual([row['address_norm'] for row in frozen], ['', ''])
        self.assertTrue(all(row['idempotency_key'] == row['external_ref'] == row['acquisition_id'] for row in frozen))
        self.assertEqual(self.service.create(request)['batch_id'], batch['batch_id'])
        with self.assertRaisesRegex(ValueError, 'import_request_conflict'):
            self.service.create({**request, 'preview_token': self.preview()['preview_token']})
        self.assertEqual(self.calls, [])

    def test_success_imports_fixed_long_term_inventory_and_binding(self):
        batch, _ = self.create()
        result = self.run_batch(batch)
        self.assertEqual((result['imported'], result['status']), (2, 'completed'))
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_LEASE_BINDINGS), 2)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_CLAIM_INTENTS), 0)
        for item in self.items(batch):
            row = record_store.get_row(record_store.EMAIL_BUTLER_POOL, item['pool_id'])
            self.assertEqual(row['butler_handoff']['version'], 2)
            self.assertEqual(row['butler_handoff']['lease_id'], item['lease']['id'])
            self.assertFalse(row['service_fact_permanent'])
            self.assertIn('openai', row['service_tags'])

    def test_import_over_api_batch_size_uses_bounded_stable_individual_intents(self):
        self.addresses = [f'parent+large{index}@icloud.com' for index in range(201)]
        batch, _ = self.create(count=201)
        result = self.run_batch(batch)
        self.assertEqual(result['imported'], 201)
        self.assertEqual(len({call['idempotency_key'] for call in self.calls}), 201)
        self.assertTrue(all(call['ttl_seconds'] is None and call['service'] == 'openai' for call in self.calls))

    def test_timeout_preserves_original_slots_and_retry_does_not_replace(self):
        self.timeout_address = self.addresses[0]
        batch, _ = self.create()
        before = [(r['id'], r['idempotency_key']) for r in self.items(batch)]
        result = self.run_batch(batch)
        self.assertEqual((result['imported'], result['unknown']), (1, 1))
        self.timeout_address = None
        self.assertEqual(self.run_batch(batch)['imported'], 2)
        self.assertEqual(before, [(r['id'], r['idempotency_key']) for r in self.items(batch)])
        self.assertEqual(len(self.intents), 2)

    def test_remote_wait_does_not_hold_a_business_database_connection(self):
        original = self.remote
        def check(**kwargs):
            from core.storage import postgres
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute('SELECT 1')
                self.assertIsNotNone(cur.fetchone())
            return original(**kwargs)
        batch, _ = self.create()
        with patch.object(self.api, 'create_lease', side_effect=check):
            self.assertEqual(self.run_batch(batch)['imported'], 2)

    def test_retry_uses_original_route_and_key_after_global_config_changes(self):
        from config import email as config
        self.timeout_address = self.addresses[0]
        batch, _ = self.create()
        self.run_batch(batch)
        self.timeout_address = None
        with patch.multiple(config, EMAIL_BUTLER_API_BASE='https://replacement.example/v2', EMAIL_BUTLER_API_KEY='replacement'):
            self.assertEqual(self.run_batch(batch)['imported'], 2)
        self.assertTrue(all(call['api_base'] == 'https://original.example/v2' and call['api_key'] == 'fixture-secret' for call in self.calls))

    def test_receipt_identity_change_stays_unknown_and_never_publishes_stock(self):
        self.wrong_identity = True
        batch, _ = self.create()
        result = self.run_batch(batch)
        self.assertEqual(result['unknown'], 2)
        self.assertIn('handoff_identity_mismatch', result['error_counts'])
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_POOL), 0)

    def test_get_does_not_restart_interrupted_submissions_and_retry_recovers(self):
        self.timeout_address = self.addresses[0]
        batch, _ = self.create()
        self.run_batch(batch)
        count = len(self.calls)
        self.service.get(batch['batch_id'])
        self.assertEqual(len(self.calls), count)
        self.timeout_address = None
        self.service.retry(batch['batch_id'])
        self.service._launch.assert_called_with(batch['batch_id'])
        self.assertEqual(self.run_batch(batch)['imported'], 2)

    def test_remote_local_conflict_keeps_original_lease_and_never_releases(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': self.addresses[0], 'status': 'available'})
        batch, _ = self.create()
        with patch.object(self.api, 'release') as release:
            result = self.run_batch(batch)
        self.assertEqual((result['imported'], result['unknown']), (1, 1))
        self.assertEqual(result['error_counts']['local_email_conflict'], 1)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_LEASE_BINDINGS), 2)
        release.assert_not_called()

    def test_create_rejects_changed_connection_since_preview(self):
        from config import email as config
        snapshot = self.preview()
        with patch.object(config, 'EMAIL_BUTLER_API_KEY', 'changed'):
            with self.assertRaisesRegex(ValueError, 'import_snapshot_conflict'):
                self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': snapshot['preview_token']})
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_IMPORT_BATCHES), 0)

    def test_invalid_count_provider_and_unsupported_filters_never_call_remote(self):
        for count in (0, -1, True, '2', 1.5):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'invalid_import_count'):
                self.preview(count)
        for changes in ({'provider': 'unknown'}, {'identity_type': 'primary'}, {'domain': 'icloud.com'}, {'group': 'private'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.preview(**changes)
        self.api.me.assert_not_called()

    def test_two_workers_cannot_own_the_same_batch(self):
        batch, _ = self.create()
        entered, release = threading.Event(), threading.Event()
        original = self.remote
        def slow(**kwargs):
            entered.set()
            release.wait(5)
            return original(**kwargs)
        with patch.object(self.api, 'create_lease', side_effect=slow), ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self.service._run_batch, batch['batch_id'])
            self.assertTrue(entered.wait(5))
            second = executor.submit(self.service._run_batch, batch['batch_id'])
            second.result(5)
            release.set()
            first.result(10)
        self.assertEqual(len(self.calls), 2)

    def test_parallel_import_finishes_other_items_while_one_request_waits(self):
        batch, _ = self.create()
        entered, release = threading.Event(), threading.Event()
        original = self.remote
        def slow(**kwargs):
            if kwargs['idempotency_key'] == self.items(batch)[0]['idempotency_key']:
                entered.set()
                release.wait(5)
            return original(**kwargs)
        with patch.object(self.api, 'create_lease', side_effect=slow), ThreadPoolExecutor(max_workers=1) as executor:
            worker = executor.submit(self.service._run_batch, batch['batch_id'])
            self.assertTrue(entered.wait(5))
            deadline = time.monotonic() + 4
            while self.service.get(batch['batch_id'])['imported'] != 1 and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertEqual(self.service.get(batch['batch_id'])['imported'], 1)
            release.set()
            worker.result(10)

    def test_global_capacity_blocks_network_before_submitting(self):
        batch, _ = self.create()
        stop = threading.Event()
        from core.operations import concurrency
        from core.storage import runtime_config
        runtime_config.write_values({'GLOBAL_TASK_WORKERS': '1'}, source='test')
        occupied = concurrency.try_admit_and_claim(execution_key='fixture:busy', task_type='email_import',
            claim=lambda conn, execution_id: {'execution_id': execution_id})
        self.assertIsNotNone(occupied.context)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                worker = executor.submit(self.service._run_batch, batch['batch_id'])
                deadline = time.monotonic() + 3
                while not self.service.get(batch['batch_id'])['blocked_by'] and time.monotonic() < deadline:
                    stop.wait(.02)
                self.assertTrue(self.service.get(batch['batch_id'])['blocked_by'])
                self.assertEqual(self.calls, [])
                self.assertTrue(all(row['status'] == 'pending' for row in self.items(batch)))
                concurrency.release_execution(occupied.context, reason='test')
                worker.result(15)
        finally:
            concurrency.release_execution(occupied.context, reason='test')

    def test_profile_no_longer_requires_final_mailbox(self):
        batch, _ = self.create()
        saved = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'batch_id', batch['batch_id'])
        profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, saved['profile_id'])
        self.assertEqual(profile['api_version'], 2)
        self.assertEqual(profile['inbox_locator']['api_base'], 'https://original.example/v2')
        self.assertNotIn('mailbox_email', profile['inbox_locator'])

    def test_owner_claim_store_outage_retries_same_batch(self):
        from psycopg import OperationalError
        batch, _ = self.create()
        original = self.service._claim_batch_owner
        def claim(value):
            if not getattr(claim, 'called', False):
                claim.called = True
                raise OperationalError('fixture')
            return original(value)
        with patch.object(self.service, '_claim_batch_owner', side_effect=claim):
            self.assertEqual(self.run_batch(batch)['imported'], 2)
        self.assertEqual(len(self.intents), 2)

    def test_errors_are_classified_without_exposing_addresses(self):
        self.timeout_address, self.reject_address = self.addresses
        batch, _ = self.create()
        result = self.run_batch(batch)
        self.assertEqual((result['unknown'], result['failed']), (1, 1))
        self.assertEqual(result['error_counts'], {'request_timeout': 1, 'permission_denied': 1})
        self.assertNotIn('@', str(result['error_counts']))

    def test_startup_marks_interrupted_batch_and_keeps_original_intents(self):
        batch, _ = self.create()
        before = [r['idempotency_key'] for r in self.items(batch)]
        self.assertEqual(self.service.reconcile_interrupted(), 1)
        self.assertEqual(self.service.get(batch['batch_id'])['status'], 'partial')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.run_batch(batch)['imported'], 2)
        self.assertEqual(before, [r['idempotency_key'] for r in self.items(batch)])

    def test_startup_completes_imports_committed_before_summary(self):
        batch, _ = self.create()
        self.run_batch(batch)
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'batch_id', batch['batch_id'])
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, row['id'], {'status': 'running'})
        self.assertEqual(self.service.reconcile_interrupted(), 1)
        self.assertEqual(self.service.get(batch['batch_id'])['status'], 'completed')
        self.assertEqual(len(self.calls), 2)

    def test_batch_classifies_storage_and_policy_failures(self):
        from psycopg import OperationalError
        self.assertEqual(self.service._batch_error_code(OperationalError('fixture')), 'import_storage_unavailable')
        self.assertEqual(self.service._batch_error_code(ValueError('fixed_route_unavailable')), 'fixed_route_unavailable')
        self.assertEqual(self.service._batch_error_code(RuntimeError('fixture')), 'import_internal_error')

    def test_client_change_blocks_original_batch_without_allocating(self):
        batch, _ = self.create()
        self.me['client_id'] = 'replacement-client'
        result = self.run_batch(batch)
        self.assertEqual(result['error_code'], 'handoff_contract_unsupported')
        self.assertTrue(result['can_retry'])
        self.assertEqual(self.calls, [])

    def test_startup_does_not_pause_active_worker(self):
        batch, _ = self.create()
        owner = self.service._claim_batch_owner(batch['batch_id'])
        try:
            self.assertEqual(self.service.reconcile_interrupted(), 0)
            self.assertEqual(self.service.get(batch['batch_id'])['status'], 'running')
        finally:
            self.service._release_batch_owner(owner)

    def test_expired_or_empty_preview_does_not_save_profile_or_batch(self):
        snapshot = self.preview()
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, 'preview_token', snapshot['preview_token'])
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, row['id'], {'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)})
        with self.assertRaisesRegex(ValueError, 'import_preview_expired'):
            self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': snapshot['preview_token']})
        self.addresses = []
        with self.assertRaisesRegex(ValueError, 'import_preview_empty'):
            self.create()
        self.assertEqual(record_store.count_rows(record_store.EMAIL_INBOX_PROFILES), 0)

    def test_preview_requires_openai_and_long_term_permissions(self):
        for field, value in [('allowed_services', ['grok']), ('permissions', ['leases.create']),
                             ('permissions', ['leases.create', 'leases.long_term', 'codes.read']),
                             ('permissions', ['leases.create', 'leases.long_term', 'leases.read'])]:
            original = self.me[field]
            self.me[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'handoff_contract_unsupported'):
                self.preview()
            self.me[field] = original
        self.assertEqual(self.calls, [])

    def test_repeated_local_conflict_reuses_saved_lease_without_another_post(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': self.addresses[0], 'status': 'available'})
        batch, _ = self.create()
        self.run_batch(batch)
        self.assertEqual(len(self.calls), 2)
        result = self.run_batch(batch)
        self.assertEqual((result['unknown'], result['imported']), (1, 1))
        self.assertEqual(len(self.calls), 2)

    def test_late_rejection_cannot_erase_prior_unknown_result(self):
        self.timeout_address = self.addresses[0]
        batch, _ = self.create()
        self.run_batch(batch)
        self.timeout_address, self.reject_address = None, self.addresses[0]
        result = self.run_batch(batch)
        self.assertEqual((result['unknown'], result['failed']), (1, 0))

    def test_definitive_rejection_is_terminal_without_replacement(self):
        self.reject_address = self.addresses[0]
        batch, _ = self.create()
        result = self.run_batch(batch)
        self.assertEqual((result['imported'], result['failed']), (1, 1))
        self.assertFalse(result['can_retry'])
        self.assertEqual(len(self.intents), 2)

    def test_all_providers_publish_eligible_v2_inventory(self):
        from core.email import inventory
        for index, provider in enumerate(('icloud_hme', 'outlook_graph', 'cloudflare', 'mailcom')):
            self.addresses = [f'provider{index}@example.test']
            self.intents = {}
            snapshot = self.preview(count=1, provider=provider)
            batch = self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': snapshot['preview_token']})
            self.assertEqual(self.run_batch(batch)['imported'], 1)
        self.assertEqual(inventory.summary('email_butler')['available'], 4)

    def test_expired_idempotency_window_only_recovers_by_original_external_ref(self):
        self.timeout_address = self.addresses[0]
        batch, _ = self.create(count=1)
        self.run_batch(batch)
        item = self.items(batch)[0]
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item['id'],
            {'first_submitted_at': (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()})
        self.timeout_address = None
        with patch.object(self.api, 'list_leases', return_value=[self.intents[item['idempotency_key']]]) as lookup:
            self.assertEqual(self.run_batch(batch)['imported'], 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(lookup.call_args.kwargs['external_ref'], item['external_ref'])

    def test_expired_idempotency_without_unique_original_never_reallocates(self):
        self.timeout_address = self.addresses[0]
        batch, _ = self.create(count=1)
        self.run_batch(batch)
        item = self.items(batch)[0]
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item['id'],
            {'first_submitted_at': (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()})
        with patch.object(self.api, 'list_leases', return_value=[]):
            result = self.run_batch(batch)
        self.assertEqual(result['error_counts'], {'idempotency_result_expired': 1})
        self.assertTrue(result['can_retry'])
        self.assertEqual(len(self.calls), 1)

    def test_legacy_unknown_batch_only_resolves_original_address(self):
        from core.email.email_butler import lease_bindings
        batch, _ = self.create(count=1)
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'batch_id', batch['batch_id'])
        item = self.items(batch)[0]
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, row['id'], {'api_version': 1})
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item['id'],
            {'address_norm': self.addresses[0], 'status': 'unknown'})
        original = self.lease(self.addresses[0], item['acquisition_id'])
        with patch.object(lease_bindings, 'resolve', return_value={**original, 'lease_id': original['id']}) as resolve:
            self.assertEqual(self.run_batch(batch)['imported'], 1)
        self.assertEqual(resolve.call_args.args, (self.addresses[0],))
        self.assertEqual(resolve.call_args.kwargs['acquisition_id'], item['acquisition_id'])
        self.assertEqual(self.calls, [])

    def test_pasted_complete_address_only_restores_existing_long_term_lease(self):
        from core.email.email_butler import lease_bindings
        from core.storage.email import local_imports
        original = self.lease('existing@example.test', 'old-acquisition')
        with patch.object(lease_bindings, 'resolve', return_value={**original, 'lease_id': original['id']}):
            inserted, skipped = local_imports.import_resources([{'email': original['email']}], source='email_butler')
        self.assertEqual((inserted, skipped), (1, 0))
        self.assertEqual(self.calls, [])
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', original['email'])
        self.assertEqual(row['lease_id'], original['id'])

    def test_saved_conflicting_lease_is_revalidated_before_publishing(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': self.addresses[0], 'status': 'available'})
        batch, _ = self.create(count=1)
        self.run_batch(batch)
        item = self.items(batch)[0]
        self.intents[item['idempotency_key']]['status'] = 'revoked'
        self.api.get_lease.reset_mock()
        result = self.run_batch(batch)
        self.assertEqual(result['unknown'], 1)
        self.assertEqual(result['imported'], 0)
        self.api.get_lease.assert_called_once_with(item['lease']['id'],
            api_base='https://original.example/v2', api_key='fixture-secret')
        self.assertEqual(len(self.calls), 1)

    def test_legacy_merged_read_binding_cannot_gain_release_permission_during_import(self):
        from core.email.email_butler import lease_bindings
        batch, _ = self.create(count=1)
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'batch_id', batch['batch_id'])
        item = self.items(batch)[0]
        address = self.addresses[0]
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, row['id'], {'api_version': 1})
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item['id'],
            {'address_norm': address, 'status': 'unknown'})
        merged = self.lease(address, 'merged-read-binding')
        with patch.object(self.api, 'list_leases', return_value=[merged]), \
                patch.object(self.api, 'get_lease', return_value=merged):
            self.assertEqual(self.run_batch(batch)['imported'], 1)
            binding = record_store.list_rows(record_store.EMAIL_BUTLER_LEASE_BINDINGS)[0]
            self.assertFalse(binding['original_ref_verified'])
            self.assertNotIn(item['acquisition_id'], binding['verified_acquisition_refs'])
            pool = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address)
            self.assertFalse(pool['butler_handoff']['original_ref_verified'])
            with self.assertRaises(self.api.ButlerV2Error) as error:
                lease_bindings.resolve(address, api_base='https://original.example/v2', api_key='fixture-secret',
                    acquisition_id=item['acquisition_id'], lease_id=merged['id'], for_release=True)
            self.assertEqual(error.exception.error_code, 'lease_original_mapping_required')
        self.assertEqual(self.calls, [])

    def test_pasted_read_only_binding_does_not_fabricate_a_verified_acquisition(self):
        from core.email.email_butler import lease_bindings
        from core.storage.email import local_imports
        original = {**self.lease('existing-read@example.test', 'merged-read-binding'),
            'lease_id': 'lse_existing_read', 'acquisition_id': '', 'original_ref_verified': False,
            'verified_acquisition_refs': []}
        with patch.object(lease_bindings, 'resolve', return_value=original):
            inserted, _ = local_imports.import_resources([{'email': original['email']}], source='email_butler')
        self.assertEqual(inserted, 1)
        pool = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', original['email'])
        self.assertFalse(pool['butler_handoff']['original_ref_verified'])
        self.assertEqual(pool['butler_handoff']['verified_acquisition_refs'], [])

    def test_worker_can_finish_with_one_business_database_connection(self):
        from core.storage import postgres
        postgres.close_pools()
        try:
            with patch.dict(os.environ, {'TURB_DB_POOL_MAX': '1'}):
                batch, _ = self.create()
                self.assertEqual(self.run_batch(batch)['imported'], 2)
        finally:
            postgres.close_pools()

    def test_parallel_remote_wait_does_not_exhaust_a_small_business_pool(self):
        from core.storage import postgres
        postgres.close_pools()
        self.addresses = [f'parent+small{index}@icloud.com' for index in range(6)]
        two_started, release = threading.Event(), threading.Event()
        monitor = threading.Lock()
        active = peak = 0
        original = self.remote
        def held_remote(**kwargs):
            nonlocal active, peak
            with monitor:
                active += 1
                peak = max(peak, active)
                if active >= 2:
                    two_started.set()
            try:
                release.wait(5)
                return original(**kwargs)
            finally:
                with monitor:
                    active -= 1
        try:
            with patch.dict(os.environ, {'TURB_DB_POOL_MAX': '2'}):
                batch, _ = self.create(count=6)
                with patch.object(self.api, 'create_lease', side_effect=held_remote), ThreadPoolExecutor(max_workers=1) as pool:
                    worker = pool.submit(self.service._run_batch, batch['batch_id'])
                    try:
                        self.assertTrue(two_started.wait(3))
                    finally:
                        release.set()
                        worker.result(15)
                self.assertEqual(self.service.get(batch['batch_id'])['imported'], 6)
                self.assertGreaterEqual(peak, 2)
                self.assertLessEqual(peak, 4)
        finally:
            postgres.close_pools()
