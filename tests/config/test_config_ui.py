# -*- coding: utf-8 -*-
"""Regression contracts for the modern configuration workspace UI."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFIG_CSS = (ROOT / "frontend/src/features/config/config.css").read_text(encoding="utf-8")


class ModernConfigUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Compile and mount the shipped components with their real draft owner.
        # A single subprocess keeps the Python regression suite inexpensive;
        # each original contract still receives its own Python test result.
        cls.vue_result = subprocess.run(
            ["node", "--test", "--test-reporter=tap", "tests/config/test_config_ui_contracts.cjs"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=30,
        )
        cls.vue_output = cls.vue_result.stdout + cls.vue_result.stderr

    def _assert_vue_contract(self, name):
        self.assertRegex(self.vue_output, rf"(?m)^ok \d+ - {name}$", self.vue_output)

    def test_country_pickers_search_names_and_codes_and_keep_ordered_pending_selection(self):
        self._assert_vue_contract("country_pickers_search_names_and_codes_and_keep_ordered_pending_selection")

    def test_empty_country_selection_explains_each_feature_and_overrides_saved_values(self):
        self._assert_vue_contract("empty_country_selection_explains_each_feature_and_overrides_saved_values")

    def test_country_inputs_normalize_separators_without_dropping_invalid_values_or_splitting_proxies(self):
        self._assert_vue_contract("country_inputs_normalize_separators_without_dropping_invalid_values_or_splitting_proxies")

    def test_config_enum_values_preserve_none_without_changing_text_placeholders(self):
        self._assert_vue_contract("config_enum_values_preserve_none_without_changing_text_placeholders")

    def test_region_select_preserves_empty_and_canonical_options(self):
        self._assert_vue_contract("region_select_preserves_empty_and_canonical_options")

    def test_email_source_uses_an_ordered_multi_select(self):
        self._assert_vue_contract("email_source_uses_an_ordered_multi_select")

    def test_regular_config_controls_expose_field_labels(self):
        self._assert_vue_contract("regular_config_controls_expose_field_labels")

    def test_config_page_exposes_runtime_status_and_refreshes_after_save(self):
        self._assert_vue_contract("config_page_exposes_runtime_status_and_refreshes_after_save")

    def test_extract_link_fields_cover_platforms_and_payment_without_menu_introduction(self):
        self._assert_vue_contract("extract_link_fields_cover_platforms_and_payment_without_menu_introduction")

    def test_workspace_has_one_save_bar_without_redundant_page_header(self):
        self._assert_vue_contract("workspace_has_one_save_bar_without_redundant_page_header")

    def test_navigation_exposes_grouped_search_metadata_and_dirty_state(self):
        self._assert_vue_contract("navigation_exposes_grouped_search_metadata_and_dirty_state")

    def test_fields_show_compact_help_without_detail_disclosures(self):
        self._assert_vue_contract("fields_show_compact_help_without_detail_disclosures")

    def test_unsaved_config_is_protected_and_reset_only_discards_pending_values(self):
        self._assert_vue_contract("unsaved_config_is_protected_and_reset_only_discards_pending_values")

    def test_config_workspace_is_overflow_safe_on_small_screens(self):
        # Layout source guards cover the actual mounted Vue selectors. Real
        # desktop/mobile measurements are recorded in the browser acceptance.
        self.assertIn("@media (max-width: 860px)", CONFIG_CSS)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", CONFIG_CSS)
        self.assertRegex(CONFIG_CSS, r"\.config-vue-navigation,\s*\.config-vue-content\s*\{\s*min-width:\s*0;")
        self.assertIn("padding-bottom: 160px", CONFIG_CSS)

    def test_config_workspace_uses_nested_scrolling_on_desktop(self):
        self.assertIn("@media (min-width: 861px)", CONFIG_CSS)
        self.assertIn("height: calc(100dvh - var(--topbar-height, 56px) - 28px)", CONFIG_CSS)
        self.assertRegex(CONFIG_CSS, r"(?s)\.config-vue-page \.config-vue-content \{[^}]*margin: 0;")
        self.assertRegex(CONFIG_CSS, r"(?s)\.config-vue-page \.config-vue-content \{[^}]*height: 100%;[^}]*overflow-y: auto;")
        self.assertRegex(CONFIG_CSS, r"(?s)\.config-vue-navigation \{[^}]*height: 100%;[^}]*overflow-y: auto;")

    def test_pending_save_bar_reserves_space_for_the_last_desktop_menu(self):
        self.assertRegex(CONFIG_CSS, r"(?s)\.config-vue-layout \{[^}]*flex: 1;[^}]*min-height: 0;")
        self.assertRegex(CONFIG_CSS, r"(?s)\.config-vue-savebar \{[^}]*position: static;[^}]*flex-shrink: 0;")

    def test_global_config_save_bar_is_hidden_until_changes_are_pending(self):
        self._assert_vue_contract("save_bar_is_hidden_until_changes_or_a_save_receipt_exist")

    def test_config_wheel_guard_targets_the_real_vertical_scroll_container(self):
        # Native overscroll containment follows the scrolling element itself,
        # so lazy mounting no longer depends on a legacy one-time wheel hook.
        self.assertRegex(CONFIG_CSS, r"(?s)\.config-vue-navigation \{[^}]*overflow-y: auto;[^}]*overscroll-behavior: contain;")
        self.assertRegex(CONFIG_CSS, r"(?s)\.config-vue-page \.config-vue-content \{[^}]*overflow-y: auto;[^}]*overscroll-behavior: contain;")

    def test_config_custom_panels_share_the_same_content_rail(self):
        self._assert_vue_contract("custom_panels_and_subtabs_share_the_field_content_rail")

    def test_config_dense_forms_expand_single_fields_and_multiline_values(self):
        self.assertRegex(CONFIG_CSS, r"\.config-vue-field\s*\{[^}]*display:\s*grid;[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(180px,")
        self.assertRegex(CONFIG_CSS, r"\.config-vue-control-group :is\(input:not\(\[type=checkbox\]\),\s*select,\s*textarea\)\s*\{[^}]*width:\s*100%;")
        self.assertRegex(CONFIG_CSS, r"\.config-vue-control-group textarea\s*\{[^}]*min-height:\s*96px;[^}]*resize:\s*vertical;")

    def test_config_section_subhelp_uses_the_same_content_rail(self):
        self.assertRegex(CONFIG_CSS, r"\.config-vue-page \.hint\s*\{[^}]*margin:\s*4px 0 0;[^}]*overflow-wrap:\s*anywhere;")

    def test_config_subtabs_use_the_same_content_rail_on_desktop_and_mobile(self):
        self.assertRegex(CONFIG_CSS, r"\.config-vue-content-header\s*\{[^}]*padding:\s*\d+px 17px 0;")
        self.assertRegex(CONFIG_CSS, r"\.config-vue-editor\s*\{[^}]*padding:\s*\d+px 17px \d+px;")
        self.assertRegex(CONFIG_CSS, r"\.config-vue-content-header,\s*\.config-vue-editor\s*\{[^}]*padding-inline:\s*11px;")

    def test_switching_config_groups_resets_the_page_viewport(self):
        self._assert_vue_contract("switching_config_groups_resets_the_page_viewport_without_losing_drafts")

    def test_read_only_driver_values_keep_their_config_key_context(self):
        self._assert_vue_contract("read_only_driver_values_keep_their_config_key_context")

    def test_config_domains_are_merged_into_menus_without_changing_schema_groups(self):
        self._assert_vue_contract("config_domains_are_merged_into_seven_menus_without_mutating_schema_groups")

    def test_navigation_and_pending_save_behavior(self):
        self.assertEqual(0, self.vue_result.returncode, self.vue_output)
        result = subprocess.run(
            ["node", "--test", "tests/config/test_config_navigation_frontend.cjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_lifecycle_pages_use_rows_without_execution_submenu(self):
        self._assert_vue_contract("lifecycle_pages_use_field_rows_without_an_execution_submenu")

if __name__ == "__main__":
    unittest.main()
