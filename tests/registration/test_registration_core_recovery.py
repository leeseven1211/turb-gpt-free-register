"""历史失败续跑必须在首次账号写入前核验当前执行实例。"""
from types import SimpleNamespace
import json
import unittest
from unittest.mock import Mock, patch

from core.accounts import export as account_export
from core.registration import service as svc
from core.storage import registration


class RegistrationCoreRecoveryTests(unittest.TestCase):
    def test_rejected_terminal_resume_does_not_write_or_report_success(self):
        context = SimpleNamespace(attempt_id=7, run_id=9, job_id=11, execution_id="stale")
        for checkpoint in ("failed", "manual_reconcile"):
            with self.subTest(checkpoint=checkpoint), \
                 patch.object(svc, "_THREAD_CTX", context), \
                 patch.object(registration, "get_attempt", return_value={"checkpoint": checkpoint, "account_id": 4}), \
                 patch.object(registration, "persist_core_account", side_effect=ValueError("执行实例已变化")), \
                 patch.object(account_export, "persist_account_core") as export, \
                 patch.object(svc, "report_registered_account") as report:
                with self.assertRaisesRegex(ValueError, "执行实例已变化"):
                    svc.persist_registration_core(email="original@example.test", access_token="test-token")
                export.assert_not_called()
                report.assert_not_called()

    def test_confirmed_terminal_resume_preserves_metadata_after_atomic_recovery(self):
        context = SimpleNamespace(attempt_id=7, run_id=9, job_id=11, execution_id="current")
        calls = Mock()
        extra = {"account_password": "saved-password", "user": {"id": "user-test"}}
        session = {"user": {"email": "original@example.test"}}
        with patch.object(svc, "_THREAD_CTX", context), \
             patch.object(registration, "get_attempt", return_value={"checkpoint": "failed", "account_id": 4}), \
             patch.object(registration, "persist_core_account", return_value={"account_id": 4}) as persist, \
             patch.object(account_export, "persist_account_core", return_value=4) as export, \
             patch.object(registration, "advance_checkpoint") as advance, \
             patch.object(svc, "report_registered_account") as report:
            for name, mock in (("persist", persist), ("export", export), ("advance", advance), ("report", report)):
                calls.attach_mock(mock, name)
            result = svc.persist_registration_core(email="original@example.test", access_token="test-token",
                totp_secret="test-secret", extra=extra, chatgpt_session=session,
                email_source="icloud_hide", proxy_used="http://proxy.example.test")
        self.assertEqual(result, 4)
        self.assertEqual([call[0] for call in calls.mock_calls], ["persist", "export", "advance", "report"])
        persist.assert_called_once_with(7, access_token="test-token",
            account={"id": 4, "email": "original@example.test", "chatgpt_session": session,
                     "totp_secret": "test-secret", "extra_json": json.dumps(extra, ensure_ascii=False),
                     "email_source": "icloud_hide", "proxy_used": "http://proxy.example.test"},
            run_id=9, job_id=11, execution_id="current")
        export.assert_called_once_with(email="original@example.test", access_token="test-token",
            totp_secret="test-secret", extra=extra, chatgpt_session=session,
            email_source="icloud_hide", proxy_used="http://proxy.example.test")
        report.assert_called_once_with(4)
