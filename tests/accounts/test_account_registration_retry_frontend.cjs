const {createReadFixture,row,list,presentation}=require('./read_owner_fixture.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {installLegacyActionsFixture, legacySelectionSnapshot, vueHarness} = require('./actions_fixture.cjs');

const source = require('../frontend_script_sources.cjs').readAccountScripts();
const template = fs.readFileSync(path.join(__dirname, '../../webui/templates/index.html'), 'utf8');
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
function load(names, dependencies = {}) {
  const context = vm.createContext({...dependencies});
  require('../frontend_script_sources.cjs').installAccountActionHelpers(context);
  for (const name of names) {
    const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
    assert.ok(match, `缺少 ${name}`);
    const end = source.indexOf('\n}', match.index) + 2;
    vm.runInContext(source.slice(match.index, end), context);
  }
  return context;
}

function receiptView(t) {
  vueHarness.cleanup();
  vueHarness.document.body.innerHTML = '<div id="accountRegistrationReceiptHost"></div>';
  const wrapper = vueHarness.mount(vueHarness.load('src/features/accounts/RegistrationRetryReceipt.vue').default);
  t.after(() => vueHarness.cleanup());
  return {wrapper, panel: vueHarness.document.getElementById('accountRegistrationRetryResultV2')};
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
  const calls = {requests: [], confirms: [], messages: [], results: [], navigations: [], taskDetails: [], tasks: [], accounts: 0};
  const context = load(['retryAccountRegistration'], {
    ACCOUNT_SELECTED: new Set([7, 8]),
    ACCOUNTS: [{id: 7, email: 'old@example.com', registration_retry: {label: '继续注册'}}],
    $: () => null,
    confirm: text => { calls.confirms.push(text); return accepted; },
    api: async (url, options) => {
      calls.requests.push({url, body: JSON.parse(options.body)});
      return request ? request() : response || {started: [{account_id: 7, job_id: 99}], started_count: 1};
    },
    showToast: text => calls.messages.push(text),
    showAccountRegistrationRetryResult: result => calls.results.push(result),
    window: {TaskCenter: {open: async options => { calls.tasks.push(JSON.parse(JSON.stringify(options))); }}},
    openLog: jobId => calls.navigations.push([{job_id: jobId}]),
    openAccountTaskLog: (taskId, runId) => calls.taskDetails.push([taskId, runId]),
    loadAccounts: async () => { calls.accounts += 1; },
    updateAccountSelectionUi() {},
  });
  installLegacyActionsFixture(context);
  return {context, calls};
}

function invokeSingleRegistration(context, button = null) {
  return context.window.AccountsPage.invokeAction(
    'account-registration-retry',
    legacySelectionSnapshot(context, {ids: [7]}),
    button,
  );
}

test('单账号 descriptor 提交原注册重跑并优先打开统一任务详情', async () => {
  const {context, calls} = operation({response: {
    started: [{account_id: 7, task_id: 99, run_id: 100, job_id: 99}],
    started_count: 1, reused: [], reused_count: 0, skipped: [], skipped_count: 0,
  }});
  const button = {disabled: false, textContent: '继续注册'};
  await invokeSingleRegistration(context, button);
  assert.deepEqual(calls.requests, [{url: '/api/accounts/7/registration-retry', body: {}}]);
  assert.match(calls.confirms[0], /继续注册/);
  assert.deepEqual(calls.taskDetails, [[99, 100]]);
  assert.deepEqual(calls.tasks, []);
  assert.equal(calls.results.length, 1);
  assert.equal(calls.accounts, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '继续注册');
});

test('批量按账号去重并统一跳任务类型列表，不自动打开回执面板', async () => {
  const {context, calls} = operation({response: {
    started: [{account_id: 7, job_id: 99}], reused: [{account_id: 8, job_id: 100}],
    skipped: [{account_id: 9, reason: '没有原任务'}],
  }});
  await context.retryAccountRegistration([7, '7', 8, 9]);
  assert.deepEqual(calls.requests, [{url: '/api/accounts/registration-retry-bulk', body: {account_ids: [7, 8, 9]}}]);
  assert.deepEqual(calls.tasks, [{filters: {type: 'registration', target: ''}}]);
  assert.equal(calls.navigations.length, 0);
  assert.equal(calls.results.length, 0);
});

test('单账号 descriptor 无统一任务标识时按类型和邮箱打开任务列表', async () => {
  const {context, calls} = operation({response: {started: [], reused: [{account_id: 7, job_id: 100}], reused_count: 1}});
  await invokeSingleRegistration(context);
  assert.deepEqual(calls.tasks, [{filters: {type: 'registration', target: 'old@example.com'}}]);
  assert.deepEqual(calls.taskDetails, []);
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
  assert.equal(context.window.AccountsPage.isActionPending('retryAccountRegistration'), false);
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
  assert.equal(context.window.AccountsPage.isActionPending('retryAccountRegistration'), false);
  assert.match(calls.messages.at(-1), /连接失败/);
});

test('提交已成功但列表刷新失败时保留提交事实，不提示再次重跑', async () => {
  const {context, calls} = operation();
  context.loadAccounts = async () => { throw new Error('列表加载失败'); };
  await context.retryAccountRegistration([7]);
  assert.match(calls.messages.at(-1), /请求已处理.*页面更新失败/);
  assert.doesNotMatch(calls.messages.at(-1), /提交失败/);
  assert.equal(calls.results.length, 0);
  assert.deepEqual(calls.tasks, [{filters: {type: 'registration', target: ''}}]);
});

test('批量结果保留所有跳过原因并转义内容，有原任务和新任务的明确入口', async t => {
  const {wrapper, panel} = receiptView(t);
  const result = {started: [{account_id: 7, job_id: 99}], reused: [{account_id: 8, job_id: 100}], skipped: [
    {account_id: 9, reason: '<script>无来源</script>'}, {account_id: 10, reason: '已完成'},
  ]};
  wrapper.vm.showResult(result, null, () => {}); await vueHarness.nextTick();
  assert.match(panel.textContent, /已创建 1 个.*进行中 1 个.*跳过 2 个/);
  const html = panel.innerHTML;
  assert.match(html, /data-registration-retry-result="0"/);
  assert.match(html, /data-registration-retry-result="1"/);
  assert.match(html, /&lt;script&gt;无来源&lt;\/script&gt;/);
  assert.match(html, /账号 #10.*已完成/);
  assert.doesNotMatch(html, /<script>/);
});

test('定位优先传递统一任务ID，只有注册job时等待任务页打开后使用原日志入口', async () => {
  const calls = [];
  const context = load(['openAccountRegistrationRetryTasks'], {
    window: {AccountsPage:{isReady:()=>true,getActionContext:()=>({accountIds:['7'],expectedEmails:{'7':'fixture@example.test'},archived:'0',querySnapshot:{},rowHints:[{id:7,email:'fixture@example.test'}]})},TaskCenter: {open: async options => { calls.push(['task-center', JSON.parse(JSON.stringify(options))]); }}},
    openLog: (...args) => calls.push(['job', ...args]),
  });
  context.openAccountRegistrationRetryTasks([{account_id: 7, task_id: 21, run_id: 22, job_id: 99}]);
  await Promise.resolve();
  assert.deepEqual(calls, [['task-center', {filters: {target: 'fixture@example.test'}, taskId: 21, runId: 22}]]);
  context.openAccountRegistrationRetryTasks([{account_id: 7, job_id: 100}]);
  await Promise.resolve();
  assert.deepEqual(calls.at(-2), ['task-center', {filters: {target: 'fixture@example.test'}, runId: null}]);
  assert.deepEqual(calls.at(-1), ['job', 100]);
});

for (const [action, taskId, runId] of [['codex', 201, 301], ['plan_check', 202, 302]]) {
  test(`${action} 仅返回 operation_task_id 时直接打开新任务`, () => {
    const calls = [];
    const context = load(['openAccountRegistrationRetryTasks'], {
      ACCOUNTS: [],
      window: {TaskCenter: {open: async options => { calls.push(['task-center', JSON.parse(JSON.stringify(options))]); }}},
      openLog: (...args) => calls.push(['job', ...args]),
    });
    context.openAccountRegistrationRetryTasks([{
      account_id: 7, job_id: 99, operation_task_id: taskId, run_id: runId, retry_action: action,
    }]);
    assert.deepEqual(calls, [['task-center', {filters: {target: ''}, taskId, runId}]]);
  });

  test(`${action} 结果列表按钮携带新任务 ID，点击打开新 Run`, async t => {
    const {wrapper, panel} = receiptView(t);
    const navigations = [];
    const context = load([
      'showAccountRegistrationRetryResult', 'openAccountRegistrationRetryTasks',
    ], {
      esc, $: selector => selector === '#accountRegistrationRetryResultV2' ? panel : null,
      ACCOUNTS: [],
      window: {AccountsPage: {showRegistrationResult: (...args) => wrapper.vm.showResult(...args)},
        TaskCenter: {open: async options => { navigations.push(['task-center', JSON.parse(JSON.stringify(options))]); }}},
      openLog: (...args) => navigations.push(['job', ...args]),
    });
    context.showAccountRegistrationRetryResult({started: [{
      account_id: 7, job_id: 99, operation_task_id: taskId, run_id: runId, retry_action: action,
    }]});
    await vueHarness.nextTick();
    const buttons = panel.querySelectorAll('[data-registration-retry-result]');
    assert.equal(buttons[0].dataset.registrationRetryTaskId, String(taskId));
    assert.equal(buttons[0].dataset.registrationRetryRunId, String(runId));
    buttons[0].click(); await vueHarness.nextTick();
    assert.deepEqual(navigations, [['task-center', {filters: {target: ''}, taskId, runId}]]);
  });
}

test('更多菜单事件使用注册重跑入口，活动任务只查看', async t => {
  const h=createReadFixture(t,{mounted:true,handlers:{list:async()=>list([row(7)])},render:{...presentation,menu:()=>'<button data-account-registration-retry="7">重跑</button><button data-account-registration-task="100" data-account-id="7">查看</button>'}});await h.ready;
  for(const [selector,action] of [['[data-account-registration-retry]','account-registration-retry'],['[data-account-registration-task]','account-registration-task:100']]){
    await h.wrapper.get('button[aria-label="更多账号操作"]').trigger('click');await h.settle();
    const button=h.body.get(selector);await button.trigger('click');await h.settle();
    const call=h.calls.at(-1);assert.equal(call[0],action);assert.deepEqual([...call[1].accountIds],['7']);assert.equal(Object.isFrozen(call[1]),true);assert.equal(call[2],button.element);
  }
  assert.equal(h.calls.length,2);
});

test('批量重跑工具栏按钮纳入勾选控制并绑定提交，原补全按钮保留', async () => {
  const {mountToolbarFixture} = require('./toolbar_fixture.cjs');
  const ui = mountToolbarFixture({state: {selectedCount: 0, archived: false}}); await ui.ready;
  const button = ui.get('btnRetrySelectedRegistrationV2');
  assert.equal(button.disabled, true); assert.equal(button.textContent, '重跑注册');
  assert.ok(ui.get('btnCompleteSelectedAccountsV2'));
  assert.match(template, /id="accountRegistrationReceiptHost"/);
  await ui.setState({selectedCount: 2}); await ui.click('btnRetrySelectedRegistrationV2');
  assert.equal(ui.calls[0][0], 'retryAccountRegistration');
});
