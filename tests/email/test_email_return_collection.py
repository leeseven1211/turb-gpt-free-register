"""删除前的安全事实和退租意图按集合读取、写入，并保留原事务边界。"""
from unittest.mock import patch

from core.email.email_butler import service_facts
from core.storage import records as store, registration
from core.storage.email import bulk_mutations, collections
from tests.email.test_email_collection_reads import CursorCounter
from tests.support_pg import PostgresTestCase


class EmailReturnCollectionTests(PostgresTestCase):
    def setUp(self):
        store.init()
        registration.reset_ready()
        registration.init()
        self.profile = store.insert_row(store.EMAIL_INBOX_PROFILES, {
            'inbox_key': 'collection-return', 'revision': 1, 'connector': 'forward_butler',
            'state': 'active', 'credential_ref': 'TEST_ONLY',
            'inbox_locator': {'api_base': 'https://fixture.test/v2'}})

    def rows(self, count, prefix='unused', **changes):
        with store.transaction() as conn:
            return collections.insert_many(conn, store.EMAIL_BUTLER_POOL, [
                {'email': f'{prefix}{number}@example.test', 'status': 'available',
                 'inbox_profile_id': self.profile, 'butler_handoff': {
                     'lease_id': f'lease-{prefix}-{number}', 'acquisition_id': f'acq-{prefix}-{number}',
                     'client_id': 'original-client'}, **changes}
                for number in range(count)])

    def delete(self, rows):
        queries = []
        with store.transaction() as conn:
            results = bulk_mutations.delete_many(
                [f"email_butler:{row['email']}" for row in rows], conn=CursorCounter(conn, queries))
        return results, queries

    def test_twenty_deletions_use_the_same_collection_queries_as_one(self):
        one, queries_one = self.delete(self.rows(1, 'one'))
        many, queries_many = self.delete(self.rows(20, 'many'))
        self.assertEqual(len(queries_many), len(queries_one),
            f'one={len(queries_one)}, twenty={len(queries_many)}')
        self.assertLessEqual(len(queries_many), 35)
        self.assertEqual([row.status for row in one + many], ['updated'] * 21)
        events = store.list_rows(store.EMAIL_SERVICE_SYNC)
        self.assertEqual(len(events), 21)
        self.assertTrue(all(event['state'] == 'pending' and not event['error_code'] for event in events))
        self.assertEqual({event['payload']['client_id'] for event in events}, {'original-client'})

    def test_collection_delete_does_not_call_single_safety_or_return_queries(self):
        rows = self.rows(8)
        with patch.object(service_facts, 'enqueue_return', side_effect=AssertionError('single return')), \
             patch('core.storage.email.local_imports.pool_mutation_protected',
                   side_effect=AssertionError('single safety')):
            results, _ = self.delete(rows)
        self.assertTrue(all(result.status == 'updated' for result in results))

    def test_return_intents_roll_back_with_pool_changes_and_replay_keeps_original_identity(self):
        rows = self.rows(3)
        with self.assertRaisesRegex(RuntimeError, 'before receipt'):
            with store.transaction() as conn:
                bulk_mutations.delete_many(
                    [f"email_butler:{row['email']}" for row in rows], conn=conn)
                raise RuntimeError('before receipt')
        self.assertEqual(store.list_rows(store.EMAIL_SERVICE_SYNC), [])
        self.assertTrue(all(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'] == 'available'
                            for row in rows))
        first, _ = self.delete(rows)
        events = store.list_rows(store.EMAIL_SERVICE_SYNC)
        store.patch_row(store.EMAIL_BUTLER_POOL, rows[0]['id'], {
            'butler_handoff': {'lease_id': 'changed-lease', 'acquisition_id': 'changed-acquisition'}})
        replay, _ = self.delete(rows)
        self.assertEqual(store.list_rows(store.EMAIL_SERVICE_SYNC), events)
        self.assertEqual([result.data['sync'] for result in replay], [result.data['sync'] for result in first])

    def test_each_target_keeps_its_existing_success_active_and_unknown_result(self):
        rows = self.rows(4)
        store.insert_row(store.ACCOUNTS, {'email': rows[0]['email'], 'access_token': 'test-at'})
        store.insert_row(store.JOBS, {'email': rows[1]['email'], 'status': 'running'})
        store.insert_row(store.JOBS, {'email': rows[2]['email'], 'status': 'failed'})
        results, _ = self.delete(rows)
        self.assertEqual(results[0].reason_code, 'registration_confirmed')
        self.assertEqual([result.data['sync']['error_code'] for result in results[1:]],
            ['registration_active', 'registration_result_unverified', None])
        self.assertEqual([result.data['sync']['state'] for result in results[1:]],
            ['pending', 'local_only', 'pending'])
