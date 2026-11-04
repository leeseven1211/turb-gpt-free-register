"""历史收码诊断更正不得改写执行状态、恢复事实和旧审计。"""
from __future__ import annotations

import json
from copy import deepcopy

from core.storage import postgres as pg, records, registration
from tests.support_pg import PostgresTestCase


class RegistrationDiagnosticCorrectionTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()
        self.diagnostics = {
            "operation": "mailbox_wait", "failure_kind": "no_mail",
            "failure_stage": "email_otp", "last_confirmed_stage": "password",
            "otp_received": False, "profile_confirmed": False,
        }
        self.evidence = {
            "source": "verified_task_log", "event_type": "mailbox_timeout", "wait_seconds": 120,
        }

    def _fixture(self, *, status="failed", cause="protocol_failure_evidence_missing"):
        message = "request_unknown: 协议失败未保留足够请求证据，无法确认具体原因"
        job_id = records.insert_row(records.JOBS, {
            "job_uuid": "diagnostic-correction", "email": "fixture@example.test",
            "job_type": "registration", "status": "failed", "error_message": message,
            "completed_at": "2026-11-03T15:06:36+00:00", "duration_ms": 142000,
            "progress_stage": "complete", "log_file": "保留原日志路径",
            "progress_steps": {"email_otp": {
                "state": "failed", "detail": message, "duration_ms": 120000,
                "started_at": "2026-11-03T15:04:36+00:00",
                "completed_at": "2026-11-03T15:06:36+00:00",
                "transitions": [{"state": "failed", "detail": "原始历史消息"}],
            }},
        })
        attempt = registration.ensure_attempt_for_job(job_id)
        run = registration.start_run(
            attempt["id"], job_id=job_id, execution_id="保留执行标识",
            initial_status=status, historical=True,
            started_at="2026-11-03T15:04:14+00:00",
            completed_at=None if status == "running" else "2026-11-03T15:06:36+00:00",
            error_code="request_unknown", error_message=message,
            result_summary={"cause_code": cause, "outcome": "request_unknown",
                            "register_response_confirmed": True, "retained_fact": "原值"},
        )
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {pg.qualified('registration_attempts')} SET private_context=%s::jsonb WHERE id=%s",
                (json.dumps({"password": "原恢复密码", "submission_facts": [{"phase": "unknown"}]}), attempt["id"]),
            )
        from core.operation_task_store import sync_registration_job

        sync_registration_job(job_id)
        return job_id, attempt["id"], run["id"]

    def _snapshot(self, job_id, attempt_id, run_id):
        with registration._connect() as conn, conn.cursor() as cur:
            result = {}
            for key, table, row_id in (("run", "registration_runs", run_id),
                                       ("attempt", "registration_attempts", attempt_id),
                                       ("job", "registration_jobs", job_id)):
                cur.execute(f"SELECT * FROM {pg.qualified(table)} WHERE id=%s", (row_id,))
                result[key] = dict(cur.fetchone())
            cur.execute(f"SELECT * FROM {pg.qualified('registration_events')} ORDER BY id")
            result["events"] = [dict(row) for row in cur.fetchall()]
            cur.execute(
                f"SELECT id, task_id, status, started_at, completed_at, duration_ms "
                f"FROM {pg.qualified('operation_runs')} WHERE source_system='registration_jobs' AND source_id=%s",
                (str(job_id),),
            )
            result["operation_execution"] = dict(cur.fetchone())
            return result

    def _correct(self, run_id, **kwargs):
        correct = getattr(registration, "correct_run_failure_diagnostics", None)
        self.assertTrue(callable(correct), "缺少只更正历史诊断的业务存储方法")
        return correct(run_id, registration_diagnostics=kwargs.get("diagnostics", self.diagnostics),
                       evidence=kwargs.get("evidence", self.evidence))

    def test_correction_preserves_all_execution_and_recovery_facts(self):
        ids = self._fixture()
        before = self._snapshot(*ids)
        updated = self._correct(ids[2])
        after = self._snapshot(*ids)
        self.assertEqual(updated["id"], ids[2])
        expected = deepcopy(before)
        message = "request_unknown: email_otp_no_mail: 等待窗口内未收到验证码邮件"
        expected["run"]["error_message"] = message
        expected["run"]["result_summary"].update(
            cause_code="email_otp_no_mail", registration_diagnostics=self.diagnostics,
        )
        expected["job"]["data"]["error_message"] = message
        expected["job"]["data"]["progress_steps"]["email_otp"]["detail"] = message
        self.assertEqual(expected["run"], after["run"])
        self.assertEqual(expected["job"], after["job"])
        self.assertEqual(before["attempt"], after["attempt"])
        self.assertEqual(before["operation_execution"], after["operation_execution"])
        self.assertEqual(before["events"], after["events"][:-1])
        audit = after["events"][-1]
        self.assertEqual("diagnostic.corrected", audit["event_type"])
        self.assertEqual(self.evidence, audit["detail"]["evidence"])
        with registration._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT error_code FROM {pg.qualified('operation_runs')} WHERE source_system='registration_jobs' AND source_id=%s", (str(ids[0]),))
            self.assertEqual("email_otp_no_mail", cur.fetchone()["error_code"])

    def test_running_run_is_rejected_without_any_change(self):
        ids = self._fixture(status="running")
        before = self._snapshot(*ids)
        with self.assertRaises(ValueError):
            self._correct(ids[2])
        self.assertEqual(before, self._snapshot(*ids))

    def test_unknown_diagnostic_is_not_enough_to_claim_no_mail(self):
        ids = self._fixture()
        before = self._snapshot(*ids)
        with self.assertRaises(ValueError):
            self._correct(ids[2], diagnostics={**self.diagnostics, "operation": "other", "failure_kind": "unknown"})
        self.assertEqual(before, self._snapshot(*ids))

    def test_evidence_rejects_missing_invalid_or_arbitrary_fields(self):
        ids = self._fixture()
        before = self._snapshot(*ids)
        for evidence in ({}, {**self.evidence, "source": "猜测"},
                         {**self.evidence, "wait_seconds": True},
                         {**self.evidence, "body": "不得传播的正文"}):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self._correct(ids[2], evidence=evidence)
        self.assertEqual(before, self._snapshot(*ids))

    def test_specific_existing_cause_is_not_overwritten(self):
        ids = self._fixture(cause="protocol_post_otp_transport_failed")
        before = self._snapshot(*ids)
        with self.assertRaises(ValueError):
            self._correct(ids[2])
        self.assertEqual(before, self._snapshot(*ids))

    def test_successful_linked_job_is_not_rewritten(self):
        ids = self._fixture()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_jobs')} SET status='success' WHERE id=%s", (ids[0],))
        before = self._snapshot(*ids)
        with self.assertRaises(ValueError):
            self._correct(ids[2])
        self.assertEqual(before, self._snapshot(*ids))

    def test_existing_received_code_evidence_prevents_timeout_correction(self):
        ids = self._fixture()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {pg.qualified('registration_runs')} SET result_summary=result_summary || %s::jsonb WHERE id=%s",
                (json.dumps({"registration_diagnostics": {
                    "operation": "otp_validate", "failure_kind": "transport_error", "otp_received": True,
                }}), ids[2]),
            )
        before = self._snapshot(*ids)
        with self.assertRaises(ValueError):
            self._correct(ids[2])
        self.assertEqual(before, self._snapshot(*ids))

    def test_new_diagnostic_cannot_claim_no_mail_after_a_code_or_http_response(self):
        ids = self._fixture()
        before = self._snapshot(*ids)
        for extra in ({"otp_received": True}, {"profile_confirmed": True},
                      {"http_status": 401}, {"last_confirmed_stage": "email_otp"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self._correct(ids[2], diagnostics={**self.diagnostics, **extra})
        self.assertEqual(before, self._snapshot(*ids))

    def test_plain_failed_run_keeps_its_error_prefix_and_sanitizes_extra_fields(self):
        ids = self._fixture(status="failed")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_runs')} SET error_message='旧失败文案' WHERE id=%s", (ids[2],))
        updated = self._correct(ids[2], diagnostics={**self.diagnostics, "raw_response": "不得保存的正文"})
        self.assertEqual("email_otp_no_mail: 等待窗口内未收到验证码邮件", updated["error_message"])
        self.assertEqual("failed", updated["status"])
        self.assertNotIn("raw_response", updated["result_summary"]["registration_diagnostics"])
