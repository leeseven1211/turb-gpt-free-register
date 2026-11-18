const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const {createRequire} = require('node:module');
const {JSDOM} = createRequire(path.resolve(__dirname, '../../frontend/package.json'))('jsdom');

const bridgeScript = fs.readFileSync(path.resolve(__dirname, '../../webui/static/js/shared/page-bridge.js'), 'utf8');

function fixture(t) {
  const dom = new JSDOM('<section id="tab"><div id="root" data-module-url="/example.js"></div></section>', {
    runScripts: 'outside-only',
  });
  t.after(() => dom.window.close());
  dom.window.eval(bridgeScript);
  const pending = Promise.withResolvers();
  const mounted = {setVisible: t.mock.fn(), setView: t.mock.fn(), openDetail: t.mock.fn()};
  const mount = t.mock.fn(() => mounted);
  const loadModule = t.mock.fn(() => pending.promise);
  const bridge = dom.window.createPageBridge({rootId: 'root', tabId: 'tab', mount: 'mount', initialView: 'list', loadModule});
  return {bridge, mounted, mount, loadModule, pending, root: dom.window.document.getElementById('root')};
}

test('hidden reads stay idle and concurrent activation mounts a page once', async t => {
  const {bridge, mounted, mount, loadModule, pending} = fixture(t);
  await bridge.read('openDetail');
  assert.equal(loadModule.mock.callCount(), 0);
  const first = bridge.setVisible(true);
  const second = bridge.setVisible(true);
  pending.resolve({mount});
  await Promise.all([first, second]);
  assert.equal(loadModule.mock.callCount(), 1);
  assert.equal(mount.mock.callCount(), 1);
  assert.equal(mount.mock.calls[0].arguments[1].visible, false);
  assert.deepEqual(mounted.setVisible.mock.calls.map(call => call.arguments[0]), [true]);
});

test('returning to a page during import discards the old detail request', async t => {
  const {bridge, mounted, mount, pending} = fixture(t);
  const first = bridge.setVisible(true);
  const detail = bridge.invoke('openDetail', ['first']);
  await bridge.setVisible(false);
  bridge.setView('other');
  const second = bridge.setVisible(true);
  pending.resolve({mount});
  await Promise.all([first, second, detail]);
  assert.equal(mounted.openDetail.mock.callCount(), 0);
  assert.deepEqual(mounted.setView.mock.calls.map(call => call.arguments[0]), ['other']);
  assert.deepEqual(mounted.setVisible.mock.calls.map(call => call.arguments[0]), [true]);
});

test('closing a dialog cancels its pending request even while the page is hidden', async t => {
  const {bridge, mounted, mount, pending} = fixture(t);
  const dialog = bridge.invoke('openDetail', ['first'], {hidden: true});
  bridge.closeDialogs();
  pending.resolve({mount});
  await dialog;
  assert.equal(mounted.openDetail.mock.callCount(), 0);
  assert.equal(mounted.setVisible.mock.callCount(), 0);
});

test('a failed import offers a working retry', async t => {
  const {bridge, mount, loadModule, pending, root} = fixture(t);
  const first = bridge.setVisible(true);
  pending.reject(new Error('chunk unavailable'));
  await first;
  assert.match(root.querySelector('[role="alert"]').textContent, /chunk unavailable/);
  const retry = root.querySelector('button');
  assert.equal(retry.textContent, '重新加载');
  loadModule.mock.mockImplementation(() => Promise.resolve({mount}));
  retry.click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(loadModule.mock.callCount(), 2);
  assert.equal(mount.mock.callCount(), 1);
});

test('a rejected page action reaches its caller and is invoked only once', async t => {
  const {bridge, mounted, mount, pending} = fixture(t);
  pending.resolve({mount});
  await bridge.setVisible(true);
  mounted.save = t.mock.fn(async () => { throw new Error('unknown result'); });
  await assert.rejects(bridge.invoke('save'), /unknown result/);
  assert.equal(mounted.save.mock.callCount(), 1);
});
