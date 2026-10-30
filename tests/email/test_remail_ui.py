# -*- coding: utf-8 -*-
"""Remail 在现代配置、资源卡片和来源表单中的行为。"""

import json
from pathlib import Path
import subprocess
import unittest

from config.schema import CONFIG_SCHEMA


ROOT = Path(__file__).resolve().parents[2]


class RemailUiTests(unittest.TestCase):
    def run_js(self, assertions):
        fields = [field.metadata() for field in CONFIG_SCHEMA.fields if field.key.startswith("REMAIL_") or field.key == "EMAIL_SOURCE"]
        harness = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const root = process.argv[1];
const fields = JSON.parse(process.argv[2]);
const sourcePaths = {"account-email-change": "js/pages/accounts/email-change.js", "account-inspection": "js/pages/accounts/inspection.js", "account-tasks": "js/pages/operations/page.js", "accounts": "js/pages/accounts/page.js", "bootstrap": "js/bootstrap.js", "butler-import": "js/pages/email/butler-import.js", "codex": "js/pages/codex/page.js", "common": "js/shared/common.js", "config": "js/pages/config/page.js", "dashboard": "js/pages/dashboard/page.js", "email": "js/pages/email/page.js", "extract-workbench": "js/pages/extract_link/page.js", "jobs": "js/pages/registration/page.js"};
function read(name) { return fs.readFileSync(path.join(root, 'webui/static', sourcePaths[name]), 'utf8'); }
function extract(source, name) {
  let start = source.indexOf(`function ${name}(`);
  if (start > 5 && source.slice(start - 6, start) === 'async ') start -= 6;
  const end = source.indexOf('\n}', start);
  if (start < 0 || end < 0) throw new Error(`缺少函数 ${name}`);
  return source.slice(start, end + 2);
}
const mailSourceRoot = {
  innerHTML: '', value: '', disabled: false, hidden: true, children: [],
  parentNode: {insertBefore(node) { this.node = node; }},
};
const targets = new Map([['#mailSourceCards', mailSourceRoot]]);
function $(selector) {
  if (!targets.has(selector)) targets.set(selector, {
    innerHTML: '', value: '', disabled: false, hidden: true, children: [],
    appendChild(child) { this.children.push(child); },
  });
  return targets.get(selector);
}
const context = vm.createContext({
  assert, fields, $, CONFIG_PENDING_UPDATES: {}, esc: String, attrEsc: String,
  mailSourceCardsExpanded: false,
  POOL_SOURCE_LABELS: {all: '全部邮箱池', outlook: 'Outlook 邮箱池'},
  REGISTRATION_EMAIL_SOURCES: [], CAPABILITIES: {}, applyFeatureGates() {},
  api: async () => ({sources: [{value: 'remail', label: 'Remail', enabled: true}]}),
  apiCached: async (url) => url === '/api/capabilities'
    ? {email_sources: {remail: {enabled: true}}}
    : {sources: [{value: 'remail', label: 'Remail', enabled: true}]},
  document: {
    getElementById: (id) => id === 'mailSourceVisibilityControls'
      ? mailSourceRoot.parentNode.node || null
      : null,
    createElement: () => ({
      dataset: {}, innerHTML: '',
      querySelector: () => ({addEventListener() {}}),
    }),
  },
});
for (const [file, names] of Object.entries({
  common: ['isPlaceholderEmpty'],
  config: [
    'emailConfigSectionForKey', 'configSchemaOptions', 'configSchemaField', 'configDriverChoices', 'configRangeAttrs',
    'configListValuesV2', 'configListOptionValuesV2', 'configListSummaryV2', 'renderConfigMultiSelectV2',
    'configCountryCodesV2', 'configCountryNameV2', 'configCountryOptionsV2', 'configCountrySummaryV2',
    'renderConfigCountryChipsV2', 'renderConfigCountryOptionsV2', 'renderConfigCountryControlV2',
    'renderConfigControlMarkupV2',
  ],
  email: ['_mailSourceVisibility', '_ensureMailSourceVisibilityControls', 'renderMailSourceCards'],
  accounts: ['loadEmailChangeSources'],
  jobs: ['loadRegistrationEmailSources'],
})) for (const name of names) vm.runInContext(extract(read(file), name), context);
Promise.resolve(vm.runInContext(process.argv[3], context)).catch(error => { console.error(error); process.exitCode = 1; });
'''
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness, str(ROOT), json.dumps(fields), assertions],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_remail_fields_use_existing_form_controls(self):
        self.run_js(r'''
for (const field of fields.filter(item => item.key.startsWith('REMAIL_'))) {
  assert.equal(emailConfigSectionForKey(field.key)[0], 'Remail');
  const html = renderConfigControlMarkupV2({...field, value: field.default});
  assert.ok(html.includes(`data-key="${field.key}"`));
  if (field.secret) assert.ok(html.includes('type="password"'));
  if (field.options?.length) {
    assert.ok(html.includes('<select'));
    assert.equal((html.match(/<option /g) || []).length, field.options.length);
  }
  if (field.type === 'int') assert.ok(html.includes(`min="${field.range.min}"`));
}
const source = fields.find(item => item.key === 'EMAIL_SOURCE');
assert.ok(renderConfigControlMarkupV2({...source, value: 'remail'}).includes('<option value="remail" selected>Remail</option>'));
''')

    def test_remail_resource_card_is_on_demand_without_local_pool_action(self):
        self.run_js(r'''
renderMailSourceCards([{source: 'remail', label: 'Remail', enabled: true, kind: 'on_demand'}]);
const html = $('#mailSourceCards').innerHTML;
assert.ok(html.includes('Remail'));
assert.ok(html.includes('按需'));
assert.ok(html.includes('运行时领取 / 创建'));
assert.ok(!html.includes('data-mail-source'));
assert.ok(!html.includes('总数'));
''')

    def test_registration_and_email_change_accept_remail_from_source_api(self):
        self.run_js(r'''
(async () => {
  await loadRegistrationEmailSources();
  const registration = $('#regEmailSourceV2');
  assert.equal(registration.disabled, false);
  assert.ok(registration.innerHTML.includes('value="remail"'));
  assert.ok(registration.innerHTML.includes('Remail'));
  assert.equal(await loadEmailChangeSources('remail'), true);
  const change = $('#emailChangeSource');
  assert.equal(change.value, 'remail');
  assert.equal(change.disabled, false);
  assert.equal(change.children[0].textContent, 'Remail');
  assert.equal(change.children[0].disabled, false);
})()
''')


if __name__ == "__main__":
    unittest.main()
