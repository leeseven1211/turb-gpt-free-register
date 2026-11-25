const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/codex/page.js'), 'utf8');
// 执行完整旧入口，只替换浏览器动态 import 边界。
const executable = source.replace('import(root.dataset.moduleUrl)', 'loadCodexModule(root.dataset.moduleUrl)');
function setup(load) {
  const calls = {imports: [], visible: [], archived: [], refresh: 0, tasks: [], toast: [], confirm: []};
  let callbacks;
  const api = {
    setVisible: value => calls.visible.push(value),
    setArchived: value => calls.archived.push(value),
    refresh: async () => { calls.refresh++; },
  };
  const root = {dataset: {moduleUrl: '/codex.js', styleUrl: '/task-center.css'}, children: [],
    replaceChildren() { this.children = []; }, append(...items) { this.children.push(...items); }};
  let style;
  const context = {
    window: {TaskCenter: {open: options => calls.tasks.push(options)}},
    showToast: message => calls.toast.push(message),
    confirm: message => { calls.confirm.push(message); return false; },
    getAccountOperationWorkers: () => 3,
    document: {
      getElementById: id => id === 'codex-credentials-root' ? root : id === 'task-center-style' ? style : null,
      createElement: () => ({setAttribute() {}, addEventListener(type, callback) { this[type] = callback; }}),
      head: {append(value) { style = value; }},
    },
    async loadCodexModule(url) { calls.imports.push(url); if (load) await load(); return {mountCodexCredentials: (_, options) => { callbacks = options; return api; }}; },
  };
  vm.runInNewContext(executable, context);
  return {context, bridge: context.window.CodexCredentials, calls, root, callbacks: () => callbacks};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('隐藏的凭证页设置归档和旧入口刷新均不加载模块', async () => {
  const {context, bridge, calls} = setup();
  bridge.setArchived(true);
  await context.loadCodex();
  assert.equal(calls.imports.length, 0);
  await bridge.setVisible(true);
  assert.deepEqual(calls.archived, [true]);
  assert.deepEqual(calls.visible, [true]);
  assert.equal(calls.refresh, 0);
});

test('加载中连续打开只挂载一次，归档与离开采用最后导航状态', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const {bridge, calls} = setup(() => pending);
  const first = bridge.setVisible(true), second = bridge.setVisible(true);
  bridge.setArchived(true);
  bridge.setVisible(false);
  finish(); await Promise.all([first, second]);
  assert.equal(calls.imports.length, 1);
  assert.deepEqual(calls.archived, [true]);
  assert.deepEqual(calls.visible, [false]);
  await bridge.setVisible(true);
  assert.deepEqual(calls.visible, [false, true]);
});

test('旧 loadCodex 在已挂载页显式刷新，加载中不重复刷新', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const {context, bridge, calls} = setup(() => pending);
  const showing = bridge.setVisible(true), refreshing = context.loadCodex();
  finish(); await Promise.all([showing, refreshing]);
  assert.equal(calls.refresh, 0);
  await context.loadCodex();
  assert.equal(calls.refresh, 1);
  bridge.setVisible(false);
  await context.loadCodex();
  assert.equal(calls.refresh, 2);
});

test('动作回调保留取消确认、并发配置和主动进度', async () => {
  const view = setup();
  await view.bridge.setVisible(true);
  const callbacks = view.callbacks();
  callbacks.notify('已入队');
  assert.equal(callbacks.confirm('是否继续'), false);
  assert.equal(callbacks.operationWorkers(), 3);
  callbacks.openTasks('codex_retry');
  callbacks.openTasks();
  assert.deepEqual(JSON.parse(JSON.stringify(view.calls.tasks)), [{filters: {target: '', type: 'codex_retry'}}, {filters: {}}]);
  assert.deepEqual(view.calls.toast, ['已入队']);
});

test('加载失败显示可重试反馈，重试沿用最后归档范围', async () => {
  let attempt = 0;
  const {bridge, calls, root} = setup(async () => { if (!attempt++) throw new Error('连接中断'); });
  await bridge.setVisible(true);
  assert.equal(root.children[0].textContent, '凭证列表加载失败：连接中断');
  assert.equal(root.children[1].textContent, '重新加载');
  bridge.setArchived(true);
  root.children[1].click(); await tick();
  assert.equal(calls.imports.length, 2);
  assert.deepEqual(calls.archived, [true]);
  assert.deepEqual(calls.visible, [true]);
});
