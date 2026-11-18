// The production Vue detail owner coordinates report reads; no legacy source slicing.
const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {createRequire}=require('node:module');
const {createVueHarness}=require('../frontend_vue_loader.cjs');
const harness=createVueHarness();
const frontendRequire=createRequire(path.resolve(__dirname,'../../frontend/package.json'));
const {effectScope,ref}=frontendRequire('vue');
const {flushPromises}=frontendRequire('@vue/test-utils');
const {useBulkDetail}=harness.load('src/features/bulk/useBulkDetail.ts');
const scopes=[];test.afterEach(()=>scopes.splice(0).forEach(scope=>scope.stop()));test.after(()=>harness.close());
async function setup(reportRequest){
 const navigation=ref({tab:'bulk',view:'detail',batch_id:'9007199254740993'}),detail={operation:{key:'plan_check'},summary_revision:1,control:{state:'active'},rounds_head:[]};let now=100000;const calls=[];
 const scope=effectScope();scopes.push(scope);
 const state=scope.run(()=>useBulkDetail(()=>navigation.value,{api:{request:async(url,options)=>{calls.push({url,options});if(url.includes('/report?'))return reportRequest(url,detail);if(url.includes('/targets?'))return {items:[],page:{has_more:false,page_size:50}};return structuredClone(detail);}},intents:{pending:()=>[],submit:async()=>({}),recover:async()=>({})},callbacks:{notify(){},navigate(){},updateNavigation(extra){navigation.value={...navigation.value,...extra};},formatDateTime:String,openTask(){}},now:()=>now}));
 await flushPromises();return {state,navigation,detail,calls,advance(){now+=11000;},scope};
}
test('报告按完整范围读取并限制运行中请求频率，完成状态会立即更新',async()=>{
 let phase='running';const h=await setup(async(url,detail)=>({operation_key:'plan_check',phase,summary_revision:detail.summary_revision}));const reports=()=>h.calls.filter(call=>call.url.includes('/report?'));
 await h.state.refreshReport();assert.equal(reports().length,1);assert.equal(reports()[0].url,'/batches/9007199254740993/report?view=current');h.detail.summary_revision=2;await h.state.refresh();assert.equal(reports().length,1);h.advance();await h.state.refresh();assert.equal(reports().length,2);h.detail.control.state='ended';phase='completed';await h.state.refresh();assert.equal(reports().length,3);await h.state.refresh();assert.equal(reports().length,3);await h.state.refreshReport(true);assert.equal(reports().length,4);
});
test('切换轮次会清除旧报告，延迟响应不能覆盖新范围',async()=>{
 let release,pending=false;const h=await setup(async()=>pending?new Promise(resolve=>{release=resolve;}):({operation_key:'plan_check',phase:'running'}));pending=true;const old=h.state.refreshReport(true);const request=h.calls.at(-1);h.navigation.value={...h.navigation.value,round_id:'77'};assert.equal(h.state.report.value,null);assert.equal(request.options.signal.aborted,true);pending=false;release({operation_key:'plan_check',phase:'completed',old:true});await old;await flushPromises();assert.equal(h.state.report.value.old,undefined);assert.equal(h.state.reportLoading.value,false);
});
test('报告单独失败保留已读统计并可重试，不影响账号明细',async()=>{
 let failed=false;const h=await setup(async()=>{if(failed)throw new Error('temporarily unavailable');return {operation_key:'plan_check',phase:'running',summary_revision:1};});const targets=h.state.targets.value;failed=true;await h.state.refreshReport(true);assert.equal(h.state.report.value.phase,'running');assert.match(h.state.reportError.value,/temporarily unavailable/);assert.equal(h.state.targets.value,targets);assert.equal(h.state.reportLoading.value,false);failed=false;await h.state.refreshReport(true);assert.equal(h.state.reportError.value,'');
});
test('首次报告失败按十秒退避，手动重试立即执行',async()=>{
 let calls=0;const h=await setup(async()=>{calls++;throw new Error('offline');});await h.state.refreshReport();assert.equal(calls,1);await h.state.refreshReport(true);assert.equal(calls,2);h.advance();await h.state.refreshReport();assert.equal(calls,3);
});
