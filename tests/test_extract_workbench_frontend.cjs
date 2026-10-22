const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const sourcePath = path.join(__dirname, '../webui/static/js/modern/extract-workbench.js');
const source = fs.existsSync(sourcePath) ? fs.readFileSync(sourcePath, 'utf8') : '';

function createView() {
  const nodes = new Map();
  const requests = [];
  const document = {
    getElementById(id) { return nodes.get(id) || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {},
  };
  const window = {
    __EXTRACT_WORKBENCH_DATA_SOURCE__(endpoint, options = {}) {
      requests.push({endpoint, options});
      return Promise.resolve({ok: true, items: [], counts: {}, page: 1, page_size: 20, total: 0});
    },
  };
  const context = {document, window, URLSearchParams, setTimeout, clearTimeout};
  vm.createContext(context);
  vm.runInContext(`${source}\n;globalThis.workbench = {
    renderCard: typeof renderExtractWorkbenchTaskCard === 'function' ? renderExtractWorkbenchTaskCard : undefined,
    modes: typeof extractWorkbenchModesForProvider === 'function' ? extractWorkbenchModesForProvider : undefined,
    createPayload: typeof extractWorkbenchCreatePayload === 'function' ? extractWorkbenchCreatePayload : undefined,
    listUrl: typeof extractWorkbenchListUrl === 'function' ? extractWorkbenchListUrl : undefined,
    setConfig(value) { if (typeof EXTRACT_WORKBENCH_CONFIG !== 'undefined') EXTRACT_WORKBENCH_CONFIG = value; },
    load: typeof loadExtractWorkbench === 'function' ? loadExtractWorkbench : undefined,
    setRoot(value) { if (typeof EXTRACT_WORKBENCH_ROOT !== 'undefined') EXTRACT_WORKBENCH_ROOT = value; },
    state: () => typeof EXTRACT_WORKBENCH_STATE === 'undefined' ? {} : ({...EXTRACT_WORKBENCH_STATE}),
    setState(value) { if (typeof EXTRACT_WORKBENCH_STATE !== 'undefined') EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, ...value}; },
  };`, context);
  return {api: context.workbench, nodes, requests, window};
}

test('任务卡分别呈现预检、提链、支付和 Plus 状态', () => {
  const {api} = createView();
  const html = api.renderCard({
    task_id: 'task-1', email: 'safe@example.test', task_status: 'running',
    preflight_status: 'success', extraction_status: 'success',
    payment_status: 'paid', plus_status: 'pending', run_count: 2,
    has_extract_link: true, has_payment_link: true,
  });
  assert.match(html, /预检/);
  assert.match(html, /提链成功/);
  assert.match(html, /支付成功/);
  assert.match(html, /Plus 待确认/);
  assert.match(html, /data-stage="payment"/);
  assert.match(html, /data-stage="plus"/);
});

test('状态筛选依赖独立支付与 Plus 字段，不把已支付误认为 Plus 已确认', () => {
  const {api} = createView();
  const task = {payment_status: 'paid', plus_status: 'pending'};
  assert.equal(api.listUrl({status: 'payment_succeeded'}).includes('status=payment_succeeded'), true);
  assert.equal(api.listUrl({status: 'plus_confirmed'}).includes('status=plus_confirmed'), true);
  assert.notEqual(task.payment_status, task.plus_status);
});

test('平台模式选择只保留服务端公布的能力', () => {
  const {api} = createView();
  const provider = {id: 'lumen', modes: ['extract_only', 'manual_payment']};
  assert.deepEqual(Array.from(api.modes(provider)), ['extract_only', 'manual_payment']);
  assert.deepEqual(Array.from(api.modes({id: 'other', modes: ['extract_only']})), ['extract_only']);
  assert.deepEqual(Array.from(api.modes({id: 'lumen', modes: ['auto_payment']})), ['auto_payment']);
  api.setConfig({default_provider: 'lumen', default_mode: 'auto_payment', providers: [provider]});
  assert.equal(api.createPayload(['acct-1'], 'lumen', 'auto_payment').mode, '');
});

test('批量创建默认 extract_only 且只提交选择的账号 ID', () => {
  const {api} = createView();
  api.setConfig({default_provider: 'lumen', default_mode: 'auto_payment', providers: [
    {id: 'lumen', default_type: 'plus', modes: ['extract_only', 'auto_payment']},
  ]});
  assert.deepEqual(JSON.parse(JSON.stringify(api.createPayload(['acct-1', 'acct-2'], 'lumen'))), {
    account_ids: ['acct-1', 'acct-2'], provider_id: 'lumen', mode: 'extract_only', type: 'plus',
  });
  assert.equal(api.createPayload(['acct-1'], 'lumen', 'auto_payment').mode, 'auto_payment');
});

test('页面刷新查询列表和能力配置，列表不请求敏感链接', async () => {
  const {api, requests} = createView();
  api.setRoot({innerHTML: '', addEventListener() {}, querySelector() { return null; }});
  await api.load({force: true});
  assert.ok(requests.some(item => item.endpoint === '/api/extract-workbench/config'));
  assert.ok(requests.some(item => item.endpoint.startsWith('/api/extract-workbench/tasks?')));
  assert.ok(requests.every(item => !item.endpoint.endsWith('/links')));
});

test('新筛选请求先返回时丢弃旧列表响应', async () => {
  const {api, window} = createView();
  api.setConfig({default_provider:'lumen', default_mode:'extract_only', providers:[]});
  api.setRoot({innerHTML:'', addEventListener() {}, querySelector() { return null; }});
  const deferred = [];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = endpoint => endpoint.startsWith('/api/extract-workbench/tasks?')
    ? new Promise(resolve => deferred.push(resolve))
    : Promise.resolve({ok:true, items:[]});
  const oldRequest = api.load();
  await Promise.resolve();
  const newRequest = api.load();
  await Promise.resolve();
  deferred[1]({items:[{task_id:'new'}], counts:{}, page:1, total:1});
  await newRequest;
  deferred[0]({items:[{task_id:'old'}], counts:{}, page:1, total:1});
  await oldRequest;
  assert.equal(api.state().items[0].task_id, 'new');
});
