const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {createActionsFixture, vueHarness: vue} = require('./actions_fixture.cjs');
const {mountToolbarFixture} = require('./toolbar_fixture.cjs');
const {flushPromises} = require('../../frontend/node_modules/@vue/test-utils');
const {mountC2aFixture} = require('./c2a_fixture.cjs');

const source = require('../frontend_script_sources.cjs').readAccountScripts();
const template = fs.readFileSync(path.join(__dirname, '..', '..', 'webui/templates/index.html'), 'utf8');
const actions = [
  ['btnCheckSelectedPlansV2', '/api/accounts/check-plan-bulk'],
  ['btnExtractSelectedLinksV2', '/api/accounts/extract-link-bulk'],
  ['btnCheckSelectedDeactivationMailV2', '/api/accounts/check-deactivation-mail-bulk'],
  ['btnStopSelectedCodexV2', '/api/codex/stop-bulk'],
  ['btnUploadSelectedCodexSub2V2', '/api/accounts/codex/upload-sub2-bulk'],
];
const copies = [
  ['btnCopySelectedEmailsV2', 'email', ['first@example.test', 'second@example.test']],
  ['btnCopySelectedExtractLinksV2', 'extract_link', ['https://example.test/first', 'https://example.test/second']],
];

async function setup({request, confirmation = true, saved = null} = {}) {
  const calls = {requests: [], toasts: [], copies: [], confirmations: [], receipts: [], dialogs: [], focuses: [], tabs: [], taskCenters: []};
  const detached=new Map();
  const placeholder=id=>{if(!detached.has(id))detached.set(id,{id,value:'',classList:{contains:()=>false},addEventListener(){},querySelector:()=>null,querySelectorAll:()=>[]});return detached.get(id);};
  const context=vm.createContext({
    ACCOUNT_SELECTED:new Set(),ACCOUNTS:[],CONFIG:[],SHOW_ARCHIVED_ACCOUNTS:false,PAGERS:{accountTasks:{page:3}},
    LIST_FACET_LABELS:{task_type:{},stage:{},target_status:{}},
    document:{getElementById:placeholder,querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){}},
    $:selector=>placeholder(selector.slice(1)),window:{addEventListener(){}},browserTimeZoneName:()=> 'Asia/Shanghai',closeLiveLogModal(){},
    activateTab:tab=>calls.tabs.push(tab),openAccountTaskLog(){},openLog(){},setInterval(){},setTimeout(){},clearTimeout(){},
    esc:value=>String(value??''),showToast:message=>calls.toasts.push(message),copyText:async text=>{calls.copies.push(text);return true;},
    confirm:message=>{calls.confirmations.push(message);return confirmation;},
    api:async(url,options)=>{calls.requests.push({url,options});return request?request(url,options):{started_count:2,skipped_count:2,stopped_count:2,queued_count:2,skipped:[],started:[]};},
  });
  // Legacy facades load before Vue mounts. No legacy listener is attached to a real toolbar or list node.
  vm.runInContext(source,context);
  context.window.TaskCenter={open:async options=>{calls.taskCenters.push(JSON.parse(JSON.stringify(options)));}};
  context.loadAccounts=async()=>{};context.loadAccountTasks=async()=>{};context.pollAccountPlanStatuses=async()=>{};
  context.trackAcceptedOperationsV2=(...args)=>calls.receipts.push(args);
  let listWrapper,rows=[];
  const owner={isReady:()=>true,getActionContext:options=>listWrapper.vm.getActionContext(options),
    refresh:()=>context.loadAccounts(),pollStatuses:()=>context.pollAccountPlanStatuses(),getRowSnapshot:id=>listWrapper.vm.getRowSnapshot(id),
    clearSelection:()=>listWrapper.vm.clearSelection(),removeAcknowledgedSelection:ids=>listWrapper.vm.removeAcknowledgedSelection(ids)};
  createActionsFixture(context,owner);context.window.AccountsPage=owner;
  const toolbar=mountToolbarFixture({saved,state:{selectedCount:0,archived:false},getContext:()=>owner.getActionContext(),notify:context.showToast,
    invoke:(descriptor,snapshot,trigger)=>context.invokeAccountAction(descriptor,snapshot,trigger)});
  await toolbar.ready;
  context.document=toolbar.document;context.$=selector=>toolbar.document.querySelector(selector);
  const queryContext={window:{},URLSearchParams};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../webui/static/js/shared/account-query.js'),'utf8'),queryContext);
  const adapter=vue.load('src/features/accounts/queryAdapter.ts').createAccountQueryAdapter(queryContext.window.AccountQuery);
  const api={
    async list(_query,page,size){return{ok:true,compact:true,items:rows,total:rows.length,page,page_size:size,offset:0,limit:size,revision:'fixture',facets:{},search_terms:[]};},
    async statuses(_query,page,size){return{ok:true,items:[],total:rows.length,page,page_size:size,offset:0,limit:size,revision:'empty',status_fields:[],queue:{workers:1,registration_workers:1,queue_limit:100,min_interval:0,jitter:0}};},
    async planDetails(){return{ok:true,item:{account_promotions:null,promotion_query_snapshot:null,plan_check_country_results:[]}};},
  };
  const presentation={cell:()=>'',menu:()=>'',emailInvalidBadge:()=>'',registrationDriverLabel:String,facetLabel:(_group,value)=>value,mobileSummary:()=>'',rowTone:()=> 'ok'};
  listWrapper=vue.mount(vue.load('src/features/accounts/AccountsList.vue').default,{props:{adapter,api,presentation,callbacks:{invoke:context.invokeAccountAction,openDetail(){},
    onStateChange:state=>{context.ACCOUNT_SELECTED=new Set(state.selectedIds.map(Number));void toolbar.setState({selectedCount:state.selectedIds.length,archived:state.archived==='only'});}}}});
  owner.syncToolbarPending=()=>{};owner.refreshQuickActions=()=>toolbar.wrapper.vm.refreshQuickActions();
  listWrapper.vm.setVisible(true);await flushPromises();
  const element=id=>toolbar.document.getElementById(id);
  const selectAll=async checked=>{const checkbox=element('accountsSelectAllV2');checkbox.checked=checked;checkbox.dispatchEvent(new toolbar.document.defaultView.Event('change',{bubbles:true}));await flushPromises();};
  const changeRow=async(id,checked)=>{const checkbox=toolbar.document.querySelector(`.account-row-check[data-account-id="${id}"]`);checkbox.checked=checked;checkbox.dispatchEvent(new toolbar.document.defaultView.Event('change',{bubbles:true}));await flushPromises();};
  const setPage=async incoming=>{rows=incoming.map(row=>({has_access_token:false,has_account_password:false,totp_enabled:false,email_invalid:false,email_invalid_at:null,email_invalid_reason:null,email_invalid_source:null,plus_promo_kind:'',plus_promo_eligible:false,plus_trial_eligible:false,plus_discount_eligible:false,...row}));context.ACCOUNTS=rows;await listWrapper.vm.refresh();await flushPromises();};
  const selectTwoPages=async()=>{
    await setPage([7,8].map(id=>({id,email:`first-${id}@example.test`,account_status:'active',current_plan_type:'free',codex_status:'success',codex_execution_status:'running',email_source:'cloudflare'})));
    await selectAll(true);
    await setPage([9,10].map(id=>({id,email:`second-${id}@example.test`,account_status:'deactivated',current_plan_type:'plus',codex_status:'failed',codex_execution_status:'failed',email_source:'outlook'})));
    await selectAll(true);
  };
  return{context,owner,calls,element,selectAll,changeRow,setPage,selectTwoPages,click:id=>toolbar.click(id),flushAnimationFrames:()=>toolbar.flush(),
    clearSelection:async()=>{listWrapper.vm.clearSelection();await flushPromises();}};
}

function c2aFixture(view, testContext) {
  const ui = mountC2aFixture({request: (url, options) => view.context.api(url, options),
    notify: text => view.calls.toasts.push(text), refreshAccounts: () => view.context.loadAccounts(),
    selectionChanged: () => view.context.updateAccountSelectionUi(),
    trackAccepted: (...args) => view.calls.receipts.push(args),
    openTasks: options => view.context.window.TaskCenter.open(options)}, {preserve:true});
  ui.bind(view.owner); testContext.after(() => ui.close()); return ui;
}

for (const [button, endpoint] of actions) {
  test(`${button}：跨页全选提交全部账号，当前页无合格项也不阻断`, async () => {
    const view = await setup();
    await view.selectTwoPages();
    assert.equal(view.element('accountsSelectedHintV2').textContent, '已选 4 个账号');
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.requests[0].url, endpoint);
    assert.equal(view.calls.requests[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(view.calls.requests[0].options.body).account_ids, [7, 8, 9, 10]);
  });
}

test('取消当前页全选仅移除当前页，单行取消后提交保留的跨页账号', async () => {
  const view = await setup();
  await view.selectTwoPages();
  await view.selectAll(false);
  assert.deepEqual([...view.context.ACCOUNT_SELECTED], [7, 8]);
  assert.equal(view.element('accountsSelectAllV2').checked, false);
  await view.setPage([{id: 7, email: 'first@example.test'}, {id: 8, email: 'second@example.test'}]);
  assert.equal(view.element('accountsSelectAllV2').checked, true);
  await view.changeRow(7, false);
  assert.deepEqual([...view.context.ACCOUNT_SELECTED], [8]);
  assert.equal(view.element('accountsSelectAllV2').indeterminate, true);
  await view.click('btnCheckSelectedPlansV2');
  assert.deepEqual(JSON.parse(view.calls.requests[0].options.body).account_ids, [8]);
});

test('未选择账号时所有修复操作均保持禁用且直接触发也不会请求', async () => {
  const view = await setup();
  view.context.updateAccountSelectionUi();
  for (const [button] of [...actions, ...copies]) {
    assert.equal(view.element(button).disabled, true);
    await view.click(button);
  }
  assert.equal(view.calls.requests.length, 0);
  assert.equal(view.calls.copies.length, 0);
  assert.ok(view.calls.toasts.every(message => /请先选择账号/.test(message)));
});

for (const [button, field, values] of copies) {
  test(`${button}：按全量跨页 ID 读取实时数据并复制返回值`, async () => {
    const view = await setup({request: async () => ({values: values.map((value, index) => ({id: index + 7, value}))})});
    await view.selectTwoPages();
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.requests[0].url, '/api/accounts/secret-bulk');
    assert.deepEqual(JSON.parse(view.calls.requests[0].options.body), {account_ids: [7, 8, 9, 10], field});
    assert.deepEqual(view.calls.copies, [values.join('\n')]);
    assert.match(view.calls.toasts.join(''), /已复制 2/);
  });

  test(`${button}：读取失败有具体反馈且不复制当前页旧数据`, async () => {
    const view = await setup({request: async () => { throw new Error('模拟数据读取失败'); }});
    await view.selectTwoPages();
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.copies.length, 0);
    assert.match(view.calls.toasts.join(''), /复制.*失败.*模拟数据读取失败/);
  });

  test(`${button}：全部账号没有可复制值时说明原因`, async () => {
    const view = await setup({request: async () => ({values: []})});
    await view.selectTwoPages();
    await view.click(button);
    assert.equal(view.calls.requests.length, 1);
    assert.equal(view.calls.copies.length, 0);
    assert.match(view.calls.toasts.join(''), /没有/);
  });
}

test('CPA 下载和 Codex 重跑确认使用跨页总数，不以当前页状态推断整批', async () => {
  const view = await setup({confirmation: false});
  await view.selectTwoPages();
  await view.click('btnDownloadSelectedCpaV2');
  await view.click('btnRetrySelectedCodexV2');
  assert.equal(view.calls.confirmations.length, 2);
  for (const message of view.calls.confirmations) {
    assert.match(message, /4 个账号/);
    assert.doesNotMatch(message, /其中.*(?:2 个账号本地 Codex|已废号 2 个)/s);
  }
  assert.equal(view.calls.requests.length, 0);
});

test('重新导入 C2A：弹窗说明更新边界，确认后追踪跨页账号的任务回执且留在账号页', async t => {
  const queued = [{accepted: true, task_id: 71, run_id: 72, status: 'queued'}];
  const skipped = [{id: 8, email: 'first-8@example.test', error_code: 'c2a_manual_queue_busy', reason: '该账号已有 C2A 重新导入任务', task_id: 88, run_id: 89}];
  const failed = [{id: 9, email: 'second-9@example.test', error_code: 'c2a_account_deactivated', error: '关联账号已确认停用，未向 C2A 更新 AT'}];
  const view = await setup({request: async () => ({accepted: true, queued_count: 1, skipped_count: 1, failed_count: 1, queued, skipped, failed})});
  const ui = c2aFixture(view, t);
  await view.selectTwoPages();

  await view.click('btnReimportSelectedC2aV2');
  await ui.flush();

  assert.equal(ui.get('c2aReimportConfirmModal').open, true);
  assert.match(ui.get('c2aReimportConfirmCountV2').textContent, /4/);
  assert.equal(view.calls.requests.length, 0);
  await view.clearSelection(); await view.setPage([{id: 99, email: 'later@example.test'}]);
  await ui.click('btnConfirmC2aReimportV2');

  assert.equal(view.calls.requests.length, 1);
  assert.equal(view.calls.requests[0].url, '/api/accounts/c2a/sync-bulk');
  assert.deepEqual(JSON.parse(view.calls.requests[0].options.body), {account_ids: [7, 8, 9, 10]});
  assert.equal(view.calls.confirmations.length, 0);
  assert.equal(view.calls.receipts.length, 1);
  assert.equal(view.calls.receipts[0][1], '重新导入 C2A');
  assert.equal(view.calls.receipts[0][2].navigate, false);
  assert.equal(view.calls.receipts[0][0].length, 2);
  assert.equal(view.calls.receipts[0][0][0].task_id, 71);
  assert.equal(view.calls.receipts[0][0][1].task_id, 88);
  assert.match(view.calls.toasts.join(''), /C2A 重新导入已入队 1 个.*未入队 2 个.*已显示具体原因/);
  assert.equal(ui.get('accountC2aReimportResultV2').hidden, false);
  assert.match(ui.get('accountC2aReimportResultV2').textContent, /C2A 重新导入：已入队 1 个，未入队 2 个/);
  assert.match(ui.get('accountC2aReimportResultV2').textContent, /c2a_manual_queue_busy/);
  assert.match(ui.get('accountC2aReimportResultV2').textContent, /c2a_account_deactivated/);
  assert.match(ui.get('accountC2aReimportResultV2').textContent, /查看任务 #88/);
  ui.get('accountC2aReimportResultV2').querySelector('[data-c2a-reimport-tasks]').click(); await ui.flush();
  assert.deepEqual(view.calls.taskCenters, [{filters: {type: 'c2a_session_reimport'}, runId: null}]);
});

test('重新导入 C2A：真实组件保留全部警告，页面引用带版本的最新脚本资源', async t => {
  const view = await setup(), ui = c2aFixture(view, t);
  await view.selectTwoPages(); await view.click('btnReimportSelectedC2aV2'); await ui.flush();
  for (const id of ['c2aReimportConfirmModal','c2aReimportConfirmCountV2','btnCancelC2aReimportV2','btnConfirmC2aReimportV2']) assert.ok(ui.get(id));
  const warning = ui.get('c2aReimportConfirmModal').textContent;
  assert.match(warning, /只把本地当前 AT 更新到同邮箱唯一匹配的既有 C2A 账号/);
  assert.match(warning, /自动移除异常账号.*自动移除限流账号/);
  assert.match(warning, /不会刷新本地 AT/);
  assert.match(warning, /异常.*恢复正常/);
  assert.match(template, /id="accountC2aConfirmHost"/);
  assert.match(template, /id="accountC2aReceiptHost"/);
  assert.match(template, /filename='js\/pages\/accounts\/page\.js', v=task_center_version/);
});

test('重新导入 C2A：取消后下一帧焦点回到顶部批量按钮', async t => {
  const view = await setup({saved:JSON.stringify({btnReimportSelectedC2aV2:1})}), ui = c2aFixture(view, t);
  await view.selectTwoPages();

  await view.click('btnReimportSelectedC2aV2');
  await ui.flush();
  assert.equal(ui.get('c2aReimportConfirmModal').open, true);
  await ui.click('btnCancelC2aReimportV2');
  ui.get('accountsMoreActionsV2').open = false;
  await ui.frame();

  assert.equal(ui.get('c2aReimportConfirmModal').open, false);
  assert.equal(view.calls.requests.length, 0);
  assert.deepEqual(view.calls.receipts, []);
  assert.equal(ui.document.activeElement.id, 'btnReimportSelectedC2aV2');
  assert.equal(ui.get('accountsMoreActionsV2').open, false);
});

test('重新导入 C2A：原生关闭事件同样恢复可见焦点且不发起同步', async t => {
  const view = await setup({saved:JSON.stringify({btnReimportSelectedC2aV2:1})}), ui = c2aFixture(view, t);
  await view.selectTwoPages();
  await view.click('btnReimportSelectedC2aV2');
  await ui.flush();
  ui.get('c2aReimportConfirmModal').close('');
  ui.get('accountsMoreActionsV2').open = false;
  await ui.frame();
  assert.equal(view.calls.requests.length, 0);
  assert.equal(ui.document.activeElement.id, 'btnReimportSelectedC2aV2');
});


test('重新导入 C2A：更多菜单已关闭时回到可见摘要，工具栏排序不夺焦',async t=>{
  const view=await setup(),ui=c2aFixture(view,t);await view.selectTwoPages();
  const more=ui.get('accountsMoreActionsV2');more.open=true;
  await view.click('btnReimportSelectedC2aV2');await ui.flush();
  await ui.click('btnCancelC2aReimportV2');more.open=false;await ui.frame();await view.flushAnimationFrames();
  assert.equal(ui.document.activeElement,more.querySelector('summary'));
  assert.equal(more.contains(ui.get('btnReimportSelectedC2aV2')),true);
  assert.equal(view.calls.requests.length,0);
});
