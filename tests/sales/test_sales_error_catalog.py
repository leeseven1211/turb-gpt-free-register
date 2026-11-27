# -*- coding: utf-8 -*-
"""销售领域错误码接入统一任务投影和短语目录的覆盖测试。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from core.operations.error_labels import FALLBACK_LABEL, short_error_label
from core.operations.errors import SALES_ERROR_DETAILS, classify_task_error


ROOT = Path(__file__).resolve().parents[2]
SALES_DYNAMIC_ERROR_CODES = {
    "shop_url_invalid",
    "shop_auth_missing",
    "source_url_invalid",
    "source_auth_missing",
}
SALES_CONTEXT_ERROR_CODES = {"invalid_field", "item_not_found"}
SALES_NON_THROWN_ERROR_CODES = {
    "sales_scheduler_storage_failed",
    "sales_task_retry_failed",
}


def sales_error_codes() -> set[str]:
    """从销售业务源码提取字面量错误码，避免测试表和业务实现重复维护。"""
    codes: set[str] = set()
    sources = sorted((ROOT / "core/sales").glob("*.py"))
    sources.append(ROOT / "webui/routes/sales.py")
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"SalesError", "_error"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                codes.add(node.args[0].value)
    codes.update(SALES_DYNAMIC_ERROR_CODES)
    return codes


class SalesErrorCatalogTests(unittest.TestCase):
    def test_every_sales_error_projects_to_a_known_task_cause_and_short_label(self):
        codes = sales_error_codes()
        self.assertGreaterEqual(len(codes), 60)
        self.assertTrue(
            codes <= set(SALES_ERROR_DETAILS) | SALES_DYNAMIC_ERROR_CODES | SALES_CONTEXT_ERROR_CODES,
            sorted(codes - set(SALES_ERROR_DETAILS) - SALES_DYNAMIC_ERROR_CODES - SALES_CONTEXT_ERROR_CODES),
        )

        for code in sorted(codes):
            with self.subTest(code=code):
                info = classify_task_error(
                    f"销售任务失败：{code}",
                    task_type="sales_sync",
                    error_code=code,
                    result_summary={"cause_code": code},
                    task_status="failed",
                )
                self.assertIsNotNone(info)
                self.assertNotEqual("unknown.unclassified", info["code"])
                self.assertEqual(code, info["cause_code"])
                self.assertEqual(code, info["error_code"])
                self.assertEqual(code, info["original_error_code"])
                self.assertNotEqual(FALLBACK_LABEL, short_error_label(info))

    def test_non_throwing_sales_scheduler_code_is_registered(self):
        for code in sorted(SALES_NON_THROWN_ERROR_CODES):
            with self.subTest(code=code):
                info = classify_task_error(
                    "销售任务调度无法读取或写入任务库",
                    task_type="sales_sync",
                    error_code=code,
                    result_summary={"cause_code": code},
                    task_status="failed",
                )
                self.assertEqual(code, info["cause_code"])
                self.assertEqual(code, info["error_code"])
                self.assertNotEqual(FALLBACK_LABEL, short_error_label(info))

    def test_unregistered_sales_code_preserves_original_codes_without_guessing(self):
        code = "shop_future_unregistered"
        info = classify_task_error(
            "销售任务失败",
            task_type="sales_sync",
            error_code=code,
            result_summary={"cause_code": code},
            task_status="failed",
        )

        self.assertEqual(code, info["error_code"])
        self.assertEqual(code, info["original_error_code"])
        self.assertNotEqual(code, info["cause_code"])
        self.assertFalse(str(info.get("cause_display_code") or "").startswith("SALES-"))

    def test_generic_sales_codes_do_not_classify_other_task_types_as_sales(self):
        for code in sorted(SALES_CONTEXT_ERROR_CODES):
            with self.subTest(code=code):
                info = classify_task_error(
                    "任务失败",
                    task_type="registration",
                    error_code=code,
                    result_summary={"cause_code": code},
                    task_status="failed",
                )
                self.assertNotEqual(code, info["cause_code"])
                self.assertFalse(str(info.get("cause_display_code") or "").startswith("SALES-"))

    def test_sales_projection_preserves_request_unknown_recovery_metadata(self):
        info = classify_task_error(
            "销售店铺回执待确认",
            task_type="sales_sync",
            error_code="shop_timeout",
            result_summary={
                "cause_code": "shop_timeout",
                "outcome": "request_unknown",
            },
            task_status="request_unknown",
        )

        self.assertEqual("shop_timeout", info["cause_code"])
        self.assertEqual("shop_timeout", info["error_code"])
        self.assertTrue(info["reconcile_required"])
        self.assertEqual("manual_only", info["retryability"])
        self.assertNotEqual(FALLBACK_LABEL, short_error_label(info))


if __name__ == "__main__":
    unittest.main()
