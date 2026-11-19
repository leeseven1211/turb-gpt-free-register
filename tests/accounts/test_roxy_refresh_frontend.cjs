const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {installLegacyActionsFixture}=require('./actions_fixture.cjs');

const accounts = require('../frontend_script_sources.cjs').readAccountScripts();
const configSource = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/config/page.js'), 'utf8');
function load(source, names, dependencies = {}) {
  const context = vm.createContext({...dependencies});
  require('../frontend_script_sources.cjs').installAccountActionHelpers(context);
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

test('Roxy 诊断旧入口把指定 Run 交给任务中心，历史运行不被替换', () => {
  // 两个 Run 的产物展示与切换断言已迁至 TaskDetail.test.ts 同名场景；
  // 此处保留旧页面到组件的真实入口及两轮身份契约。
  const opened = [];
  const context = load(accounts, ['openAccountTaskLog'], {
    window: {TaskCenter: {openDetail: (...args) => opened.push(args)}},
  });
  context.openAccountTaskLog(1, 8);
  context.openAccountTaskLog(1, 7);
  assert.deepEqual(opened, [[1, 8, null], [1, 7, null]]);
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
    'accountAtRefreshUiSettings', 'refreshSelectedToken',
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
  installLegacyActionsFixture(context);
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

test('刷新 AT 驱动和调试字段只归属刷新 AT 策略，不重复进入账号补全', async () => {
  const {vueHarness:vue}=require('./actions_fixture.cjs');
  const {createConfigDraft}=vue.load('src/features/config/useConfigDraft.ts');
  const {createConfigActions}=vue.load('src/features/config/configActions.ts');
  const Page=vue.load('src/features/config/ConfigPage.vue').default;
  const navigation=vue.load('src/features/config/navigation.ts');
  const fields = ['ACCOUNT_AT_REFRESH_DRIVER', 'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED', 'OPENAI_PROTOCOL_VERSION',
    'ACCOUNT_LIVE_CHECK_DRIVER', 'LIVE_CHECK_ROXY_FALLBACK_ENABLED', 'ACCOUNT_COMPLETION_REFRESH_AT_ENABLED']
    .map(key=>({key,label:key,group:'账号补全',type:'str',value:''}));
  const owner=createConfigDraft({api:{getSchema:async()=>fields,save:async()=>({ok:true,updated:[]}),invalidate(){}},initialFields:fields});
  const actions=createConfigActions(owner,{request:async()=>({items:[]})});
  const wrapper=vue.mount(Page,{props:{owner,actions}});
  const view={wrapper,async open(name){wrapper.vm.open(name);await vue.nextTick();}};
  try {
    await view.open('刷新 AT');
    const groups=view.wrapper.findAll('.config-vue-setting-group');
    const refresh=groups.find(group=>group.find('h3').exists()&&group.find('h3').text()==='刷新 AT 策略');
    assert.ok(refresh);
    const keys=refresh.findAll('[data-config-setting]').map(item=>item.attributes('data-config-setting'));
    assert.deepEqual(keys,['ACCOUNT_AT_REFRESH_DRIVER','OPENAI_PROTOCOL_VERSION','LIVE_CHECK_ROXY_FALLBACK_ENABLED','ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED']);
    for(const key of keys) assert.equal(view.wrapper.findAll(`[data-config-setting="${key}"]`).length,1);
    await view.open('账号补全');
    assert.deepEqual(view.wrapper.findAll('[data-config-setting]').map(item=>item.attributes('data-config-setting')),['ACCOUNT_COMPLETION_REFRESH_AT_ENABLED']);
    assert.equal(navigation.fieldDomain(fields.find(item=>item.key==='ACCOUNT_LIVE_CHECK_DRIVER')),'查活');
    assert.ok(fields.every(field=>field.group==='账号补全'));
  } finally {wrapper.unmount();actions.dispose();owner.dispose();vue.cleanup();}
});
