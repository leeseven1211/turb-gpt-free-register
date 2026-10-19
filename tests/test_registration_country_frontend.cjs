const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/config.js'), 'utf8');

function createCountryView() {
  const fields = [
    {key: 'REGISTRATION_DRIVER', label: '注册主流程驱动', type: 'str', group: '注册主链路', value: 'roxy'},
    {key: 'REGISTRATION_COUNTRY', label: '注册国家', type: 'str', group: '注册主链路', value: 'JP', country_codes: ['JP', 'US', 'NA']},
    {key: 'REGISTRATION_AUTH_MODE', label: '注册认证方式', type: 'str', group: '注册主链路', value: 'otp'},
    {key: 'PROXY_POOL_DEFAULT_COUNTRY', label: '默认国家', type: 'str', group: '代理与网络', value: 'US', country_codes: ['JP', 'US', 'NA']},
  ];
  const root = {addEventListener() {}};
  const context = {
    CONFIG: fields, esc: String, attrEsc: String,
    isPlaceholderEmpty: value => value === '' || value == null || String(value).trim().toLowerCase() === 'na',
    $(selector) { return selector === '#tab-config' ? root : null; },
    document: {querySelectorAll() { return []; }, getElementById() { return null; }},
    localStorage: {setItem() {}, getItem() { return null; }},
    window: {addEventListener() {}, scrollTo() {}}, activateTab() {},
  };
  vm.createContext(context);
  vm.runInContext(`${source}
    globalThis.view = {
      groups: configGroups, setPending: setPendingConfigValue, pending: CONFIG_PENDING_UPDATES,
      render: () => renderConfigDomainSectionV2('注册主链路', CONFIG.filter(field => field.group === '注册主链路')),
      control: key => renderConfigControlMarkupV2(CONFIG.find(field => field.key === key)),
      read: value => readConfigElementValue({value, dataset: {}}, CONFIG.find(field => field.key === 'REGISTRATION_COUNTRY')),
      countryOptions: query => configCountryOptionsV2(CONFIG.find(field => field.key === 'REGISTRATION_COUNTRY'), query),
      poolSummary: renderProxyTaskPoolSummaryV2,
    };
  `, context);
  return context.view;
}

test('注册国家归入注册主链路基础流程，显示中文国家与代码下拉', () => {
  const view = createCountryView();
  assert.ok(view.groups()['注册与账号'].some(field => field.key === 'REGISTRATION_COUNTRY'));
  const markup = view.render();
  assert.match(markup, /select data-key="REGISTRATION_COUNTRY" aria-label="注册国家"/);
  assert.match(markup, /option value="JP" selected>日本 · JP/);
  assert.match(markup, /option value="NA">纳米比亚 · NA/);
  assert.ok(markup.indexOf('data-key="REGISTRATION_DRIVER"') < markup.indexOf('data-key="REGISTRATION_COUNTRY"'));
  assert.ok(markup.indexOf('data-key="REGISTRATION_COUNTRY"') < markup.indexOf('data-key="REGISTRATION_AUTH_MODE"'));
  assert.deepEqual(Array.from(view.countryOptions('纳米比亚'), item => item.code), ['NA']);
  assert.deepEqual(Array.from(view.countryOptions('us'), item => item.code), ['US']);
});

test('注册国家草稿独立于池默认国家并保留NA，不被空占位规则吞掉', () => {
  const view = createCountryView();
  assert.equal(view.read('NA'), 'NA');
  view.setPending('REGISTRATION_COUNTRY', view.read('NA'));
  view.setPending('PROXY_POOL_DEFAULT_COUNTRY', 'JP');
  assert.match(view.render(), /option value="NA" selected>纳米比亚 · NA/);
  assert.match(view.control('PROXY_POOL_DEFAULT_COUNTRY'), /option value="JP" selected>日本 · JP/);
  view.setPending('PROXY_POOL_DEFAULT_COUNTRY', 'US');
  assert.match(view.render(), /option value="NA" selected>纳米比亚 · NA/);
  assert.equal(view.pending.REGISTRATION_COUNTRY, 'NA');
  assert.match(view.poolSummary(), /注册主链路的注册国家/);
  assert.doesNotMatch(view.poolSummary(), /注册入队时的池默认国家/);
});
