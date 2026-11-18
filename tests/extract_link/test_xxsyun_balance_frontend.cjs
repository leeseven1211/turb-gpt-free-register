const assert = require('node:assert/strict');
const test = require('node:test');
const {createConfigView, field, cleanup, flush} = require('../config/vue_fixture.cjs');
test.afterEach(cleanup);
const key = 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY', base = 'EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE';
function createView(request = async () => ({ok: true, balance: {}})) {
  const view = createConfigView([field(key, '提链', {label: 'XXSYUN API Key', secret: true, configured: true}),
    field(base, '提链', {label: 'XXSYUN API 地址', value: 'https://upi.xxsyun.xyz/api/v1'})],
  {request: (url, options) => url.includes('/types') ? {items: []} : request(url, options)});
  const control = view.mountField(key);
  return {...view, control, state: view.actions.states.xxsyunBalance, query: () => view.actions.queryXxsyunBalance(),
    button: () => control.get(`[data-config-field-action="${key}"]`), status: () => control.get('.config-field-actions [role=status]'),
    edit: value => view.owner.setField(key, value), clear: () => view.owner.clearSecret(key),
    balanceRequests: () => view.requests.filter(call => !call.url.includes('/types'))};
}

test('独立支付Key保留密码框和明确清除，提供积分按钮和可访问结果区', async () => {
  const view = createView();
  assert.equal(view.control.get(`[data-key="${key}"]`).attributes('type'), 'password');
  assert.ok(view.control.find('[aria-label="明确清除XXSYUN API Key"]').exists());
  assert.equal(view.button().text(), '查询积分');
  assert.equal(view.status().attributes('aria-live'), 'polite');
  await view.button().trigger('click'); await flush(); assert.match(view.status().text(), /可用 未知/);
});

test('已保存Key、草稿和明确清空分别查询，积分零值和未知值准确显示且不保存', async () => {
  const view = createView(() => ({ok: true, payment_provider: 'xxsyun', balance: {available_points: 0, pending_points: null, used_points: 3.5, cost_points: 2}}));
  await view.query(); await flush(); assert.match(view.status().text(), /可用 0 积分.*预占 未知.*已用 3.5 积分.*每单 2 积分/);
  assert.equal(view.owner.dirtyCount.value, 0);
  view.edit('fixture-draft'); await view.query(); view.clear(); await view.query();
  assert.deepEqual(view.balanceRequests().map(call => JSON.parse(call.options.body)), [{}, {api_key: 'fixture-draft'}, {api_key: ''}]);
  assert.ok(view.balanceRequests().every(call => call.url === '/api/extract-link/payments/xxsyun/balance'));
  assert.equal(view.saves.length, 0);
});

test('查询期间编辑、清空、撤销或保存Key都会阻止迟到结果覆盖', async () => {
  for (const action of ['edit', 'clear', 'reset', 'save']) {
    let finish; const view = createView(() => new Promise(resolve => {finish = resolve;}));
    view.edit('fixture-key'); const request = view.query(); await flush(); assert.equal(view.button().element.disabled, true);
    if (action === 'edit') view.edit('fixture-new-key');
    if (action === 'clear') view.clear();
    if (action === 'reset') view.owner.reset();
    if (action === 'save') await view.owner.saveAll();
    await flush(); assert.equal(view.button().element.disabled, false); assert.equal(view.state.text, '');
    finish({ok: true, balance: {available_points: 999, pending_points: 0, used_points: 0, cost_points: 1}}); await request; await flush();
    assert.equal(view.state.text, '');
  }
});

test('非法积分响应明确报错，缺字段显示未知；服务地址草稿需保存后查询', async () => {
  let count = 0; const view = createView(() => ++count === 1 ? {ok: true, balance: {available_points: -1}} : {ok: true, balance: {}});
  await view.query(); await flush(); assert.match(view.status().text(), /积分响应无效/);
  await view.query(); await flush(); assert.match(view.status().text(), /可用 未知.*预占 未知.*已用 未知.*每单 未知/);
  view.owner.setField(base, 'https://draft.example.test'); await view.query(); await flush();
  assert.match(view.status().text(), /先保存.*服务地址/); assert.equal(count, 2);
  assert.equal(view.owner.readField(base), 'https://draft.example.test'); assert.equal(view.owner.isDirty(base), true);
});

test('独立支付实际平台错误码显示对应中文原因，不显示异常原文', async () => {
  for (const [code, message] of [['UNAUTHENTICATED', /Key 无效/], ['EMPLOYER_PENDING', /账号尚未就绪/],
    ['PASSWORD_CHANGE_REQUIRED', /修改密码/], ['RATE_LIMITED', /过于频繁/]]) {
    const view = createView(() => {throw {code, message: 'fixture-private-upstream'};});
    await view.query(); await flush(); assert.match(view.status().text(), message); assert.doesNotMatch(view.status().text(), /fixture-private-upstream/);
  }
});
