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
const statusBadgeFunction = codex.slice(
  codex.indexOf('function _codexStatusBadge('),
  codex.indexOf('\nfunction _codexOauthBadge('),
);
const badgeContext = {
  esc: (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]),
};
vm.runInNewContext(statusBadgeFunction, badgeContext);

test('自动上传凭证计入已导出，后续启用失败仍保留上传事实', () => {
  for (const receipt of [
    {sub2api_account_id: null, sub2_sync_error: null},
    {sub2api_account_id: 150, sub2_sync_error: 'sub2api_http_error: 调度启用失败'},
  ]) {
    const badge = badgeContext._codexStatusBadge({
      exported: false, exported_count: 0, sub2_uploaded_count: 2,
      sub2_uploaded_at: '2026-11-13T14:40:00', ...receipt,
    });
    assert.ok(badge.includes('>已导出</span>'));
    assert.ok(badge.includes('Sub2API 已上传 2 次，最近 2026-11-13T14:40:00'));
    assert.ok(!badge.includes('已关联'));
    assert.ok(!badge.includes('导出 0 次'));
    assert.ok(!badge.includes('已启用'));
  }
});

test('上传与导出记录分别说明次数，不把上传次数当作本地下载次数', () => {
  const badge = badgeContext._codexStatusBadge({
    exported_count: 1, exported_at: '2026-11-12T12:00:00',
    sub2_uploaded_count: 3, sub2_uploaded_at: '2026-11-13T14:40:00',
  });
  assert.ok(badge.includes('Sub2API 已上传 3 次，最近 2026-11-13T14:40:00'));
  assert.ok(badge.includes('导出记录 1 次，最近 2026-11-12T12:00:00'));
  assert.ok(!badge.includes('本地下载'));
});

test('仅历史关联、纯导出与未导出状态保持原语义，零次上传不算导出', () => {
  const linked = badgeContext._codexStatusBadge({exported: true, exported_count: 0, sub2api_account_id: 150});
  assert.ok(linked.includes('>已关联</span>'));
  assert.ok(linked.includes('本地下载 0 次'));
  const downloaded = badgeContext._codexStatusBadge({exported_count: 1, exported_at: '2026-11-12T12:00:00'});
  assert.ok(downloaded.includes('>已导出</span>'));
  assert.ok(downloaded.includes('导出 1 次，最近 2026-11-12T12:00:00'));
  for (const sub2_uploaded_count of [undefined, 0, '0']) {
    const pending = badgeContext._codexStatusBadge({exported: false, exported_count: 0, sub2_uploaded_count});
    assert.ok(pending.includes('>未导出</span>'));
    assert.ok(!pending.includes('已上传'));
  }
});

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
