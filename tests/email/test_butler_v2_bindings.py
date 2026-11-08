"""租约映射以原客户端、完整地址和原操作证据隔离，测试使用独立 PG schema。"""
from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

from core.email.email_butler import lease_bindings as bindings, v2
from core.storage import records
from tests.support_pg import PostgresTestCase

BASE = 'https://butler.example/v2'
ADDRESS = 'parent+original@example.test'
CLIENT = 'client-original'


def lease(**changes):
    return {'id': 'lse_original', 'email': ADDRESS, 'service': 'openai', 'provider': 'icloud_hme',
            'client_id': CLIENT, 'status': 'active', 'created_at': '2026-11-08T00:00:00Z',
            'expires_at': None, 'external_ref': 'acquisition-original', **changes}


class ButlerV2BindingsTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        records.init()
        self.remote = [lease()]
        self.client = CLIENT
        self.me = patch.object(v2, 'me', side_effect=lambda **_kwargs: {'client_id': self.client}).start()
        self.get = patch.object(v2, 'get_lease', side_effect=self._get).start()
        self.list = patch.object(v2, 'list_leases', side_effect=lambda **_kwargs: deepcopy(self.remote)).start()
        self.create = patch.object(v2, 'create_lease', side_effect=AssertionError('原租约恢复不能新领邮箱')).start()
        self.release = patch.object(v2, 'release', side_effect=AssertionError('映射阶段不能退租')).start()
        self.addCleanup(patch.stopall)

    def _get(self, lease_id, **_kwargs):
        return deepcopy(next(value for value in self.remote if value['id'] == lease_id))

    def save(self, value=None, **kwargs):
        return bindings.save(lease() if value is None else value, api_base=BASE,
                             credential_ref='credential-original', client_id=CLIENT, **kwargs)

    def resolve(self, **kwargs):
        return bindings.resolve(kwargs.pop('email', ADDRESS), api_base=BASE, api_key='fixture-key',
                                credential_ref='credential-original', **kwargs)

    def assert_code(self, code, action):
        with self.assertRaises(v2.ButlerV2Error) as caught:
            action()
        self.assertEqual(caught.exception.error_code, code)
        self.create.assert_not_called()
        self.release.assert_not_called()

    def test_save_requires_original_client_and_service(self):
        for value in (lease(client_id='another-client'), lease(service='grok'), lease(email='invalid')):
            with self.subTest(value=value):
                expected = 'recipient_mismatch' if value['email'] == 'invalid' else 'lease_identity_mismatch'
                self.assert_code(expected, lambda: self.save(value))
        self.assertEqual(records.count_rows(records.EMAIL_BUTLER_LEASE_BINDINGS), 0)

    def test_resolve_rejects_wrong_full_address_service_and_returned_client(self):
        for field, wrong in (('email', 'other@example.test'), ('service', 'grok'), ('client_id', 'other-client')):
            self.remote = [lease(**{field: wrong})]
            with self.subTest(field=field):
                self.assert_code('lease_identity_mismatch', lambda: self.resolve(acquisition_id='acquisition-original'))
        self.assertEqual(records.count_rows(records.EMAIL_BUTLER_LEASE_BINDINGS), 0)

    def test_resolve_rejects_expected_client_change_before_querying_remote_leases(self):
        self.client = 'replacement-client'
        self.assert_code('lease_client_mismatch', lambda: self.resolve(client_id=CLIENT))
        self.get.assert_not_called()
        self.list.assert_not_called()

    def test_exact_external_ref_recovers_original_instead_of_another_active_lease(self):
        self.remote = [lease(id='lse_later', external_ref='later-acquisition'), lease()]
        row = self.resolve(acquisition_id='acquisition-original')
        self.assertEqual(row['lease_id'], 'lse_original')
        self.assertTrue(row['original_ref_verified'])
        self.assertIn('acquisition-original', row['verified_acquisition_refs'])
        self.assertEqual(self.list.call_args.kwargs['email'], ADDRESS)
        self.assertEqual(self.list.call_args.kwargs['service'], 'openai')
        self.assertEqual(self.list.call_args.kwargs['status'], 'all')

    def test_merged_migration_restores_reading_but_cannot_release_without_exact_original_proof(self):
        self.remote = [lease(external_ref='merged-read-binding')]
        first = self.resolve(acquisition_id='acquisition-original')
        self.assertEqual(first['lease_id'], 'lse_original')
        self.assertFalse(first['original_ref_verified'])
        self.assertEqual(first['verified_acquisition_refs'], [])
        self.list.reset_mock()
        self.assert_code('lease_original_mapping_required', lambda: self.resolve(
            acquisition_id='acquisition-original', for_release=True))
        self.get.assert_called_once()
        self.list.assert_not_called()

    def test_one_verified_acquisition_cannot_grant_release_to_another_read_alias(self):
        self.save(acquisition_id='acquisition-original', original_ref_verified=True)
        read = self.resolve(acquisition_id='unverified-other-acquisition')
        self.assertEqual(read['acquisition_id'], 'acquisition-original')
        self.assertIn('unverified-other-acquisition', read['acquisition_refs'])
        self.assertNotIn('unverified-other-acquisition', read['verified_acquisition_refs'])
        self.assert_code('lease_original_mapping_required', lambda: self.resolve(
            acquisition_id='unverified-other-acquisition', for_release=True))
        self.assertEqual(self.resolve(acquisition_id='acquisition-original', for_release=True)['lease_id'], 'lse_original')

    def test_verified_references_merge_only_for_individually_verified_operations(self):
        self.save(acquisition_id='acquisition-original', original_ref_verified=True)
        self.save(acquisition_id='acquisition-second', original_ref_verified=True)
        self.save(acquisition_id='acquisition-original', original_ref_verified=False)
        row = self.resolve(acquisition_id='acquisition-second', for_release=True)
        self.assertEqual(row['verified_acquisition_refs'], ['acquisition-original', 'acquisition-second'])
        self.assertTrue(row['original_ref_verified'])
        self.list.assert_not_called()

    def test_explicit_lease_id_does_not_borrow_another_acquisitions_proof(self):
        self.save(acquisition_id='acquisition-original', original_ref_verified=True)
        self.remote.append(lease(id='lse_later', external_ref='later-acquisition'))
        self.assert_code('lease_original_mapping_required', lambda: self.resolve(
            acquisition_id='acquisition-original', lease_id='lse_later', for_release=True))
        self.get.assert_called_once_with('lse_later', api_base=BASE, api_key='fixture-key')

    def test_explicit_original_v2_lease_id_can_be_released_without_an_acquisition_alias(self):
        row = self.resolve(lease_id='lse_original', for_release=True)
        self.assertEqual(row['lease_id'], 'lse_original')
        self.list.assert_not_called()

    def test_persisted_mapping_is_reused_after_restart_without_reselecting(self):
        self.save(acquisition_id='acquisition-original')
        row = self.resolve(acquisition_id='acquisition-original', client_id=CLIENT)
        self.assertEqual(row['lease_id'], 'lse_original')
        self.get.assert_called_once_with('lse_original', api_base=BASE, api_key='fixture-key')
        self.list.assert_not_called()

    def test_persisted_mapping_rejects_client_swap_even_without_expected_client_argument(self):
        self.save(acquisition_id='acquisition-original')
        self.client = 'replacement-client'
        self.remote = [lease(id='lse_replacement', client_id=self.client)]
        self.assert_code('lease_client_mismatch', lambda: self.resolve(acquisition_id='acquisition-original'))
        self.get.assert_not_called()
        self.list.assert_not_called()

    def test_old_return_resolves_ended_original_and_never_releases_later_lease(self):
        original = lease(status='released')
        self.save(original, acquisition_id='acquisition-original')
        self.remote = [lease(id='lse_later', external_ref='later-acquisition'), original]
        row = self.resolve(acquisition_id='acquisition-original', for_release=True)
        self.assertEqual((row['lease_id'], row['status']), ('lse_original', 'released'))
        self.list.assert_not_called()
        self.assert_code('lease_released', lambda: self.resolve(acquisition_id='acquisition-original'))

    def test_exact_ended_original_wins_over_unrelated_active_lease_without_saved_mapping(self):
        self.remote = [lease(id='lse_later', external_ref='later-acquisition'), lease(status='expired')]
        self.assert_code('lease_expired', lambda: self.resolve(acquisition_id='acquisition-original'))
        row = self.resolve(acquisition_id='acquisition-original', for_release=True)
        self.assertEqual((row['lease_id'], row['status']), ('lse_original', 'expired'))

    def test_ended_or_missing_lease_never_allocates_a_replacement(self):
        for state in ('released', 'expired', 'revoked'):
            self.remote = [lease(status=state)]
            with self.subTest(state=state):
                self.assert_code('lease_' + state, lambda: self.resolve(acquisition_id='acquisition-original'))
        self.remote = []
        self.assert_code('lease_restore_required', self.resolve)

    def test_multiple_active_and_multiple_original_matches_are_ambiguous(self):
        for external_ref in ('different-ref', 'acquisition-original'):
            self.remote = [lease(), lease(id='lse_other', external_ref=external_ref)]
            with self.subTest(external_ref=external_ref):
                self.assert_code('lease_mapping_ambiguous', lambda: self.resolve(
                    acquisition_id='missing' if external_ref == 'different-ref' else 'acquisition-original'))

    def test_active_status_with_past_expiry_is_classified_as_expired(self):
        self.remote = [lease(expires_at='2000-01-01T00:00:00Z')]
        self.assert_code('lease_expired', lambda: self.resolve(acquisition_id='acquisition-original'))

    def test_invalid_expiry_is_classified_instead_of_a_parser_exception(self):
        self.remote = [lease(expires_at='invalid-time')]
        self.assert_code('lease_expiry_invalid', lambda: self.resolve(acquisition_id='acquisition-original'))

    def test_existing_lease_cannot_be_rebound_to_another_address(self):
        self.save(acquisition_id='acquisition-original')
        self.assert_code('lease_identity_mismatch', lambda: self.save(lease(email='other@example.test')))
        row = records.list_rows(records.EMAIL_BUTLER_LEASE_BINDINGS)[0]
        self.assertEqual(row['address_norm'], ADDRESS)

    def test_original_acquisition_cannot_bind_another_lease_even_after_release(self):
        self.save(lease(status='released'), acquisition_id='acquisition-original')
        self.assert_code('lease_mapping_ambiguous', lambda: self.save(
            lease(id='lse_later'), acquisition_id='acquisition-original'))
        self.assertEqual(records.count_rows(records.EMAIL_BUTLER_LEASE_BINDINGS), 1)

    def test_additional_read_reference_cannot_be_rebound_to_another_lease(self):
        self.save(acquisition_id='acquisition-original')
        self.save(acquisition_id='unverified-read-alias', original_ref_verified=False)
        self.assert_code('lease_mapping_ambiguous', lambda: self.save(
            lease(id='lse_later'), acquisition_id='unverified-read-alias', original_ref_verified=False))

    def test_duplicate_historical_pinned_references_are_ambiguous_before_remote_query(self):
        first = self.save(acquisition_id='acquisition-original')
        second = self.save(lease(id='lse_later'), acquisition_id='other-acquisition')
        records.patch_row(records.EMAIL_BUTLER_LEASE_BINDINGS, second['id'], {
            'acquisition_refs': ['acquisition-original', 'other-acquisition']})
        self.assert_code('lease_mapping_ambiguous', lambda: self.resolve(acquisition_id='acquisition-original'))
        self.get.assert_not_called()
        self.list.assert_not_called()
        self.assertEqual(first['lease_id'], 'lse_original')

    def test_parallel_saves_for_same_original_intent_allow_only_one_lease(self):
        barrier = threading.Barrier(2)
        def attempt(lease_id):
            barrier.wait()
            try:
                return self.save(lease(id=lease_id), acquisition_id='parallel-original')['lease_id']
            except v2.ButlerV2Error as exc:
                return exc.error_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, ('lse_one', 'lse_two')))
        self.assertEqual(sum(value == 'lease_mapping_ambiguous' for value in results), 1)
        self.assertEqual(records.count_rows(records.EMAIL_BUTLER_LEASE_BINDINGS), 1)
