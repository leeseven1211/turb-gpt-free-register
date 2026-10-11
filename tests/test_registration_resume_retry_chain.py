"""继续注册子任务的身份校验、批量投影及任务中心入口回归。"""
import copy
import logging
import unittest
from unittest.mock import Mock, patch

from flask import Flask

from core import registration_service as svc
from core.storage import registration as store
from webui import runtime
from webui.routes import operations


def facts():
    root = {'id': 21, 'attempt_id': 70, 'account_id': 44, 'status': 'partial_success',
            'email': 'pending@example.test', 'email_source': 'icloud_hide'}
    child = dict(root, id=22, root_job_id=21, parent_job_id=21, job_type='registration_resume')
    account = {'id': 44, 'email': root['email'], 'access_token': '', 'extra_json': {
        'registration_checkpoint': 'email_verification_pending', 'account_password': 'test-password'}}
    attempt = {'id': 70, 'source_root_job_id': 21, 'account_id': 44, 'email_snapshot': root['email'],
               'checkpoint': 'postprocessing', 'target_status': 'email_verification_pending', 'remote_identity_state': 'confirmed'}
    return root, child, account, attempt


class ResumeRetryChainTests(unittest.TestCase):
    @staticmethod
    def _client():
        app = Flask('resume-retry-route')
        app.register_blueprint(operations.create_operations_blueprint(
            runtime.WebUIContext(app, logging.getLogger(__name__))
        ))
        return app.test_client()

    @staticmethod
    def _task():
        return {'id': 9, 'task_type': 'registration_resume', 'source_system': 'registration_chains',
                'source_id': '21:registration_resume', 'status': 'partial_success',
                'target_status': 'email_verification_pending',
                'next_actions': [{'action': 'registration_resume', 'source_job_id': 22}]}

    def test_list_and_detail_expose_actual_service_retry_decision(self):
        client = self._client()
        for allowed in (True, False):
            root, child, account, attempt = facts()
            if not allowed:
                account['extra_json']['account_password'] = ''
            with self.subTest(allowed=allowed), \
                 patch.object(operations.operation_task_store, 'list_tasks', side_effect=lambda **kw: {'items': [self._task()]}), \
                 patch.object(operations.operation_task_store, 'list_batches', return_value=[]), \
                 patch.object(operations.operation_task_store, 'get_task', side_effect=lambda *a, **kw: self._task()), \
                 patch.object(svc, '_retry_jobs_by_ids', side_effect=lambda ids: {i: {21: root, 22: child}[i] for i in ids}), \
                 patch.object(svc.db, 'get_successful_retries_for_jobs', return_value={}), \
                 patch.object(svc.db, 'get_accounts_for_jobs', return_value={22: account}), \
                 patch.object(store, 'get_attempts_for_root_jobs', return_value={21: attempt}):
                listing = client.get('/api/operations')
                detail = client.get('/api/operations/9')
            self.assertEqual(listing.status_code, 200)
            self.assertEqual(detail.status_code, 200)
            for task in (listing.get_json()['items'][0], detail.get_json()['task']):
                self.assertEqual(task['retryable'], allowed)
                self.assertEqual(bool(task['next_actions']), allowed)
                if allowed:
                    self.assertEqual(task['next_actions'][0]['source_job_id'], 22)
                else:
                    self.assertIn('密码', task['retry_reason'])

    def test_single_and_bulk_routes_resume_child_with_original_identity(self):
        client = self._client()
        root, child, account, attempt = facts()
        executor = Mock()
        with patch.object(operations.operation_task_store, 'get_task', side_effect=lambda *a, **kw: self._task()), \
             patch.object(svc.db, 'get_job', side_effect=lambda ident: {21: root, 22: child}.get(ident)), \
             patch.object(svc.db, 'get_successful_retry_for_job', return_value=None), \
             patch.object(svc, '_account_for_job', return_value=account), \
             patch.object(svc, '_enrich_account_registration_state', side_effect=lambda x: x), \
             patch.object(svc, '_read_linked_attempt_for_job', return_value=(attempt, False)), \
             patch.object(svc, '_retry_jobs_by_ids', return_value={21: root}), \
             patch.object(svc.db, 'create_retry_job', return_value=({'id': 23, 'log_file': '/tmp/resume-test.log'}, True)) as create, \
             patch.object(svc, 'get_executor', return_value=executor):
            single = client.post('/api/operations/9/retry')
            bulk = client.post('/api/operations/bulk', json={'action': 'retry', 'task_ids': [9]})
        self.assertEqual(single.status_code, 200)
        self.assertTrue(single.get_json()['ok'])
        self.assertEqual(bulk.status_code, 200)
        self.assertEqual(bulk.get_json()['accepted_count'], 1)
        self.assertEqual(create.call_count, 2)
        for call in create.call_args_list:
            self.assertEqual(call.args, (22,))
            self.assertEqual(call.kwargs['account_id'], 44)
            self.assertEqual(call.kwargs['email'], root['email'])

    def test_child_partial_and_unknown_can_resume_with_matching_root(self):
        root, child, account, attempt = facts()
        for status in ('failed', 'partial_success', 'request_unknown', 'manual_reconcile', 'interrupted'):
            with self.subTest(status=status):
                info = svc._build_retry_info(dict(child, status=status), account=account,
                    successful_retry=None, attempt=attempt, root_job=root)
                self.assertTrue(info['retryable'])
                self.assertEqual(info['retry_action'], 'registration_resume')

    def test_identity_and_terminal_fences_are_preserved(self):
        for mutation in ('missing_root', 'root_id', 'root_email', 'root_attempt', 'child_email',
                         'child_attempt', 'password', 'account_id', 'deactivated', 'active'):
            with self.subTest(mutation=mutation):
                root, child, account, attempt = facts()
                if mutation == 'missing_root': root = None
                if mutation == 'root_id': root['id'] = 999
                if mutation == 'root_email': root['email'] = 'other@example.test'
                if mutation == 'root_attempt': root['attempt_id'] = 999
                if mutation == 'child_email': child['email'] = 'other@example.test'
                if mutation == 'child_attempt': child['attempt_id'] = 999
                if mutation == 'password': account['extra_json']['account_password'] = ''
                if mutation == 'account_id': account['id'] = 999
                if mutation == 'deactivated': attempt['target_status'] = 'deactivated'
                if mutation == 'active': child['status'] = 'running'
                info = svc._build_retry_info(child, account=account, successful_retry=None, attempt=attempt, root_job=root)
                self.assertFalse(info['retryable'])

    def test_missing_or_unreadable_root_fails_closed(self):
        _, child, account, attempt = facts()
        for failure in (False, True):
            with self.subTest(failure=failure), \
                 patch.object(svc.db, 'get_successful_retry_for_job', return_value=None), \
                 patch.object(svc, '_account_for_job', return_value=account), \
                 patch.object(svc, '_read_linked_attempt_for_job', return_value=(attempt, False)), \
                 patch.object(svc, '_retry_jobs_by_ids', return_value={}, side_effect=OSError('测试读取失败') if failure else None):
                self.assertFalse(svc.get_retry_info(child)['retryable'])

    def test_successful_descendant_prevents_redundant_resume(self):
        root, child, account, attempt = facts()
        info = svc._build_retry_info(child, account=account, successful_retry={'id': 23}, attempt=attempt, root_job=root)
        self.assertFalse(info['retryable'])
        self.assertIn('#23', info['retry_reason'])

    def test_single_and_bulk_use_same_real_root(self):
        root, child, account, attempt = facts()
        with patch.object(svc.db, 'get_successful_retry_for_job', return_value=None), \
             patch.object(svc, '_account_for_job', return_value=account), \
             patch.object(svc, '_read_linked_attempt_for_job', return_value=(attempt, False)), \
             patch.object(svc, '_retry_jobs_by_ids', return_value={21: root}) as roots:
            single = svc.get_retry_info(child)
            roots.assert_called_once_with([21])
        with patch.object(svc.db, 'get_successful_retries_for_jobs', return_value={}), \
             patch.object(svc.db, 'get_accounts_for_jobs', return_value={22: account, 23: account}), \
             patch.object(store, 'get_attempts_for_root_jobs', return_value={21: attempt}), \
             patch.object(svc, '_retry_jobs_by_ids', return_value={21: root}) as roots:
            bulk = svc.get_retry_info_bulk([child, dict(child, id=23)])
            roots.assert_called_once_with([21])
        self.assertEqual(single, bulk[22])
        self.assertTrue(bulk[23]['retryable'])

    def test_child_retry_reaches_executor_without_new_identity(self):
        root, child, account, attempt = facts()
        executor = Mock()
        with patch.object(svc.db, 'get_job', side_effect=lambda ident: {21: root, 22: child}.get(ident)), \
             patch.object(svc.db, 'get_successful_retry_for_job', return_value=None), \
             patch.object(svc, '_account_for_job', return_value=account), \
             patch.object(svc, '_enrich_account_registration_state', side_effect=lambda x: x), \
             patch.object(svc, '_read_linked_attempt_for_job', return_value=(attempt, False)), \
             patch.object(svc, '_retry_jobs_by_ids', return_value={21: root}), \
             patch.object(svc.db, 'create_retry_job', return_value=({'id': 23, 'log_file': '/tmp/resume-test.log'}, True)) as create, \
             patch.object(svc, 'get_executor', return_value=executor):
            result = svc.retry_job(22, registration_driver='roxy')
        self.assertTrue(result['ok'])
        self.assertEqual(result['retry_action'], 'registration_resume')
        self.assertEqual(create.call_args.args, (22,))
        self.assertEqual(create.call_args.kwargs['email'], root['email'])
        self.assertEqual(create.call_args.kwargs['account_id'], 44)
        executor.submit.assert_called_once()

    def test_task_center_hides_rejected_actions_and_preserves_unrelated_tasks(self):
        task = {'id': 9, 'task_type': 'registration_resume', 'source_system': 'registration_chains',
                'source_id': '21:registration_resume', 'status': 'partial_success', 'target_status': 'email_verification_pending',
                'next_actions': [{'action': 'registration_resume', 'source_job_id': 22}]}
        root, child, _, _ = facts()
        for allowed in (False, True):
            item = copy.deepcopy(task)
            with patch.object(svc, '_retry_jobs_by_ids', return_value={22: child}), \
                 patch.object(svc, 'get_retry_info_bulk', return_value={22: {'retryable': allowed, 'retry_action': 'registration_resume', 'retry_reason': '校验结果'}}):
                svc.attach_registration_resume_retry_info([item])
            self.assertEqual(bool(item['next_actions']), allowed)
            self.assertEqual(item['retryable'], allowed)
        completed = dict(task, target_status='completed', next_actions=[{'action': 'codex_retry'}])
        before = copy.deepcopy(completed)
        svc.attach_registration_resume_retry_info([completed])
        self.assertEqual(completed, before)
