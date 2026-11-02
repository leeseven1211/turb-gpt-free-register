# -*- coding: utf-8 -*-
import logging
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from core.codex.roxy import oauth as roxy_codex_oauth
from core.codex import retry_service
from core.operations import progress as task_progress
from core.registration import roxy as roxy_registration
from webui import runtime


class AccountChangeActionTests(unittest.TestCase):
    def test_manual_worker_reuses_private_session_and_requires_confirmation(self):
        from core.auth.browser import password_recovery

        for confirmed in (False, True):
            with self.subTest(confirmed=confirmed):
                session = SimpleNamespace(resume=Mock(return_value=True), checkpoint=SimpleNamespace(state="unknown"))
                route = Mock(proxy_url="http://proxy.example", provider="unit", region="JP", mode="pool")
                route.public_dict.return_value = {"network_route": "proxy"}
                def browser_action(_email, **kwargs):
                    self.assertIs(session, kwargs["password_recovery"])
                    if confirmed:
                        session.checkpoint = SimpleNamespace(state="confirmed", password="private-candidate")
                with (
                    tempfile.TemporaryDirectory() as directory,
                    patch.object(retry_service.db, "get_account_by_email", return_value={
                        "id": 17, "email": "account@example.com", "extra_json": {"account_password": "original-password"},
                    }),
                    patch.object(retry_service.db, "update_account_login_password") as legacy_write,
                    patch.object(retry_service.account_task_store, "get_task", return_value={}),
                    patch.object(retry_service.account_task_store, "append_event"),
                    patch.object(retry_service, "check_stop_requested"),
                    patch("config.reload_all"),
                    patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
                    patch.object(password_recovery, "PasswordRecoverySession", return_value=session) as factory,
                    patch.object(roxy_codex_oauth, "run_roxy_chatgpt_account_action", side_effect=browser_action),
                ):
                    result = retry_service.run_twofa_worker(
                        "account@example.com", target_log_path=Path(directory) / "action.log", task_id=0,
                        steps={"password"}, manage_task=False, clear_log=False, force_password_reset=True,
                        execution_fence={"run_id": 702, "execution_id": "current-worker", "lease_token": "current-lease"},
                    )
                self.assertEqual(confirmed, result["ok"])
                self.assertEqual("current-lease", factory.call_args.kwargs["operation_lease_token"])
                session.resume.assert_called_once()
                legacy_write.assert_not_called()

    def test_manual_recovery_owner_requires_current_operation_lease(self):
        fence = {"run_id": 702, "execution_id": "current-worker", "lease_token": "current-lease"}
        owner = retry_service._manual_password_recovery_owner("account@example.com", 17, fence)
        self.assertEqual({
            "email": "account@example.com", "account_id": 17, "purpose": "manual",
            "operation_run_id": 702, "operation_execution_id": "current-worker",
            "operation_lease_token": "current-lease", "attempt_id": None,
            "registration_run_id": None, "registration_execution_id": None,
        }, owner)
        with self.assertRaisesRegex(RuntimeError, "password_recovery_owner_missing"):
            retry_service._manual_password_recovery_owner(
                "account@example.com", 17, {"run_id": 702, "execution_id": "current-worker"},
            )

    def test_manual_change_handler_passes_real_execution_fence_to_worker(self):
        fence = {"run_id": 702, "execution_id": "current-worker", "lease_token": "current-lease"}
        context = SimpleNamespace(
            run={"data": {"steps": ["password"]}}, task_type="password_change", config_snapshot={},
            account_id=17, task_id=701, run_id=702, email="account@example.com",
            report=Mock(), finished=False, last_result=None, execution_fence=fence,
            lease=Mock(return_value=nullcontext()), remote_request_started=Mock(),
            remote_request_receipt=Mock(), finish=Mock(),
        )
        with (
            patch.object(runtime, "_completion_settings_from_snapshot", return_value={}),
            patch.object(runtime.codex_retry_service, "run_twofa_worker", return_value={
                "ok": True, "status": "success",
            }) as worker,
            patch.object(runtime, "_account_setup_receipt", return_value=("confirmed", {})),
        ):
            result = runtime._handle_native_account_setup(context)
        self.assertEqual("success", result.status)
        self.assertEqual(fence, worker.call_args.kwargs["execution_fence"])

    def test_password_reset_calls_confirmed_checkpoint_only_after_relogin(self):
        driver = Mock()
        target = object()
        continue_target = object()
        confirmed = Mock()
        with (
            patch.object(roxy_codex_oauth, "_forgot_password_target", return_value=target),
            patch.object(roxy_codex_oauth, "_human_click"),
            patch.object(roxy_codex_oauth, "_wait_for_reset_route", return_value=True),
            patch.object(roxy_codex_oauth, "_reset_continue_target", return_value=continue_target),
            patch.object(roxy_codex_oauth, "_wait_for_reset_otp_page", return_value=True),
            patch.object(roxy_codex_oauth, "_wait_for_fresh_email_otp", return_value="123456"),
            patch.object(roxy_codex_oauth, "_wait_for_otp_input"),
            patch.object(roxy_codex_oauth, "_clear_otp_inputs"),
            patch.object(roxy_codex_oauth, "_type_otp"),
            patch.object(roxy_codex_oauth, "_click_if_present", return_value=True),
            patch.object(roxy_codex_oauth, "_wait_for_reset_password_form", return_value="accepted"),
            patch.object(roxy_codex_oauth, "_submit_reset_password_and_wait"),
            patch.object(roxy_codex_oauth, "_relogin_after_password_reset"),
            patch.object(roxy_codex_oauth, "human_delay"),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="New!Password123"),
        ):
            self.assertTrue(
                roxy_codex_oauth._reset_password_via_email(
                    driver,
                    "account@example.com",
                    Mock(),
                    on_password_confirmed=confirmed,
                )
            )

        confirmed.assert_called_once_with("New!Password123")

    def test_force_password_login_enters_reset_even_when_local_password_exists(self):
        driver = Mock()
        with (
            patch.object(roxy_codex_oauth, "_login_challenge_state", return_value={"url": "https://auth.openai.com/log-in/password", "inputs": [], "errors": []}),
            patch.object(roxy_codex_oauth, "_is_login_password_page", return_value=True),
            patch.object(roxy_codex_oauth, "_reset_password_via_email", return_value=True) as reset,
        ):
            result = roxy_codex_oauth.complete_openai_login_challenge(
                driver,
                "account@example.com",
                "old-password",
                "",
                timeout=2,
                otp_provider=Mock(),
                force_password_reset=True,
            )

        self.assertEqual("advanced", result)
        reset.assert_called_once()

    def test_change_queue_uses_distinct_task_type_and_force_flag(self):
        context = runtime.WebUIContext(Flask("test-runtime"), logging.getLogger("test-runtime"))
        account = {"id": 17, "email": "account@example.com", "account_status": "active"}
        with (
            patch.object(runtime.db, "get_account", return_value=account),
            patch.object(
                runtime.account_task_store,
                "submit_durable_operation",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "reused": False,
                    "task_id": 701,
                    "run_id": 702,
                    "status": "queued",
                },
            ) as submit,
        ):
            result = context.enqueue_account_setup(
                17,
                trigger="manual_account_password_change",
                steps={"password"},
                task_type="password_change",
                operation="password_change",
            )

        self.assertTrue(result["accepted"])
        self.assertEqual("password_change", submit.call_args.kwargs["task_type"])
        self.assertTrue(submit.call_args.kwargs["data"]["force_password_reset"])
        self.assertFalse(submit.call_args.kwargs["data"]["force_twofa_change"])

    def test_change_task_types_have_progress_templates(self):
        self.assertEqual(
            ["network", "browser", "authenticate", "set_password", "result"],
            [step["id"] for step in task_progress._template("password_change")],
        )
        self.assertEqual(
            ["network", "browser", "authenticate", "set_twofa", "result"],
            [step["id"] for step in task_progress._template("twofa_change")],
        )
        self.assertEqual(
            ["network", "browser", "authenticate", "set_twofa", "result"],
            [
                step["id"]
                for step in task_progress._template(
                    "twofa_change",
                    {"result_summary": {"planned_steps": ["twofa"]}},
                )
            ],
        )

    def test_historical_change_task_retries_same_force_operation(self):
        context = runtime.WebUIContext(Flask("test-runtime"), logging.getLogger("test-runtime"))
        task = {"id": 701, "status": "failed", "task_type": "twofa_change", "account_id": 17}
        account = {"id": 17, "email": "account@example.com", "account_status": "active"}
        with (
            patch.object(runtime.account_task_store, "get_task", return_value=task),
            patch.object(runtime.db, "get_account", return_value=account),
            patch.object(
                runtime.account_task_store,
                "submit_durable_operation",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "reused": False,
                    "task_id": 702,
                    "run_id": 703,
                    "status": "queued",
                },
            ) as submit,
        ):
            result = context.retry_account_task_result(701)

        self.assertEqual(202, result[1])
        self.assertTrue(submit.call_args.kwargs["data"]["force_twofa_change"])
        self.assertFalse(submit.call_args.kwargs["data"]["force_password_reset"])

    def test_change_bulk_is_capped_at_twenty_accounts(self):
        from webui.routes.accounts import create_accounts_blueprint

        app = Flask("test-account-change-route")
        context = runtime.WebUIContext(app, logging.getLogger("test-account-change-route"))
        app.register_blueprint(create_accounts_blueprint(context))
        response = app.test_client().post(
            "/api/accounts/action-bulk",
            json={"action": "password_change", "account_ids": list(range(21))},
        )

        self.assertEqual(400, response.status_code)
        self.assertIn("20", response.get_json()["error"])

    def test_force_twofa_reconfigure_disables_existing_toggle_before_enrollment(self):
        driver = Mock()
        enabled_toggle = Mock()
        enabled_toggle.get_attribute.return_value = "true"
        disabled_toggle = Mock()
        disabled_toggle.get_attribute.return_value = "false"
        totp_field = Mock()
        verify_button = Mock()
        disabled = Mock()
        secret = "JBSWY3DPEHPK3PXP"
        with (
            patch.object(roxy_registration, "_open_chatgpt_security_settings", return_value=enabled_toggle),
            patch.object(roxy_registration, "_disable_roxy_2fa") as disable,
            patch.object(
                roxy_registration,
                "_first_visible_css",
                side_effect=lambda _driver, selector: enabled_toggle if selector == '[data-testid="mfa-authenticator-toggle"]' else None,
            ),
            patch.object(roxy_registration, "_wait_mfa_enrollment_step", return_value=("totp", totp_field)),
            patch.object(roxy_registration, "_manual_totp_secret", return_value=secret),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_button_after_input", return_value=verify_button),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration, "_check_manual_stop"),
            patch.object(roxy_registration.time, "sleep"),
        ):
            result = roxy_registration.setup_roxy_2fa(
                driver,
                "account@example.com",
                existing_secret="OLDSECRET123",
                force_reconfigure=True,
                on_disabled=disabled,
            )

        self.assertEqual(secret, result)
        disable.assert_called_once_with(driver, enabled_toggle)
        disabled.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
