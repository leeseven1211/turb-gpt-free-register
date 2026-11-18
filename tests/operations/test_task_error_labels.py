"""错误短语目录覆盖真实分类器登记项；纯源码/纯函数测试，无数据库。"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from core.operations.error_labels import (
    CAUSE_CODE_LABELS, CODE_LABELS, FALLBACK_LABEL, label_catalog, label_for_code, short_error_label,
)
from tools.maintenance.generate_task_error_labels import rendered_catalog

ROOT = Path(__file__).resolve().parents[2]
TABLES = {
    '_DISPLAY_CODES', '_DISPLAY_SUMMARIES', '_CAUSE_DETAILS', '_BUTLER_RECIPIENT_CAUSES',
    '_OTP_PAGE_NETWORK_CAUSES', '_PASSWORD_RECOVERY_STORAGE_CAUSES',
    '_PASSWORD_RECOVERY_WORKFLOW_CAUSES', '_PASSWORD_RECOVERY_UNKNOWN_CAUSES',
    '_SUB2API_ERROR_DETAILS', '_C2A_ERROR_DETAILS', '_CONCURRENCY_ERROR_DETAILS',
    '_CONCURRENCY_WAIT_REASONS', '_CAUSES', 'ROXY_LOGIN_CAUSES',
}
SOURCES = ('core/operations/errors.py', 'core/accounts/plans/errors.py',
           'core/accounts/liveness/roxy/refresh_errors.py')


def classifier_tables():
    for filename in SOURCES:
        for node in ast.parse((ROOT / filename).read_text()).body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and target.id in TABLES and isinstance(node.value, ast.Dict):
                yield target.id, node.value


class TaskErrorLabelTests(unittest.TestCase):
    def test_every_registered_static_cause_has_an_explicit_short_label(self):
        """新增分类器码却忘记展示映射时失败，不能只靠全局兜底假装覆盖。"""
        known = set()
        for table, node in classifier_tables():
            for key in node.keys:
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    continue
                code = key.value
                if table.startswith('_PASSWORD_RECOVERY_'):
                    code = 'password_recovery_' + code
                known.add(code)
                with self.subTest(table=table, code=code):
                    self.assertTrue(code in CAUSE_CODE_LABELS or code in CODE_LABELS, code)
        self.assertGreater(len(known), 490)

    def test_stable_enum_and_derived_integration_categories_are_covered(self):
        tree = ast.parse((ROOT / SOURCES[0]).read_text())
        enum = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'TaskErrorCode')
        for node in enum.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                with self.subTest(code=node.value.value):
                    self.assertIsNotNone(label_for_code('code', node.value.value))
        for table, node in classifier_tables():
            if table not in {'_SUB2API_ERROR_DETAILS', '_C2A_ERROR_DETAILS'}:
                continue
            family = 'sub2api' if table == '_SUB2API_ERROR_DETAILS' else 'c2a'
            for value in node.values:
                category = ast.literal_eval(value)[0]
                with self.subTest(family=family, category=category):
                    self.assertIn(f'external.{family}.{category}', CODE_LABELS)

    def test_every_label_and_dynamic_rule_is_at_most_ten_characters(self):
        catalog = label_catalog()
        values = [catalog['fallback']]
        for field in ('codeLabels', 'causeCodeLabels', 'displayCodeLabels', 'categoryLabels'):
            values.extend(catalog[field].values())
        values.extend(rule['label'] for rule in catalog['rules'])
        for value in values:
            with self.subTest(value=value):
                self.assertTrue(1 <= len(value) <= 10)
                self.assertNotIn('…', value)

    def test_refined_mailbox_evidence_beats_generic_otp_failure(self):
        self.assertEqual('邮箱租约已到期', short_error_label({
            'cause_code': 'email_otp_failed', 'cause_display_code': 'MAIL-BUTLER-V2-EXPIRED',
            'code': 'workflow.verification',
        }))
        self.assertEqual('验证码等待超时', short_error_label({
            'cause_code': 'email_otp_failed', 'cause_display_code': 'MAIL-OTP-002',
            'code': 'workflow.verification',
        }))

    def test_dynamic_transport_http_and_missing_evidence_keep_their_meaning(self):
        fixtures = [
            ({'cause_code': 'oauth_callback_transport_timeout'}, '回调请求超时'),
            ({'cause_code': 'password_sentinel_http_rejected'}, '密码预检请求被拒'),
            ({'cause_code': 'email_otp_failed', 'cause_display_code': 'NET-MAILBOX-006'}, '收件域名解析失败'),
            ({'cause_code': 'mfa_verify_http_error', 'cause_display_code': 'OA-MFA-401'}, '双重验证请求未授权'),
            ({'cause_code': 'registration_receipt_missing'}, '执行回执缺失'),
            ({'cause_code': 'email_otp_failure_diagnostics_missing'}, '失败诊断缺失'),
            ({'code': 'token_http_401'}, '套餐凭据未通过验证'),
            ({'cause_code': 'c2a_update_unconfirmed'}, '凭据更新回执缺失'),
            ({'cause_code': 'request_unknown'}, '请求结果未确认'),
        ]
        for info, expected in fixtures:
            with self.subTest(info=info):
                self.assertEqual(expected, short_error_label(info))

    def test_unknown_text_never_becomes_a_new_diagnosis(self):
        for raw in ('account_deactivated', 'password rejected', 'HTTP 401', '<script>credentials</script>'):
            self.assertEqual(FALLBACK_LABEL, short_error_label({'summary': raw, 'raw': raw}))
        self.assertEqual('邮箱验证异常', short_error_label({'cause_code': 'future_mail_reason', 'category': 'email'}))
        self.assertEqual('账号异常', short_error_label({'source': 'account'}))

    def test_json_is_generated_from_the_same_directory(self):
        output = ROOT / 'frontend/src/generated/task-error-labels.json'
        self.assertEqual(rendered_catalog(), output.read_text())
        self.assertEqual(label_catalog(), json.loads(output.read_text()))


if __name__ == '__main__':
    unittest.main()
