const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/operations/page.js'), 'utf8');
const context = vm.createContext({esc: text => String(text).replaceAll('<', '&lt;').replaceAll('>', '&gt;')});
for (const name of ['accountTaskAdmissionReasons', 'accountTaskAdmissionReasonText', 'accountTaskAdmissionWaitMarkup']) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf('\n}', start);
  vm.runInContext(source.slice(start, end + 2), context);
}

test('只消费服务端原因，不根据前端占用或任务类型推断', () => {
  const unknown = context.accountTaskAdmissionWaitMarkup({status: 'queued', global: {occupied: 10, limit: 10}});
  assert.equal(unknown, '');
  const markup = context.accountTaskAdmissionWaitMarkup({status: 'queued', admission_wait_reasons: [
    {code: 'global_capacity', occupied: 10, limit: 10}, {code: 'account_busy'},
  ]});
  assert.match(markup, /<details/);
  assert.match(markup, /等待全局空位（10\/10）/);
  assert.match(markup, /账号正由其他任务使用/);
});

test('原因仅用于排队展示，执行或业务失败保留原状态', () => {
  for (const status of ['running', 'failed', 'success']) {
    assert.equal(context.accountTaskAdmissionWaitMarkup({status, admission_wait_reason: 'type_capacity'}), '');
  }
  assert.match(context.accountTaskAdmissionWaitMarkup({status: 'queued', admission_wait_reason: 'not_due'}), /等待下次平台查询/);
});

test('新增原因保留证据并待核验，输出转义', () => {
  const markup = context.accountTaskAdmissionWaitMarkup({status: 'queued', admission_wait_reason: '<script>'});
  assert.match(markup, /等待原因待核验/);
  assert.doesNotMatch(markup, /<script>/);
  assert.match(markup, /&lt;script&gt;/);
});
