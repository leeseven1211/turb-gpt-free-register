const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..', '..');
const commonSource = fs.readFileSync(path.join(root, 'webui/static/js/shared/common.js'), 'utf8');
const modalSource = fs.readFileSync(path.join(root, 'webui/static/js/shared/modal-compat.js'), 'utf8');
const accountsSource = require('../frontend_script_sources.cjs').readAccountScripts();

function extractFunction(source, name, nextMarker) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf(nextMarker, start);
  assert.ok(start >= 0 && end > start, `${name} 应存在且可以独立执行`);
  return source.slice(start, end);
}

const functions = [
  extractFunction(commonSource, 'closePageDialogsForNavigation', '\nfunction activateTab('),
  extractFunction(commonSource, 'activateTab', "\n$$('.sidebar-nav button[data-tab]').forEach"),
  extractFunction(commonSource, 'setModuleView', "\n$$('[data-module-subnav]').forEach"),
  extractFunction(accountsSource, 'closeAccountDetail', '\nfunction closeAccountsV2MoreMenus('),
  accountsSource.match(/^function closeEmailChangeModal[^\n]+/m)[0],
].join('\n');

function element(classes = [], parentElement = null) {
  const values = new Set(classes);
  const attributes = new Map();
  return {
    dataset: {},
    style: {},
    parentElement,
    hidden: false,
    setAttribute(name, value) { attributes.set(name, String(value)); },
    getAttribute(name) { return attributes.get(name) ?? null; },
    removeAttribute(name) {
      attributes.delete(name);
      if (name.startsWith('data-')) {
        delete this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())];
      }
    },
    closest(selector) {
      assert.equal(selector.replace(/\s/g, ''), '.hidden,[hidden]', '滚动锁应检查当前元素及隐藏祖先');
      for (let node = this; node; node = node.parentElement) {
        if (node.classList.contains('hidden') || node.hidden || node.getAttribute('hidden') !== null) return node;
      }
      return null;
    },
    classList: {
      contains: name => values.has(name),
      add: name => values.add(name),
      remove: name => values.delete(name),
      toggle(name, force) {
        const added = force === undefined ? !values.has(name) : force;
        if (added) values.add(name);
        else values.delete(name);
        return added;
      },
    },
  };
}

function createView({activeTab = 'register', taskOpen = true, stepOpen = false, otherModal = null, openDialogs = []} = {}) {
  const nodes = new Map();
  const body = element();
  const documentElement = element();
  documentElement.scrollTop = 0;
  body.parentElement = documentElement;
  const tabs = ['overview', 'register', 'bulk', 'accounts', 'extract-workbench', 'extract-stats', 'codex', 'outlook', 'proxy-traffic', 'config'];
  const contentTab = activeTab === 'tasks' ? 'accounts' : activeTab;
  for (const tab of tabs) nodes.set(`#tab-${tab}`, element(tab === contentTab ? [] : ['hidden'], body));
  nodes.get('#tab-accounts').dataset.moduleView = activeTab === 'tasks' ? 'tasks' : 'active';
  nodes.get('#tab-outlook').dataset.moduleView = 'overview';
  const open = new Set(openDialogs);
  if (taskOpen) open.add('accountTaskLogPanel');
  if (otherModal) open.add(otherModal);
  for (const id of ['logPanel', 'liveLogPanel', 'accountTaskLogPanel', 'qrPanel', 'accountDetailDrawer', 'emailChangeModal', 'overviewCustomizer']) {
    const parent = ['liveLogPanel', 'accountDetailDrawer', 'emailChangeModal'].includes(id)
      ? nodes.get('#tab-accounts')
      : id === 'overviewCustomizer' ? nodes.get('#tab-overview') : body;
    nodes.set(`#${id}`, element(open.has(id) ? [] : ['hidden'], parent));
  }
  for (const [id, panel, parent] of [
    ['accountDetailBackdrop', 'accountDetailDrawer', 'accounts'],
    ['overviewCustomizerBackdrop', 'overviewCustomizer', 'overview'],
  ]) nodes.set(`#${id}`, element(open.has(panel) ? [] : ['hidden'], nodes.get(`#tab-${parent}`)));
  nodes.get('#accountDetailDrawer').dataset.accountId = '37';
  nodes.get('#emailChangeModal').dataset.accountId = '37';
  nodes.get('#emailChangeModal').dataset.accountIds = '[37,38]';
  nodes.set('#emailChangeTitle', element());
  const focused = [];
  for (const id of ['btnCustomizeOverview', 'btnCloseAccountTaskLog']) {
    const button = element();
    button.focus = () => focused.push(id);
    nodes.set(`#${id}`, button);
  }
  const returnFocus = {isConnected: true, focus: () => focused.push('原触发按钮')};
  const overlay = element(stepOpen ? [] : ['hidden'], nodes.get('#accountTaskLogPanel'));
  nodes.set('#accountTaskStepDetailOverlay', overlay);
  const previouslyInteractive = {inert: stepOpen};
  const previouslyInert = {inert: true};
  const inertState = new Map(stepOpen ? [[previouslyInteractive, false], [previouslyInert, true]] : []);
  const clearedTimers = [];
  const scrollRestores = [];
  const noop = () => {};
  const sandbox = {
    $: selector => nodes.get(selector) || null,
    $$: () => [],
    document: {
      body,
      documentElement,
      getElementById: id => nodes.get(`#${id}`) || null,
      querySelectorAll: () => [],
      querySelector: () => null,
      addEventListener() {},
    },
    window: {scrollY: 420, scrollTo: (x, y) => scrollRestores.push([x, y]), TaskCenter: {closeDetail() { sandbox.taskCloseCalls++; nodes.get('#accountTaskLogPanel').classList.add('hidden'); }, setVisible() {}}},
    localStorage: {setItem: noop},
    clearInterval: id => clearedTimers.push(id),
    NAV_ALLOWED_TABS: [...tabs, 'tasks'],
    TAB_META: Object.fromEntries([...tabs, 'tasks'].map(tab => [tab, {title: tab, description: tab}])),
    MODULE_VIEW_META: {
      accounts: {active: '活跃账号', archived: '归档账号', tasks: '任务'},
      outlook: {overview: '总览', list: '邮箱列表'},
    },
    ACTIVE_TAB: activeTab,
    SHOW_ARCHIVED_ACCOUNTS: false,
    closeMobileSidebar: noop,
    ensureViewLoaded: noop,
    loadDashboard: noop,
    loadAccountTasks: noop,
    loadAccounts: noop,
    loadExtractWorkbench: noop,
    loadExtractStats: noop,
    taskCloseCalls: 0,
    loadCodex: noop,
    loadMailResources: noop,
    loadOutlook: noop,
    loadProxyTraffic: noop,
    loadConfig: noop,
    refreshJobs: noop,
    recordNavigationHistory: noop,
    updateNavigationBackButton: noop,
    applyAccountsArchivedFilter: archived => { sandbox.SHOW_ARCHIVED_ACCOUNTS = archived; },
    hideAccountTaskStepTooltip: noop,
    emailChangeReturnFocus: returnFocus,
    liveLogEmail: '测试目标',
    liveLogTimer: 92,
    overviewCustomizerOpen: false,
    accountTaskRequestId: 7,
    activeAccountTaskId: open.has('accountTaskLogPanel') ? 17 : null,
    activeAccountTaskRunId: open.has('accountTaskLogPanel') ? 8 : null,
    accountTaskSnapshot: open.has('accountTaskLogPanel') ? {id: 17} : null,
    accountTaskEventCursor: 12,
    accountTaskEventCache: [{id: 12}],
    accountTaskRunLogCursor: 20,
    accountTaskRunLogLines: [{message: '测试日志'}],
    accountTaskLogTimer: 91,
    accountTaskStepDetailState: stepOpen ? {stepId: 'step-auth', tab: 'time'} : null,
    accountTaskStepDetailSignature: stepOpen ? '已渲染详情' : '',
    accountTaskStepDetailReturnFocus: stepOpen ? returnFocus : null,
    accountTaskStepDetailInert: inertState,
  };
  Object.assign(sandbox, sandbox.window);
  sandbox.window = sandbox;
  const dashboardCalls = [];
  sandbox.DashboardPage = {
    closeDialogs() {dashboardCalls.push('close');},
    setVisible(value) {dashboardCalls.push(['visible', value]);},
  };
  // Only owner boundaries are synthetic. Navigation, legacy modal lifetime
  // and account compatibility wrappers execute their actual source.
  // Native Dashboard/Registration rendering has mounted Vue coverage.
  sandbox.window.AccountsPage = {
    closeEmailChange({restoreFocus=true}={}) {
      // The real wrapper forwards focus options; Vue's direct component suite owns rendering.
      const modal=nodes.get('#emailChangeModal');modal.classList.add('hidden');modal.setAttribute('aria-hidden','true');
      modal.dataset.accountId='';modal.dataset.accountIds='';
      if(restoreFocus)sandbox.emailChangeReturnFocus?.focus({preventScroll:true});sandbox.emailChangeReturnFocus=null;
      sandbox.updateModalScrollLock();
    },
    closeDetail(restoreFocus) {
      assert.equal(restoreFocus, false, '导航不得把焦点恢复到正在离开的页面');
      nodes.get('#accountDetailDrawer').classList.add('hidden');
      nodes.get('#accountDetailBackdrop').classList.add('hidden');
      nodes.get('#accountDetailBackdrop').setAttribute('aria-hidden', 'true');
      nodes.get('#accountDetailDrawer').removeAttribute('data-account-id');
      sandbox.updateModalScrollLock();
    },
    setVisible() {}, setArchived() {},
  };
  vm.runInNewContext(`${modalSource}\n${functions}`, sandbox);
  sandbox.updateModalScrollLock();
  return {sandbox, nodes, body, documentElement, overlay, inertState, previouslyInteractive, previouslyInert, clearedTimers, scrollRestores, focused, returnFocus, dashboardCalls};
}

test('切换页面通过任务模块关闭详情，重激活当前页不关闭', () => {
  for (const tab of ['accounts', 'tasks', 'config']) {
    const view = createView();
    view.sandbox.activateTab(tab);
    assert.equal(view.sandbox.taskCloseCalls, 1);
    assert.equal(view.nodes.get('#accountTaskLogPanel').classList.contains('hidden'), true);
    assert.equal(view.body.classList.contains('modal-open'), false, 'Vue 任务详情不使用旧页面滚动锁');
  }
  const view = createView({activeTab: 'tasks'});
  view.sandbox.activateTab('tasks');
  assert.equal(view.sandbox.taskCloseCalls, 0);
});

test('从账号页返回注册页关闭账号详情、换绑邮箱或查活日志并释放滚动锁', () => {
  for (const id of ['accountDetailDrawer', 'emailChangeModal', 'liveLogPanel']) {
    const view = createView({activeTab: 'accounts', taskOpen: false, otherModal: id});
    assert.equal(view.body.classList.contains('modal-open'), true, `${id} 打开时应锁定背景`);
    view.sandbox.activateTab('register');
    assert.equal(view.nodes.get(`#${id}`).classList.contains('hidden'), true, `${id} 切页应关闭`);
    assert.equal(view.nodes.get('#tab-register').classList.contains('hidden'), false);
    assert.equal(view.body.classList.contains('modal-open'), false);
    assert.equal(view.body.style.top, '');
    assert.equal(view.documentElement.style.overflow, '');
    assert.deepEqual(view.scrollRestores, [[0, 420]]);
    assert.deepEqual(view.focused, [], '切页时不能把焦点恢复到原页面');
    if (id === 'accountDetailDrawer') {
      assert.equal(view.nodes.get('#accountDetailBackdrop').classList.contains('hidden'), true);
      assert.equal(view.nodes.get('#accountDetailBackdrop').getAttribute('aria-hidden'), 'true');
      assert.equal(view.nodes.get('#accountDetailDrawer').dataset.accountId, undefined);
    } else if (id === 'emailChangeModal') {
      assert.equal(view.nodes.get('#emailChangeModal').getAttribute('aria-hidden'), 'true');
      assert.equal(view.nodes.get('#emailChangeModal').dataset.accountId, '');
      assert.equal(view.nodes.get('#emailChangeModal').dataset.accountIds, '');
      assert.equal(view.sandbox.emailChangeReturnFocus, null);
    } else {
      assert.equal(view.sandbox.liveLogEmail, null);
      assert.deepEqual(view.clearedTimers, [92]);
    }
  }
});

test('同时关闭页面弹窗时保留账号清理语义，任务模块接收关闭', () => {
  const view = createView({activeTab: 'accounts', openDialogs: ['accountDetailDrawer', 'emailChangeModal', 'liveLogPanel']});
  view.sandbox.activateTab('register');
  assert.equal(view.sandbox.taskCloseCalls, 1);
  assert.deepEqual(view.clearedTimers, [92]);
  assert.equal(view.sandbox.emailChangeReturnFocus, null);
  assert.deepEqual(view.focused, []);
  assert.deepEqual(view.scrollRestores, [[0, 420]]);
});

test('重激活账号页保留账号弹窗和轮询，普通关闭换绑弹窗仍恢复焦点', () => {
  for (const id of ['accountDetailDrawer', 'emailChangeModal', 'liveLogPanel']) {
    const view = createView({activeTab: 'accounts', taskOpen: false, otherModal: id});
    view.sandbox.activateTab('accounts');
    assert.equal(view.nodes.get(`#${id}`).classList.contains('hidden'), false);
    assert.equal(view.body.classList.contains('modal-open'), true);
    assert.deepEqual(view.clearedTimers, []);
    assert.deepEqual(view.scrollRestores, []);
    assert.deepEqual(view.focused, []);
  }
  const view = createView({activeTab: 'accounts', taskOpen: false, otherModal: 'emailChangeModal'});
  view.sandbox.closeEmailChangeModal();
  assert.deepEqual(view.focused, ['原触发按钮']);
  assert.equal(view.sandbox.emailChangeReturnFocus, null);
});

test('账号子视图切换关闭页面弹窗并解锁，重复选择当前子视图保留弹窗', () => {
  for (const id of ['accountDetailDrawer', 'emailChangeModal', 'liveLogPanel']) {
    const view = createView({activeTab: 'accounts', taskOpen: false, otherModal: id});
    view.sandbox.setModuleView('accounts', 'active');
    assert.equal(view.nodes.get(`#${id}`).classList.contains('hidden'), false, `${id} 当前子视图应保留`);
    assert.equal(view.body.classList.contains('modal-open'), true);
    assert.deepEqual(view.clearedTimers, []);
    view.sandbox.setModuleView('accounts', 'archived');
    assert.equal(view.nodes.get('#tab-accounts').dataset.moduleView, 'archived');
    assert.equal(view.nodes.get(`#${id}`).classList.contains('hidden'), true, `${id} 换子视图应关闭`);
    assert.equal(view.body.classList.contains('modal-open'), false);
    assert.equal(view.documentElement.style.overflow, '');
    assert.deepEqual(view.focused, []);
    assert.deepEqual(view.scrollRestores, [[0, 420]]);
  }
});

test('弹窗自己未关闭但祖先具有 hidden 类或属性时不能继续锁住页面', () => {
  for (const hide of [
    parent => parent.classList.add('hidden'),
    parent => parent.setAttribute('hidden', ''),
  ]) {
    for (const id of ['accountDetailDrawer', 'emailChangeModal', 'liveLogPanel']) {
      const view = createView({activeTab: 'accounts', taskOpen: false, otherModal: id});
      hide(view.nodes.get('#tab-accounts'));
      view.sandbox.updateModalScrollLock();
      assert.equal(view.nodes.get(`#${id}`).classList.contains('hidden'), false, '只检测可见性，不修改弹窗状态');
      assert.equal(view.body.classList.contains('modal-open'), false, `${id} 的隐藏祖先应释放锁`);
      assert.equal(view.documentElement.style.overflow, '');
      assert.deepEqual(view.scrollRestores, [[0, 420]]);
    }
  }
});

test('账号页隐藏后遗留的局部弹窗不会在注册页重新加锁', () => {
  const view = createView({
    taskOpen: false, openDialogs: ['accountDetailDrawer', 'emailChangeModal', 'liveLogPanel'],
  });
  assert.equal(view.body.classList.contains('modal-open'), false);
  assert.deepEqual(view.scrollRestores, []);
  view.sandbox.activateTab('register');
  assert.equal(view.body.classList.contains('modal-open'), false);
  assert.deepEqual(view.scrollRestores, []);
});

test('切页关闭任务详情时保留全局弹窗及其滚动锁', () => {
  for (const id of ['qrPanel']) {
    const view = createView({otherModal: id});
    view.sandbox.activateTab('accounts');
    assert.equal(view.nodes.get('#accountTaskLogPanel').classList.contains('hidden'), true);
    assert.equal(view.nodes.get(`#${id}`).classList.contains('hidden'), false);
    assert.equal(view.body.classList.contains('modal-open'), true);
    assert.equal(view.documentElement.style.overflow, 'hidden');
    assert.deepEqual(view.scrollRestores, []);
  }
});

test('邮箱原生导入弹窗由页面owner在导航时关闭，交付最终可见性', () => {
  const view = createView({activeTab:'outlook',taskOpen:false});
  const calls = [];
  view.sandbox.window.EmailPage = {
    closeDialogs() {calls.push('close');},
    setView(value) {calls.push(['view', value]);},
    setVisible(value) {calls.push(['visible', value]);},
  };
  view.sandbox.activateTab('accounts');
  assert.equal(calls[0], 'close');
  assert.deepEqual(calls.at(-1), ['visible', false]);
  assert.equal(view.body.classList.contains('modal-open'), false);
});

test('任务详情未打开时切页不触发任务关闭或误关其它弹窗', () => {
  const view = createView({taskOpen: false, otherModal: 'qrPanel'});
  view.sandbox.activateTab('config');
  assert.equal(view.sandbox.taskCloseCalls, 1, '关闭空详情仍使待加载请求失效');
  assert.deepEqual(view.clearedTimers, []);
  assert.equal(view.nodes.get('#qrPanel').classList.contains('hidden'), false);
  assert.equal(view.body.classList.contains('modal-open'), true);
  assert.equal(view.documentElement.style.overflow, 'hidden');
  assert.equal(view.sandbox.emailChangeReturnFocus, view.returnFocus, '未打开的换绑弹窗不执行关闭逻辑');
  assert.equal(view.nodes.get('#accountDetailDrawer').dataset.accountId, '37', '未打开的账号详情不执行关闭逻辑');
  assert.deepEqual(view.focused, [], '未打开的总览面板不执行关闭逻辑');
});

test('离开总览由唯一Vue owner关闭原生自定义面板并停止读取', () => {
  const view = createView({activeTab: 'overview', taskOpen: false});
  assert.equal(view.body.classList.contains('modal-open'), false);
  view.sandbox.activateTab('register');
  assert.deepEqual(view.dashboardCalls, ['close', ['visible', false]]);
  assert.equal(view.body.classList.contains('modal-open'), false);
});
