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

for (const name of ['retryBatchFailedJobs', 'retrySelectedJobs', 'retryJob']) {
  for (const enabled of [true, false]) {
    test(`${name} 按当前勾选发送调试设置 ${enabled}`, async () => {
      const requests = [];
      const job = {id: 21, status: 'failed', retryable: true, retry_action: 'registration_resume'};
      const context = {
        $: selector => selector === '#regDebugV2' ? {checked: enabled} : {disabled: false},
        currentBatchJobs: () => [job], JOBS: [job], JOB_SELECTED: new Set([21]),
        confirm: () => true, showToast() {}, refreshJobs() {}, setJobProgressBatch() {}, updateJobsSelectionUi() {},
        api: async (url, options) => {
          requests.push({url, body: JSON.parse(options.body)});
          return {ok: true, started_count: 1};
        },
      };
      vm.createContext(context);
      vm.runInContext(`${functionSource('registrationRetryPayload')}\n${functionSource(name)}`, context);
      await context[name](21, {disabled: false});
      assert.equal(requests.length, 1);
      assert.equal(requests[0].body.debug_enabled, enabled);
      if (name !== 'retryJob') assert.deepEqual(requests[0].body.job_ids, [21]);
    });
  }
}
