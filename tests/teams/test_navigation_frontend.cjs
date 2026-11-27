const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const read = name => fs.readFileSync(path.join(__dirname, '../../webui/static/js', name), 'utf8');
const accountSource = read('pages/accounts/bridge.js')
  .replace('import(root.dataset.moduleUrl)', 'loadAccountsModule(root.dataset.moduleUrl)');
const teamSource = read('pages/teams/page.js')
  .replace('import(root.dataset.moduleUrl)', 'loadTeamsModule(root.dataset.moduleUrl)');
const plain = value => JSON.parse(JSON.stringify(value));
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

function setup({
  mountGate = Promise.resolve(), lookupGate = Promise.resolve(),
  lookupRow = id => ({id, archived: false, team_memberships: [{membership_state: 'joined'}]}),
  lookupError = null,
} = {}) {
  const calls = {details: [], refreshes: [], queries: [], pages: [], navigation: [], toast: [], lookups: [], mounts: 0};
  const listeners = new Map();
  const root = {dataset: {moduleUrl: '/accounts.js', styleUrl: '/task-center.css'}, replaceChildren() {}, append() {}};
  const accountTab = {dataset: {moduleView: 'active'}, classList: {contains: name => name === 'hidden' && activeTab !== 'accounts'}};
  let activeTab = 'teams', query, rows = [], currentPage = 8;
  const context = {
    window: {},
    URLSearchParams,
    CAPABILITIES: {features: {}},
    createAccountVuePresentation: () => ({}),
    _accountDetailMarkup() {}, facetLabel() {}, updateModalScrollLock() {},
    migrateAccountTableWidths() {}, bindAccountsHoverTooltips() {},
    showToast: message => calls.toast.push(message),
    async api(url) {
      const params = new URL(url, 'http://test.local').searchParams;
      calls.lookups.push(params);
      await lookupGate;
      if (lookupError) throw lookupError;
      const id = params.get('q')?.slice(3);
      const row = typeof lookupRow === 'function' ? lookupRow(id) : lookupRow;
      return {ok: true, items: row ? [row] : []};
    },
    document: {
      hidden: false,
      getElementById: id => id === 'accounts-list-root' ? root : id === 'tab-accounts' ? accountTab : id === 'task-center-style' ? {} : null,
      addEventListener(type, listener) { listeners.set(type, listener); },
    },
    setModuleView(module, view) {
      calls.navigation.push([module, view]);
      accountTab.dataset.moduleView = view;
      context.window.AccountsPage.setAccountView(view);
      void context.window.AccountsPage.setVisible(activeTab === 'accounts');
    },
    activateTab(tab) {
      activeTab = tab;
      context.window.AccountsPage.setAccountView(accountTab.dataset.moduleView);
      void context.window.AccountsPage.setVisible(tab === 'accounts');
    },
    async loadAccountsModule() {
      await mountGate;
      return {mountAccounts() { calls.mounts++; return owner; }};
    },
  };
  vm.runInNewContext(read('shared/account-query.js'), context);
  query = context.window.AccountQuery.normalize({q: '旧筛选', filters: {id: '23', source: ['旧来源']}, plan: ['plus']});
  const owner = {
    setAccountView() {}, setVisible() {},
    updateQuery(value) {
      query = context.window.AccountQuery.normalize({...query, ...value});
      calls.queries.push(plain(query));
    },
    setPage(value) { currentPage = value; calls.pages.push(value); },
    setSize() {}, updateFilters() {}, resetFilters() {},
    async refresh() {
      const gate = deferred();
      const request = {query: plain(query), page: currentPage, finish(ids) { rows = ids.map(id => ({id})); gate.resolve(); }};
      calls.refreshes.push(request);
      await gate.promise;
    },
    getActionContext: () => ({querySnapshot: query}),
    getRowSnapshot: id => rows.find(row => row.id === id),
    openDetail: (...args) => calls.details.push(args),
  };
  vm.runInNewContext(accountSource, context);
  return {
    bridge: context.window.AccountsPage, calls, context,
    setOwnerQuery: raw => { query = context.window.AccountQuery.normalize(raw); },
    changeDocumentVisibility(hidden) { context.document.hidden = hidden; listeners.get('visibilitychange')?.(); },
    hideTab() { activeTab = 'teams'; },
  };
}

test('Team 跳转等待实际挂载和精确账号读取，目标不在当前页也能打开详情', async () => {
  const mount = deferred();
  const h = setup({mountGate: mount.promise});
  assert.equal(typeof h.bridge.openDetailById, 'function');
  const pending = h.bridge.openDetailById('123');
  await tick();
  assert.equal(h.calls.mounts, 0);
  assert.equal(h.calls.refreshes.length, 0);
  assert.deepEqual(h.calls.details, []);
  mount.resolve();
  await tick();
  assert.equal(h.calls.mounts, 1);
  assert.equal(h.calls.refreshes.length, 1);
  assert.equal(h.calls.lookups.length, 1);
  assert.equal(h.calls.lookups[0].get('team_scope'), null);
  assert.equal(h.calls.lookups[0].get('archived'), 'all');
  assert.equal(h.calls.lookups[0].get('page_size'), '1');
  assert.equal(h.calls.lookups[0].get('include_facets'), '0');
  const request = h.calls.refreshes[0];
  assert.equal(request.page, 1);
  assert.equal(request.query.q, 'ID:123');
  assert.equal(request.query.team_scope, 'team');
  assert.equal(request.query.archived, 'all');
  assert.equal(request.query.filters.id, '');
  assert.deepEqual(request.query.filters.source, []);
  assert.deepEqual(request.query.plan, []);
  assert.deepEqual(h.calls.details, []);
  request.finish(['123']);
  await pending;
  assert.deepEqual(h.calls.details, [['123', null]]);
});

test('导航读列表期间离开账号页后不迟到打开详情', async () => {
  const h = setup();
  const pending = h.bridge.openDetailById('123');
  await tick();
  await h.bridge.setVisible(false);
  h.calls.refreshes[0].finish(['123']);
  await pending;
  assert.deepEqual(h.calls.details, []);
  assert.deepEqual(h.calls.toast, []);
});

test('模块挂载期间改选账号子视图会取消旧目标', async () => {
  const mount = deferred();
  const h = setup({mountGate: mount.promise});
  const pending = h.bridge.openDetailById('123');
  await tick();
  h.bridge.setAccountView('active');
  mount.resolve();
  await pending;
  assert.equal(h.calls.refreshes.length, 0);
  assert.deepEqual(h.calls.details, []);
});

test('文档隐藏后再恢复仍取消旧目标，避免后台请求迟到打开', async () => {
  const h = setup();
  const pending = h.bridge.openDetailById('123');
  await tick();
  h.changeDocumentVisibility(true);
  h.changeDocumentVisibility(false);
  h.calls.refreshes[0].finish(['123']);
  await pending;
  assert.deepEqual(h.calls.details, []);
});

test('连续跳转只允许最后一个目标打开', async () => {
  const h = setup();
  const first = h.bridge.openDetailById('123');
  await tick();
  const second = h.bridge.openDetailById('456');
  await tick();
  h.calls.refreshes[1].finish(['456']);
  await second;
  h.calls.refreshes[0].finish(['123']);
  await first;
  assert.deepEqual(h.calls.details, [['456', null]]);
});

test('Vue 内改变筛选或切页时不打开原跳转目标', async () => {
  for (const change of [
    h => h.setOwnerQuery({team_scope: 'team', archived: 'all', q: '其他筛选'}),
    h => h.bridge.setPage(2),
  ]) {
    const h = setup();
    const pending = h.bridge.openDetailById('123');
    await tick();
    change(h);
    h.calls.refreshes[0].finish(['123']);
    await pending;
    assert.deepEqual(h.calls.details, []);
  }
});

test('账号读取为空时显示明确原因；无效账号 ID 不触发导航', async () => {
  const h = setup();
  const pending = h.bridge.openDetailById('123');
  await tick();
  h.calls.refreshes[0].finish([]);
  await pending;
  assert.deepEqual(h.calls.details, []);
  assert.match(h.calls.toast[0], /123/);
  assert.match(h.calls.toast[0], /找不到|未找到|不存在/);
  const invalid = setup();
  for (const id of ['', '0', '12 OR 1', Number.MAX_SAFE_INTEGER + 1]) await invalid.bridge.openDetailById(id);
  assert.equal(invalid.calls.navigation.length, 0);
  assert.equal(invalid.calls.toast.length, 4);
});

test('管理母号按事实进入普通或归档账号页，已归档的 joined 成员仍进入 Team 页', async () => {
  for (const [row, view, teamScope, archived] of [
    [{id: '123', archived: false, team_memberships: []}, 'active', 'non_team', '0'],
    [{id: '123', archived: true, team_memberships: []}, 'archived', 'all', 'only'],
    [{id: '123', archived: true, team_memberships: [{membership_state: 'joined'}]}, 'team', 'team', 'all'],
  ]) {
    const h = setup({lookupRow: row});
    const pending = h.bridge.openDetailById('123');
    await tick();
    assert.deepEqual(h.calls.navigation, [['accounts', view]]);
    assert.equal(h.calls.refreshes[0].query.team_scope, teamScope);
    assert.equal(h.calls.refreshes[0].query.archived, archived);
    h.calls.refreshes[0].finish(['123']);
    await pending;
    assert.deepEqual(h.calls.details, [['123', null]]);
  }
});

test('精确定位尚未返回时离开页面，会取消后续菜单导航', async () => {
  const lookup = deferred();
  const h = setup({lookupGate: lookup.promise});
  const pending = h.bridge.openDetailById('123');
  await h.bridge.setVisible(false);
  lookup.resolve();
  await pending;
  assert.deepEqual(h.calls.navigation, []);
  assert.deepEqual(h.calls.details, []);
});

test('定位不到账号或读取失败时保持当前页并给出原因', async () => {
  for (const options of [{lookupRow: null}, {lookupError: new Error('读取连接中断')}]) {
    const h = setup(options);
    await h.bridge.openDetailById('123');
    assert.deepEqual(h.calls.navigation, []);
    assert.deepEqual(h.calls.details, []);
    assert.equal(h.calls.toast.length, 1);
    assert.match(h.calls.toast[0], options.lookupError ? /读取连接中断/ : /123/);
  }
});

test('Team 成员详情回调直接等待账号桥接，不使用定时器猜测挂载时间', async () => {
  const gate = deferred();
  const calls = [];
  let callbacks;
  const root = {dataset: {moduleUrl: '/teams.js'}, replaceChildren() {}};
  const context = {
    window: {AccountsPage: {openDetailById: (...args) => { calls.push(args); return gate.promise; }}},
    document: {
      hidden: false,
      getElementById: id => id === 'teams-page-root' ? root : id === 'task-center-style' ? {} : null,
      addEventListener() {},
    },
    async loadTeamsModule() {
      return {mountTeams(_root, options) { callbacks = options.callbacks; return {setVisible() {}}; }};
    },
  };
  vm.runInNewContext(teamSource, context);
  await context.window.TeamsPage.activate();
  const pending = callbacks.openAccountDetail('123');
  assert.equal(pending, gate.promise);
  assert.deepEqual(plain(calls), [['123']]);
  gate.resolve();
  await pending;
});
