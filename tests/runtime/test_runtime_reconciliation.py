"""Recovery ownership and ordering without a database or background workers."""
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import Mock, patch

from core.operations import reconciliation, task_gateway


class RuntimeReconciliationTests(TestCase):
    def test_source_ids_are_qualified_by_the_legacy_namespace(self):
        fences = {
            "account_ids": [11, "11", 12],
            "source_fences": [
                {"source_system": "native_operations", "source_id": "99"},
                {"source_system": "registration_jobs", "source_id": "99"},
                {"source_system": "account_action_tasks", "source_id": "88"},
            ],
        }
        with patch.object(
            reconciliation.operation_task_store, "list_active_runtime_recovery_exclusions", return_value=fences,
        ) as query:
            result = reconciliation.legacy_recovery_exclusions(
                {" registration_resume ", "registration_resume"},
                legacy_source_systems=("registration_jobs",),
            )
            boolean_result = reconciliation.legacy_recovery_exclusions({"registration_resume"})

        self.assertFalse(result["skip_all"])
        self.assertEqual([11, 12], result["account_ids"])
        self.assertEqual(["99"], result["source_ids"])
        self.assertEqual([], boolean_result["source_ids"])
        self.assertEqual(("registration_resume",), query.call_args.kwargs["task_types"])

    def test_unknown_or_malformed_ownership_fails_closed(self):
        for value in (
            None,
            {"account_ids": ["invalid"]},
            {"source_fences": [None]},
            {"source_fences": [{"source_system": "registration_jobs"}]},
            {"source_ids": ["42"]},
        ):
            with self.subTest(value=value), patch.object(
                reconciliation.operation_task_store, "list_active_runtime_recovery_exclusions", return_value=value,
            ):
                result = reconciliation.legacy_recovery_exclusions(
                    {"registration_resume"}, legacy_source_systems=("registration_jobs",),
                    operation_logger=Mock(),
                )
            self.assertTrue(result["skip_all"])
            self.assertEqual([], result["account_ids"])
            self.assertEqual([], result["source_ids"])

        with patch.object(
            reconciliation.operation_task_store, "list_active_runtime_recovery_exclusions",
            side_effect=RuntimeError("unavailable"),
        ), patch.object(reconciliation.operation_task_store, "has_active_runtime_operations") as fallback:
            self.assertFalse(reconciliation.legacy_recovery_allowed({"live_check"}, operation_logger=Mock()))
        fallback.assert_not_called()

    def test_older_storage_fallback_preserves_conservative_recovery(self):
        for active in (False, True, RuntimeError("unavailable")):
            with self.subTest(active=active), patch.object(
                reconciliation.operation_task_store, "list_active_runtime_recovery_exclusions",
                side_effect=AttributeError("older facade"),
            ), patch.object(
                reconciliation.operation_task_store, "has_active_runtime_operations",
                **({"side_effect": active} if isinstance(active, Exception) else {"return_value": active}),
            ):
                result = reconciliation.legacy_recovery_exclusions({"live_check"}, operation_logger=Mock())
            self.assertEqual(active is not False, result["skip_all"])

    def _patch_startup_recovery(self, stack, *, remote_failure=False):
        order = []
        callbacks = {}
        targets = (
            (reconciliation.operation_task_store, "recover_interrupted_runtime_runs", "native"),
            (reconciliation.operation_task_store, "repair_stale_compatibility_projections", "projection"),
            (reconciliation.db, "recover_interrupted_live_checks", "live"),
            (reconciliation.db, "recover_interrupted_plan_checks", "plan"),
            (reconciliation.extract_link_service, "resume_known_remote_jobs", "remote"),
            (reconciliation.db, "recover_interrupted_registration_jobs", "registration"),
            (reconciliation.account_task_store, "recover_interrupted", "account"),
        )
        for owner, name, label in targets:
            def record(*_args, label=label, **_kwargs):
                order.append(label)
                if label == "remote" and remote_failure:
                    raise RuntimeError("remote unavailable")
                return 0
            callbacks[label] = stack.enter_context(patch.object(owner, name, side_effect=record))
        stack.enter_context(patch.object(
            reconciliation.operation_task_store, "list_active_runtime_recovery_exclusions",
            return_value={
                "account_ids": [11],
                "source_fences": [
                    {"source_system": "registration_jobs", "source_id": "200"},
                    {"source_system": "account_action_tasks", "source_id": "300"},
                    {"source_system": "native_operations", "source_id": "999"},
                ],
            },
        ))
        return order, callbacks

    def test_startup_recovers_inline_states_before_remote_resumption(self):
        for remote_failure in (False, True):
            with self.subTest(remote_failure=remote_failure), ExitStack() as stack:
                order, callbacks = self._patch_startup_recovery(stack, remote_failure=remote_failure)
                reconciliation.recover_before_dispatchers(Mock())
            self.assertEqual(["native", "projection", "live", "plan", "remote", "registration", "account"], order)
            callbacks["live"].assert_called_once_with(excluded_account_ids=[11])
            callbacks["plan"].assert_called_once_with(excluded_account_ids=[11])
            callbacks["registration"].assert_called_once_with(excluded_account_ids=[11], excluded_source_ids=["200"])
            callbacks["account"].assert_called_once_with(excluded_account_ids=[11], excluded_source_ids=["300"])

    def test_failed_native_startup_recovery_does_not_continue(self):
        with ExitStack() as stack:
            order, callbacks = self._patch_startup_recovery(stack)
            callbacks["native"].side_effect = RuntimeError("storage unavailable")
            with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
                reconciliation.recover_before_dispatchers(Mock())
        self.assertEqual([], order)
        callbacks["projection"].assert_not_called()

    def test_one_uncertain_category_does_not_suppress_other_legacy_recovery(self):
        with ExitStack() as stack:
            order, callbacks = self._patch_startup_recovery(stack)
            def exclusions(task_types, **_kwargs):
                return {
                    "skip_all": set(task_types) == {"live_check", "token_refresh", "account_inspection"},
                    "account_ids": [],
                    "source_ids": [],
                }
            stack.enter_context(patch.object(reconciliation, "legacy_recovery_exclusions", side_effect=exclusions))
            reconciliation.recover_before_dispatchers(Mock())
        callbacks["live"].assert_not_called()
        self.assertEqual(["native", "projection", "plan", "remote", "registration", "account"], order)

    def test_ready_dependency_recovery_only_notifies_existing_claim_owner(self):
        with patch.object(
            reconciliation.account_task_store, "drain_ready_dependencies", return_value=2,
        ) as drain, patch.object(reconciliation.operation_task_store, "claim_task_dependency") as claim:
            reconciliation.recover_ready_dependencies(Mock())
        drain.assert_called_once_with(initialized=True)
        claim.assert_not_called()
        with patch.object(
            reconciliation.account_task_store, "drain_ready_dependencies", side_effect=RuntimeError("unavailable"),
        ):
            reconciliation.recover_ready_dependencies(Mock())

    def test_browser_capability_gate_does_not_skip_debug_cleanup(self):
        with patch("config.deployment.browser_enabled", return_value=False), patch(
            "core.browser.roxy.client.cleanup_orphaned_profiles",
        ) as browser, patch("core.registration.debug.cleanup_expired_artifacts", return_value={}) as debug:
            reconciliation.recover_local_artifacts(Mock())
        browser.assert_not_called()
        debug.assert_called_once_with()

    def test_background_recovery_keeps_extract_and_codex_order(self):
        order = []
        with patch.object(
            reconciliation, "legacy_recovery_exclusions", return_value={"skip_all": False, "account_ids": [11]},
        ), patch.object(
            reconciliation.db, "recover_interrupted_extract_links", side_effect=lambda **_kwargs: order.append("extract") or 0,
        ) as extract, patch.object(
            reconciliation.codex_operation_service, "resume_queued", side_effect=lambda: order.append("codex") or 0,
        ):
            reconciliation.recover_account_background_state(Mock())
        self.assertEqual(["extract", "codex"], order)
        extract.assert_called_once_with(excluded_account_ids=[11])

    def test_deferred_proxy_backfill_runs_after_worker_start(self):
        with patch.object(
            reconciliation.db, "backfill_account_registration_proxy_context", return_value=3,
        ) as backfill:
            self.assertEqual(3, reconciliation.run_deferred_account_proxy_backfill(Mock()))
        backfill.assert_called_once_with()

    def test_periodic_recovery_repairs_projections_even_when_no_run_changed(self):
        with patch.object(
            reconciliation.operation_task_store, "recover_interrupted_runtime_runs", return_value=0,
        ), patch("core.accounts.deactivation.mail_scan.reconcile_interrupted_scans", side_effect=RuntimeError("unavailable")), patch.object(
            reconciliation.extract_link_service, "resume_known_remote_jobs",
        ) as resume:
            self.assertEqual(0, reconciliation.recover_stale_runtime_runs(Mock()))
        resume.assert_called_once_with(continuous_only=True)

    def test_periodic_storage_failure_does_not_continue_domain_recovery(self):
        with patch.object(
            reconciliation.operation_task_store, "recover_interrupted_runtime_runs", side_effect=RuntimeError("unavailable"),
        ), patch.object(reconciliation, "reconcile_recovered_projections") as project, patch.object(
            reconciliation.extract_link_service, "resume_known_remote_jobs",
        ) as resume:
            self.assertEqual(0, reconciliation.recover_stale_runtime_runs(Mock()))
        project.assert_not_called()
        resume.assert_not_called()

    def test_gateway_remains_the_only_periodic_recovery_clock(self):
        with patch.object(task_gateway, "_LAST_RUNTIME_RECOVERY_AT", 0.0), patch.object(
            reconciliation, "recover_stale_runtime_runs", side_effect=[0, 2],
        ) as recover:
            self.assertEqual(0, task_gateway._recover_stale_runtime_runs_if_due(now=60.0))
            self.assertEqual(0, task_gateway._recover_stale_runtime_runs_if_due(now=90.0))
            self.assertEqual(2, task_gateway._recover_stale_runtime_runs_if_due(now=121.0))
        self.assertEqual(2, recover.call_count)
