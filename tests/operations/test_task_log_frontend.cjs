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
