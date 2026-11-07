"""历史读绑定只能来自完整地址的原固定路由，不能复活已删除邮箱。"""
import unittest

from tools.maintenance.reconcile_butler_read_bindings import build_bindings
from tools.maintenance.reconcile_butler_service_facts import ReconcileError, transport_base


class ReadBindingReconcileTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'id': 7, 'connector': 'forward_butler', 'state': 'active',
                        'credential_ref': 'ORIGINAL_KEY',
                        'inbox_locator': {'api_base': 'https://butler.example/v1', 'mailbox_email': 'fixed@example.test'}}

    def build(self, rows, tombstones=None, profiles=None):
        return build_bindings(profiles or {7: self.profile}, rows, tombstones or set(), 'turb-local')

    def row(self, email='parent+one@icloud.com', profile=7):
        return {'email': email, 'profile_id': profile, 'record': 'pool:3'}

    def test_full_address_is_independent_and_duplicate_reference_is_stable(self):
        rows = [self.row(), self.row('parent@icloud.com'), self.row()]
        items, issues, _ = self.build(rows)
        self.assertFalse(issues)
        self.assertEqual(len(items), 2)
        self.assertEqual(items, self.build(list(reversed(rows)))[0])
        self.assertEqual(len({r['item']['binding_id'] for r in items}), 2)
        self.assertTrue(all(r['credential_ref'] == 'ORIGINAL_KEY' for r in items))

    def test_tombstone_is_excluded_even_if_old_allocation_survives(self):
        items, issues, skipped = self.build([self.row()], {'parent+one@icloud.com'})
        self.assertEqual(items, [])
        self.assertFalse(issues)
        self.assertEqual(skipped, {'tombstone': 1})

    def test_missing_or_foreign_connector_does_not_guess_global_route(self):
        items, issues, skipped = self.build([self.row(profile=99)])
        self.assertEqual(items, [])
        self.assertEqual(issues[0]['error_code'], 'fixed_route_unavailable')

    def test_multiple_fixed_routes_for_same_address_require_resolution(self):
        profiles = {7: self.profile, 8: {**self.profile, 'id': 8, 'credential_ref': 'OTHER'}}
        _, issues, _ = self.build([self.row(), self.row(profile=8)], profiles=profiles)
        self.assertEqual(issues[0]['error_code'], 'fixed_route_conflict')

    def test_legacy_token_kept_only_with_exact_binding(self):
        items, _, _ = self.build([{**self.row(), 'legacy_lease_id': 'old-token'}])
        self.assertEqual(items[0]['item']['legacy_lease_id'], 'old-token')
        self.assertEqual(items[0]['item']['mailbox_email'], 'fixed@example.test')

    def test_maintenance_transport_requires_loopback(self):
        self.assertEqual(transport_base('https://example/v1', 'http://127.0.0.1:8789/v1'), 'http://127.0.0.1:8789/v1')
        for base in ('https://foreign.example/v1', 'http://127.0.0.1/other', 'http://user:secret@127.0.0.1/v1'):
            with self.assertRaises(ReconcileError):
                transport_base('https://example/v1', base)


class ReadBindingApplyTests(unittest.TestCase):
    def run_fixture(self, *, manifest='match', changed=False):
        from contextlib import ExitStack
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from tools.maintenance import reconcile_butler_read_bindings as tool
        profile = {'id': 7, 'connector': 'forward_butler', 'state': 'active', 'credential_ref': 'KEY',
                   'inbox_locator': {'api_base': 'https://original.example/v1', 'mailbox_email': 'fixed@example.test'}}
        candidates, _, _ = tool.build_bindings({7: profile}, [{'email': 'one@example.test', 'profile_id': 7, 'record': 'pool:1'}], set(), 'turb-local')
        fingerprint = tool.digest(tool.json.dumps(candidates, sort_keys=True))
        collect = [(candidates, [], {}), ([], [], {})] if changed else [(candidates, [], {}), (candidates, [], {})]
        requests_seen = []
        def response(session, method, url, payload=None):
            requests_seen.append((method, url))
            if method == 'GET':
                return {'code': 200, 'capabilities': ['service_read_bindings.reconcile.v1'], 'policy': {'service': 'openai'}}
            return {'code': 200, 'results': [{'address': item['address'], 'binding_id': item['binding_id'], 'code': 200} for item in payload['items']]}
        with TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(tool, 'dotenv_values', return_value={'DATABASE_URL': 'test-db'}))
            stack.enter_context(patch.object(tool.psycopg, 'connect'))
            stack.enter_context(patch.object(tool, 'collect_bindings', side_effect=collect))
            stack.enter_context(patch.object(tool, 'decrypt_routes', return_value={'KEY': 'synthetic-key'}))
            stack.enter_context(patch.object(tool, 'request_json', side_effect=response))
            args = SimpleNamespace(source_root=Path(tmp), source_instance='turb-local', receipt=Path(tmp)/'receipt.json',
                                   apply=True, expected_bindings=1, expected_manifest=fingerprint if manifest == 'match' else manifest,
                                   transport_base=None)
            error = None
            try:
                result = tool.run(args)
            except ReconcileError as exc:
                error, result = str(exc), None
            return result, error, requests_seen

    def test_equal_count_changed_manifest_never_sends(self):
        _, error, calls = self.run_fixture(manifest='changed')
        self.assertEqual(error, 'read_binding_preflight_failed')
        self.assertFalse(calls)

    def test_source_changed_before_batch_never_grants_read(self):
        _, error, calls = self.run_fixture(changed=True)
        self.assertEqual(error, 'read_binding_source_changed')
        self.assertEqual([method for method, _ in calls], ['GET'])

    def test_apply_uses_only_original_read_binding_endpoint(self):
        result, error, calls = self.run_fixture()
        self.assertIsNone(error)
        self.assertTrue(result['completed'])
        self.assertEqual(calls, [('GET', 'https://original.example/v1/me'),
                                 ('POST', 'https://original.example/v1/service-read-bindings/batch')])
