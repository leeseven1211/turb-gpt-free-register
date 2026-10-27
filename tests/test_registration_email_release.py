# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import registration_service as svc
from core import task_run_log


class RegistrationEmailReleaseTests(unittest.TestCase):
    def test_bind_registration_email_keeps_root_job_lease_on_retry(self):
        previous_attempt_id = getattr(svc._THREAD_CTX, "attempt_id", None)
        previous_job_id = getattr(svc._THREAD_CTX, "job_id", None)
        svc._THREAD_CTX.attempt_id = 8
        svc._THREAD_CTX.job_id = 12
        try:
            with patch("core.storage.registration.create_attempt") as create_attempt:
                svc.bind_registration_email(
                    "held@icloud.com",
                    email_source="icloud_hide",
                    root_job_id=5,
                )
        finally:
            svc._THREAD_CTX.attempt_id = previous_attempt_id
            svc._THREAD_CTX.job_id = previous_job_id

        create_attempt.assert_called_once_with(
            "held@icloud.com",
            email_source="icloud_hide",
            root_job_id=5,
            data={"email_lease_id": "root:5:held@icloud.com"},
        )

    def test_completed_resume_marks_email_used_again(self):
        with patch("core.email_provider.release_email", return_value="icloud_hide") as release:
            changed = svc._mark_completed_resume_email("alias@icloud.com", 347)

        self.assertTrue(changed)
        release.assert_called_once_with(
            "alias@icloud.com",
            status="used",
            note="继续注册已完成，已绑定账号 #347",
        )

    def test_completed_initial_registration_marks_email_used(self):
        with patch("core.email_provider.release_email", return_value="email_butler") as release:
            changed = svc._mark_completed_registration_email("alias@example.com", 348)

        self.assertTrue(changed)
        release.assert_called_once_with(
            "alias@example.com",
            status="used",
            note="注册已完成，已绑定账号 #348",
        )

    def test_completed_registration_uses_verified_task_source(self):
        with patch("core.email_provider.release_email", return_value="icloud_hide") as release:
            changed = svc._mark_completed_registration_email(
                "alias@icloud.com",
                348,
                source="icloud_hide",
            )

        self.assertTrue(changed)
        release.assert_called_once_with(
            "alias@icloud.com",
            status="used",
            note="注册已完成，已绑定账号 #348",
            source="icloud_hide",
        )

    def _run_job(self, result=None, error=None, stop_after_result=False, capture_job_updates=False):
        job = {
            "id": 1,
            "status": "pending",
            "email_source": "icloud_hide",
        }
        proxy = SimpleNamespace(
            provider="test",
            endpoint="127.0.0.1:8080",
            exit_ip="127.0.0.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://127.0.0.1:8080",
        )

        registration_returned = False

        def run_registration(**_kwargs):
            nonlocal registration_returned
            if error is not None:
                raise error
            registration_returned = True
            return result

        def is_stop_requested(_job_id=None):
            return bool(stop_after_result and registration_returned)

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job") as update_job, patch.object(
            svc.db, "update_job_progress"
        ) as update_progress, patch.object(
            svc.db, "finish_job_progress"
        ) as finish_progress, patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(
            svc.db, "update_account_registration_proxy"
        ), patch.object(
            svc, "is_stop_requested", side_effect=is_stop_requested
        ), patch.object(
            svc, "_prepare_registration_args", return_value=("alias@icloud.com", "Test", "1990-01-01")
        ), patch.object(
            svc, "_release_unconsumed_job_email"
        ) as release_email, patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ), patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", side_effect=run_registration
        ):
            svc._run_one_job(1, str(Path(td) / "job.log"))
        if capture_job_updates:
            return release_email, update_progress, finish_progress, update_job
        return release_email, update_progress, finish_progress

    def test_returned_failure_is_not_released_twice_by_service(self):
        release_email, _update_progress, _finish_progress = self._run_job(
            result={"success": False, "email": "alias@icloud.com", "error": "browser failed"}
        )
        release_email.assert_not_called()

    def test_failed_core_write_keeps_email_and_does_not_finish_as_success(self):
        with patch.object(svc, "_mark_registration_result") as mark_success, patch.object(
            svc, "_mark_completed_registration_email"
        ) as mark_email_used, patch.object(svc, "_retain_job_email") as retain:
            _release, _progress, finish_progress, update_job = self._run_job(
                capture_job_updates=True,
                result={
                    "success": False, "core_persisted": False,
                    "email": "alias@icloud.com", "account_id": 42,
                    "access_token": "memory-only-token", "error": "核心账号保存失败",
                },
            )
        mark_success.assert_not_called()
        mark_email_used.assert_not_called()
        retain.assert_called_once()
        self.assertFalse(finish_progress.call_args.kwargs["success"])
        statuses = [call.kwargs["status"] for call in update_job.call_args_list if "status" in call.kwargs]
        self.assertEqual(statuses[-1], "failed")

    def test_saved_account_with_unknown_remote_result_is_not_partial_success(self):
        with patch.object(svc, "_mark_registration_request_unknown") as mark_unknown, patch.object(
            svc, "_mark_registration_result"
        ) as mark_success:
            _release_email, _update_progress, _finish_progress, update_job = self._run_job(
                capture_job_updates=True,
                result={
                    "success": False,
                    "email": "alias@icloud.com",
                    "account_id": 42,
                    "access_token": "",
                    "request_unknown": True,
                    "register_response_confirmed": True,
                    "cause_code": "email_otp_no_mail",
                    "error_code": "request_unknown",
                    "error": "等待窗口内未收到验证码邮件：ForwardIMAPNoMailTimeout",
                },
            )

        self.assertTrue(any(
            call.kwargs.get("status") == "failed"
            for call in update_job.call_args_list
        ))
        self.assertFalse(any(
            call.kwargs.get("status") == "partial_success"
            for call in update_job.call_args_list
        ))
        mark_success.assert_not_called()
        self.assertTrue(mark_unknown.call_args.kwargs["facts"]["register_response_confirmed"])
        self.assertEqual("email_otp_no_mail", mark_unknown.call_args.kwargs["facts"]["cause_code"])

    def test_email_submission_timeout_does_not_write_password_checkpoint(self):
        with patch.object(svc, "_mark_registration_request_unknown") as mark_unknown:
            release, _, finish, update = self._run_job(
                capture_job_updates=True,
                result={"success": False, "email": "alias@icloud.com", "request_unknown": True,
                        "email_submission_unconfirmed": True, "error": "邮箱提交超时"},
            )
        mark_unknown.assert_not_called()
        release.assert_not_called()
        finish.assert_called_with(1, success=False, detail="request_unknown: 邮箱提交超时")
        self.assertTrue(any(call.kwargs.get("status") == "failed" for call in update.call_args_list))

    def test_returned_success_closes_initial_registration_email(self):
        with patch("core.email_provider.release_email", return_value="icloud_hide") as release:
            self._run_job(
                result={
                    "success": True,
                    "registration_success": True,
                    "postprocess_success": True,
                    "email": "alias@icloud.com",
                    "account_id": 42,
                    "access_token": "token",
                }
            )

        release.assert_called_once_with(
            "alias@icloud.com",
            status="used",
            note="注册已完成，已绑定账号 #42",
            source="icloud_hide",
        )

    def test_confirmed_codex_deactivation_marks_original_source_failed_not_used(self):
        with (
            patch("core.email_provider.mark_email_permanently_unusable") as mark_unusable,
            patch("core.email_provider.release_email") as release_email,
            patch.object(svc, "_retain_job_email") as retain_email,
            patch.object(svc, "_mark_registration_attempt_deactivated") as mark_attempt,
        ):
            self._run_job(
                result={
                    "success": True,
                    "registration_success": True,
                    "postprocess_success": False,
                    "partial_success": True,
                    "email": "alias@icloud.com",
                    "account_id": 42,
                    "access_token": "token",
                    "codex": {
                        "status": "deactivated",
                        "email_permanently_unusable": True,
                        "account_unusable_error_code": "account_deactivated",
                        "message": "账号已废（account_deactivated）",
                    },
                    "error": "Codex 未完成: 账号已废（account_deactivated）",
                }
            )

        mark_unusable.assert_called_once_with(
            "alias@icloud.com",
            source="icloud_hide",
            note="上游明确确认账号永久失效: 账号已废（account_deactivated）",
        )
        release_email.assert_not_called()
        retain_email.assert_not_called()
        mark_attempt.assert_called_once_with(
            42,
            "账号已废（account_deactivated）",
            error_code="account_deactivated",
        )

    def test_stop_after_explicit_deactivation_does_not_skip_terminal_state(self):
        with (
            patch("core.email_provider.mark_email_permanently_unusable") as mark_unusable,
            patch.object(svc, "_mark_registration_attempt_deactivated") as mark_attempt,
        ):
            _release_email, _update_progress, _finish_progress, update_job = self._run_job(
                stop_after_result=True,
                capture_job_updates=True,
                result={
                    "success": True,
                    "registration_success": True,
                    "postprocess_success": False,
                    "partial_success": True,
                    "email": "alias@icloud.com",
                    "account_id": 42,
                    "access_token": "token",
                    "codex": {
                        "status": "deactivated",
                        "email_permanently_unusable": True,
                        "account_unusable_error_code": "account_deactivated",
                        "message": "账号已废（account_deactivated）",
                    },
                },
            )

        mark_unusable.assert_called_once()
        mark_attempt.assert_called_once()
        self.assertTrue(any(
            (call.kwargs.get("status") or (call.args[1] if len(call.args) > 1 else None)) == "failed"
            for call in update_job.call_args_list
        ))
        self.assertFalse(any(
            (call.kwargs.get("status") or (call.args[1] if len(call.args) > 1 else None)) == "stopped"
            for call in update_job.call_args_list
        ))

    def test_confirmed_deactivation_marks_attempt_and_account_terminal(self):
        previous = {
            name: getattr(svc._THREAD_CTX, name, None)
            for name in ("attempt_id", "run_id", "job_id", "execution_id")
        }
        svc._THREAD_CTX.attempt_id = 18
        svc._THREAD_CTX.run_id = 19
        svc._THREAD_CTX.job_id = 20
        svc._THREAD_CTX.execution_id = "worker-20"
        try:
            with patch("core.storage.registration.advance_checkpoint") as advance, patch.object(
                svc.db, "mark_account_deactivated", return_value=True
            ) as mark_account:
                changed = svc._mark_registration_attempt_deactivated(
                    42,
                    "账号已明确永久失效",
                    error_code="account_deactivated",
                )
        finally:
            for name, value in previous.items():
                if value is None:
                    try:
                        delattr(svc._THREAD_CTX, name)
                    except AttributeError:
                        pass
                else:
                    setattr(svc._THREAD_CTX, name, value)

        self.assertTrue(changed)
        advance.assert_called_once_with(
            18,
            "failed",
            run_id=19,
            job_id=20,
            execution_id="worker-20",
            event_type="account_deactivated",
            level="WARNING",
            message="账号已明确永久失效",
            detail={"account_unusable_error_code": "account_deactivated"},
            remote_identity_state="confirmed",
            remote_account_state="confirmed",
            local_account_state="persisted",
            target_status="deactivated",
        )
        mark_account.assert_called_once_with(
            42,
            "账号已明确永久失效",
            source="registration_postprocess",
        )

    def test_unhandled_registration_exception_retains_original_email(self):
        with patch.object(svc, "_retain_job_email") as retain_email:
            release_email, _update_progress, _finish_progress = self._run_job(
                error=RuntimeError("unexpected crash")
            )

        retain_email.assert_called_once()
        release_email.assert_not_called()

    def test_intermediate_failure_does_not_automatically_disable_email(self):
        with patch("core.email_provider.release_email") as release_email:
            self._run_job(error=RuntimeError("auth.openai.com/log-in/password"))

        release_email.assert_not_called()

    def test_normal_registration_retry_preserves_source_email(self):
        source = {
            "id": 31,
            "status": "failed",
            "job_type": "registration",
            "batch_id": "original-batch",
            "batch_index": 3,
            "batch_size": 10,
            "batch_workers": 4,
            "email_source": "icloud_hide",
            "email": "held@icloud.com",
        }
        retry_job = {
            "id": 32,
            "status": "pending",
            "job_type": "registration",
            "batch_id": "original-batch",
            "batch_index": 3,
            "batch_size": 10,
            "batch_workers": 4,
            "log_file": "/tmp/retry.log",
        }
        executor = Mock()

        with patch.object(svc.db, "get_job", return_value=source), patch.object(
            svc, "get_retry_info", return_value={"retryable": True, "retry_action": "registration"}
        ), patch.object(svc, "_account_for_job", return_value=None), patch.object(
            svc.db, "create_retry_job", return_value=(retry_job, True)
        ) as create_retry, patch.object(svc, "get_executor", return_value=executor):
            result = svc.retry_job(31)

        self.assertTrue(result["ok"])
        self.assertEqual(create_retry.call_args.kwargs["job_type"], "registration")
        self.assertEqual(create_retry.call_args.kwargs["email"], "held@icloud.com")
        self.assertIsNone(create_retry.call_args.kwargs["account_id"])
        executor.submit.assert_called_once_with(svc._run_one_job, 32, "/tmp/retry.log")

    def test_normal_registration_retry_uses_root_email_source(self):
        source = {
            "id": 32,
            "root_job_id": 31,
            "status": "failed",
            "job_type": "registration",
            "email_source": "",
            "email": "changed@icloud.com",
        }
        root = {
            "id": 31,
            "status": "failed",
            "job_type": "registration",
            "email_source": "icloud_hide",
            "email": "held@icloud.com",
        }
        retry_job = {"id": 33, "status": "pending", "job_type": "registration", "log_file": "/tmp/retry.log"}
        executor = Mock()

        with patch.object(svc.db, "get_job", side_effect=[source, root]), patch.object(
            svc, "get_retry_info", return_value={"retryable": True, "retry_action": "registration"}
        ), patch.object(svc, "_account_for_job", return_value=None), patch.object(
            svc.db, "create_retry_job", return_value=(retry_job, True)
        ) as create_retry, patch.object(svc, "get_executor", return_value=executor):
            result = svc.retry_job(32)

        self.assertTrue(result["ok"])
        self.assertEqual(create_retry.call_args.kwargs["email_source"], "icloud_hide")
        self.assertEqual(create_retry.call_args.kwargs["email"], "held@icloud.com")

    def test_normal_registration_retry_without_root_email_source_is_rejected(self):
        source = {
            "id": 32,
            "root_job_id": 31,
            "status": "failed",
            "job_type": "registration",
            "email_source": "icloud_hide",
            "email": "held@icloud.com",
        }
        root = {
            "id": 31,
            "status": "failed",
            "job_type": "registration",
            "email_source": "",
            "email": "held@icloud.com",
        }

        with patch.object(svc.db, "get_job", side_effect=[source, root]), patch.object(
            svc, "get_retry_info", return_value={"retryable": True, "retry_action": "registration"}
        ), patch.object(svc, "_account_for_job", return_value=None), patch.object(
            svc.db, "create_retry_job"
        ) as create_retry:
            result = svc.retry_job(32)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 409)
        self.assertIn("原邮箱来源", result["error"])
        create_retry.assert_not_called()

    def test_normal_registration_retry_without_original_email_reacquires_email(self):
        source = {
            "id": 31,
            "status": "failed",
            "job_type": "registration",
            "batch_id": "original-batch",
            "batch_index": 3,
            "batch_size": 10,
            "batch_workers": 4,
            "email_source": "icloud_hide",
        }
        retry_row = {
            "id": 32,
            "status": "pending",
            "job_type": "registration",
            "batch_id": "original-batch",
            "batch_index": 3,
            "batch_size": 10,
            "batch_workers": 4,
            "log_file": "/tmp/retry.log",
        }
        executor = Mock()

        with patch.object(svc.db, "get_job", return_value=source), patch.object(
            svc, "get_retry_info", return_value={"retryable": True, "retry_action": "registration"}
        ), patch.object(svc, "_account_for_job", return_value=None), patch.object(
            svc.db, "create_retry_job", return_value=(retry_row, True)
        ) as create_retry, patch.object(svc, "get_executor", return_value=executor):
            result = svc.retry_job(31)

        self.assertTrue(result["ok"])
        self.assertIsNone(create_retry.call_args.kwargs["email"])
        executor.submit.assert_called_once_with(svc._run_one_job, 32, "/tmp/retry.log")

    def test_retry_child_reuses_stored_email_without_acquiring_another(self):
        job = {
            "id": 2,
            "status": "pending",
            "email_source": "icloud_hide",
            "job_type": "registration",
            "parent_job_id": 1,
            "root_job_id": 1,
            "email": "held@icloud.com",
        }
        proxy = SimpleNamespace(
            provider="test",
            endpoint="127.0.0.1:8080",
            exit_ip="127.0.0.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://127.0.0.1:8080",
        )
        result = {
            "success": True,
            "registration_success": True,
            "postprocess_success": True,
            "email": "held@icloud.com",
            "account_id": 42,
            "access_token": "token",
        }

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ), patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch.object(
            svc, "_account_for_job", return_value=None
        ), patch(
            "core.email_provider.restore_email_context", return_value="icloud_hide"
        ) as restore_email, patch.object(
            svc, "_prepare_registration_args", return_value=("new@icloud.com", "Test", "1990-01-01")
        ) as prepare_args, patch.object(
            svc, "_mark_completed_registration_email", return_value=True
        ), patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ), patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", return_value=result
        ) as run_registration:
            svc._run_one_job(2, str(Path(td) / "job.log"))

        prepare_args.assert_not_called()
        restore_email.assert_called_once_with(
            "held@icloud.com",
            source="icloud_hide",
            purpose="registration_retry",
        )
        self.assertEqual(run_registration.call_args.kwargs["email"], "held@icloud.com")
        self.assertEqual(run_registration.call_args.kwargs["email_source"], "icloud_hide")

    def test_retry_child_without_email_acquires_a_new_email(self):
        job = {
            "id": 2,
            "status": "pending",
            "email_source": "icloud_hide",
            "job_type": "registration",
            "parent_job_id": 1,
            "root_job_id": 1,
            "batch_id": "original-batch",
            "email": None,
        }
        proxy = SimpleNamespace(
            provider="test",
            endpoint="127.0.0.1:8080",
            exit_ip="127.0.0.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://127.0.0.1:8080",
        )
        result = {
            "success": True,
            "registration_success": True,
            "postprocess_success": True,
            "email": "new@icloud.com",
            "account_id": 42,
            "access_token": "token",
        }

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ), patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch.object(
            svc, "_account_for_job", return_value=None
        ), patch.object(
            svc, "_prepare_registration_args", return_value=("new@icloud.com", "Test", "1990-01-01")
        ) as prepare_args, patch(
            "core.email_provider.restore_email_context"
        ) as restore_email, patch.object(
            svc, "_mark_completed_registration_email", return_value=True
        ), patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ), patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", return_value=result
        ) as run_registration:
            svc._run_one_job(2, str(Path(td) / "job.log"))

        prepare_args.assert_called_once_with(
            "icloud_hide", batch_id="original-batch", job_id=2,
            owner_kind="registration_root", owner_id=1, acquisition_id="registration:1",
        )
        restore_email.assert_not_called()
        self.assertEqual(run_registration.call_args.kwargs["email"], "new@icloud.com")

    def test_retry_child_with_source_different_from_root_is_rejected_before_restore(self):
        child = {
            "id": 2,
            "status": "pending",
            "email_source": "outlook",
            "job_type": "registration",
            "parent_job_id": 1,
            "root_job_id": 1,
            "email": "held@icloud.com",
        }
        root = {
            "id": 1,
            "status": "failed",
            "email_source": "icloud_hide",
            "job_type": "registration",
            "email": "held@icloud.com",
        }
        proxy = SimpleNamespace(
            provider="test",
            endpoint="127.0.0.1:8080",
            exit_ip="127.0.0.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://127.0.0.1:8080",
        )

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", side_effect=lambda candidate_id: root if candidate_id == 1 else child
        ), patch.object(svc.db, "update_job") as update_job, patch.object(
            svc.db, "update_job_progress"
        ), patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch.object(
            svc, "_prepare_registration_args"
        ) as prepare_args, patch(
            "core.email_provider.restore_email_context"
        ) as restore_email, patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ), patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration"
        ) as run_registration:
            svc._run_one_job(2, str(Path(td) / "job.log"))

        prepare_args.assert_not_called()
        restore_email.assert_not_called()
        run_registration.assert_not_called()
        self.assertTrue(
            any("邮箱来源与根任务不一致" in str(call.kwargs.get("error") or "") for call in update_job.call_args_list)
        )

    def test_retry_child_with_lost_temporary_context_fails_without_acquiring_another(self):
        job = {
            "id": 2,
            "status": "pending",
            "email_source": "gptmail",
            "job_type": "registration",
            "parent_job_id": 1,
            "root_job_id": 1,
            "email": "held@gptmail.test",
        }
        proxy = SimpleNamespace(
            provider="test",
            endpoint="127.0.0.1:8080",
            exit_ip="127.0.0.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://127.0.0.1:8080",
        )

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job") as update_job, patch.object(
            svc.db, "update_job_progress"
        ), patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch.object(
            svc, "_account_for_job", return_value=None
        ), patch(
            "core.email_provider.restore_email_context",
            side_effect=RuntimeError("原 GPTMail 上下文不可恢复，不能改用其他邮箱重跑"),
        ) as restore_email, patch.object(
            svc, "_prepare_registration_args"
        ) as prepare_args, patch.object(
            svc, "_retain_job_email"
        ) as retain_email, patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ), patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration"
        ) as run_registration:
            svc._run_one_job(2, str(Path(td) / "job.log"))

        restore_email.assert_called_once_with(
            "held@gptmail.test",
            source="gptmail",
            purpose="registration_retry",
        )
        prepare_args.assert_not_called()
        run_registration.assert_not_called()
        retain_email.assert_called_once()
        self.assertTrue(
            any("不能改用其他邮箱重跑" in str(call.kwargs.get("error") or "") for call in update_job.call_args_list)
        )

    def test_retry_child_with_ambiguous_source_fails_without_switching_source(self):
        job = {
            "id": 2,
            "status": "pending",
            "email_source": "icloud_hide,outlook",
            "job_type": "registration",
            "parent_job_id": 1,
            "root_job_id": 1,
            "email": "held@icloud.com",
        }
        proxy = SimpleNamespace(
            provider="test",
            endpoint="127.0.0.1:8080",
            exit_ip="127.0.0.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://127.0.0.1:8080",
        )

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job") as update_job, patch.object(
            svc.db, "update_job_progress"
        ), patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(
            svc, "_prepare_registration_args"
        ) as prepare_args, patch.object(
            svc, "_retain_job_email"
        ), patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ), patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration"
        ) as run_registration:
            svc._run_one_job(2, str(Path(td) / "job.log"))

        prepare_args.assert_not_called()
        run_registration.assert_not_called()
        self.assertTrue(
            any("原邮箱来源不明确" in str(call.kwargs.get("error") or "") for call in update_job.call_args_list)
        )

    def test_saved_pending_account_fails_current_stage_before_skipping_rest(self):
        _release_email, update_progress, finish_progress = self._run_job(
            result={
                "success": False,
                "registration_pending": True,
                "email": "alias@icloud.com",
                "account_id": 42,
                "access_token": "",
                "error": "验证码等待超时",
            }
        )

        matching = [
            call for call in update_progress.call_args_list
            if call.args[:2] == (1, "email_otp")
            and call.kwargs.get("state") == "failed"
            and call.kwargs.get("detail") == "验证码等待超时"
        ]
        self.assertEqual(len(matching), 1)
        failed_call = matching[0]
        self.assertEqual(failed_call.kwargs.get("route_attempt_no"), 1)
        self.assertTrue(failed_call.kwargs.get("step_instance_id"))
        # 兼容旧任务没有 operation run 的情况，但字段必须保留在事件中。
        self.assertIn("operation_run_id", failed_call.kwargs)
        finish_progress.assert_called_with(1, success=False, detail="验证码等待超时")

    def test_transient_proxy_failure_reuses_original_email_on_new_route(self):
        job = {
            "id": 1,
            "status": "pending",
            "email_source": "icloud_hide",
        }
        proxy1 = SimpleNamespace(
            provider="1024proxy",
            endpoint="1.1.1.1:8080",
            exit_ip="1.1.1.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://1.1.1.1:8080",
        )
        proxy2 = SimpleNamespace(
            provider="1024proxy",
            endpoint="2.2.2.2:8080",
            exit_ip="2.2.2.2",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:01"),
            expires_at=None,
            proxy_url="http://2.2.2.2:8080",
        )
        transient = {
            "success": False,
            "email": "alias@icloud.com",
            "error": "RuntimeError: 邮箱提交/认证跳转超过总预算 60 秒，ERR_TUNNEL_CONNECTION_FAILED",
        }
        success = {
            "success": True,
            "registration_success": True,
            "postprocess_success": True,
            "email": "alias@icloud.com",
            "account_id": 42,
            "access_token": "token",
        }

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ) as update_progress, patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "begin_job_route_attempt"
        ) as begin_route_attempt, patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch.object(
            svc, "_prepare_registration_args", return_value=("alias@icloud.com", "Test", "1990-01-01")
        ) as prepare_args, patch.object(
            svc, "_registration_proxy_retry_limit", return_value=1), patch.object(
            svc, "_registration_proxy_retry_delay", return_value=0
        ), patch(
            "core.proxy_provider.acquire_registration_proxy", side_effect=[proxy1, proxy2]
        ) as acquire_proxy, patch(
            "core.proxy_provider.release_proxy"
        ) as release_proxy, patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", side_effect=[transient, success]
        ) as run_registration:
            svc._run_one_job(1, str(Path(td) / "job.log"))

        self.assertEqual(run_registration.call_count, 2)
        begin_route_attempt.assert_called_once()
        self.assertEqual(acquire_proxy.call_count, 2)
        self.assertEqual(prepare_args.call_count, 1)
        self.assertEqual(
            [call.kwargs["email"] for call in run_registration.call_args_list],
            ["alias@icloud.com", "alias@icloud.com"],
        )
        self.assertEqual(
            [call.kwargs["email_source"] for call in run_registration.call_args_list],
            ["icloud_hide", "icloud_hide"],
        )
        self.assertNotIn("batch_id", acquire_proxy.call_args_list[1].kwargs)
        release_proxy.assert_any_call(proxy1, reason="registration_proxy_retry_1", fault=False)
        release_proxy.assert_any_call(proxy2, reason="pending")
        stage_transitions = [
            (call.args[1], call.kwargs.get("state"))
            for call in update_progress.call_args_list
        ]
        self.assertEqual(stage_transitions, [
            ("network", "running"),
            ("network", "success"),
            ("email", "running"),
            ("email", "success"),
            ("network", "running"),
            ("network", "success"),
            ("email", "running"),
            ("email", "success"),
        ])

    def test_proxy_acquisition_failure_is_returned_without_outer_retry(self):
        acquire_proxy = unittest.mock.Mock(
            side_effect=RuntimeError("代理池暂时没有符合要求的可用线路")
        )
        with patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ) as update_progress, patch.object(
            svc.db, "begin_job_route_attempt"
        ) as begin_route_attempt, patch.object(
            svc, "_registration_proxy_retry_limit", return_value=1
        ), patch.object(
            svc, "_registration_proxy_retry_delay", return_value=0
        ), patch.object(
            svc, "check_stop_requested"
        ), patch.object(svc.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "代理池"):
                svc._acquire_registration_proxy_with_retries(
                    acquire_proxy=acquire_proxy,
                    job_id=17,
                    batch_id=None,
                    batch_size=1,
                    batch_workers=1,
                    progress_callback=None,
                    log_logger=svc.logger,
                )

        self.assertEqual(acquire_proxy.call_count, 1)
        begin_route_attempt.assert_not_called()
        update_progress.assert_not_called()

    def test_manual_registration_retry_uses_independent_proxy_allocation(self):
        job = {
            "id": 2,
            "status": "pending",
            "job_type": "registration",
            "parent_job_id": 1,
            "root_job_id": 1,
            "batch_id": "source-batch",
            "batch_index": 3,
            "batch_size": 5,
            "batch_workers": 5,
            "email_source": "icloud_hide",
            "email": "alias@icloud.com",
        }
        proxy = SimpleNamespace(
            provider="1024proxy",
            endpoint="2.2.2.2:8080",
            exit_ip="2.2.2.2",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://2.2.2.2:8080",
        )
        result = {
            "success": True,
            "registration_success": True,
            "postprocess_success": True,
            "email": "alias@icloud.com",
            "account_id": 42,
            "access_token": "token",
        }

        with tempfile.TemporaryDirectory() as td, patch.object(
            task_run_log, "_LOG_ROOT", Path(td)
        ), patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ), patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch(
            "core.email_provider.restore_email_context", return_value="icloud_hide"
        ) as restore_email, patch.object(
            svc, "_prepare_registration_args", return_value=("alias@icloud.com", "Test", "1990-01-01")
        ) as prepare_args, patch.object(svc, "_retain_job_email"), patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ) as acquire_proxy, patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.finalize_registration_proxy_batch"
        ) as finalize_batch, patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", return_value=result
        ):
            svc._run_one_job(2, str(Path(td) / "job.log"))

        acquire_proxy.assert_called_once()
        acquire_kwargs = acquire_proxy.call_args.kwargs
        self.assertNotIn("batch_id", acquire_kwargs)
        self.assertEqual(acquire_kwargs["job_id"], 2)
        self.assertEqual(acquire_kwargs["registration_job_id"], 2)
        finalize_batch.assert_not_called()
        prepare_args.assert_not_called()
        restore_email.assert_called_once_with(
            "alias@icloud.com",
            source="icloud_hide",
            purpose="registration_retry",
        )


if __name__ == "__main__":
    unittest.main()
