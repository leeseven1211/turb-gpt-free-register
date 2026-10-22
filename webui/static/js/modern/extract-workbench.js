const EXTRACT_WORKBENCH_PAGE_SIZE = 20;
let EXTRACT_WORKBENCH_ROOT = null;
let EXTRACT_WORKBENCH_CONFIG = null;
let EXTRACT_WORKBENCH_STATE = {page: 1, status: '', provider: '', mode: '', query: '', selectedAccounts: new Set(), items: [], total: 0, counts: {}};
let EXTRACT_WORKBENCH_SEQUENCE = 0;
let EXTRACT_WORKBENCH_CONFIG_PROMISE = null;
let EXTRACT_WORKBENCH_BOUND = false;

const EXTRACT_WORKBENCH_STATUS_LABELS = {
  pending: '等待执行', queued: '排队中', running: '运行中', success: '已完成', failed: '失败',
  skipped: '已跳过', paid: '支付成功', unpaid: '未支付', pending_payment: '待支付',
  confirmed: 'Plus 已确认', plus: 'Plus 已确认', not_confirmed: 'Plus 未确认',
  unknown: '待确认', request_unknown: '结果待确认', unavailable: '未启用', not_applicable: '不适用',
};
const EXTRACT_WORKBENCH_FILTERS = [
  ['', '全部状态'], ['processing', '处理中'], ['extraction_succeeded', '成功出链'],
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
  const tone = ['success', 'paid', 'confirmed', 'plus'].includes(key) ? 'success'
    : ['failed', 'request_unknown', 'unknown'].includes(key) ? 'warning'
    : ['running', 'queued'].includes(key) ? 'active' : 'muted';
  const stageLabel = stage === 'extraction' && key === 'success' ? '提链成功'
    : stage === 'preflight' && key === 'success' ? '预检通过'
    : stage === 'payment' && ['success', 'paid'].includes(key) ? '支付成功'
    : stage === 'plus' && ['success', 'confirmed', 'plus'].includes(key) ? 'Plus 已确认'
    : stage === 'plus' && ['pending', 'unknown', 'not_confirmed'].includes(key) ? 'Plus 待确认'
    : extractWorkbenchStatusLabel(status);
  return `<div class="extract-workbench-stage extract-workbench-stage--${tone}" data-stage="${stage}">
    <span class="extract-workbench-stage-label">${label}</span><strong>${extractWorkbenchEscape(stageLabel)}</strong>
  </div>`;
}

function renderExtractWorkbenchTaskCard(task) {
  const taskId = extractWorkbenchEscape(task?.task_id || '');
  const email = extractWorkbenchEscape(task?.email || '账号未记录');
  const provider = extractWorkbenchEscape(task?.provider_id || 'legacy');
  const mode = extractWorkbenchEscape(task?.mode || 'extract_only');
  const runCount = Math.max(0, Number(task?.run_count || 0));
  const progress = task?.progress && typeof task.progress === 'object'
    ? `${task.progress.label || task.progress.stage || ''}${task.progress.percent == null ? '' : ` · ${Number(task.progress.percent)}%`}`
    : String(task?.progress || '');
  const canExtractLink = task?.has_extract_link === true;
  const canPaymentLink = task?.has_payment_link === true;
  const actionButton = (action, label) => `<button type="button" class="btn" data-workbench-action="${action}" data-task-id="${taskId}">${label}</button>`;
  const linkButton = (kind, label) => `<button type="button" class="btn" data-workbench-link="${kind}" data-task-id="${taskId}">${label}</button>`;
  const details = [task?.message, task?.error].filter(Boolean).map(extractWorkbenchEscape).join(' · ');
  return `<article class="extract-workbench-task" data-task-id="${taskId}">
    <header class="extract-workbench-task-head"><div class="extract-workbench-account"><h3>${email}</h3><span>任务 #${taskId}</span></div>
      <div class="extract-workbench-task-meta"><span>${provider}</span><span>${mode}</span><span>Run ${runCount}</span></div></header>
    <div class="extract-workbench-stages">
      ${renderExtractWorkbenchStage('preflight', '账号 / AT 预检', task?.preflight_status)}
      ${renderExtractWorkbenchStage('extraction', '提链', task?.extraction_status)}
      ${renderExtractWorkbenchStage('payment', '支付', task?.payment_status)}
      ${renderExtractWorkbenchStage('plus', 'Plus 到账核验', task?.plus_status)}
    </div>
    ${progress ? `<p class="extract-workbench-progress">${extractWorkbenchEscape(progress)}</p>` : ''}
    ${details ? `<p class="extract-workbench-task-message">${details}</p>` : ''}
    <div class="extract-workbench-task-foot"><span>任务：${extractWorkbenchEscape(extractWorkbenchStatusLabel(task?.task_status))}${task?.updated_at ? ` · ${extractWorkbenchEscape(task.updated_at)}` : ''}</span>
      <div class="extract-workbench-task-actions">
        <button type="button" class="btn" data-workbench-detail="${taskId}">详情</button>
        ${canExtractLink ? linkButton('extract', '查看提链结果') : ''}
        ${canPaymentLink ? linkButton('payment', '查看支付链接') : ''}
        ${actionButton('sync_status', '同步状态')}${actionButton('retry', '重跑')}
        ${mode === 'auto_payment' && task?.payment_status !== 'paid' ? actionButton('auto_payment', '查询自动支付') : ''}
      </div>
    </div>
    <div class="extract-workbench-detail hidden" data-workbench-detail-content></div>
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
}

function extractWorkbenchRenderTasks() {
  const target = extractWorkbenchNode('[data-workbench-tasks]');
  if (!target) return;
  const items = Array.isArray(EXTRACT_WORKBENCH_STATE.items) ? EXTRACT_WORKBENCH_STATE.items : [];
  target.innerHTML = items.length ? items.map(renderExtractWorkbenchTaskCard).join('') : '<p class="extract-workbench-empty">没有匹配的提链任务</p>';
  const summary = extractWorkbenchNode('[data-workbench-summary]');
  if (summary) summary.textContent = `共 ${Number(EXTRACT_WORKBENCH_STATE.total || 0)} 条记录`;
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
    const config = await extractWorkbenchLoadConfig(force);
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    extractWorkbenchRenderProviders();
    const result = await extractWorkbenchRequest(extractWorkbenchListUrl({...EXTRACT_WORKBENCH_STATE}));
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, items: result?.items || [], counts: result?.counts || {}, total: Number(result?.total || 0), page: Number(result?.page || EXTRACT_WORKBENCH_STATE.page)};
    extractWorkbenchRenderTasks();
    if (typeof markViewReady === 'function') markViewReady('extract-workbench');
    const summary = extractWorkbenchNode('[data-workbench-summary]');
    if (summary && !Number(EXTRACT_WORKBENCH_STATE.total)) summary.textContent = '共 0 条记录';
    if (!EXTRACT_WORKBENCH_STATE.accountsLoaded) await extractWorkbenchLoadAccounts();
  } catch (error) {
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    if (tasksNode) tasksNode.innerHTML = `<p class="extract-workbench-error">${extractWorkbenchEscape(error?.message || '加载失败，请刷新后重试')}</p>`;
    const summary = extractWorkbenchNode('[data-workbench-summary]');
    if (summary) summary.textContent = '任务暂时无法加载';
  }
  return EXTRACT_WORKBENCH_STATE;
}

async function extractWorkbenchLoadAccounts() {
  const target = extractWorkbenchNode('[data-workbench-accounts]');
  if (!target) return;
  target.innerHTML = '<p class="extract-workbench-muted">正在加载可选账号…</p>';
  const query = extractWorkbenchNode('[data-workbench-account-query]')?.value?.trim() || '';
  const params = new URLSearchParams({paged:'1', page:'1', page_size:'50', archived:'0', email:query, q:''});
  try {
    const result = await extractWorkbenchRequest(`/api/accounts?${params.toString()}`);
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
    await extractWorkbenchLoad({force:true});
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
  const card = button?.closest('[data-task-id]');
  const target = card?.querySelector('[data-workbench-detail-content]');
  if (!target) return;
  target.classList.remove('hidden');
  target.textContent = '正在读取安全任务详情…';
  try {
    const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(taskId)}`);
    const events = Array.isArray(result?.events) ? result.events : [];
    target.innerHTML = events.length ? `<ul>${events.map(event => `<li><strong>${extractWorkbenchEscape(event.label || event.stage || '事件')}</strong><span>${extractWorkbenchEscape(extractWorkbenchStatusLabel(event.status))}</span><p>${extractWorkbenchEscape(event.message || '')}</p></li>`).join('')}</ul>` : '<p>暂无阶段事件</p>';
  } catch (error) { target.textContent = error?.message || '详情读取失败'; }
}

function extractWorkbenchApplyFilters() {
  EXTRACT_WORKBENCH_STATE = {
    ...EXTRACT_WORKBENCH_STATE, page: 1,
    status: extractWorkbenchNode('[data-workbench-status]')?.value || '',
    provider: extractWorkbenchNode('[data-workbench-filter-provider]')?.value || '',
    mode: extractWorkbenchNode('[data-workbench-filter-mode]')?.value || '',
    query: extractWorkbenchNode('[data-workbench-query]')?.value?.trim() || '',
  };
  void loadExtractWorkbench({force:true});
}

function extractWorkbenchBindEvents() {
  const root = extractWorkbenchRoot();
  if (!root || EXTRACT_WORKBENCH_BOUND) return;
  EXTRACT_WORKBENCH_BOUND = true;
  root.addEventListener('click', event => {
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
    if (event.target.matches('[data-workbench-provider]')) extractWorkbenchRenderModes();
    if (event.target.matches('[data-workbench-account-id]')) {
      const id = String(event.target.dataset.workbenchAccountId);
      if (event.target.checked) EXTRACT_WORKBENCH_STATE.selectedAccounts.add(id);
      else EXTRACT_WORKBENCH_STATE.selectedAccounts.delete(id);
      extractWorkbenchRenderModes();
    }
  });
  root.addEventListener('keydown', event => {
    if (event.key === 'Enter' && event.target.matches('[data-workbench-query]')) extractWorkbenchApplyFilters();
    if (event.key === 'Enter' && event.target.matches('[data-workbench-account-query]')) void extractWorkbenchLoadAccounts();
  });
}
