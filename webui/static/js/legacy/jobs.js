// ---------- 注册 / 任务 ----------
function registrationEmailSourceLabel(value) {
  const source = REGISTRATION_EMAIL_SOURCES.find(item => item.value === value);
  return source ? source.label : (value || '-');
}

async function loadRegistrationEmailSources() {
  const select = $('#regEmailSource');
  try {
    const [result, capabilities] = await Promise.all([api('/api/email-sources'), api('/api/capabilities')]);
    CAPABILITIES = capabilities;
    const sourceCaps = capabilities.email_sources || {};
    REGISTRATION_EMAIL_SOURCES = (result.sources || []).map(item => ({...item, ...(sourceCaps[item.value] || {})}));
    applyFeatureGates();
    if (result.manual_mode) {
      select.innerHTML = '<option value="manual">手动 OTP 邮箱</option>';
      select.value = 'manual';
      select.disabled = true;
      return;
    }
    select.disabled = false;
    select.innerHTML = '<option value="">请选择本次邮箱来源</option>' + REGISTRATION_EMAIL_SOURCES.map(source =>
      `<option value="${esc(source.value)}" ${source.enabled === false ? 'disabled' : ''} title="${esc(source.reason || '')}">${esc(source.label)}${source.enabled === false ? '（未配置）' : ''}</option>`
    ).join('');
  } catch (e) {
    select.innerHTML = '<option value="">邮箱来源加载失败</option>';
    select.disabled = true;
    $('#regWarn').innerHTML = `<div class="banner warn">${esc(e.message)}</div>`;
  }
}

$('#btnStart').addEventListener('click', async () => {
  const count = parseInt($('#regCount').value || '1', 10);
  const workers = parseInt($('#regWorkers').value || '3', 10);
  const emailSource = $('#regEmailSource').disabled ? '' : $('#regEmailSource').value;
  const debugEnabled = Boolean($('#regDebug')?.checked);
  if (!$('#regEmailSource').disabled && !emailSource) {
    $('#regWarn').innerHTML = '<div class="banner warn">请先选择本次注册使用的邮箱来源</div>';
    $('#regEmailSource').focus();
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
  $('#btnStart').disabled = true;
  const restoreBtn = () => { $('#btnStart').disabled = false; };
  try {
    const r = await api('/api/jobs', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({count, workers, email_source:emailSource, debug_enabled:debugEnabled}) });
    const sourceLabel = registrationEmailSourceLabel(r.email_source || emailSource);
    const debugLabel = debugEnabled ? '；网络调试已开启' : '';
    $('#regWarn').innerHTML = r.warning ? `<div class="banner warn">${esc(r.warning)}（邮箱来源：${esc(sourceLabel)}；本次并发 ${r.workers || workers}${debugLabel}）</div>` : `<div class="banner info">已提交 ${r.submitted} 个任务，邮箱来源：${esc(sourceLabel)}，本次并发 ${r.workers || workers}${debugLabel}</div>`;
    refreshJobs();
  } catch(e) { $('#regWarn').innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; }
  finally { setTimeout(restoreBtn, 3000); }
});
$('#btnRefreshJobs').addEventListener('click', refreshJobs);
$('#jobsSelectAll').addEventListener('change', (e) => {
  const pageRows = JOBS.filter(j => !['running','stopping'].includes(j.status));
  if (e.target.checked) pageRows.forEach(j => JOB_SELECTED.add(Number(j.id)));
  else pageRows.forEach(j => JOB_SELECTED.delete(Number(j.id)));
  renderJobs();
});
$('#btnDeleteSelectedJobs').addEventListener('click', deleteSelectedJobs);
$('#btnRetrySelectedJobs').addEventListener('click', retrySelectedJobs);
$('#btnCancelPending').addEventListener('click', async () => {
  const pendingCount = Number(JOB_STATUS_COUNTS.pending || 0);
  const msg = pendingCount > 0
    ? `确定取消 ${pendingCount} 个排队中的任务吗？已运行中的任务不受影响。`
    : '当前页没有排队任务；仍要请求后端取消所有排队任务吗？';
  if (!confirm(msg)) return;
  $('#btnCancelPending').disabled = true;
  try {
    const r = await api('/api/jobs/cancel-pending', { method:'POST', headers:{'Content-Type':'application/json'}, body: '{}' });
    showToast(`已取消 ${r.cancelled} 个排队任务`);
    refreshJobs();
  } catch(e) { showToast('取消失败: ' + e.message); }
  finally { $('#btnCancelPending').disabled = false; }
});

function renderJobs() {
  const total = JOBS_TOTAL;
  const rows = JOBS;
  $('#jobsBody').innerHTML = rows.map(j => `
    <tr>
      <td><input type="checkbox" class="job-row-check" data-job-id="${esc(j.id)}" ${JOB_SELECTED.has(Number(j.id)) ? 'checked' : ''} ${['running','stopping'].includes(j.status) ? 'disabled title="运行中的任务不能选择"' : ''}></td>
      <td class="muted">#${esc(j.id)}${j.parent_job_id ? `<div class="sub-cell" title="重试自任务 #${esc(j.parent_job_id)}">↳ #${esc(j.parent_job_id)} · ${esc(j.retry_attempt || 1)}</div>` : ''}</td>
      <td>${pill(j.debug_state === 'paused' ? 'debug_paused' : (j.display_status || j.status))}</td>
      <td title="${esc(j.email || '-')}">${esc(j.email || '-')}</td>
      <td title="${esc(registrationEmailSourceLabel(j.email_source))}">${esc(registrationEmailSourceLabel(j.email_source))}</td>
      <td title="${esc(j.proxy_status || '-')}">${esc(j.proxy_provider ? `${j.proxy_provider}${j.proxy_endpoint && j.proxy_endpoint !== '-' ? ' · ' + j.proxy_endpoint : ''}` : '-')}</td>
      <td class="muted" title="${esc(j.started_at || '-')}">${esc(j.started_at || '-')}</td>
      <td class="muted" title="${esc(j.completed_at || '-')}">${esc(j.completed_at || '-')}</td>
      <td class="muted wrap" title="${esc(j.error_message || '')}">${esc(short(j.error_message || '', 90))}</td>
      <td class="actions-cell">
        <div class="actions job-actions">
          <button data-log-job="${esc(j.id)}">任务日志</button>
          ${j.status === 'running' && j.email && j.manual_otp_required ? `
            <input class="manual-otp-input" data-otp-email="${esc(j.email)}" data-otp-job="${esc(j.id)}" placeholder="邮箱验证码" maxlength="8" style="width:96px;min-height:28px;padding:2px 6px;" title="手动模式下，打开邮箱后把 6 位验证码贴这里">
            <button class="good" data-submit-otp-job="${esc(j.id)}" data-email="${esc(j.email)}">提交验证码</button>
          ` : ''}
          ${['pending','running','stopping'].includes(j.status) ? `<button class="danger" data-stop-job="${esc(j.id)}">${j.status === 'stopping' ? '停止/修复' : '停止'}</button>` : ''}
          ${j.retryable ? `<button class="good" data-retry-job="${esc(j.id)}" title="${esc(j.retry_action === 'codex' ? '账号已创建，仅补跑 Codex 授权' : (j.retry_action === 'twofa' ? '重新登录检查并补齐 2FA' : (j.retry_action === 'registration_resume' ? '使用已保存密码继续邮箱验证' : '创建新的注册任务，不覆盖原任务')))}">${esc(j.retry_label || '重试')}</button>` : ''}
          <button class="danger" data-delete-job="${esc(j.id)}" ${['running','stopping'].includes(j.status) ? 'disabled title="运行中的任务不能删除；如需删除请先停止"' : ''}>删除</button>
        </div>
      </td>
    </tr>`).join('') || '<tr><td colspan="10" class="muted">暂无任务</td></tr>';
  updateJobsSelectionUi(rows);
  _renderPager('jobs', total);
}

function updateJobsSelectionUi(pageRows = null) {
  const hint = $('#jobsSelectedHint');
  const bulkBtn = $('#btnDeleteSelectedJobs');
  const bulkRetryBtn = $('#btnRetrySelectedJobs');
  if (hint) hint.textContent = `已选 ${JOB_SELECTED.size}`;
  if (bulkBtn) bulkBtn.disabled = JOB_SELECTED.size === 0;
  if (bulkRetryBtn) {
    bulkRetryBtn.disabled = JOB_SELECTED.size === 0;
  }

  const cbAll = $('#jobsSelectAll');
  if (!cbAll) return;
  if (!pageRows) {
    pageRows = JOBS;
  }
  const selectableIds = pageRows.filter(j => !['running','stopping'].includes(j.status)).map(j => Number(j.id));
  const checkedCount = selectableIds.filter(id => JOB_SELECTED.has(id)).length;
  cbAll.checked = selectableIds.length > 0 && checkedCount === selectableIds.length;
  cbAll.indeterminate = checkedCount > 0 && checkedCount < selectableIds.length;
  cbAll.disabled = selectableIds.length === 0;
}

async function refreshJobs() {
  if (jobsLoading) return;
  jobsLoading = true;
  try {
    const p = PAGERS.jobs;
    const res = await api(`/api/jobs?paged=1&page=${encodeURIComponent(p.page)}&page_size=${encodeURIComponent(p.size)}`);
    const nextJobs = res.items || [];
    JOBS_TOTAL = Number(res.total || nextJobs.length || 0);
    JOB_STATUS_COUNTS = res.status_counts || {};
    const totalPages = Math.max(1, Math.ceil(JOBS_TOTAL / p.size));
    if (p.page > totalPages) {
      p.page = totalPages;
      jobsLoading = false;
      return refreshJobs();
    }
    const nextSignature = JSON.stringify({items: nextJobs, total: JOBS_TOTAL, status_counts: JOB_STATUS_COUNTS, page: p.page, size: p.size});
    JOBS = nextJobs;
    if (nextSignature !== jobsRenderSignature) {
      jobsRenderSignature = nextSignature;
      renderJobs();
    }
  } catch(e) {}
  finally { jobsLoading = false; }
}

let modalScrollY = 0;
function updateModalScrollLock() {
  const opened = !$('#logPanel').classList.contains('hidden') || !$('#retryLogPanel').classList.contains('hidden') || !$('#liveLogPanel').classList.contains('hidden') || !$('#qrPanel').classList.contains('hidden');
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
function closeRetryLogModal() {
  retryLogEmail = null;
  clearInterval(retryLogTimer);
  $('#retryLogPanel').classList.add('hidden');
  updateModalScrollLock();
}
function closeLiveLogModal() {
  liveLogEmail = null;
  clearInterval(liveLogTimer);
  $('#liveLogPanel').classList.add('hidden');
  updateModalScrollLock();
}
function openQrModal(url) {
  $('#qrImage').src = url;
  $('#qrOpenLink').href = url;
  $('#qrOpenLink').textContent = url;
  $('#qrPanel').classList.remove('hidden');
  updateModalScrollLock();
}
function closeQrModal() {
  $('#qrPanel').classList.add('hidden');
  $('#qrImage').removeAttribute('src');
  updateModalScrollLock();
}

$('#jobsBody').addEventListener('pointerdown', (e) => {
  const retryBtn = e.target.closest('[data-retry-job]');
  if (!retryBtn || retryBtn.disabled || e.button !== 0) return;
  e.preventDefault();
  retryBtn.dataset.pointerHandled = '1';
  retryJob(parseInt(retryBtn.dataset.retryJob, 10), retryBtn);
});

$('#jobsBody').addEventListener('click', (e) => {
  const logBtn = e.target.closest('[data-log-job]');
  if (logBtn) {
    openLog(parseInt(logBtn.dataset.logJob, 10));
    return;
  }
  const otpBtn = e.target.closest('[data-submit-otp-job]');
  if (otpBtn) {
    submitManualOtpForJob(otpBtn);
    return;
  }
  const stopBtn = e.target.closest('[data-stop-job]');
  if (stopBtn) {
    stopJob(parseInt(stopBtn.dataset.stopJob, 10), stopBtn);
    return;
  }
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
  if (delBtn) {
    deleteJob(parseInt(delBtn.dataset.deleteJob, 10), delBtn);
  }
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
$('#jobsBody').addEventListener('change', (e) => {
  const cb = e.target.closest('.job-row-check');
  if (!cb) return;
  const id = Number(cb.dataset.jobId);
  if (cb.checked) JOB_SELECTED.add(id);
  else JOB_SELECTED.delete(id);
  updateJobsSelectionUi();
});
$('#btnCloseLog').addEventListener('click', closeLogModal);

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

  $('#btnDeleteSelectedJobs').disabled = true;
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
  const job = JOBS.find(j => Number(j.id) === Number(jobId));
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
  const btn = $('#btnRetrySelectedJobs');
  btn.disabled = true;
  try {
    const r = await api('/api/jobs/retry-bulk', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({job_ids: ids}),
    });
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
  $('#logContent').textContent = '加载中…';
  $('#debugCapturePanel')?.classList.add('hidden');
  $('#debugCaptureCompare')?.classList.add('hidden');
  $('#debugCaptureTitle').textContent = '网络调试';
  const screenshot = $('#btnFailureDiagnosticScreenshot');
  if (screenshot) { screenshot.classList.add('hidden'); screenshot.removeAttribute('href'); }
  const pageState = $('#debugCapturePageState');
  if (pageState) { pageState.classList.add('hidden'); pageState.textContent = ''; }
  pollLog();
  clearInterval(logTimer);
  logTimer = setInterval(pollLog, 2000);
}
async function pollLog() {
  if (activeLogJob == null) return;
  try {
    const r = await api(`/api/jobs/${activeLogJob}/log`);
    const c = $('#logContent');
    const atBottom = c.scrollTop + c.clientHeight >= c.scrollHeight - 30;
    c.textContent = r.log || '(暂无日志)';
    if (atBottom) c.scrollTop = c.scrollHeight;
    await pollRegistrationDebug(activeLogJob);
    if (r.job && ['success','partial_success','failed','stopped','cancelled'].includes(r.job.status)) clearInterval(logTimer);
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
  if (!data?.enabled) { panel.classList.add('hidden'); return; }
  $('#debugCaptureTitle').textContent = '网络调试';
  $('#btnFailureDiagnosticScreenshot')?.classList.add('hidden');
  $('#debugCapturePageState')?.classList.add('hidden');
  panel.classList.remove('hidden');
  const summary = data.summary || {};
  const state = data.state || summary.state || 'recording';
  $('#debugCaptureSummary').textContent = `状态 ${state} · 请求 ${summary.request_count || 0} · HTTP错误 ${summary.http_error_count || 0} · 网络失败 ${summary.failed_count || 0}` + (data.hold_until ? ` · 保留至 ${data.hold_until}` : '');
  $('#btnDebugRelease')?.classList.toggle('hidden', state !== 'paused');
  $('#btnDebugCompare')?.classList.remove('hidden');
  const har = $('#btnDebugHar');
  if (har) { har.classList.remove('hidden'); har.href = `/api/jobs/${encodeURIComponent(data.job_id)}/debug/har`; }
  const rows = Array.isArray(data.events) ? data.events : [];
  $('#debugNetworkList').innerHTML = rows.map(item => {
    const status = Number(item.status || 0);
    const isError = Boolean(item.failure) || status >= 400;
    const detail = item.failure || debugBodySnippet(item.response_body);
    return `<div class="debug-network-row${isError ? ' is-error' : ''}">
      <span>${esc(item.stage || '-')}</span><strong>${esc(item.method || '-')}</strong>
      <span class="debug-network-url" title="${esc(item.url || '')}">${esc(item.url || '-')}</span>
      <span>${esc(status || (item.failure ? 'FAIL' : '-'))}${item.duration_ms != null ? ` · ${esc(Math.round(Number(item.duration_ms)))}ms` : ''}</span>
      ${detail ? `<span class="debug-network-detail">${esc(detail)}</span>` : ''}
    </div>`;
  }).join('') || '<div class="debug-network-row"><span class="debug-network-detail">抓包已启动，暂时还没有可显示的请求。</span></div>';
}

function renderRegistrationDiagnostics(data) {
  const panel = $('#debugCapturePanel');
  if (!panel) return;
  if (!data?.enabled || !data?.captured) { panel.classList.add('hidden'); return; }
  panel.classList.remove('hidden');
  $('#debugCaptureTitle').textContent = '失败诊断';
  const summary = data.summary || {};
  const page = data.page_state || {};
  const dom = page.dom || {};
  $('#debugCaptureSummary').textContent = `分类 ${data.category_label || data.category || page.failure_category || '未分类'} · 输入框 ${Number(dom.input_count || 0)} · 操作 ${Number(dom.action_count || 0)} · 失败请求 ${Number(summary.failed_count || 0)} · HTTP错误 ${Number(summary.http_error_count || 0)}`;
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
    pageState.textContent = [
      `URL: ${page.url || '-'}`,
      `标题: ${page.title || '-'} · readyState: ${page.ready_state || '-'}`,
      `原因: ${data.failure_reason || page.reason || '-'}`,
      `资源: ${Array.isArray(page.resources) ? page.resources.length : 0} 条 · 浏览器错误: ${Array.isArray(page.browser_logs) ? page.browser_logs.length : 0} 条`,
      `页面文本: ${short(page.body_text || '', 800) || '-'}`,
    ].join('\n');
    pageState.classList.remove('hidden');
  }
  const rows = Array.isArray(data.events) ? data.events : [];
  $('#debugNetworkList').innerHTML = rows.map(item => {
    const status = Number(item.status || 0);
    return `<div class="debug-network-row is-error">
      <span>${esc(item.stage || '-')}</span><strong>${esc(item.method || '-')}</strong>
      <span class="debug-network-url" title="${esc(item.url || '')}">${esc(item.url || '-')}</span>
      <span>${esc(status || 'FAIL')}${item.duration_ms != null ? ` · ${esc(Math.round(Number(item.duration_ms)))}ms` : ''}</span>
      <span class="debug-network-detail">${esc(item.failure || 'HTTP错误')}</span>
    </div>`;
  }).join('') || '<div class="debug-network-row"><span class="debug-network-detail">已保存页面失败现场，未捕获到独立的失败请求。</span></div>';
}

async function pollRegistrationDebug(jobId) {
  if (jobId == null) return;
  try {
    const data = await api(`/api/jobs/${jobId}/debug?limit=300`);
    if (data?.enabled) renderRegistrationDebug(data);
    else renderRegistrationDiagnostics(await api(`/api/jobs/${jobId}/diagnostics?limit=100`));
  }
  catch (_) {}
}

$('#btnDebugRelease')?.addEventListener('click', async () => {
  if (activeLogJob == null || !confirm('确定结束调试现场并让任务按原失败结果收口吗？浏览器和代理将被释放。')) return;
  try {
    await api(`/api/jobs/${activeLogJob}/debug/release`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'finish'})});
    showToast('已请求结束调试现场');
    pollLog();
  } catch (e) { showToast('结束调试失败: ' + e.message); }
});

$('#btnDebugCompare')?.addEventListener('click', async () => {
  if (activeLogJob == null) return;
  const out = $('#debugCaptureCompare');
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
});
