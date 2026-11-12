// 报告使用完整统计接口，不从分页行数、分项重叠或缺失字段猜测账号结果。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function renderer() {
  const sandbox = {window:{},Date,Number,String,Math};
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.resolve(__dirname,'../../webui/static/js/pages/bulk/report.js'),'utf8'),sandbox);
  return sandbox.window.BulkPlanReport;
}
function fixture() {
  return {schema_version:1,operation_key:'plan_check',batch_id:'9007199254740993',view:{kind:'current'},phase:'completed',
    generated_at:'2026-11-12T08:00:00Z',totals:{accounts:100,success:80,failed:9,partial_success:3,not_executed:5,cancelled:3,active:0,completed:100},
    duration:{sample_count:92,missing_count:8,avg_seconds:68,min_seconds:0.75,max_seconds:3725},
    at_refresh:{expired_accounts:15,invalid_accounts:4,missing_token_accounts:2,attempted_accounts:21,succeeded_accounts:18,failed_accounts:3,pending_accounts:0,not_needed_accounts:71,unknown_accounts:0,not_executed_accounts:8},
    plans:[{plan:'free',accounts:83},{plan:'plus',accounts:7},{plan:'unknown',accounts:10}],
    offers:{with_offer_accounts:12,confirmed_no_offer_accounts:75,unknown_accounts:13,
      by_plan:[{plan:'plus',accounts:9,kinds:[{kind:'free_trial',accounts:6},{kind:'discount',accounts:3}]},
        {plan:'go',accounts:8,kinds:[{kind:'free_trial',accounts:8}]}]}};
}
test('完成报告按账号去重总数展示，套餐和优惠分项重叠不改变总数',()=>{
  const html=renderer().render(fixture());
  assert.match(html,/查套餐完成报告/);assert.match(html,/当前结果 · 每个账号取最近一轮/);
  assert.match(html,/<dt>有优惠账号<\/dt><dd>12<span>个/);
  assert.match(html,/同一账号可符合多个套餐或优惠，分项数量可能重叠/);
  assert.match(html,/当前订阅套餐/);assert.match(html,/本次查询确认的套餐状态/);
  assert.match(html,/免费试用/);assert.match(html,/折扣优惠/);assert.match(html,/>Go<\/strong>/);assert.match(html,/>Plus<\/strong>/);
  assert.doesNotMatch(html,/<dt>有优惠账号<\/dt><dd>17/);
});
test('运行中与历史轮次标题及统计范围明确，部分成功独立展示',()=>{
  const data=fixture();data.phase='running';data.view={kind:'round',round_id:'9007199254740997',round_no:3};
  data.totals.active=40;data.totals.completed=60;
  const html=renderer().render(data);
  assert.match(html,/查套餐实时报告/);assert.match(html,/重跑 2 · 固定名单/);
  assert.match(html,/<dt>成功<\/dt><dd>80/);assert.match(html,/<dt>失败<\/dt><dd>9/);
  assert.match(html,/<dt>部分成功<\/dt><dd>3/);assert.match(html,/<dt>待完成<\/dt><dd>40/);
  assert.match(html,/已结束 60 \/ 100 个/);assert.match(html,/未执行 5 个/);assert.match(html,/已取消 3 个/);
  data.view.round_no=1;assert.match(renderer().render(data),/首轮名单/);
});
test('账号执行耗时保留有效样本与缺失说明，平均值不包含排队',()=>{
  const html=renderer().render(fixture());
  assert.match(html,/已结束样本 92 个/);assert.match(html,/1 分 8 秒/);
  assert.match(html,/0.75 秒/);assert.match(html,/1 小时 2 分 5 秒/);
  assert.match(html,/8 个已结束账号缺少有效耗时，未计入均值/);
  assert.match(html,/含自动刷新及链内等待，不含开始前排队/);
});
test('AT过期与远端失效及刷新结果分别展示，缺少证据不推定未过期',()=>{
  const html=renderer().render(fixture());
  assert.match(html,/<dt>AT 过期<\/dt><dd>15/);assert.match(html,/<dt>远端拒绝 AT<\/dt><dd>4/);
  assert.match(html,/<dt>缺少 AT<\/dt><dd>2/);assert.match(html,/<dt>尝试刷新<\/dt><dd>21/);
  assert.match(html,/<dt>刷新成功<\/dt><dd>18/);assert.match(html,/<dt>刷新失败<\/dt><dd>3/);
  assert.match(html,/刷新状态待确认 0 个 · 未开始执行 8 个/);
  assert.match(html,/待确认含执行中尚无结果及历史证据缺失/);
});
test('缺失字段使用未知占位，零结果仍是零，不显示NaN或伪造成功数',()=>{
  const data=fixture();data.totals.success=null;data.duration={sample_count:0,missing_count:2};
  data.at_refresh={unknown_accounts:91};data.offers={with_offer_accounts:0,confirmed_no_offer_accounts:0,unknown_accounts:100,by_plan:[]};
  const html=renderer().render(data);
  assert.match(html,/<dt>成功<\/dt><dd>—/);assert.match(html,/<dt>平均耗时<\/dt><dd>—/);
  assert.match(html,/<dt>AT 过期<\/dt><dd>—/);assert.match(html,/刷新状态待确认 91 个/);
  assert.match(html,/<dt>有优惠账号<\/dt><dd>0/);assert.match(html,/本次尚未查到可用优惠/);
  assert.doesNotMatch(html,/NaN|undefined|Infinity/);
});
test('不可信套餐和优惠标签、错误文本均转义，宽度由有限数值限制',()=>{
  const data=fixture();data.plans=[{plan:'<img src=x onerror=alert(1)>',accounts:2}];
  data.offers.by_plan=[{plan:'<script>bad()</script>',accounts:Infinity,kinds:[{kind:'" onclick="bad()',accounts:-1}]}];
  const ui=renderer(),html=ui.render(data);
  assert.doesNotMatch(html,/<img|<script|width:NaN|width:Infinity/);
  assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html,/&lt;script&gt;bad\(\)&lt;\/script&gt;/);
  assert.match(html,/&quot; onclick=&quot;bad\(\)/);assert.match(html,/width:0\.000%/);
  assert.match(ui.error('<script>error</script>'),/&lt;script&gt;error&lt;\/script&gt;/);
  assert.match(ui.loading(),/role="status"/);assert.equal(ui.render({operation_key:'token_refresh'}),'');
});
test('名单尚未固定不把准备中误显示为零账号，汇总延迟有明确提示',()=>{
  const data=fixture();data.population_ready=false;data.phase='preparing';data.totals.accounts=0;
  let html=renderer().render(data);
  assert.match(html,/账号名单准备中，固定后生成报告/);assert.doesNotMatch(html,/0 个账号|确认无优惠/);
  data.phase='completed';assert.match(renderer().render(data),/该轮名单未固定，无法生成账号统计/);
  data.population_ready=true;data.phase='running';data.projection={state:'syncing'};
  html=renderer().render(data);assert.match(html,/执行结果正在汇总，以下统计尚未收齐/);
});
