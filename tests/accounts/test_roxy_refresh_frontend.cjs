const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const accounts = require('../frontend_script_sources.cjs').readAccountScripts();
const configSource = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/config/page.js'), 'utf8');
function load(source, names, dependencies = {}) {
  const context = vm.createContext({...dependencies});
  for (const name of names) {
    const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
    assert.ok(match, `应提供 ${name}`);
    const end = source.indexOf('\n}', match.index) + 2;
    vm.runInContext(source.slice(match.index, end), context);
  }
  return context;
}
const browserConfig = [
  {key: 'ACCOUNT_AT_REFRESH_DRIVER', value: 'browser_roxy'},
  {key: 'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED', value: true},
  {key: 'OPENAI_PROTOCOL_VERSION', value: 'v2'},
];

test('诊断入口绑定当前 Run，切换历史运行时不展示其它运行的产物', () => {
  const panel = {innerHTML: ''};
  const context = load(accounts, ['renderAccountTaskArtifacts'], {
    $: () => panel, activeAccountTaskRunId: 8, esc: value => String(value), formatDateTime: () => '',
  });
  const task = {resources: [], runs: [
    {id: 7, debug_artifacts: {available: true, har_url: '/run-7/har'}},
    {id: 8, result_summary: {debug_browser_kept: true}, debug_artifacts: {
      available: true, state: 'failed', har_url: '/run-8/har', screenshot_url: '/run-8/screenshot',
      page_state_url: '/run-8/page-state', summary: {request_count: 12},
    }},
  ]};
  context.renderAccountTaskArtifacts(task);
  assert.match(panel.innerHTML, /run-8\/har/);
  assert.match(panel.innerHTML, /失败窗口已保留/);
  assert.match(panel.innerHTML, /查看失败截图/);
  assert.doesNotMatch(panel.innerHTML, /run-7/);
});

test('刷新描述按驱动和布尔调试值生成，不固定承诺邮箱 OTP', () => {
  const context = load(accounts, ['accountAtRefreshUiSettings'], {CONFIG: browserConfig});
  const browser = context.accountAtRefreshUiSettings();
  assert.equal(browser.label, 'Roxy 指纹浏览器');
  assert.match(browser.description, /Roxy 指纹浏览器.*密码、2FA 或邮箱验证/);
  assert.match(browser.debugDescription, /显示浏览器.*全程抓包.*失败保留窗口.*HAR/);
  assert.doesNotMatch(browser.description, /协议刷新|通过邮箱 OTP/);
  const protocol = context.accountAtRefreshUiSettings([
    {key: 'ACCOUNT_AT_REFRESH_DRIVER', value: 'protocol'},
    {key: 'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED', value: 'False'},
    {key: 'OPENAI_PROTOCOL_VERSION', value: 'v2'},
  ]);
  assert.equal(protocol.label, '协议刷新（v2）');
  assert.equal(protocol.debugEnabled, false);
  assert.equal(protocol.debugDescription, '');
  assert.match(context.accountAtRefreshUiSettings([]).description, /已保存的刷新驱动/);
});

function operation({accepted = true, response, readConfig} = {}) {
  const calls = {confirms: [], requests: [], tasks: [], legacyLogs: []};
  const context = load(accounts, [
    'accountAtRefreshUiSettings', 'loadAccountAtRefreshUiSettings', 'refreshSelectedToken',
  ], {
    CONFIG: [], ACCOUNT_SELECTED: new Set(),
    getAccountOperationWorkers: () => 3,
    apiCached: readConfig || (async () => browserConfig),
    confirm: message => { calls.confirms.push(message); return accepted; },
    api: async (url, options) => {
      calls.requests.push({url, options});
      return response || {started_count: 1, started: [{task_id: 7, run_id: 8, email: 'fixture@example.test'}]};
    },
    accountBulkQueueReasons: () => '', showToast() {},
    openAccountTaskLog: (...args) => calls.tasks.push(args),
    openLiveLog: email => calls.legacyLogs.push(email),
    loadAccounts: async () => {}, loadSummary() {}, updateAccountSelectionUi() {}, $: () => null,
  });
  return {context, calls};
}

test('确认使用已保存的 Roxy 配置并说明保留现场，打开本次任务日志', async () => {
  const {context, calls} = operation();
  const button = {disabled: false, textContent: '刷新AT'};
  await context.refreshSelectedToken([7], button);
  assert.match(calls.confirms[0], /Roxy 指纹浏览器.*重新登录/s);
  assert.match(calls.confirms[0], /全程抓包.*失败保留窗口/s);
  assert.deepEqual(JSON.parse(calls.requests[0].options.body), {account_ids: [7]});
  assert.deepEqual(calls.tasks, [[7, 8]]);
  assert.deepEqual(calls.legacyLogs, []);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '刷新AT');
});

test('读取配置期间阻止重复提交，取消确认后恢复按钮且不创建任务', async () => {
  let finishConfig;
  const {context, calls} = operation({accepted: false, readConfig: () => new Promise(resolve => { finishConfig = resolve; })});
  const button = {disabled: false, textContent: '刷新AT'};
  const pending = context.refreshSelectedToken([7], button);
  assert.equal(button.disabled, true);
  assert.equal(button.textContent, '读取配置…');
  await context.refreshSelectedToken([7], button);
  assert.deepEqual(calls.requests, []);
  finishConfig(browserConfig);
  await pending;
  assert.equal(calls.confirms.length, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '刷新AT');
});

test('旧接口没有任务 ID 时继续打开本次账号日志', async () => {
  const {context, calls} = operation({response: {started_count: 1, started: [{email: 'fixture@example.test'}]}});
  await context.refreshSelectedToken([7], {disabled: false, textContent: '刷新AT'});
  assert.deepEqual(calls.tasks, []);
  assert.deepEqual(calls.legacyLogs, ['fixture@example.test']);
});

test('刷新驱动和 Roxy 调试字段仅展示在独立刷新 AT 菜单的刷新策略中', () => {
  const refreshKeys = [
    'ACCOUNT_AT_REFRESH_DRIVER', 'OPENAI_PROTOCOL_VERSION', 'LIVE_CHECK_ROXY_FALLBACK_ENABLED',
    'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED',
  ];
  const fields = [...refreshKeys, 'ACCOUNT_LIVE_CHECK_DRIVER'].map(key => ({key, group: '账号补全'}));
  const events = {addEventListener() {}};
  const context = vm.createContext({CONFIG: fields, $: () => events, window: events, esc: String, attrEsc: String});
  vm.runInContext(configSource, context);
  const groups = [];
  const domains = context.configDomainGroupsV2(context.configGroups()['注册与账号']);
  for (const [domain, items] of Object.entries(domains)) {
    context.renderConfigSettingGroupV2 = (section, rows) => {
      if (rows.length) groups.push({domain, section, keys: Array.from(rows, row => row.key)});
      return '';
    };
    context.renderConfigDomainSectionV2(domain, items);
  }
  assert.deepEqual(groups, [
    {domain: '刷新 AT', section: '刷新 AT 策略', keys: refreshKeys},
    {domain: '查活', section: '查活策略', keys: ['ACCOUNT_LIVE_CHECK_DRIVER']},
  ]);
});
