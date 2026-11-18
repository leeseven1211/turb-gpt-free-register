import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import DashboardPage from './DashboardPage.vue';
import {createDashboardApi} from '../../api/dashboard';

const wrappers:ReturnType<typeof mount>[]=[];
const sample={
 accounts:{total:12,active:10,archived:2,codex_ready:4,plans:{free:8,plus:4}},
 email:{supply:{sources:[{source:'outlook',label:'Outlook',kind:'local_pool',enabled:false,total:20,available:12,used:6,failed:2}]},sources:[]},
 jobs:{total:5,counts:{success:3,failed:1,pending:1,running:0,stopping:0},today:'今天',today_counts:{success:2,partial_success:0,failed:1}},
 proxy:{platform:'1024proxy',active_leases:2,leases:[{endpoint:'192.0.2.1:8080',region:'US'},{endpoint:'192.0.2.2:8080',region:'JP'}]},
 codex:{total:4,pending:1,exported:3},
};
function setup(){
 const calls:string[]=[];
 const api=createDashboardApi(async(path)=>{calls.push(path);return path==='/api/dashboard'?sample:{features:{register:{enabled:true}}};});
 const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true,notify:vi.fn(),onNavigate:vi.fn(),onConfig:vi.fn()}}});
 wrappers.push(wrapper);return{wrapper,calls};
}
beforeEach(()=>{vi.useFakeTimers();Object.defineProperty(document,'hidden',{configurable:true,value:false});HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};vi.spyOn(window,'scrollTo').mockImplementation(()=>{});});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());document.body.replaceChildren();localStorage.clear();vi.useRealTimers();});
describe('dashboard Vue owner',()=>{
 it('renders all available metric and detail cards from the dashboard projection',async()=>{
  const {wrapper}=setup();await flushPromises();
  expect(wrapper.get('[data-dashboard-card="metric-accounts"]').text()).toContain('10');
  expect(wrapper.get('[data-dashboard-card="metric-email"]').text()).toContain('12');
  expect(wrapper.get('[data-dashboard-card="panel-email"]').text()).toContain('Outlook');
  expect(wrapper.get('[data-dashboard-card="panel-proxy"]').text()).toContain('1024Proxy');
  expect(wrapper.get('[data-dashboard-card="panel-accounts"]').text()).toContain('Plus');
 });
 it('keeps an errored local supply visible as a read failure instead of zero',async()=>{
  const api=createDashboardApi(async(path)=>path==='/api/dashboard'?{...sample,email:{supply:{status:'error',reason:'offline',sources:[{source:'outlook',kind:'local_pool',status:'error'}]},sources:[]}}:{});
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true,notify:vi.fn(),onNavigate:vi.fn(),onConfig:vi.fn()}}});wrappers.push(wrapper);await flushPromises();
  expect(wrapper.get('[data-dashboard-card="metric-email"]').text()).toContain('读取失败');
 });
 it('does not read while hidden and discards a late response after hiding',async()=>{
  let resolve!: (value:any)=>void;
  const api=createDashboardApi(vi.fn((path:string)=>path==='/api/dashboard'?new Promise(r=>{resolve=r;}):Promise.resolve({})));
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:false,notify:vi.fn(),onNavigate:vi.fn(),onConfig:vi.fn()}}});wrappers.push(wrapper);
  await (wrapper.vm as any).setVisible(true);expect(api).toBeTruthy();
  await (wrapper.vm as any).setVisible(false);resolve(sample);await flushPromises();
  expect(wrapper.find('[data-dashboard-card="metric-accounts"]').exists()).toBe(false);
 });
 it('coalesces visible refreshes and polls from one owner every fifteen seconds',async()=>{
  let resolve!:(value:any)=>void;const read=vi.fn(()=>new Promise<any>(done=>{resolve=done;}));const capabilities=vi.fn(async()=>({}));const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api:{dashboard:read,capabilities},deps:{visible:false}}});wrappers.push(wrapper);
  await (wrapper.vm as any).load();expect(read).not.toHaveBeenCalled();
  (wrapper.vm as any).setVisible(true);const first=(wrapper.vm as any).load(),second=(wrapper.vm as any).load();expect(read).toHaveBeenCalledTimes(1);
  resolve(sample);await Promise.all([first,second]);await flushPromises();
  read.mockResolvedValue(sample);await vi.advanceTimersByTimeAsync(15000);await flushPromises();expect(read).toHaveBeenCalledTimes(2);
  (wrapper.vm as any).setVisible(false);await vi.advanceTimersByTimeAsync(30000);expect(read).toHaveBeenCalledTimes(2);
 });
 it('discards pending reads and callbacks after unmount',async()=>{
  let resolve!:(value:any)=>void;const onReady=vi.fn(),onCapabilities=vi.fn(),read=vi.fn(()=>new Promise<any>(done=>{resolve=done;}));
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api:{dashboard:read,capabilities:async()=>({features:{register:{enabled:true}}})},deps:{visible:true,onReady,onCapabilities}}});wrappers.push(wrapper);
  wrapper.unmount();wrappers.splice(wrappers.indexOf(wrapper),1);resolve(sample);await flushPromises();
  expect(onReady).not.toHaveBeenCalled();expect(onCapabilities).not.toHaveBeenCalled();await vi.advanceTimersByTimeAsync(30000);expect(read).toHaveBeenCalledTimes(1);
 });
 it('persists legacy layout key and resets it through the owner',async()=>{
  localStorage.setItem('gpt_console_overview_preferences_v1',JSON.stringify({hidden:['metric-email']}));
  const {wrapper}=setup();await flushPromises();
  expect(wrapper.find('[data-dashboard-card="metric-email"]').exists()).toBe(false);
  await wrapper.get('[data-dashboard-open-customizer]').trigger('click');
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));
  await flushPromises();
  expect(wrapper.find('[role="dialog"]').attributes('aria-hidden')).toBe('true');
  await wrapper.get('[data-dashboard-open-customizer]').trigger('click');
  await wrapper.get('[data-dashboard-reset-layout]').trigger('click');
  expect(localStorage.getItem('gpt_console_overview_preferences_v1')).toBeNull();
 });
 it('keeps every card action bound to its navigation identity and configured group',async()=>{
  const onNavigate=vi.fn(),onConfig=vi.fn();const api=createDashboardApi(async path=>path==='/api/dashboard'?sample:{});
  const wrapper=mount(DashboardPage,{attachTo:document.body,props:{api,deps:{visible:true,onNavigate,onConfig}}});wrappers.push(wrapper);await flushPromises();
  const button=wrapper.get('[data-dashboard-card="panel-email"] .overview-card-tools button');expect(button.text()).toBe('管理邮箱');await button.trigger('click');expect(onNavigate).toHaveBeenCalledWith('outlook');
  await wrapper.get('[data-dashboard-card="panel-proxy"] .overview-card-tools button').trigger('click');expect(onConfig).toHaveBeenCalledWith('代理与网络');
 });
 it('retains hidden-card labels and native customizer focus and scrolling ownership',async()=>{
  localStorage.setItem('gpt_console_overview_preferences_v1',JSON.stringify({hidden:['metric-email']}));
  const {wrapper}=setup();await flushPromises();const opener=wrapper.get('[data-dashboard-open-customizer]');(opener.element as HTMLElement).focus();await opener.trigger('click');await flushPromises();
  expect(wrapper.get('dialog[open] [data-dashboard-custom-card="metric-email"]').text()).toContain('本地可用邮箱');expect(document.body.style.overflow).toBe('hidden');
  await wrapper.get('[data-dashboard-close-customizer]').trigger('click');await flushPromises();expect(document.body.style.overflow).toBe('');expect(document.activeElement).toBe(opener.element);
 });
 it('closes the native customizer and releases its background lock when navigation hides the page',async()=>{
  const {wrapper}=setup();await flushPromises();
  const opener=wrapper.get('[data-dashboard-open-customizer]');(opener.element as HTMLElement).focus();await opener.trigger('click');await flushPromises();
  expect(wrapper.find('dialog[open]').exists()).toBe(true);expect(document.body.classList.contains('em-native-dialog-lock')).toBe(true);
  const focus=vi.spyOn(opener.element as HTMLElement,'focus');
  (wrapper.vm as any).setVisible(false);await flushPromises();
  expect(wrapper.find('dialog[open]').exists()).toBe(false);
  expect(wrapper.get('dialog').attributes('aria-hidden')).toBe('true');
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(false);
  expect(document.body.style.overflow).toBe('');expect(document.documentElement.style.overflow).toBe('');
  expect(focus).not.toHaveBeenCalled();
 });
 it('releases the native customizer background lock when the mounted page is destroyed',async()=>{
  const {wrapper}=setup();await flushPromises();
  await wrapper.get('[data-dashboard-open-customizer]').trigger('click');await flushPromises();
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(true);
  wrapper.unmount();wrappers.splice(wrappers.indexOf(wrapper),1);
  expect(document.body.classList.contains('em-native-dialog-lock')).toBe(false);
  expect(document.body.style.overflow).toBe('');expect(document.documentElement.style.overflow).toBe('');
 });
 it('persists keyboard size and order while preventing cross-region drops',async()=>{
  const {wrapper}=setup();await flushPromises();
  const handle=wrapper.get('[data-dashboard-card="metric-accounts"] .overview-card-drag');await handle.trigger('keydown',{key:'ArrowRight'});
  expect(wrapper.findAll('.overview-metrics [data-dashboard-card]')[1]?.attributes('data-dashboard-card')).toBe('metric-accounts');
  const resize=wrapper.get('[data-dashboard-card="metric-accounts"] [data-overview-resize]');await resize.trigger('keydown',{key:'ArrowDown'});
  expect(wrapper.get('[data-dashboard-card="metric-accounts"]').attributes('style')).toContain('min-height:');
  await wrapper.get('[data-dashboard-custom-card="metric-email"]').trigger('dragstart');await wrapper.get('[data-dashboard-custom-card="panel-email"]').trigger('drop');
  const saved=JSON.parse(localStorage.getItem('gpt_console_overview_preferences_v1')!);expect(saved.order.metrics).toContain('metric-email');expect(saved.order.panels).not.toContain('metric-email');
 });
});
