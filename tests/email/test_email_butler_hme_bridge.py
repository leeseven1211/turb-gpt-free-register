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

    def test_new_hme_lease_preserves_intent_and_uses_strict_inbound_instead_of_messages(self):
        calls = []

        def request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            if path == "/mailboxes":
                return {"code": 200, "mailbox": mailbox()}
            if path == "/me":
                return {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]}
            if path == "/inbound/code":
                return answer()
            self.fail("HME 不得走普通 messages 轮询")

        with patch.object(butler, "_request", side_effect=request):
            account = butler.pick_account(owner_kind="registration_root", owner_id="root-17", acquisition_id="intent-17")
            self.assertEqual(account.email, PARENT)
            self.assertEqual(butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), "654321")
        self.assertEqual(next(row for row in calls if row[1] == "/mailboxes")[2]["json"], {"owner_kind": "registration_root", "owner_id": "root-17", "acquisition_id": "intent-17"})
        inbound = next(row for row in calls if row[1] == "/inbound/code")
        self.assertEqual(inbound[2]["json"]["mailbox_email"], MAILBOX)
        self.assertTrue(inbound[2]["json"]["strict_family"])

    def test_hme_lease_missing_strict_contract_is_rejected_before_caching(self):
        value = mailbox()
        value.pop("recipient_mode")
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": value}):
            with self.assertRaisesRegex(butler.EmailButlerClientError, "recipient_contract_unsupported"):
                butler.pick_account()
        self.assertIsNone(butler.get_account_context(PARENT))

    def test_restore_rejects_a_different_full_address(self):
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox("other@icloud.com")}):
            with self.assertRaisesRegex(butler.EmailButlerClientError, "recipient_mismatch"):
                butler.restore_account_context(PARENT)

    def test_otp_restore_keeps_specific_recipient_failure(self):
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox("other@icloud.com")}):
            with self.assertRaisesRegex(butler.EmailButlerClientError, "recipient_mismatch"):
                butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1)

    def test_historical_report_is_explicitly_retired_without_http(self):
        with patch('requests.request') as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'api_version_retired') as error:
                butler._request('POST', '/identities/report', json={'email': PARENT, 'status': 'ok'})
        self.assertEqual(error.exception.error_code, 'api_version_retired')
        request.assert_not_called()

    def test_new_hme_lease_keeps_connection_for_fetch_and_release(self):
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="intent")
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE="https://changed.test/v1", EMAIL_BUTLER_API_KEY="changed"), patch.object(
                butler, "fetch_inbound_otp", return_value="654321") as fetch, patch.object(
                butler, "_request", return_value={"code": 200}) as request:
            self.assertEqual(butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), "654321")
            butler.release_account(PARENT, status="used")
        self.assertEqual(fetch.call_args.kwargs["api_base"], "https://test.example/v1")
        self.assertEqual(fetch.call_args.kwargs["api_key"], "test-key")
        self.assertEqual(request.call_args.kwargs["api_base"], "https://test.example/v1")
        self.assertEqual(request.call_args.kwargs["api_key"], "test-key")

    def test_new_hme_scan_restores_strict_fixed_context_without_a_new_lease(self):
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="scan-intent")
        butler._CONTEXT_CACHE.clear()
        result = {**answer(), "signal": {"detected": False}}
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE="", EMAIL_BUTLER_API_KEY=""), patch.object(
            butler, "_request", return_value=result
        ) as request:
            scanned = butler.scan_openai_deactivation(PARENT)
        self.assertTrue(scanned["ok"])
        request.assert_called_once()
        self.assertEqual(request.call_args.args[1], "/signals/scan")
        self.assertEqual(request.call_args.kwargs["api_base"], "https://test.example/v1")
        self.assertEqual(request.call_args.kwargs["api_key"], "test-key")
        self.assertEqual(request.call_args.kwargs["json"]["mailbox_email"], MAILBOX)
        self.assertTrue(request.call_args.kwargs["json"]["strict_family"])

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

    def test_completed_hme_registration_retries_real_report_after_network_failure(self):
        from core.registration.service import _mark_completed_registration_email
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="stable-result")
        with patch.object(butler, "_request", side_effect=[butler.EmailButlerClientError("网络连接中断"), {"code": 200}]) as request:
            with self.assertLogs('core.registration_service', level="ERROR"):
                self.assertFalse(_mark_completed_registration_email(PARENT, 1, source="email_butler"))
            self.assertIsNotNone(butler.get_account_context(PARENT))
            self.assertTrue(_mark_completed_registration_email(PARENT, 1, source="email_butler"))
        self.assertEqual(len(request.call_args_list), 2)
        self.assertEqual([call.args[1] for call in request.call_args_list], ["/identities/report"] * 2)
        self.assertEqual(request.call_args_list[0].kwargs["json"]["operation_id"], request.call_args_list[1].kwargs["json"]["operation_id"])

    def test_hme_report_recovers_exact_persisted_identity_after_cache_loss(self):
        from core.registration.service import _mark_completed_registration_email
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="restart-result")
        with patch.object(butler, "_request", side_effect=butler.EmailButlerClientError("网络连接中断")) as first:
            with self.assertLogs('core.registration_service', level="ERROR"):
                self.assertFalse(_mark_completed_registration_email(PARENT, 1, source="email_butler"))
        operation_id = first.call_args.kwargs["json"].get("operation_id")
        butler._CONTEXT_CACHE.clear()
        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE="", EMAIL_BUTLER_API_KEY=""), patch.object(
                butler, "_request", return_value={"code": 200}) as second:
            self.assertTrue(_mark_completed_registration_email(PARENT, 1, source="email_butler"))
        second.assert_called_once()
        self.assertEqual(second.call_args.args[1], "/identities/report")
        self.assertEqual(second.call_args.kwargs["api_base"], "https://test.example/v1")
        self.assertEqual(second.call_args.kwargs["api_key"], "test-key")
        self.assertEqual(second.call_args.kwargs["json"]["email"], PARENT)
        self.assertTrue(operation_id)
        self.assertEqual(second.call_args.kwargs["json"]["operation_id"], operation_id)

    def test_hme_local_persistence_failure_can_retry_same_acquisition(self):
        with patch.object(email_derivation, "_save_profile_secret", side_effect=OSError("临时写入失败")), patch.object(
                butler, "_request", return_value={"code": 200, "mailbox": mailbox()}) as first:
            with self.assertRaisesRegex(butler.EmailButlerClientError, "email_derivation_profile_unavailable"):
                butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="persist-retry")
        self.assertIsNone(butler.get_account_context(PARENT))
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}) as second:
            self.assertEqual(butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="persist-retry").email, PARENT)
        first.assert_not_called()
        self.assertEqual(second.call_args.kwargs["json"]["acquisition_id"], "persist-retry")

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

    def test_hme_success_aliases_keep_operation_id_after_success_and_cache_loss(self):
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="success-aliases")
        with patch.object(butler, "_request", return_value={"code": 200}) as request:
            butler.release_account(PARENT, status="used")
            self.assertIsNone(butler.get_account_context(PARENT))
            butler.release_account(PARENT, status="success")
        self.assertEqual(len(request.call_args_list), 2)
        self.assertEqual(request.call_args_list[0].kwargs["json"]["operation_id"], request.call_args_list[1].kwargs["json"]["operation_id"])

    def test_generic_restore_and_otp_keep_hme_identity_after_success_and_cache_loss(self):
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="original-acquisition")
        with patch.object(butler, "_request", return_value={"code": 200}) as first:
            butler.release_account(PARENT, status="used")
        operation_id = first.call_args.kwargs["json"]["operation_id"]
        before_profiles = allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT))

        def request(method, path, **kwargs):
            self.assertNotEqual(path, "/mailboxes", "恢复原 HME 不能重新申请租约")
            self.assertEqual(kwargs.get("api_base"), "https://test.example/v1")
            self.assertEqual(kwargs.get("api_key"), "test-key")
            if path == "/me":
                return {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]}
            if path == "/inbound/code":
                return answer()
            self.assertEqual(path, "/identities/report", "恢复原 HME 不能重新申请租约")
            self.assertEqual(kwargs["json"]["operation_id"], operation_id)
            return {"code": 200}

        with patch.multiple(cfg, EMAIL_BUTLER_API_BASE="https://changed.test/v1", EMAIL_BUTLER_API_KEY="changed"), patch.object(
                butler, "_request", side_effect=request) as requests:
            self.assertEqual(email_provider.restore_email_context(PARENT, source="email_butler"), "email_butler")
            self.assertEqual(butler.get_account_context(PARENT).acquisition_id, "original-acquisition")
            self.assertEqual(requests.call_count, 0)
            restored = butler.restore_account_context(PARENT, api_base="https://override.test/v1", api_key="override")
            self.assertEqual((restored.api_base, restored.api_key, restored.acquisition_id),
                ("https://test.example/v1", "test-key", "original-acquisition"))
            butler.release_account(PARENT, status="success")
            self.assertIsNone(butler.get_account_context(PARENT))
            self.assertEqual(butler.fetch_latest_otp(PARENT, after_ts=100, max_wait=1), "654321")
            self.assertEqual(butler.get_account_context(PARENT).acquisition_id, "original-acquisition")
            butler.release_account(PARENT, status="used")
        self.assertEqual(allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT)), before_profiles)

    def test_hme_report_does_not_replace_persisted_acquisition_with_empty_cached_value(self):
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="persisted-acquisition")
        before_profiles = allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT))
        cached = butler.get_account_context(PARENT)
        cached.acquisition_id = ""
        cached.api_base, cached.api_key = "https://changed.test/v1", "changed"
        with patch.object(butler, "_request", return_value={"code": 200}) as report:
            butler.release_account(PARENT, status="used")
        self.assertEqual(report.call_args.kwargs["api_base"], "https://test.example/v1")
        self.assertEqual(report.call_args.kwargs["api_key"], "test-key")
        self.assertEqual(allocations.list_inbox_profiles(inbox_key=butler._hme_profile_key(PARENT)), before_profiles)

    def test_mailcom_keeps_original_release_protocol_and_cache_behavior(self):
        other = "mailcom@example.test"
        with patch.object(butler, "_request", return_value={"code": 200, "mailbox": mailbox()}):
            butler.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="shared-final")
        butler._CONTEXT_CACHE.clear()
        butler._CONTEXT_CACHE[other] = butler.EmailButlerAccount(email=other, mailbox_id="mailcom-test", provider="mailcom")
        with patch.object(butler, "_request", side_effect=butler.EmailButlerClientError("网络连接中断")) as request:
            with self.assertRaises(butler.EmailButlerClientError):
                butler.release_account(other, status="used")
        self.assertEqual(request.call_args.args[1], "/mailboxes/mailcom-test/release")
        self.assertIsNone(butler.get_account_context(other))
        with patch.object(butler, "_request", side_effect=AssertionError("无缓存 MailCom 保留原行为")):
            butler.release_account(other, status="used")


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

    def test_direct_pick_and_queued_hme_pick_use_butler_without_sidecar(self):
        with patch.object(hme, "sync_aliases", side_effect=AssertionError("不能访问 sidecar")), patch.object(
                butler, "_request", return_value={"code": 200, "mailbox": mailbox()}) as request:
            self.assertEqual(hme.pick_account(owner_kind="registration_root", owner_id="root", acquisition_id="fresh-intent").email, PARENT)
            self.assertEqual(email_provider.acquire_email("icloud_hide", owner_kind="registration_root",
                owner_id="history-root", acquisition_id="history-intent"), self.child["address"])
        acquisitions = [call for call in request.call_args_list if call.args[1] == "/mailboxes"]
        self.assertEqual(len(acquisitions), 1)
        self.assertEqual(acquisitions[0].kwargs["json"]["acquisition_id"], "fresh-intent")

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
