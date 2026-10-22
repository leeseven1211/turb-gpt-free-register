const EXTRACT_WORKBENCH_PAGE_SIZE = 20;
let EXTRACT_WORKBENCH_ROOT = null;
let EXTRACT_WORKBENCH_CONFIG = null;
let EXTRACT_WORKBENCH_STATE = {page: 1, status: '', provider: '', mode: '', query: '', selectedAccounts: new Set(), items: [], total: 0, counts: {}};
let EXTRACT_WORKBENCH_SEQUENCE = 0;
let EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE = 0;
let EXTRACT_WORKBENCH_CONFIG_PROMISE = null;
let EXTRACT_WORKBENCH_BOUND = false;
let EXTRACT_WORKBENCH_QUERY_TIMER = null;
const EXTRACT_WORKBENCH_PROVIDER_LABELS = {legacy:'现有提链', lumen_flow:'Lumen Flow', huanguang:'幻光提链'};

const EXTRACT_WORKBENCH_STATUS_LABELS = {
  pending: '等待执行', queued: '排队中', running: '运行中', success: '已完成', failed: '失败',
  passed: '预检通过', succeeded: '已完成', waiting: '等待中', settling: '收尾中', cancelling: '取消中', cancelled: '已取消',
  skipped: '已跳过', paid: '支付成功', unpaid: '未支付', pending_payment: '待支付',
  confirmed: 'Plus 已确认', plus: 'Plus 已确认', not_confirmed: 'Plus 未确认',
  unknown: '待确认', request_unknown: '结果待确认', unavailable: '未启用', not_applicable: '不适用',
};
const EXTRACT_WORKBENCH_FILTERS = [
  ['', '全部任务'], ['processing', '只看处理中'], ['running', '只看运行中'], ['extraction_succeeded', '成功出链'],
  ['payment_succeeded', '成功支付'], ['plus_confirmed', 'Plus 已确认'], ['needs_attention', '失败 / 待确认'],
];

function extractWorkbenchEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function extractWorkbenchModesForProvider(provider) {
  return Array.isArray(provider?.modes) ? provider.modes.map(String) : [];
}

function extractWorkbenchCreatePayload(accountIds, providerId, requestedMode) {
  const provider = EXTRACT_WORKBENCH_CONFIG?.providers?.find(item => item.id === providerId);
  const allowedModes = extractWorkbenchModesForProvider(provider);
  const mode = allowedModes.includes(requestedMode) ? requestedMode
    : !requestedMode && allowedModes.includes('extract_only') ? 'extract_only' : '';
  return {
    account_ids: [...new Set((Array.isArray(accountIds) ? accountIds : []).map(String).filter(Boolean))],
    provider_id: String(provider?.id || ''), mode, type: String(provider?.default_type || ''),
  };
}

function extractWorkbenchListUrl(filters = {}) {
  const params = new URLSearchParams({
    provider_id: String(filters.provider || ''), mode: String(filters.mode || ''),
    status: String(filters.status || ''), query: String(filters.query || ''),
    page: String(filters.page || 1), page_size: String(EXTRACT_WORKBENCH_PAGE_SIZE),
  });
  return `/api/extract-workbench/tasks?${params.toString()}`;
}

function extractWorkbenchStatusLabel(value, fallback = '待确认') {
  const key = String(value || '').toLowerCase();
  return EXTRACT_WORKBENCH_STATUS_LABELS[key] || key || fallback;
}

function renderExtractWorkbenchStage(stage, label, status) {
  const key = String(status || 'pending').toLowerCase();
  const tone = ['success', 'succeeded', 'passed', 'paid', 'confirmed', 'plus'].includes(key) ? 'success'
    : ['failed', 'request_unknown', 'unknown'].includes(key) ? 'warning'
    : ['running', 'queued'].includes(key) ? 'active' : 'muted';
  const stageLabel = stage === 'extraction' && key === 'success' ? '提链成功'
    : stage === 'preflight' && ['success', 'passed'].includes(key) ? '预检通过'
    : stage === 'payment' && ['success', 'paid'].includes(key) ? '支付成功'
    : stage === 'plus' && ['success', 'confirmed', 'plus'].includes(key) ? 'Plus 已确认'
    : stage === 'plus' && ['pending', 'unknown', 'not_confirmed'].includes(key) ? 'Plus 待确认'
    : extractWorkbenchStatusLabel(status);
  return `<div class="extract-workbench-data-row" data-stage="${stage}">
    <span class="extract-workbench-data-label">${label}</span><span class="extract-workbench-data-value extract-workbench-data-value--${tone}">${extractWorkbenchEscape(stageLabel)}</span>
  </div>`;
}

function extractWorkbenchIcon(name) {
  const paths = {
    external: '<path d="M8 4h5v5M13 4l-8 8M6 4H3v9h9v-3"/>',
    copy: '<rect x="5" y="5" width="8" height="9" rx="1"/><path d="M10 3H3v8"/>',
    token: '<rect x="2" y="3" width="12" height="10" rx="1"/><path d="M5 6h6M5 9h4"/>',
    check: '<path d="m3 8 3 3 7-8"/>',
    warning: '<path d="M8 4v5M8 12h.01"/>',
    dots: '<circle cx="4" cy="8" r=".7"/><circle cx="8" cy="8" r=".7"/><circle cx="12" cy="8" r=".7"/>',
    close: '<path d="m4 4 8 8M12 4l-8 8"/>',
  };
  return `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.dots}</svg>`;
}

function extractWorkbenchOutcome(task) {
  const status = String(task?.task_status || 'queued');
  const extraction = String(task?.extraction_status || 'pending');
  const paid = task?.payment_status === 'paid';
  const confirmed = ['confirmed', 'plus'].includes(task?.plus_status);
  if (paid && confirmed) return {tone:'success', state:'完成', title:'支付成功 · 到账已核实', copy:'平台状态与本地套餐核实分别记录', icon:'check'};
  if (paid) return {tone:'warning', state:'待核实', title:'支付成功 · 到账待核实', copy:'已记录支付成功，等待本地 Plus 到账核验', icon:'dots'};
  if (task?.payment_status === 'failed' && ['success', 'succeeded'].includes(extraction)) return {tone:'danger', state:'支付失败', title:'提链完成 · 支付失败', copy:'提链结果与支付结果分别记录，可查看任务详情', icon:'warning'};
  if (['request_unknown', 'attention_required'].includes(status)) return {tone:'warning', state:'待确认', title:'平台结果 · 等待确认', copy:'请查看任务详情或同步原任务状态', icon:'warning'};
  if (['failed', 'cancelled', 'stopped'].includes(status) || extraction === 'failed') return {tone:'danger', state:status === 'cancelled' ? '已取消' : '失败', title:status === 'cancelled' ? '任务已取消' : '提链未完成', copy:'保留本次运行记录，可查看原因后重跑', icon:'warning'};
  if (['success', 'succeeded'].includes(extraction)) {
    if (task?.mode !== 'extract_only' && ['running', 'queued', 'pending_payment'].includes(task?.payment_status)) return {tone:'active', state:'支付中', title:'支付处理中', copy:'出链完成与支付结果分开统计', icon:'dots'};
    return {tone:'success', state:'完成', title:'提链成功', copy:task?.mode === 'extract_only' ? '仅提链已完成，未发起支付' : '支付链接已生成，等待完成支付', icon:'check'};
  }
  if (status === 'queued' || status === 'waiting') return {tone:'muted', state:'排队中', title:'等待开始提链', copy:'执行前会在线查活并检查 AT', icon:'dots'};
  return {tone:'active', state:'运行中', title:'正在获取支付链接', copy:'出链完成后将显示对应平台结果', icon:'dots'};
}

function extractWorkbenchTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}).format(date).replaceAll('/', '-');
}

function renderExtractWorkbenchTaskCard(task) {
  const taskId = extractWorkbenchEscape(task?.task_id || '');
  const email = extractWorkbenchEscape(task?.email || '账号未记录');
  const providerId = String(task?.provider_id || 'legacy');
  const providerLabel = EXTRACT_WORKBENCH_CONFIG?.providers?.find(provider => provider.id === providerId)?.label || EXTRACT_WORKBENCH_PROVIDER_LABELS[providerId] || providerId;
  const mode = String(task?.mode || 'extract_only');
  const runCount = Math.max(1, Number(task?.run_count || 1));
  const outcome = extractWorkbenchOutcome(task);
  const rawPercent = task?.progress?.percent;
  const hasPercent = rawPercent !== null && rawPercent !== undefined && rawPercent !== '' && Number.isFinite(Number(rawPercent));
  const finished = ['success', 'failed', 'cancelled', 'stopped'].includes(task?.task_status);
  const percent = hasPercent ? Math.min(100, Math.max(0, Number(rawPercent))) : finished ? 100 : null;
  const progressLabel = task?.progress?.label || task?.progress?.stage || '';
  const canExtractLink = task?.has_extract_link === true;
  const canPaymentLink = task?.has_payment_link === true;
  const active = ['queued', 'running', 'waiting', 'settling', 'cancelling'].includes(task?.task_status);
  const actionButton = (action, label) => `<button type="button" class="btn" data-workbench-action="${action}" data-task-id="${taskId}"${active ? ' disabled' : ''}>${label}</button>`;
  const linkButton = (kind, label, icon, enabled) => `<button type="button" class="btn" data-workbench-link="${kind}" data-task-id="${taskId}"${enabled ? '' : ' disabled'}>${extractWorkbenchIcon(icon)}${label}</button>`;
  const note = extractWorkbenchEscape(task?.error || task?.message || progressLabel || outcome.copy);
  const linkType = task?.link_type ? ` · ${extractWorkbenchEscape(String(task.link_type).toUpperCase())}` : '';
  return `<article class="extract-workbench-task" data-task-id="${taskId}" data-payment="${extractWorkbenchEscape(task?.payment_status || 'unpaid')}">
    <header class="extract-workbench-top"><div class="extract-workbench-id-line"><span class="extract-workbench-number">任务 #${taskId}</span><span class="extract-workbench-state extract-workbench-state--${outcome.tone}">${outcome.state}</span><span class="extract-workbench-attempt">运行 ${runCount} 次</span></div><span class="extract-workbench-percent">${percent === null ? '—' : `${percent}%`}</span></header>
    <div class="extract-workbench-identity"><span class="extract-workbench-email" title="${email}">${email}</span><button type="button" class="extract-workbench-copy-mini" data-workbench-copy-email="${taskId}" aria-label="复制邮箱">复制</button></div>
    <div class="extract-workbench-data-rows">
      <div class="extract-workbench-data-row"><span class="extract-workbench-data-label">提链平台</span><span class="extract-workbench-data-value extract-workbench-provider-mark"><i class="extract-workbench-provider-dot extract-workbench-provider-dot--${extractWorkbenchEscape(providerId)}" aria-hidden="true"></i>${extractWorkbenchEscape(providerLabel)}${linkType}</span></div>
      ${renderExtractWorkbenchStage('preflight', '账号 / AT 预检', task?.preflight_status)}
      ${renderExtractWorkbenchStage('extraction', '提链', task?.extraction_status)}
      ${renderExtractWorkbenchStage('payment', '支付', task?.payment_status)}
      ${renderExtractWorkbenchStage('plus', 'Plus 到账核验', task?.plus_status)}
      <div class="extract-workbench-data-row"><span class="extract-workbench-data-label">最后更新</span><time class="extract-workbench-data-value">${extractWorkbenchEscape(extractWorkbenchTime(task?.updated_at || task?.created_at))}</time></div>
    </div>
    <div class="extract-workbench-note extract-workbench-note--${outcome.tone}" title="${note}">${note}</div>
    <div class="extract-workbench-progress-track" role="progressbar" aria-label="任务进度" aria-valuemin="0" aria-valuemax="100"${percent === null ? ' aria-valuetext="尚无进度信息"' : ` aria-valuenow="${percent}"`}><div class="extract-workbench-progress-fill extract-workbench-progress-fill--${outcome.tone}" style="width:${percent ?? 0}%"></div></div>
    <div class="extract-workbench-outcome"><span class="extract-workbench-outcome-symbol extract-workbench-outcome-symbol--${outcome.tone}">${extractWorkbenchIcon(outcome.icon)}</span><strong class="extract-workbench-outcome-title extract-workbench-outcome-title--${outcome.tone}">${outcome.title}</strong><span class="extract-workbench-outcome-copy">${outcome.copy}</span></div>
    <div class="extract-workbench-card-actions">
      ${linkButton('payment', '打开支付', 'external', canPaymentLink)}
      ${linkButton('extract', '复制链接', 'copy', canExtractLink)}
      <button type="button" class="btn" data-workbench-copy-at="${taskId}"${Number(task?.account_id) > 0 ? '' : ' disabled'}>${extractWorkbenchIcon('token')}复制 AT</button>
    </div>
    <details class="extract-workbench-tools"><summary>${extractWorkbenchEscape(extractWorkbenchModeLabel(mode))}<span>更多操作</span></summary><div class="extract-workbench-task-actions">
        <button type="button" class="btn" data-workbench-detail="${taskId}" aria-expanded="false">查看详情</button>
        ${actionButton('sync_status', '同步状态')}${actionButton('retry', '重跑')}
        ${mode === 'auto_payment' && task?.payment_status !== 'paid' ? actionButton('auto_payment', '查询自动支付') : ''}
      </div><div class="extract-workbench-detail hidden" data-workbench-detail-content></div></details>
  </article>`;
}

async function extractWorkbenchRequest(endpoint, options = {}) {
  if (typeof window.__EXTRACT_WORKBENCH_DATA_SOURCE__ === 'function') {
    return window.__EXTRACT_WORKBENCH_DATA_SOURCE__(endpoint, options);
  }
  return api(endpoint, options);
}

function extractWorkbenchRoot() {
  return EXTRACT_WORKBENCH_ROOT || document.getElementById('extractWorkbenchRoot');
}

function extractWorkbenchNode(selector) {
  return extractWorkbenchRoot()?.querySelector(selector) || null;
}

function extractWorkbenchRenderProviders() {
  const config = EXTRACT_WORKBENCH_CONFIG || {providers: []};
  const providers = Array.isArray(config.providers) ? config.providers : [];
  const providerSelect = extractWorkbenchNode('[data-workbench-provider]');
  const filterProvider = extractWorkbenchNode('[data-workbench-filter-provider]');
  if (!providerSelect || !filterProvider) return;
  const previous = providerSelect.value;
  providerSelect.innerHTML = providers.map(provider => `<option value="${extractWorkbenchEscape(provider.id)}">${extractWorkbenchEscape(provider.label || provider.id)}</option>`).join('');
  const initial = providers.some(provider => provider.id === previous) ? previous
    : providers.some(provider => provider.id === config.default_provider) ? config.default_provider : (providers[0]?.id || '');
  providerSelect.value = initial;
  filterProvider.innerHTML = '<option value="">全部平台</option>' + providers.map(provider => `<option value="${extractWorkbenchEscape(provider.id)}">${extractWorkbenchEscape(provider.label || provider.id)}</option>`).join('');
  filterProvider.value = EXTRACT_WORKBENCH_STATE.provider;
  extractWorkbenchRenderModes();
  const filterMode = extractWorkbenchNode('[data-workbench-filter-mode]');
  if (filterMode) {
    const modes = [...new Set(providers.flatMap(extractWorkbenchModesForProvider))];
    filterMode.innerHTML = '<option value="">全部模式</option>' + modes.map(mode => `<option value="${extractWorkbenchEscape(mode)}">${extractWorkbenchEscape(extractWorkbenchModeLabel(mode))}</option>`).join('');
    filterMode.value = EXTRACT_WORKBENCH_STATE.mode;
  }
}

function extractWorkbenchModeLabel(mode) {
  return ({extract_only:'仅提链', manual_payment:'手动支付', auto_payment:'自动支付'})[mode] || mode;
}

function extractWorkbenchRenderModes() {
  const providerId = extractWorkbenchNode('[data-workbench-provider]')?.value;
  const provider = EXTRACT_WORKBENCH_CONFIG?.providers?.find(item => item.id === providerId);
  const modeSelect = extractWorkbenchNode('[data-workbench-mode]');
  if (!modeSelect) return;
  const modes = extractWorkbenchModesForProvider(provider);
  const selected = modeSelect.value;
  const defaultMode = modes.includes('extract_only') ? 'extract_only' : modes.includes('manual_payment') ? 'manual_payment' : '';
  const initial = modes.includes(selected) ? selected : defaultMode;
  modeSelect.innerHTML = `${defaultMode ? '' : '<option value="">请选择运行模式</option>'}${modes.map(mode => `<option value="${extractWorkbenchEscape(mode)}">${extractWorkbenchEscape(extractWorkbenchModeLabel(mode))}</option>`).join('')}`;
  modeSelect.value = initial;
  const createButton = extractWorkbenchNode('[data-workbench-create]');
  if (createButton) createButton.disabled = !provider || !modes.includes(modeSelect.value) || EXTRACT_WORKBENCH_STATE.selectedAccounts.size === 0;
  const selectedCount = extractWorkbenchNode('[data-workbench-selection-count]');
  if (selectedCount) selectedCount.textContent = `已选择 ${EXTRACT_WORKBENCH_STATE.selectedAccounts.size} 个账号`;
}

function extractWorkbenchRenderStatusTabs() {
  const target = extractWorkbenchNode('[data-workbench-status-tabs]');
  if (!target) return;
  const counts = EXTRACT_WORKBENCH_STATE.counts || {};
  target.innerHTML = EXTRACT_WORKBENCH_FILTERS.map(([value, label]) => {
    const count = Number(counts[value || 'all'] ?? (value ? 0 : EXTRACT_WORKBENCH_STATE.total) ?? 0);
    return `<button type="button" class="extract-workbench-status-filter" data-workbench-status-filter="${value}" aria-pressed="${EXTRACT_WORKBENCH_STATE.status === value}"><strong>${label}</strong><span>${count.toLocaleString('zh-CN')}</span></button>`;
  }).join('');
}

function extractWorkbenchRenderTasks() {
  const target = extractWorkbenchNode('[data-workbench-tasks]');
  if (!target) return;
  const items = Array.isArray(EXTRACT_WORKBENCH_STATE.items) ? EXTRACT_WORKBENCH_STATE.items : [];
  target.innerHTML = items.length ? items.map(renderExtractWorkbenchTaskCard).join('') : '<p class="extract-workbench-empty">没有匹配的提链任务</p>';
  const summary = extractWorkbenchNode('[data-workbench-summary]');
  const total = Number(EXTRACT_WORKBENCH_STATE.total || 0);
  const first = items.length ? (EXTRACT_WORKBENCH_STATE.page - 1) * EXTRACT_WORKBENCH_PAGE_SIZE + 1 : 0;
  if (summary) summary.textContent = `显示 ${first}–${first ? first + items.length - 1 : 0} / ${total.toLocaleString('zh-CN')} 个任务`;
  extractWorkbenchRenderStatusTabs();
  const page = Number(EXTRACT_WORKBENCH_STATE.page || 1);
  const pages = Math.max(1, Math.ceil(Number(EXTRACT_WORKBENCH_STATE.total || 0) / EXTRACT_WORKBENCH_PAGE_SIZE));
  const label = extractWorkbenchNode('[data-workbench-page-label]');
  if (label) label.textContent = `第 ${page} / ${pages} 页`;
  const previous = extractWorkbenchNode('[data-workbench-page="prev"]');
  const next = extractWorkbenchNode('[data-workbench-page="next"]');
  if (previous) previous.disabled = page <= 1;
  if (next) next.disabled = page >= pages;
}

async function extractWorkbenchLoadConfig(force = false) {
  if (EXTRACT_WORKBENCH_CONFIG && !force) return EXTRACT_WORKBENCH_CONFIG;
  if (!EXTRACT_WORKBENCH_CONFIG_PROMISE) {
    EXTRACT_WORKBENCH_CONFIG_PROMISE = extractWorkbenchRequest('/api/extract-workbench/config')
      .then(result => { EXTRACT_WORKBENCH_CONFIG = result || {providers: []}; return EXTRACT_WORKBENCH_CONFIG; })
      .finally(() => { EXTRACT_WORKBENCH_CONFIG_PROMISE = null; });
  }
  return EXTRACT_WORKBENCH_CONFIG_PROMISE;
}

async function loadExtractWorkbench({force = false} = {}) {
  const root = extractWorkbenchRoot();
  if (!root) return;
  EXTRACT_WORKBENCH_ROOT = root;
  extractWorkbenchBindEvents();
  const sequence = ++EXTRACT_WORKBENCH_SEQUENCE;
  const tasksNode = extractWorkbenchNode('[data-workbench-tasks]');
  if (tasksNode) tasksNode.innerHTML = '<p class="extract-workbench-muted">加载任务中…</p>';
  try {
    await extractWorkbenchLoadConfig(force);
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    extractWorkbenchRenderProviders();
    const result = await extractWorkbenchRequest(extractWorkbenchListUrl({...EXTRACT_WORKBENCH_STATE}));
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, items: result?.items || [], counts: result?.counts || {}, total: Number(result?.total || 0), page: Number(result?.page || EXTRACT_WORKBENCH_STATE.page)};
    extractWorkbenchRenderTasks();
    if (typeof markViewReady === 'function') markViewReady('extract-workbench');
  } catch (error) {
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    if (tasksNode) tasksNode.innerHTML = `<p class="extract-workbench-error">${extractWorkbenchEscape(error?.message || '加载失败，请刷新后重试')}</p>`;
    const summary = extractWorkbenchNode('[data-workbench-summary]');
    if (summary) summary.textContent = '任务暂时无法加载';
  }
  return EXTRACT_WORKBENCH_STATE;
}

async function extractWorkbenchOpenCreate() {
  const dialog = extractWorkbenchNode('[data-workbench-create-dialog]');
  if (!dialog) return;
  if (!dialog.open) dialog.showModal();
  try {
    await extractWorkbenchLoadConfig();
    extractWorkbenchRenderProviders();
    if (!EXTRACT_WORKBENCH_STATE.accountsLoaded) await extractWorkbenchLoadAccounts();
  } catch (_) {
    const feedback = extractWorkbenchNode('[data-workbench-create-feedback]');
    if (feedback) feedback.textContent = '平台配置加载失败，请关闭后重试。';
  }
}

async function extractWorkbenchLoadAccounts() {
  const target = extractWorkbenchNode('[data-workbench-accounts]');
  if (!target) return;
  const sequence = ++EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE;
  target.innerHTML = '<p class="extract-workbench-muted">正在加载可选账号…</p>';
  const query = extractWorkbenchNode('[data-workbench-account-query]')?.value?.trim() || '';
  const params = new URLSearchParams({paged:'1', page:'1', page_size:'50', archived:'0', email:query, q:''});
  try {
    const result = await extractWorkbenchRequest(`/api/accounts?${params.toString()}`);
    if (sequence !== EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE) return;
    const accounts = Array.isArray(result?.items) ? result.items : [];
    EXTRACT_WORKBENCH_STATE.accountsLoaded = true;
    target.innerHTML = accounts.length ? accounts.map(account => {
      const id = extractWorkbenchEscape(account.id);
      const email = extractWorkbenchEscape(account.email || '账号未记录');
      const checked = EXTRACT_WORKBENCH_STATE.selectedAccounts.has(String(account.id)) ? ' checked' : '';
      return `<label class="extract-workbench-account-option"><input type="checkbox" data-workbench-account-id="${id}"${checked}><span>${email}</span></label>`;
    }).join('') : '<p class="extract-workbench-empty">没有匹配的活跃账号</p>';
    extractWorkbenchRenderModes();
  } catch (error) {
    if (sequence !== EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE) return;
    target.innerHTML = `<p class="extract-workbench-error">账号列表加载失败：${extractWorkbenchEscape(error?.message || '请重试')}</p>`;
  }
}

async function extractWorkbenchSubmit() {
  const providerId = extractWorkbenchNode('[data-workbench-provider]')?.value || '';
  const requestedMode = extractWorkbenchNode('[data-workbench-mode]')?.value || '';
  const payload = extractWorkbenchCreatePayload([...EXTRACT_WORKBENCH_STATE.selectedAccounts], providerId, requestedMode);
  if (!payload.account_ids.length || !payload.mode) return;
  const button = extractWorkbenchNode('[data-workbench-create]');
  if (button) button.disabled = true;
  const feedback = extractWorkbenchNode('[data-workbench-create-feedback]');
  if (payload.mode === 'auto_payment' && !window.confirm(`将为选中的 ${payload.account_ids.length} 个账号启用自动支付任务，确认继续？`)) {
    if (button) button.disabled = false;
    return;
  }
  try {
    const result = await extractWorkbenchRequest('/api/extract-workbench/tasks', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    if (feedback) feedback.textContent = `已提交 ${Number(result?.started || 0)} 个任务，跳过 ${Number(result?.skipped || 0)} 个，失败 ${Number(result?.failed || 0)} 个。`;
    EXTRACT_WORKBENCH_STATE.selectedAccounts.clear();
    await loadExtractWorkbench({force:true});
    if (Number(result?.started || 0) > 0) {
      extractWorkbenchNode('[data-workbench-create-dialog]')?.close();
      if (typeof showToast === 'function') showToast(`已提交 ${Number(result.started)} 个提链任务`);
    }
    await extractWorkbenchLoadAccounts();
  } catch (error) {
    if (feedback) feedback.textContent = error?.message || '提交失败，请稍后重试。';
  } finally {
    extractWorkbenchRenderModes();
  }
}

async function extractWorkbenchTaskAction(taskId, action, button) {
  if (action === 'auto_payment' && !window.confirm('确认继续此任务的自动支付？')) return;
  if (button) button.disabled = true;
  try {
    const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(taskId)}/actions`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action}),
    });
    if (result?.accepted === false) throw new Error(result.error || '操作未接受');
    showToast?.('任务操作已提交');
    await loadExtractWorkbench({force:true});
  } catch (error) {
    showToast?.(error?.message || '任务操作失败');
  } finally {
    if (button) button.disabled = false;
  }
}

async function extractWorkbenchShowLink(taskId, kind) {
  try {
    const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(taskId)}/links`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({kind}),
    });
    const link = String(result?.url || result?.link || '');
    if (!link) throw new Error('服务端未返回可用链接');
    if (kind === 'extract') {
      try { await navigator.clipboard.writeText(link); showToast?.('提链结果已复制'); }
      catch (_) { window.prompt('提链结果', link); }
    } else window.open(link, '_blank', 'noopener,noreferrer');
  } catch (error) { showToast?.(error?.message || '获取链接失败'); }
}

async function extractWorkbenchShowDetail(taskId, button) {
  const card = button?.closest('.extract-workbench-task');
  const target = card?.querySelector('[data-workbench-detail-content]');
  if (!target) return;
  if (!target.classList.contains('hidden')) {
    target.classList.add('hidden');
    button.setAttribute('aria-expanded', 'false');
    return;
  }
  target.classList.remove('hidden');
  button.setAttribute('aria-expanded', 'true');
  target.textContent = '正在读取安全任务详情…';
  try {
    const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(taskId)}`);
    const events = Array.isArray(result?.events) ? result.events : [];
    target.innerHTML = events.length ? `<ul>${events.map(event => `<li><strong>${extractWorkbenchEscape(event.label || event.stage || '事件')}</strong><span>${extractWorkbenchEscape(extractWorkbenchStatusLabel(event.status))}</span><p>${extractWorkbenchEscape(event.message || '')}</p></li>`).join('')}</ul>` : '<p>暂无阶段事件</p>';
  } catch (error) { target.textContent = error?.message || '详情读取失败'; }
}

function extractWorkbenchApplyFilters(status = EXTRACT_WORKBENCH_STATE.status) {
  EXTRACT_WORKBENCH_STATE = {
    ...EXTRACT_WORKBENCH_STATE, page: 1,
    status,
    provider: extractWorkbenchNode('[data-workbench-filter-provider]')?.value || '',
    mode: extractWorkbenchNode('[data-workbench-filter-mode]')?.value || '',
    query: extractWorkbenchNode('[data-workbench-query]')?.value?.trim() || '',
  };
  void loadExtractWorkbench({force:true});
}

async function extractWorkbenchCopy(taskId, kind) {
  const task = EXTRACT_WORKBENCH_STATE.items.find(item => String(item.task_id) === String(taskId));
  if (!task) return;
  try {
    let value = task.email || '';
    if (kind === 'at') {
      if (!Number(task.account_id)) return;
      const result = await extractWorkbenchRequest(`/api/accounts/${encodeURIComponent(task.account_id)}/secret?field=access_token`);
      value = String(result?.value || '');
    }
    if (!value) throw new Error(kind === 'at' ? '账号尚无可用 AT' : '账号邮箱未记录');
    try { await navigator.clipboard.writeText(value); }
    catch (_) { window.prompt(kind === 'at' ? '复制 AT' : '复制邮箱', value); }
    if (typeof showToast === 'function') showToast(kind === 'at' ? 'AT 已复制' : '邮箱已复制');
  } catch (error) {
    if (typeof showToast === 'function') showToast(error?.message || '复制失败');
  }
}

function extractWorkbenchBindEvents() {
  const root = extractWorkbenchRoot();
  if (!root || EXTRACT_WORKBENCH_BOUND) return;
  EXTRACT_WORKBENCH_BOUND = true;
  root.addEventListener('click', event => {
    const openCreate = event.target.closest('[data-workbench-open-create]');
    if (openCreate) { void extractWorkbenchOpenCreate(); return; }
    const closeCreate = event.target.closest('[data-workbench-close-create]');
    if (closeCreate) { extractWorkbenchNode('[data-workbench-create-dialog]')?.close(); return; }
    const statusFilter = event.target.closest('[data-workbench-status-filter]');
    if (statusFilter) { extractWorkbenchApplyFilters(statusFilter.dataset.workbenchStatusFilter); return; }
    const copyEmail = event.target.closest('[data-workbench-copy-email]');
    if (copyEmail) { void extractWorkbenchCopy(copyEmail.dataset.workbenchCopyEmail, 'email'); return; }
    const copyAt = event.target.closest('[data-workbench-copy-at]');
    if (copyAt) { void extractWorkbenchCopy(copyAt.dataset.workbenchCopyAt, 'at'); return; }
    const refresh = event.target.closest('[data-workbench-refresh]');
    if (refresh) { void loadExtractWorkbench({force:true}); return; }
    const apply = event.target.closest('[data-workbench-apply-filters]');
    if (apply) { extractWorkbenchApplyFilters(); return; }
    const accountSearch = event.target.closest('[data-workbench-search-accounts]');
    if (accountSearch) { void extractWorkbenchLoadAccounts(); return; }
    const create = event.target.closest('[data-workbench-create]');
    if (create) { void extractWorkbenchSubmit(); return; }
    const page = event.target.closest('[data-workbench-page]');
    if (page) {
      EXTRACT_WORKBENCH_STATE.page = Math.max(1, EXTRACT_WORKBENCH_STATE.page + (page.dataset.workbenchPage === 'next' ? 1 : -1));
      void loadExtractWorkbench({force:true}); return;
    }
    const action = event.target.closest('[data-workbench-action]');
    if (action) { void extractWorkbenchTaskAction(action.dataset.taskId, action.dataset.workbenchAction, action); return; }
    const link = event.target.closest('[data-workbench-link]');
    if (link) { void extractWorkbenchShowLink(link.dataset.taskId, link.dataset.workbenchLink); return; }
    const detail = event.target.closest('[data-workbench-detail]');
    if (detail) void extractWorkbenchShowDetail(detail.dataset.workbenchDetail, detail);
  });
  root.addEventListener('change', event => {
    if (event.target.matches('[data-workbench-filter-provider], [data-workbench-filter-mode]')) extractWorkbenchApplyFilters();
    if (event.target.matches('[data-workbench-provider], [data-workbench-mode]')) extractWorkbenchRenderModes();
    if (event.target.matches('[data-workbench-account-id]')) {
      const id = String(event.target.dataset.workbenchAccountId);
      if (event.target.checked) EXTRACT_WORKBENCH_STATE.selectedAccounts.add(id);
      else EXTRACT_WORKBENCH_STATE.selectedAccounts.delete(id);
      extractWorkbenchRenderModes();
    }
  });
  root.addEventListener('input', event => {
    if (event.target.matches('[data-workbench-query]')) {
      clearTimeout(EXTRACT_WORKBENCH_QUERY_TIMER);
      EXTRACT_WORKBENCH_QUERY_TIMER = setTimeout(extractWorkbenchApplyFilters, 300);
    }
  });
  root.addEventListener('keydown', event => {
    if (event.key === 'Enter' && event.target.matches('[data-workbench-query]')) extractWorkbenchApplyFilters();
    if (event.key === 'Enter' && event.target.matches('[data-workbench-account-query]')) void extractWorkbenchLoadAccounts();
  });
}
