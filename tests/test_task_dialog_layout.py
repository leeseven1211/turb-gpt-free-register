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
            Path(__file__).resolve().parents[1] / "webui/templates/index.html"
        ).read_text())

    def test_task_dialog_is_available_from_every_page(self):
        dialogs = self.template.nodes["accountTaskLogPanel"]
        self.assertEqual(1, len(dialogs), "只能有一个共享任务详情")
        ancestors = dialogs[0]["ancestors"]
        self.assertFalse(
            any(node_id and node_id.startswith("tab-") for _, node_id in ancestors),
            "注册页打开任务详情时不能被其它页面的隐藏祖先挡住",
        )
        self.assertEqual(("body", None), ancestors[-1])

    def test_step_details_remain_inside_shared_task_dialog(self):
        for node_id in ("accountTaskStepDetailOverlay", "accountTaskStepDetailDialog"):
            with self.subTest(node_id=node_id):
                nodes = self.template.nodes[node_id]
                self.assertEqual(1, len(nodes))
                self.assertIn(("div", "accountTaskLogPanel"), nodes[0]["ancestors"])
        attrs = self.template.nodes["accountTaskLogPanel"][0]["attrs"]
        self.assertEqual("dialog", attrs["role"])
        self.assertEqual("true", attrs["aria-modal"])
        self.assertEqual("accountTaskLogTitle", attrs["aria-labelledby"])
