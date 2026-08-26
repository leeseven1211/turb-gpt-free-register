# -*- coding: utf-8 -*-
"""WebUI 路由契约基线。

目录拆分期间允许移动视图函数和改用 Blueprint，但不能意外改变公开 URL、HTTP
方法或 endpoint 名。确需调整 API 时，应先单独评审契约变更，再更新本基线。
"""
from __future__ import annotations

import hashlib

from tests.support_pg import PostgresTestCase
from webui.app import create_app


class FlaskRouteContractTests(PostgresTestCase):
    EXPECTED_ROUTE_COUNT = 100
    EXPECTED_SHA256 = "56677e87b357cc85c4698d6141e6e47bbfcf15ad28f18cf9ef9489bdcd025402"

    def test_public_route_map_matches_refactor_baseline(self):
        app = create_app(auth_code="route-contract")
        rows = sorted(
            f"{rule.rule}\t{','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))}\t{rule.endpoint}"
            for rule in app.url_map.iter_rules()
        )
        payload = "\n".join(rows) + "\n"

        self.assertEqual(self.EXPECTED_ROUTE_COUNT, len(rows), payload)
        self.assertEqual(
            self.EXPECTED_SHA256,
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            payload,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
