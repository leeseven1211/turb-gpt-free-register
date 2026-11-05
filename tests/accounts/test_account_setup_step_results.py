"""组合补全逐项保存结果，成功的 2FA 不能掩盖密码缺项。"""
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.auth.challenge import PasswordSetupUnsupportedError
from core.codex import retry_service as service
from core.storage.operations import store as operation_store
from webui import runtime


class AccountSetupStepResultTests(unittest.TestCase):
    def _browser_worker(self, password_error, *, finishes=None):
        account = {"id": 7, "email": "fixture@example.test", "access_token": "fixture-at"}
        route = SimpleNamespace(
            proxy_url="http://fixture.invalid", provider="fixture", region="JP", mode="pool",
            public_dict=lambda: {}, release=Mock(),
        )
        with ExitStack() as stack:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            stack.enter_context(patch("config.reload_all"))
            stack.enter_context(patch.object(service.db, "get_account_by_email", return_value=account))
            stack.enter_context(patch.object(service.db, "update_account_login_password", return_value=True))
            stack.enter_context(patch.object(service.db, "update_account_password_capability"))
            stack.enter_context(patch.object(service.account_task_store, "get_task", return_value={}))
            stack.enter_context(patch.object(service.account_task_store, "append_event"))
            stack.enter_context(patch.object(service.account_task_store, "start_task"))
            stack.enter_context(patch.object(service.account_task_store, "finish_task", side_effect=lambda *a, **k: finishes.append(k) if finishes is not None else None))
            stack.enter_context(patch.object(service, "release"))
            stack.enter_context(patch.object(service, "check_stop_requested"))
            stack.enter_context(patch.object(service, "_attach_auth_projection"))
            stack.enter_context(patch.object(service, "_build_roxy_twofa_setup", return_value=Mock(return_value=True)))
            stack.enter_context(patch("core.auth.browser.selenium_auth.registration_password", return_value="fixture-candidate"))
            password = stack.enter_context(patch("core.auth.browser.selenium_auth.set_login_password", side_effect=password_error))
            stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", return_value=route))
            browser = stack.enter_context(patch(
                "core.codex.roxy.oauth.run_roxy_chatgpt_account_action",
                side_effect=lambda email, **kwargs: kwargs["action"](object()),
            ))
            result = service.run_twofa_worker(
                account["email"], task_id=7, target_log_path=root / "run.jsonl",
                clear_log=False, manage_task=finishes is not None, steps={"password", "twofa"},
                password_driver_override="roxy", twofa_driver_override="browser",
            )
        return result, password, browser

    def test_unsupported_password_and_successful_twofa_remain_partial(self):
        result, password, browser = self._browser_worker(PasswordSetupUnsupportedError("本轮无密码入口"))
        self.assertFalse(result["ok"])
        self.assertEqual("partial_success", result["status"])
        self.assertEqual("unsupported", result["password_setup"]["status"])
        self.assertEqual("rejected", result["password_setup"]["remote_receipt_state"])
        self.assertTrue(result["twofa_setup"]["ok"])
        self.assertEqual({"password", "twofa"}, set(result["step_results"]))
        password.assert_called_once()
        browser.assert_called_once()

    def test_failed_password_does_not_erase_successful_twofa(self):
        result, password, browser = self._browser_worker(RuntimeError("本轮密码操作失败"))
        self.assertFalse(result["ok"])
        self.assertEqual("failed", result["status"])
        self.assertEqual("failed", result["password_setup"]["status"])
        self.assertTrue(result["twofa_setup"]["ok"])
        password.assert_called_once()
        browser.assert_called_once()

    def test_outer_failure_is_preserved_even_when_every_step_reports_success(self):
        result = {"ok": False, "status": "failed", "message": "本轮改密未确认", "error_code": "password_recovery_unconfirmed"}
        service._finalize_account_setup_results(result, {"password"}, {
            "password": {"ok": True, "status": "success"},
        })
        self.assertFalse(result["ok"])
        self.assertEqual("failed", result["status"])
        self.assertEqual("password_recovery_unconfirmed", result["error_code"])
        self.assertTrue(result["password_setup"]["ok"])

    def test_force_reset_does_not_accept_confirmed_old_password(self):
        outcomes = {}
        account = {"access_token": "fixture-at", "extra_json": {
            "account_password": "fixture-old-password", "account_password_state": "confirmed",
        }}
        with patch.object(service.db, "get_account_by_email", return_value=account), patch.object(service, "_report_account_setup_event"):
            service._build_roxy_account_setup(
                "fixture@example.test", 0, include_twofa=False, force_password_reset=True,
                password_reset_confirmed=lambda: False, step_results=outcomes,
            )(object())
        self.assertFalse(outcomes["password"]["ok"])
        self.assertEqual("password_recovery_unconfirmed", outcomes["password"]["error_code"])

    def test_legacy_task_keeps_partial_status_and_safe_step_evidence(self):
        finishes = []
        result, *_ = self._browser_worker(PasswordSetupUnsupportedError("本轮无密码入口"), finishes=finishes)
        self.assertEqual("partial_success", result["status"])
        self.assertEqual("partial_success", finishes[-1]["status"])
        summary = operation_store._scrub(finishes[-1]["result_summary"])
        self.assertEqual(["password", "twofa"], summary["requested_steps"])
        self.assertFalse(summary["password_setup"]["ok"])
        self.assertTrue(summary["twofa_setup"]["ok"])
        password = next(item for item in summary["setup_step_results"] if item["step"] == "password")
        self.assertFalse(password["result"]["ok"])

    def test_successful_browser_login_without_step_execution_is_not_setup_success(self):
        result = {"ok": True, "status": "success"}
        service._finalize_account_setup_results(result, {"password", "twofa"}, {})
        self.assertFalse(result["ok"])
        self.assertEqual("not_executed", result["password_setup"]["status"])
        self.assertEqual("not_executed", result["twofa_setup"]["status"])

    def test_automatic_retry_keeps_confirmed_password_and_only_retries_twofa(self):
        outcomes = {}
        twofa = Mock(side_effect=[RuntimeError("net::ERR_CONNECTION_CLOSED"), True])
        with (
            patch.object(service.db, "get_account_by_email", return_value={"access_token": "fixture-at"}),
            patch.object(service.db, "update_account_login_password", return_value=True),
            patch.object(service.db, "update_account_password_capability"),
            patch.object(service, "_report_account_setup_event"),
            patch.object(service, "_build_roxy_twofa_setup", return_value=twofa),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="fixture-candidate"),
            patch("core.auth.browser.selenium_auth.set_login_password") as password,
        ):
            action = service._build_roxy_account_setup("fixture@example.test", 0, step_results=outcomes)
            with self.assertRaisesRegex(RuntimeError, "ERR_CONNECTION_CLOSED"):
                action(object())
            self.assertTrue(outcomes["password"]["ok"])
            action(object())
        password.assert_called_once()
        self.assertEqual(2, twofa.call_count)
        self.assertTrue(outcomes["password"]["ok"])
        self.assertTrue(outcomes["twofa"]["ok"])

    def test_candidate_password_cannot_satisfy_confirmed_receipt_readback(self):
        with patch.object(runtime.db, "get_account", return_value={
            "access_token": "fixture-at",
            "extra_json": {"account_password": "fixture-candidate", "account_password_state": "candidate"},
        }):
            state, evidence = runtime._account_setup_receipt(7, "fixture@example.test", {"password"}, {
                "ok": True, "status": "success",
                "step_results": {"password": {"ok": True, "remote_receipt_state": "confirmed"}},
            })
        self.assertEqual("local_commit_required", state)
        self.assertFalse(evidence["local_readback_checks"]["password"])

    def test_submission_with_failed_local_checkpoint_keeps_unknown_receipt(self):
        outcomes = {}

        def submit(_driver, _email, password, **callbacks):
            callbacks["on_password_submitted"](password)

        with (
            patch.object(service.db, "get_account_by_email", return_value={"access_token": "fixture-at"}),
            patch.object(service.db, "update_account_login_password", return_value=False),
            patch.object(service, "_report_account_setup_event"),
            patch("core.auth.browser.selenium_auth.registration_password", return_value="fixture-candidate"),
            patch("core.auth.browser.selenium_auth.set_login_password", side_effect=submit),
        ):
            action = service._build_roxy_account_setup(
                "fixture@example.test", 0, include_twofa=False, step_results=outcomes,
            )
            with self.assertRaisesRegex(RuntimeError, "账号配置部分失败"):
                action(object())
        self.assertTrue(outcomes["password"]["mutation_submitted"])
        self.assertEqual("unknown", outcomes["password"]["remote_receipt_state"])
