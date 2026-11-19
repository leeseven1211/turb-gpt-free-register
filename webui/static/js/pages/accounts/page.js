// Explicit action data stays separate from DOM triggers and the legacy globals.
function accountActionOwner() {
  const owner = window.AccountsPage;
  return owner && owner.isReady?.() ? owner : null;
}
function freezeAccountActionValue(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freezeAccountActionValue);
    Object.freeze(value);
  }
  return value;
}
function captureAccountActionContext(context = null, ids = null) {
  const supplied = context && Array.isArray(context.accountIds) ? context : null;
  const owner = accountActionOwner();
  const source = supplied || (owner ? owner.getActionContext(ids ? {ids: ids.map(String)} : undefined) : null);
  if (!source) return null;
  const allowed = new Set(source.accountIds.map(String));
  const accountIds = ids ? [...new Set(ids.map(String))].filter(id => allowed.has(id)) : source.accountIds.map(String);
  const wanted = new Set(accountIds);
  // Explicitly whitelist public data; never copy the trigger or a Vue proxy.
  return freezeAccountActionValue(JSON.parse(JSON.stringify({
    accountIds, expectedEmails: Object.fromEntries(Object.entries(source.expectedEmails || {}).filter(([id]) => wanted.has(id))),
    querySnapshot: source.querySnapshot, archived: source.archived,
    rowHints: (source.rowHints || []).filter(row => wanted.has(String(row.id))),
  })));
}
function accountActionIds(context, ids = null) {
  return context ? context.accountIds.map(Number) : Array.from(ids || []).map(Number);
}
function accountActionRow(id, context) {
  return context?.rowHints.find(row => String(row.id) === String(id));
}
function accountActionRefresh(context = null) {
  const owner = accountActionOwner();
  return owner ? owner.refresh() : context ? Promise.resolve() : loadAccounts();
}
function accountActionPollStatuses(context = null) {
  const owner = accountActionOwner();
  return owner ? owner.pollStatuses() : context ? Promise.resolve() : pollAccountPlanStatuses();
}
function accountActionSelectionUi(context = null) {
  if (!context || accountActionOwner()) updateAccountSelectionUi();
}
function accountActionRemoveAcknowledged(ids, context = null) {
  const requested = context ? new Set(context.accountIds) : null;
  const acknowledged = [...new Set(ids.map(String))].filter(id => !requested || requested.has(id));
  const owner = accountActionOwner();
  if (owner) owner.removeAcknowledgedSelection(acknowledged);
}
function accountActionClearSelection(context = null) {
  const owner = accountActionOwner();
  if (owner) owner.clearSelection();
}

// Account list/query/selection state belongs to the Vue page.
let ACCOUNT_BATCH_WORKERS = 3;
function accountIsDeactivated(account) {
  return ['account_status', 'codex_status', 'codex_credential_state'].some(
    key => String(account?.[key] || '').toLowerCase() === 'deactivated',
  );
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
  const requestedVersion = String(items.find(item => item.key === 'OPENAI_PROTOCOL_VERSION')?.value || 'v1').trim().toLowerCase();
  const version = ['v2', 'v3'].includes(requestedVersion) ? requestedVersion : 'v1';
  const label = driverField ? (driver === 'browser_roxy' ? 'Roxy 指纹浏览器' : `协议刷新（${version}）`) : '已保存的刷新驱动';
  const description = driver === 'protocol' && version === 'v3'
    ? `使用${label}先复用该账号有效的登录会话；会话失效或尚未保存时，按实际挑战完成密码、2FA 或邮箱验证，核对账号身份并保存最新 accessToken。`
    : `使用${label}重新登录，按实际挑战完成密码、2FA 或邮箱验证，并保存最新 accessToken。`;
  const debugDescription = debugEnabled ? 'Roxy 刷新调试已开启：实际使用 Roxy 时将显示浏览器并全程抓包；失败保留窗口，可从任务日志查看现场并下载 HAR。' : '';
  return {driver, debugEnabled, label, description, debugDescription, title: description + (debugEnabled ? ' Roxy 调试已开启，失败保留窗口。' : '')};
}

async function loadRuntimeUiSettings() {
  try {
    const settings = await apiCached('/api/ui-settings', {}, 30000);
    ACCOUNT_BATCH_WORKERS = Math.max(1, Number(settings.account_batch_workers) || 3);
  } catch(e) {}
}
function accountListQueryParams() {
  const owner = accountActionOwner();
  if (!owner) throw new Error('账号列表正在加载，请稍后重试');
  return window.AccountQuery.toLegacy(owner.getAccountSelectionSnapshot().query);
}
async function loadAccounts() {
  return window.AccountsPage?.refresh();
}
async function pollAccountPlanStatuses() {
  return window.AccountsPage?.pollStatuses();
}
function compactAccountStatus(text, fallback) {
  return Array.from(text).length > 10 ? fallback : text;
}

function accountCodexDisplay(r) {
  const status = String(r.codex_status || '').toLowerCase();
  // 旧记录可能把执行态直接存在 codex_status。
  const execution = String(r.codex_execution_status || status).toLowerCase();
  const active = ['queued', 'running', 'cancelling'].includes(execution);
  const reason = String(r.codex_error || (active ? '授权处理中' : ''));
  const display = (label, style, title = reason) => ({
    label, style, title, secondary: compactAccountStatus(reason, '执行异常'), secondaryTitle: reason,
  });
  if (accountIsDeactivated(r)) return display('封号', 'fail', '账号已确认停用/封禁');
  if (active) return display({queued: '排队中', running: '补跑中', cancelling: '停止中'}[execution], 'run');
  if (status === 'success' || status === 'completed') return display('已通过', 'ok');
  if (status === 'retrying') return display('补跑中', 'run');
  if (status === 'stopped') return display('已停止', 'mute');
  if (status === 'failed') return display('失败', 'fail');
  if (status === 'pending_confirmation' || r.codex_credential_state === 'pending_confirmation') return display('凭据核验缺失', 'mute');
  if (status === 'skipped') return display('已跳过', 'skip');
  return display('-', 'mute');
}

function accountHealthDisplay(r) {
  if (accountIsDeactivated(r)) {
    const reason = String(r.account_status_reason || '').trim();
    return {label: '已废号', style: 'fail', title: reason, secondary: compactAccountStatus(reason, '账号已停用'), secondaryTitle: reason};
  }
  const liveStatus = String(r.live_check_status || '').toLowerCase();
  if (liveStatus === 'failed') {
    const code = _liveCheckHttpStatus(r);
    const http = code ? `HTTP ${code}` : '';
    const reason = String(r.live_check_error || '').trim();
    const title = [http, reason].filter(Boolean).join('；');
    return {label: code === 401 || code === 403 ? 'Token 异常' : '查活失败', style: 'fail', title,
      secondary: http || compactAccountStatus(reason, '执行异常'), secondaryTitle: title};
  }
  if (liveStatus === 'queued' || liveStatus === 'running') {
    return {label: '查活中', style: 'mute'};
  }
  if (liveStatus === 'live') {
    const checkedAt = _fmtPlanTime(r.live_checked_at);
    return {label: '查活通过', style: 'ok', title: `上次查活通过：${checkedAt || '时间未记录'}；AT 有效期见 Token 列`,
      secondary: checkedAt ? checkedAt.replace(/^\d{4}-/, '') : '时间未记录', secondaryTitle: checkedAt};
  }
  return {label: '待查活', style: 'mute', title: '尚未完成查活，不能确认账号正常'};
}

function accountStatusLines(display, className) {
  const title = display.title ? ` title="${esc(display.title)}"` : '';
  const secondary = display.secondary ? `<div class="account-cell-line account-cell-line--sub" title="${esc(display.secondaryTitle || display.secondary)}">${esc(display.secondary)}</div>` : '';
  return `<div class="account-cell-lines"><div class="account-cell-line"><span class="${className} is-${display.style}"${title}>${esc(display.label)}</span></div>${secondary}</div>`;
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
  if (s === 'pending_confirmation' || r.codex_credential_state === 'pending_confirmation') return `<span class="acc-v2-codex is-mute"${titleAttr}>凭据核验缺失</span>`;
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
let _accountsTooltipSession = null;
let _accountsTooltipOpenGeneration = 0;

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
  const session = _accountsTooltipSession;
  _accountsTooltipSession = null;
  ++_accountsTooltipOpenGeneration;
  session?.lease?.release();
  if (_accountsTooltipNode) { _accountsTooltipNode.classList.remove('show'); _accountsTooltipNode.hidden = true; }
  if (_accountsTooltipTarget) {
    if (_accountsTooltipDescription == null) _accountsTooltipTarget.removeAttribute('aria-describedby');
    else _accountsTooltipTarget.setAttribute('aria-describedby', _accountsTooltipDescription);
  }
  _accountsTooltipTarget = null;
  _accountsTooltipDescription = null;
}

function closeAccountsVueTooltip() {
  const target = _accountsTooltipTarget;
  const focused = _accountsTooltipNode?.contains(document.activeElement);
  _hideAccountsTooltip();
  if (focused && target?.isConnected) target.focus?.({preventScroll:true});
}

function syncAccountsVueTooltip() {
  // A Vue v-html replacement need not emit mouseleave for its old target.
  if (_accountsTooltipTarget && !_accountsTooltipTarget.isConnected) _hideAccountsTooltip();
}

function _accountsTooltipIsCurrent(session) {
  syncAccountsVueTooltip();
  return Boolean(session && _accountsTooltipSession === session && session.openGeneration === _accountsTooltipOpenGeneration
    && _accountsTooltipTarget === session.target && session.target.isConnected);
}

function _loadAccountsTooltipDetails(target) {
  const cell = target.closest('.col-trial');
  if (!cell) return;
  const accountId = target.closest('tr')?.querySelector?.('[data-account-id]')?.dataset?.accountId;
  if (!accountId) return;
  const facade = window.AccountsPage;
  const owner = facade?.isReady?.() ? facade : null;
  if (!owner) return;
  const row = owner.getRowSnapshot(String(accountId));
  if (!row) return;
  const session = {target, id: String(accountId), account: _copyAccountConsumerSnapshot(row),
    lease: null, message: target.dataset.accountsTooltip, openGeneration: ++_accountsTooltipOpenGeneration};
  _accountsTooltipSession = session;
  const index = [...cell.querySelectorAll('[data-accounts-tooltip]')].indexOf(target);
  void (async () => {
    try {
      session.lease = owner.openPlanDetailsConsumer(session.id);
      const result = await session.lease.loadPlanDetails(session.id, session.lease.openGeneration);
      if (!_accountsTooltipIsCurrent(session)) return;
      Object.assign(session.account, _accountConsumerDetails(result, session.id));
      if (!_accountsTooltipIsCurrent(session)) return;
      const holder = document.createElement('div');
      holder.innerHTML = _promotionCell(session.account);
      const fresh = holder.querySelectorAll('[data-accounts-tooltip]')[index];
      if (!fresh) return;
      session.message = fresh.dataset.accountsTooltip;
      // Keep the Vue-owned row and its DOM dataset unchanged.
      _showAccountsTooltip(target);
    } catch (_) {
      // The summary remains useful when the optional expanded detail fails.
    }
  })();
}

function _scheduleAccountsTooltipHide() {
  clearTimeout(_accountsTooltipHideTimer);
  _accountsTooltipHideTimer = setTimeout(() => {
    if (_accountsTooltipNode?.matches(':hover') || _accountsTooltipNode?.contains(document.activeElement)) return;
    _hideAccountsTooltip();
  }, 150);
}

function _showAccountsTooltip(target) {
  const sameTarget = _accountsTooltipTarget === target;
  const message = sameTarget && _accountsTooltipSession?.target === target
    ? _accountsTooltipSession.message : target?.dataset?.accountsTooltip || '';
  if (!message || !target.isConnected || !target.getClientRects().length) return;
  clearTimeout(_accountsTooltipHideTimer);
  if (!sameTarget) _hideAccountsTooltip();
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
  if (!sameTarget) _accountsTooltipDescription = target.getAttribute('aria-describedby');
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
  if (!sameTarget) _loadAccountsTooltipDetails(target);
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
  const labels = {other_promo: '其他优惠', none: '无优惠', unknown: '待复查', pending: '待查询', failed: '查询失败', cancelled: '已取消', not_applicable: '不适用'};
  return labels[item.kind] || '待复查';
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
  const title = [err, msg].filter(Boolean).join('；') || r.extract_link_job_id || '';
  if (s === 'queued') return `<span class="pill status-running" title="${esc(title)}">提链排队</span>`;
  if (s === 'running') return `<span class="pill status-running" title="${esc(title)}">${esc(compactAccountStatus(msg, '提链中') || '提链中')}</span>`;
  if (s === 'success') {
    const typ = (r.extract_link_type || '').toUpperCase();
    const label = typ ? `提链成功(${typ})` : '提链成功';
    const shortLabel = compactAccountStatus(label, '提链成功');
    const detail = [title || '提炼成功，可在更多菜单复制地址', shortLabel !== label ? label : ''].filter(Boolean).join('；');
    return `<div class="extract-link-cell"><span class="pill status-success" title="${esc(detail)}">${esc(shortLabel)}</span></div>`;
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
  return `<button data-codex-retry="${esc(r.email)}" title="重新跑一次 Codex 授权；按实际验证要求使用邮箱 OTP 和手机接码">${label}</button>`;
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
  const remote = _accountPasswordAuthDisplay(r);
  const local = r.has_account_password
    ? `<button type="button" class="acc-v2-token-copy" data-account-copy-secret="account_password" data-account-id="${esc(r.id)}" title="本地已保存；点击复制账号密码。本地保存不代表远端已接受。">复制</button>`
    : '<span class="acc-v2-muted">本地未保存</span>';
  const title = `最近远端密码结果：${remote.label}；最近一次有记录的认证结果，不代表当前密码或登录态仍有效。`;
  return `<div class="account-cell-lines"><div class="account-cell-line">${local}</div><div class="account-cell-line account-cell-line--sub"><span title="${esc(title)}">${esc(remote.cellLabel)}</span></div></div>`;
}
function _accountPasswordAuthDisplay(r) {
  const states = {
    verified: {label: '登录验证通过', cellLabel: '已验证', tone: 'success'},
    accepted: {label: '创建密码被接受', cellLabel: '创建已接受', tone: 'success'},
    rejected: {label: '密码被拒绝', cellLabel: '被拒绝', tone: 'danger'},
    unknown: {label: '密码验证记录不完整', cellLabel: '记录不完整', tone: 'warning'},
    skipped: {label: '未提交', cellLabel: '未提交', tone: 'neutral'},
  };
  const status = String(r.last_password_auth_status || '');
  return Object.prototype.hasOwnProperty.call(states, status)
    ? states[status] : {label: '未验证', cellLabel: '未验证', tone: 'neutral'};
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
  const source = (r.email_source || '').toString().toLowerCase();
  const supported = ['cloudflare','icloud_hide'].includes(source);
  let title = '尚未扫描';
  if (detected) {
    title = [received && `收件: ${received}`, sender && `发件人: ${sender}`, subject].filter(Boolean).join('；') || '已收到封号邮件';
    return `<div class="account-cell-lines status-action-cell" title="${esc(title)}"><div class="account-cell-line"><span class="pill status-failed" title="${esc(title)}">封号</span></div></div>`;
  }
  let disabled = false;
  let buttonTitle = '扫描该账号对应邮箱；不会刷新 AT';
  if (!supported || status === 'unsupported') {
    disabled = true;
    title = err || (source === 'email_butler' ? 'Email Butler v2 暂不提供封号邮件扫描' : '当前邮箱来源暂不支持扫描');
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
  const retry = r.registration_retry;
  const registrationRetry = retry?.active && Number(retry.source_job_id) > 0
    ? `<button type="button" data-account-registration-task="${esc(retry.source_job_id)}" data-account-id="${esc(r.id)}" title="${esc(retry.reason || '原注册任务正在执行')}">查看进行中的注册任务</button>`
    : retry?.available && !accountIsDeactivated(r)
      ? `<button type="button" data-account-registration-retry="${esc(r.id)}" title="${esc(retry.reason || '复用原注册记录，继续未完成步骤')}">${esc(retry.label || '重跑注册')}</button>`
      : retry ? `<button type="button" title="${esc(retry.reason || '当前没有可重跑的原注册任务')}" disabled>重跑注册</button>` : '';
  const parts = [
    `<button type="button" data-account-copy-secret="copy_line" data-account-id="${esc(r.id)}">复制整行</button>`,
    `<button type="button" data-account-copy-secret="chatgpt_session" data-account-id="${esc(r.id)}" title="复制完整 ChatGPT session JSON">复制 ChatGPT session</button>`,
    r.has_account_password ? `<button type="button" data-account-copy-secret="account_password" data-account-id="${esc(r.id)}">复制账号密码</button>` : '',
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="password" data-account-id="${esc(r.id)}">补密码</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="twofa" data-account-id="${esc(r.id)}">补 2FA</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="password_change" data-account-id="${esc(r.id)}">修改密码</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="twofa_change" data-account-id="${esc(r.id)}">修改 2FA</button>`,
    accountIsDeactivated(r) ? '' : `<button type="button" data-account-action="complete" data-account-id="${esc(r.id)}">补全账号</button>`,
    registrationRetry,
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
    `<button type="button" class="danger" data-account-delete="${esc(r.id)}" data-email="${esc(r.email)}" title="删除该账号本地记录；不可撤销">删除账号</button>`,
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
        : statusLabels[status] || '查询结果记录缺失';
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
  const codex = accountCodexDisplay(r);
  const codexTone = {ok: 'success', fail: 'danger', run: 'warning'}[codex.style] || 'neutral';
  const liveDetail = [r.live_checked_at ? `检查于 ${_fmtPlanTime(r.live_checked_at)}` : '',
    r.live_check_status === 'failed' ? r.live_check_error : ''].filter(Boolean).join('；');
  const risk = r.deactivation_mail_detected ? '发现封号邮件' : (r.deactivation_mail_scan_status === 'success' ? '未发现封号邮件' : '待扫描');
  const riskTone = r.deactivation_mail_detected ? 'danger' : (r.deactivation_mail_scan_status === 'success' ? 'success' : 'neutral');
  const authFallback = r.last_auth_fallback_used === true ? '已使用回退' : (r.last_auth_fallback_used === false ? '未使用回退' : '未记录');
  const authFallbackTone = r.last_auth_fallback_used === true ? 'warning' : (r.last_auth_fallback_used === false ? 'success' : 'neutral');
  const passwordAuth = _accountPasswordAuthDisplay(r);
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
    <p class="account-detail-section-copy">本地保存不代表远端已接受。远端密码结果是最近一次有记录的认证结果，不代表当前密码或登录态仍有效。</p>
    <div class="account-detail-grid">
      ${_accountDetailState('访问 Token', tokenState, tokenTone, r.token_expires_at ? `${tokenDisplay.key === 'invalid' ? 'JWT 标称到期' : '到期'} ${_fmtPlanTime(r.token_expires_at)}` : '')}
      ${_accountDetailState('在线状态', liveState, liveTone, liveDetail)}
      ${accountIsDeactivated(r) ? _accountDetailState('账号状态', '已废号', 'danger', r.account_status_reason) : ''}
      ${_accountDetailState('邮箱状态', r.email_invalid === true ? '邮箱失效' : '未标记失效', r.email_invalid === true ? 'danger' : 'neutral', r.email_invalid === true ? [r.email_invalid_reason, r.email_invalid_at ? `标记于 ${_fmtPlanTime(r.email_invalid_at)}` : ''].filter(Boolean).join('；') : '未标记不代表已验证邮箱可用')}
      ${_accountDetailState('账号密码（本地）', r.has_account_password ? '本地已保存' : '本地未保存', r.has_account_password ? 'info' : 'neutral')}
      ${_accountDetailState('最近远端密码结果', passwordAuth.label, passwordAuth.tone)}
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
      ${_accountDetailState('Codex', codex.label === '-' ? '未授权' : codex.label, codexTone, codex.secondaryTitle)}
      ${r.extract_link_message ? _accountDetailState('提链进度', r.extract_link_message) : ''}
      ${_accountDetailState('套餐检查', r.plan_checked_at ? _fmtPlanTime(r.plan_checked_at) : '未检查')}
    </div>
  </div>`;
}
function _copyAccountConsumerSnapshot(value) {
  return JSON.parse(JSON.stringify(value));
}

function _accountConsumerDetails(result, id) {
  if (!result || String(result.accountId) !== String(id) || !result.item || typeof result.item !== 'object'
      || Array.isArray(result.item) || (result.item.id != null && String(result.item.id) !== String(id))) {
    throw new Error('账号详情响应不匹配');
  }
  return _copyAccountConsumerSnapshot(result.item);
}

// The Vue page is the sole drawer owner; legacy callers only pass identity.
function openAccountDetail(id, context = null) {
  if (!window.AccountsPage?.isReady?.()) {
    context?.lease?.release?.();
    showToast('账号列表正在加载，请稍后重试');
    return;
  }
  context?.lease?.release?.();
  window.AccountsPage.openDetail(String(id), context?.trigger || document.activeElement);
}
function closeAccountDetail(restoreFocus = true) {
  window.AccountsPage?.closeDetail(restoreFocus !== false);
}
// Shared modal code keeps this compatibility entry; Vue owns menu state.
function closeAccountsV2MoreMenus() {
  return window.AccountsPage?.closeMoreMenus?.();
}
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
function _htmlText(html) {
  const div = document.createElement('div');
  div.innerHTML = String(html || '');
  div.querySelectorAll('button, svg').forEach(node => node.remove());
  return (div.textContent || '').replace(/\s+/g, ' ').trim();
}

function createAccountVuePresentation() {
  return {
    cells: {token: _tokenCellV2, account_status: _accountStatusCellV2, password: _passwordCellV2,
      quota: _quotaCell, promotion: _promotionCell, totp: _totpCellV2, risk: _deactivationMailCell,
      time: _accountTimesCellV2},
    plan: _planCell, extractLink: _extractLinkCell, codex: _codexCellV2, menu: _accountsV2MoreMenu,
    compactStatus: compactAccountStatus, codexDisplay: accountCodexDisplay,
    healthDisplay: accountHealthDisplay, statusLines: accountStatusLines, detailMarkup: _accountDetailMarkup,
    emailInvalidBadge: _accountEmailInvalidBadge, registrationDriverLabel: accountRegistrationDriverLabel,
    facetLabel, escape: esc, short, htmlText: _htmlText,
  };
}

// Toolbar selection, pending and quick-action order are owned by the Vue shell.
function refreshAccountQuickActions() { return window.AccountsPage?.refreshQuickActions(); }
function updateAccountSelectionUi() { return window.AccountsPage?.syncToolbarPending?.(); }

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
async function copyOneAccountTotp(id, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('account-totp-copy', context, btn);
}

async function copyOneAccountSecret(id, field, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction(`account-copy-secret:${field}`, context, btn);
}

async function setupOneAccount(id, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('account-setup', context, btn);
}

async function runOneAccountAction(id, action, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('account-action:' + action, context, btn);
}

async function stopOneAccountCodex(email, btn, context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('codex-stop', context, btn);
}

async function resetOneAccountCodex(email, btn, context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('codex-reset-retrying', context, btn);
}

async function retryOneAccountCodex(email, btn, context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('codex-retry', context, btn);
}

// Navigation retains its archived preference and delegates the active query.
async function applyAccountsArchivedFilter(on) {
  SHOW_ARCHIVED_ACCOUNTS = !!on;
  window.AccountsPage?.setArchived(SHOW_ARCHIVED_ACCOUNTS);
}

async function copySelectedAccountLines(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('copySelectedAccountLines', context);
}

async function copySelectedAccountExtractLinks(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('copySelectedAccountExtractLinks', context);
}

async function copySelectedAccountPasswords(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('copySelectedAccountPasswords', context);
}

async function copySelectedAccountTotpSecrets(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('copySelectedAccountTotpSecrets', context);
}

async function copySelectedAccountEmails(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('copySelectedAccountEmails', context);
}

async function downloadSelectedAccountTxt(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('downloadSelectedAccountTxt', context);
}

async function downloadSelectedAccountSessions(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('downloadSelectedAccountSessions', context);
}

async function downloadSelectedCpa(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('downloadSelectedCpa', context);
}

async function checkOnePlan(id, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('plan-check', context, btn);
}

async function extractOneLink(id, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('extract-link', context, btn);
}

async function extractSelectedLinks(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('extractSelectedLinks', context, null);
}

async function uploadSelectedCodexSub2(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('uploadSelectedCodexSub2', context, null);
}

function openC2aReimportConfirm(ids, trigger, context = null) {
  context = captureAccountActionContext(context, ids);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.openC2a(context, trigger);
}
function reimportSelectedC2a(event, context = null) {
  context = captureAccountActionContext(context);
  const button = event?.currentTarget || document.getElementById('btnReimportSelectedC2aV2');
  if (button?.disabled) return;
  return openC2aReimportConfirm(accountActionIds(context), button, context);
}
function closeC2aReimportConfirm(returnValue = 'cancel', options = {}) { return window.AccountsPage?.closeC2a(returnValue, options); }
function submitC2aReimport() { return window.AccountsPage?.submitC2a(); }
function showC2aReimportResult(result) { return window.AccountsPage?.showC2aResult(result); }
function openC2aReimportTasks(items = []) { return window.AccountsPage?.openC2aTasks(items); }

async function checkSelectedPlans(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('checkSelectedPlans', context, null);
}



async function checkOneDeactivationMail(id, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('deactivation-mail-check', context, btn);
}

async function checkSelectedDeactivationMail(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('checkSelectedDeactivationMail', context, null);
}

function accountBulkQueueReasons(result) {
  const reasons = [...(result.skipped || []), ...(result.failed || [])]
    .map(item => String(item.reason || item.error || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  if (!reasons.length) return '';
  const details = reasons.slice(0, 3).map(reason => reason.length > 80 ? `${reason.slice(0, 80)}…` : reason);
  return `；${details.join('；')}${reasons.length > 3 ? `；另有 ${reasons.length - 3} 条原因` : ''}`;
}

async function checkSelectedLive(idsArg = null, btnArg = null, context = null) {
  context = captureAccountActionContext(context, idsArg);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('checkSelectedLive', context, btnArg);
}

async function refreshSelectedToken(idsArg = null, btnArg = null, context = null) {
  context = captureAccountActionContext(context, idsArg);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('refreshSelectedToken', context, btnArg);
}

async function deleteAccount(id, email, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('account-delete', context, btn);
}

async function setAccountsEmailInvalid(idsArg = null, invalid = true, btn = null, context = null) {
  context = captureAccountActionContext(context, idsArg);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('setAccountsEmailInvalid:' + (invalid ? '1' : '0'), context, btn);
}

async function restoreDeactivatedAccount(id, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('account-restore', context, btn);
}

async function archiveOneAccount(id, archived, btn, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('account-archive:' + (archived ? '1' : '0'), context, btn);
}

async function archiveSelectedAccounts(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('archiveSelectedAccounts', context, null);
}

async function deleteSelectedAccounts(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('deleteSelectedAccounts', context, null);
}

async function stopSelectedCodex(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('stopSelectedCodex', context, null);
}

async function retrySelectedCodex(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('retrySelectedCodex', context, null);
}

async function setupSelectedAccounts(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('setupSelectedAccounts', context, null);
}

function openBulkEmailChangeForSelectedAccounts(event, context = null) {
  context = captureAccountActionContext(context);
  return openBulkEmailChangeModal(accountActionIds(context), event?.currentTarget || null, context);
}

async function runSelectedAccountAction(action, label, taskType, context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction(({password:'addPasswordSelectedAccounts',twofa:'addTwofaSelectedAccounts',password_change:'changePasswordSelectedAccounts',twofa_change:'changeTwofaSelectedAccounts',complete:'completeSelectedAccounts'})[action], context, null);
}
function addPasswordSelectedAccounts(context = null) { return runSelectedAccountAction('password', '补密码', 'password_setup', context); }
function addTwofaSelectedAccounts(context = null) { return runSelectedAccountAction('twofa', '补 2FA', 'twofa_setup', context); }
function changePasswordSelectedAccounts(context = null) { return runSelectedAccountAction('password_change', '修改密码', 'password_change', context); }
function changeTwofaSelectedAccounts(context = null) { return runSelectedAccountAction('twofa_change', '修改 2FA', 'twofa_change', context); }
function completeSelectedAccounts(context = null) { return runSelectedAccountAction('complete', '补全账号', 'account_completion', context); }

function showAccountRegistrationRetryResult(result, context = null, open = items => openAccountRegistrationRetryTasks(items, context)) {
  return window.AccountsPage?.showRegistrationResult(result, context, open);
}

function openAccountRegistrationRetryTasks(items = [], context = null) {
  const single = items.length === 1 ? items[0] : null;
  context = captureAccountActionContext(context, single ? [single.account_id] : null);
  const account = single && !single.email ? accountActionRow(single.account_id, context) : null;
  const taskId = single?.task_id || single?.operation_task_id;
  window.TaskCenter.open({filters: {target: single?.email || account?.email || ''},
    taskId: taskId ? Number(taskId) : undefined, runId: single?.run_id ? Number(single.run_id) : null})
    .then(() => { if (!taskId && single?.job_id) openLog(Number(single.job_id)); });
}

async function retryAccountRegistration(idsArg = null, btnArg = null, context = null) {
  context = captureAccountActionContext(context, idsArg);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('retryAccountRegistration', context, btnArg);
}

async function copySelectedAccountTokens(context = null) {
  context = captureAccountActionContext(context);
  if (!window.AccountsPage?.isReady?.()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('copySelectedAccountTokens', context);
}


// Vue passes an action descriptor and immutable public data. No fake event,
// selection injection, or request-time lookup of the legacy account array.
function invokeAccountAction(action, suppliedContext, trigger = null) {
  const context = captureAccountActionContext(suppliedContext);
  if (!context) throw new Error('账号动作上下文不可用，请刷新后重试');
  if (window.AccountsPage?.isActionSupported?.(action)) return window.AccountsPage.invokeAction(action, context, trigger);
  const ids = accountActionIds(context);
  const id = ids[0];
  const email = context.expectedEmails[String(id)] || '';
  const separator = action.indexOf(':');
  const name = separator < 0 ? action : action.slice(0, separator);
  const value = separator < 0 ? '' : action.slice(separator + 1);
  if (name === 'bulk-from-account-filters' || name === 'bulk-from-selected-accounts') return BulkTasks.fromAccounts(name === 'bulk-from-selected-accounts', 'plan_check', {ids:[...context.accountIds],query:context.querySnapshot});
  if (name === 'openAccountInspectionHistory') return window.AccountsPage.openInspectionHistory(trigger);
  const bulk = {
    copySelectedAccountTokens, copySelectedAccountLines, copySelectedAccountEmails,
    copySelectedAccountExtractLinks, copySelectedAccountPasswords, copySelectedAccountTotpSecrets,
    downloadSelectedAccountTxt, downloadSelectedAccountSessions, downloadSelectedCpa,
    checkSelectedPlans, extractSelectedLinks, uploadSelectedCodexSub2,
    checkSelectedDeactivationMail, setupSelectedAccounts, addPasswordSelectedAccounts,
    addTwofaSelectedAccounts, changePasswordSelectedAccounts, changeTwofaSelectedAccounts,
    completeSelectedAccounts, stopSelectedCodex, retrySelectedCodex,
    archiveSelectedAccounts, deleteSelectedAccounts,
  };
  if (bulk[name]) return bulk[name](context);
  if (name === 'checkSelectedLive') return checkSelectedLive(null, trigger, context);
  if (name === 'refreshSelectedToken') return refreshSelectedToken(null, trigger, context);
  if (name === 'retryAccountRegistration') return retryAccountRegistration(null, trigger, context);
  if (name === 'reimportSelectedC2a') return openC2aReimportConfirm(ids, trigger, context);
  if (name === 'openBulkEmailChangeForSelectedAccounts') return openBulkEmailChangeModal(ids, trigger, context);
  if (name === 'setAccountsEmailInvalid') return setAccountsEmailInvalid(null, value !== '0', trigger, context);
  if (name === 'openAccountInspectionStart') return openAccountInspectionStart(context, trigger);
  if (name === 'deleteDeactivatedAccounts') return deleteDeactivatedAccounts(context);
  if (!id) { showToast('请先选择账号'); return; }
  if (name === 'account-setup') return setupOneAccount(id, trigger, context);
  if (name === 'account-action') return runOneAccountAction(id, value, trigger, context);
  if (name === 'account-copy-secret') return copyOneAccountSecret(id, value, trigger, context);
  if (name === 'account-totp-copy') return copyOneAccountTotp(id, trigger, context);
  if (name === 'account-registration-retry') return retryAccountRegistration([id], trigger, context);
  if (name === 'account-registration-task') return openAccountRegistrationRetryTasks([{account_id: id, email, job_id: Number(value)}], context);
  if (name === 'account-email-change') return openEmailChangeModal(id, trigger, context);
  if (name === 'account-live-check') return checkSelectedLive([id], trigger, context);
  if (name === 'account-refresh-token') return refreshSelectedToken([id], trigger, context);
  if (name === 'plan-check') return checkOnePlan(id, trigger, context);
  if (name === 'deactivation-mail-check') return checkOneDeactivationMail(id, trigger, context);
  if (name === 'account-delete') return deleteAccount(id, email, trigger, context);
  if (name === 'account-archive') return archiveOneAccount(id, value === '1', trigger, context);
  if (name === 'account-restore') return restoreDeactivatedAccount(id, trigger, context);
  if (name === 'account-email-invalid') return setAccountsEmailInvalid([id], value === '1', trigger, context);
  if (name === 'extract-link') return extractOneLink(id, trigger, context);
  if (name === 'account-task-history') return window.TaskCenter.open({filters: {target: email}});
  if (name === 'codex-stop') return stopOneAccountCodex(email, trigger, context);
  if (name === 'codex-reset-retrying') return resetOneAccountCodex(email, trigger, context);
  if (name === 'codex-retry') return retryOneAccountCodex(email, trigger, context);
  if (name === 'qr-url') { if (!value) { showToast('二维码地址为空'); return; } return openQrModal(value); }
  if (name === 'copy-id') return copyText(copyStore.get(value));
  throw new Error(`未支持的账号动作：${name}`);
}
