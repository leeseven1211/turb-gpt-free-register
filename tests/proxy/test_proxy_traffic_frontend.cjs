const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const js = path.join(__dirname, '../../webui/static/js');

test('pending proxy import honors the latest navigation without fetching on hidden mounts', async () => {
  const calls = [], imports = [], styles = [];
  const root = {dataset: {moduleUrl:'/static/proxy/proxy.js?v=sample',styleUrl:'/static/proxy/proxy.css?v=sample'}};
  let hidden = true, finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const context = {document: {
    getElementById: id => id === 'proxy-page-root' ? root : id === 'tab-proxy-traffic' ? {classList:{contains:()=>hidden}} : null,
    createElement: () => ({}), head:{append:style => styles.push(style)},
  }, facetLabel: () => '', showToast: message => assert.fail(message), loadModule: url => { imports.push(url); return pending; }};
  context.window = context;
  vm.runInNewContext(fs.readFileSync(path.join(js, 'shared/page-bridge.js'), 'utf8').replace('import(node.dataset.moduleUrl)', 'loadModule(node.dataset.moduleUrl)'), context);
  vm.runInNewContext(fs.readFileSync(path.join(js, 'pages/proxy/traffic.js'), 'utf8'), context);
  const bridge = context.ProxyTraffic;
  await bridge.setVisible(false);
  assert.deepEqual(imports, []);
  hidden = false;
  bridge.setView('records');
  const opening = bridge.setVisible(true);
  hidden = true;
  await bridge.setVisible(false);
  finish({mountProxyTraffic(node, deps) {
    assert.equal(node, root);
    assert.equal(deps.visible, false);
    return {setView: view => calls.push(view), setVisible: visible => calls.push(visible)};
  }});
  await opening;
  assert.deepEqual(calls, ['records']);
  hidden = false;
  await bridge.setVisible(true);
  bridge.setView('pool');
  await bridge.setVisible(false);
  assert.deepEqual(calls, ['records', true, 'pool', false]);
  assert.deepEqual(imports, [root.dataset.moduleUrl]);
  assert.equal(styles.length, 1);
  assert.equal(styles[0].href, root.dataset.styleUrl);
});
