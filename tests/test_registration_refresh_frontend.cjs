const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const jobsSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/jobs.js'), 'utf8');
const commonSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');
const bootstrapSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/bootstrap.js'), 'utf8');
function functionSource(name, code = jobsSource) {
  const index = code.indexOf(`function ${name}(`);
  if (index < 0) return '';
  const start = code.slice(Math.max(0, index - 6), index) === 'async ' ? index - 6 : index;
  return code.slice(start, code.indexOf('\n}', index) + 2);
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}
function harness() {
  const calls = [];
  const busy = [];
  const register = {dataset: {moduleView: 'launch'}, classList: {contains: () => false}};
  const context = {
    document: {hidden: false, querySelector: selector => selector === '#tab-register' ? register : null},
    localStorage: {getItem: () => 'old-storage-batch', setItem() {}, removeItem() {}},
    PAGERS: {jobs: {page: 1, size: 20}},
    setListBusy: (_id, value) => busy.push(value),
    updateJobStatusFilters() {}, renderJobs() {}, renderBatchProgress() {}, markViewReady() {},
    renderTableStateRow: () => '加载失败', queueMicrotask,
    api: url => {
      const pending = deferred();
      calls.push({url, ...pending});
      return pending.promise;
    },
  };
  vm.createContext(context);
  vm.runInContext(commonSource.slice(0, commonSource.indexOf('// GET requests')), context);
  context.$ = selector => selector === '#tab-register' ? register : null;
  vm.runInContext([
    'setJobProgressBatch', 'currentBatchJobs', 'jobsViewMode', 'shouldPollJobs', 'refreshJobs',
  ].map(name => functionSource(name)).join('\n'), context);
  const read = expression => vm.runInContext(expression, context);
  const set = expression => vm.runInContext(expression, context);
  const response = (batchId, status = 'running') => ({
    items: [], total: 0, revision: batchId,
    progress_batch: {batch_id: batchId, items: [{id: 1, status}], status_counts: {[status]: 1}},
    progress_batches: [{batch_id: batchId}], status_counts: {active: status === 'running' ? 1 : 0},
  });
  return {context, register, calls, busy, read, set, response};
}

test('首次打开从最新批次开始，不使用 localStorage 历史批次', () => {
  const h = harness();
  assert.equal(h.read('JOB_PROGRESS_BATCH_ID'), '');
});

test('旧批次 GET 挂起时切换立即发起新 GET，同一签名共享进行中的请求', async () => {
  const h = harness();
  h.context.setJobProgressBatch('old');
  const first = h.context.refreshJobs();
  h.context.setJobProgressBatch('new');
  const second = h.context.refreshJobs();
  const duplicate = h.context.refreshJobs({automatic: true});
  assert.equal(h.calls.length, 2);
  assert.match(h.calls[1].url, /progress_batch_id=new/);
  h.calls[1].resolve(h.response('new'));
  await Promise.all([second, duplicate]);
  h.calls[0].resolve(h.response('old'));
  await first;
  assert.equal(h.read('JOB_PROGRESS_BATCH_ID'), 'new');
  assert.equal(h.read('JOB_PROGRESS_BATCH.batch_id'), 'new');
});

test('旧响应先返回不会改新请求的 loading，也不会覆盖当前数据', async () => {
  const h = harness();
  h.context.setJobProgressBatch('old');
  const first = h.context.refreshJobs();
  h.context.setJobProgressBatch('new');
  const second = h.context.refreshJobs();
  assert.equal(h.calls.length, 2);
  h.calls[0].resolve(h.response('old'));
  await first;
  assert.equal(h.read('jobsLoading'), true);
  assert.equal(h.read('JOB_PROGRESS_BATCH_ID'), 'new');
  assert.equal(h.read('JOB_PROGRESS_BATCH'), null);
  assert.equal(h.busy.at(-1), true);
  h.calls[1].resolve(h.response('new'));
  await second;
  assert.equal(h.read('jobsLoading'), false);
});

test('发起注册只请求 batch，已有 tasks 视图只请求 table 并保留筛选分页', async () => {
  const h = harness();
  const launch = h.context.refreshJobs();
  assert.equal(new URL(h.calls[0].url, 'http://local').searchParams.get('view'), 'batch');
  h.register.dataset.moduleView = 'tasks';
  h.set("JOB_EMAIL_FILTER = 'fixture+filter'; PAGERS.jobs.page = 2");
  const table = h.context.refreshJobs();
  assert.equal(h.calls.length, 2);
  const params = new URL(h.calls[1].url, 'http://local').searchParams;
  assert.equal(params.get('view'), 'table');
  assert.equal(params.get('email'), 'fixture+filter');
  assert.equal(params.get('page'), '2');
  h.calls[1].resolve({items: [{id: 21}], total: 25, revision: 'table', facets: {}});
  await table;
  h.calls[0].resolve(h.response('old'));
  await launch;
  assert.equal(h.read('JOBS[0].id'), 21);
  assert.equal(h.read('JOB_PROGRESS_BATCH'), null);
});

test('结束批次停止自动轮询，显式刷新和新任务主动选择仍可读取', async () => {
  const h = harness();
  h.context.setJobProgressBatch('done');
  const initial = h.context.refreshJobs();
  h.calls[0].resolve(h.response('done', 'success'));
  await initial;
  assert.equal(h.context.shouldPollJobs(), false);
  await h.context.refreshJobs({automatic: true});
  assert.equal(h.calls.length, 1);
  const manual = h.context.refreshJobs();
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve(h.response('done', 'success'));
  await manual;
  h.context.setJobProgressBatch('created');
  assert.equal(h.read('JOB_PROGRESS_BATCH'), null);
  const created = h.context.refreshJobs();
  assert.equal(h.calls.length, 3);
  h.calls[2].resolve(h.response('created'));
  await created;
  assert.equal(h.context.shouldPollJobs(), true);
});

test('任务表自动轮询低频更新筛选统计，换筛选和手动刷新立即更新', async () => {
  const h = harness();
  h.register.dataset.moduleView = 'tasks';
  const facets = [];
  h.context.updateJobStatusFilters = value => facets.push(value);
  const initial = h.context.refreshJobs();
  h.calls[0].resolve({items: [], total: 0, revision: 'first', facets: {status: ['running']}, status_counts: {running: 7}});
  await initial;
  const poll = h.context.refreshJobs({automatic: true});
  assert.equal(new URL(h.calls[1].url, 'http://local').searchParams.get('include_facets'), '0');
  h.calls[1].resolve({items: [], total: 0, revision: 'second'});
  await poll;
  assert.equal(facets.length, 1);
  assert.equal(h.read('JOB_STATUS_COUNTS.running'), 7);

  h.context.refreshJobs.tableFacets.loadedAt -= 31000;
  const expired = h.context.refreshJobs({automatic: true});
  assert.notEqual(new URL(h.calls[2].url, 'http://local').searchParams.get('include_facets'), '0');
  h.calls[2].resolve({items: [], total: 0, revision: 'third', facets: {}, status_counts: {}});
  await expired;
  assert.equal(h.read('Object.keys(JOB_STATUS_COUNTS).length'), 0);

  h.set("JOB_EMAIL_FILTER = 'new-filter'");
  const filtered = h.context.refreshJobs({automatic: true});
  assert.notEqual(new URL(h.calls[3].url, 'http://local').searchParams.get('include_facets'), '0');
  h.calls[3].resolve({items: [], total: 0, facets: {}});
  await filtered;
  const manual = h.context.refreshJobs();
  assert.notEqual(new URL(h.calls[4].url, 'http://local').searchParams.get('include_facets'), '0');
  h.calls[4].resolve({items: [], total: 0, facets: {}});
  await manual;
});

test('自动刷新只读取可见注册视图，bootstrap 使用自动模式', async () => {
  const h = harness();
  h.context.document.hidden = true;
  const invisible = h.context.refreshJobs({automatic: true});
  if (h.calls.length) h.calls[0].resolve(h.response('unexpected'));
  await invisible;
  assert.equal(h.calls.length, 0);
  h.context.document.hidden = false;
  h.register.classList.contains = () => true;
  await h.context.refreshJobs({automatic: true});
  assert.equal(h.calls.length, 0);
  const intervals = [];
  const noOp = () => {};
  const context = {
    document: {hidden: false, addEventListener: noOp},
    localStorage: {getItem: () => 'overview'},
    setInterval: callback => { intervals.push(callback); },
    $: () => h.register,
    refreshJobs: options => { context.options = options; },
  };
  for (const name of ['initResizableTables', 'loadRuntimeUiSettings', 'loadSummary', 'loadCapabilities', 'restoreModuleViewState', 'activateTab', 'initializeNavigationHistory']) context[name] = noOp;
  h.register.classList.contains = () => false;
  vm.createContext(context);
  vm.runInContext(bootstrapSource, context);
  intervals[0]();
  assert.equal(context.options?.automatic, true);
});

test('切换批次立即清空旧步骤并显示当前批次的加载状态，保留批次下拉', () => {
  const h = harness();
  const elements = new Map();
  for (const id of ['batchProgressV2', 'registrationBatchSelectV2', 'batchProgressStateV2', 'batchProgressSummaryV2', 'batchProgressStagesV2', 'batchProgressTimeV2', 'batchProgressListV2', 'btnBatchStopV2', 'btnBatchCancelV2', 'btnBatchRetryV2']) {
    elements.set(id, {
      textContent: '旧批次内容', innerHTML: '', disabled: false, attributes: {},
      classList: {add() {}, remove() {}},
      setAttribute(key, value) { this.attributes[key] = value; },
    });
  }
  h.context.document.querySelector = selector => elements.get(selector.slice(1)) || null;
  h.context.document.getElementById = id => elements.get(id) || null;
  Object.assign(h.context, {esc: String, attrEsc: String, formatDateTime: String});
  vm.runInContext([
    'registrationBatchStateLabel', 'renderRegistrationBatchSelector', 'renderBatchProgress',
  ].map(name => functionSource(name)).join('\n'), h.context);
  h.set("JOB_PROGRESS_BATCH_ID = 'old'; JOB_PROGRESS_BATCH = {batch_id: 'old', items: [{id: 1}]}; JOB_PROGRESS_BATCHES = [{batch_id: 'old', total: 1}, {batch_id: 'new', total: 2}]");
  h.context.setJobProgressBatch('new');
  h.set('jobsLoading = true');
  h.context.renderBatchProgress();
  assert.equal(elements.get('batchProgressStateV2').textContent, '加载中…');
  assert.equal(elements.get('batchProgressListV2').textContent, '');
  assert.equal(elements.get('batchProgressV2').attributes['aria-busy'], 'true');
  assert.equal(elements.get('btnBatchRetryV2').disabled, true);
  const select = elements.get('registrationBatchSelectV2');
  assert.equal(select.value, 'new');
  assert.match(select.innerHTML, /value="old"/);
  assert.match(select.innerHTML, /value="new"/);
  assert.equal(select.disabled, false);
});

test('新建成功会覆盖所选历史终态批次并立即读取新批次，不等待旧 GET', async () => {
  const h = harness();
  h.context.setJobProgressBatch('old');
  const oldRequest = h.context.refreshJobs();
  const get = h.context.api;
  h.context.api = (url, options) => options?.method === 'POST'
    ? Promise.resolve({jobs: [{batch_id: 'created'}], submitted: 2})
    : get(url);
  Object.assign(h.context, {
    registrationEmailSourceLabel: String, registrationDriverLabel: () => 'Protocol', esc: String,
    setTimeout() {},
  });
  vm.runInContext(functionSource('startRegistrationFromInputs'), h.context);
  await h.context.startRegistrationFromInputs({value: '2'}, {value: '1'}, {value: 'fixture'}, null);
  assert.equal(h.calls.length, 2);
  assert.equal(h.read('JOB_PROGRESS_BATCH_ID'), 'created');
  assert.match(h.calls[1].url, /progress_batch_id=created/);
  const createdRequest = h.context.refreshJobs({automatic: true});
  h.calls[1].resolve(h.response('created'));
  await createdRequest;
  h.calls[0].resolve(h.response('old', 'success'));
  await oldRequest;
  assert.equal(h.read('JOB_PROGRESS_BATCH.batch_id'), 'created');
});

test('投影延迟继续轮询，table 终态分页仍按当前页更新', async () => {
  const h = harness();
  h.context.setJobProgressBatch('delayed');
  const launch = h.context.refreshJobs();
  const delayed = h.response('delayed', 'success');
  delayed.progress_batch.projection_delayed = true;
  h.calls[0].resolve(delayed);
  await launch;
  assert.equal(h.context.shouldPollJobs(), true);
  h.register.dataset.moduleView = 'tasks';
  h.set('PAGERS.jobs.page = 4');
  const table = h.context.refreshJobs();
  h.calls[1].resolve({items: [], total: 21, revision: 'page4'});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.calls.length, 3);
  assert.equal(new URL(h.calls[2].url, 'http://local').searchParams.get('page'), '2');
  h.calls[2].resolve({items: [{id: 21}], total: 21, revision: 'page2'});
  await table;
  assert.equal(h.read('JOBS[0].id'), 21);
  assert.equal(h.read('PAGERS.jobs.page'), 2);
  assert.equal(h.read('jobsLoading'), false);
});

test('摘要暂有所选批次但详情为空时不会等待自己的进行中请求', async () => {
  const h = harness();
  h.context.setJobProgressBatch('delayed');
  const request = h.context.refreshJobs();
  h.calls[0].resolve({items: [], progress_batch: null, progress_batches: [{batch_id: 'delayed'}]});
  const result = await Promise.race([
    request.then(() => 'done'),
    new Promise(resolve => setTimeout(() => resolve('blocked'), 20)),
  ]);
  assert.equal(result, 'done');
  assert.equal(h.read('jobsLoading'), false);
});

function useRealApi(h) {
  const network = [];
  h.context.fetch = (url, options = {}) => {
    if (options.method === 'POST') return Promise.resolve({ok: true, json: async () => ({batch_id: 'same', started_count: 1})});
    const pending = deferred();
    network.push({url, resolve: payload => pending.resolve({ok: true, json: async () => payload})});
    return pending.promise;
  };
  vm.runInContext('const API_INFLIGHT = new Map();\n' + functionSource('api', commonSource), h.context);
  return network;
}

test('真实 api 去重下 A→B→A 最后一次选择创建新的 A 网络请求，首个 A 不可覆盖', async () => {
  const h = harness();
  const network = useRealApi(h);
  h.context.setJobProgressBatch('A');
  const oldA = h.context.refreshJobs();
  h.context.setJobProgressBatch('B');
  const oldB = h.context.refreshJobs();
  h.context.setJobProgressBatch('A');
  const latestA = h.context.refreshJobs();
  assert.equal(network.length, 3);
  assert.notEqual(network[0].url, network[2].url);
  network[0].resolve(h.response('A', 'failed'));
  await oldA;
  assert.equal(h.read('JOB_PROGRESS_BATCH'), null);
  assert.equal(h.read('jobsLoading'), true);
  network[1].resolve(h.response('B', 'success'));
  await oldB;
  network[2].resolve(h.response('A', 'running'));
  await latestA;
  assert.equal(h.read('JOB_PROGRESS_BATCH.items[0].status'), 'running');
  assert.equal(h.context.shouldPollJobs(), true);
});

test('真实 api 下同批次重跑 POST 成功后的显式刷新绕过挂起的失败 GET', async () => {
  const h = harness();
  const network = useRealApi(h);
  h.context.setJobProgressBatch('same');
  h.set("JOB_PROGRESS_BATCH = {batch_id: 'same', items: [{id: 1, status: 'failed', retryable: true}], status_counts: {failed: 1}}");
  const old = h.context.refreshJobs();
  Object.assign(h.context, {confirm: () => true, showToast() {}});
  vm.runInContext(['registrationRetryPayload', 'retryBatchFailedJobs'].map(name => functionSource(name)).join('\n'), h.context);
  await h.context.retryBatchFailedJobs();
  assert.equal(network.length, 2);
  assert.notEqual(network[0].url, network[1].url);
  const fresh = h.read('jobsRequestPromise');
  network[0].resolve(h.response('same', 'failed'));
  await old;
  assert.equal(h.read('jobsLoading'), true);
  network[1].resolve(h.response('same', 'running'));
  await fresh;
  assert.equal(h.read('JOB_PROGRESS_BATCH.items[0].status'), 'running');
  assert.equal(h.context.shouldPollJobs(), true);
});

test('真实 api 下自动刷新共享同签名 GET，后续轮询沿用 generation，显式刷新才递增', async () => {
  const h = harness();
  const network = useRealApi(h);
  h.context.setJobProgressBatch('active');
  const initial = h.context.refreshJobs();
  const shared = h.context.refreshJobs({automatic: true});
  assert.equal(network.length, 1);
  network[0].resolve(h.response('active'));
  await Promise.all([initial, shared]);
  const poll = h.context.refreshJobs({automatic: true});
  assert.equal(network.length, 2);
  assert.equal(network[1].url, network[0].url);
  const manual = h.context.refreshJobs();
  assert.equal(network.length, 3);
  assert.notEqual(network[2].url, network[1].url);
  network[1].resolve(h.response('active', 'failed'));
  await poll;
  assert.equal(h.read('jobsLoading'), true);
  network[2].resolve(h.response('active'));
  await manual;
  assert.equal(h.context.shouldPollJobs(), true);
});

test('实际导航入口初始化同一注册视图只发一个 GET，终态重新进入仍读取且不合并变更刷新', async () => {
  const h = harness();
  const network = useRealApi(h);
  const tabs = new Map();
  for (const name of ['overview', 'register', 'accounts', 'extract-workbench', 'codex', 'outlook', 'proxy-traffic', 'config']) {
    tabs.set(`tab-${name}`, name === 'register' ? h.register : {dataset: {}, classList: {toggle() {}}});
  }
  h.register.classList.toggle = () => {};
  h.context.document.querySelector = selector => tabs.get(selector.slice(1)) || null;
  h.context.document.querySelectorAll = () => [];
  h.context.document.getElementById = id => tabs.get(id) || null;
  Object.assign(h.context, {
    NAV_ALLOWED_TABS: ['register'], ACTIVE_TAB: 'register',
    TAB_META: {register: {title: '注册机', description: '发起注册'}},
    MODULE_VIEW_META: {register: {launch: '发起注册'}},
    closePageDialogsForNavigation() {}, closeMobileSidebar() {},
    updateNavigationBackButton() {}, recordNavigationHistory() {},
  });
  vm.runInContext(['activateTab', 'setModuleView'].map(name => functionSource(name, commonSource)).join('\n'), h.context);
  h.context.activateTab('register', false);
  h.context.activateTab('register', false);
  h.context.setModuleView('register', 'launch', false);
  assert.equal(network.length, 1);
  const initial = h.read('jobsRequestPromise');
  network[0].resolve(h.response('latest', 'success'));
  await initial;
  assert.equal(h.context.shouldPollJobs(), false);
  h.context.activateTab('register', false);
  const navigation = h.read('jobsRequestPromise');
  h.context.setModuleView('register', 'launch', false);
  assert.equal(network.length, 2);
  const mutation = h.context.refreshJobs();
  assert.equal(network.length, 3);
  assert.notEqual(network[2].url, network[1].url);
  network[1].resolve(h.response('latest', 'success'));
  await navigation;
  assert.equal(h.read('jobsLoading'), true);
  network[2].resolve(h.response('latest', 'running'));
  await mutation;
  assert.equal(h.context.shouldPollJobs(), true);
});
