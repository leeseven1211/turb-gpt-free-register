"""注册派发只选择可能有容量的候选，最终容量仍由数据库原子准入裁决。"""
from __future__ import annotations

import os
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

from core.operations import concurrency
from core.registration import admission
from core.storage import postgres, runtime_config
from core.storage.operations import permits
from tests.support_pg import PostgresTestCase


class RegistrationDispatchCapacityTests(PostgresTestCase):
    def setUp(self):
        key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        key.start()
        self.addCleanup(key.stop)
        self.contexts = []
        self.addCleanup(self._release_all)
        permits.ensure_tables()

    def _release_all(self):
        for context in self.contexts:
            concurrency.release_execution(context)

    def policy(self, **updates):
        from config.concurrency import policy_values

        values = policy_values({})
        values.update(updates)
        runtime_config.write_values(
            {key: str(value) for key, value in values.items()}, activate=True, source="test",
        )

    def job(self, job_id, *, batch="批次甲", workers=10, driver="protocol_oss_2", attempt=None, account=None):
        job = {
            "id": job_id,
            "status": "pending",
            "job_type": "registration",
            "batch_id": batch,
            "batch_key": f"registration:{batch}",
            "batch_workers": workers,
            "attempt_id": attempt or f"attempt-{job_id}",
            "config_snapshot": {"registration_driver": driver},
            "task_type": "registration_proto2" if driver == "protocol_oss_2" else "registration_roxy",
        }
        if account is not None:
            job["account_id"] = account
        return job

    def hold(self, job):
        scopes = [{"kind": "registration_attempt", "key": job["attempt_id"], "limit": 1}]
        if job.get("account_id") is not None:
            scopes.append({
                "kind": "account", "key": f"{job['account_id']}:openai_interactive", "limit": 1,
            })
        result = concurrency.try_admit_and_claim(
            execution_key=f"registration_job:{job['id']}", task_type=job["task_type"],
            batch_key=job["batch_key"], batch_limit=job["batch_workers"], extra_scopes=scopes,
            claim=lambda _conn, execution_id: {"id": job["id"], "execution_id": execution_id},
        )
        self.assertTrue(result.admitted, result.blocked_by)
        self.contexts.append(result.context)
        return result.context

    def test_large_batch_selects_ten_without_admission_lock_or_queue_writes(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=10)
        jobs = [self.job(index) for index in range(1, 132)]
        with patch.object(permits, "admission_lock", side_effect=AssertionError("预筛不应抢准入锁")):
            chosen = admission.dispatch_candidates(jobs, limit=100)
        self.assertEqual(list(range(1, 11)), [job["id"] for job in chosen])
        with postgres.connect() as conn, conn.cursor() as cur:
            for table in ("operation_execution_permits", "operation_execution_requests"):
                cur.execute(f"SELECT count(*) FROM {postgres.qualified(table)}")
                self.assertEqual(0, cur.fetchone()[0], table)
        self.assertTrue(all(job["status"] == "pending" for job in jobs))

    def test_configured_thirty_workers_are_not_capped_at_sixteen(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=30)
        jobs = [self.job(index, workers=30) for index in range(1, 61)]
        chosen = admission.dispatch_candidates(jobs, limit=100)
        self.assertEqual(list(range(1, 31)), [job["id"] for job in chosen])

    def test_full_batch_does_not_dispatch_until_a_permit_is_released(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=10)
        active = [self.hold(self.job(index)) for index in range(1, 11)]
        waiting = [self.job(index) for index in range(11, 132)]
        with patch.object(permits, "admission_lock", side_effect=AssertionError("满额候选不应争锁")):
            self.assertEqual([], admission.dispatch_candidates(waiting, limit=100))
        concurrency.release_execution(active[-1])
        self.assertEqual([11], [job["id"] for job in admission.dispatch_candidates(waiting, limit=100)])

    def test_in_flight_candidates_reserve_capacity_across_dispatch_passes(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=10)
        jobs = [self.job(index) for index in range(1, 132)]
        chosen = admission.dispatch_candidates(jobs, in_flight=jobs[:6], limit=100)
        self.assertEqual([7, 8, 9, 10], [job["id"] for job in chosen])
        self.assertEqual([], admission.dispatch_candidates(jobs, in_flight=jobs[:10], limit=100))

    def test_admitted_in_flight_candidates_are_not_counted_twice(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=10)
        jobs = [self.job(index) for index in range(1, 132)]
        for job in jobs[:4]:
            self.hold(job)
        chosen = admission.dispatch_candidates(jobs, in_flight=jobs[:6], limit=100)
        self.assertEqual([7, 8, 9, 10], [job["id"] for job in chosen])

    def test_busy_attempt_or_account_does_not_hide_a_free_candidate(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=10)
        self.hold(self.job(100, batch="已执行", attempt="共享尝试", account=42))
        jobs = [
            self.job(1, attempt="共享尝试"),
            self.job(2, account=42),
            self.job(3),
        ]
        self.assertEqual([3], [job["id"] for job in admission.dispatch_candidates(jobs, limit=1)])

    def test_in_flight_attempt_and_account_are_reserved_before_admission(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=10)
        in_flight = [self.job(100, batch="已提交", attempt="共享尝试", account=42)]
        jobs = [self.job(1, attempt="共享尝试"), self.job(2, account=42), self.job(3)]
        chosen = admission.dispatch_candidates(jobs, in_flight=in_flight, limit=1)
        self.assertEqual([3], [job["id"] for job in chosen])

    def test_driver_and_batch_caps_allow_other_eligible_candidates(self):
        self.policy(GLOBAL_TASK_WORKERS=10, REGISTRATION_ROXY_WORKERS=2, REGISTRATION_PROTO2_WORKERS=3)
        jobs = [
            self.job(1, batch="浏览器甲", driver="roxy", workers=1),
            self.job(2, batch="浏览器甲", driver="roxy", workers=1),
            self.job(3, batch="浏览器乙", driver="roxy", workers=4),
            self.job(4, batch="协议甲", workers=2),
            self.job(5, batch="协议甲", workers=2),
            self.job(6, batch="协议甲", workers=2),
            self.job(7, batch="协议乙", workers=2),
            self.job(8, batch="协议乙", workers=2),
        ]
        self.assertEqual([1, 3, 4, 5, 7], [job["id"] for job in admission.dispatch_candidates(jobs, limit=10)])

    def test_global_and_local_submission_caps_are_both_respected(self):
        self.policy(GLOBAL_TASK_WORKERS=2, REGISTRATION_PROTO2_WORKERS=10)
        jobs = [self.job(index, batch=f"批次{index}") for index in range(1, 6)]
        self.assertEqual([1, 2], [job["id"] for job in admission.dispatch_candidates(jobs, limit=100)])
        self.assertEqual([1], [job["id"] for job in admission.dispatch_candidates(jobs, limit=1)])
        self.assertEqual([], admission.dispatch_candidates(jobs, limit=0))

    def test_capacity_hints_follow_policy_increases_and_draining(self):
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=2)
        active = [self.hold(self.job(index)) for index in (1, 2)]
        waiting = [self.job(index) for index in range(3, 8)]
        self.assertEqual([], admission.dispatch_candidates(waiting, limit=100))
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=4)
        self.assertEqual([3, 4], [job["id"] for job in admission.dispatch_candidates(waiting, limit=100)])
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=1)
        self.assertEqual([], admission.dispatch_candidates(waiting, limit=100))
        for context in active:
            concurrency.release_execution(context)
        self.assertEqual([3], [job["id"] for job in admission.dispatch_candidates(waiting, limit=100)])

    def test_migration_required_keeps_candidates_pending(self):
        runtime_config.write_values({"ACCOUNT_BATCH_WORKERS": "7"}, activate=True, source="test")
        job = self.job(1)
        self.assertEqual([], admission.dispatch_candidates([job], limit=100))
        self.assertEqual("pending", job["status"])
        self.policy(GLOBAL_TASK_WORKERS=100, REGISTRATION_PROTO2_WORKERS=10)
        self.assertEqual([job], admission.dispatch_candidates([job], limit=100))

    def test_capacity_hint_cannot_bypass_a_later_atomic_admission_check(self):
        self.policy(GLOBAL_TASK_WORKERS=1, REGISTRATION_PROTO2_WORKERS=10)
        candidate = self.job(1)
        self.assertEqual([candidate], admission.dispatch_candidates([candidate], limit=100))
        self.hold(self.job(2))
        claim = Mock(return_value={"id": candidate["id"]})
        result = concurrency.try_admit_and_claim(
            execution_key="registration_job:1", task_type="registration_proto2", claim=claim,
            batch_key=candidate["batch_key"], batch_limit=candidate["batch_workers"],
        )
        self.assertFalse(result.admitted)
        self.assertIn("global_capacity", result.blocked_by)
        claim.assert_not_called()
