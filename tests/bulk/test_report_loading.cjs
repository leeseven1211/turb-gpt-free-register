const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
function setup(request) {
  const source=fs.readFileSync(path.resolve(__dirname,'../../webui/static/js/pages/bulk/page.js'),'utf8');
  const helper=source.slice(source.indexOf('  function resetPlanReport('),source.indexOf('  function renderBusiness('));
  const state={epoch:1,nav:{batch_id:'9007199254740993'},detail:{operation:{key:'plan_check'},summary_revision:1,control:{state:'active'}}};
  const host={innerHTML:'',hidden:false};let now=100000;
  const ctx={state,Date:{now:()=>now},window:{BulkPlanReport:{render:report=>JSON.stringify(report),loading:()=>'<loading>',error:message=>message}},
    $b:()=>host,preserveMarkup:(node,html)=>{node.innerHTML=html;},request,
    detailParams:()=>new URLSearchParams({view:state.nav.round_id?'round':'current',...(state.nav.round_id?{round_id:state.nav.round_id}:{})}),
    encodeURIComponent,text:String,errorText:(error,prefix)=>prefix+error.message};
  vm.createContext(ctx);vm.runInContext(helper,ctx);ctx.resetPlanReport();return {ctx,state,host,advance:()=>{now+=11000;}};
}
test('报告按完整范围读取并限制运行中请求频率，完成状态会立即更新',async()=>{
  const calls=[];let phase='running';
  const {ctx,state,advance}=setup(async url=>{calls.push(url);return {phase,summary_revision:state.detail.summary_revision};});
  await ctx.loadPlanReport();await ctx.loadPlanReport();assert.equal(calls.length,1);
  assert.match(calls[0],/^\/batches\/9007199254740993\/report\?view=current$/);
  state.detail.summary_revision=2;await ctx.loadPlanReport();assert.equal(calls.length,1);
  advance();await ctx.loadPlanReport();assert.equal(calls.length,2);
  state.detail.control.state='ended';phase='completed';await ctx.loadPlanReport();assert.equal(calls.length,3);
  await ctx.loadPlanReport();assert.equal(calls.length,3);
  await ctx.loadPlanReport({force:true});assert.equal(calls.length,4);
});
test('切换轮次会清除旧报告，延迟响应不能覆盖新范围',async()=>{
  let release;
  const {ctx,state}=setup(()=>new Promise(resolve=>{release=resolve;}));
  const pending=ctx.loadPlanReport();
  state.epoch++;state.nav.round_id='77';ctx.resetPlanReport();
  release({phase:'completed',view:{kind:'current'}});await pending;
  assert.equal(state.planReport,null);assert.equal(state.reportLoading,false);
});
test('报告单独失败保留已读统计并提供重试，不影响账号明细',async()=>{
  let failed=false;
  const {ctx,state,host}=setup(async()=>{if(failed)throw new Error('temporarily unavailable');return {phase:'running',summary_revision:1};});
  await ctx.loadPlanReport();failed=true;await ctx.loadPlanReport({force:true});
  assert.equal(state.planReport.phase,'running');assert.match(host.innerHTML,/重新读取报告/);
  assert.match(state.reportError,/temporarily unavailable/);assert.equal(state.reportLoading,false);
  failed=false;await ctx.loadPlanReport({force:true});assert.equal(state.reportError,'');
});
test('首次报告失败按十秒退避，手动重试立即执行',async()=>{
  let calls=0;
  const {ctx,advance}=setup(async()=>{calls++;throw new Error('offline');});
  await ctx.loadPlanReport();await ctx.loadPlanReport();assert.equal(calls,1);
  await ctx.loadPlanReport({force:true});assert.equal(calls,2);
  advance();await ctx.loadPlanReport();assert.equal(calls,3);
});
