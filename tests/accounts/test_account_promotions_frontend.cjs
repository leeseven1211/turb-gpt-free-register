const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = require('../frontend_script_sources.cjs').readAccountScripts();
const accountStyles = fs.readFileSync(path.join(__dirname, '../../webui/static/css/shared/ui-foundation.css'), 'utf8');
const modernStyles = fs.readFileSync(path.join(__dirname, '../../webui/static/css/shell.css'), 'utf8');
const commonSource = fs.readFileSync(path.join(__dirname, '../../webui/static/js/shared/common.js'), 'utf8');
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
  functionSource('_quotaWindowLabel'),
  functionSource('_quotaPercent'),
  functionSource('_quotaWindowDetail'),
  functionSource('_quotaCell'),
  functionSource('_totpCellV2'),
  functionSource('_extractLinkAction'),
  functionSource('_accountDetailState'),
  functionSource('_accountCountryDetailMarkup'),
  functionSource('_accountDetailAuthMethod'),
  functionSource('_accountDetailMarkup'),
  functionSource('accountTaskResultText'),
  functionSource('accountTaskResultTooltipText'),
  functionSource('accountTaskPlanResultMarkup'),
].join('\n'), view);

const goTrial = {plan: 'go', kind: 'free_trial', eligible: true, duration_num_periods: 1, duration_period: 'month', campaign_id: 'go-free-one'};
const plusDiscount = {plan: 'plus', kind: 'discount', eligible: true, discount_percentage: 50, duration_num_periods: 2, duration_period: 'month', campaign_id: 'plus-half-two'};
const checked = {id: 1, current_plan_type: 'free', plan_check_status: 'success', account_promotions: [goTrial, plusDiscount]};

function visiblePromotionLabels(html) {
  return [...html.matchAll(/<span class="account-promotion-label">([^<]*)<\/span>/g)].map(match => match[1]);
}

function visiblePromotionCountries(html) {
  return [...html.matchAll(/<span class="account-promotion-country">([A-Z][A-Z0-9])/g)].map(match => match[1]);
}

function promotionTooltip(html) {
  return [...html.matchAll(/data-accounts-tooltip="([^"]*)"/g)].map(match => match[1]).join('\n');
}

function promotionStructure(html) {
  const cell = html.match(/<div class="([^"]*account-promotion-cell[^"]*)">/);
  const row = html.match(/<span class="([^"]*account-promotion-country-row[^"]*)"/);
  assert.ok(cell, '优惠应使用统一 cell 容器');
  assert.ok(row, '优惠应使用统一 country row');
  return {cell: cell[1], row: row[1]};
}

function assertSinglePromotion(html, expected, visibleExpected = expected.replace(/^Plus: /, '')) {
  if (expected.startsWith('Plus: ')) {
    assert.deepEqual(visiblePromotionLabels(html), [visibleExpected]);
    assert.ok(promotionTooltip(html).startsWith(`国家未记录 ${expected}`), '浮窗首项保留所选 Plus 优惠，列表使用统一国家格式');
    assert.match(html, /class="account-promotion-country" aria-label="国家未记录">—(?:<span class="account-promotion-stale">历史<\/span>)?：/);
  } else {
    assert.deepEqual(visiblePromotionLabels(html), [expected], '列表只显示 Plus 最高优惠或一个状态');
  }
  const structure = promotionStructure(html);
  assert.match(structure.cell, /^account-promotion-cell account-promotion-cell--countries(?: account-promotion-cell--single)?$/);
  assert.match(structure.row, /^account-promotion-country-row is-(success|danger|warning|neutral)(?: |$)/);
  assert.equal((html.match(/class="pill /g) || []).length, 0, '优惠行不再使用 pill');
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
  const start = source.indexOf('function bindAccountsHoverTooltips()');
  const end = source.indexOf('\nfunction _planCell(', start);
  vm.runInNewContext(`${source.slice(start, end)}\nbindAccountsHoverTooltips();`, context);
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

test('列表与浮窗只显示所选 Plus 优惠，不展示 Go 或活动编号', () => {
  const html = view._promotionCell(checked);
  assertSinglePromotion(html, 'Plus: 五折 2个月');
  const tooltip = promotionTooltip(html);
  assert.doesNotMatch(tooltip, /Go:/);
  assert.match(tooltip, /Plus: 五折 2个月/);
  assert.doesNotMatch(tooltip, /go-free-one|plus-half-two/);
});

test('旧 Plus 快照展示其优惠，提示不添加 Go 状态', () => {
  const html = view._promotionCell({current_plan_type: 'free', plan_check_status: 'success', plus_promo_kind: 'discount', plus_promo_discount_percentage: 50, plus_promo_duration_num_periods: 3, plus_promo_duration_period: 'month'});
  assertSinglePromotion(html, 'Plus: 五折 3个月');
  assert.match(promotionTooltip(html), /Plus: 五折 3个月/);
  assert.doesNotMatch(promotionTooltip(html), /Go:/);
});

test('单国旧优惠与单国家结果统一容器和 tone，无优惠分支也保留提示焦点结构', () => {
  const plusTrial = {...goTrial, plan: 'plus'};
  const legacy = view._promotionCell({current_plan_type: 'free', plan_check_status: 'success', plan_check_countries: [], account_promotions: [goTrial, plusTrial]});
  const country = view._promotionCell({plan_check_status: 'success', plan_check_country_results: [
    {country: 'JP', status: 'success', result: {account_promotions: [goTrial, plusTrial]}},
  ]});
  assert.equal(promotionStructure(legacy).cell, promotionStructure(country).cell);
  assert.match(promotionStructure(legacy).row, /^account-promotion-country-row is-success$/);
  assert.match(promotionStructure(country).row, /^account-promotion-country-row is-success is-country-\d+$/);
  assert.match(promotionStructure(legacy).row, /is-success/);
  assert.equal((legacy.match(/class="pill /g) || []).length, 0);
  assert.equal((country.match(/class="pill /g) || []).length, 0);
  assert.equal((legacy.match(/data-accounts-tooltip=/g) || []).length, 1);
  assert.equal((country.match(/data-accounts-tooltip=/g) || []).length, 1);
  assert.equal((legacy.match(/tabindex="0"/g) || []).length, 1);
  assert.equal((country.match(/tabindex="0"/g) || []).length, 1);
  assert.match(promotionTooltip(legacy), /Plus: 免费 1个月/);
  assert.match(promotionTooltip(country), /Plus: 免费 1个月/);

  const singleNone = view._promotionCell({...checked, account_promotions: [
    {plan: 'go', kind: 'none', eligible: false}, {plan: 'plus', kind: 'none', eligible: false},
  ]});
  const multiNone = view._promotionCell({plan_check_status: 'success', plan_check_country_results: [
    {country: 'JP', status: 'success', result: {account_promotions: [goTrial, {plan: 'plus', kind: 'none'}]}},
    {country: 'VN', status: 'success', result: {account_promotions: [goTrial, {plan: 'plus', kind: 'none'}]}},
  ]});
  assert.deepEqual(promotionStructure(singleNone), promotionStructure(multiNone));
  assert.match(promotionStructure(singleNone).row, /is-neutral/);
  assert.equal((singleNone.match(/class="pill /g) || []).length, 0);
  assert.equal((multiNone.match(/class="pill /g) || []).length, 0);
  assert.equal((singleNone.match(/data-accounts-tooltip=/g) || []).length, 1);
  assert.equal((multiNone.match(/data-accounts-tooltip=/g) || []).length, 1);
  assert.equal((singleNone.match(/tabindex="0"/g) || []).length, 1);
  assert.equal((multiNone.match(/tabindex="0"/g) || []).length, 1);
  assert.match(promotionTooltip(singleNone), /Plus: 无优惠/);
  assert.doesNotMatch(promotionTooltip(singleNone), /Go:/);
  assert.match(promotionTooltip(multiNone), /JP/);
  assert.match(promotionTooltip(multiNone), /VN/);
});

test('明确无优惠合并为一个状态，部分未知记录不隐藏已知优惠', () => {
  const html = view._promotionCell({...checked, account_promotions: [{plan: 'go', kind: 'none', eligible: false}, {plan: 'plus', kind: 'none', eligible: false}]});
  assertSinglePromotion(html, '无优惠');
  assert.doesNotMatch(promotionTooltip(html), /Go:/);
  assert.match(promotionTooltip(html), /Plus: 无优惠/);
  const partial = view._promotionCell({...checked, account_promotions: [plusDiscount]});
  assertSinglePromotion(partial, 'Plus: 五折 2个月');
  assert.match(promotionTooltip(partial), /Plus: 五折 2个月/);
  assert.doesNotMatch(promotionTooltip(partial), /Go:/);
  const goOnly = view._promotionCell({...checked, account_promotions: [goTrial, {plan: 'plus', kind: 'none'}]});
  assertSinglePromotion(goOnly, '无优惠');
  assert.match(promotionTooltip(goOnly), /Plus: 无优惠/);
  assert.doesNotMatch(promotionTooltip(goOnly), /Go:/);
});

test('未查询和排队执行中的记录只展示一个待查询状态', () => {
  for (const status of ['', 'queued', 'running']) {
    const html = view._promotionCell({...checked, plan_check_status: status, plan_check_queued_at: '2026-10-16 09:00:00', plan_check_started_at: '2026-10-16 09:01:00'});
    assertSinglePromotion(html, '待查询');
    assert.match(promotionTooltip(html), /Plus: 待查询/);
    assert.doesNotMatch(promotionTooltip(html), /Go:|2026-10-16/);
    if (status === 'queued') assert.match(promotionTooltip(html), /排队中/);
    if (status === 'running') assert.match(promotionTooltip(html), /正在执行|查询中/);
  }
});

test('当前 Go 套餐不代表获得 Go 免费资格，未知活动不猜优惠类型', () => {
  const legacy = view._promotionCell({current_plan_type: 'go', plan_check_status: 'success'});
  assertSinglePromotion(legacy, '无优惠');
  assert.doesNotMatch(promotionTooltip(legacy), /Go:/);
  const unknown = view._promotionCell({...checked, current_plan_type: 'go', account_promotions: [{plan: 'go', kind: 'new-structure', campaign_id: 'go-free-trial'}, plusDiscount]});
  assertSinglePromotion(unknown, 'Plus: 五折 2个月');
  assert.match(promotionTooltip(unknown), /Plus: 五折 2个月/);
  assert.doesNotMatch(promotionTooltip(unknown), /Go:/);
  const unverified = view._promotionCell({...checked, account_promotions: [{plan: 'go', kind: 'new-structure'}, {plan: 'plus', kind: 'none'}]});
  assertSinglePromotion(unverified, '无优惠');
  assertSinglePromotion(view._promotionCell({...checked, account_promotions: [goTrial]}), '待查询');
});

test('失败保留上次 Plus 优惠与错误，提示省略成功快照时间，没有快照仅显示失败', () => {
  const html = view._promotionCell({...checked, plan_check_status: 'failed', plan_last_success_at: '2026-10-12 12:00:00', plan_check_error: 'HTTP 401'});
  assertSinglePromotion(html, 'Plus: 五折 2个月');
  assert.match(html, /class="account-promotion-stale">历史<\/span>/);
  const tooltip = promotionTooltip(html);
  assert.doesNotMatch(tooltip, /Go:/);
  assert.match(tooltip, /Plus: 五折 2个月/);
  assert.match(tooltip, /显示上次成功快照/);
  assert.doesNotMatch(tooltip, /2026-10-12 12:00:00/);
  assert.match(tooltip, /本次查询失败: HTTP 401/);
  const noSnapshot = view._promotionCell({...checked, plan_check_status: 'failed', plan_check_error: 'HTTP 401'});
  assertSinglePromotion(noSnapshot, '查询失败');
  assert.match(promotionTooltip(noSnapshot), /本次查询失败: HTTP 401/);
  assert.doesNotMatch(promotionTooltip(noSnapshot), /免费/);
  const cancelled = view._promotionCell({...checked, plan_check_status: 'cancelled', plan_checked_at: '2026-10-12 12:00:00'});
  assert.match(promotionTooltip(cancelled), /本次查询已取消/);
  assert.doesNotMatch(promotionTooltip(cancelled), /Go:|2026-10-12/);
});

test('同一套餐多活动只显示最高 Plus 优惠，提示省略其他活动原始内容', () => {
  const other = {...goTrial, kind: 'discount', discount_percentage: 20, campaign_id: 'go-discount-other', title: '"><script>alert(1)</script>'};
  const html = view._promotionCell({...checked, account_promotions: [other, plusDiscount, goTrial]});
  assertSinglePromotion(html, 'Plus: 五折 2个月');
  const tooltip = promotionTooltip(html);
  assert.doesNotMatch(tooltip, /Go:/);
  assert.match(tooltip, /Plus: 五折 2个月/);
  assert.doesNotMatch(tooltip, /减 20% 1个月|go-discount-other/);
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(tooltip, /&lt;script&gt;|alert\(1\)/);
});

test('同一套餐的免费资格优先于长期高额折扣，多个 Plus 折扣按减免比例选择', () => {
  const highDiscount = {...plusDiscount, discount_percentage: 90, duration_num_periods: 1, duration_period: 'year'};
  const plusTrial = {...goTrial, plan: 'plus'};
  assertSinglePromotion(view._promotionCell({...checked, account_promotions: [highDiscount, goTrial]}), 'Plus: 减 90% 1年');
  assertSinglePromotion(view._promotionCell({...checked, account_promotions: [highDiscount, plusTrial]}), 'Plus: 免费 1个月', '免费');
  const largerDiscount = {...plusTrial, kind: 'discount', discount_percentage: 60};
  for (const offers of [[plusDiscount, largerDiscount], [largerDiscount, plusDiscount]]) {
    assertSinglePromotion(view._promotionCell({...checked, account_promotions: offers}), 'Plus: 减 60% 1个月');
  }
});

test('同类优惠比较实际期限，年与月、月与周、周与天可以交叉选择', () => {
  const cases = [
    {kind: 'free_trial', go: [1, 'year'], plus: [11, 'month'], expected: 'Plus: 免费 1年'},
    {kind: 'free_trial', go: [2, 'month'], plus: [8, 'week'], expected: 'Plus: 免费 2个月'},
    {kind: 'free_trial', go: [2, 'week'], plus: [13, 'day'], expected: 'Plus: 免费 2周'},
    {kind: 'discount', go: [13, 'day'], plus: [2, 'week'], expected: 'Plus: 五折 2周'},
  ];
  for (const item of cases) {
    const go = {...goTrial, plan: 'plus', kind: item.kind, discount_percentage: 50, duration_num_periods: item.go[0], duration_period: item.go[1]};
    const plus = {...plusDiscount, kind: item.kind, duration_num_periods: item.plus[0], duration_period: item.plus[1]};
    assertSinglePromotion(view._promotionCell({...checked, account_promotions: [go, plus]}), item.expected, item.kind === 'free_trial' ? '免费' : undefined);
  }
  const longerPlus = {...goTrial, plan: 'plus', duration_num_periods: 3, campaign_id: 'plus-free-three'};
  assertSinglePromotion(view._promotionCell({...checked, account_promotions: [goTrial, plusDiscount, longerPlus]}), 'Plus: 免费 3个月', '免费');
});

test('类型、折扣和期限同等时优先 Plus，选择不依赖接口活动顺序', () => {
  for (const kind of ['free_trial', 'discount']) {
    const go = {...goTrial, kind, discount_percentage: 50};
    const plus = {...plusDiscount, kind, duration_num_periods: 1};
    const expected = kind === 'free_trial' ? 'Plus: 免费 1个月' : 'Plus: 五折 1个月';
    for (const offers of [[go, plus], [plus, go]]) {
      assertSinglePromotion(view._promotionCell({...checked, account_promotions: offers}), expected, kind === 'free_trial' ? '免费' : undefined);
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

test('列表浮窗省略多语言原文活动与成功时间，账号详情仍保留完整来源信息', () => {
  const plus = {
    ...goTrial, plan: 'plus', campaign_id: 'plus-source-fixture',
    title: 'Try Plus free for 1 month',
    summary: 'Bạn có mã khuyến mãi giảm giá cho Plus trong 1 tháng.',
    payment_method_types: ['card', 'link'],
  };
  const single = {...checked, plan_promotion_country: 'JP', plan_checked_at: '2026-10-16 09:00:00', account_promotions: [goTrial, plus]};
  const multi = {...single, plan_check_country_results: [
    {country: 'JP', status: 'success', checked_at: single.plan_checked_at, result: {account_promotions: [goTrial, plus]}},
    {country: 'VN', status: 'success', checked_at: single.plan_checked_at, result: {account_promotions: [goTrial, {...plus, payment_method_types: ['upi']}]}},
  ]};
  for (const account of [single, multi]) {
    const tooltip = promotionTooltip(view._promotionCell(account));
    assert.match(tooltip, /Plus: 免费 1个月/);
    assert.match(tooltip, /支付方式: 银行卡 Link/);
    assert.doesNotMatch(tooltip, /实际应付|结账会话/);
    assert.doesNotMatch(tooltip, /Go:|Try Plus|Bạn có|plus-source-fixture|go-free-one|2026-10-16|查询于/);
    const drawer = view._accountDetailMarkup(account);
    assert.match(drawer, /Go: 免费 1个月/);
    assert.match(drawer, /Try Plus free for 1 month/);
    assert.match(drawer, /Bạn có mã khuyến mãi/);
    assert.match(drawer, /活动 plus-source-fixture/);
    assert.match(drawer, /支付方式: 银行卡 Link/);
    assert.match(drawer, /2026-10-16 09:00:00/);
  }
  assert.doesNotMatch(visiblePromotionLabels(view._promotionCell(multi)).join(' '), /银行卡|\bUPI\b|\bLink\b/);
  assert.match(promotionTooltip(view._promotionCell(multi)), /VN Plus: 免费 1个月；支付方式: UPI/);
});

test('多国查询只显示各国 Plus 优惠，浮窗保留历史与错误但省略 Go 和成功时间', () => {
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
  assert.match(promotionTooltip(html), /Plus: 五折 2个月/);
  assert.doesNotMatch(promotionTooltip(html), /Go:|减 20% 1个月|vn-old|2026-10-15|2026-10-14/);
  assert.match(promotionTooltip(html), /VN（历史）/);
  assert.match(html, /HTTP 403/);
  assert.equal((html.match(/class="account-promotion-country-row /g) || []).length, 2);
  assert.equal((html.match(/data-accounts-tooltip=/g) || []).length, 2);
  assert.deepEqual(visiblePromotionLabels(html), ['五折 2个月', '待查询']);
  assert.match(html, /class="account-promotion-country">JP：/);
});

test('多国部分完成时历史国家的失败与取消状态不依赖错误字段', () => {
  const html = view._promotionCell({
    plan_check_status: 'success', plan_check_partial: true,
    plan_check_country_results: [
      {country: 'JP', status: 'failed', last_success_at: '2026-10-15 09:00:00', result: {account_promotions: [plusDiscount]}},
      {country: 'VN', status: 'cancelled', last_success_at: '2026-10-15 09:00:00', result: {account_promotions: [{...goTrial, plan: 'plus'}]}},
    ],
  });
  const tooltip = promotionTooltip(html);
  assert.match(tooltip, /JP（历史） Plus: 五折 2个月[^\n]*\n本次查询失败: 未知错误/);
  assert.match(tooltip, /VN（历史） Plus: 免费 1个月[^\n]*\n本次查询已取消/);
  assert.doesNotMatch(tooltip, /2026-10-15|Go:/);
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

test('国家行显示精简 Plus 优惠，浮窗保留各国真实支付方式', () => {
  const html = view._promotionCell({plan_check_status: 'success', plan_check_country_results: [
    {country: 'JP', status: 'success', result: {account_promotions: [
      {...goTrial, payment_method_types: ['upi']},
      {...goTrial, plan: 'plus', payment_method_types: ['card', 'link', 'CARD', '', null]},
    ]}},
    {country: 'IN', status: 'success', result: {account_promotions: [
      {...plusDiscount, duration_num_periods: 3, payment_method_types: ['card', 'link', 'upi']},
    ]}},
    {country: 'VN', status: 'success', result: {account_promotions: [
      {...goTrial, payment_method_types: ['upi']}, {...goTrial, plan: 'plus'},
    ]}},
  ]});
  assert.match(html, /class="account-promotion-country">JP：<\/span>/);
  assert.deepEqual(visiblePromotionCountries(html), ['JP', 'IN']);
  assert.doesNotMatch(html, /另 \d+ 国|account-promotion-country-summary/);
  assert.deepEqual(visiblePromotionLabels(html), ['免费', '五折 3个月']);
  assert.doesNotMatch(promotionTooltip(html), /Go:/);
  assert.match(promotionTooltip(html), /Plus: 五折 3个月/);
  assert.doesNotMatch(visiblePromotionLabels(html).join(' '), /银行卡|\bUPI\b|\bLink\b|实际应付|结账会话/);
  assert.match(promotionTooltip(html), /JP Plus: 免费 1个月；支付方式: 银行卡 Link/);
  assert.match(promotionTooltip(html), /IN Plus: 五折 3个月；支付方式: 银行卡 Link UPI/);
  assert.match(promotionTooltip(html), /VN Plus: 免费 1个月；支付方式: 待查询/);
});

test('所有国家 Plus 无优惠合并显示，浮窗仍显示各国 Plus 状态且省略 Go', () => {
  const country = (code, plus) => ({country: code, status: 'success', result: {account_promotions: [goTrial, plus]}});
  const none = {plan: 'plus', kind: 'none'};
  const countries = [country('JP', none), country('VN', none)];
  const html = view._promotionCell({plan_check_status: 'success', plan_check_country_results: countries});
  assertSinglePromotion(html, '无优惠');
  assert.match(promotionTooltip(html), /JP/);
  assert.match(promotionTooltip(html), /VN/);
  assert.match(promotionTooltip(html), /Plus: 无优惠/);
  assert.doesNotMatch(promotionTooltip(html), /Go:/);
  const mixed = view._promotionCell({plan_check_status: 'success', plan_check_country_results: [...countries, country('IN', plusDiscount)]});
  assert.deepEqual(visiblePromotionLabels(mixed), ['五折 2个月']);
  assert.doesNotMatch(mixed, /class="account-promotion-country">(?:JP|VN)/);
  assert.match(promotionTooltip(mixed), /VN/);
});

test('各国尚未查询只显示待查询，未知 Plus 不受 Go 免费影响', () => {
  const pending = view._promotionCell({plan_check_country_results: [
    {country: 'JP', status: 'queued'}, {country: 'VN', status: 'running'},
  ]});
  assertSinglePromotion(pending, '待查询');
  const unknown = view._promotionCell({plan_check_status: 'success', plan_check_country_results: [
    {country: 'JP', status: 'success', result: {account_promotions: [goTrial]}},
  ]});
  assertSinglePromotion(unknown, '待查询');
  assert.match(promotionTooltip(unknown), /Plus: 待核验|Plus: 待查询/);
  assert.doesNotMatch(promotionTooltip(unknown), /Go:/);
});

test('折扣期限以优惠摘要显示，非法支付方式代码不进入套餐优惠列', () => {
  const cases = [
    [{duration_num_periods: 3, duration_period: 'month'}, '五折 3个月'],
    [{duration_num_periods: 2, duration_period: 'week'}, '五折 2周'],
    [{duration_num_periods: 3, duration_period: ''}, '五折'],
    [{duration_num_periods: null}, '五折'],
    [{discount_percentage: null, duration_num_periods: null}, '折扣'],
  ];
  for (const [fields, heading] of cases) {
    const html = view._promotionCell({plan_check_country_results: [{country: 'JP', status: 'success', result: {account_promotions: [
      {...plusDiscount, ...fields, payment_method_types: ['<img src=x onerror=alert(1)>']},
    ]}}]});
    assert.ok(html.includes('class="account-promotion-country">JP：'));
    assert.doesNotMatch(html, /<img/);
    assert.doesNotMatch(html, /onerror|&lt;img/);
    assert.doesNotMatch(html, /银行卡|\bUPI\b|\bLink\b/);
    assert.deepEqual(visiblePromotionLabels(html), [heading]);
  }
});

test('国家行只显示优惠摘要，浮窗保留结账预检详情', () => {
  const country = (code, offer) => ({country: code, status: 'success', result: {account_promotions: [
    {...goTrial, checkout_status: 'success', session_type: 'cs_live', payment_method_types: ['upi']}, offer,
  ]}});
  const html = view._promotionCell({plan_check_status: 'success', plan_check_country_results: [
    country('JP', {...goTrial, plan: 'plus', checkout_status: 'success', checkout_country: 'JP', session_type: 'oaics', payment_method_types: ['card', 'link'], checkout_amount_due_minor: 0, checkout_currency: 'jpy', checkout_currency_exponent: 0}),
    country('IN', {...plusDiscount, checkout_status: 'success', checkout_country: 'IN', session_type: 'cs_live', payment_method_types: ['card', 'upi'], checkout_amount_due_minor: 99900, checkout_currency: 'inr', checkout_currency_exponent: 2}),
  ]});
  assert.deepEqual(visiblePromotionLabels(html), ['免费', '五折 2个月']);
  assert.match(html, /class="account-promotion-country">JP：/);
  assert.match(html, /class="account-promotion-country">IN：/);
  assert.match(promotionTooltip(html), /Plus: 免费 1个月/);
  assert.match(promotionTooltip(html), /Plus: 五折 2个月/);
  assert.doesNotMatch(visiblePromotionLabels(html).join(' '), /0 JPY|999 INR|oaics|cs_live|银行卡|\bUPI\b|\bLink\b/);
  assert.match(promotionTooltip(html), /JP Plus: 免费 1个月；实际应付: 0 JPY；结账会话: oaics；支付方式: 银行卡 Link/);
  assert.match(promotionTooltip(html), /IN Plus: 五折 2个月；实际应付: 999 INR；结账会话: cs_live；支付方式: 银行卡 UPI/);
  assert.equal((html.match(/tabindex="0"/g) || []).length, 2);
  assert.doesNotMatch(html, /class="pill /);
});

test('价格与支付字段不影响套餐优惠摘要', () => {
  const amountLabel = (amount, currency, exponent) => visiblePromotionLabels(view._promotionCell({
    ...checked, account_promotions: [{...plusDiscount, checkout_status: 'success', session_type: 'oaics', payment_method_types: ['card'], checkout_amount_due_minor: amount, checkout_currency: currency, checkout_currency_exponent: exponent}],
  }))[0];
  assert.equal(amountLabel(1, 'USD', 2), '五折 2个月');
  assert.equal(amountLabel(1001, 'KWD', 3), '五折 2个月');
  assert.equal(amountLabel(100000, 'VND', 0), '五折 2个月');
  for (const [amount, currency, exponent] of [[null, 'USD', 2], [undefined, 'USD', 2], ['', 'USD', 2], ['0', 'USD', 2], [true, 'USD', 2], [-1, 'USD', 2], [1.5, 'USD', 2], [0, '', 2], [0, 'USD', null], [0, 'USD', 4]]) {
    assert.equal(amountLabel(amount, currency, exponent), '五折 2个月');
  }
  const empty = view._promotionCell({...checked, account_promotions: [{...plusDiscount, checkout_status: 'success', session_type: 'unknown'}]});
  assert.deepEqual(visiblePromotionLabels(empty), ['五折 2个月']);
  assert.doesNotMatch(empty, /0元|0 USD|unknown|银行卡|\boaics\b/);
});

test('支付预检字段不替代优惠摘要或泄漏到套餐优惠列', () => {
  const html = view._promotionCell({...checked, plan_promotion_country: 'JP', account_promotions: [{
    ...plusDiscount, checkout_status: 'failed', checkout_http_status: 403, checkout_error: '结账接口访问受限',
    session_type: 'oaics', payment_method_types: ['upi'], checkout_amount_due_minor: 0, checkout_currency: 'JPY', checkout_currency_exponent: 0,
  }]});
  assert.deepEqual(visiblePromotionLabels(html), ['五折 2个月']);
  assert.match(html, /JP：/);
  assert.match(promotionTooltip(html), /Plus: 五折 2个月/);
  assert.doesNotMatch(visiblePromotionLabels(html).join(' '), /0 JPY|oaics|UPI|银行卡|结账接口访问受限/);
  assert.match(promotionTooltip(html), /支付方式查询失败；结账接口访问受限/);
  assert.doesNotMatch(promotionTooltip(html), /0 JPY|oaics|UPI|银行卡/);
  const httpOnly = view._promotionCell({...checked, account_promotions: [{...plusDiscount, checkout_status: 'failed', checkout_http_status: 429}]});
  assert.match(promotionTooltip(httpOnly), /Plus: 五折 2个月；支付方式查询失败；HTTP 429/);
});

test('跳过支付预检与国家不匹配保持待查询，不借用其他活动或国家的结果', () => {
  for (const fields of [{checkout_status: 'skipped', checkout_error: '未取得结账会话'}, {checkout_status: 'success', country: 'JP', checkout_country: 'IN'}]) {
    const html = view._promotionCell({...checked, plan_promotion_country: 'JP', account_promotions: [
      {...goTrial, checkout_status: 'success', session_type: 'cs_live', payment_method_types: ['upi']},
      {...plusDiscount, ...fields, session_type: 'oaics', payment_method_types: ['card'], checkout_amount_due_minor: 0, checkout_currency: 'INR', checkout_currency_exponent: 2},
    ]});
    assert.deepEqual(visiblePromotionLabels(html), ['五折 2个月']);
    assert.match(promotionTooltip(html), /Plus: 五折 2个月/);
    assert.doesNotMatch(html, /UPI|银行卡|oaics|cs_live|0 INR/);
  }
});

test('结账展示只接受枚举与支付代码，不输出完整会话、URL、secret或注入内容', () => {
  const malicious = {
    ...plusDiscount, checkout_status: 'success', session_type: 'cs_live_sensitiveid',
    payment_method_types: ['card', '<img src=x onerror=alert(1)>', 'https://checkout.example/session', 'cs_live_sensitiveid', 'oaics_sensitiveid', 'sk_live_private', 'client_secret_private', 'paypal'],
    checkout_url: 'https://checkout.example/private', checkout_session_id: 'cs_live_private', checkout_client_secret: 'private-secret',
    checkout_amount_due_minor: 0, checkout_currency: '<script>', checkout_currency_exponent: 2,
  };
  const success = view._promotionCell({...checked, account_promotions: [malicious]});
  assert.deepEqual(visiblePromotionLabels(success), ['五折 2个月']);
  assert.doesNotMatch(success, /<img|&lt;img|script|https:|sensitiveid|private|secret/);
  const failure = view._promotionCell({...checked, account_promotions: [{...malicious, checkout_status: 'failed', checkout_error: '接口失败 https://checkout.example/private cs_live_sensitiveid oaics_sensitiveid client_secret=private <img src=x>'}]});
  assert.match(promotionTooltip(failure), /Plus: 五折 2个月/);
  assert.doesNotMatch(failure, /<img|https:|sensitiveid|private|client_secret/);
});

test('多国优惠仍只占两行，浮窗和账号详情保留各国价格与支付方式', () => {
  const account = {plan_check_status: 'success', plan_check_country_results: ['JP', 'IN', 'VN'].map((country, index) => ({
    country, status: 'success', checked_at: `2026-10-16T0${index + 1}:00:00Z`, result: {account_promotions: [{...goTrial, plan: 'plus', checkout_country: country, checkout_status: 'success', session_type: index === 1 ? 'cs_live' : 'oaics', payment_method_types: index === 1 ? ['card', 'link', 'upi'] : ['card', 'link'], checkout_amount_due_minor: 0, checkout_currency: ['JPY', 'INR', 'VND'][index], checkout_currency_exponent: index === 1 ? 2 : 0}]},
  }))};
  const html = view._promotionCell(account);
  assert.equal((html.match(/class="account-promotion-country-row /g) || []).length, 2);
  assert.deepEqual(visiblePromotionCountries(html), ['VN', 'IN']);
  assert.deepEqual(visiblePromotionLabels(html), ['免费', '免费']);
  assert.doesNotMatch(html, /另 \d+ 国|account-promotion-country-summary/);
  const tooltip = promotionTooltip(html);
  assert.match(tooltip, /JP Plus: 免费 1个月/);
  assert.match(tooltip, /IN Plus: 免费 1个月/);
  assert.match(tooltip, /VN Plus: 免费 1个月/);
  assert.doesNotMatch(visiblePromotionLabels(html).join(' '), /0 JPY|0 INR|0 VND|oaics|cs_live|银行卡|\bUPI\b|\bLink\b/);
  for (const detail of [tooltip, view._accountDetailMarkup(account)]) {
    assert.match(detail, /实际应付: 0 JPY；结账会话: oaics；支付方式: 银行卡 Link/);
    assert.match(detail, /实际应付: 0 INR；结账会话: cs_live；支付方式: 银行卡 Link UPI/);
    assert.match(detail, /实际应付: 0 VND；结账会话: oaics；支付方式: 银行卡 Link/);
  }
});

test('多国详情保留成功总数，任务摘要只展示国家结果和异常状态', () => {
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
  assert.match(drawer, /1\/3 个国家成功/);
  const result = view.accountTaskResultText({task_type: 'plan_check', status: 'success', result_summary: account});
  assert.doesNotMatch(result, /国家查询|个国家成功|1\/3/);
  assert.match(result, /^套餐 free · 部分失败 · JP Go: 免费/);
  assert.match(result, /VN Plus: 免费/);
  assert.match(result, /IN 已取消/);
  assert.match(result, /部分失败/);
});

test('任务摘要只有多国汇总字段时省略成功计数并保留国家优惠与失败提示', () => {
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
  assert.doesNotMatch(result, /国家查询|个国家成功|1\/3/);
  assert.match(result, /失败国家：VN、IN/);
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

test('多国任务精简结果只显示套餐和最佳优惠，完整浮窗保留逐国 Go 与 Plus', () => {
  const task = {task_type: 'plan_check', status: 'success', result_summary: {
    current_plan_type: 'free', plan_check_status: 'success',
    plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [goTrial, plusDiscount]}},
      {country: 'VN', status: 'success', result: {account_promotions: [
        {plan: 'go', kind: 'none'}, {...goTrial, plan: 'plus'},
      ]}},
      {country: 'IN', status: 'success', result: {account_promotions: [
        {plan: 'go', kind: 'none'}, {plan: 'plus', kind: 'none'},
      ]}},
    ],
  }};
  const compact = view.accountTaskResultText(task, true);
  assert.match(compact, /^free · Plus:? 免费 1个月$/);
  assert.doesNotMatch(compact, /JP|VN|IN|国家查询|个国家成功/);
  const tooltip = view.accountTaskResultTooltipText(task);
  assert.match(tooltip, /套餐 free/);
  assert.match(tooltip, /JP[\s\S]*Go: 免费 1个月/);
  assert.match(tooltip, /JP[\s\S]*Plus: 五折 2个月/);
  assert.match(tooltip, /\n[^\n]*VN/);
  assert.match(tooltip, /VN[\s\S]*Plus: 免费 1个月/);
  assert.match(tooltip, /\n[^\n]*IN/);
  assert.match(tooltip, /IN[\s\S]*Plus: 无优惠/);
  assert.doesNotMatch(tooltip, /国家查询|个国家成功|3\/3/);
});

test('精简优惠优先免费再折扣，同级选择 Plus 并区分待查询与待核验', () => {
  const compact = account_promotions => view.accountTaskResultText({
    task_type: 'plan_check', status: 'success', result_summary: {...checked, account_promotions},
  }, true);
  assert.match(compact([goTrial, plusDiscount]), /^free · Go:? 免费 1个月$/);
  assert.match(compact([goTrial, {...goTrial, plan: 'plus'}]), /^free · Plus:? 免费 1个月$/);
  assert.match(compact([
    {plan: 'go', kind: 'discount', discount_percentage: 20}, plusDiscount,
  ]), /^free · Plus:? 五折 2个月$/);
  assert.match(view._accountTaskPromotionSummary([{plan: 'plus', kind: 'none'}]), /^无优惠$/);
  assert.match(view._accountTaskPromotionSummary([{plan: 'plus', kind: 'pending'}]), /待查询/);
  assert.match(view._accountTaskPromotionSummary([{plan: 'plus', kind: 'unknown'}]), /待核验/);
  assert.doesNotMatch(view._accountTaskPromotionSummary([
    {...goTrial, plan: 'plus', stale: true}, {...goTrial, plan: 'plus', stale: false},
  ]), /历史/);
});

test('多国均无优惠时任务精简结果合并状态，浮窗仍列出每个国家', () => {
  const task = {task_type: 'plan_check', status: 'success', result_summary: {
    current_plan_type: 'free', plan_check_status: 'success',
    plan_check_country_results: ['JP', 'VN'].map(country => ({country, status: 'success', result: {
      account_promotions: [{plan: 'go', kind: 'none'}, {plan: 'plus', kind: 'none'}],
    }})),
  }};
  assert.equal(view.accountTaskResultText(task, true), 'free · 无优惠');
  const tooltip = view.accountTaskResultTooltipText(task);
  assert.match(tooltip, /JP[\s\S]*Go: 无优惠[\s\S]*Plus: 无优惠/);
  assert.match(tooltip, /VN[\s\S]*Go: 无优惠[\s\S]*Plus: 无优惠/);
});

test('部分失败任务精简结果标记历史优惠，浮窗保留失败原因和取消状态', () => {
  const task = {task_type: 'plan_check', status: 'success', result_summary: {
    current_plan_type: 'free', plan_check_status: 'success', plan_check_partial: true,
    plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [{plan: 'go', kind: 'none'}, plusDiscount]}},
      {country: 'VN', status: 'failed', error: 'HTTP 429', last_success_at: '2026-10-14 09:00:00', result: {
        account_promotions: [{plan: 'go', kind: 'none'}, {...goTrial, plan: 'plus', duration_num_periods: 2}],
      }},
      {country: 'IN', status: 'cancelled', error: '已取消'},
    ],
  }};
  const compact = view.accountTaskResultText(task, true);
  assert.match(compact, /^free · /);
  assert.match(compact, /Plus:? 免费 2个月/);
  assert.match(compact, /部分失败/);
  assert.match(compact, /历史/);
  assert.doesNotMatch(compact, /JP|VN|IN|HTTP 429|失败国家/);
  const tooltip = view.accountTaskResultTooltipText(task);
  assert.match(tooltip, /VN[\s\S]*Plus: 免费 2个月/);
  assert.match(tooltip, /显示上次成功快照/);
  assert.match(tooltip, /本次查询失败: HTTP 429/);
  assert.match(tooltip, /IN[\s\S]*已取消/);
  assert.doesNotMatch(tooltip, /国家查询|个国家成功|1\/3/);
});

test('明确空国家列表时任务精简结果和浮窗使用最新单次结果', () => {
  const task = {task_type: 'plan_check', status: 'success', result_summary: {
    ...checked, plan_check_countries: [], country_total_count: null, country_success_count: null,
    plan_check_country_results: [{country: 'JP', status: 'success', result: {
      account_promotions: [{...goTrial, plan: 'plus', duration_num_periods: 12}],
    }}],
  }};
  assert.match(view.accountTaskResultText(task, true), /^free · Go:? 免费 1个月$/);
  const tooltip = view.accountTaskResultTooltipText(task);
  assert.match(tooltip, /Go: 免费 1个月/);
  assert.match(tooltip, /Plus: 五折 2个月/);
  assert.doesNotMatch(tooltip, /JP|12个月|国家查询|0\/0/);
});

test('任务套餐精简入口使用可聚焦按钮且浮窗保留全部详情并转义 HTML', () => {
  const task = {task_type: 'plan_check', status: 'success', result_summary: {
    current_plan_type: 'free', plan_check_status: 'success', plan_check_partial: true,
    plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [goTrial, plusDiscount]}},
      {country: 'VN', status: 'failed', error: '错误 " <img src=x> & \'失败\''},
    ],
  }};
  const html = view.accountTaskPlanResultMarkup(task);
  assert.match(html, /^<button\b/);
  assert.match(html, /type="button"/);
  assert.match(html, /class="account-task-result-summary"/);
  assert.match(html, /data-account-task-result-tooltip(?:\s|=|>)/);
  assert.match(html, /data-accounts-tooltip="[^"]*JP[^"]*VN/);
  assert.match(html, /aria-label="[^"]*查看套餐查询详情/);
  assert.match(html, /free · [^<]*免费 1个月/);
  assert.doesNotMatch(html, /\stitle=/);
  assert.doesNotMatch(html, /<img\b/);
  assert.match(html, /&quot; &lt;img src=x&gt; &amp; &#39;失败&#39;/);
  const tooltip = promotionTooltip(html);
  assert.match(tooltip, /JP[\s\S]*Go: 免费 1个月[\s\S]*Plus: 五折 2个月/);
  assert.match(tooltip, /VN[\s\S]*本次查询失败/);
  assert.equal((html.match(/<button\b/g) || []).length, 1);
  assert.equal((html.match(/<\/button>/g) || []).length, 1);
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
    plan_check_country_results: [{country: 'JP', status: 'failed', error: 'HTTP 403', last_success_at: '2026-10-14', result: {account_promotions: [{...goTrial, plan: 'plus'}]}}],
  });
  assert.match(html, /class="account-promotion-country">JP<span class="account-promotion-stale">历史<\/span>：<\/span>/);
  assert.deepEqual(visiblePromotionLabels(html), ['免费']);
});

test('三国优惠只显示最新两国，较旧免费优惠不覆盖最新折扣且浮窗保留各国', () => {
  const html = view._promotionCell({
    plan_check_country_results: [
      {country: 'JP', status: 'success', checked_at: '2026-10-16T12:00:00Z', result: {account_promotions: [{plan: 'plus', kind: 'discount', discount_percentage: 20}]}},
      {country: 'VN', status: 'success', checked_at: '2026-10-16T09:00:00Z', result: {account_promotions: [{plan: 'plus', kind: 'free_trial', duration_num_periods: 1, duration_period: 'month'}]}},
      {country: 'IN', status: 'success', checked_at: '2026-10-16T10:00:00Z', result: {account_promotions: [{plan: 'plus', kind: 'discount', discount_percentage: 50}]}},
    ],
  });
  assert.equal((html.match(/class="account-promotion-country-row /g) || []).length, 2);
  assert.deepEqual(visiblePromotionCountries(html), ['JP', 'IN']);
  assert.doesNotMatch(html, /另 \d+ 国|account-promotion-country-summary/);
  assert.match(promotionTooltip(html), /JP/);
  assert.match(promotionTooltip(html), /VN/);
  assert.match(promotionTooltip(html), /IN/);
});

test('十国仅显示最新两国，失败历史国家仍保留标记和全部国家浮窗', () => {
  const countries = Array.from({length: 10}, (_, index) => ({
    country: `C${index}`,
    status: index === 8 ? 'failed' : 'success',
    checked_at: `2026-10-16T${String(index + 1).padStart(2, '0')}:00:00Z`,
    error: index === 8 ? 'HTTP 429' : '',
    last_success_at: index === 8 ? '2026-10-14' : undefined,
    result: {account_promotions: [{plan: 'plus', kind: 'free_trial', duration_num_periods: 1, duration_period: 'month', payment_method_types: ['card', 'link', 'upi', 'very-long-payment-provider-name']}]},
  }));
  const html = view._promotionCell({plan_check_country_results: countries});
  assert.equal((html.match(/class="account-promotion-country-row /g) || []).length, 2);
  assert.deepEqual(visiblePromotionCountries(html), ['C9', 'C8']);
  assert.doesNotMatch(html, /另 \d+ 国|account-promotion-country-summary|account-promotion-summary-badge/);
  assert.match(html, /class="account-promotion-stale">历史/);
  assert.match(promotionTooltip(html), /C8（历史）[\s\S]*本次查询失败: HTTP 429/);
  assert.match(promotionTooltip(html), /C0 Plus:/);
});

test('国家时间相同或缺失时按原输入顺序显示，缺失时间不压过有效时间', () => {
  const country = (code, fields = {}) => ({country: code, status: 'success', ...fields, result: {account_promotions: [plusDiscount]}});
  for (const countries of [
    [country('VN'), country('JP'), country('IN')],
    ['VN', 'JP', 'IN'].map(code => country(code, {checked_at: '2026-10-16T09:00:00Z'})),
  ]) {
    assert.deepEqual(visiblePromotionCountries(view._promotionCell({plan_check_country_results: countries})), ['VN', 'JP']);
  }
  const html = view._promotionCell({plan_check_country_results: [
    country('VN'), country('JP', {checked_at: '2026-10-16T09:00:00Z'}), country('IN', {checked_at: '2026-10-16T10:00:00Z'}),
  ]});
  assert.deepEqual(visiblePromotionCountries(html), ['IN', 'JP']);
});

test('国家查询时间优先于成功快照时间，无效查询时间回退成功时间', () => {
  const country = (code, fields = {}) => ({country: code, status: 'success', ...fields, result: {account_promotions: [plusDiscount]}});
  const html = view._promotionCell({plan_check_country_results: [
    country('JP', {checked_at: '2026-10-16T09:00:00Z', last_success_at: '2026-10-16T13:00:00Z'}),
    country('VN', {checked_at: '无效时间', last_success_at: '2026-10-16T11:00:00Z'}),
    country('IN', {last_success_at: '2026-10-16T10:00:00Z'}),
    country('US', {checked_at: '无效时间', last_success_at: '也无效'}),
  ]});
  assert.deepEqual(visiblePromotionCountries(html), ['VN', 'IN']);
  assert.match(promotionTooltip(html), /JP Plus:/);
  assert.match(promotionTooltip(html), /US Plus:/);
});

test('最新无优惠国家仍被过滤，失败历史按最新尝试时间排序并显示国家优惠摘要', () => {
  const html = view._promotionCell({plan_check_country_results: [
    {country: 'JP', status: 'success', checked_at: '2026-10-16T09:00:00Z', result: {account_promotions: [{...plusDiscount, payment_method_types: ['card']}]}},
    {country: 'VN', status: 'failed', checked_at: '2026-10-16T12:00:00Z', last_success_at: '2026-10-14T09:00:00Z', error: 'HTTP 403', result: {account_promotions: [{...plusDiscount, payment_method_types: ['upi']}]}},
    {country: 'IN', status: 'success', checked_at: '2026-10-16T10:00:00Z', result: {account_promotions: [{...plusDiscount, payment_method_types: ['link']}]}},
    {country: 'US', status: 'success', checked_at: '2026-10-16T14:00:00Z', result: {account_promotions: [{plan: 'plus', kind: 'none'}]}},
  ]});
  assert.deepEqual(visiblePromotionCountries(html), ['VN', 'IN']);
  assert.deepEqual(visiblePromotionLabels(html), ['五折 2个月', '五折 2个月']);
  assert.match(html, /class="account-promotion-stale">历史/);
  assert.match(promotionTooltip(html), /VN（历史）[\s\S]*本次查询失败: HTTP 403/);
  assert.match(promotionTooltip(html), /JP Plus: 五折 2个月/);
  assert.doesNotMatch(visiblePromotionLabels(html).join(' '), /银行卡|\bUPI\b|\bLink\b/);
  assert.match(promotionTooltip(html), /VN（历史） Plus: 五折 2个月；支付方式: UPI/);
  assert.match(promotionTooltip(html), /JP Plus: 五折 2个月；支付方式: 银行卡/);
  assert.match(promotionTooltip(html), /IN Plus: 五折 2个月；支付方式: Link/);
  assert.match(promotionTooltip(html), /US Plus: 无优惠/);
});

test('明确空国家列表关闭多国时，最新单次查询不被历史国家结果覆盖', () => {
  const account = {
    current_plan_type: 'free', plan_check_status: 'success', plan_check_countries: [],
    account_promotions: [goTrial, plusDiscount],
    plan_check_country_results: [{country: 'JP', status: 'success', result: {account_promotions: [goTrial]}}],
  };
  const list = view._promotionCell(account);
  assertSinglePromotion(list, 'Plus: 五折 2个月');
  assert.doesNotMatch(list, /JP/);
  const detail = view._accountDetailMarkup(account);
  assert.match(detail, /Go 优惠/);
  assert.doesNotMatch(detail, /JP 优惠/);
});

function createResizableAccountTable(savedWidths = null, savedTotal = 0) {
  const template = fs.readFileSync(path.join(__dirname, '../../webui/templates/index.html'), 'utf8');
  const tableSource = template.slice(template.indexOf('<table class="accounts-table-v2"'));
  const colgroup = tableSource.slice(tableSource.indexOf('<colgroup>'), tableSource.indexOf('</colgroup>'));
  const columnClasses = [...colgroup.matchAll(/<col class="([^"]+)"/g)].map(match => match[1]);
  const columns = columnClasses.map(() => ({style: {}}));
  const style = {
    width: '',
    setProperty(name, value) { this[name] = value; },
    removeProperty(name) { delete this[name]; },
  };
  const table = {dataset: {resizableTable: 'accounts'}, style, querySelectorAll: selector => selector === 'colgroup col' ? columns : headers};
  table.getBoundingClientRect = () => ({width: Number.parseFloat(table.style.width) || 1500});
  const headers = columnClasses.map((value, index) => ({
    classList: {contains: name => value.split(' ').includes(name)},
    appendChild(handle) { this.handle = handle; },
    getBoundingClientRect() { return {width: (Number.parseFloat(columns[index].style.width) || 0) * table.getBoundingClientRect().width / 100}; },
  }));
  const storageKey = 'gpt_console_table_widths_accounts';
  const totalStorageKey = 'gpt_console_table_total_accounts';
  const storage = new Map([
    ...(savedWidths ? [[storageKey, JSON.stringify(savedWidths)]] : []),
    ...(savedTotal ? [[totalStorageKey, String(savedTotal)]] : []),
  ]);
  const listeners = new Map();
  const sandbox = {
    localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value)},
    document: {
      body: {classList: {add() {}, remove() {}}},
      createElement: () => ({
        classList: {add() {}, remove() {}},
        setAttribute() {},
        addEventListener(name, callback) { this[`on${name}`] = callback; },
      }),
      addEventListener(name, callback) { listeners.set(name, callback); },
      removeEventListener(name) { listeners.delete(name); },
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(commonSource.slice(commonSource.indexOf('const ACCOUNT_COLUMN_MIN_WIDTH'), commonSource.indexOf('function initResizableTables(')), sandbox);
  sandbox.initResizableTable(table);
  return {columns, table, headers, listeners, promotionIndex: columnClasses.indexOf('col-trial'), storage, storageKey};
}

test('默认列宽按 1500px 设计宽度应用，给国家与支付方式至少 180px 内容空间', () => {
  const {columns, promotionIndex} = createResizableAccountTable();
  assert.ok(promotionIndex >= 0, '账号表格应包含套餐优惠列');
  assert.ok(columns.every(column => Number.parseFloat(column.style.width) > 0), '默认列宽应覆盖所有真实表格列');
  const contentWidth = 1500 * Number.parseFloat(columns[promotionIndex].style.width) / 100 - 12;
  assert.ok(contentWidth >= 180, `套餐优惠内容空间不足: ${contentWidth}px`);
});

test('扩大默认套餐优惠列不覆盖用户已经保存的列宽', () => {
  const saved = Array(16).fill(10);
  saved[10] = 7;
  const {columns, promotionIndex, storage, storageKey} = createResizableAccountTable(saved);
  const expected = saved[promotionIndex] / saved.reduce((sum, value) => sum + value, 0) * 100;
  assert.equal(Number.parseFloat(columns[promotionIndex].style.width), expected);
  assert.equal(storage.get(storageKey), JSON.stringify(saved));
});

test('恢复保存的账号表格总宽，必要时只扩表并保留原列宽比例', () => {
  const saved = [36, 72, 160, 80, 104, 84, 88, 72, 88, 88, 192, 72, 88, 72, 96, 108];
  const {columns, table, promotionIndex} = createResizableAccountTable(saved, 1520);
  assert.equal(table.style.width, '1520px');
  const total = saved.reduce((sum, value) => sum + value, 0);
  assert.equal(Number.parseFloat(columns[promotionIndex].style.width), saved[promotionIndex] / total * 100);
});

test('优惠列保存比例较窄时尊重用户选择，不强制扩展表格', () => {
  const saved = [4, 8, 12, 5, 7, 6, 6, 5, 5, 5, 4, 5, 5, 5, 6, 4];
  const {columns, table, promotionIndex, storage, storageKey} = createResizableAccountTable(saved, 1396);
  const savedTotal = saved.reduce((sum, value) => sum + value, 0);
  assert.equal(Number.parseFloat(table.style.width), 1396);
  assert.equal(Number.parseFloat(columns[promotionIndex].style.width), saved[promotionIndex] / savedTotal * 100);
  assert.equal(storage.get(storageKey), JSON.stringify(saved));
});

test('历史窄 Token 与操作列不再被默认最小宽度重写，重载保持用户选择', () => {
  const saved = [36, 5, 160, 80, 104, 0.1, 88, 72, 88, 88, 1, 72, 88, 72, 96, 0.2];
  const first = createResizableAccountTable(saved, 1396);
  const storedBefore = first.storage.get(first.storageKey);
  const actualWidths = first.columns.map(column => Number.parseFloat(column.style.width) * Number.parseFloat(first.table.style.width) / 100);
  assert.equal(first.table.style.width, '1396px');
  assert.ok(actualWidths[5] < 28);
  assert.equal(storedBefore, JSON.stringify(saved));

  const reloaded = createResizableAccountTable(JSON.parse(storedBefore), Number.parseFloat(first.table.style.width));
  const reloadedWidths = reloaded.columns.map(column => Number.parseFloat(column.style.width) * Number.parseFloat(reloaded.table.style.width) / 100);
  assert.deepEqual(reloadedWidths, actualWidths);
  assert.equal(reloaded.storage.get(reloaded.storageKey), storedBefore);
});

test('额度列优先显示实际 5H 与周窗口，其他窗口仍可从提示查看', () => {
  const html = view._quotaCell({
    quota_status: 'success',
    quota_windows: [
      {kind: 'monthly', used_percent: 30},
      {kind: 'weekly', used_percent: 40},
      {kind: 'five_hour', used_percent: 10},
      {kind: 'daily', used_percent: 20},
    ],
  });
  assert.deepEqual([...html.matchAll(/<div class="quota-cell-line">([^<]+)<\/div>/g)].map(match => match[1]), ['5H', 'WEEKLY']);
  assert.match(html, /MONTH · 已用 30%/);
  assert.match(html, /DAY · 已用 20%/);
});

test('额度标签使用真实网格轨道，两个窗口不会以内联方式挤在一行', () => {
  const html = view._quotaCell({quota_status: 'success', quota_windows: [
    {kind: 'five_hour', used_percent: 10}, {kind: 'weekly', used_percent: 20},
  ]});
  assert.equal((html.match(/<div class="quota-cell-line">/g) || []).length, 2);
  assert.match(accountStyles, /\.quota-cell\s*\{[^}]*display:\s*grid;[^}]*grid-template-rows:\s*repeat\(2,/s);
  assert.match(accountStyles, /\.quota-cell-line\s*\{[^}]*display:\s*block;/s);
});

test('默认 2FA 窄列保留可完整点击的短验证码复制按钮', () => {
  const html = view._totpCellV2({id: 7, totp_enabled: true});
  assert.match(html, /data-account-totp-copy="7"[^>]*>复制<\/button>/);
  assert.match(html, /class="account-cell-line"><button/);
  assert.match(modernStyles, /\.status-action-cell button[\s\S]*?min-height:\s*26px;\s*padding:\s*0 10px;/);
  assert.match(accountStyles, /\.account-cell-line button\s*\{\s*flex:\s*0 0 auto;/);
});

test('用户调窄优惠列仍可通过提示查看完整国家与历史信息', () => {
  const saved = [36, 72, 160, 80, 104, 84, 88, 72, 88, 88, 1, 72, 88, 72, 96, 108];
  const {columns, table, headers, listeners, promotionIndex, storage, storageKey} = createResizableAccountTable(saved, 1396);
  headers[promotionIndex].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  listeners.get('pointermove')({clientX: -1000});
  const tableWidth = table.getBoundingClientRect().width;
  assert.ok(Math.abs(Number.parseFloat(columns[promotionIndex].style.width) * tableWidth / 100 - 28) < .001);
  listeners.get('pointerup')();
  const storedWidths = JSON.parse(storage.get(storageKey));
  assert.ok(Math.abs(storedWidths[promotionIndex] * tableWidth - 28) < .001);
  assert.match(accountStyles, /\.account-promotion-country-summary\s*\{[^}]*overflow:\s*visible\s*!important;/s);
  assert.match(accountStyles, /\.account-promotion-summary-badge\s*\{[^}]*flex:\s*0 0 auto;/s);
  const html = view._promotionCell({plan_promotion_country: 'JP', ...checked});
  assert.match(promotionTooltip(html), /JP Plus: 五折 2个月/);
});

test('旧单国成功与历史优惠采用同一国家格式，不借注册国家猜查询国家', () => {
  const html = view._promotionCell({...checked, plan_promotion_country: 'VN', registration_proxy_region: 'US'});
  assert.match(html, /class="account-promotion-country">VN：/);
  assert.match(html, /is-country-\d+/);
  assert.deepEqual(visiblePromotionLabels(html), ['五折 2个月']);
  const unknown = view._promotionCell({...checked, registration_proxy_region: 'US'});
  assert.match(unknown, /class="account-promotion-country" aria-label="国家未记录">—：/);
  assert.match(promotionTooltip(unknown), /国家未记录 Plus: 五折 2个月/);
  assert.doesNotMatch(unknown, /class="account-promotion-country">US/);
  const historical = view._promotionCell({...checked, plan_promotion_country: 'JP', plan_check_status: 'failed', plan_last_success_at: '2026-10-15'});
  assert.match(historical, /JP<span class="account-promotion-stale">历史/);
  assert.match(promotionTooltip(historical), /上次成功快照/);
});

test('常见国家优惠行使用稳定且不同的颜色和浅色背景', () => {
  const country = code => view._promotionCell({plan_check_country_results: [
    {country: code, status: 'success', result: {account_promotions: [plusDiscount]}},
  ]});
  const colors = ['JP', 'IN', 'VN', 'US'].map(code => country(code).match(/is-country-\d+/)[0]);
  assert.equal(new Set(colors).size, colors.length);
  assert.match(accountStyles, /\.account-promotion-country-row\.is-country-0\s*\{[^}]*background:\s*#[0-9a-f]{6}/i);
  assert.match(accountStyles, /\.account-promotion-country-row\.is-country-15\s*\{[^}]*background:\s*#[0-9a-f]{6}/i);
});

test('关闭多国后单次失败沿用最佳活动自己的历史国家，不取聚合首国', () => {
  const html = view._promotionCell({
    plan_check_countries: [], plan_check_status: 'failed', plan_last_success_at: '2026-10-15',
    plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [{plan: 'plus', kind: 'none'}]}},
      {country: 'US', status: 'success', result: {account_promotions: [{plan: 'plus', kind: 'free_trial'}]}},
    ],
    account_promotions: [
      {plan: 'plus', kind: 'none', country: 'JP'},
      {plan: 'plus', kind: 'free_trial', country: 'US'},
    ],
  });
  assert.match(html, /US<span class="account-promotion-stale">历史/);
  assert.doesNotMatch(html, /JP<span class="account-promotion-stale">历史/);
});
