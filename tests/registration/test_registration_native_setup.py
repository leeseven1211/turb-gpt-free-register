"""原注册缺项使用真实原生 Run 和账号租约，禁止把其它活动操作当作补全成功。"""
from contextlib import ExitStack
from unittest.mock import patch

from core import db, account_task_store
from core.registration import service
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import store
from tests.support_pg import PostgresTestCase
from webui import runtime


class RegistrationNativeSetupTests(PostgresTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.stack.enter_context(patch("config.account.ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", False))
        self.stack.enter_context(patch.dict("os.environ", {"TURB_BROWSER_ENABLED": "false"}))
        self.stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": "required-password@example.test", "access_token": "fixture-at",
            "totp_secret": "fixture-totp", "plan_check_status": "success",
        })
        self.source = {"id": 91, "attempt_id": 11, "email": "required-password@example.test"}
        self.snapshot = {"registration_driver": "protocol_oss_2", "password_enabled": True,
                         "twofa_enabled": True, "twofa_driver": "protocol", "plan_check_enabled": True}
        with patch.object(runtime, "_RUNTIME_HANDLERS_REGISTERED", False):
            runtime._register_runtime_handlers()

    def submit(self, snapshot=None):
        return service._submit_registration_account_setup(
            self.source, db.get_account(self.account_id), snapshot or self.snapshot,
        )

    def test_protocol_repair_executes_with_real_run_and_lease_without_browser(self):
        queued = self.submit()
        self.assertTrue(queued["ok"], queued)
        run = store.get_run(queued["run_id"])
        self.assertEqual(["password"], run["data"]["steps"])
        self.assertEqual("protocol", run["data"]["config_snapshot"]["password_driver"])

        def worker(email, **kwargs):
            fence = kwargs["execution_fence"]
            self.assertEqual(queued["run_id"], fence["run_id"])
            self.assertTrue(fence["execution_id"])
            self.assertTrue(fence["lease_token"])
            records.patch_row(records.ACCOUNTS, self.account_id, changes={
                "extra_json": {"account_password": "fixture-confirmed", "account_password_state": "confirmed"},
            })
            outcome = {"ok": True, "status": "success", "remote_receipt_state": "confirmed",
                       "mutation_submitted": True, "password_added": True}
            return {"ok": True, "status": "success", "password_driver": "protocol",
                    "password_setup": outcome, "step_results": {"password": outcome}}

        with patch.object(runtime.codex_retry_service, "run_twofa_worker", side_effect=worker):
            result = task_gateway._execute_operation_handler("account_setup_retry", queued["run_id"])
        self.assertEqual("success", result["status"], result)
        self.assertEqual("success", store.get_run(queued["run_id"])["status"])
        self.assertTrue(db.get_account(self.account_id)["totp_secret"])

    def test_unrelated_active_task_is_not_reported_as_successful_setup_submission(self):
        store.create_runtime_task(task_type="token_refresh", account_id=self.account_id,
                                  email=self.source["email"], source_system="native_operations",
                                  source_id="other-auth", resource_family="openai_interactive")
        result = self.submit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(409, result["status"])
        self.assertIn("尚未入队", result["error"])
        self.assertIsNone(store.find_task_by_source("webui_runtime", "registration-account-setup:91"))

    def test_terminal_retry_captures_new_driver_and_country_in_same_task(self):
        first = self.submit()
        store.finish_run(first["run_id"], status="failed", error="fixture-network")
        snapshot = dict(self.snapshot, registration_driver="roxy", twofa_driver="browser",
                        retry_proxy_country_override="JP")
        with patch.dict("os.environ", {"TURB_BROWSER_ENABLED": "true"}):
            second = self.submit(snapshot)
        self.assertTrue(second["ok"], second)
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        run = store.get_run(second["run_id"])
        self.assertEqual("JP", run["data"]["proxy_country_override"])
        self.assertEqual("roxy", run["data"]["config_snapshot"]["password_driver"])
        self.assertEqual(["password"], run["data"]["required_steps"])

    def test_same_active_repair_is_reused_without_new_run(self):
        first = self.submit()
        second = self.submit()
        self.assertTrue(second["ok"], second)
        self.assertTrue(second["reused"])
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(1, len(store.get_task(first["task_id"])["runs"]))

    def test_terminal_setup_retry_reports_an_unrelated_new_active_run_as_conflict(self):
        first = self.submit()
        store.finish_run(first["run_id"], status="failed", error="fixture-network")
        store.create_runtime_task(task_type="token_refresh", account_id=self.account_id,
                                  email=self.source["email"], source_system="native_operations",
                                  source_id="new-active-refresh", resource_family="openai_interactive")
        result = self.submit()
        self.assertFalse(result["ok"], result)
        self.assertEqual(409, result["status"])
        self.assertTrue(result["busy"])
        self.assertEqual(1, len(store.get_task(first["task_id"])["runs"]))

    def test_account_bulk_does_not_count_unrelated_busy_as_a_reused_repair(self):
        from core.accounts import registration_retry

        projection = {self.account_id: {"active": False, "available": True,
                                      "source_job_id": self.source["id"], "action": "twofa"}}
        with patch.object(registration_retry, "project_accounts", return_value=projection), patch.object(
            registration_retry.registration_service, "retry_job", return_value={
                "ok": False, "busy": True, "error": "密码缺项尚未入队，可稍后重跑",
            },
        ):
            result = registration_retry.retry_accounts([self.account_id])
        self.assertEqual(0, result["reused_count"])
        self.assertEqual(0, result["started_count"])
        self.assertEqual(1, result["skipped_count"])
