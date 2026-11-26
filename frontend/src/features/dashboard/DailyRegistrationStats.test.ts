import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import DailyRegistrationStats from './DailyRegistrationStats.vue';
import type {DailyRegistrationStatsState} from './contracts';
import type {AccountQuerySpec} from '../accounts/queryAdapter';

const wrappers:ReturnType<typeof mount>[]=[];
const baseQuery:AccountQuerySpec={
 schema_version:1,
 entity:'account',
 archived:'0',
 q:'注册任务日期:2026-11-20..2026-11-26',
 date_from:'',
 date_to:'',
 plan:[],
 filters:{
  id:'',email:'',source:[],registration_driver:[],token:[],password:[],
  promotion:['none'],totp:[],risk:[],codex:[],account_status:[],email_status:[],
 },
 order:[{field:'id',direction:'desc'}],
 limit:null,
};
const state:DailyRegistrationStatsState={
 data:{
  ok:true,timezone:'Asia/Shanghai',date_from:'2026-11-20',date_to:'2026-11-26',
  updated_at:'2026-11-26T12:00:00+08:00',
  rows:[
   {date:'2026-11-20',total:2,counts:{success:1,partial_success:1,failed:0,running:0,pending:1,queued:2,stopping:1,cancelled:0,stopped:1,interrupted:1,unsupported:2,deactivated:1,mystery_status:3},accounts_total:3,plans:{plus:2,free:1},unpromoted_count:2,query:baseQuery},
   {date:'2026-11-21',total:0,counts:{},accounts_total:0,plans:{},unpromoted_count:0,query:{...baseQuery,q:'注册任务日期:2026-11-21'}},
  ],
  summary:{total:2,accounts_total:3,unpromoted_count:2,counts:{success:1,partial_success:1,failed:0,running:0,cancelled:0},plans:{plus:2,free:1},query:{...baseQuery,q:'注册任务日期:2026-11-20..2026-11-21'}},
 },
 loading:false,error:'',updatedAt:'2026-11-26T12:00:00+08:00',
 requestedRange:null,displayedRange:{from:'2026-11-20',to:'2026-11-26'},scopeCurrent:true,
 load:vi.fn(),
};

beforeEach(()=>{vi.useFakeTimers();});
afterEach(()=>{wrappers.splice(0).forEach(wrapper=>wrapper.unmount());vi.useRealTimers();});

describe('DailyRegistrationStats',()=>{
 it('uses the server date range, renders daily counts and plan distribution',()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  expect(wrapper.get('[data-daily-range]').text()).toContain('2026-11-20');
  expect(wrapper.get('[data-daily-range]').text()).toContain('2026-11-26');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('成功 1');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('部分成功 1');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('进行中 4');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('取消 1');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('Plus 2 · 67%');
  expect(wrapper.get('[data-daily-row="2026-11-21"]').text()).toContain('总数 0');
  expect(wrapper.findAll('[data-daily-bar]')).toHaveLength(2);
 });

 it('shows nonzero interrupted and terminal special states without exposing unknown raw keys',()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  const row=wrapper.get('[data-daily-row="2026-11-20"]');
  expect(row.text()).toContain('执行中断 1');
  expect(row.text()).toContain('不支持 2');
  expect(row.text()).toContain('已停用 1');
  expect(row.text()).not.toContain('mystery_status');
 });

 it('shows explicitly unavailable groups as pending instead of silently displaying zero',()=>{
  const unknown={...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,counts:null,plans:null,unpromoted_count:null}]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:unknown}});
  wrappers.push(wrapper);
  const row=wrapper.get('[data-daily-row="2026-11-20"]');
  expect(row.text()).toContain('成功 —');
  expect(row.text()).toContain('套餐待查');
  expect(row.text()).toContain('无优惠 待查');
 });

 it('disables empty batches and sends only the server query and generated name',async()=>{
  const onBulkPlanCreate=vi.fn();
  const wrapper=mount(DailyRegistrationStats,{props:{state,onBulkPlanCreate}});
  wrappers.push(wrapper);
  const rows=wrapper.findAll('[data-daily-row]');
  const first=rows[0]!;
  await first.get('[data-daily-bulk]').trigger('click');
  expect(onBulkPlanCreate).toHaveBeenCalledExactlyOnceWith({
   name:'2026-11-20 无优惠账号查套餐',query:baseQuery,
  });
  expect(rows[1]!.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
  expect(rows[1]!.text()).toContain('未归档无优惠 0');
 });

 it('keeps old data visible during a local error and retries the daily read',async()=>{
  const load=vi.fn();
  const errorState={...state,error:'统计暂不可用',load};
  const wrapper=mount(DailyRegistrationStats,{props:{state:errorState}});
  wrappers.push(wrapper);
  expect(wrapper.get('[data-daily-error]').text()).toContain('统计暂不可用');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').element).toBeTruthy();
  await wrapper.get('[data-daily-retry]').trigger('click');
  expect(load).toHaveBeenCalledOnce();
 });

 it('blocks daily and interval batch actions while a changed range is pending or failed, then restores both after success',async()=>{
  const onBulkPlanCreate=vi.fn();
  const pendingState={...state,loading:true,scopeCurrent:false,requestedRange:{from:'2026-11-01',to:'2026-11-30'}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:pendingState,onBulkPlanCreate}});
  wrappers.push(wrapper);
  expect(wrapper.get('[data-daily-stale]').text()).toContain('正在读取新日期范围');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
  expect(wrapper.get('[data-daily-summary-bulk]').attributes('disabled')).toBeDefined();
  await wrapper.get('[data-daily-bulk]').trigger('click');
  await wrapper.get('[data-daily-summary-bulk]').trigger('click');
  expect(onBulkPlanCreate).not.toHaveBeenCalled();

  await wrapper.setProps({state:{...pendingState,loading:false,error:'统计暂不可用'}});
  expect(wrapper.get('[data-daily-stale]').text()).toContain('读取失败');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
  expect(wrapper.get('[data-daily-summary-bulk]').attributes('disabled')).toBeDefined();

  await wrapper.setProps({state:{...state,load:vi.fn(),scopeCurrent:true,error:''},onBulkPlanCreate});
  await wrapper.get('[data-daily-bulk]').trigger('click');
  await wrapper.get('[data-daily-summary-bulk]').trigger('click');
  expect(onBulkPlanCreate).toHaveBeenCalledTimes(2);
 });

 it('requests a new range after switching to 30 days and never uses a selection request',async()=>{
  const load=vi.fn();
  const wrapper=mount(DailyRegistrationStats,{props:{state:{...state,load}}});
  wrappers.push(wrapper);
  await wrapper.get('[data-daily-range-30]').trigger('click');
  await flushPromises();
  expect(load).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/));
  expect(wrapper.html()).not.toContain('data-daily-selection-request');
 });

 it('anchors preset ranges to the current Beijing day instead of the previous response end',async()=>{
  vi.setSystemTime(new Date('2026-12-15T01:00:00Z'));
  const load=vi.fn();
  const wrapper=mount(DailyRegistrationStats,{props:{state:{...state,load}}});
  wrappers.push(wrapper);
  await wrapper.get('[data-daily-range-30]').trigger('click');
  expect(load).toHaveBeenCalledWith('2026-11-16','2026-12-15');
 });
});
