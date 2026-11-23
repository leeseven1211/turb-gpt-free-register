// Existing Python UI contracts run the real migrated components without a server.
const assert = require('node:assert/strict');
const {createVueHarness} = require('../frontend_vue_loader.cjs');
const {installNetworkFence} = require('../config/vue_migration_contracts.cjs');

async function run(name) {
  const closeFence = installNetworkFence(), harness = createVueHarness(), owners = [];
  try {
    const Overview = harness.load('src/features/email/EmailOverview.vue').default;
    const sources = [
      {source:'outlook',label:'Outlook 邮箱池',kind:'local_pool',enabled:false,available:2,total:3,history_available:true,default_visible:false},
      {source:'icloud_hide',label:'iCloud 隐藏邮箱池',kind:'local_pool',enabled:true,total:1,default_visible:true},
      {source:'email_butler',label:'Email Butler',kind:'on_demand',enabled:false,dependency:true,dependency_reason:'<script>alert(1)</script>',default_visible:true},
      {source:'mailnest',label:'<img src=x onerror=alert(1)>',kind:'on_demand',enabled:false,default_visible:false},
    ];
    if (name === 'overview_visibility' || name === 'overview_capacity') {
      const view = harness.mount(Overview, {props:{sources,expanded:false,loading:false,error:'',butlerLabel:'从 Butler 导入'}});
      assert.match(view.text(), /Outlook 邮箱池/);
      assert.match(view.text(), /iCloud 隐藏邮箱池/);
      assert.match(view.text(), /Email Butler/);
      assert.doesNotMatch(view.text(), /onerror/);
      assert.equal(view.find('script').exists(), false);
      assert.match(view.text(), /<script>alert\(1\)<\/script>/);
      const card = view.findAll('button.em-source-card').find(item => item.text().includes('Outlook'));
      assert.ok(card, 'local inventory keeps a real keyboard accessible navigation button');
      assert.match(card.text(), /本地库存/);assert.match(card.text(), /总数 3/);
      assert.doesNotMatch(card.text(), /运行时领取/);
      await card.trigger('click');assert.deepEqual(view.emitted('source'), [['outlook']]);
      const expand = view.get('[aria-expanded]');
      await expand.trigger('click');assert.equal(view.emitted('expand').length, 1);
      await view.setProps({expanded:true});
      assert.match(view.text(), /<img src=x onerror=alert\(1\)>/);
      assert.equal(view.find('img').exists(), false);
      const disabled = view.findAll('.em-source-card').find(item => item.text().includes('onerror'));
      assert.ok(disabled);assert.match(disabled.text(), /未启用/);
      return;
    }
    const {createEmailApi} = harness.load('src/api/email.ts');
    const {useEmailInventory} = harness.load('src/features/email/useEmailInventory.ts');
    const Inventory = harness.load('src/features/email/EmailInventory.vue').default;
    const deps = {notify() {}, confirm:() => true, clipboard:async () => {}, onNavigate() {}, onInventoryChanged:async () => {}};
    const api = createEmailApi(async path => {
      if (path.includes('/summary')) return {parents:[]};
      assert.ok(path.startsWith('/api/outlook?'));return {items:[],total:0,facets:{}};
    });
    const owner = useEmailInventory(api, deps);owners.push(owner);
    owner.state.items = [
      {id:1,source:'outlook',email:'replaced@example.test',status:'replaced'},
      {id:2,source:'outlook',email:'pending@example.test',status:'pending_sync'},
      {id:3,source:'outlook',email:'available@example.test',status:'available'},
    ];owner.state.total = 300000;
    const view = harness.mount(Inventory, {props:{owner,active:true,butlerLabel:'从 Butler 导入'}});
    if (name === 'retired_status') {
      const rows = view.findAll('tbody tr');
      assert.match(rows[0].text(), /换绑后邮箱/);
      assert.equal(rows[0].find('.em-more summary').exists(), false);
      assert.equal(rows[1].find('.em-more summary').exists(), false);
      assert.equal(rows[2].find('.em-more summary').exists(), true);
      return;
    }
    if (name === 'inventory_controls') {
      await view.get('[aria-label="选择邮箱 available@example.test"]').setValue(true);
      for (const label of ['标记未使用','停用选中','标失败','删除选中','复制当前页','导入邮箱','从 Butler 导入','恢复列宽','刷新']) {
        assert.ok(view.findAll('button').some(button => button.text() === label), label);
      }
      assert.equal(view.findAll('thead th').filter(th => th.find('button[aria-haspopup]').exists()).length >= 3, true);
      assert.match(view.get('.ui-list-toolbar').text(), /已选 1 个邮箱/);
      assert.match(view.get('[aria-label="邮箱资源分页"]').text(), /共 300,000 条/);
      assert.equal(view.findAll('thead .ui-table__resize').length,9);
      assert.equal(view.find('[data-resizable-table]').exists(), false, 'legacy resizer does not own the Vue table');
      return;
    }
    throw new Error(`Unknown email UI contract: ${name}`);
  } finally {
    owners.forEach(owner => owner.dispose());harness.close();closeFence();
  }
}
if (require.main === module) run(process.argv[2]).catch(error => {console.error(error);process.exitCode = 1;});
module.exports = {run};
