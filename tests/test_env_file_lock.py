# -*- coding: utf-8 -*-
"""配置回滚与收件密钥保存共享锁的线程、进程竞态回归。"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import config
from config import env_loader, schema as config_schema
from core import email_derivation
from webui import config_editor


_PROFILE_KEY = "EMAIL_DERIVATION_IMAP_SECRET_LOCK_TEST"
_CHILD_WRITER = '''
from pathlib import Path
import sys
from config import env_loader
env_loader._ENV_PATH = Path(sys.argv[1])
from core.email_derivation import _save_profile_secret
print("ready", flush=True)
_save_profile_secret("EMAIL_DERIVATION_IMAP_SECRET_LOCK_TEST", "child-test-value")
print("saved", flush=True)
'''


class EnvFileLockTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="turb-env-lock-"))
        self.addCleanup(self._clean_directory)
        self.path = self.directory / ".env"
        self.path.write_text('ACCOUNT_BATCH_WORKERS="2"\nBASE_VALUE="keep"\n', encoding="utf-8")
        for context in (
            patch.object(env_loader, "_ENV_PATH", self.path),
            patch.object(config_schema, "_PUBLISHED_SNAPSHOT", None),
            patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def _clean_directory(self):
        # 只删除本用例创建的单个文件，不递归删除目录。
        for path in self.directory.iterdir():
            if not path.is_file():
                raise AssertionError("临时环境目录出现非预期子目录")
            path.unlink()
        self.directory.rmdir()

    def assert_original_config_and_profile_exist(self, value):
        saved = env_loader.read_env_file()
        self.assertEqual(saved["ACCOUNT_BATCH_WORKERS"], "2")
        self.assertEqual(saved["BASE_VALUE"], "keep")
        self.assertEqual(saved[_PROFILE_KEY], value)

    def test_failed_config_reload_cannot_rollback_concurrent_thread_profile_secret(self):
        in_reload, release_reload = threading.Event(), threading.Event()
        writer_started, writer_done = threading.Event(), threading.Event()
        def fail_reload():
            in_reload.set()
            if not release_reload.wait(5):
                raise RuntimeError("测试配置热加载等待超时")
            raise RuntimeError("测试配置热加载失败")
        def save_profile():
            writer_started.set()
            try:
                email_derivation._save_profile_secret(_PROFILE_KEY, "thread-test-value")
            finally:
                writer_done.set()
        with patch.object(config, "reload_all", side_effect=fail_reload), ThreadPoolExecutor(max_workers=2) as executor:
            failed_save = executor.submit(config_editor.update_config, {"ACCOUNT_BATCH_WORKERS": 4})
            self.assertTrue(in_reload.wait(5))
            profile_save = executor.submit(save_profile)
            self.assertTrue(writer_started.wait(5))
            try:
                self.assertFalse(writer_done.wait(.2), "配置回滚结束前不能交错保存 profile 密钥")
            finally:
                release_reload.set()
            with self.assertRaisesRegex(RuntimeError, "热加载失败"):
                failed_save.result(timeout=5)
            profile_save.result(timeout=5)
        self.assert_original_config_and_profile_exist("thread-test-value")
        self.assertEqual(os.environ[_PROFILE_KEY], "thread-test-value")

    @unittest.skipIf(os.name == "nt", "Windows 当前只提供单进程配置锁")
    def test_failed_config_reload_holds_process_lock_until_file_rollback_finishes(self):
        processes = []
        def fail_reload_with_competing_process():
            process = subprocess.Popen(
                [sys.executable, "-c", _CHILD_WRITER, str(self.path)],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            processes.append(process)
            self.assertEqual(process.stdout.readline().strip(), "ready")
            with self.assertRaises(subprocess.TimeoutExpired, msg="其他进程必须等待配置回滚持有的文件锁"):
                process.wait(timeout=.2)
            raise RuntimeError("测试跨进程配置热加载失败")
        try:
            with patch.object(config, "reload_all", side_effect=fail_reload_with_competing_process):
                with self.assertRaisesRegex(RuntimeError, "跨进程配置热加载失败"):
                    config_editor.update_config({"ACCOUNT_BATCH_WORKERS": 4})
            stdout, stderr = processes[0].communicate(timeout=10)
            self.assertEqual(processes[0].returncode, 0, stderr)
            self.assertEqual(stdout.strip(), "saved")
            self.assert_original_config_and_profile_exist("child-test-value")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    def test_nested_env_lock_and_profile_write_preserve_existing_versioned_secret(self):
        env_loader.write_env_values({"EMAIL_DERIVATION_IMAP_SECRET_OLD_TEST": "old-test-value"})
        with env_loader.env_file_lock():
            with env_loader.env_file_lock():
                email_derivation._save_profile_secret(_PROFILE_KEY, "new-test-value")
        self.assert_original_config_and_profile_exist("new-test-value")
        self.assertEqual(env_loader.read_env_file()["EMAIL_DERIVATION_IMAP_SECRET_OLD_TEST"], "old-test-value")
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
