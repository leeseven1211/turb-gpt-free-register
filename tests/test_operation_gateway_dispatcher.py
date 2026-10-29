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
            self.assertIn("native_operations", kwargs["source_systems"])
            self.assertNotIn("account_action_tasks", kwargs["source_systems"])
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

    def test_provider_capacity_skips_full_provider_without_blocking_other_provider(self):
        from core.operations import task_gateway

        submitted = []
        callbacks = []
        completed = set()
        rows = [
            {"id": 7101, "task_type": "maintenance_capacity_test", "source_system": "native_operations", "data": {"provider_id": "lumen_flow"}},
            {"id": 7102, "task_type": "maintenance_capacity_test", "source_system": "native_operations", "data": {"provider_id": "lumen_flow"}},
            {"id": 7103, "task_type": "maintenance_capacity_test", "source_system": "native_operations", "data": {"provider_id": "huanguang"}},
        ]

        class Future:
            def add_done_callback(self, callback):
                callbacks.append(callback)

        class Executor:
            def available_slots(self):
                return 3

            def try_submit(self, handler, run_id):
                submitted.append(int(run_id))
                return Future()

        operation = SimpleNamespace(
            list_dispatchable_runs=lambda **_kwargs: [
                row for row in rows if int(row["id"]) not in completed
            ]
        )
        try:
            with (
                patch.object(task_gateway, "_operation", return_value=operation),
                patch.object(task_gateway, "_executor", return_value=Executor()),
            ):
                task_gateway.register_dispatch_handler(
                    "maintenance_capacity_test",
                    lambda _run_id: None,
                    dispatch_capacity_key=lambda run: run["data"]["provider_id"],
                    dispatch_capacity_limit=lambda _key: 1,
                )
                self.assertEqual(2, task_gateway.dispatch_registered_once(limit=10))
                self.assertEqual([7101, 7103], submitted)
                completed.add(7101)
                callbacks[0](None)
                self.assertEqual(1, task_gateway.dispatch_registered_once(limit=10))
                for callback in callbacks[1:]:
                    callback(None)
        finally:
            task_gateway.unregister_dispatch_handler("maintenance_capacity_test")
            for run_id in (7101, 7102, 7103):
                task_gateway.release_dispatch(run_id)

        self.assertEqual([7101, 7103, 7102], submitted)

    def test_provider_capacity_is_released_when_executor_rejects_submission(self):
        from core.operations import task_gateway

        submitted = []
        rows = [
            {"id": 7201, "task_type": "maintenance_capacity_reject_test", "source_system": "native_operations", "data": {"provider_id": "lumen_flow"}},
            {"id": 7202, "task_type": "maintenance_capacity_reject_test", "source_system": "native_operations", "data": {"provider_id": "lumen_flow"}},
        ]

        class Future:
            def add_done_callback(self, callback):
                callback(self)

        class Executor:
            def available_slots(self):
                return 2

            def try_submit(self, handler, run_id):
                submitted.append(int(run_id))
                if int(run_id) == 7201:
                    raise RuntimeError("executor unavailable")
                return Future()

        operation = SimpleNamespace(list_dispatchable_runs=lambda **_kwargs: rows)
        try:
            with (
                patch.object(task_gateway, "_operation", return_value=operation),
                patch.object(task_gateway, "_executor", return_value=Executor()),
            ):
                task_gateway.register_dispatch_handler(
                    "maintenance_capacity_reject_test",
                    lambda _run_id: None,
                    dispatch_capacity_key=lambda run: run["data"]["provider_id"],
                    dispatch_capacity_limit=lambda _key: 1,
                )
                self.assertEqual(1, task_gateway.dispatch_registered_once(limit=10))
        finally:
            task_gateway.unregister_dispatch_handler("maintenance_capacity_reject_test")
            for run_id in (7201, 7202):
                task_gateway.release_dispatch(run_id)

        self.assertEqual([7201, 7202], submitted)

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

    def test_single_slot_rotates_initial_and_huanguang_continuation(self):
        from core.operations import task_gateway

        submitted, callbacks = [], []
        rows = [
            {"id": 7301, "task_type": "extract_link", "source_system": "native_operations", "data": {"provider_id": "huanguang"}},
            {"id": 7302, "task_type": "extract_link", "source_system": "native_operations", "data": {"provider_id": "huanguang", "extract_poll_continuation": True}},
        ]

        class Future:
            def add_done_callback(self, callback):
                callbacks.append(callback)

        class Executor:
            def available_slots(self):
                return 1

            def try_submit(self, _handler, run_id):
                submitted.append(run_id)
                return Future()

        def list_runs(**kwargs):
            return sorted(rows, key=lambda row: row["data"].get("extract_poll_continuation", False)
                          != kwargs.get("prioritize_continuations", False))

        with (
            patch.object(task_gateway, "_operation", return_value=SimpleNamespace(list_dispatchable_runs=list_runs)),
            patch.object(task_gateway, "_executor", return_value=Executor()),
        ):
            previous = task_gateway._run_handler_snapshot()[0].get("extract_link")
            previous_capacity = task_gateway._run_handler_snapshot()[1].get("extract_link")
            try:
                task_gateway.register_dispatch_handler("extract_link", lambda _run_id: None,
                    dispatch_capacity_key=lambda _run: "huanguang", dispatch_capacity_limit=lambda _key: 1)
                for _ in range(4):
                    self.assertEqual(1, task_gateway.dispatch_registered_once(limit=10))
                    callbacks[-1](None)
            finally:
                task_gateway.unregister_dispatch_handler("extract_link")
                if previous:
                    task_gateway.register_dispatch_handler("extract_link", previous[0], source_systems=previous[1],
                        dispatch_capacity_key=previous_capacity[0] if previous_capacity else None,
                        dispatch_capacity_limit=previous_capacity[1] if previous_capacity else None)
                for row in rows:
                    task_gateway.release_dispatch(row["id"])
        self.assertEqual({7301, 7302}, set(submitted[:2]))
        self.assertEqual([submitted[0], submitted[1], submitted[0], submitted[1]], submitted)

    def test_deferred_handler_returns_without_terminal_finish(self):
        from core.operations import task_gateway

        queued = {"id": 7350, "task_id": 7351, "task_type": "maintenance_deferred_test", "data": {}}

        def requeue(_run_id, **kwargs):
            queued.update(status="queued", data=kwargs.get("data") or {})
            return queued

        def fail_terminal(*_args, **_kwargs):
            self.fail("延期执行不能写入终态")

        operation = SimpleNamespace(claim_run=lambda *_args, **_kwargs: queued,
            is_run_cancel_requested=lambda *_args: False, requeue_claimed_run=requeue,
            finish_run=fail_terminal)

        def handler(context):
            self.assertFalse(context.deferred)
            context.defer(delay_seconds=5, reason="等待远端状态", data={"extract_poll_continuation": True})
            self.assertTrue(context.deferred)

        try:
            with patch.object(task_gateway, "_operation", return_value=operation):
                task_gateway.register_operation_handler("maintenance_deferred_test", handler)
                result = task_gateway._execute_operation_handler("maintenance_deferred_test", 7350)
        finally:
            task_gateway.unregister_operation_handler("maintenance_deferred_test")
        self.assertEqual("deferred", result["status"])
        self.assertEqual("queued", queued["status"])
        self.assertTrue(queued["data"]["extract_poll_continuation"])

    def test_continuations_use_two_slots_without_hiding_initial_work(self):
        from core.operations import task_gateway

        submitted, callbacks = [], []
        rows = [
            {"id": number, "task_type": "extract_link", "source_system": "native_operations", "data": {
                "provider_id": "huanguang", "extract_poll_continuation": number < 7490}}
            for number in range(7400, 7500)
        ]

        class Future:
            def add_done_callback(self, callback):
                callbacks.append(callback)

        class Executor:
            def available_slots(self):
                return 10

            def try_submit(self, _handler, run_id):
                submitted.append(run_id)
                return Future()

        def list_runs(**kwargs):
            continuation, initial = rows[:90], rows[90:]
            if not kwargs.get("prioritize_continuations", False):
                continuation, initial = initial, continuation
            mixed = [row for pair in zip(continuation, initial) for row in pair]
            mixed.extend(continuation[len(initial):])
            return mixed[:kwargs["limit"]]

        previous = task_gateway._run_handler_snapshot()[0].get("extract_link")
        previous_capacity = task_gateway._run_handler_snapshot()[1].get("extract_link")
        try:
            with (
                patch.object(task_gateway, "_operation", return_value=SimpleNamespace(list_dispatchable_runs=list_runs)),
                patch.object(task_gateway, "_executor", return_value=Executor()),
            ):
                task_gateway.register_dispatch_handler("extract_link", lambda _run_id: None,
                    dispatch_capacity_key=lambda _run: {"huanguang": 10, "batch:1": 10},
                    dispatch_capacity_limit=lambda _key: 10)
                self.assertEqual(10, task_gateway.dispatch_registered_once(limit=64))
                self.assertEqual(2, sum(run_id < 7490 for run_id in submitted))
                self.assertEqual(8, sum(run_id >= 7490 for run_id in submitted))
        finally:
            for callback in callbacks:
                callback(None)
            task_gateway.unregister_dispatch_handler("extract_link")
            if previous:
                task_gateway.register_dispatch_handler("extract_link", previous[0], source_systems=previous[1],
                    dispatch_capacity_key=previous_capacity[0] if previous_capacity else None,
                    dispatch_capacity_limit=previous_capacity[1] if previous_capacity else None)
            for row in rows:
                task_gateway.release_dispatch(row["id"])

    def test_legacy_continuation_capacity_preserves_initial_slots(self):
        from core.operations import task_gateway

        continuation = {"task_type": "extract_link", "data": {
            "provider_id": "legacy", "extract_poll_continuation": True}}
        initial = {"task_type": "extract_link", "data": {"provider_id": "legacy"}}
        capacity = (lambda _run: {"legacy": 10, "batch:legacy": 10}, lambda _key: 10)
        tokens = []
        try:
            for _ in range(2):
                accepted, token = task_gateway._reserve_dispatch_capacity("extract_link", continuation, capacity)
                self.assertTrue(accepted)
                tokens.append(token)
            accepted, token = task_gateway._reserve_dispatch_capacity("extract_link", continuation, capacity)
            if accepted:
                tokens.append(token)
            self.assertFalse(accepted)
            accepted, token = task_gateway._reserve_dispatch_capacity("extract_link", initial, capacity)
            self.assertTrue(accepted)
            tokens.append(token)
        finally:
            for token in tokens:
                task_gateway._release_dispatch_capacity(token)

    def test_single_slot_rotates_initial_and_legacy_continuation(self):
        from core.operations import task_gateway

        submitted, callbacks = [], []
        rows = [
            {"id": 9301, "task_type": "extract_link", "source_system": "native_operations", "data": {"provider_id": "legacy"}},
            {"id": 9302, "task_type": "extract_link", "source_system": "native_operations", "data": {"provider_id": "legacy", "extract_poll_continuation": True}},
        ]

        class Future:
            def add_done_callback(self, callback):
                callbacks.append(callback)

        class Executor:
            def available_slots(self):
                return 1

            def try_submit(self, _handler, run_id):
                submitted.append(run_id)
                return Future()

        def list_runs(**kwargs):
            return sorted(rows, key=lambda row: row["data"].get("extract_poll_continuation", False)
                          != kwargs.get("prioritize_continuations", False))

        previous = task_gateway._run_handler_snapshot()[0].get("extract_link")
        previous_capacity = task_gateway._run_handler_snapshot()[1].get("extract_link")
        try:
            with (patch.object(task_gateway, "_operation", return_value=SimpleNamespace(list_dispatchable_runs=list_runs)),
                  patch.object(task_gateway, "_executor", return_value=Executor())):
                task_gateway.register_dispatch_handler("extract_link", lambda _run_id: None,
                    dispatch_capacity_key=lambda _run: "legacy", dispatch_capacity_limit=lambda _key: 1)
                for _ in range(4):
                    self.assertEqual(1, task_gateway.dispatch_registered_once(limit=10))
                    callbacks[-1](None)
            self.assertEqual({9301, 9302}, set(submitted[:2]))
            self.assertEqual([submitted[0], submitted[1], submitted[0], submitted[1]], submitted)
        finally:
            task_gateway.unregister_dispatch_handler("extract_link")
            if previous:
                task_gateway.register_dispatch_handler("extract_link", previous[0], source_systems=previous[1],
                    dispatch_capacity_key=previous_capacity[0] if previous_capacity else None,
                    dispatch_capacity_limit=previous_capacity[1] if previous_capacity else None)
            for row in rows:
                task_gateway.release_dispatch(row["id"])

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

    def test_open_source_registration_drivers_resolve_to_supported_codex_snapshot_drivers(self):
        from core import codex_operation_service

        for registration_driver, oauth_driver in (("roxy_oss", "roxy"), ("protocol_oss", "protocol")):
            with self.subTest(driver=registration_driver):
                result = codex_operation_service._project_config_snapshot({
                    "CODEX_OAUTH_DRIVER": "same_as_registration",
                    "REGISTRATION_DRIVER": registration_driver,
                }, 17)
                self.assertEqual(oauth_driver, result["oauth_driver"])
                explicit = codex_operation_service._project_config_snapshot({
                    "CODEX_OAUTH_DRIVER": "protocol",
                    "REGISTRATION_DRIVER": registration_driver,
                }, 17)
                self.assertEqual("protocol", explicit["oauth_driver"])

    def test_legacy_codex_snapshot_resolves_open_source_roxy_without_persisting_unsupported_driver(self):
        from core import codex_operation_service

        with patch("config.codex.CODEX_OAUTH_DRIVER", "same_as_registration"), patch(
            "config.roxybrowser.REGISTRATION_DRIVER", "roxy_oss"
        ):
            result = codex_operation_service._legacy_config_snapshot()

        self.assertEqual("roxy", result["oauth_driver"])

    def test_codex_following_open_source_roxy_dispatches_browser_oauth(self):
        from core import codex_oauth

        expected = {"ok": True, "status": "success"}
        with (
            patch("config.codex.CODEX_OAUTH_DRIVER", "same_as_registration"),
            patch("config.roxybrowser.REGISTRATION_DRIVER", "roxy_oss"),
            patch("core.roxy_codex_oauth.run_roxy_codex_oauth", return_value=expected) as roxy,
            patch.object(codex_oauth, "BrowserSession") as protocol_session,
        ):
            result = codex_oauth.run_codex_oauth("test@example.test", proxy="", force=True)

        self.assertEqual(result, expected)
        self.assertEqual(roxy.call_args.args, ("test@example.test",))
        protocol_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
