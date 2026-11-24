"""集合读取只随来源数量增加 SQL，敏感值不进入持久命令。"""
from types import SimpleNamespace
import logging
from unittest.mock import patch

from flask import Flask

from core.storage import records as store
from tests.support_pg import PostgresTestCase
from webui.routes.email_pool import create_email_pool_blueprint


class CursorCounter:
    def __init__(self, conn, queries):
        self.conn, self.queries = conn, queries
    def cursor(self, *args, **kwargs):
        return CountingCursor(self.conn.cursor(*args, **kwargs), self.queries)
    def __getattr__(self, name):
        return getattr(self.conn, name)


class CountingCursor:
    def __init__(self, cursor, queries):
        self.cursor, self.queries = cursor, queries
    def __enter__(self):
        self.cursor.__enter__()
        return self
    def __exit__(self, *args):
        return self.cursor.__exit__(*args)
    def execute(self, query, params=None, **kwargs):
        self.queries.append(str(query))
        return self.cursor.execute(query, params, **kwargs)
    def __getattr__(self, name):
        return getattr(self.cursor, name)


class EmailCollectionReadsTests(PostgresTestCase):
    def setUp(self):
        store.init()
        app = Flask(__name__)
        app.register_blueprint(create_email_pool_blueprint(SimpleNamespace(logger=logging.getLogger('test'))))
        self.client = app.test_client()

    def test_copy_lines_read_one_query_per_source_and_preserve_order(self):
        from core.storage.email import secrets
        for number in range(12):
            store.insert_row(store.OUTLOOK_POOL, {'email': f'copy{number}@example.test',
                'password': 'p', 'client_id': 'c', 'refresh_token': 'r'})
        store.insert_row(store.GENERIC_API_POOL, {'email': 'api@example.test', 'code_url': 'fixture-url',
            'expires_at': '2027-01-01T00:00:00+00:00'})
        queries = []
        with store.transaction() as conn:
            result = secrets.read_many([{'source': 'generic_api', 'email': 'api@example.test'}]
                + [{'source': 'outlook', 'email': f'copy{number}@example.test'} for number in range(12)]
                + [{'source': 'outlook', 'email': 'COPY0@example.test'}, {'email': 'missing@example.test'}],
                'copy_line', conn=CursorCounter(conn, queries))
        self.assertEqual(len(queries), 2)
        self.assertEqual(result['count'], 13)
        self.assertEqual(result['values'][0]['value'], 'api@example.test----fixture-url----2027-01-01T00:00:00+00:00')
        self.assertEqual(result['values'][1]['value'], 'copy0@example.test----p----c----r')
        self.assertEqual(result['skipped'][0]['email'], 'missing@example.test')

    def test_account_id_precedes_email_fallback_and_butler_fields_stay_restricted(self):
        from core.storage.email import secrets
        by_id = store.insert_row(store.ACCOUNTS, {'email': 'other@example.test', 'access_token': 'id-at'})
        store.insert_row(store.ACCOUNTS, {'email': 'pool@example.test', 'access_token': 'email-at'})
        store.insert_row(store.OUTLOOK_POOL, {'email': 'pool@example.test', 'registered_account_id': by_id,
            'access_token': 'pool-at'})
        store.insert_row(store.EMAIL_BUTLER_POOL, {'email': 'butler@example.test'})
        items = [{'email': 'pool@example.test'}, {'source': 'email_butler', 'email': 'butler@example.test'}]
        result = secrets.read_many(items, 'access_token')
        self.assertEqual(result['values'], [{'source': 'outlook', 'email': 'pool@example.test', 'value': 'id-at'}])
        self.assertEqual(result['skipped'][0]['source'], 'email_butler')
        with patch('core.db.email_pool_secret', side_effect=AssertionError('单条读取不应被循环调用')):
            response = self.client.post('/api/outlook/secret-bulk', json={'items': items, 'field': 'copy_line'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['count'], 2)

    def test_single_email_and_domain_mutations_share_collection_storage(self):
        from core.storage.email import bulk_mutations
        store.insert_row(store.DOMAIN_POOL, {'email': 'domain@example.test', 'status': 'available'})
        with patch('core.db.release_domain_email', side_effect=AssertionError('旧单条写入不应被调用')):
            response = self.client.post('/api/domain-pool/status',
                json={'email': 'domain@example.test', 'status': 'failed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(store.get_row_by(store.DOMAIN_POOL, 'email', 'domain@example.test')['status'], 'failed')
        with patch('core.db.delete_domain_email', side_effect=AssertionError('旧单条删除不应被调用')):
            response = self.client.post('/api/domain-pool/delete', json={'email': 'domain@example.test'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['deleted'])
        store.insert_row(store.OUTLOOK_POOL, {'email': 'single@example.test', 'status': 'available'})
        with patch('core.db.release_outlook', side_effect=AssertionError('旧单条写入不应被调用')):
            response = self.client.post('/api/outlook/status', json={'email': 'single@example.test', 'status': 'used'})
        self.assertEqual(response.status_code, 200)
        with patch('core.db.delete_outlook', side_effect=AssertionError('旧单条删除不应被调用')):
            response = self.client.post('/api/outlook/delete', json={'email': 'single@example.test'})
        self.assertTrue(response.json['deleted'])
