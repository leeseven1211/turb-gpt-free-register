import {effectScope,nextTick} from 'vue';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {useProxyTraffic} from './useProxyTraffic';
import type {ProxyTrafficApi,ProxyQuery,ProxyRecordView,ProxyRow,ProxySummary,ProxyPoolSnapshot} from './contracts';
const scopes:ReturnType<typeof effectScope>[]=[];
function page(items:ProxyRow[]=[{id:1,lease_id:'lease-1'}],total=80,offset=0,limit=20){return{items,count:items.length,total,offset,limit,has_more:offset+items.length<total};}
function setup(){
 const requests:{view:ProxyRecordView;query:ProxyQuery;signal?:AbortSignal}[]=[];
 let read=(view:ProxyRecordView,query:ProxyQuery,_signal?:AbortSignal)=>Promise.resolve(page([{id:1,lease_id:view}],80,(query.page-1)*query.size,query.size));
 const api:ProxyTrafficApi={page:(view,query,signal)=>{requests.push({view,query:{...query},signal});return read(view,query,signal);},summary:vi.fn(async()=>({ok:true,total_bytes:1024,today_bytes:100,today_request_count:0,today_browser_count:7,today_route_count:3,purposes:['plan-check'],lease_states:['leased','released']})),pool:vi.fn(async()=>null)};
 const scope=effectScope();scopes.push(scope);const owner=scope.run(()=>useProxyTraffic({api}))!;
 return{owner,requests,api,setRead:(fn:typeof read)=>{read=fn;}};
}
async function settle(){await nextTick();for(let i=0;i<16;i++)await Promise.resolve();await nextTick();}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(yes=>{resolve=yes;});return{resolve,promise};}
beforeEach(()=>{vi.useFakeTimers();Object.defineProperty(document,'hidden',{configurable:true,value:false});});
afterEach(()=>{scopes.splice(0).forEach(scope=>scope.stop());vi.useRealTimers();});
describe('single proxy read owner',()=>{
 it('does no hidden read, coalesces first visible load and polls only while visible',async()=>{
  const h=setup();await h.owner.load();expect(h.requests).toHaveLength(0);
  h.owner.setVisible(true);await Promise.all([h.owner.load(),h.owner.load()]);await settle();expect(h.requests).toHaveLength(3);expect(h.requests[0]!.query).toEqual({page:1,size:20,window:'all',purpose:'all',state:'all',search:''});
  await vi.advanceTimersByTimeAsync(30000);await settle();expect(h.requests).toHaveLength(6);
  h.owner.setVisible(false);await vi.advanceTimersByTimeAsync(60000);expect(h.requests).toHaveLength(6);
 });
 it('an initial targeted update still initializes all lists and global facets',async()=>{
  const h=setup(),old=deferred<ReturnType<typeof page>>();h.setRead(()=>old.promise);h.owner.setVisible(true);await settle();h.owner.setState('history','released');
  h.setRead((view,q)=>Promise.resolve(page([{id:2,lease_id:view}],1,0,q.size)));await settle();expect(h.requests.slice(3).map(r=>r.view)).toEqual(['current','history','traffic']);expect(h.owner.summary.value?.total_bytes).toBe(1024);
  old.resolve(page([{id:99}]));await settle();expect(h.owner.pages.current.items[0]?.id).toBe(2);
 });
 it('does not start a correction read after the page becomes hidden',async()=>{
  const h=setup();h.owner.setVisible(true);await settle();const late=deferred<ReturnType<typeof page>>();h.setRead(()=>late.promise);h.owner.setPage('history',4);await settle();const before=h.requests.length;h.owner.setVisible(false);late.resolve(page([],1,60));await settle();expect(h.requests).toHaveLength(before);
 });
 it('late summary and pool cannot publish after hiding',async()=>{
  const h=setup(),metrics=deferred<ProxySummary>(),inventory=deferred<ProxyPoolSnapshot|null>();h.api.summary=()=>metrics.promise;h.api.pool=()=>inventory.promise;h.owner.setVisible(true);await settle();h.owner.setVisible(false);metrics.resolve({total_bytes:999,today_bytes:999});inventory.resolve({policy:{},counts:{ready:99}});await settle();expect(h.owner.summary.value).toBeNull();expect(h.owner.pool.value).toBeNull();expect(h.owner.loading.value).toBe(false);
 });
 it('shares search/window/purpose but keeps state and pages per view',async()=>{
  const h=setup();h.owner.setVisible(true);await settle();h.requests.length=0;
  h.owner.updateFilters({search:' token ',purpose:'plan-check',window:'24h'});await vi.advanceTimersByTimeAsync(260);await settle();
  expect(h.requests).toHaveLength(3);expect(h.requests.find(r=>r.view==='history')!.query).toMatchObject({search:' token ',purpose:'plan-check',window:'24h',page:1});
  h.requests.length=0;h.owner.setState('history','released');await settle();expect(h.requests.map(r=>r.view)).toEqual(['history']);expect(h.requests[0]!.query.state).toBe('released');expect(h.owner.pages.traffic.state).toBe('all');
 });
 it('invalidates immediately during debounce so late old lists, summary and pool cannot commit',async()=>{
  const h=setup(),old=deferred<ReturnType<typeof page>>();h.setRead(()=>old.promise);h.owner.setVisible(true);await settle();
  h.owner.updateFilters({search:'new'});expect(h.requests[0]!.signal?.aborted).toBe(true);
  old.resolve(page([{id:99,lease_id:'stale'}]));await settle();expect(h.owner.pages.current.items).toEqual([]);expect(h.owner.summary.value).toBeNull();
  h.setRead((view,query)=>Promise.resolve(page([{id:2,lease_id:view+'-new'}],1,0,query.size)));await vi.advanceTimersByTimeAsync(260);await settle();
  expect(h.owner.pages.current.items[0]?.id).toBe(2);expect(h.owner.summary.value?.today_request_count).toBe(0);
 });
 it('hiding/document hiding aborts reads and a return refreshes once with final filters',async()=>{
  const h=setup(),old=deferred<ReturnType<typeof page>>();h.setRead(()=>old.promise);h.owner.setVisible(true);await settle();
  Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));expect(h.requests[0]!.signal?.aborted).toBe(true);
  h.owner.updateFilters({window:'7d'});old.resolve(page([{id:88}]));await settle();expect(h.owner.pages.current.items).toEqual([]);
  h.setRead((_v,q)=>Promise.resolve(page([{id:3}],1,0,q.size)));Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));await settle();
  expect(h.requests).toHaveLength(6);expect(h.owner.pages.current.items[0]?.id).toBe(3);
 });
 it('corrects a shrinking final page once and resets page on size/filter changes',async()=>{
  const h=setup();h.owner.setVisible(true);await settle();h.requests.length=0;
  h.setRead((_view,q)=>Promise.resolve(page(q.page===2?[{id:22}]:[],21,(q.page-1)*q.size,q.size)));
  h.owner.setPage('history',4);await settle();expect(h.requests.map(r=>r.query.page)).toEqual([4,2]);expect(h.owner.pages.history.page).toBe(2);
  h.requests.length=0;h.owner.setPage('history',1);h.owner.setSize('history',50);await settle();expect(h.requests).toHaveLength(1);expect(h.requests[0]!.query).toMatchObject({page:1,size:50});
 });
 it('freezes the opened record across poll/filter/page and closes on module or subview navigation',async()=>{
  const h=setup();h.owner.setVisible(true);await settle();h.owner.openDetail('history',h.owner.pages.history.items[0]!);expect(h.owner.detail.value?.row.lease_id).toBe('history');
  h.owner.pages.history.items[0]!.lease_id='mutated';await h.owner.load();expect(h.owner.detail.value?.row.lease_id).toBe('history');
  h.owner.setRecordView('traffic');expect(h.owner.detail.value).toBeNull();h.owner.openDetail('traffic',{id:5});h.owner.setView('records');h.owner.setView('pool');expect(h.owner.detail.value).toBeNull();
 });
 it('clears all mandatory snapshots on a current failure and leaves optional pool unavailable',async()=>{
  const h=setup();h.owner.setVisible(true);await settle();h.setRead(()=>Promise.reject(new Error('fixture offline')));await h.owner.load('history');
  expect(h.owner.pages.current.items).toEqual([]);expect(h.owner.summary.value).toBeNull();expect(h.owner.error.value).toBe('fixture offline');
 });
});
