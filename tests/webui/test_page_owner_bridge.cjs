{
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

}

{
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = () => fs.readFileSync(path.resolve(__dirname, '../../webui/static/js/shared/page-bridge.js'), 'utf8');
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => {resolve = a; reject = b;});
  return {promise, resolve, reject};
}
function harness() {
  const imports = [], mounts = [], calls = [], notices = [], nodes = new Map();
  const root = {dataset: {moduleUrl:'/synthetic.js', styleUrl:'/synthetic.css'}, children:[],
    replaceChildren() {this.children = [];}, append(...nodes) {this.children.push(...nodes);}};
  nodes.set('root', root); nodes.set('tab', {classList: {contains: () => false}});
  const handle = {
    setVisible(value) {calls.push(['visible', value]);},
    setView(value) {calls.push(['view', value]);},
    closeDialogs() {calls.push(['close']);},
    closeDetail(options) {calls.push(['detail-close', options.restoreFocus]);},
    async load(view) {calls.push(['load', view]);},
    async openDetail(id) {calls.push(['detail', id]);},
    async create(payload) {calls.push(['create', payload]); return {accepted: true};},
    destroy() {calls.push(['destroy']);},
  };
  const pending = deferred();
  const context = {window:null, document:{hidden:false, getElementById:id=>nodes.get(id),
    createElement() {return {setAttribute(k,v) {this[k]=v;}, addEventListener(k,fn) {this[k]=fn;}};},
    head:{append(node) {nodes.set(node.id, node);}}}};
  context.window = context;
  vm.runInNewContext(source(), context);
  const bridge = context.createPageBridge({rootId:'root', tabId:'tab', mount:'mountExample',
    initialView:'one', loadModule:async url=>{imports.push(url); return pending.promise;},
    dependencies:()=>({example:true}), notify:error=>notices.push(String(error))});
  return {bridge, handle, imports, mounts, calls, notices, root, context, pending,
    resolve() {pending.resolve({mountExample:(root,deps)=>{mounts.push({root,deps}); return handle;}});}};
}
test('hidden reads do not load, repeated activation mounts/delivers visibility once', async () => {
  const h=harness();
  await h.bridge.read('load');
  assert.equal(h.imports.length,0);
  const a=h.bridge.setVisible(true), b=h.bridge.setVisible(true);
  h.resolve(); await Promise.all([a,b]);
  assert.equal(h.mounts.length,1);
  assert.equal(h.calls.filter(x=>x[0]==='visible'&&x[1]).length,1);
  assert.equal(h.mounts[0].deps.visible,false);
});
test('navigation during import stays hidden and a stale dialog cannot open after A-B-A', async () => {
  const h=harness(), activation=h.bridge.setVisible(true), detail=h.bridge.invoke('openDetail',['9']);
  h.bridge.setView('two'); await h.bridge.setVisible(false);
  const again=h.bridge.setVisible(true);
  h.resolve(); await Promise.all([activation,detail,again]);
  assert.equal(h.calls.some(x=>x[0]==='detail'),false);
  assert.deepEqual(h.calls.filter(x=>x[0]==='view').at(-1),['view','two']);
  assert.equal(h.calls.filter(x=>x[0]==='visible'&&x[1]).length,1);
});
test('close during import invalidates a hidden independent detail', async () => {
  const h=harness(), opening=h.bridge.invoke('openDetail',['9007199254740993'],{hidden:true});
  h.bridge.closeDialogs(); h.resolve(); await opening;
  assert.equal(h.calls.some(x=>x[0]==='detail'),false);
  assert.equal(h.calls.some(x=>x[0]==='visible'&&x[1]),false);
});
test('lazy import failure has visible retry and clears rejected promise', async () => {
  const h=harness(), activation=h.bridge.setVisible(true);
  h.pending.reject(new Error('chunk offline'));await activation;
  assert.equal(h.root.children[0].role,'alert');
  assert.equal(h.root.children[1].textContent,'重新加载');
  assert.equal(h.notices.length,1);
});
test('business errors propagate and writes are not retried by the bridge', async () => {
  const h=harness(), activation=h.bridge.setVisible(true);h.resolve();await activation;
  h.handle.create=async()=>{h.calls.push(['write']);throw new Error('unknown response');};
  await assert.rejects(h.bridge.invoke('create',[{}]),/unknown response/);
  assert.equal(h.calls.filter(x=>x[0]==='write').length,1);
});
test('load and closeDetail compatibility calls keep a hidden page unmounted', async () => {
  const h=harness();
  await h.bridge.load('history');
  h.bridge.closeDetail();
  assert.equal(h.imports.length,0);
  assert.deepEqual(h.calls,[]);
});
test('closeDetail invalidates a pending detail without starting another mount', async () => {
  const h=harness(), activation=h.bridge.setVisible(true), detail=h.bridge.invoke('openDetail',['9']);
  h.bridge.closeDetail({restoreFocus:false});
  h.resolve(); await Promise.all([activation,detail]);
  assert.equal(h.imports.length,1);
  assert.equal(h.mounts.length,1);
  assert.equal(h.calls.some(call=>call[0]==='detail'),false);
  assert.equal(h.calls.some(call=>call[0]==='detail-close'),false);
});
test('load forwards its view only while visible and closeDetail preserves focus options', async () => {
  const h=harness(), activation=h.bridge.setVisible(true);
  h.resolve(); await activation;
  await h.bridge.load('history');
  h.bridge.closeDetail({restoreFocus:true});
  h.bridge.closeDetail();
  await h.bridge.setVisible(false);
  await h.bridge.load('current');
  assert.deepEqual(h.calls.filter(call=>call[0]==='load'),[['load','history']]);
  assert.deepEqual(h.calls.filter(call=>call[0]==='detail-close'),[['detail-close',true],['detail-close',false]]);
});

}
