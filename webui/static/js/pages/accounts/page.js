// 账号列表、筛选、详情和原账号操作：依赖 common.js 的页面状态与工具函数。
let accountsLoading = false;
let accountsReloadQueued = false;
let accountsRenderedQuery = '';
let planStatusLoading = false;
let planStatusRevision = '';
let accountSessionDownloadLoading = false;
let ACCOUNT_BATCH_WORKERS = 3;
const ACCOUNT_SELECTED_EMAILS = new Map();
function accountIsDeactivated(account) {
  return ['account_status', 'codex_status', 'codex_credential_state'].some(
    key => String(account?.[key] || '').toLowerCase() === 'deactivated',
  );
}
let accountAdvancedSearchQuery = '';
let accountSearchTerms = [];
let accountSearchErrorQuery = null;
function renderAccountSearchTerms(terms) {
  accountSearchTerms = terms;
  const summary = $('#accountSearchSummaryV2');
  if (!summary) return;
  summary.hidden = !terms.length;
  summary.innerHTML = terms.length ? `
    <span class="column-filter-summary-label">高级搜索 · 同时满足</span>
    ${terms.map((term, index) => `<button type="button" class="column-filter-chip" data-account-search-term="${index}" aria-label="移除${attrEsc(term.label)}：${attrEsc(term.display_value)}"><span>${esc(term.label)}：${esc(term.display_value)}</span><span class="column-filter-chip-close" aria-hidden="true">×</span></button>`).join('')}` : '';
}
function showAccountSearchError(message = '') {
  const error = $('#accountAdvancedSearchErrorV2');
  if (error) {
    error.textContent = message;
    error.hidden = !message;
  }
  $('#accountAdvancedSearchV2')?.setAttribute('aria-invalid', message ? 'true' : 'false');
}
function getAccountsQuery() {
  const el = document.getElementById('qAccountsV2');
  return (el ? el.value : '').trim();
}
function getAccountOperationWorkers() {
  const configured = CONFIG.find(item => item.key === 'ACCOUNT_BATCH_WORKERS');
  return Math.max(1, Number(configured?.value ?? ACCOUNT_BATCH_WORKERS) || 3);
}
function configuredLiveCheckDriver() {
  const configured = CONFIG.find(item => item.key === 'ACCOUNT_LIVE_CHECK_DRIVER');
  const value = String(configured?.value ?? '').trim().toLowerCase();
  return value || null;
}
function accountAtRefreshUiSettings(fields = CONFIG) {
  const items = Array.isArray(fields) ? fields : [];
  const driverField = items.find(item => item.key === 'ACCOUNT_AT_REFRESH_DRIVER');
  const driver = String(driverField?.value || 'protocol').trim().toLowerCase() === 'browser_roxy' ? 'browser_roxy' : 'protocol';
  const debugValue = items.find(item => item.key === 'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED')?.value;
  const debugEnabled = debugValue === true || String(debugValue).trim().toLowerCase() === 'true';
  const version = String(items.find(item => item.key === 'OPENAI_PROTOCOL_VERSION')?.value || 'v1').trim().toLowerCase() === 'v2' ? 'v2' : 'v1';
  const label = driverField ? (driver === 'browser_roxy' ? 'Roxy 指纹浏览器' : `协议刷新（${version}）`) : '已保存的刷新驱动';
  const description = `使用${label}重新登录，按实际挑战完成密码、2FA 或邮箱验证，并保存最新 accessToken。`;
  const debugDescription = debugEnabled ? 'Roxy 刷新调试已开启：实际使用 Roxy 时将显示浏览器并全程抓包；失败保留窗口，可从任务日志查看现场并下载 HAR。' : '';
  return {driver, debugEnabled, label, description, debugDescription, title: description + (debugEnabled ? ' Roxy 调试已开启，失败保留窗口。' : '')};
}
async function loadAccountAtRefreshUiSettings() {
  try {
    const fields = await apiCached('/api/config', {}, 30000);
    return accountAtRefreshUiSettings(fields);
  } catch (error) {
    return accountAtRefreshUiSettings();
  }
}
async function loadRuntimeUiSettings() {
  try {
    const settings = await apiCached('/api/ui-settings', {}, 30000);
    ACCOUNT_BATCH_WORKERS = Math.max(1, Number(settings.account_batch_workers) || 3);
  } catch(e) {}
}
function accountListQueryParams() {
  const archived = SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0';
  const plan = columnFilterValue(document.getElementById('accountPlanFilterV2')) || (SHOW_PLUS_ACCOUNTS_ONLY ? 'plus' : '');
  const email = getAccountsQuery();
  const q = accountAdvancedSearchQuery;
  const dateFrom = document.getElementById('dateFromAccountsV2')?.value || '';
  const dateTo = document.getElementById('dateToAccountsV2')?.value || '';
  const p = PAGERS.accounts;
  const params = new URLSearchParams({paged:'1', page:String(p.page), page_size:String(p.size), archived, plan, email, q, date_from:dateFrom, date_to:dateTo});
  const accountFilters = {
    id: 'accountIdFilterV2', source: 'accountSourceFilterV2', registration_driver: 'accountRegistrationDriverFilterV2', token: 'accountTokenFilterV2',
    password: 'accountPasswordFilterV2', promotion: 'accountTrialFilterV2', totp: 'accountTotpFilterV2', risk: 'accountRiskFilterV2', codex: 'accountCodexFilterV2', account_status: 'accountStatusFilterV2',
    email_status: 'accountEmailStatusFilterV2',
  };
  Object.entries(accountFilters).forEach(([key, id]) => params.set(key, columnFilterValue(document.getElementById(id))));
  return params;
}
function showAccountsLoadingState(query) {
  if (query === accountsRenderedQuery) return;
  const body = $('#accountsBodyV2');
  if (body) body.innerHTML = renderTableStateRow(16, '正在加载筛选结果…', '', 'loading');
}
async function loadAccounts() {
  const params = accountListQueryParams();
  const query = params.toString();
  showAccountsLoadingState(query);
  if (accountsLoading) {
    accountsReloadQueued = true;
    return;
  }
  accountsLoading = true;
  accountsReloadQueued = false;
  setListBusy('accountsPanelV2', true);
  try {
    const p = PAGERS.accounts;
    const res = await api(`/api/accounts?${params.toString()}`);
    if (params.toString() !== accountListQueryParams().toString()) {
      accountsReloadQueued = true;
      return;
    }
    accountSearchErrorQuery = null;
    showAccountSearchError();
    renderAccountSearchTerms(res.search_terms || []);
    const facets = res.facets || {};
    const syncAccountFacet = (id, items, options = {}) => syncFacetSelect(id, items, {...options, preserveSelected: true});
    syncAccountFacet('accountSourceFilterV2', facets.source, {group:'source'});
    syncAccountFacet('accountRegistrationDriverFilterV2', facets.registration_driver, {
      group:'registration_driver', values:['roxy','roxy_oss','protocol','protocol_oss','protocol_oss_2','cloakbrowser','unknown'],
    });
    syncAccountFacet('accountTokenFilterV2', facets.token, {
      group:'account_token',
      values:['has','expired','invalid_401','invalid_403','invalid_other','none'],
    });
    syncAccountFacet('accountPasswordFilterV2', facets.password, {group:'password'});
    syncAccountFacet('accountPlanFilterV2', facets.plan, {group:'plan'});
    syncAccountFacet('accountTrialFilterV2', facets.promotion, {group:'promotion'});
    syncAccountFacet('accountTotpFilterV2', facets.totp, {group:'totp'});
    syncAccountFacet('accountRiskFilterV2', facets.risk, {group:'risk'});
    syncAccountFacet('accountCodexFilterV2', facets.codex, {group:'codex'});
    syncAccountFacet('accountStatusFilterV2', facets.account_status, {group:'account_status', values:['active','deactivated']});
    if (params.toString() !== accountListQueryParams().toString()) {
      accountsReloadQueued = true;
      return;
    }
    ACCOUNTS = res.items || [];
    ACCOUNTS_TOTAL = Number(res.total || ACCOUNTS.length || 0);
    const totalPages = Math.max(1, Math.ceil(ACCOUNTS_TOTAL / p.size));
    if (p.page > totalPages) {
      p.page = totalPages;
      accountsReloadQueued = true;
      return;
    }
    accountsRenderedQuery = params.toString();
    renderAccounts();
    markViewReady(`accounts:${SHOW_ARCHIVED_ACCOUNTS ? 'archived' : 'active'}`);
  } catch(e) {
    if (params.toString() !== accountListQueryParams().toString()) {
      accountsReloadQueued = true;
      return;
    }
    if (e.code === 'account_search_invalid') {
      accountSearchErrorQuery = accountAdvancedSearchQuery;
      showAccountSearchError(e.message);
      renderAccountSearchTerms([]);
      ACCOUNTS = [];
      ACCOUNTS_TOTAL = 0;
      renderAccounts();
      return;
    }
    if (!ACCOUNTS.length) $('#accountsBodyV2').innerHTML = renderTableStateRow(16, '账号加载失败', '请检查服务状态后刷新列表。', 'error');
    else if (query !== accountsRenderedQuery) $('#accountsBodyV2').innerHTML = renderTableStateRow(16, '筛选结果加载失败', '请检查服务状态后刷新列表。', 'error');
    showToast('加载账号失败: ' + e.message);
  }
  finally {
    accountsLoading = false;
    setListBusy('accountsPanelV2', false);
    if (accountsReloadQueued) {
      accountsReloadQueued = false;
      void loadAccounts();
    }
  }
}
function applyAccountStatusSnapshot(account, item, statusFields = []) {
  const revision = account.plan_details_revision;
  // 缺失字段也是权威清空，避免 Object.assign 遗留上轮状态。
  statusFields.forEach(key => { delete account[key]; });
  Object.assign(account, item);
  if (item.plan_summary && revision !== item.plan_details_revision) {
    const promotions = rows => Array.isArray(rows) ? rows.map(item => ({...item, plan: 'plus'})) : null;
    account.account_promotions = promotions(item.plan_summary.promotions);
    account.plan_check_country_results = item.plan_summary.countries.map(country => {
      const {promotions: items, ...state} = country;
      return {...state, ...(Array.isArray(items) ? {result: {account_promotions: promotions(items)}} : {})};
    });
    delete account.promotion_query_snapshot;
    account._planDetailsPending = true;
  }
}
function loadAccountPlanDetails(account) {
  if (!account?._planDetailsPending) return Promise.resolve(account);
  if (account._planDetailsRequest) return account._planDetailsRequest;
  const revision = account.plan_details_revision;
  const request = api(`/api/accounts/${encodeURIComponent(account.id)}/plan-details`).then(result => {
    if (account.plan_details_revision === revision) {
      Object.assign(account, result.item || {});
      account._planDetailsPending = false;
      return account;
    }
    // 等待期间有新摘要时，让当前打开动作继续等待最新明细。
    if (account._planDetailsRequest === request) delete account._planDetailsRequest;
    return loadAccountPlanDetails(account);
  }).finally(() => { if (account._planDetailsRequest === request) delete account._planDetailsRequest; });
  account._planDetailsRequest = request;
  return request;
}
async function pollAccountPlanStatuses() {
  if (planStatusLoading || accountsLoading || accountSearchErrorQuery === accountAdvancedSearchQuery) return;
  planStatusLoading = true;
  try {
    const params = accountListQueryParams().toString();
    const snapshot = await api(`/api/accounts/plan-check-status?${params}&compact=1`);
    if (accountsLoading || params !== accountListQueryParams().toString()) return;
    const items = snapshot.items || [];
    const accountById = new Map(ACCOUNTS.map(r => [Number(r.id), r]));
    const hasUnknown = items.some(item => !accountById.has(Number(item.id)));
    if (hasUnknown || items.length !== ACCOUNTS.length || Number(snapshot.total || 0) !== ACCOUNTS_TOTAL) {
      planStatusRevision = snapshot.revision || '';
      await loadAccounts();
      return;
    }
    if ((snapshot.revision || '') !== planStatusRevision) {
      let needsFullReload = false;
      items.forEach(item => {
        const account = accountById.get(Number(item.id));
        const wasChecking = ['queued', 'running'].includes(account?.plan_check_status);
        const isChecking = ['queued', 'running'].includes(item.plan_check_status);
        const wasExtracting = ['queued', 'running'].includes(account?.extract_link_status);
        const isExtracting = ['queued', 'running'].includes(item.extract_link_status);
        if (wasChecking && !isChecking) needsFullReload = true;
        if (wasExtracting && !isExtracting) needsFullReload = true;
        applyAccountStatusSnapshot(account, item, snapshot.status_fields || []);
      });
      planStatusRevision = snapshot.revision || '';
      if (needsFullReload) await loadAccounts();
      else renderAccounts();
    }
  } catch(e) {}
  finally { planStatusLoading = false; }
}
function _codexCell(r) {
  const s = r.codex_status || '';
  const exec = r.codex_execution_status || '';
  const err = r.codex_error || '';
  const titleAttr = err ? ` title="${esc(err)}"` : '';
  if (['queued','running','cancelling'].includes(exec)) return `<span class="pill status-running">${exec === 'queued' ? '排队中' : exec === 'cancelling' ? '停止中' : '补跑中'}</span>`;
  if (s === 'success') return `<span class="pill status-success">成功</span>`;
  if (s === 'retrying') return `<span class="pill status-running">补跑中</span>`;
  if (s === 'stopped') return `<span class="pill status-used"${titleAttr}>已停止</span>`;
  if (s === 'failed') return `<span class="pill status-failed"${titleAttr}>失败</span>`;
  if (s === 'pending_confirmation' || r.codex_credential_state === 'pending_confirmation') return `<span class="pill status-used"${titleAttr}>待确认</span>`;
  if (s === 'skipped') return `<span class="pill status-used">已跳过</span>`;
  if (s === 'deactivated') return `<span class="pill status-failed" title="账号已被 OpenAI 删除/停用/封禁，无法授权">已废号</span>`;
  return `<span class="muted">-</span>`;
}
function _codexCellV2(r) {
  if (accountIsDeactivated(r)) return '<span class="acc-v2-codex is-fail" title="账号已确认停用/封禁">封号</span>';
  const s = r.codex_status || '';
  const exec = r.codex_execution_status || '';
  const err = r.codex_error || '';
  const titleAttr = err ? ` title="${esc(err)}"` : '';
  if (['queued','running','cancelling'].includes(exec)) return `<span class="acc-v2-codex is-run"${titleAttr}>${exec === 'queued' ? '排队中' : exec === 'cancelling' ? '停止中' : '补跑中'}</span>`;
  if (s === 'success') return `<span class="acc-v2-codex is-ok"${titleAttr}>已通过</span>`;
  if (s === 'retrying') return `<span class="acc-v2-codex is-run"${titleAttr}>补跑中</span>`;
  if (s === 'stopped') return `<span class="acc-v2-codex is-mute"${titleAttr}>已停止</span>`;
  if (s === 'failed') return `<span class="acc-v2-codex is-fail"${titleAttr}>失败</span>`;
  if (s === 'pending_confirmation' || r.codex_credential_state === 'pending_confirmation') return `<span class="acc-v2-codex is-mute"${titleAttr}>待确认</span>`;
  if (s === 'skipped') return `<span class="acc-v2-codex is-skip"${titleAttr}>已跳过</span>`;
  if (s === 'deactivated') return `<span class="acc-v2-codex is-fail" title="账号已被 OpenAI 删除/停用/封禁，无法授权">已废号</span>`;
  return `<span class="acc-v2-muted">-</span>`;
}
function _accountStatusCellV2(r) {
  const reason = String(r.account_status_reason || '').trim();
  const lines = (status, summary = '', summaryTitle = summary) => `<div class="account-cell-lines"><div class="account-cell-line">${status}</div>${summary ? `<div class="account-cell-line account-cell-line--sub" title="${esc(summaryTitle)}">${esc(short(summary, 34))}</div>` : ''}</div>`;
  if (accountIsDeactivated(r)) {
    return lines(`<span class="acc-v2-account-status is-fail"${reason ? ` title="${esc(reason)}"` : ''}>已废号</span>`, reason);
  }
  const liveStatus = String(r.live_check_status || '').toLowerCase();
  const liveHttp = _liveCheckHttpStatus(r);
  const liveReason = String(r.live_check_error || '').trim();
  if (liveStatus === 'failed') {
    const tokenIssue = liveHttp === 401 || liveHttp === 403;
    const label = tokenIssue ? `Token 异常 · HTTP ${liveHttp}` : '查活失败';
    const detail = [liveHttp ? `HTTP ${liveHttp}` : '', liveReason].filter(Boolean).join('；');
    return lines(`<span class="acc-v2-account-status is-fail"${detail ? ` title="${esc(detail)}"` : ''}>${label}</span>`, liveReason || (liveHttp ? `HTTP ${liveHttp}` : ''));
  }
  if (liveStatus === 'queued' || liveStatus === 'running') {
    return '<span class="acc-v2-account-status is-mute">查活中</span>';
  }
  if (liveStatus === 'live') {
    const checkedAt = _fmtPlanTime(r.live_checked_at);
    const title = `上次查活通过：${checkedAt || '时间未记录'}；AT 有效期见 Token 列`;
    const time = checkedAt ? checkedAt.replace(/^\d{4}-/, '') : '时间未记录';
    return lines(`<span class="acc-v2-account-status is-ok" title="${esc(title)}">查活通过</span>`, time, checkedAt || time);
  }
  return '<span class="acc-v2-account-status is-mute" title="尚未完成查活，不能确认账号正常">待查活</span>';
}
function _fmtPlanTime(v, dateOnly = false) {
  if (!v) return '';
  try {
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) {
      const raw = String(v).replace('T', ' ').replace(/(\+00:00|Z)$/, '');
      return dateOnly ? raw.slice(0, 10) : raw;
    }
    const pad = n => String(n).padStart(2, '0');
    const day = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
    return dateOnly ? day : `${day} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch(e) {
    return String(v);
  }
}
function _billingLabel(v) {
  const x = (v || '').toString().toLowerCase();
  if (x === 'monthly') return '月付';
  if (x === 'yearly' || x === 'annual' || x === 'annually') return '年付';
  return v || '';
}
function _discountLabel(r) {
  const amount = r.discount_amount;
  const type = (r.discount_type || '').toString().toLowerCase();
  if (amount === undefined || amount === null || amount === '') return '';
  const n = Number(amount);
  if (type === 'percentage' && !Number.isNaN(n)) { const v = Number.isInteger(n) ? String(n) : String(n); return `${v}%折扣`; }
  if (!Number.isNaN(n)) return `${n}折扣`;
  return `${amount}折扣`;
}

let _accountsTooltipNode = null;
let _accountsTooltipTarget = null;
let _accountsTooltipDescription = null;
let _accountsTooltipHideTimer = null;

function rememberTaskTooltipView() {
  return {
    hovered: Boolean(_accountsTooltipNode?.matches(':hover')),
    focused: Boolean(_accountsTooltipNode?.contains(document.activeElement)),
    scrollTop: _accountsTooltipNode?.scrollTop || 0,
  };
}

function restoreTaskTooltipView(target, view) {
  if (!target.matches(':hover') && target !== document.activeElement && !view?.hovered && !view?.focused) return;
  _showAccountsTooltip(target);
  _accountsTooltipNode.scrollTop = view?.scrollTop || 0;
  if (view?.focused) _accountsTooltipNode.focus({preventScroll:true});
}

function _accountsTooltipSelector() {
  return '.accounts-table-v2 .col-plan [data-accounts-tooltip], .accounts-table-v2 .col-quota [data-accounts-tooltip], .accounts-table-v2 .col-trial [data-accounts-tooltip], #accountTaskStageProgress [data-accounts-tooltip], #batchProgressListV2 [data-accounts-tooltip], #accountTasksBody [data-account-task-result-tooltip]';
}

function _hideAccountsTooltip() {
  clearTimeout(_accountsTooltipHideTimer);
  if (_accountsTooltipNode) { _accountsTooltipNode.classList.remove('show'); _accountsTooltipNode.hidden = true; }
  if (_accountsTooltipTarget) {
    if (_accountsTooltipDescription == null) _accountsTooltipTarget.removeAttribute('aria-describedby');
    else _accountsTooltipTarget.setAttribute('aria-describedby', _accountsTooltipDescription);
  }
  _accountsTooltipTarget = null;
  _accountsTooltipDescription = null;
}

function _scheduleAccountsTooltipHide() {
  clearTimeout(_accountsTooltipHideTimer);
  _accountsTooltipHideTimer = setTimeout(() => {
    if (_accountsTooltipNode?.matches(':hover') || _accountsTooltipNode?.contains(document.activeElement)) return;
    _hideAccountsTooltip();
  }, 150);
}

function _showAccountsTooltip(target) {
  const accountId = target?.closest?.('tr')?.querySelector?.('[data-account-id]')?.dataset?.accountId;
  const account = ACCOUNTS.find(item => Number(item.id) === Number(accountId));
  if (target?.closest?.('.col-trial') && account?._planDetailsPending && !target._planDetailsLoading) {
    target._planDetailsLoading = true;
    const index = [...target.closest('.col-trial').querySelectorAll('[data-accounts-tooltip]')].indexOf(target);
    void loadAccountPlanDetails(account).then(() => {
      if (!target.isConnected || account._planDetailsPending) return;
      const holder = document.createElement('div');
      holder.innerHTML = _promotionCell(account);
      const fresh = holder.querySelectorAll('[data-accounts-tooltip]')[index];
      if (fresh) target.dataset.accountsTooltip = fresh.dataset.accountsTooltip;
      if (_accountsTooltipTarget === target) _showAccountsTooltip(target);
    }).catch(() => {}).finally(() => { target._planDetailsLoading = false; });
  }
  const message = target?.dataset?.accountsTooltip || '';
  if (!message || !target.isConnected || !target.getClientRects().length) return;
  _hideAccountsTooltip();
  if (!_accountsTooltipNode) {
    _accountsTooltipNode = document.createElement('div');
    _accountsTooltipNode.className = 'accounts-hover-tooltip';
    _accountsTooltipNode.id = 'accountsHoverTooltip';
    _accountsTooltipNode.setAttribute('role', 'tooltip');
    _accountsTooltipNode.addEventListener('mouseenter', () => clearTimeout(_accountsTooltipHideTimer));
    _accountsTooltipNode.addEventListener('mouseleave', _scheduleAccountsTooltipHide);
    _accountsTooltipNode.addEventListener('focusout', _scheduleAccountsTooltipHide);
    document.body.appendChild(_accountsTooltipNode);
  }

  _accountsTooltipTarget = target;
  _accountsTooltipDescription = target.getAttribute('aria-describedby');
  target.setAttribute('aria-describedby', [_accountsTooltipDescription, _accountsTooltipNode.id].filter(Boolean).join(' '));
  _accountsTooltipNode.classList.toggle('is-task-step', Boolean(target.closest('#accountTaskStageProgress, #batchProgressListV2, [data-account-task-result-tooltip]')));
  _accountsTooltipNode.classList.toggle('is-promotion', Boolean(target.closest('.col-trial')));
  _accountsTooltipNode.tabIndex = target.closest('#accountTaskStageProgress, #batchProgressListV2, .col-trial, [data-account-task-result-tooltip]') ? 0 : -1;
  _accountsTooltipNode.textContent = message;
  _accountsTooltipNode.hidden = false;
  _accountsTooltipNode.style.left = '0px';
  _accountsTooltipNode.style.top = '0px';
  _accountsTooltipNode.classList.add('show');

  const rect = target.getBoundingClientRect();
  const tipRect = _accountsTooltipNode.getBoundingClientRect();
  const padding = 8;
  const gap = 6;
  const left = Math.max(padding, Math.min(rect.left, window.innerWidth - tipRect.width - padding));
  let top = rect.bottom + gap;
  if (top + tipRect.height > window.innerHeight - padding && rect.top - tipRect.height - gap >= padding) {
    top = rect.top - tipRect.height - gap;
  }
  _accountsTooltipNode.style.left = `${left}px`;
  _accountsTooltipNode.style.top = `${Math.max(padding, Math.min(top, window.innerHeight - tipRect.height - padding))}px`;
}

function bindAccountsHoverTooltips() {
  const targetFor = (node) => node?.closest?.(_accountsTooltipSelector()) || null;
  const showFocusedTooltip = (event) => {
    const target = targetFor(event.target);
    if (target && (!target.closest('#accountTaskStageProgress, #batchProgressListV2') || target.matches(':focus-visible'))) _showAccountsTooltip(target);
  };
  document.addEventListener('mouseover', (event) => {
    const target = targetFor(event.target);
    if (!target || (event.relatedTarget && target.contains(event.relatedTarget))) return;
    if (target.closest('#accountTaskStageProgress, #batchProgressListV2') && !window.matchMedia('(hover: hover)').matches) return;
    _showAccountsTooltip(target);
  });
  document.addEventListener('mouseout', (event) => {
    const target = targetFor(event.target);
    if (!target || (event.relatedTarget && target.contains(event.relatedTarget))) return;
    if (!_accountsTooltipTarget || _accountsTooltipTarget === target) _scheduleAccountsTooltipHide();
  });
  document.addEventListener('focusin', showFocusedTooltip);
  // 捕获 focus 与 focusin 共用入口，键盘聚焦也能打开完整优惠提示。
  document.addEventListener('focus', showFocusedTooltip, true);
  document.addEventListener('focusout', (event) => {
    const target = targetFor(event.target);
    if (!target || (event.relatedTarget && target.contains(event.relatedTarget))) return;
    if (!_accountsTooltipTarget || _accountsTooltipTarget === target) _scheduleAccountsTooltipHide();
  });
  window.addEventListener('scroll', event => {
    if (_accountsTooltipNode?.contains(event.target)) return;
    const target = _accountsTooltipTarget;
    // 聚焦可触发表格自动横向滚动，仍可见的优惠或任务结果需要重新定位提示。
    if ((target?.closest('.col-trial') || target?.closest('[data-account-task-result-tooltip]')) && document.activeElement === target) {
      const rect = target.getBoundingClientRect();
      if (rect.right > 0 && rect.left < window.innerWidth && rect.bottom > 0 && rect.top < window.innerHeight) {
        _showAccountsTooltip(target);
        return;
      }
    }
    _hideAccountsTooltip();
  }, true);
  window.addEventListener('resize', _hideAccountsTooltip);
  document.addEventListener('click', event => {
    const target = targetFor(event.target);
    if (target?.closest('.col-trial, [data-account-task-result-tooltip]')) {
      _showAccountsTooltip(target);
      return;
    }
    if (!_accountsTooltipNode?.contains(event.target)) _hideAccountsTooltip();
  }, true);
  document.addEventListener('keydown', event => {
    if (!_accountsTooltipTarget?.closest('#accountTaskStageProgress, #batchProgressListV2, .col-trial, [data-account-task-result-tooltip]')) return;
    if (event.key === 'ArrowDown' && document.activeElement === _accountsTooltipTarget) {
      event.preventDefault();
      _accountsTooltipNode?.focus({preventScroll:true});
      return;
    }
    if (event.key !== 'Escape') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (_accountsTooltipNode?.contains(document.activeElement)) _accountsTooltipTarget.focus({preventScroll:true});
    _hideAccountsTooltip();
  }, true);
}

function _planCell(r) {
  const ok = r.plan_check_ok;
  const err = r.plan_check_error || '';
  const plan = String(r.current_plan_type || '').trim() || String(r.plan_type || '').trim() || '未查询';
  const checked = r.plan_checked_at ? `查询: ${r.plan_checked_at}` : '未查询实时套餐';
  const route = (r.plan_check_network_route || '').toString();
  const routeLabel = route === 'proxy' ? `网络: 代理${r.plan_check_proxy_used ? ` (${r.plan_check_proxy_used})` : ''}` :
    route === 'direct_fallback' ? `网络: 直连回退${r.plan_check_proxy_fallback_reason ? ` (${r.plan_check_proxy_fallback_reason})` : ''}` :
    route === 'direct' ? '网络: 直连' : '';
  const registrationRoute = r.registration_proxy_region
    ? `注册出口: ${r.registration_proxy_provider || '代理'} / ${r.registration_proxy_region}` : '';
  const title = [err || checked, registrationRoute, routeLabel].filter(Boolean).join('；');
  const lower = plan.toLowerCase();

  if (lower === 'free') {
    const text = plan;
    const cls = 'status-success';
    return `<span class="pill ${cls}" data-accounts-tooltip="${esc(title)}" tabindex="0">${esc(text)}</span>`;
  }

  const cls = lower === '未查询' ? 'status-used' : 'status-success';
  const expireRaw = r.plan_expires_at || r.expires_at || r.plan_renews_at || r.renews_at || '';
  const expire = _fmtPlanTime(expireRaw, true);
  const billing = _billingLabel(r.billing_period);
  const discount = _discountLabel(r);
  const text = plan;
  const detail = [title];
  if (billing) detail.push(`计费周期: ${billing}`);
  if (r.billing_currency) detail.push(`币种: ${r.billing_currency}`);
  if (expireRaw) detail.push(`到期时间: ${expire || expireRaw}`);
  if (r.plan_renews_at) detail.push(`续费时间: ${r.plan_renews_at}`);
  if (discount) detail.push(`折扣: ${discount}`);
  if (r.discount_expires_at) detail.push(`折扣结束: ${r.discount_expires_at}`);
  if (r.discount_promo_campaign_id) detail.push(`优惠: ${r.discount_promo_campaign_id}`);
  return `<span class="pill ${cls}" data-accounts-tooltip="${esc(detail.join('；'))}" tabindex="0">${esc(text)}</span>`;
}
function _quotaWindowLabel(w) {
  const labels = {five_hour: '5H', weekly: 'WEEKLY', monthly: 'MONTH', daily: 'DAY', custom: 'CUSTOM'};
  const kind = String(w?.kind || '').toLowerCase();
  return labels[kind] || String(w?.label || 'OTHER').trim().toUpperCase();
}
function _quotaPercent(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '';
  return `${Math.round(Math.max(0, Math.min(100, n)))}%`;
}
function _quotaWindowDetail(w) {
  const parts = [_quotaWindowLabel(w)];
  const used = _quotaPercent(w.used_percent);
  const remaining = _quotaPercent(w.remaining_percent);
  if (used) parts.push(`已用 ${used}`);
  if (remaining) parts.push(`剩余 ${remaining}`);
  const resetAt = Number(w.reset_at);
  if (Number.isFinite(resetAt) && resetAt > 0) {
    const date = new Date((resetAt > 1e12 ? resetAt / 1000 : resetAt) * 1000);
    if (!Number.isNaN(date.getTime())) parts.push(`重置于 ${date.toLocaleString()}`);
  }
  return parts.join(' · ');
}
function _quotaCell(r) {
  const windows = Array.isArray(r.quota_windows) ? r.quota_windows.filter(Boolean) : [];
  const status = String(r.quota_status || '').toLowerCase();
  const checked = r.quota_checked_at || r.quota_last_success_at || '';
  const error = r.quota_error || '';
  if (!windows.length) {
    if (status === 'queued' || status === 'running' || ['queued', 'running'].includes(String(r.plan_check_status || '').toLowerCase())) {
      return '<span class="pill status-running">查询中</span>';
    }
    if (status === 'failed') {
      return `<span class="pill status-failed" data-accounts-tooltip="${esc(error || '额度查询失败')}" tabindex="0">查询失败</span>`;
    }
    if (status === 'success') {
      return `<span class="acc-v2-muted" data-accounts-tooltip="${esc(checked ? `查询于 ${checked}` : '额度接口未返回窗口')}" tabindex="0">未返回窗口</span>`;
    }
    return '<span class="acc-v2-muted" data-accounts-tooltip="尚未查询额度" tabindex="0">未查询</span>';
  }
  const details = windows.map(_quotaWindowDetail);
  if (status === 'failed') details.push(`本次查询失败: ${error || '未知错误'}；显示上次成功快照`);
  if (checked) details.push(`查询于 ${checked}`);
  const priority = {five_hour: 0, weekly: 1};
  const visible = windows.map((window, index) => ({window, index})).sort((left, right) =>
    (priority[String(left.window.kind || '').toLowerCase()] ?? 2) - (priority[String(right.window.kind || '').toLowerCase()] ?? 2) || left.index - right.index,
  ).slice(0, 2);
  const singleLineClass = visible.length === 1 ? ' quota-cell--single' : '';
  return `<div class="quota-cell${singleLineClass}" data-accounts-tooltip="${esc(details.join('；'))}" tabindex="0">${visible.map(({window}) => `<div class="quota-cell-line">${esc(_quotaWindowLabel(window))}</div>`).join('')}</div>`;
}
function _plusPromotionKind(r) {
  const explicit = String(r.plus_promo_kind || '').trim().toLowerCase();
  if (['free_trial', 'discount', 'other_promo', 'none', 'unknown'].includes(explicit)) return explicit;
  const percentageRaw = r.plus_promo_discount_percentage ?? r.plus_trial_discount_percentage;
  const percentage = percentageRaw === null || percentageRaw === undefined || percentageRaw === '' ? NaN : Number(percentageRaw);
  const campaignId = String(r.plus_promo_campaign_id || r.plus_trial_campaign_id || '').trim().toLowerCase();
  const searchable = [
    campaignId,
    r.plus_promo_title || r.plus_trial_title,
    r.plus_promo_promotion_type,
    r.plus_promo_promotion_type_label || r.plus_trial_promotion_type_label,
  ].join(' ').toLowerCase();
  if (percentage === 100) return 'free_trial';
  if (Number.isFinite(percentage) && percentage > 0 && percentage < 100) return 'discount';
  if (searchable.includes('pct-off') || searchable.includes('discount') || searchable.includes('% off')) return 'discount';
  if (searchable.includes('free trial') || campaignId.includes('-free') || campaignId.includes('trial')) return 'free_trial';
  if (searchable.trim()) return 'other_promo';
  if (r.plus_discount_eligible === true) return 'discount';
  if (r.plus_promo_eligible === true || r.plus_trial_eligible === true) return 'unknown';
  return 'none';
}
function _plusPromotionDuration(r) {
  const periods = r.plus_promo_duration_num_periods ?? r.plus_trial_duration_num_periods;
  if (periods === null || periods === undefined || periods === '') return '';
  const period = String(r.plus_promo_duration_period || r.plus_trial_duration_period || '').toLowerCase();
  const unit = period === 'month' ? '个月' : (period === 'year' ? '年' : period);
  return unit ? ` ${periods} ${unit}` : '';
}
function _plusPromotionLabel(r) {
  const kind = _plusPromotionKind(r);
  const duration = _plusPromotionDuration(r);
  if (kind === 'free_trial') return `免费${duration}`.trim();
  if (kind === 'discount') {
    const raw = r.plus_promo_discount_percentage ?? r.plus_trial_discount_percentage;
    const percentage = raw === null || raw === undefined || raw === '' ? NaN : Number(raw);
    const discount = percentage === 50 ? '五折' : (Number.isFinite(percentage) ? `减 ${percentage}%` : '折扣');
    return `${discount}${duration}`.trim();
  }
  if (kind === 'other_promo') return '其他优惠';
  if (kind === 'unknown') return '历史优惠待复查';
  return '无优惠';
}
function _plusPromotionDetail(r) {
  const details = [_plusPromotionLabel(r)];
  const title = r.plus_promo_title || r.plus_trial_title;
  const campaignId = r.plus_promo_campaign_id || r.plus_trial_campaign_id;
  if (title && title !== details[0]) details.push(String(title));
  if (campaignId) details.push(`活动 ${campaignId}`);
  return details.join('；');
}
function _isFreeTrialPromotion(r) {
  return _plusPromotionKind(r) === 'free_trial';
}
function _promotionPlanLabel(plan) {
  return plan === 'go' ? 'Go' : 'Plus';
}
function _accountPromotions(r) {
  if (Array.isArray(r.account_promotions)) {
    return ['go', 'plus'].flatMap(plan => {
      const items = r.account_promotions.filter(item => item && String(item.plan || '').toLowerCase() === plan);
      if (!items.length) return [{plan, kind: 'unknown'}];
      return items.map(item => {
        const kind = String(item.kind || '').toLowerCase();
        return {...item, plan, kind: ['free_trial', 'discount', 'other_promo', 'none', 'unknown'].includes(kind) ? kind : 'unknown'};
      });
    });
  }
  const plan = String(r.current_plan_type || r.plan_type || '').toLowerCase();
  return [
    {plan: 'go', kind: 'pending', summary: '旧查询未记录 Go 优惠，请重新查询套餐'},
    {
      plan: 'plus', kind: plan && plan !== 'free' ? 'not_applicable' : _plusPromotionKind(r),
      title: r.plus_promo_title || r.plus_trial_title,
      campaign_id: r.plus_promo_campaign_id || r.plus_trial_campaign_id,
      discount_percentage: r.plus_promo_discount_percentage ?? r.plus_trial_discount_percentage,
      duration_num_periods: r.plus_promo_duration_num_periods ?? r.plus_trial_duration_num_periods,
      duration_period: r.plus_promo_duration_period || r.plus_trial_duration_period,
    },
  ];
}
function _accountCountryResultError(entry) {
  const error = String(entry?.error || '').trim();
  if (error) return error;
  const status = Number(entry?.http_status);
  return Number.isFinite(status) && status > 0 ? `HTTP ${status}` : '';
}
function _accountCountryResultItems(entry, overallStatus = '') {
  const country = String(entry?.country || '').trim().toUpperCase();
  const status = String(entry?.status || '').trim().toLowerCase();
  const overall = String(overallStatus || '').trim().toLowerCase();
  const result = entry?.result && typeof entry.result === 'object' ? entry.result : null;
  const hasSnapshot = Boolean(result && Object.keys(result).length && entry?.last_success_at);
  const withMeta = (items, stale = false) => items.map(item => ({...item, country, stale}));
  const overallPending = ['queued', 'running'].includes(overall);
  const overallAborted = ['failed', 'cancelled'].includes(overall);
  if (status === 'success' && overallPending) {
    const items = result ? _accountPromotions(result) : ['go', 'plus'].map(plan => ({plan, kind: 'unknown'}));
    return {country, items: withMeta(items, true), stale: true,
      context: `${country}：${overall === 'queued' ? '新任务排队中' : '新任务正在执行'}；沿用上次成功快照${entry?.checked_at ? `；上次成功查询: ${entry.checked_at}` : ''}`};
  }
  if (['queued', 'running'].includes(status) && overallAborted) {
    const cancelled = overall === 'cancelled';
    if (hasSnapshot) {
      return {country, items: withMeta(_accountPromotions(result), true), stale: true,
        context: `${country}：${cancelled ? '已取消' : '查询中断'}；显示上次成功快照；上次成功查询: ${entry.last_success_at}`};
    }
    return {country, items: ['go', 'plus'].map(plan => ({plan, kind: cancelled ? 'cancelled' : 'failed', country})), stale: false,
      context: `${country}：${cancelled ? '已取消' : '查询中断'}`};
  }
  if (status === 'queued' || status === 'running') {
    return {country, items: ['go', 'plus'].map(plan => ({plan, kind: 'pending', country})), stale: false,
      context: `${country}：${status === 'queued' ? '查询排队中' : '查询中'}${entry?.checked_at ? `；记录于 ${entry.checked_at}` : ''}`};
  }
  if (status === 'success') {
    const items = result ? _accountPromotions(result) : ['go', 'plus'].map(plan => ({plan, kind: 'unknown'}));
    return {country, items: withMeta(items), stale: false, context: entry?.checked_at ? `${country}：查询于 ${entry.checked_at}` : `${country}：查询完成`};
  }
  const error = _accountCountryResultError(entry) || (status === 'cancelled' ? '查询已取消' : '未知错误');
  if (hasSnapshot) {
    return {country, items: withMeta(_accountPromotions(result), true), stale: true,
      context: `${country}：显示上次成功快照；上次成功查询: ${entry.last_success_at}；本次查询${status === 'cancelled' ? '取消' : '失败'}: ${error}`};
  }
  return {country, items: ['go', 'plus'].map(plan => ({plan, kind: status === 'cancelled' ? 'cancelled' : 'failed', country})), stale: false,
    context: `${country}：本次查询${status === 'cancelled' ? '取消' : '失败'}: ${error}`};
}
function _accountCountryPromotionDisplays(r) {
  // 空数组是后端明确关闭多国查询的信号；历史国家结果必须留在数据中，但不能覆盖最新单次查询投影。
  if (Array.isArray(r?.plan_check_countries) && r.plan_check_countries.length === 0) return [];
  const countryResults = Array.isArray(r?.plan_check_country_results)
    ? r.plan_check_country_results.filter(item => item && String(item.country || '').trim())
    : [];
  if (countryResults.length) return countryResults.map(item => ({
    ..._accountCountryResultItems(item, r?.plan_check_status),
    checkedAt: [item.checked_at, item.last_success_at].map(value => Date.parse(value || '')).find(Number.isFinite) ?? 0,
    queryContext: ['failed', 'cancelled'].includes(String(item.status || '').toLowerCase())
      ? _accountPromotionQueryTooltip(item.status, _accountCountryResultError(item)) : '',
  }));
  const items = Array.isArray(r?.account_promotions)
    ? _accountPromotions(r).filter(item => String(item.country || '').trim())
    : [];
  if (!items.length) return [];
  const grouped = new Map();
  items.forEach(item => {
    const country = String(item.country || '').trim().toUpperCase();
    if (!grouped.has(country)) grouped.set(country, []);
    grouped.get(country).push({...item, country});
  });
  return [...grouped.entries()].map(([country, countryItems]) => ({
    country,
    items: ['go', 'plus'].flatMap(plan => {
      const matches = countryItems.filter(item => item.plan === plan);
      return matches.length ? matches : [{plan, kind: 'unknown', country}];
    }),
    stale: countryItems.some(item => item.stale === true),
    context: `${country}：${countryItems.some(item => item.stale === true) ? '显示上次成功快照' : '查询结果'}`,
  }));
}
function _accountCountryPromotionBest(display) {
  return [...(display?.items || [])].sort(_compareAccountPromotions)[0] || {plan: 'go', kind: 'unknown'};
}
function _accountCountryPromotionDetail(display) {
  const details = (display?.items || []).map(item => _accountPromotionDetail(item));
  return [details.join('；'), display?.context || ''].filter(Boolean).join('；');
}
function _accountCountryTaskSummaryData(r) {
  const countries = Array.isArray(r?.plan_check_countries)
    ? r.plan_check_countries.map(value => String(value || '').trim().toUpperCase()).filter(Boolean)
    : [];
  const totalRaw = r?.country_total_count;
  const successRaw = r?.country_success_count;
  const totalIsNumber = typeof totalRaw === 'number' && Number.isFinite(totalRaw) && totalRaw > 0;
  const successIsNumber = typeof successRaw === 'number' && Number.isFinite(successRaw) && successRaw >= 0;
  const failedCountries = Array.isArray(r?.failed_countries)
    ? r.failed_countries.map(value => typeof value === 'object' ? value?.country : value).map(value => String(value || '').trim().toUpperCase()).filter(Boolean)
    : [];
  const hasCounts = totalIsNumber || countries.length > 0;
  if (!hasCounts) return null;
  const total = totalIsNumber ? totalRaw : countries.length;
  const success = successIsNumber ? successRaw : 0;
  return {countries, total, success, failedCountries};
}
function _accountCountryTaskState(r, overallTaskStatus = '') {
  if (Array.isArray(r?.plan_check_countries) && r.plan_check_countries.length === 0) return null;
  const results = Array.isArray(r?.plan_check_country_results)
    ? r.plan_check_country_results.filter(item => item && String(item.country || '').trim())
    : [];
  const summaryData = _accountCountryTaskSummaryData(r);
  if (!results.length && !summaryData) return null;
  const success = results.length ? results.filter(item => String(item.status || '').toLowerCase() === 'success').length : summaryData.success;
  const total = results.length ? results.length : summaryData.total;
  const failed = results.length
    ? results.filter(item => ['failed', 'cancelled'].includes(String(item.status || '').toLowerCase())).length
    : summaryData.failedCountries.length;
  const active = results.some(item => ['queued', 'running'].includes(String(item.status || '').toLowerCase())) || ['queued', 'running'].includes(String(overallTaskStatus || '').toLowerCase());
  const allFailed = total > 0 && success === 0 && failed >= total;
  const interrupted = ['failed', 'cancelled'].includes(String(overallTaskStatus || '').toLowerCase()) && active;
  const state = allFailed ? '全部失败' : interrupted ? (overallTaskStatus === 'cancelled' ? '已取消' : '查询中断') : failed && success ? '部分失败' : active ? '查询中' : '';
  const failedText = (!results.length && summaryData.failedCountries.length) ? `失败国家：${summaryData.failedCountries.join('、')}` : '';
  return {state, failedText};
}
function _accountTaskPromotionSummary(items) {
  const best = [...items].sort((a, b) => _compareAccountPromotions(a, b) || Number(Boolean(a.stale)) - Number(Boolean(b.stale)))[0];
  if (!best) return '待查询';
  const hasOffer = ['free_trial', 'discount', 'other_promo'].includes(best.kind);
  return [
    `${hasOffer ? `${_promotionPlanLabel(best.plan)} ` : ''}${_accountPromotionLabel(best)}`,
    best.stale ? '历史' : '',
  ].filter(Boolean).join(' · ');
}
function _accountCountryTaskSummary(r, overallTaskStatus = '', compact = false) {
  const status = _accountCountryTaskState(r, overallTaskStatus);
  if (!status) return '';
  const displays = _accountCountryPromotionDisplays({...r, plan_check_status: r.plan_check_status || overallTaskStatus});
  const offers = compact ? _accountTaskPromotionSummary(displays.flatMap(display => display.items)) : displays.map(display => {
    const best = _accountCountryPromotionBest(display);
    const label = _accountPromotionLabel(best);
    const plan = ['free_trial', 'discount', 'other_promo'].includes(best.kind) ? `${_promotionPlanLabel(best.plan)}: ` : '';
    return `${display.country} ${plan}${label}`;
  }).join(' · ');
  return [status.state, compact ? '' : status.failedText, offers].filter(Boolean).join(' · ');
}
function _accountPromotionLabel(item) {
  const periods = Number(item.duration_num_periods);
  const units = {month: '个月', year: '年', week: '周', day: '天'};
  const unit = units[String(item.duration_period || '').toLowerCase()];
  const duration = Number.isFinite(periods) && periods > 0 && unit ? ` ${periods}${unit}` : '';
  if (item.kind === 'free_trial') return `免费${duration}`;
  if (item.kind === 'discount') {
    const raw = item.discount_percentage;
    const percentage = raw === null || raw === undefined || raw === '' ? NaN : Number(raw);
    const discount = percentage === 50 ? '五折' : (Number.isFinite(percentage) && percentage > 0 && percentage < 100 ? `减 ${percentage}%` : '折扣');
    return `${discount}${duration}`;
  }
  const labels = {other_promo: '其他优惠', none: '无优惠', unknown: '待核验', pending: '待查询', failed: '查询失败', cancelled: '已取消', not_applicable: '不适用'};
  return labels[item.kind] || '待核验';
}
function _accountPromotionDetail(item, context = '') {
  const label = `${_promotionPlanLabel(item.plan)}: ${_accountPromotionLabel(item)}`;
  const details = [label];
  if (item.summary && item.summary !== _accountPromotionLabel(item)) details.push(String(item.summary));
  if (item.title) details.push(String(item.title));
  if (item.campaign_id) details.push(`活动 ${item.campaign_id}`);
  if (['free_trial', 'discount', 'other_promo'].includes(item.kind)) details.push(..._accountPromotionCheckoutDetail(item));
  if (context) details.push(context);
  return details.join('；');
}
function _accountPromotionDisplay(r) {
  const status = String(r.plan_check_status || '').toLowerCase();
  if (['queued', 'running'].includes(status)) {
    const stamp = status === 'queued' ? r.plan_check_queued_at : r.plan_check_started_at;
    return {items: ['go', 'plus'].map(plan => ({plan, kind: 'pending'})), context: `套餐查询${status === 'queued' ? '排队中' : '正在执行'}${stamp ? `: ${stamp}` : ''}`};
  }
  if (status === 'failed') {
    const error = `本次查询失败: ${r.plan_check_error || '未知错误'}`;
    if (r.plan_last_success_at) return {items: _accountPromotions(r), context: `显示上次成功快照；上次成功查询: ${r.plan_last_success_at}；${error}`};
    return {items: ['go', 'plus'].map(plan => ({plan, kind: 'failed'})), context: error};
  }
  if (status !== 'success' && r.plan_check_ok !== true) {
    return {items: ['go', 'plus'].map(plan => ({plan, kind: 'pending'})), context: '尚未查询套餐优惠'};
  }
  return {items: _accountPromotions(r), context: r.plan_checked_at ? `查询于 ${r.plan_checked_at}` : ''};
}
function _accountPromotionTone(item) {
  if (item.kind === 'free_trial') return 'success';
  if (item.kind === 'failed') return 'danger';
  if (item.kind === 'cancelled') return 'danger';
  return ['discount', 'other_promo', 'unknown', 'pending'].includes(item.kind) ? 'warning' : 'neutral';
}
function _compareAccountPromotions(a, b) {
  const priority = {free_trial: 0, discount: 1, other_promo: 2, unknown: 3, pending: 4, failed: 5, cancelled: 5, none: 6, not_applicable: 7};
  const kind = (priority[a.kind] ?? 3) - (priority[b.kind] ?? 3);
  if (kind) return kind;
  if (['free_trial', 'discount'].includes(a.kind)) {
    const percentage = item => {
      const value = Number(item.discount_percentage);
      return Number.isFinite(value) && value > 0 && value <= 100 ? value : 0;
    };
    const discount = percentage(b) - percentage(a);
    if (a.kind === 'discount' && discount) return discount;
    // 期限只用于展示排序，按近似天数比较，标签仍保留实际账单周期。
    const duration = item => {
      const units = {day: 1, week: 7, month: 30, year: 365};
      const count = typeof item.duration_num_periods === 'boolean' ? 0 : Number(item.duration_num_periods);
      return Number.isFinite(count) && count > 0 ? count * (units[String(item.duration_period || '').toLowerCase()] || 0) : 0;
    };
    const length = duration(b) - duration(a);
    if (length) return length;
  }
  return Number(b.plan === 'plus') - Number(a.plan === 'plus');
}
function _accountPromotionGroups(items) {
  return ['go', 'plus'].map(plan => {
    const matches = items.filter(item => item.plan === plan).sort(_compareAccountPromotions);
    return {plan, items: matches, lead: matches[0]};
  });
}
function _accountPromotionGroupLabel(group) {
  const extra = group.items.length > 1 ? ` +${group.items.length - 1}` : '';
  return `${_promotionPlanLabel(group.plan)}: ${_accountPromotionLabel(group.lead)}${extra}`;
}
function _accountPromotionGroupDetail(group, context = '') {
  const details = group.items.map(item => _accountPromotionDetail(item));
  if (context) details.push(context);
  return details.join('；');
}
function _accountPlusPromotion(items) {
  return items.filter(item => item.plan === 'plus').sort(_compareAccountPromotions)[0] || {plan: 'plus', kind: 'unknown'};
}
function _accountPromotionPaymentMethods(item) {
  // 支付方式必须属于该套餐活动，不能按国家推断或借用 Go 的结账结果。
  const methods = Array.isArray(item.payment_method_types) ? item.payment_method_types : [];
  const labels = {card: '银行卡', link: 'Link', upi: 'UPI'};
  return [...new Set(methods.filter(value => typeof value === 'string').map(value => value.trim().toLowerCase()).filter(value => {
    // 仅接受支付方式代码，避免把链接、会话标识或凭据误显示成支付方式。
    return /^[a-z][a-z0-9_-]{0,63}$/.test(value) && !/^(?:cs_(?:live|test)|oaics|(?:pk|sk)_(?:live|test))(?:_|$)/.test(value) && !value.includes('secret');
  }).map(method => {
    return Object.hasOwn(labels, method) ? labels[method] : method;
  }))];
}
function _accountPromotionCheckoutStatus(item) {
  const country = String(item.country || '').trim().toUpperCase();
  const checkoutCountry = String(item.checkout_country || '').trim().toUpperCase();
  if (country && checkoutCountry && country !== checkoutCountry) return 'mismatched';
  const status = String(item.checkout_status || '').toLowerCase();
  return ['success', 'failed', 'skipped'].includes(status) ? status : '';
}
function _accountPromotionCheckoutAmount(item) {
  const amount = item.checkout_amount_due_minor;
  const exponent = item.checkout_currency_exponent;
  const currency = typeof item.checkout_currency === 'string' ? item.checkout_currency.trim().toUpperCase() : '';
  if (!Number.isSafeInteger(amount) || amount < 0 || !Number.isInteger(exponent) || exponent < 0 || exponent > 3 || !/^[A-Z]{3}$/.test(currency)) return '';
  const digits = String(amount).padStart(exponent + 1, '0');
  const value = exponent ? `${digits.slice(0, -exponent)}.${digits.slice(-exponent)}`.replace(/\.?0+$/, '') : digits;
  return `${value} ${currency}`;
}
function _accountPromotionCheckoutSession(item) {
  const type = String(item.session_type || '').toLowerCase();
  return ['cs_live', 'oaics'].includes(type) ? type : '';
}
function _accountPromotionCheckoutError(item) {
  // 后端只保存安全错误摘要；前端仍过滤意外传入的完整链接和结账凭据。
  const error = typeof item.checkout_error === 'string' ? item.checkout_error : '';
  return error.replace(/https?:\/\/[^\s；，]+/gi, '[链接已隐藏]')
    .replace(/\b(?:cs_(?:live|test)|oaics|(?:pk|sk)_(?:live|test))_[a-z0-9_-]+\b/gi, '[结账标识已隐藏]')
    .replace(/\b[^\s；，]*secret[^\s；，]*\b/gi, '[凭据已隐藏]').slice(0, 240).trim();
}
function _accountPromotionCheckoutDetail(item) {
  const status = _accountPromotionCheckoutStatus(item);
  if (status === 'failed' || status === 'skipped') {
    const error = _accountPromotionCheckoutError(item);
    const httpStatus = item.checkout_http_status;
    const http = Number.isInteger(httpStatus) && httpStatus >= 100 && httpStatus <= 599 ? `HTTP ${httpStatus}` : '';
    return [status === 'failed' ? '支付方式查询失败' : '支付方式待查询', error || http].filter(Boolean);
  }
  if (status === 'mismatched') return ['支付方式: 待查询'];
  const methods = _accountPromotionPaymentMethods(item);
  const amount = status === 'success' ? _accountPromotionCheckoutAmount(item) : '';
  const session = status === 'success' ? _accountPromotionCheckoutSession(item) : '';
  return [amount ? `实际应付: ${amount}` : '', session ? `结账会话: ${session}` : '', `支付方式: ${methods.join(' ') || (status === 'success' ? '未返回' : '待查询')}`].filter(Boolean);
}
function _accountPlusCellLabel(item) {
  if (item.kind === 'unknown') return '待查询';
  if (item.kind === 'not_applicable') return '无优惠';
  if (item.kind === 'free_trial') return '免费';
  return _accountPromotionLabel(item);
}
function _accountPromotionTooltip(item) {
  const details = [`${_promotionPlanLabel(item.plan)}: ${_accountPromotionLabel(item)}`];
  if (['free_trial', 'discount', 'other_promo'].includes(item.kind)) {
    details.push(..._accountPromotionCheckoutDetail(item));
  }
  return details.join('；');
}
function _accountPromotionQueryTooltip(queryStatus, error = '') {
  const status = String(queryStatus || '').toLowerCase();
  if (status === 'queued') return '新任务排队中';
  if (status === 'running') return '新任务正在执行';
  if (status === 'failed') return `本次查询失败: ${error || '未知错误'}`;
  if (status === 'cancelled') return `本次查询已取消${error ? `: ${error}` : ''}`;
  return '';
}
function _accountPromotionCountryTone(country) {
  const code = String(country || '').trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(code)) return '';
  const hash = (code.charCodeAt(0) * 31 + code.charCodeAt(1)) % 16;
  return `is-country-${hash}`;
}
function _accountPromotionRowMarkup({best, country = '', stale = false, label, tooltip}) {
  const countryTone = _accountPromotionCountryTone(country);
  const unknownCountry = country === '国家未记录';
  const heading = country
    ? `<span class="account-promotion-country"${unknownCountry ? ' aria-label="国家未记录"' : ''}>${esc(unknownCountry ? '—' : country)}${stale ? '<span class="account-promotion-stale">历史</span>' : ''}：</span>`
    : '';
  return `<span class="account-promotion-country-row is-${_accountPromotionTone(best)}${countryTone ? ` ${countryTone}` : ''}${stale ? ' is-stale' : ''}" data-accounts-tooltip="${esc(tooltip)}" tabindex="0">${heading}<span class="account-promotion-label">${esc(label)}</span></span>`;
}
function _promotionCell(r) {
  // 列表只显示优惠摘要，悬浮详情保留当前活动的结账信息。
  const cell = lines => `<div class="account-promotion-cell account-promotion-cell--countries${lines.length === 1 ? ' account-promotion-cell--single' : ''}">${lines.join('')}</div>`;
  const countryDisplays = _accountCountryPromotionDisplays(r);
  if (countryDisplays.length) {
    const rows = countryDisplays.map(display => ({display, best: _accountPlusPromotion(display.items)}));
    const detail = [
      ...rows.map(({display, best}) => [
        `${display.country}${display.stale ? '（历史）' : ''} ${_accountPromotionTooltip(best)}`,
        display.queryContext,
      ].filter(Boolean).join('\n')),
      _accountPromotionQueryTooltip(r.plan_check_status, r.plan_check_error),
    ].filter(Boolean).join('\n');
    const allNone = rows.every(({best}) => ['none', 'not_applicable'].includes(best.kind));
    const allPending = rows.every(({best}) => ['unknown', 'pending'].includes(best.kind));
    if ((allNone || allPending) && rows.every(({display}) => !display.stale)) {
      return cell([_accountPromotionRowMarkup({best: {kind: allNone ? 'none' : 'pending'}, label: allNone ? '无优惠' : '待查询', tooltip: detail})]);
    }
    // 显示最新两个国家，同一查询时间或未记录时间时保留配置国家顺序。
    const visibleRows = rows
      .filter(({display, best}) => display.stale || !['none', 'not_applicable'].includes(best.kind))
      .sort((left, right) => (right.display.checkedAt || 0) - (left.display.checkedAt || 0))
      .slice(0, 2);
    const countryMarkup = ({display, best}) => {
      const label = _accountPlusCellLabel(best);
      return _accountPromotionRowMarkup({best, country: display.country, stale: display.stale, label, tooltip: detail});
    };
    return cell(visibleRows.map(countryMarkup));
  }
  const display = _accountPromotionDisplay(r);
  const best = _accountPlusPromotion(display.items);
  const hasOffer = ['free_trial', 'discount', 'other_promo'].includes(best.kind);
  const countryValue = String(r.plan_promotion_country || best.country || '').trim().toUpperCase();
  const country = /^[A-Z]{2}$/.test(countryValue) ? countryValue : '国家未记录';
  const label = _accountPlusCellLabel(best);
  const historical = r.plan_check_status === 'failed' && !!r.plan_last_success_at;
  const tooltip = [
    `${hasOffer ? `${country} ` : ''}${_accountPromotionTooltip(best)}`,
    historical ? '显示上次成功快照' : '',
    _accountPromotionQueryTooltip(r.plan_check_status, r.plan_check_error),
  ].filter(Boolean).join('\n');
  return cell([_accountPromotionRowMarkup({best, country: hasOffer ? country : '', stale: historical, label, tooltip})]);
}
function _planAction(r) {
  if (accountIsDeactivated(r)) return '';
  if (['queued','running'].includes(r.plan_check_status)) {
    const automatic = r.plan_check_trigger === 'registration_auto';
    const queued = r.plan_check_status === 'queued';
    const label = automatic ? (queued ? '自动查询排队中…' : '自动查询中…') : (queued ? '查询排队中…' : '查询中…');
    return `<button data-plan-check="${esc(r.id)}" disabled title="套餐查询正在执行，完成后可再次查询">${label}</button>`;
  }
  return `<button data-plan-check="${esc(r.id)}" title="查询当前套餐以及 Go、Plus 免费试用或折扣优惠">查套餐</button>`;
}
function _fmtExtractExpire(v) {
  if (!v) return '';
  const raw = String(v).trim();
  let n = Number(raw);
  if (!Number.isNaN(n) && n > 0) {
    if (n > 1e12) n = Math.floor(n / 1000);
    const d = new Date(n * 1000);
    if (!Number.isNaN(d.getTime())) return _fmtPlanTime(d.toISOString(), false);
  }
  return _fmtPlanTime(raw, false) || raw;
}
function _extractLinkCell(r) {
  const s = r.extract_link_status || '';
  const err = r.extract_link_error || '';
  const msg = r.extract_link_message || '';
  const title = esc(err || msg || r.extract_link_job_id || '');
  if (s === 'queued') return `<span class="pill status-running" title="${title}">提链排队</span>`;
  if (s === 'running') return `<span class="pill status-running" title="${title}">${esc(msg || '提链中')}</span>`;
  if (s === 'success') {
    const typ = (r.extract_link_type || '').toUpperCase();
    return `<div class="extract-link-cell"><span class="pill status-success" title="${title || '提炼成功，可在更多菜单复制地址'}">提链成功${typ ? '(' + esc(typ) + ')' : ''}</span></div>`;
  }
  return '';
}
function _extractLinkAction(r) {
  if (accountIsDeactivated(r)) return '';
  const s = r.extract_link_status || '';
  if (['queued','running'].includes(s)) return `<button disabled title="${esc(r.extract_link_message || '提链任务执行中')}">提链中…</button>`;
  const plan = (r.current_plan_type || r.plan_type || '').toString().toLowerCase();
  const eligible = plan === 'free' && _isFreeTrialPromotion(r);
  if (!eligible) return '';
  const failedReason = s === 'failed' ? (r.extract_link_error || r.extract_link_message || '') : '';
  return `<button class="good" data-extract-link="${esc(r.id)}" title="${esc(failedReason ? '重新提链；上次失败原因：' + failedReason : '为已确认 Plus 免费试用资格的 free 账号创建提链任务')}">提链</button>`;
}
function _codexAction(r) {
  if (accountIsDeactivated(r)) return '';
  const s = r.codex_status || '';
  const exec = r.codex_execution_status || '';
  if (['queued','running','cancelling'].includes(exec) || s === 'retrying') {
    return `<button class="danger" data-codex-stop="${esc(r.email)}" title="协作式停止该账号正在进行的 Codex 补跑">${exec === 'cancelling' ? '停止中…' : '停止补跑'}</button>`;
  }
  if (s === 'deactivated') return '';
  const label = s === 'success' ? '重新补跑 Codex' : '补跑 Codex';
  return `<button data-codex-retry="${esc(r.email)}" title="重新跑一次 Codex 授权（会消耗 1 封邮箱 OTP + 1 个接码短信）">${label}</button>`;
}
function _liveCheckHttpStatus(r) {
  const direct = Number.parseInt(r?.live_check_http_status, 10);
  if (Number.isFinite(direct) && direct >= 100 && direct <= 599) return direct;
  const matched = String(r?.live_check_error || '').match(/\bHTTP\s*([1-5]\d{2})\b/i);
  return matched ? Number.parseInt(matched[1], 10) : null;
}
function _tokenRejectedByLiveCheck(r) {
  return (r?.live_check_status || '') === 'failed';
}
function _tokenDisplayState(r) {
  if (!r?.has_access_token) return {key: 'missing', label: '无 Token', title: '账号没有 Token'};
  const expiresAt = r.token_expires_at || '';
  const expires = expiresAt ? new Date(expiresAt) : null;
  const expiredByTime = expires && !Number.isNaN(expires.getTime()) && expires.getTime() <= Date.now();
  const expiryText = formatDateTime(expiresAt) || '未知';
  const liveHttpStatus = _liveCheckHttpStatus(r);
  if (_tokenRejectedByLiveCheck(r)) {
    const codeText = liveHttpStatus ? `HTTP ${liveHttpStatus}` : '状态码未知';
    const reason = String(r.live_check_error || '在线验证失败，未提供具体原因');
    return {
      key: 'invalid',
      label: `失效 · ${liveHttpStatus || '未知'}`,
      title: `${codeText}；${reason}；JWT 标称到期：${expiryText}；点击复制完整 Token`,
    };
  }
  if (r.token_expired === true || expiredByTime) {
    return {key: 'expired', label: '过期', title: `Token 到期：${expiryText}；点击复制完整 Token`};
  }
  return {key: 'normal', label: '正常', title: `Token 到期：${expiryText}；点击复制完整 Token`};
}
function _tokenCellV2(r) {
  const state = _tokenDisplayState(r);
  if (state.key === 'missing') return `<span class="acc-v2-muted">${esc(state.label)}</span>`;
  const label = state.key === 'invalid' ? '失效' : state.label;
  const button = `<button type="button" class="acc-v2-token-state is-${attrEsc(state.key)}" data-account-copy-secret="access_token" data-account-id="${esc(r.id)}" title="${esc(state.title)}">${esc(label)}</button>`;
  const status = state.key === 'invalid' ? _liveCheckHttpStatus(r) : null;
  return `<div class="account-cell-lines"><div class="account-cell-line">${button}</div>${status ? `<div class="account-cell-line account-cell-line--sub">HTTP ${status}</div>` : ''}</div>`;
}
function _passwordCellV2(r) {
  if (!r.has_account_password) return '<span class="acc-v2-muted">未设置</span>';
  return `<button type="button" class="acc-v2-token-copy" data-account-copy-secret="account_password" data-account-id="${esc(r.id)}" title="复制该账号密码">复制</button>`;
}
function _totpCellV2(r) {
  const button = r.totp_enabled
    ? `<button type="button" data-account-totp-copy="${esc(r.id)}" title="获取并复制当前 6 位 TOTP 验证码">复制</button>`
    : `<button type="button" data-account-action="twofa" data-account-id="${esc(r.id)}"${accountIsDeactivated(r) ? ' disabled title="账号已停用，无法补充 2FA"' : ' title="为该账号补充 Authenticator 2FA"'}>补充</button>`;
  return `
    <div class="account-cell-lines status-action-cell" data-account-totp-cell="${esc(r.id)}">
      <div class="account-cell-line">${button}</div>
    </div>
  `;
}
function _accountTimesCellV2(r) {
  const full = value => String(value || '-').replace('T', ' ');
  const shortTime = value => {
    const text = full(value);
    const match = text.match(/^\d{4}-(\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?/);
    return match ? [match[1], match[2]].filter(Boolean).join(' ') : text;
  };
  const line = (label, value) => `<div class="account-cell-line"><span class="account-time-label">${label}</span><time datetime="${esc(value || '')}">${esc(shortTime(value))}</time></div>`;
  return `<div class="account-cell-lines account-times-cell" title="${esc(`创建 ${full(r.created_at)}；更新 ${full(r.updated_at)}`)}">${line('创建', r.created_at)}${line('更新', r.updated_at)}</div>`;
}
function _deactivationMailCell(r) {
  const detected = r.deactivation_mail_detected === true;
  const status = r.deactivation_mail_scan_status || '';
  const checked = r.deactivation_mail_checked_at || '';
  const received = r.deactivation_mail_received_at || '';
  const subject = r.deactivation_mail_subject || '';
  const sender = r.deactivation_mail_sender || '';
  const err = r.deactivation_mail_error || '';
  const supported = ['email_butler','cloudflare','icloud_hide'].includes((r.email_source || '').toString().toLowerCase());
  let title = '尚未扫描';
  if (detected) {
    title = [received && `收件: ${received}`, sender && `发件人: ${sender}`, subject].filter(Boolean).join('；') || '已收到封号邮件';
    return `<div class="account-cell-lines status-action-cell" title="${esc(title)}"><div class="account-cell-line"><span class="pill status-failed" title="${esc(title)}">封号</span></div></div>`;
  }
  let disabled = false;
  let buttonTitle = '扫描该账号对应邮箱；不会刷新 AT';
  if (!supported || status === 'unsupported') {
    disabled = true;
    title = err || '当前邮箱来源暂不支持扫描';
    buttonTitle = title;
  } else if (status === 'queued' || status === 'running') {
    disabled = true;
    title = status === 'queued'
      ? '排队中；正在扫描邮箱，不会刷新 AT'
      : '扫描中；正在扫描邮箱，不会刷新 AT';
    buttonTitle = title;
  } else if (status === 'success') {
    title = checked ? `扫描时间: ${checked}` : '未发现高置信度封号通知';
  } else if (status === 'failed') {
    title = err || checked || '扫描失败';
  }
  const disabledAttr = disabled ? ' disabled' : '';
  const button = `<button type="button" data-deactivation-mail-check="${esc(r.id)}"${disabledAttr} title="${esc(buttonTitle)}">复查</button>`;
  return `<div class="account-cell-lines status-action-cell" title="${esc(title)}"><div class="account-cell-line">${button}</div></div>`;
}
function _accountsV2MoreMenu(r) {
  const parts = [
    `<button type="button" data-account-copy-secret="copy_line" data-account-id="${esc(r.id)}">复制整行</button>`,
    `<button type="button" data-account-copy-secret="chatgpt_session" data-account-id="${esc(r.id)}" title="复制完整 ChatGPT session JSON">复制 ChatGPT session</button>`,
    r.has_account_password ? `<button type="button" data-account-copy-secret="account_password" data-account-id="${esc(r.id)}">复制账号密码</button>` : '',
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="password" data-account-id="${esc(r.id)}">补密码</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="twofa" data-account-id="${esc(r.id)}">补 2FA</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="password_change" data-account-id="${esc(r.id)}">修改密码</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="twofa_change" data-account-id="${esc(r.id)}">修改 2FA</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="complete" data-account-id="${esc(r.id)}">补全账号</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-email-change="${esc(r.id)}" title="协议自动领取新邮箱并换绑；不会启动浏览器">换绑邮箱</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" onclick="checkSelectedLive([Number('${esc(r.id)}')], this); return false;" title="只在线验证现有 Token；不会发送邮箱验证码或刷新 AT">查活</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" onclick="refreshSelectedToken([Number('${esc(r.id)}')], this); return false;" title="${esc(accountAtRefreshUiSettings().title)}">刷新AT</button>`,
    accountIsDeactivated(r) ? `<button type="button" data-account-restore="${esc(r.id)}" title="已确认 OpenAI 恢复访问权限后，解除本地停用标记">已解封，恢复账号</button>` : '',
    `<button type="button" data-account-email-invalid="${esc(r.id)}" data-invalid="${r.email_invalid === true ? '0' : '1'}" title="仅更新独立邮箱失效标记，不修改 OpenAI 账号状态">${r.email_invalid === true ? '解除邮箱失效' : '标记邮箱失效'}</button>`,
    `<button type="button" data-account-task-history="${esc(r.email)}" title="在任务实例中查看该账号的 Codex 补跑、查活、AT 刷新、套餐和封号邮件历史">任务记录</button>`,
    _planAction(r),
    _extractLinkAction(r),
    (String(r.extract_link_status || '').toLowerCase() === 'success' || r.extract_link_ok === true)
      && (r.extract_link_long_url || r.extract_link_copy_paste)
      ? cbtn('复制提炼地址', r.extract_link_long_url || r.extract_link_copy_paste, 'account-menu-copy')
      : '',
    _codexAction(r),
    `<button type="button" data-account-archive="${esc(r.id)}" data-archived="${r.archived ? '0' : '1'}" title="${r.archived ? '恢复到默认账号列表' : '归档后默认账号列表不再显示'}">${r.archived ? '恢复' : '归档'}</button>`,
  ].filter(html => String(html || '').trim());
  return parts.join('');
}
function _accountDetailState(label, value, tone = 'neutral', detail = '') {
  return `<div class="account-detail-state">
    <span class="account-detail-label">${esc(label)}</span>
    <div class="account-detail-state-value"><span class="account-detail-dot account-detail-dot--${esc(tone)}"></span><strong>${esc(value || '-')}</strong></div>
    ${detail ? `<small>${esc(detail)}</small>` : ''}
  </div>`;
}
function _accountDetailAuthMethod(value) {
  const labels = {
    password: '密码登录',
    email_otp: '邮箱 OTP',
    token: 'Token',
    protocol: '协议认证',
    browser: '浏览器认证',
  };
  const key = String(value || '').toLowerCase();
  return labels[key] || value || '未记录';
}
function _accountDetailFingerprintMarkup(r) {
  const fingerprint = r.fingerprint_summary && typeof r.fingerprint_summary === 'object'
    ? r.fingerprint_summary : {};
  const sourceLabels = {protocol: '协议认证', roxy: 'RoxyBrowser', browser: '浏览器', unknown: '未知来源'};
  const source = sourceLabels[String(fingerprint.source || '').toLowerCase()] || fingerprint.source || '未记录';
  const dpr = fingerprint.device_pixel_ratio == null ? '未记录' : `${fingerprint.device_pixel_ratio}x`;
  const hasFingerprint = Object.keys(fingerprint).length > 0;
  return `<div class="account-detail-section">
    <div class="account-detail-section-title">最近认证指纹</div>
    <p class="account-detail-section-copy">只展示最近一次认证观测的安全摘要，不代表注册时永久固定的浏览器环境。</p>
    <div class="account-detail-grid">
      ${_accountDetailState('来源', hasFingerprint ? source : '未记录', hasFingerprint ? 'info' : 'neutral')}
      ${_accountDetailState('Profile 摘要', fingerprint.profile_ref || '未记录', fingerprint.profile_ref ? 'info' : 'neutral')}
      ${_accountDetailRoxyProfileState(r)}
      ${_accountDetailState('浏览器 / 系统', fingerprint.browser || '未记录')}
      ${_accountDetailState('屏幕 / DPR', fingerprint.screen ? `${fingerprint.screen} / ${dpr}` : '未记录')}
      ${_accountDetailState('语言', fingerprint.language || '未记录')}
      ${_accountDetailState('时区', fingerprint.timezone || '未记录')}
      ${_accountDetailState('观测国家', fingerprint.geo_country || '未记录')}
      ${_accountDetailState('硬件摘要', fingerprint.hardware || '未记录')}
      ${_accountDetailState('观测时间', fingerprint.observed_at ? _fmtPlanTime(fingerprint.observed_at) : '未记录')}
    </div>
  </div>`;
}
function _accountDetailRoxyProfileState(r) {
  const profileName = String(r.roxy_profile_name || '').trim();
  const profileId = String(r.roxy_profile_id || '').trim();
  return _accountDetailState(
    'Roxy Profile 窗口名称',
    profileName || '未记录',
    profileName ? 'info' : 'neutral',
    profileId ? `Profile ID: ${profileId}` : '',
  );
}
function _accountCountryDetailMarkup(r, displays) {
  const resultByCountry = new Map((Array.isArray(r?.plan_check_country_results) ? r.plan_check_country_results : [])
    .filter(item => item && String(item.country || '').trim())
    .map(item => [String(item.country).trim().toUpperCase(), item]));
  const statusLabels = {queued: '排队中', running: '查询中', success: '已完成', failed: '失败', cancelled: '已取消'};
  const success = [...resultByCountry.values()].filter(item => String(item.status || '').toLowerCase() === 'success').length;
  const total = resultByCountry.size;
  const failed = [...resultByCountry.values()].filter(item => ['failed', 'cancelled'].includes(String(item.status || '').toLowerCase())).length;
  const active = [...resultByCountry.values()].some(item => ['queued', 'running'].includes(String(item.status || '').toLowerCase()));
  const overallStatus = String(r?.plan_check_status || '').toLowerCase();
  const overallAborted = ['failed', 'cancelled'].includes(overallStatus) && active;
  const allFailed = total > 0 && success === 0 && failed >= total;
  const partial = !allFailed && ((success > 0 && failed > 0) || (r.plan_check_partial === true && success > 0));
  const state = allFailed ? ' · 全部失败' : overallAborted ? ` · ${overallStatus === 'cancelled' ? '已取消' : '查询中断'}` : partial ? ' · 部分失败' : active ? ' · 查询中' : '';
  const summary = total ? `${success}/${total} 个国家成功${state}` : '未记录国家结果';
  return `${displays.map(display => {
    const entry = resultByCountry.get(display.country);
    const best = _accountCountryPromotionBest(display);
    const status = String(entry?.status || '').toLowerCase();
    const statusText = display.stale && ['queued', 'running'].includes(overallStatus)
      ? (overallStatus === 'queued' ? '新任务排队中' : '新任务正在执行')
      : overallAborted && ['queued', 'running'].includes(status)
        ? (overallStatus === 'cancelled' ? '已取消' : '查询中断')
        : statusLabels[status] || '结果待确认';
    const context = [statusText, _accountCountryPromotionDetail(display)].filter(Boolean).join('；');
    return _accountDetailState(`${display.country} 优惠`, _accountPromotionGroupLabel({plan: best.plan, items: [best], lead: best}), _accountPromotionTone(best), context);
  }).join('')}${_accountDetailState('多国套餐检查', summary, allFailed || overallAborted ? 'danger' : partial || active ? 'warning' : 'success', r.plan_checked_at ? `检查于 ${_fmtPlanTime(r.plan_checked_at)}` : '')}`;
}
function _accountDetailMarkup(r) {
  const liveHttpStatus = _liveCheckHttpStatus(r);
  const liveHttpLabel = liveHttpStatus ? ` (HTTP ${liveHttpStatus})` : '';
  const tokenDisplay = _tokenDisplayState(r);
  const tokenStateLabels = {missing: '无 Token', normal: 'Token 正常', expired: 'Token 已过期', invalid: `Token 已失效${liveHttpLabel}`};
  const tokenState = tokenStateLabels[tokenDisplay.key] || tokenDisplay.label;
  const tokenTone = tokenDisplay.key === 'normal' ? 'success' : 'danger';
  const liveState = r.live_check_status === 'live' ? '上次查活通过' : (r.live_check_status === 'failed' ? `查活失败${liveHttpLabel}` : (r.live_check_status === 'running' ? '查活中' : '未查活'));
  const liveTone = r.live_check_status === 'live' ? 'success' : (r.live_check_status === 'failed' ? 'danger' : (r.live_check_status === 'running' ? 'warning' : 'neutral'));
  const plan = (r.current_plan_type || r.plan_type || '未查询').toString();
  const promotionDisplay = _accountPromotionDisplay(r);
  const countryDisplays = _accountCountryPromotionDisplays(r);
  const codexRaw = (r.codex_status || r.codex_execution_status || '').toString().toLowerCase();
  const codexLabels = { success: '已通过', completed: '已通过', failed: '失败', deactivated: '已废号', running: '补跑中', queued: '排队中', cancelling: '停止中', retrying: '补跑中', stopped: '已停止', pending_confirmation: '待确认', skipped: '已跳过' };
  const codex = codexLabels[codexRaw] || '未授权';
  const codexTone = ['success', 'completed'].includes(codexRaw) ? 'success' : (['failed', 'deactivated'].includes(codexRaw) ? 'danger' : (['running', 'queued', 'cancelling', 'retrying'].includes(codexRaw) ? 'warning' : 'neutral'));
  const risk = r.deactivation_mail_detected ? '发现封号邮件' : (r.deactivation_mail_scan_status === 'success' ? '未发现封号邮件' : '待扫描');
  const riskTone = r.deactivation_mail_detected ? 'danger' : (r.deactivation_mail_scan_status === 'success' ? 'success' : 'neutral');
  const authFallback = r.last_auth_fallback_used === true ? '已使用回退' : (r.last_auth_fallback_used === false ? '未使用回退' : '未记录');
  const authFallbackTone = r.last_auth_fallback_used === true ? 'warning' : (r.last_auth_fallback_used === false ? 'success' : 'neutral');
  const note = String(r.note || '').trim();
  return `<div class="account-detail-section">
    <div class="account-detail-section-title">账号与注册</div>
    <div class="account-detail-grid">
      ${_accountDetailState('账号 ID', `#${r.id}`, 'info')}
      ${_accountDetailState('邮箱来源', facetLabel('source', r.email_source) || '未知')}
      ${_accountDetailState('姓名', r.user_name || '未设置')}
      ${_accountDetailState('注册出口国家', r.registration_proxy_region || '未记录', r.registration_proxy_region ? 'info' : 'neutral')}
      ${_accountDetailState('注册代理', r.registration_proxy_provider || '未记录')}
      ${_accountDetailState('注册时间', _fmtPlanTime(r.created_at) || '-')}
    </div>
    ${note ? `<div class="account-detail-note"><span>备注</span><p>${esc(note)}</p></div>` : ''}
  </div>
  <div class="account-detail-section">
    <div class="account-detail-section-title">健康与安全</div>
    <div class="account-detail-grid">
      ${_accountDetailState('访问 Token', tokenState, tokenTone, r.token_expires_at ? `${tokenDisplay.key === 'invalid' ? 'JWT 标称到期' : '到期'} ${_fmtPlanTime(r.token_expires_at)}` : '')}
      ${_accountDetailState('在线状态', liveState, liveTone, r.live_checked_at ? `检查于 ${_fmtPlanTime(r.live_checked_at)}` : '')}
      ${_accountDetailState('邮箱状态', r.email_invalid === true ? '邮箱失效' : '未标记失效', r.email_invalid === true ? 'danger' : 'neutral', r.email_invalid === true ? [r.email_invalid_reason, r.email_invalid_at ? `标记于 ${_fmtPlanTime(r.email_invalid_at)}` : ''].filter(Boolean).join('；') : '未标记不代表已验证邮箱可用')}
      ${_accountDetailState('账号密码', r.has_account_password ? '已设置' : '未设置', r.has_account_password ? 'success' : 'neutral')}
      ${_accountDetailState('Authenticator 2FA', r.totp_enabled ? '已启用' : '未启用', r.totp_enabled ? 'success' : 'neutral')}
      ${_accountDetailState('封号邮件', risk, riskTone)}
      ${_accountDetailState('最近认证方式', _accountDetailAuthMethod(r.last_auth_method))}
      ${_accountDetailState('认证回退', authFallback, authFallbackTone)}
      ${_accountDetailState('归档状态', r.archived ? '已归档' : '活跃', r.archived ? 'neutral' : 'success')}
    </div>
  </div>
  ${_accountDetailFingerprintMarkup(r)}
  <div class="account-detail-section">
    <div class="account-detail-section-title">套餐与授权</div>
    <div class="account-detail-grid">
      ${_accountDetailState('当前套餐', plan, plan.toLowerCase() === 'free' ? 'info' : 'success', r.plan_checked_at ? `检查于 ${_fmtPlanTime(r.plan_checked_at)}` : '')}
      ${countryDisplays.length ? _accountCountryDetailMarkup(r, countryDisplays) : _accountPromotionGroups(promotionDisplay.items).map(group => _accountDetailState(`${_promotionPlanLabel(group.plan)} 优惠`, _accountPromotionGroupLabel(group), _accountPromotionTone(group.lead), _accountPromotionGroupDetail(group, promotionDisplay.context))).join('')}
      ${_accountDetailState('Codex', codex, codexTone)}
      ${_accountDetailState('套餐检查', r.plan_checked_at ? _fmtPlanTime(r.plan_checked_at) : '未检查')}
    </div>
  </div>`;
}
async function refreshAccountRoxyProfile(account) {
  if (!account || !account.id) return;
  $('#accountDetailBody').innerHTML = _accountDetailMarkup(account);
  try {
    const result = await api(`/api/accounts/${encodeURIComponent(account.id)}/roxy-profile`);
    account.roxy_profile_id = String(result.profile_id || '').trim();
    account.roxy_profile_name = String(result.window_name || '').trim();
  } catch (_) {
    account.roxy_profile_id = '';
    account.roxy_profile_name = '';
  } finally {
    if (Number($('#accountDetailDrawer')?.dataset.accountId || 0) === Number(account.id)) {
      $('#accountDetailBody').innerHTML = _accountDetailMarkup(account);
    }
  }
}
function openAccountDetail(id) {
  const account = ACCOUNTS.find(item => Number(item.id) === Number(id));
  if (!account) { showToast('账号详情暂不可用，请先刷新列表'); return; }
  $('#accountDetailDrawer').dataset.accountId = String(account.id);
  account.roxy_profile_id = '';
  account.roxy_profile_name = '';
  $('#accountDetailTitle').textContent = account.email || `账号 #${account.id}`;
  $('#accountDetailSubtitle').textContent = `账号 #${account.id} · ${facetLabel('source', account.email_source) || '未知来源'}`;
  $('#accountDetailBody').innerHTML = _accountDetailMarkup(account);
  $('#accountDetailDrawer').classList.remove('hidden');
  $('#accountDetailBackdrop').classList.remove('hidden');
  $('#accountDetailBackdrop').setAttribute('aria-hidden', 'false');
  updateModalScrollLock();
  $('#btnCloseAccountDetail')?.focus({preventScroll:true});
  void loadAccountPlanDetails(account).then(() => {
    if (Number($('#accountDetailDrawer')?.dataset.accountId || 0) === Number(account.id)) return refreshAccountRoxyProfile(account);
  }).catch(() => {
    if (Number($('#accountDetailDrawer')?.dataset.accountId || 0) === Number(account.id)) {
      showToast('优惠详情加载失败，请重新打开详情重试');
    }
  });
}
function closeAccountDetail() {
  $('#accountDetailDrawer')?.classList.add('hidden');
  $('#accountDetailBackdrop')?.classList.add('hidden');
  $('#accountDetailBackdrop')?.setAttribute('aria-hidden', 'true');
  $('#accountDetailDrawer')?.removeAttribute('data-account-id');
  updateModalScrollLock();
}
$('#btnCloseAccountDetail')?.addEventListener('click', closeAccountDetail);
$('#accountDetailBackdrop')?.addEventListener('click', closeAccountDetail);
function closeAccountsV2MoreMenus(except = null) {
  document.querySelectorAll('.accounts-table-v2 .acc-v2-more.open').forEach(el => {
    if (except && el === except) return;
    el.classList.remove('open');
  });
}
function positionAccountsV2MoreMenu(wrap) {
  const btn = wrap.querySelector('.acc-v2-more-btn');
  const menu = wrap.querySelector('.acc-v2-more-menu');
  if (!btn || !menu) return;
  const rect = btn.getBoundingClientRect();
  const menuW = Math.max(menu.offsetWidth || 148, 148);
  const menuH = menu.offsetHeight || 0;
  let left = rect.right - menuW;
  left = Math.max(8, Math.min(left, window.innerWidth - menuW - 8));
  let top = rect.bottom + 4;
  if (top + menuH > window.innerHeight - 8 && rect.top - menuH - 4 > 8) {
    top = rect.top - menuH - 4;
  }
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
}
function getOpenAccountsV2MoreId() {
  const open = document.querySelector('.accounts-table-v2 .acc-v2-more.open');
  return open?.dataset.accountMoreId || '';
}
function restoreAccountsV2MoreMenu(accountId) {
  if (!accountId) return;
  const wrap = Array.from(document.querySelectorAll('.accounts-table-v2 .acc-v2-more'))
    .find(item => String(item.dataset.accountMoreId || '') === String(accountId));
  if (!wrap) return;
  const button = wrap.querySelector('.acc-v2-more-btn');
  wrap.classList.add('open');
  button?.setAttribute('aria-expanded', 'true');
  positionAccountsV2MoreMenu(wrap);
}
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && $('#emailChangeModal')?.classList.contains('hidden') && !$('#accountDetailDrawer')?.classList.contains('hidden')) {
    closeAccountDetail();
  }
});
function accountRegistrationDriverLabel(value) {
  return ({
    roxy: 'roxy',
    roxy_oss: 'roxy-public',
    protocol: 'proto-local',
    protocol_oss: 'proto-public',
    protocol_oss_2: 'proto-sso',
    cloakbrowser: 'CloakBrowser（历史）',
  })[String(value || '').trim().toLowerCase()] || '未记录';
}
function _accountEmailInvalidBadge(r) {
  if (r.email_invalid !== true) return '';
  const detail = [r.email_invalid_reason || '该账号关联邮箱已标记失效', r.email_invalid_at ? `标记时间：${r.email_invalid_at}` : ''].filter(Boolean).join('；');
  return `<span class="pill status-failed account-email-invalid-badge" title="${esc(detail)}">邮箱失效</span>`;
}
function renderAccounts() {
  const openMoreId = getOpenAccountsV2MoreId();
  const total = ACCOUNTS_TOTAL;
  const rows = ACCOUNTS;
  const rowHtmlV2 = (r) => {
    const extractLink = _extractLinkCell(r);
    const codexSummary = r.codex_error || (['queued', 'running', 'cancelling'].includes(r.codex_execution_status) ? '授权处理中' : '');
    return `
    <tr>
      <td class="col-check"><input type="checkbox" class="account-row-check" data-account-id="${esc(r.id)}" ${ACCOUNT_SELECTED.has(Number(r.id)) ? 'checked' : ''}></td>
      <td class="col-id">#${esc(r.id)}</td>
      <td class="col-email" title="${esc([r.email || '-', r.user_name || ''].filter(Boolean).join(' · '))}">
        <button type="button" class="acc-v2-email-link account-cell-line" data-account-detail-id="${esc(r.id)}" title="查看账号详情">
          <span class="acc-v2-email">${esc(r.email)}${r.archived ? ' <span class="pill status-used" title="该账号已归档">归档</span>' : ''}</span>
        </button>
        <div class="acc-v2-sub account-cell-line account-cell-line--sub account-email-meta"><span class="account-email-name">${esc(r.user_name || '-')}</span>${_accountEmailInvalidBadge(r)}</div>
      </td>
      <td class="col-source">${esc(r.email_source || '-')}</td>
      <td class="col-registration-driver" title="${esc(accountRegistrationDriverLabel(r.registration_driver))}">${esc(accountRegistrationDriverLabel(r.registration_driver))}</td>
      <td class="col-token">${_tokenCellV2(r)}</td>
      <td class="col-account-status">${_accountStatusCellV2(r)}</td>
      <td class="col-small">${_passwordCellV2(r)}</td>
      <td class="col-plan"><div class="account-cell-lines"><div class="account-cell-line">${_planCell(r)}</div>${extractLink ? `<div class="account-cell-line account-cell-line--sub">${extractLink}</div>` : ''}</div></td>
      <td class="col-quota">${_quotaCell(r)}</td>
      <td class="col-trial">${_promotionCell(r)}</td>
      <td class="col-small">${_totpCellV2(r)}</td>
      <td class="col-risk-mail">${_deactivationMailCell(r)}</td>
      <td class="col-status"><div class="account-cell-lines"><div class="account-cell-line">${_codexCellV2(r)}</div>${codexSummary ? `<div class="account-cell-line account-cell-line--sub" title="${esc(codexSummary)}">${esc(short(codexSummary, 34))}</div>` : ''}</div></td>
      <td class="col-time">${_accountTimesCellV2(r)}</td>
      <td class="col-actions">
        <div class="account-cell-lines acc-v2-actions">
          <button type="button" class="danger" data-account-delete="${esc(r.id)}" data-email="${esc(r.email)}">删除</button>
          <div class="acc-v2-more" data-account-more-id="${esc(r.id)}">
            <button type="button" class="acc-v2-more-btn" data-acc-more-toggle aria-haspopup="true" aria-expanded="false">更多</button>
            <div class="acc-v2-more-menu" role="menu">${_accountsV2MoreMenu(r)}</div>
          </div>
        </div>
      </td>
    </tr>`;
  };

  const bodyV2 = $('#accountsBodyV2');
  if (bodyV2) {
    bodyV2.innerHTML = rows.map(rowHtmlV2).join('') || (accountSearchErrorQuery === accountAdvancedSearchQuery
      ? renderTableStateRow(16, '搜索条件有误', '请按输入框旁的提示修改，或清空高级搜索。', 'error')
      : renderTableStateRow(16, '暂无匹配账号', '可移除部分搜索条件，或切换活跃与归档账号视图。'));
    if (openMoreId) requestAnimationFrame(() => restoreAccountsV2MoreMenu(openMoreId));
  }
  const summary = $('#accountsPageSummary');
  if (summary) summary.textContent = `${total || 0} 个账号 · 当前页 ${rows.length} 条`;
  updateAccountSelectionUi(rows);
  _renderPager('accounts', total);
}

function updateAccountRowDensity() {
  const wrap = document.querySelector('#accountsPanelV2 > .accounts-table-v2-wrap');
  const table = wrap?.querySelector('table');
  if (!table || wrap.clientHeight <= 0) return;
  const minimum = window.matchMedia('(max-width: 860px)').matches ? 60 : 50;
  const available = wrap.clientHeight - (table.tHead?.getBoundingClientRect().height || 0) - 2;
  const height = Math.max(minimum, Math.min(56, Math.floor(available / 10)));
  table.style.setProperty('--account-row-height', `${height}px`);
}

(function bindAccountRowDensity() {
  const wrap = document.querySelector('#accountsPanelV2 > .accounts-table-v2-wrap');
  if (wrap && typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(updateAccountRowDensity).observe(wrap);
  }
  window.addEventListener('resize', updateAccountRowDensity);
})();

function updateAccountSelectionUi(pageRows = null) {
  for (const id of ACCOUNT_SELECTED_EMAILS.keys()) {
    if (!ACCOUNT_SELECTED.has(id)) ACCOUNT_SELECTED_EMAILS.delete(id);
  }
  const none = ACCOUNT_SELECTED.size === 0;
  const hintV2 = $('#accountsSelectedHintV2');
  const toolbarV2 = $('#accountsToolbarV2');
  toolbarV2?.classList.toggle('has-selection', !none);
  if (hintV2) hintV2.textContent = none ? '选择账号后批量操作' : `已选 ${ACCOUNT_SELECTED.size} 个账号`;

  const archiveLabel = SHOW_ARCHIVED_ACCOUNTS ? '恢复选中' : '归档选中';
  const archiveTitle = SHOW_ARCHIVED_ACCOUNTS ? '把选中的归档账号恢复到默认账号列表' : '归档选中的账号；默认账号列表将不再查询/显示这些账号';
  const v2Ids = [
    'btnCheckSelectedLiveV2', 'btnRefreshSelectedTokenV2', 'btnCheckSelectedPlansV2', 'btnEmailChangeSelectedV2', 'btnCheckSelectedDeactivationMailV2', 'btnExtractSelectedLinksV2',
    'btnSetupSelectedAccountsV2', 'btnAddPasswordSelectedAccountsV2', 'btnAddTwofaSelectedAccountsV2', 'btnChangePasswordSelectedAccountsV2', 'btnChangeTwofaSelectedAccountsV2', 'btnCompleteSelectedAccountsV2', 'btnUploadSelectedCodexSub2V2', 'btnRetrySelectedCodexV2', 'btnDownloadSelectedCpaV2', 'btnStopSelectedCodexV2',
    'btnCopySelectedTokensV2', 'btnCopySelectedLinesV2', 'btnCopySelectedEmailsV2',
    'btnCopySelectedExtractLinksV2',
    'btnCopySelectedPasswordsV2', 'btnCopySelectedTotpsV2',
    'btnDownloadSelectedTxtV2', 'btnDownloadSelectedSessionsV2', 'btnArchiveSelectedAccountsV2', 'btnDeleteSelectedAccountsV2',
    'btnMarkSelectedEmailInvalidV2', 'btnClearSelectedEmailInvalidV2',
  ];
  v2Ids.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.disabled = none || (id === 'btnDownloadSelectedSessionsV2' && accountSessionDownloadLoading);
    if (id === 'btnArchiveSelectedAccountsV2') {
      el.textContent = archiveLabel;
      el.title = archiveTitle;
    }
  });

  if (!pageRows) pageRows = ACCOUNTS;
  const pageIds = pageRows.map(r => Number(r.id));
  const checkedCount = pageIds.filter(id => ACCOUNT_SELECTED.has(id)).length;
  const cbAll = document.getElementById('accountsSelectAllV2');
  if (cbAll) {
    cbAll.checked = pageIds.length > 0 && checkedCount === pageIds.length;
    cbAll.indeterminate = checkedCount > 0 && checkedCount < pageIds.length;
    cbAll.disabled = pageIds.length === 0;
  }
}

// ---------- 查活日志面板 ----------
let liveLogEmail = null, liveLogTimer = null;

function openLiveLog(email) {
  liveLogEmail = email;
  $('#liveLogEmail').textContent = email;
  $('#liveLogPanel').classList.remove('hidden');
  updateModalScrollLock();
  $('#btnCloseLiveLog')?.focus({preventScroll:true});
  $('#liveLogContent').textContent = '加载中…';
  pollLiveLog();
  clearInterval(liveLogTimer);
  liveLogTimer = setInterval(pollLiveLog, 2000);
}
async function pollLiveLog() {
  if (!liveLogEmail) return;
  try {
    const r = await api(`/api/accounts/live-check-log?email=${encodeURIComponent(liveLogEmail)}`);
    const c = $('#liveLogContent');
    const atBottom = c.scrollTop + c.clientHeight >= c.scrollHeight - 30;
    c.textContent = r.log || '(暂无日志，等待任务写入…)';
    if (atBottom) c.scrollTop = c.scrollHeight;
    if (!r.running) {
      clearInterval(liveLogTimer);
      loadAccounts();
    }
  } catch(e) {}
}
$('#btnCloseLiveLog').addEventListener('click', closeLiveLogModal);

// 账号操作按钮（事件委托）
async function onAccountsBodyClick(e) {
  const detailBtn = e.target.closest('[data-account-detail-id]');
  if (detailBtn) {
    e.preventDefault();
    openAccountDetail(Number(detailBtn.dataset.accountDetailId));
    return;
  }
  const moreToggle = e.target.closest('[data-acc-more-toggle]');
  if (moreToggle) {
    e.preventDefault();
    e.stopPropagation();
    const wrap = moreToggle.closest('.acc-v2-more');
    if (!wrap) return;
    const willOpen = !wrap.classList.contains('open');
    closeAccountsV2MoreMenus();
    if (willOpen) {
      wrap.classList.add('open');
      moreToggle.setAttribute('aria-expanded', 'true');
      positionAccountsV2MoreMenu(wrap);
    }
    return;
  }
  if (e.target.closest('.acc-v2-more-menu')) {
    // 点菜单项后收起，再继续走下面的动作处理
    closeAccountsV2MoreMenus();
  }

  const emailChangeBtn = e.target.closest('[data-account-email-change]');
  if (emailChangeBtn) {
    openEmailChangeModal(Number(emailChangeBtn.dataset.accountEmailChange), emailChangeBtn);
    return;
  }

  const totpCopyBtn = e.target.closest('[data-account-totp-copy]');
  if (totpCopyBtn) {
    const id = Number(totpCopyBtn.dataset.accountTotpCopy);
    totpCopyBtn.disabled = true;
    totpCopyBtn.textContent = '查询中…';
    try {
      const result = await api(`/api/accounts/${encodeURIComponent(id)}/totp-code`);
      if (!result.code) throw new Error('验证码为空');
      const copied = await copyText(result.code, false);
      showToast(copied ? `验证码已复制，剩余 ${result.remaining_seconds || 0} 秒` : '验证码已查询，但复制失败');
    } catch(err) {
      showToast('复制验证码失败: ' + err.message);
    } finally {
      totpCopyBtn.disabled = false;
      totpCopyBtn.textContent = '复制';
    }
    return;
  }

  const copySecretBtn = e.target.closest('[data-account-copy-secret]');
  if (copySecretBtn) {
    const id = Number(copySecretBtn.dataset.accountId);
    const field = copySecretBtn.dataset.accountCopySecret;
    copySecretBtn.disabled = true;
    try {
      const value = await fetchOneAccountSecret(id, field);
      if (!value) { showToast('可复制内容为空'); return; }
      copyText(value);
      showToast(field === 'access_token' ? 'Token 已复制' : (field === 'account_password' ? '账号密码已复制' : (field === 'totp_secret' ? 'TOTP 密钥已复制' : (field === 'chatgpt_session' ? 'ChatGPT session 已复制' : '账号整行已复制'))));
    } catch(err) {
      showToast('复制失败: ' + err.message);
    } finally {
      copySecretBtn.disabled = false;
    }
    return;
  }

  const accountSetupBtn = e.target.closest('[data-account-setup]');
  if (accountSetupBtn) {
    const id = Number(accountSetupBtn.dataset.accountSetup);
    const row = ACCOUNTS.find(item => Number(item.id) === id);
    const email = row?.email || `账号 #${id}`;
    if (!confirm(`补齐账号配置？\n\n${email}\n\n只执行账号密码、套餐查询和 Authenticator 2FA，不执行 Codex 授权。`)) return;
    accountSetupBtn.disabled = true;
    try {
      const result = await api(`/api/accounts/${encodeURIComponent(id)}/setup`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: '{}',
      });
      showToast(result.message || '已开始补齐账号配置');
      loadAccounts();
      const search = $('#accountTaskTargetFilterV2');
      const typeFilter = $('#accountTaskTypeFilterV2');
      if (search) search.value = email;
      if (typeFilter) typeFilter.value = 'account_setup_retry';
      PAGERS.accountTasks.page = 1;
      activateTab('tasks');
    } catch(err) {
      showToast('补齐账号配置失败: ' + err.message);
      accountSetupBtn.disabled = false;
    }
    return;
  }

  const accountActionBtn = e.target.closest('[data-account-action]');
  if (accountActionBtn) {
    const id = Number(accountActionBtn.dataset.accountId);
    const action = String(accountActionBtn.dataset.accountAction || '').trim().toLowerCase();
    const row = ACCOUNTS.find(item => Number(item.id) === id);
    const email = row?.email || `账号 #${id}`;
    const labels = {password: '补密码', twofa: '补 2FA', password_change: '修改密码', twofa_change: '修改 2FA', complete: '补全账号'};
    if (!labels[action]) return;
    if (!confirm(`${labels[action]}？\n\n${email}`)) return;
    accountActionBtn.disabled = true;
    try {
      const result = await api(`/api/accounts/${encodeURIComponent(id)}/action`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action}),
      });
      showToast(result.message || `${labels[action]}已入队`);
      loadAccounts();
      const search = $('#accountTaskTargetFilterV2');
      const typeFilter = $('#accountTaskTypeFilterV2');
      if (search) search.value = email;
      if (typeFilter) typeFilter.value = result.registration_resume
        ? 'registration_resume'
        : ({password: 'password_setup', twofa: 'twofa_setup', password_change: 'password_change', twofa_change: 'twofa_change', complete: 'account_completion'})[action];
      PAGERS.accountTasks.page = 1;
      activateTab('tasks');
    } catch(err) {
      showToast(`${labels[action]}失败: ` + err.message);
      accountActionBtn.disabled = false;
    }
    return;
  }

  const planBtn = e.target.closest('[data-plan-check]');
  if (planBtn) {
    await checkOnePlan(Number(planBtn.dataset.planCheck), planBtn);
    return;
  }

  const riskMailBtn = e.target.closest('[data-deactivation-mail-check]');
  if (riskMailBtn) {
    await checkOneDeactivationMail(Number(riskMailBtn.dataset.deactivationMailCheck), riskMailBtn);
    return;
  }

  const liveBtn = e.target.closest('[data-account-live-check]');
  if (liveBtn) {
    await checkSelectedLive([Number(liveBtn.dataset.accountLiveCheck)], liveBtn);
    return;
  }

  const taskHistoryBtn = e.target.closest('[data-account-task-history]');
  if (taskHistoryBtn) {
    const search = $('#accountTaskTargetFilterV2');
    if (search) search.value = String(taskHistoryBtn.dataset.accountTaskHistory || '');
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
    return;
  }

  const delBtn = e.target.closest('[data-account-delete]');
  if (delBtn) {
    await deleteAccount(Number(delBtn.dataset.accountDelete), delBtn.dataset.email, delBtn);
    return;
  }

  const archiveBtn = e.target.closest('[data-account-archive]');
  if (archiveBtn) {
    await archiveOneAccount(Number(archiveBtn.dataset.accountArchive), archiveBtn.dataset.archived === '1', archiveBtn);
    return;
  }

  const restoreBtn = e.target.closest('[data-account-restore]');
  if (restoreBtn) {
    await restoreDeactivatedAccount(Number(restoreBtn.dataset.accountRestore), restoreBtn);
    return;
  }

  const emailInvalidBtn = e.target.closest('[data-account-email-invalid]');
  if (emailInvalidBtn) {
    await setAccountsEmailInvalid([Number(emailInvalidBtn.dataset.accountEmailInvalid)], emailInvalidBtn.dataset.invalid === '1', emailInvalidBtn);
    return;
  }

  const extractBtn = e.target.closest('[data-extract-link]');
  if (extractBtn) {
    await extractOneLink(Number(extractBtn.dataset.extractLink), extractBtn);
    return;
  }

  const qrBtn = e.target.closest('[data-qr-url]');
  if (qrBtn) {
    const url = qrBtn.dataset.qrUrl || '';
    if (!url) { showToast('二维码地址为空'); return; }
    openQrModal(url);
    return;
  }

  const stopCodexBtn = e.target.closest('[data-codex-stop]');
  if (stopCodexBtn) {
    const email = stopCodexBtn.dataset.codexStop;
    if (!confirm(`确定停止该账号的 Codex 补跑吗？\n\n${email}\n\n会发送停止信号并将状态标记为“已停止”。`)) return;
    stopCodexBtn.disabled = true;
    try {
      const r = await api('/api/codex/stop', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email}) });
      showToast(r.message || '已发送停止信号');
      loadAccounts();
    } catch(err) {
      showToast('停止失败: ' + err.message);
      stopCodexBtn.disabled = false;
    }
    return;
  }

  const resetBtn = e.target.closest('[data-codex-reset-retrying]');
  if (resetBtn) {
    const email = resetBtn.dataset.codexResetRetrying;
    if (!confirm(`确定重置该账号的 Codex「补跑中」状态吗？\n\n${email}\n\n重置后状态会变为“失败”，可再次点击“补跑 Codex”。`)) return;
    resetBtn.disabled = true;
    try {
      const r = await api('/api/codex/reset-retrying', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email, status:'failed'}) });
      showToast(r.message || '已重置补跑状态');
      loadAccounts();
    } catch(err) {
      showToast('重置失败: ' + err.message);
      resetBtn.disabled = false;
    }
    return;
  }

  const btn = e.target.closest('[data-codex-retry]');
  if (!btn) return;
  const email = btn.dataset.codexRetry;
  if (!confirm(`重新跑 Codex 授权？\n\n${email}\n\n将消耗：\n  • 1 封邮箱 OTP（自动收）\n  • 1 个接码短信（约 $0.13）\n\n补跑会在后台进行（~1-2 分钟），完成后状态自动更新。`)) return;
  btn.disabled = true;
  try {
    const r = await api('/api/codex/retry', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email}) });
    showToast(r.message || '已开始补跑');
    loadAccounts();
    const search = $('#accountTaskTargetFilterV2');
    const typeFilter = $('#accountTaskTypeFilterV2');
    if (search) search.value = email;
    if (typeFilter) typeFilter.value = 'codex_retry';
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
  } catch(err) {
    showToast('触发补跑失败: ' + err.message);
    btn.disabled = false;
  }
}
function onAccountsBodyChange(e) {
  const cb = e.target.closest('.account-row-check');
  if (!cb) return;
  const id = Number(cb.dataset.accountId);
  if (cb.checked) {
    ACCOUNT_SELECTED.add(id);
    const account = ACCOUNTS.find(item => Number(item.id) === id);
    if (account?.email) ACCOUNT_SELECTED_EMAILS.set(id, account.email);
  } else {
    ACCOUNT_SELECTED.delete(id);
    ACCOUNT_SELECTED_EMAILS.delete(id);
  }
  updateAccountSelectionUi();
}
function syncAccountsSelectAll(checked) {
  const pageRows = ACCOUNTS;
  if (checked) pageRows.forEach(r => { ACCOUNT_SELECTED.add(Number(r.id)); ACCOUNT_SELECTED_EMAILS.set(Number(r.id), r.email); });
  else pageRows.forEach(r => { ACCOUNT_SELECTED.delete(Number(r.id)); ACCOUNT_SELECTED_EMAILS.delete(Number(r.id)); });
  renderAccounts();
}
(function bindAccountsV2Events() {
  const bodyV2 = $('#accountsBodyV2');
  if (bodyV2) {
    bodyV2.addEventListener('click', onAccountsBodyClick);
    bodyV2.addEventListener('change', onAccountsBodyChange);
  }
  const selectAllV2 = $('#accountsSelectAllV2');
  if (selectAllV2) selectAllV2.addEventListener('change', (e) => syncAccountsSelectAll(e.target.checked));
  document.addEventListener('click', (e) => {
    if (e.target.closest('.acc-v2-more')) return;
    closeAccountsV2MoreMenus();
  });
  window.addEventListener('scroll', () => closeAccountsV2MoreMenus(), true);
  window.addEventListener('resize', () => closeAccountsV2MoreMenus());
})();
function setAccountsFilterToggle(el, on) {
  if (!el) return;
  el.classList.toggle('is-active', !!on);
  el.setAttribute('aria-pressed', on ? 'true' : 'false');
}
async function applyAccountsArchivedFilter(on) {
  SHOW_ARCHIVED_ACCOUNTS = !!on;
  setAccountsFilterToggle($('#showArchivedAccountsV2'), SHOW_ARCHIVED_ACCOUNTS);
  ACCOUNT_SELECTED.clear();
  PAGERS.accounts.page = 1;
  await loadAccounts();
  await pollAccountPlanStatuses();
}
async function applyAccountsPlusFilter(on) {
  SHOW_PLUS_ACCOUNTS_ONLY = !!on;
  setAccountsFilterToggle($('#showPlusAccountsOnlyV2'), SHOW_PLUS_ACCOUNTS_ONLY);
  ACCOUNT_SELECTED.clear();
  PAGERS.accounts.page = 1;
  await loadAccounts();
  await pollAccountPlanStatuses();
}
async function refreshAccountsList(btn) {
  if (!btn) return;
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '刷新中…';
  try {
    planStatusRevision = '';
    await loadAccounts();
    await pollAccountPlanStatuses();
    loadSummary();
    showToast('账号列表已刷新');
  } catch(e) {
    showToast('刷新账号失败: ' + e.message);
  } finally {
    btn.textContent = old;
    btn.disabled = false;
  }
}
(function bindAccountsFilterV2() {
  let timer = null;
  let composing = false;
  const search = $('#accountAdvancedSearchV2');
  const clearSearch = $('#btnClearAccountSearchV2');
  const syncSearch = () => { if (clearSearch) clearSearch.hidden = !search?.value; };
  const apply = () => {
    clearTimeout(timer);
    accountAdvancedSearchQuery = search?.value.trim() || '';
    accountSearchErrorQuery = null;
    showAccountSearchError();
    renderAccountSearchTerms([]);
    ACCOUNT_SELECTED.clear();
    updateAccountSelectionUi();
    PAGERS.accounts.page = 1;
    loadAccounts();
  };
  const reload = () => { clearTimeout(timer); timer = setTimeout(apply, 250); };
  search?.addEventListener('compositionstart', () => { composing = true; clearTimeout(timer); });
  search?.addEventListener('compositionend', () => { composing = false; syncSearch(); reload(); });
  search?.addEventListener('input', event => {
    syncSearch();
    if (!composing && !event.isComposing) reload();
  });
  const resetSearch = () => {
    if (!search) return;
    search.value = '';
    composing = false;
    syncSearch();
    apply();
    search.focus();
  };
  search?.addEventListener('keydown', event => {
    if (composing || event.isComposing || event.keyCode === 229) return;
    if (event.key === 'Enter') { event.preventDefault(); apply(); }
    if (event.key === 'Escape') { event.preventDefault(); resetSearch(); }
  });
  clearSearch?.addEventListener('click', resetSearch);
  $('#accountSearchSummaryV2')?.addEventListener('click', event => {
    const button = event.target.closest('[data-account-search-term]');
    const term = button && accountSearchTerms[Number(button.dataset.accountSearchTerm)];
    if (!term || !search || composing) return;
    search.value = term.query_without;
    syncSearch();
    apply();
    search.focus();
  });
  syncSearch();
  ['accountIdFilterV2','qAccountsV2'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', reload);
  });
  ['accountSourceFilterV2','accountRegistrationDriverFilterV2','accountTokenFilterV2','accountStatusFilterV2','accountEmailStatusFilterV2','accountPasswordFilterV2','accountPlanFilterV2','accountTrialFilterV2','accountTotpFilterV2','accountRiskFilterV2','accountCodexFilterV2','dateFromAccountsV2','dateToAccountsV2'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', reload);
  });

  const archivedV2 = $('#showArchivedAccountsV2');
  if (archivedV2) archivedV2.addEventListener('click', () => {
    applyAccountsArchivedFilter(!SHOW_ARCHIVED_ACCOUNTS);
  });
  const refreshV2 = $('#btnRefreshAccountsV2');
  if (refreshV2) refreshV2.addEventListener('click', () => refreshAccountsList(refreshV2));
  $('#btnResetAccountFiltersV2')?.addEventListener('click', () => {
    ['accountAdvancedSearchV2','accountIdFilterV2','qAccountsV2','accountSourceFilterV2','accountRegistrationDriverFilterV2','accountTokenFilterV2','accountStatusFilterV2','accountEmailStatusFilterV2','accountPasswordFilterV2','accountPlanFilterV2','accountTrialFilterV2','accountTotpFilterV2','accountRiskFilterV2','accountCodexFilterV2','dateFromAccountsV2','dateToAccountsV2'].forEach(id => {
      setColumnFilterValue(document.getElementById(id), '');
    });
    syncSearch(); refreshColumnFilterStates(); apply();
  });
})();


async function fetchAccountSecrets(ids, field) {
  const r = await api('/api/accounts/secret-bulk', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({account_ids: ids, field}),
  });
  return (r.values || []).map(x => x.value).filter(Boolean);
}

async function fetchOneAccountSecret(id, field) {
  const r = await api(`/api/accounts/${encodeURIComponent(id)}/secret?field=${encodeURIComponent(field)}`);
  return r.value || '';
}

async function copySelectedAccountLines() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  try {
    const lines = await fetchAccountSecrets(ids, 'copy_line');
    if (!lines.length) { showToast('选中账号没有可复制整行'); return; }
    copyText(lines.join('\n'));
    showToast(`已复制 ${lines.length} 行`);
  } catch(err) { showToast('复制失败: ' + err.message); }
}

async function copySelectedAccountExtractLinks() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  const links = ACCOUNTS
    .filter(r => ids.includes(Number(r.id)))
    .filter(r => String(r.extract_link_status || '').toLowerCase() === 'success' || r.extract_link_ok === true)
    .map(r => r.extract_link_long_url || r.extract_link_copy_paste || '')
    .map(value => String(value).trim())
    .filter(Boolean);
  if (!links.length) { showToast('选中账号没有成功提炼地址'); return; }
  const copied = await copyText(links.join('\n'), false);
  showToast(copied ? `已复制 ${links.length} 个提炼地址` : '复制提炼地址失败');
}

async function copySelectedAccountPasswords() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  try {
    const lines = await fetchAccountSecrets(ids, 'account_password_line');
    if (!lines.length) { showToast('选中账号均未设置密码'); return; }
    copyText(lines.join('\n'));
    showToast(`已复制 ${lines.length} 个账号密码；未设置密码的账号已跳过`);
  } catch(err) { showToast('复制密码失败: ' + err.message); }
}

async function copySelectedAccountTotpSecrets() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  try {
    const lines = await fetchAccountSecrets(ids, 'totp_secret');
    if (!lines.length) { showToast('选中账号没有已设置的 2FA 密钥'); return; }
    copyText(lines.join('\n'));
    showToast(`已复制 ${lines.length} 个 2FA 密钥；未设置 2FA 的账号已跳过`);
  } catch(err) { showToast('复制 2FA 失败: ' + err.message); }
}

function bindDateFilterPanel({ btnId, panelId, fromId, toId, onApply }) {
  const btn = document.getElementById(btnId);
  const panel = document.getElementById(panelId);
  if (!btn || !panel) return;
  const wrap = panel.closest('.acc-v2-date-select');
  const now = new Date();
  let viewY = now.getFullYear();
  let viewM = now.getMonth();
  let start = document.getElementById(fromId)?.value || '';
  let end = document.getElementById(toId)?.value || '';
  let openSnapshot = { start, end };
  let dirty = false;
  if (start) { const d = new Date(start); viewY = d.getFullYear(); viewM = d.getMonth(); }
  const fmt = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const setHidden = () => {
    const f = document.getElementById(fromId); if (f) f.value = start;
    const t = document.getElementById(toId); if (t) t.value = end;
  };
  const syncBtnText = () => {
    btn.textContent = (start || end) ? `📅 ${start || '…'} ~ ${end || '…'}` : '📅 日期筛选';
  };
  const close = () => {
    if (wrap) wrap.classList.remove('open');
    else panel.classList.remove('open');
    // 只选了开始/结束其中一端就关闭 → 还原到打开前的完整状态，避免留下残缺筛选
    if (dirty && !(start && end)) {
      start = openSnapshot.start;
      end = openSnapshot.end;
      setHidden();
      syncBtnText();
    }
    dirty = false;
  };

  const render = () => {
    const y = viewY, m = viewM;
    const firstDay = new Date(y, m, 1);
    const dim = new Date(y, m + 1, 0).getDate();
    const lead = firstDay.getDay();
    const cells = [];
    for (let i = lead - 1; i >= 0; i--) cells.push({ d: new Date(y, m, -i), other: true });
    for (let day = 1; day <= dim; day++) cells.push({ d: new Date(y, m, day), other: false });
    let tail = 1;
    while (cells.length % 7 !== 0) cells.push({ d: new Date(y, m + 1, tail++), other: true });
    panel.innerHTML = `
      <div class="cal">
        <div class="cal-head">
          <button type="button" class="cal-nav" data-cal-nav="-1" title="上个月">‹</button>
          <span class="cal-title">${y}年${m + 1}月</span>
          <button type="button" class="cal-nav" data-cal-nav="1" title="下个月">›</button>
        </div>
        <div class="cal-week">${['日', '一', '二', '三', '四', '五', '六'].map(w => `<span>${w}</span>`).join('')}</div>
        <div class="cal-grid">
          ${cells.map(({ d, other }) => {
            const ds = fmt(d);
            const cls = ['cal-cell'];
            if (other) cls.push('other');
            if (start && end && ds > start && ds < end) cls.push('in-range');
            if (ds === start || ds === end) cls.push(ds === start && ds === end ? 'start end' : (ds === start ? 'start' : 'end'));
            return `<button type="button" class="${cls.join(' ')}" data-date="${ds}" data-other="${other ? 1 : 0}">${d.getDate()}</button>`;
          }).join('')}
        </div>
        <div class="cal-foot">
          <div class="cal-foot-btns">
            <button type="button" class="jobs-tb-btn" data-quick-date="today">今天</button>
            <button type="button" class="jobs-tb-btn" data-quick-date="yesterday">昨天</button>
            <button type="button" class="jobs-tb-btn" data-quick-date="3d">近3天</button>
            <button type="button" class="jobs-tb-btn" data-quick-date="7d">近7天</button>
          </div>
          <div class="cal-foot-tip">双击某个日期，只看当天</div>
        </div>
      </div>`;
    panel.querySelectorAll('[data-cal-nav]').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      viewM += Number(b.dataset.calNav);
      if (viewM < 0) { viewM = 11; viewY--; }
      if (viewM > 11) { viewM = 0; viewY++; }
      render();
    }));
    panel.querySelectorAll('[data-date]').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      const ds = b.dataset.date;
      if (b.dataset.other === '1') {
        const d = new Date(ds);
        viewY = d.getFullYear(); viewM = d.getMonth();
      }
      dirty = true;
      if (!start || (start && end)) { start = ds; end = ''; }
      else { end = ds; if (end < start) [start, end] = [end, start]; }
      setHidden();
      syncBtnText();
      if (start && end) { close(); if (onApply) onApply(); }
      else render();
    }));
    panel.querySelectorAll('[data-date]').forEach(b => b.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      start = b.dataset.date;
      end = start;
      dirty = false;
      setHidden();
      syncBtnText();
      close();
      if (onApply) onApply();
    }));
    panel.querySelectorAll('[data-quick-date]').forEach(b => b.addEventListener('click', (e) => {
      e.stopPropagation();
      const en = new Date();
      const st = new Date();
      const k = b.dataset.quickDate;
      if (k === 'yesterday') { st.setDate(st.getDate() - 1); en.setDate(en.getDate() - 1); }
      else if (k === '3d') st.setDate(st.getDate() - 2);
      else if (k === '7d') st.setDate(st.getDate() - 6);
      start = fmt(st); end = fmt(en);
      dirty = false;
      setHidden(); syncBtnText(); close(); if (onApply) onApply();
    }));
  };

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const willOpen = wrap ? !wrap.classList.contains('open') : !panel.classList.contains('open');
    close();
    if (willOpen) {
      openSnapshot = { start, end };
      dirty = false;
      if (wrap) wrap.classList.add('open');
      render();
    }
  });
  document.addEventListener('click', (e) => {
    if (e.target.closest(`#${btnId}, #${panelId}`)) return;
    close();
  });
  syncBtnText();
}

function copySelectedAccountEmails() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  const emails = ACCOUNTS
    .filter(r => ids.includes(Number(r.id)))
    .map(r => (r.email || '').trim())
    .filter(Boolean);
  if (!emails.length) { showToast('选中账号没有可复制的邮箱'); return; }
  copyText(emails.join('\n'));
  showToast(`已复制 ${emails.length} 个邮箱`);
}

async function downloadSelectedAccountTxt() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  let lines = [];
  try {
    lines = await fetchAccountSecrets(ids, 'copy_line');
  } catch(err) { showToast('生成 TXT 失败: ' + err.message); return; }
  if (!lines.length) { showToast('选中账号没有可下载整行'); return; }
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const filename = `accounts-selected-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.txt`;
  const blob = new Blob(['\ufeff' + lines.join('\n') + '\n'], {type: 'text/plain;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 800);
  showToast(`已下载 ${lines.length} 个账号 TXT`);
}

async function downloadSelectedAccountSessions() {
  if (accountSessionDownloadLoading) return;
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  const btn = $('#btnDownloadSelectedSessionsV2');
  const old = btn?.textContent || '下载 Session';
  accountSessionDownloadLoading = true;
  if (btn) { btn.disabled = true; btn.textContent = '打包中…'; }
  try {
    const r = await api('/api/accounts/download-session-bulk', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({account_ids: ids, prepare: true}),
    });
    if (!r.download_url) throw new Error('服务端未返回下载地址');
    const a = document.createElement('a');
    a.href = r.download_url;
    a.download = r.filename || '';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 1000);
    const addedCount = Number(r.added_count || 0);
    const skippedCount = Number(r.skipped_count || 0);
    if (addedCount === 0) {
      showToast(`没有可下载的 Session，已生成结果清单，跳过 ${skippedCount} 个；开始下载，分类原因见 ZIP 内 manifest.json；Session 缺失或无效的账号请先刷新 AT，读取失败的账号请重试`);
    } else {
      showToast(`已打包 ${addedCount} 个账号 Session，跳过 ${skippedCount} 个；开始下载，结果见 ZIP 内 manifest.json`);
    }
  } catch (err) {
    showToast('下载 Session 失败: ' + err.message);
  } finally {
    accountSessionDownloadLoading = false;
    if (btn) btn.textContent = old;
    updateAccountSelectionUi();
  }
}

async function downloadSelectedCpa() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const selectedAccounts = ids.map(id => ACCOUNTS.find(a => Number(a.id) === Number(id))).filter(Boolean);
  const missingCodex = selectedAccounts.filter(a => (a.codex_status || '') !== 'success').length;
  let msg = `确定从 CPA 下载选中的 ${ids.length} 个账号的 CPA/Codex JSON 吗？\n\n会按账号邮箱匹配 CPA auth-files，成功的文件会打包成 ZIP。`;
  if (missingCodex) msg += `\n\n其中 ${missingCodex} 个账号本地 Codex 状态不是 success，若 CPA 端没有文件会写入 manifest 错误清单。`;
  if (!confirm(msg)) return;
  const btn = $('#btnDownloadSelectedCpaV2');
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '下载中…';
  try {
    // 先由服务端准备 ZIP，再用同源 GET 顶层下载。
    // 这样比隐藏 iframe / blob URL 更像普通用户点击下载，Chrome 不容易挂起或标记“不安全下载”。
    const r = await api('/api/accounts/download-cpa-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids, prepare: true}),
    });
    if (!r.download_url) throw new Error('服务端未返回下载地址');
    const a = document.createElement('a');
    a.href = r.download_url;
    a.download = r.filename || '';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 1000);
    showToast(`已生成 ZIP，开始下载${r.error_count ? `（${r.error_count} 个失败见 manifest）` : ''}`);
    setTimeout(loadCodex, 1200);
  } catch(err) {
    showToast('下载 CPA 失败: ' + err.message);
  } finally {
    setTimeout(() => {
      btn.textContent = old;
      updateAccountSelectionUi();
    }, 1200);
  }
}

async function checkOnePlan(id, btn) {
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '查询中…';
  try {
    const r = await api('/api/accounts/check-plan', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_id: id}),
    });
    showToast(r.message || '套餐查询已加入后台队列');
    await pollAccountPlanStatuses();
  } catch(err) {
    showToast(err.message);
    await pollAccountPlanStatuses();
    btn.disabled = false;
    btn.textContent = old;
  }
}

async function extractOneLink(id, btn) {
  const acc = ACCOUNTS.find(a => Number(a.id) === Number(id));
  if (!acc) { showToast('账号不存在'); return; }
  const plan = (acc.current_plan_type || acc.plan_type || '').toString().toLowerCase();
  if (plan !== 'free' || !_isFreeTrialPromotion(acc)) {
    showToast('仅支持已确认 Plus 免费试用资格的 free 账号提链；折扣优惠不支持');
    return;
  }
  if (!confirm(`确定为该账号提链吗？\n\n${acc.email || ('#' + id)}\n\n提链类型按配置使用，成功会消耗 1 次 CDK。`)) return;
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '提链中…';
  try {
    const queued = await api('/api/accounts/extract-link', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_id: id}),
    });
    const fallback = queued.fallback_from && queued.link_type
      ? `；${String(queued.fallback_from).toUpperCase()} 已失败，改用 ${String(queued.link_type).toUpperCase()}`
      : '';
    showToast(`提炼任务已入队${queued.task_id ? ` · 任务 #${queued.task_id}` : ''}${fallback}，可在任务中心查看日志`);
    loadAccountTasks();
    await pollAccountPlanStatuses();
  } catch(err) {
    showToast('提链失败: ' + err.message);
    btn.disabled = false;
    btn.textContent = old;
  }
}

async function extractSelectedLinks() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const selected = ids.map(id => ACCOUNTS.find(a => Number(a.id) === Number(id))).filter(Boolean);
  const eligible = selected.filter(a => !accountIsDeactivated(a) && (a.current_plan_type || a.plan_type || '').toString().toLowerCase() === 'free' && _isFreeTrialPromotion(a));
  if (!eligible.length) { showToast('选中账号里没有已确认的 Plus 免费试用账号'); return; }
  if (!confirm(`确定批量提链 ${eligible.length} 个 Plus 免费试用账号吗？\n\n折扣优惠和历史待复查账号会自动跳过。成功会按账号消耗 CDK 次数。`)) return;
  const btn = $('#btnExtractSelectedLinksV2');
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '提链中…';
  try {
    const r = await api('/api/accounts/extract-link-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: eligible.map(a => a.id)}),
    });
    const skipped = (r.skipped_count || 0) + (r.busy_count || 0) + (r.failed_count || 0);
    const fallbackCount = (r.started || []).filter(item => item.fallback_from).length;
    const fallbackText = fallbackCount ? `，其中 ${fallbackCount} 个已自动跳过失败类型` : '';
    showToast(skipped ? `已入队 ${r.started_count || 0} 个，跳过/失败 ${skipped} 个${fallbackText}` : `已入队 ${r.started_count || 0} 个${fallbackText}`);
    loadAccountTasks();
    await pollAccountPlanStatuses();
  } catch(err) {
    showToast('批量提链失败: ' + err.message);
    updateAccountSelectionUi();
  } finally {
    btn.textContent = old;
  }
}

async function uploadSelectedCodexSub2() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const selected = ids.map(id => ACCOUNTS.find(a => Number(a.id) === Number(id))).filter(Boolean);
  const ready = selected.filter(a => (a.codex_status || '') === 'success');
  if (!ready.length) { showToast('选中账号里没有已通过的 Codex OAuth 凭证'); return; }
  if (!confirm(`确定上传选中的 ${ready.length} 个 Codex OAuth 凭证到 sub2api 吗？\n\n未完成 Codex OAuth 的账号会自动跳过。`)) return;
  const btn = $('#btnUploadSelectedCodexSub2V2');
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '上传中…';
  try {
    const r = await api('/api/accounts/codex/upload-sub2-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
    });
    const skipped = (r.skipped_count || 0) + (r.failed_count || 0);
    showToast(skipped ? `已上传 ${r.uploaded_count || 0} 个，跳过/失败 ${skipped} 个` : `已上传 ${r.uploaded_count || 0} 个`);
    await pollAccountPlanStatuses();
  } catch(err) {
    showToast('批量上传 sub2 失败: ' + err.message);
    updateAccountSelectionUi();
  } finally {
    btn.textContent = old;
  }
}

async function checkSelectedPlans() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const eligibleIds = ids.filter(id => {
    const account = ACCOUNTS.find(item => Number(item.id) === Number(id));
    return account && !accountIsDeactivated(account);
  });
  if (!eligibleIds.length) { showToast('选中账号均已废号'); return; }
  const btn = $('#btnCheckSelectedPlansV2');
  if (!btn) return;
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '查询中…';
  try {
    const r = await api('/api/accounts/check-plan-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: eligibleIds}),
    });
    const failed = r.failed_count || 0;
    const busy = r.busy_count || 0;
    showToast(`已入队 ${r.started_count || 0} 个，查询中跳过 ${busy} 个，入队失败 ${failed} 个`);
    await pollAccountPlanStatuses();
  } catch(err) {
    showToast('批量查询失败: ' + err.message);
    updateAccountSelectionUi();
  } finally {
    btn.textContent = old;
  }
}

async function _pollDeactivationMailResults(ids, attempts = 30) {
  const wanted = new Set((ids || []).map(Number));
  for (let i = 0; i < attempts; i += 1) {
    await new Promise(resolve => setTimeout(resolve, 1500));
    await loadAccounts();
    const visible = ACCOUNTS.filter(a => wanted.has(Number(a.id)));
    if (visible.length && visible.every(a => !['queued','running'].includes(a.deactivation_mail_scan_status || ''))) return;
  }
}

async function checkOneDeactivationMail(id, btn) {
  const old = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '扫描中…'; }
  try {
    await api(`/api/accounts/${encodeURIComponent(id)}/check-deactivation-mail`, { method:'POST' });
    showToast('封号邮件扫描已入队；不会刷新 AT');
    await loadAccounts();
    await _pollDeactivationMailResults([id]);
  } catch(err) {
    showToast('扫描失败: ' + err.message);
  } finally {
    if (btn && btn.isConnected) { btn.disabled = false; btn.textContent = old; }
  }
}

async function checkSelectedDeactivationMail() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (!ids.length) { showToast('请先选择账号'); return; }
  const eligible = ids.filter(id => {
    const acc = ACCOUNTS.find(a => Number(a.id) === Number(id));
    return acc && ['email_butler','cloudflare','icloud_hide'].includes((acc.email_source || '').toString().toLowerCase());
  });
  if (!eligible.length) { showToast('选中账号中没有支持扫描的邮箱来源'); return; }
  const btn = $('#btnCheckSelectedDeactivationMailV2');
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '扫描中…';
  try {
    const r = await api('/api/accounts/check-deactivation-mail-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: eligible}),
    });
    showToast(`已入队 ${r.started_count || 0} 个，跳过 ${r.skipped_count || 0} 个；不会刷新 AT`);
    await loadAccounts();
    if ((r.started_count || 0) > 0) await _pollDeactivationMailResults(eligible);
  } catch(err) {
    showToast('批量扫描失败: ' + err.message);
  } finally {
    btn.textContent = old;
    updateAccountSelectionUi();
  }
}

function accountBulkQueueReasons(result) {
  const reasons = [...(result.skipped || []), ...(result.failed || [])]
    .map(item => String(item.reason || item.error || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  if (!reasons.length) return '';
  const details = reasons.slice(0, 3).map(reason => reason.length > 80 ? `${reason.slice(0, 80)}…` : reason);
  return `；${details.join('；')}${reasons.length > 3 ? `；另有 ${reasons.length - 3} 条原因` : ''}`;
}

async function checkSelectedLive(idsArg = null, btnArg = null) {
  const ids = idsArg || Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const workers = getAccountOperationWorkers();
  const msg = idsArg ? `确定查活这个账号吗？

只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。` : `确定查活选中的 ${ids.length} 个账号吗？

只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。

并发线程数：${workers}`;
  if (!confirm(msg)) return;
  const btn = btnArg || $('#btnCheckSelectedLiveV2');
  const old = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = '查活中…';
  }
  try {
    const r = await api('/api/accounts/check-live-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids, driver: configuredLiveCheckDriver()}),
    });
    const skipped = (r.skipped || []).length;
    const configuredDriver = configuredLiveCheckDriver() || '默认';
    const effectiveDriver = r.live_check_driver || '未知';
    showToast(`查活已入队 ${r.started_count || 0} 个，忙碌 ${r.busy_count || 0} 个，失败 ${r.failed_count || 0}${skipped ? `，跳过 ${skipped}` : ''}（配置驱动：${configuredDriver}，实际驱动：${effectiveDriver}）${accountBulkQueueReasons(r)}`);
    const firstStarted = (r.started || [])[0];
    if (firstStarted?.email) openLiveLog(firstStarted.email);
    await loadAccounts();
    loadSummary();
  } catch(err) {
    showToast('查活失败: ' + err.message);
    updateAccountSelectionUi();
  } finally {
    if (btn) {
      btn.textContent = old;
      btn.disabled = false;
    }
  }
}

async function refreshSelectedToken(idsArg = null, btnArg = null) {
  const ids = idsArg || Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const workers = getAccountOperationWorkers();
  const btn = btnArg || $('#btnRefreshSelectedTokenV2');
  if (btn?.disabled) return;
  const old = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '读取配置…'; }
  try {
    const settings = await loadAccountAtRefreshUiSettings();
    const scope = ids.length === 1 ? '这个账号' : `选中的 ${ids.length} 个账号`;
    const msg = `确定刷新${scope}的 AT 吗？\n\n${settings.description}${settings.debugDescription ? `\n\n${settings.debugDescription}` : ''}${ids.length > 1 ? `\n\n并发线程数：${workers}` : ''}`;
    if (!confirm(msg)) return;
    if (btn) btn.textContent = '刷新中…';
    const r = await api('/api/accounts/refresh-token-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
    });
    const skipped = (r.skipped || []).length;
    showToast(`刷新AT已入队 ${r.started_count || 0} 个，忙碌 ${r.busy_count || 0} 个，失败 ${r.failed_count || 0}${skipped ? `，跳过 ${skipped}` : ''}${accountBulkQueueReasons(r)}`);
    const firstStarted = (r.started || [])[0];
    if (firstStarted?.task_id) openAccountTaskLog(firstStarted.task_id, firstStarted.run_id || null);
    else if (firstStarted?.email) openLiveLog(firstStarted.email);
    await loadAccounts();
    loadSummary();
  } catch(err) {
    showToast('刷新AT失败: ' + err.message);
    updateAccountSelectionUi();
  } finally {
    if (btn) { btn.textContent = old; btn.disabled = false; }
  }
}

async function deleteAccount(id, email, btn) {
  if (!confirm(`确定删除账号 #${id}？\n\n${email || ''}\n\n会从本地账号列表、注册成功邮箱和 token 文件中移除。`)) return;
  btn.disabled = true;
  try {
    await api(`/api/accounts/${id}/delete`, { method:'POST', headers:{'Content-Type':'application/json'}, body: '{}' });
    ACCOUNT_SELECTED.delete(Number(id));
    showToast('账号已删除');
    loadAccounts(); loadSummary();
  } catch(err) {
    showToast('删除失败: ' + err.message);
    btn.disabled = false;
  }
}

async function setAccountsEmailInvalid(idsArg = null, invalid = true, btn = null) {
  if (btn?.disabled) return;
  const ids = [...new Set((idsArg || Array.from(ACCOUNT_SELECTED)).map(Number))];
  if (!ids.length) { showToast('请先选择账号'); return; }
  if (ids.length > 500) { showToast('单次最多操作 500 个账号'); return; }
  const expectedEmails = {};
  for (const id of ids) {
    const email = ACCOUNTS.find(item => Number(item.id) === id)?.email || ACCOUNT_SELECTED_EMAILS.get(id);
    if (!email) { showToast('部分账号缺少邮箱快照，请重新勾选后操作'); return; }
    expectedEmails[id] = email;
  }
  let reason = '';
  if (invalid) {
    const input = prompt(`为 ${ids.length} 个账号标记邮箱失效，请填写原因（最多 300 字）`, '用户确认邮箱失效');
    if (input === null) return;
    reason = input.trim() || '用户确认邮箱失效';
    if (reason.length > 300) { showToast('邮箱失效原因最多 300 字'); return; }
  } else if (!confirm(`确定解除 ${ids.length} 个账号的邮箱失效标记？\n\n仅清除本地标记，邮箱可用性仍需确认。`)) return;
  const old = btn?.textContent || '';
  if (btn) { btn.disabled = true; btn.textContent = '更新中…'; }
  try {
    const result = await api('/api/accounts/email-invalid-bulk', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({account_ids: ids, invalid, reason, expected_emails: expectedEmails}),
    });
    const skipped = (result.skipped || []).length;
    showToast(`${invalid ? '已标记邮箱失效' : '已清除本地邮箱失效标记'} ${Number(result.updated_count || 0)} 个${skipped ? `，跳过 ${skipped} 个（邮箱可能已变更）` : ''}`);
    await loadAccounts();
  } catch (error) {
    showToast('更新邮箱失效标记失败: ' + error.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = old; }
    updateAccountSelectionUi();
  }
}

async function restoreDeactivatedAccount(id, btn) {
  if (btn?.disabled) return;
  const account = ACCOUNTS.find(item => Number(item.id) === Number(id));
  if (!accountIsDeactivated(account)) {
    showToast('当前账号没有本地停用标记，无需恢复');
    return;
  }
  if (!confirm(`确定恢复账号 #${id}？\n\n已确认 OpenAI 恢复访问权限后，解除本地停用标记；历史封禁记录保留，AT 和 Codex 凭证需要重新验证。`)) return;
  const old = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '恢复中…'; }
  try {
    const result = await api(`/api/accounts/${encodeURIComponent(id)}/restore`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({reason: '已收到 OpenAI 恢复访问通知'}),
    });
    showToast(result.message || '已解除本地停用标记，请刷新 AT 重新验证');
    await loadAccounts();
    await loadSummary();
  } catch(err) {
    showToast('恢复账号失败: ' + err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = old; }
  }
}

async function archiveOneAccount(id, archived, btn) {
  const acc = ACCOUNTS.find(a => Number(a.id) === Number(id));
  const email = acc?.email || '';
  const action = archived ? '归档' : '恢复';
  if (!confirm(`确定${action}账号 #${id}？\n\n${email}\n\n${archived ? '归档后默认账号列表不会查询/显示它，可勾选“查看归档”单独查看。' : '恢复后会回到默认账号列表。'}`)) return;
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = `${action}中…`;
  try {
    await api(`/api/accounts/${id}/archive`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({archived}),
    });
    ACCOUNT_SELECTED.delete(Number(id));
    showToast(archived ? '账号已归档' : '账号已恢复');
    loadAccounts(); loadSummary();
  } catch(err) {
    showToast(`${action}失败: ` + err.message);
    btn.disabled = false;
    btn.textContent = old;
  }
}

async function archiveSelectedAccounts() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const archived = !SHOW_ARCHIVED_ACCOUNTS;
  const action = archived ? '归档' : '恢复';
  if (!confirm(`确定${action}选中的 ${ids.length} 个账号吗？\n\n${archived ? '归档后默认账号列表不会查询/显示这些账号，可勾选“查看归档”单独查看。' : '恢复后这些账号会回到默认账号列表。'}`)) return;
  const btn = $('#btnArchiveSelectedAccountsV2');
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = `${action}中…`;
  try {
    const r = await api('/api/accounts/archive-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids, archived}),
    });
    (r.updated || []).forEach(item => ACCOUNT_SELECTED.delete(Number(item.id)));
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已${action} ${r.updated_count || 0} 个，跳过 ${skippedCount} 个` : `已${action} ${r.updated_count || 0} 个`);
    loadAccounts(); loadSummary();
  } catch(err) {
    showToast(`批量${action}失败: ` + err.message);
    updateAccountSelectionUi();
  } finally {
    btn.textContent = old;
  }
}

async function deleteSelectedAccounts() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  if (!confirm(`确定删除选中的 ${ids.length} 个账号吗？\n\n会从本地账号列表、注册成功邮箱和 token 文件中移除。`)) return;
  const _delBtn = $('#btnDeleteSelectedAccountsV2'); if (_delBtn) _delBtn.disabled = true;
  try {
    const r = await api('/api/accounts/delete-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
    });
    (r.deleted || []).forEach(item => ACCOUNT_SELECTED.delete(Number(item.id)));
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已删除 ${r.deleted_count || 0} 个，跳过 ${skippedCount} 个` : `已删除 ${r.deleted_count || 0} 个`);
    loadAccounts(); loadSummary();
  } catch(err) {
    showToast('批量删除失败: ' + err.message);
    updateAccountSelectionUi();
  }
}

async function stopSelectedCodex() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const selectedAccounts = ids.map(id => ACCOUNTS.find(a => Number(a.id) === Number(id))).filter(Boolean);
  const retrying = selectedAccounts.filter(a => ['queued','running','cancelling'].includes(a.codex_execution_status || '') || (a.codex_status || '') === 'retrying');
  if (retrying.length === 0) { showToast('选中账号里没有正在补跑的 Codex'); return; }
  if (!confirm(`确定停止选中的 ${retrying.length} 个 Codex 补跑吗？\n\n会发送停止信号，并将状态标记为“已停止”。`)) return;
  const btn = $('#btnStopSelectedCodexV2');
  if (!btn) return;
  btn.disabled = true;
  try {
    const r = await api('/api/codex/stop-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: retrying.map(a => a.id)}),
    });
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已停止 ${r.stopped_count || 0} 个，跳过 ${skippedCount} 个` : `已停止 ${r.stopped_count || 0} 个`);
    loadAccounts();
  } catch(err) {
    showToast('停止选中补跑失败: ' + err.message);
    updateAccountSelectionUi();
  }
}

async function retrySelectedCodex() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const workers = getAccountOperationWorkers();
  const selectedAccounts = ids.map(id => ACCOUNTS.find(a => Number(a.id) === Number(id))).filter(Boolean);
  const retryingCount = selectedAccounts.filter(a => ['queued','running','cancelling'].includes(a.codex_execution_status || '') || (a.codex_status || '') === 'retrying').length;
  const deactivatedCount = selectedAccounts.filter(accountIsDeactivated).length;
  let msg = `批量补跑选中的 ${ids.length} 个账号 Codex 授权？

并发线程数：${workers}

将按账号消耗邮箱 OTP 和接码短信。`;
  if (retryingCount || deactivatedCount) msg += `

其中：补跑中 ${retryingCount} 个、已废号 ${deactivatedCount} 个会自动跳过。`;
  if (!confirm(msg)) return;
  const btn = $('#btnRetrySelectedCodexV2');
  if (!btn) return;
  btn.disabled = true;
  try {
    const r = await api('/api/codex/retry-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
    });
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已开始 ${r.started_count || 0} 个，跳过 ${skippedCount} 个` : (r.message || '已开始批量补跑'));
    loadAccounts();
    const search = $('#accountTaskTargetFilterV2');
    const typeFilter = $('#accountTaskTypeFilterV2');
    if (search) search.value = '';
    if (typeFilter) typeFilter.value = 'codex_retry';
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
  } catch(err) {
    showToast('批量补跑失败: ' + err.message);
    updateAccountSelectionUi();
  }
}

async function setupSelectedAccounts() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  if (!confirm(`确定补齐选中的 ${ids.length} 个账号配置吗？\n\n只执行：账号密码、套餐查询、Authenticator 2FA。\n不会执行 Codex 授权。`)) return;
  const btn = $('#btnSetupSelectedAccountsV2');
  if (!btn) return;
  btn.disabled = true;
  try {
    const r = await api('/api/accounts/setup-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
    });
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已开始补齐 ${r.started_count || 0} 个，跳过 ${skippedCount} 个` : `已开始补齐 ${r.started_count || 0} 个账号配置`);
    loadAccounts();
    const search = $('#accountTaskTargetFilterV2');
    const typeFilter = $('#accountTaskTypeFilterV2');
    if (search) search.value = '';
    if (typeFilter) typeFilter.value = 'account_setup_retry';
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
  } catch(err) {
    showToast('补齐账号配置失败: ' + err.message);
    updateAccountSelectionUi();
  }
}

function openBulkEmailChangeForSelectedAccounts(event) {
  return openBulkEmailChangeModal(Array.from(ACCOUNT_SELECTED), event?.currentTarget || null);
}

async function runSelectedAccountAction(action, label, taskType) {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  if (['password_change', 'twofa_change'].includes(action) && ids.length > 20) {
    showToast('修改密码或修改 2FA 单次最多操作 20 个账号');
    return;
  }
  if (!confirm(`确定${label}选中的 ${ids.length} 个账号吗？`)) return;
  try {
    const r = await api('/api/accounts/action-bulk', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids, action}),
    });
    const skipped = (r.skipped || []).length;
    showToast(skipped ? `已开始 ${r.started_count || 0} 个，跳过 ${skipped} 个` : (r.message || `${label}已入队`));
    loadAccounts();
    const search = $('#accountTaskTargetFilterV2');
    const typeFilter = $('#accountTaskTypeFilterV2');
    if (search) search.value = '';
    const started = Array.isArray(r.started) ? r.started : [];
    const allRegistrationResume = started.length > 0 && started.every(item => item.registration_resume);
    if (typeFilter) typeFilter.value = allRegistrationResume ? 'registration_resume' : taskType;
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
  } catch(err) {
    showToast(`${label}失败: ` + err.message);
    updateAccountSelectionUi();
  }
}
function addPasswordSelectedAccounts() { return runSelectedAccountAction('password', '补密码', 'password_setup'); }
function addTwofaSelectedAccounts() { return runSelectedAccountAction('twofa', '补 2FA', 'twofa_setup'); }
function changePasswordSelectedAccounts() { return runSelectedAccountAction('password_change', '修改密码', 'password_change'); }
function changeTwofaSelectedAccounts() { return runSelectedAccountAction('twofa_change', '修改 2FA', 'twofa_change'); }
function completeSelectedAccounts() { return runSelectedAccountAction('complete', '补全账号', 'account_completion'); }

async function copySelectedAccountTokens() {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
  try {
    const lines = await fetchAccountSecrets(ids, 'access_token');
    if (!lines.length) { showToast('选中账号没有可复制 Token'); return; }
    copyText(lines.join('\n'));
    showToast(`已复制 ${lines.length} 个 Token`);
  } catch(e) { showToast('复制失败: ' + e.message); }
}
(function bindAccountsToolbarV2() {
  const bind = (id, fn) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', fn);
  };
  bind('btnCheckSelectedPlansV2', checkSelectedPlans);
  bind('btnEmailChangeSelectedV2', openBulkEmailChangeForSelectedAccounts);
  bind('btnCheckSelectedDeactivationMailV2', checkSelectedDeactivationMail);
  bind('btnRefreshSelectedTokenV2', () => refreshSelectedToken());
  bind('btnExtractSelectedLinksV2', extractSelectedLinks);
  bind('btnSetupSelectedAccountsV2', setupSelectedAccounts);
  bind('btnAddPasswordSelectedAccountsV2', addPasswordSelectedAccounts);
  bind('btnAddTwofaSelectedAccountsV2', addTwofaSelectedAccounts);
  bind('btnChangePasswordSelectedAccountsV2', changePasswordSelectedAccounts);
  bind('btnChangeTwofaSelectedAccountsV2', changeTwofaSelectedAccounts);
  bind('btnCompleteSelectedAccountsV2', completeSelectedAccounts);
  bind('btnUploadSelectedCodexSub2V2', uploadSelectedCodexSub2);
  bind('btnRetrySelectedCodexV2', retrySelectedCodex);
  bind('btnDownloadSelectedCpaV2', downloadSelectedCpa);
  bind('btnStopSelectedCodexV2', stopSelectedCodex);
  bind('btnCopySelectedTokensV2', copySelectedAccountTokens);
  bind('btnCopySelectedLinesV2', copySelectedAccountLines);
  bind('btnCopySelectedExtractLinksV2', copySelectedAccountExtractLinks);
  bind('btnCopySelectedEmailsV2', copySelectedAccountEmails);
  bind('btnCopySelectedPasswordsV2', copySelectedAccountPasswords);
  bind('btnCopySelectedTotpsV2', copySelectedAccountTotpSecrets);
  bind('btnDownloadSelectedTxtV2', downloadSelectedAccountTxt);
  bind('btnDownloadSelectedSessionsV2', downloadSelectedAccountSessions);
  bind('btnArchiveSelectedAccountsV2', archiveSelectedAccounts);
  bind('btnDeleteSelectedAccountsV2', deleteSelectedAccounts);
  bind('btnMarkSelectedEmailInvalidV2', event => setAccountsEmailInvalid(null, true, event.currentTarget));
  bind('btnClearSelectedEmailInvalidV2', event => setAccountsEmailInvalid(null, false, event.currentTarget));
})();
