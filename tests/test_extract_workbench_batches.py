from __future__ import annotations

import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from core import account_task_store, extract_link_service, record_store
from core.storage import extract_link_batches, extract_link_jobs, operation
from tests.support_pg import PostgresTestCase


class ExtractWorkbenchBatchValidationTests(unittest.TestCase):
    def test_invalid_filters_and_quantities_are_rejected(self):
        for filters in ({"access_token": "private"}, {"date_from": "2026-1-01"},
                        {"date_from": "2026-10-22", "date_to": "2026-10-14"},
                        {"extract_status": "unsupported"}, {"query": 1}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                extract_link_batches.normalize_filters(filters)
        for limit in (0, 5001, True, "100"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                extract_link_batches.normalize_limit(limit)

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
            {"plus_promo_kind": "discount"}, {"access_token": ""}, {"extract_link_status": "success"},
            {"extract_link_status": "running"}, {"plan_type": "plus", "current_plan_type": "plus"},
            {"email_source": "domain"}, {},
        ])
        operation.create_runtime_task(task_type="live_check", account_id=ids[-1], email="busy@example.test")
        result = extract_link_service.preview_workbench_candidates(filters={"source": "icloud_hide", "date_from": "2026-10-14", "date_to": "2026-10-14"}, limit=1)
        self.assertEqual(2, result["total"])
        self.assertEqual(1, result["selected_count"])
        self.assertEqual(ids[0], result["items"][0]["account_id"])
        self.assertNotIn("test-private-at", repr(result))
        all_result = extract_link_service.preview_workbench_candidates(filters={"source": "icloud_hide", "extract_status": "all"}, limit=100)
        self.assertEqual({ids[0], ids[1], ids[6]}, {item["account_id"] for item in all_result["items"]})

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
            first = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=1, submission_id=submission_id)
            second = extract_link_service.create_workbench_batch(provider_id="lumen_flow", mode="extract_only", limit=2, submission_id=submission_id)
        self.assertEqual(first, second)
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

    def test_pending_unknown_and_plan_verification_remain_processing(self):
        scenarios = [
            ("partial_success", "pending", "not_applicable"),
            ("attention_required", "unknown", "not_applicable"),
            ("success", "succeeded", "pending"),
            ("success", "succeeded", "unknown"),
        ]
        ids = self.accounts([{"plan_check_status": "queued"} for _ in scenarios])
        for account_id, (task_status, payment, plus) in zip(ids, scenarios):
            with self.subTest(payment=payment, plus=plus):
                batch_id = self.state_batch(account_id=account_id, task_status=task_status,
                    state={"extraction_state": "succeeded", "payment_state": payment, "plus_status": plus})
                detail = extract_link_service.workbench_batch_detail(batch_id)
                task_counts = extract_link_service.list_workbench_tasks(batch_id=batch_id)["counts"]
                self.assertEqual(task_counts, detail["counts"])
                self.assertEqual(1, detail["counts"]["processing"])
                self.assertEqual("running", detail["status"])

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
