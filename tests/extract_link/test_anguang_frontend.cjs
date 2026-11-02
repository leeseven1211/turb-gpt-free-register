const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const configSource = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/config/page.js'), 'utf8');
const workbenchSource = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/extract_link/page.js'), 'utf8');
const prefix = 'EXTRACT_LINK_ANGUANG_';
const field = (key, extra = {}) => ({key, group: '提链', label: key, type: 'str', value: '', ...extra});

function configView() {
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', {value: 'legacy', options: [{value: 'legacy', label: '虾扯蛋链'}, {value: 'anguang', label: 'anguang'}]}),
    field('EXTRACT_LINK_LEGACY_ENABLED', {type: 'bool', value: true}),
    field(prefix + 'ENABLED', {type: 'bool', value: false}),
    field(prefix + 'AUTO_PAYMENT_ENABLED', {type: 'bool', value: false}),
    field(prefix + 'AUTO_RETRY', {type: 'bool', value: false}),
    field(prefix + 'API_BASE', {value: 'https://ytc.xxsyun.xyz/openapi/v1'}),
    field(prefix + 'API_KEY', {secret: true, configured: true}),
    field(prefix + 'PROCESSING_MODE', {value: 'STANDARD', options: [{value: 'STANDARD', label: '流光'}, {value: 'STRICT', label: 'sea'}]}),
    field(prefix + 'PLAN_NAME', {value: 'chatgptplusplan'}),
    field('EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY', {secret: true, configured: true}),
  ];
  const context = {
    CONFIG: fields,
    document: {getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; },
      addEventListener() {}, documentElement: {dataset: {}}},
    window: {addEventListener() {}, scrollTo() {}},
    localStorage: {getItem() { return null; }, setItem() {}},
    $(selector) { return selector === '#tab-config' ? {addEventListener() {}} : null; },
    esc: value => String(value ?? ''), attrEsc: value => String(value ?? ''),
    isPlaceholderEmpty: value => value == null || value === '',
  };
  vm.createContext(context);
  vm.runInContext(`${configSource}\n;globalThis.view = {
    render: () => renderExtractLinkSectionV2(CONFIG),
    open() { CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2 = '暗光（XXSYUN 一条龙）'; },
    search() { CONFIG_NAV_QUERY_V2 = '${prefix}API_KEY'; selectConfigSearchDestinationV2('提链'); },
    section: () => CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2,
    pending: CONFIG_PENDING_UPDATES,
  };`, context);
  return context.view;
}

test('暗光配置分类能通过Key搜索定位，显示独立密钥且不修改任何开关', () => {
  const view = configView();
  const common = view.render();
  assert.match(common, /data-extract-link-tab="暗光（XXSYUN 一条龙）"/);
  assert.match(common, /anguang/);
  view.search();
  assert.equal(view.section(), '暗光（XXSYUN 一条龙）');
  const html = view.render();
  assert.match(html, /type="password" data-key="EXTRACT_LINK_ANGUANG_API_KEY" value=""/);
  assert.match(html, /data-clear-secret="EXTRACT_LINK_ANGUANG_API_KEY"/);
  assert.doesNotMatch(html, /data-key="EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"/);
  assert.doesNotMatch(html, /data-query-xxsyun-payment-balance/);
  assert.doesNotMatch(html, /data-key="EXTRACT_LINK_ANGUANG_AUTO_PAYMENT_ENABLED" checked/);
  assert.equal(JSON.stringify(view.pending), '{}');
});

test('暗光分类解释平台自动扫码及三种结果的独立含义', () => {
  const view = configView();
  view.open();
  const html = view.render();
  assert.match(html, /平台必自动扫码，不能关闭/);
  assert.match(html, /SUCCEEDED[^<]*只.*出链/);
  assert.match(html, /scan\.completed[^<]*扫码完成/);
  assert.match(html, /Plus[^<]*独立核对/);
  assert.match(html, /一条虫 Key/);
  assert.match(html, /普通扫码 Key/);
});

function workbenchView() {
  const context = {URL, URLSearchParams, document: {getElementById() { return null; }, addEventListener() {}},
    window: {}, setTimeout, clearTimeout};
  vm.createContext(context);
  vm.runInContext(`${workbenchSource}\n;globalThis.view = {
    setup() { EXTRACT_WORKBENCH_CONFIG = {providers: [{id: 'anguang', modes: ['auto_payment'], link_types: ['upi'], default_type: 'upi', payment_source: 'native', payment_sources: ['native']}]}; },
    create: extractWorkbenchCreatePayload, card: renderExtractWorkbenchTaskCard,
  };`, context);
  context.view.setup();
  return context.view;
}

test('暗光任务只接受服务端公布的自动支付与UPI，未明确模式时不默认付款', () => {
  const view = workbenchView();
  for (const mode of ['extract_only', 'manual_payment', '']) {
    const result = view.create(['123'], 'anguang', mode, 'upi');
    assert.equal(result.mode, '');
  }
  const payload = view.create(['123', '123'], 'anguang', 'auto_payment', 'pix');
  assert.equal(payload.mode, 'auto_payment');
  assert.equal(payload.type, 'upi');
  assert.equal(payload.provider_id, 'anguang');
  assert.equal(JSON.stringify(payload.account_ids), '["123"]');
});

test('历史暗光任务仍用暗光名称展示，不依赖当前平台是否启用', () => {
  const html = workbenchView().card({task_id: '1', provider_id: 'anguang', mode: 'auto_payment',
    task_status: 'running', payment_status: 'pending', extraction_status: 'succeeded', plus_status: 'pending'});
  assert.match(html, /暗光（XXSYUN 一条龙）/);
});
