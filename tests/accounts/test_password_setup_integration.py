"""纯协议补密码的执行、准入和持久任务接入。"""

from contextlib import ExitStack
import logging
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts.completion import completion_plan
from core.codex import retry_service as worker
from core.operations.stages import flow_for
from core.runtime.capabilities import account_setup_unavailable
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import store as operation_store
from tests.support_pg import PostgresTestCase
from webui import runtime


class PasswordSetupIntegrationTests(unittest.TestCase):
    def run_setup(
        self,
        *,
        steps=None,
        password_ok=True,
        twofa_ok=True,
        force_reset=False,
        fallback=False,
        reset_enabled=False,
        plan_ok=True,
        password_status=None,
        stop_after_password=False,
    ):
        actions = []
        account = {"id": 42, "email": "fixture@example.test", "access_token": "fixture-old-at"}
        fence = {"run_id": 51, "execution_id": "fixture-execution", "lease_token": "fixture-lease"}
        route = SimpleNamespace(
            proxy_url="http://fixture.proxy:8080",
            provider="fixture",
            mode="pool",
            region="JP",
            release=Mock(),
            lease=SimpleNamespace(lease_id="fixture-proxy-lease"),
            public_dict=lambda: {"network_route": "proxy", "proxy_mode": "pool"},
        )

        def password_setup(email, *, proxy, execution_fence, checkpoint=None, report=None):
            actions.append(("password", email, proxy, execution_fence))
            if password_ok:
                account.update(access_token="fixture-new-at", extra_json={"account_password": "fixture-password"})
            return {
                "ok": password_ok,
                "status": password_status or ("success" if password_ok else "failed"),
                "message": "补密码完成" if password_ok else "密码明确被拒绝",
                "password_driver": "protocol",
                "browser_opened": False,
                "remote_receipt_state": "none"
                if password_status == "deactivated"
                else "confirmed"
                if password_ok
                else "rejected",
                "mutation_submitted": password_status != "deactivated",
                "stop_requested": stop_after_password,
            }

        service = ModuleType("core.accounts.password_setup.service")
        service.run_protocol_password_setup = password_setup

        def twofa_setup(_email, current, *_args, **_kwargs):
            actions.append(("twofa", current.get("access_token")))
            if not twofa_ok:
                raise RuntimeError("fixture twofa rejected")
            return {
                "ok": True,
                "status": "success",
                "message": "2FA 完成",
                "twofa_driver": "protocol",
                "browser_opened": False,
            }

        def browser_setup(*_args, **kwargs):
            self.assertEqual(force_reset, kwargs["allow_password_reset"])
            actions.append(("browser",))

        def plan_check(*_args, **_kwargs):
            actions.append(("plan",))
            return {"ok": plan_ok, "status": "success" if plan_ok else "failed", "message": "套餐查询结果"}

        def persist_deactivated(*_args, **_kwargs):
            account["account_status"] = "deactivated"
            return True

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {service.__name__: service}))
            stack.enter_context(patch("config.reload_all"))
            stack.enter_context(patch("config.account.ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", fallback))
            stack.enter_context(patch("config.account.ACCOUNT_PASSWORD_RESET_ENABLED", reset_enabled))
            stack.enter_context(
                patch.object(worker.db, "get_account_by_email", side_effect=lambda _email: dict(account))
            )
            stack.enter_context(patch.object(worker.db, "update_account_twofa_status"))
            stack.enter_context(patch.object(worker.account_task_store, "get_task", return_value={}))
            stack.enter_context(patch.object(worker.account_task_store, "append_event"))
            stack.enter_context(
                patch.object(worker.task_run_log, "TaskRunLogHandler", return_value=logging.NullHandler())
            )
            stack.enter_context(patch.object(worker, "check_stop_requested"))
            stack.enter_context(patch.object(worker, "_run_protocol_direct_twofa", side_effect=twofa_setup))
            stack.enter_context(patch.object(worker, "_run_retry_plan_check", side_effect=plan_check))
            stack.enter_context(
                patch.object(worker, "_persist_account_deactivated_result", side_effect=persist_deactivated)
            )
            stack.enter_context(patch.object(worker, "_build_roxy_account_setup", return_value=Mock()))
            stack.enter_context(patch.object(worker, "_manual_password_recovery_owner", return_value={}))
            stack.enter_context(
                patch(
                    "core.auth.browser.password_recovery.PasswordRecoverySession",
                    return_value=SimpleNamespace(
                        resume=Mock(),
                        checkpoint=SimpleNamespace(state="confirmed"),
                    ),
                )
            )
            stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", return_value=route))
            stack.enter_context(
                patch("core.codex.roxy.oauth.run_roxy_chatgpt_account_action", side_effect=browser_setup)
            )
            stack.enter_context(patch.object(worker, "_RUNNING_THREADS", {}))
            stack.enter_context(patch.object(worker, "_RESERVED_AT", {}))
            stack.enter_context(patch.object(worker, "_STOP_REQUESTED", set()))
            result = worker.run_twofa_worker(
                account["email"],
                task_id=81,
                manage_task=False,
                clear_log=False,
                target_log_path=Path(directory) / "setup.log",
                steps=steps or {"password"},
                password_driver_override="protocol",
                twofa_driver_override="protocol",
                execution_fence=fence,
                force_password_reset=force_reset,
            )
        return result, actions, account, fence

    def test_protocol_password_setup_completes_without_browser_and_passes_fence(self):
        result, actions, account, fence = self.run_setup()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["browser_opened"])
        self.assertEqual("protocol", result["password_driver"])
        self.assertEqual([("password", "fixture@example.test", "http://fixture.proxy:8080", fence)], actions)
        self.assertEqual("fixture-password", account["extra_json"]["account_password"])

    def test_protocol_password_precedes_twofa_with_refreshed_token(self):
        result, actions, _account, _fence = self.run_setup(steps={"password", "twofa"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(["password", "twofa"], [item[0] for item in actions])
        self.assertEqual("fixture-new-at", actions[1][1])
        self.assertTrue(result["password_setup"]["ok"])
        self.assertTrue(result["twofa_setup"]["ok"])
        self.assertFalse(result["browser_opened"])

    def test_plan_plus_protocol_twofa_keeps_protocol_route(self):
        result, actions, _account, _fence = self.run_setup(steps={"plan_check", "twofa"})
        self.assertEqual(["plan", "twofa"], [item[0] for item in actions])
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["browser_opened"])

    def test_plan_failure_keeps_password_and_twofa_results(self):
        result, actions, _account, _fence = self.run_setup(steps={"plan_check", "password", "twofa"}, plan_ok=False)
        self.assertEqual(["plan", "password", "twofa"], [item[0] for item in actions])
        self.assertEqual("partial_success", result["status"])
        self.assertFalse(result["plan_check"]["ok"])
        self.assertTrue(result["password_setup"]["ok"])
        self.assertTrue(result["twofa_setup"]["ok"])

    def test_password_rejection_keeps_completed_twofa_visible(self):
        result, actions, _account, _fence = self.run_setup(steps={"password", "twofa"}, password_ok=False)
        self.assertEqual(["password", "twofa"], [item[0] for item in actions])
        self.assertFalse(result["ok"])
        self.assertEqual("partial_success", result["status"])
        self.assertFalse(result["password_setup"]["ok"])
        self.assertTrue(result["twofa_setup"]["ok"])

    def test_confirmed_deactivation_is_saved_before_stopping_twofa(self):
        result, actions, account, _fence = self.run_setup(
            steps={"password", "twofa"},
            password_ok=False,
            password_status="deactivated",
        )
        self.assertEqual(["password"], [item[0] for item in actions])
        self.assertEqual("deactivated", result["status"])
        self.assertTrue(result["account_status_persisted"])
        self.assertEqual("deactivated", account["account_status"])
        self.assertEqual("skipped", result["twofa_setup"]["status"])
        state, _detail = runtime._account_setup_receipt(42, "fixture@example.test", {"password", "twofa"}, result)
        self.assertEqual("not_submitted", state)

    def test_stop_after_password_commit_keeps_confirmed_password_and_skips_twofa(self):
        result, actions, account, _fence = self.run_setup(steps={"password", "twofa"}, stop_after_password=True)
        self.assertEqual(["password"], [item[0] for item in actions])
        self.assertEqual("partial_success", result["status"])
        self.assertTrue(result["password_setup"]["ok"])
        self.assertEqual("confirmed", result["password_setup"]["remote_receipt_state"])
        self.assertEqual("skipped", result["twofa_setup"]["status"])
        with patch.object(runtime.db, "get_account", return_value=account):
            state, _detail = runtime._account_setup_receipt(42, "fixture@example.test", {"password", "twofa"}, result)
        self.assertEqual("confirmed", state)

    def test_password_only_stop_after_commit_keeps_confirmed_success(self):
        result, actions, _account, _fence = self.run_setup(stop_after_password=True)
        self.assertEqual(["password"], [item[0] for item in actions])
        self.assertTrue(result["ok"])
        self.assertTrue(result["stop_requested"])
        self.assertEqual("success", result["status"])

    def test_password_rejection_keeps_successful_plan_as_partial(self):
        result, actions, _account, _fence = self.run_setup(steps={"plan_check", "password"}, password_ok=False)
        self.assertEqual(["plan", "password"], [item[0] for item in actions])
        self.assertEqual("partial_success", result["status"])
        self.assertTrue(result["plan_check"]["ok"])
        self.assertFalse(result["password_setup"]["ok"])

    def test_twofa_failure_keeps_completed_password_visible(self):
        result, actions, account, _fence = self.run_setup(steps={"password", "twofa"}, twofa_ok=False)
        self.assertEqual(["password", "twofa"], [item[0] for item in actions])
        self.assertFalse(result["ok"])
        self.assertEqual("partial_success", result["status"])
        self.assertTrue(result["password_setup"]["ok"])
        self.assertFalse(result["twofa_setup"]["ok"])
        self.assertIn("account_password", account["extra_json"])

    def test_twofa_browser_fallback_respects_existing_switch(self):
        result, actions, _account, _fence = self.run_setup(steps={"password", "twofa"}, twofa_ok=False, fallback=True)
        self.assertEqual(["password", "twofa", "browser"], [item[0] for item in actions])
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["browser_opened"])
        self.assertTrue(result["password_setup"]["ok"])

    def test_twofa_browser_fallback_does_not_repeat_protocol_password_work(self):
        result, actions, _account, _fence = self.run_setup(
            steps={"password", "twofa"},
            password_ok=False,
            twofa_ok=False,
            fallback=True,
            reset_enabled=True,
        )
        self.assertEqual(["password", "twofa", "browser"], [item[0] for item in actions])
        self.assertEqual("partial_success", result["status"])

    def test_protocol_password_admission_works_without_browser(self):
        with (
            patch.dict(os.environ, {"TURB_BROWSER_ENABLED": "false"}),
            patch(
                "config.account.ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
                False,
            ),
        ):
            self.assertIsNone(account_setup_unavailable({"password"}, {"password_driver": "protocol"}))
            self.assertIsNone(
                account_setup_unavailable(
                    {"password", "twofa"},
                    {"password_driver": "protocol", "twofa_driver": "protocol"},
                )
            )
            self.assertIsNotNone(account_setup_unavailable({"password"}, {"password_driver": "roxy"}))
            self.assertIsNotNone(
                account_setup_unavailable(
                    {"password"},
                    {"password_driver": "protocol"},
                    force_password_reset=True,
                )
            )

    def test_forced_password_change_keeps_browser_path(self):
        result, actions, _account, _fence = self.run_setup(force_reset=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual([("browser",)], actions)

    def test_browser_missing_entry_cache_does_not_block_protocol_password(self):
        account = {
            "access_token": "fixture-at",
            "extra_json": {
                "account_password_capability": {
                    "reason": "password_settings_entry_unavailable",
                    "evidence": "stable_settings_page",
                }
            },
        }
        settings = {
            "password_enabled": True,
            "password_driver": "protocol",
            "twofa_enabled": False,
            "plan_check_enabled": False,
            "codex_enabled": False,
        }
        plan = completion_plan(account, settings)
        self.assertEqual(["password"], plan["missing_steps"])
        self.assertEqual([], plan["blocked"])

    def test_mailbox_password_is_not_openai_password_in_planning_or_receipt(self):
        account = {"access_token": "fixture-at", "password": "fixture-mailbox-password"}
        plan = completion_plan(
            account,
            {
                "password_driver": "protocol",
                "password_enabled": True,
                "plan_check_enabled": False,
                "twofa_enabled": False,
                "codex_enabled": False,
            },
        )
        self.assertEqual(["password"], plan["missing_steps"])
        with patch.object(runtime.db, "get_account", return_value=account):
            confirmed, checks = runtime._account_setup_readback(42, "fixture@example.test", {"password"}, {})
        self.assertFalse(confirmed)
        self.assertEqual({"password": False}, checks)

    def test_protocol_password_progress_omits_browser_but_keeps_authentication(self):
        flow = flow_for("password_setup", {"data": {"config_snapshot": {"password_driver": "protocol"}}})
        self.assertEqual(["network", "authenticate", "set_password", "result"], [item["id"] for item in flow])

    def test_protocol_rejection_is_not_changed_to_unknown_receipt(self):
        state, _detail = runtime._account_setup_receipt(
            42,
            "fixture@example.test",
            {"password"},
            {
                "ok": False,
                "status": "failed",
                "password_driver": "protocol",
                "password_setup": {
                    "ok": False,
                    "status": "failed",
                    "remote_receipt_state": "rejected",
                    "mutation_submitted": True,
                },
            },
        )
        self.assertEqual("rejected", state)

    def test_protocol_preflight_failure_preserves_not_submitted_evidence(self):
        state, detail = runtime._account_setup_receipt(
            42,
            "fixture@example.test",
            {"password"},
            {
                "ok": False,
                "status": "failed",
                "password_driver": "protocol",
                "password_setup": {
                    "ok": False,
                    "status": "failed",
                    "mutation_submitted": False,
                    "remote_receipt_state": "none",
                },
            },
        )
        self.assertEqual("not_submitted", state)
        self.assertIs(False, detail["mutation_submitted"])
        self.assertIs(False, detail["action_dispatched"])

    def test_protocol_partial_success_checks_only_completed_mutations(self):
        result = {
            "ok": False,
            "status": "partial_success",
            "password_driver": "protocol",
            "password_setup": {"ok": True, "status": "success", "remote_receipt_state": "confirmed"},
            "twofa_setup": {"ok": False, "status": "failed", "remote_receipt_state": "rejected"},
        }
        with patch.object(
            runtime.db, "get_account", return_value={"extra_json": {"account_password": "fixture-password"}}
        ):
            state, detail = runtime._account_setup_receipt(42, "fixture@example.test", {"password", "twofa"}, result)
        self.assertEqual("confirmed", state)
        self.assertEqual({"password": True}, detail["local_readback_checks"])
        self.assertEqual("partial_success", runtime._safe_operation_result(result).status)

    def test_storage_preserves_only_password_policy_and_safe_outcome_metadata(self):
        value = operation_store._scrub(
            {
                "password_driver": "protocol",
                "password_enabled": True,
                "password_reset_enabled": False,
                "password_setup": {
                    "ok": True,
                    "status": "success",
                    "password": "fixture-raw-secret",
                    "password_driver": "protocol",
                },
                "account_password": "fixture-raw-secret",
                "login_password": "fixture-raw-secret",
                "password": "fixture-raw-secret",
                "local_readback_checks": {"password": True},
            }
        )
        self.assertEqual("protocol", value["password_driver"])
        self.assertTrue(value["password_setup"]["ok"])
        self.assertEqual({"password": True}, value["local_readback_checks"])
        self.assertNotIn("fixture-raw-secret", str(value))


class PasswordSetupDurableIntegrationTests(PostgresTestCase):
    def finish_partial(
        self,
        *,
        task_type="account_setup_retry",
        source="webui_runtime",
        saved=True,
        failed_state="rejected",
        omit_evidence=False,
        mailbox_password=False,
        reconcile=False,
    ):
        self.guard_case_no = getattr(self, "guard_case_no", 0) + 1
        email = f"guard-password-{self.guard_case_no}@example.test"
        account_id = records.insert_row(
            records.ACCOUNTS,
            {
                "email": email,
                "extra_json": {"account_password": "fixture-password"} if saved else {},
                **({"password": "fixture-mailbox-password"} if mailbox_password else {}),
            },
        )
        created = operation_store.create_runtime_task(
            task_type=task_type,
            account_id=account_id,
            email=email,
            source_system=source,
            resource_family="openai_interactive",
            data={"steps": ["password", "twofa"]},
        )
        run_id = int(created["run"]["id"])
        operation_store.claim_run(run_id, execution_id="fixture-owner", worker_pid=os.getpid())
        lease = operation_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        fence = {"execution_id": "fixture-owner", "lease_token": lease}
        operation_store.record_remote_intent(run_id, **fence, action="account_setup", request_id="fixture-setup")
        evidence = [
            {"step": "password", "ok": True, "receipt_state": "confirmed"},
            {"step": "twofa", "ok": False, "receipt_state": failed_state},
        ]
        operation_store.record_remote_receipt(
            run_id,
            **fence,
            outcome="confirmed",
            action="account_setup",
            request_id="fixture-setup",
            detail={
                "remote_result_confirmed": True,
                "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True,
                "setup_step_receipts": evidence,
            },
        )
        return operation_store.finish_run(
            run_id,
            **fence,
            status="partial_success",
            result_summary={
                "password_driver": "protocol",
                "setup_step_receipts": [] if omit_evidence else evidence,
                "reconcile_required": reconcile,
            },
        )

    def test_partial_guard_keeps_other_task_types_and_unconfirmed_evidence_protected(self):
        for change in (
            {"task_type": "registration"},
            {"task_type": "password_change"},
            {"source": "native_operations"},
            {"saved": False},
            {"failed_state": "unknown"},
            {"omit_evidence": True},
            {"saved": False, "mailbox_password": True},
            {"reconcile": True},
        ):
            with self.subTest(change=change):
                result = self.finish_partial(**change)
                self.assertEqual("attention_required", result["status"])

    def test_native_password_setup_passes_real_execution_and_account_lease_fence(self):
        account_id = records.insert_row(
            records.ACCOUNTS,
            {
                "email": "durable-password@example.test",
                "access_token": "fixture-at",
                "extra_json": {"account_password": "fixture-password"},
            },
        )
        observed = []

        def setup(_email, **kwargs):
            observed.append(kwargs)
            return {
                "ok": True,
                "status": "success",
                "password_driver": "protocol",
                "browser_opened": False,
                "password_setup": {
                    "ok": True,
                    "status": "success",
                    "remote_receipt_state": "confirmed",
                },
            }

        with ExitStack() as stack:
            stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
            for name in ("_OPERATION_HANDLERS", "_OPERATION_HANDLER_ALLOWLISTS", "_DISPATCH_HANDLERS"):
                stack.enter_context(patch.dict(getattr(task_gateway, name), {}))
            task_gateway.register_operation_handler(
                "password_setup",
                runtime._handle_native_account_setup,
                source_systems=("webui_runtime",),
                config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
            )
            stack.enter_context(patch.object(runtime.codex_retry_service, "run_twofa_worker", side_effect=setup))
            queued = task_gateway.submit_durable_operation(
                task_type="password_setup",
                account_id=account_id,
                email="durable-password@example.test",
                source_system="webui_runtime",
                source_id="fixture-password-setup",
                resource_family="openai_interactive",
                data={"steps": ["password"]},
                config_snapshot={"password_driver": "protocol"},
                config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
                dispatch=False,
            )
            result = task_gateway._execute_operation_handler("password_setup", int(queued["run_id"]))
        self.assertEqual("success", result["status"], result)
        self.assertEqual("protocol", observed[0]["password_driver_override"])
        self.assertEqual(queued["run_id"], observed[0]["execution_fence"]["run_id"])
        self.assertTrue(observed[0]["execution_fence"]["execution_id"])
        self.assertTrue(observed[0]["execution_fence"]["lease_token"])
        persisted = operation_store.get_run(int(queued["run_id"]))
        self.assertEqual("confirmed", persisted["data"]["remote_intent"]["receipt_state"])

    def test_native_confirmed_partial_keeps_step_evidence_and_partial_terminal(self):
        account_id = records.insert_row(
            records.ACCOUNTS,
            {
                "email": "partial-password@example.test",
                "access_token": "fixture-at",
                "extra_json": {"account_password": "fixture-password"},
            },
        )
        outcome = {
            "ok": False,
            "status": "partial_success",
            "password_driver": "protocol",
            "browser_opened": False,
            "password_setup": {
                "ok": True,
                "status": "success",
                "remote_receipt_state": "confirmed",
                "mutation_submitted": True,
            },
            "twofa_setup": {
                "ok": False,
                "status": "failed",
                "remote_receipt_state": "rejected",
                "mutation_submitted": True,
            },
        }
        with ExitStack() as stack:
            stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
            for name in ("_OPERATION_HANDLERS", "_OPERATION_HANDLER_ALLOWLISTS", "_DISPATCH_HANDLERS"):
                stack.enter_context(patch.dict(getattr(task_gateway, name), {}))
            task_gateway.register_operation_handler(
                "account_setup_retry",
                runtime._handle_native_account_setup,
                source_systems=("webui_runtime",),
                config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
            )
            stack.enter_context(patch.object(runtime.codex_retry_service, "run_twofa_worker", return_value=outcome))
            queued = task_gateway.submit_durable_operation(
                task_type="account_setup_retry",
                account_id=account_id,
                email="partial-password@example.test",
                source_system="webui_runtime",
                source_id="fixture-password-partial",
                resource_family="openai_interactive",
                data={"steps": ["password", "twofa"]},
                config_snapshot={"password_driver": "protocol", "twofa_driver": "protocol"},
                config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
                dispatch=False,
            )
            result = task_gateway._execute_operation_handler("account_setup_retry", int(queued["run_id"]))
        self.assertEqual("partial_success", result["database_status"], result)
        persisted = operation_store.get_run(int(queued["run_id"]))
        self.assertTrue(persisted["result_summary"]["password_setup"]["ok"])
        self.assertFalse(persisted["result_summary"]["twofa_setup"]["ok"])
