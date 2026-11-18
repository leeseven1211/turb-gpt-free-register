"""Focused contracts for the independent proxy and traffic workspace."""

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "tests/proxy/vue_migration_contracts.cjs"


class ProxyTrafficUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            ["node", str(HELPER)], cwd=ROOT, capture_output=True, text=True, timeout=60,
            check=False,
        )
        if result.returncode:
            raise AssertionError(f"Current Vue contract runner failed:\n{result.stdout}\n{result.stderr}")
        cls.contracts = json.loads(result.stdout)

    def assert_contract(self, name):
        result = self.contracts[name]
        self.assertTrue(result["ok"], result.get("error", name))

    def test_template_exposes_an_independent_three_view_workspace(self):
        self.assert_contract("workspace")

    def test_template_removes_the_manual_refresh_row_and_top_filter_card(self):
        self.assert_contract("no_manual_refresh_card")

    def test_template_puts_existing_filters_in_relevant_table_headers(self):
        self.assert_contract("header_filters")

    def test_proxy_filter_script_synchronizes_header_controls_without_manual_refresh_ui(self):
        self.assert_contract("filter_sync")

    def test_navigation_allows_proxy_traffic_and_loads_its_page(self):
        self.assert_contract("navigation")

    def test_frontend_uses_only_the_proxy_traffic_contract_and_never_renders_secrets(self):
        self.assert_contract("api_and_safe_fields")

    def test_template_exposes_proxy_pool_capacity_summary_without_inventory_secrets(self):
        self.assert_contract("pool_capacity")

    def test_proxy_traffic_css_is_responsive_and_keeps_long_values_readable(self):
        self.assert_contract("responsive_readability")


if __name__ == "__main__":
    unittest.main()
