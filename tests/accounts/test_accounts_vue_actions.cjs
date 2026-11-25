const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {createActionsFixture,vueHarness} = require('./actions_fixture.cjs');
const {mountToolbarFixture} = require('./toolbar_fixture.cjs');

// Optional artifact root lets the coordinating test run inspect the exact
// candidate before applying it. Normal repository runs use the real sources.
const root = process.env.ACCOUNTS_ACTIONS_ROOT || path.resolve(__dirname, '../..');
const page = fs.readFileSync(path.join(root, 'webui/static/js/pages/accounts/page.js'), 'utf8');
const email = fs.readFileSync(path.join(root, 'webui/static/js/pages/accounts/email-change.js'), 'utf8');
const inspection = fs.readFileSync(path.join(root, 'webui/static/js/pages/accounts/inspection.js'), 'utf8');
const legacyRoot = process.env.ACCOUNTS_LEGACY_ROOT || root;
const querySource = fs.readFileSync(path.join(legacyRoot, 'webui/static/js/shared/account-query.js'), 'utf8');
const helperNames = ['accountActionOwner', 'freezeAccountActionValue', 'captureAccountActionContext',
  'accountActionIds', 'accountActionRow', 'accountActionRefresh', 'accountActionPollStatuses',
  'accountActionSelectionUi', 'accountActionRemoveAcknowledged', 'accountActionClearSelection'];
const plain = value => JSON.parse(JSON.stringify(value));
function functionSource(source, name) {
  const match = new RegExp(`^(?:async )?function ${name}\\(`, 'm').exec(source);
  assert.ok(match, `missing real function ${name}`);
  const lineEnd = source.indexOf('\n', match.index);
  if (source.slice(match.index, lineEnd).endsWith(' }')) return source.slice(match.index, lineEnd);
  return source.slice(match.index, source.indexOf('\n}', match.index) + 2);
}
function loadFunctions(context, source, names) {
  for (const name of names) vm.runInContext(functionSource(source, name), context, {filename: name + '.js'});
}
function element() {
  const classes = new Set(['hidden']);
  return {disabled: false, textContent: 'original', dataset: {}, value: '', hidden: false, isConnected: true,
    classList: {add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x), toggle(x, enabled) { enabled ? classes.add(x) : classes.delete(x); }},
    setAttribute() {}, focus() {}, setCustomValidity() {}, checkValidity: () => true,
    reportValidity() {}, appendChild() {}, addEventListener() {}, querySelector: () => null,
    querySelectorAll: () => [], showModal() { this.open = true; }, close() { this.open = false; }};
}
function fixture(names, extra = {}) {
  const calls = {requests: [], refresh: 0, polls: 0, removed: [], clear: 0, toasts: [], task: [], confirms: []};
  const controls = new Map();
  const get = id => { if (!controls.has(id)) controls.set(id, element()); return controls.get(id); };
  const selected = new Set([999]);
  for (const method of ['add', 'delete', 'clear']) selected[method] = () => { throw new Error('must not mutate legacy selection'); };
  const oldRows = new Proxy([], {get() { throw new Error('must not read legacy ACCOUNTS on explicit path'); }});
  const contextData = {accountIds: ['7', '8'], expectedEmails: {'7': 'seven@example.test', '8': 'eight@example.test'},
    querySnapshot: {schema_version: 1, entity: 'account', q: '备注:"a/b 待整理"', archived: '0', filters: {email: ''}},
    archived: '0', rowHints: [{id: 7, email: 'seven@example.test', email_source: 'icloud_hide'}, {id: 8, email: 'eight@example.test'}]};
  const owner = {isReady: () => true, getActionContext: () => contextData,
    refresh: async () => { calls.refresh++; }, pollStatuses: async () => { calls.polls++; },
    removeAcknowledgedSelection: ids => calls.removed.push(plain(ids)), clearSelection: () => { calls.clear++; },
    getRowSnapshot: id => ({id: Number(id), deactivation_mail_scan_status: 'done'})};
  const sandbox = vm.createContext({console, Promise, URLSearchParams, AbortController, Set, Map,
    window: {AccountsPage: owner, TaskCenter: {open: async value => { calls.task.push(plain(value)); }}},
    document: {getElementById: get, activeElement: get('active'), createElement: () => element()},
    $: selector => get(selector.slice(1)), ACCOUNT_SELECTED: selected, ACCOUNT_SELECTED_EMAILS: new Map([[999, 'old@example.test']]),
    ACCOUNTS: oldRows, SHOW_ARCHIVED_ACCOUNTS: false, ACCOUNT_REGISTRATION_RETRY_PENDING: new Set(),
    ACCOUNT_QUICK_ACTIONS: {pending: false}, accountSessionDownloadLoading: false,
    showToast: value => calls.toasts.push(value), updateAccountSelectionUi() {}, loadSummary() {},
    loadAccounts() { throw new Error('explicit action must refresh facade'); },
    pollAccountPlanStatuses() { throw new Error('explicit action must poll facade'); },
    confirm: text => { calls.confirms.push(text); return true; }, prompt: () => 'verified missing mailbox',
    api: async (url, options) => { calls.requests.push({url, options}); return {ok: true, started_count: 2, updated: [], deleted: []}; },
    getAccountOperationWorkers: () => 3, configuredLiveCheckDriver: () => 'protocol',
    setTimeout: callback => { callback(); return 1; }, clearTimeout() {},
    accountBulkQueueReasons: () => '', loadAccountTasks() {}, openLiveLog() {},
    updateModalScrollLock() {}, refreshAccountQuickActions() {},
    ...extra,
  });
  createActionsFixture(sandbox, owner);
  loadFunctions(sandbox, page, helperNames); loadFunctions(sandbox, page, names);
  return {context: sandbox, contextData, owner, calls, get, controls};
}

test('邮箱失效确认使用冻结 IDs/email 映射，确认时清选、翻页和换绑不能改变 POST', async () => {
  const h = fixture(['setAccountsEmailInvalid']);
  h.context.api = async (url, options) => {h.calls.requests.push({url, options}); return {ok: true, updated_count: 2, skipped: []};};
  h.context.prompt = () => {
    h.contextData.accountIds.splice(0, 2, '99'); h.contextData.expectedEmails['7'] = 'rebound@example.test';
    h.contextData.rowHints.length = 0; return 'user reason';
  };
  await h.context.setAccountsEmailInvalid(null, true, h.get('trigger'), h.contextData);
  assert.equal(h.calls.requests.length, 1);
  assert.equal(h.calls.requests[0].url, '/api/accounts/email-invalid-bulk');
  assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {account_ids: [7, 8], invalid: true, reason: 'user reason',
    expected_emails: {'7': 'seven@example.test', '8': 'eight@example.test'}});
  assert.equal(h.calls.refresh, 1); assert.equal(h.context.ACCOUNT_SELECTED.has(999), true);
});

test('显式邮箱映射缺失不补读旧行，不确认也不 POST；500 上限在确认前保留', async () => {
  for (const missing of [undefined, '', null]) {
    const h = fixture(['setAccountsEmailInvalid']); h.contextData.expectedEmails['8'] = missing;
    let prompts = 0; h.context.prompt = () => { prompts++; return 'reason'; };
    await h.context.setAccountsEmailInvalid(null, true, null, h.contextData);
    assert.equal(h.calls.requests.length, 0); assert.equal(prompts, 0);
    assert.match(h.calls.toasts.join(''), /缺少邮箱快照/);
  }
  const h = fixture(['setAccountsEmailInvalid']); h.contextData.accountIds = Array.from({length: 501}, (_, index) => String(index + 1));
  await h.context.setAccountsEmailInvalid(null, false, null, h.contextData);
  assert.equal(h.calls.requests.length, 0); assert.equal(h.calls.confirms.length, 0);
  assert.match(h.calls.toasts.join(''), /500/);
});

test('兼容无参 toolbar 在确认前只从 facade 获取一次快照，POST 保持原协议', async () => {
  const h = fixture(['archiveSelectedAccounts']); let snapshots = 0;
  h.owner.getActionContext = () => { snapshots++; return h.contextData; };
  h.context.confirm = () => { h.contextData.accountIds = ['99']; h.contextData.archived = 'only'; return true; };
  h.context.api = async (url, options) => { h.calls.requests.push({url, options}); return {updated: [{id: 7}], skipped: [{id: 8}], updated_count: 1}; };
  await h.context.archiveSelectedAccounts();
  assert.equal(snapshots, 1); assert.equal(h.calls.requests[0].url, '/api/accounts/archive-bulk');
  assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {account_ids: [7, 8], archived: true});
  assert.deepEqual(h.calls.removed, [['7']]); assert.equal(h.calls.clear, 0);
});

for (const [name, key, endpoint] of [['archiveSelectedAccounts', 'updated', 'archive-bulk'], ['deleteSelectedAccounts', 'deleted', 'delete-bulk']]) {
  test(`${name} 仅移除返回的已确认且属于提交目标 ID，count/跳过/未知不清选`, async () => {
    const h = fixture([name]);
    h.context.api = async (url, options) => { h.calls.requests.push({url, options}); return {[key]: [{id: 7}, {id: 999}], [`${key}_count`]: 100, skipped: [{id: 8}]}; };
    await h.context[name](h.contextData);
    assert.equal(h.calls.requests[0].url, `/api/accounts/${endpoint}`);
    assert.deepEqual(h.calls.removed, [['7']]); assert.equal(h.calls.clear, 0);
    assert.equal(h.context.ACCOUNT_SELECTED.has(999), true);
  });
}

test('单项归档和删除仅在明确成功回执后移除对应选择', async () => {
  for (const [name, success] of [['archiveOneAccount', {updated: true, id: 7}], ['deleteAccount', {deleted: true}]]) {
    for (const response of [{ok: true}, success]) {
      const h = fixture([name]); h.context.api = async () => response;
      const args = name === 'archiveOneAccount' ? [7, true, h.get('trigger'), h.contextData] : [7, 'seven@example.test', h.get('trigger'), h.contextData];
      await h.context[name](...args);
      assert.deepEqual(h.calls.removed, response === success ? [['7']] : []);
    }
  }
});

for (const [name, endpoint, expected] of [
  ['checkSelectedPlans', '/api/accounts/check-plan-bulk', {account_ids: [7, 8]}],
  ['extractSelectedLinks', '/api/accounts/extract-link-bulk', {account_ids: [7, 8]}],
  ['uploadSelectedCodexSub2', '/api/accounts/codex/upload-sub2-bulk', {account_ids: [7, 8]}],
  ['setupSelectedAccounts', '/api/accounts/setup-bulk', {account_ids: [7, 8]}],
  ['stopSelectedCodex', '/api/codex/stop-bulk', {account_ids: [7, 8]}],
  ['retrySelectedCodex', '/api/codex/retry-bulk', {account_ids: [7, 8]}],
]) {
  test(`${name} 使用显式跨页目标且不修改已有 body`, async () => {
    const h = fixture([name]); await h.context[name](h.contextData);
    assert.equal(h.calls.requests[0].url, endpoint); assert.equal(h.calls.requests[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), expected);
  });
}

test('AT 配置异步读取期间变更 owner 选择不会改变已冻结的刷新目标', async () => {
  let resolve; const h = fixture(['refreshSelectedToken'], {apiCached: () => new Promise(done => { resolve = done; })});
  const request = h.context.refreshSelectedToken(null, h.get('trigger'), h.contextData);
  h.contextData.accountIds = ['99']; resolve([]); await request;
  assert.equal(h.calls.requests[0].url, '/api/accounts/refresh-token-bulk');
  assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {account_ids: [7, 8]});
});

test('C2A 确认窗口保存原目标，提交只通知任务中心且不创建回执或跳转', async () => {
  const {vueHarness} = require('./actions_fixture.cjs');
  const {effectScope} = require('../../frontend/node_modules/vue'); const scope = effectScope();
  try {
    const h = fixture(['openC2aReimportConfirm', 'reimportSelectedC2a', 'submitC2aReimport']);
    const {useC2aReimport} = vueHarness.load('src/features/accounts/useC2aReimport.ts');
    const owner = scope.run(() => useC2aReimport({
      request: async (url, options) => {h.calls.requests.push({url, options}); return {accepted: true, queued_count: 1, queued: [{task_id: 4, run_id: 6}]};},
      notify: value => h.calls.toasts.push(value), refreshAccounts: () => h.owner.refresh(),
      openTasks: value => h.calls.task.push(plain(value)),
    }));
    h.owner.openC2a = (context, trigger) => owner.open(context, trigger);
    h.owner.submitC2a = () => owner.submit();
    h.context.reimportSelectedC2a(null, h.contextData); h.contextData.accountIds = ['99'];
    await h.context.submitC2aReimport();
    assert.equal(h.calls.requests[0].url, '/api/accounts/c2a/sync-bulk');
    assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {account_ids: [7, 8]});
    assert.deepEqual(h.calls.task,[]);
    assert.match(h.calls.toasts.join(''),/C2A 重新导入已入队 1 个.*任务中心/);assert.doesNotMatch(h.calls.toasts.join(''),/任务回执|已显示具体原因/);
  } finally {scope.stop();}
});

test('单项 Codex 端点仍按点击时邮箱提交，动态 row-action 不改 URL 和 body', async () => {
  for (const [name, endpoint, body] of [
    ['stopOneAccountCodex', 'stop', {email: 'seven@example.test'}],
    ['resetOneAccountCodex', 'reset-retrying', {email: 'seven@example.test', status: 'failed'}],
    ['retryOneAccountCodex', 'retry', {email: 'seven@example.test'}],
  ]) {
    const h = fixture([name]);
    h.contextData.accountIds=['7'];
    h.context.confirm = () => { h.contextData.expectedEmails['7'] = 'rebound@example.test'; return true; };
    await h.context[name]('seven@example.test', h.get('trigger'), h.contextData);
    assert.equal(h.calls.requests[0].url, `/api/codex/${endpoint}`);
    assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), body);
  }
  const h = fixture(['runOneAccountAction']);
  h.contextData.accountIds=['7'];
  await h.context.runOneAccountAction(7, 'password_change', h.get('trigger'), h.contextData);
  assert.equal(h.calls.requests[0].url, '/api/accounts/7/action');
  assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {action: 'password_change'});
  assert.equal(h.calls.task[0].filters.target, 'seven@example.test');
});

test('导出读取独立 secret-bulk，不使用 rowHints 中的任何凭据字段', async () => {
  for (const [name, field] of [['copySelectedAccountTokens', 'access_token'], ['copySelectedAccountLines', 'account_credentials_line'],
    ['copySelectedAccountEmails', 'email'], ['copySelectedAccountPasswords', 'account_password_line'], ['copySelectedAccountTotpSecrets', 'totp_secret']]) {
    const h = fixture([name], {copyText: async () => true});
    h.contextData.rowHints[0].access_token = 'must-not-copy';
    h.context.api = async (url, options) => { h.calls.requests.push({url, options}); return {values: [{value: 'from secret API'}]}; };
    await h.context[name](h.contextData);
    assert.equal(h.calls.requests[0].url, '/api/accounts/secret-bulk');
    assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {account_ids: [7, 8], field});
  }
});

test('换邮窗口保留打开时 email/source，翻页后提交和TaskCenter仍指向原账号', async () => {
  const {createVueHarness} = require('../frontend_vue_loader.cjs'); const vue = createVueHarness();
  const {effectScope} = require('../../frontend/node_modules/vue'); const scope = effectScope();
  try {
    const h = fixture([]); const {useAccountEmailChange} = vue.load('src/features/accounts/useAccountEmailChange.ts');
    const owner = scope.run(() => useAccountEmailChange({
      request: async (url, options) => { h.calls.requests.push({url, options}); return url === '/api/email-sources'
        ? {sources: [{value: 'icloud_hide', enabled: true}, {value: 'outlook', enabled: true}]} : {ok: true, task_id: 71}; },
      notify: value => h.calls.toasts.push(value), syncModalScrollLock() {},
      refreshAccounts: value => { h.calls.refresh++; assert.equal(value.rowHints[0].email, 'seven@example.test'); },
      openTasks: filters => h.calls.task.push({filters}),
    }));
    // The legacy entry point must pass the explicit context to the real Vue owner.
    h.owner.openEmailChange = (id, context) => owner.openSingle(id, context);
    loadFunctions(h.context, email, ['openEmailChangeModal']);
    await h.context.openEmailChangeModal(7, h.get('trigger'), h.contextData);
    assert.equal(owner.source.value, 'icloud_hide'); assert.equal(owner.account.value.email, 'seven@example.test');
    owner.source.value = 'outlook';
    h.contextData.rowHints.length = 0; h.contextData.expectedEmails['7'] = 'rebound@example.test';
    await owner.submit();
    const submitted = h.calls.requests.find(call => call.options?.method === 'POST');
    assert.equal(submitted.url, '/api/accounts/7/email-change');
    assert.deepEqual(JSON.parse(submitted.options.body), {email_source: 'outlook'});
    assert.equal(h.calls.task[0].filters.target, 'seven@example.test'); assert.equal(h.calls.refresh, 1);
  } finally {scope.stop(); vue.close();}
});

test('巡检归档范围开窗即冻结；未知回执重试复用相同 idempotency_key', async () => {
  const {createVueHarness} = require('../frontend_vue_loader.cjs'); const vue = createVueHarness();
  const {effectScope} = require('../../frontend/node_modules/vue'); const scope = effectScope();
  try {
    const h = fixture([]); const {useAccountInspection} = vue.load('src/features/accounts/useAccountInspection.ts');
    const owner = scope.run(() => useAccountInspection({
      request: async (url, options) => {h.calls.requests.push({url, options}); throw new Error('response unknown');},
      notify: value => h.calls.toasts.push(value), operationWorkers: () => 3, randomUUID: () => 'same-intent-key',
      refreshAccounts() {}, refreshSummary() {}, openTask() {}, formatDateTime: String,
    }));
    h.owner.openInspectionStart = context => owner.openStart(context);
    loadFunctions(h.context, inspection, ['openAccountInspectionStart']);
    h.contextData.archived = 'only'; h.context.openAccountInspectionStart(h.contextData); h.contextData.archived = '0';
    owner.workers.value = 16; await owner.submit(); await owner.submit();
    assert.equal(h.calls.requests.length, 2);
    for (const call of h.calls.requests) assert.deepEqual(JSON.parse(call.options.body), {workers: 16, archived: 'only', idempotency_key: 'same-intent-key'});
    owner.workers.value = 17; await owner.submit(); assert.equal(h.calls.requests.length, 2);
  } finally {scope.stop(); vue.close();}
});

test('删除废号传显式 archived 并使用 clearSelection 回调，不按 count 猜 ID', async () => {
  const h = fixture([], {deletingDeactivatedAccounts: false});
  loadFunctions(h.context, inspection, ['accountInspectionScope', 'accountInspectionScopeLabel', 'deleteDeactivatedAccounts']);
  h.context.api = async (url, options) => { h.calls.requests.push({url, options}); return {ok: true, deleted_count: 4}; };
  h.contextData.archived = 'only'; await h.context.deleteDeactivatedAccounts(h.contextData);
  assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {archived: 'only'});
  assert.equal(h.calls.clear, 1); assert.deepEqual(h.calls.removed, []);
});

test('toolbar状态来自owner且不更新旧表格选框或旧邮箱map', async () => {
  const h=fixture(['updateAccountSelectionUi']);const checkbox=h.get('accountsSelectAllV2');checkbox.checked='untouched';
  const toolbar=mountToolbarFixture({state:{selectedCount:2,archived:true},getContext:()=>h.contextData,invoke:(...args)=>h.owner.invokeAction(...args)});await toolbar.ready;
  let pendingRefreshes=0;h.owner.syncToolbarPending=()=>{pendingRefreshes++;};
  h.context.updateAccountSelectionUi(null,{selectedIds:['7','8'],selectedEmails:{},archived:'only',total:2,page:1,size:10,loading:false,visible:true});
  assert.equal(pendingRefreshes,1,'旧同步入口仅委托真实owner刷新pending');
  assert.equal(toolbar.get('accountsSelectedHintV2').textContent,'已选 2 个账号');
  assert.equal(toolbar.get('btnArchiveSelectedAccountsV2').textContent,'恢复选中');
  assert.equal(toolbar.get('btnCheckSelectedPlansV2').disabled,false);assert.equal(checkbox.checked,'untouched');
  assert.equal(h.get('accountsSelectedHintV2').textContent,'original','旧DOM不再被同步入口写入');
  assert.equal(h.context.ACCOUNT_SELECTED_EMAILS.get(999),'old@example.test');
});

test('批次创建复制显式快照再navigate；selected=false仍保留query source=null', async () => {
  for (const selected of [true, false]) {
    vueHarness.cleanup();
    const {flushPromises}=require('../../frontend/node_modules/@vue/test-utils');
    const queryContext={window:{},URLSearchParams};vm.runInNewContext(querySource,queryContext);
    const values=new Map();const storage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key),key:index=>[...values.keys()][index]||null,get length(){return values.size;}};
    const deps={adapter:queryContext.window.AccountQuery,storage,now:Date.now,isVisible:()=>true,onNavigation(){},intents:{pending:()=>[],submit:async()=>({}),recover:async()=>({})},
      api:{request:async path=>path==='/catalog'?{operations:[{key:'plan_check',version:1}],limits:{},query_schema:{}}:{matched:2,facets:{}}},
      callbacks:{notify(){},formatDateTime:String,openTask(){},navigate(){},updateNavigation(){}}};
    const wrapper=vueHarness.mount(vueHarness.load('src/features/bulk/BulkPageShell.vue').default,{props:{deps}});
    const snapshot = {ids: ['7', '8'], query: {q: '备注:"a/b 待整理"', archived: 'only'}};
    await wrapper.vm.fromAccounts(selected,'plan_check',snapshot);snapshot.ids.push('99');snapshot.query.q='changed after navigate';await flushPromises();
    const draft=JSON.parse(storage.getItem('turb_bulk_draft_v1'));
    assert.deepEqual(draft.source,selected?{kind:'ids',entity:'account',ids:['7','8']}:null);
    assert.equal(draft.query.q,'备注:"a/b 待整理"');assert.equal(draft.query.archived,'only');
    wrapper.unmount();
  }
});

test('owner卸载后显式动作回执不退回旧列表写路径', async () => {
  const h = fixture(['checkSelectedPlans']);
  h.context.api = async (url, options) => { h.calls.requests.push({url, options}); h.owner.isReady = () => false; return {ok: true, started_count: 2}; };
  await h.context.checkSelectedPlans(h.contextData);
  assert.equal(h.calls.requests.length, 1); assert.equal(h.calls.polls, 0);
  assert.match(h.calls.toasts.join(''), /已入队/);
});

test('Vue真实dispatcher按descriptor分发一次，邮箱与动作来自显式context并保留URL内冒号', async () => {
  const bulkNames = ['copySelectedAccountTokens', 'copySelectedAccountLines', 'copySelectedAccountEmails',
    'copySelectedAccountExtractLinks', 'copySelectedAccountPasswords', 'copySelectedAccountTotpSecrets',
    'downloadSelectedAccountTxt', 'downloadSelectedAccountSessions', 'downloadSelectedCpa',
    'checkSelectedPlans', 'extractSelectedLinks', 'uploadSelectedCodexSub2', 'checkSelectedDeactivationMail',
    'setupSelectedAccounts', 'addPasswordSelectedAccounts', 'addTwofaSelectedAccounts', 'changePasswordSelectedAccounts',
    'changeTwofaSelectedAccounts', 'completeSelectedAccounts', 'stopSelectedCodex', 'retrySelectedCodex',
    'archiveSelectedAccounts', 'deleteSelectedAccounts'];
  const h = fixture([...bulkNames, 'invokeAccountAction', 'stopOneAccountCodex', 'runOneAccountAction', 'setAccountsEmailInvalid']);
  h.owner.getActionContext = () => { throw new Error('must not reread owner for supplied context'); };
  const clicked = plain(h.contextData); clicked.accountIds = ['7'];
  h.context.confirm = () => { clicked.expectedEmails['7'] = 'changed@example.test'; return true; };
  await h.context.invokeAccountAction('codex-stop', clicked, h.get('trigger'));
  assert.equal(h.calls.requests.length, 1);
  assert.deepEqual(JSON.parse(h.calls.requests[0].options.body), {email: 'seven@example.test'});
  await h.context.invokeAccountAction('account-action:password_change', clicked, h.get('trigger'));
  assert.equal(h.calls.requests.length, 2); assert.equal(h.calls.requests[1].url, '/api/accounts/7/action');
  assert.deepEqual(JSON.parse(h.calls.requests[1].options.body), {action: 'password_change'});
  const qr = []; h.context.openQrModal = value => qr.push(value);
  h.context.invokeAccountAction('qr-url:https://example.test:443/image?a=b:c', clicked, h.get('trigger'));
  assert.deepEqual(qr, ['https://example.test:443/image?a=b:c']);
  assert.equal(h.context.ACCOUNT_SELECTED.has(999), true);
});
