"""外围远端业务与注册、账号任务共享执行许可，协调过程不重复占槽。"""
from __future__ import annotations

from contextlib import ExitStack

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

from core.operations import concurrency, task_gateway
from core.storage import runtime_config
from core.storage.operations import runtime, store
from tests.support_pg import PostgresTestCase
from tests.support_settlement import install_native_settlement_fixture


class PeripheralConcurrencyTests(PostgresTestCase):
    def setUp(self):
        self.encryption = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.encryption.start()
        self.addCleanup(self.encryption.stop)
        self.contexts = []
        self.policy()
        if self._testMethodName in {
            "test_manual_and_periodic_sub2api_scans_queue_without_outbound_or_child_wait",
            "test_sentinel_check_waits_as_durable_maintenance_and_releases_after_check_lease",
        }:
            # Per-test TRUNCATE removes the native domain capability marker.
            store.reset_ready()
            store.init()
            self.settlement_fixture = install_native_settlement_fixture(self)

    def tearDown(self):
        # The low-level blocker is not a settlement participant. Release it
        # before guarded dependency cleanup closes the native fixture.
        self._release_contexts()

    def _release_contexts(self):
        for context in self.contexts:
            concurrency.release_execution(context)

    def policy(self, **updates):
        from config.concurrency import policy_values

        values = policy_values({})
        values.update(GLOBAL_TASK_WORKERS=1, EMAIL_IMPORT_WORKERS=4)
        values.update(updates)
        runtime_config.write_values({key: str(value) for key, value in values.items()}, activate=True, source="test")

    def blocker(self):
        admitted = concurrency.try_admit_and_claim(
            execution_key="peripheral-blocker", task_type="live_check", claim=lambda _conn, execution_id: {"execution_id": execution_id},
        )
        self.assertTrue(admitted)
        self.contexts.append(admitted.context)
        return admitted.context

    def test_manual_and_periodic_sub2api_scans_queue_without_outbound_or_child_wait(self):
        from core.integrations.sub2api import monitor

        blocker = self.blocker()
        observed = []

        def fetch(**_kwargs):
            observed.append(concurrency.current_execution().task_type)
            self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
            return []

        stack = self.enterContext(ExitStack())
        stack.enter_context(patch.object(monitor.jobs, "enqueue_due", return_value={}))
        stack.enter_context(patch.object(monitor.client, "configured_backend_identity", return_value="fixture-backend"))
        stack.enter_context(patch.object(monitor.client, "configured_upload_options", return_value={}))
        remote = stack.enter_context(patch.object(monitor.client, "list_configured_error_accounts", side_effect=fetch))
        stack.enter_context(patch.object(monitor.db, "list_codex_accounts", return_value=[]))
        stack.enter_context(patch.object(monitor.repair_store, "list_repairs", return_value=[]))
        stack.enter_context(patch.object(monitor._cfg, "SUB2API_MONITOR_ENABLED", True))
        manual = monitor.run_once(force=True)
        scheduled = monitor.run_once(force=False)
        self.assertTrue(manual["accepted"])
        self.assertTrue(scheduled["accepted"])
        self.assertEqual("queued", manual["status"])
        remote.assert_not_called()
        blocked = task_gateway._execute_operation_handler("sub2api_scan", manual["run_id"])
        self.assertIn("global_capacity", blocked["blocked_by"])
        remote.assert_not_called()
        concurrency.release_execution(blocker)
        for queued in (manual, scheduled):
            result = task_gateway._execute_operation_handler("sub2api_scan", queued["run_id"])
            self.assertEqual("success", result["status"])
            self.settlement_fixture.wait_for_run_released(int(queued["run_id"]))
            self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])
        self.assertEqual(["sub2api_scan", "sub2api_scan"], observed)

    def test_sentinel_check_waits_as_durable_maintenance_and_releases_after_check_lease(self):
        from core.auth.protocol.sentinel_assets import AssetCheck
        from core.maintenance import sentinel

        blocker = self.blocker()
        directory = self.enterContext(tempfile.TemporaryDirectory())
        stack = self.enterContext(ExitStack())
        # This test chooses when the Worker consumes the durable request.
        # Restore any previous registrations after the explicit consumer exits.
        for name in (
            "_DISPATCH_HANDLERS", "_DISPATCH_CAPACITY_HANDLERS", "_OPERATION_HANDLERS",
            "_OPERATION_HANDLER_ALLOWLISTS", "_OPERATION_ACTIONS", "_OPERATION_ACTION_SOURCES",
        ):
            stack.enter_context(patch.dict(getattr(task_gateway, name), clear=True))
        stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        root = Path(directory)
        manager = Mock(cache_dir=root / "cache")
        manager._path.side_effect = lambda name: manager.cache_dir / name
        manager.check.return_value = AssetCheck("refreshed")
        builtin = root / "sdk.js"
        builtin.write_text("fixture")
        executor = Mock(side_effect=AssertionError("request acceptance must not execute a check"))
        service = sentinel.SentinelMaintenanceService(
            manager=manager, builtin_path=builtin, executor=executor,
        )
        stack.enter_context(patch.object(service, "_load_local"))
        stack.enter_context(patch.object(service, "_persist_check"))
        stack.enter_context(patch.object(sentinel, "get_service", return_value=service))
        lease = stack.enter_context(patch.object(service, "_lease", wraps=service._lease))
        sentinel.register_handler()

        queued = service.start_check()
        self.assertTrue(queued["accepted"])
        self.assertEqual("queued", queued["status"])
        executor.assert_not_called()
        manager.check.assert_not_called()
        lease.assert_not_called()
        self.assertFalse(manager.cache_dir.exists())
        original = runtime.get_run(queued["run_id"])
        self.assertEqual(queued["task_id"], original["task_id"])
        self.assertEqual("queued", original["status"])

        blocked = task_gateway._execute_operation_handler(sentinel._TASK_TYPE, queued["run_id"])
        self.assertEqual("queued", blocked["status"])
        self.assertEqual(queued["run_id"], blocked["run_id"])
        self.assertIn("global_capacity", blocked["blocked_by"])
        manager.check.assert_not_called()
        lease.assert_not_called()
        self.assertFalse(manager.cache_dir.exists())
        self.assertEqual("queued", runtime.get_run(queued["run_id"])["status"])
        self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
        concurrency.release_execution(blocker)

        def check(**_kwargs):
            self.assertEqual("maintenance_check", concurrency.current_execution().task_type)
            self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
            self.assertTrue(service._external_running())
            return AssetCheck("refreshed")

        manager.check.side_effect = check
        result = task_gateway._execute_operation_handler(sentinel._TASK_TYPE, queued["run_id"])
        self.assertEqual("success", result["status"])
        self.settlement_fixture.wait_for_run_released(int(queued["run_id"]))
        self.assertEqual(queued["run_id"], result["run_id"])
        self.assertEqual(queued["task_id"], result["task_id"])
        manager.check.assert_called_once_with(refresh=True)
        executor.assert_not_called()
        terminal = runtime.get_run(queued["run_id"])
        self.assertEqual("success", terminal["status"])
        self.assertEqual(queued["task_id"], terminal["task_id"])
        self.assertFalse(service._external_running())
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_cancelling_a_queued_sentinel_check_closes_only_its_waiting_cache_lease(self):
        from core.auth.protocol.sentinel_assets import AssetCheck
        from core.maintenance.sentinel import SentinelMaintenanceService

        with tempfile.TemporaryDirectory() as directory:
            manager = Mock(cache_dir=Path(directory) / "cache")
            manager._path.side_effect = lambda name: manager.cache_dir / name
            manager.check.return_value = AssetCheck("refreshed")
            service = SentinelMaintenanceService(manager=manager, executor=lambda _callback: None)
            with patch.object(service, "_load_local"), patch.object(service, "_persist_check"):
                queued = service.start_check()
                task = {"id": queued["task_id"], "runs": [runtime.get_run(queued["run_id"])]}
                from core.maintenance.sentinel import _cancel_check

                _cancel_check(task)
                self.assertEqual("cancelled", runtime.get_run(queued["run_id"])["status"])
                self.assertFalse(service._external_running())
                manager.check.assert_not_called()
