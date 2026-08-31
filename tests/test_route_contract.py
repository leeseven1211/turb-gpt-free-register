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
    EXPECTED_ROUTE_COUNT = 104
    EXPECTED_SHA256 = "a301a0e0adec4818fa7b7046beab3733559d088c0ae8d0d2aba422aeb652c212"

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
