"""续跑取得 Token 后自动补密码，并持久关联原执行的真实结果。"""
from types import SimpleNamespace
from unittest.mock import patch

from core import account_task_store, db
from core.accounts import operation_handlers
from core.operations import task_gateway
from core.registration import service, standalone
from core.storage import records, registration
from core.storage.operations import store
from tests.support_pg import PostgresTestCase
from tests.support_settlement import install_native_settlement_fixture


class ResumePasswordCompletionTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(task_gateway, "notify_dispatch"))
        self.enterContext(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        store.reset_ready()
        store.init()
        self.settings = {
            "password_enabled": True, "password_driver": "protocol",
            "password_proxy_mode": "pool", "twofa_enabled": False,
            "plan_check_enabled": False, "codex_enabled": False,
        }
        self.enterContext(patch("config.account.completion_settings", return_value=self.settings))
        self.enterContext(patch.dict("os.environ", {"TURB_BROWSER_ENABLED": "false"}))
        self.email = "resume-completion@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "access_token": "fixture-token", "plan_check_status": "success",
            "extra_json": {"account_password": "fixture-candidate", "account_password_state": "candidate"},
        })
        self.root = db.create_job("outlook")
        db.update_job(self.root["id"], status="failed", email=self.email, account_id=self.account_id)
        registration.finish_run(registration.list_runs(self.root["attempt_id"])[0]["id"], status="failed")
        self.job, _ = db.create_retry_job(
            self.root["id"], job_type="registration_resume", email_source="outlook",
            email=self.email, account_id=self.account_id,
            data={"config_snapshot": {"password_enabled": True, "registration_driver": "protocol_oss_2"}},
        )
        self.run = registration.start_run(
            self.job["attempt_id"], job_id=self.job["id"], action_type="registration_resume",
            execution_id="fixture-resume", initial_status="running",
        )
        db.update_job(self.job["id"], status="running")
        parent = store.find_task_by_source("registration_chains", f"{self.root['id']}:registration_resume")
        self.parent_id = parent["id"]
        self.parent_run_id = store.get_task(self.parent_id, include_events=False)["last_run_id"]
        self.result = {
            "success": True, "registration_success": True, "core_persisted": True,
            "postprocess_success": False, "partial_success": True,
            "account_id": self.account_id, "email": self.email, "access_token": "fixture-token",
            "cause_code": "registration_password_unconfirmed", "error": "原密码尚未确认生效",
        }

    def invoke(self, *, driver="protocol_oss_2", enabled=True, result=None):
        context = SimpleNamespace(attempt_id=self.job["attempt_id"], run_id=self.run["id"],
                                  execution_id="fixture-resume", job_id=self.job["id"])
        with patch.object(service, "_THREAD_CTX", context):
            return standalone._run_registration_with_facts(
                lambda **kwargs: dict(self.result if result is None else result),
                {"email": self.email, "registration_options": {"password_enabled": enabled}},
                entrypoint="protocol_cli", driver_name=driver,
            )

    def tasks(self):
        return [item for item in store.list_tasks(page_size=100)["items"]
                if item["task_type"] == "password_setup"]

    def finish_auth(self, error="registration_password_unconfirmed: 原密码尚未确认生效"):
        registration.finish_run(self.run["id"], status="partial_success")
        db.update_job(self.job["id"], status="partial_success", error=error, completed_at="2026-11-17T01:08:00Z")

    def confirm_password(self):
        records.patch_row(records.ACCOUNTS, self.account_id, changes={
            "extra_json": {"account_password": "fixture-confirmed", "account_password_state": "confirmed"},
        })

    def parent(self):
        return store.get_task(self.parent_id, include_events=False)

    def register_runtime_handlers(self):
        from webui import runtime

        install_native_settlement_fixture(self)
        with patch.object(operation_handlers, "_RUNTIME_HANDLERS_REGISTERED", False):
            runtime._register_runtime_handlers()

    def test_each_registration_driver_queues_the_same_shared_password_task(self):
        for driver in ("protocol_oss_2", "roxy"):
            with self.subTest(driver=driver):
                self.invoke(driver=driver)
                tasks = self.tasks()
                self.assertEqual(1, len(tasks))
                child = store.get_task(tasks[0]["id"], include_events=False)
                self.assertEqual(self.parent_id, child["parent_task_id"])
                self.assertEqual(["password"], child["runs"][-1]["data"]["steps"])
                self.assertEqual("protocol", child["runs"][-1]["data"]["config_snapshot"]["password_driver"])

    def test_same_resume_never_automatically_retries_a_terminal_password_task(self):
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        child = self.tasks()[0]
        store.finish_run(child["last_run_id"], status="failed", error="password_setup_network_failed")
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        self.assertEqual(1, len(store.get_task(child["id"], include_events=False)["runs"]))

    def test_no_automatic_password_task_without_required_confirmed_core(self):
        for result, enabled in (
            ({**self.result, "core_persisted": False, "registration_success": False}, True),
            ({**self.result, "registration_pending": True}, True),
            (self.result, False),
        ):
            with self.subTest(result=result, enabled=enabled):
                self.invoke(result=result, enabled=enabled)
                self.assertEqual([], self.tasks())
        records.patch_row(records.ACCOUNTS, self.account_id, changes={"access_token": ""})
        self.invoke()
        self.assertEqual([], self.tasks())

    def test_confirmed_password_and_new_registration_do_not_trigger_completion(self):
        self.confirm_password()
        self.invoke()
        self.assertEqual([], self.tasks())
        records.patch_row(records.ACCOUNTS, self.account_id, changes={
            "extra_json": {"account_password": "fixture-candidate", "account_password_state": "candidate"},
        })
        registration.finish_run(self.run["id"], status="failed")
        self.run = registration.start_run(
            self.job["attempt_id"], action_type="registration", execution_id="fixture-resume",
            initial_status="running",
        )
        self.invoke()
        self.assertEqual([], self.tasks())

    def test_parent_waits_for_password_and_success_survives_projection_rebuild(self):
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        child = self.tasks()[0]
        self.finish_auth()
        self.assertEqual("waiting", self.parent()["status"])
        self.confirm_password()
        store.finish_run(child["last_run_id"], status="success")
        store.reset_ready()
        store.sync_registration_job(self.job["id"])
        parent = self.parent()
        self.assertEqual("success", parent["status"])
        self.assertFalse(parent["error_code"])
        self.assertFalse(parent["error_message"])
        self.assertEqual(self.parent_run_id, parent["last_run_id"])
        listed = next(item for item in store.list_tasks(status="success", page_size=100)["items"]
                      if item["id"] == self.parent_id)
        self.assertFalse(listed["error_code"])
        self.assertFalse(listed["error_message"])

    def test_automatic_task_executes_with_real_operation_fence_and_password_receipt(self):
        from webui import runtime

        self.register_runtime_handlers()
        self.invoke()
        self.finish_auth()
        child = self.tasks()[0]

        def worker(email, **kwargs):
            self.assertEqual(self.email, email)
            self.assertEqual({"password"}, kwargs["steps"])
            self.assertEqual("protocol", kwargs["execution_settings"]["password_driver"])
            fence = kwargs["execution_fence"]
            self.assertEqual(child["last_run_id"], fence["run_id"])
            self.assertTrue(fence["execution_id"])
            self.assertTrue(fence["lease_token"])
            self.confirm_password()
            receipt = {"ok": True, "status": "success", "remote_receipt_state": "confirmed",
                       "mutation_submitted": True, "password_added": True}
            return {"ok": True, "status": "success", "password_driver": "protocol",
                    "password_setup": receipt, "step_results": {"password": receipt}}

        with patch.object(runtime.codex_retry_service, "run_twofa_worker", side_effect=worker):
            result = task_gateway._execute_operation_handler("password_setup", child["last_run_id"])
        self.assertEqual("success", result["status"], result)
        self.assertEqual("success", self.parent()["status"])

    def test_queued_automatic_task_skips_remote_submission_if_password_was_confirmed(self):
        from webui import runtime

        self.register_runtime_handlers()
        self.invoke()
        self.finish_auth()
        child = self.tasks()[0]
        self.confirm_password()
        with patch.object(runtime.codex_retry_service, "run_twofa_worker",
                          side_effect=AssertionError("密码已确认后不应再次提交远端请求")):
            result = task_gateway._execute_operation_handler("password_setup", child["last_run_id"])
        self.assertEqual("success", result["status"], result)
        self.assertEqual("success", self.parent()["status"])

    def test_stopped_resume_cancels_queued_automatic_password_without_remote_submission(self):
        from webui import runtime

        self.register_runtime_handlers()
        self.invoke()
        self.finish_auth()
        child = self.tasks()[0]
        db.update_job(self.job["id"], status="stopped")
        with patch.object(runtime.codex_retry_service, "run_twofa_worker",
                          side_effect=AssertionError("原注册已停止，不应再提交自动补密码")):
            result = task_gateway._execute_operation_handler("password_setup", child["last_run_id"])
        self.assertEqual("cancelled", result["status"], result)
        self.assertEqual("stopped", self.parent()["status"])

    def test_child_manual_retry_restores_parent_waiting_and_can_finish_successfully(self):
        self.invoke()
        self.finish_auth()
        child = self.tasks()[0]
        store.finish_run(child["last_run_id"], status="failed", error="password_setup_network_failed")
        retried = store.retry_runtime_task(child["id"])
        self.assertEqual("waiting", self.parent()["status"])
        self.confirm_password()
        store.finish_run(retried["id"], status="success")
        self.assertEqual("success", self.parent()["status"])

    def test_task_success_without_confirmed_password_does_not_mark_parent_success(self):
        self.invoke()
        self.finish_auth()
        store.finish_run(self.tasks()[0]["last_run_id"], status="success")
        self.assertEqual("partial_success", self.parent()["status"])
        self.assertEqual("registration_completion_incomplete", self.parent()["error_code"])

    def test_progress_keeps_waiting_even_after_authentication_completion_event(self):
        self.invoke()
        db.finish_job_progress(self.job["id"], success=True)
        self.finish_auth()
        progress = store.get_run_progress(self.parent_id, self.parent_run_id)
        self.assertEqual("waiting", progress["outcome"]["status"])
        self.assertEqual(self.tasks()[0]["id"], progress["outcome"]["child_tasks"][0]["task_id"])

    def test_rebuilding_projection_does_not_duplicate_completion_events(self):
        self.invoke()
        self.finish_auth()
        self.confirm_password()
        store.finish_run(self.tasks()[0]["last_run_id"], status="success")
        before = store.get_task(self.parent_id)["events"]
        store.sync_registration_job(self.job["id"])
        after = store.get_task(self.parent_id)["events"]
        self.assertEqual(
            len([event for event in before if event["event_type"] == "task.completion_updated"]),
            len([event for event in after if event["event_type"] == "task.completion_updated"]),
        )

    def test_completion_refreshes_batch_without_perpetual_projection_queue(self):
        self.invoke()
        self.finish_auth()
        self.confirm_password()
        store.finish_run(self.tasks()[0]["last_run_id"], status="success")
        completed_at = self.parent()["completed_at"]
        store.sync_registration_job(self.job["id"])
        self.assertEqual(completed_at, self.parent()["completed_at"])
        store.drain_projection_queue(limit=20)
        self.assertEqual([], store.drain_projection_queue(limit=20))
        batch_id = self.parent()["batch_id"]
        batch = next(row for row in store.list_batches() if row["id"] == batch_id)
        self.assertEqual(1, batch["success_count"])

    def test_cancelling_resume_does_not_create_an_automatic_password_task(self):
        db.update_job(self.job["id"], status="stopping")
        self.invoke()
        self.assertEqual([], self.tasks())

    def test_queue_failure_keeps_registration_core_and_reports_classified_error(self):
        from core.storage.operations import registration_completion

        with patch.object(registration_completion, "enqueue", side_effect=RuntimeError("合成存储异常")):
            result = self.invoke()
        self.assertTrue(result["core_persisted"])
        self.assertTrue(result["registration_success"])
        self.assertEqual("registration_completion_dispatch_failed", result["cause_code"])
        self.assertEqual("fixture-token", db.get_account(self.account_id)["access_token"])

    def test_password_failure_keeps_token_and_reports_child_error(self):
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        child = self.tasks()[0]
        self.finish_auth()
        store.finish_run(child["last_run_id"], status="failed", error="password_setup_network_failed")
        parent = self.parent()
        self.assertEqual("partial_success", parent["status"])
        self.assertEqual("password_setup_network_failed", parent["error_code"])
        self.assertEqual("fixture-token", db.get_account(self.account_id)["access_token"])
        self.invoke()
        self.assertEqual(1, len(store.get_task(child["id"], include_events=False)["runs"]))

    def test_successful_password_does_not_hide_another_postprocess_failure(self):
        self.result["error"] = "Codex 未完成：网络超时; 原密码尚未确认生效"
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        self.finish_auth(error=self.result["error"])
        self.confirm_password()
        store.finish_run(self.tasks()[0]["last_run_id"], status="success")
        parent = self.parent()
        self.assertEqual("partial_success", parent["status"])
        self.assertIn("Codex 未完成", parent["error_message"])
        self.assertNotIn("原密码尚未确认", parent["error_message"])

    def test_existing_manual_password_task_is_reused(self):
        queued = task_gateway.submit_durable_operation(
            task_type="password_setup", account_id=self.account_id, email=self.email,
            source_system="webui_runtime", source_id="manual-password",
            data={"steps": ["password"]},
        )
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        self.finish_auth()
        self.confirm_password()
        store.finish_run(queued["run_id"], status="success")
        self.assertEqual("success", self.parent()["status"])

    def test_interrupted_reused_child_updates_waiting_parent_on_startup(self):
        queued = task_gateway.submit_durable_operation(
            task_type="password_setup", account_id=self.account_id, email=self.email,
            source_system="webui_runtime", source_id="manual-interrupted-password",
            data={"steps": ["password"]},
        )
        self.invoke()
        self.finish_auth()
        self.assertEqual("waiting", self.parent()["status"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET status='running',heartbeat_at=now()-interval '1 hour' WHERE id=%s""",
                        (queued["run_id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='running' WHERE id=%s",
                        (queued["task_id"],))
        store.recover_interrupted_runtime_runs(stale_after_seconds=1)
        self.assertEqual("interrupted", store.get_run(queued["run_id"])["status"])
        self.assertEqual("partial_success", self.parent()["status"])
        self.assertEqual("worker_interrupted", self.parent()["error_code"])

    def test_unrelated_account_operation_does_not_lose_the_automatic_queue_item(self):
        task_gateway.submit_durable_operation(
            task_type="token_refresh", account_id=self.account_id, email=self.email,
            source_id="active-refresh",
        )
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        run = store.get_run(self.tasks()[0]["last_run_id"])
        scopes = task_gateway._operation_admission_arguments(run)["extra_scopes"]
        self.assertIn({"kind": "account", "key": f"{self.account_id}:openai_interactive", "limit": 1}, scopes)

    def test_late_child_does_not_overwrite_a_newer_registration_resume(self):
        self.invoke()
        self.assertEqual(1, len(self.tasks()))
        child = self.tasks()[0]
        self.finish_auth()
        db.create_retry_job(
            self.job["id"], job_type="registration_resume", email_source="outlook",
            email=self.email, account_id=self.account_id,
        )
        newest_run_id = self.parent()["last_run_id"]
        self.assertNotEqual(self.parent_run_id, newest_run_id)
        self.confirm_password()
        store.finish_run(child["last_run_id"], status="success")
        store.sync_registration_job(self.job["id"])
        parent = self.parent()
        self.assertEqual(newest_run_id, parent["last_run_id"])
        self.assertEqual("queued", parent["status"])

    def test_old_waiting_completion_cannot_hide_a_newer_terminal_resume(self):
        self.invoke()
        self.finish_auth()
        newer, _ = db.create_retry_job(
            self.job["id"], job_type="registration_resume", email_source="outlook",
            email=self.email, account_id=self.account_id,
        )
        latest_id = self.parent()["last_run_id"]
        self.confirm_password()
        db.update_job(newer["id"], status="success", error="", completed_at="2026-11-17T01:20:00Z")
        parent = self.parent()
        self.assertEqual(latest_id, parent["last_run_id"])
        self.assertEqual("success", parent["status"])
