const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const common = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');
const accounts = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/accounts.js'), 'utf8');
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
    LIST_FACET_LABELS: {}, URLSearchParams,
    esc: value => String(value), attrEsc: value => String(value),
    refreshColumnFilterState() {}, renderColumnFilterOptions() {},
    SHOW_ARCHIVED_ACCOUNTS: false, SHOW_PLUS_ACCOUNTS_ONLY: false,
    accountAdvancedSearchQuery: '', PAGERS: {accounts: {page: 2, size: 20}},
  };
  vm.createContext(view);
  vm.runInContext(common.slice(common.indexOf('function facetLabel('), common.indexOf('// ---------- 分页状态 ----------')), view);
  vm.runInContext([functionSource(common, 'columnFilterDisplayValue'), functionSource(accounts, 'getAccountsQuery'), functionSource(accounts, 'accountListQueryParams')].join('\n'), view);
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
  for (const [id, values] of [['accountPlanFilterV2', ['free', 'unqueried']], ['accountSourceFilterV2', ['outlook', 'icloud_hide']], ['accountCodexFilterV2', ['success', 'failed']]]) {
    const control = select();
    controls.set(id, control);
    view.syncFacetSelect(id, values.map(value => ({value, count: 1})));
    view.setColumnFilterValue(control, values.join(','));
  }
  controls.set('qAccountsV2', {value: 'example.test'});
  const params = view.accountListQueryParams();
  assert.equal(params.get('plan'), 'free,unqueried');
  assert.equal(params.get('source'), 'icloud_hide,outlook');
  assert.equal(params.get('codex'), 'failed,success');
  assert.equal(params.get('email'), 'example.test');
  assert.equal(params.get('page'), '2');
});

test('套餐为空时与筛选统一显示未查询，有旧套餐时沿用旧值', () => {
  const {view} = harness();
  Object.assign(view, {_fmtPlanTime: () => '', _billingLabel: () => '', _discountLabel: () => ''});
  vm.runInContext(functionSource(accounts, '_planCell'), view);
  assert.match(view._planCell({}), />未查询<\/span>/);
  assert.match(view._planCell({current_plan_type: ' ', plan_type: 'free'}), />free<\/span>/);
});
