import base64
import importlib.util
import json
import os
import time
from contextlib import ExitStack
from unittest.mock import Mock, patch

from config import c2a as config
from core.integrations.c2a import client, manual_sync
from core.operations import task_gateway
from core.storage import postgres, records
from core.storage.operations import bulk, runtime
from tests.support_pg import PostgresTestCase


def at(email, *, issued, expires):
    claims = {"iat": issued, "exp": expires, "https://api.openai.com/profile": {"email": email}}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{payload}.isolated-test-signature"


def remote(remote_id, email, **changes):
    return {
        "id": remote_id, "email": email, "enabled": True, "backend_status": "正常", "status_category": "abnormal",
        "status_reason_code": "credentials_unavailable", "credential_availability": "unavailable",
        "access_token_status": "invalid", **changes,
    }


class C2AMonitorTests(PostgresTestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("core.integrations.c2a.monitor"), "C2A 巡检尚未实现")
        from core.integrations.c2a import monitor
        from core.storage import c2a

        self.monitor = monitor
        self.store = c2a
        self.backend = "a" * 64
        self.now = int(time.time())
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(config, "C2A_MONITOR_ENABLED", True, create=True))
        self.stack.enter_context(patch.object(config, "C2A_MONITOR_COOLDOWN_SECONDS", 300, create=True))
        self.stack.enter_context(patch.object(client, "configured_backend_identity", return_value=self.backend))
        self.stack.enter_context(patch("core.bulk_operations.catalog.capture_settings", return_value={
            "parameters": {}, "config_revision": "12", "config_snapshot": {},
        }))
        self.stack.enter_context(patch("core.accounts.liveness.service.deployment_unavailable", return_value=None))
        self.remote_list = self.stack.enter_context(patch.object(client, "list_configured_accounts", return_value=[], create=True))
        self.queued_upload = self.stack.enter_context(patch.object(manual_sync, "queue_target", side_effect=self._queue_target, create=True))
        self.store.init()
        bulk.init()

    def _queue_target(self, account, remote_id, *, expected_backend, idempotency_key, trigger):
        created = runtime.create_runtime_task(
            task_type="c2a_session_reimport", account_id=account["id"], email=account["email"],
            trigger=trigger, source_id=idempotency_key,
            data={"backend_identity": expected_backend, "remote_account_id": remote_id, "monitor_managed": True},
        )
        return {"accepted": True, "task_id": created["id"], "run_id": created["run"]["id"]}

    def _scan(self, **options):
        return self.monitor._scan(self.backend, **options)

    def _seed_account(self, email, *, fresh=False):
        token = at(email, issued=self.now - (120 if fresh else 7200), expires=self.now + (3600 if fresh else -60))
        return self.seed(records.ACCOUNTS, [{"email": email, "status": "success", "access_token": token}])[0]

    def _start_refresh(self, rows):
        self.remote_list.return_value = rows
        self._scan()
        repairs = self.store.list_repairs(self.backend)
        selection_ids = {row["selection_id"] for row in repairs}
        self.assertEqual(len(selection_ids), 1)
        selection_id = next(iter(selection_ids))
        bulk.freeze_selection(selection_id)
        self._scan()
        batch_ids = {row["batch_id"] for row in self.store.list_repairs(self.backend)}
        self.assertEqual(len(batch_ids), 1)
        return next(iter(batch_ids))

    def _set_refresh_receipt(self, run_id, receipt_state):
        table = postgres.qualified("operation_runs")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {table} SET data=data || %s::jsonb WHERE id=%s",
                (json.dumps({"remote_intent": {"kind": "remote_write", "action": "token_refresh", "receipt_state": receipt_state}}), run_id),
            )

    def _finish_refreshed(self, account_id, email, run_id):
        records.patch_row(records.ACCOUNTS, account_id, changes={
            "access_token": at(email, issued=self.now, expires=self.now + 7200),
        })
        self._set_refresh_receipt(run_id, "confirmed")
        runtime.finish_run(run_id, status="success", result_summary={
            "ok": True, "remote_receipt_state": "confirmed", "validation_method": "email_otp",
        })
        bulk.project_pending()

    def _fail_refresh(self, batch_id, *, receipt_unknown=False):
        from core.bulk_operations.adapters import submit_chunk

        self.assertEqual(bulk.process_batch(batch_id, submit_chunk)["submitted"], 1)
        target = bulk.list_targets(batch_id)["items"][0]
        run_id = target["run_id"]
        run = runtime.claim_run(run_id, execution_id=f"c2a-test-failure-{run_id}", worker_pid=os.getpid())
        self.assertEqual(run["status"], "running")
        if receipt_unknown:
            self._set_refresh_receipt(run_id, "started")
        finished = runtime.finish_run(run_id, status="failed", result_summary={"error_code": "invalid_credentials"})
        if receipt_unknown:
            self.assertEqual(finished["status"], "attention_required")
            self.assertEqual(finished["result_summary"]["outcome"], "request_unknown")
        bulk.project_pending()
        self.assertEqual(bulk.list_targets(batch_id)["items"][0]["outcome"], "failed")
        return target

    def _fail_second_refresh(self, *, receipt_unknown=False):
        retry_at = self.store.list_repairs(self.backend)[0]["next_attempt_at"]
        with patch.object(self.monitor.time, "time", return_value=retry_at + 1):
            batch_id = self._start_refresh(self.remote_list.return_value)
            target = self._fail_refresh(batch_id, receipt_unknown=receipt_unknown)
            self._scan()
        return batch_id, target

    def _selection_count(self):
        selections = postgres.qualified("operation_selections")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {selections}")
            return cur.fetchone()[0]

    def test_batches_expired_accounts_and_syncs_confirmed_item_while_batch_active(self):
        from core.bulk_operations.adapters import submit_chunk

        first = self._seed_account("first@example.test")
        second = self._seed_account("second@example.test")
        batch_id = self._start_refresh([
            remote("remote-1", "first@example.test"),
            remote("remote-1b", "first@example.test"),
            remote("remote-2", "second@example.test"),
        ])
        targets = bulk.list_targets(batch_id)["items"]
        self.assertEqual({row["outcome"] for row in targets}, {"pending_submit"})
        self._scan()
        self.assertEqual(self.monitor.status()["repair_stages"], {"refresh_wait": 2})
        self.assertEqual(bulk.process_batch(batch_id, submit_chunk)["submitted"], 2)
        targeted = bulk.list_targets(batch_id)["items"]
        self.assertEqual({row["account_id"] for row in targeted}, {first, second})
        first_run = next(row["run_id"] for row in targeted if row["account_id"] == first)
        self._scan()
        self.assertFalse(self.queued_upload.called, "等待中的刷新不得产生 C2A 写入任务")

        def finish_then_read(*args, **kwargs):
            self._finish_refreshed(first, "first@example.test", first_run)
            return list_targets(*args, **kwargs)

        list_targets = bulk.list_targets
        with patch.object(config, "C2A_MONITOR_ENABLED", False), patch.object(bulk, "list_targets", side_effect=finish_then_read):
            self.remote_list.side_effect = AssertionError("关闭后不能重新扫描远端")
            result = self._scan(continuation_only=True)
        self.assertEqual([call.args[1] for call in self.queued_upload.call_args_list], ["remote-1"])
        self.assertEqual(result["batch_refs"], [{"batch_id": str(batch_id), "round_id": str(bulk.get_batch(batch_id)["initial_round_id"])}])
        job = self.store.list_repairs(self.backend)[0]["targets"]["remote-1"]
        self.assertEqual(result["child_tasks"], [{
            "task_id": str(job["task_id"]), "run_id": str(job["run_id"]), "task_type": "c2a_session_reimport", "status": "queued",
        }])
        self.assertEqual(self.monitor.status()["repair_stages"], {"refresh_wait": 1, "sync_wait": 1})
        runtime.finish_run(job["run_id"], status="success", result_summary={"ok": True})
        self._scan(continuation_only=True)
        self.assertEqual([call.args[1] for call in self.queued_upload.call_args_list], ["remote-1", "remote-1b"])

    def test_remote_list_error_still_advances_persisted_sync(self):
        self._seed_account("latest@example.test", fresh=True)
        self.remote_list.return_value = [remote("existing", "latest@example.test", access_token_issued_at=self.now - 1800)]
        self._scan()
        self.assertEqual(len(self.queued_upload.call_args_list), 1)
        job = self.store.list_repairs(self.backend)[0]["targets"]["existing"]
        runtime.finish_run(job["run_id"], status="success", result_summary={"ok": True})
        self.remote_list.side_effect = client.C2AError("scan_accounts", "c2a_timeout", "合成错误")
        result = self._scan()
        self.assertEqual(result["error_code"], "c2a_timeout")
        self.assertEqual(self.monitor.status()["repair_stages"], {"done": 1})

    def test_unknown_upload_retries_after_cooldown_and_reuses_persisted_generation(self):
        self._seed_account("retry@example.test", fresh=True)
        self.remote_list.return_value = [remote("existing", "retry@example.test", access_token_issued_at=self.now - 1800)]
        self._scan()
        first_call = self.queued_upload.call_args
        job = self.store.list_repairs(self.backend)[0]["targets"]["existing"]
        runtime.finish_run(job["run_id"], status="attention_required", result_summary={"outcome": "request_unknown"})
        self._scan()
        self._scan()
        self.assertEqual(self.queued_upload.call_count, 1)
        retry_at = self.store.list_repairs(self.backend)[0]["targets"]["existing"]["next_attempt_at"]
        with patch.object(self.monitor.time, "time", return_value=retry_at + 1):
            self._scan()
        self.assertEqual(self.queued_upload.call_count, 2)
        self.assertEqual(self.queued_upload.call_args.args[1], "existing")
        self.assertNotEqual(self.queued_upload.call_args.kwargs["idempotency_key"], first_call.kwargs["idempotency_key"])

    def test_cancelled_upload_is_reopened_only_by_manual_scan(self):
        self._seed_account("stop@example.test", fresh=True)
        self.remote_list.return_value = [remote("original", "stop@example.test", access_token_issued_at=self.now - 1800)]
        self._scan()
        job = self.store.list_repairs(self.backend)[0]["targets"]["original"]
        runtime.request_run_cancel(job["run_id"], reason="用户取消")
        self._scan()
        retry_at = self.store.list_repairs(self.backend)[0]["next_attempt_at"]
        with patch.object(self.monitor.time, "time", return_value=retry_at + 1):
            self._scan()
            self.assertEqual(self.queued_upload.call_count, 1)
            self.assertEqual(self.monitor.status()["repair_stages"], {"cancelled": 1})
            self._scan(force=True)
        self.assertEqual(self.queued_upload.call_count, 2)

    def test_remote_non_credential_failures_are_not_reauthenticated(self):
        self.remote_list.return_value = [
            remote("disabled", "disabled@example.test", backend_status="禁用", status_category="disabled", enabled=False),
            remote("limited", "limited@example.test", status_reason_code="rate_limited"),
            remote("quota", "quota@example.test", backend_status="限流", status_reason_code="image_quota_exhausted"),
            remote("error", "error@example.test", status_reason_code="remote_check_failed", credential_availability="usable",
                   access_token_status="valid", access_token_expires_at=self.now + 3600),
            remote("pending", "pending@example.test", status_reason_code="verification_pending", credential_availability="usable",
                   access_token_status="valid", access_token_expires_at=self.now + 3600),
            remote("unexpected", "unexpected@example.test", access_token_status="valid", credential_availability="usable",
                   backend_status="异常", status_reason_code=""),
        ]
        result = self._scan()
        self.assertEqual(result["reasons"], {
            "c2a_remote_account_disabled": 1,
            "c2a_remote_rate_limited": 1,
            "c2a_remote_quota_exhausted": 1,
            "c2a_remote_temporarily_unavailable": 1,
            "c2a_remote_verification_pending": 1,
            "c2a_remote_diagnostic_missing": 1,
        })
        self.assertEqual(self.store.list_repairs(self.backend), [])

    def test_hard_credential_failure_takes_priority_over_inconclusive_probe(self):
        accounts = [self._seed_account(email) for email in ("pending@example.test", "check@example.test")]
        self.remote_list.return_value = [
            remote("pending", "pending@example.test", status_reason_code="verification_pending", credential_availability="recoverable",
                   access_token_status="valid", access_token_expires_at=self.now - 30),
            remote("check", "check@example.test", status_reason_code="remote_check_failed", credential_availability="recoverable"),
        ]
        self._scan()
        self.assertEqual([row["account_id"] for row in self.store.list_repairs(self.backend)], accounts)

    def test_cancelling_running_bulk_refresh_preserves_unknown_receipt_and_stops_automatic_login(self):
        from core.bulk_operations.adapters import submit_chunk

        email = "cancel-refresh@example.test"
        self._seed_account(email)
        first_batch = self._start_refresh([remote("original", email)])
        self._fail_refresh(first_batch)
        self._scan()
        retry_at = self.store.list_repairs(self.backend)[0]["next_attempt_at"]
        with patch.object(self.monitor.time, "time", return_value=retry_at + 1):
            batch_id = self._start_refresh(self.remote_list.return_value)
        self.assertEqual(bulk.process_batch(batch_id, submit_chunk)["submitted"], 1)
        run_id = bulk.list_targets(batch_id)["items"][0]["run_id"]
        self.assertEqual(runtime.claim_run(run_id, execution_id="c2a-test-cancel", worker_pid=os.getpid())["status"], "running")
        self._set_refresh_receipt(run_id, "started")
        self.assertEqual(runtime.request_run_cancel(run_id, reason="用户取消刷新")["status"], "cancelling")
        self.assertEqual(runtime.finish_run(run_id, status="cancelled")["status"], "attention_required")
        bulk.project_pending()
        self.assertEqual(bulk.list_targets(batch_id)["items"][0]["outcome"], "failed")
        self.assertEqual(self._scan()["reasons"], {"c2a_repair_cancelled": 1})
        self.assertFalse(self.store.has_pending(self.backend))
        row = self.store.list_repairs(self.backend)[0]
        self.assertEqual(row["stage"], "cancelled")
        self.assertEqual(row.get("refresh_failure_count"), 1)
        self._scan()
        self.assertFalse(self.store.has_pending(self.backend))
        self._scan(force=True)
        self.assertTrue(self.store.has_pending(self.backend))
        self.assertEqual(self.store.list_repairs(self.backend)[0]["refresh_failure_count"], 1)

    def test_two_failed_refresh_runs_stop_automatic_submission_even_on_manual_scan(self):
        email = "refresh-limit@example.test"
        self._seed_account(email)
        first_batch = self._start_refresh([remote("original", email)])
        first = self._fail_refresh(first_batch)
        for scan in range(3):
            self._scan()
            row = self.store.list_repairs(self.backend)[0]
            with self.subTest(first_run=first["run_id"], scan=scan):
                self.assertEqual(row.get("refresh_failure_count"), 1)
                self.assertEqual(row.get("refresh_observed_run_id"), first["run_id"])
        second_batch, second = self._fail_second_refresh(receipt_unknown=True)
        self.assertNotEqual(second["run_id"], first["run_id"])
        exhausted = self.store.list_repairs(self.backend)[0]
        later = max(exhausted["next_attempt_at"], self.now + 600) + 1
        self.assertEqual(self._selection_count(), 2)

        with patch.object(self.monitor.time, "time", return_value=later):
            for force in (False, True):
                with self.subTest(force=force):
                    self._scan(force=force)
                    self.assertEqual(self._selection_count(), 2, "巡检不得创建第三次刷新名单")
                    self.assertEqual(
                        {row["id"] for row in bulk.list_batches()["items"]},
                        {first_batch, second_batch},
                    )
                    row = self.store.list_repairs(self.backend)[0]
                    self.assertEqual(row["stage"], "refresh_exhausted")
                    self.assertEqual(row.get("refresh_failure_count"), 2)
                    self.assertEqual(row.get("refresh_observed_run_id"), second["run_id"])
        self.assertFalse(self.queued_upload.called)

    def test_refresh_failures_before_execution_do_not_consume_remaining_attempt(self):
        from core.bulk_operations.adapters import submit_chunk

        email = "refresh-setup@example.test"
        self._seed_account(email)
        batch_id = self._start_refresh([remote("original", email)])
        first = self._fail_refresh(batch_id)
        self._scan()
        row = self.store.list_repairs(self.backend)[0]

        with patch.object(self.monitor.time, "time", return_value=row["next_attempt_at"] + 1):
            self._scan()
            pending = self.store.list_repairs(self.backend)[0]
            self.assertTrue(bulk.fail_selection(pending["selection_id"], error_code="selection_failed"))
            self._scan()
        selection_failure = self.store.list_repairs(self.backend)[0]
        self.assertEqual(selection_failure["last_code"], "selection_failed")
        self.assertIsNone(selection_failure["batch_id"])

        with patch.object(self.monitor.time, "time", return_value=selection_failure["next_attempt_at"] + 1):
            self._scan()
            pending = self.store.list_repairs(self.backend)[0]
            bulk.freeze_selection(pending["selection_id"])
            with patch.object(
                self.monitor.bulk_service, "create_batch",
                side_effect=bulk.BulkError("config_revision_changed", "合成批次受理错误"),
            ):
                self._scan()
        batch_failure = self.store.list_repairs(self.backend)[0]
        self.assertEqual(batch_failure["last_code"], "config_revision_changed")
        self.assertIsNone(batch_failure["batch_id"])
        self.assertEqual([row["id"] for row in bulk.list_batches()["items"]], [batch_id])

        with patch.object(self.monitor.time, "time", return_value=batch_failure["next_attempt_at"] + 1):
            unexecuted_batch = self._start_refresh(self.remote_list.return_value)
            self.assertEqual(bulk.process_batch(unexecuted_batch, submit_chunk)["submitted"], 1)
            run_id = bulk.list_targets(unexecuted_batch)["items"][0]["run_id"]
            runtime.finish_run(run_id, status="unsupported")
            bulk.project_pending()
            self.assertEqual(bulk.list_targets(unexecuted_batch)["items"][0]["outcome"], "not_executed")
            self._scan()
        not_executed = self.store.list_repairs(self.backend)[0]
        for row in (selection_failure, batch_failure, not_executed):
            with self.subTest(failed_stage=row["last_code"]):
                self.assertEqual(row["stage"], "refresh_retry")
                self.assertEqual(row.get("refresh_failure_count"), 1)
        for row in (selection_failure, batch_failure):
            self.assertEqual(row.get("refresh_observed_run_id"), first["run_id"])

    def _assert_user_retry_syncs_original_target(self, *, exhausted):
        from core.bulk_operations.adapters import submit_chunk

        email = "retry-batch@example.test"
        account_id = self._seed_account(email)
        batch_id = self._start_refresh([remote("original", email)])
        failed = self._fail_refresh(batch_id)
        self._scan()
        if exhausted:
            batch_id, failed = self._fail_second_refresh()
        row = self.store.list_repairs(self.backend)[0]
        self.assertEqual(row["stage"], "refresh_exhausted" if exhausted else "refresh_retry")
        self.assertEqual(row["refresh_failure_count"], 2 if exhausted else 1)
        retry = self.monitor.bulk_service.retry_managed_task(failed["task_id"], request_key="c2a-test-user-retry")
        retry_round = int(retry["round_id"])
        bulk.freeze_round(retry_round)
        self._scan()
        self.assertEqual(self.store.list_repairs(self.backend)[0]["stage"], "refresh_wait")
        self.assertEqual(bulk.process_batch(batch_id, submit_chunk)["submitted"], 1)
        current = bulk.list_targets(batch_id)["items"][0]
        self.assertEqual(current["round_id"], retry_round)
        records.patch_row(records.ACCOUNTS, account_id, changes={
            "access_token": at(email, issued=self.now, expires=self.now + 7200),
        })
        self._scan()
        self.assertFalse(self.queued_upload.called, "人工新轮尚未收口时不得启动上传")
        self._finish_refreshed(account_id, email, current["run_id"])
        result = self._scan()
        self.assertEqual(self.queued_upload.call_args.args[1], "original")
        self.assertEqual(result["batch_refs"], [{"batch_id": str(batch_id), "round_id": str(retry_round)}])
        self.assertEqual(self.store.list_repairs(self.backend)[0]["refresh_failure_count"], 0)

    def test_user_retry_of_managed_batch_reuses_persisted_target_and_new_at(self):
        self._assert_user_retry_syncs_original_target(exhausted=False)

    def test_user_retry_of_exhausted_managed_batch_syncs_the_original_target(self):
        self._assert_user_retry_syncs_original_target(exhausted=True)

    def test_exhausted_account_can_sync_a_new_local_at_without_refreshing(self):
        email = "external-refresh@example.test"
        account_id = self._seed_account(email)
        first_batch = self._start_refresh([remote("original", email)])
        self._fail_refresh(first_batch)
        self._scan()
        self._fail_second_refresh()
        self.assertEqual(self.store.list_repairs(self.backend)[0]["stage"], "refresh_exhausted")
        records.patch_row(records.ACCOUNTS, account_id, changes={
            "access_token": at(email, issued=self.now, expires=self.now + 7200),
        })
        self._scan()
        self.assertEqual(self._selection_count(), 2)
        self.assertEqual(self.queued_upload.call_args.args[1], "original")
        row = self.store.list_repairs(self.backend)[0]
        self.assertEqual(row["stage"], "sync_wait")
        self.assertEqual(row["refresh_failure_count"], 0)

    def test_result_summary_keeps_reason_codes_after_persistence(self):
        self._seed_account("unchanged@example.test")
        batch_id = self._start_refresh([remote("original", "unchanged@example.test")])
        from core.bulk_operations.adapters import submit_chunk

        bulk.process_batch(batch_id, submit_chunk)
        run_id = bulk.list_targets(batch_id)["items"][0]["run_id"]
        runtime.claim_run(run_id, execution_id="c2a-test-unchanged", worker_pid=os.getpid())
        self._set_refresh_receipt(run_id, "confirmed")
        runtime.finish_run(run_id, status="success", result_summary={"ok": True, "remote_receipt_state": "confirmed"})
        bulk.project_pending()
        context = Mock(run={"data": {"backend_identity": self.backend}})
        result = self.monitor._handle_scan(context)
        scan_id = runtime.create_runtime_task(
            task_type=self.monitor.TASK_TYPE, account_id=None, email="", source_id="c2a-test-reason-scrub",
        )["run"]["id"]
        runtime.finish_run(scan_id, status=result.status, result_summary=result.summary)
        self.assertEqual(runtime.get_run(scan_id)["result_summary"]["reasons"], [{
            "code": "c2a_refresh_token_unchanged", "count": 1,
        }])
        self.assertEqual(self.store.list_repairs(self.backend)[0].get("refresh_failure_count"), 1)

    def test_pending_retry_uses_recent_local_at_without_submitting_another_batch(self):
        account_id = self._seed_account("newer@example.test")
        self.remote_list.return_value = [remote("existing", "newer@example.test")]
        self._scan()
        row = self.store.list_repairs(self.backend)[0]
        row.update(stage="refresh_retry", next_attempt_at=self.now, last_code="c2a_refresh_token_unchanged")
        self.store.save_repairs(self.backend, [row])
        records.patch_row(records.ACCOUNTS, account_id, changes={
            "access_token": at("newer@example.test", issued=self.now, expires=self.now + 7200),
        })
        with patch.object(self.monitor.bulk_service, "create_selection") as select:
            self._scan()
        self.assertFalse(select.called)
        self.assertEqual(self.queued_upload.call_args.args[1], "existing")

    def test_missing_local_at_closes_pending_retry_when_no_other_account_is_due(self):
        account_id = self._seed_account("missing@example.test")
        self.remote_list.return_value = [remote("existing", "missing@example.test")]
        self._scan()
        row = self.store.list_repairs(self.backend)[0]
        row.update(stage="refresh_retry", next_attempt_at=self.now, last_code="c2a_refresh_token_unchanged")
        self.store.save_repairs(self.backend, [row])
        records.patch_row(records.ACCOUNTS, account_id, changes={"access_token": ""})
        self._scan(continuation_only=True)
        self.assertFalse(self.store.has_pending(self.backend))
        self.assertEqual(self.store.list_repairs(self.backend)[0]["last_code"], "c2a_local_at_missing")

    def test_confirmed_token_conflict_keeps_target_closed_for_the_same_local_at(self):
        self._seed_account("conflict@example.test", fresh=True)
        self.remote_list.return_value = [remote("original", "conflict@example.test", access_token_issued_at=self.now - 1800)]
        self._scan()
        job = self.store.list_repairs(self.backend)[0]["targets"]["original"]
        runtime.finish_run(job["run_id"], status="failed", result_summary={"cause_code": "c2a_remote_token_conflict"})
        result = self._scan()
        self.assertEqual(result["reasons"], {"c2a_remote_token_conflict": 1})
        row = self.store.list_repairs(self.backend)[0]
        self.assertEqual(row["stage"], "done")
        with patch.object(self.monitor.time, "time", return_value=row["next_attempt_at"] + 1):
            self._scan()
        self.assertEqual(self.queued_upload.call_count, 1)

    def test_cycle_limit_is_shared_by_refresh_and_upload(self):
        previous = self._seed_account("previous@example.test")
        self.remote_list.return_value = [remote("previous", "previous@example.test")]
        self._scan()
        row = self.store.list_repairs(self.backend)[0]
        row.update(stage="refresh_retry", next_attempt_at=self.now)
        self.store.save_repairs(self.backend, [row])
        self._seed_account("fresh@example.test", fresh=True)
        self.remote_list.return_value.append(remote("fresh", "fresh@example.test", access_token_issued_at=self.now - 1800))
        with patch.object(config, "C2A_MONITOR_MAX_PER_CYCLE", 1), patch.object(
            self.monitor.bulk_service, "create_selection", wraps=self.monitor.bulk_service.create_selection,
        ) as select:
            self._scan()
            self.assertEqual(select.call_count, 1)
            self.assertEqual(select.call_args.args[0]["source"]["ids"], [previous])
            self.assertFalse(self.queued_upload.called)

    def test_parallel_scan_does_not_report_an_empty_success(self):
        with self.store.scan_lock(self.backend) as acquired:
            self.assertTrue(acquired)
            result = self._scan()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "c2a_scan_in_progress")
        self.assertFalse(self.remote_list.called)

    def test_uncertain_local_submission_reuses_intent_after_cancellation(self):
        self._seed_account("resume@example.test", fresh=True)
        self.remote_list.return_value = [remote("original", "resume@example.test", access_token_issued_at=self.now - 1800)]
        context = Mock()
        context.checkpoint.side_effect = [None, task_gateway.OperationCancelled("合成取消")]
        with self.assertRaises(task_gateway.OperationCancelled):
            self._scan(context=context)
        self.assertFalse(self.queued_upload.called)
        target = self.store.list_repairs(self.backend)[0]["targets"]["original"]
        self.assertTrue(target["key"])
        self._scan(continuation_only=True)
        self.assertEqual(self.queued_upload.call_args.kwargs["idempotency_key"], target["key"])

    def test_backend_change_after_listing_preserves_existing_intents(self):
        self._seed_account("bound@example.test", fresh=True)
        self.remote_list.return_value = [remote("original", "bound@example.test", access_token_issued_at=self.now - 1800)]
        self._scan()
        before = self.store.list_repairs(self.backend)
        with patch.object(client, "configured_backend_identity", return_value="b" * 64):
            result = self._scan()
        self.assertEqual(result["error_code"], "c2a_backend_changed")
        self.assertEqual(self.store.list_repairs(self.backend), before)
        self.assertEqual(self.queued_upload.call_count, 1)
