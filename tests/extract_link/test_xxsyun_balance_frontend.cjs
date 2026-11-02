const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/config/page.js'), 'utf8');
const key = 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY';
const base = 'EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE';

function createView() {
  const listeners = {};
  const root = {addEventListener(name, callback) { listeners[name] = callback; }};
  const status = {textContent: ''};
  const input = {
    value: '', type: 'password', dataset: {key},
    closest(selector) {
      if (selector.includes('[data-key]')) return this;
      return selector === '#tab-config' ? root : null;
    },
    dispatchEvent() { listeners.input({target: this}); },
  };
  const control = {querySelector() { return input; }};
  const button = {disabled: false, textContent: '', closest() { return control; }};
  const fields = [{key, group: '提链', label: 'XXSYUN API Key', type: 'str', secret: true, configured: true, value: ''},
    {key: base, group: '提链', label: 'XXSYUN API 地址', type: 'str', value: 'https://upi.xxsyun.xyz/api/v1'}];
  const context = {
    CONFIG: fields,
    document: {getElementById() { return null; }, querySelector() { return null; }, querySelectorAll(selector) {
      if (selector.includes('data-query-xxsyun-payment-balance')) return [button];
      if (selector.includes('data-xxsyun-payment-balance-status')) return [status];
      return [];
    }, documentElement: {dataset: {}}, addEventListener() {}},
    window: {addEventListener() {}, confirm() { return true; }, scrollTo() {}},
    localStorage: {getItem() { return null; }, setItem() {}},
    $(selector) { return selector === '#tab-config' ? root : null; },
    esc: value => String(value ?? ''), attrEsc: value => String(value ?? ''),
    isPlaceholderEmpty: value => value == null || value === '', showToast() {}, invalidateApiCache() {},
    Event: class {}, loadCapabilities: async () => {}, loadRegistrationEmailSources: async () => {},
  };
  vm.createContext(context);
  vm.runInContext(`${source}\nloadConfig = async () => {};
    globalThis.view = {render: () => renderConfigControlMarkupV2(CONFIG[0]),
      track: trackConfigFieldChange, pending: CONFIG_PENDING_UPDATES,
      reset: resetPendingConfigUpdates, save: saveConfigUpdates};`, context);
  const click = () => listeners.click({target: {closest(selector) {
    return selector === '[data-query-xxsyun-payment-balance]' ? button : null;
  }}, preventDefault() {}});
  const edit = (value, clear = false) => {
    input.value = value;
    input.dataset.secretClear = clear ? 'true' : 'false';
    context.view.track({target: input});
  };
  return {context, view: context.view, input, button, status, click, edit};
}

test('独立支付Key保留密码框和明确清除，提供积分按钮和可访问结果区', () => {
  const {view} = createView();
  const html = view.render();
  assert.match(html, /type="password"/);
  assert.match(html, new RegExp(`data-clear-secret="${key}"`));
  assert.match(html, /data-query-xxsyun-payment-balance/);
  assert.match(html, /查询积分/);
  assert.match(html, /role="status" aria-live="polite"/);
});

test('已保存Key、草稿和明确清空分别查询，积分零值和未知值准确显示且不保存', async () => {
  const {context, view, status, click, edit} = createView();
  const calls = [];
  context.api = async (url, options) => {
    calls.push({url, payload: JSON.parse(options.body)});
    return {ok: true, payment_provider: 'xxsyun', balance: {available_points: 0, pending_points: null, used_points: 3.5, cost_points: 2}};
  };
  await click();
  assert.match(status.textContent, /可用 0 积分.*预占 未知.*已用 3.5 积分.*每单 2 积分/);
  assert.equal(JSON.stringify(view.pending), '{}');
  edit('fixture-draft');
  await click();
  edit('', true);
  await click();
  assert.deepEqual(calls.map(call => call.payload), [{}, {api_key: 'fixture-draft'}, {api_key: ''}]);
  assert.ok(calls.every(call => call.url === '/api/extract-link/payments/xxsyun/balance'));
});

test('查询期间编辑、清空、撤销或保存Key都会阻止迟到结果覆盖', async () => {
  for (const action of ['edit', 'clear', 'reset', 'save']) {
    const {context, view, button, status, click, edit} = createView();
    let finish;
    context.api = async url => url === '/api/config' ? {reloaded: true, restart_required: []}
      : new Promise(resolve => { finish = resolve; });
    edit('fixture-key');
    const request = click();
    assert.equal(button.disabled, true);
    if (action === 'edit') edit('fixture-new-key');
    if (action === 'clear') edit('', true);
    if (action === 'reset') view.reset();
    if (action === 'save') await view.save();
    assert.equal(button.disabled, false);
    assert.equal(status.textContent, '');
    finish({ok: true, balance: {available_points: 999, pending_points: 0, used_points: 0, cost_points: 1}});
    await request;
    assert.equal(status.textContent, '');
  }
});

test('非法积分响应明确报错，缺字段显示未知；服务地址草稿需保存后查询', async () => {
  const {context, view, status, click} = createView();
  let count = 0;
  context.api = async () => {
    count += 1;
    return count === 1 ? {ok: true, balance: {available_points: -1}} : {ok: true, balance: {}};
  };
  await click();
  assert.match(status.textContent, /积分响应无效/);
  await click();
  assert.match(status.textContent, /可用 未知.*预占 未知.*已用 未知.*每单 未知/);
  vm.runInContext(`setPendingConfigValue('${base}', 'https://draft.example.test')`, context);
  await click();
  assert.match(status.textContent, /先保存.*服务地址/);
  assert.equal(count, 2);
  assert.equal(view.pending[base], 'https://draft.example.test');
});

test('独立支付实际平台错误码显示对应中文原因，不显示异常原文', async () => {
  for (const [code, message] of [['UNAUTHENTICATED', /Key 无效/], ['EMPLOYER_PENDING', /账号尚未就绪/],
    ['PASSWORD_CHANGE_REQUIRED', /修改密码/], ['RATE_LIMITED', /过于频繁/]]) {
    const {context, click, status} = createView();
    context.api = async () => { throw {code, message: 'fixture-private-upstream'}; };
    await click();
    assert.match(status.textContent, message);
    assert.doesNotMatch(status.textContent, /fixture-private-upstream/);
  }
});
