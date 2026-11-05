"""并发配置、显式迁移与只读状态接口契约。"""
from contextlib import contextmanager
import copy
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Flask

import config
from config import env_loader, runtime, schema
from config.concurrency import POLICY_KEYS, WORKER_KEYS, migration_preview, policy_values
from webui import config_editor
from webui.routes.config import create_config_blueprint


class ConcurrencyConfigTests(unittest.TestCase):
    def test_all_execution_limits_accept_positive_integers_without_arbitrary_ceiling(self):
        values = {key: 1000000 for key in WORKER_KEYS}
        self.assertEqual(values, schema.validate_config_updates(values))
        for key in WORKER_KEYS:
            field = schema.CONFIG_SCHEMA[key]
            self.assertEqual({"min": 1}, field.range)
            self.assertEqual("config.concurrency", field.module)
            self.assertEqual("并发控制", field.group)
            self.assertFalse(field.restart)
        for invalid in (0, -1, True, None, 1.5, "1.5", "abc"):
            with self.subTest(invalid=invalid), self.assertRaises(schema.ConfigValidationError):
                policy_values({"GLOBAL_TASK_WORKERS": invalid})

    def test_legacy_key_reading_survives_but_writing_reports_migration(self):
        self.assertEqual(9, schema.validate_value("ACCOUNT_BATCH_WORKERS", "9"))
        with self.assertRaises(schema.ConfigValidationError) as caught:
            schema.validate_config_updates({"ACCOUNT_BATCH_WORKERS": 9})
        self.assertEqual("concurrency_config_migrated", caught.exception.code)
        self.assertIn("并发控制", caught.exception.errors["ACCOUNT_BATCH_WORKERS"])

    def test_preview_never_reinterprets_legacy_account_limit_as_global(self):
        source = {"ACCOUNT_BATCH_WORKERS": "17"}
        before = dict(source)
        preview = migration_preview(source)
        self.assertTrue(preview["migration_required"])
        self.assertEqual(3, preview["proposed_values"]["GLOBAL_TASK_WORKERS"])
        self.assertEqual(17, preview["proposed_values"]["ACCOUNT_PLAN_CHECK_WORKERS"])
        self.assertEqual(3, preview["proposed_values"]["REGISTRATION_ROXY_WORKERS"])
        self.assertEqual(1, preview["proposed_values"]["EMAIL_IMPORT_WORKERS"])
        self.assertEqual(before, source)
        self.assertEqual(set(POLICY_KEYS), set(preview["required_keys"]))
        self.assertFalse(migration_preview(None)["migration_required"])

    def test_new_policy_values_do_not_depend_on_legacy_pool(self):
        policy = policy_values({"GLOBAL_TASK_WORKERS": "5", "ACCOUNT_PLAN_CHECK_WORKERS": "11", "ACCOUNT_BATCH_WORKERS": "1"})
        self.assertEqual(5, policy["GLOBAL_TASK_WORKERS"])
        self.assertEqual(11, policy["ACCOUNT_PLAN_CHECK_WORKERS"])
        self.assertEqual(3, policy["ACCOUNT_TOKEN_REFRESH_WORKERS"])
        self.assertNotIn("ACCOUNT_BATCH_WORKERS", policy)

    def test_remote_sub2api_account_attribute_is_distinct_from_local_workers(self):
        field = schema.CONFIG_SCHEMA["SUB2API_UPLOAD_CONCURRENCY"]
        self.assertEqual("Codex", field.group)
        self.assertIn("远端调度属性", field.help)
        self.assertNotIn("SUB2API_UPLOAD_CONCURRENCY", WORKER_KEYS)


class _Repository:
    def __init__(self):
        self.values = {"ACCOUNT_BATCH_WORKERS": "8", "PROXY_POOL": "[]"}
        self.commit_error = False

    def read_values(self):
        return copy.deepcopy(self.values)

    def write_values(self, updates, **_kwargs):
        self.values.update(updates)
        return list(updates)

    @contextmanager
    def transaction(self):
        before = dict(self.values)
        try:
            yield object()
            if self.commit_error:
                raise RuntimeError("测试事务提交失败")
        except BaseException:
            self.values = before
            raise


class ConcurrencyMigrationSaveTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / ".env"
        self.path.write_text("WEBUI_AUTH_CODE=fixture\n", encoding="utf-8")
        self.repository = _Repository()
        for context in (
            patch.object(env_loader, "_ENV_PATH", self.path),
            patch.object(runtime, "_repository", return_value=self.repository),
            patch.object(runtime, "_automatic_database_allowed", return_value=True),
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", "DATABASE_URL": "fixture"}),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
            patch("core.operations.task_gateway.notify_dispatch"),
        ):
            context.start()
            self.addCleanup(context.stop)
        runtime.reset_cache()
        self.addCleanup(runtime.reset_cache)
        self.addCleanup(config.reload_all)

    def test_partial_first_save_is_rejected_without_publishing_or_writing(self):
        config.reload_all()
        before = schema.non_sensitive_snapshot()
        old_values = dict(self.repository.values)
        with self.assertRaises(schema.ConfigValidationError) as caught:
            config_editor.update_config({"GLOBAL_TASK_WORKERS": 7})
        self.assertEqual("concurrency_policy_migration_required", caught.exception.code)
        self.assertEqual(old_values, self.repository.values)
        self.assertIs(before, schema.non_sensitive_snapshot())

    def test_complete_save_applies_once_then_partial_updates_are_allowed(self):
        proposed = config_editor.get_concurrency_migration_preview()["proposed_values"]
        proposed["GLOBAL_TASK_WORKERS"] = 10
        old_file = self.path.read_bytes()
        result = config_editor.update_config(proposed)
        self.assertEqual(set(POLICY_KEYS), set(result["database_updated"]))
        self.assertEqual("1", self.repository.values["CONCURRENCY_POLICY_REVISION"])
        self.assertEqual(10, schema.non_sensitive_snapshot()["GLOBAL_TASK_WORKERS"])
        self.assertEqual("8", self.repository.values["ACCOUNT_BATCH_WORKERS"])
        self.assertEqual(old_file, self.path.read_bytes())
        config_editor.update_config({"ACCOUNT_PLAN_CHECK_WORKERS": 20})
        self.assertEqual("20", self.repository.values["ACCOUNT_PLAN_CHECK_WORKERS"])

    def test_commit_failure_restores_whole_policy_and_published_snapshot(self):
        config.reload_all()
        before = schema.non_sensitive_snapshot()
        self.repository.commit_error = True
        with self.assertRaisesRegex(RuntimeError, "提交失败"):
            config_editor.update_config(migration_preview(self.repository.values)["proposed_values"])
        self.assertNotIn("CONCURRENCY_POLICY_REVISION", self.repository.values)
        self.assertNotIn("GLOBAL_TASK_WORKERS", self.repository.values)
        self.assertIs(before, schema.non_sensitive_snapshot())


class ConcurrencyConfigRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(create_config_blueprint(SimpleNamespace(logger=logging.getLogger(__name__))))
        self.client = app.test_client()

    def test_old_client_gets_explicit_migration_code_and_field(self):
        with patch("webui.config_editor.update_config", side_effect=schema.ConfigValidationError({
            "ACCOUNT_BATCH_WORKERS": "请迁移并发策略",
        }, code="concurrency_config_migrated")):
            response = self.client.post("/api/config", json={"updates": {"ACCOUNT_BATCH_WORKERS": 7}})
        self.assertEqual(400, response.status_code)
        self.assertEqual("concurrency_config_migrated", response.json["error_code"])
        self.assertIn("ACCOUNT_BATCH_WORKERS", response.json["fields"])

    def test_preview_is_read_only_and_contains_only_concurrency_fields(self):
        preview = migration_preview({"ACCOUNT_BATCH_WORKERS": "9", "SMS_API_KEY": "fixture-secret"})
        with patch("webui.config_editor.get_concurrency_migration_preview", return_value=preview), patch(
            "webui.config_editor.update_config"
        ) as update:
            response = self.client.get("/api/config/concurrency-preview")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json["migration_required"])
        self.assertNotIn("fixture-secret", response.get_data(as_text=True))
        update.assert_not_called()

    def test_status_projects_owner_counts_and_explicitly_requests_optional_details(self):
        status = {"scope": "test_fixture", "policy_revision": "fixture", "observed_at": "2026-11-05",
                  "global": {"limit": 4, "occupied": 10, "reserved": 1, "executing": 7,
                             "cleaning": 1, "debug_hold": 1, "draining": True}, "types": []}
        with patch("core.operations.concurrency.get_concurrency_status", return_value=status) as query:
            response = self.client.get("/api/operations/concurrency?details=1")
        query.assert_called_once_with(include_details=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(status["global"], response.json["global"])
        self.assertTrue(response.json["ok"])

    def test_store_unavailable_is_classified_without_exposing_raw_details(self):
        from core.operations.concurrency import ConcurrencyStoreUnavailable

        with patch("core.operations.concurrency.get_concurrency_status", side_effect=ConcurrencyStoreUnavailable("fixture-private")):
            response = self.client.get("/api/operations/concurrency")
        self.assertEqual(503, response.status_code)
        self.assertEqual("scheduler_store_unavailable", response.json["error_code"])
        self.assertNotIn("fixture-private", response.get_data(as_text=True))
