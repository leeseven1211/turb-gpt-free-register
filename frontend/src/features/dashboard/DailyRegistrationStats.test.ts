import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import DailyRegistrationStats from './DailyRegistrationStats.vue';
import type {DailyRegistrationStatsState} from './contracts';
import type {AccountQuerySpec} from '../accounts/queryAdapter';

const wrappers:ReturnType<typeof mount>[]=[];
const baseQuery:AccountQuerySpec={
 schema_version:1,entity:'account',team_scope:'all',archived:'0',q:'',date_from:'2026-11-24',date_to:'2026-11-24',plan:[],
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
function render(value=state){
 const wrapper=mount(DailyRegistrationStats,{props:{state:value}});wrappers.push(wrapper);return wrapper;
}
beforeEach(()=>{vi.useFakeTimers();});
afterEach(()=>{wrappers.splice(0).forEach(wrapper=>wrapper.unmount());vi.useRealTimers();});

describe('DailyRegistrationStats',()=>{
 it('总览只展示每日账号总数和有无优惠占比',()=>{
  const wrapper=render();
  expect(wrapper.text()).toContain('每日账号总数');
  expect(wrapper.text()).toContain('每日有无优惠占比');
  expect(wrapper.text()).not.toContain('每日优惠种类占比');
  expect(wrapper.text()).not.toContain('优惠覆盖数');
  expect(wrapper.text()).not.toContain('注册任务总数');
  expect(wrapper.text()).not.toContain('成功 90');
  expect(wrapper.findAll('[data-daily-bar]')).toHaveLength(3);
  expect(wrapper.findAll('[data-daily-presence]')).toHaveLength(3);
  expect(wrapper.findAll('[data-daily-offer-cell]')).toHaveLength(0);
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

 it('小幅非零优惠占比仍可见',async()=>{
  const wrapper=render();
  for(const [accounts,count,share] of [[999,1,'0.1%'],[999,26,'2.6%'],[67,4,'5.97%'],[100000,1,'<0.01%']] as const){
   await wrapper.setProps({state:{...state,data:{...state.data!,rows:[{date:'2026-11-24',accounts_total:accounts,promotion_presence:{eligible:count,none:accounts-count,unknown:0}}]}}});
   expect(wrapper.get('[data-daily-presence="2026-11-24"]').text()).toContain(`有优惠 ${count} 个 · ${share}`);
  }
 });

 it('缺失有无优惠数据时保留待查，不把其余账号算为无优惠',()=>{
  const wrapper=render({...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,promotion_presence:null,offers:null,unpromoted_count:null},state.data!.rows![1]!]}});
  const first=wrapper.get('[data-daily-presence="2026-11-24"]');
  expect(first.text()).toContain('有无优惠数据待查');
  expect(first.findAll('[data-presence-segment]')).toHaveLength(0);
  expect(first.text()).not.toContain('无优惠 100');
 });

 it('does not render misleading presence ratios when counts disagree with the day total',()=>{
  const wrapper=render({...state,data:{...state.data!,rows:[{...state.data!.rows![0]!,promotion_presence:{eligible:40,none:100,unknown:10}}]}});
  expect(wrapper.get('[data-daily-presence="2026-11-24"]').text()).toContain('有无优惠数据待查');
  expect(wrapper.get('[data-daily-presence="2026-11-24"]').findAll('[data-presence-segment]')).toHaveLength(0);
 });

 it('已有日和区间筛选快照时也不展示查套餐批量入口或日期操作条',async()=>{
  const wrapper=render();
  expect(wrapper.find('[data-daily-bulk]').exists()).toBe(false);
  expect(wrapper.find('[data-daily-summary-bulk]').exists()).toBe(false);
  expect(wrapper.find('[data-daily-row]').exists()).toBe(false);
  expect(wrapper.text()).not.toContain('新建查套餐批量');
  expect(wrapper.text()).not.toContain('新建区间查套餐批量');
  await wrapper.get('[data-daily-bar="2026-11-26"]').trigger('click');
  expect(wrapper.find('[data-daily-row]').exists()).toBe(false);
  expect(wrapper.get('[data-daily-bar="2026-11-26"]').attributes('aria-pressed')).toBe('true');
 });

 it('supports keyboard day selection and retains the selected day until a new range removes it',async()=>{
  const wrapper=render();const first=wrapper.get('[data-daily-bar="2026-11-24"]');
  expect(wrapper.findAll('[data-daily-bar]').every(bar=>bar.attributes('aria-controls')===undefined)).toBe(true);
  expect(first.attributes('tabindex')).toBe('0');await first.trigger('keydown',{key:'End'});
  const last=wrapper.get('[data-daily-bar="2026-11-26"]');
  expect(last.attributes('aria-pressed')).toBe('true');expect(last.attributes('tabindex')).toBe('0');
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[...state.data!.rows!]}}});
  expect(last.attributes('aria-pressed')).toBe('true');await last.trigger('keydown',{key:'Home'});
  expect(first.attributes('aria-pressed')).toBe('true');await first.trigger('keydown',{key:'ArrowRight'});
  expect(wrapper.get('[data-daily-bar="2026-11-25"]').attributes('aria-pressed')).toBe('true');
  await wrapper.setProps({state:{...state,data:{...state.data!,rows:[state.data!.rows![0]!]}}});
  expect(wrapper.get('[data-daily-bar="2026-11-24"]').attributes('aria-pressed')).toBe('true');
  expect(wrapper.get('[data-daily-bar="2026-11-24"]').attributes('tabindex')).toBe('0');
 });

 it('keeps old successful figures visible during a local error and retries only the daily read',async()=>{
  const load=vi.fn();const wrapper=render({...state,error:'统计暂不可用',load});
  expect(wrapper.get('[data-daily-error]').text()).toContain('统计暂不可用');
  expect(wrapper.findAll('[data-daily-presence]')).toHaveLength(3);
  await wrapper.get('[data-daily-retry]').trigger('click');expect(load).toHaveBeenCalledOnce();
 });

 it('新范围读取中或失败时提示旧数据范围，不再提示创建查套餐批量',async()=>{
  const pending={...state,loading:true,scopeCurrent:false,requestedRange:{from:'2026-11-01',to:'2026-11-30'}};
  const wrapper=render(pending);
  expect(wrapper.get('[data-daily-stale]').text()).toContain('正在读取新日期范围');
  expect(wrapper.get('[data-daily-stale]').text()).toContain('上一成功范围');
  expect(wrapper.get('[data-daily-stale]').text()).not.toContain('查套餐批量');
  expect(wrapper.findAll('[data-daily-presence]')).toHaveLength(3);
  await wrapper.setProps({state:{...pending,loading:false,error:'统计暂不可用'}});
  expect(wrapper.get('[data-daily-stale]').text()).toContain('读取失败');
  expect(wrapper.get('[data-daily-stale]').text()).not.toContain('查套餐批量');
  expect(wrapper.findAll('[data-daily-presence]')).toHaveLength(3);
  await wrapper.setProps({state});
  expect(wrapper.find('[data-daily-stale]').exists()).toBe(false);
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
