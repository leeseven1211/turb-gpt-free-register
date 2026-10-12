/* Independent read-only view for the persistent proxy and browser-traffic contract. */
const PROXY_TRAFFIC_ENDPOINTS = Object.freeze({
  current: '/api/proxy-traffic/current',
  history: '/api/proxy-traffic/history',
  traffic: '/api/proxy-traffic/traffic',
  summary: '/api/proxy-traffic/summary',
});
const PROXY_TRAFFIC_VIEWS = Object.freeze([
  {view: 'current', key: 'current_leases'},
  {view: 'history', key: 'lease_history'},
  {view: 'traffic', key: 'browser_traffic'},
]);
const PROXY_TRAFFIC_VIEW_CONFIG = {
  current: {
    key: 'current_leases',
    body: 'proxyTrafficCurrentBody',
    status: 'proxyTrafficPanelStatusCurrent',
    columns: 8,
    title: '暂无当前租约',
    description: '当前没有可显示的持久化线路租约。',
  },
  history: {
    key: 'lease_history',
    body: 'proxyTrafficHistoryBody',
    status: 'proxyTrafficPanelStatusHistory',
    columns: 8,
    title: '暂无线路历史',
    description: '当前没有可显示的已结束或已释放租约。',
  },
  traffic: {
    key: 'browser_traffic',
    body: 'proxyTrafficTrafficBody',
    status: 'proxyTrafficPanelStatusTraffic',
    columns: 8,
    title: '暂无请求流量',
    description: '当前没有可显示的浏览器或协议 HTTP 流量摘要。',
  },
};
const PROXY_TRAFFIC_STATUS_TEXT = {
  loading: '正在加载',
  ready: '已同步',
  empty: '暂无记录',
  error: '加载失败',
};
const PROXY_TRAFFIC_STATUS_LABELS = {
  shared_pending: '共享线路检测中',
  shared_leased: '共享查询中',
  leased: '租约中',
  recent: '最近释放',
  released: '已释放',
  expired: '已过期',
  failed: '失败',
  unavailable: '未采集',
  observed: '可观测',
  complete: '已完成',
  running: '运行中',
  available: '可观测',
};
const PROXY_TRAFFIC_WINDOW_OPTIONS = Object.freeze([
  {value: 'all', label: '全部时间'},
  {value: '1h', label: '最近 1 小时'},
  {value: '24h', label: '最近 24 小时'},
  {value: '7d', label: '最近 7 天'},
]);

let proxyTrafficSnapshot = null;
let proxyTrafficSummary = null;
let proxyTrafficActiveView = 'current';
let proxyTrafficLoading = false;
let proxyTrafficReloadQueued = false;
let proxyTrafficFilterTimer = null;
let proxyTrafficDesiredVersion = 0;
const PROXY_TRAFFIC_STALE = Symbol('proxy-traffic-stale');
const proxyTrafficFilters = {window: 'all', purpose: 'all', search: ''};
const proxyTrafficStateFilters = {current: 'all', history: 'all', traffic: 'all'};
const proxyTrafficPages = {
  current: {page: 1, size: 20, total: 0},
  history: {page: 1, size: 20, total: 0},
  traffic: {page: 1, size: 20, total: 0},
};
const proxyTrafficScrollResetViews = new Set();

function proxyTrafficEsc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function proxyTrafficValue(row, key) {
  return row && Object.prototype.hasOwnProperty.call(row, key) ? row[key] : '';
}

function proxyTrafficText(value, fallback = '—') {
  return value == null || value === '' ? fallback : proxyTrafficEsc(value);
}

function proxyTrafficNumber(row, key) {
  const value = Number(proxyTrafficValue(row, key));
  return Number.isFinite(value) && value >= 0 ? value : null;
}

function proxyTrafficBytes(value) {
  if (!Number.isFinite(value) || value < 0) return '—';
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let scaled = value;
  let index = -1;
  while (scaled >= 1024 && index < units.length - 1) {
    scaled /= 1024;
    index += 1;
  }
  return `${scaled >= 100 ? scaled.toFixed(0) : scaled >= 10 ? scaled.toFixed(1) : scaled.toFixed(2)} ${units[index]}`;
}

function proxyTrafficDate(value) {
  if (value == null || value === '') return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? proxyTrafficText(value) : date.toLocaleString('zh-CN', {hour12: false});
}

function proxyTrafficStatus(value) {
  const raw = String(value == null ? '' : value);
  const label = PROXY_TRAFFIC_STATUS_LABELS[raw] || raw || '未知';
  const className = raw.toLowerCase().replace(/[^a-z0-9_-]/g, '') || 'unknown';
  return `<span class="proxy-traffic-status proxy-traffic-status--${className}">${proxyTrafficEsc(label)}</span>`;
}

function proxyTrafficField(label, value, className = '') {
  return `<div class="proxy-traffic-detail-item"><dt>${proxyTrafficEsc(label)}</dt><dd class="${className}">${proxyTrafficText(value)}</dd></div>`;
}

function proxyTrafficDetailsButton(view, row) {
  const id = proxyTrafficValue(row, 'id');
  if (id == null || id === '') return '<span class="proxy-traffic-muted">—</span>';
  return `<button type="button" class="proxy-traffic-detail-button" data-proxy-detail="${proxyTrafficEsc(view)}" data-proxy-detail-id="${proxyTrafficEsc(id)}" aria-label="查看${view === 'history' ? '线路历史' : '请求流量'}详情">详情</button>`;
}

function proxyTrafficCorrelation(row, includeJob = false) {
  const items = [
    ['任务', proxyTrafficValue(row, 'operation_task_id'), 'proxy-traffic-id'],
    ['运行', proxyTrafficValue(row, 'operation_run_id'), 'proxy-traffic-id'],
  ];
  if (includeJob) items.push(['注册 job', proxyTrafficValue(row, 'registration_job_id'), 'proxy-traffic-id']);
  const visible = items.filter((item) => item[1] != null && item[1] !== '');
  if (!visible.length) return '<span class="proxy-traffic-muted">—</span>';
  return `<div class="proxy-traffic-correlation">${visible.map((item) => `<span><small>${proxyTrafficEsc(item[0])}</small><strong class="${item[2]}">${proxyTrafficText(item[1])}</strong></span>`).join('')}</div>`;
}

function proxyTrafficTaskTypeLabel(row) {
  const taskId = proxyTrafficValue(row, 'operation_task_id');
  const registrationJobId = proxyTrafficValue(row, 'registration_job_id');
  const hasRegistrationJob = registrationJobId != null && registrationJobId !== '';
  if ((taskId == null || taskId === '') && !hasRegistrationJob) return '未关联任务';
  const taskType = String(proxyTrafficValue(row, 'operation_task_type') || (hasRegistrationJob ? 'registration' : '')).trim();
  if (!taskType) return '未关联任务';
  return typeof LIST_FACET_LABELS !== 'undefined'
    ? (LIST_FACET_LABELS.task_type?.[taskType] || taskType)
    : taskType;
}

function proxyTrafficTaskSummary(row) {
  const taskId = proxyTrafficValue(row, 'operation_task_id');
  const runId = proxyTrafficValue(row, 'operation_run_id');
  const identifiers = [];
  if (taskId != null && taskId !== '') identifiers.push(`任务 #${proxyTrafficEsc(taskId)}`);
  if (runId != null && runId !== '') identifiers.push(`运行 #${proxyTrafficEsc(runId)}`);
  const registrationJobId = proxyTrafficValue(row, 'registration_job_id');
  if ((taskId == null || taskId === '') && registrationJobId != null && registrationJobId !== '') {
    identifiers.push(`注册 job #${proxyTrafficEsc(registrationJobId)}`);
  }
  return `<div class="proxy-traffic-correlation"><strong>${proxyTrafficEsc(proxyTrafficTaskTypeLabel(row))}</strong>${identifiers.length ? `<small>${identifiers.join(' · ')}</small>` : ''}</div>`;
}

function proxyTrafficLeaseTime(row, endKey = 'expires_at') {
  const start = proxyTrafficValue(row, 'acquired_at');
  const end = proxyTrafficValue(row, endKey);
  if (!start && !end) return '—';
  return `<div class="proxy-traffic-time"><span>${proxyTrafficDate(start)}</span><small>${end ? `至 ${proxyTrafficDate(end)}` : '进行中'}</small></div>`;
}

function proxyTrafficRenderCurrent(row) {
  return `<tr>
    <td><div class="proxy-traffic-primary proxy-traffic-id" title="${proxyTrafficText(proxyTrafficValue(row, 'lease_id'), '')}">${proxyTrafficText(proxyTrafficValue(row, 'lease_id'), '未提供租约 ID')}</div><small class="proxy-traffic-muted">${proxyTrafficText(proxyTrafficValue(row, 'provider'))}</small></td>
    <td><span class="proxy-traffic-ip" title="${proxyTrafficText(proxyTrafficValue(row, 'exit_ip'), '')}">${proxyTrafficText(proxyTrafficValue(row, 'exit_ip'))}</span></td>
    <td>${proxyTrafficStatus(proxyTrafficValue(row, 'state'))}</td>
    <td><span class="proxy-traffic-id">${proxyTrafficText(proxyTrafficValue(row, 'account_id'))}</span></td>
    <td>${proxyTrafficText(proxyTrafficValue(row, 'purpose'))}</td>
    <td>${proxyTrafficCorrelation(row)}</td>
    <td>${proxyTrafficText(proxyTrafficValue(row, 'route_attempt_no'))}</td>
    <td>${proxyTrafficLeaseTime(row)}</td>
  </tr>`;
}

function proxyTrafficRenderHistory(row) {
  return `<tr>
    <td><div class="proxy-traffic-primary proxy-traffic-id" title="${proxyTrafficText(proxyTrafficValue(row, 'lease_id'), '')}">${proxyTrafficText(proxyTrafficValue(row, 'lease_id'), '未提供租约 ID')}</div><small class="proxy-traffic-muted">${proxyTrafficText(proxyTrafficValue(row, 'provider'))}</small></td>
    <td><span class="proxy-traffic-ip" title="${proxyTrafficText(proxyTrafficValue(row, 'exit_ip'), '')}">${proxyTrafficText(proxyTrafficValue(row, 'exit_ip'))}</span></td>
    <td>${proxyTrafficStatus(proxyTrafficValue(row, 'state'))}</td>
    <td><span class="proxy-traffic-id">${proxyTrafficText(proxyTrafficValue(row, 'account_id'))}</span></td>
    <td>${proxyTrafficText(proxyTrafficValue(row, 'purpose'))}</td>
    <td>${proxyTrafficCorrelation(row, true)}</td>
    <td>${proxyTrafficLeaseTime(row, 'released_at')}</td>
    <td>${proxyTrafficDetailsButton('history', row)}</td>
  </tr>`;
}

function proxyTrafficRenderTraffic(row) {
  const source = String(proxyTrafficValue(row, 'source') || '');
  const upload = proxyTrafficNumber(row, 'upload_bytes');
  const download = proxyTrafficNumber(row, 'download_bytes');
  const total = proxyTrafficNumber(row, 'total_bytes');
  const availability = String(proxyTrafficValue(row, 'availability') || '').toLowerCase();
  const unavailable = availability !== 'available' || total == null;
  const measuredText = `${proxyTrafficBytes(upload)} / ${proxyTrafficBytes(download)} / ${proxyTrafficBytes(total)}`;
  const byteText = unavailable ? '未采集' : `${measuredText}${source === 'protocol_http' && proxyTrafficNumber(row, 'byte_unknown_count') > 0 ? '（部分字节未知）' : ''}`;
  const countText = [
    proxyTrafficNumber(row, 'request_count'),
    proxyTrafficNumber(row, 'failed_count'),
    proxyTrafficNumber(row, 'unfinished_count'),
    proxyTrafficNumber(row, 'unknown_count'),
  ].map((value) => value == null ? '—' : String(value)).join(' / ');
  return `<tr>
    <td><span class="proxy-traffic-primary">${proxyTrafficText(source)}</span></td>
    <td><span class="proxy-traffic-mono">${proxyTrafficText(proxyTrafficValue(row, 'method'))}</span></td>
    <td>${proxyTrafficStatus(unavailable ? 'unavailable' : 'observed')}</td>
    <td><span class="proxy-traffic-number" title="${proxyTrafficEsc(byteText)}">${proxyTrafficEsc(byteText)}</span></td>
    <td><span class="proxy-traffic-number" title="请求 / 失败 / 未完成 / 未知">${proxyTrafficEsc(countText)}</span></td>
    <td>${proxyTrafficTaskSummary(row)}</td>
    <td>${proxyTrafficDate(proxyTrafficValue(row, 'started_at'))}</td>
    <td>${proxyTrafficDetailsButton('traffic', row)}</td>
  </tr>`;
}

function proxyTrafficStateRow(view, kind, title, description) {
  const config = PROXY_TRAFFIC_VIEW_CONFIG[view];
  const visual = kind === 'loading'
    ? '<span class="table-state-spinner" aria-hidden="true"></span>'
    : `<span class="table-state-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg></span>`;
  return `<tr class="list-state-row"><td class="table-state-cell" colspan="${config.columns}"><div class="table-state is-${proxyTrafficEsc(kind)}" role="status">${visual}<strong>${proxyTrafficEsc(title)}</strong><small>${proxyTrafficEsc(description)}</small></div></td></tr>`;
}

function proxyTrafficSetPanelState(view, kind, title, description) {
  const config = PROXY_TRAFFIC_VIEW_CONFIG[view];
  const body = document.getElementById(config.body);
  const status = document.getElementById(config.status);
  if (body) body.innerHTML = proxyTrafficStateRow(view, kind, title, description);
  if (status) status.textContent = PROXY_TRAFFIC_STATUS_TEXT[kind] || kind;
}

function proxyTrafficRows(view) {
  const config = PROXY_TRAFFIC_VIEW_CONFIG[view];
  return proxyTrafficSnapshot?.[config.key] || [];
}

function proxyTrafficFilterHeaders(key = '') {
  const suffix = key ? `[data-proxy-filter-key="${key}"]` : '[data-proxy-filter-key]';
  return [...document.querySelectorAll(`#tab-proxy-traffic ${suffix}`)];
}

function proxyTrafficFilterControl(header) {
  return header ? document.getElementById(header.dataset.columnFilter || '') : null;
}

function proxyTrafficFilterIcon(type) {
  if (type === 'search') {
    return '<svg class="column-filter-trigger-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="3.75"></circle><path d="m10 10 3 3"></path></svg>';
  }
  return '<svg class="column-filter-trigger-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 3.5h11L9.3 8.3v3.4l-2.6 1.2V8.3z"></path></svg>';
}

function proxyTrafficRenderFilterOptions(select) {
  const list = select?.closest('.column-filter-header')?.querySelector('[data-column-filter-options]');
  if (!list) return;
  list.innerHTML = [...select.options].map((option) => `
    <button type="button" class="column-filter-option" role="menuitemradio"
      data-column-filter-option="${proxyTrafficEsc(option.value)}" aria-checked="${option.selected ? 'true' : 'false'}">
      <span>${proxyTrafficEsc(option.textContent || option.label || '全部')}</span>
      <svg class="column-filter-option-check" viewBox="0 0 16 16" aria-hidden="true"><path d="m3 8.3 3.1 3L13 4.7"></path></svg>
    </button>`).join('');
}

function proxyTrafficRefreshFilterControlState(control) {
  const header = control?.closest('[data-proxy-filter-key]');
  if (!header) return;
  const emptyValue = header.dataset.filterEmptyValue || (control.matches('input[type="search"]') ? '' : 'all');
  header.classList.toggle('has-filter-value', String(control.value ?? '') !== emptyValue);
  if (control.matches('select')) proxyTrafficRenderFilterOptions(control);
}

function proxyTrafficInitColumnFilterFallback() {
  proxyTrafficFilterHeaders().forEach((header) => {
    if (header.dataset.columnFilterReady === '1') return;
    const id = header.dataset.columnFilter;
    const type = header.dataset.filterType || 'search';
    const label = header.textContent.trim();
    const filterLabel = header.dataset.filterLabel || `按${label}筛选`;
    const trigger = `<button type="button" class="column-filter-trigger" data-column-filter-trigger aria-expanded="false" aria-label="${proxyTrafficEsc(filterLabel)}"><span class="column-filter-trigger-label">${proxyTrafficEsc(label)}</span>${proxyTrafficFilterIcon(type)}</button>`;
    header.dataset.columnFilterReady = '1';
    header.dataset.proxyFilterFallback = '1';
    header.dataset.filterTitle = label;
    if (type === 'search') {
      header.innerHTML = `${trigger}
        <div class="column-filter-search" data-column-filter-search>
          <svg class="column-filter-search-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="3.75"></circle><path d="m10 10 3 3"></path></svg>
          <input id="${proxyTrafficEsc(id)}" type="search" placeholder="${proxyTrafficEsc(header.dataset.filterPlaceholder || '')}" aria-label="${proxyTrafficEsc(filterLabel)}" autocomplete="off">
          <button type="button" class="column-filter-clear-inline" data-clear-column-filter aria-label="清空${proxyTrafficEsc(label)}筛选" title="清空">×</button>
        </div>`;
      return;
    }
    header.innerHTML = `${trigger}
      <select id="${proxyTrafficEsc(id)}" class="column-filter-native" hidden tabindex="-1" aria-hidden="true"><option value="all">全部</option></select>
      <div class="column-filter-popover column-filter-popover--select" role="menu" aria-label="${proxyTrafficEsc(filterLabel)}">
        <div class="column-filter-options" data-column-filter-options></div>
      </div>`;
    header.querySelector('[data-column-filter-trigger]')?.setAttribute('aria-haspopup', 'menu');
    proxyTrafficRenderFilterOptions(document.getElementById(id));
  });
}

function proxyTrafficCloseFallbackFilters(exceptHeader = null) {
  document.querySelectorAll('#tab-proxy-traffic [data-proxy-filter-fallback="1"]').forEach((header) => {
    if (header === exceptHeader) return;
    header.classList.remove('is-filter-open', 'is-searching');
    header.querySelector('[data-column-filter-trigger]')?.setAttribute('aria-expanded', 'false');
  });
}

function proxyTrafficPositionFallbackPopover(header) {
  const trigger = header?.querySelector('[data-column-filter-trigger]');
  const popover = header?.querySelector('.column-filter-popover');
  if (!trigger || !popover) return;
  const rect = trigger.getBoundingClientRect();
  const width = Math.min(208, Math.max(148, window.innerWidth - 20));
  const left = Math.max(10, Math.min(rect.left, window.innerWidth - width - 10));
  popover.style.width = `${width}px`;
  popover.style.left = `${left}px`;
  popover.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - Math.max(48, popover.offsetHeight) - 10)}px`;
}

function proxyTrafficBindFallbackColumnFilters() {
  const page = document.getElementById('tab-proxy-traffic');
  if (!page || page.dataset.proxyFallbackFiltersBound === '1') return;
  page.dataset.proxyFallbackFiltersBound = '1';
  page.addEventListener('click', (event) => {
    const header = event.target.closest?.('[data-proxy-filter-fallback="1"]');
    const clear = event.target.closest?.('[data-clear-column-filter]');
    if (clear && header) {
      event.preventDefault();
      const control = proxyTrafficFilterControl(header);
      if (control) {
        control.value = header.dataset.filterEmptyValue || (control.matches('input[type="search"]') ? '' : 'all');
        control.dispatchEvent(new Event(control.matches('input[type="search"]') ? 'input' : 'change', {bubbles: true}));
        control.focus({preventScroll: true});
      }
      return;
    }
    const option = event.target.closest?.('[data-column-filter-option]');
    if (option && header) {
      event.preventDefault();
      const select = proxyTrafficFilterControl(header);
      if (select) {
        select.value = option.dataset.columnFilterOption ?? 'all';
        select.dispatchEvent(new Event('change', {bubbles: true}));
      }
      proxyTrafficCloseFallbackFilters();
      header.querySelector('[data-column-filter-trigger]')?.focus({preventScroll: true});
      return;
    }
    const trigger = event.target.closest?.('[data-column-filter-trigger]');
    if (trigger && header) {
      event.preventDefault();
      const type = header.dataset.filterType || 'search';
      const willOpen = type === 'search' || !header.classList.contains('is-filter-open');
      proxyTrafficCloseFallbackFilters(willOpen ? header : null);
      if (type === 'search') {
        header.classList.add('is-searching');
        requestAnimationFrame(() => proxyTrafficFilterControl(header)?.focus({preventScroll: true}));
      } else {
        header.classList.toggle('is-filter-open', willOpen);
        trigger.setAttribute('aria-expanded', String(willOpen));
        if (willOpen) requestAnimationFrame(() => proxyTrafficPositionFallbackPopover(header));
      }
      return;
    }
    if (!event.target.closest?.('.column-filter-popover')) proxyTrafficCloseFallbackFilters();
  });
  page.addEventListener('keydown', (event) => {
    const header = event.target.closest?.('[data-proxy-filter-fallback="1"]');
    if (!header || !['Escape', 'Enter'].includes(event.key)) return;
    if (event.key === 'Enter' && !event.target.matches('input[type="search"]')) return;
    event.preventDefault();
    proxyTrafficCloseFallbackFilters();
    header.querySelector('[data-column-filter-trigger]')?.focus({preventScroll: true});
  });
}

function proxyTrafficPopulateSelects(key, options, allLabel) {
  const values = options.map(({value}) => String(value));
  if (!values.includes(String(proxyTrafficFilters[key]))) proxyTrafficFilters[key] = 'all';
  proxyTrafficFilterHeaders(key).forEach((header) => {
    const select = proxyTrafficFilterControl(header);
    if (!select) return;
    select.innerHTML = [`<option value="all">${proxyTrafficEsc(allLabel)}</option>`]
      .concat(options.filter(({value}) => String(value) !== 'all').map(({value, label}) => `<option value="${proxyTrafficEsc(value)}">${proxyTrafficEsc(label)}</option>`))
      .join('');
  });
}

function proxyTrafficSyncFilterControls() {
  Object.entries(proxyTrafficFilters).forEach(([key, value]) => {
    proxyTrafficFilterHeaders(key).forEach((header) => {
      const control = proxyTrafficFilterControl(header);
      if (!control) return;
      control.value = String(value);
      proxyTrafficRefreshFilterControlState(control);
    });
  });
  proxyTrafficFilterHeaders('state').forEach((header) => {
    const view = header.closest('[data-proxy-panel]')?.dataset.proxyPanel;
    const control = proxyTrafficFilterControl(header);
    if (!view || !control) return;
    control.value = proxyTrafficStateFilters[view];
    proxyTrafficRefreshFilterControlState(control);
  });
  const clear = document.getElementById('btnClearProxyTrafficFilters');
  if (clear) clear.hidden = !Object.entries(proxyTrafficFilters).some(([key, value]) => value !== (key === 'search' ? '' : 'all'))
    && !Object.values(proxyTrafficStateFilters).some((value) => value !== 'all');
}

function proxyTrafficBindFilterControls() {
  proxyTrafficFilterHeaders().forEach((header) => {
    const control = proxyTrafficFilterControl(header);
    if (!control || control.dataset.proxyFilterBound === '1') return;
    control.dataset.proxyFilterBound = '1';
    const eventName = control.matches('input[type="search"]') ? 'input' : 'change';
    control.addEventListener(eventName, () => {
      const key = header.dataset.proxyFilterKey;
      const view = header.closest('[data-proxy-panel]')?.dataset.proxyPanel;
      if (key === 'state' && view) {
        proxyTrafficStateFilters[view] = control.value;
        proxyTrafficPages[view].page = 1;
        proxyTrafficScrollResetViews.add(view);
        proxyTrafficSyncFilterControls();
        proxyTrafficDesiredVersion += 1;
        loadProxyTraffic(view);
        return;
      }
      proxyTrafficFilters[key] = control.value;
      proxyTrafficSyncFilterControls();
      Object.entries(proxyTrafficPages).forEach(([name, page]) => {
        page.page = 1;
        proxyTrafficScrollResetViews.add(name);
      });
      proxyTrafficDesiredVersion += 1;
      if (proxyTrafficFilterTimer) clearTimeout(proxyTrafficFilterTimer);
      proxyTrafficFilterTimer = setTimeout(loadProxyTraffic, eventName === 'input' ? 260 : 0);
    });
  });
}

function proxyTrafficClearFilters() {
  proxyTrafficFilters.window = 'all';
  proxyTrafficFilters.purpose = 'all';
  proxyTrafficFilters.search = '';
  Object.keys(proxyTrafficStateFilters).forEach((view) => { proxyTrafficStateFilters[view] = 'all'; });
  proxyTrafficSyncFilterControls();
  Object.entries(proxyTrafficPages).forEach(([name, page]) => {
    page.page = 1;
    proxyTrafficScrollResetViews.add(name);
  });
  proxyTrafficDesiredVersion += 1;
  if (proxyTrafficFilterTimer) clearTimeout(proxyTrafficFilterTimer);
  loadProxyTraffic();
}

function proxyTrafficRefreshFilterOptions() {
  if (!proxyTrafficSummary) return;
  const purposes = Array.isArray(proxyTrafficSummary.purposes) ? proxyTrafficSummary.purposes : [];
  const states = Array.isArray(proxyTrafficSummary.lease_states) ? proxyTrafficSummary.lease_states : [];
  proxyTrafficPopulateSelects('purpose', purposes.map((value) => ({value, label: value})), '全部用途');
  proxyTrafficFilterHeaders('state').forEach((header) => {
    const view = header.closest('[data-proxy-panel]')?.dataset.proxyPanel;
    const select = proxyTrafficFilterControl(header);
    if (!view || !select) return;
    const values = view === 'traffic' ? ['available']
      : states.filter((value) => view === 'current' ? ['pending', 'leased', 'shared_pending', 'shared_leased'].includes(value) : !['pending', 'leased', 'shared_pending', 'shared_leased'].includes(value));
    if (!values.includes(proxyTrafficStateFilters[view])) proxyTrafficStateFilters[view] = 'all';
    select.innerHTML = '<option value="all">全部状态</option>' + values.map((value) => `<option value="${proxyTrafficEsc(value)}">${proxyTrafficEsc(PROXY_TRAFFIC_STATUS_LABELS[value] || value)}</option>`).join('');
  });
  proxyTrafficSyncFilterControls();
}

function proxyTrafficRenderSummary() {
  const values = {
    totalBytes: proxyTrafficBytes(Number(proxyTrafficSummary?.total_bytes)),
    todayBytes: proxyTrafficBytes(Number(proxyTrafficSummary?.today_bytes)),
    todayRequestCount: proxyTrafficSummary?.today_request_count ?? proxyTrafficSummary?.today_browser_count,
    todayRouteCount: proxyTrafficSummary?.today_route_count,
  };
  Object.entries(values).forEach(([key, value]) => {
    const element = document.querySelector(`[data-proxy-summary="${key}"]`);
    if (element) element.textContent = value == null ? '—' : String(value);
  });
}

function proxyTrafficRenderPager(view) {
  const page = proxyTrafficPages[view];
  const pager = document.getElementById(`proxyTrafficPager${view[0].toUpperCase()}${view.slice(1)}`);
  if (!pager) return;
  const activeControl = pager.contains(document.activeElement) ? document.activeElement : null;
  const activePageButton = activeControl?.dataset?.proxyPage;
  const activePageSize = activeControl?.hasAttribute?.('data-proxy-page-size');
  const pages = Math.max(1, Math.ceil(page.total / page.size));
  const first = page.total ? (page.page - 1) * page.size + 1 : 0;
  const last = Math.min(page.total, page.page * page.size);
  pager.innerHTML = `<span class="proxy-traffic-page-total">${page.total ? `显示 ${first}–${last} 条，共 ${page.total} 条` : '共 0 条'}</span>
    <div class="proxy-traffic-page-actions" role="group" aria-label="翻页">
      <button type="button" data-proxy-pager="${view}" data-proxy-page="prev" aria-label="上一页" ${page.page <= 1 ? 'disabled' : ''}>上一页</button>
      <span class="proxy-traffic-page-number" role="status" aria-live="polite" aria-label="第 ${page.page} 页，共 ${pages} 页">${page.page} / ${pages}</span>
      <button type="button" data-proxy-pager="${view}" data-proxy-page="next" aria-label="下一页" ${page.page >= pages ? 'disabled' : ''}>下一页</button>
    </div>
    <label class="proxy-traffic-page-size">每页 <select data-proxy-page-size="${view}" aria-label="${view === 'current' ? '当前租约' : view === 'history' ? '线路历史' : '请求流量'}每页条数">
        ${[20, 50, 100].map((size) => `<option value="${size}" ${page.size === size ? 'selected' : ''}>${size}</option>`).join('')}
      </select> 条</label>`;
  const replacement = activePageButton
    ? pager.querySelector(`[data-proxy-page="${activePageButton}"]:not(:disabled)`) || pager.querySelector('[data-proxy-page]:not(:disabled)')
    : activePageSize ? pager.querySelector('[data-proxy-page-size]') : null;
  replacement?.focus({preventScroll: true});
}

function proxyTrafficRenderRows() {
  if (!proxyTrafficSnapshot) return;
  const renderers = {current: proxyTrafficRenderCurrent, history: proxyTrafficRenderHistory, traffic: proxyTrafficRenderTraffic};
  Object.entries(renderers).forEach(([view, renderer]) => {
    const config = PROXY_TRAFFIC_VIEW_CONFIG[view];
    const body = document.getElementById(config.body);
    const rows = proxyTrafficRows(view);
    if (!body) return;
    body.innerHTML = rows.length
      ? rows.map(renderer).join('')
      : proxyTrafficStateRow(view, 'empty', config.title, config.description);
    const status = document.getElementById(config.status);
    if (status) status.textContent = proxyTrafficPages[view].total ? `${proxyTrafficPages[view].total} 条记录` : PROXY_TRAFFIC_STATUS_TEXT.empty;
    const count = document.querySelector(`[data-proxy-count="${view}"]`);
    if (count) count.textContent = String(proxyTrafficPages[view].total);
    proxyTrafficRenderPager(view);
  });
  proxyTrafficRenderSummary();
}

function proxyTrafficRenderError(error) {
  const detail = error?.message || '服务暂时不可用，请稍后刷新。';
  Object.keys(PROXY_TRAFFIC_VIEW_CONFIG).forEach((view) => {
    proxyTrafficSetPanelState(view, 'error', '代理与流量数据暂不可用', `接口尚未提供或响应格式不完整：${detail}`);
  });
  document.querySelectorAll('[data-proxy-count]').forEach((element) => { element.textContent = '—'; });
  document.querySelectorAll('[data-proxy-summary]').forEach((element) => { element.textContent = '—'; });
}

function proxyTrafficOpenDetail(view, id) {
  const row = proxyTrafficRows(view).find((item) => String(proxyTrafficValue(item, 'id')) === String(id));
  const dialog = document.getElementById('proxyTrafficDetailDialog');
  const body = document.getElementById('proxyTrafficDetailBody');
  const title = document.getElementById('proxyTrafficDetailTitle');
  if (!row || !dialog || !body || !title) return;
  const items = view === 'history' ? [
    ['租约 ID', proxyTrafficValue(row, 'lease_id')],
    ['线路来源', proxyTrafficValue(row, 'provider')],
    ['出口 IP', proxyTrafficValue(row, 'exit_ip')],
    ['状态', PROXY_TRAFFIC_STATUS_LABELS[proxyTrafficValue(row, 'state')] || proxyTrafficValue(row, 'state')],
    ['账号', proxyTrafficValue(row, 'account_id')],
    ['用途', proxyTrafficValue(row, 'purpose')],
    ['任务', proxyTrafficValue(row, 'operation_task_id')],
    ['运行', proxyTrafficValue(row, 'operation_run_id')],
    ['注册 job', proxyTrafficValue(row, 'registration_job_id')],
    ['重试序号', proxyTrafficValue(row, 'route_attempt_no')],
    ['获取时间', proxyTrafficDate(proxyTrafficValue(row, 'acquired_at'))],
    ['到期时间', proxyTrafficDate(proxyTrafficValue(row, 'expires_at'))],
    ['释放时间', proxyTrafficDate(proxyTrafficValue(row, 'released_at'))],
  ] : [
    ['来源', proxyTrafficValue(row, 'source')],
    ['字节口径', proxyTrafficValue(row, 'source') === 'protocol_http' ? 'HTTP 传输正文；不含请求/响应头、TLS、隧道或代理商账单' : '浏览器可观测字节；不等同代理商账单'],
    ['总请求耗时', proxyTrafficValue(row, 'duration_ms') == null ? null : `${proxyTrafficValue(row, 'duration_ms')} 毫秒`],
    ['状态族', row.status_families ? Object.entries(row.status_families).map(([family, count]) => `${family}: ${count}`).join(' / ') : null],
    ['重定向次数', proxyTrafficValue(row, 'redirect_count')],
    ['解压后响应正文', proxyTrafficValue(row, 'decoded_response_bytes') == null ? null : proxyTrafficBytes(proxyTrafficNumber(row, 'decoded_response_bytes'))],
    ['字节未知请求数', proxyTrafficValue(row, 'byte_unknown_count')],
    ['注册 Attempt', proxyTrafficValue(row, 'registration_attempt_id')],
    ['注册 Run', proxyTrafficValue(row, 'registration_run_id')],
    ['方法', proxyTrafficValue(row, 'method')],
    ['上传流量', proxyTrafficBytes(proxyTrafficNumber(row, 'upload_bytes'))],
    ['下载流量', proxyTrafficBytes(proxyTrafficNumber(row, 'download_bytes'))],
    ['总流量', proxyTrafficBytes(proxyTrafficNumber(row, 'total_bytes'))],
    ['请求数', proxyTrafficValue(row, 'request_count')],
    ['失败数', proxyTrafficValue(row, 'failed_count')],
    ['未完成数', proxyTrafficValue(row, 'unfinished_count')],
    ['未知数', proxyTrafficValue(row, 'unknown_count')],
    ['线路租约', proxyTrafficValue(row, 'proxy_lease_id')],
    ['账号', proxyTrafficValue(row, 'account_id')],
    ['任务类型', proxyTrafficTaskTypeLabel(row)],
    ['注册 job', proxyTrafficValue(row, 'registration_job_id')],
    ['任务', proxyTrafficValue(row, 'operation_task_id')],
    ['运行', proxyTrafficValue(row, 'operation_run_id')],
    ['开始时间', proxyTrafficDate(proxyTrafficValue(row, 'started_at'))],
    ['完成时间', proxyTrafficDate(proxyTrafficValue(row, 'ended_at'))],
  ];
  title.textContent = view === 'history' ? '线路历史详情' : '请求流量详情';
  body.innerHTML = items.filter((item) => item[1] != null && item[1] !== '').map((item) => proxyTrafficField(item[0], item[1])).join('');
  dialog.showModal();
}

function proxyTrafficNormalizePage(view, payload) {
  if (!payload || typeof payload !== 'object') throw new Error('响应不是对象');
  if (payload.ok !== true) throw new Error(payload.error || `${view} 接口返回失败`);
  if (payload.view != null && payload.view !== view) throw new Error(`${view} 接口视图不匹配`);
  if (!Array.isArray(payload.items)) throw new Error(`${view} 接口缺少 items`);
  const count = Number(payload.count);
  const total = Number(payload.total);
  const limit = Number(payload.limit);
  const offset = Number(payload.offset);
  if (!Number.isInteger(count) || count < 0 || count !== payload.items.length || !Number.isInteger(total) || total < count || !Number.isInteger(limit) || limit < 1 || !Number.isInteger(offset) || offset < 0) {
    throw new Error(`${view} 接口分页字段无效`);
  }
  return {
    view,
    items: payload.items,
    count,
    total,
    limit,
    offset,
  };
}

async function proxyTrafficRequestPage(view) {
  const source = window.__PROXY_TRAFFIC_DATA_SOURCE__;
  const endpoint = PROXY_TRAFFIC_ENDPOINTS[view];
  const state = proxyTrafficPages[view];
  const options = {
    view, limit: state.size, offset: (state.page - 1) * state.size,
    window: proxyTrafficFilters.window,
    purpose: view === 'traffic' ? 'all' : proxyTrafficFilters.purpose,
    state: proxyTrafficStateFilters[view],
    search: proxyTrafficFilters.search.trim(),
  };
  if (typeof source === 'function') return source(endpoint, options);
  const params = new URLSearchParams(Object.fromEntries(Object.entries(options).filter(([key]) => key !== 'view')));
  return api(`${endpoint}?${params.toString()}`);
}

async function proxyTrafficRequestNormalizedPage(view, version = proxyTrafficDesiredVersion) {
  let page = proxyTrafficNormalizePage(view, await proxyTrafficRequestPage(view));
  if (version !== proxyTrafficDesiredVersion) throw PROXY_TRAFFIC_STALE;
  if (page.total === 0) {
    proxyTrafficPages[view].page = 1;
    return page;
  }
  if (page.offset >= page.total) {
    proxyTrafficPages[view].page = Math.ceil(page.total / proxyTrafficPages[view].size);
    page = proxyTrafficNormalizePage(view, await proxyTrafficRequestPage(view));
    if (version !== proxyTrafficDesiredVersion) throw PROXY_TRAFFIC_STALE;
  }
  return page;
}

async function proxyTrafficRequestSummary() {
  const source = window.__PROXY_TRAFFIC_DATA_SOURCE__;
  const payload = typeof source === 'function'
    ? await source(PROXY_TRAFFIC_ENDPOINTS.summary, {view: 'summary'})
    : await api(PROXY_TRAFFIC_ENDPOINTS.summary);
  if (!payload || payload.ok !== true || !Number.isFinite(Number(payload.total_bytes)) || !Number.isFinite(Number(payload.today_bytes))) {
    throw new Error('流量统计接口响应无效');
  }
  return payload;
}

function proxyTrafficApplyPage(view, page) {
  proxyTrafficSnapshot[PROXY_TRAFFIC_VIEW_CONFIG[view].key] = page.items;
  proxyTrafficPages[view].total = page.total;
}

async function proxyTrafficRequest(version = proxyTrafficDesiredVersion) {
  const [pages, summary] = await Promise.all([Promise.all(PROXY_TRAFFIC_VIEWS.map(async ({view, key}) => {
    const page = await proxyTrafficRequestNormalizedPage(view, version);
    return {key, page};
  })), proxyTrafficRequestSummary()]);
  if (version !== proxyTrafficDesiredVersion) throw PROXY_TRAFFIC_STALE;
  proxyTrafficSummary = summary;
  return pages.reduce((snapshot, {key, page}) => {
    snapshot[key] = page.items;
    const view = PROXY_TRAFFIC_VIEWS.find((item) => item.key === key).view;
    proxyTrafficPages[view].total = page.total;
    return snapshot;
  }, {});
}

async function loadProxyTraffic(view = null) {
  if (proxyTrafficLoading) {
    proxyTrafficReloadQueued = true;
    return;
  }
  proxyTrafficLoading = true;
  const version = proxyTrafficDesiredVersion;
  (view ? [view] : Object.keys(PROXY_TRAFFIC_VIEW_CONFIG)).forEach((name) => {
    proxyTrafficSetPanelState(name, 'loading', `正在加载${name === 'current' ? '当前租约' : name === 'history' ? '线路历史' : '请求流量'}`, '正在同步代理与流量 API');
  });
  try {
    if (view && proxyTrafficSnapshot) {
      const page = await proxyTrafficRequestNormalizedPage(view, version);
      if (version !== proxyTrafficDesiredVersion) throw PROXY_TRAFFIC_STALE;
      proxyTrafficApplyPage(view, page);
    } else {
      proxyTrafficSnapshot = await proxyTrafficRequest(version);
      proxyTrafficRefreshFilterOptions();
    }
    proxyTrafficRenderRows();
    proxyTrafficScrollResetViews.forEach((name) => {
      const tableWrap = document.querySelector(`[data-proxy-panel="${name}"] .proxy-traffic-table-wrap`);
      if (tableWrap) tableWrap.scrollTop = 0;
      proxyTrafficScrollResetViews.delete(name);
    });
    markViewReady('proxy-traffic');
  } catch (error) {
    if (error === PROXY_TRAFFIC_STALE) return;
    proxyTrafficSnapshot = null;
    proxyTrafficSummary = null;
    proxyTrafficRenderError(error);
  } finally {
    proxyTrafficLoading = false;
    if (proxyTrafficReloadQueued) {
      proxyTrafficReloadQueued = false;
      setTimeout(loadProxyTraffic, 0);
    }
  }
}

function proxyTrafficSetView(view, focus = false) {
  if (!PROXY_TRAFFIC_VIEW_CONFIG[view]) return;
  const dialog = document.getElementById('proxyTrafficDetailDialog');
  if (dialog?.open) dialog.close();
  proxyTrafficActiveView = view;
  document.querySelectorAll('[data-proxy-view]').forEach((button) => {
    const active = button.dataset.proxyView === view;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
    if (focus && active) button.focus();
  });
  document.querySelectorAll('[data-proxy-panel]').forEach((panel) => {
    const active = panel.dataset.proxyPanel === view;
    panel.classList.toggle('hidden', !active);
    panel.setAttribute('aria-hidden', active ? 'false' : 'true');
    if (active) {
      const reset = document.getElementById('btnResetProxyTrafficColumns');
      if (reset) {
        reset.dataset.proxyResetColumns = panel.querySelector('[data-resizable-table]').dataset.resizableTable;
        reset.setAttribute('aria-label', `恢复${panel.getAttribute('aria-label')}列宽`);
      }
    }
  });
}

function proxyTrafficBindControls() {
  const page = document.getElementById('tab-proxy-traffic');
  document.querySelectorAll('[data-proxy-view]').forEach((button) => {
    button.addEventListener('click', () => proxyTrafficSetView(button.dataset.proxyView));
  });
  document.querySelector('.proxy-traffic-view-tabs')?.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const buttons = [...document.querySelectorAll('[data-proxy-view]')];
    const current = buttons.indexOf(document.activeElement);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    event.preventDefault();
    proxyTrafficSetView(buttons[next].dataset.proxyView, true);
  });
  document.getElementById('btnClearProxyTrafficFilters')?.addEventListener('click', proxyTrafficClearFilters);
  page?.addEventListener('click', (event) => {
    const reset = event.target.closest?.('[data-proxy-reset-columns]');
    if (reset) {
      resetResizableTable(reset.dataset.proxyResetColumns);
      return;
    }
    const detail = event.target.closest?.('[data-proxy-detail]');
    if (detail) {
      proxyTrafficOpenDetail(detail.dataset.proxyDetail, detail.dataset.proxyDetailId);
      return;
    }
    if (event.target.closest?.('[data-proxy-close-detail]')) {
      document.getElementById('proxyTrafficDetailDialog')?.close();
      return;
    }
    const button = event.target.closest?.('[data-proxy-pager]');
    if (!button || button.disabled) return;
    const view = button.dataset.proxyPager;
    const state = proxyTrafficPages[view];
    if (!state) return;
    const maxPage = Math.max(1, Math.ceil(state.total / state.size));
    state.page = Math.max(1, Math.min(maxPage, state.page + (button.dataset.proxyPage === 'next' ? 1 : -1)));
    proxyTrafficScrollResetViews.add(view);
    proxyTrafficDesiredVersion += 1;
    loadProxyTraffic(view);
  });
  page?.addEventListener('change', (event) => {
    const select = event.target.closest?.('[data-proxy-page-size]');
    if (!select) return;
    const state = proxyTrafficPages[select.dataset.proxyPageSize];
    if (!state) return;
    state.size = Number(select.value) || 20;
    state.page = 1;
    proxyTrafficScrollResetViews.add(select.dataset.proxyPageSize);
    proxyTrafficDesiredVersion += 1;
    loadProxyTraffic(select.dataset.proxyPageSize);
  });
  document.getElementById('proxyTrafficDetailDialog')?.addEventListener('click', (event) => {
    if (event.target === event.currentTarget) event.currentTarget.close();
  });
}

function initProxyTraffic() {
  if (!document.getElementById('tab-proxy-traffic')) return;
  proxyTrafficInitColumnFilterFallback();
  proxyTrafficBindFallbackColumnFilters();
  proxyTrafficPopulateSelects('window', PROXY_TRAFFIC_WINDOW_OPTIONS, '全部时间');
  proxyTrafficBindFilterControls();
  proxyTrafficSyncFilterControls();
  proxyTrafficBindControls();
  proxyTrafficSetView(proxyTrafficActiveView);
  setInterval(() => {
    const page = document.getElementById('tab-proxy-traffic');
    if (!document.hidden && page && !page.classList.contains('hidden')) loadProxyTraffic();
  }, 30000);
}

initProxyTraffic();
