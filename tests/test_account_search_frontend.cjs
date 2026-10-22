const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/accounts.js'), 'utf8');
const commonSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');

function functionSource(name, script = source) {
  const start = script.indexOf(`function ${name}(`);
  return script.slice(start, script.indexOf('\n}', start) + 2);
}

function harness() {
  const elements = new Map();
  const timers = new Map();
  const requests = [];
  let timerId = 0;
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', hidden: false, handlers: {}, attributes: {}, innerHTML: '',
      setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener(type, callback) { this.handlers[type] = callback; },
      focus() { this.focused = true; },
      dispatch(type, data = {}) { this.handlers[type]?.({preventDefault() {}, ...data}); },
    });
    return elements.get(id);
  }
  const view = {
    document: {getElementById: element}, $: selector => element(selector.slice(1)),
    URLSearchParams, SHOW_ARCHIVED_ACCOUNTS: false, SHOW_PLUS_ACCOUNTS_ONLY: false,
    accountAdvancedSearchQuery: '',
    accountSearchTerms: [], accountSearchErrorQuery: null,
    esc: value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;'),
    PAGERS: {accounts: {page: 3, size: 20}}, ACCOUNT_SELECTED: new Set([7]),
    updateAccountSelectionUi() {}, refreshColumnFilterStates() {},
    setTimeout(callback) { const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    loadAccounts() { requests.push(view.accountListQueryParams()); },
  };
  view.attrEsc = view.esc;
  view.debounce = callback => { let id; return () => { view.clearTimeout(id); id = view.setTimeout(callback); }; };
  vm.createContext(view);
  const bindingStart = source.indexOf('(function bindAccountsFilterV2()');
  vm.runInContext([
    ...['columnFilterValue', 'setColumnFilterValue'].filter(name => commonSource.includes(`function ${name}(`)).map(name => functionSource(name, commonSource)),
    functionSource('renderAccountSearchTerms'), functionSource('showAccountSearchError'),
    functionSource('getAccountsQuery'), functionSource('accountListQueryParams'),
    source.slice(bindingStart, source.indexOf('\n})();', bindingStart) + 6),
  ].join('\n'), view);
  function flush() {
    const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(callback => callback());
  }
  return {view, element, requests, flush, timers};
}

test('组合搜索原样提交，条件标签可单独移除并保留列筛选', () => {
  const {view, element, requests} = harness();
  const input = element('accountAdvancedSearchV2');
  input.value = '协议/jp 备注:"a/b 待整理"';
  input.dispatch('keydown', {key: 'Enter'});
  assert.equal(requests[0].get('q'), '协议/jp 备注:"a/b 待整理"');
  view.renderAccountSearchTerms([
    {label: '注册出口', display_value: '日本 JP', query_without: '协议 备注:"a/b 待整理"'},
  ]);
  assert.equal(element('accountSearchSummaryV2').hidden, false);
  assert.match(element('accountSearchSummaryV2').innerHTML, /注册出口：日本 JP/);
  element('accountSourceFilterV2').value = 'outlook';
  element('accountSearchSummaryV2').dispatch('click', {target: {closest: () => ({dataset: {accountSearchTerm: '0'}})}});
  assert.equal(requests.at(-1).get('q'), '协议 备注:"a/b 待整理"');
  assert.equal(requests.at(-1).get('source'), 'outlook');
  assert.equal(input.focused, true);
});

test('条件回显转义输入文字，避免把备注作为 HTML 执行', () => {
  const {view, element} = harness();
  view.renderAccountSearchTerms([{label: '备注', display_value: '<img src=x>', query_without: ''}]);
  assert.doesNotMatch(element('accountSearchSummaryV2').innerHTML, /<img/);
});

test('高级搜索和邮箱列筛选分别传递，并保留分页与归档条件', () => {
  const {view, element} = harness();
  element('accountAdvancedSearchV2').value = '  协议注册  ';
  element('accountAdvancedSearchV2').dispatch('keydown', {key: 'Enter'});
  view.PAGERS.accounts.page = 3;
  element('qAccountsV2').value = 'example.test';
  view.SHOW_ARCHIVED_ACCOUNTS = true;
  const params = view.accountListQueryParams();
  assert.equal(params.get('q'), '协议注册');
  assert.equal(params.get('email'), 'example.test');
  assert.equal(params.get('archived'), 'only');
  assert.equal(params.get('page'), '3');
});

test('中文组合输入完成后才搜索，连续输入合并请求并清除旧选择', () => {
  const {element, requests, flush, view} = harness();
  const input = element('accountAdvancedSearchV2');
  input.dispatch('compositionstart');
  input.value = 'xie'; input.dispatch('input', {isComposing: true}); flush();
  input.dispatch('keydown', {key: 'Enter', isComposing: true});
  assert.equal(requests.length, 0);
  input.value = '协议'; input.dispatch('compositionend');
  input.value = '协议注册'; input.dispatch('input'); flush();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].get('q'), '协议注册');
  assert.equal(requests[0].get('page'), '1');
  assert.equal(view.ACCOUNT_SELECTED.size, 0);
});

test('回车立即搜索并取消待执行的延迟请求', () => {
  const {element, requests, flush} = harness();
  const input = element('accountAdvancedSearchV2');
  input.value = '协议注册'; input.dispatch('input');
  input.dispatch('keydown', {key: 'Enter'});
  assert.equal(requests.length, 1);
  flush();
  assert.equal(requests.length, 1);
});

test('清空高级搜索保留列筛选并回到第一页，焦点返回输入框', () => {
  const {element, requests, flush} = harness();
  const input = element('accountAdvancedSearchV2');
  input.value = '协议注册'; input.dispatch('input');
  element('accountSourceFilterV2').value = 'icloud_hide';
  element('btnClearAccountSearchV2').dispatch('click'); flush();
  assert.equal(input.value, '');
  assert.equal(input.focused, true);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].get('q'), '');
  assert.equal(requests[0].get('source'), 'icloud_hide');
  assert.equal(requests[0].get('page'), '1');
});

test('清筛同时移除高级搜索和列条件，不留下延迟请求', () => {
  const {element, requests, flush} = harness();
  const input = element('accountAdvancedSearchV2');
  input.value = '协议注册'; input.dispatch('input');
  element('accountSourceFilterV2').value = 'icloud_hide';
  element('btnResetAccountFiltersV2').dispatch('click'); flush();
  assert.equal(input.value, '');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].get('source'), '');
  assert.equal(requests[0].get('page'), '1');
});

test('注册驱动变更回到第一页并重载，清筛移除驱动和其他列条件', () => {
  const {element, requests, flush} = harness();
  const driver = element('accountRegistrationDriverFilterV2');
  driver.value = 'protocol_oss,roxy';
  driver.dispatch('change'); flush();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].get('registration_driver'), 'protocol_oss,roxy');
  assert.equal(requests[0].get('page'), '1');
  element('accountSourceFilterV2').value = 'icloud_hide';
  element('btnResetAccountFiltersV2').dispatch('click'); flush();
  assert.equal(driver.value, '');
  assert.equal(requests.at(-1).get('registration_driver'), '');
  assert.equal(requests.at(-1).get('source'), '');
});

test('切换搜索时丢弃旧请求结果，避免旧账号覆盖新条件', async () => {
  const {view, element} = harness();
  const pending = [];
  const rendered = [];
  Object.assign(view, {
    accountsLoading: false, accountsReloadQueued: false, ACCOUNTS: [], ACCOUNTS_TOTAL: 0,
    setListBusy() {}, syncFacetSelect() {}, markViewReady() {}, showToast() {},
    api: url => new Promise(resolve => pending.push({url, resolve})),
    renderAccounts() { rendered.push(view.ACCOUNTS.map(row => row.id)); },
  });
  const start = source.indexOf('async function loadAccounts(');
  vm.runInContext(source.slice(start, source.indexOf('\nasync function pollAccountPlanStatuses(', start)), view);
  view.PAGERS.accounts.page = 1;
  element('accountAdvancedSearchV2').value = '协议注册';
  view.accountAdvancedSearchQuery = '协议注册';
  const oldRequest = view.loadAccounts();
  element('accountAdvancedSearchV2').value = '浏览器注册';
  view.accountAdvancedSearchQuery = '浏览器注册';
  await view.loadAccounts();
  pending[0].resolve({items: [{id: 1}], total: 25});
  await oldRequest;
  assert.equal(rendered.length, 0, '旧搜索响应不应展示');
  assert.equal(pending.length, 2);
  assert.equal(new URL(pending[1].url, 'http://example.test').searchParams.get('q'), '浏览器注册');
  pending[1].resolve({items: [{id: 2}], total: 60});
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(rendered, [[2]]);
});

test('旧响应和轮询读取已提交搜索词，不会在中文组合输入中查询拼音', async () => {
  const {view, element} = harness();
  const pending = [];
  Object.assign(view, {
    accountsLoading: false, accountsReloadQueued: false, ACCOUNTS: [], ACCOUNTS_TOTAL: 0,
    setListBusy() {}, syncFacetSelect() {}, markViewReady() {}, showToast() {}, renderAccounts() {},
    api: url => new Promise(resolve => pending.push({url, resolve})),
  });
  const start = source.indexOf('async function loadAccounts(');
  vm.runInContext(source.slice(start, source.indexOf('\nasync function pollAccountPlanStatuses(', start)), view);
  view.PAGERS.accounts.page = 1;
  const oldRequest = view.loadAccounts();
  const input = element('accountAdvancedSearchV2');
  input.dispatch('compositionstart');
  input.value = 'xie'; input.dispatch('input', {isComposing: true});
  pending[0].resolve({items: [{id: 1}], total: 25});
  await oldRequest;
  assert.equal(pending.length, 1, '组合输入期间不能因旧响应补发拼音搜索');
  assert.equal(view.accountListQueryParams().get('q'), '', '轮询应沿用已提交条件');
  input.value = '协议注册'; input.dispatch('compositionend');
  input.dispatch('keydown', {key: 'Enter'});
  assert.equal(pending.length, 2);
  assert.equal(new URL(pending[1].url, 'http://example.test').searchParams.get('q'), '协议注册');
  pending[1].resolve({items: [{id: 2}], total: 25});
  await new Promise(resolve => setImmediate(resolve));
});

test('错误搜索显示行内提示并清除旧结果，修正后正常恢复', async () => {
  const {view, element} = harness();
  const pending = [];
  Object.assign(view, {
    accountsLoading: false, accountsReloadQueued: false, planStatusLoading: false,
    ACCOUNTS: [{id: 7}], ACCOUNTS_TOTAL: 1,
    setListBusy() {}, syncFacetSelect() {}, markViewReady() {}, showToast() {}, renderAccounts() {},
    api: url => new Promise((resolve, reject) => pending.push({url, resolve, reject})),
  });
  const start = source.indexOf('async function loadAccounts(');
  vm.runInContext(source.slice(start, source.indexOf('\nfunction _codexCell(', start)), view);
  view.accountAdvancedSearchQuery = '地区:JJ';
  const invalid = view.loadAccounts();
  pending[0].reject(Object.assign(new Error('请填写有效国家代码'), {code: 'account_search_invalid'}));
  await invalid;
  assert.equal(element('accountAdvancedSearchV2').attributes['aria-invalid'], 'true');
  assert.equal(element('accountAdvancedSearchErrorV2').hidden, false);
  assert.match(element('accountAdvancedSearchErrorV2').textContent, /有效国家代码/);
  assert.equal(view.ACCOUNTS.length, 0);
  assert.equal(view.ACCOUNTS_TOTAL, 0);
  await view.pollAccountPlanStatuses();
  assert.equal(pending.length, 1, '错误查询不应继续轮询');
  element('accountAdvancedSearchV2').value = '协议 jp';
  element('accountAdvancedSearchV2').dispatch('keydown', {key: 'Enter'});
  assert.equal(element('accountAdvancedSearchErrorV2').hidden, true);
  pending[1].resolve({items: [{id: 9}], total: 1, search_terms: [{label: '注册出口', display_value: '日本 JP', query_without: '协议'}]});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(view.ACCOUNTS[0].id, 9);
  assert.equal(element('accountAdvancedSearchV2').attributes['aria-invalid'], 'false');
  assert.match(element('accountSearchSummaryV2').innerHTML, /日本 JP/);
});

test('过期搜索错误不会覆盖新条件或显示过期提示', async () => {
  const {view, element} = harness();
  const pending = [];
  Object.assign(view, {
    accountsLoading: false, accountsReloadQueued: false, ACCOUNTS: [], ACCOUNTS_TOTAL: 0,
    setListBusy() {}, syncFacetSelect() {}, markViewReady() {}, showToast() {}, renderAccounts() {},
    api: url => new Promise((resolve, reject) => pending.push({url, resolve, reject})),
  });
  const start = source.indexOf('async function loadAccounts(');
  vm.runInContext(source.slice(start, source.indexOf('\nasync function pollAccountPlanStatuses(', start)), view);
  view.accountAdvancedSearchQuery = '地区:JJ';
  const invalid = view.loadAccounts();
  view.accountAdvancedSearchQuery = '协议 jp';
  pending[0].reject(Object.assign(new Error('过期错误'), {code: 'account_search_invalid'}));
  await invalid;
  assert.notEqual(element('accountAdvancedSearchErrorV2').textContent, '过期错误');
  assert.equal(pending.length, 2);
  pending[1].resolve({items: [{id: 9}], total: 1});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(view.ACCOUNTS[0].id, 9);
});

test('API 错误保留业务错误码，供搜索框显示语法提示', async () => {
  const common = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');
  const start = common.indexOf('async function api(');
  const view = {
    API_INFLIGHT: new Map(),
    fetch: async () => ({ok: false, status: 400, json: async () => ({error: '国家代码有误', code: 'account_search_invalid'})}),
  };
  vm.createContext(view);
  vm.runInContext(common.slice(start, common.indexOf('\nasync function apiCached(', start)), view);
  await assert.rejects(view.api('/api/accounts?q=invalid'), error => error.message === '国家代码有误' && error.code === 'account_search_invalid');
  assert.equal(view.API_INFLIGHT.size, 0);
});
