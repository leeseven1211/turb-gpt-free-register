// Mount the real Vue owner: all API calls are mocks, no account requests are sent.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {createVueHarness} = require('../frontend_vue_loader.cjs');
process.env.TZ = 'Asia/Shanghai';
const h = createVueHarness();
const native = h.document.defaultView;
for (const key of ['Document', 'ShadowRoot']) globalThis[key] = native[key];
native.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
native.HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new native.Event('close')); };
const common = fs.readFileSync('webui/static/js/shared/common.js', 'utf8');
const formatting = vm.createContext({});
vm.runInContext(common.slice(common.indexOf('function formatDateTime('), common.indexOf('function browserTimeZoneName(')), formatting);
const requests = [];
const taskNavigations = [];
let reply = {ok: true, created: true, task: {id: 1}}, nextError, workers = 4;
const notices = [];
const component = h.load('src/features/accounts/Inspection.vue').default;
const page = h.mount(component, {props: {deps: {
  request: async (url, options) => {requests.push({url, options}); if (nextError) {const error = nextError; nextError = null; throw error;} return typeof reply === 'function' ? reply(url) : reply;},
  notify: text => notices.push(text), operationWorkers: () => workers,
  randomUUID: () => 'fixture-request-key', refreshAccounts() {}, refreshSummary() {}, openTask() {},
  openTasks: options => taskNavigations.push(options),
  formatDateTime: value => formatting.formatDateTime(value),
}}});
const scope = archived => Object.freeze({archived, accountIds: Object.freeze(['1']), expectedEmails: Object.freeze({'1': 'one@test'}), rowHints: Object.freeze([]), querySnapshot: Object.freeze({})});
const element = id => h.document.getElementById(id);
const flush = async () => {await new Promise(resolve => setImmediate(resolve)); await h.nextTick();};
const submit = async () => {await page.get('form').trigger('submit'); await flush();};
(async () => {
  try {
    page.vm.openStart(scope('0')); await flush();
    assert.equal(element('accountInspectionStart').dataset.archived, '0');
    assert.equal(Number(element('accountInspectionWorkers').value), 4);
    workers = 20; page.vm.openStart(scope('0')); await flush();
    assert.equal(Number(element('accountInspectionWorkers').value), 16);
    page.vm.openStart(scope('only')); await flush();
    assert.equal(element('accountInspectionStart').dataset.archived, 'only');
    await page.get('#accountInspectionWorkers').setValue('2');
    nextError = new Error('模拟请求超时'); await submit();
    assert.match(element('accountInspectionStartError').textContent, /巡检启动请求失败/);
    assert.equal(element('btnConfirmAccountInspection').disabled, false);
    const firstKey = JSON.parse(requests[0].options.body).idempotency_key;
    for (const status of [400, 403, 409]) {
      nextError = Object.assign(new Error(`请求被拒绝（HTTP ${status}）`), {status}); await submit();
      const error = element('accountInspectionStartError').textContent;
      assert.match(error, /巡检启动请求失败：请求被拒绝/);
      assert.doesNotMatch(error, /未收到响应|响应缺失/);
      assert.equal(JSON.parse(requests.at(-1).options.body).idempotency_key, firstKey);
    }
    reply = url => url.includes('?page=') ? {items: [], total: 0, active: null} : {created: true, task: {id: 1}};
    await submit();
    const accepted = requests.filter(request => request.options.method === 'POST').at(-1);
    assert.equal(JSON.parse(accepted.options.body).idempotency_key, firstKey);
    assert.equal(JSON.parse(accepted.options.body).archived, 'only');
    assert.deepEqual(taskNavigations, [{filters: {type: 'account_inspection_batch', target: ''}}]);
    assert.equal(element('accountInspectionHistory').open, false);
    reply = {items: [{id: 9, task_id: 9, workers: 2, archived: '0', status: 'completed', created_at: '<script>', checked_count: 0, skipped_count: 1, total_count: 1, invalid_count: 0, live_failed_count: 0, deactivated_skipped_count: 1, live_success_count: 0, plan_success_count: 0, plan_failed_count: 0}], active: null, total: 1};
    page.vm.openHistory(); await flush();
    assert.match(element('accountInspectionHistoryContent').textContent, /失败详情 1/);
    assert.doesNotMatch(element('accountInspectionHistoryContent').innerHTML, /<script>/);
    reply.items[0].created_at = '2026-10-19T01:04:17+00:00';
    await page.vm.refreshHistory(); await flush();
    assert.match(element('accountInspectionHistoryContent').textContent, /2026-10-19 09:04:17/);
    reply = {items: [{account_id: 4, email: '<img src=x>', status: 'deactivated_skipped', failed_at: 'now', error: '<script>fixture</script>'}], total: 1};
    page.vm.openFailures(9); await flush();
    const markup = element('accountInspectionFailuresContent').innerHTML;
    assert.match(markup, /已废跳过/); assert.doesNotMatch(markup, /<img|<script>/);
    assert.match(page.text(), /不限当前页，不受勾选、搜索或其他筛选条件影响/);
    assert.equal(element('accountInspectionHistory').getAttribute('aria-labelledby'), 'accountInspectionHistoryTitle');
    const taskPresentation = fs.readFileSync('frontend/src/features/tasks/presentation.ts', 'utf8');
    assert.match(taskPresentation, /account_inspection_batch: '巡检批次'/);
    // Keep unknown-provider/disabled capability coverage against the new real owner.
    const {createRequire} = require('node:module');
    const frontendRequire = createRequire(require('node:path').resolve('frontend/package.json'));
    const {effectScope} = frontendRequire('vue');
    const {useAccountEmailChange} = h.load('src/features/accounts/useAccountEmailChange.ts');
    const emailScope = effectScope();
    const emailOwner = emailScope.run(() => useAccountEmailChange({
      request: async () => ({sources: [{value: 'mailcode', label: 'MailCode', enabled: true}, {value: 'xigua', label: '西瓜', enabled: false, reason: '尚未配置'}]}),
      notify() {}, refreshAccounts() {}, openTasks() {}, syncModalScrollLock() {},
    }));
    try {
      emailOwner.openBulk(scope('0')); await flush();
      assert.equal(emailOwner.source.value, 'mailcode');
      assert.equal(emailOwner.sources.value[0].label, 'MailCode');
      assert.equal(emailOwner.sources.value[1].label, '西瓜');
      assert.equal(emailOwner.sources.value[1].enabled, false);
      const emailComponent = h.load('src/features/accounts/EmailChange.vue').default;
      const host = h.document.createElement('div'); host.id = 'accountEmailChangeHost'; h.document.body.append(host);
      const emailPage = h.mount(emailComponent, {props: {deps: {
        request: async () => ({sources: [{value: 'mailcode', label: 'MailCode', enabled: true}, {value: 'xigua', label: '西瓜', enabled: false, reason: '尚未配置'}]}),
        notify() {}, refreshAccounts() {}, openTasks() {}, syncModalScrollLock() {},
      }}});
      emailPage.vm.openBulk(scope('0')); await flush();
      const disabled = h.document.querySelector('#emailChangeSource option[value="xigua"]');
      assert.equal(disabled.textContent, '西瓜（不可用）'); assert.equal(disabled.disabled, true);
      emailPage.unmount();
    } finally {emailScope.stop();}
    page.vm.close('failures'); await flush();
    const stale = h.document.createElement('button'); h.document.body.append(stale);
    page.vm.openFailures(9, stale); await flush(); stale.remove(); page.vm.close('failures'); await flush();
    assert.equal(h.document.activeElement, element('accountInspectionHistory').querySelector('button:not([disabled])'));
    console.log('巡检 UI：真实 Vue 范围、并发、超时复用提交键、历史计数、转义和动态来源通过');
  } finally {page.vm.close(); await flush(); h.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
