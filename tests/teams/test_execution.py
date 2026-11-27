"""Team 编排使用真实持久任务边界的隔离回归。"""
from __future__ import annotations

import importlib
from contextlib import ExitStack
from unittest.mock import patch

from core import account_task_store
from core.operations import task_gateway
from core.storage import postgres, records
from core.storage.operations import store as operations
from tests.support_pg import PostgresTestCase
from tests.support_settlement import install_native_settlement_fixture


class TeamExecutionTests(PostgresTestCase):
    def setUp(self):
        try:
            self.execution = importlib.import_module("core.teams.execution")
        except ModuleNotFoundError:
            self.fail("Team 持久执行编排尚未实现")
        from core.storage.teams import repository

        self.store = repository
        self.resources = ExitStack()
        self.addCleanup(self.resources.close)
        self.resources.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.resources.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        operations.reset_ready()
        operations.init()
        self.store.init()
        self.execution.register_handlers()
        self.fixture = install_native_settlement_fixture(self)
        self.addCleanup(self.fixture.close)
        self.accounts = self.seed(records.ACCOUNTS, [
            {"email": f"execution-{index}@example.test", "password": "test-only-password"}
            for index in range(4)
        ])

    def tearDown(self):
        self.fixture.close()
        for task_type in self.execution.TASK_TYPES:
            task_gateway.unregister_operation_handler(task_type)

    def bind(self):
        probe = self.store.create_probe(manager_account_id=self.accounts[0])
        probe = self.store.update_probe(
            probe["id"], status="success", stage="complete",
            workspaces=[{
                "workspace_id": "workspace-execution", "workspace_type": "team",
                "name": "执行团队", "role": "owner", "can_manage": True,
                "capabilities": {"read_members": True, "read_invitations": True, "invite_members": True},
                "purchased_seats": 3,
            }],
        )
        return self.store.bind_team(
            manager_account_id=self.accounts[0], workspace_id="workspace-execution",
            probe_id=probe["id"], probe_revision=probe["revision"], planned_member_limit=3,
        )["team"]

    def run_task(self, task_type, run_id):
        result = task_gateway._execute_operation_handler(task_type, int(run_id))
        matches = [entry for entry in self.fixture.contexts.values()
                   if int(entry.claimed_run["id"]) == int(run_id)]
        if matches:
            self.fixture.wait_for_execution_released(matches[-1])
        return result

    def run_identity(self, kind, submission):
        self.run_task(kind, submission["run_id"])
        child = self.child(submission["task_id"], kind)
        self.run_task(kind, child["last_run_id"])
        self.ready(submission["run_id"])
        return self.run_task(kind, submission["run_id"])

    def test_enqueue_shares_callers_transaction_and_indexes_team_identity(self):
        team = self.bind()
        with self.store.transaction() as conn:
            submitted = self.execution.enqueue_operation(conn, "team_sync", {
                "team_id": team["id"], "manager_account_id": self.accounts[0],
                "request_key": "execution-sync-request-0001",
            })
        task = operations.get_task(submitted["task_id"])
        self.assertEqual(team["id"], task["team_id"])
        self.assertEqual("team_sync", task["task_type"])
        self.assertIsNone(task["account_id"])
        self.assertEqual("openai_interactive", operations.get_run(submitted["run_id"])["resource_family"])
        with self.assertRaisesRegex(RuntimeError, "测试回滚"):
            with self.store.transaction() as conn:
                self.execution.enqueue_operation(conn, "team_sync", {
                    "team_id": team["id"], "manager_account_id": self.accounts[0],
                    "request_key": "execution-sync-rollback-0001",
                })
                raise RuntimeError("测试回滚")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*) FROM {postgres.qualified('operation_tasks')} WHERE task_type='team_sync'"
            )
            self.assertEqual(1, cur.fetchone()[0])

    def test_binding_outbox_recovers_task_once_after_consumer_restart(self):
        team = self.bind()
        first = self.execution.process_pending_outbox()
        self.assertEqual(1, first)
        self.assertEqual(0, self.execution.process_pending_outbox())
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id,team_id FROM {postgres.qualified('operation_tasks')} WHERE task_type='team_sync'"
            )
            rows = cur.fetchall()
            self.assertEqual(1, len(rows))
            self.assertEqual(team["id"], rows[0][1])

    def test_probe_discovery_persists_workspaces_without_binding_or_personal_session_write(self):
        probe = self.store.create_probe(manager_account_id=self.accounts[0])
        submission = self.execution.enqueue_operation(None, "team_probe", {
            "probe_id": probe["id"], "manager_account_id": self.accounts[0],
            "request_key": "execution-probe-request-0001",
        })
        remote = _Remote(self.accounts)
        with patch.object(self.execution, "remote_adapter", return_value=remote):
            result = self.run_identity("team_probe", submission)
        self.assertEqual("success", result["status"])
        saved = self.store.get_probe(probe["id"])
        self.assertEqual("success", saved["status"])
        self.assertEqual("workspace-execution", saved["workspaces"][0]["workspace_id"])
        self.assertEqual(0, self.store.list_teams()["total"])

    def test_sync_failure_retains_last_successful_member_and_seat_facts(self):
        team = self.bind()
        remote = _Remote(self.accounts)
        with patch.object(self.execution, "remote_adapter", return_value=remote):
            submission = self.execution.enqueue_operation(None, "team_sync", {
                "team_id": team["id"], "request_key": "execution-sync-success-0001",
            })
            self.assertEqual("success", self.run_identity("team_sync", submission)["status"])
            before = self.store.get_team(team["id"])
            remote.fail_snapshot = True
            submission = self.execution.enqueue_operation(None, "team_sync", {
                "team_id": team["id"], "request_key": "execution-sync-failed-0001",
            })
            self.assertEqual("failed", self.run_identity("team_sync", submission)["status"])
        after = self.store.get_team(team["id"])
        self.assertEqual(before["last_synced_at"], after["last_synced_at"])
        self.assertEqual(1, after["confirmed_member_count"])
        self.assertEqual(3, after["purchased_seats"])
        self.assertEqual("failed", after["last_sync_status"])

    def test_busy_manager_keeps_probe_request_durable_and_waits_for_exact_identity(self):
        busy = gateway_submit = task_gateway.submit_durable_operation(
            task_type="live_check", account_id=self.accounts[0], email="execution-0@example.test",
            source_system="synthetic_service", source_id="busy-manager", dispatch=False,
        )
        probe = self.store.create_probe(manager_account_id=self.accounts[0])
        submitted = self.execution.enqueue_operation(None, "team_probe", {
            "manager_account_id": self.accounts[0], "probe_id": probe["id"],
            "request_key": "busy-manager-probe-request",
        })
        result = self.run_task("team_probe", submitted["run_id"])
        self.assertEqual("deferred", result["status"])
        self.assertEqual("waiting_account", result["reason"])
        self.assertNotEqual(gateway_submit["task_id"], submitted["task_id"])
        operations.request_run_cancel(busy["run_id"])
        self.ready(submitted["run_id"])
        with patch.object(self.execution, "remote_adapter", return_value=_Remote(self.accounts)):
            self.assertEqual("success", self.run_identity("team_probe", submitted)["status"])

    def test_join_uses_separate_manager_and_member_tasks_and_persists_verified_context(self):
        from cryptography.fernet import Fernet
        from core.storage.runtime_config import decrypt_private_text

        team = self.bind()
        request = self.store.create_join_request(
            team["id"], targets=[{"account_id": self.accounts[1],
                                  "email_snapshot": "execution-1@example.test"}],
            task_factory=self.execution.enqueue_operation,
        )
        remote = _Remote(self.accounts)
        with patch.object(self.execution, "remote_adapter", return_value=remote), patch.dict(
            "os.environ", {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}
        ):
            self.run_task("team_join_request", request["run_id"])
            item = self.store.list_join_items(team["id"], request["id"])["items"][0]
            self.assertEqual("accepted", item["acceptance_status"])
            # 第一次保存持久围栏，第二次发出母号子任务。
            self.ready(item["run_id"])
            self.run_task("team_join", item["run_id"])
            self.ready(item["run_id"])
            self.run_task("team_join", item["run_id"])
            invite = self.child(item["task_id"], "team_invite")
            self.assertEqual(self.accounts[0], invite["account_id"])
            self.assertEqual("queued", operations.get_run(item["run_id"])["status"])
            invite_result = self.run_task("team_invite", invite["last_run_id"])
            self.assertEqual("success", invite_result["status"], invite_result)
            # 邀请成功不能提前把加入父任务收成成功。
            self.assertEqual("queued", operations.get_run(item["run_id"])["status"])
            self.ready(item["run_id"])
            self.run_task("team_join", item["run_id"])
            accept = self.child(item["task_id"], "team_accept")
            self.assertEqual(self.accounts[1], accept["account_id"])
            self.assertNotEqual(invite["id"], accept["id"])
            self.assertEqual("success", self.run_task("team_accept", accept["last_run_id"])["status"])
            self.ready(item["run_id"])
            self.assertEqual("success", self.run_task("team_join", item["run_id"])["status"])
            invitation = self.store.get_invitation(team["id"], item["invitation_id"])
            self.assertEqual("joined", invitation["membership_state"])
            self.assertTrue(invitation["local_saved"])
            self.assertTrue(self.store.get_account_states(team["id"], [self.accounts[1]])[self.accounts[1]]["already_member"])
            saved = self.store.get_auth_context(team["id"], self.accounts[1])
            self.assertEqual("workspace-execution", saved["workspace_id"])
            self.assertIn('"workspace_id": "workspace-execution"', decrypt_private_text(saved["encrypted_context"]))
        self.assertEqual([self.accounts[0]], remote.invite_accounts)
        self.assertEqual([self.accounts[1]], remote.accept_accounts)

    def test_capacity_wait_and_cancel_keep_business_ownership_and_reservation(self):
        team = self.bind()
        self.store.apply_sync_snapshot(
            team["id"], workspace_id=team["workspace_id"], manager_account_id=self.accounts[0],
            manager_revision=team["manager_revision"], members=[], invitations=[],
            purchased_seats=0, members_complete=True, invitations_complete=True,
        )
        request = self.store.create_join_request(
            team["id"], targets=[{"account_id": self.accounts[1]}],
            task_factory=self.execution.enqueue_operation,
        )
        self.run_task("team_join_request", request["run_id"])
        item = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.ready(item["run_id"])
        self.run_task("team_join", item["run_id"])
        self.ready(item["run_id"])
        self.run_task("team_join", item["run_id"])
        invitation = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual("accepted", item["acceptance_status"])
        self.assertFalse(invitation["seat_reserved"])
        self.execution.cancel_task(operations.get_task(item["task_id"]))
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT team_id FROM {postgres.qualified('team_account_ownership')} WHERE account_id=%s",
                (self.accounts[1],),
            )
            self.assertEqual(team["id"], cur.fetchone()[0])

    def test_verified_join_survives_auth_context_save_failure(self):
        team = self.bind()
        request = self.store.create_join_request(
            team["id"], targets=[{"account_id": self.accounts[1]}],
            task_factory=self.execution.enqueue_operation,
        )
        remote = _Remote(self.accounts)
        remote.joined = True
        with patch.object(self.execution, "remote_adapter", return_value=remote), patch.dict(
            "os.environ", {"TURB_CONFIG_ENCRYPTION_KEY": ""}
        ):
            self.run_task("team_join_request", request["run_id"])
            item = self.store.list_join_items(team["id"], request["id"])["items"][0]
            self.ready(item["run_id"])
            self.run_task("team_join", item["run_id"])
            invitation = self.store.get_invitation(team["id"], item["invitation_id"])
            accepted = self.execution.enqueue_operation(None, "team_accept", {
                "team_id": team["id"], "workspace_id": team["workspace_id"],
                "invitation_id": invitation["id"], "account_id": self.accounts[1],
                "intent_fence": invitation["execution_fence"], "parent_task_id": item["task_id"],
                "manager_account_id": self.accounts[0], "manager_revision": team["manager_revision"],
                "request_key": "save-failure-context-test",
            })
            result = self.run_task("team_accept", accepted["run_id"])
        self.assertEqual("partial_success", result["status"])
        invitation = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual("joined", invitation["membership_state"])
        self.assertFalse(invitation["local_saved"])
        self.assertTrue(self.store.get_account_states(team["id"], [self.accounts[1]])[self.accounts[1]]["already_member"])

    def test_sync_retry_key_replays_new_run_and_keeps_old_run(self):
        submitted = self.execution.enqueue_operation(None, "team_sync", {
            "team_id": self.bind()["id"], "request_key": "sync-before-manual-retry",
        })
        remote = _Remote(self.accounts)
        remote.fail_snapshot = True
        with patch.object(self.execution, "remote_adapter", return_value=remote):
            self.run_identity("team_sync", submitted)
        task = operations.get_task(submitted["task_id"])
        retry = self.execution.retry_task(task, request_key="sync-manual-retry-key-0001")
        replay = self.execution.retry_task(task, request_key="sync-manual-retry-key-0001")
        self.assertEqual(retry, replay)
        self.assertNotEqual(submitted["run_id"], retry["run_id"])
        self.assertEqual(2, len(operations.get_task(submitted["task_id"])["runs"]))
        remote.fail_snapshot = False
        with patch.object(self.execution, "remote_adapter", return_value=remote):
            self.assertEqual("success", self.run_identity("team_sync", retry)["status"])

    def test_pending_or_accepted_invitation_accepts_without_manager_auth_or_new_capacity(self):
        from cryptography.fernet import Fernet

        team = self.bind()
        request = self.store.create_join_request(
            team["id"], operation="continue", targets=[{"account_id": self.accounts[1]}],
            task_factory=self.execution.enqueue_operation,
        )
        self.run_task("team_join_request", request["run_id"])
        item = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.store.update_invitation(team["id"], item["invitation_id"], changes={
            "invitation_state": "accepted", "remote_invitation_id": "existing-invite",
        })
        remote = _Remote(self.accounts)
        remote.joined = True
        remote.fail_snapshot = True
        with patch.object(self.execution, "remote_adapter", return_value=remote), patch.dict(
            "os.environ", {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}
        ):
            self.run_task("team_join", item["run_id"])
            self.ready(item["run_id"])
            self.run_task("team_join", item["run_id"])
            accept = self.child(item["task_id"], "team_accept")
            self.assertEqual("success", self.run_task("team_accept", accept["last_run_id"])["status"])
            self.ready(item["run_id"])
            self.assertEqual("success", self.run_task("team_join", item["run_id"])["status"])
        self.assertEqual([], remote.invite_accounts)

    def test_interrupted_identity_child_gets_new_run_before_remote_recovery(self):
        probe = self.store.create_probe(manager_account_id=self.accounts[0])
        submission = self.execution.enqueue_operation(None, "team_probe", {
            "probe_id": probe["id"], "manager_account_id": self.accounts[0],
            "request_key": "restart-identity-child-test",
        })
        self.run_task("team_probe", submission["run_id"])
        original = self.child(submission["task_id"], "team_probe")
        self.interrupt(original["last_run_id"])
        busy = task_gateway.submit_durable_operation(
            task_type="live_check", account_id=self.accounts[0], email="execution-0@example.test",
            source_system="synthetic_service", source_id="busy-recovery", dispatch=False,
        )
        self.ready(submission["run_id"])
        waiting = self.run_task("team_probe", submission["run_id"])
        self.assertEqual("deferred", waiting["status"])
        self.assertEqual("waiting_account", waiting["reason"])
        operations.request_run_cancel(busy["run_id"])
        self.ready(submission["run_id"])
        self.assertEqual("deferred", self.run_task("team_probe", submission["run_id"])["status"])
        newer = self.child(submission["task_id"], "team_probe")
        self.assertNotEqual(original["last_run_id"], newer["last_run_id"])
        with patch.object(self.execution, "remote_adapter", return_value=_Remote(self.accounts)):
            self.assertEqual("success", self.run_task("team_probe", newer["last_run_id"])["status"])
            self.ready(submission["run_id"])
            self.assertEqual("success", self.run_task("team_probe", submission["run_id"])["status"])

    def test_restart_recovers_interrupted_parent_and_preserves_business_ownership(self):
        team = self.bind()
        request = self.store.create_join_request(
            team["id"], targets=[{"account_id": self.accounts[1]}],
            task_factory=self.execution.enqueue_operation,
        )
        self.run_task("team_join_request", request["run_id"])
        item = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.interrupt(item["run_id"])
        self.execution.reconcile_execution_projections(recover=True)
        invitation = self.store.get_invitation(team["id"], item["invitation_id"])
        self.assertEqual("queued", invitation["execution_status"])
        self.assertNotEqual(item["run_id"], invitation["last_run_id"])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT team_id FROM {postgres.qualified('team_account_ownership')} WHERE account_id=%s",
                        (self.accounts[1],))
            self.assertEqual(team["id"], cur.fetchone()[0])

    def test_cancelled_parent_prevents_late_acceptance_and_drains_cancelled_outbox(self):
        from core.operations.runtime import OperationCancelled

        team = self.bind()
        request = self.store.create_join_request(
            team["id"], targets=[{"account_id": self.accounts[1]}],
            task_factory=self.execution.enqueue_operation,
        )
        self.execution.cancel_task(operations.get_task(request["task_id"]))
        with self.assertRaises(OperationCancelled):
            self.store.accept_join_item(team["id"], request["id"], 0,
                                        task_factory=self.execution.enqueue_operation)
        item = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.assertEqual("pending", item["acceptance_status"])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {postgres.qualified('team_account_ownership')} WHERE account_id=%s",
                        (self.accounts[1],))
            self.assertEqual(0, cur.fetchone()[0])

    def test_restart_after_unknown_write_reconciles_snapshot_before_new_invite(self):
        team = self.bind()
        request = self.store.create_join_request(
            team["id"], targets=[{"account_id": self.accounts[1]}],
            task_factory=self.execution.enqueue_operation,
        )
        self.run_task("team_join_request", request["run_id"])
        item = self.store.list_join_items(team["id"], request["id"])["items"][0]
        self.run_task("team_join", item["run_id"])
        self.ready(item["run_id"])
        self.run_task("team_join", item["run_id"])
        original = self.child(item["task_id"], "team_invite")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('operation_runs')} "
                        "SET status='attention_required',completed_at=now(),"
                        "result_summary='{\"cause_code\":\"worker_interrupted\",\"outcome\":\"request_unknown\"}'::jsonb "
                        "WHERE id=%s", (original["last_run_id"],))
            cur.execute(f"UPDATE {postgres.qualified('operation_tasks')} SET status='attention_required' WHERE id=%s",
                        (original["id"],))
        self.ready(item["run_id"])
        self.assertEqual("deferred", self.run_task("team_join", item["run_id"])["status"])
        newer = self.child(item["task_id"], "team_invite")
        self.assertNotEqual(original["last_run_id"], newer["last_run_id"])
        remote = _Remote(self.accounts)
        remote.invited = True
        with patch.object(self.execution, "remote_adapter", return_value=remote):
            result = self.run_task("team_invite", newer["last_run_id"])
        self.assertEqual("success", result["status"], result)
        self.assertEqual([], remote.invite_accounts)
        self.assertEqual(2, len(operations.get_task(original["id"])["runs"]))

    def test_reverify_switching_manager_keeps_old_receipt_and_checks_current_identity(self):
        team = self.bind()
        probe = self.store.create_probe(manager_account_id=self.accounts[1])
        probe = self.store.update_probe(probe["id"], status="success", workspaces=[{
            "workspace_id": team["workspace_id"], "workspace_type": "team",
            "role": "admin", "can_manage": True,
        }])
        submission = self.execution.enqueue_operation(None, "team_reverify", {
            "team_id": team["id"], "request_key": "reverify-manager-switch-request",
        })
        self.run_task("team_reverify", submission["run_id"])
        old_child = self.child(submission["task_id"], "team_reverify")
        remote = _Remote(self.accounts)
        remote.on_discover = lambda: self.store.patch_team(
            team["id"], expected_revision=team["revision"], changes={"manager_account_id": self.accounts[1]},
            probe_id=probe["id"], probe_revision=probe["revision"],
        )
        with patch.object(self.execution, "remote_adapter", return_value=remote):
            old_result = self.run_task("team_reverify", old_child["last_run_id"])
            self.assertTrue(old_result["result_summary"]["manager_changed"])
            self.ready(submission["run_id"])
            self.run_task("team_reverify", submission["run_id"])
            current_child = self.child(submission["task_id"], "team_reverify")
            self.assertEqual(self.accounts[1], current_child["account_id"])
            self.assertEqual("success", self.run_task("team_reverify", current_child["last_run_id"])["status"])
            self.ready(submission["run_id"])
            self.assertEqual("success", self.run_task("team_reverify", submission["run_id"])["status"])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {postgres.qualified('team_execution_receipts')} "
                        "WHERE team_id=%s AND manager_account_id=%s AND kind='reverify'",
                        (team["id"], self.accounts[0]))
            self.assertEqual(1, cur.fetchone()[0])

    def test_sync_batch_links_reused_tasks_without_reassigning_original_batch(self):
        team = self.bind()
        with self.store.transaction() as conn:
            first = self.execution.enqueue_sync_batch(conn, [team["id"]])
            refs = self.execution.enqueue_team_action(conn, "team_sync", team["id"])
            self.execution.attach_sync_batch(conn, first["batch_id"], [{"team_id": team["id"], **refs}])
            second = self.execution.enqueue_sync_batch(conn, [team["id"]])
            reused = self.execution.enqueue_team_action(conn, "team_sync", team["id"])
            self.execution.attach_sync_batch(conn, second["batch_id"], [{"team_id": team["id"], **reused}])
        self.assertEqual(refs["task_id"], reused["task_id"])
        self.assertEqual(first["batch_id"], operations.get_task(refs["task_id"])["batch_id"])
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT batch_id FROM {postgres.qualified('operation_batch_items')} "
                        "WHERE task_id=%s ORDER BY batch_id", (refs["task_id"],))
            self.assertEqual([(first["batch_id"],), (second["batch_id"],)], cur.fetchall())
        operations.request_run_cancel(refs["run_id"])
        self.execution.reconcile_execution_projections()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT status FROM {postgres.qualified('operation_batches')} WHERE id=%s",
                        (second["batch_id"],))
            self.assertEqual("stopped", cur.fetchone()[0])

    def interrupt(self, run_id):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('operation_runs')} SET status='interrupted',completed_at=now() WHERE id=%s",
                        (int(run_id),))
            cur.execute(f"UPDATE {postgres.qualified('operation_tasks')} SET status='interrupted' WHERE last_run_id=%s",
                        (int(run_id),))

    def ready(self, run_id):
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('operation_runs')} SET next_attempt_at=NULL WHERE id=%s",
                        (int(run_id),))

    def child(self, parent_task_id, task_type):
        from psycopg.rows import dict_row
        with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {postgres.qualified('operation_tasks')} "
                        "WHERE parent_task_id=%s AND task_type=%s ORDER BY id DESC LIMIT 1",
                        (int(parent_task_id), task_type))
            return dict(cur.fetchone())


class _Remote:
    """只替代真实远端，持久受理、账号锁及业务写回仍走正式实现。"""

    def __init__(self, accounts):
        self.accounts = accounts
        self.fail_snapshot = False
        self.joined = False
        self.invited = False
        self.invite_accounts = []
        self.accept_accounts = []
        self.on_discover = None

    def discover(self, account_id, target_workspace_id=None):
        if self.on_discover is not None:
            callback, self.on_discover = self.on_discover, None
            callback()
        return {"workspaces": [{
            "workspace_id": "workspace-execution", "workspace_type": "team", "name": "执行团队",
            "role": "owner", "can_manage": True,
            "capabilities": {"read_members": True, "read_invitations": True, "invite_members": True},
            "purchased_seats": 3,
        }]}

    def snapshot(self, manager_account_id, workspace_id):
        if self.fail_snapshot:
            from core.teams.remote import TeamRemoteError
            raise TeamRemoteError("team_workspace_unavailable", "测试工作区暂不可见", retryable=True)
        return {
            "workspace": {"id": workspace_id, "name": "执行团队", "role": "owner", "can_manage": True},
            "members": [{"remote_user_id": "owner", "email": "execution-0@example.test",
                         "account_id": self.accounts[0], "role": "owner"}],
            "invitations": ([{"remote_invitation_id": "invite-test", "email": "execution-1@example.test",
                              "invitation_state": "pending"}] if self.invited else []),
            "members_complete": True, "invitations_complete": True,
            "confirmed_member_count": 1, "pending_invite_count": 0, "purchased_seats": 3,
        }

    def invite(self, manager_account_id, workspace_id, email):
        self.invited = True
        self.invite_accounts.append(manager_account_id)
        return {"workspace_id": workspace_id, "remote_invitation_id": "invite-test",
                "invitation_state": "pending", "email": email}

    def accept(self, account_id, workspace_id, invitation):
        self.joined = True
        self.accept_accounts.append(account_id)
        return {"workspace_id": workspace_id, "invitation_state": "accepted"}

    def verify_member(self, account_id, workspace_id):
        return {
            "workspace_id": workspace_id, "joined": self.joined,
            "member": {"remote_user_id": "user-test", "role": "member"},
            "auth_context": {"account_id": account_id, "email": "execution-1@example.test",
                             "user_id": "user-test", "workspace_id": workspace_id},
        }
