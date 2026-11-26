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
const offers=[
 {key:'offer-plus-half',plan:'plus',label:'Plus 半价 2个月',count:2,stale_count:1},
 {key:'offer-team-trial',plan:'team',label:'Team 免费 1个月',count:3,stale_count:0},
 {key:'offer-go-discount',plan:'go',label:'Go 减 25% 1个月',count:1,stale_count:0},
];
const state:DailyRegistrationStatsState={
 data:{
  ok:true,timezone:'Asia/Shanghai',date_from:'2026-11-20',date_to:'2026-11-26',
  updated_at:'2026-11-26T12:00:00+08:00',
  rows:[
   {date:'2026-11-20',total:8,counts:{success:5,failed:3},accounts_total:4,plans:{plus:2,free:2},offers,promoted_accounts_total:3,unpromoted_count:2,query:baseQuery},
   {date:'2026-11-21',total:0,counts:{},accounts_total:0,plans:{},offers:[],promoted_accounts_total:0,unpromoted_count:0,query:{...baseQuery,q:'注册任务日期:2026-11-21'}},
  ],
  summary:{total:8,accounts_total:4,unpromoted_count:2,offers,promoted_accounts_total:3,query:{...baseQuery,q:'注册任务日期:2026-11-20..2026-11-21'}},
 },
 loading:false,error:'',updatedAt:'2026-11-26T12:00:00+08:00',
 requestedRange:null,displayedRange:{from:'2026-11-20',to:'2026-11-26'},scopeCurrent:true,
 load:vi.fn(),
};

beforeEach(()=>{vi.useFakeTimers();});
afterEach(()=>{wrappers.splice(0).forEach(wrapper=>wrapper.unmount());vi.useRealTimers();});

describe('DailyRegistrationStats',()=>{
 it('shows all concrete plan offers for the selected day without registration result charts',async()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  expect(wrapper.get('[data-daily-range]').text()).toContain('2026-11-20');
  expect(wrapper.get('[data-daily-range]').text()).toContain('2026-11-26');
  expect(wrapper.text()).toContain('每日账号套餐优惠');
  expect(wrapper.text()).toContain('同一账号有多项优惠时分别计数');
  expect(wrapper.text()).toContain('每项按账号去重');
  expect(wrapper.find('[data-daily-view="status"]').exists()).toBe(false);
  const row=wrapper.get('[data-daily-row="2026-11-20"]');
  expect(row.text()).toContain('注册任务总数 8');
  expect(row.text()).toContain('账号总数（含归档） 4');
  expect(row.text()).toContain('有优惠账号 3');
  expect(row.text()).not.toContain('成功');
  expect(row.text()).not.toContain('失败');
  expect(row.text()).toContain('Team 免费 1个月');
  expect(row.text()).toContain('Plus 半价 2个月');
  expect(row.text()).toContain('Go 减 25% 1个月');
  expect(wrapper.findAll('[data-daily-row]')).toHaveLength(1);
  expect(wrapper.findAll('[data-daily-bar]')).toHaveLength(2);
  await wrapper.get('[data-daily-bar="2026-11-21"]').trigger('click');
  expect(wrapper.find('[data-daily-row="2026-11-20"]').exists()).toBe(false);
  expect(wrapper.get('[data-daily-row="2026-11-21"]').text()).toContain('注册任务总数 0');
  expect(wrapper.get('[data-daily-row="2026-11-21"]').text()).toContain('暂无可用优惠记录');
 });

 it('uses the deduplicated account total as every offer percentage denominator and marks stale offers',()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  const team=wrapper.get('[data-daily-offer="offer-team-trial"]');
  const plus=wrapper.get('[data-daily-offer="offer-plus-half"]');
  const go=wrapper.get('[data-daily-offer="offer-go-discount"]');
  expect(team.text()).toContain('3 个账号');
  expect(team.text()).toContain('75%');
  expect(plus.text()).toContain('2 个账号');
  expect(plus.text()).toContain('50%');
  expect(plus.text()).toContain('1 个待复查');
  expect(go.text()).toContain('25%');
  expect(team.text()).not.toContain('待复查');
  expect(wrapper.findAll('[data-daily-offer-group]').map(group=>group.attributes('data-daily-offer-group'))).toEqual(['team','plus','go']);
 });

 it('disables empty batches and sends only the unchanged server query and generated name',async()=>{
  const onBulkPlanCreate=vi.fn();
  const wrapper=mount(DailyRegistrationStats,{props:{state,onBulkPlanCreate}});
  wrappers.push(wrapper);
  await wrapper.get('[data-daily-bulk]').trigger('click');
  expect(onBulkPlanCreate).toHaveBeenCalledExactlyOnceWith({
   name:'2026-11-20 无优惠账号查套餐',query:baseQuery,
  });
  expect(wrapper.get('[data-daily-row]').text()).toContain('未归档 Plus 无优惠 2');
  await wrapper.get('[data-daily-bar="2026-11-21"]').trigger('click');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
  expect(wrapper.get('[data-daily-row]').text()).toContain('未归档 Plus 无优惠 0');
 });

 it('stacks all offer coverage against an absolute axis without counting the stack as unique accounts',()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  const bar=wrapper.get('[data-daily-bar="2026-11-20"]');
  expect(wrapper.get('[data-daily-axis]').text()).toContain('优惠覆盖数');
  expect(wrapper.findAll('[data-daily-axis-tick]').map(tick=>tick.text())).toEqual(['8','6','4','2','0']);
  expect(bar.get('[data-daily-segment="offer-team-trial"]').attributes('style')).toContain('height: 37.5%');
  expect(bar.get('[data-daily-segment="offer-plus-half"]').attributes('style')).toContain('height: 25%');
  expect(bar.get('[data-daily-segment="offer-go-discount"]').attributes('style')).toContain('height: 12.5%');
  expect(bar.attributes('aria-label')).toContain('优惠覆盖数 6');
  expect(bar.attributes('aria-label')).toContain('有优惠账号 3');
  expect(bar.attributes('aria-label')).toContain('Team 免费 1个月 3');
  expect(wrapper.get('[data-daily-bar="2026-11-21"]').findAll('[data-daily-segment]')).toHaveLength(0);
  expect(wrapper.get('[data-daily-bar="2026-11-21"]').text()).toContain('0');
  expect(wrapper.get('[data-daily-legend]').text()).toContain('Plus 半价 2个月');
 });

 it('shows each day account total beside separate offer coverage and offers the daily percentage on hover',()=>{
  const wrapper=mount(DailyRegistrationStats,{props:{state}});
  wrappers.push(wrapper);
  const first=wrapper.get('[data-daily-bar="2026-11-20"]');
  const empty=wrapper.get('[data-daily-bar="2026-11-21"]');
  expect(first.get('[data-daily-account-total]').text()).toBe('账号 4');
  expect(first.get('[data-daily-coverage-total]').text()).toBe('覆盖 6');
  expect(empty.get('[data-daily-account-total]').text()).toBe('账号 0');
  expect(empty.get('[data-daily-coverage-total]').text()).toBe('覆盖 0');
  expect(first.get('[data-daily-segment="offer-team-trial"]').attributes('title')).toBe('Team 免费 1个月 3个账号 · 75%（占当日账号）');
  expect(first.get('[data-daily-segment="offer-plus-half"]').attributes('title')).toBe('Plus 半价 2个月 2个账号 · 50%（占当日账号）');
  expect(wrapper.text()).toContain('优惠账号数 ÷ 当日账号总数');
  expect(wrapper.text()).toContain('多项占比合计可超过100%');
 });

 it('keeps offer order and color consistent across dates with different offer sizes',()=>{
  const chartState={...state,data:{...state.data!,rows:[
   state.data!.rows![0]!,
   {...state.data!.rows![1]!,accounts_total:4,offers:[...offers].reverse().map(item=>({...item,count:item.plan==='team'?1:3}))},
  ]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:chartState}});
  wrappers.push(wrapper);
  const first=wrapper.get('[data-daily-bar="2026-11-20"]');
  const second=wrapper.get('[data-daily-bar="2026-11-21"]');
  const expected=['offer-team-trial','offer-plus-half','offer-go-discount'];
  expect(first.findAll('[data-daily-segment]').map(segment=>segment.attributes('data-daily-segment'))).toEqual(expected);
  expect(second.findAll('[data-daily-segment]').map(segment=>segment.attributes('data-daily-segment'))).toEqual(expected);
  for(const key of expected){
   expect((first.get(`[data-daily-segment="${key}"]`).element as HTMLElement).style.backgroundColor)
    .toBe((second.get(`[data-daily-segment="${key}"]`).element as HTMLElement).style.backgroundColor);
  }
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
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[...state.data!.rows!]}}});
  expect(second.attributes('aria-pressed')).toBe('true');
  await second.trigger('keydown',{key:'Home'});
  expect(first.attributes('aria-pressed')).toBe('true');
  await first.trigger('keydown',{key:'End'});
  expect(second.attributes('aria-pressed')).toBe('true');
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[state.data!.rows![0]!]}}});
  expect(wrapper.find('[data-daily-row="2026-11-20"]').exists()).toBe(true);
 });

 it('distinguishes missing offer data from a confirmed empty array without drawing a fake bar',()=>{
  const unknown={...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,offers:null,promoted_accounts_total:null,unpromoted_count:null},state.data!.rows![1]!]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:unknown}});
  wrappers.push(wrapper);
  const pending=wrapper.get('[data-daily-bar="2026-11-20"]');
  expect(pending.attributes('aria-label')).toContain('优惠数据待查');
  expect(pending.get('[data-daily-account-total]').text()).toBe('账号 4');
  expect(pending.get('[data-daily-coverage-total]').text()).toBe('覆盖 待查');
  expect(pending.findAll('[data-daily-segment]')).toHaveLength(0);
  expect(wrapper.get('[data-daily-row]').text()).toContain('优惠数据待查');
  expect(wrapper.get('[data-daily-row]').text()).toContain('有优惠账号 —');
  expect(wrapper.get('[data-daily-row]').text()).toContain('Plus 无优惠 待查');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
  expect(wrapper.get('[data-daily-bar="2026-11-21"]').attributes('aria-label')).not.toContain('待查');
 });

 it('keeps a pending legend when offer data is unavailable and does not fall back to subscription or status counts',()=>{
  const unknown={...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,offers:undefined,accounts_total:null}]}};
  const wrapper=mount(DailyRegistrationStats,{props:{state:unknown}});
  wrappers.push(wrapper);
  expect(wrapper.get('[data-daily-legend]').text()).toContain('优惠数据待查');
  expect(wrapper.get('[data-daily-legend]').text()).not.toContain('暂无可用优惠记录');
  expect(wrapper.get('[data-daily-bar="2026-11-20"]').findAll('[data-daily-segment]')).toHaveLength(0);
  expect(wrapper.text()).not.toContain('成功 5');
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
