const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const fullSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/email.js'), 'utf8');
const source = fullSource.slice(fullSource.indexOf('function renderButlerLeases('), fullSource.indexOf('async function loadOutlook('));
const IDS = ['fb4ae841-1745-4450-ae65-a73ec0f28f99', 'fd431849-c753-428f-97fe-7ed4cd0f96ef'];

function createView(storage = new Map()) {
  const nodes = new Map(), calls = [], toasts = [];
  const element = id => {
    if (!nodes.has(id)) nodes.set(id, {disabled: false, textContent: '', handlers: {}, addEventListener(name, handler) { this.handlers[name] = handler; }});
    return nodes.get(id);
  };
  let nextId = 0;
  const context = {
    $: selector => element(selector.slice(1)),
    sessionStorage: {
      getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    crypto: {randomUUID: () => IDS[nextId++]},
    showToast: message => toasts.push(message),
    api: async (url, options) => { calls.push({url, body: JSON.parse(options.body)}); return {ok: true, item: {email: 'fixture@example.test'}}; },
  };
  vm.createContext(context);
  vm.runInContext(source + '\nloadMailResources = async () => {};', context);
  const button = element('btnLeaseButlerMailbox');
  return {context, storage, calls, toasts, button, click: () => button.handlers.click({currentTarget: button})};
}

test('首次手动领取在发送前保存意图，成功后清除，下一次领取使用新意图', async () => {
  const view = createView();
  let savedDuringRequest;
  view.context.api = async (url, options) => {
    const body = JSON.parse(options.body);
    savedDuringRequest = [...view.storage.values()];
    view.calls.push({url, body});
    return {ok: true, item: {email: 'fixture@example.test'}};
  };
  await view.click();
  assert.equal(view.calls[0].body.request_id, IDS[0]);
  assert.deepEqual(savedDuringRequest, [IDS[0]]);
  assert.equal(view.storage.size, 0);
  await view.click();
  assert.equal(view.calls[1].body.request_id, IDS[1]);
  assert.equal(view.button.disabled, false);
});

test('结果未知与网络中断保留原意图，刷新后继续原请求', async () => {
  const view = createView();
  view.context.api = async (url, options) => {
    view.calls.push(JSON.parse(options.body));
    throw Object.assign(new Error('fixture unknown'), {code: 'request_unknown'});
  };
  await view.click();
  assert.deepEqual([...view.storage.values()], [IDS[0]]);
  assert.match(view.toasts.at(-1), /原.*意图|原.*请求/);
  const refreshed = createView(view.storage);
  refreshed.context.api = async (url, options) => {
    refreshed.calls.push(JSON.parse(options.body));
    throw new TypeError('network interrupted');
  };
  await refreshed.click();
  assert.equal(refreshed.calls[0].request_id, IDS[0]);
  assert.deepEqual([...view.storage.values()], [IDS[0]]);
  refreshed.context.api = async (url, options) => {
    refreshed.calls.push(JSON.parse(options.body));
    return {ok: true, item: {email: 'fixture@example.test'}};
  };
  await refreshed.click();
  assert.equal(refreshed.calls[1].request_id, IDS[0]);
  assert.equal(view.storage.size, 0);
});

test('重复点击不能在前一个领取尚未返回时重复发送', async () => {
  const view = createView();
  let finish;
  view.context.api = async (url, options) => {
    view.calls.push(JSON.parse(options.body));
    return new Promise(resolve => { finish = resolve; });
  };
  const pending = view.click();
  const repeated = view.click();
  assert.equal(view.calls.length, 1);
  finish({ok: true, item: {email: 'fixture@example.test'}});
  await Promise.all([pending, repeated]);
});

test('无法读取或持久保存领取意图时禁止提交', async () => {
  for (const method of ['getItem', 'setItem']) {
    const view = createView();
    view.context.sessionStorage[method] = () => { throw new Error('storage blocked'); };
    await view.click();
    assert.equal(view.calls.length, 0);
    assert.match(view.toasts.at(-1), /无法保存领取意图/);
    assert.equal(view.button.disabled, false);
  }
});

test('服务端未明确成功时保留意图并显示失败', async () => {
  const view = createView();
  view.context.api = async () => ({ok: false, request_unknown: true, code: 'request_unknown', error: 'fixture unknown'});
  await view.click();
  assert.deepEqual([...view.storage.values()], [IDS[0]]);
  assert.doesNotMatch(view.toasts.at(-1), /^已租用/);
});

test('普通 HTTP 页面缺少 randomUUID 时仍使用安全随机 UUID 并先持久化', async () => {
  const view = createView();
  delete view.context.crypto.randomUUID;
  view.context.crypto.getRandomValues = bytes => { bytes.fill(17); return bytes; };
  await view.click();
  assert.equal(view.calls.length, 1);
  assert.match(view.calls[0].body.request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('存储静默丢弃写入时禁止发号', async () => {
  const view = createView();
  view.context.sessionStorage.setItem = () => {};
  await view.click();
  assert.equal(view.calls.length, 0);
  assert.match(view.toasts.at(-1), /无法保存领取意图/);
});
