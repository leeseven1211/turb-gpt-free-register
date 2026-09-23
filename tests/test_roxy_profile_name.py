# -*- coding: utf-8 -*-
"""账号详情读取最后一次 Roxy Profile 信息的回归测试。"""
from __future__ import annotations

import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from webui import runtime
from webui.routes.accounts import create_accounts_blueprint


class RoxyProfileNameTests(unittest.TestCase):
    def test_modern_account_detail_refreshes_profile_window_name_and_id(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "webui/static/js/modern/accounts.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Roxy Profile 窗口名称", source)
        self.assertIn(
            "/api/accounts/${encodeURIComponent(account.id)}/roxy-profile",
            source,
        )
        self.assertIn("account.roxy_profile_id = String(result.profile_id || '').trim()", source)
        self.assertIn("account.roxy_profile_name = String(result.window_name || '').trim()", source)

    def test_recent_fingerprint_section_exposes_roxy_profile_window_name(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "webui/static/js/modern/accounts.js"
        ).read_text(encoding="utf-8")
        fingerprint_section = source[
            source.index("function _accountDetailFingerprintMarkup"):
            source.index("function _accountDetailRoxyProfileState")
        ]

        self.assertIn("_accountDetailRoxyProfileState(r)", fingerprint_section)

    def test_account_route_returns_saved_profile_window_name_and_id(self):
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
                    "open_result": {
                        "data": {"windowName": "rb-1790150160878-77e2"},
                    },
                },
            },
        }
        with patch("webui.routes.accounts.db.get_account", return_value=account):
            response = app.test_client().get("/api/accounts/1940/roxy-profile")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "ok": True,
                "profile_id": "profile-1",
                "window_name": "rb-1790150160878-77e2",
            },
            response.get_json(),
        )

    def test_account_route_keeps_id_when_window_name_is_missing(self):
        app = Flask("roxy-profile-id-fallback")
        app.register_blueprint(
            create_accounts_blueprint(
                runtime.WebUIContext(app, logging.getLogger("roxy-profile-id-fallback")),
            )
        )
        account = {
            "id": 1940,
            "email": "account@example.test",
            "extra_json": {
                "roxybrowser": {
                    "profile_id": "profile-1",
                    "retained": False,
                },
            },
        }
        with patch("webui.routes.accounts.db.get_account", return_value=account):
            response = app.test_client().get("/api/accounts/1940/roxy-profile")

        self.assertEqual(
            {"ok": True, "profile_id": "profile-1", "window_name": ""},
            response.get_json(),
        )

    def test_account_route_falls_back_to_latest_auth_context_profile_id(self):
        app = Flask("roxy-profile-context")
        app.register_blueprint(
            create_accounts_blueprint(
                runtime.WebUIContext(app, logging.getLogger("roxy-profile-context")),
            )
        )
        account = {"id": 1940, "email": "account@example.test", "extra_json": {}}
        with (
            patch("webui.routes.accounts.db.get_account", return_value=account),
            patch(
                "core.storage.account_auth.latest_roxy_profile_id",
                return_value="context-profile",
            ),
        ):
            response = app.test_client().get("/api/accounts/1940/roxy-profile")

        self.assertEqual(
            {"ok": True, "profile_id": "context-profile", "window_name": ""},
            response.get_json(),
        )

    def test_last_profile_id_is_read_even_when_binding_is_not_reusable(self):
        from core.roxy_profile_binding import last_account_profile_id, last_account_profile_name

        account = {
            "extra_json": {
                "roxybrowser": {"profile_id": "deleted-profile", "retained": False},
            },
        }
        self.assertEqual("deleted-profile", last_account_profile_id(account))
        self.assertEqual(
            "direct-profile",
            last_account_profile_id({"roxybrowser": {"profile_id": "direct-profile"}}),
        )
        self.assertEqual(
            "rb-direct",
            last_account_profile_name({
                "roxybrowser": {
                    "profile_id": "direct-profile",
                    "open_result": {"windowName": "rb-direct"},
                },
            }),
        )

    def test_historical_backfill_only_fills_missing_display_ids(self):
        from core.roxy_profile_binding import backfill_account_profile_ids

        accounts = {
            "existing@example.test": {"extra_json": {"roxybrowser": {"profile_id": "old"}}},
            "missing@example.test": {"extra_json": {}},
        }
        with (
            patch("core.db.get_account_by_email", side_effect=accounts.get),
            patch("core.db.update_account_roxy_profile", return_value=True) as update,
        ):
            result = backfill_account_profile_ids({
                "existing@example.test": "newer",
                "missing@example.test": "profile-2",
                "unknown@example.test": "profile-3",
            })

        self.assertEqual(
            {
                "candidates": 3,
                "matched_accounts": 2,
                "already_recorded": 1,
                "updated": 1,
                "window_names_updated": 0,
                "missing_accounts": 1,
                "failed": 0,
            },
            result,
        )
        update.assert_called_once_with("missing@example.test", "profile-2", retained=False)

    def test_historical_backfill_fills_name_only_for_the_same_profile_id(self):
        from core.roxy_profile_binding import backfill_account_profile_ids

        accounts = {
            "same@example.test": {
                "extra_json": {"roxybrowser": {"profile_id": "profile-1"}},
            },
            "different@example.test": {
                "extra_json": {"roxybrowser": {"profile_id": "profile-other"}},
            },
        }
        with (
            patch("core.db.get_account_by_email", side_effect=accounts.get),
            patch("core.db.update_account_roxy_profile_window_name", return_value=True) as update_name,
        ):
            result = backfill_account_profile_ids({
                "same@example.test": {
                    "profile_id": "profile-1",
                    "window_name": "rb-same",
                },
                "different@example.test": {
                    "profile_id": "profile-1",
                    "window_name": "rb-wrong",
                },
            })

        self.assertEqual(1, result["window_names_updated"])
        update_name.assert_called_once_with("same@example.test", "rb-same")

    def test_history_backfill_route_returns_redacted_counts(self):
        app = Flask("roxy-profile-history")
        app.register_blueprint(
            create_accounts_blueprint(
                runtime.WebUIContext(app, logging.getLogger("roxy-profile-history")),
            )
        )
        with (
            patch(
                "core.roxy_profile_binding.load_historical_profile_bindings",
                return_value={
                    "account@example.test": {
                        "profile_id": "profile-1",
                        "window_name": "rb-history",
                    },
                },
            ),
            patch(
                "core.roxy_profile_binding.backfill_account_profile_ids",
                return_value={
                    "candidates": 1,
                    "matched_accounts": 1,
                    "already_recorded": 0,
                    "updated": 1,
                    "window_names_updated": 0,
                    "missing_accounts": 0,
                    "failed": 0,
                },
            ),
        ):
            response = app.test_client().post("/api/accounts/roxy-profile/backfill-history")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "ok": True,
                "source_profile_ids": 1,
                "candidates": 1,
                "matched_accounts": 1,
                "already_recorded": 0,
                "updated": 1,
                "window_names_updated": 0,
                "missing_accounts": 0,
                "failed": 0,
            },
            response.get_json(),
        )
