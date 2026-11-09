"""邮箱池删除入口统一展示成功保护，并交由存储层判断删除资格。"""
import logging
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from flask import Flask

from webui import runtime
from webui.routes import email_pool


class EmailPoolDeleteRoutesTests(unittest.TestCase):
    SOURCES = {
        'outlook': 'db.delete_outlook',
        'generic_api': 'db.delete_generic_api_email',
        'cloudflare_domain': 'db.delete_domain_email',
        'icloud_hide': 'db.delete_icloud_hide_email',
        'email_butler': 'local_email_imports.delete_butler_email',
    }

    def setUp(self):
        app = Flask('email-pool-delete-routes')
        context = runtime.WebUIContext(app, logging.getLogger('email-pool-delete-routes'))
        app.register_blueprint(email_pool.create_email_pool_blueprint(context))
        self.client = app.test_client()
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.lookup = stack.enter_context(patch.object(email_pool, '_pool_row_for_source',
            side_effect=lambda email, source: {'email': email, 'status': 'request_unknown'}))
        self.protected = stack.enter_context(patch.object(email_pool.local_email_imports,
            'pool_mutation_protected', return_value=False))
        self.sync = stack.enter_context(patch.object(email_pool, '_email_sync_status',
            return_value={'state': 'not_required'}))
        self.deleters = {source: stack.enter_context(patch('webui.routes.email_pool.' + target,
            return_value=True)) for source, target in self.SOURCES.items()}

    def test_confirmed_success_has_same_single_and_bulk_reason_for_every_source(self):
        self.protected.return_value = True
        for source in self.SOURCES:
            item = {'source': source, 'email': source + '@example.test'}
            with self.subTest(source=source):
                single = self.client.post('/api/outlook/delete', json=item)
                self.assertEqual(single.status_code, 200)
                self.assertFalse(single.json['deleted'])
                self.assertEqual(single.json['reason'], '邮箱已确认注册成功，不能删除')
                self.assertEqual(single.json['reason_code'], 'registration_confirmed')
                bulk = self.client.post('/api/outlook/delete-bulk', json={'items': [item]})
                self.assertEqual(bulk.status_code, 200)
                self.assertEqual(bulk.json['deleted_count'], 0)
                self.assertEqual(bulk.json['skipped'][0]['source'], source)
                self.assertEqual(bulk.json['skipped'][0]['reason'], single.json['reason'])
                self.assertEqual(bulk.json['skipped'][0]['reason_code'], 'registration_confirmed')
        for delete in self.deleters.values():
            delete.assert_not_called()
        self.sync.assert_not_called()

    def test_unconfirmed_history_reaches_source_deleter_for_single_and_bulk(self):
        for source, delete in self.deleters.items():
            item = {'source': source, 'email': source + '@example.test'}
            with self.subTest(source=source):
                single = self.client.post('/api/outlook/delete', json=item)
                self.assertEqual(single.status_code, 200)
                self.assertTrue(single.json['deleted'])
                bulk = self.client.post('/api/outlook/delete-bulk', json={'items': [item]})
                self.assertEqual(bulk.status_code, 200)
                self.assertEqual(bulk.json['deleted_count'], 1)
                self.assertEqual(bulk.json['skipped'], [])
                self.assertEqual(delete.call_count, 2)
                delete.assert_called_with(item['email'])

    def test_bulk_keeps_success_and_other_skip_reasons(self):
        self.protected.side_effect = lambda row: row['email'].startswith('success')
        self.deleters['generic_api'].return_value = False
        response = self.client.post('/api/outlook/delete-bulk', json={'items': [
            {'source': 'outlook', 'email': 'success@example.test'},
            {'source': 'generic_api', 'email': 'missing@example.test'},
            {'source': 'email_butler', 'email': 'unknown@example.test'},
        ]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['deleted_count'], 1)
        self.assertEqual([item['reason'] for item in response.json['skipped']],
            ['邮箱已确认注册成功，不能删除', '邮箱不存在'])

    def test_late_confirmed_success_keeps_same_single_and_bulk_reason(self):
        self.deleters['email_butler'].return_value = False
        item = {'source': 'email_butler', 'email': 'late-success@example.test'}
        self.protected.side_effect = [False, True, False, True]
        single = self.client.post('/api/outlook/delete', json=item)
        bulk = self.client.post('/api/outlook/delete-bulk', json={'items': [item]})
        self.assertFalse(single.json['deleted'])
        self.assertEqual(single.json['reason'], '邮箱已确认注册成功，不能删除')
        self.assertEqual(single.json['reason_code'], 'registration_confirmed')
        self.assertEqual(bulk.json['deleted_count'], 0)
        self.assertEqual(bulk.json['skipped'], [{**item,
            'reason': single.json['reason'], 'reason_code': 'registration_confirmed'}])
        self.sync.assert_not_called()

    def test_retained_lease_message_and_count_survive_delete_response(self):
        receipt = {
            'state': 'local_only', 'kind': 'return', 'permanent': False,
            'error_code': 'registration_result_unverified', 'lease_retained': True,
            'message': '本地已移除，注册结果未确认，已保留原租约',
        }
        self.sync.return_value = receipt
        item = {'source': 'email_butler', 'email': 'unknown@example.test'}
        single = self.client.post('/api/outlook/delete', json=item)
        self.assertTrue(single.json['deleted'])
        self.assertEqual(single.json['sync'], receipt)
        bulk = self.client.post('/api/outlook/delete-bulk', json={'items': [item]})
        self.assertEqual(bulk.json['deleted'][0]['sync'], receipt)
        self.assertEqual(bulk.json['lease_retained_count'], 1)
        self.assertEqual(bulk.json['pending_sync_count'], 0)

    def test_public_sync_keeps_display_fields_without_connection_details(self):
        receipt = email_pool._public_email_sync({
            'state': 'local_only', 'kind': 'return', 'permanent': True,
            'error_code': 'registration_confirmed', 'lease_retained': True,
            'message': '本地已移除，邮箱已确认注册成功，已保留原租约',
            'api_key': 'private-test-key', 'lease_id': 'private-test-lease',
        })
        self.assertEqual(receipt, {
            'state': 'local_only', 'kind': 'return', 'permanent': True,
            'error_code': 'registration_confirmed', 'lease_retained': True,
            'message': '本地已移除，邮箱已确认注册成功，已保留原租约',
        })


if __name__ == '__main__':
    unittest.main()
