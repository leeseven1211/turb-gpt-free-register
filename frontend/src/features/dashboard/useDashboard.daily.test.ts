import {defineComponent,h} from 'vue';
import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import type {DashboardApi} from '../../api/dashboard';
import {useDashboard} from './useDashboard';

let wrapper:ReturnType<typeof mount>|undefined;
beforeEach(()=>Object.defineProperty(document,'hidden',{configurable:true,value:false}));
afterEach(()=>wrapper?.unmount());

describe('useDashboard daily registration owner',()=>{
 it('keeps the selected range for an unparameterized retry and coalesces the same slow read',async()=>{
  const calls:Array<[string|undefined,string|undefined]>=[];
  let resolve!: (value:unknown)=>void;
  const api:DashboardApi={
   dashboard:async()=>({}),
   capabilities:async()=>({}),
   extractSummary:async()=>({}),
   registrationDaily:vi.fn((from,to)=>{calls.push([from,to]);return new Promise(done=>{resolve=done;});}),
  };
  let owner!:ReturnType<typeof useDashboard>;
  const Host=defineComponent({setup(){owner=useDashboard(api,{visible:true});return()=>h('div');}});
  wrapper=mount(Host);
  expect(calls).toHaveLength(1);
  resolve({ok:true,date_from:'2026-11-20',date_to:'2026-11-26',rows:[]});
  await flushPromises();
  const first=owner.loadDaily('2026-10-01','2026-10-02');
  const retry=owner.loadDaily();
  expect(retry).toBe(first);
  expect(calls.at(-1)).toEqual(['2026-10-01','2026-10-02']);
  resolve({ok:true,date_from:'2026-10-01',date_to:'2026-10-02',rows:[]});
  await first;
  const retained=owner.loadDaily();
  expect(calls.at(-1)).toEqual(['2026-10-01','2026-10-02']);
  resolve({ok:true,date_from:'2026-10-01',date_to:'2026-10-02',rows:[]});
  await retained;
 });

 it('marks a changed range stale until success and keeps the old scope usable on same-range failure',async()=>{
  let settle!: {resolve:(value:unknown)=>void;reject:(reason:unknown)=>void};
  const api:DashboardApi={
   dashboard:async()=>({}),
   capabilities:async()=>({}),
   extractSummary:async()=>({}),
   registrationDaily:vi.fn((from,to)=>new Promise((resolve,reject)=>{
    settle={resolve,reject};
   })),
  };
  let owner!:ReturnType<typeof useDashboard>;
  const Host=defineComponent({setup(){owner=useDashboard(api,{visible:true});return()=>h('div');}});
  wrapper=mount(Host);
  settle.resolve({ok:true,date_from:'2026-11-20',date_to:'2026-11-26',rows:[]});
  await flushPromises();

  const changed=owner.loadDaily('2026-11-01','2026-11-30');
  expect(owner.dailyScopeCurrent.value).toBe(false);
  settle.resolve({ok:true,date_from:'2026-11-01',date_to:'2026-11-30',rows:[]});
  await changed;
  expect(owner.dailyScopeCurrent.value).toBe(true);

  const same=owner.loadDaily();
  expect(owner.dailyScopeCurrent.value).toBe(true);
  settle.reject(new Error('统计暂不可用'));
  await same;
  expect(owner.dailyScopeCurrent.value).toBe(true);
  expect(owner.dailyError.value).toBe('统计暂不可用');
 });
});
