# -*- coding: utf-8 -*-
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TaskRunLogRedactionTests(unittest.TestCase):
    def test_context_stage_and_event_associations_are_written(self):
        from core import task_run_log

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            path = root / "run.jsonl"
            with patch.object(task_run_log, "_LOG_ROOT", root), task_run_log.stage_context(
                    "network", task_id=11, run_id=22,
                    event_uuid="event-uuid", source_event_id=33,
                    source_system="native_operations", main_step_id=44,
            ):
                self.assertTrue(task_run_log.append(path, level="INFO", message="线路已就绪"))
            row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual("network", row["stage"])
        self.assertEqual(11, row["task_id"])
        self.assertEqual(22, row["run_id"])
        self.assertEqual("event-uuid", row["event_uuid"])
        self.assertEqual(33, row["source_event_id"])
        self.assertEqual("native_operations", row["source_system"])
        self.assertEqual(44, row["main_step_id"])

    def test_handler_reads_current_stage_for_reused_worker_scope(self):
        from core import task_run_log

        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "run.jsonl"
            with patch.object(task_run_log, "_LOG_ROOT", Path(tempdir)):
                handler = task_run_log.TaskRunLogHandler(path, task_id=1, run_id=2, stage="runtime")
                logger = logging.getLogger("task-run-log-context-test")
                logger.setLevel(logging.INFO)
                logger.propagate = False
                logger.addHandler(handler)
                try:
                    with task_run_log.stage_context("network", task_id=1, run_id=2):
                        logger.info("network event")
                    with task_run_log.stage_context("browser", task_id=1, run_id=2):
                        logger.info("browser event")
                finally:
                    logger.removeHandler(handler)
                    handler.close()
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(["network", "browser"], [row["stage"] for row in rows])

    def test_nested_reporter_does_not_replace_outer_run_identity(self):
        from core import task_run_log
        from core.task_reporter import TaskReporter

        with patch("core.task_reporter.task_gateway.append_event", return_value=None):
            with task_run_log.stage_context("registration", task_id=10, run_id=20):
                TaskReporter(99).stage("plan_check", "running", "子任务开始")
                context = task_run_log.current_context()

        self.assertEqual(10, context["task_id"])
        self.assertEqual(20, context["run_id"])
        self.assertEqual("plan_check", context["stage"])

    def test_native_report_binds_database_id_when_row_uses_id_key(self):
        from core import task_run_log
        from core.operation_runtime import CancellationToken, operation_context, report_stage

        token = CancellationToken(run_id=20, token="cancel-token", checker=lambda *_: False)
        with task_run_log.stage_context("preflight", task_id=10, run_id=20):
            with operation_context(token, reporter=lambda **_: {"id": 77, "event_uuid": "event-77"}):
                report_stage("network", "线路已就绪", state="success")
            context = task_run_log.current_context()

        self.assertEqual(77, context["event_id"])
        self.assertEqual("event-77", context["event_uuid"])

    def test_historical_chinese_otp_and_auth_session_are_redacted_on_read(self):
        from core import task_run_log

        fake_code = "731842"
        fake_session = "fake-session-context-731842"
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            path = root / "tasks" / "example" / "run.jsonl"
            path.parent.mkdir(parents=True)
            rows = [
                {"message": f"[步骤10] 提交邮箱验证码: {fake_code}"},
                {"message": f"[Roxy注册][OTP] 收到验证码：{fake_code}"},
                {"message": "[步骤10] 验证响应摘要: " + json.dumps({
                    "page": {"type": "about_you"},
                    "oai-client-auth-session": {"context": fake_session},
                })},
                {"message": f"oai-client-auth-session：{fake_session}"},
                {"message": f"oai-client-auth-session：prefix\n{fake_session}"},
            ]
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            with patch.object(task_run_log, "_LOG_ROOT", root):
                result = task_run_log.read_incremental(path)

        rendered = json.dumps(result["items"], ensure_ascii=False)
        self.assertNotIn(fake_code, rendered)
        self.assertNotIn(fake_session, rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_private_auth_identifiers_and_credentials_do_not_enter_run_log(self):
        from core import task_run_log

        scrubbed = task_run_log.scrub({
            "device_id": "private-device-id",
            "oai_session_id": "private-session-id",
            "oai-client-auth-session": "private-auth-session-context",
            "datadog_trace_id": "private-trace-id",
            "session_identifiers": {"sentinel_sid": "nested-private-sid"},
            "cookie": "private-cookie",
            "access_token": "private-token",
            "proxy_url": "http://user:proxy-password@example.test:8080",
            "safe": "ok",
        })
        text = task_run_log.redact_text(
            "device_id=private-device-id oai_session_id=private-session-id "
            "token=private-token cookie=private-cookie "
            "proxy=http://user:proxy-password@example.test:8080"
        )

        for value in (
            "private-device-id", "private-session-id", "private-trace-id",
            "nested-private-sid", "private-cookie", "private-token", "proxy-password",
            "private-auth-session-context",
        ):
            self.assertNotIn(value, repr(scrubbed))
            self.assertNotIn(value, text)
        self.assertEqual("ok", scrubbed["safe"])
        self.assertIn("http://***@example.test:8080", text)

    def test_legacy_registration_log_path_writes_under_shared_logs_root(self):
        from core import task_run_log

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir) / "logs"
            legacy_root = Path(tempdir) / "注册日志"
            old_path = legacy_root / "tasks" / "job-1" / "run.jsonl"
            with (
                patch.object(task_run_log, "_LOG_ROOT", root),
                patch.object(task_run_log, "_LEGACY_LOG_ROOT", legacy_root),
            ):
                task_run_log.append(
                    old_path,
                    level="INFO",
                    message="legacy path",
                )

            self.assertTrue((root / "tasks" / "job-1" / "run.jsonl").exists())
            self.assertFalse(old_path.exists())

    def test_explicit_new_event_does_not_inherit_another_event_identity(self):
        from core import task_run_log
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with patch.object(task_run_log, "_LOG_ROOT", root):
                with task_run_log.stage_context("network", task_id=1, run_id=2, event_id=7, event_uuid="old"):
                    path = root / "run.jsonl"
                    task_run_log.append(path, level="INFO", message="新的阶段事件", stage="network", event_uuid="new")
                    line = task_run_log.read_incremental(path)["items"][0]
                    self.assertNotIn("event_id", line)
                    self.assertEqual("new", line["event_uuid"])

    def test_switching_task_clears_previous_run_and_event_context(self):
        from core import task_run_log
        with task_run_log.stage_context("network", task_id=1, run_id=2, event_id=7):
            task_run_log.set_current_stage("network", task_id=3)
            self.assertNotIn("run_id", task_run_log.current_context())
            self.assertNotIn("event_id", task_run_log.current_context())

    def test_nested_reporter_does_not_bind_child_event_to_parent_log(self):
        from core import task_run_log
        from core.task_reporter import TaskReporter
        with patch("core.task_reporter.task_gateway.append_event", return_value={"id": 777, "event_uuid": "child-event"}):
            with task_run_log.stage_context("registration", task_id=10, run_id=20):
                TaskReporter(99).stage("plan_check", "running", "子任务开始")
                self.assertNotIn("event_id", task_run_log.current_context())
                self.assertNotIn("event_uuid", task_run_log.current_context())

    def test_nested_native_runs_do_not_copy_child_logs_into_parent_file(self):
        from types import SimpleNamespace
        from core import task_run_log
        from core.account_operation_executor import operation_log_context
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            parent_path, child_path = root / "parent.jsonl", root / "child.jsonl"
            parent = SimpleNamespace(task_id=1, run_id=2, run={"log_file": str(parent_path)})
            child = SimpleNamespace(task_id=3, run_id=4, run={"log_file": str(child_path)})
            with patch.object(task_run_log, "_LOG_ROOT", root):
                with operation_log_context(parent):
                    with operation_log_context(child):
                        logging.getLogger("nested-task-log-test").warning("子 Run 日志")
                    logging.getLogger("nested-task-log-test").warning("父 Run 日志")
                self.assertEqual(["父 Run 日志"], [line["message"] for line in task_run_log.read_incremental(parent_path)["items"]])
                self.assertEqual(["子 Run 日志"], [line["message"] for line in task_run_log.read_incremental(child_path)["items"]])


if __name__ == "__main__":
    unittest.main()
