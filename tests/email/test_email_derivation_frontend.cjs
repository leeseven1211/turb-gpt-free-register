const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {createVueHarness} = require('../frontend_vue_loader.cjs');
const vue = createVueHarness();
const {flushPromises} = require('../../frontend/node_modules/@vue/test-utils');
const Page = vue.load('src/features/email/EmailPageShell.vue').default;
const {createEmailApi} = vue.load('src/api/email.ts');
const root = path.join(__dirname, '../..');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const plain = value => JSON.parse(JSON.stringify(value));
function deferred() {let resolve;const promise = new Promise(yes => {resolve = yes;});return {promise,resolve};}
test.afterEach(() => vue.cleanup());
test.after(() => vue.close());

// The real API adapter and Vue page own reads and parent scope. Only transport
// and the shell's lazy module boundary are replaced with deterministic fixtures.
function fixture(onNavigate = () => {}) {
  const calls = [], events = [];
  const rows = [
    {source:'outlook',id:4,email:'parent@example.test'},
    {source:'icloud_hide',id:4,email:'different-source@example.test'},
    {source:'outlook',id:15,email:'no-history@example.test'},
  ];
  const api = createEmailApi(async (url, options = {}) => {
    calls.push({url,options});events.push(['request',url]);
    if (url.startsWith('/api/outlook?')) return {items:rows,total:rows.length,facets:{}};
    if (url.startsWith('/api/email-derivation/summary?')) return {enabled:false,parents:[{source:'outlook',parent_id:4,child_count:2,max_children:8}]};
    if (url.startsWith('/api/email-derivation/allocations?')) return {items:[{id:8,source:'outlook',parent_id:4,parent_email:'parent@example.test',email:'parent+child@example.test',state:'reserved',can_generate:true,can_disable:true,can_delete:true}],total:1};
    if (url === '/api/dashboard') return {email:{supply:{sources:[]}}};
    throw new Error(`Unexpected email request: ${url}`);
  });
  const deps = {notify:message => assert.fail(message),confirm:() => true,clipboard:async () => {},onInventoryChanged:async () => {},
    onNavigate(view) {events.push(['navigate','outlook',view]);onNavigate(view);}};
  Object.defineProperty(vue.document,'hidden',{configurable:true,value:false});
  return {api,deps,calls,events};
}

test('库存母项摘要只读取现有记录，不显示额度、生成操作或无历史的入口', async () => {
  const f = fixture();
  const page = vue.mount(Page,{props:{api:f.api,deps:f.deps,initialView:'list',initialVisible:true}});
  await flushPromises();
  const summaries = f.calls.filter(call => call.url.startsWith('/api/email-derivation/summary?'));
  assert.equal(summaries.length,1);
  assert.equal(summaries[0].url,'/api/email-derivation/summary?source=all');
  assert.equal(summaries[0].options.method,undefined);
  assert.ok(summaries[0].options.signal instanceof AbortSignal);
  const inventory = page.get('section[aria-label="邮箱池"]');
  const parent = inventory.get('button[aria-label="查看 parent@example.test 的历史子地址"]');
  assert.match(parent.attributes('title'),/历史子地址 2 个/);
  assert.doesNotMatch(inventory.text()+parent.attributes('title'),/2\/8|生成额度|剩余额度|生成子地址/);
  assert.equal(inventory.find('button[aria-label="查看 different-source@example.test 的历史子地址"]').exists(),false);
  assert.equal(inventory.find('button[aria-label="查看 no-history@example.test 的历史子地址"]').exists(),false);
  assert.equal(inventory.findAll('[data-derivation-state],[data-history-write]').length,0);
  assert.ok(f.calls.every(call => !call.options.method || call.options.method === 'GET'));
  assert.equal(f.calls.some(call => call.url.startsWith('/api/email-derivation/allocations?')),false);
});

test('库存跳转在激活历史读取前交付精确母邮箱，挂载前重复激活只创建一次实例', async () => {
  const loading = deferred(), imports = [], mounted = [];
  const rootNode = vue.document.createElement('div');rootNode.id='email-page-root';rootNode.dataset.moduleUrl='/fixture-email.js';rootNode.dataset.styleUrl='/fixture-email.css';
  const tab = vue.document.createElement('div');tab.id='tab-outlook';tab.append(rootNode);vue.document.body.append(tab);
  const style = vue.document.createElement('link');style.id='task-center-style';vue.document.head.append(style);
  const context = {window:null,document:vue.document,showToast:message=>assert.fail(message),copyText:async()=>true,
    setModuleView(_module,view) {context.EmailPage.setView(view);void context.EmailPage.setVisible(true);},
    loadEmailModule(url) {imports.push(url);return loading.promise;}};
  context.window=context;
  const f=fixture(view=>context.setModuleView('outlook',view));
  vm.runInNewContext(read('webui/static/js/pages/email/page.js').replace('import(root.dataset.moduleUrl)','loadEmailModule(root.dataset.moduleUrl)'),context);
  context.EmailPage.setView('list');
  const first=context.EmailPage.setVisible(true),second=context.EmailPage.setVisible(true);
  assert.equal(imports.length,1);assert.equal(mounted.length,0);assert.equal(f.calls.length,0);
  loading.resolve({mountEmail(node,deps) {
    assert.equal(node,rootNode);assert.equal(deps.visible,false);assert.equal(deps.view,'list');
    const page=vue.mount(Page,{attachTo:node,props:{api:f.api,deps:{...deps,notify:f.deps.notify,onNavigate:f.deps.onNavigate},initialView:deps.view,initialVisible:deps.visible}});
    mounted.push(page);
    return {setView:page.vm.setView,setVisible:page.vm.setVisible,closeDialogs:page.vm.closeDialogs,
      refreshOverview:page.vm.refreshOverview,refreshInventory:page.vm.refreshInventory,refreshHistory:page.vm.refreshHistory,refreshDerivationSummary:page.vm.refreshDerivationSummary,destroy:()=>page.unmount()};
  }});
  await Promise.all([first,second]);await flushPromises();
  assert.equal(mounted.length,1);assert.equal(f.calls.filter(call=>call.url.startsWith('/api/outlook?')).length,1);
  const page=mounted[0];
  await page.get('button[aria-label="查看 parent@example.test 的历史子地址"]').trigger('click');await flushPromises();
  const historyReads=f.calls.filter(call=>call.url.startsWith('/api/email-derivation/allocations?'));
  assert.equal(historyReads.length,1);
  assert.deepEqual(Object.fromEntries(new URL(historyReads[0].url,'http://fixture').searchParams),{page:'1',page_size:'50',source:'outlook',parent_id:'4'});
  assert.deepEqual(plain(f.events.filter(event=>event[0]==='navigate')),[['navigate','outlook','derivations']]);
  const history=page.get('section[aria-label="历史子邮箱"]');
  assert.match(history.get('[data-email-count-row]').text(),/母邮箱：parent@example.test/);
  assert.match(history.text(),/parent\+child@example.test|只读/);
  assert.equal(history.findAll('button').some(button=>['生成','停用','删除'].includes(button.text())),false);
  assert.ok(f.events.findIndex(event=>event[0]==='navigate') < f.events.findIndex(event=>event[0]==='request'&&event[1].startsWith('/api/email-derivation/allocations?')));
  assert.equal(imports.length,1);assert.ok(f.calls.every(call=>!call.options.method||call.options.method==='GET'));
  style.remove();
});
