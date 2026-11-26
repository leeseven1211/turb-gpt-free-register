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
 it('uses the server date range and shows one selected day with counts and plan distribution',async()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  expect(wrapper.get('[data-daily-range]').text()).toContain('2026-11-20');
  expect(wrapper.get('[data-daily-range]').text()).toContain('2026-11-26');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('成功 1');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('部分成功 1');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('进行中 4');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('取消 1');
  expect(wrapper.get('[data-daily-row="2026-11-20"]').text()).toContain('Plus 2 · 67%');
  expect(wrapper.findAll('[data-daily-row]')).toHaveLength(1);
  expect(wrapper.findAll('[data-daily-bar]')).toHaveLength(2);
  await wrapper.get('[data-daily-bar="2026-11-21"]').trigger('click');
  expect(wrapper.find('[data-daily-row="2026-11-20"]').exists()).toBe(false);
  expect(wrapper.get('[data-daily-row="2026-11-21"]').text()).toContain('总数 0');
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
  await wrapper.get('[data-daily-bulk]').trigger('click');
  expect(onBulkPlanCreate).toHaveBeenCalledExactlyOnceWith({
   name:'2026-11-20 无优惠账号查套餐',query:baseQuery,
  });
  await wrapper.get('[data-daily-bar="2026-11-21"]').trigger('click');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
  expect(wrapper.get('[data-daily-row]').text()).toContain('未归档无优惠 0');
 });

 it('stacks known status groups against an absolute count axis and leaves zero dates without a bar',()=>{
  const chartState={...state,data:{...state.data!,rows:[
   {...state.data!.rows![0]!,total:20,counts:{success:4,partial_success:2,failed:3,pending:1,queued:2,running:2,cancelled:2,stopped:1,interrupted:1,unsupported:1,deactivated:1}},
   state.data!.rows![1]!,
  ]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:chartState}});
  wrappers.push(wrapper);
  const bar=wrapper.get('[data-daily-bar="2026-11-20"]');
  expect(wrapper.get('[data-daily-axis]').text()).toContain('任务数');
  expect(wrapper.findAll('[data-daily-axis-tick]').map(tick=>tick.text())).toEqual(['20','15','10','5','0']);
  expect(bar.get('[data-daily-segment="success"]').attributes('style')).toContain('height: 20%');
  expect(bar.get('[data-daily-segment="active"]').attributes('style')).toContain('height: 25%');
  expect(bar.get('[data-daily-segment="cancelled"]').attributes('style')).toContain('height: 15%');
  expect(bar.attributes('aria-label')).toContain('成功 4');
  expect(bar.attributes('aria-label')).toContain('进行中 5');
  expect(wrapper.get('[data-daily-bar="2026-11-21"]').findAll('[data-daily-segment]')).toHaveLength(0);
  expect(wrapper.get('[data-daily-bar="2026-11-21"]').text()).toContain('0');
  expect(wrapper.get('[data-daily-legend]').text()).toContain('部分成功');
 });

 it('switches to daily plan stacks using account counts and preserves the selected day without submitting a batch',async()=>{
  const load=vi.fn();
  const onBulkPlanCreate=vi.fn();
  const wrapper=mount(DailyRegistrationStats,{props:{state:{...state,load},onBulkPlanCreate}});
  wrappers.push(wrapper);
  await wrapper.get('[data-daily-view="plans"]').trigger('click');
  expect(wrapper.get('[data-daily-view="plans"]').attributes('aria-pressed')).toBe('true');
  expect(wrapper.get('[data-daily-axis]').text()).toContain('账号数');
  expect(wrapper.get('[data-daily-bar="2026-11-20"]').get('[data-daily-segment="plus"]').attributes('style')).toContain('height: 50%');
  expect(wrapper.get('[data-daily-legend]').text()).toContain('Plus');
  expect(wrapper.find('[data-daily-row="2026-11-20"]').exists()).toBe(true);
  expect(load).not.toHaveBeenCalled();
  expect(onBulkPlanCreate).not.toHaveBeenCalled();
 });

 it('keeps plan stack order consistent across dates even when the largest plan changes',async()=>{
  const chartState={...state,data:{...state.data!,rows:[
   state.data!.rows![0]!,
   {...state.data!.rows![1]!,accounts_total:4,plans:{free:3,plus:1}},
  ]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:chartState}});
  wrappers.push(wrapper);
  await wrapper.get('[data-daily-view="plans"]').trigger('click');
  expect(wrapper.get('[data-daily-bar="2026-11-20"]').findAll('[data-daily-segment]').map(segment=>segment.attributes('data-daily-segment'))).toEqual(['free','plus']);
  expect(wrapper.get('[data-daily-bar="2026-11-21"]').findAll('[data-daily-segment]').map(segment=>segment.attributes('data-daily-segment'))).toEqual(['free','plus']);
 });

 it('supports keyboard date selection and preserves it until a new range removes the date',async()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  const first=wrapper.get('[data-daily-bar="2026-11-20"]');
  expect(first.attributes('tabindex')).toBe('0');
  await first.trigger('keydown',{key:'ArrowRight'});
  const second=wrapper.get('[data-daily-bar="2026-11-21"]');
  expect(second.attributes('aria-pressed')).toBe('true');
  expect(second.attributes('tabindex')).toBe('0');
  expect(wrapper.find('[data-daily-row="2026-11-21"]').exists()).toBe(true);
  await wrapper.get('[data-daily-view="plans"]').trigger('click');
  expect(second.attributes('aria-pressed')).toBe('true');
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[...state.data!.rows!]}}});
  expect(second.attributes('aria-pressed')).toBe('true');
  await second.trigger('keydown',{key:'Home'});
  expect(first.attributes('aria-pressed')).toBe('true');
  await first.trigger('keydown',{key:'End'});
  expect(second.attributes('aria-pressed')).toBe('true');
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[state.data!.rows![0]!]}}});
  expect(wrapper.find('[data-daily-row="2026-11-20"]').exists()).toBe(true);
 });

 it('labels unavailable chart data as pending while keeping known zero separate',async()=>{
  const unknown={...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,counts:null,plans:null,unpromoted_count:null},state.data!.rows![1]!]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:unknown}});
  wrappers.push(wrapper);
  expect(wrapper.get('[data-daily-bar="2026-11-20"]').attributes('aria-label')).toContain('状态待查');
  expect(wrapper.get('[data-daily-bar="2026-11-20"]').find('[data-daily-segment="unavailable"]').exists()).toBe(true);
  await wrapper.get('[data-daily-view="plans"]').trigger('click');
  expect(wrapper.get('[data-daily-bar="2026-11-20"]').attributes('aria-label')).toContain('套餐待查');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
  expect(wrapper.get('[data-daily-bar="2026-11-21"]').findAll('[data-daily-segment]')).toHaveLength(0);
 });

 it('keeps a pending plan legend when both the plan distribution and account total are unavailable',async()=>{
  const unknown={...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,counts:null,plans:null,accounts_total:null}]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:unknown}});
  wrappers.push(wrapper);
  await wrapper.get('[data-daily-view="plans"]').trigger('click');
  expect(wrapper.get('[data-daily-legend]').text()).toContain('套餐待查');
  expect(wrapper.get('[data-daily-legend]').text()).not.toContain('暂无套餐账号');
  expect(wrapper.get('[data-daily-bar="2026-11-20"]').findAll('[data-daily-segment]')).toHaveLength(0);
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
