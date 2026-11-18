const assert = require('node:assert/strict');
const test = require('node:test');
const {createConfigView, field, cleanup, flush} = require('../config/vue_fixture.cjs');
test.afterEach(cleanup);
const keys = {extraction: 'EXTRACT_LINK_HUANGUANG_CDK', payment: 'EXTRACT_LINK_HUANGUANG_PAYMENT_CDK', xxsyun: 'EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY', base: 'EXTRACT_LINK_HUANGUANG_API_BASE'};
const names = {extraction: 'huanguangExtraction', payment: 'huanguangPayment', xxsyun: 'huanguangXxsyun'};
const quota = (remaining = 3) => ({ok: true, quota: {required: true, remaining, reserved: 0, active: true}});
function createView(request = async () => quota()) {
  const view = createConfigView(Object.entries(keys).map(([kind, key]) => field(key, '提链', {
    label: kind === 'extraction' ? '幻光提链 CDK' : kind === 'payment' ? '幻光支付扫码 CDK' : key,
    secret: kind !== 'base', configured: true, value: kind === 'base' ? 'https://quota.example.test' : '',
  })), {request: (url, options) => url.includes('/types') ? {items: []} : request(url, options)});
  const controls = Object.fromEntries(['extraction', 'payment', 'xxsyun'].map(kind => [kind, view.mountField(keys[kind])]));
  return {...view, controls, state: kind => view.actions.states[names[kind]],
    query: kind => kind === 'xxsyun' ? view.actions.queryHuanguangXxsyun() : view.actions.queryHuanguangQuota(kind),
    button: kind => controls[kind].get(`[data-config-field-action="${keys[kind]}"]`),
    status: kind => controls[kind].get('.config-field-actions [role="status"]'),
    edit: (kind, value) => view.owner.setField(keys[kind], value),
    clear: kind => view.owner.clearSecret(keys[kind]),
    requestsForQuota: () => view.requests.filter(call => !call.url.includes('/types')),
  };
}

test('两类 CDK 各自渲染可访问的查询按钮与结果区', async () => {
  const view = createView();
  for (const kind of ['extraction', 'payment']) {
    assert.equal(view.button(kind).attributes('type'), 'button');
    assert.equal(view.button(kind).attributes('aria-label'), `查询幻光${kind === 'extraction' ? '提链' : '支付扫码'} CDK 剩余次数`);
    assert.equal(view.status(kind).attributes('aria-live'), 'polite');
    await view.button(kind).trigger('click'); await flush();
    assert.match(view.status(kind).text(), /剩余 3 次/);
  }
});

test('保存 CDK 后的新查询不会复用保存前尚未结束的 GET 响应', async () => {
  let finishOld, queries = 0;
  const view = createView(() => ++queries === 1 ? new Promise(resolve => {finishOld = resolve;}) : quota(2));
  const oldQuery = view.query('extraction'); await flush();
  view.edit('extraction', 'changed-cdk-test');
  await view.owner.saveAll();
  const newQuery = view.query('extraction'); await flush();
  assert.equal(view.button('extraction').element.disabled, true);
  finishOld(quota(99)); await oldQuery; await newQuery; await flush();
  assert.equal(queries, 2);
  assert.match(view.status('extraction').text(), /剩余 2 次/);
  assert.doesNotMatch(view.status('extraction').text(), /99/);
  assert.equal(view.button('extraction').element.disabled, false);
  assert.deepEqual(view.saves, [{[keys.extraction]: 'changed-cdk-test'}]);
});

test('CDK 查询只 GET 已保存的对应项目，保留零与未知次数且不保存配置', async () => {
  const view = createView(() => ({ok: true, quota: {required: true, remaining: 0, reserved: null, active: true}}));
  await view.query('extraction'); await view.query('payment'); await flush();
  assert.deepEqual(view.requestsForQuota().map(({url, options}) => ({url, method: options.method, body: options.body})), [
    {url: '/api/extract-link/huanguang/cdk-quota/extraction', method: 'GET', body: undefined},
    {url: '/api/extract-link/huanguang/cdk-quota/payment', method: 'GET', body: undefined},
  ]);
  for (const kind of ['extraction', 'payment']) {
    assert.match(view.status(kind).text(), /剩余 0 次.*占用 未知.*已启用/);
    assert.equal(view.button(kind).element.disabled, false);
  }
  assert.equal(view.owner.dirtyCount.value, 0); assert.equal(view.saves.length, 0);
});

test('CDK 免计次、停用与未知状态分别呈现，不把未知次数变成零', async () => {
  for (const scenario of [
    {quota: {required: false, remaining: null, reserved: null, active: true}, want: /^平台免计次$/},
    {quota: {required: true, remaining: 7, reserved: 0, active: false}, want: /已停用/},
    {quota: {required: true, remaining: null, reserved: 0, active: null}, want: /剩余 未知.*状态未知/},
  ]) {
    const view = createView(() => ({ok: true, quota: scenario.quota}));
    await view.query('payment'); await flush();
    assert.match(view.status('payment').text(), scenario.want);
    assert.doesNotMatch(view.status('payment').text(), /剩余 0 次/);
  }
});

test('未保存的 CDK 与 API_BASE 阻止查询草稿，另一类 CDK 可独立查询', async () => {
  const view = createView(); view.edit('extraction', 'draft-cdk-test');
  await view.query('extraction'); await flush();
  assert.match(view.status('extraction').text(), /先保存/); assert.equal(view.requestsForQuota().length, 0);
  await view.query('payment'); assert.equal(view.requestsForQuota().length, 1);
  view.edit('base', 'https://draft.example.test'); await view.query('payment'); await flush();
  assert.match(view.status('payment').text(), /先保存/); assert.equal(view.requestsForQuota().length, 1);
});

test('CDK 查询期间编辑或清除凭据会失效旧结果且恢复按钮', async () => {
  for (const change of ['edit', 'clear', 'base']) {
    let resolve; const view = createView(() => new Promise(done => {resolve = done;}));
    const request = view.query('extraction'); await flush();
    assert.equal(view.button('extraction').element.disabled, true); assert.match(view.button('extraction').text(), /正在查询/);
    assert.equal(view.controls.extraction.get('.config-field-actions').attributes('aria-busy'), 'true');
    if (change === 'edit') view.edit('extraction', 'new-draft-test');
    if (change === 'clear') view.clear('extraction');
    if (change === 'base') view.edit('base', 'https://next.example.test');
    await flush(); assert.equal(view.button('extraction').element.disabled, false); assert.equal(view.state('extraction').text, '');
    resolve(quota(99)); await request; await flush(); assert.equal(view.state('extraction').text, '');
    await view.query('extraction'); await flush(); assert.match(view.status('extraction').text(), /先保存/);
  }
});

test('清空草稿、撤销与保存也清除次数结果，保存中的旧 XXSYUN 查询不能回写', async () => {
  let resolve; const view = createView(url => url.endsWith('xxsyun-quota') ? new Promise(done => {resolve = done;}) : quota(8));
  await view.query('payment'); view.edit('payment', 'draft-test'); view.edit('payment', '');
  assert.equal(view.state('payment').text, '');
  await view.query('payment'); await flush(); assert.match(view.status('payment').text(), /剩余 8 次/);
  view.edit('payment', 'next-test'); view.owner.reset(); assert.equal(view.state('payment').text, '');
  view.edit('xxsyun', 'draft-key-test'); const request = view.query('xxsyun'); await flush();
  assert.equal(view.button('xxsyun').element.disabled, true); await view.owner.saveAll();
  resolve({ok: true, remainingUses: 99, totalUses: 99, reservedUses: 0}); await request; await flush();
  assert.equal(view.state('xxsyun').text, ''); assert.equal(view.button('xxsyun').element.disabled, false);
});

test('API_BASE 编辑作废旧 XXSYUN 请求，保存后仍可查询 Key 草稿', async () => {
  let finishOld, count = 0; const view = createView(() => ++count === 1 ? new Promise(resolve => {finishOld = resolve;}) : {ok: true, remainingUses: 2, totalUses: null, reservedUses: 0});
  const oldQuery = view.query('xxsyun'); await flush(); assert.equal(view.button('xxsyun').element.disabled, true);
  view.edit('base', 'https://changed.example.test'); await flush(); assert.equal(view.button('xxsyun').element.disabled, false); assert.equal(view.state('xxsyun').text, '');
  await view.query('xxsyun'); await flush(); assert.match(view.status('xxsyun').text(), /先保存.*服务地址/); assert.equal(count, 1);
  finishOld({ok: true, remainingUses: 99, totalUses: 99, reservedUses: 0}); await oldQuery;
  assert.match(view.state('xxsyun').text, /先保存.*服务地址/);
  await view.owner.saveAll(); assert.equal(view.state('xxsyun').text, '');
  view.edit('xxsyun', 'draft-key-test'); await view.query('xxsyun'); await flush();
  assert.equal(count, 2); assert.equal(view.saves.length, 1);
  const call = view.requestsForQuota().at(-1); assert.equal(call.url, '/api/extract-link/huanguang/xxsyun-quota');
  assert.deepEqual(JSON.parse(call.options.body), {api_key: 'draft-key-test'});
  assert.match(view.status('xxsyun').text(), /剩余 2 次/); assert.equal(view.button('xxsyun').element.disabled, false);
});

test('单项查询加载与失败独立，按稳定错误码显示安全原因并能再次查询', async () => {
  const resolvers = {}; const view = createView(url => new Promise((done, fail) => {resolvers[url.split('/').pop()] = {done, fail};}));
  const extraction = view.query('extraction'), payment = view.query('payment'); await flush();
  assert.equal(view.button('extraction').element.disabled, true); assert.equal(view.button('payment').element.disabled, true);
  resolvers.extraction.fail(Object.assign(new Error('raw-private-response'), {code: 'network_error'})); await extraction; await flush();
  assert.match(view.status('extraction').text(), /网络/); assert.doesNotMatch(view.status('extraction').text(), /raw-private/);
  assert.equal(view.button('extraction').element.disabled, false); assert.equal(view.button('payment').element.disabled, true);
  resolvers.payment.done(quota(4)); await payment;
  view.dependencies.request = () => quota(2); await view.query('extraction'); await flush(); assert.match(view.status('extraction').text(), /剩余 2 次/);
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
    const view = createView(() => {throw Object.assign(new Error('raw-private-key-and-response'), {code: scenario.code});});
    await view.query(scenario.kind); await flush(); assert.match(view.status(scenario.kind).text(), scenario.want);
    assert.doesNotMatch(view.status(scenario.kind).text(), /raw-private|unrecognized-private/); assert.equal(view.button(scenario.kind).element.disabled, false);
  }
});

test('CDK 非法数字和缺失结构归为响应异常，不伪造余额', async () => {
  for (const data of [null, {}, {required: true, remaining: -1, reserved: null, active: true},
    {required: true, remaining: 1.5, reserved: null, active: true},
    {required: true, remaining: Number.MAX_SAFE_INTEGER + 1, reserved: null, active: true},
    {required: true, remaining: null, reserved: '0', active: true},
    {required: true, remaining: 0, reserved: 0, active: 'true'}]) {
    const view = createView(() => ({ok: true, quota: data})); await view.query('extraction'); await flush();
    assert.match(view.status('extraction').text(), /响应.*无效|响应.*异常/); assert.doesNotMatch(view.status('extraction').text(), /剩余 0 次/);
    assert.equal(view.button('extraction').element.disabled, false);
  }
});
