const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');

const source = require('../frontend_script_sources.cjs').readAccountScripts();
const actions = [
  ['btnCheckSelectedPlansV2', '/api/accounts/check-plan-bulk'],
  ['btnExtractSelectedLinksV2', '/api/accounts/extract-link-bulk'],
  ['btnCheckSelectedDeactivationMailV2', '/api/accounts/check-deactivation-mail-bulk'],
  ['btnStopSelectedCodexV2', '/api/codex/stop-bulk'],
  ['btnUploadSelectedCodexSub2V2', '/api/accounts/codex/upload-sub2-bulk'],
];
const copies = [
  ['btnCopySelectedEmailsV2', 'email', ['first@example.test', 'second@example.test']],
  ['btnCopySelectedExtractLinksV2', 'extract_link', ['https://example.test/first', 'https://example.test/second']],
];

function setup({request, confirmation = true} = {}) {
  const calls = {requests: [], toasts: [], copies: [], confirmations: []};
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      id, disabled: false, textContent: id, value: '', checked: false, indeterminate: false,
      classList: {toggle() {}, contains: () => true}, listeners: {},
      addEventListener(name, listener) { this.listeners[name] = listener; },
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    ACCOUNT_SELECTED: new Set(), ACCOUNTS: [], CONFIG: [], SHOW_ARCHIVED_ACCOUNTS: false,
    LIST_FACET_LABELS: {task_type: {}, stage: {}, target_status: {}},
    document: {
      getElementById: element, querySelector: () => null, querySelectorAll: () => [], addEventListener() {},
    },
    $: selector => element(selector.slice(1)), window: {addEventListener() {}},
    browserTimeZoneName: () => 'Asia/Shanghai', closeLiveLogModal() {},
    setInterval() {}, setTimeout() {}, clearTimeout() {},
    showToast: message => calls.toasts.push(message),
    copyText: async text => { calls.copies.push(text); return true; },
    confirm: message => { calls.confirmations.push(message); return confirmation; },
    api: async (url, options) => {
      calls.requests.push({url, options});
      if (request) return request(url, options);
      return {started_count: 2, skipped_count: 2, stopped_count: 2, queued_count: 2, skipped: [], started: []};
    },
  });
  vm.runInContext(source, context);
  // 保留真实选择和按钮绑定，仅替换渲染及提交后的轮询，避免测试发起后台请求。
  context.renderAccounts = () => context.updateAccountSelectionUi();
  context.loadAccounts = async () => {};
  context.loadAccountTasks = async () => {};
  context.pollAccountPlanStatuses = async () => {};
  context._pollDeactivationMailResults = async () => {};

  const selectAll = checked => element('accountsSelectAllV2').listeners.change({target: {checked}});
  const changeRow = (id, checked) => {
    const checkbox = {dataset: {accountId: String(id)}, checked};
    element('accountsBodyV2').listeners.change({target: {closest: selector => selector === '.account-row-check' ? checkbox : null}});
  };
  const setPage = rows => { context.ACCOUNTS = rows; context.updateAccountSelectionUi(); };
  const selectTwoPages = () => {
    setPage([7, 8].map(id => ({id, email: `first-${id}@example.test`, account_status: 'active',
      current_plan_type: 'free', codex_status: 'success', codex_execution_status: 'running', email_source: 'cloudflare'})));
    selectAll(true);
    // 当前页没有合格项，上一页的选中账号仍须由服务端检查并执行。
    setPage([9, 10].map(id => ({id, email: `second-${id}@example.test`, account_status: 'deactivated',
      current_plan_type: 'plus', codex_status: 'failed', codex_execution_status: 'failed', email_source: 'outlook'})));
    selectAll(true);
  };
  const click = id => element(id).listeners.click({currentTarget: element(id)});
  return {context, calls, element, selectAll, changeRow, setPage, selectTwoPages, click};
}

for (const [button, endpoint] of actions) {
  test(`${button}：跨页全选提交全部账号，当前页无合格项也不阻断`, async () => {
    const view = setup();
    view.selectTwoPages();
    assert.equal(view.element('accountsSelectedHintV2').textContent, '已选 4 个账号');
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.requests[0].url, endpoint);
    assert.equal(view.calls.requests[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(view.calls.requests[0].options.body).account_ids, [7, 8, 9, 10]);
  });
}

test('取消当前页全选仅移除当前页，单行取消后提交保留的跨页账号', async () => {
  const view = setup();
  view.selectTwoPages();
  view.selectAll(false);
  assert.deepEqual([...view.context.ACCOUNT_SELECTED], [7, 8]);
  assert.equal(view.element('accountsSelectAllV2').checked, false);
  view.setPage([{id: 7, email: 'first@example.test'}, {id: 8, email: 'second@example.test'}]);
  assert.equal(view.element('accountsSelectAllV2').checked, true);
  view.changeRow(7, false);
  assert.deepEqual([...view.context.ACCOUNT_SELECTED], [8]);
  assert.equal(view.element('accountsSelectAllV2').indeterminate, true);
  await view.click('btnCheckSelectedPlansV2');
  assert.deepEqual(JSON.parse(view.calls.requests[0].options.body).account_ids, [8]);
});

test('未选择账号时所有修复操作均保持禁用且直接触发也不会请求', async () => {
  const view = setup();
  view.context.updateAccountSelectionUi();
  for (const [button] of [...actions, ...copies]) {
    assert.equal(view.element(button).disabled, true);
    await view.click(button);
  }
  assert.equal(view.calls.requests.length, 0);
  assert.equal(view.calls.copies.length, 0);
  assert.ok(view.calls.toasts.every(message => /请先选择账号/.test(message)));
});

for (const [button, field, values] of copies) {
  test(`${button}：按全量跨页 ID 读取实时数据并复制返回值`, async () => {
    const view = setup({request: async () => ({values: values.map((value, index) => ({id: index + 7, value}))})});
    view.selectTwoPages();
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.requests[0].url, '/api/accounts/secret-bulk');
    assert.deepEqual(JSON.parse(view.calls.requests[0].options.body), {account_ids: [7, 8, 9, 10], field});
    assert.deepEqual(view.calls.copies, [values.join('\n')]);
    assert.match(view.calls.toasts.join(''), /已复制 2/);
  });

  test(`${button}：读取失败有具体反馈且不复制当前页旧数据`, async () => {
    const view = setup({request: async () => { throw new Error('模拟数据读取失败'); }});
    view.selectTwoPages();
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.copies.length, 0);
    assert.match(view.calls.toasts.join(''), /复制.*失败.*模拟数据读取失败/);
  });

  test(`${button}：全部账号没有可复制值时说明原因`, async () => {
    const view = setup({request: async () => ({values: []})});
    view.selectTwoPages();
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.copies.length, 0);
    assert.match(view.calls.toasts.join(''), /没有/);
  });
}

test('CPA 下载和 Codex 重跑确认使用跨页总数，不以当前页状态推断整批', async () => {
  const view = setup({confirmation: false});
  view.selectTwoPages();
  await view.click('btnDownloadSelectedCpaV2');
  await view.click('btnRetrySelectedCodexV2');
  assert.equal(view.calls.confirmations.length, 2);
  for (const message of view.calls.confirmations) {
    assert.match(message, /4 个账号/);
    assert.doesNotMatch(message, /其中.*(?:2 个账号本地 Codex|已废号 2 个)/s);
  }
  assert.equal(view.calls.requests.length, 0);
});
