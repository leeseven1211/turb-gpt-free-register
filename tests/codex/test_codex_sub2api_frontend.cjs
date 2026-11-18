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
  assert.match(template, /filename='task-center\/codex.js', v=task_center_version/);
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
