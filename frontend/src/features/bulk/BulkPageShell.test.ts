import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import BulkPageShell from './BulkPageShell.vue';
import {createBulkIntent} from './useBulkIntent';
import type {BulkNavigation,BulkPageDependencies} from './contracts';
import {realAdapter} from '../accounts/uiTestSupport';
const wrappers:ReturnType<typeof mount>[]=[];
const originalShowModal=Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype,'showModal');
const originalClose=Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype,'close');
beforeEach(()=>{vi.useFakeTimers();sessionStorage.clear();vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});
 Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(this:HTMLDialogElement){this.open=true;}});
 Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(this:HTMLDialogElement){this.open=false;}});
 vi.spyOn(window,'scrollTo').mockImplementation(()=>{});
});
afterEach(()=>{
 wrappers.splice(0).forEach(wrapper=>wrapper.unmount());vi.useRealTimers();vi.unstubAllGlobals();
 if(originalShowModal)Object.defineProperty(HTMLDialogElement.prototype,'showModal',originalShowModal);else Reflect.deleteProperty(HTMLDialogElement.prototype,'showModal');
 if(originalClose)Object.defineProperty(HTMLDialogElement.prototype,'close',originalClose);else Reflect.deleteProperty(HTMLDialogElement.prototype,'close');
});
function fixture(navigation:Partial<BulkNavigation>={}){
 let visible=true;
 const request=vi.fn<(path:string,options?:RequestInit)=>Promise<unknown>>(async path=>{
  if(path==='/catalog')return{operations:[{key:'plan_check',version:1,label:'查询套餐'}],query_schema:{},limits:{}};
  if(path.startsWith('/query-facets'))return{facets:{},matched:2};
  if(path.includes('/targets'))return{items:[],page:{page_size:50,has_more:false}};
  if(path.includes('/report'))return{operation_key:'plan_check',phase:'completed',summary:{},population:{},summary_revision:1};
  if(path.startsWith('/batches/'))return{id:path.split('/')[2]?.split('?')[0],operation_key:'plan_check',name:'大整数批次',summary_revision:1,target_count:0,control:{state:'ended',revision:1},summary:{},rounds_head:[]};
  return{items:[{id:'9007199254740993',name:'批量套餐',action_key:'plan_check',target_count:2,summary:{success:2}}],page:{page_size:20,has_more:false}};
 });
 const api={request:<T>(path:string,options?:RequestInit)=>request(path,options) as Promise<T>};
 const deps:BulkPageDependencies={api,intents:createBulkIntent(api,sessionStorage,()=> 'fixed-key-1234567890'),storage:sessionStorage,
  adapter:realAdapter(),now:()=>Date.now(),isVisible:()=>visible,onNavigation:vi.fn(),
  callbacks:{navigate:vi.fn(),updateNavigation:vi.fn(),notify:vi.fn(),formatDateTime:value=>String(value||'—'),openTask:vi.fn()}};
 const wrapper=mount(BulkPageShell,{attachTo:document.body,props:{deps,initialNavigation:{tab:'bulk',view:'list',...navigation}}});wrappers.push(wrapper);
 return{wrapper,request,deps,setHostVisible(value:boolean){visible=value;document.dispatchEvent(new Event('visibilitychange'));}};
}
it('inactive detail link does not read until activation, and preserves exact string identity',async()=>{
 const h=fixture({view:'detail',batch_id:'9007199254740993'});await flushPromises();expect(h.request).not.toHaveBeenCalled();
 await h.wrapper.vm.activate();await flushPromises();
 expect(h.request.mock.calls.filter(([path])=>path==='/batches/9007199254740993?view=current')).toHaveLength(1);
 expect(document.body.textContent).toContain('#9007199254740993');
});
it('one visible list timer stops when hidden and unmount removes it',async()=>{
 const h=fixture();await h.wrapper.vm.activate();await flushPromises();expect(h.request).toHaveBeenCalledTimes(1);
 await vi.advanceTimersByTimeAsync(7000);await flushPromises();expect(h.request).toHaveBeenCalledTimes(2);
 h.setHostVisible(false);await flushPromises();await vi.advanceTimersByTimeAsync(14000);expect(h.request).toHaveBeenCalledTimes(2);
 h.setHostVisible(true);await flushPromises();expect(h.request).toHaveBeenCalledTimes(3);
 h.wrapper.unmount();await vi.advanceTimersByTimeAsync(14000);expect(h.request).toHaveBeenCalledTimes(3);
});
it('account scope is frozen, old limit removed and selected bigint IDs remain strings',async()=>{
 const h=fixture();const query=h.deps.adapter.normalize({limit:20,filters:{email:'first'}});
 const snapshot={ids:['9007199254740993'],query};
 await h.wrapper.vm.fromAccounts(true,'plan_check',snapshot);query.filters.email='changed';snapshot.ids.push('2');await flushPromises();
 const saved=JSON.parse(sessionStorage.getItem('turb_bulk_draft_v1')!);
 expect(saved.name).toBe('');expect(saved.query.limit).toBeNull();expect(saved.query.filters.email).toBe('first');expect(saved.source.ids).toEqual(['9007199254740993']);
 expect(h.wrapper.vm.navigationState()).toEqual({tab:'bulk',view:'create'});
 expect(h.deps.onNavigation).toHaveBeenLastCalledWith({tab:'bulk',view:'create'},'push');
});
it('daily registration snapshot keeps its name and query while only opening the create page',async()=>{
 const h=fixture();
 const query=h.deps.adapter.normalize({
  q:'注册任务日期:2026-11-26..2026-11-26',
  archived:'0',
  filters:{promotion:['none']},
 });
 const snapshot={ids:[],query,name:'2026-11-26 无优惠账号查套餐'} as unknown as {ids:readonly (string|number)[];query:typeof query};
 await h.wrapper.vm.fromAccounts(false,'plan_check',snapshot);
 await flushPromises();
 const saved=JSON.parse(sessionStorage.getItem('turb_bulk_draft_v1')!);
 expect(saved).toMatchObject({
  name:'2026-11-26 无优惠账号查套餐',
  operation_key:'plan_check',
  query:{q:'注册任务日期:2026-11-26..2026-11-26',archived:'0',filters:{promotion:['none']}},
  source:null,
  max_concurrency:3,
 });
 expect(h.request.mock.calls.some(([,options])=>options?.method==='POST')).toBe(false);
 expect(h.wrapper.vm.navigationState()).toEqual({tab:'bulk',view:'create'});
});
it('global receipt recovery replays the saved request once then opens the accepted batch',async()=>{
 const h=fixture();await h.wrapper.vm.activate();const original={name:'accepted',selection_id:'14'};
 sessionStorage.setItem('turb_bulk_intent:create',JSON.stringify({key:'saved-key-123456789',signature:JSON.stringify({path:'/batches',body:original})}));
 h.request.mockImplementationOnce(async()=>({id:'9007199254740995'}));
 await h.wrapper.vm.recover();await flushPromises();
 const write=h.request.mock.calls.find(([,options])=>options?.method==='POST')!;
 expect(write[1]?.headers).toMatchObject({'Idempotency-Key':'saved-key-123456789'});
 expect(JSON.parse(write[1]?.body as string)).toEqual(original);
 expect(h.wrapper.vm.navigationState().batch_id).toBe('9007199254740995');
 expect(sessionStorage.getItem('turb_bulk_intent:create')).toBeNull();
});
it('storage failure is visible without destroying a usable list',async()=>{
 const h=fixture();await h.wrapper.vm.activate();await flushPromises();
 h.deps.intents.pending=()=>{throw new Error('存储被禁用');};
 await h.wrapper.vm.recover();await flushPromises();
 expect(h.wrapper.get('[data-bulk-error]').text()).toContain('存储被禁用');expect(h.wrapper.text()).toContain('批量套餐');
});
it('late accepted recovery preserves the new navigation and reports the original batch',async()=>{
 const h=fixture();await h.wrapper.vm.activate();
 sessionStorage.setItem('turb_bulk_intent:create',JSON.stringify({key:'saved-key-123456789',signature:JSON.stringify({path:'/batches',body:{selection_id:'14'}})}));
 let release!:(value:unknown)=>void;
 h.request.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}));
 const recovering=h.wrapper.vm.recover();await flushPromises();
 h.wrapper.vm.restoreNavigation({view:'list',q:'new search'});await h.wrapper.vm.activate();
 release({id:'9007199254740995'});await recovering;await flushPromises();
 expect(h.wrapper.vm.navigationState()).toMatchObject({view:'list',q:'new search'});
 expect(h.deps.callbacks.notify).toHaveBeenCalledWith(expect.stringContaining('#9007199254740995'));
 expect(sessionStorage.getItem('turb_bulk_intent:create')).toBeNull();
});
it('failed write immediately exposes its retained recovery intent on a terminal detail',async()=>{
 const h=fixture({view:'detail',batch_id:'9007199254740993'});await h.wrapper.vm.activate();await flushPromises();
 const detail=h.wrapper.findComponent({name:'BulkDetail'});
 // Submission goes through the actual dependency handed to the detail slice.
 h.request.mockRejectedValueOnce(new Error('回执丢失'));
 await expect(detail.props('deps').intents.submit('control:9007199254740993:pause','/batches/9007199254740993/control',{action:'pause'})).rejects.toThrow('回执丢失');
 await flushPromises();
 expect(document.querySelector('[data-bulk-recovery]')).not.toBeNull();
});
it('reopening terminal detail starts a fresh read without waiting on the aborted read',async()=>{
 const h=fixture({view:'detail',batch_id:'9007199254740993'});await h.wrapper.vm.activate();await flushPromises();
 let release!:(value:unknown)=>void;
 h.request.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}));
 const old=h.wrapper.vm.refresh();await flushPromises();
 const oldRequest=h.request.mock.calls.at(-1)![1]!;
 h.setHostVisible(false);await flushPromises();h.setHostVisible(true);await flushPromises();
 expect(oldRequest.signal?.aborted).toBe(true);
 expect(h.request.mock.calls.filter(([path])=>path==='/batches/9007199254740993?view=current')).toHaveLength(3);
 release({id:'9007199254740993',name:'aborted old result'});await old;await flushPromises();
 expect(document.body.textContent).not.toContain('aborted old result');
});
it('查看批次在页面内展示，返回列表后恢复原筛选和分页',async()=>{
 const h=fixture({q:'套餐',state:'ended',cursor:'list.page.2'});
 await h.wrapper.vm.activate();await flushPromises();
 await h.wrapper.get('[data-bulk-open]').trigger('click');await flushPromises();
 expect(h.wrapper.get('.bulk-detail-owner').isVisible()).toBe(true);
 expect(h.wrapper.get('[data-bulk-title]').text()).toContain('大整数批次');
 expect(h.wrapper.get('[aria-label="批次列表"]').isVisible()).toBe(false);
 expect(document.querySelector('dialog[open]')).toBeNull();
 await h.wrapper.get('[data-bulk-action="back-list"]').trigger('click');await flushPromises();
 expect(h.wrapper.vm.navigationState()).toEqual({tab:'bulk',view:'list',q:'套餐',state:'ended',cursor:'list.page.2'});
 expect(h.wrapper.get('[aria-label="批次列表"]').isVisible()).toBe(true);
});
it('列表查看报告只打开浮窗，关闭后保留原列表筛选和分页',async()=>{
 const h=fixture({q:'套餐',state:'ended',cursor:'list.page.2'});await h.wrapper.vm.activate();await flushPromises();
 const navigation={tab:'bulk',view:'list',q:'套餐',state:'ended',cursor:'list.page.2'};
 await h.wrapper.get('[data-bulk-report]').trigger('click');await flushPromises();
 const dialog=document.querySelector<HTMLDialogElement>('[data-bulk-report-dialog][open]');
 expect(dialog).not.toBeNull();expect(dialog?.textContent).toContain('查套餐');
 expect(dialog?.textContent).not.toContain('账号明细');
 expect(h.wrapper.get('.bulk-detail-owner').isVisible()).toBe(false);
 expect(h.wrapper.vm.navigationState()).toEqual(navigation);
 expect(h.deps.onNavigation).not.toHaveBeenCalled();
 dialog!.querySelector<HTMLButtonElement>('[data-bulk-report-close]')!.click();await flushPromises();
 expect(document.querySelector('dialog[open]')).toBeNull();
 expect(h.wrapper.vm.navigationState()).toEqual(navigation);
 expect(h.wrapper.get('[aria-label="批次列表"]').isVisible()).toBe(true);
 expect(h.wrapper.get('.bulk-results-card').isVisible()).toBe(false);
 expect(h.deps.onNavigation).not.toHaveBeenCalled();
});
it('报告加载期间改变列表筛选会取消报告读取，不再轮询隐藏详情',async()=>{
 const h=fixture({q:'套餐'});await h.wrapper.vm.activate();await flushPromises();
 let release!:(value:unknown)=>void;
 let signal:AbortSignal|undefined;
 h.request.mockImplementationOnce((_path,options)=>{signal=options?.signal as AbortSignal;return new Promise(resolve=>{release=resolve;});});
 await h.wrapper.get('[data-bulk-report]').trigger('click');await flushPromises();
 await h.wrapper.get('.bl-toolbar .list-filter-chip').trigger('click');await flushPromises();
 expect(signal?.aborted).toBe(true);
 release({id:'9007199254740993',operation_key:'plan_check',control:{state:'active'},summary:{},rounds_head:[]});
 await flushPromises();
 const reads=h.request.mock.calls.filter(([path])=>path.startsWith('/batches/')).length;
 await vi.advanceTimersByTimeAsync(14000);await flushPromises();
 expect(h.request.mock.calls.filter(([path])=>path.startsWith('/batches/'))).toHaveLength(reads);
 expect(document.querySelector('dialog[open]')).toBeNull();
 expect(h.wrapper.vm.navigationState()).toEqual({tab:'bulk',view:'list'});
});
it.each(['list','detail'] as const)('隐藏批量任务时关闭 %s 报告并停止读取，返回时恢复原范围',async view=>{
 const h=fixture(view==='detail'?{view,batch_id:'9007199254740993'}:{view,q:'套餐'});
 await h.wrapper.vm.activate();
 if(view==='detail')await h.wrapper.vm.showReport();else await h.wrapper.get('[data-bulk-report]').trigger('click');
 await flushPromises();
 expect(document.querySelector('[data-bulk-report-dialog][open]')).not.toBeNull();
 h.wrapper.vm.setVisible(false);await flushPromises();
 expect(document.querySelector('dialog[open]')).toBeNull();
 const reads=h.request.mock.calls.length;await vi.advanceTimersByTimeAsync(14000);
 expect(h.request).toHaveBeenCalledTimes(reads);expect(h.wrapper.vm.navigationState().view).toBe(view);
 await h.wrapper.vm.activate();await flushPromises();
 expect(h.wrapper.get(view==='detail'?'.bulk-detail-owner':'[aria-label="批次列表"]').isVisible()).toBe(true);
 if(view==='list')expect(h.wrapper.vm.navigationState().q).toBe('套餐');
});
it('查看报告时详情读取失败会保留页面错误，不打开空白浮窗',async()=>{
 const h=fixture();await h.wrapper.vm.activate();await flushPromises();
 h.request.mockRejectedValueOnce(new Error('批次详情读取失败'));
 await h.wrapper.get('[data-bulk-report]').trigger('click');await flushPromises();
 expect(h.wrapper.get('[data-bulk-error]').text()).toContain('批次详情读取失败');
 expect(h.wrapper.get('[aria-label="批次列表"]').isVisible()).toBe(true);
 expect(document.querySelector('dialog[open]')).toBeNull();
 expect(h.request.mock.calls.some(([path])=>path.includes('/report?'))).toBe(false);
});
