"""付费邮箱的配置、提交与入口契约；所有供应商 HTTP 均为模拟。"""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import config
from config import email as cfg
from config import register as register_cfg
from config.env_loader import SECRET_ENV_KEYS
from config.schema import CONFIG_SCHEMA, build_non_sensitive_snapshot, resolve_config
from core import registration_service
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class PaidMailConfigurationTests(unittest.TestCase):
    def test_sources_and_secret_fields_share_schema_and_package_exports(self):
        resolved = resolve_config({"EMAIL_SOURCE": "MAILCODE,XIGUA"}, strict=True)
        self.assertEqual(resolved["EMAIL_SOURCE"].value, "mailcode,xigua")
        for key in ("MAILCODE_API_KEY", "XIGUA_API_KEY"):
            self.assertTrue(CONFIG_SCHEMA[key].secret)
            self.assertIn(key, SECRET_ENV_KEYS)
            self.assertIn(key, config.__all__)
            self.assertTrue(hasattr(config, key))
            self.assertNotIn("private-test-key", json.dumps(dict(build_non_sensitive_snapshot({key: "private-test-key"}).values)))
        self.assertNotIn("MAILCODE_API_BASE", CONFIG_SCHEMA)

    def test_registration_root_owner_is_passed_for_both_paid_sources(self):
        for source in ("mailcode", "xigua"):
            with self.subTest(source=source), patch.object(cfg, "USE_EMAIL_SERVICE", True), patch.object(register_cfg, "REGISTER_EMAIL", ""), patch.object(register_cfg, "REGISTER_NAME", "Test User"), patch("core.email_provider.acquire_email", return_value="paid@example.test") as acquire:
                result = registration_service._prepare_registration_args(source, owner_kind="registration_root", owner_id=42, acquisition_id="registration:42")
            self.assertEqual(result[0], "paid@example.test")
            self.assertEqual(acquire.call_args.kwargs["owner_id"], 42)
            self.assertEqual(acquire.call_args.kwargs["acquisition_id"], "registration:42")

    def test_cli_passes_stable_identity_for_both_paid_sources(self):
        import main
        for source in ("mailcode", "xigua"):
            with self.subTest(source=source), patch.object(main, "REGISTER_EMAIL", ""), patch.object(main, "REGISTER_NAME", "Test User"), patch.object(cfg, "USE_EMAIL_SERVICE", True), patch.object(main, "acquire_email", return_value="paid@example.test") as acquire:
                main.prepare_registration_inputs(email_source=source, owner_kind="cli", owner_id="batch:1", acquisition_id="batch:1")
            acquire.assert_called_once_with(source, owner_kind="cli", owner_id="batch:1", acquisition_id="batch:1")

    def test_email_change_passes_existing_run_acquisition(self):
        from core.email_change_service import _acquire_email_change_target
        context = SimpleNamespace(checkpoint=lambda: None, task_id=37, run={"data": {"remail_acquisition_id": "change:37"}})
        for source in ("mailcode", "xigua"):
            with self.subTest(source=source), patch("core.email_provider.acquire_email", return_value="new@example.test") as acquire, patch("core.db.get_account_by_email", return_value=None), patch("core.email_derivation.store.find_allocation", side_effect=AssertionError("付费订单来源不能查询派生地址账本")):
                target, result = _acquire_email_change_target(context, account_id=1, source=source, current_email="old@example.test")
            self.assertEqual(target, "new@example.test")
            self.assertIsNone(result)
            acquire.assert_called_once_with(source, owner_kind="email_change", owner_id=37, acquisition_id="change:37")


class PaidMailWebUiTests(PostgresTestCase):
    def setUp(self):
        for key, value in {"USE_EMAIL_SERVICE": True, "EMAIL_SOURCE": "mailcode,xigua",
                           "MAILCODE_API_KEY": "private-test-key", "MAILCODE_PRODUCT_ID": "product-test",
                           "XIGUA_API_KEY": "private-test-key", "XIGUA_API_BASE": "https://xigua.example.test",
                           "XIGUA_OFFER_ID": "offer-test"}.items():
            self.enterContext(patch.object(cfg, key, value))
        self.enterContext(patch("requests.sessions.Session.request", side_effect=AssertionError("禁止真实供应商调用")))
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    def test_source_readiness_is_local_and_enabled_in_order(self):
        response = self.client.get("/api/email-sources")
        self.assertEqual(response.status_code, 200)
        sources = response.get_json()["sources"]
        self.assertEqual([source["value"] for source in sources], ["mailcode", "xigua"])
        self.assertTrue(all(source["enabled"] for source in sources))
        self.assertNotIn("private-test-key", response.get_data(as_text=True))

    def test_missing_secret_disables_source_and_rejects_before_job_submission(self):
        for source, key in (("mailcode", "MAILCODE_API_KEY"), ("xigua", "XIGUA_API_KEY")):
            with self.subTest(source=source), patch.object(cfg, key, ""), patch("webui.app.svc.submit_registration") as submit:
                response = self.client.post("/api/jobs", json={"count": 1, "workers": 1, "email_source": source})
            self.assertEqual(response.status_code, 400)
            submit.assert_not_called()

    def test_jobs_submit_without_reading_outlook_inventory(self):
        for source in ("mailcode", "xigua"):
            with self.subTest(source=source), patch("webui.app.svc.submit_registration", return_value=[{"id": 1}]) as submit:
                response = self.client.post("/api/jobs", json={"count": 2, "workers": 2, "email_source": source})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["warning"], "")
            submit.assert_called_once_with(count=2, workers=2, email_source=source)

    def test_dashboard_renders_paid_sources_as_on_demand(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        sources = {row["source"]: row for row in response.get_json()["email"]["sources"]}
        for name in ("mailcode", "xigua"):
            self.assertEqual(sources[name]["kind"], "on_demand")
            self.assertTrue(sources[name]["enabled"])
        self.assertNotIn("private-test-key", response.get_data(as_text=True))

    def test_catalog_is_retired_without_querying_remote_products_or_wallet(self):
        with patch("core.mailcode_client.list_products", return_value=[{"id": "product-test", "stock": 10}]) as products, patch("core.mailcode_client.get_wallet", return_value={"balance": "123"}) as wallet, patch("core.mailcode_client.pick_account") as purchase:
            response = self.client.get("/api/mailcode/catalog")
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.get_json()["reason_code"], "email_management_managed_by_service")
        products.assert_not_called()
        wallet.assert_not_called()
        purchase.assert_not_called()
