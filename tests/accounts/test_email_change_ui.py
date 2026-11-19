from __future__ import annotations

import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class _ElementCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def by_id(self, element_id: str):
        return next(
            ((tag, attrs) for tag, attrs in self.elements if attrs.get("id") == element_id),
            None,
        )


class EmailChangeUiTests(unittest.TestCase):
    """Run the actual Vue dialog and owner; these UI contracts require no database."""

    def run_vue(self, assertions: str):
        harness = r"""
const assert = require('node:assert/strict');
const {createVueHarness} = require('./tests/frontend_vue_loader.cjs');
const vue = createVueHarness();
const EmailChange = vue.load('src/features/accounts/EmailChange.vue').default;
vue.document.body.innerHTML = '<div id="accountEmailChangeHost"></div>';
const calls = {requests: [], tasks: [], refresh: [], receipts: []};
const context = {accountIds: ['7', '8'], expectedEmails: {'7': 'old@example.test', '8': 'eight@example.test'},
  rowHints: [{id: 7, email: 'old@example.test', email_source: 'outlook'}],
  querySnapshot: {schema_version: 1, entity: 'account', q: '', archived: '0', filters: {}}, archived: '0'};
const deps = {
  request: async (url, options) => {
    calls.requests.push({url, options});
    return url === '/api/email-sources' ? {sources: [
      {value: 'outlook', label: 'Outlook', enabled: true},
      {value: 'icloud_hide', label: 'iCloud', enabled: false, reason: '尚未配置'},
    ]} : {ok: true, task_id: 99, started_count: 2, skipped_count: 1};
  },
  notify() {}, syncModalScrollLock() {},
  refreshAccounts: value => calls.refresh.push(value),
  openTasks: value => calls.tasks.push(value),
  recordReceipt: value => calls.receipts.push(value),
};
const wrapper = vue.mount(EmailChange, {props: {deps}});
const byId = id => vue.document.getElementById(id);
async function settle() { for (let i = 0; i < 10; i++) await vue.nextTick(); }
async function submit() {
  byId('emailChangeForm').dispatchEvent(new vue.document.defaultView.Event('submit', {bubbles: true, cancelable: true}));
  await settle();
}
(async () => {
  try {
""" + assertions + r"""
    console.log('ok');
  } finally { vue.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
        self.assertEqual("ok", result.stdout.strip())

    def test_ui_renders_source_only_accessible_dialog(self):
        self.run_vue(r"""
    wrapper.vm.openSingle(7, context); await settle();
    const modal = byId('emailChangeModal');
    assert.equal(modal.getAttribute('role'), 'dialog');
    assert.equal(modal.getAttribute('aria-modal'), 'true');
    assert.equal(modal.getAttribute('aria-labelledby'), 'emailChangeTitle');
    assert.equal(modal.getAttribute('aria-hidden'), 'false');
    assert.equal(modal.parentElement.id, 'accountEmailChangeHost');
    const source = byId('emailChangeSource');
    assert.equal(source.tagName, 'SELECT');
    assert.equal(source.name, 'email_source');
    assert.equal(source.required, true);
    assert.equal(byId('emailChangeTarget'), null);
    assert.match(byId('emailChangeNote').textContent, /不会启动浏览器/);
""")

    def test_modern_submit_posts_only_source_and_opens_email_change_tasks(self):
        self.run_vue(r"""
    context.accountIds = ['7'];
    const captured = JSON.parse(JSON.stringify(context));
    wrapper.vm.openSingle(7, context); await settle();
    context.rowHints[0].email = 'changed-after-open@example.test';
    context.accountIds = ['99'];
    await submit();
    const request = calls.requests.find(call => call.options?.method === 'POST');
    assert.equal(request.url, '/api/accounts/7/email-change');
    assert.deepEqual(JSON.parse(request.options.body), {email_source: 'outlook'});
    assert.deepEqual(calls.tasks, [{type: 'email_change', target: 'old@example.test'}]);
    assert.deepEqual(calls.refresh, [captured]);
    assert.equal(calls.receipts[0].accountId, 7);
    assert.equal(calls.receipts[0].oldEmail, 'old@example.test');
""")

    def test_modern_submit_bulk_email_change_posts_selected_accounts(self):
        self.run_vue(r"""
    context.accountIds = ['7', '8', '7'];
    const captured = JSON.parse(JSON.stringify({...context, accountIds: ['7', '8']}));
    wrapper.vm.openBulk(context); await settle();
    context.accountIds = ['99'];
    await submit();
    const request = calls.requests.find(call => call.options?.method === 'POST');
    assert.equal(request.url, '/api/accounts/email-change-bulk');
    assert.deepEqual(JSON.parse(request.options.body), {account_ids: [7, 8], email_source: 'outlook'});
    assert.deepEqual(calls.tasks, [{type: 'email_change', target: ''}]);
    assert.deepEqual(calls.refresh, [captured]);
""")

    def test_ui_exposes_bulk_email_change_button_for_selected_accounts(self):
        source = (ROOT / "webui/templates/index.html").read_text()
        parser = _ElementCollector()
        parser.feed(source)
        self.assertIsNotNone(parser.by_id("accounts-list-root"))
        self.assertIsNotNone(parser.by_id("accountEmailChangeHost"))
        self.assertIsNone(parser.by_id("emailChangeModal"))
        self.run_vue(r"""
    const Toolbar = vue.load('src/features/accounts/AccountsToolbar.vue').default;
    const invoked = [];
    const toolbar = vue.mount(Toolbar, {props: {
      state: {selectedCount: 0, archived: false}, capabilities: {}, getContext: () => context,
      invoke: (action, captured, trigger) => invoked.push({action, captured, trigger}),
      runtime: {storage: vue.document.defaultView.localStorage, requestFrame: callback => requestAnimationFrame(callback), cancelFrame: handle => cancelAnimationFrame(handle), addStorageListener: () => () => {}},
    }});
    await settle();
    const button = byId('btnEmailChangeSelectedV2');
    assert.equal(button.tagName, 'BUTTON'); assert.equal(button.textContent, '批量换绑邮箱');
    assert.equal(button.disabled, true); button.click(); assert.equal(invoked.length, 0);
    await toolbar.setProps({state: {selectedCount: 2, archived: false}}); await settle();
    assert.equal(button.disabled, false); button.click(); await settle();
    assert.equal(invoked.length, 1); assert.equal(invoked[0].action, 'openBulkEmailChangeForSelectedAccounts');
    assert.equal(invoked[0].captured, context); assert.equal(invoked[0].trigger, button);
""")

    def test_ui_loads_email_change_sources_and_disables_unavailable_choices(self):
        self.run_vue(r"""
    wrapper.vm.openSingle(7, context); await settle();
    assert.equal(calls.requests[0].url, '/api/email-sources');
    const source = byId('emailChangeSource');
    const unavailable = source.querySelector('option[value="icloud_hide"]');
    assert.equal(unavailable.disabled, true);
    assert.equal(unavailable.title, '尚未配置');
    assert.equal(unavailable.dataset.reason, '尚未配置');
    assert.match(unavailable.textContent, /不可用/);
    assert.equal(source.value, 'outlook');
""")
