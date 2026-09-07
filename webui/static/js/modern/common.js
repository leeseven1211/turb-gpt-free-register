const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
let copySeq = 0;
const copyStore = new Map();
let ACCOUNTS = [], OUTLOOK = [], CONFIG = [];
let ACCOUNT_TASKS = [], ACCOUNT_TASKS_TOTAL = 0;
let ACCOUNTS_TOTAL = 0;
let OUTLOOK_TOTAL = 0;
let outlookLoading = false;
let outlookReloadQueued = false;
let SHOW_ARCHIVED_ACCOUNTS = false;
let SHOW_PLUS_ACCOUNTS_ONLY = false;
const ACCOUNT_SELECTED = new Set();
const OUTLOOK_SELECTED = new Set();
let JOBS = [];
let JOBS_TOTAL = 0;
let JOB_STATUS_COUNTS = {};
let JOB_PROGRESS_BATCH = null;
let JOB_PROGRESS_BATCHES = [];
let JOB_PROGRESS_BATCH_ID = localStorage.getItem('gpt_console_registration_batch_id') || '';
let JOB_STATUS_FILTER = '';
let JOB_ID_FILTER = '';
let JOB_EMAIL_FILTER = '';
let JOB_EMAIL_SOURCE_FILTER = '';
let JOB_PROXY_FILTER = '';
let JOB_ERROR_FILTER = '';
let JOB_DATE_FROM = '';
let JOB_DATE_TO = '';
let jobsRenderSignature = '';
let batchProgressRenderSignature = '';
const JOB_SELECTED = new Set();
let REGISTRATION_EMAIL_SOURCES = [];
let activeLogJob = null, logTimer = null, jobsTimer = null;
let summaryLoading = false;
let dashboardLoading = false;
let jobsLoading = false;
let jobsReloadQueued = false;
let accountTasksLoading = false;

const LIST_FACET_LABELS = {
  status: {
    queued:'排队中', pending:'排队中', running:'运行中', waiting:'等待中', stopping:'停止中', cancelling:'停止中', settling:'收尾中',
    failed:'失败', partial_success:'部分成功', success:'成功', stopped:'已停止', cancelled:'已取消', interrupted:'执行中断',
    deactivated:'已停用', unsupported:'不支持', attention_required:'需人工处理',
    available:'可用', used:'已使用', disabled:'停用', exported:'已导出', unexported:'未导出', archived:'已归档',
  },
  source: {
    outlook:'Outlook', generic_api:'通用 API', cloudflare_domain:'域名邮箱', cloudflare_temp:'Cloudflare 临时邮箱',
    icloud_hide:'iCloud 隐藏邮箱', email_butler:'Email Butler', gptmail:'GPTMail', mailnest:'MailNest', cloudmail:'CloudMail',
  },
  token: {has:'有 Token', none:'无 Token'},
  account_token: {
    has:'正常', expired:'过期', invalid_401:'失效 · 401', invalid_403:'失效 · 403',
    invalid_other:'失效 · 其他', none:'无 Token',
  },
  password: {has:'已设置', none:'未设置'},
  totp: {enabled:'已启用', disabled:'未启用'},
  risk: {detected:'已收到', clear:'未发现', pending:'待处理'},
  trial: {eligible:'可用', ineligible:'不可用', pending:'待查询', failed:'查询失败', not_applicable:'不适用'},
  codex: {success:'已通过', retrying:'进行中', failed:'失败', stopped:'已停止', deactivated:'已停用', skipped:'已跳过', missing:'缺失'},
  account_status: {active:'正常', deactivated:'已废号', unknown:'待确认'},
  task_type: {
    registration:'注册', registration_resume:'继续邮箱验证', twofa_retry:'2FA 配置补跑',
    account_setup_retry:'账号配置补跑', password_setup:'补密码', twofa_setup:'补 2FA', account_completion:'补全账号',
    codex_retry:'Codex 补跑', codex_token_refresh:'Codex Token 刷新',
    live_check:'查活', token_refresh:'AT 刷新', plan_check:'查套餐', deactivation_mail:'查封号邮件',
  },
  target_status: {
    not_created:'尚未创建', in_progress:'处理中', email_verification_pending:'待邮箱验证或资料补全',
    account_available:'账号可用', credential_valid:'凭证有效', credential_pending_confirmation:'凭证待确认',
    attention_required:'需人工处理', deactivated:'账号已停用', account_deactivated:'账号已停用',
    cancelled:'已取消', failed:'失败', pending:'等待执行', request_unknown:'结果待确认',
    manual_reconcile:'需人工对账', completed:'已完成', unknown:'状态待确认',
  },
  stage: {
    queued:'进入队列', running:'执行中', preflight:'配置预检', network:'分配网络', network_route:'分配网络',
    driver:'启动浏览器', email:'准备邮箱', browser:'启动浏览器', page:'打开页面', submit_email:'提交邮箱',
    auth_redirect:'进入认证', email_otp:'邮箱验证', profile:'账号资料', token:'获取 Token', codex:'Codex 授权',
    login_password:'账号密码', mfa_challenge:'TOTP 验证', account_setup:'账号配置', access_token:'校验 Token', reauth:'重新登录',
    roxy_fallback:'浏览器回退', oauth:'Codex 授权', auth_url:'获取授权地址', login:'登录 OpenAI',
    phone_check:'检查手机验证', phone_acquire:'申请接码号码', phone_otp:'短信验证', consent:'确认授权',
    callback:'接收 OAuth 回调', credential_confirm:'确认远端凭证', credential_persist:'保存凭证', cancelling:'正在停止',
    twofa:'设置 2FA', plan:'套餐信息', plan_check:'查询套餐', plan_request:'请求套餐', refresh_token:'刷新 Token',
    mailbox_scan:'扫描邮件', complete:'完成', interrupted:'执行中断', event:'事件',
  },
  run_count: {'0':'0 次', '1':'1 次', '2':'2 次', '3':'3 次', '4+':'4 次及以上'},
};
function facetLabel(group, value) {
  const key = String(value || '').toLowerCase();
  if (group === 'plan') return key ? key.charAt(0).toUpperCase() + key.slice(1) : '-';
  return LIST_FACET_LABELS[group]?.[key] || key || '-';
}
function syncFacetSelect(id, items, {group='', allValue='', allLabel='全部', values=[]} = {}) {
  const select = document.getElementById(id);
  if (!select) return;
  const current = select.value;
  const sourceRows = Array.isArray(items) ? items : [];
  const dataRows = sourceRows.filter(item => {
    const value = String(item?.value || '').trim();
    return value && Number(item?.count || 0) > 0;
  });
  const counts = new Map(dataRows.map(item => [String(item.value), Number(item.count || 0)]));
  const orderedValues = Array.isArray(values)
    ? values.map(String).filter(value => counts.has(value))
    : [];
  const rows = orderedValues.length
    ? orderedValues.map(value => ({value, count: counts.get(value) || 0}))
      .concat(dataRows.filter(item => !orderedValues.includes(String(item.value))))
    : dataRows;
  const options = [{value: allValue, label: allLabel}].concat(rows.map(item => ({
    value: String(item.value || ''),
    label: `${facetLabel(group, item.value)} · ${Number(item.count || 0)}`,
  })));
  select.innerHTML = options.map(item => `<option value="${attrEsc(item.value)}">${esc(item.label)}</option>`).join('');
  select.value = options.some(item => item.value === current) ? current : allValue;
  refreshColumnFilterState(select);
  renderColumnFilterOptions(select);
}

// ---------- 分页状态 ----------
const PAGERS = {
  jobs:     { page: 1, size: 20 },
  accounts: { page: 1, size: 20 },
  outlook:  { page: 1, size: 20 },
  codex:    { page: 1, size: 20 },
  accountTasks: { page: 1, size: 20 },
};

function _renderPager(id, total) {
  const p = PAGERS[id];
  const totalPages = Math.max(1, Math.ceil(total / p.size));
  if (p.page > totalPages) p.page = Math.max(1, totalPages);
  const start = total > 0 ? (p.page - 1) * p.size + 1 : 0;
  const end = Math.min(p.page * p.size, total);
  const sizes = [20, 50, 100];
  const html = `
    <button onclick="pagerGo('${id}',-1)"${p.page <= 1 ? ' disabled' : ''}>← 上一页</button>
    <span class="pager-info">${total > 0 ? `第 ${start}–${end} 条 / 共 ${total} 条（第 ${p.page} / ${totalPages} 页）` : '无数据'}</span>
    <button onclick="pagerGo('${id}',1)"${p.page >= totalPages ? ' disabled' : ''}>下一页 →</button>
    <select onchange="pagerSetSize('${id}',this.value)">${sizes.map(s =>
      `<option value="${s}"${p.size === s ? ' selected' : ''}>${s} 条/页</option>`
    ).join('')}</select>`;
  const el = document.getElementById('pager-' + id);
  if (el) el.innerHTML = html;

  if (id === 'jobs' || id === 'accounts' || id === 'codex' || id === 'outlook' || id === 'accountTasks') {
    const elV2 = document.getElementById(
      id === 'jobs' ? 'pager-jobs-v2'
        : id === 'accounts' ? 'pager-accounts-v2'
        : id === 'codex' ? 'pager-codex-v2'
        : id === 'accountTasks' ? 'pager-accountTasks-v2'
        : 'pager-outlook-v2'
    );
    if (elV2) {
      const sizeWrapId = id === 'jobs' ? 'jobsPagerSize'
        : id === 'accounts' ? 'accountsPagerSize'
        : id === 'codex' ? 'codexPagerSize'
        : id === 'accountTasks' ? 'accountTasksPagerSize'
        : 'outlookPagerSize';
      const v2Sizes = [10, 20, 30, 50, 100];
      const pages = [];
      let from = Math.max(1, p.page - 2);
      let to = Math.min(totalPages, from + 4);
      from = Math.max(1, to - 4);
      for (let i = from; i <= to; i++) {
        pages.push(i === p.page
          ? `<span class="pager-page">${i}</span>`
          : `<button type="button" onclick="pagerGoTo('${id}',${i})">${i}</button>`);
      }
      elV2.innerHTML = `
        <span class="pager-total">共 ${total} 条</span>
        <button type="button" onclick="pagerGo('${id}',-1)"${p.page <= 1 ? ' disabled' : ''} title="上一页">‹</button>
        ${pages.join('')}
        <button type="button" onclick="pagerGo('${id}',1)"${p.page >= totalPages ? ' disabled' : ''} title="下一页">›</button>
        <div class="pager-size" id="${sizeWrapId}">
          <button type="button" class="pager-size-btn" onclick="toggleV2PagerSize(event,'${sizeWrapId}')">${p.size}条/页</button>
          <div class="pager-size-menu" role="listbox">
            ${v2Sizes.map(s =>
              `<button type="button" class="pager-size-item${p.size === s ? ' is-active' : ''}" role="option" onclick="pickV2PagerSize('${id}','${sizeWrapId}',${s})">${s}条/页</button>`
            ).join('')}
          </div>
        </div>
        <label class="pager-goto">前往
          <input type="number" min="1" max="${totalPages}" value="${p.page}" inputmode="numeric"
            onkeydown="if(event.key==='Enter'){pagerJump('${id}',this.value);event.preventDefault();}"
            onchange="pagerJump('${id}',this.value)">
          页
        </label>`;
    }
  }
}
function toggleV2PagerSize(e, wrapId) {
  e.stopPropagation();
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  const open = wrap.classList.toggle('open');
  if (open) {
    const closer = (ev) => {
      if (wrap.contains(ev.target)) return;
      wrap.classList.remove('open');
      document.removeEventListener('click', closer);
    };
    setTimeout(() => document.addEventListener('click', closer), 0);
  }
}
function pickV2PagerSize(id, wrapId, size) {
  const wrap = document.getElementById(wrapId);
  if (wrap) wrap.classList.remove('open');
  pagerSetSize(id, size);
}
function toggleJobsPagerSize(e) { toggleV2PagerSize(e, 'jobsPagerSize'); }
function pickJobsPagerSize(size) { pickV2PagerSize('jobs', 'jobsPagerSize', size); }
function pagerGoTo(id, page) {
  const p = PAGERS[id];
  if (!p) return;
  const total = id === 'jobs' ? JOBS_TOTAL
    : id === 'accounts' ? ACCOUNTS_TOTAL
    : id === 'outlook' ? OUTLOOK_TOTAL
    : id === 'codex' ? CODEX_TOTAL
    : id === 'accountTasks' ? ACCOUNT_TASKS_TOTAL
    : (p.size || 20);
  const totalPages = Math.max(1, Math.ceil(Number(total || 0) / p.size) || 1);
  p.page = Math.max(1, Math.min(parseInt(page, 10) || 1, totalPages));
  _reloadPagedList(id);
}
function pagerJump(id, val) {
  pagerGoTo(id, val);
}

function _reloadPagedList(id) {
  ({ jobs: refreshJobs, accounts: loadAccounts, outlook: loadOutlook, codex: loadCodex, accountTasks: loadAccountTasks })[id]?.();
}
function pagerGo(id, dir) {
  PAGERS[id].page = Math.max(1, PAGERS[id].page + dir);
  _reloadPagedList(id);
}
function pagerSetSize(id, val) {
  PAGERS[id].size = parseInt(val, 10) || 20;
  PAGERS[id].page = 1;
  _reloadPagedList(id);
}

// ---------- 统一列表列宽 ----------
const TABLE_DEFAULT_WIDTHS = {
  jobs:     [4, 6, 15, 9, 11, 8, 9, 9, 13, 16],
  // Desktop account rows need to scan in one viewport; long values keep
  // their full text in the cell title and the detail drawer.
  accounts: [3, 4, 17, 7, 6, 6, 7, 7, 10, 9, 8, 8, 8],
  codex:    [4, 19, 7, 9, 9, 11, 11, 11, 19],
  outlook:  [4, 20, 9, 9, 8, 14, 14, 18],
  accountTasks: [6, 9, 18, 10, 11, 13, 10, 11, 17, 15, 10],
};
const TABLE_WIDTH_STORAGE_PREFIX = 'gpt_console_table_widths_';

function applyResizableTableWidths(table, widths) {
  const cols = Array.from(table.querySelectorAll('colgroup col'));
  if (!cols.length || !Array.isArray(widths) || widths.length !== cols.length) return;
  const total = widths.reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0) || 100;
  cols.forEach((col, index) => { col.style.width = `${Math.max(0, Number(widths[index]) || 0) / total * 100}%`; });
}

function readSavedTableWidths(key, expectedLength) {
  try {
    const widths = JSON.parse(localStorage.getItem(TABLE_WIDTH_STORAGE_PREFIX + key) || 'null');
    return Array.isArray(widths) && widths.length === expectedLength ? widths : null;
  } catch(e) { return null; }
}

function saveTableWidths(key, widths) {
  localStorage.setItem(TABLE_WIDTH_STORAGE_PREFIX + key, JSON.stringify(widths.map(value => Number(value.toFixed(4)))));
}

function resetResizableTable(key) {
  const table = document.querySelector(`table[data-resizable-table="${key}"]`);
  if (!table) return;
  localStorage.removeItem(TABLE_WIDTH_STORAGE_PREFIX + key);
  applyResizableTableWidths(table, TABLE_DEFAULT_WIDTHS[key]);
  showToast('已恢复默认列宽');
}

function initResizableTable(table) {
  if (!table || table.dataset.resizableReady === '1') return;
  const key = table.dataset.resizableTable;
  const cols = Array.from(table.querySelectorAll('colgroup col'));
  const headers = Array.from(table.querySelectorAll('thead tr:first-child th'));
  if (!key || !cols.length || cols.length !== headers.length) return;
  table.dataset.resizableReady = '1';
  applyResizableTableWidths(table, readSavedTableWidths(key, cols.length) || TABLE_DEFAULT_WIDTHS[key]);

  headers.forEach((header, index) => {
    if (index === 0 || index >= headers.length - 1) return;
    const handle = document.createElement('span');
    handle.className = 'table-col-resizer';
    handle.title = '拖动调整列宽';
    handle.setAttribute('aria-hidden', 'true');
    header.appendChild(handle);
    handle.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      const tableWidth = Math.max(1, table.getBoundingClientRect().width);
      const startX = event.clientX;
      const startWidths = headers.map(item => item.getBoundingClientRect().width);
      const nextIndex = index + 1;
      const minCurrent = 64;
      const minNext = headers[nextIndex].classList.contains('col-actions') ? 108 : 64;
      handle.classList.add('is-dragging');
      document.body.classList.add('is-resizing-table-column');

      const onMove = moveEvent => {
        let delta = moveEvent.clientX - startX;
        delta = Math.max(minCurrent - startWidths[index], Math.min(delta, startWidths[nextIndex] - minNext));
        const nextWidths = [...startWidths];
        nextWidths[index] += delta;
        nextWidths[nextIndex] -= delta;
        applyResizableTableWidths(table, nextWidths.map(value => value / tableWidth));
      };
      const onUp = () => {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        document.removeEventListener('pointercancel', onUp);
        handle.classList.remove('is-dragging');
        document.body.classList.remove('is-resizing-table-column');
        const finalWidth = Math.max(1, table.getBoundingClientRect().width);
        saveTableWidths(key, headers.map(item => item.getBoundingClientRect().width / finalWidth));
      };
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
      document.addEventListener('pointercancel', onUp);
    });
  });
}

function initResizableTables() {
  document.querySelectorAll('table[data-resizable-table]').forEach(initResizableTable);
  const resetButtons = {
    btnResetJobsColumnsV2: 'jobs',
    btnResetAccountsColumnsV2: 'accounts',
    btnResetCodexColumnsV2: 'codex',
    btnResetOutlookColumnsV2: 'outlook',
    btnResetAccountTaskColumnsV2: 'accountTasks',
  };
  Object.entries(resetButtons).forEach(([id, key]) => {
    document.getElementById(id)?.addEventListener('click', () => resetResizableTable(key));
  });
}

// ---------- 统一列表表头筛选 ----------
const COLUMN_FILTER_RESET_IDS = {
  jobs: 'btnResetJobFiltersV2',
  accounts: 'btnResetAccountFiltersV2',
  codex: 'btnResetCodexFiltersV2',
  outlook: 'btnResetOutlookFiltersV2',
  accountTasks: 'btnResetAccountTaskFiltersV2',
};

function columnFilterIcon(type) {
  if (type === 'search') {
    return `<svg class="column-filter-trigger-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="3.75"></circle><path d="m10 10 3 3"></path></svg>`;
  }
  if (type === 'date' || type === 'date-range') {
    return `<svg class="column-filter-trigger-icon" viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="3.5" width="11" height="10" rx="2"></rect><path d="M5 2v3M11 2v3M2.5 6.5h11"></path></svg>`;
  }
  return `<svg class="column-filter-trigger-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 3.5h11L9.3 8.3v3.4l-2.6 1.2V8.3z"></path></svg>`;
}

function columnFilterControls(header) {
  if (!header) return [];
  return Array.from(header.querySelectorAll('.column-filter-search input, .column-filter-native, .column-filter-date-field input'));
}

function columnFilterEmptyValue(header, control) {
  return control?.id === header?.dataset.columnFilter ? (header.dataset.filterEmptyValue || '') : '';
}

function refreshColumnFilterState(control) {
  const header = control?.closest?.('[data-column-filter]');
  if (!header) return;
  const hasValue = columnFilterControls(header).some(item => String(item.value ?? '') !== columnFilterEmptyValue(header, item));
  header.classList.toggle('has-filter-value', hasValue);
  if (control.matches?.('select')) renderColumnFilterOptions(control);
  renderColumnFilterSummaryForTable(header.closest('table[data-resizable-table]'));
}

function refreshColumnFilterStates() {
  document.querySelectorAll('[data-column-filter]').forEach(header => {
    const control = document.getElementById(header.dataset.columnFilter);
    if (control) refreshColumnFilterState(control);
  });
  document.querySelectorAll('table[data-resizable-table]').forEach(renderColumnFilterSummaryForTable);
}

function closeColumnFilterPopovers(exceptHeader = null) {
  document.querySelectorAll('.column-filter-header.is-filter-open').forEach(header => {
    if (header === exceptHeader) return;
    header.classList.remove('is-filter-open');
    header.querySelector('[data-column-filter-trigger]')?.setAttribute('aria-expanded', 'false');
  });
}

function closeColumnFilterSearches(exceptHeader = null, restoreFocus = false) {
  document.querySelectorAll('.column-filter-header.is-searching').forEach(header => {
    if (header === exceptHeader) return;
    header.classList.remove('is-searching');
    if (restoreFocus) header.querySelector('[data-column-filter-trigger]')?.focus({preventScroll:true});
  });
}

function positionColumnFilterPopover(header) {
  const trigger = header?.querySelector('[data-column-filter-trigger]');
  const popover = header?.querySelector('.column-filter-popover');
  if (!trigger || !popover) return;
  const rect = trigger.getBoundingClientRect();
  const type = header.dataset.filterType || 'search';
  const preferredWidth = type === 'date-range'
    ? 292
    : type === 'date'
      ? 202
      : Math.min(220, Math.max(148, rect.width + 42));
  const width = Math.min(preferredWidth, Math.max(148, window.innerWidth - 20));
  const left = Math.max(10, Math.min(rect.left, window.innerWidth - width - 10));
  popover.style.width = `${width}px`;
  const estimatedHeight = Math.max(48, popover.offsetHeight || 48);
  const below = rect.bottom + 6;
  const top = below + estimatedHeight <= window.innerHeight - 10
    ? below
    : Math.max(10, rect.top - estimatedHeight - 6);
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
}

function renderColumnFilterOptions(select) {
  const header = select?.closest?.('.column-filter-header');
  const list = header?.querySelector('[data-column-filter-options]');
  if (!header || !list) return;
  list.innerHTML = Array.from(select.options).map(option => `
    <button type="button" class="column-filter-option" role="menuitemradio"
      data-column-filter-option="${attrEsc(option.value)}" aria-checked="${option.selected ? 'true' : 'false'}">
      <span>${esc(option.textContent || option.label || '全部')}</span>
      <svg class="column-filter-option-check" viewBox="0 0 16 16" aria-hidden="true"><path d="m3 8.3 3.1 3L13 4.7"></path></svg>
    </button>`).join('');
}

function columnFilterDisplayValue(header) {
  const type = header.dataset.filterType || 'search';
  const primary = document.getElementById(header.dataset.columnFilter);
  if (!primary) return '';
  if (type === 'select') {
    const selected = primary.options?.[primary.selectedIndex];
    return selected ? String(selected.textContent || '').replace(/\s*·\s*\d+\s*$/, '') : '';
  }
  if (type === 'date-range') {
    const end = document.getElementById(header.dataset.filterEndId || '');
    return [primary.value, end?.value].filter(Boolean).join(' → ');
  }
  return String(primary.value || '').trim();
}

function renderColumnFilterSummaryForTable(table) {
  if (!table) return;
  const scope = table.dataset.resizableTable;
  const summary = document.querySelector(`[data-filter-summary="${scope}"]`);
  if (!summary) return;
  const active = Array.from(table.querySelectorAll('[data-column-filter].has-filter-value')).map(header => ({
    id: header.dataset.columnFilter,
    label: header.dataset.filterTitle || '',
    value: columnFilterDisplayValue(header),
  })).filter(item => item.value);
  summary.hidden = active.length === 0;
  if (!active.length) {
    summary.innerHTML = '';
    return;
  }
  summary.innerHTML = `
    <span class="column-filter-summary-label">当前筛选</span>
    ${active.map(item => `<button type="button" class="column-filter-chip" data-clear-filter-id="${attrEsc(item.id)}" title="清除 ${attrEsc(item.label)} 筛选"><span>${esc(item.label)}：${esc(item.value)}</span><span class="column-filter-chip-close" aria-hidden="true">×</span></button>`).join('')}
    <button type="button" class="column-filter-summary-clear" data-clear-all-column-filters="${attrEsc(scope)}">清除全部</button>`;
}

function clearColumnFilterHeader(header, {focus=false, close=false} = {}) {
  if (!header) return;
  const controls = columnFilterControls(header);
  const primary = document.getElementById(header.dataset.columnFilter);
  controls.forEach(control => { control.value = columnFilterEmptyValue(header, control); });
  if (primary) {
    refreshColumnFilterState(primary);
    const eventName = primary.matches('input[type="search"]') ? 'input' : 'change';
    primary.dispatchEvent(new Event(eventName, {bubbles:true}));
  }
  if (close) {
    closeColumnFilterPopovers();
    closeColumnFilterSearches();
  }
  if (focus) primary?.focus({preventScroll:true});
}

function initColumnFilters() {
  document.querySelectorAll('[data-column-filter]').forEach(header => {
    if (header.dataset.columnFilterReady === '1') return;
    const id = header.dataset.columnFilter;
    const type = header.dataset.filterType || 'search';
    const label = header.textContent.trim();
    const filterLabel = header.dataset.filterLabel || `按${label}筛选`;
    const emptyValue = header.dataset.filterEmptyValue || '';
    const inputmode = header.dataset.filterInputmode ? ` inputmode="${attrEsc(header.dataset.filterInputmode)}"` : '';
    const placeholder = header.dataset.filterPlaceholder ? ` placeholder="${attrEsc(header.dataset.filterPlaceholder)}"` : '';
    const trigger = `<button type="button" class="column-filter-trigger" data-column-filter-trigger aria-expanded="false" aria-label="${attrEsc(filterLabel)}"><span class="column-filter-trigger-label">${esc(label)}</span>${columnFilterIcon(type)}</button>`;
    header.dataset.columnFilterReady = '1';
    header.dataset.filterTitle = label;
    if (type === 'search') {
      header.innerHTML = `${trigger}
        <div class="column-filter-search" data-column-filter-search>
          <svg class="column-filter-search-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="3.75"></circle><path d="m10 10 3 3"></path></svg>
          <input id="${attrEsc(id)}" type="search"${inputmode}${placeholder} aria-label="${attrEsc(filterLabel)}" autocomplete="off">
          <button type="button" class="column-filter-clear-inline" data-clear-column-filter aria-label="清空${attrEsc(label)}筛选" title="清空">×</button>
        </div>`;
      return;
    }
    if (type === 'select') {
      header.innerHTML = `${trigger}
        <select id="${attrEsc(id)}" class="column-filter-native" hidden tabindex="-1" aria-hidden="true"><option value="${attrEsc(emptyValue)}">全部</option></select>
        <div class="column-filter-popover column-filter-popover--select" role="menu" aria-label="${attrEsc(filterLabel)}">
          <div class="column-filter-options" data-column-filter-options></div>
        </div>`;
      header.querySelector('[data-column-filter-trigger]')?.setAttribute('aria-haspopup', 'menu');
      renderColumnFilterOptions(document.getElementById(id));
      return;
    }
    const endId = header.dataset.filterEndId || '';
    const isRange = type === 'date-range' && endId;
    header.innerHTML = `${trigger}
      <div class="column-filter-popover column-filter-popover--date${isRange ? ' column-filter-popover--range' : ''}" role="dialog" aria-label="${attrEsc(filterLabel)}">
        <label class="column-filter-date-field"><span>${isRange ? '从' : '选择日期'}</span><input id="${attrEsc(id)}" type="date" aria-label="${attrEsc(filterLabel)}${isRange ? '开始' : ''}"></label>
        ${isRange ? `<label class="column-filter-date-field"><span>至</span><input id="${attrEsc(endId)}" type="date" aria-label="${attrEsc(filterLabel)}结束"></label>` : ''}
        <button type="button" class="column-filter-date-clear" data-clear-column-filter>清除日期</button>
      </div>`;
    header.querySelector('[data-column-filter-trigger]')?.setAttribute('aria-haspopup', 'dialog');
  });

  document.addEventListener('click', event => {
    const chip = event.target.closest('[data-clear-filter-id]');
    if (chip) {
      const control = document.getElementById(chip.dataset.clearFilterId || '');
      clearColumnFilterHeader(control?.closest?.('[data-column-filter]'));
      return;
    }
    const clearAll = event.target.closest('[data-clear-all-column-filters]');
    if (clearAll) {
      document.getElementById(COLUMN_FILTER_RESET_IDS[clearAll.dataset.clearAllColumnFilters])?.click();
      return;
    }
    const trigger = event.target.closest('[data-column-filter-trigger]');
    if (trigger) {
      event.preventDefault();
      event.stopPropagation();
      document.querySelectorAll('.toolbar-overflow[open]').forEach(item => item.removeAttribute('open'));
      closeAccountsV2MoreMenus();
      const header = trigger.closest('.column-filter-header');
      const type = header.dataset.filterType || 'search';
      if (type === 'search') {
        closeColumnFilterPopovers();
        closeColumnFilterSearches(header);
        header.classList.add('is-searching');
        requestAnimationFrame(() => {
          const input = document.getElementById(header.dataset.columnFilter);
          input?.focus({preventScroll:true});
          input?.select();
        });
        return;
      }
      const willOpen = !header.classList.contains('is-filter-open');
      closeColumnFilterSearches();
      closeColumnFilterPopovers(willOpen ? header : null);
      header.classList.toggle('is-filter-open', willOpen);
      trigger.setAttribute('aria-expanded', String(willOpen));
      if (willOpen) {
        requestAnimationFrame(() => {
          positionColumnFilterPopover(header);
          if (type === 'select') {
            renderColumnFilterOptions(document.getElementById(header.dataset.columnFilter));
            header.querySelector('.column-filter-option[aria-checked="true"], .column-filter-option')?.focus({preventScroll:true});
          } else {
            header.querySelector('.column-filter-date-field input')?.focus({preventScroll:true});
          }
        });
      }
      return;
    }
    const option = event.target.closest('[data-column-filter-option]');
    if (option) {
      event.preventDefault();
      event.stopPropagation();
      const header = option.closest('.column-filter-header');
      const select = document.getElementById(header?.dataset.columnFilter || '');
      if (!select) return;
      select.value = option.dataset.columnFilterOption ?? '';
      refreshColumnFilterState(select);
      select.dispatchEvent(new Event('change', {bubbles:true}));
      closeColumnFilterPopovers();
      header.querySelector('[data-column-filter-trigger]')?.focus({preventScroll:true});
      return;
    }
    const clear = event.target.closest('[data-clear-column-filter]');
    if (clear) {
      event.preventDefault();
      event.stopPropagation();
      const header = clear.closest('.column-filter-header');
      const type = header?.dataset.filterType || 'search';
      clearColumnFilterHeader(header, {focus:type === 'search', close:type !== 'search'});
      return;
    }
    if (!event.target.closest('.column-filter-popover')) closeColumnFilterPopovers();
    if (!event.target.closest('.column-filter-header.is-searching')) closeColumnFilterSearches();
    if (!event.target.closest('.toolbar-overflow')) document.querySelectorAll('.toolbar-overflow[open]').forEach(item => item.removeAttribute('open'));
    else if (event.target.closest('.toolbar-overflow-menu button')) event.target.closest('.toolbar-overflow')?.removeAttribute('open');
  });
  document.addEventListener('keydown', event => {
    const search = event.target.closest?.('.column-filter-search input');
    if (search && (event.key === 'Enter' || event.key === 'Escape')) {
      event.preventDefault();
      closeColumnFilterSearches(null, true);
      return;
    }
    if (event.key === 'Escape' && event.target.closest?.('.column-filter-popover')) {
      const header = event.target.closest('.column-filter-header');
      closeColumnFilterPopovers();
      header?.querySelector('[data-column-filter-trigger]')?.focus({preventScroll:true});
    }
  });
  document.addEventListener('input', event => refreshColumnFilterState(event.target), true);
  document.addEventListener('change', event => {
    refreshColumnFilterState(event.target);
    const header = event.target.closest?.('.column-filter-header');
    if (header?.dataset.filterType === 'date') closeColumnFilterPopovers();
  }, true);
  window.addEventListener('resize', () => closeColumnFilterPopovers());
  window.addEventListener('scroll', event => {
    if (event.target?.closest?.('.column-filter-options')) return;
    closeColumnFilterPopovers();
    closeColumnFilterSearches();
  }, true);
  refreshColumnFilterStates();
}

initColumnFilters();

// ---------- 工具 ----------
function fmt(v) { return v == null || v === '' ? '-' : String(v); }
function esc(v) { return fmt(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
// 配置表单必须用这个：空值保持空，不能把 '' 显示成 '-'，否则一点保存就会写回 config
function attrEsc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function isPlaceholderEmpty(v) {
  const s = String(v == null ? '' : v).trim();
  return !s || ['-', '—', '无', '空', 'none', 'null', 'n/a', 'na'].includes(s.toLowerCase());
}
function short(v, n=40) { const s = v || ''; return s.length > n ? s.slice(0,n)+'…' : s; }
function copyId(v) { if (!v) return ''; const id = 'c'+(++copySeq); copyStore.set(id, v); return id; }
function cbtn(label, value, cls='') { const id = copyId(value); return `<button class="${cls}" data-copy-id="${id}" ${id?'':'disabled'}>${label}</button>`; }
function pill(status) {
  const map = { available:'可用', used:'已用', failed:'失败', partial_success:'部分成功', disabled:'已停用', pending:'排队', running:'运行中', debug_paused:'调试暂停', stopping:'停止中', stopped:'已停止', success:'成功', cancelled:'已取消' };
  return `<span class="pill status-${esc(status)}">${esc(map[status]||status||'-')}</span>`;
}
function pillV2(status) {
  const s = String(status || '');
  const map = { available:'可用', used:'已用', failed:'失败', partial_success:'部分成功', disabled:'已停用', pending:'排队', queued:'排队中', running:'运行中', debug_paused:'调试暂停', stopping:'停止中', stopped:'已停止', success:'成功', cancelled:'已取消', interrupted:'已中断', unsupported:'不支持', deactivated:'已停用', attention_required:'需要处理', not_created:'尚未创建', in_progress:'处理中', email_verification_pending:'待邮箱验证 / 资料', account_available:'账号可用', unknown:'状态待确认' };
  let cls = 'jobs-v2-pill--muted';
  if (s === 'success' || s === 'account_available' || s === 'available') cls = 'jobs-v2-pill--success';
  else if (s === 'failed' || s === 'interrupted' || s === 'deactivated' || s === 'attention_required') cls = 'jobs-v2-pill--failed';
  else if (s === 'running' || s === 'debug_paused' || s === 'stopping' || s === 'in_progress' || s === 'email_verification_pending') cls = 'jobs-v2-pill--running';
  else if (s === 'pending' || s === 'queued' || s === 'cancelled' || s === 'stopped' || s === 'unsupported') cls = 'jobs-v2-pill--muted';
  return `<span class="jobs-v2-pill ${cls}">${esc(map[s]||s||'-')}</span>`;
}
function formatDateTime(v) {
  if (v == null || v === '') return '-';
  const d = v instanceof Date ? v : new Date(v);
  if (Number.isNaN(d.getTime())) {
    const s = String(v).replace('T', ' ').replace(/\.\d+.*$/, '').replace(/Z$/, '').replace(/[+-]\d{2}:\d{2}$/, '');
    return s || '-';
  }
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
function taskErrorBadge(info) {
  if (!info) return '';
  return `<span class="task-error-badge" data-source="${attrEsc(info.source || 'unknown')}" title="${attrEsc(info.title || '')}">${esc(info.source_label || '未分类')} · ${esc(info.kind_label || '待归类')}</span>`;
}
function renderTaskLogErrorSummary(id, task) {
  const el = document.getElementById(id);
  if (!el) return;
  const info = task?.error_info;
  const raw = task?.error_message || task?.error || '';
  if (!info && !raw) {
    el.classList.add('hidden');
    el.innerHTML = '';
    return;
  }
  el.innerHTML = `${taskErrorBadge(info)}<span>${esc(info?.summary || raw)}</span>`;
  el.classList.remove('hidden');
}
function jobsV2OpIcons() {
  return {
    view: `<svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    retry: `<svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>`,
    stop: `<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`,
    check: `<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`,
    del: `<svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`,
  };
}
function renderTableStateRow(colspan, title, description, kind = 'empty') {
  const visual = kind === 'loading'
    ? '<span class="table-state-spinner" aria-hidden="true"></span>'
    : `<span class="table-state-icon" aria-hidden="true"><svg viewBox="0 0 24 24">${kind === 'error'
        ? '<circle cx="12" cy="12" r="9"/><path d="M12 7v6"/><path d="M12 17h.01"/>'
        : '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 10h8"/><path d="M8 14h5"/>'}</svg></span>`;
  return `<tr class="list-state-row"><td class="table-state-cell" colspan="${Number(colspan) || 1}"><div class="table-state is-${attrEsc(kind)}" role="status">${visual}<strong>${esc(title)}</strong>${description ? `<small>${esc(description)}</small>` : ''}</div></td></tr>`;
}
function setListBusy(panelId, busy) {
  const panel = document.getElementById(panelId);
  if (panel) panel.setAttribute('aria-busy', busy ? 'true' : 'false');
}
function showToast(t) {
  const el = $('#toast');
  el.textContent = t;
  el.classList.add('show');
  clearTimeout(showToast.t);
  showToast.t = setTimeout(() => el.classList.remove('show'), 2200);
}
async function copyText(text) {
  if (!text) return;
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else { const a=document.createElement('textarea'); a.value=text; a.style.position='fixed'; a.style.opacity='0'; document.body.appendChild(a); a.select(); document.execCommand('copy'); a.remove(); }
    showToast('已复制');
  } catch(e) { showToast('复制失败'); }
}
async function api(url, opts) {
  const r = await fetch(url, opts);
  const j = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(j.error || ('HTTP '+r.status));
  return j;
}
let CAPABILITIES = {features:{}, email_sources:{}};
const FEATURE_SELECTORS = {
  register: '#btnStartV2,#btnStart',
  live_check: '#btnCheckSelectedLiveTopV2,#btnCheckSelectedLiveV2,#btnRefreshSelectedTokenV2,#btnRefreshSelectedTokenTopV2,#btnCheckSelectedLiveTop,#btnRefreshSelectedTokenTop,#btnCheckSelectedLive,#btnRefreshSelectedToken,[data-account-live-check],[data-account-token-refresh]',
  plan_check: '#btnCheckSelectedPlansV2,#btnCheckSelectedPlans,[data-plan-check]',
  extract_link: '#btnExtractSelectedLinksV2,#btnExtractSelectedLinks,[data-extract-link]',
  sub2_upload: '#btnUploadSelectedCodexSub2V2,#btnUploadSelectedCodexSub2,#btnCodexUploadSub2V2,[data-codex-upload-sub2]',
  codex_retry: '#btnRetrySelectedCodexV2,#btnRetrySelectedCodex,#btnCodexReauthorizeBulkV2,[data-codex-retry],[data-codex-reauthorize]',
  cpa_download: '#btnDownloadSelectedCpaV2,#btnDownloadSelectedCpa,#btnCodexDownloadBulkCpaV2,#btnCodexDownloadBulkCpa,[data-codex-download-cpa]',
  deactivation_mail: '#btnCheckSelectedDeactivationMailV2,#btnCheckSelectedDeactivationMail,[data-account-deactivation-mail]',
  proxy_provider_test: '#btnTestProxy1024V2,#btnTestProxy1024',
  roxy_workspaces: '#btnLoadRoxyWorkspacesV2,#btnLoadRoxyWorkspaces',
  cloudmail_token: '#btnGenCloudMailTokenV2,#btnGenCloudMailToken',
  cloudmail_domains: '#btnLoadCloudMailDomainsV2,#btnLoadCloudMailDomains',
  icloud_hme: '#btnTestICloudHMEV2,#btnTestICloudHME',
  email_butler_test: '#btnTestEmailButlerV2,#btnTestEmailButler',
};
function applyFeatureGates(root=document) {
  for (const [feature, selector] of Object.entries(FEATURE_SELECTORS)) {
    const item = (CAPABILITIES.features || {})[feature];
    if (!item) continue;
    root.querySelectorAll(selector).forEach(btn => {
      if (!btn.dataset.featureBaseTitle) btn.dataset.featureBaseTitle = btn.title || '';
      btn.dataset.feature = feature;
      btn.classList.toggle('feature-unavailable', !item.enabled);
      btn.setAttribute('aria-disabled', item.enabled ? 'false' : 'true');
      btn.title = item.enabled ? btn.dataset.featureBaseTitle : `不可用：${item.reason || '缺少必要配置'}`;
    });
  }
}
async function loadCapabilities() {
  try {
    CAPABILITIES = await api('/api/capabilities');
    applyFeatureGates();
  } catch (_) {}
}
document.addEventListener('click', (event) => {
  const blocked = event.target.closest('button.feature-unavailable');
  if (!blocked) return;
  event.preventDefault(); event.stopImmediatePropagation();
  const item = (CAPABILITIES.features || {})[blocked.dataset.feature] || {};
  showToast(item.reason || '功能缺少必要配置');
}, true);
new MutationObserver(() => applyFeatureGates()).observe(document.body, {childList:true, subtree:true});
function debounce(fn, wait=250) {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

// ---------- Tab 切换与浏览器历史 ----------
const TAB_META = {
  overview: { title: '平台总览', description: '账号、邮箱、任务和网络资源运行状态' },
  register: { title: '注册中心', description: '发起批次并追踪自动化注册流程' },
  tasks: { title: '任务中心', description: '统一查看注册、恢复、Codex 补跑和账号操作的任务链路' },
  accounts: { title: '账号资产', description: '查询、筛选和批量维护已注册账号' },
  codex: { title: 'Codex 授权', description: '管理 OAuth 凭证、归档与导出状态' },
  outlook: { title: '邮箱资源池', description: '统一维护注册邮箱素材及可用状态' },
  config: { title: '运行配置', description: '调整安全的运行参数与服务集成' },
};
const NAV_ALLOWED_TABS = ['overview','register','tasks','accounts','codex','outlook','config'];
const NAV_HISTORY_KEY = 'gptConsoleNav';
let ACTIVE_TAB = 'overview';
let navigationHistoryBound = false;

function navigationModuleForTab(tab) {
  return ['register', 'accounts', 'outlook'].includes(tab) ? tab : null;
}
function normalizeNavigationState(raw) {
  const tab = NAV_ALLOWED_TABS.includes(raw?.tab) ? raw.tab : 'overview';
  const module = navigationModuleForTab(tab);
  const view = raw?.view;
  if (module && view && MODULE_VIEW_META[module]?.[view]) return {tab, module, view};
  return {tab};
}
function currentNavigationState() {
  const tab = NAV_ALLOWED_TABS.includes(ACTIVE_TAB) ? ACTIVE_TAB : 'overview';
  const module = navigationModuleForTab(tab);
  const view = module ? document.getElementById(`tab-${module}`)?.dataset.moduleView : null;
  return normalizeNavigationState({tab, view});
}
function navigationHash(state) {
  const nav = normalizeNavigationState(state);
  return `#${nav.tab}${nav.module && nav.view ? `/${encodeURIComponent(nav.view)}` : ''}`;
}
function parseNavigationHash(hash) {
  const parts = String(hash || '').replace(/^#/, '').split('/').filter(Boolean);
  if (!parts.length || !NAV_ALLOWED_TABS.includes(parts[0]) || parts.length > 2) return null;
  let view = '';
  if (parts[1]) {
    try { view = decodeURIComponent(parts[1]); } catch (_) { return null; }
  }
  const nav = normalizeNavigationState({tab: parts[0], view});
  return parts[1] && !nav.view ? null : nav;
}
function historyNavigationState() {
  if (history.state?.[NAV_HISTORY_KEY]) {
    return normalizeNavigationState({tab: history.state.gptConsoleNavTab, view: history.state.gptConsoleNavView});
  }
  return parseNavigationHash(location.hash);
}
function updateNavigationBackButton() {
  const button = $('#navHistoryBack');
  if (!button) return;
  const index = Number(history.state?.gptConsoleNavIndex || 0);
  button.disabled = index <= 0;
}
function recordNavigationHistory(mode = 'push') {
  const nav = currentNavigationState();
  const hash = navigationHash(nav);
  const current = historyNavigationState();
  if (mode === 'push' && current && JSON.stringify(current) === JSON.stringify(nav) && location.hash === hash) {
    updateNavigationBackButton();
    return;
  }
  const currentIndex = history.state?.[NAV_HISTORY_KEY] ? Number(history.state.gptConsoleNavIndex || 0) : 0;
  const nextIndex = mode === 'push' ? currentIndex + 1 : currentIndex;
  const nextState = {
    ...(history.state || {}),
    [NAV_HISTORY_KEY]: true,
    gptConsoleNavTab: nav.tab,
    gptConsoleNavView: nav.view || '',
    gptConsoleNavIndex: nextIndex,
  };
  history[mode === 'push' ? 'pushState' : 'replaceState'](nextState, '', hash);
  updateNavigationBackButton();
}
function applyNavigationState(raw) {
  const nav = normalizeNavigationState(raw);
  activateTab(nav.tab, true, 'none');
  if (nav.module && nav.view) setModuleView(nav.module, nav.view, true, 'none');
  updateNavigationBackButton();
}
function initializeNavigationHistory(fallbackTab = 'overview') {
  const fromLocation = parseNavigationHash(location.hash);
  if (fromLocation) applyNavigationState(fromLocation);
  else if (!NAV_ALLOWED_TABS.includes(ACTIVE_TAB)) activateTab(fallbackTab, true, 'none');
  recordNavigationHistory('replace');
  if (navigationHistoryBound) return;
  navigationHistoryBound = true;
  $('#navHistoryBack')?.addEventListener('click', () => {
    if (!$('#navHistoryBack').disabled) history.back();
  });
  window.addEventListener('popstate', () => {
    applyNavigationState(historyNavigationState() || {tab: 'overview'});
  });
}
function closeMobileSidebar() {
  document.body.classList.remove('sidebar-open');
  const toggle = $('#mobileNavToggle');
  if (toggle) toggle.setAttribute('aria-expanded', 'false');
}
function toggleMobileSidebar() {
  const open = document.body.classList.toggle('sidebar-open');
  const toggle = $('#mobileNavToggle');
  if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
}
function containVerticalScroll(el) {
  if (!el || el.dataset.scrollContained === '1') return;
  el.dataset.scrollContained = '1';
  el.addEventListener('wheel', event => {
    const overflowY = getComputedStyle(el).overflowY;
    if (overflowY !== 'auto' && overflowY !== 'scroll') return;
    const canScroll = el.scrollHeight > el.clientHeight + 1;
    const atTop = el.scrollTop <= 0;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
    if (!canScroll || (event.deltaY < 0 && atTop) || (event.deltaY > 0 && atBottom)) {
      event.preventDefault();
    }
  }, { passive: false });
}
containVerticalScroll(document.querySelector('.sidebar-nav'));
containVerticalScroll(document.querySelector('#configNavV2'));
$('#mobileNavToggle')?.addEventListener('click', toggleMobileSidebar);
$('#sidebarScrim')?.addEventListener('click', closeMobileSidebar);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMobileSidebar(); });
function updateTopbarClock() {
  const el = $('#topbarClock');
  if (!el) return;
  el.textContent = new Intl.DateTimeFormat('zh-CN', {
    month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false
  }).format(new Date()).replace('/', ' / ');
}
updateTopbarClock();
setInterval(updateTopbarClock, 30000);

function activateTab(tab, persist=true, historyMode=persist ? 'push' : 'none') {
  if (!NAV_ALLOWED_TABS.includes(tab)) tab = 'overview';
  ACTIVE_TAB = tab;
  $$('.sidebar-nav button[data-tab]').forEach(x => {
    const active = x.dataset.tab === tab;
    x.classList.toggle('active', active);
    if (active) x.setAttribute('aria-current', 'page');
    else x.removeAttribute('aria-current');
  });
  $$('.sidebar-module[data-sidebar-module]').forEach(item => {
    item.classList.toggle('is-open', item.dataset.sidebarModule === tab);
  });
  const contentTabs = ['overview','register','accounts','codex','outlook','config'];
  const accountTab = $('#tab-accounts');
  if (tab === 'tasks' && accountTab) accountTab.dataset.moduleView = 'tasks';
  if (tab === 'accounts' && accountTab?.dataset.moduleView === 'tasks') {
    accountTab.dataset.moduleView = SHOW_ARCHIVED_ACCOUNTS ? 'archived' : 'active';
  }
  const contentTab = tab === 'tasks' ? 'accounts' : tab;
  contentTabs.forEach(t => $('#tab-'+t).classList.toggle('hidden', t !== contentTab));
  const meta = TAB_META[tab];
  const currentView = document.getElementById(`tab-${contentTab}`)?.dataset.moduleView;
  const description = MODULE_VIEW_META[tab]?.[currentView] || meta.description;
  if ($('#topbarTitle')) $('#topbarTitle').textContent = meta.title;
  if ($('#topbarDescription')) $('#topbarDescription').textContent = description;
  document.title = `${meta.title} · Turb Console`;
  closeMobileSidebar();
  if (persist) localStorage.setItem('gpt_console_active_tab', tab);
  if (tab === 'overview') loadDashboard();
  if (tab === 'tasks') loadAccountTasks();
  if (tab === 'accounts') {
    const view = $('#tab-accounts')?.dataset.moduleView || 'active';
    if (view === 'tasks') loadAccountTasks(); else loadAccounts();
  }
  if (tab === 'codex') loadCodex();
  if (tab === 'outlook') {
    const view = $('#tab-outlook')?.dataset.moduleView || 'overview';
    if (view === 'overview') loadMailResources(); else loadOutlook();
  }
  if (tab === 'config') loadConfig();
  if (tab === 'register') refreshJobs();
  if (historyMode === 'push') recordNavigationHistory();
  else updateNavigationBackButton();
}
$$('.sidebar-nav button[data-tab]').forEach(b => b.addEventListener('click', () => activateTab(b.dataset.tab)));

const MODULE_VIEW_META = {
  register: {
    launch: '配置邮箱来源、批次数量与并发线程',
  },
  accounts: {
    active: '查询、筛选和批量维护活跃账号',
    archived: '集中查看和恢复已归档账号',
  },
  outlook: {
    overview: '查看邮箱供给、使用情况与 Email Butler 租约',
    list: '查询、导入和批量维护邮箱素材',
  },
};
function setModuleView(module, view, persist=true, historyMode='push') {
  const tab = document.getElementById(`tab-${module}`);
  if (!tab || !MODULE_VIEW_META[module]?.[view]) return;
  tab.dataset.moduleView = view;
  if (persist) localStorage.setItem(`gpt_console_module_view_${module}`, view);
  document.querySelectorAll(`[data-module-subnav="${module}"] [data-view]`).forEach(btn => {
    btn.classList.toggle('is-active', btn.dataset.view === view);
  });
  if ($('#topbarDescription')) $('#topbarDescription').textContent = MODULE_VIEW_META[module][view];
  if (module === 'accounts' && view === 'tasks') loadAccountTasks();
  else if (module === 'accounts' && SHOW_ARCHIVED_ACCOUNTS !== (view === 'archived')) applyAccountsArchivedFilter(view === 'archived');
  if (module === 'register' && view === 'tasks') refreshJobs();
  if (module === 'codex') loadCodex();
  if (module === 'outlook') view === 'overview' ? loadMailResources() : loadOutlook();
  closeMobileSidebar();
  if (historyMode === 'push') recordNavigationHistory();
  else updateNavigationBackButton();
}
$$('[data-module-subnav]').forEach(nav => nav.addEventListener('click', event => {
  const btn = event.target.closest('[data-view]');
  if (!btn) return;
  const module = nav.dataset.moduleSubnav;
  if (document.getElementById(`tab-${module}`)?.classList.contains('hidden')) activateTab(module, true, 'none');
  setModuleView(module, btn.dataset.view);
}));
function restoreModuleViewState() {
  Object.entries(MODULE_VIEW_META).forEach(([module, views]) => {
    const saved = localStorage.getItem(`gpt_console_module_view_${module}`);
    if (!saved || !views[saved]) return;
    const tab = document.getElementById(`tab-${module}`);
    if (!tab) return;
    tab.dataset.moduleView = saved;
    document.querySelectorAll(`[data-module-subnav="${module}"] [data-view]`).forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.view === saved);
    });
    if (module === 'accounts') SHOW_ARCHIVED_ACCOUNTS = saved === 'archived';
  });
}
