# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TaskRunLogRedactionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
