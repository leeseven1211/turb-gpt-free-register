/* Independent read-only view for the persistent proxy and browser-traffic contract. */
const PROXY_TRAFFIC_ENDPOINTS = Object.freeze({
  current: '/api/proxy-traffic/current',
  history: '/api/proxy-traffic/history',
  traffic: '/api/proxy-traffic/traffic',
});
const PROXY_TRAFFIC_REQUEST_PAGE = Object.freeze({limit: 200, offset: 0});
const PROXY_TRAFFIC_VIEWS = Object.freeze([
  {view: 'current', key: 'current_leases'},
  {view: 'history', key: 'lease_history'},
  {view: 'traffic', key: 'browser_traffic'},
]);
const PROXY_TRAFFIC_KEYS = PROXY_TRAFFIC_VIEWS.map(({key}) => key);
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
    title: '暂无浏览器流量',
    description: '当前没有可显示的 Roxy/CDP 流量摘要；协议任务会显示为未采集。',
  },
};
const PROXY_TRAFFIC_STATUS_TEXT = {
  loading: '正在加载',
  ready: '已同步',
  empty: '暂无记录',
  error: '加载失败',
};
const PROXY_TRAFFIC_STATUS_LABELS = {
  leased: '租约中',
  recent: '最近释放',
  released: '已释放',
  expired: '已过期',
  failed: '失败',
  unavailable: '未采集',
  observed: '可观测',
  complete: '已完成',
  running: '运行中',
};

let proxyTrafficSnapshot = null;
let proxyTrafficActiveView = 'current';
let proxyTrafficLoading = false;
let proxyTrafficReloadQueued = false;
const proxyTrafficFilters = {window: 'all', purpose: 'all', state: 'all', search: ''};

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

function proxyTrafficDetails(items) {
  const visible = items.filter((item) => item[1] != null && item[1] !== '');
  if (!visible.length) return '<span class="proxy-traffic-muted">—</span>';
  return `<details class="proxy-traffic-row-details"><summary>详情</summary><dl>${visible.map((item) => proxyTrafficField(item[0], item[1], item[2] || '')).join('')}</dl></details>`;
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
    <td>${proxyTrafficDetails([
      ['租约 ID', proxyTrafficValue(row, 'lease_id'), 'proxy-traffic-id'],
      ['重试序号', proxyTrafficValue(row, 'route_attempt_no')],
      ['获取时间', proxyTrafficDate(proxyTrafficValue(row, 'acquired_at'))],
      ['释放时间', proxyTrafficDate(proxyTrafficValue(row, 'released_at'))],
    ])}</td>
  </tr>`;
}

function proxyTrafficRenderTraffic(row) {
  const source = String(proxyTrafficValue(row, 'source') || '');
  const upload = proxyTrafficNumber(row, 'upload_bytes');
  const download = proxyTrafficNumber(row, 'download_bytes');
  const total = proxyTrafficNumber(row, 'total_bytes');
  const availability = String(proxyTrafficValue(row, 'availability') || '').toLowerCase();
  const unavailable = availability !== 'available' || total == null;
  const byteText = unavailable ? '未采集' : `${proxyTrafficBytes(upload)} / ${proxyTrafficBytes(download)} / ${proxyTrafficBytes(total)}`;
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
    <td>${proxyTrafficCorrelation(row)}</td>
    <td>${proxyTrafficDate(proxyTrafficValue(row, 'started_at'))}</td>
    <td>${proxyTrafficDetails([
      ['来源', proxyTrafficValue(row, 'source')],
      ['方法', proxyTrafficValue(row, 'method')],
      ['上传字节', upload == null ? '' : proxyTrafficBytes(upload)],
      ['下载字节', download == null ? '' : proxyTrafficBytes(download)],
      ['总字节', total == null ? '' : proxyTrafficBytes(total)],
      ['完成时间', proxyTrafficDate(proxyTrafficValue(row, 'ended_at'))],
    ])}</td>
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

function proxyTrafficTimeLimit() {
  const now = Date.now();
  return {all: null, '1h': now - 60 * 60 * 1000, '24h': now - 24 * 60 * 60 * 1000, '7d': now - 7 * 24 * 60 * 60 * 1000}[proxyTrafficFilters.window];
}

function proxyTrafficInWindow(row) {
  const limit = proxyTrafficTimeLimit();
  if (limit == null) return true;
  const values = ['acquired_at', 'released_at', 'started_at', 'ended_at']
    .map((key) => new Date(proxyTrafficValue(row, key)).getTime())
    .filter((value) => Number.isFinite(value));
  return !values.length || values.some((value) => value >= limit);
}

function proxyTrafficMatches(row) {
  if (proxyTrafficFilters.purpose !== 'all' && String(proxyTrafficValue(row, 'purpose')) !== proxyTrafficFilters.purpose) return false;
  const rowState = proxyTrafficValue(row, 'state') || proxyTrafficValue(row, 'availability');
  if (proxyTrafficFilters.state !== 'all' && String(rowState) !== proxyTrafficFilters.state) return false;
  if (!proxyTrafficInWindow(row)) return false;
  const search = proxyTrafficFilters.search.trim().toLowerCase();
  if (!search) return true;
  return [
    'lease_id', 'provider', 'exit_ip', 'account_id', 'purpose', 'operation_task_id',
    'operation_run_id', 'registration_job_id', 'proxy_lease_id', 'source', 'method', 'state',
  ].some((key) => String(proxyTrafficValue(row, key)).toLowerCase().includes(search));
}

function proxyTrafficRows(view) {
  const config = PROXY_TRAFFIC_VIEW_CONFIG[view];
  return proxyTrafficSnapshot?.[config.key]?.filter(proxyTrafficMatches) || [];
}

function proxyTrafficPopulateSelect(id, values, current) {
  const select = document.getElementById(id);
  if (!select) return;
  const options = ['<option value="all">全部' + (id === 'proxyTrafficPurpose' ? '用途' : '状态') + '</option>'];
  values.forEach((value) => options.push(`<option value="${proxyTrafficEsc(value)}">${proxyTrafficEsc(value)}</option>`));
  select.innerHTML = options.join('');
  select.value = values.includes(current) ? current : 'all';
}

function proxyTrafficRefreshFilterOptions() {
  if (!proxyTrafficSnapshot) return;
  const purposes = new Set();
  const states = new Set();
  PROXY_TRAFFIC_KEYS.forEach((key) => {
    proxyTrafficSnapshot[key].forEach((row) => {
      const purpose = proxyTrafficValue(row, 'purpose');
      const state = proxyTrafficValue(row, 'state') || proxyTrafficValue(row, 'availability');
      if (purpose) purposes.add(String(purpose));
      if (state) states.add(String(state));
    });
  });
  proxyTrafficPopulateSelect('proxyTrafficPurpose', [...purposes].sort(), proxyTrafficFilters.purpose);
  proxyTrafficPopulateSelect('proxyTrafficState', [...states].sort(), proxyTrafficFilters.state);
}

function proxyTrafficRenderSummary() {
  const counts = {
    current: proxyTrafficRows('current').length,
    history: proxyTrafficRows('history').length,
    traffic: proxyTrafficRows('traffic').length,
  };
  let totalBytes = 0;
  let hasBytes = false;
  proxyTrafficRows('traffic').forEach((row) => {
    const value = proxyTrafficNumber(row, 'total_bytes');
    if (value != null) {
      totalBytes += value;
      hasBytes = true;
    }
  });
  Object.entries(counts).forEach(([key, value]) => {
    const element = document.querySelector(`[data-proxy-summary="${key}"]`);
    if (element) element.textContent = String(value);
  });
  const bytes = document.querySelector('[data-proxy-summary="bytes"]');
  if (bytes) bytes.textContent = hasBytes ? proxyTrafficBytes(totalBytes) : '未采集';
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
    if (status) status.textContent = rows.length ? `${rows.length} 条记录` : PROXY_TRAFFIC_STATUS_TEXT.empty;
    const count = document.querySelector(`[data-proxy-count="${view}"]`);
    if (count) count.textContent = String(rows.length);
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

function proxyTrafficNormalizePage(view, payload) {
  if (!payload || typeof payload !== 'object') throw new Error('响应不是对象');
  if (payload.ok !== true) throw new Error(payload.error || `${view} 接口返回失败`);
  if (payload.view != null && payload.view !== view) throw new Error(`${view} 接口视图不匹配`);
  if (!Array.isArray(payload.items)) throw new Error(`${view} 接口缺少 items`);
  const count = Number(payload.count);
  const limit = Number(payload.limit);
  const offset = Number(payload.offset);
  if (!Number.isInteger(count) || count < 0 || !Number.isInteger(limit) || limit < 1 || !Number.isInteger(offset) || offset < 0) {
    throw new Error(`${view} 接口分页字段无效`);
  }
  return {
    view,
    items: payload.items,
    count,
    limit,
    offset,
  };
}

async function proxyTrafficRequestPage(view) {
  const source = window.__PROXY_TRAFFIC_DATA_SOURCE__;
  const endpoint = PROXY_TRAFFIC_ENDPOINTS[view];
  const {limit, offset} = PROXY_TRAFFIC_REQUEST_PAGE;
  if (typeof source === 'function') return source(endpoint, {view, limit, offset});
  const params = new URLSearchParams({limit: String(limit), offset: String(offset)});
  return api(`${endpoint}?${params.toString()}`);
}

async function proxyTrafficRequest() {
  const pages = await Promise.all(PROXY_TRAFFIC_VIEWS.map(async ({view, key}) => {
    const page = proxyTrafficNormalizePage(view, await proxyTrafficRequestPage(view));
    return {key, page};
  }));
  const firstPage = pages[0].page;
  if (pages.some(({page}) => page.limit !== firstPage.limit || page.offset !== firstPage.offset)) {
    throw new Error('代理与流量接口分页字段不一致');
  }
  return pages.reduce((snapshot, {key, page}) => {
    snapshot[key] = page.items;
    return snapshot;
  }, {});
}

function proxyTrafficSetRefreshState(loading) {
  const button = document.getElementById('btnRefreshProxyTraffic');
  if (!button) return;
  button.disabled = loading;
  button.setAttribute('aria-busy', loading ? 'true' : 'false');
  const label = button.querySelector('span');
  if (label) label.textContent = loading ? '刷新中…' : '刷新';
}

async function loadProxyTraffic() {
  if (proxyTrafficLoading) {
    proxyTrafficReloadQueued = true;
    return;
  }
  proxyTrafficLoading = true;
  proxyTrafficSetRefreshState(true);
  Object.keys(PROXY_TRAFFIC_VIEW_CONFIG).forEach((view) => {
    proxyTrafficSetPanelState(view, 'loading', `正在加载${view === 'current' ? '当前租约' : view === 'history' ? '线路历史' : '浏览器流量'}`, '正在同步代理与流量 API');
  });
  try {
    proxyTrafficSnapshot = await proxyTrafficRequest();
    proxyTrafficRefreshFilterOptions();
    proxyTrafficRenderRows();
    const updated = document.getElementById('proxyTrafficLastUpdated');
    if (updated) updated.textContent = `已同步 ${new Date().toLocaleTimeString('zh-CN', {hour12: false})}`;
  } catch (error) {
    proxyTrafficSnapshot = null;
    proxyTrafficRenderError(error);
    const updated = document.getElementById('proxyTrafficLastUpdated');
    if (updated) updated.textContent = '加载失败';
  } finally {
    proxyTrafficLoading = false;
    proxyTrafficSetRefreshState(false);
    if (proxyTrafficReloadQueued) {
      proxyTrafficReloadQueued = false;
      setTimeout(loadProxyTraffic, 0);
    }
  }
}

function proxyTrafficSetView(view, focus = false) {
  if (!PROXY_TRAFFIC_VIEW_CONFIG[view]) return;
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
  });
}

function proxyTrafficBindControls() {
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
  document.getElementById('btnRefreshProxyTraffic')?.addEventListener('click', loadProxyTraffic);
  document.getElementById('btnClearProxyTrafficFilters')?.addEventListener('click', () => {
    proxyTrafficFilters.window = 'all';
    proxyTrafficFilters.purpose = 'all';
    proxyTrafficFilters.state = 'all';
    proxyTrafficFilters.search = '';
    document.getElementById('proxyTrafficWindow').value = 'all';
    document.getElementById('proxyTrafficPurpose').value = 'all';
    document.getElementById('proxyTrafficState').value = 'all';
    document.getElementById('proxyTrafficSearch').value = '';
    proxyTrafficRenderRows();
  });
  document.getElementById('proxyTrafficWindow')?.addEventListener('change', (event) => {
    proxyTrafficFilters.window = event.target.value;
    proxyTrafficRenderRows();
  });
  document.getElementById('proxyTrafficPurpose')?.addEventListener('change', (event) => {
    proxyTrafficFilters.purpose = event.target.value;
    proxyTrafficRenderRows();
  });
  document.getElementById('proxyTrafficState')?.addEventListener('change', (event) => {
    proxyTrafficFilters.state = event.target.value;
    proxyTrafficRenderRows();
  });
  document.getElementById('proxyTrafficSearch')?.addEventListener('input', (event) => {
    proxyTrafficFilters.search = event.target.value;
    proxyTrafficRenderRows();
  });
}

function initProxyTraffic() {
  if (!document.getElementById('tab-proxy-traffic')) return;
  proxyTrafficBindControls();
  proxyTrafficSetView(proxyTrafficActiveView);
  setInterval(() => {
    const page = document.getElementById('tab-proxy-traffic');
    if (!document.hidden && page && !page.classList.contains('hidden')) loadProxyTraffic();
  }, 30000);
}

initProxyTraffic();
