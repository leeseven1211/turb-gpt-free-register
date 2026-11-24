const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {loadedFiles, readAccountScript} = require('../frontend_script_sources.cjs');
const {mountToolbarFixture,ACCOUNT_TOOLBAR_BUTTONS} = require('./toolbar_fixture.cjs');

test('账号脚本按模板顺序初始化且关键事件只绑定一次', async () => {
  const listeners = new Map();
  const captureKeydowns = [];
  const node = id => ({
    id, value: '', classList: {contains: () => true}, querySelectorAll: () => [],
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
  assert.equal(listeners.has('emailChangeForm:submit'), false, '换邮表单由 Vue 单独绑定');
  assert.equal(listeners.has('accountTaskLogPanel:wheel'), false, '旧任务详情不再绑定监听');
  assert.equal(listeners.has('accountInspectionHistory:close'), false, '巡检生命周期由 Vue 单独绑定');
  for(const button of ACCOUNT_TOOLBAR_BUTTONS)assert.equal(listeners.has(`${button.id}:click`),false,`${button.id} 仅由 Vue 绑定`);
  assert.equal(listeners.has('accountsToolbarV2:click'),false,'旧使用次数 capture listener 已退出');

  const calls = [];
  context.window.TaskCenter = {
    openDetail: (...args) => calls.push(['detail', ...args]),
    refresh: options => calls.push(['refresh', options.metadata]),
    track: (...args) => calls.push(['track', ...args]),
  };
  vm.runInContext("openAccountTaskLog(17, 8, 'authenticate'); loadAccountTasks({forceMetadata:true});", context);
  assert.deepEqual(calls, [['detail', 17, 8, 'authenticate'], ['refresh', true]]);

  const toolbar=mountToolbarFixture();await toolbar.ready;
  for(const button of ACCOUNT_TOOLBAR_BUTTONS){
    assert.equal(toolbar.document.querySelectorAll(`#${button.id}`).length,1);
    assert.equal(toolbar.get(button.id).getAttribute('onclick'),null);
    await toolbar.click(button.id);
  }
  assert.equal(toolbar.calls.length,34,'所有工具栏入口一次点击只调用一次边界');
  assert.deepEqual(toolbar.calls.map(([descriptor])=>descriptor),ACCOUNT_TOOLBAR_BUTTONS.map(button=>button.action));
  assert.deepEqual(toolbar.ids(),[
    'btnCopySelectedTokensV2','btnRefreshSelectedTokenV2','btnCopySelectedLinesV2',
    'btnRetrySelectedCodexV2','btnArchiveSelectedAccountsV2',
  ]);
  assert.equal(toolbar.storage.writes.length,0,'工具栏点击不写入历史使用次数');
});
