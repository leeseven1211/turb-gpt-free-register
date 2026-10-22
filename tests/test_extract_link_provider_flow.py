from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ExtractLinkProviderFlowTests(unittest.TestCase):
    def test_workbench_projection_keeps_account_reference_without_credentials(self):
        from core import extract_link_service

        item = extract_link_service._workbench_task_item({
            "task_id": 17,
            "run_id": 28,
            "account_id": 77,
            "task_data": {"provider_id": "lumen_flow", "link_type": "momo"},
            "access_token": "must-not-project",
        })

        self.assertEqual(77, item["account_id"])
        self.assertEqual("momo", item["link_type"])
        self.assertNotIn("access_token", item)
        self.assertNotIn("must-not-project", repr(item))

    def test_workbench_counts_running_separately_from_queued_before_status_filter(self):
        from core import extract_link_service

        rows = [
            {"task_id": task_id, "run_status": status}
            for task_id, status in enumerate(("queued", "running", "settling", "cancelling", "waiting", "success"), 1)
        ]
        with (
            patch("core.storage.extract_link_jobs.list_workbench_rows", return_value=rows) as list_rows,
            patch.object(extract_link_service.db, "get_accounts_for_jobs", return_value={}),
        ):
            result = extract_link_service.list_workbench_tasks(
                provider_id="lumen_flow", mode="extract_only", query="fixture", status="running",
            )

        list_rows.assert_called_once_with(provider_id="lumen_flow", mode="extract_only", query="fixture")
        self.assertEqual(6, result["counts"]["all"])
        self.assertEqual(5, result["counts"]["processing"])
        self.assertEqual(3, result["counts"]["running"])
        self.assertEqual(3, result["total"])
        self.assertEqual({2, 3, 4}, {item["task_id"] for item in result["items"]})

    def test_legacy_provider_mode_reads_its_own_platform_switches(self):
        from core import extract_link_service

        values = {
            "EXTRACT_LINK_ENABLED": True,
            "EXTRACT_LINK_EXTRACT_ENABLED": True,
            "EXTRACT_LINK_MANUAL_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_AUTO_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_LEGACY_ENABLED": True,
            "EXTRACT_LINK_LEGACY_EXTRACT_ENABLED": False,
            "EXTRACT_LINK_LEGACY_MANUAL_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_LEGACY_AUTO_PAYMENT_ENABLED": False,
        }
        with patch.object(
            extract_link_service,
            "_runtime_setting",
            side_effect=lambda name, default=None: values.get(name, default),
        ):
            self.assertFalse(extract_link_service._provider_mode_enabled("legacy", "extract_only"))
            values["EXTRACT_LINK_LEGACY_EXTRACT_ENABLED"] = True
            self.assertTrue(extract_link_service._provider_mode_enabled("legacy", "manual_payment"))
            values["EXTRACT_LINK_MANUAL_PAYMENT_ENABLED"] = False
            self.assertFalse(extract_link_service._provider_mode_enabled("legacy", "manual_payment"))
            values["EXTRACT_LINK_MANUAL_PAYMENT_ENABLED"] = True
            self.assertFalse(extract_link_service._provider_mode_enabled("legacy", "auto_payment"))

    def test_legacy_provider_keeps_existing_api_and_cdk_config_keys(self):
        from core import extract_link_service

        values = {
            "EXTRACT_LINK_ENABLED": True,
            "EXTRACT_LINK_LEGACY_ENABLED": True,
            "EXTRACT_LINK_EXTRACT_ENABLED": True,
            "EXTRACT_LINK_LEGACY_EXTRACT_ENABLED": True,
            "EXTRACT_LINK_API_BASE": "https://legacy.example.test",
            "EXTRACT_LINK_CDK": "fixture-cdk",
            "EXTRACT_LINK_TYPE": "pix",
        }
        with patch.object(
            extract_link_service,
            "_runtime_setting",
            side_effect=lambda name, default=None: values.get(name, default),
        ):
            config = extract_link_service._provider_configuration("legacy")

        self.assertEqual("https://legacy.example.test", config.api_base)
        self.assertEqual("fixture-cdk", config.cdk)
        self.assertEqual("pix", config.default_type)

    def test_unresolved_auto_payment_skips_new_charge_but_does_not_block_extract_only(self):
        from core import extract_link_service

        account = {
            "id": 77,
            "email": "fixture@example.test",
            "access_token": "stored-token",
            "plus_trial_eligible": True,
            "plan_type": "free",
        }
        runtime_config = SimpleNamespace(
            capabilities={"extract": True, "payment": True},
            default_type="momo",
        )
        with (
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", return_value=runtime_config),
            patch.object(extract_link_service, "_provider_link_type", return_value="momo"),
            patch.object(extract_link_service, "_provider_request_options", return_value={}),
            patch.object(extract_link_service.db, "get_account", return_value=account),
            patch.object(extract_link_service.db, "account_is_deactivated", return_value=False),
            patch("core.plus_promotion.is_free_trial_record", return_value=True),
            patch("core.storage.extract_link_jobs.has_unresolved_auto_payment", return_value=True) as unresolved,
            patch.object(extract_link_service.db, "claim_account_extract", return_value=True) as claim,
            patch.object(extract_link_service.db, "update_account_extract"),
            patch.object(extract_link_service.account_task_store, "submit_durable_operation", return_value={"accepted": True}),
        ):
            payment_result = extract_link_service.create_workbench_tasks(
                account_ids=[77], provider_id="lumen_flow", mode="auto_payment", type="momo",
            )
            extract_only_result = extract_link_service.create_workbench_tasks(
                account_ids=[77], provider_id="lumen_flow", mode="extract_only", type="momo",
            )

        self.assertEqual({"started": 0, "skipped": 1, "failed": 0}, payment_result)
        self.assertEqual({"started": 1, "skipped": 0, "failed": 0}, extract_only_result)
        unresolved.assert_called_once_with(77)
        self.assertEqual(1, claim.call_count)

    def test_startup_requeues_status_sync_for_known_interrupted_provider_jobs(self):
        from core import extract_link_service

        recoverable = [{
            "task_id": 17,
            "run_id": 28,
            "provider_id": "lumen_flow",
            "mode": "auto_payment",
        }]
        with (
            patch("core.storage.extract_link_jobs.list_recoverable_workbench_jobs", return_value=recoverable),
            patch("core.storage.operation.retry_runtime_task", return_value={"id": 29}) as retry,
            patch.object(extract_link_service.account_task_store, "notify_dispatch") as notify,
            patch.object(extract_link_service, "_bool_setting", return_value=True),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
        ):
            count = extract_link_service.resume_known_remote_jobs()

        self.assertEqual(1, count)
        retry.assert_called_once_with(
            17,
            trigger="extract_workbench_restart_sync",
            data={
                "provider_id": "lumen_flow",
                "mode": "auto_payment",
                "workbench_action": "sync_status",
                "provider_job_run_id": 28,
            },
        )
        notify.assert_called_once()

    def test_legacy_completed_task_uses_matching_account_result_projection(self):
        from core import extract_link_service

        row = {
            "task_id": 17,
            "run_id": 28,
            "account_id": 77,
            "email": "fixture@example.test",
            "task_data": {"link_type": "pix"},
            "task_status": "success",
            "run_status": "success",
            "run_count": 1,
            "result_summary": {"has_link": True, "remote_job_id": "old-job"},
        }
        account = {
            "extract_link_job_id": "old-job",
            "extract_link_status": "success",
            "extract_link_long_url": "https://example.test/old-result",
        }
        with (
            patch("core.storage.extract_link_jobs.list_workbench_rows", return_value=[row]),
            patch("core.storage.extract_link_jobs.get_provider_job_public", return_value=None),
            patch.object(extract_link_service.db, "get_accounts_for_jobs", return_value={17: account}),
            patch("core.storage.operation.get_task", return_value={
                "id": 17,
                "task_type": "extract_link",
                "account_id": 77,
                "data": {"link_type": "pix"},
                "last_run_id": 28,
            }),
            patch("core.storage.operation.get_run", return_value={
                "id": 28,
                "result_summary": {"has_link": True, "remote_job_id": "old-job"},
            }),
            patch.object(extract_link_service.db, "get_account", return_value=account),
        ):
            listed = extract_link_service.list_workbench_tasks()
            link = extract_link_service.extract_workbench_task_link(17, "extract")

        self.assertEqual("success", listed["items"][0]["extraction_status"])
        self.assertTrue(listed["items"][0]["has_extract_link"])
        self.assertEqual("https://example.test/old-result", link["url"])

    def test_workbench_modes_require_global_provider_and_adapter_capabilities(self):
        from core import extract_link_service

        values = {
            "EXTRACT_LINK_ENABLED": True,
            "EXTRACT_LINK_DEFAULT_PROVIDER": "lumen_flow",
            "EXTRACT_LINK_DEFAULT_MODE": "auto_payment",
            "EXTRACT_LINK_EXTRACT_ENABLED": True,
            "EXTRACT_LINK_MANUAL_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_AUTO_PAYMENT_ENABLED": False,
            "EXTRACT_LINK_LUMEN_FLOW_ENABLED": True,
            "EXTRACT_LINK_LUMEN_FLOW_EXTRACT_ENABLED": True,
            "EXTRACT_LINK_LUMEN_FLOW_MANUAL_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_LUMEN_FLOW_AUTO_PAYMENT_ENABLED": True,
            "EXTRACT_LINK_LUMEN_FLOW_CONCURRENCY": 2,
            "EXTRACT_LINK_LUMEN_FLOW_DEFAULT_TYPE": "momo",
            "EXTRACT_LINK_LUMEN_FLOW_API_BASE": "https://lumen.example.test",
            "EXTRACT_LINK_LUMEN_FLOW_CDK": "test-cdk",
        }
        with patch.object(
            extract_link_service,
            "_runtime_setting",
            side_effect=lambda name, default=None: values.get(name, default),
        ):
            config = extract_link_service.workbench_config()

        lumen = next(provider for provider in config["providers"] if provider["id"] == "lumen_flow")
        self.assertEqual(["extract_only", "manual_payment"], lumen["modes"])
        self.assertEqual("extract_only", config["default_mode"])
        self.assertNotIn("cdk", repr(config).lower())
        self.assertNotIn("test-cdk", repr(config))

    def test_extract_only_provider_run_uses_fresh_token_without_payment_call(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        provider = SimpleNamespace(
            create_job=Mock(return_value=ProviderJob(
                job_id="fixture-job",
                extraction_state="succeeded",
                links=("https://example.test/extract",),
            )),
            get_status=Mock(),
            start_payment=Mock(),
        )

        class Context:
            account_id = 77
            email = "fixture@example.test"
            task_id = 800
            run_id = 801
            config_snapshot = {}
            run = {
                "id": 801,
                "trigger": "test",
                "data": {
                    "provider_id": "lumen_flow",
                    "mode": "extract_only",
                    "link_type": "momo",
                },
            }

            def __init__(self):
                self.reports = []
                self.finished = None

            @contextmanager
            def lease(self, **_kwargs):
                yield None

            def checkpoint(self, *_args, **_kwargs):
                return None

            def report(self, **event):
                self.reports.append(event)

            def finish(self, **result):
                self.finished = result

        context = Context()
        account = {
            "id": 77,
            "email": "fixture@example.test",
            "access_token": "old-enqueue-token",
        }
        with (
            patch.object(extract_link_service.db, "get_account", return_value=account),
            patch.object(extract_link_service.db, "account_is_deactivated", return_value=False),
            patch("core.plus_promotion.is_free_trial_record", return_value=True),
            patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True),
            patch.object(extract_link_service, "_ensure_extract_token", return_value="fresh-live-token"),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", create=True, return_value=SimpleNamespace(
                config=SimpleNamespace(provider_id="lumen_flow", capabilities={"extract": True, "payment": False}),
                api_base="https://lumen.example.test",
                cdk="test-cdk",
                default_type="momo",
                timeout=30,
                poll_interval=1,
                event_timeout=10,
            )),
            patch.object(extract_link_service, "_provider", create=True, return_value=provider),
            patch("core.storage.extract_link_jobs.save_provider_job", return_value={}),
            patch("core.storage.extract_link_jobs.update_provider_job_state", return_value=True),
            patch.object(extract_link_service.db, "update_account_extract", return_value=True),
        ):
            extract_link_service._handle_provider_operation(context)

        request = provider.create_job.call_args.args[0]
        self.assertEqual("fresh-live-token", request.access_token)
        self.assertEqual("extract_only", request.mode)
        provider.start_payment.assert_not_called()
        provider.get_status.assert_not_called()
        self.assertEqual("success", context.finished["status"])

    def test_unknown_auto_payment_create_result_is_persisted_as_payment_unknown(self):
        from core import extract_link_service

        provider = SimpleNamespace(create_job=Mock(side_effect=TimeoutError("upstream timeout")))

        class Context:
            account_id = 77
            email = "fixture@example.test"
            task_id = 810
            run_id = 811
            config_snapshot = {}
            run = {
                "id": 811,
                "trigger": "test",
                "data": {
                    "provider_id": "lumen_flow",
                    "mode": "auto_payment",
                    "link_type": "momo",
                },
            }

            def __init__(self):
                self.finished = None

            @contextmanager
            def lease(self, **_kwargs):
                yield None

            def checkpoint(self, *_args, **_kwargs):
                return None

            def report(self, **_event):
                return None

            def finish(self, **result):
                self.finished = result

            def remote_request_started(self, *_args, **_kwargs):
                return None

            def remote_request_receipt(self, **_kwargs):
                return None

        context = Context()
        account = {"id": 77, "email": "fixture@example.test", "access_token": "stored-token"}
        with (
            patch.object(extract_link_service.db, "get_account", return_value=account),
            patch.object(extract_link_service.db, "account_is_deactivated", return_value=False),
            patch("core.plus_promotion.is_free_trial_record", return_value=True),
            patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True),
            patch.object(extract_link_service, "_ensure_extract_token", return_value="fresh-token"),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(
                config=SimpleNamespace(provider_id="lumen_flow", capabilities={"extract": True, "payment": True}),
                api_base="https://lumen.example.test",
                cdk="test-cdk",
                default_type="momo",
                timeout=30,
                poll_interval=1,
                event_timeout=10,
            )),
            patch.object(extract_link_service, "_provider", return_value=provider),
            patch.object(extract_link_service, "_provider_request_options", return_value={}),
            patch.object(extract_link_service, "_update_provider_job") as update_job,
            patch.object(extract_link_service.db, "update_account_extract") as update_account,
        ):
            extract_link_service._handle_provider_operation(context)

        self.assertEqual("request_unknown", context.finished["status"])
        self.assertEqual("unknown", update_job.call_args.args[3]["payment_state"])
        self.assertEqual("request_unknown", update_account.call_args.args[1]["status"])

    def test_plus_confirmation_filter_uses_account_plan_check_projection(self):
        from core import extract_link_service

        row = {
            "task_id": 11,
            "account_id": 77,
            "email": "fixture@example.test",
            "task_data": {"provider_id": "lumen_flow", "mode": "manual_payment"},
            "task_status": "success",
            "run_status": "success",
            "run_count": 1,
            "public_state": {
                "extraction_state": "succeeded",
                "payment_state": "succeeded",
                "plus_status": "pending",
                "links": ["https://example.test/extract"],
                "payment_links": ["https://example.test/pay"],
            },
        }
        with (
            patch("core.storage.extract_link_jobs.list_workbench_rows", return_value=[row]),
            patch.object(extract_link_service.db, "get_accounts_for_jobs", return_value={
                11: {
                    "plan_check_status": "success",
                    "current_plan_type": "plus",
                    "access_token": "must-not-project",
                },
            }),
        ):
            result = extract_link_service.list_workbench_tasks(status="plus_confirmed")

        self.assertEqual(1, result["total"])
        self.assertEqual("confirmed", result["items"][0]["plus_status"])
        self.assertNotIn("must-not-project", repr(result))

    def test_auto_payment_retry_with_existing_order_only_queues_status_sync(self):
        from core import extract_link_service

        task = {
            "id": 11,
            "task_type": "extract_link",
            "source_system": "native_operations",
            "status": "attention_required",
            "account_id": 77,
            "data": {"provider_id": "lumen_flow", "mode": "auto_payment", "link_type": "momo"},
            "runs": [{"id": 22, "run_no": 1}],
            "last_run_id": 22,
        }
        with (
            patch("core.storage.operation.get_task", return_value=task),
            patch("core.storage.extract_link_jobs.get_provider_job_public", return_value={
                "job_id": "existing-order",
                "public_state": {"extraction_state": "succeeded", "payment_state": "unknown"},
            }),
            patch("core.storage.operation.retry_runtime_task", return_value={"id": 33}) as retry,
            patch.object(extract_link_service.account_task_store, "notify_dispatch") as notify,
            patch.object(extract_link_service.db, "claim_account_extract") as claim,
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_bool_setting", return_value=True),
        ):
            result = extract_link_service.perform_extract_workbench_action(11, "retry")

        self.assertTrue(result["accepted"])
        self.assertEqual(33, result["run_id"])
        payload = retry.call_args.kwargs["data"]
        self.assertEqual("sync_status", payload["workbench_action"])
        self.assertEqual(22, payload["provider_job_run_id"])
        self.assertEqual("auto_payment", payload["mode"])
        claim.assert_not_called()
        notify.assert_called_once()

    def test_auto_payment_retry_without_order_retries_extraction_only(self):
        from core import extract_link_service

        task = {
            "id": 12,
            "task_type": "extract_link",
            "source_system": "native_operations",
            "status": "attention_required",
            "account_id": 78,
            "data": {"provider_id": "lumen_flow", "mode": "auto_payment", "link_type": "momo"},
            "runs": [{"id": 23, "run_no": 1}],
            "last_run_id": 23,
        }
        with (
            patch("core.storage.operation.get_task", return_value=task),
            patch("core.storage.extract_link_jobs.get_provider_job_public", return_value=None),
            patch("core.storage.operation.retry_runtime_task", return_value={"id": 34}) as retry,
            patch.object(extract_link_service.account_task_store, "notify_dispatch"),
            patch.object(extract_link_service.db, "claim_account_extract", return_value=True) as claim,
            patch.object(extract_link_service.db, "update_account_extract"),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_bool_setting", return_value=True),
        ):
            result = extract_link_service.perform_extract_workbench_action(12, "retry")

        self.assertTrue(result["accepted"])
        self.assertEqual(34, result["run_id"])
        payload = retry.call_args.kwargs["data"]
        self.assertEqual("create", payload["workbench_action"])
        self.assertEqual("extract_only", payload["mode"])
        self.assertIsNone(payload["provider_job_run_id"])
        claim.assert_called_once_with(78, trigger="extract_workbench_retry", link_type="momo")

    def test_provider_concurrency_limit_uses_each_platform_config_key(self):
        from core import extract_link_service

        values = {
            "EXTRACT_LINK_LEGACY_CONCURRENCY": 3,
            "EXTRACT_LINK_LUMEN_FLOW_CONCURRENCY": 2,
            "EXTRACT_LINK_HUANGUANG_CONCURRENCY": 4,
        }
        with patch.object(
            extract_link_service,
            "_runtime_setting",
            side_effect=lambda name, default=None: values.get(name, default),
        ):
            self.assertEqual(3, extract_link_service._provider_dispatch_capacity_limit("legacy"))
            self.assertEqual(2, extract_link_service._provider_dispatch_capacity_limit("lumen_flow"))
            self.assertEqual(4, extract_link_service._provider_dispatch_capacity_limit("huanguang"))

    def test_lumen_payment_sync_waits_until_provider_due_time(self):
        from datetime import datetime, timezone

        from core import extract_link_service

        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        future = {"next_payment_state_sync_at": "2026-10-22T12:05:00Z"}

        self.assertFalse(extract_link_service._provider_payment_sync_due(future, now=now))
        self.assertTrue(extract_link_service._provider_payment_sync_due(
            {"next_payment_state_sync_at": "2026-10-22T11:55:00Z"}, now=now,
        ))
        self.assertFalse(extract_link_service._provider_payment_sync_due(
            {"next_payment_state_sync_at": "not-a-timestamp"}, now=now,
        ))


if __name__ == "__main__":
    unittest.main()
