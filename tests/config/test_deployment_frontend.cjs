const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {field, createConfigView, cleanup, harness, navigation} = require('./vue_fixture.cjs');
const commonSource = fs.readFileSync(path.join(__dirname, '../../webui/static/js/shared/common.js'), 'utf8');
test.afterEach(cleanup);

test('配置选项保留禁用原因并呈现不可选的浏览器驱动', () => {
  const f = field('REGISTRATION_DRIVER', '注册主链路', {value: 'protocol_oss_2', options: [
    {value: 'protocol_oss_2', label: '协议 2'}, {value: 'roxy', label: 'Roxy', disabled: true, reason: '当前部署未提供浏览器'},
  ]});
  const view = createConfigView([f]);
  assert.equal(navigation.schemaOptions(f)[1].disabled, true);
  const select = view.control(f.key);
  assert.equal(select.element.value, 'protocol_oss_2');
  assert.equal(select.element.disabled, false);
  assert.equal(select.get('option[value="roxy"]').element.disabled, true);
  assert.match(select.text(), /当前部署未提供浏览器/);
});

test('纯浏览器配置置灰并显示原因，历史开启的兜底仍可关闭', async () => {
  const fields = [field('ROXY_API_BASE', 'RoxyBrowser', {readonly: true}), field('ROXY_OPEN_HEADLESS', 'RoxyBrowser', {type: 'bool', value: false, readonly: true}), field('LIVE_CHECK_ROXY_FALLBACK_ENABLED', '刷新 AT', {type: 'bool', value: true, disable_enable: true})].map(f => ({...f, reason: '当前部署未提供浏览器'}));
  const view = createConfigView(fields);
  for (const key of ['ROXY_API_BASE', 'ROXY_OPEN_HEADLESS']) {
    const control = view.mountField(key);
    assert.equal(control.get('fieldset').element.disabled, true);
    assert.match(control.text(), /当前部署未提供浏览器/);
  }
  const fallback = view.mountField('LIVE_CHECK_ROXY_FALLBACK_ENABLED');
  assert.equal(fallback.get('fieldset').element.disabled, false);
  await fallback.get('input').setValue(false);
  assert.equal(view.owner.readField('LIVE_CHECK_ROXY_FALLBACK_ENABLED'), false);
  assert.equal(fallback.get('fieldset').element.disabled, true);
});

test('关闭普通浏览器查活 gate 时仍显示部署禁用选项及原因', () => {
  const view = createConfigView([field('ACCOUNT_LIVE_CHECK_DRIVER', '查活', {value: 'protocol_current', options: [
    {value: 'protocol_current', label: '协议'}, {value: 'browser_roxy', label: 'Roxy', disabled: true, reason: '当前部署未提供浏览器'},
  ]}), field('ACCOUNT_LIVE_CHECK_BROWSER_ENABLED', '查活', {type: 'bool', value: false})]);
  const select = view.control('ACCOUNT_LIVE_CHECK_DRIVER');
  assert.equal(select.findAll('option').length, 2);
  assert.equal(select.get('option[value="browser_roxy"]').element.disabled, true);
  assert.match(select.text(), /当前部署未提供浏览器/);
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
