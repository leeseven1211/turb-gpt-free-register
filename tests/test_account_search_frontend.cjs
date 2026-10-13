const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/accounts.js'), 'utf8');

function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  const next = source.slice(start + 1).search(/\n(?:async )?function /);
  return source.slice(start, next < 0 ? undefined : start + 1 + next);
}

function harness() {
  const elements = new Map();
  const timers = new Map();
  const requests = [];
  let timerId = 0;
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', hidden: false, handlers: {},
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
    PAGERS: {accounts: {page: 3, size: 20}}, ACCOUNT_SELECTED: new Set([7]),
    updateAccountSelectionUi() {}, refreshColumnFilterStates() {},
    setTimeout(callback) { const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    loadAccounts() { requests.push(view.accountListQueryParams()); },
  };
  view.debounce = callback => { let id; return () => { view.clearTimeout(id); id = view.setTimeout(callback); }; };
  vm.createContext(view);
  const bindingStart = source.indexOf('(function bindAccountsFilterV2()');
  vm.runInContext([
    functionSource('getAccountsQuery'), functionSource('accountListQueryParams'),
    source.slice(bindingStart, source.indexOf('\n})();', bindingStart) + 6),
  ].join('\n'), view);
  function flush() {
    const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(callback => callback());
  }
  return {view, element, requests, flush, timers};
}

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
