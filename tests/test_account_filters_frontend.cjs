const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const common = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');
const accounts = require('./frontend_script_sources.cjs').readAccountScripts();
function functionSource(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `应提供 ${name}`);
  const next = source.slice(start + 1).search(/\n(?:async )?function /);
  return source.slice(start, next < 0 ? undefined : start + 1 + next);
}
function select() {
  return {
    multiple: true, dataset: {}, options: [],
    get selectedOptions() { return this.options.filter(option => option.selected); },
    get value() { return this.selectedOptions[0]?.value || ''; },
    set innerHTML(html) {
      this.options = [...html.matchAll(/<option value="([^"]*)">([^<]*)<\/option>/g)].map(([, value, label]) => ({value, textContent: label, selected: false}));
    },
  };
}
function harness() {
  const controls = new Map();
  const view = {
    document: {getElementById: id => controls.get(id)},
    URLSearchParams,
    esc: value => String(value), attrEsc: value => String(value),
    refreshColumnFilterState() {}, renderColumnFilterOptions() {},
    SHOW_ARCHIVED_ACCOUNTS: false, SHOW_PLUS_ACCOUNTS_ONLY: false,
    accountAdvancedSearchQuery: '', PAGERS: {accounts: {page: 2, size: 20}},
  };
  vm.createContext(view);
  const labelsStart = common.indexOf('const LIST_FACET_LABELS =');
  vm.runInContext(common.slice(labelsStart, common.indexOf('\n};', labelsStart) + 3), view);
  vm.runInContext(common.slice(common.indexOf('function facetLabel('), common.indexOf('// ---------- 分页状态 ----------')), view);
  vm.runInContext([functionSource(common, 'columnFilterDisplayValue'), functionSource(accounts, 'getAccountsQuery'), functionSource(accounts, 'accountListQueryParams'), functionSource(accounts, 'accountRegistrationDriverLabel')].join('\n'), view);
  return {view, controls};
}

test('实际选项包含未查询，零计数选项不显示，多选同步后保留有效项', () => {
  const {view, controls} = harness();
  const control = select();
  controls.set('accountPlanFilterV2', control);
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'free', count: 2}, {value: 'unqueried', count: 3}, {value: 'pro', count: 0}], {group: 'plan'});
  assert.deepEqual(control.options.map(option => option.textContent), ['全部', 'Free · 2', '未查询 · 3']);
  view.setColumnFilterValue(control, 'free,unqueried');
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'unqueried', count: 4}], {group: 'plan'});
  assert.equal(view.columnFilterValue(control), 'unqueried');
  view.syncFacetSelect('accountPlanFilterV2', [], {group: 'plan'});
  assert.equal(view.columnFilterValue(control), '');
  assert.equal(control.options[0].selected, true);
});

test('多选值采用稳定顺序，计数变化和重排不会改变请求条件', () => {
  const {view, controls} = harness();
  const control = select();
  controls.set('accountPlanFilterV2', control);
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'unqueried', count: 3}, {value: 'free', count: 2}], {group: 'plan'});
  view.setColumnFilterValue(control, 'unqueried,free');
  assert.equal(view.columnFilterValue(control), 'free,unqueried');
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'free', count: 4}, {value: 'unqueried', count: 1}], {group: 'plan'});
  assert.equal(view.columnFilterValue(control), 'free,unqueried');
});

test('账号联动统计保留零匹配的已选项，恢复匹配后更新数量', () => {
  const {view, controls} = harness();
  const control = select();
  controls.set('accountPlanFilterV2', control);
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'free', count: 2}, {value: 'plus', count: 1}], {group: 'plan'});
  view.setColumnFilterValue(control, 'free,plus');
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'plus', count: 1}, {value: 'pro', count: 0}], {group: 'plan', preserveSelected: true});
  assert.equal(view.columnFilterValue(control), 'free,plus');
  assert.deepEqual(control.options.map(option => option.textContent), ['全部', 'Plus · 1', 'Free · 0']);
  view.syncFacetSelect('accountPlanFilterV2', [], {group: 'plan', preserveSelected: true});
  assert.equal(view.columnFilterValue(control), 'free,plus');
  assert.deepEqual(control.options.map(option => option.textContent), ['全部', 'Free · 0', 'Plus · 0']);
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'free', count: 3}, {value: 'plus', count: 2}], {group: 'plan', preserveSelected: true});
  assert.equal(view.columnFilterValue(control), 'free,plus');
  assert.deepEqual(control.options.map(option => option.textContent), ['全部', 'Free · 3', 'Plus · 2']);
});

test('账号组合筛选零结果时保留条件，不因同步选项重新加载', async () => {
  const {view, controls} = harness();
  for (const [id, value] of [['accountSourceFilterV2', 'outlook'], ['accountPlanFilterV2', 'plus']]) {
    const control = select();
    controls.set(id, control);
    view.syncFacetSelect(id, [{value, count: 1}]);
    view.setColumnFilterValue(control, value);
  }
  const body = {innerHTML: ''};
  let requests = 0;
  let renders = 0;
  Object.assign(view, {
    $: () => body, accountsLoading: false, accountsReloadQueued: false, accountsRenderedQuery: '',
    PAGERS: {accounts: {page: 1, size: 20}},
    api: async () => { requests += 1; return {items: [], total: 0, facets: {source: [], plan: []}}; },
    setListBusy() {}, showAccountSearchError() {}, renderAccountSearchTerms() {},
    renderAccounts() { renders += 1; }, markViewReady() {},
    showToast(message) { throw Error(message); }, renderTableStateRow: () => '',
  });
  vm.runInContext(functionSource(accounts, 'showAccountsLoadingState'), view);
  vm.runInContext(`async ${functionSource(accounts, 'loadAccounts')}`, view);
  const query = view.accountListQueryParams().toString();
  await view.loadAccounts();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(view.accountListQueryParams().toString(), query);
  assert.equal(view.ACCOUNTS_TOTAL, 0);
  assert.equal(requests, 1);
  assert.equal(renders, 1);
});

test('全部清除所有选项，条件标签回显全部所选值', () => {
  const {view, controls} = harness();
  const control = select();
  controls.set('accountPlanFilterV2', control);
  view.syncFacetSelect('accountPlanFilterV2', [{value: 'free', count: 2}, {value: 'unqueried', count: 3}], {group: 'plan'});
  view.setColumnFilterValue(control, 'free,unqueried');
  assert.equal(view.columnFilterDisplayValue({dataset: {filterType: 'select', columnFilter: 'accountPlanFilterV2'}}), 'Free、未查询');
  view.setColumnFilterValue(control, '');
  assert.equal(view.columnFilterValue(control), '');
  assert.equal(control.selectedOptions.length, 1);
  assert.equal(control.selectedOptions[0].value, '');
});

test('列表与轮询共用的查询参数包含每列全部选中值和分页条件', () => {
  const {view, controls} = harness();
  for (const [id, values] of [['accountPlanFilterV2', ['free', 'unqueried']], ['accountSourceFilterV2', ['outlook', 'icloud_hide']], ['accountRegistrationDriverFilterV2', ['roxy', 'protocol_oss']], ['accountCodexFilterV2', ['success', 'failed']]]) {
    const control = select();
    controls.set(id, control);
    view.syncFacetSelect(id, values.map(value => ({value, count: 1})));
    view.setColumnFilterValue(control, values.join(','));
  }
  controls.set('qAccountsV2', {value: 'example.test'});
  const params = view.accountListQueryParams();
  assert.equal(params.get('plan'), 'free,unqueried');
  assert.equal(params.get('source'), 'icloud_hide,outlook');
  assert.equal(params.get('registration_driver'), 'protocol_oss,roxy');
  assert.equal(params.get('codex'), 'failed,success');
  assert.equal(params.get('email'), 'example.test');
  assert.equal(params.get('page'), '2');
});

test('注册驱动选项与显示名一致，包含未记录，多选回显且同步后保留条件', () => {
  const {view, controls} = harness();
  const control = select();
  controls.set('accountRegistrationDriverFilterV2', control);
  const rows = ['roxy', 'roxy_oss', 'protocol', 'protocol_oss', 'protocol_oss_2', 'cloakbrowser', 'unknown'].map(value => ({value, count: 1}));
  view.syncFacetSelect('accountRegistrationDriverFilterV2', rows, {group: 'registration_driver'});
  assert.deepEqual(control.options.map(option => option.textContent), ['全部', 'roxy · 1', 'roxy-public · 1', 'proto-local · 1', 'proto-public · 1', 'proto-sso · 1', 'CloakBrowser（历史） · 1', '未记录 · 1']);
  assert.equal(view.accountRegistrationDriverLabel(' CLOAKBROWSER '), 'CloakBrowser（历史）');
  view.setColumnFilterValue(control, 'cloakbrowser,protocol_oss,unknown');
  assert.equal(view.columnFilterDisplayValue({dataset: {filterType: 'select', columnFilter: 'accountRegistrationDriverFilterV2'}}), 'proto-public、CloakBrowser（历史）、未记录');
  view.syncFacetSelect('accountRegistrationDriverFilterV2', rows.slice().reverse(), {group: 'registration_driver'});
  assert.equal(view.columnFilterValue(control), 'cloakbrowser,protocol_oss,unknown');
});

test('切换注册驱动筛选后，接口返回前不继续展示上一次的行', async () => {
  const {view} = harness();
  const body = {innerHTML: '<tr><td>proto-sso</td></tr>'};
  let resolveApi;
  view.$ = () => body;
  view.accountListQueryParams = () => new URLSearchParams('registration_driver=unknown');
  view.PAGERS = {accounts: {page: 1, size: 20}};
  view.accountsLoading = false;
  view.accountsReloadQueued = false;
  view.accountsRenderedQuery = 'registration_driver=protocol_oss_2';
  view.api = () => new Promise(resolve => { resolveApi = resolve; });
  view.setListBusy = () => {};
  view.showAccountSearchError = () => {};
  view.renderAccountSearchTerms = () => {};
  view.syncFacetSelect = () => {};
  view.renderAccounts = () => {};
  view.markViewReady = () => {};
  view.renderTableStateRow = (_columns, title) => title;
  vm.runInContext(functionSource(accounts, 'showAccountsLoadingState'), view);
  vm.runInContext(`async ${functionSource(accounts, 'loadAccounts')}`, view);

  const pending = view.loadAccounts();
  const bodyWhileLoading = body.innerHTML;
  resolveApi({items: [], total: 0, facets: {}});
  await pending;

  assert.equal(bodyWhileLoading, '正在加载筛选结果…');

  body.innerHTML = '<tr><td>未记录结果</td></tr>';
  view.api = () => Promise.resolve({items: [], total: 0, facets: {}});
  const refresh = view.loadAccounts();
  const bodyWhileRefreshing = body.innerHTML;
  await refresh;
  assert.equal(bodyWhileRefreshing, '<tr><td>未记录结果</td></tr>');
});

test('套餐为空时与筛选统一显示未查询，有旧套餐时沿用旧值', () => {
  const {view} = harness();
  Object.assign(view, {_fmtPlanTime: () => '', _billingLabel: () => '', _discountLabel: () => ''});
  vm.runInContext(functionSource(accounts, '_planCell'), view);
  assert.match(view._planCell({}), />未查询<\/span>/);
  assert.match(view._planCell({current_plan_type: ' ', plan_type: 'free'}), />free<\/span>/);
});
