const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/config/page.js'), 'utf8');

function createProviderView() {
  const field = (key, value, extra = {}) => ({key, value, label: key, type: 'str', group: '代理与网络', ...extra});
  const fields = [
    field('PROXY_POOL_SOURCE', '1024proxy', {options: ['1024proxy', '711proxy', 'manual'].map(value => ({value, label: value}))}),
    field('PROXY_POOL_DEFAULT_COUNTRY', 'JP'), field('PROXY_POOL', [], {type: 'list_str_multiline', secret: true}),
    ...['1024', '711'].flatMap(provider => [
      field(`PROXY_${provider}_API_URL`, '', {secret: true, configured: true}),
      field(`PROXY_${provider}_PROTOCOL`, 'http'),
      field(`PROXY_${provider}_SESSION_MINUTES`, 30, {type: 'int'}),
      field(`PROXY_${provider}_API_TIMEOUT`, 12, {type: 'float'}),
    ]),
  ];
  const root = {addEventListener() {}};
  const nodes = new Map([
    ['btnTestProxyProviderV2', {disabled: false, textContent: '', dataset: {}, addEventListener() {}}],
    ['proxyProviderTestStatusV2', {innerHTML: '', textContent: ''}],
  ]);
  const controls = new Map();
  const context = {
    CONFIG: fields, esc: String, attrEsc: String,
    isPlaceholderEmpty: value => value === '' || value == null,
    $(selector) { return selector === '#tab-config' ? root : nodes.get(selector.slice(1)) || null; },
    document: {querySelector: selector => controls.get(selector.match(/data-key="(.*?)"/)?.[1]) || null},
    window: {addEventListener() {}}, showToast() {},
  };
  vm.createContext(context);
  vm.runInContext(`${source}
    CONFIG_PROXY_ACTIVE_SECTION_V2 = '代理来源';
    globalThis.view = {
      pending: CONFIG_PENDING_UPDATES, setPending: setPendingConfigValue,
      render: () => renderConfigDomainSectionV2('代理与网络', CONFIG),
      visible: key => proxySourceFieldVisibleV2(CONFIG.find(field => field.key === key)),
      search: query => { CONFIG_NAV_QUERY_V2 = query; },
      test: testProxyProviderV2,
    };
  `, context);
  return {view: context.view, context, controls, nodes};
}

test('切换供应商仅显示对应参数，草稿和未选来源搜索保持可用', () => {
  const {view} = createProviderView();
  let markup = view.render();
  assert.match(markup, /data-key="PROXY_1024_API_URL"/);
  assert.doesNotMatch(markup, /data-key="PROXY_711_API_URL"/);
  view.setPending('PROXY_711_API_URL', 'https://example.test/api?key=draft');
  view.setPending('PROXY_POOL_SOURCE', '711proxy');
  markup = view.render();
  assert.match(markup, /711Proxy 本地联调/);
  assert.match(markup, /data-key="PROXY_711_API_URL" value="https:\/\/example.test\/api\?key=draft"/);
  assert.doesNotMatch(markup, /data-key="PROXY_1024_API_URL"/);
  assert.match(markup, /role="status" aria-live="polite"/);
  view.setPending('PROXY_POOL_SOURCE', 'manual');
  assert.equal(view.visible('PROXY_POOL'), true);
  assert.equal(view.visible('PROXY_711_API_URL'), false);
  assert.doesNotMatch(view.render(), /btnTestProxyProviderV2/);
  view.search('PROXY_711_API_URL');
  assert.equal(view.visible('PROXY_711_API_URL'), true);
  view.search('');
  view.setPending('PROXY_POOL_SOURCE', '711proxy');
  assert.match(view.render(), /value="https:\/\/example.test\/api\?key=draft"/);
});

test('测试使用当前供应商和未保存参数，并反馈加载、成功状态', async () => {
  const {view, context, controls, nodes} = createProviderView();
  view.setPending('PROXY_POOL_SOURCE', '711proxy');
  view.setPending('PROXY_POOL_DEFAULT_COUNTRY', 'GB');
  view.setPending('PROXY_711_PROTOCOL', 'socks5h');
  view.setPending('PROXY_711_SESSION_MINUTES', 45);
  view.setPending('PROXY_1024_API_URL', 'https://other.test/api?key=other');
  controls.set('PROXY_711_API_URL', {value: 'https://example.test/api?key=unsaved', dataset: {}});
  let payload;
  context.api = async (url, options) => {
    assert.equal(url, '/api/proxy-provider/test');
    assert.equal(nodes.get('btnTestProxyProviderV2').disabled, true);
    payload = JSON.parse(options.body);
    return {lease: {provider: '711proxy', region: 'GB', endpoint: 'proxy:80', exit_ip: '192.0.2.1'}};
  };
  await view.test();
  assert.deepEqual(payload, {
    provider: '711proxy', api_url: 'https://example.test/api?key=unsaved',
    region: 'GB', protocol: 'socks5h', session_minutes: 45,
  });
  assert.equal(nodes.get('btnTestProxyProviderV2').disabled, false);
  assert.match(nodes.get('proxyProviderTestStatusV2').innerHTML, /测试成功 · 711proxy/);
  assert.equal(view.pending.PROXY_1024_API_URL, 'https://other.test/api?key=other');
});

test('测试可沿用已保存密钥，失败后保留草稿并恢复按钮', async () => {
  const {view, context, nodes} = createProviderView();
  view.setPending('PROXY_POOL_SOURCE', '711proxy');
  view.setPending('PROXY_711_SESSION_MINUTES', 60);
  context.api = async (_url, options) => {
    const payload = JSON.parse(options.body);
    assert.equal(payload.api_url, '');
    assert.equal(payload.session_minutes, 60);
    throw new Error('模拟线路检测失败');
  };
  await view.test();
  assert.match(nodes.get('proxyProviderTestStatusV2').innerHTML, /测试失败：模拟线路检测失败/);
  assert.equal(nodes.get('btnTestProxyProviderV2').disabled, false);
  assert.equal(view.pending.PROXY_711_SESSION_MINUTES, 60);
});
