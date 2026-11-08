"""Manual remote imports have explicit actions and sanitized failures."""
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from core.email import email_butler
from webui import runtime
from webui.routes import email_pool


class RemoteError(RuntimeError):
    pass


class ButlerImportRoutesTests(unittest.TestCase):
    def setUp(self):
        app = Flask('butler-import-routes')
        context = runtime.WebUIContext(app, logging.getLogger('butler-import-routes'))
        app.register_blueprint(email_pool.create_email_pool_blueprint(context))
        self.client = app.test_client()
        self.service = SimpleNamespace(RemoteError=RemoteError, **{
            name: Mock(return_value={'batch_id': 'fixture', 'status': 'completed'})
            for name in ('options', 'preview', 'create', 'get', 'retry')
        })
        self.module = patch.object(email_butler, 'manual_import', self.service, create=True)
        self.module.start()
        self.addCleanup(self.module.stop)

    def test_preview_and_options_do_not_start_import(self):
        options = self.client.get('/api/email-butler/import-options')
        body = {'provider': 'icloud_hme', 'identity_type': 'primary', 'count': 5}
        preview = self.client.post('/api/email-butler/import-preview', json=body)
        self.assertEqual(options.status_code, 200)
        self.assertEqual(preview.status_code, 200)
        self.service.options.assert_called_once_with()
        self.service.preview.assert_called_once_with(body)
        self.service.create.assert_not_called()
        self.service.retry.assert_not_called()

    def test_mutations_and_status_are_separate(self):
        body = {'request_id': 'stable', 'preview_token': 'snapshot'}
        response = self.client.post('/api/email-butler/imports', json=body)
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json['ok'])
        self.assertEqual(response.json['batch']['batch_id'], 'fixture')
        self.service.create.assert_called_once_with(body)
        self.assertEqual(self.client.get('/api/email-butler/imports/fixture').status_code, 200)
        self.service.get.assert_called_once_with('fixture')
        self.service.retry.assert_not_called()
        self.assertEqual(self.client.post('/api/email-butler/imports/fixture/retry', json={}).status_code, 202)
        self.service.retry.assert_called_once_with('fixture')

    def test_invalid_json_shapes_do_not_reach_service(self):
        for endpoint in ('import-preview', 'imports'):
            for body in ([], ['bad'], 'bad', None):
                with self.subTest(endpoint=endpoint, body=body):
                    response = self.client.post('/api/email-butler/' + endpoint, json=body)
                    self.assertEqual(response.status_code, 400)
        self.service.preview.assert_not_called()
        self.service.create.assert_not_called()

    def test_expected_error_status_and_unexpected_error_redaction(self):
        for error, status in ((ValueError('invalid_count: 数量无效'), 400),
                              (ValueError('secret-token-and-upstream-body'), 400),
                              (LookupError('batch_missing: 批次不存在'), 404),
                              (RemoteError('butler_unavailable: Butler 暂不可用'), 502),
                              (RuntimeError('secret-token-and-upstream-body'), 500)):
            with self.subTest(error=type(error).__name__):
                self.service.preview.side_effect = error
                response = self.client.post('/api/email-butler/import-preview', json={})
                self.assertEqual(response.status_code, status)
                self.assertFalse(response.json['ok'])
                self.assertNotIn('secret-token', response.get_data(as_text=True))

    def test_v2_errors_preserve_classification_and_do_not_expire_turb_login(self):
        from core.email.email_butler.v2 import ButlerV2Error

        for code, upstream, expected, retryable in (
            ('permission_denied', 403, 403, False),
            ('invalid_api_key', 401, 502, False),
            ('no_inventory', 409, 409, False),
            ('provider_unavailable', 502, 502, True),
            ('request_timeout', None, 502, True),
        ):
            with self.subTest(code=code):
                self.service.preview.side_effect = ButlerV2Error(code, '私有上游细节',
                    status_code=upstream, retryable=retryable, request_unknown=retryable)
                response = self.client.post('/api/email-butler/import-preview', json={})
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.json['error_code'], code)
                self.assertEqual(response.json['upstream_status'], upstream)
                self.assertEqual(response.json['retryable'], retryable)
                self.assertNotIn('私有上游细节', response.get_data(as_text=True))

    def test_v2_unsupported_filter_and_configuration_have_specific_messages(self):
        for code, expected in (
            ('butler_filter_unsupported', '来源和数量'),
            ('butler_configuration_required', '/v2'),
            ('butler_availability_invalid', '响应无效'),
        ):
            with self.subTest(code=code):
                self.service.preview.side_effect = ValueError(code)
                response = self.client.post('/api/email-butler/import-preview', json={})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error_code'], code)
                self.assertIn(expected, response.json['error'])
                self.assertNotIn('最终转发收件箱', response.json['error'])


if __name__ == '__main__':
    unittest.main()
