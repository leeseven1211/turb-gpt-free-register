"""原窗口的中继端口和真实线路归属跨进程恢复。"""
import json
import socket
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import browser_traffic, proxy_lease_store, record_store, roxybrowser_client
from core.protocol_traffic import correlation_context
from core.proxy_chain import ProxyChainRelay
from tests.support_pg import PostgresTestCase


class BrowserRelayRecoveryTests(PostgresTestCase):
    def setUp(self):
        self.route = 'http://private-user:private-password@127.0.0.1:19999'
        self.lease_id = 'original-lease'
        self.profile_id = 'retained-profile'
        record_store.insert_row(record_store.PROXY_LEASES, {
            'lease_id': self.lease_id, 'provider': 'test', 'endpoint': '127.0.0.1:19999',
            'proxy_url': self.route, 'state': 'released', 'operation_task_id': 501,
            'acquired_at': '2026-10-19T00:00:00',
        })

    def tearDown(self):
        for profile_id in list(roxybrowser_client._PROFILE_RELAYS):
            roxybrowser_client._close_profile_relay(profile_id)

    def bind(self):
        relay = ProxyChainRelay(self.route).start()
        with correlation_context(inherit=False, proxy_lease_id=self.lease_id):
            roxybrowser_client._remember_profile_relay(self.profile_id, relay)
        self.assertTrue(relay.binding_persisted)
        self.assertEqual(relay.origin_lease_id, self.lease_id)
        return relay

    def simulate_exit(self, relay):
        with roxybrowser_client._PROFILE_RELAYS_LOCK:
            roxybrowser_client._PROFILE_RELAYS.pop(self.profile_id)
        relay.close()

    def test_restart_rebuilds_same_port_and_original_route_without_browser_requests(self):
        original = self.bind()
        original_port = original.listen_port
        self.simulate_exit(original)
        opened = roxybrowser_client.RoxyOpenResult(self.profile_id, {})
        with patch.object(roxybrowser_client.RoxyBrowserClient, 'request') as request:
            roxybrowser_client.RoxyBrowserClient.attach_retained_profile_relay(opened)
        request.assert_not_called()
        self.assertTrue(opened.proxy_route_retained)
        self.assertEqual(opened.proxy_relay.listen_port, original_port)
        self.assertEqual(opened.proxy_relay.target.raw, self.route)
        self.assertEqual(opened.proxy_relay.origin_lease_id, self.lease_id)
        self.assertIs(roxybrowser_client.restore_profile_relay(self.profile_id), opened.proxy_relay)

    def test_startup_restores_keep_open_ports_even_without_temporary_profile_registry(self):
        original = self.bind()
        original_port = original.listen_port
        self.simulate_exit(original)
        with patch.object(roxybrowser_client, '_load_profile_registry_locked', return_value=[]), patch.object(
            roxybrowser_client._cfg, 'ROXY_KEEP_BROWSER_OPEN', True
        ), patch.object(roxybrowser_client.RoxyBrowserClient, '_find_active_profile_by_id', return_value={'openStatus': 0}), patch.object(
            roxybrowser_client.RoxyBrowserClient, 'request', return_value={
                'data': [{'dirId': self.profile_id, 'pid': 123, 'http': '127.0.0.1:9222'}],
            }
        ) as request:
            result = roxybrowser_client.cleanup_orphaned_profiles()
        self.assertEqual(result['restored_relays'], 1)
        self.assertEqual(roxybrowser_client._profile_relay(self.profile_id).listen_port, original_port)
        request.assert_called_once_with('GET', '/browser/connection_info', params={'dirIds': self.profile_id})

    def test_startup_unknown_connection_keeps_original_recovery_binding(self):
        original = self.bind()
        self.simulate_exit(original)
        with patch.object(roxybrowser_client.RoxyBrowserClient, 'request', return_value={'data': None}):
            self.assertEqual(roxybrowser_client.restore_kept_profile_relays(), (0, 1))
        self.assertEqual(len(proxy_lease_store.private_browser_relays(self.profile_id)), 1)

    def test_startup_confirmed_closed_connection_revokes_recovery_binding(self):
        original = self.bind()
        self.simulate_exit(original)
        with patch.object(roxybrowser_client.RoxyBrowserClient, 'request', return_value={'data': []}):
            self.assertEqual(roxybrowser_client.restore_kept_profile_relays(), (0, 0))
        self.assertEqual(proxy_lease_store.private_browser_relays(self.profile_id), [])

    def test_same_process_resume_uses_old_route_lease_and_current_task_identifiers(self):
        relay = self.bind()
        opened = SimpleNamespace(profile_id=self.profile_id, debugger_address='127.0.0.1:9222',
                                 proxy_relay=relay, proxy_route_retained=True)
        with correlation_context(inherit=False, proxy_lease_id='new-unused-lease', registration_job_id=22,
                                 operation_run_id=33), patch.object(browser_traffic, '_new_roxy_collector', return_value=Mock()), patch.object(
            browser_traffic, 'persist_summary'
        ) as persist:
            capture = browser_traffic.start_roxy_capture(opened, purpose='registration')
            capture.stop()
        self.assertEqual(persist.call_args.kwargs['proxy_lease_id'], self.lease_id)
        self.assertEqual(persist.call_args.kwargs['registration_job_id'], 22)
        self.assertEqual(persist.call_args.kwargs['operation_run_id'], 33)

    def test_confirmed_close_revokes_recovery_and_does_not_reacquire_lease(self):
        relay = self.bind()
        client = roxybrowser_client.RoxyBrowserClient()
        with patch.object(client, 'request'), patch.object(client, '_wait_profile_closed', return_value=False):
            self.assertFalse(client.close_profile(self.profile_id))
        self.assertEqual(len(proxy_lease_store.private_browser_relays(self.profile_id)), 1)
        with patch.object(client, 'request'), patch.object(client, '_wait_profile_closed', return_value=True):
            self.assertTrue(client.close_profile(self.profile_id))
        self.assertEqual(proxy_lease_store.private_browser_relays(self.profile_id), [])
        self.assertIsNone(roxybrowser_client._profile_relay(self.profile_id))
        self.assertIsNone(relay._listener)
        self.assertEqual(record_store.get_row_by(record_store.PROXY_LEASES, 'lease_id', self.lease_id)['state'], 'released')

    def test_conflicting_local_port_is_not_silently_replaced(self):
        original = self.bind()
        original_port = original.listen_port
        self.simulate_exit(original)
        with socket.socket() as other:
            other.bind(('127.0.0.1', original_port))
            other.listen(1)
            with self.assertRaises(RuntimeError) as raised:
                roxybrowser_client.restore_profile_relay(self.profile_id)
        self.assertNotIn('private-password', str(raised.exception))
        self.assertIsNone(roxybrowser_client._profile_relay(self.profile_id))
        self.assertEqual(proxy_lease_store.private_browser_relays(self.profile_id)[0]['browser_relay']['listen_port'], original_port)

    def test_private_recovery_binding_does_not_expose_credentials_or_change_lease_projection(self):
        relay = self.bind()
        row = proxy_lease_store.private_browser_relays(self.profile_id)[0]
        self.assertEqual(row['browser_relay'], {'profile_id': self.profile_id, 'listen_port': relay.listen_port,
                                               'blocked_hosts': [], 'open': True})
        self.assertNotIn('private-password', json.dumps(row['browser_relay']))
        self.assertEqual(row['proxy_url'], self.route)
        self.assertEqual(row['state'], 'released')

    def test_matching_task_can_persist_browser_relay_without_protocol_correlation(self):
        relay = ProxyChainRelay(self.route).start()
        with correlation_context(inherit=False), patch('core.task_run_log.current_context', return_value={
            'identifier_namespace': 'operation', 'task_id': 501,
        }):
            roxybrowser_client._remember_profile_relay(self.profile_id, relay)
        self.assertTrue(relay.binding_persisted)
        self.assertEqual(relay.origin_lease_id, self.lease_id)


class UnknownRetainedRouteTests(unittest.TestCase):
    def test_open_connection_requires_matching_profile_process_and_http_address(self):
        client = roxybrowser_client.RoxyBrowserClient()
        self.addCleanup(client.http.close)
        for row in [
            {'dirId': 'original', 'pid': 0, 'http': '127.0.0.1:9222'},
            {'dirId': 'original', 'pid': True, 'http': '127.0.0.1:9222'},
            {'dirId': 'original', 'pid': 123, 'http': ''},
            None,
        ]:
            with self.subTest(row=row), patch.object(client, 'request', return_value={'data': [row]}):
                with self.assertRaises(RuntimeError):
                    client.get_open_profile_connection('original')
        with patch.object(client, 'request', return_value={'data': [
            {'dirId': 'other', 'pid': 123, 'http': '127.0.0.1:9222'},
        ]}):
            self.assertIsNone(client.get_open_profile_connection('original'))

    def test_unknown_retained_route_never_claims_current_new_lease(self):
        opened = SimpleNamespace(profile_id='legacy-profile', debugger_address='127.0.0.1:9222',
                                 proxy_relay=None, proxy_route_retained=True)
        with correlation_context(inherit=False, proxy_lease_id='new-unused-lease'), patch.object(
            browser_traffic, '_new_roxy_collector', return_value=Mock()
        ), patch.object(browser_traffic, 'persist_summary') as persist:
            browser_traffic.start_roxy_capture(opened).stop()
        self.assertIsNone(persist.call_args.kwargs.get('proxy_lease_id'))


class RelayPersistenceFailureTests(unittest.TestCase):
    def test_keep_open_persistence_failure_fails_before_browser_open_and_reclaims_new_profile(self):
        relay = ProxyChainRelay('http://127.0.0.1:19999').start()
        client = roxybrowser_client.RoxyBrowserClient()
        try:
            with correlation_context(inherit=False, proxy_lease_id='original-lease'), patch.object(
                roxybrowser_client._cfg, 'ROXY_KEEP_BROWSER_OPEN', True
            ), patch('core.proxy_chain.open_browser_proxy', return_value=(relay.proxy_url, relay)), patch(
                'core.proxy_lease_store.bind_browser_relay', side_effect=RuntimeError('private-storage-detail')
            ), patch.object(client, 'create_profile', return_value='new-profile'), patch.object(
                client, 'delete_profile', return_value=True
            ) as delete, patch.object(client, 'request') as request, patch.object(
                roxybrowser_client, '_track_created_profile'
            ), patch.object(roxybrowser_client, '_untrack_created_profile') as untrack:
                with self.assertRaises(RuntimeError) as raised:
                    client.open_profile(profile_id='', proxy_url='http://127.0.0.1:19999')
            self.assertEqual(relay.recovery_state, 'failed')
            self.assertIsNone(relay._listener)
            self.assertNotIn('private-storage-detail', str(raised.exception))
            request.assert_not_called()
            delete.assert_called_once_with('new-profile')
            untrack.assert_called_once_with('new-profile')
            self.assertIsNone(roxybrowser_client._profile_relay('new-profile'))
        finally:
            relay.close()

    def test_nonretained_window_marks_unavailable_recovery_without_promising_restart_support(self):
        relay = ProxyChainRelay('http://127.0.0.1:19999').start()
        try:
            with correlation_context(inherit=False, proxy_lease_id='original-lease'), patch.object(
                roxybrowser_client._cfg, 'ROXY_KEEP_BROWSER_OPEN', False
            ), patch('core.proxy_lease_store.bind_browser_relay', return_value=None):
                roxybrowser_client._remember_profile_relay('short-lived-profile', relay)
            self.assertEqual(relay.recovery_state, 'unavailable')
            self.assertFalse(relay.binding_persisted)
        finally:
            roxybrowser_client._close_profile_relay('short-lived-profile')
