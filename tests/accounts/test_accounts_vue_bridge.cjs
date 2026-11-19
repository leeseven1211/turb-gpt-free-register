const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/accounts/bridge.js'), 'utf8');
const executable = source.replace('import(root.dataset.moduleUrl)', 'loadAccountsModule(root.dataset.moduleUrl)');
const plain = value => JSON.parse(JSON.stringify(value));
function setup(load) {
  const calls = {imports: [], mounts: 0, archived: [], visible: [], refresh: 0, polls: 0,
    removed: [], cleared: 0, states: [], actions: [], details: [], detailClosed: [], toast: [], gated: [], migrations: 0};
  let callbacks, mountedOptions;
  const snapshot = Object.freeze({ids: Object.freeze(['1', '11']), expectedEmails: Object.freeze({'1': 'first@example.test', '11': 'second@example.test'})});
  const actionContext = Object.freeze({accountIds: snapshot.ids, expectedEmails: snapshot.expectedEmails,
    rowHints: Object.freeze([]), archived: 'only', querySnapshot: Object.freeze({archived: 'only'})});
  const lease = {openGeneration: 7, release() {}, async loadPlanDetails() { return {}; }};
  const instance = {
    setArchived: value => calls.archived.push(value), setVisible: value => calls.visible.push(value),
    refresh: async () => { calls.refresh++; }, pollStatuses: async () => { calls.polls++; },
    getAccountSelectionSnapshot: () => snapshot, getActionContext: () => actionContext,
    getRowSnapshot: id => ({id, email: 'row@example.test'}), openPlanDetailsConsumer: () => lease,
    openDetail: (...args) => calls.details.push(args), closeDetail: value => calls.detailClosed.push(value),
    syncToolbarPending() {},setCapabilities() {},refreshQuickActions() {},
    isActionSupported: action => action === 'downloadSelectedAccountSessions',
    isActionPending: action => action === 'downloadSelectedAccountSessions',
    invokeAction: (...args) => calls.actions.push(args),
    removeAcknowledgedSelection: ids => calls.removed.push(ids), clearSelection: () => { calls.cleared++; },
    resetColumns() {}, updateQuery() {}, updateFilters() {}, resetFilters() {}, setPage() {}, setSize() {},
  };
  const root = {dataset: {moduleUrl: '/accounts.js', styleUrl: '/task-center.css'}, children: [],
    replaceChildren() { this.children = []; }, append(...items) { this.children.push(...items); }};
  let style;
  const buttons = new Map();
  const query = {normalize() {}, toLegacy() {}, fromLegacy() {}};
  const presentation = {marker: 'legacy-public-presenters'};
  const context = {
    CAPABILITIES:{features:{}},
    window: {AccountQuery: query},
    showToast: message => calls.toast.push(message),
    createAccountVuePresentation: () => presentation,
    _accountDetailMarkup: () => 'detail', facetLabel: (_field,value) => value,
    updateModalScrollLock() {}, syncAccountsVueTooltip() {},
    migrateAccountTableWidths: () => { calls.migrations++; },
    updateAccountSelectionUi: (_rows, state) => calls.states.push(state),
    invokeAccountAction: (...args) => calls.actions.push(args),
    openAccountDetail: (...args) => calls.details.push(args),
    closeAccountDetail() {}, closeAccountsVueTooltip() {},
    applyFeatureGates: node => calls.gated.push(node),
    document: {
      getElementById: id => id === 'accounts-list-root' ? root : id === 'task-center-style' ? style : buttons.get(id) || null,
      createElement: () => ({setAttribute() {}, addEventListener(type, callback) { this[type] = callback; }}),
      head: {append(value) { style = value; }},
    },
    async loadAccountsModule(url) {
      calls.imports.push(url); if (load) await load();
      return {mountAccounts(node, options) {
        calls.mounts++; assert.equal(node, root); assert.equal(options.query, query);
        assert.equal(options.presentation, presentation); callbacks = options.callbacks; mountedOptions = options;
        return instance;
      }};
    },
  };
  vm.runInNewContext(executable, context);
  return {bridge: context.window.AccountsPage, calls, root, callbacks: () => callbacks, options: () => mountedOptions, buttons, snapshot, actionContext, lease};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('隐藏账号页不加载；动作快照在挂载前明确不可用', async () => {
  const {bridge, calls} = setup();
  bridge.setArchived(true); await bridge.refresh(); await bridge.pollStatuses();
  assert.equal(bridge.isReady(), false); assert.equal(calls.imports.length, 0);
  assert.throws(() => bridge.getActionContext(), /加载/);
  await bridge.setVisible(true);
  assert.equal(bridge.isReady(), true); assert.deepEqual(calls.archived, [true]);
  assert.deepEqual(calls.visible, [true]); assert.equal(calls.refresh, 0);
  assert.equal(calls.migrations, 1);
});

test('连续显示只挂载一次，模块加载途中导航采用最后范围和可见性', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const {bridge, calls} = setup(() => pending);
  const first = bridge.setVisible(true), second = bridge.setVisible(true), refresh = bridge.refresh();
  bridge.setArchived(true); await bridge.setVisible(false); finish();
  await Promise.all([first, second, refresh]);
  assert.equal(calls.imports.length, 1); assert.equal(calls.mounts, 1);
  assert.deepEqual(calls.archived, [true]); assert.deepEqual(calls.visible, [false]);
  assert.equal(calls.refresh, 0); await bridge.setVisible(true);
  assert.deepEqual(calls.visible, [false, true]);
});

test('快照、详情租约与回流只转交真实owner，不另建选择状态', async () => {
  const h = setup(); await h.bridge.setVisible(true);
  assert.equal(h.bridge.getAccountSelectionSnapshot(), h.snapshot);
  assert.equal(h.bridge.getActionContext(), h.actionContext);
  assert.equal(h.bridge.openPlanDetailsConsumer('1'), h.lease);
  assert.deepEqual(plain(h.bridge.getRowSnapshot('1')), {id:'1', email:'row@example.test'});
  h.bridge.openDetail(1, 'trigger'); h.bridge.closeDetail(false);
  assert.deepEqual(plain(h.calls.details), [['1', 'trigger']]);
  assert.deepEqual(h.calls.detailClosed, [false]);
  h.bridge.removeAcknowledgedSelection(['1']); h.bridge.clearSelection();
  await h.bridge.refresh(); await h.bridge.pollStatuses();
  assert.deepEqual(h.calls.removed, [['1']]); assert.equal(h.calls.cleared, 1);
  assert.equal(h.calls.refresh, 1); assert.equal(h.calls.polls, 1);
  const trigger = {id:'button'};
  h.callbacks().invoke('emailInvalid', h.actionContext, trigger);
  assert.equal(h.calls.actions[0][1], h.actionContext); assert.equal(h.calls.actions[0][2], trigger);
  h.callbacks().onStateChange({selectedIds:['1'],total:20});
  assert.deepEqual(plain(h.calls.states[0]), {selectedIds:['1'],total:20});
});

test('模块失败有明确重试，重试仍使用最后归档范围且不会重复挂载', async () => {
  let attempts = 0;
  const h = setup(async () => { if (!attempts++) throw new Error('连接中断'); });
  await h.bridge.setVisible(true);
  assert.equal(h.bridge.isReady(), false); assert.match(h.root.children[0].textContent, /连接中断/);
  assert.equal(h.root.children[1].textContent, '重新加载');
  h.bridge.setArchived(true); h.root.children[1].click(); await tick();
  assert.equal(h.calls.imports.length, 2); assert.equal(h.calls.mounts, 1);
  assert.deepEqual(h.calls.archived, [true]); assert.equal(h.bridge.isReady(), true);
});

test('动作门禁和忙碌按钮由桥接层读取，pending来自真实owner并在恢复时重新应用选择和能力',async()=>{
  const h=setup();await h.bridge.setVisible(true);
  const button={disabled:false,textContent:'下载 Session',attributes:new Map(),getAttribute(key){return this.attributes.get(key);},classList:{contains:()=>false}};
  h.buttons.set('btnDownloadSelectedSessionsV2',button);
  const deps=h.options().actionDependencies;
  assert.equal(deps.canInvoke('downloadSelectedAccountSessions',null),true);
  button.attributes.set('aria-disabled','true');assert.equal(deps.canInvoke('downloadSelectedAccountSessions',null),false);
  button.attributes.delete('aria-disabled');
  const restore=deps.beginBusy('downloadSelectedAccountSessions',null,'打包中…');
  assert.equal(button.disabled,true);assert.equal(button.textContent,'打包中…');
  assert.equal(deps.canInvoke('downloadSelectedAccountSessions',null),false);
  assert.equal(h.bridge.isActionSupported('downloadSelectedAccountSessions'),true);
  assert.equal(h.bridge.isActionPending('downloadSelectedAccountSessions'),true);
  h.bridge.invokeAction('downloadSelectedAccountSessions',h.actionContext);
  assert.equal(h.calls.actions[0][1],h.actionContext);
  restore();assert.equal(button.textContent,'下载 Session');assert.equal(button.disabled,false);
  assert.equal(h.calls.states.length,1);assert.equal(h.calls.gated.length,1);
  button.classList.contains=()=>true;assert.equal(deps.canInvoke('downloadSelectedAccountSessions',null),false);
});
