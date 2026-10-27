// ---------- 概览 ----------
const OVERVIEW_PREFERENCE_KEY = 'gpt_console_overview_preferences_v1';
const OVERVIEW_REGIONS = ['metrics', 'panels'];
let LAST_DASHBOARD_DATA = null;
let overviewDraggedCardId = '';
let overviewPageDragState = null;
let overviewCustomizerOpen = false;
let overviewResizeState = null;

function emailSupplyValue(supply, key) {
  const value = supply?.[key];
  return Number.isInteger(value) && value >= 0 ? value : supply?.status === 'error' ? '读取失败' : '未知';
}

function emailSupplyHint(supply) {
  return `仅统计本地库存；用完后请手动导入邮箱。Email Butler 仅提供收码连接${supply?.reason ? `；${supply.reason}` : ''}`;
}

function renderRegistrationEmailSupply(supply) {
  const hint = emailSupplyHint(supply);
  for (const [selector, key] of [['#statOutlook', 'total'], ['#statAvailable', 'available'], ['#statUsed', 'used'], ['#statFailed', 'failed']]) {
    const node = $(selector);
    if (node) { node.textContent = emailSupplyValue(supply, key); node.title = hint; }
  }
  const scope = $('#registrationEmailSupplyHint');
  if (scope) scope.textContent = hint;
}

async function loadSummary() {
  if (summaryLoading) return;
  summaryLoading = true;
  try {
    const s = await apiCached('/api/summary', {}, 3000);
    $('#statAccounts').textContent = s.accounts;
    renderRegistrationEmailSupply(s.email_supply);
  } catch(e) { renderRegistrationEmailSupply({status: 'error', reason: '本地库存读取失败，请稍后重试'}); }
  finally { summaryLoading = false; }
}

function overviewCapability(...path) {
  if (typeof CAPABILITIES === 'undefined') return null;
  let current = CAPABILITIES;
  for (const key of path) {
    if (!current || typeof current !== 'object') return null;
    current = current[key];
  }
  return current && typeof current.enabled === 'boolean' ? current.enabled : null;
}

function overviewEmailSources(data) {
  const localSources = data?.email?.supply?.sources;
  if (Array.isArray(localSources)) return localSources.filter(source => source?.kind === 'local_pool');
  const sources = Array.isArray(data?.email?.sources) ? data.email.sources : [];
  return sources.filter(source => {
    if (!source || source.enabled !== true) return false;
    const capability = overviewCapability('email_sources', source.source);
    return capability === null ? true : capability;
  });
}

function overviewLocalPools(data) {
  return overviewEmailSources(data).filter(source => source.kind === 'local_pool');
}

function overviewProxyAvailable(data) {
  const platform = String(data?.proxy?.platform || 'none').trim().toLowerCase();
  if (!platform || platform === 'none' || platform === 'direct') return false;
  const capability = overviewCapability('proxy', 'registration');
  return capability === null ? true : capability;
}

function overviewJobsAvailable(data) {
  const counts = data?.jobs?.counts || {};
  const active = Number(counts.running || 0) + Number(counts.pending || 0) + Number(counts.stopping || 0);
  if (Number(data?.jobs?.total || 0) <= 0 && active <= 0) return false;
  const capability = overviewCapability('features', 'register');
  return capability === null ? true : capability;
}

function overviewCardAvailable(card, data) {
  try { return Boolean(card.available(data)); } catch (_) { return false; }
}

function overviewDragHandle(label) {
  return `<span class="overview-card-drag" role="button" tabindex="0" aria-label="拖动${attrEsc(label)}卡片排序，或使用方向键调整顺序" title="拖动排序；方向键调整顺序">
    <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="5" cy="3" r="1"/><circle cx="11" cy="3" r="1"/><circle cx="5" cy="8" r="1"/><circle cx="11" cy="8" r="1"/><circle cx="5" cy="13" r="1"/><circle cx="11" cy="13" r="1"/></svg>
  </span>`;
}

function overviewResizeHandle(label) {
  return `<button type="button" class="overview-resize-handle" data-overview-resize aria-label="拖动调整${attrEsc(label)}卡片宽高；方向键可调整" title="拖动调整宽高；方向键调整">
    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 14l8-8M10 14l4-4"/></svg>
  </button>`;
}

function dashboardMetric(id, label, value, hint, color, size = 'normal', height = 0) {
  return `<article class="overview-metric" data-overview-card="${attrEsc(id)}" data-overview-size="${attrEsc(size)}" style="--metric-color:${attrEsc(color)};${height ? `min-height:${height}px` : ''}">
    <div class="overview-metric-top"><span>${esc(label)}</span><div class="overview-card-tools"><i class="overview-metric-dot" aria-hidden="true"></i>${overviewDragHandle(label)}</div></div>
    <strong>${esc(value)}</strong><small>${esc(hint)}</small>${overviewResizeHandle(label)}
  </article>`;
}

function jobStatusLabel(status) {
  return ({pending:'排队',running:'运行中',success:'成功',failed:'失败',partial_success:'部分成功',stopped:'已停止',cancelled:'已取消'})[status] || status || '未知';
}

function overviewMoreSummary(count, unit, density, paired = false, suffix = '，进入详情查看') {
  return count > 0 ? `<div class="overview-more-summary overview-more-summary--${density}${paired ? ' overview-more-summary--paired' : ''}">另有 ${esc(count)} ${esc(unit)}${esc(suffix)}</div>` : '';
}

function overviewDensityForHeight(height) {
  if (!height) return 'normal';
  return height < 220 ? 'minimal' : height < 300 ? 'compact' : 'normal';
}

const OVERVIEW_CARD_REGISTRY = [
  {
    id: 'metric-accounts', region: 'metrics', label: '有效账号',
    available: data => Number(data?.accounts?.total || 0) > 0,
    render: (data, preferences) => dashboardMetric('metric-accounts', '有效账号', data.accounts.active || 0, `归档 ${data.accounts.archived || 0}`, '#5b5ce2', preferences?.sizes?.['metric-accounts'], preferences?.heights?.['metric-accounts']),
  },
  {
    id: 'metric-email', region: 'metrics', label: '本地可用邮箱',
    available: data => overviewEmailSources(data).length > 0,
    render: (data, preferences) => {
      const supply = data.email.supply;
      return dashboardMetric('metric-email', '本地可用邮箱', emailSupplyValue(supply, 'available'), emailSupplyHint(supply), '#2dbb8a', preferences?.sizes?.['metric-email'], preferences?.heights?.['metric-email']);
    },
  },
  {
    id: 'metric-jobs', region: 'metrics', label: '运行任务',
    available: overviewJobsAvailable,
    render: (data, preferences) => {
      const counts = data.jobs.counts || {};
      const active = Number(counts.running || 0) + Number(counts.pending || 0) + Number(counts.stopping || 0);
      return dashboardMetric('metric-jobs', '运行任务', active, `累计任务 ${data.jobs.total || 0}`, '#e6a23c', preferences?.sizes?.['metric-jobs'], preferences?.heights?.['metric-jobs']);
    },
  },
  {
    id: 'metric-codex', region: 'metrics', label: 'Codex 凭证',
    available: data => Number(data?.codex?.total || 0) > 0,
    render: (data, preferences) => dashboardMetric('metric-codex', 'Codex 凭证', data.codex.total || 0, `待导出 ${data.codex.pending || 0}`, '#377dff', preferences?.sizes?.['metric-codex'], preferences?.heights?.['metric-codex']),
  },
  {
    id: 'metric-proxy', region: 'metrics', label: '活跃出口',
    available: overviewProxyAvailable,
    render: (data, preferences) => dashboardMetric('metric-proxy', '活跃出口', data.proxy.active_leases || 0, `代理平台 ${overviewProxyPlatformLabel(data.proxy.platform)}`, '#a855f7', preferences?.sizes?.['metric-proxy'], preferences?.heights?.['metric-proxy']),
  },
  {
    id: 'panel-email', region: 'panels', label: '邮箱资源 · 本地库存',
    available: data => overviewEmailSources(data).length > 0,
    action: {type: 'go', value: 'outlook', label: '管理邮箱'},
    render: data => {
      const sources = overviewEmailSources(data);
      return `<div class="overview-source-grid">${sources.map((source, index) => {
      const value = emailSupplyValue(source, 'available');
      const detail = `本地总数 ${emailSupplyValue(source, 'total')} · 已用 ${emailSupplyValue(source, 'used')} · 失败 ${emailSupplyValue(source, 'failed')}`;
      return `<article class="overview-source${index >= 2 ? ' overview-density-secondary' : ''}${index >= 1 ? ' overview-density-minimal-extra' : ''}">
        <div class="overview-source-top"><span class="overview-source-name" title="${attrEsc(source.label)}">${esc(source.label)}</span><i class="overview-source-state is-on" aria-hidden="true"></i></div>
        <strong>${esc(value)}</strong>
        <small>${esc(detail)}</small>
      </article>`;
      }).join('')}</div>${overviewMoreSummary(sources.length - 2, '个来源', 'compact', true)}${overviewMoreSummary(sources.length - 1, '个来源', 'minimal')}`;
    },
  },
  {
    id: 'panel-proxy', region: 'panels', label: '网络出口 · 代理与网络',
    available: overviewProxyAvailable,
    action: {type: 'config', value: '代理与网络', label: '配置'},
    render: data => {
      const proxy = data.proxy || {};
      const leases = (proxy.leases || []).slice(0, 3);
      const totalLeases = Math.max(Number(proxy.active_leases || 0), (proxy.leases || []).length);
      return `<div class="overview-proxy-grid">
        <div class="overview-proxy-item"><span>系统代理平台</span><strong>${esc(overviewProxyPlatformLabel(proxy.platform))}</strong></div>
        <div class="overview-proxy-item"><span>活跃出口</span><strong>${esc(proxy.active_leases || 0)} 个</strong></div>
      </div><div class="overview-exit-list">${leases.map((lease, index) => `<div class="overview-exit-row${index >= 1 ? ' overview-density-secondary' : ''}">
        <i aria-hidden="true"></i><span title="${attrEsc(lease.endpoint || lease.exit_ip || '')}">${esc(lease.endpoint || lease.exit_ip || '活跃出口')}</span><small>${esc(lease.region || lease.provider || '')}</small>
      </div>`).join('') || '<div class="muted">当前没有活跃代理出口</div>'}</div>${overviewMoreSummary(totalLeases - 1, '个出口', 'compact', false, '')}`;
    },
  },
  {
    id: 'panel-jobs', region: 'panels', label: '注册流水线 · 今日任务结果',
    available: overviewJobsAvailable,
    action: {type: 'go', value: 'register', label: '查看全部'},
    render: data => {
      const todayCounts = data.jobs.today_counts || {};
      const todayRows = [
        ['success', '成功', todayCounts.success || 0],
        ['partial_success', '部分成功', todayCounts.partial_success || 0],
        ['failed', '失败', todayCounts.failed || 0],
      ];
      return `<div class="overview-job-list">${todayRows.map(([status, label, count], index) => `<div class="overview-job-row${status === 'partial_success' || (index > 0 && !count) ? ' overview-density-secondary' : ''}">
        ${pill(status)}<div class="overview-job-main"><strong>${esc(count)} 个任务</strong><small>${esc(data.jobs.today || '今天')} · ${esc(label)}</small></div>
      </div>`).join('')}</div>${Number(todayCounts.partial_success || 0) ? `<div class="overview-more-summary overview-more-summary--compact">部分成功 ${esc(todayCounts.partial_success)}</div>` : ''}`;
    },
  },
  {
    id: 'panel-accounts', region: 'panels', label: '账号资产 · 套餐分布',
    available: data => Object.keys(data?.accounts?.plans || {}).length > 0,
    action: {type: 'go', value: 'accounts', label: '管理账号'},
    render: data => {
      const plans = Object.entries(data.accounts.plans || {}).sort((a,b) => Number(b[1]) - Number(a[1]));
      const planMax = Math.max(1, ...plans.map(([,count]) => Number(count || 0)));
      const planLabels = {
        free:'Free', free_trial_eligible:'Free · Plus 免费试用', free_half_price_eligible:'Free · Plus 半价',
        free_discount_eligible:'Free · Plus 其他折扣', free_promo_unknown:'Free · 优惠待复查',
        plus:'Plus', pro:'Pro', team:'Team', go:'Go', unknown:'未检测',
      };
      return `<div class="overview-plan-list">${plans.map(([plan,count], index) => `<div class="overview-plan-row${index >= 3 ? ' overview-density-secondary' : ''}${index >= 2 ? ' overview-density-minimal-extra' : ''}">
        <span>${esc(planLabels[plan] || plan)}</span><div class="overview-plan-bar"><i style="width:${Math.max(4, Math.round(Number(count || 0) / planMax * 100))}%"></i></div><strong>${esc(count)}</strong>
      </div>`).join('')}</div>${overviewMoreSummary(plans.length - 3, '种套餐', 'compact', true)}${overviewMoreSummary(plans.length - 2, '种套餐', 'minimal')}`;
    },
  },
  {
    id: 'panel-task-queue', region: 'panels', label: '注册流水线 · 当前任务队列',
    available: data => overviewJobsAvailable(data) && ['pending', 'running', 'stopping'].some(key => Number(data.jobs.counts?.[key] || 0) > 0),
    action: {type: 'go', value: 'register', label: '查看任务'},
    render: data => {
      const counts = data.jobs.counts || {};
      return `<div class="overview-status-grid">
        <div class="overview-status-item"><span>待处理</span><strong>${esc(counts.pending || 0)}</strong></div>
        <div class="overview-status-item"><span>运行中</span><strong>${esc(counts.running || 0)}</strong></div>
        <div class="overview-status-item overview-density-secondary"><span>停止中</span><strong>${esc(counts.stopping || 0)}</strong></div>
      </div>${Number(counts.stopping || 0) ? `<div class="overview-more-summary overview-more-summary--compact">停止中 ${esc(counts.stopping)}</div>` : ''}`;
    },
  },
  {
    id: 'panel-job-history', region: 'panels', label: '注册流水线 · 累计任务结果',
    available: data => overviewJobsAvailable(data) && ['success', 'partial_success', 'failed', 'stopped', 'cancelled'].some(key => Number(data.jobs.counts?.[key] || 0) > 0),
    action: {type: 'go', value: 'register', label: '查看任务'},
    render: data => {
      const counts = data.jobs.counts || {};
      const stopped = Number(counts.stopped || 0) + Number(counts.cancelled || 0);
      return `<div class="overview-status-grid">
        <div class="overview-status-item"><span>成功</span><strong>${esc(counts.success || 0)}</strong></div>
        <div class="overview-status-item"><span>失败</span><strong>${esc(counts.failed || 0)}</strong></div>
        <div class="overview-status-item overview-density-secondary"><span>部分成功</span><strong>${esc(counts.partial_success || 0)}</strong></div>
        <div class="overview-status-item overview-density-secondary"><span>已停止或取消</span><strong>${esc(stopped)}</strong></div>
      </div>${Number(counts.partial_success || 0) || stopped ? `<div class="overview-more-summary overview-more-summary--compact">部分成功 ${esc(counts.partial_success || 0)} · 已停止或取消 ${esc(stopped)}</div>` : ''}`;
    },
  },
  {
    id: 'panel-email-health', region: 'panels', label: '邮箱资源 · 邮箱池状态',
    available: data => overviewLocalPools(data).some(source => Number(source.total || 0) > 0),
    action: {type: 'go', value: 'outlook', label: '查看邮箱'},
    render: data => {
      const pools = overviewLocalPools(data);
      const count = key => pools.reduce((total, source) => total + Number(source[key] || 0), 0);
      return `<div class="overview-status-grid">
        <div class="overview-status-item"><span>可用邮箱</span><strong>${esc(count('available'))}</strong></div>
        <div class="overview-status-item overview-density-secondary"><span>已用邮箱</span><strong>${esc(count('used'))}</strong></div>
        <div class="overview-status-item"><span>失败邮箱</span><strong>${esc(count('failed'))}</strong></div>
        <div class="overview-status-item overview-density-secondary"><span>停用邮箱</span><strong>${esc(count('disabled'))}</strong></div>
      </div><div class="overview-more-summary overview-more-summary--compact">已用 ${esc(count('used'))} · 停用 ${esc(count('disabled'))}</div>`;
    },
  },
  {
    id: 'panel-codex-progress', region: 'panels', label: 'Codex 授权 · 凭证处理进度',
    available: data => Number(data?.codex?.total || 0) > 0,
    action: {type: 'go', value: 'codex', label: '查看凭证'},
    render: data => `<div class="overview-status-grid">
      <div class="overview-status-item"><span>已导出</span><strong>${esc(data.codex.exported || 0)}</strong></div>
      <div class="overview-status-item"><span>待导出</span><strong>${esc(data.codex.pending || 0)}</strong></div>
      <div class="overview-status-item overview-density-secondary"><span>账号 Codex 就绪</span><strong>${esc(data.accounts?.codex_ready || 0)}</strong></div>
    </div><div class="overview-more-summary overview-more-summary--compact">账号 Codex 就绪 ${esc(data.accounts?.codex_ready || 0)}</div>`,
  },
];

function overviewProxyPlatformLabel(platform) {
  const value = String(platform || '').trim();
  return ({'1024proxy':'1024Proxy','711proxy':'711Proxy',manual:'手动代理池','1024':'1024Proxy',pool:'静态代理池',none:'直连',direct:'直连'})[value.toLowerCase()] || value || '未配置';
}

function overviewRegistryCard(id) {
  return OVERVIEW_CARD_REGISTRY.find(card => card.id === id) || null;
}

function overviewAvailableCardIds(data) {
  return OVERVIEW_REGIONS.reduce((result, region) => {
    result[region] = OVERVIEW_CARD_REGISTRY
      .filter(card => card.region === region && overviewCardAvailable(card, data))
      .map(card => card.id);
    return result;
  }, {});
}

function normalizeOverviewPreferences(raw, availableIds) {
  const source = raw && typeof raw === 'object' ? raw : {};
  const known = new Set(OVERVIEW_REGIONS.flatMap(region => availableIds?.[region] || []));
  const hidden = Array.isArray(source.hidden)
    ? [...new Set(source.hidden.filter(id => known.has(id)))]
    : [];
  const order = {};
  for (const region of OVERVIEW_REGIONS) {
    const available = Array.isArray(availableIds?.[region]) ? availableIds[region] : [];
    const saved = Array.isArray(source.order?.[region]) ? source.order[region] : [];
    order[region] = [...new Set([
      ...saved.filter(id => available.includes(id)),
      ...available.filter(id => !saved.includes(id)),
    ])];
  }
  const sizes = {};
  const heights = {};
  for (const id of known) {
    const fallback = 'normal';
    sizes[id] = ['normal', 'wide', 'full'].includes(source.sizes?.[id]) ? source.sizes[id] : fallback;
    const height = Number(source.heights?.[id]);
    if (Number.isFinite(height) && height >= 100 && height <= 800) heights[id] = Math.round(height);
  }
  return {order, hidden, sizes, heights};
}

function overviewStorage() {
  return typeof localStorage === 'undefined' ? null : localStorage;
}

function readOverviewPreferences(availableIds) {
  const storage = overviewStorage();
  if (!storage) return normalizeOverviewPreferences({}, availableIds);
  try {
    return normalizeOverviewPreferences(JSON.parse(storage.getItem(OVERVIEW_PREFERENCE_KEY) || '{}'), availableIds);
  } catch (_) {
    return normalizeOverviewPreferences({}, availableIds);
  }
}

function saveOverviewPreferences(preferences) {
  const storage = overviewStorage();
  if (!storage) return;
  try { storage.setItem(OVERVIEW_PREFERENCE_KEY, JSON.stringify(preferences)); } catch (_) {}
}

function overviewActionMarkup(action) {
  if (!action) return '';
  const dataAttribute = action.type === 'config' ? 'data-overview-config' : 'data-overview-go';
  return `<button type="button" ${dataAttribute}="${attrEsc(action.value)}">${esc(action.label)}</button>`;
}

function renderOverviewPanel(card, data, preferences) {
  const titleParts = card.label.split(' · ');
  const size = preferences?.sizes?.[card.id] || 'normal';
  const height = preferences?.heights?.[card.id];
  return `<section class="overview-panel" data-overview-card="${attrEsc(card.id)}" data-overview-size="${attrEsc(size)}" data-overview-density="${overviewDensityForHeight(height)}"${height ? ` style="min-height:${height}px"` : ''}>
    <div class="overview-panel-head">
      <div><span>${esc(titleParts[0])}</span><h3>${esc(titleParts.slice(1).join(' · '))}</h3></div>
      <div class="overview-card-tools">${overviewActionMarkup(card.action)}${overviewDragHandle(titleParts.slice(1).join(' · '))}</div>
    </div>
    ${card.render(data)}${overviewResizeHandle(titleParts.slice(1).join(' · '))}
  </section>`;
}

function overviewCustomizeItem(card, preferences) {
  const checked = !preferences.hidden.includes(card.id);
  return `<div class="overview-customizer-item" draggable="true" data-overview-custom-card="${attrEsc(card.id)}" data-overview-custom-region="${attrEsc(card.region)}">
    <span class="overview-drag-handle" aria-hidden="true">拖动</span>
    <label><input type="checkbox" data-overview-toggle="${attrEsc(card.id)}" ${checked ? 'checked' : ''}> <span>${esc(card.label)}</span></label>
    <div class="overview-customizer-move" role="group" aria-label="调整 ${attrEsc(card.label)} 顺序">
      <button type="button" data-overview-move="up" data-overview-move-id="${attrEsc(card.id)}" data-overview-move-region="${attrEsc(card.region)}">上移</button>
      <button type="button" data-overview-move="down" data-overview-move-id="${attrEsc(card.id)}" data-overview-move-region="${attrEsc(card.region)}">下移</button>
    </div>
  </div>`;
}

function renderOverviewCustomizer(data, availableIds, preferences) {
  const root = $('#overviewCustomizeList');
  if (!root) return;
  root.innerHTML = OVERVIEW_REGIONS.map(region => {
    const cards = preferences.order[region].map(overviewRegistryCard).filter(Boolean);
    const label = region === 'metrics' ? '指标卡片' : '详细卡片';
    return `<section class="overview-customizer-group" data-overview-custom-region-group="${region}">
      <div class="overview-customizer-group-head"><strong>${label}</strong><small>${cards.length} 张可用卡片</small></div>
      <div class="overview-customizer-items">${cards.map(card => overviewCustomizeItem(card, preferences)).join('') || '<div class="overview-customizer-empty">当前没有已启用且可展示的卡片</div>'}</div>
    </section>`;
  }).join('');
}

function overviewCardIdsForRender(data, preferences, region) {
  return preferences.order[region]
    .filter(id => !preferences.hidden.includes(id))
    .map(overviewRegistryCard)
    .filter(card => card && overviewCardAvailable(card, data));
}

function renderDashboard(data) {
  if (overviewPageDragState) finishOverviewPageDrag(true);
  LAST_DASHBOARD_DATA = data || {};
  const availableIds = overviewAvailableCardIds(LAST_DASHBOARD_DATA);
  const preferences = readOverviewPreferences(availableIds);
  const metricRoot = $('#overviewMetrics');
  const panelRoot = $('#overviewPanels');
  if (metricRoot) metricRoot.innerHTML = overviewCardIdsForRender(LAST_DASHBOARD_DATA, preferences, 'metrics').map(card => card.render(LAST_DASHBOARD_DATA, preferences)).join('');
  if (panelRoot) panelRoot.innerHTML = overviewCardIdsForRender(LAST_DASHBOARD_DATA, preferences, 'panels').map(card => renderOverviewPanel(card, LAST_DASHBOARD_DATA, preferences)).join('');
  renderOverviewCustomizer(LAST_DASHBOARD_DATA, availableIds, preferences);
}

function updateOverviewPreferences(mutator) {
  if (!LAST_DASHBOARD_DATA) return;
  const availableIds = overviewAvailableCardIds(LAST_DASHBOARD_DATA);
  const preferences = readOverviewPreferences(availableIds);
  mutator(preferences);
  const normalized = normalizeOverviewPreferences(preferences, availableIds);
  saveOverviewPreferences(normalized);
  renderDashboard(LAST_DASHBOARD_DATA);
}

function moveOverviewCard(region, cardId, direction) {
  updateOverviewPreferences(preferences => {
    const order = preferences.order[region] || [];
    const index = order.indexOf(cardId);
    const nextIndex = direction === 'up' ? index - 1 : index + 1;
    if (index < 0 || nextIndex < 0 || nextIndex >= order.length) return;
    [order[index], order[nextIndex]] = [order[nextIndex], order[index]];
  });
}

function reorderOverviewCard(preferences, region, sourceId, targetId, after = false) {
  const order = preferences.order[region] || [];
  const from = order.indexOf(sourceId);
  if (from < 0 || !order.includes(targetId) || sourceId === targetId) return;
  order.splice(from, 1);
  const to = order.indexOf(targetId);
  order.splice(to + (after ? 1 : 0), 0, sourceId);
}

function toggleOverviewCard(cardId, visible) {
  updateOverviewPreferences(preferences => {
    preferences.hidden = preferences.hidden.filter(id => id !== cardId);
    if (!visible) preferences.hidden.push(cardId);
  });
}

function resetOverviewLayout() {
  const storage = overviewStorage();
  if (storage) {
    try { storage.removeItem(OVERVIEW_PREFERENCE_KEY); } catch (_) {}
  }
  if (LAST_DASHBOARD_DATA) renderDashboard(LAST_DASHBOARD_DATA);
  showToast('已恢复默认布局');
}

function openOverviewCustomizer() {
  const panel = $('#overviewCustomizer');
  const backdrop = $('#overviewCustomizerBackdrop');
  if (!panel || !backdrop) return;
  overviewCustomizerOpen = true;
  panel.classList.remove('hidden');
  panel.setAttribute('aria-hidden', 'false');
  backdrop.classList.remove('hidden');
  document.body.classList.add('overview-customizer-open');
  $('#btnCustomizeOverview')?.setAttribute('aria-expanded', 'true');
  panel.querySelector?.('input, button')?.focus();
}

function closeOverviewCustomizer() {
  const panel = $('#overviewCustomizer');
  const backdrop = $('#overviewCustomizerBackdrop');
  if (!panel || !backdrop) return;
  overviewCustomizerOpen = false;
  panel.classList.add('hidden');
  panel.setAttribute('aria-hidden', 'true');
  backdrop.classList.add('hidden');
  document.body.classList.remove('overview-customizer-open');
  $('#btnCustomizeOverview')?.setAttribute('aria-expanded', 'false');
  $('#btnCustomizeOverview')?.focus();
}

function handleOverviewCardDrop(targetId, targetRegion, after = false, sourceId = overviewDraggedCardId) {
  if (!sourceId || !LAST_DASHBOARD_DATA) return;
  const sourceCard = overviewRegistryCard(sourceId);
  if (!sourceCard || sourceCard.region !== targetRegion || sourceCard.id === targetId) return;
  updateOverviewPreferences(preferences => reorderOverviewCard(preferences, targetRegion, sourceId, targetId, after));
}

function startOverviewPageDrag(event, handle) {
  if (event.button !== 0 || overviewPageDragState || overviewResizeState) return;
  const card = handle.closest('[data-overview-card]');
  const grid = card?.parentElement;
  const root = $('#tab-overview');
  if (!card || !grid || !root) return;
  overviewPageDragState = {
    root, grid, card, pointerId: event.pointerId,
    region: grid.id === 'overviewMetrics' ? 'metrics' : 'panels',
    startX: event.clientX, startY: event.clientY,
    lastX: event.clientX, lastY: event.clientY,
    originalNodes: [...grid.children], ghost: null, scrollFrame: null,
  };
  root.setPointerCapture(event.pointerId);
  event.preventDefault();
}

function overviewPageDropAfter(state, target, clientX, clientY) {
  const rect = target.getBoundingClientRect();
  const sourceRect = state.card.getBoundingClientRect();
  const singleColumn = getComputedStyle(state.grid).gridTemplateColumns.split(/\s+/).length === 1;
  const otherRow = Math.abs(sourceRect.top - rect.top) > 8;
  return singleColumn || otherRow || target.dataset.overviewSize === 'full'
    ? clientY >= rect.top + rect.height / 2
    : clientX >= rect.left + rect.width / 2;
}

function previewOverviewPageOrder(state, event) {
  const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-overview-card]');
  if (!target || target === state.card || target.parentElement !== state.grid) return;
  const after = overviewPageDropAfter(state, target, event.clientX, event.clientY);
  const reference = after ? target.nextElementSibling : target;
  if (reference === state.card || state.card.nextElementSibling === reference) return;
  const cards = [...state.grid.children];
  for (const node of cards) node.getAnimations?.().forEach(animation => animation.cancel());
  const before = new Map(cards.map(node => [node, node.getBoundingClientRect()]));
  state.grid.insertBefore(state.card, reference);
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
  for (const node of cards) {
    if (node === state.card) continue;
    const previous = before.get(node);
    const next = node.getBoundingClientRect();
    const dx = previous.left - next.left;
    const dy = previous.top - next.top;
    if (dx || dy) node.animate?.([
      {transform: `translate(${dx}px, ${dy}px)`},
      {transform: 'translate(0, 0)'},
    ], {duration: 180, easing: 'cubic-bezier(.2,.75,.2,1)'});
  }
}

function continueOverviewDragScroll(state) {
  state.scrollFrame = null;
  if (overviewPageDragState !== state || !state.ghost) return;
  const margin = 64;
  const y = state.lastY;
  const speed = y >= 0 && y < margin ? -Math.ceil((margin - y) / 4)
    : y <= window.innerHeight && y > window.innerHeight - margin ? Math.ceil((y - window.innerHeight + margin) / 4) : 0;
  if (!speed) return;
  const scrolling = document.scrollingElement;
  const before = scrolling?.scrollTop;
  window.scrollBy(0, speed);
  if (scrolling?.scrollTop === before) return;
  previewOverviewPageOrder(state, {clientX: state.lastX, clientY: state.lastY});
  state.scrollFrame = requestAnimationFrame(() => continueOverviewDragScroll(state));
}

function moveOverviewPageDrag(event) {
  const state = overviewPageDragState;
  if (!state || event.pointerId !== state.pointerId) return;
  state.lastX = event.clientX;
  state.lastY = event.clientY;
  const dx = event.clientX - state.startX;
  const dy = event.clientY - state.startY;
  if (!state.ghost && Math.hypot(dx, dy) < 5) return;
  if (!state.ghost) {
    const rect = state.card.getBoundingClientRect();
    const ghost = state.card.cloneNode(true);
    ghost.classList.add('overview-drag-ghost');
    ghost.setAttribute('aria-hidden', 'true');
    Object.assign(ghost.style, {left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`});
    document.body.appendChild(ghost);
    state.ghost = ghost;
    state.card.classList.add('is-drag-placeholder');
  }
  state.ghost.style.transform = `translate3d(${dx}px, ${dy}px, 0)`;
  previewOverviewPageOrder(state, event);
  if (!state.scrollFrame) state.scrollFrame = requestAnimationFrame(() => continueOverviewDragScroll(state));
}

function finishOverviewPageDrag(cancelled = false, pointerId = null) {
  const state = overviewPageDragState;
  if (!state || (pointerId !== null && pointerId !== state.pointerId)) return;
  overviewPageDragState = null;
  if (state.scrollFrame) cancelAnimationFrame(state.scrollFrame);
  if (state.root.hasPointerCapture?.(state.pointerId)) state.root.releasePointerCapture(state.pointerId);
  state.ghost?.remove();
  state.card.classList.remove('is-drag-placeholder');
  if (cancelled) {
    state.grid.replaceChildren(...state.originalNodes);
    return;
  }
  if (!state.ghost) return;
  const visibleOrder = [...state.grid.children].map(card => card.dataset.overviewCard);
  updateOverviewPreferences(preferences => {
    const previousOrder = preferences.order[state.region] || [];
    preferences.order[state.region] = [...visibleOrder, ...previousOrder.filter(id => !visibleOrder.includes(id))];
  });
}

function overviewResizeSize(region, columns, span) {
  if (span <= 1) return 'normal';
  if (span >= Math.min(columns, region === 'metrics' ? 4 : 3) && columns >= 3) return 'full';
  return 'wide';
}

function startOverviewResize(event, handle) {
  if (overviewResizeState || overviewPageDragState) return;
  const card = handle.closest('[data-overview-card]');
  const grid = card?.parentElement;
  if (!card || !grid) return;
  const columns = getComputedStyle(grid).gridTemplateColumns.split(/\s+/).length;
  const gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
  const region = grid.id === 'overviewMetrics' ? 'metrics' : 'panels';
  const cardWidth = card.getBoundingClientRect().width;
  const gridWidth = grid.getBoundingClientRect().width;
  overviewResizeState = {
    card, handle, region, id: card.dataset.overviewCard, columns, gap, pointerId: event.pointerId,
    columnWidth: (gridWidth - gap * (columns - 1)) / columns,
    startX: event.clientX, startY: event.clientY,
    startWidth: cardWidth, startHeight: card.getBoundingClientRect().height,
    startSize: card.dataset.overviewSize, startDensity: card.dataset.overviewDensity, startMinHeight: card.style.minHeight,
    changed: false,
  };
  handle.setPointerCapture(event.pointerId);
  card.classList.add('is-resizing');
  event.preventDefault();
}

function moveOverviewResize(event) {
  const state = overviewResizeState;
  if (!state || event.pointerId !== state.pointerId) return;
  const width = state.startWidth + event.clientX - state.startX;
  const span = Math.max(1, Math.min(state.columns, Math.round((width + state.gap) / (state.columnWidth + state.gap))));
  const size = overviewResizeSize(state.region, state.columns, span);
  state.card.dataset.overviewSize = size;
  if (Math.abs(event.clientY - state.startY) > 4) {
    const height = Math.max(160, Math.min(800, Math.round(state.startHeight + event.clientY - state.startY)));
    state.card.style.minHeight = `${height}px`;
    if (state.region === 'panels') state.card.dataset.overviewDensity = overviewDensityForHeight(height);
  }
  state.changed = state.changed || Math.abs(event.clientX - state.startX) > 4 || Math.abs(event.clientY - state.startY) > 4;
}

function finishOverviewResize(cancelled = false, pointerId = null) {
  const state = overviewResizeState;
  if (!state || (pointerId !== null && pointerId !== state.pointerId)) return;
  overviewResizeState = null;
  state.card.classList.remove('is-resizing');
  if (cancelled || !state.changed) {
    state.card.dataset.overviewSize = state.startSize;
    if (state.region === 'panels') state.card.dataset.overviewDensity = state.startDensity;
    state.card.style.minHeight = state.startMinHeight;
    return;
  }
  updateOverviewPreferences(preferences => {
    preferences.sizes[state.id] = state.card.dataset.overviewSize;
    const height = parseInt(state.card.style.minHeight, 10);
    if (Number.isFinite(height)) preferences.heights[state.id] = height;
  });
}

$('#btnRefreshOverview')?.addEventListener('click', loadDashboard);
$('#btnCustomizeOverview')?.addEventListener('click', openOverviewCustomizer);
$('#btnCloseOverviewCustomize')?.addEventListener('click', closeOverviewCustomizer);
$('#overviewCustomizerBackdrop')?.addEventListener('click', closeOverviewCustomizer);
$('#btnResetOverviewLayout')?.addEventListener('click', resetOverviewLayout);
$('#tab-overview')?.addEventListener('click', e => {
  const go = e.target.closest('[data-overview-go]');
  if (go) { activateTab(go.dataset.overviewGo); return; }
  const config = e.target.closest('[data-overview-config]');
  if (config) { openConfigGroup(config.dataset.overviewConfig); return; }
  const move = e.target.closest('[data-overview-move]');
  if (move) moveOverviewCard(move.dataset.overviewMoveRegion, move.dataset.overviewMoveId, move.dataset.overviewMove);
});
$('#tab-overview')?.addEventListener('keydown', e => {
  const card = e.target.closest('[data-overview-card]');
  if (!card) return;
  const region = card.parentElement?.id === 'overviewMetrics' ? 'metrics' : 'panels';
  if (e.target.closest('.overview-card-drag') && ['ArrowLeft', 'ArrowUp', 'ArrowRight', 'ArrowDown'].includes(e.key)) {
    e.preventDefault();
    const id = card.dataset.overviewCard;
    moveOverviewCard(region, id, ['ArrowLeft', 'ArrowUp'].includes(e.key) ? 'up' : 'down');
    $('#tab-overview')?.querySelector(`[data-overview-card="${id}"] .overview-card-drag`)?.focus();
  }
  if (e.target.closest('[data-overview-resize]') && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
    e.preventDefault();
    const id = card.dataset.overviewCard;
    updateOverviewPreferences(preferences => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const options = ['normal', 'wide', 'full'];
        const index = options.indexOf(preferences.sizes[id]);
        preferences.sizes[id] = options[Math.max(0, Math.min(2, index + (e.key === 'ArrowRight' ? 1 : -1)))];
      } else {
        preferences.heights[id] = Math.max(160, Math.min(800, (preferences.heights[id] || Math.round(card.getBoundingClientRect().height)) + (e.key === 'ArrowDown' ? 40 : -40)));
      }
    });
    $('#tab-overview')?.querySelector(`[data-overview-card="${id}"] [data-overview-resize]`)?.focus();
  }
});
$('#tab-overview')?.addEventListener('pointerdown', e => {
  const resizeHandle = e.target.closest('[data-overview-resize]');
  if (resizeHandle) { startOverviewResize(e, resizeHandle); return; }
  const dragHandle = e.target.closest('.overview-card-drag');
  if (dragHandle) startOverviewPageDrag(e, dragHandle);
});
$('#tab-overview')?.addEventListener('pointermove', e => {
  moveOverviewResize(e);
  moveOverviewPageDrag(e);
});
$('#tab-overview')?.addEventListener('pointerup', e => {
  finishOverviewResize(false, e.pointerId);
  finishOverviewPageDrag(false, e.pointerId);
});
$('#tab-overview')?.addEventListener('pointercancel', e => {
  finishOverviewResize(true, e.pointerId);
  finishOverviewPageDrag(true, e.pointerId);
});
$('#tab-overview')?.addEventListener('change', e => {
  const toggle = e.target.closest('[data-overview-toggle]');
  if (toggle) toggleOverviewCard(toggle.dataset.overviewToggle, toggle.checked);
});
$('#overviewCustomizeList')?.addEventListener('dragstart', e => {
  const item = e.target.closest('[data-overview-custom-card]');
  if (!item) return;
  overviewDraggedCardId = item.dataset.overviewCustomCard;
  item.classList.add('is-dragging');
  e.dataTransfer?.setData('text/plain', overviewDraggedCardId);
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
});
$('#overviewCustomizeList')?.addEventListener('dragover', e => {
  const item = e.target.closest('[data-overview-custom-card]');
  if (!item) return;
  e.preventDefault();
  item.classList.add('is-drag-over');
});
$('#overviewCustomizeList')?.addEventListener('dragleave', e => {
  e.target.closest('[data-overview-custom-card]')?.classList.remove('is-drag-over');
});
$('#overviewCustomizeList')?.addEventListener('drop', e => {
  const item = e.target.closest('[data-overview-custom-card]');
  if (!item) return;
  e.preventDefault();
  item.classList.remove('is-drag-over');
  handleOverviewCardDrop(item.dataset.overviewCustomCard, item.dataset.overviewCustomRegion);
  overviewDraggedCardId = '';
});
$('#overviewCustomizeList')?.addEventListener('dragend', e => {
  e.target.closest('[data-overview-custom-card]')?.classList.remove('is-dragging', 'is-drag-over');
  overviewDraggedCardId = '';
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && overviewPageDragState) finishOverviewPageDrag(true);
  if (e.key === 'Escape' && overviewCustomizerOpen) closeOverviewCustomizer();
});

async function loadDashboard() {
  if (dashboardLoading) return;
  dashboardLoading = true;
  const button = $('#btnRefreshOverview');
  if (button) button.disabled = true;
  try {
    const [data, capabilities] = await Promise.all([
      api('/api/dashboard'),
      apiCached('/api/capabilities', {}, 30000).catch(() => null),
    ]);
    if (capabilities && typeof CAPABILITIES !== 'undefined') CAPABILITIES = capabilities;
    renderDashboard(data);
    markViewReady('overview');
  }
  catch(e) { showToast('总览加载失败: ' + e.message); }
  finally {
    dashboardLoading = false;
    if (button) button.disabled = false;
  }
}
