# -*- coding: utf-8 -*-
"""Regression contracts for the modern configuration workspace UI."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "webui/templates/index.html").read_text(encoding="utf-8")
CONFIG_JS = (ROOT / "webui/static/js/modern/config.js").read_text(encoding="utf-8")
COMMON_JS = (ROOT / "webui/static/js/modern/common.js").read_text(encoding="utf-8")
FOUNDATION_CSS = (ROOT / "webui/static/css/ui-foundation.css").read_text(encoding="utf-8")


class ModernConfigUiContractTests(unittest.TestCase):
    def _run_config_control_js(self, assertions):
        harness = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const root = process.argv[1];
const config = fs.readFileSync(path.join(root, 'webui/static/js/modern/config.js'), 'utf8');
const common = fs.readFileSync(path.join(root, 'webui/static/js/modern/common.js'), 'utf8');
function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf('\n}', start);
  if (start < 0 || end < 0) throw new Error(`缺少待验证函数：${name}`);
  return source.slice(start, end + 2);
}
const context = vm.createContext({
  assert, CONFIG: [], CONFIG_PENDING_UPDATES: {}, esc: String, attrEsc: String,
});
vm.runInContext(extractFunction(common, 'isPlaceholderEmpty'), context);
for (const name of [
  'configSchemaOptions', 'configDriverChoices',
  'renderConfigControlMarkupV2', 'readConfigElementValue',
]) {
  vm.runInContext(extractFunction(config, name), context);
}
vm.runInContext(process.argv[2], context);
'''
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness, str(ROOT), assertions],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_config_enum_values_preserve_none_without_changing_text_placeholders(self):
        self._run_config_control_js(r'''
for (const key of ['REGISTRATION_PROXY_MODE', 'CLOUDFLARE_AUTH_MODE']) {
  const field = {key, type: 'str', options: [{value: 'none', label: '无'}]};
  for (const value of ['none', ' NONE ']) {
    assert.equal(readConfigElementValue({dataset: {}, value}, field), 'none');
  }
}
const textField = {key: 'REGISTER_NAME', type: 'str'};
for (const value of ['none', '-', ' 无 ', '']) {
  assert.equal(readConfigElementValue({dataset: {}, value}, textField), '');
}
assert.equal(readConfigElementValue({dataset: {}, value: ' Alice '}, textField), 'Alice');
const region = {key: 'PROXY_1024_REGION', type: 'str', options: [
  {value: '', label: '沿用 API URL'}, {value: 'JP', label: '日本'},
]};
assert.equal(readConfigElementValue({dataset: {}, value: ''}, region), '');
assert.equal(readConfigElementValue({dataset: {}, value: 'jp'}, region), 'JP');
''')

    def test_region_select_preserves_empty_and_canonical_options(self):
        self._run_config_control_js(r'''
const region = {key: 'PROXY_1024_REGION', type: 'str', options: [
  {value: '', label: '沿用 API URL'},
  {value: 'US', label: '美国'}, {value: 'JP', label: '日本'},
  {value: 'Rand', label: '随机地区'}, null, {}, {value: null},
]};
for (const [value, expected, label] of [
  ['', '', '沿用 API URL'], ['JP', 'JP', '日本'],
  ['us', 'US', '美国'], ['Rand', 'Rand', '随机地区'],
]) {
  const markup = renderConfigControlMarkupV2({...region, value});
  assert.equal((markup.match(/<option /g) || []).length, 4);
  assert.equal((markup.match(/ selected/g) || []).length, 1);
  assert.ok(markup.includes(`<option value="${expected}" selected>${label}</option>`));
  assert.ok(!markup.includes('当前配置'));
}
CONFIG_PENDING_UPDATES.PROXY_1024_REGION = '';
const pending = renderConfigControlMarkupV2({...region, value: 'US'});
assert.ok(pending.includes('<option value="" selected>沿用 API URL</option>'));
''')

    def test_email_source_uses_an_ordered_multi_select(self):
        self._run_config_control_js(r'''
const field = {key: 'EMAIL_SOURCE', type: 'str', value: 'mailnest,outlook', csv_options: ['outlook', 'mailnest'], options: [
  {value: 'outlook', label: 'Outlook'}, {value: 'mailnest', label: 'MailNest'},
]};
const markup = renderConfigControlMarkupV2(field);
assert.ok(markup.includes('<select multiple'));
assert.ok(markup.includes('<option value="outlook" selected>Outlook</option>'));
assert.ok(markup.includes('<option value="mailnest" selected>MailNest</option>'));
const selected = {multiple: true, selectedOptions: [{value: 'mailnest'}, {value: 'outlook'}], dataset: {}};
assert.equal(readConfigElementValue(selected, field), 'mailnest,outlook');
''')

    def test_config_page_exposes_runtime_status_and_refreshes_after_save(self):
        self.assertIn('config-field-status-v2', CONFIG_JS)
        self.assertIn("f.invalid_env", CONFIG_JS)
        self.assertIn("f.restart", CONFIG_JS)
        self.assertIn("await loadConfig();", CONFIG_JS)

    def test_config_workspace_keeps_global_save_bar_without_redundant_page_header(self):
        self.assertIn('class="config-workspace-v2"', TEMPLATE)
        self.assertNotIn('config-page-head-v2', TEMPLATE)
        self.assertNotIn('config-page-kicker-v2', TEMPLATE)
        self.assertNotIn('id="configPageTitleV2"', TEMPLATE)
        self.assertNotIn('id="configPageDescriptionV2"', TEMPLATE)
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

    def test_config_workspace_uses_nested_scrolling_on_desktop(self):
        desktop_scroll_rule = """
@media (min-width: 861px) {
  body:has(#tab-config:not(.hidden)) {
    overflow-y: hidden;
  }

  #tab-config .config-workspace-v2 {
    height: calc(100dvh - var(--topbar-height) - 54px);
    padding-bottom: 0;
    overflow: hidden;
  }

  #tab-config .config-layout-v2 {
    height: 100%;
    overflow: hidden;
  }

  #tab-config .config-nav-v2 {
    height: 100%;
    max-height: 100%;
    overflow: hidden;
  }

  #tab-config .config-main-v2 {
    height: 100%;
    max-height: 100%;
    overflow-y: auto;
    padding: 0 6px 104px 0;
    overscroll-behavior: contain;
  }
}
"""
        self.assertIn(desktop_scroll_rule, FOUNDATION_CSS)

    def test_global_config_save_bar_is_hidden_until_changes_are_pending(self):
        self.assertIn(
            '<div class="config-save-bar-v2" id="configSaveBarV2" hidden>',
            TEMPLATE,
        )
        self.assertIn(
            "const saveBar = document.getElementById('configSaveBarV2');",
            CONFIG_JS,
        )
        self.assertIn("if (saveBar) saveBar.hidden = count === 0;", CONFIG_JS)

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

    def test_config_section_subhelp_uses_the_same_content_rail(self):
        self.assertIn(
            "#tab-config .config-section-v2-subhelp {\n"
            "  margin-inline: var(--ui-space-5);",
            FOUNDATION_CSS,
        )
        self.assertIn(
            "#tab-config .config-section-v2-subhelp {\n"
            "    margin-inline: 14px;",
            FOUNDATION_CSS,
        )

    def test_config_subtabs_use_the_same_content_rail_on_desktop_and_mobile(self):
        self.assertIn(
            "#tab-config .config-subtabs-v2 {\n"
            "  margin-inline: var(--ui-space-5);",
            FOUNDATION_CSS,
        )
        self.assertIn(
            "#tab-config .config-subtabs-v2 {\n"
            "    margin-inline: 14px;",
            FOUNDATION_CSS,
        )

    def test_switching_config_groups_resets_the_page_viewport(self):
        self.assertIn("resetConfigViewportV2", CONFIG_JS)
        self.assertIn("window.scrollTo({ top: 0, left: 0, behavior: 'auto' })", CONFIG_JS)

    def test_read_only_driver_values_keep_their_config_key_context(self):
        self.assertIn('config-setting-readonly-v2', CONFIG_JS)
        self.assertIn('data-config-setting="${attrEsc(displayKey)}"', CONFIG_JS)
        self.assertIn('由注册主链路统一维护', CONFIG_JS)

    def test_lifecycle_groups_are_first_class_config_pages(self):
        self.assertIn("const group = rawGroup || '其他';", CONFIG_JS)
        self.assertIn("if (name === '注册主链路')", CONFIG_JS)
        self.assertIn("if (name === '账号补全')", CONFIG_JS)
        self.assertIn("if (name === '注册调试')", CONFIG_JS)
        self.assertNotIn("CONFIG_LIFECYCLE_SOURCE_GROUPS_V2.has(rawGroup) ? CONFIG_LIFECYCLE_GROUP_V2 : rawGroup", CONFIG_JS)

    def test_lifecycle_pages_use_rows_without_execution_submenu(self):
        self.assertIn('config-setting-list-v2', CONFIG_JS)
        self.assertIn('config-setting-row-v2', CONFIG_JS)
        self.assertIn('renderRegistrationMainSectionV2', CONFIG_JS)
        self.assertIn('renderAccountCompletionSectionV2', CONFIG_JS)
        self.assertIn('renderRegistrationDebugSectionV2', CONFIG_JS)
        self.assertIn("'OPENAI_PROTOCOL_VERSION'", CONFIG_JS)
        self.assertNotIn('data-lifecycle-section-v2', CONFIG_JS)
        self.assertIn('.config-setting-row-v2', FOUNDATION_CSS)
        self.assertIn('grid-template-columns: minmax(0, 1fr) minmax(240px, 340px)', FOUNDATION_CSS)


if __name__ == "__main__":
    unittest.main()
