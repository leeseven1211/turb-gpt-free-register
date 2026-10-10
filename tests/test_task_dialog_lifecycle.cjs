const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const commonSource = fs.readFileSync(path.join(root, 'webui/static/js/modern/common.js'), 'utf8');
const jobsSource = fs.readFileSync(path.join(root, 'webui/static/js/modern/jobs.js'), 'utf8');
const accountsSource = fs.readFileSync(path.join(root, 'webui/static/js/modern/accounts.js'), 'utf8');

function extractFunction(source, name, nextMarker) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf(nextMarker, start);
  assert.ok(start >= 0 && end > start, `${name} 应存在且可以独立执行`);
  return source.slice(start, end);
}

const functions = [
  extractFunction(commonSource, 'activateTab', "\n$$('.sidebar-nav button[data-tab]').forEach"),
  extractFunction(jobsSource, 'updateModalScrollLock', '\nfunction closeLogModal('),
  extractFunction(jobsSource, 'closeAccountTaskLogModal', '\nfunction openQrModal('),
  extractFunction(accountsSource, 'closeAccountTaskStepDialog', '\nfunction scrollAccountTaskDialogFromWheel('),
].join('\n');

function element(classes = []) {
  const values = new Set(classes);
  return {
    dataset: {},
    style: {},
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

function createView({activeTab = 'register', taskOpen = true, stepOpen = false, otherModal = null} = {}) {
  const nodes = new Map();
  const tabs = ['overview', 'register', 'accounts', 'codex', 'outlook', 'proxy-traffic', 'config'];
  for (const tab of tabs) nodes.set(`#tab-${tab}`, element(tab === activeTab ? [] : ['hidden']));
  nodes.get('#tab-accounts').dataset.moduleView = activeTab === 'tasks' ? 'tasks' : 'active';
  nodes.get('#tab-outlook').dataset.moduleView = 'overview';
  for (const id of ['logPanel', 'liveLogPanel', 'accountTaskLogPanel', 'qrPanel', 'outlookImportModal', 'accountDetailDrawer', 'emailChangeModal']) {
    const open = id === 'accountTaskLogPanel' ? taskOpen : id === otherModal;
    nodes.set(`#${id}`, element(open ? [] : ['hidden']));
  }
  const overlay = element(stepOpen ? [] : ['hidden']);
  nodes.set('#accountTaskStepDetailOverlay', overlay);
  const previouslyInteractive = {inert: stepOpen};
  const previouslyInert = {inert: true};
  const inertState = new Map(stepOpen ? [[previouslyInteractive, false], [previouslyInert, true]] : []);
  const clearedTimers = [];
  const scrollRestores = [];
  const body = element();
  const documentElement = {style: {}, scrollTop: 0};
  const noop = () => {};
  const sandbox = {
    $: selector => nodes.get(selector) || null,
    $$: () => [],
    document: {
      body,
      documentElement,
      getElementById: id => nodes.get(`#${id}`) || null,
    },
    window: {scrollY: 420, scrollTo: (x, y) => scrollRestores.push([x, y])},
    localStorage: {setItem: noop},
    clearInterval: id => clearedTimers.push(id),
    NAV_ALLOWED_TABS: [...tabs, 'tasks'],
    TAB_META: Object.fromEntries([...tabs, 'tasks'].map(tab => [tab, {title: tab, description: tab}])),
    MODULE_VIEW_META: {},
    ACTIVE_TAB: activeTab,
    SHOW_ARCHIVED_ACCOUNTS: false,
    closeMobileSidebar: noop,
    ensureViewLoaded: noop,
    loadDashboard: noop,
    loadAccountTasks: noop,
    loadAccounts: noop,
    loadCodex: noop,
    loadMailResources: noop,
    loadOutlook: noop,
    loadProxyTraffic: noop,
    loadConfig: noop,
    refreshJobs: noop,
    recordNavigationHistory: noop,
    updateNavigationBackButton: noop,
    hideAccountTaskStepTooltip: noop,
    accountTaskRequestId: 7,
    activeAccountTaskId: taskOpen ? 17 : null,
    activeAccountTaskRunId: taskOpen ? 8 : null,
    accountTaskSnapshot: taskOpen ? {id: 17} : null,
    accountTaskEventCursor: 12,
    accountTaskEventCache: [{id: 12}],
    accountTaskRunLogCursor: 20,
    accountTaskRunLogLines: [{message: '测试日志'}],
    accountTaskLogTimer: 91,
    accountTaskStepDetailState: stepOpen ? {stepId: 'step-auth', tab: 'time'} : null,
    accountTaskStepDetailSignature: stepOpen ? '已渲染详情' : '',
    accountTaskStepDetailReturnFocus: null,
    accountTaskStepDetailInert: inertState,
  };
  vm.runInNewContext(`let modalScrollY = 0;\n${functions}`, sandbox);
  sandbox.updateModalScrollLock();
  return {sandbox, nodes, body, documentElement, overlay, inertState, previouslyInteractive, previouslyInert, clearedTimers, scrollRestores};
}

test('从注册切到账号、任务或配置时关闭任务详情并恢复页面滚动', () => {
  for (const tab of ['accounts', 'tasks', 'config']) {
    const view = createView();
    view.sandbox.activateTab(tab);
    assert.equal(view.nodes.get('#accountTaskLogPanel').classList.contains('hidden'), true, `${tab} 切页应关闭详情`);
    assert.equal(view.sandbox.activeAccountTaskId, null);
    assert.equal(view.sandbox.activeAccountTaskRunId, null);
    assert.equal(view.sandbox.accountTaskSnapshot, null);
    assert.equal(view.sandbox.accountTaskRequestId, 8, '关闭应使旧请求失效');
    assert.deepEqual(view.clearedTimers, [91]);
    assert.equal(view.body.classList.contains('modal-open'), false);
    assert.equal(view.body.style.top, '');
    assert.equal(view.documentElement.style.overflow, '');
    assert.deepEqual(view.scrollRestores, [[0, 420]]);
  }
});

test('重激活当前页签保留已打开任务详情和滚动锁', () => {
  for (const activeTab of ['register', 'tasks']) {
    const view = createView({activeTab});
    view.sandbox.activateTab(activeTab);
    assert.equal(view.nodes.get('#accountTaskLogPanel').classList.contains('hidden'), false);
    assert.equal(view.sandbox.activeAccountTaskId, 17);
    assert.equal(view.sandbox.accountTaskRequestId, 7);
    assert.deepEqual(view.clearedTimers, []);
    assert.equal(view.body.classList.contains('modal-open'), true);
    assert.equal(view.documentElement.style.overflow, 'hidden');
    assert.deepEqual(view.scrollRestores, []);
  }
});

test('父任务详情关闭时收起步骤弹窗并恢复原有 inert 状态', () => {
  const view = createView({stepOpen: true});
  view.sandbox.closeAccountTaskLogModal();
  assert.equal(view.overlay.classList.contains('hidden'), true);
  assert.equal(view.sandbox.accountTaskStepDetailState, null);
  assert.equal(view.sandbox.accountTaskStepDetailSignature, '');
  assert.equal(view.inertState.size, 0);
  assert.equal(view.previouslyInteractive.inert, false);
  assert.equal(view.previouslyInert.inert, true);
  assert.equal(view.body.classList.contains('modal-open'), false);
});

test('切页关闭任务详情时保留其它弹窗及其滚动锁', () => {
  const view = createView({otherModal: 'qrPanel'});
  view.sandbox.activateTab('accounts');
  assert.equal(view.nodes.get('#accountTaskLogPanel').classList.contains('hidden'), true);
  assert.equal(view.nodes.get('#qrPanel').classList.contains('hidden'), false);
  assert.equal(view.body.classList.contains('modal-open'), true);
  assert.equal(view.documentElement.style.overflow, 'hidden');
  assert.deepEqual(view.scrollRestores, []);
});

test('任务详情未打开时切页不触发任务关闭或误关其它弹窗', () => {
  const view = createView({taskOpen: false, otherModal: 'qrPanel'});
  view.sandbox.activateTab('config');
  assert.equal(view.sandbox.accountTaskRequestId, 7);
  assert.deepEqual(view.clearedTimers, []);
  assert.equal(view.nodes.get('#qrPanel').classList.contains('hidden'), false);
  assert.equal(view.body.classList.contains('modal-open'), true);
  assert.equal(view.documentElement.style.overflow, 'hidden');
});
