// Exercise the production Vue report. Statistics come from the complete report response.
const test=require('node:test');
const assert=require('node:assert/strict');
const {createVueHarness}=require('../frontend_vue_loader.cjs');
const harness=createVueHarness();
const BulkReport=harness.load('src/features/bulk/BulkReport.vue').default;
const {operationNames}=harness.load('src/features/bulk/bulkDetailPresentation.ts');
test.afterEach(()=>harness.cleanup());test.after(()=>harness.close());
function report(data){return harness.mount(BulkReport,{props:{report:data,formatDateTime:value=>String(value||'—')}});}
function metric(wrapper,title){return wrapper.findAll('dt').find(node=>node.text()===title)?.element.nextElementSibling.textContent;}
function fixture(){return {schema_version:1,operation_key:'plan_check',batch_id:'9007199254740993',view:{kind:'current'},phase:'completed',generated_at:'2026-11-12T08:00:00Z',totals:{accounts:100,success:80,failed:9,partial_success:3,not_executed:5,cancelled:3,active:0,completed:100},duration:{sample_count:92,missing_count:8,avg_seconds:68,min_seconds:.75,max_seconds:3725},at_refresh:{expired_accounts:15,invalid_accounts:4,missing_token_accounts:2,attempted_accounts:21,succeeded_accounts:18,failed_accounts:3,pending_accounts:0,not_needed_accounts:71,unknown_accounts:0,not_executed_accounts:8},plans:[{plan:'free',accounts:83},{plan:'plus',accounts:7},{plan:'unknown',accounts:10}],offers:{with_offer_accounts:12,confirmed_no_offer_accounts:75,unknown_accounts:13,by_plan:[{plan:'plus',accounts:9,kinds:[{kind:'free_trial',accounts:6},{kind:'discount',accounts:3}]},{plan:'go',accounts:8,kinds:[{kind:'free_trial',accounts:8}]}]}};}
test('完成报告按账号去重总数展示，套餐和优惠分项重叠不改变总数',()=>{
 const wrapper=report(fixture()),text=wrapper.text();assert.match(text,/查套餐完成报告/);assert.match(text,/当前结果 · 每个账号取最近一轮/);assert.equal(metric(wrapper,'有优惠账号'),'12个');assert.match(text,/分项数量可能重叠/);assert.match(text,/当前订阅套餐/);assert.match(text,/本次查询确认的套餐状态/);assert.match(text,/免费试用/);assert.match(text,/折扣优惠/);assert.match(text,/Go/);assert.match(text,/Plus/);
});
test('运行中与历史轮次标题及统计范围明确，部分成功独立展示',()=>{
 const data=fixture();data.phase='running';data.view={kind:'round',round_id:'9007199254740997',round_no:3};data.totals.active=40;data.totals.completed=60;
 const wrapper=report(data),text=wrapper.text();assert.match(text,/查套餐实时报告/);assert.match(text,/重跑 2 · 固定名单/);assert.equal(metric(wrapper,'成功'),'80个');assert.equal(metric(wrapper,'失败'),'9个');assert.equal(metric(wrapper,'部分成功'),'3个');assert.equal(metric(wrapper,'待完成'),'40个');assert.match(text,/已结束 60 \/ 100 个/);assert.match(text,/未执行 5 个/);assert.match(text,/已取消 3 个/);data.view.round_no=1;assert.match(report(data).text(),/首轮名单/);
});
test('账号执行耗时保留有效样本与缺失说明，平均值不包含排队',()=>{
 const text=report(fixture()).text();for(const term of ['已结束样本 92 个','1 分 8 秒','0.75 秒','1 小时 2 分 5 秒','8 个已结束账号缺少有效耗时，未计入均值','含自动刷新及链内等待，不含开始前排队'])assert.ok(text.includes(term),term);
});
test('AT过期与远端失效及刷新结果分别展示，缺少证据不推定未过期',()=>{
 const wrapper=report(fixture());for(const [title,value]of [['AT 过期',15],['远端拒绝 AT',4],['缺少 AT',2],['尝试刷新',21],['刷新成功',18],['刷新失败',3]])assert.equal(metric(wrapper,title),`${value}个`);assert.match(wrapper.text(),/刷新状态待确认 0 个 · 未开始执行 8 个/);assert.match(wrapper.text(),/待确认含执行中尚无结果及历史证据缺失/);
});
test('缺失字段使用未知占位，零结果仍是零，不显示NaN或伪造成功数',()=>{
 const data=fixture();data.totals.success=null;data.duration={sample_count:0,missing_count:2};data.at_refresh={unknown_accounts:91};data.offers={with_offer_accounts:0,confirmed_no_offer_accounts:0,unknown_accounts:100,by_plan:[]};const wrapper=report(data);assert.equal(metric(wrapper,'成功'),'—个');assert.equal(metric(wrapper,'平均耗时'),'—');assert.equal(metric(wrapper,'AT 过期'),'—个');assert.match(wrapper.text(),/刷新状态待确认 91 个/);assert.equal(metric(wrapper,'有优惠账号'),'0个');assert.match(wrapper.text(),/本次尚未查到可用优惠/);assert.doesNotMatch(wrapper.text(),/NaN|undefined|Infinity/);
});
test('不可信套餐和优惠标签按文本展示，宽度由有限数值限制',()=>{
 const data=fixture();data.plans=[{plan:'<img src=x onerror=alert(1)>',accounts:2}];data.offers.by_plan=[{plan:'<script>bad()</script>',accounts:Infinity,kinds:[{kind:'" onclick="bad()',accounts:-1}]}];const wrapper=report(data);assert.equal(wrapper.findAll('img,script').length,0);assert.match(wrapper.text(),/<img src=x onerror=alert\(1\)>/);assert.match(wrapper.text(),/<script>bad\(\)<\/script>/);assert.match(wrapper.text(),/" onclick="bad\(\)/);assert.equal(wrapper.findAll('.bulk-report-rail > span').some(node=>/NaN|Infinity/.test(node.attributes('style'))),false);assert.ok(wrapper.findAll('.bulk-report-rail > span').some(node=>node.element.style.width==='0%'));
});
test('名单尚未固定不把准备中误显示为零账号，汇总延迟有明确提示',()=>{
 const data=fixture();data.population_ready=false;data.phase='preparing';data.totals.accounts=0;let wrapper=report(data);assert.match(wrapper.text(),/账号名单准备中，固定后生成报告/);assert.doesNotMatch(wrapper.text(),/0 个账号|确认无优惠/);data.phase='completed';assert.match(report(data).text(),/该轮名单未固定，无法生成账号统计/);data.population_ready=true;data.phase='running';data.projection={state:'syncing'};assert.match(report(data).text(),/执行结果正在汇总，以下统计尚未收齐/);
});
test('六种任务均展示正确报告标题，共用结果耗时并保留独立功能统计',()=>{
 for(const [key,name]of Object.entries(operationNames)){const data=fixture();data.operation_key=key;data.business_summary={'account.codex.credential_confirmed':18};let wrapper=report(data);assert.ok(wrapper.text().includes(`${name}完成报告`));assert.equal(metric(wrapper,'成功'),'80个');assert.match(wrapper.text(),/平均耗时/);assert.match(wrapper.text(),/Codex 凭证已确认/);
 if(key==='plan_check'){assert.match(wrapper.text(),/AT 检查与自动刷新/);assert.match(wrapper.text(),/优惠结果/);assert.match(wrapper.text(),/更多查询统计/);}else{assert.match(wrapper.text(),/功能统计/);assert.doesNotMatch(wrapper.text(),/AT 检查与自动刷新|有优惠账号|当前订阅套餐/);delete data.business_summary;assert.match(report(data).text(),/暂无已确认的功能统计/);}
 data.phase='running';assert.ok(report(data).text().includes(`${name}实时报告`));data.population_ready=false;assert.equal(report(data).attributes('aria-label'),`${name}报告`);}
});
test('通用报告的缺失统计保持未知，准备和投影失败提示不冒充完成',()=>{
 const data=fixture();data.operation_key='codex_retry';data.totals={accounts:2,failed:0};data.duration={};data.phase='running';data.projection={state:'failed'};const wrapper=report(data);assert.match(wrapper.text(),/补 Codex实时报告/);assert.equal(metric(wrapper,'成功'),'—个');assert.equal(metric(wrapper,'失败'),'0个');assert.equal(metric(wrapper,'平均耗时'),'—');assert.match(wrapper.text(),/结果汇总暂时失败/);assert.doesNotMatch(wrapper.text(),/NaN|undefined|查套餐|优惠结果/);
});
