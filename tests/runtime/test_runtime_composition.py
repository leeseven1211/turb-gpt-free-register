"""Runtime composition regressions migrated from the Phase 6 T1 candidate.

Exercise product modules directly with injected components and an offline owner.
"""
from __future__ import annotations

import logging
import types
import unittest
from unittest.mock import patch

from core.runtime import bindings, composition, context, manifest, process
from core.runtime.instance_owner import OwnerError


class FakeOwner:
    def __init__(self, events, *, reject=False):
        self.events, self.reject = events, reject
        self.alive = False
        self.close_result = True

    def start(self):
        self.events.append("owner:start")
        if self.reject:
            raise RuntimeError("owner_already_running")
        self.alive = True

    def require_owner(self):
        if not self.alive:
            raise RuntimeError("owner_lost")

    def close(self, timeout=2.0):
        self.events.append("owner:close")
        if self.close_result:
            self.alive = False
        return self.close_result


class RuntimeCompositionTests(unittest.TestCase):
    def setUp(self):
        self.context = context
        self.manifest = manifest
        self.composition = composition
        self.bindings = bindings
        self.process = process
        self.events = []
        # Process installation is global; isolate it without reloading modules
        # or replacing the product objects held by other tests.
        for name in ("_RUNTIME", "_LIFECYCLE"):
            guard = patch.object(process, name, None)
            guard.start()
            self.addCleanup(guard.stop)

    def runtime(self, mode="worker", *, fail=None, block=None, optional_fail=False):
        context = self.context.RuntimeContext(mode, logging.getLogger("runtime-composition-test"))
        owner = FakeOwner(self.events)
        hooks = {}
        for spec in self.manifest.COMPONENTS:
            def start(ctx, name=spec.name):
                self.events.append(name)
                self.assertFalse(ctx.admission.is_open(), name)
                if name == block:
                    ctx.admission.block("owner_lost")
                if name == fail:
                    raise ValueError("private arbitrary exception text")
            def stop(ctx, remaining, name=spec.name):
                self.assertGreaterEqual(remaining, 0)
                self.assertFalse(ctx.admission.is_open())
                self.events.append(f"stop:{name}")
                return True
            hooks[spec.name] = self.composition.ComponentHooks(start, stop)
        return self.composition.RuntimeController(context, hooks, owner=owner), owner

    def test_web_starts_without_owner_or_loading_execution_components(self):
        runtime = self.composition.RuntimeController(self.context.RuntimeContext("web"), {})
        self.assertTrue(runtime.start())
        self.assertFalse(runtime.start())
        self.assertFalse(runtime.context.admission.is_open())
        self.assertEqual(["web"], list(runtime.context.admission.reasons()))
        self.assertEqual({}, runtime.status()["components"])
        self.assertTrue(runtime.status()["startup_complete"])

    def test_execution_without_owner_fails_before_domain_side_effects(self):
        runtime, _owner = self.runtime()
        runtime.owner = None
        with self.assertRaisesRegex(self.composition.RuntimeStartError, "owner_required"):
            runtime.start()
        self.assertEqual([], self.events)
        self.assertFalse(runtime.context.admission.is_open())

    def test_invalid_mode_rejected_before_composition(self):
        with self.assertRaisesRegex(ValueError, "runtime_mode_invalid"):
            self.context.RuntimeContext("other")

    def test_rejected_owner_precedes_initialization_and_recovery(self):
        runtime, owner = self.runtime()
        owner.reject = True
        with self.assertRaises(self.composition.RuntimeStartError):
            runtime.start()
        self.assertEqual(["owner:start", "owner:close"], self.events)
        self.assertFalse(runtime.status()["startup_complete"])

    def test_missing_binding_rejected_before_owner_acquisition(self):
        runtime, _owner = self.runtime()
        del runtime.components["registration_dispatcher"]
        with self.assertRaisesRegex(self.composition.RuntimeStartError, "component_binding_missing"):
            runtime.start()
        self.assertEqual([], self.events)

    def test_combined_and_worker_have_same_explicit_handlers_and_recovery_order(self):
        captures = []
        for mode in ("combined", "worker"):
            self.events = []
            runtime, _owner = self.runtime(mode)
            self.assertTrue(runtime.start())
            self.assertFalse(runtime.start())
            captures.append(list(self.events))
            self.assertTrue(runtime.context.admission.is_open())
            self.assertTrue(runtime.status()["startup_complete"])
        self.assertEqual(captures[0], captures[1])
        order = captures[0]
        self.assertEqual("owner:start", order[0])
        self.assertLess(order.index("registration_storage"), order.index("recover_before_handlers"))
        self.assertLess(order.index("operation_storage"), order.index("recover_before_handlers"))
        self.assertLess(order.index("recover_before_handlers"), order.index("proxy_pool"))
        self.assertLess(order.index("maintenance_handlers"), order.index("recover_before_dispatchers"))
        self.assertLess(order.index("c2a_monitor_storage"), order.index("c2a_monitor_handler"))
        self.assertLess(order.index("c2a_monitor_handler"), order.index("operation_dispatcher"))
        self.assertLess(order.index("codex_retry_handler"), order.index("operation_dispatcher"))
        self.assertLess(order.index("codex_refresh_handler"), order.index("operation_dispatcher"))
        self.assertLess(order.index("recover_before_dispatchers"), order.index("projection_worker"))
        self.assertLess(order.index("bulk_workers"), order.index("recover_ready_dependencies"))
        self.assertLess(order.index("sms_cancel_worker"), order.index("recover_account_background_state"))
        self.assertLess(order.index("recover_account_background_state"), order.index("at_refresher"))

    def test_unblocking_startup_cannot_clear_owner_or_configuration_failure(self):
        runtime, _owner = self.runtime(block="recover_account_background_state")
        runtime.context.admission.block("config")
        runtime.start()
        self.assertEqual(("config", "owner_lost"), runtime.context.admission.reasons())
        runtime.context.admission.unblock("config")
        self.assertFalse(runtime.context.admission.is_open())

    def test_owner_loss_during_start_fails_before_next_component(self):
        runtime, owner = self.runtime()
        original = runtime.components["recover_before_handlers"].start
        def lose(ctx):
            original(ctx)
            owner.alive = False
            ctx.admission.block("owner_lost")
        runtime.components["recover_before_handlers"] = self.composition.ComponentHooks(lose)
        with self.assertRaises(self.composition.RuntimeStartError):
            runtime.start()
        self.assertNotIn("proxy_pool", self.events)
        self.assertFalse(runtime.status()["startup_complete"])
        self.assertIn("owner_lost", runtime.context.admission.reasons())

    def test_start_failure_cleans_partially_started_service_and_keeps_error_sanitized(self):
        runtime, _owner = self.runtime(fail="registration_dispatcher")
        with self.assertRaisesRegex(self.composition.RuntimeStartError, "component_start_failed"):
            runtime.start()
        stops = [entry for entry in self.events if entry.startswith("stop:")]
        self.assertEqual(
            ["stop:registration_dispatcher", "stop:projection_worker", "stop:proxy_pool",
             "stop:config_observer", "stop:settlement"], stops,
        )
        self.assertEqual("owner:close", self.events[-1])
        self.assertNotIn("private arbitrary", repr(runtime.status()))
        self.assertFalse(runtime.status()["startup_complete"])

    def test_incomplete_stop_preserves_owner_and_can_be_retried(self):
        runtime, _owner = self.runtime()
        runtime.start()
        live = runtime.components["projection_worker"]
        runtime.components["projection_worker"] = self.composition.ComponentHooks(live.start, lambda _c, _t: False)
        self.assertFalse(runtime.stop(timeout=0))
        self.assertNotIn("owner:close", self.events)
        self.assertEqual(["settlement", "projection_worker"], runtime.status()["remaining_components"])
        runtime.components["projection_worker"] = live
        self.assertTrue(runtime.stop(timeout=1))
        self.assertEqual("owner:close", self.events[-1])

    def test_missing_stop_or_none_result_is_not_confirmed_stopped(self):
        for stop in (None, lambda _c, _t: None):
            with self.subTest(stop=stop):
                self.events = []
                runtime, _owner = self.runtime()
                runtime.start()
                runtime.components["sms_cancel_worker"] = self.composition.ComponentHooks(lambda _c: None, stop)
                self.assertFalse(runtime.stop(timeout=0))
                self.assertNotIn("owner:close", self.events)
                self.assertEqual(["settlement", "sms_cancel_worker"], runtime.status()["remaining_components"])

    def test_owner_close_timeout_is_not_reported_stopped(self):
        runtime, owner = self.runtime()
        runtime.start()
        owner.close_result = False
        self.assertFalse(runtime.stop(timeout=0))
        self.assertEqual("stop_incomplete", runtime.status()["state"])
        owner.close_result = True
        self.assertTrue(runtime.stop(timeout=1))

    def test_failed_owner_start_with_live_monitor_retains_cleanup_requirement(self):
        runtime, owner = self.runtime()
        owner.reject = True
        owner.close_result = False
        with self.assertRaises(self.composition.RuntimeStartError):
            runtime.start()
        self.assertIn("owner:close", self.events)
        self.assertTrue(runtime.status()["owner_cleanup_required"])
        self.assertFalse(runtime.stop(timeout=0))
        owner.close_result = True
        self.assertTrue(runtime.stop(timeout=0))
        self.assertFalse(runtime.status()["owner_cleanup_required"])

    def test_stop_order_must_cover_all_owned_services_before_mutation(self):
        runtime, _owner = self.runtime()
        runtime.start()
        count = len(self.events)
        with self.assertRaisesRegex(ValueError, "stop_order_incomplete"):
            runtime.stop(order=("projection_worker",))
        self.assertEqual(count, len(self.events))
        self.assertTrue(runtime.context.admission.is_open())

    def test_binding_catalog_is_lazy_and_handler_registration_uses_core_implementations(self):
        loaded = []
        called = []
        modules = {}
        def resolve(name):
            loaded.append(name)
            self.assertTrue(name.startswith("core."))
            self.assertFalse(name.startswith("webui."))
            if name not in modules:
                modules[name] = types.SimpleNamespace()
            return modules[name]
        hooks = self.bindings.build_components(resolve=resolve)
        self.assertEqual([], loaded)
        maintenance = resolve("core.accounts.liveness.service")
        maintenance.register_maintenance_operation_handlers = lambda: called.append("maintenance")
        gateway = resolve("core.operations.task_gateway")
        gateway.register_dispatch_handler = lambda name, handler: called.append((name, handler))
        codex = resolve("core.codex.operation_service")
        codex._execute_run = object()
        codex.register_handler = lambda: gateway.register_dispatch_handler("codex_retry", codex._execute_run)
        refresh = resolve("core.codex.token_refresh_service")
        refresh._register_worker = lambda: called.append("codex_refresh")
        ctx = self.context.RuntimeContext("worker")
        hooks["maintenance_handlers"].start(ctx)
        hooks["codex_retry_handler"].start(ctx)
        hooks["codex_refresh_handler"].start(ctx)
        self.assertEqual(["maintenance", ("codex_retry", codex._execute_run), "codex_refresh"], called)

    def test_failed_runtime_cannot_start_another_generation(self):
        runtime, _owner = self.runtime(fail="operation_storage")
        with self.assertRaises(self.composition.RuntimeStartError):
            runtime.start()
        count = len(self.events)
        with self.assertRaisesRegex(self.composition.RuntimeStartError, "runtime_restart_requires_new_context"):
            runtime.start()
        self.assertEqual(count, len(self.events))

    def test_missing_registered_handler_blocks_startup_before_recovery_and_dispatch(self):
        runtime, _owner = self.runtime()
        hooks = self.bindings.build_components(
            resolve=lambda name: types.SimpleNamespace(registered_dispatch_types=lambda: ("codex_retry",)),
        )
        self.assertIn("verify_handlers", hooks)
        runtime.components["verify_handlers"] = hooks["verify_handlers"]
        with self.assertRaisesRegex(self.composition.RuntimeStartError, "component_start_failed"):
            runtime.start()
        self.assertNotIn("recover_before_dispatchers", self.events)
        self.assertNotIn("operation_dispatcher", self.events)
        self.assertFalse(runtime.context.admission.is_open())

    def test_canonical_handler_set_is_verified_without_dispatching_a_run(self):
        names = (
            "account_setup_retry", "password_setup", "password_change", "twofa_setup", "twofa_change",
            "account_completion", "registration_resume", "account_inspection", "live_check", "token_refresh",
            "plan_check", "deactivation_mail", "extract_link", "email_change", "codex_retry",
            "codex_token_refresh", "sentinel_maintenance_check", "sub2api_scan", "sub2api_manual_upload",
            "c2a_session_reimport", "c2a_scan",
            "team_probe", "team_sync", "team_reverify", "team_join_request",
            "team_join", "team_invite", "team_accept", "team_outbox_drain",
            "sales_sync",
        )
        calls = []
        def resolve(name):
            self.assertEqual("core.operations.task_gateway", name)
            calls.append(name)
            return types.SimpleNamespace(registered_dispatch_types=lambda: names)
        hooks = self.bindings.build_components(resolve=resolve)
        self.assertIn("verify_handlers", hooks)
        hooks["verify_handlers"].start(self.context.RuntimeContext("worker"))
        self.assertEqual(["core.operations.task_gateway"], calls)

    def test_special_binding_arguments_preserve_logger_prewarm_and_dependency_callback(self):
        calls = []
        dependency_handler = object()
        logger = logging.getLogger("chosen-runtime")
        modules = {
            "core.proxy.pool": types.SimpleNamespace(start=lambda **kw: calls.append(("proxy", kw))),
            "core.operations.reconciliation": types.SimpleNamespace(
                recover_before_handlers=lambda active_logger: calls.append(("recovery", active_logger)),
            ),
            "core.accounts.completion_dependencies": types.SimpleNamespace(
                submit_ready_completion_dependency=dependency_handler,
            ),
            "core.operations.task_gateway": types.SimpleNamespace(
                set_dependency_ready_handler=lambda handler: calls.append(("dependency", handler)),
                stop_dispatcher=lambda **kw: calls.append(("stop", kw)) or True,
            ),
        }
        hooks = self.bindings.build_components(resolve=modules.__getitem__)
        ctx = self.context.RuntimeContext("worker", logger)
        hooks["proxy_pool"].start(ctx)
        hooks["recover_before_handlers"].start(ctx)
        hooks["dependency_handler"].start(ctx)
        self.assertTrue(hooks["operation_dispatcher"].stop(ctx, 0.25))
        self.assertEqual([
            ("proxy", {"prewarm": True}), ("recovery", logger), ("dependency", dependency_handler),
            ("stop", {"timeout": 0.25}),
        ], calls)

    def test_optional_start_failure_is_visible_and_its_partial_allocation_is_still_closed(self):
        runtime, _owner = self.runtime(fail="email_usage_reports")
        self.assertTrue(runtime.start())
        self.assertEqual(
            {"state": "start_failed", "error_type": "ValueError"},
            runtime.status()["components"]["email_usage_reports"],
        )
        self.assertTrue(runtime.stop())
        self.assertIn("stop:email_usage_reports", self.events)

    def test_process_facade_requires_explicit_installation_and_forbids_replacement(self):
        facade = self.process
        with self.assertRaisesRegex(self.composition.RuntimeStartError, "runtime_not_configured"):
            facade.start_runtime()
        runtime = self.composition.RuntimeController(self.context.RuntimeContext("web"), {})
        facade.install_runtime(runtime)
        facade.install_runtime(runtime)
        self.assertTrue(facade.start_runtime())
        self.assertFalse(facade.start_runtime())
        self.assertEqual("web", facade.runtime_status()["mode"])
        other = self.composition.RuntimeController(self.context.RuntimeContext("web"), {})
        with self.assertRaisesRegex(self.composition.RuntimeStartError, "runtime_already_configured"):
            facade.install_runtime(other)

    def test_uninstalled_context_is_explicit_and_never_grants_managed_execution(self):
        facade = self.process
        self.assertTrue(hasattr(facade, "get_runtime_context"))
        self.assertTrue(hasattr(facade, "execution_admitted"))
        self.assertIsNone(facade.get_runtime_context())
        self.assertFalse(facade.execution_admitted())

    def test_installed_role_admission_checks_owner_and_current_blockers(self):
        facade = self.process
        self.assertTrue(hasattr(facade, "get_runtime_context"))
        self.assertTrue(hasattr(facade, "execution_admitted"))
        runtime, owner = self.runtime()
        facade.install_runtime(runtime)
        self.assertIs(runtime.context, facade.get_runtime_context())
        self.assertFalse(facade.execution_admitted())
        runtime.start()
        self.assertTrue(facade.execution_admitted())
        runtime.context.admission.block("config")
        self.assertFalse(facade.execution_admitted())
        runtime.context.admission.unblock("config")
        owner.alive = False
        self.assertFalse(facade.execution_admitted())
        self.assertIn("owner_lost", runtime.context.admission.reasons())

    def test_web_never_grants_execution_even_when_someone_clears_its_gate(self):
        facade = self.process
        self.assertTrue(hasattr(facade, "execution_admitted"))
        runtime = self.composition.RuntimeController(self.context.RuntimeContext("web"), {})
        facade.install_runtime(runtime)
        runtime.start()
        runtime.context.admission.unblock("web")
        self.assertFalse(facade.execution_admitted())

    def test_owner_probe_pause_denies_execution_without_marking_owner_lost(self):
        facade = self.process
        runtime, owner = self.runtime()
        facade.install_runtime(runtime)
        runtime.start()
        runtime.context.admission.block("owner_probe_paused")
        with patch.object(owner, "require_owner", side_effect=OwnerError("owner_probe_paused")):
            self.assertFalse(facade.execution_owner_valid())
            self.assertFalse(facade.execution_admitted())
            self.assertEqual(("owner_probe_paused",), runtime.context.admission.reasons())
            self.assertFalse(facade.execution_owner_lost())
        owner.alive = False
        self.assertTrue(facade.execution_owner_lost())
        self.assertIn("owner_lost", runtime.context.admission.reasons())

    def test_owner_valid_allows_drain_settlement_without_new_admission(self):
        facade = self.process
        self.assertTrue(hasattr(facade, "execution_owner_valid"))
        runtime, owner = self.runtime()
        facade.install_runtime(runtime)
        self.assertFalse(facade.execution_owner_valid())
        runtime.start()
        runtime.context.admission.block("draining")
        self.assertTrue(facade.execution_owner_valid())
        self.assertFalse(facade.execution_admitted())
        runtime.components["projection_worker"] = self.composition.ComponentHooks(lambda _c: None, lambda _c, _t: False)
        self.assertFalse(runtime.stop(timeout=0))
        self.assertTrue(facade.execution_owner_valid())
        owner.alive = False
        self.assertFalse(facade.execution_owner_valid())
        self.assertIn("owner_lost", runtime.context.admission.reasons())

    def test_owner_valid_never_grants_uninstalled_web_or_released_owner(self):
        facade = self.process
        self.assertTrue(hasattr(facade, "execution_owner_valid"))
        self.assertFalse(facade.execution_owner_valid())
        web = self.composition.RuntimeController(self.context.RuntimeContext("web"), {})
        self.assertFalse(web.execution_owner_valid())
        runtime, _owner = self.runtime()
        runtime.start()
        self.assertTrue(runtime.stop())
        self.assertFalse(runtime.execution_owner_valid())


if __name__ == "__main__":
    unittest.main(verbosity=2)
