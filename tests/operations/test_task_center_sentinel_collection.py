"""Sentinel 重试按原缓存互斥身份归组，同缓存一次追加执行。"""
import hashlib
import uuid
from unittest.mock import patch

from psycopg import Cursor

from core.maintenance import sentinel
from core.operations import task_gateway
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class SentinelRetryCollectionTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        sentinel.register_actions()

    def tasks(self, count, *, same_key=False, prefix=''):
        tasks = {}
        for number in range(count):
            key = hashlib.sha256((prefix + str(number) if not same_key else 'shared').encode()).hexdigest()
            result = store.create_runtime_task(
                task_type=sentinel._TASK_TYPE, account_id=None, email='', source_id=uuid.uuid4().hex,
                data={'cache_key': key, 'retained': 'old-config'}, resource_family='maintenance_check')
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                            (result['run']['id'],))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                            (result['id'],))
            result.update(status='failed', runs=[result['run']])
            tasks[result['id']] = result
        return tasks

    def retry(self, tasks):
        from core.operations.task_center_sentinel import accept_retries
        statements = []
        execute = Cursor.execute
        def record(cursor, query, *args, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, *args, **kwargs)
        with patch.object(Cursor, 'execute', record), patch.object(task_gateway, 'notify_dispatch'):
            result = accept_retries(tasks)
        return result, statements

    def test_distinct_caches_use_constant_sql_and_one_new_run_per_original_task(self):
        first, small = self.retry(self.tasks(1, prefix='one'))
        many, large = self.retry(self.tasks(20, prefix='many'))
        self.assertEqual(len(large), len(small))
        self.assertLessEqual(len(large), 20)
        self.assertTrue(all(status == 202 and result['accepted'] and not result['reused']
                            for result, status in [*first.values(), *many.values()]))
        for task_id, (result, _) in many.items():
            run = store.get_run(result['run_id'])
            self.assertEqual(run['task_id'], task_id)
            self.assertEqual(run['data']['retry_action'], 'manual_retry')
            self.assertEqual(run['data']['retained'], 'old-config')

    def test_shared_cache_appends_only_first_task_and_reuses_active_run(self):
        tasks = self.tasks(4, same_key=True)
        result, _ = self.retry(tasks)
        payloads = [payload for payload, _ in result.values()]
        self.assertEqual([row['reused'] for row in payloads], [False, True, True, True])
        self.assertEqual(len({row['run_id'] for row in payloads}), 1)
        replay, _ = self.retry(tasks)
        self.assertTrue(all(payload['reused'] for payload, _ in replay.values()))
        self.assertEqual({payload['run_id'] for payload, _ in replay.values()}, {payloads[0]['run_id']})

    def test_invalid_cache_key_and_ineligible_tasks_keep_existing_rejection_boundaries(self):
        tasks = self.tasks(3)
        ids = list(tasks)
        tasks[ids[0]]['data']['cache_key'] = 'invalid'
        tasks[ids[1]]['status'] = 'running'
        tasks[ids[2]]['target_status'] = 'account_deactivated'
        result, _ = self.retry(tasks)
        self.assertEqual(list(result), [ids[0]])
        self.assertEqual(result[ids[0]][1], 409)
        self.assertIn('invalid_sentinel_cache_key', result[ids[0]][0]['error'])

    def test_stale_first_source_is_rejected_but_next_source_can_queue_same_cache(self):
        tasks = self.tasks(3, same_key=True)
        first = next(iter(tasks.values()))
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='running',"
                        "data=data || %s::jsonb WHERE id=%s",
                        ('{"cache_key":"' + 'f' * 64 + '"}', first['run']['id']))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='running' WHERE id=%s",
                        (first['id'],))
        replies, _ = self.retry(tasks)
        payloads = [payload for payload, _ in replies.values()]
        self.assertFalse(payloads[0]['accepted'])
        self.assertTrue(payloads[1]['accepted'])
        self.assertFalse(payloads[1]['reused'])
        self.assertEqual(payloads[1]['run_id'], payloads[2]['run_id'])
        self.assertTrue(payloads[2]['reused'])

    def test_group_winner_survives_statement_chunks_after_rejected_prefix(self):
        tasks = self.tasks(5, same_key=True)
        prefix = list(tasks.values())[:2]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='running',"
                        "data=data || %s::jsonb WHERE id=ANY(%s)",
                        ('{"cache_key":"' + 'f' * 64 + '"}', [task['run']['id'] for task in prefix]))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='running' WHERE id=ANY(%s)",
                        ([task['id'] for task in prefix],))
        with patch('core.storage.operations.bulk_retry_tasks._CHUNK_SIZE', 2):
            replies, _ = self.retry(tasks)
        payloads = [payload for payload, _ in replies.values()]
        self.assertEqual([payload['accepted'] for payload in payloads], [False, False, True, True, True])
        self.assertEqual(len({payload['run_id'] for payload in payloads[2:]}), 1)
        self.assertEqual([payload['reused'] for payload in payloads[2:]], [False, True, True])

    def test_collection_failure_keeps_each_error_receipt_and_does_not_dispatch(self):
        tasks = self.tasks(3)
        from core.operations.task_center_sentinel import accept_retries
        with patch('core.storage.operations.bulk_retry_tasks.retry_tasks_many',
                   side_effect=RuntimeError('isolated failure')), patch.object(task_gateway, 'notify_dispatch') as notify:
            replies = accept_retries(tasks)
        self.assertEqual({status for _, status in replies.values()}, {503})
        self.assertTrue(all(not payload['ok'] and 'isolated failure' not in payload['error']
                            for payload, _ in replies.values()))
        notify.assert_not_called()
