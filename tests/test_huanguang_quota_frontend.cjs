const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/config.js'), 'utf8');
const keys = {
  extraction: 'EXTRACT_LINK_HUANGUANG_CDK',
  payment: 'EXTRACT_LINK_HUANGUANG_PAYMENT_CDK',
  xxsyun: 'EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY',
  base: 'EXTRACT_LINK_HUANGUANG_API_BASE',
};

function createView() {
  const controls = {};
  const listeners = {};
  const fields = Object.entries(keys).map(([kind, key]) => ({
    key, group: '提链', label: kind === 'extraction' ? '幻光提链 CDK' : kind === 'payment' ? '幻光支付扫码 CDK' : key,
    type: 'str', secret: kind !== 'base', configured: true,
    value: kind === 'base' ? 'https://quota.example.test' : '',
  }));
  const root = {addEventListener(name, callback) { listeners[name] = callback; }};
  const context = {
    CONFIG: fields,
    document: {
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll(selector) {
        if (selector.includes('data-query-huanguang-xxsyun-quota')) return [controls.xxsyun.button];
        if (selector.includes('data-huanguang-xxsyun-quota-status')) return [controls.xxsyun.status];
        const kind = selector.match(/(?:cdk-quota|cdk-quota-status)="(extraction|payment)"/)?.[1];
        if (kind) return [selector.includes('status') ? controls[kind].status : controls[kind].button];
        return [];
      },
      documentElement: {dataset: {}}, addEventListener() {},
    },
    window: {addEventListener() {}, confirm() { return true; }, scrollTo() {}},
    localStorage: {getItem() { return null; }, setItem() {}},
    $(selector) { return selector === '#tab-config' ? root : null; },
    esc: value => String(value ?? ''), attrEsc: value => String(value ?? ''),
    isPlaceholderEmpty: value => value === null || value === undefined || value === '',
    showToast() {}, invalidateApiCache() {},
    loadCapabilities: async () => {}, loadRegistrationEmailSources: async () => {},
    Event: class { constructor(type) { this.type = type; } },
  };
  for (const kind of ['extraction', 'payment', 'xxsyun', 'base']) {
    const input = {
      value: kind === 'base' ? 'https://quota.example.test' : '', type: kind === 'base' ? 'text' : 'password', dataset: {key: keys[kind]},
      closest(selector) {
        if (selector.includes('[data-key]')) return this;
        if (selector === '#tab-config') return root;
        return null;
      },
      dispatchEvent() { listeners.input({target: this}); },
    };
    const control = {input, status: {textContent: ''}, querySelector() { return input; }};
    control.button = {dataset: {queryHuanguangCdkQuota: kind}, disabled: false, textContent: '查询剩余次数', closest() { return control; }};
    control.clear = {closest() { return control; }};
    controls[kind] = control;
  }
  vm.createContext(context);
  vm.runInContext(`${source}
    loadConfig = async () => {};
    globalThis.view = {
      render: key => renderConfigControlMarkupV2(CONFIG.find(field => field.key === key)),
      track: trackConfigFieldChange, save: saveConfigUpdates,
      pending: CONFIG_PENDING_UPDATES, forcePending: (key, value) => setPendingConfigValue(key, value, {force: true}),
      reset: resetPendingConfigUpdates,
    };
  `, context);
  function click(kind) {
    const selector = kind === 'xxsyun' ? '[data-query-huanguang-xxsyun-quota]' : '[data-query-huanguang-cdk-quota]';
    return listeners.click({target: {closest(value) { return value === selector ? controls[kind].button : null; }}, preventDefault() {}});
  }
  function edit(kind, value) { controls[kind].input.value = value; context.view.track({target: controls[kind].input}); }
  function clear(kind) {
    return listeners.click({target: {closest(value) { return value === '[data-clear-secret]' ? controls[kind].clear : null; }}, preventDefault() {}});
  }
  return {view: context.view, context, controls, click, edit, clear};
}

test('两类 CDK 各自渲染可访问的查询按钮与结果区', () => {
  const {view} = createView();
  for (const kind of ['extraction', 'payment']) {
    const markup = view.render(keys[kind]);
    assert.match(markup, new RegExp(`data-query-huanguang-cdk-quota="${kind}"`));
    assert.match(markup, /<button type="button" class="btn"/);
    assert.match(markup, new RegExp(`aria-label="查询幻光${kind === 'extraction' ? '提链' : '支付扫码'} CDK 剩余次数"`));
    assert.match(markup, /role="status" aria-live="polite"/);
  }
});

test('保存 CDK 后的新查询不会复用保存前尚未结束的 GET 响应', async () => {
  const {context, controls, click, edit, view} = createView();
  const commonSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');
  context.API_INFLIGHT = new Map();
  vm.runInContext(commonSource.slice(commonSource.indexOf('async function api('), commonSource.indexOf('async function apiCached(')), context);
  let finishOld;
  let queries = 0;
  const response = value => ({ok: true, json: async () => value});
  context.fetch = async (url) => {
    if (url === '/api/config') return response({reloaded: true, restart_required: []});
    queries += 1;
    if (queries === 1) return new Promise(resolve => { finishOld = () => resolve(response({ok: true, quota: {required: true, remaining: 99, reserved: 0, active: true}})); });
    return response({ok: true, quota: {required: true, remaining: 2, reserved: 0, active: true}});
  };
  const oldQuery = click('extraction');
  edit('extraction', 'changed-cdk-test');
  await view.save();
  controls.extraction.input.value = '';
  const newQuery = click('extraction');
  assert.equal(controls.extraction.button.disabled, true);
  finishOld();
  await oldQuery;
  await newQuery;
  assert.equal(queries, 2);
  assert.match(controls.extraction.status.textContent, /剩余 2 次/);
  assert.doesNotMatch(controls.extraction.status.textContent, /99/);
  assert.equal(controls.extraction.button.disabled, false);
});

test('CDK 查询只 GET 已保存的对应项目，保留零与未知次数且不保存配置', async () => {
  const {context, controls, click, view} = createView();
  const calls = [];
  context.api = async (url, options) => {
    calls.push({url, options});
    return {ok: true, quota: {required: true, remaining: 0, reserved: null, active: true}};
  };
  await click('extraction');
  await click('payment');
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
    {url: '/api/extract-link/huanguang/cdk-quota/extraction', options: {method: 'GET'}},
    {url: '/api/extract-link/huanguang/cdk-quota/payment', options: {method: 'GET'}},
  ]);
  for (const kind of ['extraction', 'payment']) {
    assert.match(controls[kind].status.textContent, /剩余 0 次/);
    assert.match(controls[kind].status.textContent, /占用 未知/);
    assert.match(controls[kind].status.textContent, /已启用/);
    assert.equal(controls[kind].button.disabled, false);
  }
  assert.equal(JSON.stringify(view.pending), '{}');
});

test('CDK 免计次、停用与未知状态分别呈现，不把未知次数变成零', async () => {
  for (const scenario of [
    {quota: {required: false, remaining: null, reserved: null, active: true}, want: /^平台免计次$/},
    {quota: {required: true, remaining: 7, reserved: 0, active: false}, want: /已停用/},
    {quota: {required: true, remaining: null, reserved: 0, active: null}, want: /剩余 未知.*状态未知/},
  ]) {
    const {context, controls, click} = createView();
    context.api = async () => ({ok: true, quota: scenario.quota});
    await click('payment');
    assert.match(controls.payment.status.textContent, scenario.want);
    assert.doesNotMatch(controls.payment.status.textContent, /剩余 0 次/);
  }
});

test('未保存的 CDK 与 API_BASE 阻止查询草稿，另一类 CDK 可独立查询', async () => {
  const {context, controls, click, edit} = createView();
  const calls = [];
  context.api = async (url) => { calls.push(url); return {ok: true, quota: {required: true, remaining: 3, reserved: 0, active: true}}; };
  edit('extraction', 'draft-cdk-test');
  await click('extraction');
  assert.match(controls.extraction.status.textContent, /先保存/);
  assert.equal(calls.length, 0);
  await click('payment');
  assert.equal(calls.length, 1);
  edit('base', 'https://draft.example.test');
  await click('payment');
  assert.match(controls.payment.status.textContent, /先保存/);
  assert.equal(calls.length, 1);
});

test('CDK 查询期间编辑或清除凭据会失效旧结果且恢复按钮', async () => {
  for (const change of ['edit', 'clear', 'base']) {
    const {context, controls, click, edit, clear} = createView();
    let resolve;
    context.api = () => new Promise(done => { resolve = done; });
    const request = click('extraction');
    assert.equal(controls.extraction.button.disabled, true);
    assert.match(controls.extraction.status.textContent, /正在查询/);
    if (change === 'edit') edit('extraction', 'new-draft-test');
    if (change === 'clear') clear('extraction');
    if (change === 'base') edit('base', 'https://next.example.test');
    assert.equal(controls.extraction.button.disabled, false);
    assert.equal(controls.extraction.status.textContent, '');
    resolve({ok: true, quota: {required: true, remaining: 99, reserved: 0, active: true}});
    await request;
    assert.equal(controls.extraction.status.textContent, '');
    await click('extraction');
    assert.match(controls.extraction.status.textContent, /先保存/);
  }
});

test('清空草稿、撤销与保存也清除次数结果，保存中的旧 XXSYUN 查询不能回写', async () => {
  const {context, controls, click, edit, view} = createView();
  let resolve;
  context.api = async (url) => {
    if (url === '/api/config') return {reloaded: true, restart_required: []};
    if (url.endsWith('xxsyun-quota')) return new Promise(done => { resolve = done; });
    return {ok: true, quota: {required: true, remaining: 8, reserved: 0, active: true}};
  };
  await click('payment');
  edit('payment', 'draft-test');
  edit('payment', '');
  assert.equal(controls.payment.status.textContent, '');
  await click('payment');
  assert.match(controls.payment.status.textContent, /剩余 8 次/);
  edit('payment', 'next-test');
  view.reset();
  assert.equal(controls.payment.status.textContent, '');
  edit('xxsyun', 'draft-key-test');
  const request = click('xxsyun');
  assert.equal(controls.xxsyun.button.disabled, true);
  await view.save();
  resolve({ok: true, remainingUses: 99, totalUses: 99, reservedUses: 0});
  await request;
  assert.equal(controls.xxsyun.status.textContent, '');
  assert.equal(controls.xxsyun.button.disabled, false);
});

test('API_BASE 编辑作废旧 XXSYUN 请求，保存后仍可查询 Key 草稿', async () => {
  const {context, controls, click, edit, view} = createView();
  const calls = [];
  let finishOld;
  context.api = async (url, options) => {
    calls.push({url, options});
    if (url === '/api/config') return {reloaded: true, restart_required: []};
    if (calls.length === 1) return new Promise(resolve => { finishOld = resolve; });
    return {ok: true, remainingUses: 2, totalUses: null, reservedUses: 0};
  };
  const oldQuery = click('xxsyun');
  assert.equal(controls.xxsyun.button.disabled, true);
  edit('base', 'https://changed.example.test');
  assert.equal(controls.xxsyun.button.disabled, false);
  assert.equal(controls.xxsyun.status.textContent, '');
  await click('xxsyun');
  assert.match(controls.xxsyun.status.textContent, /先保存.*服务地址/);
  assert.equal(calls.length, 1);
  finishOld({ok: true, remainingUses: 99, totalUses: 99, reservedUses: 0});
  await oldQuery;
  assert.match(controls.xxsyun.status.textContent, /先保存.*服务地址/);
  await view.save();
  assert.equal(controls.xxsyun.status.textContent, '');
  edit('xxsyun', 'draft-key-test');
  await click('xxsyun');
  assert.equal(calls.length, 3);
  assert.equal(calls[2].url, '/api/extract-link/huanguang/xxsyun-quota');
  assert.deepEqual(JSON.parse(calls[2].options.body), {api_key: 'draft-key-test'});
  assert.match(controls.xxsyun.status.textContent, /剩余 2 次/);
  assert.equal(controls.xxsyun.button.disabled, false);
});

test('单项查询加载与失败独立，按稳定错误码显示安全原因并能再次查询', async () => {
  const {context, controls, click} = createView();
  const resolve = {};
  context.api = (url) => new Promise((done, fail) => { resolve[url.split('/').pop()] = {done, fail}; });
  const extraction = click('extraction');
  const payment = click('payment');
  assert.equal(controls.extraction.button.disabled, true);
  assert.equal(controls.payment.button.disabled, true);
  resolve.extraction.fail(Object.assign(new Error('raw-private-response'), {code: 'network_error'}));
  await extraction;
  assert.match(controls.extraction.status.textContent, /网络/);
  assert.doesNotMatch(controls.extraction.status.textContent, /raw-private/);
  assert.equal(controls.extraction.button.disabled, false);
  assert.equal(controls.payment.button.disabled, true);
  resolve.payment.done({ok: true, quota: {required: true, remaining: 4, reserved: 0, active: true}});
  await payment;
  context.api = async () => ({ok: true, quota: {required: true, remaining: 2, reserved: 0, active: true}});
  await click('extraction');
  assert.match(controls.extraction.status.textContent, /剩余 2 次/);
});

test('XXSYUN 与 CDK 均按错误码分类，拒绝显示任意异常原文', async () => {
  for (const scenario of [
    {kind: 'xxsyun', code: 'key_invalid', want: /XXSYUN API Key 无效或已失效/},
    {kind: 'xxsyun', code: 'key_missing', want: /未配置.*XXSYUN API Key/},
    {kind: 'payment', code: 'cdk_invalid', want: /支付扫码 CDK.*无效/},
    {kind: 'extraction', code: 'cdk_missing', want: /未配置.*提链 CDK/},
    {kind: 'xxsyun', code: 'config_invalid', want: /配置/},
    {kind: 'payment', code: 'upstream_http_error', want: /上游/},
    {kind: 'xxsyun', code: 'invalid_response', want: /响应.*无效|响应.*异常/},
    {kind: 'payment', code: 'unrecognized-private-code', want: /查询失败.*稍后重试/},
  ]) {
    const {context, controls, click} = createView();
    context.api = async () => { throw Object.assign(new Error('raw-private-key-and-response'), {code: scenario.code}); };
    await click(scenario.kind);
    assert.match(controls[scenario.kind].status.textContent, scenario.want);
    assert.doesNotMatch(controls[scenario.kind].status.textContent, /raw-private|unrecognized-private/);
    assert.equal(controls[scenario.kind].button.disabled, false);
  }
});

test('CDK 非法数字和缺失结构归为响应异常，不伪造余额', async () => {
  for (const quota of [null, {},
    {required: true, remaining: -1, reserved: null, active: true},
    {required: true, remaining: 1.5, reserved: null, active: true},
    {required: true, remaining: Number.MAX_SAFE_INTEGER + 1, reserved: null, active: true},
    {required: true, remaining: null, reserved: '0', active: true},
    {required: true, remaining: 0, reserved: 0, active: 'true'},
  ]) {
    const {context, controls, click} = createView();
    context.api = async () => ({ok: true, quota});
    await click('extraction');
    assert.match(controls.extraction.status.textContent, /响应.*无效|响应.*异常/);
    assert.doesNotMatch(controls.extraction.status.textContent, /剩余 0 次/);
    assert.equal(controls.extraction.button.disabled, false);
  }
});
