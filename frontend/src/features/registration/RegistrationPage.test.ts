import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import RegistrationPage from './RegistrationPage.vue';
import RegistrationProgress from './RegistrationProgress.vue';
import type {JobProgressResponse, RegistrationApi, RegistrationJob} from '../../api/registration';
const wrappers:ReturnType<typeof mount>[]=[];
function setup(){
 const api:RegistrationApi={
  metadata:vi.fn(async()=>({sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}})),
  summary:vi.fn(async()=>({accounts:0})),
  jobs:vi.fn(async()=>({items:[{id:'9007199254740993',email:'long-address@example.test',email_source:'outlook',status:'failed',error_message:'raw diagnostic details that must remain available only in expansion'}],total:125})),
  progress:vi.fn(async(id)=>({ok:true,job:{id,progress:{main_steps:[]}}})),
  create:vi.fn(async()=>({})),action:vi.fn(async()=>({})),log:vi.fn(async()=>({})),debug:vi.fn(async()=>({})),diagnostics:vi.fn(async()=>({})),compare:vi.fn(async()=>({})),
 };
 const wrapper=mount(RegistrationPage,{attachTo:document.body,props:{deps:{api,visible:false,view:'tasks'}}});wrappers.push(wrapper);
 (wrapper.vm as unknown as {setVisible(value:boolean):void}).setVisible(true);
 return {wrapper,api};
}
function launchBatch(api: RegistrationApi, id: string, items: RegistrationJob[]) {
  vi.mocked(api.jobs).mockResolvedValue({progress_batch:{batch_id:id,items}});
}
function progressResponse(id: number, label: string, operation_run_id?: string): JobProgressResponse {
  return {ok:true,job:{id,operation_run_id,progress:{main_steps:[{id:'probe',label,state:'success'}]}}};
}
beforeEach(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};vi.spyOn(window,'scrollTo').mockImplementation(()=>{});});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());document.body.replaceChildren();});
describe('registration list standards',()=>{
 it('filters from column headings and removes one count-row chip without clearing other filters',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  await wrapper.get('thead button[aria-label="筛选邮箱"]').trigger('click');await flushPromises();
  const email=document.querySelector<HTMLInputElement>('[aria-label="筛选邮箱值"]')!;expect(email).not.toBeNull();email.value='long-address';email.dispatchEvent(new Event('change',{bubbles:true}));await flushPromises();
  await wrapper.get('thead button[aria-label="筛选状态"]').trigger('click');await flushPromises();
  const status=document.querySelector<HTMLSelectElement>('[aria-label="筛选状态值"]')!;status.value='failed';status.dispatchEvent(new Event('change',{bubbles:true}));await flushPromises();
  const row=wrapper.get('[data-registration-count-row]');expect(row.text()).toContain('125');expect(row.get('.list-filter-summary').text()).toContain('long-address');
  await row.get('[aria-label="清除状态筛选"]').trigger('click');await flushPromises();
  expect(vi.mocked(api.jobs).mock.calls.at(-1)?.[0]).toMatchObject({email:'long-address',status:'',page:1});
  expect(row.get('.list-filter-summary').text()).toContain('long-address');
 });
 it('keeps short error summaries expandable and uses real jump pagination',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  const result=wrapper.get('[data-registration-result]');expect(result.get('summary').text()).toBe('执行异常');expect(result.text()).toContain('raw diagnostic details');
  expect(wrapper.get('.registration-table-wrap').find('table').exists()).toBe(true);
  const pagination=wrapper.get('nav[aria-label="注册任务分页"]');await pagination.get('[aria-label="跳转页码"]').setValue('4');await pagination.get('form').trigger('submit');await flushPromises();
  expect(vi.mocked(api.jobs).mock.calls.at(-1)?.[0]).toMatchObject({page:4,page_size:20});
 });
 it('retains clickable conditional phases, dependency evidence and native log dismissal',async()=>{
  const {wrapper,api}=setup();
  vi.mocked(api.jobs).mockResolvedValue({items:[],total:0,progress_batch:{batch_id:'batch-test',items:[{id:8,email:'steps@example.test',status:'success'}]}});
  vi.mocked(api.progress).mockResolvedValue({ok:true,job:{id:8,status:'success',progress:{main_steps:[{id:'prepare',label:'准备',state:'success'},{id:'verify',label:'核验',state:'skipped',depends_on:['prepare'],execution:{kind:'conditional',condition:{label:'已获得凭证',state:'not_met'},dependency_state:'satisfied'}}]}}});
  (wrapper.vm as unknown as {setView(view:'launch'):void}).setView('launch');await (wrapper.vm as unknown as {load():Promise<void>}).load();await flushPromises();
  expect(wrapper.find('.registration-progress').exists()).toBe(false);
  expect(api.progress).not.toHaveBeenCalled();
  expect(vi.mocked(api.jobs).mock.lastCall?.[0]).toMatchObject({view:'batch',progress_detail:0});
  await wrapper.get('button[aria-label="查看阶段 · steps@example.test"]').trigger('click');
  await flushPromises();
  expect(api.progress).toHaveBeenCalledWith(8,expect.any(AbortSignal));
  const phase=wrapper.findAll('.registration-steps button').find(button=>button.text().includes('核验'))!;
  expect(phase.text()).toContain('条件未满足');expect(wrapper.get('.registration-progress details').text()).toContain('准备');expect(wrapper.get('.registration-progress details').text()).toContain('已获得凭证');
  await phase.trigger('click');await flushPromises();
  expect(api.log).not.toHaveBeenCalled();
  const log = wrapper.get('.registration-stage-selected').findAll('button').find(button => button.text() === '阶段日志')!;
  await log.trigger('click');await flushPromises();expect(api.log).toHaveBeenCalled();expect(wrapper.find('dialog[open][aria-labelledby="registration-log-title"]').exists()).toBe(true);
  await wrapper.get('dialog[aria-labelledby="registration-log-title"]').trigger('cancel');await flushPromises();expect(wrapper.find('dialog[open][aria-labelledby="registration-log-title"]').exists()).toBe(false);
 });
 it('opens a single failed account and its recorded stage from the batch summary',async()=>{
  const {wrapper,api}=setup();
  vi.mocked(api.jobs).mockResolvedValue({
   progress_batch:{batch_id:'batch-test',total:3,status_counts:{success:1,failed:1,pending:1,active:1},items:[
    {id:7,email:'success@example.test',status:'success'},
    {id:8,email:'failure@example.test',status:'failed',retryable:true,progress:{
     failure:{step_id:'set_twofa',label:'配置 2FA'},
    }},
    {id:9,email:'queued@example.test',status:'pending'},
   ]},
  });
  vi.mocked(api.progress).mockResolvedValue({ok:true,job:{id:8,status:'failed',progress:{
   failure:{step_id:'set_twofa',label:'配置 2FA',message:'校验失败的详细记录'},
   main_steps:[{id:'set_twofa',label:'配置 2FA',state:'failed',message:'校验失败的详细记录'}],
  }}});
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  expect(wrapper.get('[aria-pressed="false"][data-batch-filter="active"]').text()).toBe('运行 / 排队 1');
  expect(wrapper.get('.registration-batch').text()).not.toContain('校验失败的详细记录');
  expect(api.progress).not.toHaveBeenCalled();
  await wrapper.get('[data-batch-filter="failed"]').trigger('click');
  await flushPromises();
  expect(api.progress).toHaveBeenCalledTimes(1);
  expect(wrapper.findAll('.registration-batch-card')).toHaveLength(1);
  expect(wrapper.get('.registration-batch-card').text()).toContain('failure@example.test');
  expect(wrapper.get('.registration-stage-selected').text()).toContain('配置 2FA');
  expect(wrapper.get('.registration-stage-selected').text()).toContain('校验失败的详细记录');
  expect(api.log).not.toHaveBeenCalled();
  await wrapper.get('[data-batch-filter="active"]').trigger('click');
  expect(wrapper.get('.registration-batch-card').text()).toContain('queued@example.test');
  expect(wrapper.find('.registration-progress').exists()).toBe(false);
 });
 it('从批次摘要展示运行耗时和执行时间，失败原因仍然可见',async()=>{
  const {wrapper,api}=setup();
  const now=Date.parse('2026-11-20T10:04:00Z');
  vi.spyOn(Date,'now').mockReturnValue(now);
  launchBatch(api,'timed-batch',[
   {id:7,status:'failed',started_at:'2026-11-20T10:00:00Z',completed_at:'2026-11-20T10:01:30Z',
    retry_count:2,progress:{failure:{label:'配置 2FA'}}},
   {id:8,status:'running',started_at:'2026-11-20T10:02:00Z',progress:{current:{label:'登录验证'}}},
   {id:9,status:'pending'},
   {id:10,status:'success',started_at:'2026-11-20T10:00:00Z',completed_at:'2026-11-20T10:00:19Z',retry_count:0},
   {id:11,status:'cancelled',completed_at:'2026-11-20T10:02:00Z'},
   {id:12,status:'failed',started_at:'无效时间'},
  ]);
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  const [failed,running,pending,success,cancelled,legacy]=wrapper.findAll('.registration-batch-card');
  expect(failed!.text()).toContain('配置 2FA');
  expect(failed!.text()).toContain('#7');
  expect(failed!.text()).toContain('人工重试 2 次');
  expect(failed!.get('.registration-batch-timing').text()).toContain('运行耗时 1 分 30 秒');
  expect(failed!.get('.registration-batch-timing').text()).toMatch(/开始 .+结束 /);
  expect(running!.text()).toContain('登录验证');
  expect(running!.get('.registration-batch-timing').text()).toContain('运行耗时 2 分 0 秒');
  expect(running!.get('.registration-batch-timing').text()).not.toContain('结束');
  expect(pending!.find('.registration-batch-timing').exists()).toBe(false);
  expect(success!.text()).toContain('人工重试 0 次');
  expect(success!.get('.registration-batch-timing').text()).toContain('运行耗时 19.0 秒');
  expect(cancelled!.get('.registration-batch-timing').text()).toMatch(/^结束 /);
  expect(legacy!.find('.registration-batch-timing').exists()).toBe(false);
  expect(legacy!.text()).not.toContain('人工重试');
  expect(api.progress).not.toHaveBeenCalled();
 });
 it('keeps every card in a large batch and opens only the selected job with its exact id',async()=>{
  const {wrapper,api}=setup();
  const items: RegistrationJob[]=Array.from({length:205},(_,index)=>({id:index+1,status:'success'}));
  items.push({id:'9007199254740993',status:'failed',retryable:true});
  launchBatch(api,'large-batch',items);
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  expect(wrapper.findAll('.registration-batch-card')).toHaveLength(206);
  expect(api.progress).not.toHaveBeenCalled();
  await wrapper.get('[aria-controls="registration-stages-9007199254740993"]').trigger('click');
  await flushPromises();
  expect(api.progress).toHaveBeenCalledExactlyOnceWith('9007199254740993',expect.any(AbortSignal));
 });
 it('indicates an in-flight request and lets the same card retry a rejected read',async()=>{
  const {wrapper,api}=setup();let reject!: (reason:Error)=>void;
  launchBatch(api,'retry-batch',[{id:8,status:'failed',progress:{current:{label:'摘要'}}}]);
  vi.mocked(api.progress).mockImplementationOnce(()=>new Promise((_,fail)=>{reject=fail;}))
   .mockResolvedValueOnce({ok:true,job:{id:8,progress:{current:{label:'只有摘要'}}}})
   .mockResolvedValueOnce(progressResponse(8,'已读取的阶段'));
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  await wrapper.get('[aria-controls="registration-stages-8"]').trigger('click');
  expect(wrapper.get('[data-progress-state="loading"]').text()).toContain('正在读取阶段详情');
  expect(wrapper.find('.registration-progress').exists()).toBe(false);
  reject(new Error('详情请求暂不可用'));await flushPromises();
  const error=wrapper.get('[data-progress-state="error"]');
  expect(error.text()).toContain('详情请求暂不可用');
  await error.get('button').trigger('click');await flushPromises();
  expect(wrapper.find('.registration-progress').exists()).toBe(false);
  await wrapper.get('[data-progress-state="error"] button').trigger('click');await flushPromises();
  expect(wrapper.get('[data-progress-state="ready"] .registration-steps').text()).toContain('已读取的阶段');
 });
 it('shows an empty stage history only after a complete detail response',async()=>{
  const {wrapper,api}=setup();
  launchBatch(api,'empty-history-batch',[{id:8,status:'success'}]);
  vi.mocked(api.progress).mockResolvedValueOnce({ok:true,job:{id:8,progress:{main_steps:[]}}});
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  await wrapper.get('[aria-controls="registration-stages-8"]').trigger('click');await flushPromises();
  expect(wrapper.get('[data-progress-state="ready"]').text()).toContain('暂无阶段记录');
 });
 it('refreshes an expanded terminal card after explicitly reloading the batch',async()=>{
  const {wrapper,api}=setup();
  launchBatch(api,'manual-refresh-batch',[{id:8,status:'success'}]);
  vi.mocked(api.progress).mockResolvedValueOnce(progressResponse(8,'已保存阶段'))
   .mockResolvedValueOnce(progressResponse(8,'补齐证据的阶段'));
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  await wrapper.get('[aria-controls="registration-stages-8"]').trigger('click');await flushPromises();
  expect(wrapper.get('[data-progress-state="ready"]').text()).toContain('已保存阶段');
  await (wrapper.vm as any).load({automatic:true});await flushPromises();
  expect(api.progress).toHaveBeenCalledTimes(1);
  await (wrapper.vm as any).load();await flushPromises();
  expect(wrapper.get('[data-progress-state="ready"]').text()).toContain('补齐证据的阶段');
  expect(api.progress).toHaveBeenCalledTimes(2);
 });
 it('cancels obsolete details on a same-job run change and clears expansion after a retry replaces the current job',async()=>{
  const {wrapper,api}=setup();let resolve!: (value:JobProgressResponse)=>void;
  const row={id:8,status:'running',operation_run_id:'5'};
  launchBatch(api,'changing-batch',[row]);
  vi.mocked(api.progress).mockImplementationOnce(()=>new Promise(done=>{resolve=done;}))
   .mockResolvedValueOnce(progressResponse(8,'当前阶段','6'));
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  await wrapper.get('[aria-controls="registration-stages-8"]').trigger('click');
  const firstSignal=vi.mocked(api.progress).mock.calls[0]![1]!;
  launchBatch(api,'changing-batch',[{...row,operation_run_id:'6'}]);
  await (wrapper.vm as any).load({automatic:true});await flushPromises();
  expect(firstSignal.aborted).toBe(true);
  resolve(progressResponse(8,'旧阶段','5'));await flushPromises();
  expect(wrapper.get('[data-progress-state="ready"] .registration-steps').text()).toContain('当前阶段');
  expect(wrapper.text()).not.toContain('旧阶段');
  launchBatch(api,'changing-batch',[{...row,id:9,operation_run_id:'7'}]);
  await (wrapper.vm as any).load({automatic:true});await flushPromises();
  expect(wrapper.get('[aria-controls="registration-stages-9"]').attributes('aria-expanded')).toBe('false');
  expect(api.progress).toHaveBeenCalledTimes(2);
 });
 it('refreshes only the expanded running card on batch polling and cancels it when the batch changes',async()=>{
  const {wrapper,api}=setup();let resolve!: (value:JobProgressResponse)=>void;
  const row={id:8,status:'running',operation_run_id:'5'};
  launchBatch(api,'first-batch',[row,{id:9,status:'running'}]);
  vi.mocked(api.progress).mockResolvedValueOnce(progressResponse(8,'初始阶段','5'))
   .mockImplementationOnce(()=>new Promise(done=>{resolve=done;}));
  (wrapper.vm as any).setView('launch');await (wrapper.vm as any).load();await flushPromises();
  await wrapper.get('[aria-controls="registration-stages-8"]').trigger('click');await flushPromises();
  launchBatch(api,'first-batch',[{...row},{id:9,status:'running'}]);
  await (wrapper.vm as any).load({automatic:true});await flushPromises();
  expect(vi.mocked(api.progress).mock.calls.map(([id])=>id)).toEqual([8,8]);
  const signal=vi.mocked(api.progress).mock.calls[1]![1]!;
  launchBatch(api,'second-batch',[{id:8,status:'running',operation_run_id:'8'}]);
  await (wrapper.vm as any).setBatch('second-batch');await flushPromises();
  expect(signal.aborted).toBe(true);
  resolve(progressResponse(8,'上一批阶段','5'));await flushPromises();
  expect(wrapper.get('[aria-controls="registration-stages-8"]').attributes('aria-expanded')).toBe('false');
  expect(wrapper.text()).not.toContain('上一批阶段');
  expect(api.progress).toHaveBeenCalledTimes(2);
 });
 it('selects manual email mode and shows the server worker count after creation',async()=>{
  const {wrapper,api}=setup();await flushPromises();vi.mocked(api.metadata).mockResolvedValue({manual_mode:true,sources:[],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}});vi.mocked(api.create).mockResolvedValue({submitted:1,workers:2});
  await (wrapper.vm as unknown as {ensureMeta(force?:boolean):Promise<void>}).ensureMeta(true);await flushPromises();
  expect((wrapper.get('.registration-launcher select').element as HTMLSelectElement).value).toBe('manual');
  await wrapper.get('.registration-launcher button').trigger('click');await flushPromises();
  expect(vi.mocked(api.create).mock.calls.at(-1)?.[0]).toMatchObject({email_source:'manual'});expect((wrapper.get('.registration-launcher input[type="number"][step]').element as HTMLInputElement).value).toBe('2');
 });
 it('keeps disabled historical source labels while excluding them from new registration',async()=>{
  const {wrapper,api}=setup();await flushPromises();vi.mocked(api.metadata).mockResolvedValue({sources:[{value:'outlook',label:'Outlook',enabled:true},{value:'email_butler',label:'Email Butler',enabled:false}],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}});
  vi.mocked(api.jobs).mockResolvedValue({items:[{id:7,email:'history@example.test',email_source:'email_butler',status:'success'}],total:1});
  await (wrapper.vm as any).ensureMeta(true);await (wrapper.vm as any).load();await flushPromises();
  expect(wrapper.get('tbody tr').text()).toContain('Email Butler');expect(wrapper.get('.registration-launcher select').text()).not.toContain('Email Butler');
  await wrapper.get('thead button[aria-label="筛选邮箱来源"]').trigger('click');await flushPromises();expect(document.querySelector('[aria-label="筛选邮箱来源值"]')!.textContent).toContain('Email Butler');
 });
 it('preserves compact duration, diagnostic text and pause timing evidence',async()=>{
  const wrapper=mount(RegistrationProgress,{attachTo:document.body,props:{active:true,job:{progress:{main_steps:[{id:'network',label:'分配网络',state:'success',duration_ms:2200,started_at:'2026-11-17T01:00:00Z',completed_at:'2026-11-17T01:00:02.200Z',message:'<img src=x onerror=alert(1)>'},{id:'auth',label:'登录验证',state:'debug_paused',started_at:'2026-11-17T01:00:00Z',debug_pause:{state:'paused',paused_at:'2026-11-17T01:00:03Z',hold_until:'2026-11-17T02:00:00Z'}}]}}}});wrappers.push(wrapper);
  expect(wrapper.get('[data-registration-step-duration]').text()).toContain('2.2');const step=wrapper.get('.registration-steps button');expect(step.attributes('title')).toContain('开始：');expect(step.attributes('title')).toContain('结束：');expect(step.attributes('title')).toContain('<img src=x onerror=alert(1)>');expect(wrapper.find('img').exists()).toBe(false);
  const paused=wrapper.findAll('.registration-steps li')[1]!;expect(paused.text()).toContain('暂停于');expect(paused.text()).toContain('保留至');await paused.get('[aria-label="查看登录验证的关系与证据"]').trigger('click');await flushPromises();expect(wrapper.get('dialog[open]').text()).toContain('等待结束调试');
 });
 it('retains a rejected manual code for retry and shows the owner receipt',async()=>{
  const {wrapper,api}=setup();vi.mocked(api.jobs).mockResolvedValue({items:[{id:8,email:'otp@example.test',email_source:'outlook',status:'running',manual_otp_required:true}],total:1});vi.mocked(api.action).mockRejectedValue(new Error('验证码未接受'));
  await (wrapper.vm as any).load();await flushPromises();const code=wrapper.get('[placeholder="邮箱验证码"]');await code.setValue('123456');await wrapper.findAll('button').find(button=>button.text()==='提交验证码')!.trigger('click');await flushPromises();
  expect(wrapper.text()).toContain('验证码未接受');expect((code.element as HTMLInputElement).value).toBe('123456');expect(api.action).toHaveBeenCalledTimes(1);
 });
 it('shows the explicit disabled registration reason and prevents a launch click',async()=>{
  const {wrapper,api}=setup();await flushPromises();vi.mocked(api.metadata).mockResolvedValue({sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[],capabilities:{features:{register:{enabled:false,reason:'synthetic unavailable'}}}});
  await (wrapper.vm as any).ensureMeta(true);await flushPromises();await wrapper.get('.registration-launcher select').setValue('outlook');const button=wrapper.get('.registration-launcher button');
  expect(button.attributes()).toHaveProperty('disabled');expect(button.attributes('title')).toContain('synthetic unavailable');expect(wrapper.get('.registration-launch').text()).toContain('synthetic unavailable');await button.trigger('click');expect(api.create).not.toHaveBeenCalled();
 });
 it('keeps a selected source when a fresh read returns the same source',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  await wrapper.get('.registration-launcher select').setValue('outlook');
  vi.mocked(api.metadata).mockResolvedValueOnce({sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[],capabilities:{features:{register:{enabled:true}}}});
  await (wrapper.vm as any).loadSources();await flushPromises();
  expect((wrapper.get('.registration-launcher select').element as HTMLSelectElement).value).toBe('outlook');
 });
 it('fails closed when metadata omits the register eligibility result',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  vi.mocked(api.metadata).mockResolvedValueOnce({sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[]});
  await (wrapper.vm as any).ensureMeta(true);await flushPromises();
  const button=wrapper.get('.registration-launcher button[type="submit"]');
  expect(button.attributes('disabled')).toBeDefined();
  expect(wrapper.get('.registration-launch').text()).toContain('注册资格未确认');
  await button.trigger('click');
  expect(api.create).not.toHaveBeenCalled();
 });
 it('shows a recoverable source read error instead of staying in the loading message',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  vi.mocked(api.metadata).mockRejectedValueOnce(new Error('邮箱来源服务暂不可用'));
  await (wrapper.vm as any).ensureMeta(true);
  await flushPromises();
  expect(wrapper.get('.registration-launch').text()).toContain('邮箱来源服务暂不可用');
  expect(wrapper.get('.registration-launch').text()).not.toContain('正在读取邮箱来源');
  expect(wrapper.get('[data-registration-source-retry]').text()).toContain('重试');
 });
 it('restores legacy ratio widths, supports keyboard resizing and resets only registration widths',async()=>{
  localStorage.setItem('gpt_console_table_widths_jobs',JSON.stringify(Array(11).fill(1)));localStorage.setItem('gpt_console_table_total_jobs','2200');localStorage.setItem('gpt_console_table_total_accounts','1900');
  const {wrapper}=setup();await flushPromises();expect(wrapper.get('col').attributes('style')).toContain('200px');
  await wrapper.get('[aria-label="调整ID列宽，方向键调整"]').trigger('keydown',{key:'ArrowRight'});expect(wrapper.findAll('col')[1]!.attributes('style')).toContain('210px');
  await wrapper.get('[aria-label="恢复注册任务列宽"]').trigger('click');expect(localStorage.getItem('gpt_console_table_widths_jobs')).toBeNull();expect(localStorage.getItem('gpt_console_table_total_accounts')).toBe('1900');
 });
});
