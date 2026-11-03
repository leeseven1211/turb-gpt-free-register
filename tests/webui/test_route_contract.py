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
    # Snapshot history: commit 1006937 had the prior map; f33e523 intentionally
    # added /api/extract-link/types. The release then added /healthz and
    # /readyz，以及经过评审的配置快照、durable operations、proxy-traffic API、
    # 协议邮箱换绑路由、任务终止入口、任务中心批量动作和 iCloud HME 账号目录。
    # 本轮移植新增巡检历史/启动/取消/失败详情、已废清理及 MailCode 商品余额接口。
    # 配置页补充 Roxy 工作区目录，本轮新增邮箱子地址概况和分配台账两条只读路由。
    # 本轮对照 main 的 155 条路由，确认原路由未变；库存管理仅新增显式生成
    # 与批量停用/恢复两条写入路由，同时校正此前遗漏更新的历史快照。
    # 同步已存在的五条 Butler 手动导入路由，以及账号 Session 批量下载路由；
    # 排除这六条新增项后，原 157 条路由的摘要仍与上一版基线完全一致。
    # 保持这些变更显式记录，不从当前路由表推导基线。
    EXPECTED_ROUTE_COUNT = 163
    EXPECTED_SHA256 = "2ac1dc2665779900d8deeb126cc0bcf96a109e4b5ffa16c8a59be949d3da99b5"
    # Already committed additions since the 4e38812 baseline, with no changed
    # or removed routes. Keep these explicit rather than replacing its hash.
    PREEXISTING_ADDED_ROUTES = {
        "/api/accounts/<int:acc_id>/plan-details\tGET\tapi_account_plan_details",  # 47bd4de
        "/api/extract-link/huanguang/cdk-quota/<kind>\tGET\tapi_huanguang_single_cdk_quota",  # dde1223
        "/api/extract-link/payments/xxsyun/balance\tPOST\tapi_xxsyun_payment_balance",  # e03c999
        "/api/extract-workbench/batches/<int:batch_id>/cancel\tPOST\tcancel_extract_workbench_batch",  # f5672de
        "/api/extract-workbench/tasks/<int:task_id>/payment-query-credential\tPOST\trestore_extract_workbench_payment_query_credential",  # 1119f6a
    }
    # Explicit additive maintenance/integration routes; the previous 163-route
    # baseline remains independently verified after removing only these rows.
    ADDED_ROUTES = {
        "/api/sub2api/automation\tGET\tapi_sub2api_automation",
        "/api/sub2api/automation/check\tPOST\tapi_sub2api_automation_check",
        "/api/maintenance/sentinel\tGET\tapi_sentinel_maintenance",
        "/api/maintenance/sentinel/check\tPOST\tapi_sentinel_maintenance_check",
        "/api/accounts/<int:acc_id>/registration-retry\tPOST\tapi_account_registration_retry",
        "/api/accounts/registration-retry-bulk\tPOST\tapi_accounts_registration_retry_bulk",
    }

    def test_public_route_map_matches_refactor_baseline(self):
        app = create_app(auth_code="route-contract")
        rows = sorted(
            f"{rule.rule}\t{','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))}\t{rule.endpoint}"
            for rule in app.url_map.iter_rules()
        )
        added_routes = self.PREEXISTING_ADDED_ROUTES | self.ADDED_ROUTES
        self.assertTrue(added_routes.issubset(set(rows)), "新增路由契约不完整")
        rows = [row for row in rows if row not in added_routes]
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
