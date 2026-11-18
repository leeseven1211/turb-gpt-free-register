import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import AccountsTable from './AccountsTable.vue';
import {accountRow,presentation,realAdapter} from './uiTestSupport';
const wrappers:ReturnType<typeof mount>[]=[];
function table(extra:Record<string,unknown>={}){const w=mount(AccountsTable,{attachTo:document.body,props:{items:[accountRow()],selected:new Set<string>(),query:realAdapter().normalize(),facets:{},presentation,loading:false,error:'',invalidSearch:false,stale:false,visible:true,pageSelected:false,pageIndeterminate:false,openFilter:null,...extra}});wrappers.push(w);return w;}
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});vi.stubGlobal('matchMedia',()=>({matches:false,addEventListener(){},removeEventListener(){}}));});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());localStorage.clear();vi.unstubAllGlobals();});
describe('账号16列表格',()=>{
 it('新查询加载时隐藏旧页并展示加载行，同查询刷新保留行，失败后旧页禁用',async()=>{
  const w=table();expect(w.find('[data-account-row="1"]').exists()).toBe(true);
  await w.setProps({loading:true,stale:true});await flushPromises();
  expect(w.find('[data-account-row]').exists()).toBe(false);expect(w.get('.ac-empty').text()).toContain('正在加载账号');
  await w.setProps({loading:true,stale:false});await flushPromises();
  expect(w.find('[data-account-row="1"]').exists()).toBe(true);expect(w.find('.ac-empty').exists()).toBe(false);
  await w.setProps({loading:false,stale:true,error:'请求失败'});await flushPromises();
  expect(w.find('[data-account-row="1"]').exists()).toBe(true);expect(w.get<HTMLInputElement>('input[data-account-id="1"]').element.disabled).toBe(true);
 });
 it('当前页保持16列且单行选择只发绑定ID，页选使用owner提供状态',async()=>{
  const w=table({pageSelected:false,pageIndeterminate:true});expect(w.findAll('thead th')).toHaveLength(16);expect(w.findAll('tbody tr td')).toHaveLength(16);expect(w.findAll('col')).toHaveLength(16);
  expect(w.get<HTMLInputElement>('#accountsSelectAllV2').element.indeterminate).toBe(true);await w.get('input[data-account-id="1"]').setValue(true);expect(w.emitted('select')).toEqual([['1',true]]);
 });
 it('旧copy-id事件消费一次，不再冒泡到文档复制委托',async()=>{
  const w=table();const globalCopy=vi.fn((event:Event)=>{if((event.target as Element).closest('[data-copy-id]'))return;});document.addEventListener('click',globalCopy);
  try{await w.get('[data-copy-id]').trigger('click');expect(w.emitted('action')).toHaveLength(1);expect(w.emitted('action')?.[0]?.slice(0,2)).toEqual(['copy-id:copy-key-1','1']);expect(globalCopy).not.toHaveBeenCalled();}finally{document.removeEventListener('click',globalCopy);}
 });
 it('stale列表禁用全部行操作和勾选，程序分派旧点击也不发action或detail',async()=>{
  const w=table({stale:true});expect(w.get<HTMLInputElement>('input[data-account-id="1"]').element.disabled).toBe(true);expect(w.get<HTMLInputElement>('#accountsSelectAllV2').element.disabled).toBe(true);
  for(const element of w.findAll('tbody button'))expect(element.attributes('disabled')).toBeDefined();
  w.get('[data-account-action]').element.dispatchEvent(new MouseEvent('click',{bubbles:true}));w.get('[data-account-detail-id]').element.dispatchEvent(new MouseEvent('click',{bubbles:true}));await flushPromises();expect(w.emitted('action')).toBeUndefined();expect(w.emitted('detail')).toBeUndefined();
 });
 it('更多Portal保留动作数据和能力gate，隐藏或stale后关闭',async()=>{
  const w=table(),body=new DOMWrapper(document.body);await w.get('button[aria-label="更多账号操作"]').trigger('click');await flushPromises();expect(body.get('.ac-row-menu [data-account-email-invalid]').attributes('data-invalid')).toBe('1');
  const gate=(event:Event)=>{if((event.target as Element).closest('[data-codex-retry]')){event.preventDefault();event.stopImmediatePropagation();}};document.addEventListener('click',gate,true);
  try{await body.get('.ac-row-menu [data-codex-retry]').trigger('click');expect(w.emitted('action')).toBeUndefined();}finally{document.removeEventListener('click',gate,true);}
  await w.setProps({stale:true});await flushPromises();expect(body.find('.ac-row-menu').exists()).toBe(false);
  await w.setProps({stale:false});await w.get('button[aria-label="更多账号操作"]').trigger('click');await flushPromises();await w.setProps({visible:false});await flushPromises();expect(body.find('.ac-row-menu').exists()).toBe(false);
 });
 it('旧列宽保持ratio+total并在用户调整后写layout版本，reset回1500',async()=>{
  localStorage.setItem('gpt_console_table_widths_accounts',JSON.stringify([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]));localStorage.setItem('gpt_console_table_total_accounts','1360');
  const w=table();expect(w.findAll('col')[1]!.attributes('style')).toContain('20px');await w.get('button[aria-label="调整ID列宽，方向键调整"]').trigger('keydown',{key:'ArrowRight'});expect(localStorage.getItem('gpt_console_accounts_columns_v2')).toBe('2');expect(localStorage.getItem('gpt_console_table_total_accounts')).toBe('1370');w.vm.resetColumns();await flushPromises();expect(localStorage.getItem('gpt_console_accounts_columns_v2')).toBeNull();expect(w.get('table').attributes('style')).toContain('1500px');
 });
});
