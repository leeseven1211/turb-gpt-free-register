const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', '..', 'webui/static/js/pages/email/page.js'), 'utf8');
const rowAction = source.slice(source.indexOf('async function onOutlookBodyClick('), source.indexOf('(function bindOutlookV2()'));
const bulkAction = source.slice(source.indexOf('function _poolDeleteResultMessage('));

function createView(result, accepted = true) {
  const calls = [], toasts = [], confirmations = [], refreshes = [];
  const selected = new Set(['email_butler|unknown@example.test', 'outlook|success@example.test']);
  const button = {disabled: false};
  const context = {
    OUTLOOK_SELECTED: selected,
    getPoolSource: () => 'all',
    document: {getElementById: () => button},
    confirm: text => { confirmations.push(text); return accepted; },
    showToast: text => toasts.push(text),
    api: async (url, options) => { calls.push({url, body: JSON.parse(options.body)}); return result; },
    loadOutlook: () => refreshes.push('list'),
    loadSummary: () => refreshes.push('summary'),
    updateOutlookSelectionUi() {},
  };
  vm.createContext(context);
  vm.runInContext(`${rowAction}\n${bulkAction}\nglobalThis.view = {onOutlookBodyClick, deleteSelectedOutlook};`, context);
  return {view: context.view, calls, toasts, confirmations, refreshes, selected};
}

test('批量删除展示各类跳过原因，只取消已移除项的勾选', async () => {
  const screen = createView({deleted_count: 1,
    deleted: [{source: 'email_butler', email: 'unknown@example.test'}],
    skipped: [
      {reason: '邮箱已确认注册成功，不能删除'},
      {reason: '邮箱已确认注册成功，不能删除'},
      {reason: '邮箱不存在'},
    ],
  });
  await screen.view.deleteSelectedOutlook();
  assert.equal(screen.calls.length, 1);
  assert.equal(screen.calls[0].url, '/api/outlook/delete-bulk');
  assert.equal(screen.calls[0].body.items.length, 2);
  assert.equal(screen.toasts[0], '本地已移除 1 个，跳过 3 个：邮箱已确认注册成功，不能删除（2 个）；邮箱不存在（1 个）');
  assert.deepEqual([...screen.selected], ['outlook|success@example.test']);
  assert.deepEqual(screen.refreshes, ['list', 'summary']);
  assert.match(screen.confirmations[0], /本地邮箱池移除/);
  assert.match(screen.confirmations[0], /保留使用历史/);
  assert.match(screen.confirmations[0], /缺少注册完成回执时保留原租约/);
  assert.match(screen.confirmations[0], /确认账号未创建后才可退还/);
});

test('批量删除统计保留租约，同时保留跳过原因与未删除项勾选', async () => {
  const screen = createView({deleted_count: 1,
    deleted: [{source: 'email_butler', email: 'unknown@example.test',
      sync: {state: 'local_only', lease_retained: true, error_code: 'registration_result_unverified'}}],
    skipped: [{source: 'outlook', email: 'success@example.test', reason: '邮箱已确认注册成功，不能删除'}],
  });
  await screen.view.deleteSelectedOutlook();
  assert.equal(screen.toasts[0], '本地已移除 1 个，其中 1 个已保留原租约，跳过 1 个：邮箱已确认注册成功，不能删除（1 个）');
  assert.deepEqual([...screen.selected], ['outlook|success@example.test']);
});

test('单条删除展示保留原租约的后端说明', async () => {
  const message = '本地已移除，注册结果未确认，已保留原租约';
  const screen = createView({deleted: true,
    sync: {state: 'local_only', lease_retained: true, message}});
  const action = {dataset: {poolAct: 'delete', email: 'unknown@example.test', source: 'email_butler'}};
  await screen.view.onOutlookBodyClick({target: {closest: selector => selector === '[data-pool-act]' ? action : null}});
  assert.deepEqual(screen.toasts, [message]);
  assert.deepEqual([...screen.selected], ['outlook|success@example.test']);
  assert.deepEqual(screen.refreshes, ['list', 'summary']);
  assert.match(screen.confirmations[0], /缺少注册完成回执时保留原租约/);
});

test('单条删除展示活跃注册延后退租的后端说明', async () => {
  const message = '本地已移除，注册仍在执行，结束后再核验租约';
  const screen = createView({deleted: true,
    sync: {state: 'pending', error_code: 'registration_active', message}});
  const action = {dataset: {poolAct: 'delete', email: 'unknown@example.test', source: 'email_butler'}};
  await screen.view.onOutlookBodyClick({target: {closest: selector => selector === '[data-pool-act]' ? action : null}});
  assert.deepEqual(screen.toasts, [message]);
});

test('单条成功保护直接展示后端原因', async () => {
  const screen = createView({deleted: false, reason: '邮箱已确认注册成功，不能删除'});
  const action = {dataset: {poolAct: 'delete', email: 'success@example.test', source: 'outlook'}};
  await screen.view.onOutlookBodyClick({target: {closest: selector => selector === '[data-pool-act]' ? action : null}});
  assert.equal(screen.calls[0].url, '/api/outlook/delete');
  assert.deepEqual(screen.toasts, ['邮箱已确认注册成功，不能删除']);
  assert.equal(screen.selected.size, 2);
  assert.equal(screen.refreshes.length, 0);
  assert.match(screen.confirmations[0], /保留使用历史/);
});

test('取消原有删除确认后不发送请求', async () => {
  const screen = createView({}, false);
  await screen.view.deleteSelectedOutlook();
  assert.equal(screen.calls.length, 0);
  assert.equal(screen.toasts.length, 0);
  assert.equal(screen.selected.size, 2);
});
