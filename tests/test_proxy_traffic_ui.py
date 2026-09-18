"""Focused contracts for the independent proxy and traffic workspace."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "modern": ROOT / "webui/templates/index.html",
    "legacy": ROOT / "webui/templates/index_legacy.html",
}
MODERN_COMMON = (ROOT / "webui/static/js/modern/common.js").read_text(encoding="utf-8")
LEGACY_COMMON = (ROOT / "webui/static/js/legacy/common.js").read_text(encoding="utf-8")
PROXY_JS_PATH = ROOT / "webui/static/js/proxy_traffic.js"
PROXY_JS = PROXY_JS_PATH.read_text(encoding="utf-8") if PROXY_JS_PATH.exists() else ""
FOUNDATION_CSS = (ROOT / "webui/static/css/ui-foundation.css").read_text(encoding="utf-8")


class ProxyTrafficUiContractTest(unittest.TestCase):
    def test_both_templates_expose_an_independent_three_view_workspace(self):
        required_views = (
            'data-proxy-view="current"',
            'data-proxy-view="history"',
            'data-proxy-view="traffic"',
        )
        for name, path in TEMPLATES.items():
            html = path.read_text(encoding="utf-8")
            self.assertIn('data-tab="proxy-traffic"', html, name)
            self.assertIn('id="tab-proxy-traffic"', html, name)
            for view in required_views:
                self.assertIn(view, html, name)
            self.assertIn('id="proxyTrafficCurrentBody"', html, name)
            self.assertIn('id="proxyTrafficHistoryBody"', html, name)
            self.assertIn('id="proxyTrafficTrafficBody"', html, name)
            self.assertIn('js/proxy_traffic.js', html, name)

    def test_both_templates_remove_the_manual_refresh_row_and_top_filter_card(self):
        for name, path in TEMPLATES.items():
            html = path.read_text(encoding="utf-8")
            self.assertNotIn('Network operations', html, name)
            self.assertNotIn('<h2>代理与流量</h2>', html, name)
            self.assertNotIn('查看持久化线路租约与 Roxy/CDP 可观测的浏览器字节；协议任务显示为未采集。', html, name)
            self.assertNotIn('class="proxy-traffic-head"', html, name)
            self.assertNotIn('id="proxyTrafficLastUpdated"', html, name)
            self.assertNotIn('id="btnRefreshProxyTraffic"', html, name)
            self.assertNotIn('class="proxy-traffic-toolbar"', html, name)

    def test_both_templates_put_existing_filters_in_relevant_table_headers(self):
        filter_contracts = {
            "search": ("proxyTrafficSearchCurrent", "proxyTrafficSearchHistory", "proxyTrafficSearchTraffic"),
            "state": ("proxyTrafficStateCurrent", "proxyTrafficStateHistory", "proxyTrafficStateTraffic"),
            "window": ("proxyTrafficWindowCurrent", "proxyTrafficWindowHistory", "proxyTrafficWindowTraffic"),
            "purpose": ("proxyTrafficPurposeCurrent", "proxyTrafficPurposeHistory"),
        }
        for name, path in TEMPLATES.items():
            html = path.read_text(encoding="utf-8")
            for key, control_ids in filter_contracts.items():
                self.assertGreaterEqual(html.count(f'data-proxy-filter-key="{key}"'), len(control_ids), name)
                for control_id in control_ids:
                    self.assertIn(f'data-column-filter="{control_id}"', html, name)
            self.assertIn('id="btnClearProxyTrafficFilters"', html, name)
            self.assertIn('class="proxy-traffic-view-bar"', html, name)

    def test_proxy_filter_script_synchronizes_header_controls_without_manual_refresh_ui(self):
        self.assertIn("[data-proxy-filter-key]", PROXY_JS)
        self.assertIn("proxyTrafficSyncFilterControls", PROXY_JS)
        self.assertIn("proxyTrafficBindFilterControls", PROXY_JS)
        self.assertNotIn("btnRefreshProxyTraffic", PROXY_JS)
        self.assertNotIn("proxyTrafficLastUpdated", PROXY_JS)

    def test_navigation_allows_proxy_traffic_and_loads_its_page(self):
        self.assertIn("'proxy-traffic': { title: '代理与流量'", MODERN_COMMON)
        self.assertIn("'proxy-traffic'", MODERN_COMMON)
        self.assertIn("if (tab === 'proxy-traffic') loadProxyTraffic();", MODERN_COMMON)
        self.assertIn("'proxy-traffic'", LEGACY_COMMON)
        self.assertIn("if (tab === 'proxy-traffic') loadProxyTraffic();", LEGACY_COMMON)

    def test_frontend_uses_only_the_proxy_traffic_contract_and_never_renders_secrets(self):
        self.assertNotIn("const PROXY_TRAFFIC_API = '/api/proxy-traffic';", PROXY_JS)
        for endpoint in (
            "'/api/proxy-traffic/current'",
            "'/api/proxy-traffic/history'",
            "'/api/proxy-traffic/traffic'",
        ):
            self.assertIn(endpoint, PROXY_JS)
        self.assertIn("Promise.all", PROXY_JS)
        self.assertIn("payload.view != null", PROXY_JS)
        self.assertIn("Array.isArray(payload.items)", PROXY_JS)
        for page_field in ("count", "limit", "offset"):
            self.assertIn(f"payload.{page_field}", PROXY_JS)
        for field in ("current_leases", "lease_history", "browser_traffic"):
            self.assertIn(field, PROXY_JS)
        for secret_field in ("proxy_url", "username", "password"):
            self.assertNotIn(secret_field, PROXY_JS)
        self.assertIn("exit_ip", PROXY_JS)
        self.assertNotIn("proxyTrafficNormalize(await proxyTrafficRequest())", PROXY_JS)
        self.assertIn("proxyTrafficSnapshot = await proxyTrafficRequest();", PROXY_JS)
        self.assertIn("route_attempt_no", PROXY_JS)
        self.assertIn("availability", PROXY_JS)
        self.assertIn("ended_at", PROXY_JS)
        self.assertNotIn("finished_at", PROXY_JS)
        self.assertNotIn("proxyTrafficValue(row, 'status')", PROXY_JS)

    def test_proxy_traffic_css_is_responsive_and_keeps_long_values_readable(self):
        self.assertIn(".proxy-traffic-table-wrap", FOUNDATION_CSS)
        self.assertIn("overflow-wrap: anywhere", FOUNDATION_CSS)
        self.assertIn("table-layout: fixed", FOUNDATION_CSS)
        self.assertIn("@media (max-width: 860px)", FOUNDATION_CSS)
        self.assertIn(".proxy-traffic-table", FOUNDATION_CSS)
        self.assertIn(".proxy-traffic-view-bar", FOUNDATION_CSS)
        self.assertIn(".proxy-traffic-page .column-filter-header", FOUNDATION_CSS)
        self.assertIn(".proxy-traffic-page .column-filter-trigger:focus-visible", FOUNDATION_CSS)


if __name__ == "__main__":
    unittest.main()
