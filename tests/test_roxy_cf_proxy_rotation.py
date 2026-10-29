"""本地 Roxy 仅凭当前认证入口挑战换线，关闭后才交回服务层。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.registration import roxy
from core.registration.email_otp import _EmailSubmissionUnknown
from tests import test_registration_resume_session as resume
from tests.test_roxy_native_signin_diagnostics import event


FORM = 'https://chatgpt.com/auth/login'
FACTS = {'job_id': 31, 'attempt_id': 41, 'run_id': 71, 'execution_id': 'cf-current-run'}


class EntryChallengeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.driver = SimpleNamespace(current_url=FORM, current_window_handle='CDwindow-current-target')
        self.diagnostic = roxy._NativeSigninFailureDiagnostics(Mock(), include_form_entry=True)
        self.diagnostic.begin_navigation(self.driver)
        self.observe(event('document', url=FORM, method='GET', started=10.0, resource_type='Document'))

    def observe(self, value, phase='request'):
        self.diagnostic.observe_network(value, phase=phase)

    def challenge(self, request='signin', *, endpoint='nextauth_signin', **kwargs):
        extra = {'url': 'https://chatgpt.com/api/auth/csrf', 'method': 'GET'} if endpoint == 'nextauth_csrf' else {}
        self.observe(event(request, **extra, **kwargs))
        self.observe(event(request, status=403, headers={'cf-mitigated': 'challenge'}, **extra, **kwargs), 'response')

    def test_form_signin_and_csrf_require_explicit_challenge(self):
        for endpoint in ('nextauth_signin', 'nextauth_csrf'):
            with self.subTest(endpoint=endpoint):
                self.setUp()
                self.challenge(endpoint=endpoint)
                result = self.diagnostic.failure_diagnostic(self.driver)
                self.assertEqual(result['cause_code'], 'auth_cloudflare_challenge')
                self.assertEqual(result['cause_diagnostics']['auth_endpoint'], endpoint)

    def test_later_success_pending_request_other_tab_and_rum_cannot_supply_challenge(self):
        for mode in ('success', 'pending', 'other_tab', 'rum', 'ordinary_403', 'auth_progress'):
            with self.subTest(mode=mode):
                self.setUp()
                if mode in {'success', 'pending', 'auth_progress'}:
                    self.challenge()
                    if mode == 'auth_progress':
                        self.observe(event('auth-document', url='https://auth.openai.com/email-verification',
                                           method='GET', started=12.0, resource_type='Document'))
                    else:
                        self.observe(event('new', started=12.0))
                        if mode == 'success':
                            self.observe(event('new', started=12.0, status=200), 'response')
                elif mode == 'other_tab':
                    self.challenge(target='other-target')
                elif mode == 'rum':
                    self.challenge(url='https://auth.openai.com/awe/api/v2/rum')
                else:
                    self.observe(event('signin'))
                    self.observe(event('signin', status=403, headers={'server': 'cloudflare'}), 'response')
                self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})

    def test_current_tab_must_still_match_the_challenged_navigation(self):
        self.challenge()
        self.driver.current_window_handle = 'CDwindow-other-target'
        self.assertEqual(self.diagnostic.failure_diagnostic(self.driver), {})


class CfRotationContextTests(unittest.TestCase):
    def test_ephemeral_context_is_bound_to_current_registration_run_and_profile(self):
        options = {'_roxy_cf_proxy_rotation': {**FACTS, 'retry_available': True, 'reopen_profile_id': 'bound'}}
        for action in ('registration', 'registration_resume'):
            with self.subTest(action=action), patch('core.storage.registration.get_run', return_value={
                **FACTS, 'id': 71, 'action_type': action, 'status': 'running',
            }):
                self.assertEqual(roxy._validated_roxy_cf_proxy_rotation(options, FACTS, 'bound'),
                                 options['_roxy_cf_proxy_rotation'])
        with patch('core.storage.registration.get_run', return_value={
            **FACTS, 'id': 71, 'action_type': 'registration', 'status': 'running',
        }):
            with self.assertRaisesRegex(RuntimeError, 'request_unknown'):
                roxy._validated_roxy_cf_proxy_rotation(options, {**FACTS, 'run_id': 72}, 'bound')

    def test_deleted_temporary_context_cannot_reopen_a_bound_profile(self):
        options = {'_roxy_cf_proxy_rotation': {
            **FACTS, 'previous_cf_temporary_profile_deleted': True, 'reopen_profile_id': '',
        }}
        with patch('core.storage.registration.get_run', return_value={
            **FACTS, 'action_type': 'registration_resume', 'status': 'running',
        }), self.assertRaisesRegex(RuntimeError, 'request_unknown'):
            roxy._validated_roxy_cf_proxy_rotation(options, FACTS, 'bound')


class CfDeletedProfileConfirmationTests(unittest.TestCase):
    def test_recycle_bin_must_explicitly_contain_the_exact_deleted_profile(self):
        for data, expected in (([{'dirId': 'temporary'}], True),
                               ({'rows': [{'dirId': 'temporary'}]}, True),
                               ([], False), ({'unexpected': []}, False),
                               ([{'dirId': 'another'}], False)):
            with self.subTest(data=data):
                client = Mock()
                client.request.return_value = {'data': data}
                self.assertIs(roxy._confirmed_cf_profile_deleted(client, 'temporary'), expected)


class CfRotationFlowTests(unittest.TestCase):
    def run_flow(self, *, created=False, closed=True, deleted=True, options=True, helpers=None,
                 previous_deleted=False, finish_advance=False, callback_handoff=False):
        flow = resume.ResumeSessionFlowTests()
        with flow.run_context() as (driver, mocks):
            mocks['context'].return_value = dict(FACTS)
            mocks['run'].return_value = {**FACTS, 'id': 71, 'action_type': 'registration_resume', 'status': 'running'}
            mocks['opened'].return_value.created_by_run = created
            mocks['opened'].return_value.account_bound = not created
            mocks['opened'].return_value.proxy_route_retained = False
            driver.current_window_handle = 'CDwindow-current-target'
            driver.execute_async_script.return_value = {'ok': True, 'status': 200, 'json_valid': True, 'data': {}}
            capture = Mock()
            mocks['opened'].return_value.traffic_capture = capture
            client = mocks['client'].return_value
            client.close_profile.return_value = closed
            client.get_open_profile_connection.return_value = None if closed else object()
            client.delete_profile.return_value = deleted
            client._find_active_profile_by_id.return_value = None if deleted else {'dirId': 'unit-profile'}
            client.request.return_value = {'data': [{'dirId': 'unit-profile'}] if deleted else []}

            def navigate(_driver, url, **kwargs):
                driver.current_url = url
                observer = capture.set_auth_diagnostic_observer.call_args.args[0]
                observer(event('document', url=url, method='GET', started=10.0,
                               resource_type='Document'), phase='request')
                observer(event('signin'), phase='request')
                observer(event('signin', status=403, headers={'cf-mitigated': 'challenge'}), phase='response')

            mocks['navigate'].side_effect = navigate
            def submit(*args, **kwargs):
                if callback_handoff:
                    kwargs['on_before_recovery']()
                raise _EmailSubmissionUnknown('email_submit_unconfirmed')
            mocks['_submit_email_and_wait_next'].side_effect = submit
            config = {'_roxy_cf_proxy_rotation': {
                **FACTS, 'retry_available': True, 'reopen_profile_id': '',
                'previous_cf_temporary_profile_deleted': previous_deleted,
            }} if options else {}
            if previous_deleted:
                mocks['attempt_default'].side_effect = RuntimeError('原任务尚未结束，不得恢复自身')
            def finish(_opened):
                if finish_advance:
                    observer = capture.set_auth_diagnostic_observer.call_args.args[0]
                    observer(event('later-success', started=12.0), phase='request')
                    observer(event('later-success', started=12.0, status=200), phase='response')
            with patch('core.browser_traffic.finish_roxy_capture', side_effect=finish), \
                    patch('core.roxybrowser_client._untrack_created_profile') as untrack:
                result = flow.run_registration(registration_options=config, _browser_helpers=helpers,
                                               **({'profile_id': None} if previous_deleted else {}))
            mocks['untrack'] = untrack
        return result, mocks, client

    def test_bound_profile_is_closed_then_reopened_and_original_unknown_semantics_remain(self):
        result, mocks, client = self.run_flow(callback_handoff=True)
        self.assertTrue(result['cf_proxy_rotation_ready'])
        self.assertEqual(result['cf_proxy_rotation_profile_id'], 'unit-profile')
        self.assertEqual(result['cf_proxy_rotation_context'], FACTS)
        self.assertTrue(result['request_unknown'])
        self.assertEqual(result['error_code'], 'request_unknown')
        self.assertEqual(result['cause_code'], 'auth_cloudflare_challenge')
        client.close_profile.assert_called_once_with('unit-profile')
        client.delete_profile.assert_not_called()
        mocks['pause'].assert_not_called()
        mocks['release'].assert_not_called()

    def test_no_current_context_keeps_the_email_helper_without_cf_handoff(self):
        _result, mocks, _client = self.run_flow(options=False)
        self.assertNotIn('on_before_recovery', mocks['_submit_email_and_wait_next'].call_args.kwargs)

    def test_only_confirmed_close_and_delete_of_unbound_temporary_profile_allows_new_window(self):
        result, mocks, client = self.run_flow(created=True)
        self.assertTrue(result['cf_proxy_rotation_ready'])
        self.assertEqual(result['cf_proxy_rotation_profile_id'], '')
        client.delete_profile.assert_called_once_with('unit-profile')
        mocks['untrack'].assert_called_once_with('unit-profile')
        mocks['pause'].assert_not_called()

    def test_deleted_temporary_profile_does_not_recover_the_current_running_job(self):
        result, mocks, _client = self.run_flow(created=True, previous_deleted=True)
        self.assertTrue(result['cf_proxy_rotation_ready'])
        mocks['take_default'].assert_not_called()
        mocks['attempt_default'].assert_not_called()
        mocks['bound_default'].assert_not_called()

    def test_capture_drain_must_not_close_a_newer_successful_auth_request(self):
        result, mocks, client = self.run_flow(finish_advance=True)
        self.assertFalse(result['cf_proxy_rotation_ready'])
        self.assertNotEqual(result.get('cause_code'), 'auth_cloudflare_challenge')
        self.assertNotIn('auth_cloudflare_challenge', result['error'])
        client.close_profile.assert_not_called()
        mocks['pause'].assert_called_once()

    def test_failed_close_delete_or_missing_current_context_never_permits_rotation(self):
        for kwargs in ({'closed': False}, {'created': True, 'deleted': False}, {'options': False}):
            with self.subTest(kwargs=kwargs):
                result, mocks, _client = self.run_flow(**kwargs)
                self.assertFalse(result.get('cf_proxy_rotation_ready', False))
                mocks['pause'].assert_called_once()


if __name__ == '__main__':
    unittest.main()
