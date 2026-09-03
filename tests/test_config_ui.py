# -*- coding: utf-8 -*-
"""Regression contracts for the modern configuration workspace UI."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "webui/templates/index.html").read_text(encoding="utf-8")
CONFIG_JS = (ROOT / "webui/static/js/modern/config.js").read_text(encoding="utf-8")
COMMON_JS = (ROOT / "webui/static/js/modern/common.js").read_text(encoding="utf-8")
FOUNDATION_CSS = (ROOT / "webui/static/css/ui-foundation.css").read_text(encoding="utf-8")


class ModernConfigUiContractTests(unittest.TestCase):
    def test_config_workspace_has_page_context_and_global_save_bar(self):
        self.assertIn('class="config-workspace-v2"', TEMPLATE)
        self.assertIn('id="configPageTitleV2"', TEMPLATE)
        self.assertIn('id="configPageDescriptionV2"', TEMPLATE)
        self.assertIn('id="configSaveBarV2"', TEMPLATE)
        self.assertIn('data-reset-config-v2', TEMPLATE)

    def test_config_navigation_exposes_grouped_search_metadata_and_dirty_state(self):
        self.assertIn("configNavCategoryV2", CONFIG_JS)
        self.assertIn("data-config-search", CONFIG_JS)
        self.assertIn("data-config-keys", CONFIG_JS)
        self.assertIn("data-config-dirty", CONFIG_JS)
        self.assertIn("config-nav-v2-group", CONFIG_JS)

    def test_config_fields_keep_data_keys_and_show_the_key_as_secondary_context(self):
        self.assertIn('class="config-field-key-v2"', CONFIG_JS)
        self.assertIn('data-key="${attrEsc(f.key)}"', CONFIG_JS)

    def test_unsaved_config_is_protected_and_reset_only_discards_pending_values(self):
        self.assertIn("beforeunload", CONFIG_JS)
        self.assertIn("data-reset-config-v2", CONFIG_JS)
        self.assertIn("Object.keys(CONFIG_PENDING_UPDATES)", CONFIG_JS)

    def test_config_workspace_is_overflow_safe_on_small_screens(self):
        self.assertIn("#tab-config .config-workspace-v2", FOUNDATION_CSS)
        self.assertIn("min-width: 0", FOUNDATION_CSS)
        self.assertIn("scrollbar-gutter: stable;\n  text-size-adjust", FOUNDATION_CSS)
        self.assertIn("@media (max-width: 860px)", FOUNDATION_CSS)
        self.assertIn("config-save-bar-v2", FOUNDATION_CSS)

    def test_config_wheel_guard_targets_the_real_vertical_scroll_container(self):
        self.assertIn("containVerticalScroll(document.querySelector('#configNavV2'));", COMMON_JS)
        self.assertIn("getComputedStyle(el).overflowY", COMMON_JS)
        self.assertNotIn("containVerticalScroll(document.querySelector('.config-nav-v2'));", COMMON_JS)

    def test_config_custom_panels_share_the_same_content_rail(self):
        self.assertIn('config-tool-panel-v2 roxy-workspace-box', CONFIG_JS)
        self.assertIn('#tab-config .config-section-v2 > .config-tool-panel-v2', FOUNDATION_CSS)
        self.assertIn('#tab-config .config-section-v2 > .config-lifecycle-driver-grid-v2', FOUNDATION_CSS)
        self.assertIn('margin-inline: var(--ui-space-5)', FOUNDATION_CSS)
        self.assertIn('margin-inline: 14px', FOUNDATION_CSS)

    def test_config_dense_forms_expand_single_fields_and_multiline_values(self):
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr));', FOUNDATION_CSS)
        self.assertIn('.config-section-v2-body:has(> .config-field-v2:only-child)', FOUNDATION_CSS)
        self.assertIn('.config-section-v2-body > .config-field-v2:has(textarea)', FOUNDATION_CSS)

    def test_switching_config_groups_resets_the_page_viewport(self):
        self.assertIn("resetConfigViewportV2", CONFIG_JS)
        self.assertIn("window.scrollTo({ top: 0, left: 0, behavior: 'auto' })", CONFIG_JS)

    def test_read_only_driver_values_keep_their_config_key_context(self):
        self.assertIn("renderLifecycleFixedDriver('ACCOUNT_PASSWORD_DRIVER'", CONFIG_JS)
        self.assertIn("renderLifecycleFixedDriver('ACCOUNT_PLAN_CHECK_DRIVER'", CONFIG_JS)
        self.assertIn('config-twofa-driver-v2-label-wrap', CONFIG_JS)


if __name__ == "__main__":
    unittest.main()
