const assert = require('node:assert/strict');
const test = require('node:test');
const {harness, field, createConfigView, cleanup, flush} = require('./vue_fixture.cjs');
test.afterEach(cleanup);
const f = (key, value = 3) => field(key, '并发控制', {value, type: 'int', help: '填写正整数', range: {min: 1}});
const snapshot = () => ({ok: true, scope: '测试部署', policy_revision: 'fixture', observed_at: '2026-11-05T01:00:00Z', global: {limit: 4, occupied: 10, reserved: 1, executing: 7, cleaning: 1, debug_hold: 1, draining: true}, types: []});
async function view(dependencies = {}) {
  const result = createConfigView([f('GLOBAL_TASK_WORKERS'), f('ACCOUNT_PLAN_CHECK_WORKERS'), f('CONCURRENCY_POLICY_REVISION', 1)], {request: async url => url.includes('preview') ? {ok: true, migration_required: false, proposed_values: {}} : url.includes('extract-link/types') ? {items: [{type: 'plus'}]} : snapshot(), ...dependencies});
  await result.open('并发控制'); await flush(); return result;
}
test('并发字段正整数与可定位错误约束保持，内部策略版本不作为输入', async () => {
  const v = await view(); const control = v.control('GLOBAL_TASK_WORKERS');
  assert.equal(v.wrapper.find(`label[for="${control.attributes('id')}"]`).exists(), true);
  assert.equal(control.attributes('min'), '1'); assert.equal(control.attributes('step'), '1'); assert.equal(control.attributes('max'), undefined);
  assert.equal(v.wrapper.find('[data-key="CONCURRENCY_POLICY_REVISION"]').exists(), false);
  assert.match(control.attributes('aria-describedby'), /-help .*?-error/);
  assert.match(v.wrapper.text(), /复用父任务许可/); assert.match(v.wrapper.text(), /XXSYUN 未结束订单名额/);
});
test('状态轮询保持草稿输入DOM与焦点，并显示缩容占用分项', async () => {
  const v = await view(); const input = v.control('GLOBAL_TASK_WORKERS'); await input.setValue('9'); input.element.focus(); const element = input.element;
  await v.actions.refreshConcurrency(); await flush();
  assert.equal(v.owner.readField('GLOBAL_TASK_WORKERS'), '9'); assert.equal(v.control('GLOBAL_TASK_WORKERS').element, element); assert.equal(harness.document.activeElement, element);
  assert.match(v.wrapper.text(), /10 \/ 4，等待现有任务结束/); assert.match(v.wrapper.text(), /预约 1 · 执行 7 · 清理 1 · 调试保留 1/);
});
test('部署范围与观察时间沿用浏览器本地时区格式', async () => {
  const v = await view(); const formatted = new Intl.DateTimeFormat('zh-CN', {year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false}).format(new Date('2026-11-05T01:00:00Z'));
  assert.match(v.wrapper.text(), /部署范围 测试部署/); assert.equal(v.wrapper.text().includes(`观察时间 ${formatted}`), true);
});
test('隐藏页面与文档停止周期读取，返回可见页面立即刷新', async t => {
  t.mock.timers.enable({apis: ['setTimeout']}); const v = await view(); const calls = () => v.requests.filter(item => item.url.startsWith('/api/operations/concurrency')).length;
  const initial = calls(); t.mock.timers.tick(3000); await flush(); assert.equal(calls(), initial + 1);
  v.actions.setForeground(false); const hidden = calls(); t.mock.timers.tick(9000); await flush(); assert.equal(calls(), hidden);
  v.actions.setForeground(true); await flush(); assert.equal(calls(), hidden + 1);
  await v.wrapper.setProps({active: false}); v.actions.setForeground(false); v.actions.setForeground(true); t.mock.timers.tick(9000); await flush(); assert.equal(calls(), hidden + 1);
  await v.wrapper.setProps({active: true}); await flush(); assert.equal(calls(), hidden + 2);
});
test('隐藏前旧响应不覆盖原状态', async () => {
  const v = await view(); let resolve; v.dependencies.request = url => url.startsWith('/api/operations/concurrency') ? new Promise(done => {resolve = done;}) : Promise.resolve({ok: true});
  const pending = v.actions.refreshConcurrency(); await flush(); await v.wrapper.setProps({active: false}); resolve({ok: true, global: {occupied: 999}}); await pending;
  assert.equal(v.actions.states.concurrency.snapshot.global.occupied, 10);
});
test('迁移建议只填草稿并保留已编辑值，完整策略版本一并提交', async () => {
  const v = await view(); v.owner.setField('GLOBAL_TASK_WORKERS', '12'); v.actions.states.concurrencyPreview.snapshot = {proposed_values: {GLOBAL_TASK_WORKERS: 3, ACCOUNT_PLAN_CHECK_WORKERS: 8, CONCURRENCY_POLICY_REVISION: 1}};
  v.actions.applyConcurrencyPreview(); assert.equal(v.owner.readField('GLOBAL_TASK_WORKERS'), '12'); assert.equal(v.owner.readField('ACCOUNT_PLAN_CHECK_WORKERS'), 8); assert.equal(v.saves.length, 0);
  await flush(); await v.save(); assert.deepEqual(v.saves, [{GLOBAL_TASK_WORKERS: '12', ACCOUNT_PLAN_CHECK_WORKERS: 8, CONCURRENCY_POLICY_REVISION: 1}]);
});
test('迁移默认值再次编辑相同数值后仍完整保留首次提交键', async () => {
  const v = await view(); v.actions.states.concurrencyPreview.snapshot = {migration_required: true, proposed_values: {GLOBAL_TASK_WORKERS: 3, ACCOUNT_PLAN_CHECK_WORKERS: 3, CONCURRENCY_POLICY_REVISION: 1}};
  v.actions.applyConcurrencyPreview(); v.owner.setField('GLOBAL_TASK_WORKERS', 4); v.owner.setField('GLOBAL_TASK_WORKERS', 3); await v.control('ACCOUNT_PLAN_CHECK_WORKERS').setValue('3');
  await v.save(); assert.deepEqual(v.saves, [{GLOBAL_TASK_WORKERS: 3, ACCOUNT_PLAN_CHECK_WORKERS: '3', CONCURRENCY_POLICY_REVISION: 1}]);
});
test('数字不被截断，无效保存保留草稿并定位真实错误输入', async () => {
  const v = await view();
  for (const value of ['', '0', '-1', '1.5', '1e3']) {v.owner.setField('GLOBAL_TASK_WORKERS', value); assert.equal((await v.owner.saveAll()).status, 'validation-error');}
  await flush(); assert.equal(v.saves.length, 0); assert.equal(v.owner.readField('GLOBAL_TASK_WORKERS'), '1e3');
  assert.ok(v.owner.fieldErrors.GLOBAL_TASK_WORKERS); assert.equal(harness.document.activeElement, v.control('GLOBAL_TASK_WORKERS').element);
  const summary = v.wrapper.get('.config-vue-error-summary'); assert.equal(summary.attributes('role'), 'alert'); await summary.get('button').trigger('click'); await flush(); assert.equal(harness.document.activeElement, v.control('GLOBAL_TASK_WORKERS').element);
  for (const value of ['1', '51', '1000000']) {v.owner.setField('GLOBAL_TASK_WORKERS', value); assert.equal((await v.owner.saveAll()).status, 'saved');}
});
test('等待原因保留容量证据和全部既有分类，未知分类明确待核验', async () => {
  const v = await view(); v.actions.states.concurrency.snapshot = {...snapshot(), types: [{key: 'plan_check', label: '查询套餐', blocked_by: [{code: 'global_capacity', occupied: 10, limit: 10}, 'account_busy', 'not_due', 'fairness_turn', 'executor_capacity', 'resource_capacity', 'scheduler_store_unavailable', 'permit_owner_lost', 'execution_active', 'future_reason']}]}; await flush();
  for (const label of ['等待全局空位（10/10）', '账号正由其他任务使用', '等待下次平台查询', '等待公平调度轮次', '等待执行承载空位', '等待业务资源空位', '调度存储暂不可用', '执行许可归属已变化', '上一执行仍在退出或清理', '调度等待原因未登记（future_reason）']) assert.equal(v.wrapper.text().includes(label), true, label);
});
test('定位任务通过明确筛选参数，保留注册入口和全部任务类型', async () => {
  const opened = []; const v = await view({onNavigateTasks: target => opened.push(target)});
  v.actions.states.concurrency.snapshot = {types: [{config_key: 'ACCOUNT_SETUP_WORKERS', key: 'account_setup', task_types: ['password_setup', 'twofa_setup', 'password_setup']}]};
  v.actions.locateConcurrencyTasks('ACCOUNT_SETUP_WORKERS'); assert.deepEqual(opened[0], {types: ['password_setup', 'twofa_setup']});
  v.actions.locateConcurrencyTasks('GLOBAL_TASK_WORKERS'); assert.deepEqual(opened.at(-1), {types: []});
  v.actions.locateConcurrencyTasks('REGISTRATION_WORKERS'); assert.deepEqual(opened.at(-1), {registration: true});
});
