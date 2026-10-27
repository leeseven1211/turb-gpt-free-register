const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const fullSource = fs.readFileSync(path.join(root, 'webui/static/js/modern/email.js'), 'utf8');
const source = fullSource.slice(0, fullSource.indexOf('function getPoolSource()'));

function createView() {
  const nodes = new Map();
  function element(id) {
    if (!nodes.has(id)) nodes.set(id, {
      id, textContent: '', innerHTML: '', hidden: false, disabled: false, checked: false, indeterminate: false,
      value: '', dataset: {}, attributes: {}, handlers: {}, open: false, isConnected: true,
      classList: {toggle() {}},
      addEventListener(name, handler) { this.handlers[name] = handler; },
      setAttribute(key, value) { this.attributes[key] = value; }, scrollIntoView() {}, focus() {},
      showModal() { this.open = true; }, close() { this.open = false; this.handlers.close?.(); },
    });
    return nodes.get(id);
  }
  const calls = [], navigation = [], copied = [], toasts = [], pagers = [];
  const summary = {enabled: true, sources: ['icloud_hide', 'outlook'], total: 2, max_children: 3, parents: [{source: 'icloud_hide', parent_id: 4, child_count: 2, max_children: 3}]};
  const allocations = {total: 60, items: [
    {id: 1, email: 'parent+abc123@example.test', parent_email: '<script>bad</script>@example.test', parent_id: 4, source: 'icloud_hide', state: 'available', can_disable: true, can_restore: false, created_at: '2026-10-20'},
    {id: 2, email: 'parent+def456@example.test', parent_email: 'parent@example.test', parent_id: 4, source: 'icloud_hide', state: 'reserved', registered_account_id: 5, root_task_id: 'root-1', can_disable: false, can_restore: false},
    {id: 3, email: 'parent+ghi789@example.test', parent_email: 'parent@example.test', source: 'icloud_hide', state: 'disabled', can_disable: false, can_restore: true},
  ]};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  let requestId = 0;
  const context = {
    URLSearchParams, OUTLOOK: [], PAGERS: {derivations: {page: 1, size: 50}},
    crypto: {randomUUID: () => `fixture-request-${++requestId}`},
    setModuleView: (module, view) => navigation.push([module, view]),
    document: {getElementById: element, activeElement: element('trigger')},
    esc, attrEsc: esc, formatDateTime: value => String(value ?? '-'), poolLabel: value => value,
    refreshColumnFilterStates() {}, renderColumnFilterOptions() {},
    debounce: fn => fn, setTimeout, clearTimeout,
    renderTableStateRow: (columns, title, detail) => `<tr><td colspan="${columns}">${title}${detail || ''}</td></tr>`,
    _renderPager: (id, total) => pagers.push({id, total}),
    copyText: async text => { copied.push(text); return true; },
    showToast: text => toasts.push(text),
    api: async (url, options) => { calls.push({url, options}); return url.includes('/summary?') ? summary : allocations; },
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.view = {state: EMAIL_DERIVATION_VIEW, load: loadEmailDerivationResources, loadSummary: loadEmailDerivationSummary, render: renderEmailDerivationAllocations, parentCell: _poolDerivationCell, showParent: showEmailDerivationParent, selectAll: syncEmailDerivationSelectAll, change: onEmailDerivationBodyChange, copy: copyEmailDerivationEmails};`, context);
  return {nodes, element, calls, navigation, copied, toasts, pagers, context, summary, allocations, view: context.view};
}

const settle = () => new Promise(resolve => setImmediate(resolve));

test('历史列表保留完整地址和归属，即使旧响应带能力标记也不渲染库存写操作', async () => {
  const {calls, element, view, pagers} = createView();
  await view.loadSummary();
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.includes('/summary?'));
  assert.ok(view.parentCell({source: 'icloud_hide', id: 4, email: 'parent@example.test'}).includes('历史子地址 2 个'));
  await view.load();
  const html = element('emailDerivationBody').innerHTML;
  assert.ok(html.includes('parent+abc123@example.test'));
  assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'));
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('可领取') && html.includes('归属已保留') && html.includes('已停用'));
  assert.ok(html.includes('账号 #5 · 任务 #root-1'));
  assert.doesNotMatch(html, /data-derivation-state|<button/);
  assert.equal(calls.filter(call => call.options).length, 0);
  assert.deepEqual(pagers.at(-1), {id: 'derivations', total: 60});
  assert.equal(element('emailDerivationTableWrap').attributes['aria-busy'], 'false');
});

test('所有表头条件与统一分页完整传递，切换来源清除精确母资源并重置选择', async () => {
  const {calls, element, navigation, context, view} = createView();
  view.showParent({dataset: {source: 'icloud_hide', derivationParent: '4', parentEmail: 'parent@example.test'}});
  assert.deepEqual(navigation, [['outlook', 'derivations']]);
  await view.load();
  assert.equal(new URL(calls.at(-1).url, 'https://fixture.test').searchParams.get('parent_id'), '4');
  for (const [id, value] of Object.entries({emailDerivationQuery: 'abc', emailDerivationParentQuery: 'parent', emailDerivationStateFilter: 'available', emailDerivationRelatedQuery: 'root-1', emailDerivationCreatedFrom: '2026-10-01', emailDerivationCreatedTo: '2026-10-27'})) element(id).value = value;
  context.PAGERS.derivations.page = 2;
  await view.load();
  const params = new URL(calls.at(-1).url, 'https://fixture.test').searchParams;
  for (const [key, value] of Object.entries({q:'abc', parent_q:'parent', source:'icloud_hide', state:'available', related_q:'root-1', created_from:'2026-10-01', created_to:'2026-10-27', page:'2', page_size:'50'})) assert.equal(params.get(key), value);
  view.selectAll(true);
  element('emailDerivationSourceFilter').value = 'outlook';
  element('emailDerivationSourceFilter').handlers.change();
  await settle();
  assert.equal(view.state.parentId, null);
  assert.equal(context.PAGERS.derivations.page, 1);
  assert.equal(element('emailDerivationSelectAll').checked, false);
  assert.equal(new URL(calls.at(-1).url, 'https://fixture.test').searchParams.get('source'), 'outlook');
});

test('加载失败保留已显示库存，后返回的旧请求不会覆盖当前筛选', async () => {
  const {element, context, allocations, view} = createView();
  await view.load();
  const previous = element('emailDerivationBody').innerHTML;
  context.api = async () => { throw new Error('服务暂不可用'); };
  await view.load();
  assert.equal(element('emailDerivationBody').innerHTML, previous);
  assert.match(element('emailDerivationListStatus').textContent, /加载失败.*服务暂不可用/);
  assert.equal(element('emailDerivationTableWrap').attributes['aria-busy'], 'false');
  let resolveFirst;
  context.api = () => new Promise(resolve => { resolveFirst = resolve; });
  const first = view.load();
  context.api = async () => ({...allocations, total: 7});
  await view.load();
  resolveFirst({...allocations, total: 2});
  await first;
  assert.equal(view.state.total, 7);
});

test('全选仅作用当前页，半选可见，复制优先选中且跨页保留地址', async () => {
  const {element, allocations, copied, view} = createView();
  await view.load();
  await view.copy();
  assert.equal(copied.at(-1), allocations.items.map(row => row.email).join('\n'));
  const checkbox = {checked: true, dataset: {derivationId: '1'}};
  view.change({target: {closest: () => checkbox}});
  assert.equal(element('emailDerivationSelectAll').indeterminate, true);
  await view.copy();
  assert.equal(copied.at(-1), allocations.items[0].email);
  view.render({items: [{...allocations.items[0], id: 4, email: 'next+abc@example.test'}], total: 60});
  view.selectAll(true);
  await view.copy();
  assert.equal(copied.at(-1), `${allocations.items[0].email}\nnext+abc@example.test`);
  view.selectAll(false);
  await view.copy();
  assert.equal(copied.at(-1), allocations.items[0].email);
});

test('母资源仅显示已存在的子地址历史，不展示生成额度或零用量入口', async () => {
  const {summary, view} = createView();
  summary.parents.push({source: 'outlook', parent_id: 4, child_count: 2, max_children: 8});
  await view.loadSummary();
  assert.match(view.parentCell({source: 'outlook', id: 4, email: 'history@example.test'}), /历史子地址 2 个/);
  assert.doesNotMatch(view.parentCell({source: 'outlook', id: 4}), /2\/8|生成|data-derivation-state/);
  assert.equal(view.parentCell({source: 'outlook', id: 15, email: 'fresh@example.test'}), '');
  summary.enabled = false;
  assert.equal(view.parentCell({source: 'icloud_hide', id: 15}), '');
  assert.match(view.parentCell({source: 'icloud_hide', id: 4}), /历史子地址 2 个/);
});

test('空历史列表提示到 Email Butler 管理子邮箱', async () => {
  const {element, context, view} = createView();
  context.api = async () => ({items: [], total: 0});
  await view.load();
  assert.match(element('emailDerivationBody').innerHTML, /Email Butler/);
  assert.doesNotMatch(element('emailDerivationBody').innerHTML, /点击.*生成/);
});

test('库存列表注册统一分页，翻页与每页条数驱动库存加载', () => {
  const common = fs.readFileSync(path.join(root, 'webui/static/js/modern/common.js'), 'utf8');
  const elements = new Map();
  let reloads = 0;
  const context = vm.createContext({
    document: {getElementById: id => { if (!elements.has(id)) elements.set(id, {innerHTML: ''}); return elements.get(id); }},
    EMAIL_DERIVATION_VIEW: {total: 101}, loadEmailDerivationResources: () => reloads++,
    refreshJobs() {}, loadAccounts() {}, loadOutlook() {}, loadCodex() {}, loadAccountTasks() {},
  });
  vm.runInContext(common.slice(common.indexOf('// ---------- 分页状态 ----------'), common.indexOf('// ---------- 统一列表列宽 ----------')), context);
  vm.runInContext("_renderPager('derivations', 101); pagerGoTo('derivations', 2); pagerSetSize('derivations', 20)", context);
  assert.equal(reloads, 2);
  assert.match(elements.get('pager-derivations-v2').innerHTML, /共 101 条/);
  assert.equal(vm.runInContext('PAGERS.derivations.page', context), 1);
  assert.equal(vm.runInContext('PAGERS.derivations.size', context), 20);
});


test('没有任务号的历史归属仍不被标为尚未领取，零库存分页保持第一页', async () => {
  const {element, context, view} = createView();
  view.render({total: 1, items: [{id: 8, email: 'history+abc@example.test', state: 'reserved'}]});
  assert.doesNotMatch(element('emailDerivationBody').innerHTML, /尚未领取/);
  assert.match(element('emailDerivationBody').innerHTML, /归属已保留/);
  context.PAGERS.derivations.page = 9;
  context.api = async () => ({total: 0, items: []});
  await view.load();
  assert.equal(context.PAGERS.derivations.page, 1);
  assert.equal(element('emailDerivationSelectAll').disabled, true);
  assert.equal(element('btnCopyEmailDerivation').disabled, true);
});
