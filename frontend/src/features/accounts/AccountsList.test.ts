import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import AccountsList from './AccountsList.vue';
import type {AccountsCallbacks} from './presentation';
import type {AccountActionContext} from './useAccounts';
import {accountRow,deferred,listResponse,presentation,readApi,realAdapter} from './uiTestSupport';
const wrappers:ReturnType<typeof mount>[]=[];
async function page(extra:Partial<AccountsCallbacks>={}){const reads=readApi();const callbacks:AccountsCallbacks={openDetail:vi.fn(),invoke:vi.fn(),onStateChange:vi.fn(),closeConsumers:vi.fn(),...extra};const w=mount(AccountsList,{attachTo:document.body,props:{adapter:realAdapter(),api:reads.api,presentation,callbacks}});wrappers.push(w);w.vm.setVisible(true);await flushPromises();return{w,callbacks,...reads};}
async function menuAction(w:ReturnType<typeof mount>,selector='[data-account-email-invalid]'){
 await w.get('button[aria-label="更多账号操作"]').trigger('click');await flushPromises();
 const action=new DOMWrapper(document.body).get<HTMLElement>(`.ac-row-menu ${selector}`);await action.trigger('click');await flushPromises();return action.element;
}
beforeEach(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});vi.stubGlobal('matchMedia',()=>({matches:false,addEventListener(){},removeEventListener(){}}));});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());localStorage.clear();vi.unstubAllGlobals();});
describe('账号列表实际controller整合',()=>{
 it('page/size沿真实分页器发一个最终查询并保留跨页选择',async()=>{
  const {w,requests,callbacks}=await page();expect(w.get('select[aria-label="每页条数"]').findAll('option').map(option=>option.attributes('value'))).toEqual(['10','20','30','50','100']);await w.get('input[data-account-id="1"]').setValue(true);await w.findAll('button').find(x=>x.text()==='下一页')!.trigger('click');await flushPromises();await w.get('input[data-account-id="2"]').setValue(true);
  expect(w.vm.getAccountSelectionSnapshot().ids).toEqual(['1','2']);requests.length=0;await w.get('select[aria-label="每页条数"]').setValue('50');await flushPromises();expect(requests).toHaveLength(1);expect(requests[0]).toMatchObject({page:1,size:50});expect(w.vm.getAccountSelectionSnapshot().ids).toEqual(['1','2']);expect(callbacks.onStateChange).toHaveBeenLastCalledWith(expect.objectContaining({selectedIds:['1','2'],page:1,size:50}));
 });
 it('总数显示在分页栏，工具栏筛选摘要可移除高级搜索条件并保留列条件',async()=>{
  const {w,api,requests}=await page();api.list=async(query,page,size,signal)=>{requests.push({page,size,q:query.q,signal});return{...listResponse([accountRow()],page,size),search_terms:query.q?[{field:'note',label:'备注',value:'a/b',display_value:'a/b',query_without:''}]:[]};};
  w.vm.updateQuery({q:'备注:"a/b"',filters:realAdapter().normalize({filters:{source:['cloudflare']}}).filters});await flushPromises();
  expect(w.get('.ac-toolbar').text()).not.toContain('30 个账号');
  expect(w.get('[aria-label="账号列表分页"] .list-pagination__range').text()).toContain('共 30 条');
  const bar=w.get('.ac-toolbar-main');expect(bar.get('[aria-label="已应用筛选"]').text()).toContain('来源：cloudflare');expect(bar.text()).toContain('备注：a/b');await bar.get('button[aria-label="移除备注：a/b"]').trigger('click');await flushPromises();expect(requests.at(-1)?.q).toBe('');expect(w.vm.getAccountSelectionSnapshot().query.filters.source).toEqual(['cloudflare']);
 });

 it('列表摘要使用动态优惠 metadata，不暴露 offer_v1 摘要键',async()=>{
  const offer='offer_v1_0000000000000000000000000000000a';
  const {w,api}=await page();
  api.list=async(query,page,size)=>({...listResponse([accountRow()],page,size),facets:{promotion:[
   {value:offer,count:0,group:'plus',label:'Plus 其他折扣 12 个月'},
  ]}});
  w.vm.updateFilters({promotion:[offer]});
  await flushPromises();
  expect(w.get('[aria-label="已应用筛选"]').text()).toContain('Plus 其他折扣 12 个月');
  expect(w.get('[aria-label="已应用筛选"]').text()).not.toContain(offer);
 });
 it('行点击只invoke一次且确认等待期间换页清选不改变冻结context',async()=>{
  let captured:AccountActionContext|undefined;const pending=deferred<void>();const invoke=vi.fn(async(_action:string,context:AccountActionContext)=>{captured=context;await pending.promise;});const {w}=await page({invoke});await w.get('[data-account-action="twofa"]').trigger('click');expect(invoke).toHaveBeenCalledTimes(1);expect(invoke.mock.calls[0]?.[0]).toBe('account-action:twofa');expect(captured?.accountIds).toEqual(['1']);expect(Object.isFrozen(captured)).toBe(true);expect(Object.isFrozen(captured?.querySnapshot.filters)).toBe(true);
  w.vm.setPage(2);await flushPromises();w.vm.clearSelection();expect(captured?.expectedEmails).toEqual({'1':'account-1@example.test'});expect(captured?.rowHints[0]?.id).toBe(1);pending.resolve();await flushPromises();
 });
 it('Portal重开和原按钮卸载不会重复执行仍在确认或提交中的账号操作',async()=>{
  const confirmation=deferred<boolean>(),request=deferred<void>();const submit=vi.fn(()=>request.promise);const invoke=vi.fn(async()=>{if(await confirmation.promise)await submit();});const {w}=await page({invoke});
  const firstTrigger=await menuAction(w);expect(firstTrigger.isConnected).toBe(false);await menuAction(w);expect(invoke).toHaveBeenCalledTimes(1);expect(submit).not.toHaveBeenCalled();
  confirmation.resolve(true);await flushPromises();await menuAction(w);expect(invoke).toHaveBeenCalledTimes(1);expect(submit).toHaveBeenCalledTimes(1);
  request.resolve();await flushPromises();await menuAction(w);expect(invoke).toHaveBeenCalledTimes(2);
 });
 it.each(['cancel','reject'])('确认取消或请求失败后释放防重，允许重试（%s）',async(outcome)=>{
  const confirmation=deferred<void>();const invoke=vi.fn().mockImplementationOnce(async()=>{await confirmation.promise;if(outcome==='reject')throw new Error('提交失败');});const {w,callbacks}=await page({invoke,notify:vi.fn()});
  await menuAction(w);await menuAction(w);expect(invoke).toHaveBeenCalledTimes(1);confirmation.resolve();await flushPromises();await menuAction(w);expect(invoke).toHaveBeenCalledTimes(2);expect(callbacks.notify).toHaveBeenCalledTimes(outcome==='reject'?1:0);
 });
 it('防重仅限制相同账号及动作，跨页后仍阻止原请求重复提交',async()=>{
  const pending=deferred<void>();const invoke=vi.fn<AccountsCallbacks['invoke']>(()=>pending.promise);const {w}=await page({invoke});await menuAction(w);await menuAction(w,'[data-account-delete]');expect(invoke).toHaveBeenCalledTimes(2);
  w.vm.setPage(2);await flushPromises();await menuAction(w);expect(invoke).toHaveBeenCalledTimes(3);expect(invoke.mock.calls[2]?.[1]).toMatchObject({accountIds:['2']});
  w.vm.setPage(1);await flushPromises();await menuAction(w);expect(invoke).toHaveBeenCalledTimes(3);pending.resolve();await flushPromises();
 });
 it('改变查询但读取失败时旧行保留且禁用操作，重试成功后重新可用',async()=>{
  const {w,api,callbacks}=await page();api.list=async()=>{throw new Error('网络中断');};w.vm.updateQuery({q:'new'});await flushPromises();expect(w.text()).toContain('account-1@example.test');expect(w.get('[role="alert"]').text()).toContain('网络中断');expect(w.get<HTMLButtonElement>('[data-account-action]').element.disabled).toBe(true);w.get('[data-account-action]').element.dispatchEvent(new MouseEvent('click',{bubbles:true}));await flushPromises();expect(callbacks.invoke).not.toHaveBeenCalled();
  api.list=async()=>listResponse([accountRow(4)]);await w.get('[role="alert"] button').trigger('click');await flushPromises();expect(w.text()).toContain('account-4@example.test');expect(w.get<HTMLButtonElement>('[data-account-action]').element.disabled).toBe(false);
 });
 it('detail获得冻结快照和独立lease；隐藏通知关闭并使旧lease失效',async()=>{
  let lease:Parameters<AccountsCallbacks['openDetail']>[2]|undefined;const openDetail=vi.fn<AccountsCallbacks['openDetail']>((_id,_row,value)=>{lease=value;});const closeConsumers=vi.fn(()=>lease?.release());const {w}=await page({openDetail,closeConsumers});await w.get('[data-account-detail-id="1"]').trigger('click');expect(openDetail).toHaveBeenCalledTimes(1);expect(Object.isFrozen(openDetail.mock.calls[0]?.[1])).toBe(true);expect(await lease!.loadPlanDetails('1',lease!.openGeneration)).toMatchObject({accountId:'1'});w.vm.setVisible(false);await flushPromises();expect(closeConsumers).toHaveBeenCalled();await expect(lease!.loadPlanDetails('1',lease!.openGeneration)).rejects.toMatchObject({name:'AbortError'});
 });
 it('Escape清空高级搜索并保持输入焦点，中文组合中的Enter不提交拼音',async()=>{
  const {w,requests}=await page();const input=w.get<HTMLInputElement>('#accountAdvancedSearchV2');input.element.focus();await input.trigger('compositionstart');await input.setValue('zhong');await input.trigger('keydown',{key:'Enter',isComposing:true});expect(requests).toHaveLength(1);await input.trigger('compositionend');await input.setValue('中文');await input.trigger('submit');await w.get('form[role="search"]').trigger('submit');await flushPromises();expect(requests.at(-1)?.q).toBe('中文');await input.trigger('keydown',{key:'Escape'});await flushPromises();expect(requests.at(-1)?.q).toBe('');expect(input.element.value).toBe('');expect(document.activeElement).toBe(input.element);
 });
 it('document隐藏关闭Portal及consumer，恢复仅一次读取且不复活浮层',async()=>{
  const {w,callbacks,requests}=await page();await w.get('button[aria-label="更多账号操作"]').trigger('click');await flushPromises();const body=new DOMWrapper(document.body);expect(body.find('.ac-row-menu').exists()).toBe(true);requests.length=0;Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));await flushPromises();expect(body.find('.ac-row-menu').exists()).toBe(false);expect(callbacks.closeConsumers).toHaveBeenCalled();Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));await flushPromises();expect(requests).toHaveLength(1);expect(body.find('.ac-row-menu').exists()).toBe(false);
 });
});
