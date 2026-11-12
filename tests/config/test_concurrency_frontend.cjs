const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/config/page.js'), 'utf8');
const field = (key, value = 3) => ({key, value, type: 'int', label: key, group: '并发控制', help: '填写正整数', range: {min: 1}});

function harness() {
  const timers = new Map();
  const textNodes = new Map();
  const calls = [];
  let timer = 0;
  const root = {addEventListener() {}, classList: {contains: () => false}};
  const panel = {
    querySelector(selector) {
      if (!textNodes.has(selector)) textNodes.set(selector, {textContent: '', hidden: false});
      return textNodes.get(selector);
    },
    querySelectorAll() { return []; },
  };
  textNodes.set('[data-concurrency-migration]', {hidden: true, querySelector: () => ({disabled: false})});
  const errorSummary = {focused: false, focus() { this.focused = true; }};
  const context = {
    CONFIG: [field('GLOBAL_TASK_WORKERS'), field('ACCOUNT_PLAN_CHECK_WORKERS'), field('CONCURRENCY_POLICY_REVISION', 1)],
    document: {
      hidden: false, activeElement: null, documentElement: {dataset: {}}, addEventListener() {},
      getElementById(id) { return id === 'tab-config' ? root : id === 'configConcurrencyErrorsV2' ? errorSummary : null; },
      querySelector(selector) { return selector.includes('[data-config-section="并发控制"]') ? panel : null; },
      querySelectorAll() { return []; },
    },
    window: {addEventListener() {}, scrollTo() {}, confirm() { return true; }},
    localStorage: {getItem() { return null; }, setItem() {}},
    MutationObserver: class {observe() {}},
    $(selector) { return selector === '#tab-config' ? root : null; },
    esc: value => String(value ?? ''), attrEsc: value => String(value ?? ''),
    isPlaceholderEmpty: value => value === '' || value == null,
    activateTab() {}, showToast() {}, invalidateApiCache() {},
    loadCapabilities: async () => {}, loadRegistrationEmailSources: async () => {},
    setTimeout(callback) { timers.set(++timer, callback); return timer; },
    clearTimeout(id) { timers.delete(id); },
    api: async (url, options) => {
      calls.push({url, options});
      return url.includes('preview') ? {ok: true, migration_required: false, proposed_values: {}} : {
        ok: true, scope: '测试部署', policy_revision: 'fixture', observed_at: '2026-11-05T01:00:00Z',
        global: {limit: 4, occupied: 10, reserved: 1, executing: 7, cleaning: 1, debug_hold: 1, draining: true},
        types: [],
      };
    },
  };
  vm.createContext(context);
  vm.runInContext(`${source}
    renderConfigLayoutV2 = () => {};
    loadConfig = async () => {};
    globalThis.view = {
      state: CONFIG_CONCURRENCY_V2, pending: CONFIG_PENDING_UPDATES, errors: CONFIG_FIELD_ERRORS_V2,
      render: renderConcurrencyConfigSectionV2, query: queryConcurrencyStatusV2, sync: syncConcurrencyStatusV2,
      update: updateConcurrencyStatusV2, usePreview: useConcurrencyPreviewV2,
      save: saveConfigUpdates, waitText: concurrencyWaitTextV2,
      track: trackConfigFieldChange,
      error: concurrencyFieldErrorV2, read: readConfigElementValue,
    };
  `, context);
  return {context, view: context.view, calls, timers, panel, root, textNodes, errorSummary};
}

test('并发输入使用明确标签、正整数下限与可定位错误，策略标记不作为输入展示', () => {
  const {view} = harness();
  const markup = view.render([field('GLOBAL_TASK_WORKERS'), field('ACCOUNT_PLAN_CHECK_WORKERS'), field('CONCURRENCY_POLICY_REVISION', 1)]);
  assert.match(markup, /label for="concurrency-GLOBAL_TASK_WORKERS"/);
  assert.match(markup, /min="1" step="1"/);
  assert.doesNotMatch(markup, /\bmax="/);
  assert.doesNotMatch(markup, /data-key="CONCURRENCY_POLICY_REVISION"/);
  assert.match(markup, /复用父任务许可/);
  assert.match(markup, /XXSYUN 未结束订单名额/);
  assert.match(markup, /aria-describedby="concurrency-GLOBAL_TASK_WORKERS-help concurrency-GLOBAL_TASK_WORKERS-error"/);
});

test('状态轮询保持草稿、DOM输入与焦点，并清楚显示缩容中的占用分项', async () => {
  const {view, context, textNodes} = harness();
  const input = {value: '9'};
  context.document.activeElement = input;
  view.pending.GLOBAL_TASK_WORKERS = '9';
  view.state.visible = true;
  await view.query();
  assert.equal(view.pending.GLOBAL_TASK_WORKERS, '9');
  assert.equal(input.value, '9');
  assert.equal(context.document.activeElement, input);
  assert.match(textNodes.get('[data-concurrency-summary]').textContent, /10 \/ 4，等待现有任务结束/);
  assert.match(textNodes.get('[data-concurrency-summary]').textContent, /预约 1 · 执行 7 · 清理 1 · 调试保留 1/);
});

test('部署范围明确标注，观察时间复用项目浏览器时区格式', async () => {
  const {view, context, textNodes} = harness();
  context.formatDateTime = value => value === '2026-11-05T01:00:00Z' ? '2026-11-05 09:00' : value;
  view.state.visible = true;
  await view.query();
  assert.match(textNodes.get('[data-concurrency-scope]').textContent, /^部署范围 测试部署/);
  assert.match(textNodes.get('[data-concurrency-scope]').textContent, /观察时间 2026-11-05 09:00/);
});

test('页面和浏览器标签隐藏时停止轮询，重新显示后立即刷新', async () => {
  const {view, context, timers, calls, root} = harness();
  view.state.visible = true;
  await view.query();
  assert.equal(timers.size, 1);
  context.document.hidden = true;
  view.sync();
  assert.equal(timers.size, 0);
  const before = calls.length;
  await view.query();
  assert.equal(calls.length, before);
  context.document.hidden = false;
  view.sync();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, before + 1);
  root.classList.contains = () => true;
  view.sync();
  assert.equal(timers.size, 0);
});

test('隐藏前发出的旧响应不会更新新页面状态', async () => {
  const {view, context} = harness();
  let resolveStatus;
  context.api = url => url.includes('preview') ? Promise.resolve({ok: true}) : new Promise(resolve => { resolveStatus = resolve; });
  view.state.visible = true;
  const inflight = view.query();
  context.document.hidden = true;
  view.sync();
  resolveStatus({ok: true, global: {occupied: 999}});
  await inflight;
  assert.equal(view.state.snapshot, null);
});

test('迁移建议只填入草稿并保留用户已经编辑的全局值', () => {
  const {view, calls} = harness();
  view.pending.GLOBAL_TASK_WORKERS = '12';
  view.state.preview = {proposed_values: {GLOBAL_TASK_WORKERS: 3, ACCOUNT_PLAN_CHECK_WORKERS: 8, CONCURRENCY_POLICY_REVISION: 1}};
  view.usePreview();
  assert.equal(view.pending.GLOBAL_TASK_WORKERS, '12');
  assert.equal(view.pending.ACCOUNT_PLAN_CHECK_WORKERS, 8);
  assert.equal(view.pending.CONCURRENCY_POLICY_REVISION, 1);
  assert.equal(calls.length, 0);
});

test('迁移草稿中的默认值即使重新输入相同数值也完整保留，首次保存不会缺键', () => {
  const {view} = harness();
  view.state.preview = {migration_required: true, proposed_values: {GLOBAL_TASK_WORKERS: 3, ACCOUNT_PLAN_CHECK_WORKERS: 3, CONCURRENCY_POLICY_REVISION: 1}};
  view.usePreview();
  const input = {dataset: {key: 'GLOBAL_TASK_WORKERS'},value: '3',setAttribute() {},
    closest(selector) { return selector === '[data-key], [data-wait-seconds-key], [data-price-key]' ? this : selector === '#tab-config' ? {} : null; }};
  view.track({target:input});
  assert.equal(view.pending.GLOBAL_TASK_WORKERS, '3');
  assert.equal(view.pending.ACCOUNT_PLAN_CHECK_WORKERS, 3);
  assert.equal(view.pending.CONCURRENCY_POLICY_REVISION, 1);
});

test('无效数字不会被parseInt截断，保存失败保留草稿并聚焦错误摘要', async () => {
  const {view, calls, errorSummary} = harness();
  const f = field('GLOBAL_TASK_WORKERS');
  for (const value of ['', '0', '-1', '1.5', '1e3']) assert.notEqual(view.error(value), '');
  for (const value of ['1', '51', '1000000']) assert.equal(view.error(value), '');
  assert.equal(view.read({value: '1.5'}, f), '1.5');
  view.pending.GLOBAL_TASK_WORKERS = '1.5';
  await view.save();
  assert.equal(calls.length, 0);
  assert.equal(view.pending.GLOBAL_TASK_WORKERS, '1.5');
  assert.ok(view.errors.GLOBAL_TASK_WORKERS);
  assert.ok(errorSummary.focused);
});

test('等待原因包含服务端容量证据，证据缺失时明确待核验', () => {
  const {view} = harness();
  assert.equal(view.waitText({code: 'global_capacity', occupied: 10, limit: 10}), '等待全局空位（10/10）');
  assert.equal(view.waitText('account_busy'), '账号正由其他任务使用');
  assert.equal(view.waitText('not_due'), '等待下次平台查询');
  assert.equal(view.waitText('fairness_turn'), '等待公平调度轮次');
  assert.equal(view.waitText('executor_capacity'), '等待执行承载空位');
  assert.equal(view.waitText('resource_capacity'), '等待业务资源空位');
  assert.match(view.waitText('future_reason'), /调度等待原因未登记（future_reason）/);
});
