// 验证查询兼容、十进制身份和不明回执恢复，不调用业务接口。
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
function context(fetch = async () => ({ok:true,json:async()=>({ok:true,data:{}})})) {
  const values = new Map();
  const sessionStorage = {getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k),key:i=>[...values.keys()][i],get length(){return values.size;}};
  const sandbox = {window:null,document:{getElementById:()=>null,querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{}},sessionStorage,URLSearchParams,fetch,Date,Math,crypto:require('node:crypto').webcrypto,setTimeout,clearTimeout};
  sandbox.window=sandbox;vm.createContext(sandbox);
  for (const file of ['webui/static/js/shared/account-query.js','webui/static/js/pages/bulk/page.js'])vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),sandbox);
  return sandbox;
}
function plain(value){return JSON.parse(JSON.stringify(value));}
test('旧列表所有查询字段往返不改语义，文本逗号不变成枚举',()=>{
  const {AccountQuery}=context();
  const legacy=new URLSearchParams({archived:'only',plan:'plus,free',email:'some+name@example.invalid',q:'备注:"a/b"',date_from:'2026-10-01',date_to:'2026-10-31',id:'123',source:'hotmail,generic_api',promotion:'none',password:'has',totp:'enabled',risk:'clear',registration_driver:'protocol_oss_2',token:'invalid_401',codex:'success',account_status:'active',email_status:'unmarked'});
  const query=AccountQuery.fromLegacy(legacy);
  assert.equal(query.filters.email,'some+name@example.invalid');
  assert.equal(query.filters.id,'123');
  assert.equal('email' in query,false);
  assert.deepEqual(plain(query.order),[{field:'id',direction:'desc'}]);
  const roundtrip=AccountQuery.toLegacy(query);
  for(const [key,value]of legacy){if(['plan','source'].includes(key))assert.equal(roundtrip.get(key),value.split(',').sort().join(','));else assert.equal(roundtrip.get(key),value,key);}
});
test('归档全部与目标上限保持服务端契约',()=>{
  const {AccountQuery}=context();const query=AccountQuery.normalize({archived:'all',limit:'500',filters:{email:'姓名',id:'9007199254740993'}});
  assert.equal(query.archived,'all');assert.equal(query.limit,500);assert.equal(query.filters.id,'9007199254740993');assert.equal(query.filters.email,'姓名');
});
test('回执丢失复用同幂等键，确认成功后新意图用新键',async()=>{
  const calls=[];let attempt=0;const ctx=context(async(url,options)=>{calls.push({url,options});if(++attempt===1)throw new Error('连接中断');return {ok:true,json:async()=>({ok:true,data:{id:'9007199254740993'}})};});
  await assert.rejects(ctx.BulkTasks.intent('create','/batches',{selection_id:'71'}));
  const result=await ctx.BulkTasks.intent('create','/batches',{selection_id:'71'});
  assert.equal(result.id,'9007199254740993');
  assert.equal(calls[0].options.headers['Idempotency-Key'],calls[1].options.headers['Idempotency-Key']);
  await ctx.BulkTasks.intent('create','/batches',{selection_id:'71'});
  assert.notEqual(calls[1].options.headers['Idempotency-Key'],calls[2].options.headers['Idempotency-Key']);
});
test('不明回执时修改内容不会静默发第二个请求',async()=>{
  let count=0;const ctx=context(async()=>{count++;throw new Error('连接中断');});
  await assert.rejects(ctx.BulkTasks.intent('create','/batches',{selection_id:'71'}));
  await assert.rejects(ctx.BulkTasks.intent('create','/batches',{selection_id:'72'}),e=>e.code==='request_receipt_pending');
  assert.equal(count,1);
});
test('明确配置冲突未受理允许更新设置后新意图',async()=>{
  let count=0;const calls=[];const ctx=context(async(url,options)=>{calls.push(options);return ++count===1?{ok:false,status:409,json:async()=>({ok:false,error:{code:'config_revision_changed',message:'配置已更新'}})}:{ok:true,json:async()=>({ok:true,data:{id:'71'}})};});
  await assert.rejects(ctx.BulkTasks.intent('create','/batches',{expected_config_revision:'1'}),e=>e.code==='config_revision_changed');
  await ctx.BulkTasks.intent('create','/batches',{expected_config_revision:'2'});
  assert.notEqual(calls[0].headers['Idempotency-Key'],calls[1].headers['Idempotency-Key']);
});
test('导航与轮次保留超出JS安全整数的字符串ID',()=>{
  const ctx=context();ctx.BulkTasks.restoreNavigation({tab:'bulk',view:'detail',batch_id:'9007199254740993',round_id:'9007199254740997'});
  assert.equal(ctx.BulkTasks.navigationState().batch_id,'9007199254740993');assert.equal(ctx.BulkTasks.navigationState().round_id,'9007199254740997');
});
test('找回预览同时恢复原功能范围和参数，不把旧名单装入新筛选',()=>{
  const ctx=context();
  const body={operation:{key:'plan_check',version:1},source:{kind:'query',query:{date_from:'2026-10-01',date_to:'2026-10-31',filters:{promotion:['none']},limit:500}},parameters:{timezone_offset_min:-480},expected_config_revision:'old'};
  ctx.BulkTasks.restoreSelectionRequest(body,{id:'71',state:'ready',target_count:500});
  const draft=JSON.parse(ctx.sessionStorage.getItem('turb_bulk_draft_v1'));
  const selected=JSON.parse(ctx.sessionStorage.getItem('turb_bulk_selection_v1'));
  assert.equal(draft.operation_key,'plan_check');assert.equal(draft.query.date_from,'2026-10-01');
  assert.deepEqual(draft.query.filters.promotion,['none']);assert.equal(draft.limit,500);
  assert.equal(draft.parameters.timezone_offset_min,-480);assert.equal(selected.id,'71');
});
test('超过40轮的历史分页在轮询后继续下一页并保留深链所选轮',async()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const load=source.slice(source.indexOf('  async function loadDetail('),source.indexOf('  function renderDetail()'));
  const action=source.slice(source.indexOf('  async function action('),source.indexOf("  document.getElementById('tab-bulk')?.addEventListener('click'"));
  const rounds=(top,bottom)=>Array.from({length:top-bottom+1},(_,index)=>({id:String(top-index),round_no:top-index,state:'completed'}));
  const urls=[];
  const state={loading:false,epoch:1,nav:{batch_id:'71',round_id:'1'},rounds:[],roundsCursor:null,targets:{items:[]},detail:null};
  const sandbox={state,Map,Number,String,encodeURIComponent,URLSearchParams,
    busy:value=>{state.loading=value;},detailParams:()=>new URLSearchParams({view:'round',round_id:'1'}),
    renderDetail:()=>{},loadTargets:async()=>{},clearError:()=>{},report:error=>{throw error;},
    request:async url=>{urls.push(url);if(url.includes('/rounds?'))return url.endsWith('cursor=page2')?{items:rounds(23,4),next_cursor:'page3'}:{items:rounds(3,1),next_cursor:null};return {rounds_head:rounds(43,24),selected_round:{id:'1',round_no:1},rounds_next_cursor:'page2',summary_revision:1};}};
  vm.createContext(sandbox);vm.runInContext(`${load}\n${action}`,sandbox);
  await sandbox.loadDetail();
  assert.equal(state.roundsCursor,'page2');assert.ok(state.rounds.some(round=>round.id==='1'));
  await sandbox.action('more-rounds');
  assert.equal(state.roundsCursor,'page3');
  await sandbox.loadDetail();
  assert.equal(state.roundsCursor,'page3');
  await sandbox.action('more-rounds');
  assert.equal(state.roundsCursor,'');assert.equal(state.rounds.length,43);
  assert.equal(new Set(state.rounds.map(round=>round.id)).size,43);
  assert.deepEqual(urls.filter(url=>url.includes('/rounds?')),['/batches/71/rounds?cursor=page2','/batches/71/rounds?cursor=page3']);
  await sandbox.loadDetail();assert.equal(state.detail.rounds_next_cursor,'');
});

function operationContext(api) {
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/operations/page.js'),'utf8');
  const helper=source.slice(source.indexOf('async function operationIntent('),source.indexOf('async function retryAccountTask('));
  const values=new Map();
  const sandbox={api,sessionStorage:{getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)},crypto:require('node:crypto').webcrypto,Date,Math};
  vm.createContext(sandbox);vm.runInContext(helper,sandbox);return sandbox;
}
test('旧任务中心重跑丢回执后沿原键恢复，确认成功后才换键',async()=>{
  const calls=[];let attempt=0;
  const ctx=operationContext(async(url,options)=>{calls.push({url,options});if(++attempt===1)throw new Error('连接中断');return {data:{round_id:'71'}};});
  await assert.rejects(ctx.operationIntent('retry:17','/api/operations/17/retry'));
  await ctx.operationIntent('retry:17','/api/operations/17/retry');
  assert.equal(calls[0].options.headers['Idempotency-Key'],calls[1].options.headers['Idempotency-Key']);
  await ctx.operationIntent('retry:17','/api/operations/17/retry');
  assert.notEqual(calls[1].options.headers['Idempotency-Key'],calls[2].options.headers['Idempotency-Key']);
});
test('旧任务中心批量重跑不明回执不能换目标重发，明确拒绝可更新',async()=>{
  const calls=[];let attempt=0;
  const ctx=operationContext(async(url,options)=>{calls.push(options);if(++attempt===1)throw new Error('连接中断');const error=new Error('明确未受理');error.status=422;throw error;});
  const original={action:'retry',task_ids:[1,2]};
  await assert.rejects(ctx.operationIntent('bulk:retry','/api/operations/bulk',original));
  await assert.rejects(ctx.operationIntent('bulk:retry','/api/operations/bulk',{action:'retry',task_ids:[3]}),/保持原选择/);
  assert.equal(calls.length,1);
  await assert.rejects(ctx.operationIntent('bulk:retry','/api/operations/bulk',original));
  await assert.rejects(ctx.operationIntent('bulk:retry','/api/operations/bulk',{action:'retry',task_ids:[3]}));
  assert.notEqual(calls[1].headers['Idempotency-Key'],calls[2].headers['Idempotency-Key']);
});

function renderingContext() {
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const labels=source.slice(source.indexOf('  const labels ='),source.indexOf('  const terminal ='));
  const label=source.slice(source.indexOf('  const label ='),source.indexOf('  const busy ='));
  const business=source.slice(source.indexOf('  function renderBusiness('),source.indexOf('  async function loadTargets('));
  const result=source.slice(source.indexOf('  function resultText('),source.indexOf('  function targetId('));
  const host={innerHTML:''};
  const sandbox={Object,Number,String,host,$b:()=>host,preserveMarkup:(element,markup)=>{element.innerHTML=markup;},
    text:value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])),
    facetLabel:(_field,value)=>({none:'无优惠',free_trial:'免费试用',other_promo:'其他优惠'}[value]||value)};
  vm.createContext(sandbox);vm.runInContext(`${labels}\n${label}\n${business}\n${result}`,sandbox);return sandbox;
}
test('五类功能的服务端统计维度都展示中文且保留数量，不泄露内部键',()=>{
  const ctx=renderingContext();
  const metrics={'account.confirmed_no_offer':12,'account.plan.free':13,'account.plus_offer.free_trial':2,'account.plus_offer.other_promo':3,
    'account.comparison.new_offer':4,'account.comparison.not_comparable':5,'country_query.failed':6,
    'account.password_setup.confirmed':7,'account.twofa_setup.confirmed':8,'account.codex.credential_confirmed':9,
    'step.password.confirmed':10,'step.twofa.pending':11,'step.codex.confirmed':12,'step.access_token.pending':13,'step.plan_check.confirmed':14};
  ctx.renderBusiness(metrics);
  for(const key of Object.keys(metrics))assert.equal(ctx.host.innerHTML.includes(key),false,key);
  for(const title of ['本次确认无优惠','套餐 · Free','免费试用','其他优惠','新增优惠','历史条件不可比较','国家项查询失败','密码','2FA','Codex','AT','套餐'])assert.ok(ctx.host.innerHTML.includes(title),title);
  for(const value of Object.values(metrics))assert.ok(ctx.host.innerHTML.includes(`<dd>${value}</dd>`),value);
  ctx.renderBusiness({});assert.equal(ctx.host.innerHTML,'');
});
test('套餐明细区分真实优惠变化和不可比较，待执行不显示旧结果',()=>{
  const ctx=renderingContext();
  const result={query_outcome:'success',account_plan_type:'free',plus_offer_kind:'free_trial',countries_requested:['JP'],country_success_count:1};
  for(const [comparison,label]of Object.entries({unchanged:'优惠未变化',new_offer:'新增优惠',offer_removed:'优惠消失',changed:'优惠变化'})){
    const rendered=ctx.resultText({...result,comparison});assert.ok(rendered.includes(label));assert.ok(rendered.includes('国家项成功 1 / 1'));assert.equal(rendered.includes(comparison),false);
  }
  const incomparable=ctx.resultText({...result,comparison:'not_comparable'});
  assert.equal(incomparable.includes('优惠变化'),false);assert.equal(incomparable.includes('not_comparable'),false);
  assert.equal(ctx.resultText({...result,query_outcome:'pending',comparison:'new_offer'}),'等待本轮查询结果');
  const unconfirmed=ctx.resultText({query_outcome:'unconfirmed',plus_offer_kind:'unknown',comparison:'not_comparable'});
  assert.equal(unconfirmed,'查询待确认');
});
