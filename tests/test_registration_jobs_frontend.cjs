const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/jobs.js'), 'utf8');
function functionSource(name) {
  const declaration = `function ${name}(`;
  const index = source.indexOf(declaration);
  if (index < 0) return '';
  const start = source.slice(Math.max(0, index - 6), index) === 'async ' ? index - 6 : index;
  return source.slice(start, source.indexOf('\n}', index) + 2);
}

test('注册请求使用配置中的 driver 并在结果提示中显示协议名称', async () => {
  const requests = [];
  const warning = {innerHTML: ''};
  const countInput = {value: '50'};
  const workersInput = {value: '3'};
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
      {value: 'protocol', label: '本地优化 Protocol'},
      {value: 'protocol_oss', label: '开源 Protocol'},
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
        registration_driver: 'protocol_oss',
        submitted: 50,
        workers: 3,
      };
    },
  };
  vm.createContext(context);
  vm.runInContext([
    functionSource('registrationEmailSourceLabel'),
    functionSource('registrationDriverLabel'),
    functionSource('startRegistrationFromInputs'),
  ].join('\n'), context);

  await context.startRegistrationFromInputs(
    countInput,
    workersInput,
    {value: 'outlook'},
    startButton,
  );

  assert.equal(requests.length, 1);
  assert.equal(Object.hasOwn(requests[0], 'registration_driver'), false);
  assert.match(warning.innerHTML, /开源 Protocol/);
  assert.equal(batchId, 'batch-fixture');
});
