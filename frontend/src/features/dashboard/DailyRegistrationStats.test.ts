import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import DailyRegistrationStats from './DailyRegistrationStats.vue';
import type {DailyRegistrationStatsState} from './contracts';
import type {AccountQuerySpec} from '../accounts/queryAdapter';

const wrappers:ReturnType<typeof mount>[]=[];
const baseQuery:AccountQuerySpec={
 schema_version:1,entity:'account',archived:'0',q:'',date_from:'2026-11-24',date_to:'2026-11-24',plan:[],
 filters:{id:'',email:'',source:[],registration_driver:[],token:[],password:[],promotion:['none'],totp:[],risk:[],codex:[],account_status:[],email_status:[]},
 order:[{field:'id',direction:'desc'}],limit:null,
};
const offers=[
 {key:'offer-plus-half',plan:'plus',label:'Plus 半价 2个月',count:20,stale_count:1},
 {key:'offer-team-trial',plan:'team',label:'Team 免费 1个月',count:30,stale_count:0},
 {key:'offer-go-discount',plan:'go',label:'Go 减 25% 1个月',count:10,stale_count:0},
];
const state:DailyRegistrationStatsState={
 data:{ok:true,timezone:'Asia/Shanghai',date_from:'2026-11-24',date_to:'2026-11-26',cohort_basis_label:'按账号首次入库日期统计',
  rows:[
   {date:'2026-11-24',total:150,counts:{success:90,failed:60},accounts_total:100,promoted_accounts_total:40,promotion_presence:{eligible:40,none:50,unknown:10},offers,unpromoted_count:55,query:baseQuery},
   {date:'2026-11-25',accounts_total:200,promoted_accounts_total:80,promotion_presence:{eligible:80,none:100,unknown:20},offers:[{...offers[0]!,count:10,stale_count:0},{...offers[1]!,count:60}],unpromoted_count:100,query:{...baseQuery,date_from:'2026-11-25',date_to:'2026-11-25'}},
   {date:'2026-11-26',accounts_total:0,promoted_accounts_total:0,promotion_presence:{eligible:0,none:0,unknown:0},offers:[],unpromoted_count:0,query:{...baseQuery,date_from:'2026-11-26',date_to:'2026-11-26'}},
  ],summary:{accounts_total:300,promoted_accounts_total:120,promotion_presence:{eligible:120,none:150,unknown:30},offers,unpromoted_count:155,query:{...baseQuery,date_to:'2026-11-26'}},
 },loading:false,error:'',updatedAt:'2026-11-26T12:00:00+08:00',requestedRange:null,displayedRange:{from:'2026-11-24',to:'2026-11-26'},scopeCurrent:true,load:vi.fn(),
};
function render(value=state,onBulkPlanCreate=vi.fn()){
 const wrapper=mount(DailyRegistrationStats,{props:{state:value,onBulkPlanCreate}});wrappers.push(wrapper);return wrapper;
}
beforeEach(()=>{vi.useFakeTimers();});
afterEach(()=>{wrappers.splice(0).forEach(wrapper=>wrapper.unmount());vi.useRealTimers();});

describe('DailyRegistrationStats',()=>{
 it('shows account totals, presence proportions and every offer date together without opening a day',()=>{
  const wrapper=render();
  expect(wrapper.text()).toContain('每日账号总数');
  expect(wrapper.text()).toContain('每日有无优惠占比');
  expect(wrapper.text()).toContain('每日优惠种类占比');
  expect(wrapper.text()).not.toContain('优惠覆盖数');
  expect(wrapper.text()).not.toContain('注册任务总数');
  expect(wrapper.text()).not.toContain('成功 90');
  expect(wrapper.findAll('[data-daily-bar]')).toHaveLength(3);
  expect(wrapper.findAll('[data-daily-presence]')).toHaveLength(3);
  expect(wrapper.findAll('[data-daily-offer-cell]')).toHaveLength(9);
  expect(wrapper.get('[data-daily-range]').text()).toContain('2026-11-24 至 2026-11-26');
  expect(wrapper.get('[data-daily-range-3]').classes()).toContain('active');
 });

 it('sizes quantity columns by unique account totals and keeps the zero date without a fake quantity',()=>{
  const wrapper=render();
  expect(wrapper.get('[data-daily-axis]').text()).toContain('账号数');
  expect(wrapper.findAll('[data-daily-axis-tick]').map(tick=>tick.text())).toEqual(['200','150','100','50','0']);
  const first=wrapper.get('[data-daily-bar="2026-11-24"]');
  expect(first.get('[data-daily-account-total]').text()).toBe('100');
  expect(first.get('[data-daily-quantity]').attributes('style')).toContain('height: 50%');
  expect(first.attributes('aria-label')).toContain('账号总数 100');
  expect(wrapper.get('[data-daily-bar="2026-11-26"] [data-daily-quantity]').attributes('style')).toContain('height: 0%');
 });

 it('shows mutually exclusive daily presence labels using the entire day account denominator',()=>{
  const wrapper=render();
  const first=wrapper.get('[data-daily-presence="2026-11-24"]');
  expect(first.text()).toContain('有优惠 40 个 · 40%');
  expect(first.text()).toContain('无优惠 50 个 · 50%');
  expect(first.text()).toContain('待确认 10 个 · 10%');
  expect(first.get('[data-presence-segment="eligible"]').attributes('style')).toContain('width: 40%');
  expect(first.get('[data-presence-segment="none"]').attributes('style')).toContain('width: 50%');
  expect(first.get('[data-presence-segment="unknown"]').attributes('style')).toContain('width: 10%');
  expect(wrapper.get('[data-daily-presence="2026-11-25"]').text()).toContain('有优惠 80 个 · 40%');
  expect(wrapper.get('[data-daily-presence="2026-11-26"]').text()).toContain('暂无账号');
  expect(wrapper.get('[data-daily-presence="2026-11-26"]').findAll('[data-presence-segment]')).toHaveLength(0);
 });

 it('compares concrete offer shares across all dates without treating categories as a whole',()=>{
  const wrapper=render();
  expect(wrapper.findAll('[data-daily-offer-row]').map(row=>row.attributes('data-daily-offer-row'))).toEqual(['offer-team-trial','offer-plus-half','offer-go-discount']);
  const first=wrapper.get('[data-daily-offer-cell="offer-team-trial:2026-11-24"]');
  const second=wrapper.get('[data-daily-offer-cell="offer-team-trial:2026-11-25"]');
  expect(first.text()).toContain('30%');expect(first.text()).toContain('30 个');
  expect(second.text()).toContain('30%');expect(second.text()).toContain('60 个');
  expect(first.get('[data-daily-offer-fill]').attributes('style')).toContain('width: 30%');
  expect(wrapper.get('[data-daily-offer-cell="offer-plus-half:2026-11-24"]').text()).toContain('1 个待复查');
  expect(wrapper.get('[data-daily-offer-cell="offer-go-discount:2026-11-25"]').text()).toContain('0%');
  expect(wrapper.get('[data-daily-offer-cell="offer-go-discount:2026-11-26"]').text()).toContain('—');
  expect(wrapper.text()).toContain('每项占比均以当天账号总数为分母');
 });

 it('keeps small nonzero offer and presence percentages visible',async()=>{
  const wrapper=render();
  for(const [accounts,count,share] of [[999,1,'0.1%'],[999,26,'2.6%'],[67,4,'5.97%'],[100000,1,'<0.01%']] as const){
   const offer={...offers[0]!,count};
   await wrapper.setProps({state:{...state,data:{...state.data!,rows:[{date:'2026-11-24',accounts_total:accounts,offers:[offer],promotion_presence:{eligible:count,none:accounts-count,unknown:0}}]}}});
   expect(wrapper.get('[data-daily-offer-cell="offer-plus-half:2026-11-24"]').text()).toContain(share);
   expect(wrapper.get('[data-daily-presence="2026-11-24"]').text()).toContain(`有优惠 ${count} 个 · ${share}`);
  }
 });

 it('keeps missing presence and offer data pending instead of calling the remaining accounts none',()=>{
  const wrapper=render({...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,promotion_presence:null,offers:null,unpromoted_count:null},state.data!.rows![1]!]}});
  const first=wrapper.get('[data-daily-presence="2026-11-24"]');
  expect(first.text()).toContain('有无优惠数据待查');
  expect(first.findAll('[data-presence-segment]')).toHaveLength(0);
  expect(first.text()).not.toContain('无优惠 100');
  expect(wrapper.get('[data-daily-offer-cell="offer-team-trial:2026-11-24"]').text()).toContain('待查');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
 });

 it('does not render misleading presence ratios when counts disagree with the day total',()=>{
  const wrapper=render({...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,promotion_presence:{eligible:40,none:100,unknown:10}}]}});
  expect(wrapper.get('[data-daily-presence="2026-11-24"]').text()).toContain('有无优惠数据待查');
  expect(wrapper.get('[data-daily-presence="2026-11-24"]').findAll('[data-presence-segment]')).toHaveLength(0);
 });

 it('keeps daily and interval batch actions as unchanged query/name prefills and disables empty days',async()=>{
  const onBulkPlanCreate=vi.fn();const wrapper=render(state,onBulkPlanCreate);
  await wrapper.get('[data-daily-bulk]').trigger('click');
  expect(onBulkPlanCreate).toHaveBeenCalledExactlyOnceWith({name:'2026-11-24 无优惠账号查套餐',query:baseQuery});
  expect(wrapper.get('[data-daily-row]').text()).toContain('Plus 无优惠账号查套餐');
  await wrapper.get('[data-daily-summary-bulk]').trigger('click');
  expect(onBulkPlanCreate).toHaveBeenLastCalledWith({name:'2026-11-24..2026-11-26 无优惠账号查套餐',query:state.data!.summary!.query});
  await wrapper.get('[data-daily-bar="2026-11-26"]').trigger('click');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();
 });

 it('supports keyboard day selection and retains the selected day until a new range removes it',async()=>{
  const wrapper=render();const first=wrapper.get('[data-daily-bar="2026-11-24"]');
  expect(first.attributes('tabindex')).toBe('0');await first.trigger('keydown',{key:'End'});
  const last=wrapper.get('[data-daily-bar="2026-11-26"]');
  expect(last.attributes('aria-pressed')).toBe('true');expect(last.attributes('tabindex')).toBe('0');
  expect(wrapper.get('[data-daily-row]').attributes('data-daily-row')).toBe('2026-11-26');
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[...state.data!.rows!]}}});
  expect(last.attributes('aria-pressed')).toBe('true');await last.trigger('keydown',{key:'Home'});
  expect(first.attributes('aria-pressed')).toBe('true');await first.trigger('keydown',{key:'ArrowRight'});
  expect(wrapper.get('[data-daily-bar="2026-11-25"]').attributes('aria-pressed')).toBe('true');
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[state.data!.rows![0]!]}}});
  expect(wrapper.get('[data-daily-row]').attributes('data-daily-row')).toBe('2026-11-24');
 });

 it('keeps old successful figures visible during a local error and retries only the daily read',async()=>{
  const load=vi.fn();const wrapper=render({...state,error:'统计暂不可用',load});
  expect(wrapper.get('[data-daily-error]').text()).toContain('统计暂不可用');
  expect(wrapper.findAll('[data-daily-presence]')).toHaveLength(3);
  await wrapper.get('[data-daily-retry]').trigger('click');expect(load).toHaveBeenCalledOnce();
 });

 it('blocks daily and interval batch actions for a pending or failed changed range',async()=>{
  const onBulkPlanCreate=vi.fn();const pending={...state,loading:true,scopeCurrent:false,requestedRange:{from:'2026-11-01',to:'2026-11-30'}};
  const wrapper=render(pending,onBulkPlanCreate);
  expect(wrapper.get('[data-daily-stale]').text()).toContain('正在读取新日期范围');
  expect(wrapper.get('[data-daily-bulk]').attributes('disabled')).toBeDefined();expect(wrapper.get('[data-daily-summary-bulk]').attributes('disabled')).toBeDefined();
  await wrapper.get('[data-daily-bulk]').trigger('click');await wrapper.get('[data-daily-summary-bulk]').trigger('click');expect(onBulkPlanCreate).not.toHaveBeenCalled();
  await wrapper.setProps({state:{...pending,loading:false,error:'统计暂不可用'}});expect(wrapper.get('[data-daily-stale]').text()).toContain('读取失败');
  await wrapper.setProps({state});await wrapper.get('[data-daily-bulk]').trigger('click');expect(onBulkPlanCreate).toHaveBeenCalledOnce();
 });

 it('supports three, seven, thirty and custom day ranges anchored to the current Beijing date',async()=>{
  vi.setSystemTime(new Date('2026-12-14T20:00:00Z'));const load=vi.fn();const wrapper=render({...state,load});
  await wrapper.get('[data-daily-range-3]').trigger('click');expect(load).toHaveBeenLastCalledWith('2026-12-13','2026-12-15');
  await wrapper.get('[data-daily-range-7]').trigger('click');expect(load).toHaveBeenLastCalledWith('2026-12-09','2026-12-15');
  await wrapper.get('[data-daily-range-30]').trigger('click');expect(load).toHaveBeenLastCalledWith('2026-11-16','2026-12-15');
  const requestedBeforeCustom=load.mock.calls.length;
  await wrapper.get('[data-daily-range-custom]').trigger('click');
  expect(load).toHaveBeenCalledTimes(requestedBeforeCustom);
  expect((wrapper.get('input[aria-label="开始日期"]').element as HTMLInputElement).value).toBe('2026-11-24');
  await wrapper.get('input[aria-label="开始日期"]').setValue('2026-11-28');
  expect(load).toHaveBeenCalledTimes(requestedBeforeCustom);
  await wrapper.get('input[aria-label="开始日期"]').setValue('');
  expect(load).toHaveBeenCalledTimes(requestedBeforeCustom);
  await wrapper.get('input[aria-label="开始日期"]').setValue('2026-11-01');await wrapper.get('input[aria-label="结束日期"]').setValue('2026-11-03');
  await flushPromises();expect(load).toHaveBeenLastCalledWith('2026-11-01','2026-11-03');
 });
});
