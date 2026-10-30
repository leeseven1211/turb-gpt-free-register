# -*- coding: utf-8 -*-
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.browser import traffic as browser_traffic
from core.browser.roxy import client as roxybrowser_client
from core.browser.traffic_diagnostics import BrowserTrafficDiagnostics, sanitize_diagnostics
from core.proxy.chain import open_browser_proxy
from core.registration.debug import _RoxyTargetCollector
from core.browser.roxy.client import RoxyBrowserClient, RoxyOpenResult


class BrowserTransportPortTests(unittest.TestCase):
    def tearDown(self):
        for profile in list(roxybrowser_client._PROFILE_RELAYS):
            roxybrowser_client._close_profile_relay(profile)

    def test_selected_route_is_only_wrapped_without_acquiring_another_lease(self):
        with patch('core.proxy.chain.ProxyChainRelay') as factory, patch('config.proxy.pick_proxy', create=True) as pick:
            local = factory.return_value.start.return_value
            local.proxy_url = 'http://127.0.0.1:1234'
            result, relay = open_browser_proxy('socks5h://private:password@route.example:1080')
        self.assertEqual(result, local.proxy_url)
        self.assertIs(relay, local)
        self.assertEqual(factory.call_args.args, ('socks5h://private:password@route.example:1080',))
        pick.assert_not_called()

    def test_unsupported_proxy_protocol_preserves_original_route(self):
        with patch('core.proxy.chain.ProxyChainRelay') as factory:
            self.assertEqual(open_browser_proxy('https://route.example:443'), ('https://route.example:443', None))
        factory.assert_not_called()

    def test_profile_create_failure_closes_unused_local_port(self):
        relay = Mock()
        client = RoxyBrowserClient()
        with patch('core.proxy.chain.open_browser_proxy', return_value=('http://127.0.0.1:1234', relay)), patch.object(
            client, 'create_profile', side_effect=RuntimeError('创建失败')
        ):
            with self.assertRaises(RuntimeError):
                client.open_profile(profile_id='', proxy_url='http://route.example:8080')
        relay.close.assert_called_once()

    def test_keep_open_and_unconfirmed_close_preserve_relay_until_confirmed(self):
        relay = Mock()
        opened = RoxyOpenResult('port-profile', {}, proxy_relay=relay)
        client = RoxyBrowserClient()
        roxybrowser_client._remember_profile_relay(opened.profile_id, relay)
        with patch.object(roxybrowser_client._cfg, 'ROXY_KEEP_BROWSER_OPEN', True), patch.object(
            browser_traffic, 'finish_roxy_capture'
        ):
            client.cleanup_profile(opened)
        relay.close.assert_not_called()
        with patch.object(client, 'request'), patch.object(client, '_wait_profile_closed', return_value=False):
            self.assertFalse(client.close_profile(opened.profile_id))
        relay.close.assert_not_called()
        with patch.object(client, 'request'), patch.object(client, '_wait_profile_closed', return_value=True):
            self.assertTrue(client.close_profile(opened.profile_id))
        relay.close.assert_called_once()

    def test_proxy_update_failure_releases_only_new_relay(self):
        relay = Mock()
        old_relay = Mock()
        client = RoxyBrowserClient()
        roxybrowser_client._remember_profile_relay('bound-profile', old_relay)
        with patch.object(client, '_find_active_profile_by_id', return_value={'openStatus': 0}), patch(
            'core.proxy.chain.open_browser_proxy', return_value=('http://127.0.0.1:1234', relay)
        ), patch.object(client, 'close_profile', return_value=True), patch.object(
            client, 'request', side_effect=RuntimeError('更新失败')
        ):
            with self.assertRaises(RuntimeError):
                client.open_profile_for_account(profile_id='bound-profile', proxy_url='http://route.example:8080')
        relay.close.assert_called_once()
        old_relay.close.assert_not_called()

    def test_transport_is_separate_and_resumed_window_does_not_recount_prior_bytes(self):
        snapshots = [
            {'available': True, 'upload_bytes': 20, 'download_bytes': 80,
             'destinations': [{'host': 'chatgpt.com', 'port': 443, 'upload_bytes': 20, 'download_bytes': 80, 'connection_count': 1}]},
            {'available': True, 'upload_bytes': 30, 'download_bytes': 130,
             'destinations': [{'host': 'chatgpt.com', 'port': 443, 'upload_bytes': 30, 'download_bytes': 130, 'connection_count': 2}]},
            {'available': True, 'upload_bytes': 40, 'download_bytes': 150,
             'destinations': [{'host': 'chatgpt.com', 'port': 443, 'upload_bytes': 40, 'download_bytes': 150, 'connection_count': 3}]},
        ]
        relay = SimpleNamespace(traffic_snapshot=Mock(side_effect=snapshots), origin_lease_id='lease-selected')
        opened = SimpleNamespace(profile_id='profile', debugger_address='127.0.0.1:9222', proxy_relay=relay)
        with patch.object(browser_traffic, '_new_roxy_collector', return_value=Mock()), patch.object(
            browser_traffic, 'persist_summary'
        ) as persist:
            from core.network.protocol_traffic import correlation_context
            with correlation_context(proxy_lease_id='lease-selected', registration_job_id=12):
                first = browser_traffic.start_roxy_capture(opened, purpose='registration')
            first.record_network({'url': 'https://chatgpt.com/', 'encoded_data_length': 7})
            first.stop()
            first.stop()
            opened.traffic_capture = None
            second = browser_traffic.start_roxy_capture(opened)
            second.stop()
        first_saved = persist.call_args_list[0].kwargs
        second_saved = persist.call_args_list[1].kwargs
        self.assertEqual(first_saved['summary']['total_bytes'], 7)
        self.assertEqual(first_saved['summary']['proxy_transport']['total_bytes'], 100)
        self.assertEqual(first_saved['proxy_lease_id'], 'lease-selected')
        self.assertEqual(first_saved['registration_job_id'], 12)
        self.assertEqual(second_saved['summary']['proxy_transport']['total_bytes'], 30)
        self.assertEqual(second_saved['summary']['proxy_transport']['destinations'][0]['connection_count'], 1)
        self.assertEqual(persist.call_count, 2)

    def test_resource_and_coverage_metadata_are_bounded_and_redacted(self):
        with patch.multiple('config.browser', BROWSER_TRAFFIC_DETAIL_LOG=True, BROWSER_TRAFFIC_DETAIL_MAX_ENTRIES=1,
                            BROWSER_JS_COVERAGE_LOG=True, BROWSER_JS_COVERAGE_MAX_ENTRIES=1):
            diagnostics = BrowserTrafficDiagnostics()
        diagnostics.record_resource({'url': 'https://user:password@cdn.example/a.js?token=private'}, 0, 5)
        diagnostics.record_resource({'url': 'https://cdn.example/b.js?otp=123456'}, 0, 10)
        diagnostics.record_coverage({'result': [{'url': 'https://cdn.example/app.js?session=secret', 'functions': [
            {'functionName': 'render', 'ranges': [{'startOffset': 0, 'endOffset': 20, 'count': 3}]},
            {'functionName': 'unused', 'ranges': [{'startOffset': 20, 'endOffset': 40, 'count': 0}]},
        ]}]})
        saved = sanitize_diagnostics(diagnostics.snapshot())
        self.assertEqual(len(saved['resource_details']), 1)
        self.assertEqual(saved['resource_details'][0]['download_bytes'], 10)
        self.assertEqual(saved['js_coverage']['scripts'][0]['executed_function_count'], 1)
        serialized = json.dumps(saved)
        for private in ('password', 'token=', 'private', '123456', 'secret', 'ranges', 'render'):
            self.assertNotIn(private, serialized)

    def test_coverage_uses_existing_collector_response_without_response_bodies(self):
        with patch('config.browser.BROWSER_JS_COVERAGE_LOG', True):
            session = browser_traffic._SummaryOnlyCDPSession('profile')
        collector = _RoxyTargetCollector(SimpleNamespace(session=session), 'target', '', 'page')
        collector._pending[1] = {'traffic_coverage': True}
        collector._handle({'id': 1, 'result': {'result': [{'url': 'https://cdn.example/app.js', 'functions': []}]}})
        self.assertTrue(collector._coverage_ready.is_set())
        self.assertFalse(session.body_capture_enabled)
        self.assertEqual(session.diagnostics.snapshot()['js_coverage']['collected_target_count'], 1)
        collector._pending[2] = {'traffic_coverage_start': True}
        collector._handle({'id': 2, 'error': {'message': 'Profiler 不支持'}})
        self.assertTrue(collector._coverage_failed)
        self.assertEqual(session.diagnostics.snapshot()['js_coverage']['unsupported_target_count'], 1)

    def test_diagnostics_default_off_keeps_summary_free_of_urls(self):
        with patch.multiple('config.browser', BROWSER_TRAFFIC_DETAIL_LOG=False, BROWSER_JS_COVERAGE_LOG=False):
            session = browser_traffic._SummaryOnlyCDPSession('profile')
        session.record_network({'url': 'https://private.example/?token=secret', 'encoded_data_length': 3})
        self.assertNotIn('resource_details', session.summary())
        self.assertNotIn('js_coverage', session.summary())
        self.assertNotIn('private.example', json.dumps(session.summary()))


from tests.support_pg import PostgresTestCase


class BrowserTransportStorageTests(PostgresTestCase):
    def test_new_metadata_is_persisted_without_changing_primary_byte_semantics(self):
        from core.storage import records as record_store
        browser_traffic.persist_summary(summary_key='transport-storage', summary={
            'source': 'roxy_cdp', 'upload_bytes': 3, 'download_bytes': 7,
            'proxy_transport': {'available': True, 'upload_bytes': 30, 'download_bytes': 70,
                                'password': 'private-secret', 'destinations': [
                                    {'host': 'chatgpt.com', 'port': 443, 'upload_bytes': 30, 'download_bytes': 70,
                                     'connection_count': 2, 'request_body': 'private-body'},
                                    {'host': 'user:secret@example.com', 'port': 443},
                                ]},
            'resource_details': [{'url': 'https://user:password@cdn.example/app.js?token=private-secret',
                                  'total_bytes': 8, 'request_headers': {'Authorization': 'private-header'}}],
            'js_coverage': {'enabled': True, 'scripts': [{'url': 'https://cdn.example/app.js?session=private-secret',
                              'function_count': 4, 'executed_function_count': 1, 'source': 'private-source'}]},
        }, proxy_lease_id='lease-test', registration_job_id=91)
        row = record_store.get_row_by(record_store.BROWSER_TRAFFIC, 'summary_key', 'transport-storage')
        self.assertEqual(row['total_bytes'], 10)
        self.assertEqual(row['proxy_transport']['total_bytes'], 100)
        self.assertEqual(len(row['proxy_transport']['destinations']), 1)
        self.assertEqual(row['proxy_lease_id'], 'lease-test')
        self.assertEqual(browser_traffic.aggregate_summaries([row])['total_bytes'], 10)
        encoded = json.dumps(row)
        for private in ('password', 'private-', 'token=', 'session=', 'Authorization', 'request_body'):
            self.assertNotIn(private, encoded)


class BrowserTransportConfigTests(unittest.TestCase):
    def test_new_configuration_accepts_domain_lists_and_bounds_diagnostic_capacity(self):
        from config.schema import ConfigValidationError, validate_value
        self.assertEqual(validate_value('BROWSER_DATA_SAVER_BLOCKED_PROXY_HOSTS', '*.GVT1.com.\ndl.google.com'),
                         ['gvt1.com', 'dl.google.com'])
        self.assertEqual(validate_value('BROWSER_DATA_SAVER_BLOCKED_PROXY_HOSTS', []), [])
        for value in ('https://gvt1.com', 'user:pass@gvt1.com:443', 'gvt1.com/path'):
            with self.assertRaises(ConfigValidationError):
                validate_value('BROWSER_DATA_SAVER_BLOCKED_PROXY_HOSTS', [value])
        with self.assertRaises(ConfigValidationError):
            validate_value('BROWSER_JS_COVERAGE_MAX_ENTRIES', 10001)

    def test_real_local_http_connect_listener_preserves_route_and_counts_tls_payload(self):
        import socket
        import threading
        from core.proxy.chain import ProxyChainRelay, _read_exact
        supplier = socket.socket()
        supplier.bind(('127.0.0.1', 0))
        supplier.listen(1)
        supplier.settimeout(3)
        received = []
        def serve():
            connection, _ = supplier.accept()
            with connection:
                connection.settimeout(3)
                header = b''
                while b'\r\n\r\n' not in header:
                    header += connection.recv(4096)
                received.append(header)
                connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                received.append(_read_exact(connection, 5))
                connection.sendall(b'reply')
        thread = threading.Thread(target=serve)
        thread.start()
        relay = ProxyChainRelay('http://127.0.0.1:' + str(supplier.getsockname()[1])).start()
        try:
            with socket.create_connection(('127.0.0.1', int(relay.proxy_url.rsplit(':', 1)[1])), timeout=3) as browser:
                browser.sendall(b'CONNECT chatgpt.com:443 HTTP/1.1\r\n\r\n')
                header = b''
                while b'\r\n\r\n' not in header:
                    header += browser.recv(4096)
                browser.sendall(b'hello')
                self.assertEqual(_read_exact(browser, 5), b'reply')
            thread.join(timeout=3)
            self.assertIn(b'CONNECT chatgpt.com:443 ', received[0])
            self.assertEqual(received[1], b'hello')
            self.assertEqual(relay.traffic_snapshot()['total_bytes'], 10)
            self.assertEqual(relay.traffic_snapshot()['destinations'][0]['host'], 'chatgpt.com')
        finally:
            relay.close()
            supplier.close()
            thread.join(timeout=3)
