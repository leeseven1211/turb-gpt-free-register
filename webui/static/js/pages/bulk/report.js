// 批次报告只渲染服务端确认的本轮统计，不从账号缓存或分页明细推算结果。
window.BulkPlanReport = (() => {
  const operationNames = {plan_check:'查套餐',token_refresh:'刷新 AT',password_setup:'补密码',twofa_setup:'补 2FA',codex_retry:'补 Codex',account_completion:'组合补全'};
  const planNames = {free:'Free',plus:'Plus',pro:'Pro',team:'Team',business:'Business',enterprise:'Enterprise',go:'Go',unknown:'尚未确认'};
  const offerNames = {free_trial:'免费试用',half_price:'半价优惠',discount:'折扣优惠',other_discount:'其他折扣',other_promo:'其他优惠'};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const numeric = value => value !== null && value !== undefined && value !== '' && typeof value !== 'boolean' && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : null;
  const number = value => numeric(value) === null ? '—' : Math.floor(Number(value)).toLocaleString('zh-CN');
  const planName = value => planNames[value] || String(value || '尚未确认');
  const offerName = value => offerNames[value] || String(value || '其他优惠');
  function duration(value) {
    const seconds = numeric(value);
    if (seconds === null) return '—';
    if (seconds < 60) return `${seconds === 0 ? '0' : seconds < 1 ? seconds.toFixed(2) : seconds.toFixed(1).replace(/\.0$/, '')} 秒`;
    const rounded = Math.round(seconds), hours = Math.floor(rounded / 3600), minutes = Math.floor(rounded % 3600 / 60), rest = rounded % 60;
    return [hours ? `${hours} 小时` : '', minutes ? `${minutes} 分` : '', rest ? `${rest} 秒` : ''].filter(Boolean).join(' ') || '0 秒';
  }
  function timestamp(value) {
    if (!value) return '—';
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime()) ? parsed.toLocaleString('zh-CN', {hour12:false}) : '—';
  }
  function metric(title, value, variant = '', note = '') {
    return `<div class="bulk-report-metric ${variant}"><dt>${escape(title)}</dt><dd>${number(value)}<span>个</span></dd>${note ? `<small>${escape(note)}</small>` : ''}</div>`;
  }
  function minor(title, value, variant = '') {
    return `<div class="bulk-report-minor ${variant}"><dt>${escape(title)}</dt><dd>${number(value)}<span>个</span></dd></div>`;
  }
  function rail(value, max, modifier = '') {
    const n = numeric(value), top = numeric(max);
    const width = n !== null && top > 0 ? Math.max(0, Math.min(100, n / top * 100)) : 0;
    return `<span class="bulk-report-rail ${modifier}" aria-hidden="true"><span style="width:${width.toFixed(3)}%"></span></span>`;
  }
  function scopeText(report) {
    const view = report.view || {};
    if (view.kind === 'round') return Number(view.round_no) === 1 ? '首轮名单' : numeric(view.round_no) !== null ? `重跑 ${Number(view.round_no) - 1} · 固定名单` : '所选轮次 · 固定名单';
    return '当前结果 · 每个账号取最近一轮';
  }
  function offersMarkup(offers = {}) {
    const rows = Array.isArray(offers.by_plan) ? [...offers.by_plan] : [];
    rows.sort((a, b) => (numeric(b.accounts) || 0) - (numeric(a.accounts) || 0) || planName(a.plan).localeCompare(planName(b.plan)));
    const max = Math.max(0, ...rows.map(row => numeric(row.accounts) || 0));
    return `<section class="bulk-report-offers" aria-labelledby="bulkReportOffersTitle"><div class="bulk-report-section-head"><div><h4 id="bulkReportOffersTitle">优惠结果</h4><p>统计本次查到的可用优惠，按账号去重</p></div></div><dl class="bulk-report-offer-totals">${metric('有优惠账号', offers.with_offer_accounts, 'is-accent', '多个国家只算一个账号')}${metric('确认无优惠', offers.confirmed_no_offer_accounts, '', '完整查询成功且无优惠')}${metric('优惠待确认', offers.unknown_accounts, '', '含待完成、未执行或缺少结果')}</dl><div class="bulk-report-offer-list">${rows.length ? rows.map(row => {
      const kinds = Array.isArray(row.kinds) ? row.kinds : [];
      return `<div class="bulk-report-offer-row"><div class="bulk-report-offer-line"><strong>${escape(planName(row.plan))}</strong><span><b>${number(row.accounts)}</b> 个账号</span></div>${rail(row.accounts, max)}<dl class="bulk-report-kind-list">${kinds.map(kind => `<div><dt>${escape(offerName(kind.kind))}</dt><dd>${number(kind.accounts)}<span>个</span></dd></div>`).join('')}</dl></div>`;
    }).join('') : `<p class="bulk-report-empty">${numeric(offers.with_offer_accounts) === 0 ? '本次尚未查到可用优惠。' : '暂无优惠套餐明细。'}</p>`}</div><p class="bulk-report-note">同一账号可符合多个套餐或优惠，分项数量可能重叠。</p></section>`;
  }
  function plansMarkup(plans) {
    const rows = Array.isArray(plans) ? [...plans] : [];
    rows.sort((a, b) => a.plan === 'unknown' ? 1 : b.plan === 'unknown' ? -1 : (numeric(b.accounts) || 0) - (numeric(a.accounts) || 0));
    const max = Math.max(0, ...rows.map(row => numeric(row.accounts) || 0));
    return `<section class="bulk-report-plans" aria-labelledby="bulkReportPlansTitle"><div class="bulk-report-section-head"><div><h4 id="bulkReportPlansTitle">当前订阅套餐</h4><p>本次查询确认的套餐状态</p></div></div><dl class="bulk-report-plan-list">${rows.length ? rows.map(row => `<div class="${row.plan === 'unknown' ? 'is-unknown' : ''}"><dt>${escape(planName(row.plan))}</dt><dd><span>${number(row.accounts)}<small>个</small></span>${rail(row.accounts, max, row.plan === 'unknown' ? 'is-muted' : '')}</dd></div>`).join('') : '<div class="bulk-report-empty">暂无套餐结果。</div>'}</dl><p class="bulk-report-note">“尚未确认”包含待完成、失败或缺少套餐记录的账号。</p></section>`;
  }
  function render(report, businessMarkup = '') {
    if (!report || !Object.prototype.hasOwnProperty.call(operationNames, report.operation_key)) return '';
    const operation = operationNames[report.operation_key];
    if (report.population_ready === false) return `<section class="bulk-plan-report bulk-report-placeholder" aria-label="${escape(operation)}报告"><h3>${escape(operation)}报告</h3><p role="status">${escape(scopeText(report))} · ${report.phase === 'preparing' ? '账号名单准备中，固定后生成报告。' : '该轮名单未固定，无法生成账号统计。'}</p></section>`;
    const totals = report.totals || {}, timing = report.duration || {}, at = report.at_refresh || {};
    const completed = report.phase === 'completed', preparing = report.phase === 'preparing';
    const title = `${operation}${completed ? '完成报告' : '实时报告'}`;
    const timingMarkup = `<section aria-labelledby="bulkReportDurationTitle"><div class="bulk-report-section-head"><h4 id="bulkReportDurationTitle">账号执行耗时</h4><span>已结束样本 ${number(timing.sample_count)} 个</span></div><dl class="bulk-report-durations"><div class="is-average"><dt>平均耗时</dt><dd>${escape(duration(timing.avg_seconds))}</dd></div><div><dt>最快</dt><dd>${escape(duration(timing.min_seconds))}</dd></div><div><dt>最慢</dt><dd>${escape(duration(timing.max_seconds))}</dd></div></dl><p class="bulk-report-note">从账号开始执行到结束，${report.operation_key === 'plan_check' ? '含自动刷新及链内等待' : '含链内等待'}，不含开始前排队。${numeric(timing.missing_count) > 0 ? ` ${number(timing.missing_count)} 个已结束账号缺少有效耗时，未计入均值。` : numeric(timing.sample_count) === 0 ? ' 暂无有效耗时样本。' : ''}</p></section>`;
    // businessMarkup 只能由页面的受控功能统计渲染器传入，接口文本不直接当 HTML 使用。
    const functionMarkup = `<section aria-labelledby="bulkReportFunctionTitle"><div class="bulk-report-section-head"><h4 id="bulkReportFunctionTitle">功能统计</h4><span>当前查看范围</span></div>${typeof businessMarkup === 'string' && businessMarkup.trim() ? businessMarkup : '<p class="bulk-report-empty">暂无已确认的功能统计。</p>'}</section>`;
    const taskMarkup = report.operation_key === 'plan_check' ? `<section aria-labelledby="bulkReportAtTitle"><div class="bulk-report-section-head"><h4 id="bulkReportAtTitle">AT 检查与自动刷新</h4><span>按账号去重</span></div><dl class="bulk-report-at-causes">${minor('AT 过期',at.expired_accounts)}${minor('远端拒绝 AT',at.invalid_accounts)}${minor('缺少 AT',at.missing_token_accounts)}</dl><dl class="bulk-report-at-results">${minor('尝试刷新',at.attempted_accounts)}${minor('刷新成功',at.succeeded_accounts,'is-success')}${minor('刷新失败',at.failed_accounts,'is-danger')}${minor('刷新中',at.pending_accounts)}</dl><p class="bulk-report-note">${numeric(at.not_needed_accounts) !== null ? `未触发刷新 ${number(at.not_needed_accounts)} 个 · ` : ''}刷新状态待确认 ${number(at.unknown_accounts)} 个${numeric(at.not_executed_accounts) !== null ? ` · 未开始执行 ${number(at.not_executed_accounts)} 个` : ''}。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。</p></section>` : functionMarkup;
    const moreStats = report.operation_key === 'plan_check' && typeof businessMarkup === 'string' && businessMarkup.trim() ? `<details class="bulk-business-details"><summary>更多查询统计<span>展开查看</span></summary>${businessMarkup}</details>` : '';
    const distributions = report.operation_key === 'plan_check' ? `<div class="bulk-report-distributions">${offersMarkup(report.offers)}${plansMarkup(report.plans)}</div>` : '';
    return `<section class="bulk-plan-report" aria-labelledby="bulkPlanReportTitle"><header class="bulk-report-header"><div><div class="bulk-report-heading-line"><h3 id="bulkPlanReportTitle">${title}</h3><span class="bulk-report-phase ${completed ? 'is-completed' : ''}">${completed ? '已完成' : preparing ? '名单准备中' : '统计更新中'}</span></div><p>${escape(scopeText(report))} · ${number(totals.accounts)} 个账号</p></div><span class="bulk-report-updated">更新于 ${escape(timestamp(report.generated_at))}</span></header>${report.projection?.state && report.projection.state !== 'current' ? `<p class="bulk-report-sync" role="status">${report.projection.state === 'failed' ? '结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。' : '执行结果正在汇总，以下统计尚未收齐。'}</p>` : ''}<dl class="bulk-report-outcomes">${metric('成功',totals.success,'is-success')}${metric('失败',totals.failed,'is-danger')}${metric('部分成功',totals.partial_success,'is-warning')}${metric('待完成',totals.active)}</dl><div class="bulk-report-outcome-note"><span>已结束 ${number(totals.completed)} / ${number(totals.accounts)} 个</span><span>未执行 ${number(totals.not_executed)} 个</span><span>已取消 ${number(totals.cancelled)} 个</span></div><div class="bulk-report-execution">${timingMarkup}${taskMarkup}</div>${distributions}${moreStats}</section>`;
  }
  function loading(operationKey) {
    const title = `${operationNames[operationKey] || '批次'}报告`;
    return `<section class="bulk-plan-report bulk-report-placeholder" aria-label="${escape(title)}"><h3>${escape(title)}</h3><p role="status">正在汇总本次执行结果…</p></section>`;
  }
  function error(message = '暂时无法读取报告，请刷新重试。', operationKey) {
    const title = `${operationNames[operationKey] || '批次'}报告`;
    return `<section class="bulk-plan-report bulk-report-placeholder" aria-label="${escape(title)}"><h3>${escape(title)}</h3><p role="alert">${escape(message)}</p></section>`;
  }
  return {render, loading, error};
})();
