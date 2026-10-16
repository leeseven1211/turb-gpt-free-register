"""补密码在原生 Run 中保留线路、浏览器和密码检查点证据。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from core import codex_retry_service as service, task_run_log
from core.operation_runtime import OperationCancelled, operation_context, report_stage
from core.registration.state_machine import StageTimeout
from core.task_progress import build_progress_snapshot


class PasswordSetupReportingTests(unittest.TestCase):
    def tearDown(self):
        task_run_log.clear_current_context()

    def _run_native(self, *, fail_relogin=False, cancel_relogin=False):
        events = []
        route = SimpleNamespace(
            proxy_url=None, provider="fixture", region="fixture", mode="direct",
            public_dict=lambda: {"network_route": "direct"}, release=Mock(),
        )

        def browser(_email, **kwargs):
            report_stage("browser", "浏览器已连接", state="success")
            report_stage("login", "正在登录")
            kwargs["on_password_reset_submitted"]("fixture-new-password")
            report_stage("login", "正在使用新密码重新登录")
            if cancel_relogin:
                raise OperationCancelled("用户手动停止账号配置")
            if fail_relogin:
                raise StageTimeout("fixture relogin timeout")

        with ExitStack() as stack:
            stack.enter_context(patch("config.reload_all"))
            stack.enter_context(patch("config.account.ACCOUNT_PASSWORD_RESET_ENABLED", True))
            stack.enter_context(patch.object(service.db, "get_account_by_email", return_value={"id": 7}))
            saved = stack.enter_context(patch.object(service.db, "update_account_login_password", return_value=True))
            stack.enter_context(patch.object(service.account_task_store, "get_task", return_value={}))
            legacy = stack.enter_context(patch.object(service.account_task_store, "append_event"))
            stack.enter_context(patch.object(service.task_run_log, "TaskRunLogHandler"))
            stack.enter_context(patch.object(service.logging, "getLogger", return_value=Mock()))
            stack.enter_context(patch.object(service, "check_stop_requested"))
            stack.enter_context(patch.object(service, "_attach_auth_projection"))
            stack.enter_context(patch.object(service, "_build_roxy_account_setup", return_value=Mock()))
            stack.enter_context(patch("core.account_proxy.acquire_account_proxy", return_value=route))
            stack.enter_context(patch("core.roxy_codex_oauth.run_roxy_chatgpt_account_action", side_effect=browser))
            stack.enter_context(operation_context(Mock(), reporter=lambda **event: events.append(event)))
            result = service.run_twofa_worker(
                "fixture@example.test", task_id=0, steps={"password"},
                manage_task=False, clear_log=False,
                target_log_path="/tmp/turb-password-setup-reporting/run.jsonl",
            )
        return result, events, saved, legacy

    def test_native_run_records_real_stage_order_and_password_checkpoint(self):
        result, events, saved, legacy = self._run_native()
        self.assertTrue(result["ok"])
        self.assertEqual(
            [(e["stage"], e["state"]) for e in events[:4]],
            [("network", "running"), ("network", "success"), ("browser", "running"), ("browser", "success")],
        )
        saved.assert_called_once_with("fixture@example.test", "fixture-new-password", source="password_reset")
        checkpoint = next(e for e in events if (e.get("detail") or {}).get("checkpoint") == "password_reset_submitted")
        self.assertTrue(checkpoint["detail"]["saved"])
        self.assertNotIn("fixture-new-password", str(events))
        legacy.assert_not_called()

    def test_relogin_failure_preserves_checkpoint_and_actual_failure_stage(self):
        result, events, saved, _legacy = self._run_native(fail_relogin=True)
        self.assertFalse(result["ok"])
        saved.assert_called_once()
        failed = [e for e in events if e.get("state") == "failed"]
        self.assertEqual([e["stage"] for e in failed], ["login"])
        self.assertTrue(any((e.get("detail") or {}).get("saved") for e in events))

    def test_legacy_task_keeps_its_original_event_contract(self):
        with patch.object(service.account_task_store, "append_event") as legacy, patch.object(service, "report_stage") as native:
            service._report_account_setup_event(17, stage="network", state="success", message="线路已分配")
        legacy.assert_called_once_with(17, stage="network", state="success", message="线路已分配")
        native.assert_not_called()

    def test_native_cancellation_does_not_report_again_or_become_unknown(self):
        def guarded_report(*args, **kwargs):
            if "已被用户停止" in str(kwargs.get("message")):
                raise OperationCancelled("取消后不能继续上报业务阶段")
            return report_stage(*args, **kwargs)

        with patch.object(service, "report_stage", side_effect=guarded_report):
            result, events, saved, _legacy = self._run_native(cancel_relogin=True)
        self.assertEqual(result["status"], "stopped")
        saved.assert_called_once()
        self.assertFalse(any(e.get("state") == "failed" for e in events))

    def test_native_retry_notice_does_not_start_another_stage(self):
        with patch.object(service, "report_stage") as native:
            service._report_account_setup_event(
                0, stage="browser", message="准备恢复浏览器登录", level="WARNING", event_type="note.warning",
            )
        self.assertIsNone(native.call_args.kwargs["state"])

    def test_password_only_action_does_not_add_unknown_twofa_steps(self):
        events = []

        def set_password(_driver, _email, password, *, on_password_submitted):
            on_password_submitted(password)

        with (
            patch.object(service.db, "get_account_by_email", return_value={"access_token": "fixture-access"}),
            patch.object(service.db, "update_account_login_password", return_value=True),
            patch.object(service.db, "update_account_password_capability"),
            patch("core.registration.selenium_auth.registration_password", return_value="fixture-password"),
            patch("core.registration.selenium_auth.set_login_password", side_effect=set_password),
            operation_context(Mock(), reporter=lambda **event: events.append(event)),
        ):
            action = service._build_roxy_account_setup("fixture@example.test", 0, include_twofa=False)
            self.assertTrue(action(object()))

        self.assertFalse(any(e["stage"] in {"twofa", "twofa_result"} for e in events))
        persisted = [{**e, "id": i, "event_type": f"stage.{e['state']}"} for i, e in enumerate(events, 1) if e.get("state")]
        progress = build_progress_snapshot(1, 2, "password_setup", {"status": "success"}, persisted)
        self.assertFalse(any(s["id"].startswith("unknown:") for s in progress["main_steps"]))

