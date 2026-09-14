"""Shared auth cancellation/result contracts without remote browser work."""
from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from core.auth_challenge import AuthErrorCode, StepResult
from core import codex_retry_service, roxy_codex_oauth
from core.registration.auth_context import AuthExecutionContext, CancellationRequested
from core.registration import roxy as roxy_registration
from core.registration.state_machine import StageBudget, StageTimeout


class AuthExecutionContextTests(TestCase):
    def test_dispatched_action_without_response_is_request_unknown(self):
        result = StepResult(
            stage="password",
            ok=False,
            code=AuthErrorCode.NETWORK_ERROR,
            action_dispatched=True,
            remote_response_received=False,
            evidence={"url": "https://chatgpt.com/auth/callback?code=secret", "password": "secret"},
        )

        self.assertEqual(AuthErrorCode.REQUEST_UNKNOWN.value, result.code)
        self.assertFalse(result.ok)
        self.assertEqual("manual_reconcile", result.next_action)
        self.assertFalse(result.retryable)
        self.assertNotIn("password", result.as_dict()["evidence"])
        self.assertEqual("/auth/callback", result.as_dict()["evidence"]["url_path"])

    def test_context_combines_budget_and_cancellation_without_service_import(self):
        now = [100.0]
        budget = StageBudget.start(5, clock=lambda: now[0])
        context = AuthExecutionContext(budget=budget, cancellation=lambda: False)
        self.assertEqual(5.0, context.remaining())

        now[0] = 106.0
        with self.assertRaises(StageTimeout):
            context.checkpoint()

        cancelled_budget = StageBudget.start(5, cancellation=lambda: True)
        with self.assertRaises(CancellationRequested):
            cancelled_budget.require()

        cancelled = AuthExecutionContext(cancellation=lambda: True)
        with self.assertRaises(CancellationRequested):
            cancelled.checkpoint()

    def test_application_specific_cancellation_errors_are_injected_at_boundary(self):
        context = AuthExecutionContext(
            cancellation=lambda: True,
            cancellation_error=lambda: RuntimeError("registration-stop"),
        )
        with self.assertRaisesRegex(RuntimeError, "registration-stop"):
            context.checkpoint()

        from core.registration_service import StopRequested

        with patch("core.registration_service.is_stop_requested", return_value=True):
            with self.assertRaises(StopRequested):
                roxy_registration._call_shared_capability("_log_prefix", object())

        with patch.object(roxy_codex_oauth, "current_token", return_value=None):
            self.assertIsNone(roxy_codex_oauth._auth_execution_context())
        with patch.object(codex_retry_service, "is_stop_requested", return_value=True):
            retry_context = codex_retry_service._auth_execution_context("a@example.com")
            with self.assertRaises(codex_retry_service.CodexRetryStopped):
                retry_context.checkpoint()
