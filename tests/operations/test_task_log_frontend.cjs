// Common technical time tests remain unchanged; registration scenarios run the actual Vue progress/owner.
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),test=require('node:test'),vm=require('node:vm');
const {createVueHarness}=require('../frontend_vue_loader.cjs');
const harness=createVueHarness(),win=harness.document.defaultView;
win.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
win.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new win.Event('close'));};win.scrollTo=()=>{};
const Progress=harness.load('src/features/registration/RegistrationProgress.vue').default;
const {useRegistration}=harness.load('src/features/registration/useRegistration.ts');
const {stepDuration}=harness.load('src/features/tasks/detail/model.ts');
const {formatDuration}=harness.load('src/features/tasks/presentation.ts');
const live=[];test.afterEach(()=>{live.splice(0).forEach(x=>x.dispose());harness.cleanup();});test.after(()=>harness.close());
const flush=async()=>{await new Promise(r=>setImmediate(r));await harness.nextTick();};
const root=path.join(__dirname,'..','..');
const commonSource=fs.readFileSync(path.join(root,'webui/static/js/shared/common.js'),'utf8');
const dateStart=commonSource.indexOf('function formatDateTime(v)'),dateEnd=commonSource.indexOf('\nfunction taskErrorBadge',dateStart),dateFunctions=commonSource.slice(dateStart,dateEnd);
assert.ok(dateStart>=0&&dateEnd>dateStart,'公共日期格式化函数应存在');
function formatInTimeZone(timeZone,value){const script=`const vm=require('node:vm');const context={Intl,Date,value:${JSON.stringify(value)}};vm.runInNewContext(${JSON.stringify(`${dateFunctions}\nresult=formatDateTime(value);`)},context);process.stdout.write(String(context.result));`;return execFileSync(process.execPath,['-e',script],{env:{...process.env,TZ:timeZone},encoding:'utf8'});}
function progress(steps){return harness.mount(Progress,{props:{job:{id:77,progress_snapshot:{main_steps:steps}},active:true}});}
const TaskFailure = harness.load('src/features/tasks/detail/TaskFailure.vue').default;
const TaskProgress = harness.load('src/features/tasks/detail/TaskProgress.vue').default;
const taskModel = harness.load('src/features/tasks/detail/model.ts');
const taskPresentation = harness.load('src/features/tasks/presentation.ts');
const {useTaskDetail} = harness.load('src/features/tasks/detail/useTaskDetail.ts');
const {effectScope} = require('node:module').createRequire(path.join(__dirname, '../../frontend/package.json'))('vue');
function failureView(failure, execution = null) {
  return harness.mount(TaskFailure, {props: {failure, execution, status: 'request_unknown'}});
}
test('flow_version2 失败摘要显示具体原因和结果状态，并折叠技术证据', () => {
  const failure = {step_id:'auth',stage:'oauth',label:'Codex 授权',event_id:'evt-9',message:'<远端结果待确认>',
    error_info:{code:'REMOTE-001',summary:'远端结果待确认',cause_summary:'密码验证请求返回 HTTP 401'},reconcile_required:true};
  const w = failureView(failure);
  assert.match(w.get('summary').text(), /失败位置：Codex 授权 · oauth.*密码验证请求返回 HTTP 401/);
  assert.doesNotMatch(w.get('summary').text(), /待确认|未确认|需要对账/);
  assert.equal(w.attributes('open'), undefined);
  assert.match(w.get('pre').text(), /<远端结果待确认>/);
  assert.match(w.text(), /事件 evt-9/);
  assert.match(w.get('pre').html(), /&lt;远端结果待确认&gt;/);
  const inferred = failureView({message:'仅凭旁路记录推断',evidence:{inferred:true},error_info:{summary:'待确认'}});
  assert.match(inferred.get('summary').text(), /历史失败位置.*阶段记录缺失.*失败诊断记录缺失/);
  assert.deepEqual(['unconfirmed','not_executed','request_unknown','stopped','attention_required'].map(taskModel.progressLabel),
    ['响应记录缺失','未执行','失败','已中断','失败']);
});
test('待确认状态不要求人工处理，并保留原单状态查询标签', () => {
  for (const status of ['attention_required','manual_reconcile','password_confirmation_pending']) {
    assert.equal(taskPresentation.label('status', status), '失败');
  }
  assert.equal(taskPresentation.label('stage', 'remote_sync'), '原单状态查询');
});
test('详情失败位置优先采用有具体证据纠正的阶段', () => {
  const failure = {label:'校验 Token',stage:'access_token',message:'原单查询 HTTP 404',error_info:{stage:'remote_sync',summary:'原单查询 HTTP 404'}};
  assert.match(failureView(failure).get('summary').text(), /失败位置：原单状态查询/);
  assert.match(failureView({...failure,error_info:null}).get('summary').text(), /校验 Token · access_token/);
});
test('Roxy 登录失败显示具体分类并保留原始事件文案', () => {
  const failure = {label:'登录与身份验证',stage:'authenticate',message:'Roxy 浏览器登录未完成',
    error_info:{code:'roxy_login_page_timeout',summary:'Roxy 登录页未就绪，登录预检请求超时'}};
  const w = failureView(failure);
  assert.match(w.get('summary').text(), /Roxy 登录页未就绪，登录预检请求超时/);
  assert.doesNotMatch(w.get('summary').text(), /Roxy 浏览器登录未完成/);
  assert.match(w.get('pre').text(), /Roxy 浏览器登录未完成/);
  assert.equal(failure.message, 'Roxy 浏览器登录未完成');
});
test('套餐查询失败在详情展示每个国家的具体原因并转义文本', () => {
  const w = failureView({label:'查询套餐',stage:'plan_request',message:'旧泛化摘要',country_failures:[
    {country:'JP',summary:'本地检查发现 AT 已过期，未发起套餐请求'},
    {country:'VN',summary:'服务端返回 HTTP 401 <拒绝>'},{country:'IN'},
  ]});
  assert.deepEqual(w.findAll('li').map(n=>n.text()), ['JP：本地检查发现 AT 已过期，未发起套餐请求','VN：服务端返回 HTTP 401 <拒绝>','IN：诊断记录不完整']);
  assert.match(w.get('ul').html(), /&lt;拒绝&gt;/);
  assert.doesNotMatch(w.get('summary').text(), /旧泛化摘要/);
});
test('自动刷新 AT 失败的具体原因先于逐国旧 AT 错误展示', () => {
  const w = failureView({label:'刷新 AT',stage:'mfa_challenge',message:'自动刷新 AT 失败：MFA 验证被拒绝',
    error_info:{summary:'自动刷新 AT 失败：MFA 验证被拒绝',auto_refresh_at_failed:true},
    country_failures:[{country:'JP',summary:'套餐接口返回 HTTP 401，AT 未通过验证'}]});
  assert.match(w.get('summary').text(), /自动刷新 AT 失败：MFA 验证被拒绝/);
  assert.ok(w.text().indexOf('MFA 验证被拒绝') < w.text().indexOf('JP：套餐接口'));
});
test('混合历史事件按校正后的时间展示且不改变 ID 游标顺序', () => {
  const events = [{id:'10',created_at:'2026-09-08T02:11:15Z'},{id:'20',created_at:'2026-09-08T02:08:37Z'},{id:'30',created_at:'2026-09-08T10:11:15+08:00'}];
  assert.deepEqual(taskModel.orderedEvents(events).map(x=>x.id), ['20','10','30']);
  assert.deepEqual(events.map(x=>x.id), ['10','20','30']);
});
test('步骤筛选同时支持 main_step_id 和 raw_stages，并能清除回全量运行日志', () => {
  const steps = [{id:'step-auth',raw_stages:['authenticate','page']}];
  const events = [{id:'1',main_step_id:'step-auth'},{id:'2',raw_stages:['legacy-auth']},{id:'3',main_step_id:'step-other'},{id:'4',stage:'page'}];
  const filter = value => events.filter(x=>taskModel.matchesStep(x,value,steps)).map(x=>x.id);
  assert.deepEqual(filter('step-auth'), ['1','4']);
  assert.deepEqual(filter('legacy-auth'), ['2']);
  assert.deepEqual(filter(null), ['1','2','3','4']);
  assert.deepEqual(events.filter(x=>taskModel.matchesStep({...x,fields:{}},'step-auth',steps,true)).map(x=>x.id), ['1','4']);
});
test('旧 Run 步骤弹窗在运行切换时关闭并保留阶段筛选入口', async () => {
  const w = harness.mount(TaskProgress,{props:{progress:{task_id:'1',run_id:'2',outcome:{status:'success'},main_steps:[
    {id:'preflight',label:'<配置预检>',state:'pending',display_status:'record_incomplete',duration_ms:1200,attempts:[{state:'running'}]},
  ]},filter:null,active:true,context:'1:2'}});
  assert.match(w.get('.tc-step-select').text(), /记录不完整.*1\.2/s);
  assert.equal(w.get('.tc-step-select').find('配置预检').exists(), false);
  await w.get('.tc-step-select').trigger('click');
  assert.deepEqual(w.emitted('filter'), [['preflight']]);
  await w.get('.tc-step-inspect').trigger('click');
  assert.equal(w.get('.tc-step-dialog').attributes('open'), '');
  await w.setProps({context:'1:3'});
  assert.equal(w.get('.tc-step-dialog').attributes('open'), undefined);
});
test('切换 Run 清除旧步骤筛选，显式传入筛选在空快照加载期间保留', async () => {
  const scope = effectScope();
  const api = {detail:async()=>({task:{id:'1',status:'success',runs:[{id:'2',status:'success'},{id:'3',status:'success'}]}}),
    progress:async()=>({progress:{task_id:'1',run_id:'2',outcome:{status:'success'},main_steps:[]}}),
    events:async()=>({items:[],next_after_id:null,has_more:false}),logs:async()=>({items:[],next_offset:null,has_more:false})};
  const owner = scope.run(()=>useTaskDetail(api));
  try {
    await owner.open('1','2','network');
    assert.equal(owner.stepFilter.value,'network');
    await owner.selectRun('3');
    assert.equal(owner.stepFilter.value,null);
    await owner.open('1','2','auth');
    assert.equal(owner.stepFilter.value,'auth');
  } finally {scope.stop();}
});
test('历史泛化回执消息不能覆盖失败摘要的具体 HTTP 或取码原因', () => {
  for (const cause of ['密码验证请求返回 HTTP 401','邮箱取码等待超时']) {
    const w = failureView({label:'认证',stage:'email_otp',message:'远端结果待确认',error_info:{summary:'结果未知',cause_summary:cause}});
    assert.match(w.get('summary').text(), new RegExp(cause));
    assert.doesNotMatch(w.get('summary').text(), /结果未知|待确认/);
  }
});
test('技术日志时间按浏览器时区转换并支持跨日', () => {
  assert.equal(formatInTimeZone('Asia/Shanghai', '2026-10-08T08:48:32Z'), '2026-10-08 16:48:32');
  assert.equal(formatInTimeZone('America/Los_Angeles', '2026-10-08T08:48:32Z'), '2026-10-08 01:48:32');
  assert.equal(formatInTimeZone('Asia/Shanghai', '2026-10-08T08:48:32+09:00'), '2026-10-08 07:48:32');
  assert.equal(formatInTimeZone('Asia/Shanghai', '2026-10-08T23:30:00-07:00'), '2026-10-09 14:30:00');
});

test('缺失和非法时间保留可诊断信息', () => {
  assert.equal(formatInTimeZone('UTC', null), '-');
  assert.equal(formatInTimeZone('UTC', 'not-a-time'), '无效时间：not-a-time');
  assert.match(dateFunctions, /return s \? `无效时间：\$\{s\}` : '时间缺失'/);
});


test('注册步骤显示耗时和安全悬浮信息，整块卡片仍可查看日志',async()=>{
 const w=progress([{id:'network',label:'分配网络',state:'success',duration_ms:2200,started_at:'2026-10-10T00:00:00Z',completed_at:'2026-10-10T00:00:02.200Z',message:'<img src=x onerror=alert(1)>'}]);await flush();
 const button=w.get('.registration-steps li button');assert.match(button.get('[data-registration-step-duration]').text(),/2\.2\s*秒/);assert.match(button.attributes('title'),/开始.*2026/);assert.match(button.attributes('title'),/<img src=x onerror=alert\(1\)>/);assert.equal(button.find('img').exists(),false);assert.equal(button.find('details').exists(),false);await button.trigger('click');assert.deepEqual(w.emitted('log'),[['network']]);
});
test('执行中的耗时使用当前时间，历史未收口的步骤不继续计时',()=>{
 const started_at='2026-10-10T00:00:00Z',now=Date.parse(started_at)+42000;
 const values=[stepDuration({state:'running',started_at,duration_ms:1000},now),stepDuration({state:'pending',display_status:'record_incomplete',started_at},now),stepDuration({state:'success',duration_ms:0},now),stepDuration({state:'pending'},now)];assert.deepEqual(values,[42000,null,0,null]);assert.match(formatDuration(values[0]),/42\.0\s*秒/);assert.equal(formatDuration(values[1]),'—');assert.doesNotMatch(formatDuration(values[2]),/—/);
});
test('调试暂停冻结当前步骤计时，历史缺失暂停时间不倒推',async()=>{
 const started_at='2026-10-13T10:00:00Z',debug_pause={state:'paused',paused_at:'2026-10-13T10:00:42Z',hold_until:'2026-10-13T10:30:42Z',reason:'不可显示'},step={id:'auth',label:'认证',state:'running',display_status:'debug_paused',started_at,debug_pause};
 assert.deepEqual([stepDuration(step,Date.parse(started_at)+90000),stepDuration(step,Date.parse(started_at)+180000),stepDuration({...step,debug_pause:{state:'paused'},duration_ms:1000}),stepDuration({state:'failed',duration_ms:2000,debug_pause})],[42000,42000,null,2000]);const w=progress([step]);await flush();const title=w.get('.registration-steps li button').attributes('title');assert.match(title,/调试暂停.*等待结束调试/);assert.match(title,/暂停于.*保留至/);assert.doesNotMatch(title,/不可显示/);const missing=progress([{...step,debug_pause:{state:'paused'}}]);await flush();assert.match(missing.get('.registration-steps li button').attributes('title'),/暂停时间未记录/);
});
test('注册任务日志入口传递 operation task、Run 和步骤映射',async()=>{
 const calls=[],logs=[];const owner=useRegistration({visible:false,openTask:(...args)=>calls.push(args),api:{log:async id=>(logs.push(id),{job:{id,status:'success'},log:'synthetic'}),debug:async()=>({enabled:false}),diagnostics:async()=>({captured:false})}});live.push(owner);owner.state.jobs=[{id:7,operation_task_id:'9007199254740993',operation_run_id:'9007199254740995'},{id:99}];owner.openLog(7,'step-auth');assert.deepEqual(calls,[['9007199254740993','9007199254740995','step-auth']]);assert.equal(owner.state.detail.id,null);owner.openLog(99);await flush();assert.deepEqual(logs,[99]);assert.equal(owner.state.detail.id,99);
});
test('批次进度优先使用 v2 main_steps 的实际顺序并转义标签',async()=>{
 const w=harness.mount(Progress,{props:{active:true,job:{progress_steps:{legacy:{state:'success'}},progress:{},progress_snapshot:{flow_version:'flow_version2',main_steps:[{id:'observed',label:'<已观察>',state:'request_unknown',raw_stages:['oauth'],duration_ms:'invalid'},{id:'skipped',label:'已跳过步骤',state:'skipped'},{id:'pending',label:'未观察步骤',state:'skipped',display_status:'not_executed'}]}}}});await flush();const buttons=w.findAll('.registration-steps li>button:first-child');assert.equal(buttons.length,2);assert.match(buttons[0].text(),/<已观察>/);assert.match(buttons[1].text(),/未观察步骤.*未执行/);assert.match(buttons[0].html(),/&lt;已观察&gt;/);assert.doesNotMatch(w.text(),/NaN|错误旧顺序|legacy/);assert.match(buttons[0].text(),/失败/);await buttons[0].trigger('click');assert.deepEqual(w.emitted('log'),[['observed']]);
});
test('进度详情按真实阶段显示事件，不把开始和完成算成重试',async()=>{
 const step={id:'authenticate',label:'登录与身份验证',state:'running',raw_stages:['page','submit_email','auth_redirect','login_password','email_otp'],children:[{id:'page',label:'打开页面',state:'success',duration_ms:51000},{id:'submit_email',label:'提交邮箱',state:'running',started_at:'2026-10-13T08:49:09Z'}],attempts:[{raw_stage:'page',raw_stage_label:'打开页面',state:'running',created_at:'2026-10-13T08:48:18Z',step_instance_id:'page-a'},{raw_stage:'page',raw_stage_label:'打开页面',state:'success',created_at:'2026-10-13T08:49:09Z',step_instance_id:'page-a'},{raw_stage:'submit_email',raw_stage_label:'提交邮箱',state:'running',created_at:'2026-10-13T08:49:09Z',step_instance_id:'email-a'}]};const w=progress([step]);await flush();const title=w.get('.registration-steps li>button:first-child').attributes('title');assert.match(title,/已记录阶段.*打开页面.*提交邮箱/);assert.doesNotMatch(title,/login_password|email_otp|尝试记录/);await w.get('[aria-label="查看登录验证的关系与证据"]').trigger('click');await flush();const evidence=w.get('dialog .tc-step-evidence'),events=evidence.findAll('details').find(x=>x.find('summary').text().startsWith('阶段事件'));assert.ok(events);assert.match(events.get('summary').text(),/3/);assert.equal(events.findAll('ol>li').length,3);assert.match(events.text(),/打开页面.*已完成|已完成.*打开页面/);assert.doesNotMatch(events.text(),/重试|尝试记录/);assert.match(evidence.text(),/51\.0\s*秒/);
});
test('旧阶段事件缺少实际时间时明确提示，不能借用阶段开始时间',async()=>{
 const step={id:'authenticate',label:'登录与身份验证',state:'running',attempts:[{raw_stage:'submit_email',raw_stage_label:'提交邮箱',state:'running',started_at:'2026-10-13T09:24:23Z',created_at:null,event_time_known:false}]};const w=progress([step]);await flush();assert.match(w.get('.registration-steps li>button:first-child').attributes('title'),/提交邮箱.*发生时间未记录/);await w.get('[aria-label="查看登录验证的关系与证据"]').trigger('click');await flush();const event=w.get('dialog .tc-event-meta');assert.match(event.text(),/发生时间未记录/);assert.doesNotMatch(event.text(),/09:24:23/);
});
