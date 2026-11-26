import {defineComponent,h} from 'vue';
import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import type {DashboardApi} from '../../api/dashboard';
import type {DashboardDeps} from './contracts';
import {DASHBOARD_POLL_MS,useDashboard} from './useDashboard';

function deferred(){
 let resolve!:(value:any)=>void,reject!:(reason:unknown)=>void;
 const promise=new Promise<any>((done,fail)=>{resolve=done;reject=fail;});
 return {promise,resolve,reject};
}

const wrappers:ReturnType<typeof mount>[]=[];
function setup(api:DashboardApi,deps:DashboardDeps={}){
 let owner!:ReturnType<typeof useDashboard>;
 const Host=defineComponent({setup(){owner=useDashboard(api,{visible:true,...deps});return()=>h('div');}});
 const wrapper=mount(Host);
 wrappers.push(wrapper);
 return {owner,wrapper};
}

beforeEach(()=>{
 vi.useFakeTimers();
 Object.defineProperty(document,'hidden',{configurable:true,value:false});
});
afterEach(()=>{
 wrappers.splice(0).forEach(wrapper=>wrapper.unmount());
 vi.useRealTimers();
});

describe('useDashboard independent response timing',()=>{
 it('publishes core data and ends loading before either auxiliary read settles',async()=>{
  const dashboard=deferred(),capabilities=deferred(),extract=deferred();
  const onReady=vi.fn(),onCapabilities=vi.fn(),notify=vi.fn();
  const {owner}=setup({
   dashboard:()=>dashboard.promise,
   capabilities:()=>capabilities.promise,
   extractSummary:()=>extract.promise,
  },{onReady,onCapabilities,notify});
  const wholeLoad=owner.load();
  let settled=false;
  void wholeLoad.then(()=>{settled=true;});

  dashboard.resolve({accounts:{active:10}});
  await flushPromises();
  expect(owner.data.value).toEqual({accounts:{active:10}});
  expect(owner.loading.value).toBe(false);
  expect(owner.error.value).toBe('');
  expect(onReady).toHaveBeenCalledOnce();
  expect(owner.updatedAt.value).not.toBeNull();
  const updatedAt=owner.updatedAt.value;
  expect(settled).toBe(false);

  capabilities.resolve({features:{register:{enabled:false}}});
  await flushPromises();
  expect(owner.caps.value).toEqual({features:{register:{enabled:false}}});
  expect(onCapabilities).toHaveBeenCalledExactlyOnceWith({features:{register:{enabled:false}}});
  expect(owner.extract.value).toBeNull();
  expect(settled).toBe(false);

  extract.resolve({ok:true,today_extracted:7,all:42,providers:[]});
  await wholeLoad;
  expect(owner.extract.value.today_extracted).toBe(7);
  expect(owner.extract.value.all).toBe(42);
  expect(owner.updatedAt.value).toBe(updatedAt);
  expect(onReady).toHaveBeenCalledOnce();
  expect(notify).not.toHaveBeenCalled();
 });

 it('coalesces the whole refresh without restoring core loading while auxiliaries are pending',async()=>{
  const dashboard=deferred(),capabilities=deferred(),extract=deferred();
  const read=vi.fn(()=>dashboard.promise),dailyRead=vi.fn(async()=>({ok:true,rows:[]}));
  const {owner}=setup({
   dashboard:read,capabilities:()=>capabilities.promise,extractSummary:()=>extract.promise,
   registrationDaily:dailyRead,
  });
  const first=owner.load();
  expect(owner.load()).toBe(first);
  expect(owner.loading.value).toBe(true);
  dashboard.resolve({accounts:{active:10}});
  await flushPromises();

  expect(owner.load()).toBe(first);
  expect(owner.loading.value).toBe(false);
  await vi.advanceTimersByTimeAsync(DASHBOARD_POLL_MS*2);
  expect(read).toHaveBeenCalledOnce();
  expect(dailyRead).toHaveBeenCalledOnce();
  expect(owner.loading.value).toBe(false);

  capabilities.resolve({});
  extract.resolve(null);
  await first;
  await vi.advanceTimersByTimeAsync(DASHBOARD_POLL_MS);
  await flushPromises();
  expect(read).toHaveBeenCalledTimes(2);
  expect(dailyRead).toHaveBeenCalledTimes(2);
  expect(owner.loading.value).toBe(false);
 });

 it('reports core failure immediately while auxiliary completion keeps that error intact',async()=>{
  const dashboard=deferred(),capabilities=deferred(),extract=deferred();
  const notify=vi.fn(),onReady=vi.fn();
  const {owner}=setup({
   dashboard:()=>dashboard.promise,capabilities:()=>capabilities.promise,extractSummary:()=>extract.promise,
  },{notify,onReady});
  const pending=owner.load();
  dashboard.reject(new Error('总览读取超时'));
  await flushPromises();
  expect(owner.error.value).toBe('总览读取超时');
  expect(owner.loading.value).toBe(false);
  expect(notify).toHaveBeenCalledExactlyOnceWith('总览加载失败：总览读取超时');
  expect(owner.load()).toBe(pending);
  expect(owner.loading.value).toBe(false);

  capabilities.resolve({features:{register:{enabled:false}}});
  extract.resolve({ok:true,today_extracted:7,providers:[]});
  await pending;
  expect(owner.error.value).toBe('总览读取超时');
  expect(owner.caps.value.features.register.enabled).toBe(false);
  expect(owner.extract.value.today_extracted).toBe(7);
  expect(owner.updatedAt.value).toBeNull();
  expect(onReady).not.toHaveBeenCalled();
  expect(notify).toHaveBeenCalledOnce();
 });

 it('keeps successful core data when auxiliaries fail without a failure notification',async()=>{
  const dashboard=deferred(),capabilities=deferred(),extract=deferred();
  const notify=vi.fn();
  const {owner}=setup({
   dashboard:()=>dashboard.promise,capabilities:()=>capabilities.promise,extractSummary:()=>extract.promise,
  },{notify});
  const pending=owner.load();
  dashboard.resolve({accounts:{active:10}});
  await flushPromises();
  expect(owner.data.value.accounts.active).toBe(10);
  capabilities.reject(new Error('能力读取失败'));
  extract.reject(new Error('提炼读取失败'));
  await pending;
  expect(owner.error.value).toBe('');
  expect(owner.caps.value).toEqual({});
  expect(owner.extract.value).toBeNull();
  expect(notify).not.toHaveBeenCalled();
 });

 it.each(['route-hidden','document-hidden','unmount'])('discards late auxiliary responses after %s',async mode=>{
  const capabilities=deferred(),extract=deferred();
  const onCapabilities=vi.fn();
  let signal!:AbortSignal;
  const {owner,wrapper}=setup({
   dashboard:async()=>({accounts:{active:10}}),
   capabilities:nextSignal=>{signal=nextSignal!;return capabilities.promise;},
   extractSummary:()=>extract.promise,
  },{onCapabilities});
  const pending=owner.load();
  await flushPromises();
  expect(owner.data.value.accounts.active).toBe(10);
  if(mode==='route-hidden')owner.setVisible(false);
  else if(mode==='document-hidden'){
   Object.defineProperty(document,'hidden',{configurable:true,value:true});
   document.dispatchEvent(new Event('visibilitychange'));
  }else{
   wrapper.unmount();
   wrappers.splice(wrappers.indexOf(wrapper),1);
  }
  expect(signal.aborted).toBe(true);
  capabilities.resolve({features:{register:{enabled:false}}});
  extract.resolve({ok:true,today_extracted:999,providers:[]});
  await pending;
  expect(owner.caps.value).toEqual({});
  expect(owner.extract.value).toBeNull();
  expect(onCapabilities).not.toHaveBeenCalled();
  expect(owner.loading.value).toBe(false);
 });

 it('prevents old auxiliaries and finalizers from overwriting a newer visible request',async()=>{
  const oldCaps=deferred(),oldExtract=deferred(),nextDash=deferred(),nextCaps=deferred(),nextExtract=deferred();
  const onCapabilities=vi.fn();
  const {owner}=setup({
   dashboard:vi.fn().mockResolvedValueOnce({accounts:{active:10}}).mockImplementation(()=>nextDash.promise),
   capabilities:vi.fn().mockImplementationOnce(()=>oldCaps.promise).mockImplementation(()=>nextCaps.promise),
   extractSummary:vi.fn().mockImplementationOnce(()=>oldExtract.promise).mockImplementation(()=>nextExtract.promise),
  },{onCapabilities});
  const oldLoad=owner.load();
  await flushPromises();
  owner.setVisible(false);
  owner.setVisible(true);
  const newLoad=owner.load();
  expect(owner.loading.value).toBe(true);
  oldCaps.resolve({features:{register:{enabled:false}}});
  oldExtract.resolve({ok:true,today_extracted:999,providers:[]});
  await oldLoad;
  expect(owner.load()).toBe(newLoad);
  expect(owner.loading.value).toBe(true);
  expect(owner.caps.value).toEqual({});
  expect(owner.extract.value).toBeNull();
  expect(onCapabilities).not.toHaveBeenCalled();

  nextDash.resolve({accounts:{active:20}});
  nextCaps.resolve({features:{register:{enabled:true}}});
  nextExtract.resolve({ok:true,today_extracted:8,providers:[]});
  await newLoad;
  expect(owner.data.value.accounts.active).toBe(20);
  expect(owner.caps.value.features.register.enabled).toBe(true);
  expect(owner.extract.value.today_extracted).toBe(8);
  expect(onCapabilities).toHaveBeenCalledOnce();
  expect(owner.loading.value).toBe(false);
 });
});
