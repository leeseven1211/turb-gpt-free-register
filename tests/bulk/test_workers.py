"""协调worker必须完整存活，重入启动能补起缺失线程。"""
from unittest import TestCase
from unittest.mock import Mock, patch

from core.bulk_operations import adapters, service
from core.storage import records
from core.storage.operations import bulk
from tests.support_pg import PostgresTestCase


class WorkerLifecycleTests(TestCase):
    def test_partial_workers_are_not_ready_and_start_repairs_missing_thread(self):
        alive = Mock()
        alive.is_alive.return_value = True
        dead = Mock()
        dead.is_alive.return_value = False
        started = []

        def thread(**kwargs):
            item = Mock()
            item.is_alive.side_effect = lambda: item in started
            item.start.side_effect = lambda: started.append(item)
            return item

        with patch.dict(service._THREADS, {"selection": alive, "expand": dead}, clear=True), patch.object(
            service, "_store", return_value=Mock()
        ), patch.object(service.threading, "Thread", side_effect=thread):
            self.assertFalse(service.worker_status()["alive"])
            self.assertTrue(service.start_workers())
            self.assertEqual(len(started), 2)
            self.assertTrue(service.worker_status()["alive"])
            self.assertFalse(service.start_workers())


class SelectionWorkerRoutingTests(TestCase):
    def run_selection(self, operation_key, freeze):
        store = Mock(BulkError=bulk.BulkError)
        item = {"id": 7, "action_key": operation_key, "owner_id": "worker-owner", "fence": 3,
                "query_spec": {}, "config_snapshot": {"auto_refresh_at_enabled": False}}
        store.claim_work.side_effect = lambda kind, owner, limit: [item] if kind == "selection" else []
        store.freeze_selection.side_effect = freeze
        with patch.object(service, "_store", return_value=store), patch.object(
            service, "_LAST_MAINTENANCE", service.time.monotonic()
        ), patch("core.bulk_operations.execution.repair_pending_handoffs", return_value=0):
            self.assertEqual(1, service.run_once("selection"))
        store.fail_selection.assert_not_called()
        return store

    def test_plan_check_selects_database_policy_without_python_callback(self):
        with patch.object(adapters, "preflight_many", side_effect=AssertionError("unexpected Python preflight")):
            store = self.run_selection("plan_check", Mock())
        store.freeze_selection.assert_called_once_with(
            7, where_sql="TRUE", params=[], owner_id="worker-owner", fence=3,
            preflight_policy="plan_check_db_v1",
        )

    def test_other_operations_keep_identity_callback_and_saved_settings(self):
        for key in ("token_refresh", "password_setup", "twofa_setup", "account_completion", "codex_retry"):
            with self.subTest(operation_key=key):
                targets = [{"id": 19, "target_id": 31, "account_id": 31, "ordinal": 1}]
                conn = object()
                receipts = [{"target_id": 19, "status": "not_executable", "reason_code": "account_missing"}]

                def freeze(selection_id, *, preflight, **kwargs):
                    self.assertEqual(7, selection_id)
                    self.assertEqual({"where_sql": "TRUE", "params": [], "owner_id": "worker-owner",
                                      "fence": 3, "preflight_identity_only": True}, kwargs)
                    self.assertIs(receipts, preflight(targets, conn))

                with patch.object(adapters, "preflight_many", return_value=receipts) as callback:
                    self.run_selection(key, freeze)
                callback.assert_called_once_with(
                    targets, operation_key=key, settings={"auto_refresh_at_enabled": False}, conn=conn,
                )


class SelectionWorkerTests(PostgresTestCase):
    def test_token_refresh_keeps_identity_projection_and_persists_real_preflight(self):
        bulk.reset_ready()
        bulk.init()
        account_id = self.seed(records.ACCOUNTS, [{"email": "worker-preflight@example.test"}])[0]
        selected = bulk.create_selection(
            request_key="worker-identity-preflight", source={"kind": "ids", "ids": [account_id]},
            operation_key="token_refresh", config_revision="test-v1",
            config_snapshot={"auto_refresh_at_enabled": False},
        )
        original = adapters.preflight_many
        observed = []

        def observed_preflight(targets, **kwargs):
            observed.extend(targets)
            return original(targets, **kwargs)

        with patch.object(adapters, "preflight_many", side_effect=observed_preflight):
            self.assertEqual(1, service.run_once("selection"))
        self.assertEqual(1, len(observed))
        self.assertEqual({"id", "target_id", "account_id", "ordinal"}, set(observed[0]))
        self.assertEqual(account_id, observed[0]["account_id"])
        frozen = bulk.get_selection(selected["id"])
        self.assertEqual("ready", frozen["state"])
        self.assertEqual({"ready": 0, "waiting_account": 0, "not_executable": 1}, frozen["preflight_summary"])
        self.assertEqual("access_token_missing", frozen["targets"][0]["match_evidence"]["preflight"]["reason_code"])

    def test_plan_check_database_policy_persists_preflight_without_python_callback(self):
        bulk.reset_ready()
        bulk.init()
        account_id = self.seed(records.ACCOUNTS, [{"email": "worker-plan-policy@example.test"}])[0]
        selected = bulk.create_selection(
            request_key="worker-plan-policy", source={"kind": "ids", "ids": [account_id]},
            operation_key="plan_check", config_revision="test-v1",
            config_snapshot={"auto_refresh_at_enabled": False},
        )
        with patch.object(adapters, "preflight_many", side_effect=AssertionError("unexpected Python preflight")):
            self.assertEqual(1, service.run_once("selection"))
        frozen = bulk.get_selection(selected["id"])
        self.assertEqual("ready", frozen["state"])
        self.assertEqual({"ready": 0, "waiting_account": 0, "not_executable": 1}, frozen["preflight_summary"])
        target = frozen["targets"][0]
        preflight = target["match_evidence"]["preflight"]
        self.assertEqual(target["id"], preflight["target_id"])
        self.assertEqual("not_executable", preflight["status"])
        self.assertEqual("access_token_missing", preflight["reason_code"])
        self.assertIsNone(preflight["blocker_run_id"])
        self.assertTrue(preflight["checked_at"])
