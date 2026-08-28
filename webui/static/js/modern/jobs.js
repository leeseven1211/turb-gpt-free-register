// ---------- 注册 / 任务 ----------
function registrationEmailSourceLabel(value) {
  const source = REGISTRATION_EMAIL_SOURCES.find(item => item.value === String(value || ''));
  return source?.label || String(value || '-');
}
async function loadRegistrationEmailSources() {
  const select = $('#regEmailSourceV2');
  if (!select) return;
  try {
    const [result, capabilities] = await Promise.all([api('/api/email-sources'), api('/api/capabilities')]);
    CAPABILITIES = capabilities;
    const sourceCaps = capabilities.email_sources || {};
    REGISTRATION_EMAIL_SOURCES = (Array.isArray(result.sources) ? result.sources : []).map(item => ({
      ...item,
      ...(sourceCaps[item.value] || {}),
    }));
    applyFeatureGates();
    if (result.manual_mode) {
      select.innerHTML = '<option value="manual">手动配置邮箱</option>';
      select.disabled = true;
      return;
    }
    select.disabled = false;
    select.innerHTML = '<option value="">请选择本次邮箱来源</option>' + REGISTRATION_EMAIL_SOURCES.map(item =>
      `<option value="${esc(item.value)}" ${item.enabled === false ? 'disabled' : ''} title="${esc(item.reason || '')}">${esc(item.label)}${item.enabled === false ? '（未配置）' : ''}</option>`
    ).join('');
  } catch (error) {
    select.innerHTML = '<option value="">邮箱来源加载失败</option>';
    select.disabled = true;
  }
}
async function startRegistrationFromInputs(countEl, workersEl, sourceEl, startBtn) {
  const count = parseInt((countEl?.value || '1'), 10);
  const workers = parseInt((workersEl?.value || '3'), 10);
  const emailSource = String(sourceEl?.value || '').trim();
  const debugEnabled = Boolean($('#regDebugV2')?.checked);
  if (!emailSource) {
    const warnEl = $('#regWarnV2');
    if (warnEl) warnEl.innerHTML = '<div class="banner warn">请选择本次注册使用的邮箱来源</div>';
    sourceEl?.focus();
    return;
  }
  const activeCount = Number(JOB_STATUS_COUNTS.active || 0);
  if (activeCount > 0) {
    const ok = confirm(
      `当前任务表里已有 ${activeCount} 个任务在跑或排队，` +
      `这次会再加 ${count} 个，合计 ${activeCount + count} 个，确定继续？\n\n` +
      `（如果只是想跑这 ${count} 个，建议先点"取消所有排队"清掉残留再提交）`
    );
    if (!ok) return;
  }
  if (startBtn) startBtn.disabled = true;
  const restoreBtn = () => {
    if (startBtn) startBtn.disabled = false;
    const b2 = $('#btnStartV2'); if (b2) b2.disabled = false;
  };
  const b2 = $('#btnStartV2'); if (b2) b2.disabled = true;
  try {
    const r = await api('/api/jobs', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({count, workers, email_source:emailSource, debug_enabled:debugEnabled}) });
    setJobProgressBatch(r.jobs?.[0]?.batch_id || '');
    const sourceLabel = registrationEmailSourceLabel(r.email_source || emailSource);
    const debugLabel = debugEnabled ? ' · 网络调试已开启' : '';
    const warnHtml = r.warning ? `<div class="banner warn">${esc(r.warning)}（邮箱 ${esc(sourceLabel)} · 并发 ${r.workers || workers}${debugLabel}）</div>` : `<div class="banner info">已提交 ${r.submitted} 个任务 · 邮箱 ${esc(sourceLabel)} · 并发 ${r.workers || workers}${debugLabel}</div>`;
    const warnEl = $('#regWarnV2'); if (warnEl) warnEl.innerHTML = warnHtml;
    const c2 = $('#regCountV2'); if (c2) c2.value = count;
    const w2 = $('#regWorkersV2'); if (w2) w2.value = workers;
    refreshJobs();
  } catch(e) {
    const warnEl = $('#regWarnV2'); if (warnEl) warnEl.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`;
  }
  finally { setTimeout(restoreBtn, 3000); }
}
async function cancelAllPendingJobs(btn) {
  const pendingCount = Number(JOB_STATUS_COUNTS.pending || 0);
  const msg = pendingCount > 0
    ? `确定取消 ${pendingCount} 个排队中的任务吗？已运行中的任务不受影响。`
    : '当前页没有排队任务；仍要请求后端取消所有排队任务吗？';
  if (!confirm(msg)) return;
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/jobs/cancel-pending', { method:'POST', headers:{'Content-Type':'application/json'}, body: '{}' });
    showToast(`已取消 ${r.cancelled} 个排队任务`);
    refreshJobs();
  } catch(e) { showToast('取消失败: ' + e.message); }
  finally {
    if (btn) btn.disabled = false;
    const b2 = $('#btnCancelPendingV2'); if (b2) b2.disabled = false;
  }
}

function currentBatchJobs() {
  return Array.isArray(JOB_PROGRESS_BATCH?.items) ? JOB_PROGRESS_BATCH.items : [];
}

async function batchStopJobs() {
  const batchId = String(JOB_PROGRESS_BATCH?.batch_id || '').trim();
  const ids = currentBatchJobs().filter(job => ['running', 'stopping'].includes(String(job.status || '')));
  if (!batchId || !ids.length) { showToast('当前批次没有正在运行的任务'); return; }
  if (!confirm('确定停止当前批次的 ' + ids.length + ' 个运行中任务吗？任务会在当前步骤检查点退出。')) return;
  const btn = $('#btnBatchStopV2');
  if (btn) btn.disabled = true;
  try {
    const result = await api('/api/jobs/batches/' + encodeURIComponent(batchId) + '/stop', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'
    });
    showToast(result.message || '已请求停止当前批次');
    await refreshJobs();
  } catch (e) { showToast('批次停止失败: ' + e.message); }
  finally { if (btn) btn.disabled = false; }
}

async function batchCancelJobs() {
  const batchId = String(JOB_PROGRESS_BATCH?.batch_id || '').trim();
  const ids = currentBatchJobs().filter(job => String(job.status || '') === 'pending');
  if (!batchId || !ids.length) { showToast('当前批次没有排队任务'); return; }
  if (!confirm('确定取消当前批次的 ' + ids.length + ' 个排队任务吗？运行中的任务不受影响。')) return;
  const btn = $('#btnBatchCancelV2');
  if (btn) btn.disabled = true;
  try {
    const result = await api('/api/jobs/batches/' + encodeURIComponent(batchId) + '/cancel', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'
    });
    showToast('已取消 ' + Number(result.cancelled || 0) + ' 个排队任务');
    await refreshJobs();
  } catch (e) { showToast('批次取消失败: ' + e.message); }
  finally { if (btn) btn.disabled = false; }
}

async function retryBatchFailedJobs() {
  const ids = currentBatchJobs().filter(job => ['failed', 'partial_success', 'stopped', 'cancelled'].includes(String(job.status || '')) && job.retryable).map(job => Number(job.id));
  if (!ids.length) { showToast('当前批次没有可重跑的失败任务'); return; }
  if (!confirm('确定重跑当前批次的 ' + ids.length + ' 个失败任务吗？已创建账号的任务会只补跑 Codex。')) return;
  const btn = $('#btnBatchRetryV2');
  if (btn) btn.disabled = true;
  try {
    const result = await api('/api/jobs/retry-bulk', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({job_ids: ids})});
    if (result.batch_id) setJobProgressBatch(result.batch_id);
    showToast('已提交 ' + (result.started_count || 0) + ' 个失败任务' + (result.skipped?.length ? '，跳过 ' + result.skipped.length + ' 个' : ''));
    refreshJobs();
  } catch (e) { showToast('批次重跑失败: ' + e.message); }
}
function syncJobsSelectAll(checked) {
  const pageRows = JOBS.filter(j => !['running','stopping'].includes(j.status));
  if (checked) pageRows.forEach(j => JOB_SELECTED.add(Number(j.id)));
  else pageRows.forEach(j => JOB_SELECTED.delete(Number(j.id)));
  renderJobs();
}
function bindJobsBodyEvents(bodyEl) {
  if (!bodyEl || bodyEl.dataset.bound === '1') return;
  bodyEl.dataset.bound = '1';
  bodyEl.addEventListener('pointerdown', (e) => {
    const retryBtn = e.target.closest('[data-retry-job]');
    if (!retryBtn || retryBtn.disabled || e.button !== 0) return;
    e.preventDefault();
    retryBtn.dataset.pointerHandled = '1';
    retryJob(parseInt(retryBtn.dataset.retryJob, 10), retryBtn);
  });
  bodyEl.addEventListener('click', (e) => {
    const logBtn = e.target.closest('[data-log-job]');
    if (logBtn) {
      openLog(parseInt(logBtn.dataset.logJob, 10));
      return;
    }
    const stopBtn = e.target.closest('[data-stop-job]');
    if (stopBtn) { stopJob(parseInt(stopBtn.dataset.stopJob, 10), stopBtn); return; }
    const otpBtn = e.target.closest('[data-submit-otp-job]');
    if (otpBtn) { submitManualOtpForJob(otpBtn); return; }
    const retryBtn = e.target.closest('[data-retry-job]');
    if (retryBtn) {
      if (retryBtn.dataset.pointerHandled === '1') {
        delete retryBtn.dataset.pointerHandled;
        return;
      }
      retryJob(parseInt(retryBtn.dataset.retryJob, 10), retryBtn);
      return;
    }
    const delBtn = e.target.closest('[data-delete-job]');
    if (delBtn) deleteJob(parseInt(delBtn.dataset.deleteJob, 10), delBtn);
  });
  bodyEl.addEventListener('change', (e) => {
    const cb = e.target.closest('.job-row-check');
    if (!cb) return;
    const id = Number(cb.dataset.jobId);
    if (cb.checked) JOB_SELECTED.add(id);
    else JOB_SELECTED.delete(id);
    updateJobsSelectionUi();
  });
}

// 注册任务区
(() => {
  const startV2 = $('#btnStartV2');
  loadRegistrationEmailSources();
  if (startV2) startV2.addEventListener('click', () => startRegistrationFromInputs($('#regCountV2'), $('#regWorkersV2'), $('#regEmailSourceV2'), startV2));
  const delV2 = $('#btnDeleteSelectedJobsV2');
  if (delV2) delV2.addEventListener('click', deleteSelectedJobs);
  const retryV2 = $('#btnRetrySelectedJobsV2');
  if (retryV2) retryV2.addEventListener('click', retrySelectedJobs);
  const cancelV2 = $('#btnCancelPendingV2');
  if (cancelV2) cancelV2.addEventListener('click', () => cancelAllPendingJobs(cancelV2));
  $('#btnBatchStopV2')?.addEventListener('click', batchStopJobs);
  $('#btnBatchCancelV2')?.addEventListener('click', batchCancelJobs);
  $('#btnBatchRetryV2')?.addEventListener('click', retryBatchFailedJobs);
  $('#registrationBatchSelectV2')?.addEventListener('change', event => {
    setJobProgressBatch(event.target.value || '');
    batchProgressRenderSignature = '';
    refreshJobs();
  });
  const refreshV2 = $('#btnRefreshJobsV2');
  if (refreshV2) refreshV2.addEventListener('click', () => refreshJobsManual(refreshV2));

  function stepInputNumber(inputId, delta) {
    const el = document.getElementById(inputId);
    if (!el) return;
    const min = Number(el.min || 1);
    const max = Number(el.max || 9999);
    const next = Math.min(max, Math.max(min, (parseInt(el.value, 10) || min) + delta));
    el.value = String(next);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  document.querySelectorAll('#jobsToolbarV2 [data-step-for], #accountsToolbarV2 [data-step-for]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      stepInputNumber(btn.dataset.stepFor, parseInt(btn.dataset.step, 10) || 0);
    });
  });
  const selectAllV2 = $('#jobsSelectAllV2');
  if (selectAllV2) selectAllV2.addEventListener('change', (e) => syncJobsSelectAll(e.target.checked));
  bindJobsBodyEvents($('#jobsBodyV2'));
  const progressListV2 = $('#batchProgressListV2');
  if (progressListV2) progressListV2.addEventListener('click', (e) => {
    const logBtn = e.target.closest('[data-progress-log-job]');
    if (logBtn) openLog(parseInt(logBtn.dataset.progressLogJob, 10));
    const retryBtn = e.target.closest('[data-progress-retry-job]');
    if (retryBtn) retryJob(parseInt(retryBtn.dataset.progressRetryJob, 10), retryBtn);
  });
})();

function progressDateMs(value) {
  if (!value) return 0;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? ms : 0;
}

function formatProgressDuration(startValue, endValue = '') {
  const start = progressDateMs(startValue);
  if (!start) return '';
  const end = progressDateMs(endValue) || Date.now();
  const seconds = Math.max(0, Math.floor((end - start) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (hours > 0) return `${hours}时${minutes}分${rest}秒`;
  if (minutes > 0) return `${minutes}分${rest}秒`;
  return `${rest}秒`;
}

function progressJobResult(job) {
  const status = String(job.status || 'pending');
  if (status === 'success') return { label: '成功', cls: '' };
  if (status === 'request_unknown') return { label: '待确认', cls: 'is-failed' };
  if (status === 'failed') return { label: '失败', cls: 'is-failed' };
  if (status === 'cancelled') return { label: '已取消', cls: 'is-failed' };
  if (status === 'stopped') return { label: '已停止', cls: 'is-failed' };
  if (status === 'stopping') return { label: '停止中', cls: 'is-running' };
  if (status === 'running') return { label: '进行中', cls: 'is-running' };
  return { label: '等待中', cls: 'is-waiting' };
}

function refreshBatchProgressDurations() {
  $$('#batchProgressListV2 [data-progress-duration-start]').forEach(el => {
    const duration = formatProgressDuration(el.dataset.progressDurationStart, el.dataset.progressDurationEnd || '');
    el.textContent = duration ? `${el.dataset.progressDurationPrefix || ''}${duration}` : '';
  });
}

function setJobProgressBatch(batchId) {
  JOB_PROGRESS_BATCH_ID = String(batchId || '').trim();
  if (JOB_PROGRESS_BATCH_ID) localStorage.setItem('gpt_console_registration_batch_id', JOB_PROGRESS_BATCH_ID);
  else localStorage.removeItem('gpt_console_registration_batch_id');
}

function renderRegistrationBatchSelector() {
  const select = $('#registrationBatchSelectV2');
  if (!select) return;
  const batches = Array.isArray(JOB_PROGRESS_BATCHES) ? [...JOB_PROGRESS_BATCHES] : [];
  if (JOB_PROGRESS_BATCH?.batch_id && !batches.some(batch => batch.batch_id === JOB_PROGRESS_BATCH.batch_id)) {
    batches.unshift({
      batch_id: JOB_PROGRESS_BATCH.batch_id,
      created_at: JOB_PROGRESS_BATCH.created_at,
      total: JOB_PROGRESS_BATCH.total,
      kind: currentBatchJobs().some(job => job.parent_job_id) ? 'retry' : 'registration',
      status_counts: JOB_PROGRESS_BATCH.status_counts || {},
    });
  }
  select.innerHTML = batches.map(batch => {
    const counts = batch.status_counts || {};
    const active = Number(counts.active || 0);
    const failures = Number(counts.failed || 0) + Number(counts.partial_success || 0) + Number(counts.request_unknown || 0) + Number(counts.stopped || 0) + Number(counts.cancelled || 0);
    const state = active > 0 ? `进行中 ${active}` : (failures > 0 ? `异常 ${failures}` : '已完成');
    const kind = batch.kind === 'retry' ? '批量重跑' : '发起注册';
    const time = formatDateTime(batch.created_at).replace(/:\d{2}$/, '');
    const label = `${time} · ${kind} · ${Number(batch.total || 0)} 个 · ${state}`;
    return `<option value="${attrEsc(batch.batch_id)}">${esc(label)}</option>`;
  }).join('');
  select.value = JOB_PROGRESS_BATCH_ID;
  select.disabled = batches.length < 2;
}

function renderBatchProgress() {
  const panel = $('#batchProgressV2');
  if (!panel) return;
  renderRegistrationBatchSelector();
  const batch = JOB_PROGRESS_BATCH;
  const items = batch && Array.isArray(batch.items) ? batch.items : [];
  const stages = batch && Array.isArray(batch.stages) ? batch.stages : [];
  if (!batch || !items.length || !stages.length) {
    batchProgressRenderSignature = '';
    panel.classList.add('hidden');
    return;
  }
  panel.classList.remove('hidden');

  const hasFailedStep = job => Object.values(job.progress_steps || {}).some(step => step && ['failed', 'stopped'].includes(step.state));
  const success = items.filter(job => job.status === 'success' && !hasFailedStep(job)).length;
  const failed = items.filter(job => ['failed', 'cancelled', 'stopped'].includes(job.status) || hasFailedStep(job)).length;
  const active = items.filter(job => ['running', 'stopping'].includes(job.status) && !hasFailedStep(job)).length;
  const pending = items.filter(job => job.status === 'pending').length;
  const total = Number(batch.total || items.length);
  const stateEl = $('#batchProgressStateV2');
  let stateLabel = '等待中', stateClass = 'is-waiting';
  if (success === total && total > 0) { stateLabel = '全部成功'; stateClass = ''; }
  else if (active > 0) { stateLabel = '进行中'; stateClass = ''; }
  else if (failed > 0) { stateLabel = success > 0 ? '部分失败' : '批次失败'; stateClass = 'is-failed'; }
  if (batch.projection_delayed) {
    stateLabel += ' · 投影延迟';
    if (!stateClass) stateClass = 'is-waiting';
  }
  if (stateEl) {
    stateEl.textContent = stateLabel;
    stateEl.className = `batch-progress-v2-state ${stateClass}`.trim();
  }
  const summaryEl = $('#batchProgressSummaryV2');
  if (summaryEl) summaryEl.textContent = `成功 ${success} · 失败 ${failed} · 运行 ${active} · 等待 ${pending} ｜ 共 ${total} · 并发 ${Number(batch.workers || 1)}`;
  const allDone = active === 0 && pending === 0;
  const batchDuration = formatProgressDuration(batch.started_at || batch.created_at, allDone ? batch.completed_at : '');
  const timeEl = $('#batchProgressTimeV2');
  if (timeEl) timeEl.textContent = batchDuration ? `批次耗时 ${batchDuration}` : '';

  const runningIds = items.filter(job => ['running', 'stopping'].includes(String(job.status || ''))).map(job => Number(job.id));
  const pendingIds = items.filter(job => String(job.status || '') === 'pending').map(job => Number(job.id));
  const retryIds = items.filter(job => ['failed', 'partial_success', 'stopped', 'cancelled'].includes(String(job.status || '')) && job.retryable).map(job => Number(job.id));
  const stopBtn = $('#btnBatchStopV2');
  const cancelBtn = $('#btnBatchCancelV2');
  const retryBtn = $('#btnBatchRetryV2');
  if (stopBtn) stopBtn.disabled = runningIds.length === 0;
  if (cancelBtn) cancelBtn.disabled = pendingIds.length === 0;
  if (retryBtn) retryBtn.disabled = retryIds.length === 0;

  const list = $('#batchProgressListV2');
  if (!list) return;
  const nextRenderSignature = JSON.stringify({batch_id: batch.batch_id, stages, items});
  if (nextRenderSignature === batchProgressRenderSignature) {
    // 只更新计时文字，避免轮询重建 DOM 后打断失败节点的悬浮报错。
    refreshBatchProgressDurations();
    return;
  }
  batchProgressRenderSignature = nextRenderSignature;
  list.innerHTML = items.map((job, itemIndex) => {
    const steps = job.progress_steps && typeof job.progress_steps === 'object' ? job.progress_steps : {};
    const terminal = ['success', 'partial_success', 'failed', 'cancelled', 'stopped', 'request_unknown'].includes(String(job.status || ''));
    const duration = formatProgressDuration(job.started_at || job.created_at, terminal ? job.completed_at : '');
    const failedStageIndex = stages.findIndex(stage => ['failed', 'stopped'].includes(String((steps[stage.key] || {}).state || '')));
    const failedStep = failedStageIndex >= 0 ? (steps[stages[failedStageIndex].key] || {}) : null;
    const result = String(job.status || '') === 'request_unknown'
      ? progressJobResult(job)
      : failedStep ? { label: '部分失败', cls: 'is-failed' } : progressJobResult(job);
    const cardFailed = ['failed', 'cancelled', 'stopped', 'request_unknown'].includes(String(job.status || '')) || Boolean(failedStep);
    const stepHtml = stages.map((stage, index) => {
      const step = steps[stage.key] || {};
      const state = String(step.state || 'pending');
      const previous = index > 0 ? (steps[stages[index - 1].key] || {}) : {};
      const reached = index > 0 && ['success', 'skipped'].includes(String(previous.state || ''));
      const symbol = state === 'success' ? '✓'
        : state === 'skipped' ? '–'
        : state === 'running' ? '…'
        : state === 'failed' ? '×'
        : state === 'stopped' ? '!'
        : String(index + 1);
      const stageError = ['failed', 'stopped'].includes(state) ? (step.detail || job.error_message || '') : '';
      const stageDetail = stageError || (state === 'skipped' ? (step.detail || '已跳过') : '');
      const detailTitle = stageDetail ? ` title="${esc(stageDetail)}" aria-label="${esc(stage.label)}：${esc(stageDetail)}"` : '';
      const stepDuration = formatProgressDuration(step.started_at, ['success', 'failed', 'skipped', 'stopped'].includes(state) ? step.completed_at : '');
      const stepDurationEnd = ['success', 'failed', 'skipped', 'stopped'].includes(state) ? (step.completed_at || '') : '';
      return `<div class="batch-progress-v2-step is-${esc(state)}${reached ? ' is-reached' : ''}"${detailTitle}>
        <span class="batch-progress-v2-node">${symbol}</span>
        <span class="batch-progress-v2-step-label">${esc(stage.label)}${stepDuration ? `<span class="batch-progress-v2-step-duration" data-progress-duration-start="${attrEsc(step.started_at)}" data-progress-duration-end="${attrEsc(stepDurationEnd)}">${esc(stepDuration)}</span>` : ''}</span>
      </div>`;
    }).join('');
    const batchIndex = Number(job.batch_index || itemIndex + 1);
    const email = job.email || (job.status === 'pending' ? '等待领取邮箱…' : '准备邮箱中…');
    const sourceLabel = registrationEmailSourceLabel(job.email_source);
    return `<article class="batch-progress-v2-card${cardFailed ? ' is-failed' : ''}">
      <div class="batch-progress-v2-card-top">
        <div class="batch-progress-v2-identity">
          <span class="batch-progress-v2-index">#${esc(batchIndex)}</span>
          <span class="batch-progress-v2-email" title="${esc(email)}">${esc(email)}</span>
          <span class="sub-cell">${esc(sourceLabel)}</span>
        </div>
        <div class="batch-progress-v2-meta">
          ${!terminal && duration ? `<span data-progress-duration-start="${attrEsc(job.started_at || job.created_at)}" data-progress-duration-end="" data-progress-duration-prefix="耗时 ">耗时 ${esc(duration)}</span>` : ''}
          <span class="batch-progress-v2-result ${result.cls}">${result.label}</span>
          ${job.retryable ? `<button type="button" class="batch-progress-v2-log" data-progress-retry-job="${esc(job.id)}" title="${esc(job.retry_label || '重跑该任务')}">重跑</button>` : ''}
          <button type="button" class="batch-progress-v2-log" data-progress-log-job="${esc(job.id)}">查看日志</button>
        </div>
      </div>
      <div class="batch-progress-v2-steps-scroll"><div class="batch-progress-v2-steps" style="--batch-progress-step-count:${Math.max(stages.length, 1)}">${stepHtml}</div></div>
    </article>`;
  }).join('');
  refreshBatchProgressDurations();
}

function renderJobs() {
  const total = JOBS_TOTAL;
  const rows = JOBS;
  const bodyV2 = $('#jobsBodyV2');
  if (bodyV2) {
    const icons = jobsV2OpIcons();
    bodyV2.innerHTML = rows.map(j => {
      const running = ['running','stopping'].includes(j.status);
      const stoppable = ['pending','running','stopping'].includes(j.status);
      const started = formatDateTime(j.started_at);
      const completed = formatDateTime(j.completed_at);
      const err = j.error_message || '';
      const manualOtp = j.status === 'running' && j.email && j.manual_otp_required;
      const proxyLabel = j.proxy_provider ? `${j.proxy_provider}${j.proxy_endpoint && j.proxy_endpoint !== '-' ? ` · ${j.proxy_endpoint}` : ''}${j.proxy_region && j.proxy_region !== '-' ? ` · ${j.proxy_region}` : ''}` : '-';
      return `
      <tr>
        <td class="col-check"><input type="checkbox" class="job-row-check" data-job-id="${esc(j.id)}" ${JOB_SELECTED.has(Number(j.id)) ? 'checked' : ''} ${running ? 'disabled title="运行中的任务不能选择"' : ''}></td>
        <td class="col-id">#${esc(j.id)}${j.parent_job_id ? `<div class="sub-cell" title="重试自任务 #${esc(j.parent_job_id)}">↳ #${esc(j.parent_job_id)} · ${esc(j.retry_attempt || 1)}</div>` : ''}</td>
        <td class="col-email" title="${esc(j.email || '-')}">${esc(j.email || '-')}</td>
        <td class="col-source" title="${esc(registrationEmailSourceLabel(j.email_source))}">${esc(registrationEmailSourceLabel(j.email_source))}</td>
        <td class="col-proxy" title="${esc(proxyLabel)} · ${esc(j.proxy_status || '-')}">${esc(proxyLabel)}</td>
        <td class="col-status">${pillV2(j.debug_state === 'paused' ? 'debug_paused' : (j.display_status || j.status))}</td>
        <td class="col-time" title="${esc(started)}">${esc(started)}</td>
        <td class="col-time" title="${esc(completed)}">${esc(completed)}</td>
        <td class="col-error" title="${esc(err)}">${err ? `${taskErrorBadge(j.error_info)}<span class="task-error-cell-text">${esc(short(j.error_info?.summary || err, 60))}</span>` : '-'}</td>
        <td class="col-actions">
          <div class="jobs-v2-ops">
            <button type="button" class="jobs-v2-op jobs-v2-op--view" data-log-job="${esc(j.id)}" title="查看日志">${icons.view}</button>
            ${manualOtp ? `<input class="manual-otp-input manual-otp-input--v2" data-otp-email="${esc(j.email)}" data-otp-job="${esc(j.id)}" placeholder="邮箱验证码" maxlength="8" title="手动模式下，打开邮箱后把 6 位验证码贴这里"><button type="button" class="jobs-v2-op jobs-v2-op--otp" data-submit-otp-job="${esc(j.id)}" data-email="${esc(j.email)}" title="提交验证码">${icons.check}</button>` : ''}
            ${stoppable ? `<button type="button" class="jobs-v2-op jobs-v2-op--stop" data-stop-job="${esc(j.id)}" title="${j.status === 'stopping' ? '停止/修复' : '停止'}">${icons.stop}</button>` : ''}
            ${j.retryable ? `<button type="button" class="jobs-v2-op jobs-v2-op--retry" data-retry-job="${esc(j.id)}" title="${esc(j.retry_action === 'codex' ? '账号已创建，仅补跑 Codex 授权' : (j.retry_action === 'twofa' ? '重新登录检查并补齐 2FA' : (j.retry_action === 'registration_resume' ? '使用已保存密码继续邮箱验证' : (j.retry_label || '重试'))))}">${icons.retry}</button>` : ''}
            <button type="button" class="jobs-v2-op jobs-v2-op--del" data-delete-job="${esc(j.id)}" ${running ? 'disabled title="运行中的任务不能删除；如需删除请先停止"' : 'title="删除"'}>${icons.del}</button>
          </div>
        </td>
      </tr>`;
    }).join('') || renderTableStateRow(10, '暂无匹配任务', '调整筛选条件，或发起新的注册批次。');
  }


  renderBatchProgress();
  const summary = $('#jobsPageSummary');
  if (summary) summary.textContent = `${total || 0} 个任务 · 当前页 ${rows.length} 条`;
  updateJobsSelectionUi(rows);
  _renderPager('jobs', total);
}

function updateJobsSelectionUi(pageRows = null) {
  const bulkBtnV2 = $('#btnDeleteSelectedJobsV2');
  const bulkRetryBtnV2 = $('#btnRetrySelectedJobsV2');
  const hintV2 = $('#jobsSelectedHintV2');
  const toolbarV2 = hintV2?.closest('.list-action-toolbar');
  toolbarV2?.classList.toggle('has-selection', JOB_SELECTED.size > 0);
  if (hintV2) hintV2.textContent = JOB_SELECTED.size ? `已选 ${JOB_SELECTED.size} 个任务` : '选择任务后批量操作';
  if (bulkBtnV2) bulkBtnV2.disabled = JOB_SELECTED.size === 0;
  if (bulkRetryBtnV2) bulkRetryBtnV2.disabled = JOB_SELECTED.size === 0;

  if (!pageRows) pageRows = JOBS;
  const selectableIds = pageRows.filter(j => !['running','stopping'].includes(j.status)).map(j => Number(j.id));
  const checkedCount = selectableIds.filter(id => JOB_SELECTED.has(id)).length;
  const cbAll = document.getElementById('jobsSelectAllV2');
  if (cbAll) {
    cbAll.checked = selectableIds.length > 0 && checkedCount === selectableIds.length;
    cbAll.indeterminate = checkedCount > 0 && checkedCount < selectableIds.length;
    cbAll.disabled = selectableIds.length === 0;
  }
}

function updateJobStatusFilters(facets = {}) {
  syncFacetSelect('jobStatusColumnFilterV2', facets.status, {group:'status'});
  syncFacetSelect('jobSourceColumnFilterV2', facets.email_source, {group:'source'});
  const status = $('#jobStatusColumnFilterV2'); if (status) status.value = JOB_STATUS_FILTER;
  const source = $('#jobSourceColumnFilterV2'); if (source) source.value = JOB_EMAIL_SOURCE_FILTER;
  if (status) refreshColumnFilterState(status);
  if (source) refreshColumnFilterState(source);
}
$('#jobStatusColumnFilterV2')?.addEventListener('change', event => {
  JOB_STATUS_FILTER = event.target.value || '';
  PAGERS.jobs.page = 1;
  JOB_SELECTED.clear();
  jobsRenderSignature = '';
  refreshJobs();
});
[
  ['jobIdFilterV2', value => { JOB_ID_FILTER = value; }],
  ['jobEmailFilterV2', value => { JOB_EMAIL_FILTER = value; }],
  ['jobProxyFilterV2', value => { JOB_PROXY_FILTER = value; }],
  ['jobErrorFilterV2', value => { JOB_ERROR_FILTER = value; }],
].forEach(([id, assign]) => document.getElementById(id)?.addEventListener('input', debounce(event => {
  assign(event.target.value.trim());
  PAGERS.jobs.page = 1;
  JOB_SELECTED.clear();
  refreshColumnFilterStates();
  refreshJobs();
}, 250)));
$('#jobSourceColumnFilterV2')?.addEventListener('change', event => {
  JOB_EMAIL_SOURCE_FILTER = event.target.value || '';
  PAGERS.jobs.page = 1;
  JOB_SELECTED.clear();
  refreshJobs();
});
['jobDateFromV2', 'jobDateToV2'].forEach(id => document.getElementById(id)?.addEventListener('change', event => {
  if (id === 'jobDateFromV2') JOB_DATE_FROM = event.target.value || '';
  else JOB_DATE_TO = event.target.value || '';
  PAGERS.jobs.page = 1;
  JOB_SELECTED.clear();
  refreshJobs();
}));
$('#btnResetJobFiltersV2')?.addEventListener('click', () => {
  JOB_ID_FILTER = ''; JOB_EMAIL_FILTER = ''; JOB_EMAIL_SOURCE_FILTER = ''; JOB_PROXY_FILTER = ''; JOB_ERROR_FILTER = '';
  JOB_DATE_FROM = ''; JOB_DATE_TO = ''; JOB_STATUS_FILTER = '';
  ['jobIdFilterV2', 'jobEmailFilterV2', 'jobSourceColumnFilterV2', 'jobProxyFilterV2', 'jobStatusColumnFilterV2', 'jobDateFromV2', 'jobDateToV2', 'jobErrorFilterV2'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '';
  });
  PAGERS.jobs.page = 1;
  JOB_SELECTED.clear();
  refreshColumnFilterStates();
  refreshJobs();
});

async function refreshJobs() {
  if (jobsLoading) { jobsReloadQueued = true; return; }
  jobsLoading = true;
  setListBusy('jobsPanelV2', true);
  try {
    const p = PAGERS.jobs;
    const res = await api(`/api/jobs?paged=1&page=${encodeURIComponent(p.page)}&page_size=${encodeURIComponent(p.size)}&status=${encodeURIComponent(JOB_STATUS_FILTER)}&id=${encodeURIComponent(JOB_ID_FILTER)}&email=${encodeURIComponent(JOB_EMAIL_FILTER)}&email_source=${encodeURIComponent(JOB_EMAIL_SOURCE_FILTER)}&proxy=${encodeURIComponent(JOB_PROXY_FILTER)}&error=${encodeURIComponent(JOB_ERROR_FILTER)}&date_from=${encodeURIComponent(JOB_DATE_FROM)}&date_to=${encodeURIComponent(JOB_DATE_TO)}&progress_batch_id=${encodeURIComponent(JOB_PROGRESS_BATCH_ID)}`);
    const nextJobs = res.items || [];
    JOBS_TOTAL = Number(res.total || nextJobs.length || 0);
    JOB_STATUS_COUNTS = res.status_counts || {};
    updateJobStatusFilters(res.facets || {});
    JOB_PROGRESS_BATCHES = res.progress_batches || [];
    JOB_PROGRESS_BATCH = res.progress_batch || null;
    if (JOB_PROGRESS_BATCH_ID && !JOB_PROGRESS_BATCH) {
      setJobProgressBatch(JOB_PROGRESS_BATCHES[0]?.batch_id || '');
      if (JOB_PROGRESS_BATCH_ID) {
        jobsLoading = false;
        return refreshJobs();
      }
    } else if (!JOB_PROGRESS_BATCH_ID && JOB_PROGRESS_BATCH?.batch_id) {
      setJobProgressBatch(JOB_PROGRESS_BATCH.batch_id);
    }
    const totalPages = Math.max(1, Math.ceil(JOBS_TOTAL / p.size));
    if (p.page > totalPages) {
      p.page = totalPages;
      jobsLoading = false;
      return refreshJobs();
    }
    const nextSignature = `${res.revision || ''}|${p.page}|${p.size}|${JSON.stringify(JOB_PROGRESS_BATCH || {})}|${JSON.stringify(JOB_PROGRESS_BATCHES)}`;
    JOBS = nextJobs;
    if (nextSignature !== jobsRenderSignature) {
      jobsRenderSignature = nextSignature;
      renderJobs();
    } else {
      // 数据不变时也刷新耗时文本。
      renderBatchProgress();
    }
  } catch(e) {
    if (!JOBS.length) $('#jobsBodyV2').innerHTML = renderTableStateRow(10, '任务加载失败', '服务暂时不可用，系统会自动重试。', 'error');
  }
  finally {
    jobsLoading = false;
    setListBusy('jobsPanelV2', false);
    if (jobsReloadQueued) {
      jobsReloadQueued = false;
      queueMicrotask(refreshJobs);
    }
  }
}
async function refreshJobsManual(btn) {
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '刷新中…';
  try { await refreshJobs(); showToast('任务列表已刷新'); }
  finally { btn.textContent = old; btn.disabled = false; }
}

let modalScrollY = 0;
function updateModalScrollLock() {
  const opened = !$('#logPanel').classList.contains('hidden')
    || !$('#liveLogPanel').classList.contains('hidden')
    || !$('#accountTaskLogPanel').classList.contains('hidden')
    || !$('#qrPanel').classList.contains('hidden')
    || !$('#outlookImportModal').classList.contains('hidden')
    || !$('#accountDetailDrawer').classList.contains('hidden');
  const locked = document.body.classList.contains('modal-open');
  if (opened && !locked) {
    modalScrollY = window.scrollY || document.documentElement.scrollTop || 0;
    document.body.style.top = `-${modalScrollY}px`;
    document.body.classList.add('modal-open');
    document.documentElement.style.overflow = 'hidden';
  } else if (!opened && locked) {
    document.body.classList.remove('modal-open');
    document.body.style.top = '';
    document.documentElement.style.overflow = '';
    window.scrollTo(0, modalScrollY || 0);
  }
}
function closeLogModal() {
  activeLogJob = null;
  clearInterval(logTimer);
  $('#logPanel').classList.add('hidden');
  updateModalScrollLock();
}
function closeLiveLogModal() {
  liveLogEmail = null;
  clearInterval(liveLogTimer);
  $('#liveLogPanel').classList.add('hidden');
  updateModalScrollLock();
}
function closeAccountTaskLogModal() {
  activeAccountTaskId = null;
  clearInterval(accountTaskLogTimer);
  $('#accountTaskLogPanel').classList.add('hidden');
  updateModalScrollLock();
}
function openQrModal(url) {
  $('#qrImage').src = url;
  $('#qrOpenLink').href = url;
  $('#qrOpenLink').textContent = url;
  $('#qrPanel').classList.remove('hidden');
  updateModalScrollLock();
  $('#btnCloseQrPanel')?.focus({preventScroll:true});
}
function closeQrModal() {
  $('#qrPanel').classList.add('hidden');
  $('#qrImage').removeAttribute('src');
  updateModalScrollLock();
}

$('#btnCloseLog').addEventListener('click', closeLogModal);
$('#btnCloseAccountTaskLog')?.addEventListener('click', closeAccountTaskLogModal);
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (!$('#logPanel').classList.contains('hidden')) closeLogModal();
  else if (!$('#liveLogPanel').classList.contains('hidden')) closeLiveLogModal();
  else if (!$('#accountTaskLogPanel').classList.contains('hidden')) closeAccountTaskLogModal();
  else if (!$('#qrPanel').classList.contains('hidden')) closeQrModal();
});

async function submitManualOtpForJob(btn) {
  const jobId = parseInt(btn.dataset.submitOtpJob, 10);
  const email = btn.dataset.email || '';
  const input = document.querySelector(`.manual-otp-input[data-otp-job="${jobId}"]`);
  const code = (input?.value || '').trim();
  if (!code) { showToast('请先填写邮箱验证码'); return; }
  btn.disabled = true;
  try {
    const r = await api('/api/manual-otp', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ email, code, job_id: jobId }),
    });
    showToast(r.ok ? `已提交验证码给 ${email || ('#'+jobId)}` : (r.error || '提交失败'));
    if (input) input.value = '';
    if (activeLogJob === jobId) pollLog();
  } catch (e) {
    showToast('提交验证码失败: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

async function stopJob(jobId, btn) {
  const job = JOBS.find(j => Number(j.id) === Number(jobId));
  const statusText = job?.status || '-';
  const emailText = job?.email || '未分配邮箱';
  if (!confirm(`确定停止任务 #${jobId}？\n\n状态：${statusText}\n邮箱：${emailText}\n\n排队任务会直接取消；运行中的任务会发送停止信号，并在当前步骤检查点退出。`)) return;
  btn.disabled = true;
  try {
    const r = await api(`/api/jobs/${jobId}/stop`, { method:'POST', headers:{'Content-Type':'application/json'}, body: '{}' });
    showToast(r.message || '已发送停止信号');
    refreshJobs();
    if (activeLogJob === jobId) pollLog();
  } catch(e) {
    showToast('停止失败: ' + e.message);
    btn.disabled = false;
  }
}

async function deleteJob(jobId, btn) {
  const job = JOBS.find(j => Number(j.id) === Number(jobId));
  const statusText = job?.status || '-';
  const emailText = job?.email || '未分配邮箱';
  if (!confirm(`确定删除任务 #${jobId}？\n\n状态：${statusText}\n邮箱：${emailText}\n\n会同时删除该任务日志。排队任务删除后将不会执行。`)) return;
  btn.disabled = true;
  try {
    const r = await api(`/api/jobs/${jobId}/delete`, { method:'POST', headers:{'Content-Type':'application/json'}, body: '{}' });
    if (activeLogJob === jobId) closeLogModal();
    showToast(r.deleted ? '任务已删除' : '任务不存在');
    JOB_SELECTED.delete(Number(jobId));
    refreshJobs();
  } catch(e) {
    showToast('删除失败: ' + e.message);
    btn.disabled = false;
  }
}

async function deleteSelectedJobs() {
  const ids = Array.from(JOB_SELECTED);
  if (ids.length === 0) { showToast('请先选择任务'); return; }
  const msg = `确定删除选中的 ${ids.length} 个任务吗？\n\n` +
              `会同时删除对应日志。排队/运行中的任务会由后端逐条校验，不能删除的会自动跳过。`;
  if (!confirm(msg)) return;

  const bulkDel = $('#btnDeleteSelectedJobsV2');
  if (bulkDel) bulkDel.disabled = true;
  try {
    const r = await api('/api/jobs/delete-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({job_ids: ids}),
    });
    (r.deleted || []).forEach(id => JOB_SELECTED.delete(Number(id)));
    if (activeLogJob != null && (r.deleted || []).map(Number).includes(Number(activeLogJob))) closeLogModal();
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已删除 ${r.deleted_count || 0} 个，跳过 ${skippedCount} 个` : `已删除 ${r.deleted_count || 0} 个`);
    refreshJobs();
  } catch(e) {
    showToast('批量删除失败: ' + e.message);
    updateJobsSelectionUi();
  }
}

async function retryJob(jobId, btn) {
  const job = JOBS.find(j => Number(j.id) === Number(jobId))
    || currentBatchJobs().find(j => Number(j.id) === Number(jobId));
  if (!job || !job.retryable) { showToast('该任务当前不可重试'); return; }
  const actionText = job.retry_action === 'codex'
    ? '仅补跑 Codex 授权'
    : (job.retry_action === 'twofa'
      ? '重新登录检查并补齐 Authenticator 2FA'
      : (job.retry_action === 'registration_resume'
        ? '使用已保存账号密码继续邮箱验证'
        : '创建新的完整注册任务'));
  if (!confirm(`确定${job.retry_label || '重试'}任务 #${jobId}？\n\n${actionText}\n原任务记录和日志会保留。`)) return;
  btn.disabled = true;
  try {
    const r = await api(`/api/jobs/${jobId}/retry`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({}),
    });
    showToast(r.message || '已提交重试任务');
    JOB_SELECTED.delete(Number(jobId));
    refreshJobs();
  } catch (e) {
    showToast('重试失败: ' + e.message);
    btn.disabled = false;
  }
}

async function retrySelectedJobs() {
  const ids = Array.from(JOB_SELECTED);
  if (!confirm(`确定重试选中的 ${ids.length} 个任务吗？\n\n后端会逐条校验；已创建账号的任务只补跑 Codex，其余任务重新入队注册，不能重试的会自动跳过。`)) return;
  const btn = $('#btnRetrySelectedJobsV2');
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/jobs/retry-bulk', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({job_ids: ids}),
    });
    if (r.batch_id) setJobProgressBatch(r.batch_id);
    ids.forEach(id => JOB_SELECTED.delete(Number(id)));
    const skippedCount = (r.skipped || []).length;
    const reusedCount = r.reused_count || 0;
    showToast(`已提交 ${r.started_count || 0} 个${reusedCount ? `，复用 ${reusedCount} 个` : ''}${skippedCount ? `，跳过 ${skippedCount} 个` : ''}`);
    refreshJobs();
  } catch (e) {
    showToast('批量重试失败: ' + e.message);
  } finally {
    updateJobsSelectionUi();
  }
}

function openLog(jobId) {
  activeLogJob = jobId;
  $('#logJobId').textContent = jobId;
  $('#logPanel').classList.remove('hidden');
  updateModalScrollLock();
  $('#btnCloseLog')?.focus({preventScroll:true});
  $('#logContent').textContent = '加载中…';
  const debugPanel = $('#debugCapturePanel');
  if (debugPanel) debugPanel.classList.add('hidden');
  const comparePanel = $('#debugCaptureCompare');
  if (comparePanel) comparePanel.classList.add('hidden');
  const title = $('#debugCaptureTitle');
  if (title) title.textContent = '网络调试';
  const screenshot = $('#btnFailureDiagnosticScreenshot');
  if (screenshot) { screenshot.classList.add('hidden'); screenshot.removeAttribute('href'); }
  const pageState = $('#debugCapturePageState');
  if (pageState) { pageState.classList.add('hidden'); pageState.textContent = ''; }
  renderTaskLogErrorSummary('logErrorSummary', null);
  pollLog();
  clearInterval(logTimer);
  logTimer = setInterval(pollLog, 2000);
}
async function pollLog() {
  if (activeLogJob == null) return;
  try {
    const r = await api(`/api/jobs/${activeLogJob}/log`);
    const c = $('#logContent');
    renderTaskLogErrorSummary('logErrorSummary', r.job || null);
    const atBottom = c.scrollTop + c.clientHeight >= c.scrollHeight - 30;
    c.textContent = r.log || '(暂无日志)';
    if (atBottom) c.scrollTop = c.scrollHeight;
    await pollRegistrationDebug(activeLogJob);
    if (r.job && ['success','partial_success','failed','stopped','cancelled','request_unknown'].includes(r.job.status)) clearInterval(logTimer);
  } catch(e) {}
}

function debugBodySnippet(value) {
  if (value == null || value === '') return '';
  let text = '';
  try { text = typeof value === 'string' ? value : JSON.stringify(value); }
  catch (_) { text = String(value); }
  return short(text, 320);
}

function renderRegistrationDebug(data) {
  const panel = $('#debugCapturePanel');
  if (!panel) return;
  if (!data?.enabled) {
    panel.classList.add('hidden');
    return;
  }
  const title = $('#debugCaptureTitle');
  if (title) title.textContent = '网络调试';
  const screenshot = $('#btnFailureDiagnosticScreenshot');
  if (screenshot) screenshot.classList.add('hidden');
  const pageState = $('#debugCapturePageState');
  if (pageState) pageState.classList.add('hidden');
  panel.classList.remove('hidden');
  const summary = data.summary || {};
  const state = data.state || summary.state || 'recording';
  const summaryEl = $('#debugCaptureSummary');
  if (summaryEl) {
    summaryEl.textContent = `状态 ${state} · 请求 ${summary.request_count || 0} · HTTP错误 ${summary.http_error_count || 0} · 网络失败 ${summary.failed_count || 0}` +
      (data.hold_until ? ` · 保留至 ${formatDateTime(data.hold_until)}` : '');
  }
  const releaseBtn = $('#btnDebugRelease');
  if (releaseBtn) releaseBtn.classList.toggle('hidden', state !== 'paused');
  $('#btnDebugCompare')?.classList.remove('hidden');
  const har = $('#btnDebugHar');
  if (har) { har.classList.remove('hidden'); har.href = `/api/jobs/${encodeURIComponent(data.job_id)}/debug/har`; }
  const rows = Array.isArray(data.events) ? data.events : [];
  const list = $('#debugNetworkList');
  if (list) list.innerHTML = rows.map(item => {
    const status = Number(item.status || 0);
    const isError = Boolean(item.failure) || status >= 400;
    const detail = item.failure || debugBodySnippet(item.response_body);
    return `<div class="debug-network-row${isError ? ' is-error' : ''}">
      <span>${esc(item.stage || '-')}</span>
      <strong>${esc(item.method || '-')}</strong>
      <span class="debug-network-url" title="${esc(item.url || '')}">${esc(item.url || '-')}</span>
      <span>${esc(status || (item.failure ? 'FAIL' : '-'))}${item.duration_ms != null ? ` · ${esc(Math.round(Number(item.duration_ms)))}ms` : ''}</span>
      ${detail ? `<span class="debug-network-detail">${esc(detail)}</span>` : ''}
    </div>`;
  }).join('') || '<div class="debug-network-row"><span class="debug-network-detail">抓包已启动，暂时还没有可显示的请求。</span></div>';
}

function renderRegistrationDiagnostics(data) {
  const panel = $('#debugCapturePanel');
  if (!panel) return;
  if (!data?.enabled || !data?.captured) {
    panel.classList.add('hidden');
    return;
  }
  panel.classList.remove('hidden');
  const title = $('#debugCaptureTitle');
  if (title) title.textContent = '失败诊断';
  const summary = data.summary || {};
  const page = data.page_state || {};
  const dom = page.dom || {};
  const summaryEl = $('#debugCaptureSummary');
  if (summaryEl) {
    summaryEl.textContent = `分类 ${data.category_label || data.category || page.failure_category || '未分类'} · 输入框 ${Number(dom.input_count || 0)} · 操作 ${Number(dom.action_count || 0)} · 失败请求 ${Number(summary.failed_count || 0)} · HTTP错误 ${Number(summary.http_error_count || 0)}`;
  }
  $('#btnDebugRelease')?.classList.add('hidden');
  $('#btnDebugCompare')?.classList.add('hidden');
  $('#btnDebugHar')?.classList.add('hidden');
  $('#debugCaptureCompare')?.classList.add('hidden');
  const screenshot = $('#btnFailureDiagnosticScreenshot');
  if (screenshot) {
    screenshot.classList.toggle('hidden', !data.screenshot_url);
    if (data.screenshot_url) screenshot.href = data.screenshot_url;
  }
  const pageState = $('#debugCapturePageState');
  if (pageState) {
    const lines = [
      `URL: ${page.url || '-'}`,
      `标题: ${page.title || '-'} · readyState: ${page.ready_state || '-'}`,
      `原因: ${data.failure_reason || page.reason || '-'}`,
      `资源: ${Array.isArray(page.resources) ? page.resources.length : 0} 条 · 浏览器错误: ${Array.isArray(page.browser_logs) ? page.browser_logs.length : 0} 条`,
      `页面文本: ${short(page.body_text || '', 800) || '-'}`,
    ];
    pageState.textContent = lines.join('\n');
    pageState.classList.remove('hidden');
  }
  const rows = Array.isArray(data.events) ? data.events : [];
  const list = $('#debugNetworkList');
  if (list) list.innerHTML = rows.map(item => {
    const status = Number(item.status || 0);
    const detail = item.failure || 'HTTP错误';
    return `<div class="debug-network-row is-error">
      <span>${esc(item.stage || '-')}</span>
      <strong>${esc(item.method || '-')}</strong>
      <span class="debug-network-url" title="${esc(item.url || '')}">${esc(item.url || '-')}</span>
      <span>${esc(status || 'FAIL')}${item.duration_ms != null ? ` · ${esc(Math.round(Number(item.duration_ms)))}ms` : ''}</span>
      <span class="debug-network-detail">${esc(detail)}</span>
    </div>`;
  }).join('') || '<div class="debug-network-row"><span class="debug-network-detail">已保存页面失败现场，未捕获到独立的失败请求。</span></div>';
}

async function pollRegistrationDebug(jobId) {
  if (jobId == null) return;
  try {
    const data = await api(`/api/jobs/${jobId}/debug?limit=300`);
    if (data?.enabled) renderRegistrationDebug(data);
    else renderRegistrationDiagnostics(await api(`/api/jobs/${jobId}/diagnostics?limit=100`));
  } catch (_) {}
}

async function releaseRegistrationDebug() {
  if (activeLogJob == null || !confirm('确定结束调试现场并让任务按原失败结果收口吗？浏览器和代理将被释放。')) return;
  const btn = $('#btnDebugRelease');
  if (btn) btn.disabled = true;
  try {
    await api(`/api/jobs/${activeLogJob}/debug/release`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'finish'})});
    showToast('已请求结束调试现场');
    pollLog();
  } catch (e) { showToast('结束调试失败: ' + e.message); }
  finally { if (btn) btn.disabled = false; }
}

async function compareRegistrationDebug() {
  if (activeLogJob == null) return;
  const out = $('#debugCaptureCompare');
  if (!out) return;
  out.classList.remove('hidden');
  out.textContent = '正在对齐同批成功任务的请求序列…';
  try {
    const data = await api(`/api/jobs/${activeLogJob}/debug/compare`);
    out.textContent = `基线任务 #${data.baseline_job_id} · 差异 ${data.difference_count}\n` +
      (data.differences || []).slice(0, 100).map(diff => {
        const left = diff.baseline ? `${diff.baseline.status || '-'}${diff.baseline.failure ? ' ' + diff.baseline.failure : ''}` : '缺失';
        const right = diff.target ? `${diff.target.status || '-'}${diff.target.failure ? ' ' + diff.target.failure : ''}` : '缺失';
        return `${diff.stage || '-'} ${diff.method} ${diff.host}${diff.path} [${diff.ordinal}]\n  成功: ${left}\n  当前: ${right}`;
      }).join('\n');
  } catch (e) { out.textContent = '对比失败：' + e.message; }
}

$('#btnDebugRelease')?.addEventListener('click', releaseRegistrationDebug);
$('#btnDebugCompare')?.addEventListener('click', compareRegistrationDebug);
