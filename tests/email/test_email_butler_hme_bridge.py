# -*- coding: utf-8 -*-
"""统一 Butler 后的新租约及历史 HME 身份桥接回归。"""
import unittest
import os
import hashlib
from contextlib import contextmanager
from unittest.mock import patch

from config import email as cfg
from core.email.email_butler import client as butler
from core.email import derivation as email_derivation, provider as email_provider
from core.email import forward_imap as imap
from core.email.icloud_hide import client as hme
from core.storage import records as record_store
from core.storage.email import address_allocations as allocations
from tests.support_pg import PostgresTestCase


MAILBOX = "final@example.test"
PARENT = "alias@icloud.com"


def mailbox(address=PARENT):
    return {"id": "lease-test:" + address, "email": address, "lease_id": "lease-test",
        "provider": "icloud_hme", "mailbox_email": MAILBOX,
        "recipient_mode": "forwarded_exact_v1", "strict_family": True}


def answer(address=PARENT):
    return {"code": 200, "verification_code": "654321", "recipient_mode": "forwarded_exact_v1",
        "recipient_match": {"email": address, "mailbox_email": MAILBOX, "strict_family": True},
        "recipient_evidence": {"original_recipients": [address]}}


class ButlerHMEProviderTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.secrets = patch.object(email_derivation, "_save_profile_secret",
            side_effect=lambda reference, value: os.environ.__setitem__(reference, value))
        self.secrets.start()
        self.addCleanup(self.secrets.stop)
        self.scope = patch.multiple(cfg, EMAIL_BUTLER_API_BASE="https://test.example/v1", EMAIL_BUTLER_API_KEY="test-key")
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.cache = patch.dict(butler._CONTEXT_CACHE, {}, clear=True)
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def seed_legacy(self, acquisition_id='intent', *, value=None, restore=True):
        from core.storage.email import butler_claims as claims
        os.environ['LEGACY_HME_TEST_SECRET'] = 'test-key'
        claims.prepare(acquisition_id=acquisition_id, owner_kind='registration_root', owner_id='root',
                       api_base='https://test.example/v2', credential_ref='LEGACY_HME_TEST_SECRET')
        intent = claims.record_result(acquisition_id, mailbox=value or mailbox())
        if not restore:
            return intent
        return butler.pick_account(owner_kind='registration_root', owner_id='root', acquisition_id=acquisition_id)

    @contextmanager
    def v2_inbox(self):
        from core.email.email_butler import lease_bindings, v2
        binding = {'lease_id': 'lse_original_hme', 'client_id': 'original-client', 'api_base': 'https://test.example/v2'}
        receipt = {'lease_id': 'lse_original_hme', 'service': 'openai', 'status': 'matched',
                   'verification_code': '654321', 'code_id': 'code-original', 'received_at': '1970-01-01T00:02:00Z'}
        with patch.object(lease_bindings, 'resolve', return_value=binding) as resolve, \
                patch.object(v2, 'code', return_value=receipt) as code, \
                patch.object(v2, 'create_lease', side_effect=AssertionError('历史恢复不能新分配')), \
                patch.object(butler, '_request', side_effect=AssertionError('不能调用退役接口')):
            yield resolve, code

    def reports(self):
        return record_store.list_rows(record_store.EMAIL_USAGE_REPORTS, where='address_norm = %s', params=(PARENT,))

    def test_historical_hme_identity_restores_and_uses_original_v2_lease(self):
        with patch.object(butler, '_request', side_effect=AssertionError('不能新申请')):
            account = self.seed_legacy('intent-17')
        self.assertEqual(account.email, PARENT)
        self.assertEqual(account.acquisition_id, 'intent-17')
        self.assertTrue(account.strict_family)
        with self.v2_inbox() as (resolve, code):
            self.assertEqual(butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), '654321')
        self.assertEqual(resolve.call_args.args[0], PARENT)
        self.assertEqual(resolve.call_args.kwargs['acquisition_id'], 'intent-17')
        self.assertEqual(code.call_args.args[0], 'lse_original_hme')
        self.assertEqual(code.call_args.kwargs['since'], '1970-01-01T00:01:40Z')

    def test_historical_hme_receipt_missing_strict_contract_is_rejected_before_caching(self):
        value = mailbox()
        value.pop('recipient_mode')
        self.seed_legacy(value=value, restore=False)
        with patch.object(butler, '_request') as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'recipient_contract_unsupported'):
                butler.pick_account(owner_kind='registration_root', owner_id='root', acquisition_id='intent')
        request.assert_not_called()
        self.assertIsNone(butler.get_account_context(PARENT))

    def test_restore_rejects_a_different_full_address(self):
        intent = self.seed_legacy(value=mailbox('other@icloud.com'), restore=False)
        record_store.patch_row(record_store.EMAIL_BUTLER_CLAIM_INTENTS, intent['id'], {'address_norm': PARENT})
        with patch.object(butler, '_request') as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'recipient_mismatch'):
                butler.restore_account_context(PARENT)
        request.assert_not_called()
        self.assertIsNone(butler.get_account_context(PARENT))

    def test_otp_restore_keeps_specific_recipient_failure(self):
        intent = self.seed_legacy(value=mailbox('other@icloud.com'), restore=False)
        record_store.patch_row(record_store.EMAIL_BUTLER_CLAIM_INTENTS, intent['id'], {'address_norm': PARENT})
        with patch.object(butler, '_request') as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'recipient_mismatch'):
                butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1)
        request.assert_not_called()
        self.assertIsNone(butler.get_account_context(PARENT))

    def test_historical_report_is_explicitly_retired_without_http(self):
        with patch('requests.request') as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'api_version_retired') as error:
                butler._request('POST', '/identities/report', json={'email': PARENT, 'status': 'ok'})
        self.assertEqual(error.exception.error_code, 'api_version_retired')
        request.assert_not_called()

    def test_historical_hme_keeps_fixed_connection_for_otp_and_local_result(self):
        self.seed_legacy('original-connection')
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://changed.test/v2', EMAIL_BUTLER_API_KEY='changed'), self.v2_inbox() as (resolve, code):
            self.assertEqual(butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), '654321')
            butler.release_account(PARENT, status='used')
        for call in (resolve.call_args, code.call_args):
            self.assertEqual(call.kwargs['api_base'], 'https://test.example/v2')
            self.assertEqual(call.kwargs['api_key'], 'test-key')
        reports = self.reports()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['state'], 'local_only')
        self.assertEqual(reports[0]['api_base'], 'https://test.example/v2')

    def test_historical_hme_scan_is_unsupported_without_reallocation(self):
        from core.email.email_butler import v2
        self.seed_legacy('scan-intent')
        butler._CONTEXT_CACHE.clear()
        before = allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT))
        with patch.object(butler, '_request') as request, patch.object(v2, 'create_lease') as create:
            with self.assertRaises(butler.EmailButlerClientError) as caught:
                butler.scan_openai_deactivation(PARENT)
        self.assertEqual(caught.exception.error_code, 'signal_scan_unsupported')
        self.assertEqual(allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT)), before)
        request.assert_not_called()
        create.assert_not_called()

    def test_cached_hme_scan_is_explicitly_unsupported_without_http_or_reallocation(self):
        context = butler.EmailButlerAccount(PARENT, 'lease-hme', provider='icloud_hme', mailbox_email=MAILBOX,
            api_base='https://cached.test/v1', api_key='cached-key', strict_family=True)
        butler._CONTEXT_CACHE[PARENT] = context
        with patch.object(butler, '_restore_hme_context', side_effect=AssertionError('不能重建身份')), \
                patch.object(butler, '_request') as request:
            with self.assertRaises(butler.EmailButlerClientError) as error:
                butler.scan_openai_deactivation(PARENT)
        self.assertEqual(error.exception.error_code, 'signal_scan_unsupported')
        self.assertIs(butler.get_account_context(PARENT), context)
        request.assert_not_called()

    def test_completed_hme_registration_retries_failed_local_result_without_remote_report(self):
        from core.registration.service import _mark_completed_registration_email
        from core.email.email_butler import usage_reports
        self.seed_legacy('stable-result')
        original_enqueue = usage_reports.enqueue
        with patch.object(usage_reports, 'enqueue', side_effect=OSError('local write failure')), \
                patch.object(butler, '_request', side_effect=AssertionError('没有远端注册报告')):
            with self.assertLogs('core.registration_service', level='ERROR'):
                self.assertFalse(_mark_completed_registration_email(PARENT, 1, source='email_butler'))
        self.assertIsNotNone(butler.get_account_context(PARENT))
        self.assertEqual(self.reports(), [])
        with patch.object(usage_reports, 'enqueue', wraps=original_enqueue), patch.object(butler, '_request') as request:
            self.assertTrue(_mark_completed_registration_email(PARENT, 1, source='email_butler'))
            self.assertTrue(_mark_completed_registration_email(PARENT, 1, source='email_butler'))
        self.assertEqual(len(self.reports()), 1)
        self.assertEqual(self.reports()[0]['state'], 'local_only')
        request.assert_not_called()

    def test_hme_local_result_recovers_persisted_identity_after_cache_loss(self):
        from core.registration.service import _mark_completed_registration_email
        self.seed_legacy('restart-result')
        self.assertTrue(_mark_completed_registration_email(PARENT, 1, source='email_butler'))
        first = self.reports()[0]
        butler._CONTEXT_CACHE.clear()
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE='', EMAIL_BUTLER_API_KEY=''), patch.object(butler, '_request') as request:
            self.assertTrue(_mark_completed_registration_email(PARENT, 1, source='email_butler'))
        self.assertEqual(len(self.reports()), 1)
        self.assertEqual(self.reports()[0]['operation_id'], first['operation_id'])
        self.assertEqual(self.reports()[0]['credential_ref'], first['credential_ref'])
        self.assertEqual(self.reports()[0]['address_norm'], PARENT)
        request.assert_not_called()

    def test_hme_local_persistence_failure_can_retry_same_confirmed_acquisition(self):
        from core.storage.email import butler_claims as claims
        self.seed_legacy('persist-retry', restore=False)
        with patch.object(email_derivation, '_save_profile_secret', side_effect=OSError('临时写入失败')), \
                patch.object(butler, '_request') as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'email_derivation_profile_unavailable'):
                butler.pick_account(owner_kind='registration_root', owner_id='root', acquisition_id='persist-retry')
        self.assertIsNone(butler.get_account_context(PARENT))
        self.assertEqual(claims.get_intent('persist-retry')['status'], 'claimed')
        with patch.object(butler, '_request') as retry:
            account = butler.pick_account(owner_kind='registration_root', owner_id='root', acquisition_id='persist-retry')
        self.assertEqual(account.email, PARENT)
        self.assertEqual(account.acquisition_id, 'persist-retry')
        request.assert_not_called()
        retry.assert_not_called()

    def test_unknown_hme_outcomes_keep_context_and_do_not_report(self):
        account = butler.EmailButlerAccount(email=PARENT, mailbox_id="lease-test", provider="icloud_hme",
            mailbox_email=MAILBOX, recipient_mode="forwarded_exact_v1", strict_family=True)
        butler._CONTEXT_CACHE[PARENT] = account
        with patch.object(butler, "_request", side_effect=AssertionError("未知结果不能报告或释放")):
            for status in ("request_unknown", "unknown", "running", "reserved"):
                butler.release_account(PARENT, status=status)
                self.assertIs(butler.get_account_context(PARENT), account)
        butler._CONTEXT_CACHE.clear()
        with patch.object(butler, "_restore_hme_context", side_effect=AssertionError("未知结果不恢复或改变身份")):
            for status in ("request_unknown", "unknown", "running", "reserved"):
                butler.release_account(PARENT, status=status)

    def test_hme_success_aliases_keep_one_local_operation_after_cache_loss(self):
        self.seed_legacy('success-aliases')
        with patch.object(butler, '_request') as request:
            butler.release_account(PARENT, status='used')
            self.assertIsNone(butler.get_account_context(PARENT))
            operation = self.reports()[0]['operation_id']
            butler.release_account(PARENT, status='success')
        self.assertEqual(len(self.reports()), 1)
        self.assertEqual(self.reports()[0]['operation_id'], operation)
        self.assertEqual(self.reports()[0]['state'], 'local_only')
        request.assert_not_called()

    def test_generic_restore_and_v2_otp_keep_hme_identity_after_success_and_cache_loss(self):
        self.seed_legacy('original-acquisition')
        butler.release_account(PARENT, status='used')
        operation_id = self.reports()[0]['operation_id']
        before_profiles = allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT))
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE='https://changed.test/v2', EMAIL_BUTLER_API_KEY='changed'), self.v2_inbox() as (resolve, _):
            self.assertEqual(email_provider.restore_email_context(PARENT, source='email_butler'), 'email_butler')
            restored = butler.restore_account_context(PARENT, api_base='https://override.test/v2', api_key='override')
            self.assertEqual((restored.api_base, restored.api_key, restored.acquisition_id),
                             ('https://test.example/v2', 'test-key', 'original-acquisition'))
            butler.release_account(PARENT, status='success')
            self.assertIsNone(butler.get_account_context(PARENT))
            self.assertEqual(butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), '654321')
            self.assertEqual(resolve.call_args.kwargs['acquisition_id'], 'original-acquisition')
            butler.release_account(PARENT, status='used')
        self.assertEqual(allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT)), before_profiles)
        self.assertEqual(len(self.reports()), 1)
        self.assertEqual(self.reports()[0]['operation_id'], operation_id)

    def test_hme_local_result_uses_persisted_identity_over_empty_cached_acquisition(self):
        self.seed_legacy('persisted-acquisition')
        before_profiles = allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT))
        cached = butler.get_account_context(PARENT)
        cached.acquisition_id = ''
        cached.api_base, cached.api_key = 'https://changed.test/v2', 'changed'
        with patch.object(butler, '_request') as request:
            butler.release_account(PARENT, status='used')
        report = self.reports()[0]
        expected = hashlib.sha256(b'turb-hme:persisted-acquisition:ok').hexdigest()
        self.assertEqual(report['operation_id'], expected)
        self.assertEqual(report['api_base'], 'https://test.example/v2')
        self.assertEqual(report['credential_ref'], before_profiles[0]['credential_ref'])
        self.assertEqual(allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT)), before_profiles)
        request.assert_not_called()

    def test_mailcom_result_does_not_release_remote_lease_or_inherit_hme_identity(self):
        from core.email.email_butler import v2
        self.seed_legacy('shared-final')
        other = 'mailcom@example.test'
        butler._CONTEXT_CACHE[other] = butler.EmailButlerAccount(email=other, mailbox_id='mailcom-test', provider='mailcom')
        with patch.object(butler, '_request') as request, patch.object(v2, 'release') as release:
            butler.release_account(other, status='used')
            self.assertIsNone(butler.get_account_context(other))
            butler.release_account(other, status='used')
        self.assertEqual(record_store.list_rows(record_store.EMAIL_USAGE_REPORTS), [])
        self.assertIsNotNone(butler.get_account_context(PARENT))
        request.assert_not_called()
        release.assert_not_called()


class HistoricalHMEBridgeTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.secrets = patch.object(email_derivation, "_save_profile_secret",
            side_effect=lambda reference, value: os.environ.__setitem__(reference, value))
        self.secrets.start()
        self.addCleanup(self.secrets.stop)
        self.flag = patch.object(cfg, "ICLOUD_HME_BUTLER_BRIDGE_ENABLED", True, create=True)
        self.flag.start()
        self.addCleanup(self.flag.stop)
        self.config = patch.multiple(cfg, USE_EMAIL_SERVICE=True, EMAIL_SOURCE="email_butler", EMAIL_BUTLER_API_BASE="https://test.example/v1",
            EMAIL_BUTLER_API_KEY="test-key", ICLOUD_HME_INBOX_MODE="forward_butler", ICLOUD_HME_FORWARD_IMAP_EMAIL=MAILBOX, EMAIL_DERIVATION_ENABLED=False)
        self.config.start()
        self.addCleanup(self.config.stop)
        self.cache = patch.dict(butler._CONTEXT_CACHE, {}, clear=True)
        self.cache.start()
        self.addCleanup(self.cache.stop)
        self.parent = record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": PARENT, "account_id": "apple-stable", "anonymous_id": "alias-stable", "status": "used"})
        self.profile = allocations.create_inbox_profile(inbox_key="old-imap", connector="forward_imap", credential_ref="OLD_KEY",
            inbox_locator={"server": "imap.old.test", "email": "old@example.test", "port": 993})
        self.child = allocations.allocate_address(source="icloud_hide", parent_id=self.parent,
            inbox_profile_id=self.profile["id"], acquisition_id="history-intent", owner_kind="registration_root", owner_id="history-root")

    def request(self, method, path, **kwargs):
        if path == "/mailboxes":
            return {"code": 200, "mailbox": mailbox(kwargs["json"]["requested_email"])}
        if path == "/me":
            return {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]}
        if path == "/inbound/code":
            return answer(kwargs["json"]["email"])
        if path == "/identities/report":
            return {"code": 200}
        self.fail("桥接不应调用其他接口")

    @contextmanager
    def v2_inbox(self):
        from core.email.email_butler import lease_bindings, v2
        leases = {}
        def resolve(address, **kwargs):
            identifier = 'lse_' + hashlib.sha256(address.encode()).hexdigest()[:16]
            leases[identifier] = address
            return {'lease_id': identifier, 'client_id': 'stable-client', 'email': address,
                'provider': 'icloud_hme', 'service': 'openai', 'status': 'active', 'expires_at': None,
                'api_base': v2.normalize_base(kwargs['api_base'])}
        def code(lease_id, **kwargs):
            self.assertIn(lease_id, leases)
            return {'lease_id': lease_id, 'service': 'openai', 'status': 'matched',
                'verification_code': '654321', 'code_id': 'code_stable_delivery',
                'received_at': '1970-01-01T00:02:00Z'}
        with patch.object(lease_bindings, 'resolve', side_effect=resolve) as restored, \
                patch.object(v2, 'code', side_effect=code) as fetched, \
                patch.object(v2, 'create_lease', side_effect=AssertionError('历史恢复不能新领邮箱')), \
                patch.object(butler, '_request', side_effect=AssertionError('不能调用退役接口')):
            yield restored, fetched

    def test_historical_child_restores_and_receives_without_sidecar_imap_or_old_secret(self):
        address = self.child['address']
        with self.v2_inbox() as (restored, fetched), patch.object(
                hme, '_request', side_effect=AssertionError('不能依赖本机 sidecar')), patch.object(
                imap, '_connect', side_effect=AssertionError('不能读取本机 IMAP')):
            self.assertEqual(email_provider.restore_email_context(address, source='icloud_hide'), 'icloud_hide')
            self.assertEqual(email_provider.wait_for_otp(address, after_ts=100, email_source='icloud_hide', max_wait=1), '654321')
        self.assertEqual(restored.call_args.args, (address,))
        self.assertEqual(fetched.call_args.kwargs['since'], '1970-01-01T00:01:40Z')
        saved = allocations.get_allocation(self.child['id'])
        self.assertEqual((saved['address'], saved['owner_id'], saved['acquisition_id'], saved['state']),
            (address, 'history-root', 'history-intent', 'reserved'))

    def test_direct_parent_and_bound_entrypoints_use_bridge(self):
        with self.v2_inbox() as (restored, fetched), patch.object(
                imap, '_connect', side_effect=AssertionError('不能读取本机 IMAP')), patch.object(
                hme, '_request', side_effect=AssertionError('不能访问 sidecar')):
            self.assertEqual(hme.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), '654321')
            self.assertEqual(email_derivation.fetch_bound_otp(self.child['address'], after_ts=100, max_wait=1), '654321')
        self.assertEqual([call.args[0] for call in restored.call_args_list], [PARENT, self.child['address']])
        self.assertNotEqual(fetched.call_args_list[0].args[0], fetched.call_args_list[1].args[0])

    def test_strict_butler_candidate_is_retained_in_child_authentication_ledger(self):
        from core.auth.email_guard import email_auth_session
        address = self.child['address']
        with email_auth_session(address) as session, self.v2_inbox():
            self.assertEqual(email_provider.wait_for_otp(address, after_ts=100, max_wait=1), '654321')
            saved = allocations.get_otp_request(session.row['id'])
            self.assertTrue(saved['candidate_message_key'].endswith(':code_stable_delivery'))
            self.assertEqual(saved['candidate_evidence']['recipient'], address)
            self.assertEqual(saved['candidate_evidence']['contract'], 'butler.v2.lease')
            self.assertEqual(saved['candidate_evidence']['code_id'], 'code_stable_delivery')
            self.assertEqual(saved['submission_state'], 'offered')
            self.assertEqual(saved['cursor']['butler_v2_after_code_id'], 'code_stable_delivery')
            self.assertNotIn('original_recipients', saved['candidate_evidence'])
            self.assertNotIn('654321', str(saved))

    def test_bulk_scan_restores_parent_profile_without_any_child_allocation(self):
        from core.email.email_butler import bridge as email_butler_bridge

        ref = "EMAIL_DERIVATION_BUTLER_SECRET_PARENT_ONLY"
        profile = allocations.create_inbox_profile(inbox_key="parent-only-butler", connector="forward_butler", credential_ref=ref,
            inbox_locator={"api_base": "https://pinned.test/v1", "mailbox_email": MAILBOX})
        parent = "parent-only@icloud.com"
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {
            "email": parent, "account_id": "apple-stable", "status": "used",
            "derivation_policy": {"inbox_profile_id": profile["id"]}})
        with patch.dict(os.environ, {ref: "pinned-key"}):
            restored = email_butler_bridge.inbox_profiles_for_addresses([parent])
        self.assertEqual(restored[parent]["api_base"], "https://pinned.test/v2")
        self.assertEqual(restored[parent]["api_key"], "pinned-key")
        self.assertTrue(restored[parent]["strict_family"])

    def test_release_of_fixed_imap_child_retains_identity_without_remote_report(self):
        with patch.object(butler, "_request", side_effect=self.request) as request:
            email_provider.release_email(self.child["address"], status="used", source="icloud_hide")
        request.assert_not_called()
        self.assertEqual(record_store.list_rows(record_store.EMAIL_USAGE_REPORTS), [])
        saved = allocations.get_allocation(self.child["id"])
        self.assertEqual(saved["state"], "used")
        self.assertEqual(saved["acquisition_id"], "history-intent")
        self.assertEqual(saved["owner_id"], "history-root")

    def test_unknown_outcome_does_not_release_remote_identity(self):
        with patch.object(butler, "_request", side_effect=self.request) as request:
            email_provider.release_email(self.child["address"], status="request_unknown", source="icloud_hide")
        self.assertFalse(any(call.args[1] in {"/identities/report", "/mailboxes"} for call in request.call_args_list))
        self.assertEqual(allocations.get_allocation(self.child["id"])["state"], "reserved")

    def test_parent_uses_pinned_butler_profile_when_global_connection_changes(self):
        from core.storage.email.inbox_cutover import apply_cutover, plan_cutover
        ref = 'EMAIL_DERIVATION_BUTLER_SECRET_PINNED'
        apply_cutover(plan_cutover(api_base='https://pinned.test/v1', mailbox_email=MAILBOX, credential_ref=ref))
        with patch.dict(os.environ, {ref: 'pinned-key'}), patch.multiple(cfg,
                EMAIL_BUTLER_API_BASE='', EMAIL_BUTLER_API_KEY='', ICLOUD_HME_FORWARD_IMAP_EMAIL=''), \
                self.v2_inbox() as (restored, fetched):
            self.assertEqual(hme.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), '654321')
        self.assertEqual(restored.call_args.args, (PARENT,))
        self.assertEqual(restored.call_args.kwargs['credential_ref'], ref)
        self.assertEqual(restored.call_args.kwargs['api_base'], 'https://pinned.test/v2')
        self.assertEqual(restored.call_args.kwargs['api_key'], 'pinned-key')
        self.assertEqual(fetched.call_args.kwargs['api_base'], 'https://pinned.test/v2')
        self.assertEqual(fetched.call_args.kwargs['api_key'], 'pinned-key')

    def test_unknown_parent_preserves_local_pool_state(self):
        before = record_store.get_row(record_store.ICLOUD_HIDE_POOL, self.parent)
        with patch.object(butler, "_request", side_effect=AssertionError("未知结果不写远端")):
            hme.release_account(PARENT, status="request_unknown")
        self.assertEqual(record_store.get_row(record_store.ICLOUD_HIDE_POOL, self.parent), before)

    def test_new_hme_pick_requires_local_inventory_while_historical_child_restores(self):
        with patch.object(hme, 'sync_aliases', side_effect=AssertionError('不能访问 sidecar')), \
                patch.object(butler, '_request') as request:
            with self.assertRaisesRegex(hme.ICloudHMEError, 'local_email_inventory_empty'):
                hme.pick_account(owner_kind='registration_root', owner_id='root', acquisition_id='fresh-intent')
            self.assertEqual(email_provider.acquire_email('icloud_hide', owner_kind='registration_root',
                             owner_id='history-root', acquisition_id='history-intent'), self.child['address'])
        request.assert_not_called()

    def test_flag_disabled_preserves_original_bound_route(self):
        with patch.object(cfg, "ICLOUD_HME_BUTLER_BRIDGE_ENABLED", False), patch.object(
                email_derivation, "_profile_credentials", return_value={"connector": "forward_imap"}), patch.object(
                imap, "fetch_latest_otp", return_value="123456"), patch.object(
                butler, "_request", side_effect=AssertionError("关闭开关不能调用 Butler")):
            self.assertEqual(hme.fetch_latest_otp(self.child["address"], after_ts=100, max_wait=1), "123456")

    def test_report_operation_id_stays_stable_on_same_outcome_retry(self):
        from core.storage.email.inbox_cutover import apply_cutover, plan_cutover
        reference = "EMAIL_DERIVATION_BUTLER_SECRET_REPORT_FIXTURE"
        apply_cutover(plan_cutover(api_base="https://fixed.example/v1", mailbox_email=MAILBOX, credential_ref=reference))
        with patch.object(butler, "_request", side_effect=self.request) as request:
            hme.release_account(self.child["address"], status="success")
            hme.release_account(self.child["address"], status="used")
        request.assert_not_called()
        reports = record_store.list_rows(record_store.EMAIL_USAGE_REPORTS)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["state"], "local_only")
        self.assertEqual(reports[0]["credential_ref"], reference)
        self.assertEqual(reports[0]["address_norm"], self.child["address"])


if __name__ == "__main__":
    unittest.main()
