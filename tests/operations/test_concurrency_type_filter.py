"""并发类型定位仅合并真实 task_type，不拼接 SQL。"""
import unittest

from core.storage.operations.store import _operation_task_where


class ConcurrencyTypeFilterTests(unittest.TestCase):
    def test_single_type_is_backward_compatible(self):
        where, params = _operation_task_where(task_type="plan_check")
        self.assertIn("t.task_type = ANY(%s)", where)
        self.assertEqual([["plan_check"]], params)

    def test_alias_list_is_trimmed_deduplicated_and_parameterized(self):
        where, params = _operation_task_where(task_type=" sub2api_sync,sub2api_manual_upload,sub2api_sync ")
        self.assertEqual([["sub2api_sync", "sub2api_manual_upload"]], params)
        self.assertFalse(any("sub2api_manual_upload" in item for item in where))

    def test_empty_unknown_and_bounded_lists_are_safe(self):
        self.assertEqual([], _operation_task_where(task_type=" , , ")[1])
        self.assertEqual([["future_type"]], _operation_task_where(task_type="future_type")[1])
        self.assertEqual(20, len(_operation_task_where(task_type=",".join(f"type_{i}" for i in range(30)))[1][0]))
        self.assertEqual([], _operation_task_where(task_type="plan_check,live_check", exclude="task_type")[1])
