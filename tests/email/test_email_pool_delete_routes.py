"""单条删除与批量 Worker 使用相同保护规则；批量 HTTP 仅受理命令。"""
import logging
from unittest.mock import patch

from flask import Flask

from core.storage import records as store, registration
from core.storage.email import bulk_mutations
from tests.support_pg import PostgresTestCase
from webui import runtime
from webui.routes import email_pool


class EmailPoolDeleteRoutesTests(PostgresTestCase):
    SOURCES = {
        'outlook': store.OUTLOOK_POOL,
        'generic_api': store.GENERIC_API_POOL,
        'cloudflare_domain': store.DOMAIN_POOL,
        'icloud_hide': store.ICLOUD_HIDE_POOL,
        'email_butler': store.EMAIL_BUTLER_POOL,
    }

    def setUp(self):
        store.init()
        registration.reset_ready()
        registration.init()
        app = Flask('email-pool-delete-routes')
        context = runtime.WebUIContext(app, logging.getLogger('email-pool-delete-routes'))
        app.register_blueprint(email_pool.create_email_pool_blueprint(context))
        self.client = app.test_client()

    def seed_row(self, source, email, **changes):
        return store.insert_row(self.SOURCES[source], {
            'email': email, 'status': 'request_unknown', **changes})

    def accept(self, items):
        commands = []
        def submit(operation, targets, parameters, **kwargs):
            commands.append((operation, targets, parameters))
            return {'accepted': True, 'command_id': 11, 'task_id': 12, 'run_id': 13}
        with patch('core.operations.bulk_mutation_worker.submit_bulk_mutation', side_effect=submit):
            response = self.client.post('/api/outlook/delete-bulk', json={'items': items})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json['accepted'])
        self.assertEqual(response.json['command_id'], '11')
        self.assertNotIn('deleted_count', response.json)
        self.assertEqual(len(commands), 1)
        return commands[0]

    def execute(self, command):
        operation, targets, parameters = command
        self.assertEqual(operation, 'email_pool_delete')
        with store.transaction() as conn:
            return bulk_mutations._handle_delete_chunk(targets, parameters, conn=conn)

    def test_confirmed_success_has_same_single_and_bulk_reason_for_every_source(self):
        for source in self.SOURCES:
            item = {'source': source, 'email': source + '@example.test'}
            self.seed_row(**item)
            store.insert_row(store.ACCOUNTS, {'email': item['email'], 'access_token': 'fixture-at'})
            with self.subTest(source=source):
                single = self.client.post('/api/outlook/delete', json=item)
                self.assertEqual(single.status_code, 200)
                self.assertFalse(single.json['deleted'])
                self.assertEqual(single.json['reason'], '邮箱已确认注册成功，不能删除')
                self.assertEqual(single.json['reason_code'], 'registration_confirmed')
                result = self.execute(self.accept([item]))[0]
                self.assertEqual((result.status, result.reason_code, result.reason),
                    ('skipped', 'registration_confirmed', single.json['reason']))
                self.assertEqual(result.data['source'], source)

    def test_unconfirmed_history_uses_same_collection_for_single_and_bulk(self):
        for source in self.SOURCES:
            item = {'source': source, 'email': source + '@example.test'}
            row_id = self.seed_row(**item)
            with self.subTest(source=source):
                single = self.client.post('/api/outlook/delete', json=item)
                self.assertEqual(single.status_code, 200)
                self.assertTrue(single.json['deleted'])
                result = self.execute(self.accept([item]))[0]
                self.assertEqual(result.status, 'updated')
                self.assertEqual(store.get_row(self.SOURCES[source], row_id)['status'], 'tombstone')

    def test_bulk_keeps_success_and_other_skip_reasons(self):
        self.seed_row('outlook', 'success@example.test')
        store.insert_row(store.ACCOUNTS, {'email': 'success@example.test', 'access_token': 'fixture-at'})
        self.seed_row('email_butler', 'unknown@example.test')
        results = self.execute(self.accept([
            {'source': 'outlook', 'email': 'success@example.test'},
            {'source': 'generic_api', 'email': 'missing@example.test'},
            {'source': 'email_butler', 'email': 'unknown@example.test'},
        ]))
        self.assertEqual([result.status for result in results], ['skipped', 'skipped', 'updated'])
        self.assertEqual([result.reason for result in results[:2]],
            ['邮箱已确认注册成功，不能删除', '邮箱不存在'])

    def test_success_confirmed_after_acceptance_is_checked_at_worker_execution(self):
        item = {'source': 'email_butler', 'email': 'late-success@example.test'}
        row_id = self.seed_row(**item)
        command = self.accept([item])
        self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row_id)['status'], 'request_unknown')
        store.insert_row(store.ACCOUNTS, {'email': item['email'], 'access_token': 'late-at'})
        result = self.execute(command)[0]
        single = self.client.post('/api/outlook/delete', json=item)
        self.assertEqual((result.status, result.reason_code), ('skipped', 'registration_confirmed'))
        self.assertEqual(result.reason, single.json['reason'])
        self.assertEqual(store.list_rows(store.EMAIL_SERVICE_SYNC), [])

    def test_retained_lease_message_survives_single_and_bulk_receipt(self):
        item = {'source': 'email_butler', 'email': 'unknown@example.test'}
        self.seed_row(**item, butler_handoff={'lease_id': 'original-lease'})
        single = self.client.post('/api/outlook/delete', json=item)
        self.assertTrue(single.json['deleted'])
        receipt = single.json['sync']
        self.assertEqual((receipt['state'], receipt['error_code'], receipt['lease_retained']),
            ('local_only', 'registration_result_unverified', True))
        self.assertEqual(receipt['message'], '本地已移除，注册结果未确认，已保留原租约')
        result = self.execute(self.accept([item]))[0]
        self.assertEqual(email_pool._public_email_sync(result.data['sync']), receipt)
        self.assertEqual(sum(bool(result.data['sync']['lease_retained']) for result in [result]), 1)

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
