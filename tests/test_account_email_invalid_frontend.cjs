const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/accounts.js'), 'utf8');
function load(names, dependencies = {}) {
  const context = vm.createContext({...dependencies});
  for (const name of names) {
    const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
    assert.ok(match, `应提供 ${name}`);
    const end = source.indexOf('\n}', match.index) + 2;
    vm.runInContext(source.slice(match.index, end), context);
  }
  return context;
}
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

test('邮箱失效徽标独立显示且不会把正常OpenAI账号识别为封号', () => {
  const context = load(['accountIsDeactivated', '_accountEmailInvalidBadge'], {esc: escape});
  const row = {id: 7, email_invalid: true, account_status: 'active', email_invalid_reason: '<邮箱失效>'};
  assert.equal(context.accountIsDeactivated(row), false);
  assert.match(context._accountEmailInvalidBadge(row), />邮箱失效<\/span>/);
  assert.match(context._accountEmailInvalidBadge(row), /&lt;邮箱失效&gt;/);
  assert.equal(context._accountEmailInvalidBadge({...row, email_invalid: false}), '');
});

test('独立邮箱状态筛选进入列表和轮询共用查询参数', () => {
  const controls = new Map([['accountEmailStatusFilterV2', {value: 'invalid'}]]);
  const context = load(['getAccountsQuery', 'accountListQueryParams'], {
    document: {getElementById: id => controls.get(id)}, URLSearchParams,
    SHOW_ARCHIVED_ACCOUNTS: false, SHOW_PLUS_ACCOUNTS_ONLY: false,
    accountAdvancedSearchQuery: '', PAGERS: {accounts: {page: 2, size: 10}},
    columnFilterValue: control => control?.value || '',
  });
  assert.equal(context.accountListQueryParams().get('email_status'), 'invalid');
  controls.get('accountEmailStatusFilterV2').value = 'unmarked';
  assert.equal(context.accountListQueryParams().get('email_status'), 'unmarked');
});

test('更多菜单提供独立标记和解除入口且保留邮箱失效账号的原有操作', () => {
  const context = load(['accountIsDeactivated', '_accountsV2MoreMenu'], {
    esc: escape, _planAction: () => '', _extractLinkAction: () => '', _codexAction: () => '',
    accountAtRefreshUiSettings: () => ({title: '使用已保存的刷新驱动重新登录'}),
  });
  const marked = context._accountsV2MoreMenu({id: 7, email_invalid: true, account_status: 'active'});
  assert.match(marked, /data-account-email-invalid="7"[^>]*data-invalid="0"[^>]*>解除邮箱失效<\/button>/);
  assert.match(marked, /data-account-email-change="7"/);
  assert.match(marked, /刷新AT/);
  assert.doesNotMatch(marked, /data-account-restore/);
  const unmarked = context._accountsV2MoreMenu({id: 8, email_invalid: false});
  assert.match(unmarked, /data-account-email-invalid="8"[^>]*data-invalid="1"[^>]*>标记邮箱失效<\/button>/);
});

function operation(overrides = {}) {
  const calls = {requests: [], toasts: [], reloads: 0};
  const context = load(['setAccountsEmailInvalid'], {
    ACCOUNT_SELECTED: new Set([7, 8]),
    ACCOUNT_SELECTED_EMAILS: new Map([[8, 'page-two@example.test']]),
    ACCOUNTS: [{id: 7, email: 'current@example.test'}],
    prompt: () => '用户确认邮箱失效', confirm: () => true,
    api: async (url, options) => { calls.requests.push({url, options}); return {updated_count: 2, skipped: []}; },
    loadAccounts: async () => { calls.reloads += 1; },
    showToast: message => calls.toasts.push(message), updateAccountSelectionUi() {},
    ...overrides,
  });
  return {context, calls};
}

test('单号和跨页批量打标提交邮箱快照，等待时防止重复提交', async () => {
  let complete;
  const {context, calls} = operation({api: (url, options) => {
    calls.requests.push({url, options});
    return new Promise(resolve => { complete = resolve; });
  }});
  const button = {disabled: false, textContent: '标记邮箱失效'};
  const pending = context.setAccountsEmailInvalid(null, true, button);
  assert.equal(button.disabled, true);
  await context.setAccountsEmailInvalid(null, true, button);
  assert.equal(calls.requests.length, 1);
  assert.equal(calls.requests[0].url, '/api/accounts/email-invalid-bulk');
  assert.equal(calls.requests[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls.requests[0].options.body), {
    account_ids: [7, 8], invalid: true, reason: '用户确认邮箱失效',
    expected_emails: {'7': 'current@example.test', '8': 'page-two@example.test'},
  });
  complete({updated_count: 2, skipped: []});
  await pending;
  assert.equal(calls.reloads, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '标记邮箱失效');
});

test('解除仅清除本地邮箱标记且请求仍携带邮箱快照', async () => {
  const confirms = [];
  const {context, calls} = operation({confirm: text => { confirms.push(text); return true; }});
  await context.setAccountsEmailInvalid([7], false);
  assert.equal(JSON.parse(calls.requests[0].options.body).invalid, false);
  assert.deepEqual(JSON.parse(calls.requests[0].options.body).expected_emails, {'7': 'current@example.test'});
  assert.match(confirms[0], /仅清除本地标记/);
  assert.doesNotMatch(calls.toasts.join(''), /邮箱已恢复/);
});

test('缺失跨页邮箱快照或取消原因输入时不提交标记', async () => {
  for (const override of [{ACCOUNT_SELECTED_EMAILS: new Map()}, {prompt: () => null}]) {
    const {context, calls} = operation(override);
    await context.setAccountsEmailInvalid(null, true);
    assert.equal(calls.requests.length, 0);
  }
});

test('行事件委托把独立邮箱标记动作传给统一提交函数', async () => {
  const button = {dataset: {accountEmailInvalid: '7', invalid: '0'}};
  const calls = [];
  const context = load(['onAccountsBodyClick'], {setAccountsEmailInvalid: async (...args) => calls.push(args)});
  await context.onAccountsBodyClick({target: {closest: selector => selector === '[data-account-email-invalid]' ? button : null}});
  assert.equal(calls.length, 1);
  assert.deepEqual(Array.from(calls[0][0]), [7]);
  assert.equal(calls[0][1], false);
  assert.equal(calls[0][2], button);
});

test('勾选和全选记录邮箱快照，取消选择后不残留快照', () => {
  const context = load(['onAccountsBodyChange', 'syncAccountsSelectAll', 'updateAccountSelectionUi'], {
    ACCOUNT_SELECTED: new Set(), ACCOUNT_SELECTED_EMAILS: new Map(),
    ACCOUNTS: [{id: 7, email: 'seven@example.test'}, {id: 8, email: 'eight@example.test'}],
    $: () => null, document: {getElementById: () => null},
    SHOW_ARCHIVED_ACCOUNTS: false, renderAccounts() {},
  });
  const change = checked => context.onAccountsBodyChange({target: {closest: () => ({checked, dataset: {accountId: '7'}})}});
  change(true);
  assert.equal(context.ACCOUNT_SELECTED_EMAILS.get(7), 'seven@example.test');
  change(false);
  assert.equal(context.ACCOUNT_SELECTED_EMAILS.has(7), false);
  context.syncAccountsSelectAll(true);
  assert.equal(context.ACCOUNT_SELECTED_EMAILS.get(8), 'eight@example.test');
  context.ACCOUNT_SELECTED.clear();
  context.updateAccountSelectionUi();
  assert.equal(context.ACCOUNT_SELECTED_EMAILS.size, 0);
});

test('筛选变更和清筛重置邮箱状态并复用原有重载行为', () => {
  const controls = new Map();
  function control(value = '') {
    return {value, listeners: {}, addEventListener(name, listener) { this.listeners[name] = listener; }, focus() {}};
  }
  for (const [id, value] of [['accountEmailStatusFilterV2', 'invalid'], ['btnResetAccountFiltersV2', ''], ['accountAdvancedSearchV2', '']]) controls.set(id, control(value));
  const calls = {reloads: 0};
  const context = vm.createContext({
    $: selector => controls.get(selector.slice(1)), document: {getElementById: id => controls.get(id)},
    clearTimeout() {}, setTimeout: callback => { callback(); return 1; },
    ACCOUNT_SELECTED: new Set(), PAGERS: {accounts: {page: 3}},
    accountAdvancedSearchQuery: '', accountSearchErrorQuery: null,
    showAccountSearchError() {}, renderAccountSearchTerms() {}, updateAccountSelectionUi() {},
    refreshColumnFilterStates() {}, setColumnFilterValue: (target, value) => { if (target) target.value = value; },
    loadAccounts: () => { calls.reloads += 1; },
  });
  const start = source.indexOf('(function bindAccountsFilterV2()');
  assert.ok(start >= 0);
  const end = source.indexOf('\n})();', start) + '\n})();'.length;
  vm.runInContext(source.slice(start, end), context);
  controls.get('accountEmailStatusFilterV2').listeners.change();
  assert.equal(context.PAGERS.accounts.page, 1);
  assert.equal(calls.reloads, 1);
  controls.get('btnResetAccountFiltersV2').listeners.click();
  assert.equal(controls.get('accountEmailStatusFilterV2').value, '');
  assert.equal(calls.reloads, 2);
});

test('轻量轮询用false和null移除当前页旧邮箱失效显示且不改账号状态', async () => {
  const account = {id: 7, email: 'current@example.test', account_status: 'active', email_invalid: true, email_invalid_reason: '旧原因', email_invalid_at: '旧时间'};
  const calls = {renders: 0, reloads: 0};
  const context = load(['applyAccountStatusSnapshot', 'pollAccountPlanStatuses'], {
    planStatusLoading: false, accountsLoading: false, accountSearchErrorQuery: null,
    accountAdvancedSearchQuery: '', planStatusRevision: 'before',
    accountListQueryParams: () => new URLSearchParams('email_status='), URLSearchParams,
    ACCOUNTS: [account], ACCOUNTS_TOTAL: 1,
    api: async () => ({total: 1, revision: 'after', items: [{id: 7, email_invalid: false, email_invalid_reason: null, email_invalid_at: null, email_invalid_source: null}]}),
    renderAccounts: () => { calls.renders += 1; }, loadAccounts: () => { calls.reloads += 1; },
  });
  await context.pollAccountPlanStatuses();
  assert.equal(account.email_invalid, false);
  assert.equal(account.email_invalid_reason, null);
  assert.equal(account.email_invalid_at, null);
  assert.equal(account.account_status, 'active');
  assert.equal(calls.renders, 1);
  assert.equal(calls.reloads, 0);
  assert.equal(context.planStatusLoading, false);
});
