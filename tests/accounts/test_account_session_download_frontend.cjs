const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {createActionsFixture, legacySelectionSnapshot} = require('./actions_fixture.cjs');
const {mountToolbarFixture} = require('./toolbar_fixture.cjs');
const {flushPromises} = require('../../frontend/node_modules/@vue/test-utils');

const source = require('../frontend_script_sources.cjs').readAccountScripts();

async function setup({selected = [7, 8], request} = {}) {
  const calls = {requests: [], toasts: [], downloads: []};
  const selectedIds = new Set(selected);
  let toolbar,inFlight;
  const elements = new Map([['btnCloseLiveLog', {addEventListener() {}}]]);
  const get=id=>toolbar?.get(id)||elements.get(id)||null;
  const context = vm.createContext({
    LIST_FACET_LABELS: {task_type: {}, stage: {}, target_status: {}},
    ACCOUNT_SELECTED: selectedIds,
    // 第二个选中账号位于其他页，下载仍须使用完整的选择集合。
    ACCOUNTS: [{id: 7, email: 'current@example.test'}],
    SHOW_ARCHIVED_ACCOUNTS: false,
    browserTimeZoneName: () => 'Asia/Shanghai',
    closeLiveLogModal() {},
    document: {
      getElementById: get,
      querySelector: () => null, querySelectorAll: () => [], addEventListener() {},
      body: {appendChild() {}},
      createElement: tag => {
        assert.equal(tag, 'a');
        return {click() { calls.downloads.push({href: this.href, download: this.download}); }, remove() {}};
      },
    },
    $: selector => get(selector.slice(1)),
    window: {addEventListener() {}},
    setInterval() {}, setTimeout: callback => { callback(); return 1; }, clearTimeout() {},
    showToast: message => calls.toasts.push(message),
    confirm: () => { throw new Error('下载本地 Session 无需确认弹窗'); },
    api: async (url, options) => {
      calls.requests.push({url, options});
      if (request) return request(url, options);
      return {
        ok: true, prepared: true, download_url: '/api/downloads/session-test',
        filename: 'accounts-session-bulk-test.zip', added_count: 1, skipped_count: 1,
        skipped: [{id: 8, email: 'other@example.test', error_code: 'session_missing', reason: '未保存 Session'}],
      };
    },
  });
  vm.runInContext(source, context);
  const owner = {isReady: () => true, getActionContext: () => legacySelectionSnapshot(context)};
  createActionsFixture(context, owner); context.window.AccountsPage = owner;
  toolbar=mountToolbarFixture({state:{selectedCount:selectedIds.size,archived:false},getContext:()=>owner.getActionContext(),
    invoke:(descriptor,snapshot,trigger)=>{inFlight=owner.invokeAction(descriptor,snapshot,trigger);return inFlight;},notify:context.showToast});
  owner.syncToolbarPending=()=>toolbar.setState({selectedCount:selectedIds.size,archived:false,pending:{downloadSelectedAccountSessions:owner.isActionPending('downloadSelectedAccountSessions')}});
  await toolbar.ready;
  const button=toolbar.get('btnDownloadSelectedSessionsV2');
  const click = () => {button.click();return Promise.resolve(inFlight).then(()=>flushPromises());};
  return {context, button, calls, selectedIds, click};
}

test('跨页选择全部提交并通过服务端地址下载 ZIP，提示成功和跳过清单', async () => {
  const {context, calls, button, click} = await setup();
  await context.updateAccountSelectionUi();
  assert.equal(button.disabled, false);
  await click();
  assert.equal(calls.requests.length, 1);
  assert.equal(calls.requests[0].url, '/api/accounts/download-session-bulk');
  assert.equal(calls.requests[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls.requests[0].options.body), {account_ids: [7, 8], prepare: true});
  assert.deepEqual(calls.downloads, [{href: '/api/downloads/session-test', download: 'accounts-session-bulk-test.zip'}]);
  assert.match(calls.toasts.join(''), /1.*Session/);
  assert.match(calls.toasts.join(''), /跳过\s*1/);
  assert.match(calls.toasts.join(''), /manifest\.json/);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '下载 Session');
});

test('全部账号缺失、无效或读取失败时仍下载结果 ZIP，并说明后续处理', async () => {
  const {button, calls, click} = await setup({
    selected: [7, 8, 9],
    request: async () => ({
      ok: true, prepared: true, download_url: '/api/downloads/session-manifest',
      filename: 'accounts-session-bulk-manifest.zip', added_count: 0, skipped_count: 3,
      skipped: [
        {id: 7, email: 'missing@example.test', error_code: 'session_missing', reason: '未保存 Session，请先刷新 AT'},
        {id: 8, email: 'invalid@example.test', error_code: 'session_invalid', reason: 'Session 缺少有效 accessToken，请先刷新 AT'},
        {id: 9, email: 'unreadable@example.test', error_code: 'session_read_failed', reason: '读取 Session 失败，请重试'},
      ],
    }),
  });
  await click();
  assert.equal(calls.requests.length, 1);
  assert.deepEqual(calls.downloads, [{href: '/api/downloads/session-manifest', download: 'accounts-session-bulk-manifest.zip'}]);
  const message = calls.toasts.join('');
  assert.match(message, /没有可下载的 Session.*已生成结果清单/);
  assert.match(message, /跳过\s*3/);
  assert.match(message, /ZIP.*manifest\.json/);
  assert.match(message, /缺失.*无效.*刷新 AT/);
  assert.match(message, /读取失败.*重试/);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '下载 Session');
});

test('无选择时保持禁用且直接调用也不会请求或下载', async () => {
  const {context, button, calls, click} = await setup({selected: []});
  await context.updateAccountSelectionUi();
  await click();
  await context.downloadSelectedAccountSessions();
  assert.equal(button.disabled, true);
  assert.equal(calls.requests.length, 0);
  assert.equal(calls.downloads.length, 0);
  assert.match(calls.toasts.join(''), /请先选择账号/);
});

test('打包中禁用并拒绝重复请求，选择变化不会提前恢复按钮', async () => {
  let finish;
  const {context, button, calls, selectedIds, click} = await setup({request: () => new Promise(resolve => { finish = resolve; })});
  const pending = click();
  await flushPromises();
  assert.equal(button.disabled, true);
  assert.match(button.textContent, /打包中/);
  selectedIds.clear();
  selectedIds.add(9);
  await context.updateAccountSelectionUi();
  assert.equal(button.disabled, true);
  button.click();
  await flushPromises();
  assert.equal(calls.requests.length, 1);
  finish({ok: true, prepared: true, download_url: '/api/downloads/ready', filename: 'ready.zip', added_count: 2, skipped_count: 0, skipped: []});
  await pending;
  assert.deepEqual(JSON.parse(calls.requests[0].options.body).account_ids, [7, 8]);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '下载 Session');
});

test('打包期间清空选择，完成后仍保持禁用', async () => {
  let finish;
  const {context, button, selectedIds, click} = await setup({request: () => new Promise(resolve => { finish = resolve; })});
  const pending = click();
  await flushPromises();
  assert.match(button.textContent, /打包中/);
  selectedIds.clear();
  await context.updateAccountSelectionUi();
  finish({ok: true, prepared: true, download_url: '/api/downloads/ready', added_count: 2, skipped_count: 0, skipped: []});
  await pending;
  assert.equal(button.disabled, true);
  assert.equal(button.textContent, '下载 Session');
});

test('服务端报错时显示具体原因且恢复按钮，可再次下载', async () => {
  const {button, calls, click} = await setup({request: async () => { throw new Error('Session 打包服务暂时不可用，请重试'); }});
  await click();
  assert.equal(calls.requests.length, 1);
  assert.equal(calls.downloads.length, 0);
  assert.match(calls.toasts.join(''), /下载 Session 失败.*打包服务暂时不可用.*重试/);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '下载 Session');
  await click();
  assert.equal(calls.requests.length, 2);
});

test('缺少下载地址时反馈明确错误并恢复，避免空链接下载', async () => {
  const {button, calls, click} = await setup({request: async () => ({ok: true, prepared: true, added_count: 2, skipped_count: 0, skipped: []})});
  await click();
  assert.equal(calls.downloads.length, 0);
  assert.match(calls.toasts.join(''), /未返回下载地址/);
  assert.equal(button.disabled, false);
});
