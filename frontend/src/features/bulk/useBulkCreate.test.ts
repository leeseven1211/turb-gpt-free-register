import {effectScope,nextTick} from 'vue';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {BulkApiError} from '../../api/bulk';
import {deferred,realAdapter} from '../accounts/uiTestSupport';
import type {BulkApi,BulkCatalog,BulkCreateDependencies,BulkDraft,BulkRecord,BulkStorage} from './contracts';
import {createBulkIntent} from './useBulkIntent';
import {useBulkCreate} from './useBulkCreate';

const scopes:ReturnType<typeof effectScope>[]=[];
const plain=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
function storage():BulkStorage {const values=new Map<string,string>();return{get length(){return values.size;},key:index=>[...values.keys()][index]??null,getItem:key=>values.get(key)??null,setItem:(key,value)=>{values.set(key,value);},removeItem:key=>{values.delete(key);}};}
function catalog(revision='r1'):BulkCatalog{return{operations:[{key:'plan_check',version:1,label:'查询套餐',effective_settings:{config_revision:revision},parameter_schema:{timezone_offset_min:{type:'integer'}}},{key:'token_refresh',version:1,label:'刷新 AT'}],query_schema:{},limits:{concurrency_max:128}};}
function setup(saved:Record<string,unknown>={}) {
 const adapter=realAdapter(),store=storage();for(const [key,value]of Object.entries(saved))store.setItem(key,JSON.stringify(value));
 const calls:{path:string;body?:BulkRecord;options?:RequestInit}[]=[];
 const handlers={read:async(path:string):Promise<unknown>=>path==='/catalog'?catalog():path.startsWith('/query-facets')?{facets:{source:[{value:'cloudflare',count:30}]},matched:30}:{id:'9007199254740993',state:'ready',target_count:30,selection_revision:2},post:async(path:string,_body:BulkRecord):Promise<unknown>=>path==='/selections'?{id:'9007199254740993',state:'preparing'}:{id:'9007199254740997'}};
 const api:BulkApi={async request<T>(path:string,options?:RequestInit):Promise<T>{const body=options?.body?JSON.parse(String(options.body)):undefined;calls.push({path,body,options});return (options?.method==='POST'?handlers.post(path,body):handlers.read(path)) as Promise<T>;}};
 const callbacks={navigate:vi.fn(),updateNavigation:vi.fn(),notify:vi.fn(),formatDateTime:String,openTask:vi.fn()};
 let time=1,key=0;const deps:BulkCreateDependencies={adapter,storage:store,api,intents:createBulkIntent(api,store,()=>`key-${++key}`),callbacks,now:()=>time};
 const scope=effectScope();scopes.push(scope);const owner=scope.run(()=>useBulkCreate(deps))!;
 const draft=(extra:Partial<BulkDraft>={}):BulkDraft=>({name:'测试批次',operation_key:'plan_check',query:adapter.normalize(),source:null,parameters:{},max_concurrency:3,...extra});
 return{owner,scope,deps,calls,handlers,callbacks,store,draft,setTime:(value:number)=>{time=value;}};
}
afterEach(()=>{scopes.splice(0).forEach(scope=>scope.stop());vi.useRealTimers();});

describe('批次创建 owner',()=>{
 it('固定名单保留大整数字符串及来源快照，按 ready revision 创建暂停批次',async()=>{
  const h=setup();const ids=['9007199254740993','9007199254740995'];const seed=h.draft({source:{kind:'ids',entity:'account',ids}});h.owner.applySeed(seed);ids.push('5');await h.owner.initialize();await h.owner.createBatch(true);
  const writes=h.calls.filter(call=>call.body);expect(writes.map(call=>call.path)).toEqual(['/selections','/batches']);expect(writes[0]!.body).toMatchObject({source:{kind:'ids',entity:'account',ids:['9007199254740993','9007199254740995']},parameters:{timezone_offset_min:new Date().getTimezoneOffset()},expected_config_revision:'r1'});
  expect(writes[1]!.body).toMatchObject({selection_id:'9007199254740993',selection_revision:2,execution:{max_concurrency:3,start_paused:true},expected_config_revision:'r1'});expect(h.callbacks.navigate).toHaveBeenCalledWith('detail',{batch_id:'9007199254740997'});expect(h.store.getItem('turb_bulk_selection_v1')).toBeNull();
 });
 it('旧草稿限额和执行覆盖失效，查询保留但使用配置页参数',async()=>{
  const adapter=realAdapter();const h=setup({turb_bulk_draft_v1:{name:'旧草稿',operation_key:'plan_check',limit:5,query:adapter.normalize({limit:2,archived:'only',date_from:'2026-10-01',filters:{promotion:['none']}}),parameters:{countries:['US']},max_concurrency:5},turb_bulk_selection_v1:{id:'71',state:'ready',target_count:2,selection_revision:1,request_parameters:{countries:['US']}}});
  await h.owner.initialize();await h.owner.createBatch();const writes=h.calls.filter(call=>call.body);expect(writes[0]!.path).toBe('/selections');expect(writes[0]!.body).toMatchObject({source:{kind:'query',query:{archived:'only',limit:null,date_from:'2026-10-01',filters:{promotion:['none']}}},parameters:{timezone_offset_min:new Date().getTimezoneOffset()}});expect(h.owner.draft.value).not.toHaveProperty('limit');expect(h.owner.draft.value.parameters).toEqual({});
 });
 it('已固定名单只保留套餐时区参数，不重建选择也不改时区',async()=>{
  const h=setup({turb_bulk_selection_v1:{id:'71',state:'ready',target_count:3,selection_revision:1,config_revision:'saved-revision',request_parameters:{timezone_offset_min:0}}});h.handlers.read=async path=>path==='/catalog'?catalog():path.startsWith('/query-facets')?{facets:{},matched:3}:{id:'71',state:'ready',target_count:3,selection_revision:4};await h.owner.initialize();await h.owner.createBatch();
  expect(h.calls.filter(call=>call.body)).toHaveLength(1);expect(h.calls.find(call=>call.body)?.body).toMatchObject({selection_id:'71',selection_revision:4,parameters:{timezone_offset_min:0},expected_config_revision:'saved-revision'});
 });
 it('preparing仅由外部刷新推进且重复点击不重复创建',async()=>{
  vi.useFakeTimers();const h=setup();let ready=false;h.handlers.read=async path=>path==='/catalog'?catalog():path.startsWith('/query-facets')?{facets:{},matched:4}:{id:'71',state:ready?'ready':'preparing',target_count:4,selection_revision:2};await h.owner.initialize();await h.owner.createBatch();await h.owner.createBatch(true);const reads=h.calls.length;await vi.advanceTimersByTimeAsync(10000);expect(h.calls).toHaveLength(reads);expect(h.owner.creating.value).toBe(true);expect(h.owner.needsRefresh.value).toBe(true);
  ready=true;await Promise.all([h.owner.refresh(),h.owner.refresh()]);expect(h.calls.filter(call=>call.path==='/selections')).toHaveLength(1);expect(h.calls.filter(call=>call.path==='/batches')).toHaveLength(1);expect(h.owner.creating.value).toBe(false);
 });
 it('准备结果为空或失败时不创建批次',async()=>{
  for(const selection of [{id:'71',state:'ready',target_count:0,selection_revision:1},{id:'71',state:'failed',error_code:'snapshot_failed',error:{message:'范围准备失败'}}]){const h=setup();h.handlers.post=async()=>selection;await h.owner.initialize();await h.owner.createBatch();expect(h.calls.some(call=>call.path==='/batches')).toBe(false);expect(h.owner.error.value).toMatch(/没有匹配账号|范围准备失败/);expect(h.owner.creating.value).toBe(false);}
 });
 it('并发数校验定位字段且不提交',async()=>{
  const h=setup();await h.owner.initialize();h.owner.setDraftField('max_concurrency',129);await h.owner.createBatch();expect(h.calls.some(call=>call.body)).toBe(false);expect(h.owner.errorField.value).toBe('max_concurrency');h.owner.setDraftField('max_concurrency',2.5);await h.owner.createBatch();expect(h.calls.some(call=>call.body)).toBe(false);
 });
 it('筛选查询竞态不会覆盖新范围且缓存还原 matched',async()=>{
  const h=setup();await h.owner.initialize();const slow=deferred<unknown>();h.handlers.read=async path=>path.includes('query-facets')?(JSON.parse(decodeURIComponent(path.split('?query=')[1]!)).archived==='only'?slow.promise:{facets:{source:[{value:'cloudflare',count:30}]},matched:30}):catalog();h.owner.setQueryField('archived','only');const first=h.owner.loadFacets();h.owner.setQueryField('archived','0');await h.owner.loadFacets();slow.resolve({facets:{source:[{value:'icloud_hide',count:3}]},matched:3});await first;expect(h.owner.matched.value).toBe(30);expect(h.owner.facets.value.source?.[0]?.value).toBe('cloudflare');h.owner.setQueryField('archived','only');await h.owner.loadFacets();expect(h.owner.matched.value).toBe(3);
 });
 it('修改条件使选择失效，旧 selection 读取不能污染新草稿',async()=>{
  const h=setup({turb_bulk_selection_v1:{id:'71',state:'ready',target_count:3}});const pending=deferred<unknown>();h.handlers.read=async path=>path==='/catalog'?catalog():path.startsWith('/query-facets')?{facets:{},matched:30}:pending.promise;const loading=h.owner.initialize();await nextTick();await Promise.resolve();h.owner.applySeed(h.draft({operation_key:'token_refresh',source:{kind:'ids',ids:['5'],entity:'account'}}));pending.resolve({id:'71',state:'ready',target_count:3});await loading;expect(h.owner.selection.value).toBeNull();expect(h.owner.draft.value.operation_key).toBe('token_refresh');
 });
 it('旧创建回执迟到时保留新草稿，只告知已创建的原批次',async()=>{
  const h=setup();const pending=deferred<unknown>(),started=deferred<void>();h.handlers.post=async path=>{if(path==='/selections')return{id:'71',state:'ready',target_count:3,selection_revision:1};started.resolve();return pending.promise;};await h.owner.initialize();const creating=h.owner.createBatch();await started.promise;h.owner.applySeed(h.draft({name:'新草稿',operation_key:'token_refresh'}));pending.resolve({id:'81'});await creating;expect(h.owner.draft.value.name).toBe('新草稿');expect(h.callbacks.navigate).not.toHaveBeenCalled();expect(h.callbacks.notify).toHaveBeenCalledWith(expect.stringContaining('原批次 #81'));
 });
 it('配置版本变化重读目录并废弃旧选择，明确显示恢复信息',async()=>{
  const h=setup();let count=0;h.handlers.read=async path=>path==='/catalog'?catalog(++count===1?'r1':'r2'):path.startsWith('/query-facets')?{facets:{},matched:3}:{id:'71',state:'ready',target_count:3,selection_revision:1};h.handlers.post=async path=>{if(path==='/selections')return{id:'71',state:'ready',target_count:3,selection_revision:1};throw new BulkApiError('配置已更新',409,'config_revision_changed');};await h.owner.initialize();await h.owner.createBatch();expect(h.owner.selection.value).toBeNull();expect(h.owner.configRevision.value).toBe('r2');expect(h.callbacks.notify).toHaveBeenCalledWith('配置已更新，请重新创建批次。');
 });
 it('已消费选择显示原批次入口，过期选择失效',async()=>{
  for(const code of ['selection_consumed','selection_expired']){const h=setup();h.handlers.post=async path=>{if(path==='/selections')return{id:'71',state:'ready',target_count:3,selection_revision:1};throw new BulkApiError('范围不可用',409,code,{existing_batch_id:'81'});};await h.owner.initialize();await h.owner.createBatch();if(code==='selection_consumed')expect(h.owner.existingBatchId.value).toBe('81');else expect(h.owner.selection.value).toBeNull();}
 });
 it('丢失创建回执持久化原键，重挂载恢复直接回到原批次',async()=>{
  const h=setup();let failure=true;h.handlers.post=async path=>{if(path==='/selections')return{id:'71',state:'ready',target_count:3,selection_revision:1};if(failure)throw new BulkApiError('连接中断',0);return{id:'81'};};await h.owner.initialize();await h.owner.createBatch();const request=h.calls.find(call=>call.path==='/batches')!;expect(h.owner.pendingCount.value).toBe(1);failure=false;await h.owner.recover();const restored=h.calls.filter(call=>call.path==='/batches').at(-1)!;expect(restored.options?.headers).toEqual(request.options?.headers);expect(restored.body).toEqual(request.body);expect(h.callbacks.navigate).toHaveBeenCalledWith('detail',{batch_id:'81'});expect(h.owner.pendingCount.value).toBe(0);
 });
 it('选择回执恢复重新还原原账号范围，清除旧limit后不能沿用截断选择',async()=>{
  const h=setup();const body={operation:{key:'plan_check',version:1},source:{kind:'query',query:h.deps.adapter.normalize({limit:5,filters:{email:'saved@example.test'}})},parameters:{timezone_offset_min:0},expected_config_revision:'r1'};h.store.setItem('turb_bulk_intent:selection',JSON.stringify({key:'saved-key',signature:JSON.stringify({path:'/selections',body})}));h.handlers.post=async()=>({id:'71',state:'ready',target_count:5,selection_revision:1});await h.owner.recover();expect(h.owner.draft.value.query.filters.email).toBe('saved@example.test');expect(h.owner.draft.value.query.limit).toBeNull();expect(h.owner.selection.value).toBeNull();expect(h.callbacks.navigate).toHaveBeenCalledWith('create');
 });
 it('真实401保留草稿与请求，错误提示重新登录',async()=>{
  const h=setup();h.owner.applySeed(h.draft({name:'保留草稿'}));h.handlers.post=async()=>{throw new BulkApiError('登录失效',401);};await h.owner.initialize();await h.owner.createBatch();expect(h.owner.error.value).toContain('请重新登录');expect(JSON.parse(h.store.getItem('turb_bulk_draft_v1')!).name).toBe('保留草稿');expect(h.owner.pendingCount.value).toBe(1);
 });
 it('卸载取消读取且不会在稍后继续创建',async()=>{
  const h=setup();const pending=deferred<unknown>();h.handlers.post=async()=>pending.promise;await h.owner.initialize();const writing=h.owner.createBatch();h.scope.stop();pending.resolve({id:'71',state:'ready',target_count:3});await writing;expect(h.calls.some(call=>call.path==='/batches')).toBe(false);expect(h.callbacks.navigate).not.toHaveBeenCalled();
 });
 it('隐藏中止UI读取，保留准备意图且外层重新显示刷新后继续',async()=>{
  const h=setup();let pendingRead=false;const pending=deferred<unknown>();h.handlers.read=async path=>path==='/catalog'?catalog():path.startsWith('/query-facets')?{facets:{},matched:3}:pendingRead?pending.promise:{id:'71',state:'preparing'};await h.owner.initialize();await h.owner.createBatch();pendingRead=true;const reading=h.owner.refresh();await nextTick();h.owner.setVisible(false);expect(h.calls.at(-1)?.options?.signal?.aborted).toBe(true);pending.resolve({id:'71',state:'ready',target_count:3,selection_revision:1});await reading;expect(h.calls.some(call=>call.path==='/batches')).toBe(false);expect(h.owner.creating.value).toBe(true);expect(h.owner.error.value).toBe('');h.owner.setVisible(true);await h.owner.refresh();expect(h.calls.filter(call=>call.path==='/batches')).toHaveLength(1);
 });
 it('隐藏挂载不预取目录/范围，显示后外层刷新只加载一次',async()=>{
  const h=setup();h.owner.setVisible(false);await h.owner.initialize();await h.owner.refresh();expect(h.calls).toHaveLength(0);h.owner.setVisible(true);await Promise.all([h.owner.refresh(),h.owner.initialize()]);expect(h.calls.filter(call=>call.path==='/catalog')).toHaveLength(1);
 });
});
