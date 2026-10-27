"""Manual remote imports have explicit actions and sanitized failures."""
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

import core
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
        self.module = patch.object(core, 'butler_manual_import', self.service, create=True)
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


if __name__ == '__main__':
    unittest.main()
