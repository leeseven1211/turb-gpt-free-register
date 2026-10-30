"""补全账号可显式登录取得首个 AT，独立刷新入口仍保留默认限制。"""

from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts import completion as account_completion_service
from core.accounts.liveness import service as live_check_service
from core.operations import task_gateway


class CompletionRefreshAuthTests(unittest.TestCase):
    account = {"id": 41, "email": "completion@example.test", "access_token": ""}

    def _enqueue(self, *, allow_missing_token=None, active_job=None):
        with (
            patch.object(live_check_service.db, "get_account", return_value=dict(self.account)),
            patch.object(live_check_service.db, "claim_account_live_check", return_value=True) as claim,
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="browser_roxy"),
            patch.object(live_check_service, "register_operation_handlers"),
            patch.object(live_check_service, "_captured_proxy_source", return_value="auto"),
            patch.object(live_check_service, "_append_log"),
            patch.object(account_completion_service, "active_registration_job", return_value=active_job, create=True) as active,
            patch.object(
                live_check_service.account_task_store,
                "submit_durable_operation",
                return_value={"accepted": True, "task_id": 42, "run_id": 43},
            ) as submit,
        ):
            options = {} if allow_missing_token is None else {"allow_missing_token": allow_missing_token}
            result = live_check_service.enqueue_account_live_check(
                account_id=41,
                email="completion@example.test",
                force_refresh=True,
                **options,
            )
        return result, claim, active, submit

    def test_independent_refresh_still_rejects_missing_at_by_default(self):
        result, claim, active, submit = self._enqueue()

        self.assertFalse(result["accepted"])
        self.assertTrue(result["not_registered"])
        claim.assert_not_called()
        active.assert_not_called()
        submit.assert_not_called()

    def test_completion_explicitly_allows_missing_at_and_freezes_auth_scope(self):
        result, claim, active, submit = self._enqueue(allow_missing_token=True)

        self.assertTrue(result["accepted"])
        claim.assert_called_once()
        active.assert_called_once_with(41, "completion@example.test")
        data = submit.call_args.kwargs["data"]
        self.assertTrue(data["completion_auth"])
        self.assertTrue(data["force_refresh"])
        self.assertEqual("browser_roxy", data["refresh_driver"])

    def test_completion_does_not_enqueue_while_same_account_is_registering(self):
        result, claim, active, submit = self._enqueue(
            allow_missing_token=True,
            active_job={"id": 44, "status": "running"},
        )

        self.assertFalse(result["accepted"])
        self.assertTrue(result["busy"])
        self.assertIn("注册", result["error"])
        active.assert_called_once_with(41, "completion@example.test")
        claim.assert_not_called()
        submit.assert_not_called()

    def test_queued_completion_auth_rechecks_active_registration_before_remote_work(self):
        context = SimpleNamespace(
            account_id=41,
            task_id=42,
            email="completion@example.test",
            resource_family="openai_interactive",
            config_snapshot={},
            run={"data": {"force_refresh": True, "completion_auth": True}},
            lease=lambda **_kwargs: nullcontext(),
        )
        with (
            patch.object(live_check_service.db, "get_account", return_value=dict(self.account)),
            patch.object(account_completion_service, "active_registration_job", return_value={"id": 44}, create=True) as active,
            patch.object(live_check_service, "operation_log_context", return_value=nullcontext()),
            patch.object(live_check_service, "_run_live_check") as run,
        ):
            with self.assertRaises(task_gateway.OperationLeaseUnavailable):
                live_check_service._handle_live_operation(context)

        active.assert_called_once_with(41, "completion@example.test")
        run.assert_not_called()


class CompletionRefreshFallbackTests(unittest.TestCase):
    def _dispatch_refresh(self, protocol_result, *, completion_auth=True,
                          fallback_enabled=True, driver="v2"):
        account = {"id": 41, "email": "completion@example.test", "access_token": ""}
        execution = []
        written_results = []
        context = SimpleNamespace(
            account_id=41,
            task_id=42,
            run_id=43,
            email=account["email"],
            resource_family="openai_interactive",
            config_snapshot={
                "auth_raw_context_enabled": False,
                "auth_profile_mode": "current",
                "roxy_fallback_enabled": fallback_enabled,
            },
            run={"data": {
                "force_refresh": True,
                "refresh_driver": driver,
                **({"completion_auth": True} if completion_auth else {}),
            }},
            lease=lambda **_kwargs: nullcontext(),
            remote_request_started=Mock(),
            remote_request_receipt=Mock(),
        )

        def protocol(_email, **kwargs):
            execution.append("protocol")
            kwargs["on_remote_request_started"]()
            return dict(protocol_result)

        def browser(_email, **_kwargs):
            execution.append("browser")
            return {"ok": True, "status": "live", "access_token": "fixture-fresh", "session": {}}

        def save_result(_account_id, result):
            written_results.append(dict(result))
            account.update({
                "access_token": result.get("access_token", ""),
                "live_check_ok": bool(result.get("ok")),
                "live_check_status": result.get("status"),
            })
            return True

        route = SimpleNamespace(
            proxy_url="http://fixture.invalid:8080",
            public_dict=lambda: {"network_route": "proxy"},
            release=Mock(),
        )
        with (
            patch.object(live_check_service.db, "get_account", side_effect=lambda *_args: dict(account)),
            patch.object(live_check_service.db, "mark_account_live_check_running", return_value=True),
            patch.object(live_check_service.db, "update_account_liveness", side_effect=save_result),
            patch.object(account_completion_service, "active_registration_job", return_value=None),
            patch.object(live_check_service, "_reporter"),
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_checkpoint"),
            patch.object(live_check_service, "operation_log_context", return_value=nullcontext()),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=protocol),
            patch.object(live_check_service, "check_account_liveness", side_effect=AssertionError("本用例不应调用 v1 认证")),
            patch("core.accounts.liveness.roxy.flow.available", return_value=True),
            patch("core.accounts.liveness.roxy.flow.refresh_access_token", side_effect=browser),
        ):
            live_check_service._handle_live_operation(context)
        return written_results[-1], execution, context

    def test_completion_without_at_can_use_configured_browser_fallback_after_safe_rejection(self):
        result, execution, context = self._dispatch_refresh({
            "ok": False, "status": "failed", "error": "password_rejected",
        })

        self.assertTrue(result["ok"])
        self.assertEqual("fixture-fresh", result["access_token"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(["protocol", "browser"], execution)
        self.assertEqual("rejected", context.remote_request_receipt.call_args_list[0].kwargs["outcome"])

    def test_completion_unknown_auth_result_never_uses_browser_fallback(self):
        for error in ("password_result_unknown", "auth_result_not_classified"):
            with self.subTest(error=error):
                result, execution, _context = self._dispatch_refresh({
                    "ok": False, "status": "failed", "error": error,
                })

                self.assertFalse(result["ok"])
                self.assertTrue(result["reconcile_required"])
                self.assertEqual(["protocol"], execution)

    def test_completion_fallback_still_respects_adapter_and_configuration_gates(self):
        for adapter_allowed, fallback_enabled in ((False, True), (True, False)):
            with self.subTest(adapter_allowed=adapter_allowed, fallback_enabled=fallback_enabled):
                result, execution, _context = self._dispatch_refresh({
                    "ok": False, "status": "failed", "error": "password_rejected",
                    "roxy_fallback_allowed": adapter_allowed,
                }, fallback_enabled=fallback_enabled)

                self.assertFalse(result["ok"])
                self.assertEqual("password_rejected", result["error"])
                self.assertEqual(["protocol"], execution)

    def test_missing_at_without_completion_auth_does_not_gain_browser_fallback(self):
        result, execution, _context = self._dispatch_refresh({
            "ok": False, "status": "failed", "error": "password_rejected",
        }, completion_auth=False)

        self.assertFalse(result["ok"])
        self.assertEqual(["protocol"], execution)

    def test_completion_direct_browser_driver_runs_once_without_protocol_or_second_fallback(self):
        result, execution, _context = self._dispatch_refresh({}, driver="browser_roxy")

        self.assertTrue(result["ok"])
        self.assertEqual("fixture-fresh", result["access_token"])
        self.assertEqual(["browser"], execution)
        self.assertNotIn("fallback_used", result)
