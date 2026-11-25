const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/operations/page.js'), 'utf8');
// 保留完整旧入口执行；只替换模块加载边界，避免 Node VM 请求浏览器静态资源。
const executable = source.replace('import(root.dataset.moduleUrl)', 'loadTaskCenterModule(root.dataset.moduleUrl)');

function setup(load) {
  const calls = {imports: [], open: [], refresh: [], visible: [], tabs: [], toast: [], closes: 0, mounts: 0, resets: 0, network: []};
  const api = {
    open: async options => calls.open.push(JSON.parse(JSON.stringify(options))),
    refresh: async options => calls.refresh.push(options),
    setVisible: value => calls.visible.push(value),
    closeDetail: () => { calls.closes++; },
  };
  const root = {dataset: {moduleUrl: '/module.js', styleUrl: '/module.css'}, children: [],
    replaceChildren() { calls.resets++; this.children = []; }, append(...items) { this.children.push(...items); }};
  let style;
  const context = {
    window: {}, ACTIVE_TAB: 'bulk', loadAccounts() {}, showToast: message => calls.toast.push(message),
    api(...args) { calls.network.push(args); throw new Error('bridge 不得重新提交业务请求'); },
    fetch(...args) { calls.network.push(args); throw new Error('bridge 不得重新提交业务请求'); },
    document: {
      getElementById: id => id === 'task-center-root' ? root : id === 'task-center-style' ? style : null,
      createElement: () => ({listeners: {}, setAttribute() {},
        addEventListener(name, listener) { this.listeners[name] = listener; },
        click() { this.listeners.click?.(); }}),
      head: {append(value) { style = value; }},
    },
    activateTab(tab) {
      if (tab !== context.ACTIVE_TAB) context.window.TaskCenter.closeDetail();
      context.ACTIVE_TAB = tab;
      calls.tabs.push(tab); context.window.TaskCenter.setVisible(tab === 'tasks');
    },
    async loadTaskCenterModule(url) {
      calls.imports.push(url); if (load) await load();
      return {mountTaskCenter: (_root, options) => {
        calls.mounts++; root.children = [{mounted: true}]; return api;
      }};
    },
  };
  vm.runInNewContext(executable, context);
  return {context, bridge: context.window.TaskCenter, calls, root, api};
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('旧批次 dataset 字符串 Run ID 在入口转换，保留指定执行与步骤且不跳离原页', async () => {
  const {context, calls} = setup();
  await context.openAccountTaskLog('17', '8', 'authenticate');
  assert.deepEqual(calls.open, [{taskId: 17, runId: 8, stepId: 'authenticate'}]);
  assert.deepEqual(calls.tabs, []);
});

test('跨页入口清单参数原样交给组件，任务和运行标识统一为数字', async () => {
  const {bridge, calls} = setup();
  await bridge.open({filters: {type: 'password_setup,twofa_setup', target: 'fixture@example.test'}, taskId: '17', runId: '8'});
  assert.deepEqual(calls.open, [{filters: {type: 'password_setup,twofa_setup', target: 'fixture@example.test'}, taskId: 17, runId: 8}]);
  assert.deepEqual(calls.tabs, ['tasks']);
  assert.deepEqual(calls.visible, [true]);
});

test('懒加载合并且只打开最后一次请求，导航关闭会撤销未完成详情入口', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const {bridge, calls} = setup(() => pending);
  const first = bridge.openDetail(1, 11), second = bridge.openDetail(2, 22);
  finish(); await Promise.all([first, second]);
  assert.equal(calls.imports.length, 1);
  assert.deepEqual(calls.open, [{taskId: 2, runId: 22, stepId: null}]);

  let finishNext;
  const nextPending = new Promise(resolve => { finishNext = resolve; });
  const next = setup(() => nextPending);
  const opening = next.bridge.openDetail(3, 33);
  next.bridge.closeDetail(); finishNext(); await opening;
  assert.deepEqual(next.calls.open, []);
});

test('加载期间离开任务页不会在加载完成后开启列表轮询', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const {bridge, calls} = setup(() => pending);
  bridge.setVisible(true); bridge.setVisible(false); finish();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls.visible, [false]);
});

test('旧刷新入口保留 metadata，隐藏未加载页不发请求', async () => {
  const {context, bridge, calls} = setup();
  await context.loadAccountTasks({forceMetadata: true});
  assert.equal(calls.imports.length, 0);
  bridge.setVisible(true); await settle();
  await context.loadAccountTasks({forceMetadata: true});
  assert.equal(calls.refresh[0].metadata, true);
  assert.deepEqual(calls.tabs, []);
});

test('模块加载失败留重试入口，下次调用可以重新加载', async () => {
  let attempt = 0;
  const {bridge, calls, root} = setup(async () => { if (!attempt++) throw new Error('加载中断'); });
  await bridge.openDetail(17, 8);
  assert.equal(root.children[0].textContent, '任务中心加载失败：加载中断');
  assert.equal(root.children[1].textContent, '重新加载');
  await bridge.openDetail(17, 8);
  assert.equal(calls.imports.length, 2);
  assert.deepEqual(calls.open, [{taskId: 17, runId: 8, stepId: null}]);
});

// Bigint task and run ID compatibility.

test('bigint bridge preserves task/run IDs in both entry points', async () => {
  const {bridge, calls} = setup();
  await bridge.openDetail('9007199254740993', '9223372036854775807');
  await bridge.open({taskId: '9007199254740995', runId: '9007199254740997'});
  assert.deepEqual(calls.open, [{taskId: '9007199254740993', runId: '9223372036854775807', stepId: null}, {taskId: '9007199254740995', runId: '9007199254740997'}]);
});
test('unsafe numeric ID is rejected before opening a guessed task', async () => {
  const {bridge, calls} = setup();
  await bridge.openDetail(9007199254740992, 8);
  assert.deepEqual(calls.open, []);
  assert.equal(calls.toast.length, 1);
});
