"""Butler 原因准确展示，通用权限错误不误指向邮箱服务。"""
import unittest
from core.operations.errors import classify_task_error


class ButlerV2ErrorClassificationTests(unittest.TestCase):
    def test_mailbox_error_keeps_specific_v2_cause_and_unknown_receipt(self):
        for code in ('permission_denied', 'lease_expired', 'lease_client_mismatch',
                     'provider_unavailable', 'inbound_code_ambiguous', 'api_version_retired',
                     'butler_transport_timeout', 'idempotency_conflict'):
            with self.subTest(code=code):
                result = classify_task_error('Email Butler 请求失败：' + code,
                    task_type='token_refresh', error_code=code,
                    result_summary={'outcome': 'request_unknown'}, task_status='attention_required')
                self.assertEqual(result['code'], code)
                self.assertTrue(result['display_code'].startswith('MAIL-'))
                self.assertTrue(result['reconcile_required'])

    def test_unrelated_generic_permission_error_is_not_a_butler_failure(self):
        result = classify_task_error('其他平台拒绝请求 permission_denied',
                                     task_type='extract_link', error_code='permission_denied')
        self.assertNotIn('Butler', result['summary'])
        self.assertFalse(str(result.get('display_code')).startswith('MAIL-BUTLER'))
