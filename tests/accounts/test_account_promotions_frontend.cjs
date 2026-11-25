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
  functionSource('compactAccountStatus'),
  functionSource('accountCodexDisplay'),
  functionSource('_accountDetailState'),
  functionSource('_accountCountryDetailMarkup'),
  functionSource('_accountDetailAuthMethod'),
  functionSource('_accountPasswordAuthDisplay'),
  functionSource('_accountDetailMarkup'),
].join('\n'), view);

const goTrial = {plan: 'go', kind: 'free_trial', eligible: true, duration_num_periods: 1, duration_period: 'month', campaign_id: 'go-free-one'};
const plusDiscount = {plan: 'plus', kind: 'discount', eligible: true, discount_percentage: 50, duration_num_periods: 2, duration_period: 'month', campaign_id: 'plus-half-two'};
const checked = {id: 1, current_plan_type: 'free', plan_check_status: 'success', account_promotions: [goTrial, plusDiscount]};

function visiblePromotionLabels(html) {
  return [...html.matchAll(/<span class="account-promotion-label">([^<]*)<\/span>/g)].map(match => match[1]);
}
function promotionTooltip(html, plan = '') {
  const pattern = plan ? new RegExp(`data-promotion-plan="${plan}" data-accounts-tooltip="([^"]*)"`, 'g') : /data-accounts-tooltip="([^"]*)"/g;
  return [...html.matchAll(pattern)].map(match => match[1]).join('\n');
}
function tagTone(html, plan) {
  return html.match(new RegExp(`class="account-promotion-tag ([^"]+)" data-promotion-plan="${plan}"`))?.[1];
}
function assertPlanTags(html) {
  assert.deepEqual(visiblePromotionLabels(html), ['Team', 'Plus', 'Go']);
  assert.equal((html.match(/class="account-promotion-tag /g) || []).length, 3);
  assert.equal((html.match(/tabindex="0"/g) || []).length, 3);
  assert.doesNotMatch(html, /class="account-promotion-country|is-country-\d|class="pill /);
}
const teamTrial = {...goTrial, plan: 'team', campaign_id: 'team-1-month-free'};

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
    _accountsTooltipBound: false,
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

test('浮窗重复初始化不会重复注册全局事件', () => {
  const counts = new Map();
  const add = name => counts.set(name, (counts.get(name) || 0) + 1);
  const context = {_accountsTooltipBound: false, _hideAccountsTooltip() {}, document: {addEventListener: add}, window: {addEventListener: add}};
  const start = source.indexOf('function bindAccountsHoverTooltips()');
  const end = source.indexOf('\nfunction _planCell(', start);
  vm.runInNewContext(`${source.slice(start, end)}\nbindAccountsHoverTooltips();bindAccountsHoverTooltips();`, context);
  assert.equal(counts.get('mouseover'), 1);
  assert.equal(counts.get('scroll'), 1);
  assert.equal(counts.get('keydown'), 1);
});

test('套餐优惠固定显示 Team、Plus、Go 三标签，免费绿色、折扣蓝色、无优惠灰色', () => {
  const row = {...checked, plan_promotion_country: 'JP', account_promotions: [teamTrial, plusDiscount, {plan: 'go', kind: 'none'}]};
  const html = view._promotionCell(row);
  assertPlanTags(html);
  assert.equal(tagTone(html, 'team'), 'is-free');
  assert.equal(tagTone(html, 'plus'), 'is-discount');
  assert.equal(tagTone(html, 'go'), 'is-muted');
  assert.match(promotionTooltip(html, 'team'), /Team（Business）: 免费试用 1个月/);
  assert.match(promotionTooltip(html, 'team'), /team-1-month-free/);
  assert.match(promotionTooltip(html, 'plus'), /JP Plus: 五折 2个月/);
  assert.match(promotionTooltip(html, 'go'), /Go: 无优惠/);
});

test('旧记录缺 Team 与未确认活动保持灰色，具体状态留在各套餐浮窗', () => {
  const html = view._promotionCell({...checked, account_promotions: [{plan: 'go', kind: 'unknown'}, {plan: 'plus', kind: 'none'}]});
  assertPlanTags(html);
  for (const plan of ['team', 'plus', 'go']) assert.equal(tagTone(html, plan), 'is-muted');
  assert.match(promotionTooltip(html, 'team'), /待查询/);
  assert.match(promotionTooltip(html, 'plus'), /无优惠/);
  assert.match(promotionTooltip(html, 'go'), /待复查/);
  assert.match(view._accountDetailMarkup({...checked, account_promotions: [plusDiscount]}), /Team（Business）: 待查询/);
});

test('蓝色仅表示半价，其余折扣保持灰色并在浮窗说明减免比例', () => {
  for (const percentage of [20, 60, 90]) {
    const html = view._promotionCell({...checked, account_promotions: [{...plusDiscount, discount_percentage: percentage}]});
    assert.equal(tagTone(html, 'plus'), 'is-muted');
    assert.match(promotionTooltip(html, 'plus'), new RegExp(`减 ${percentage}% 2个月`));
  }
});

test('查询排队、失败和取消只改变浮窗原因，不增加标签或使用成功颜色', () => {
  for (const [status, expected] of [['queued', /排队/], ['running', /正在执行/], ['failed', /HTTP 403/], ['cancelled', /取消/]]) {
    const html = view._promotionCell({plan_check_status: status, plan_check_error: 'HTTP 403'});
    assertPlanTags(html);
    for (const plan of ['team', 'plus', 'go']) {
      assert.equal(tagTone(html, plan), 'is-muted');
      assert.match(promotionTooltip(html, plan), expected);
    }
  }
});

test('跨国家每个套餐选择最高优惠，保留较旧免费、同套餐全部活动与失败证据', () => {
  const row = {plan_check_status: 'success', plan_check_country_results: [
    {country: 'JP', status: 'success', checked_at: '2026-11-20', result: {account_promotions: [
      {...teamTrial, kind: 'discount', discount_percentage: 50}, {...plusDiscount, discount_percentage: 90}, {plan: 'go', kind: 'none'},
    ]}},
    {country: 'VN', status: 'failed', error: 'HTTP 429', last_success_at: '2026-11-01', result: {account_promotions: [
      {...teamTrial, duration_num_periods: 2}, {...goTrial, plan: 'plus'}, {...goTrial, kind: 'discount', discount_percentage: 50},
    ]}},
  ]};
  const before = JSON.stringify(row);
  const html = view._promotionCell(row);
  assertPlanTags(html);
  assert.equal(tagTone(html, 'team'), 'is-free');
  assert.equal(tagTone(html, 'plus'), 'is-free');
  assert.equal(tagTone(html, 'go'), 'is-discount');
  assert.match(html, /aria-label="Plus：免费 1个月（历史）"/);
  assert.match(promotionTooltip(html, 'team'), /JP[\s\S]*五折[\s\S]*VN（历史）[\s\S]*免费试用 2个月[\s\S]*HTTP 429/);
  assert.match(promotionTooltip(html, 'plus'), /减 90%[\s\S]*免费 1个月/);
  assert.equal(JSON.stringify(row), before, '展示不得改写国家与活动证据');
});

test('相同优惠优先当前证据，免费与折扣分别按实际期限和折扣选择', () => {
  const html = view._promotionCell({...checked, account_promotions: [
    {...teamTrial, stale: true}, {...teamTrial, stale: false},
    {...plusDiscount, discount_percentage: 20, duration_num_periods: 12}, {...plusDiscount, discount_percentage: 60},
    {...goTrial, duration_num_periods: 11}, {...goTrial, duration_num_periods: 1, duration_period: 'year'},
  ]});
  assert.match(html, /aria-label="Team：免费试用 1个月"/);
  assert.match(html, /aria-label="Plus：减 60% 2个月"/);
  assert.match(html, /aria-label="Go：免费 1年"/);
});

test('新查询排队时标签保持历史优惠，浮窗保留旧国家与新任务原因', () => {
  const html = view._promotionCell({plan_check_status: 'queued', plan_check_country_results: [
    {country: 'JP', status: 'success', checked_at: '2026-11-01', result: {account_promotions: [teamTrial, plusDiscount, goTrial]}},
  ]});
  assertPlanTags(html);
  assert.equal(tagTone(html, 'team'), 'is-free');
  assert.match(promotionTooltip(html, 'team'), /JP（历史）[\s\S]*新任务排队中/);
  assert.match(promotionTooltip(html, 'plus'), /上次成功/);
});

test('各套餐浮窗保留自己的国家金额与支付方式，不借用其他套餐或国家结果', () => {
  const row = {plan_check_status: 'success', plan_check_country_results: [
    {country: 'JP', status: 'success', result: {account_promotions: [
      {...teamTrial}, {...plusDiscount, checkout_status: 'success', checkout_country: 'JP', session_type: 'oaics', payment_method_types: ['card', 'link'], checkout_amount_due_minor: 0, checkout_currency: 'JPY', checkout_currency_exponent: 0},
      {...goTrial, payment_method_types: ['upi']},
    ]}},
    {country: 'IN', status: 'success', result: {account_promotions: [
      {...plusDiscount, checkout_status: 'success', checkout_country: 'IN', session_type: 'cs_live', payment_method_types: ['upi'], checkout_amount_due_minor: 99900, checkout_currency: 'INR', checkout_currency_exponent: 2},
    ]}},
  ]};
  const html = view._promotionCell(row);
  assertPlanTags(html);
  const plus = promotionTooltip(html, 'plus');
  assert.match(plus, /JP Plus:[^\n]*实际应付: 0 JPY；结账会话: oaics；支付方式: 银行卡 Link/);
  assert.match(plus, /IN Plus:[^\n]*实际应付: 999 INR；结账会话: cs_live；支付方式: UPI/);
  assert.doesNotMatch(promotionTooltip(html, 'team'), /实际应付|oaics|cs_live|UPI|银行卡/);
  assert.match(promotionTooltip(html, 'go'), /Go: 免费 1个月；[^\n]*支付方式: UPI/);
});

test('预检失败、跳过与国家不匹配不影响套餐颜色，浮窗保留准确原因', () => {
  for (const fields of [
    {checkout_status: 'failed', checkout_http_status: 429, checkout_error: '结账接口访问受限'},
    {checkout_status: 'skipped', checkout_error: '未取得结账会话'},
    {checkout_status: 'success', country: 'JP', checkout_country: 'IN'},
  ]) {
    const html = view._promotionCell({...checked, account_promotions: [{...plusDiscount, ...fields, session_type: 'oaics', payment_method_types: ['card'], checkout_amount_due_minor: 0, checkout_currency: 'INR', checkout_currency_exponent: 2}]});
    assert.equal(tagTone(html, 'plus'), 'is-discount');
    assert.doesNotMatch(promotionTooltip(html, 'plus'), /oaics|银行卡|0 INR/);
    assert.match(promotionTooltip(html, 'plus'), fields.checkout_status === 'failed' ? /支付方式查询失败；结账接口访问受限/ : /待查询/);
  }
});

test('结账浮窗过滤凭据与注入内容，非法价格不显示为零', () => {
  const offer = {...plusDiscount, checkout_status: 'success', session_type: 'cs_live_sensitiveid', payment_method_types: ['card', '<img src=x>', 'https://checkout.example/session', 'cs_live_sensitiveid', 'oaics_sensitiveid', 'sk_live_private', 'client_secret_private', 'paypal'], checkout_url: 'https://checkout.example/private', checkout_amount_due_minor: null, checkout_currency: 'USD', checkout_currency_exponent: 2};
  const html = view._promotionCell({...checked, account_promotions: [offer]});
  assert.equal(tagTone(html, 'plus'), 'is-discount');
  assert.match(promotionTooltip(html, 'plus'), /银行卡 paypal/);
  assert.doesNotMatch(html, /<img|&lt;img|https:|sensitiveid|private|secret|实际应付/);
  const failure = view._promotionCell({...checked, account_promotions: [{...offer, checkout_status: 'failed', checkout_error: '接口失败 https://checkout.example/private cs_live_sensitiveid oaics_sensitiveid client_secret=private <img src=x>'}]});
  assert.doesNotMatch(failure, /<img|https:|sensitiveid|private|client_secret/);
});

test('三标签不因国家数量膨胀，全部国家与失败历史仍可查看', () => {
  const countries = Array.from({length: 10}, (_, index) => ({country: `C${index}`, status: index === 8 ? 'failed' : 'success', error: index === 8 ? 'HTTP 429' : '', last_success_at: index === 8 ? '2026-11-01' : undefined, result: {account_promotions: [teamTrial, plusDiscount, goTrial]}}));
  const html = view._promotionCell({plan_check_country_results: countries});
  assertPlanTags(html);
  assert.match(promotionTooltip(html, 'team'), /C0[\s\S]*C8（历史）[\s\S]*HTTP 429[\s\S]*C9/);
  assert.match(view._accountDetailMarkup({plan_check_country_results: countries}), /C8 优惠/);
});

test('Go 免费资格不开放 Plus 提链，原确认 Plus 免费资格仍可提链', () => {
  assert.equal(view._extractLinkAction({...checked, plus_promo_kind: 'discount'}), '');
  assert.equal(view._extractLinkAction({...checked, plus_promo_kind: 'none'}), '');
  assert.match(view._extractLinkAction({...checked, plus_promo_kind: 'free_trial', plus_trial_eligible: true}), /data-extract-link/);
});

test('账号详情展示 Go 与 Plus 优惠及本次查询错误', () => {
  const drawer = view._accountDetailMarkup({...checked, plan_check_status: 'failed', plan_last_success_at: '2026-10-12 12:00:00', plan_check_error: 'HTTP 403'});
  assert.match(drawer, /Go 优惠/);
  assert.match(drawer, /Plus 优惠/);
  assert.match(drawer, /Go: 免费 1个月/);
  assert.match(drawer, /Plus: 五折 2个月/);
  assert.match(drawer, /本次查询失败: HTTP 403/);
});

test('多国账号详情保留成功总数和失败原因', () => {
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
});

// Task rows now render the production Vue presenter rather than legacy task DOM.
const taskVue=require('./actions_fixture.cjs').vueHarness;
const taskPresentation=taskVue.load('src/features/tasks/presentation.ts');
view.accountTaskResultText=taskPresentation.resultText;
view.accountTaskResultTooltipText=taskPresentation.resultDetails;

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

test('明确空国家列表关闭多国时，三标签使用最新单次查询且不混入历史国家', () => {
  const account = {...checked, plan_check_countries: [], plan_check_country_results: [
    {country: 'JP', status: 'success', result: {account_promotions: [teamTrial]}},
  ]};
  const html = view._promotionCell(account);
  assertPlanTags(html);
  assert.equal(tagTone(html, 'team'), 'is-muted');
  assert.equal(tagTone(html, 'plus'), 'is-discount');
  assert.doesNotMatch(promotionTooltip(html), /JP/);
  assert.doesNotMatch(view._accountDetailMarkup(account), /JP 优惠/);
});

// Width assertions follow the current Vue table; the preserved pure promotion
// presenter still supplies the actual country/tooltip markup in the same cells.
const vue = taskVue;
const AccountsTable = vue.load('src/features/accounts/AccountsTable.vue').default;
const {createAccountPresentation} = vue.load('src/features/accounts/presentation.ts');
const querySandbox = {window: {}, URLSearchParams};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../webui/static/js/shared/account-query.js'), 'utf8'), querySandbox);
test.afterEach(() => vue.cleanup());

async function createResizableAccountTable(savedWidths = null, savedTotal = 0) {
  const storageKey = 'gpt_console_table_widths_accounts';
  const totalStorageKey = 'gpt_console_table_total_accounts';
  const storage = {get: key => localStorage.getItem(key)};
  localStorage.clear();
  if (savedWidths) localStorage.setItem(storageKey, JSON.stringify(savedWidths));
  if (savedTotal) localStorage.setItem(totalStorageKey, String(savedTotal));
  // The same pure migration is called by the production bridge before mount.
  const migration = vm.createContext({localStorage});
  vm.runInContext(commonSource.slice(commonSource.indexOf('const ACCOUNT_COLUMN_MIN_WIDTH'), commonSource.indexOf('function initResizableTables(')), migration);
  migration.migrateAccountTableWidths();
  const presentation = createAccountPresentation({
    cells: {token: () => '', account_status: () => '', password: () => '', quota: view._quotaCell,
      promotion: view._promotionCell, totp: view._totpCellV2, risk: () => '', time: () => ''},
    plan: () => '', extractLink: () => '', codex: () => '', menu: () => '', emailInvalidBadge: () => '',
    registrationDriverLabel: () => '', facetLabel: (_group, value) => value, escape: view.esc,
    short: (value, length) => value.slice(0, length), htmlText: html => html.replace(/<[^>]*>/g, ''),
  });
  const wrapper = vue.mount(AccountsTable, {props: {items: [{...checked, plan_promotion_country: 'JP'}],
    selected: new Set(), query: querySandbox.window.AccountQuery.normalize(), facets: {}, presentation,
    loading: false, error: '', invalidSearch: false, stale: false, visible: true,
    pageSelected: false, pageIndeterminate: false, openFilter: null}});
  await vue.nextTick();
  const table = wrapper.get('table').element;
  const columns = wrapper.findAll('col').map(col => col.element);
  const headers = wrapper.findAll('thead th');
  const promotionIndex = headers.findIndex(header => header.classes().includes('col-trial'));
  return {columns, table, headers, wrapper, promotionIndex, storage, storageKey};
}
function assertWidth(actual, expected, message = '') {
  assert.ok(Math.abs(actual - expected) < 0.0001, `${message}: ${actual} != ${expected}`);
}

test('默认列宽按 1500px 设计宽度应用，为三个套餐短标签保留完整内容空间', async () => {
  const {columns, promotionIndex} = await createResizableAccountTable();
  assert.ok(promotionIndex >= 0, '账号表格应包含套餐优惠列');
  assert.ok(columns.every(column => Number.parseFloat(column.style.width) > 0), '默认列宽应覆盖所有真实表格列');
  assert.equal(columns.length, 16);
  const contentWidth = Number.parseFloat(columns[promotionIndex].style.width) - 12;
  assert.ok(contentWidth >= 180, `套餐优惠内容空间不足: ${contentWidth}px`);
});

test('扩大默认套餐优惠列不覆盖用户已经保存的列宽', async () => {
  const saved = Array(16).fill(10);
  saved[10] = 7;
  const {columns, promotionIndex, storage, storageKey} = await createResizableAccountTable(saved);
  const expected = saved[promotionIndex] / saved.reduce((sum, value) => sum + value, 0) * 1500;
  assertWidth(Number.parseFloat(columns[promotionIndex].style.width), expected);
  assert.equal(storage.get(storageKey), JSON.stringify(saved));
});

test('恢复保存的账号表格总宽，必要时只扩表并保留原列宽比例', async () => {
  const saved = [36, 72, 160, 80, 104, 84, 88, 72, 88, 88, 192, 72, 88, 72, 96, 108];
  const {columns, table, promotionIndex} = await createResizableAccountTable(saved, 1520);
  assertWidth(Number.parseFloat(table.style.width), 1520);
  const total = saved.reduce((sum, value) => sum + value, 0);
  assertWidth(Number.parseFloat(columns[promotionIndex].style.width), saved[promotionIndex] / total * 1520);
});

test('优惠列保存比例较窄时尊重用户选择，不强制扩展表格', async () => {
  const saved = [4, 8, 12, 5, 7, 6, 6, 5, 5, 5, 4, 5, 5, 5, 6, 4];
  const {columns, table, promotionIndex, storage, storageKey} = await createResizableAccountTable(saved, 1396);
  const savedTotal = saved.reduce((sum, value) => sum + value, 0);
  assertWidth(Number.parseFloat(table.style.width), 1396);
  assertWidth(Number.parseFloat(columns[promotionIndex].style.width), saved[promotionIndex] / savedTotal * 1396);
  assert.equal(storage.get(storageKey), JSON.stringify(saved));
});

test('历史窄 Token 与操作列不再被默认最小宽度重写，重载保持用户选择', async () => {
  const saved = [36, 5, 160, 80, 104, 0.1, 88, 72, 88, 88, 1, 72, 88, 72, 96, 0.2];
  const first = await createResizableAccountTable(saved, 1396);
  const storedBefore = first.storage.get(first.storageKey);
  const actualWidths = first.columns.map(column => Number.parseFloat(column.style.width));
  assert.equal(first.table.style.width, '1396px');
  assert.ok(actualWidths[5] < 28);
  assert.equal(storedBefore, JSON.stringify(saved));

  const reloaded = await createResizableAccountTable(JSON.parse(storedBefore), Number.parseFloat(first.table.style.width));
  const reloadedWidths = reloaded.columns.map(column => Number.parseFloat(column.style.width));
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

test('用户调窄优惠列仍可通过提示查看完整国家与历史信息', async () => {
  const saved = [36, 72, 160, 80, 104, 84, 88, 72, 88, 88, 1, 72, 88, 72, 96, 108];
  const {columns, table, headers, wrapper, promotionIndex, storage, storageKey} = await createResizableAccountTable(saved, 1396);
  await headers[promotionIndex].get('button.ui-table__resize').trigger('pointerdown', {button: 0, clientX: 100});
  document.dispatchEvent(new MouseEvent('pointermove', {clientX: -1000}));
  await vue.nextTick();
  const tableWidth = Number.parseFloat(table.style.width);
  assert.ok(Math.abs(Number.parseFloat(columns[promotionIndex].style.width) - 28) < .001);
  document.dispatchEvent(new MouseEvent('pointerup'));
  const storedWidths = JSON.parse(storage.get(storageKey));
  assert.ok(Math.abs(storedWidths[promotionIndex] / 100 * tableWidth - 28) < .001);
  assert.equal(wrapper.get('td.col-trial [data-promotion-plan="plus"]').attributes('tabindex'), '0');
  assert.match(wrapper.get('td.col-trial [data-promotion-plan="plus"]').attributes('data-accounts-tooltip'), /JP Plus: 五折 2个月/);
  const html = view._promotionCell({plan_promotion_country: 'JP', ...checked});
  assert.match(promotionTooltip(html), /JP Plus: 五折 2个月/);
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
  assert.match(result, /Go:? 免费/);
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
  assert.match(result, /^套餐 free · Go: 免费 1个月(?: · |；)Plus: 五折 2个月$/);
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

test('精简优惠优先免费再折扣，同级选择 Plus 并区分待查询与待复查', () => {
  const compact = account_promotions => view.accountTaskResultText({
    task_type: 'plan_check', status: 'success', result_summary: {...checked, account_promotions},
  }, true);
  assert.match(compact([goTrial, plusDiscount]), /^free · Go:? 免费 1个月$/);
  assert.match(compact([goTrial, {...goTrial, plan: 'plus'}]), /^free · Plus:? 免费 1个月$/);
  assert.match(compact([
    {plan: 'go', kind: 'discount', discount_percentage: 20}, plusDiscount,
  ]), /^free · Plus:? 五折 2个月$/);
  for (const [kind,label] of [['none','无优惠'],['pending','待查询'],['unknown','待复查']]) assert.match(taskPresentation.resultDetails({id:1,task_type:'plan_check',status:'success',result_summary:{account_promotions:[{plan:'plus',kind}]}}),new RegExp(`Plus: ${label}`));
  assert.doesNotMatch(compact([{...goTrial,plan:'plus',stale:true},{...goTrial,plan:'plus',stale:false}]),/历史/);
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



test('任务套餐精简入口可聚焦展开，保留全部国家详情并转义 HTML', async () => {
  taskVue.cleanup();const TaskTable=taskVue.load('src/features/tasks/TaskTable.vue').default;
  const task={id:1,task_type:'plan_check',status:'success',result_summary:{current_plan_type:'free',plan_check_status:'success',plan_check_partial:true,plan_check_country_results:[
    {country:'JP',status:'success',result:{account_promotions:[goTrial,plusDiscount]}},
    {country:'VN',status:'failed',error:'错误 " <img src=x> & 失败'},
  ]}};
  const wrapper=taskVue.mount(TaskTable,{props:{items:[task],selected:new Set(),loading:false,busy:false,error:''}});await taskVue.nextTick();
  const details=wrapper.get('details'),summary=details.get('summary');assert.equal(summary.text(),'部分失败');assert.match(summary.attributes('title'),/JP[\s\S]*VN/);
  assert.match(details.text(),/JP[\s\S]*Go: 免费 1个月[\s\S]*Plus: 五折 2个月/);assert.match(details.text(),/错误 " <img src=x> & 失败/);assert.equal(details.find('img').exists(),false);assert.equal(wrapper.findAll('details').length,1);taskVue.cleanup();
});
