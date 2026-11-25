const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {createReadFixture,row,list,status,statusRow,deferred} = require('./read_owner_fixture.cjs');
const source = require('../frontend_script_sources.cjs').readAccountScripts();
test('轻量状态清空旧错误与国家结果，相同详情版本保留按需加载的完整明细', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row(1,{plan_check_error:'旧错误',plan_check_country_results:[{country:'US'}],account_promotions:[{summary:'旧详情'}]})]),statuses:async()=>status([statusRow()],{status_fields:['plan_check_error']}),planDetails:async()=>({ok:true,item:{account_promotions:[{summary:'完整详情'}]}})}});await h.ready;
  await h.owner.pollStatuses();let account=h.owner.getRowSnapshot('1');assert.equal(account.plan_check_error,undefined);assert.deepEqual(h.plain(account.plan_check_country_results),[]);assert.deepEqual(h.plain(account.account_promotions),[]);
  const lease=h.owner.openPlanDetailsConsumer('1');await lease.loadPlanDetails('1',lease.openGeneration);
  h.behavior.statuses=async()=>status([statusRow()],{revision:'status-2',status_fields:['plan_check_error']});await h.owner.pollStatuses();assert.equal(h.owner.getRowSnapshot('1').account_promotions[0].summary,'完整详情');assert.equal(h.detailsRequests.length,1);lease.release();
});
test('详情请求合并且旧响应后自动补拉最新revision，当前打开动作得到完整明细', async t => {
  const firstResponse=deferred();let calls=0;
  const h=createReadFixture(t,{handlers:{planDetails:()=>++calls===1?firstResponse.promise:Promise.resolve({ok:true,item:{account_promotions:[{summary:'最新详情'}]}})}});await h.ready;await h.owner.pollStatuses();
  const first=h.owner.openPlanDetailsConsumer('1'),second=h.owner.openPlanDetailsConsumer('1');const a=first.loadPlanDetails('1',first.openGeneration),b=second.loadPlanDetails('1',second.openGeneration);
  h.behavior.statuses=async()=>status([statusRow(1,{plan_details_revision:'v2'})],{revision:'status-2'});await h.owner.pollStatuses();
  const third=h.owner.openPlanDetailsConsumer('1'),c=third.loadPlanDetails('1',third.openGeneration);firstResponse.resolve({ok:true,item:{account_promotions:[{summary:'过期详情'}]}});
  const results=await Promise.all([a,b,c]);assert.equal(calls,2);for(const result of results){assert.equal(result.revision,'v2');assert.equal(result.item.account_promotions[0].summary,'最新详情');}
  assert.equal(h.owner.getRowSnapshot('1').account_promotions[0].summary,'最新详情');assert.equal(h.detailsRequests[0].signal.aborted,true);first.release();second.release();third.release();
});
// Preserve the legacy metadata regressions through the actual Vue task list owner.
const taskVue=require('./actions_fixture.cjs').vueHarness;
const {effectScope}=require('../../frontend/node_modules/vue');
const {flushPromises}=require('../../frontend/node_modules/@vue/test-utils');
const taskApi=taskVue.load('src/api/tasks.ts').tasksApi;
const {useTaskList}=taskVue.load('src/features/tasks/useTaskList.ts');
const taskResult=(id=7,extra={})=>({ok:true,items:[{id,task_type:'plan_check',status:'success'}],total:1,page:1,page_size:20,revision:'same',...extra});
function taskFixture(t,respond){
  const prior=taskApi.list,calls=[];taskApi.list=(query,signal)=>{calls.push({query:{...query},signal});return respond(query,signal,calls.length);};
  const scope=effectScope(),owner=scope.run(useTaskList);t.after(()=>{scope.stop();taskApi.list=prior;});
  return{owner,calls,settle:flushPromises};
}

test('统一任务轮询复用筛选统计，相同revision不重绘，换筛选立即刷新元数据', async t=>{
  const h=taskFixture(t,async(_query,_signal,count)=>taskResult(7,count===1?{facets:{status:[{value:'success',count:1}]}}:{}));
  h.owner.setVisible(true);await h.settle();const items=h.owner.items.value,facets=h.owner.facets.value;h.owner.toggle(7,true);
  await h.owner.refresh();assert.equal(h.calls.at(-1).query.include_facets,0);assert.equal(h.calls.at(-1).query.include_batches,0);
  assert.equal(h.owner.items.value,items);assert.equal(h.owner.facets.value,facets);assert.equal(h.owner.selected.value.has(7),true);
  h.owner.filters.status='failed';await h.settle();assert.equal(h.calls.at(-1).query.status,'failed');assert.equal(h.calls.at(-1).query.include_facets,1);
  assert.notEqual(h.owner.items.value,items);assert.equal(h.owner.selected.value.size,0);
});

test('手动任务刷新绕过metadata缓存并中止在途轮询，旧响应不会覆盖新统计', async t=>{
  const old=deferred();const h=taskFixture(t,async(_query,_signal,count)=>count===2?old.promise:taskResult(count===1?7:9,{revision:String(count),facets:{status:[{value:count===1?'success':'failed',count:count}]}}));
  await h.owner.refresh();const polling=h.owner.refresh();assert.equal(h.calls[1].query.include_facets,0);
  await h.owner.refresh({metadata:true});assert.equal(h.calls[1].signal.aborted,true);assert.equal(h.calls[2].query.include_facets,1);
  old.resolve(taskResult(7,{facets:{status:[{value:'stale',count:1}]}}));await polling;
  assert.equal(h.owner.items.value[0].id,9);assert.equal(h.owner.facets.value.status[0].value,'failed');
});

test('任务页兼容显式刷新入口传递metadata意图，独立批次导航不被列表重取', async t=>{
  const h=taskFixture(t,async()=>taskResult());
  const TaskCenter=taskVue.load('src/features/tasks/TaskCenter.vue').default;
  const wrapper=taskVue.mount(TaskCenter,{global:{stubs:{TaskDetail:true}}});t.after(()=>wrapper.unmount());
  wrapper.vm.setVisible(true);await h.settle();await wrapper.vm.refresh();assert.equal(h.calls.at(-1).query.include_facets,0);
  await wrapper.vm.refresh({metadata:true});assert.equal(h.calls.at(-1).query.include_facets,1);assert.equal(h.calls.at(-1).query.include_batches,0);
});
test('按国家聚合历史优惠在轻量轮询后保持套餐短标签与历史详情', async t => {
  const account=row(1,{plan_check_status:'failed',plan_check_countries:['US'],account_promotions:[{plan:'plus',kind:'free_trial',country:'US',stale:true}]});
  const h=createReadFixture(t,{handlers:{list:async()=>list([account]),statuses:async()=>status([statusRow(1,{plan_details_revision:'v2',plan_summary:{promotions:[{kind:'free_trial',country:'US',stale:true}],countries:[]}})])}});await h.ready;
  const context={esc:value=>String(value??'')};vm.createContext(context);const start=source.indexOf('function _plusPromotionKind(');vm.runInContext(source.slice(start,source.indexOf('function _planAction(',start)),context);
  const before=context._promotionCell(h.owner.getRowSnapshot('1'));await h.owner.pollStatuses();assert.equal(context._promotionCell(h.owner.getRowSnapshot('1')),before);assert.match(before,/US（历史）/);assert.match(before,/data-promotion-plan="plus"/);
});
