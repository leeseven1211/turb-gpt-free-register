from __future__ import annotations

import unittest
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ExtractLinkProviderFlowTests(unittest.TestCase):
    def test_payment_artifact_survives_merge_and_summary_hides_payment_contents(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        artifact = {"payment_page_url": "https://checkout.example.test/page", "qr_data": "upi://pay?pa=synthetic&tn=Token%2BExact", "amount": 0}
        first = ProviderJob(extraction_state="succeeded", payment_artifact=artifact)
        partial = ProviderJob(payment_artifact={"currency": "BRL", "qr_data": ""})
        job = extract_link_service._merge_provider_jobs(first, partial)
        state = extract_link_service._safe_provider_job_state(job, mode="extract_only")
        self.assertEqual({**artifact, "currency": "BRL"}, state["payment_artifact"])
        item = extract_link_service._workbench_task_item({"task_id": 17, "public_state": state})
        self.assertTrue(item["has_extract_link"])
        self.assertTrue(item["has_payment_entry"])
        self.assertTrue(item["has_qr"])
        self.assertNotIn(artifact["qr_data"], repr(item))
        self.assertNotIn(artifact["payment_page_url"], repr(item))

    def test_hosted_url_only_historical_job_has_copy_link_and_read_only_payment_entry(self):
        from core import extract_link_service

        job = {"public_state": {"payment_links": ["https://checkout.example.test/page"], "extraction_state": "succeeded"}}
        task = {"task_type": "extract_link", "last_run_id": 18, "data": {"provider_id": "lumen_flow"}}
        with (
            patch("core.storage.operation.get_task", return_value=task),
            patch("core.storage.extract_link_jobs.get_provider_job_public", return_value=job),
            patch.object(extract_link_service, "_provider") as create_provider,
            patch.object(extract_link_service.db, "get_account") as get_account,
        ):
            copied = extract_link_service.extract_workbench_task_link(17, "extract")
            entry = extract_link_service.extract_workbench_task_payment_entry(17)
        self.assertEqual({"url": "https://checkout.example.test/page"}, copied)
        self.assertEqual({"payment_page_url": "https://checkout.example.test/page"}, entry)
        create_provider.assert_not_called()
        get_account.assert_not_called()
        item = extract_link_service._workbench_task_item({"task_id": 17, "public_state": job["public_state"]})
        self.assertTrue(item["has_extract_link"])
        self.assertFalse(item["has_qr"])

    def test_payment_entry_keeps_distinct_page_and_payment_urls_and_checks_task_kind(self):
        from core import extract_link_service

        artifact = {"payment_page_url": "https://checkout.example.test/page", "payment_url": "https://payments.example.test/entry", "qr_data": "exact:token/value"}
        job = {"public_state": {"payment_artifact": artifact, "links": [], "payment_links": []}}
        with (
            patch("core.storage.operation.get_task", return_value={"task_type": "extract_link", "last_run_id": 18}),
            patch("core.storage.extract_link_jobs.get_provider_job_public", return_value=job),
        ):
            self.assertEqual(artifact, extract_link_service.extract_workbench_task_payment_entry(17))
            self.assertEqual({"url": artifact["payment_page_url"]}, extract_link_service.extract_workbench_task_link(17, "extract"))
            self.assertEqual({"url": artifact["payment_url"]}, extract_link_service.extract_workbench_task_link(17, "payment"))
        with patch("core.storage.operation.get_task", return_value={"task_type": "check_plan", "last_run_id": 18}):
            self.assertIsNone(extract_link_service.extract_workbench_task_payment_entry(17))

    def test_historical_payment_links_are_not_hidden_by_new_metadata_only_artifact(self):
        from core import extract_link_service

        state = {
            "payment_links": ["https://checkout.example.test/historical"],
            "payment_artifact": {"payment_status": "requires_action", "amount": 0},
        }
        with (
            patch("core.storage.operation.get_task", return_value={"task_type": "extract_link", "last_run_id": 18}),
            patch("core.storage.extract_link_jobs.get_provider_job_public", return_value={"public_state": state}),
        ):
            self.assertEqual({
                **state["payment_artifact"], "payment_page_url": state["payment_links"][0],
            }, extract_link_service.extract_workbench_task_payment_entry(17))

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
            patch("core.storage.extract_link_jobs.list_workbench_page", return_value={
                "items": rows[1:4], "total": 3, "page": 1, "page_size": 20,
                "counts": {"all": 6, "processing": 5, "running": 3, "extraction_succeeded": 0,
                           "payment_succeeded": 0, "plus_confirmed": 0, "needs_attention": 6},
            }) as list_rows,
            patch.object(extract_link_service.db, "get_accounts_for_jobs", return_value={}),
        ):
            result = extract_link_service.list_workbench_tasks(
                provider_id="lumen_flow", mode="extract_only", query="fixture", status="running",
            )

        list_rows.assert_called_once_with(provider_id="lumen_flow", mode="extract_only", query="fixture",
                                          status="running", page=1, page_size=20)
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
            patch("core.plus_promotion.is_extract_link_eligible", return_value=True),
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
            patch("core.storage.extract_link_jobs.list_workbench_page", return_value={
                "items": [row], "total": 1, "page": 1, "page_size": 20,
                "counts": {"all": 1, "processing": 0, "running": 0, "extraction_succeeded": 1,
                           "payment_succeeded": 0, "plus_confirmed": 0, "needs_attention": 1},
            }),
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
        self.assertTrue(lumen["link_types"])
        self.assertTrue(all("cdk" not in provider["unavailable_reason"].lower() for provider in config["unavailable_providers"]))
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
            patch("core.plus_promotion.is_extract_link_eligible", return_value=True),
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
            patch("core.plus_promotion.is_extract_link_eligible", return_value=True),
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
            patch("core.storage.extract_link_jobs.list_workbench_page", return_value={
                "items": [row], "total": 1, "page": 1, "page_size": 20,
                "counts": {"all": 1, "processing": 0, "running": 0, "extraction_succeeded": 1,
                           "payment_succeeded": 1, "plus_confirmed": 1, "needs_attention": 0},
            }),
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


class ExtractLinkPreflightConfigurationTests(unittest.TestCase):
    @contextmanager
    def _scenario(self, *, provider_id, preflight_enabled, refresh_at_enabled, inline_results):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        context = SimpleNamespace(
            account_id=77, email="fixture@example.test", task_id=810, run_id=811,
            config_snapshot={}, checkpoint=Mock(), report=Mock(), finish=Mock(),
            run={"data": {"provider_id": provider_id, "mode": "extract_only", "link_type": "pix"}},
            remote_request_started=Mock(), remote_request_receipt=Mock(),
        )
        context.lease = contextmanager(lambda **_kwargs: iter([None]))
        provider = SimpleNamespace(
            create_job=Mock(return_value=ProviderJob(
                job_id="fixture-job", extraction_state="succeeded", links=("https://example.test/fixture",),
            )),
            get_status=Mock(), start_payment=Mock(),
        )
        account = {"id": 77, "email": context.email, "access_token": "initial-account-token"}
        settings = {
            "EXTRACT_LINK_PREFLIGHT_ENABLED": preflight_enabled,
            "EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED": refresh_at_enabled,
        }
        with ExitStack() as stack:
            stack.enter_context(patch.object(extract_link_service, "_runtime_setting", side_effect=lambda name, default=None: settings.get(name, default)))
            get_account = stack.enter_context(patch.object(extract_link_service.db, "get_account", side_effect=[
                account, {**account, "access_token": "latest-database-token"},
            ]))
            stack.enter_context(patch.object(extract_link_service.db, "account_is_deactivated", return_value=False))
            stack.enter_context(patch("core.plus_promotion.is_extract_link_eligible", return_value=True))
            stack.enter_context(patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True))
            inline = stack.enter_context(patch("core.live_check_service.run_account_live_check_inline", side_effect=inline_results))
            stack.enter_context(patch.object(extract_link_service, "_provider_enabled", return_value=True))
            stack.enter_context(patch.object(extract_link_service, "_provider_mode_enabled", return_value=True))
            stack.enter_context(patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(
                default_type="pix", event_timeout=10, poll_interval=1, timeout=30,
            )))
            stack.enter_context(patch.object(extract_link_service, "_provider_link_type", return_value="pix"))
            stack.enter_context(patch.object(extract_link_service, "_provider_request_options", return_value={}))
            stack.enter_context(patch.object(extract_link_service, "_provider", return_value=provider))
            stack.enter_context(patch.object(extract_link_service, "_acquire_huanguang_proxies", return_value=([], [])))
            stack.enter_context(patch.object(extract_link_service, "_release_huanguang_proxies"))
            save_job = stack.enter_context(patch.object(extract_link_service, "_update_provider_job"))
            stack.enter_context(patch.object(extract_link_service.db, "update_account_extract"))
            yield SimpleNamespace(context=context, provider=provider, inline=inline, get_account=get_account, save_job=save_job)

    @staticmethod
    def _states(scenario, stage):
        return [call.kwargs["state"] for call in scenario.context.report.call_args_list
                if call.kwargs.get("stage") == stage and call.kwargs.get("state")]

    def test_huanguang_configured_proxy_pools_reach_provider_without_auto_allocation(self):
        from core import extract_link_service

        entries = ["http://entry-one.example.test:8080", "http://entry-two.example.test:8080"]
        exits = ["socks5h://fixture-user:fixture-password@exit-one.example.test:1080"]
        settings = {
            "EXTRACT_LINK_PREFLIGHT_ENABLED": False,
            "EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES": repr(entries),
            "EXTRACT_LINK_HUANGUANG_EXIT_PROXIES": "\n".join(exits),
        }
        with self._scenario(provider_id="huanguang", preflight_enabled=False, refresh_at_enabled=False, inline_results=[]) as scenario:
            with patch.object(extract_link_service, "_runtime_setting", side_effect=lambda name, default=None: settings.get(name, default)), patch.object(extract_link_service, "_acquire_huanguang_proxies") as acquire:
                extract_link_service._handle_provider_operation(scenario.context)

        self.assertEqual("success", scenario.context.finish.call_args.kwargs["status"])
        acquire.assert_not_called()
        request = scenario.provider.create_job.call_args.args[0]
        self.assertEqual(tuple(entries), request.entry_proxies)
        self.assertEqual(tuple(exits), request.exit_proxies)
        self.assertNotIn("fixture-password", repr(scenario.context.report.call_args_list))
        self.assertNotIn("fixture-password", repr(scenario.save_job.call_args_list))
        self.assertNotIn("fixture-password", repr(scenario.context.finish.call_args_list))

    def test_huanguang_only_allocates_missing_proxy_side(self):
        from core import extract_link_service

        for configured_side, missing_side in (("entry", "exit"), ("exit", "entry")):
            with self.subTest(configured_side=configured_side), self._scenario(
                provider_id="huanguang", preflight_enabled=False, refresh_at_enabled=False, inline_results=[],
            ) as scenario:
                configured = [f"http://{configured_side}-manual.example.test:8080"]
                automatic = "http://automatic.example.test:8080"
                settings = {
                    "EXTRACT_LINK_PREFLIGHT_ENABLED": False,
                    f"EXTRACT_LINK_HUANGUANG_{configured_side.upper()}_PROXIES": configured,
                }
                with patch.object(extract_link_service, "_runtime_setting", side_effect=lambda name, default=None: settings.get(name, default)), patch.object(
                    extract_link_service, "_acquire_huanguang_proxies", return_value=([SimpleNamespace(proxy_url=automatic)], [91]),
                ) as acquire:
                    extract_link_service._handle_provider_operation(scenario.context)

                acquire.assert_called_once_with(scenario.context, purposes=(missing_side,))
                request = scenario.provider.create_job.call_args.args[0]
                self.assertEqual(tuple(configured), getattr(request, f"{configured_side}_proxies"))
                self.assertEqual((automatic,), getattr(request, f"{missing_side}_proxies"))
                self.assertEqual("success", scenario.context.finish.call_args.kwargs["status"])

    def test_huanguang_empty_manual_pools_keep_both_automatic_india_routes(self):
        from core import extract_link_service

        routes = ("http://entry-auto.example.test:8080", "http://exit-auto.example.test:8080")
        with self._scenario(provider_id="huanguang", preflight_enabled=False, refresh_at_enabled=False, inline_results=[]) as scenario:
            with patch.object(extract_link_service, "_acquire_huanguang_proxies", return_value=([SimpleNamespace(proxy_url=value) for value in routes], [91, 92])) as acquire:
                extract_link_service._handle_provider_operation(scenario.context)

        acquire.assert_called_once_with(scenario.context, purposes=("entry", "exit"))
        request = scenario.provider.create_job.call_args.args[0]
        self.assertEqual((routes[0],), request.entry_proxies)
        self.assertEqual((routes[1],), request.exit_proxies)

    def test_huanguang_invalid_manual_pool_fails_before_remote_submission(self):
        from core import extract_link_service

        settings = {
            "EXTRACT_LINK_PREFLIGHT_ENABLED": False,
            "EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES": ["http://fixture-user:fixture-password@invalid.example.test"],
        }
        with self._scenario(provider_id="huanguang", preflight_enabled=False, refresh_at_enabled=False, inline_results=[]) as scenario:
            with patch.object(extract_link_service, "_runtime_setting", side_effect=lambda name, default=None: settings.get(name, default)), patch.object(extract_link_service, "_acquire_huanguang_proxies") as acquire:
                extract_link_service._handle_provider_operation(scenario.context)

        acquire.assert_not_called()
        scenario.provider.create_job.assert_not_called()
        self.assertEqual("failed", scenario.context.finish.call_args.kwargs["status"])
        self.assertNotIn("fixture-password", repr(scenario.context.finish.call_args_list))

    def test_huanguang_proxy_preparation_returns_leases_before_caller_reports_progress(self):
        from core import extract_link_service

        context = SimpleNamespace(report=Mock(side_effect=RuntimeError("合成事件写入失败")))
        leases = [SimpleNamespace(proxy_url="http://entry.example.test:8080"), SimpleNamespace(proxy_url="http://exit.example.test:8080")]
        with patch.object(extract_link_service, "_runtime_setting", return_value=[]), patch.object(
            extract_link_service, "_acquire_huanguang_proxies", return_value=(leases, [91, 92]),
        ):
            routes, returned_leases, resource_ids = extract_link_service._prepare_huanguang_proxies(context)

        self.assertIs(leases, returned_leases)
        self.assertEqual([91, 92], resource_ids)
        self.assertEqual((leases[0].proxy_url,), routes["entry"])
        self.assertEqual((leases[1].proxy_url,), routes["exit"])
        context.report.assert_not_called()

    def test_all_providers_skip_preflight_and_keep_skipped_after_job_creation(self):
        from core import extract_link_service

        for provider_id in ("legacy", "lumen_flow", "huanguang"):
            for refresh_at_enabled in (True, False):
                with self.subTest(provider_id=provider_id, refresh_at_enabled=refresh_at_enabled), self._scenario(
                    provider_id=provider_id, preflight_enabled=False,
                    refresh_at_enabled=refresh_at_enabled, inline_results=[],
                ) as scenario:
                    extract_link_service._handle_provider_operation(scenario.context)
                    scenario.inline.assert_not_called()
                    self.assertEqual(2, scenario.get_account.call_count)
                    self.assertEqual("latest-database-token", scenario.provider.create_job.call_args.args[0].access_token)
                    self.assertEqual(["skipped"], self._states(scenario, "preflight"))
                    self.assertEqual(["skipped"], self._states(scenario, "refresh_token"))
                    self.assertEqual("skipped", scenario.save_job.call_args.args[3]["preflight_status"])
                    finished = scenario.context.finish.call_args.kwargs
                    self.assertEqual("success", finished["status"])
                    self.assertEqual("skipped", finished["result_summary"]["preflight_status"])
                    scenario.provider.start_payment.assert_not_called()

    def test_all_providers_continue_with_live_token_when_refresh_is_disabled(self):
        from core import extract_link_service

        for provider_id in ("legacy", "lumen_flow", "huanguang"):
            with self.subTest(provider_id=provider_id), self._scenario(
                provider_id=provider_id, preflight_enabled=True, refresh_at_enabled=False,
                inline_results=[{"accepted": True, "result": {"ok": True, "status": "live"}}],
            ) as scenario:
                extract_link_service._handle_provider_operation(scenario.context)
                scenario.inline.assert_called_once()
                self.assertFalse(scenario.inline.call_args.kwargs["force_refresh"])
                self.assertEqual("latest-database-token", scenario.provider.create_job.call_args.args[0].access_token)
                self.assertEqual("success", self._states(scenario, "preflight")[-1])
                self.assertEqual(["skipped"], self._states(scenario, "refresh_token"))
                self.assertEqual("passed", scenario.save_job.call_args.args[3]["preflight_status"])
                self.assertEqual("success", scenario.context.finish.call_args.kwargs["status"])

    def test_all_providers_stop_invalid_token_when_refresh_is_disabled(self):
        from core import extract_link_service

        for provider_id in ("legacy", "lumen_flow", "huanguang"):
            with self.subTest(provider_id=provider_id), self._scenario(
                provider_id=provider_id, preflight_enabled=True, refresh_at_enabled=False,
                inline_results=[{"accepted": True, "result": {"ok": False, "status": "failed", "token_expired": True}}],
            ) as scenario:
                extract_link_service._handle_provider_operation(scenario.context)
                scenario.inline.assert_called_once()
                self.assertFalse(scenario.inline.call_args.kwargs["force_refresh"])
                scenario.provider.create_job.assert_not_called()
                scenario.context.remote_request_started.assert_not_called()
                self.assertEqual("failed", self._states(scenario, "preflight")[-1])
                self.assertEqual(["skipped"], self._states(scenario, "refresh_token"))
                self.assertEqual("failed", scenario.save_job.call_args.args[3]["preflight_status"])
                self.assertEqual("failed", scenario.context.finish.call_args.kwargs["status"])


class ExtractLinkTerminalFailureFlowTests(unittest.TestCase):
    @contextmanager
    def _scenario(self, *, failed_job=None, poll_error=None):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        events = []

        def report(**event):
            event = {**event, "id": len(events) + 1, "event_type": f"stage.{event.get('state', 'running')}"}
            events.append(event)
            return event

        context = SimpleNamespace(
            account_id=77, email="fixture@example.test", task_id=810, run_id=811,
            config_snapshot={}, finished=False, checkpoint=Mock(),
            run={"data": {"provider_id": "lumen_flow", "mode": "extract_only", "link_type": "momo"}},
            report=Mock(side_effect=report), finish=Mock(),
            remote_request_started=Mock(), remote_request_receipt=Mock(),
        )
        context.lease = contextmanager(lambda **_kwargs: iter([None]))
        provider = SimpleNamespace(
            create_job=Mock(return_value=ProviderJob(job_id="fixture-job", extraction_state="running")),
            get_status=Mock(return_value=failed_job, side_effect=poll_error),
            start_payment=Mock(),
        )
        account = {"id": 77, "email": context.email, "access_token": "fixture-token"}
        clock = [0.0]
        with (
            patch.object(extract_link_service.db, "get_account", return_value=account),
            patch.object(extract_link_service.db, "account_is_deactivated", return_value=False),
            patch("core.plus_promotion.is_extract_link_eligible", return_value=True),
            patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True),
            patch.object(extract_link_service, "_ensure_extract_token", return_value="fresh-token"),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(
                default_type="momo", event_timeout=10, poll_interval=1, timeout=30,
            )),
            patch.object(extract_link_service, "_provider", return_value=provider),
            patch.object(extract_link_service, "_update_provider_job") as save_job,
            patch.object(extract_link_service.db, "update_account_extract") as save_account,
            patch.object(extract_link_service.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
            patch.object(extract_link_service.time, "monotonic", side_effect=lambda: clock[0]),
        ):
            yield SimpleNamespace(
                context=context, provider=provider, events=events,
                save_job=save_job, save_account=save_account,
            )

    def test_huanguang_auto_payment_without_scan_result_remains_unknown_after_extraction(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        incomplete = ProviderJob(
            job_id="fixture-job", extraction_state="succeeded", payment_state="not_started",
            links=("https://checkout.example.test/session",),
            summary={"remote_polling": False, "automatic_payment_terminal": True},
        )
        with self._scenario(failed_job=incomplete) as scenario:
            scenario.context.run["data"].update({"provider_id": "huanguang", "mode": "auto_payment", "link_type": "upi"})
            with patch.object(extract_link_service, "_prepare_huanguang_proxies", return_value=({"entry": (), "exit": ()}, [], [])):
                extract_link_service._handle_provider_operation(scenario.context)

        finished = scenario.context.finish.call_args.kwargs
        self.assertEqual("request_unknown", finished["status"])
        self.assertEqual("succeeded", finished["result_summary"]["extraction_status"])
        self.assertEqual("unknown", finished["result_summary"]["payment_status"])
        self.assertIn("待确认", finished["message"])
        scenario.provider.start_payment.assert_not_called()

    def test_polled_failure_keeps_reason_and_explicit_extraction_stage_without_payment(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob
        from core.task_progress import build_progress_snapshot

        failed_job = ProviderJob(
            job_id="fixture-job", extraction_state="failed",
            summary={"remote_status": "FAILED", "remote_terminal_failure": True, "failure_message": "当前账号不符合优惠条件"},
        )
        with self._scenario(failed_job=failed_job) as scenario:
            extract_link_service._handle_provider_operation(scenario.context)

        finished = scenario.context.finish.call_args.kwargs
        self.assertEqual("failed", finished["status"])
        self.assertIn("当前账号不符合优惠条件", finished["message"])
        self.assertEqual("extract_provider_failed", finished["result_summary"]["cause_code"])
        self.assertTrue(finished["result_summary"]["remote_terminal_failure"])
        self.assertIn("当前账号不符合优惠条件", scenario.save_job.call_args.args[3]["message"])
        self.assertIn("当前账号不符合优惠条件", scenario.save_account.call_args.args[1]["message"])
        receipt = scenario.context.remote_request_receipt.call_args.kwargs
        self.assertEqual("confirmed", receipt["outcome"])
        self.assertEqual("fixture-job", receipt["detail"]["remote_job_id"])
        self.assertEqual("lumen_flow", receipt["detail"]["provider_id"])
        scenario.provider.start_payment.assert_not_called()
        snapshot = build_progress_snapshot(
            810, 811, "extract_link",
            {"status": "failed", "error_message": finished["error"], "result_summary": finished["result_summary"]},
            scenario.events,
        )
        self.assertEqual("extraction", snapshot["failure"]["stage"])
        self.assertEqual("explicit", snapshot["failure"]["evidence"])
        self.assertEqual("LINK-FAILED", snapshot["failure"]["error_info"]["display_code"])

    def test_sync_error_keeps_previous_business_state_and_reports_query_failure(self):
        from core import extract_link_service

        prior = {"job_id": "fixture-job", "private_data": {}, "public_state": {
            "extraction_state": "failed", "payment_state": "not_started", "preflight_status": "passed",
            "plus_status": "not_applicable", "summary": {"failure_code": "SETUP_INTENT_FAILED", "remote_terminal_failure": True},
        }}
        with self._scenario(poll_error=RuntimeError("Provider 请求失败（HTTP 404）")) as scenario, patch(
            "core.storage.extract_link_jobs.get_provider_job_private", return_value=prior,
        ):
            scenario.context.run["data"].update({"workbench_action": "sync_status", "provider_job_run_id": 28})
            extract_link_service._handle_provider_operation(scenario.context)
        result = scenario.context.finish.call_args.kwargs
        self.assertEqual("failed", result["result_summary"]["extraction_status"])
        self.assertEqual("passed", result["result_summary"]["preflight_status"])
        self.assertIn("同步状态失败", result["message"])
        self.assertEqual("SETUP_INTENT_FAILED", scenario.save_job.call_args.args[3]["summary"]["failure_code"])
        scenario.provider.create_job.assert_not_called()

    def test_extraction_success_keeps_compatibility_summary_and_native_payment_result(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        artifact = {
            "payment_page_url": "https://checkout.example.test/session",
            "payment_url": "https://payments.example.test/instructions",
            "qr_data": "000201-PAYMENT-EXACT+VALUE",
            "qr_image_url_png": "https://payments.example.test/qr.png",
            "qr_image_url_svg": "https://payments.example.test/qr.svg",
            "expires_at": "2026-10-24T00:00:00+00:00",
        }
        with self._scenario(failed_job=ProviderJob(
            job_id="fixture-job", extraction_state="succeeded", payment_artifact=artifact,
        )) as scenario:
            extract_link_service._handle_provider_operation(scenario.context)

        summary = scenario.context.finish.call_args.kwargs["result_summary"]
        self.assertTrue(summary["ok"])
        self.assertEqual("success", summary["status"])
        self.assertTrue(summary["has_link"])
        self.assertTrue(summary["has_qr"])
        self.assertEqual("提链成功", summary["message"])
        self.assertNotIn(artifact["qr_data"], repr(summary))
        self.assertNotIn(artifact["payment_page_url"], repr(summary))
        account_result = scenario.save_account.call_args.args[1]
        self.assertTrue(account_result["ok"])
        self.assertEqual({**artifact, "expires_at": "2026-10-24T00:00:00Z"}, scenario.save_job.call_args.args[3]["payment_artifact"])
        self.assertNotIn(artifact["qr_data"], repr(account_result))
        self.assertNotIn(artifact["qr_image_url_png"], repr(account_result))
        self.assertNotIn(artifact["payment_page_url"], repr(account_result))

    def test_pending_automatic_payment_does_not_undo_successful_extraction(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        with self._scenario(failed_job=ProviderJob(job_id="fixture-job", extraction_state="succeeded", payment_state="pending")) as scenario:
            scenario.context.run["data"]["mode"] = "auto_payment"
            scenario.provider.create_job.return_value = ProviderJob(
                job_id="fixture-job", extraction_state="succeeded", payment_state="pending",
                links=("https://checkout.example.test/session",),
            )
            extract_link_service._handle_provider_operation(scenario.context)

        finish = scenario.context.finish.call_args.kwargs
        self.assertEqual("partial_success", finish["status"])
        self.assertEqual("succeeded", finish["result_summary"]["extraction_status"])
        self.assertEqual("pending", finish["result_summary"]["payment_status"])
        self.assertTrue(finish["result_summary"]["ok"])
        self.assertTrue(scenario.save_account.call_args.args[1]["ok"])
        scenario.provider.start_payment.assert_not_called()

    def test_terminal_failure_without_reason_does_not_invent_platform_detail(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        with self._scenario(failed_job=ProviderJob(
            job_id="fixture-job", extraction_state="failed",
            summary={"remote_status": "FAILED", "remote_terminal_failure": True},
        )) as scenario:
            extract_link_service._handle_provider_operation(scenario.context)

        finished = scenario.context.finish.call_args.kwargs
        self.assertEqual("failed", finished["status"])
        self.assertIn("平台未提供失败细项", finished["message"])
        self.assertEqual("平台未提供失败细项", finished["result_summary"]["failure_message"])

    def test_poll_transport_error_keeps_last_valid_state_instead_of_platform_failure(self):
        from core import extract_link_service

        with self._scenario(poll_error=TimeoutError("平台查询超时")) as scenario:
            extract_link_service._handle_provider_operation(scenario.context)

        finished = scenario.context.finish.call_args.kwargs
        self.assertEqual("request_unknown", finished["status"])
        self.assertEqual("running", finished["result_summary"]["extraction_status"])
        self.assertNotIn("remote_terminal_failure", finished["result_summary"])
        self.assertNotIn("cause_code", finished["result_summary"])
        self.assertFalse(any(event.get("stage") == "extraction" and event.get("state") == "failed" for event in scenario.events))
        scenario.provider.start_payment.assert_not_called()

    def test_create_rejection_keeps_platform_reason_in_workbench_message(self):
        from core import extract_link_service
        from core.extract_link_providers.contracts import ProviderJob

        with self._scenario() as scenario:
            scenario.provider.create_job.return_value = ProviderJob(
                extraction_state="failed",
                summary={"outcome": "REJECTED", "failure_message": "提链次数不足"},
            )
            extract_link_service._handle_provider_operation(scenario.context)

        finished = scenario.context.finish.call_args.kwargs
        self.assertEqual("failed", finished["status"])
        self.assertEqual("rejected", scenario.context.remote_request_receipt.call_args.kwargs["outcome"])
        self.assertIn("提链次数不足", scenario.save_job.call_args.args[3]["message"])
        self.assertIn("提链次数不足", scenario.save_account.call_args.args[1]["message"])
        self.assertEqual("extract_provider_failed", finished["result_summary"]["cause_code"])
        scenario.provider.get_status.assert_not_called()
        scenario.provider.start_payment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
