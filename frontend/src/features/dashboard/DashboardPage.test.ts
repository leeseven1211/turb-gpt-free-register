import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {nextTick} from 'vue';
import DashboardPage from './DashboardPage.vue';
import {createDashboardApi} from '../../api/dashboard';
import {DASHBOARD_POLL_MS} from './useDashboard';

const wrappers:ReturnType<typeof mount>[]=[];
const sample={
 accounts:{total:12,active:10,archived:2,codex_ready:4,plans:{free:8,plus:4}},
 email:{supply:{status:'known',total:20,available:12,used:6,failed:2,disabled:0,sources:[{source:'outlook',label:'Outlook',kind:'local_pool',total:20,available:12,used:6,failed:2}]},sources:[]},
 jobs:{total:5,counts:{success:3,failed:1,pending:1,running:0,stopping:0},today:'今天',today_counts:{success:2,partial_success:0,failed:1}},
 proxy:{platform:'1024proxy',active_leases:2,leases:[{endpoint:'192.0.2.1:8080',region:'US'},{endpoint:'192.0.2.2:8080',region:'JP'}]},
 codex:{total:4,pending:1,exported:3},
};
const extractSample={ok:true,today_extracted:7,today_plus_confirmed:2,awaiting_payment:1,needs_review:1,processing:1,all:42,providers:[]};

function setup(){
 const calls:string[]=[];
 const api=createDashboardApi(async(path)=>{
  calls.push(path);
  if(path==='/api/dashboard')return sample;
  if(path==='/api/extract-workbench/summary')return extractSample;
  return {features:{register:{enabled:true}}};
 });
 const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true,notify:vi.fn(),onNavigate:vi.fn(),onConfig:vi.fn()}}});
 wrappers.push(wrapper);return{wrapper,calls};
}
beforeEach(()=>{vi.useFakeTimers();Object.defineProperty(document,'hidden',{configurable:true,value:false});});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());document.body.replaceChildren();vi.useRealTimers();});

describe('dashboard Vue owner',()=>{
 it('renders daily statistics before the core overview and its auxiliary reads finish',async()=>{
  let resolveDashboard!:(value:any)=>void;
  const api={
   dashboard:()=>new Promise<any>(resolve=>{resolveDashboard=resolve;}),
   capabilities:async()=>({}),
   extractSummary:async()=>extractSample,
   registrationDaily:async()=>({
    ok:true,date_from:'2026-11-26',date_to:'2026-11-26',
    rows:[{date:'2026-11-26',total:3,counts:{success:2,failed:1},accounts_total:2,plans:{free:2},promoted_accounts_total:1,offers:[{key:'offer-team-trial',plan:'team',label:'Team 免费 1个月',count:1,stale_count:0}],unpromoted_count:0}],
   }),
  };
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true}}});wrappers.push(wrapper);
  await flushPromises();
  expect(wrapper.get('[data-daily-row="2026-11-26"]').text()).toContain('Team 免费 1个月');
  expect(wrapper.get('[data-daily-offer="offer-team-trial"]').text()).toContain('1 个账号 · 50%');
  expect(wrapper.find('[data-overview-card="accounts"]').exists()).toBe(false);
  expect(wrapper.find('[aria-label="正在读取总览"]').exists()).toBe(true);
  resolveDashboard(sample);
  await flushPromises();
  expect(wrapper.findAll('[data-daily-row]')).toHaveLength(1);
  expect(wrapper.get('[data-overview-card="accounts"]').text()).toContain('10');
 });

 it('renders the seven service areas and their live figures',async()=>{
  const {wrapper,calls}=setup();await flushPromises();
  expect(calls).toContain('/api/dashboard');
  expect(calls).toContain('/api/extract-workbench/summary');
  expect(wrapper.get('[data-overview-card="email"]').text()).toContain('12');
  expect(wrapper.get('[data-overview-card="accounts"]').text()).toContain('10');
  expect(wrapper.get('[data-overview-card="codex"]').text()).toContain('4');
  expect(wrapper.get('[data-overview-card="extract"]').text()).toContain('7');
  expect(wrapper.get('[data-overview-card="extract"]').text()).not.toContain('待核对');
  expect(wrapper.findAll('.ov-pulse-item')[4].text()).not.toContain('待核对');
  expect(wrapper.get('[data-overview-card="plans"]').text()).toContain('Plus');
  expect(wrapper.get('[data-overview-card="proxy"]').text()).toContain('1024Proxy');
  expect(wrapper.get('[data-overview-card="jobs"]').text()).toContain('今天');
  expect(wrapper.findAll('.ov-pulse-item')).toHaveLength(7);
 });

 it.each([0,1])('shows an actual ready rate for %i of 100 accounts',async ready=>{
  const api=createDashboardApi(async path=>path==='/api/dashboard'
   ?{...sample,accounts:{...sample.accounts,total:100,active:100,archived:0,codex_ready:ready,plans:{free:99,plus:1}}}
   :path==='/api/extract-workbench/summary'?extractSample:{});
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true}}});wrappers.push(wrapper);await flushPromises();
  const meter=wrapper.get('[data-overview-card="accounts"] .ov-meter');
  expect(meter.get('strong').text()).toBe(`${ready}%`);
  expect(meter.get('.ov-bar > i').attributes('style')).toContain(`width: ${ready}%`);
  expect(wrapper.get('[data-overview-card="codex"] .ov-foot').text()).toBe(`账号 Codex 就绪 ${ready} · 覆盖 ${ready}% 活跃账号`);
  const plus=wrapper.get('[data-overview-card="plans"]').findAll('.ov-bars li').find(row=>row.text().includes('Plus'))!;
  expect(plus.text()).toContain('1 · 1%');
 });

 it('surfaces an exhausted email pool as a warning instead of hiding it',async()=>{
  const api=createDashboardApi(async path=>path==='/api/dashboard'
   ?{...sample,email:{supply:{...sample.email.supply,available:0,used:20,sources:[{source:'outlook',label:'Outlook',kind:'local_pool',total:20,available:0,used:20}]},sources:[]}}
   :path==='/api/extract-workbench/summary'?extractSample:{});
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true}}});wrappers.push(wrapper);await flushPromises();
  expect(wrapper.get('[data-overview-card="email"]').text()).toContain('库存耗尽');
  expect(wrapper.get('.ov-alerts').text()).toContain('邮箱池已用完');
 });

 it('keeps an errored local supply visible as a read failure instead of zero',async()=>{
  const api=createDashboardApi(async path=>path==='/api/dashboard'
   ?{...sample,email:{supply:{status:'error',reason:'offline',sources:[{source:'outlook',kind:'local_pool',status:'error'}]},sources:[]}}
   :path==='/api/extract-workbench/summary'?extractSample:{});
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true}}});wrappers.push(wrapper);await flushPromises();
  expect(wrapper.get('[data-overview-card="email"]').text()).toContain('读取失败');
  expect(wrapper.get('[data-overview-card="email"]').text()).not.toContain('库存耗尽');
 });

 it('renders even when the extract summary is unavailable',async()=>{
  const api=createDashboardApi(async path=>{
   if(path==='/api/dashboard')return sample;
   if(path==='/api/extract-workbench/summary')throw new Error('extract offline');
   return {};
  });
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true}}});wrappers.push(wrapper);await flushPromises();
  expect(wrapper.get('[data-overview-card="accounts"]').text()).toContain('10');
  expect(wrapper.get('[data-overview-card="extract"]').text()).toContain('空闲');
 });

 it('does not read while hidden and discards a late response after hiding',async()=>{
  let resolve!: (value:any)=>void;
  const api=createDashboardApi(vi.fn((path:string)=>path==='/api/dashboard'?new Promise(r=>{resolve=r;}):Promise.resolve({})));
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:false}}});wrappers.push(wrapper);
  await (wrapper.vm as any).setVisible(true);expect(api).toBeTruthy();
  await (wrapper.vm as any).setVisible(false);resolve(sample);await flushPromises();
  expect(wrapper.find('[data-overview-card="accounts"]').exists()).toBe(false);
 });

 it('coalesces visible refreshes and polls from one owner',async()=>{
  let resolve!:(value:any)=>void;const read=vi.fn(()=>new Promise<any>(done=>{resolve=done;}));const capabilities=vi.fn(async()=>({}));const extractSummary=vi.fn(async()=>extractSample);
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api:{dashboard:read,capabilities,extractSummary},deps:{visible:false}}});wrappers.push(wrapper);
  await (wrapper.vm as any).load();expect(read).not.toHaveBeenCalled();
  (wrapper.vm as any).setVisible(true);const first=(wrapper.vm as any).load(),second=(wrapper.vm as any).load();expect(read).toHaveBeenCalledTimes(1);
  resolve(sample);await Promise.all([first,second]);await flushPromises();
  read.mockResolvedValue(sample);await vi.advanceTimersByTimeAsync(DASHBOARD_POLL_MS);await flushPromises();expect(read).toHaveBeenCalledTimes(2);
  (wrapper.vm as any).setVisible(false);await vi.advanceTimersByTimeAsync(DASHBOARD_POLL_MS*2);expect(read).toHaveBeenCalledTimes(2);
 });

 it('首次和手动刷新期间显示加载态，后台轮询期间保留按钮可操作',async()=>{
  let resolve!: (value:any)=>void;
  const read=vi.fn(()=>new Promise<any>(done=>{resolve=done;}));
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{
   api:{dashboard:read,capabilities:async()=>({}),extractSummary:async()=>extractSample},
   deps:{visible:true},
  }});wrappers.push(wrapper);
  await nextTick();
  const button=wrapper.get('button.ui-refresh-button');
  expect(button.attributes('disabled')).toBeDefined();
  expect(button.text()).toContain('刷新中');
  resolve(sample);await flushPromises();
  expect(button.attributes('disabled')).toBeUndefined();
  expect(button.text()).toBe('刷新');

  let pollResolve!: (value:any)=>void;
  read.mockImplementation(()=>new Promise<any>(done=>{pollResolve=done;}));
  await vi.advanceTimersByTimeAsync(DASHBOARD_POLL_MS);
  expect(button.attributes('disabled')).toBeUndefined();
  expect(button.text()).toBe('刷新');
  expect(wrapper.get('[data-overview-card="accounts"]').text()).toContain('10');
  pollResolve(sample);await flushPromises();

  let manualResolve!: (value:any)=>void;
  read.mockImplementation(()=>new Promise<any>(done=>{manualResolve=done;}));
  const manual=wrapper.get('button.ui-refresh-button').trigger('click');
  await Promise.resolve();
  expect(button.attributes('disabled')).toBeDefined();
  expect(button.text()).toContain('刷新中');
  manualResolve(sample);await manual;await flushPromises();
 });

 it('已加载总览在恢复可见时静默刷新并保留旧数据',async()=>{
  const read=vi.fn(async()=>sample);
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{
   api:{dashboard:read,capabilities:async()=>({}),extractSummary:async()=>extractSample},
   deps:{visible:true},
  }});wrappers.push(wrapper);
  await flushPromises();
  const button=wrapper.get('button.ui-refresh-button');
  await (wrapper.vm as any).setVisible(false);
  let resolve!: (value:any)=>void;
  read.mockImplementation(()=>new Promise<any>(done=>{resolve=done;}));
  await (wrapper.vm as any).setVisible(true);
  await nextTick();
  expect(button.attributes('disabled')).toBeUndefined();
  expect(button.text()).toBe('刷新');
  expect(wrapper.get('[data-overview-card="accounts"]').text()).toContain('10');
  resolve(sample);await flushPromises();
 });

 it('首次加载失败后后台重试显示加载态并保留旧错误直到成功',async()=>{
  const read=vi.fn()
   .mockRejectedValueOnce(new Error('首次读取失败'))
   .mockImplementationOnce(()=>new Promise<any>(done=>{resolve=done;}));
  let resolve!: (value:any)=>void;
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{
   api:{dashboard:read,capabilities:async()=>({}),extractSummary:async()=>extractSample},
   deps:{visible:true},
  }});wrappers.push(wrapper);
  await flushPromises();
  expect(wrapper.get('.ov-error').text()).toContain('首次读取失败');
  await vi.advanceTimersByTimeAsync(DASHBOARD_POLL_MS);
  await nextTick();
  expect(wrapper.get('button.ui-refresh-button').attributes('disabled')).toBeDefined();
  expect(wrapper.get('.ov-error').text()).toContain('首次读取失败');
  resolve(sample);await flushPromises();
  expect(wrapper.find('.ov-error').exists()).toBe(false);
 });

 it('discards pending reads and callbacks after unmount',async()=>{
  let resolve!:(value:any)=>void;const onReady=vi.fn(),onCapabilities=vi.fn(),read=vi.fn(()=>new Promise<any>(done=>{resolve=done;}));
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api:{dashboard:read,capabilities:async()=>({features:{register:{enabled:true}}}),extractSummary:async()=>extractSample},deps:{visible:true,onReady,onCapabilities}}});wrappers.push(wrapper);
  wrapper.unmount();wrappers.splice(wrappers.indexOf(wrapper),1);resolve(sample);await flushPromises();
  expect(onReady).not.toHaveBeenCalled();expect(onCapabilities).not.toHaveBeenCalled();await vi.advanceTimersByTimeAsync(DASHBOARD_POLL_MS*2);expect(read).toHaveBeenCalledTimes(1);
 });

 it('binds every card action and pulse item to its navigation identity',async()=>{
  const onNavigate=vi.fn();
  const api=createDashboardApi(async path=>path==='/api/dashboard'?sample:path==='/api/extract-workbench/summary'?extractSample:{});
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true,onNavigate}}});wrappers.push(wrapper);await flushPromises();
  await wrapper.get('[data-overview-action="email"]').trigger('click');expect(onNavigate).toHaveBeenCalledWith('outlook');
  await wrapper.get('[data-overview-action="proxy"]').trigger('click');expect(onNavigate).toHaveBeenCalledWith('proxy-traffic');
  await wrapper.get('[data-overview-action="jobs"]').trigger('click');expect(onNavigate).toHaveBeenCalledWith('tasks');
  await wrapper.get('[data-overview-action="extract"]').trigger('click');expect(onNavigate).toHaveBeenCalledWith('extract-workbench');
  await wrapper.findAll('.ov-pulse-item')[4].trigger('click');expect(onNavigate).toHaveBeenCalledWith('extract-workbench');
 });
});
