// The Python contract suite exercises current Vue source through this offline loader.
// No built asset, historical baseline, Flask application or database is loaded.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createVueHarness} = require('../frontend_vue_loader.cjs');

const root = path.resolve(__dirname, '../..');
const template = fs.readFileSync(path.join(root, 'webui/templates/index.html'), 'utf8');
const common = fs.readFileSync(path.join(root, 'webui/static/js/shared/common.js'), 'utf8');
const h = createVueHarness();
const browserGlobals = new Map();
for (const name of ['NodeFilter', 'HTMLInputElement', 'HTMLTextAreaElement', 'HTMLSelectElement']) {
  browserGlobals.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
  Object.defineProperty(globalThis, name, {configurable: true, writable: true, value: h.document.defaultView[name]});
}
const Page = h.load('src/features/proxy/ProxyTrafficPage.vue').default;
const {fixtureApi, fixturePool, fixtureSummary, fixtureLease, fixtureTraffic, fixturePage} = h.load('src/features/proxy/fixtures.ts');
const {createProxyApi, normalizeProxyPage} = h.load('src/api/proxy.ts');
const results = {};
Object.defineProperty(h.document, 'hidden', {configurable: true, value: false});
h.document.defaultView.HTMLDialogElement.prototype.showModal = function () {this.open = true;};
h.document.defaultView.HTMLDialogElement.prototype.close = function () {this.open = false; this.dispatchEvent(new Event('close'));};
async function settle() {await h.nextTick();for (let i = 0; i < 20; i++) await Promise.resolve();await h.nextTick();await new Promise(resolve => setImmediate(resolve));}
function mount(view = 'records', api = fixtureApi()) {
  return h.mount(Page, {props: {deps: {api, visible: true, view, facetLabel: (_group, value) => value}}});
}
async function contract(name, action) {
  const previousFetch = globalThis.fetch;
  try {await action();results[name] = {ok: true};}
  catch (error) {results[name] = {ok: false, error: error.stack || String(error)};}
  finally {globalThis.fetch = previousFetch;h.cleanup();}
}
async function main() {
  await contract('workspace', async () => {
    const shell = new h.document.defaultView.DOMParser().parseFromString(template, 'text/html');
    assert.equal(shell.querySelectorAll('#proxy-page-root').length, 1);
    assert.ok(shell.querySelector('[data-tab="proxy-traffic"]'));
    assert.ok(shell.querySelector('#tab-proxy-traffic #proxy-page-root'));
    const w = mount();await settle();
    assert.deepEqual(w.findAll('[role="tab"]').map(tab => tab.attributes('data-proxy-view')), ['current', 'history', 'traffic']);
    for (const name of ['current', 'history', 'traffic']) assert.ok(w.get(`[data-proxy-table="${name}"]`).exists());
    await w.get('[data-proxy-view="history"]').trigger('click');
    assert.equal(w.get('[data-proxy-view="history"]').attributes('aria-selected'), 'true');
    assert.equal(w.get('[data-proxy-panel="history"]').element.style.display, '');
  });
  await contract('no_manual_refresh_card', async () => {
    const w = mount();await settle();
    assert.equal(w.find('#btnRefreshProxyTraffic').exists(), false);
    assert.equal(w.find('.proxy-traffic-head').exists(), false);
    assert.equal(w.find('.proxy-traffic-toolbar').exists(), false);
    assert.equal(w.findAll('button').some(button => /^(?:手动)?刷新$/.test(button.text())), false);
    assert.equal(w.findAll('h2').some(heading => heading.text() === '代理与流量'), false);
    assert.ok(w.get('[role="tablist"]').exists());
    assert.ok(w.get('[data-proxy-summary="totalBytes"]').exists());
  });
  await contract('header_filters', async () => {
    const w = mount();await settle();
    for (const name of ['current', 'history', 'traffic']) {
      const table = w.get(`[data-proxy-table="${name}"]`);
      for (const label of ['搜索', '状态', '时间']) assert.ok(table.find(`thead button[aria-label="筛选${label}"]`).exists(), `${name}: ${label}`);
      assert.equal(table.find('thead button[aria-label="筛选用途"]').exists(), name !== 'traffic');
    }
    await w.get('[data-proxy-table="current"] button[aria-label="筛选状态"]').trigger('click');await settle();
    const option = h.document.querySelector('[data-proxy-filter-option="leased"]');
    assert.ok(option);option.click();await settle();
    assert.match(w.get('.list-filter-summary').text(), /当前状态：租约中/);
    assert.equal(w.get('[data-proxy-table="current"] button[aria-label="筛选状态"]').attributes('data-active'), '');
  });
  await contract('filter_sync', async () => {
    const requests = [], api = fixtureApi();
    api.page = async (view, query) => {requests.push({view, query: {...query}});return fixturePage(view);};
    const w = mount('records', api);await settle();requests.length = 0;
    await w.get('[data-proxy-table="current"] button[aria-label="筛选状态"]').trigger('click');await settle();
    h.document.querySelector('[data-proxy-filter-option="leased"]').click();await settle();
    assert.deepEqual(requests.map(row => row.view), ['current']);
    assert.equal(requests[0].query.state, 'leased');
    await w.get('[data-proxy-view="history"]').trigger('click');
    assert.equal(w.get('[data-proxy-table="history"] button[aria-label="筛选状态"]').attributes('data-active'), undefined);
    await w.get('.list-filter-summary button').trigger('click');await settle();
    assert.equal(w.find('.list-filter-summary').exists(), false);
    assert.equal(requests.at(-1).query.state, 'all');
  });
  await contract('navigation', async () => {
    const calls = [];
    for (const name of ['overview', 'register', 'bulk', 'accounts', 'codex', 'outlook', 'proxy-traffic', 'config', 'extract-workbench', 'extract-stats']) {
      const tab = h.document.createElement('div');tab.id = `tab-${name}`;tab.dataset.moduleView = name === 'proxy-traffic' ? 'records' : 'overview';h.document.body.append(tab);
    }
    const start = common.indexOf('function activateTab('), end = common.indexOf("\n$$('.sidebar-nav button[data-tab]')", start);
    assert.ok(start >= 0 && end > start);
    const context = {
      window: {ProxyTraffic: {setView: value => calls.push(['view', value]), setVisible: value => calls.push(['visible', value])}},
      document: h.document, localStorage, ACTIVE_TAB: 'overview', NAV_ALLOWED_TABS: ['overview', 'proxy-traffic'],
      TAB_META: {'proxy-traffic': {title: '代理与流量', description: '独立代理池'}},
      MODULE_VIEW_META: {'proxy-traffic': {records: '租约与流量'}},
      $: selector => h.document.querySelector(selector), $$: () => [],
      closePageDialogsForNavigation: () => calls.push(['close']), closeMobileSidebar() {}, updateNavigationBackButton() {},
      recordNavigationHistory() {}, ensureViewLoaded() {}, loadDashboard() {},
    };
    vm.runInNewContext(common.slice(start, end) + "\nactivateTab('proxy-traffic', false, 'none');", context);
    assert.deepEqual(calls.filter(row => row[0] === 'view' || row[0] === 'visible'), [['view', 'records'], ['visible', true]]);
    assert.equal(h.document.getElementById('tab-proxy-traffic').classList.contains('hidden'), false);
    assert.equal(h.document.getElementById('tab-outlook').classList.contains('hidden'), true);
    const commonIndex = template.indexOf("filename='js/shared/common.js'");
    const facadeIndex = template.indexOf("filename='js/pages/proxy/traffic.js'");
    const bootstrapIndex = template.indexOf("filename='js/bootstrap.js'");
    assert.ok(commonIndex < facadeIndex && facadeIndex < bootstrapIndex);
  });
  await contract('api_and_safe_fields', async () => {
    const requests = [];
    globalThis.fetch = async (url, options) => {
      requests.push({url: String(url), options});
      const endpoint = String(url).split('?')[0];
      if (endpoint === '/api/proxy-traffic/summary') return Response.json(fixtureSummary);
      if (endpoint === '/api/proxy-pool') return Response.json(fixturePool);
      const view = endpoint.split('/').at(-1);
      return Response.json({ok: true, view, items: [view === 'traffic' ? fixtureTraffic : fixtureLease], count: 1, total: 201, limit: 20, offset: 20});
    };
    const api = createProxyApi(), signal = new AbortController().signal;
    for (const view of ['current', 'history', 'traffic']) {
      const page = await api.page(view, {page: 2, size: 20, window: '7d', purpose: 'plan-check', state: 'released', search: ' A & 42 '}, signal);
      assert.equal(page.count, 1);assert.equal(page.total, 201);assert.equal(page.offset, 20);
      const url = new URL(requests.at(-1).url, 'http://fixture');
      assert.equal(url.pathname, `/api/proxy-traffic/${view}`);
      assert.equal(url.searchParams.get('purpose'), view === 'traffic' ? 'all' : 'plan-check');
      assert.equal(url.searchParams.get('search'), 'A & 42');
      assert.equal(requests.at(-1).options.signal, signal);
      assert.equal(requests.at(-1).options.credentials, 'same-origin');
    }
    await api.summary(signal);await api.pool(signal);
    assert.ok(requests.some(row => row.url === '/api/proxy-traffic/summary'));
    assert.ok(requests.some(row => row.url === '/api/proxy-pool'));
    const valid = {ok: true, view: 'history', items: [{id: 1}], count: 1, total: 201, limit: 20, offset: 20};
    for (const invalid of [{view: 'current'}, {items: null}, {count: 2}, {total: -1}, {limit: 0}, {offset: -1}]) {
      assert.throws(() => normalizeProxyPage('history', {...valid, ...invalid}));
    }
    const secretApi = fixtureApi();
    const injected = {proxy_url: 'RAW_PROXY_SECRET', username: 'RAW_USERNAME_SECRET', password: 'RAW_PASSWORD_SECRET'};
    secretApi.page = async view => fixturePage(view, [{...(view === 'traffic' ? fixtureTraffic : fixtureLease), ...injected, finished_at: 'INVALID_FINISHED_SENTINEL'}]);
    secretApi.pool = async () => ({...fixturePool, items: fixturePool.items.map(row => ({...row, ...injected}))});
    const w = mount('records', secretApi);await settle();
    assert.match(w.get('[data-proxy-table="current"]').text(), /lease-public-17/);
    assert.match(w.get('[data-proxy-table="current"]').text(), /203\.0\.113\.20/);
    assert.match(w.get('[data-proxy-table="current"]').text(), /2/);
    await w.get('[data-proxy-view="traffic"]').trigger('click');
    assert.match(w.get('[data-proxy-table="traffic"]').text(), /protocol_http/);
    assert.match(w.get('[data-proxy-table="traffic"]').text(), /46 B/);
    assert.match(w.get('[data-proxy-table="traffic"]').text(), /9 \/ 2 \/ 1 \/ 3/);
    await w.get('[data-proxy-table="traffic"] [data-proxy-detail]').trigger('click');await settle();
    assert.match(w.get('dialog').text(), /完成时间2026\/11\/16/);
    for (const secret of Object.values(injected)) assert.equal(w.text().includes(secret), false);
    assert.equal(w.text().includes('INVALID_FINISHED_SENTINEL'), false);
  });
  await contract('pool_capacity', async () => {
    const w = mount('pool');await settle();
    for (const [key, value] of Object.entries({poolCapacity: '17 / 20', poolReady: '3', poolFetching: '1', poolChecking: '2', poolLeased: '4', poolShared: '5'})) {
      assert.equal(w.get(`[data-proxy-summary="${key}"]`).text(), value);
    }
    const pool = w.get('[data-proxy-module-panel="pool"]');
    for (const text of ['脱敏端点', '脱敏出口', '最近错误', '203.0.113.0/24', 'JP', '等待 3', '目标 6', '等待轮换 2', '故障隔离 1', '候选', '7 秒后补货', '超过全池容量 20']) assert.ok(pool.text().includes(text), text);
    assert.equal(pool.find('input[type="password"]').exists(), false);
  });
  await contract('responsive_readability', async () => {
    const api = fixtureApi(), long = 'very-long-public-resource-value-'.repeat(15);
    api.page = async view => fixturePage(view, [{...(view === 'traffic' ? fixtureTraffic : fixtureLease), source: long, lease_id: long}]);
    const w = mount('records', api);await settle();
    assert.ok(w.get('[data-proxy-table="current"]').text().includes(long));
    const scroll = w.get('[data-proxy-table="current"]').element.closest('.pt-table-scroll');
    assert.equal(scroll.getAttribute('tabindex'), '0');
    const col = w.get('[data-proxy-table="current"] col'), before = col.attributes('style');
    await w.get('[data-proxy-table="current"] button[aria-label^="调整"]').trigger('keydown', {key: 'ArrowRight'});
    assert.notEqual(col.attributes('style'), before);
    const css = fs.readFileSync(path.join(root, 'frontend/src/features/proxy/proxy.css'), 'utf8');
    assert.match(css, /overflow-wrap:\s*anywhere/);assert.match(css, /table-layout:\s*fixed/);
    assert.match(css, /@media\s*\(max-width:\s*680px\)/);assert.match(css, /\.pt-table-scroll\s*\{[^}]*overflow:\s*auto/);
    assert.match(css, /focus-visible/);assert.match(css, /\.pt-toolbar\s+\.pt-mobile-filter\s*\{\s*display:\s*inline-flex/);
  });
}
function close() {
  h.close();
  for (const [name, descriptor] of browserGlobals) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    else delete globalThis[name];
  }
}
main().then(() => {close();process.stdout.write(JSON.stringify(results) + '\n');},
  error => {close();process.stderr.write(String(error.stack || error));process.exitCode = 1;});
