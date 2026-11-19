const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/operations/page.js'), 'utf8');
// 保留完整旧入口执行；只替换模块加载边界，避免 Node VM 请求浏览器静态资源。
const executable = source.replace('import(root.dataset.moduleUrl)', 'loadTaskCenterModule(root.dataset.moduleUrl)');

function setup(load) {
  const calls = {imports: [], open: [], refresh: [], visible: [], track: [], tabs: [], toast: [], closes: 0, mounts: 0, resets: 0, network: []};
  let callbacks;
  const api = {
    open: async options => calls.open.push(JSON.parse(JSON.stringify(options))),
    refresh: async options => calls.refresh.push(options),
    setVisible: value => calls.visible.push(value),
    track: (...args) => {
      calls.track.push(args);
      if (args[2]?.navigate !== false) callbacks.onNavigate();
    },
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
        calls.mounts++; callbacks = options; root.children = [{mounted: true}]; return api;
      }};
    },
  };
  vm.runInNewContext(executable, context);
  return {context, bridge: context.window.TaskCenter, calls, root, api};
}
const plain = value => JSON.parse(JSON.stringify(value));
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

test('旧刷新与回执入口保留 metadata 和 navigate false，隐藏未加载页不发请求', async () => {
  const {context, bridge, calls} = setup();
  await context.loadAccountTasks({forceMetadata: true});
  assert.equal(calls.imports.length, 0);
  const references = [{accepted: true, task_id: 17, run_id: 8}];
  await context.trackAcceptedOperationsV2(references, '上传', {navigate: false});
  assert.deepEqual(plain(calls.track[0][0]), references);
  assert.notEqual(calls.track[0][0], references);
  assert.equal(calls.track[0][1], '上传');
  assert.equal(calls.track[0][2].navigate, false);
  assert.deepEqual(calls.tabs, []);
  bridge.setVisible(true);
  await context.loadAccountTasks({forceMetadata: true});
  assert.equal(calls.refresh[0].metadata, true);
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

test('首次回执加载失败后显式打开补交原Run，刷新不重复且不重发业务请求', async () => {
  let attempt = 0;
  const {bridge, calls} = setup(async () => { if (!attempt++) throw new Error('模块离线'); });
  await bridge.track([{accepted: true, task_id: 17, run_id: 8, status: 'accepted'}], '上传', {navigate: false});
  assert.equal(calls.track.length, 0);
  assert.deepEqual(calls.tabs, []);
  await bridge.open({filters: {type: 'sub2api_manual_upload'}, taskId: 17, runId: 8});
  await bridge.refresh();
  assert.deepEqual(plain(calls.track), [[[{accepted: true, task_id: 17, run_id: 8, status: 'accepted'}], '上传', {navigate: false}]]);
  assert.deepEqual(calls.open, [{filters: {type: 'sub2api_manual_upload'}, taskId: 17, runId: 8}]);
  assert.deepEqual(calls.tabs, ['tasks']);
  assert.equal(calls.imports.length, 2);
  assert.equal(calls.mounts, 1);
  assert.deepEqual(calls.network, []);
});

test('连续加载失败后再次显示补交全部FIFO回执，默认导航只执行一次', async () => {
  let attempt = 0;
  const {bridge, calls, root} = setup(async () => { if (++attempt <= 2) throw new Error('模块离线'); });
  await bridge.track([{accepted: true, task_id: 1, run_id: 11}], '第一批');
  await bridge.track([{accepted: true, task_id: 2, run_id: 22}], '第二批');
  bridge.setVisible(true);
  await settle();
  assert.deepEqual(calls.track.map(([refs, label]) => [refs[0].task_id, label]), [[1, '第一批'], [2, '第二批']]);
  assert.deepEqual(calls.tabs, ['tasks']);
  assert.equal(calls.imports.length, 3);
  assert.equal(calls.mounts, 1);
  assert.equal(root.children[0].mounted, true);
  await bridge.refresh();
  assert.equal(calls.track.length, 2);
  assert.deepEqual(calls.network, []);
});

test('失败页面的重试按钮恢复留页回执且沿用最新可见性', async () => {
  let attempt = 0;
  const {bridge, calls, root} = setup(async () => { if (++attempt <= 2) throw new Error('离线'); });
  await bridge.track([{accepted: true, task_id: 17, run_id: 8}], '上传', {navigate: false});
  bridge.setVisible(true); await settle();
  assert.equal(calls.imports.length, 2);
  root.children[1].click(); await settle();
  assert.equal(calls.imports.length, 3);
  assert.equal(calls.track.length, 1);
  assert.equal(calls.track[0][2].navigate, false);
  assert.deepEqual(calls.tabs, []);
  assert.equal(calls.visible.at(-1), true);
});

test('并发回执共享加载并冻结公开字段，显式新详情优先于旧导航', async () => {
  let finish;
  const {bridge, calls} = setup(() => new Promise(resolve => { finish = resolve; }));
  const references = [{accepted: true, task_id: '17', run_id: '8', status: 'accepted', filename: 'omit.json', content: 'private'}];
  const options = {navigate: false};
  const first = bridge.track(references, '第一批', options);
  const second = bridge.track([{accepted: true, task_id: 18, run_id: 9}], '第二批');
  const opening = bridge.open({filters: {type: 'plan_check'}, taskId: 99, runId: 3});
  references[0].run_id = '999'; references[0].status = 'failed'; references.push({accepted: true, task_id: 19});
  options.navigate = true;
  finish(); await Promise.all([first, second, opening]);
  assert.equal(calls.imports.length, 1); assert.equal(calls.mounts, 1);
  assert.deepEqual(plain(calls.track), [
    [[{accepted: true, task_id: '17', run_id: '8', status: 'accepted'}], '第一批', {navigate: false}],
    [[{accepted: true, task_id: 18, run_id: 9}], '第二批', {navigate: false}],
  ]);
  assert.deepEqual(calls.tabs, ['tasks']);
  assert.deepEqual(calls.open, [{filters: {type: 'plan_check'}, taskId: 99, runId: 3}]);
  assert.deepEqual(calls.network, []);
});

test('同步导航和track重入只交付一次队首，新回执仍按FIFO交付', async () => {
  const {bridge, calls, api} = setup();
  const original = api.track;
  let extra;
  api.track = (...args) => {
    if (!extra) extra = bridge.track([{accepted: true, task_id: 2, run_id: 22}], '重入', {navigate: false});
    original(...args);
  };
  await bridge.track([{accepted: true, task_id: 1, run_id: 11}], '初始');
  await extra;
  assert.deepEqual(calls.track.map(([refs]) => refs[0].task_id), [1, 2]);
  assert.deepEqual(calls.tabs, ['tasks']);
  assert.equal(calls.imports.length, 1);
});

test('已挂载组件交付失败保留队首和后续批次，不清空组件或重交成功项', async () => {
  const {bridge, calls, api, root} = setup();
  await bridge.track([{accepted: true, task_id: 1, run_id: 11}], '已交付', {navigate: false});
  const original = api.track;
  let failing = true;
  api.track = (...args) => {
    if (failing) throw new Error('接收回执失败');
    original(...args);
  };
  await bridge.track([{accepted: true, task_id: 2, run_id: 22}], '待恢复', {navigate: false});
  await bridge.track([{accepted: true, task_id: 3, run_id: 33}], '后续', {navigate: false});
  assert.equal(root.children[0].mounted, true);
  assert.equal(calls.resets, 0); assert.equal(calls.mounts, 1);
  failing = false;
  await bridge.refresh();
  assert.deepEqual(calls.track.map(([refs]) => refs[0].task_id), [1, 2, 3]);
  assert.equal(calls.imports.length, 1);
  await bridge.refresh(); assert.equal(calls.track.length, 3);
});

test('首次挂载后交付抛错不会被误判为模块加载失败，重试入口复用已有组件', async () => {
  const {bridge, calls, api, root} = setup();
  const original = api.track;
  let failing = true;
  api.track = (...args) => {
    if (failing) throw new Error('组件暂不能接收');
    original(...args);
  };
  await bridge.track([{accepted: true, task_id: 7, run_id: 8}], '上传', {navigate: false});
  assert.equal(root.children[0].mounted, true);
  assert.equal(calls.resets, 0);
  assert.equal(calls.track.length, 0);
  failing = false;
  await bridge.openDetail(7, 8);
  assert.equal(calls.imports.length, 1); assert.equal(calls.mounts, 1);
  assert.deepEqual(calls.track.map(([refs]) => refs[0].task_id), [7]);
  assert.deepEqual(calls.open, [{taskId: 7, runId: 8, stepId: null}]);
});

for (const cancellation of ['close', 'leave', 'detail']) {
  test(`加载期间${cancellation}撤销旧回执导航但不丢回执`, async () => {
    let finish;
    const {bridge, calls} = setup(() => new Promise(resolve => { finish = resolve; }));
    const tracking = bridge.track([{accepted: true, task_id: 1, run_id: 11}], '原任务');
    let opening;
    if (cancellation === 'close') bridge.closeDetail();
    if (cancellation === 'leave') bridge.setVisible(false);
    if (cancellation === 'detail') opening = bridge.openDetail(88, 99);
    finish(); await Promise.all([tracking, opening]);
    assert.equal(calls.track.length, 1);
    assert.equal(calls.track[0][2].navigate, false);
    assert.deepEqual(calls.tabs, []);
    assert.deepEqual(calls.open, cancellation === 'detail' ? [{taskId: 88, runId: 99, stepId: null}] : []);
  });
}

test('默认回执导航成功后重新显示不会再导航，false回执恢复保持隐藏', async () => {
  const defaults = setup();
  await defaults.bridge.track([{accepted: true, task_id: 1}], '默认');
  defaults.bridge.setVisible(true); await settle();
  assert.deepEqual(defaults.calls.tabs, ['tasks']);
  assert.equal(defaults.calls.track.length, 1);
  let attempt = 0;
  const hidden = setup(async () => { if (!attempt++) throw new Error('离线'); });
  await hidden.bridge.track([{accepted: true, task_id: 2}], '上传', {navigate: false});
  await hidden.bridge.track([{accepted: true, task_id: 3}], '上传2', {navigate: false});
  assert.deepEqual(hidden.calls.track.map(([refs]) => refs[0].task_id), [2, 3]);
  assert.deepEqual(hidden.calls.tabs, []);
  assert.deepEqual(hidden.calls.visible, []);
  assert.deepEqual(hidden.calls.network, []);
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
