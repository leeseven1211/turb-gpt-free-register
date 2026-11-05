"""注册批次、CLI 与兼容入口共用 PostgreSQL 执行许可。"""
from __future__ import annotations

import multiprocessing
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

from core import db
from core.operations import concurrency, run_log
from core.registration import admission, service, standalone
from core.storage import registration, runtime_config
from core.storage.operations import permits
from tests.support_pg import PostgresTestCase


def _cli_hold_last_slot(start, stop, results):
    start.wait(10)
    admitted = admission.try_admit_cli(batch_id="cli-shared-budget", index=1, batch_workers=5, driver="roxy")
    results.put(admitted.admitted)
    stop.wait(10)
    if admitted.context is not None:
        concurrency.release_execution(admitted.context)


class RegistrationConcurrencyTests(PostgresTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log_root = patch.object(run_log, "_LOG_ROOT", Path(self.temp.name))
        self.log_root.start()
        self.addCleanup(self.log_root.stop)
        self.task_log_root = patch.object(run_log, "_TASK_LOG_ROOT", Path(self.temp.name) / "tasks")
        self.task_log_root.start()
        self.addCleanup(self.task_log_root.stop)
        self.encryption = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.encryption.start()
        self.addCleanup(self.encryption.stop)
        self.contexts = []
        self.addCleanup(self._release_contexts)
        self.facts = service.registration_fact_context()
        for key in self.facts:
            setattr(service._THREAD_CTX, key, None)
        self.addCleanup(self._restore_facts)
        permits.ensure_tables()
        self.policy(GLOBAL_TASK_WORKERS=4, REGISTRATION_ROXY_WORKERS=4)

    def _release_contexts(self):
        for context in self.contexts:
            concurrency.release_execution(context)

    def _restore_facts(self):
        for key, value in self.facts.items():
            setattr(service._THREAD_CTX, key, value)

    def policy(self, **updates):
        from config.concurrency import policy_values

        values = policy_values({})
        values.update(updates)
        runtime_config.write_values({key: str(value) for key, value in values.items()}, activate=True, source="test")

    def job(self, batch="first", workers=3, driver="roxy", **kwargs):
        return db.create_job(
            "outlook", batch_id=batch, batch_workers=workers,
            data={"config_snapshot": {"registration_driver": driver}}, **kwargs,
        )

    def admit(self, job):
        result = admission.try_admit_job(job)
        if result.context is not None:
            self.contexts.append(result.context)
        return result

    def test_workers_three_and_five_share_global_type_and_batch_limits(self):
        first = [self.job("three", 3) for _ in range(4)]
        second = [self.job("five", 5) for _ in range(6)]
        for job in first[:3]:
            self.assertTrue(self.admit(job))
        self.assertIn("batch_capacity", self.admit(first[3]).blocked_by)
        self.assertTrue(self.admit(second[0]))
        self.assertIn("global_capacity", self.admit(second[1]).blocked_by)
        self.assertEqual("pending", db.get_job(second[1]["id"])["status"])
        self.assertEqual(4, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_roxy_and_proto2_have_independent_type_limits(self):
        self.policy(GLOBAL_TASK_WORKERS=3, REGISTRATION_ROXY_WORKERS=1, REGISTRATION_PROTO2_WORKERS=2)
        self.assertTrue(self.admit(self.job("roxy-one", driver="roxy")))
        self.assertIn("type_capacity", self.admit(self.job("roxy-two", driver="roxy")).blocked_by)
        self.assertTrue(self.admit(self.job("proto-one", driver="protocol_oss_2")))
        self.assertTrue(self.admit(self.job("proto-two", driver="protocol_oss_2")))
        self.assertEqual(3, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_cli_process_and_webui_jobs_share_one_last_slot(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        job = self.job()
        process_context = multiprocessing.get_context("spawn")
        start, stop, results = process_context.Event(), process_context.Event(), process_context.Queue()
        process = process_context.Process(target=_cli_hold_last_slot, args=(start, stop, results))
        try:
            process.start()
            start.set()
            self.assertTrue(results.get(timeout=20))
            self.assertIn("global_capacity", self.admit(job).blocked_by)
            self.assertEqual("pending", db.get_job(job["id"])["status"])
        finally:
            stop.set()
            process.join(timeout=15)
            if process.is_alive():
                process.terminate()
                process.join(timeout=3)
        self.assertEqual(0, process.exitcode)
        self.assertTrue(self.admit(job))

    def test_global_one_inline_standalone_reuses_claim_and_execution_identity(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        job = self.job()
        seen = []

        def execute():
            service._activate_job(job["id"])
            try:
                service._ensure_registration_run_context(db.get_job(job["id"]))
                facts = service.registration_fact_context()
                result = standalone.run_registration_in_context(
                    lambda **_kwargs: seen.append(concurrency.current_execution().execution_id) or {"success": True},
                    {"email": "inline@example.test"}, driver_name="roxy",
                )
                self.assertTrue(result["success"])
                self.assertEqual(facts["execution_id"], seen[0])
                self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
            finally:
                service._deactivate_job(job["id"])

        with patch.object(db, "claim_job_for_execution", wraps=db.claim_job_for_execution) as claim, \
                patch.object(concurrency, "try_admit_and_claim", wraps=concurrency.try_admit_and_claim) as admit:
            admission.run_job(job["id"], execute)
        self.assertEqual(1, claim.call_count)
        self.assertIn("conn", claim.call_args.kwargs)
        self.assertEqual(1, admit.call_count)
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_cancelled_job_is_never_claimed_or_given_a_permit(self):
        job = self.job()
        self.assertTrue(db.transition_job_status(job["id"], ("pending",), "cancelled"))
        result = self.admit(job)
        self.assertFalse(result)
        self.assertEqual("cancelled", db.get_job(job["id"])["status"])
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_terminal_job_keeps_permit_and_attempt_mutex_through_cleanup(self):
        first = self.job()
        context = self.admit(first).context
        db.update_job(first["id"], status="failed", completed_at=service._now_iso())
        child, _ = db.create_retry_job(first["id"], job_type="registration", email_source="outlook", batch_workers=3)
        with concurrency.execution_scope(context):
            admission.mark_execution_state("cleaning")
            blocked = self.admit(child)
            self.assertIn("resource_capacity", blocked.blocked_by)
            self.assertEqual(1, concurrency.get_concurrency_status()["global"]["cleaning"])
        concurrency.release_execution(context)
        self.assertTrue(self.admit(child))

    def test_startup_recovery_preserves_owned_job_and_run_but_interrupts_legacy_queue(self):
        active = self.job("active")
        context = self.admit(active).context
        service._THREAD_CTX.job_id = active["id"]
        run = service._ensure_registration_run_context(db.get_job(active["id"]))
        service._THREAD_CTX.job_id = None
        queued = self.job("legacy")
        self.assertEqual(1, db.recover_interrupted_registration_jobs())
        self.assertEqual("running", db.get_job(active["id"])["status"])
        self.assertEqual("running", registration.get_run(run["run_id"])["status"])
        self.assertEqual("interrupted", db.get_job(queued["id"])["status"])
        self.assertTrue(concurrency.validate_execution(context))

    def test_executor_rejection_does_not_claim_or_fail_persisted_job(self):
        job = self.job()
        pool = Mock()
        pool.available_slots.return_value = 1
        pool.try_submit.side_effect = RuntimeError("测试执行器拒绝提交")
        with patch.object(service, "get_executor", return_value=pool), \
                patch.object(db, "claim_job_for_execution", wraps=db.claim_job_for_execution) as claim:
            self.assertEqual(0, service.dispatch_pending_once())
        claim.assert_not_called()
        self.assertEqual("pending", db.get_job(job["id"])["status"])
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_composite_legacy_twofa_and_codex_retry_use_actual_action_classes(self):
        self.assertEqual("account_setup_retry", admission.registration_admission_class({"job_type": "twofa_retry"}))
        self.assertEqual("twofa_setup", admission.registration_admission_class({"job_type": "twofa_setup"}))
        self.assertEqual("codex_retry", admission.registration_admission_class({"job_type": "codex_retry"}))

    def test_cli_releases_only_after_proxy_cleanup(self):
        import main

        events = []
        lease = Mock(proxy_url="http://proxy.invalid")

        def cleanup(_lease, **_kwargs):
            self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
            self.assertIsNotNone(concurrency.current_execution())
            events.append("proxy_cleaned")

        with patch("core.proxy.provider.acquire_registration_proxy", return_value=lease), \
                patch("core.proxy.provider.release_proxy", side_effect=cleanup), \
                patch.object(main, "prepare_registration_inputs", return_value=("cli@example.test", "Fixture", "1990-01-01")), \
                patch.object(main, "run_registration", return_value={"success": True}):
            result = main.run_one_batch_item(0, 1, "cleanup-order", registration_options={"registration_driver": "roxy"})
        self.assertTrue(result["success"])
        self.assertEqual(["proxy_cleaned"], events)
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])
