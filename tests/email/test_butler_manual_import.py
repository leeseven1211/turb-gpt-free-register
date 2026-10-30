"""Fixed HME import batches survive uncertain remote outcomes and restarts."""
import importlib.util
import os
import uuid
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.storage import records as record_store, postgres as postgres_store
from tests.support_pg import PostgresTestCase


class ButlerManualImportTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.assertIsNotNone(importlib.util.find_spec('core.email.email_butler.manual_import'),
                             'manual import batch service is missing')
        from core.email.email_butler import manual_import as service
        from config import email as config
        self.service = service
        record_store.init()
        self.calls = []
        self.addresses = ['parent@icloud.com', 'parent+child@icloud.com']
        self.timeout_address = None
        self.reject_address = None
        self.wrong_identity = False
        self.bulk_supported = False
        for target in [
            patch.multiple(config, EMAIL_BUTLER_API_BASE='https://original.example/v1',
                           EMAIL_BUTLER_API_KEY='fixture-secret', ICLOUD_HME_FORWARD_IMAP_EMAIL='final@example.test'),
            patch('core.email.derivation._save_profile_secret', side_effect=lambda k, v: os.environ.__setitem__(k, v)),
            patch('core.email.email_butler.inventory_handoff._consumer_instance', return_value='fixture-instance'),
            patch('core.email.email_butler.client._request', side_effect=self.remote),
            patch.object(service, '_launch'),
        ]:
            target.start()
            self.addCleanup(target.stop)

    def candidate(self, email):
        return {'email': email, 'provider': 'icloud_hme', 'identity_id': 'identity:' + email,
                'identity_type': 'plus_alias' if '+' in email else 'primary',
                'parent_email': 'parent@icloud.com', 'mailbox_email': 'final@example.test',
                'recipient_mode': 'forwarded_exact_v1', 'strict_family': True}

    def remote(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == '/me':
            return {'code': 200, 'id': 'fixture-client', 'policy': {'consumer': 'turb', 'service': 'openai'},
                    'capabilities': ['mailboxes.acquisition.v1', 'inbound.recipient_evidence.v1']
                    + (['mailboxes.import_batch.v1'] if self.bulk_supported else [])}
        if path == '/mailboxes/import-candidates':
            self.assertEqual(method, 'GET')
            return {'code': 200, 'supported': True, 'policy_applied': True,
                    'total_available': len(self.addresses), 'returned': len(self.addresses),
                    'candidates': [self.candidate(email) for email in self.addresses]}
        if path == '/mailboxes/import-batch':
            results = []
            for item in kwargs['json']['items']:
                email = item['requested_email']
                if email == self.timeout_address:
                    raise TimeoutError('测试批量响应中断')
                result = {'requested_email': email, 'acquisition_id': item['acquisition_id']}
                if email == self.reject_address:
                    result.update(code=409, error_code='acquisition_conflict')
                else:
                    mailbox = {**self.candidate(email), 'lease_id': 'ephemeral-read-lease'}
                    if self.wrong_identity:
                        mailbox['identity_id'] = 'replacement-identity'
                    result.update(code=200, mailbox=mailbox)
                results.append(result)
            return {'code': 200, 'results': list(reversed(results))}
        self.assertEqual((method, path), ('POST', '/mailboxes'))
        email = kwargs['json']['requested_email']
        self.assertIn('acquisition_id', kwargs['json'])
        if email == self.timeout_address:
            raise TimeoutError('private upstream details must not escape')
        if email == self.reject_address:
            from core.email.email_butler.client import EmailButlerClientError
            raise EmailButlerClientError('private rejection', status_code=409)
        item = self.candidate(email)
        item['lease_id'] = 'ephemeral-read-lease'
        if self.wrong_identity:
            item['identity_id'] = 'replacement-identity'
        return {'code': 200, 'mailbox': item}

    def preview(self, count=2):
        return self.service.preview({'provider': 'icloud_hme', 'identity_type': 'all', 'count': count})

    def create(self):
        preview = self.preview()
        request = {'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']}
        return self.service.create(request), request

    def items(self, batch):
        return record_store.list_rows(record_store.EMAIL_BUTLER_IMPORT_ITEMS,
                                      where='batch_id = %s', params=(batch['batch_id'],), order_by='position ASC')

    def test_preview_is_read_only_and_excludes_cross_source_addresses(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': self.addresses[0], 'status': 'available'})
        result = self.preview()
        self.assertEqual((result['available'], result['selected']), (1, 1))
        self.assertEqual(result['items'], [{'email': self.addresses[1], 'identity_type': 'plus_alias'}])
        self.assertEqual(record_store.count_rows(record_store.EMAIL_INBOX_PROFILES), 0)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_POOL), 0)
        self.assertTrue(all(method == 'GET' for method, _, _ in self.calls))

    def test_create_freezes_candidates_and_request_replay_does_not_select_again(self):
        batch, request = self.create()
        frozen = self.items(batch)
        self.assertEqual([row['address_norm'] for row in frozen], self.addresses)
        self.assertTrue(all(row['acquisition_id'] and row['status'] == 'pending' for row in frozen))
        self.assertEqual(self.service.create(request)['batch_id'], batch['batch_id'])
        other = self.preview()
        with self.assertRaisesRegex(ValueError, 'import_request_conflict'):
            self.service.create({**request, 'preview_token': other['preview_token']})
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_IMPORT_BATCHES), 1)

    def test_success_imports_permanent_fixed_inventory_without_legacy_claims(self):
        batch, _ = self.create()
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['status'], result['imported'], result['total']), ('completed', 2, 2))
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_CLAIM_INTENTS), 0)
        from core.email.inventory import summary
        self.assertEqual(summary('email_butler')['available'], 2)
        self.assertNotIn('icloud.com', str(result))
        self.assertNotIn('fixture-secret', str(result))

    def test_bulk_import_splits_200_addresses_into_eight_requests(self):
        self.bulk_supported = True
        self.addresses = [f'parent+batch{index}@icloud.com' for index in range(200)]
        preview = self.preview(count=200)
        batch = self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']})
        self.calls.clear()
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['status'], result['imported']), ('completed', 200))
        writes = [(path, kwargs) for _, path, kwargs in self.calls if path.startswith('/mailboxes')]
        self.assertEqual([path for path, _ in writes], ['/mailboxes/import-batch'] * 8)
        self.assertEqual([len(kwargs['json']['items']) for _, kwargs in writes], [25] * 8)

    def test_bulk_timeout_preserves_original_items_and_retry_does_not_replace(self):
        self.bulk_supported = True
        batch, _ = self.create()
        self.timeout_address = self.addresses[1]
        self.service._run_batch(batch['batch_id'])
        self.assertEqual(self.service.get(batch['batch_id'])['unknown'], 2)
        self.timeout_address = None
        self.reject_address = self.addresses[1]
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['imported'], result['unknown'], result['failed']), (1, 1, 0))
        writes = [kwargs['json'] for _, path, kwargs in self.calls if path == '/mailboxes/import-batch']
        self.assertEqual(writes[0], writes[1])
        self.reject_address = None
        self.service._run_batch(batch['batch_id'])
        self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)

    def test_handoff_wait_does_not_hold_a_business_database_connection(self):
        batch, _ = self.create()
        from psycopg.rows import dict_row
        def remote_without_transaction(method, path, **kwargs):
            if path == '/mailboxes':
                business_pool = postgres_store._pool_for(postgres_store.database_url(), {'row_factory': dict_row})
                stats = business_pool.get_stats()
                self.assertEqual(stats['pool_available'], stats['pool_size'],
                                 '等待远端交接时应归还业务数据库连接')
            return self.remote(method, path, **kwargs)
        postgres_store.close_pools()
        try:
            with patch.dict(os.environ, {'TURB_DB_POOL_MAX': '1'}), \
                 patch('core.email.email_butler.client._request', side_effect=remote_without_transaction):
                self.service._run_batch(batch['batch_id'])
            self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)
        finally:
            postgres_store.close_pools()

    def test_timeout_keeps_prior_success_and_retry_uses_original_route_and_acquisition(self):
        batch, _ = self.create()
        self.timeout_address = self.addresses[1]
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['status'], result['imported'], result['unknown']), ('partial', 1, 1))
        original = self.items(batch)[1]
        from config import email as config
        config.EMAIL_BUTLER_API_BASE = 'https://changed.example/v1'
        config.EMAIL_BUTLER_API_KEY = 'changed-secret'
        config.ICLOUD_HME_FORWARD_IMAP_EMAIL = 'changed@example.test'
        self.timeout_address = None
        self.service.retry(batch['batch_id'])
        self.service._run_batch(batch['batch_id'])
        self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)
        writes = [kwargs for method, path, kwargs in self.calls if path == '/mailboxes' and
                  kwargs['json']['requested_email'] == self.addresses[1]]
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0]['json'], writes[1]['json'])
        self.assertEqual(writes[1]['api_base'], 'https://original.example/v1')
        self.assertEqual(writes[1]['api_key'], 'fixture-secret')
        self.assertEqual(self.items(batch)[1]['acquisition_id'], original['acquisition_id'])

    def test_receipt_identity_change_stays_unknown_and_never_creates_available_stock(self):
        batch, _ = self.create()
        self.wrong_identity = True
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['unknown'], result['imported']), (2, 0))
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_POOL), 0)

    def test_get_does_not_restart_interrupted_submissions_and_explicit_retry_recovers(self):
        batch, _ = self.create()
        item = self.items(batch)[0]
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item['id'], {'status': 'submitting'})
        self.calls.clear()
        self.service.get(batch['batch_id'])
        self.assertEqual(self.calls, [])
        self.service.retry(batch['batch_id'])
        self.service._run_batch(batch['batch_id'])
        self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)

    def test_second_batch_and_paste_cannot_take_an_active_fixed_candidate(self):
        batch, _ = self.create()
        again = self.preview()
        self.assertEqual(again['selected'], 0)
        from core.storage.email.local_imports import import_resources
        self.assertEqual(import_resources([{'email': self.addresses[0]}], source='email_butler'), (0, 1))
        self.service._run_batch(batch['batch_id'])
        self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)

    def test_create_rejects_changed_connection_since_preview(self):
        preview = self.preview()
        from config import email as config
        config.EMAIL_BUTLER_API_KEY = 'replacement-key'
        with self.assertRaisesRegex(ValueError, 'import_snapshot_conflict'):
            self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']})
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_IMPORT_BATCHES), 0)

    def test_validation_never_calls_remote_for_invalid_count_or_provider(self):
        for data in [{'provider': 'outlook', 'count': 1}, {'count': True}, {'count': 0}, {'count': 201},
                     {'count': 1, 'identity_type': 'unrecognized'}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.service.preview(data)
        self.assertEqual(self.calls, [])

    def test_two_process_style_workers_cannot_handoff_the_same_batch_twice(self):
        batch, _ = self.create()
        entered, release = threading.Event(), threading.Event()
        def held_remote(method, path, **kwargs):
            if path == '/mailboxes':
                entered.set()
                self.assertTrue(release.wait(5))
            return self.remote(method, path, **kwargs)
        with patch('core.email.email_butler.client._request', side_effect=held_remote), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.service._run_batch, batch['batch_id'])
            try:
                self.assertTrue(entered.wait(3))
                second = pool.submit(self.service._run_batch, batch['batch_id'])
                second.result(timeout=2)
            finally:
                release.set()
            first.result(timeout=5)
        self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)
        self.assertEqual(len([path for _, path, _ in self.calls if path == '/mailboxes']), 2)

    def test_parallel_imports_finish_other_addresses_while_one_handoff_is_slow(self):
        self.addresses = ['parent+child' + str(index) + '@icloud.com' for index in range(8)]
        preview = self.preview(count=8)
        batch = self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']})
        four_started, release_fast, release_slow = threading.Event(), threading.Event(), threading.Event()
        monitor = threading.Lock()
        active = peak = 0

        def held_remote(method, path, **kwargs):
            nonlocal active, peak
            if path != '/mailboxes':
                return self.remote(method, path, **kwargs)
            with monitor:
                active += 1
                peak = max(peak, active)
                if active == 4:
                    four_started.set()
            try:
                gate = release_slow if kwargs['json']['requested_email'] == self.addresses[0] else release_fast
                if not gate.wait(5):
                    raise TimeoutError('测试交接等待超时')
                return self.remote(method, path, **kwargs)
            finally:
                with monitor:
                    active -= 1

        with patch('core.email.email_butler.client._request', side_effect=held_remote), ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(self.service._run_batch, batch['batch_id'])
            try:
                self.assertTrue(four_started.wait(2), '慢地址占用时，其他地址也应开始交接')
                release_fast.set()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    progress = self.service.get(batch['batch_id'])
                    if progress['imported'] == 7:
                        break
                    threading.Event().wait(0.01)
                self.assertEqual((progress['imported'], progress['submitting']), (7, 1))
                self.assertEqual(peak, 4)
            finally:
                release_fast.set()
                release_slow.set()
                worker.result(timeout=5)
        self.assertEqual(self.service.get(batch['batch_id'])['imported'], 8)

    def test_error_counts_explain_failed_and_unconfirmed_handoffs_without_addresses(self):
        batch, _ = self.create()
        self.reject_address, self.timeout_address = self.addresses
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual(result['error_counts'], {'handoff_rejected': 1, 'handoff_unconfirmed': 1})
        self.assertNotIn('icloud.com', str(result))

    def test_startup_marks_only_interrupted_batch_and_retry_keeps_original_identity(self):
        batch, request = self.create()
        original = self.items(batch)[0]
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, original['id'], {'status': 'submitting'})
        self.calls.clear()
        self.assertEqual(self.service.reconcile_interrupted(), 1)
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['status'], result['error_code'], result['pending'], result['submitting']),
                         ('partial', 'import_interrupted', 1, 1))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.service.reconcile_interrupted(), 0)
        self.assertEqual(self.service.create(request)['batch_id'], batch['batch_id'])
        self.service._run_batch(batch['batch_id'])
        self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)
        self.assertEqual(self.items(batch)[0]['acquisition_id'], original['acquisition_id'])

    def test_startup_completes_imports_committed_before_batch_summary(self):
        batch, _ = self.create()
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'batch_id', batch['batch_id'])
        profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, row['profile_id'])
        for item in self.items(batch):
            self.service._process_item(row, item, profile)
        self.assertEqual(self.service.get(batch['batch_id'])['status'], 'running')
        self.calls.clear()
        self.assertEqual(self.service.reconcile_interrupted(), 1)
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['status'], result['error_code'], result['imported'], result['can_retry']),
                         ('completed', None, 2, False))
        self.assertEqual(self.calls, [])

    def test_batch_classifies_database_and_local_worker_failures_separately(self):
        from psycopg import OperationalError
        from psycopg_pool import PoolTimeout

        batch, _ = self.create()
        for error, expected in ((RuntimeError('测试本地任务异常'), 'import_internal_error'),
                                (OperationalError('测试数据库异常'), 'import_storage_unavailable'),
                                (PoolTimeout('测试连接池耗尽'), 'import_storage_unavailable')):
            with self.subTest(error=type(error).__name__), patch.object(self.service, '_process_item', side_effect=error):
                self.service._run_batch(batch['batch_id'])
                result = self.service.get(batch['batch_id'])
                self.assertEqual((result['status'], result['error_code']), ('partial', expected))
                self.assertEqual(result['pending'], 2)

    def test_batch_classifies_remote_contract_and_fixed_credentials_failures(self):
        from core.email.derivation import EmailDerivationError

        batch, _ = self.create()
        cases = [
            (patch.object(self.service, '_request', side_effect=self.service.RemoteError('butler_remote_unavailable')),
             'butler_remote_unavailable'),
            (patch.object(self.service.handoff, 'verify_client', side_effect=ValueError('handoff_contract_unsupported')),
             'handoff_contract_unsupported'),
            (patch('core.email.derivation._profile_credentials', side_effect=EmailDerivationError(
                'email_derivation_profile_unavailable', '测试固定凭据缺失')), 'fixed_route_unavailable'),
        ]
        for target, expected in cases:
            with self.subTest(expected=expected), target:
                self.service._run_batch(batch['batch_id'])
                result = self.service.get(batch['batch_id'])
                self.assertEqual((result['status'], result['error_code']), ('partial', expected))
                self.assertEqual(result['pending'], 2)

    def test_startup_does_not_pause_a_batch_with_an_active_worker(self):
        batch, _ = self.create()
        entered, release = threading.Event(), threading.Event()

        def held_remote(method, path, **kwargs):
            if path == '/mailboxes':
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('测试交接等待超时')
            return self.remote(method, path, **kwargs)

        with patch('core.email.email_butler.client._request', side_effect=held_remote), ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(self.service._run_batch, batch['batch_id'])
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.service.reconcile_interrupted(), 0)
                self.assertEqual(self.service.get(batch['batch_id'])['status'], 'running')
            finally:
                release.set()
                worker.result(timeout=5)
        self.assertEqual(self.service.get(batch['batch_id'])['status'], 'completed')

    def test_expired_or_empty_preview_rejects_before_saving_profile_or_batch(self):
        preview = self.preview()
        snapshot = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS,
                                          'preview_token', preview['preview_token'])
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, snapshot['id'], {
            'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)})
        with self.assertRaisesRegex(ValueError, 'import_preview_expired'):
            self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']})
        self.addresses = []
        empty = self.preview()
        with self.assertRaisesRegex(ValueError, 'import_preview_empty'):
            self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': empty['preview_token']})
        self.assertEqual(record_store.count_rows(record_store.EMAIL_INBOX_PROFILES), 0)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_IMPORT_BATCHES), 0)

    def test_remote_contract_without_policy_intersection_is_not_an_import_preview(self):
        def unfiltered(method, path, **kwargs):
            result = self.remote(method, path, **kwargs)
            if path == '/mailboxes/import-candidates':
                result['policy_applied'] = False
            return result
        with patch('core.email.email_butler.client._request', side_effect=unfiltered):
            with self.assertRaisesRegex(self.service.RemoteError, 'butler_candidates_contract_unsupported'):
                self.preview()
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS), 0)

    def test_create_rechecks_conflict_after_preview_without_remote_handoff(self):
        preview = self.preview()
        record_store.insert_row(record_store.GENERIC_API_POOL, {'email': self.addresses[0],
                                'status': 'available', 'code_url': 'https://fixture.example/code'})
        batch = self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']})
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['imported'], result['skipped']), (1, 1))
        writes = [kwargs['json']['requested_email'] for _, path, kwargs in self.calls if path == '/mailboxes']
        self.assertEqual(writes, [self.addresses[1]])

    def test_late_rejection_cannot_erase_an_original_unknown_handoff(self):
        batch, _ = self.create()
        self.timeout_address = self.addresses[1]
        self.service._run_batch(batch['batch_id'])
        self.timeout_address = None
        self.reject_address = self.addresses[1]
        self.service.retry(batch['batch_id'])
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['unknown'], result['failed'], result['can_retry']), (1, 0, True))

    def test_first_definitive_rejection_finishes_without_retrying_or_replacing(self):
        batch, _ = self.create()
        self.reject_address = self.addresses[1]
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['failed'], result['unknown'], result['can_retry']), (1, 0, False))
        writes = len([path for _, path, _ in self.calls if path == '/mailboxes'])
        self.reject_address = None
        self.service.retry(batch['batch_id'])
        self.service._run_batch(batch['batch_id'])
        self.assertEqual(len([path for _, path, _ in self.calls if path == '/mailboxes']), writes)

    def test_config_change_during_create_cannot_change_the_frozen_profile(self):
        preview = self.preview()
        from core.storage.email import local_imports as local_email_imports
        from config import email as config
        original = local_email_imports._fixed_butler_profile
        def save_after_config_change(conn, **kwargs):
            config.EMAIL_BUTLER_API_BASE = 'https://raced.example/v1'
            config.EMAIL_BUTLER_API_KEY = 'raced-key'
            return original(conn, **kwargs)
        with patch.object(local_email_imports, '_fixed_butler_profile', side_effect=save_after_config_change):
            batch = self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']})
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'batch_id', batch['batch_id'])
        profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, row['profile_id'])
        self.assertEqual(profile['inbox_locator']['api_base'], 'https://original.example/v1')
        self.assertEqual(os.environ[profile['credential_ref']], 'fixture-secret')

    def test_domain_filter_normalizes_the_supported_at_prefix(self):
        result = self.service.preview({'count': 1, 'domain': '@ICLOUD.COM'})
        self.assertEqual(result['selected'], 1)
        self.assertEqual(result['filters']['domain'], 'icloud.com')

    def test_worker_does_not_exhaust_a_single_connection_business_pool(self):
        postgres_store.close_pools()
        try:
            with patch.dict(os.environ, {'TURB_DB_POOL_MAX': '1'}):
                batch, _ = self.create()
                self.service._run_batch(batch['batch_id'])
                self.assertEqual(self.service.get(batch['batch_id'])['imported'], 2)
        finally:
            postgres_store.close_pools()

    def test_small_business_pool_can_finish_parallel_handoffs_without_connection_exhaustion(self):
        postgres_store.close_pools()
        self.addresses = ['parent+small' + str(index) + '@icloud.com' for index in range(6)]
        two_started, release = threading.Event(), threading.Event()
        monitor = threading.Lock()
        active = peak = 0

        def held_remote(method, path, **kwargs):
            nonlocal active, peak
            if path != '/mailboxes':
                return self.remote(method, path, **kwargs)
            with monitor:
                active += 1
                peak = max(peak, active)
                if active == 2:
                    two_started.set()
            try:
                if not release.wait(5):
                    raise TimeoutError('测试交接等待超时')
                return self.remote(method, path, **kwargs)
            finally:
                with monitor:
                    active -= 1

        try:
            with patch.dict(os.environ, {'TURB_DB_POOL_MAX': '2'}):
                preview = self.preview(count=6)
                batch = self.service.create({'request_id': str(uuid.uuid4()), 'preview_token': preview['preview_token']})
                with patch('core.email.email_butler.client._request', side_effect=held_remote), ThreadPoolExecutor(max_workers=1) as pool:
                    worker = pool.submit(self.service._run_batch, batch['batch_id'])
                    try:
                        self.assertTrue(two_started.wait(2))
                    finally:
                        release.set()
                        worker.result(timeout=5)
                self.assertEqual(self.service.get(batch['batch_id'])['imported'], 6)
                self.assertEqual(peak, 2)
        finally:
            postgres_store.close_pools()

    def test_unknown_local_conflict_keeps_original_uncertainty_and_candidate(self):
        batch, _ = self.create()
        self.timeout_address = self.addresses[1]
        self.service._run_batch(batch['batch_id'])
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': self.addresses[1], 'status': 'used'})
        self.timeout_address = None
        self.service._run_batch(batch['batch_id'])
        result = self.service.get(batch['batch_id'])
        self.assertEqual((result['unknown'], result['skipped'], result['can_retry']), (1, 0, True))
