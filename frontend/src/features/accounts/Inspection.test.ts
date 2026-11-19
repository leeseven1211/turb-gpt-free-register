import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import Inspection from './Inspection.vue';
import type {AccountInspectionDependencies} from './useAccountInspection';
import type {AccountActionContext} from './useAccounts';
import {deferred,realAdapter} from './uiTestSupport';
const wrappers:ReturnType<typeof mount>[]=[];
function context(archived='0'):AccountActionContext{return Object.freeze({accountIds:['7'],expectedEmails:{'7':'a@test'},querySnapshot:realAdapter().normalize(),archived,rowHints:[]});}
function setup(extra:Partial<AccountInspectionDependencies>={}){
 const deps:AccountInspectionDependencies={request:vi.fn(async()=>({items:[],total:0,active:null})),notify:vi.fn(),operationWorkers:()=>4,randomUUID:vi.fn(()=> 'request-key'),refreshAccounts:vi.fn(),refreshSummary:vi.fn(),openTask:vi.fn(),formatDateTime:value=>`local:${value}`,...extra};
 const w=mount(Inspection,{attachTo:document.body,props:{deps}});wrappers.push(w);return{w,deps};
}
beforeEach(()=>{vi.useFakeTimers();Object.defineProperty(document,'hidden',{configurable:true,value:false});
 Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(this:HTMLDialogElement){this.open=true;}});
 Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(this:HTMLDialogElement){this.open=false;this.dispatchEvent(new Event('close'));}});
});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());vi.useRealTimers();vi.restoreAllMocks();document.body.replaceChildren();});
describe('账号巡检组件保留原请求和运行快照合同',()=>{
 it('范围在打开时冻结，并发默认上限16；超范围不提交',async()=>{
  const {w,deps}=setup({operationWorkers:()=>20});w.vm.openStart(context('only'));await flushPromises();expect(w.get('#accountInspectionScope').text()).toBe('本次范围：已归档账号');expect(w.get<HTMLInputElement>('#accountInspectionWorkers').element.value).toBe('16');
  for(const workers of ['0','17','1.5']){await w.get('#accountInspectionWorkers').setValue(workers);await w.get('form').trigger('submit');}expect(deps.request).not.toHaveBeenCalled();
 });
 it('超时及400/403/409保留幂等键，成功后才换键，接受后历史失败不重发POST',async()=>{
  let count=0;const request=vi.fn<AccountInspectionDependencies['request']>(async(path)=>{if(path.includes('?page='))throw new Error('history unavailable');if(++count<=4)throw new Error(['timeout','HTTP 400','HTTP 403','HTTP 409'][count-1]);return{created:count===5};});const {w,deps}=setup({request});
  w.vm.openStart(context('only'));await flushPromises();await w.get('#accountInspectionWorkers').setValue('2');
  for(let index=0;index<4;index++){await w.get('form').trigger('submit');await flushPromises();expect(w.get('#accountInspectionStartError').text()).toContain('巡检启动请求失败');}
  await w.get('form').trigger('submit');await flushPromises();expect(request.mock.calls.filter(call=>call[1]?.method==='POST').map(call=>JSON.parse(String(call[1]?.body)))).toEqual(Array(5).fill({workers:2,archived:'only',idempotency_key:'request-key'}));expect(deps.randomUUID).toHaveBeenCalledTimes(1);expect(deps.notify).toHaveBeenCalledWith('巡检已加入统一任务队列');
  w.vm.openStart(context());await flushPromises();await w.get('form').trigger('submit');await flushPromises();expect(deps.randomUUID).toHaveBeenCalledTimes(2);expect(deps.notify).toHaveBeenCalledWith('已有本次巡检记录，已打开历史');
 });
 it('30秒超时中止请求，期间重复提交不再POST',async()=>{
  const pending=deferred<unknown>();let signal:AbortSignal|undefined;const request=vi.fn((_path:string,options?:RequestInit)=>{signal=options?.signal as AbortSignal;signal?.addEventListener('abort',()=>pending.reject(new DOMException('timeout','AbortError')));return pending.promise;});const {w}=setup({request});w.vm.openStart(context());await flushPromises();await w.get('form').trigger('submit');await w.get('form').trigger('submit');expect(request).toHaveBeenCalledTimes(1);await vi.advanceTimersByTimeAsync(30000);expect(signal?.aborted).toBe(true);expect(w.get('#accountInspectionStartError').text()).toContain('巡检启动请求失败');expect(w.get<HTMLButtonElement>('#btnConfirmAccountInspection').element.disabled).toBe(false);
 });
 it('失败详情换ID时拒绝旧结果，finally只补读最新ID一次',async()=>{
  const old=deferred<unknown>();const request=vi.fn().mockImplementationOnce(()=>old.promise).mockResolvedValue({items:[{account_id:8,email:'new@test',status:'deactivated_skipped',failed_at:'time',error:'<script>bad</script>'}],total:1});const {w}=setup({request});w.vm.openFailures(1);w.vm.openFailures(2);w.vm.openFailures(3);await flushPromises();expect(request).toHaveBeenCalledTimes(1);old.resolve({items:[{account_id:1,email:'old@test'}],total:1});await flushPromises();expect(request.mock.calls.map(call=>call[0])).toEqual(['/api/accounts/inspections/1/failures?page=1','/api/accounts/inspections/3/failures?page=1']);expect(w.get('#accountInspectionFailuresContent').text()).toContain('new@test');expect(w.text()).not.toContain('old@test');expect(w.find('script').exists()).toBe(false);
 });
 it('历史分页复开拒绝旧页，加载中页码不可改变',async()=>{
  const old=deferred<unknown>();const request=vi.fn().mockResolvedValueOnce({items:[],total:60}).mockImplementationOnce(()=>old.promise).mockResolvedValue({items:[],total:60});const {w}=setup({request});w.vm.openHistory();await flushPromises();w.vm.changeHistoryPage(1);await flushPromises();w.vm.changeHistoryPage(1);w.vm.openHistory();old.resolve({items:[{id:99}],total:99});await flushPromises();expect(request.mock.calls.map(call=>call[0])).toEqual(['/api/accounts/inspections?page=1','/api/accounts/inspections?page=2','/api/accounts/inspections?page=1']);expect(w.get('#accountInspectionPageLabel').text()).toBe('共 60 条 · 第 1 页');expect(w.text()).not.toContain('#99');
 });
 it('每5秒仅刷新打开视图，隐藏停止定时器，恢复后继续；卸载不发送cancel',async()=>{
  const request=vi.fn(async()=>({items:[],total:0}));const {w}=setup({request});w.vm.openHistory();await flushPromises();await vi.advanceTimersByTimeAsync(5000);expect(request).toHaveBeenCalledTimes(2);Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));await vi.advanceTimersByTimeAsync(15000);expect(request).toHaveBeenCalledTimes(2);Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));await vi.advanceTimersByTimeAsync(5000);expect(request).toHaveBeenCalledTimes(3);w.unmount();await vi.advanceTimersByTimeAsync(10000);expect(request).toHaveBeenCalledTimes(3);expect(vi.getTimerCount()).toBe(0);
 });
 it('隐藏中止在途GET并拒绝晚回写，关闭不停止已接受的巡检',async()=>{
  const late=deferred<unknown>();const request=vi.fn<AccountInspectionDependencies['request']>(()=>late.promise);const {w}=setup({request});w.vm.openHistory();await flushPromises();const signal=request.mock.calls[0]![1]!.signal!;Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));expect(signal.aborted).toBe(true);late.resolve({items:[{id:7}],total:1});await flushPromises();expect(w.text()).not.toContain('#7');w.vm.close();expect(request.mock.calls).toHaveLength(1);
 });
 it('保留原始计数和task_id；active结束仅刷新账号和总览一次',async()=>{
  const record={id:9,task_id:77,status:'completed',archived:'0',workers:2,created_at:'stamp',checked_count:2,skipped_count:3,total_count:5,invalid_count:1,live_success_count:1,live_failed_count:2,deactivated_skipped_count:1,plan_success_count:0,plan_failed_count:3};const request=vi.fn().mockResolvedValueOnce({items:[record],total:1,active:{id:9}}).mockResolvedValue({items:[record],total:1,active:null});const {w,deps}=setup({request});w.vm.openHistory();await flushPromises();expect(w.text()).toContain('失败详情 3');expect(w.text()).toContain('5 / 5');expect(w.text()).toContain('local:stamp');await w.vm.refreshHistory();await w.vm.refreshHistory();expect(deps.refreshAccounts).toHaveBeenCalledTimes(1);expect(deps.refreshSummary).toHaveBeenCalledTimes(1);await w.get('[data-inspection-task="9"]').trigger('click');expect(deps.openTask).toHaveBeenCalledWith(77);expect(w.get<HTMLDialogElement>('#accountInspectionHistory').element.open).toBe(false);
 });
 it('停止只POST cancel，无body/确认，提示安全检查点停止',async()=>{
  const {w,deps}=setup();await w.vm.stop(9);expect(deps.request).toHaveBeenCalledWith('/api/accounts/inspections/9/cancel',expect.objectContaining({method:'POST'}));const init=(deps.request as ReturnType<typeof vi.fn>).mock.calls[0][1];expect(init.body).toBeUndefined();expect(deps.notify).toHaveBeenCalledWith('已请求停止，将在安全检查点结束');
 });
 it('历史与失败GET超时保留原错误反馈，不把超时当生命周期取消吞掉',async()=>{
  const request=vi.fn<AccountInspectionDependencies['request']>((_path,options)=>new Promise((_resolve,reject)=>options?.signal?.addEventListener('abort',()=>reject(new DOMException('read timeout','AbortError')))));const {w,deps}=setup({request});w.vm.openHistory();w.vm.openFailures(9);await vi.advanceTimersByTimeAsync(30000);expect(deps.notify).toHaveBeenCalledWith('读取巡检历史失败：read timeout');expect(w.get('#accountInspectionFailuresContent').text()).toBe('读取失败：read timeout，可点击刷新重试。');
 });
 it('打开任务前同步关闭巡检历史，焦点恢复不覆盖新任务弹窗',async()=>{
  const request=vi.fn(async()=>({items:[{id:9,task_id:77}],total:1}));const taskFocus=document.createElement('button');document.body.append(taskFocus);const openTask=vi.fn(()=>{expect((document.getElementById('accountInspectionHistory') as HTMLDialogElement).open).toBe(false);taskFocus.focus();});const {w}=setup({request,openTask});w.vm.openHistory();await flushPromises();await w.get('[data-inspection-task="9"]').trigger('click');await flushPromises();expect(document.activeElement).toBe(taskFocus);
 });
 it('同一视图刷新保留滚动和焦点；子弹窗触发器失联时返回父弹窗按钮',async()=>{
  const row={id:9,task_id:7,status:'running',archived:'0',workers:2,live_failed_count:1};const request=vi.fn(async()=>({items:[{...row}],total:1}));const {w}=setup({request});w.vm.openHistory();await flushPromises();const scroll=w.get<HTMLElement>('#accountInspectionHistoryContent [data-inspection-scroll]');scroll.element.scrollLeft=150;scroll.element.focus();await w.vm.refreshHistory();await flushPromises();expect(scroll.element.scrollLeft).toBe(150);expect(document.activeElement).toBe(scroll.element);const old=document.createElement('button');document.body.append(old);w.vm.openFailures(9,old);await flushPromises();old.remove();w.vm.close('failures');await flushPromises();expect(document.activeElement).toBe(w.get('#accountInspectionHistory .modal-header button').element);
 });
 it('浏览器延后的close事件不会抢走任务焦点或关闭刚重新打开的历史',async()=>{
  Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(this:HTMLDialogElement){this.open=false;setTimeout(()=>this.dispatchEvent(new Event('close')),0);}});
  const trigger=document.createElement('button'),taskFocus=document.createElement('button');document.body.append(trigger,taskFocus);const {w}=setup({request:vi.fn(async()=>({items:[{id:9,task_id:77}],total:1})),openTask:()=>taskFocus.focus()});w.vm.openHistory(trigger);await flushPromises();await w.get('[data-inspection-task="9"]').trigger('click');await vi.advanceTimersByTimeAsync(0);expect(document.activeElement).toBe(taskFocus);
  w.vm.openHistory(trigger);await flushPromises();w.vm.close('history');w.vm.openHistory(trigger);await flushPromises();await vi.advanceTimersByTimeAsync(0);expect(w.get<HTMLDialogElement>('#accountInspectionHistory').element.open).toBe(true);
 });
});
