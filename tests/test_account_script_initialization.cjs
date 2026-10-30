const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {loadedFiles, readAccountScript} = require('./frontend_script_sources.cjs');

test('账号脚本按模板顺序初始化且关键事件只绑定一次', () => {
  const listeners = new Map();
  const captureKeydowns = [];
  const node = id => ({
    id, value: '', classList: {contains: () => true},
    addEventListener(name, listener) {
      const key = `${id}:${name}`;
      listeners.set(key, [...(listeners.get(key) || []), listener]);
    },
  });
  const nodes = new Map();
  const getNode = id => {
    if (!nodes.has(id)) nodes.set(id, node(id));
    return nodes.get(id);
  };
  const document = {
    addEventListener(name, listener, capture) {
      if (name === 'keydown' && capture === true) captureKeydowns.push(listener);
    },
    getElementById: getNode,
    querySelector: () => null,
    querySelectorAll: () => [],
  };
  const context = vm.createContext({
    document,
    window: {addEventListener() {}},
    $: selector => getNode(selector.slice(1)),
    LIST_FACET_LABELS: {task_type: {}, stage: {}, target_status: {}},
    closeLiveLogModal() {},
    browserTimeZoneName: () => 'Asia/Shanghai',
    setInterval() {},
    clearTimeout() {},
  });

  assert.deepEqual(loadedFiles, [
    'accounts.js', 'account-tasks.js', 'account-email-change.js', 'account-inspection.js',
  ]);
  for (const file of loadedFiles) {
    vm.runInContext(readAccountScript(file), context, {filename: file});
  }
  assert.equal(listeners.get('emailChangeForm:submit')?.length, 1);
  assert.equal(listeners.get('accountTaskLogPanel:wheel')?.length, 1);
  assert.equal(listeners.get('accountInspectionHistory:close')?.length, 1);

  let backgroundFocuses = 0;
  const background = {
    closest: () => ({}),
    focus() { backgroundFocuses++; },
    removeAttribute() {},
    setAttribute() {},
  };
  const tooltip = {classList: {remove() {}}, contains: () => true};
  document.activeElement = tooltip;
  context.stepCloseCalls = 0;
  context.background = background;
  context.tooltip = tooltip;
  vm.runInContext(`
    accountTaskStepDetailState = {stepId: 'test-step'};
    closeAccountTaskStepDialog = () => { globalThis.stepCloseCalls++; };
    _accountsTooltipTarget = background;
    _accountsTooltipNode = tooltip;
  `, context);
  const event = {
    key: 'Escape',
    stopped: false,
    preventDefault() {},
    stopImmediatePropagation() { this.stopped = true; },
  };
  for (const listener of captureKeydowns) {
    listener(event);
    if (event.stopped) break;
  }
  assert.equal(context.stepCloseCalls, 1, '步骤详情先处理 Escape');
  assert.equal(backgroundFocuses, 0, '提示不把焦点移回背景');
});
