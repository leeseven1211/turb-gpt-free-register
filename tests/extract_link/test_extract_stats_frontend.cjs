const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/extract_link/stats.js'), 'utf8');

function fixture(overrides = {}) {
  return {ok: true, days: 30, date_from: '2026-10-14', date_to: '2026-11-12',
    totals: {total: 100, extracted: 60, paid: 30, plus_confirmed: 25, failed: 15, processing: 25,
      awaiting_payment: 12, needs_review: 3, extraction_failed: 10, payment_failed: 5,
      extraction_rate: 60 / 70, payment_rate: 30 / 35, avg_seconds: 125},
    daily: [{date: '2026-11-11', total: 60, extracted: 40, paid: 20, plus_confirmed: 18, failed: 8},
      {date: '2026-11-12', total: 40, extracted: 20, paid: 10, plus_confirmed: 7, failed: 7}],
    providers: [{provider_id: 'anguang', total: 100, extracted: 60, paid: 30, plus_confirmed: 25,
      failed: 15, processing: 25, extraction_failed: 10, payment_failed: 5,
      extraction_rate: 60 / 70, payment_rate: 30 / 35, avg_seconds: 125}],
    failures: [{code: 'payment_timeout', label: '支付超时', count: 5}, {code: 'preflight_failed', label: '预检失败', count: 10}],
    modes: [{mode: 'auto_payment', total: 100, extracted: 60, paid: 30, plus_confirmed: 25, failed: 15}],
    current: {all: 140, processing: 35, awaiting_payment: 15, needs_review: 4}, generated_at: '2026-11-12T04:20:00Z', ...overrides};
}

function node(extra = {}) {
  return {dataset: {}, attributes: {}, innerHTML: '', textContent: '', hidden: false,
    setAttribute(name, value) { this.attributes[name] = value; }, ...extra};
}

function view(request = async () => fixture()) {
  const content = node(), status = node(), notice = node({hidden: true}), refresh = node(), provider = node({value: ''});
  const periods = [7, 30, 90].map(days => node({dataset: {extractStatsDays: String(days)}}));
  const nodes = {'[data-extract-stats-content]': content, '[data-extract-stats-status]': status,
    '[data-extract-stats-notice]': notice, '[data-extract-stats-refresh]': refresh, '[data-extract-stats-provider]': provider};
  const handlers = {};
  const root = node({querySelector: selector => nodes[selector], querySelectorAll: () => periods,
    addEventListener(name, handler) { handlers[name] = handler; }});
  const context = {URLSearchParams, document: {getElementById: id => id === 'extractStatsRoot' ? root : null},
    window: {__EXTRACT_STATS_DATA_SOURCE__: request}};
  vm.createContext(context);
  vm.runInContext(`${source}\n;globalThis.testApi = {load:loadExtractStats,render:renderExtractStats,
    rate:extractStatsRate, duration:extractStatsDuration, trend:renderExtractStatsTrend,
    failures:renderExtractStatsFailures, state:EXTRACT_STATS_STATE};`, context);
  return {api: context.testApi, root, content, status, notice, refresh, provider, periods, handlers};
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
}

test('空分母和缺失耗时显示破折号，零成功率保持为0.0%', () => {
  const {api} = view();
  for (const value of [null, undefined, '', -1, 2, '无结果']) assert.equal(api.rate(value), '—');
  assert.equal(api.rate(0), '0.0%');
  assert.equal(api.rate(1 / 3), '33.3%');
  assert.equal(api.duration(null), '—');
  assert.equal(api.duration(0), '0 秒');
  assert.equal(api.duration(125), '2 分 5 秒');
});

test('成功率明确阶段分母，支付成功与Plus确认以及当前全部日期分别展示', () => {
  const {api} = view();
  api.state.provider = 'anguang';
  const html = api.render(fixture());
  assert.match(html, /已出链 \/（已出链 \+ 提链失败）/);
  assert.match(html, /已支付 \/（已支付 \+ 支付失败）/);
  assert.match(html, /出链 60 · 失败 10/);
  assert.match(html, /支付 30 · 失败 5/);
  assert.match(html, /当前所选平台，全部日期/);
  assert.match(html, /Plus 已确认/);
  assert.match(html, /最新成功运行的总耗时/);
  assert.match(html, /今日任务按北京时间创建日归属/);
  assert.match(html, /<dt>今日任务出链<\/dt><dd>20<\/dd>/);
  assert.match(html, /<dt>今日任务 Plus<\/dt><dd>7<\/dd>/);
  assert.match(html, /<dt>当前待支付<small>全部日期<\/small><\/dt><dd>15<\/dd>/);
  assert.match(html, /<dt>当前待核对<small>全部日期<\/small><\/dt><dd>4<\/dd>/);
  assert.doesNotMatch(html, /data-workbench-status-filter/);
});

test('空区间的今日与当前指标保持为零', () => {
  const {api} = view();
  const html = api.render(fixture({daily: [], current: {}}));
  assert.match(html, /<dt>今日任务出链<\/dt><dd>0<\/dd>/);
  assert.match(html, /<dt>今日任务 Plus<\/dt><dd>0<\/dd>/);
  assert.match(html, /<dt>当前待支付<small>全部日期<\/small><\/dt><dd>0<\/dd>/);
  assert.match(html, /<dt>当前待核对<small>全部日期<\/small><\/dt><dd>0<\/dd>/);
});

test('趋势含可访问说明及全部每日数据，空区间不渲染无意义曲线', () => {
  const {api} = view();
  const html = api.trend(fixture().daily);
  assert.match(html, /role="img" aria-labelledby="extractStatsTrendTitle extractStatsTrendDescription"/);
  assert.match(html, /<summary>查看每日明细<\/summary>/);
  assert.match(html, /Plus 已确认/);
  assert.match(html, /2026-11-12/);
  assert.doesNotMatch(html, /NaN|Infinity/);
  assert.doesNotMatch(api.trend([{date: '2026-11-12', total: 0}]), /<svg/);
  assert.match(api.trend([]), /没有提链任务/);
});

test('错误分类按数量排序并转义平台、日期、模式和错误内容', () => {
  const {api} = view();
  const failures = api.failures([{code: '<script>alert(1)</script>', label: '<img src=x>', count: 9},
    {code: 'small', label: '少量错误', count: 2}]);
  assert.ok(failures.indexOf('&lt;img') < failures.indexOf('少量错误'));
  assert.doesNotMatch(failures, /<script>|<img/);
  assert.match(failures, /&lt;script&gt;/);
  const html = api.render(fixture({providers: [{provider_id: '<svg onload=x>', total: 1}],
    modes: [{mode: '<script>x</script>', total: 1}], date_from: '<img src=x>'}));
  assert.doesNotMatch(html, /<script>|<img|<svg onload/);
  assert.match(html, /&lt;svg onload=x&gt;/);
});

test('初次加载显示反馈，过滤平台进入请求且完成后更新控件', async () => {
  const pending = deferred();
  let endpoint;
  const ui = view(url => { endpoint = url; return pending.promise; });
  ui.api.state.provider = 'anguang';
  const loading = ui.api.load();
  assert.equal(ui.root.attributes['aria-busy'], 'true');
  assert.equal(ui.refresh.disabled, true);
  assert.match(ui.content.innerHTML, /正在汇总/);
  assert.equal(endpoint, '/api/extract-workbench/analytics?days=30&provider_id=anguang');
  pending.resolve(fixture());
  await loading;
  assert.equal(ui.root.attributes['aria-busy'], 'false');
  assert.equal(ui.refresh.disabled, false);
  assert.equal(ui.provider.value, 'anguang');
  assert.equal(ui.periods[1].attributes['aria-pressed'], 'true');
  assert.match(ui.content.innerHTML, /每日趋势/);
});

test('较晚返回的旧时间范围响应不覆盖当前结果或结束当前加载', async () => {
  const older = deferred(), newer = deferred();
  let requests = 0;
  const ui = view(() => (++requests === 1 ? older : newer).promise);
  const first = ui.api.load();
  ui.api.state.days = 7;
  const second = ui.api.load();
  older.resolve(fixture({date_from: '旧时间范围'}));
  await first;
  assert.equal(ui.root.attributes['aria-busy'], 'true');
  assert.doesNotMatch(ui.content.innerHTML, /旧时间范围/);
  newer.resolve(fixture({date_from: '最新时间范围', days: 7}));
  await second;
  assert.match(ui.content.innerHTML, /最新时间范围/);
  assert.equal(ui.root.attributes['aria-busy'], 'false');
  assert.equal(ui.periods[0].attributes['aria-pressed'], 'true');
});

test('同范围刷新失败保留上次数据，换范围失败不会显示旧数据，重试可恢复', async () => {
  let failure = false;
  const ui = view(async () => { if (failure) throw new Error('统计连接失败'); return fixture(); });
  await ui.api.load();
  const previous = ui.content.innerHTML;
  failure = true;
  await ui.api.load();
  assert.equal(ui.content.innerHTML, previous);
  assert.equal(ui.notice.hidden, false);
  assert.match(ui.notice.innerHTML, /保留上次统计/);
  assert.match(ui.notice.innerHTML, /data-extract-stats-retry/);
  ui.api.state.days = 90;
  await ui.api.load();
  assert.doesNotMatch(ui.content.innerHTML, /每日趋势/);
  assert.match(ui.content.innerHTML, /未取得所选范围/);
  ui.api.state.days = 30;
  await ui.api.load();
  assert.equal(ui.content.innerHTML, previous);
  assert.match(ui.notice.innerHTML, /保留上次统计/);
  failure = false;
  await ui.api.load();
  assert.equal(ui.notice.hidden, true);
  assert.match(ui.content.innerHTML, /每日趋势/);
});

test('不完整或显式失败的响应进入可重试错误状态', async () => {
  const ui = view(async () => ({ok: false, error: '<远端错误>'}));
  await ui.api.load();
  assert.equal(ui.notice.hidden, false);
  assert.match(ui.notice.innerHTML, /&lt;远端错误&gt;/);
  assert.equal(ui.root.attributes['aria-busy'], 'false');
});
