# -*- coding: utf-8 -*-
"""兼容导出去抖器的行为测试。

导出被移出写入主路径后，这些性质就成了正确性的一部分：窗口内的多次变更必须
合并成一次渲染，进程退出前必须补写，渲染失败不能拖垮业务写入。
"""
import threading
import time
import unittest
from unittest.mock import patch

from core import compat_export


class CompatExportTests(unittest.TestCase):
    def setUp(self):
        # 每个用例一套干净的登记表与队列
        with compat_export._CV:
            compat_export._EXPORTERS.clear()
            compat_export._DIRTY.clear()
        compat_export._STOPPING = False
        self.calls = []
        self.lock = threading.Lock()
        compat_export.register("demo", self._record)

    def _record(self):
        with self.lock:
            self.calls.append(time.monotonic())

    def _call_count(self):
        with self.lock:
            return len(self.calls)

    def test_sync_mode_exports_inline(self):
        with patch.dict("os.environ", {"COMPAT_EXPORT_MODE": "sync"}):
            compat_export.schedule("demo")
        self.assertEqual(self._call_count(), 1)

    def test_off_mode_skips_export(self):
        with patch.dict("os.environ", {"COMPAT_EXPORT_MODE": "off"}):
            compat_export.schedule("demo")
        self.assertEqual(self._call_count(), 0)
        self.assertEqual(compat_export.pending(), [])

    def test_debounced_bursts_collapse_into_one_render(self):
        """20 次连续写入只应换来一次渲染——这正是把导出移出主路径的意义。"""
        with patch.dict("os.environ", {
            "COMPAT_EXPORT_MODE": "debounced",
            "COMPAT_EXPORT_DEBOUNCE_SECONDS": "0.15",
        }):
            for _ in range(20):
                compat_export.schedule("demo")
            self.assertEqual(self._call_count(), 0, "去抖窗口内不应该已经渲染")

            deadline = time.monotonic() + 3.0
            while self._call_count() == 0 and time.monotonic() < deadline:
                time.sleep(0.02)

        self.assertEqual(self._call_count(), 1)

    def test_flush_runs_pending_immediately(self):
        with patch.dict("os.environ", {
            "COMPAT_EXPORT_MODE": "debounced",
            "COMPAT_EXPORT_DEBOUNCE_SECONDS": "30",
        }):
            compat_export.schedule("demo")
            self.assertEqual(compat_export.pending(), ["demo"])

            flushed = compat_export.flush()

        self.assertEqual(flushed, ["demo"])
        self.assertEqual(self._call_count(), 1)
        self.assertEqual(compat_export.pending(), [])

    def test_shutdown_flushes_pending_work(self):
        """进程退出前必须补写。

        真实踩过：webui.sh stop 发 SIGTERM，Python 默认直接终止进程，
        finally 和 atexit 都不执行，去抖窗口里的改动就丢了。web.py 因此把
        SIGTERM 转成 SystemExit，走正常退出路径触发这里的 flush。
        """
        with patch.dict("os.environ", {
            "COMPAT_EXPORT_MODE": "debounced",
            "COMPAT_EXPORT_DEBOUNCE_SECONDS": "30",
        }):
            compat_export.schedule("demo")
            self.assertEqual(self._call_count(), 0)
            compat_export.shutdown()
        self.assertEqual(self._call_count(), 1)
        self.assertEqual(compat_export.pending(), [])


    def test_render_failure_does_not_propagate(self):
        """兼容文件不是事实来源；导出炸了也不能让业务写入失败。"""
        def boom():
            raise RuntimeError("磁盘满了")

        compat_export.register("broken", boom)
        with patch.dict("os.environ", {"COMPAT_EXPORT_MODE": "sync"}), \
             self.assertLogs("core.compat_export", level="ERROR") as logs:
            compat_export.schedule("broken")   # 不应抛出
        self.assertTrue(any("磁盘满了" in line for line in logs.output))

    def test_unknown_kind_is_ignored_with_a_warning(self):
        with patch.dict("os.environ", {"COMPAT_EXPORT_MODE": "debounced"}), \
             self.assertLogs("core.compat_export", level="WARNING"):
            compat_export.schedule("没登记过的种类")
        self.assertEqual(compat_export.pending(), [])

    def test_invalid_config_falls_back_to_defaults(self):
        with patch.dict("os.environ", {"COMPAT_EXPORT_MODE": "乱写"}):
            self.assertEqual(compat_export.mode(), "debounced")
        with patch.dict("os.environ", {"COMPAT_EXPORT_DEBOUNCE_SECONDS": "不是数字"}):
            self.assertEqual(compat_export.debounce_seconds(), 5.0)


if __name__ == "__main__":
    unittest.main()
