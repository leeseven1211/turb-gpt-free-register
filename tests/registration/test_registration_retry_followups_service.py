"""注册重试把不同补跑动作规划为集合，再交原生队列执行。"""
from unittest.mock import patch

from core import db
from core.accounts.plans import service as plan_service
from core.codex import operation_service as codex_service
from core.operations import task_gateway
from core.registration import service
from core.storage import records, registration
from core.storage.operations import store
from core.storage.operations import legacy_task_store
from core.storage.registration import retry_followups
from tests.support_pg import PostgresTestCase


class RegistrationRetryFollowupsServiceTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()

    def source(self, index, *, action, linked=True):
        email = f"retry-service-{index}@example.test"
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": email, "access_token": "fixture-private-at",
            "codex_status": "failed" if action == "codex" else "success",
            "plan_check_status": "failed" if action == "plan_check" else "success",
            "totp_secret": "" if action == "twofa" else "fixture-totp",
            "extra_json": {"account_password": "fixture-password", "account_password_state": "confirmed"},
        })
        snapshot = {"registration_driver": "protocol_oss_2", "password_enabled": True,
                    "twofa_enabled": True, "plan_check_enabled": True, "codex_enabled": True}
        if linked:
            job = db.create_job("outlook", batch_id=f"service-followup-{index}",
                                data={"config_snapshot": snapshot})
            db.update_job(job["id"], email=email, account_id=account_id, status="partial_success")
            registration.finish_run(registration.list_runs(job["attempt_id"])[0]["id"], status="partial_success")
        else:
            row = db._new_job_row(email_source="outlook", email=email, account_id=account_id,
                                  data={"config_snapshot": snapshot})
            row["status"] = "partial_success"
            job = {"id": records.insert_row(records.JOBS, row)}
        return db.get_job(job["id"])

    def retry(self, sources):
        with (
            patch.object(plan_service, "enqueue_account_plan_check", side_effect=AssertionError("per-item plan enqueue")),
            patch.object(codex_service, "submit", side_effect=AssertionError("per-item Codex enqueue")),
            patch.object(service, "_submit_registration_account_setup",
                         wraps=service._submit_registration_account_setup),
            patch.object(task_gateway, "submit_durable_operation", side_effect=AssertionError("per-item durable enqueue")),
            patch.object(codex_service, "_config_snapshot", return_value={"oauth_driver": "protocol"}),
            patch.object(codex_service, "_deployment_unavailable", return_value=None),
            patch.object(codex_service, "_feature_ready", return_value=(True, "")),
            patch("core.runtime.capabilities.account_setup_unavailable", return_value=None),
            patch.object(plan_service, "register_operation_handlers", side_effect=AssertionError("API installs plan handler")),
            patch.object(codex_service, "register_handler", side_effect=AssertionError("API installs Codex handler")),
            patch.object(task_gateway, "start_dispatcher", side_effect=AssertionError("API starts worker dispatcher")),
            patch.object(task_gateway, "notify_dispatch") as notify,
            patch.object(retry_followups, "admit", wraps=retry_followups.admit) as admit,
        ):
            results = service.retry_jobs([row["id"] for row in sources], workers=7, debug_enabled=True)
        self.assertEqual(1, admit.call_count)
        notify.assert_called_once()
        return results, admit.call_args.args[0]

    def test_mixed_actions_keep_original_data_parent_and_debug_results(self):
        records.init()
        sources = [self.source(index, action=action)
                   for index, action in enumerate(("plan_check", "codex", "twofa"), 1)]
        results, plans = self.retry(sources)
        self.assertEqual(["plan_check", "codex", "twofa"], [plan.action for plan in plans])
        for source, plan in zip(sources, plans):
            result = results[source["id"]]
            self.assertTrue(result["ok"], result)
            self.assertTrue(result["created"], result)
            run = store.get_run(result["run_id"])
            task = store.get_task(result["operation_task_id"], include_events=False)
            self.assertEqual(source["account_id"], task["account_id"])
            self.assertNotIn("fixture-private-at", str(run["data"]))
            self.assertFalse(result["debug_enabled"])
            if plan.action == "plan_check":
                self.assertNotIn("countries", run["data"])
                self.assertEqual("-", run["data"]["timezone_offset_min"])
                self.assertEqual("registration_retry_plan_check", task["trigger"])
                self.assertIsNone(task["parent_task_id"])
            else:
                parent = store.find_task_by_source("registration_jobs", str(source["id"]), include_runs=True)
                self.assertEqual(parent["id"], task["parent_task_id"])
            if plan.action == "twofa":
                self.assertEqual(["twofa"], run["data"]["steps"])
                self.assertEqual("protocol", run["data"]["config_snapshot"]["twofa_driver"])
                self.assertEqual(source["attempt_id"], run["data"]["registration_attempt_id"])

    def test_legacy_unlinked_account_uses_the_same_collection_followup(self):
        records.init()
        source = self.source(1, action="codex", linked=False)
        results, plans = self.retry([source])
        self.assertTrue(results[source["id"]]["ok"], results)
        self.assertEqual("codex", plans[0].action)
        self.assertIsNone(source.get("attempt_id"))

    def test_setup_terminal_retries_append_to_the_original_task(self):
        records.init()
        source = self.source(1, action="twofa")
        first, _ = self.retry([source])
        first_result = first[source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                        (first_result["run_id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                        (first_result["operation_task_id"],))
        second, _ = self.retry([db.get_job(source["id"])])
        second_result = second[source["id"]]
        self.assertTrue(second_result["ok"], second_result)
        self.assertEqual(first_result["operation_task_id"], second_result["operation_task_id"])
        self.assertNotEqual(first_result["run_id"], second_result["run_id"])
        self.assertEqual(2, store.get_run(second_result["run_id"])["run_no"])

    def test_storage_failure_returns_each_source_without_worker_wake_or_internal_details(self):
        records.init()
        source = self.source(1, action="codex")
        with (
            patch.object(codex_service, "_config_snapshot", return_value={"oauth_driver": "protocol"}),
            patch.object(codex_service, "_deployment_unavailable", return_value=None),
            patch.object(codex_service, "_feature_ready", return_value=(True, "")),
            patch.object(retry_followups, "admit", side_effect=RuntimeError("private-database-details")),
            patch.object(task_gateway, "notify_dispatch") as notify,
        ):
            results = service.retry_jobs([source["id"]], workers=3)
        result = results[source["id"]]
        self.assertFalse(result["ok"])
        self.assertEqual(503, result["status"])
        self.assertNotIn("private-database-details", str(result))
        notify.assert_not_called()
