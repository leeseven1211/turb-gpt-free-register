// 模拟 UI 状态，只执行 accounts.js 中真实巡检函数，不发账号请求。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = require('../frontend_script_sources.cjs').readAccountScripts();
process.env.TZ = 'Asia/Shanghai';
const nodes = new Map();
let focused;
function element(id) {
  if (!nodes.has(id)) nodes.set(id, {id, dataset: {}, disabled: false, textContent: '', innerHTML: '', value: '3', open: false, isConnected: true,
    addEventListener(name, listener) { this.listeners ??= {}; this.listeners[name] = listener; }, focus() { focused = this; }, showModal() { this.open = true; }, close() { this.open = false; this.listeners?.close?.(); }, querySelector() { return null; }});
  return nodes.get(id);
}
const requests = [];
let reply = {ok: true, created: true, task: {id: 1}};
let nextError;
const context = vm.createContext({
  document: {hidden: false, activeElement: element('trigger'), getElementById: element},
  SHOW_ARCHIVED_ACCOUNTS: false, getAccountOperationWorkers: () => 4,
  api: async (url, options) => { requests.push({url, options}); if (nextError) { const e = nextError; nextError = null; throw e; } return typeof reply === 'function' ? reply(url) : reply; },
  esc: s => String(s ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;'),
  showToast() {}, loadAccounts() {}, loadSummary() {}, openAccountTaskLog() {},
  ACCOUNT_SELECTED: new Set([1]), crypto: {randomUUID: () => 'fixture-request-key'},
  setTimeout: () => 1, clearTimeout() {}, setInterval() {}, AbortController,
  console, Map, Number, JSON, Promise,
});
vm.runInContext(source.slice(source.indexOf('// 巡检使用原生 dialog')), context);
const common = fs.readFileSync('webui/static/js/shared/common.js', 'utf8');
vm.runInContext(common.slice(common.indexOf('function formatDateTime('), common.indexOf('function browserTimeZoneName(')), context);
(async () => {
  vm.runInContext('openAccountInspectionStart()', context);
  assert.equal(element('accountInspectionStart').dataset.archived, '0');
  assert.equal(element('accountInspectionWorkers').value, 4);
  context.getAccountOperationWorkers = () => 20;
  vm.runInContext('openAccountInspectionStart()', context);
  assert.equal(element('accountInspectionWorkers').value, 16);
  context.SHOW_ARCHIVED_ACCOUNTS = true;
  vm.runInContext('openAccountInspectionStart()', context);
  assert.equal(element('accountInspectionStart').dataset.archived, 'only');
  element('accountInspectionWorkers').value = '2';
  nextError = new Error('模拟请求超时');
  await vm.runInContext('submitAccountInspection({preventDefault(){}})', context);
  assert.match(element('accountInspectionStartError').textContent, /启动结果待确认/);
  assert.equal(element('btnConfirmAccountInspection').disabled, false);
  const firstKey = JSON.parse(requests[0].options.body).idempotency_key;
  reply = url => url.includes('?page=') ? {items: [], total: 0, active: null} : {created: true, task: {id: 1}};
  await vm.runInContext('submitAccountInspection({preventDefault(){}})', context);
  assert.equal(JSON.parse(requests[1].options.body).idempotency_key, firstKey);
  assert.equal(JSON.parse(requests[1].options.body).archived, 'only');
  await new Promise(resolve => setImmediate(resolve));
  reply = {items: [{id: 9, task_id: 9, workers: 2, archived: '0', status: 'completed', created_at: '<script>', checked_count: 0, skipped_count: 1, total_count: 1, invalid_count: 0, live_failed_count: 0, deactivated_skipped_count: 1, live_success_count: 0, plan_success_count: 0, plan_failed_count: 0}], active: null, total: 1};
  await vm.runInContext('refreshAccountInspectionHistory()', context);
  assert.match(element('accountInspectionHistoryContent').innerHTML, /失败详情 1/);
  assert.doesNotMatch(element('accountInspectionHistoryContent').innerHTML, /<script>/);
  reply.items[0].created_at = '2026-10-19T01:04:17+00:00';
  await vm.runInContext('refreshAccountInspectionHistory()', context);
  assert.match(element('accountInspectionHistoryContent').innerHTML, /2026-10-19 09:04:17/);
  reply = {items: [{account_id: 4, email: '<img src=x>', status: 'deactivated_skipped', failed_at: 'now', error: '<script>fixture</script>'}], total: 1};
  vm.runInContext('openAccountInspectionFailures(9)', context);
  await new Promise(resolve => setImmediate(resolve));
  const markup = element('accountInspectionFailuresContent').innerHTML;
  assert.match(markup, /已废跳过/);
  assert.doesNotMatch(markup, /<img|<script>/);
  const template = fs.readFileSync('webui/templates/index.html', 'utf8');
  assert.match(template, /不限当前页，不受勾选、搜索或其他筛选条件影响/);
  assert.match(template, /aria-labelledby="accountInspectionHistoryTitle"/);
  assert.match(source, /account_inspection_batch: '巡检批次'/);
  // 换绑来源由后端 capability 提供；未知新来源按返回标签显示，无需硬编码。
  const loader = source.slice(source.indexOf('async function loadEmailChangeSources'), source.indexOf('async function openEmailChangeModal'));
  assert.match(loader, /api\('\/api\/email-sources'\)/);
  assert.match(loader, /item\.label \|\| item\.value/);
  assert.match(loader, /option\.disabled = !item\.enabled/);
  context.$ = selector => element(selector.slice(1));
  context.document.createElement = () => ({dataset: {}});
  const options = [];
  element('emailChangeSource').appendChild = option => options.push(option);
  reply = {sources: [{value: 'mailcode', label: 'MailCode', enabled: true}, {value: 'xigua', label: '西瓜', enabled: false, reason: '尚未配置'}]};
  vm.runInContext(loader, context);
  await vm.runInContext("loadEmailChangeSources('mailcode')", context);
  assert.equal(element('emailChangeSource').value, 'mailcode');
  assert.equal(options[0].textContent, 'MailCode');
  assert.equal(options[1].textContent, '西瓜（不可用）');
  assert.equal(options[1].disabled, true);
  // 父弹窗轮询替换了触发按钮时，返回父弹窗刷新按钮而不是页面 body。
  const staleTrigger = element('stale-failure-trigger');
  context.document.activeElement = staleTrigger;
  element('accountInspectionFailures').open = false;
  vm.runInContext("showAccountInspectionDialog('accountInspectionFailures')", context);
  staleTrigger.isConnected = false;
  element('accountInspectionHistory').open = true;
  element('accountInspectionHistory').querySelector = () => element('history-refresh');
  vm.runInContext("closeAccountInspectionDialog('accountInspectionFailures')", context);
  assert.equal(focused, element('history-refresh'));
  console.log('巡检 UI：范围、并发、超时复用提交键、历史计数、转义和动态来源通过');
})().catch(error => { console.error(error); process.exitCode = 1; });
