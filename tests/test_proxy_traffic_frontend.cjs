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
  vm.runInNewContext(`${source}\n;globalThis.proxyTest = {
    requestPage: proxyTrafficRequestPage,
    requestAll: proxyTrafficRequest,
    requestNormalizedPage: (...args) => proxyTrafficRequestNormalizedPage(...args),
    normalizePage: proxyTrafficNormalizePage,
    renderSummary: proxyTrafficRenderSummary,
    renderTraffic: proxyTrafficRenderTraffic,
    setView: proxyTrafficSetView,
    setSummary(value) { proxyTrafficSummary = value; },
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
  for (const key of ['totalBytes', 'todayBytes', 'todayBrowserCount', 'todayRouteCount']) {
    elements.set(`[data-proxy-summary="${key}"]`, {textContent: ''});
  }
  api.setSummary({total_bytes: 1024, today_bytes: 512, today_browser_count: 3, today_route_count: 5});
  api.renderSummary();
  assert.equal(elements.get('[data-proxy-summary="totalBytes"]').textContent, '1.00 KB');
  assert.equal(elements.get('[data-proxy-summary="todayBytes"]').textContent, '512 B');
  assert.equal(elements.get('[data-proxy-summary="todayBrowserCount"]').textContent, '3');
  assert.equal(elements.get('[data-proxy-summary="todayRouteCount"]').textContent, '5');
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

test('切换代理子视图时关闭已打开的详情弹窗', () => {
  const {api, nodes} = createView();
  let closes = 0;
  nodes.set('proxyTrafficDetailDialog', {open: true, close() { closes += 1; }});
  api.setView('history');
  assert.equal(closes, 1);
});
