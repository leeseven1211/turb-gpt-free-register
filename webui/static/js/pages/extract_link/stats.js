// 提链统计独立维护筛选与请求顺序，避免切换时间范围后显示旧请求的结果。
const EXTRACT_STATS_STATE = {days: 30, provider: '', sequence: 0, data: null, scope: '', renderedScope: '', providers: new Map()};
const EXTRACT_STATS_PROVIDER_LABELS = {legacy: '虾扯蛋链', lumen: 'Lumen Flow', lumen_flow: 'Lumen Flow', huanguang: '幻光提链', anguang: '暗光（XXSYUN 一条龙）'};
const EXTRACT_STATS_MODE_LABELS = {extract_only: '仅提链', manual_payment: '手动支付', auto_payment: '自动支付'};

function extractStatsEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}

function extractStatsCount(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? Math.floor(number) : 0;
}

function extractStatsNumber(value) { return extractStatsCount(value).toLocaleString('zh-CN'); }

function extractStatsRate(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number <= 1 ? `${(number * 100).toFixed(1)}%` : '—';
}

function extractStatsDuration(value) {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) || Number(value) < 0) return '—';
  const seconds = Math.round(Number(value));
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
  return `${Math.floor(seconds / 3600)} 小时 ${Math.floor(seconds % 3600 / 60)} 分`;
}

function extractStatsProviderLabel(provider) { return EXTRACT_STATS_PROVIDER_LABELS[provider] || String(provider || '未记录平台'); }

function extractStatsUrl() {
  const params = new URLSearchParams({days: String(EXTRACT_STATS_STATE.days)});
  if (EXTRACT_STATS_STATE.provider) params.set('provider_id', EXTRACT_STATS_STATE.provider);
  return `/api/extract-workbench/analytics?${params}`;
}

function extractStatsRequest(url) {
  if (typeof window.__EXTRACT_STATS_DATA_SOURCE__ === 'function') return window.__EXTRACT_STATS_DATA_SOURCE__(url);
  if (typeof extractWorkbenchRequest === 'function') return extractWorkbenchRequest(url);
  return api(url);
}

function extractStatsMetric(label, value, hint, tone = '') {
  return `<article class="es-metric ${tone ? `es-metric--${tone}` : ''}"><span class="es-metric-label">${label}</span><strong>${extractStatsNumber(value)}</strong><span class="es-metric-hint">${hint}</span></article>`;
}

function renderExtractStatsTrend(items) {
  const daily = Array.isArray(items) ? items : [];
  if (!daily.length || !daily.some(item => extractStatsCount(item.total))) return '<div class="es-empty"><strong>这个时间段还没有提链任务</strong><p>选择其他时间范围，或在提链工作台新建批次。</p></div>';
  const series = [['total', '任务总数', 'total'], ['extracted', '已出链', 'extracted'], ['paid', '已支付', 'paid']];
  const width = 880, height = 242, left = 48, right = 20, top = 22, bottom = 36;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const peak = Math.max(1, ...daily.flatMap(item => series.map(([key]) => extractStatsCount(item[key]))));
  const maximum = peak <= 4 ? 4 : Math.ceil(peak / 4) * 4;
  const x = index => left + (daily.length === 1 ? plotWidth / 2 : index * plotWidth / (daily.length - 1));
  const y = value => top + plotHeight * (1 - extractStatsCount(value) / maximum);
  const grid = Array.from({length: 5}, (_, index) => {
    const value = maximum * index / 4, position = y(value);
    return `<line x1="${left}" x2="${width - right}" y1="${position}" y2="${position}" class="es-chart-gridline"/><text x="${left - 10}" y="${position + 4}" text-anchor="end" class="es-chart-label">${extractStatsNumber(value)}</text>`;
  }).join('');
  const ticks = [...new Set([0, ...daily.map((_, index) => index).filter(index => index % Math.max(1, Math.ceil(daily.length / 7)) === 0), daily.length - 1])];
  const dates = ticks.map(index => `<text x="${x(index)}" y="${height - 10}" text-anchor="middle" class="es-chart-label">${extractStatsEscape(String(daily[index].date || '').slice(5))}</text>`).join('');
  const paths = series.map(([key, label, tone]) => {
    const path = daily.map((item, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${y(item[key]).toFixed(2)}`).join(' ');
    return `<path class="es-chart-line es-chart-line--${tone}" d="${path}"/>${daily.map((item, index) => `<circle class="es-chart-point es-chart-point--${tone}" cx="${x(index)}" cy="${y(item[key])}" r="${daily.length <= 31 ? 3 : 2}"><title>${extractStatsEscape(item.date)} ${label} ${extractStatsNumber(item[key])}</title></circle>`).join('')}`;
  }).join('');
  return `<div class="es-chart-legend">${series.map(([, label, tone]) => `<span><i class="es-legend-dot es-legend-dot--${tone}" aria-hidden="true"></i>${label}</span>`).join('')}</div>
    <div class="es-chart-scroll"><svg class="es-chart" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="extractStatsTrendTitle extractStatsTrendDescription"><title id="extractStatsTrendTitle">每日提链与支付趋势</title><desc id="extractStatsTrendDescription">${daily.length} 天的任务总数、已出链与已支付数量。完整数值以及 Plus 到账、失败数量可在下方每日明细中查看。</desc>${grid}${dates}${paths}</svg></div>
    <details class="es-daily-details"><summary>查看每日明细</summary><div class="es-table-scroll"><table><caption class="es-sr-only">每日任务统计，按北京时间任务创建日归属</caption><thead><tr><th scope="col">日期</th><th scope="col">任务总数</th><th scope="col">已出链</th><th scope="col">已支付</th><th scope="col">Plus 已确认</th><th scope="col">失败</th></tr></thead><tbody>${daily.map(item => `<tr><th scope="row">${extractStatsEscape(item.date)}</th>${['total', 'extracted', 'paid', 'plus_confirmed', 'failed'].map(key => `<td>${extractStatsNumber(item[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
}

function renderExtractStatsFailures(items) {
  const failures = (Array.isArray(items) ? items : []).filter(item => extractStatsCount(item.count)).sort((a, b) => extractStatsCount(b.count) - extractStatsCount(a.count));
  if (!failures.length) return '<div class="es-empty es-empty--compact"><span class="es-empty-success" aria-hidden="true">✓</span><strong>暂无失败记录</strong><p>所选范围没有失败任务。</p></div>';
  const maximum = Math.max(...failures.map(item => extractStatsCount(item.count)));
  return `<ol class="es-failures">${failures.map(item => `<li><div class="es-failure-heading"><span>${extractStatsEscape(item.label || item.code || '原因未记录')}</span><strong>${extractStatsNumber(item.count)}</strong></div><div class="es-failure-track" aria-hidden="true"><span style="width:${extractStatsCount(item.count) / maximum * 100}%"></span></div><code>${extractStatsEscape(item.code || '未记录错误码')}</code></li>`).join('')}</ol>`;
}

function renderExtractStatsProviders(items) {
  const providers = Array.isArray(items) ? items : [];
  if (!providers.length) return '<div class="es-empty es-empty--compact"><strong>暂无平台数据</strong><p>所选范围没有提链任务。</p></div>';
  return `<div class="es-table-scroll" tabindex="0" aria-label="平台统计，可左右滚动"><table class="es-provider-table"><caption class="es-sr-only">各提链平台的任务产出与转化</caption><thead><tr><th scope="col">平台</th><th scope="col">任务数</th><th scope="col">已出链</th><th scope="col" title="已出链 /（已出链 + 提链失败），未结束任务不进入分母">提链成功率</th><th scope="col">已支付</th><th scope="col" title="已支付 /（已支付 + 支付失败），未结束任务不进入分母">支付成功率</th><th scope="col">Plus 已确认</th><th scope="col">失败</th><th scope="col">处理中</th><th scope="col" title="最新成功运行的平均总耗时">平均耗时</th></tr></thead><tbody>${providers.map(item => `<tr><th scope="row">${extractStatsEscape(extractStatsProviderLabel(item.provider_id))}</th><td>${extractStatsNumber(item.total)}</td><td class="es-number-extracted">${extractStatsNumber(item.extracted)}</td><td title="已出链 ${extractStatsNumber(item.extracted)}，提链失败 ${extractStatsNumber(item.extraction_failed)}">${extractStatsRate(item.extraction_rate)}</td><td class="es-number-paid">${extractStatsNumber(item.paid)}</td><td title="已支付 ${extractStatsNumber(item.paid)}，支付失败 ${extractStatsNumber(item.payment_failed)}">${extractStatsRate(item.payment_rate)}</td><td>${extractStatsNumber(item.plus_confirmed)}</td><td>${extractStatsNumber(item.failed)}</td><td>${extractStatsNumber(item.processing)}</td><td class="es-nowrap">${extractStatsDuration(item.avg_seconds)}</td></tr>`).join('')}</tbody></table></div>`;
}

function renderExtractStatsModes(items, total) {
  const modes = Array.isArray(items) ? items : [];
  if (!modes.length) return '<div class="es-empty es-empty--compact"><strong>暂无模式数据</strong></div>';
  return `<div class="es-modes">${modes.map(item => {
    const share = extractStatsCount(total) ? Math.min(1, extractStatsCount(item.total) / extractStatsCount(total)) : null;
    return `<article class="es-mode"><div class="es-mode-heading"><h3>${extractStatsEscape(EXTRACT_STATS_MODE_LABELS[item.mode] || item.mode || '未记录模式')}</h3><span>${extractStatsRate(share)}</span></div><strong class="es-mode-total">${extractStatsNumber(item.total)}<small> 个任务</small></strong><div class="es-mode-track" aria-hidden="true"><span style="width:${share === null ? 0 : share * 100}%"></span></div><dl>${[['extracted', '出链'], ['paid', '支付'], ['plus_confirmed', 'Plus'], ['failed', '失败']].map(([key, label]) => `<div><dt>${label}</dt><dd>${extractStatsNumber(item[key])}</dd></div>`).join('')}</dl></article>`;
  }).join('')}</div>`;
}

function renderExtractStats(data) {
  const totals = data?.totals || {}, current = data?.current || {};
  const daily = Array.isArray(data?.daily) ? data.daily : [];
  const today = daily[daily.length - 1] || {};
  const period = `${extractStatsEscape(data?.date_from || '—')} — ${extractStatsEscape(data?.date_to || '—')}`;
  return `<section class="es-today" aria-labelledby="extractStatsTodayTitle"><div class="es-today-heading"><h2 id="extractStatsTodayTitle">今日与当前</h2><span>今日任务按北京时间创建日归属</span></div><dl><div><dt>今日任务出链</dt><dd>${extractStatsNumber(today.extracted)}</dd></div><div><dt>今日任务 Plus</dt><dd>${extractStatsNumber(today.plus_confirmed)}</dd></div><div><dt>当前待支付<small>全部日期</small></dt><dd>${extractStatsNumber(current.awaiting_payment)}</dd></div><div><dt>当前待核对<small>全部日期</small></dt><dd>${extractStatsNumber(current.needs_review)}</dd></div></dl></section>
    <div class="es-scope"><span>${period}</span><span>按任务创建日统计 · 同一任务仅计一次</span></div>
    <div class="es-metrics">${extractStatsMetric('任务总数', totals.total, '所选时间内创建的任务')}${extractStatsMetric('已出链', totals.extracted, '已获得支付链接', 'brand')}${extractStatsMetric('已支付', totals.paid, '支付结果已确认', 'green')}${extractStatsMetric('Plus 已确认', totals.plus_confirmed, '套餐到账已核验', 'blue')}</div>
    <div class="es-summary-grid"><section class="es-panel es-conversion" aria-labelledby="extractStatsConversionTitle"><div class="es-panel-header"><h2 id="extractStatsConversionTitle">转化与耗时</h2><span>未结束任务不进入成功率分母</span></div><dl><div><dt>提链成功率</dt><dd>${extractStatsRate(totals.extraction_rate)}</dd><span>已出链 /（已出链 + 提链失败）</span><small>出链 ${extractStatsNumber(totals.extracted)} · 失败 ${extractStatsNumber(totals.extraction_failed)}</small></div><div><dt>支付成功率</dt><dd>${extractStatsRate(totals.payment_rate)}</dd><span>已支付 /（已支付 + 支付失败）</span><small>支付 ${extractStatsNumber(totals.paid)} · 失败 ${extractStatsNumber(totals.payment_failed)}</small></div><div><dt>平均耗时</dt><dd class="es-duration">${extractStatsDuration(totals.avg_seconds)}</dd><span>最新成功运行的总耗时</span></div></dl></section>
    <section class="es-panel es-task-states" aria-labelledby="extractStatsStatesTitle"><div class="es-panel-header"><h2 id="extractStatsStatesTitle">区间任务状态</h2><span>所选范围的最新结果</span></div><dl>${[['failed', '失败', 'red'], ['processing', '处理中', 'brand'], ['awaiting_payment', '待支付', 'amber'], ['needs_review', '待核对', 'amber']].map(([key, label, tone]) => `<div><dt><i class="es-state-dot es-state-dot--${tone}" aria-hidden="true"></i>${label}</dt><dd>${extractStatsNumber(totals[key])}</dd></div>`).join('')}</dl><p class="es-current">${EXTRACT_STATS_STATE.provider ? '当前所选平台' : '当前全部平台'}，全部日期：处理中 ${extractStatsNumber(current.processing)} · 待支付 ${extractStatsNumber(current.awaiting_payment)} · 待核对 ${extractStatsNumber(current.needs_review)}</p></section></div>
    <div class="es-chart-grid"><section class="es-panel es-trend" aria-labelledby="extractStatsDailyTitle"><div class="es-panel-header"><h2 id="extractStatsDailyTitle">每日趋势</h2><span>按北京时间任务创建日归属</span></div>${renderExtractStatsTrend(data?.daily)}</section><section class="es-panel" aria-labelledby="extractStatsFailureTitle"><div class="es-panel-header"><h2 id="extractStatsFailureTitle">失败分类</h2><span>${extractStatsNumber(totals.failed)} 个失败任务</span></div>${renderExtractStatsFailures(data?.failures)}</section></div>
    <section class="es-panel es-platforms" aria-labelledby="extractStatsProvidersTitle"><div class="es-panel-header"><h2 id="extractStatsProvidersTitle">平台对比</h2><span>支付成功与 Plus 到账分别统计</span></div>${renderExtractStatsProviders(data?.providers)}</section>
    <section class="es-panel es-mode-panel" aria-labelledby="extractStatsModesTitle"><div class="es-panel-header"><h2 id="extractStatsModesTitle">模式分布</h2><span>所选范围内的任务组成</span></div>${renderExtractStatsModes(data?.modes, totals.total)}</section>`;
}

function extractStatsSetBusy(root, busy) {
  root.setAttribute('aria-busy', String(busy));
  const refresh = root.querySelector('[data-extract-stats-refresh]');
  if (refresh) { refresh.disabled = busy; refresh.setAttribute('aria-busy', String(busy)); }
}

function extractStatsSyncControls(root, data) {
  for (const button of root.querySelectorAll('[data-extract-stats-days]')) button.setAttribute('aria-pressed', String(Number(button.dataset.extractStatsDays) === EXTRACT_STATS_STATE.days));
  for (const item of Array.isArray(data?.providers) ? data.providers : []) if (item.provider_id) EXTRACT_STATS_STATE.providers.set(String(item.provider_id), extractStatsProviderLabel(item.provider_id));
  const select = root.querySelector('[data-extract-stats-provider]');
  if (select) {
    for (const [id, label] of Object.entries(EXTRACT_STATS_PROVIDER_LABELS)) EXTRACT_STATS_STATE.providers.set(id, label);
    select.innerHTML = '<option value="">全部平台</option>' + [...EXTRACT_STATS_STATE.providers].filter(([id]) => id !== 'lumen').map(([id, label]) => `<option value="${extractStatsEscape(id)}">${extractStatsEscape(label)}</option>`).join('');
    select.value = EXTRACT_STATS_STATE.provider;
  }
}

function extractStatsBind(root) {
  if (root.dataset.extractStatsBound === 'true') return;
  root.dataset.extractStatsBound = 'true';
  root.addEventListener('click', event => {
    const period = event.target.closest('[data-extract-stats-days]');
    if (period) {
      const days = Number(period.dataset.extractStatsDays);
      if (![7, 30, 90].includes(days) || days === EXTRACT_STATS_STATE.days) return;
      EXTRACT_STATS_STATE.days = days;
      void loadExtractStats();
    } else if (event.target.closest('[data-extract-stats-refresh], [data-extract-stats-retry]')) void loadExtractStats();
  });
  root.addEventListener('change', event => {
    if (!event.target.matches('[data-extract-stats-provider]')) return;
    EXTRACT_STATS_STATE.provider = String(event.target.value || '');
    void loadExtractStats();
  });
}

async function loadExtractStats() {
  const root = document.getElementById('extractStatsRoot');
  if (!root) return;
  extractStatsBind(root);
  const content = root.querySelector('[data-extract-stats-content]');
  const status = root.querySelector('[data-extract-stats-status]');
  const notice = root.querySelector('[data-extract-stats-notice]');
  const url = extractStatsUrl(), sequence = ++EXTRACT_STATS_STATE.sequence;
  const hasPrevious = EXTRACT_STATS_STATE.data && EXTRACT_STATS_STATE.scope === url;
  extractStatsSetBusy(root, true);
  extractStatsSyncControls(root);
  if (notice) { notice.hidden = true; notice.innerHTML = ''; }
  if (status) status.textContent = hasPrevious ? '正在刷新统计…' : '正在加载统计…';
  if (!hasPrevious && content) {
    content.innerHTML = '<div class="es-loading" role="status"><span class="es-loading-dot" aria-hidden="true"></span>正在汇总提链任务…</div>';
    EXTRACT_STATS_STATE.renderedScope = '';
  } else if (hasPrevious && content && EXTRACT_STATS_STATE.renderedScope !== url) {
    content.innerHTML = renderExtractStats(EXTRACT_STATS_STATE.data);
    EXTRACT_STATS_STATE.renderedScope = url;
  }
  try {
    const data = await extractStatsRequest(url);
    if (sequence !== EXTRACT_STATS_STATE.sequence) return;
    if (!data || data.ok === false || !data.totals || !Array.isArray(data.daily)) throw new Error(data?.error || '统计响应格式不完整');
    EXTRACT_STATS_STATE.data = data;
    EXTRACT_STATS_STATE.scope = url;
    EXTRACT_STATS_STATE.renderedScope = url;
    extractStatsSyncControls(root, data);
    if (content) content.innerHTML = renderExtractStats(data);
    const generated = data.generated_at ? new Date(data.generated_at) : null;
    if (status) status.textContent = generated && Number.isFinite(generated.getTime()) ? `更新于 ${generated.toLocaleTimeString('zh-CN', {timeZone: 'Asia/Shanghai', hour12: false})}` : '统计已更新';
  } catch (error) {
    if (sequence !== EXTRACT_STATS_STATE.sequence) return;
    if (status) status.textContent = '统计加载失败';
    if (notice) {
      notice.hidden = false;
      notice.innerHTML = `<span>${hasPrevious ? '刷新失败，以下保留上次统计。' : '统计暂时无法加载。'}${extractStatsEscape(error?.message || '请稍后重试')}</span><button type="button" data-extract-stats-retry>重试</button>`;
    }
    if (!hasPrevious && content) content.innerHTML = '<div class="es-loading es-loading--failed">未取得所选范围的统计，请重试。</div>';
  } finally {
    if (sequence === EXTRACT_STATS_STATE.sequence) extractStatsSetBusy(root, false);
  }
}
