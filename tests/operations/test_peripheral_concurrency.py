"""外围远端业务与注册、账号任务共享执行许可，协调过程不重复占槽。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

from core.operations import concurrency, task_gateway
from core.storage import runtime_config
from core.storage.operations import runtime, store
from tests.support_pg import PostgresTestCase


class PeripheralConcurrencyTests(PostgresTestCase):
    def setUp(self):
        self.encryption = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.encryption.start()
        self.addCleanup(self.encryption.stop)
        self.contexts = []
        self.addCleanup(self._release_contexts)
        self.policy()

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

        with patch.object(monitor.jobs, "enqueue_due", return_value={}), \
                patch.object(monitor.client, "configured_backend_identity", return_value="fixture-backend"), \
                patch.object(monitor.client, "configured_upload_options", return_value={}), \
                patch.object(monitor.client, "list_configured_error_accounts", side_effect=fetch) as remote, \
                patch.object(monitor.db, "list_codex_accounts", return_value=[]), \
                patch.object(monitor.repair_store, "list_repairs", return_value=[]), \
                patch.object(monitor._cfg, "SUB2API_MONITOR_ENABLED", True):
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
                self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])
        self.assertEqual(["sub2api_scan", "sub2api_scan"], observed)

    def test_sentinel_check_waits_as_durable_maintenance_and_releases_after_check_lease(self):
        from core.auth.protocol.sentinel_assets import AssetCheck
        from core.maintenance.sentinel import SentinelMaintenanceService

        blocker = self.blocker()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = Mock(cache_dir=root / "cache")
            manager._path.side_effect = lambda name: manager.cache_dir / name
            manager.check.return_value = AssetCheck("refreshed")
            builtin = root / "sdk.js"
            builtin.write_text("fixture")
            callbacks = []
            service = SentinelMaintenanceService(manager=manager, builtin_path=builtin, executor=callbacks.append)
            with patch.object(service, "_load_local"), patch.object(service, "_persist_check"):
                queued = service.start_check()
                self.assertTrue(queued["accepted"])
                self.assertEqual("queued", queued["status"])
                callbacks.pop(0)()
                manager.check.assert_not_called()
                self.assertEqual("queued", runtime.get_run(queued["run_id"])["status"])
                concurrency.release_execution(blocker)

                def check(**_kwargs):
                    self.assertEqual("maintenance_check", concurrency.current_execution().task_type)
                    self.assertTrue(service._external_running())
                    return AssetCheck("refreshed")

                manager.check.side_effect = check
                result = task_gateway._execute_operation_handler("sentinel_maintenance_check", queued["run_id"])
                self.assertEqual("success", result["status"])
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
