const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..', '..');
const operations = fs.readFileSync(path.join(root, 'webui/static/js/pages/operations/page.js'), 'utf8');
const codex = fs.readFileSync(path.join(root, 'webui/static/js/pages/codex/page.js'), 'utf8');
const resultFunction = operations.slice(
  operations.indexOf('function accountTaskResultText('),
  operations.indexOf('\nfunction normalizeAccountTaskStage('),
);
const reauthorizeFunction = codex.slice(
  codex.indexOf('async function codexReauthorize('),
  codex.indexOf('\nasync function codexRefreshTokens('),
);

test('Codex 授权任务分别展示自动上传成功、失败、停止及未启用结果', () => {
  const context = {};
  vm.runInNewContext(resultFunction, context);
  const summary = (extra = {}) => context.accountTaskResultText({
    task_type: 'codex_retry', status: 'success',
    result_summary: {ok: true, credential_confirmed: true, ...extra},
  });
  assert.equal(summary({sub2api_sync: {status: 'success'}}), '授权成功 · sub2api 已启用');
  assert.equal(summary({sub2api_sync: {status: 'failed'}}), '授权成功 · sub2api 同步失败');
  assert.equal(summary({sub2api_sync: {status: 'cancelled'}}), '授权成功 · sub2api 同步已停止');
  assert.equal(summary(), '授权成功 · 凭证已确认');
  assert.equal(summary({credential_confirmed: false}), '授权成功');
});

test('重新授权确认说明开关开启后自动同步，关闭时仍可手工上传', async () => {
  let note = '';
  const context = {
    getAccountOperationWorkers: () => 3,
    confirm(value) { note = value; return false; },
  };
  vm.runInNewContext(reauthorizeFunction, context);
  await context.codexReauthorize(['codex-test.json']);

  assert.ok(note.includes('更新本地 Codex 凭证'));
  assert.ok(note.includes('授权后自动上传并启用 sub2api'));
  assert.ok(note.includes('开启'));
  assert.ok(note.includes('自动上传并恢复调度'));
  assert.ok(note.includes('关闭'));
  assert.ok(note.includes('上传 sub2api'));
});
