const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const sourcePath = path.join(__dirname, '../webui/static/js/modern/extract-workbench.js');
const source = fs.existsSync(sourcePath) ? fs.readFileSync(sourcePath, 'utf8') : '';

function createView({timers = null} = {}) {
  const nodes = new Map();
  const requests = [];
  const copied = [];
  const toasts = [];
  const confirmations = [];
  const document = {
    getElementById(id) { return nodes.get(id) || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {},
  };
  const timerApi = timers || {setTimeout, clearTimeout};
  const window = {
    crypto: require('node:crypto').webcrypto,
    confirm(message) { confirmations.push(message); return true; },
    __EXTRACT_WORKBENCH_DATA_SOURCE__(endpoint, options = {}) {
      requests.push({endpoint, options});
      return Promise.resolve({ok: true, items: [], counts: {}, page: 1, page_size: 20, total: 0});
    },
  };
  const context = {document, window, URL, URLSearchParams, setTimeout:timerApi.setTimeout, clearTimeout:timerApi.clearTimeout,
    LIST_FACET_LABELS:{source:{cloudflare_domain:'域名邮箱',email_butler:'Email Butler',remail:'Remail'}},
    navigator:{clipboard:{writeText:async value => copied.push(value)}}, showToast(message) { toasts.push(message); }};
  vm.createContext(context);
  vm.runInContext(`${source}\n;globalThis.workbench = {
    renderCard: typeof renderExtractWorkbenchTaskCard === 'function' ? renderExtractWorkbenchTaskCard : undefined,
    modes: typeof extractWorkbenchModesForProvider === 'function' ? extractWorkbenchModesForProvider : undefined,
    linkTypes: typeof extractWorkbenchLinkTypesForProvider === 'function' ? extractWorkbenchLinkTypesForProvider : undefined,
    createPayload: typeof extractWorkbenchCreatePayload === 'function' ? extractWorkbenchCreatePayload : undefined,
    listUrl: typeof extractWorkbenchListUrl === 'function' ? extractWorkbenchListUrl : undefined,
    outcome: extractWorkbenchOutcome,
    renderTabs: extractWorkbenchRenderStatusTabs,
    renderTasks: extractWorkbenchRenderTasks,
    syncTasks: extractWorkbenchSyncTaskCards,
    openCreate: extractWorkbenchOpenCreate,
    copy: extractWorkbenchCopy,
    submit: extractWorkbenchSubmit,
    loadAccounts: extractWorkbenchLoadAccounts,
    candidateSignature: extractWorkbenchCandidateSignature,
    candidateFilters: extractWorkbenchCandidateFilters,
    invalidatePreview: extractWorkbenchInvalidatePreview,
    switchBatch: extractWorkbenchSwitchBatch,
    cancelBatch: typeof extractWorkbenchCancelBatch === 'function' ? extractWorkbenchCancelBatch : undefined,
    renderBatches: extractWorkbenchRenderBatches,
    renderProviders: extractWorkbenchRenderProviders,
    renderLinkTypes: extractWorkbenchRenderLinkTypes,
    renderCandidatePromotion: extractWorkbenchRenderCandidatePromotion,
    accountSources: extractWorkbenchAccountSources,
    renderPaymentEntry: renderExtractWorkbenchPaymentEntry,
    showPaymentEntry: extractWorkbenchShowPaymentEntry,
    showDetail: extractWorkbenchShowDetail,
    scheduleRefresh: extractWorkbenchScheduleRefresh,
    copyPaymentEntry: extractWorkbenchCopyPaymentEntry,
    paymentQrError: extractWorkbenchPaymentQrError,
    paymentQrSources: extractWorkbenchPaymentQrSources,
    paymentUrl: extractWorkbenchPaymentUrl,
    setConfig(value) { if (typeof EXTRACT_WORKBENCH_CONFIG !== 'undefined') EXTRACT_WORKBENCH_CONFIG = value; },
    load: typeof loadExtractWorkbench === 'function' ? loadExtractWorkbench : undefined,
    setRoot(value) { if (typeof EXTRACT_WORKBENCH_ROOT !== 'undefined') EXTRACT_WORKBENCH_ROOT = value; },
    state: () => typeof EXTRACT_WORKBENCH_STATE === 'undefined' ? {} : ({...EXTRACT_WORKBENCH_STATE}),
    setState(value) { if (typeof EXTRACT_WORKBENCH_STATE !== 'undefined') EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, ...value}; },
  };`, context);
  return {api: context.workbench, nodes, requests, window, copied, document, toasts, confirmations};
}

function createBatchCancelView() {
  const view = createView();
  const button = {disabled: true, textContent: '取消批次', title: '', attributes: {},
    setAttribute(name, value) { this.attributes[name] = String(value); }};
  const select = {innerHTML: '', value: ''};
  const tasks = {innerHTML: '', scrollTop: 0};
  const selectors = {'[data-workbench-cancel-batch]': button, '[data-workbench-batch-select]': select,
    '[data-workbench-tasks]': tasks};
  const listeners = {};
  view.api.setRoot({querySelector: selector => selectors[selector] || null,
    addEventListener(name, callback) { listeners[name] = callback; }});
  view.api.setConfig({providers: []});
  view.api.setState({batchInitialized: true});
  return {...view, button, select, tasks, listeners};
}

function createFakeTimers() {
  let nextId = 1;
  const pending = new Map();
  return {
    setTimeout(callback, delay) {
      const id = nextId++;
      pending.set(id, {callback, delay});
      return id;
    },
    clearTimeout(id) { pending.delete(id); },
    runNext() {
      const next = pending.keys().next();
      if (next.done) return null;
      const id = next.value;
      const item = pending.get(id);
      pending.delete(id);
      item.callback();
      return item;
    },
    pendingDelays() { return [...pending.values()].map(item => item.delay); },
  };
}

function createWorkbenchTaskDom(view, taskIds = []) {
  const cards = new Map();
  const makeCard = (taskId) => {
    const detailButton = {
      tagName: 'BUTTON',
      dataset: {workbenchDetail: String(taskId)},
      attributes: {'aria-expanded': 'false'},
      setAttribute(name, value) { this.attributes[name] = String(value); },
      getAttribute(name) { return this.attributes[name]; },
      closest(selector) { return selector === '.extract-workbench-task' ? card : null; },
      focus() { view.document.activeElement = this; },
    };
    const summary = {
      tagName: 'SUMMARY',
      dataset: {},
      closest(selector) { return selector === '.extract-workbench-task' ? card : selector === 'details' ? details : null; },
      focus() { view.document.activeElement = this; },
    };
    const actionButton = {
      tagName: 'BUTTON',
      dataset: {workbenchAction: 'retry', taskId: String(taskId)},
      closest(selector) { return selector === '.extract-workbench-task' ? card : null; },
      focus() { view.document.activeElement = this; },
    };
    const detailContent = {
      innerHTML: '',
      textContent: '',
      classList: {
        hidden: true,
        contains(name) { return name === 'hidden' ? this.hidden : false; },
        add(name) { if (name === 'hidden') this.hidden = true; },
        remove(name) { if (name === 'hidden') this.hidden = false; },
      },
    };
    const details = {
      open: false,
      closest(selector) { return selector === '.extract-workbench-task' ? card : null; },
      querySelector(selector) {
        if (selector === '[data-workbench-detail]') return detailButton;
        if (selector === '[data-workbench-detail-content]') return detailContent;
        return null;
      },
    };
    const card = {
      dataset: {taskId: String(taskId)},
      querySelector(selector) {
        if (selector === 'details') return details;
        if (selector === 'summary') return summary;
        if (selector === '[data-workbench-detail]') return detailButton;
        if (selector === '[data-workbench-action="retry"]') return actionButton;
        if (selector === '[data-workbench-detail-content]') return detailContent;
        return null;
      },
      querySelectorAll(selector) { return selector === 'details[open]' && details.open ? [details] : []; },
      closest(selector) { return selector === '.extract-workbench-task' ? card : null; },
      contains(node) { return node === detailButton || node === detailContent || node === details || node === summary || node === actionButton; },
      detailButton,
      summary,
      actionButton,
      detailContent,
      details,
    };
    cards.set(String(taskId), card);
    return card;
  };
  const tasks = {
    scrollTop: 0,
    _html: '',
    get innerHTML() { return this._html; },
    set innerHTML(value) {
      this._html = String(value);
      cards.clear();
      for (const match of this._html.matchAll(/data-task-id="([^"]+)"/g)) makeCard(match[1]);
    },
    querySelector(selector) {
      if (selector === '.extract-workbench-task') return cards.values().next().value || null;
      const match = selector.match(/^\[data-task-id="([^"]+)"\]$/);
      return match ? cards.get(match[1]) || null : null;
    },
    querySelectorAll(selector) {
      if (selector === 'details[open]') return [...cards.values()].filter(card => card.details.open).map(card => card.details);
      if (selector === '.extract-workbench-task') return [...cards.values()];
      return [];
    },
    contains(node) { return [...cards.values()].some(card => card.contains(node)); },
    card(taskId) { return cards.get(String(taskId)) || null; },
  };
  const root = {
    extra: {},
    addEventListener() {},
    querySelector(selector) {
      if (this.extra[selector]) return this.extra[selector];
      if (selector === '[data-workbench-tasks]') return tasks;
      if (selector === '[data-workbench-tasks] details[open]') return [...cards.values()].find(card => card.details.open)?.details || null;
      return null;
    },
  };
  view.api.setRoot(root);
  tasks.innerHTML = taskIds.map(taskId => view.api.renderCard({task_id: taskId, task_status: 'running', extraction_status: 'running'})).join('');
  return {root, tasks, card: taskId => tasks.card(taskId)};
}

class SampleDomNode {
  constructor(tagName, attributes = {}, textContent = '') {
    this.nodeType = 1;
    this.tagName = String(tagName).toUpperCase();
    this.attributes = Object.entries(attributes).map(([name, value]) => ({name, value: String(value)}));
    this.childNodes = [];
    this.replaceChildrenCalls = 0;
    this.insertBeforeCalls = 0;
    this.removeChildCalls = 0;
    this.parentNode = null;
    this._textContent = String(textContent);
    this.dataset = {};
    for (const attribute of this.attributes) {
      if (attribute.name.startsWith('data-')) {
        const key = attribute.name.slice(5).replace(/-([a-z])/g, (_, char) => char.toUpperCase());
        this.dataset[key] = attribute.value;
      }
    }
  }
  get textContent() { return this.childNodes.length ? this.childNodes.map(child => child.textContent).join('') : this._textContent; }
  set textContent(value) { this.childNodes = []; this._textContent = String(value ?? ''); }
  appendChild(child) { child.parentNode = this; this.childNodes.push(child); return child; }
  replaceChildren(...children) { this.replaceChildrenCalls += 1; for (const child of [...this.childNodes]) this.removeChild(child); for (const child of children) this.appendChild(child); }
  insertBefore(child, before = null) {
    this.insertBeforeCalls += 1;
    if (child.parentNode) child.parentNode.removeChild(child);
    const index = before ? this.childNodes.indexOf(before) : -1;
    child.parentNode = this;
    if (index < 0) this.childNodes.push(child);
    else this.childNodes.splice(index, 0, child);
    return child;
  }
  removeChild(child) {
    this.removeChildCalls += 1;
    const index = this.childNodes.indexOf(child);
    if (index < 0) throw new Error('NotFoundError');
    this.childNodes.splice(index, 1);
    child.parentNode = null;
    return child;
  }
  setAttribute(name, value) {
    const existing = this.attributes.find(attribute => attribute.name === name);
    if (existing) existing.value = String(value);
    else this.attributes.push({name, value: String(value)});
    if (name.startsWith('data-')) {
      const key = name.slice(5).replace(/-([a-z])/g, (_, char) => char.toUpperCase());
      this.dataset[key] = String(value);
    }
  }
  removeAttribute(name) { this.attributes = this.attributes.filter(attribute => attribute.name !== name); }
  matches(selector) {
    if (selector === '.extract-workbench-task') return this.attributes.some(attribute => attribute.name === 'class' && attribute.value.includes('extract-workbench-task'));
    if (selector === 'details') return this.tagName === 'DETAILS';
    if (selector === 'summary') return this.tagName === 'SUMMARY';
    if (selector.startsWith('[data-') && selector.endsWith(']')) return this.attributes.some(attribute => attribute.name === selector.slice(1, -1));
    return false;
  }
  querySelectorAll(selector) {
    const found = [];
    const visit = node => {
      for (const child of node.childNodes || []) {
        if (child.matches?.(selector)) found.push(child);
        visit(child);
      }
    };
    visit(this);
    return found;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  cloneNode(deep = false) {
    const copy = new SampleDomNode(this.tagName, Object.fromEntries(this.attributes.map(attribute => [attribute.name, attribute.value])), this.textContent);
    if (deep) for (const child of this.childNodes) copy.appendChild(child.cloneNode(true));
    return copy;
  }
}

class SampleTextNode {
  constructor(value) { this.nodeType = 3; this.nodeValue = String(value); this.parentNode = null; }
  get textContent() { return this.nodeValue; }
  set textContent(value) { this.nodeValue = String(value ?? ''); }
  cloneNode() { return new SampleTextNode(this.nodeValue); }
}

function sampleTaskCard(taskId, progress, detailText) {
  const card = new SampleDomNode('article', {'class': 'extract-workbench-task', 'data-task-id': taskId});
  const progressNode = new SampleDomNode('div', {'data-progress': ''});
  progressNode.appendChild(new SampleTextNode(progress));
  card.appendChild(progressNode);
  const details = new SampleDomNode('details');
  details.open = true;
  details.appendChild(new SampleDomNode('summary'));
  const actions = new SampleDomNode('div');
  actions.appendChild(new SampleDomNode('button', {'data-workbench-detail': taskId, 'aria-expanded': 'true'}));
  actions.appendChild(new SampleDomNode('button', {'data-workbench-action': 'retry', 'data-task-id': taskId}));
  details.appendChild(actions);
  const detailNode = new SampleDomNode('div', {'data-workbench-detail-content': '', 'class': 'extract-workbench-detail'});
  detailNode.appendChild(new SampleTextNode(detailText));
  details.appendChild(detailNode);
  card.appendChild(details);
  return card;
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

test('新建批次按平台公布的提链类型初始化并提交用户选项', () => {
  const {api} = createView();
  api.setConfig({providers:[{id:'lumen', default_type:'momo', link_types:['momo','upi'], modes:['extract_only']}]});
  assert.deepEqual(Array.from(api.linkTypes({id:'lumen', default_type:'momo', link_types:['momo','upi']})), ['momo','upi']);
  assert.equal(api.createPayload([], 'lumen', 'extract_only').type, 'momo');
  assert.equal(api.createPayload([], 'lumen', 'extract_only', 'upi').type, 'upi');
  assert.equal(api.createPayload([], 'lumen', 'extract_only', 'unknown').type, 'momo');
});

test('新建批次显示不可用平台原因，平台筛选只显示可用平台', () => {
  const {api} = createView();
  const provider = {innerHTML:'', value:''};
  const filter = {innerHTML:'', value:''};
  api.setConfig({default_provider:'lumen', providers:[{id:'lumen', label:'Lumen Flow', modes:['extract_only'], link_types:['momo']}], unavailable_providers:[{id:'huanguang', label:'幻光提链', unavailable_reason:'缺少平台授权信息'}]});
  api.setRoot({querySelector:selector => ({'[data-workbench-provider]':provider,'[data-workbench-filter-provider]':filter}[selector] || null)});
  api.renderProviders();
  assert.match(provider.innerHTML, /幻光提链（缺少平台授权信息）/);
  assert.match(provider.innerHTML, /value="huanguang" disabled/);
  assert.doesNotMatch(filter.innerHTML, /幻光提链/);
});

test('候选筛选提交套餐优惠并更新资格说明', () => {
  const {api} = createView();
  const promotion = {value:'half_price'};
  const hint = {textContent:''};
  api.setRoot({querySelector:selector => ({'[data-workbench-promotion]':promotion,'[data-workbench-candidate-hint]':hint}[selector] || null)});
  assert.equal(api.candidateFilters().promotion, 'half_price');
  api.renderCandidatePromotion();
  assert.match(hint.textContent, /半价/);
  promotion.value = '';
  assert.equal(api.candidateFilters().promotion, 'eligible');
});

test('页面刷新查询列表和能力配置，列表不请求敏感链接', async () => {
  const {api, requests} = createView();
  api.setRoot({innerHTML: '', addEventListener() {}, querySelector() { return null; }});
  await api.load({force: true});
  assert.ok(requests.some(item => item.endpoint === '/api/extract-workbench/config'));
  assert.ok(requests.some(item => item.endpoint.startsWith('/api/extract-workbench/tasks?')));
  assert.ok(requests.every(item => !item.endpoint.endsWith('/links')));
  assert.ok(requests.every(item => !item.endpoint.startsWith('/api/accounts')));
});

test('任务列表每页查询 10 条，批次历史仍每页查询 20 条', async () => {
  const {api, requests} = createView();
  const batchSelect = {innerHTML:'', value:''};
  api.setRoot({addEventListener() {}, querySelector: selector => selector === '[data-workbench-batch-select]' ? batchSelect : null});
  await api.load({force:true});
  const taskRequest = requests.find(item => item.endpoint.startsWith('/api/extract-workbench/tasks?'));
  assert.equal(new URLSearchParams(taskRequest.endpoint.split('?')[1]).get('page_size'), '10');
  assert.ok(requests.some(item => item.endpoint === '/api/extract-workbench/batches?page=1&page_size=20'));
});

test('31 条任务分为四页，第二页摘要与首尾翻页状态正确', () => {
  const {api} = createView();
  const tasks = {innerHTML:''};
  const summary = {textContent:''};
  const label = {textContent:''};
  const previous = {disabled:false};
  const next = {disabled:false};
  const selectors = {'[data-workbench-tasks]':tasks, '[data-workbench-summary]':summary,
    '[data-workbench-page-label]':label, '[data-workbench-page="prev"]':previous, '[data-workbench-page="next"]':next};
  api.setRoot({querySelector: selector => selectors[selector] || null});
  for (const [page, count, range, previousDisabled, nextDisabled] of [
    [1, 10, '1–10', true, false], [2, 10, '11–20', false, false], [4, 1, '31–31', false, true],
  ]) {
    api.setState({page, total:31, items:Array.from({length:count}, (_, index) => ({task_id:(page - 1) * 10 + index + 1}))});
    api.renderTasks();
    assert.equal(summary.textContent, `显示 ${range} / 31 个任务`);
    assert.equal(label.textContent, `第 ${page} / 4 页`);
    assert.equal(previous.disabled, previousDisabled);
    assert.equal(next.disabled, nextDisabled);
    assert.equal((tasks.innerHTML.match(/class="extract-workbench-task"/g) || []).length, count);
  }
});

test('批次历史 31 条仍分为两页并保留独立翻页状态', () => {
  const {api} = createView();
  const label = {textContent:''};
  const previous = {disabled:false};
  const next = {disabled:false};
  const selectors = {'[data-workbench-batch-page-label]':label,
    '[data-workbench-batch-page="prev"]':previous, '[data-workbench-batch-page="next"]':next};
  api.setRoot({querySelector: selector => selectors[selector] || null});
  api.setState({batchPage:1, batchTotal:31});
  api.renderBatches();
  assert.equal(label.textContent, '第 1 / 2 页');
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, false);
  api.setState({batchPage:2});
  api.renderBatches();
  assert.equal(label.textContent, '第 2 / 2 页');
  assert.equal(previous.disabled, false);
  assert.equal(next.disabled, true);
});

test('取消批次仅在选择具体批次后启用，全部任务和放弃确认均不发请求', async () => {
  const {api, button, requests, window, confirmations} = createBatchCancelView();
  api.renderBatches();
  assert.equal(button.disabled, true);
  assert.match(button.title, /选择.*批次/);
  assert.equal(typeof api.cancelBatch, 'function');
  await api.cancelBatch();
  assert.equal(requests.length, 0);
  assert.equal(confirmations.length, 0);
  api.setState({batch: '7', batches: [{batch_id: 7, title: '十月提链'}]});
  api.renderBatches();
  assert.equal(button.disabled, false);
  assert.match(button.title, /整批.*排队/);
  window.confirm = message => { confirmations.push(message); return false; };
  await api.cancelBatch();
  assert.equal(requests.length, 0);
  assert.match(confirmations[0], /十月提链/);
  assert.match(confirmations[0], /CDK/);
  assert.match(confirmations[0], /运行中.*已完成.*保留/);
  assert.equal(button.disabled, false);
});

test('取消批次提交整批 API 并刷新摘要和任务，保留当前批次与筛选', async () => {
  const view = createBatchCancelView();
  const {api, button, select, tasks, window, toasts} = view;
  const requests = [];
  api.setState({batch: '7', batches: [{batch_id: 7, title: '十月提链'}], page: 4,
    status: 'processing', provider: 'legacy', mode: 'auto_payment', query: '查找'});
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async (endpoint, options = {}) => {
    requests.push({endpoint, options});
    if (endpoint.endsWith('/cancel')) return {ok: true, batch_id: 7, cancelled: 147, skipped: 3, failed: 0};
    if (endpoint === '/api/extract-workbench/config') return {providers: []};
    if (endpoint.includes('/batches?')) return {items: [{batch_id: 7, title: '十月提链', status: 'cancelled'}], total: 1};
    return {items: [{task_id: 42, task_status: 'cancelled'}], counts: {all: 1}, total: 1, page: 4};
  };
  assert.equal(typeof api.cancelBatch, 'function');
  await api.cancelBatch();
  const posted = requests.filter(request => request.options.method === 'POST');
  assert.equal(posted.length, 1);
  assert.equal(posted[0].endpoint, '/api/extract-workbench/batches/7/cancel');
  assert.deepEqual(JSON.parse(posted[0].options.body), {});
  assert.equal(posted[0].options.headers['Content-Type'], 'application/json');
  const filters = new URLSearchParams(requests.find(request => request.endpoint.includes('/tasks?')).endpoint.split('?')[1]);
  assert.equal(filters.get('batch_id'), '7');
  assert.equal(filters.get('page'), '4');
  assert.equal(filters.get('status'), 'processing');
  assert.equal(filters.get('provider_id'), 'legacy');
  assert.equal(filters.get('mode'), 'auto_payment');
  assert.equal(filters.get('query'), '查找');
  assert.equal(select.value, '7');
  assert.equal(api.state().batchDetail.status, 'cancelled');
  assert.match(tasks.innerHTML, /任务 #42/);
  assert.match(toasts.at(-1), /取消 147/);
  assert.match(toasts.at(-1), /跳过 3/);
  assert.equal(button.disabled, false);
});

test('取消请求未完成时禁止重复提交，切换批次不改变已提交目标或回跳', async () => {
  const {api, button, window, confirmations} = createBatchCancelView();
  const posted = [];
  let finishCancel;
  api.setState({batch: '7', batches: [{batch_id: 7, title: '旧批次'}]});
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async (endpoint, options = {}) => {
    if (endpoint.endsWith('/cancel')) {
      posted.push(endpoint);
      return new Promise(resolve => { finishCancel = resolve; });
    }
    if (endpoint === '/api/extract-workbench/config') return {providers: []};
    if (endpoint.includes('/batches?')) return {items: [{batch_id: 22, title: '新批次'}], total: 1};
    return {items: [], counts: {}, total: 0, page: 1};
  };
  assert.equal(typeof api.cancelBatch, 'function');
  const cancelling = api.cancelBatch();
  assert.equal(button.disabled, true);
  assert.match(button.textContent, /取消中/);
  assert.equal(button.attributes['aria-busy'], 'true');
  await api.switchBatch('22');
  assert.equal(button.disabled, true);
  await api.cancelBatch();
  assert.equal(confirmations.length, 1);
  assert.deepEqual(posted, ['/api/extract-workbench/batches/7/cancel']);
  finishCancel({ok: true, batch_id: 7, cancelled: 4, skipped: 0, failed: 0});
  await cancelling;
  assert.equal(api.state().batch, '22');
  assert.equal(api.state().batchDetail.title, '新批次');
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '取消批次');
  assert.equal(button.attributes['aria-busy'], 'false');
});

test('取消批次对零取消、部分失败和接口失败分别反馈并恢复操作', async () => {
  for (const [response, error, expected] of [
    [{ok: true, batch_id: 7, cancelled: 0, skipped: 3, failed: 0}, null, /没有可取消.*跳过 3/],
    [{ok: true, batch_id: 7, cancelled: 4, skipped: 1, failed: 2}, null, /取消 4.*失败 2/],
    [{ok: false, error: '批次不存在'}, null, /批次不存在/],
    [null, new Error('网络暂不可用'), /网络暂不可用/],
  ]) {
    const {api, button, window, toasts} = createBatchCancelView();
    api.setState({batch: '7'});
    window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
      if (endpoint.endsWith('/cancel')) {
        if (error) throw error;
        return response;
      }
      if (endpoint === '/api/extract-workbench/config') return {providers: []};
      return {items: [], counts: {}, total: 0, page: 1};
    };
    assert.equal(typeof api.cancelBatch, 'function');
    await api.cancelBatch();
    assert.match(toasts.at(-1), expected);
    assert.doesNotMatch(toasts.at(-1), /全部取消/);
    assert.equal(button.disabled, false);
  }
});

test('取消批次按钮点击事件提交所选批次', async () => {
  const {api, button, listeners, window} = createBatchCancelView();
  const posted = [];
  api.setState({batch: '7'});
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async (endpoint, options = {}) => {
    if (options.method === 'POST') posted.push(endpoint);
    if (endpoint.endsWith('/cancel')) return {ok: true, batch_id: 7, cancelled: 1, skipped: 0, failed: 0};
    if (endpoint === '/api/extract-workbench/config') return {providers: []};
    if (endpoint === '/api/extract-workbench/batches/7') return {item: {batch_id: 7}};
    return {items: [], counts: {}, total: 0, page: 1};
  };
  await api.load();
  button.closest = selector => selector === '[data-workbench-cancel-batch]' ? button : null;
  listeners.click({target: button});
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(posted, ['/api/extract-workbench/batches/7/cancel']);
});

test('quiet DOM 同步按 task_id 复用卡片、详情按钮和详情内容节点，并支持重排', () => {
  const {api} = createView();
  const tasks = new SampleDomNode('div');
  const old42 = sampleTaskCard('42', '10%', '旧详情');
  const old43 = sampleTaskCard('43', '20%', '另一个详情');
  const old42Button = old42.querySelector('[data-workbench-detail]');
  const old42Action = old42.querySelector('[data-workbench-action]');
  const old42Details = old42.querySelector('details');
  const old42Content = old42.querySelector('[data-workbench-detail-content]');
  tasks.replaceChildren(old42, old43);
  tasks.replaceChildrenCalls = 0;
  old42.replaceChildrenCalls = 0;
  old42Details.replaceChildrenCalls = 0;
  const fresh43 = sampleTaskCard('43', '30%', '新详情 43');
  const fresh42 = sampleTaskCard('42', '90%', '新详情 42');
  const fresh44 = sampleTaskCard('44', '40%', '新详情 44');

  api.syncTasks(tasks, [{task_id: '43'}, {task_id: '42'}, {task_id: '44'}], [fresh43, fresh42, fresh44]);

  assert.deepEqual(tasks.childNodes.map(card => card.dataset.taskId), ['43', '42', '44']);
  assert.equal(tasks.childNodes[1], old42);
  assert.equal(tasks.childNodes[1].querySelector('[data-workbench-detail]'), old42Button);
  assert.equal(tasks.childNodes[1].querySelector('[data-workbench-action]'), old42Action);
  assert.equal(tasks.childNodes[1].querySelector('[data-workbench-detail-content]'), old42Content);
  assert.equal(tasks.childNodes[1].querySelector('[data-progress]').textContent, '90%');
  assert.equal(tasks.childNodes[1].querySelector('[data-workbench-detail-content]').textContent, '旧详情');
  assert.equal(tasks.childNodes[0], old43);

  const stableTasks = new SampleDomNode('div');
  const stable42 = sampleTaskCard('42', '10%', '保留详情');
  const stable42Details = stable42.querySelector('details');
  const stable42Button = stable42.querySelector('[data-workbench-detail]');
  const stable42Action = stable42.querySelector('[data-workbench-action]');
  stableTasks.replaceChildren(stable42);
  stableTasks.replaceChildrenCalls = 0;
  stable42.replaceChildrenCalls = 0;
  stable42Details.replaceChildrenCalls = 0;
  const stableFresh = sampleTaskCard('42', '11%', '新详情不能覆盖');
  api.syncTasks(stableTasks, [{task_id: '42'}], [stableFresh]);
  assert.equal(stableTasks.replaceChildrenCalls, 0);
  assert.equal(stable42.replaceChildrenCalls, 0);
  assert.equal(stable42Details.replaceChildrenCalls, 0);
  assert.equal(stable42.querySelector('[data-workbench-detail]'), stable42Button);
  assert.equal(stable42.querySelector('[data-workbench-action]'), stable42Action);
});

test('DOM 同步处理空文本子节点时不会重复删除已清空节点', () => {
  const {api} = createView();
  const tasks = new SampleDomNode('div');
  const oldCard = sampleTaskCard('42', '10%', '旧详情');
  tasks.replaceChildren(oldCard);
  const freshCard = sampleTaskCard('42', '10%', '新详情');
  const freshProgress = freshCard.querySelector('[data-progress]');
  freshProgress.childNodes = [];
  freshProgress._textContent = '';

  assert.doesNotThrow(() => api.syncTasks(tasks, [{task_id: '42'}], [freshCard]));
  assert.equal(oldCard.querySelector('[data-progress]').textContent, '');
});

test('主动刷新与切换批次重置卡片滚动，自动刷新保留最新滚动位置', async () => {
  const {api, window} = createView();
  const tasks = {scrollTop:140, innerHTML:''};
  api.setConfig({providers:[]});
  api.setRoot({addEventListener() {}, querySelector: selector => selector === '[data-workbench-tasks]' ? tasks : null});
  api.setState({page:2, status:'running'});
  await api.load({force:true});
  assert.equal(tasks.scrollTop, 0);
  tasks.scrollTop = 140;
  await api.switchBatch('22');
  assert.equal(tasks.scrollTop, 0);
  Object.defineProperty(tasks, 'innerHTML', {set(value) { this.html = value; this.scrollTop = 0; }, get() { return this.html; }});
  tasks.scrollTop = 140;
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) tasks.scrollTop = 185;
    return {items:[{task_id:1}], counts:{}, total:1, page:1};
  };
  await api.load({quiet:true});
  assert.equal(tasks.scrollTop, 185);
});

test('quiet 刷新继续同步其他卡片，并保留展开详情、安全内容、滚动和焦点', async () => {
  const timers = createFakeTimers();
  const view = createView({timers});
  const fixture = createWorkbenchTaskDom(view, [42, 43]);
  const tab = {classList: {contains: () => false}};
  view.nodes.set('tab-extract-workbench', tab);
  view.api.setConfig({providers: []});
  view.api.setState({batchInitialized: true, batch: '', items: [{task_id: 42}, {task_id: 43}], counts: {processing: 2}, total: 2});
  const openCard = fixture.card(42);
  openCard.details.open = true;
  openCard.detailButton.setAttribute('aria-expanded', 'true');
  openCard.detailContent.classList.remove('hidden');
  openCard.detailContent.innerHTML = '<ul><li>安全阶段事件</li></ul>';
  openCard.detailContent.textContent = '安全阶段事件';
  view.document.activeElement = openCard.detailButton;
  fixture.tasks.scrollTop = 137;
  const requests = [];
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    requests.push(endpoint);
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) {
      return {items: [{task_id: 42, task_status: 'running'}, {task_id: 43, task_status: 'success'}], counts: {processing: 1}, total: 2, page: 1};
    }
    if (endpoint === '/api/extract-workbench/tasks/42') return {events: [{label: '提链', status: 'success', message: '安全阶段事件（最新）'}]};
    throw new Error(`unexpected endpoint: ${endpoint}`);
  };

  await view.api.load({quiet: true});
  await new Promise(resolve => setImmediate(resolve));

  const restored = fixture.card(42);
  assert.equal(restored.details.open, true);
  assert.equal(restored.detailButton.getAttribute('aria-expanded'), 'true');
  assert.match(restored.detailContent.innerHTML, /安全阶段事件（最新）/);
  assert.equal(fixture.tasks.scrollTop, 137);
  assert.equal(view.document.activeElement, restored.detailButton);
  assert.ok(requests.some(endpoint => endpoint.startsWith('/api/extract-workbench/tasks?')));
  assert.equal(requests.filter(endpoint => endpoint === '/api/extract-workbench/tasks/42').length, 1);
  assert.ok(requests.every(endpoint => !endpoint.endsWith('/links') && !endpoint.endsWith('/payment-entry') && !endpoint.startsWith('/api/accounts')));
});

test('只展开更多操作但未展开安全详情时，quiet 刷新不强开详情或请求详情', async () => {
  const view = createView();
  const fixture = createWorkbenchTaskDom(view, [42]);
  view.api.setConfig({providers: []});
  view.api.setState({batchInitialized: true, batch: '', items: [{task_id: 42}], counts: {processing: 1}, total: 1});
  fixture.card(42).details.open = true;
  const detailRequests = [];
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) return {items: [{task_id: 42}], counts: {processing: 1}, total: 1, page: 1};
    detailRequests.push(endpoint);
    return {events: [{label: '不应读取', status: 'success'}]};
  };
  await view.api.load({quiet: true});
  const restored = fixture.card(42);
  assert.equal(restored.details.open, true);
  assert.equal(restored.detailContent.classList.contains('hidden'), true);
  assert.equal(detailRequests.length, 0);
});

test('quiet 请求完成前用户收起详情并把焦点移到更多操作时，刷新保留最新状态', async () => {
  const view = createView();
  const fixture = createWorkbenchTaskDom(view, [42]);
  view.api.setConfig({providers: []});
  view.api.setState({batchInitialized: true, batch: '', items: [{task_id: 42}], counts: {processing: 1}, total: 1});
  const card = fixture.card(42);
  card.details.open = true;
  card.detailContent.classList.remove('hidden');
  card.detailContent.innerHTML = '<p>旧详情</p>';
  card.detailButton.setAttribute('aria-expanded', 'true');
  view.document.activeElement = card.detailButton;
  let resolveTasks;
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = endpoint => endpoint.startsWith('/api/extract-workbench/tasks?')
    ? new Promise(resolve => { resolveTasks = resolve; })
    : Promise.resolve({events: []});
  const loading = view.api.load({quiet: true});
  await Promise.resolve();
  card.details.open = false;
  card.detailContent.classList.add('hidden');
  card.summary.focus();
  resolveTasks({items: [{task_id: 42}], counts: {processing: 1}, total: 1, page: 1});
  await loading;
  const restored = fixture.card(42);
  assert.equal(restored.details.open, false);
  assert.equal(restored.detailContent.classList.contains('hidden'), true);
  assert.equal(view.document.activeElement, restored.summary);

  restored.details.open = true;
  restored.actionButton.focus();
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => endpoint.startsWith('/api/extract-workbench/tasks?')
    ? {items: [{task_id: 42}], counts: {processing: 1}, total: 1, page: 1}
    : {events: []};
  await view.api.load({quiet: true});
  assert.equal(view.document.activeElement, fixture.card(42).actionButton);
});

test('详情请求未完成时列表刷新立即安排下一轮定时器', async () => {
  const timers = createFakeTimers();
  const view = createView({timers});
  const fixture = createWorkbenchTaskDom(view, [42]);
  const tab = {classList: {contains: () => false}};
  view.nodes.set('tab-extract-workbench', tab);
  view.api.setConfig({providers: []});
  view.api.setState({batchInitialized: true, batch: '', items: [{task_id: 42}], counts: {processing: 1}, total: 1});
  fixture.card(42).details.open = true;
  fixture.card(42).detailContent.classList.remove('hidden');
  let resolveDetail;
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) return Promise.resolve({items: [{task_id: 42, task_status: 'success'}], counts: {processing: 1}, total: 1, page: 1});
    return new Promise(resolve => { resolveDetail = resolve; });
  };
  await view.api.load({quiet: true});
  assert.match(fixture.tasks.innerHTML, /任务 #42/);
  assert.deepEqual(timers.pendingDelays(), [5000]);
  resolveDetail({events: []});
  await new Promise(resolve => setImmediate(resolve));
});

test('展开详情不会暂停定时刷新', async () => {
  const timers = createFakeTimers();
  const view = createView({timers});
  const fixture = createWorkbenchTaskDom(view, [42]);
  const tab = {classList: {contains: () => false}};
  view.nodes.set('tab-extract-workbench', tab);
  view.api.setConfig({providers: []});
  view.api.setState({batchInitialized: true, batch: '', items: [{task_id: 42}], counts: {processing: 1}, total: 1});
  fixture.card(42).details.open = true;
  let taskRefreshes = 0;
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) taskRefreshes += 1;
    return {items: [{task_id: 42, task_status: 'running'}], counts: {processing: 1}, total: 1, page: 1};
  };
  view.api.scheduleRefresh();
  assert.deepEqual(timers.pendingDelays(), [5000]);
  timers.runNext();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(taskRefreshes, 1);
});

test('批次列表已有当前批次摘要时复用摘要，没有当前批次才读取详情', async () => {
  const view = createView();
  const fixture = createWorkbenchTaskDom(view, []);
  const batchSelect = {innerHTML: '', value: ''};
  fixture.root.extra = {'[data-workbench-batch-select]': batchSelect};
  const originalQuerySelector = fixture.root.querySelector.bind(fixture.root);
  fixture.root.querySelector = selector => fixture.root.extra[selector] || originalQuerySelector(selector);
  view.api.setConfig({providers: []});
  view.api.setState({batch: '7', batchInitialized: true});
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/batches?page=')) return {items: [{batch_id: 7, title: '当前批次', counts: {processing: 1}}], total: 1};
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) return {items: [], counts: {}, total: 0, page: 1};
    throw new Error(`不应请求当前批次详情: ${endpoint}`);
  };
  await view.api.load({quiet: true});
  assert.equal(view.api.state().batchDetail.title, '当前批次');
});

test('quiet 网络错误保留旧卡片并安排自动重试', async () => {
  const timers = createFakeTimers();
  const view = createView({timers});
  const fixture = createWorkbenchTaskDom(view, [42]);
  const tab = {classList: {contains: () => false}};
  view.nodes.set('tab-extract-workbench', tab);
  view.api.setConfig({providers: []});
  view.api.setState({batchInitialized: true, batch: '', items: [{task_id: 42, task_status: 'running'}], counts: {processing: 1}, total: 1});
  const summary = {textContent: ''};
  fixture.root.extra = {'[data-workbench-summary]': summary};
  const oldHtml = fixture.tasks.innerHTML;
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) throw new Error('网络暂不可用');
    return {items: [], counts: {processing: 1}, total: 1, page: 1};
  };
  await view.api.load({quiet: true});
  assert.equal(fixture.tasks.innerHTML, oldHtml);
  assert.match(summary.textContent, /重试/);
  assert.deepEqual(timers.pendingDelays(), [5000]);

  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) return {items: [{task_id: 42, task_status: 'success'}], counts: {}, total: 1, page: 1};
    return {items: [], counts: {}, total: 0, page: 1};
  };
  timers.runNext();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(fixture.tasks.innerHTML, /任务 #42/);
  assert.doesNotMatch(fixture.tasks.innerHTML, /网络暂不可用/);
});

test('原型卡片保留三项主操作、中文平台和运行次数，未知进度不伪造百分比', () => {
  const {api} = createView();
  const html = api.renderCard({task_id:42, account_id:7, email:'<account>@example.test',
    provider_id:'lumen_flow', mode:'extract_only', task_status:'running', run_count:2,
    preflight_status:'passed', extraction_status:'running', payment_status:'unpaid', plus_status:'pending'});
  for (const label of ['Lumen Flow', '仅提链', '运行 2 次', '预检通过', '支付入口', '复制链接', '复制 AT']) assert.ok(html.includes(label));
  assert.match(html, /extract-workbench-card-actions/);
  assert.match(html, /&lt;account&gt;@example.test/);
  assert.doesNotMatch(html, /Run 2|运行 2\/3|aria-valuenow="100"|>extract_only</);
});

test('支付成功待核验、出链成功未支付和提链失败呈现不同结果', () => {
  const {api} = createView();
  assert.equal(api.outcome({task_status:'success',payment_status:'paid',plus_status:'pending'}).title,'支付成功 · 到账待核实');
  assert.equal(api.outcome({task_status:'success',payment_status:'paid',plus_status:'confirmed'}).title,'支付成功 · 到账已核实');
  assert.equal(api.outcome({task_status:'success',mode:'extract_only',extraction_status:'success',payment_status:'unpaid'}).title,'提链成功');
  assert.equal(api.outcome({task_status:'failed',extraction_status:'failed',payment_status:'unpaid'}).title,'提链未完成');
  assert.equal(api.outcome({task_status:'failed',extraction_status:'failed',payment_status:'failed'}).title,'提链未完成');
  assert.equal(api.outcome({task_status:'request_unknown',extraction_status:'failed',payment_status:'unpaid'}).title,'平台结果 · 等待确认');
});

test('独立套餐已核实的 Plus 到账与平台支付待确认分别展示', () => {
  const {api} = createView();
  const task = {task_id:42, mode:'auto_payment', task_status:'request_unknown',
    extraction_status:'success', payment_status:'request_unknown', plus_status:'confirmed'};
  const outcome = api.outcome(task);
  assert.equal(outcome.state, 'Plus 已到账');
  assert.equal(outcome.title, 'Plus 已到账 · 支付待确认');
  assert.match(outcome.copy, /本地套餐已核实/);
  const html = api.renderCard(task);
  assert.match(html, /Plus 已到账/);
  assert.match(html, /结果待确认/);
  assert.doesNotMatch(html, /支付成功/);
  assert.equal(api.outcome({...task, plus_status:'not_applicable'}).title, '提链成功 · 后续结果待确认');
  assert.equal(api.outcome({...task, mode:'extract_only'}).title, '提链成功 · 后续结果待确认');
  assert.equal(api.outcome({...task, payment_status:'failed'}).title, '提链完成 · 支付失败');
  assert.equal(api.outcome({...task, extraction_status:'failed'}).title, '平台结果 · 等待确认');
});

test('停止查询的远端运行快照不再显示本地运行中', () => {
  const {api} = createView();
  const task = {task_id:42, provider_id:'huanguang', mode:'extract_only', task_status:'request_unknown',
    preflight_status:'passed', extraction_status:'running', payment_status:'unpaid', plus_status:'unknown'};
  const html = api.renderCard(task);
  assert.equal(api.outcome(task).title, '已停止查询 · 等待同步');
  assert.match(html, /已停止查询/);
  assert.match(html, /等待同步/);
  assert.doesNotMatch(html, /运行中|正在获取支付链接/);
});

test('同 Run 续查排队显示等待平台同步并保留已有结果', () => {
  const {api} = createView();
  const task = {task_id:42, provider_id:'huanguang', mode:'extract_only', task_status:'queued',
    preflight_status:'passed', extraction_status:'running', payment_status:'unpaid', plus_status:'unknown'};
  for (const extraction_status of ['pending', 'queued', 'running', 'unknown']) {
    const pending = {...task, extraction_status};
    assert.equal(api.outcome(pending).title, '等待平台同步');
    assert.match(api.renderCard(pending), /等待平台同步/);
    assert.doesNotMatch(api.renderCard(pending), /等待开始提链|执行前会在线查活/);
  }
  const fresh = {...task, preflight_status:'pending', extraction_status:'pending'};
  assert.equal(api.outcome(fresh).title, '等待开始提链');
  const completed = {...task, mode:'auto_payment', extraction_status:'success', payment_status:'paid', plus_status:'confirmed', has_extract_link:true};
  const html = api.renderCard(completed);
  assert.match(html, /提链成功/);
  assert.match(html, /支付成功 · 到账已核实/);
  assert.match(html, /Plus 已到账/);
  assert.doesNotMatch(html, /等待开始提链|正在获取支付链接/);
  assert.match(html, /data-workbench-link="extract" data-task-id="42">/);
});

test('扫码完成与独立套餐联合确认后显示支付成功及核验来源', () => {
  const {api} = createView();
  const task = {task_id:42, mode:'auto_payment', task_status:'success',
    extraction_status:'success', payment_status:'paid', plus_status:'confirmed',
    payment_confirmation_source:'local_plan_check'};
  const outcome = api.outcome(task);
  assert.equal(outcome.title, '支付成功 · 到账已核实');
  assert.match(outcome.copy, /扫码订单已完成/);
  assert.match(outcome.copy, /独立套餐查询已确认 Plus 到账/);
  const html = api.renderCard(task);
  assert.match(html, /支付成功/);
  assert.match(html, /Plus 已到账/);
  assert.doesNotMatch(html, /支付待确认|结果待确认/);
});

test('提链成功事实独立于任务后续失败和待确认，结果区不反写提链失败', () => {
  const {api} = createView();
  for (const [status, title] of [['failed','提链成功 · 后续处理失败'], ['attention_required','提链成功 · 后续结果待确认'], ['request_unknown','提链成功 · 后续结果待确认']]) {
    const task = {task_status:status, extraction_status:'success', payment_status:'unpaid', has_extract_link:true};
    assert.equal(api.outcome(task).title, title);
    assert.doesNotMatch(api.renderCard(task), /提链未完成/);
  }
});

test('支付入口兼容列表能力标记与历史链接，卡片不携带敏感支付内容', () => {
  const {api} = createView();
  for (const flag of ['has_payment_entry', 'has_qr', 'has_payment_link', 'has_extract_link']) {
    const html = api.renderCard({task_id:42, [flag]:true, payment_url:'https://private.example.test/session', qr_data:'private-payment-data'});
    assert.match(html, /data-workbench-payment-entry="42">/);
    assert.doesNotMatch(html, /private-payment-data|private\.example/);
  }
  assert.match(api.renderCard({task_id:42}), /data-workbench-payment-entry="42" disabled/);
});

test('支付入口分别呈现支付页面、平台入口、二维码与平台核验，零金额不丢失', () => {
  const {api} = createView();
  const html = api.renderPaymentEntry({payment_page_url:'https://checkout.example.test/page', payment_url:'https://pay.example.test/entry',
    qr_data:'payment-payload<&>', qr_image_url_png:'https://img.example.test/code.png', qr_image_url_svg:'https://img.example.test/code.svg',
    amount:0, currency:'inr', payment_status:'succeeded', platform_plus_status:'confirmed'});
  assert.match(html, /支付页面/);
  assert.match(html, /href="https:\/\/checkout\.example\.test\/page"/);
  assert.match(html, /href="https:\/\/pay\.example\.test\/entry"/);
  assert.match(html, /src="https:\/\/img\.example\.test\/code\.png"/);
  assert.match(html, /payment-payload&lt;&amp;&gt;/);
  assert.match(html, /0 INR/);
  assert.match(html, /平台显示已开通/);
  assert.match(html, /本地到账以卡片中的/);
  assert.doesNotMatch(html, /onerror=|到账已核实/);
  const pending = api.renderPaymentEntry({payment_status:'requires_action', platform_plus_status:'WAITING_FOR_PAYMENT'});
  assert.match(pending, /等待扫码或付款/);
  assert.match(pending, /等待支付后核验/);
});

test('只有普通支付页面时不伪造二维码，无图片的二维码内容只呈现原文', () => {
  const {api} = createView();
  const page = api.renderPaymentEntry({payment_page_url:'https://checkout.example.test/page'});
  assert.doesNotMatch(page, /<img/);
  assert.match(page, /平台未返回二维码/);
  const raw = api.renderPaymentEntry({qr_data:'upi://pay?pa=demo'});
  assert.doesNotMatch(raw, /<img/);
  assert.match(raw, /upi:\/\/pay\?pa=demo/);
  assert.match(raw, /可复制下方二维码原文/);
});

test('平台链接与二维码图片过滤脚本地址，不把不可信字段注入 HTML', () => {
  const {api} = createView();
  const html = api.renderPaymentEntry({payment_page_url:'javascript:alert(1)', payment_url:'data:text/html,<script>alert(1)</script>',
    qr_image_url_png:'javascript:alert(1)', qr_image_url_svg:'https://img.example.test/qr.svg', qr_data:'<img src=x onerror=alert(1)>'});
  assert.doesNotMatch(html, /href="(?:javascript|data):|src="javascript:|<img src=x/);
  assert.match(html, /src="https:\/\/img\.example\.test\/qr\.svg"/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.equal(api.paymentUrl('https://user:secret@example.test/private'), '');
  assert.deepEqual(Array.from(api.paymentQrSources({qr_image_url_png:'data:image/png;base64,YWJj'})), ['data:image/png;base64,YWJj']);
});

function installPaymentDialog(view) {
  const listeners = {};
  const content = {innerHTML:'', textContent:'', attributes:{}, setAttribute(name,value) {this.attributes[name]=value;}};
  const task = {textContent:''};
  const dialog = {open:false, dataset:{}, attributes:{}, innerHTML:'',
    setAttribute(name,value) {this.attributes[name]=value;},
    querySelector:selector => ({'[data-workbench-payment-content]':content, '[data-workbench-payment-task]':task})[selector] || null,
    addEventListener(name,handler) {listeners[name]=handler;},
    showModal() {this.open=true;},
    close() {this.open=false; listeners.close?.();},
    getBoundingClientRect() {return {left:10,right:100,top:10,bottom:100};},
  };
  let appended = null;
  const root = {querySelector:selector => selector === '[data-workbench-payment-dialog]' ? appended : null,
    appendChild(node) {appended=node;}, querySelectorAll() {return [];}};
  view.document.createElement = () => dialog;
  view.api.setRoot(root);
  return {dialog, content, task, listeners};
}

test('支付入口点击后按需读取，加载与完成状态清晰且不会自动打开支付页面', async () => {
  const view = createView();
  const {dialog, content} = installPaymentDialog(view);
  const deferred = [];
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = (endpoint,options) => {
    view.requests.push({endpoint,options}); return new Promise(resolve => deferred.push(resolve));
  };
  let focused = 0;
  const request = view.api.showPaymentEntry(42, {isConnected:true, focus() {focused++;}});
  assert.equal(dialog.open, true);
  assert.equal(dialog.attributes['aria-labelledby'], 'extractWorkbenchPaymentTitle');
  assert.match(dialog.innerHTML, /data-workbench-close-payment.*aria-label="关闭支付入口"/);
  assert.match(content.innerHTML, /正在读取支付入口/);
  assert.equal(content.attributes['aria-busy'], 'true');
  assert.equal(view.requests[0].endpoint, '/api/extract-workbench/tasks/42/payment-entry');
  assert.equal(view.requests[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(view.requests[0].options.body), {});
  deferred[0]({ok:true,entry:{payment_page_url:'https://checkout.example.test/page', qr_data:'private-qr-data'}});
  await request;
  assert.equal(content.attributes['aria-busy'], 'false');
  assert.match(content.innerHTML, /private-qr-data/);
  await view.api.copyPaymentEntry('qr_data');
  assert.deepEqual(view.copied, ['private-qr-data']);
  assert.equal(view.api.state().qr_data, undefined);
  dialog.close();
  assert.equal(content.textContent, '');
  assert.equal(focused, 1);
  await view.api.copyPaymentEntry('qr_data');
  assert.equal(view.copied.length, 1);
});

test('关闭窗口或切换任务后迟到的支付入口响应不能覆盖当前内容', async () => {
  const view = createView();
  const {dialog, content} = installPaymentDialog(view);
  const deferred = [];
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = () => new Promise(resolve => deferred.push(resolve));
  const older = view.api.showPaymentEntry(41);
  dialog.close();
  const newer = view.api.showPaymentEntry(42);
  deferred[1]({ok:true,entry:{qr_data:'new-qr-data'}});
  await newer;
  deferred[0]({ok:true,entry:{qr_data:'old-qr-data'}});
  await older;
  assert.match(content.innerHTML, /new-qr-data/);
  assert.doesNotMatch(content.innerHTML, /old-qr-data/);
});

test('支付入口读取失败保留重试，二维码图片失败依次回退 SVG 和文字', async () => {
  const view = createView();
  const {content} = installPaymentDialog(view);
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async () => {throw new Error('平台暂不可用');};
  await view.api.showPaymentEntry(42);
  assert.match(content.innerHTML, /role="alert"/);
  assert.match(content.innerHTML, /平台暂不可用/);
  assert.match(content.innerHTML, /重新读取/);
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async () => ({ok:true, entry:{qr_image_url_png:'https://img.example.test/code.png',qr_image_url_svg:'https://img.example.test/code.svg'}});
  await view.api.showPaymentEntry(42);
  const fallback = {hidden:true};
  const image = {dataset:{},hidden:false,parentElement:{querySelector:() => fallback}};
  view.api.paymentQrError(image);
  assert.equal(image.src, 'https://img.example.test/code.svg');
  view.api.paymentQrError(image);
  assert.equal(image.hidden, true);
  assert.equal(fallback.hidden, false);
});

test('点击遮罩关闭支付入口，弹窗内部留白不触发关闭', async () => {
  const view = createView();
  const {dialog, listeners} = installPaymentDialog(view);
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async () => ({ok:true,entry:{}});
  await view.api.showPaymentEntry(42);
  listeners.click({target:dialog,clientX:50,clientY:50});
  assert.equal(dialog.open,true);
  listeners.click({target:dialog,clientX:5,clientY:5});
  assert.equal(dialog.open,false);
});

test('顶部标签使用全部统计数，切换状态后不把筛选结果当全部数量', () => {
  const {api} = createView();
  const tabs={innerHTML:''};
  api.setRoot({querySelector: selector => selector==='[data-workbench-status-tabs]' ? tabs : null});
  api.setState({status:'running',total:1,counts:{all:1705,running:7,processing:18}});
  api.renderTabs();
  assert.match(tabs.innerHTML,/全部任务<\/strong><span>1,705/);
  assert.match(tabs.innerHTML,/data-workbench-status-filter="running" aria-pressed="true"/);
  assert.match(tabs.innerHTML,/只看运行中<\/strong><span>7/);
});

test('新建批次弹窗打开后才查询候选，重新打开会刷新匹配数量', async () => {
  const {api,requests}=createView();
  const dialog={open:false, showModal(){this.open=true;},close(){this.open=false;}};
  const accounts={innerHTML:''};
  api.setConfig({providers:[]});
  api.setRoot({querySelector:selector=>({'[data-workbench-create-dialog]':dialog,'[data-workbench-accounts]':accounts})[selector] || null});
  assert.equal(requests.length,0);
  await api.openCreate();
  assert.equal(dialog.open,true);
  dialog.close();
  await api.openCreate();
  assert.equal(requests.filter(item=>item.endpoint.startsWith('/api/extract-workbench/candidates?')).length,2);
  assert.doesNotMatch(accounts.innerHTML,/type="checkbox"/);
});

test('复制 AT 只在点击时读取指定账号密钥，不写入任务卡片或状态', async () => {
  const {api,window,copied,requests}=createView();
  const task={task_id:42,account_id:7,email:'sample@example.test'};
  api.setState({items:[task]});
  assert.equal(requests.length,0);
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async endpoint=>{
    requests.push({endpoint}); return {ok:true,value:'test-access-token'};
  };
  await api.copy(42,'at');
  assert.equal(requests[0].endpoint,'/api/accounts/7/secret?field=access_token');
  assert.deepEqual(copied,['test-access-token']);
  assert.doesNotMatch(api.renderCard(api.state().items[0]),/test-access-token/);
  assert.equal(api.state().items[0].access_token,undefined);
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

test('账号搜索的新响应先返回后，旧的成功或失败响应都不能覆盖结果', async () => {
  for (const staleReject of [false,true]) {
    const {api,window}=createView();
    const query={value:'older'};
    const accounts={innerHTML:''};
    api.setRoot({querySelector:selector=>({'[data-workbench-account-query]':query,'[data-workbench-accounts]':accounts})[selector] || null});
    const deferred=[];
    window.__EXTRACT_WORKBENCH_DATA_SOURCE__=()=>new Promise((resolve,reject)=>deferred.push({resolve,reject}));
    const older=api.loadAccounts();
    query.value='newer';
    const newer=api.loadAccounts();
    deferred[1].resolve({items:[{id:2,email:'newer@example.test'}]});
    await newer;
    if (staleReject) deferred[0].reject(new Error('旧搜索失败'));
    else deferred[0].resolve({items:[{id:1,email:'older@example.test'}]});
    await older;
    assert.match(accounts.innerHTML,/newer@example.test/);
    assert.doesNotMatch(accounts.innerHTML,/older@example.test|旧搜索失败/);
  }
});

test('筛选批次提交数量不受预览条数限制，成功后切到新批次', async () => {
  const {api,window}=createView();
  const dialog={open:true,close(){this.open=false;}};
  const feedback={textContent:''};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only'],default_type:'momo'}]});
  const selectors={'[data-workbench-create-dialog]':dialog,'[data-workbench-create-feedback]':feedback,
    '[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'},
    '[data-workbench-batch-limit]':{value:'100'},'[data-workbench-batch-title]':{value:'10月14日提链'},
    '[data-workbench-date-from]':{value:'2026-10-14'},'[data-workbench-date-to]':{value:'2026-10-14'}};
  api.setRoot({querySelector:selector=>selectors[selector] || null,addEventListener(){}});
  api.setState({preview:{selected_count:100,items:[{account_id:7}]},previewSignature:api.candidateSignature()});
  const posted=[];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async (endpoint,options={})=>{
    if (endpoint==='/api/extract-workbench/batches' && options.method==='POST') {
      posted.push(JSON.parse(options.body));return {batch_id:44,requested:100,started:98,skipped:2,failed:0};
    }
    if (endpoint==='/api/extract-workbench/config') return {providers:[{id:'lumen_flow',modes:['extract_only']}]};
    if (endpoint==='/api/extract-workbench/batches/44') return {item:{batch_id:44,title:'10月14日提链'}};
    return {items:[{task_id:42}],total:1,counts:{all:1},page:1};
  };
  await api.submit();
  assert.equal(dialog.open,false);
  assert.equal(api.state().batch,'44');
  assert.equal(api.state().batchDetail.title,'10月14日提链');
  assert.equal(api.state().items[0].task_id,42);
  assert.equal(posted.length,1);
  assert.equal(posted[0].limit,100);
  assert.equal(posted[0].filters.date_from,'2026-10-14');
  assert.equal(posted[0].filters.extract_status,'not_succeeded');
  assert.equal(posted[0].account_ids,undefined);
  assert.match(posted[0].submission_id,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.match(feedback.textContent,/入队 98 个任务/);
});

test('筛选条件变更后预览失效，提交不会沿用旧匹配数量', async () => {
  const {api,requests}=createView();
  const query={value:'first'};
  const feedback={textContent:''};
  const selectors={'[data-workbench-account-query]':query,'[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'},'[data-workbench-candidate-summary]':feedback};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only'],default_type:'momo',link_types:['momo']}]});
  api.setRoot({querySelector:selector=>selectors[selector] || null});
  api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
  query.value='second';
  api.invalidatePreview();
  await api.submit();
  assert.equal(api.state().preview,null);
  assert.equal(requests.length,0);
  assert.match(feedback.textContent,/重新预览/);
});

test('切换批次后旧批次任务和摘要的迟到响应均被忽略', async () => {
  const {api,window}=createView();
  api.setConfig({providers:[]});
  api.setRoot({querySelector(){return null;},addEventListener(){}});
  const pending={};
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=endpoint=>{
    if(endpoint==='/api/extract-workbench/config')return Promise.resolve({providers:[]});
    return new Promise(resolve=>{pending[endpoint]=resolve;});
  };
  const older=api.switchBatch('11');
  await new Promise(resolve=>setImmediate(resolve));
  const newer=api.switchBatch('22');
  await new Promise(resolve=>setImmediate(resolve));
  const taskUrl=id=>Object.keys(pending).find(url=>url.includes('/tasks?') && url.includes(`batch_id=${id}`));
  pending[taskUrl('22')]({items:[{task_id:222}],counts:{all:1},total:1,page:1});
  pending['/api/extract-workbench/batches/22']({item:{batch_id:22,title:'新批次'}});
  await newer;
  pending[taskUrl('11')]({items:[{task_id:111}],counts:{all:1},total:1,page:1});
  pending['/api/extract-workbench/batches/11']({item:{batch_id:11,title:'旧批次'}});
  await older;
  assert.equal(api.state().items[0].task_id,222);
  assert.equal(api.state().batchDetail.title,'新批次');
  assert.equal(api.state().batch,'22');
});

test('批次切换清空上批筛选，全部任务请求不携带batch_id', async () => {
  const {api,requests}=createView();
  api.setConfig({providers:[]});
  api.setRoot({querySelector(){return null;},addEventListener(){}});
  api.setState({batch:'11',status:'running',provider:'lumen_flow',query:'older',page:4});
  await api.switchBatch('');
  assert.equal(api.state().status,'');
  assert.equal(api.state().provider,'');
  assert.equal(api.state().query,'');
  assert.equal(api.state().page,1);
  assert.ok(requests.some(r=>r.endpoint.includes('/tasks?') && !r.endpoint.includes('batch_id=')));
});

test('创建响应丢失后重试沿用提交标识，改变批次参数才生成新标识', async () => {
  const {api,window}=createView();
  const title={value:'同一批次'};
  const selectors={'[data-workbench-batch-title]':title,'[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'}};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only'],default_type:'momo',link_types:['momo']}]});
  api.setRoot({querySelector:selector=>selectors[selector] || null});
  api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
  const posted=[];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async (endpoint,options)=>{
    posted.push(JSON.parse(options.body)); throw new Error('连接中断');
  };
  await api.submit();
  await api.submit();
  assert.equal(posted.length,2);
  assert.equal(posted[0].submission_id,posted[1].submission_id);
  title.value='另一个批次';
  await api.submit();
  assert.notEqual(posted[0].submission_id,posted[2].submission_id);
});

test('邮箱来源复用账号现有枚举，域名邮箱和 Butler 等来源不遗漏', () => {
  const {api}=createView();
  assert.equal(api.accountSources().cloudflare_domain,'域名邮箱');
  assert.equal(api.accountSources().email_butler,'Email Butler');
  assert.equal(api.accountSources().remail,'Remail');
  assert.equal(api.accountSources().domain,undefined);
});


test('批次配置初始化默认并发，刷新保留用户已编辑的值', async () => {
  const {api, window}=createView();
  const workers={value:'1'};
  const hint={textContent:''};
  const selectors={'[data-workbench-batch-workers]':workers,'[data-workbench-concurrency-hint]':hint};
  api.setRoot({querySelector:selector=>selectors[selector] || null,addEventListener(){}});
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async endpoint=>endpoint.endsWith('/config')
    ? {providers:[],batch_workers_default:4,batch_workers_max:16}
    : {items:[],counts:{},total:0,page:1};
  await api.load({force:true});
  assert.equal(workers.value,'4');
  assert.equal(workers.min,'1');
  assert.equal(workers.max,'16');
  assert.match(hint.textContent,/并发|同时/);
  workers.value='7';
  await api.load({force:true});
  assert.equal(workers.value,'7');
});

test('提交携带批次并发，连接失败重试保留标识，修改并发生成新标识', async () => {
  const {api,window}=createView();
  const workers={value:'4'};
  const selectors={'[data-workbench-batch-workers]':workers,'[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'}};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only'],default_type:'momo',link_types:['momo']}],batch_workers_default:1,batch_workers_max:16});
  api.setRoot({querySelector:selector=>selectors[selector] || null});
  api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
  const posted=[];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async (endpoint,options)=>{
    posted.push(JSON.parse(options.body)); throw new Error('连接中断');
  };
  await api.submit();
  await api.submit();
  assert.equal(posted[0].workers,4);
  assert.equal(posted[0].submission_id,posted[1].submission_id);
  workers.value='8';
  await api.submit();
  assert.equal(posted[2].workers,8);
  assert.notEqual(posted[0].submission_id,posted[2].submission_id);
});

test('批次并发空值、非整数和超范围时不发送创建请求', async () => {
  for (const value of ['', '0', '17', '1.5', 'abc']) {
    const {api,requests}=createView();
    const feedback={textContent:''};
    const selectors={'[data-workbench-batch-workers]':{value},'[data-workbench-provider]':{value:'lumen_flow'},
      '[data-workbench-mode]':{value:'extract_only'},'[data-workbench-create-feedback]':feedback};
    api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only'],default_type:'momo',link_types:['momo']}],batch_workers_default:1,batch_workers_max:16});
    api.setRoot({querySelector:selector=>selectors[selector] || null});
    api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
    await api.submit();
    assert.equal(requests.length,0,`非法并发 ${value} 不应发起请求`);
    assert.match(feedback.textContent,/并发.*1.*16/);
  }
});

test('批次摘要行已移除，批次选择和分页仍可用', () => {
  const template=fs.readFileSync(path.join(__dirname, '../webui/templates/index.html'), 'utf8');
  assert.doesNotMatch(template,/data-workbench-batch-summary|extract-workbench-batch-summary/);
  const {api}=createView();
  const select={innerHTML:'',value:''};
  const label={textContent:''};
  const previous={disabled:false};
  const next={disabled:false};
  const nodes={
    '[data-workbench-batch-select]':select,
    '[data-workbench-batch-page-label]':label,
    '[data-workbench-batch-page="prev"]':previous,
    '[data-workbench-batch-page="next"]':next,
  };
  api.setRoot({querySelector:selector=>nodes[selector] || null});
  api.setState({batches:[{batch_id:7,title:'当前批次',requested_count:9,status:'running'}],batch:'7',batchTotal:21,batchPage:2});
  api.renderBatches();
  assert.match(select.innerHTML,/当前批次/);
  assert.equal(select.value,'7');
  assert.equal(label.textContent,'第 2 / 2 页');
  assert.equal(previous.disabled,false);
  assert.equal(next.disabled,true);
});
