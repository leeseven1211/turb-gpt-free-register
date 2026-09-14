from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


class OperationGatewayDispatcherTests(unittest.TestCase):
    def tearDown(self):
        from core.operations import task_gateway

        task_gateway.stop_dependency_dispatcher()
        task_gateway.stop_dispatcher()
        task_gateway.set_dependency_ready_handler(None)
        task_gateway.unregister_dispatch_handler("maintenance_test")
        task_gateway.release_dispatch(7001)

    def test_registered_dispatch_is_task_type_based_and_does_not_duplicate_legacy_rows(self):
        from core.operations import task_gateway

        submitted: list[int] = []

        class Future:
            def add_done_callback(self, callback):
                callback(self)

        class Executor:
            def available_slots(self):
                return 1

            def try_submit(self, handler, run_id):
                submitted.append(int(run_id))
                return Future()

        def list_dispatchable_runs(**kwargs):
            self.assertEqual(("native_operations",), kwargs["source_systems"])
            return [
                {"id": 7002, "task_type": "maintenance_test", "source_system": "account_action_tasks"},
                {"id": 7001, "task_type": "maintenance_test", "source_system": "native_operations"},
            ]

        operation = SimpleNamespace(list_dispatchable_runs=list_dispatchable_runs)
        with (
            patch.object(task_gateway, "_operation", return_value=operation),
            patch.object(task_gateway, "_executor", return_value=Executor()),
        ):
            task_gateway.register_dispatch_handler("maintenance_test", lambda _run_id: None)
            self.assertEqual(1, task_gateway.dispatch_registered_once(limit=10))

        self.assertEqual([7001], submitted)

    def test_dependency_dispatcher_has_one_persistent_thread(self):
        from core.operations import task_gateway

        operation = SimpleNamespace(recover_stale_task_dependencies=lambda: 0)
        with patch.object(task_gateway, "_operation", return_value=operation):
            task_gateway.set_dependency_ready_handler(None)
            self.assertTrue(task_gateway.start_dependency_dispatcher(interval_seconds=0.05))
            self.assertFalse(task_gateway.start_dependency_dispatcher(interval_seconds=0.05))
            status = task_gateway.dependency_dispatcher_status()

        self.assertTrue(status["started"])
        self.assertEqual("operation-dependency-dispatcher", status["claim_owner"])
        self.assertTrue(task_gateway.stop_dependency_dispatcher(timeout=2))

    def test_schema_config_snapshot_object_is_consumed_without_defining_config(self):
        from core import codex_operation_service
        from config import schema

        snapshot = schema.ConfigSnapshot(
            values={
                "CODEX_OAUTH_DRIVER": "same_as_registration",
                "REGISTRATION_DRIVER": "RoxyBrowser",
                "CODEX_AUTH_URL_SOURCE": "CPA",
                "SMS_PROVIDER": "L",
                "SMS_COUNTRY": "10",
                "ACCOUNT_ACTION_PROXY_MODE": "provider:1024proxy",
                "ACCOUNT_PASSWORD_PROXY_MODE": "direct",
                "ACCOUNT_2FA_PROXY_MODE": "registration",
                "ACCOUNT_PLAN_CHECK_PROXY_MODE": "direct",
                "ACCOUNT_LIVE_CHECK_PROXY_MODE": "direct",
                "ACCOUNT_REFRESH_AT_PROXY_MODE": "registration",
                "ACCOUNT_CODEX_PROXY_MODE": "registration",
                "UNRELATED_GLOBAL_SETTING": "must-not-persist",
                "NESTED_UNRELATED": {"secretish": "no"},
            },
            sources={
                "CODEX_OAUTH_DRIVER": "config.codex",
                "UNRELATED_GLOBAL_SETTING": "config.other",
            },
            revision=17,
        )
        # Patch the real provider on the already-imported package. Replacing
        # only sys.modules leaves config.schema pointing at its cached module
        # and can silently exercise live defaults instead of this fixture.
        with (
            patch.object(codex_operation_service, "_CONFIG_SNAPSHOT_PROVIDER", None),
            patch.object(schema, "non_sensitive_snapshot", return_value=snapshot),
        ):
            result = codex_operation_service._config_snapshot()

        self.assertEqual("roxybrowser", result["oauth_driver"])
        self.assertEqual("cpa", result["auth_source"])
        self.assertEqual("l", result["sms_provider"])
        self.assertEqual("10", result["sms_country"])
        self.assertEqual("provider:1024proxy", result["account_proxy_mode"])
        self.assertEqual("direct", result["account_proxy_modes"]["password"])
        self.assertEqual(17, result["config_snapshot_revision"])
        self.assertNotIn("sources", result)
        self.assertNotIn("UNRELATED_GLOBAL_SETTING", result)
        self.assertNotIn("NESTED_UNRELATED", result)
        self.assertNotIn("config_snapshot_version", result)


if __name__ == "__main__":
    unittest.main()
