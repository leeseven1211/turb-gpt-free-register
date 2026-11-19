# -*- coding: utf-8 -*-
import json
import subprocess
from pathlib import Path

from core.storage import records as record_store
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class LiveCheckStatusUiTests(PostgresTestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def test_accounts_api_exposes_failed_probe_http_status(self):
        self.seed(record_store.ACCOUNTS, [{
            "email": "rejected@example.com",
            "access_token": "still-present",
            "token_expires_at": "2099-01-01T00:00:00Z",
            "token_expired": False,
            "live_check_status": "failed",
            "live_check_http_status": 401,
            "live_check_error": "现有 accessToken 已过期或失效，请点击“刷新AT”",
        }])

        response = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&q=rejected@example.com",
            headers=self.headers,
        )

        self.assertEqual(200, response.status_code)
        account = response.get_json()["items"][0]
        self.assertFalse(account["token_expired"])
        self.assertEqual("failed", account["live_check_status"])
        self.assertEqual(401, account["live_check_http_status"])

    def test_account_ui_renders_clickable_token_states(self):
        modern = self.client.get("/static/js/pages/accounts/page.js")
        foundation = self.client.get("/static/css/shared/ui-foundation.css")
        try:
            modern_source = modern.get_data(as_text=True)
            foundation_source = foundation.get_data(as_text=True)
            self.assertIn("live_check_http_status", modern_source)
            self.assertIn("data-account-copy-secret=\"access_token\"", modern_source)
            self.assertIn("失效 ·", modern_source)
            self.assertIn("Token 到期：", modern_source)
            self.assertIn("acc-v2-token-state", modern_source)
            self.assertNotIn("acc-v2-token-alert", modern_source)
            self.assertIn(".accounts-table-v2 .acc-v2-token-state.is-normal", foundation_source)
            self.assertIn(".accounts-table-v2 .acc-v2-token-state.is-expired", foundation_source)
            self.assertIn(".accounts-table-v2 .acc-v2-token-state.is-invalid", foundation_source)
        finally:
            modern.close()
            foundation.close()
        rendered = subprocess.run(["node", "--input-type=commonjs", "-e", r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const h = require('./tests/frontend_vue_loader.cjs').createVueHarness();
for (const key of ['NodeFilter', 'HTMLInputElement']) globalThis[key] = h.document.defaultView[key];
const scope = {window: {}, URLSearchParams};
vm.runInNewContext(fs.readFileSync('webui/static/js/shared/account-query.js', 'utf8'), scope);
const values = ['has', 'expired', 'invalid_401', 'invalid_403', 'invalid_other', 'none'];
const Table = h.load('src/features/accounts/AccountsTable.vue').default;
const table = h.mount(Table, {props: {
  items: [], selected: new Set(), query: scope.window.AccountQuery.normalize(),
  facets: {token: values.map(value => ({value, count: 1}))}, presentation: {facetLabel: (_, value) => value},
  loading: false, error: '', invalidSearch: false, stale: false, visible: true,
  pageSelected: false, pageIndeterminate: false, openFilter: null,
}});
(async () => {
  try {
    await table.get('thead th.col-token button.tc-column-filter-trigger').trigger('click');
    assert.deepEqual(table.emitted('update:openFilter'), [['token']]);
    await table.setProps({openFilter: 'token'});
    const inputs = [...h.document.querySelectorAll('.list-filter-popover input[type="checkbox"][value]')];
    assert.deepEqual(inputs.map(input => input.value), values);
    for (const input of inputs) {
      input.checked = true; input.dispatchEvent(new Event('change', {bubbles: true})); await h.nextTick(); input.checked = false;
    }
    assert.deepEqual(table.emitted('filter'), values.map(value => ['token', [value]]));
    console.log('ok');
  } finally {await table.setProps({openFilter: null}); await new Promise(resolve => setTimeout(resolve, 0)); h.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
"""], cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, check=False)
        self.assertEqual(0, rendered.returncode, rendered.stderr or rendered.stdout)
        self.assertEqual("ok", rendered.stdout.strip())

    def test_account_ui_renders_account_status_as_a_separate_column(self):
        modern = self.client.get("/", headers=self.headers).get_data(as_text=True)
        self.assertIn('id="accounts-list-root"', modern)
        rendered = subprocess.run(["node", "--input-type=commonjs", "-e", r"""
const fs = require('node:fs'), vm = require('node:vm');
const h = require('./tests/frontend_vue_loader.cjs').createVueHarness();
for (const key of ['NodeFilter', 'HTMLInputElement']) globalThis[key] = h.document.defaultView[key];
const scope = {window: {}, URLSearchParams};
vm.runInNewContext(fs.readFileSync('webui/static/js/shared/account-query.js', 'utf8'), scope);
const Table = h.load('src/features/accounts/AccountsTable.vue').default;
const table = h.mount(Table, {props: {
  items: [], selected: new Set(), query: scope.window.AccountQuery.normalize(),
  facets: {account_status: [{value: 'deactivated', count: 1}]},
  presentation: {facetLabel: (_, value) => value},
  loading: false, error: '', invalidSearch: false, stale: false, visible: true,
  pageSelected: false, pageIndeterminate: false, openFilter: null,
}});
(async () => {
  try {
    const header = table.get('thead th.col-account-status');
    await header.get('button.tc-column-filter-trigger').trigger('click');
    const opened = table.emitted('update:openFilter');
    await table.setProps({openFilter: 'account_status'});
    const option = h.document.querySelector('.list-filter-popover input[value="deactivated"]');
    option.checked = true; option.dispatchEvent(new Event('change', {bubbles: true}));
    await h.nextTick();
    console.log(JSON.stringify({label: header.text(), tokenColumn: table.get('thead th.col-token').text(),
      opened, changed: table.emitted('filter')}));
  } finally { await table.setProps({openFilter: null}); await new Promise(resolve => setTimeout(resolve, 0)); h.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
"""], cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, check=False)
        self.assertEqual(0, rendered.returncode, rendered.stderr or rendered.stdout)
        column = json.loads(rendered.stdout)
        self.assertIn("账号状态", column["label"])
        self.assertIn("Token", column["tokenColumn"])
        self.assertEqual([["account_status"]], column["opened"])
        self.assertEqual([["account_status", ["deactivated"]]], column["changed"])

        response = self.client.get("/static/js/pages/accounts/page.js")
        try:
            source = response.get_data(as_text=True)
            self.assertIn("accountStatus", source)
            self.assertIn("已废号", source)
            self.assertIn("Token 异常", source)
            self.assertIn("查活失败", source)
            self.assertIn("待查活", source)
        finally:
            response.close()
