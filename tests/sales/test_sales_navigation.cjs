const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../webui/static/js/shared/common.js'), 'utf8');
function fixture() {
  const calls = [], nodes = new Map();
  function node(id) {
    if (!nodes.has(id)) {
      const classes = new Set();
      nodes.set(id, {dataset: {}, classList: {toggle(name, value) {value ? classes.add(name) : classes.delete(name);},
        contains: name => classes.has(name)}});
    }
    return nodes.get(id);
  }
  node('tab-accounts').dataset.moduleView = 'active';
  const context = {document: {getElementById: node, querySelectorAll: () => []}, window: null,
    $: selector => node(selector.slice(1)), localStorage: {setItem() {}},
    ACTIVE_TAB: 'accounts', SHOW_ARCHIVED_ACCOUNTS: false,
    closePageDialogsForNavigation: () => calls.push(['close']), closeMobileSidebar() {},
    recordNavigationHistory() {}, updateNavigationBackButton() {},
    applyAccountsArchivedFilter: value => calls.push(['archive', value]),
    SalesPage: {setVisible: value => calls.push(['sales', value])},
    AccountsPage: {setVisible: value => calls.push(['accounts', value])}};
  context.window = context;
  const start = source.indexOf('const MODULE_VIEW_META =');
  const end = source.indexOf("$$('[data-module-subnav]').forEach", start);
  assert.ok(start >= 0 && end > start);
  vm.runInNewContext(source.slice(start, end), context);
  return {context, node, calls};
}
test('进入贩卖区切换面板但不改变原账号归档范围', () => {
  const {context, node, calls} = fixture();
  context.setModuleView('accounts', 'sales');
  assert.equal(node('tab-accounts').dataset.moduleView, 'sales');
  assert.equal(node('salesPanel').classList.contains('hidden'), false);
  assert.equal(node('accountsPanelV2').classList.contains('hidden'), true);
  assert.deepEqual(calls.filter(call => call[0] === 'archive'), []);
  assert.deepEqual(calls.filter(call => call[0] === 'sales'), [['sales', true]]);
  assert.deepEqual(calls.filter(call => call[0] === 'accounts'), [['accounts', false]]);
});
test('从贩卖区进入归档账号恢复账号面板并通知销售页隐藏', () => {
  const {context, node, calls} = fixture();
  context.setModuleView('accounts', 'sales');
  context.setModuleView('accounts', 'archived');
  assert.equal(node('salesPanel').classList.contains('hidden'), true);
  assert.equal(node('accountsPanelV2').classList.contains('hidden'), false);
  assert.deepEqual(calls.filter(call => call[0] === 'archive'), [['archive', true]]);
  assert.deepEqual(calls.filter(call => call[0] === 'sales').at(-1), ['sales', false]);
});
