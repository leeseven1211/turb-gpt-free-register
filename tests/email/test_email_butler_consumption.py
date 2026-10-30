"""Butler consumer intents and full-address remote identity protection."""
from unittest.mock import patch

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
        client._CONTEXT_CACHE.clear()
        self.scope = patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://butler.test/v1', EMAIL_BUTLER_API_KEY='fixture-key',USE_EMAIL_SERVICE=True)
        self.scope.start()
        self.environment=patch.dict(__import__('os').environ)
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

    def acquire(self, **extra):
        return client.pick_account(owner_kind='registration_root',owner_id='17',acquisition_id='registration:17',**extra)

    def test_intent_is_committed_before_network_and_unknown_resumes_same_id_after_restart(self):
        from core.storage.email import butler_claims as claims
        def interrupted(*args, **kwargs):
            if args[0]=='GET':
                return {'capabilities':['mailboxes.acquisition.v1']}
            intent = claims.get_intent('registration:17')
            self.assertEqual((intent['owner_kind'],intent['owner_id']),('registration_root','17'))
            raise client.requests.ReadTimeout('interrupted')
        with patch.object(client,'_request',side_effect=interrupted):
            with self.assertRaises(client.EmailButlerClaimUnknown) as caught:
                self.acquire()
        self.assertTrue(caught.exception.request_unknown)
        self.assertEqual(claims.get_intent('registration:17')['status'],'request_unknown')
        client._CONTEXT_CACHE.clear()
        with patch.object(client,'_request',return_value=self.mailbox()) as request:
            resumed=self.acquire()
        self.assertEqual(resumed.email,'parent+child@example.test')
        self.assertEqual(request.call_args.kwargs['json']['acquisition_id'],'registration:17')
        self.assertEqual(claims.get_intent('registration:17')['status'],'claimed')
        with patch.object(client,'_request',side_effect=AssertionError('must restore locally')):
            self.assertEqual(self.acquire().email,resumed.email)
        with patch.object(client,'_request',side_effect=AssertionError('owner conflict before HTTP')):
            with self.assertRaisesRegex(client.EmailButlerClientError,'identity_conflict'):
                client.pick_account(owner_kind='registration_root',owner_id='18',acquisition_id='registration:17')

    def test_success_with_unparseable_identity_stays_unknown(self):
        from core.storage.email import butler_claims as claims
        with patch.object(client,'_request',return_value={'mailbox':{'email':'incomplete@example.test'}}):
            with self.assertRaises(client.EmailButlerClaimUnknown):
                self.acquire()
        self.assertEqual(claims.get_intent('registration:17')['status'],'request_unknown')

    def test_remote_child_persists_strict_identity_and_uses_nullable_local_fence(self):
        with patch.object(client,'_request',return_value=self.mailbox()):
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

    def test_non_hme_child_without_exact_contract_fails_closed(self):
        with patch.object(client,'_request',return_value=self.mailbox(provider='outlook',recipient_mode='',strict_family=False)):
            with self.assertRaisesRegex(client.EmailButlerClientError,'recipient_contract_unsupported'):
                self.acquire()

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
        with patch.object(client,'_request',return_value=self.mailbox()):
            account=self.acquire()
        def receive(*args,**kwargs):
            self.assertIsNotNone(guard.current_session())
            self.assertEqual(allocations.list_otp_requests(account.email)[0]['cursor']['requested_after'],'100.0')
            guard.observe_candidate('message-stable',{'recipient':account.email})
            return '000000'
        with guard.email_auth_session(account.email):
            with patch.object(client,'fetch_latest_otp',side_effect=receive):
                self.assertEqual(email_provider.wait_for_otp(account.email,after_ts=100.0,email_source='email_butler'),'000000')

    def test_bridge_availability_uses_butler_not_sidecar_or_local_stock(self):
        from core.runtime import capabilities as feature_availability
        with patch.multiple(cfg,EMAIL_SOURCE='email_butler,icloud_hide',ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True,ICLOUD_HME_API_BASE='',EMAIL_DERIVATION_ENABLED=False,ICLOUD_HME_AUTO_CREATE=False),patch('core.db.icloud_hide_email_pool_summary',side_effect=AssertionError('no local HME stock')):
            status=feature_availability.email_source_availability()['icloud_hide']
        self.assertTrue(status['enabled'],status)

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

    def test_missing_original_secret_cannot_fall_back_or_repin_current_key(self):
        import os
        from core.storage.email import butler_claims as claims
        with patch.object(client,'_request',side_effect=client.requests.ReadTimeout('interrupted')):
            with self.assertRaises(client.EmailButlerClaimUnknown):
                self.acquire()
        intent=claims.get_intent('registration:17')
        with patch.dict(os.environ,{intent['credential_ref']:''}),patch('config.env_loader.read_env_file',return_value={}):
            with patch.object(client,'_request',side_effect=AssertionError('cannot switch secret')):
                with self.assertRaises(client.EmailButlerClaimUnknown):
                    self.acquire()

    def test_imported_butler_child_restores_exact_identity_before_auth(self):
        email='parent+imported@example.test'
        record_store.insert_row(record_store.ACCOUNTS,{'email':email,'email_source':'email_butler'})
        with patch.object(client,'_request',return_value=self.mailbox(email)) as request:
            with guard.email_auth_session(email) as session:
                self.assertIsNotNone(session)
                self.assertIsNone(session.binding_id)
        self.assertEqual(request.call_args.kwargs['json']['requested_email'],email)
        self.assertEqual(client.active_mailbox_leases(), [])
        client._CONTEXT_CACHE.clear()
        with patch.object(client,'_request',side_effect=AssertionError('fixed profile must survive restart')):
            with guard.email_auth_session(email) as restored:
                self.assertIsNotNone(restored)

    def test_core_inventory_status_writes_are_closed(self):
        with self.assertRaisesRegex(email_derivation.EmailDerivationError,'Butler'):
            email_derivation.update_inventory_status([1],'available')

    def test_retired_local_policy_does_not_redirect_new_primary_outlook_claims(self):
        from core.email import provider as email_provider
        from types import SimpleNamespace
        with patch.multiple(cfg,EMAIL_DERIVATION_ENABLED=True,EMAIL_DERIVATION_SOURCES='outlook'),patch('core.email.outlook.client.pick_account',return_value=SimpleNamespace(email='primary@example.test')):
            address=email_provider._pick_from_source('outlook',owner_kind='registration_root',owner_id='new',acquisition_id='new-primary')
        self.assertEqual(address,'primary@example.test')

    def test_known_initial_rejection_is_not_unknown_but_prior_unknown_stays_unknown(self):
        from core.storage.email import butler_claims as claims
        from unittest.mock import Mock
        response=Mock(status_code=401)
        response.json.return_value={'error_code':'invalid_key','message':'unauthorized'}
        with patch.object(client.requests,'request',return_value=response):
            with self.assertRaises(client.EmailButlerClientError) as rejected:
                self.acquire()
        self.assertFalse(getattr(rejected.exception,'request_unknown',False))
        self.assertEqual(claims.get_intent('registration:17')['status'],'rejected')
        with patch.object(client,'_request',side_effect=client.requests.ReadTimeout('interrupted')):
            with self.assertRaises(client.EmailButlerClaimUnknown):
                self.acquire()
        with patch.object(client.requests,'request',return_value=response):
            with self.assertRaises(client.EmailButlerClaimUnknown):
                self.acquire()
        self.assertEqual(claims.get_intent('registration:17')['status'],'request_unknown')

    def test_unknown_claim_without_remote_acquisition_capability_never_reposts(self):
        with patch.object(client,'_request',side_effect=client.requests.ReadTimeout('interrupted')):
            with self.assertRaises(client.EmailButlerClaimUnknown):
                self.acquire()
        with patch.object(client,'_request',return_value={'capabilities':[]}) as request:
            with self.assertRaises(client.EmailButlerClaimUnknown):
                self.acquire()
        self.assertEqual(request.call_count,1)
        self.assertEqual(request.call_args.args,('GET','/me'))

    def test_expired_non_hme_lease_never_allocates_again(self):
        payload={'mailbox':{'id':'generic-1','email':'generic@example.test','provider':'mailcom','leased_until':'2000-01-01T00:00:00Z'}}
        with patch.object(client,'_request',return_value=payload):
            self.acquire()
        client._CONTEXT_CACHE.clear()
        with patch.object(client,'_request',side_effect=AssertionError('cannot renew by new allocation')):
            with self.assertRaisesRegex(client.EmailButlerClientError,'lease_restore_required'):
                self.acquire()

    def test_ordinary_mailbox_read_keeps_claim_connection_after_global_change(self):
        payload = {'mailbox': {'id': 'generic-1', 'email': 'generic@example.test',
                              'provider': 'mailcom', 'leased_until': '2099-01-01T00:00:00Z'}}
        with patch.object(client, '_request', return_value=payload):
            account = self.acquire()
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://changed.test/v1', EMAIL_BUTLER_API_KEY='changed-key'), patch.object(
                client, '_request', return_value={'messages': [{'code': '000000'}]}) as request:
            self.assertEqual(client.fetch_latest_otp(account.email, max_wait=1, settle_seconds=0), '000000')
        self.assertEqual(request.call_args.kwargs.get('api_base'), 'https://butler.test/v1')
        self.assertEqual(request.call_args.kwargs.get('api_key'), 'fixture-key')

    def test_expired_claim_and_owner_conflict_prevent_source_fallback(self):
        from core.email import provider as email_provider
        payload = {'mailbox': {'id': 'generic-1', 'email': 'generic@example.test',
                              'provider': 'mailcom', 'leased_until': '2000-01-01T00:00:00Z'}}
        with patch.object(client, '_request', return_value=payload):
            self.acquire()
        with patch.object(cfg, 'EMAIL_SOURCE', 'email_butler,outlook'), patch(
                'core.email.outlook.client.pick_account', side_effect=AssertionError('intent cannot change source')) as fallback:
            for owner in ('17', '18'):
                with self.subTest(owner=owner), self.assertRaises(client.EmailButlerClientError) as caught:
                    email_provider.acquire_email(owner_kind='registration_root', owner_id=owner,
                                                 acquisition_id='registration:17')
                self.assertTrue(getattr(caught.exception, 'identity_locked', False))
        fallback.assert_not_called()

    def test_delayed_known_rejection_never_overwrites_unknown_claim(self):
        from core.storage.email import butler_claims as claims
        with patch.object(client,'_request',side_effect=client.requests.ReadTimeout('interrupted')):
            with self.assertRaises(client.EmailButlerClaimUnknown):
                self.acquire()
        current=claims.record_result('registration:17',rejected=True)
        self.assertEqual(current['status'],'request_unknown')

    def test_concurrent_generic_claim_has_one_first_submission(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from core.storage.email import butler_claims as claims
        ready=threading.Barrier(2)
        posts=[]
        def request(method,path,**kwargs):
            if method=='GET':
                ready.wait(timeout=5)
                return {'capabilities':[]}
            posts.append(kwargs['json']['acquisition_id'])
            return {'mailbox':{'id':'generic-1','email':'generic@example.test','provider':'mailcom','leased_until':'2099-01-01T00:00:00Z'}}
        def acquire(_):
            try:
                return self.acquire()
            except client.EmailButlerClaimUnknown:
                return None
        with patch.object(client,'_request',side_effect=request),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(acquire,range(2)))
        self.assertEqual(posts,['registration:17'])
        self.assertTrue(any(results))
        self.assertEqual(claims.get_intent('registration:17')['status'],'claimed')
