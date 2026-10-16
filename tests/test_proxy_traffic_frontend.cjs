const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/proxy_traffic.js'), 'utf8');

function createView() {
  const elements = new Map();
  const nodes = new Map();
  const document = {
    getElementById(id) { return nodes.get(id) || null; },
    querySelector(selector) { return elements.get(selector) || null; },
    querySelectorAll() { return []; },
  };
  const window = {};
  const context = {document, window, URLSearchParams, setTimeout, setInterval};
  vm.runInNewContext(`const LIST_FACET_LABELS = {task_type: {plan_check: '查套餐'}};\n${source}\n;globalThis.proxyTest = {
    requestPage: proxyTrafficRequestPage,
    requestAll: proxyTrafficRequest,
    requestNormalizedPage: (...args) => proxyTrafficRequestNormalizedPage(...args),
    normalizePage: proxyTrafficNormalizePage,
    renderSummary: proxyTrafficRenderSummary,
    renderPool: proxyPoolRender,
    renderTraffic: proxyTrafficRenderTraffic,
    openDetail: proxyTrafficOpenDetail,
    setSnapshot(value) { proxyTrafficSnapshot = value; },
    setView: proxyTrafficSetView,
    setSummary(value) { proxyTrafficSummary = value; },
    setPool(value) { proxyPoolSnapshot = value; },
    setState(view, value) { proxyTrafficStateFilters[view] = value; },
    setPage(view, value) { proxyTrafficPages[view].page = value; },
    invalidate() { proxyTrafficDesiredVersion += 1; },
  };`, context);
  return {api: context.proxyTest, elements, nodes, window};
}

test('分页请求默认取 20 条且携带服务端筛选', async () => {
  const {api, window} = createView();
  const requests = [];
  window.__PROXY_TRAFFIC_DATA_SOURCE__ = (endpoint, options) => {
    requests.push({endpoint, ...options});
    return {ok: true, items: [], count: 0, total: 0, limit: 20, offset: 0};
  };
  await api.requestPage('history');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].endpoint, '/api/proxy-traffic/history');
  assert.equal(requests[0].limit, 20);
  assert.equal(requests[0].offset, 0);
  assert.equal(requests[0].window, 'all');
});

test('页记录数与筛选后总数分别保留', () => {
  const {api} = createView();
  const page = api.normalizePage('traffic', {
    ok: true, items: [{id: 1}], count: 1, total: 201, limit: 20, offset: 20,
  });
  assert.equal(page.count, 1);
  assert.equal(page.total, 201);
});

test('采集状态只筛选所属列表', async () => {
  const {api, window} = createView();
  const requests = [];
  window.__PROXY_TRAFFIC_DATA_SOURCE__ = (endpoint, options) => {
    requests.push({endpoint, ...options});
    return {ok: true, items: [], count: 0, total: 0, limit: 20, offset: 0};
  };
  api.setState('history', 'released');
  await api.requestPage('history');
  await api.requestPage('traffic');
  assert.equal(requests[0].state, 'released');
  assert.equal(requests[1].state, 'all');
});

test('数据变少后自动回到最后一页并重新取数', async () => {
  const {api, window} = createView();
  const offsets = [];
  api.setPage('history', 3);
  window.__PROXY_TRAFFIC_DATA_SOURCE__ = (_endpoint, options) => {
    offsets.push(options.offset);
    return {
      ok: true, items: options.offset === 20 ? [{id: 1}] : [],
      count: options.offset === 20 ? 1 : 0,
      total: 21, limit: 20, offset: options.offset,
    };
  };
  const page = await api.requestNormalizedPage('history');
  assert.deepEqual(offsets, [40, 20]);
  assert.equal(page.items.length, 1);
});

test('筛选发生变化时丢弃旧请求结果', async () => {
  const {api, window} = createView();
  const releases = [];
  window.__PROXY_TRAFFIC_DATA_SOURCE__ = (_endpoint, options) => new Promise((resolve) => {
    if (options.view === 'summary') {
      resolve({ok: true, total_bytes: 0, today_bytes: 0, today_browser_count: 0, today_route_count: 0});
    } else {
      releases.push(() => resolve({ok: true, items: [], count: 0, total: 0, limit: 20, offset: 0}));
    }
  });
  const oldRequest = api.requestAll(0);
  await Promise.resolve();
  api.invalidate();
  releases.forEach((release) => release());
  await assert.rejects(oldRequest);
});

test('摘要取全库统计且与当前列表页无关', () => {
  const {api, elements} = createView();
  for (const key of ['totalBytes', 'todayBytes', 'todayRequestCount', 'todayRouteCount']) {
    elements.set(`[data-proxy-summary="${key}"]`, {textContent: ''});
  }
  api.setSummary({total_bytes: 1024, today_bytes: 512, today_browser_count: 3, today_protocol_count: 2, today_request_count: 5, today_route_count: 5});
  api.renderSummary();
  assert.equal(elements.get('[data-proxy-summary="totalBytes"]').textContent, '1.00 KB');
  assert.equal(elements.get('[data-proxy-summary="todayBytes"]').textContent, '512 B');
  assert.equal(elements.get('[data-proxy-summary="todayRequestCount"]').textContent, '5');
  assert.equal(elements.get('[data-proxy-summary="todayRouteCount"]').textContent, '5');
});

test('请求记录摘要兼容旧响应并保留新响应的零计数', () => {
  const {api, elements} = createView();
  const selector = '[data-proxy-summary="todayRequestCount"]';
  elements.set(selector, {textContent: ''});
  api.setSummary({today_browser_count: 3});
  api.renderSummary();
  assert.equal(elements.get(selector).textContent, '3');
  api.setSummary({today_browser_count: 3, today_request_count: 0});
  api.renderSummary();
  assert.equal(elements.get(selector).textContent, '0');
});

test('代理池摘要展示各状态并只渲染脱敏库存字段', () => {
  const {api, elements, nodes} = createView();
  for (const key of ['poolCapacity', 'poolReady', 'poolFetching', 'poolChecking', 'poolLeased', 'poolShared']) {
    elements.set(`[data-proxy-summary="${key}"]`, {textContent: ''});
  }
  nodes.set('proxyPoolPanelStatus', {textContent: ''});
  nodes.set('proxyPoolBody', {innerHTML: ''});
  api.setPool({
    policy: {max_size: 20},
    counts: {fetching: 1, checking: 2, ready: 3, leased: 4, shared: 5},
    items: [{resource_id: 'resource-1', provider: '1024proxy', state: 'ready', region: 'US', endpoint: 'proxy:8080', exit_ip: '203.0.113.0/24', checked_at: '2026-10-13T00:00:00Z', expires_at: '2026-10-13T01:00:00Z', last_error_code: null}],
  });
  api.renderSummary();
  api.renderPool();
  assert.equal(elements.get('[data-proxy-summary="poolCapacity"]').textContent, '15 / 20');
  assert.equal(elements.get('[data-proxy-summary="poolChecking"]').textContent, '2');
  assert.equal(elements.get('[data-proxy-summary="poolShared"]').textContent, '5');
  assert.match(nodes.get('proxyPoolBody').innerHTML, /203\.0\.113\.0\/24/);
  assert.doesNotMatch(nodes.get('proxyPoolBody').innerHTML, /proxy_url|username|password/);
});

test('代理池库存显示按国家的脱敏统计并保留等待与目标库存', () => {
  const {api, nodes} = createView();
  nodes.set('proxyPoolPanelStatus', {textContent: ''});
  nodes.set('proxyPoolBody', {innerHTML: ''});
  api.setPool({
    policy: {max_size: 20, min_ready: 2},
    counts: {ready: 3},
    waiting_local: 4,
    country_pools: [
      {provider: '1024proxy', region: 'JP', counts: {ready: 2, checking: 1}, waiting_local: 3, target_ready: 5},
      {provider: 'roxy', region: 'VN', counts: {ready: 1, leased: 2}, waiting_local: 1, target_ready: 4},
    ],
    items: [],
  });
  api.renderPool();
  const html = nodes.get('proxyPoolBody').innerHTML;
  assert.match(html, /JP/);
  assert.match(html, /VN/);
  assert.match(html, /可领取 2/);
  assert.match(html, /等待 3/);
  assert.match(html, /目标 5/);
  assert.doesNotMatch(html, /proxy_url|username|password/);
});

test('等待轮换计入容量并展示各国供给原因与容量提示', () => {
  const {api, elements, nodes} = createView();
  elements.set('[data-proxy-summary="poolCapacity"]', {textContent: ''});
  nodes.set('proxyPoolPanelStatus', {textContent: ''});
  nodes.set('proxyPoolBody', {innerHTML: ''});
  api.setPool({
    policy: {max_size: 4, min_ready: 3}, counts: {ready: 1, rotation_wait: 2},
    capacity_warning: '各国空闲底数合计 6，超过全池容量 4',
    country_pools: [{provider: '1024proxy', region: 'JP', counts: {ready: 1, rotation_wait: 2, quarantine: 1},
      last_supply_error: 'supply_candidates_duplicate', retry_after_seconds: 7, target_ready: 3, waiting_local: 2}],
    items: [{resource_id: 'r1', state: 'rotation_wait', provider: '1024proxy', region: 'JP'}],
  });
  api.renderSummary();
  api.renderPool();
  assert.equal(elements.get('[data-proxy-summary="poolCapacity"]').textContent, '3 / 4');
  assert.match(nodes.get('proxyPoolBody').innerHTML, /等待轮换 2/);
  assert.match(nodes.get('proxyPoolBody').innerHTML, /故障隔离 1/);
  assert.match(nodes.get('proxyPoolBody').innerHTML, /候选均已占用/);
  assert.match(nodes.get('proxyPoolPanelStatus').textContent, /空闲底数合计 6/);
});

test('浏览器详情用独立触发按钮避免单元格内展开裁切', () => {
  const {api} = createView();
  const html = api.renderTraffic({
    id: 7, source: 'roxy_cdp', method: 'cdp', availability: 'available',
    upload_bytes: 12, download_bytes: 34, total_bytes: 46,
  });
  assert.match(html, /data-proxy-detail="traffic"/);
  assert.doesNotMatch(html, /<details\b/);
});

test('请求流量展示任务类型和关联编号，未关联任务有明确提示', () => {
  const {api} = createView();
  const linked = api.renderTraffic({
    id: 8, source: 'roxy_cdp', method: 'cdp', availability: 'available',
    upload_bytes: 1, download_bytes: 2, total_bytes: 3,
    operation_task_id: 41, operation_run_id: 42, operation_task_type: 'plan_check',
  });
  assert.match(linked, /查套餐/);
  assert.match(linked, /任务 #41/);
  assert.match(linked, /运行 #42/);

  const unlinked = api.renderTraffic({
    id: 9, source: 'protocol_http', method: 'GET', availability: 'available',
    upload_bytes: 1, download_bytes: 2, total_bytes: 3,
  });
  assert.match(unlinked, /未关联任务/);

  const deleted = api.renderTraffic({
    id: 10, source: 'protocol_http', method: 'GET', availability: 'available',
    upload_bytes: 1, download_bytes: 2, total_bytes: 3,
    operation_task_id: 99,
  });
  assert.match(deleted, /未关联任务/);

  const registration = api.renderTraffic({
    id: 11, source: 'roxy_cdp', method: 'cdp', availability: 'available',
    upload_bytes: 1, download_bytes: 2, total_bytes: 3,
    operation_run_id: 76, registration_job_id: 77, operation_task_type: 'registration',
  });
  assert.match(registration, /注册/);
  assert.match(registration, /运行 #76/);
  assert.match(registration, /注册 job #77/);
});

test('请求流量详情显示任务类型及任务和运行编号', () => {
  const {api, nodes} = createView();
  const dialog = {showModal() { this.open = true; }};
  const body = {innerHTML: ''};
  const title = {textContent: ''};
  nodes.set('proxyTrafficDetailDialog', dialog);
  nodes.set('proxyTrafficDetailBody', body);
  nodes.set('proxyTrafficDetailTitle', title);
  api.setSnapshot({browser_traffic: [{
    id: 10, source: 'roxy_cdp', method: 'cdp', availability: 'available',
    upload_bytes: 1, download_bytes: 2, total_bytes: 3,
    operation_task_id: 51, operation_run_id: 52, operation_task_type: 'plan_check',
  }]});

  api.openDetail('traffic', 10);

  assert.equal(dialog.open, true);
  assert.match(body.innerHTML, /任务类型/);
  assert.match(body.innerHTML, /查套餐/);
  assert.match(body.innerHTML, /51/);
  assert.match(body.innerHTML, /52/);
});

test('请求流量详情保留注册 job 关联', () => {
  const {api, nodes} = createView();
  const dialog = {showModal() { this.open = true; }};
  const body = {innerHTML: ''};
  const title = {textContent: ''};
  nodes.set('proxyTrafficDetailDialog', dialog);
  nodes.set('proxyTrafficDetailBody', body);
  nodes.set('proxyTrafficDetailTitle', title);
  api.setSnapshot({browser_traffic: [{
    id: 12, source: 'roxy_cdp', method: 'cdp', availability: 'available',
    upload_bytes: 1, download_bytes: 2, total_bytes: 3,
    operation_run_id: 76, registration_job_id: 77, operation_task_type: 'registration',
  }]});

  api.openDetail('traffic', 12);

  assert.match(body.innerHTML, /任务类型/);
  assert.match(body.innerHTML, /注册/);
  assert.match(body.innerHTML, /注册 job/);
  assert.match(body.innerHTML, /77/);
});

test('切换代理子视图时关闭已打开的详情弹窗', () => {
  const {api, nodes} = createView();
  let closes = 0;
  nodes.set('proxyTrafficDetailDialog', {open: true, close() { closes += 1; }});
  api.setView('history');
  assert.equal(closes, 1);
});
