"""Remail 下单结果不明时，任务必须保留核验状态并阻止重复付费。"""
from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import email_change_service, registration_service
from core.remail_client import RemailError, RemailOrderUncertain


class RemailRegistrationReconciliationTests(unittest.TestCase):
    def _run_allocation_failure(self, error, *, stopped=False):
        service = registration_service
        job = {"id": 9, "status": "pending", "email_source": "remail", "email": ""}
        proxy = SimpleNamespace(
            provider="test", endpoint="127.0.0.1:8080", exit_ip="127.0.0.1", region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **kwargs: "2026-10-10T00:00:00"),
            expires_at=None,
        )

        def update_job(_job_id, **changes):
            job.update(changes)

        with ExitStack() as stack:
            for name in ("_activate_job", "_deactivate_job", "_ensure_registration_run_context", "_retain_job_email"):
                stack.enter_context(patch.object(service, name))
            stack.enter_context(patch.object(service, "_registration_proxy_correlation", return_value={}))
            stack.enter_context(patch.object(service, "_JobLogContext", return_value=nullcontext()))
            stack.enter_context(patch.object(service, "_acquire_registration_proxy_with_retries", return_value=proxy))
            stack.enter_context(patch.object(service, "_account_for_job", return_value=None))
            stack.enter_context(patch.object(service, "is_stop_requested", return_value=stopped))
            stack.enter_context(patch.object(service.db, "get_job", return_value=job))
            stack.enter_context(patch.object(service.db, "update_job", side_effect=update_job))
            stack.enter_context(patch.object(service.db, "claim_job_for_execution", return_value=True))
            stack.enter_context(patch.object(service.db, "update_job_progress"))
            stack.enter_context(patch.object(service.db, "finish_job_progress"))
            stack.enter_context(patch("core.proxy_provider.release_proxy"))
            stack.enter_context(patch("core.registration_debug.capture_current_failure"))
            allocate = stack.enter_context(patch.object(service, "_prepare_registration_args", side_effect=error))
            run = stack.enter_context(patch("core.registration.dispatcher.run_registration"))
            finish = stack.enter_context(patch.object(service, "_finish_registration_run"))
            mark_identity = stack.enter_context(patch.object(service, "_mark_registration_request_unknown"))
            service._run_one_job(9, "/unused-test-log")

        allocate.assert_called_once()
        run.assert_not_called()
        mark_identity.assert_not_called()
        return job, finish

    def test_uncertain_order_is_not_downgraded_to_failure_or_user_stop(self):
        for stopped in (False, True):
            with self.subTest(stopped=stopped):
                job, finish = self._run_allocation_failure(
                    RemailOrderUncertain("订单交付超时"), stopped=stopped,
                )
                self.assertEqual(job["status"], "request_unknown")
                self.assertEqual(job["email"], "")
                self.assertIn("禁止直接重试下单", job["error"])
                self.assertEqual(finish.call_args.args[0], "request_unknown")
                self.assertEqual(
                    finish.call_args.kwargs["result_summary"]["cause_code"],
                    "remail_order_request_unknown",
                )

    def test_explicit_allocation_rejection_keeps_normal_failure_behavior(self):
        job, finish = self._run_allocation_failure(RemailError("Remail 请求参数无效 (HTTP 400)"))
        self.assertEqual(job["status"], "failed")
        self.assertEqual(finish.call_args.args[0], "failed")

    def test_uncertain_order_blocks_registration_retry_projection_and_endpoint(self):
        service = registration_service
        job = {"id": 9, "status": "request_unknown", "email_source": "remail", "email": ""}
        with (
            patch.object(service.db, "get_job", return_value=job),
            patch.object(service.db, "get_successful_retry_for_job", return_value=None),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(service, "_enrich_account_registration_state", return_value=None),
            patch.object(service, "_read_linked_attempt_for_job", return_value=(None, False)),
            patch.object(service.db, "create_retry_job") as create_retry,
            patch.object(service, "get_executor") as executor,
        ):
            info = service.get_retry_info(job)
            result = service.retry_job(9)

        self.assertFalse(info["retryable"])
        self.assertEqual(info["next_actions"], [])
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 409)
        create_retry.assert_not_called()
        executor.assert_not_called()


class RemailEmailChangeReconciliationTests(unittest.TestCase):
    def _run_allocation_failure(self, error):
        service = email_change_service
        account = {"id": 7, "email": "old@example.test", "email_source": "outlook", "access_token": "fixture-at"}
        context = Mock(
            account_id=7, email=account["email"], run_id=31, task_id=32,
            run={"data": {"email_source": "remail"}, "trigger": "test"},
            config_snapshot={"email_change_enabled": True},
        )
        context.lease.return_value = nullcontext()
        with (
            patch.object(service.db, "get_account", return_value=account),
            patch("core.browser_traffic.record_unavailable"),
            patch.object(service.db, "claim_account_email_change", return_value=True),
            patch.object(service.email_provider, "acquire_email", side_effect=error) as allocate,
            patch.object(service.db, "finish_account_email_change", return_value=True) as finish,
            patch.object(service, "acquire_account_proxy") as acquire_proxy,
            patch.object(service, "begin_change_with_optional_reauth") as begin,
            patch.object(service, "_release_unconsumed") as release,
        ):
            result = service._handle_email_change(context)

        allocate.assert_called_once_with("remail")
        acquire_proxy.assert_not_called()
        begin.assert_not_called()
        release.assert_not_called()
        return result, finish, account

    def test_uncertain_order_blocks_email_change_and_subsequent_submission(self):
        result, finish, account = self._run_allocation_failure(RemailOrderUncertain("订单交付超时"))
        self.assertEqual(result.status, "request_unknown")
        self.assertEqual(result.summary["cause_code"], "remail_order_request_unknown")
        self.assertEqual(finish.call_args.kwargs["outcome"], "request_unknown")
        self.assertIsNone(finish.call_args.kwargs["new_email"])

        account["email_change_status"] = finish.call_args.kwargs["outcome"]
        with (
            patch.object(email_change_service.db, "get_account", return_value=account),
            patch.object(email_change_service, "_account_age_gate_error", return_value=None),
            patch("core.feature_availability.require_email_source", return_value=(True, "")),
            patch.object(email_change_service, "register_operation_handlers") as register,
        ):
            submission = email_change_service.submit_email_change(7, source="remail")
        self.assertFalse(submission["accepted"])
        self.assertTrue(submission["reconcile_required"])
        register.assert_not_called()

    def test_explicit_order_rejection_keeps_normal_email_change_failure(self):
        result, finish, _account = self._run_allocation_failure(RemailError("Remail 请求参数无效 (HTTP 400)"))
        self.assertEqual(result.status, "failed")
        self.assertNotIn("outcome", finish.call_args.kwargs)
