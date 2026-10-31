const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '../..');
const configSource = fs.readFileSync(path.join(root, 'webui/static/js/pages/config/page.js'), 'utf8');
const commonSource = fs.readFileSync(path.join(root, 'webui/static/js/shared/common.js'), 'utf8');

function configContext(fields = []) {
  const context = vm.createContext({
    CONFIG: fields, document: {addEventListener() {}, querySelectorAll: () => []},
    window: {addEventListener() {}}, $: () => ({addEventListener() {}}),
    esc: String, attrEsc: String, isPlaceholderEmpty: value => value == null || value === '',
  });
  vm.runInContext(configSource, context);
  return context;
}

test('配置选项保留禁用原因并呈现不可选的浏览器驱动', () => {
  const field = {key: 'REGISTRATION_DRIVER', label: '注册驱动', type: 'str', value: 'protocol_oss_2', options: [
    {value: 'protocol_oss_2', label: '协议 2'},
    {value: 'roxy', label: 'Roxy', disabled: true, reason: '当前部署未提供浏览器'},
  ]};
  const context = configContext([field]);
  const options = context.configSchemaOptions(field);
  assert.equal(options[1].disabled, true);
  assert.equal(options[1].reason, '当前部署未提供浏览器');
  const html = context.renderConfigControlMarkupV2(field);
  assert.match(html, /<option value="roxy"[^>]*disabled[^>]*>Roxy/);
  assert.match(html, /当前部署未提供浏览器/);
  assert.match(html, /<option value="protocol_oss_2" selected>协议 2<\/option>/);
  assert.doesNotMatch(html, /<select[^>]* disabled/);
});

test('纯浏览器配置置灰并显示原因，历史开启的兜底仍可关闭', () => {
  const context = configContext();
  for (const field of [
    {key: 'ROXY_API_BASE', type: 'str', value: 'http://127.0.0.1:50100', readonly: true},
    {key: 'ROXY_OPEN_HEADLESS', type: 'bool', value: false, readonly: true},
    {key: 'LIVE_CHECK_ROXY_FALLBACK_ENABLED', type: 'bool', value: false, disable_enable: true},
  ]) {
    const html = context.renderConfigControlMarkupV2({...field, label: '浏览器配置', reason: '当前部署未提供浏览器'});
    assert.match(html, /<fieldset[^>]*disabled/);
    assert.match(html, /当前部署未提供浏览器/);
  }
  const enabled = context.renderConfigControlMarkupV2({
    key: 'LIVE_CHECK_ROXY_FALLBACK_ENABLED', type: 'bool', value: true, disable_enable: true, reason: '当前部署未提供浏览器',
  });
  assert.doesNotMatch(enabled, /<fieldset[^>]*disabled/);
  assert.match(enabled, /当前部署未提供浏览器/);
});

test('关闭普通浏览器查活 gate 时仍显示部署禁用选项及原因', () => {
  const context = configContext([
    {key: 'ACCOUNT_LIVE_CHECK_DRIVER', options: [
      {value: 'protocol_current', label: '协议'},
      {value: 'browser_roxy', label: 'Roxy', disabled: true, reason: '当前部署未提供浏览器'},
    ]},
    {key: 'ACCOUNT_LIVE_CHECK_BROWSER_ENABLED', value: false},
  ]);
  assert.equal(context.liveCheckDriverChoices().length, 2);
  assert.equal(context.liveCheckDriverChoices()[1].disabled, true);
});

test('查活与刷新 AT 独立置灰，浏览器动作不会误禁协议 2FA 或补全', () => {
  const buttons = [
    ['#btnCheckSelectedLiveV2', '查活'], ['#btnRefreshSelectedTokenV2', '刷新 AT'],
    ['#btnAddPasswordSelectedAccountsV2', '补密码'], ['#btnChangeTwofaSelectedAccountsV2', '修改 2FA'],
    ['#btnAddTwofaSelectedAccountsV2', '补 2FA'], ['#btnCompleteSelectedAccountsV2', '补全账号'],
  ].map(([selector, title]) => ({selector, title, dataset: {}, attrs: {}, classes: new Set(),
    classList: {toggle(name, enabled) { if (enabled) this.owner.classes.add(name); else this.owner.classes.delete(name); }},
    setAttribute(name, value) { this.attrs[name] = value; },
  }));
  buttons.forEach(button => { button.classList.owner = button; });
  const context = vm.createContext({
    document: {querySelectorAll(selector) { return buttons.filter(button => selector.split(',').includes(button.selector)); }},
  });
  const start = commonSource.indexOf('let CAPABILITIES =');
  const end = commonSource.indexOf('async function loadCapabilities()', start);
  vm.runInContext(commonSource.slice(start, end), context);
  vm.runInContext(`CAPABILITIES = {features: {
    live_check: {enabled: true}, token_refresh: {enabled: false, reason: '刷新驱动需要浏览器'},
    password_setup: {enabled: false, reason: '补密码需要浏览器'}, twofa_change: {enabled: false, reason: '修改 2FA 需要浏览器'},
  }}; applyFeatureGates();`, context);
  assert.equal(buttons[0].attrs['aria-disabled'], 'false');
  assert.equal(buttons[1].attrs['aria-disabled'], 'true');
  assert.match(buttons[1].title, /刷新驱动需要浏览器/);
  assert.equal(buttons[2].attrs['aria-disabled'], 'true');
  assert.equal(buttons[3].attrs['aria-disabled'], 'true');
  assert.equal(buttons[4].classes.has('feature-unavailable'), false);
  assert.equal(buttons[5].classes.has('feature-unavailable'), false);
  vm.runInContext(`CAPABILITIES.features.token_refresh = {enabled: true}; applyFeatureGates();`, context);
  assert.equal(buttons[1].attrs['aria-disabled'], 'false');
  assert.equal(buttons[1].title, '刷新 AT');
});
