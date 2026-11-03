const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = require('../frontend_script_sources.cjs').readAccountScripts();
const template = fs.readFileSync(path.join(__dirname, '../../webui/templates/index.html'), 'utf8');
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
function load(names, dependencies = {}) {
  const context = vm.createContext({...dependencies});
  for (const name of names) {
    const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
    assert.ok(match, `缺少 ${name}`);
    const end = source.indexOf('\n}', match.index) + 2;
    vm.runInContext(source.slice(match.index, end), context);
  }
  return context;
}

test('行菜单根据后端资格显示继续、查看进行中任务或不可用原因', () => {
  const context = load(['accountIsDeactivated', '_accountsV2MoreMenu'], {
    esc, accountAtRefreshUiSettings: () => ({title: ''}),
    _planAction: () => '', _extractLinkAction: () => '', _codexAction: () => '',
  });
  const menu = registration_retry => context._accountsV2MoreMenu({id: 7, registration_retry});
  assert.match(menu({available: true, source_job_id: 99, label: '继续注册', reason: '复用原邮箱'}), /data-account-registration-retry="7"[^>]*>继续注册/);
  const active = menu({available: false, active: true, source_job_id: 100, reason: '任务运行中'});
  assert.match(active, /data-account-registration-task="100"/);
  assert.doesNotMatch(active, /data-account-registration-retry=/);
  for (const reason of ['账号已完成注册', '找不到原注册任务']) {
    const unavailable = menu({available: false, reason});
    assert.match(unavailable, new RegExp(`title="${reason}"[^>]*disabled[^>]*>重跑注册`));
    assert.doesNotMatch(unavailable, /data-account-registration-retry=/);
  }
  assert.doesNotMatch(menu(undefined), /data-account-registration-retry=/);
});

test('账号页刷新说明识别 v3，会话失效后才重新认证', () => {
  const context = load(['accountAtRefreshUiSettings'], {CONFIG: []});
  const fields = [{key: 'ACCOUNT_AT_REFRESH_DRIVER', value: 'protocol'}, {key: 'OPENAI_PROTOCOL_VERSION', value: 'v3'}];
  const result = context.accountAtRefreshUiSettings(fields);
  assert.equal(result.label, '协议刷新（v3）');
  assert.match(result.description, /先复用.*登录会话/);
  assert.match(result.description, /失效.*密码、2FA 或邮箱验证/);
  for (const version of ['v1', 'v2']) {
    fields[1].value = version;
    assert.equal(context.accountAtRefreshUiSettings(fields).label, `协议刷新（${version}）`);
  }
  fields[0].value = 'browser_roxy';
  fields[1].value = 'v3';
  assert.equal(context.accountAtRefreshUiSettings(fields).label, 'Roxy 指纹浏览器');
});

function operation({response, request, accepted = true} = {}) {
  const calls = {requests: [], confirms: [], messages: [], results: [], navigations: [], accounts: 0};
  const context = load(['retryAccountRegistration'], {
    ACCOUNT_SELECTED: new Set([7, 8]), ACCOUNT_REGISTRATION_RETRY_PENDING: new Set(),
    ACCOUNTS: [{id: 7, registration_retry: {label: '继续注册'}}],
    $: () => null,
    confirm: text => { calls.confirms.push(text); return accepted; },
    api: async (url, options) => {
      calls.requests.push({url, body: JSON.parse(options.body)});
      return request ? request() : response || {started: [{account_id: 7, job_id: 99}], started_count: 1};
    },
    showToast: text => calls.messages.push(text),
    accountRegistrationRetrySummary: () => '已创建 1 个',
    showAccountRegistrationRetryResult: result => calls.results.push(result),
    openAccountRegistrationRetryTasks: items => calls.navigations.push(items),
    loadAccounts: async () => { calls.accounts += 1; },
    updateAccountSelectionUi() {},
  });
  return {context, calls};
}

test('单账号调用原注册重跑适配接口，直接打开新任务', async () => {
  const {context, calls} = operation();
  const button = {disabled: false, textContent: '继续注册'};
  await context.retryAccountRegistration([7], button);
  assert.deepEqual(calls.requests, [{url: '/api/accounts/7/registration-retry', body: {}}]);
  assert.match(calls.confirms[0], /继续注册/);
  assert.equal(calls.navigations[0][0].job_id, 99);
  assert.equal(calls.results.length, 1);
  assert.equal(calls.accounts, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '继续注册');
});

test('批量按账号去重，仅提交账号 ID，结果留在账号页供逐项查看', async () => {
  const {context, calls} = operation({response: {
    started: [{account_id: 7, job_id: 99}], reused: [{account_id: 8, job_id: 100}],
    skipped: [{account_id: 9, reason: '没有原任务'}],
  }});
  await context.retryAccountRegistration([7, '7', 8, 9]);
  assert.deepEqual(calls.requests, [{url: '/api/accounts/registration-retry-bulk', body: {account_ids: [7, 8, 9]}}]);
  assert.equal(calls.navigations.length, 0);
  assert.equal(calls.results[0].skipped[0].reason, '没有原任务');
});

test('单号已在执行时打开进行中任务，不误报新建', async () => {
  const {context, calls} = operation({response: {started: [], reused: [{account_id: 7, job_id: 100}], reused_count: 1}});
  await context.retryAccountRegistration([7]);
  assert.equal(calls.navigations[0][0].job_id, 100);
});

test('提交中的账号在按钮重绘或另一个入口再次点击时也不重复提交', async () => {
  let finish;
  const {context, calls} = operation({request: () => new Promise(resolve => { finish = resolve; })});
  const first = context.retryAccountRegistration([7], {disabled: false, textContent: '继续注册'});
  await context.retryAccountRegistration([7], {disabled: false, textContent: '继续注册'});
  assert.equal(calls.requests.length, 1);
  assert.match(calls.messages.at(-1), /正在提交/);
  finish({started: [{account_id: 7, job_id: 99}]});
  await first;
  assert.equal(context.ACCOUNT_REGISTRATION_RETRY_PENDING.size, 0);
});

test('取消确认不提交；请求失败恢复按钮并允许再次提交', async () => {
  const cancelled = operation({accepted: false});
  await cancelled.context.retryAccountRegistration([7]);
  assert.equal(cancelled.calls.requests.length, 0);
  const {context, calls} = operation({request: async () => { throw new Error('连接失败'); }});
  const button = {disabled: false, textContent: '重跑注册'};
  await context.retryAccountRegistration([7], button);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '重跑注册');
  assert.equal(context.ACCOUNT_REGISTRATION_RETRY_PENDING.size, 0);
  assert.match(calls.messages.at(-1), /连接失败/);
});

test('提交已成功但列表刷新失败时保留提交事实，不提示再次重跑', async () => {
  const {context, calls} = operation();
  context.loadAccounts = async () => { throw new Error('列表加载失败'); };
  await context.retryAccountRegistration([7]);
  assert.match(calls.messages.at(-1), /请求已处理.*页面更新失败/);
  assert.doesNotMatch(calls.messages.at(-1), /提交失败/);
  assert.equal(calls.results.length, 1);
});

test('批量结果保留所有跳过原因并转义内容，有原任务和新任务的明确入口', () => {
  const context = load(['accountRegistrationRetrySummary', 'renderAccountRegistrationRetryResult'], {esc});
  const result = {started: [{account_id: 7, job_id: 99}], reused: [{account_id: 8, job_id: 100}], skipped: [
    {account_id: 9, reason: '<script>无来源</script>'}, {account_id: 10, reason: '已完成'},
  ]};
  assert.match(context.accountRegistrationRetrySummary(result), /已创建 1 个.*进行中 1 个.*跳过 2 个/);
  const html = context.renderAccountRegistrationRetryResult(result);
  assert.match(html, /data-registration-retry-result="0"/);
  assert.match(html, /data-registration-retry-result="1"/);
  assert.match(html, /&lt;script&gt;无来源&lt;\/script&gt;/);
  assert.match(html, /账号 #10.*已完成/);
  assert.doesNotMatch(html, /<script>/);
});

test('定位优先使用统一任务ID，只有注册job时使用现有日志入口', () => {
  const calls = [];
  const filters = new Map();
  const context = load(['openAccountRegistrationRetryTasks'], {
    $: selector => { if (!filters.has(selector)) filters.set(selector, {value: '旧筛选'}); return filters.get(selector); },
    PAGERS: {accountTasks: {page: 4}}, ACCOUNTS: [{id: 7, email: 'fixture@example.test'}],
    activateTab: tab => calls.push(['tab', tab]),
    openAccountTaskLog: (...args) => calls.push(['task', ...args]),
    openLog: (...args) => calls.push(['job', ...args]),
  });
  context.openAccountRegistrationRetryTasks([{account_id: 7, task_id: 21, run_id: 22, job_id: 99}]);
  assert.deepEqual(calls.at(-1), ['task', 21, 22]);
  assert.equal(filters.get('#accountTaskTypeFilterV2').value, '');
  assert.equal(filters.get('#accountTaskTargetFilterV2').value, 'fixture@example.test');
  context.openAccountRegistrationRetryTasks([{account_id: 7, job_id: 100}]);
  assert.deepEqual(calls.at(-1), ['job', 100]);
});

for (const [action, taskId, runId] of [['codex', 201, 301], ['plan_check', 202, 302]]) {
  test(`${action} 仅返回 operation_task_id 时直接打开新任务`, () => {
    const calls = [];
    const context = load(['openAccountRegistrationRetryTasks'], {
      $: () => null, PAGERS: {accountTasks: {page: 1}}, ACCOUNTS: [],
      activateTab() {},
      openAccountTaskLog: (...args) => calls.push(['task', ...args]),
      openLog: (...args) => calls.push(['job', ...args]),
    });
    context.openAccountRegistrationRetryTasks([{
      account_id: 7, job_id: 99, operation_task_id: taskId, run_id: runId, retry_action: action,
    }]);
    assert.deepEqual(calls, [['task', taskId, runId]]);
  });

  test(`${action} 结果列表按钮携带新任务 ID，点击打开新 Run`, () => {
    const calls = [];
    const buttons = [];
    const panel = {
      hidden: true,
      set innerHTML(html) {
        this.html = html;
        for (const match of html.matchAll(/<button[^>]*data-registration-retry-result="(\d+)"[^>]*>/g)) {
          const dataset = {registrationRetryResult: match[1]};
          const task = /data-registration-retry-task-id="(\d+)"/.exec(match[0]);
          const run = /data-registration-retry-run-id="(\d+)"/.exec(match[0]);
          if (task) dataset.registrationRetryTaskId = task[1];
          if (run) dataset.registrationRetryRunId = run[1];
          buttons.push({dataset, addEventListener: (_event, fn) => calls.push(fn)});
        }
      },
      querySelector: () => null,
      querySelectorAll: () => buttons,
    };
    const navigations = [];
    const context = load([
      'accountRegistrationRetrySummary', 'renderAccountRegistrationRetryResult',
      'showAccountRegistrationRetryResult', 'openAccountRegistrationRetryTasks',
    ], {
      esc, $: selector => selector === '#accountRegistrationRetryResultV2' ? panel : null,
      PAGERS: {accountTasks: {page: 1}}, ACCOUNTS: [], activateTab() {},
      openAccountTaskLog: (...args) => navigations.push(['task', ...args]),
      openLog: (...args) => navigations.push(['job', ...args]),
    });
    context.showAccountRegistrationRetryResult({started: [{
      account_id: 7, job_id: 99, operation_task_id: taskId, run_id: runId, retry_action: action,
    }]});
    assert.equal(buttons[0].dataset.registrationRetryTaskId, String(taskId));
    assert.equal(buttons[0].dataset.registrationRetryRunId, String(runId));
    calls[0]();
    assert.deepEqual(navigations, [['task', taskId, runId]]);
  });
}

test('更多菜单事件使用注册重跑入口，活动任务只查看', async () => {
  const calls = [];
  const context = load(['onAccountsBodyClick'], {
    closeAccountsV2MoreMenus() {},
    retryAccountRegistration: (...args) => calls.push(['retry', ...args]),
    openAccountRegistrationRetryTasks: items => calls.push(['view', items]),
  });
  const button = {dataset: {accountRegistrationRetry: '7'}};
  await context.onAccountsBodyClick({target: {closest: selector => selector === '[data-account-registration-retry]' ? button : null}});
  assert.equal(calls[0][0], 'retry');
  assert.equal(calls[0][1][0], 7);
  assert.equal(calls[0][2], button);
  const active = {dataset: {accountRegistrationTask: '100', accountId: '7'}};
  await context.onAccountsBodyClick({target: {closest: selector => selector === '[data-account-registration-task]' ? active : null}});
  assert.equal(calls[1][0], 'view');
  assert.equal(calls[1][1][0].job_id, 100);
});

test('批量重跑工具栏按钮纳入勾选控制并绑定提交，原补全按钮保留', () => {
  assert.match(template, /id="btnRetrySelectedRegistrationV2"[^>]*disabled[^>]*>重跑注册/);
  assert.match(template, /id="accountRegistrationRetryResultV2"[^>]*hidden/);
  assert.match(source, /bind\('btnRetrySelectedRegistrationV2',/);
  assert.match(source, /'btnRetrySelectedRegistrationV2'/);
  assert.match(template, /id="btnCompleteSelectedAccountsV2"/);
});
