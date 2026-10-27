"""本地统一库存的计数、原子领取与重入安全契约。"""
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core import record_store
from tests.support_pg import PostgresTestCase


class LocalEmailInventoryTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        record_store.init()
        from core import email_butler_client as butler
        self.environment = patch.dict(os.environ, {'LOCAL_TEST_BUTLER_SECRET': 'test-value'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.cache = patch.dict(butler._CONTEXT_CACHE, {}, clear=True)
        self.cache.start()
        self.addCleanup(self.cache.stop)
        self.secrets = patch('core.email_derivation._save_profile_secret',
            side_effect=lambda key, value: os.environ.__setitem__(key, value))
        self.secrets.start()
        self.addCleanup(self.secrets.stop)

    def inventory(self):
        from core import local_email_inventory
        return local_email_inventory

    def add(self, source, address, **values):
        inventory = self.inventory()
        if source in {'icloud_hide', 'email_butler'}:
            values.setdefault('butler_handoff', {'version': 1, 'state': 'issued',
                'owner_kind': 'local_inventory', 'owner_id': 'fixture-consumer',
                'identity_id': 'fixture:' + address, 'acquisition_id': 'fixture:' + address})
        if source == 'icloud_hide' and 'derivation_policy' not in values:
            profile_id = record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
                'inbox_key': 'hme:' + address, 'connector': 'forward_butler',
                'credential_ref': 'LOCAL_TEST_BUTLER_SECRET', 'revision': 1, 'state': 'active',
                'inbox_locator': {'api_base': 'https://fixed.example/v1', 'mailbox_email': 'final@example.test'},
            })
            values['derivation_policy'] = {'inbox_profile_id': profile_id}
        if source == 'email_butler':
            if 'inbox_profile_id' not in values:
                values['inbox_profile_id'] = record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
                    'inbox_key': 'local:' + address, 'connector': 'forward_butler',
                    'credential_ref': 'LOCAL_TEST_BUTLER_SECRET', 'revision': 1, 'state': 'active',
                    'inbox_locator': {'api_base': 'https://fixed.example/v1', 'mailbox_email': 'final@example.test'},
                })
            values = {'provider': 'icloud_hme', 'recipient_mode': 'forwarded_exact_v1',
                      'strict_family': True, 'mailbox_email': 'final@example.test', **values}
        return record_store.insert_row(inventory.TABLES[source], {
            'email': address, 'status': 'available', **values,
        })

    def test_five_source_counts_and_claims_use_only_local_rows(self):
        inv = self.inventory()
        for index, source in enumerate(inv.TABLES):
            self.add(source, f'local-{index}@example.test')
        with patch('requests.request', side_effect=AssertionError('禁止远端发号或统计')):
            self.assertEqual(inv.summary()['available'], 5)
            for source in inv.TABLES:
                row = inv.claim(source, owner_kind='test', owner_id=source, acquisition_id='claim:' + source)
                self.assertEqual(row['status'], 'used')
                self.assertEqual(inv.summary(source)['available'], 0)
            self.assertEqual(inv.summary()['used'], 5)

    def test_fixed_butler_inventory_without_confirmed_handoff_is_not_new_supply(self):
        inv = self.inventory()
        for source in ['email_butler', 'icloud_hide']:
            with self.subTest(source=source):
                row_id = self.add(source, source + '@icloud.com')
                record_store.patch_row(inv.TABLES[source], row_id, {'butler_handoff': {}})
                self.assertEqual(inv.summary(source)['available'], 0)
                self.assertIsNone(inv.claim(source, owner_kind='test', owner_id=source, acquisition_id='no-handoff:' + source))

    def test_handoff_gate_preserves_existing_claim_restore(self):
        inv = self.inventory()
        row_id = self.add('email_butler', 'existing@icloud.com')
        original = inv.claim('email_butler', owner_kind='test', owner_id='existing', acquisition_id='existing')
        record_store.patch_row(inv.TABLES['email_butler'], row_id, {'butler_handoff': {}})
        resumed = inv.claim('email_butler', owner_kind='test', owner_id='existing', acquisition_id='existing')
        self.assertEqual(resumed['id'], original['id'])
        self.assertEqual(record_store.count_rows(record_store.LOCAL_EMAIL_CLAIMS), 1)

    def test_fixed_imap_inventory_does_not_require_butler_handoff(self):
        inv = self.inventory()
        profile_id = record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
            'inbox_key': 'imap-fixture', 'connector': 'forward_imap', 'state': 'active', 'revision': 1,
            'credential_ref': 'LOCAL_TEST_BUTLER_SECRET',
            'inbox_locator': {'server': 'imap.example.test', 'email': 'final@example.test'},
        })
        self.add('icloud_hide', 'fixed-imap@icloud.com', butler_handoff={},
                 derivation_policy={'inbox_profile_id': profile_id})
        self.assertEqual(inv.summary('icloud_hide')['available'], 1)
        self.assertIsNotNone(inv.claim('icloud_hide', owner_kind='test', owner_id='imap', acquisition_id='imap'))

    def test_capacity_and_claim_exclude_registered_invalid_inactive_and_old_remote_claims(self):
        inv = self.inventory()
        self.add('icloud_hide', 'good@example.test')
        self.add('icloud_hide', 'invalid@example.test', email_invalid=True)
        self.add('icloud_hide', 'inactive@example.test', remote_active=False)
        self.add('icloud_hide', 'registered@example.test')
        record_store.insert_row(record_store.ACCOUNTS, {'email': 'registered@example.test'})
        self.add('icloud_hide', 'remote@example.test')
        record_store.insert_row(record_store.EMAIL_BUTLER_CLAIM_INTENTS, {
            'acquisition_id': 'old', 'owner_kind': 'test', 'owner_id': 'old', 'status': 'claimed',
            'api_base': 'https://example.test/v1', 'credential_ref': 'TEST_SECRET',
            'address_norm': 'remote@example.test', 'mailbox': {'email': 'remote@example.test'},
        })
        self.assertEqual(inv.summary('icloud_hide')['available'], 1)
        self.assertEqual(inv.claim('icloud_hide')['email'], 'good@example.test')
        self.assertIsNone(inv.claim('icloud_hide'))

    def test_same_intent_is_durable_and_cannot_change_owner_or_source(self):
        inv = self.inventory()
        self.add('icloud_hide', 'same@example.test')
        self.add('icloud_hide', 'next@example.test')
        first = inv.claim('icloud_hide', owner_kind='registration_root', owner_id=17, acquisition_id='intent')
        second = inv.claim('icloud_hide', owner_kind='registration_root', owner_id='17', acquisition_id='intent')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(inv.summary('icloud_hide')['available'], 1)
        for source, owner in [('outlook', '17'), ('icloud_hide', '18')]:
            with self.subTest(source=source, owner=owner), self.assertRaisesRegex(RuntimeError, 'identity_conflict'):
                inv.claim(source, owner_kind='registration_root', owner_id=owner, acquisition_id='intent')

    def test_simultaneous_claims_have_one_identity_and_no_duplicate_address(self):
        inv = self.inventory()
        self.add('icloud_hide', 'concurrent@example.test')
        with ThreadPoolExecutor(8) as pool:
            rows = list(pool.map(lambda _: inv.claim('icloud_hide', owner_kind='test', owner_id='one', acquisition_id='single'), range(8)))
        self.assertEqual(len({row['id'] for row in rows}), 1)
        self.assertEqual(record_store.count_rows(record_store.LOCAL_EMAIL_CLAIMS), 1)

    def test_cross_source_duplicate_can_be_claimed_only_once(self):
        inv = self.inventory()
        self.add('icloud_hide', 'duplicate@example.test')
        self.add('email_butler', 'duplicate@example.test')
        with ThreadPoolExecutor(2) as pool:
            rows = list(pool.map(inv.claim, ['icloud_hide', 'email_butler']))
        self.assertEqual(sum(row is not None for row in rows), 1)
        self.assertEqual(inv.summary()['available'], 0)

    def test_later_source_occupied_row_blocks_earlier_available_duplicate(self):
        inv = self.inventory()
        self.add('outlook', 'already-used@example.test')
        self.add('email_butler', 'already-used@example.test', status='used')
        self.assertEqual(inv.summary()['available'], 0)
        self.assertIsNone(inv.claim('outlook'))

    def test_butler_rows_without_fixed_exact_route_are_not_available_or_claimable(self):
        inv = self.inventory()
        record_store.insert_row(record_store.EMAIL_BUTLER_POOL, {'email': 'missing@icloud.com', 'status': 'available'})
        self.assertEqual(inv.summary('email_butler')['available'], 0)
        self.assertIsNone(inv.claim('email_butler'))

    def test_hme_without_fixed_profile_cannot_be_claimed_or_repin_global_after_failure(self):
        from core import email_butler_bridge as bridge, email_butler_client as butler
        inv = self.inventory()
        self.add('icloud_hide', 'unfixed@icloud.com', derivation_policy={})
        with patch.object(butler, '_persist_hme_context', side_effect=AssertionError('不能领取后固定当前global')):
            self.assertEqual(inv.summary('icloud_hide')['available'], 0)
            with self.assertRaisesRegex(RuntimeError, 'inventory_empty'):
                bridge.pick_account(owner_kind='test', owner_id='one', acquisition_id='unfixed')
        self.assertEqual(record_store.count_rows(record_store.LOCAL_EMAIL_CLAIMS), 0)

    def test_claim_and_job_email_commit_together_and_missing_job_rolls_back(self):
        inv = self.inventory()
        self.add('icloud_hide', 'bound@example.test')
        root = record_store.insert_row(record_store.JOBS, {'job_uuid': 'root', 'status': 'queued', 'batch_id': 'batch'})
        child = record_store.insert_row(record_store.JOBS, {'job_uuid': 'child', 'status': 'queued', 'batch_id': 'batch', 'root_job_id': root})
        row = inv.claim('icloud_hide', job_id=child, batch_id='batch', acquisition_id='bound')
        self.assertEqual(record_store.get_row(record_store.JOBS, root)['email'], row['email'])
        self.assertEqual(record_store.get_row(record_store.JOBS, child)['email'], row['email'])
        self.add('icloud_hide', 'rollback@example.test')
        with self.assertRaisesRegex(RuntimeError, 'local_email_job_missing'):
            inv.claim('icloud_hide', job_id=9999, acquisition_id='rollback')
        self.assertEqual(inv.summary('icloud_hide')['available'], 1)
        self.assertEqual(record_store.count_rows(record_store.LOCAL_EMAIL_CLAIMS), 1)

    def test_unknown_and_available_release_keep_local_claim_occupied_without_remote_report(self):
        from core import email_provider, email_butler_client as butler, icloud_hme_client as hme
        inv = self.inventory()
        self.add('icloud_hide', 'retained@icloud.com')
        inv.claim('icloud_hide', owner_kind='test', owner_id='one', acquisition_id='retained')
        with patch.object(butler, '_request', side_effect=AssertionError('本地领取不依赖远端上报')):
            hme.release_account('retained@icloud.com', status='request_unknown')
            email_provider.release_email('retained@icloud.com', status='available', source='icloud_hide')
        self.assertFalse(email_provider.release_email_if_unconsumed('retained@icloud.com'))
        self.assertEqual(inv.summary('icloud_hide')['used'], 1)
        self.assertEqual(inv.summary('icloud_hide')['available'], 0)

    def test_hme_bridge_claim_pins_context_and_keeps_it_after_settings_change(self):
        from config import email as cfg
        from core import email_butler_client as butler, email_butler_bridge as bridge, email_derivation
        inv = self.inventory()
        self.add('icloud_hide', 'pinned@icloud.com')
        with patch.dict(os.environ), patch.object(email_derivation, '_save_profile_secret',
                side_effect=lambda key, value: os.environ.__setitem__(key, value)), patch.multiple(
                cfg, EMAIL_BUTLER_API_BASE='https://fixed.example/v1', EMAIL_BUTLER_API_KEY='test-value',
                ICLOUD_HME_FORWARD_IMAP_EMAIL='final@example.test'), patch.object(
                butler, '_request', side_effect=AssertionError('本地领取不能调用远端')):
            account = bridge.pick_account(owner_kind='test', owner_id='one', acquisition_id='pinned')
            butler._CONTEXT_CACHE.clear()
            with patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://changed.example/v1', EMAIL_BUTLER_API_KEY='changed'):
                restored = bridge.restore_context(account.email)
            self.assertEqual(restored.api_base, 'https://fixed.example/v1')
            self.assertEqual(restored.acquisition_id, 'pinned')

    def test_hme_fixed_route_survives_cache_loss_bridge_off_and_sidecar_mode(self):
        from config import email as cfg
        from core import email_butler_client as butler, email_butler_bridge as bridge, email_derivation, icloud_hme_client as hme
        from core import email_provider
        self.add('icloud_hide', 'stable@icloud.com')
        with patch.object(email_derivation, '_save_profile_secret', side_effect=lambda key, value: os.environ.__setitem__(key, value)), patch.multiple(
                cfg, EMAIL_BUTLER_API_BASE='https://fixed.example/v1', EMAIL_BUTLER_API_KEY='test-value',
                ICLOUD_HME_FORWARD_IMAP_EMAIL='final@example.test'):
            bridge.pick_account(owner_kind='test', owner_id='one', acquisition_id='stable')
        butler._CONTEXT_CACHE.clear()
        with patch.multiple(cfg, ICLOUD_HME_BUTLER_BRIDGE_ENABLED=False, ICLOUD_HME_INBOX_MODE='sidecar',
                EMAIL_BUTLER_API_BASE='https://changed.example/v1', EMAIL_BUTLER_API_KEY='changed'), patch.object(
                butler, 'fetch_inbound_otp', return_value='000000') as fetch, patch.object(
                hme, '_request', side_effect=AssertionError('固定路由不能改回sidecar')):
            email_provider.restore_email_context('stable@icloud.com', source='icloud_hide')
            self.assertEqual(hme.fetch_latest_otp('stable@icloud.com', after_ts=100, max_wait=1), '000000')
        self.assertEqual(fetch.call_args.kwargs['api_base'], 'https://fixed.example/v1')
        self.assertEqual(fetch.call_args.kwargs['api_key'], 'test-value')
        self.assertEqual(fetch.call_args.kwargs['mailbox_email'], 'final@example.test')

    def test_hme_fixed_imap_route_survives_global_butler_bridge_change(self):
        from config import email as cfg
        from core import icloud_hme_client as hme, forward_imap_client as imap
        profile = record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
            'inbox_key': 'fixed-imap', 'connector': 'forward_imap', 'credential_ref': 'LOCAL_TEST_BUTLER_SECRET',
            'revision': 1, 'state': 'active', 'inbox_locator': {
                'server': 'imap.example.test', 'port': 993, 'email': 'fixed@example.test'},
        })
        self.add('icloud_hide', 'imap@icloud.com', derivation_policy={'inbox_profile_id': profile})
        hme.pick_account(owner_kind='test', owner_id='one', acquisition_id='imap')
        with patch.multiple(cfg, ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True, ICLOUD_HME_INBOX_MODE='sidecar'), patch.object(
                imap, 'fetch_latest_otp', return_value='000000') as fetch, patch.object(
                __import__('core.email_butler_client', fromlist=['_request']), '_request', side_effect=AssertionError('不能把固定IMAP改为Butler')):
            self.assertEqual(hme.fetch_latest_otp('imap@icloud.com', after_ts=100), '000000')
        self.assertEqual(fetch.call_count, 1)

    def test_primary_clients_pick_existing_material_without_import_or_generation(self):
        from core import outlook_client, generic_api_mail_client, qqmail_client
        self.add('outlook', 'outlook@example.test', password='fixture', client_id='client', refresh_token='refresh')
        self.add('generic_api', 'api@example.test', code_url='https://code.example.test/read')
        self.add('cloudflare_domain', 'domain@example.test')
        with patch('requests.request', side_effect=AssertionError('领取不访问远端')), patch.object(
                generic_api_mail_client, 'import_from_file', side_effect=AssertionError('禁止运行时导入')), patch.object(
                qqmail_client.random, 'choices', side_effect=AssertionError('禁止运行时生成')):
            self.assertEqual(outlook_client.pick_account().email, 'outlook@example.test')
            self.assertEqual(generic_api_mail_client.pick_account().code_url, 'https://code.example.test/read')
            self.assertEqual(qqmail_client.pick_domain_email(), 'domain@example.test')

    def test_old_claimed_butler_intent_restores_original_without_consuming_local_stock(self):
        from core import email_butler_client as butler
        inv = self.inventory()
        self.add('email_butler', 'unused@icloud.com')
        record_store.insert_row(record_store.EMAIL_BUTLER_CLAIM_INTENTS, {
            'acquisition_id': 'confirmed', 'owner_kind': 'test', 'owner_id': 'one', 'status': 'claimed',
            'api_base': 'https://old.example/v1', 'credential_ref': 'LOCAL_OLD_TEST_SECRET',
            'address_norm': 'original@icloud.com', 'mailbox': {
                'id': 'old-id', 'email': 'original@icloud.com', 'provider': 'icloud_hme',
                'recipient_mode': 'forwarded_exact_v1', 'strict_family': True, 'mailbox_email': 'final@example.test'},
        })
        with patch.dict(os.environ, {'LOCAL_OLD_TEST_SECRET': 'test-value'}), patch.object(
                butler, '_request', side_effect=AssertionError('禁止重新提交旧领取')):
            account = butler.pick_account(owner_kind='test', owner_id='one', acquisition_id='confirmed')
        self.assertEqual(account.email, 'original@icloud.com')
        self.assertEqual(account.api_base, 'https://old.example/v1')
        self.assertEqual(inv.summary('email_butler')['available'], 1)

    def test_old_claimed_butler_mailbox_mismatch_and_expired_generic_never_reallocate(self):
        from core import email_butler_client as butler
        for identity, mailbox in [
            ('mismatch', {'id': 'old-id', 'email': 'different@icloud.com', 'provider': 'icloud_hme',
                'recipient_mode': 'forwarded_exact_v1', 'strict_family': True, 'mailbox_email': 'final@example.test'}),
            ('expired', {'id': 'old-id', 'email': 'original@icloud.com', 'provider': 'mailcom',
                'leased_until': '2000-01-01T00:00:00Z'}),
        ]:
            with self.subTest(identity=identity):
                record_store.insert_row(record_store.EMAIL_BUTLER_CLAIM_INTENTS, {
                    'acquisition_id': identity, 'owner_kind': 'test', 'owner_id': 'one', 'status': 'claimed',
                    'api_base': 'https://old.example/v1', 'credential_ref': 'LOCAL_TEST_BUTLER_SECRET',
                    'address_norm': 'original@icloud.com', 'mailbox': mailbox,
                })
                with patch.object(butler, '_request', side_effect=AssertionError('禁止申请/续租旧地址')):
                    with self.assertRaises(butler.EmailButlerClientError):
                        butler.pick_account(owner_kind='test', owner_id='one', acquisition_id=identity)

    def test_unknown_remote_intent_cannot_fall_back_to_local_stock(self):
        inv = self.inventory()
        self.add('email_butler', 'unused@example.test')
        record_store.insert_row(record_store.EMAIL_BUTLER_CLAIM_INTENTS, {
            'acquisition_id': 'unknown', 'owner_kind': 'test', 'owner_id': 'one', 'status': 'request_unknown',
            'api_base': 'https://example.test/v1', 'credential_ref': 'TEST_SECRET',
        })
        with self.assertRaisesRegex(RuntimeError, 'request_unknown'):
            inv.claim('email_butler', owner_kind='test', owner_id='one', acquisition_id='unknown')
        self.assertEqual(inv.summary('email_butler')['available'], 1)

    def test_hme_new_pick_never_syncs_creates_or_claims_remote(self):
        from core import email_butler_client as butler, icloud_hme_client as hme
        self.add('icloud_hide', 'local@icloud.com', account_id='local-account')
        with patch.object(hme, 'sync_aliases', side_effect=AssertionError('禁止自动同步')), patch.object(
                hme, 'create_address', side_effect=AssertionError('禁止自动创建')), patch.object(
                butler, '_request', side_effect=AssertionError('禁止远端发号')):
            account = hme.pick_account(owner_kind='test', owner_id='one', acquisition_id='hme')
        self.assertEqual(account.email, 'local@icloud.com')

    def test_butler_plain_local_forward_identity_restores_without_remote_claim(self):
        from core import email_butler_client as butler
        profile_id = record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
            'inbox_key': 'local-forward', 'connector': 'forward_butler', 'credential_ref': 'LOCAL_TEST_BUTLER_SECRET',
            'inbox_locator': {'api_base': 'https://fixed.example/v1', 'mailbox_email': 'final@example.test'},
            'revision': 1, 'state': 'active',
        })
        self.add('email_butler', 'local+child@icloud.com', inbox_profile_id=profile_id,
                 provider='icloud_hme', recipient_mode='forwarded_exact_v1', strict_family=True)
        with patch.dict(os.environ, {'LOCAL_TEST_BUTLER_SECRET': 'test-value'}), patch.object(
                butler, '_request', side_effect=AssertionError('本地恢复禁止调用mailboxes')):
            account = butler.pick_account(owner_kind='test', owner_id='one', acquisition_id='local-butler')
            butler._CONTEXT_CACHE.clear()
            restored = butler.restore_account_context(account.email)
        self.assertEqual(restored.api_base, 'https://fixed.example/v1')
        self.assertEqual(restored.mailbox_email, 'final@example.test')
        self.assertTrue(restored.strict_family)

    def test_butler_local_scan_and_bulk_routes_survive_release_and_settings_change(self):
        from config import email as cfg
        from core import email_butler_client as butler, email_butler_bridge as bridge
        self.add('email_butler', 'scan+child@icloud.com')
        account = butler.pick_account(owner_kind='test', owner_id='one', acquisition_id='scan')
        butler.release_account(account.email, status='used')
        butler._CONTEXT_CACHE.clear()
        response = {'signal': {'detected': False}, 'recipient_mode': 'forwarded_exact_v1',
                    'recipient_match': {'email': account.email, 'mailbox_email': 'final@example.test', 'strict_family': True},
                    'recipient_evidence': {'original_recipients': [account.email]}}
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://changed.example/v1', EMAIL_BUTLER_API_KEY='changed'), patch.object(
                butler, '_request', return_value=response) as request:
            self.assertTrue(butler.scan_openai_deactivation(account.email)['ok'])
            routes = bridge.inbox_profiles_for_addresses([account.email])
        self.assertEqual(request.call_args.kwargs['api_base'], 'https://fixed.example/v1')
        self.assertTrue(request.call_args.kwargs['json']['strict_family'])
        self.assertEqual(routes[account.email]['api_base'], 'https://fixed.example/v1')
        self.assertEqual(routes[account.email]['api_key'], 'test-value')

    def test_source_resolution_uses_durable_local_identity_after_process_cache_loss(self):
        from config import email as cfg
        from core import email_provider, email_butler_client as butler
        self.add('email_butler', 'resolve@icloud.com')
        butler.pick_account(owner_kind='test', owner_id='one', acquisition_id='resolve')
        butler._CONTEXT_CACHE.clear()
        with patch.dict(email_provider._EMAIL_SOURCE_HINTS, {}, clear=True), patch.object(cfg, 'EMAIL_SOURCE', 'outlook'):
            self.assertEqual(email_provider.resolve_email_source('resolve@icloud.com'), 'email_butler')

    def test_imported_butler_plus_identity_keeps_authentication_ledger_before_account_write(self):
        from core import email_auth_guard as guard, email_butler_client as butler
        self.add('email_butler', 'auth+child@icloud.com')
        account = butler.pick_account(owner_kind='test', owner_id='one', acquisition_id='auth')
        butler._CONTEXT_CACHE.clear()
        with patch.object(butler, '_request', side_effect=AssertionError('认证恢复禁止远端发号')):
            with guard.email_auth_session(account.email) as session:
                self.assertIsNotNone(session)
                self.assertIsNone(session.binding_id)
                guard.begin_generation(100)
                offered = guard.observe_candidate('fixed-message', {'recipient': account.email})
                self.assertEqual(offered['submission_state'], 'offered')
        receipts = record_store.list_rows(record_store.EMAIL_OTP_REQUESTS,
            where='candidate_message_key = %s', params=('fixed-message',))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]['candidate_message_key'], 'fixed-message')
        self.assertEqual(receipts[0]['candidate_evidence']['recipient'], account.email)
        self.assertEqual(receipts[0]['submission_state'], 'result_unknown')

    def test_legacy_remote_source_cannot_create_new_address(self):
        from core.email_provider import acquire_email
        with patch('requests.request', side_effect=AssertionError('禁止远端发号')):
            for source in ['gptmail', 'remail', 'mailcode', 'xigua', 'mailnest', 'cloudmail', 'cloudflare']:
                with self.subTest(source=source), self.assertRaisesRegex(RuntimeError, 'local_inventory_source_required'):
                    acquire_email(source)
