"""独立协议入口的持久意图、执行互斥与凭据恢复契约。"""
from unittest.mock import patch
import errno
import socket

from core import registration_service as service
from core.registration.standalone import run_protocol_in_context
from core.storage import registration, registration_standalone
from tests.support_pg import PostgresTestCase


class ProtocolStandaloneTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.email = f"standalone-{self._testMethodName}@example.test"
        self.original = service.registration_fact_context()
        for key in self.original:
            setattr(service._THREAD_CTX, key, None)
        self.addCleanup(self._restore_context)

    def _restore_context(self):
        for key, value in self.original.items():
            setattr(service._THREAD_CTX, key, value)

    def _save_password(self, state="started"):
        facts = service.registration_fact_context()
        registration.save_password_checkpoint(
            facts["attempt_id"], email=self.email, password="fixture-original-password",
            state=state, run_id=facts["run_id"], execution_id=facts["execution_id"],
        )
        return facts

    def test_exception_after_submission_keeps_same_attempt_and_original_password(self):
        seen = []

        def disconnected(**kwargs):
            seen.append(self._save_password())
            raise TimeoutError("合成提交无响应")

        with self.assertRaises(TimeoutError):
            run_protocol_in_context(disconnected, {"email": self.email, "name": "Fixture"})
        first = seen[0]
        self.assertEqual(registration.get_run(first["run_id"])["status"], "request_unknown")
        self.assertTrue(all(value is None for value in service.registration_fact_context().values()))

        def resume(**kwargs):
            self.assertEqual(kwargs["existing_password"], "fixture-original-password")
            self.assertEqual(service.registration_fact_context()["attempt_id"], first["attempt_id"])
            return {"status": "request_unknown", "registration_success": False}

        run_protocol_in_context(resume, {"email": self.email, "name": "Fixture"})
        self.assertEqual(len(registration.list_runs(first["attempt_id"])), 2)
        self.assertNotIn("private_context", registration.get_attempt(first["attempt_id"]))

    def test_prepared_password_is_reused_without_claiming_remote_confirmation(self):
        def prepare(**kwargs):
            self._save_password("prepared")
            raise RuntimeError("合成提交前中断")

        with self.assertRaises(RuntimeError):
            run_protocol_in_context(prepare, {"email": self.email})
        attempt = registration_standalone.prepare_attempt(self.email)
        self.assertIsNone(attempt.get("account_id"))
        self.assertEqual(registration.list_runs(attempt["id"])[0]["status"], "interrupted")

        def resume(**kwargs):
            self.assertEqual(kwargs["existing_password"], "fixture-original-password")
            return {"status": "failed", "registration_success": False}

        run_protocol_in_context(resume, {"email": self.email})
        self.assertEqual(registration.list_runs(attempt["id"])[0]["status"], "failed")

    def test_active_run_cannot_be_stolen(self):
        attempt = registration_standalone.prepare_attempt(self.email)
        run = registration.start_run(attempt["id"], execution_id="other-execution", initial_status="running")
        with patch("core.registration.standalone.uuid.uuid4", return_value="new-execution"), self.assertRaisesRegex(RuntimeError, "活动执行"):
            run_protocol_in_context(lambda **kwargs: self.fail("不应调用驱动"), {"email": self.email})
        self.assertEqual(registration.get_run(run["id"])["status"], "running")

    def test_existing_web_task_chain_is_not_replaced_by_cli(self):
        original = registration.create_attempt(self.email, driver="protocol")
        with self.assertRaisesRegex(RuntimeError, "原任务"):
            run_protocol_in_context(lambda **kwargs: self.fail("不应调用驱动"), {"email": self.email})
        self.assertEqual(registration.list_runs(original["id"]), [])

    def test_existing_complete_context_does_not_create_another_attempt(self):
        for key, value in {"attempt_id": 11, "run_id": 12, "execution_id": "fixture", "job_id": 13}.items():
            setattr(service._THREAD_CTX, key, value)
        expected = {"registration_success": True}
        with patch.object(registration_standalone, "prepare_attempt") as prepare:
            self.assertIs(run_protocol_in_context(lambda **kwargs: expected, {"email": self.email}), expected)
        prepare.assert_not_called()

    def test_partial_context_fails_before_driver_and_db_mutation(self):
        service._THREAD_CTX.job_id = 13
        with patch.object(registration_standalone, "prepare_attempt") as prepare, self.assertRaisesRegex(RuntimeError, "不完整"):
            run_protocol_in_context(lambda **kwargs: self.fail("不应调用驱动"), {"email": self.email})
        prepare.assert_not_called()

    def test_success_closes_run_and_blocks_second_registration(self):
        def success(**kwargs):
            facts = service.registration_fact_context()
            registration.persist_core_account(
                facts["attempt_id"], access_token="fixture-access-token",
                account={"email": self.email}, run_id=facts["run_id"], execution_id=facts["execution_id"],
            )
            return {"registration_success": True, "postprocess_success": True}

        run_protocol_in_context(success, {"email": self.email})
        with self.assertRaisesRegex(RuntimeError, "核心账号已保存"):
            run_protocol_in_context(success, {"email": self.email})

    def _start_old_cli_run(self, *, state="started", host=None, pid=812345, data=None):
        attempt = registration_standalone.prepare_attempt(self.email)
        run = registration.start_run(
            attempt["id"], execution_id="old-cli", worker_pid=pid, initial_status="running",
            data=data if data is not None else {"entrypoint": "protocol_cli", "worker_host": host or socket.gethostname()},
        )
        if state:
            registration.save_password_checkpoint(
                attempt["id"], email=self.email, password="fixture-original-password", state=state,
                run_id=run["id"], execution_id="old-cli",
            )
        return attempt, run

    def test_dead_local_cli_run_recovers_only_same_attempt_and_reuses_password(self):
        attempt, run = self._start_old_cli_run()
        other = registration_standalone.prepare_attempt("other-" + self.email)
        other_run = registration.start_run(other["id"], execution_id="other-cli", worker_pid=912345, initial_status="running",
            data={"entrypoint": "protocol_cli", "worker_host": socket.gethostname()})
        def resume(**kwargs):
            self.assertEqual(kwargs["existing_password"], "fixture-original-password")
            self.assertEqual(service.registration_fact_context()["attempt_id"], attempt["id"])
            return {"registration_success": False, "request_unknown": True}
        with patch.object(registration_standalone.os, "kill", side_effect=ProcessLookupError(errno.ESRCH, "旧进程已退出")) as probe, patch.object(registration, "recover_interrupted_runs") as global_recovery:
            run_protocol_in_context(resume, {"email": self.email})
        probe.assert_called_once_with(812345, 0)
        global_recovery.assert_not_called()
        self.assertEqual(registration.get_run(run["id"])["status"], "request_unknown")
        self.assertEqual(registration.get_run(other_run["id"])["status"], "running")
        self.assertEqual(len(registration.list_runs(attempt["id"])), 2)

    def test_dead_prepared_run_stays_interrupted_and_does_not_claim_submission(self):
        attempt, run = self._start_old_cli_run(state="prepared")
        with patch.object(registration_standalone.os, "kill", side_effect=ProcessLookupError(errno.ESRCH, "已退出")):
            registration_standalone.prepare_attempt(self.email)
        self.assertEqual(registration.get_run(run["id"])["status"], "interrupted")
        self.assertEqual(registration.get_attempt(attempt["id"])["remote_account_state"], "not_started")

    def test_live_pid_or_permission_denied_does_not_allow_takeover(self):
        _, run = self._start_old_cli_run()
        for error in (None, PermissionError(errno.EPERM, "无法确认 PID")):
            with self.subTest(error=type(error).__name__), patch.object(registration_standalone.os, "kill", side_effect=error), self.assertRaisesRegex(RuntimeError, "活动执行"):
                run_protocol_in_context(lambda **kwargs: self.fail("不应抢占驱动"), {"email": self.email})
        self.assertEqual(registration.get_run(run["id"])["status"], "running")

    def test_foreign_host_or_legacy_owner_is_never_recovered_by_local_pid(self):
        _, run = self._start_old_cli_run(host="foreign-worker-host")
        with patch.object(registration_standalone.os, "kill") as probe, self.assertRaisesRegex(RuntimeError, "活动执行"):
            run_protocol_in_context(lambda **kwargs: self.fail("不应抢占驱动"), {"email": self.email})
        probe.assert_not_called()
        self.assertEqual(registration.get_run(run["id"])["status"], "running")

    def test_cli_native_run_traffic_scope_is_created_and_reset(self):
        from core import protocol_traffic, task_run_log
        before = task_run_log.current_context()
        outer_traffic = protocol_traffic._CORRELATION.get()
        def inspect_scope(**kwargs):
            facts = service.registration_fact_context()
            capture = protocol_traffic.ProtocolTrafficCapture.for_current_context()
            self.assertIsNotNone(capture)
            self.assertEqual(capture.correlation["registration_attempt_id"], facts["attempt_id"])
            self.assertEqual(capture.correlation["registration_run_id"], facts["run_id"])
            self.assertNotIn("operation_run_id", capture.correlation)
            self.assertNotIn("operation_task_id", capture.correlation)
            self.assertEqual(task_run_log.current_context()["stage"], "registration")
            return {"registration_success": False}
        with task_run_log.stage_context("legacy", task_id=911, run_id=922), protocol_traffic.correlation_context(operation_task_id=911, operation_run_id=922, purpose="legacy"):
            previous_log = task_run_log.current_context()
            previous_traffic = dict(protocol_traffic._CORRELATION.get())
            run_protocol_in_context(inspect_scope, {"email": self.email})
            self.assertEqual(task_run_log.current_context(), previous_log)
            self.assertEqual(protocol_traffic._CORRELATION.get(), previous_traffic)
        self.assertEqual(task_run_log.current_context(), before)
        self.assertEqual(protocol_traffic._CORRELATION.get(), outer_traffic)

    def test_stop_after_submission_keeps_original_password_and_unknown_run(self):
        seen = []
        def stopped(**kwargs):
            seen.append(self._save_password())
            raise service.StopRequested("合成用户停止")
        with self.assertRaises(service.StopRequested):
            run_protocol_in_context(stopped, {"email": self.email})
        self.assertEqual(registration.get_run(seen[0]["run_id"])["status"], "request_unknown")
        self.assertEqual(registration.get_private_resume_context(seen[0]["attempt_id"], email=self.email)["password"], "fixture-original-password")
        self.assertTrue(all(value is None for value in service.registration_fact_context().values()))

    def test_finish_failure_preserves_driver_exception_and_clears_scopes(self):
        from core import protocol_traffic, task_run_log
        original = TimeoutError("合成原始提交异常")
        def disconnected(**kwargs):
            self._save_password()
            raise original
        before = task_run_log.current_context()
        with patch.object(registration, "finish_run", side_effect=RuntimeError("合成写入失败")), self.assertRaises(TimeoutError) as raised:
            run_protocol_in_context(disconnected, {"email": self.email})
        self.assertIs(raised.exception, original)
        self.assertTrue(all(value is None for value in service.registration_fact_context().values()))
        self.assertEqual(task_run_log.current_context(), before)
        self.assertIsNone(protocol_traffic._CORRELATION.get())

    def test_dead_cli_with_saved_core_closes_run_and_never_repeats_driver(self):
        attempt, run = self._start_old_cli_run()
        registration.persist_core_account(
            attempt["id"], access_token="fixture-access-token", account={"email": self.email},
            run_id=run["id"], execution_id="old-cli",
        )
        with patch.object(registration_standalone.os, "kill", side_effect=ProcessLookupError(errno.ESRCH, "已退出")), self.assertRaisesRegex(RuntimeError, "核心账号已保存"):
            run_protocol_in_context(lambda **kwargs: self.fail("已有核心账号不能再次注册"), {"email": self.email})
        self.assertEqual(registration.get_run(run["id"])["status"], "partial_success")
        self.assertTrue(registration.get_run(run["id"])["result_summary"]["registration_success"])
        self.assertEqual(len(registration.list_runs(attempt["id"])), 1)
        self.assertEqual(registration.get_attempt(attempt["id"])["local_account_state"], "persisted")

    def test_stop_after_core_saved_keeps_partial_success(self):
        seen = []
        def stop_postprocess(**kwargs):
            facts = self._save_password("confirmed")
            seen.append(facts)
            registration.persist_core_account(
                facts["attempt_id"], access_token="fixture-access-token", account={"email": self.email},
                run_id=facts["run_id"], execution_id=facts["execution_id"],
            )
            raise service.StopRequested("合成后处理停止")
        with self.assertRaises(service.StopRequested):
            run_protocol_in_context(stop_postprocess, {"email": self.email})
        self.assertEqual(registration.get_run(seen[0]["run_id"])["status"], "partial_success")
        self.assertTrue(registration.get_run(seen[0]["run_id"])["result_summary"]["registration_success"])
        self.assertEqual(registration.get_attempt(seen[0]["attempt_id"])["local_account_state"], "persisted")

    def test_reported_partial_without_core_does_not_claim_registration_success(self):
        run_protocol_in_context(lambda **kwargs: {"status": "partial_success", "registration_success": False}, {"email": self.email})
        attempt = registration_standalone.prepare_attempt(self.email)
        self.assertFalse(registration.list_runs(attempt["id"])[0]["result_summary"]["registration_success"])
