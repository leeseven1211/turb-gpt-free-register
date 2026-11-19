"""共享任务详情必须独立于页面，避免打开隐藏弹窗后锁住滚动。"""
from html.parser import HTMLParser
from pathlib import Path
import unittest


class _TemplateNodes(HTMLParser):
    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__()
        self.stack = []
        self.nodes = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        node_id = attrs.get("id")
        if node_id:
            self.nodes.setdefault(node_id, []).append({
                "attrs": attrs, "ancestors": tuple(self.stack),
            })
        if tag not in self._VOID_TAGS:
            self.stack.append((tag, node_id))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack = self.stack[:index]
                break


class SharedTaskDialogLayoutTests(unittest.TestCase):
    def setUp(self):
        self.template = _TemplateNodes()
        self.template.feed((
            Path(__file__).resolve().parents[2] / "webui/templates/index.html"
        ).read_text())

    def test_task_center_has_one_mount_and_one_lazy_resource_entry(self):
        roots = self.template.nodes["task-center-root"]
        self.assertEqual(1, len(roots), "任务中心只保留一个组件实例")
        attrs = roots[0]["attrs"]
        self.assertIn("task-center/task-center.js", attrs["data-module-url"])
        self.assertIn("task-center/task-center.css", attrs["data-style-url"])
        self.assertIn(("section", "accountTasksPanel"), roots[0]["ancestors"])

    def test_template_does_not_keep_a_second_task_dialog(self):
        # Vue TaskDetail 使用 Teleport 和原生 dialog；全局可见性、Escape、焦点与滚动
        # 由 frontend/src/features/tasks/detail/detail.test.ts 及真实浏览器验收覆盖。
        for node_id in ("accountTaskLogPanel", "accountTaskStepDetailOverlay", "accountTaskStepDetailDialog"):
            self.assertNotIn(node_id, self.template.nodes)
