const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {installLegacyActionsFixture,vueHarness:vue} = require('./actions_fixture.cjs');
const {createReadFixture,row,list,status,statusRow,presentation}=require('./read_owner_fixture.cjs');

const source = require('../frontend_script_sources.cjs').readAccountScripts();
function load(names, dependencies = {}) {
  const context = vm.createContext({...dependencies});
  require('../frontend_script_sources.cjs').installAccountActionHelpers(context);
  for (const name of names) {
    const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
    assert.ok(match, `应提供 ${name}`);
    const end = source.indexOf('\n}', match.index) + 2;
    vm.runInContext(source.slice(match.index, end), context);
  }
  return context;
}
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

test('邮箱失效徽标独立显示且不会把正常OpenAI账号识别为封号', () => {
  const context = load(['accountIsDeactivated', '_accountEmailInvalidBadge'], {esc: escape});
  const row = {id: 7, email_invalid: true, account_status: 'active', email_invalid_reason: '<邮箱失效>'};
  assert.equal(context.accountIsDeactivated(row), false);
  assert.match(context._accountEmailInvalidBadge(row), />邮箱失效<\/span>/);
  assert.match(context._accountEmailInvalidBadge(row), /&lt;邮箱失效&gt;/);
  assert.equal(context._accountEmailInvalidBadge({...row, email_invalid: false}), '');
});

test('独立邮箱状态筛选进入列表和轮询共用查询参数', async t => {
  const h=createReadFixture(t);await h.ready;
  for(const value of ['invalid','unmarked']){
    h.owner.updateFilters({email_status:[value]});await h.settle();await h.owner.pollStatuses();
    assert.equal(h.params().get('email_status'),value);
    assert.equal(h.params(h.statusRequests.at(-1)).get('email_status'),value);
  }
});

test('更多菜单提供独立标记和解除入口且保留邮箱失效账号的原有操作', () => {
  const context = load(['accountIsDeactivated', '_accountsV2MoreMenu'], {
    esc: escape, _planAction: () => '', _extractLinkAction: () => '', _codexAction: () => '',
    accountAtRefreshUiSettings: () => ({title: '使用已保存的刷新驱动重新登录'}),
  });
  const marked = context._accountsV2MoreMenu({id: 7, email_invalid: true, account_status: 'active'});
  assert.match(marked, /data-account-email-invalid="7"[^>]*data-invalid="0"[^>]*>解除邮箱失效<\/button>/);
  assert.match(marked, /data-account-email-change="7"/);
  assert.match(marked, /刷新AT/);
  assert.doesNotMatch(marked, /data-account-restore/);
  const unmarked = context._accountsV2MoreMenu({id: 8, email_invalid: false});
  assert.match(unmarked, /data-account-email-invalid="8"[^>]*data-invalid="1"[^>]*>标记邮箱失效<\/button>/);
});

function operation(overrides = {}) {
  const calls = {requests: [], toasts: [], reloads: 0};
  const context = load(['setAccountsEmailInvalid'], {
    ACCOUNT_SELECTED: new Set([7, 8]),
    ACCOUNT_SELECTED_EMAILS: new Map([[8, 'page-two@example.test']]),
    ACCOUNTS: [{id: 7, email: 'current@example.test'}],
    prompt: () => '用户确认邮箱失效', confirm: () => true,
    api: async (url, options) => { calls.requests.push({url, options}); return {updated_count: 2, skipped: []}; },
    loadAccounts: async () => { calls.reloads += 1; },
    showToast: message => calls.toasts.push(message), updateAccountSelectionUi() {},
    ...overrides,
  });
  installLegacyActionsFixture(context);
  return {context, calls};
}

test('单号和跨页批量打标提交邮箱快照，等待时防止重复提交', async () => {
  let complete;
  const {context, calls} = operation({api: (url, options) => {
    calls.requests.push({url, options});
    return new Promise(resolve => { complete = resolve; });
  }});
  const button = {disabled: false, textContent: '标记邮箱失效'};
  const pending = context.setAccountsEmailInvalid(null, true, button);
  await Promise.resolve();
  assert.equal(button.disabled, true);
  await context.setAccountsEmailInvalid(null, true, button);
  assert.equal(calls.requests.length, 1);
  assert.equal(calls.requests[0].url, '/api/accounts/email-invalid-bulk');
  assert.equal(calls.requests[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls.requests[0].options.body), {
    account_ids: [7, 8], invalid: true, reason: '用户确认邮箱失效',
    expected_emails: {'7': 'current@example.test', '8': 'page-two@example.test'},
  });
  complete({updated_count: 2, skipped: []});
  await pending;
  assert.equal(calls.reloads, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '标记邮箱失效');
});

test('解除仅清除本地邮箱标记且请求仍携带邮箱快照', async () => {
  const confirms = [];
  const {context, calls} = operation({confirm: text => { confirms.push(text); return true; }});
  await context.setAccountsEmailInvalid([7], false);
  assert.equal(JSON.parse(calls.requests[0].options.body).invalid, false);
  assert.deepEqual(JSON.parse(calls.requests[0].options.body).expected_emails, {'7': 'current@example.test'});
  assert.match(confirms[0], /仅清除本地标记/);
  assert.doesNotMatch(calls.toasts.join(''), /邮箱已恢复/);
});

test('缺失跨页邮箱快照或取消原因输入时不提交标记', async () => {
  for (const override of [{ACCOUNT_SELECTED_EMAILS: new Map()}, {prompt: () => null}]) {
    const {context, calls} = operation(override);
    await context.setAccountsEmailInvalid(null, true);
    assert.equal(calls.requests.length, 0);
  }
});

test('行事件委托把独立邮箱标记动作传给统一提交函数', async t => {
  const h=createReadFixture(t,{mounted:true,handlers:{list:async()=>list([row(7)])},render:{...presentation,menu:()=>'<button data-account-email-invalid="7" data-invalid="0">解除邮箱失效</button>'}});await h.ready;
  await h.wrapper.get('button[aria-label="更多账号操作"]').trigger('click');await h.settle();
  const button=h.body.get('[data-account-email-invalid="7"]');await button.trigger('click');await h.settle();
  assert.equal(h.calls.length,1);assert.equal(h.calls[0][0],'account-email-invalid:0');
  assert.deepEqual([...h.calls[0][1].accountIds],['7']);assert.deepEqual({...h.calls[0][1].expectedEmails},{'7':'account-7@example.test'});assert.equal(Object.isFrozen(h.calls[0][1]),true);assert.equal(h.calls[0][2],button.element);
});

test('勾选和全选记录邮箱快照，取消选择后不残留快照', async () => {
  const {effectScope}=require('../../frontend/node_modules/vue');
  const {useAccounts}=vue.load('src/features/accounts/useAccounts.ts');
  const {createAccountQueryAdapter}=vue.load('src/features/accounts/queryAdapter.ts');
  const queryContext={window:{},URLSearchParams};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../webui/static/js/shared/account-query.js'),'utf8'),queryContext);
  const rows=[{id:7,email:'seven@example.test'},{id:8,email:'eight@example.test'}];
  const api={async list(_query,page,size){return{ok:true,compact:true,items:rows,total:2,page,page_size:size,offset:0,limit:size,revision:'fixture',facets:{},search_terms:[]};},async statuses(){return{ok:true,items:[],status_fields:[],revision:'empty'};}};
  const scope=effectScope(),owner=scope.run(()=>useAccounts(createAccountQueryAdapter(queryContext.window.AccountQuery),api));
  try{
    owner.setVisible(true);await owner.refresh();owner.toggle('7',true);
    assert.equal(owner.selectedEmails.value['7'],'seven@example.test');
    owner.toggle('7',false);assert.equal(Object.hasOwn(owner.selectedEmails.value,'7'),false);
    owner.togglePage(true);assert.equal(owner.selectedEmails.value['8'],'eight@example.test');
    assert.deepEqual(owner.getActionContext().expectedEmails,{'7':'seven@example.test','8':'eight@example.test'});
    owner.clearSelection();assert.equal(owner.selected.value.size,0);assert.deepEqual(owner.selectedEmails.value,{});assert.deepEqual(owner.getActionContext().expectedEmails,{});
  }finally{scope.stop();}
});

test('筛选变更和清筛重置邮箱状态并复用原有重载行为', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row()],{total:60})}});await h.ready;h.owner.setPage(3);await h.settle();h.requests.length=0;
  h.owner.updateFilters({email_status:['invalid']});await h.settle();
  assert.equal(h.params().get('page'),'1');assert.equal(h.params().get('email_status'),'invalid');assert.equal(h.requests.length,1);
  h.owner.resetFilters();await h.settle();assert.equal(h.params().get('email_status'),'');assert.equal(h.requests.length,2);
});

test('轻量轮询用false和null移除当前页旧邮箱失效显示且不改账号状态', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row(7,{account_status:'active',email_invalid:true,email_invalid_reason:'旧原因',email_invalid_at:'旧时间'})]),statuses:async()=>status([statusRow(7,{email_invalid:false,email_invalid_reason:null,email_invalid_at:null,email_invalid_source:null})])}});await h.ready;
  await h.owner.pollStatuses();const account=h.owner.items.value[0];
  assert.equal(account.email_invalid,false);assert.equal(account.email_invalid_reason,null);assert.equal(account.email_invalid_at,null);assert.equal(account.account_status,'active');
  assert.equal(h.requests.length,1);assert.equal(h.statusRequests.length,1);assert.equal(h.owner.polling.value,false);
});
