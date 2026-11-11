const EXTRACT_WORKBENCH_PAGE_SIZE = 20;
let EXTRACT_WORKBENCH_ROOT = null;
let EXTRACT_WORKBENCH_CONFIG = null;
let EXTRACT_WORKBENCH_STATE = {page: 1, status: '', provider: '', mode: '', query: '', selectedAccounts: new Set(), items: [], total: 0, counts: {}, batch:'', batches:[], batchPage:1, batchTotal:0, batchInitialized:false, batchDetail:null, cancellingBatch:'', preview:null, previewSignature:'', creating:false, submission:null, batchWorkersInitialized:false};
let EXTRACT_WORKBENCH_SEQUENCE = 0;
let EXTRACT_WORKBENCH_BATCHES_AT = 0;
let EXTRACT_WORKBENCH_BATCHES_PAGE = 0;
let EXTRACT_WORKBENCH_RENDER_SIGNATURE = "";
let EXTRACT_WORKBENCH_TABLE_SIGNATURE = "";
let EXTRACT_WORKBENCH_ACCOUNT_SEQUENCE = 0;
let EXTRACT_WORKBENCH_CONFIG_PROMISE = null;
let EXTRACT_WORKBENCH_BOUND = false;
let EXTRACT_WORKBENCH_QUERY_TIMER = null;
let EXTRACT_WORKBENCH_POLL_TIMER = null;
let EXTRACT_WORKBENCH_DETAIL_REQUESTS = new Map();
let EXTRACT_WORKBENCH_PAYMENT_ENTRY = null;
let EXTRACT_WORKBENCH_DRAWER_TRIGGER = null;
const EXTRACT_WORKBENCH_SELECTED = new Set();
let EXTRACT_WORKBENCH_QUOTA_CACHE = {at: 0, value: null};
let EXTRACT_WORKBENCH_PAYMENT_SEQUENCE = 0;
let EXTRACT_WORKBENCH_PAYMENT_TRIGGER = null;
const EXTRACT_WORKBENCH_PROVIDER_LABELS = {legacy:'虾扯蛋链', lumen:'Lumen Flow', lumen_flow:'Lumen Flow', huanguang:'幻光提链', anguang:'暗光（XXSYUN 一条龙）'};
const EXTRACT_WORKBENCH_PROVIDER_SHORT_LABELS = {legacy:'其他', lumen:'流光', lumen_flow:'流光', huanguang:'幻光', anguang:'暗光'};
const EXTRACT_WORKBENCH_LINK_TYPE_LABELS = {
  pix: 'PIX', upi: 'UPI', gopay: 'GoPay', momo: 'MOMO', gcash: 'GCash',
  paypal: 'PayPal', ideal: 'iDEAL', ideal_short: 'iDEAL Short', kakao_pay: 'Kakao Pay',
  ph_short: 'PH Short',
};
const EXTRACT_WORKBENCH_PROMOTION_LABELS = {
  eligible: '全部可提链优惠', all: '全部（有无优惠）', free_trial: '免费试用', half_price: '半价',
  other_discount: '其他折扣', other_promo: '其他优惠', none: '无优惠',
};

const EXTRACT_WORKBENCH_STATUS_LABELS = {
  pending: '等待执行', queued: '排队中', running: '运行中', success: '已完成', failed: '失败',
  passed: '预检通过', succeeded: '已完成', waiting: '等待中', settling: '收尾中', cancelling: '取消中', cancelled: '已取消',
  skipped: '已跳过', paid: '支付成功', unpaid: '未支付', pending_payment: '待支付',
  confirmed: 'Plus 已确认', plus: 'Plus 已确认', not_confirmed: 'Plus 未确认',
  unknown: '待确认', request_unknown: '结果待确认', unavailable: '未启用', not_applicable: '不适用',
  query_stopped: '已停止查询', waiting_sync: '等待平台同步',
  awaiting_payment: '待支付', processing_payment: '支付中', expired: '已过期',
  not_started: '未开始', checking: '核验中', unavailable: '无法确认',
};
const EXTRACT_WORKBENCH_FILTERS = [
  ['', '全部'], ['processing', '处理中'], ['awaiting_payment', '待支付'],
  ['needs_review', '待核对'], ['extraction_succeeded', '已出链'],
  ['plus_confirmed', '已完成'], ['failed', '失败'],
];
const EXTRACT_WORKBENCH_PAYMENT_PHASE_LABELS = {
  not_started: '未开始', awaiting_payment: '待支付', processing: '支付中',
  paid: '已支付', failed: '支付失败', expired: '已过期', unknown: '结果未知',
};
const EXTRACT_WORKBENCH_PLUS_STATE_LABELS = {
  unknown: '未核验', checking: '核验中', confirmed: '已到账',
  not_confirmed: '未到账', unavailable: '无法确认',
};

function extractWorkbenchEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function extractWorkbenchProviderShortLabel(providerId, fallback = '') {
  const key = String(providerId || 'legacy');
  return EXTRACT_WORKBENCH_PROVIDER_SHORT_LABELS[key] || fallback || EXTRACT_WORKBENCH_PROVIDER_LABELS[key] || key;
}

function extractWorkbenchMaskEmail(value) {
  const email = String(value || '账号未记录');
  const at = email.lastIndexOf('@');
  if (at <= 0) return email;
  return `${email.slice(0, 1)}***${email.slice(at)}`;
}

function extractWorkbenchShortTime(value) {
  const date = new Date(value || '');
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai', hour:'2-digit', minute:'2-digit', hour12:false}).format(date);
}

function extractWorkbenchRenderDesignClock() {
  const target = extractWorkbenchNode('[data-ewd-clock]');
  if (!target) return;
  target.textContent = new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date()).replaceAll('/', '-');
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

function extractWorkbenchStageClass(state) {
  return state === 'done' ? 'success' : state === 'failed' ? 'danger'
    : state === 'running' ? 'active' : state === 'warning' ? 'warning' : 'muted';
}

function extractWorkbenchWaitLabel(task) {
  const start = Date.parse(task?.created_at || '');
  if (!Number.isFinite(start)) return '—';
  const finished = ['success', 'failed', 'cancelled', 'stopped', 'interrupted'].includes(String(task?.task_status || ''));
  const end = finished ? Date.parse(task?.updated_at || '') : Date.now();
  const minutes = Math.max(0, Math.floor(((Number.isFinite(end) ? end : Date.now()) - start) / 60000));
  if (minutes < 60) return `${minutes} 分`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
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
  if (paid && confirmed) return {tone:'success', state:'完成', title:'支付成功 · 到账已核实', copy:task?.payment_confirmation_source === 'local_plan_check' ? '扫码订单已完成，独立套餐查询已确认 Plus 到账' : task?.payment_confirmation_source === 'platform_order_check' ? '支付平台已核验 Plus 到账' : '平台状态与本地套餐核实分别记录', icon:'check'};
  if (paid) return {tone:'warning', state:'待核实', title:'支付成功 · 到账待核实', copy:'已记录支付成功，等待本地 Plus 到账核验', icon:'dots'};
  if (task?.payment_status === 'failed' && ['success', 'succeeded'].includes(extraction)) return {tone:'danger', state:'支付失败', title:'提链完成 · 支付失败', copy:'提链结果与支付结果分别记录，可查看任务详情', icon:'warning'};
  if (confirmed && ['auto_payment', 'manual_payment'].includes(task?.mode) && ['success', 'succeeded'].includes(extraction)) return {tone:'success', state:'Plus 已到账', title:'Plus 已到账 · 支付待确认', copy:'本地套餐已核实，平台支付结果仍待确认', icon:'check'};
  if (['success', 'succeeded'].includes(extraction)) {
    if (['request_unknown', 'attention_required'].includes(status)) return {tone:'warning', state:'待确认', title:'提链成功 · 后续结果待确认', copy:'提链结果已保留，请查看后续处理详情', icon:'warning'};
    if (['failed', 'cancelled', 'stopped'].includes(status)) return {tone:'warning', state:'待处理', title:status === 'failed' ? '提链成功 · 后续处理失败' : '提链成功 · 任务已停止', copy:'提链结果已保留，后续处理状态单独记录', icon:'warning'};
    if (task?.mode !== 'extract_only' && ['running', 'queued', 'pending_payment'].includes(task?.payment_status)) return {tone:'active', state:'支付中', title:'支付处理中', copy:'出链完成与支付结果分开统计', icon:'dots'};
    return {tone:'success', state:'完成', title:'提链成功', copy:task?.mode === 'extract_only' ? '仅提链已完成，未发起支付' : '支付链接已生成，等待完成支付', icon:'check'};
  }
  const syncState = extractWorkbenchSyncState(task);
  if (syncState === 'query_stopped') return {tone:'warning', state:'等待同步', title:'已停止查询 · 等待同步', copy:'远端任务已保留，可继续同步原任务状态', icon:'dots'};
  if (syncState === 'waiting_sync') return {tone:'muted', state:'等待同步', title:'等待平台同步', copy:'原任务已保留，到期后继续查询平台结果', icon:'dots'};
  if (['request_unknown', 'attention_required'].includes(status)) return {tone:'warning', state:'待确认', title:'平台结果 · 等待确认', copy:'请查看任务详情或同步原任务状态', icon:'warning'};
  if (['failed', 'cancelled', 'stopped'].includes(status) || extraction === 'failed') return {tone:'danger', state:status === 'cancelled' ? '已取消' : '失败', title:status === 'cancelled' ? '任务已取消' : '提链未完成', copy:'保留本次运行记录，可查看原因后重跑', icon:'warning'};
  if (status === 'queued' || status === 'waiting') return {tone:'muted', state:'排队中', title:'等待开始提链', copy:'执行前会在线查活并检查 AT', icon:'dots'};
  return {tone:'active', state:'运行中', title:'正在获取支付链接', copy:'出链完成后将显示对应平台结果', icon:'dots'};
}

function extractWorkbenchSyncState(task) {
  const status = String(task?.task_status || 'queued');
  const extraction = String(task?.extraction_status || 'pending');
  if (['request_unknown', 'attention_required'].includes(status) && ['queued', 'running'].includes(extraction)) return 'query_stopped';
  if (['queued', 'waiting'].includes(status) && ['passed', 'success', 'skipped'].includes(task?.preflight_status)
      && ['pending', 'queued', 'running', 'unknown'].includes(extraction)) return 'waiting_sync';
  return '';
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
  const extractionStatus = extractWorkbenchSyncState(task) || task?.extraction_status;
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
  const paymentSource = mode === 'auto_payment' ? extractWorkbenchPaymentSourceLabel(task) : '';
  return `<article class="extract-workbench-task" data-task-id="${taskId}" data-payment="${extractWorkbenchEscape(task?.payment_status || 'unpaid')}">
    <header class="extract-workbench-top"><div class="extract-workbench-id-line"><span class="extract-workbench-number">任务 #${taskId}</span><span class="extract-workbench-state extract-workbench-state--${outcome.tone}">${outcome.state}</span></div><span class="extract-workbench-percent">${percent === null ? '—' : `${percent}%`}</span></header>
    <div class="extract-workbench-identity"><span class="extract-workbench-email" title="${email}">${email}</span><button type="button" class="extract-workbench-copy-mini" data-workbench-copy-email="${taskId}" aria-label="复制邮箱">复制</button></div>
    <div class="extract-workbench-data-rows">
      <div class="extract-workbench-data-row"><span class="extract-workbench-data-label">提链平台</span><span class="extract-workbench-data-value extract-workbench-provider-mark"><i class="extract-workbench-provider-dot extract-workbench-provider-dot--${extractWorkbenchEscape(providerId)}" aria-hidden="true"></i>${extractWorkbenchEscape(providerLabel)}${linkType}</span></div>
      ${paymentSource ? `<div class="extract-workbench-data-row"><span class="extract-workbench-data-label">自动支付来源</span><span class="extract-workbench-data-value">${extractWorkbenchEscape(paymentSource)}</span></div>` : ''}
      ${renderExtractWorkbenchStage('preflight', '账号 / AT 预检', task?.preflight_status)}
      ${renderExtractWorkbenchStage('extraction', '提链', extractionStatus)}
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

function renderExtractWorkbenchTaskRow(task) {
  const taskId = extractWorkbenchEscape(task?.task_id || '');
  const email = String(task?.email || '账号未记录');
  const maskedEmail = extractWorkbenchEscape(extractWorkbenchMaskEmail(email));
  const providerId = String(task?.provider_id || 'legacy');
  const providerLabel = extractWorkbenchProviderShortLabel(providerId, EXTRACT_WORKBENCH_CONFIG?.providers?.find(provider => provider.id === providerId)?.label);
  const mode = String(task?.mode || 'extract_only');
  const stages = task?.stages || {};
  const prepare = stages.prepare || {state: 'pending', status: task?.preflight_status};
  const run = stages.run || {state: 'pending', status: task?.extraction_status};
  const verify = stages.verify || {state: 'pending', status: task?.plus_status};
  const halt = task?.reconcile_halt || {};
  const prepareLabel = extractWorkbenchStatusLabel(prepare.status, '未开始');
  // 运行段只说“有没有拿到链”，完成与否由核验段决定，避免“已完成 + 未到账”自相矛盾。
  const runLabel = halt.halted ? '待核对'
    : (run.status === 'success' || run.status === 'succeeded' ? '已出链' : extractWorkbenchStatusLabel(run.status, '未开始'));
  const runDetail = halt.halted
    ? (halt.label || '已停止自动同步')
    : ([run.step, run.percent === null || run.percent === undefined || run.percent === '' ? '' : `${run.percent}%`].filter(Boolean).join(' · ') || extractWorkbenchTime(task?.updated_at));
  const verifyLabel = EXTRACT_WORKBENCH_PLUS_STATE_LABELS[task?.plus_state] || extractWorkbenchStatusLabel(verify.status, '未核验');
  const paymentLabel = EXTRACT_WORKBENCH_PAYMENT_PHASE_LABELS[task?.payment_phase] || '';
  const runTone = halt.halted ? 'warning' : extractWorkbenchStageClass(run.state);
  const canPaymentEntry = task?.has_payment_entry === true || task?.has_qr === true || task?.has_payment_link === true;
  const checked = EXTRACT_WORKBENCH_SELECTED.has(String(task?.task_id));
  const isFailed = ['failed', 'cancelled', 'stopped', 'interrupted'].includes(String(task?.task_status || ''));
  const action = isFailed
    ? `<button type="button" class="btn ew-btn" data-workbench-action="retry">重试</button>`
    : canPaymentEntry
      ? `<button type="button" class="btn ew-btn ew-btn--link" data-workbench-payment-entry="${taskId}">链接</button>`
      : `<button type="button" class="btn ew-btn" data-workbench-action="sync_status">同步</button>`;
  const prepareDetail = prepare.step || `${extractWorkbenchShortTime(task?.created_at)} · 已刷 AT`;
  const verifyDetail = paymentLabel || (verify.step || '');
  return `<div class="ew-row extract-workbench-task" role="row" aria-selected="${checked}" data-selected="${checked}" data-task-id="${taskId}" data-payment="${extractWorkbenchEscape(task?.payment_status || 'unpaid')}">
    <div class="ew-cell ew-c0"><input type="checkbox" data-workbench-select="${taskId}" aria-label="选择任务 #${taskId}"${checked ? ' checked' : ''}></div>
    <div class="ew-cell ew-c1"><b title="${extractWorkbenchEscape(email)}">${maskedEmail}</b><small>#${taskId} · ${extractWorkbenchShortTime(task?.created_at)} 提交</small></div>
    <div class="ew-cell ew-c2"><span class="ew-plat"><i class="extract-workbench-provider-dot extract-workbench-provider-dot--${extractWorkbenchEscape(providerId)}"></i>${extractWorkbenchEscape(providerLabel)}</span><small>${extractWorkbenchEscape(extractWorkbenchModeLabel(mode))}</small></div>
    <div class="ew-cell ew-c3"><b class="ew-${extractWorkbenchStageClass(prepare.state)}">${extractWorkbenchEscape(prepareLabel)}</b><small>${extractWorkbenchEscape(prepareDetail)}</small></div>
    <div class="ew-cell ew-c4"><b class="ew-${runTone}">${extractWorkbenchEscape(runLabel)}</b><small>${extractWorkbenchEscape(runDetail)}</small></div>
    <div class="ew-cell ew-c5"><b class="ew-${extractWorkbenchStageClass(verify.state)}">${extractWorkbenchEscape(verifyLabel)}</b><small>${extractWorkbenchEscape(verifyDetail)}</small></div>
    <div class="ew-cell ew-c6">${extractWorkbenchEscape(extractWorkbenchWaitLabel(task))}</div>
    <div class="ew-cell ew-c7">
      ${action}
      <button type="button" class="btn ew-btn" data-workbench-detail="${taskId}" aria-expanded="false">详情</button>
    </div>
    <div class="extract-workbench-detail hidden ew-detail" data-workbench-detail-content></div>
  </div>`;
}

function extractWorkbenchRequest(endpoint, options = {}) {
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
  return Number.isInteger(maximum) && maximum >= 1 && maximum <= 50 ? maximum : 50;
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
    ? `本批最多同时运行 ${workers} 个账号，实际并发还受平台并发限制。`
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

function extractWorkbenchPaymentSourceLabel(item) {
  const source = String(item?.payment_source || '');
  if (!source) return '';
  return String(item?.payment_source_label || ({native:'平台自带', xxsyun:'XXSYUN'})[source] || '未知来源');
}

function extractWorkbenchPaymentSourceSuffix(item) {
  const label = item?.mode === 'auto_payment' ? extractWorkbenchPaymentSourceLabel(item) : '';
  return label ? ` · 自动支付来源：${label}` : '';
}

function extractWorkbenchRenderAdmission() {
  const target = extractWorkbenchNode('[data-workbench-admission]');
  if (!target) return;
  const config = EXTRACT_WORKBENCH_CONFIG || {};
  const providers = Array.isArray(config.providers) ? config.providers : [];
  const unavailable = Array.isArray(config.unavailable_providers) ? config.unavailable_providers : [];
  if (!providers.length && !unavailable.length) {
    target.innerHTML = '<p class="extract-workbench-muted">平台配置读取中…</p>';
    return;
  }
  const workers = Math.max(1, Number(extractWorkbenchNode('[data-workbench-batch-workers]')?.value || 1));
  const limit = Math.max(0, Number(extractWorkbenchNode('[data-workbench-batch-limit]')?.value || 0));
  const batchCap = 5000;
  const rows = [
    ...providers.map(provider => {
      const modes = Array.isArray(provider.modes) ? provider.modes.length : 0;
      return `<div class="ew-admission-row" data-state="ok">
        <i class="extract-workbench-provider-dot extract-workbench-provider-dot--${extractWorkbenchEscape(provider.id)}"></i>
        <span class="ew-admission-name">${extractWorkbenchEscape(provider.label || provider.id)}</span>
        <span class="ew-admission-state">可用</span>
        <span class="ew-admission-meta">模式 ${modes} 种 · 平台并发上限 ${Number(provider.concurrency || 0) || '—'} · 本批并发 ${workers} · 单批上限 ${batchCap.toLocaleString('zh-CN')}</span>
      </div>`;
    }),
    ...unavailable.map(provider => `<div class="ew-admission-row" data-state="bad">
        <i class="extract-workbench-provider-dot extract-workbench-provider-dot--${extractWorkbenchEscape(provider.id)}"></i>
        <span class="ew-admission-name">${extractWorkbenchEscape(provider.label || provider.id)}</span>
        <span class="ew-admission-state">不可用</span>
        <span class="ew-admission-meta">${extractWorkbenchEscape(provider.unavailable_reason || '连接配置无效')}</span>
      </div>`),
  ];
  const slices = limit > batchCap ? Math.ceil(limit / batchCap) : 0;
  const sliceHint = slices
    ? `<p class="ew-admission-slice">本批 ${limit.toLocaleString('zh-CN')} 个超过单批上限，提交时会自动切成 ${slices} 批 × 约 ${Math.round(limit / slices)} 个。</p>`
    : '';
  target.innerHTML = rows.join('') + sliceHint;
  extractWorkbenchRenderDesignCreateSummary();
}

function extractWorkbenchRenderDesignCreateSummary() {
  const summary = extractWorkbenchNode('[data-ewd-create-count]');
  if (!summary) return;
  const providerId = extractWorkbenchNode('[data-workbench-provider]')?.value || '';
  const provider = EXTRACT_WORKBENCH_CONFIG?.providers?.find(item => item.id === providerId);
  const mode = extractWorkbenchNode('[data-workbench-mode]')?.value || '';
  const type = extractWorkbenchNode('[data-workbench-type]')?.value || '';
  const workers = extractWorkbenchBatchWorkers();
  const previewValid = EXTRACT_WORKBENCH_STATE.previewSignature === extractWorkbenchCandidateSignature();
  const count = previewValid ? Number(EXTRACT_WORKBENCH_STATE.preview?.selected_count || 0) : 0;
  const limit = Math.max(0, Number(extractWorkbenchNode('[data-workbench-batch-limit]')?.value || 0));
  const slices = limit > 5000 ? Math.ceil(limit / 5000) : 1;
  summary.textContent = count.toLocaleString('zh-CN');
  const set = (selector, value) => { const node = extractWorkbenchNode(selector); if (node) node.textContent = value || '—'; };
  set('[data-ewd-create-provider]', provider ? extractWorkbenchProviderShortLabel(provider.id, provider.label) : '—');
  set('[data-ewd-create-mode]', mode ? extractWorkbenchModeLabel(mode) : '—');
  set('[data-ewd-create-type]', type ? extractWorkbenchLinkTypeLabel(type) : '—');
  set('[data-ewd-create-workers]', workers === null ? '—' : String(workers));
  set('[data-ewd-create-slices]', slices > 1 ? `${slices} 批 · 每批 ≤5000` : '单批');
  const ready = Boolean(provider && mode && type && count > 0 && workers !== null && !EXTRACT_WORKBENCH_STATE.creating);
  const summaryButton = extractWorkbenchNode('[data-workbench-create-summary]');
  if (summaryButton) summaryButton.disabled = !ready;
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
  if (selectedCount) selectedCount.textContent = `本批计划运行 ${count.toLocaleString('zh-CN')} 个账号${extractWorkbenchPaymentSourceSuffix({...provider, mode: modeSelect.value})}`;
  extractWorkbenchRenderDesignCreateSummary();
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
  hint.textContent = promotion === 'all'
    ? '匹配套餐优惠已查明（有或无）的活跃、未归档 free 账号；套餐待查及状态未知的账号不包含，提交前仍会在线查活。'
    : promotion === 'eligible'
      ? '仅匹配活跃、未归档且具备任一可提链优惠的 free 账号；提交前仍会在线查活。'
      : promotion === 'none'
        ? '仅匹配活跃、未归档且上次查询无优惠的 free 账号；当前优惠由提链平台判断，提交前仍会在线查活。'
        : `仅匹配活跃、未归档且具备「${label}」优惠的 free 账号；提交前仍会在线查活。`;
}

function extractWorkbenchBatchStatus(status) {
  return ({queued:'排队中',running:'运行中',success:'已完成',partial_success:'部分成功',partial:'部分完成',partial_submission:'部分入队',failed:'失败',attention_required:'待处理',cancelled:'已取消',completed:'已完成'})[status] || extractWorkbenchStatusLabel(status);
}

function extractWorkbenchRenderBatchCancel() {
  const button = extractWorkbenchNode('[data-workbench-cancel-batch]');
  if (!button) return;
  const cancelling = Boolean(EXTRACT_WORKBENCH_STATE.cancellingBatch);
  button.disabled = cancelling || !EXTRACT_WORKBENCH_STATE.batch;
  button.textContent = cancelling ? '取消中…' : '取消批次';
  button.title = cancelling ? `正在取消批次 #${EXTRACT_WORKBENCH_STATE.cancellingBatch} 的排队任务，请稍候`
    : EXTRACT_WORKBENCH_STATE.batch ? '取消当前整批排队任务（含 CDK 额度等待），运行中与已完成任务保留'
    : '请先选择一个具体批次，全部任务视图不能取消批次';
  button.setAttribute('aria-busy', String(cancelling));
}

function extractWorkbenchOverviewValue(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number.toLocaleString('zh-CN') : '—';
}

function extractWorkbenchFormatDuration(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) return '—';
  return seconds >= 60 ? `${Math.round(seconds / 60)} 分` : `${Math.round(seconds)} 秒`;
}

function extractWorkbenchFormatDurationCompact(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) return '—';
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}'${String(whole % 60).padStart(2, '0')}"`;
}

async function extractWorkbenchQuotaLine(providerIds) {
  if (!providerIds.includes('huanguang')) return {};
  if (EXTRACT_WORKBENCH_QUOTA_CACHE.value && Date.now() - EXTRACT_WORKBENCH_QUOTA_CACHE.at < 60_000) {
    return EXTRACT_WORKBENCH_QUOTA_CACHE.value;
  }
  try {
    const quota = await extractWorkbenchRequest('/api/extract-link/huanguang/cdk-quota');
    const value = quota?.ok === true ? quota : {};
    EXTRACT_WORKBENCH_QUOTA_CACHE = {at: Date.now(), value};
    return value;
  } catch (_) {
    EXTRACT_WORKBENCH_QUOTA_CACHE = {at: Date.now(), value: {}};
    return {};
  }
}

function extractWorkbenchRenderOverview(summary) {
  if (!summary) return;
  const values = {
    today_extracted: summary.today_extracted,
    awaiting_payment: summary.awaiting_payment,
    needs_review: summary.needs_review,
    today_plus_confirmed: summary.today_plus_confirmed,
  };
  for (const [key, value] of Object.entries(values)) {
    const stat = extractWorkbenchNode(`[data-stat="${key}"]`);
    if (!stat) continue;
    const target = stat.querySelector('.ew-stat-value');
    if (target) target.textContent = extractWorkbenchOverviewValue(value);
    if (key === 'needs_review') stat.dataset.hot = Number(value) > 0 ? 'true' : 'false';
  }
  const health = extractWorkbenchNode('[data-workbench-health]');
  if (!health) return;
  const configProviders = Array.isArray(EXTRACT_WORKBENCH_CONFIG?.providers) ? EXTRACT_WORKBENCH_CONFIG.providers : [];
  const stats = Array.isArray(summary.providers) ? summary.providers : [];
  const lumenId = configProviders.some(item => item.id === 'lumen') ? 'lumen'
    : configProviders.some(item => item.id === 'lumen_flow') ? 'lumen_flow' : 'lumen';
  // 设计稿固定四格：三个已接平台 + 一个“其他”占位，避免少平台时整排视觉塌陷。
  const ids = ['huanguang', 'anguang', lumenId, 'legacy'];
  void extractWorkbenchRenderHealthPanels(health, ids, stats);
}

async function extractWorkbenchRenderHealthPanels(host, providerIds, stats) {
  if (!providerIds.length) {
    host.innerHTML = '<span class="ew-health-empty">还没有可用的提链平台</span>';
    return;
  }
  const quota = await extractWorkbenchQuotaLine(providerIds);
  const byId = new Map(stats.map(item => [String(item.provider_id), item]));
  host.innerHTML = providerIds.map(id => {
    const stat = byId.get(id) || {};
    const provider = (EXTRACT_WORKBENCH_CONFIG?.providers || []).find(item => item.id === id) || {};
    const label = extractWorkbenchProviderShortLabel(id, provider.label);
    const rate = typeof stat.success_rate === 'number' ? stat.success_rate : null;
    const tone = id === 'legacy' || rate === null ? 'muted' : rate < 0.6 ? 'warn' : '';
    const statusText = id === 'legacy' ? '未启用' : rate === null ? '暂无数据' : rate < 0.6 ? '排队偏多' : '正常';
    const quotaText = id === 'huanguang' && quota?.ok === true
      ? Number(quota.extraction?.remaining ?? 0).toLocaleString('zh-CN')
      : '—';
    const quotaLabel = id === 'anguang' ? '可用积分' : id === 'lumen' || id === 'lumen_flow' ? '可用次数' : '可用额度';
    const activityLabel = id === 'anguang' ? '排队' : '在跑';
    const bar = rate === null ? 0 : Math.max(0, Math.min(100, Math.round(rate * 100)));
    return `<article class="ew-plat-card">
      <div class="ew-plat-card-h"><i class="extract-workbench-provider-dot extract-workbench-provider-dot--${extractWorkbenchEscape(id)}"></i>${extractWorkbenchEscape(label)}<span class="ew-plat-st" data-tone="${tone}">${statusText}</span></div>
      <div class="ew-plat-card-g">
        <span>${quotaLabel} <b>${quotaText}</b></span>
        <span>${activityLabel} <b>${Number((id === 'anguang' ? stat.queued_now : stat.active_now) || 0).toLocaleString('zh-CN')}</b></span>
        <span>成功率 <b>${rate === null ? '—' : `${Math.round(rate * 100)}%`}</b></span>
        <span>平均 <b>${extractWorkbenchFormatDurationCompact(stat.avg_seconds)}</b></span>
      </div>
      <div class="ew-plat-card-bar"${tone === 'warn' ? ' data-tone="warn"' : ''}><i style="width:${bar}%"></i></div>
    </article>`;
  }).join('');
}

async function loadExtractWorkbenchSummary() {
  if (!extractWorkbenchNode('[data-workbench-overview]')) return;
  try {
    const summary = await extractWorkbenchRequest('/api/extract-workbench/summary');
    if (summary?.ok === false) return;
    extractWorkbenchRenderOverview(summary);
  } catch (_) {
    /* 概览失败不影响列表主流程 */
  }
}

function extractWorkbenchRenderBatches() {
  const select = extractWorkbenchNode('[data-workbench-batch-select]');
  if (select) {
    const batches = [...EXTRACT_WORKBENCH_STATE.batches];
    const current = EXTRACT_WORKBENCH_STATE.batchDetail;
    if (current && !batches.some(batch => String(batch.batch_id) === String(current.batch_id))) batches.unshift(current);
    select.innerHTML = '<option value="">全部任务（含历史单独任务）</option>' + batches.map(batch => `<option value="${extractWorkbenchEscape(batch.batch_id)}">${extractWorkbenchEscape(batch.title || `批次 #${batch.batch_id}`)} · ${Number(batch.requested_count || 0)} 个 · ${extractWorkbenchEscape(extractWorkbenchBatchStatus(batch.status))}${extractWorkbenchEscape(extractWorkbenchPaymentSourceSuffix(batch))}</option>`).join('');
    select.value = EXTRACT_WORKBENCH_STATE.batch;
  }
  const pages = Math.max(1, Math.ceil(EXTRACT_WORKBENCH_STATE.batchTotal / 20));
  const label = extractWorkbenchNode('[data-workbench-batch-page-label]');
  if (label) label.textContent = `第 ${EXTRACT_WORKBENCH_STATE.batchPage} / ${pages} 页`;
  const previous = extractWorkbenchNode('[data-workbench-batch-page="prev"]');
  const next = extractWorkbenchNode('[data-workbench-batch-page="next"]');
  if (previous) previous.disabled = EXTRACT_WORKBENCH_STATE.batchPage <= 1;
  if (next) next.disabled = EXTRACT_WORKBENCH_STATE.batchPage >= pages;
  extractWorkbenchRenderBatchCancel();
}

function extractWorkbenchSwitchBatch(batchId) {
  clearTimeout(EXTRACT_WORKBENCH_QUERY_TIMER);
  EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, batch:String(batchId || ''), batchInitialized:true, batchDetail:null, page:1, status:'', provider:'', mode:'', query:''};
  for (const selector of ['[data-workbench-filter-provider]','[data-workbench-filter-mode]','[data-workbench-query]']) {
    const node = extractWorkbenchNode(selector);
    if (node) node.value = '';
  }
  extractWorkbenchRenderBatchCancel();
  return loadExtractWorkbench({force:true});
}

function extractWorkbenchOpenCancelDialog() {
  const batchId = EXTRACT_WORKBENCH_STATE.batch;
  if (!batchId || EXTRACT_WORKBENCH_STATE.cancellingBatch) return;
  const batch = EXTRACT_WORKBENCH_STATE.batches.find(item => String(item.batch_id) === String(batchId)) || EXTRACT_WORKBENCH_STATE.batchDetail;
  const dialog = extractWorkbenchNode('[data-workbench-cancel-dialog]');
  if (!dialog) { void extractWorkbenchCancelBatch({confirmed: true}); return; }
  const title = batch?.title || `批次 #${batchId}`;
  const scope = extractWorkbenchNode('[data-workbench-cancel-scope]');
  if (scope) scope.textContent = `将停止「${title}」里所有还没开始的排队任务，不受当前页签、筛选和分页限制。`;
  const counts = extractWorkbenchNode('[data-workbench-cancel-counts]');
  if (counts) {
    const rows = [
      ['排队中', batch?.queued_count],
      ['运行中（保留）', batch?.running_count],
      ['已完成（保留）', batch?.success_count],
      ['失败', batch?.failed_count],
    ].filter(([, value]) => Number.isFinite(Number(value)));
    counts.innerHTML = rows.map(([label, value]) => `<li><span>${label}</span><b>${Number(value).toLocaleString('zh-CN')}</b></li>`).join('');
  }
  dialog.showModal();
}

async function extractWorkbenchCancelBatch({confirmed = false} = {}) {
  const batchId = EXTRACT_WORKBENCH_STATE.batch;
  if (!batchId || EXTRACT_WORKBENCH_STATE.cancellingBatch) return;
  const batch = EXTRACT_WORKBENCH_STATE.batches.find(item => String(item.batch_id) === String(batchId)) || EXTRACT_WORKBENCH_STATE.batchDetail;
  const title = batch?.title || `批次 #${batchId}`;
  if (!confirmed && !window.confirm(`确认取消「${title}」整批尚未开始的排队任务（包含 CDK 额度等待）？\n此操作覆盖整个批次，不受当前筛选或分页限制；运行中与已完成任务保留。`)) return;
  EXTRACT_WORKBENCH_STATE.cancellingBatch = batchId;
  extractWorkbenchRenderBatchCancel();
  try {
    const result = await extractWorkbenchRequest(`/api/extract-workbench/batches/${encodeURIComponent(batchId)}/cancel`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({}),
    });
    if (result?.ok !== true) throw new Error(result?.error || '取消批次失败，请重试');
    const cancelled = Number(result.cancelled || 0);
    const skipped = Number(result.skipped || 0);
    const failed = Number(result.failed || 0);
    const message = failed > 0
      ? `批次 #${batchId}：已取消 ${cancelled} 个排队任务，跳过 ${skipped} 个，失败 ${failed} 个，可再次点击完成剩余处理。`
      : cancelled > 0 ? `批次 #${batchId}：已取消 ${cancelled} 个排队任务，跳过 ${skipped} 个。`
      : `批次 #${batchId}：没有可取消的排队任务，跳过 ${skipped} 个。`;
    await loadExtractWorkbench({force:true});
    if (typeof showToast === 'function') showToast(message);
  } catch (error) {
    if (typeof showToast === 'function') showToast(error?.message || '取消批次失败，请重试');
  } finally {
    EXTRACT_WORKBENCH_STATE.cancellingBatch = '';
    extractWorkbenchRenderBatchCancel();
  }
}

/* 轮询节奏由配置页决定：在动 / 静止 / 失败退避封顶，待核对与已结束不自动刷。 */
function extractWorkbenchPollPolicy() {
  const poll = EXTRACT_WORKBENCH_CONFIG?.poll || {};
  const active = Number(poll.active_seconds);
  const idle = Number(poll.idle_seconds);
  const backoff = Number(poll.backoff_max_seconds);
  return {
    activeMs: Number.isFinite(active) && active > 0 ? Math.min(60, active) * 1000 : 3000,
    idleMs: Number.isFinite(idle) && idle > 0 ? Math.min(300, idle) * 1000 : 15000,
    backoffMs: Number.isFinite(backoff) && backoff > 0 ? Math.min(1800, backoff) * 1000 : 300000,
  };
}

function extractWorkbenchPollDelay() {
  const counts = EXTRACT_WORKBENCH_STATE.counts || {};
  const batchCounts = EXTRACT_WORKBENCH_STATE.batchDetail?.counts || {};
  const policy = extractWorkbenchPollPolicy();
  if (Number(counts.processing || batchCounts.processing || 0) > 0) return policy.activeMs;
  if (Number(counts.awaiting_payment || batchCounts.awaiting_payment || 0) > 0) return policy.idleMs;
  return 0;
}

function extractWorkbenchScheduleRefresh({retry = false} = {}) {
  clearTimeout(EXTRACT_WORKBENCH_POLL_TIMER);
  const tab = document.getElementById('tab-extract-workbench');
  if (!tab || tab.classList.contains('hidden')) return;
  const delay = retry ? extractWorkbenchPollPolicy().idleMs : extractWorkbenchPollDelay();
  if (!delay) return;
  EXTRACT_WORKBENCH_POLL_TIMER = setTimeout(() => {
    if (document.hidden) extractWorkbenchScheduleRefresh({retry});
    else if (!tab.classList.contains('hidden')) void loadExtractWorkbench({quiet:true});
  }, delay);
}

function extractWorkbenchRenderStatusTabs() {
  const target = extractWorkbenchNode('[data-workbench-status-tabs]');
  if (!target) return;
  const counts = EXTRACT_WORKBENCH_STATE.counts || {};
  target.innerHTML = EXTRACT_WORKBENCH_FILTERS.map(([value, label]) => {
    const count = Number(counts[value || 'all'] ?? (value ? 0 : EXTRACT_WORKBENCH_STATE.total) ?? 0);
    const warn = (value === 'needs_review' || value === 'failed') && count > 0;
    return `<button type="button" class="extract-workbench-status-filter" data-workbench-status-filter="${value}" aria-pressed="${EXTRACT_WORKBENCH_STATE.status === value}"${warn ? ' data-warn="true"' : ''}><strong>${label}</strong><span>${count.toLocaleString('zh-CN')}</span></button>`;
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
  const head = '<div class="ew-table ewd-table" role="table" aria-label="提链任务"><div class="ew-head" role="row">'
    + '<span role="columnheader">账号 / 任务</span><span role="columnheader">平台 · 模式</span>'
    + '<span role="columnheader">准备</span><span role="columnheader">运行</span>'
    + '<span role="columnheader">核验</span><span role="columnheader">已等待</span>'
    + '<span role="columnheader">操作</span></div>';
  const signature = JSON.stringify({
    items: items.map(task => [
      task.task_id, task.task_status, task.extraction_status, task.payment_status,
      task.payment_phase, task.plus_state, task.progress?.percent, task.progress?.label,
      task.reconcile_halt?.reason, task.has_payment_entry, task.updated_at,
    ]),
    selected: [...EXTRACT_WORKBENCH_SELECTED].sort(),
  });
  if (!(quiet && signature === EXTRACT_WORKBENCH_TABLE_SIGNATURE)) {
    const filtered = Boolean(EXTRACT_WORKBENCH_STATE.status || EXTRACT_WORKBENCH_STATE.provider
      || EXTRACT_WORKBENCH_STATE.mode || EXTRACT_WORKBENCH_STATE.query || EXTRACT_WORKBENCH_STATE.batch);
    const emptyHtml = filtered
      ? '<p class="extract-workbench-empty">没有匹配的提链任务，换个筛选条件试试。</p>'
      : `<div class="ew-empty">
          <h3>还没有提链任务</h3>
          <p>建第一个批次，流程就三步：圈账号 → 看平台准入 → 选模式提交。提交后这里会按「处理中 / 待支付 / 待核对 / 已出链 / 已完成 / 失败」自动分桶。</p>
          <ul><li>只提链：拿到链接就结束</li><li>手动支付：出二维码，等人扫码</li><li>自动支付 + 核验：付完自动确认 Plus 是否到账</li></ul>
          <button type="button" class="btn extract-workbench-primary" data-workbench-open-create>新建批次</button>
        </div>`;
    target.innerHTML = items.length
      ? head + items.map(renderExtractWorkbenchTaskRow).join('') + '</div>'
      : emptyHtml;
    EXTRACT_WORKBENCH_TABLE_SIGNATURE = signature;
  }
  const summary = extractWorkbenchNode('[data-workbench-summary]');
  const total = Number(EXTRACT_WORKBENCH_STATE.total || 0);
  const first = items.length ? (EXTRACT_WORKBENCH_STATE.page - 1) * EXTRACT_WORKBENCH_PAGE_SIZE + 1 : 0;
  if (summary) summary.textContent = `显示 ${first}–${first ? first + items.length - 1 : 0} / ${total.toLocaleString('zh-CN')} 个任务${extractWorkbenchPaymentSourceSuffix(EXTRACT_WORKBENCH_STATE.batchDetail)}`;
  const totalTarget = extractWorkbenchNode('[data-workbench-total]');
  if (totalTarget) totalTarget.textContent = `共 ${total.toLocaleString('zh-CN')} 条`;
  extractWorkbenchRenderBatchBar();
  extractWorkbenchRenderStatusTabs();
  const page = Number(EXTRACT_WORKBENCH_STATE.page || 1);
  const pages = Math.max(1, Math.ceil(Number(EXTRACT_WORKBENCH_STATE.total || 0) / EXTRACT_WORKBENCH_PAGE_SIZE));
  const label = extractWorkbenchNode('[data-workbench-page-label]');
  if (label) label.textContent = `第 ${page} / ${pages} 页`;
  const pageNumbers = extractWorkbenchNode('[data-workbench-page-numbers]');
  if (pageNumbers) {
    const visible = new Set([1, pages, page - 1, page, page + 1].filter(value => value >= 1 && value <= pages));
    const ordered = [...visible].sort((a, b) => a - b);
    let last = 0;
    pageNumbers.innerHTML = ordered.map(value => {
      const gap = value - last > 1 ? '<span class="ewd-pager-gap">…</span>' : '';
      last = value;
      return `${gap}<button type="button" data-workbench-page-number="${value}"${value === page ? ' aria-current="page"' : ''}>${value}</button>`;
    }).join('');
  }
  const previous = extractWorkbenchNode('[data-workbench-page="prev"]');
  const next = extractWorkbenchNode('[data-workbench-page="next"]');
  if (previous) previous.disabled = page <= 1;
  if (next) next.disabled = page >= pages;
}

function extractWorkbenchRenderBatchBar() {
  const bar = extractWorkbenchNode('[data-workbench-batchbar]');
  if (!bar) return;
  const count = EXTRACT_WORKBENCH_SELECTED.size;
  bar.classList.toggle('hidden', count === 0);
  const label = bar.querySelector('[data-workbench-selected-count]');
  if (label) label.textContent = `已选 ${count} 项`;
  const all = extractWorkbenchNode('[data-workbench-select-all]');
  if (all) {
    const ids = (EXTRACT_WORKBENCH_STATE.items || []).map(item => String(item.task_id));
    all.checked = ids.length > 0 && ids.every(id => EXTRACT_WORKBENCH_SELECTED.has(id));
  }
}

function extractWorkbenchSelectedTasks() {
  return (EXTRACT_WORKBENCH_STATE.items || []).filter(item => EXTRACT_WORKBENCH_SELECTED.has(String(item.task_id)));
}

function extractWorkbenchDownloadCsv(rows, filename) {
  const header = ['任务号', '邮箱', '平台', '模式', '任务状态', '提链状态', '支付阶段', 'Plus 核验', '消息', '创建时间', '更新时间'];
  const escape = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const lines = [header.map(escape).join(',')].concat(rows.map(item => [
    item.task_id, item.email, item.provider_id, item.mode, item.task_status, item.extraction_status,
    item.payment_phase, item.plus_state, item.error || item.message || '', item.created_at, item.updated_at,
  ].map(escape).join(',')));
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function extractWorkbenchExport(filtered = true) {
  if (!filtered) {
    extractWorkbenchDownloadCsv(extractWorkbenchSelectedTasks(), 'extract-workbench-selected.csv');
    return;
  }
  const params = new URLSearchParams();
  for (const key of ['provider', 'mode', 'status', 'query', 'batch']) {
    const stateKey = key === 'provider' ? 'provider' : key === 'batch' ? 'batch' : key;
    const value = EXTRACT_WORKBENCH_STATE[stateKey];
    if (value) params.set(key === 'batch' ? 'batch_id' : key, String(value));
  }
  try {
    const response = await fetch(`/api/extract-workbench/export?${params.toString()}`, {credentials: 'same-origin'});
    if (!response.ok) throw new Error('导出失败');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'extract-workbench.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    if (typeof showToast === 'function') showToast('已导出当前筛选结果（最多 5000 条）');
  } catch (error) {
    if (typeof showToast === 'function') showToast(error?.message || '导出失败，请重试');
  }
}

async function extractWorkbenchBulk(action) {
  const ids = [...EXTRACT_WORKBENCH_SELECTED];
  if (!ids.length) return;
  if (action === 'clear') {
    EXTRACT_WORKBENCH_SELECTED.clear();
    extractWorkbenchRenderTasks({quiet:true});
    extractWorkbenchRenderBatchBar();
    return;
  }
  if (action === 'export') {
    extractWorkbenchDownloadCsv(extractWorkbenchSelectedTasks(), 'extract-workbench-selected.csv');
    return;
  }
  if (action === 'sync') {
    let accepted = 0;
    let failed = 0;
    for (const id of ids) {
      try {
        const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(id)}/actions`, {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: 'sync_status'}),
        });
        if (result?.accepted) accepted += 1; else failed += 1;
      } catch (_) {
        failed += 1;
      }
    }
    if (typeof showToast === 'function') showToast(`已提交同步：${accepted} 个${failed ? `，失败 ${failed} 个` : ''}`);
    void loadExtractWorkbench({force: true});
    return;
  }
  if (action === 'links') {
    const lines = [];
    let skipped = 0;
    for (const item of extractWorkbenchSelectedTasks()) {
      if (!item.has_payment_entry) { skipped += 1; continue; }
      try {
        const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(item.task_id)}/payment-entry`, {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({}),
        });
        const entry = result?.entry || {};
        const link = entry.payment_page_url || entry.payment_url || entry.qr_data || '';
        if (link) lines.push(`${item.email}\t${link}`); else skipped += 1;
      } catch (_) {
        skipped += 1;
      }
    }
    if (!lines.length) { if (typeof showToast === 'function') showToast('所选任务没有可复制的支付入口'); return; }
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      if (typeof showToast === 'function') showToast(`已复制 ${lines.length} 条支付链接${skipped ? `，跳过 ${skipped} 个` : ''}`);
    } catch (_) {
      if (typeof showToast === 'function') showToast('复制失败，请检查浏览器剪贴板权限');
    }
  }
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

function extractWorkbenchDetailStage(label, stage, fallback = '未开始') {
  const state = String(stage?.state || 'pending');
  const tone = state === 'done' ? 'ok' : state === 'failed' ? 'bad' : state === 'warning' ? 'warn' : state === 'running' ? 'run' : 'idle';
  const mark = {ok:'✓', bad:'×', warn:'!', run:'●', idle:'○'}[tone];
  const status = extractWorkbenchStatusLabel(stage?.status, fallback);
  const detail = stage?.step || '';
  return `<section class="ewd-detail-stage ewd-detail-stage--${tone}">
    <div class="ewd-detail-stage-head"><em>${mark}</em>${label}</div>
    <b>${extractWorkbenchEscape(status)}</b>
    <small>${extractWorkbenchEscape(detail)}</small>
  </section>`;
}

function extractWorkbenchDetailHtml(result) {
  const item = result?.item || {};
  const events = Array.isArray(result?.events) ? result.events : [];
  const stages = item.stages || {};
  const stageRow = [
    extractWorkbenchDetailStage('准备', stages.prepare, '未开始'),
    extractWorkbenchDetailStage('运行', stages.run, '未开始'),
    extractWorkbenchDetailStage('核验', stages.verify, '未开始'),
  ].join('');
  const raw = item.remote_raw && typeof item.remote_raw === 'object' ? Object.entries(item.remote_raw) : [];
  const rawLine = raw.length
    ? `<details class="ewd-raw"><summary>平台原文 <span>${raw.length} 项</span></summary><div>${raw.map(([key, value]) => `<span><b>${extractWorkbenchEscape(key)}</b><code>${extractWorkbenchEscape(value)}</code></span>`).join('')}</div></details>`
    : '';
  // 支付来源与订单是排查依据，放在三段下面一行常显，不塞进折叠区。
  const source = extractWorkbenchPaymentSourceLabel(item);
  const order = item.payment_order;
  const metaLines = [];
  if (source) metaLines.push(`自动支付来源：${source}`);
  if (order && typeof order === 'object') {
    metaLines.push(`支付订单：${order.remote_order_id || '等待平台回执'}`);
    if (order.submission_state) metaLines.push(`支付提交：${({reserved:'等待提交', submitting:'提交中', submitted:'已提交', unknown:'回执待恢复', failed:'提交失败'})[order.submission_state] || extractWorkbenchStatusLabel(order.submission_state)}`);
    metaLines.push(`支付状态：${extractWorkbenchStatusLabel(order.payment_state, '待确认')}`);
    metaLines.push(`Plus 到账核验：${extractWorkbenchStatusLabel(item.plus_status, '待确认')}`);
  }
  const metaLine = metaLines.length
    ? `<p class="ew-detail-meta ewd-detail-meta">${metaLines.map(text => `<span>${extractWorkbenchEscape(text)}</span>`).join('')}</p>`
    : '';
  const halt = item.reconcile_halt || {};
  const haltLine = halt.halted
    ? `<p class="ewd-detail-halt">${extractWorkbenchEscape(halt.label || '已停止自动续查，待核对')}${halt.reason ? `<code>${extractWorkbenchEscape(halt.reason)}</code>` : ''}</p>`
    : '';
  const timeline = events.length
    ? `<ol class="ewd-timeline">${events.map(event => {
        const time = extractWorkbenchTime(event.at || event.created_at || event.time);
        return `<li class="${String(event.status || '').toLowerCase() === 'success' ? 'is-ok' : ''}"><span></span><div><time>${extractWorkbenchEscape(extractWorkbenchShortTime(event.at || event.created_at || event.time))}</time><b>${extractWorkbenchEscape(event.label || event.stage || '事件')}</b>`
          + `${event.message ? `<small>${extractWorkbenchEscape(event.message)}</small>` : ''}</div></li>`;
      }).join('')}</ol>`
    : '<p class="extract-workbench-muted">暂无阶段事件</p>';
  const syncCopy = item?.reconcile_halt?.halted ? '自动同步已停，等待人工核对' : '自动同步按当前轮询策略继续';
  return `<div class="ewd-detail-body">
    ${metaLine}
    <div class="ewd-detail-stages">${stageRow}</div>
    ${haltLine}
    <section class="ewd-node-a" data-detail-node-a>
      <div class="ewd-node-a-head"><b>节点 A · 提链成功</b><em data-detail-node-a-time>${extractWorkbenchShortTime(item.updated_at || item.created_at)}</em><span data-detail-node-a-state>读取中…</span></div>
      <div class="ew-node-a-body" data-detail-node-a-body></div>
    </section>
    ${rawLine}
    <section class="ewd-detail-timeline"><h4>执行时间线</h4>${timeline}</section>
    <div class="ewd-detail-sync">自动同步 <b>运行 ${Number(item.run_count || 1)} 次</b><span>· ${extractWorkbenchEscape(syncCopy)}</span><button type="button" data-workbench-drawer-action="sync_status">刷新</button></div>
  </div>`;
}

function extractWorkbenchNodeAEmpty(text) {
  return `<p class="ewd-node-empty">${extractWorkbenchEscape(text)}</p>`;
}

function extractWorkbenchNodeAEntry(entry, item) {
  const qrImage = entry.qr_image_url_png || entry.qr_image_url_svg || '';
  const pageUrl = entry.payment_page_url || entry.payment_url || '';
  const qrData = entry.qr_data || '';
  const parts = [];
  parts.push(`<div class="ewd-node-a-grid"><div class="ewd-node-qr">${qrImage
    ? `<img src="${extractWorkbenchEscape(qrImage)}" alt="支付二维码" loading="lazy">`
    : qrData ? `<code>${extractWorkbenchEscape(qrData)}</code>` : `<span>二维码待平台返回</span>`}</div>`);
  const row = (label, value, copyValue = value) => `<div class="ewd-node-link"><b>${label}<button type="button" data-detail-copy="${extractWorkbenchEscape(copyValue || '')}" ${copyValue ? '' : 'disabled'}>复制</button></b><span>${extractWorkbenchEscape(value || '平台未返回')}</span></div>`;
  parts.push(`<div class="ewd-node-links">${row('支付链接', pageUrl || qrData, pageUrl || qrData)}${row('提链链接', item.extract_link || '可从任务链接操作复制', item.extract_link || '')}<div class="ewd-node-expiry">二维码有效期至 <b data-detail-countdown>—</b>${entry.amount !== undefined ? `<span>金额 ${extractWorkbenchEscape(entry.amount)}</span>` : ''}</div></div></div>`);
  return parts.join('');
}

function extractWorkbenchStartCountdown(root, expiresAt) {
  const target = root?.querySelector?.('[data-detail-countdown]');
  if (!target) return;
  const deadline = Number.isFinite(Number(expiresAt)) && Number(expiresAt) > 10_000_000_000
    ? Number(expiresAt)
    : Date.parse(String(expiresAt || ''));
  if (!Number.isFinite(deadline)) { target.textContent = '—'; return; }
  const tick = () => {
    const left = Math.floor((deadline - Date.now()) / 1000);
    if (left <= 0) { target.textContent = '已过期'; target.dataset.expired = 'true'; return; }
    target.textContent = `${String(Math.floor(left / 60)).padStart(2, '0')}:${String(left % 60).padStart(2, '0')}`;
    target.dataset.expired = 'false';
    root.__ewCountdown = setTimeout(tick, 1000);
  };
  if (root.__ewCountdown) clearTimeout(root.__ewCountdown);
  tick();
}

async function extractWorkbenchFillNodeA(root, item) {
  const body = root?.querySelector?.('[data-detail-node-a-body]');
  const state = root?.querySelector?.('[data-detail-node-a-state]');
  if (!body) return;
  if (!item?.has_payment_entry) {
    body.innerHTML = extractWorkbenchNodeAEmpty('这一步还没有支付入口');
    if (state) state.textContent = '无';
    return;
  }
  if (state) state.textContent = '读取中…';
  try {
    const result = await extractWorkbenchRequest(
      `/api/extract-workbench/tasks/${encodeURIComponent(item.task_id)}/payment-entry`,
      {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})},
    );
    const entry = result?.entry;
    if (!entry) throw new Error('没有支付入口');
    body.innerHTML = extractWorkbenchNodeAEntry(entry, item);
    if (state) state.textContent = entry.qr_data || entry.qr_image_url_png || entry.qr_image_url_svg ? '二维码可用' : '支付链接';
    extractWorkbenchStartCountdown(root, entry.expires_at);
  } catch (error) {
    body.innerHTML = extractWorkbenchNodeAEmpty(error?.message || '支付入口读取失败');
    if (state) state.textContent = '不可用';
  }
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
  extractWorkbenchRenderDesignClock();
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
    let batchItems = EXTRACT_WORKBENCH_STATE.batches || [];
    const refreshBatches = force || !quiet || EXTRACT_WORKBENCH_BATCHES_PAGE !== EXTRACT_WORKBENCH_STATE.batchPage || Date.now() - EXTRACT_WORKBENCH_BATCHES_AT >= 30000;
    if (extractWorkbenchNode('[data-workbench-batch-select]') && refreshBatches) {
      const batches = await extractWorkbenchRequest(`/api/extract-workbench/batches?page=${EXTRACT_WORKBENCH_STATE.batchPage}&page_size=20`);
      if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
      EXTRACT_WORKBENCH_BATCHES_AT = Date.now();
      EXTRACT_WORKBENCH_BATCHES_PAGE = EXTRACT_WORKBENCH_STATE.batchPage;
      batchItems = batches?.items || [];
      EXTRACT_WORKBENCH_STATE.batches = batchItems;
      EXTRACT_WORKBENCH_STATE.batchTotal = Number(batches?.total || 0);
      if (!EXTRACT_WORKBENCH_STATE.batchInitialized) {
        EXTRACT_WORKBENCH_STATE.batch = String(batchItems[0]?.batch_id || '');
        EXTRACT_WORKBENCH_STATE.batchInitialized = true;
      }
    }
    const batchId = EXTRACT_WORKBENCH_STATE.batch;
    const batchSummary = refreshBatches ? batchItems.find(batch => String(batch?.batch_id || '') === String(batchId || '')) || null : null;
    const [result, detail] = await Promise.all([
      extractWorkbenchRequest(extractWorkbenchListUrl({...EXTRACT_WORKBENCH_STATE})),
      batchId && !batchSummary ? extractWorkbenchRequest(`/api/extract-workbench/batches/${encodeURIComponent(batchId)}`) : Promise.resolve(batchSummary ? {item: batchSummary} : null),
    ]);
    if (sequence !== EXTRACT_WORKBENCH_SEQUENCE) return;
    EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, batchDetail:detail?.item || null, items: result?.items || [], counts: result?.counts || {}, total: Number(result?.total || 0), page: Number(result?.page || EXTRACT_WORKBENCH_STATE.page)};
    for (const id of [...EXTRACT_WORKBENCH_SELECTED]) {
      if (!EXTRACT_WORKBENCH_STATE.items.some(item => String(item.task_id) === id)) EXTRACT_WORKBENCH_SELECTED.delete(id);
    }
    const signature = JSON.stringify([extractWorkbenchListUrl({...EXTRACT_WORKBENCH_STATE}), result?.revision || result]);
    const unchanged = quiet && EXTRACT_WORKBENCH_RENDER_SIGNATURE === signature;
    EXTRACT_WORKBENCH_RENDER_SIGNATURE = signature;
    const quietSnapshot = quiet && !unchanged ? extractWorkbenchCaptureQuietState(tasksNode) : null;
    extractWorkbenchRenderBatches();
    void loadExtractWorkbenchSummary();
    const scrollTop = quiet ? tasksNode?.scrollTop || 0 : 0;
    if (quiet && quietSnapshot && tasksNode) quietSnapshot.scrollTop = tasksNode.scrollTop ?? quietSnapshot.scrollTop;
    if (!unchanged) extractWorkbenchRenderTasks({quiet});
    if (quiet && !unchanged) extractWorkbenchRestoreQuietState(tasksNode, quietSnapshot);
    else if (tasksNode) tasksNode.scrollTop = scrollTop;
    extractWorkbenchScheduleRefresh();
    if (typeof markViewReady === 'function') markViewReady('extract-workbench');
  } catch (error) {
    EXTRACT_WORKBENCH_RENDER_SIGNATURE = '';
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
    extractWorkbenchRenderAdmission();
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
      const promotion = ['free_trial', 'half_price', 'other_discount', 'other_promo', 'none'].includes(String(account.account_promotion_value || ''))
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
  const provider = EXTRACT_WORKBENCH_CONFIG?.providers?.find(item => item.id === providerId);
  if (payload.mode === 'auto_payment' && !window.confirm(`将为本批约 ${count} 个账号启用自动支付任务${extractWorkbenchPaymentSourceSuffix({...provider, mode: payload.mode})}，确认继续？`)) {
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

async function extractWorkbenchCopyDrawerPayment(taskId) {
  try {
    const result = await extractWorkbenchRequest(`/api/extract-workbench/tasks/${encodeURIComponent(taskId)}/payment-entry`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({}),
    });
    const entry = result?.entry || {};
    const value = entry.payment_page_url || entry.payment_url || entry.qr_data || '';
    if (!value) throw new Error('平台未返回可复制的支付链接');
    try { await navigator.clipboard.writeText(value); }
    catch (_) { window.prompt('复制支付链接', value); }
    showToast?.('支付链接已复制');
  } catch (error) {
    showToast?.(error?.message || '支付链接读取失败');
  }
}

async function extractWorkbenchCopyDetailValue(value) {
  if (!value) return;
  try { await navigator.clipboard.writeText(value); showToast?.('已复制'); }
  catch (_) { window.prompt('复制内容', value); }
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

function extractWorkbenchCloseDrawer() {
  const drawer = extractWorkbenchNode('[data-workbench-drawer]');
  const backdrop = extractWorkbenchNode('[data-workbench-drawer-backdrop]');
  const body = extractWorkbenchNode('[data-workbench-drawer-body]');
  if (body?.__ewCountdown) clearTimeout(body.__ewCountdown);
  drawer?.classList.add('hidden');
  if (drawer) delete drawer.dataset.workbenchDrawerTask;
  backdrop?.classList.add('hidden');
  document.body.classList.remove('ew-drawer-open');
  const trigger = EXTRACT_WORKBENCH_DRAWER_TRIGGER;
  EXTRACT_WORKBENCH_DRAWER_TRIGGER = null;
  trigger?.focus?.();
}

async function extractWorkbenchOpenDrawer(taskId, trigger = null) {
  const drawer = extractWorkbenchNode('[data-workbench-drawer]');
  const backdrop = extractWorkbenchNode('[data-workbench-drawer-backdrop]');
  const body = extractWorkbenchNode('[data-workbench-drawer-body]');
  const title = extractWorkbenchNode('[data-workbench-drawer-title]');
  const sub = extractWorkbenchNode('[data-workbench-drawer-sub]');
  const state = extractWorkbenchNode('[data-workbench-drawer-state]');
  if (!drawer || !body) return;
  const task = EXTRACT_WORKBENCH_STATE.items.find(item => String(item.task_id) === String(taskId)) || {};
  const providerId = String(task.provider_id || 'legacy');
  const providerLabel = EXTRACT_WORKBENCH_CONFIG?.providers?.find(item => item.id === providerId)?.label
    || EXTRACT_WORKBENCH_PROVIDER_LABELS[providerId] || providerId;
  EXTRACT_WORKBENCH_DRAWER_TRIGGER = trigger;
  if (title) title.textContent = task.email || `任务 #${taskId}`;
  if (sub) sub.textContent = `#${taskId} · ${providerLabel} · ${extractWorkbenchModeLabel(String(task.mode || 'extract_only'))}`;
  if (state) state.textContent = EXTRACT_WORKBENCH_PAYMENT_PHASE_LABELS[task.payment_phase] || EXTRACT_WORKBENCH_PLUS_STATE_LABELS[task.plus_state] || extractWorkbenchStatusLabel(task.task_status, '读取中');
  drawer.dataset.workbenchDrawerTask = String(taskId);
  drawer.classList.remove('hidden');
  backdrop?.classList.remove('hidden');
  document.body.classList.add('ew-drawer-open');
  body.innerHTML = '<p class="extract-workbench-muted">正在读取安全任务详情…</p>';
  try {
    body.innerHTML = await extractWorkbenchLoadTaskDetail(taskId);
    void extractWorkbenchFillNodeA(body, task);
  } catch (error) {
    body.innerHTML = `<p class="extract-workbench-error">${extractWorkbenchEscape(error?.message || '详情读取失败')}</p>`;
  }
  drawer.focus?.();
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
    const item = EXTRACT_WORKBENCH_STATE.items.find(task => String(task.task_id) === String(taskId)) || {};
    void extractWorkbenchFillNodeA(target, item);
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
    const designNav = event.target.closest('[data-ewd-nav]');
    if (designNav) {
      const tab = designNav.dataset.ewdNav;
      document.querySelector(`.sidebar-nav button[data-tab="${tab}"]`)?.click();
      return;
    }
    const createNav = event.target.closest('[data-ewd-create-nav]');
    if (createNav) {
      extractWorkbenchNode('[data-workbench-create-dialog]')?.close();
      document.querySelector(`.sidebar-nav button[data-tab="${createNav.dataset.ewdCreateNav}"]`)?.click();
      return;
    }
    const closePayment = event.target.closest('[data-workbench-close-payment]');
    if (closePayment) { extractWorkbenchNode('[data-workbench-payment-dialog]')?.close(); return; }
    const detailCopy = event.target.closest('[data-detail-copy]');
    if (detailCopy) { void extractWorkbenchCopyDetailValue(detailCopy.dataset.detailCopy || ''); return; }
    const drawerAction = event.target.closest('[data-workbench-drawer-action]');
    if (drawerAction) {
      const drawer = extractWorkbenchNode('[data-workbench-drawer]');
      const taskId = String(drawer?.dataset.workbenchDrawerTask || '');
      const action = drawerAction.dataset.workbenchDrawerAction;
      if (!taskId) return;
      if (action === 'copy-payment') { void extractWorkbenchCopyDrawerPayment(taskId); return; }
      if (action === 'copy-at') { void extractWorkbenchCopy(taskId, 'at'); return; }
      if (action === 'sync_status' || action === 'retry') { void extractWorkbenchTaskAction(taskId, action, drawerAction); return; }
      if (action === 'stop') { showToast?.('停止单个任务暂未开放，请在批次筛选后使用取消批次。'); return; }
    }
    const paymentCopy = event.target.closest('[data-workbench-payment-copy]');
    if (paymentCopy) { void extractWorkbenchCopyPaymentEntry(paymentCopy.dataset.workbenchPaymentCopy); return; }
    const paymentEntry = event.target.closest('[data-workbench-payment-entry]');
    if (paymentEntry) { void extractWorkbenchShowPaymentEntry(paymentEntry.dataset.workbenchPaymentEntry, paymentEntry); return; }
    const allBatches = event.target.closest('[data-workbench-all-batches]');
    if (allBatches) { void extractWorkbenchSwitchBatch(''); return; }
    const cancelBatch = event.target.closest('[data-workbench-cancel-batch]');
    if (cancelBatch) { extractWorkbenchOpenCancelDialog(); return; }
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
    const summaryCreate = event.target.closest('[data-workbench-create-summary]');
    if (summaryCreate) { void extractWorkbenchSubmit(); return; }
    const page = event.target.closest('[data-workbench-page]');
    if (page) {
      EXTRACT_WORKBENCH_STATE.page = Math.max(1, EXTRACT_WORKBENCH_STATE.page + (page.dataset.workbenchPage === 'next' ? 1 : -1));
      void loadExtractWorkbench({force:true}); return;
    }
    const pageNumber = event.target.closest('[data-workbench-page-number]');
    if (pageNumber) {
      EXTRACT_WORKBENCH_STATE.page = Math.max(1, Number(pageNumber.dataset.workbenchPageNumber || 1));
      void loadExtractWorkbench({force:true}); return;
    }
    const action = event.target.closest('[data-workbench-action]');
    if (action) {
      const taskId = action.dataset.taskId || action.closest('.extract-workbench-task')?.dataset.taskId;
      if (taskId) void extractWorkbenchTaskAction(taskId, action.dataset.workbenchAction, action);
      return;
    }
    const link = event.target.closest('[data-workbench-link]');
    if (link) { void extractWorkbenchShowLink(link.dataset.taskId, link.dataset.workbenchLink); return; }
    const detail = event.target.closest('[data-workbench-detail]');
    if (detail) { void extractWorkbenchOpenDrawer(detail.dataset.workbenchDetail, detail); return; }
    const exportAll = event.target.closest('[data-workbench-export]');
    if (exportAll) { void extractWorkbenchExport(true); return; }
    const bulk = event.target.closest('[data-workbench-bulk]');
    if (bulk) { void extractWorkbenchBulk(bulk.dataset.workbenchBulk); return; }
    if (event.target.closest('[data-workbench-drawer-close]') || event.target.closest('[data-workbench-drawer-backdrop]')) {
      extractWorkbenchCloseDrawer(); return;
    }
    const cancelClose = event.target.closest('[data-workbench-cancel-close]');
    if (cancelClose) { extractWorkbenchNode('[data-workbench-cancel-dialog]')?.close(); return; }
    const cancelConfirm = event.target.closest('[data-workbench-cancel-confirm]');
    if (cancelConfirm) {
      extractWorkbenchNode('[data-workbench-cancel-dialog]')?.close();
      void extractWorkbenchCancelBatch({confirmed: true});
      return;
    }
    const row = event.target.closest('.ew-row.extract-workbench-task');
    if (row && !event.target.closest('button, a, input, select, label, details, summary')) {
      const id = String(row.dataset.taskId || '');
      if (!id) return;
      if (EXTRACT_WORKBENCH_SELECTED.has(id)) EXTRACT_WORKBENCH_SELECTED.delete(id);
      else EXTRACT_WORKBENCH_SELECTED.add(id);
      extractWorkbenchRenderTasks({quiet:true});
      extractWorkbenchRenderBatchBar();
    }
  });
  root.addEventListener('change', event => {
    if (event.target.matches('[data-workbench-select]')) {
      const id = String(event.target.dataset.workbenchSelect || '');
      if (event.target.checked) EXTRACT_WORKBENCH_SELECTED.add(id); else EXTRACT_WORKBENCH_SELECTED.delete(id);
      extractWorkbenchRenderBatchBar();
      return;
    }
    if (event.target.matches('[data-workbench-select-all]')) {
      const ids = (EXTRACT_WORKBENCH_STATE.items || []).map(item => String(item.task_id));
      if (event.target.checked) ids.forEach(id => EXTRACT_WORKBENCH_SELECTED.add(id));
      else ids.forEach(id => EXTRACT_WORKBENCH_SELECTED.delete(id));
      extractWorkbenchRenderTasks({quiet: true});
      extractWorkbenchRenderBatchBar();
      return;
    }
    if (event.target.matches('[data-workbench-batch-select]')) { void extractWorkbenchSwitchBatch(event.target.value); return; }
    if (event.target.matches('[data-workbench-account-source], [data-workbench-date-from], [data-workbench-date-to], [data-workbench-extract-status], [data-workbench-promotion], [data-workbench-batch-limit]')) extractWorkbenchInvalidatePreview();
    if (event.target.matches('[data-workbench-filter-provider], [data-workbench-filter-mode]')) extractWorkbenchApplyFilters();
    if (event.target.matches('[data-workbench-provider]')) { extractWorkbenchRenderModes(); extractWorkbenchRenderLinkTypes(); extractWorkbenchRenderAdmission(); return; }
    if (event.target.matches('[data-workbench-batch-workers], [data-workbench-batch-limit]')) { extractWorkbenchRenderAdmission(); return; }
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
    if (event.key === 'Escape') {
      const drawer = extractWorkbenchNode('[data-workbench-drawer]');
      if (drawer && !drawer.classList.contains('hidden')) { extractWorkbenchCloseDrawer(); return; }
    }
    if (event.key === 'Enter' && event.target.matches('[data-workbench-query]')) extractWorkbenchApplyFilters();
    if (event.key === 'Enter' && event.target.matches('[data-workbench-account-query]')) void extractWorkbenchLoadAccounts();
  });
}
