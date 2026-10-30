# -*- coding: utf-8 -*-
"""运行配置来源、持久化分流及失败恢复契约。"""
import copy
import os
import tempfile
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import config
from config import env_loader, schema
from webui import config_editor


class _Repository:
    def __init__(self, values=None):
        self.values = values
        self.commit_error = False

    def read_values(self):
        return copy.deepcopy(self.values)

    def write_values(self, updates, **kwargs):
        if self.values is None:
            raise AssertionError("不得隐式激活部分配置")
        self.values.update(updates)
        return list(updates)

    @contextmanager
    def transaction(self):
        before = copy.deepcopy(self.values)
        try:
            yield object()
            if self.commit_error:
                raise RuntimeError("测试提交失败")
        except BaseException:
            self.values = before
            raise


class RuntimeConfigLoadingTests(unittest.TestCase):
    def setUp(self):
        from config import runtime
        self.runtime = runtime
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / ".env"
        self.path.write_text('WEBUI_AUTH_CODE="bootstrap-code"\nACCOUNT_BATCH_WORKERS="2"\n', encoding="utf-8")
        self.repository = _Repository({"ACCOUNT_BATCH_WORKERS": "6", "PROXY_POOL": "[]"})
        for context in (
            patch.object(env_loader, "_ENV_PATH", self.path),
            patch.object(runtime, "_repository", return_value=self.repository),
            patch.object(runtime, "_automatic_database_allowed", return_value=True),
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", "DATABASE_URL": "fixture"}),
            patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.runtime.reset_cache()
        self.addCleanup(self.runtime.reset_cache)
        self.addCleanup(config.reload_all)

    def test_bootstrap_keys_and_unknown_runtime_keys_are_distinct(self):
        for key in ("DATABASE_URL", "WEBUI_AUTH_CODE", "TURB_CONFIG_ENCRYPTION_KEY", "TASK_RUN_LOG_ROOT", "NODE_EXECUTABLE"):
            self.assertTrue(self.runtime.is_bootstrap_key(key))
        self.assertFalse(self.runtime.is_bootstrap_key("EMAIL_DERIVATION_IMAP_SECRET_OLD"))
        self.assertFalse(self.runtime.is_bootstrap_key("UNKNOWN_LEGACY_RUNTIME_KEY"))

    def test_database_values_override_stale_environment_and_absence_restores_default(self):
        os.environ["ACCOUNT_BATCH_WORKERS"] = "3"
        os.environ["SMS_API_KEY"] = "stale-environment-secret"
        self.runtime.load_values(force=True)
        self.assertEqual("6", os.environ["ACCOUNT_BATCH_WORKERS"])
        self.assertNotIn("SMS_API_KEY", os.environ)
        self.assertEqual([], schema.resolve_config()["PROXY_POOL"].value)
        self.assertEqual("database", schema.resolve_config()["ACCOUNT_BATCH_WORKERS"].source)
        self.assertEqual("env", schema.resolve_config({"ACCOUNT_BATCH_WORKERS": "3"})["ACCOUNT_BATCH_WORKERS"].source)

    def test_active_database_read_failure_never_falls_back_to_file(self):
        self.runtime.load_values(force=True)
        with patch.object(self.repository, "read_values", side_effect=RuntimeError("config_key_missing")):
            with self.assertRaisesRegex(RuntimeError, "config_key_missing"):
                self.runtime.load_values(force=True)

    def test_dotenv_disabled_does_not_automatically_probe_database(self):
        with patch.object(self.runtime, "_automatic_database_allowed", return_value=False), patch.object(
            self.runtime, "_repository", side_effect=AssertionError("禁止自动连库")
        ):
            self.assertIsNone(self.runtime.load_values(force=True))

    def test_inactive_database_rejects_partial_runtime_activation(self):
        self.repository.values = None
        self.runtime.reset_cache()
        with self.assertRaisesRegex(RuntimeError, "迁移"):
            self.runtime.write_persisted_values({"ACCOUNT_BATCH_WORKERS": "5"})
        self.assertIsNone(self.repository.values)

    def test_missing_active_metadata_with_master_key_never_loads_legacy_values(self):
        self.repository.values = None
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": "fixture-deployment-key"}):
            with self.assertRaisesRegex(RuntimeError, "config_not_migrated"):
                self.runtime.load_values(force=True)

    def test_versioned_secret_uses_database_without_modifying_env(self):
        from core.email.derivation import _profile_credentials, _save_profile_secret
        before = self.path.read_bytes()
        reference = "EMAIL_DERIVATION_IMAP_SECRET_ORIGINAL"
        _save_profile_secret(reference, "fixture-original-secret")
        self.assertEqual("fixture-original-secret", self.repository.values[reference])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual("fixture-original-secret", _profile_credentials({
            "credential_ref": reference, "connector": "forward_imap", "inbox_locator": {},
            "id": 7, "inbox_key": "fixture", "revision": 1,
        })["password"])

    def test_secret_metadata_reports_database_source_without_exposing_value(self):
        self.repository.values["SMS_API_KEY"] = "fixture-provider-secret"
        self.runtime.load_values(force=True)
        config.reload_all()
        item = {field["key"]: field for field in schema.effective_config_metadata()}["SMS_API_KEY"]
        self.assertEqual("database", item["source"])
        self.assertEqual("database", item["configured_source"])
        self.assertEqual("database", item["storage"])
        self.assertTrue(item["configured"])
        self.assertEqual("", item["value"])
        self.assertNotIn("fixture-provider-secret", repr(item))

    def test_webui_save_updates_database_and_preserves_old_task_snapshot(self):
        self.runtime.load_values(force=True)
        config.reload_all()
        before_file = self.path.read_bytes()
        old_snapshot = schema.non_sensitive_snapshot()
        result = config_editor.update_config({"ACCOUNT_BATCH_WORKERS": 7})
        self.assertEqual("7", self.repository.values["ACCOUNT_BATCH_WORKERS"])
        self.assertEqual(before_file, self.path.read_bytes())
        self.assertEqual(6, old_snapshot["ACCOUNT_BATCH_WORKERS"])
        self.assertEqual(7, schema.non_sensitive_snapshot()["ACCOUNT_BATCH_WORKERS"])
        self.assertEqual([], result["env_updated"])
        self.assertEqual(["ACCOUNT_BATCH_WORKERS"], result["database_updated"])
        metadata = {item["key"]: item for item in schema.effective_config_metadata()}
        self.assertEqual("database", metadata["ACCOUNT_BATCH_WORKERS"]["storage"])
        self.assertEqual("database", metadata["ACCOUNT_BATCH_WORKERS"]["source"])

    def test_commit_failure_restores_database_environment_modules_snapshot_and_bootstrap(self):
        self.runtime.load_values(force=True)
        config.reload_all()
        old_snapshot = schema.non_sensitive_snapshot()
        old_environment = dict(os.environ)
        old_file = self.path.read_bytes()
        self.repository.commit_error = True
        with self.assertRaisesRegex(RuntimeError, "提交失败"):
            config_editor.update_config({"ACCOUNT_BATCH_WORKERS": 7, "WEBUI_AUTH_CODE": "new-code"})
        self.assertEqual("6", self.repository.values["ACCOUNT_BATCH_WORKERS"])
        self.assertEqual(old_environment, dict(os.environ))
        self.assertEqual(old_file, self.path.read_bytes())
        self.assertEqual(6, config.ACCOUNT_BATCH_WORKERS)
        self.assertIs(old_snapshot, schema.non_sensitive_snapshot())

    def test_reload_failure_rolls_back_staged_database_values(self):
        self.runtime.load_values(force=True)
        before_file = self.path.read_bytes()
        with patch.object(config, "reload_all", side_effect=RuntimeError("测试重载失败")):
            with self.assertRaisesRegex(RuntimeError, "重载失败"):
                config_editor.update_config({"ACCOUNT_BATCH_WORKERS": 7})
        self.assertEqual("6", self.repository.values["ACCOUNT_BATCH_WORKERS"])
        self.assertEqual("6", os.environ["ACCOUNT_BATCH_WORKERS"])
        self.assertEqual(before_file, self.path.read_bytes())

    def test_validation_refreshes_values_after_acquiring_database_lock(self):
        self.runtime.load_values(force=True)
        original_transaction = self.repository.transaction

        @contextmanager
        def concurrent_commit_before_lock():
            self.repository.values["ACCOUNT_BATCH_WORKERS"] = "9"
            with original_transaction() as conn:
                yield conn

        original_validate = config_editor.validate_config_updates

        def validate_latest(updates):
            self.assertEqual("9", os.environ["ACCOUNT_BATCH_WORKERS"])
            return original_validate(updates)

        with patch.object(self.repository, "transaction", concurrent_commit_before_lock), patch.object(
            config_editor, "validate_config_updates", side_effect=validate_latest
        ):
            config_editor.update_config({"REGISTER_NAME": "fixture-name"})
        self.assertEqual("9", self.repository.values["ACCOUNT_BATCH_WORKERS"])

    def test_snapshot_readers_only_see_committed_values_during_commit_gate(self):
        self.runtime.load_values(force=True)
        config.reload_all()
        for fail in (False, True):
            with self.subTest(commit_fails=fail):
                old_snapshot = schema.non_sensitive_snapshot()
                before = copy.deepcopy(self.repository.values)
                commit_started, release_commit = threading.Event(), threading.Event()

                @contextmanager
                def gated_transaction():
                    try:
                        yield object()
                        commit_started.set()
                        if not release_commit.wait(5):
                            raise AssertionError("测试提交门超时")
                        if fail:
                            raise RuntimeError("测试提交失败")
                    except BaseException:
                        self.repository.values = before
                        raise

                target = int(before["ACCOUNT_BATCH_WORKERS"]) + 1
                with patch.object(self.repository, "transaction", gated_transaction), ThreadPoolExecutor(max_workers=2) as executor:
                    saved = executor.submit(config_editor.update_config, {"ACCOUNT_BATCH_WORKERS": target})
                    reader_started, reader_done = threading.Event(), threading.Event()

                    def concurrent_read():
                        reader_started.set()
                        try:
                            return self.runtime.load_values(force=True)
                        finally:
                            reader_done.set()

                    try:
                        self.assertTrue(commit_started.wait(5))
                        reader = executor.submit(concurrent_read)
                        self.assertTrue(reader_started.wait(5))
                        self.assertFalse(reader_done.wait(.1), "候选重载期间其他线程不能投影旧数据库环境")
                        self.assertIs(old_snapshot, schema.non_sensitive_snapshot())
                        self.assertEqual(int(before["ACCOUNT_BATCH_WORKERS"]), schema.non_sensitive_snapshot()["ACCOUNT_BATCH_WORKERS"])
                    finally:
                        release_commit.set()
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "提交失败"):
                            saved.result(timeout=5)
                        self.assertIs(old_snapshot, schema.non_sensitive_snapshot())
                    else:
                        saved.result(timeout=5)
                        self.assertEqual(target, schema.non_sensitive_snapshot()["ACCOUNT_BATCH_WORKERS"])
                    self.assertEqual(self.repository.values, reader.result(timeout=5))


class RuntimeConfigStartupTests(unittest.TestCase):
    def test_physical_parser_preserves_standard_dotenv_semantics_and_bootstrap_roundtrip(self):
        from io import StringIO
        from dotenv.main import DotEnv

        content = """BASE=file
WEBUI_AUTH_CODE="${BASE} # 登录" # 注释
WEBUI_SESSION_SECRET='literal\\nvalue'
NODE_EXECUTABLE="/path/with\\t tab"
"""
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "PYTHON_DOTENV_DISABLED": "1", "BASE": "ambient",
        }):
            path = Path(directory) / ".env"
            path.write_text(content, encoding="utf-8")
            with patch.object(env_loader, "_ENV_PATH", path):
                expected = DotEnv(None, stream=StringIO(content), override=False).dict()
                self.assertEqual(expected, env_loader.read_env_file())
                secret = 'quoted" and backslash\\n and real\nline\rreturn\ttab'
                env_loader.write_env_values({"WEBUI_SESSION_SECRET": secret})
                self.assertEqual(secret, env_loader.read_env_file()["WEBUI_SESSION_SECRET"])

    def test_real_import_and_webui_save_use_active_database_from_temporary_bootstrap(self):
        from cryptography.fernet import Fernet
        from core.storage import runtime_config as repository
        from tests.support_pg import database_available, drop_schema, temporary_schema_name

        if not database_available():
            self.skipTest("需要隔离 PostgreSQL")
        selected_schema = temporary_schema_name("runtime_startup")
        key = Fernet.generate_key().decode("ascii")
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "TURB_DB_SCHEMA": selected_schema, "TURB_CONFIG_ENCRYPTION_KEY": key,
        }):
            try:
                repository.write_values({
                    "ACCOUNT_BATCH_WORKERS": "6", "PROXY_POOL": "[]",
                    "UNKNOWN_LEGACY_RUNTIME_KEY": "original-value",
                }, activate=True, source="test")
                path = Path(directory) / ".env"
                path.write_text(
                    'WEBUI_AUTH_CODE="temporary-login"\n'
                    f'TURB_DB_SCHEMA="{selected_schema}"\nTURB_CONFIG_ENCRYPTION_KEY="{key}"\n'
                    'ACCOUNT_BATCH_WORKERS="2"\nSMS_API_KEY="stale-file-value"\n', encoding="utf-8",
                )
                script = r'''
import importlib.util
import os
import sys
from pathlib import Path
root, path = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("config", root / "config/__init__.py", submodule_search_locations=[str(root / "config")])
package = importlib.util.module_from_spec(spec)
sys.modules["config"] = package
loader_spec = importlib.util.spec_from_file_location("config.env_loader", root / "config/env_loader.py")
loader = importlib.util.module_from_spec(loader_spec)
sys.modules["config.env_loader"] = loader
loader_spec.loader.exec_module(loader)
loader._ENV_PATH = path
spec.loader.exec_module(package)
from config import codex
assert codex.ACCOUNT_BATCH_WORKERS == 6
assert "SMS_API_KEY" not in os.environ
assert os.environ["UNKNOWN_LEGACY_RUNTIME_KEY"] == "original-value"
assert os.environ["WEBUI_AUTH_CODE"] == "temporary-login"
from webui.app import create_app
from webui import config_editor
from config import schema
from core.storage import runtime_config as runtime_config_store
app = create_app()
before_file = path.read_bytes()
old_snapshot = schema.non_sensitive_snapshot()
saved = config_editor.update_config({"ACCOUNT_BATCH_WORKERS": 7})
assert saved["database_updated"] == ["ACCOUNT_BATCH_WORKERS"]
assert runtime_config_store.read_values()["ACCOUNT_BATCH_WORKERS"] == "7"
assert package.ACCOUNT_BATCH_WORKERS == 7
assert old_snapshot["ACCOUNT_BATCH_WORKERS"] == 6
assert schema.non_sensitive_snapshot().sources["ACCOUNT_BATCH_WORKERS"] == "database"
assert path.read_bytes() == before_file
print("controlled_startup_and_save_ok")
'''
                child_environment = {**os.environ, "PYTHON_DOTENV_DISABLED": "0", "ACCOUNT_BATCH_WORKERS": "3"}
                diagnostic_wrapper = "try:\n" + "\n".join("    " + line for line in script.splitlines()) + '''
except BaseException as error:
    import traceback
    print(type(error).__name__ + ":" + ",".join(str(frame.lineno) for frame in traceback.extract_tb(error.__traceback__)), file=sys.stderr)
    raise SystemExit(1)
'''
                result = subprocess.run([sys.executable, "-c", diagnostic_wrapper, str(root), str(path)],
                                        env=child_environment, cwd=root, text=True, capture_output=True, timeout=30)
                # 不回显子进程输出，异常只以类型/退出码判定，防止未来断言含配置。
                self.assertEqual(0, result.returncode, "受控数据库启动或配置保存失败：" + result.stderr.strip())
                self.assertEqual("controlled_startup_and_save_ok", result.stdout.strip())
            finally:
                drop_schema(selected_schema)
