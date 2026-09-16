/*
 * Independent proxy/traffic page contract.
 *
 * Task 2 supplies one authenticated read-only response from this endpoint.
 * It contains persistent lease correlations and browser traffic summaries only;
 * no proxy connection fields or request payload data belong in this contract.
 */
const PROXY_TRAFFIC_API = Object.freeze({
  url: '/api/proxy-traffic',
  query: ['q', 'provider', 'state', 'purpose', 'view', 'limit'],
  response: ['current_leases', 'history', 'traffic'],
});

(() => {
  const VIEWS = {
    current: { body: 'proxyTrafficCurrentBody', panel: 'proxyTrafficCurrentView', label: '当前租约' },
    history: { body: 'proxyTrafficHistoryBody', panel: 'proxyTrafficHistoryView', label: '线路历史' },
    traffic: { body: 'proxyTrafficTrafficBody', panel: 'proxyTrafficTrafficView', label: '浏览器流量' },
  };
  const VIEW_KEYS = { current: 'current_leases', history: 'history', traffic: 'traffic' };
  const STATUS_LABELS = {
    active: '活跃', leased: '已租用', pending: '待验证', recent: '隔离中', released: '已释放',
    expired: '已过期', failed: '失败', unavailable: '未采集', unknown: '待确认',
  };
  const PURPOSE_LABELS = {
    registration: '注册', 'email-change': '邮箱换绑', email_change: '邮箱换绑',
    'account-action': '账号操作', live_check: '查活', 'live-check': '查活',
    plan_check: '查套餐', 'plan-check': '查套餐', refresh_at: '刷新 AT', 'refresh-at': '刷新 AT',
    codex: 'Codex', unknown: '未标注',
  };
  const state = {
    activeView: 'current',
    loading: false,
    requestId: 0,
    payload: { current_leases: [], history: [], traffic: [], facets: {} },
    filters: { q: '', provider: '', state: '', purpose: '' },
  };

  function byId(id) { return document.getElementById(id); }
  function text(value, fallback = '-') {
    const valueText = value == null ? '' : String(value).trim();
    return valueText || fallback;
  }
  function safeText(value, fallback = '-') {
    return typeof esc === 'function' ? esc(text(value, fallback)) : text(value, fallback);
  }
  function formatNumber(value) {
    const amount = Number(value || 0);
    return Number.isFinite(amount) ? new Intl.NumberFormat('zh-CN').format(amount) : '0';
  }
  function formatBytes(value) {
    const amount = Number(value || 0);
    if (!Number.isFinite(amount) || amount <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(amount) / Math.log(1024)), units.length - 1);
    const shown = amount / (1024 ** index);
    return `${shown >= 10 || index === 0 ? shown.toFixed(0) : shown.toFixed(1)} ${units[index]}`;
  }
  function formatDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return safeText(value);
    return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  }
  function formatDuration(value) {
    const milliseconds = Number(value || 0);
    if (!Number.isFinite(milliseconds) || milliseconds <= 0) return '-';
    if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
    const seconds = milliseconds / 1000;
    return `${seconds >= 10 ? seconds.toFixed(0) : seconds.toFixed(1)} s`;
  }
  function statusLabel(value) {
    const key = String(value || 'unknown').toLowerCase();
    return STATUS_LABELS[key] || key || '待确认';
  }
  function purposeLabel(value) {
    const key = String(value || 'unknown').toLowerCase();
    return PURPOSE_LABELS[key] || key || '未标注';
  }
  function statusMarkup(value) {
    const key = String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]/g, '-');
    return `<span class="proxy-traffic-status proxy-traffic-status--${key}">${safeText(statusLabel(value))}</span>`;
  }
  function cell(main, sub = '') {
    return `<span class="proxy-traffic-main-cell">${main}</span>${sub ? `<span class="proxy-traffic-sub-cell">${sub}</span>` : ''}`;
  }
  function valueOf(row, ...keys) {
    for (const key of keys) {
      if (row && row[key] !== undefined && row[key] !== null && row[key] !== '') return row[key];
    }
    return '';
  }
  function normalizePayload(raw) {
    const payload = raw?.data && typeof raw.data === 'object' ? raw.data : (raw || {});
    return {
      current_leases: Array.isArray(payload.current_leases) ? payload.current_leases : [],
      history: Array.isArray(payload.history) ? payload.history : [],
      traffic: Array.isArray(payload.traffic) ? payload.traffic : [],
      facets: payload.facets && typeof payload.facets === 'object' ? payload.facets : {},
      as_of: payload.as_of || payload.updated_at || null,
    };
  }
  function buildUrl() {
    const params = new URLSearchParams();
    Object.entries(state.filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    params.set('view', 'all');
    params.set('limit', '100');
    return `${PROXY_TRAFFIC_API.url}?${params.toString()}`;
  }
  async function fetchProxyTraffic(url) {
    if (typeof window.__proxyTrafficFetch === 'function') return window.__proxyTrafficFetch(url);
    return api(url);
  }
  function setRefreshState(loading) {
    const button = byId('btnRefreshProxyTraffic');
    if (button) {
      button.disabled = loading;
      button.textContent = loading ? '同步中…' : '刷新';
    }
    const updated = byId('proxyTrafficUpdatedAt');
    if (updated && loading) updated.textContent = '同步中…';
  }
  function stateMarkup(kind, label, hint, retry = false) {
    const icon = kind === 'error'
      ? '<span class="table-state-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16h.01"/></svg></span>'
      : kind === 'empty'
        ? '<span class="table-state-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 6h14M5 12h10M5 18h7"/></svg></span>'
        : '<span class="table-state-spinner" aria-hidden="true"></span>';
    return `<tr class="list-state-row"><td class="table-state-cell" colspan="7"><div class="table-state is-${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${icon}<strong>${safeText(label)}</strong><small>${safeText(hint)}</small>${retry ? '<button type="button" class="jobs-tb-btn jobs-tb-btn--primary" data-proxy-retry>重新加载</button>' : ''}</div></td></tr>`;
  }
  function setBodyState(view, kind, label, hint, retry = false) {
    const body = byId(VIEWS[view].body);
    if (body) body.innerHTML = stateMarkup(kind, label, hint, retry);
  }
  function detailButton(view, index) {
    const id = `proxy-detail-${view}-${index}`;
    return `<button type="button" class="proxy-traffic-row-toggle" data-proxy-detail-toggle="${id}" aria-expanded="false" aria-controls="${id}">详情</button>`;
  }
  function detailRow(id, items, note = '') {
    const content = items.map(([label, value]) => `<div class="proxy-traffic-detail-item"><span>${safeText(label)}</span><strong>${value}</strong></div>`).join('');
    return `<tr class="proxy-traffic-row-detail" id="${id}" hidden><td colspan="7"><div class="proxy-traffic-detail-grid">${content}${note ? `<p class="proxy-traffic-detail-note">${safeText(note)}</p>` : ''}</div></td></tr>`;
  }
  function correlationItems(row) {
    const account = valueOf(row, 'account_id');
    const task = valueOf(row, 'operation_task_id', 'task_id');
    const run = valueOf(row, 'operation_run_id', 'run_id');
    const job = valueOf(row, 'registration_job_id', 'job_id');
    const attempt = valueOf(row, 'route_attempt', 'attempt');
    return {
      main: task || run || job || account || '-',
      sub: [account && `账号 ${account}`, run && `运行 ${run}`, job && `注册 ${job}`, attempt && `第 ${attempt} 次`].filter(Boolean).join(' · '),
      details: [
        ['账号 ID', safeText(account)],
        ['Operation task', safeText(task)],
        ['Operation run', safeText(run)],
        ['Registration job', safeText(job)],
        ['线路尝试', safeText(attempt, '未记录')],
      ],
    };
  }
  function renderLeaseRows(rows, view) {
    const body = byId(VIEWS[view].body);
    if (!body) return;
    if (!rows.length) {
      setBodyState(view, 'empty', `暂无${VIEWS[view].label}`, '调整筛选条件或等待新的持久化记录。');
      return;
    }
    body.innerHTML = rows.map((row, index) => {
      const detailId = `proxy-detail-${view}-${index}`;
      const correlation = correlationItems(row);
      const provider = valueOf(row, 'provider');
      const region = valueOf(row, 'region');
      const acquired = valueOf(row, 'acquired_at');
      const released = valueOf(row, 'released_at');
      const endLabel = view === 'history' ? '释放' : '到期';
      const endValue = view === 'history' ? released : valueOf(row, 'expires_at');
      const detailNote = valueOf(row, 'release_reason') || (view === 'history' ? '该记录来自持久化线路历史。' : '当前租约来自持久化代理租约记录。');
      return `<tr><td>${cell(safeText(provider), safeText(region))}</td><td class="proxy-traffic-mono">${safeText(valueOf(row, 'exit_ip'))}</td><td>${statusMarkup(valueOf(row, 'state'))}</td><td>${cell(safeText(purposeLabel(valueOf(row, 'purpose'))), safeText(valueOf(row, 'method')))}</td><td>${cell(safeText(correlation.main), safeText(correlation.sub))}</td><td>${cell(safeText(acquired), `${endLabel} ${safeText(endValue)}`)}</td><td>${detailButton(view, index)}</td></tr>${detailRow(detailId, [['提供方', safeText(provider)], ['地域', safeText(region)], ['状态', statusMarkup(valueOf(row, 'state'))], ['用途', safeText(purposeLabel(valueOf(row, 'purpose'))),], ...correlation.details], detailNote)}`;
    }).join('');
  }
  function requestStats(row) {
    const count = valueOf(row, 'request_count');
    const failed = valueOf(row, 'failed_request_count');
    const unfinished = valueOf(row, 'unfinished_request_count');
    const unknown = valueOf(row, 'unknown_size_request_count');
    return cell(`${formatNumber(count)} 次请求`, `失败 ${formatNumber(failed)} · 未完成 ${formatNumber(unfinished)} · 未知 ${formatNumber(unknown)}`);
  }
  function renderTrafficRows(rows) {
    const body = byId(VIEWS.traffic.body);
    if (!body) return;
    if (!rows.length) {
      setBodyState('traffic', 'empty', '暂无浏览器流量摘要', '当前筛选条件下没有可观测的 HTTP/WebSocket 流量。');
      return;
    }
    body.innerHTML = rows.map((row, index) => {
      const detailId = `proxy-detail-traffic-${index}`;
      const upload = valueOf(row, 'upload_bytes');
      const download = valueOf(row, 'download_bytes');
      const total = valueOf(row, 'total_bytes') || Number(upload || 0) + Number(download || 0);
      const unavailable = valueOf(row, 'status') === 'unavailable' || valueOf(row, 'unavailable_reason');
      const note = valueOf(row, 'unavailable_reason') || (unavailable ? '协议任务未采集浏览器字节。' : '仅保留字节和请求计数摘要，不包含 URL、Header 或请求体。');
      return `<tr><td>${cell(safeText(valueOf(row, 'source')), safeText(valueOf(row, 'method')))}</td><td>${cell(safeText(formatDate(valueOf(row, 'started_at', 'start_at'))), `结束 ${safeText(formatDate(valueOf(row, 'finished_at', 'end_at')))} · ${safeText(formatDuration(valueOf(row, 'duration_ms', 'duration')))}`)}</td><td class="proxy-traffic-mono">${formatBytes(upload)}</td><td class="proxy-traffic-mono">${formatBytes(download)}</td><td class="proxy-traffic-mono">${formatBytes(total)}</td><td>${requestStats(row)}</td><td>${detailButton('traffic', index)}</td></tr>${detailRow(detailId, [['来源', safeText(valueOf(row, 'source'))], ['方法', safeText(valueOf(row, 'method'))], ['上传', safeText(formatBytes(upload))], ['下载', safeText(formatBytes(download))], ['总计', safeText(formatBytes(total))], ['WebSocket', safeText(formatNumber(valueOf(row, 'websocket_count')))], ['状态', statusMarkup(valueOf(row, 'status') || (unavailable ? 'unavailable' : 'active'))]], note)}`;
    }).join('');
  }
  function updateSummary() {
    const payload = state.payload;
    const summary = {
      current_leases: payload.current_leases.length,
      history: payload.history.length,
      traffic: payload.traffic.length,
      total_bytes: payload.traffic.reduce((sum, row) => sum + Number(valueOf(row, 'total_bytes') || Number(valueOf(row, 'upload_bytes') || 0) + Number(valueOf(row, 'download_bytes') || 0)), 0),
    };
    document.querySelectorAll('[data-proxy-summary]').forEach(item => {
      const key = item.dataset.proxySummary;
      item.textContent = key === 'total_bytes' ? formatBytes(summary[key]) : formatNumber(summary[key]);
    });
  }
  function populateFilter(id, values, labeler) {
    const select = byId(id);
    if (!select) return;
    const current = select.value;
    const options = [...new Set(values.map(value => String(value || '').trim()).filter(Boolean))].sort();
    select.innerHTML = `<option value="">全部${labeler}</option>${options.map(value => `<option value="${safeText(value)}">${safeText(labeler === '提供方' ? value : labeler === '状态' ? statusLabel(value) : purposeLabel(value))}</option>`).join('')}`;
    select.value = options.includes(current) ? current : '';
  }
  function populateFilters() {
    const rows = [...state.payload.current_leases, ...state.payload.history, ...state.payload.traffic];
    const facets = state.payload.facets || {};
    populateFilter('proxyTrafficProvider', Array.isArray(facets.providers) ? facets.providers : rows.map(row => valueOf(row, 'provider')), '提供方');
    populateFilter('proxyTrafficState', Array.isArray(facets.states) ? facets.states : rows.map(row => valueOf(row, 'state', 'status')), '状态');
    populateFilter('proxyTrafficPurpose', Array.isArray(facets.purposes) ? facets.purposes : rows.map(row => valueOf(row, 'purpose')), '用途');
  }
  function matchesFilters(row) {
    const query = state.filters.q.toLowerCase();
    const haystack = [row.account_id, row.operation_task_id, row.operation_run_id, row.registration_job_id, row.purpose, row.provider, row.source, row.method, row.exit_ip].filter(Boolean).join(' ').toLowerCase();
    return (!query || haystack.includes(query))
      && (!state.filters.provider || String(row.provider || '') === state.filters.provider)
      && (!state.filters.state || String(row.state || row.status || '') === state.filters.state)
      && (!state.filters.purpose || String(row.purpose || '') === state.filters.purpose);
  }
  function filteredRows(key) { return (state.payload[key] || []).filter(matchesFilters); }
  function renderData() {
    updateSummary();
    renderLeaseRows(filteredRows('current_leases'), 'current');
    renderLeaseRows(filteredRows('history'), 'history');
    renderTrafficRows(filteredRows('traffic'));
  }
  function setActiveView(view, focus = false) {
    if (!VIEWS[view]) return;
    state.activeView = view;
    document.querySelectorAll('[data-proxy-view]').forEach(button => {
      const active = button.dataset.proxyView === view;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
      if (focus && active) button.focus();
    });
    document.querySelectorAll('[data-proxy-view-panel]').forEach(panel => {
      panel.hidden = panel.dataset.proxyViewPanel !== view;
    });
  }
  function updateUpdatedAt(value) {
    const updated = byId('proxyTrafficUpdatedAt');
    if (!updated) return;
    updated.textContent = value ? `更新于 ${formatDate(value)}` : '已刷新';
  }
  async function loadProxyTraffic(options = {}) {
    const requestId = ++state.requestId;
    state.loading = true;
    setRefreshState(true);
    if (!options.silent) {
      Object.keys(VIEWS).forEach(view => setBodyState(view, 'loading', `正在加载${VIEWS[view].label}`, '正在同步持久化代理与流量摘要。'));
    }
    try {
      const raw = await fetchProxyTraffic(buildUrl());
      if (requestId !== state.requestId) return;
      if (raw?.ok === false) throw new Error(raw.error || '代理与流量接口返回失败');
      state.payload = normalizePayload(raw);
      populateFilters();
      renderData();
      updateUpdatedAt(state.payload.as_of || new Date().toISOString());
    } catch (error) {
      if (requestId !== state.requestId) return;
      const message = error?.message || '代理与流量数据加载失败';
      Object.keys(VIEWS).forEach(view => setBodyState(view, 'error', '加载失败', `${message}。请确认接口可用后重试。`, true));
      const updated = byId('proxyTrafficUpdatedAt');
      if (updated) updated.textContent = '同步失败';
    } finally {
      if (requestId === state.requestId) {
        state.loading = false;
        setRefreshState(false);
      }
    }
  }
  function resetFilters() {
    state.filters = { q: '', provider: '', state: '', purpose: '' };
    ['proxyTrafficQuery', 'proxyTrafficProvider', 'proxyTrafficState', 'proxyTrafficPurpose'].forEach(id => { const el = byId(id); if (el) el.value = ''; });
    renderData();
  }
  function bind() {
    document.querySelectorAll('[data-proxy-view]').forEach(button => button.addEventListener('click', () => setActiveView(button.dataset.proxyView)));
    document.querySelectorAll('[data-proxy-view]').forEach(button => button.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      const tabs = Array.from(document.querySelectorAll('[data-proxy-view]'));
      const index = tabs.indexOf(button);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      event.preventDefault();
      setActiveView(tabs[next].dataset.proxyView, true);
    }));
    byId('btnRefreshProxyTraffic')?.addEventListener('click', () => loadProxyTraffic());
    byId('btnResetProxyTrafficFilters')?.addEventListener('click', resetFilters);
    byId('proxyTrafficQuery')?.addEventListener('input', event => {
      state.filters.q = String(event.target.value || '').trim();
      renderData();
    });
    [['proxyTrafficProvider', 'provider'], ['proxyTrafficState', 'state'], ['proxyTrafficPurpose', 'purpose']].forEach(([id, key]) => byId(id)?.addEventListener('change', event => {
      state.filters[key] = String(event.target.value || '');
      renderData();
    }));
    document.addEventListener('click', event => {
      const toggle = event.target.closest('[data-proxy-detail-toggle]');
      if (toggle) {
        const detail = byId(toggle.dataset.proxyDetailToggle);
        if (!detail) return;
        const expanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        detail.hidden = expanded;
        return;
      }
      if (event.target.closest('[data-proxy-retry]')) loadProxyTraffic();
    });
  }
  bind();
  window.loadProxyTraffic = loadProxyTraffic;
  window.setProxyTrafficView = setActiveView;
  window.setProxyTrafficFetcher = fetcher => { window.__proxyTrafficFetch = fetcher; };
  window.setInterval(() => {
    const page = byId('tab-proxy-traffic');
    if (!document.hidden && page && !page.classList.contains('hidden') && !state.loading) loadProxyTraffic({silent: true});
  }, 30000);
})();
