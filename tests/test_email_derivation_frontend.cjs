const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const fullSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/email.js'), 'utf8');
const source = fullSource.slice(0, fullSource.indexOf('function getPoolSource()'));

function createView() {
  const nodes = new Map();
  for (const id of ['emailDerivationPanel', 'emailDerivationSummary', 'emailDerivationSource', 'emailDerivationParentFilter', 'btnClearDerivationParent', 'btnRefreshEmailDerivation', 'emailDerivationTableWrap', 'emailDerivationBody', 'emailDerivationListStatus', 'btnDerivationPrev', 'btnDerivationNext']) {
    nodes.set(id, {textContent: '', innerHTML: '', hidden: false, disabled: false, value: '', attributes: {}, handlers: {},
      addEventListener(event, handler) { this.handlers[event] = handler; },
      setAttribute(key, value) { this.attributes[key] = value; }, scrollIntoView() {},
    });
  }
  const calls = [];
  const navigation = [];
  const summary = {enabled: true, sources: ['icloud_hide', 'outlook'], total: 2, max_children: 3, parents: [{source: 'icloud_hide', parent_id: 4, child_count: 2, max_children: 3}]};
  const allocations = {total: 60, items: [{id: 1, email: 'parent+abc123@example.test', parent_email: '<script>bad</script>@example.test', parent_id: 4, source: 'icloud_hide', state: 'used', registered_account_id: 5, root_task_id: 'root-1', created_at: '2026-10-20'}]};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const context = {
    URLSearchParams, OUTLOOK: [],
    setModuleView: (module, view) => navigation.push([module, view]),
    document: {getElementById(id) { return nodes.get(id) || null; }},
    esc, attrEsc: esc, formatDateTime: value => String(value ?? '-'), poolLabel: value => value,
    api: async url => { calls.push(url); return url.includes('/summary?') ? summary : allocations; },
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.view = {state: EMAIL_DERIVATION_VIEW, load: loadEmailDerivationResources, loadSummary: loadEmailDerivationSummary, render: renderEmailDerivationAllocations, parentCell: _poolDerivationCell, showParent: showEmailDerivationParent};`, context);
  return {nodes, calls, navigation, context, summary, allocations, view: context.view};
}

test('邮箱列表只读取概况，子地址页面直接读取台账并保留完整地址与母资源额度', async () => {
  const {nodes, calls, view} = createView();
  await view.loadSummary();
  assert.equal(calls.length, 1);
  assert.ok(calls[0].includes('/summary?'));
  assert.ok(nodes.get('emailDerivationSummary').textContent.includes('每母邮箱 3 个额度'));
  const parent = view.parentCell({source: 'icloud_hide', id: 4, email: 'parent@example.test'});
  assert.ok(parent.includes('原地址 · 子地址 2/3'));
  assert.ok(parent.includes('data-derivation-parent="4"'));
  await view.load();
  assert.equal(calls.length, 3);
  const html = nodes.get('emailDerivationBody').innerHTML;
  assert.ok(html.includes('parent+abc123@example.test'));
  assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('账号 #5 · 任务 #root-1'));
  assert.equal(nodes.get('btnDerivationPrev').disabled, true);
  assert.equal(nodes.get('btnDerivationNext').disabled, false);
  assert.equal(nodes.get('emailDerivationTableWrap').attributes['aria-busy'], 'false');
});

test('母资源筛选与来源绑定，切换来源清除旧母资源并重置分页', async () => {
  const {nodes, calls, navigation, view} = createView();
  view.showParent({dataset: {source: 'icloud_hide', derivationParent: '4', parentEmail: 'parent@example.test'}});
  assert.deepEqual(navigation, [['outlook', 'derivations']]);
  await view.load();
  assert.ok(calls.at(-1).includes('source=icloud_hide'));
  assert.ok(calls.at(-1).includes('parent_id=4'));
  assert.equal(nodes.get('btnClearDerivationParent').hidden, false);
  assert.equal(nodes.get('emailDerivationParentFilter').textContent, '母邮箱：parent@example.test');
  view.state.page = 2;
  nodes.get('emailDerivationSource').handlers.change({currentTarget: {value: 'outlook'}});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(view.state.parentId, null);
  assert.equal(view.state.page, 1);
  assert.ok(!calls.at(-1).includes('parent_id'));
  assert.ok(calls.at(-1).includes('source=outlook'));
  assert.equal(nodes.get('btnClearDerivationParent').hidden, true);
});

test('读取失败保留已显示数据并恢复刷新按钮', async () => {
  const {nodes, context, view} = createView();
  await view.load();
  const previous = nodes.get('emailDerivationBody').innerHTML;
  context.api = async () => { throw new Error('private-token'); };
  await view.load();
  assert.equal(nodes.get('emailDerivationBody').innerHTML, previous);
  assert.equal(nodes.get('btnRefreshEmailDerivation').disabled, false);
  assert.equal(nodes.get('emailDerivationTableWrap').attributes['aria-busy'], 'false');
  assert.equal(nodes.get('emailDerivationListStatus').textContent, '子地址加载失败，请刷新重试。');
  assert.ok(!nodes.get('emailDerivationSummary').textContent.includes('private'));
});

test('较早请求晚返回不会覆盖新的来源筛选', async () => {
  const {nodes, context, summary, view} = createView();
  const pending = [];
  context.api = () => new Promise(resolve => { pending.push(resolve); });
  const first = view.load();
  view.state.source = 'outlook';
  context.api = async () => ({...summary, total: 7});
  await view.load();
  pending.forEach(resolve => resolve({...summary, total: 2}));
  await first;
  assert.ok(nodes.get('emailDerivationSummary').textContent.includes('已生成 7 个'));
});


test('零分配母资源展示默认额度，并能按完整母资源身份打开空台账', async () => {
  const {nodes, calls, context, summary, view} = createView();
  summary.parents = [];
  summary.total = 0;
  context.api = async url => {
    calls.push(url);
    return url.includes('/summary?') ? summary : {total: 0, items: []};
  };
  await view.load();
  const html = view.parentCell({source: 'icloud_hide', id: 12, email: 'fresh@example.test'});
  assert.ok(html.includes('原地址 · 子地址 0/3'));
  assert.ok(html.includes('data-derivation-parent="12"'));
  assert.ok(html.includes('data-source="icloud_hide"'));
  assert.ok(html.includes('data-parent-email="fresh@example.test"'));
  view.showParent({dataset: {source: 'icloud_hide', derivationParent: '12', parentEmail: 'fresh@example.test'}});
  await view.load();
  const request = new URL(calls.at(-1), 'https://fixture.test');
  assert.equal(request.searchParams.get('source'), 'icloud_hide');
  assert.equal(request.searchParams.get('parent_id'), '12');
  assert.equal(request.searchParams.get('page'), '1');
  assert.ok(nodes.get('emailDerivationBody').innerHTML.includes('当前筛选下没有子地址'));
  assert.equal(nodes.get('btnDerivationPrev').disabled, true);
  assert.equal(nodes.get('btnDerivationNext').disabled, true);
});

test('默认零用量仅用于启用且支持的来源，历史计数与单母额度优先保留', async () => {
  const {summary, view} = createView();
  summary.parents.push({source: 'outlook', parent_id: 4, child_count: 2, max_children: 8});
  summary.parents.push({source: 'outlook', parent_id: 9, child_count: 1, max_children: 0});
  await view.load();
  assert.ok(view.parentCell({source: 'outlook', id: 4, email: 'override@example.test'}).includes('子地址 2/8'));
  assert.ok(view.parentCell({source: 'outlook', id: 9, email: 'zero-limit@example.test'}).includes('子地址 1/0'));
  summary.max_children = 6;
  assert.ok(view.parentCell({source: 'outlook', id: 15, email: 'fresh@example.test'}).includes('子地址 0/6'));
  assert.ok(view.parentCell({source: 'outlook', id: 16, email: 'new-override@example.test', derivation_policy: {max_children: 4}}).includes('子地址 0/4'));
  assert.equal(view.parentCell({source: 'outlook', id: 17, email: 'parent-disabled@example.test', derivation_policy: {enabled: false}}), '');
  summary.sources = ['icloud_hide', 'generic_api'];
  assert.equal(view.parentCell({source: 'outlook', id: 15, email: 'not-enabled@example.test'}), '');
  assert.equal(view.parentCell({source: 'generic_api', id: 15, email: 'not-supported@example.test'}), '');
  summary.enabled = false;
  assert.equal(view.parentCell({source: 'icloud_hide', id: 15, email: 'disabled@example.test'}), '');
  assert.ok(view.parentCell({source: 'outlook', id: 4, email: 'history@example.test'}).includes('子地址 2/8'));
  assert.ok(view.parentCell({source: 'icloud_hide', id: 4, email: 'history-hme@example.test'}).includes('子地址 2/3'));
});
