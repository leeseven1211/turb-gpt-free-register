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
// 任务轮询的筛选、元数据缓存和手动刷新由 useTaskList.test.ts 验证。
test('按国家聚合历史优惠在轻量轮询后保持完整列表的国家徽标与摘要', async t => {
  const account=row(1,{plan_check_status:'failed',plan_check_countries:['US'],account_promotions:[{plan:'plus',kind:'free_trial',country:'US',stale:true}]});
  const h=createReadFixture(t,{handlers:{list:async()=>list([account]),statuses:async()=>status([statusRow(1,{plan_details_revision:'v2',plan_summary:{promotions:[{kind:'free_trial',country:'US',stale:true}],countries:[]}})])}});await h.ready;
  const context={esc:value=>String(value??'')};vm.createContext(context);const start=source.indexOf('function _plusPromotionKind(');vm.runInContext(source.slice(start,source.indexOf('function _planAction(',start)),context);
  const before=context._promotionCell(h.owner.getRowSnapshot('1'));await h.owner.pollStatuses();assert.equal(context._promotionCell(h.owner.getRowSnapshot('1')),before);assert.match(before,/account-promotion-stale/);
});
