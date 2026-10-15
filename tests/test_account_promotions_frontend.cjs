const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/accounts.js'), 'utf8');
const promotionSource = source.slice(source.indexOf('function _plusPromotionKind('), source.indexOf('function _planAction('));

function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `应提供 ${name}`);
  const next = source.slice(start + 1).search(/\n(?:async )?function /);
  return source.slice(start, next < 0 ? undefined : start + 1 + next);
}

const view = {
  esc: value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char])),
  accountIsDeactivated: () => false,
  _liveCheckHttpStatus: () => null,
  _tokenDisplayState: () => ({key: 'missing'}),
  _fmtPlanTime: value => value || '',
  _accountDetailFingerprintMarkup: () => '',
  facetLabel: (_group, value) => value || '',
};
vm.createContext(view);
vm.runInContext([
  promotionSource,
  functionSource('_extractLinkAction'),
  functionSource('_accountDetailState'),
  functionSource('_accountCountryDetailMarkup'),
  functionSource('_accountDetailAuthMethod'),
  functionSource('_accountDetailMarkup'),
  functionSource('accountTaskResultText'),
].join('\n'), view);

const goTrial = {plan: 'go', kind: 'free_trial', eligible: true, duration_num_periods: 1, duration_period: 'month', campaign_id: 'go-free-one'};
const plusDiscount = {plan: 'plus', kind: 'discount', eligible: true, discount_percentage: 50, duration_num_periods: 2, duration_period: 'month', campaign_id: 'plus-half-two'};
const checked = {id: 1, current_plan_type: 'free', plan_check_status: 'success', account_promotions: [goTrial, plusDiscount]};

function visiblePromotionLabels(html) {
  return [...html.matchAll(/<span class="account-promotion-label">([^<]*)<\/span>/g)].map(match => match[1]);
}

function promotionTooltip(html) {
  return [...html.matchAll(/data-accounts-tooltip="([^"]*)"/g)].map(match => match[1]).join('\n');
}

function assertSinglePromotion(html, expected) {
  assert.deepEqual(visiblePromotionLabels(html), [expected], '列表只显示最高优惠或一个状态');
  assert.equal((html.match(/class="pill /g) || []).length, 1);
  assert.equal((html.match(/tabindex="0"/g) || []).length, 1);
  assert.equal((html.match(/data-accounts-tooltip=/g) || []).length, 1);
}

function tooltipAfterTableScroll({focused = true, left = 40} = {}) {
  const listeners = new Map();
  const tip = {hidden: false, left: 0, contains: () => false};
  const target = {
    closest: selector => selector === '.col-trial' ? {} : null,
    getBoundingClientRect: () => ({left, right: left + 80, top: 90, bottom: 116}),
  };
  const context = {
    document: {activeElement: focused ? target : null, addEventListener() {}},
    window: {innerWidth: 390, innerHeight: 844, addEventListener: (name, callback) => listeners.set(name, callback)},
    _accountsTooltipTarget: target,
    _accountsTooltipNode: tip,
    _hideAccountsTooltip: () => { tip.hidden = true; },
    _showAccountsTooltip: element => { tip.hidden = false; tip.left = element.getBoundingClientRect().left; },
  };
  const start = source.indexOf('(function bindAccountsHoverTooltips()');
  const end = source.indexOf('})();', start) + '})();'.length;
  vm.runInNewContext(source.slice(start, end), context);
  listeners.get('scroll')({target: {className: 'accounts-table-v2-wrap'}});
  return tip;
}

test('聚焦国家优惠后表格自动横向滚动，提示保持打开并按新位置定位', () => {
  const tip = tooltipAfterTableScroll();
  assert.equal(tip.hidden, false);
  assert.equal(tip.left, 40);
});

test('未聚焦优惠或优惠已滚出可见区域时，表格滚动关闭提示', () => {
  assert.equal(tooltipAfterTableScroll({focused: false}).hidden, true);
  assert.equal(tooltipAfterTableScroll({left: -100}).hidden, true);
});

test('列表只显示 Go 免费最高优惠，悬停和键盘焦点可查看 Go 与 Plus 全部优惠', () => {
  const html = view._promotionCell(checked);
  assertSinglePromotion(html, 'Go: 免费 1个月');
  const tooltip = promotionTooltip(html);
  assert.match(tooltip, /Go: 免费 1个月/);
  assert.match(tooltip, /Plus: 五折 2个月/);
  assert.match(tooltip, /go-free-one/);
  assert.match(tooltip, /plus-half-two/);
});

test('旧 Plus 快照展示其优惠，提示中的 Go 保留待查询而不误判无优惠', () => {
  const html = view._promotionCell({current_plan_type: 'free', plan_check_status: 'success', plus_promo_kind: 'discount', plus_promo_discount_percentage: 50, plus_promo_duration_num_periods: 3, plus_promo_duration_period: 'month'});
  assertSinglePromotion(html, 'Plus: 五折 3个月');
  assert.match(promotionTooltip(html), /Go: 待查询/);
  assert.doesNotMatch(promotionTooltip(html), /Go: 无优惠/);
});

test('明确无优惠合并为一个状态，部分未知记录不隐藏已知优惠', () => {
  const html = view._promotionCell({...checked, account_promotions: [{plan: 'go', kind: 'none', eligible: false}, {plan: 'plus', kind: 'none', eligible: false}]});
  assertSinglePromotion(html, '无优惠');
  assert.match(promotionTooltip(html), /Go: 无优惠/);
  assert.match(promotionTooltip(html), /Plus: 无优惠/);
  const partial = view._promotionCell({...checked, account_promotions: [plusDiscount]});
  assertSinglePromotion(partial, 'Plus: 五折 2个月');
  assert.match(promotionTooltip(partial), /Go: 待核验/);
  assert.doesNotMatch(promotionTooltip(partial), /Go: 无优惠/);
});

test('未查询和排队执行中的记录只展示一个待查询状态', () => {
  for (const status of ['', 'queued', 'running']) {
    const html = view._promotionCell({...checked, plan_check_status: status});
    assertSinglePromotion(html, '待查询');
    assert.match(promotionTooltip(html), /Go: 待查询/);
    assert.match(promotionTooltip(html), /Plus: 待查询/);
  }
});

test('当前 Go 套餐不代表获得 Go 免费资格，未知活动不猜优惠类型', () => {
  const legacy = view._promotionCell({current_plan_type: 'go', plan_check_status: 'success'});
  assertSinglePromotion(legacy, '待查询');
  assert.match(promotionTooltip(legacy), /Go: 待查询/);
  assert.doesNotMatch(promotionTooltip(legacy), /Go: 免费/);
  const unknown = view._promotionCell({...checked, current_plan_type: 'go', account_promotions: [{plan: 'go', kind: 'new-structure', campaign_id: 'go-free-trial'}, plusDiscount]});
  assertSinglePromotion(unknown, 'Plus: 五折 2个月');
  assert.match(promotionTooltip(unknown), /Go: 待核验/);
  assert.doesNotMatch(promotionTooltip(unknown), /Go: 免费/);
  const unverified = view._promotionCell({...checked, account_promotions: [{plan: 'go', kind: 'new-structure'}, {plan: 'plus', kind: 'none'}]});
  assertSinglePromotion(unverified, '待核验');
});

test('失败保留上次最高优惠，提示包含完整成功快照和错误，没有快照仅显示失败', () => {
  const html = view._promotionCell({...checked, plan_check_status: 'failed', plan_last_success_at: '2026-10-12 12:00:00', plan_check_error: 'HTTP 401'});
  assertSinglePromotion(html, 'Go: 免费 1个月');
  const tooltip = promotionTooltip(html);
  assert.match(tooltip, /Go: 免费 1个月/);
  assert.match(tooltip, /Plus: 五折 2个月/);
  assert.match(tooltip, /显示上次成功快照/);
  assert.match(tooltip, /2026-10-12 12:00:00/);
  assert.match(tooltip, /本次查询失败: HTTP 401/);
  const noSnapshot = view._promotionCell({...checked, plan_check_status: 'failed', plan_check_error: 'HTTP 401'});
  assertSinglePromotion(noSnapshot, '查询失败');
  assert.match(promotionTooltip(noSnapshot), /本次查询失败: HTTP 401/);
  assert.doesNotMatch(promotionTooltip(noSnapshot), /免费/);
});

test('同一套餐多活动只显示最高优惠，提示保留全部活动并转义内容', () => {
  const other = {...goTrial, kind: 'discount', discount_percentage: 20, campaign_id: 'go-discount-other', title: '"><script>alert(1)</script>'};
  const html = view._promotionCell({...checked, account_promotions: [other, plusDiscount, goTrial]});
  assertSinglePromotion(html, 'Go: 免费 1个月');
  const tooltip = promotionTooltip(html);
  assert.match(tooltip, /Go: 免费 1个月/);
  assert.match(tooltip, /Plus: 五折 2个月/);
  assert.match(tooltip, /减 20% 1个月/);
  assert.match(tooltip, /go-discount-other/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(tooltip, /&lt;script&gt;/);
});

test('免费资格优先于长期高额折扣；折扣按减免比例选择最高优惠', () => {
  const highDiscount = {...plusDiscount, discount_percentage: 90, duration_num_periods: 1, duration_period: 'year'};
  assertSinglePromotion(view._promotionCell({...checked, account_promotions: [highDiscount, goTrial]}), 'Go: 免费 1个月');
  const goDiscount = {...goTrial, kind: 'discount', discount_percentage: 60};
  for (const offers of [[plusDiscount, goDiscount], [goDiscount, plusDiscount]]) {
    assertSinglePromotion(view._promotionCell({...checked, account_promotions: offers}), 'Go: 减 60% 1个月');
  }
});

test('同类优惠比较实际期限，年与月、月与周、周与天可以交叉选择', () => {
  const cases = [
    {kind: 'free_trial', go: [1, 'year'], plus: [11, 'month'], expected: 'Go: 免费 1年'},
    {kind: 'free_trial', go: [2, 'month'], plus: [8, 'week'], expected: 'Go: 免费 2个月'},
    {kind: 'free_trial', go: [2, 'week'], plus: [13, 'day'], expected: 'Go: 免费 2周'},
    {kind: 'discount', go: [13, 'day'], plus: [2, 'week'], expected: 'Plus: 五折 2周'},
  ];
  for (const item of cases) {
    const go = {...goTrial, kind: item.kind, discount_percentage: 50, duration_num_periods: item.go[0], duration_period: item.go[1]};
    const plus = {...plusDiscount, kind: item.kind, duration_num_periods: item.plus[0], duration_period: item.plus[1]};
    assertSinglePromotion(view._promotionCell({...checked, account_promotions: [go, plus]}), item.expected);
  }
  const longerGo = {...goTrial, duration_num_periods: 3, campaign_id: 'go-free-three'};
  assertSinglePromotion(view._promotionCell({...checked, account_promotions: [goTrial, plusDiscount, longerGo]}), 'Go: 免费 3个月');
});

test('类型、折扣和期限同等时优先 Plus，选择不依赖接口活动顺序', () => {
  for (const kind of ['free_trial', 'discount']) {
    const go = {...goTrial, kind, discount_percentage: 50};
    const plus = {...plusDiscount, kind, duration_num_periods: 1};
    const expected = kind === 'free_trial' ? 'Plus: 免费 1个月' : 'Plus: 五折 1个月';
    for (const offers of [[go, plus], [plus, go]]) {
      assertSinglePromotion(view._promotionCell({...checked, account_promotions: offers}), expected);
    }
  }
});

test('Go 免费资格不开放 Plus 提链，原确认 Plus 免费资格仍可提链', () => {
  assert.equal(view._extractLinkAction({...checked, plus_promo_kind: 'discount'}), '');
  assert.equal(view._extractLinkAction({...checked, plus_promo_kind: 'none'}), '');
  assert.match(view._extractLinkAction({...checked, plus_promo_kind: 'free_trial', plus_trial_eligible: true}), /data-extract-link/);
});

test('账号详情和查询任务结果同步展示 Go 与 Plus 优惠', () => {
  const drawer = view._accountDetailMarkup({...checked, plan_check_status: 'failed', plan_last_success_at: '2026-10-12 12:00:00', plan_check_error: 'HTTP 403'});
  assert.match(drawer, /Go 优惠/);
  assert.match(drawer, /Plus 优惠/);
  assert.match(drawer, /Go: 免费 1个月/);
  assert.match(drawer, /Plus: 五折 2个月/);
  assert.match(drawer, /本次查询失败: HTTP 403/);
  const result = view.accountTaskResultText({task_type: 'plan_check', status: 'success', result_summary: checked});
  assert.equal(result, '套餐 free · Go: 免费 1个月 · Plus: 五折 2个月');
});

test('多国查询列表逐国显示最高优惠，并在提示中保留该国 Go 与 Plus 活动', () => {
  const html = view._promotionCell({
    plan_check_status: 'success',
    plan_check_countries: ['JP', 'VN'],
    plan_check_country_results: [
      {country: 'JP', status: 'success', checked_at: '2026-10-15 09:00:00', result: {
        account_promotions: [goTrial, plusDiscount],
      }},
      {country: 'VN', status: 'failed', error: 'HTTP 403', last_success_at: '2026-10-14 10:00:00', result: {
        account_promotions: [{plan: 'go', kind: 'discount', discount_percentage: 20, duration_num_periods: 1, duration_period: 'month', campaign_id: 'vn-old'}],
      }},
    ],
  });
  assert.match(html, /JP/);
  assert.match(html, /VN/);
  assert.match(html, /Go: 免费 1个月/);
  assert.match(html, /减 20% 1个月/);
  assert.match(html, /VN[^<]*上次成功快照|上次成功快照[^<]*VN/);
  assert.match(html, /HTTP 403/);
  assert.equal((html.match(/class="pill /g) || []).length, 2);
  assert.equal((html.match(/data-accounts-tooltip=/g) || []).length, 2);
});

test('多国查询初次失败没有快照时不显示无优惠', () => {
  const html = view._promotionCell({
    plan_check_status: 'failed',
    plan_check_partial: true,
    plan_check_country_results: [
      {country: 'IN', status: 'failed', error: '没有可用线路'},
    ],
  });
  assert.match(html, /IN/);
  assert.match(html, /查询失败/);
  assert.doesNotMatch(html, /无优惠/);
  assert.match(html, /没有可用线路/);
});

test('多国详情和任务摘要展示完整国家结果与成功总数', () => {
  const account = {
    id: 8,
    current_plan_type: 'free',
    plan_check_status: 'success',
    plan_check_partial: true,
    plan_check_country_results: [
      {country: 'JP', status: 'success', checked_at: '2026-10-15 09:00:00', result: {account_promotions: [goTrial]}},
      {country: 'VN', status: 'failed', error: 'HTTP 429', last_success_at: '2026-10-14 09:00:00', result: {account_promotions: [{plan: 'plus', kind: 'free_trial', duration_num_periods: 1, duration_period: 'month'}]}},
      {country: 'IN', status: 'cancelled', error: '已取消'},
    ],
  };
  const drawer = view._accountDetailMarkup(account);
  assert.match(drawer, /JP 优惠/);
  assert.match(drawer, /VN 优惠/);
  assert.match(drawer, /IN 优惠/);
  assert.match(drawer, /HTTP 429/);
  const result = view.accountTaskResultText({task_type: 'plan_check', status: 'success', result_summary: account});
  assert.match(result, /1\/3/);
  assert.match(result, /部分失败/);
});

test('任务摘要只有多国汇总字段时仍按国家计数并展示带国家的优惠', () => {
  const result = view.accountTaskResultText({task_type: 'plan_check', status: 'success', result_summary: {
    current_plan_type: 'free',
    plan_check_countries: ['JP', 'VN', 'IN'],
    plan_check_partial: true,
    country_success_count: 1,
    country_total_count: 3,
    failed_countries: ['VN', 'IN'],
    account_promotions: [
      {...goTrial, country: 'JP'},
      {plan: 'plus', kind: 'discount', discount_percentage: 20, country: 'VN', stale: true},
    ],
  }});
  assert.match(result, /1\/3/);
  assert.match(result, /部分失败/);
  assert.match(result, /JP/);
  assert.match(result, /VN/);
  assert.match(result, /Go: 免费/);
});

test('空国家列表且国家计数为 null 时，单次任务摘要不误显示 0/0 国家查询', () => {
  const result = view.accountTaskResultText({task_type: 'plan_check', status: 'success', result_summary: {
    ok: true,
    current_plan_type: 'free',
    plan_check_countries: [],
    country_total_count: null,
    country_success_count: null,
    account_promotions: [goTrial, plusDiscount],
  }});
  assert.equal(result, '套餐 free · Go: 免费 1个月 · Plus: 五折 2个月');
  assert.doesNotMatch(result, /国家查询/);
});

test('所有国家失败时详情显示全部失败，查询中断不会显示绿色成功', () => {
  const allFailed = view._accountDetailMarkup({
    current_plan_type: 'free', plan_check_partial: true,
    plan_check_country_results: [
      {country: 'JP', status: 'failed', error: 'HTTP 403'},
      {country: 'VN', status: 'failed', error: '无线路'},
    ],
  });
  assert.match(allFailed, /全部失败/);
  assert.doesNotMatch(allFailed, /部分失败/);

  const interrupted = view._accountDetailMarkup({
    current_plan_type: 'free', plan_check_status: 'failed', plan_check_partial: true,
    plan_check_country_results: [{country: 'IN', status: 'running'}],
  });
  assert.match(interrupted, /查询中断/);
  assert.doesNotMatch(interrupted, /多国套餐检查[\s\S]*已完成/);
});

test('新任务排队时旧国家成功快照标记历史并提示新任务排队', () => {
  const html = view._promotionCell({
    current_plan_type: 'free', plan_check_status: 'queued',
    plan_check_country_results: [{country: 'JP', status: 'success', checked_at: '2026-10-14 09:00:00', result: {account_promotions: [goTrial]}}],
  });
  assert.match(html, /JP/);
  assert.match(html, /历史/);
  assert.match(html, /新任务排队中/);
});

test('历史徽标与国家代码独立于可裁切优惠文案渲染', () => {
  const html = view._promotionCell({
    plan_check_country_results: [{country: 'JP', status: 'failed', error: 'HTTP 403', last_success_at: '2026-10-14', result: {account_promotions: [goTrial]}}],
  });
  assert.match(html, /class="account-promotion-country">JP<span class="account-promotion-stale">历史<\/span><\/span>/);
  assert.match(html, /class="account-promotion-label">Go: 免费 1个月<\/span>/);
});

test('明确空国家列表关闭多国时，最新单次查询不被历史国家结果覆盖', () => {
  const account = {
    current_plan_type: 'free', plan_check_status: 'success', plan_check_countries: [],
    account_promotions: [goTrial, plusDiscount],
    plan_check_country_results: [{country: 'JP', status: 'success', result: {account_promotions: [goTrial]}}],
  };
  const list = view._promotionCell(account);
  assertSinglePromotion(list, 'Go: 免费 1个月');
  assert.doesNotMatch(list, /JP/);
  const detail = view._accountDetailMarkup(account);
  assert.match(detail, /Go 优惠/);
  assert.doesNotMatch(detail, /JP 优惠/);
});

function createResizableAccountTable(savedWidths = null) {
  const template = fs.readFileSync(path.join(__dirname, '../webui/templates/index.html'), 'utf8');
  const tableSource = template.slice(template.indexOf('<table class="accounts-table-v2"'));
  const colgroup = tableSource.slice(tableSource.indexOf('<colgroup>'), tableSource.indexOf('</colgroup>'));
  const columnClasses = [...colgroup.matchAll(/<col class="([^"]+)"/g)].map(match => match[1]);
  const columns = columnClasses.map(() => ({style: {}}));
  const headers = columnClasses.map(value => ({classList: {contains: name => value.split(' ').includes(name)}, appendChild() {}}));
  const table = {dataset: {resizableTable: 'accounts'}, querySelectorAll: selector => selector === 'colgroup col' ? columns : headers};
  const storageKey = 'gpt_console_table_widths_accounts';
  const storage = new Map(savedWidths ? [[storageKey, JSON.stringify(savedWidths)]] : []);
  const sandbox = {
    localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value)},
    document: {createElement: () => ({setAttribute() {}, addEventListener() {}})},
  };
  const common = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');
  vm.createContext(sandbox);
  vm.runInContext(common.slice(common.indexOf('const TABLE_DEFAULT_WIDTHS ='), common.indexOf('function initResizableTables(')), sandbox);
  sandbox.initResizableTable(table);
  return {columns, promotionIndex: columnClasses.indexOf('col-trial'), storage, storageKey};
}

test('默认列宽按真实 colgroup 应用，1280px 表格给套餐优惠至少 120px 内容空间', () => {
  const {columns, promotionIndex} = createResizableAccountTable();
  assert.ok(promotionIndex >= 0, '账号表格应包含套餐优惠列');
  assert.ok(columns.every(column => Number.parseFloat(column.style.width) > 0), '默认列宽应覆盖所有真实表格列');
  const contentWidth = 1280 * Number.parseFloat(columns[promotionIndex].style.width) / 100 - 12;
  assert.ok(contentWidth >= 120, `套餐优惠内容空间不足: ${contentWidth}px`);
});

test('扩大默认套餐优惠列不覆盖用户已经保存的列宽', () => {
  const saved = Array(15).fill(10);
  saved[9] = 7;
  const {columns, promotionIndex, storage, storageKey} = createResizableAccountTable(saved);
  const expected = saved[promotionIndex] / saved.reduce((sum, value) => sum + value, 0) * 100;
  assert.equal(Number.parseFloat(columns[promotionIndex].style.width), expected);
  assert.equal(storage.get(storageKey), JSON.stringify(saved));
});
