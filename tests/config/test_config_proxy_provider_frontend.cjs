const assert = require('node:assert/strict');
const test = require('node:test');
const {field, createConfigView, cleanup, flush} = require('./vue_fixture.cjs');
test.afterEach(cleanup);
function providerView(dependencies = {}) {
  const f = (key, value, extra = {}) => field(key, '代理与网络', {value, ...extra});
  return createConfigView([
    f('PROXY_POOL_SOURCE', '1024proxy', {options: ['1024proxy', '711proxy', 'manual'].map(value => ({value, label: value}))}),
    f('PROXY_POOL_DEFAULT_COUNTRY', 'JP'), f('PROXY_POOL', [], {type: 'list_str_multiline', secret: true}),
    ...['1024', '711'].flatMap(provider => [f(`PROXY_${provider}_API_URL`, '', {secret: true, configured: true}), f(`PROXY_${provider}_PROTOCOL`, 'http'), f(`PROXY_${provider}_SESSION_MINUTES`, 30, {type: 'int'})]),
  ], dependencies);
}
test('切换供应商仅显示对应参数，未选来源搜索和草稿保持可用', async () => {
  const view = providerView(); await view.open('代理与网络'); await view.section('代理来源');
  assert.equal(view.wrapper.find('[data-key="PROXY_1024_API_URL"]').exists(), true);
  assert.equal(view.wrapper.find('[data-key="PROXY_711_API_URL"]').exists(), false);
  view.owner.setField('PROXY_711_API_URL', 'https://example.test/api?key=draft');
  await view.control('PROXY_POOL_SOURCE').setValue('711proxy');
  assert.equal(view.control('PROXY_711_API_URL').element.value, 'https://example.test/api?key=draft');
  assert.equal(view.wrapper.find('[data-key="PROXY_1024_API_URL"]').exists(), false);
  assert.equal(view.wrapper.find('[role="status"][aria-live="polite"]').exists(), true);
  await view.control('PROXY_POOL_SOURCE').setValue('manual');
  assert.equal(view.wrapper.find('[data-key="PROXY_POOL"]').exists(), true);
  assert.equal(view.wrapper.find('[data-config-action="test-proxy"]').exists(), false);
  await view.search('PROXY_711_API_URL');
  assert.equal(view.control('PROXY_711_API_URL').element.value, 'https://example.test/api?key=draft');
  await view.search(''); await view.control('PROXY_POOL_SOURCE').setValue('711proxy');
  assert.equal(view.control('PROXY_711_API_URL').element.value, 'https://example.test/api?key=draft');
});
test('测试使用当前供应商未保存参数，反馈加载成功且不隐式保存', async () => {
  let resolve;
  const view = providerView({request: (url) => url === '/api/proxy-provider/test' ? new Promise(done => {resolve = done;}) : Promise.resolve({items: [{type: 'plus'}]})});
  await view.open('代理与网络'); await view.section('代理来源'); await view.control('PROXY_POOL_SOURCE').setValue('711proxy');
  view.owner.setField('PROXY_POOL_DEFAULT_COUNTRY', 'GB'); view.owner.setField('PROXY_711_PROTOCOL', 'socks5h'); view.owner.setField('PROXY_711_SESSION_MINUTES', 45);
  view.owner.setField('PROXY_1024_API_URL', 'other-draft'); await view.control('PROXY_711_API_URL').setValue('https://example.test/api?key=unsaved');
  const button = view.wrapper.get('[data-config-action="test-proxy"]'); await button.trigger('click'); await flush();
  assert.equal(button.element.disabled, true);
  const call = view.requests.find(item => item.url === '/api/proxy-provider/test');
  assert.deepEqual(JSON.parse(call.options.body), {provider: '711proxy', api_url: 'https://example.test/api?key=unsaved', region: 'GB', protocol: 'socks5h', session_minutes: 45});
  resolve({ok: true, lease: {provider: '711proxy', region: 'GB', endpoint: 'proxy:80', exit_ip: '192.0.2.1'}}); await flush();
  assert.equal(button.element.disabled, false); assert.match(view.wrapper.text(), /测试成功 · 711proxy/);
  assert.equal(view.owner.readField('PROXY_1024_API_URL'), 'other-draft'); assert.equal(view.saves.length, 0);
});
test('测试沿用已保存密钥，失败不回显敏感异常且草稿保留', async () => {
  const view = providerView({request: async url => {if (url === '/api/proxy-provider/test') throw new Error('private-key=never-display'); return {items: [{type: 'plus'}]};}});
  await view.open('代理与网络'); await view.section('代理来源'); await view.control('PROXY_POOL_SOURCE').setValue('711proxy'); view.owner.setField('PROXY_711_SESSION_MINUTES', 60);
  const button = view.wrapper.get('[data-config-action="test-proxy"]'); await button.trigger('click'); await flush();
  const payload = JSON.parse(view.requests.find(item => item.url === '/api/proxy-provider/test').options.body);
  assert.equal(payload.api_url, ''); assert.equal(payload.session_minutes, 60);
  assert.match(view.wrapper.text(), /代理提取测试失败/); assert.doesNotMatch(view.wrapper.text(), /never-display/);
  assert.equal(button.element.disabled, false); assert.equal(view.owner.readField('PROXY_711_SESSION_MINUTES'), 60);
});
