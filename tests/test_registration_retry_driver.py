"""单任务继续邮箱验证时的注册驱动选择边界。"""

from __future__ import annotations

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from core import db, registration_service
from webui.app import create_app


class RegistrationRetryDriverTests(unittest.TestCase):
    def _facts(self):
        source = {
            "id": 21,
            "root_job_id": 21,
            "attempt_id": 70,
            "account_id": 44,
            "status": "partial_success",
            "job_type": "registration",
            "email": "pending@example.test",
            "email_source": "icloud_hide",
            "config_snapshot": {
                "registration_driver": "protocol",
                "password_enabled": True,
                "twofa_enabled": True,
            },
            "batch_id": "original-batch",
            "batch_index": 3,
            "batch_size": 10,
            "batch_workers": 2,
        }
        account = {
            "id": 44,
            "email": "pending@example.test",
            "access_token": "",
            "extra_json": {
                "registration_checkpoint": "email_verification_pending",
                "account_password": "SavedPassword!123",
            },
        }
        attempt = {
            "id": 70,
            "root_job_id": 21,
            "email": "pending@example.test",
            "email_snapshot": "pending@example.test",
            "checkpoint": "otp_started",
            "target_status": "request_unknown",
            "remote_account_state": "request_unknown",
            "account_id": None,
        }
        return source, account, attempt

    def _retry(self, source, account, attempt, *, action="registration_resume", child=None):
        created = child is None
        child = child or {
            "id": 22,
            "status": "pending",
            "job_type": "registration_resume",
            "log_file": "/tmp/test-registration-retry.log",
        }
        executor = Mock()
        with ExitStack() as stack:
            stack.enter_context(patch.object(db, "get_job", return_value=source))
            stack.enter_context(patch.object(registration_service, "_account_for_job", return_value=account))
            stack.enter_context(patch.object(registration_service, "_enrich_account_registration_state", side_effect=lambda value: value))
            stack.enter_context(patch.object(registration_service, "get_retry_info", return_value={
                "retryable": True,
                "retry_action": action,
            }))
            stack.enter_context(patch.object(registration_service, "_read_linked_attempt_for_job", return_value=(attempt, False)))
            create_retry = stack.enter_context(patch.object(db, "create_retry_job", return_value=(child, created)))
            stack.enter_context(patch.object(registration_service, "get_executor", return_value=executor))
            result = registration_service.retry_job(21, registration_driver="roxy")
            call = create_retry.call_args
        return result, call, executor

    def test_roxy_resume_overrides_only_new_child_snapshot(self):
        source, account, attempt = self._facts()
        original = copy.deepcopy(source)

        result, create_call, executor = self._retry(source, account, attempt)

        self.assertTrue(result["ok"])
        self.assertEqual(create_call.kwargs["job_type"], "registration_resume")
        self.assertEqual(create_call.kwargs["email"], "pending@example.test")
        self.assertEqual(create_call.kwargs["account_id"], 44)
        self.assertEqual(create_call.kwargs["data"]["config_snapshot"], {
            "registration_driver": "roxy",
            "password_enabled": True,
            "twofa_enabled": True,
        })
        self.assertEqual(source, original)
        executor.submit.assert_called_once()

    def test_roxy_resume_rejects_non_resume_and_unverified_identity(self):
        for changed, action in (
            ({}, "registration"),
            ({"account": {"access_token": "already-complete"}}, "registration_resume"),
            ({"account": {"extra_json": {"registration_checkpoint": "completed", "account_password": "SavedPassword!123"}}}, "registration_resume"),
            ({"account": {"extra_json": {"registration_checkpoint": "email_verification_pending"}}}, "registration_resume"),
            ({"account": {"email": "different@example.test"}}, "registration_resume"),
            ({"source": {"attempt_id": None}}, "registration_resume"),
            ({"attempt": {"root_job_id": 99}}, "registration_resume"),
            ({"attempt": {"email": "different@example.test"}}, "registration_resume"),
            ({"attempt": {"checkpoint": "core_persisted"}}, "registration_resume"),
        ):
            with self.subTest(changed=changed, action=action):
                source, account, attempt = self._facts()
                source.update(changed.get("source", {}))
                account.update(changed.get("account", {}))
                attempt.update(changed.get("attempt", {}))
                result, create_call, executor = self._retry(source, account, attempt, action=action)
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], 409)
                self.assertIsNone(create_call)
                executor.submit.assert_not_called()

    def test_roxy_resume_does_not_reuse_active_protocol_child(self):
        source, account, attempt = self._facts()
        active = {
            "id": 22,
            "status": "pending",
            "job_type": "registration_resume",
            "data": {"config_snapshot": {"registration_driver": "protocol"}},
        }

        result, create_call, executor = self._retry(source, account, attempt, child=active)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 409)
        self.assertIsNotNone(create_call)
        executor.submit.assert_not_called()

    def test_single_job_retry_api_passes_roxy_choice(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("webui.app.svc.retry_job", return_value={"ok": True, "created": True}) as retry:
            response = client.post(
                "/api/jobs/21/retry",
                json={"registration_driver": "roxy", "workers": 2},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 200)
        retry.assert_called_once_with(21, workers=2, registration_driver="roxy")

    def test_single_job_retry_api_rejects_unknown_driver(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("webui.app.svc.retry_job") as retry:
            response = client.post(
                "/api/jobs/21/retry",
                json={"registration_driver": "unknown"},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 400)
        retry.assert_not_called()

    def test_retry_apis_reject_non_object_json_bodies(self):
        client = create_app(auth_code="test-auth").test_client()
        for path, payload in (
            ("/api/jobs/21/retry", []),
            ("/api/jobs/21/retry", False),
            ("/api/jobs/retry-bulk", []),
            ("/api/jobs/retry-bulk", False),
        ):
            with self.subTest(path=path, payload=payload), patch("webui.app.svc.retry_job") as retry:
                response = client.post(
                    path,
                    json=payload,
                    headers={"X-Auth-Code": "test-auth"},
                )
                self.assertEqual(response.status_code, 400)
                retry.assert_not_called()

    def test_bulk_retry_api_rejects_driver_choice(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("webui.app.svc.retry_job") as retry:
            response = client.post(
                "/api/jobs/retry-bulk",
                json={"job_ids": [21], "registration_driver": "roxy"},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 400)
        retry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
