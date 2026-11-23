import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import EmailPageShell from './EmailPageShell.vue';
import {fixture} from './testSupport';
const wrappers:ReturnType<typeof mount>[]=[];
beforeEach(()=>{
 Object.defineProperty(document,'hidden',{configurable:true,value:false});localStorage.clear();
 vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});
 vi.stubGlobal('scrollTo',vi.fn());
 Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.open=true;}});
 Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(){this.open=false;}});
});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());localStorage.clear();vi.unstubAllGlobals();});
async function page(view='list',configure?:(context:ReturnType<typeof fixture>)=>void){
 const f=fixture();f.handlers.set('/api/outlook',()=>({items:[{id:9,source:'outlook',email:'resource@example.test',status:'used',usage_state:'bound',registered_account_id:12,created_at:'2026-11-16T12:00:00Z',resource_meta:{password:true,client_id:true,refresh_token:true},note:'完整的错误原因会超过十个Unicode字符必须保留详情'}],total:45,facets:{source:[{value:'outlook',count:45}],status:[{value:'used',count:45}]}}));
 f.handlers.set('/api/email-derivation/summary',()=>({parents:[{source:'outlook',parent_id:9,child_count:2}]}));
 f.handlers.set('/api/email-derivation/allocations',()=>({items:[{id:1,source:'outlook',email:'child@example.test',parent_email:'resource@example.test',state:'reserved',created_at:'2026-11-16T12:00:00Z'}],total:1}));
 configure?.(f);const w=mount(EmailPageShell,{attachTo:document.body,props:{api:f.api,deps:f.deps,initialView:view as 'list',initialVisible:true}});wrappers.push(w);await flushPromises();return{w,...f};
}
describe('complete email page owner',()=>{
 it('工具栏保留筛选标签和选中数，总数只显示在分页栏',async()=>{
  const {w,calls}=await page();
  const inventory=w.get('section[aria-label="邮箱池"]');
  const toolbar=inventory.get('.em-toolbar');
  expect(inventory.find('[data-email-count-row]').exists()).toBe(false);
  for(const name of ['复制当前页','导入邮箱','从 Butler 导入','恢复列宽','刷新'])expect(w.findAll('button').some(b=>b.text()===name)).toBe(true);
  expect(w.findAll('thead button').some(b=>b.attributes('aria-label')==='筛选状态')).toBe(true);
  await w.get('button[aria-label="筛选状态"]').trigger('click');await flushPromises();
  const body=new DOMWrapper(document.body);
  expect(body.find('[data-filter-value="available"]').exists()).toBe(false);
  await body.get('.list-filter-popover input[type=radio][value=used]').setValue(true);await flushPromises();
  expect(toolbar.get('.list-filter-summary').text()).toContain('状态：已用');
  expect(calls.filter(c=>c.path.startsWith('/api/outlook?')).at(-1)?.path).toContain('status=used');
  await inventory.get('input[aria-label="选择邮箱 resource@example.test"]').setValue(true);
  expect(toolbar.text()).toContain('已选 1 个邮箱');
  expect(toolbar.text()).toContain('标记未使用');
  expect(inventory.find('.ui-list-bulkbar').exists()).toBe(false);
  expect(toolbar.text()).not.toContain('45');
  expect(w.find('.list-pagination__jump').exists()).toBe(true);
  expect(inventory.get('.list-pagination__range').text()).toContain('共 45 条');
  await toolbar.get('button[aria-label="移除status筛选"]').trigger('click');await flushPromises();
  expect(toolbar.find('.list-filter-summary').exists()).toBe(false);
  const lastInventoryRead=calls.filter(c=>c.path.startsWith('/api/outlook?')).at(-1);
  expect(lastInventoryRead?.path).toMatch(/[?&]status=(?:&|$)/);
  expect(w.get('[data-email-note] summary').text().trim().length).toBeLessThanOrEqual(10);
  expect(w.get('[data-email-note] summary').text().trim()).toBe('备注记录');
  expect(w.get('section[aria-label="邮箱池"]').findAll('thead tr')).toHaveLength(1);
 });
 it('preserves explicit parent-history navigation and keeps the history readonly',async()=>{
  const {w,deps}=await page();await w.get('button[aria-label="查看 resource@example.test 的历史子地址"]').trigger('click');await flushPromises();
  expect(deps.onNavigate).toHaveBeenCalledWith('derivations');w.vm.setView('derivations');await flushPromises();
  expect(w.get('section[aria-label="历史子邮箱"] [data-email-count-row]').text()).toContain('母邮箱');expect(w.text()).toContain('历史归属');expect(w.text()).toContain('只读');expect(w.find('button[data-history-write]').exists()).toBe(false);
 });
 it('keeps expanded evidence after refresh and closes heading portals when hidden',async()=>{
  const {w}=await page();const details=w.get('[data-email-note]');(details.element as HTMLDetailsElement).open=true;
  await w.findAll('button').find(b=>b.text()==='刷新')!.trigger('click');await flushPromises();expect((w.get('[data-email-note]').element as HTMLDetailsElement).open).toBe(true);
  await w.get('button[aria-label="筛选状态"]').trigger('click');await flushPromises();expect(new DOMWrapper(document.body).find('.list-filter-popover').exists()).toBe(true);
  w.vm.setVisible(false);await flushPromises();expect(new DOMWrapper(document.body).find('.list-filter-popover').exists()).toBe(false);
 });
 it('renders local pools disabled in registration and keeps expanded source choices through refresh',async()=>{
  const {w,handlers}=await page('overview');handlers.set('/api/dashboard',()=>({email:{supply:{sources:[{source:'outlook',kind:'local_pool',label:'Outlook',enabled:false,default_visible:false,total:2,available:1},{source:'other',kind:'on_demand',label:'其他服务',enabled:false,default_visible:false}]}}}));
  await w.vm.refreshOverview();await flushPromises();expect(w.text()).toContain('Outlook');expect(w.text()).not.toContain('其他服务');
  await w.findAll('button').find(b=>b.text().includes('显示未启用'))!.trigger('click');await w.vm.refreshOverview();await flushPromises();expect(w.text()).toContain('其他服务');
 });
 it('opens both imports without remote claim, and a local accepted result stays open',async()=>{
  const {w,handlers,calls,deps}=await page();handlers.set('/api/outlook/import-preview',()=>({new:1,total_lines:1,valid:1}));handlers.set('/api/outlook/import',()=>({inserted:1,accepted_count:1,parsed:1}));
  await w.findAll('button').find(b=>b.text()==='导入邮箱')!.trigger('click');await flushPromises();
  await w.get('textarea[aria-label="邮箱资源"]').setValue('email----password----client----refresh');await w.get('button[data-local-submit]').trigger('click');await flushPromises();
  expect((w.get('dialog[data-email-local-import]').element as HTMLDialogElement).open).toBe(true);expect(w.text()).toContain('已接收 1');expect(deps.onNavigate).not.toHaveBeenCalled();
  expect(calls.some(c=>c.path==='/api/email-butler/imports')).toBe(false);expect(calls.some(c=>c.path.startsWith('/api/email-service-sync'))).toBe(false);
 });
 it('keeps both Butler entries in sync, shows original filters and running recovery controls',async()=>{
  localStorage.setItem('turb.butler-import.v1',JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:'running',filters:{provider:'auto',count:30}}));
  const {w}=await page('list',f=>f.handlers.set('/api/email-butler/imports/batch',()=>({batch:{batch_id:'batch',status:'running',imported:2,skipped:1,failed:1,unknown:1,pending:20,submitting:5,total:30,requested:30,can_retry:true,can_cancel:true}})));
  expect(w.findAll('button[data-butler-opener]').map(button=>button.text())).toEqual(['Butler 导入中 · 2/30','Butler 导入中 · 2/30']);
  await w.vm.openButlerImport();await flushPromises();expect(w.get('dialog[data-email-butler-import]').text()).toContain('全部来源');expect(w.get('dialog[data-email-butler-import]').text()).toContain('已处理 5 / 30');expect(w.get('dialog[data-email-butler-import]').text()).toContain('关闭，后台继续');expect(w.get('dialog[data-email-butler-import]').text()).not.toContain('继续原批次');
  await w.get('button[aria-label="关闭 Butler 导入窗口"]').trigger('click');await flushPromises();expect(w.find('button[aria-label="查看 Butler 导入进度"]').exists()).toBe(true);
 });
 it('hides recovery after completed/cancelled restore while preserving a result opener',async()=>{
  for(const status of ['completed','cancelled']){
   localStorage.setItem('turb.butler-import.v1',JSON.stringify({request_id:'original',preview_token:'preview',batch_id:'batch',batch_status:status,filters:{provider:'icloud_hme',count:2}}));
   const {w}=await page('list',f=>f.handlers.set('/api/email-butler/imports/batch',()=>({batch:{batch_id:'batch',status:status==='cancelled'?'running':'completed',imported:2,total:2,can_retry:false}})));
   expect(w.find('button[aria-label="查看 Butler 导入进度"]').exists()).toBe(false);expect(w.findAll('button[data-butler-opener]').map(button=>button.text())).toEqual(['查看 Butler 导入','查看 Butler 导入']);expect((w.get('dialog[data-email-butler-import]').element as HTMLDialogElement).open).toBe(false);
  }
 });
 it('history selection is page-scoped/indeterminate and empty history keeps Butler guidance',async()=>{
  const {w,handlers}=await page('derivations',f=>f.handlers.set('/api/email-derivation/allocations',()=>({items:[{id:1,email:'a@example.test',source:'outlook',state:'reserved'},{id:2,email:'b@example.test',source:'outlook',state:'used'}],total:2})));
  await w.get('input[aria-label="选择历史子邮箱 a@example.test"]').setValue(true);expect((w.get('input[aria-label="全选当前页子邮箱"]').element as HTMLInputElement).indeterminate).toBe(true);
  handlers.set('/api/email-derivation/allocations',()=>({items:[],total:0}));await w.vm.refreshHistory();await flushPromises();expect(w.get('section[aria-label="历史子邮箱"]').text()).toContain('Email Butler');expect(w.get('section[aria-label="历史子邮箱"]').text()).not.toContain('生成额度');
 });
 it('does not show zero-child parent actions or trust legacy writable history flags',async()=>{
  const {w}=await page('list',f=>{f.handlers.set('/api/email-derivation/summary',()=>({parents:[{source:'outlook',parent_id:9,child_count:0,remaining:100,enabled:true}]}));f.handlers.set('/api/email-derivation/allocations',()=>({items:[{id:1,source:'outlook',email:'readonly@example.test',state:'reserved',can_generate:true,can_disable:true,can_delete:true,capabilities:{writable:true}}],total:1}));});
  expect(w.find('button[aria-label="查看 resource@example.test 的历史子地址"]').exists()).toBe(false);
  w.vm.setView('derivations');await flushPromises();expect(w.get('section[aria-label="历史子邮箱"]').text()).toContain('只读');expect(w.get('section[aria-label="历史子邮箱"]').findAll('button').some(button=>['生成','停用','删除'].includes(button.text()))).toBe(false);
 });
 it('opens row more actions in a modal and colors status values',async()=>{
  const {w}=await page();
  expect(w.get('td .em-tone.is-active').text()).toContain('已用');
  await w.findAll('button').find(button=>button.text()==='更多')!.trigger('click');await flushPromises();
  const dialog=w.get('dialog[data-email-more]');
  expect((dialog.element as HTMLDialogElement).open).toBe(true);
  expect(dialog.text()).toContain('恢复可用');expect(dialog.text()).toContain('停用');expect(dialog.text()).toContain('标失败');
  await dialog.get('button[aria-label="关闭邮箱操作"]').trigger('click');await flushPromises();
  expect((dialog.element as HTMLDialogElement).open).toBe(false);
 });
 it('changes page size atomically with one final page-one read',async()=>{
  const {w,calls}=await page();const section=w.get('section[aria-label="邮箱池"]');await section.findAll('button').find(button=>button.text()==='下一页')!.trigger('click');await flushPromises();calls.length=0;
  await section.get('select[aria-label="每页条数"]').setValue('50');await flushPromises();const reads=calls.filter(call=>call.path.startsWith('/api/outlook?'));expect(reads).toHaveLength(1);expect(reads[0]!.path).toContain('page=1&page_size=50');
 });
 it('opens local Butler paste import with original owned-lease help and complete address placeholders',async()=>{
  const {w,calls}=await page('overview');await w.findAll('button').find(button=>button.text()==='粘贴导入')!.trigger('click');await flushPromises();
  const dialog=w.get('dialog[data-email-local-import]');expect((dialog.get('select[aria-label="导入类型"]').element as HTMLSelectElement).value).toBe('email_butler');expect(dialog.text()).toContain('手动导入仅恢复本人原租约');expect(dialog.get('textarea').attributes('placeholder')).toContain('owned@icloud.com');expect(dialog.get('textarea').attributes('placeholder')).toContain('owned@outlook.com');expect(calls.some(call=>call.path==='/api/email-butler/imports')).toBe(false);
 });
});
