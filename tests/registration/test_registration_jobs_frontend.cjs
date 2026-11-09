const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/registration/page.js'), 'utf8');
function functionSource(name) {
  const declaration = `function ${name}(`;
  const index = source.indexOf(declaration);
  if (index < 0) return '';
  const start = source.slice(Math.max(0, index - 6), index) === 'async ' ? index - 6 : index;
  return source.slice(start, source.indexOf('\n}', index) + 2);
}

function registrationStartFixture({workers = '3', responseWorkers = 3} = {}) {
  const requests = [];
  const warning = {innerHTML: ''};
  const countInput = {value: '50'};
  const workersInput = {
    value: workers,
    attributes: {},
    focused: false,
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    focus() { this.focused = true; },
  };
  const startButton = {disabled: false};
  let batchId = '';
  const context = {
    $: selector => selector === '#regDebugV2'
      ? {checked: false}
      : selector === '#regWarnV2'
        ? warning
        : selector === '#regCountV2'
          ? countInput
          : selector === '#regWorkersV2'
            ? workersInput
            : {disabled: false},
    JOB_STATUS_COUNTS: {active: 0},
    REGISTRATION_EMAIL_SOURCES: [{value: 'outlook', label: 'Outlook 邮箱池'}],
    REGISTRATION_DRIVERS: [
      {value: 'protocol_oss_2', label: '开源protocol-2'},
      {value: 'roxy', label: '本地 Roxy'},
    ],
    esc: value => String(value),
    setJobProgressBatch(value) { batchId = value; },
    refreshJobs() {},
    setTimeout(callback) { callback(); },
    api: async (_url, options) => {
      requests.push(JSON.parse(options.body));
      return {
        jobs: [{batch_id: 'batch-fixture'}],
        email_source: 'outlook',
        registration_driver: 'protocol_oss_2',
        submitted: 50,
        workers: responseWorkers,
      };
    },
  };
  vm.createContext(context);
  vm.runInContext([
    functionSource('registrationEmailSourceLabel'),
    functionSource('registrationDriverLabel'),
    functionSource('startRegistrationFromInputs'),
  ].join('\n'), context);
  return {context, requests, warning, countInput, workersInput, startButton, get batchId() { return batchId; }};
}

test('注册请求使用配置中的 driver 并在结果提示中显示协议名称', async () => {
  const fixture = registrationStartFixture();
  const {context, requests, warning, countInput, workersInput, startButton} = fixture;

  await context.startRegistrationFromInputs(
    countInput,
    workersInput,
    {value: 'outlook'},
    startButton,
  );

  assert.equal(requests.length, 1);
  assert.equal(Object.hasOwn(requests[0], 'registration_driver'), false);
  assert.match(warning.innerHTML, /开源protocol-2/);
  assert.equal(fixture.batchId, 'batch-fixture');
});

test('注册并发 30、50、100 按原值提交，不再截断为 16', async () => {
  for (const workers of [30, 50, 100]) {
    const fixture = registrationStartFixture({workers: String(workers), responseWorkers: workers});
    await fixture.context.startRegistrationFromInputs(
      fixture.countInput, fixture.workersInput, {value: 'outlook'}, fixture.startButton,
    );
    assert.equal(fixture.requests.length, 1);
    assert.equal(fixture.requests[0].workers, workers);
    assert.equal(fixture.workersInput.value, String(workers));
    assert.match(fixture.warning.innerHTML, new RegExp(`并发 ${workers}`));
  }
});

test('无效注册并发不会发起 API 请求，保留输入并聚焦错误字段', async () => {
  for (const workers of ['0', '-1', '1.5', '非数字', '30abc', '9007199254740992', 'Infinity', '']) {
    const fixture = registrationStartFixture({workers});
    await fixture.context.startRegistrationFromInputs(
      fixture.countInput, fixture.workersInput, {value: 'outlook'}, fixture.startButton,
    );
    assert.equal(fixture.requests.length, 0, workers);
    assert.equal(fixture.workersInput.value, workers);
    assert.equal(fixture.workersInput.focused, true);
    assert.equal(fixture.workersInput.attributes['aria-invalid'], 'true');
    assert.equal(fixture.startButton.disabled, false);
    assert.match(fixture.warning.innerHTML, /正整数/);
  }
});

test('注册提交后按服务端返回并发回显，并清除已纠正的输入错误', async () => {
  const fixture = registrationStartFixture({workers: '0', responseWorkers: 50});
  await fixture.context.startRegistrationFromInputs(
    fixture.countInput, fixture.workersInput, {value: 'outlook'}, fixture.startButton,
  );
  fixture.workersInput.value = '100';
  await fixture.context.startRegistrationFromInputs(
    fixture.countInput, fixture.workersInput, {value: 'outlook'}, fixture.startButton,
  );
  assert.equal(fixture.requests.length, 1);
  assert.equal(fixture.requests[0].workers, 100);
  assert.equal(fixture.workersInput.value, '50');
  assert.match(fixture.warning.innerHTML, /并发 50/);
  assert.equal(Object.hasOwn(fixture.workersInput.attributes, 'aria-invalid'), false);
});

test('注册并发输入保留正整数步长且无固定上限', () => {
  const html = fs.readFileSync(path.join(__dirname, '../../webui/templates/index.html'), 'utf8');
  const input = html.match(/<input\b[^>]*\bid="regWorkersV2"[^>]*>/)?.[0] || '';
  assert.match(input, /\bmin="1"/);
  assert.match(input, /\bstep="1"/);
  assert.doesNotMatch(input, /\bmax=/);
});

test('注册任务可在选项尚未加载时区分开源和本地 Roxy', () => {
  const context = {REGISTRATION_DRIVERS: []};
  vm.createContext(context);
  vm.runInContext(functionSource('registrationDriverLabel'), context);
  assert.equal(context.registrationDriverLabel('roxy_oss'), '开源 Roxy（历史）');
  assert.equal(context.registrationDriverLabel('roxy'), '本地 Roxy');
  assert.equal(context.registrationDriverLabel('protocol_oss_2'), '开源protocol-2');
});
