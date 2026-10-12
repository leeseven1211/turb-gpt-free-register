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
  functionSource('_accountDetailAuthMethod'),
  functionSource('_accountDetailMarkup'),
  functionSource('accountTaskResultText'),
].join('\n'), view);

const goTrial = {plan: 'go', kind: 'free_trial', eligible: true, duration_num_periods: 1, duration_period: 'month', campaign_id: 'go-free-one'};
const plusDiscount = {plan: 'plus', kind: 'discount', eligible: true, discount_percentage: 50, duration_num_periods: 2, duration_period: 'month', campaign_id: 'plus-half-two'};
const checked = {id: 1, current_plan_type: 'free', plan_check_status: 'success', account_promotions: [goTrial, plusDiscount]};

test('同时显示 Go 免费和 Plus 折扣，活动详情可通过键盘焦点查看', () => {
  const html = view._promotionCell(checked);
  assert.match(html, /Go: 免费 1个月/);
  assert.match(html, /Plus: 五折 2个月/);
  assert.match(html, /go-free-one/);
  assert.match(html, /plus-half-two/);
  assert.equal((html.match(/tabindex="0"/g) || []).length, 2);
  assert.equal((html.match(/data-accounts-tooltip=/g) || []).length, 2);
});

test('旧 Plus 快照保留原优惠，Go 显示待查询而不误判无优惠', () => {
  const html = view._promotionCell({current_plan_type: 'free', plan_check_status: 'success', plus_promo_kind: 'discount', plus_promo_discount_percentage: 50, plus_promo_duration_num_periods: 3, plus_promo_duration_period: 'month'});
  assert.match(html, /Go: 待查询/);
  assert.match(html, /Plus: 五折 3个月/);
  assert.doesNotMatch(html, /Go: 无优惠/);
});

test('只有成功查询明确返回 none 才显示该套餐无优惠', () => {
  const html = view._promotionCell({...checked, account_promotions: [{plan: 'go', kind: 'none', eligible: false}, {plan: 'plus', kind: 'none', eligible: false}]});
  assert.match(html, /Go: 无优惠/);
  assert.match(html, /Plus: 无优惠/);
  const partial = view._promotionCell({...checked, account_promotions: [plusDiscount]});
  assert.match(partial, /Go: 待核验/);
  assert.doesNotMatch(partial, /Go: 无优惠/);
});

test('当前 Go 套餐不代表获得 Go 免费资格，未知活动不猜优惠类型', () => {
  const legacy = view._promotionCell({current_plan_type: 'go', plan_check_status: 'success'});
  assert.match(legacy, /Go: 待查询/);
  assert.doesNotMatch(legacy, /Go: 免费/);
  const unknown = view._promotionCell({...checked, current_plan_type: 'go', account_promotions: [{plan: 'go', kind: 'new-structure', campaign_id: 'go-free-trial'}, plusDiscount]});
  assert.match(unknown, /Go: 待核验/);
  assert.doesNotMatch(unknown, /Go: 免费/);
});

test('失败显示两项上次成功优惠和错误，没有成功快照则显示失败', () => {
  const html = view._promotionCell({...checked, plan_check_status: 'failed', plan_last_success_at: '2026-10-12 12:00:00', plan_check_error: 'HTTP 401'});
  assert.match(html, /Go: 免费 1个月/);
  assert.match(html, /Plus: 五折 2个月/);
  assert.match(html, /显示上次成功快照/);
  assert.match(html, /2026-10-12 12:00:00/);
  assert.match(html, /本次查询失败: HTTP 401/);
  const noSnapshot = view._promotionCell({...checked, plan_check_status: 'failed', plan_check_error: 'HTTP 401'});
  assert.match(noSnapshot, /Go: 查询失败/);
  assert.match(noSnapshot, /Plus: 查询失败/);
  assert.doesNotMatch(noSnapshot, /免费/);
});

test('同一套餐多活动保持两行摘要，提示保留全部活动并转义内容', () => {
  const other = {...goTrial, kind: 'discount', discount_percentage: 20, campaign_id: 'go-discount-other', title: '"><script>alert(1)</script>'};
  const html = view._promotionCell({...checked, account_promotions: [other, plusDiscount, goTrial]});
  assert.match(html, /Go: 免费 1个月 \+1/);
  assert.match(html, /减 20% 1个月/);
  assert.match(html, /go-discount-other/);
  assert.equal((html.match(/tabindex="0"/g) || []).length, 2);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
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
