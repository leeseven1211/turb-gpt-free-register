# -*- coding: utf-8 -*-
"""账号详情读取最后一次 Roxy Profile ID 的回归测试。"""
from __future__ import annotations

import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from webui import runtime
from webui.routes.accounts import create_accounts_blueprint


class RoxyProfileNameTests(unittest.TestCase):
    def test_modern_account_detail_refreshes_last_profile_id(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "webui/static/js/modern/accounts.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Roxy Profile ID", source)
        self.assertIn(
            "/api/accounts/${encodeURIComponent(account.id)}/roxy-profile",
            source,
        )
        self.assertIn("account.roxy_profile_id = String(result.profile_id || '').trim()", source)

    def test_recent_fingerprint_section_exposes_roxy_profile_id(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "webui/static/js/modern/accounts.js"
        ).read_text(encoding="utf-8")
        fingerprint_section = source[
            source.index("function _accountDetailFingerprintMarkup"):
            source.index("function _accountDetailRoxyProfileState")
        ]

        self.assertIn("_accountDetailRoxyProfileState(r)", fingerprint_section)

    def test_account_route_returns_last_profile_id_without_active_profile_lookup(self):
        app = Flask("roxy-profile-name")
        app.register_blueprint(
            create_accounts_blueprint(
                runtime.WebUIContext(app, logging.getLogger("roxy-profile-name")),
            )
        )
        account = {
            "id": 1940,
            "email": "account@example.test",
            "extra_json": {
                "roxybrowser": {
                    "profile_id": "profile-1",
                    "retained": True,
                },
            },
        }
        with patch("webui.routes.accounts.db.get_account", return_value=account):
            response = app.test_client().get("/api/accounts/1940/roxy-profile")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"ok": True, "profile_id": "profile-1"},
            response.get_json(),
        )
