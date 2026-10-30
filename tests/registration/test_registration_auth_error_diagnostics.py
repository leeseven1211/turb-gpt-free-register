"""认证失败只保留固定错误枚举，普通流量采集不落原始正文。"""
import base64
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.browser.traffic import _SummaryOnlyCDPSession
from core.network.response_diagnostics import auth_error_from_body, auth_submission_endpoint, safe_auth_error
from core.auth.browser.submission_recovery import SubmissionDiagnostics, auth_session_missing, begin_auth_session
from core.registration.debug import _RoxyTargetCollector


class AuthErrorSanitizerTests(unittest.TestCase):
    def test_structured_error_preserves_only_known_enums(self):
        raw = {"error": {"code": "invalid_auth_step", "type": "invalid_request_error",
                         "message": "private@example.test code=123456", "token": "private-token"}}
        self.assertEqual(auth_error_from_body(json.dumps(raw)), {
            "code": "invalid_auth_step", "type": "invalid_request_error", "category": "auth_state",
        })

    def test_unknown_codes_and_arbitrary_categories_do_not_escape(self):
        result = safe_auth_error({"code": "private@example.test", "type": "123456",
                                  "category": "private-token", "message": "private-password"})
        self.assertEqual(result, {"code": "unknown", "type": "unknown", "category": "unknown"})
        self.assertEqual(safe_auth_error(None), {})
        self.assertEqual(safe_auth_error({"message": "private-password"}), {})

    def test_wrong_email_otp_code_preserves_exact_safe_rejection(self):
        raw = {"error": {"code": "wrong_email_otp_code", "type": "invalid_request_error",
                         "message": "private@example.test 123456", "category": "private-token"}}
        self.assertEqual(auth_error_from_body(json.dumps(raw)), {
            "code": "wrong_email_otp_code", "type": "invalid_request_error", "category": "otp_rejected",
        })
        for code in ("wrong_email_otp_code_extra", "WRONG_EMAIL_OTP_CODE"):
            with self.subTest(code=code):
                self.assertEqual(safe_auth_error({"code": code})["code"], "unknown")

    def test_bad_or_excessive_bodies_are_ignored(self):
        for body in ("<html>private</html>", "[1,2]", '{"error": {"code": "email_taken"}, "error": {}}',
                     '{"error":{"code":"email_taken"},"padding":"' + '中' * 25000 + '"}',
                     '{"error":{"code":"email_taken"},"padding":"' + 'x' * 70000 + '"}'):
            with self.subTest(size=len(body)):
                self.assertEqual(auth_error_from_body(body), {})

    def test_profile_endpoint_requires_original_auth_origin(self):
        self.assertEqual(auth_submission_endpoint('https://auth.openai.com/api/accounts/create_account'),
                         'profile_submit')
        for url in ('http://auth.openai.com/api/accounts/create_account',
                    'https://auth.openai.com.evil.test/api/accounts/create_account',
                    'https://private@auth.openai.com/api/accounts/create_account',
                    'https://auth.openai.com:8443/api/accounts/create_account',
                    'https://chatgpt.com/api/accounts/create_account'):
            with self.subTest(url=url):
                self.assertEqual(auth_submission_endpoint(url), '')

    def test_passwordless_code_request_is_not_a_password_submission(self):
        self.assertEqual(auth_submission_endpoint('https://auth.openai.com/api/accounts/passwordless/send-otp'),
                         'otp_resend')


class AuthErrorCollectorTests(unittest.TestCase):
    def worker(self, *, status=400, url='https://auth.openai.com/api/accounts/create_account',
               method='POST', mime='application/json', length=256, full=False):
        session = (SimpleNamespace(job_id=991, current_stage='email_otp', body_capture_enabled=True,
                                   record_network=Mock())
                   if full else _SummaryOnlyCDPSession('test-profile'))
        diagnostics = SubmissionDiagnostics()
        session.auth_diagnostic_observer = diagnostics.observe_network
        session.submission_observer = Mock()
        session.record_network = Mock(wraps=session.record_network)
        worker = _RoxyTargetCollector(SimpleNamespace(session=session), 'test-target', 'ws://test-only', 'page')
        worker._ws = Mock()
        worker._handle({'method': 'Network.requestWillBeSent', 'params': {
            'requestId': 'r1', 'timestamp': 1, 'type': 'Fetch',
            'request': {'url': url, 'method': method},
        }})
        worker._handle({'method': 'Network.responseReceived', 'params': {
            'requestId': 'r1', 'response': {'url': url, 'status': status, 'mimeType': mime,
                                         'headers': {'content-type': mime}},
        }})
        worker._handle({'method': 'Network.loadingFinished', 'params': {
            'requestId': 'r1', 'timestamp': 1.2, 'encodedDataLength': length,
        }})
        return session, diagnostics, worker

    def test_full_capture_retains_safe_auth_error_without_changing_raw_body(self):
        for options, code in (
            ({'status': 401, 'url': 'https://auth.openai.com/api/accounts/email-otp/validate'}, 'invalid_otp'),
            ({'status': 404, 'method': 'GET',
              'url': 'https://auth.openai.com/api/accounts/client_auth_session_dump'}, 'missing_session'),
        ):
            with self.subTest(code=code):
                session, _diagnostics, worker = self.worker(full=True, **options)
                commands = [json.loads(x.args[0]) for x in worker._ws.send.call_args_list]
                self.assertEqual([x['method'] for x in commands], ['Network.getResponseBody'])
                payload = json.dumps({'error': {'code': code, 'type': 'invalid_request_error',
                                                'message': 'private@example.test 123456'}})
                worker._handle({'id': commands[0]['id'], 'result': {'body': payload}})
                record = session.record_network.call_args.args[0]
                self.assertEqual(record['auth_error'], {
                    'code': code, 'type': 'invalid_request_error',
                    'category': 'otp_rejected' if code == 'invalid_otp' else 'auth_state',
                })
                self.assertEqual(record['response_body'], payload)
                self.assertEqual(record['status'], options['status'])
                self.assertEqual(worker._ws.send.call_count, 1)
                session.submission_observer.assert_not_called()

    def test_full_capture_does_not_derive_auth_error_from_other_responses(self):
        for options in ({'status': 200}, {'method': 'GET'}, {'length': 70000}, {'mime': 'text/html'},
                        {'url': 'https://auth.openai.com.evil.test/api/accounts/create_account'}):
            with self.subTest(options=options):
                session, _diagnostics, worker = self.worker(full=True, **options)
                command = json.loads(worker._ws.send.call_args.args[0])
                payload = '{"error":{"code":"invalid_otp"}}'
                worker._handle({'id': command['id'], 'result': {'body': payload}})
                record = session.record_network.call_args.args[0]
                self.assertNotIn('auth_error', record)
                self.assertEqual(record['response_body'], payload)

    def test_full_capture_late_body_cannot_label_redirected_request(self):
        session, _diagnostics, worker = self.worker(full=True, status=401)
        command = json.loads(worker._ws.send.call_args.args[0])
        worker._handle({'method': 'Network.requestWillBeSent', 'params': {
            'requestId': 'r1', 'timestamp': 2, 'type': 'Fetch',
            'redirectResponse': {'status': 302},
            'request': {'url': 'https://auth.openai.com/api/accounts/email-otp/validate', 'method': 'POST'},
        }})
        worker._handle({'method': 'Network.responseReceived', 'params': {
            'requestId': 'r1', 'response': {'status': 401, 'mimeType': 'application/json',
                                         'headers': {'content-type': 'application/json'}},
        }})
        worker._requests['r1']['encoded_data_length'] = 256
        worker._handle({'id': command['id'], 'result': {'body': '{"error":{"code":"invalid_otp"}}'}})
        self.assertNotIn('auth_error', session.record_network.call_args.args[0])

    def test_summary_reads_only_auth_error_then_discards_body(self):
        session, diagnostics, worker = self.worker()
        commands = [json.loads(x.args[0]) for x in worker._ws.send.call_args_list]
        self.assertEqual([x['method'] for x in commands], ['Network.getResponseBody'])
        payload = json.dumps({'error': {'code': 'email_taken', 'type': 'invalid_request_error',
                                        'message': 'private@example.test 123456'}})
        worker._handle({'id': commands[0]['id'], 'result': {
            'body': base64.b64encode(payload.encode()).decode(), 'base64Encoded': True,
        }})
        record = session.record_network.call_args.args[0]
        self.assertNotIn('response_body', record)
        self.assertNotIn('private@example.test', json.dumps(record))
        self.assertNotIn('123456', json.dumps(record))
        self.assertEqual(record['auth_error']['code'], 'email_taken')
        event = diagnostics.recent_network()[-1]
        self.assertEqual(event['path'], '/api/accounts/create_account')
        self.assertEqual(event['endpoint_kind'], 'profile_submit')
        self.assertEqual(event['auth_error']['category'], 'email_conflict')
        meta = session.submission_observer.call_args.args[0]
        self.assertEqual(meta['auth_error']['code'], 'email_taken')

    def test_successes_and_other_responses_do_not_read_bodies(self):
        cases = ({'status': 200}, {'url': 'https://auth.openai.com/api/auth/session'},
                 {'url': 'https://evil.test/api/accounts/create_account'}, {'method': 'GET'},
                 {'mime': 'text/html'}, {'length': 70000})
        for case in cases:
            with self.subTest(case=case):
                session, _diag, worker = self.worker(**case)
                worker._ws.send.assert_not_called()
                self.assertNotIn('response_body', session.record_network.call_args.args[0])

    def test_cdp_body_error_still_preserves_rejection_status(self):
        session, diagnostics, worker = self.worker()
        command = json.loads(worker._ws.send.call_args.args[0])
        worker._handle({'id': command['id'], 'error': {'message': 'No resource'}})
        self.assertEqual(session.record_network.call_args.args[0]['status'], 400)
        self.assertEqual(diagnostics.recent_network()[-1]['status'], 400)

    def test_missing_body_reply_is_bounded_and_late_reply_is_ignored(self):
        session, diagnostics, worker = self.worker()
        command = json.loads(worker._ws.send.call_args.args[0])
        with patch('core.registration.debug.time.monotonic', return_value=float('inf')):
            worker._expire_auth_error_reads()
        self.assertEqual(session.record_network.call_count, 1)
        self.assertEqual(diagnostics.recent_network()[-1]['status'], 400)
        worker._handle({'id': command['id'], 'result': {
            'body': '{"error":{"code":"email_taken"}}',
        }})
        self.assertEqual(session.record_network.call_count, 1)
        self.assertNotIn('auth_error', session.record_network.call_args.args[0])

    def test_target_close_after_completed_http_preserves_status_without_network_failure(self):
        session, diagnostics, worker = self.worker()
        worker._finish_open_requests()
        record = session.record_network.call_args.args[0]
        self.assertEqual(record['status'], 400)
        self.assertNotIn('failure', record)
        self.assertEqual(diagnostics.recent_network()[-1]['network_error'], '')

    def test_body_arriving_after_deadline_is_ignored_without_waiting_for_expiry_poll(self):
        session, diagnostics, worker = self.worker()
        command = json.loads(worker._ws.send.call_args.args[0])
        with patch('core.registration.debug.time.monotonic', return_value=float('inf')):
            worker._handle({'id': command['id'], 'result': {
                'body': '{"error":{"code":"email_taken"}}',
            }})
        self.assertEqual(session.record_network.call_count, 1)
        self.assertNotIn('auth_error', session.record_network.call_args.args[0])
        self.assertEqual(diagnostics.recent_network()[-1]['status'], 400)

    def test_old_body_cannot_attach_to_redirect_reusing_request_id(self):
        session, _diagnostics, worker = self.worker()
        command = json.loads(worker._ws.send.call_args.args[0])
        worker._handle({'method': 'Network.requestWillBeSent', 'params': {
            'requestId': 'r1', 'timestamp': 2, 'type': 'Document',
            'redirectResponse': {'status': 302},
            'request': {'url': 'https://auth.openai.com/about-you', 'method': 'GET'},
        }})
        worker._handle({'id': command['id'], 'result': {
            'body': '{"error":{"code":"email_taken"}}',
        }})
        self.assertIn('r1', worker._requests)
        self.assertNotIn('auth_error', worker._requests['r1'])

    def test_late_headers_preserve_sanitized_error_metadata(self):
        session, diagnostics, worker = self.worker()
        command = json.loads(worker._ws.send.call_args.args[0])
        worker._handle({'id': command['id'], 'result': {
            'body': '{"error":{"code":"email_taken"}}',
        }})
        worker._handle({'method': 'Network.responseReceivedExtraInfo', 'params': {
            'requestId': 'r1', 'statusCode': 400, 'headers': {'server': 'cloudflare'},
        }})
        self.assertEqual(diagnostics.recent_network()[-1]['auth_error']['code'], 'email_taken')
        self.assertEqual(session.record_network.call_count, 1)

    def test_metadata_sanitizes_error_again(self):
        diagnostics = SubmissionDiagnostics()
        diagnostics.observe_network({
            'url': 'https://auth.openai.com/api/accounts/create_account', 'method': 'POST',
            'request_id': 'r1', 'target_id': 't1', 'status': 400,
            'auth_error': {'code': 'private@example.test', 'type': 'private-password'},
        }, phase='complete')
        result = diagnostics.recent_network()[0]
        self.assertNotIn('private', json.dumps(result))
        self.assertEqual(result['auth_error']['code'], 'unknown')

    def test_current_session_missing_get_is_diagnostic_and_never_a_submission(self):
        session, diagnostics, worker = self.worker(
            status=404, method='GET', url='https://auth.openai.com/api/accounts/client_auth_session_dump',
        )
        command = json.loads(worker._ws.send.call_args.args[0])
        worker._handle({'id': command['id'], 'result': {
            'body': '{"error":{"code":"missing_session","message":"private-token"}}',
        }})
        driver = SimpleNamespace(_registration_submission_diagnostics=diagnostics)
        self.assertTrue(auth_session_missing(driver))
        session.submission_observer.assert_not_called()
        record = session.record_network.call_args.args[0]
        self.assertNotIn('response_body', record)
        self.assertNotIn('private-token', json.dumps(record))
        self.assertEqual(diagnostics.recent_network()[-1]['endpoint_kind'], 'auth_session_dump')
        begin_auth_session(driver)
        self.assertFalse(auth_session_missing(driver))

    def test_404_without_exact_missing_session_or_newer_healthy_response_cannot_restart(self):
        diagnostics = SubmissionDiagnostics()
        driver = SimpleNamespace(_registration_submission_diagnostics=diagnostics)
        base = {'url': 'https://auth.openai.com/api/accounts/client_auth_session_dump',
                'method': 'GET', 'request_id': 'old', 'target_id': 'target', 'status': 404}
        diagnostics.observe_network(base, phase='request')
        diagnostics.observe_network(base, phase='complete')
        self.assertFalse(auth_session_missing(driver))
        diagnostics.observe_network({**base, 'auth_error': {'code': 'missing_session'}}, phase='complete')
        self.assertTrue(auth_session_missing(driver))
        healthy = {**base, 'request_id': 'new', 'status': 200}
        diagnostics.observe_network(healthy, phase='request')
        diagnostics.observe_network(healthy, phase='complete')
        self.assertFalse(auth_session_missing(driver))

    def test_late_or_orphan_old_session_response_cannot_contaminate_new_session(self):
        diagnostics = SubmissionDiagnostics()
        driver = SimpleNamespace(_registration_submission_diagnostics=diagnostics)
        old = {'url': 'https://auth.openai.com/api/accounts/client_auth_session_dump',
               'method': 'GET', 'request_id': 'old', 'target_id': 'target'}
        diagnostics.observe_network(old, phase='request')
        for number in range(45):
            diagnostics.observe_network({**old, 'url': 'https://auth.openai.com/api/accounts/authorize',
                                         'request_id': str(number)}, phase='request')
        begin_auth_session(driver)
        rejection = {'status': 404, 'auth_error': {'code': 'missing_session'}}
        diagnostics.observe_network({**old, **rejection}, phase='complete')
        self.assertFalse(auth_session_missing(driver))
        diagnostics.observe_network({**old, **rejection, 'request_id': 'unobserved'}, phase='complete')
        self.assertFalse(auth_session_missing(driver))
        fresh = {**old, 'request_id': 'fresh'}
        diagnostics.observe_network(fresh, phase='request')
        diagnostics.observe_network({**fresh, **rejection}, phase='complete')
        self.assertTrue(auth_session_missing(driver))

    def test_session_error_body_is_not_read_for_post_or_foreign_origin(self):
        for options in ({'method': 'POST'}, {'status': 200},
                        {'url': 'https://auth.openai.com.evil.test/api/accounts/client_auth_session_dump'}):
            with self.subTest(options=options):
                kwargs = {'status': 404, 'method': 'GET',
                          'url': 'https://auth.openai.com/api/accounts/client_auth_session_dump', **options}
                session, _diagnostics, worker = self.worker(**kwargs)
                worker._ws.send.assert_not_called()
                session.submission_observer.assert_not_called()
