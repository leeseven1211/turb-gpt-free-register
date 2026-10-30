"""补全派生 Codex 在执行前等待同账号注册结束。"""

import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from core import account_completion_service, account_task_store, codex_oauth
from core import codex_operation_service as service
from core import record_store, task_run_log
from tests.support_pg import PostgresTestCase


class CodexCompletionRegistrationGuardTests(PostgresTestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        log_root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(task_run_log, "_LOG_ROOT", log_root))
        stack.enter_context(patch.object(task_run_log, "_TASK_LOG_ROOT", log_root / "tasks"))
        stack.enter_context(patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": self.schema}))
        stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        stack.enter_context(patch.object(service, "_feature_ready", return_value=(True, "")))
        stack.enter_context(patch.object(service, "_config_snapshot", return_value={"oauth_driver": "protocol"}))
        account_task_store.init()
        self.email = "completion-codex@example.test"
        self.account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": self.email,
            "account_status": "active",
        })

    def _submit(self, *, completion_auth=None):
        options = {} if completion_auth is None else {"completion_auth": completion_auth}
        submitted = service.submit(self.email, dispatch=False, **options)
        self.assertTrue(submitted["accepted"], submitted)
        return submitted

    def _execute(self, submitted, *, active_job, oauth_error=None):
        route = Mock(proxy_url=None, provider="test", mode="direct", region="")
        route.public_dict.return_value = {"network_route": "test-direct"}
        with (
            patch.object(account_completion_service, "active_registration_job", return_value=active_job) as active,
            patch("core.account_proxy.acquire_account_proxy", return_value=route) as network,
            patch.object(codex_oauth, "run_codex_oauth", return_value={
                "ok": True,
                "status": "success",
                "credential_confirmed": True,
                "message": "Codex 凭证已保存",
            }, side_effect=oauth_error) as oauth,
        ):
            returned = service._execute_run(int(submitted["run_id"]))
        return returned, active, network, oauth

    def test_completion_auth_scope_is_saved_in_durable_run(self):
        submitted = self._submit(completion_auth=True)

        run = service.operation_task_store.get_run(int(submitted["run_id"]))
        self.assertTrue(run["data"]["completion_auth"])

    def test_queued_completion_requeues_before_network_when_registration_started(self):
        submitted = self._submit(completion_auth=True)

        returned, active, network, oauth = self._execute(submitted, active_job={"id": 44, "status": "running"})

        self.assertEqual("deferred", returned["status"])
        run = service.operation_task_store.get_run(int(submitted["run_id"]))
        task = service.operation_task_store.get_task(int(submitted["task_id"]))
        self.assertEqual("queued", run["status"])
        self.assertEqual("queued", task["status"])
        self.assertNotIn("remote_intent", run["data"])
        self.assertIsNone(run.get("execution_id"))
        account = service.db.get_account(self.account_id)
        self.assertEqual("queued", account["codex_execution_status"])
        self.assertEqual(int(submitted["run_id"]), account["codex_active_run_id"])
        active.assert_called_once_with(self.account_id, self.email)
        network.assert_not_called()
        oauth.assert_not_called()

    def test_completion_runs_oauth_after_registration_is_finished(self):
        submitted = self._submit(completion_auth=True)

        returned, active, _, oauth = self._execute(submitted, active_job=None)

        self.assertEqual("success", returned["status"])
        active.assert_called_once_with(self.account_id, self.email)
        oauth.assert_called_once()

    def test_independent_codex_keeps_existing_behavior(self):
        submitted = self._submit()

        returned, active, _, oauth = self._execute(submitted, active_job={"id": 44, "status": "running"})

        self.assertEqual("success", returned["status"])
        active.assert_not_called()
        oauth.assert_called_once()

    def test_remote_lease_exception_keeps_existing_reconciliation_behavior(self):
        submitted = self._submit()

        returned, active, _, _ = self._execute(
            submitted,
            active_job=None,
            oauth_error=service.task_gateway.OperationLeaseUnavailable("远端调用中的租约错误"),
        )

        self.assertEqual("attention_required", returned["status"])
        run = service.operation_task_store.get_run(int(submitted["run_id"]))
        self.assertEqual("attention_required", run["status"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        active.assert_not_called()
