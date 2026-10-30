# -*- coding: utf-8 -*-
"""Regression contracts for the modern configuration workspace UI."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (ROOT / "webui/templates/index.html").read_text(encoding="utf-8")
CONFIG_JS = (ROOT / "webui/static/js/pages/config/page.js").read_text(encoding="utf-8")
COMMON_JS = (ROOT / "webui/static/js/shared/common.js").read_text(encoding="utf-8")
FOUNDATION_CSS = (ROOT / "webui/static/css/shared/ui-foundation.css").read_text(encoding="utf-8")
CONFIG_WORKSPACE_CSS = (ROOT / "webui/static/css/pages/config.css").read_text(encoding="utf-8")


class ModernConfigUiContractTests(unittest.TestCase):
    def _run_config_control_js(self, assertions):
        harness = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const root = process.argv[1];
const config = fs.readFileSync(path.join(root, 'webui/static/js/pages/config/page.js'), 'utf8');
const common = fs.readFileSync(path.join(root, 'webui/static/js/shared/common.js'), 'utf8');
function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf('\n}', start);
  if (start < 0 || end < 0) throw new Error(`缺少待验证函数：${name}`);
  return source.slice(start, end + 2);
}
const context = vm.createContext({
  assert, CONFIG: [], CONFIG_PENDING_UPDATES: {}, CONFIG_HUANGUANG_CDK_QUOTAS_V2: {},
  esc: String, attrEsc: String,
});
vm.runInContext(common.slice(common.indexOf('function fmt('), common.indexOf('function isPlaceholderEmpty(')), context);
vm.runInContext(extractFunction(common, 'isPlaceholderEmpty'), context);
for (const name of [
  'configSchemaOptions', 'configSchemaField', 'configRangeAttrs', 'configDriverChoices',
  'configListValuesV2', 'configListOptionValuesV2', 'configListSummaryV2', 'renderConfigMultiSelectV2',
  'configCountryCodesV2', 'configCountryNameV2', 'configCountryOptionsV2',
  'configCountrySummaryV2',
  'renderConfigCountryChipsV2', 'renderConfigCountryOptionsV2', 'renderConfigCountryControlV2',
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

    def test_country_pickers_search_names_and_codes_and_keep_ordered_pending_selection(self):
        self._run_config_control_js(r'''
for (const key of ['PROXY_POOL_COUNTRIES', 'PLAN_CHECK_COUNTRIES']) {
  const field = {key, type: 'list_str_multiline', label: '国家列表',
    value: ['SG', 'JP'], country_codes: ['US', 'JP', 'SG', 'DE']};
  assert.deepEqual(Array.from(configCountryOptionsV2(field, '日本'), item => item.code), ['JP']);
  assert.deepEqual(Array.from(configCountryOptionsV2(field, ' de '), item => item.code), ['DE']);
  assert.equal(configCountryOptionsV2(field, '不存在的国家').length, 0);
  const saved = renderConfigControlMarkupV2(field);
  assert.ok(saved.includes(`<input type="hidden" data-key="${key}" value="SG,JP">`));
  assert.ok(saved.indexOf('data-country-remove="SG"') < saved.indexOf('data-country-remove="JP"'));

  CONFIG_PENDING_UPDATES[key] = ['DE', 'JP'];
  const markup = renderConfigControlMarkupV2(field);
  assert.ok(markup.includes(`data-country-picker="${key}"`));
  assert.ok(markup.includes('config-country-picker-v2--compact'));
  assert.ok(markup.includes('<details class="config-country-choices-v2">'));
  assert.ok(!/<details[^>]*\bopen(?:\s|>|=)/.test(markup));
  assert.equal((markup.match(/<summary\b/g) || []).length, 1);
  assert.ok(markup.includes('<span data-country-summary>德国 DE、日本 JP</span>'));
  assert.ok(markup.includes('data-country-count>2 国</span>'));
  assert.ok(markup.includes('data-country-code="DE" aria-pressed="true"'));
  assert.ok(markup.includes('data-country-code="SG" aria-pressed="false"'));
  assert.ok(markup.indexOf('data-country-remove="DE"') < markup.indexOf('data-country-remove="JP"'));
  assert.ok(markup.includes(`<input type="hidden" data-key="${key}" value="DE,JP">`));
  assert.equal((markup.match(new RegExp(`data-key="${key}"`, 'g')) || []).length, 1);
  assert.ok(!markup.includes('<textarea'));
  assert.ok(!markup.includes('data-country-raw'));
  assert.ok(markup.includes('可选 4 个国家 / 地区'));
}
''')

    def test_empty_country_selection_explains_each_feature_and_overrides_saved_values(self):
        self._run_config_control_js(r'''
for (const [key, summary, help] of [
  ['PLAN_CHECK_COUNTRIES', '沿用账号注册国家', '按选择顺序查询；留空沿用账号注册国家，不影响注册查套餐。'],
  ['PROXY_POOL_COUNTRIES', '未选择额外预热国家', '留空不额外预热；实际可用线路取决于代理来源和库存。'],
]) {
  const field = {key, type: 'list_str_multiline', label: '国家列表', value: ['JP'], country_codes: ['US', 'JP']};
  CONFIG_PENDING_UPDATES[key] = [];
  const markup = renderConfigControlMarkupV2(field);
  assert.ok(markup.includes(`<span data-country-summary>${summary}</span>`));
  assert.ok(markup.includes('data-country-count>多选</span>'));
  assert.ok(markup.includes(`<input type="hidden" data-key="${key}" value="">`));
  assert.ok(!markup.includes('aria-pressed="true"'));
  assert.ok(markup.includes(help));
}
''')

    def test_country_inputs_normalize_separators_without_dropping_invalid_values_or_splitting_proxies(self):
        self._run_config_control_js(r'''
for (const key of ['PROXY_POOL_COUNTRIES', 'PLAN_CHECK_COUNTRIES']) {
  const field = {key, type: 'list_str_multiline'};
  const read = value => Array.from(readConfigElementValue({dataset: {}, value}, field));
  assert.deepEqual(read('jp, US\n sg jp'), ['JP', 'US', 'SG']);
  assert.deepEqual(read(''), []);
  // 无效代码保留给后端校验，不能在多选操作时静默丢弃。
  assert.deepEqual(read('jp ZZ'), ['JP', 'ZZ']);
  assert.deepEqual(Array.from(configCountryCodesV2(['sg', 'JP', 'sg'])), ['SG', 'JP']);
}
const proxies = {key: 'PROXY_POOL', type: 'list_str_multiline'};
assert.deepEqual(Array.from(readConfigElementValue({dataset: {}, value: 'http://proxy.test/a,b'}, proxies)), ['http://proxy.test/a,b']);
''')

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
const defaultCountry = {key: 'PROXY_POOL_DEFAULT_COUNTRY', type: 'str', country_codes: ['JP', 'NA']};
assert.equal(readConfigElementValue({dataset: {}, value: 'NA'}, defaultCountry), 'NA');
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
assert.ok(markup.includes('<select class="config-multi-compat-v2" multiple'));
assert.ok(markup.includes('<option value="outlook" selected>Outlook</option>'));
assert.ok(markup.includes('<option value="mailnest" selected>MailNest</option>'));
const selected = {multiple: true, selectedOptions: [{value: 'mailnest'}, {value: 'outlook'}], dataset: {}};
assert.equal(readConfigElementValue(selected, field), 'mailnest,outlook');
''')

    def test_regular_config_controls_expose_field_labels(self):
        self._run_config_control_js(r'''
for (const field of [
  {key: 'COUNT', label: '数量', type: 'int', value: 2},
  {key: 'RATIO', label: '比例', type: 'float', value: 0.5},
  {key: 'NAME', label: '名称', type: 'str', value: 'demo'},
  {key: 'LINES', label: '多行', type: 'list_str_multiline', value: ['a']},
]) {
  const markup = renderConfigControlMarkupV2(field);
  assert.ok(markup.includes(`aria-label="${field.label}"`));
}
''')

    def test_config_page_exposes_runtime_status_and_refreshes_after_save(self):
        self.assertIn('config-field-status-v2', CONFIG_JS)
        self.assertIn("f.invalid_env", CONFIG_JS)
        self.assertIn("f.restart", CONFIG_JS)
        self.assertIn("await loadConfig();", CONFIG_JS)

    def test_extract_link_section_summary_covers_platforms_and_payment_controls(self):
        self.assertIn("管理平台启用、默认模式、支付权限、平台凭据与并发。", CONFIG_JS)

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

    def test_config_fields_show_compact_help_without_detail_disclosures(self):
        self.assertIn('class="config-setting-short-help-v2"', CONFIG_JS)
        self.assertNotIn('config-field-help-v2', CONFIG_JS)
        self.assertNotIn('详细帮助', CONFIG_JS)
        self.assertIn('data-key="${attrEsc(f.key)}"', CONFIG_JS)
        self.assertIn('ROXY_ONE_PROFILE_PER_ACCOUNT:', CONFIG_JS)
        self.assertIn('ROXY_RANDOM_PROFILE_NAME_ON_CREATE:', CONFIG_JS)
        self.assertIn('display: block;', CONFIG_WORKSPACE_CSS)
        self.assertIn('padding: 6px 8px;', CONFIG_WORKSPACE_CSS)

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

  /* 待保存栏出现时，导航列表仍能滚动到最后一个菜单。 */
  #tab-config:has(#configSaveBarV2:not([hidden])) .config-nav-v2 {
    padding-bottom: 104px;
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

    def test_pending_save_bar_reserves_space_for_the_last_desktop_menu(self):
        self.assertIn(
            "#tab-config:has(#configSaveBarV2:not([hidden])) .config-nav-v2 {\n"
            "    padding-bottom: 104px;",
            FOUNDATION_CSS,
        )

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

    def test_config_domains_are_merged_into_menus_without_changing_schema_groups(self):
        self.assertIn("const group = configMenuGroupV2(rawGroup);", CONFIG_JS)
        self.assertIn("'注册与账号': ['注册主链路', '账号补全', '注册与账号']", CONFIG_JS)
        self.assertIn("'邮箱与验证码': ['邮箱 / OTP', '接码平台']", CONFIG_JS)
        self.assertIn("'浏览器': ['RoxyBrowser', '浏览器画像', '人工节奏']", CONFIG_JS)
        self.assertIn("'系统与维护': ['通用配置', 'WebUI 授权', '定时任务', '任务中心', '注册调试']", CONFIG_JS)
        self.assertIn('data-config-domain-v2', CONFIG_JS)
        self.assertIn("if (name === '注册主链路')", CONFIG_JS)
        self.assertIn("if (name === '账号补全')", CONFIG_JS)
        self.assertIn("if (name === '注册调试')", CONFIG_JS)

    def test_navigation_and_pending_save_behavior(self):
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
