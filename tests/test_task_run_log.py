# -*- coding: utf-8 -*-
import unittest


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


if __name__ == "__main__":
    unittest.main()
