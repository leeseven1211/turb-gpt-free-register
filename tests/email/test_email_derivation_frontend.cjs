const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const root = path.join(__dirname, '../..');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const email = read('webui/static/js/pages/email/page.js');
const source = email.slice(0, email.indexOf('function getPoolSource()'));

// Real navigation bridge with a local module fixture. Vue and the list requests are
// exercised together in frontend/src/features/emailHistory/EmailHistoryPage.test.ts.
function setup() {
  const requests = [], events = [];
  const summary = {enabled: false, parents: [{source: 'outlook', parent_id: 4, child_count: 2, max_children: 8}]};
  const tab = {classList: {contains: () => false}};
  const node = {dataset: {moduleUrl: 'fixture'}, scrollIntoView() {}};
  const context = vm.createContext({window: {}, OUTLOOK: [], attrEsc: String,
    document: {getElementById: id => id === 'tab-outlook' ? tab : node},
    api: async (url, options) => {requests.push([url,options]); return summary;},
    copyText: async () => true, showToast() {},
    setModuleView: (module,view) => {events.push(['navigate',module,view]); return context.window.EmailHistory.setVisible(true);},
  });
  vm.runInContext(read('webui/static/js/shared/page-bridge.js'), context);
  const bridge = context.window.createPageBridge;
  context.window.createPageBridge = options => bridge({...options, loadModule: async () => ({
    mountEmailHistory: () => ({setView: parent => events.push(['parent', parent.source, parent.id, parent.email]),
      setVisible: value => events.push(['visible',value])}),
  })});
  vm.runInContext(source, context);
  return {context,requests,events};
}

test('库存母项摘要只读取现有记录，不显示额度、生成操作或无历史的入口', async () => {
  const {context, requests} = setup();
  await context.loadEmailDerivationSummary();
  assert.deepEqual(requests, [['/api/email-derivation/summary?source=all', undefined]]);
  const cell = context._poolDerivationCell({source:'outlook',id:4,email:'parent@example.test'});
  assert.match(cell,/历史子地址 2 个/);
  assert.match(cell,/data-derivation-parent="4"/);
  assert.doesNotMatch(cell,/2\/8|生成|data-derivation-state/);
  assert.equal(context._poolDerivationCell({source:'icloud_hide',id:4}), '');
  assert.equal(context._poolDerivationCell({source:'outlook',id:15}), '');
});

test('库存跳转在激活 Vue 实例之前交付精确母邮箱，挂载前重复激活只交付一次', async () => {
  const {context,requests,events} = setup();
  context.showEmailDerivationParent({dataset:{source:'outlook',derivationParent:'4',parentEmail:'parent@example.test'}});
  await context.window.EmailHistory.setVisible(true);
  assert.deepEqual(events, [['navigate','outlook','derivations'],['parent','outlook','4','parent@example.test'],['visible',true]]);
  assert.deepEqual(requests, []);
});
