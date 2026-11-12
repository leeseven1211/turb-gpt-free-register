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
  const stateHelpers=source.slice(source.indexOf('  const failedAliases ='),source.indexOf('  const operationNames ='));
  const label=source.slice(source.indexOf('  const label ='),source.indexOf('  const busy ='));
  const business=source.slice(source.indexOf('  function renderBusiness('),source.indexOf('  async function loadTargets('));
  const result=source.slice(source.indexOf('  function resultText('),source.indexOf('  function targetId('));
  const host={innerHTML:''};
  const sandbox={Object,Number,String,host,$b:()=>host,preserveMarkup:(element,markup)=>{element.innerHTML=markup;},
    text:value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])),
    facetLabel:(_field,value)=>({none:'无优惠',free_trial:'免费试用',other_promo:'其他优惠'}[value]||value)};
  vm.createContext(sandbox);vm.runInContext(`${labels}\n${stateHelpers}\n${label}\n${business}\n${result}`,sandbox);return sandbox;
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
  assert.equal(unconfirmed,'查询失败');
});
test('AT 刷新展示本轮结果，确认与失败统计不显示内部字段名',()=>{
  const ctx=renderingContext();
  for(const [outcome,title]of Object.entries({pending:'等待本轮 AT 刷新',success:'本轮 AT 刷新成功',failed:'本轮 AT 刷新失败',unconfirmed:'本轮 AT 刷新失败',not_executed:'本轮未执行 AT 刷新'})){
    assert.equal(ctx.resultText({refresh_outcome:outcome,confirmation:'unconfirmed'}),title);
  }
  ctx.renderBusiness({'account.token_refresh.confirmed':8,'account.token_refresh.unconfirmed':2,'account.token_refresh.failed':3});
  assert.ok(ctx.host.innerHTML.includes('刷新'));
  for(const value of [8,5])assert.ok(ctx.host.innerHTML.includes(`<dd>${value}</dd>`));
  assert.equal(ctx.host.innerHTML.includes('account.token_refresh'),false);
});

test('筛选选项的旧响应不能覆盖更新后的归档范围',async()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const helper=source.slice(source.indexOf('  async function ensureFacets('),source.indexOf('  function scheduleFacets('));
  const queries=Object.create(null);const ctx=context();
  ctx.state={draft:{query:{archived:'0'}},facetsCache:new Map()};
  ctx.request=url=>new Promise(resolve=>{queries[JSON.parse(decodeURIComponent(url.split('?query=')[1])).archived]=resolve;});
  vm.runInContext(helper,ctx);
  const before=ctx.ensureFacets();ctx.state.draft.query={archived:'only'};
  const after=ctx.ensureFacets();
  queries.only({facets:{source:[{value:'icloud_hide'}]}});await after;
  queries['0']({facets:{source:[{value:'outlook'}]}});await before;
  assert.equal(ctx.state.facets.source[0].value,'icloud_hide');
  assert.equal(ctx.state.facetsCache.size,2);
});

test('切回缓存筛选时恢复对应匹配数，等待读取时清除旧数量',async()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const helper=source.slice(source.indexOf('  async function ensureFacets('),source.indexOf('  function scheduleFacets('));
  const ctx=context();const seen=[];let calls=0;
  ctx.state={draft:{query:{archived:'0'}},facetsCache:new Map()};
  ctx.renderMatch=()=>seen.push(ctx.state.matched);
  ctx.request=async url=>{calls++;const query=JSON.parse(decodeURIComponent(url.split('?query=')[1]));return {facets:{source:[]},matched:query.archived==='only'?3:42};};
  vm.runInContext(helper,ctx);
  await ctx.ensureFacets();assert.equal(ctx.state.matched,42);
  ctx.state.draft.query={archived:'only'};await ctx.ensureFacets();assert.equal(ctx.state.matched,3);
  ctx.state.draft.query={archived:'0'};await ctx.ensureFacets();assert.equal(ctx.state.matched,42);
  assert.equal(calls,2);assert.deepEqual(seen,[null,42,null,3,42]);
});

function selectionSummaryContext() {
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const helper=source.slice(source.indexOf('  function renderSelection('),source.indexOf('  async function createBatch('));
  const nodes=Object.fromEntries(['[data-bulk-submit]','[data-bulk-action="create-paused"]',
    '[data-bulk-create-summary]','[data-bulk-create-hint]','[data-bulk-side-count]','[data-bulk-side-warning]']
    .map(selector=>[selector,{textContent:'',hidden:false,disabled:false}]));
  nodes['[data-bulk-create-form]']={querySelectorAll:()=>[]};
  const ctx={state:{draft:{source:null,limit:''},selection:null,matched:500},nodes,
    $b:selector=>nodes[selector],renderSideSummary:()=>{}};
  vm.createContext(ctx);vm.runInContext(helper,ctx);return ctx;
}
test('执行摘要按数量上限展示本批数量，零匹配时禁用两种创建入口',()=>{
  const ctx=selectionSummaryContext();
  ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-side-count]'].textContent,'500 个');
  assert.equal(ctx.nodes['[data-bulk-side-warning]'].hidden,false);
  ctx.state.draft.limit='50';ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-side-count]'].textContent,'50 个');
  assert.equal(ctx.nodes['[data-bulk-side-warning]'].hidden,true);
  assert.equal(ctx.nodes['[data-bulk-submit]'].disabled,false);
  ctx.state.matched=0;ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-side-count]'].textContent,'0 个');
  assert.equal(ctx.nodes['[data-bulk-submit]'].disabled,true);
  assert.equal(ctx.nodes['[data-bulk-action="create-paused"]'].disabled,true);
});
test('固定账号名单的执行摘要不受无关筛选匹配数和数量上限影响',()=>{
  const ctx=selectionSummaryContext();
  ctx.state.draft={source:{kind:'ids',ids:['1','2']},limit:'1'};
  ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-side-count]'].textContent,'2 个');
  assert.equal(ctx.nodes['[data-bulk-side-warning]'].hidden,true);
  ctx.state.draft.source={kind:'batch_targets',batch_id:'71'};ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-side-count]'].textContent,'创建时确认');
  assert.equal(ctx.nodes['[data-bulk-create-hint]'].textContent,'创建时沿用原批次固定名单');
  ctx.state.selection={state:'ready',target_count:17};ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-side-count]'].textContent,'17 个');
});

function queryFilterContext() {
  const ctx=context();
  ctx.facetLabel=(field,value)=>({none:'无优惠',free_trial:'免费试用',expired:'已过期',has:'有 Token'}[value]||value);
  vm.runInContext(fs.readFileSync(path.join(root,'webui/static/js/shared/account-filters.js'),'utf8'),ctx);
  return ctx;
}
test('筛选摘要保留日期、多选、归档及精确文本，不从展示标签重建查询',()=>{
  const ctx=queryFilterContext();
  const query=ctx.AccountQuery.normalize({date_from:'2026-10-01',date_to:'2026-10-31',archived:'all',q:'备注:"a/b"',
    plan:['free','plus'],filters:{email:'some+name@example.invalid',promotion:['none','free_trial'],token:['expired'],id:'9007199254740993'}});
  const before=JSON.stringify(query);
  const chips=plain(ctx.AccountFilters.chips(query,{fields:[]}));
  assert.ok(chips.some(([key,title])=>key==='dates'&&title.includes('2026-10-01')&&title.includes('2026-10-31')));
  assert.ok(chips.some(([key,title])=>key==='promotion'&&title.includes('无优惠')&&title.includes('免费试用')));
  assert.ok(chips.some(([key,title])=>key==='email'&&title.includes('some+name@example.invalid')));
  assert.ok(chips.some(([key,title])=>key==='id'&&title.includes('9007199254740993')));
  assert.ok(chips.some(([key])=>key==='archived'));
  assert.equal(JSON.stringify(query),before);
});
test('执行摘要等待匹配和正在创建时清除旧数量并阻止重复提交',()=>{
  const ctx=selectionSummaryContext();
  ctx.state.matched=null;ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-side-count]'].textContent,'匹配中');
  assert.equal(ctx.nodes['[data-bulk-side-warning]'].hidden,true);
  ctx.state.matched=42;ctx.state.creating=true;ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-submit]'].disabled,true);
  assert.equal(ctx.nodes['[data-bulk-action="create-paused"]'].disabled,true);
  assert.equal(ctx.nodes['[data-bulk-create-summary]'].textContent,'正在固定账号范围…');
  ctx.state.creating=false;ctx.renderSelection();
  assert.equal(ctx.nodes['[data-bulk-submit]'].disabled,false);
  assert.equal(ctx.nodes['[data-bulk-action="create-paused"]'].disabled,false);
});

function createBatchContext() {
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const helper=source.slice(source.indexOf('  function parameters('),source.indexOf('  function renderSelection('));
  const create=source.slice(source.indexOf('  async function createBatch('),source.indexOf('  function renderDetailShell('));
  const calls=[],errors=[],navigation=[];
  const state={epoch:1,nav:{view:'create'},selection:null,creating:false,draft:{name:'本批测试',operation_key:'plan_check',
    query:{filters:{promotion:['none']}},limit:'5',max_concurrency:'3',parameters:{countries:['JP'],auto_refresh_at_enabled:false}}};
  const ctx=context();
  Object.assign(ctx,{state,calls,errors,navigation,
    $b:()=>({reportValidity:()=>true}),operation:()=>({key:'plan_check',version:1,parameter_schema:{timezone_offset_min:{type:'integer'}}}),
    configRevision:()=> 'fixture-v1',
    saveSelection:()=>{},saveDraft:()=>{},renderSelection:()=>{},clearError:()=>{},showToast:()=>{},notice:()=>{},
    report:error=>errors.push(error),navigate:(view,extra)=>{state.nav={view,...extra};navigation.push(state.nav);},
    intent:async(scope,path,body)=>{calls.push({method:'POST',scope,path,body:plain(body)});
      return path==='/selections'?{id:'9007199254740993',state:'preparing'}:{id:'9007199254740997'};},
    request:async path=>{calls.push({method:'GET',path});return {id:'9007199254740993',state:'ready',target_count:5,selection_revision:2};}});
  vm.runInContext(helper+'\n'+create,ctx);return ctx;
}
test('直接创建会自动固定账号范围并等待就绪，无需先预览账号',async()=>{
  const ctx=createBatchContext();
  await ctx.createBatch();
  assert.equal(ctx.errors.length,0);
  assert.deepEqual(ctx.calls.map(call=>[call.method,call.path]),[
    ['POST','/selections'],['GET','/selections/9007199254740993?page_size=1'],['POST','/batches']]);
  assert.equal(ctx.calls[0].body.source.query.limit,5);
  assert.deepEqual(ctx.calls[0].body.source.query.filters.promotion,['none']);
  const body=ctx.calls[2].body;
  assert.equal(body.selection_id,'9007199254740993');assert.equal(body.selection_revision,2);
  assert.deepEqual(body.parameters,{timezone_offset_min:new Date().getTimezoneOffset()});
  assert.equal(body.expected_config_revision,'fixture-v1');
  assert.deepEqual(body.execution,{max_concurrency:3,start_paused:false});
  assert.deepEqual(ctx.navigation,[{view:'detail',batch_id:'9007199254740997'}]);
  assert.equal(ctx.state.creating,false);
});
test('旧名单含隐藏操作参数时重新固定范围，纯时区名单仍可恢复',async()=>{
  for(const overrides of [{request_parameters:{countries:['US']}},{request_parameters:{},parameters:{auto_refresh_at_enabled:false}}]){
    const ctx=createBatchContext();
    ctx.state.selection={id:'old-selection',state:'ready',target_count:5,selection_revision:1,...overrides};
    await ctx.createBatch();
    assert.equal(ctx.errors.length,0);
    assert.equal(ctx.calls[0].path,'/selections');
    assert.deepEqual(ctx.calls[0].body.parameters,{timezone_offset_min:new Date().getTimezoneOffset()});
    assert.notEqual(ctx.calls.at(-1).body.selection_id,'old-selection');
  }
  const ctx=createBatchContext();
  ctx.state.selection={id:'preserved-selection',state:'ready',target_count:5,selection_revision:1,
    request_parameters:{timezone_offset_min:0}};
  await ctx.createBatch();
  assert.equal(ctx.calls.length,1);
  assert.equal(ctx.calls[0].body.selection_id,'preserved-selection');
  assert.deepEqual(ctx.calls[0].body.parameters,{timezone_offset_min:0});
});
test('创建并暂停使用同一创建链路并将暂停意图随批次原子提交',async()=>{
  const ctx=createBatchContext();await ctx.createBatch(true);
  assert.equal(ctx.errors.length,0);
  assert.deepEqual(ctx.calls.at(-1).body.execution,{max_concurrency:3,start_paused:true});
  assert.equal(ctx.state.selection,null);
});
test('固定范围为空时不创建批次并报告分类错误',async()=>{
  const ctx=createBatchContext();
  ctx.request=async path=>{ctx.calls.push({method:'GET',path});return {id:'71',state:'ready',target_count:0,selection_revision:1};};
  await ctx.createBatch();
  assert.equal(ctx.calls.some(call=>call.path==='/batches'),false);
  assert.equal(ctx.errors[0].code,'selection_empty');assert.equal(ctx.navigation.length,0);
  assert.equal(ctx.state.creating,false);
});
test('账号范围准备期间重复点击不会创建第二份范围或批次',async()=>{
  const ctx=createBatchContext();let finishSelection;
  const original=ctx.intent;
  ctx.intent=(scope,path,body)=>path==='/selections'?new Promise(resolve=>{finishSelection=()=>resolve({id:'71',state:'ready',target_count:5,selection_revision:1});ctx.calls.push({method:'POST',path,body:plain(body)});}):original(scope,path,body);
  const first=ctx.createBatch();await ctx.createBatch(true);finishSelection();await first;
  assert.equal(ctx.errors.length,0);
  assert.equal(ctx.calls.filter(call=>call.path==='/selections').length,1);
  assert.equal(ctx.calls.filter(call=>call.path==='/batches').length,1);
  assert.equal(ctx.calls.at(-1).body.execution.start_paused,false);
});
test('创建响应晚于页面切换时保留新草稿和范围，不导航回旧批次',async()=>{
  const ctx=createBatchContext();let finishBatch;
  ctx.state.selection={id:'old-selection',state:'ready',target_count:5,selection_revision:1,config_revision:'fixture-v1'};
  const notices=[];ctx.showToast=message=>notices.push(message);
  ctx.intent=(scope,path,body)=>new Promise(resolve=>{ctx.calls.push({scope,path,body:plain(body)});finishBatch=resolve;});
  const pending=ctx.createBatch();
  const newDraft={name:'刚建立的新草稿',operation_key:'token_refresh',query:{},parameters:{refresh_driver:'roxy'},max_concurrency:2};
  const newSelection={id:'new-selection',state:'ready',target_count:2};
  ctx.state.epoch++;
  ctx.state.draft=newDraft;ctx.state.selection=newSelection;ctx.state.nav={view:'create'};
  finishBatch({id:'old-batch'});await pending;
  assert.equal(ctx.errors.length,0);
  assert.equal(ctx.state.draft,newDraft);assert.equal(ctx.state.selection,newSelection);
  assert.deepEqual(ctx.state.nav,{view:'create'});assert.equal(ctx.navigation.length,0);
  assert.equal(ctx.state.creating,false);
  assert.equal(notices.length,1);assert.ok(notices[0].includes('old-batch'));
});
test('查看历史轮次时暂停和继续仍控制整个批次，取消保留当前轮范围',async()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const helper=source.slice(source.indexOf('  async function control('),source.indexOf('  function fromAccounts('));
  const calls=[];let confirms=0;
  const ctx={state:{nav:{batch_id:'71',round_id:'19'},detail:{control:{revision:7},summary:{queued:3}}},
    $b:()=>({disabled:false}),resultCounts:value=>value,clearError:()=>{},notice:()=>{},schedule:()=>{},report:error=>{throw error;},
    confirmAction:async()=>{confirms++;return true;},intent:async(scope,path,body)=>calls.push({scope,path,body:plain(body)}),
    loadDetail:async()=>{ctx.state.detail.control.revision++;}};
  vm.createContext(ctx);vm.runInContext(helper,ctx);
  await ctx.control('pause');await ctx.control('resume');
  assert.equal(confirms,0);
  assert.deepEqual(calls.map(call=>call.body.scope),[{kind:'batch'},{kind:'batch'}]);
  assert.deepEqual(calls.map(call=>call.body.expected_control_revision),[7,8]);
  await ctx.control('cancel_not_started');
  assert.equal(confirms,1);assert.deepEqual(calls[2].body.scope,{kind:'round',round_id:'19'});
});
test('动态选项保留正在操作的节点，收起后补入新来源并保留旧选择',()=>{
  const ctx=queryFilterContext();ctx.attrEsc=value=>String(value);ctx.esc=value=>String(value);
  const selected={dataset:{queryFilter:'source'},type:'checkbox',checked:true,value:'outlook'};
  const archived={dataset:{query:'archived'},value:'only'};
  const panel={innerHTML:'original-checkbox-node',querySelectorAll:()=>[selected],querySelector:()=>null,
    insertAdjacentHTML:(_position,html)=>{panel.innerHTML+=html;}};const chipHost={innerHTML:''};
  const details={dataset:{filterField:'source'},open:true,classList:{toggle:()=>{}},contains:()=>false,
    querySelector:selector=>selector==='.bulk-filter-options'?panel:{textContent:'',hidden:true}};
  const host={querySelectorAll:selector=>selector==='[data-query]'?[archived]:selector==='[data-query-filter]'?[selected]:selector==='[data-filter-field]'?[details]:[],
    querySelector:selector=>selector==='[data-filter-field="source"]'?details:selector==='[data-query-chips]'?chipHost:null};
  const schema={fields:[{key:'source',options:[{value:'icloud_hide',label:'iCloud Hide'}]}]};
  ctx.AccountFilters.updateOptions(host,schema);
  assert.ok(panel.innerHTML.startsWith('original-checkbox-node'));
  assert.ok(panel.innerHTML.includes('value="icloud_hide"'));
  details.open=false;ctx.AccountFilters.updateOptions(host,schema);
  assert.ok(panel.innerHTML.includes('value="icloud_hide"'));
  assert.ok(panel.innerHTML.includes('value="outlook" checked'));
  assert.equal(selected.checked,true);
});
test('清空条件和退出固定名单后重新加载对应范围的可选项',async()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const action=source.slice(source.indexOf('  async function action('),source.indexOf("  document.getElementById('tab-bulk')?.addEventListener('click'"));
  const ctx=context();let scheduled=0;
  Object.assign(ctx,{state:{draft:{query:{archived:'only'},source:{kind:'ids',ids:['1']},limit:2}},
    invalidateSelection:()=>{},saveDraft:()=>{},renderCreate:()=>{},scheduleFacets:()=>{scheduled++;}});
  vm.runInContext(action,ctx);
  for(const choice of ['clear-filters','use-query']){
    await ctx.action(choice);assert.equal(ctx.state.draft.query.archived,'0');assert.equal(ctx.state.draft.source,null);
  }
  assert.equal(scheduled,2);
});
test('列表日期与结果错误分类面板均有明确关闭入口',()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const helper=source.slice(source.indexOf('  function popoverHeader('),source.indexOf('  function renderListShell('));
  const list=source.slice(source.indexOf('  function renderListShell('),source.indexOf('  async function loadList('));
  const detail=source.slice(source.indexOf('  function renderDetailShell('),source.indexOf('  function detailParams('));
  const host={innerHTML:''};const ctx={state:{nav:{}},host,$b:()=>host,operationNames:{},labels:{},terminal:[],
    optionsMarkup:()=>'',text:String,attrEsc:String,label:String};vm.createContext(ctx);vm.runInContext(helper+list+detail,ctx);
  ctx.renderListShell();assert.ok(host.innerHTML.includes('aria-label="关闭创建日期筛选"'));
  ctx.renderDetailShell();assert.ok(host.innerHTML.includes('aria-label="关闭错误分类筛选"'));
});

test('新建批次铺满布局、固定摘要和危险操作二次确认',()=>{
  const page=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const css=fs.readFileSync(path.join(root,'webui/static/css/pages/bulk.css'),'utf8');
  for(const marker of ['bulk-create-side','bulk-side-actions','data-bulk-submit','confirmAction','取消排队账号','停止正在执行','已选 ${count} 个（可跨页）'])assert.ok(page.includes(marker),marker);
  for(const marker of ['grid-template-columns: minmax(0, 1fr) 320px','position: fixed','grid-template-columns: repeat(2, minmax(0, 1fr))'])assert.ok(css.includes(marker),marker);
});
test('状态字典不再出现同名展示',()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const line=source.slice(source.indexOf('  const labels ='),source.indexOf('  const terminal =')).split('\n')[0];
  const values=[...line.matchAll(/:'([^']+)'/g)].map(match=>match[1]);
  assert.equal(new Set(values).size,values.length);
});


test('历史回执异常统一计入失败，旧深链也进入失败筛选',()=>{
  const ctx=renderingContext();
  assert.deepEqual(plain(ctx.resultCounts({success:3,failed:2,attention_required:4,request_unknown:1,unconfirmed:2})),{success:3,failed:9});
  const page=context();
  page.BulkTasks.restoreNavigation({view:'detail',batch_id:'71',result_state:'attention_required'});
  assert.equal(page.BulkTasks.navigationState().result_state,'failed');
  for(const result of [{confirmation:'unconfirmed'},{credential_confirmation:'failed'},{refresh_outcome:'unconfirmed'},{query_outcome:'unconfirmed'}]){
    assert.doesNotMatch(ctx.resultText(result),/待确认|未确认|待核验|结果未知/);
    assert.match(ctx.resultText(result),/失败/);
  }
});

test('失败账号明细优先展示中文错误原因和分类码，诊断文案转义',()=>{
  const source=fs.readFileSync(path.join(root,'webui/static/js/pages/bulk/page.js'),'utf8');
  const helpers=source.slice(source.indexOf('  function targetId('),source.indexOf('  function updateSelected('));
  const badge=source.slice(source.indexOf('  function badge('),source.indexOf('  function badge(')+source.slice(source.indexOf('  function badge(')).indexOf('\n'));
  const ctx=renderingContext();const host=ctx.host;
  ctx.state={targets:{items:[{id:'4',account_id:'2413',state:'attention_required',task_id:'19',result:{result:{refresh_outcome:'unconfirmed'},reason:{code:'password_verify_http_error',display_code:'OA-PWD-409',summary:'密码验证返回 HTTP 409（invalid_state）<诊断>'}}}]},selected:new Set(),targetPrev:[]};
  ctx.document={activeElement:null};ctx.window={getSelection:()=>null};
  ctx.$b=selector=>selector==='[data-bulk-targets]'?host:selector==='[data-bulk-select-page]'?null:{};
  ctx.attrEsc=ctx.text;ctx.short=value=>value;ctx.updateSelected=()=>{};
  vm.runInContext(`${badge}\n${helpers}`,ctx);ctx.renderTargets();
  assert.match(host.innerHTML,/密码验证返回 HTTP 409（invalid_state）&lt;诊断&gt;/);
  assert.match(host.innerHTML,/OA-PWD-409/);
  assert.doesNotMatch(host.innerHTML,/待确认|未确认|<诊断>/);
});


test('设置和授权仍在排队或执行时显示等待结果，保留已有凭据事实',()=>{
  const ctx=renderingContext();
  assert.equal(ctx.resultText({confirmation:'pending'}),'等待本轮设置结果');
  assert.equal(ctx.resultText({credential_confirmation:'pending',existing_asset_preserved:true}),'等待本轮授权结果');
  assert.equal(ctx.resultText({credential_confirmation:'failed',existing_asset_preserved:true}),'本轮授权失败 · 已有可用凭证保留');
});
