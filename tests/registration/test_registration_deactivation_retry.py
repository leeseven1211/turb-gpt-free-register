# -*- coding: utf-8 -*-
"""已明确永久失效的注册 Attempt 不得再次进入注册重跑。"""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from core.registration import service as service
from core.storage import registration as registration_store


class RegistrationDeactivationRetryTests(unittest.TestCase):
    def _failed_job(self) -> dict:
        return {
            "id": 81,
            "root_job_id": 80,
            "attempt_id": 180,
            "status": "failed",
            "job_type": "registration",
            "email_source": "icloud_hide",
            "email": "held@example.test",
        }

    def test_single_retry_projection_hides_registration_retry_for_deactivated_root_attempt(self):
        job = self._failed_job()
        with (
            patch.object(service.db, "get_successful_retry_for_job", return_value=None),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(
                registration_store,
                "get_attempt",
                return_value={"target_status": "deactivated"},
            ) as get_attempt,
        ):
            info = service.get_retry_info(job)

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertIn("永久失效", info["retry_reason"])
        get_attempt.assert_called_once_with(180)

    def test_single_retry_projection_fails_closed_when_linked_attempt_read_raises(self):
        job = self._failed_job()
        with (
            patch.object(service.db, "get_successful_retry_for_job", return_value=None),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(
                registration_store,
                "get_attempt",
                side_effect=RuntimeError("registration storage unavailable"),
            ) as get_attempt,
        ):
            info = service.get_retry_info(job)

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertIn("读取失败", info["retry_reason"])
        self.assertIn("稍后重试", info["retry_reason"])
        get_attempt.assert_called_once_with(180)

    def test_unlinked_light_job_does_not_read_registration_attempt(self):
        job = self._failed_job()
        job.pop("attempt_id")
        with (
            patch.object(service.db, "get_successful_retry_for_job", return_value=None),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(registration_store, "get_attempt_by_job") as get_attempt_by_job,
            patch.object(registration_store, "get_attempt") as get_attempt,
        ):
            service.get_retry_info(job)

        get_attempt_by_job.assert_not_called()
        get_attempt.assert_not_called()

    def test_bulk_retry_projection_hides_registration_retry_for_deactivated_root_attempt(self):
        job = self._failed_job()
        with (
            patch.object(service.db, "get_successful_retries_for_jobs", return_value={}),
            patch.object(service.db, "get_accounts_for_jobs", return_value={}),
            patch.object(
                registration_store,
                "get_attempts_for_root_jobs",
                return_value={80: {"target_status": "deactivated"}},
                create=True,
            ) as get_attempts,
        ):
            info = service.get_retry_info_bulk([job])[81]

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertIn("永久失效", info["retry_reason"])
        get_attempts.assert_called_once_with([80])

    def test_bulk_projection_skips_attempt_query_for_unlinked_light_jobs(self):
        job = self._failed_job()
        job.pop("attempt_id")
        with (
            patch.object(service.db, "get_successful_retries_for_jobs", return_value={}),
            patch.object(service.db, "get_accounts_for_jobs", return_value={}),
            patch.object(registration_store, "get_attempts_for_root_jobs", create=True) as get_attempts,
        ):
            service.get_retry_info_bulk([job])

        get_attempts.assert_not_called()

    def test_bulk_projection_fails_closed_when_attempt_query_raises(self):
        job = self._failed_job()
        with (
            patch.object(service.db, "get_successful_retries_for_jobs", return_value={}),
            patch.object(service.db, "get_accounts_for_jobs", return_value={}),
            patch.object(
                registration_store,
                "get_attempts_for_root_jobs",
                side_effect=RuntimeError("registration storage unavailable"),
                create=True,
            ),
        ):
            info = service.get_retry_info_bulk([job])[81]

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertIn("读取失败", info["retry_reason"])

    def test_single_retry_projection_fails_closed_when_linked_attempt_is_missing(self):
        job = self._failed_job()
        with (
            patch.object(service.db, "get_successful_retry_for_job", return_value=None),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(registration_store, "get_attempt", return_value=None),
        ):
            info = service.get_retry_info(job)

        self.assertFalse(info["retryable"])
        self.assertIsNone(info["retry_action"])
        self.assertIn("读取失败", info["retry_reason"])

    def test_retry_endpoint_rejects_deactivated_root_attempt_even_if_projection_is_stale(self):
        source = self._failed_job()
        source["attempt_id"] = 181
        root = {**source, "id": 80, "root_job_id": 80, "attempt_id": 180}
        retry_job = {"id": 82, "status": "pending", "job_type": "registration", "log_file": "/tmp/retry.log"}
        executor = Mock()
        with (
            patch.object(service.db, "get_job", side_effect=[source, root]),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(service, "_enrich_account_registration_state", return_value=None),
            patch.object(service, "get_retry_info", return_value={"retryable": True, "retry_action": "registration"}),
            patch.object(
                registration_store,
                "get_attempt",
                return_value={"target_status": "deactivated"},
            ) as get_attempt,
            patch.object(service.db, "create_retry_job", return_value=(retry_job, True)) as create_retry,
            patch.object(service, "get_executor", return_value=executor),
        ):
            result = service.retry_job(81)

        self.assertFalse(result["ok"])
        self.assertEqual(409, result["status"])
        self.assertIn("永久失效", result["error"])
        get_attempt.assert_called_once_with(180)
        create_retry.assert_not_called()
        executor.submit.assert_not_called()

    def test_retry_endpoint_rejects_attempt_read_error_even_if_projection_is_forced_retryable(self):
        source = self._failed_job()
        source["attempt_id"] = 181
        root = {**source, "id": 80, "root_job_id": 80, "attempt_id": 180}
        retry_job = {"id": 82, "status": "pending", "job_type": "registration", "log_file": "/tmp/retry.log"}
        executor = Mock()
        with (
            patch.object(service.db, "get_job", side_effect=[source, root]),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(service, "_enrich_account_registration_state", return_value=None),
            patch.object(service, "get_retry_info", return_value={"retryable": True, "retry_action": "registration"}),
            patch.object(
                registration_store,
                "get_attempt",
                side_effect=RuntimeError("registration storage unavailable"),
            ) as get_attempt,
            patch.object(service.db, "create_retry_job", return_value=(retry_job, True)) as create_retry,
            patch.object(service, "get_executor", return_value=executor),
        ):
            result = service.retry_job(81)

        self.assertFalse(result["ok"])
        self.assertEqual(409, result["status"])
        self.assertIn("读取失败", result["error"])
        self.assertIn("稍后重试", result["error"])
        get_attempt.assert_called_once_with(180)
        create_retry.assert_not_called()
        executor.submit.assert_not_called()

    def test_deactivated_attempt_without_account_keeps_local_state_none(self):
        previous = {
            name: getattr(service._THREAD_CTX, name, None)
            for name in ("attempt_id", "run_id", "job_id", "execution_id")
        }
        service._THREAD_CTX.attempt_id = 18
        service._THREAD_CTX.run_id = 19
        service._THREAD_CTX.job_id = 20
        service._THREAD_CTX.execution_id = "worker-20"
        try:
            with patch.object(registration_store, "advance_checkpoint") as advance:
                changed = service._mark_registration_attempt_deactivated(
                    None,
                    "账号已明确永久失效",
                    error_code="account_deactivated",
                )
        finally:
            for name, value in previous.items():
                if value is None:
                    try:
                        delattr(service._THREAD_CTX, name)
                    except AttributeError:
                        pass
                else:
                    setattr(service._THREAD_CTX, name, value)

        self.assertTrue(changed)
        self.assertEqual("none", advance.call_args.kwargs["local_account_state"])


if __name__ == "__main__":
    unittest.main()
