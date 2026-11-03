# -*- coding: utf-8 -*-
"""v3 只进入显式 AT 刷新，并随任务快照冻结。"""
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from config import account as account_config
from core.accounts.liveness import service
from core.auth.protocol.version import normalize_protocol_version, resolve_protocol_version


class ProtocolV3SelectionTests(unittest.TestCase):
    def test_schema_accepts_v3_without_changing_default(self):
        from config import schema
        field = schema.CONFIG_SCHEMA["OPENAI_PROTOCOL_VERSION"]
        self.assertEqual("v1", field.default)
        self.assertEqual({"v1", "v2", "v3"}, {option.value for option in field.options})
        self.assertEqual({"OPENAI_PROTOCOL_VERSION": "v3"}, schema.validate_config_updates({
            "OPENAI_PROTOCOL_VERSION": "v3",
        }))

    def test_v3_is_public_refresh_version_only(self):
        self.assertEqual("v3", normalize_protocol_version("3"))
        self.assertEqual("v3", resolve_protocol_version("refresh_at", requested="v3"))
        for step in ("registration", "twofa", "plan_check", "live_check", "codex_oauth"):
            with self.subTest(step=step):
                self.assertEqual("v1", resolve_protocol_version(step, requested="v3"))

    def test_v3_selection_does_not_depend_on_v2_legacy_gate(self):
        with patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", False):
            for value in ("v3", "3", "protocol_v3"):
                with self.subTest(value=value):
                    self.assertEqual("protocol_v3", service._resolve_refresh_driver(value))
        self.assertEqual("v3", service._refresh_driver_request("protocol_v3"))

    def test_saved_snapshot_selects_v3_and_roxy_remains_independent(self):
        self.assertEqual("protocol_v3", service._resolve_refresh_driver(
            config_snapshot={"refresh_driver": "protocol", "refresh_protocol_version": "v3"},
        ))
        self.assertEqual("browser_roxy", service._resolve_refresh_driver(
            config_snapshot={"refresh_driver": "browser_roxy", "refresh_protocol_version": "v3"},
        ))

    def test_invalid_email_does_not_downgrade_v3_task_to_v2(self):
        account = {"id": 7, "email": "fixture@example.test", "access_token": "fixture-at", "email_invalid": True}
        with (
            patch.object(service.db, "get_account", return_value=account),
            patch.object(service.db, "account_is_deactivated", return_value=False),
            patch.object(service.db, "claim_account_live_check", return_value=True),
            patch.object(service, "_append_log"),
            patch.object(service.account_task_store, "submit_durable_operation", return_value={
                "accepted": True, "task_id": 101, "run_id": 1001, "status": "queued",
            }) as submit,
        ):
            result = service.enqueue_account_live_check(
                account_id=7, email=account["email"], trigger="token_refresh_manual", force_refresh=True,
                driver="v3",
            )
        self.assertTrue(result["accepted"])
        self.assertEqual("protocol_v3", result["token_refresh_driver"])
        self.assertEqual("v3", submit.call_args.kwargs["data"]["refresh_driver"])

    def test_worker_routes_v3_with_account_and_keeps_old_drivers_idle(self):
        for proxy in (None, "http://proxy.example:8080"):
            with self.subTest(proxy=proxy), ExitStack() as stack:
                reporter = MagicMock()
                route = MagicMock(proxy_url="http://proxy.example:8080")
                route.public_dict.return_value = {"network_route": "proxy"}
                for item in (
                    patch.object(service.db, "mark_account_live_check_running", return_value=True),
                    patch.object(service.db, "get_account", return_value={"id": 7, "email_invalid": True, "access_token": "fixture-old"}),
                    patch.object(service.db, "update_account_liveness", return_value=True),
                    patch.object(service, "_reporter", return_value=reporter),
                    patch.object(service, "_append_log"),
                    patch.object(service, "token_claims", return_value={}),
                    patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
                ):
                    stack.enter_context(item)
                v3 = stack.enter_context(patch("core.accounts.liveness.protocol.v3.refresh_access_token", return_value={
                    "ok": True, "status": "live", "access_token": "fixture-fresh", "session": {},
                    "session_reused": True, "auth_method": "session_cookie", "live_check_driver": "protocol_v3",
                }))
                v2 = stack.enter_context(patch("core.accounts.liveness.protocol.v2.refresh_access_token"))
                legacy = stack.enter_context(patch.object(service, "check_account_liveness"))
                browser = stack.enter_context(patch("core.accounts.liveness.roxy.flow.refresh_access_token"))
                result = service._run_live_check(
                    account_id=7, email="fixture@example.test", trigger="fixture", proxy=proxy,
                    force_refresh=True, refresh_driver="v3",
                    config_snapshot={"auth_raw_context_enabled": False, "roxy_fallback_enabled": False},
                )
                self.assertTrue(result["ok"])
                self.assertEqual("v3", result["protocol_version"])
                self.assertEqual(7, v3.call_args.kwargs["account_id"])
                v3.assert_called_once()
                v2.assert_not_called()
                legacy.assert_not_called()
                browser.assert_not_called()
                self.assertTrue(any(call.args[:2] == ("login_password", "skipped") for call in reporter.stage.call_args_list))
                self.assertFalse(any(call.args[:2] == ("email_otp", "success") for call in reporter.stage.call_args_list))

    def test_completed_auth_steps_remain_success_when_later_stage_fails(self):
        for cause, email_status, mfa_status in (
            ("mfa_verify_failed", "success", "failed"),
            ("workspace_select_failed", "success", "success"),
            ("session_fetch_failed", "success", "success"),
        ):
            with self.subTest(cause=cause):
                reporter = MagicMock()
                service._report_protocol_v2_refresh(reporter, {
                    "ok": False, "live_check_driver": "protocol_v3", "error_code": cause,
                    "auth_method": "password_email_otp_mfa", "password_auth_status": "verified",
                    "email_otp_status": email_status, "mfa_status": mfa_status,
                })
                stages = {call.args[0]: call.args[1] for call in reporter.stage.call_args_list}
                self.assertEqual("success", stages["login_password"])
                self.assertEqual(email_status, stages["email_otp"])
                self.assertEqual(mfa_status, stages["mfa_challenge"])
                self.assertNotIn("token", stages)


if __name__ == "__main__":
    unittest.main()
