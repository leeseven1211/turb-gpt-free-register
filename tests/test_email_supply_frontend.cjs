const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'webui/static/js/modern/dashboard.js'), 'utf8');
const pools = ['outlook', 'generic_api', 'cloudflare_domain', 'icloud_hide', 'email_butler'];
const localSupply = () => ({
  scope: 'local_pool', status: 'known', total: 20, available: 12, used: 6, failed: 2, reason: '',
  sources: pools.map((source, index) => ({source, label: source, kind: 'local_pool', status: 'known', total: index === 3 ? 20 : 0, available: index === 3 ? 12 : 0, used: index === 3 ? 6 : 0, failed: index === 3 ? 2 : 0})),
});
const summary = supply => ({accounts: 24, outlook_total: 0, outlook_available: 0, outlook_used: 0, outlook_failed: 0, email_supply: supply});
const dashboard = supply => ({
  accounts: {total: 0, plans: {}},
  email: {local_available: 0, supply, sources: [{source: 'email_butler', label: 'Butler 连接', kind: 'on_demand', enabled: true}]},
  jobs: {total: 0, counts: {}, today_counts: {}}, proxy: {platform: 'none'}, codex: {},
});
function createView(responses = {}) {
  const nodes = new Map(), calls = [], toasts = [], ready = [];
  const element = selector => {
    if (!nodes.has(selector)) nodes.set(selector, {
      innerHTML: '', title: '', disabled: false, text: '',
      get textContent() { return this.text; }, set textContent(value) { this.text = String(value); },
      addEventListener() {},
    });
    return nodes.get(selector);
  };
  const request = async url => {
    calls.push(url);
    const response = responses[url] ?? ({'/api/summary': summary(localSupply()), '/api/capabilities': {}, '/api/dashboard': dashboard(localSupply())}[url]);
    if (response instanceof Error) throw response;
    if (response === undefined) throw new Error(`禁止额外供给查询 ${url}`);
    return typeof response === 'function' ? response() : response;
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const context = {
    $: element, document: {addEventListener() {}}, summaryLoading: false, dashboardLoading: false,
    CAPABILITIES: {email_sources: {icloud_hide: {enabled: false}}}, api: request, apiCached: request, esc, attrEsc: esc, pill: String,
    localStorage: {getItem() { return null; }, setItem() {}},
    showToast: value => toasts.push(value), markViewReady: value => ready.push(value),
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nglobalThis.view = {loadSummary, loadDashboard, card: overviewRegistryCard};`, context);
  return {view: context.view, element, calls, toasts, ready};
}

test('注册统计仅用本地汇总，保留本地 HME 可用库存', async () => {
  const {view, element, calls} = createView();
  await view.loadSummary();
  for (const [selector, expected] of [['#statAccounts', '24'], ['#statOutlook', '20'], ['#statAvailable', '12'], ['#statUsed', '6'], ['#statFailed', '2']]) assert.equal(element(selector).textContent, expected);
  assert.deepEqual(calls, ['/api/summary']);
  assert.match(element('#registrationEmailSupplyHint').textContent, /本地库存/);
  assert.match(element('#registrationEmailSupplyHint').textContent, /用完.*手动导入/);
});

test('汇总失败时库存显示读取失败，不保留旧数字或显示零', async () => {
  const responses = {};
  const {view, element, calls} = createView(responses);
  await view.loadSummary();
  responses['/api/summary'] = new Error('offline');
  await view.loadSummary();
  assert.equal(element('#statAvailable').textContent, '读取失败');
  assert.deepEqual(calls, ['/api/summary', '/api/summary']);
});

test('本地库存读取错误不回退兼容字段中的零', async () => {
  const supply = {...localSupply(), status: 'error', total: null, available: null, used: null, failed: null, reason: '本地库存读取失败'};
  const {view, element} = createView({'/api/summary': summary(supply)});
  await view.loadSummary();
  for (const selector of ['#statOutlook', '#statAvailable', '#statUsed', '#statFailed']) assert.equal(element(selector).textContent, '读取失败');
  assert.ok(element('#registrationEmailSupplyHint').textContent.includes(supply.reason));
});

test('本地库存为空显示确定的零', async () => {
  const supply = {...localSupply(), total: 0, available: 0, used: 0, failed: 0};
  const {view, element} = createView({'/api/summary': summary(supply)});
  await view.loadSummary();
  assert.equal(element('#statAvailable').textContent, '0');
});

test('概览只读本地 dashboard 汇总，不请求远端库存接口', async () => {
  const {view, element, calls, ready, toasts} = createView();
  await view.loadDashboard();
  assert.deepEqual(calls.sort(), ['/api/capabilities', '/api/dashboard']);
  assert.match(element('#overviewMetrics').innerHTML, /<strong>12<\/strong>/);
  assert.match(element('#overviewMetrics').innerHTML, /本地/);
  assert.deepEqual(ready, ['overview']);
  assert.deepEqual(toasts, []);
});

test('本地库存详情优先五个池的数据，配置停用不隐藏库存', () => {
  const {view} = createView();
  const html = view.card('panel-email').render(dashboard(localSupply()));
  for (const source of pools) assert.ok(html.includes(source), html);
  assert.match(html, /<strong>12<\/strong>/);
  assert.doesNotMatch(html, /按需|运行时租用|Butler 连接/);
});
