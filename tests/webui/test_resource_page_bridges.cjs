const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const rootDir = path.resolve(__dirname, '../..');
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
function setup(kind) {
  const email = kind === 'email', imports = [], mounts = [], calls = [], notices = [];
  const pending = deferred(), tabClasses = new Set(), elements = new Map();
  const root = {dataset:{moduleUrl:'/synthetic.js', styleUrl:'/synthetic.css'}, children:[],
    replaceChildren() {this.children = [];}, append(...nodes) {this.children.push(...nodes);}};
  const api = {
    setView: value => calls.push(['view', value]),
    setVisible: value => calls.push(['visible', value]),
    closeDialogs: () => calls.push(['close']),
    closeDetail: () => calls.push(['close']),
    destroy: () => calls.push(['destroy']),
  };
  for (const method of ['load', 'refreshOverview', 'refreshInventory', 'refreshHistory',
    'refreshDerivationSummary', 'openImport', 'openButlerImport']) {
    api[method] = async value => {calls.push([method, value]);};
  }
  const tab = {dataset:{moduleView:email ? 'overview' : 'pool'}, classList:{contains:value => tabClasses.has(value)}};
  elements.set(email ? 'email-page-root' : 'proxy-page-root', root);
  elements.set(email ? 'tab-outlook' : 'tab-proxy-traffic', tab);
  elements.set('task-center-style', {});
  const context = {window:null, Promise, document:{hidden:false, getElementById:id => elements.get(id),
    head:{append() {}}, createElement() {return {setAttribute(key, value) {this[key] = value;}, addEventListener(event, fn) {this[event] = fn;}};}},
    showToast: message => notices.push(message), markViewReady() {}, facetLabel: (_group, value) => value,
    copyText: async () => {}, confirm: () => true, setModuleView: (...args) => calls.push(['navigate', ...args]),
    invalidateApiCache: value => calls.push(['invalidate', value]),
    loadCapabilities: async () => {}, loadRegistrationEmailSources: async () => {}, loadSummary: async () => {},
    loadResourceModule: async url => {imports.push(url); return pending.promise;}};
  context.window = context;
  const file = email ? 'webui/static/js/pages/email/page.js' : 'webui/static/js/pages/proxy/traffic.js';
  const source = fs.readFileSync(path.join(rootDir, file), 'utf8');
  vm.runInNewContext(source.replace('import(root.dataset.moduleUrl)', 'loadResourceModule(root.dataset.moduleUrl)'), context);
  return {bridge:context[email ? 'EmailPage' : 'ProxyTraffic'], calls, notices, imports, mounts, root, tabClasses,
    resolve() {pending.resolve({[email ? 'mountEmail' : 'mountProxyTraffic']:(node, deps) => {
      mounts.push({node, deps}); return api;
    }});},
    reject:pending.reject, api, context};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('resource modules have one mount each and no active legacy state or poller', () => {
  const template = fs.readFileSync(path.join(rootDir, 'webui/templates/index.html'), 'utf8');
  const common = fs.readFileSync(path.join(rootDir, 'webui/static/js/shared/common.js'), 'utf8');
  for (const name of ['email', 'proxy']) assert.equal((template.match(new RegExp(`id="${name}-page-root"`, 'g')) || []).length, 1);
  for (const oldId of ['outlookBodyV2', 'emailDerivationBody', 'proxyTrafficHistoryBody', 'butlerImportModal']) {
    assert.equal(template.includes(`id="${oldId}"`), false);
  }
  assert.equal(template.includes("filename='js/pages/email/butler-import.js'"), false);
  assert.equal(/\b(?:OUTLOOK_SELECTED|OUTLOOK_TOTAL|EMAIL_DERIVATION_VIEW)\b/.test(common), false);
  assert.match(common, /EmailPage\?\.setVisible\(tab === 'outlook'\)/);
  assert.match(common, /ProxyTraffic\?\.setVisible\(tab === 'proxy-traffic'\)/);
});

for (const kind of ['email', 'proxy']) {
  test(`${kind}: hidden refresh does not import; repeated activation shares one owner`, async () => {
    const h = setup(kind), refresh = kind === 'email' ? 'refreshInventory' : 'load';
    await h.bridge[refresh]();
    assert.equal(h.imports.length, 0);
    const a = h.bridge.setVisible(true), b = h.bridge.setVisible(true);
    h.resolve(); await Promise.all([a, b]);
    assert.equal(h.imports.length, 1); assert.equal(h.mounts.length, 1);
    assert.equal(h.calls.filter(call => call[0] === 'visible' && call[1]).length, 1);
  });
  test(`${kind}: leaving during lazy import delivers the latest view and stays hidden`, async () => {
    const h = setup(kind), opening = h.bridge.setVisible(true);
    h.bridge.setView(kind === 'email' ? 'derivations' : 'records');
    h.tabClasses.add('hidden'); await h.bridge.setVisible(false);
    h.resolve(); await opening;
    assert.equal(h.mounts.length, 1);
    assert.equal(h.mounts[0].deps.visible, false);
    assert.equal(h.calls.some(call => call[0] === 'visible' && call[1]), false);
    assert.deepEqual(h.calls.filter(call => call[0] === 'view').at(-1),
      ['view', kind === 'email' ? 'derivations' : 'records']);
  });
  test(`${kind}: document visibility is handled by the owner without losing host activation`, async () => {
    const h = setup(kind);
    h.context.document.hidden = true;
    const opening = h.bridge.setVisible(true);h.resolve();await opening;
    assert.equal(h.calls.some(call => call[0] === 'visible' && call[1]), true);
  });
  test(`${kind}: failed import shows a working retry and does not retain the rejected promise`, async () => {
    const h = setup(kind), opening = h.bridge.setVisible(true);
    h.reject(new Error('synthetic load failure')); await opening;
    assert.equal(h.root.children[0].getAttribute?.('role') || h.root.children[0].role, 'alert');
    assert.match(h.root.children[0].textContent, /synthetic load failure/);
    assert.equal(h.root.children[1].textContent, '重新加载');
    let mounted = 0;
    h.context.loadResourceModule = async () => ({[kind === 'email' ? 'mountEmail' : 'mountProxyTraffic']:() => {mounted++; return h.api;}});
    h.root.children[1].click(); await tick();
    assert.equal(mounted, 1);
  });
}

test('email: a stale modal open cannot reopen after navigation during import', async () => {
  const h = setup('email'), activate = h.bridge.setVisible(true), opening = h.bridge.openImport('generic_api');
  await h.bridge.setVisible(false); h.resolve(); await Promise.all([activate, opening]);
  assert.equal(h.calls.some(call => call[0] === 'openImport'), false);
});

test('email: shared refresh failure remains distinguishable from an accepted inventory change', async () => {
  const h = setup('email'), opening = h.bridge.setVisible(true); h.resolve(); await opening;
  const failure = new Error('shared refresh failed');
  h.context.loadSummary = async () => {throw failure;};
  await assert.rejects(h.mounts[0].deps.onInventoryChanged(), /shared refresh failed/);
  assert.equal(h.calls.some(call => call[0] === 'navigate'), false);
});

test('email: clipboard failure rejects so the owner cannot display a false success', async () => {
  const h = setup('email'), opening = h.bridge.setVisible(true);h.resolve();await opening;
  h.context.copyText = async () => false;
  await assert.rejects(h.mounts[0].deps.clipboard('synthetic'), /复制失败/);
});
