// ---------- 账号 ----------
let accountsLoading = false;
let accountsReloadQueued = false;
let planStatusLoading = false;
let planStatusRevision = '';
let ACCOUNT_BATCH_WORKERS = 3;
const ACCOUNT_TASK_TYPE_LABELS = LIST_FACET_LABELS.task_type;
const ACCOUNT_TASK_TRIGGER_LABELS = {
  manual:'手动', manual_bulk:'手动批量', manual_retry:'失败重跑', scheduled:'定时',
  registration_auto:'注册后自动', registration_job_retry:'注册任务重试', token_refresh_scheduled:'AT 定时刷新',
  codex_token_refresh_scheduled:'Codex 定时刷新'
};
const ACCOUNT_TASK_STAGE_LABELS = LIST_FACET_LABELS.stage;
const OPERATION_TARGET_LABELS = LIST_FACET_LABELS.target_status;
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
function accountTaskResultText(task) {
  const status = String(task.status || '');
  if (status === 'queued') return '等待执行';
  if (status === 'running') return '执行中';
  if (task.error_message) return task.error_message;
  const result = task.result_summary || {};
  if (task.task_type === 'registration' || task.task_type === 'registration_resume') {
    return OPERATION_TARGET_LABELS[task.target_status] || task.target_status || '注册执行已结束';
  }
  if (task.task_type === 'plan_check') return result.current_plan_type ? `套餐 ${result.current_plan_type}${result.plus_trial_eligible ? ' · 可 Plus 试用' : ''}` : '查询完成';
  if (task.task_type === 'deactivation_mail') {
    if (!Object.prototype.hasOwnProperty.call(result, 'detected')) return '-';
    return result.detected ? '发现封号邮件' : '未发现封号邮件';
  }
  if (task.task_type === 'live_check' || task.task_type === 'token_refresh') return result.ok ? '账号正常' : (result.status || '-');
  if (['account_setup_retry','password_setup','twofa_setup','account_completion'].includes(task.task_type)) return result.ok ? (result.message || '账号配置操作已完成') : (result.message || result.status || '账号配置补跑失败');
  if (task.task_type === 'codex_retry') {
    if (result.ok) return result.credential_confirmed ? '授权成功 · 凭证已确认' : '授权成功';
    if (result.status === 'attention_required') return 'Callback 已接收 · 凭证待确认';
    return result.message || result.status || '补跑失败';
  }
  if (task.task_type === 'codex_token_refresh') {
    if (!result.ok) return 'OAuth Token 刷新失败';
    return result.sub2_sync === 'failed' ? 'Token 已刷新 · sub2 同步失败' : 'OAuth Token 已刷新';
  }
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
  partial_success:'部分完成', cancelled:'已取消', interrupted:'已中断', attention_required:'待确认'
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
  const status = String(step?.display_status || step?.state || 'pending');
  return ACCOUNT_TASK_PROGRESS_STATUS_LABELS[status] || ACCOUNT_TASK_STEP_STATE_LABELS[status] || status;
}
function renderAccountTaskProgressSnapshot(progress) {
  const panel = $('#accountTaskStageProgress');
  if (!panel) return;
  const stages = Array.isArray(progress?.main_steps) ? progress.main_steps : [];
  if (!stages.length) {
    panel.classList.add('hidden');
    panel.innerHTML = '';
    return;
  }
  const current = progress.current;
  const currentText = current
    ? `当前：${current.label || current.step_id}${current.child_label ? ` · ${current.child_label}` : ''}`
    : `结果：${progress.outcome?.status || '未开始'}`;
  const sourceText = progress.source === 'legacy_derived' ? '历史记录按已有结构化事件还原' : '';
  const track = stages.map(stage => {
    const state = String(stage.state || 'pending');
    const children = Array.isArray(stage.children) ? stage.children : [];
    const childrenHtml = children.length
      ? `<div class="account-task-stage-children">${children.map(child => `<span class="account-task-stage-child is-${attrEsc(child.state || 'pending')}">${esc(child.label || child.step_id)} · ${esc(accountTaskProgressStateLabel(child))}</span>`).join('')}</div>`
      : '';
    return `<div class="account-task-stage-step is-${attrEsc(state)}"><span class="account-task-stage-node"></span><span class="account-task-stage-label">${esc(stage.label || stage.id)}</span><span class="account-task-stage-state">${esc(accountTaskProgressStateLabel(stage))}</span>${childrenHtml}</div>`;
  }).join('');
  panel.innerHTML = `<div class="account-task-stage-current"><strong>${esc(currentText)}</strong>${sourceText ? `<small>${esc(sourceText)}</small>` : ''}</div><div class="account-task-stage-track">${track}</div>`;
  panel.classList.remove('hidden');
}
function renderAccountTaskStageProgress(task, selectedRunId = null) {
  renderAccountTaskProgressSnapshot(task?.progress || null);
}
function renderAccountTasks() {
  const body = $('#accountTasksBody');
  if (!body) return;
  body.innerHTML = ACCOUNT_TASKS.map(task => {
    const result = accountTaskResultText(task);
    const active = ['queued','running','stopping','cancelling','settling','waiting'].includes(String(task.status || ''));
    const retryable = Array.isArray(task.next_actions) && task.next_actions.length > 0 && !active;
    const cancellable = task.source_system === 'native_operations' && active;
    const target = task.account_id ? `账号 #${task.account_id}` : (task.attempt_id ? `注册尝试 #${task.attempt_id}` : '-');
    const batch = task.batch_title || (task.batch_uuid ? short(task.batch_uuid, 12) : '单任务');
    const trigger = ACCOUNT_TASK_TRIGGER_LABELS[task.trigger] || task.trigger || '-';
    const stage = ACCOUNT_TASK_STAGE_LABELS[normalizeAccountTaskStage(task.current_stage)] || task.current_stage || '-';
    const error = task.error_message || '';
    return `<tr>
      <td>#${esc(task.id)}</td>
      <td>${esc(ACCOUNT_TASK_TYPE_LABELS[task.task_type] || task.task_type)}</td>
      <td title="${esc(task.email_snapshot)}"><strong>${esc(target)}</strong><div class="sub-cell">${esc(task.email_snapshot || '-')}</div></td>
      <td>${pillV2(task.status)}</td>
      <td>${pillV2(task.target_status)}</td>
      <td title="${esc(batch)} · ${esc(trigger)}">${esc(short(batch, 26))}<div class="sub-cell">${esc(trigger)}</div></td>
      <td>${esc(task.run_count || 0)} 次<div class="sub-cell">最近 #${esc(task.last_run_no || '-')}</div></td>
      <td>${esc(stage)}<div class="sub-cell">${esc(formatTaskDuration(task.duration_ms))}</div></td>
      <td title="${esc(formatDateTime(task.created_at))} → ${esc(formatDateTime(task.completed_at))}">${esc(formatDateTime(task.created_at))}<div class="sub-cell">${esc(formatDateTime(task.completed_at))}</div></td>
      <td class="task-error" title="${esc(error || result)}">${error ? `${taskErrorBadge(task.error_info)}<span class="task-error-cell-text">${esc(short(task.error_info?.summary || result, 90))}</span>` : esc(short(result, 90))}</td>
      <td><div class="task-row-actions"><button type="button" class="task-row-action" data-account-task-log="${esc(task.id)}">日志</button>${cancellable ? `<button type="button" class="task-row-action danger" data-account-task-cancel="${esc(task.id)}">停止</button>` : ''}${retryable ? `<button type="button" class="task-row-action task-row-action--retry" data-account-task-retry="${esc(task.id)}">重跑</button>` : ''}</div></td>
    </tr>`;
  }).join('') || renderTableStateRow(11, '暂无任务记录', '调整搜索或筛选条件后再试。');
  const summary = $('#accountTaskPageSummary');
  if (summary) summary.textContent = `${ACCOUNT_TASKS_TOTAL || 0} 个任务 · 当前页 ${ACCOUNT_TASKS.length} 条`;
  _renderPager('accountTasks', ACCOUNT_TASKS_TOTAL);
}
async function loadAccountTasks() {
  if (accountTasksLoading) return;
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
    const result = await api(`/api/operations?${params.toString()}`);
    updateAccountTaskFilters(result.facets || {});
    ACCOUNT_TASKS = result.items || [];
    ACCOUNT_TASKS_TOTAL = Number(result.total || 0);
    const totalPages = Math.max(1, Math.ceil(ACCOUNT_TASKS_TOTAL / p.size));
    if (p.page > totalPages) {
      p.page = totalPages;
      accountTasksLoading = false;
      return loadAccountTasks();
    }
    if ($('#accountTaskRefreshHint')) $('#accountTaskRefreshHint').textContent = `最近批次 ${Number((result.batches || []).length)} 个 · 共 ${ACCOUNT_TASKS_TOTAL} 个任务`;
    renderAccountTasks();
  } catch (e) {
    if (!ACCOUNT_TASKS.length) $('#accountTasksBody').innerHTML = renderTableStateRow(11, '任务记录加载失败', '请检查服务状态后刷新列表。', 'error');
    showToast('加载任务中心失败: ' + e.message);
  }
  finally {
    accountTasksLoading = false;
    setListBusy('accountTasksPanel', false);
  }
}
let activeAccountTaskId = null, activeAccountTaskRunId = null, accountTaskLogTimer = null;
let activeAccountTaskDetailView = 'events', accountTaskSnapshot = null, accountTaskPolling = false;
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

function renderAccountTaskEvents() {
  const content = $('#accountTaskLogContent');
  if (!content) return;
  content.innerHTML = accountTaskEventCache.map(event => {
    const eventType = String(event.event_type || 'note.info');
    const level = String(event.level || 'INFO').toUpperCase();
    const state = accountTaskEventStepState(event);
    const detail = meaningfulTaskDetail(event.detail);
    const css = level === 'ERROR' || state === 'failed' ? ' is-error' : level === 'WARNING' ? ' is-warning' : state === 'success' ? ' is-success' : '';
    return `<div class="account-task-event${css}" data-event-id="${attrEsc(event.id)}">
      <div class="account-task-event-head"><span>${esc(formatDateTime(event.created_at))}</span><span>${esc(level)}</span><span>${esc(ACCOUNT_TASK_STAGE_LABELS[normalizeAccountTaskStage(event.stage)] || event.stage || '事件')}</span><span class="account-task-event-type">${esc(eventType)}</span></div>
      <div class="account-task-event-message">${esc(event.message || '-')}</div>
      ${detail ? `<details class="account-task-event-detail"><summary>查看技术详情</summary><pre>${esc(JSON.stringify(detail, null, 2))}</pre></details>` : ''}
    </div>`;
  }).join('') || '<div class="account-task-empty">暂无事件</div>';
}

function renderAccountTaskRunLog() {
  const panel = $('#accountTaskRunLogContent');
  if (!panel) return;
  panel.textContent = accountTaskRunLogLines.map(item => {
    const fields = meaningfulTaskDetail(item.fields);
    return `${item.ts || ''} ${item.level || 'INFO'} ${item.stage || 'event'} ${item.message || ''}${fields ? `\n${JSON.stringify(fields, null, 2)}` : ''}`;
  }).join('\n') || '(当前 Run 暂无技术日志；旧任务可能只有事件时间线)';
}

function renderAccountTaskArtifacts(task) {
  const panel = $('#accountTaskArtifactContent');
  if (!panel) return;
  const resources = (task?.resources || []).filter(item => !activeAccountTaskRunId || String(item.run_id || '') === String(activeAccountTaskRunId));
  panel.innerHTML = resources.map(item => `<div class="account-task-artifact"><strong>${esc(item.resource_type || '运行资源')}</strong><div>${esc(item.provider || item.state || '-')}</div><small>${esc(formatDateTime(item.acquired_at || item.created_at))}</small></div>`).join('') || '<div class="account-task-empty">当前 Run 没有诊断资源或产物</div>';
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
  activeAccountTaskRunId = runId ? Number(runId) : null;
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
  const desired = Number(activeAccountTaskRunId || task?.last_run_id || runs[runs.length - 1]?.id || 0) || null;
  select.innerHTML = runs.map(run => `<option value="${attrEsc(run.id)}">第 ${esc(run.run_no || '-')} 次 · ${esc(run.status || '-')}</option>`).join('');
  if (desired && runs.some(run => Number(run.id) === desired)) select.value = String(desired);
  const selected = Number(select.value || desired || 0) || null;
  if (selected !== activeAccountTaskRunId) resetAccountTaskRunData(selected);
  select.disabled = runs.length <= 1;
}

async function pollAccountTaskEvents(reset = false) {
  if (!activeAccountTaskId || !activeAccountTaskRunId) return;
  const scroller = $('#accountTaskLogContent')?.parentElement;
  const atBottom = !scroller || scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 36;
  const params = new URLSearchParams({limit:'500'});
  if (!reset && accountTaskEventCursor != null) params.set('after_id', String(accountTaskEventCursor));
  const result = await api(`/api/operations/${encodeURIComponent(activeAccountTaskId)}/runs/${encodeURIComponent(activeAccountTaskRunId)}/events?${params}`);
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
  const taskId = Number(activeAccountTaskId);
  const runId = Number(activeAccountTaskRunId);
  const requestId = ++accountTaskProgressRequestId;
  try {
    const result = await api(`/api/operations/${encodeURIComponent(taskId)}/runs/${encodeURIComponent(activeAccountTaskRunId)}/progress`);
    if (requestId !== accountTaskProgressRequestId || taskId !== Number(activeAccountTaskId) || runId !== Number(activeAccountTaskRunId)) return;
    accountTaskProgressSnapshot = result.progress || null;
    accountTaskProgressError = '';
    renderAccountTaskProgressSnapshot(accountTaskProgressSnapshot);
  } catch (e) {
    if (requestId !== accountTaskProgressRequestId || taskId !== Number(activeAccountTaskId) || runId !== Number(activeAccountTaskRunId)) return;
    accountTaskProgressError = e.message || '进度更新失败';
    // Keep the last good snapshot. A first-load failure stays hidden rather
    // than falling back to the incomplete event page.
    if (accountTaskProgressSnapshot) renderAccountTaskProgressSnapshot(accountTaskProgressSnapshot);
  }
}

async function pollAccountTaskRunLog(reset = false) {
  if (!activeAccountTaskId || !activeAccountTaskRunId) return;
  const params = new URLSearchParams({limit:'500'});
  if (!reset && accountTaskRunLogCursor != null) params.set('cursor', String(accountTaskRunLogCursor));
  const result = await api(`/api/operations/${encodeURIComponent(activeAccountTaskId)}/runs/${encodeURIComponent(activeAccountTaskRunId)}/logs?${params}`);
  if (reset || accountTaskRunLogCursor == null) accountTaskRunLogLines = result.items || [];
  else accountTaskRunLogLines.push(...(result.items || []));
  accountTaskRunLogCursor = Number(result.next_cursor || 0);
  renderAccountTaskRunLog();
}

function openAccountTaskLog(taskId) {
  activeAccountTaskId = Number(taskId);
  accountTaskSnapshot = null;
  resetAccountTaskRunData(null);
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

async function pollAccountTaskLog() {
  if (!activeAccountTaskId || accountTaskPolling) return;
  accountTaskPolling = true;
  try {
    const result = await api(`/api/operations/${encodeURIComponent(activeAccountTaskId)}?include_events=0`);
    const task = result.task || {};
    accountTaskSnapshot = task;
    renderTaskLogErrorSummary('accountTaskLogErrorSummary', task);
    const previousRunId = activeAccountTaskRunId;
    syncAccountTaskRunPicker(task);
    const selectedRun = (task.runs || []).find(run => Number(run.id) === Number(activeAccountTaskRunId)) || {};
    $('#accountTaskDetailSummary').textContent = `${ACCOUNT_TASK_TYPE_LABELS[task.task_type] || task.task_type || '任务'} · ${selectedRun.status || task.status || '-'} · ${formatTaskDuration(selectedRun.duration_ms)}`;
    await pollAccountTaskProgress();
    if (previousRunId !== activeAccountTaskRunId || accountTaskEventCursor == null) {
      await pollAccountTaskEvents(true);
      if (activeAccountTaskDetailView === 'logs') await pollAccountTaskRunLog(true);
    } else {
      await pollAccountTaskEvents(false);
      if (activeAccountTaskDetailView === 'logs') await pollAccountTaskRunLog(false);
    }
    renderAccountTaskArtifacts(task);
    if (!['queued','running','cancelling','settling'].includes(String(task.status || ''))) {
      clearInterval(accountTaskLogTimer);
      loadAccountTasks();
      loadAccounts();
    }
  } catch (e) {
    $('#accountTaskLogContent').innerHTML = `<div class="account-task-empty">加载失败：${esc(e.message)}</div>`;
  } finally {
    accountTaskPolling = false;
  }
}

$('#accountTaskRunSelect')?.addEventListener('change', event => {
  resetAccountTaskRunData(Number(event.target.value || 0) || null);
  pollAccountTaskLog();
});
document.querySelectorAll('[data-account-task-detail-tab]').forEach(button => button.addEventListener('click', () => setAccountTaskDetailView(button.dataset.accountTaskDetailTab)));
$('#accountTaskNewEvents')?.addEventListener('click', () => {
  const scroller = $('#accountTaskLogContent')?.parentElement;
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
  accountTaskNewEventCount = 0;
  $('#accountTaskNewEvents').classList.add('hidden');
});
async function retryAccountTask(taskId, button) {
  button.disabled = true;
  try {
    await api(`/api/operations/${encodeURIComponent(taskId)}/retry`, {method:'POST'});
    showToast('任务已重新入队');
    loadAccountTasks();
  } catch (e) {
    showToast('重跑失败: ' + e.message);
    button.disabled = false;
  }
}
async function cancelAccountTask(taskId, button) {
  button.disabled = true;
  try {
    await api(`/api/operations/${encodeURIComponent(taskId)}/cancel`, {method:'POST'});
    showToast('已请求停止，任务将在安全检查点收口');
    loadAccountTasks();
  } catch (e) {
    showToast('停止失败: ' + e.message);
    button.disabled = false;
  }
}
function updateAccountTaskFilters(facets = {}) {
  syncFacetSelect('accountTaskTypeFilterV2', facets.task_type, {
    group: 'task_type',
    values: ['registration', 'registration_resume', 'account_setup_retry', 'password_setup', 'twofa_setup', 'account_completion', 'twofa_retry', 'codex_retry', 'codex_token_refresh', 'live_check', 'token_refresh', 'plan_check', 'deactivation_mail'],
  });
  syncFacetSelect('accountTaskStatusFilterV2', facets.status, {
    group: 'status',
    values: ['queued', 'running', 'success', 'partial_success', 'failed', 'deactivated', 'unsupported', 'attention_required', 'interrupted', 'stopped', 'cancelled'],
  });
  syncFacetSelect('accountTaskTargetStatusFilterV2', facets.target_status, {group: 'target_status'});
  syncFacetSelect('accountTaskRunCountFilterV2', facets.run_count, {group: 'run_count', values: ['0', '1', '2', '3', '4+']});
  syncFacetSelect('accountTaskStageFilterV2', facets.stage, {group: 'stage'});
}

let accountTaskFilterTimer = null;
function scheduleAccountTaskFilterReload(immediate = false) {
  PAGERS.accountTasks.page = 1;
  refreshColumnFilterStates();
  clearTimeout(accountTaskFilterTimer);
  if (immediate) {
    loadAccountTasks();
    return;
  }
  accountTaskFilterTimer = setTimeout(loadAccountTasks, 260);
}
$('#btnRefreshAccountTasks')?.addEventListener('click', loadAccountTasks);
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
  const logBtn = event.target.closest('[data-account-task-log]');
  if (logBtn) { openAccountTaskLog(Number(logBtn.dataset.accountTaskLog)); return; }
  const retryBtn = event.target.closest('[data-account-task-retry]');
  if (retryBtn) { retryAccountTask(Number(retryBtn.dataset.accountTaskRetry), retryBtn); return; }
  const cancelBtn = event.target.closest('[data-account-task-cancel]');
  if (cancelBtn) cancelAccountTask(Number(cancelBtn.dataset.accountTaskCancel), cancelBtn);
});
function getAccountsQuery() {
  const el = document.getElementById('qAccountsV2');
  return (el ? el.value : '').trim();
}
function getAccountOperationWorkers() {
  const configured = CONFIG.find(item => item.key === 'ACCOUNT_BATCH_WORKERS');
  return Math.max(1, Math.min(16, Number(configured?.value ?? ACCOUNT_BATCH_WORKERS) || 3));
}
function configuredLiveCheckDriver() {
  const configured = CONFIG.find(item => item.key === 'ACCOUNT_LIVE_CHECK_DRIVER');
  const value = String(configured?.value ?? '').trim().toLowerCase();
  return value || null;
}
async function loadRuntimeUiSettings() {
  try {
    const items = await api('/api/config');
    if (Array.isArray(items)) {
      CONFIG = items;
      const field = items.find(item => item.key === 'ACCOUNT_BATCH_WORKERS');
      ACCOUNT_BATCH_WORKERS = Math.max(1, Math.min(16, Number(field?.value) || 3));
    }
  } catch(e) {}
}
async function loadAccounts() {
  if (accountsLoading) {
    accountsReloadQueued = true;
    return;
  }
  accountsLoading = true;
  accountsReloadQueued = false;
  setListBusy('accountsPanelV2', true);
  try {
    const archived = SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0';
    const plan = document.getElementById('accountPlanFilterV2')?.value || (SHOW_PLUS_ACCOUNTS_ONLY ? 'plus' : '');
    const q = getAccountsQuery();
    const dateFrom = document.getElementById('dateFromAccountsV2')?.value || '';
    const dateTo = document.getElementById('dateToAccountsV2')?.value || '';
    const p = PAGERS.accounts;
    const params = new URLSearchParams({paged:'1', page:String(p.page), page_size:String(p.size), archived, plan, email:q, date_from:dateFrom, date_to:dateTo});
    const accountFilters = {
      id: 'accountIdFilterV2', source: 'accountSourceFilterV2', token: 'accountTokenFilterV2',
      password: 'accountPasswordFilterV2', trial: 'accountTrialFilterV2', totp: 'accountTotpFilterV2', risk: 'accountRiskFilterV2', codex: 'accountCodexFilterV2', account_status: 'accountStatusFilterV2',
    };
    Object.entries(accountFilters).forEach(([key, id]) => params.set(key, document.getElementById(id)?.value || ''));
    const res = await api(`/api/accounts?${params.toString()}`);
    const facets = res.facets || {};
    syncFacetSelect('accountSourceFilterV2', facets.source, {group:'source'});
    syncFacetSelect('accountTokenFilterV2', facets.token, {
      group:'account_token',
      values:['has','expired','invalid_401','invalid_403','invalid_other','none'],
    });
    syncFacetSelect('accountPasswordFilterV2', facets.password, {group:'password'});
    syncFacetSelect('accountPlanFilterV2', facets.plan, {group:'plan'});
    syncFacetSelect('accountTrialFilterV2', facets.trial, {group:'trial'});
    syncFacetSelect('accountTotpFilterV2', facets.totp, {group:'totp'});
    syncFacetSelect('accountRiskFilterV2', facets.risk, {group:'risk'});
    syncFacetSelect('accountCodexFilterV2', facets.codex, {group:'codex'});
    syncFacetSelect('accountStatusFilterV2', facets.account_status, {group:'account_status', values:['active','deactivated']});
    ACCOUNTS = res.items || [];
    ACCOUNTS_TOTAL = Number(res.total || ACCOUNTS.length || 0);
    const totalPages = Math.max(1, Math.ceil(ACCOUNTS_TOTAL / p.size));
    if (p.page > totalPages) {
      p.page = totalPages;
      accountsReloadQueued = true;
      return;
    }
    renderAccounts();
  } catch(e) {
    if (!ACCOUNTS.length) $('#accountsBodyV2').innerHTML = renderTableStateRow(14, '账号加载失败', '请检查服务状态后刷新列表。', 'error');
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
async function pollAccountPlanStatuses() {
  if (planStatusLoading || accountsLoading) return;
  planStatusLoading = true;
  try {
    const archived = SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0';
    const plan = SHOW_PLUS_ACCOUNTS_ONLY ? 'plus' : '';
    const q = getAccountsQuery();
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
  if ((r.account_status || '').toLowerCase() === 'deactivated') return '<span class="acc-v2-codex is-fail" title="账号已确认停用/封禁">封号</span>';
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
  const status = String(r.account_status || 'active').toLowerCase();
  const reason = String(r.account_status_reason || '').trim();
  if (status === 'deactivated') {
    return `<span class="acc-v2-account-status is-fail"${reason ? ` title="${esc(reason)}"` : ''}>已废号</span>`;
  }
  const liveStatus = String(r.live_check_status || '').toLowerCase();
  const liveHttp = _liveCheckHttpStatus(r);
  const liveReason = String(r.live_check_error || '').trim();
  if (liveStatus === 'failed') {
    const tokenIssue = liveHttp === 401 || liveHttp === 403;
    const label = tokenIssue ? `Token 异常 · HTTP ${liveHttp}` : '查活失败';
    const detail = [liveHttp ? `HTTP ${liveHttp}` : '', liveReason].filter(Boolean).join('；');
    return `<span class="acc-v2-account-status is-fail"${detail ? ` title="${esc(detail)}"` : ''}>${label}</span>`;
  }
  if (liveStatus === 'queued' || liveStatus === 'running') {
    return '<span class="acc-v2-account-status is-mute">查活中</span>';
  }
  if (liveStatus === 'live') return '<span class="acc-v2-account-status is-ok">正常</span>';
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

  const cls = lower === '-' ? 'status-used' : 'status-success';
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
  if (plan && plan !== 'free') return '<span class="acc-v2-muted">-</span>';
  if (!plan) return '<span class="pill status-running">待查询</span>';
  if (status === 'queued' || status === 'running') {
    const stamp = status === 'queued' ? r.plan_check_queued_at : r.plan_check_started_at;
    return `<span class="pill status-running" title="${esc(stamp || '套餐查询正在执行')}">待查询</span>`;
  }
  if (status === 'failed') {
    if (r.plan_last_success_at) {
      const label = r.plus_trial_eligible ? '可用' : '不可用';
      return `<span class="pill ${r.plus_trial_eligible ? 'status-success' : 'status-used'}" title="上次成功查询: ${esc(r.plan_last_success_at)}；本次查询失败: ${esc(err || '未知错误')}">${label}</span>`;
    }
    return `<span class="pill status-failed" title="${esc(err || '套餐查询失败')}">查询失败</span>`;
  }
  if (status !== 'success' && r.plan_check_ok !== true) {
    return '<span class="pill status-running">待查询</span>';
  }
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
  return `<button type="button" class="acc-v2-token-state is-${attrEsc(state.key)}" data-account-copy-secret="access_token" data-account-id="${esc(r.id)}" title="${esc(state.title)}">${esc(state.label)}</button>`;
}
function _passwordCellV2(r) {
  if (!r.has_account_password) return '<span class="acc-v2-muted">未设置</span>';
  return `<button type="button" class="acc-v2-token-copy" data-account-copy-secret="account_password" data-account-id="${esc(r.id)}" title="复制该账号密码">复制</button>`;
}
function _totpCellV2(r) {
  if (!r.totp_enabled) return '<span class="acc-v2-muted">未启用</span>';
  return `
    <div class="status-action-cell" data-account-totp-cell="${esc(r.id)}">
      <span class="pill status-success">已启用</span>
      <button type="button" data-account-totp-copy="${esc(r.id)}" title="获取并复制当前 6 位 TOTP 验证码">复制</button>
    </div>
  `;
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
  let badge = '<span class="pill status-used">待扫描</span>';
  let title = '尚未扫描';
  if (!supported || status === 'unsupported') {
    badge = '<span class="pill status-used">不支持</span>';
    title = err || '当前邮箱来源暂不支持扫描';
  } else if (detected) {
    badge = '<span class="pill status-failed">已收到</span>';
    title = [received && `收件: ${received}`, sender && `发件人: ${sender}`, subject].filter(Boolean).join('；');
  } else if (status === 'queued' || status === 'running') {
    badge = `<span class="pill status-running">${status === 'queued' ? '排队中' : '扫描中'}</span>`;
    title = '正在扫描邮箱，不会刷新 AT';
  } else if (status === 'success') {
    badge = '<span class="pill status-success">未发现</span>';
    title = checked ? `扫描时间: ${checked}` : '未发现高置信度封号通知';
  } else if (status === 'failed') {
    badge = '<span class="pill status-running">扫描失败</span>';
    title = err || checked || '扫描失败';
  }
  const button = supported && !['queued','running'].includes(status)
    ? `<button type="button" data-deactivation-mail-check="${esc(r.id)}" title="扫描该账号对应邮箱；不会刷新 AT">复查</button>`
    : '';
  return `<div class="status-action-cell" title="${esc(title)}">${badge}${button}</div>`;
}
function _accountsV2MoreMenu(r) {
  const parts = [
    `<button type="button" data-account-copy-secret="copy_line" data-account-id="${esc(r.id)}">复制整行</button>`,
    r.has_account_password ? `<button type="button" data-account-copy-secret="account_password" data-account-id="${esc(r.id)}">复制账号密码</button>` : '',
    (r.account_status || '').toLowerCase() === 'deactivated' ? '' : `<button type="button" data-account-action="password" data-account-id="${esc(r.id)}">补密码</button>`,
    (r.account_status || '').toLowerCase() === 'deactivated' ? '' : `<button type="button" data-account-action="twofa" data-account-id="${esc(r.id)}">补 2FA</button>`,
    (r.account_status || '').toLowerCase() === 'deactivated' ? '' : `<button type="button" data-account-action="complete" data-account-id="${esc(r.id)}">补全账号</button>`,
    (r.account_status || '').toLowerCase() === 'deactivated' ? '' : `<button type="button" onclick="checkSelectedLive([Number('${esc(r.id)}')], this); return false;" title="只在线验证现有 Token；不会发送邮箱验证码或刷新 AT">查活</button>`,
    (r.account_status || '').toLowerCase() === 'deactivated' ? '' : `<button type="button" onclick="refreshSelectedToken([Number('${esc(r.id)}')], this); return false;" title="通过邮箱 OTP 重新登录并刷新最新 AT">刷新AT</button>`,
    `<button type="button" data-account-task-history="${esc(r.email)}" title="在任务实例中查看该账号的 Codex 补跑、查活、AT 刷新、套餐和封号邮件历史">任务记录</button>`,
    _planAction(r),
    _extractLinkAction(r),
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
function _accountDetailMarkup(r) {
  const liveHttpStatus = _liveCheckHttpStatus(r);
  const liveHttpLabel = liveHttpStatus ? ` (HTTP ${liveHttpStatus})` : '';
  const tokenDisplay = _tokenDisplayState(r);
  const tokenStateLabels = {missing: '无 Token', normal: 'Token 正常', expired: 'Token 已过期', invalid: `Token 已失效${liveHttpLabel}`};
  const tokenState = tokenStateLabels[tokenDisplay.key] || tokenDisplay.label;
  const tokenTone = tokenDisplay.key === 'normal' ? 'success' : 'danger';
  const liveState = r.live_check_status === 'live' ? '查活正常' : (r.live_check_status === 'failed' ? `查活失败${liveHttpLabel}` : (r.live_check_status === 'running' ? '查活中' : '未查活'));
  const liveTone = r.live_check_status === 'live' ? 'success' : (r.live_check_status === 'failed' ? 'danger' : (r.live_check_status === 'running' ? 'warning' : 'neutral'));
  const plan = (r.current_plan_type || r.plan_type || '未查询').toString();
  const trial = plan.toLowerCase() === 'free' ? (r.plus_trial_eligible ? 'Plus 试用可用' : 'Plus 试用不可用') : '不适用';
  const trialTone = trial === 'Plus 试用可用' ? 'success' : (trial === 'Plus 试用不可用' ? 'neutral' : 'neutral');
  const codexRaw = (r.codex_status || r.codex_execution_status || '').toString().toLowerCase();
  const codexLabels = { success: '已通过', completed: '已通过', failed: '失败', deactivated: '已废号', running: '补跑中', queued: '排队中', cancelling: '停止中', retrying: '补跑中', stopped: '已停止', pending_confirmation: '待确认', skipped: '已跳过' };
  const codex = codexLabels[codexRaw] || '未授权';
  const codexTone = ['success', 'completed'].includes(codexRaw) ? 'success' : (['failed', 'deactivated'].includes(codexRaw) ? 'danger' : (['running', 'queued', 'cancelling', 'retrying'].includes(codexRaw) ? 'warning' : 'neutral'));
  const risk = r.deactivation_mail_detected ? '发现封号邮件' : (r.deactivation_mail_scan_status === 'success' ? '未发现封号邮件' : '待扫描');
  const riskTone = r.deactivation_mail_detected ? 'danger' : (r.deactivation_mail_scan_status === 'success' ? 'success' : 'neutral');
  return `<div class="account-detail-section">
    <div class="account-detail-section-title">身份信息</div>
    <div class="account-detail-grid">
      ${_accountDetailState('账号 ID', `#${r.id}`, 'info')}
      ${_accountDetailState('邮箱来源', r.email_source || '未知')}
      ${_accountDetailState('姓名', r.user_name || '未设置')}
      ${_accountDetailState('创建时间', _fmtPlanTime(r.created_at) || '-')}
    </div>
  </div>
  <div class="account-detail-section">
    <div class="account-detail-section-title">健康与安全</div>
    <div class="account-detail-grid">
      ${_accountDetailState('访问 Token', tokenState, tokenTone, r.token_expires_at ? `${tokenDisplay.key === 'invalid' ? 'JWT 标称到期' : '到期'} ${_fmtPlanTime(r.token_expires_at)}` : '')}
      ${_accountDetailState('在线状态', liveState, liveTone, r.live_checked_at ? `检查于 ${_fmtPlanTime(r.live_checked_at)}` : '')}
      ${_accountDetailState('账号密码', r.has_account_password ? '已设置' : '未设置', r.has_account_password ? 'success' : 'neutral')}
      ${_accountDetailState('Authenticator 2FA', r.totp_enabled ? '已启用' : '未启用', r.totp_enabled ? 'success' : 'neutral')}
      ${_accountDetailState('封号邮件', risk, riskTone)}
      ${_accountDetailState('归档状态', r.archived ? '已归档' : '活跃', r.archived ? 'neutral' : 'success')}
    </div>
  </div>
  <div class="account-detail-section">
    <div class="account-detail-section-title">套餐与授权</div>
    <div class="account-detail-grid">
      ${_accountDetailState('当前套餐', plan, plan.toLowerCase() === 'free' ? 'info' : 'success', r.plan_checked_at ? `检查于 ${_fmtPlanTime(r.plan_checked_at)}` : '')}
      ${_accountDetailState('Plus 试用', trial, trialTone)}
      ${_accountDetailState('Codex', codex, codexTone)}
      ${_accountDetailState('注册时间', _fmtPlanTime(r.created_at, true) || '-', 'neutral')}
    </div>
  </div>`;
}
function openAccountDetail(id) {
  const account = ACCOUNTS.find(item => Number(item.id) === Number(id));
  if (!account) { showToast('账号详情暂不可用，请先刷新列表'); return; }
  $('#accountDetailTitle').textContent = account.email || `账号 #${account.id}`;
  $('#accountDetailSubtitle').textContent = `账号 #${account.id} · ${account.email_source || '未知来源'}`;
  $('#accountDetailBody').innerHTML = _accountDetailMarkup(account);
  $('#accountDetailDrawer').classList.remove('hidden');
  $('#accountDetailBackdrop').classList.remove('hidden');
  $('#accountDetailBackdrop').setAttribute('aria-hidden', 'false');
  updateModalScrollLock();
  $('#btnCloseAccountDetail')?.focus({preventScroll:true});
}
function closeAccountDetail() {
  $('#accountDetailDrawer')?.classList.add('hidden');
  $('#accountDetailBackdrop')?.classList.add('hidden');
  $('#accountDetailBackdrop')?.setAttribute('aria-hidden', 'true');
  updateModalScrollLock();
}
$('#btnCloseAccountDetail')?.addEventListener('click', closeAccountDetail);
$('#accountDetailBackdrop')?.addEventListener('click', closeAccountDetail);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !$('#accountDetailDrawer')?.classList.contains('hidden')) {
    closeAccountDetail();
  }
});
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
function renderAccounts() {
  const openMoreId = getOpenAccountsV2MoreId();
  const total = ACCOUNTS_TOTAL;
  const rows = ACCOUNTS;
  const rowHtmlV2 = (r) => `
    <tr>
      <td class="col-check"><input type="checkbox" class="account-row-check" data-account-id="${esc(r.id)}" ${ACCOUNT_SELECTED.has(Number(r.id)) ? 'checked' : ''}></td>
      <td class="col-id">#${esc(r.id)}</td>
      <td class="col-email" title="${esc([r.email || '-', r.user_name || ''].filter(Boolean).join(' · '))}">
        <button type="button" class="acc-v2-email-link" data-account-detail-id="${esc(r.id)}" title="查看账号详情">
          <span class="acc-v2-email">${esc(r.email)}${r.archived ? ' <span class="pill status-used" title="该账号已归档">归档</span>' : ''}</span>
        </button>
        <div class="acc-v2-sub">${esc(r.user_name || '-')}</div>
      </td>
      <td class="col-source">${esc(r.email_source || '-')}</td>
      <td class="col-token">${_tokenCellV2(r)}</td>
      <td class="col-account-status">${_accountStatusCellV2(r)}</td>
      <td class="col-small">${_passwordCellV2(r)}</td>
      <td class="col-plan">${_planCell(r)}<div class="acc-v2-sub">${_extractLinkCell(r)}</div></td>
      <td class="col-trial">${_trialCell(r)}</td>
      <td class="col-small">${_totpCellV2(r)}</td>
      <td class="col-risk-mail">${_deactivationMailCell(r)}</td>
      <td class="col-status">${_codexCellV2(r)}</td>
      <td class="col-time" title="${esc(r.created_at || '-')}">${esc(r.created_at || '-')}</td>
      <td class="col-actions">
        <div class="acc-v2-actions">
          <button type="button" class="danger" data-account-delete="${esc(r.id)}" data-email="${esc(r.email)}">删除</button>
          <div class="acc-v2-more" data-account-more-id="${esc(r.id)}">
            <button type="button" class="acc-v2-more-btn" data-acc-more-toggle aria-haspopup="true" aria-expanded="false">更多</button>
            <div class="acc-v2-more-menu" role="menu">${_accountsV2MoreMenu(r)}</div>
          </div>
        </div>
      </td>
    </tr>`;

  const bodyV2 = $('#accountsBodyV2');
  if (bodyV2) {
    bodyV2.innerHTML = rows.map(rowHtmlV2).join('') || renderTableStateRow(14, '暂无匹配账号', '调整筛选条件，或切换活跃与归档账号视图。');
    if (openMoreId) requestAnimationFrame(() => restoreAccountsV2MoreMenu(openMoreId));
  }
  const summary = $('#accountsPageSummary');
  if (summary) summary.textContent = `${total || 0} 个账号 · 当前页 ${rows.length} 条`;
  updateAccountSelectionUi(rows);
  _renderPager('accounts', total);
}

function updateAccountSelectionUi(pageRows = null) {
  const none = ACCOUNT_SELECTED.size === 0;
  const hintV2 = $('#accountsSelectedHintV2');
  const toolbarV2 = $('#accountsToolbarV2');
  toolbarV2?.classList.toggle('has-selection', !none);
  if (hintV2) hintV2.textContent = none ? '选择账号后批量操作' : `已选 ${ACCOUNT_SELECTED.size} 个账号`;

  const archiveLabel = SHOW_ARCHIVED_ACCOUNTS ? '恢复选中' : '归档选中';
  const archiveTitle = SHOW_ARCHIVED_ACCOUNTS ? '把选中的归档账号恢复到默认账号列表' : '归档选中的账号；默认账号列表将不再查询/显示这些账号';
  const v2Ids = [
    'btnCheckSelectedLiveV2', 'btnRefreshSelectedTokenV2', 'btnCheckSelectedPlansV2', 'btnCheckSelectedDeactivationMailV2', 'btnExtractSelectedLinksV2',
    'btnSetupSelectedAccountsV2', 'btnAddPasswordSelectedAccountsV2', 'btnAddTwofaSelectedAccountsV2', 'btnCompleteSelectedAccountsV2', 'btnUploadSelectedCodexSub2V2', 'btnRetrySelectedCodexV2', 'btnDownloadSelectedCpaV2', 'btnStopSelectedCodexV2',
    'btnCopySelectedTokensV2', 'btnCopySelectedLinesV2', 'btnCopySelectedEmailsV2',
    'btnCopySelectedPasswordsV2',
    'btnDownloadSelectedTxtV2', 'btnArchiveSelectedAccountsV2', 'btnDeleteSelectedAccountsV2',
  ];
  v2Ids.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.disabled = none;
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
      showToast(field === 'access_token' ? 'Token 已复制' : (field === 'account_password' ? '账号密码已复制' : (field === 'totp_secret' ? 'TOTP 密钥已复制' : '账号整行已复制')));
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
    const labels = {password: '补密码', twofa: '补 2FA', complete: '补全账号'};
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
        : ({password: 'password_setup', twofa: 'twofa_setup', complete: 'account_completion'})[action];
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
  if (cb.checked) ACCOUNT_SELECTED.add(id);
  else ACCOUNT_SELECTED.delete(id);
  updateAccountSelectionUi();
}
function syncAccountsSelectAll(checked) {
  const pageRows = ACCOUNTS;
  if (checked) pageRows.forEach(r => ACCOUNT_SELECTED.add(Number(r.id)));
  else pageRows.forEach(r => ACCOUNT_SELECTED.delete(Number(r.id)));
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
  const reload = debounce(() => {
    ACCOUNT_SELECTED.clear();
    PAGERS.accounts.page = 1;
    loadAccounts();
  }, 250);
  ['accountIdFilterV2','qAccountsV2'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', reload);
  });
  ['accountSourceFilterV2','accountTokenFilterV2','accountStatusFilterV2','accountPasswordFilterV2','accountPlanFilterV2','accountTrialFilterV2','accountTotpFilterV2','accountRiskFilterV2','accountCodexFilterV2','dateFromAccountsV2','dateToAccountsV2'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', reload);
  });

  const archivedV2 = $('#showArchivedAccountsV2');
  if (archivedV2) archivedV2.addEventListener('click', () => {
    applyAccountsArchivedFilter(!SHOW_ARCHIVED_ACCOUNTS);
  });
  const refreshV2 = $('#btnRefreshAccountsV2');
  if (refreshV2) refreshV2.addEventListener('click', () => refreshAccountsList(refreshV2));
  $('#btnResetAccountFiltersV2')?.addEventListener('click', () => {
    ['accountIdFilterV2','qAccountsV2','accountSourceFilterV2','accountTokenFilterV2','accountStatusFilterV2','accountPasswordFilterV2','accountPlanFilterV2','accountTrialFilterV2','accountTotpFilterV2','accountRiskFilterV2','accountCodexFilterV2','dateFromAccountsV2','dateToAccountsV2'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    ACCOUNT_SELECTED.clear(); PAGERS.accounts.page = 1; refreshColumnFilterStates(); loadAccounts();
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
  const btn = $('#btnExtractSelectedLinksV2');
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
  const btn = $('#btnCheckSelectedPlansV2');
  if (!btn) return;
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

async function checkSelectedLive(idsArg = null, btnArg = null) {
  const ids = idsArg || Array.from(ACCOUNT_SELECTED);
  if (ids.length === 0) { showToast('请先选择账号'); return; }
  const workers = getAccountOperationWorkers();
  const msg = idsArg ? `确定查活这个账号吗？

只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。` : `确定查活选中的 ${ids.length} 个账号吗？

只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。

并发线程数：${workers}`;
  if (!confirm(msg)) return;
  const firstAcc = ACCOUNTS.find(a => Number(a.id) === Number(ids[0]));
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
  const btn = btnArg || $('#btnRefreshSelectedTokenV2');
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
  const deactivatedCount = selectedAccounts.filter(a => (a.codex_status || '') === 'deactivated').length;
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

async function runSelectedAccountAction(action, label, taskType) {
  const ids = Array.from(ACCOUNT_SELECTED).map(Number);
  if (!ids.length) { showToast('请先选择账号'); return; }
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
  bind('btnCheckSelectedDeactivationMailV2', checkSelectedDeactivationMail);
  bind('btnRefreshSelectedTokenV2', () => refreshSelectedToken());
  bind('btnExtractSelectedLinksV2', extractSelectedLinks);
  bind('btnSetupSelectedAccountsV2', setupSelectedAccounts);
  bind('btnAddPasswordSelectedAccountsV2', addPasswordSelectedAccounts);
  bind('btnAddTwofaSelectedAccountsV2', addTwofaSelectedAccounts);
  bind('btnCompleteSelectedAccountsV2', completeSelectedAccounts);
  bind('btnUploadSelectedCodexSub2V2', uploadSelectedCodexSub2);
  bind('btnRetrySelectedCodexV2', retrySelectedCodex);
  bind('btnDownloadSelectedCpaV2', downloadSelectedCpa);
  bind('btnStopSelectedCodexV2', stopSelectedCodex);
  bind('btnCopySelectedTokensV2', copySelectedAccountTokens);
  bind('btnCopySelectedLinesV2', copySelectedAccountLines);
  bind('btnCopySelectedEmailsV2', copySelectedAccountEmails);
  bind('btnCopySelectedPasswordsV2', copySelectedAccountPasswords);
  bind('btnDownloadSelectedTxtV2', downloadSelectedAccountTxt);
  bind('btnArchiveSelectedAccountsV2', archiveSelectedAccounts);
  bind('btnDeleteSelectedAccountsV2', deleteSelectedAccounts);
})();
