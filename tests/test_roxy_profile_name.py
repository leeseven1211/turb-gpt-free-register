# -*- coding: utf-8 -*-
"""账号详情读取最新可用 Roxy Profile 名称的回归测试。"""
from __future__ import annotations

import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from core.roxybrowser_client import RoxyBrowserClient
from webui import runtime
from webui.routes.accounts import create_accounts_blueprint


class RoxyProfileNameTests(unittest.TestCase):
    def test_modern_account_detail_refreshes_latest_profile_name(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "webui/static/js/modern/accounts.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Roxy Profile 名称", source)
        self.assertIn(
            "/api/accounts/${encodeURIComponent(account.id)}/roxy-profile",
            source,
        )

    def test_client_returns_window_name_from_active_profile(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        with patch.object(
            client,
            "_find_active_profile_by_id",
            return_value={"dirId": "profile-1", "windowName": "rb-current-1234"},
        ):
            self.assertEqual("rb-current-1234", client.get_active_profile_name("profile-1"))

    def test_account_route_returns_only_latest_usable_profile_name(self):
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
        with (
            patch("webui.routes.accounts.db.get_account", return_value=account),
            patch("core.roxybrowser_client.RoxyBrowserClient") as client_cls,
        ):
            client_cls.return_value.get_active_profile_name.return_value = "rb-current-1234"
            response = app.test_client().get("/api/accounts/1940/roxy-profile")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"ok": True, "profile_name": "rb-current-1234"},
            response.get_json(),
        )
        client_cls.return_value.get_active_profile_name.assert_called_once_with("profile-1")
