"""本地导入的 SQL 数量按分块增长，跨来源和原服务事实不可绕过。"""
from unittest.mock import patch

from core.storage import records as store
from core.storage.email import local_imports
from core.email.email_butler import service_facts
from tests.support_pg import PostgresTestCase
from tests.email.test_email_collection_reads import CursorCounter


class EmailCollectionImportsTests(PostgresTestCase):
    def setUp(self):
        store.init()
        self.consumer = patch('core.email.email_butler.inventory_handoff._consumer_instance', return_value='fixture-instance')
        self.consumer.start()
        self.addCleanup(self.consumer.stop)

    def test_generic_import_uses_bounded_sql_and_keeps_cross_source_history(self):
        store.insert_row(store.OUTLOOK_POOL, {'email': 'duplicate@example.test', 'status': 'tombstone'})
        store.insert_row(store.EMAIL_SERVICE_SYNC, {'event_key': 'old-import', 'kind': 'import',
            'source': 'generic_api', 'address_norm': 'historical@example.test', 'pool_id': 99,
            'state': 'local_only', 'attempts': 0})
        records = [{'email': f'fresh{number}@example.test', 'code_url': 'fixture-url'} for number in range(20)]
        records += [{'email': 'FRESH0@example.test', 'code_url': 'fixture-url'},
            {'email': 'duplicate@example.test', 'code_url': 'fixture-url'},
            {'email': 'historical@example.test', 'code_url': 'fixture-url'}]
        queries = []
        with store.transaction() as conn:
            result = local_imports.import_resources(records, source='generic_api', _conn=CursorCounter(conn, queries))
        self.assertEqual(result, (20, 3))
        self.assertLessEqual(len(queries), 14, '\n'.join(queries))
        self.assertEqual(store.count_rows(store.GENERIC_API_POOL), 20)
        self.assertEqual(store.count_rows(store.EMAIL_SERVICE_SYNC), 21)
        row = store.get_row_by(store.GENERIC_API_POOL, 'email', 'fresh0@example.test')
        self.assertEqual((row['status'], row['service_sync_state'], row['service_fact_permanent']), ('available', 'local_only', True))

    def test_registered_import_is_collective_and_inherits_invalid_fact(self):
        store.insert_row(store.GENERIC_API_POOL, {'email': 'existing@example.test', 'status': 'used',
            'email_invalid': True, 'email_invalid_reason': '测试失效', 'email_invalid_source': 'manual'})
        records = [{'email': 'existing@example.test', 'code_url': 'fixed', 'access_token': 'fixture-at'}]
        records += [{'email': f'reg{number}@example.test', 'code_url': 'fixed'} for number in range(12)]
        queries = []
        with store.transaction() as conn:
            result = local_imports.import_resources(records, source='generic_api', _as_registered=True,
                _conn=CursorCounter(conn, queries))
        self.assertEqual(result, (13, 0))
        self.assertLessEqual(len(queries), 22, '\n'.join(queries))
        account = store.get_row_by(store.ACCOUNTS, 'email', 'existing@example.test')
        self.assertTrue(account['email_invalid'])
        self.assertEqual(account['access_token'], 'fixture-at')
        self.assertEqual(store.count_rows(store.ACCOUNTS), 13)
        self.assertTrue(all(row['status'] == 'used' and row['registered_account_id'] for row in store.list_rows(store.GENERIC_API_POOL)))

    def test_enqueue_import_many_is_idempotent_and_transactional(self):
        rows = []
        for number in range(4):
            row_id = store.insert_row(store.OUTLOOK_POOL, {'email': f'event{number}@example.test', 'status': 'available'})
            rows.append(store.get_row(store.OUTLOOK_POOL, row_id))
        with self.assertRaisesRegex(RuntimeError, '回滚'):
            with store.transaction() as conn:
                service_facts.enqueue_import_many('outlook', rows, conn=conn)
                raise RuntimeError('回滚')
        self.assertEqual(store.count_rows(store.EMAIL_SERVICE_SYNC), 0)
        with store.transaction() as conn:
            first = service_facts.enqueue_import_many('outlook', rows, conn=conn)
            second = service_facts.enqueue_import_many('outlook', rows, conn=conn)
        self.assertEqual([row['id'] for row in first], [row['id'] for row in second])
        self.assertEqual(store.count_rows(store.EMAIL_SERVICE_SYNC), 4)
