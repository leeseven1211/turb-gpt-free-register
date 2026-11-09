# -*- coding: utf-8 -*-
"""批量复制字段遵循已保存账号状态，不依赖当前分页。"""
from __future__ import annotations

import unittest


class AccountCopyValueTests(unittest.TestCase):
    def test_email_uses_saved_value_and_trims_whitespace(self):
        from webui.route_helpers import _account_secret_value

        self.assertEqual(_account_secret_value({"email": "  account@example.test\n"}, "email"), "account@example.test")
        self.assertEqual(_account_secret_value({}, "email"), "")

    def test_extract_link_requires_explicit_success_and_prefers_long_url(self):
        from webui.route_helpers import _account_secret_value

        for evidence in ({"extract_link_status": "SUCCESS"}, {"extract_link_ok": True}):
            with self.subTest(evidence=evidence):
                row = {**evidence, "extract_link_long_url": "  https://example.test/long\n", "extract_link_copy_paste": "fallback"}
                self.assertEqual(_account_secret_value(row, "extract_link"), "https://example.test/long")
                row["extract_link_long_url"] = ""
                self.assertEqual(_account_secret_value(row, "extract_link"), "fallback")
                row.pop("extract_link_copy_paste")
                self.assertEqual(_account_secret_value(row, "extract_link"), "")

    def test_stale_link_is_not_copied_when_current_result_is_not_successful(self):
        from webui.route_helpers import _account_secret_value

        for status in (None, "", "queued", "running", "failed"):
            for ok in (None, False, "true", 1):
                with self.subTest(status=status, ok=ok):
                    row = {"extract_link_status": status, "extract_link_ok": ok, "extract_link_long_url": "https://example.test/stale"}
                    self.assertEqual(_account_secret_value(row, "extract_link"), "")

    def test_existing_fields_keep_their_copy_format_and_unknown_fields_are_rejected(self):
        from webui.route_helpers import _account_secret_value

        row = {"email": "account@example.test", "access_token": " token ", "copy_line": "existing-line", "totp_secret": "secret", "extra_json": {"account_password": "password"}}
        for field, expected in (("access_token", " token "), ("copy_line", "existing-line"), ("totp_secret", "secret"), ("account_password", "password"), ("account_password_line", "account@example.test----password")):
            with self.subTest(field=field):
                self.assertEqual(_account_secret_value(row, field), expected)
        with self.assertRaisesRegex(ValueError, "email/extract_link"):
            _account_secret_value(row, "unsupported")
