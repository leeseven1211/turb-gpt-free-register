// 账号任务中心：依赖 common.js 的页面状态和工具函数，以及 accounts.js 的套餐展示辅助。
let accountTaskForceMetadataQueued = false;
let accountTaskMetadataAt = 0;
let accountTaskMetadataQuery = '';
let accountTaskListSignature = '';
let accountTaskRecentBatchCount = 0;
const ACCOUNT_TASK_TYPE_LABELS = LIST_FACET_LABELS.task_type;
Object.assign(ACCOUNT_TASK_TYPE_LABELS, {account_inspection: '账号巡检', account_inspection_batch: '巡检批次',
  sub2api_manual_upload: 'Sub2API 手动上传', sub2api_scan: 'Sub2API 异常扫描', c2a_session_reimport: 'C2A 重新导入'});
const ACCOUNT_TASK_STAGE_LABELS = LIST_FACET_LABELS.stage;
const OPERATION_TARGET_LABELS = LIST_FACET_LABELS.target_status;
const OPERATION_RECEIPTS_V2 = {items: new Map(), timer: null, loading: false, cursor: 0, observer: null, error: ''};
const OPERATION_RECEIPT_TERMINAL_V2 = new Set(['success', 'partial_success', 'failed', 'cancelled', 'stopped', 'interrupted', 'attention_required', 'deactivated', 'unsupported']);

function operationReceiptsVisibleV2() {
  const tab = document.getElementById('tab-accounts');
  return !!tab && !tab.classList.contains('hidden') && tab.dataset.moduleView === 'tasks' && !document.hidden;
}

function operationReceiptStateLabelV2(status) {
  return ({queued: '排队', running: '执行中', stopping: '停止清理中', cancelling: '停止清理中',
    success: '成功', partial_success: '部分成功', failed: '失败', cancelled: '已取消', stopped: '已停止',
    interrupted: '已中断', attention_required: '结果待确认', deactivated: '已停用', unsupported: '不支持'})[status] || '等待状态更新';
}

function renderOperationReceiptsV2() {
  const panel = document.getElementById('operationReceiptsV2');
  if (!panel) return;
  const state = OPERATION_RECEIPTS_V2;
  const items = [...state.items.values()];
  panel.hidden = !items.length;
  if (!items.length) return;
  const done = items.filter(item => OPERATION_RECEIPT_TERMINAL_V2.has(item.status));
  const success = done.filter(item => item.status === 'success').length;
  const failed = done.length - success;
  if (!panel.querySelector('[data-operation-receipt-summary]')) {
    panel.innerHTML = `<div class="operation-receipts-header-v2"><strong>本次提交的任务回执</strong>
      <p data-operation-receipt-summary role="status" aria-live="polite"></p>
      <button type="button" class="jobs-tb-btn" data-operation-receipt-refresh>刷新回执</button></div>
      <details class="operation-receipts-details-v2"><summary>查看任务与最终结果</summary>
        <ul class="operation-receipts-list-v2" aria-label="本次提交的任务结果"></ul>
      </details>`;
  }
  panel.querySelector('[data-operation-receipt-summary]').textContent = `共 ${items.length} 项 · 等待/执行 ${items.length - done.length} · 成功 ${success} · 失败或待处理 ${failed}${state.error ? `；${state.error}` : ''}`;
  const list = panel.querySelector('.operation-receipts-list-v2');
  const scrollTop = list.scrollTop;
  const active = document.activeElement;
  const focusedTask = list.contains(active) ? active.dataset.operationReceiptTask : null;
  const focusedRun = active?.dataset.operationReceiptRun || '';
  list.innerHTML = items.map(item => `<li class="operation-receipt-row-v2"><button type="button" class="jobs-tb-btn" data-operation-receipt-task="${item.task_id}" data-operation-receipt-run="${item.run_id || ''}">${esc(item.label)} #${item.task_id} · ${operationReceiptStateLabelV2(item.status)}</button>${item.message ? ` <span class="operation-receipt-message-v2">${esc(item.message)}</span>` : ''}</li>`).join('');
  if (focusedTask) {
    Array.from(list.querySelectorAll('[data-operation-receipt-task]')).find(button => button.dataset.operationReceiptTask === focusedTask && button.dataset.operationReceiptRun === focusedRun)?.focus({preventScroll: true});
  }
  list.scrollTop = scrollTop;
}

function scheduleOperationReceiptsV2() {
  const state = OPERATION_RECEIPTS_V2;
  if (state.timer !== null) clearTimeout(state.timer);
  state.timer = null;
  if (!operationReceiptsVisibleV2() || state.loading || ![...state.items.values()].some(item => !OPERATION_RECEIPT_TERMINAL_V2.has(item.status))) return;
  state.timer = setTimeout(() => { state.timer = null; refreshOperationReceiptsV2(); }, 2000);
}

async function refreshOperationReceiptsV2() {
  const state = OPERATION_RECEIPTS_V2;
  if (state.loading || !operationReceiptsVisibleV2()) return;
  const pending = [...state.items.values()].filter(item => !OPERATION_RECEIPT_TERMINAL_V2.has(item.status));
  if (!pending.length) { renderOperationReceiptsV2(); return; }
  const start = state.cursor % pending.length;
  const selected = [...pending.slice(start), ...pending.slice(0, start)].slice(0, 20);
  state.cursor = start + selected.length;
  state.loading = true;
  state.error = '';
  try {
    const results = await Promise.allSettled(selected.map(item => api(`/api/operations/${item.task_id}?include_events=0`)));
    results.forEach((result, index) => {
      const item = selected[index];
      if (result.status !== 'fulfilled' || result.value?.ok === false) {
        state.error = '部分回执暂未读到，任务仍保留，请稍后刷新';
        return;
      }
      const task = result.value.task || {};
      const run = (task.runs || []).find(run => Number(run.id) === Number(item.run_id)) || task;
      item.status = run.status || task.status || 'queued';
      const summary = run.result_summary || task.result_summary || {};
      item.message = run.error_message || task.error_message || (OPERATION_RECEIPT_TERMINAL_V2.has(item.status) ? summary.message || (item.status === 'success' ? '已确认完成' : '可打开任务查看分类原因与日志') : '');
    });
  } finally {
    state.loading = false;
    renderOperationReceiptsV2();
    scheduleOperationReceiptsV2();
  }
}

function trackAcceptedOperationsV2(references, label = '任务', options = {}) {
  const state = OPERATION_RECEIPTS_V2;
  for (const item of references || []) {
    if (!item?.accepted || !Number(item.task_id)) continue;
    const key = `${item.task_id}:${item.run_id || ''}`;
    state.items.set(key, {task_id: Number(item.task_id), run_id: Number(item.run_id) || null,
      label, status: item.status || 'queued', message: ''});
  }
  const tab = document.getElementById('tab-accounts');
  if (tab && !state.observer) {
    const sync = () => { renderOperationReceiptsV2(); if (operationReceiptsVisibleV2()) refreshOperationReceiptsV2(); else scheduleOperationReceiptsV2(); };
    state.observer = new MutationObserver(sync);
    state.observer.observe(tab, {attributes: true, attributeFilter: ['class', 'data-module-view']});
    document.addEventListener('visibilitychange', sync);
    document.getElementById('operationReceiptsV2')?.addEventListener('click', event => {
      const button = event.target.closest('[data-operation-receipt-task], [data-operation-receipt-refresh]');
      if (!button) return;
      if (button.dataset.operationReceiptTask) openAccountTaskLog(Number(button.dataset.operationReceiptTask), Number(button.dataset.operationReceiptRun) || null);
      else refreshOperationReceiptsV2();
    });
  }
  if (options.navigate !== false) return showOperationReceiptsV2();
  renderOperationReceiptsV2();
  refreshOperationReceiptsV2();
}

function showOperationReceiptsV2() {
  const filter = document.getElementById('accountTaskTypeFilterV2');
  if (filter) filter.value = '';
  activateTab('tasks');
  renderOperationReceiptsV2();
  refreshOperationReceiptsV2();
}
function formatTaskDuration(ms) {
  if (ms == null || ms === '') return '-';
  const value = Number(ms);
  if (!Number.isFinite(value) || value < 0) return '-';
  if (value < 1000) return `${Math.round(value)}ms`;
  const seconds = Math.round(value / 100) / 10;
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}
function accountTaskErrorDisplayText(info, raw = '') {
  const summary = taskErrorDisplayText(info, raw);
  const cause = String(info?.cause_summary || '').trim();
  return cause && !String(summary).includes(cause) ? `${summary} · ${cause}` : summary;
}
function accountTaskErrorDisplayTitle(info, raw = '') {
  const title = taskErrorDisplayTitle(info, raw);
  const cause = String(info?.cause_summary || '').trim();
  return cause && !String(title).includes(cause)
    ? `${title} · ${info.cause_display_code ? `${info.cause_display_code} · ` : ''}${cause}` : title;
}
function accountTaskAdmissionReasons(task) {
  if (Array.isArray(task?.admission_wait_reasons) && task.admission_wait_reasons.length) return task.admission_wait_reasons;
  return task?.admission_wait_reason ? [{code: task.admission_wait_reason}] : [];
}
function accountTaskAdmissionReasonText(reason) {
  const code = typeof reason === 'string' ? reason : reason?.code;
  const labels = {
    executor_capacity: '等待执行承载空位', resource_capacity: '等待业务资源空位',
    global_capacity: '等待全局空位', type_capacity: '等待本类空位',
    batch_paused: '等待批次继续', batch_capacity: '等待当前批次空位', provider_capacity: '等待平台空位',
    account_busy: '账号正由其他任务使用', remote_order_capacity: '等待远端订单名额',
    not_due: '等待下次平台查询', execution_active: '上一执行仍在退出或清理',
    fairness_turn: '等待公平调度轮次', concurrency_policy_migration_required: '等待确认并发迁移策略',
    scheduler_store_unavailable: '调度存储暂不可用', permit_owner_lost: '执行所有者待核验',
  };
  const counts = reason?.occupied != null && reason?.limit != null ? `（${reason.occupied}/${reason.limit}）` : '';
  return labels[code] ? labels[code] + counts : `等待原因待核验（${code || '缺少原因代码'}）`;
}
function accountTaskAdmissionWaitMarkup(task) {
  const reasons = accountTaskAdmissionReasons(task);
  if (task?.status !== 'queued' || !reasons.length) return '';
  if (reasons.length === 1) return `<div class="sub-cell">${esc(accountTaskAdmissionReasonText(reasons[0]))}</div>`;
  return `<details class="sub-cell"><summary>${esc(accountTaskAdmissionReasonText(reasons[0]))}</summary><div>${reasons.map(reason => esc(accountTaskAdmissionReasonText(reason))).join('<br>')}</div></details>`;
}
function accountTaskResultText(task, compact = false) {
  const status = String(task.status || '');
  if (status === 'queued') return accountTaskAdmissionReasons(task).length
    ? accountTaskAdmissionReasonText(accountTaskAdmissionReasons(task)[0]) : '等待执行';
  if (status === 'running') return '执行中';
  const result = task.result_summary || {};
  if (task.task_type === 'extract_link') {
    const extraction = String(result.extraction_status || '').toLowerCase();
    const payment = String(result.payment_status || '').toLowerCase();
    const extracted = ['succeeded', 'success'].includes(extraction)
      || (!extraction && result.ok === true && result.has_link === true);
    if (extracted) {
      const label = `提链成功${result.link_type ? ` · ${String(result.link_type).toUpperCase()}` : ''}`;
      if (['failed', 'error'].includes(payment)) return `${label} · 支付失败`;
      if (['succeeded', 'success', 'paid'].includes(payment)) return `${label} · 支付成功`;
      if (['unknown', 'request_unknown', 'attention_required'].includes(payment)) return `${label} · 支付待确认`;
      if (['pending', 'pending_payment', 'processing'].includes(payment)) {
        return `${label} · ${result.mode === 'manual_payment' ? '等待手动支付' : '支付待确认'}`;
      }
      if (result.mode === 'manual_payment' && payment === 'not_started') return `${label} · 等待手动支付`;
      if (['request_unknown', 'attention_required', 'partial_success'].includes(status)) return `${label} · 后续处理待确认`;
      if (['cancelled', 'stopped', 'interrupted'].includes(status)) return `${label} · 任务已中断`;
      if (status === 'failed') return `${label} · 后续处理失败`;
      return label;
    }
    if (['failed', 'error'].includes(extraction)) return '提链失败';
    if (['unknown', 'request_unknown', 'attention_required'].includes(extraction)) return '提链结果待确认';
    if (['pending', 'queued'].includes(extraction)) return '等待提链';
    if (extraction === 'running') return '提链中';
    if (status === 'cancelled') return '任务已取消';
    if (['stopped', 'interrupted'].includes(status)) return '任务已中断';
    if (['request_unknown', 'attention_required', 'partial_success', 'unknown'].includes(status)) return '提链结果待确认';
    if (task.error_message) return accountTaskErrorDisplayText(task.error_info, task.error_message);
    if (Object.prototype.hasOwnProperty.call(result, 'ok')) {
      return result.message || result.status || (result.ok ? '提炼完成' : '提炼失败');
    }
    return result.message || (status === 'failed' ? '提链失败' : '提链结果未记录');
  }
  if (task.error_message) return accountTaskErrorDisplayText(task.error_info, task.error_message);
  if (task.task_type === 'registration' || task.task_type === 'registration_resume') {
    return facetLabel('target_status', task.target_status) || '注册执行已结束';
  }
  if (task.task_type === 'plan_check') {
    const plan = String(result.current_plan_type || '');
    const prefix = plan ? `${compact ? plan : `套餐 ${plan}`} · ` : '';
    const countrySummary = _accountCountryTaskSummary(result, task.status, compact);
    if (countrySummary) return `${prefix}${countrySummary}`;
    if (Array.isArray(result.account_promotions)) {
      const items = _accountPromotions(result);
      const promotions = compact ? _accountTaskPromotionSummary(items) : _accountPromotionGroups(items).map(_accountPromotionGroupLabel).join(' · ');
      return `${prefix}${promotions}`;
    }
    return plan ? (plan.toLowerCase() === 'free' ? `${prefix}Plus ${_plusPromotionLabel(result)}` : `${compact ? '' : '套餐 '}${plan}`) : '查询完成';
  }
  if (task.task_type === 'deactivation_mail') {
    if (!Object.prototype.hasOwnProperty.call(result, 'detected')) return '-';
    return result.detected ? '发现封号邮件' : '未发现封号邮件';
  }
  if (task.task_type === 'live_check' || task.task_type === 'token_refresh') return result.ok ? '账号正常' : (result.status || '-');
  if (task.task_type === 'email_change') {
    if (result.email_change_confirmed) {
      return result.post_change_live_check?.accepted ? '邮箱已换绑 · AT 刷新已排队' : '邮箱已换绑 · AT 刷新待处理';
    }
    return result.message || result.status || '邮箱换绑未完成';
  }
  if (['account_setup_retry','password_setup','password_change','twofa_setup','twofa_change','account_completion'].includes(task.task_type)) return result.ok ? (result.message || '账号配置操作已完成') : (result.message || result.status || '账号配置操作失败');
  if (task.task_type === 'codex_retry') {
    if (result.ok) {
      const syncStatus = result.sub2api_sync?.status;
      if (syncStatus === 'success') return '授权成功 · sub2api 已启用';
      if (syncStatus === 'failed') return '授权成功 · sub2api 同步失败';
      if (syncStatus === 'cancelled') return '授权成功 · sub2api 同步已停止';
      return result.credential_confirmed ? '授权成功 · 凭证已确认' : '授权成功';
    }
    if (result.status === 'attention_required') return 'Callback 已接收 · 凭证待确认';
    return result.message || result.status || '补跑失败';
  }
  if (task.task_type === 'codex_token_refresh') {
    if (!result.ok) return 'OAuth Token 刷新失败';
    return result.sub2_sync === 'failed' ? 'Token 已刷新 · sub2 同步失败' : 'OAuth Token 已刷新';
  }
  if (task.task_type === 'c2a_session_reimport') return result.ok ? (result.message || 'C2A AT 已从本地重新导入') : result.error_code || result.message || 'C2A 重新导入失败，请查看任务日志';
  if (task.task_type === 'sub2api_manual_upload') return result.ok ? '手动上传 Sub2API 已完成' : result.error_code || result.message || '手动上传失败，请查看任务日志';
  if (task.task_type === 'sub2api_scan') return result.ok ? 'Sub2API 异常扫描已完成' : result.error_code || result.message || '扫描未完成，请查看任务日志';
  return Object.keys(result).length ? JSON.stringify(result) : '-';
}
function normalizeAccountTaskStage(stage) {
  const value = String(stage || 'event').replace(/_result$/, '');
  return value === 'network_route' ? 'network' : value;
}
const ACCOUNT_TASK_STEP_STATE_LABELS = {
  pending:'未开始', running:'执行中', success:'已完成', skipped:'已跳过', failed:'失败'
};
const ACCOUNT_TASK_PROGRESS_STATUS_LABELS = {
  pending:'未开始', running:'执行中', success:'已完成', skipped:'已跳过', failed:'失败',
  unconfirmed:'未确认', not_executed:'未执行', request_unknown:'结果待确认', stopped:'已中断',
  partial_success:'部分完成', cancelled:'已取消', interrupted:'已中断', attention_required:'结果待确认',
  deferred:'已延后', awaiting_confirmation:'待确认', record_incomplete:'记录不完整'
};
function accountTaskEventStepState(event) {
  const detail = event?.detail && typeof event.detail === 'object' ? event.detail : {};
  const eventType = String(event?.event_type || '');
  const fromType = eventType.startsWith('stage.') ? eventType.slice(6) : '';
  const explicit = String(detail.step_state || fromType || '').toLowerCase();
  if (Object.prototype.hasOwnProperty.call(ACCOUNT_TASK_STEP_STATE_LABELS, explicit)) return explicit;
  return String(event?.level || '').toUpperCase() === 'ERROR' ? 'failed' : null;
}
function accountTaskProgressStateLabel(step) {
  const status = String(step?.display_status || step?.state || 'pending').toLowerCase();
  return ACCOUNT_TASK_PROGRESS_STATUS_LABELS[status] || TASK_PROGRESS_STATUS_LABELS[status] || ACCOUNT_TASK_STEP_STATE_LABELS[status] || status;
}
let accountTaskStepFilter = null;
let accountTaskPendingStepFilter = null;
let accountTaskStepPage = 0, accountTaskStepPageSize = 0;
let accountTaskStepDetailState = null, accountTaskStepDetailReturnFocus = null;
let accountTaskStepDetailSignature = '';
const accountTaskStepDetailInert = new Map();
function accountTaskProgressStepId(step) {
  return String(step?.id || step?.step_id || '').trim();
}
function accountTaskProgressStepLabel(step) {
  return String(step?.label || step?.name || accountTaskProgressStepId(step) || '未命名步骤');
}
function accountTaskProgressStepEvidence(step) {
  const fields = [];
  if (Array.isArray(step?.raw_stages) && step.raw_stages.length) fields.push(`原始阶段：${step.raw_stages.join('、')}`);
  if (step?.observed_order != null) fields.push(`实际顺序：第 ${step.observed_order} 步`);
  if (step?.started_at || step?.completed_at) fields.push(`${formatDateTime(step.started_at)} → ${formatDateTime(step.completed_at)}`);
  if (step?.duration_ms != null) fields.push(`耗时 ${formatTaskDuration(step.duration_ms)}`);
  return fields;
}
function accountTaskStepAttempts(step) {
  const attempts = Array.isArray(step?.attempts) ? step.attempts : [];
  return attempts.length ? `<details class="account-task-stage-attempts" data-account-task-detail="attempts"><summary>查看阶段事件（${attempts.length}）</summary><pre>${esc(JSON.stringify(attempts, null, 2))}</pre></details>` : '';
}
function accountTaskStepDetails(step) {
  const rawDetail = step?.reason || step?.message || '';
  const evidence = accountTaskProgressStepEvidence(step);
  const evidenceHtml = evidence.length ? `<details class="account-task-stage-technical" data-account-task-detail="technical"><summary>阶段与时间</summary><div class="account-task-stage-evidence">${evidence.map(item => `<span>${esc(item)}</span>`).join('')}</div></details>` : '';
  return `${rawDetail ? `<div class="account-task-stage-reason">${esc(rawDetail)}</div>` : ''}${evidenceHtml}${accountTaskStepAttempts(step)}`;
}
function accountTaskFailureLocation(failure) {
  const classifiedStage = String(failure.error_info?.stage || '').trim();
  const correctedStage = classifiedStage && !['unknown', 'complete', 'result', 'event', 'queued'].includes(classifiedStage)
    && classifiedStage !== failure.stage ? classifiedStage : '';
  return correctedStage
    ? (typeof facetLabel === 'function' ? facetLabel('stage', correctedStage) : correctedStage)
    : [failure.label || failure.step_id || '位置待确认', failure.stage].filter(Boolean).join(' · ');
}
function accountTaskCountryFailures(progress) {
  const rows = Array.isArray(progress?.failure?.country_failures) ? progress.failure.country_failures : [];
  const items = rows.filter(row => row && typeof row === 'object' && String(row.country || '').trim());
  if (!items.length) return '';
  return `<ul class="account-task-country-failures">${items.map(row => `<li>${esc(String(row.country).trim())}：${esc(String(row.summary || '').trim() || '诊断记录不完整')}</li>`).join('')}</ul>`;
}
function accountTaskFailureSummary(progress) {
  const failure = progress?.failure && typeof progress.failure === 'object' ? progress.failure : null;
  if (!failure) return '';
  const location = accountTaskFailureLocation(failure);
  const message = failure.message || (typeof failure.evidence === 'string' ? failure.evidence : '') || '失败位置待确认';
  const countries = accountTaskCountryFailures(progress);
  const reconcile = failure.reconcile_required || ['request_unknown', 'attention_required'].includes(String(progress?.outcome?.status || '').toLowerCase());
  const inferred = failure.inferred === true || failure.evidence?.inferred === true || failure.evidence?.source === 'inferred' || failure.evidence?.kind === 'inferred' || failure.evidence === 'inferred' || failure.evidence === 'legacy' || failure.evidence === 'unobserved';
  const locationTitle = inferred || (!failure.step_id && !failure.label && !failure.event_id) ? '待确认位置' : '失败位置';
  const event = failure.event_id ? `<span>事件 ${esc(failure.event_id)}</span>` : '';
  const errorSummary = failure.error_info?.summary || failure.error_info?.display_code || '';
  const cause = String(failure.error_info?.cause_summary || '').trim();
  const causeHtml = cause && !String(errorSummary).includes(cause) && !String(message).includes(cause)
    ? `<span>原因：${esc(cause)}</span>` : '';
  const technical = failure.error_info || (failure.evidence && typeof failure.evidence === 'object')
    ? `<details><summary>查看技术详情</summary><pre>${esc(JSON.stringify({error_info: failure.error_info || null, evidence: failure.evidence || null}, null, 2))}</pre></details>`
    : '';
  const primary = !countries || failure.error_info?.auto_refresh_at_failed ? `<span>${esc(message)}</span>` : '';
  return `<div class="account-task-progress-failure" role="status"><strong>${esc(locationTitle)}：${esc(location)}</strong>${primary}${countries}${errorSummary && errorSummary !== message ? `<span>错误：${esc(errorSummary)}</span>` : ''}${causeHtml}${event}${reconcile ? '<span class="account-task-progress-flag">远端结果待确认</span>' : ''}${technical}</div>`;
}
function accountTaskStepTooltipText(step) {
  return taskProgressStepTooltip(step);
}

function hideAccountTaskStepTooltip() {
  if (typeof _accountsTooltipTarget !== 'undefined' && _accountsTooltipTarget?.closest?.('#accountTaskStageProgress')) _hideAccountsTooltip();
}
function accountTaskProgressStepMarkup(step, index, compact = false) {
  const id = accountTaskProgressStepId(step) || `step-${index + 1}`;
  const state = String(step?.display_status || taskProgressStepStatus(step));
  const selected = accountTaskStepFilter === id || (Array.isArray(step?.raw_stages) && step.raw_stages.includes(accountTaskStepFilter));
  const label = taskProgressCompactLabel(step);
  const tooltip = attrEsc(accountTaskStepTooltipText(step));
  const duration = taskProgressStepDuration(step);
  return `<div class="account-task-stage-step is-${attrEsc(state)}${selected ? ' is-selected' : ''}" data-account-task-step="${attrEsc(id)}"><button type="button" class="account-task-stage-select" data-account-task-step-filter="${attrEsc(id)}" data-accounts-tooltip="${tooltip}" aria-pressed="${selected ? 'true' : 'false'}" aria-label="筛选${esc(label)}的事件和日志：${esc(accountTaskProgressStateLabel(step))}，耗时 ${esc(duration)}"><span class="account-task-stage-node" aria-hidden="true">${state === 'success' ? '✓' : state === 'failed' ? '×' : state === 'stopped' ? '!' : state === 'running' ? '…' : String(index + 1)}</span><span class="account-task-stage-label">${esc(label)}</span><span class="account-task-stage-state">${esc(accountTaskProgressStateLabel(step))}</span><span class="account-task-stage-duration">耗时 ${esc(duration)}</span></button></div>`;
}

function accountTaskChildRuns(progress) {
  const children = (progress?.outcome?.child_tasks || []).filter(child => Number(child.task_id) > 0);
  if (!children.length) return '';
  return `<div class="account-task-child-runs"><strong>独立子任务</strong>${children.map(child => `<button type="button" data-account-task-child="${attrEsc(child.task_id)}" data-child-run="${attrEsc(child.run_id || '')}">${esc(facetLabel('task_type', child.task_type) || '子任务')} #${esc(child.task_id)} · ${esc(taskProgressStatusLabel(child.status || 'queued'))}</button>`).join('')}</div>`;
}
function accountTaskProgressPageSize(width, count = 0) {
  const available = Math.max(0, Number(width) || 1000);
  const minWidth = available < 540 ? 136 : count > 8 ? 80 : count > 5 ? 108 : 138;
  const capacity = Math.max(1, Math.floor((available + 12) / (minWidth + 12)));
  return count > 0 ? Math.min(count, capacity) : capacity;
}
function accountTaskProgressPage(stages, page, size) {
  const pages = Math.max(1, Math.ceil(stages.length / size));
  const current = Math.max(0, Math.min(Number(page) || 0, pages - 1));
  return {page: current, pages, start: current * size, steps: stages.slice(current * size, (current + 1) * size)};
}
function accountTaskStepDialogContext() {
  return `${typeof activeAccountTaskId === 'undefined' ? '' : activeAccountTaskId || ''}:${typeof activeAccountTaskRunId === 'undefined' ? '' : activeAccountTaskRunId || ''}`;
}
function accountTaskStepAttemptMarkup(attempt, index) {
  const state = String(attempt?.display_status || attempt?.state || 'pending');
  const label = ACCOUNT_TASK_PROGRESS_STATUS_LABELS[state] || TASK_PROGRESS_STATUS_LABELS[state] || state;
  return `<li class="account-task-attempt"><div><strong>记录 ${index + 1} · ${esc(label)}</strong><time>${esc(formatDateTime(attempt.created_at))}</time></div><p>${esc(attempt.message || '无补充说明')}</p><small>${esc(attempt.raw_stage || '')}${attempt.event_id ? ` · 事件 ${esc(attempt.event_id)}` : ''}</small><details data-step-dialog-detail="attempt-${index}"><summary>技术字段</summary><pre>${esc(JSON.stringify(attempt, null, 2))}</pre></details></li>`;
}
function accountTaskStepDialogBody(step, tab) {
  if (!step) return tab === 'children' ? accountTaskChildRuns(accountTaskProgressSnapshot) || '<p>当前 Run 没有独立子任务。</p>' : accountTaskFailureSummary(accountTaskProgressSnapshot) || '<p>当前 Run 没有失败记录。</p>';
  if (tab === 'attempts') {
    const attempts = Array.isArray(step.attempts) ? step.attempts : [];
    return attempts.length ? `<ol class="account-task-attempt-list">${attempts.map(accountTaskStepAttemptMarkup).join('')}</ol>` : '<p>此步骤暂无阶段事件。</p>';
  }
  if (tab === 'children') {
    const children = taskProgressVisibleSteps(step.children);
    return children.map(child => `<section class="account-task-step-child is-${attrEsc(child.display_status || taskProgressStepStatus(child))}"><h4>${esc(accountTaskProgressStepLabel(child))}<span>${esc(accountTaskProgressStateLabel(child))}</span></h4>${accountTaskStepDetails(child)}</section>`).join('') || '<p>此步骤没有子步骤。</p>';
  }
  const evidence = accountTaskProgressStepEvidence(step);
  return `<div class="account-task-step-time"><p>${esc(step.reason || step.message || '无补充说明')}</p><dl><dt>状态</dt><dd>${esc(accountTaskProgressStateLabel(step))}</dd><dt>开始时间</dt><dd>${esc(formatDateTime(step.started_at))}</dd><dt>结束时间</dt><dd>${esc(formatDateTime(step.completed_at))}</dd><dt>耗时</dt><dd>${esc(formatTaskDuration(step.duration_ms))}</dd></dl><div class="account-task-stage-evidence">${evidence.map(item => `<span>${esc(item)}</span>`).join('')}</div></div>`;
}
function renderAccountTaskStepDialog() {
  if (!accountTaskStepDetailState) return;
  if (accountTaskStepDetailState.context !== accountTaskStepDialogContext()) { closeAccountTaskStepDialog(false); return; }
  const state = accountTaskStepDetailState;
  const step = state.stepId ? (accountTaskProgressSnapshot?.main_steps || []).find(item => accountTaskProgressStepId(item) === state.stepId) : null;
  if (state.stepId && (!step || taskProgressStepStatus(step) === 'skipped')) { closeAccountTaskStepDialog(); return; }
  const signature = JSON.stringify({state, step, failure: !step && accountTaskProgressSnapshot?.failure, children: !step && accountTaskProgressSnapshot?.outcome?.child_tasks});
  if (signature === accountTaskStepDetailSignature) return;
  accountTaskStepDetailSignature = signature;
  const title = $('#accountTaskStepDetailTitle');
  const content = $('#accountTaskStepDetailContent');
  if (!title || !content) return;
  title.textContent = step ? accountTaskProgressStepLabel(step) : '任务诊断详情';
  const tabs = step ? [['time', '阶段与时间'], ['attempts', `阶段事件（${(step.attempts || []).length}）`], ['children', `子步骤（${taskProgressVisibleSteps(step.children).length}）`]] : [['failure', '失败证据'], ['children', '独立子任务']];
  const focusedTab = document.activeElement?.getAttribute?.('data-step-dialog-tab');
  $('#accountTaskStepDetailTabs').innerHTML = tabs.map(([id, label]) => `<button type="button" role="tab" data-step-dialog-tab="${id}" aria-selected="${state.tab === id}" class="${state.tab === id ? 'is-active' : ''}" aria-controls="accountTaskStepDetailContent">${esc(label)}</button>`).join('');
  const scrollTop = content.scrollTop;
  const opened = new Set(Array.from(content.querySelectorAll('details[open]')).map(item => item.dataset.stepDialogDetail).filter(Boolean));
  content.innerHTML = accountTaskStepDialogBody(step, state.tab);
  content.querySelectorAll('details[data-step-dialog-detail]').forEach(item => { item.open = opened.has(item.dataset.stepDialogDetail); });
  content.scrollTop = scrollTop;
  if (focusedTab) Array.from($('#accountTaskStepDetailTabs').querySelectorAll('button')).find(item => item.dataset.stepDialogTab === focusedTab)?.focus({preventScroll:true});
}
function openAccountTaskStepDialog(stepId = null, tab = 'time', trigger = null) {
  hideAccountTaskStepTooltip();
  const overlay = $('#accountTaskStepDetailOverlay');
  if (!overlay) return;
  accountTaskStepDetailReturnFocus = trigger || document.activeElement;
  accountTaskStepDetailState = {context: accountTaskStepDialogContext(), stepId, tab};
  accountTaskStepDetailSignature = '';
  Array.from($('#accountTaskLogPanel')?.children || []).forEach(item => {
    if (item === overlay) return;
    if (!accountTaskStepDetailInert.has(item)) accountTaskStepDetailInert.set(item, item.inert);
    item.inert = true;
  });
  overlay.classList.remove('hidden');
  renderAccountTaskStepDialog();
  $('#btnCloseAccountTaskStepDetail')?.focus({preventScroll:true});
}
function closeAccountTaskStepDialog(restoreFocus = true) {
  const state = accountTaskStepDetailState;
  $('#accountTaskStepDetailOverlay')?.classList.add('hidden');
  accountTaskStepDetailInert.forEach((wasInert, item) => { item.inert = wasInert; });
  accountTaskStepDetailInert.clear();
  accountTaskStepDetailState = null;
  accountTaskStepDetailSignature = '';
  if (restoreFocus && state) {
    const oldTrigger = accountTaskStepDetailReturnFocus;
    const replacement = Array.from($('#accountTaskStageProgress')?.querySelectorAll('button') || []).find(item => state.stepId ? item.dataset.accountTaskStepDetails === state.stepId && item.dataset.stepDetailTab === state.tab : state.tab === 'children' ? item.hasAttribute('data-account-task-child-details') : item.hasAttribute('data-account-task-failure-details'));
    (oldTrigger?.isConnected ? oldTrigger : replacement || $('#btnCloseAccountTaskLog'))?.focus({preventScroll:true});
  }
  accountTaskStepDetailReturnFocus = null;
}
function scrollAccountTaskDialogFromWheel(event) {
  if (event.defaultPrevented || event.ctrlKey || event.shiftKey || !event.deltaY) return;
  const overlay = $('#accountTaskStepDetailOverlay');
  const stepDialogOpen = overlay && !overlay.classList.contains('hidden');
  const content = stepDialogOpen
    ? $('#accountTaskStepDetailContent')
    : $('#accountTaskLogPanel')?.querySelector('.account-task-detail-content');
  // 正文及其内部代码块沿用浏览器滚动；标题、步骤与页签滚动当前弹窗正文。
  if (!content || content.contains(event.target) || content.scrollHeight <= content.clientHeight) return;
  const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? content.clientHeight : 1;
  event.preventDefault();
  hideAccountTaskStepTooltip();
  content.scrollTop += event.deltaY * unit;
}
function accountTaskProgressBrief(progress) {
  const failure = progress?.failure;
  const children = (progress?.outcome?.child_tasks || []).filter(child => Number(child.task_id) > 0);
  const location = failure ? accountTaskFailureLocation(failure) : '';
  const roxyLoginSummary = String(failure?.error_info?.code || '').startsWith('roxy_login_') ? failure.error_info.summary : '';
  const message = roxyLoginSummary || failure?.message || '';
  const inferred = failure?.inferred === true || failure?.evidence?.inferred === true || ['inferred', 'legacy', 'unobserved'].includes(failure?.evidence) || ['inferred'].includes(failure?.evidence?.source || failure?.evidence?.kind);
  return `<div class="account-task-stage-brief">${failure ? `<button type="button" class="account-task-failure-brief" data-account-task-failure-details aria-haspopup="dialog" title="${attrEsc(`${location}：${message}`)}"><strong>${inferred ? '待确认位置' : '失败'}：${esc(location)}</strong><span>${esc(message || '查看定位与证据')}</span></button>` : '<span class="account-task-stage-brief-hint">悬浮查看时间与阶段事件，点击步骤筛选日志。</span>'}${children.length ? `<button type="button" class="account-task-child-brief" data-account-task-child-details aria-haspopup="dialog">子任务 ${children.length}</button>` : ''}</div>`;
}
function renderAccountTaskProgressSnapshot(progress) {
  const panel = $('#accountTaskStageProgress');
  if (!panel) return;
  const tooltipTarget = typeof _accountsTooltipTarget === 'undefined' ? null : _accountsTooltipTarget;
  const tooltipStep = tooltipTarget?.closest?.('[data-account-task-step]')?.dataset.accountTaskStep;
  const tooltipTab = tooltipTarget?.dataset.stepDetailTab;
  const tooltipView = tooltipStep ? rememberTaskTooltipView() : null;
  hideAccountTaskStepTooltip();
  const stages = taskProgressVisibleSteps(progress?.main_steps);
  if (progress && accountTaskStepFilter && !stages.some(stage => accountTaskProgressStepId(stage) === accountTaskStepFilter || (stage.raw_stages || []).includes(accountTaskStepFilter))) accountTaskStepFilter = null;
  if (!stages.length) {
    accountTaskStepPage = 0;
    accountTaskStepPageSize = 0;
    panel.classList.add('hidden');
    panel.innerHTML = '';
    closeAccountTaskStepDialog();
    renderAccountTaskFilterBar();
    return;
  }
  const current = progress.current;
  const currentText = progress?.debug_pause
    ? taskDebugPauseSummary(progress.debug_pause)
    : current
    ? `当前：${current.label || current.step_id}${current.child_label ? ` · ${current.child_label}` : ''}`
    : `结果：${taskProgressStatusLabel(progress.outcome?.status || 'pending')}`;
  const sourceText = progress.source === 'legacy_derived' ? '历史记录按已有结构化事件还原' : progress.source === 'insufficient_evidence' ? '记录不足，步骤状态未确认' : '';
  const activeElement = document.activeElement;
  const focusedFilter = activeElement?.getAttribute?.('data-account-task-step-filter');
  const focusedDetails = activeElement?.getAttribute?.('data-account-task-step-details');
  const focusedTab = activeElement?.getAttribute?.('data-step-detail-tab');
  const focusedPage = activeElement?.getAttribute?.('data-account-task-step-page');
  const width = panel.clientWidth - 16;
  const size = accountTaskProgressPageSize(width, stages.length);
  const compact = size >= 6 || width / size < 180;
  panel.classList.toggle('is-compact', compact);
  panel.classList.toggle('is-dense', size >= 9);
  if (!accountTaskStepPageSize && accountTaskStepFilter) {
    const selectedIndex = stages.findIndex(item => accountTaskProgressStepId(item) === accountTaskStepFilter || (item.raw_stages || []).includes(accountTaskStepFilter));
    if (selectedIndex >= 0) accountTaskStepPage = Math.floor(selectedIndex / size);
  }
  if (accountTaskStepPageSize && size !== accountTaskStepPageSize) accountTaskStepPage = Math.floor(accountTaskStepPage * accountTaskStepPageSize / size);
  accountTaskStepPageSize = size;
  const page = accountTaskProgressPage(stages, accountTaskStepPage, size);
  accountTaskStepPage = page.page;
  const track = page.steps.map((step, index) => accountTaskProgressStepMarkup(step, page.start + index, compact)).join('');
  const pager = page.pages > 1
    ? `<span>共 ${stages.length} 步 · ${page.start + 1}–${page.start + page.steps.length}</span><div><button type="button" data-account-task-step-page="${page.page - 1}"${page.page === 0 ? ' disabled' : ''} aria-label="上一页步骤">上一页</button><span aria-live="polite">${page.page + 1} / ${page.pages}</span><button type="button" data-account-task-step-page="${page.page + 1}"${page.page + 1 === page.pages ? ' disabled' : ''} aria-label="下一页步骤">下一页</button></div>`
    : `<span>共 ${stages.length} 步</span><span>已全部显示</span>`;
  const countryFailures = accountTaskCountryFailures(progress);
  panel.classList.toggle('has-country-failures', Boolean(countryFailures));
  panel.innerHTML = `<div class="account-task-stage-current"><strong>${esc(currentText)}</strong><small title="${attrEsc(sourceText || '按实际执行记录排列，未执行步骤在后')}">${esc(sourceText || '按实际执行记录排列')}</small></div>${accountTaskProgressBrief(progress)}${countryFailures}<div class="account-task-stage-track" style="--task-step-columns:${size}">${track}</div><div class="account-task-stage-pager" aria-label="步骤翻页">${pager}</div>`;
  panel.classList.remove('hidden');
  const restore = Array.from(panel.querySelectorAll('button')).find(item => focusedFilter ? item.getAttribute('data-account-task-step-filter') === focusedFilter : focusedDetails ? item.getAttribute('data-account-task-step-details') === focusedDetails && item.getAttribute('data-step-detail-tab') === focusedTab : focusedPage != null && item.getAttribute('data-account-task-step-page') === focusedPage);
  if (restore) restore.focus({preventScroll:true});
  if (tooltipStep && !accountTaskStepDetailState) {
    const target = Array.from(panel.querySelectorAll('[data-accounts-tooltip]')).find(item => tooltipTab ? item.dataset.accountTaskStepDetails === tooltipStep && item.dataset.stepDetailTab === tooltipTab : item.dataset.accountTaskStepFilter === tooltipStep);
    if (target) restoreTaskTooltipView(target, tooltipView);
  }
  renderAccountTaskStepDialog();
  renderAccountTaskFilterBar();
}
function renderAccountTaskStageProgress(task, selectedRunId = null) {
  renderAccountTaskProgressSnapshot(task?.progress || null);
}
function accountTaskCanRetry(task) {
  const status = String(task?.status || '').toLowerCase();
  const targetStatus = String(task?.target_status || '').toLowerCase();
  const summary = task?.result_summary && typeof task.result_summary === 'object' ? task.result_summary : {};
  const summaryDeactivated = ['status', 'requested_status'].some(
    key => String(summary[key] || '').toLowerCase() === 'deactivated',
  );
  const active = ['queued','running','stopping','cancelling','settling','waiting'].includes(status);
  const deactivated = status === 'deactivated' || ['deactivated', 'account_deactivated'].includes(targetStatus) || summaryDeactivated;
  return !active && !deactivated && Array.isArray(task?.next_actions) && task.next_actions.length > 0;
}
function accountTaskIsActive(task) {
  return ['queued','running','stopping','cancelling','settling','waiting'].includes(String(task?.status || '').toLowerCase());
}
function accountTaskCanTerminate(task) {
  return task?.source_system === 'native_operations'
    && accountTaskIsActive(task)
    && String(task.status || '').toLowerCase() !== 'queued';
}
function accountTaskCanStop(task) {
  return task?.source_system === 'native_operations'
    && (String(task.status || '').toLowerCase() === 'queued' || accountTaskCanTerminate(task));
}
function accountTaskSelectedRows() {
  return ACCOUNT_TASKS.filter(task => ACCOUNT_TASK_SELECTED.has(Number(task.id)));
}
function updateAccountTaskSelectionUi() {
  const selected = accountTaskSelectedRows();
  const retryable = selected.filter(accountTaskCanRetry).length;
  const cancellable = selected.filter(task => String(task.status || '').toLowerCase() === 'queued').length;
  const terminable = selected.filter(accountTaskCanTerminate).length;
  const deletable = selected.filter(task => !accountTaskIsActive(task)).length;
  const hint = $('#accountTaskSelectedHintV2');
  const toolbar = hint?.closest('.list-action-toolbar');
  toolbar?.classList.toggle('has-selection', selected.length > 0);
  if (hint) hint.textContent = selected.length
    ? `已选 ${selected.length} 个 · 可重跑 ${retryable} · 可取消 ${cancellable} · 可终止 ${terminable} · 可删除 ${deletable}`
    : '选择任务后批量操作';
  const retryBtn = $('#btnRetrySelectedAccountTasksV2');
  const cancelBtn = $('#btnCancelSelectedAccountTasksV2');
  const terminateBtn = $('#btnTerminateSelectedAccountTasksV2');
  const deleteBtn = $('#btnDeleteSelectedAccountTasksV2');
  if (retryBtn) retryBtn.disabled = retryable === 0;
  if (cancelBtn) cancelBtn.disabled = cancellable === 0;
  if (terminateBtn) terminateBtn.disabled = terminable === 0;
  if (deleteBtn) deleteBtn.disabled = deletable === 0;
  const selectAll = $('#accountTasksSelectAllV2');
  const pageIds = ACCOUNT_TASKS.map(task => Number(task.id));
  const checkedCount = pageIds.filter(id => ACCOUNT_TASK_SELECTED.has(id)).length;
  if (selectAll) {
    selectAll.checked = pageIds.length > 0 && checkedCount === pageIds.length;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < pageIds.length;
    selectAll.disabled = pageIds.length === 0;
  }
}
function syncAccountTasksSelectAll(checked) {
  ACCOUNT_TASKS.forEach(task => {
    const id = Number(task.id);
    if (checked) ACCOUNT_TASK_SELECTED.add(id);
    else ACCOUNT_TASK_SELECTED.delete(id);
  });
  renderAccountTasks();
}
function renderAccountTasks() {
  const body = $('#accountTasksBody');
  if (!body) return;
  const tooltipTarget = typeof _accountsTooltipTarget === 'undefined' ? null : _accountsTooltipTarget;
  const tooltipTaskId = tooltipTarget?.dataset.accountTaskResultTooltip;
  const tooltipView = tooltipTaskId ? rememberTaskTooltipView() : null;
  const restoreTooltipFocus = tooltipTaskId && document.activeElement === tooltipTarget;
  if (tooltipTaskId) _hideAccountsTooltip();
  const pageIds = new Set(ACCOUNT_TASKS.map(task => Number(task.id)));
  ACCOUNT_TASK_SELECTED.forEach(id => { if (!pageIds.has(Number(id))) ACCOUNT_TASK_SELECTED.delete(id); });
  body.innerHTML = ACCOUNT_TASKS.map(task => {
    const result = accountTaskResultText(task);
    const active = accountTaskIsActive(task);
    const retryable = accountTaskCanRetry(task);
    const terminable = accountTaskCanTerminate(task);
    const stoppable = accountTaskCanStop(task);
    const terminationLabel = task.status === 'queued' ? '取消' : '终止';
    const target = task.account_id ? `账号 #${task.account_id}` : (task.attempt_id ? `注册尝试 #${task.attempt_id}` : '-');
    const managedBatchId = task.bulk_batch_id || task.bulk_context?.batch_id;
    const batch = task.batch_title || (task.batch_uuid ? short(task.batch_uuid, 12) : '单任务');
    const trigger = facetLabel('trigger', task.trigger);
    const stage = task.current_stage_label || facetLabel('stage', normalizeAccountTaskStage(task.current_stage));
    const error = task.error_message || '';
    const errorInfo = task.error_info || null;
    const reportedFailureStage = task.failure_stage || task.result_summary?.failure_stage;
    const classifiedStage = String(errorInfo?.stage || '').trim();
    const hasClassifiedStage = classifiedStage && !['unknown', 'complete', 'result', 'event', 'queued'].includes(classifiedStage);
    const authDiagnostics = task.result_summary?.auth_diagnostics || {};
    const mfaOperation = authDiagnostics.operation === 'password_email_fallback'
      ? authDiagnostics.cause_operation : authDiagnostics.operation;
    const mfaDiagnostic = ['token_refresh', 'live_check'].includes(task.task_type) && !active && task.status !== 'success'
      && ['login_password', 'email_otp'].includes(reportedFailureStage)
      && ['mfa_verify', 'mfa_issue_challenge'].includes(mfaOperation);
    const failureStage = mfaDiagnostic ? 'mfa_challenge' : hasClassifiedStage ? classifiedStage : reportedFailureStage;
    const failureLabel = failureStage === reportedFailureStage && task.failure_stage_label
      ? task.failure_stage_label : facetLabel('stage', normalizeAccountTaskStage(failureStage));
    const failureLocation = failureStage && !active ? `失败于 ${failureLabel}` : '';
    const errorText = accountTaskErrorDisplayText(errorInfo, error);
    const extractionSucceeded = task.task_type === 'extract_link' && (
      ['succeeded', 'success'].includes(String(task.result_summary?.extraction_status || '').toLowerCase())
      || (!task.result_summary?.extraction_status && task.result_summary?.ok === true && task.result_summary?.has_link === true)
    );
    const resultErrorText = extractionSucceeded ? result : errorText;
    const compactPlanResult = task.task_type === 'plan_check' && !active && !error;
    return `<tr class="${ACCOUNT_TASK_SELECTED.has(Number(task.id)) ? 'is-selected' : ''}">
      <td class="task-col-check col-check"><input type="checkbox" data-account-task-select="${esc(task.id)}" ${ACCOUNT_TASK_SELECTED.has(Number(task.id)) ? 'checked' : ''} aria-label="选择任务 #${esc(task.id)}"></td>
      <td>#${esc(task.id)}</td>
      <td title="${esc(task.task_type || '')}">${esc(facetLabel('task_type', task.task_type))}</td>
      <td title="${esc(task.email_snapshot)}"><strong>${esc(target)}</strong><div class="sub-cell">${esc(task.email_snapshot || '-')}</div></td>
      <td title="${esc(task.status || '')}">${pillV2(task.debug_pause ? 'debug_paused' : task.status, 'status')}${task.debug_pause ? '<div class="sub-cell">等待结束调试</div>' : accountTaskAdmissionWaitMarkup(task)}</td>
      <td title="${esc(task.target_status || '')}">${pillV2(task.target_status, 'target_status')}</td>
      <td title="${esc(batch)} · ${esc(trigger)}">${managedBatchId ? `<button type="button" class="bulk-link" data-account-bulk-batch="${attrEsc(managedBatchId)}" data-account-bulk-round="${attrEsc(task.bulk_round_id || task.bulk_context?.round_id || '')}">${esc(short(batch, 26))}</button>` : esc(short(batch, 26))}<div class="sub-cell">${esc(trigger)}</div></td>
      <td>${esc(task.run_count || 0)} 次<div class="sub-cell">最近 #${esc(task.last_run_no || '-')}</div></td>
      <td>${esc(stage)}${failureLocation ? `<div class="sub-cell">${esc(failureLocation)}</div>` : ''}<div class="sub-cell">${esc(formatTaskDuration(task.duration_ms))}</div></td>
      <td title="${esc(formatDateTime(task.created_at))} → ${esc(formatDateTime(task.completed_at))}">${esc(formatDateTime(task.created_at))}<div class="sub-cell">${esc(formatDateTime(task.completed_at))}</div></td>
      <td class="task-error"${compactPlanResult ? '' : ` title="${esc(error ? accountTaskErrorDisplayTitle(errorInfo, error) : result)}"`}>${compactPlanResult ? accountTaskPlanResultMarkup(task) : error ? `${taskErrorBadge(errorInfo)}<span class="task-error-cell-text">${esc(short(resultErrorText, 90))}</span>${extractionSucceeded && errorText && errorText !== result ? `<span class="task-error-cell-text">原因：${esc(short(errorText, 90))}</span>` : ''}` : esc(short(result, 90))}</td>
      <td><div class="task-row-actions"><button type="button" class="task-row-action" data-account-task-log="${esc(task.id)}">日志</button>${stoppable ? `<button type="button" class="task-row-action task-row-action--terminate" data-account-task-terminate="${esc(task.id)}" aria-label="${terminationLabel}任务 #${esc(task.id)}">${terminationLabel}</button>` : ''}${retryable ? `<button type="button" class="task-row-action task-row-action--retry" data-account-task-retry="${esc(task.id)}">重跑</button>` : ''}${!active ? `<button type="button" class="task-row-action task-row-action--delete" data-account-task-delete="${esc(task.id)}">删除</button>` : ''}</div></td>
    </tr>`;
  }).join('') || renderTableStateRow(12, '暂无任务记录', '调整搜索或筛选条件后再试。');
  const summary = $('#accountTaskPageSummary');
  if (summary) summary.textContent = `${ACCOUNT_TASKS_TOTAL || 0} 个任务 · 当前页 ${ACCOUNT_TASKS.length} 条`;
  updateAccountTaskSelectionUi();
  autoSizeResizableTableColumns(document.querySelector('table[data-resizable-table="accountTasks"]'));
  _renderPager('accountTasks', ACCOUNT_TASKS_TOTAL);
  if (tooltipTaskId) {
    const target = Array.from(body.querySelectorAll('[data-account-task-result-tooltip]')).find(item => item.dataset.accountTaskResultTooltip === tooltipTaskId);
    if (target) {
      if (restoreTooltipFocus) target.focus({preventScroll:true});
      restoreTaskTooltipView(target, tooltipView);
    }
  }
}
async function loadAccountTasks({forceMetadata = false} = {}) {
  if (accountTasksLoading) {
    accountTasksReloadQueued = true;
    accountTaskForceMetadataQueued = accountTaskForceMetadataQueued || forceMetadata;
    return;
  }
  accountTasksLoading = true;
  setListBusy('accountTasksPanel', true);
  const p = PAGERS.accountTasks;
  const params = new URLSearchParams({
    page: String(p.page),
    page_size: String(p.size),
    task_id: $('#accountTaskIdFilterV2')?.value.trim() || '',
    type: $('#accountTaskTypeFilterV2')?.value || '',
    target: $('#accountTaskTargetFilterV2')?.value.trim() || '',
    status: $('#accountTaskStatusFilterV2')?.value || '',
    target_status: $('#accountTaskTargetStatusFilterV2')?.value || '',
    batch: $('#accountTaskBatchFilterV2')?.value.trim() || '',
    run_count: $('#accountTaskRunCountFilterV2')?.value || '',
    stage: $('#accountTaskStageFilterV2')?.value || '',
    created_from: $('#accountTaskDateFromV2')?.value || '',
    created_to: $('#accountTaskDateToV2')?.value || '',
    result: $('#accountTaskResultFilterV2')?.value.trim() || '',
  });
  try {
    const query = params.toString();
    const refreshMetadata = forceMetadata || accountTaskMetadataQuery !== query || Date.now() - accountTaskMetadataAt >= 30000;
    params.set('include_facets', refreshMetadata ? '1' : '0');
    params.set('include_batches', refreshMetadata ? '1' : '0');
    const result = await api(`/api/operations?${params.toString()}`);
    if (result.facets) updateAccountTaskFilters(result.facets);
    if (refreshMetadata) {
      accountTaskMetadataAt = Date.now();
      accountTaskMetadataQuery = query;
      accountTaskRecentBatchCount = Number((result.batches || []).length);
    }
    const signature = JSON.stringify([query, result.revision || [result.total, result.items]]);
    const unchanged = accountTaskListSignature === signature;
    accountTaskListSignature = signature;
    ACCOUNT_TASKS = result.items || [];
    ACCOUNT_TASKS_TOTAL = Number(result.total || 0);
    const totalPages = Math.max(1, Math.ceil(ACCOUNT_TASKS_TOTAL / p.size));
    if (p.page > totalPages) {
      p.page = totalPages;
      accountTasksLoading = false;
      return loadAccountTasks();
    }
    if ($('#accountTaskRefreshHint')) $('#accountTaskRefreshHint').textContent = `最近批次 ${accountTaskRecentBatchCount} 个 · 共 ${ACCOUNT_TASKS_TOTAL} 个任务`;
    if (!unchanged) renderAccountTasks();
    markViewReady('account-tasks');
  } catch (e) {
    accountTaskListSignature = '';
    if (!ACCOUNT_TASKS.length) $('#accountTasksBody').innerHTML = renderTableStateRow(12, '任务记录加载失败', '请检查服务状态后刷新列表。', 'error');
    showToast('加载任务中心失败: ' + e.message);
  }
  finally {
    accountTasksLoading = false;
    setListBusy('accountTasksPanel', false);
    if (accountTasksReloadQueued) {
      accountTasksReloadQueued = false;
      const forceMetadata = accountTaskForceMetadataQueued;
      accountTaskForceMetadataQueued = false;
      void loadAccountTasks({forceMetadata});
    }
  }
}
let activeAccountTaskId = null, activeAccountTaskRunId = null, accountTaskLogTimer = null;
let activeAccountTaskDetailView = 'events', accountTaskSnapshot = null, accountTaskPolling = false;
let accountTaskRequestId = 0;
let accountTaskEventCursor = null, accountTaskEventCache = [], accountTaskNewEventCount = 0;
let accountTaskRunLogCursor = null, accountTaskRunLogLines = [];
let accountTaskProgressSnapshot = null, accountTaskProgressRequestId = 0, accountTaskProgressError = '';

function meaningfulTaskDetail(detail) {
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const cleaned = {};
  Object.entries(detail).forEach(([key, value]) => {
    if (['step_state'].includes(key) || value == null || value === '') return;
    if (Array.isArray(value) && !value.length) return;
    if (typeof value === 'object' && !Array.isArray(value) && !Object.keys(value).length) return;
    cleaned[key] = value;
  });
  return Object.keys(cleaned).length ? cleaned : null;
}
function rememberTaskLogDetails(panel, attribute) {
  return new Set(Array.from(panel.querySelectorAll?.('details[open]') || []).map(item => item.closest(`[${attribute}]`)?.getAttribute(attribute)).filter(Boolean));
}
function restoreTaskLogDetails(panel, attribute, opened) {
  Array.from(panel.querySelectorAll?.('details') || []).forEach(item => {
    if (opened.has(item.closest(`[${attribute}]`)?.getAttribute(attribute))) item.open = true;
  });
}
function accountTaskEventStepId(event) {
  const detail = event?.detail && typeof event.detail === 'object' ? event.detail : {};
  return String(event?.main_step_id || detail.main_step_id || '').trim();
}
function accountTaskEventStage(event) {
  const detail = event?.detail && typeof event.detail === 'object' ? event.detail : {};
  return String(event?.stage || detail.stage || event?.stage_label || '').trim();
}
function accountTaskFilterRawStages() {
  const progress = Array.isArray(accountTaskProgressSnapshot?.main_steps) ? accountTaskProgressSnapshot.main_steps : [];
  const step = progress.find(item => accountTaskProgressStepId(item) === accountTaskStepFilter || (item.raw_stages || []).includes(accountTaskStepFilter));
  return Array.isArray(step?.raw_stages) ? step.raw_stages.map(String) : [];
}
function accountTaskEventMatchesFilter(event) {
  if (!accountTaskStepFilter) return true;
  const detail = event?.detail && typeof event.detail === 'object' ? event.detail : {};
  const stepId = accountTaskEventStepId(event);
  const stage = accountTaskEventStage(event);
  const eventId = String(event?.event_id || event?.id || '');
  const rawStages = Array.isArray(event?.raw_stages)
    ? event.raw_stages.map(String)
    : Array.isArray(detail.raw_stages) ? detail.raw_stages.map(String) : [];
  const stageLabel = String(event?.stage_label || detail.stage_label || '').trim();
  const selectedRawStages = accountTaskFilterRawStages();
  return stepId === accountTaskStepFilter || stage === accountTaskStepFilter || stageLabel === accountTaskStepFilter || rawStages.includes(accountTaskStepFilter) || eventId === accountTaskStepFilter || selectedRawStages.includes(stage) || selectedRawStages.includes(stageLabel) || rawStages.some(item => selectedRawStages.includes(item));
}
function accountTaskLogItemMatchesFilter(item) {
  if (!accountTaskStepFilter) return true;
  const fields = item?.fields && typeof item.fields === 'object' ? item.fields : {};
  const stepId = String(item?.main_step_id || fields.main_step_id || '').trim();
  const stage = String(item?.stage || fields.stage || '').trim();
  const eventId = String(item?.event_id || fields.event_id || '');
  const rawStages = Array.isArray(item?.raw_stages) ? item.raw_stages.map(String) : Array.isArray(fields.raw_stages) ? fields.raw_stages.map(String) : [];
  const selectedRawStages = accountTaskFilterRawStages();
  return stepId === accountTaskStepFilter || stage === accountTaskStepFilter || rawStages.includes(accountTaskStepFilter) || eventId === accountTaskStepFilter || selectedRawStages.includes(stage) || rawStages.some(item => selectedRawStages.includes(item));
}
function accountTaskFilterLabel() {
  if (!accountTaskStepFilter) return '全流程';
  const progress = accountTaskProgressSnapshot?.main_steps || [];
  const step = progress.find(item => accountTaskProgressStepId(item) === accountTaskStepFilter || (item.raw_stages || []).includes(accountTaskStepFilter));
  return step ? accountTaskProgressStepLabel(step) : accountTaskStepFilter;
}
function renderAccountTaskFilterBar() {
  const host = $('#accountTaskProgressFilter');
  if (!host) return;
  const selectedStep = taskProgressVisibleSteps(accountTaskProgressSnapshot?.main_steps).find(step => accountTaskProgressStepId(step) === accountTaskStepFilter || step.raw_stages?.includes(accountTaskStepFilter));
  host.innerHTML = `<span class="account-task-filter-label">当前查看：<strong>${esc(accountTaskFilterLabel())}</strong></span>${accountTaskStepFilter ? '<button type="button" class="account-task-filter-clear" data-account-task-filter-clear>清除筛选 · 查看全流程</button>' : ''}${selectedStep ? `<span class="account-task-selected-timing">开始 ${esc(selectedStep.started_at ? formatDateTime(selectedStep.started_at) : '—')} · 结束 ${esc(selectedStep.completed_at ? formatDateTime(selectedStep.completed_at) : '—')} · 耗时 ${esc(taskProgressStepDuration(selectedStep))}</span>` : ''}`;
}
function setAccountTaskStepFilter(stepId) {
  accountTaskStepFilter = stepId ? String(stepId) : null;
  renderAccountTaskProgressSnapshot(accountTaskProgressSnapshot);
  renderAccountTaskEvents();
  renderAccountTaskRunLog();
  renderAccountTaskFilterBar();
}

function renderAccountTaskEvents() {
  const content = $('#accountTaskLogContent');
  if (!content) return;
  // 展示顺序按校正后的时间排列，保留缓存和接口游标的 ID 顺序。
  const opened = rememberTaskLogDetails(content, 'data-event-id');
  const events = [...accountTaskEventCache].filter(accountTaskEventMatchesFilter).sort((left, right) => {
    const leftTime = Date.parse(left.created_at);
    const rightTime = Date.parse(right.created_at);
    return (Number.isNaN(leftTime) ? 0 : leftTime) - (Number.isNaN(rightTime) ? 0 : rightTime)
      || Number(left.id) - Number(right.id);
  });
  content.innerHTML = events.map(event => {
    const level = String(event.level || 'INFO').toUpperCase();
    const state = accountTaskEventStepState(event);
    const detail = meaningfulTaskDetail(event.detail);
    const css = level === 'ERROR' || state === 'failed' ? ' is-error' : level === 'WARNING' ? ' is-warning' : state === 'success' ? ' is-success' : '';
    const stepId = accountTaskEventStepId(event);
    const stageLabel = event.stage_label || ACCOUNT_TASK_STAGE_LABELS[normalizeAccountTaskStage(event.stage)] || event.stage || '事件';
    const mainSteps = accountTaskProgressSnapshot?.main_steps || [];
    const mainStep = mainSteps.find(item => item.id === stepId || (item.raw_stages || []).includes(event.raw_stage || event.stage));
    const association = mainStep ? ` · ${mainStep.label}` : stepId ? '' : ' · 未关联步骤';
    return `<div class="account-task-event${css}" data-event-id="${attrEsc(event.id)}">
      <div class="account-task-event-head"><span>${esc(formatDateTime(event.created_at))}</span><span>${esc(level)}</span><span>${esc(stageLabel)}${esc(association)}</span><span class="account-task-event-type">${esc(state ? ACCOUNT_TASK_STEP_STATE_LABELS[state] : '记录')}</span>${event.event_id ? `<span class="account-task-event-id">事件 ${esc(event.event_id)}</span>` : ''}</div>
      <div class="account-task-event-message">${esc(event.message || '-')}</div>
      ${detail ? `<details class="account-task-event-detail"><summary>查看技术详情</summary><pre>${esc(JSON.stringify(detail, null, 2))}</pre></details>` : ''}
    </div>`;
  }).join('') || `<div class="account-task-empty">${accountTaskStepFilter ? '当前步骤暂无关联事件' : '暂无事件'}</div>`;
  restoreTaskLogDetails(content, 'data-event-id', opened);
  renderAccountTaskFilterBar();
}

function renderAccountTaskRunLog() {
  const panel = $('#accountTaskRunLogContent');
  if (!panel) return;
  const opened = rememberTaskLogDetails(panel, 'data-log-key');
  const lines = accountTaskRunLogLines.filter(accountTaskLogItemMatchesFilter);
  panel.innerHTML = lines.map(item => {
    const fields = meaningfulTaskDetail(item.fields);
    const formattedTimestamp = formatDateTime(item.ts);
    const timestamp = formattedTimestamp === '-' ? '时间缺失' : formattedTimestamp;
    const rawStages = Array.isArray(item?.raw_stages) ? item.raw_stages : Array.isArray(item?.fields?.raw_stages) ? item.fields.raw_stages : [];
    const stepId = item?.main_step_id || item?.fields?.main_step_id || '';
    const label = stepId || rawStages.length ? (item.stage_label || item.stage || '未关联步骤') : '未关联步骤';
    const detail = fields
      ? `<details class="account-task-log-detail"><summary>查看技术详情</summary><pre>${esc(JSON.stringify(fields, null, 2))}</pre></details>`
      : '';
    return `<div class="account-task-log-line" data-log-key="${esc(`${item.event_uuid || item.event_id || ''}|${item.ts || ''}|${String(item.message || '').slice(0, 100)}`)}"><span>${esc(`${timestamp} ${item.level || 'INFO'} ${label} ${item.message || ''}`)}</span>${detail}</div>`;
  }).join('') || `<div class="account-task-empty">${accountTaskStepFilter ? '当前步骤暂无关联运行日志' : '(当前 Run 暂无技术日志；旧任务可能只有事件时间线)'}</div>`;
  restoreTaskLogDetails(panel, 'data-log-key', opened);
}

function updateAccountTaskTimeZoneHints() {
  const text = `时间按当前浏览器时区显示 · ${browserTimeZoneName()}`;
  document.querySelectorAll('[data-browser-timezone-hint]').forEach(element => {
    element.textContent = text;
    element.title = text;
  });
}
updateAccountTaskTimeZoneHints();

function renderAccountTaskArtifacts(task) {
  const panel = $('#accountTaskArtifactContent');
  if (!panel) return;
  const resources = (task?.resources || []).filter(item => !activeAccountTaskRunId || String(item.run_id || '') === String(activeAccountTaskRunId));
  const run = (task?.runs || []).find(item => String(item.id) === String(activeAccountTaskRunId));
  const debug = run?.debug_artifacts;
  const browserKept = run?.result_summary?.debug_browser_kept === true;
  const diagnostic = debug?.available ? `<div class="account-task-artifact"><strong>Roxy 刷新调试</strong><div>${debug.state === 'recording' ? '正在抓包' : '诊断已保存'} · 请求 ${esc(debug.summary?.request_count || 0)} 条${browserKept ? ' · 失败窗口已保留，可在 Roxy 中查看' : ''}</div><div class="account-task-artifact-links"><a href="${esc(debug.har_url)}" download>下载 HAR</a>${debug.page_state_url ? `<a href="${esc(debug.page_state_url)}" download>下载页面现场</a>` : ''}${debug.screenshot_url ? `<a href="${esc(debug.screenshot_url)}" target="_blank" rel="noopener">查看失败截图</a>` : ''}</div></div>` : '';
  panel.innerHTML = diagnostic + resources.map(item => `<div class="account-task-artifact"><strong>${esc(item.resource_type || '运行资源')}</strong><div>${esc(item.provider || item.state || '-')}</div><small>${esc(formatDateTime(item.acquired_at || item.created_at))}</small></div>`).join('') || '<div class="account-task-empty">当前 Run 没有诊断资源或产物</div>';
}

function setAccountTaskDetailView(view) {
  activeAccountTaskDetailView = ['events','logs','artifacts'].includes(view) ? view : 'events';
  document.querySelectorAll('[data-account-task-detail-tab]').forEach(button => {
    button.classList.toggle('is-active', button.dataset.accountTaskDetailTab === activeAccountTaskDetailView);
  });
  document.querySelectorAll('[data-account-task-detail-view]').forEach(panel => {
    panel.classList.toggle('hidden', panel.dataset.accountTaskDetailView !== activeAccountTaskDetailView);
  });
  $('#accountTaskNewEvents')?.classList.toggle('hidden', activeAccountTaskDetailView !== 'events' || accountTaskNewEventCount <= 0);
  if (activeAccountTaskDetailView === 'logs' && activeAccountTaskRunId) pollAccountTaskRunLog();
  if (activeAccountTaskDetailView === 'artifacts') renderAccountTaskArtifacts(accountTaskSnapshot);
}

function resetAccountTaskRunData(runId) {
  hideAccountTaskStepTooltip();
  closeAccountTaskStepDialog(false);
  activeAccountTaskRunId = runId ? String(runId) : null;
  accountTaskStepPage = 0;
  accountTaskStepPageSize = 0;
  accountTaskStepFilter = accountTaskPendingStepFilter || null;
  accountTaskPendingStepFilter = null;
  accountTaskEventCursor = null;
  accountTaskEventCache = [];
  accountTaskNewEventCount = 0;
  accountTaskRunLogCursor = null;
  accountTaskRunLogLines = [];
  accountTaskProgressSnapshot = null;
  accountTaskProgressError = '';
  accountTaskProgressRequestId += 1;
  $('#accountTaskLogContent').innerHTML = '<div class="account-task-empty">正在加载事件…</div>';
  $('#accountTaskRunLogContent').textContent = '正在加载运行日志…';
  $('#accountTaskNewEvents')?.classList.add('hidden');
  renderAccountTaskProgressSnapshot(null);
}

function syncAccountTaskRunPicker(task) {
  const select = $('#accountTaskRunSelect');
  const runs = Array.isArray(task?.runs) ? task.runs : [];
  const desired = String(activeAccountTaskRunId || task?.last_run_id || runs[runs.length - 1]?.id || '') || null;
  select.innerHTML = runs.map(run => `<option value="${attrEsc(run.id)}">第 ${esc(run.run_no || '-')} 次 · ${esc(run.status || '-')}</option>`).join('');
  if (desired && runs.some(run => String(run.id) === desired)) select.value = String(desired);
  const selected = String(select.value || desired || '') || null;
  if (selected !== activeAccountTaskRunId) resetAccountTaskRunData(selected);
  select.disabled = runs.length <= 1;
}

async function pollAccountTaskEvents(reset = false) {
  if (!activeAccountTaskId || !activeAccountTaskRunId) return;
  const requestId = accountTaskRequestId;
  const taskId = String(activeAccountTaskId);
  const runId = String(activeAccountTaskRunId);
  const scroller = $('#accountTaskLogContent')?.parentElement;
  const atBottom = !scroller || scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 36;
  const params = new URLSearchParams({limit:'500'});
  if (!reset && accountTaskEventCursor != null) params.set('after_id', String(accountTaskEventCursor));
  const result = await api(`/api/operations/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(runId)}/events?${params}`);
  if (requestId !== accountTaskRequestId || taskId !== String(activeAccountTaskId) || runId !== String(activeAccountTaskRunId)) return;
  const incoming = result.items || [];
  if (reset || accountTaskEventCursor == null) accountTaskEventCache = incoming;
  else {
    const known = new Set(accountTaskEventCache.map(item => String(item.id)));
    accountTaskEventCache.push(...incoming.filter(item => !known.has(String(item.id))));
  }
  accountTaskEventCursor = Number(result.next_after_id || accountTaskEventCursor || 0);
  renderAccountTaskEvents();
  if (atBottom && scroller) scroller.scrollTop = scroller.scrollHeight;
  else if (incoming.length) {
    accountTaskNewEventCount += incoming.length;
    const button = $('#accountTaskNewEvents');
    button.textContent = `有 ${accountTaskNewEventCount} 条新事件，回到底部`;
    button.classList.toggle('hidden', activeAccountTaskDetailView !== 'events');
  }
}

async function pollAccountTaskProgress() {
  if (!activeAccountTaskId || !activeAccountTaskRunId) return;
  const taskId = String(activeAccountTaskId);
  const runId = String(activeAccountTaskRunId);
  const detailRequestId = accountTaskRequestId;
  const requestId = ++accountTaskProgressRequestId;
  try {
    const result = await api(`/api/operations/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(activeAccountTaskRunId)}/progress`);
    if (detailRequestId !== accountTaskRequestId || requestId !== accountTaskProgressRequestId || taskId !== String(activeAccountTaskId) || runId !== String(activeAccountTaskRunId)) return;
    accountTaskProgressSnapshot = result.progress || null;
    accountTaskProgressError = '';
    renderAccountTaskProgressSnapshot(accountTaskProgressSnapshot);
  } catch (e) {
    if (detailRequestId !== accountTaskRequestId || requestId !== accountTaskProgressRequestId || taskId !== String(activeAccountTaskId) || runId !== String(activeAccountTaskRunId)) return;
    accountTaskProgressError = e.message || '进度更新失败';
    // 保留最近的完整快照；首次读取失败时不从分页事件推导不完整进度。
    if (accountTaskProgressSnapshot) renderAccountTaskProgressSnapshot(accountTaskProgressSnapshot);
  }
}

async function pollAccountTaskRunLog(reset = false) {
  if (!activeAccountTaskId || !activeAccountTaskRunId) return;
  const requestId = accountTaskRequestId;
  const taskId = String(activeAccountTaskId);
  const runId = String(activeAccountTaskRunId);
  const params = new URLSearchParams({limit:'500'});
  if (!reset && accountTaskRunLogCursor != null) params.set('cursor', String(accountTaskRunLogCursor));
  const result = await api(`/api/operations/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(runId)}/logs?${params}`);
  if (requestId !== accountTaskRequestId || taskId !== String(activeAccountTaskId) || runId !== String(activeAccountTaskRunId)) return;
  if (reset || accountTaskRunLogCursor == null) accountTaskRunLogLines = result.items || [];
  else accountTaskRunLogLines.push(...(result.items || []));
  accountTaskRunLogCursor = Number(result.next_cursor || 0);
  renderAccountTaskRunLog();
}

function openAccountTaskLog(taskId, runId = null, stepId = null) {
  accountTaskRequestId += 1;
  activeAccountTaskId = String(taskId);
  accountTaskPendingStepFilter = stepId ? String(stepId) : null;
  accountTaskSnapshot = null;
  resetAccountTaskRunData(runId || null);
  setAccountTaskDetailView('events');
  $('#accountTaskLogId').textContent = taskId;
  $('#accountTaskDetailSummary').textContent = '正在加载任务摘要…';
  renderTaskLogErrorSummary('accountTaskLogErrorSummary', null);
  renderAccountTaskStageProgress(null);
  $('#accountTaskLogPanel').classList.remove('hidden');
  updateModalScrollLock();
  $('#btnCloseAccountTaskLog')?.focus({preventScroll:true});
  clearInterval(accountTaskLogTimer);
  pollAccountTaskLog();
  accountTaskLogTimer = setInterval(pollAccountTaskLog, 2000);
}

function renderAccountTaskSelectedRunError(run) {
  const error = run?.error_message || '';
  const info = run?.error_info || null;
  renderTaskLogErrorSummary('accountTaskLogErrorSummary', {
    error_message: error,
    error_info: info ? {...info, summary: accountTaskErrorDisplayText(info, error)} : null,
  });
}

async function pollAccountTaskLog() {
  if (!activeAccountTaskId || accountTaskPolling) return;
  const requestId = accountTaskRequestId;
  const taskId = String(activeAccountTaskId);
  accountTaskPolling = true;
  try {
    const result = await api(`/api/operations/${encodeURIComponent(taskId)}?include_events=0`);
    if (requestId !== accountTaskRequestId || taskId !== String(activeAccountTaskId)) return;
    const task = result.task || {};
    accountTaskSnapshot = task;
    const previousRunId = activeAccountTaskRunId;
    syncAccountTaskRunPicker(task);
    if (requestId !== accountTaskRequestId || taskId !== String(activeAccountTaskId)) return;
    const selectedRun = (task.runs || []).find(run => String(run.id) === String(activeAccountTaskRunId)) || {};
    renderAccountTaskSelectedRunError(selectedRun.id ? selectedRun : task);
    const waitReasons = accountTaskAdmissionReasons(selectedRun.id ? selectedRun : task);
    const waitText = (selectedRun.status || task.status) === 'queued' && waitReasons.length
      ? ` · ${waitReasons.map(accountTaskAdmissionReasonText).join('；')}` : '';
    $('#accountTaskDetailSummary').textContent = `${facetLabel('task_type', task.task_type)} · ${selectedRun.debug_pause ? taskDebugPauseSummary(selectedRun.debug_pause) : `${facetLabel('status', selectedRun.status || task.status)} · ${formatTaskDuration(selectedRun.duration_ms)}${waitText}`}`;
    await pollAccountTaskProgress();
    if (requestId !== accountTaskRequestId || taskId !== String(activeAccountTaskId)) return;
    if (previousRunId !== activeAccountTaskRunId || accountTaskEventCursor == null) {
      await pollAccountTaskEvents(true);
      if (activeAccountTaskDetailView === 'logs') await pollAccountTaskRunLog(true);
    } else {
      await pollAccountTaskEvents(false);
      if (activeAccountTaskDetailView === 'logs') await pollAccountTaskRunLog(false);
    }
    if (requestId !== accountTaskRequestId || taskId !== String(activeAccountTaskId)) return;
    renderAccountTaskArtifacts(task);
    if (!accountTaskIsActive(task)) {
      clearInterval(accountTaskLogTimer);
      loadAccountTasks();
      loadAccounts();
    }
  } catch (e) {
    if (requestId === accountTaskRequestId && taskId === String(activeAccountTaskId)) {
      $('#accountTaskLogContent').innerHTML = `<div class="account-task-empty">加载失败：${esc(e.message)}</div>`;
    }
  } finally {
    accountTaskPolling = false;
  }
}

$('#accountTaskRunSelect')?.addEventListener('change', event => {
  resetAccountTaskRunData(String(event.target.value || '') || null);
  pollAccountTaskLog();
});
$('#accountTaskLogPanel')?.addEventListener('wheel', scrollAccountTaskDialogFromWheel, {passive:false});
$('#accountTaskStageProgress')?.addEventListener('click', event => {
  const details = event.target.closest('[data-account-task-step-details]');
  if (details) { openAccountTaskStepDialog(details.dataset.accountTaskStepDetails, details.dataset.stepDetailTab, details); return; }
  const failure = event.target.closest('[data-account-task-failure-details]');
  if (failure) { openAccountTaskStepDialog(null, 'failure', failure); return; }
  const childDetails = event.target.closest('[data-account-task-child-details]');
  if (childDetails) { openAccountTaskStepDialog(null, 'children', childDetails); return; }
  const pager = event.target.closest('[data-account-task-step-page]');
  if (pager) {
    if (pager.disabled) return;
    const forward = Number(pager.dataset.accountTaskStepPage) > accountTaskStepPage;
    accountTaskStepPage = Number(pager.dataset.accountTaskStepPage);
    renderAccountTaskProgressSnapshot(accountTaskProgressSnapshot);
    const buttons = Array.from($('#accountTaskStageProgress').querySelectorAll('[data-account-task-step-page]'));
    (buttons.find(item => Number(item.dataset.accountTaskStepPage) === accountTaskStepPage + (forward ? 1 : -1) && !item.disabled) || buttons.find(item => !item.disabled))?.focus({preventScroll:true});
    return;
  }
  const child = event.target.closest('[data-account-task-child]');
  if (child) { openAccountTaskLog(Number(child.dataset.accountTaskChild), Number(child.dataset.childRun) || null); return; }
  const step = event.target.closest('[data-account-task-step]');
  if (!step) return;
  const id = step.dataset.accountTaskStep || '';
  setAccountTaskStepFilter(accountTaskStepFilter === id ? null : id);
});
$('#accountTaskStageProgress')?.addEventListener('keydown', event => {
  const step = event.target.closest('[data-account-task-step-filter]');
  if (!step || !['Enter', ' '].includes(event.key)) return;
  event.preventDefault();
  step.click();
});
$('#btnCloseAccountTaskStepDetail')?.addEventListener('click', () => closeAccountTaskStepDialog());
$('#btnCloseAccountTaskLog')?.addEventListener('click', () => { hideAccountTaskStepTooltip(); closeAccountTaskStepDialog(false); });
$('#accountTaskStepDetailOverlay')?.addEventListener('click', event => {
  if (event.target.id === 'accountTaskStepDetailOverlay') { closeAccountTaskStepDialog(); return; }
  const tab = event.target.closest('[data-step-dialog-tab]');
  if (tab && accountTaskStepDetailState) {
    accountTaskStepDetailState.tab = tab.dataset.stepDialogTab;
    $('#accountTaskStepDetailContent').scrollTop = 0;
    renderAccountTaskStepDialog();
  }
  const child = event.target.closest('[data-account-task-child]');
  if (child) { closeAccountTaskStepDialog(false); openAccountTaskLog(Number(child.dataset.accountTaskChild), Number(child.dataset.childRun) || null); }
});
$('#accountTaskStepDetailTabs')?.addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || !accountTaskStepDetailState) return;
  const buttons = Array.from(event.currentTarget.querySelectorAll('button'));
  const index = buttons.indexOf(document.activeElement);
  if (index < 0) return;
  event.preventDefault();
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
  buttons[next].click();
  Array.from(event.currentTarget.querySelectorAll('button'))[next]?.focus({preventScroll:true});
});
document.addEventListener('keydown', event => {
  if (!accountTaskStepDetailState) return;
  if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); closeAccountTaskStepDialog(); return; }
  if (event.key !== 'Tab') return;
  const controls = Array.from($('#accountTaskStepDetailDialog')?.querySelectorAll('button, [href], summary, [tabindex]:not([tabindex="-1"])') || []).filter(item => !item.disabled && item.getClientRects().length);
  const first = controls[0], last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}, true);
if (typeof ResizeObserver !== 'undefined' && $('#accountTaskStageProgress')) {
  new ResizeObserver(entries => {
    const width = entries[0]?.contentRect?.width || 0;
    if (width > 0 && accountTaskProgressSnapshot && accountTaskProgressPageSize(width, taskProgressVisibleSteps(accountTaskProgressSnapshot.main_steps).length) !== accountTaskStepPageSize) renderAccountTaskProgressSnapshot(accountTaskProgressSnapshot);
  }).observe($('#accountTaskStageProgress'));
}
$('#accountTaskProgressFilter')?.addEventListener('click', event => {
  if (event.target.closest('[data-account-task-filter-clear]') || event.target.closest('[data-account-task-filter-all]')) setAccountTaskStepFilter(null);
});
document.querySelectorAll('[data-account-task-detail-tab]').forEach(button => button.addEventListener('click', () => setAccountTaskDetailView(button.dataset.accountTaskDetailTab)));
$('#accountTaskNewEvents')?.addEventListener('click', () => {
  const scroller = $('#accountTaskLogContent')?.parentElement;
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
  accountTaskNewEventCount = 0;
  $('#accountTaskNewEvents').classList.add('hidden');
});
async function operationIntent(scope, url, body) {
  const storageKey=`turb_operation_intent:${scope}`;
  const signature=JSON.stringify({url,body:body||null});
  let saved=null;try{saved=JSON.parse(sessionStorage.getItem(storageKey)||'null');}catch(_){}
  if(saved&&saved.signature!==signature)throw new Error('上次重跑回执尚未确认，请保持原选择重试以找回原请求。');
  saved ||= {key:globalThis.crypto?.randomUUID?.()||`operation-${Date.now()}-${Math.random().toString(36).slice(2)}`,signature};
  sessionStorage.setItem(storageKey,JSON.stringify(saved));
  try {
    const result=await api(url,{method:'POST',headers:{'Idempotency-Key':saved.key,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
    sessionStorage.removeItem(storageKey);return result;
  }catch(error){if([400,403,404,409,410,422,429].includes(error.status))sessionStorage.removeItem(storageKey);throw error;}
}
async function retryAccountTask(taskId, button) {
  button.disabled = true;
  try {
    const result = await operationIntent(`retry:${taskId}`,`/api/operations/${encodeURIComponent(taskId)}/retry`);
    const receipt = result.data || result;
    showToast(receipt.round_id || receipt.bulk_round_id ? '重跑已受理，已创建所属批次的新轮次' : '任务已重新入队');
    loadAccountTasks();
  } catch (e) {
    showToast('重跑失败: ' + e.message);
    button.disabled = false;
  }
}
async function terminateAccountTask(taskId, button) {
  const task = ACCOUNT_TASKS.find(item => Number(item.id) === Number(taskId));
  const queued = task?.status === 'queued';
  const label = queued ? '取消' : '终止';
  const message = queued
    ? `确定${label}排队中的任务 #${taskId}？`
    : `确定${label}任务 #${taskId}？\n\n任务会立即从任务中心收口；如果已经向远端发起写入，结果可能需要人工核验。`;
  if (!window.confirm(message)) return;
  button.disabled = true;
  try {
    const result = await api(`/api/operations/${encodeURIComponent(taskId)}/terminate`, {method:'POST'});
    const state = String(result.state || '');
    showToast(state === 'cancelled' ? '任务已取消' : state === 'attention_required' ? '任务已终止，但远端结果待核验' : '任务已终止');
    loadAccountTasks();
  } catch (e) {
    showToast(`${label}失败: ` + e.message);
    button.disabled = false;
  }
}
async function deleteAccountTask(taskId, button) {
  const task = ACCOUNT_TASKS.find(item => Number(item.id) === Number(taskId));
  if (!task || accountTaskIsActive(task)) {
    showToast('执行中的任务不能删除，请先停止任务');
    return;
  }
  if (!window.confirm(`确定删除任务 #${taskId}？\n\n删除后任务会从任务中心隐藏，历史审计记录仍会保留。`)) return;
  button.disabled = true;
  try {
    await api(`/api/operations/${encodeURIComponent(taskId)}/delete`, {method:'POST'});
    showToast('任务已删除');
    ACCOUNT_TASK_SELECTED.delete(Number(taskId));
    await loadAccountTasks();
  } catch (e) {
    showToast('删除失败: ' + e.message);
    button.disabled = false;
  }
}
async function bulkAccountTasks(action) {
  const selected = accountTaskSelectedRows();
  const eligible = selected.filter(task => action === 'retry'
    ? accountTaskCanRetry(task)
    : action === 'cancel'
      ? String(task.status || '').toLowerCase() === 'queued'
      : action === 'delete'
        ? !accountTaskIsActive(task)
        : accountTaskCanTerminate(task));
  if (!eligible.length) {
    showToast(action === 'retry' ? '选中任务中没有可重跑项' : action === 'cancel' ? '选中任务中没有排队项' : action === 'delete' ? '选中任务中没有可删除项' : '选中任务中没有可终止的原生运行任务');
    return;
  }
  const label = action === 'retry' ? '重跑' : action === 'cancel' ? '取消排队' : action === 'delete' ? '删除' : '终止运行';
  const warning = action === 'retry'
    ? '原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。'
    : action === 'cancel'
      ? '只会取消尚未开始的排队任务。'
      : action === 'delete'
        ? '任务会从任务中心隐藏，历史审计记录仍会保留；执行中的任务会跳过。'
        : '运行中的任务会立即收口；如果已经向远端发起写入，结果可能需要人工核验。';
  if (!window.confirm(`确定${label}选中的 ${eligible.length} 个任务吗？\n\n${warning}`)) return;
  const buttonId = action === 'retry' ? 'btnRetrySelectedAccountTasksV2' : action === 'cancel' ? 'btnCancelSelectedAccountTasksV2' : action === 'delete' ? 'btnDeleteSelectedAccountTasksV2' : 'btnTerminateSelectedAccountTasksV2';
  const button = document.getElementById(buttonId);
  if (button) button.disabled = true;
  try {
    const result = action==='retry'
      ? await operationIntent('bulk:retry','/api/operations/bulk',{action,task_ids:eligible.map(task=>Number(task.id))})
      : await api('/api/operations/bulk', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,task_ids:eligible.map(task=>Number(task.id))})});
    const skipped = Number(result.skipped_count || 0);
    if (action === 'cancel') {
      const accepted = Array.isArray(result.accepted) ? result.accepted : [];
      const cancelled = accepted.filter(item => item.state === 'cancelled').length;
      const cancelling = accepted.filter(item => item.state === 'cancelling').length;
      const other = accepted.length - cancelled - cancelling;
      const summary = [`已取消 ${cancelled} 个`, `取消中 ${cancelling} 个`];
      if (other) summary.push(`已受理 ${other} 个`);
      if (skipped) summary.push(`跳过 ${skipped} 个`);
      const message = summary.join('，');
      showToast(message);
      accepted.forEach(item => ACCOUNT_TASK_SELECTED.delete(Number(item.task_id)));
      renderAccountTasks();
      if (skipped) {
        const details = (result.skipped || []).map(item => `#${item.task_id}：${item.error || '操作未接受'}`);
        window.alert(`${message}\n\n${details.join('\n')}`);
      }
    } else {
      showToast(`已${label} ${Number(result.accepted_count || 0)} 个${skipped ? `，跳过 ${skipped} 个` : ''}`);
      ACCOUNT_TASK_SELECTED.clear();
    }
    await loadAccountTasks();
  } catch (e) {
    showToast(`${label}失败: ` + e.message);
  } finally {
    updateAccountTaskSelectionUi();
  }
}
function updateAccountTaskFilters(facets = {}) {
  const selectedType = document.getElementById('accountTaskTypeFilterV2')?.value || '';
  const selectedTypes = selectedType.split(',').filter(Boolean);
  const types = [...(facets.task_type || [])];
  if (selectedTypes.length > 1) {
    types.push({value: selectedType, label: '并发分类中的全部任务类型',
      count: Math.max(1, types.filter(item => selectedTypes.includes(item.value)).reduce((sum, item) => sum + Number(item.count || 0), 0))});
  }
  syncFacetSelect('accountTaskTypeFilterV2', types, {
    group: 'task_type',
    values: ['registration', 'registration_resume', 'account_setup_retry', 'password_setup', 'password_change', 'twofa_setup', 'twofa_change', 'account_completion', 'email_change', 'twofa_retry', 'codex_retry', 'codex_token_refresh', 'sub2api_sync', 'c2a_session_reimport', 'live_check', 'token_refresh', 'plan_check', 'deactivation_mail', 'extract_link', 'account_inspection', 'account_inspection_batch'],
  });
  syncFacetSelect('accountTaskStatusFilterV2', facets.status, {
    group: 'status',
    values: ['queued', 'running', 'success', 'partial_success', 'failed', 'deactivated', 'unsupported', 'attention_required', 'request_unknown', 'interrupted', 'stopped', 'cancelled'],
  });
  syncFacetSelect('accountTaskTargetStatusFilterV2', facets.target_status, {group: 'target_status'});
  syncFacetSelect('accountTaskRunCountFilterV2', facets.run_count, {group: 'run_count', values: ['0', '1', '2', '3', '4+']});
  syncFacetSelect('accountTaskStageFilterV2', facets.stage, {group: 'stage'});
}

let accountTaskFilterTimer = null;
function scheduleAccountTaskFilterReload(immediate = false) {
  PAGERS.accountTasks.page = 1;
  ACCOUNT_TASK_SELECTED.clear();
  refreshColumnFilterStates();
  clearTimeout(accountTaskFilterTimer);
  if (immediate) {
    loadAccountTasks();
    return;
  }
  accountTaskFilterTimer = setTimeout(loadAccountTasks, 260);
}
$('#btnRefreshAccountTasks')?.addEventListener('click', () => loadAccountTasks({forceMetadata:true}));
$('#btnRetrySelectedAccountTasksV2')?.addEventListener('click', () => bulkAccountTasks('retry'));
$('#btnCancelSelectedAccountTasksV2')?.addEventListener('click', () => bulkAccountTasks('cancel'));
$('#btnTerminateSelectedAccountTasksV2')?.addEventListener('click', () => bulkAccountTasks('terminate'));
$('#btnDeleteSelectedAccountTasksV2')?.addEventListener('click', () => bulkAccountTasks('delete'));
$('#accountTasksSelectAllV2')?.addEventListener('change', event => syncAccountTasksSelectAll(event.target.checked));
['accountTaskIdFilterV2', 'accountTaskTargetFilterV2', 'accountTaskBatchFilterV2', 'accountTaskResultFilterV2'].forEach(id => {
  document.getElementById(id)?.addEventListener('input', () => scheduleAccountTaskFilterReload());
});
['accountTaskTypeFilterV2', 'accountTaskStatusFilterV2', 'accountTaskTargetStatusFilterV2', 'accountTaskRunCountFilterV2', 'accountTaskStageFilterV2', 'accountTaskDateFromV2', 'accountTaskDateToV2'].forEach(id => {
  document.getElementById(id)?.addEventListener('change', () => scheduleAccountTaskFilterReload(true));
});
$('#btnResetAccountTaskFiltersV2')?.addEventListener('click', () => {
  clearTimeout(accountTaskFilterTimer);
  ['accountTaskIdFilterV2', 'accountTaskTypeFilterV2', 'accountTaskTargetFilterV2', 'accountTaskStatusFilterV2', 'accountTaskTargetStatusFilterV2', 'accountTaskBatchFilterV2', 'accountTaskRunCountFilterV2', 'accountTaskStageFilterV2', 'accountTaskDateFromV2', 'accountTaskDateToV2', 'accountTaskResultFilterV2'].forEach(id => {
    const control = document.getElementById(id);
    if (control) control.value = '';
  });
  scheduleAccountTaskFilterReload(true);
});
$('#accountTasksPanel')?.addEventListener('click', event => {
  const batchBtn = event.target.closest('[data-account-bulk-batch]');
  if (batchBtn && window.BulkTasks) { BulkTasks.navigate('detail', {batch_id:batchBtn.dataset.accountBulkBatch, round_id:batchBtn.dataset.accountBulkRound || ''}); return; }
  const logBtn = event.target.closest('[data-account-task-log]');
  if (logBtn) { openAccountTaskLog(Number(logBtn.dataset.accountTaskLog)); return; }
  const retryBtn = event.target.closest('[data-account-task-retry]');
  if (retryBtn) { retryAccountTask(Number(retryBtn.dataset.accountTaskRetry), retryBtn); return; }
  const deleteBtn = event.target.closest('[data-account-task-delete]');
  if (deleteBtn) { deleteAccountTask(Number(deleteBtn.dataset.accountTaskDelete), deleteBtn); return; }
  const terminateBtn = event.target.closest('[data-account-task-terminate]');
  if (terminateBtn) terminateAccountTask(Number(terminateBtn.dataset.accountTaskTerminate), terminateBtn);
});
$('#accountTasksPanel')?.addEventListener('change', event => {
  const checkbox = event.target.closest('[data-account-task-select]');
  if (!checkbox) return;
  const taskId = Number(checkbox.dataset.accountTaskSelect);
  if (checkbox.checked) ACCOUNT_TASK_SELECTED.add(taskId);
  else ACCOUNT_TASK_SELECTED.delete(taskId);
  renderAccountTasks();
});
// 步骤详情的捕获监听先于共享提示处理 Escape。
bindAccountsHoverTooltips();
function accountTaskResultTooltipText(task) {
  const result = task.result_summary || {};
  const status = _accountCountryTaskState(result, task.status);
  const displays = _accountCountryPromotionDisplays({...result, plan_check_status: result.plan_check_status || task.status});
  const details = [
    result.current_plan_type ? `套餐 ${result.current_plan_type}` : '套餐查询结果',
    status?.state,
    status?.failedText,
    ...(Array.isArray(result.country_failures) ? result.country_failures : []).map(row => `${row.country}：${row.summary || '诊断记录不完整'}`),
  ];
  if (displays.length) {
    displays.forEach(display => {
      details.push([
        `${display.country}${display.stale ? '（历史）' : ''}`,
        ...display.items.map(item => _accountPromotionTooltip(item)),
        display.context,
      ].filter(Boolean).join('\n'));
    });
  } else {
    details.push(..._accountPromotions(result).map(item => _accountPromotionTooltip(item)));
  }
  return details.filter(Boolean).join('\n');
}
function accountTaskPlanResultMarkup(task) {
  const summary = accountTaskResultText(task, true);
  return `<button type="button" class="account-task-result-summary" data-account-task-result-tooltip="${esc(task.id || '')}" data-accounts-tooltip="${esc(accountTaskResultTooltipText(task))}" aria-label="${esc(`查看套餐查询详情：${summary}`)}">${esc(summary)}</button>`;
}
