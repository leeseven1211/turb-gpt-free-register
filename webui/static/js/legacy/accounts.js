// ---------- 账号 ----------
let accountsLoading = false;
let planStatusLoading = false;
let planStatusRevision = '';
function getAccountOperationWorkers() {
  const configured = (typeof CONFIG !== 'undefined' && Array.isArray(CONFIG))
    ? CONFIG.find(item => item.key === 'ACCOUNT_BATCH_WORKERS')
    : null;
  return Math.max(1, Math.min(16, Number(configured?.value || 3)));
}
function configuredLiveCheckDriver() {
  const configured = (typeof CONFIG !== 'undefined' && Array.isArray(CONFIG))
    ? CONFIG.find(item => item.key === 'ACCOUNT_LIVE_CHECK_DRIVER')
    : null;
  const value = String(configured?.value ?? '').trim().toLowerCase();
  return value || null;
}
async function loadAccounts() {
  if (accountsLoading) return;
  accountsLoading = true;
  try {
    const archived = SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0';
    const plan = SHOW_PLUS_ACCOUNTS_ONLY ? 'plus' : '';
    const q = $('#qAccounts') ? $('#qAccounts').value.trim() : '';
    const p = PAGERS.accounts;
    const res = await api(`/api/accounts?paged=1&page=${encodeURIComponent(p.page)}&page_size=${encodeURIComponent(p.size)}&archived=${encodeURIComponent(archived)}&plan=${encodeURIComponent(plan)}&q=${encodeURIComponent(q)}`);
    ACCOUNTS = res.items || [];
    ACCOUNTS_TOTAL = Number(res.total || ACCOUNTS.length || 0);
    const totalPages = Math.max(1, Math.ceil(ACCOUNTS_TOTAL / p.size));
    if (p.page > totalPages) { p.page = totalPages; accountsLoading = false; return loadAccounts(); }
    renderAccounts();
  } catch(e) { showToast('加载账号失败: ' + e.message); }
  finally { accountsLoading = false; }
}
async function pollAccountPlanStatuses() {
  if (planStatusLoading || accountsLoading) return;
  planStatusLoading = true;
  try {
    const archived = SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0';
    const plan = SHOW_PLUS_ACCOUNTS_ONLY ? 'plus' : '';
    const q = $('#qAccounts') ? $('#qAccounts').value.trim() : '';
    const p = PAGERS.accounts;
    const snapshot = await api(`/api/accounts/plan-check-status?page=${encodeURIComponent(p.page)}&page_size=${encodeURIComponent(p.size)}&archived=${encodeURIComponent(archived)}&plan=${encodeURIComponent(plan)}&q=${encodeURIComponent(q)}`);
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
        Object.assign(account, item);
      });
      planStatusRevision = snapshot.revision || '';
      if (needsFullReload) await loadAccounts();
      else renderAccounts();
    }
  } catch(e) {}
  finally { planStatusLoading = false; }
}
function _codexCell(r) {
  if ((r.account_status || '').toLowerCase() === 'deactivated') return '<span class="pill status-failed" title="账号已确认停用/封禁">封号</span>';
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
function _planCell(r) {
  const ok = r.plan_check_ok;
  const err = r.plan_check_error || '';
  const plan = (r.current_plan_type || r.plan_type || '-').toString();
  const checked = r.plan_checked_at ? `查询: ${esc(r.plan_checked_at)}` : '未查询实时套餐';
  const route = (r.plan_check_network_route || '').toString();
  const routeLabel = route === 'proxy' ? `网络: 代理${r.plan_check_proxy_used ? ` (${r.plan_check_proxy_used})` : ''}` :
    route === 'direct_fallback' ? `网络: 直连回退${r.plan_check_proxy_fallback_reason ? ` (${r.plan_check_proxy_fallback_reason})` : ''}` :
    route === 'direct' ? '网络: 直连' : '';
  const registrationRoute = r.registration_proxy_region
    ? `注册出口: ${esc(r.registration_proxy_provider || '代理')} / ${esc(r.registration_proxy_region)}` : '';
  const title = [err ? esc(err) : checked, registrationRoute, routeLabel].filter(Boolean).join('；');
  const lower = plan.toLowerCase();

  if (lower === 'free') {
    const text = plan;
    const cls = 'status-success';
    return `<span class="pill ${cls}" title="${title}">${esc(text)}</span>`;
  }

  const isPaid = lower.includes('plus') || lower.includes('pro') || lower.includes('team') || lower.includes('go');
  const cls = lower === '-' ? 'status-used' : (isPaid ? 'status-success' : 'status-running');
  const expireRaw = r.plan_expires_at || r.expires_at || r.plan_renews_at || r.renews_at || '';
  const expire = _fmtPlanTime(expireRaw, true);
  const parts = [];
  const billing = _billingLabel(r.billing_period);
  if (billing) parts.push(billing);
  if (r.billing_currency) parts.push(r.billing_currency);
  if (expire) parts.push(`到期 ${expire}`);
  const discount = _discountLabel(r);
  if (discount) parts.push(discount);
  const text = parts.length ? `${plan}（${parts.join('/')}）` : plan;
  const detail = [title];
  if (expireRaw) detail.push(`到期时间: ${expireRaw}`);
  if (r.plan_renews_at) detail.push(`续费时间: ${r.plan_renews_at}`);
  if (r.discount_expires_at) detail.push(`折扣结束: ${r.discount_expires_at}`);
  if (r.discount_promo_campaign_id) detail.push(`优惠: ${r.discount_promo_campaign_id}`);
  return `<span class="pill ${cls}" title="${esc(detail.join('；'))}">${esc(text)}</span>`;
}
function _trialCell(r) {
  const plan = (r.current_plan_type || r.plan_type || '').toString().toLowerCase();
  const status = (r.plan_check_status || '').toString().toLowerCase();
  const err = r.plan_check_error || '';
  if (plan && plan !== 'free') return '<span class="muted">-</span>';
  if (!plan) return '<span class="pill status-running">待查询</span>';
  if (status === 'queued' || status === 'running') return '<span class="pill status-running">待查询</span>';
  if (status === 'failed') {
    if (r.plan_last_success_at) {
      const label = r.plus_trial_eligible ? '可用' : '不可用';
      return `<span class="pill ${r.plus_trial_eligible ? 'status-success' : 'status-used'}" title="上次成功查询: ${esc(r.plan_last_success_at)}；本次查询失败: ${esc(err || '未知错误')}">${label}</span>`;
    }
    return `<span class="pill status-failed" title="${esc(err || '套餐查询失败')}">查询失败</span>`;
  }
  if (status !== 'success' && r.plan_check_ok !== true) return '<span class="pill status-running">待查询</span>';
  return r.plus_trial_eligible
    ? '<span class="pill status-success">可用</span>'
    : '<span class="pill status-used">不可用</span>';
}
function _planAction(r) {
  if (['queued','running'].includes(r.plan_check_status)) {
    const automatic = r.plan_check_trigger === 'registration_auto';
    const queued = r.plan_check_status === 'queued';
    const label = automatic ? (queued ? '自动查询排队中…' : '自动查询中…') : (queued ? '查询排队中…' : '查询中…');
    return `<button data-plan-check="${esc(r.id)}" disabled title="套餐查询正在执行，完成后可再次查询">${label}</button>`;
  }
  return `<button data-plan-check="${esc(r.id)}" title="查询当前套餐；free 账号会检查 Plus 试用资格">查套餐</button>`;
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
    const link = r.extract_link_long_url || r.extract_link_copy_paste || '';
    const qr = r.extract_link_image_url_png || r.extract_link_image_url_svg || '';
    const expire = _fmtExtractExpire(r.extract_link_expires_at || '');
    const copy = link ? cbtn('复制提链', link, 'extract-link-btn extract-copy') : '';
    const qrBtn = qr ? `<button class="extract-link-btn extract-qr" data-qr-url="${esc(qr)}" title="打开支付二维码图片">查看二维码</button>` : '';
    const expireHtml = expire ? `<div class="extract-link-expire" title="支付链接过期时间">支付到期：${esc(expire)}</div>` : '';
    return `<div class="extract-link-cell"><span class="pill status-success" title="${title || esc(link)}">提链成功${typ ? '(' + esc(typ) + ')' : ''}</span>${copy}${qrBtn}${expireHtml}</div>`;
  }
  if (s === 'failed') {
    const reason = err || msg || '未知原因';
    return `<div class="extract-link-cell"><span class="pill status-failed" title="${esc(reason)}">提链失败</span><div class="extract-link-error" title="${esc(reason)}">${esc(reason)}</div></div>`;
  }
  return '';
}
function _extractLinkAction(r) {
  const s = r.extract_link_status || '';
  if (['queued','running'].includes(s)) return `<button disabled title="${esc(r.extract_link_message || '提链任务执行中')}">提链中…</button>`;
  const plan = (r.current_plan_type || r.plan_type || '').toString().toLowerCase();
  const eligible = plan === 'free' && !!r.plus_trial_eligible;
  if (!eligible) return '';
  const failedReason = s === 'failed' ? (r.extract_link_error || r.extract_link_message || '') : '';
  return `<button class="good" data-extract-link="${esc(r.id)}" title="${esc(failedReason ? '重新提链；上次失败原因：' + failedReason : '为该 free(可Plus试用) 账号创建 PIX/UPI/KAKAO_PAY/IDEAL 提链任务')}">提链</button>`;
}
function _codexAction(r) {
  if ((r.account_status || '').toLowerCase() === 'deactivated') return '';
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
function _legacyTokenSummary(r) {
  if (!r.has_access_token) return '<span class="muted">无 Token</span>';
  const expiresAt = r.token_expires_at || '';
  const expires = expiresAt ? new Date(expiresAt) : null;
  const expiredByTime = expires && !Number.isNaN(expires.getTime()) && expires.getTime() <= Date.now();
  const expiryText = _fmtPlanTime(expiresAt) || '未知';
  const httpStatus = _liveCheckHttpStatus(r);
  let state = 'normal', label = '正常', title = `Token 到期：${expiryText}；点击复制完整 Token`;
  if (_tokenRejectedByLiveCheck(r)) {
    state = 'invalid';
    label = `失效 · ${httpStatus || '未知'}`;
    title = `${httpStatus ? `HTTP ${httpStatus}` : '状态码未知'}；${r.live_check_error || '在线验证失败，未提供具体原因'}；JWT 标称到期：${expiryText}；点击复制完整 Token`;
  } else if (r.token_expired === true || expiredByTime) {
    state = 'expired'; label = '过期';
  }
  const tone = state === 'normal' ? 'status-success' : 'status-failed';
  return `<button type="button" class="pill ${tone}" data-account-copy-secret="access_token" data-account-id="${esc(r.id)}" title="${esc(title)}">${esc(label)}</button>`;
}
function _liveStatusSub(r) {
  const s = r.live_check_status || '';
  const err = r.live_check_error || '';
  const at = r.live_checked_at || '';
  const httpStatus = _liveCheckHttpStatus(r);
  const httpLabel = httpStatus ? ` (HTTP ${httpStatus})` : '';
  if (s === 'live') return `<div class="sub-cell" title="${esc(at)}">查活: 正常</div>`;
  if (s === 'queued') return `<div class="sub-cell" style="color:#e6a23c">查活: 排队</div>`;
  if (s === 'running') return `<div class="sub-cell" style="color:#e6a23c">查活: 运行中</div>`;
  if (s === 'deactivated') return `<div class="sub-cell" style="color:#f56c6c" title="${esc(err || at)}">查活: 已废${httpLabel}</div>`;
  if (s === 'failed') return `<div class="sub-cell" style="color:#f56c6c" title="${esc(err || at)}">查活: 失败${httpLabel}</div>`;
  return '';
}
function renderAccounts() {
  const p = PAGERS.accounts;
  const total = ACCOUNTS_TOTAL;
  const rows = ACCOUNTS;
  $('#accountsBody').innerHTML = rows.map(r => `
    <tr>
      <td><input type="checkbox" class="account-row-check" data-account-id="${esc(r.id)}" ${ACCOUNT_SELECTED.has(Number(r.id)) ? 'checked' : ''}></td>
      <td class="muted">#${esc(r.id)}</td>
      <td><div class="main-cell">${esc(r.email)}${r.archived ? ' <span class="pill status-used" title="该账号已归档">归档</span>' : ''}</div><div class="sub-cell">${esc(r.user_name || '-')}</div></td>
      <td>${esc(r.email_source || '-')}</td>
      <td><span class="mono">${_legacyTokenSummary(r)}</span></td>
      <td>${_planCell(r)}<div class="sub-cell">${_extractLinkCell(r)}</div></td>
      <td>${_trialCell(r)}</td>
      <td>${r.totp_enabled ? `<div data-account-totp-cell="${esc(r.id)}"><span class="pill status-success">已启用</span> <button class="good" data-account-totp-code="${esc(r.id)}" title="查询当前 6 位 TOTP 验证码">查询验证码</button> <span class="mono" data-account-totp-value hidden></span> <span class="muted" data-account-totp-ttl hidden></span> <button class="good" data-account-totp-copy="${esc(r.id)}" data-totp-code="" title="复制当前 TOTP 验证码" hidden>复制</button></div>` : '<span class="muted">未启用</span>'}</td>
      <td>${_codexCell(r)}</td>
      <td class="muted">${esc(r.created_at || '-')}</td>
      <td class="actions actions-cell">
        <div class="account-row-actions">
          <div class="account-action-group"><button class="good" data-account-copy-secret="copy_line" data-account-id="${esc(r.id)}">复制整行</button></div>
          <div class="account-action-group">${r.account_status === 'deactivated' ? '' : `<button data-account-live-check="${esc(r.id)}" title="只在线验证现有 Token；不会发送邮箱验证码或刷新 AT">查活</button> <button data-account-token-refresh="${esc(r.id)}" title="通过邮箱 OTP 重新登录并刷新最新 AT">刷新AT</button>`} <button data-account-live-log="${esc(r.email)}" title="查看该账号最近一次查活日志">查活日志</button> ${_planAction(r)} ${_extractLinkAction(r)}</div>
          <div class="account-action-group">${_codexAction(r)} <button data-codex-log="${esc(r.email)}" title="查看该账号最近一次 Codex 补跑日志">补跑日志</button></div>
          <div class="account-action-group danger-zone"><button data-account-archive="${esc(r.id)}" data-archived="${r.archived ? '0' : '1'}" title="${r.archived ? '恢复到默认账号列表' : '归档后默认账号列表不再显示'}">${r.archived ? '恢复' : '归档'}</button> <button class="danger" data-account-delete="${esc(r.id)}" data-email="${esc(r.email)}">删除</button></div>
        </div>
      </td>
    </tr>`).join('') || '<tr><td colspan="11" class="muted">暂无账号</td></tr>';
  updateAccountSelectionUi(rows);
  _renderPager('accounts', total);
}

function updateAccountSelectionUi(pageRows = null) {
  const hint = $('#accountsSelectedHint');
  const bulkBtn = $('#btnDeleteSelectedAccounts');
  const retryBulkBtn = $('#btnRetrySelectedCodex');
  const stopCodexBulkBtn = $('#btnStopSelectedCodex');
  const downloadCpaBtn = $('#btnDownloadSelectedCpa');
  const extractLinksBtn = $('#btnExtractSelectedLinks');
  const uploadCodexSub2Btn = $('#btnUploadSelectedCodexSub2');
  const checkPlanBtn = $('#btnCheckSelectedPlans');
  const copySelectedBtn = $('#btnCopySelectedLines');
  const downloadTxtBtn = $('#btnDownloadSelectedTxt');
  const refreshTokenBtn = $('#btnRefreshSelectedToken');
  const archiveSelectedBtn = $('#btnArchiveSelectedAccounts');
  if (hint) hint.textContent = `已选 ${ACCOUNT_SELECTED.size}`;
  if (bulkBtn) bulkBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (retryBulkBtn) retryBulkBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (stopCodexBulkBtn) stopCodexBulkBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (downloadCpaBtn) downloadCpaBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (extractLinksBtn) extractLinksBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (uploadCodexSub2Btn) uploadCodexSub2Btn.disabled = ACCOUNT_SELECTED.size === 0;
  if (checkPlanBtn) checkPlanBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (copySelectedBtn) copySelectedBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (downloadTxtBtn) downloadTxtBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (refreshTokenBtn) refreshTokenBtn.disabled = ACCOUNT_SELECTED.size === 0;
  if (archiveSelectedBtn) {
    archiveSelectedBtn.disabled = ACCOUNT_SELECTED.size === 0;
    archiveSelectedBtn.textContent = SHOW_ARCHIVED_ACCOUNTS ? '恢复选中' : '归档选中';
    archiveSelectedBtn.title = SHOW_ARCHIVED_ACCOUNTS ? '把选中的归档账号恢复到默认账号列表' : '归档选中的账号；默认账号列表将不再查询/显示这些账号';
  }

  const cbAll = $('#accountsSelectAll');
  if (!cbAll) return;
  if (!pageRows) {
    pageRows = ACCOUNTS;
  }
  const pageIds = pageRows.map(r => Number(r.id));
  const checkedCount = pageIds.filter(id => ACCOUNT_SELECTED.has(id)).length;
  cbAll.checked = pageIds.length > 0 && checkedCount === pageIds.length;
  cbAll.indeterminate = checkedCount > 0 && checkedCount < pageIds.length;
  cbAll.disabled = pageIds.length === 0;
}

// ---------- 补跑日志面板 ----------
let retryLogEmail = null, retryLogTimer = null;

function openRetryLog(email) {
  retryLogEmail = email;
  $('#retryLogEmail').textContent = email;
  $('#retryLogPanel').classList.remove('hidden');
  updateModalScrollLock();
  $('#retryLogContent').textContent = '加载中…';
  pollRetryLog();
  clearInterval(retryLogTimer);
  retryLogTimer = setInterval(pollRetryLog, 2000);
}
async function pollRetryLog() {
  if (!retryLogEmail) return;
  try {
    const r = await api(`/api/codex/retry-log?email=${encodeURIComponent(retryLogEmail)}`);
    const c = $('#retryLogContent');
    const atBottom = c.scrollTop + c.clientHeight >= c.scrollHeight - 30;
    c.textContent = r.log || '(暂无日志，等待任务写入…)';
    if (atBottom) c.scrollTop = c.scrollHeight;
    if (!r.running) {
      clearInterval(retryLogTimer);
      loadAccounts();
    }
  } catch(e) {}
}
$('#btnCloseRetryLog').addEventListener('click', closeRetryLogModal);

// ---------- 查活日志面板 ----------
let liveLogEmail = null, liveLogTimer = null;

function openLiveLog(email) {
  liveLogEmail = email;
  $('#liveLogEmail').textContent = email;
  $('#liveLogPanel').classList.remove('hidden');
  updateModalScrollLock();
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

// 老 UI 查活兜底：捕获阶段直接拦截，避免被表格/按钮组其它事件吞掉。
document.addEventListener('click', async (e) => {
  const bulkBtn = e.target.closest('[data-live-check-selected]');
  if (bulkBtn) {
    e.preventDefault();
    e.stopPropagation();
    await checkSelectedLive(null, bulkBtn);
    return;
  }
  const refreshBulkBtn = e.target.closest('[data-token-refresh-selected]');
  if (refreshBulkBtn) {
    e.preventDefault();
    e.stopPropagation();
    await refreshSelectedToken(null, refreshBulkBtn);
    return;
  }
  const oneBtn = e.target.closest('[data-account-live-check]');
  if (oneBtn) {
    e.preventDefault();
    e.stopPropagation();
    await checkSelectedLive([Number(oneBtn.dataset.accountLiveCheck)], oneBtn);
  }
}, true);

// 账号操作按钮（事件委托）
$('#accountsBody').addEventListener('click', async (e) => {
  const totpQueryBtn = e.target.closest('[data-account-totp-code]');
  if (totpQueryBtn) {
    const id = Number(totpQueryBtn.dataset.accountTotpCode);
    const cell = totpQueryBtn.closest('[data-account-totp-cell]');
    totpQueryBtn.disabled = true;
    try {
      const result = await api(`/api/accounts/${encodeURIComponent(id)}/totp-code`);
      const value = cell?.querySelector('[data-account-totp-value]');
      const ttl = cell?.querySelector('[data-account-totp-ttl]');
      const copy = cell?.querySelector('[data-account-totp-copy]');
      if (value) { value.textContent = result.code || ''; value.hidden = false; }
      if (ttl) { ttl.textContent = result.remaining_seconds ? `剩余 ${result.remaining_seconds}s` : ''; ttl.hidden = false; }
      if (copy) { copy.dataset.totpCode = result.code || ''; copy.hidden = !result.code; }
      totpQueryBtn.textContent = '刷新验证码';
      showToast(`验证码已查询，剩余 ${result.remaining_seconds || 0} 秒`);
    } catch(err) {
      showToast('查询验证码失败: ' + err.message);
    } finally {
      totpQueryBtn.disabled = false;
    }
    return;
  }

  const totpCopyBtn = e.target.closest('[data-account-totp-copy]');
  if (totpCopyBtn) {
    const code = String(totpCopyBtn.dataset.totpCode || '');
    if (!code) { showToast('请先查询验证码'); return; }
    copyText(code);
    showToast('验证码已复制');
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
      showToast(field === 'access_token' ? 'Token 已复制' : (field === 'totp_secret' ? 'TOTP 密钥已复制' : '账号整行已复制'));
    } catch(err) {
      showToast('复制失败: ' + err.message);
    } finally {
      copySecretBtn.disabled = false;
    }
    return;
  }

  const planBtn = e.target.closest('[data-plan-check]');
  if (planBtn) {
    await checkOnePlan(Number(planBtn.dataset.planCheck), planBtn);
    return;
  }

  const refreshBtn = e.target.closest('[data-account-token-refresh]');
  if (refreshBtn) {
    await refreshSelectedToken([Number(refreshBtn.dataset.accountTokenRefresh)], refreshBtn);
    return;
  }
  const liveBtn = e.target.closest('[data-account-live-check]');
  if (liveBtn) {
    await checkSelectedLive([Number(liveBtn.dataset.accountLiveCheck)], liveBtn);
    return;
  }

  const liveLogBtn = e.target.closest('[data-account-live-log]');
  if (liveLogBtn) {
    openLiveLog(liveLogBtn.dataset.accountLiveLog);
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

  const logBtn = e.target.closest('[data-codex-log]');
  if (logBtn) {
    openRetryLog(logBtn.dataset.codexLog);
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
      if (retryLogEmail === email) pollRetryLog();
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
      if (retryLogEmail === email) {
        clearInterval(retryLogTimer);
        pollRetryLog();
      }
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
    openRetryLog(email);
    const poll = setInterval(async () => {
      const acc = ACCOUNTS.find(a => a.email === email);
      if (!acc || (!['queued','running','cancelling'].includes(acc.codex_execution_status || '') && acc.codex_status !== 'retrying')) clearInterval(poll);
    }, 5000);
    setTimeout(() => clearInterval(poll), 5 * 60 * 1000);
  } catch(err) {
    showToast('触发补跑失败: ' + err.message);
    btn.disabled = false;
  }
});
$('#accountsBody').addEventListener('change', (e) => {
  const cb = e.target.closest('.account-row-check');
  if (!cb) return;
  const id = Number(cb.dataset.accountId);
  if (cb.checked) ACCOUNT_SELECTED.add(id);
  else ACCOUNT_SELECTED.delete(id);
  updateAccountSelectionUi();
});
$('#accountsSelectAll').addEventListener('change', (e) => {
  const pageRows = ACCOUNTS;
  if (e.target.checked) pageRows.forEach(r => ACCOUNT_SELECTED.add(Number(r.id)));
  else pageRows.forEach(r => ACCOUNT_SELECTED.delete(Number(r.id)));
  renderAccounts();
});
$('#btnDeleteSelectedAccounts').addEventListener('click', deleteSelectedAccounts);
$('#btnArchiveSelectedAccounts').addEventListener('click', archiveSelectedAccounts);
$('#btnCopySelectedLines').addEventListener('click', copySelectedAccountLines);
$('#btnDownloadSelectedTxt').addEventListener('click', downloadSelectedAccountTxt);
$('#btnExtractSelectedLinks').addEventListener('click', extractSelectedLinks);
$('#btnUploadSelectedCodexSub2').addEventListener('click', uploadSelectedCodexSub2);
$('#btnRetrySelectedCodex').addEventListener('click', retrySelectedCodex);
$('#btnDownloadSelectedCpa').addEventListener('click', downloadSelectedCpa);
$('#btnStopSelectedCodex').addEventListener('click', stopSelectedCodex);
$('#btnCheckSelectedPlans').addEventListener('click', checkSelectedPlans);
$('#showArchivedAccounts').addEventListener('change', async (e) => {
  SHOW_ARCHIVED_ACCOUNTS = !!e.target.checked;
  ACCOUNT_SELECTED.clear();
  PAGERS.accounts.page = 1;
  await loadAccounts();
  await pollAccountPlanStatuses();
});
$('#showPlusAccountsOnly').addEventListener('change', async (e) => {
  SHOW_PLUS_ACCOUNTS_ONLY = !!e.target.checked;
  ACCOUNT_SELECTED.clear();
  PAGERS.accounts.page = 1;
  await loadAccounts();
  await pollAccountPlanStatuses();
});
$('#btnRefreshAccounts').addEventListener('click', async () => {
  const btn = $('#btnRefreshAccounts');
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
});


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

async function downloadSelectedCpa() {
  const ids = Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const selectedAccounts = ids.map(id => ACCOUNTS.find(a => Number(a.id) === Number(id))).filter(Boolean);
  const missingCodex = selectedAccounts.filter(a => (a.codex_status || '') !== 'success').length;
  let msg = `确定从 CPA 下载选中的 ${ids.length} 个账号的 CPA/Codex JSON 吗？\n\n会按账号邮箱匹配 CPA auth-files，成功的文件会打包成 ZIP。`;
  if (missingCodex) msg += `\n\n其中 ${missingCodex} 个账号本地 Codex 状态不是 success，若 CPA 端没有文件会写入 manifest 错误清单。`;
  if (!confirm(msg)) return;
  const btn = $('#btnDownloadSelectedCpa');
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
  if (plan !== 'free' || !acc.plus_trial_eligible) {
    showToast('仅支持 free(可Plus试用) 账号提链');
    return;
  }
  if (!confirm(`确定为该账号提链吗？\n\n${acc.email || ('#' + id)}\n\n提链类型按配置使用 PIX/UPI/KAKAO_PAY/IDEAL，成功会消耗 1 次 CDK。`)) return;
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '提链中…';
  try {
    await api('/api/accounts/extract-link', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_id: id}),
    });
    showToast('提链任务已入队');
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
  const eligible = selected.filter(a => (a.current_plan_type || a.plan_type || '').toString().toLowerCase() === 'free' && !!a.plus_trial_eligible);
  if (!eligible.length) { showToast('选中账号里没有 free(可Plus试用)'); return; }
  if (!confirm(`确定批量提链 ${eligible.length} 个 free(可Plus试用) 账号吗？\n\n非可试用账号会自动跳过。成功会按账号消耗 CDK 次数。`)) return;
  const btn = $('#btnExtractSelectedLinks');
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '提链中…';
  try {
    const r = await api('/api/accounts/extract-link-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
    });
    const skipped = (r.skipped_count || 0) + (r.busy_count || 0) + (r.failed_count || 0);
    showToast(skipped ? `已入队 ${r.started_count || 0} 个，跳过/失败 ${skipped} 个` : `已入队 ${r.started_count || 0} 个`);
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
  const btn = $('#btnUploadSelectedCodexSub2');
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
  const btn = $('#btnCheckSelectedPlans');
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '查询中…';
  try {
    const r = await api('/api/accounts/check-plan-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
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

async function checkSelectedLive(idsArg = null, btnArg = null) {
  const ids = idsArg || Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const workers = getAccountOperationWorkers();
  const msg = idsArg ? `确定查活这个账号吗？` : `确定查活选中的 ${ids.length} 个账号吗？

只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。

并发线程数：${workers}`;
  if (!confirm(msg)) return;
  const firstAcc = ACCOUNTS.find(a => Number(a.id) === Number(ids[0]));
  const btn = btnArg || $('#btnCheckSelectedLive') || $('#btnCheckSelectedLiveTop');
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
    showToast(`查活已入队 ${r.started_count || 0} 个，忙碌 ${r.busy_count || 0} 个，失败 ${r.failed_count || 0}${skipped ? `，跳过 ${skipped}` : ''}（配置驱动：${configuredDriver}，实际驱动：${effectiveDriver}）`);
    const firstStarted = (r.started || [])[0];
    if (firstStarted?.email) openLiveLog(firstStarted.email);
    else if (firstAcc && firstAcc.email) openLiveLog(firstAcc.email);
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
  const msg = idsArg ? `确定刷新这个账号的 AT 吗？\n\n会通过邮箱 OTP 重新登录并保存最新 accessToken。` : `确定刷新选中的 ${ids.length} 个账号的 AT 吗？\n\n会通过邮箱 OTP 重新登录并保存最新 accessToken。\n\n并发线程数：${workers}`;
  if (!confirm(msg)) return;
  const firstAcc = ACCOUNTS.find(a => Number(a.id) === Number(ids[0]));
  const btn = btnArg || $('#btnRefreshSelectedToken') || $('#btnRefreshSelectedTokenTop');
  const old = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '刷新中…'; }
  try {
    const r = await api('/api/accounts/refresh-token-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_ids: ids}),
    });
    const skipped = (r.skipped || []).length;
    showToast(`刷新AT已入队 ${r.started_count || 0} 个，忙碌 ${r.busy_count || 0} 个，失败 ${r.failed_count || 0}${skipped ? `，跳过 ${skipped}` : ''}`);
    const firstStarted = (r.started || [])[0];
    if (firstStarted?.email) openLiveLog(firstStarted.email);
    else if (firstAcc && firstAcc.email) openLiveLog(firstAcc.email);
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
  const btn = $('#btnArchiveSelectedAccounts');
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
  $('#btnDeleteSelectedAccounts').disabled = true;
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
  const btn = $('#btnStopSelectedCodex');
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
    if (retryLogEmail) pollRetryLog();
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
  const deactivatedCount = selectedAccounts.filter(a => (a.codex_status || '') === 'deactivated').length;
  let msg = `批量补跑选中的 ${ids.length} 个账号 Codex 授权？

并发线程数：${workers}

将按账号消耗邮箱 OTP 和接码短信。`;
  if (retryingCount || deactivatedCount) msg += `

其中：补跑中 ${retryingCount} 个、已废号 ${deactivatedCount} 个会自动跳过。`;
  if (!confirm(msg)) return;
  const btn = $('#btnRetrySelectedCodex');
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
    const first = (r.started || [])[0];
    if (first && first.email) openRetryLog(first.email);
    const poll = setInterval(loadAccounts, 5000);
    setTimeout(() => clearInterval(poll), 10 * 60 * 1000);
  } catch(err) {
    showToast('批量补跑失败: ' + err.message);
    updateAccountSelectionUi();
  }
}

$('#qAccounts').addEventListener('input', debounce(() => { ACCOUNT_SELECTED.clear(); PAGERS.accounts.page = 1; loadAccounts(); }, 250));
$('#copyAllTokens').addEventListener('click', async () => {
  const ids = ACCOUNTS.filter(r => r.has_access_token).map(r => Number(r.id));
  if (!ids.length) { showToast('当前页没有 Token'); return; }
  try { copyText((await fetchAccountSecrets(ids, 'access_token')).join('\n')); } catch(e) { showToast('复制失败: ' + e.message); }
});
$('#copyAllLines').addEventListener('click', async () => {
  const ids = ACCOUNTS.map(r => Number(r.id));
  if (!ids.length) { showToast('当前页没有账号'); return; }
  try { copyText((await fetchAccountSecrets(ids, 'copy_line')).join('\n')); } catch(e) { showToast('复制失败: ' + e.message); }
});
