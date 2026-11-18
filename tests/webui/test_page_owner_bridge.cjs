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
    async load() {calls.push(['load']);},
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
