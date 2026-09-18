# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TaskRunLogRedactionTests(unittest.TestCase):
    def test_private_auth_identifiers_and_credentials_do_not_enter_run_log(self):
        from core import task_run_log

        scrubbed = task_run_log.scrub({
            "device_id": "private-device-id",
            "oai_session_id": "private-session-id",
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
