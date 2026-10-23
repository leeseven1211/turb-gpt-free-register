const EXTRACT_WORKBENCH_PAGE_SIZE = 10;
let EXTRACT_WORKBENCH_ROOT = null;
let EXTRACT_WORKBENCH_CONFIG = null;
let EXTRACT_WORKBENCH_STATE = {page: 1, status: '', provider: '', mode: '', query: '', selectedAccounts: new Set(), items: [], total: 0, counts: {}, batch:'', batches:[], batchPage:1, batchTotal:0, batchInitialized:false, batchDetail:null, preview:null, previewSignature:'', creating:false, submission:null, batchWorkersInitialized:false};
let EXTRACT_WORKBENCH_SEQUENCE = 0;
let EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE = 0;
let EXTRACT_WORKBENCH_CONFIG_PROMISE = null;
let EXTRACT_WORKBENCH_BOUND = false;
let EXTRACT_WORKBENCH_QUERY_TIMER = null;
let EXTRACT_WORKBENCH_POLL_TIMER = null;
let EXTRACT_WORKBENCH_DETAIL_REQUESTS = new Map();
let EXTRACT_WORKBENCH_PAYMENT_ENTRY = null;
let EXTRACT_WORKBENCH_PAYMENT_SEQUENCE = 0;
let EXTRACT_WORKBENCH_PAYMENT_TRIGGER = null;
const EXTRACT_WORKBENCH_PROVIDER_LABELS = {legacy:'现有提链', lumen_flow:'Lumen Flow', huanguang:'幻光提链'};
const EXTRACT_WORKBENCH_LINK_TYPE_LABELS = {
  pix: 'PIX', upi: 'UPI', gopay: 'GoPay', momo: 'MOMO', gcash: 'GCash',
  paypal: 'PayPal', ideal: 'iDEAL', ideal_short: 'iDEAL Short', kakao_pay: 'Kakao Pay',
  ph_short: 'PH Short',
};
const EXTRACT_WORKBENCH_PROMOTION_LABELS = {
  eligible: '全部可提链优惠', free_trial: '免费试用', half_price: '半价',
  other_discount: '其他折扣', other_promo: '其他优惠',
};

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

function extractWorkbenchLinkTypesForProvider(provider) {
  if (!provider) return [];
  const values = Array.isArray(provider.link_types) ? provider.link_types.map(String).filter(Boolean) : [];
  // 兼容未返回 link_types 的旧配置，仍允许使用服务端公布的默认类型。
  return values.length ? [...new Set(values)] : (provider.default_type ? [String(provider.default_type)] : []);
}

function extractWorkbenchLinkTypeLabel(type) {
  const value = String(type || '');
  return EXTRACT_WORKBENCH_LINK_TYPE_LABELS[value] || value;
}

function extractWorkbenchPromotionLabel(value) {
  return EXTRACT_WORKBENCH_PROMOTION_LABELS[String(value || 'eligible')] || EXTRACT_WORKBENCH_PROMOTION_LABELS.eligible;
}

function extractWorkbenchPromotionValue(value) {
  const candidate = String(value || '');
  return Object.prototype.hasOwnProperty.call(EXTRACT_WORKBENCH_PROMOTION_LABELS, candidate) ? candidate : 'eligible';
}

function extractWorkbenchCreatePayload(accountIds, providerId, requestedMode, requestedType) {
  const provider = EXTRACT_WORKBENCH_CONFIG?.providers?.find(item => item.id === providerId);
  const allowedModes = extractWorkbenchModesForProvider(provider);
  const mode = allowedModes.includes(requestedMode) ? requestedMode
    : !requestedMode && allowedModes.includes('extract_only') ? 'extract_only' : '';
  const allowedTypes = extractWorkbenchLinkTypesForProvider(provider);
  const defaultType = String(provider?.default_type || '');
  const type = allowedTypes.includes(String(requestedType || '')) ? String(requestedType)
    : allowedTypes.includes(defaultType) ? defaultType : (allowedTypes[0] || defaultType);
  return {
    account_ids: [...new Set((Array.isArray(accountIds) ? accountIds : []).map(String).filter(Boolean))],
    provider_id: String(provider?.id || ''), mode, type,
  };
}

function extractWorkbenchListUrl(filters = {}) {
  const params = new URLSearchParams({
    provider_id: String(filters.provider || ''), mode: String(filters.mode || ''),
    status: String(filters.status || ''), query: String(filters.query || ''),
    page: String(filters.page || 1), page_size: String(EXTRACT_WORKBENCH_PAGE_SIZE),
  });
  if (filters.batch) params.set('batch_id', String(filters.batch));
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
    : stage === 'plus' && ['success', 'confirmed', 'plus'].includes(key) ? 'Plus 已到账'
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
  if (paid && confirmed) return {tone:'success', state:'完成', title:'支付成功 · 到账已核实', copy:task?.payment_confirmation_source === 'local_plan_check' ? '扫码订单已完成，独立套餐查询已确认 Plus 到账' : '平台状态与本地套餐核实分别记录', icon:'check'};
  if (paid) return {tone:'warning', state:'待核实', title:'支付成功 · 到账待核实', copy:'已记录支付成功，等待本地 Plus 到账核验', icon:'dots'};
  if (task?.payment_status === 'failed' && ['success', 'succeeded'].includes(extraction)) return {tone:'danger', state:'支付失败', title:'提链完成 · 支付失败', copy:'提链结果与支付结果分别记录，可查看任务详情', icon:'warning'};
  if (confirmed && ['auto_payment', 'manual_payment'].includes(task?.mode) && ['success', 'succeeded'].includes(extraction)) return {tone:'success', state:'Plus 已到账', title:'Plus 已到账 · 支付待确认', copy:'本地套餐已核实，平台支付结果仍待确认', icon:'check'};
  if (['success', 'succeeded'].includes(extraction)) {
    if (['request_unknown', 'attention_required'].includes(status)) return {tone:'warning', state:'待确认', title:'提链成功 · 后续结果待确认', copy:'提链结果已保留，请查看后续处理详情', icon:'warning'};
    if (['failed', 'cancelled', 'stopped'].includes(status)) return {tone:'warning', state:'待处理', title:status === 'failed' ? '提链成功 · 后续处理失败' : '提链成功 · 任务已停止', copy:'提链结果已保留，后续处理状态单独记录', icon:'warning'};
    if (task?.mode !== 'extract_only' && ['running', 'queued', 'pending_payment'].includes(task?.payment_status)) return {tone:'active', state:'支付中', title:'支付处理中', copy:'出链完成与支付结果分开统计', icon:'dots'};
    return {tone:'success', state:'完成', title:'提链成功', copy:task?.mode === 'extract_only' ? '仅提链已完成，未发起支付' : '支付链接已生成，等待完成支付', icon:'check'};
  }
  if (['request_unknown', 'attention_required'].includes(status)) return {tone:'warning', state:'待确认', title:'平台结果 · 等待确认', copy:'请查看任务详情或同步原任务状态', icon:'warning'};
  if (['failed', 'cancelled', 'stopped'].includes(status) || extraction === 'failed') return {tone:'danger', state:status === 'cancelled' ? '已取消' : '失败', title:status === 'cancelled' ? '任务已取消' : '提链未完成', copy:'保留本次运行记录，可查看原因后重跑', icon:'warning'};
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
  const canPaymentEntry = task?.has_payment_entry === true || task?.has_qr === true || task?.has_payment_link === true || canExtractLink;
  const active = ['queued', 'running', 'waiting', 'settling', 'cancelling'].includes(task?.task_status);
  const actionButton = (action, label) => `<button type="button" class="btn" data-workbench-action="${action}" data-task-id="${taskId}"${active ? ' disabled' : ''}>${label}</button>`;
  const linkButton = (kind, label, icon, enabled) => `<button type="button" class="btn" data-workbench-link="${kind}" data-task-id="${taskId}"${enabled ? '' : ' disabled'}>${extractWorkbenchIcon(icon)}${label}</button>`;
  const note = extractWorkbenchEscape(task?.error || task?.message || progressLabel || outcome.copy);
  const linkType = task?.link_type ? ` · ${extractWorkbenchEscape(String(task.link_type).toUpperCase())}` : '';
  return `<article class="extract-workbench-task" data-task-id="${taskId}" data-payment="${extractWorkbenchEscape(task?.payment_status || 'unpaid')}">
    <header class="extract-workbench-top"><div class="extract-workbench-id-line"><span class="extract-workbench-number">任务 #${taskId}</span><span class="extract-workbench-state extract-workbench-state--${outcome.tone}">${outcome.state}</span></div><span class="extract-workbench-percent">${percent === null ? '—' : `${percent}%`}</span></header>
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
      <button type="button" class="btn" data-workbench-payment-entry="${taskId}"${canPaymentEntry ? '' : ' disabled'}>${extractWorkbenchIcon('external')}支付入口</button>
      ${linkButton('extract', '复制链接', 'copy', canExtractLink)}
      <button type="button" class="btn" data-workbench-copy-at="${taskId}"${Number(task?.account_id) > 0 ? '' : ' disabled'}>${extractWorkbenchIcon('token')}复制 AT</button>
    </div>
    <details class="extract-workbench-tools"><summary>${extractWorkbenchEscape(extractWorkbenchModeLabel(mode))}<small class="extract-workbench-attempt">运行 ${runCount} 次</small><span>更多操作</span></summary><div class="extract-workbench-task-actions">
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

function extractWorkbenchBatchWorkersMax() {
  const maximum = EXTRACT_WORKBENCH_CONFIG?.batch_workers_max;
  return Number.isInteger(maximum) && maximum >= 1 && maximum <= 16 ? maximum : 16;
}

function extractWorkbenchBatchWorkersDefault() {
  const workers = EXTRACT_WORKBENCH_CONFIG?.batch_workers_default;
  return Number.isInteger(workers) && workers >= 1 && workers <= extractWorkbenchBatchWorkersMax() ? workers : 1;
}

function extractWorkbenchBatchWorkers() {
  const input = extractWorkbenchNode('[data-workbench-batch-workers]');
  const workers = input ? Number(input.value) : extractWorkbenchBatchWorkersDefault();
  return Number.isInteger(workers) && workers >= 1 && workers <= extractWorkbenchBatchWorkersMax() ? workers : null;
}

function extractWorkbenchRenderBatchWorkers() {
  const input = extractWorkbenchNode('[data-workbench-batch-workers]');
  if (!input) return;
  input.min = '1';
  input.max = String(extractWorkbenchBatchWorkersMax());
  input.step = '1';
  if (!EXTRACT_WORKBENCH_STATE.batchWorkersInitialized) {
    input.value = String(extractWorkbenchBatchWorkersDefault());
    EXTRACT_WORKBENCH_STATE.batchWorkersInitialized = true;
  }
  const hint = extractWorkbenchNode('[data-workbench-concurrency-hint]');
  const workers = extractWorkbenchBatchWorkers();
  if (hint) hint.textContent = workers
    ? `本批最多同时运行 ${workers} 个账号，仍受平台与共享执行额度限制。`
    : `批次并发请输入 1 到 ${extractWorkbenchBatchWorkersMax()} 的整数。`;
}

function extractWorkbenchRenderProviders() {
  extractWorkbenchRenderBatchWorkers();
  const config = EXTRACT_WORKBENCH_CONFIG || {providers: []};
  const providers = Array.isArray(config.providers) ? config.providers : [];
  const unavailableProviders = Array.isArray(config.unavailable_providers) ? config.unavailable_providers : [];
  const providerSelect = extractWorkbenchNode('[data-workbench-provider]');
  const filterProvider = extractWorkbenchNode('[data-workbench-filter-provider]');
  if (!providerSelect || !filterProvider) return;
  const previous = providerSelect.value;
  providerSelect.innerHTML = providers.map(provider => `<option value="${extractWorkbenchEscape(provider.id)}">${extractWorkbenchEscape(provider.label || provider.id)}</option>`).join('')
    + unavailableProviders.map(provider => `<option value="${extractWorkbenchEscape(provider.id)}" disabled>${extractWorkbenchEscape(provider.label || provider.id)}（${extractWorkbenchEscape(provider.unavailable_reason || '平台配置暂不可用')}）</option>`).join('');
  const initial = providers.some(provider => provider.id === previous) ? previous
    : providers.some(provider => provider.id === config.default_provider) ? config.default_provider : (providers[0]?.id || '');
  providerSelect.value = initial;
  filterProvider.innerHTML = '<option value="">全部平台</option>' + providers.map(provider => `<option value="${extractWorkbenchEscape(provider.id)}">${extractWorkbenchEscape(provider.label || provider.id)}</option>`).join('');
  filterProvider.value = EXTRACT_WORKBENCH_STATE.provider;
  extractWorkbenchRenderModes();
  extractWorkbenchRenderLinkTypes();
  const filterMode = extractWorkbenchNode('[data-workbench-filter-mode]');
  if (filterMode) {
    const modes = [...new Set(providers.flatMap(extractWorkbenchModesForProvider))];
    filterMode.innerHTML = '<option value="">全部模式</option>' + modes.map(mode => `<option value="${extractWorkbenchEscape(mode)}">${extractWorkbenchEscape(extractWorkbenchModeLabel(mode))}</option>`).join('');
    filterMode.value = EXTRACT_WORKBENCH_STATE.mode;
  }
}

function extractWorkbenchAccountSources() {
  return {...(typeof LIST_FACET_LABELS === 'undefined' ? {} : LIST_FACET_LABELS.source), manual:'手动导入'};
}

function extractWorkbenchRenderAccountSources() {
  const select = extractWorkbenchNode('[data-workbench-account-source]');
  if (!select) return;
  const selected = select.value;
  select.innerHTML = '<option value="">全部来源</option>' + Object.entries(extractWorkbenchAccountSources())
    .map(([value, label]) => `<option value="${extractWorkbenchEscape(value)}">${extractWorkbenchEscape(label)}</option>`).join('');
  select.value = selected;
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
  const previewValid = EXTRACT_WORKBENCH_STATE.previewSignature === extractWorkbenchCandidateSignature();
  const count = previewValid ? Number(EXTRACT_WORKBENCH_STATE.preview?.selected_count || 0) : 0;
  if (createButton) createButton.disabled = EXTRACT_WORKBENCH_STATE.creating || !provider || !modes.includes(modeSelect.value) || count === 0 || extractWorkbenchBatchWorkers() === null;
  const selectedCount = extractWorkbenchNode('[data-workbench-selection-count]');
  if (selectedCount) selectedCount.textContent = `本批计划运行 ${count.toLocaleString('zh-CN')} 个账号`;
}

function extractWorkbenchRenderLinkTypes() {
  const providerId = extractWorkbenchNode('[data-workbench-provider]')?.value;
  const provider = EXTRACT_WORKBENCH_CONFIG?.providers?.find(item => item.id === providerId);
  const typeSelect = extractWorkbenchNode('[data-workbench-type]');
  if (!typeSelect) return;
  const types = extractWorkbenchLinkTypesForProvider(provider);
  const selected = String(typeSelect.value || '');
  const defaultType = String(provider?.default_type || '');
  const initial = types.includes(selected) ? selected : types.includes(defaultType) ? defaultType : (types[0] || '');
  typeSelect.innerHTML = types.length
    ? types.map(type => `<option value="${extractWorkbenchEscape(type)}">${extractWorkbenchEscape(extractWorkbenchLinkTypeLabel(type))}</option>`).join('')
    : '<option value="">暂无可用提链类型</option>';
  typeSelect.value = initial;
  typeSelect.disabled = !types.length;
  extractWorkbenchRenderCandidatePromotion();
  extractWorkbenchRenderModes();
}

function extractWorkbenchRenderCandidatePromotion() {
  const promotionNode = extractWorkbenchNode('[data-workbench-promotion]');
  const promotion = extractWorkbenchPromotionValue(promotionNode?.value);
  if (promotionNode && promotionNode.value !== promotion) promotionNode.value = promotion;
  const hint = extractWorkbenchNode('[data-workbench-candidate-hint]');
  if (!hint) return;
  const label = extractWorkbenchPromotionLabel(promotion);
  hint.textContent = promotion === 'eligible'
    ? '仅匹配活跃、未归档且具备任一可提链优惠的 free 账号；提交前仍会在线查活。'
    : `仅匹配活跃、未归档且具备「${label}」优惠的 free 账号；提交前仍会在线查活。`;
}

function extractWorkbenchBatchStatus(status) {
  return ({queued:'排队中',running:'运行中',success:'已完成',partial_success:'部分成功',partial:'部分完成',partial_submission:'部分入队',failed:'失败',attention_required:'待处理',cancelled:'已取消',completed:'已完成'})[status] || extractWorkbenchStatusLabel(status);
}

function extractWorkbenchRenderBatches() {
  const select = extractWorkbenchNode('[data-workbench-batch-select]');
  if (select) {
    const batches = [...EXTRACT_WORKBENCH_STATE.batches];
    const current = EXTRACT_WORKBENCH_STATE.batchDetail;
    if (current && !batches.some(batch => String(batch.batch_id) === String(current.batch_id))) batches.unshift(current);
    select.innerHTML = '<option value="">全部任务（含历史单独任务）</option>' + batches.map(batch => `<option value="${extractWorkbenchEscape(batch.batch_id)}">${extractWorkbenchEscape(batch.title || `批次 #${batch.batch_id}`)} · ${Number(batch.requested_count || 0)} 个 · ${extractWorkbenchEscape(extractWorkbenchBatchStatus(batch.status))}</option>`).join('');
    select.value = EXTRACT_WORKBENCH_STATE.batch;
  }
  const pages = Math.max(1, Math.ceil(EXTRACT_WORKBENCH_STATE.batchTotal / 20));
  const label = extractWorkbenchNode('[data-workbench-batch-page-label]');
  if (label) label.textContent = `第 ${EXTRACT_WORKBENCH_STATE.batchPage} / ${pages} 页`;
  const previous = extractWorkbenchNode('[data-workbench-batch-page="prev"]');
  const next = extractWorkbenchNode('[data-workbench-batch-page="next"]');
  if (previous) previous.disabled = EXTRACT_WORKBENCH_STATE.batchPage <= 1;
  if (next) next.disabled = EXTRACT_WORKBENCH_STATE.batchPage >= pages;
}

function extractWorkbenchSwitchBatch(batchId) {
  clearTimeout(EXTRACT_WORKBENCH_QUERY_TIMER);
  EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, batch:String(batchId || ''), batchInitialized:true, batchDetail:null, page:1, status:'', provider:'', mode:'', query:''};
  for (const selector of ['[data-workbench-filter-provider]','[data-workbench-filter-mode]','[data-workbench-query]']) {
    const node = extractWorkbenchNode(selector);
    if (node) node.value = '';
  }
  return loadExtractWorkbench({force:true});
}

function extractWorkbenchScheduleRefresh({retry = false} = {}) {
  clearTimeout(EXTRACT_WORKBENCH_POLL_TIMER);
  const tab = document.getElementById('tab-extract-workbench');
  if (!tab || tab.classList.contains('hidden')) return;
  if (!retry && !Number(EXTRACT_WORKBENCH_STATE.batchDetail?.counts?.processing || EXTRACT_WORKBENCH_STATE.counts.processing || 0)) return;
  EXTRACT_WORKBENCH_POLL_TIMER = setTimeout(() => {
    if (document.hidden) extractWorkbenchScheduleRefresh({retry});
    else if (!tab.classList.contains('hidden')) void loadExtractWorkbench({quiet:true});
  }, 5000);
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

function extractWorkbenchBuildTaskCards(items) {
  if (typeof document?.createElement !== 'function') return null;
  const template = document.createElement('template');
  if (!template) return null;
  template.innerHTML = items.map(renderExtractWorkbenchTaskCard).join('');
  return [...(template.content?.querySelectorAll?.('.extract-workbench-task') || [])];
}

function extractWorkbenchCopyNodeAttributes(existing, fresh, skipped = []) {
  const attributes = [...(fresh.attributes || [])];
  for (const attribute of [...(existing.attributes || [])]) {
    if (!attributes.some(item => item.name === attribute.name) && !skipped.includes(attribute.name)) existing.removeAttribute(attribute.name);
  }
  for (const attribute of attributes) {
    if (!skipped.includes(attribute.name)) existing.setAttribute(attribute.name, attribute.value);
  }
}

function extractWorkbenchPreservedNodeKey(node) {
  if (node?.matches?.('summary')) return 'summary';
  if (node?.matches?.('[data-workbench-detail-content]')) return 'detail-content';
  const fields = ['workbenchDetail', 'workbenchAction', 'workbenchLink', 'workbenchPaymentEntry', 'workbenchCopyEmail', 'workbenchCopyAt'];
  const field = fields.find(name => node?.dataset?.[name] !== undefined);
  return field ? `${field}:${node.dataset[field]}` : '';
}

function extractWorkbenchSyncNode(existing, fresh) {
  if (!existing || !fresh || existing.nodeType !== fresh.nodeType || (existing.nodeType === 1 && existing.tagName !== fresh.tagName)) {
    return fresh.cloneNode(true);
  }
  if (existing.nodeType !== 1) {
    if (existing.textContent !== fresh.textContent) existing.textContent = fresh.textContent;
    return existing;
  }
  if (existing.matches?.('[data-workbench-detail-content]')) return existing;
  const skipped = existing.matches?.('details') ? ['open'] : existing.matches?.('[data-workbench-detail]') ? ['aria-expanded'] : [];
  extractWorkbenchCopyNodeAttributes(existing, fresh, skipped);
  const existingChildren = [...(existing.childNodes || [])];
  const used = new Set();
  const desired = [...(fresh.childNodes || [])].map((freshChild, index) => {
    const key = extractWorkbenchPreservedNodeKey(freshChild);
    let candidate = key ? existingChildren.find(child => !used.has(child) && extractWorkbenchPreservedNodeKey(child) === key) : null;
    if (!candidate) {
      const atIndex = existingChildren[index];
      if (atIndex && !used.has(atIndex) && !extractWorkbenchPreservedNodeKey(freshChild) && !extractWorkbenchPreservedNodeKey(atIndex) && atIndex.nodeType === freshChild.nodeType && (atIndex.nodeType !== 1 || atIndex.tagName === freshChild.tagName)) candidate = atIndex;
    }
    if (!candidate) return freshChild.cloneNode(true);
    used.add(candidate);
    return extractWorkbenchSyncNode(candidate, freshChild);
  });
  for (const child of existingChildren) if (!used.has(child)) existing.removeChild(child);
  for (let index = 0; index < desired.length; index += 1) {
    if (existing.childNodes[index] !== desired[index]) existing.insertBefore(desired[index], existing.childNodes[index] || null);
  }
  return existing;
}

function extractWorkbenchSyncTaskCard(existing, fresh) {
  if (!existing || !fresh || typeof existing.insertBefore !== 'function' || typeof existing.removeChild !== 'function') return fresh;
  return extractWorkbenchSyncNode(existing, fresh);
}

function extractWorkbenchSyncTaskCards(target, items, freshCards = null) {
  if (!target || typeof target.querySelectorAll !== 'function' || typeof target.insertBefore !== 'function' || typeof target.removeChild !== 'function') {
    if (target) target.innerHTML = items.length ? items.map(renderExtractWorkbenchTaskCard).join('') : '<p class="extract-workbench-empty">没有匹配的提链任务</p>';
    return;
  }
  const nextCards = freshCards || extractWorkbenchBuildTaskCards(items);
  if (!nextCards) {
    target.innerHTML = items.length ? items.map(renderExtractWorkbenchTaskCard).join('') : '<p class="extract-workbench-empty">没有匹配的提链任务</p>';
    return;
  }
  const existingById = new Map([...target.querySelectorAll('.extract-workbench-task')]
    .map(card => [String(card.dataset?.taskId || ''), card]));
  const ordered = nextCards.map(fresh => {
    const taskId = String(fresh.dataset?.taskId || '');
    return extractWorkbenchSyncTaskCard(existingById.get(taskId), fresh);
  });
  if (!ordered.length) {
    target.innerHTML = '<p class="extract-workbench-empty">没有匹配的提链任务</p>';
    return;
  }
  const keep = new Set(ordered);
  for (const child of [...(target.childNodes || [])]) if (!keep.has(child)) target.removeChild(child);
  for (let index = 0; index < ordered.length; index += 1) {
    if (target.childNodes[index] !== ordered[index]) target.insertBefore(ordered[index], target.childNodes[index] || null);
  }
}

function extractWorkbenchRenderTasks({quiet = false} = {}) {
  const target = extractWorkbenchNode('[data-workbench-tasks]');
  if (!target) return;
  const items = Array.isArray(EXTRACT_WORKBENCH_STATE.items) ? EXTRACT_WORKBENCH_STATE.items : [];
  if (quiet) extractWorkbenchSyncTaskCards(target, items);
  else target.innerHTML = items.length ? items.map(renderExtractWorkbenchTaskCard).join('') : '<p class="extract-workbench-empty">没有匹配的提链任务</p>';
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

function extractWorkbenchCaptureQuietState(tasksNode) {
  if (!tasksNode) return null;
  const details = [...(tasksNode.querySelectorAll?.('details[open]') || [])].map(detail => {
    const card = detail.closest?.('.extract-workbench-task');
    const button = detail.querySelector?.('[data-workbench-detail]');
    const content = detail.querySelector?.('[data-workbench-detail-content]');
    const taskId = card?.dataset?.taskId || button?.dataset?.workbenchDetail;
    if (!taskId) return null;
    return {
      taskId: String(taskId),
      contentExpanded: Boolean(content && !content.classList?.contains('hidden')),
      content: content ? {innerHTML: content.innerHTML || '', textContent: content.textContent || ''} : null,
    };
  }).filter(Boolean);
  let focus = null;
  const active = document.activeElement;
  if (active && tasksNode.contains?.(active)) {
    const card = active.closest?.('.extract-workbench-task');
    const taskId = card?.dataset?.taskId;
    if (taskId && String(active.tagName || '').toUpperCase() === 'SUMMARY') focus = {taskId: String(taskId), kind: 'summary'};
    else if (taskId) {
      const focusFields = [
        ['detail', 'workbenchDetail'], ['payment-entry', 'workbenchPaymentEntry'],
        ['copy-email', 'workbenchCopyEmail'], ['copy-at', 'workbenchCopyAt'],
        ['action', 'workbenchAction'], ['link', 'workbenchLink'],
      ];
      const field = focusFields.find(([, key]) => active.dataset?.[key] !== undefined);
      if (field) focus = {taskId: String(taskId), kind: field[0], value: String(active.dataset[field[1]])};
    }
  }
  return {scrollTop: tasksNode.scrollTop || 0, details, focus};
}

function extractWorkbenchFindTaskCard(tasksNode, taskId) {
  return [...(tasksNode?.querySelectorAll?.('.extract-workbench-task') || [])]
    .find(card => String(card?.dataset?.taskId || '') === String(taskId)) || null;
}

function extractWorkbenchDetailHtml(result) {
  const events = Array.isArray(result?.events) ? result.events : [];
  return events.length ? `<ul>${events.map(event => `<li><strong>${extractWorkbenchEscape(event.label || event.stage || '事件')}</strong><span>${extractWorkbenchEscape(extractWorkbenchStatusLabel(event.status))}</span><p>${extractWorkbenchEscape(event.message || '')}</p></li>`).join('')}</ul>` : '<p>暂无阶段事件</p>';
}

function extractWorkbenchLoadTaskDetail(taskId) {
  const key = String(taskId);
  const existing = EXTRACT_WORKBENCH_DETAIL_REQUESTS.get(key);
  if (existing) return existing;
  const request = extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(key)}`)
    .then(extractWorkbenchDetailHtml)
    .finally(() => EXTRACT_WORKBENCH_DETAIL_REQUESTS.delete(key));
  EXTRACT_WORKBENCH_DETAIL_REQUESTS.set(key, request);
  return request;
}

function extractWorkbenchRestoreQuietState(tasksNode, snapshot) {
  if (!tasksNode || !snapshot) return;
  tasksNode.scrollTop = snapshot.scrollTop;
  for (const saved of snapshot.details) {
    const card = extractWorkbenchFindTaskCard(tasksNode, saved.taskId);
    const details = card?.querySelector?.('details');
    const button = card?.querySelector?.('[data-workbench-detail]');
    const target = card?.querySelector?.('[data-workbench-detail-content]');
    if (!details || !button || !target) continue;
    details.open = true;
    if (saved.contentExpanded) {
      button.setAttribute('aria-expanded', 'true');
      target.classList.remove('hidden');
      if (saved.content?.innerHTML) target.innerHTML = saved.content.innerHTML;
      else if (saved.content?.textContent) target.textContent = saved.content.textContent;
      void extractWorkbenchShowDetail(saved.taskId, button, {refresh: true});
    }
  }
  if (snapshot.focus) {
    const card = extractWorkbenchFindTaskCard(tasksNode, snapshot.focus.taskId);
    const selectors = {
      summary: 'summary', detail: '[data-workbench-detail]', 'payment-entry': '[data-workbench-payment-entry]',
      'copy-email': '[data-workbench-copy-email]', 'copy-at': '[data-workbench-copy-at]',
      action: `[data-workbench-action="${snapshot.focus.value}"]`, link: `[data-workbench-link="${snapshot.focus.value}"]`,
    };
    card?.querySelector?.(selectors[snapshot.focus.kind])?.focus?.();
  }
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

async function loadExtractWorkbench({force = false, quiet = false} = {}) {
  const root = extractWorkbenchRoot();
  if (!root) return;
  EXTRACT_WORKBENCH_ROOT = root;
  extractWorkbenchBindEvents();
  const sequence = ++EXTRACT_WORKBENCH_SEQUENCE;
  const tasksNode = extractWorkbenchNode('[data-workbench-tasks]');
  if (tasksNode && !quiet) {
    tasksNode.innerHTML = '<p class="extract-workbench-muted">加载任务中…</p>';
    tasksNode.scrollTop = 0;
  }
  try {
    await extractWorkbenchLoadConfig(force);
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    extractWorkbenchRenderProviders();
    let batchItems = [];
    if (extractWorkbenchNode('[data-workbench-batch-select]')) {
      const batches = await extractWorkbenchRequest(`/api/extract-workbench/batches?page=${EXTRACT_WORKBENCH_STATE.batchPage}&page_size=20`);
      if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
      batchItems = batches?.items || [];
      EXTRACT_WORKBENCH_STATE.batches = batchItems;
      EXTRACT_WORKBENCH_STATE.batchTotal = Number(batches?.total || 0);
      if (!EXTRACT_WORKBENCH_STATE.batchInitialized) {
        EXTRACT_WORKBENCH_STATE.batch = String(batchItems[0]?.batch_id || '');
        EXTRACT_WORKBENCH_STATE.batchInitialized = true;
      }
    }
    const batchId = EXTRACT_WORKBENCH_STATE.batch;
    const batchSummary = batchItems.find(batch => String(batch?.batch_id || '') === String(batchId || '')) || null;
    const [result, detail] = await Promise.all([
      extractWorkbenchRequest(extractWorkbenchListUrl({...EXTRACT_WORKBENCH_STATE})),
      batchId && !batchSummary ? extractWorkbenchRequest(`/api/extract-workbench/batches/${encodeURIComponent(batchId)}`) : Promise.resolve(batchSummary ? {item: batchSummary} : null),
    ]);
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, batchDetail:detail?.item || null, items: result?.items || [], counts: result?.counts || {}, total: Number(result?.total || 0), page: Number(result?.page || EXTRACT_WORKBENCH_STATE.page)};
    const quietSnapshot = quiet ? extractWorkbenchCaptureQuietState(tasksNode) : null;
    extractWorkbenchRenderBatches();
    const scrollTop = quiet ? tasksNode?.scrollTop || 0 : 0;
    if (quiet && quietSnapshot && tasksNode) quietSnapshot.scrollTop = tasksNode.scrollTop ?? quietSnapshot.scrollTop;
    extractWorkbenchRenderTasks({quiet});
    if (quiet) extractWorkbenchRestoreQuietState(tasksNode, quietSnapshot);
    else if (tasksNode) tasksNode.scrollTop = scrollTop;
    extractWorkbenchScheduleRefresh();
    if (typeof markViewReady === 'function') markViewReady('extract-workbench');
  } catch (error) {
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    if (quiet) {
      const summary = extractWorkbenchNode('[data-workbench-summary]');
      if (summary) summary.textContent = '任务暂时无法加载，正在重试…';
      extractWorkbenchScheduleRefresh({retry: true});
    } else {
      if (tasksNode) tasksNode.innerHTML = `<p class="extract-workbench-error">${extractWorkbenchEscape(error?.message || '加载失败，请刷新后重试')}</p>`;
      const summary = extractWorkbenchNode('[data-workbench-summary]');
      if (summary) summary.textContent = '任务暂时无法加载';
    }
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
    extractWorkbenchRenderAccountSources();
    await extractWorkbenchLoadAccounts();
  } catch (_) {
    const feedback = extractWorkbenchNode('[data-workbench-create-feedback]');
    if (feedback) feedback.textContent = '平台配置加载失败，请关闭后重试。';
  }
}

async function extractWorkbenchLoadAccounts() {
  const target = extractWorkbenchNode('[data-workbench-accounts]');
  if (!target) return;
  const sequence = ++EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE;
  target.innerHTML = '<p class="extract-workbench-muted">正在统计符合条件的账号…</p>';
  const filters = extractWorkbenchCandidateFilters();
  const limit = Number(extractWorkbenchNode('[data-workbench-batch-limit]')?.value || 100);
  const signature = extractWorkbenchCandidateSignature();
  EXTRACT_WORKBENCH_STATE.preview = null;
  EXTRACT_WORKBENCH_STATE.previewSignature = '';
  extractWorkbenchRenderModes();
  const params = new URLSearchParams({...filters, limit:String(limit)});
  try {
    if (!Number.isInteger(limit) || limit < 1 || limit > 5000) throw new Error('本批运行数量须为 1 至 5000 的整数');
    const result = await extractWorkbenchRequest(`/api/extract-workbench/candidates?${params.toString()}`);
    if (sequence !== EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE) return;
    const accounts = Array.isArray(result?.items) ? result.items : [];
    EXTRACT_WORKBENCH_STATE.accountsLoaded = true;
    EXTRACT_WORKBENCH_STATE.preview = result;
    EXTRACT_WORKBENCH_STATE.previewSignature = signature;
    const summary = extractWorkbenchNode('[data-workbench-candidate-summary]');
    if (summary) summary.textContent = `匹配 ${Number(result?.total || 0).toLocaleString('zh-CN')} 个可用账号，本批计划运行 ${Number(result?.selected_count || 0).toLocaleString('zh-CN')} 个；预览前 ${accounts.length} 个。`;
    target.innerHTML = accounts.length ? `<table><thead><tr><th>账号</th><th>来源</th><th>注册时间</th><th>套餐优惠</th><th>提链状态</th></tr></thead><tbody>${accounts.map(account => {
      const email = extractWorkbenchEscape(account.email || '账号未记录');
      const source = extractWorkbenchAccountSources()[account.email_source] || account.email_source || '未记录';
      const promotion = ['free_trial', 'half_price', 'other_discount', 'other_promo'].includes(String(account.account_promotion_value || ''))
        ? extractWorkbenchPromotionLabel(account.account_promotion_value) : '—';
      return `<tr><td title="${email}">${email}</td><td>${extractWorkbenchEscape(source)}</td><td>${extractWorkbenchEscape(String(account.created_at || '').slice(0, 10) || '—')}</td><td>${extractWorkbenchEscape(promotion)}</td><td>${extractWorkbenchEscape(account.extract_link_status ? extractWorkbenchStatusLabel(account.extract_link_status) : '尚未提链')}</td></tr>`;
    }).join('')}</tbody></table>` : '<p class="extract-workbench-empty">没有匹配的可用账号，请调整筛选条件</p>';
    extractWorkbenchRenderModes();
  } catch (error) {
    if (sequence !== EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE) return;
    target.innerHTML = `<p class="extract-workbench-error">账号列表加载失败：${extractWorkbenchEscape(error?.message || '请重试')}</p>`;
    const summary = extractWorkbenchNode('[data-workbench-candidate-summary]');
    if (summary) summary.textContent = '预览未完成，请检查筛选条件后重试。';
  }
}

function extractWorkbenchCandidateFilters() {
  const value = selector => extractWorkbenchNode(selector)?.value?.trim() || '';
  const promotion = extractWorkbenchPromotionValue(value('[data-workbench-promotion]'));
  return {query:value('[data-workbench-account-query]'),source:value('[data-workbench-account-source]'),date_from:value('[data-workbench-date-from]'),date_to:value('[data-workbench-date-to]'),extract_status:value('[data-workbench-extract-status]') || 'not_succeeded',promotion};
}

function extractWorkbenchCandidateSignature() {
  return JSON.stringify({filters:extractWorkbenchCandidateFilters(),limit:Number(extractWorkbenchNode('[data-workbench-batch-limit]')?.value || 100)});
}

function extractWorkbenchInvalidatePreview() {
  ++EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE;
  EXTRACT_WORKBENCH_STATE.preview = null;
  EXTRACT_WORKBENCH_STATE.previewSignature = '';
  const summary = extractWorkbenchNode('[data-workbench-candidate-summary]');
  if (summary) summary.textContent = '筛选条件已变更，请重新预览匹配账号。';
  extractWorkbenchRenderCandidatePromotion();
  extractWorkbenchRenderModes();
}

function extractWorkbenchSubmissionId() {
  const crypto = window.crypto || globalThis.crypto;
  if (crypto?.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

async function extractWorkbenchSubmit() {
  const providerId = extractWorkbenchNode('[data-workbench-provider]')?.value || '';
  const requestedMode = extractWorkbenchNode('[data-workbench-mode]')?.value || '';
  const requestedType = extractWorkbenchNode('[data-workbench-type]')?.value || '';
  const selected = extractWorkbenchCreatePayload([], providerId, requestedMode, requestedType);
  const count = Number(EXTRACT_WORKBENCH_STATE.preview?.selected_count || 0);
  if (EXTRACT_WORKBENCH_STATE.creating || !count || !selected.mode || !selected.type || EXTRACT_WORKBENCH_STATE.previewSignature !== extractWorkbenchCandidateSignature()) return;
  const workers = extractWorkbenchBatchWorkers();
  const feedback = extractWorkbenchNode('[data-workbench-create-feedback]');
  if (workers === null) {
    if (feedback) feedback.textContent = `批次并发请输入 1 到 ${extractWorkbenchBatchWorkersMax()} 的整数。`;
    return;
  }
  const payload = {workers,title:extractWorkbenchNode('[data-workbench-batch-title]')?.value?.trim() || '',provider_id:selected.provider_id,mode:selected.mode,type:selected.type,filters:extractWorkbenchCandidateFilters(),limit:Number(extractWorkbenchNode('[data-workbench-batch-limit]')?.value || 100)};
  const button = extractWorkbenchNode('[data-workbench-create]');
  if (button) button.disabled = true;
  if (payload.mode === 'auto_payment' && !window.confirm(`将为本批约 ${count} 个账号启用自动支付任务，确认继续？`)) {
    if (button) button.disabled = false;
    return;
  }
  EXTRACT_WORKBENCH_STATE.creating = true;
  try {
    const signature = JSON.stringify(payload);
    if (EXTRACT_WORKBENCH_STATE.submission?.signature !== signature) {
      EXTRACT_WORKBENCH_STATE.submission = {signature, id:extractWorkbenchSubmissionId()};
    }
    payload.submission_id = EXTRACT_WORKBENCH_STATE.submission.id;
    const result = await extractWorkbenchRequest('/api/extract-workbench/batches', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    if (feedback) feedback.textContent = `已创建批次，入队 ${Number(result?.started || 0)} 个任务，跳过 ${Number(result?.skipped || 0)} 个，提交失败 ${Number(result?.failed || 0)} 个。`;
    if (result?.batch_id) {
      EXTRACT_WORKBENCH_STATE.batchPage = 1;
      await extractWorkbenchSwitchBatch(result.batch_id);
      extractWorkbenchNode('[data-workbench-create-dialog]')?.close();
      if (typeof showToast === 'function') showToast(`批次已创建，${Number(result.started || 0)} 个提链任务已入队`);
    }
    EXTRACT_WORKBENCH_STATE.preview = null;
    EXTRACT_WORKBENCH_STATE.previewSignature = '';
    EXTRACT_WORKBENCH_STATE.submission = null;
  } catch (error) {
    if (feedback) feedback.textContent = `${error?.message || '提交未完成'}；可重试获取同一批次的提交结果。`;
  } finally {
    EXTRACT_WORKBENCH_STATE.creating = false;
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

function extractWorkbenchPaymentUrl(value, {image = false} = {}) {
  const text = String(value || '').trim();
  if (image && /^data:image\/(?:png|svg\+xml);base64,[a-z0-9+/=\s]+$/i.test(text)) return text;
  try {
    const parsed = new URL(text);
    return ['https:', 'http:'].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : '';
  } catch (_) { return ''; }
}

function extractWorkbenchPaymentQrSources(entry) {
  return [...new Set([entry?.qr_image_url_png, entry?.qr_image_url_svg]
    .map(value => extractWorkbenchPaymentUrl(value, {image:true})).filter(Boolean))];
}

function extractWorkbenchPaymentStatus(value, {plus = false} = {}) {
  const key = String(value ?? '').toLowerCase();
  const labels = plus
    ? {true:'平台显示已开通', confirmed:'平台显示已开通', plus:'平台显示已开通', active:'平台显示已开通', activated:'平台显示已开通', success:'平台显示已开通', succeeded:'平台显示已开通', false:'平台尚未确认', waiting_for_payment:'等待支付后核验', pending:'平台待核验', unknown:'平台待核验', not_started:'平台尚未核验', not_confirmed:'平台尚未确认', failed:'平台核验失败', not_applicable:'不适用'}
    : {paid:'支付成功', succeeded:'支付成功', success:'支付成功', pending:'待支付', unpaid:'未支付', not_started:'未发起支付', pending_payment:'待支付', requires_action:'等待扫码或付款', requires_confirmation:'等待支付确认', requires_payment_method:'需要支付方式', running:'支付处理中', processing:'支付处理中', failed:'支付失败', canceled:'已取消', cancelled:'已取消', expired:'已过期', unknown:'待确认'};
  return labels[key] || (key ? String(value) : '平台未返回');
}

function renderExtractWorkbenchPaymentEntry(entry = {}) {
  const pageUrl = extractWorkbenchPaymentUrl(entry.payment_page_url);
  const paymentUrl = extractWorkbenchPaymentUrl(entry.payment_url);
  const qrData = String(entry.qr_data || '');
  const images = extractWorkbenchPaymentQrSources(entry);
  const alternative = pageUrl || paymentUrl ? '可使用上方支付链接。' : qrData ? '可复制下方二维码原文。' : '平台未返回其他支付入口。';
  const hasAmount = entry.amount !== null && entry.amount !== undefined && entry.amount !== '';
  const amount = hasAmount ? `${String(entry.amount)}${entry.currency ? ` ${String(entry.currency).toUpperCase()}` : ''}` : '平台未返回';
  const field = (label, value, key, url = false) => `<section class="extract-workbench-payment-field"><div class="extract-workbench-payment-field-head"><h3>${label}</h3>${value ? `<div><button type="button" class="btn" data-workbench-payment-copy="${key}" aria-label="复制${label}">${extractWorkbenchIcon('copy')}复制</button>${url ? `<a class="btn" href="${extractWorkbenchEscape(value)}" target="_blank" rel="noopener noreferrer" aria-label="打开${label}">${extractWorkbenchIcon('external')}打开</a>` : ''}</div>` : ''}</div>${value ? `<pre>${extractWorkbenchEscape(value)}</pre>` : '<p class="extract-workbench-payment-missing">平台未返回</p>'}</section>`;
  return `<dl class="extract-workbench-payment-facts"><div><dt>金额</dt><dd>${extractWorkbenchEscape(amount)}</dd></div><div><dt>平台支付状态</dt><dd>${extractWorkbenchEscape(extractWorkbenchPaymentStatus(entry.payment_status))}</dd></div><div><dt>平台 Plus 核验</dt><dd>${extractWorkbenchEscape(extractWorkbenchPaymentStatus(entry.platform_plus_status, {plus:true}))}</dd></div><div><dt>有效期至</dt><dd>${entry.expires_at ? extractWorkbenchEscape(extractWorkbenchTime(entry.expires_at)) : '平台未返回'}</dd></div></dl>
    <p class="extract-workbench-payment-hint">平台 Plus 状态供参考，本地到账以卡片中的“Plus 到账核验”为准。</p>
    ${field('支付页面', pageUrl, 'payment_page_url', true)}${field('支付入口', paymentUrl, 'payment_url', true)}
    <section class="extract-workbench-payment-qr"><h3>支付二维码</h3>${images.length ? `<img src="${extractWorkbenchEscape(images[0])}" alt="平台返回的支付二维码" width="208" height="208" referrerpolicy="no-referrer" data-workbench-payment-qr><p class="extract-workbench-payment-missing" data-workbench-payment-qr-fallback hidden>二维码图片加载失败。${alternative}</p>` : `<p class="extract-workbench-payment-missing">${qrData ? '平台未返回二维码图片，可复制下方二维码原文。' : `平台未返回二维码。${alternative}`}</p>`}</section>
    ${field('二维码原文', qrData, 'qr_data')}`;
}

function extractWorkbenchPaymentQrError(image) {
  const sources = extractWorkbenchPaymentQrSources(EXTRACT_WORKBENCH_PAYMENT_ENTRY);
  const index = Number(image.dataset.workbenchQrIndex || 0) + 1;
  image.dataset.workbenchQrIndex = String(index);
  if (sources[index]) { image.src = sources[index]; return; }
  image.hidden = true;
  const fallback = image.parentElement?.querySelector('[data-workbench-payment-qr-fallback]');
  if (fallback) fallback.hidden = false;
}

function extractWorkbenchPaymentDialog() {
  const root = extractWorkbenchRoot();
  if (!root) return null;
  let dialog = root.querySelector('[data-workbench-payment-dialog]');
  if (dialog) return dialog;
  dialog = document.createElement('dialog');
  dialog.className = 'extract-workbench-payment-dialog';
  dialog.setAttribute('data-workbench-payment-dialog', '');
  dialog.setAttribute('aria-labelledby', 'extractWorkbenchPaymentTitle');
  dialog.innerHTML = `<header class="extract-workbench-payment-head"><div><h2 id="extractWorkbenchPaymentTitle">支付入口</h2><p data-workbench-payment-task></p></div><button type="button" class="extract-workbench-dialog-close" data-workbench-close-payment aria-label="关闭支付入口" autofocus>${extractWorkbenchIcon('close')}</button></header><div data-workbench-payment-content aria-live="polite"></div>`;
  dialog.addEventListener('close', () => {
    EXTRACT_WORKBENCH_PAYMENT_SEQUENCE += 1;
    EXTRACT_WORKBENCH_PAYMENT_ENTRY = null;
    dialog.querySelector('[data-workbench-payment-content]').textContent = '';
    const trigger = EXTRACT_WORKBENCH_PAYMENT_TRIGGER?.isConnected ? EXTRACT_WORKBENCH_PAYMENT_TRIGGER
      : Array.from(root.querySelectorAll?.('[data-workbench-payment-entry]') || []).find(node => node.dataset.workbenchPaymentEntry === dialog.dataset.workbenchTaskId);
    trigger?.focus();
    EXTRACT_WORKBENCH_PAYMENT_TRIGGER = null;
  });
  dialog.addEventListener('error', event => {
    if (event.target.matches('[data-workbench-payment-qr]')) extractWorkbenchPaymentQrError(event.target);
  }, true);
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  root.appendChild(dialog);
  return dialog;
}

async function extractWorkbenchShowPaymentEntry(taskId, button) {
  const dialog = extractWorkbenchPaymentDialog();
  if (!dialog) return;
  const sequence = ++EXTRACT_WORKBENCH_PAYMENT_SEQUENCE;
  EXTRACT_WORKBENCH_PAYMENT_ENTRY = null;
  dialog.dataset.workbenchTaskId = String(taskId);
  if (button && !dialog.open) EXTRACT_WORKBENCH_PAYMENT_TRIGGER = button;
  const content = dialog.querySelector('[data-workbench-payment-content]');
  dialog.querySelector('[data-workbench-payment-task]').textContent = `任务 #${taskId} · 查看平台返回的链接与二维码`;
  content.setAttribute('aria-busy', 'true');
  content.innerHTML = '<p class="extract-workbench-payment-message" role="status">正在读取支付入口…</p>';
  if (!dialog.open) dialog.showModal();
  try {
    const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(taskId)}/payment-entry`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({}),
    });
    if (sequence !== EXTRACT_WORKBENCH_PAYMENT_SEQUENCE || !dialog.open) return;
    if (result?.ok === false || !result?.entry || typeof result.entry !== 'object') throw new Error(result?.error || '服务端未返回支付入口');
    EXTRACT_WORKBENCH_PAYMENT_ENTRY = result.entry;
    content.innerHTML = renderExtractWorkbenchPaymentEntry(result.entry);
  } catch (error) {
    if (sequence !== EXTRACT_WORKBENCH_PAYMENT_SEQUENCE || !dialog.open) return;
    content.innerHTML = `<div class="extract-workbench-payment-message" role="alert"><p>${extractWorkbenchEscape(error?.message || '支付入口读取失败')}</p><button type="button" class="btn" data-workbench-payment-entry="${extractWorkbenchEscape(taskId)}">重新读取</button></div>`;
  } finally {
    if (sequence === EXTRACT_WORKBENCH_PAYMENT_SEQUENCE) content.setAttribute('aria-busy', 'false');
  }
}

async function extractWorkbenchCopyPaymentEntry(key) {
  if (!['payment_page_url', 'payment_url', 'qr_data'].includes(key)) return;
  const value = key === 'qr_data' ? String(EXTRACT_WORKBENCH_PAYMENT_ENTRY?.qr_data || '')
    : extractWorkbenchPaymentUrl(EXTRACT_WORKBENCH_PAYMENT_ENTRY?.[key]);
  if (!value) return;
  try { await navigator.clipboard.writeText(value); showToast?.('已复制'); }
  catch (_) { window.prompt('复制支付入口内容', value); }
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

async function extractWorkbenchShowDetail(taskId, button, {refresh = false} = {}) {
  const card = button?.closest('.extract-workbench-task');
  const target = card?.querySelector('[data-workbench-detail-content]');
  if (!target) return;
  if (!refresh && !target.classList.contains('hidden')) {
    target.classList.add('hidden');
    button.setAttribute('aria-expanded', 'false');
    return;
  }
  target.classList.remove('hidden');
  button.setAttribute('aria-expanded', 'true');
  if (!refresh) target.textContent = '正在读取安全任务详情…';
  try {
    target.innerHTML = await extractWorkbenchLoadTaskDetail(taskId);
  } catch (error) {
    if (!refresh || !target.innerHTML) target.textContent = error?.message || '详情读取失败';
  }
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
    const closePayment = event.target.closest('[data-workbench-close-payment]');
    if (closePayment) { extractWorkbenchNode('[data-workbench-payment-dialog]')?.close(); return; }
    const paymentCopy = event.target.closest('[data-workbench-payment-copy]');
    if (paymentCopy) { void extractWorkbenchCopyPaymentEntry(paymentCopy.dataset.workbenchPaymentCopy); return; }
    const paymentEntry = event.target.closest('[data-workbench-payment-entry]');
    if (paymentEntry) { void extractWorkbenchShowPaymentEntry(paymentEntry.dataset.workbenchPaymentEntry, paymentEntry); return; }
    const allBatches = event.target.closest('[data-workbench-all-batches]');
    if (allBatches) { void extractWorkbenchSwitchBatch(''); return; }
    const batchPage = event.target.closest('[data-workbench-batch-page]');
    if (batchPage) {
      EXTRACT_WORKBENCH_STATE.batchPage = Math.max(1, EXTRACT_WORKBENCH_STATE.batchPage + (batchPage.dataset.workbenchBatchPage === 'next' ? 1 : -1));
      void loadExtractWorkbench({force:true}); return;
    }
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
    if (event.target.matches('[data-workbench-batch-select]')) { void extractWorkbenchSwitchBatch(event.target.value); return; }
    if (event.target.matches('[data-workbench-account-source], [data-workbench-date-from], [data-workbench-date-to], [data-workbench-extract-status], [data-workbench-promotion], [data-workbench-batch-limit]')) extractWorkbenchInvalidatePreview();
    if (event.target.matches('[data-workbench-filter-provider], [data-workbench-filter-mode]')) extractWorkbenchApplyFilters();
    if (event.target.matches('[data-workbench-provider]')) { extractWorkbenchRenderModes(); extractWorkbenchRenderLinkTypes(); return; }
    if (event.target.matches('[data-workbench-mode], [data-workbench-type]')) extractWorkbenchRenderModes();
  });
  root.addEventListener('input', event => {
    if (event.target.matches('[data-workbench-batch-workers]')) {
      EXTRACT_WORKBENCH_STATE.batchWorkersInitialized = true;
      extractWorkbenchRenderBatchWorkers();
      extractWorkbenchRenderModes();
    }
    if (event.target.matches('[data-workbench-account-query], [data-workbench-batch-limit], [data-workbench-date-from], [data-workbench-date-to], [data-workbench-promotion]')) extractWorkbenchInvalidatePreview();
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
