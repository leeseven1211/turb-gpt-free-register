"""账号入口只适配原注册任务，不另建注册流程。"""
import importlib
import uuid
from unittest.mock import Mock, patch

from core import db
from core.codex import operation_service as codex_operation_service
from core.registration import service as registration_service
from core.storage import postgres, records, registration
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountRegistrationRetryTests(PostgresTestCase):
    def setUp(self):
        records.init()
        registration.init()
        self.client = create_app(auth_code="retry-test").test_client()
        self.headers = {"X-Auth-Code": "retry-test"}

    def _account(self, email="pending@example.test", **changes):
        return records.insert_row(records.ACCOUNTS, {
            "email": email, "access_token": "", "codex_status": "failed",
            "extra_json": {"registration_checkpoint": "email_verification_pending", "account_password": "private-password"},
            **changes,
        })

    def _chain(self, account_id, *, email="pending@example.test", job_account=True, status="failed"):
        job_id = records.insert_row(records.JOBS, {
            "job_uuid": str(uuid.uuid4()), "job_type": "registration", "email": email,
            "email_source": "outlook", "account_id": account_id if job_account else None,
            "status": status,
        })
        attempt = registration.create_attempt(email, email_source="outlook", root_job_id=job_id)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('registration_attempts')} SET account_id=%s, "
                        "checkpoint='password_confirmed', target_status='email_verification_pending' WHERE id=%s",
                        (account_id, attempt["id"]))
        records.patch_row(records.JOBS, job_id, {"attempt_id": attempt["id"]})
        return job_id, attempt["id"]

    def _child(self, root, attempt, account_id, *, status="failed"):
        return records.insert_row(records.JOBS, {
            "job_uuid": str(uuid.uuid4()), "job_type": "registration_resume",
            "root_job_id": root, "parent_job_id": root, "attempt_id": attempt,
            "account_id": account_id, "email": "pending@example.test", "email_source": "outlook",
            "status": status,
        })

    def _projection(self, account_id):
        response = self.client.get("/api/accounts", query_string={"paged": 1}, headers=self.headers)
        self.assertEqual(200, response.status_code)
        row = next(row for row in response.get_json()["items"] if row["id"] == account_id)
        return row.get("registration_retry")

    def _post(self, account_id):
        return self.client.post(f"/api/accounts/{account_id}/registration-retry", json={}, headers=self.headers)

    def test_single_route_continues_original_registration_and_whitelists_result(self):
        account = self._account()
        job, _ = self._chain(account)
        with patch.object(registration_service, "retry_job", return_value={
            "ok": True, "created": True, "job": {"id": 81, "access_token": "private-token"},
            "source_job_id": job, "retry_action": "registration_resume", "message": "已创建",
            "operation_task_id": 91, "run_id": 92, "private_context": "private",
        }) as execute:
            response = self._post(account)
        self.assertEqual(202, response.status_code)
        result = response.get_json()
        self.assertEqual(1, result["started_count"])
        self.assertEqual({"account_id": account, "job_id": 81, "source_job_id": job,
                          "retry_action": "registration_resume", "message": "已创建",
                          "operation_task_id": 91, "run_id": 92}, result["started"][0])
        execute.assert_called_once_with(job)
        self.assertNotIn("private", str(result))

    def test_list_finds_original_attempt_when_job_account_id_is_empty(self):
        account = self._account()
        root, _ = self._chain(account, job_account=False)
        self.assertEqual({"available": True, "source_job_id": root, "action": "registration_resume",
                          "label": "继续邮箱验证", "reason": "注册尚未完成；复用原邮箱和已保存密码继续同一账号验证",
                          "active": False}, self._projection(account))

    def test_no_source_and_imported_accounts_have_no_registration_action(self):
        account = self._account()
        projection = self._projection(account)
        self.assertIsInstance(projection, dict)
        self.assertFalse(projection["available"])
        self.assertIn("原注册", projection["reason"])
        with patch.object(registration_service, "retry_job") as execute:
            result = self._post(account).get_json()
        self.assertEqual(account, result["skipped"][0]["account_id"])
        execute.assert_not_called()

    def test_latest_child_is_selected_instead_of_old_failure(self):
        account = self._account()
        root, attempt = self._chain(account)
        child = self._child(root, attempt, account)
        self.assertEqual(child, self._projection(account)["source_job_id"])

    def test_later_success_prevents_old_failed_registration_from_resuming(self):
        account = self._account(access_token="valid-token", codex_status="success", totp_secret="test-secret",
                                plan_check_status="success")
        root, attempt = self._chain(account)
        self._child(root, attempt, account, status="success")
        self.assertFalse(self._projection(account)["available"])
        with patch.object(registration_service, "retry_job") as execute:
            result = self._post(account).get_json()
        self.assertEqual(1, result["skipped_count"])
        execute.assert_not_called()

    def test_active_chain_is_reused_without_dispatching_another_run(self):
        account = self._account()
        root, attempt = self._chain(account)
        child = self._child(root, attempt, account, status="running")
        projection = self._projection(account)
        self.assertTrue(projection["active"])
        self.assertFalse(projection["available"])
        with patch.object(registration_service, "retry_job") as execute:
            result = self._post(account).get_json()
        self.assertEqual(child, result["reused"][0]["job_id"])
        self.assertEqual(0, result["started_count"])
        self.assertEqual(1, result["reused_count"])
        execute.assert_not_called()

    def test_two_distinct_attempts_never_choose_an_arbitrary_old_failure(self):
        account = self._account()
        self._chain(account)
        self._chain(account)
        projection = self._projection(account)
        self.assertFalse(projection["available"])
        self.assertIn("多个", projection["reason"])

    def test_wrong_email_binding_is_not_a_registration_source(self):
        account = self._account()
        self._chain(account, email="someone-else@example.test")
        projection = self._projection(account)
        self.assertFalse(projection["available"])

    def test_bulk_deduplicates_accounts_and_keeps_skips(self):
        account = self._account()
        job, _ = self._chain(account)
        missing = self._account("no-job@example.test")
        with patch.object(registration_service, "retry_job", return_value={
            "ok": True, "created": True, "job": {"id": 81}, "retry_action": "registration_resume", "message": "已创建",
        }) as execute:
            response = self.client.post("/api/accounts/registration-retry-bulk", json={
                "account_ids": [account, account, missing, 999999],
            }, headers=self.headers)
        result = response.get_json()
        self.assertEqual(202, response.status_code)
        self.assertEqual(1, result["started_count"])
        self.assertEqual(2, result["skipped_count"])
        execute.assert_called_once_with(job)

    def test_malformed_bulk_and_single_bodies_are_rejected(self):
        with patch.object(registration_service, "retry_job") as execute:
            for payload in ([], {}, {"account_ids": []}, {"account_ids": "1"}, {"account_ids": [True]},
                            {"account_ids": [0]}, {"account_ids": [1.5]}, {"account_ids": [2**63]},
                            {"account_ids": list(range(1, 502))}):
                with self.subTest(payload=payload):
                    response = self.client.post("/api/accounts/registration-retry-bulk", json=payload, headers=self.headers)
                    self.assertEqual(400, response.status_code)
            self.assertEqual(400, self.client.post("/api/accounts/1/registration-retry", json=[], headers=self.headers).status_code)
        execute.assert_not_called()

    def test_both_commands_require_existing_authentication(self):
        for url in ("/api/accounts/1/registration-retry", "/api/accounts/registration-retry-bulk"):
            self.assertEqual(401, self.client.post(url, json={"account_ids": [1]}).status_code)

    def test_click_reloads_latest_source_after_list_was_rendered(self):
        account = self._account()
        root, attempt = self._chain(account)
        self.assertTrue(self._projection(account)["available"])
        child = self._child(root, attempt, account, status="pending")
        with patch.object(registration_service, "retry_job") as execute:
            result = self._post(account).get_json()
        self.assertEqual(child, result["reused"][0]["job_id"])
        execute.assert_not_called()

    def test_projection_failure_does_not_break_account_listing(self):
        account = self._account()
        module = importlib.import_module("core.accounts.registration_retry")
        with patch.object(module, "project_accounts", side_effect=RuntimeError("private db detail")):
            projection = self._projection(account)
        self.assertFalse(projection["available"])
        self.assertNotIn("private", str(projection))

    def test_account_completion_stays_an_independent_action(self):
        account = self._account()
        self._chain(account)
        with patch("webui.runtime.WebUIContext.enqueue_account_completion", return_value={
            "accepted": True, "task_id": 81,
        }) as complete, patch.object(registration_service, "retry_job") as execute:
            client = create_app(auth_code="retry-test").test_client()
            result = client.post(f"/api/accounts/{account}/action", json={"action": "complete"}, headers=self.headers)
        self.assertEqual(202, result.status_code)
        self.assertEqual(81, result.get_json()["task_id"])
        complete.assert_called_once()
        execute.assert_not_called()

    def test_real_retry_creates_child_on_original_attempt_without_running_worker(self):
        account = self._account()
        root, attempt = self._chain(account)
        records.patch_row(records.JOBS, root, {"data": {"config_snapshot": {"registration_driver": "protocol"}}})
        with patch.object(registration_service, "get_executor", return_value=Mock()):
            response = self._post(account)
        self.assertEqual(202, response.status_code)
        created = response.get_json()["started"][0]
        child = db.get_job(created["job_id"])
        self.assertNotEqual(root, child["id"])
        self.assertEqual(root, child["root_job_id"])
        self.assertEqual(account, child["account_id"])
        self.assertEqual(attempt, child["attempt_id"])
        self.assertEqual("registration_resume", child["job_type"])

    def test_active_attempt_with_no_job_account_or_email_is_still_reused(self):
        account = self._account()
        root, _ = self._chain(account, job_account=False, status="running")
        records.patch_row(records.JOBS, root, {"email": ""})
        self.assertTrue(self._projection(account)["active"])
        with patch.object(registration_service, "retry_job") as execute:
            result = self._post(account).get_json()
        self.assertEqual(root, result["reused"][0]["job_id"])
        execute.assert_not_called()

    def test_read_failure_returns_actionable_skip_instead_of_server_error(self):
        account = self._account()
        module = importlib.import_module("core.accounts.registration_retry")
        with patch.object(module, "project_accounts", side_effect=RuntimeError("private db detail")):
            response = self._post(account)
        self.assertEqual(200, response.status_code)
        result = response.get_json()
        self.assertEqual(1, result["skipped_count"])
        self.assertNotIn("private", str(result))

    def test_compact_projection_never_forwards_extra_registration_fields(self):
        from webui.route_helpers import _compact_account_for_list
        result = _compact_account_for_list({"id": 1, "registration_retry": {
            "available": True, "source_job_id": 2, "action": "registration_resume",
            "label": "继续注册", "reason": "", "active": False, "private_context": "must-stay-private",
        }})
        self.assertEqual(6, len(result["registration_retry"]))
        self.assertNotIn("must-stay-private", str(result))

    def test_job_account_link_can_resolve_attempt_without_attempt_account_link(self):
        account = self._account()
        root, attempt = self._chain(account)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('registration_attempts')} SET account_id=NULL WHERE id=%s", (attempt,))
        projection = self._projection(account)
        self.assertTrue(projection["available"])
        self.assertEqual(root, projection["source_job_id"])

    def test_missing_root_never_uses_child_as_an_unrelated_registration(self):
        account = self._account()
        root, attempt = self._chain(account)
        self._child(root, attempt, account)
        records.delete_rows(records.JOBS, [root])
        self.assertFalse(self._projection(account)["available"])

    def test_deactivated_account_cannot_resume_a_matching_registration(self):
        account = self._account(account_status="deactivated")
        self._chain(account)
        self.assertFalse(self._projection(account)["available"])
        with patch.object(registration_service, "retry_job") as execute:
            result = self._post(account).get_json()
        self.assertIn("废号", result["skipped"][0]["reason"])
        execute.assert_not_called()

    def test_projection_connection_count_does_not_grow_per_account(self):
        module = importlib.import_module("core.accounts.registration_retry")
        accounts = []
        for index in range(8):
            email = f"bounded-{index}@example.test"
            account = self._account(email)
            self._chain(account, email=email)
            accounts.append({"id": account})
        module.project_accounts(accounts)
        with patch.object(postgres, "connect", wraps=postgres.connect) as connections:
            small = module.project_accounts(accounts[:1])
            small_count = connections.call_count
        with patch.object(postgres, "connect", wraps=postgres.connect) as connections:
            large = module.project_accounts(accounts)
            large_count = connections.call_count
        self.assertTrue(small[accounts[0]["id"]]["available"])
        self.assertTrue(all(item["available"] for item in large.values()))
        self.assertGreater(small_count, 0)
        self.assertEqual(small_count, large_count)

    def test_active_twofa_child_is_reused_as_part_of_original_registration_chain(self):
        account = self._account(access_token="valid-token", codex_status="success", plan_check_status="success")
        root, attempt = self._chain(account)
        child = self._child(root, attempt, account, status="running")
        records.patch_row(records.JOBS, child, {"job_type": "twofa_retry"})
        projection = self._projection(account)
        self.assertTrue(projection["active"])
        self.assertFalse(projection["available"])
        self.assertEqual(child, projection["source_job_id"])
        with patch.object(registration_service, "retry_job") as execute:
            response = self._post(account)
        result = response.get_json()
        self.assertEqual(1, result["reused_count"])
        self.assertEqual(child, result["reused"][0]["job_id"])
        execute.assert_not_called()

    def test_postprocessing_history_does_not_replace_original_registration_source(self):
        account = self._account(access_token="valid-token", codex_status="success", plan_check_status="success")
        root, attempt = self._chain(account)
        child = self._child(root, attempt, account)
        records.patch_row(records.JOBS, child, {"job_type": "twofa_retry"})
        projection = self._projection(account)
        self.assertFalse(projection["active"])
        self.assertEqual(root, projection["source_job_id"])
        self.assertEqual("twofa", projection["action"])

    def test_unrelated_active_account_action_is_not_a_registration_chain(self):
        account = self._account()
        root, _ = self._chain(account)
        records.insert_row(records.JOBS, {
            "job_uuid": str(uuid.uuid4()), "job_type": "twofa_retry", "account_id": account,
            "status": "running", "email": "pending@example.test",
        })
        projection = self._projection(account)
        self.assertFalse(projection["active"])
        self.assertEqual(root, projection["source_job_id"])

    def test_real_codex_busy_result_keeps_existing_task_and_run_in_reused(self):
        account = self._account(access_token="valid-token", codex_status="failed", plan_check_status="success",
                                totp_secret="test-secret")
        self._chain(account)
        with patch.object(codex_operation_service, "submit", return_value={
            "accepted": False, "busy": True, "task_id": 91, "run_id": 92,
            "error": "该账号已有排队或运行中的账号操作", "status": "running",
        }):
            response = self._post(account)
        result = response.get_json()
        self.assertEqual(202, response.status_code)
        self.assertEqual(0, result["started_count"])
        self.assertEqual(0, result["skipped_count"])
        self.assertEqual(1, result["reused_count"])
        item = result["reused"][0]
        self.assertEqual(91, item["task_id"])
        self.assertEqual(92, item["run_id"])
        self.assertEqual("codex", item["retry_action"])
        self.assertIn("已有", item["message"])
