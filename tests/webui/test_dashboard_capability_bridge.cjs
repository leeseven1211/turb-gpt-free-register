const test = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const js = path.resolve(__dirname, '../../webui/static/js');
const source = file => readFileSync(path.join(js, file), 'utf8');

test('总览只加入启动时仍在进行的能力请求，全局刷新独立生效', async () => {
  const common = source('shared/common.js');
  const requests = [];
  const updates = [];
  const context = vm.createContext({
    document: {addEventListener() {}},
    fetch: () => new Promise(resolve => requests.push(resolve)),
    window: {createPageBridge: options => options, AccountsPage: {setCapabilities: value => updates.push(value)}},
    applyFeatureGates() {},
  });
  vm.runInContext(`
    const API_INFLIGHT = new Map();
    const API_CACHE = new Map();
    let CAPABILITIES;
    ${common.slice(common.indexOf('async function api('), common.indexOf('function markViewReady('))}
    ${common.slice(common.indexOf('async function loadCapabilities('), common.indexOf("document.addEventListener('click', (event)"))}
  `, context);
  vm.runInContext(source('pages/dashboard/page.js'), context);
  const {pendingCapabilities} = context.window.DashboardPage.dependencies();
  assert.equal(pendingCapabilities(), undefined);

  const bootstrap = context.loadCapabilities();
  const joined = pendingCapabilities();
  assert.ok(joined);
  assert.equal(requests.length, 1);
  const features = {register: {enabled: true}};
  requests[0]({ok: true, json: async () => ({ok: true, features})});
  await bootstrap;
  assert.deepEqual(await joined, {ok: true, features});
  assert.deepEqual(updates, [features]);
  assert.equal(pendingCapabilities(), undefined);

  context.invalidateApiCache('/api/capabilities');
  const failed = context.loadCapabilities();
  const failing = pendingCapabilities();
  requests[1]({ok: false, status: 503, json: async () => ({error: '临时不可用'})});
  await assert.rejects(failing, /临时不可用/);
  await failed;
  assert.equal(pendingCapabilities(), undefined);
  const retry = context.loadCapabilities();
  assert.equal(requests.length, 3);
  requests[2]({ok: true, json: async () => ({ok: true, features})});
  await retry;
  assert.deepEqual(updates, [features, features]);
});
