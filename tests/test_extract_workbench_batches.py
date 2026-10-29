from __future__ import annotations

import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from core import account_task_store, extract_link_service, record_store
from core.storage import extract_link_batches, extract_link_jobs, operation
from tests.support_pg import PostgresTestCase


class ExtractWorkbenchBatchValidationTests(unittest.TestCase):
    def test_cancel_batch_rejects_invalid_id_before_reading_storage(self):
        for batch_id in (0, -1, True, "1"):
            with self.subTest(batch_id=batch_id), patch.object(extract_link_batches, "batch_rows") as batches:
                with self.assertRaises(ValueError):
                    extract_link_service.cancel_workbench_batch(batch_id)
                batches.assert_not_called()

    def test_cancel_batch_missing_or_foreign_batch_does_not_touch_tasks(self):
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": []}),
            patch.object(operation, "list_tasks") as tasks,
            patch.object(operation, "request_run_cancel") as cancel,
        ):
            self.assertIsNone(extract_link_service.cancel_workbench_batch(91))
        tasks.assert_not_called()
        cancel.assert_not_called()

    def test_cancel_batch_continues_after_one_cancel_error_and_counts_skips(self):
        rows = [{"last_run_id": value, "status": "queued"} for value in range(1, 5)]
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": [{"id": 91}]}),
            patch.object(operation, "list_tasks", return_value={"items": rows, "total": len(rows)}),
            patch.object(operation, "request_run_cancel", side_effect=[
                RuntimeError("private-detail"), LookupError("missing"),
                {"status": "running", "cancel_skipped": True}, {"status": "cancelled"},
            ]),
            patch.object(extract_link_service.account_task_store, "notify_dispatch"),
        ):
            result = extract_link_service.cancel_workbench_batch(91)
        self.assertEqual({"batch_id": 91, "cancelled": 1, "skipped": 2, "failed": 1}, result)

    def test_cancel_batch_waits_for_submission_to_finish(self):
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": [{
                "id": 91, "created_at": datetime.now(timezone.utc),
                "data": {"submission_complete": False},
            }]}),
            patch.object(operation, "list_tasks") as tasks,
            self.assertRaisesRegex(ValueError, "正在入队"),
        ):
            extract_link_service.cancel_workbench_batch(91)
        tasks.assert_not_called()

    def test_cancel_batch_allows_unfinished_submission_from_previous_process(self):
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": [{
                "id": 91, "created_at": datetime.now(timezone.utc) - timedelta(days=1),
                "data": {"submission_complete": False},
            }]}),
            patch.object(operation, "list_tasks", return_value={"items": [], "total": 0}),
        ):
            result = extract_link_service.cancel_workbench_batch(91)
        self.assertEqual(0, result["failed"])

    def test_cancel_batch_allows_submission_that_finished_with_an_error(self):
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": [{
                "id": 91, "data": {"submission_complete": False,
                    "submission_skipped": 0, "submission_failed": 1},
            }]}),
            patch.object(operation, "list_tasks", return_value={"items": [], "total": 0}),
        ):
            result = extract_link_service.cancel_workbench_batch(91)
        self.assertEqual(0, result["failed"])

    def test_cancel_batch_syncs_account_with_version_captured_before_cancel(self):
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": [{"id": 91}]}),
            patch.object(operation, "list_tasks", return_value={"items": [{
                "last_run_id": 12, "status": "queued", "account_id": 8,
            }], "total": 1}),
            patch.object(record_store, "get_row", return_value={"__record_version": "123"}) as snapshot,
            patch.object(operation, "request_run_cancel", return_value={"status": "cancelled"}) as cancel,
            patch.object(extract_link_batches, "sync_cancelled_account_extraction", create=True, return_value=True) as sync,
            patch.object(extract_link_service.account_task_store, "notify_dispatch"),
        ):
            cancel.side_effect = lambda *args, **kwargs: (
                snapshot.assert_called_once_with(record_store.ACCOUNTS, 8, include_version=True)
                or {"status": "cancelled"})
            result = extract_link_service.cancel_workbench_batch(91)
        sync.assert_called_once_with(12, expected_account_version="123")
        self.assertEqual(1, result["cancelled"])

    def test_cancel_batch_retries_account_sync_for_already_cancelled_run(self):
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": [{"id": 91}]}),
            patch.object(operation, "list_tasks", return_value={"items": [{
                "last_run_id": 12, "status": "cancelled", "account_id": 8,
            }], "total": 1}),
            patch.object(operation, "request_run_cancel") as cancel,
            patch.object(extract_link_batches, "sync_cancelled_account_extraction", create=True, return_value=True) as sync,
        ):
            result = extract_link_service.cancel_workbench_batch(91)
        cancel.assert_not_called()
        sync.assert_called_once_with(12)
        self.assertEqual({"batch_id": 91, "cancelled": 0, "skipped": 0, "failed": 0}, result)

    def test_cancel_batch_reports_account_sync_failure_and_continues(self):
        with (
            patch.object(extract_link_batches, "batch_rows", return_value={"items": [{"id": 91}]}),
            patch.object(operation, "list_tasks", return_value={"items": [
                {"last_run_id": value, "status": "queued", "account_id": value} for value in (1, 2)
            ], "total": 2}),
            patch.object(record_store, "get_row", return_value={"__record_version": "123"}),
            patch.object(operation, "request_run_cancel", return_value={"status": "cancelled"}),
            patch.object(extract_link_batches, "sync_cancelled_account_extraction", create=True,
                side_effect=[False, True]),
            patch.object(extract_link_service.account_task_store, "notify_dispatch"),
        ):
            result = extract_link_service.cancel_workbench_batch(91)
        self.assertEqual({"batch_id": 91, "cancelled": 1, "skipped": 0, "failed": 1}, result)

    def test_invalid_filters_and_quantities_are_rejected(self):
        for filters in ({"access_token": "private"}, {"date_from": "2026-1-01"},
                        {"date_from": "2026-10-22", "date_to": "2026-10-14"},
                        {"extract_status": "unsupported"}, {"promotion": "unknown"}, {"query": 1}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                extract_link_batches.normalize_filters(filters)
        for limit in (0, 5001, True, "100"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                extract_link_batches.normalize_limit(limit)

    def test_batch_workers_accept_twenty_and_fifty_but_reject_out_of_range_or_non_integer(self):
        for workers in (1, 16, 20, 50):
            with self.subTest(workers=workers):
                self.assertEqual(workers, extract_link_batches.normalize_workers(workers))
        for workers in (True, 0, -1, 51, "20", 20.0, None):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                extract_link_batches.normalize_workers(workers)

    def test_disabled_platform_is_rejected_before_creating_batch_or_reading_accounts(self):
        with (
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=False),
            patch.object(extract_link_batches, "candidate_accounts") as candidates,
            patch.object(operation, "create_runtime_batch") as create,
            self.assertRaises(ValueError),
        ):
            extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="auto_payment")
        candidates.assert_not_called()
        create.assert_not_called()

    def test_submission_id_must_be_standard_uuid_before_reading_storage(self):
        for value in ("unsafe", "a" * 32, 123, "11111111-1111-1111-1111-11111111111z"):
            with self.subTest(value=value), patch.object(extract_link_batches, "submission_result") as lookup, self.assertRaises(ValueError):
                extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", submission_id=value)
            lookup.assert_not_called()
        value = str(uuid.uuid4())
        self.assertEqual(value, extract_link_batches.normalize_submission_id(value.upper()))

    def test_workbench_config_exposes_safe_batch_worker_defaults(self):
        for workers in (7, 20, 50):
            with self.subTest(workers=workers), patch.object(
                extract_link_service, "_bool_setting", return_value=False,
            ), patch.object(
                extract_link_service, "_runtime_setting", side_effect=lambda key, default=None: workers if key == "EXTRACT_LINK_BATCH_WORKERS" else default,
            ):
                result = extract_link_service.workbench_config()
                self.assertEqual(workers, result["batch_workers_default"])
                self.assertEqual(50, result["batch_workers_max"])

    def test_dispatch_keeps_fifty_workers_in_batch_and_provider_capacity(self):
        with patch.object(
            extract_link_service, "_runtime_setting",
            side_effect=lambda key, default=None: 50 if key == "EXTRACT_LINK_LUMEN_FLOW_CONCURRENCY" else default,
        ):
            capacity = extract_link_service._provider_dispatch_capacity_key({
                "batch_id": 9, "batch_workers": 50, "data": {"provider_id": "lumen_flow"},
            })
        self.assertEqual({"lumen_flow": 50, "batch:9": 50}, capacity)

    def test_workbench_config_explains_enabled_provider_missing_connection_fields(self):
        def provider_configuration(provider_id):
            if provider_id == "huanguang":
                raise ValueError("提链平台 API 地址或 CDK 未配置")
            return SimpleNamespace(default_type="pix", capabilities={})

        with (
            patch.object(extract_link_service, "_bool_setting", return_value=True),
            patch.object(extract_link_service, "_provider_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", side_effect=provider_configuration),
            patch.object(extract_link_service, "_runtime_setting", side_effect=lambda key, default=None: default),
        ):
            result = extract_link_service.workbench_config()
        self.assertEqual(["legacy", "lumen_flow"], [provider["id"] for provider in result["providers"]])
        self.assertEqual(list(extract_link_service.DEFAULT_LINK_TYPE_ORDER), result["providers"][0]["link_types"])
        self.assertEqual([{
            "id": "huanguang", "label": "幻光", "unavailable_reason": "缺少API地址和平台授权信息",
        }], result["unavailable_providers"])

    def test_more_than_500_accounts_share_one_batch_and_only_notify_once(self):
        candidates = {"total": 501, "items": [{"account_id": value} for value in range(1, 502)],
                      "filters": {"extract_status": "not_succeeded"}, "limit": 501}
        with (
            patch.object(extract_link_service, "_provider_mode_enabled", return_value=True),
            patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(default_type="momo", capabilities={})),
            patch.object(extract_link_service, "_provider_link_type", return_value="momo"),
            patch.object(extract_link_service, "_provider_request_options", return_value={}),
            patch.object(extract_link_batches, "candidate_accounts", return_value=candidates),
            patch.object(operation, "create_runtime_batch", return_value={"id": 9}) as create,
            patch.object(extract_link_service, "create_workbench_tasks", side_effect=[{"started": 500}, {"started": 1}]) as tasks,
            patch.object(extract_link_batches, "finish_submission", return_value=501) as finish,
            patch.object(extract_link_service.account_task_store, "notify_dispatch") as notify,
        ):
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=501)
        self.assertEqual({"batch_id": 9, "requested": 501, "started": 501, "skipped": 0, "failed": 0}, result)
        self.assertEqual([500, 1], [len(call.kwargs["account_ids"]) for call in tasks.call_args_list])
        self.assertTrue(all(call.kwargs["batch_id"] == 9 and call.kwargs["dispatch"] is False for call in tasks.call_args_list))
        self.assertNotIn("access_token", repr(create.call_args.kwargs["data"]))
        finish.assert_called_once_with(9, skipped=0, failed=0, complete=True)
        notify.assert_called_once()


class ExtractWorkbenchBatchStorageTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._previous_operation_schema = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        cls._account_schema_patch = patch.object(account_task_store, "_SCHEMA", cls.schema)
        cls._account_ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        cls._account_schema_patch.start()
        cls._account_ready_patch.start()
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        try:
            operation.reset_ready()
            if cls._previous_operation_schema is None:
                os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
            else:
                os.environ["OPERATION_TASK_DB_SCHEMA"] = cls._previous_operation_schema
        finally:
            cls._account_schema_patch.stop()
            cls._account_ready_patch.stop()
            super().tearDownClass()

    def setUp(self):
        operation.init()

    def test_cancel_batch_covers_all_pages_and_preserves_other_tasks(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="待取消批次", requested_count=203,
            data={"workbench_batch": True, "submission_complete": True})
        other = operation.create_runtime_batch(batch_type="extract_link", title="其他批次", requested_count=1,
            data={"workbench_batch": True, "submission_complete": True})
        def create(batch_id, task_type="extract_link"):
            return operation.create_runtime_task(task_type=task_type, account_id=None, email="cancel@example.test",
                batch_id=batch_id, data={"provider_id": "huanguang"})
        queued = [create(batch["id"]) for _ in range(201)]
        running = create(batch["id"])
        claimed = operation.claim_run(running["run"]["id"], execution_id="cancel-test", worker_pid=os.getpid())
        self.assertIsNotNone(claimed)
        completed = create(batch["id"])
        operation.request_run_cancel(completed["run"]["id"])
        other_task = create(other["id"])
        other_type = create(batch["id"], "live_check")
        with patch.object(extract_link_service.account_task_store, "notify_dispatch"):
            result = extract_link_service.cancel_workbench_batch(batch["id"])
            repeated = extract_link_service.cancel_workbench_batch(batch["id"])
        self.assertEqual({"batch_id": batch["id"], "cancelled": 201, "skipped": 0, "failed": 0}, result)
        self.assertEqual(0, repeated["cancelled"])
        for task in queued:
            self.assertEqual("cancelled", operation.get_run(task["run"]["id"])["status"])
        self.assertEqual("running", operation.get_run(running["run"]["id"])["status"])
        self.assertEqual("cancelled", operation.get_run(completed["run"]["id"])["status"])
        self.assertEqual("queued", operation.get_run(other_task["run"]["id"])["status"])
        self.assertEqual("queued", operation.get_run(other_type["run"]["id"])["status"])

    def test_cancel_batch_skips_run_claimed_after_listing(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="取消竞争", requested_count=1,
            data={"workbench_batch": True, "submission_complete": True})
        task = operation.create_runtime_task(task_type="extract_link", account_id=None, email="race@example.test",
            batch_id=batch["id"], data={"provider_id": "huanguang"})
        original_cancel = operation.request_run_cancel
        def claim_before_cancel(run_id, **kwargs):
            claimed = operation.claim_run(run_id, execution_id="racing-worker", worker_pid=os.getpid())
            self.assertIsNotNone(claimed)
            return original_cancel(run_id, **kwargs)
        with patch.object(operation, "request_run_cancel", side_effect=claim_before_cancel):
            result = extract_link_service.cancel_workbench_batch(batch["id"])
        self.assertEqual({"batch_id": batch["id"], "cancelled": 0, "skipped": 1, "failed": 0}, result)
        run = operation.get_run(task["run"]["id"])
        self.assertEqual("running", run["status"])
        self.assertIsNone(run.get("cancel_requested_at"))

    def accounts(self, overrides):
        return self.seed(record_store.ACCOUNTS, [{
            "email": f"batch-sample-{index}@example.test", "created_at": "2026-10-14T10:00:00",
            "updated_at": "2026-10-14T10:00:00", "email_source": "icloud_hide",
            "current_plan_type": "free", "plan_type": "free", "access_token": "test-private-at",
            "plus_promo_kind": "free_trial", "plan_check_status": "success", "plan_check_ok": True,
            **value,
        } for index, value in enumerate(overrides)])

    def provider_patches(self):
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch.object(extract_link_service, "_provider_mode_enabled", return_value=True))
        stack.enter_context(patch.object(extract_link_service, "_provider_configuration", return_value=SimpleNamespace(default_type="momo", capabilities={"payment": True})))
        stack.enter_context(patch.object(extract_link_service, "_provider_link_type", return_value="momo"))
        stack.enter_context(patch.object(extract_link_service, "_provider_request_options", return_value={}))
        stack.enter_context(patch.object(extract_link_service, "get_config_snapshot", return_value={}))
        stack.enter_context(patch.object(extract_link_service.account_task_store, "notify_dispatch"))
        return stack

    def test_candidate_query_excludes_ineligible_and_busy_accounts_but_keeps_expired_at(self):
        ids = self.accounts([
            {}, {"token_expired": True}, {"archived": True}, {"account_status": "deactivated"},
            {"plus_promo_kind": "discount"}, {"plus_promo_kind": "other_promo"},
            {"plus_promo_kind": "unknown"}, {"access_token": ""}, {"extract_link_status": "success"},
            {"extract_link_status": "running"}, {"plan_type": "plus", "current_plan_type": "plus"},
            {"email_source": "domain"}, {},
        ])
        operation.create_runtime_task(task_type="live_check", account_id=ids[-1], email="busy@example.test")
        result = extract_link_service.preview_workbench_candidates(filters={"source": "icloud_hide", "date_from": "2026-10-14", "date_to": "2026-10-14"}, limit=1)
        self.assertEqual(4, result["total"])
        self.assertEqual(1, result["selected_count"])
        self.assertEqual(ids[0], result["items"][0]["account_id"])
        self.assertNotIn("test-private-at", repr(result))
        all_result = extract_link_service.preview_workbench_candidates(filters={"source": "icloud_hide", "extract_status": "all"}, limit=100)
        self.assertEqual({ids[0], ids[1], ids[4], ids[5], ids[8]}, {item["account_id"] for item in all_result["items"]})

    def test_candidate_promotion_filter_supports_confirmed_trial_discount_and_other_offer(self):
        ids = self.accounts([
            {},
            {"plus_promo_kind": "discount", "plus_promo_discount_percentage": 50},
            {"plus_promo_kind": "discount", "plus_promo_discount_percentage": 20},
            {"plus_promo_kind": "other_promo"},
            {"plus_promo_kind": "unknown"},
        ])
        for promotion, expected in (
            ("free_trial", ids[0]),
            ("half_price", ids[1]),
            ("other_discount", ids[2]),
            ("other_promo", ids[3]),
        ):
            with self.subTest(promotion=promotion):
                result = extract_link_service.preview_workbench_candidates(
                    filters={"promotion": promotion}, limit=100,
                )
                self.assertEqual([expected], [item["account_id"] for item in result["items"]])
        all_result = extract_link_service.preview_workbench_candidates(filters={"promotion": "eligible"}, limit=100)
        self.assertEqual(set(ids[:4]), {item["account_id"] for item in all_result["items"]})

    def test_batch_workers_are_persisted_and_old_batches_keep_existing_limits(self):
        self.accounts([{}, {}])
        with self.provider_patches():
            created = extract_link_service.create_workbench_batch(
                provider_id="lumen_flow", mode="extract_only", limit=1, workers=50)
            with patch.object(extract_link_service, "_runtime_setting", side_effect=lambda key, default=None: 20 if key == "EXTRACT_LINK_BATCH_WORKERS" else default):
                defaulted = extract_link_service.create_workbench_batch(
                    provider_id="lumen_flow", mode="extract_only", limit=1)
        self.assertEqual(50, extract_link_service.workbench_batch_detail(created["batch_id"])["workers"])
        self.assertEqual(20, extract_link_service.workbench_batch_detail(defaulted["batch_id"])["workers"])
        legacy = operation.create_runtime_batch(batch_type="extract_link", title="并发测试", requested_count=4, data={"workbench_batch": True})
        self.assertIsNone(extract_link_service.workbench_batch_detail(legacy["id"])["workers"])

    def test_batch_workers_strictly_validate_before_account_reads(self):
        for value in (True, 0, 51, "2", 2.0):
            with self.subTest(value=value), self.provider_patches(), self.assertRaises(ValueError):
                extract_link_service.create_workbench_batch(
                    provider_id="lumen_flow", mode="extract_only", workers=value)

    def test_dispatch_projects_twenty_and_fifty_worker_batch_limits(self):
        expected = {}
        for workers in (20, 50):
            batch = operation.create_runtime_batch(
                batch_type="extract_link", title="批次并发投影", requested_count=1,
                data={"workbench_batch": True, "workers": workers},
            )
            task = operation.create_runtime_task(
                task_type="extract_link", batch_id=batch["id"], account_id=None,
                email="workers@example.test", data={"provider_id": "lumen_flow"},
            )
            expected[task["run"]["id"]] = workers
        runs = operation.list_dispatchable_runs(task_types=("extract_link",))
        self.assertEqual(expected, {run["id"]: run["batch_workers"] for run in runs})

    def test_old_and_non_extract_batches_keep_their_existing_claim_behavior(self):
        for batch_type, metadata in (("extract_link", {"workbench_batch": True}),
                                     ("account_action", {"workbench_batch": True, "workers": 1})):
            batch = operation.create_runtime_batch(batch_type=batch_type, title="旧批次", requested_count=2, data=metadata)
            tasks = [operation.create_runtime_task(task_type="extract_link", batch_id=batch["id"], account_id=None,
                         email="legacy@example.test") for _ in range(2)]
            for task in tasks:
                claimed = operation.claim_next_queued_run(execution_id="legacy", worker_pid=os.getpid())
                self.assertEqual(task["run"]["id"], claimed["id"])

    def test_parallel_claims_respect_batch_capacity_release_and_retry(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="并发测试", requested_count=4, data={"workbench_batch": True, "workers": 2})
        account_ids = self.accounts([{}, {}, {}, {}])
        tasks = [operation.create_runtime_task(task_type="extract_link", batch_id=batch["id"], account_id=account_id, email="workers@example.test",
                    data={"provider_id": "lumen_flow"}) for account_id in account_ids]
        barrier = threading.Barrier(4)
        def claim(task):
            barrier.wait(timeout=10)
            return operation.claim_run(task["run"]["id"], execution_id=uuid.uuid4().hex, worker_pid=os.getpid())
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(claim, tasks))
        claimed = [item for item in results if item]
        self.assertEqual(2, len(claimed))
        leases = {run["id"]: operation.acquire_account_lease(account_id=run["account_id"], run_id=run["id"]) for run in claimed}
        self.assertTrue(all(leases.values()))
        self.assertEqual([], operation.list_dispatchable_runs(task_types=("extract_link",)))
        # 独立批次仍可认领，已满批次不会挡住后面的批次。
        other = operation.create_runtime_batch(batch_type="extract_link", title="并发测试", requested_count=4, data={"workbench_batch": True, "workers": 1})
        other_task = operation.create_runtime_task(task_type="extract_link", batch_id=other["id"], account_id=None, email="other@example.test")
        self.assertEqual([other_task["run"]["id"]], [r["id"] for r in operation.list_dispatchable_runs(task_types=("extract_link",))])
        operation.finish_run(claimed[0]["id"], status="failed", execution_id=claimed[0]["execution_id"], lease_token=leases[claimed[0]["id"]])
        self.assertFalse(operation.release_account_lease(claimed[0]["id"], leases[claimed[0]["id"]]))
        retry = operation.retry_runtime_task(claimed[0]["task_id"])
        self.assertEqual(batch["id"], retry["batch_id"])
        retried = operation.claim_run(retry["id"], execution_id="retry", worker_pid=os.getpid())
        self.assertIsNotNone(retried)
        retry_lease = operation.acquire_account_lease(account_id=retried["account_id"], run_id=retried["id"])
        self.assertTrue(retry_lease)
        queued = next(task for task in tasks if task["run"]["id"] not in {r["id"] for r in claimed})
        self.assertIsNone(operation.claim_run(queued["run"]["id"], execution_id="blocked", worker_pid=os.getpid()))
        operation.finish_run(retried["id"], status="cancelled", execution_id="retry", lease_token=retry_lease)
        self.assertIsNotNone(operation.claim_run(queued["run"]["id"], execution_id="released", worker_pid=os.getpid()))

    def test_dispatch_reserves_batch_and_provider_capacity_before_shared_workers(self):
        for provider_limit, shared_workers, expected_first in ((4, 4, 3), (2, 4, 2), (4, 2, 2)):
            with self.subTest(provider_limit=provider_limit, shared_workers=shared_workers):
                self.assert_dispatch_capacity(provider_limit, shared_workers, expected_first)

    def test_dispatch_supports_fifty_workers_and_preserves_lower_capacity_limits(self):
        for batch_workers, provider_limit, shared_workers, expected_first in (
            (50, 50, 50, 50), (20, 50, 50, 20), (50, 20, 50, 20), (50, 50, 20, 20),
        ):
            with self.subTest(batch_workers=batch_workers, provider_limit=provider_limit, shared_workers=shared_workers):
                self.assert_dispatch_capacity(
                    provider_limit, shared_workers, expected_first,
                    batch_workers=(batch_workers,), tasks_per_batch=51,
                    expected_indices=range(expected_first),
                )

    def assert_dispatch_capacity(self, provider_limit, shared_workers, expected_first, *,
                                 batch_workers=(1, 2), tasks_per_batch=2, expected_indices=None):
        from core.account_operation_executor import AccountOperationExecutor
        from core.operations import task_gateway

        batches = [operation.create_runtime_batch(batch_type="extract_link", title="并发调度", requested_count=tasks_per_batch,
                   data={"workbench_batch": True, "workers": workers}) for workers in batch_workers]
        tasks = [operation.create_runtime_task(task_type="extract_link", batch_id=batch["id"], account_id=None, email="workers@example.test",
                     data={"provider_id": "lumen_flow"}) for batch in batches for _ in range(tasks_per_batch)]
        executor = AccountOperationExecutor()
        release = threading.Event()
        started = threading.Condition()
        active = []
        errors = []
        def handler(run_id):
            try:
                run = operation.claim_run(run_id, execution_id=str(run_id), worker_pid=os.getpid())
                if not run:
                    return
                with started:
                    active.append(run_id)
                    started.notify_all()
                release.wait(timeout=10)
                operation.finish_run(run_id, status="success", execution_id=str(run_id))
            except Exception as exc:
                errors.append(exc)
        try:
            with (
                patch("core.account_operation_executor.configured_workers", return_value=shared_workers),
                patch.object(task_gateway, "_executor", return_value=executor),
                patch.dict(task_gateway._DISPATCH_HANDLERS, {}, clear=True),
                patch.dict(task_gateway._DISPATCH_CAPACITY_HANDLERS, {}, clear=True),
                patch.dict(task_gateway._DISPATCH_CAPACITY_COUNTS, {}, clear=True),
                patch.object(extract_link_service, "_provider_dispatch_capacity_limit", return_value=provider_limit),
            ):
                task_gateway.register_dispatch_handler("extract_link", handler,
                    dispatch_capacity_key=extract_link_service._provider_dispatch_capacity_key,
                    dispatch_capacity_limit=extract_link_service._provider_dispatch_capacity_limit)
                dispatch_limit = max(20, len(tasks))
                self.assertEqual(expected_first, task_gateway.dispatch_registered_once(limit=dispatch_limit))
                with started:
                    self.assertTrue(started.wait_for(lambda: len(active) == expected_first, timeout=10))
                if expected_indices is None:
                    expected_indices = [0, *range(2, expected_first + 1)]
                self.assertEqual({tasks[index]["run"]["id"] for index in expected_indices}, set(active))
                self.assertEqual(shared_workers - expected_first, executor.available_slots())
                self.assertEqual(0, task_gateway.dispatch_registered_once(limit=dispatch_limit))
                release.set()
                # 等待真实 worker 终态与容量回调，再运行剩余任务。
                with executor._condition:
                    self.assertTrue(executor._condition.wait_for(lambda: executor._accepted == 0, timeout=10))
                remaining = len(tasks) - expected_first
                while remaining:
                    dispatched = task_gateway.dispatch_registered_once(limit=dispatch_limit)
                    self.assertGreater(dispatched, 0)
                    remaining -= dispatched
                    with executor._condition:
                        self.assertTrue(executor._condition.wait_for(lambda: executor._accepted == 0, timeout=10))
                self.assertEqual([], errors)
        finally:
            release.set()
            if executor._executor:
                executor._executor.shutdown(wait=True)
            for task in tasks:
                task_gateway.release_dispatch(task["run"]["id"])

    def test_batch_creation_persists_membership_and_filtered_task_counts(self):
        ids = self.accounts([{}, {}, {"email_source": "domain"}])
        with self.provider_patches():
            result = extract_link_service.create_workbench_batch(title="十四号提链", provider_id="lumen_flow", mode="extract_only", filters={"source": "icloud_hide"}, limit=2)
        self.assertEqual(2, result["started"])
        self.assertEqual(0, result["skipped"])
        selected = extract_link_service.list_workbench_tasks(batch_id=result["batch_id"])
        self.assertEqual(2, selected["total"])
        self.assertEqual(set(ids[:2]), {item["account_id"] for item in selected["items"]})
        self.assertTrue(all(item["batch_id"] == result["batch_id"] for item in selected["items"]))
        detail = extract_link_service.workbench_batch_detail(result["batch_id"])
        self.assertEqual("十四号提链", detail["title"])
        self.assertEqual(2, detail["counts"]["processing"])
        self.assertEqual(2, detail["started_count"])
        self.assertFalse(detail["submission_incomplete"])
        self.assertNotIn("test-private-at", repr(detail))

    def test_cancel_batch_releases_real_account_claims_for_next_batch(self):
        ids = self.accounts([{}, {}])
        with self.provider_patches():
            batch = extract_link_service.create_workbench_batch(
                provider_id="lumen_flow", mode="extract_only", limit=2,
            )
            result = extract_link_service.cancel_workbench_batch(batch["batch_id"])
            repeated = extract_link_service.cancel_workbench_batch(batch["batch_id"])
            candidates = extract_link_batches.candidate_accounts()
            next_batch = extract_link_service.create_workbench_batch(
                provider_id="lumen_flow", mode="extract_only", limit=1,
            )
        self.assertEqual({"batch_id": batch["batch_id"], "cancelled": 2, "skipped": 0, "failed": 0}, result)
        self.assertEqual(0, repeated["cancelled"])
        self.assertEqual(0, repeated["failed"])
        self.assertEqual(set(ids), {item["account_id"] for item in candidates["items"]})
        self.assertEqual(1, next_batch["started"])
        self.assertEqual("cancelled", record_store.get_row(record_store.ACCOUNTS, ids[1])["extract_link_status"])

    def test_failed_unpaid_account_with_historical_create_intent_can_enter_new_auto_payment_batch(self):
        account_id = self.accounts([{"extract_link_status": "failed"}])[0]
        historical = operation.create_runtime_task(
            task_type="extract_link", account_id=account_id, email="failed-retry@example.test",
            data={
                "provider_id": "lumen_flow", "mode": "auto_payment",
                "remote_intent": {
                    "kind": "remote_write", "action": "extract_link_create",
                    "state": "confirmed", "receipt_state": "confirmed",
                },
            },
        )
        historical_run_id = int(historical["run"]["id"])
        extract_link_jobs.save_provider_job(
            historical_run_id, "lumen_flow", "failed-remote-job",
            {"preflight_status": "passed", "extraction_state": "failed", "payment_state": "not_started"},
            {},
        )
        finished = operation.finish_run(
            historical_run_id, status="failed", message="平台提链失败，尚未开始支付",
            result_summary={"extraction_status": "failed", "payment_status": "not_started"},
        )
        # 旧收口规则会把保留创建意向的失败投影为待确认，仍不应永久阻断新批次。
        self.assertEqual("attention_required", finished["status"])

        with self.provider_patches():
            result = extract_link_service.create_workbench_batch(
                provider_id="lumen_flow", mode="auto_payment", workers=5, limit=1,
                filters={"extract_status": "failed", "promotion": "free_trial"},
                submission_id=str(uuid.uuid4()),
            )

        self.assertEqual(1, result["started"])
        self.assertEqual(1, result["requested"])
        self.assertEqual(0, result["skipped"])
        self.assertEqual(0, result["failed"])
        selected = extract_link_service.list_workbench_tasks(batch_id=result["batch_id"])
        self.assertEqual([account_id], [item["account_id"] for item in selected["items"]])

    def test_batch_summary_counts_latest_attempt_once_and_keeps_historical_tasks(self):
        self.accounts([{}])
        with self.provider_patches():
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=1)
        first = extract_link_service.list_workbench_tasks(batch_id=result["batch_id"])["items"][0]
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status='failed' WHERE id=%s", (first["task_id"],))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='failed' WHERE id=%s", (first["run_id"],))
        retry = operation.retry_runtime_task(first["task_id"])
        self.assertEqual(result["batch_id"], retry["batch_id"])
        operation.create_runtime_task(task_type="extract_link", account_id=None, email="historical@example.test")
        detail = extract_link_service.workbench_batch_detail(result["batch_id"])
        self.assertEqual(1, detail["counts"]["all"])
        self.assertEqual(1, detail["counts"]["processing"])
        self.assertEqual(1, detail["started_count"])
        self.assertEqual(2, extract_link_service.list_workbench_tasks()["total"])
        self.assertEqual(1, extract_link_service.list_workbench_batches()["total"])

    def test_empty_interrupted_batch_is_not_reported_as_permanently_queued(self):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="提交中断", requested_count=10,
                                               data={"workbench_batch": True, "provider_id": "lumen_flow", "mode": "extract_only", "submission_complete": False})
        detail = extract_link_service.workbench_batch_detail(batch["id"])
        self.assertEqual("failed", detail["status"])
        self.assertTrue(detail["submission_incomplete"])
        self.assertEqual(0, detail["started_count"])

    def test_changed_account_is_skipped_after_candidate_snapshot(self):
        ids = self.accounts([{}, {}])
        original = extract_link_service.db.claim_account_extract
        def claim(account_id, **kwargs):
            return False if account_id == ids[1] else original(account_id, **kwargs)
        with self.provider_patches(), patch.object(extract_link_service.db, "claim_account_extract", side_effect=claim):
            result = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=2)
        self.assertEqual(1, result["started"])
        self.assertEqual(1, result["skipped"])
        detail = extract_link_service.workbench_batch_detail(result["batch_id"])
        self.assertEqual(2, detail["requested_count"])
        self.assertEqual(1, detail["skipped_count"])
        self.assertFalse(detail["submission_incomplete"])

    def test_lost_response_retry_returns_original_batch_without_selecting_next_accounts(self):
        ids = self.accounts([{}, {}, {}])
        submission_id = str(uuid.uuid4())
        with self.provider_patches(), patch.object(extract_link_batches, "candidate_accounts", wraps=extract_link_batches.candidate_accounts) as candidates:
            first = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=1, submission_id=submission_id, workers=3)
            second = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=2, submission_id=submission_id, workers=5)
        self.assertEqual(first, second)
        self.assertEqual(3, extract_link_service.workbench_batch_detail(first["batch_id"])["workers"])
        self.assertEqual(1, candidates.call_count)
        self.assertEqual(1, extract_link_service.list_workbench_batches()["total"])
        tasks = extract_link_service.list_workbench_tasks()["items"]
        self.assertEqual([ids[0]], [item["account_id"] for item in tasks])
        with patch.object(extract_link_service, "_provider_mode_enabled", return_value=False):
            self.assertEqual(first, extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", submission_id=submission_id))

    def test_concurrent_submission_id_reserves_candidates_once(self):
        self.accounts([{}, {}, {}])
        submission_id = str(uuid.uuid4())
        first_selected = threading.Event()
        allow_insert = threading.Event()
        original_candidates = extract_link_batches.candidate_accounts

        def candidates(**kwargs):
            selected = original_candidates(**kwargs)
            first_selected.set()
            if not allow_insert.wait(5):
                raise AssertionError("并发提交测试未释放候选事务")
            return selected

        def reserve():
            return extract_link_batches.reserve_submission(
                submission_id=submission_id, title="并发批次", provider_id="lumen_flow",
                mode="extract_only", link_type="momo", filters=None, limit=1,
            )

        with patch.object(extract_link_batches, "candidate_accounts", side_effect=candidates) as selected, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(reserve)
            self.assertTrue(first_selected.wait(5))
            second = pool.submit(reserve)
            allow_insert.set()
            results = [first.result(10), second.result(10)]
        self.assertEqual([False, True], sorted(item["created"] for item in results))
        self.assertEqual(1, selected.call_count)
        created = next(item for item in results if item["created"])
        retried = next(item for item in results if not item["created"])
        self.assertEqual(created["batch_id"], retried["result"]["batch_id"])
        self.assertEqual(1, retried["result"]["requested"])
        self.assertEqual(0, retried["result"]["started"])

    def test_interrupted_reserved_submission_does_not_reselect_or_stay_running(self):
        self.accounts([{}, {}])
        submission_id = str(uuid.uuid4())
        reservation = extract_link_batches.reserve_submission(submission_id=submission_id, title="中断批次", provider_id="lumen_flow", mode="extract_only", link_type="momo", filters=None, limit=1)
        with patch.object(extract_link_batches, "candidate_accounts") as candidates:
            retried = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", submission_id=submission_id)
        candidates.assert_not_called()
        self.assertEqual(reservation["batch_id"], retried["batch_id"])
        self.assertEqual(0, retried["started"])
        detail = extract_link_service.workbench_batch_detail(retried["batch_id"])
        self.assertEqual("failed", detail["status"])
        self.assertTrue(detail["submission_incomplete"])

    def state_batch(self, *, account_id, task_status="success", mode="auto_payment", state=None, provider_id="lumen_flow", result_summary=None):
        batch = operation.create_runtime_batch(batch_type="extract_link", title="状态批次", requested_count=1,
            data={"workbench_batch": True, "provider_id": provider_id, "mode": mode, "submission_complete": True})
        task = operation.create_runtime_task(task_type="extract_link", account_id=account_id, email="status@example.test", batch_id=batch["id"],
            data={"provider_id": provider_id, "mode": mode, "config_snapshot": {"access_token": "must-not-be-projected"}})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status=%s WHERE id=%s", (task_status, task["id"]))
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET status=%s, result_summary=%s::jsonb WHERE id=%s", (task_status, operation._json(result_summary or {}), task["run"]["id"]))
        if state is not None:
            extract_link_jobs.save_provider_job(task["run"]["id"], provider_id, "test-job", state, {"job_secret": "must-not-be-projected"})
        return int(batch["id"])

    def test_pending_payment_and_plan_verification_remain_processing_but_unknown_does_not(self):
        scenarios = [
            ("partial_success", "pending", "not_applicable", 1, "waiting"),
            ("attention_required", "unknown", "not_applicable", 0, "partial_success"),
            ("success", "succeeded", "pending", 1, "waiting"),
            ("success", "succeeded", "unknown", 1, "waiting"),
        ]
        ids = self.accounts([{"plan_check_status": "queued"} for _ in scenarios])
        for account_id, (task_status, payment, plus, processing, status) in zip(ids, scenarios):
            with self.subTest(payment=payment, plus=plus):
                batch_id = self.state_batch(account_id=account_id, task_status=task_status,
                    state={"extraction_state": "succeeded", "payment_state": payment, "plus_status": plus})
                detail = extract_link_service.workbench_batch_detail(batch_id)
                task_counts = extract_link_service.list_workbench_tasks(batch_id=batch_id)["counts"]
                self.assertEqual(task_counts, detail["counts"])
                self.assertEqual(processing, detail["counts"]["processing"])
                self.assertEqual(0, detail["counts"]["running"])
                self.assertEqual(status, detail["status"])
                if payment == "unknown":
                    self.assertEqual(1, detail["counts"]["needs_attention"])

    def test_queued_continuation_with_link_keeps_batch_queued(self):
        account_id = self.accounts([{"plan_check_status": "queued"}])[0]
        batch_id = self.state_batch(account_id=account_id, provider_id="huanguang", task_status="queued",
            state={"preflight_status": "passed", "extraction_state": "succeeded",
                   "payment_state": "pending", "plus_status": "not_applicable"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} SET data=data || %s::jsonb, next_attempt_at=now() + interval '30 seconds' WHERE task_id IN (SELECT id FROM {operation._table('operation_tasks')} WHERE batch_id=%s)",
                ('{"extract_poll_continuation": true}', batch_id),
            )
        detail = extract_link_service.workbench_batch_detail(batch_id)
        self.assertEqual("queued", detail["status"])
        self.assertEqual(1, detail["counts"]["processing"])
        self.assertEqual(0, detail["counts"]["running"])
        self.assertEqual(1, detail["counts"]["extraction_succeeded"])
        self.assertEqual(extract_link_service.list_workbench_tasks(batch_id=batch_id)["counts"], detail["counts"])

    def test_summary_aggregate_matches_task_semantics_without_full_account_or_run_projection(self):
        scenarios = [
            {"state": {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "confirmed"}},
            {"state": {"extraction_state": "succeeded", "payment_state": "failed", "plus_status": "not_applicable"}},
            {"state": {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "failed"}},
            {"state": {"extraction_state": "succeeded", "payment_state": "succeeded", "plus_status": "not_confirmed"}},
            {"mode": "extract_only", "state": {"extraction_state": "succeeded", "plus_status": "not_applicable"}},
            {"mode": "manual_payment", "state": {"extraction_state": "succeeded", "payment_state": "not_started", "plus_status": "not_applicable"}},
            {"provider_id": "legacy", "mode": "extract_only", "result_summary": {"remote_job_id": "safe-id", "has_link": True}},
            {"task_status": "failed", "state": {"extraction_state": "failed", "payment_state": "failed", "plus_status": "not_applicable"}},
        ]
        ids = self.accounts([{} for _ in scenarios])
        expected = {}
        for account_id, scenario in zip(ids, scenarios):
            batch_id = self.state_batch(account_id=account_id, **scenario)
            expected[batch_id] = extract_link_service.list_workbench_tasks(batch_id=batch_id)["counts"]
        with (
            patch.object(extract_link_jobs, "list_workbench_rows", side_effect=AssertionError("批次摘要不能读取完整任务投影")),
            patch.object(extract_link_service.db, "get_accounts_for_jobs", side_effect=AssertionError("批次摘要不能读取完整账号")),
        ):
            listed = extract_link_service.list_workbench_batches()
            for item in listed["items"]:
                self.assertEqual(expected[item["batch_id"]], item["counts"])
                self.assertEqual(item, extract_link_service.workbench_batch_detail(item["batch_id"]))
        self.assertNotIn("must-not-be-projected", repr(listed))
        statuses = {item["batch_id"]: item["status"] for item in listed["items"]}
        self.assertEqual("success", statuses[min(expected)])
        self.assertEqual("partial_success", statuses[min(expected) + 1])
