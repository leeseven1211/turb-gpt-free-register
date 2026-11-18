"""Butler consumer intents and full-address remote identity protection."""
import os
from unittest.mock import patch

from core.email.inventory import LocalEmailInventoryError

from config import email as cfg
from core.email.email_butler import client as client
from core.auth import email_guard as guard
from core.email import derivation as email_derivation
from core.storage import records as record_store
from core.storage.email import address_allocations as allocations
from tests.support_pg import PostgresTestCase


class ButlerConsumptionTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.enterContext(patch.dict(client._CONTEXT_CACHE, {}, clear=True))
        self.scope = patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://butler.test/v1', EMAIL_BUTLER_API_KEY='fixture-key',USE_EMAIL_SERVICE=True)
        self.scope.start()
        self.environment=patch.dict(os.environ, {'LEGACY_BUTLER_TEST_SECRET': 'fixture-key'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.scope.stop)
        self.secret = patch('core.email.derivation._save_profile_secret', side_effect=lambda ref, key: __import__('os').environ.__setitem__(ref,key))
        self.secret.start()
        self.addCleanup(self.secret.stop)

    @staticmethod
    def mailbox(email='parent+child@example.test', **extra):
        return {'capabilities':['mailboxes.acquisition.v1'],'mailbox': {'id':'identity-1','email':email,'provider':'icloud_hme',
            'identity_type':'child','parent_email':'parent@example.test','identity_id':'identity-1',
            'mailbox_email':'final@example.test','recipient_mode':'forwarded_exact_v1','strict_family':True, **extra}}

    def seed_legacy_intent(self, *, state='claimed', mailbox=None):
        from core.storage.email import butler_claims as claims
        intent = claims.prepare(acquisition_id='registration:17', owner_kind='registration_root', owner_id='17',
                                api_base='https://butler.test/v2', credential_ref='LEGACY_BUTLER_TEST_SECRET')
        if state == 'claimed':
            return claims.record_result('registration:17', mailbox=mailbox or self.mailbox()['mailbox'])
        if state == 'request_unknown':
            claims.mark_submitting('registration:17')
            return claims.record_result('registration:17', unknown=True)
        return intent

    def acquire(self, **extra):
        return client.pick_account(owner_kind='registration_root',owner_id='17',acquisition_id='registration:17',**extra)

    def test_persisted_unknown_intent_blocks_reallocation_and_confirmed_receipt_restores(self):
        from core.storage.email import butler_claims as claims
        self.seed_legacy_intent(state='request_unknown')
        client._CONTEXT_CACHE.clear()
        with patch.object(client, '_request', side_effect=AssertionError('旧意图不能重新提交')) as request:
            with self.assertRaises(LocalEmailInventoryError) as caught:
                self.acquire()
            self.assertTrue(caught.exception.request_unknown)
            self.assertEqual(claims.get_intent('registration:17')['status'], 'request_unknown')
            # Model an already reconciled historical receipt; runtime must only restore it.
            claims.record_result('registration:17', mailbox=self.mailbox()['mailbox'])
            resumed = self.acquire()
            self.assertEqual(resumed.email, 'parent+child@example.test')
            self.assertEqual(resumed.acquisition_id, 'registration:17')
            self.assertEqual(self.acquire().email, resumed.email)
            with self.assertRaisesRegex(LocalEmailInventoryError, 'identity_conflict'):
                client.pick_account(owner_kind='registration_root', owner_id='18', acquisition_id='registration:17')
        request.assert_not_called()

    def test_unresolved_legacy_receipt_stays_unknown_without_new_remote_request(self):
        from core.storage.email import butler_claims as claims
        self.seed_legacy_intent(state='request_unknown')
        intent = claims.get_intent('registration:17')
        record_store.patch_row(record_store.EMAIL_BUTLER_CLAIM_INTENTS, intent['id'],
                               {'mailbox': {'email': 'incomplete@example.test'}})
        with patch.object(client, '_request') as request:
            with self.assertRaises(LocalEmailInventoryError) as caught:
                self.acquire()
        self.assertTrue(caught.exception.request_unknown)
        self.assertEqual(claims.get_intent('registration:17')['status'], 'request_unknown')
        request.assert_not_called()

    def test_remote_child_persists_strict_identity_and_uses_nullable_local_fence(self):
        self.seed_legacy_intent()
        with patch.object(client,'_request',side_effect=AssertionError('历史身份恢复不能新申请')):
            account=self.acquire()
        client._CONTEXT_CACHE.clear()
        restored=client.restore_account_context(account.email)
        self.assertEqual((restored.identity_type,restored.parent_email,restored.identity_id),('child','parent@example.test','identity-1'))
        self.assertIsNone(allocations.find_allocation(address=account.email))
        with guard.email_auth_session(account.email) as session:
            self.assertIsNotNone(session)
            self.assertIsNone(session.binding_id)
            guard.begin_generation(100)
            guard.observe_candidate('message-stable',{'recipient':account.email})
        request=allocations.list_otp_requests(account.email)[0]
        self.assertEqual(request['submission_state'],'result_unknown')
        self.assertIsNone(request['address_binding_id'])

    def test_non_hme_legacy_child_without_exact_contract_fails_closed(self):
        self.seed_legacy_intent(mailbox=self.mailbox(provider='outlook', recipient_mode='', strict_family=False)['mailbox'])
        with patch.object(client, '_request') as request:
            with self.assertRaisesRegex(client.EmailButlerClientError, 'recipient_contract_unsupported'):
                self.acquire()
        request.assert_not_called()
        self.assertIsNone(client.get_account_context('parent+child@example.test'))

    def test_new_local_generation_is_closed_for_all_sources(self):
        for source in ('outlook','icloud_hide'):
            with self.subTest(source=source),self.assertRaisesRegex(email_derivation.EmailDerivationError,'Butler'):
                email_derivation.generate_inventory(source,1,'new-'+source)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS),0)

    def test_existing_generation_request_restores_after_cutover(self):
        record_store.insert_row(record_store.EMAIL_ADDRESS_GENERATION_REQUESTS,{
            'request_id':'old','source':'outlook','requested':2,'parent_id':None,
            'result':{'requested':2,'created':2,'reused':0,'shortfall':0,'reason_code':'','reason':''}})
        self.assertEqual(email_derivation.generate_inventory('outlook',2,'old')['reused'],2)

    def test_new_local_claim_requires_butler_but_existing_binding_restores(self):
        with patch.object(cfg,'EMAIL_DERIVATION_ENABLED',True),patch.object(cfg,'EMAIL_DERIVATION_SOURCES','outlook'):
            with self.assertRaisesRegex(email_derivation.EmailDerivationError,'Butler'):
                email_derivation.acquire_address('outlook',owner_kind='registration_root',owner_id='new',acquisition_id='new')

    def test_unknown_claim_prevents_source_fallback(self):
        from core.email import provider as email_provider
        with patch.object(cfg,'EMAIL_SOURCE','email_butler,outlook'),patch.object(email_provider,'_pick_from_source',side_effect=client.EmailButlerClaimUnknown('request_unknown')) as pick:
            with self.assertRaises(client.EmailButlerClaimUnknown):
                email_provider.acquire_email(owner_kind='registration_root',owner_id='17',acquisition_id='registration:17')
        self.assertEqual(pick.call_count,1)

    def test_registration_preparation_passes_butler_intent(self):
        from core.registration import service as svc
        from config import register as register_cfg
        with patch.object(register_cfg,'REGISTER_EMAIL',''),patch.object(register_cfg,'REGISTER_NAME','Fixture'),patch.object(cfg,'USE_EMAIL_SERVICE',True),patch('core.email.provider.acquire_email',return_value='primary@example.test') as acquire:
            svc._prepare_registration_args('email_butler',owner_kind='registration_root',owner_id='17',acquisition_id='registration:17')
        self.assertEqual(acquire.call_args.kwargs['acquisition_id'],'registration:17')

    def test_remote_child_fetch_records_generation_and_candidate(self):
        from core.email import provider as email_provider
        self.seed_legacy_intent()
        with patch.object(client,'_request',side_effect=AssertionError('历史身份恢复不能新申请')):
            account=self.acquire()
        def receive(*args,**kwargs):
            self.assertIsNotNone(guard.current_session())
            self.assertEqual(allocations.list_otp_requests(account.email)[0]['cursor']['requested_after'],'100.0')
            guard.observe_candidate('message-stable',{'recipient':account.email})
            return '000000'
        with guard.email_auth_session(account.email):
            with patch.object(client,'fetch_latest_otp',side_effect=receive):
                self.assertEqual(email_provider.wait_for_otp(account.email,after_ts=100.0,email_source='email_butler'),'000000')

    def test_bridge_configuration_does_not_make_empty_local_inventory_ready(self):
        from core.runtime import capabilities as feature_availability
        with patch.multiple(cfg,EMAIL_SOURCE='email_butler,icloud_hide',ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True,ICLOUD_HME_API_BASE='',EMAIL_DERIVATION_ENABLED=False,ICLOUD_HME_AUTO_CREATE=False),patch('core.db.icloud_hide_email_pool_summary',side_effect=AssertionError('no local HME stock')):
            status=feature_availability.email_source_availability()['icloud_hide']
        self.assertFalse(status['enabled'],status)
        self.assertEqual(status['available'], 0)

    def test_cli_preparation_passes_butler_intent(self):
        import main
        with patch.object(main,'REGISTER_EMAIL',''),patch.object(main,'REGISTER_NAME','Fixture'),patch.object(cfg,'USE_EMAIL_SERVICE',True),patch.object(main,'acquire_email',return_value='primary@example.test') as acquire:
            main.prepare_registration_inputs(email_source='email_butler',owner_kind='cli',owner_id='cli:17',acquisition_id='cli:17')
        self.assertEqual(acquire.call_args.kwargs['acquisition_id'],'cli:17')

    def test_email_change_preparation_passes_butler_intent(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from core.accounts.email_change import service as email_change_service
        context=SimpleNamespace(checkpoint=Mock(),config_snapshot={},run={'data':{'remail_acquisition_id':'change:17'}},task_id=17)
        with patch('core.email.provider.acquire_email',return_value='primary@example.test') as acquire,patch('core.db.get_account_by_email',return_value=None):
            target,error=email_change_service._acquire_email_change_target(context,account_id=7,source='email_butler',current_email='old@example.test')
        self.assertIsNone(error)
        self.assertEqual(acquire.call_args.kwargs,{'owner_kind':'email_change','owner_id':17,'acquisition_id':'change:17'})

    def test_missing_original_secret_cannot_repin_current_global_key(self):
        self.seed_legacy_intent()
        with patch.dict(os.environ, {'LEGACY_BUTLER_TEST_SECRET': ''}), patch(
            'config.runtime.read_persisted_values', return_value={}
        ), patch.object(cfg, 'EMAIL_BUTLER_API_KEY', 'new-global-key'), patch.object(client, '_request') as request:
            with self.assertRaisesRegex(email_derivation.EmailDerivationError, 'email_derivation_profile_unavailable'):
                self.acquire()
        request.assert_not_called()
        self.assertIsNone(client.get_account_context('parent+child@example.test'))

    def test_imported_butler_child_restores_persisted_exact_identity_before_auth(self):
        email = 'parent+imported@example.test'
        record_store.insert_row(record_store.ACCOUNTS, {'email': email, 'email_source': 'email_butler'})
        self.seed_legacy_intent(mailbox=self.mailbox(email)['mailbox'])
        with patch.object(client, '_request', side_effect=AssertionError('恢复不能重新分配')) as request:
            with guard.email_auth_session(email) as session:
                self.assertIsNotNone(session)
                self.assertIsNone(session.binding_id)
            profile = client._restore_hme_context(email)
            self.assertEqual(profile.acquisition_id, 'registration:17')
            client._CONTEXT_CACHE.clear()
            with guard.email_auth_session(email) as restored:
                self.assertIsNotNone(restored)
                self.assertIsNone(restored.binding_id)
            # Auth can read the persisted fixed identity without populating the process cache.
            restored_profile = client._restore_hme_context(email)
            self.assertEqual(restored_profile.acquisition_id, profile.acquisition_id)
            self.assertEqual(restored_profile.identity_id, profile.identity_id)
            self.assertEqual(restored_profile.email, email)
        request.assert_not_called()

    def test_core_inventory_status_writes_are_closed(self):
        with self.assertRaisesRegex(email_derivation.EmailDerivationError,'Butler'):
            email_derivation.update_inventory_status([1],'available')

    def test_retired_local_policy_does_not_redirect_new_primary_outlook_claims(self):
        from core.email import provider as email_provider
        from types import SimpleNamespace
        with patch.multiple(cfg,EMAIL_DERIVATION_ENABLED=True,EMAIL_DERIVATION_SOURCES='outlook'),patch('core.email.outlook.client.pick_account',return_value=SimpleNamespace(email='primary@example.test')):
            address=email_provider._pick_from_source('outlook',owner_kind='registration_root',owner_id='new',acquisition_id='new-primary')
        self.assertEqual(address,'primary@example.test')

    def test_legacy_store_rejection_cannot_downgrade_prior_unknown_receipt(self):
        from core.storage.email import butler_claims as claims
        self.seed_legacy_intent(state='prepared')
        admitted, submitted = claims.mark_submitting('registration:17')
        self.assertTrue(admitted)
        rejected = claims.record_result('registration:17', rejected=True, execution=submitted['submission_execution'])
        self.assertEqual(rejected['status'], 'rejected')
        admitted, _ = claims.mark_submitting('registration:17')
        self.assertTrue(admitted)
        claims.record_result('registration:17', unknown=True)
        late = claims.record_result('registration:17', rejected=True, execution=submitted['submission_execution'])
        self.assertEqual(late['status'], 'request_unknown')
        with patch.object(client, '_request') as request, self.assertRaises(LocalEmailInventoryError) as caught:
            self.acquire()
        self.assertTrue(caught.exception.request_unknown)
        request.assert_not_called()

    def test_unknown_legacy_claim_never_probes_or_reposts_retired_endpoint(self):
        self.seed_legacy_intent(state='request_unknown')
        with patch.object(client, '_request') as request:
            with self.assertRaises(LocalEmailInventoryError) as caught:
                self.acquire()
        self.assertTrue(caught.exception.request_unknown)
        request.assert_not_called()

    def test_expired_non_hme_original_lease_fails_closed_without_new_allocation(self):
        from core.email.email_butler import lease_bindings, v2
        self.seed_legacy_intent(mailbox={'id': 'generic-1', 'email': 'generic@example.test',
                                        'provider': 'mailcom', 'leased_until': '2000-01-01T00:00:00Z'})
        account = self.acquire()
        client._CONTEXT_CACHE.clear()
        with patch.object(lease_bindings, 'resolve', side_effect=v2.ButlerV2Error('lease_expired', '原租约已到期')), \
                patch.object(v2, 'create_lease') as create, patch.object(client, '_request') as request:
            with self.assertRaisesRegex(client.EmailButlerClientError, '原租约已到期') as caught:
                client.fetch_latest_otp(account.email, after_ts=100, max_wait=1)
        self.assertEqual(caught.exception.error_code, 'lease_expired')
        create.assert_not_called()
        request.assert_not_called()

    def test_ordinary_mailbox_v2_read_keeps_claim_connection_after_global_change(self):
        from core.email.email_butler import lease_bindings, v2
        self.seed_legacy_intent(mailbox={'id': 'generic-1', 'email': 'generic@example.test', 'provider': 'mailcom'})
        account = self.acquire()
        binding = {'lease_id': 'lse_original', 'client_id': 'original-client', 'api_base': 'https://butler.test/v2'}
        receipt = {'lease_id': 'lse_original', 'service': 'openai', 'status': 'matched',
                   'verification_code': '000000', 'code_id': 'code-original', 'received_at': '1970-01-01T00:02:00Z'}
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://changed.test/v2', EMAIL_BUTLER_API_KEY='changed-key'), \
                patch.object(lease_bindings, 'resolve', return_value=binding) as resolve, \
                patch.object(v2, 'code', return_value=receipt) as code, patch.object(v2, 'create_lease') as create:
            self.assertEqual(client.fetch_latest_otp(account.email, after_ts=100, max_wait=1), '000000')
        self.assertEqual(resolve.call_args.kwargs['api_base'], 'https://butler.test/v2')
        self.assertEqual(resolve.call_args.kwargs['api_key'], 'fixture-key')
        self.assertEqual(code.call_args.kwargs['api_base'], 'https://butler.test/v2')
        self.assertEqual(code.call_args.kwargs['api_key'], 'fixture-key')
        create.assert_not_called()

    def test_unknown_claim_and_owner_conflict_prevent_source_fallback(self):
        from core.email import provider as email_provider
        self.seed_legacy_intent(state='request_unknown')
        with patch.object(cfg, 'EMAIL_SOURCE', 'email_butler,outlook'), patch(
            'core.email.outlook.client.pick_account', side_effect=AssertionError('原意图不能换邮箱来源')
        ) as fallback:
            for owner in ('17', '18'):
                with self.subTest(owner=owner), self.assertRaises(LocalEmailInventoryError) as caught:
                    email_provider.acquire_email(owner_kind='registration_root', owner_id=owner,
                                                 acquisition_id='registration:17')
                self.assertTrue(caught.exception.request_unknown or caught.exception.identity_locked)
        fallback.assert_not_called()

    def test_delayed_known_rejection_never_overwrites_unknown_claim(self):
        from core.storage.email import butler_claims as claims
        self.seed_legacy_intent(state='request_unknown')
        current = claims.record_result('registration:17', rejected=True)
        self.assertEqual(current['status'], 'request_unknown')

    def test_concurrent_legacy_store_has_one_first_submitter(self):
        from concurrent.futures import ThreadPoolExecutor
        from core.storage.email import butler_claims as claims
        self.seed_legacy_intent(state='prepared')
        with patch.object(client, '_request') as request, ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claims.mark_submitting('registration:17'), range(2)))
        self.assertEqual(sum(admitted for admitted, _ in results), 1)
        self.assertEqual(claims.get_intent('registration:17')['status'], 'submitting')
        request.assert_not_called()
