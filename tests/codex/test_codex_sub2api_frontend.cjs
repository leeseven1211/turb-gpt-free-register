const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {vueHarness} = require('../accounts/actions_fixture.cjs');
const {createAccountActions} = vueHarness.load('src/features/accounts/actions.ts');

const root = path.join(__dirname, '../..');
const read = filename => fs.readFileSync(path.join(root, filename), 'utf8');
// 确认文案、取消请求和上传回执的行为测试已迁至 features/codex/actions.test.ts。
// 此处保留旧壳层责任：唯一挂载点、延迟入口、功能门禁与跨页刷新接缝。
test('Codex 模块仅有一个挂载点，真实账号动作下载后经原入口延迟刷新', async () => {
  const template = read('webui/templates/index.html');
  const bridge = read('webui/static/js/pages/codex/page.js');
  assert.equal((template.match(/id="codex-credentials-root"/g) || []).length, 1);
  assert.match(template, /filename='task-center\/codex.js', v=asset_version/);
  assert.match(bridge, /import\(root.dataset.moduleUrl\)/);
  assert.match(bridge, /function loadCodex\(\)[\s\S]*window.CodexCredentials.refresh\(\)/);
  assert.doesNotMatch(bridge, /CODEX_SELECTED|CODEX_SHOW_ARCHIVED|PAGERS\.codex/);
  const calls = [], downloads = [], timers = [], toasts = [];
  let refreshes = 0;
  const context = {window: {CodexCredentials: {refresh: async () => {refreshes++;}}}};
  vm.runInNewContext(bridge.slice(bridge.indexOf('function loadCodex()')), context);
  const actions = createAccountActions({
    request: async (url, options) => {
      calls.push({url, options});
      return {ok: true, prepared: true, download_url: '/api/downloads/cpa-id', filename: 'cpa.zip', added_count: 1, error_count: 0};
    },
    notify: value => toasts.push(value), confirm: () => true, clipboard: async () => true,
    downloadBlob: () => assert.fail('CPA 下载应使用服务端准备的地址'),
    downloadUrl: (url, filename) => downloads.push({url, filename}), now: () => new Date(),
    schedule: (callback, delay) => timers.push({callback, delay}), reloadCodex: () => context.loadCodex(),
  });
  const snapshot = {accountIds: ['23'], expectedEmails: {}, querySnapshot: {}, archived: '0', rowHints: []};
  await actions.invoke('downloadSelectedCpa', snapshot);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/accounts/download-cpa-bulk');
  assert.equal(calls[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[0].options.body), {account_ids: [23], prepare: true});
  assert.deepEqual(downloads, [{url: '/api/downloads/cpa-id', filename: 'cpa.zip'}]);
  assert.deepEqual(toasts, ['已生成 ZIP，开始下载']);
  assert.equal(refreshes, 0);
  assert.ok(timers.length);
  assert.ok(timers.every(timer => timer.delay === 1200));
  await Promise.all(timers.map(async timer => timer.callback()));
  assert.equal(refreshes, 1);
  assert.equal(actions.isPending('downloadSelectedCpa', snapshot), false);
});

test('Sub2API 与重新授权门禁仍在全局捕获边界，导航显式通知新页', () => {
  const common = read('webui/static/js/shared/common.js');
  assert.match(common, /sub2_upload:.*#btnCodexUploadSub2V2,\[data-codex-upload-sub2\]/);
  assert.match(common, /codex_retry:.*#btnCodexReauthorizeBulkV2.*\[data-codex-reauthorize\]/);
  assert.match(common, /cpa_download:.*#btnCodexDownloadBulkCpaV2.*\[data-codex-download-cpa\]/);
  assert.match(common, /window.CodexCredentials\?\.setVisible\(tab === 'codex'\)/);
  assert.doesNotMatch(common, /CODEX_SHOW_ARCHIVED|CODEX_TOTAL|codexLoading/);
});

// 主线后补的历史上传事实由 Vue 展示 owner 验证，不能只保留旧壳层断言。
const {credentialStatus} = vueHarness.load('src/features/codex/presentation.ts');
const {taskResultSummary} = vueHarness.load('src/features/tasks/resultSummary.ts');
test('自动上传凭证计入已导出，后续启用失败仍保留上传事实', () => {
  for (const receipt of [
    {sub2api_account_id: null, sub2_sync_error: null},
    {sub2api_account_id: 150, sub2_sync_error: 'sub2api_http_error: 调度启用失败'},
  ]) {
    const badge = credentialStatus({filename: 'fixture.json', exported: false, exported_count: 0, sub2_uploaded_count: 2,
      sub2_uploaded_at: '2026-11-13T14:40:00', ...receipt});
    assert.equal(badge.label, '已导出');
    assert.equal(badge.title, 'Sub2API 已上传 2 次，最近 2026-11-13T14:40:00');
    assert.doesNotMatch(badge.title, /已启用|导出 0 次|本地下载/);
  }
});
test('上传与导出记录分别说明次数，零次上传和仅关联不推定远端上传', () => {
  const uploaded = credentialStatus({filename: 'fixture.json', exported_count: 1, exported_at: '2026-11-12T12:00:00',
    sub2_uploaded_count: 3, sub2_uploaded_at: '2026-11-13T14:40:00'});
  assert.equal(uploaded.title, 'Sub2API 已上传 3 次，最近 2026-11-13T14:40:00；导出记录 1 次，最近 2026-11-12T12:00:00');
  const linked = credentialStatus({filename: 'fixture.json', exported: true, exported_count: 0, sub2api_account_id: 150});
  assert.equal(linked.label, '已关联');
  assert.match(linked.title, /本地下载 0 次/);
  for (const sub2_uploaded_count of [undefined, 0, '0']) {
    const pending = credentialStatus({filename: 'fixture.json', exported: false, exported_count: 0, sub2_uploaded_count});
    assert.equal(pending.label, '未导出');
    assert.doesNotMatch(pending.title, /已上传/);
  }
});
test('Codex 授权结果保留自动同步成功、失败、停止及未启用的独立事实', () => {
  const summary = (extra = {}) => taskResultSummary({id: 1, task_type: 'codex_retry', status: 'success',
    result_summary: {ok: true, credential_confirmed: true, ...extra}});
  for (const [status, expected, tone] of [['success', '同步已完成', 'success'], ['failed', '同步失败', 'warning'], ['cancelled', '同步已停止', 'warning']]) {
    assert.deepEqual(summary({sub2api_sync: {status}}), {label: '授权成功', secondary: expected, tone});
  }
  assert.deepEqual(summary(), {label: '授权成功', secondary: '凭证已确认', tone: 'success'});
  assert.equal(summary({credential_confirmed: false}).secondary, undefined);
});
