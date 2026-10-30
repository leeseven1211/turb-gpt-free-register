const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const source = require('./frontend_script_sources.cjs').readAccountScripts();
function helpers(api) {
  const context = {api};
  vm.createContext(context);
  const start = source.indexOf('function applyAccountStatusSnapshot(');
  const end = source.indexOf('async function pollAccountPlanStatuses(', start);
  vm.runInContext(source.slice(start, end) + '\nglobalThis.apply = applyAccountStatusSnapshot; globalThis.detail = loadAccountPlanDetails;', context);
  return context;
}
test('轻量状态清空旧错误与国家结果，相同详情版本保留按需加载的完整明细', () => {
  const {apply} = helpers();
  const account = {plan_check_error: '旧错误', plan_check_country_results: [{country:'US'}], account_promotions:[{summary:'旧详情'}]};
  const snapshot = {id: 1, plan_details_revision:'v1', plan_summary:{promotions:[], countries:[]}};
  apply(account, snapshot, ['plan_check_error']);
  assert.equal(account.plan_check_error, undefined);
  assert.equal(JSON.stringify(account.plan_check_country_results), '[]');
  assert.equal(JSON.stringify(account.account_promotions), '[]');
  account.account_promotions = [{summary:'完整详情'}];
  account._planDetailsPending = false;
  apply(account, snapshot, ['plan_check_error']);
  assert.equal(account.account_promotions[0].summary, '完整详情');
});
test('详情请求合并且旧响应后自动补拉最新revision，当前打开动作得到完整明细', async () => {
  let resolve;
  let calls = 0;
  const {detail, apply} = helpers(() => {
    calls += 1;
    return calls === 1 ? new Promise(done => {resolve=done;}) : Promise.resolve({item:{account_promotions:[{summary:'最新详情'}]}});
  });
  const account = {id: 1, plan_details_revision: 'v1', _planDetailsPending:true};
  const first = detail(account);
  const second = detail(account);
  apply(account, {plan_details_revision:'v2', plan_summary:{promotions:[], countries:[]}}, []);
  const openedAfterPoll = detail(account);
  resolve({item: {account_promotions: [{summary:'过期详情'}]}});
  await Promise.all([first, second, openedAfterPoll]);
  assert.equal(calls, 2);
  assert.equal(account.account_promotions[0].summary, '最新详情');
  assert.equal(account._planDetailsPending, false);
});


test('统一任务轮询复用筛选选项和批次数，相同revision不重绘，换筛选立即刷新导航', async () => {
  let selectedStatus = '';
  let renders = 0;
  let facets = 0;
  const requests = [];
  const context = vm.createContext({URLSearchParams, Date,
    accountTasksLoading:false, accountTasksReloadQueued:false, accountTaskForceMetadataQueued:false,
    accountTaskMetadataAt:0, accountTaskMetadataQuery:'', accountTaskListSignature:'', accountTaskRecentBatchCount:0,
    ACCOUNT_TASKS:[], ACCOUNT_TASKS_TOTAL:0, PAGERS:{accountTasks:{page:1,size:20}},
    $: selector => selector === '#accountTaskStatusFilterV2' ? {value:selectedStatus} : null,
    setListBusy() {}, updateAccountTaskFilters() {facets += 1;},
    renderAccountTasks() {renders += 1;}, markViewReady() {}, showToast(message) {throw Error(message);},
    api: async url => {
      requests.push(url);
      return url.includes('include_facets=1') ? {items:[{id:1}], total:1, revision:'unchanged', facets:{status:[]}, batches:[{id:1}]} : {items:[{id:1}], total:1, revision:'unchanged'};
    },
  });
  const start = source.indexOf('async function loadAccountTasks(');
  vm.runInContext(source.slice(start, source.indexOf('\nlet activeAccountTaskId',start)), context);
  await context.loadAccountTasks();
  await context.loadAccountTasks();
  assert.equal(facets, 1);
  assert.equal(renders, 1);
  assert.match(requests[1], /include_facets=0/);
  assert.match(requests[1], /include_batches=0/);
  selectedStatus = 'failed';
  await context.loadAccountTasks();
  assert.equal(facets, 2);
  assert.equal(renders, 2);
});


test('手动任务刷新绕过metadata缓存，加载中点击保留强制刷新意图', async () => {
  let release;
  const requests = [];
  const context = vm.createContext({URLSearchParams, Date,
    accountTasksLoading:false, accountTasksReloadQueued:false, accountTaskForceMetadataQueued:false,
    accountTaskMetadataAt:Date.now(), accountTaskMetadataQuery:'page=1&page_size=20&task_id=&type=&target=&status=&target_status=&batch=&run_count=&stage=&created_from=&created_to=&result=', accountTaskListSignature:'', accountTaskRecentBatchCount:0,
    ACCOUNT_TASKS:[], ACCOUNT_TASKS_TOTAL:0, PAGERS:{accountTasks:{page:1,size:20}},
    $: () => null, setListBusy() {}, updateAccountTaskFilters() {}, renderAccountTasks() {}, markViewReady() {}, showToast(message) {throw Error(message);},
    api: url => {requests.push(url); return requests.length === 1 ? new Promise(done => {release=done;}) : Promise.resolve({items:[],total:0,revision:'same',facets:{},batches:[]});},
  });
  const start = source.indexOf('async function loadAccountTasks(');
  vm.runInContext(source.slice(start, source.indexOf('\nlet activeAccountTaskId',start)), context);
  const polling = context.loadAccountTasks();
  assert.match(requests[0], /include_facets=0/);
  await context.loadAccountTasks({forceMetadata:true});
  release({items:[],total:0,revision:'same'});
  await polling;
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 2);
  assert.match(requests[1], /include_facets=1/);
  assert.match(requests[1], /include_batches=1/);
  await context.loadAccountTasks({forceMetadata:true});
  assert.match(requests[2], /include_facets=1/);
});


test('按国家聚合历史优惠在轻量轮询后保持完整列表的国家徽标与摘要', () => {
  const context = helpers();
  context.esc = value => String(value ?? '');
  const start = source.indexOf('function _plusPromotionKind(');
  vm.runInContext(source.slice(start, source.indexOf('function _planAction(', start)), context);
  const account = {id:1, plan_check_status:'failed', plan_check_countries:['US'],
    account_promotions:[{plan:'plus',kind:'free_trial',country:'US',stale:true}]};
  const before = context._promotionCell(account);
  context.apply(account, {plan_details_revision:'v2', plan_summary:{
    promotions:[{kind:'free_trial',country:'US',stale:true}], countries:[],
  }}, []);
  assert.equal(context._promotionCell(account), before);
  assert.match(before, /account-promotion-stale/);
});

test('任务页刷新按钮显式请求立即更新筛选与批次导航', async () => {
  let click;
  let options;
  const context = vm.createContext({
    $: () => ({addEventListener: (event, handler) => {assert.equal(event, 'click'); click = handler;}}),
    loadAccountTasks: async value => {options = value;},
  });
  vm.runInContext(source.split('\n').find(line => line.includes("$('#btnRefreshAccountTasks')")), context);
  await click({type:'click'});
  assert.equal(options.forceMetadata, true);
});
